"""Tests for the Golaxy remaining-道具 counts client: GET /items/{username}.

Powers the 领地N/支招N/变化图N button badges. Source-derived from app.js
`userToolGet`; see golaxy-protocol.md Section 9.4a. Same MockTransport style
as test_golaxy_engine_client.py / test_golaxy_engine_analysis.py -- no respx,
no network.
"""

from __future__ import annotations

import httpx
import pytest

from katrain.web.platforms.golaxy.engine_client import (
    GOLAXY_ITEMS_URL,
    ITEMS_TIMEOUT_SECONDS,
    AuthExpired,
    Fatal,
    ItemCountsResult,
    Retryable,
    fetch_item_counts,
)

TOKEN = "test-access-token-123"
USERNAME = "0086-13116158612"

# data with the three counts as top-level ints (the common case).
COUNTS_BODY = {"code": "0", "msg": "", "data": {"area": 396, "options": 398, "variation": 3}}


def make_client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def body_handler(body):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=body)

    return handler


class TestRequestShaping:
    async def test_hits_items_path_with_username(self):
        seen = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["url"] = request.url
            return httpx.Response(200, json=COUNTS_BODY)

        client = make_client(handler)
        await fetch_item_counts(client, username=USERNAME, access_token=TOKEN)
        assert str(seen["url"]) == GOLAXY_ITEMS_URL + USERNAME

    async def test_username_is_url_encoded(self):
        seen = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["url"] = request.url
            return httpx.Response(200, json=COUNTS_BODY)

        client = make_client(handler)
        # A '+' in the raw username must not be sent literally (it would decode
        # to a space server-side); urllib.parse.quote(safe="") encodes it.
        await fetch_item_counts(client, username="0086-1/2+3", access_token=TOKEN)
        assert "0086-1%2F2%2B3" in str(seen["url"])

    async def test_authorization_bearer_header_present(self):
        seen = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["headers"] = request.headers
            return httpx.Response(200, json=COUNTS_BODY)

        client = make_client(handler)
        await fetch_item_counts(client, username=USERNAME, access_token=TOKEN)
        assert seen["headers"]["Authorization"] == f"bearer {TOKEN}"

    async def test_browser_like_headers_present(self):
        seen = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["headers"] = request.headers
            return httpx.Response(200, json=COUNTS_BODY)

        client = make_client(handler)
        await fetch_item_counts(client, username=USERNAME, access_token=TOKEN)
        assert seen["headers"]["Origin"] == "https://19x19.com"
        assert "Referer" in seen["headers"]
        assert "Chrome" in seen["headers"]["User-Agent"]

    async def test_is_a_get_with_no_query(self):
        seen = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["method"] = request.method
            seen["params"] = request.url.params
            return httpx.Response(200, json=COUNTS_BODY)

        client = make_client(handler)
        await fetch_item_counts(client, username=USERNAME, access_token=TOKEN)
        assert seen["method"] == "GET"
        assert len(seen["params"]) == 0

    def test_items_timeout_is_sane(self):
        assert 0 < ITEMS_TIMEOUT_SECONDS <= 60


class TestParsing:
    async def test_int_counts(self):
        client = make_client(body_handler(COUNTS_BODY))
        result = await fetch_item_counts(client, username=USERNAME, access_token=TOKEN)
        assert result == ItemCountsResult(area=396, options=398, variation=3)

    async def test_data_as_json_string_is_parsed(self):
        # The web client's userToolGet does JSON.parse(r.data) when data is a
        # string -- fetch_item_counts must too (via _unwrap_data).
        body = {"code": "0", "data": '{"area": 10, "options": 0, "variation": 7}'}
        client = make_client(body_handler(body))
        result = await fetch_item_counts(client, username=USERNAME, access_token=TOKEN)
        assert result == ItemCountsResult(area=10, options=0, variation=7)

    async def test_numeric_string_counts_are_coerced(self):
        body = {"code": "0", "data": {"area": "396", "options": " 12 ", "variation": "3"}}
        client = make_client(body_handler(body))
        result = await fetch_item_counts(client, username=USERNAME, access_token=TOKEN)
        assert result == ItemCountsResult(area=396, options=12, variation=3)

    async def test_missing_keys_become_none_not_zero(self):
        # A parse gap must surface as "unknown" (None), never as 0 (which the UI
        # would render as 次数不足).
        body = {"code": "0", "data": {"area": 5}}
        client = make_client(body_handler(body))
        result = await fetch_item_counts(client, username=USERNAME, access_token=TOKEN)
        assert result == ItemCountsResult(area=5, options=None, variation=None)

    async def test_non_numeric_values_become_none(self):
        body = {"code": "0", "data": {"area": "lots", "options": None, "variation": [3]}}
        client = make_client(body_handler(body))
        result = await fetch_item_counts(client, username=USERNAME, access_token=TOKEN)
        assert result == ItemCountsResult(area=None, options=None, variation=None)

    async def test_bool_is_not_a_count(self):
        # bool is an int subclass; True/False are never valid counts.
        body = {"code": "0", "data": {"area": True, "options": False, "variation": 2}}
        client = make_client(body_handler(body))
        result = await fetch_item_counts(client, username=USERNAME, access_token=TOKEN)
        assert result == ItemCountsResult(area=None, options=None, variation=2)

    async def test_zero_is_preserved(self):
        body = {"code": "0", "data": {"area": 0, "options": 0, "variation": 0}}
        client = make_client(body_handler(body))
        result = await fetch_item_counts(client, username=USERNAME, access_token=TOKEN)
        assert result == ItemCountsResult(area=0, options=0, variation=0)

    async def test_result_is_frozen(self):
        client = make_client(body_handler(COUNTS_BODY))
        result = await fetch_item_counts(client, username=USERNAME, access_token=TOKEN)
        with pytest.raises(Exception):
            result.area = 1  # type: ignore[misc]


class TestErrors:
    async def test_empty_username_raises_fatal_without_network(self):
        called = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            called["n"] += 1
            return httpx.Response(200, json=COUNTS_BODY)

        client = make_client(handler)
        with pytest.raises(Fatal):
            await fetch_item_counts(client, username="", access_token=TOKEN)
        assert called["n"] == 0  # no request was made

    async def test_http_401_is_auth_expired(self):
        client = make_client(lambda r: httpx.Response(401, json={}))
        with pytest.raises(AuthExpired):
            await fetch_item_counts(client, username=USERNAME, access_token=TOKEN)

    async def test_http_429_is_retryable(self):
        client = make_client(lambda r: httpx.Response(429, json={}))
        with pytest.raises(Retryable):
            await fetch_item_counts(client, username=USERNAME, access_token=TOKEN)

    async def test_http_500_is_fatal(self):
        client = make_client(lambda r: httpx.Response(500, text="boom"))
        with pytest.raises(Fatal):
            await fetch_item_counts(client, username=USERNAME, access_token=TOKEN)

    async def test_code_6003_is_auth_expired(self):
        body = {"code": "6003", "msg": "invalid token", "data": ""}
        client = make_client(body_handler(body))
        with pytest.raises(AuthExpired):
            await fetch_item_counts(client, username=USERNAME, access_token=TOKEN)

    async def test_other_nonzero_code_is_fatal(self):
        body = {"code": "9999", "msg": "nope", "data": ""}
        client = make_client(body_handler(body))
        with pytest.raises(Fatal):
            await fetch_item_counts(client, username=USERNAME, access_token=TOKEN)

    async def test_network_error_is_retryable(self):
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("down")

        client = make_client(handler)
        with pytest.raises(Retryable):
            await fetch_item_counts(client, username=USERNAME, access_token=TOKEN)
