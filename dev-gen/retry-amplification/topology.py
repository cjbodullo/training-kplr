"""The concrete estate. Hand written so every trap sits where it is meant to sit."""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from model import Call, Scenario, Service
from estate import Policy, to_layer

# --------------------------------------------------------------- policy helpers


def grpc(attempts, init="0.05s", mx="0.25s", codes=("UNAVAILABLE",), deadline_ms=None):
    n = {
        "retryPolicy": {
            "maxAttempts": attempts,
            "initialBackoff": init,
            "maxBackoff": mx,
            "backoffMultiplier": 2,
            "retryableStatusCodes": list(codes),
        }
    }
    if deadline_ms:
        n["deadline_ms"] = deadline_ms
    return Policy("grpc", n)


def grpc_hedge(attempts, delay="0.04s", codes=("UNAVAILABLE",), deadline_ms=None):
    n = {
        "hedging": {
            "maxAttempts": attempts,
            "hedgingDelay": delay,
            "nonFatalStatusCodes": list(codes),
        }
    }
    if deadline_ms:
        n["deadline_ms"] = deadline_ms
    return Policy("grpc", n)


def grpc_plain(deadline_ms=None):
    """No retry policy at all: one attempt, deadline only."""
    n = {"retryPolicy": {
        "maxAttempts": 1, "initialBackoff": "0s", "maxBackoff": "0s",
        "backoffMultiplier": 2, "retryableStatusCodes": []}}
    if deadline_ms:
        n["deadline_ms"] = deadline_ms
    return Policy("grpc", n)


def gohttp(max_retries, backoff_ms=(0,), statuses=(), retry_timeout=False,
           request_ms=None, overall_ms=None):
    return Policy("gohttp", {
        "maxRetries": max_retries, "backoffMs": list(backoff_ms),
        "retryStatusCodes": list(statuses), "retryOnTimeout": retry_timeout,
        "requestTimeoutMs": request_ms, "overallTimeoutMs": overall_ms,
    })


def u3(total, backoff=0.0, forcelist=(), read_ms=None, major=2, retry_read=True):
    return Policy("urllib3", {
        "total": total, "backoff_factor": backoff,
        "status_forcelist": list(forcelist), "read_timeout_ms": read_ms,
        "urllib3_major": major, "retry_read": retry_read,
    })


def ten(attempts, wait_ms=0, statuses=(), retry_timeout=False, read_ms=None, stop_delay_ms=None):
    return Policy("tenacity", {
        "stop_after_attempt": attempts, "wait_fixed_ms": wait_ms,
        "retry_on_status": list(statuses), "retry_timeout": retry_timeout,
        "read_timeout_ms": read_ms, "stop_after_delay_ms": stop_delay_ms,
    })


def r4j(attempts, wait_ms=0, statuses=(), retry_timeout=False, read_ms=None, tl_ms=None):
    return Policy("resilience4j", {
        "maxAttempts": attempts, "waitDuration_ms": wait_ms,
        "retryStatuses": list(statuses), "retry_timeout": retry_timeout,
        "read_timeout_ms": read_ms, "time_limiter_ms": tl_ms,
    })


def polly(retries, sleeps=(0,), statuses=(), retry_timeout=False, http_ms=None, overall_ms=None):
    return Policy("polly", {
        "retryCount": retries, "sleep_ms": list(sleeps),
        "handleStatuses": list(statuses), "retry_timeout": retry_timeout,
        "http_client_timeout_ms": http_ms, "overall_timeout_ms": overall_ms,
    })


def nginx(tries, next_upstream, read_ms=None, next_timeout_ms=None):
    return Policy("nginx", {
        "proxy_next_upstream_tries": tries, "proxy_next_upstream": next_upstream,
        "proxy_read_timeout_ms": read_ms,
        "proxy_next_upstream_timeout_ms": next_timeout_ms,
    })


def haproxy(retries, retry_on="", timeout_server_ms=None):
    return Policy("haproxy", {
        "retries": retries, "retry_on": retry_on,
        "timeout_server_ms": timeout_server_ms,
    })


def envoy(num_retries, retry_on, per_try_ms=None, timeout_ms=None, base=25, mx=250,
          codes=()):
    return Policy("envoy", {
        "num_retries": num_retries, "retry_on": retry_on,
        "per_try_timeout_ms": per_try_ms, "timeout_ms": timeout_ms,
        "base_interval_ms": base, "max_interval_ms": mx,
        "retriable_status_codes": list(codes),
    }, site="app")


def istio(num_retries, retry_on, per_try_ms=None, timeout_ms=None, base=25, mx=250,
          codes=()):
    return Policy("istio", {
        "num_retries": num_retries, "retry_on": retry_on,
        "per_try_timeout_ms": per_try_ms, "timeout_ms": timeout_ms,
        "base_interval_ms": base, "max_interval_ms": mx,
        "retriable_status_codes": list(codes),
    }, site="mesh")


# ------------------------------------------------------------------ namespaces

# istio-injection label on the namespace
NAMESPACES = {
    "edge": False,       # the two public proxies run outside the mesh
    "core": True,
    "catalog": True,
    "fulfil": False,     # legacy namespace, never onboarded to the mesh
    "payments": True,
    "data": True,
}

# workloads whose pod template overrides the namespace label
POD_INJECT_OVERRIDE = {
    "fraud-scoring": False,   # opted out after a latency incident
    "pick-service": True,     # opted in ahead of its namespace
}


def has_sidecar(svc: Service) -> bool:
    if svc.name in POD_INJECT_OVERRIDE:
        return POD_INJECT_OVERRIDE[svc.name]
    return NAMESPACES[svc.namespace]


# ------------------------------------------------------- mesh route rules (VS)
# host -> list of (uri prefix or None, policy). First matching rule wins.
VIRTUAL_SERVICES: Dict[str, List[Tuple[Optional[str], Policy]]] = {
    "basket-service": [(None, istio(2, "gateway-error,connect-failure", per_try_ms=400, timeout_ms=1500))],
    "pricing-service": [(None, istio(1, "5xx", per_try_ms=300, timeout_ms=1200))],
    "inventory-service": [(None, istio(1, "gateway-error", per_try_ms=900, timeout_ms=2000))],
    # only the v2 read path carries retries; the v1 posting path is left alone
    "ledger-service": [("/v2/", istio(2, "5xx", per_try_ms=250, timeout_ms=1000))],
    "risk-service": [(None, istio(1, "connect-failure,reset", per_try_ms=500, timeout_ms=1500))],
    "identity-service": [(None, istio(2, "gateway-error", per_try_ms=200, timeout_ms=900))],
    "session-store": [(None, istio(2, "gateway-error,reset", per_try_ms=120, timeout_ms=600))],
    "catalog-index": [(None, istio(1, "5xx", per_try_ms=350, timeout_ms=1400))],
    "rating-service": [(None, istio(1, "gateway-error", per_try_ms=200, timeout_ms=700))],
    "entitlement-service": [(None, istio(2, "gateway-error", per_try_ms=180, timeout_ms=800))],
    "tax-service": [(None, istio(1, "5xx", per_try_ms=260, timeout_ms=900))],
    "promo-service": [(None, istio(1, "gateway-error", per_try_ms=220, timeout_ms=800))],
    "settlement-service": [(None, istio(1, "gateway-error", per_try_ms=600, timeout_ms=1800))],
    "invoice-service": [(None, istio(1, "5xx", per_try_ms=400, timeout_ms=1500))],
    "token-service": [(None, istio(2, "gateway-error", per_try_ms=150, timeout_ms=600))],
    "pref-service": [(None, istio(1, "gateway-error", per_try_ms=150, timeout_ms=600))],
    "loyalty-service": [(None, istio(1, "gateway-error", per_try_ms=300, timeout_ms=1000))],
    "slot-service": [(None, istio(2, "gateway-error", per_try_ms=350, timeout_ms=1300))],
    "media-service": [(None, istio(1, "gateway-error", per_try_ms=250, timeout_ms=900))],
    "device-trust": [(None, istio(2, "gateway-error", per_try_ms=120, timeout_ms=500))],
    "fraud-scoring": [(None, istio(1, "5xx", per_try_ms=400, timeout_ms=1200))],
    "geo-service": [(None, istio(1, "gateway-error", per_try_ms=150, timeout_ms=600))],
    "warehouse-api": [(None, istio(1, "gateway-error", per_try_ms=700, timeout_ms=2000))],
    "recommendation-api": [(None, istio(1, "gateway-error", per_try_ms=300, timeout_ms=1000))],
    "payments-api": [(None, istio(1, "connect-failure", per_try_ms=900, timeout_ms=2500))],
    "catalog-api": [(None, istio(1, "gateway-error", per_try_ms=500, timeout_ms=1800))],
}


def mesh_policy(host: str, path: str) -> Optional[Policy]:
    for prefix, pol in VIRTUAL_SERVICES.get(host, []):
        if prefix is None or path.startswith(prefix):
            return pol
    return None


# ------------------------------------------------------------------- the estate

# (name, namespace, stack, parallel, router, [(target, path, method, app policy, fanout)])
ESTATE = [
    # ---- edge -------------------------------------------------------------
    ("web-gateway", "edge", "nginx", False, True, [
        ("checkout-api", "/checkout/submit", "POST", nginx(3, "error timeout http_502 http_503", read_ms=2500), 1),
        ("catalog-api", "/catalog/item", "GET", nginx(3, "error timeout http_502 http_503", read_ms=1800), 1),
        ("account-api", "/account/profile", "GET", nginx(3, "error timeout http_502 http_503", read_ms=1800), 1),
        ("order-api", "/orders/place", "POST", nginx(3, "error timeout http_503 non_idempotent", read_ms=3000), 1),
        ("search-api", "/search/query", "GET", nginx(2, "error timeout http_503", read_ms=1200), 1),
    ]),
    ("mobile-edge", "edge", "haproxy", False, True, [
        ("delivery-api", "/m/slots", "GET", haproxy(3, "conn-failure response-timeout 503", 1600), 1),
        ("payments-api", "/m/pay", "POST", haproxy(1, "conn-failure", 2500), 1),
        ("recommendation-api", "/m/recs", "GET", haproxy(3, "all-retryable-errors", 1000), 1),
        ("refund-api", "/m/refund", "POST", haproxy(2, "conn-failure 503", 2200), 1),
    ]),

    # ---- core APIs --------------------------------------------------------
    ("checkout-api", "core", "grpc-go", False, False, [
        ("basket-service", "/grocer.v1.Basket/Load", "POST", grpc(3, deadline_ms=2400), 1),
        ("pricing-service", "/grocer.v1.Pricing/Quote", "POST", grpc(2, deadline_ms=1500), 1),
        ("inventory-service", "/grocer.v1.Stock/Reserve", "POST", grpc_plain(deadline_ms=1800), 1),
        ("payments-api", "/v1/pay/authorise", "POST", gohttp(1, (150,), statuses=(503,), retry_timeout=True, request_ms=1100, overall_ms=2200), 1),
    ]),
    ("order-api", "core", "spring-r4j", False, False, [
        ("basket-service", "/grocer.v1.Basket/Load", "POST", r4j(3, 120, statuses=(503,), read_ms=700), 1),
        ("fulfilment-service", "/v1/plan", "POST", r4j(2, 200, statuses=(503, 502), retry_timeout=True, read_ms=900), 1),
        ("ledger-service", "/v1/post", "POST", r4j(3, 100, statuses=(503,), read_ms=600), 1),
    ]),
    ("account-api", "core", "py-urllib3", False, False, [
        ("identity-service", "/v1/whoami", "GET", u3(2, 0.1, (502, 503), read_ms=400), 1),
        ("pref-service", "/v1/prefs", "GET", u3(1, 0.0, (503,), read_ms=300), 1),
        ("loyalty-service", "/v1/tier", "GET", u3(2, 0.05, (), read_ms=500, retry_read=True), 1),
    ]),
    ("search-api", "core", "grpc-go", False, False, [
        ("catalog-index", "/grocer.v1.Index/Search", "POST", grpc_hedge(3, "0.04s", deadline_ms=1200), 1),
        ("recommendation-api", "/v1/recs", "GET", gohttp(1, (80,), statuses=(503,), retry_timeout=True, request_ms=450, overall_ms=900), 1),
    ]),
    ("catalog-api", "catalog", "dotnet-polly", False, False, [
        ("catalog-index", "/v1/index/get", "GET", polly(2, (60, 120), statuses=(503, 504), http_ms=600), 1),
        ("media-service", "/v1/asset", "GET", polly(1, (50,), statuses=(503,), http_ms=400), 1),
        ("rating-service", "/v1/score", "GET", polly(2, (40, 80), statuses=(503,), retry_timeout=True, http_ms=300), 1),
    ]),
    ("delivery-api", "core", "py-tenacity", False, False, [
        ("slot-service", "/v1/slots", "GET", ten(3, 150, statuses=(503,), retry_timeout=True, read_ms=500), 1),
        ("address-service", "/v1/resolve", "GET", ten(2, 100, statuses=(), retry_timeout=True, read_ms=400), 1),
    ]),
    ("payments-api", "payments", "spring-r4j", False, False, [
        ("risk-service", "/v1/score", "POST", r4j(2, 80, statuses=(503,), read_ms=800), 1),
        ("ledger-service", "/v2/reserve", "POST", r4j(3, 90, statuses=(503,), retry_timeout=True, read_ms=500), 1),
        ("partner-gateway", "/psp/auth", "POST", r4j(2, 250, statuses=(), retry_timeout=True, read_ms=1200), 1),
    ]),
    ("recommendation-api", "catalog", "py-urllib3", False, False, [
        ("rating-service", "/v1/score", "GET", u3(2, 0.05, (503,), read_ms=250), 1),
        ("catalog-index", "/v1/index/get", "GET", u3(1, 0.05, (503,), read_ms=350), 1),
    ]),
    ("refund-api", "payments", "dotnet-polly", False, False, [
        ("ledger-service", "/v2/reverse", "POST", polly(2, (100, 200), statuses=(503,), http_ms=600), 1),
        ("invoice-service", "/v1/credit", "POST", polly(1, (150,), statuses=(503,), retry_timeout=True, http_ms=700), 1),
        ("settlement-service", "/v1/settle", "POST", polly(2, (120, 240), statuses=(503,), http_ms=900), 1),
    ]),

    # ---- core domain ------------------------------------------------------
    ("basket-service", "core", "grpc-go", False, False, [
        ("pricing-service", "/grocer.v1.Pricing/Quote", "POST", grpc(2, deadline_ms=900), 1),
        ("session-store", "/grocer.v1.KV/Get", "GET", grpc(3, init="0.02s", mx="0.08s", deadline_ms=400), 1),
    ]),
    ("pricing-service", "core", "grpc-go", False, False, [
        ("promo-service", "/v1/promo/eval", "POST", gohttp(1, (60,), statuses=(503,), retry_timeout=True, request_ms=300, overall_ms=600), 1),
        ("tax-service", "/v1/tax/rate", "POST", gohttp(1, (70,), statuses=(503,), retry_timeout=True, request_ms=350, overall_ms=700), 1),
    ]),
    ("inventory-service", "core", "grpc-go", True, False, [
        ("stock-shard", "/grocer.v1.Shard/Peek", "GET", grpc(2, init="0.03s", mx="0.12s", deadline_ms=800), 8),
        ("warehouse-api", "/v1/onhand", "GET", gohttp(1, (100,), statuses=(503,), retry_timeout=True, request_ms=600, overall_ms=1200), 1),
    ]),
    ("fulfilment-service", "fulfil", "spring-r4j", False, False, [
        ("slot-service", "/v1/slots", "GET", r4j(2, 120, statuses=(503,), read_ms=600), 1),
        ("pick-service", "/v1/pick", "POST", r4j(3, 80, statuses=(503,), retry_timeout=True, read_ms=500), 1),
        ("label-service", "/v1/label", "POST", r4j(2, 100, statuses=(503,), read_ms=700), 1),
    ]),
    ("ledger-service", "payments", "grpc-go", False, False, [
        ("settlement-service", "/grocer.v1.Settlement/Settle", "POST", grpc(2, deadline_ms=1000), 1),
    ]),
    ("risk-service", "payments", "grpc-go", True, False, [
        ("fraud-scoring", "/v1/score", "POST", gohttp(2, (40, 80), statuses=(503,), retry_timeout=True, request_ms=350, overall_ms=700), 1),
        ("device-trust", "/grocer.v1.Trust/Check", "GET", grpc(2, deadline_ms=400), 1),
    ]),
    ("identity-service", "core", "grpc-go", False, False, [
        ("token-service", "/grocer.v1.Token/Verify", "POST", grpc_hedge(3, "0.03s", deadline_ms=300), 1),
        ("session-store", "/grocer.v1.KV/Get", "GET", grpc(2, init="0.02s", mx="0.08s", deadline_ms=250), 1),
    ]),
    ("loyalty-service", "core", "py-urllib3", False, False, [
        ("entitlement-service", "/v1/grants", "GET", u3(2, 0.05, (503,), read_ms=300), 1),
    ]),
    ("promo-service", "core", "py-tenacity", False, False, [
        ("entitlement-service", "/v1/grants", "GET", ten(2, 60, statuses=(), retry_timeout=True, read_ms=200), 1),
    ]),
    ("tax-service", "core", "dotnet-polly", False, False, [
        ("geo-service", "/v1/zone", "GET", polly(1, (40,), statuses=(503,), http_ms=200), 1),
    ]),
    ("media-service", "catalog", "dotnet-polly", False, False, [
        ("cdn-origin", "/assets", "GET", polly(2, (30, 60), statuses=(502, 503), http_ms=300), 1),
    ]),
    ("address-service", "core", "py-urllib3", False, False, [
        ("postcode-service", "/v1/lookup", "GET", u3(1, 0.0, (503,), read_ms=200, major=1), 1),
        ("geo-service", "/v1/zone", "GET", u3(2, 0.05, (503,), read_ms=200), 1),
    ]),
    ("slot-service", "fulfil", "grpc-go", False, False, [
        ("route-service", "/v1/route/plan", "POST", gohttp(1, (70,), statuses=(503,), retry_timeout=True, request_ms=350, overall_ms=700), 1),
        ("geo-service", "/grocer.v1.Geo/Zone", "GET", grpc(2, init="0.02s", mx="0.08s", deadline_ms=300), 1),
    ]),
    ("route-service", "fulfil", "spring-r4j", False, False, [
        ("courier-service", "/v1/dispatch", "POST", r4j(3, 70, statuses=(503,), retry_timeout=True, read_ms=400), 1),
    ]),
    ("courier-service", "fulfil", "envoy-egress", False, False, [
        ("partner-gateway", "/courier/book", "POST", envoy(2, "gateway-error", per_try_ms=500, timeout_ms=1600), 1),
    ]),
    ("partner-gateway", "edge", "haproxy", False, False, [
        ("psp-acquirer", "/ext", "POST", haproxy(2, "conn-failure response-timeout", 900), 1),
    ]),
    ("pick-service", "fulfil", "grpc-go", False, False, [
        ("warehouse-api", "/v1/onhand", "GET", gohttp(1, (90,), statuses=(503,), retry_timeout=True, request_ms=450, overall_ms=900), 1),
    ]),
    ("label-service", "fulfil", "py-tenacity", False, False, [
        ("courier-service", "/v1/dispatch", "POST", ten(2, 90, statuses=(503,), read_ms=400), 1),
    ]),
    ("invoice-service", "payments", "spring-r4j", False, False, [
        ("ledger-service", "/v2/reserve", "POST", r4j(2, 110, statuses=(503,), read_ms=500), 1),
    ]),
    ("settlement-service", "payments", "grpc-go", False, False, [
        ("partner-gateway", "/psp/settle", "POST", gohttp(2, (110, 220), statuses=(503,), retry_timeout=True, request_ms=550, overall_ms=1100), 1),
    ]),
    ("fraud-scoring", "payments", "py-urllib3", False, False, [
        ("device-trust", "/v1/trust", "GET", u3(2, 0.04, (503,), read_ms=150), 1),
    ]),
    ("warehouse-api", "fulfil", "envoy-egress", False, False, [
        ("supplier-api", "/supplier/stock", "GET", envoy(2, "5xx", per_try_ms=400, timeout_ms=1500), 1),
    ]),
    ("entitlement-service", "core", "grpc-go", False, False, [
        ("session-store", "/grocer.v1.KV/Get", "GET", grpc(2, init="0.02s", mx="0.08s", deadline_ms=200), 1),
    ]),
    ("catalog-index", "catalog", "grpc-go", False, False, []),
    ("rating-service", "catalog", "py-urllib3", False, False, []),
    ("stock-shard", "core", "grpc-go", False, False, []),
    ("session-store", "data", "grpc-go", False, False, []),
    ("token-service", "core", "grpc-go", False, False, []),
    ("pref-service", "core", "py-urllib3", False, False, []),
    ("geo-service", "core", "grpc-go", False, False, []),
    ("postcode-service", "core", "py-urllib3", False, False, []),
    ("device-trust", "payments", "grpc-go", False, False, []),
    ("cdn-origin", "catalog", "nginx", False, False, []),
    ("supplier-api", "edge", "nginx", False, False, []),
    ("psp-acquirer", "edge", "nginx", False, False, []),
]

# upstreams still configured but no longer called on any live route. The estate has
# never had a clean-up pass; the traces are what says an edge is live.
STALE = {
    "checkout-api": [("loyalty-service", "/v1/tier", "GET", "gohttp")],
    "account-api": [("session-store", "/v1/kv/get", "GET", "urllib3")],
    "catalog-api": [("recommendation-api", "/v1/recs", "GET", "polly")],
    "fulfilment-service": [("geo-service", "/v1/zone", "GET", "resilience4j")],
    "refund-api": [("risk-service", "/v1/score", "POST", "polly")],
    "payments-api": [("device-trust", "/v1/trust", "GET", "resilience4j")],
}

# kubernetes Service names that do not match the workload name
SERVICE_DNS = {
    "recommendation-api": "recs-internal",
    "warehouse-api": "wms-gateway",
    "catalog-index": "index-grpc",
}


_STALE_POLICY = {
    "gohttp": lambda: gohttp(1, (100,), statuses=(503,), retry_timeout=True,
                             request_ms=500, overall_ms=1000),
    "urllib3": lambda: u3(1, 0.05, (503,), read_ms=250),
    "polly": lambda: polly(1, (80,), statuses=(503,), http_ms=400),
    "resilience4j": lambda: r4j(2, 100, statuses=(503,), read_ms=400),
    "tenacity": lambda: ten(2, 80, statuses=(503,), read_ms=300),
}


def stale_entries(name):
    """Configured upstreams that no longer carry traffic on any live route."""
    return [(t, path, method, _STALE_POLICY[dialect](), 1)
            for t, path, method, dialect in STALE.get(name, [])]


def build(flags: Optional[dict] = None) -> Tuple[Dict[str, Service], List[Scenario]]:
    """flags is for the ablation battery only; the shipped estate uses no flags."""
    f = flags or {}
    services: Dict[str, Service] = {}
    raw: Dict[str, list] = {}
    for name, ns, stack, parallel, router, calls in ESTATE:
        services[name] = Service(
            name=name, namespace=ns, stack=stack, parallel=parallel,
            service_dns=SERVICE_DNS.get(name, name), router=router, calls=[],
        )
        raw[name] = calls

    for name, calls in raw.items():
        svc = services[name]
        if f.get("parallel_as_sequential"):
            svc.parallel = False
        sidecar = has_sidecar(svc)
        if f.get("mesh_everywhere"):
            sidecar = True
        if f.get("no_mesh"):
            sidecar = False
        for target, path, method, pol, fanout in calls:
            layers = []
            app = to_layer(pol, "GET" if f.get("nginx_post_retries") else method)
            if app is not None:
                layers.append(_ablate(app, f))
            if sidecar:
                mesh = mesh_policy(target, "/v2/" if f.get("ignore_vs_match") else path)
                if mesh is not None:
                    layers.append(_ablate(to_layer(mesh, method), f))
            svc.calls.append(Call(
                target=target, layers=layers, fanout=1 if f.get("no_fanout") else fanout,
                label=path, path=path, method=method,
            ))
    return services, SCENARIOS


_TOTAL_DIALECTS = {"grpc", "tenacity", "resilience4j", "nginx"}
_RETRY_DIALECTS = {"envoy", "istio", "urllib3", "polly", "haproxy", "gohttp"}


def _ablate(layer, f):
    import dataclasses
    if not f:
        return layer
    ch = {}
    if f.get("attempts_as_total") and layer.dialect in _RETRY_DIALECTS:
        ch["attempts"] = max(1, layer.attempts - 1)
    if f.get("attempts_as_retries") and layer.dialect in _TOTAL_DIALECTS:
        ch["attempts"] = layer.attempts + 1
    if f.get("retry_any_5xx"):
        ch["retry_on"] = frozenset({"500", "502", "503", "504"})
    if f.get("propagate_all"):
        ch["propagates"] = True
    if f.get("propagate_none"):
        ch["propagates"] = False
    if f.get("no_overall"):
        ch["overall_ms"] = None
    if f.get("hedge_once") and layer.hedge_delay_ms is not None:
        ch["attempts"] = 1
    if f.get("haproxy_503") and layer.dialect == "haproxy":
        ch["retry_on"] = frozenset(set(layer.retry_on) | {"503"})
    if f.get("budget_divides"):
        ch["attempts"] = max(1, int(layer.attempts * 0.2) + 1) if layer.site == "mesh" else layer.attempts
    return dataclasses.replace(layer, **ch) if ch else layer


SCENARIOS: List[Scenario] = [
    Scenario("S01", "web-gateway", "pricing-service", "/checkout/submit", "fast", "503", 5000),
    Scenario("S02", "web-gateway", "pricing-service", "/checkout/submit", "hang", "503", 5000),
    Scenario("S03", "web-gateway", "session-store", "/checkout/submit", "fast", "503", 5000),
    Scenario("S04", "web-gateway", "stock-shard", "/checkout/submit", "fast", "503", 5000),
    Scenario("S05", "web-gateway", "stock-shard", "/checkout/submit", "hang", "503", 5000),
    Scenario("S06", "web-gateway", "settlement-service", "/checkout/submit", "fast", "503", 5000),
    Scenario("S07", "web-gateway", "token-service", "/account/profile", "fast", "503", 4000),
    Scenario("S08", "web-gateway", "token-service", "/account/profile", "hang", "503", 4000),
    Scenario("S09", "web-gateway", "entitlement-service", "/account/profile", "fast", "503", 4000),
    Scenario("S10", "web-gateway", "geo-service", "/orders/place", "fast", "503", 6000),
    Scenario("S11", "web-gateway", "courier-service", "/orders/place", "fast", "503", 6000),
    Scenario("S12", "web-gateway", "psp-acquirer", "/orders/place", "hang", "503", 6000),
    Scenario("S13", "web-gateway", "catalog-index", "/search/query", "fast", "503", 3000),
    Scenario("S14", "web-gateway", "catalog-index", "/search/query", "hang", "503", 3000),
    Scenario("S15", "web-gateway", "rating-service", "/search/query", "fast", "503", 3000),
    Scenario("S16", "web-gateway", "cdn-origin", "/catalog/item", "fast", "502", 3500),
    Scenario("S17", "web-gateway", "catalog-index", "/catalog/item", "fast", "503", 3500),
    Scenario("S18", "mobile-edge", "geo-service", "/m/slots", "fast", "503", 4500),
    Scenario("S19", "mobile-edge", "geo-service", "/m/slots", "hang", "503", 4500),
    Scenario("S20", "mobile-edge", "psp-acquirer", "/m/pay", "fast", "503", 5000),
    Scenario("S21", "mobile-edge", "device-trust", "/m/pay", "fast", "503", 5000),
    Scenario("S22", "mobile-edge", "device-trust", "/m/pay", "hang", "503", 5000),
    Scenario("S23", "mobile-edge", "rating-service", "/m/recs", "fast", "503", 2500),
    Scenario("S24", "mobile-edge", "settlement-service", "/m/refund", "fast", "503", 5500),
    Scenario("S25", "mobile-edge", "invoice-service", "/m/refund", "hang", "503", 5500),
    Scenario("S26", "web-gateway", "supplier-api", "/checkout/submit", "fast", "503", 5000),
    Scenario("S27", "web-gateway", "ledger-service", "/orders/place", "fast", "503", 6000),
    Scenario("S28", "web-gateway", "ledger-service", "/orders/place", "hang", "503", 6000),
    Scenario("S29", "web-gateway", "warehouse-api", "/checkout/submit", "hang", "503", 5000),
    Scenario("S30", "web-gateway", "recommendation-api", "/search/query", "fast", "503", 3000),
    Scenario("S31", "web-gateway", "promo-service", "/checkout/submit", "fast", "503", 5000),
    Scenario("S32", "mobile-edge", "route-service", "/m/slots", "fast", "503", 4500),
]
