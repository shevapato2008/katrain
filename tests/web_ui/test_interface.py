import pytest
import os
import sys

# Ensure katrain package is in path
sys.path.append(os.getcwd())

# The directory conftest intentionally stubs the public module for API tests.
# Load the real implementation under an isolated name for these direct checks.
import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "_reference_real_interface", Path(__file__).parents[2] / "katrain/web/interface.py"
)
_interface = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_interface)
NullEngine, WebKaTrain = _interface.NullEngine, _interface.WebKaTrain


def test_web_katrain_initialization():
    """Test that WebKaTrain can be initialized without Kivy GUI errors."""
    wkt = WebKaTrain(force_package_config=True, enable_engine=False)
    assert wkt.engine is None
    assert wkt.game is None
    assert "B" in wkt.players_info
    assert "W" in wkt.players_info


def test_web_katrain_start_game():
    """Test starting a game and getting the initial state."""
    wkt = WebKaTrain(force_package_config=True, enable_engine=False)
    wkt.start()
    assert wkt.game is not None
    assert isinstance(wkt.engine, NullEngine)
    state = wkt.get_state()
    assert state["board_size"] == [19, 19]
    assert state["is_root"] is True
    assert state["player_to_move"] == "B"


def test_web_katrain_play_move():
    """Test playing a move and verifying the state update."""
    wkt = WebKaTrain(force_package_config=True, enable_engine=False)
    wkt.start()

    # Play a move at (3, 3) - D4
    wkt("play", (3, 3))

    state = wkt.get_state()
    assert state["is_root"] is False
    assert state["last_move"] == [3, 3]
    assert state["player_to_move"] == "W"

    # Verify stone is on board
    stones = state["stones"]
    assert any(s[0] == "B" and s[1] == [3, 3] for s in stones)


def test_web_katrain_undo_redo():
    """Test undo and redo functionality."""
    wkt = WebKaTrain(force_package_config=True, enable_engine=False)
    wkt.start()

    wkt("play", (3, 3))
    assert wkt.get_state()["is_root"] is False

    wkt("undo")
    assert wkt.get_state()["is_root"] is True

    wkt("redo")
    assert wkt.get_state()["is_root"] is False
    assert wkt.get_state()["last_move"] == [3, 3]


if __name__ == "__main__":
    pytest.main([__file__])


def _reference_game():
    from katrain.core.constants import PLAYER_HUMAN

    w = WebKaTrain(force_package_config=True, enable_engine=False)
    w.save_config = lambda *args, **kwargs: None
    w.message_callback = lambda *args, **kwargs: None
    w.start()
    for player in w.players_info.values():
        player.update(player_type=PLAYER_HUMAN)
    return w


def test_reference_collector_captures_real_commit_before_callbacks():
    w = _reference_game()
    parent = w.game.current_node
    receipts = []

    def collect(game, actual_parent, node, board):
        assert w.ai_ladder_commit_lock._is_owned()
        assert game is w.game
        assert actual_parent is parent
        assert node is game.current_node
        assert isinstance(board, tuple) and isinstance(board[0], tuple)
        receipts.append((node, board))

    w("play", (3, 15), guard=True, expected_player="B", _reference_committed=collect)
    assert len(receipts) == 1
    assert receipts[0][1][3][3] == 1
    w._do_play((4, 14), guard=True, expected_player="W")
    assert receipts[0][1][4][4] == 0


@pytest.mark.parametrize("refusal", ["illegal", "minimum_use", "ended"])
def test_reference_collector_never_claims_a_refused_move(refusal):
    from katrain.web.models import EndgameConflict

    w = _reference_game()
    if refusal == "illegal":
        w._do_play((3, 3), guard=True)
    elif refusal == "minimum_use":
        w.timer_paused = False
        w.active_game_timer.update(main_time=0, minimal_use=100)
    else:
        w.game.current_node.end_state = "B+R"
    parent = w.game.current_node
    receipts = []
    if refusal == "ended":
        with pytest.raises(EndgameConflict):
            w._do_play((3, 3), guard=True, _reference_committed=lambda *args: receipts.append(args))
    else:
        w._do_play((3, 3), guard=True, _reference_committed=lambda *args: receipts.append(args))
    assert receipts == []
    assert w.game.current_node is parent


def test_reference_collector_failure_does_not_reject_a_committed_move(caplog):
    w = _reference_game()

    def broken(*args):
        raise RuntimeError("optional collector failed")

    w("play", (3, 15), guard=True, _reference_committed=broken)
    assert w.game.current_node.depth == 1
    assert "optional collector failed" in caplog.text
