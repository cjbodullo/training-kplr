"""Estate model and the request-composition engine that defines ground truth.

The engine is deliberately small and explicit. It is the *meaning* of the shipped
configuration, not a parser: `estate.py` builds the model, `render.py` writes it out in
eight real config dialects, and `solution/` parses those files back and runs an
independent implementation of the same rules. The two must agree on every scenario.

Modelling conventions (these are stated in the shipped platform note, so the agent has
them too):

  * healthy processing time is treated as zero; only per-try timeouts and retry backoff
    contribute to elapsed time.
  * a failing dependency either answers immediately with an HTTP status ("fast" mode) or
    never answers at all ("hang" mode).
  * every retry layer is cold: no token bucket, budget or breaker has any state.
  * retry backoff uses the configured maximum interval for the attempt.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

INF = 10 ** 9

# statuses the engine moves around. "timeout" is internal: it means "no answer yet".
OK = "200"
GATEWAY_TIMEOUT = "504"
NO_ANSWER = "timeout"


@dataclass
class Layer:
    """One retry/timeout layer in front of one call.

    `attempts` is the normalised TOTAL number of requests this layer is willing to put on
    the wire, including the first one. The dialects disagree about how to spell that and
    render.py keeps each dialect's own spelling.
    """

    site: str  # "app" or "mesh"
    dialect: str
    attempts: int
    per_try_ms: Optional[int]
    overall_ms: Optional[int]
    backoff_ms: List[int]  # delay before attempt 2, 3, ... (last value repeats)
    retry_on: frozenset  # statuses that make this layer try again
    propagates: bool  # does it pass its remaining budget downstream
    hedge_delay_ms: Optional[int] = None  # set => hedging, not sequential retry

    def backoff_before(self, attempt_index: int) -> int:
        """Delay before attempt number `attempt_index` (1-based; 1 has no delay)."""
        if attempt_index <= 1 or not self.backoff_ms:
            return 0
        i = min(attempt_index - 2, len(self.backoff_ms) - 1)
        return self.backoff_ms[i]


@dataclass
class Call:
    """An outbound dependency of a service."""

    target: str
    layers: List[Layer]  # outermost first: application client, then egress mesh proxy
    fanout: int = 1  # identical requests issued for one inbound request
    label: str = ""  # route label; on an edge router this is the public route
    path: str = ""  # request path, decides which mesh route rule applies
    method: str = "GET"


@dataclass
class Service:
    name: str
    namespace: str
    stack: str
    calls: List[Call] = field(default_factory=list)
    parallel: bool = False  # sequential (abort on first failure) vs parallel fan-out
    service_dns: str = ""  # kubernetes Service name, may differ from the workload name
    router: bool = False  # an edge proxy: serves one route per inbound request


@dataclass
class Scenario:
    key: str
    entry: str
    failing: str
    route: str  # which route of the entry proxy the client calls
    mode: str  # "fast" or "hang"
    status: str  # status the failing service answers with, when mode == "fast"
    client_deadline_ms: int


class Engine:
    def __init__(self, services: Dict[str, Service]):
        self.services = services

    # ------------------------------------------------------------------ public

    def evaluate(self, sc: Scenario) -> dict:
        counts: Dict[str, int] = {}
        self._sc = sc
        elapsed, status = self._enter(sc, counts)
        if elapsed >= sc.client_deadline_ms:
            elapsed = sc.client_deadline_ms
            outcome = "client_timeout"
        else:
            outcome = status
        return {
            "requests": dict(sorted(counts.items())),
            "elapsed_ms": int(elapsed),
            "client_outcome": outcome,
        }

    # ----------------------------------------------------------------- internal

    def _enter(self, sc: Scenario, counts) -> tuple:
        """The synthetic client: one attempt, no retries, a hard deadline."""
        elapsed, status = self._service(sc.entry, sc.client_deadline_ms, counts)
        if elapsed >= sc.client_deadline_ms:
            return sc.client_deadline_ms, NO_ANSWER
        return elapsed, status

    def _service(self, name: str, budget: int, counts) -> tuple:
        counts[name] = counts.get(name, 0) + 1
        svc = self.services[name]
        sc = self._sc

        if name == sc.failing:
            if sc.mode == "hang":
                return budget, NO_ANSWER
            return 0, sc.status

        if not svc.calls:
            return 0, OK

        if svc.router:
            chosen = [c for c in svc.calls if c.label == sc.route]
            if len(chosen) != 1:
                raise KeyError(f"{name} has no single route {sc.route!r}")
            return self._call(chosen[0], budget, counts)

        if svc.parallel:
            worst = 0
            bad = None
            for call in svc.calls:
                for _ in range(call.fanout):
                    e, st = self._call(call, budget, counts)
                    worst = max(worst, e)
                    if st != OK and bad is None:
                        bad = st
            return worst, (bad if bad is not None else OK)

        elapsed = 0
        for call in svc.calls:
            for _ in range(call.fanout):
                e, st = self._call(call, max(0, budget - elapsed), counts)
                elapsed += e
                if st != OK:
                    return elapsed, st
        return elapsed, OK

    def _call(self, call: Call, budget: int, counts) -> tuple:
        inner: Callable[[int], tuple] = lambda b: self._service(call.target, b, counts)
        for layer in reversed(call.layers):
            inner = self._wrap(layer, inner)
        return inner(budget)

    def _wrap(self, layer: Layer, inner: Callable[[int], tuple]) -> Callable[[int], tuple]:
        def run(budget: int) -> tuple:
            deadline = budget if budget is not None else INF
            if layer.overall_ms is not None:
                deadline = min(deadline, layer.overall_ms)

            if layer.hedge_delay_ms is not None:
                return self._hedge(layer, inner, deadline)

            elapsed = 0
            status = OK
            for attempt in range(1, layer.attempts + 1):
                wait = layer.backoff_before(attempt)
                if wait:
                    if elapsed + wait >= deadline:
                        return deadline, GATEWAY_TIMEOUT
                    elapsed += wait
                remaining = deadline - elapsed
                if remaining <= 0:
                    return deadline, GATEWAY_TIMEOUT
                try_budget = remaining
                if layer.per_try_ms is not None:
                    try_budget = min(try_budget, layer.per_try_ms)
                inner_budget = try_budget if layer.propagates else INF
                e, status = inner(inner_budget)
                if e >= try_budget or status == NO_ANSWER:
                    # this attempt ran out of time as far as this layer is concerned
                    elapsed += try_budget
                    status = GATEWAY_TIMEOUT
                else:
                    elapsed += e
                if status == OK:
                    return elapsed, OK
                if status not in layer.retry_on:
                    return elapsed, status
                if elapsed >= deadline:
                    return deadline, status
            return elapsed, status

        return run

    def _hedge(self, layer: Layer, inner: Callable[[int], tuple], deadline: int) -> tuple:
        """gRPC style hedging: attempt i goes out at (i-1)*hedgingDelay, or straight away
        if the previous attempt has already come back with a retryable status."""
        delay = layer.hedge_delay_ms or 0
        sent = 0
        clock = 0  # when the attempt about to be sent leaves
        finish = 0  # when the last attempt came back
        status = OK
        while sent < layer.attempts:
            if clock >= deadline:
                break
            sent += 1
            remaining = deadline - clock
            try_budget = remaining
            if layer.per_try_ms is not None:
                try_budget = min(try_budget, layer.per_try_ms)
            inner_budget = try_budget if layer.propagates else INF
            e, status = inner(inner_budget)
            if e >= try_budget or status == NO_ANSWER:
                e = try_budget
                status = GATEWAY_TIMEOUT
            finish = clock + e
            if status == OK:
                return finish, OK
            if status not in layer.retry_on:
                return finish, status
            # the next hedge leaves on its timer, or straight away if this one is back
            clock = clock + min(delay, e)
        return min(max(finish, clock), deadline), (status if status != OK else GATEWAY_TIMEOUT)
