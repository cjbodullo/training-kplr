#!/usr/bin/env python3
"""Workload generator for the logstat task.

Emits an nginx access log (slo log_format), a route table and a deploy window
file.  Profiles differ in the shape knobs that the data contract allows, so a
reader tuned to one profile is not fast on another.

Usage: gen.py <outdir> <profile> <seed>
"""
import gzip
import os
import random
import sys
import time

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

SERVICES = ["catalog", "checkout", "identity", "media", "payments", "search"]

UAS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 18_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.2 Mobile/15E148 Safari/604.1",
    "curl/8.5.0",
    "python-requests/2.32.3",
    "Go-http-client/2.0",
    "okhttp/4.12.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36",
    "checkout-worker/3.4.1 (+https://ops.example.net/agents)",
    "Mozilla/5.0 (compatible; bingbot/2.0; +http://www.bing.com/bingbot.htm)",
]

REFERERS = ["-", "https://shop.example.net/", "https://shop.example.net/cart",
            "https://m.example.net/app", "https://partner.example.org/deals"]

METHODS = ["GET", "GET", "GET", "GET", "POST", "POST", "PUT", "DELETE", "PATCH", "HEAD"]

WORDS = ["orders", "items", "carts", "checkout", "sessions", "assets", "thumbs",
         "variants", "bundles", "prices", "stock", "regions", "locales", "tenants",
         "invoices", "refunds", "captures", "tokens", "profiles", "consents",
         "search", "suggest", "facets", "rankings", "uploads", "renditions",
         "playlists", "segments", "subscriptions", "entitlements", "ledgers",
         "disputes", "payouts", "webhooks", "events", "batches", "reports",
         "audits", "keys", "grants", "devices", "policies", "shipments"]


class Profile:
    def __init__(self, **kw):
        self.lines = kw.get("lines", 250_000)
        self.patterns = kw.get("patterns", 900)
        self.clients = kw.get("clients", 40_000)
        self.max_depth = kw.get("max_depth", 4)
        self.tz_mix = kw.get("tz_mix", ["+0000"])
        self.ipv6_frac = kw.get("ipv6_frac", 0.0)
        self.retry_frac = kw.get("retry_frac", 0.02)
        self.max_attempts = kw.get("max_attempts", 3)
        self.tail_ms = kw.get("tail_ms", 4_000)
        self.tail_frac = kw.get("tail_frac", 0.002)
        self.unmatched_frac = kw.get("unmatched_frac", 0.01)
        self.malformed_frac = kw.get("malformed_frac", 0.003)
        self.skew = kw.get("skew", 1.1)
        self.reorder_s = kw.get("reorder_s", 30)
        self.no_rid_frac = kw.get("no_rid_frac", 0.02)
        self.param_frac = kw.get("param_frac", 0.35)
        self.star_frac = kw.get("star_frac", 0.05)
        self.tail_route_frac = kw.get("tail_route_frac", 0.03)
        self.query_frac = kw.get("query_frac", 0.25)
        self.pct_frac = kw.get("pct_frac", 0.05)
        self.day = kw.get("day", (2026, 9, 17))


PROFILES = {
    # shipped sample: one quiet tenant, one node, everything mild
    "sample": Profile(lines=150_000, patterns=900, clients=40_000, max_depth=4,
                      tz_mix=["+0000"], ipv6_frac=0.0, retry_frac=0.02,
                      max_attempts=2, tail_ms=4_000, tail_frac=0.002,
                      skew=1.15, reorder_s=20, param_frac=0.30, star_frac=0.03,
                      tail_route_frac=0.02, pct_frac=0.03),
    # sealed A: near-unique clients, ipv6, mixed node timezones
    "wide": Profile(lines=250_000, patterns=1_300, clients=360_000, max_depth=5,
                    tz_mix=["+0000", "+0530", "-0700", "+0200", "+0900"],
                    ipv6_frac=0.22, retry_frac=0.04, max_attempts=3,
                    tail_ms=9_000, tail_frac=0.004, skew=0.6, reorder_s=90,
                    param_frac=0.40, star_frac=0.05, tail_route_frac=0.03,
                    pct_frac=0.08),
    # sealed B: big route table, deep paths, heavy param overlap
    "deep": Profile(lines=250_000, patterns=4_000, clients=70_000, max_depth=8,
                    tz_mix=["+0000", "-0500", "+0100"], ipv6_frac=0.05,
                    retry_frac=0.03, max_attempts=3, tail_ms=6_000,
                    tail_frac=0.003, skew=0.9, reorder_s=60, param_frac=0.55,
                    star_frac=0.12, tail_route_frac=0.08, pct_frac=0.12,
                    unmatched_frac=0.02),
    # sealed C: long latency tail, heavy retries, wide reordering
    "tail": Profile(lines=250_000, patterns=1_500, clients=140_000, max_depth=6,
                    tz_mix=["+0000", "+0530", "-0300"], ipv6_frac=0.10,
                    retry_frac=0.26, max_attempts=8, tail_ms=880_000,
                    tail_frac=0.02, skew=1.4, reorder_s=300, param_frac=0.45,
                    star_frac=0.06, tail_route_frac=0.04, pct_frac=0.06,
                    no_rid_frac=0.05),
    # small fixtures for the shipped unit tests
    "tiny": Profile(lines=4_000, patterns=120, clients=900, max_depth=5,
                    tz_mix=["+0000", "+0530", "-0700"], ipv6_frac=0.15,
                    retry_frac=0.15, max_attempts=4, tail_ms=120_000,
                    tail_frac=0.01, skew=1.0, reorder_s=120, param_frac=0.45,
                    star_frac=0.10, tail_route_frac=0.06, pct_frac=0.10),
}


def days_from_civil(y, m, d):
    y -= m <= 2
    era = (y if y >= 0 else y - 399) // 400
    yoe = y - era * 400
    doy = (153 * (m + (-3 if m > 2 else 9)) + 2) // 5 + d - 1
    doe = yoe * 365 + yoe // 4 - yoe // 100 + doy
    return era * 146097 + doe - 719468


def civil_from_days(z):
    z += 719468
    era = (z if z >= 0 else z - 146096) // 146097
    doe = z - era * 146097
    yoe = (doe - doe // 1460 + doe // 36524 - doe // 146096) // 365
    y = yoe + era * 400
    doy = doe - (365 * yoe + yoe // 4 - yoe // 100)
    mp = (5 * doy + 2) // 153
    d = doy - (153 * mp + 2) // 5 + 1
    m = mp + (3 if mp < 10 else -9)
    return (y + (m <= 2), m, d)


def fmt_time_local(epoch, off):
    sign = 1 if off[0] == "+" else -1
    offs = sign * (int(off[1:3]) * 3600 + int(off[3:5]) * 60)
    t = epoch + offs
    days, rem = divmod(t, 86400)
    y, m, d = civil_from_days(days)
    hh, rem = divmod(rem, 3600)
    mm, ss = divmod(rem, 60)
    return "%02d/%s/%04d:%02d:%02d:%02d %s" % (d, MONTHS[m - 1], y, hh, mm, ss, off)


def make_clients(rng, n, ipv6_frac):
    out = []
    seen = set()
    while len(out) < n:
        if rng.random() < ipv6_frac:
            groups = [format(rng.getrandbits(16), "x") for _ in range(4)]
            a = "2a02:%s:%s:%s::%s" % (groups[0], groups[1], groups[2], groups[3])
        else:
            a = "%d.%d.%d.%d" % (rng.choice([10, 172, 192, 34, 51, 82, 203]),
                                 rng.randrange(256), rng.randrange(256),
                                 rng.randrange(1, 255))
        if a in seen:
            continue
        seen.add(a)
        out.append(a)
    return out


class Pattern:
    __slots__ = ("service", "method", "segs", "kinds", "slo", "weight",
                 "err4", "err5", "base_ms", "spread", "bytes_mu")

    def key(self):
        return "/" + "/".join(self.segs)


def make_routes(rng, prof):
    pats = []
    seen = set()
    per_service = max(1, prof.patterns // len(SERVICES))
    for svc in SERVICES:
        roots = [svc] + rng.sample(WORDS, 4)
        n = per_service + rng.randrange(-5, 6)
        made = 0
        guard = 0
        while made < n and guard < n * 40:
            guard += 1
            depth = rng.randint(2, prof.max_depth)
            segs, kinds = [], []
            segs.append("api")
            kinds.append("lit")
            segs.append(rng.choice(["v1", "v2", "v3"]))
            kinds.append("lit")
            segs.append(rng.choice(roots))
            kinds.append("lit")
            for i in range(depth - 1):
                r = rng.random()
                if r < prof.param_frac:
                    segs.append("{%s}" % rng.choice(["id", "sku", "ref", "slug", "key", "uid"]))
                    kinds.append("par")
                elif r < prof.param_frac + prof.star_frac:
                    segs.append("*")
                    kinds.append("star")
                else:
                    segs.append(rng.choice(WORDS))
                    kinds.append("lit")
            if rng.random() < prof.tail_route_frac:
                segs.append("**")
                kinds.append("tail")
            k = (rng.choice(METHODS) if rng.random() > 0.15 else "*", tuple(segs))
            if k in seen:
                continue
            seen.add(k)
            p = Pattern()
            p.service = svc
            p.method = k[0]
            p.segs = list(segs)
            p.kinds = kinds
            p.slo = rng.choice([150, 250, 400, 600, 800, 1200, 2000, 3000])
            p.weight = rng.paretovariate(prof.skew)
            p.err4 = rng.choice([0.0, 0.005, 0.02, 0.05, 0.12])
            p.err5 = rng.choice([0.0, 0.0, 0.001, 0.004, 0.02, 0.06])
            p.base_ms = rng.choice([4, 9, 18, 35, 70, 140, 280, 560, 900])
            p.spread = rng.uniform(0.35, 1.5)
            p.bytes_mu = rng.choice([180, 900, 4200, 19000, 85000])
            pats.append(p)
            made += 1
    return pats


HEX = "0123456789abcdef"


def rand_seg(rng, kind):
    if kind == "par":
        style = rng.random()
        if style < 0.4:
            return "".join(rng.choice(HEX) for _ in range(rng.choice([8, 12, 24, 32])))
        if style < 0.7:
            return str(rng.randrange(1, 9_000_000))
        if style < 0.85:
            return "%s-%s-%d" % (rng.choice(WORDS), rng.choice(WORDS), rng.randrange(999))
        return "%s%%2F%s" % (rng.choice(WORDS), rng.choice(WORDS))
    return rng.choice(WORDS)


def pct_encode(rng, s):
    out = []
    for ch in s:
        if ch.isalnum() and rng.random() < 0.12:
            out.append("%%%02X" % ord(ch) if rng.random() < 0.5 else "%%%02x" % ord(ch))
        else:
            out.append(ch)
    return "".join(out)


def gen(outdir, profile, seed):
    prof = PROFILES[profile]
    rng = random.Random(seed)
    os.makedirs(outdir, exist_ok=True)

    pats = make_routes(rng, prof)
    with open(os.path.join(outdir, "routes.tsv"), "w") as fh:
        fh.write("# method\tpattern\tservice\tslo_ms\n")
        for p in pats:
            fh.write("%s\t%s\t%s\t%d\n" % (p.method, p.key(), p.service, p.slo))

    day0 = days_from_civil(*prof.day) * 86400
    with open(os.path.join(outdir, "deploys.csv"), "w") as fh:
        fh.write("service,release,start_epoch,end_epoch\n")
        for svc in SERVICES:
            t = day0 + rng.randrange(0, 3600)
            n = rng.randint(3, 7)
            for i in range(n):
                dur = rng.randrange(2 * 3600, 6 * 3600)
                rel = "%d.%d.%d" % (rng.randrange(1, 9), rng.randrange(0, 30), rng.randrange(0, 40))
                fh.write("%s,%s,%d,%d\n" % (svc, rel, t, t + dur))
                t += dur + rng.randrange(0, 1800)

    clients = make_clients(rng, prof.clients, prof.ipv6_frac)
    weights = [p.weight for p in pats]
    total_w = sum(weights)
    cum, acc = [], 0.0
    for w in weights:
        acc += w
        cum.append(acc / total_w)

    def pick_pattern():
        r = rng.random()
        lo, hi = 0, len(cum) - 1
        while lo < hi:
            mid = (lo + hi) // 2
            if cum[mid] < r:
                lo = mid + 1
            else:
                hi = mid
        return pats[lo]

    n_clients = len(clients)
    zipf_n = min(n_clients, 5000)
    records = []
    emitted = 0
    target = prof.lines
    while emitted < target:
        p = pick_pattern()
        segs = []
        for seg, kind in zip(p.segs, p.kinds):
            if kind == "lit":
                segs.append(seg)
            elif kind == "par":
                segs.append(rand_seg(rng, "par"))
            elif kind == "star":
                segs.append(rand_seg(rng, "lit" if rng.random() < 0.5 else "par"))
            else:
                for _ in range(rng.randint(0, 3)):
                    segs.append(rand_seg(rng, "lit" if rng.random() < 0.6 else "par"))
        if rng.random() < prof.unmatched_frac:
            segs = segs + [rand_seg(rng, "lit"), rand_seg(rng, "par")]
        # the contract caps a target at 12 path segments
        segs = segs[:12]
        path = "/" + "/".join(segs)
        if rng.random() < prof.pct_frac:
            path = pct_encode(rng, path)
        if rng.random() < prof.query_frac:
            path += "?%s=%s&%s=%d" % (rng.choice(["page", "q", "cursor", "limit"]),
                                      rand_seg(rng, "lit"), rng.choice(["sort", "ttl"]),
                                      rng.randrange(1, 400))
        method = p.method if p.method != "*" else rng.choice(METHODS)

        # client: a hot core plus a long unique tail
        if rng.random() < 0.35:
            cl = clients[rng.randrange(zipf_n)]
        else:
            cl = clients[rng.randrange(n_clients)]

        r = rng.random()
        if r < p.err5:
            status = rng.choice([500, 502, 503, 504])
        elif r < p.err5 + p.err4:
            status = rng.choice([400, 401, 403, 404, 409, 422, 429])
        else:
            status = rng.choice([200, 200, 200, 201, 204, 206, 301, 302, 304])

        if rng.random() < prof.tail_frac:
            ms = rng.randrange(p.base_ms * 4 + 1, prof.tail_ms)
        else:
            ms = max(0, int(rng.lognormvariate(0, p.spread) * p.base_ms))
        ms = min(ms, 899_999)

        nbytes = 0 if status in (204, 304) else max(0, int(rng.lognormvariate(0, 0.8) * p.bytes_mu))
        end = day0 + rng.randrange(0, 86400)
        rid = "-" if rng.random() < prof.no_rid_frac else "".join(rng.choice(HEX) for _ in range(12))
        ua = rng.choice(UAS)
        if rng.random() < 0.02:
            ua = ua + ' \\"probe\\"'
        ref = rng.choice(REFERERS)
        off = rng.choice(prof.tz_mix)

        if rid != "-" and rng.random() < prof.retry_frac:
            n_att = rng.randint(2, prof.max_attempts)
        else:
            n_att = 1
        t = end
        for att in range(1, n_att + 1):
            if att < n_att:
                a_ms = max(1, int(ms * rng.uniform(0.2, 1.1)))
                a_status = rng.choice([502, 503, 504, 500])
            else:
                a_ms = ms
                a_status = status
            urt_parts = []
            rest = a_ms
            for _ in range(rng.randint(1, min(3, prof.max_attempts))):
                take = max(0, int(rest * rng.uniform(0.2, 0.9)))
                urt_parts.append(take)
                rest -= take
                if rest <= 0:
                    break
            urt = ", ".join("%d.%03d" % divmod(v, 1000) for v in urt_parts) if urt_parts and rng.random() > 0.03 else "-"
            uct = "%d.%03d" % (0, rng.randrange(0, 40))
            records.append((t + rng.randrange(0, 4), cl, off, method, path, a_status,
                            nbytes if att == n_att else 0, ref, ua, a_ms, uct, urt, rid, att))
            emitted += 1
            t += max(1, a_ms // 1000 + rng.randrange(0, 3))

    records = records[:prof.lines]
    # bounded reordering: the log is a merge of several nodes
    records.sort(key=lambda r: r[0])
    jitter = prof.reorder_s
    if jitter:
        keyed = [(r[0] + rng.randrange(-jitter, jitter + 1), i) for i, r in enumerate(records)]
        keyed.sort()
        records = [records[i] for _, i in keyed]

    path_out = os.path.join(outdir, "access.log")
    n_mal = 0
    with open(path_out, "w") as fh:
        buf = []
        for rec in records:
            (t, cl, off, method, path, status, nbytes, ref, ua, ms, uct, urt, rid, att) = rec
            line = ('%s - - [%s] "%s %s HTTP/1.1" %d %d "%s" "%s" rt=%d.%03d uct=%s urt=%s rid=%s att=%d\n'
                    % (cl, fmt_time_local(t, off), method, path, status, nbytes, ref, ua,
                       ms // 1000, ms % 1000, uct, urt, rid, att))
            if rng.random() < prof.malformed_frac:
                n_mal += 1
                kind = rng.randrange(5)
                if kind == 0:
                    line = line[:rng.randrange(20, max(21, len(line) // 2))] + "\n"
                elif kind == 1:
                    line = line.replace(' %d ' % status, ' -- ', 1)
                elif kind == 2:
                    line = line.replace('"%s %s HTTP/1.1"' % (method, path), '"-"', 1)
                elif kind == 3:
                    line = line.replace('rt=', 'rt=x', 1)
                else:
                    line = "\n"
            buf.append(line)
            if len(buf) >= 20000:
                fh.write("".join(buf))
                buf = []
        fh.write("".join(buf))
    size = os.path.getsize(path_out)
    print("%s: %d lines (%d damaged), %.1f MB, %d patterns, %d clients"
          % (profile, len(records), n_mal, size / 1e6, len(pats), len(clients)))


if __name__ == "__main__":
    t0 = time.time()
    gen(sys.argv[1], sys.argv[2], int(sys.argv[3]))
    print("  %.1fs" % (time.time() - t0))
