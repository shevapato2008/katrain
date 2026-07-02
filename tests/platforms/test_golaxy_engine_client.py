"""Tests for the Golaxy human-vs-AI "genmove" tunnel client.

Uses httpx.MockTransport (built into httpx) to fake the network -- no respx,
no new dependency. See katrain/web/platforms/golaxy/engine_client.py for the
protocol reference (superpowers/tracks/kiosk-play-golaxy/golaxy-protocol.md
Section 2).
"""

from __future__ import annotations

import httpx
import pytest

from katrain.web.platforms.golaxy.engine_client import (
    GENMOVE_TIMEOUT_SECONDS,
    GOLAXY_AI_LEVELS,
    AuthExpired,
    Fatal,
    GenmoveResult,
    GolaxyEngineError,
    Retryable,
    engine_genmove,
    get_level,
    list_levels,
)

TOKEN = "test-access-token-123"


def make_client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def success_handler(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json={"code": "0", "msg": "", "data": {"coord": 286, "prob": 0.187845}})


class TestRequestShaping:
    async def test_hits_genmove_path(self):
        seen = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["url"] = request.url
            return success_handler(request)

        client = make_client(handler)
        await engine_genmove(client, moves=[72, 300, 288], level=1100, access_token=TOKEN)
        assert str(seen["url"]).startswith("https://api.19x19.com/api/engine/dcnn/tunnel/genmove")

    async def test_auth_token_header_present_and_correct(self):
        seen = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["headers"] = request.headers
            return success_handler(request)

        client = make_client(handler)
        await engine_genmove(client, moves=[], level=1100, access_token=TOKEN)
        assert seen["headers"]["Auth_token"] == TOKEN

    async def test_no_standard_authorization_header(self):
        seen = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["headers"] = request.headers
            return success_handler(request)

        client = make_client(handler)
        await engine_genmove(client, moves=[], level=1100, access_token=TOKEN)
        assert "Authorization" not in seen["headers"]

    async def test_query_params_all_present(self):
        seen = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["params"] = request.url.params
            return success_handler(request)

        client = make_client(handler)
        await engine_genmove(client, moves=[72, 300, 288], level=1100, access_token=TOKEN)
        params = seen["params"]
        assert params["moves"] == "72,300,288"
        assert params["board_size"] == "19"
        assert params["boardSize"] == "19"
        assert params["komi"] == "7.5"
        assert params["rule"] == "chinese"
        assert params["handicap"] == "0"
        assert params["level"] == "1100"
        assert params["style"] == "555559"
        assert params["elodiff"] == "0"
        assert params["resign"] == "6"
        assert params["org"] == "golaxy_web"
        assert params["context_name"] == "ai_game_player"

    async def test_moves_empty_list_is_empty_string(self):
        seen = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["params"] = request.url.params
            return success_handler(request)

        client = make_client(handler)
        await engine_genmove(client, moves=[], level=1100, access_token=TOKEN)
        assert seen["params"]["moves"] == ""

    async def test_moves_csv_join(self):
        seen = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["params"] = request.url.params
            return success_handler(request)

        client = make_client(handler)
        await engine_genmove(client, moves=[72, 300, 288], level=1100, access_token=TOKEN)
        assert seen["params"]["moves"] == "72,300,288"


class TestGenmoveTimeout:
    def test_genmove_timeout_is_long_enough_for_strong_bots(self):
        # Strong bots think well past the RestClient's shared 30s default --
        # genmove needs its own long read timeout. Phase 5 calibrates the
        # exact value; this just documents the intent.
        assert GENMOVE_TIMEOUT_SECONDS >= 120


class TestSuccessParse:
    async def test_returns_genmove_result(self):
        client = make_client(success_handler)
        result = await engine_genmove(client, moves=[], level=1100, access_token=TOKEN)
        assert result == GenmoveResult(coord=286, prob=pytest.approx(0.187845))

    async def test_result_is_frozen_dataclass(self):
        client = make_client(success_handler)
        result = await engine_genmove(client, moves=[], level=1100, access_token=TOKEN)
        with pytest.raises(Exception):
            result.coord = 0


class TestErrorTaxonomy:
    async def test_code_not_zero_is_fatal(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"code": "1", "msg": "bad request", "data": None})

        client = make_client(handler)
        with pytest.raises(Fatal):
            await engine_genmove(client, moves=[], level=1100, access_token=TOKEN)

    async def test_missing_coord_is_fatal(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"code": "0", "msg": "", "data": {"prob": 0.5}})

        client = make_client(handler)
        with pytest.raises(Fatal):
            await engine_genmove(client, moves=[], level=1100, access_token=TOKEN)

    async def test_null_coord_is_fatal(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"code": "0", "msg": "", "data": {"coord": None, "prob": 0.5}})

        client = make_client(handler)
        with pytest.raises(Fatal):
            await engine_genmove(client, moves=[], level=1100, access_token=TOKEN)

    async def test_http_401_is_auth_expired(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(401, json={"code": "401", "msg": "unauthorized"})

        client = make_client(handler)
        with pytest.raises(AuthExpired):
            await engine_genmove(client, moves=[], level=1100, access_token=TOKEN)

    async def test_http_429_is_retryable(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(429, json={"code": "429", "msg": "rate limited"})

        client = make_client(handler)
        with pytest.raises(Retryable):
            await engine_genmove(client, moves=[], level=1100, access_token=TOKEN)

    async def test_timeout_is_retryable(self):
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.TimeoutException("timed out", request=request)

        client = make_client(handler)
        with pytest.raises(Retryable):
            await engine_genmove(client, moves=[], level=1100, access_token=TOKEN)

    async def test_transport_error_is_retryable(self):
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("connection failed", request=request)

        client = make_client(handler)
        with pytest.raises(Retryable):
            await engine_genmove(client, moves=[], level=1100, access_token=TOKEN)

    async def test_http_500_is_fatal(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(500, text="internal server error")

        client = make_client(handler)
        with pytest.raises(Fatal):
            await engine_genmove(client, moves=[], level=1100, access_token=TOKEN)

    async def test_all_subclass_golaxy_engine_error(self):
        assert issubclass(AuthExpired, GolaxyEngineError)
        assert issubclass(Retryable, GolaxyEngineError)
        assert issubclass(Fatal, GolaxyEngineError)

    async def test_retryable_chains_cause(self):
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.TimeoutException("timed out", request=request)

        client = make_client(handler)
        try:
            await engine_genmove(client, moves=[], level=1100, access_token=TOKEN)
        except Retryable as exc:
            assert exc.__cause__ is not None
        else:
            pytest.fail("expected Retryable")


class TestLevelTable:
    def test_has_39_entries(self):
        assert len(GOLAXY_AI_LEVELS) == 39

    def test_entries_have_required_keys(self):
        for entry in GOLAXY_AI_LEVELS:
            assert set(entry.keys()) == {"elo_score", "level_name", "name", "goal_difference", "timing"}

    def test_strongest_first(self):
        assert GOLAXY_AI_LEVELS[0]["elo_score"] == 3300
        assert GOLAXY_AI_LEVELS[0]["name"] == "星猛虎"
        assert GOLAXY_AI_LEVELS[-1]["elo_score"] == 220
        assert GOLAXY_AI_LEVELS[-1]["name"] == "星小蚁"

    def test_get_level_1100_is_star_shrimp(self):
        entry = get_level(1100)
        assert entry is not None
        assert entry["name"] == "星铠虾"
        assert entry["level_name"] == "1级"
        assert entry["elo_score"] == 1100

    def test_get_level_unknown_returns_none(self):
        assert get_level(9999) is None

    def test_list_levels_returns_all(self):
        levels = list_levels()
        assert len(levels) == 39

    def test_list_levels_is_a_copy(self):
        levels = list_levels()
        levels.append({"bogus": True})
        assert len(GOLAXY_AI_LEVELS) == 39
