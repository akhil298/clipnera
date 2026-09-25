from __future__ import annotations

import functools

import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.testclient import TestClient

import core.security as security
from core.exceptions import CustomException
from core.middleware import register_middlewares
from core.rate_limit import (
    DEFAULT_RATE,
    Rate,
    RateLimiter,
    RateLimitMiddleware,
    _Rule,
    caller_identity,
    gcra,
    no_rate_limit,
    rate_limit,
)


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def _with_client_ip(app):
    """TestClient always connects as "testclient"; let tests pick the IP via a header."""

    async def wrapper(scope, receive, send):
        if scope["type"] == "http":
            ip = dict(scope["headers"]).get(b"x-test-ip")
            if ip:
                scope["client"] = (ip.decode(), 1234)
        await app(scope, receive, send)

    return wrapper


def _json_error_handler(app: FastAPI) -> None:
    @app.exception_handler(CustomException)
    async def handler(request, exc: CustomException):
        return JSONResponse(status_code=exc.status_code, content=exc.to_dict())


def _build_app(default_rate: str = "3/minute", static_dir: str | None = None, **options) -> tuple[FastAPI, Clock]:
    app = FastAPI()
    if static_dir:
        app.mount("/static", StaticFiles(directory=static_dir), name="static")
    _json_error_handler(app)

    @app.get("/plain")
    async def plain():
        return {"ok": True}

    @app.get("/other")
    async def other():
        return {"ok": True}

    @app.post("/login")
    @rate_limit("2/minute")
    async def login():
        return {"ok": True}

    @app.get("/burst")
    @rate_limit("10/minute")
    async def burst():
        return {"ok": True}

    @app.get("/items/{item_id}")
    @rate_limit("2/minute")
    async def item(item_id: int, q: str | None = None):
        return {"id": item_id, "q": q}

    @app.post("/shared-a")
    @rate_limit("2/minute", bucket="auth")
    async def shared_a():
        return {"ok": True}

    @app.post("/shared-b")
    @rate_limit("2/minute", bucket="auth")
    async def shared_b():
        return {"ok": True}

    @app.get("/stacked")
    @rate_limit("3/minute")
    @rate_limit("4/hour")
    async def stacked():
        return {"ok": True}

    # Decorator above the route decorator works too: FastAPI returns the same function.
    @rate_limit("1/minute")
    @app.get("/outer")
    async def outer():
        return {"ok": True}

    @app.get("/wrapped")
    @rate_limit("1/minute")
    @_passthrough
    async def wrapped(name: str):
        return {"name": name}

    @app.get("/health")
    @no_rate_limit
    async def health():
        return {"status": "ok"}

    clock = Clock()
    app.add_middleware(
        RateLimitMiddleware,
        default_rate=default_rate,
        store=RateLimiter(clock=clock),
        **options,
    )
    return app, clock


def _passthrough(fn):
    @functools.wraps(fn)
    async def inner(*args, **kwargs):
        return await fn(*args, **kwargs)

    return inner


@pytest.fixture
def client_and_clock():
    app, clock = _build_app()
    return TestClient(_with_client_ip(app)), clock


def _statuses(client: TestClient, method: str, path: str, n: int, **kwargs) -> list[int]:
    return [client.request(method, path, **kwargs).status_code for _ in range(n)]


# --- Rate parsing ---------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "limit", "window"),
    [
        ("100/minute", 100, 60),
        ("100/min", 100, 60),
        ("100/mins", 100, 60),
        ("100/m", 100, 60),
        ("5/second", 5, 1),
        ("5/sec", 5, 1),
        ("5/secs", 5, 1),
        ("5/s", 5, 1),
        ("10/hr", 10, 3600),
        ("10/hrs", 10, 3600),
        ("10/h", 10, 3600),
        ("10/2 hrs", 10, 7200),
        ("50/d", 50, 86400),
        ("20/15min", 20, 900),
        ("20/15 mins", 20, 900),
        ("3/30 sec", 3, 30),
        ("7/Min", 7, 60),
        ("10/hours", 10, 3600),
        ("20/15 minutes", 20, 900),
        (" 1 / day ", 1, 86400),
        ("7/MINUTE", 7, 60),
    ],
)
def test_rate_parse(value, limit, window):
    assert Rate.parse(value) == Rate(limit, float(window))


@pytest.mark.parametrize("value", ["", "abc", "10", "10/fortnight", "10/mn", "10/", "0/min", "10/0 mins", "-1/min", "1.5/min"])
def test_rate_parse_rejects_invalid(value):
    with pytest.raises(ValueError):
        Rate.parse(value)


# --- GCRA core ------------------------------------------------------------


def test_gcra_allows_burst_then_denies_with_exact_retry_after():
    rate = Rate.parse("5/minute")
    tat, now = None, 0.0
    remaining = []
    for _ in range(5):
        tat, decision = gcra(tat, now, rate)
        assert decision.allowed
        remaining.append(decision.remaining)
    assert remaining == [4, 3, 2, 1, 0]

    new_tat, decision = gcra(tat, now, rate)
    assert new_tat is None
    assert not decision.allowed
    assert decision.retry_after == pytest.approx(12.0)


def test_gcra_refills_one_request_per_interval():
    rate = Rate.parse("5/minute")
    tat = None
    for _ in range(5):
        tat, _ = gcra(tat, 0.0, rate)

    _, decision = gcra(tat, 11.9, rate)
    assert not decision.allowed
    tat, decision = gcra(tat, 12.0, rate)
    assert decision.allowed and decision.remaining == 0
    _, decision = gcra(tat, 12.0, rate)
    assert not decision.allowed


def test_gcra_full_window_idle_restores_full_burst():
    rate = Rate.parse("3/minute")
    tat = None
    for _ in range(3):
        tat, _ = gcra(tat, 0.0, rate)
    _, decision = gcra(tat, 60.0, rate)
    assert decision.allowed and decision.remaining == 2


# --- Limiter store --------------------------------------------------------


def test_denied_requests_do_not_consume_quota():
    clock = Clock()
    store = RateLimiter(clock=clock)
    rules = [_Rule("b", Rate.parse("1/minute"))]
    assert store.hit("ip:a", rules).allowed
    for _ in range(50):
        assert not store.hit("ip:a", rules).allowed
    clock.now += 60
    assert store.hit("ip:a", rules).allowed


def test_multiple_rules_count_only_when_all_allow():
    clock = Clock()
    store = RateLimiter(clock=clock)
    loose = _Rule("loose", Rate.parse("10/minute"))
    tight = _Rule("tight", Rate.parse("1/minute"))
    assert store.hit("ip:a", [loose, tight]).allowed
    for _ in range(5):
        assert not store.hit("ip:a", [loose, tight]).allowed
    # The denied calls above must not have drained the loose bucket.
    assert store.hit("ip:a", [loose]).remaining == 8


def test_decision_reports_tightest_remaining():
    store = RateLimiter(clock=Clock())
    decision = store.hit("ip:a", [_Rule("x", Rate.parse("10/minute")), _Rule("y", Rate.parse("3/minute"))])
    assert (decision.limit, decision.remaining) == (3, 2)


def test_sweep_drops_expired_entries():
    clock = Clock()
    store = RateLimiter(clock=clock)
    rule = [_Rule("b", Rate.parse("5/minute"))]
    for i in range(100):
        store.hit(f"ip:{i}", rule)
    assert len(store._tats) == 100
    clock.now += 61
    store.hit("ip:new", rule)
    assert list(store._tats) == ["b|5/60|ip:new"]


# --- Caller identity ------------------------------------------------------


def test_identity_prefers_valid_bearer_user(monkeypatch):
    monkeypatch.setattr(security.settings, "SECRET_KEY", "test-secret")
    token = security.create_access_token("user-42")
    scope = {"headers": [(b"authorization", f"Bearer {token}".encode())], "client": ("1.2.3.4", 1)}
    assert caller_identity(scope) == "user:user-42"


@pytest.mark.parametrize(
    "headers",
    [[], [(b"authorization", b"Bearer not-a-jwt")], [(b"authorization", b"Basic abc")]],
)
def test_identity_falls_back_to_ip(monkeypatch, headers):
    monkeypatch.setattr(security.settings, "SECRET_KEY", "test-secret")
    assert caller_identity({"headers": headers, "client": ("1.2.3.4", 1)}) == "ip:1.2.3.4"
    assert caller_identity({"headers": headers, "client": None}) == "ip:unknown"


# --- Middleware: route level vs global ------------------------------------


def test_route_limit_is_enforced_with_429_contract(client_and_clock):
    client, _ = client_and_clock
    first = client.post("/login")
    assert first.status_code == 200
    assert first.headers["x-ratelimit-limit"] == "2"
    assert first.headers["x-ratelimit-remaining"] == "1"
    assert client.post("/login").status_code == 200

    blocked = client.post("/login")
    assert blocked.status_code == 429
    assert blocked.json() == {
        "error": "RATE_LIMITED",
        "message": "Too many requests. Please slow down and try again shortly.",
    }
    assert blocked.headers["retry-after"] == "30"
    assert blocked.headers["x-ratelimit-remaining"] == "0"


def test_route_limit_recovers_after_interval(client_and_clock):
    client, clock = client_and_clock
    assert _statuses(client, "POST", "/login", 3) == [200, 200, 429]
    clock.now += 30
    assert _statuses(client, "POST", "/login", 2) == [200, 429]


def test_routes_without_limit_share_global_bucket(client_and_clock):
    client, _ = client_and_clock
    assert client.get("/plain").status_code == 200
    assert client.get("/other").status_code == 200
    assert client.get("/plain").headers["x-ratelimit-limit"] == "3"
    assert client.get("/other").status_code == 429
    assert client.get("/plain").status_code == 429


def test_route_limit_replaces_global_limit(client_and_clock):
    client, _ = client_and_clock
    # /burst allows 10 even though the global default is 3.
    assert _statuses(client, "GET", "/burst", 10) == [200] * 10
    assert client.get("/burst").status_code == 429
    # ...and none of it counted against the global bucket.
    assert _statuses(client, "GET", "/plain", 3) == [200] * 3


def test_exhausted_global_does_not_block_route_with_own_limit(client_and_clock):
    client, _ = client_and_clock
    _statuses(client, "GET", "/plain", 5)
    assert client.get("/plain").status_code == 429
    assert client.post("/login").status_code == 200


def test_path_params_share_one_route_bucket(client_and_clock):
    client, _ = client_and_clock
    assert client.get("/items/1").status_code == 200
    assert client.get("/items/2").status_code == 200
    assert client.get("/items/3").status_code == 429


def test_named_bucket_is_shared_across_routes(client_and_clock):
    client, _ = client_and_clock
    assert client.post("/shared-a").status_code == 200
    assert client.post("/shared-b").status_code == 200
    assert client.post("/shared-a").status_code == 429
    assert client.post("/shared-b").status_code == 429


def test_stacked_limits_all_apply(client_and_clock):
    client, clock = client_and_clock
    assert _statuses(client, "GET", "/stacked", 4) == [200, 200, 200, 429]
    # The minute window refills, but the hourly one (4/hour) still caps it.
    clock.now += 60
    assert _statuses(client, "GET", "/stacked", 2) == [200, 429]
    clock.now += 900
    assert client.get("/stacked").status_code == 200


def test_decorator_order_does_not_matter(client_and_clock):
    client, _ = client_and_clock
    assert _statuses(client, "GET", "/outer", 2) == [200, 429]


def test_decorator_keeps_endpoint_signature(client_and_clock):
    client, _ = client_and_clock
    assert client.get("/items/7?q=hi").json() == {"id": 7, "q": "hi"}
    assert client.get("/items/abc").status_code == 422
    assert client.get("/wrapped?name=x").json() == {"name": "x"}
    assert client.get("/wrapped?name=x").status_code == 429


def test_decorator_returns_same_function_and_validates_rate():
    async def endpoint():
        return None

    assert rate_limit("5/minute")(endpoint) is endpoint
    with pytest.raises(ValueError):
        rate_limit("lots")


def test_unknown_paths_count_against_global(client_and_clock):
    client, _ = client_and_clock
    assert _statuses(client, "GET", "/nope", 4) == [404, 404, 404, 429]
    assert client.get("/plain").status_code == 429


def test_limits_are_per_caller_ip(client_and_clock):
    client, _ = client_and_clock
    assert _statuses(client, "POST", "/login", 3, headers={"x-test-ip": "10.0.0.1"}) == [200, 200, 429]
    assert client.post("/login", headers={"x-test-ip": "10.0.0.2"}).status_code == 200


def test_limits_are_per_user_even_behind_one_ip(client_and_clock, monkeypatch):
    client, _ = client_and_clock
    monkeypatch.setattr(security.settings, "SECRET_KEY", "test-secret")
    alice = {"Authorization": f"Bearer {security.create_access_token('alice')}"}
    bob = {"Authorization": f"Bearer {security.create_access_token('bob')}"}
    assert _statuses(client, "POST", "/login", 3, headers=alice) == [200, 200, 429]
    assert client.post("/login", headers=bob).status_code == 200
    # Anonymous callers on the same IP are a separate bucket from signed-in users.
    assert client.post("/login").status_code == 200


def test_no_rate_limit_api_is_never_limited(client_and_clock):
    client, _ = client_and_clock
    assert _statuses(client, "GET", "/health", 20) == [200] * 20
    assert "x-ratelimit-limit" not in client.get("/health").headers
    # ...and it does not count against the global bucket either.
    assert _statuses(client, "GET", "/plain", 3) == [200] * 3


def test_preflight_is_never_limited(client_and_clock):
    client, _ = client_and_clock
    assert all(s != 429 for s in _statuses(client, "OPTIONS", "/login", 10))


def test_non_api_routes_are_not_limited(tmp_path):
    (tmp_path / "clip.mp4").write_bytes(b"video")
    app, _ = _build_app(static_dir=str(tmp_path))
    client = TestClient(app)
    assert _statuses(client, "GET", "/static/clip.mp4", 10) == [200] * 10
    assert _statuses(client, "GET", "/openapi.json", 10) == [200] * 10
    assert _statuses(client, "GET", "/docs", 10) == [200] * 10
    assert _statuses(client, "GET", "/plain", 4) == [200, 200, 200, 429]


def test_no_rate_limit_returns_same_function():
    async def endpoint():
        return None

    assert no_rate_limit(endpoint) is endpoint


# --- Real app wiring ------------------------------------------------------


def test_register_middlewares_installs_limiter_inside_cors():
    app = FastAPI()
    register_middlewares(app)
    names = [m.cls.__name__ for m in app.user_middleware]
    assert "RateLimitMiddleware" in names
    # user_middleware is outermost-first; CORS must wrap the limiter so 429s carry CORS headers.
    assert names.index("CORSMiddleware") < names.index("RateLimitMiddleware")


def test_default_rate_is_valid():
    assert Rate.parse(DEFAULT_RATE) == Rate(300, 60.0)


def test_429_response_carries_cors_headers():
    app = FastAPI()
    register_middlewares(app)

    @app.get("/x")
    async def x():
        return {"ok": True}

    client = TestClient(app)
    origin = {"Origin": "http://localhost:3000"}
    allowed = _statuses(client, "GET", "/x", Rate.parse(DEFAULT_RATE).limit, headers=origin)
    assert allowed == [200] * len(allowed)
    blocked = client.get("/x", headers=origin)
    assert blocked.status_code == 429
    assert blocked.headers["access-control-allow-origin"] == "http://localhost:3000"
