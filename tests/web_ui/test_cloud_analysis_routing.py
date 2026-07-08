"""Wave B #4: route on-demand analysis (领地/图表) to the CLOUD engine, keep 对局 local.

CLOUD_KATAGO_URL (or engine/remote_url) builds a second analysis engine; analyze_current
uses it while genmove keeps game.engines[player]=local. Health-gated: if create_engine's
health check fails and it falls back to a LOCAL engine, we discard it so analysis_engine()
returns the working local PLAY engine — never a second/dead subprocess on the SBC.
"""

import sys
import time

import pytest

# The shared web_ui conftest mocks `katrain.web.interface`; this suite needs the REAL
# WebKaTrain (same pattern as test_suppress_auto_eval.py).
sys.modules.pop("katrain.web.interface", None)

from katrain.core.engine import KataGoEngine, KataGoHttpEngine  # noqa: E402
import katrain.web.interface as interface_mod  # noqa: E402  (patch create_engine on THIS module
from katrain.web.interface import NullEngine, WebKaTrain  # noqa: E402  ref — other web_ui files
import katrain.web.core.config as config_module  # noqa: E402  re-pop interface, so a string target

# would patch a different module instance than the one WebKaTrain came from.


class RecordingEngine(NullEngine):
    """Engine stub recording every analysis request (which engine got the query)."""

    def __init__(self, name="engine"):
        super().__init__()
        self.name = name
        self.priorities = []

    def request_analysis(self, node=None, *args, **kwargs):
        self.priorities.append(kwargs.get("priority"))
        return None


@pytest.fixture
def katrain_mode(monkeypatch):
    def _set(mode):
        monkeypatch.setattr(config_module.settings, "KATRAIN_MODE", mode)
        return mode

    return _set


def _make_katrain(mode, katrain_mode):
    katrain_mode(mode)
    wkt = WebKaTrain(force_package_config=True, enable_engine=False)
    wkt.engine = RecordingEngine("local-play")
    return wkt


def _settle():
    time.sleep(0.15)


# -- analyze_current routing (领地/图表) --------------------------------------------


def test_analyze_current_routes_to_cloud_analysis_engine(katrain_mode):
    wkt = _make_katrain("board", katrain_mode)
    cloud = RecordingEngine("cloud-analysis")
    wkt.analysis_engine_instance = cloud  # simulate a configured, healthy cloud engine
    wkt._do_new_game(size=19)
    _settle()
    wkt.engine.priorities.clear()
    cloud.priorities.clear()

    wkt("analyze_current")
    _settle()

    assert cloud.priorities, "领地/图表 analysis must route to the cloud analysis engine"
    assert wkt.engine.priorities == [], f"analysis leaked to the local play engine: {wkt.engine.priorities}"


def test_analyze_current_falls_back_to_local_without_cloud(katrain_mode):
    wkt = _make_katrain("board", katrain_mode)
    wkt.analysis_engine_instance = None  # no cloud configured
    wkt._do_new_game(size=19)
    _settle()
    wkt.engine.priorities.clear()

    wkt("analyze_current")
    _settle()

    # analysis_engine() falls back to the local play engine -> unchanged behavior.
    assert wkt.engine.priorities, "without a cloud engine, analysis must use the local play engine"


# -- _init_analysis_engine: URL source + health-fallback guard ---------------------


def test_init_builds_cloud_engine_from_cloud_katago_url(katrain_mode, monkeypatch):
    wkt = _make_katrain("board", katrain_mode)
    monkeypatch.setattr(config_module.settings, "CLOUD_KATAGO_URL", "https://api-go.example")
    healthy = object.__new__(KataGoHttpEngine)  # bypass heavy __init__; only isinstance matters
    monkeypatch.setattr(interface_mod, "create_engine", lambda k, c: healthy)

    wkt._init_analysis_engine()

    assert wkt.analysis_engine_instance is healthy
    assert wkt.analysis_engine() is healthy  # analysis routes to cloud


def test_init_discards_local_fallback_when_cloud_unreachable(katrain_mode, monkeypatch):
    wkt = _make_katrain("board", katrain_mode)
    monkeypatch.setattr(config_module.settings, "CLOUD_KATAGO_URL", "https://api-go.example")
    # create_engine's health check failed -> it returns a LOCAL KataGoEngine, not HTTP.
    fallback = object.__new__(KataGoEngine)
    shut = {"called": False}
    fallback.shutdown = lambda finish=False: shut.__setitem__("called", True)
    monkeypatch.setattr(interface_mod, "create_engine", lambda k, c: fallback)

    wkt._init_analysis_engine()

    assert wkt.analysis_engine_instance is None  # local fallback discarded, not retained
    assert shut["called"] is True  # and its (would-be) subprocess shut down
    assert wkt.analysis_engine() is wkt.engine  # analysis uses the working local PLAY engine


def test_init_noop_without_any_remote_url(katrain_mode, monkeypatch):
    wkt = _make_katrain("board", katrain_mode)
    monkeypatch.setattr(config_module.settings, "CLOUD_KATAGO_URL", "")
    called = {"create": False}
    monkeypatch.setattr(
        interface_mod,
        "create_engine",
        lambda k, c: called.__setitem__("create", True) or object.__new__(KataGoHttpEngine),
    )

    wkt._init_analysis_engine()

    assert wkt.analysis_engine_instance is None
    assert called["create"] is False  # no URL -> never even tries to build a remote engine
    assert wkt.analysis_engine() is wkt.engine


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
