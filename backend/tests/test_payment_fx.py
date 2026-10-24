from __future__ import annotations

from types import SimpleNamespace

import httpx
import pytest

import payment.fx as fx


class _Client:
    def __init__(self, handler):
        self._handler = handler

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def get(self, url):
        return self._handler(url)


@pytest.fixture(autouse=True)
def fresh(monkeypatch):
    monkeypatch.setattr(fx, "_cached", None)
    monkeypatch.setattr(fx, "get_settings", lambda: SimpleNamespace(USD_INR_FALLBACK_RATE=90.0))


def _serve(monkeypatch, handler):
    calls = []

    def counted(url):
        calls.append(url)
        return handler(url)

    monkeypatch.setattr(fx.httpx, "AsyncClient", lambda **kw: _Client(counted))
    return calls


def _rate(value):
    return lambda url: httpx.Response(200, json={"rates": {"INR": value}}, request=httpx.Request("GET", url))


def _down(url):
    raise httpx.ConnectError("down")


def test_to_inr_rounds_up_to_whole_rupees():
    assert fx.to_inr(30, 94.94) == 2849
    assert fx.to_inr(5, 95.0) == 475


@pytest.mark.asyncio
async def test_rate_is_fetched_once_then_cached(monkeypatch):
    calls = _serve(monkeypatch, _rate(94.94))
    assert await fx.usd_inr_rate() == 94.94
    assert await fx.usd_inr_rate() == 94.94
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_unreachable_source_falls_back_to_the_setting(monkeypatch):
    _serve(monkeypatch, _down)
    assert await fx.usd_inr_rate() == 90.0


@pytest.mark.asyncio
async def test_unreachable_source_keeps_the_last_good_rate(monkeypatch):
    _serve(monkeypatch, _rate(94.94))
    await fx.usd_inr_rate()
    monkeypatch.setattr(fx, "_cached", (94.94, 0.0))  # expired
    _serve(monkeypatch, _down)
    assert await fx.usd_inr_rate() == 94.94
