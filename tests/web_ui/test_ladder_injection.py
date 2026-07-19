"""Task 4: per-game rung injection (fail-closed) + lifecycle/concurrency safety.

Covers:
  - resolve_ladder_rung(n) module helper (Step 1/2).
  - WebKaTrain lifecycle: new-game rung injection + reset-to-None on any new game/
    load_sgf that omits it (Step 4a/b).
  - _do_ai_move fail-closed when an ai:ladder player has no injected rung (Step 4c).
  - _do_ai_move catches LadderUnavailable -> no move + surfaced flag (Step 4d).
  - Deterministic concurrency: _do_new_game's game/rung swap is serialized against an
    in-flight _do_ai_move generation by the SAME ai_lock (Step 4e).
"""

import sys
import threading

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

# The shared web_ui conftest mocks `katrain.web.interface` as a MagicMock so that
# unrelated tests don't drag in the kivy import chain. This suite needs the REAL
# WebKaTrain/resolve_ladder_rung, so undo that mock here (same pattern as
# test_suppress_auto_eval.py / test_cloud_analysis_routing.py). Blast radius is
# limited to this module.
sys.modules.pop("katrain.web.interface", None)

from katrain.core.constants import AI_LADDER, AI_POLICY, PLAYER_AI  # noqa: E402
from katrain.core.game import Move  # noqa: E402
from katrain.web.interface import WebKaTrain, resolve_ladder_rung  # noqa: E402
from katrain.web.server import create_app  # noqa: E402


# --- Task 5: /api/ladder-rungs + ai:ladder default (HTTP surface) -------------------


@pytest.fixture
def client():
    app = create_app(enable_engine=False)
    with TestClient(app) as c:
        yield c


def test_ladder_rungs_endpoint(client):
    resp = client.get("/api/ladder-rungs")
    assert resp.status_code == 200
    rungs = resp.json()["rungs"]
    assert len(rungs) == 40
    # New star阵-free wire schema: only rung + rank_name.
    assert set(rungs[0].keys()) == {"rung", "rank_name"}
    assert rungs[0] == {"rung": 1, "rank_name": "18级"}
    assert rungs[38] == {"rung": 39, "rank_name": "超越职业"}
    assert rungs[39] == {"rung": 40, "rank_name": "KataGo 中等算力"}
    # No internal 星阵/elo fields leak to the browser.
    for r in rungs:
        assert "golaxy_level_name" not in r
        assert "display_elo" not in r


def test_ai_constants_ladder_default(client):
    assert client.get("/api/ai-constants").json()["strategy_defaults"]["ai:ladder"] == {}


def test_new_game_invalid_ladder_rung_returns_422(client):
    session_resp = client.post("/api/session")
    assert session_resp.status_code == 200
    session_id = session_resp.json()["session_id"]

    resp = client.post("/api/new-game", json={"session_id": session_id, "ladder_rung": 41})
    assert resp.status_code == 422


# --- Step 1/2: resolve_ladder_rung unit tests -------------------------------------


def test_resolve_valid():
    s = resolve_ladder_rung(1)
    assert s == {"rung": 1}


def test_resolve_absent_is_none():
    assert resolve_ladder_rung(None) is None


def test_resolve_invalid_raises():
    with pytest.raises(ValueError):
        resolve_ladder_rung(0)
    with pytest.raises(ValueError):
        resolve_ladder_rung(41)


# --- helpers -----------------------------------------------------------------------


def _make_katrain():
    wkt = WebKaTrain(force_package_config=True, enable_engine=False)
    wkt.start()
    return wkt


def _make_ladder_player(wkt, bw):
    """Turn player `bw` into an ai:ladder player (does not touch ladder_rung)."""
    wkt.update_player(bw, player_type=PLAYER_AI, player_subtype=AI_LADDER)


# --- Step 4a/b: lifecycle (set + reset) ---------------------------------------------


def test_new_game_sets_injected_rung():
    wkt = _make_katrain()
    wkt("new_game", ladder_rung=5)
    assert wkt.ladder_rung == {"rung": 5}


def test_new_game_without_rung_resets_to_none():
    wkt = _make_katrain()
    wkt("new_game", ladder_rung=5)
    assert wkt.ladder_rung == {"rung": 5}

    # A subsequent new game that does NOT pass a rung must clear the stale value --
    # this is the fix for the SGF-load / plain-new-game stale-rung leak.
    wkt("new_game")
    assert wkt.ladder_rung is None


def test_load_sgf_without_rung_resets_to_none():
    wkt = _make_katrain()
    wkt._do_new_game(ladder_rung=7)
    assert wkt.ladder_rung == {"rung": 7}

    wkt("load_sgf", "(;GM[1]FF[4]SZ[19])")
    assert wkt.ladder_rung is None


def test_new_game_invalid_rung_raises():
    wkt = _make_katrain()
    with pytest.raises(ValueError):
        wkt._do_new_game(ladder_rung=999)


# --- Step 4c: fail-closed when ai:ladder player has no injected rung ----------------


def test_ai_ladder_no_rung_fails_closed_no_move():
    wkt = _make_katrain()
    next_bw = wkt.game.current_node.next_player
    _make_ladder_player(wkt, next_bw)
    assert wkt.ladder_rung is None  # no rung was ever injected

    root = wkt.game.root
    wkt._do_ai_move()

    assert wkt.game.root.children == []  # no move was played
    assert wkt.game.root is root


def test_ai_ladder_no_rung_fail_closed_sets_last_ladder_error():
    """Final-review fix, part 1: the no-injected-rung fail-closed branch must ALSO
    mark last_ladder_error, same as the LadderUnavailable branch does -- otherwise
    _do_update_state's re-trigger guard (which gates on last_ladder_error) has nothing
    to gate on for this path and spawns an AI thread forever (see the loop test below)."""
    wkt = _make_katrain()
    next_bw = wkt.game.current_node.next_player
    _make_ladder_player(wkt, next_bw)
    assert wkt.ladder_rung is None  # no rung was ever injected
    assert wkt.last_ladder_error is False

    wkt._do_ai_move()

    assert wkt.game.root.children == []  # no move was played
    assert wkt.last_ladder_error is True
    assert wkt.get_state()["last_ladder_error"] is True


# --- Step 4d: LadderUnavailable -> no move + surfaced flag --------------------------


def test_ai_ladder_unavailable_no_move_and_flag_set():
    wkt = _make_katrain()
    next_bw = wkt.game.current_node.next_player
    _make_ladder_player(wkt, next_bw)

    # Rung 1 is a humanSL rung; the test harness's NullEngine has no has_human_model
    # attribute (getattr(...) -> False), so LadderStrategy.generate_move() raises
    # LadderUnavailable before issuing any analysis request.
    wkt.ladder_rung = {"rung": 1}
    assert wkt.last_ladder_error is False

    root = wkt.game.root
    wkt._do_ai_move()

    assert wkt.game.root.children == []  # NO uncalibrated fallback move was played
    assert wkt.game.root is root
    assert wkt.last_ladder_error is True
    assert wkt.get_state()["last_ladder_error"] is True


def test_ladder_error_flag_cleared_by_new_game():
    wkt = _make_katrain()
    wkt.last_ladder_error = True
    wkt("new_game")
    assert wkt.last_ladder_error is False


# --- Step 4e: deterministic concurrency test ----------------------------------------


def test_new_game_serialized_against_inflight_ai_move(monkeypatch):
    """_do_new_game must block on ai_lock while an ai:ladder generation is in flight, and
    the in-flight generation must use its OWN (game, rung) snapshot -- not whatever
    _do_new_game swaps self.game/self.ladder_rung to concurrently."""
    wkt = _make_katrain()
    next_bw = wkt.game.current_node.next_player
    _make_ladder_player(wkt, next_bw)
    wkt.ladder_rung = {"rung": 5}
    old_game = wkt.game

    gen_started = threading.Event()
    release_gen = threading.Event()
    captured = {}

    def fake_generate_ai_move(game, mode, settings):
        captured["game"] = game
        captured["rung"] = settings.get("rung")
        captured["mode"] = mode
        gen_started.set()
        assert release_gen.wait(timeout=5), "test bug: release_gen never set"
        # Simulate a played move landing on the LOCAL (old) game snapshot.
        node = game.play(Move((3, 3), player=game.current_node.next_player))
        return (node.move, node)

    import katrain.core.ai as ai_mod

    monkeypatch.setattr(ai_mod, "generate_ai_move", fake_generate_ai_move)

    # We call _do_ai_move directly (not via _do_ai_move_and_broadcast) for tight control
    # over timing, so mirror its real bookkeeping: mark a move as already pending so the
    # new game's update_state() (next player is STILL ai:ladder -- reset_players() does not
    # clear player_type/subtype) doesn't spawn a second, uncontrolled AI-move thread that
    # would race with our assertions below.
    wkt._ai_move_pending = True

    ai_thread = threading.Thread(target=wkt._do_ai_move, daemon=True)
    ai_thread.start()

    assert gen_started.wait(timeout=5), "AI thread never entered generate_ai_move"
    assert wkt.ai_lock.locked()  # AI thread holds ai_lock for the whole generation

    new_game_done = threading.Event()

    def _do_new_game_call():
        wkt._do_new_game(ladder_rung=20)
        new_game_done.set()

    ng_thread = threading.Thread(target=_do_new_game_call, daemon=True)
    ng_thread.start()

    # Bounded window to let _do_new_game attempt (and, if the lock were missing, complete)
    # its state swap. Since the AI thread genuinely still holds ai_lock (release_gen is not
    # set), _do_new_game can only still be blocked at this point if the swap is correctly
    # serialized by the same lock.
    ng_thread.join(timeout=0.5)
    assert ng_thread.is_alive(), "_do_new_game did not block on ai_lock during in-flight AI move"
    assert not new_game_done.is_set()
    assert wkt.ladder_rung == {"rung": 5}  # unchanged while the AI thread still holds the lock
    assert wkt.game is old_game

    release_gen.set()

    ai_thread.join(timeout=5)
    assert not ai_thread.is_alive()

    assert new_game_done.wait(timeout=5)
    ng_thread.join(timeout=5)

    # (ii) the completed move used rung 5's LOCAL snapshot (not the new game's rung 20),
    # and landed on the OLD game.
    assert captured["rung"] == 5
    assert captured["mode"] == AI_LADDER
    assert captured["game"] is old_game
    assert len(old_game.root.children) == 1

    # The new-game swap completed only after the lock was released.
    assert wkt.game is not old_game
    assert wkt.game.root.children == []
    assert wkt.ladder_rung == {"rung": 20}


# --- Final-review fix: stop the infinite AI-move retry loop on ladder fail-closed ---
#
# _do_ai_move_and_broadcast runs _do_ai_move on a background thread and, in its
# `finally`, clears _ai_move_pending then calls update_state() -> _do_update_state().
# _do_update_state's re-trigger block spawns a NEW _do_ai_move_and_broadcast thread
# whenever (next_player.ai and not cn.children and not end_result and not pending).
# After a fail-closed ladder move (no move played, no end_result), that condition was
# TRUE again -> infinite respawn loop (CPU busy-loop for the no-rung case; repeated
# bounded-wait engine queries for the LadderUnavailable case). The fix gates the
# re-trigger on `not last_ladder_error` so a ladder that just failed closed does not
# get immediately respawned; the flag clears on new game / successful move so normal
# play and recovery are unaffected.


class _FakeThread:
    """Records spawn attempts instead of actually starting a thread, so the test is
    deterministic (no real threads/sleep) and doesn't need a working AI backend."""

    calls = []

    def __init__(self, target=None, args=(), kwargs=None, daemon=None):
        self.target = target
        self.args = args

    def start(self):
        _FakeThread.calls.append((self.target, self.args))


def test_do_update_state_does_not_respawn_ai_thread_when_ladder_error_set(monkeypatch):
    """The core regression test: with an ai:ladder next player, no children, no
    end_result, and last_ladder_error already True (simulating 'this turn's ladder
    move just failed closed'), _do_update_state must NOT spawn a new AI thread."""
    wkt = _make_katrain()
    next_bw = wkt.game.current_node.next_player
    _make_ladder_player(wkt, next_bw)
    assert wkt.game.current_node.children == []
    assert wkt.game.end_result is None

    wkt.last_ladder_error = True  # this turn's ladder move already failed closed
    wkt._ai_move_pending = False  # cleared by _do_ai_move_and_broadcast's finally

    _FakeThread.calls = []
    monkeypatch.setattr(threading, "Thread", _FakeThread)

    wkt._do_update_state()

    assert _FakeThread.calls == []  # NOT respawned -> loop is broken
    assert wkt._ai_move_pending is False  # never flipped True since nothing spawned


def test_do_update_state_respawns_ai_thread_when_no_ladder_error(monkeypatch):
    """Confirms the guard is a no-op for the normal case: a regular (non-ladder) AI
    player with last_ladder_error False (the default, and what a successful ladder
    move resets it to) still gets re-triggered as before."""
    wkt = _make_katrain()
    next_bw = wkt.game.current_node.next_player
    wkt.update_player(next_bw, player_type=PLAYER_AI, player_subtype=AI_POLICY)
    assert wkt.last_ladder_error is False
    wkt._ai_move_pending = False

    _FakeThread.calls = []
    monkeypatch.setattr(threading, "Thread", _FakeThread)

    wkt._do_update_state()

    assert len(_FakeThread.calls) == 1  # normal re-trigger flow still fires
    target, args = _FakeThread.calls[0]
    assert target == wkt._do_ai_move_and_broadcast
    assert args == (wkt.game.current_node,)
    assert wkt._ai_move_pending is True  # set before the (faked) spawn, as before


def test_do_update_state_respawns_ai_ladder_when_last_ladder_error_false(monkeypatch):
    """Same guard-is-a-no-op check, but for an ai:ladder player specifically -- this is
    the state right after a SUCCESSFUL ladder move (last_ladder_error reset to False at
    interface.py:1010), i.e. the very case the fix must not break: normal ladder play
    must keep re-triggering turn after turn."""
    wkt = _make_katrain()
    next_bw = wkt.game.current_node.next_player
    _make_ladder_player(wkt, next_bw)
    wkt.ladder_rung = {"rung": 5}
    assert wkt.last_ladder_error is False
    wkt._ai_move_pending = False

    _FakeThread.calls = []
    monkeypatch.setattr(threading, "Thread", _FakeThread)

    wkt._do_update_state()

    assert len(_FakeThread.calls) == 1  # ladder re-trigger still fires when healthy


if __name__ == "__main__":
    pytest.main([__file__])
