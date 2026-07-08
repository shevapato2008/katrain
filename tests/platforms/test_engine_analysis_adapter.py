"""Tests for GolaxyAdapter.engine_analysis (area/options/judge/variation).

Mirrors test_golaxy_engine_adapter.py's style: the network is mocked at the
``GolaxyRestClient.engine_analysis`` boundary (an ``AsyncMock``), so these
tests never touch httpx. Task 1 (engine_client.py) already validated the
wire parsing into AreaResult/OptionsResult/VariationResult/JudgeResult; this
suite validates the ADAPTER layer -- looking up the engine-game context,
mirroring the genmove auth-refresh-retry discipline for analysis calls, and
decoding raw Golaxy int coords / the 722-float area list / the 361-char judge
belong string into KaTrain (col, row) structures via coords.golaxy_to_katrain.

Golden decode values (validated live in golaxy-protocol.md Section 9.5):
  golaxy_to_katrain(60)  -> Move(col=3, row=3)   (D16)
  golaxy_to_katrain(288) -> Move(col=3, row=15)  (D4; black stone)
  golaxy_to_katrain(300) -> Move(col=15, row=15) (Q4; white stone)

Tests are async (``asyncio_mode=auto`` in pyproject.toml).
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from katrain.web.platforms.golaxy.adapter import (
    AnalysisResult,
    AreaAnalysis,
    Candidate,
    EngineGameConfig,
    EngineGameContext,
    GolaxyAdapter,
    JudgeAnalysis,
    JudgePoint,
    OptionsAnalysis,
    OwnershipPoint,
    Point,
    VariationAnalysis,
)
from katrain.web.platforms.golaxy.coords import Move, golaxy_to_katrain
from katrain.web.platforms.golaxy.engine_client import (
    AreaResult,
    AuthExpired,
    Fatal,
    JudgeResult,
    OptionsResult,
    QuotaExhausted,
    Retryable,
    VariationResult,
)

MOVES = [288, 300]  # seeded engine-game history used by every test below


def make_adapter() -> GolaxyAdapter:
    """Adapter marked connected by seeding a token on the REST client."""
    adapter = GolaxyAdapter()
    adapter._rest.set_tokens("tok", "refresh")
    return adapter


def seed_game(adapter: GolaxyAdapter, moves=None, **cfg_kwargs) -> str:
    """Seed an EngineGameContext directly (analysis doesn't need start_engine_game)."""
    game_id = "golaxy-engine-analysis-test"
    cfg = EngineGameConfig(level=8888, human_color="B", **cfg_kwargs)
    ctx = EngineGameContext(game_id=game_id, config=cfg, moves=list(moves if moves is not None else MOVES))
    adapter._engine_games[game_id] = ctx
    return game_id


def recorder():
    """Return (events_list, async_callback) for capturing emitted events."""
    events: list = []

    async def cb(*args):
        events.append(args)

    return events, cb


# --------------------------------------------------------------------------- #
# Golden decode sanity (confirms the codec matches the brief before trusting  #
# the adapter tests that build on it)                                        #
# --------------------------------------------------------------------------- #


def test_golden_decode_values():
    assert golaxy_to_katrain(60) == Move(col=3, row=3)
    assert golaxy_to_katrain(288) == Move(col=3, row=15)
    assert golaxy_to_katrain(300) == Move(col=15, row=15)


# --------------------------------------------------------------------------- #
# Per-kind happy-path decode                                                  #
# --------------------------------------------------------------------------- #


async def test_variation_decodes_sequence_and_passes_through_winrate_delta():
    adapter = make_adapter()
    game_id = seed_game(adapter)
    result = VariationResult(coord=[60, 288, 300], winrate=0.375, delta=-2.1)
    adapter._rest.engine_analysis = AsyncMock(return_value=result)

    analysis = await adapter.engine_analysis(game_id, "variation")

    assert isinstance(analysis, VariationAnalysis)
    assert analysis.sequence[0] == Point(col=3, row=3)
    assert analysis.sequence == [Point(col=3, row=3), Point(col=3, row=15), Point(col=15, row=15)]
    assert analysis.winrate == pytest.approx(0.375)
    assert analysis.delta == pytest.approx(-2.1)


async def test_variation_skips_unknown_special_coords():
    adapter = make_adapter()
    game_id = seed_game(adapter)
    result = VariationResult(coord=[60, -1, 361, 288], winrate=0.1, delta=0.0)
    adapter._rest.engine_analysis = AsyncMock(return_value=result)

    analysis = await adapter.engine_analysis(game_id, "variation")

    assert analysis.sequence == [Point(col=3, row=3), Point(col=3, row=15)]


async def test_area_decodes_361_points_and_passes_through_winrate_delta():
    adapter = make_adapter()
    game_id = seed_game(adapter)
    area = [0.0] * 722
    area[288] = 0.683
    area[720] = 999.0  # degenerate second channel -- must NOT leak into ownership
    result = AreaResult(area=area, winrate=0.375, delta=-2.2)
    adapter._rest.engine_analysis = AsyncMock(return_value=result)

    analysis = await adapter.engine_analysis(game_id, "area")

    assert isinstance(analysis, AreaAnalysis)
    assert len(analysis.ownership) == 361
    point = analysis.ownership[288]
    assert (point.col, point.row) == (3, 15)
    assert point.value == pytest.approx(0.683)
    assert analysis.winrate == pytest.approx(0.375)
    assert analysis.delta == pytest.approx(-2.2)


async def test_options_decodes_candidates_with_parallel_arrays():
    adapter = make_adapter()
    game_id = seed_game(adapter)
    result = OptionsResult(coord=[60, 59], prob=[0.4, 0.189], winrate=[0.376, 0.377], delta=[-2.1, -1.9])
    adapter._rest.engine_analysis = AsyncMock(return_value=result)

    analysis = await adapter.engine_analysis(game_id, "options")

    assert isinstance(analysis, OptionsAnalysis)
    assert len(analysis.candidates) == 2
    c0 = analysis.candidates[0]
    assert isinstance(c0, Candidate)
    assert (c0.col, c0.row) == (3, 3)  # coord 60
    assert c0.prob == pytest.approx(0.4)
    assert c0.winrate == pytest.approx(0.376)
    assert c0.delta == pytest.approx(-2.1)


async def test_options_skips_unknown_special_coords():
    adapter = make_adapter()
    game_id = seed_game(adapter)
    result = OptionsResult(coord=[60, 999], prob=[0.4, 0.1], winrate=[0.376, 0.3], delta=[-2.1, -1.0])
    adapter._rest.engine_analysis = AsyncMock(return_value=result)

    analysis = await adapter.engine_analysis(game_id, "options")

    assert len(analysis.candidates) == 1
    assert (analysis.candidates[0].col, analysis.candidates[0].row) == (3, 3)


async def test_judge_decodes_361_points_and_passes_through_winner_delta():
    adapter = make_adapter()
    game_id = seed_game(adapter)
    belong = list("U" * 361)
    belong[288] = "B"
    belong[300] = "W"
    belong = "".join(belong)
    result = JudgeResult(belong=belong, winner="B", delta=3.5)
    adapter._rest.engine_analysis = AsyncMock(return_value=result)

    analysis = await adapter.engine_analysis(game_id, "judge")

    assert isinstance(analysis, JudgeAnalysis)
    assert len(analysis.ownership) == 361
    p288 = analysis.ownership[288]
    assert isinstance(p288, JudgePoint)
    assert (p288.col, p288.row) == (3, 15)
    assert p288.owner == "B"
    assert analysis.ownership[300].owner == "W"
    assert analysis.winner == "B"
    assert analysis.delta == pytest.approx(3.5)


# --------------------------------------------------------------------------- #
# ctx wiring: _call_analysis forwards the right fields, read-only guarantee   #
# --------------------------------------------------------------------------- #


async def test_call_analysis_passes_ctx_fields_through():
    adapter = make_adapter()
    game_id = seed_game(adapter, komi=6.5, rule="japanese", handicap=2, board_size=19)
    seen = {}

    async def fake(**kwargs):
        seen.update(kwargs)
        return VariationResult(coord=[], winrate=0.0, delta=0.0)

    adapter._rest.engine_analysis = fake

    await adapter.engine_analysis(game_id, "variation")

    assert seen["kind"] == "variation"
    assert seen["moves"] == MOVES
    assert seen["komi"] == 6.5
    assert seen["rule"] == "japanese"
    assert seen["handicap"] == 2
    assert seen["board_size"] == 19


async def test_analysis_is_read_only_and_works_on_finished_game():
    adapter = make_adapter()
    game_id = seed_game(adapter)
    ctx = adapter._engine_games[game_id]
    ctx.status = "finished"
    before_moves = list(ctx.moves)

    adapter._rest.engine_analysis = AsyncMock(return_value=VariationResult(coord=[60], winrate=0.1, delta=0.0))

    await adapter.engine_analysis(game_id, "variation")

    assert ctx.moves == before_moves  # not mutated
    assert ctx.status == "finished"  # not mutated / not required to be "playing"


# --------------------------------------------------------------------------- #
# Retry discipline (parallel to _genmove_with_retry -- genmove untouched)     #
# --------------------------------------------------------------------------- #


async def test_quota_exhausted_propagates_without_retry():
    adapter = make_adapter()
    game_id = seed_game(adapter)
    mock = AsyncMock(side_effect=QuotaExhausted("item is not sufficient"))
    adapter._rest.engine_analysis = mock

    with pytest.raises(QuotaExhausted):
        await adapter.engine_analysis(game_id, "area")

    mock.assert_awaited_once()  # NOT retried


async def test_fatal_propagates_without_retry():
    adapter = make_adapter()
    game_id = seed_game(adapter)
    mock = AsyncMock(side_effect=Fatal("bad request"))
    adapter._rest.engine_analysis = mock

    with pytest.raises(Fatal):
        await adapter.engine_analysis(game_id, "judge")

    mock.assert_awaited_once()  # NOT retried


async def test_retryable_retries_once_and_returns_result():
    adapter = make_adapter()
    game_id = seed_game(adapter)

    calls = []
    result = JudgeResult(belong="U" * 361, winner="U", delta=0.0)

    def side_effect(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            raise Retryable("transient")
        return result

    adapter._rest.engine_analysis = AsyncMock(side_effect=side_effect)

    analysis = await adapter.engine_analysis(game_id, "judge")

    assert len(calls) == 2
    assert calls[0] == calls[1]
    assert len(analysis.ownership) == 361


async def test_auth_expired_refresh_then_retry_returns_second_result():
    adapter = make_adapter()
    game_id = seed_game(adapter)
    adapter._rest.refresh_access_token = AsyncMock(return_value={"access_token": "new"})

    calls = []
    second_result = VariationResult(coord=[60], winrate=0.4, delta=0.1)

    def side_effect(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            raise AuthExpired("token expired")
        return second_result

    adapter._rest.engine_analysis = AsyncMock(side_effect=side_effect)

    refreshed, refreshed_cb = recorder()
    adapter.on_token_refreshed(refreshed_cb)

    analysis = await adapter.engine_analysis(game_id, "variation")

    adapter._rest.refresh_access_token.assert_awaited_once()
    assert len(refreshed) == 1
    assert len(calls) == 2
    assert calls[0] == calls[1]
    assert analysis.sequence == [Point(col=3, row=3)]
    assert analysis.winrate == pytest.approx(0.4)


async def test_auth_expired_twice_emits_and_raises():
    adapter = make_adapter()
    game_id = seed_game(adapter)
    adapter._rest.refresh_access_token = AsyncMock(return_value={})
    adapter._rest.engine_analysis = AsyncMock(side_effect=AuthExpired("token expired"))

    expired, expired_cb = recorder()
    adapter.on_auth_expired(expired_cb)

    with pytest.raises(AuthExpired):
        await adapter.engine_analysis(game_id, "judge")

    assert len(expired) == 1
    assert adapter._rest.engine_analysis.await_count == 2


# --------------------------------------------------------------------------- #
# Not-found / malformed                                                       #
# --------------------------------------------------------------------------- #


async def test_unknown_game_id_raises_keyerror():
    adapter = make_adapter()
    with pytest.raises(KeyError):
        await adapter.engine_analysis("nope", "area")


async def test_malformed_area_too_short_raises_fatal():
    adapter = make_adapter()
    game_id = seed_game(adapter)
    adapter._rest.engine_analysis = AsyncMock(return_value=AreaResult(area=[0.1] * 100, winrate=0.1, delta=0.0))

    with pytest.raises(Fatal):
        await adapter.engine_analysis(game_id, "area")


async def test_malformed_judge_too_short_raises_fatal():
    adapter = make_adapter()
    game_id = seed_game(adapter)
    adapter._rest.engine_analysis = AsyncMock(return_value=JudgeResult(belong="U" * 100, winner="U", delta=0.0))

    with pytest.raises(Fatal):
        await adapter.engine_analysis(game_id, "judge")


# --------------------------------------------------------------------------- #
# §13 Non-goal: options per-move fields (prob/winrate/delta) are best-effort  #
# -- missing/short arrays must draw every candidate from coord, never raise, #
# never truncate (task-13-2 final review finding).                           #
# --------------------------------------------------------------------------- #


async def test_options_missing_parallel_arrays_defaults_to_zero_for_every_coord():
    adapter = make_adapter()
    game_id = seed_game(adapter)
    result = OptionsResult(coord=[60, 59], prob=[], winrate=[], delta=[])
    adapter._rest.engine_analysis = AsyncMock(return_value=result)

    analysis = await adapter.engine_analysis(game_id, "options")

    assert isinstance(analysis, OptionsAnalysis)
    assert len(analysis.candidates) == 2
    decoded = [golaxy_to_katrain(c) for c in (60, 59)]
    for candidate, coord_decoded in zip(analysis.candidates, decoded):
        assert (candidate.col, candidate.row) == (coord_decoded.col, coord_decoded.row)
        assert candidate.prob == pytest.approx(0.0)
        assert candidate.winrate == pytest.approx(0.0)
        assert candidate.delta == pytest.approx(0.0)


async def test_options_shorter_prob_array_does_not_truncate_candidates():
    adapter = make_adapter()
    game_id = seed_game(adapter)
    # prob/winrate/delta only cover the first coord -- coord has 3 entries.
    result = OptionsResult(coord=[60, 59, 320], prob=[0.4], winrate=[0.376], delta=[-2.1])
    adapter._rest.engine_analysis = AsyncMock(return_value=result)

    analysis = await adapter.engine_analysis(game_id, "options")

    assert len(analysis.candidates) == 3  # one per in-range coord, no truncation
    assert analysis.candidates[0].prob == pytest.approx(0.4)
    assert analysis.candidates[1].prob == pytest.approx(0.0)
    assert analysis.candidates[2].prob == pytest.approx(0.0)
