"""Render the estate into the files the platform actually keeps in its repo."""

from __future__ import annotations

import json
import os
from typing import Dict

from topology import (
    ESTATE, NAMESPACES, POD_INJECT_OVERRIDE, SERVICE_DNS, STALE,
    VIRTUAL_SERVICES, stale_entries,
)

STACK_IMAGE = {
    "nginx": "nginx:1.27.3-alpine",
    "haproxy": "haproxy:3.0.6-alpine",
    "envoy-egress": "envoyproxy/envoy:v1.32.1",
    "grpc-go": "registry.internal/go-runtime:1.23.4",
    "spring-r4j": "registry.internal/jdk21-boot:3.3.5",
    "py-urllib3": "registry.internal/python:3.12.7",
    "py-tenacity": "registry.internal/python:3.12.7",
    "dotnet-polly": "registry.internal/dotnet:8.0.11",
}

PORT = {
    "grpc-go": 8443,
    "spring-r4j": 8080,
    "py-urllib3": 8080,
    "py-tenacity": 8080,
    "dotnet-polly": 8080,
    "nginx": 8080,
    "haproxy": 8080,
    "envoy-egress": 10000,
}


def w(root, rel, text):
    path = os.path.join(root, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


def dns(name, ns):
    return f"{SERVICE_DNS.get(name, name)}.{ns}.svc.cluster.local"


def ns_of(name):
    for n, ns, *_ in ESTATE:
        if n == name:
            return ns
    raise KeyError(name)


def stack_of(name):
    for n, _, stack, *_ in ESTATE:
        if n == name:
            return stack
    raise KeyError(name)


# ----------------------------------------------------------------- kubernetes


def render_k8s(root):
    lines = []
    for ns, injected in NAMESPACES.items():
        labels = {"name": ns, "platform.grocer.io/tier": _tier(ns)}
        if injected:
            labels["istio-injection"] = "enabled"
        body = "\n".join(f"    {k}: {json.dumps(v)}" for k, v in sorted(labels.items()))
        lines.append(
            "apiVersion: v1\nkind: Namespace\nmetadata:\n"
            f"  name: {ns}\n  labels:\n{body}\n"
        )
    w(root, "platform/kubernetes/namespaces.yaml", "---\n".join(lines))

    for name, ns, stack, parallel, router, calls in ESTATE:
        ann = {"prometheus.io/scrape": "true", "checksum/config": _cksum(name)}
        if name in POD_INJECT_OVERRIDE:
            ann["sidecar.istio.io/inject"] = "true" if POD_INJECT_OVERRIDE[name] else "false"
        ann_block = "\n".join(f"        {k}: {json.dumps(v)}" for k, v in sorted(ann.items()))
        port = PORT[stack]
        env = [("SERVICE_NAME", name), ("POD_NAMESPACE", ns)]
        for target, path, method, pol, fanout in calls:
            key = target.upper().replace("-", "_")
            env.append((f"{key}_ADDR", f"{dns(target, ns_of(target))}:{PORT[stack_of(target)]}"))
        env_block = "\n".join(
            f"            - name: {k}\n              value: {json.dumps(v)}" for k, v in env
        )
        w(root, f"platform/kubernetes/{ns}/{name}.yaml", f"""apiVersion: apps/v1
kind: Deployment
metadata:
  name: {name}
  namespace: {ns}
  labels:
    app: {name}
    app.kubernetes.io/part-of: grocer-platform
spec:
  replicas: {3 if router else 2}
  selector:
    matchLabels:
      app: {name}
  template:
    metadata:
      labels:
        app: {name}
        version: v1
      annotations:
{ann_block}
    spec:
      containers:
        - name: {name}
          image: {STACK_IMAGE[stack]}
          ports:
            - name: {"grpc" if stack == "grpc-go" else "http"}
              containerPort: {port}
          env:
{env_block}
---
apiVersion: v1
kind: Service
metadata:
  name: {SERVICE_DNS.get(name, name)}
  namespace: {ns}
  labels:
    app: {name}
spec:
  selector:
    app: {name}
  ports:
    - name: {"grpc" if stack == "grpc-go" else "http"}
      port: {port}
      targetPort: {port}
""")


def _tier(ns):
    return {"edge": "edge", "data": "stateful"}.get(ns, "application")


def _cksum(name):
    h = 0
    for ch in name:
        h = (h * 131 + ord(ch)) % (2 ** 32)
    return f"{h:08x}"


# ----------------------------------------------------------------------- mesh


def render_mesh(root):
    for host, rules in sorted(VIRTUAL_SERVICES.items()):
        ns = ns_of(host)
        fqdn = f"{SERVICE_DNS.get(host, host)}.{ns}.svc.cluster.local"
        out = ["apiVersion: networking.istio.io/v1", "kind: VirtualService",
               "metadata:", f"  name: {host}", f"  namespace: {ns}",
               "spec:", "  hosts:", f"    - {fqdn}", "  http:"]
        for prefix, pol in rules:
            n = pol.native
            first = True

            def bullet(text):
                nonlocal first
                out.append(("    - " if first else "      ") + text)
                first = False

            if prefix is not None:
                bullet("match:")
                out.append(f"        - uri:")
                out.append(f"            prefix: {prefix}")
            bullet("route:")
            out.append("        - destination:")
            out.append(f"            host: {fqdn}")
            bullet(f"timeout: {_ms(n['timeout_ms'])}")
            out.append("      retries:")
            out.append(f"        attempts: {n['num_retries']}")
            out.append(f"        perTryTimeout: {_ms(n['per_try_timeout_ms'])}")
            out.append(f"        retryOn: {n['retry_on']}")
        w(root, f"platform/mesh/virtualservice/{host}.yaml", "\n".join(out) + "\n")

    for host in sorted(VIRTUAL_SERVICES):
        ns = ns_of(host)
        fqdn = f"{SERVICE_DNS.get(host, host)}.{ns}.svc.cluster.local"
        w(root, f"platform/mesh/destinationrule/{host}.yaml", f"""apiVersion: networking.istio.io/v1
kind: DestinationRule
metadata:
  name: {host}
  namespace: {ns}
spec:
  host: {fqdn}
  trafficPolicy:
    connectionPool:
      tcp:
        maxConnections: {64 + (len(host) % 7) * 16}
      http:
        http1MaxPendingRequests: {32 + (len(host) % 5) * 8}
        maxRequestsPerConnection: 128
    outlierDetection:
      consecutive5xxErrors: 5
      interval: 10s
      baseEjectionTime: 30s
      maxEjectionPercent: 50
""")


def _ms(v):
    if v is None:
        return "null"
    if v % 1000 == 0:
        return f"{v // 1000}s"
    return f"{v}ms"


# ------------------------------------------------------------------ edge nginx


def render_nginx(root):
    gw = next(e for e in ESTATE if e[0] == "web-gateway")
    routes = gw[5]
    upstreams = []
    locations = []
    for target, path, method, pol, fanout in routes:
        n = pol.native
        up = target.replace("-", "_")
        upstreams.append(
            f"    upstream {up} {{\n"
            f"        server {dns(target, ns_of(target))}:{PORT[stack_of(target)]} max_fails=0;\n"
            f"        keepalive 32;\n    }}"
        )
        loc = [f"        location {path} {{"]
        loc.append(f"            proxy_pass http://{up};")
        # the http block already sets these; a location only repeats what it changes
        if n["proxy_next_upstream"] != HTTP_NEXT_UPSTREAM:
            loc.append(f"            proxy_next_upstream {n['proxy_next_upstream']};")
        if n["proxy_next_upstream_tries"] != HTTP_NEXT_TRIES:
            loc.append(f"            proxy_next_upstream_tries {n['proxy_next_upstream_tries']};")
        if n.get("proxy_read_timeout_ms"):
            loc.append(f"            proxy_read_timeout {_ms(n['proxy_read_timeout_ms'])};")
        loc.append("            proxy_set_header X-Request-Id $request_id;")
        loc.append("        }")
        locations.append("\n".join(loc))

    w(root, "platform/edge/nginx/nginx.conf", f"""user  www-data;
worker_processes  auto;
error_log  /var/log/nginx/error.log notice;
events {{
    worker_connections  4096;
}}

http {{
    include       /etc/nginx/mime.types;
    default_type  application/octet-stream;
    sendfile        on;
    keepalive_timeout  65;

    proxy_connect_timeout 200ms;
    proxy_send_timeout 2s;
    proxy_read_timeout 2s;
    proxy_next_upstream {HTTP_NEXT_UPSTREAM};
    proxy_next_upstream_tries {HTTP_NEXT_TRIES};
    proxy_next_upstream_timeout 0;

{chr(10).join(upstreams)}

    server {{
        listen 8080;
        server_name www.grocer.example;

{chr(10).join(locations)}

        location /healthz {{
            return 200 'ok';
        }}
    }}
}}
""")


HTTP_NEXT_UPSTREAM = "error timeout http_502 http_503"
HTTP_NEXT_TRIES = 3


# --------------------------------------------------------------- edge haproxy


def render_haproxy(root):
    me = next(e for e in ESTATE if e[0] == "mobile-edge")
    pg = next(e for e in ESTATE if e[0] == "partner-gateway")
    backends = []
    rules = []
    for target, path, method, pol, fanout in me[5]:
        n = pol.native
        be = "be_" + target.replace("-", "_")
        rules.append(f"    use_backend {be} if {{ path_beg {path} }}")
        body = [f"backend {be}", "    mode http", "    balance roundrobin"]
        if n["retries"] != DEFAULTS_RETRIES:
            body.append(f"    retries {n['retries']}")
        if n.get("retry_on"):
            body.append(f"    retry-on {n['retry_on']}")
        if n.get("timeout_server_ms"):
            body.append(f"    timeout server {n['timeout_server_ms']}ms")
        body.append(
            f"    server s1 {dns(target, ns_of(target))}:{PORT[stack_of(target)]} check init-addr none"
        )
        backends.append("\n".join(body))

    for target, path, method, pol, fanout in pg[5]:
        n = pol.native
        body = ["backend be_psp", "    mode http", "    balance first"]
        if n["retries"] != DEFAULTS_RETRIES:
            body.append(f"    retries {n['retries']}")
        if n.get("retry_on"):
            body.append(f"    retry-on {n['retry_on']}")
        if n.get("timeout_server_ms"):
            body.append(f"    timeout server {n['timeout_server_ms']}ms")
        body.append(
            f"    server acq1 {dns(target, ns_of(target))}:{PORT[stack_of(target)]} "
            "check init-addr none")
        backends.append("\n".join(body))

    w(root, "platform/edge/haproxy/haproxy.cfg", f"""global
    log stdout format raw local0 info
    maxconn 20000

defaults
    mode http
    log global
    option httplog
    option redispatch
    retries {DEFAULTS_RETRIES}
    timeout connect 200ms
    timeout client 30s
    timeout server 2s

frontend fe_mobile
    bind *:8080
{chr(10).join(rules)}
    default_backend be_delivery_api

frontend fe_partner
    bind *:8081
    default_backend be_psp

{chr(10).join(backends)}
""")


DEFAULTS_RETRIES = 3


# ------------------------------------------------------------- envoy (egress)


def render_envoy(root):
    for name, ns, stack, parallel, router, calls in ESTATE:
        if stack != "envoy-egress":
            continue
        routes, clusters = [], []
        for target, path, method, pol, fanout in calls:
            n = pol.native
            cl = target.replace("-", "_")
            routes.append(f"""                        - match:
                            prefix: {path}
                          route:
                            cluster: {cl}
                            timeout: {_s(n['timeout_ms'])}
                            retry_policy:
                              retry_on: {n['retry_on']}
                              num_retries: {n['num_retries']}
                              per_try_timeout: {_s(n['per_try_timeout_ms'])}
                              retry_back_off:
                                base_interval: {_s(n['base_interval_ms'])}
                                max_interval: {_s(n['max_interval_ms'])}""")
            clusters.append(f"""  - name: {cl}
    type: STRICT_DNS
    connect_timeout: 0.2s
    load_assignment:
      cluster_name: {cl}
      endpoints:
        - lb_endpoints:
            - endpoint:
                address:
                  socket_address:
                    address: {dns(target, ns_of(target))}
                    port_value: {PORT[stack_of(target)]}""")
        w(root, f"services/{name}/envoy.yaml", f"""admin:
  address:
    socket_address: {{ address: 127.0.0.1, port_value: 9901 }}
static_resources:
  listeners:
    - name: egress
      address:
        socket_address: {{ address: 0.0.0.0, port_value: 10000 }}
      filter_chains:
        - filters:
            - name: envoy.filters.network.http_connection_manager
              typed_config:
                "@type": type.googleapis.com/envoy.extensions.filters.network.http_connection_manager.v3.HttpConnectionManager
                stat_prefix: egress_http
                route_config:
                  name: egress_routes
                  virtual_hosts:
                    - name: upstreams
                      domains: ["*"]
                      routes:
{chr(10).join(routes)}
                http_filters:
                  - name: envoy.filters.http.router
                    typed_config:
                      "@type": type.googleapis.com/envoy.extensions.filters.http.router.v3.Router
  clusters:
{chr(10).join(clusters)}
""")


def _s(v):
    if v is None:
        return "null"
    return f"{v / 1000:g}s"


# --------------------------------------------------------------- client stacks


def render_clients(root):
    for name, ns, stack, parallel, router, calls in ESTATE:
        if stack in ("nginx", "haproxy", "envoy-egress") or not calls:
            continue
        entries = sorted(list(calls) + stale_entries(name), key=lambda e: e[0])
        if stack == "grpc-go":
            _grpc_client(root, name, ns, entries)
        elif stack == "spring-r4j":
            _r4j_client(root, name, ns, entries)
        elif stack == "py-urllib3":
            _u3_client(root, name, ns, entries)
        elif stack == "py-tenacity":
            _ten_client(root, name, ns, entries)
        elif stack == "dotnet-polly":
            _polly_client(root, name, ns, entries)


def _grpc_client(root, name, ns, calls):
    """A Go service keeps two client files: gRPC upstreams and plain HTTP ones."""
    grpc_doc = {"upstreams": {}}
    http_doc = {"upstreams": {}}
    for target, path, method, pol, fanout in calls:
        n = pol.native
        addr = f"{dns(target, ns_of(target))}:{PORT[stack_of(target)]}"
        if pol.dialect == "grpc":
            body = path.strip("/")
            grpc_service, grpc_method = body.split("/", 1)
            cfg = {"methodConfig": [{
                "name": [{"service": grpc_service, "method": grpc_method}],
            }]}
            if n.get("deadline_ms"):
                cfg["methodConfig"][0]["timeout"] = f"{n['deadline_ms'] / 1000:g}s"
            if "hedging" in n:
                cfg["methodConfig"][0]["hedgingPolicy"] = n["hedging"]
            else:
                rp = dict(n["retryPolicy"])
                if rp["maxAttempts"] > 1:
                    cfg["methodConfig"][0]["retryPolicy"] = rp
            grpc_doc["upstreams"][target] = {
                "target": f"dns:///{addr}",
                "fullMethod": path,
                "serviceConfig": cfg,
            }
        else:
            http_doc["upstreams"][target] = {
                "baseURL": f"http://{addr}",
                "path": path,
                "method": method,
                "maxRetries": n["maxRetries"],
                "backoffMs": n["backoffMs"],
                "retryStatusCodes": n["retryStatusCodes"],
                "retryOnTimeout": n["retryOnTimeout"],
                "requestTimeoutMs": n["requestTimeoutMs"],
                "overallTimeoutMs": n["overallTimeoutMs"],
            }
    if grpc_doc["upstreams"]:
        w(root, f"services/{name}/grpc_service_config.json",
          json.dumps(grpc_doc, indent=2) + "\n")
    if http_doc["upstreams"]:
        w(root, f"services/{name}/http_upstreams.json",
          json.dumps(http_doc, indent=2) + "\n")
    w(root, f"services/{name}/client.go", f"""package client

// {name} builds one client per upstream at start up.
//
// gRPC upstreams come from grpc_service_config.json: the object under
// "serviceConfig" is handed to grpc-go verbatim through WithDefaultServiceConfig,
// so grpc-go itself applies the retry or hedging policy and the method timeout.
//
// Plain HTTP upstreams come from http_upstreams.json and go through the shared
// platform helper below. maxRetries is the number of further requests the helper
// will send after the first one has failed; backoffMs[i] is the pause before
// retry i+1; requestTimeoutMs bounds one request and overallTimeoutMs bounds the
// whole helper call including the pauses.

import (
\t"net/http"
\t"time"

\t"google.golang.org/grpc"
\t"platform/retryhttp"
)

func DialGRPC(u GRPCUpstream) (*grpc.ClientConn, error) {{
\treturn grpc.NewClient(u.Target, grpc.WithDefaultServiceConfig(u.ServiceConfigJSON))
}}

func DoHTTP(u HTTPUpstream, req *http.Request) (*http.Response, error) {{
\treturn retryhttp.Do(req, retryhttp.Options{{
\t\tMaxRetries:     u.MaxRetries,
\t\tBackoff:        u.BackoffMs,
\t\tRetryStatus:    u.RetryStatusCodes,
\t\tRetryOnTimeout: u.RetryOnTimeout,
\t\tPerRequest:     time.Duration(u.RequestTimeoutMs) * time.Millisecond,
\t\tOverall:        time.Duration(u.OverallTimeoutMs) * time.Millisecond,
\t}})
}}
""")


def _r4j_client(root, name, ns, calls):
    retry, tl, ups = [], [], []
    for target, path, method, pol, fanout in calls:
        n = pol.native
        retry.append(
            f"      {target}:\n"
            f"        maxAttempts: {n['maxAttempts']}\n"
            f"        waitDuration: {n['waitDuration_ms']}ms\n"
            f"        retryExceptions:\n"
            f"          - java.io.IOException\n"
            + ("          - java.util.concurrent.TimeoutException\n" if n.get("retry_timeout") else "")
            + f"        resultStatusCodes: {n['retryStatuses'] or []}"
        )
        if n.get("time_limiter_ms"):
            tl.append(f"      {target}:\n        timeoutDuration: {n['time_limiter_ms']}ms")
        ups.append(
            f"  {target}:\n"
            f"    url: http://{dns(target, ns_of(target))}:{PORT[stack_of(target)]}\n"
            f"    path: {path}\n"
            f"    method: {method}\n"
            f"    readTimeout: {n['read_timeout_ms']}ms"
        )
    tl_block = ("  timelimiter:\n    instances:\n" + "\n".join(tl) + "\n") if tl else ""
    w(root, f"services/{name}/application.yaml", f"""spring:
  application:
    name: {name}

resilience4j:
  retry:
    instances:
{chr(10).join(retry)}
{tl_block}
upstreams:
{chr(10).join(ups)}
""")


def _u3_client(root, name, ns, calls):
    doc = {"clients": {}}
    major = 2
    for target, path, method, pol, fanout in calls:
        n = pol.native
        major = n.get("urllib3_major", 2)
        doc["clients"][target] = {
            "url": f"http://{dns(target, ns_of(target))}:{PORT[stack_of(target)]}{path}",
            "method": method,
            "retry": {
                "total": n["total"],
                "backoff_factor": n["backoff_factor"],
                "status_forcelist": n["status_forcelist"],
                "read": n["total"],
                "raise_on_status": False,
            },
            "timeout": {
                "connect": 0.2,
                "read": (n["read_timeout_ms"] or 0) / 1000,
            },
        }
    w(root, f"services/{name}/http_clients.json", json.dumps(doc, indent=2) + "\n")
    pin = "urllib3==1.26.18" if major < 2 else "urllib3==2.2.3"
    w(root, f"services/{name}/requirements.txt", f"{pin}\nPyYAML==6.0.2\n")
    w(root, f"services/{name}/client.py", f'''"""Outbound HTTP for {name}.

Every block under "clients" in http_clients.json is passed through to urllib3: the
"retry" mapping becomes urllib3.util.Retry(**retry) and "timeout" becomes
urllib3.util.Timeout(**timeout). Nothing else in this file changes the retry
behaviour.
"""

import json
import pathlib

import urllib3

_CFG = json.loads((pathlib.Path(__file__).parent / "http_clients.json").read_text())
_POOL = urllib3.PoolManager()


def call(upstream: str, body=None):
    spec = _CFG["clients"][upstream]
    return _POOL.request(
        spec["method"],
        spec["url"],
        body=body,
        retries=urllib3.util.Retry(**spec["retry"]),
        timeout=urllib3.util.Timeout(**spec["timeout"]),
    )
''')


def _ten_client(root, name, ns, calls):
    doc = {"clients": {}}
    for target, path, method, pol, fanout in calls:
        n = pol.native
        entry = {
            "url": f"http://{dns(target, ns_of(target))}:{PORT[stack_of(target)]}{path}",
            "method": method,
            "stop_after_attempt": n["stop_after_attempt"],
            "wait_fixed": n["wait_fixed_ms"] / 1000,
            "retry_on_status": n["retry_on_status"],
            "retry_on_timeout": bool(n.get("retry_timeout")),
            "request_timeout": (n["read_timeout_ms"] or 0) / 1000,
        }
        doc["clients"][target] = entry
    w(root, f"services/{name}/retry_policy.json", json.dumps(doc, indent=2) + "\n")
    w(root, f"services/{name}/requirements.txt", "tenacity==9.0.0\nrequests==2.32.3\n")
    w(root, f"services/{name}/client.py", f'''"""Outbound HTTP for {name}, wrapped with tenacity.

The numbers come straight out of retry_policy.json:
stop=stop_after_attempt(spec["stop_after_attempt"]), wait=wait_fixed(spec["wait_fixed"]),
and the request itself uses requests.request(..., timeout=spec["request_timeout"]).
"""

import json
import pathlib

import requests
from tenacity import (
    retry, retry_if_exception_type, retry_if_result, stop_after_attempt, wait_fixed,
)

_CFG = json.loads((pathlib.Path(__file__).parent / "retry_policy.json").read_text())


def _build(spec):
    predicate = retry_if_result(lambda r: r.status_code in spec["retry_on_status"])
    if spec["retry_on_timeout"]:
        predicate = predicate | retry_if_exception_type(requests.exceptions.Timeout)
    return retry(
        stop=stop_after_attempt(spec["stop_after_attempt"]),
        wait=wait_fixed(spec["wait_fixed"]),
        retry=predicate,
        reraise=True,
    )


def call(upstream: str, body=None):
    spec = _CFG["clients"][upstream]

    @_build(spec)
    def _once():
        return requests.request(
            spec["method"], spec["url"], json=body, timeout=spec["request_timeout"],
        )

    return _once()
''')


def _polly_client(root, name, ns, calls):
    doc = {"Clients": {}}
    for target, path, method, pol, fanout in calls:
        n = pol.native
        doc["Clients"][target] = {
            "BaseAddress": f"http://{dns(target, ns_of(target))}:{PORT[stack_of(target)]}",
            "Path": path,
            "Method": method,
            "RetryCount": n["retryCount"],
            "SleepDurations": [f"{v}ms" for v in n["sleep_ms"]],
            "HandleStatusCodes": n["handleStatuses"],
            "HandleTimeout": bool(n.get("retry_timeout")),
            "HttpClientTimeout": f"{n['http_client_timeout_ms']}ms" if n.get("http_client_timeout_ms") else None,
        }
    w(root, f"services/{name}/appsettings.Resilience.json", json.dumps(doc, indent=2) + "\n")
    w(root, f"services/{name}/Resilience.cs", f"""// Outbound resilience for {name}.
//
// One named HttpClient per upstream. RetryCount and SleepDurations come from
// appsettings.Resilience.json and are handed to Polly's WaitAndRetryAsync, and
// HttpClientTimeout becomes HttpClient.Timeout for that client.

public static class ResilienceSetup
{{
    public static void AddUpstreams(IServiceCollection services, ClientOptions opts)
    {{
        foreach (var (name, c) in opts.Clients)
        {{
            services.AddHttpClient(name, http =>
                {{
                    http.BaseAddress = new Uri(c.BaseAddress);
                    if (c.HttpClientTimeout is not null)
                        http.Timeout = ParseDuration(c.HttpClientTimeout);
                }})
                .AddPolicyHandler(HttpPolicyExtensions
                    .HandleTransientHttpError()
                    .OrResult(r => c.HandleStatusCodes.Contains((int)r.StatusCode))
                    .WaitAndRetryAsync(
                        c.RetryCount,
                        attempt => ParseDuration(c.SleepDurations[attempt - 1])));
        }}
    }}
}}
""")
