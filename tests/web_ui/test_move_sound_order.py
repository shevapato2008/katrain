"""Move sounds identify the committed node and follow its state broadcast."""

import sys
import threading
import time

import pytest

pytest.importorskip("fastapi")

# tests/web_ui/conftest.py installs a lightweight interface stub for most web tests.
# This focused suite exercises the real WebKaTrain implementation.
sys.modules.pop("katrain.web.interface", None)

from katrain.core.constants import AI_DEFAULT, PLAYER_AI, PLAYER_HUMAN  # noqa: E402
from katrain.core.sgf_parser import Move  # noqa: E402
from katrain.web.interface import WebKaTrain  # noqa: E402
from katrain.web.models import GameEnd  # noqa: E402


def _web_katrain():
    wkt = WebKaTrain(force_package_config=True, enable_engine=False)
    wkt.save_config = lambda *_args, **_kwargs: None
    wkt.start()
    return wkt


def _seat(wkt, *, ai_colors=()):
    for color in ("B", "W"):
        if color in ai_colors:
            wkt.players_info[color].update(player_type=PLAYER_AI, player_subtype=AI_DEFAULT)
        else:
            wkt.players_info[color].update(player_type=PLAYER_HUMAN)


def _install_deterministic_ai(monkeypatch, coords=(3, 3)):
    committed = {}

    def generate_ai_move(game, _mode, _settings):
        node = game.play(Move(coords, player=game.current_node.next_player))
        committed["node"] = node
        return node.move, node

    import katrain.core.ai as ai_module

    monkeypatch.setattr(ai_module, "generate_ai_move", generate_ai_move)
    return committed


def test_ai_move_broadcasts_state_before_its_node_associated_sound(monkeypatch):
    wkt = _web_katrain()
    _seat(wkt, ai_colors={"B"})
    committed = _install_deterministic_ai(monkeypatch)
    events = []
    wkt._do_update_state = lambda: None
    wkt.update_state_callback = lambda state: events.append(("state", state["current_node_id"]))
    wkt.message_callback = lambda kind, payload: events.append((kind, payload))

    wkt._do_ai_move_and_broadcast(wkt.game.current_node)

    node = committed["node"]
    assert events[0] == ("state", id(node))
    assert events[1][0] == "sound"
    assert events[1][1]["after_node_id"] == id(node)


def test_human_move_sound_contains_the_resulting_node_id():
    wkt = _web_katrain()
    _seat(wkt)
    sounds = []
    wkt.message_callback = lambda kind, payload: sounds.append(payload) if kind == "sound" else None

    wkt._do_play((3, 3))

    assert len(sounds) == 1
    assert sounds[0]["sound"].startswith("stone")
    assert sounds[0]["after_node_id"] == id(wkt.game.current_node)


def test_capture_sound_contains_the_resulting_node_id():
    wkt = _web_katrain()
    _seat(wkt)
    sounds = []
    wkt.message_callback = lambda kind, payload: sounds.append(payload) if kind == "sound" else None
    wkt._do_play((0, 1))
    wkt._do_play((0, 0))
    sounds.clear()

    wkt._do_play((1, 0))

    assert sounds == [{"sound": "capturing", "after_node_id": id(wkt.game.current_node)}]


def test_ai_sound_uses_pre_broadcast_snapshot_when_update_state_navigates(monkeypatch):
    wkt = _web_katrain()
    _seat(wkt, ai_colors={"B"})
    committed = _install_deterministic_ai(monkeypatch, coords=(4, 4))
    events = []

    def broadcast_then_navigate(state):
        events.append(("state", state["current_node_id"]))
        wkt.game.undo(1)

    wkt._do_update_state = lambda: None
    wkt.update_state_callback = broadcast_then_navigate
    wkt.message_callback = lambda kind, payload: events.append((kind, payload))

    wkt._do_ai_move_and_broadcast(wkt.game.current_node)

    node = committed["node"]
    assert wkt.game.current_node is node.parent
    assert events[0] == ("state", id(node))
    assert events[1][0] == "sound"
    assert events[1][1]["sound"].startswith("stone")
    assert events[1][1]["after_node_id"] == id(node)


def test_ai_navigation_without_a_committed_move_does_not_emit_sound(monkeypatch):
    wkt = _web_katrain()
    branch = wkt.game.play(Move((3, 3), player="B"))
    wkt.game.undo(1)
    sounds = []

    def navigate_without_move(_expected_node):
        wkt.game.set_current_node(branch)
        return None

    monkeypatch.setattr(wkt, "_do_ai_move", navigate_without_move)
    wkt._do_update_state = lambda: None
    wkt.update_state_callback = lambda _state: None
    wkt.message_callback = lambda kind, payload: sounds.append(payload) if kind == "sound" else None

    wkt._do_ai_move_and_broadcast(wkt.game.current_node)

    assert wkt.game.current_node is branch
    assert sounds == []


def test_ai_capture_sound_uses_the_committed_capture_node(monkeypatch):
    wkt = _web_katrain()
    wkt.game.play(Move((0, 1), player="B"))
    wkt.game.play(Move((0, 0), player="W"))
    _seat(wkt, ai_colors={"B"})
    committed = _install_deterministic_ai(monkeypatch, coords=(1, 0))
    sounds = []
    wkt._do_update_state = lambda: None
    wkt.update_state_callback = lambda _state: None
    wkt.message_callback = lambda kind, payload: sounds.append(payload) if kind == "sound" else None

    wkt._do_ai_move_and_broadcast(wkt.game.current_node)

    node = committed["node"]
    assert sounds == [{"sound": "capturing", "after_node_id": id(node)}]


def test_ai_capture_navigated_before_wrapper_snapshot_does_not_emit_stale_sound(monkeypatch):
    wkt = _web_katrain()
    wkt.game.play(Move((0, 1), player="B"))
    wkt.game.play(Move((0, 0), player="W"))
    _seat(wkt, ai_colors={"B"})
    committed = _install_deterministic_ai(monkeypatch, coords=(1, 0))
    broadcasts = []
    sounds = []

    monkeypatch.setattr(wkt, "_reset_ladder_stall_retry", lambda: wkt.game.undo(1))
    wkt._do_update_state = lambda: None
    wkt.update_state_callback = lambda state: broadcasts.append(state["current_node_id"])
    wkt.message_callback = lambda kind, payload: sounds.append(payload) if kind == "sound" else None

    wkt._do_ai_move_and_broadcast(wkt.game.current_node)

    node = committed["node"]
    assert wkt.game.current_node is node.parent
    assert broadcasts == [id(node.parent)]
    assert sounds == []


def test_ai_move_from_replaced_game_does_not_emit_after_new_game_state(monkeypatch):
    wkt = _web_katrain()
    replacement = _web_katrain()
    old_game = wkt.game
    _seat(wkt, ai_colors={"B"})
    committed = _install_deterministic_ai(monkeypatch)
    broadcasts = []
    sounds = []

    monkeypatch.setattr(wkt, "_reset_ladder_stall_retry", lambda: setattr(wkt, "game", replacement.game))
    wkt._do_update_state = lambda: None
    wkt.update_state_callback = lambda state: broadcasts.append(state["current_node_id"])
    wkt.message_callback = lambda kind, payload: sounds.append(payload) if kind == "sound" else None

    wkt._do_ai_move_and_broadcast(old_game.current_node)

    assert committed["node"] is old_game.current_node
    assert wkt.game is replacement.game
    assert broadcasts == [id(replacement.game.current_node)]
    assert sounds == []


def test_throttled_broadcast_drops_sound_if_navigation_happens_before_real_state(monkeypatch):
    wkt = _web_katrain()
    _seat(wkt, ai_colors={"B"})
    committed = _install_deterministic_ai(monkeypatch)
    entered_snapshot = threading.Event()
    release_snapshot = threading.Event()
    broadcasted = threading.Event()
    broadcasts = []
    sounds = []
    real_get_state = wkt.get_state

    def blocked_get_state():
        entered_snapshot.set()
        assert release_snapshot.wait(2), "test bug: trailing state snapshot was never released"
        return real_get_state()

    def record_broadcast(state):
        broadcasts.append(state)
        broadcasted.set()

    monkeypatch.setattr(wkt, "get_state", blocked_get_state)
    monkeypatch.setattr(wkt, "_do_update_state", lambda: None)
    wkt.update_state_callback = record_broadcast
    wkt.message_callback = lambda kind, payload: sounds.append(payload) if kind == "sound" else None
    wkt._last_broadcast_time = time.time()
    wkt._pending_broadcast = False

    wkt._do_ai_move_and_broadcast(wkt.game.current_node)

    node = committed["node"]
    assert sounds == []
    assert entered_snapshot.wait(1), "trailing state broadcast never reached its snapshot"
    wkt.game.undo(1)
    release_snapshot.set()
    assert broadcasted.wait(1), "trailing state broadcast did not run"
    assert len(broadcasts) == 1
    assert broadcasts[0]["current_node_id"] == id(node.parent)
    assert sounds == []


def test_throttled_sound_follows_its_matching_real_broadcast(monkeypatch):
    wkt = _web_katrain()
    _seat(wkt, ai_colors={"B"})
    committed = _install_deterministic_ai(monkeypatch)
    callback_entered = threading.Event()
    release_callback = threading.Event()
    sounded = threading.Event()
    events = []

    def record_broadcast(state):
        events.append(("state", state["current_node_id"]))
        callback_entered.set()
        assert release_callback.wait(2), "test bug: trailing state callback was never released"

    def record_message(kind, payload):
        events.append((kind, payload))
        if kind == "sound":
            sounded.set()

    monkeypatch.setattr(wkt, "_do_update_state", lambda: None)
    wkt.update_state_callback = record_broadcast
    wkt.message_callback = record_message
    wkt._last_broadcast_time = time.time()
    wkt._pending_broadcast = False

    wkt._do_ai_move_and_broadcast(wkt.game.current_node)

    node = committed["node"]
    assert events == []
    assert callback_entered.wait(1), "trailing state broadcast did not run"
    assert events == [("state", id(node))]
    release_callback.set()
    assert sounded.wait(1), "matching sound did not follow the trailing broadcast"
    assert events[0] == ("state", id(node))
    assert events[1][0] == "sound"
    assert events[1][1]["after_node_id"] == id(node)


def test_navigation_after_wrapper_validation_but_before_broadcast_drops_stale_sound(monkeypatch):
    wkt = _web_katrain()
    _seat(wkt, ai_colors={"B"})
    committed = _install_deterministic_ai(monkeypatch)
    entered_snapshot = threading.Event()
    release_snapshot = threading.Event()
    broadcasts = []
    sounds = []
    real_get_state = wkt.get_state

    def blocked_get_state():
        entered_snapshot.set()
        assert release_snapshot.wait(2), "test bug: state snapshot was never released"
        return real_get_state()

    monkeypatch.setattr(wkt, "get_state", blocked_get_state)
    monkeypatch.setattr(wkt, "_do_update_state", lambda: None)
    wkt.update_state_callback = broadcasts.append
    wkt.message_callback = lambda kind, payload: sounds.append(payload) if kind == "sound" else None

    worker = threading.Thread(target=wkt._do_ai_move_and_broadcast, args=(wkt.game.current_node,))
    worker.start()
    assert entered_snapshot.wait(2), "AI wrapper never reached the state snapshot"
    node = committed["node"]
    wkt.game.undo(1)
    release_snapshot.set()
    worker.join(2)

    assert not worker.is_alive()
    assert broadcasts[0]["current_node_id"] == id(node.parent)
    assert sounds == []


def test_game_replacement_after_wrapper_validation_but_before_broadcast_drops_old_sound(monkeypatch):
    wkt = _web_katrain()
    replacement = _web_katrain()
    _seat(wkt, ai_colors={"B"})
    committed = _install_deterministic_ai(monkeypatch)
    entered_snapshot = threading.Event()
    release_snapshot = threading.Event()
    broadcasts = []
    sounds = []
    real_get_state = wkt.get_state

    def blocked_get_state():
        entered_snapshot.set()
        assert release_snapshot.wait(2), "test bug: state snapshot was never released"
        return real_get_state()

    monkeypatch.setattr(wkt, "get_state", blocked_get_state)
    monkeypatch.setattr(wkt, "_do_update_state", lambda: None)
    wkt.update_state_callback = broadcasts.append
    wkt.message_callback = lambda kind, payload: sounds.append(payload) if kind == "sound" else None

    worker = threading.Thread(target=wkt._do_ai_move_and_broadcast, args=(wkt.game.current_node,))
    worker.start()
    assert entered_snapshot.wait(2), "AI wrapper never reached the state snapshot"
    old_node = committed["node"]
    with wkt.ai_ladder_commit_lock:
        wkt.game = replacement.game
    release_snapshot.set()
    worker.join(2)

    assert not worker.is_alive()
    assert old_node is not replacement.game.current_node
    assert broadcasts[0]["game_id"] == replacement.game.game_id
    assert broadcasts[0]["current_node_id"] == id(replacement.game.current_node)
    assert sounds == []


@pytest.mark.parametrize("throttled", [False, True])
def test_sound_callback_failure_does_not_skip_game_ended_callback(monkeypatch, caplog, throttled):
    wkt = _web_katrain()
    ended = []
    sound_attempted = threading.Event()
    _seat(wkt, ai_colors={"B"})

    def commit_terminal_move(game, _mode, _settings):
        node = game.play(Move((4, 4), player="B"))
        game.terminal = GameEnd(game, node, "B+R")
        return node.move, node

    def fail_on_sound(kind, _payload):
        if kind == "sound":
            sound_attempted.set()
            raise RuntimeError("speaker unavailable")

    import katrain.core.ai as ai_module

    monkeypatch.setattr(ai_module, "generate_ai_move", commit_terminal_move)
    wkt._do_update_state = lambda: None
    wkt.update_state_callback = lambda _state: None
    wkt.message_callback = fail_on_sound
    wkt.game_ended_callback = ended.append
    if throttled:
        wkt._last_broadcast_time = time.time()
        wkt._pending_broadcast = False

    with caplog.at_level("ERROR", logger="katrain_web"):
        wkt._do_ai_move_and_broadcast(wkt.game.current_node)
        assert ended == [wkt.game.terminal]
        assert sound_attempted.wait(1), "move sound was never attempted"
        deadline = time.monotonic() + 1
        while "Error in AI move sound: speaker unavailable" not in caplog.text and time.monotonic() < deadline:
            time.sleep(0.01)

    assert "Error in AI move sound: speaker unavailable" in caplog.text


def test_pass_does_not_emit_a_stone_sound():
    wkt = _web_katrain()
    _seat(wkt)
    sounds = []
    wkt.message_callback = lambda kind, payload: sounds.append(payload) if kind == "sound" else None

    wkt._do_play(None)

    assert sounds == []
