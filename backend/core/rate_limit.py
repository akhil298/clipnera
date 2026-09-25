"""Request rate limiting: per-route limits with a global fallback.

Declare a limit on an API by decorating its endpoint::

    @router.post("/login")
    @rate_limit("5/minute")
    async def login(...): ...

Stack decorators to combine windows, e.g. "5/minute" and "50/day".
``RateLimitMiddleware`` enforces them before the request body is read. APIs
that declare no limit fall back to the global ``DEFAULT_RATE``, as do
unknown paths; opt an API out entirely with ``@no_rate_limit``. Non-API routes
(static files, the docs pages) are never limited. Callers are identified by the user id in their bearer
token, or by client IP when there is none.

Limits use GCRA (the generic cell rate algorithm): "5/minute" allows a burst of
5, then one more request every 12 seconds. State is one float per caller and
bucket, held in process memory. The server runs a single uvicorn process; with
several workers each would keep its own counts, and the store would need to
move to Redis.
"""

import math
import re
import time
from dataclasses import dataclass
from typing import Callable, Iterable, TypeVar

from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from starlette.routing import BaseRoute, Match
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from core.exceptions import CustomException
from core.logging_config import get_logger
from core.security import decode_access_token

log = get_logger(__name__)

# Global limit for every API without its own @rate_limit or @no_rate_limit.
DEFAULT_RATE = "300/min"

_UNIT_SECONDS = {
    **dict.fromkeys(("s", "sec", "secs", "second", "seconds"), 1),
    **dict.fromkeys(("m", "min", "mins", "minute", "minutes"), 60),
    **dict.fromkeys(("h", "hr", "hrs", "hour", "hours"), 3600),
    **dict.fromkeys(("d", "day", "days"), 86400),
}
_RATE_RE = re.compile(r"^\s*(\d+)\s*/\s*(\d+)?\s*([a-z]+)\s*$", re.IGNORECASE)
_LIMITS_ATTR = "__rate_limits__"
_SWEEP_INTERVAL_SECONDS = 60.0


@dataclass(frozen=True)
class Rate:
    limit: int
    window: float

    @classmethod
    def parse(cls, value: str) -> "Rate":
        """Parse "<count>/<unit>" or "<count>/<n> <unit>", e.g. "100/min", "20/15 mins", "5/hr".

        Units: s, sec, second; m, min, minute; h, hr, hour; d, day. Plurals work too.
        """
        match = _RATE_RE.match(value)
        unit_seconds = _UNIT_SECONDS.get(match.group(3).lower()) if match else None
        if unit_seconds is None:
            raise ValueError(f"Invalid rate {value!r}; expected e.g. '100/min', '20/15 mins' or '5/hr'")
        count, multiplier, _ = match.groups()
        limit = int(count)
        window = int(multiplier or 1) * unit_seconds
        if limit <= 0 or window <= 0:
            raise ValueError(f"Invalid rate {value!r}; count and window must be positive")
        return cls(limit=limit, window=float(window))

    @property
    def interval(self) -> float:
        return self.window / self.limit


@dataclass(frozen=True)
class Decision:
    allowed: bool
    limit: int
    remaining: int
    retry_after: float


def gcra(tat: float | None, now: float, rate: Rate) -> tuple[float | None, Decision]:
    """One GCRA step. Returns the new theoretical arrival time (None when denied) and the decision."""
    base = max(tat or now, now)
    new_tat = base + rate.interval
    allow_at = new_tat - rate.window
    if now < allow_at:
        return None, Decision(False, rate.limit, 0, allow_at - now)
    remaining = int((rate.window - (new_tat - now)) / rate.interval + 1e-9)
    return new_tat, Decision(True, rate.limit, remaining, 0.0)


@dataclass(frozen=True)
class _Rule:
    bucket: str
    rate: Rate


Endpoint = TypeVar("Endpoint", bound=Callable)


def rate_limit(rate: str, *, bucket: str | None = None) -> Callable[[Endpoint], Endpoint]:
    """Give an API its own limit in place of the global one.

    Each API counts separately. Pass ``bucket`` to share one count across every
    API that uses the same name, e.g. all auth endpoints. The endpoint is
    returned unchanged, so FastAPI still sees its real signature.
    """
    parsed = Rate.parse(rate)

    def decorator(endpoint: Endpoint) -> Endpoint:
        setattr(endpoint, _LIMITS_ATTR, (*getattr(endpoint, _LIMITS_ATTR, ()), (parsed, bucket)))
        return endpoint

    return decorator


def no_rate_limit(endpoint: Endpoint) -> Endpoint:
    """Exempt an API from rate limiting, the global limit included."""
    setattr(endpoint, _LIMITS_ATTR, ())
    return endpoint


class RateLimiter:
    """In-memory GCRA store. ``hit`` never awaits, so each call is atomic on the event loop."""

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._tats: dict[str, float] = {}
        self._next_sweep = 0.0

    def hit(self, identity: str, rules: Iterable[_Rule]) -> Decision:
        """Count one request against every rule. It is counted only if all of them allow it."""
        now = self._clock()
        self._sweep(now)
        updates: dict[str, float] = {}
        tightest: Decision | None = None
        for rule in rules:
            key = f"{rule.bucket}|{rule.rate.limit}/{rule.rate.window:g}|{identity}"
            new_tat, decision = gcra(self._tats.get(key), now, rule.rate)
            if not decision.allowed:
                return decision
            updates[key] = new_tat
            if tightest is None or decision.remaining < tightest.remaining:
                tightest = decision
        self._tats.update(updates)
        return tightest or Decision(True, 0, 0, 0.0)

    def _sweep(self, now: float) -> None:
        # An expired arrival time behaves exactly like a missing one, so drop it.
        if now < self._next_sweep:
            return
        self._next_sweep = now + _SWEEP_INTERVAL_SECONDS
        self._tats = {key: tat for key, tat in self._tats.items() if tat > now}


class RateLimitMiddleware:
    """Applies each API's ``@rate_limit`` rules, or the global default when it has none."""

    def __init__(
        self,
        app: ASGIApp,
        *,
        default_rate: str = DEFAULT_RATE,
        store: RateLimiter | None = None,
    ) -> None:
        self.app = app
        self.default_rule = _Rule("global", Rate.parse(default_rate))
        self.store = store or RateLimiter()
        # Keyed by id(): routes define __eq__ and are unhashable. They live as long as the app.
        self._route_rules: dict[int, tuple[_Rule, ...]] = {}

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        rules = self._rules_for(scope) if scope["type"] == "http" else ()
        if not rules or scope["method"] == "OPTIONS":
            await self.app(scope, receive, send)
            return

        identity = caller_identity(scope)
        decision = self.store.hit(identity, rules)
        if not decision.allowed:
            log.warning(f"Rate limited {scope['method']} {scope['path']} ({identity})")
            await _rate_limited_response(decision)(scope, receive, send)
            return

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                message.setdefault("headers", [])
                message["headers"] = [*message["headers"], *_limit_headers(decision)]
            await send(message)

        await self.app(scope, receive, send_with_headers)

    def _rules_for(self, scope: Scope) -> tuple[_Rule, ...]:
        route = _match_route(scope)
        if route is None:
            return (self.default_rule,)
        rules = self._route_rules.get(id(route))
        if rules is None:
            rules = self._declared_rules(route)
            self._route_rules[id(route)] = rules
        return rules

    def _declared_rules(self, route: BaseRoute) -> tuple[_Rule, ...]:
        if not isinstance(route, APIRoute):
            return ()
        limits = getattr(route.endpoint, _LIMITS_ATTR, None)
        if limits is None:
            return (self.default_rule,)
        return tuple(_Rule(bucket or _route_bucket(route), rate) for rate, bucket in limits)


def caller_identity(scope: Scope) -> str:
    """The authenticated user id when the bearer token is valid, otherwise the client IP."""
    for name, value in scope.get("headers", []):
        if name == b"authorization":
            header = value.decode("latin-1")
            if header.startswith("Bearer "):
                payload = decode_access_token(header[7:])
                if payload and payload.get("sub"):
                    return f"user:{payload['sub']}"
            break
    client = scope.get("client")
    return f"ip:{client[0] if client else 'unknown'}"


def _match_route(scope: Scope) -> BaseRoute | None:
    app = scope.get("app")
    router = getattr(app, "router", None)
    for route in getattr(router, "routes", ()):
        match, _ = route.matches(scope)
        if match == Match.FULL:
            return route
    return None


def _route_bucket(route: APIRoute) -> str:
    return f"{','.join(sorted(route.methods))} {route.path}"


def _limit_headers(decision: Decision) -> list[tuple[bytes, bytes]]:
    return [
        (b"x-ratelimit-limit", str(decision.limit).encode()),
        (b"x-ratelimit-remaining", str(decision.remaining).encode()),
    ]


def _rate_limited_response(decision: Decision) -> JSONResponse:
    error = CustomException(
        message="Too many requests. Please slow down and try again shortly.",
        code="RATE_LIMITED",
        status_code=429,
    )
    response = JSONResponse(status_code=error.status_code, content=error.to_dict())
    response.headers["Retry-After"] = str(math.ceil(decision.retry_after))
    response.raw_headers.extend(_limit_headers(decision))
    return response
