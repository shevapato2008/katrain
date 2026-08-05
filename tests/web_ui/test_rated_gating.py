"""Phase 3 + 4a: rated-game analysis gating (anti-cheat) and remote analysis engine.

Rated/ranked games must forbid ALL analysis at the dispatch chokepoint; free games
allow it. The remote analysis engine is additive: analysis_engine() falls back to
the play engine unless engine/remote_url is configured.
"""

import sys

import pytest

sys.modules.pop("katrain.web.interface", None)

import katrain.web.interface as interface_mod  # noqa: E402
from katrain.web.interface import NullEngine, WebKaTrain  # noqa: E402


class RecordingEngine(NullEngine):
    def __init__(self):
        super().__init__()
        self.analysis_calls = 0

    def request_analysis(self, node=None, *args, **kwargs):
        self.analysis_calls += 1
        return None


def _wk():
    wk = WebKaTrain(force_package_config=True, enable_engine=False)
    wk.engine = RecordingEngine()
    return wk


# --- analysis_allowed ---------------------------------------------------------


def test_free_game_allows_analysis():
    wk = _wk()
    wk._do_new_game(size=9, game_type="free")
    assert wk.analysis_allowed is True
    assert wk.get_state()["analysis_allowed"] is True


def test_rated_game_forbids_analysis_flag():
    wk = _wk()
    wk._do_new_game(size=9, game_type="rated")
    assert wk.analysis_allowed is False
    state = wk.get_state()
    assert state["analysis_allowed"] is False and state["game_type"] == "rated"


def test_ranked_game_forbids_analysis_flag():
    wk = _wk()
    wk._do_new_game(size=9, game_type="ranked")
    assert wk.analysis_allowed is False


def test_ai_ladder_ranked_game_forbids_analysis_flag():
    wk = _wk()
    wk._do_new_game(size=9, game_type="ai_ladder_ranked")
    assert wk.analysis_allowed is False
    assert wk.get_state()["analysis_allowed"] is False


# --- dispatch chokepoint ------------------------------------------------------


def test_rated_blocks_analyze_extra_at_dispatch():
    wk = _wk()
    wk._do_new_game(size=9, game_type="rated")
    wk.engine.analysis_calls = 0
    wk("analyze_extra", mode="extra")
    assert wk.engine.analysis_calls == 0  # blocked, engine never queried


def test_free_allows_analyze_extra_at_dispatch():
    wk = _wk()
    wk._do_new_game(size=9, game_type="free")
    # play a move so there's a node to analyze
    wk("play", (2, 2))
    wk.engine.analysis_calls = 0
    wk("analyze_extra", mode="extra")
    assert wk.engine.analysis_calls >= 1


def test_rated_blocks_show_pv():
    wk = _wk()
    wk._do_new_game(size=9, game_type="rated")
    wk("show_pv", "B C3 D4")
    assert wk.preview_pv == []  # _do_show_pv never ran


# --- analysis-revealing toggles ----------------------------------------------


def test_rated_blocks_analysis_toggles():
    wk = _wk()
    wk._do_new_game(size=9, game_type="rated")
    for setting in ("hints", "ownership", "policy", "eval"):
        wk("toggle_ui", setting)
    assert wk.show_hints is False and wk.show_ownership is False and wk.show_policy is False
    assert wk.show_dots is False


def test_rated_still_allows_nonanalysis_toggles():
    wk = _wk()
    wk._do_new_game(size=9, game_type="rated")
    before = wk.show_coordinates
    wk("toggle_ui", "coords")
    assert wk.show_coordinates != before  # coords toggle is not analysis, still works


def test_free_allows_analysis_toggles():
    wk = _wk()
    wk._do_new_game(size=9, game_type="free")
    wk("toggle_ui", "hints")
    assert wk.show_hints is True


# --- remote analysis engine (R6) ---------------------------------------------


def test_analysis_engine_falls_back_to_play_engine_without_remote():
    wk = _wk()
    wk._do_new_game(size=9)
    wk._init_analysis_engine()  # no engine/remote_url configured
    assert wk.analysis_engine() is wk.engine


def test_analysis_engine_uses_remote_when_configured(monkeypatch):
    wk = _wk()
    wk._do_new_game(size=9)

    # Must be a real HTTP engine: _init_analysis_engine keeps the result only when it is a
    # KataGoHttpEngine (create_engine silently falls back to a LOCAL engine on health-check
    # failure, which we discard so analysis never runs on a dead/second subprocess).
    from katrain.core.engine import KataGoHttpEngine

    sentinel = object.__new__(KataGoHttpEngine)
    captured = {}

    def fake_create_engine(katrain, cfg):
        captured["cfg"] = cfg
        return sentinel

    monkeypatch.setattr(interface_mod, "create_engine", fake_create_engine)
    monkeypatch.setattr(wk, "config", lambda key, *a: "http://remote:8000" if key == "engine/remote_url" else {})
    wk._init_analysis_engine()

    assert wk.analysis_engine() is sentinel
    assert captured["cfg"]["http_url"] == "http://remote:8000"
    assert captured["cfg"]["backend"] == "http"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
