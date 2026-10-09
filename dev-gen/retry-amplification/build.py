"""Generate the shipped workspace and the sealed answer."""

from __future__ import annotations

import gzip
import json
import os
import shutil
import sys

from model import Engine
from topology import SERVICE_DNS, build
import render
from traces import TraceGen

HERE = os.path.dirname(os.path.abspath(__file__))
BUNDLE = os.path.abspath(os.path.join(HERE, "..", "..", "task-src", "retry-amplification"))
APP = os.path.join(BUNDLE, "environment", "app")
TESTS = os.path.join(BUNDLE, "tests")

TRACE_FILES = 6
TRACES_PER_FILE = 1100


def main():
    services, scenarios = build()
    if os.path.isdir(APP):
        shutil.rmtree(APP)
    os.makedirs(APP, exist_ok=True)

    render.render_k8s(APP)
    render.render_mesh(APP)
    render.render_nginx(APP)
    render.render_haproxy(APP)
    render.render_envoy(APP)
    render.render_clients(APP)
    write_static(APP)
    write_scenarios(APP, scenarios)
    write_traces(APP, services)

    eng = Engine(services)
    truth = {sc.key: eng.evaluate(sc) for sc in scenarios}
    os.makedirs(TESTS, exist_ok=True)
    with open(os.path.join(TESTS, "truth.json"), "w") as fh:
        json.dump({"scenarios": truth}, fh, indent=1, sort_keys=True)

    n_files = sum(len(f) for _, _, f in os.walk(APP))
    size = sum(
        os.path.getsize(os.path.join(d, f))
        for d, _, fs in os.walk(APP) for f in fs
    )
    print(f"workspace: {n_files} files, {size / 1e6:.1f} MB")
    print(f"answer: {len(truth)} scenarios, "
          f"{sum(len(v['requests']) for v in truth.values())} service counts, "
          f"{sum(sum(v['requests'].values()) for v in truth.values())} requests")


# ------------------------------------------------------------------ scenarios


def write_scenarios(app, scenarios):
    doc = {"scenarios": []}
    for sc in scenarios:
        doc["scenarios"].append({
            "id": sc.key,
            "entry_proxy": sc.entry,
            "route": sc.route,
            "impaired_service": sc.failing,
            "impairment": "no_response" if sc.mode == "hang" else f"status_{sc.status}",
            "client_deadline_ms": sc.client_deadline_ms,
        })
    with open(os.path.join(app, "scenarios.json"), "w") as fh:
        json.dump(doc, fh, indent=2)
        fh.write("\n")


# --------------------------------------------------------------------- traces


def write_traces(app, services):
    gen = TraceGen(
        services,
        dns=lambda n: f"{SERVICE_DNS.get(n, n)}.{services[n].namespace}.svc.cluster.local",
        svc_name=lambda n: SERVICE_DNS.get(n, n),
    )
    base = 1789_000_000_000_000_000
    os.makedirs(os.path.join(app, "traces"), exist_ok=True)
    total = 0
    for idx in range(TRACE_FILES):
        path = os.path.join(app, "traces", f"spans-{idx + 1:02d}.ndjson.gz")
        with gzip.open(path, "wt", encoding="utf-8", compresslevel=9) as fh:
            for i in range(TRACES_PER_FILE):
                base += 37_000_000
                spans = (gen.batch_trace(base) if gen.rnd.random() < 0.04
                         else gen.trace(base))
                for span in spans:
                    fh.write(json.dumps(span, separators=(",", ":")) + "\n")
                total += len(spans)
    print(f"traces: {TRACE_FILES * TRACES_PER_FILE} traces, {total} spans")


# --------------------------------------------------------------------- static


def write_static(app):
    render.w(app, "platform/retryhttp/retry.go", RETRYHTTP_GO)
    render.w(app, "README.md", README)
    render.w(app, "docs/PLATFORM.md", PLATFORM)


RETRYHTTP_GO = '''package retryhttp

// Shared outbound helper for the Go services. Every Go service that talks plain
// HTTP goes through Do; the numbers come from that service's http_upstreams.json.

import (
	"context"
	"net/http"
	"time"
)

type Options struct {
	MaxRetries     int      // further requests after the first one, so 0 means one request
	Backoff        []int    // Backoff[i] is the pause in ms before retry i+1
	RetryStatus    []int    // response codes that earn another request
	RetryOnTimeout bool     // treat "per request deadline passed" as retryable
	PerRequest     time.Duration
	Overall        time.Duration
}

func Do(req *http.Request, o Options) (*http.Response, error) {
	deadline := time.Now().Add(o.Overall)
	var last *http.Response
	for attempt := 0; attempt <= o.MaxRetries; attempt++ {
		if attempt > 0 {
			pause := time.Duration(o.Backoff[min(attempt-1, len(o.Backoff)-1)]) * time.Millisecond
			if time.Now().Add(pause).After(deadline) {
				return nil, ErrOverallDeadline
			}
			time.Sleep(pause)
		}
		ctx, cancel := context.WithTimeout(req.Context(), o.PerRequest)
		resp, err := http.DefaultClient.Do(req.WithContext(ctx))
		cancel()
		if err != nil {
			if !o.RetryOnTimeout {
				return nil, err
			}
			last = nil
			continue
		}
		if !contains(o.RetryStatus, resp.StatusCode) {
			return resp, nil
		}
		last = resp
		if !time.Now().Before(deadline) {
			break
		}
	}
	return last, nil
}
'''

README = """# grocer-platform

Configuration for the storefront estate. One directory per concern.

    platform/kubernetes   namespaces, Deployments and Services, one file per workload
    platform/mesh         Istio VirtualServices and DestinationRules, one file per host
    platform/edge         the two public proxies
    platform/retryhttp    the shared Go outbound helper
    services/<name>       whatever that service uses to configure its own upstream calls
    traces                a gzipped ndjson export from the tracing backend
    docs/PLATFORM.md      how we reason about a dependency going bad
    scenarios.json        the dependency failures the reliability review is asking about

Services are written in five stacks and each configures its upstream calls in whatever
its stack provides, so the file you want under `services/<name>` depends on the service.
The tracing export covers a normal Tuesday afternoon, one hour, unsampled.

There is no service dependency register. We have tried three times to keep one accurate
and it was wrong within a fortnight; the traces are the register now.
"""

PLATFORM = """# Reasoning about a bad dependency

When one service starts failing, the question the reliability review asks is never "is it
down". It is how many requests the rest of the estate will pile onto it and onto everything
beside it, and whether the customer gets an answer at all. Retries compose: a client library
retry sits inside a sidecar retry sits inside an edge proxy retry, and the request count at
the bottom is the product, not the sum.

We model one single request from one customer, arriving at a cold estate. The conventions
below are what the review uses so that two people analysing the same failure get the same
number.

## The request

One request arrives at the entry proxy named in the scenario, on the route named in the
scenario. Nothing else is in flight. Every retry budget, token bucket, circuit breaker and
outlier detector starts empty and idle, and one request is never enough to move any of them,
so they do not change the outcome.

## The impairment

`status_503` and `status_502` mean the impaired service answers every request it receives
with that status, immediately. `no_response` means it accepts the request and never answers:
it is the caller's own timeout that ends the attempt.

Every other service is healthy and answers correctly. We treat healthy processing time as
zero, so the only things that take time are attempts that are waiting on the impaired
service and the pauses a client takes between attempts.

## Timing

A retry pause is the largest value the policy allows for that attempt; where a policy
jitters, take the top of the range. An attempt that is waiting on the impaired service ends
when the shortest per-attempt timeout covering it expires. An overall or total timeout is a
budget for everything inside it, pauses included: when it expires the layer stops, whether
or not it has attempts left, and reports a gateway timeout upwards.

A layer that passes its remaining budget downstream binds the service it calls. A layer
that does not pass anything down leaves that service running on its own timeouts, which
is how work continues after the customer has already been answered. Those requests still
happened and they still count. A service working inside a budget spends what its earlier
calls have already taken, so each call it makes starts with whatever is left.

## What a service does when a call fails

A service that issues its calls one after another stops at the first one that fails: the
calls it had not made yet never happen, and it has taken as long as its calls so far added
together. A service that issues its calls together makes all of them whatever happens, it
has taken as long as the slowest of them, and it reports the first failure among them.

A service that gives up hands back the answer that stopped it, so a status raised deep in
the estate is what the customer sees unless something above it ran out of time first, and
a layer that runs out of time reports a gateway timeout in its place.

## What we report

For each scenario: every service that receives at least one request and exactly how many it
receives, how long the customer waits, and what the customer ends up with.
"""


if __name__ == "__main__":
    main()
