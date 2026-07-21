import threading
from copy import deepcopy
from types import MappingProxyType
from unittest.mock import MagicMock, patch

import pytest
import requests

from katrain.core.base_katrain import KaTrainBase
from katrain.core.engine import BaseEngine, KataGoEngine, KataGoHttpEngine, create_engine
from katrain.core.game import BaseGame
from katrain.core.sgf_parser import Move


def _capabilities():
    return {
        "capability_schema": 1,
        "katago_version": "KataGo v1.16.3",
        "default_model": "b28",
        "models": {
            alias: {
                "running": True,
                "model_path": f"/models/{alias}.bin.gz",
                "model_sha256": alias + "-sha256",
                "model_sha256_verified": True,
                "has_human_model": True,
                "human_model_path": "/models/human.bin.gz",
                "human_model_sha256": "human-sha256",
                "human_model_sha256_verified": True,
            }
            for alias in ("b18", "b28")
        },
    }


class _NoStartHttpEngine(KataGoHttpEngine):
    def start(self):
        pass


class _NoStartNativeEngine(KataGoEngine):
    def start(self):
        pass


def _engine_config(katrain):
    config = dict(katrain.config("engine"))
    config["backend"] = "http"
    config["http_url"] = "http://127.0.0.1:8000"
    return config


def _http_engine(capabilities=None):
    katrain = KaTrainBase(force_package_config=True, debug_level=0)
    return _NoStartHttpEngine(katrain, _engine_config(katrain), capabilities=capabilities or _capabilities())


def _native_engine():
    katrain = KaTrainBase(force_package_config=True, debug_level=0)
    config = _engine_config(katrain)
    config["altcommand"] = "katago analysis"
    return _NoStartNativeEngine(katrain, config)


def _analysis_node(katrain):
    game = BaseGame(katrain, bypass_config=True)
    game.play(Move.from_gtp("D4", player="B"))
    return game.play(Move.from_gtp("Q4", player="W"))


def test_ladder_extra_settings_routes_http_model_without_mutating_input():
    engine = _http_engine()
    native_settings = {"humanSLProfile": "rank_9d", "nested": {"values": [1]}}
    original = deepcopy(native_settings)

    routed = engine.ladder_extra_settings(native_settings, "b18")

    assert routed == {**original, "model": "b18"}
    assert native_settings == original
    assert routed is not native_settings


@pytest.mark.parametrize("main_model", ["b18", "", 0, False])
def test_base_and_native_reject_every_explicit_model_selector(main_model):
    base = object.__new__(BaseEngine)
    native = _native_engine()

    for engine in (base, native):
        with pytest.raises(ValueError, match="per-query model"):
            engine.ladder_extra_settings({}, main_model)
        with pytest.raises(ValueError, match="per-query model"):
            engine.require_ladder_capability(main_model, human_required=False)
        assert engine.ladder_extra_settings({"humanSLProfile": "rank_5d"}, None) == {"humanSLProfile": "rank_5d"}


def test_native_builder_rejects_model_even_when_ladder_helper_is_bypassed():
    engine = _native_engine()
    node = _analysis_node(engine.katrain)

    with pytest.raises(ValueError, match="per-query model"):
        engine.build_analysis_query(node, extra_settings={"model": "b18"})


def test_http_builder_allows_wrapper_model_selector_without_mutating_input():
    engine = _http_engine()
    node = _analysis_node(engine.katrain)
    settings = {"model": "b18", "humanSLProfile": "rank_9d"}

    query, _ = engine.build_analysis_query(node, extra_settings=settings)

    assert query["overrideSettings"]["model"] == "b18"
    assert settings == {"model": "b18", "humanSLProfile": "rank_9d"}


def test_http_capability_snapshot_is_normalized_deep_copied_and_immutable():
    capabilities = _capabilities()
    engine = _http_engine(capabilities)
    capabilities["models"]["b18"]["model_path"] = "/tampered"

    assert engine.capabilities["models"]["b18"]["model_path"] == "/models/b18.bin.gz"
    assert isinstance(engine.capabilities, MappingProxyType)
    with pytest.raises(TypeError):
        engine.capabilities["default_model"] = "b18"
    with pytest.raises(TypeError):
        engine.capabilities["models"]["b18"]["running"] = False


@pytest.mark.parametrize("alias", ["b18", "b28"])
def test_require_ladder_capability_accepts_valid_models(alias):
    identity = _http_engine().require_ladder_capability(alias, human_required=True)

    assert identity["selected_model"] == alias
    assert identity["model_path"] == f"/models/{alias}.bin.gz"
    assert identity["model_sha256"] == alias + "-sha256"
    assert identity["human_model_sha256"] == "human-sha256"
    assert identity["katago_version"] == "KataGo v1.16.3"


def test_require_ladder_capability_uses_default_model_for_none():
    identity = _http_engine().require_ladder_capability(None, human_required=False)
    assert identity["selected_model"] == "b28"


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda data: data["models"].pop("b18"), "b18"),
        (lambda data: data["models"]["b18"].update(running=False), "not running"),
        (lambda data: data["models"]["b18"].update(model_path=""), "identity"),
        (lambda data: data["models"]["b18"].update(model_sha256=""), "identity"),
        (lambda data: data["models"]["b18"].update(model_sha256_verified=False), "verified"),
        (lambda data: data["models"]["b18"].update(human_model_path=""), "human model"),
        (lambda data: data["models"]["b18"].update(human_model_sha256=""), "human model"),
        (lambda data: data["models"]["b18"].update(human_model_sha256_verified=False), "human model"),
    ],
)
def test_require_ladder_capability_rejects_uncertified_model(mutate, message):
    capabilities = _capabilities()
    mutate(capabilities)
    engine = _http_engine(capabilities)

    with pytest.raises(ValueError, match=message):
        engine.require_ladder_capability("b18", human_required=True)


def test_certified_capability_never_trusts_legacy_human_flag():
    capabilities = _capabilities()
    capabilities["has_human_model"] = True
    capabilities["models"]["b18"].update(
        has_human_model=False,
        human_model_path=None,
        human_model_sha256=None,
        human_model_sha256_verified=False,
    )
    engine = _http_engine(capabilities)
    engine.has_human_model = True

    with pytest.raises(ValueError, match="human model"):
        engine.require_ladder_capability("b18", human_required=True)


def test_native_ladder_capability_rejects_alias_and_requires_human_model():
    engine = _native_engine()
    with pytest.raises(ValueError, match="per-query model"):
        engine.require_ladder_capability("b18", human_required=False)
    with pytest.raises(ValueError, match="human model"):
        engine.require_ladder_capability(None, human_required=True)

    engine.has_human_model = True
    assert engine.require_ladder_capability(None, human_required=True) is None


def test_create_engine_parses_schema_one_health_and_derives_default_human_support():
    katrain = KaTrainBase(force_package_config=True, debug_level=0)
    config = _engine_config(katrain)
    response = MagicMock()
    response.json.return_value = _capabilities()

    with (
        patch("katrain.core.engine.requests.get", return_value=response),
        patch.object(KataGoHttpEngine, "start", lambda self: None),
    ):
        engine = create_engine(katrain, config)

    response.raise_for_status.assert_called_once_with()
    assert isinstance(engine, KataGoHttpEngine)
    assert engine.capabilities["default_model"] == "b28"
    assert engine.has_human_model is True


def test_create_engine_uses_config_human_fallback_only_for_legacy_health():
    katrain = KaTrainBase(force_package_config=True, debug_level=0)
    config = _engine_config(katrain)
    config["http_has_human_model"] = True
    response = MagicMock()
    response.json.return_value = {"status": "ok"}

    with (
        patch("katrain.core.engine.requests.get", return_value=response),
        patch.object(KataGoHttpEngine, "start", lambda self: None),
    ):
        engine = create_engine(katrain, config)

    assert isinstance(engine, KataGoHttpEngine)
    assert engine.has_human_model is True
    with pytest.raises(ValueError, match="certified"):
        engine.require_ladder_capability(None, human_required=False)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda data: data.update(capability_schema=2),
        lambda data: data.update(katago_version=""),
        lambda data: data.update(default_model=""),
        lambda data: data.update(models={}),
        lambda data: data["models"]["b18"].update(model_sha256_verified=False),
    ],
)
def test_create_engine_rejects_malformed_certified_health(mutate):
    katrain = KaTrainBase(force_package_config=True, debug_level=0)
    config = _engine_config(katrain)
    capabilities = _capabilities()
    mutate(capabilities)
    response = MagicMock()
    response.json.return_value = capabilities
    local = object()

    with (
        patch("katrain.core.engine.requests.get", return_value=response),
        patch("katrain.core.engine.KataGoEngine", return_value=local),
    ):
        assert create_engine(katrain, config) is local


def test_create_engine_calls_raise_for_status_before_using_health_body():
    katrain = KaTrainBase(force_package_config=True, debug_level=0)
    config = _engine_config(katrain)
    response = MagicMock()
    response.raise_for_status.side_effect = requests.HTTPError("503 unavailable")
    local = object()

    with (
        patch("katrain.core.engine.requests.get", return_value=response),
        patch("katrain.core.engine.KataGoEngine", return_value=local),
    ):
        assert create_engine(katrain, config) is local

    response.json.assert_not_called()


def test_http_engine_request_payload():
    katrain = KaTrainBase(force_package_config=True, debug_level=0)
    config = dict(katrain.config("engine"))
    config["backend"] = "http"
    config["http_url"] = "http://127.0.0.1:8000"
    engine = KataGoHttpEngine(katrain, config)
    try:
        game = BaseGame(katrain, bypass_config=True)
        game.play(Move.from_gtp("D4", player="B"))
        node = game.play(Move.from_gtp("Q4", player="W"))

        seen = {}
        done = threading.Event()

        def fake_post_json(payload):
            seen["payload"] = payload
            board_squares = payload["boardXSize"] * payload["boardYSize"]
            return {
                "id": payload["id"],
                "moveInfos": [{"move": "D4", "order": 0, "visits": 10, "winrate": 0.5, "scoreLead": 0.0, "pv": ["D4"]}],
                "rootInfo": {"visits": 10, "winrate": 0.5, "scoreLead": 0.0},
                "ownership": [0.0] * board_squares,
                "policy": [1.0 / (board_squares + 1)] * (board_squares + 1),
            }

        engine._post_json = fake_post_json

        def callback(result, partial_result):
            seen["result"] = result
            seen["partial"] = partial_result
            done.set()

        engine.request_analysis(node, callback)
        assert done.wait(2)

        payload = seen["payload"]
        assert payload["moves"] == [["B", "D4"], ["W", "Q4"]]
        assert payload["initialStones"] == []
        assert payload["rules"] == "japanese"
        assert payload["boardXSize"] == 19
        assert payload["overrideSettings"]["reportAnalysisWinratesAs"] == "BLACK"
        assert seen["result"]["id"] == payload["id"]
        assert node.analysis_visits_requested == config["max_visits"]
        assert seen["partial"] is False
    finally:
        engine.shutdown(finish=False)
