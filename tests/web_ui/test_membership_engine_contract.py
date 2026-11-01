"""Paid analysis verifies the HTTP result against its frozen model and requested depth."""

import json

import httpx
import pytest

from katrain.cron.clients.katago import KataGoClient


MODEL_SHA = "93bdb63a3bfae4a70db0cb5265287495ecfc10b1ba1cc6814feeba1cdf055871"


def engine_result(*, visits=500, board_size=19):
    return {
        "id": "position-0",
        "turnNumber": 0,
        "isDuringSearch": False,
        "_wrapper": {
            "selected_model": "tf3-b11c768",
            "model_sha256": MODEL_SHA,
            "model_sha256_verified": True,
        },
        "rootInfo": {"visits": visits, "winrate": 0.51, "scoreLead": 0.3},
        "moveInfos": [
            {"move": "D4", "visits": visits - 1, "winrate": 0.52, "scoreLead": 0.5, "prior": 0.2, "pv": ["D4"]}
        ],
        "ownership": [0.0] * (board_size * board_size),
    }


@pytest.fixture
def mock_http_analyze(monkeypatch):
    requests = []
    original_client = httpx.AsyncClient

    async def analyze(result, *, configured_sha="", **kwargs):
        def handler(request):
            requests.append(json.loads(request.content))
            # Keep malformed engine numbers intact so validation sees NaN/Infinity.
            return httpx.Response(200, content=json.dumps(result), headers={"content-type": "application/json"})

        class Client(original_client):
            def __init__(self, **client_kwargs):
                super().__init__(transport=httpx.MockTransport(handler), **client_kwargs)

        monkeypatch.setattr("katrain.cron.clients.katago.httpx.AsyncClient", Client)
        monkeypatch.setattr("katrain.cron.clients.katago.config.KATAGO_EXPECTED_MODEL_SHA256", configured_sha)
        return await KataGoClient(base_url="http://engine.test").analyze("position-0", [], **kwargs)

    return analyze, requests


async def test_configured_model_rejects_500_visits_for_a_2000_visit_request(mock_http_analyze):
    analyze, requests = mock_http_analyze
    with pytest.raises(ValueError, match="depth"):
        await analyze(engine_result(visits=500), configured_sha=MODEL_SHA, max_visits=2000)
    assert requests[0]["maxVisits"] == 2000


@pytest.mark.parametrize("configured_sha", ["", "another-global-model"])
@pytest.mark.parametrize("visits", [500, 2000])
async def test_explicit_paid_model_accepts_requested_depth_without_global_configuration(
    mock_http_analyze, configured_sha, visits
):
    analyze, requests = mock_http_analyze
    result = engine_result(visits=visits)
    assert (
        await analyze(result, configured_sha=configured_sha, expected_model_sha256=MODEL_SHA, max_visits=visits)
        == result
    )
    assert requests[0]["maxVisits"] == visits


async def test_explicit_paid_model_rejects_short_search_without_global_configuration(mock_http_analyze):
    analyze, _ = mock_http_analyze
    with pytest.raises(ValueError, match="depth"):
        await analyze(engine_result(visits=500), expected_model_sha256=MODEL_SHA, max_visits=2000)


@pytest.mark.parametrize(
    "change",
    [
        pytest.param(lambda r: r.update(id="other-request"), id="wrong-request"),
        pytest.param(lambda r: r.update(turnNumber=1), id="wrong-turn"),
        pytest.param(lambda r: r.update(turnNumber=False), id="boolean-turn"),
        pytest.param(lambda r: r.pop("isDuringSearch"), id="missing-final"),
        pytest.param(lambda r: r.update(isDuringSearch=True), id="during-search"),
        pytest.param(lambda r: r["_wrapper"].update(model_sha256="wrong"), id="wrong-sha"),
        pytest.param(lambda r: r["_wrapper"].update(model_sha256_verified=False), id="unverified-sha"),
        pytest.param(lambda r: r["_wrapper"].pop("selected_model"), id="missing-selected-model"),
        pytest.param(lambda r: r["_wrapper"].update(selected_model=True), id="boolean-selected-model"),
        pytest.param(lambda r: r["rootInfo"].update(visits=True), id="boolean-root-visits"),
        pytest.param(lambda r: r["rootInfo"].update(winrate=True), id="boolean-root-winrate"),
        pytest.param(lambda r: r["rootInfo"].update(scoreLead=float("nan")), id="nan-root-score"),
        pytest.param(lambda r: r["rootInfo"].update(winrate=1.1), id="root-winrate-range"),
        pytest.param(lambda r: r.update(moveInfos=[]), id="missing-candidates"),
        pytest.param(lambda r: r["moveInfos"][0].update(move=""), id="empty-candidate-move"),
        pytest.param(lambda r: r["moveInfos"][0].update(move="T20"), id="off-board-candidate"),
        pytest.param(lambda r: r["moveInfos"][0].update(visits=True), id="boolean-candidate-visits"),
        pytest.param(lambda r: r["moveInfos"][0].update(visits=-1), id="negative-candidate-visits"),
        pytest.param(lambda r: r["moveInfos"][0].update(winrate=True), id="boolean-candidate-winrate"),
        pytest.param(lambda r: r["moveInfos"][0].update(scoreLead=float("inf")), id="infinite-candidate-score"),
        pytest.param(lambda r: r["moveInfos"][0].update(prior=float("nan")), id="nan-candidate-prior"),
        pytest.param(lambda r: r["moveInfos"][0].update(prior=-0.1), id="candidate-prior-range"),
        pytest.param(lambda r: r.update(ownership=[0.0] * 360), id="wrong-ownership-area"),
        pytest.param(lambda r: r["ownership"].__setitem__(0, True), id="boolean-ownership"),
        pytest.param(lambda r: r["ownership"].__setitem__(0, float("nan")), id="nan-ownership"),
        pytest.param(lambda r: r["ownership"].__setitem__(0, 1.1), id="ownership-range"),
    ],
)
async def test_explicit_paid_model_rejects_unusable_http_result(mock_http_analyze, change):
    analyze, _ = mock_http_analyze
    result = engine_result()
    change(result)
    with pytest.raises(ValueError):
        await analyze(result, expected_model_sha256=MODEL_SHA, max_visits=500)


async def test_paid_nine_by_nine_board_accepts_81_ownership_values(mock_http_analyze):
    analyze, requests = mock_http_analyze
    result = engine_result(board_size=9)
    assert await analyze(result, expected_model_sha256=MODEL_SHA, max_visits=500, board_size=9) == result
    assert requests[0]["boardXSize"] == requests[0]["boardYSize"] == 9


async def test_paid_nine_by_nine_board_rejects_19_by_19_ownership(mock_http_analyze):
    analyze, _ = mock_http_analyze
    with pytest.raises(ValueError, match="board size"):
        await analyze(engine_result(), expected_model_sha256=MODEL_SHA, max_visits=500, board_size=9)


async def test_legacy_unconfigured_call_remains_compatible(mock_http_analyze):
    analyze, _ = mock_http_analyze
    legacy_result = {"rootInfo": {"visits": 10}, "moveInfos": []}
    assert await analyze(legacy_result, max_visits=500) == legacy_result


async def test_configured_model_uses_the_default_requested_visits(mock_http_analyze, monkeypatch):
    analyze, _ = mock_http_analyze
    monkeypatch.setattr("katrain.cron.clients.katago.config.ANALYSIS_MAX_VISITS", 2000)
    with pytest.raises(ValueError, match="depth"):
        await analyze(engine_result(visits=500), configured_sha=MODEL_SHA)


async def test_legacy_health_check_accepts_200_without_model_configuration(monkeypatch):
    original_client = httpx.AsyncClient

    class Client(original_client):
        def __init__(self, **kwargs):
            super().__init__(transport=httpx.MockTransport(lambda request: httpx.Response(200)), **kwargs)

    monkeypatch.setattr("katrain.cron.clients.katago.httpx.AsyncClient", Client)
    monkeypatch.setattr("katrain.cron.clients.katago.config.KATAGO_EXPECTED_MODEL_SHA256", "")
    assert await KataGoClient(base_url="http://engine.test").health_check()
