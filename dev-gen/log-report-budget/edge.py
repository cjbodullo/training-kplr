#!/usr/bin/env python3
"""Hand written corner case fixtures for logstat.

Each directory holds access.log / routes.tsv / deploys.csv.  expected.json is
filled in afterwards by running the shipped engine.

Usage: edge.py <outdir>
"""
import os
import sys

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36"


def line(addr, t, method, target, status, nbytes, rt, urt, rid, att,
         ua=UA, ref="-"):
    return ('%s - - [%s] "%s %s HTTP/1.1" %s %s "%s" "%s" rt=%s uct=0.001 urt=%s rid=%s att=%d\n'
            % (addr, t, method, target, status, nbytes, ref, ua, rt, urt, rid, att))


def write(outdir, name, log_lines, routes, deploys):
    d = os.path.join(outdir, name)
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "access.log"), "w") as fh:
        fh.write("".join(log_lines))
    with open(os.path.join(d, "routes.tsv"), "w") as fh:
        fh.write("# method\tpattern\tservice\tslo_ms\n")
        fh.write("".join(r + "\n" for r in routes))
    with open(os.path.join(d, "deploys.csv"), "w") as fh:
        fh.write("service,release,start_epoch,end_epoch\n")
        fh.write("".join(r + "\n" for r in deploys))


def main(outdir):
    T = "17/Sep/2026:%02d:%02d:%02d +0000"
    TZ = "17/Sep/2026:%02d:%02d:%02d +0530"
    TW = "16/Sep/2026:%02d:%02d:%02d -0700"

    # --- routing: specificity, methods, tails, params with different names
    routes = [
        "GET\t/api/v1/orders/{id}\tcheckout\t200",
        "GET\t/api/v1/orders/{aid}\tcheckout\t900",
        "GET\t/api/v1/orders/*\tcheckout\t300",
        "GET\t/api/v1/orders/**\tcheckout\t400",
        "GET\t/api/v1/orders\tcheckout\t150",
        "*\t/api/v1/orders/{id}/items\tcheckout\t250",
        "POST\t/api/v1/orders/{id}/items\tcheckout\t800",
        "GET\t/api/v1/**\tcatalog\t1000",
        "GET\t/api/v1/orders/{id}\tcheckout\t9999",  # duplicate row, ignored
        "GET\t/assets/**\tmedia\t50",
        "HEAD\t/health\tcatalog\t10",
    ]
    log = [
        # exact literal beats everything
        line("10.0.0.1", T % (0, 0, 1), "GET", "/api/v1/orders", 200, 10, "0.100", "0.090", "aaaaaaaaaaaa", 1),
        # {id} beats {aid} on the tie break, and both beat * and **
        line("10.0.0.2", T % (0, 0, 2), "GET", "/api/v1/orders/77", 200, 20, "0.250", "0.200", "bbbbbbbbbbbb", 1),
        # star wins where the param does not apply? no: same length, param is more specific
        line("10.0.0.3", T % (0, 0, 3), "GET", "/api/v1/orders/77/items", 201, 30, "0.300", "-", "cccccccccccc", 1),
        # method literal beats "*"
        line("10.0.0.4", T % (0, 0, 4), "POST", "/api/v1/orders/77/items", 500, 0, "0.900", "0.400, 0.400", "dddddddddddd", 1),
        # ** with two extra segments
        line("10.0.0.5", T % (0, 0, 5), "GET", "/api/v1/orders/77/items/9/x", 200, 40, "0.410", "0.400", "eeeeeeeeeeee", 1),
        # /api/v1/** catches a path no orders pattern matches
        line("10.0.0.6", T % (0, 0, 6), "GET", "/api/v1/carts/9", 404, 0, "0.010", "-", "ffffffffffff", 1),
        # unmatched
        line("10.0.0.7", T % (0, 0, 7), "GET", "/nothing/here", 404, 0, "0.020", "-", "111111111111", 1),
        # absolute form target, percent encoding, encoded slash stays inside a segment
        line("10.0.0.8", T % (0, 0, 8), "GET", "https://shop.example.net/a%70i/v1/or%64ers/a%2Fb", 200, 55, "0.130", "0.120", "222222222222", 1),
        # query string and fragment are dropped
        line("10.0.0.9", T % (0, 0, 9), "GET", "/api/v1/orders/77?page=2#frag", 200, 60, "0.700", "0.650", "333333333333", 1),
        # a % that is not an escape stays literal
        line("10.0.0.10", T % (0, 0, 10), "GET", "/api/v1/orders/1%2", 200, 12, "0.030", "-", "444444444444", 1),
        # HEAD on /health, escaped quote in the user agent, bytes "-"
        line("10.0.0.11", T % (0, 0, 11), "HEAD", "/health", 200, "-", "0.005", "0.001", "555555555555", 1,
             ua='probe \\"one\\" two'),
        # ipv6 client, non utc node
        line("2a02:1:2:3::9", TZ % (5, 30, 12), "GET", "/assets/img/logo.png", 200, 900, "0.080", "0.070", "666666666666", 1),
        line("2a02:1:2:3::9", TW % (17, 0, 13), "GET", "/assets/img/logo.png", 304, 0, "0.004", "-", "777777777777", 1),
        # retries of one rid across two routes: attributed to the last attempt
        line("10.0.0.12", T % (0, 1, 0), "GET", "/api/v1/orders/5", 503, 0, "1.000", "1.000", "99aabbccddee", 1),
        line("10.0.0.12", T % (0, 1, 6), "GET", "/api/v1/orders/5/items", 200, 70, "2.000", "2.000", "99aabbccddee", 2),
        # rid "-" is its own logical request
        line("10.0.0.13", T % (0, 1, 7), "GET", "/api/v1/orders/6", 200, 15, "0.150", "0.100", "-", 1),
        # eight upstream entries
        line("10.0.0.14", T % (0, 1, 8), "GET", "/api/v1/orders/7", 200, 15, "0.888", "0.100, 0.100, 0.100, 0.100, 0.100, 0.100, 0.100, 0.188", "888888888888", 1),
        # damaged lines of every kind
        "\n",
        "garbage\n",
        '10.0.0.15 - - [17/Sep/2026:00:01:09 +0000] "GET /api/v1/orders/8 HTTP/1.1" 2x0 10 "-" "ua" rt=0.100 uct=0.001 urt=0.090 rid=aaaabbbbcccc att=1\n',
        '10.0.0.16 - - [32/Sep/2026:00:01:10 +0000] "GET /api/v1/orders/9 HTTP/1.1" 200 10 "-" "ua" rt=0.100 uct=0.001 urt=0.090 rid=aaaabbbbcccd att=1\n',
        '10.0.0.17 - - [17/Sep/2026:00:01:11 +0000] "-" 400 0 "-" "ua" rt=0.100 uct=0.001 urt=0.090 rid=aaaabbbbccce att=1\n',
        '10.0.0.18 - - [17/Sep/2026:00:01:12 +0000] "GET /api/v1/orders/10 HTTP/1.1" 200 10 "-" "ua" rt=0.1 uct=0.001 urt=0.090 rid=aaaabbbbcccf att=1\n',
        '10.0.0.19 - - [17/Sep/2026:00:01:13 +0000] "GET /api/v1/orders/11 HTTP/1.1" 200 10 "-" "ua" rt=900.000 uct=0.001 urt=0.090 rid=aaaabbbbccd0 att=1\n',
        # a request that ends exactly when another starts: not concurrent
        line("10.0.0.20", T % (0, 2, 0), "GET", "/api/v1/orders/12", 200, 10, "1.000", "-", "aaaabbbbccd1", 1),
        line("10.0.0.21", T % (0, 2, 1), "GET", "/api/v1/orders/13", 200, 10, "1.000", "-", "aaaabbbbccd2", 1),
        # long request that spans buckets, ends in a later bucket
        line("10.0.0.22", T % (0, 9, 59), "GET", "/api/v1/orders/14", 200, 10, "599.000", "-", "aaaabbbbccd3", 1),
    ]
    deploys = [
        "checkout,2.0.1,1789603200,1789603800",
        "checkout,2.0.2,1789603800,1789604400",
        "catalog,9.9.9,1789600000,1789603260",
        "media,1.0.0,1789560000,1789660000",
        "ghost,0.0.1,1789600000,1789660000",
    ]
    write(outdir, "corners", log, routes, deploys)

    # --- an empty log
    write(outdir, "empty", [], routes, deploys)

    # --- nothing but damaged lines
    write(outdir, "damaged", ["\n", "x\n", "10.0.0.1 - -\n"], routes, deploys)

    # --- a log that spans three days, sparse buckets, unsorted windows
    spread = []
    for day, tag in ((15, "15/Sep/2026"), (16, "16/Sep/2026"), (17, "17/Sep/2026")):
        for h in range(0, 24, 5):
            for k in range(4):
                off = ["+0000", "+0530", "-0700", "+0900"][k % 4]
                spread.append(line("10.%d.%d.%d" % (day, h, k),
                                   "%s:%02d:%02d:%02d %s" % (tag, h, k * 7, (k * 13) % 60, off),
                                   ["GET", "POST", "HEAD"][k % 3],
                                   ["/api/v1/orders/%d" % (k + day), "/api/v1/orders/%d/items" % k,
                                    "/health"][k % 3],
                                   [200, 404, 503][k % 3], 100 * k,
                                   "%d.%03d" % (k, (h * 7) % 1000),
                                   "-" if k % 2 else "%d.%03d" % (k, 1),
                                   "-" if k == 3 else "ab%02d%02d%02d%02d" % (day, h, k, k),
                                   1 + (k % 2)))
    write(outdir, "spread", spread, routes,
          ["checkout,7.1.0,1789430400,1789520400",
           "checkout,6.0.0,1789344000,1789430400",
           "catalog,3.3.3,1789603200,1789689600"])

    # --- one route table with no deploy windows at all
    write(outdir, "nowindows",
          [line("10.1.0.%d" % i, T % (1, 0, i), "GET", "/api/v1/orders/%d" % i, 200, i,
                "0.%03d" % i, "0.%03d" % i, "abcdef0000%02d" % i, 1) for i in range(1, 40)],
          routes, [])


if __name__ == "__main__":
    main(sys.argv[1])
