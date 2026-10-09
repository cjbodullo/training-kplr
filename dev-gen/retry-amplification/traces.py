"""A healthy-window trace corpus.

The call graph is not written down anywhere in the repo; it has to come out of here.
The corpus is honest about what a tracing backend really records, which is why a naive
edge count is wrong: every call produces both a CLIENT span on the caller and a SERVER
span on the callee, a small share of calls carry a genuine transient resend, peers are
recorded under the kubernetes Service name rather than the workload name, and a nightly
reindex job walks part of the estate without being on any public route.
"""

from __future__ import annotations

import random
from typing import Dict, List

from model import Service

ENTRY_WEIGHTS = [
    ("web-gateway", "/catalog/item", 0.26),
    ("web-gateway", "/search/query", 0.21),
    ("web-gateway", "/account/profile", 0.13),
    ("web-gateway", "/checkout/submit", 0.08),
    ("web-gateway", "/orders/place", 0.05),
    ("mobile-edge", "/m/recs", 0.12),
    ("mobile-edge", "/m/slots", 0.07),
    ("mobile-edge", "/m/pay", 0.05),
    ("mobile-edge", "/m/refund", 0.03),
]

BATCH_SHARE = 0.04
RESEND_SHARE = 0.025

GRPC_STACKS = {"grpc-go"}


class TraceGen:
    def __init__(self, services: Dict[str, Service], dns, svc_name, seed=20260920):
        self.s = services
        self.dns = dns
        self.svc_name = svc_name
        self.rnd = random.Random(seed)
        self._sid = 0

    def _id(self, n=8):
        self._sid += 1
        return f"{self._sid:0{n * 2}x}"

    def trace(self, base_ns: int) -> List[dict]:
        r = self.rnd.random()
        acc = 0.0
        for entry, route, wgt in ENTRY_WEIGHTS:
            acc += wgt
            if r <= acc / sum(w for *_, w in ENTRY_WEIGHTS):
                break
        tid = self._id(16)
        spans: List[dict] = []
        root = self._id()
        svc = self.s[entry]
        dur = self._walk_router(tid, root, entry, route, base_ns, spans)
        spans.append(self._span(
            tid, root, None, f"{self._method(entry, route)} {route}", "SERVER", entry,
            base_ns, base_ns + dur,
            {"http.request.method": self._method(entry, route), "url.path": route,
             "http.response.status_code": 200, "http.route": route},
        ))
        return spans

    def batch_trace(self, base_ns: int) -> List[dict]:
        """A nightly reindex job. It is not reachable from any public route."""
        tid = self._id(16)
        root = self._id()
        spans: List[dict] = []
        t = base_ns
        for target in ("catalog-index", "media-service", "rating-service"):
            cs, ce = t, t + 40_000_000
            child = self._id()
            spans.append(self._span(
                tid, child, root, f"GET {target}", "CLIENT", "catalog-reindex-job",
                cs, ce,
                {"http.request.method": "GET", "url.path": "/v1/reindex",
                 "peer.service": self.svc_name(target), "server.address": self.dns(target),
                 "http.response.status_code": 200},
            ))
            server = self._id()
            spans.append(self._span(
                tid, server, child, "GET /v1/reindex", "SERVER", target, cs + 500_000,
                ce - 500_000, {"http.response.status_code": 200}))
            t = ce
        spans.append(self._span(
            tid, root, None, "reindex catalogue", "INTERNAL", "catalog-reindex-job",
            base_ns, t, {"job.schedule": "nightly", "job.name": "catalog-reindex"}))
        return spans

    # ------------------------------------------------------------------ walk

    def _walk_router(self, tid, parent, name, route, start_ns, spans) -> int:
        svc = self.s[name]
        call = next(c for c in svc.calls if c.label == route)
        return self._emit_call(tid, parent, name, call, start_ns, spans)

    def _walk(self, tid, parent, name, start_ns, spans) -> int:
        svc = self.s[name]
        if not svc.calls:
            return self.rnd.randint(2, 9) * 1_000_000
        if svc.parallel:
            worst = 0
            for call in svc.calls:
                for _ in range(call.fanout):
                    worst = max(worst, self._emit_call(tid, parent, name, call, start_ns, spans))
            return worst + 1_000_000
        t = 0
        for call in svc.calls:
            for _ in range(call.fanout):
                t += self._emit_call(tid, parent, name, call, start_ns + t, spans)
        return t + 1_000_000

    def _emit_call(self, tid, parent, caller, call, start_ns, spans) -> int:
        target = call.target
        resends = 1 if self.rnd.random() < RESEND_SHARE else 0
        t = start_ns
        for attempt in range(resends + 1):
            child = self._id()
            server = self._id()
            inner = (self._walk(tid, server, target, t + 400_000, spans)
                     if attempt == resends else 3_000_000)
            dur = inner + 900_000
            grpc = self.s[caller].stack in GRPC_STACKS and self.s[target].stack in GRPC_STACKS
            attrs = {
                "peer.service": self.svc_name(target),
                "server.address": self.dns(target),
                "http.request.resend_count": attempt,
            }
            if grpc:
                body = call.path.strip("/")
                rpc_service, rpc_method = body.split("/", 1)
                attrs.update({
                    "rpc.system": "grpc", "rpc.service": rpc_service,
                    "rpc.method": rpc_method,
                    "rpc.grpc.status_code": 14 if attempt < resends else 0,
                })
                span_name = call.path
            else:
                attrs.update({
                    "http.request.method": call.method, "url.path": call.path,
                    "http.response.status_code": 503 if attempt < resends else 200,
                })
                span_name = f"{call.method} {call.path}"
            spans.append(self._span(tid, child, parent, span_name, "CLIENT", caller,
                                    t, t + dur, attrs))
            spans.append(self._span(
                tid, server, child, span_name, "SERVER", target,
                t + 400_000, t + dur - 400_000,
                {"http.response.status_code": 503 if attempt < resends else 200}
                if not grpc else
                {"rpc.system": "grpc", "rpc.grpc.status_code": 14 if attempt < resends else 0},
            ))
            t += dur
        return t - start_ns

    # ------------------------------------------------------------------ util

    def _method(self, entry, route):
        return next(c.method for c in self.s[entry].calls if c.label == route)

    def _span(self, tid, sid, parent, name, kind, service, start, end, attrs):
        span = {
            "traceId": tid,
            "spanId": sid,
            "name": name,
            "kind": kind,
            "startTimeUnixNano": int(start),
            "endTimeUnixNano": int(end),
            "resource": {
                "service.name": service,
                "k8s.namespace.name": self.s[service].namespace
                if service in self.s else "batch",
            },
            "attributes": attrs,
        }
        if parent:
            span["parentSpanId"] = parent
        return span
