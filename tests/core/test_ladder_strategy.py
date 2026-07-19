import pytest
from katrain.core.constants import AI_LADDER
from katrain.core.ai import STRATEGY_REGISTRY
from katrain.core.game import Move


class FakeEngine:
    def __init__(self, analysis, has_human_model=True, alive=True, call_back=True):
        self._a, self.has_human_model, self._alive, self._cb = analysis, has_human_model, alive, call_back
        self.last = {}

    def request_analysis(
        self,
        node,
        callback,
        error_callback=None,
        visits=None,
        extra_settings=None,
        include_policy=True,
        priority=0,
        time_limit=True,
        **kw,
    ):
        self.last = {"visits": visits, "extra": extra_settings, "time_limit": time_limit}
        if self._cb:
            callback(self._a, False)  # deliver result; if False, never calls back (dead-worker sim)

    def check_alive(self, os_error="", exception_if_dead=False, **kw):
        return self._alive  # returns BOOL, never raises


class FakeNode:
    def __init__(self):
        self.player, self.next_player, self.policy_ranking = "B", "B", None
        self.end_state = None


class FakeKatrain:
    def log(self, *a, **k):
        pass

    def config(self, *a, **k):
        return {}


class FakeGame:
    def __init__(self, eng):
        self.board_size = (19, 19)
        self.current_node = FakeNode()
        self.engines = {"B": eng, "W": eng}
        self.katrain = FakeKatrain()

    def play(self, move):
        node = FakeNode()
        node.move = move
        self.current_node = node
        return node


def _mk(rung_val, analysis, hhm=True):
    eng = FakeEngine(analysis, hhm)
    s = STRATEGY_REGISTRY[AI_LADDER](FakeGame(eng), {"rung": rung_val})
    return s, eng


def test_registered():
    assert AI_LADDER in STRATEGY_REGISTRY


def test_humansl_rung_pure_visits_and_profile():
    hp = [0.0] * (19 * 19 + 1)
    hp[(19 - 3 - 1) * 19 + 3] = 1.0
    s, eng = _mk(1, {"humanPolicy": hp})
    move, _ = s.generate_move()
    assert eng.last["visits"] == 1 and eng.last["time_limit"] is False
    assert (
        eng.last["extra"]["humanSLProfile"] == "rank_20k" and eng.last["extra"]["reportAnalysisWinratesAs"] == "BLACK"
    )
    assert move.gtp() == "D4"


def test_search_rung_high_visits_top_move():
    s, eng = _mk(39, {"moveInfos": [{"move": "Q16", "order": 0}]})
    move, _ = s.generate_move()
    assert eng.last["visits"] >= 100 and eng.last["extra"].get("humanSLProfile") is None and move.gtp() == "Q16"


def test_missing_rung_fails_closed():
    s = STRATEGY_REGISTRY[AI_LADDER](FakeGame(FakeEngine({})), {})  # no 'rung'
    with pytest.raises(ValueError):
        s.generate_move()


def test_invalid_rung_fails_closed():
    s, _ = _mk(999, {})
    with pytest.raises(ValueError):
        s.generate_move()


def test_humansl_no_human_model_raises_unavailable():
    from katrain.core.ai import LadderUnavailable

    s, eng = _mk(1, {"moveInfos": [{"move": "Q16", "order": 0}]}, hhm=False)
    with pytest.raises(LadderUnavailable):  # NO silent PolicyStrategy fallback (uncalibrated strength)
        s.generate_move()


def test_analysis_error_raises_unavailable():
    from katrain.core.ai import LadderUnavailable

    eng = FakeEngine({})

    def boom(node, callback, error_callback=None, **kw):
        error_callback("boom")

    eng.request_analysis = boom
    s = STRATEGY_REGISTRY[AI_LADDER](FakeGame(eng), {"rung": 1})
    with pytest.raises(LadderUnavailable):  # NO cached-top-policy fallback either
        s.generate_move()


def test_humansl_degraded_response_raises_unavailable():
    # humanSL rung 1 but response has NO humanPolicy (only moveInfos): must NOT play a search
    # move under the humanSL label -> LadderUnavailable (H2, no cross-mechanism fallback).
    from katrain.core.ai import LadderUnavailable

    s, eng = _mk(1, {"moveInfos": [{"move": "Q16", "order": 0}]})  # has_human_model True, but degraded output
    with pytest.raises(LadderUnavailable):
        s.generate_move()


def test_dead_engine_raises_unavailable_no_hang(monkeypatch):
    # Engine never calls back AND check_alive() -> False: LadderStrategy must raise promptly
    # (not spin forever holding ai_lock). Shrink the timeout so the deadline path is also covered.
    import katrain.core.ai as ai
    from katrain.core.ai import LadderUnavailable

    monkeypatch.setattr(ai, "LADDER_ANALYSIS_TIMEOUT_S", 0.2, raising=False)
    eng = FakeEngine({"moveInfos": [{"move": "Q16", "order": 0}]}, alive=False, call_back=False)
    s = STRATEGY_REGISTRY[AI_LADDER](FakeGame(eng), {"rung": 39})  # net_search, no human model needed
    with pytest.raises(LadderUnavailable):
        s.generate_move()


def test_empty_completed_analysis_raises_unavailable_no_hang():
    # Engine calls back with an EMPTY dict (falsy but COMPLETE): must NOT wait out the deadline —
    # the explicit `done` flag fires, then `not analysis` -> LadderUnavailable (M2).
    from katrain.core.ai import LadderUnavailable

    s, eng = _mk(39, {})  # net_search rung, callback delivers {} synchronously, alive=True
    with pytest.raises(LadderUnavailable):
        s.generate_move()
    assert eng.last["visits"] >= 100  # it DID issue the query, then failed closed on empty payload


def test_ladder_never_global_resigns(monkeypatch):
    # The generic pre-strategy resignation check must be skipped for AI_LADDER, matching the
    # calibration harness (which never resigns our side). Force should_ai_resign -> True and
    # assert the ladder still produces a move instead of resigning (R6-H1 parity).
    import katrain.core.ai as ai

    monkeypatch.setattr(ai, "should_ai_resign", lambda *a, **k: True)
    eng = FakeEngine({"moveInfos": [{"move": "Q16", "order": 0}]})
    game = FakeGame(eng)
    result = ai.generate_ai_move(game, AI_LADDER, {"rung": 39})
    assert result is not None
    move, played_node = result
    assert move.gtp() == "Q16"
    assert game.current_node.end_state is None


def test_ladder_generate_ai_move_keeps_rung_off_katrain_log(caplog):
    # katrain.log is the WS-broadcast channel: WebKaTrain.log forwards EVERY level via
    # message_callback -> SessionManager WS -> ZenModeApp TopBar (codex round 3/5, verified).
    # NOTHING on the ladder path may push the rung index / visits / 星阵 through it:
    #   - AIStrategy.__init__ settings-dump ({'rung': 39})  -> routed to stdlib logger (round 5 fix)
    #   - LadderStrategy success detail (rung · visits)     -> routed to stdlib logger (round 3 fix)
    #   - the returned ai_thoughts                          -> clean 段位 label only
    # The spy is installed BEFORE generate_ai_move so it sees the construction-time init log.
    import logging
    from katrain.core.ai import generate_ai_move
    from katrain.core.constants import AI_LADDER

    eng = FakeEngine({"moveInfos": [{"move": "Q16", "order": 0}]})
    game = FakeGame(eng)
    seen = []
    game.katrain.log = lambda *a, **k: seen.append(str(a[0]) if a else "")

    with caplog.at_level(logging.DEBUG, logger="katrain.core.ai"):
        move, node = generate_ai_move(game, AI_LADDER, {"rung": 39})  # rung 39 == 超越职业

    assert node.ai_thoughts == "棋力阶梯 超越职业"          # clean user-visible thought (SGF + TopBar)
    joined = " ".join(seen)
    for banned in ("星阵", "rung", "visits", "39"):           # per codex round 5 recommendation
        assert banned not in joined
    assert "visits=" in caplog.text                            # observability preserved server-side
