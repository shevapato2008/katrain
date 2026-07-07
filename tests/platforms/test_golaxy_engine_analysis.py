"""Tests for the Golaxy in-game analysis tunnels: area/options/judge/variation.

These are siblings of the genmove tunnel (see engine_client.py and
test_golaxy_engine_client.py) -- same auth, same coord encoding, same
MockTransport testing style. Response shapes are the live-captured bodies
from superpowers/tracks/kiosk-play-golaxy/golaxy-protocol.md Section 9.5
(2026-07-07), quoted verbatim in the shape of the JSON literals below.
"""

from __future__ import annotations

import json

import httpx
import pytest

from katrain.web.platforms.golaxy.engine_client import (
    AreaResult,
    AuthExpired,
    Fatal,
    GOLAXY_AREA_URL,
    GOLAXY_JUDGE_URL,
    GOLAXY_OPTIONS_URL,
    GOLAXY_VARIATION_URL,
    GolaxyEngineError,
    JudgeResult,
    OptionsResult,
    QuotaExhausted,
    Retryable,
    VariationResult,
    engine_analysis,
)

TOKEN = "test-access-token-123"

# --- Live-captured success bodies (golaxy-protocol.md Section 9.5) ---------

AREA_BODY = {
    "code": "0",
    "msg": "",
    "data": {"winrate": 0.375, "delta": -2.2, "area": [0.1] * 722},
}

OPTIONS_BODY = {
    "code": "0",
    "msg": "",
    "data": {
        "coord": [60, 59, 320, 41, 72],
        "prob": [0.4, 0.189, 0.144, 0.133, 0.122],
        "winrate": [0.376, 0.377, 0.374, 0.372, 0.374],
        "delta": [-2.1, -2.1, -1.9, -1.8, -2.2],
    },
}

VARIATION_BODY = {
    "code": "0",
    "data": {"winrate": 0.375, "delta": -2.1, "coord": [60, 288, 320, 301, 319, 299, 317, 54, 73, 53, 51]},
}

JUDGE_BODY = {
    "code": "0",
    "data": {"belong": ("U" * 361), "winner": "U", "delta": 0},
}


def make_client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def body_handler(body: dict):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=body)

    return handler


class TestRequestShaping:
    async def test_area_hits_area_path(self):
        seen = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["url"] = request.url
            return httpx.Response(200, json=AREA_BODY)

        client = make_client(handler)
        await engine_analysis(client, kind="area", moves=[288, 300], access_token=TOKEN)
        assert str(seen["url"]).startswith(GOLAXY_AREA_URL)

    async def test_options_hits_options_path(self):
        seen = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["url"] = request.url
            return httpx.Response(200, json=OPTIONS_BODY)

        client = make_client(handler)
        await engine_analysis(client, kind="options", moves=[288, 300], access_token=TOKEN)
        assert str(seen["url"]).startswith(GOLAXY_OPTIONS_URL)

    async def test_judge_hits_judge_path(self):
        seen = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["url"] = request.url
            return httpx.Response(200, json=JUDGE_BODY)

        client = make_client(handler)
        await engine_analysis(client, kind="judge", moves=[288, 300], access_token=TOKEN)
        assert str(seen["url"]).startswith(GOLAXY_JUDGE_URL)

    async def test_variation_hits_variation_path(self):
        seen = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["url"] = request.url
            return httpx.Response(200, json=VARIATION_BODY)

        client = make_client(handler)
        await engine_analysis(client, kind="variation", moves=[288, 300], access_token=TOKEN)
        assert str(seen["url"]).startswith(GOLAXY_VARIATION_URL)

    async def test_level_defaults_to_8888(self):
        seen = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["params"] = request.url.params
            return httpx.Response(200, json=VARIATION_BODY)

        client = make_client(handler)
        await engine_analysis(client, kind="variation", moves=[288, 300], access_token=TOKEN)
        assert seen["params"]["level"] == "8888"

    async def test_moves_csv_join(self):
        seen = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["params"] = request.url.params
            return httpx.Response(200, json=VARIATION_BODY)

        client = make_client(handler)
        await engine_analysis(client, kind="variation", moves=[288, 300, 72], access_token=TOKEN)
        assert seen["params"]["moves"] == "288,300,72"

    async def test_authorization_bearer_header_present(self):
        seen = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["headers"] = request.headers
            return httpx.Response(200, json=VARIATION_BODY)

        client = make_client(handler)
        await engine_analysis(client, kind="variation", moves=[], access_token=TOKEN)
        assert seen["headers"]["Authorization"] == f"bearer {TOKEN}"

    async def test_browser_like_headers_present(self):
        seen = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["headers"] = request.headers
            return httpx.Response(200, json=VARIATION_BODY)

        client = make_client(handler)
        await engine_analysis(client, kind="variation", moves=[], access_token=TOKEN)
        assert seen["headers"]["Origin"] == "https://19x19.com"
        assert "19x19.com" in seen["headers"]["Referer"]
        assert "Mozilla/5.0" in seen["headers"]["User-Agent"]

    async def test_board_size_variants_all_present(self):
        seen = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["params"] = request.url.params
            return httpx.Response(200, json=VARIATION_BODY)

        client = make_client(handler)
        await engine_analysis(client, kind="variation", moves=[], access_token=TOKEN)
        params = seen["params"]
        assert params["board_size"] == "19"
        assert params["boardSize"] == "19"
        assert params["boardsize"] == "19"

    async def test_other_params_present(self):
        seen = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["params"] = request.url.params
            return httpx.Response(200, json=VARIATION_BODY)

        client = make_client(handler)
        await engine_analysis(client, kind="variation", moves=[], access_token=TOKEN)
        params = seen["params"]
        assert params["komi"] == "7.5"
        assert params["rule"] == "chinese"
        assert params["handicap"] == "0"
        assert params["style"] == "555559"
        assert params["org"] == "golaxy_web"
        assert params["context_name"] == "ai_game_player"


class TestSuccessParse:
    async def test_area_success_returns_area_result(self):
        client = make_client(body_handler(AREA_BODY))
        result = await engine_analysis(client, kind="area", moves=[288, 300], access_token=TOKEN)
        assert isinstance(result, AreaResult)
        assert len(result.area) == 722
        assert result.winrate == pytest.approx(0.375)
        assert result.delta == pytest.approx(-2.2)

    async def test_options_success_returns_options_result(self):
        client = make_client(body_handler(OPTIONS_BODY))
        result = await engine_analysis(client, kind="options", moves=[288, 300], access_token=TOKEN)
        assert isinstance(result, OptionsResult)
        assert len(result.coord) == len(result.prob) == len(result.winrate) == len(result.delta) == 5
        assert all(isinstance(c, int) for c in result.coord)
        assert result.coord == [60, 59, 320, 41, 72]

    async def test_variation_success_returns_variation_result(self):
        client = make_client(body_handler(VARIATION_BODY))
        result = await engine_analysis(client, kind="variation", moves=[288, 300], access_token=TOKEN)
        assert isinstance(result, VariationResult)
        assert len(result.coord) == 11
        assert result.winrate == pytest.approx(0.375)
        assert result.delta == pytest.approx(-2.1)

    async def test_judge_success_returns_judge_result(self):
        client = make_client(body_handler(JUDGE_BODY))
        result = await engine_analysis(client, kind="judge", moves=[288, 300], access_token=TOKEN)
        assert isinstance(result, JudgeResult)
        assert len(result.belong) == 361
        assert result.winner == "U"
        assert result.delta == pytest.approx(0)

    async def test_options_data_as_json_string_is_parsed(self):
        body = {"code": "0", "msg": "", "data": json.dumps(OPTIONS_BODY["data"])}

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=body)

        client = make_client(handler)
        result = await engine_analysis(client, kind="options", moves=[288, 300], access_token=TOKEN)
        assert isinstance(result, OptionsResult)
        assert result.coord == [60, 59, 320, 41, 72]

    async def test_variation_data_as_json_string_is_parsed(self):
        body = {"code": "0", "msg": "", "data": json.dumps(VARIATION_BODY["data"])}

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=body)

        client = make_client(handler)
        result = await engine_analysis(client, kind="variation", moves=[288, 300], access_token=TOKEN)
        assert isinstance(result, VariationResult)
        assert len(result.coord) == 11

    async def test_results_are_frozen_dataclasses(self):
        client = make_client(body_handler(AREA_BODY))
        result = await engine_analysis(client, kind="area", moves=[], access_token=TOKEN)
        with pytest.raises(Exception):
            result.winrate = 0.0


class TestErrorTaxonomy:
    async def test_code_7003_raises_quota_exhausted(self):
        body = {"code": "7003", "msg": "item is not sufficient", "data": ""}

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=body)

        client = make_client(handler)
        with pytest.raises(QuotaExhausted):
            await engine_analysis(client, kind="area", moves=[], access_token=TOKEN)

    async def test_quota_exhausted_is_not_auth_or_fatal_or_retryable(self):
        body = {"code": "7003", "msg": "item is not sufficient", "data": ""}

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=body)

        client = make_client(handler)
        try:
            await engine_analysis(client, kind="options", moves=[], access_token=TOKEN)
        except QuotaExhausted as exc:
            assert not isinstance(exc, AuthExpired)
            assert not isinstance(exc, Fatal)
            assert not isinstance(exc, Retryable)
        else:
            pytest.fail("expected QuotaExhausted")

    async def test_quota_exhausted_subclasses_golaxy_engine_error(self):
        assert issubclass(QuotaExhausted, GolaxyEngineError)

    async def test_code_6003_is_auth_expired(self):
        body = {"code": "6003", "msg": "invalid token", "data": None}

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=body)

        client = make_client(handler)
        with pytest.raises(AuthExpired):
            await engine_analysis(client, kind="judge", moves=[], access_token=TOKEN)

    async def test_invalid_token_msg_is_auth_expired(self):
        body = {"code": "9999", "msg": "Invalid Token", "data": None}

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=body)

        client = make_client(handler)
        with pytest.raises(AuthExpired):
            await engine_analysis(client, kind="variation", moves=[], access_token=TOKEN)

    async def test_other_non_zero_code_is_fatal(self):
        body = {"code": "1", "msg": "bad request", "data": None}

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=body)

        client = make_client(handler)
        with pytest.raises(Fatal):
            await engine_analysis(client, kind="area", moves=[], access_token=TOKEN)

    async def test_malformed_area_missing_area_field_is_fatal(self):
        body = {"code": "0", "msg": "", "data": {"winrate": 0.5, "delta": 1.0}}

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=body)

        client = make_client(handler)
        with pytest.raises(Fatal):
            await engine_analysis(client, kind="area", moves=[], access_token=TOKEN)

    async def test_malformed_options_missing_coord_is_fatal(self):
        body = {
            "code": "0",
            "msg": "",
            "data": {"prob": [0.5], "winrate": [0.5], "delta": [1.0]},
        }

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=body)

        client = make_client(handler)
        with pytest.raises(Fatal):
            await engine_analysis(client, kind="options", moves=[], access_token=TOKEN)

    async def test_malformed_variation_missing_coord_is_fatal(self):
        body = {"code": "0", "msg": "", "data": {"winrate": 0.5, "delta": 1.0}}

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=body)

        client = make_client(handler)
        with pytest.raises(Fatal):
            await engine_analysis(client, kind="variation", moves=[], access_token=TOKEN)

    async def test_malformed_judge_missing_belong_is_fatal(self):
        body = {"code": "0", "msg": "", "data": {"winner": "U", "delta": 0}}

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=body)

        client = make_client(handler)
        with pytest.raises(Fatal):
            await engine_analysis(client, kind="judge", moves=[], access_token=TOKEN)

    async def test_http_401_is_auth_expired(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(401, json={"code": "401", "msg": "unauthorized"})

        client = make_client(handler)
        with pytest.raises(AuthExpired):
            await engine_analysis(client, kind="variation", moves=[], access_token=TOKEN)

    async def test_http_429_is_retryable(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(429, json={"code": "429", "msg": "rate limited"})

        client = make_client(handler)
        with pytest.raises(Retryable):
            await engine_analysis(client, kind="variation", moves=[], access_token=TOKEN)

    async def test_timeout_is_retryable(self):
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.TimeoutException("timed out", request=request)

        client = make_client(handler)
        with pytest.raises(Retryable):
            await engine_analysis(client, kind="area", moves=[], access_token=TOKEN)

    async def test_transport_error_is_retryable(self):
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("connection failed", request=request)

        client = make_client(handler)
        with pytest.raises(Retryable):
            await engine_analysis(client, kind="area", moves=[], access_token=TOKEN)

    async def test_http_500_is_fatal(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(500, text="internal server error")

        client = make_client(handler)
        with pytest.raises(Fatal):
            await engine_analysis(client, kind="area", moves=[], access_token=TOKEN)

    async def test_unknown_kind_raises_value_error(self):
        client = make_client(body_handler(VARIATION_BODY))
        with pytest.raises(ValueError):
            await engine_analysis(client, kind="bogus", moves=[], access_token=TOKEN)


class TestMissingOptionalFieldsDoNotBlock:
    """§13 Non-goal: options/variation per-move fields (prob/winrate/delta) are
    best-effort -- missing them must NOT raise, only coord (or, for area/judge,
    their own required fields) is required. See task-13-2 final review finding."""

    async def test_options_missing_prob_winrate_delta_does_not_raise(self):
        body = {"code": "0", "msg": "", "data": {"coord": [60, 59]}}

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=body)

        client = make_client(handler)
        result = await engine_analysis(client, kind="options", moves=[], access_token=TOKEN)
        assert isinstance(result, OptionsResult)
        assert result.coord == [60, 59]
        assert result.prob in ([], None)
        assert result.winrate in ([], None)
        assert result.delta in ([], None)

    async def test_options_missing_coord_is_still_fatal(self):
        body = {"code": "0", "msg": "", "data": {"prob": [0.4], "winrate": [0.1], "delta": [0.0]}}

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=body)

        client = make_client(handler)
        with pytest.raises(Fatal):
            await engine_analysis(client, kind="options", moves=[], access_token=TOKEN)

    async def test_variation_missing_winrate_delta_defaults_to_zero(self):
        body = {"code": "0", "msg": "", "data": {"coord": [60, 288]}}

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=body)

        client = make_client(handler)
        result = await engine_analysis(client, kind="variation", moves=[], access_token=TOKEN)
        assert isinstance(result, VariationResult)
        assert result.coord == [60, 288]
        assert result.winrate == pytest.approx(0.0)
        assert result.delta == pytest.approx(0.0)

    async def test_variation_missing_coord_is_still_fatal(self):
        body = {"code": "0", "msg": "", "data": {"winrate": 0.5, "delta": 1.0}}

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=body)

        client = make_client(handler)
        with pytest.raises(Fatal):
            await engine_analysis(client, kind="variation", moves=[], access_token=TOKEN)
