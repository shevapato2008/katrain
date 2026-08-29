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
import time
from dataclasses import replace
from types import SimpleNamespace

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
from katrain.core.game import Game, Move  # noqa: E402
from katrain.web.interface import LADDER_STALL_RETRY_SCHEDULE, WebKaTrain, resolve_ladder_rung  # noqa: E402
from katrain.web.api.v1.endpoints.auth import get_current_user, get_current_user_optional  # noqa: E402
from katrain.web.server import create_app  # noqa: E402
from katrain.web.session import SessionManager  # noqa: E402


# --- Task 5: /api/ladder-rungs + ai:ladder default (HTTP surface) -------------------


@pytest.fixture
def client(isolated_session_factory):
    app = create_app(enable_engine=False)
    # 必须在进 `TestClient` **之前**设。不设的话 lifespan 里的 `init_db()` 会对开发机
    # 真实 dev 库跑 `backfill_ai_ladder_decisions` —— 那是一条对**真实账本表**的
    # `UPDATE ai_ladder_game_ledger SET counted = TRUE …`。`tests/conftest.py` 的闸拦得住。
    app.state.session_factory = isolated_session_factory
    user = SimpleNamespace(id=987654, uuid="ladder-injection-user", username="ladder-injection-user")
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_current_user_optional] = lambda: user
    with TestClient(app) as c:
        yield c


def test_ladder_rungs_endpoint(client):
    resp = client.get("/api/ladder-rungs")
    assert resp.status_code == 200
    rungs = resp.json()["rungs"]
    assert len(rungs) == 41
    assert set(rungs[0].keys()) == {"rung", "rank_name", "certification_status", "availability", "route"}
    assert rungs[0] == {
        "rung": 1,
        "rank_name": "20级",
        "certification_status": "certified",
        "availability": "available",
        "route": "server",
    }
    assert rungs[-1]["rank_name"] == "超越人类"
    # 2026-08-20「开始吧」之后目录不再是铁板一块：29 档 certified/available、
    # 12 档封档仍报 provisional/unavailable。端点照实转发，不做任何美化。
    from katrain.core import ladder

    available = {r["rung"] for r in rungs if r["availability"] == "available"}
    assert available == set(ladder.PLAYABLE_RUNGS)
    assert all(r["certification_status"] == "certified" for r in rungs if r["rung"] in available)
    assert all(
        (r["certification_status"], r["availability"]) == ("provisional", "unavailable")
        for r in rungs
        if r["rung"] not in available
    )
    # No internal 星阵/elo fields leak to the browser.
    for r in rungs:
        assert "golaxy_level_name" not in r
        assert "display_elo" not in r


def test_ai_constants_ladder_default(client):
    assert client.get("/api/ai-constants").json()["strategy_defaults"]["ai:ladder"] == {}


def test_ranked_session_never_starts_initial_or_replacement_game_analysis(monkeypatch):
    analyzed = threading.Event()
    monkeypatch.setattr(Game, "analyze_all_nodes", lambda *_args, **_kwargs: analyzed.set())
    manager = SessionManager(enable_engine=False)

    session = manager.create_session(
        user_id=1,
        initial_game_type="ai_ladder_ranked",
        skip_initial_analysis=True,
    )
    assert not analyzed.wait(0.05)

    session.katrain("new_game", game_type="ai_ladder_ranked")
    assert not analyzed.wait(0.05)
    manager.remove_session(session.session_id)


def test_new_game_unavailable_ladder_level_returns_422_before_game_mutation(client):
    session_resp = client.post("/api/session")
    assert session_resp.status_code == 200
    session_id = session_resp.json()["session_id"]

    before = client.get("/api/state", params={"session_id": session_id}).json()["state"]
    from katrain.core import ladder

    retired = min(ladder._RETIRED_RUNGS)  # 19级(2)：有配方但封档，正是这条要挡的那一类
    resp = client.post("/api/new-game", json={"session_id": session_id, "ladder_rung": retired})
    assert resp.status_code == 422
    after = client.get("/api/state", params={"session_id": session_id}).json()["state"]
    assert after == before


# --- Step 1/2: resolve_ladder_rung unit tests -------------------------------------


def test_resolve_unavailable_level_raises():
    from katrain.core import ladder

    # 封档档位：**有配方**（所以不是"没实现"）但不可坐 —— 这正是 fail-closed 要挡的形状。
    for rung in sorted(ladder._RETIRED_RUNGS):
        assert ladder.get_level(rung).recipe is not None
        with pytest.raises(ValueError):
            resolve_ladder_rung(rung)
    # 反面：认证档位必须解析得出来，否则这条闸就把所有人都挡住了。
    assert resolve_ladder_rung(1) is not None


def test_resolve_absent_is_none():
    assert resolve_ladder_rung(None) is None


def test_resolve_invalid_raises():
    with pytest.raises(ValueError):
        resolve_ladder_rung(0)
    with pytest.raises(ValueError):
        resolve_ladder_rung(42)


# --- helpers -----------------------------------------------------------------------


def _make_katrain():
    wkt = WebKaTrain(force_package_config=True, enable_engine=False)
    wkt.start()
    return wkt


def _make_ladder_player(wkt, bw):
    """Turn player `bw` into an ai:ladder player (does not touch ladder_rung)."""
    wkt.update_player(bw, player_type=PLAYER_AI, player_subtype=AI_LADDER)


def _certify_fixture_rungs(monkeypatch, *rungs):
    """Keep lifecycle tests independent from the still-changing production certifications."""
    from katrain.core import ladder

    levels = list(ladder.LADDER_LEVELS)
    for rung in rungs:
        assert levels[rung - 1].recipe is not None
        levels[rung - 1] = replace(levels[rung - 1], certification_status="certified", availability="available")
    monkeypatch.setattr(ladder, "LADDER_LEVELS", tuple(levels))


# --- Step 4a/b: lifecycle (set + reset) ---------------------------------------------


def test_new_game_sets_injected_rung(monkeypatch):
    _certify_fixture_rungs(monkeypatch, 5)
    wkt = _make_katrain()
    wkt("new_game", ladder_rung=5)
    assert wkt.ladder_rung == {"rung": 5}


def test_new_game_without_rung_resets_to_none(monkeypatch):
    _certify_fixture_rungs(monkeypatch, 5)
    wkt = _make_katrain()
    wkt("new_game", ladder_rung=5)
    assert wkt.ladder_rung == {"rung": 5}

    # A subsequent new game that does NOT pass a rung must clear the stale value --
    # this is the fix for the SGF-load / plain-new-game stale-rung leak.
    wkt("new_game")
    assert wkt.ladder_rung is None


def test_new_game_clears_remote_terminal_marker():
    wkt = _make_katrain()
    wkt.ai_ladder_remote_ended = True

    wkt("new_game")

    assert wkt.ai_ladder_remote_ended is False


def test_remote_terminal_does_not_surface_as_ladder_engine_failure(monkeypatch):
    _certify_fixture_rungs(monkeypatch, 5)
    wkt = _make_katrain()
    wkt._do_new_game(ladder_rung=5)
    _make_ladder_player(wkt, wkt.game.current_node.next_player)
    wkt.ai_ladder_remote_ended = True

    wkt._do_ai_move()

    assert wkt.last_ladder_error is False


def test_load_sgf_without_rung_resets_to_none(monkeypatch):
    _certify_fixture_rungs(monkeypatch, 7)
    wkt = _make_katrain()
    wkt._do_new_game(ladder_rung=7)
    assert wkt.ladder_rung == {"rung": 7}

    wkt("load_sgf", "(;GM[1]FF[4]SZ[19])")
    assert wkt.ladder_rung is None


def test_ranked_session_uses_frozen_recipe_after_global_catalog_changes(monkeypatch):
    from copy import deepcopy
    from katrain.core import ladder

    _certify_fixture_rungs(monkeypatch, 5)
    frozen = deepcopy(ladder.LADDER_LEVELS[4].recipe)
    original_visits = frozen.max_visits
    wkt = _make_katrain()
    wkt._do_new_game(ladder_rung=5, frozen_ladder_recipe=frozen)
    _make_ladder_player(wkt, wkt.game.current_node.next_player)

    levels = list(ladder.LADDER_LEVELS)
    levels[4] = replace(levels[4], recipe=replace(frozen, max_visits=original_visits + 999))
    monkeypatch.setattr(ladder, "LADDER_LEVELS", tuple(levels))
    captured = {}

    def fake_generate_ai_move(game, mode, settings):
        captured.update(settings)
        node = game.play(Move((3, 3), player=game.current_node.next_player))
        return node.move, node

    import katrain.core.ai as ai_mod

    monkeypatch.setattr(ai_mod, "generate_ai_move", fake_generate_ai_move)
    wkt._do_ai_move()

    assert captured["rung"] == 5
    assert captured["frozen_rung"] is frozen
    assert captured["frozen_rung"].max_visits == original_visits
    assert ai_mod._resolve_ladder_strategy_rung(captured) is frozen


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
    _certify_fixture_rungs(monkeypatch, 5, 20)
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


# --- Task 5: rank_display 段位 on the board nameplate --------------------------------


def test_get_state_emits_rank_display_for_ladder_ai():
    wkt = _make_katrain()
    _make_ladder_player(wkt, "W")
    wkt.ladder_rung = {"rung": 36}

    state = wkt.get_state()
    w = state["players_info"]["W"]
    assert w["rank_display"] == "8段"  # the 41-tier catalog's rung 36 rank_name
    assert w["calculated_rank"] is None  # 段位 rides rank_display, not calculated_rank
    b = state["players_info"]["B"]
    assert b["rank_display"] is None  # human player: no ladder rank_display


def test_rank_display_none_when_seat_flipped_to_human_via_partial_update():
    """codex round 1 (medium): a partial /api/player update that changes only player_type
    must not leave a human wearing the ladder 段位 while the rung is still set. Guard is
    `p.ai and ...`."""
    from katrain.core.constants import PLAYER_HUMAN

    wkt = _make_katrain()
    _make_ladder_player(wkt, "W")
    wkt.ladder_rung = {"rung": 36}

    wkt.players_info["W"].player_type = PLAYER_HUMAN  # subtype intentionally left as "ai:ladder"
    assert wkt.players_info["W"].player_subtype == AI_LADDER  # precondition: stale subtype

    state = wkt.get_state()
    assert state["players_info"]["W"]["rank_display"] is None


# --- codex round 4 (high): ladder-error broadcast must not leak the rung index -------


def test_ladder_unavailable_does_not_broadcast_rung_index(monkeypatch, caplog):
    # codex round 4 (high): the LadderUnavailable catch in _do_ai_move interpolated the
    # exception (whose message embeds `rung {n}`) into self.log(..., OUTPUT_ERROR).
    # WebKaTrain.log broadcasts EVERY level via message_callback -> SessionManager WS ->
    # ZenModeApp TopBar. The rung index / visits / 星阵 must NOT reach the client; only the
    # generic last_ladder_error flag should.
    import logging
    import katrain.core.ai as ai

    wkt = _make_katrain()
    next_bw = wkt.game.current_node.next_player
    _make_ladder_player(wkt, next_bw)
    wkt.ladder_rung = {"rung": 36}

    def boom(game, mode, settings):
        raise ai.LadderUnavailable("rung 36: analysis timed out (visits=450)")

    monkeypatch.setattr(ai, "generate_ai_move", boom)

    broadcasts = []
    wkt.message_callback = lambda msg_type, data: broadcasts.append((msg_type, data))

    with caplog.at_level(logging.ERROR, logger="katrain_web"):
        wkt._do_ai_move()

    assert wkt.last_ladder_error is True  # user-facing surface = generic flag, not the diagnostic text
    logged = " ".join(str(d.get("message", "")) for (t, d) in broadcasts if t == "log")
    for banned in ("rung", "visits", "36", "星阵"):
        assert banned not in logged
    assert "rung 36" in caplog.text  # diagnostics preserved on the server-side stdlib logger


if __name__ == "__main__":
    pytest.main([__file__])


# --- 单向闩 -> 有界重试 --------------------------------------------------------------
#
# 上面三条钉的是「刚失败完不许立刻重生」(否则 _do_ai_move_and_broadcast 的 finally 会把
# 自己再叫起来,成无限循环)。它们钉住的**只是那一刻**。从前判据是「失败过没有」,于是
# 一次瞬时失败(引擎重启、一次查询丢了)就把整局的 AI 永久关掉 —— 引擎下一秒好了也不回来。
# 现在判据是**截止时刻**:冷却期内照旧不重生,冷却期过了重试一次,排期用尽才真的闩死。


class _FakeTimer:
    """记录排期,不真的等。"""

    instances = []

    def __init__(self, delay, fn):
        self.delay = delay
        self.fn = fn
        self.started = False
        self.cancelled = False
        _FakeTimer.instances.append(self)

    def start(self):
        self.started = True

    def cancel(self):
        self.cancelled = True


def test_stalled_ladder_move_is_retried_once_the_cooldown_expires(monkeypatch):
    wkt = _make_katrain()
    next_bw = wkt.game.current_node.next_player
    _make_ladder_player(wkt, next_bw)

    wkt.last_ladder_error = True
    wkt._ladder_retry_attempt = 1
    wkt._ladder_retry_at = time.time() - 0.01  # 冷却已过
    wkt._ai_move_pending = False

    _FakeThread.calls = []
    monkeypatch.setattr(threading, "Thread", _FakeThread)

    wkt._do_update_state()

    assert len(_FakeThread.calls) == 1  # 引擎恢复后这一局还能继续
    assert wkt._ai_move_pending is True


def test_an_exhausted_retry_schedule_leaves_the_game_latched(monkeypatch):
    """排期用尽 = `_ladder_retry_at` 归 0。此后永远不再重生 —— 有界,不是无限重试。"""
    wkt = _make_katrain()
    next_bw = wkt.game.current_node.next_player
    _make_ladder_player(wkt, next_bw)

    wkt.last_ladder_error = True
    wkt._ladder_retry_attempt = len(LADDER_STALL_RETRY_SCHEDULE)
    wkt._ladder_retry_at = 0.0
    wkt._ai_move_pending = False

    _FakeThread.calls = []
    monkeypatch.setattr(threading, "Thread", _FakeThread)

    wkt._do_update_state()

    assert _FakeThread.calls == []


def test_each_stall_arms_the_next_delay_and_then_stops(monkeypatch):
    wkt = _make_katrain()
    monkeypatch.setattr(threading, "Timer", _FakeTimer)
    _FakeTimer.instances = []

    for expected_delay in LADDER_STALL_RETRY_SCHEDULE:
        wkt._surface_ladder_unavailable()
        armed = _FakeTimer.instances[-1]
        assert (armed.delay, armed.started) == (expected_delay, True)
        assert wkt._ladder_stall_blocks_retrigger() is True  # 冷却期内不许重生

    armed_count = len(_FakeTimer.instances)
    wkt._surface_ladder_unavailable()  # 第五次:排期已用尽
    assert len(_FakeTimer.instances) == armed_count
    assert wkt._ladder_retry_at == 0.0
    assert wkt._ladder_stall_blocks_retrigger() is True


def test_a_successful_ladder_move_and_a_new_game_both_clear_the_retry_state(monkeypatch):
    """两个清除点都要清:少任何一处,上一局用掉的重试次数会算在下一局头上。"""
    wkt = _make_katrain()
    monkeypatch.setattr(threading, "Timer", _FakeTimer)
    _FakeTimer.instances = []

    wkt._surface_ladder_unavailable()
    assert wkt._ladder_retry_attempt == 1
    wkt._reset_ladder_stall_retry()  # 成功落子走的就是这一句
    assert (wkt._ladder_retry_attempt, wkt._ladder_retry_at) == (0, 0.0)
    assert _FakeTimer.instances[-1].cancelled is True

    wkt._surface_ladder_unavailable()
    assert wkt._ladder_retry_attempt == 1
    wkt._do_new_game()
    assert (wkt._ladder_retry_attempt, wkt._ladder_retry_at) == (0, 0.0)
    assert wkt.last_ladder_error is False
