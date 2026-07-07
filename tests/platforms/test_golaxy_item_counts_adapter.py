"""Tests for the adapter layer of the remaining-道具 counts feature.

Covers GolaxyRestClient.set_username normalization, the RestClient wrapper
passing the normalized username through to engine_client.fetch_item_counts
(via httpx.MockTransport), and GolaxyAdapter.fetch_item_counts' auth-refresh-
retry discipline (mirrors test_engine_analysis_adapter.py's style: mock at the
RestClient boundary with AsyncMock). asyncio_mode=auto (pyproject.toml).
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import httpx
import pytest

from katrain.web.platforms.golaxy.adapter import GolaxyAdapter, GolaxyRestClient
from katrain.web.platforms.golaxy.engine_client import (
    GOLAXY_ITEMS_URL,
    AuthExpired,
    Fatal,
    ItemCountsResult,
    Retryable,
)

COUNTS_BODY = {"code": "0", "msg": "", "data": {"area": 396, "options": 398, "variation": 3}}


def make_adapter() -> GolaxyAdapter:
    adapter = GolaxyAdapter()
    adapter._rest.set_tokens("tok", "refresh")
    return adapter


def recorder():
    events: list = []

    async def cb(*args):
        events.append(args)

    return events, cb


# --------------------------------------------------------------------------- #
# set_username normalization                                                  #
# --------------------------------------------------------------------------- #


class TestSetUsername:
    def test_bare_phone_gets_0086_prefix(self):
        rest = GolaxyRestClient()
        rest.set_username("13116158612")
        assert rest._username == "0086-13116158612"

    def test_already_prefixed_is_untouched(self):
        rest = GolaxyRestClient()
        rest.set_username("0086-13116158612")
        assert rest._username == "0086-13116158612"

    def test_none_is_noop_and_does_not_clobber(self):
        rest = GolaxyRestClient()
        rest.set_username("13116158612")
        rest.set_username(None)  # a token-only reconnect lacking the phone
        assert rest._username == "0086-13116158612"

    def test_empty_string_is_noop(self):
        rest = GolaxyRestClient()
        rest.set_username("")
        assert rest._username is None


# --------------------------------------------------------------------------- #
# RestClient wrapper -> engine_client (end-to-end URL via MockTransport)       #
# --------------------------------------------------------------------------- #


async def test_rest_fetch_item_counts_uses_normalized_username_end_to_end():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = request.url
        seen["auth"] = request.headers.get("Authorization")
        return httpx.Response(200, json=COUNTS_BODY)

    rest = GolaxyRestClient()
    rest.set_tokens("tok-abc", "refresh")
    rest.set_username("13116158612")  # bare phone -> normalized to 0086-...
    rest._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))

    result = await rest.fetch_item_counts()

    assert str(seen["url"]) == GOLAXY_ITEMS_URL + "0086-13116158612"
    assert seen["auth"] == "bearer tok-abc"
    assert result == ItemCountsResult(area=396, options=398, variation=3)


# --------------------------------------------------------------------------- #
# GolaxyAdapter.fetch_item_counts retry discipline                            #
# --------------------------------------------------------------------------- #


async def test_returns_result_on_success():
    adapter = make_adapter()
    result = ItemCountsResult(area=1, options=2, variation=3)
    adapter._rest.fetch_item_counts = AsyncMock(return_value=result)

    assert await adapter.fetch_item_counts() is result


async def test_fatal_propagates_without_retry():
    adapter = make_adapter()
    mock = AsyncMock(side_effect=Fatal("boom"))
    adapter._rest.fetch_item_counts = mock

    with pytest.raises(Fatal):
        await adapter.fetch_item_counts()
    mock.assert_awaited_once()


async def test_retryable_retries_once_and_returns():
    adapter = make_adapter()
    result = ItemCountsResult(area=5, options=5, variation=5)
    calls = {"n": 0}

    async def side_effect():
        calls["n"] += 1
        if calls["n"] == 1:
            raise Retryable("transient")
        return result

    adapter._rest.fetch_item_counts = AsyncMock(side_effect=side_effect)

    assert await adapter.fetch_item_counts() == result
    assert calls["n"] == 2


async def test_auth_expired_refresh_then_retry():
    adapter = make_adapter()
    adapter._rest.refresh_access_token = AsyncMock(return_value={"access_token": "new"})
    result = ItemCountsResult(area=7, options=None, variation=0)
    calls = {"n": 0}

    async def side_effect():
        calls["n"] += 1
        if calls["n"] == 1:
            raise AuthExpired("expired")
        return result

    adapter._rest.fetch_item_counts = AsyncMock(side_effect=side_effect)
    refreshed, refreshed_cb = recorder()
    adapter.on_token_refreshed(refreshed_cb)

    assert await adapter.fetch_item_counts() == result
    adapter._rest.refresh_access_token.assert_awaited_once()
    assert len(refreshed) == 1
    assert calls["n"] == 2


async def test_auth_expired_twice_emits_and_raises():
    adapter = make_adapter()
    adapter._rest.refresh_access_token = AsyncMock(return_value={})
    adapter._rest.fetch_item_counts = AsyncMock(side_effect=AuthExpired("expired"))
    expired, expired_cb = recorder()
    adapter.on_auth_expired(expired_cb)

    with pytest.raises(AuthExpired):
        await adapter.fetch_item_counts()
    assert len(expired) == 1
    assert adapter._rest.fetch_item_counts.await_count == 2
