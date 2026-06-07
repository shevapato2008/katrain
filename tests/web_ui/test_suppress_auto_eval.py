"""R1: suppress kiosk (board mode) per-node auto eval during MODE_PLAY.

In board mode the single-threaded local engine must only receive genmove
(PRIORITY_EXTRA_AI_QUERY) queries while playing — no PRIORITY_DEFAULT per-move
eval and no PRIORITY_GAME_ANALYSIS initial/edit/restart scans. Server mode
(galaxy) and research/review modes keep their analysis behaviour unchanged.
"""

import sys
import time

import pytest

# The shared web_ui conftest mocks `katrain.web.interface` as a MagicMock so that
# unrelated tests don't drag in the kivy chain. This suite needs the REAL
# WebKaTrain, so undo that mock here (kivy is still mocked by conftest; fastapi is
# available in the test env). Blast radius is limited to this module.
sys.modules.pop("katrain.web.interface", None)

from katrain.core.constants import (  # noqa: E402
    MODE_ANALYZE,
    MODE_PLAY,
    PRIORITY_DEFAULT,
    PRIORITY_GAME_ANALYSIS,
)
from katrain.web.interface import NullEngine, WebKaTrain  # noqa: E402
import katrain.web.core.config as config_module  # noqa: E402


class RecordingEngine(NullEngine):
    """Engine stub that records the priority of every analysis request."""

    def __init__(self):
        super().__init__()
        self.priorities = []

    def request_analysis(self, node=None, *args, **kwargs):
        self.priorities.append(kwargs.get("priority"))
        return None


@pytest.fixture
def katrain_mode(monkeypatch):
    """Set settings.KATRAIN_MODE for the duration of a test."""

    def _set(mode):
        monkeypatch.setattr(config_module.settings, "KATRAIN_MODE", mode)
        return mode

    return _set


def _make_katrain(mode, katrain_mode):
    katrain_mode(mode)
    wkt = WebKaTrain(force_package_config=True, enable_engine=False)
    wkt.engine = RecordingEngine()
    return wkt


def _settle():
    # let the daemon thread that runs analyze_all_nodes (initial analysis) run
    time.sleep(0.15)


# --- per-move auto eval -------------------------------------------------------


def test_board_mode_suppresses_move_eval(katrain_mode):
    wkt = _make_katrain("board", katrain_mode)
    wkt._do_new_game(size=19)
    _settle()
    wkt.engine.priorities.clear()

    wkt("play", (3, 3))
    _settle()

    assert (
        PRIORITY_DEFAULT not in wkt.engine.priorities
    ), f"board MODE_PLAY must not emit per-move eval, got {wkt.engine.priorities}"


def test_server_mode_keeps_move_eval(katrain_mode):
    wkt = _make_katrain("server", katrain_mode)
    wkt._do_new_game(size=19)
    _settle()
    wkt.engine.priorities.clear()

    wkt("play", (3, 3))
    _settle()

    assert (
        PRIORITY_DEFAULT in wkt.engine.priorities
    ), f"server mode must keep per-move eval (regression), got {wkt.engine.priorities}"


# --- initial analysis ---------------------------------------------------------


def test_board_mode_skips_initial_analysis(katrain_mode):
    wkt = _make_katrain("board", katrain_mode)
    wkt._do_new_game(size=19)
    _settle()

    assert (
        PRIORITY_GAME_ANALYSIS not in wkt.engine.priorities
    ), f"board mode must skip initial analyze_all_nodes, got {wkt.engine.priorities}"


def test_server_mode_runs_initial_analysis(katrain_mode):
    wkt = _make_katrain("server", katrain_mode)
    # move_tree=None path uses skip_initial_analysis=False -> background scan runs.
    # A single empty-root game still analyzes the root node.
    wkt._do_new_game(size=19)
    _settle()

    assert (
        PRIORITY_GAME_ANALYSIS in wkt.engine.priorities
    ), f"server mode must run initial analysis (regression), got {wkt.engine.priorities}"


# --- ponder -------------------------------------------------------------------


def test_board_mode_skips_ponder(katrain_mode):
    wkt = _make_katrain("board", katrain_mode)
    wkt._do_new_game(size=19)
    _settle()
    wkt.engine.priorities.clear()

    wkt.pondering = True
    wkt._do_update_state()
    _settle()

    assert wkt.engine.priorities == [], f"board mode must not ponder, got {wkt.engine.priorities}"


# --- edit game ----------------------------------------------------------------


def test_board_mode_skips_edit_game_analysis(katrain_mode):
    wkt = _make_katrain("board", katrain_mode)
    wkt._do_new_game(size=19, komi=6.5)
    _settle()
    wkt.engine.priorities.clear()

    wkt._do_edit_game(komi=7.5)
    _settle()

    assert (
        wkt.engine.priorities == []
    ), f"board mode edit must not trigger analyze_all_nodes, got {wkt.engine.priorities}"


# --- research / review mode is never suppressed -------------------------------


def test_research_mode_not_suppressed_on_board(katrain_mode):
    wkt = _make_katrain("board", katrain_mode)
    wkt.play_analyze_mode = MODE_ANALYZE
    wkt._do_new_game(size=19)
    _settle()
    wkt.engine.priorities.clear()

    wkt.game.play(__import__("katrain.core.sgf_parser", fromlist=["Move"]).Move((3, 3), player="B"))
    _settle()

    assert (
        PRIORITY_DEFAULT in wkt.engine.priorities
    ), f"research/review mode must keep eval even on board, got {wkt.engine.priorities}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
