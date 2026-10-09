"""The estate: services, namespaces, call graph and the native retry policies.

Everything here is expressed the way the platform actually writes it (native dialect
numbers), and `normalise()` turns a native policy into the Layer the engine understands.
That split is the point of the task: the agent has to do the same normalisation from the
rendered files, and the dialects disagree with each other about what a number means.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from model import Layer, Call, Service

# ---------------------------------------------------------------- native policies

# statuses the engine speaks. Dialect-native condition names map onto these.
ALL_5XX = frozenset({"500", "502", "503", "504"})


@dataclass
class Policy:
    """A retry/timeout policy as its own tool spells it."""

    dialect: str
    native: dict
    site: str = "app"


def _grpc_backoff(native) -> List[int]:
    init = int(round(float(native["initialBackoff"].rstrip("s")) * 1000))
    cap = int(round(float(native["maxBackoff"].rstrip("s")) * 1000))
    mult = float(native.get("backoffMultiplier", 2))
    out, cur = [], init
    for _ in range(8):
        out.append(min(int(cur), cap))
        cur = cur * mult
    return out


GRPC_STATUS = {
    "UNAVAILABLE": "503",
    "DEADLINE_EXCEEDED": "504",
    "INTERNAL": "500",
    "RESOURCE_EXHAUSTED": "429",
    "ABORTED": "409",
}

ENVOY_RETRY_ON = {
    "5xx": {"500", "502", "503", "504"},
    "gateway-error": {"502", "503", "504"},
    "connect-failure": set(),
    "reset": set(),
    "retriable-status-codes": set(),
    "retriable-4xx": {"409"},
    "unavailable": {"503"},
}


def normalise(p: Policy) -> Layer:
    """Native policy -> engine Layer. This is the expertise the task is about."""
    n = p.native
    d = p.dialect

    if d in ("envoy", "istio"):
        # num_retries / attempts are ADDITIONAL attempts on top of the first one.
        attempts = int(n["num_retries"]) + 1
        on = set()
        for token in n.get("retry_on", "").split(","):
            token = token.strip()
            if not token:
                continue
            on |= ENVOY_RETRY_ON.get(token, set())
        for code in n.get("retriable_status_codes", []):
            on.add(str(code))
        base = int(n.get("base_interval_ms", 25))
        cap = int(n.get("max_interval_ms", base * 10))
        backoff, cur = [], base
        for _ in range(8):
            backoff.append(min(cur, cap))
            cur *= 2
        return Layer(
            site=p.site,
            dialect=d,
            attempts=attempts,
            per_try_ms=n.get("per_try_timeout_ms"),
            overall_ms=n.get("timeout_ms"),
            backoff_ms=backoff,
            retry_on=frozenset(on),
            propagates=True,  # envoy forwards x-envoy-expected-rq-timeout-ms
        )

    if d == "grpc":
        if "hedging" in n:
            h = n["hedging"]
            return Layer(
                site=p.site,
                dialect=d,
                attempts=int(h["maxAttempts"]),  # TOTAL, hedged
                per_try_ms=None,
                overall_ms=n.get("deadline_ms"),
                backoff_ms=[],
                retry_on=frozenset(
                    GRPC_STATUS[c] for c in h.get("nonFatalStatusCodes", [])
                ),
                propagates=True,  # grpc-timeout header
                hedge_delay_ms=int(round(float(h["hedgingDelay"].rstrip("s")) * 1000)),
            )
        r = n["retryPolicy"]
        return Layer(
            site=p.site,
            dialect=d,
            attempts=int(r["maxAttempts"]),  # TOTAL, includes the original
            per_try_ms=None,  # grpc has no per-attempt timeout, only the deadline
            overall_ms=n.get("deadline_ms"),
            backoff_ms=_grpc_backoff(r),
            retry_on=frozenset(GRPC_STATUS[c] for c in r["retryableStatusCodes"]),
            propagates=True,
        )

    if d == "gohttp":
        # the in-house Go helper counts RETRIES after the first request
        return Layer(
            site=p.site,
            dialect=d,
            attempts=int(n["maxRetries"]) + 1,
            per_try_ms=n.get("requestTimeoutMs"),
            overall_ms=n.get("overallTimeoutMs"),
            backoff_ms=[int(x) for x in n.get("backoffMs", [0])],
            retry_on=frozenset(str(c) for c in n.get("retryStatusCodes", []))
            | ({"504"} if n.get("retryOnTimeout", False) else set()),
            propagates=False,
        )

    if d == "urllib3":
        total = int(n["total"])  # RETRIES, not attempts
        f = float(n.get("backoff_factor", 0))
        # urllib3 >= 2.0 sleeps before the first retry too; 1.26 does not.
        two_x = n.get("urllib3_major", 2) >= 2
        backoff = []
        for k in range(1, 9):
            v = f * (2 ** (k - 1))
            if k == 1 and not two_x:
                v = 0.0
            backoff.append(int(round(min(v, float(n.get("backoff_max", 120))) * 1000)))
        return Layer(
            site=p.site,
            dialect=d,
            attempts=total + 1,
            per_try_ms=n.get("read_timeout_ms"),
            overall_ms=None,  # requests/urllib3 has no overall budget
            backoff_ms=backoff,
            retry_on=frozenset(str(c) for c in n.get("status_forcelist", []))
            | ({"504"} if n.get("retry_read", True) else set()),
            propagates=False,  # plain HTTP client, no deadline header
        )

    if d == "tenacity":
        return Layer(
            site=p.site,
            dialect=d,
            attempts=int(n["stop_after_attempt"]),  # TOTAL
            per_try_ms=n.get("read_timeout_ms"),
            overall_ms=n.get("stop_after_delay_ms"),
            backoff_ms=[int(n.get("wait_fixed_ms", 0))] * 8,
            retry_on=frozenset(str(c) for c in n.get("retry_on_status", []))
            | ({"504"} if n.get("retry_timeout", False) else set()),
            propagates=False,
        )

    if d == "resilience4j":
        return Layer(
            site=p.site,
            dialect=d,
            attempts=int(n["maxAttempts"]),  # TOTAL
            per_try_ms=n.get("read_timeout_ms"),
            overall_ms=n.get("time_limiter_ms"),
            backoff_ms=[int(n.get("waitDuration_ms", 0))] * 8,
            retry_on=frozenset(str(c) for c in n.get("retryStatuses", []))
            | ({"504"} if n.get("retry_timeout", False) else set()),
            propagates=False,
        )

    if d == "polly":
        return Layer(
            site=p.site,
            dialect=d,
            attempts=int(n["retryCount"]) + 1,  # WaitAndRetryAsync(n) == n retries
            per_try_ms=n.get("http_client_timeout_ms"),
            overall_ms=n.get("overall_timeout_ms"),
            backoff_ms=[int(x) for x in n.get("sleep_ms", [0])],
            retry_on=frozenset(str(c) for c in n.get("handleStatuses", []))
            | ({"504"} if n.get("retry_timeout", False) else set()),
            propagates=False,
        )

    if d == "nginx":
        tries = int(n["proxy_next_upstream_tries"])  # TOTAL tries, 0 means unlimited
        on = set()
        tokens = n["proxy_next_upstream"].split()
        for token in tokens:
            if token == "timeout":
                on.add("504")  # upstream did not answer inside proxy_read_timeout
            elif token == "error":
                continue  # transport level, no HTTP status involved
            elif token.startswith("http_"):
                on.add(token[5:])
        idempotent_only = "non_idempotent" not in tokens
        return Layer(
            site=p.site,
            dialect=d,
            attempts=tries if tries else 8,
            per_try_ms=n.get("proxy_read_timeout_ms"),
            overall_ms=n.get("proxy_next_upstream_timeout_ms"),
            backoff_ms=[0] * 8,  # nginx does not back off between upstream tries
            retry_on=frozenset(on),
            propagates=False,
        ), idempotent_only  # type: ignore[return-value]

    if d == "haproxy":
        # `retries` counts RETRIES after the first attempt, and without an L7
        # `retry-on` condition it only covers connection failures.
        on = set()
        for token in n.get("retry_on", "").split():
            if token.isdigit():
                on.add(token)
            elif token == "response-timeout":
                on.add("504")
            elif token == "all-retryable-errors":
                # conn-failure, empty-response, junk-response, response-timeout,
                # 0rtt-rejected. It does NOT cover a 503 the server actually sent.
                on.add("504")
        return Layer(
            site=p.site,
            dialect=d,
            attempts=int(n["retries"]) + 1,
            per_try_ms=n.get("timeout_server_ms"),
            overall_ms=None,
            backoff_ms=[0] * 8,
            retry_on=frozenset(on),
            propagates=False,
        )

    raise ValueError(d)


def to_layer(p: Policy, method: str) -> Optional[Layer]:
    out = normalise(p)
    if isinstance(out, tuple):  # nginx carries its idempotence gate alongside
        layer, idempotent_only = out
        if idempotent_only and method not in ("GET", "HEAD", "PUT", "DELETE"):
            layer = Layer(
                site=layer.site,
                dialect=layer.dialect,
                attempts=1,
                per_try_ms=layer.per_try_ms,
                overall_ms=layer.overall_ms,
                backoff_ms=[0] * 8,
                retry_on=frozenset(),
                propagates=layer.propagates,
            )
        return layer
    return out
