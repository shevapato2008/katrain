import pytest
from katrain.core.constants import AI_LADDER
from katrain.core.ai import STRATEGY_REGISTRY
from katrain.core.game import Move
from katrain.core.ladder import LADDER_ALLOW_PROVISIONAL_ENV, LadderUnavailable, resolve_available_rung


@pytest.fixture(autouse=True)
def allow_provisional_rungs(monkeypatch):
    """Every test in this file is about how a ladder move is GENERATED -- the picker,
    the attestation, the fail-closed paths -- not about whether a rung has passed
    calibration. `_CERTIFIED_RUNGS` is empty today, so without this every one of
    them would just raise LadderUnavailable in the constructor and test nothing.

    The certification gate itself is covered by tests/core/test_ladder.py and by
    `test_the_certification_gate_still_applies_when_the_switch_is_off` below, so
    turning it off here cannot hide a regression in it.
    """
    monkeypatch.setenv(LADDER_ALLOW_PROVISIONAL_ENV, "1")


def test_the_certification_gate_still_applies_when_the_switch_is_off(monkeypatch):
    """Guards the fixture above: it must be the dev switch doing this, not a rung
    that quietly became certified."""
    monkeypatch.delenv(LADDER_ALLOW_PROVISIONAL_ENV, raising=False)
    with pytest.raises(LadderUnavailable):
        resolve_available_rung(41)


# The identity a healthy engine attests for a net_search rung. Every net_search
# rung in the 41-tier catalogue runs on b18 (see _fixed_product_recipe), so an
# identity naming any other model is what "drift" means in these tests.
B18_IDENTITY = {
    "selected_model": "b18",
    "model_path": "/models/b18.bin.gz",
    "model_sha256": "b18-sha",
    "human_model_path": "/models/humanv0.bin.gz",
    "human_model_sha256": "human-sha",
    "katago_version": "KataGo v1.16.3",
}


#: Rungs picked by MECHANISM, not by number: these tests are about how each
#: mechanism generates a move. Re-derive them from the catalogue if it changes
#: shape again -- 41 is the only pure net_search rung that really searches, and 36
#: the only human_argmax one. native_policy_argmax is synthesised from 41 rather
#: than taken from rung 39, so the attested identity stays the same across the
#: parametrised cases.
HUMAN_WEIGHTED_RUNG = 1     # 20级
HUMAN_ARGMAX_RUNG = 36      # 8段
NET_SEARCH_RUNG = 41        # 超越人类, 64 visits


def _search_analysis(move="Q16", identity=B18_IDENTITY):
    analysis = {"moveInfos": [{"move": move, "order": 0}]}
    if identity is not None:
        analysis["_wrapper"] = dict(identity)
    return analysis


def _policy(*entries):
    policy = [0.0] * (19 * 19 + 1)
    for index, value in entries:
        policy[index] = value
    return policy


class FakeEngine:
    def __init__(
        self,
        analysis,
        has_human_model=True,
        alive=True,
        call_back=True,
        capability=B18_IDENTITY,
        reject_routing=False,
    ):
        self._a, self.has_human_model, self._alive, self._cb = analysis, has_human_model, alive, call_back
        self.capability = capability
        self.reject_routing = reject_routing
        self.last = {}
        self.request_count = 0

    def require_ladder_capability(self, main_model, human_required):
        self.last["required"] = (main_model, human_required)
        if self.reject_routing and main_model is not None:
            raise ValueError("explicit model routing unsupported")
        if human_required and not self.has_human_model:
            raise ValueError("human model unavailable")
        return dict(self.capability) if main_model is not None and self.capability is not None else None

    def ladder_extra_settings(self, native_settings, main_model):
        if self.reject_routing and main_model is not None:
            raise ValueError("explicit model routing unsupported")
        settings = dict(native_settings)
        if main_model is not None:
            settings["model"] = main_model
        return settings

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
        self.request_count += 1
        self.last.update({"visits": visits, "extra": extra_settings, "time_limit": time_limit})
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
    s, eng = _mk(HUMAN_WEIGHTED_RUNG, {"humanPolicy": hp})
    move, _ = s.generate_move()
    assert eng.last["visits"] == 1 and eng.last["time_limit"] is False
    assert (
        eng.last["extra"]["humanSLProfile"] == "rank_20k" and eng.last["extra"]["reportAnalysisWinratesAs"] == "BLACK"
    )
    assert move.gtp() == "D4"


def test_human_weighted_rung_uses_one_u64_draw_in_shared_picker(monkeypatch):
    import secrets

    draw = 17_524_406_870_024_074_035
    calls = []
    monkeypatch.setattr(secrets, "randbits", lambda bits: calls.append(bits) or draw)

    strategy, _ = _mk(HUMAN_WEIGHTED_RUNG, {"humanPolicy": _policy((342, 0.9), (0, 0.1))})
    move, _ = strategy.generate_move()

    assert move.gtp() == "A19"
    assert calls == [64]


def test_human_temperature_rung_uses_rung_temperature_and_one_u64_draw(monkeypatch):
    import secrets
    from dataclasses import replace

    import katrain.core.ladder as ladder

    draw = 17_524_406_870_024_074_035
    calls = []
    rung = replace(
        ladder.get_level(HUMAN_WEIGHTED_RUNG).recipe,
        selection=ladder.HUMAN_TEMPERATURE,
        human_policy_temperature=0.5,
    )
    monkeypatch.setattr(ladder, "resolve_available_rung", lambda _: rung)
    monkeypatch.setattr(secrets, "randbits", lambda bits: calls.append(bits) or draw)

    strategy, _ = _mk(rung.rung, {"humanPolicy": _policy((342, 0.9), (0, 0.1))})
    move, _ = strategy.generate_move()

    assert move.gtp() == "A1"
    assert calls == [64]


@pytest.mark.parametrize(
    ("selection", "analysis", "expected_gtp"),
    [
        ("human_argmax", {"humanPolicy": _policy((342, 0.9), (0, 0.1))}, "A1"),
        ("search", _search_analysis("Q16"), "Q16"),
        (
            "native_policy_argmax",
            {
                "rootInfo": {"visits": 1},
                "moveInfos": [],
                "policy": _policy((0, 1.0)),
                "_wrapper": dict(B18_IDENTITY),
            },
            "A19",
        ),
    ],
)
def test_deterministic_rung_selection_never_draws_randomness(monkeypatch, selection, analysis, expected_gtp):
    import secrets
    from dataclasses import replace

    import katrain.core.ladder as ladder

    base = ladder.get_level(HUMAN_ARGMAX_RUNG if selection == ladder.HUMAN_ARGMAX else NET_SEARCH_RUNG).recipe
    changes = {"selection": selection}
    if selection == ladder.NATIVE_POLICY_ARGMAX:
        changes["max_visits"] = 1
    rung = replace(base, **changes)
    monkeypatch.setattr(ladder, "resolve_available_rung", lambda _: rung)
    monkeypatch.setattr(secrets, "randbits", lambda bits: pytest.fail(f"unexpected {bits}-bit random draw"))

    strategy, _ = _mk(rung.rung, analysis)
    move, _ = strategy.generate_move()

    assert move.gtp() == expected_gtp


def test_cross_mechanism_response_fails_closed_without_search_fallback(monkeypatch):
    from dataclasses import replace

    import katrain.core.ladder as ladder
    from katrain.core.ai import LadderUnavailable

    rung = replace(ladder.get_level(NET_SEARCH_RUNG).recipe, max_visits=1, selection=ladder.NATIVE_POLICY_ARGMAX)
    monkeypatch.setattr(ladder, "resolve_available_rung", lambda _: rung)
    analysis = {
        "rootInfo": {"visits": 1},
        "moveInfos": [{"move": "Q16", "order": 0}],
        "policy": _policy((0, 1.0)),
        "_wrapper": dict(B18_IDENTITY),
    }
    strategy, _ = _mk(rung.rung, analysis)

    with pytest.raises(LadderUnavailable, match="native_policy_argmax"):
        strategy.generate_move()


def test_runtime_passes_complete_rung_to_shared_picker(monkeypatch):
    from dataclasses import replace

    import katrain.core.ladder as ladder

    rung = replace(ladder.get_level(NET_SEARCH_RUNG).recipe, rank_name="spy rung")
    calls = []

    def picker(analysis, received_rung, board_size, *, draw_u64=None):
        calls.append((analysis, received_rung, board_size, draw_u64))
        return "pass"

    monkeypatch.setattr(ladder, "resolve_available_rung", lambda _: rung)
    monkeypatch.setattr(ladder, "pick_ladder_rung_move", picker)
    analysis = _search_analysis()
    strategy, _ = _mk(rung.rung, analysis)

    move, _ = strategy.generate_move()

    assert move.gtp() == "pass"
    assert calls == [(analysis, rung, (19, 19), None)]


def test_search_rung_high_visits_top_move():
    from katrain.core.ladder import get_level

    s, eng = _mk(NET_SEARCH_RUNG, _search_analysis())
    move, _ = s.generate_move()
    # The rung's own configured visits, read from the catalogue rather than
    # hard-coded: the point is that a search rung searches, not that it searches
    # some particular number that calibration is free to change.
    assert eng.last["visits"] == get_level(NET_SEARCH_RUNG).recipe.max_visits > 1
    assert eng.last["extra"]["model"] == "b18"
    assert eng.last["extra"].get("humanSLProfile") is None
    assert move.gtp() == "Q16"


def test_search_rung_rejects_wrong_or_missing_attestation():
    from katrain.core.ai import LadderUnavailable

    wrong = dict(B18_IDENTITY, selected_model="b28", model_path="/models/b28.bin.gz", model_sha256="b28-sha")
    for analysis in (_search_analysis(identity=wrong), _search_analysis(identity=None)):
        strategy, _ = _mk(NET_SEARCH_RUNG, analysis)
        with pytest.raises(LadderUnavailable, match="attestation"):
            strategy.generate_move()


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("selected_model", "b28"),
        ("model_path", "/models/other.bin.gz"),
        ("model_sha256", "other-sha"),
        ("human_model_sha256", "other-human-sha"),
        ("katago_version", "KataGo v0.0"),
    ],
)
def test_search_rung_rejects_response_identity_drift_from_startup(field, value):
    from katrain.core.ai import LadderUnavailable

    response_identity = dict(B18_IDENTITY)
    response_identity[field] = value
    strategy, _ = _mk(NET_SEARCH_RUNG, _search_analysis(identity=response_identity))
    with pytest.raises(LadderUnavailable, match=field):
        strategy.generate_move()


def test_search_rung_rejects_startup_capability_for_another_model():
    from katrain.core.ai import LadderUnavailable

    capability = dict(
        B18_IDENTITY,
        selected_model="b28",
        model_path="/models/b28.bin.gz",
        model_sha256="b28-sha",
    )
    strategy, _ = _mk(NET_SEARCH_RUNG, _search_analysis())
    strategy.game.engines["B"].capability = capability
    with pytest.raises(LadderUnavailable, match="selected_model"):
        strategy.generate_move()


def test_humansl_search_requires_human_attestation(monkeypatch):
    from katrain.core.ai import LadderUnavailable
    from katrain.core.ladder import HUMANSL_PIKL_BASELINE, LadderRung
    import katrain.core.ladder as ladder

    rung = LadderRung(
        rung=999,
        golaxy_level_name=None,
        golaxy_api_level=None,
        display_elo=None,
        ref_rank="rank_9d",
        rank_name="9D search",
        net="b18",
        mechanism="humansl_search",
        selection="search",
        human_sl_profile="rank_9d",
        max_visits=40,
        human_sl_params=dict(HUMANSL_PIKL_BASELINE),
    )
    monkeypatch.setattr(ladder, "resolve_available_rung", lambda _: rung)
    identity = dict(B18_IDENTITY)
    identity["human_model_path"] = None
    identity["human_model_sha256"] = None
    capability = dict(identity, human_model_path="/models/humanv0.bin.gz", human_model_sha256="human-sha")
    engine = FakeEngine(_search_analysis(identity=identity), capability=capability)
    strategy = STRATEGY_REGISTRY[AI_LADDER](FakeGame(engine), {"rung": 999})
    with pytest.raises(LadderUnavailable, match="human_model_path"):
        strategy.generate_move()


def test_explicit_model_route_rejection_is_unavailable_before_io():
    from katrain.core.ai import LadderUnavailable

    engine = FakeEngine(_search_analysis(), reject_routing=True)
    strategy = STRATEGY_REGISTRY[AI_LADDER](FakeGame(engine), {"rung": NET_SEARCH_RUNG})
    with pytest.raises(LadderUnavailable, match="routing unsupported"):
        strategy.generate_move()
    assert engine.request_count == 0


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

    s, eng = _mk(HUMAN_WEIGHTED_RUNG, {"moveInfos": [{"move": "Q16", "order": 0}]}, hhm=False)
    with pytest.raises(LadderUnavailable):  # NO silent PolicyStrategy fallback (uncalibrated strength)
        s.generate_move()


def test_analysis_error_raises_unavailable():
    from katrain.core.ai import LadderUnavailable

    eng = FakeEngine({})

    def boom(node, callback, error_callback=None, **kw):
        error_callback("boom")

    eng.request_analysis = boom
    s = STRATEGY_REGISTRY[AI_LADDER](FakeGame(eng), {"rung": HUMAN_WEIGHTED_RUNG})
    with pytest.raises(LadderUnavailable):  # NO cached-top-policy fallback either
        s.generate_move()


def test_humansl_degraded_response_raises_unavailable():
    # humanSL rung 1 but response has NO humanPolicy (only moveInfos): must NOT play a search
    # move under the humanSL label -> LadderUnavailable (H2, no cross-mechanism fallback).
    from katrain.core.ai import LadderUnavailable

    s, eng = _mk(HUMAN_WEIGHTED_RUNG, {"moveInfos": [{"move": "Q16", "order": 0}]})  # has_human_model True, but degraded output
    with pytest.raises(LadderUnavailable):
        s.generate_move()


def test_dead_engine_raises_unavailable_no_hang(monkeypatch):
    # Engine never calls back AND check_alive() -> False: LadderStrategy must raise promptly
    # (not spin forever holding ai_lock). Shrink the timeout so the deadline path is also covered.
    import katrain.core.ai as ai
    from katrain.core.ai import LadderUnavailable

    monkeypatch.setattr(ai, "LADDER_ANALYSIS_TIMEOUT_S", 0.2, raising=False)
    eng = FakeEngine(_search_analysis(), alive=False, call_back=False)
    s = STRATEGY_REGISTRY[AI_LADDER](FakeGame(eng), {"rung": NET_SEARCH_RUNG})  # net_search, no human model needed
    with pytest.raises(LadderUnavailable):
        s.generate_move()


def test_empty_completed_analysis_raises_unavailable_no_hang():
    # Engine calls back with an EMPTY dict (falsy but COMPLETE): must NOT wait out the deadline —
    # the explicit `done` flag fires, then `not analysis` -> LadderUnavailable (M2).
    from katrain.core.ai import LadderUnavailable

    from katrain.core.ladder import get_level

    s, eng = _mk(NET_SEARCH_RUNG, {})  # net_search rung, callback delivers {} synchronously, alive=True
    with pytest.raises(LadderUnavailable):
        s.generate_move()
    # it DID issue the query, then failed closed on the empty payload
    assert eng.last["visits"] == get_level(NET_SEARCH_RUNG).recipe.max_visits


def test_ladder_never_global_resigns(monkeypatch):
    # The generic pre-strategy resignation check must be skipped for AI_LADDER, matching the
    # calibration harness (which never resigns our side). Force should_ai_resign -> True and
    # assert the ladder still produces a move instead of resigning (R6-H1 parity).
    import katrain.core.ai as ai

    monkeypatch.setattr(ai, "should_ai_resign", lambda *a, **k: True)
    eng = FakeEngine(_search_analysis())
    game = FakeGame(eng)
    result = ai.generate_ai_move(game, AI_LADDER, {"rung": NET_SEARCH_RUNG})
    assert result is not None
    move, played_node = result
    assert move.gtp() == "Q16"
    assert game.current_node.end_state is None


def test_remote_terminal_during_ladder_analysis_cancels_query_and_never_plays():
    import threading
    from katrain.core.ai import LadderUnavailable, generate_ai_move

    started = threading.Event()

    class DeferredEngine(FakeEngine):
        def request_analysis(self, node, callback, **kwargs):
            self.node = node
            self.callback = callback
            started.set()

        def terminate_queries(self, only_for_node=None, **kwargs):
            self.terminated_node = only_for_node

    engine = DeferredEngine(_search_analysis(), call_back=False)
    game = FakeGame(engine)
    original_node = game.current_node
    failure = []

    def generate():
        try:
            generate_ai_move(game, AI_LADDER, {"rung": NET_SEARCH_RUNG})
        except Exception as exc:
            failure.append(exc)

    worker = threading.Thread(target=generate)
    worker.start()
    assert started.wait(timeout=1)
    game.katrain.ai_ladder_remote_ended = True
    engine.terminate_queries(only_for_node=original_node)
    engine.callback(_search_analysis(), False)  # a result already in flight arrives late
    worker.join(timeout=1)

    assert not worker.is_alive()
    assert engine.terminated_node is original_node
    assert game.current_node is original_node
    assert len(failure) == 1 and isinstance(failure[0], LadderUnavailable)


def test_remote_terminal_after_move_generation_still_blocks_game_play():
    from katrain.core.ai import LadderUnavailable, generate_ai_move

    engine = FakeEngine(_search_analysis())
    game = FakeGame(engine)
    original_node = game.current_node

    def mark_at_commit(message, *args, **kwargs):
        if str(message).startswith("Playing move"):
            game.katrain.ai_ladder_remote_ended = True

    game.katrain.log = mark_at_commit

    with pytest.raises(LadderUnavailable, match="before move commit"):
        generate_ai_move(game, AI_LADDER, {"rung": NET_SEARCH_RUNG})

    assert game.current_node is original_node


def test_ladder_generate_ai_move_keeps_rung_off_katrain_log(caplog):
    # katrain.log is the WS-broadcast channel: WebKaTrain.log forwards EVERY level via
    # message_callback -> SessionManager WS -> ZenModeApp TopBar (codex round 3/5, verified).
    # NOTHING on the ladder path may push the rung index / visits / 星阵 through it:
    #   - AIStrategy.__init__ settings-dump ({'rung': N})   -> routed to stdlib logger (round 5 fix)
    #   - LadderStrategy success detail (rung · visits)     -> routed to stdlib logger (round 3 fix)
    #   - the returned ai_thoughts                          -> clean 段位 label only
    # The spy is installed BEFORE generate_ai_move so it sees the construction-time init log.
    import logging
    from katrain.core.ai import generate_ai_move
    from katrain.core.constants import AI_LADDER

    eng = FakeEngine(_search_analysis())
    game = FakeGame(eng)
    seen = []
    game.katrain.log = lambda *a, **k: seen.append(str(a[0]) if a else "")

    with caplog.at_level(logging.DEBUG, logger="katrain.core.ai"):
        move, node = generate_ai_move(game, AI_LADDER, {"rung": NET_SEARCH_RUNG})  # 41 == 超越人类

    assert node.ai_thoughts == "棋力阶梯 超越人类"  # clean user-visible thought (SGF + TopBar)
    joined = " ".join(seen)
    for banned in ("星阵", "rung", "visits", str(NET_SEARCH_RUNG)):  # per codex round 5 recommendation
        assert banned not in joined
    assert "visits=" in caplog.text  # observability preserved server-side
