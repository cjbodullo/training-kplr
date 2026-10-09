// Calibration baseline "L1": what an engineer writes after one profiling pass
// over the shipped logstat - pointer based line parsing instead of getline and
// substr, a segment trie instead of the linear scan over every pattern, and
// hash containers instead of std::map.  Idiomatic C++ throughout: std::string
// keys, unordered_set per group, std::sort, nth_element.
#include <algorithm>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <map>
#include <sstream>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <vector>

typedef int64_t i64;
typedef int32_t i32;

static bool read_file(const char *path, std::string *out) {
    std::ifstream in(path, std::ios::binary);
    if (!in) return false;
    std::ostringstream ss;
    ss << in.rdbuf();
    *out = ss.str();
    return true;
}

static inline bool digit(char c) { return c >= '0' && c <= '9'; }
static inline int d2(const char *p) { return (p[0] - '0') * 10 + (p[1] - '0'); }

static i64 days_from_civil(i64 y, unsigned m, unsigned d) {
    y -= m <= 2;
    const i64 era = (y >= 0 ? y : y - 399) / 400;
    const unsigned yoe = static_cast<unsigned>(y - era * 400);
    const unsigned doy = (153 * (m + (m > 2 ? -3 : 9)) + 2) / 5 + d - 1;
    const unsigned doe = yoe * 365 + yoe / 4 - yoe / 100 + doy;
    return era * 146097 + static_cast<i64>(doe) - 719468;
}

static int month_of(const char *p) {
    static const char *names[12] = {"Jan", "Feb", "Mar", "Apr", "May", "Jun",
                                    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"};
    for (int i = 0; i < 12; i++) {
        if (memcmp(p, names[i], 3) == 0) return i + 1;
    }
    return -1;
}

static int hexval(char c) {
    if (c >= '0' && c <= '9') return c - '0';
    if (c >= 'a' && c <= 'f') return c - 'a' + 10;
    if (c >= 'A' && c <= 'F') return c - 'A' + 10;
    return -1;
}

struct Record {
    std::string client;
    std::string method;
    std::string rid;
    std::vector<std::string> segs;
    i64 end_epoch = 0;
    i64 bytes = 0;
    i32 rt_ms = 0;
    i32 upstream_ms = 0;
    int status = 0;
};

static i32 parse_ms(const char *p, const char *end, const char **next, bool *ok) {
    const char *s = p;
    i64 whole = 0;
    while (p < end && digit(*p)) {
        whole = whole * 10 + (*p - '0');
        p++;
        if (p - s > 7) {
            *ok = false;
            return 0;
        }
    }
    if (p == s || p + 3 >= end || *p != '.' || !digit(p[1]) || !digit(p[2]) || !digit(p[3])) {
        *ok = false;
        return 0;
    }
    i64 ms = whole * 1000 + (p[1] - '0') * 100 + (p[2] - '0') * 10 + (p[3] - '0');
    if (ms > 899999) {
        *ok = false;
        return 0;
    }
    *next = p + 4;
    *ok = true;
    return static_cast<i32>(ms);
}

static const char *skip_quoted(const char *p, const char *end, const char **body_end) {
    if (p >= end || *p != '"') return nullptr;
    p++;
    while (p < end) {
        if (*p == '\\') {
            p += 2;
            continue;
        }
        if (*p == '"') {
            *body_end = p;
            return p + 1;
        }
        p++;
    }
    return nullptr;
}

static bool parse_line(const char *p, const char *end, Record *out) {
    if (end - p < 40) return false;
    const char *sp = static_cast<const char *>(memchr(p, ' ', end - p));
    if (!sp || sp == p || sp - p > 45) return false;
    out->client.assign(p, sp - p);
    p = sp + 1;
    sp = static_cast<const char *>(memchr(p, ' ', end - p));
    if (!sp) return false;
    p = sp + 1;
    sp = static_cast<const char *>(memchr(p, ' ', end - p));
    if (!sp) return false;
    p = sp + 1;

    if (p + 28 > end || *p != '[' || p[27] != ']') return false;
    const char *t = p + 1;
    if (t[2] != '/' || t[6] != '/' || t[11] != ':' || t[14] != ':' || t[17] != ':' ||
        t[20] != ' ') {
        return false;
    }
    for (int i : {0, 1, 7, 8, 9, 10, 12, 13, 15, 16, 18, 19}) {
        if (!digit(t[i])) return false;
    }
    int mon = month_of(t + 3);
    if (mon < 0) return false;
    int day = d2(t);
    int year = (t[7] - '0') * 1000 + (t[8] - '0') * 100 + (t[9] - '0') * 10 + (t[10] - '0');
    int hh = d2(t + 12), mi = d2(t + 15), ss = d2(t + 18);
    if (day < 1 || day > 31 || hh > 23 || mi > 59 || ss > 59 || year < 1970 || year > 2999) {
        return false;
    }
    if ((t[21] != '+' && t[21] != '-') || !digit(t[22]) || !digit(t[23]) || !digit(t[24]) ||
        !digit(t[25])) {
        return false;
    }
    int offsec = d2(t + 22) * 3600 + d2(t + 24) * 60;
    if (t[21] == '-') offsec = -offsec;
    out->end_epoch = days_from_civil(year, mon, day) * 86400 + hh * 3600 + mi * 60 + ss - offsec;
    p += 28;
    if (p >= end || *p != ' ') return false;
    p++;

    const char *req_end = nullptr;
    const char *after = skip_quoted(p, end, &req_end);
    if (!after) return false;
    const char *r = p + 1;
    const char *msp = static_cast<const char *>(memchr(r, ' ', req_end - r));
    if (!msp) return false;
    out->method.assign(r, msp - r);
    if (out->method.empty() || out->method.size() > 15) return false;
    for (size_t i = 0; i < out->method.size(); i++) {
        if (out->method[i] < 'A' || out->method[i] > 'Z') return false;
    }
    const char *target = msp + 1;
    const char *tsp = static_cast<const char *>(memchr(target, ' ', req_end - target));
    if (!tsp) return false;
    if (req_end - tsp < 6 || memcmp(tsp + 1, "HTTP/", 5) != 0) return false;
    const char *tend = tsp;
    if (tend - target > 7 && memcmp(target, "http", 4) == 0) {
        const char *host = nullptr;
        if (memcmp(target, "http://", 7) == 0) {
            host = target + 7;
        } else if (tend - target > 8 && memcmp(target, "https://", 8) == 0) {
            host = target + 8;
        }
        if (host) {
            const char *slash = static_cast<const char *>(memchr(host, '/', tend - host));
            target = slash ? slash : tend;
        }
    }
    {
        const char *q = static_cast<const char *>(memchr(target, '?', tend - target));
        if (q) tend = q;
        const char *f = static_cast<const char *>(memchr(target, '#', tend - target));
        if (f) tend = f;
    }
    if (target >= tend || *target != '/') return false;
    out->segs.clear();
    const char *s = target;
    while (s < tend) {
        while (s < tend && *s == '/') s++;
        if (s >= tend) break;
        const char *e2 = static_cast<const char *>(memchr(s, '/', tend - s));
        if (!e2) e2 = tend;
        std::string seg;
        seg.reserve(e2 - s);
        for (const char *c = s; c < e2;) {
            if (*c == '%' && e2 - c >= 3) {
                int hi = hexval(c[1]), lo = hexval(c[2]);
                if (hi >= 0 && lo >= 0) {
                    seg.push_back(static_cast<char>(hi * 16 + lo));
                    c += 3;
                    continue;
                }
            }
            seg.push_back(*c++);
        }
        out->segs.push_back(seg);
        s = e2 + 1;
    }
    p = after;
    if (p >= end || *p != ' ') return false;
    p++;

    if (p + 4 > end || !digit(p[0]) || !digit(p[1]) || !digit(p[2]) || p[3] != ' ') return false;
    out->status = (p[0] - '0') * 100 + (p[1] - '0') * 10 + (p[2] - '0');
    if (out->status < 100) return false;
    p += 4;
    if (p >= end) return false;
    if (*p == '-' && p + 1 < end && p[1] == ' ') {
        out->bytes = 0;
        p += 2;
    } else {
        i64 b = 0;
        const char *s0 = p;
        while (p < end && digit(*p)) {
            b = b * 10 + (*p - '0');
            p++;
            if (p - s0 > 18) return false;
        }
        if (p == s0 || p >= end || *p != ' ') return false;
        out->bytes = b;
        p++;
    }
    const char *body_end = nullptr;
    p = skip_quoted(p, end, &body_end);
    if (!p || p >= end || *p != ' ') return false;
    p++;
    p = skip_quoted(p, end, &body_end);
    if (!p || p >= end || *p != ' ') return false;
    p++;

    if (end - p < 4 || memcmp(p, "rt=", 3) != 0) return false;
    p += 3;
    bool ok = false;
    out->rt_ms = parse_ms(p, end, &p, &ok);
    if (!ok || p >= end || *p != ' ') return false;
    p++;
    if (end - p < 5 || memcmp(p, "uct=", 4) != 0) return false;
    p += 4;
    if (*p == '-') {
        p++;
    } else {
        parse_ms(p, end, &p, &ok);
        if (!ok) return false;
    }
    if (p >= end || *p != ' ') return false;
    p++;
    if (end - p < 5 || memcmp(p, "urt=", 4) != 0) return false;
    p += 4;
    i32 up = 0;
    if (*p == '-' && p + 1 < end && p[1] == ' ') {
        p++;
    } else {
        int count = 0;
        while (true) {
            if (p < end && *p == '-') {
                p++;
            } else {
                up += parse_ms(p, end, &p, &ok);
                if (!ok) return false;
            }
            if (++count > 8) return false;
            if (p + 1 < end && p[0] == ',' && p[1] == ' ') {
                p += 2;
                continue;
            }
            break;
        }
    }
    out->upstream_ms = up;
    if (p >= end || *p != ' ') return false;
    p++;
    if (end - p < 5 || memcmp(p, "rid=", 4) != 0) return false;
    p += 4;
    const char *rid = p;
    while (p < end && *p != ' ') p++;
    size_t rlen = p - rid;
    if (rlen == 0 || rlen > 64) return false;
    if (rlen == 1 && *rid == '-') {
        out->rid.clear();
    } else {
        for (size_t i = 0; i < rlen; i++) {
            char c = rid[i];
            bool good = (c >= '0' && c <= '9') || (c >= 'a' && c <= 'z') ||
                        (c >= 'A' && c <= 'Z') || c == '-' || c == '_';
            if (!good) return false;
        }
        out->rid.assign(rid, rlen);
    }
    if (p >= end || *p != ' ') return false;
    p++;
    if (end - p < 5 || memcmp(p, "att=", 4) != 0) return false;
    p += 4;
    const char *att = p;
    i64 a = 0;
    while (p < end && digit(*p)) {
        a = a * 10 + (*p - '0');
        p++;
    }
    if (p == att || p - att > 2 || a < 1) return false;
    return p == end;
}

// ------------------------------------------------------------------- routing

enum { kLiteral = 0, kParam = 1, kStar = 2, kTail = 3 };

struct Pat {
    std::string method, pattern, service;
    int slo_ms = 0;
};

struct TNode {
    std::unordered_map<std::string, int> lit;
    int param = -1, star = -1;
    std::vector<std::pair<std::string, int> > ends;   // method -> pattern id
    std::vector<std::pair<std::string, int> > tails;  // ** patterns
};

struct Router {
    std::vector<TNode> nodes;
    std::vector<Pat> pats;

    bool load(const char *path) {
        std::string buf;
        if (!read_file(path, &buf)) return false;
        nodes.push_back(TNode());
        std::istringstream in(buf);
        std::string line;
        std::map<std::string, bool> seen;
        while (std::getline(in, line)) {
            if (line.empty() || line[0] == '#') continue;
            std::vector<std::string> f;
            size_t a = 0;
            while (true) {
                size_t b = line.find('\t', a);
                if (b == std::string::npos) {
                    f.push_back(line.substr(a));
                    break;
                }
                f.push_back(line.substr(a, b - a));
                a = b + 1;
            }
            if (f.size() != 4) return false;
            Pat p;
            p.method = f[0];
            p.pattern = f[1];
            p.service = f[2];
            p.slo_ms = atoi(f[3].c_str());
            if (p.pattern.empty() || p.pattern[0] != '/') return false;
            if (seen.count(p.method + "\t" + p.pattern)) continue;
            seen[p.method + "\t" + p.pattern] = true;
            std::vector<std::string> segs;
            std::vector<int> kinds;
            size_t k = 1;
            while (k <= p.pattern.size()) {
                size_t m = p.pattern.find('/', k);
                if (m == std::string::npos) m = p.pattern.size();
                if (m > k) {
                    std::string seg = p.pattern.substr(k, m - k);
                    int kind = kLiteral;
                    if (seg == "**") {
                        kind = kTail;
                    } else if (seg == "*") {
                        kind = kStar;
                    } else if (seg.size() >= 2 && seg[0] == '{' &&
                               seg[seg.size() - 1] == '}') {
                        kind = kParam;
                    }
                    segs.push_back(seg);
                    kinds.push_back(kind);
                }
                k = m + 1;
            }
            for (size_t t = 0; t + 1 < kinds.size(); t++) {
                if (kinds[t] == kTail) return false;
            }
            int pid = static_cast<int>(pats.size());
            pats.push_back(p);
            int node = 0;
            bool tail = false;
            for (size_t t = 0; t < segs.size(); t++) {
                if (kinds[t] == kTail) {
                    tail = true;
                    break;
                }
                if (kinds[t] == kLiteral) {
                    std::unordered_map<std::string, int>::iterator it =
                        nodes[node].lit.find(segs[t]);
                    if (it == nodes[node].lit.end()) {
                        nodes.push_back(TNode());
                        int idx = static_cast<int>(nodes.size() - 1);
                        nodes[node].lit[segs[t]] = idx;
                        node = idx;
                    } else {
                        node = it->second;
                    }
                } else if (kinds[t] == kParam) {
                    if (nodes[node].param < 0) {
                        nodes.push_back(TNode());
                        nodes[node].param = static_cast<int>(nodes.size() - 1);
                    }
                    node = nodes[node].param;
                } else {
                    if (nodes[node].star < 0) {
                        nodes.push_back(TNode());
                        nodes[node].star = static_cast<int>(nodes.size() - 1);
                    }
                    node = nodes[node].star;
                }
            }
            if (tail) {
                nodes[node].tails.push_back(std::make_pair(p.method, pid));
            } else {
                nodes[node].ends.push_back(std::make_pair(p.method, pid));
            }
        }
        return true;
    }

    int pick(const std::vector<std::pair<std::string, int> > &v,
             const std::string &method) const {
        int lit = -1, star = -1;
        for (size_t i = 0; i < v.size(); i++) {
            if (v[i].first == method) {
                if (lit < 0 || pats[v[i].second].pattern < pats[lit].pattern) lit = v[i].second;
            } else if (v[i].first == "*") {
                if (star < 0 || pats[v[i].second].pattern < pats[star].pattern) {
                    star = v[i].second;
                }
            }
        }
        return lit >= 0 ? lit : star;
    }

    int dfs(int node, const std::vector<std::string> &segs, size_t i,
            const std::string &method) const {
        const TNode &n = nodes[node];
        if (i == segs.size()) {
            if (!n.ends.empty()) {
                int r = pick(n.ends, method);
                if (r >= 0) return r;
            }
            if (!n.tails.empty()) {
                int r = pick(n.tails, method);
                if (r >= 0) return r;
            }
            return -1;
        }
        std::unordered_map<std::string, int>::const_iterator it = n.lit.find(segs[i]);
        if (it != n.lit.end()) {
            int r = dfs(it->second, segs, i + 1, method);
            if (r >= 0) return r;
        }
        if (n.param >= 0) {
            int r = dfs(n.param, segs, i + 1, method);
            if (r >= 0) return r;
        }
        if (n.star >= 0) {
            int r = dfs(n.star, segs, i + 1, method);
            if (r >= 0) return r;
        }
        if (!n.tails.empty()) {
            int r = pick(n.tails, method);
            if (r >= 0) return r;
        }
        return -1;
    }
};

// ---------------------------------------------------------------- aggregation

struct Group {
    i64 requests = 0, e4 = 0, e5 = 0, bytes = 0, upstream = 0, breaches = 0;
    i64 logical = 0, retried = 0, peak_bucket_clients = 0;
    std::vector<i32> lat;
    std::vector<i64> logical_lat;
    std::unordered_set<std::string> clients;
};

struct Bucket {
    i64 requests = 0;
    i64 peak = 0;
    std::vector<i32> lat;
};

struct Logical {
    i64 min_start = 0, max_end = 0;
    i64 attempts = 0;
    int group = 0;
};

static i64 quant(std::vector<i32> *v, int q) {
    if (v->empty()) return 0;
    size_t n = v->size();
    size_t rank = (n * q + 99) / 100;
    if (rank < 1) rank = 1;
    std::nth_element(v->begin(), v->begin() + (rank - 1), v->end());
    return (*v)[rank - 1];
}

static i64 quant64(std::vector<i64> *v, int q) {
    if (v->empty()) return 0;
    size_t n = v->size();
    size_t rank = (n * q + 99) / 100;
    if (rank < 1) rank = 1;
    std::nth_element(v->begin(), v->begin() + (rank - 1), v->end());
    return (*v)[rank - 1];
}

static void json_str(std::string *out, const std::string &s) {
    out->push_back('"');
    for (size_t i = 0; i < s.size(); i++) {
        unsigned char c = static_cast<unsigned char>(s[i]);
        if (c == '"' || c == '\\') {
            out->push_back('\\');
            out->push_back(static_cast<char>(c));
        } else if (c < 0x20 || c >= 0x7f) {
            char tmp[8];
            snprintf(tmp, sizeof(tmp), "\\u%04x", c);
            *out += tmp;
        } else {
            out->push_back(static_cast<char>(c));
        }
    }
    out->push_back('"');
}

static void json_num(std::string *out, i64 v) {
    char tmp[24];
    snprintf(tmp, sizeof(tmp), "%lld", static_cast<long long>(v));
    *out += tmp;
}

int main(int argc, char **argv) {
    if (argc != 5) {
        fprintf(stderr, "usage: quick <access.log> <routes.tsv> <deploys.csv> <out.json>\n");
        return 2;
    }
    Router router;
    if (!router.load(argv[2])) {
        fprintf(stderr, "quick: bad route table\n");
        return 1;
    }
    const int npat = static_cast<int>(router.pats.size());

    struct Win {
        i64 start, end;
        std::string release;
    };
    std::unordered_map<std::string, std::vector<Win> > windows;
    {
        std::string buf;
        if (!read_file(argv[3], &buf)) return 1;
        std::istringstream in(buf);
        std::string line;
        bool first = true;
        while (std::getline(in, line)) {
            if (line.empty()) continue;
            if (first) {
                first = false;
                if (line.compare(0, 7, "service") == 0) continue;
            }
            std::vector<std::string> f;
            size_t a = 0;
            while (true) {
                size_t b = line.find(',', a);
                if (b == std::string::npos) {
                    f.push_back(line.substr(a));
                    break;
                }
                f.push_back(line.substr(a, b - a));
                a = b + 1;
            }
            if (f.size() != 4) return 1;
            Win w;
            w.start = atoll(f[2].c_str());
            w.end = atoll(f[3].c_str());
            w.release = f[1];
            windows[f[0]].push_back(w);
        }
    }

    std::string log;
    if (!read_file(argv[1], &log)) return 1;

    std::vector<Group> groups(npat + 1);
    std::unordered_set<std::string> all_clients, all_rids;
    std::unordered_map<std::string, Logical> logicals;
    std::unordered_map<std::string, Bucket> buckets;              // service\tbucket
    std::unordered_map<std::string, std::vector<std::pair<i64, int> > > events;
    std::unordered_map<std::string, i64> rel_requests, rel_breaches;
    std::unordered_map<std::string, std::unordered_map<std::string, i64> > rel_routes;
    std::unordered_map<std::string, std::unordered_set<std::string> > group_bucket_clients;

    i64 lines_total = 0, lines_damaged = 0, lines_parsed = 0, unmatched = 0;
    Record rec;
    const char *p = log.data();
    const char *end = p + log.size();
    while (p < end) {
        const char *nl = static_cast<const char *>(memchr(p, '\n', end - p));
        const char *lend = nl ? nl : end;
        lines_total++;
        if (!parse_line(p, lend, &rec)) {
            lines_damaged++;
            p = lend + 1;
            continue;
        }
        lines_parsed++;
        int pid = router.dfs(0, rec.segs, 0, rec.method);
        int gid = pid < 0 ? npat : pid;
        std::string service = pid < 0 ? "-" : router.pats[pid].service;
        i64 slo = pid < 0 ? 0 : router.pats[pid].slo_ms;
        if (pid < 0) unmatched++;

        Group &g = groups[gid];
        g.requests++;
        if (rec.status >= 500) {
            g.e5++;
        } else if (rec.status >= 400) {
            g.e4++;
        }
        g.bytes += rec.bytes;
        g.upstream += rec.upstream_ms;
        bool breach = pid >= 0 && rec.rt_ms > slo;
        if (breach) g.breaches++;
        g.lat.push_back(rec.rt_ms);
        g.clients.insert(rec.client);
        all_clients.insert(rec.client);
        if (!rec.rid.empty()) all_rids.insert(rec.rid);

        i64 bucket = (rec.end_epoch / 300) * 300;
        char bk[64];
        snprintf(bk, sizeof(bk), "%lld", static_cast<long long>(bucket));
        std::string bkey = service + "\t" + bk;
        Bucket &b = buckets[bkey];
        b.requests++;
        b.lat.push_back(rec.rt_ms);

        char gk[64];
        snprintf(gk, sizeof(gk), "%d\t%lld", gid, static_cast<long long>(bucket));
        group_bucket_clients[gk].insert(rec.client);

        i64 end_ms = rec.end_epoch * 1000;
        i64 start_ms = end_ms - rec.rt_ms;
        std::vector<std::pair<i64, int> > &ev = events[service];
        ev.push_back(std::make_pair(start_ms, 1));
        ev.push_back(std::make_pair(end_ms, -1));

        if (rec.rid.empty()) {
            g.logical++;
            g.logical_lat.push_back(rec.rt_ms);
        } else {
            std::unordered_map<std::string, Logical>::iterator it = logicals.find(rec.rid);
            if (it == logicals.end()) {
                Logical lg;
                lg.min_start = start_ms;
                lg.max_end = end_ms;
                lg.attempts = 1;
                lg.group = gid;
                logicals[rec.rid] = lg;
            } else {
                Logical &lg = it->second;
                if (start_ms < lg.min_start) lg.min_start = start_ms;
                if (end_ms >= lg.max_end) {
                    lg.max_end = end_ms;
                    lg.group = gid;
                }
                lg.attempts++;
            }
        }

        std::unordered_map<std::string, std::vector<Win> >::iterator wit =
            windows.find(service);
        if (pid >= 0 && wit != windows.end()) {
            for (size_t i = 0; i < wit->second.size(); i++) {
                const Win &w = wit->second[i];
                if (rec.end_epoch < w.start || rec.end_epoch >= w.end) continue;
                std::string key = service + "\t" + w.release;
                rel_requests[key]++;
                if (breach) {
                    rel_breaches[key]++;
                    rel_routes[key][router.pats[pid].pattern]++;
                }
                break;
            }
        }
        p = lend + 1;
    }

    for (std::unordered_map<std::string, Logical>::iterator it = logicals.begin();
         it != logicals.end(); ++it) {
        Group &g = groups[it->second.group];
        g.logical++;
        if (it->second.attempts >= 2) g.retried++;
        g.logical_lat.push_back(it->second.max_end - it->second.min_start);
    }
    for (std::unordered_map<std::string, std::unordered_set<std::string> >::iterator it =
             group_bucket_clients.begin();
         it != group_bucket_clients.end(); ++it) {
        int gid = atoi(it->first.c_str());
        i64 n = static_cast<i64>(it->second.size());
        if (n > groups[gid].peak_bucket_clients) groups[gid].peak_bucket_clients = n;
    }
    for (std::unordered_map<std::string, std::vector<std::pair<i64, int> > >::iterator it =
             events.begin();
         it != events.end(); ++it) {
        std::vector<std::pair<i64, int> > &ev = it->second;
        std::sort(ev.begin(), ev.end());
        i64 inflight = 0;
        for (size_t i = 0; i < ev.size(); i++) {
            inflight += ev[i].second;
            i64 bucket = (ev[i].first / 300000) * 300;
            char bk[64];
            snprintf(bk, sizeof(bk), "%lld", static_cast<long long>(bucket));
            std::unordered_map<std::string, Bucket>::iterator bit =
                buckets.find(it->first + "\t" + bk);
            if (bit == buckets.end()) continue;
            if (inflight > bit->second.peak) bit->second.peak = inflight;
        }
    }

    std::string out;
    out.reserve(1 << 20);
    out += "{\"version\":1,\"totals\":{\"lines_total\":";
    json_num(&out, lines_total);
    out += ",\"lines_damaged\":";
    json_num(&out, lines_damaged);
    out += ",\"lines_parsed\":";
    json_num(&out, lines_parsed);
    out += ",\"unmatched\":";
    json_num(&out, unmatched);
    out += ",\"distinct_clients\":";
    json_num(&out, static_cast<i64>(all_clients.size()));
    out += ",\"distinct_request_ids\":";
    json_num(&out, static_cast<i64>(all_rids.size()));
    out += "},\"routes\":[";
    std::vector<int> order;
    for (int g = 0; g <= npat; g++) {
        if (groups[g].requests > 0) order.push_back(g);
    }
    const std::string dash = "-";
    std::sort(order.begin(), order.end(), [&](int a, int b) {
        const std::string &sa = a == npat ? dash : router.pats[a].service;
        const std::string &sb = b == npat ? dash : router.pats[b].service;
        if (sa != sb) return sa < sb;
        const std::string &pa = a == npat ? dash : router.pats[a].pattern;
        const std::string &pb = b == npat ? dash : router.pats[b].pattern;
        if (pa != pb) return pa < pb;
        const std::string &ma = a == npat ? dash : router.pats[a].method;
        const std::string &mb = b == npat ? dash : router.pats[b].method;
        return ma < mb;
    });
    for (size_t i = 0; i < order.size(); i++) {
        int gid = order[i];
        Group &g = groups[gid];
        if (i) out += ",";
        out += "{\"service\":";
        json_str(&out, gid == npat ? dash : router.pats[gid].service);
        out += ",\"pattern\":";
        json_str(&out, gid == npat ? dash : router.pats[gid].pattern);
        out += ",\"method\":";
        json_str(&out, gid == npat ? dash : router.pats[gid].method);
        out += ",\"slo_ms\":";
        json_num(&out, gid == npat ? 0 : router.pats[gid].slo_ms);
        out += ",\"requests\":";
        json_num(&out, g.requests);
        out += ",\"errors_4xx\":";
        json_num(&out, g.e4);
        out += ",\"errors_5xx\":";
        json_num(&out, g.e5);
        out += ",\"bytes\":";
        json_num(&out, g.bytes);
        out += ",\"upstream_ms\":";
        json_num(&out, g.upstream);
        out += ",\"slo_breaches\":";
        json_num(&out, g.breaches);
        out += ",\"p50_ms\":";
        json_num(&out, quant(&g.lat, 50));
        out += ",\"p95_ms\":";
        json_num(&out, quant(&g.lat, 95));
        out += ",\"p99_ms\":";
        json_num(&out, quant(&g.lat, 99));
        out += ",\"distinct_clients\":";
        json_num(&out, static_cast<i64>(g.clients.size()));
        out += ",\"logical_requests\":";
        json_num(&out, g.logical);
        out += ",\"retried_logical\":";
        json_num(&out, g.retried);
        out += ",\"p95_logical_ms\":";
        json_num(&out, quant64(&g.logical_lat, 95));
        out += ",\"peak_bucket_clients\":";
        json_num(&out, g.peak_bucket_clients);
        out += "}";
    }
    out += "],\"buckets\":[";
    {
        std::vector<std::pair<std::pair<std::string, i64>, Bucket *> > bs;
        for (std::unordered_map<std::string, Bucket>::iterator it = buckets.begin();
             it != buckets.end(); ++it) {
            size_t tab = it->first.find('\t');
            bs.push_back(std::make_pair(
                std::make_pair(it->first.substr(0, tab), atoll(it->first.c_str() + tab + 1)),
                &it->second));
        }
        std::sort(bs.begin(), bs.end(),
                  [](const std::pair<std::pair<std::string, i64>, Bucket *> &a,
                     const std::pair<std::pair<std::string, i64>, Bucket *> &b) {
                      return a.first < b.first;
                  });
        for (size_t i = 0; i < bs.size(); i++) {
            if (i) out += ",";
            out += "{\"service\":";
            json_str(&out, bs[i].first.first);
            out += ",\"start_epoch\":";
            json_num(&out, bs[i].first.second);
            out += ",\"requests\":";
            json_num(&out, bs[i].second->requests);
            out += ",\"p99_ms\":";
            json_num(&out, quant(&bs[i].second->lat, 99));
            out += ",\"peak_inflight\":";
            json_num(&out, bs[i].second->peak);
            out += "}";
        }
    }
    out += "],\"releases\":[";
    {
        std::vector<std::string> keys;
        for (std::unordered_map<std::string, i64>::iterator it = rel_requests.begin();
             it != rel_requests.end(); ++it) {
            keys.push_back(it->first);
        }
        std::sort(keys.begin(), keys.end());
        for (size_t i = 0; i < keys.size(); i++) {
            size_t tab = keys[i].find('\t');
            if (i) out += ",";
            out += "{\"service\":";
            json_str(&out, keys[i].substr(0, tab));
            out += ",\"release\":";
            json_str(&out, keys[i].substr(tab + 1));
            i64 req = rel_requests[keys[i]];
            i64 br = rel_breaches.count(keys[i]) ? rel_breaches[keys[i]] : 0;
            out += ",\"requests\":";
            json_num(&out, req);
            out += ",\"breaches\":";
            json_num(&out, br);
            out += ",\"breach_ppm\":";
            json_num(&out, req > 0 ? (br * 1000000) / req : 0);
            out += ",\"top_routes\":[";
            std::vector<std::pair<i64, std::string> > tops;
            if (rel_routes.count(keys[i])) {
                for (std::unordered_map<std::string, i64>::iterator it =
                         rel_routes[keys[i]].begin();
                     it != rel_routes[keys[i]].end(); ++it) {
                    if (it->second > 0) tops.push_back(std::make_pair(-it->second, it->first));
                }
            }
            std::sort(tops.begin(), tops.end());
            for (size_t t = 0; t < tops.size() && t < 5; t++) {
                if (t) out += ",";
                out += "[";
                json_str(&out, tops[t].second);
                out += ",";
                json_num(&out, -tops[t].first);
                out += "]";
            }
            out += "]}";
        }
    }
    out += "]}\n";
    FILE *f = fopen(argv[4], "wb");
    if (!f) return 1;
    fwrite(out.data(), 1, out.size(), f);
    fclose(f);
    return 0;
}
