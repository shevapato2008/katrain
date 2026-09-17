"""Move sounds identify the committed node and follow its state broadcast."""

import sys

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
    wkt.update_state = lambda **_kwargs: events.append(("state", id(wkt.game.current_node)))
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

    def broadcast_then_navigate(**_kwargs):
        events.append(("state", id(wkt.game.current_node)))
        wkt.game.undo(1)

    wkt.update_state = broadcast_then_navigate
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
    wkt.update_state = lambda **_kwargs: None
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
    wkt.update_state = lambda **_kwargs: None
    wkt.message_callback = lambda kind, payload: sounds.append(payload) if kind == "sound" else None

    wkt._do_ai_move_and_broadcast(wkt.game.current_node)

    node = committed["node"]
    assert sounds == [{"sound": "capturing", "after_node_id": id(node)}]


def test_sound_callback_failure_does_not_skip_game_ended_callback(monkeypatch, caplog):
    wkt = _web_katrain()
    ended = []

    def commit_terminal_move(_expected_node):
        node = wkt.game.play(Move((4, 4), player="B"))
        wkt.game.terminal = GameEnd(wkt.game, node, "B+R")
        return node.move, node

    def fail_on_sound(kind, _payload):
        if kind == "sound":
            raise RuntimeError("speaker unavailable")

    monkeypatch.setattr(wkt, "_do_ai_move", commit_terminal_move)
    wkt.update_state = lambda **_kwargs: None
    wkt.message_callback = fail_on_sound
    wkt.game_ended_callback = ended.append

    with caplog.at_level("ERROR", logger="katrain_web"):
        wkt._do_ai_move_and_broadcast(wkt.game.current_node)

    assert ended == [wkt.game.terminal]
    assert "Error in AI move sound: speaker unavailable" in caplog.text


def test_pass_does_not_emit_a_stone_sound():
    wkt = _web_katrain()
    _seat(wkt)
    sounds = []
    wkt.message_callback = lambda kind, payload: sounds.append(payload) if kind == "sound" else None

    wkt._do_play(None)

    assert sounds == []
