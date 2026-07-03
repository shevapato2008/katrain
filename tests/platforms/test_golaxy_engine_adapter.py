"""Tests for the GolaxyAdapter human-vs-AI engine-play state machine.

The network is mocked at the ``GolaxyRestClient.engine_genmove`` boundary
(an ``AsyncMock`` set on ``adapter._rest.engine_genmove``) so these tests never
touch httpx. The correctness core under test is the *proposed-moves discipline*:
the human move is encoded into an immutable ``proposed_moves`` snapshot BEFORE the
network call, ``ctx.moves`` is committed exactly once only after a valid AI coord
comes back, and every retry reuses the SAME snapshot -- so a timeout/retry can
never append the human move twice or land moves out of order.

Tests are async (``asyncio_mode=auto`` in pyproject.toml).
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from katrain.web.platforms.golaxy.adapter import (
    EngineGameConfig,
    EngineGameContext,
    EngineGameStart,
    GolaxyAdapter,
    GolaxyEngineTerminal,
)
from katrain.web.platforms.golaxy.coords import Move, golaxy_to_katrain, katrain_to_golaxy
from katrain.web.platforms.golaxy.engine_client import (
    AuthExpired,
    Fatal,
    GenmoveResult,
    Retryable,
    get_level,
    list_levels,
)
from katrain.web.platforms.models import OnlineUser, PlatformGameSession, PlatformMove

AI_COORD = 286  # arbitrary valid on-board coord used by the mocked engine


def make_adapter() -> GolaxyAdapter:
    """Adapter marked connected by seeding a token on the REST client."""
    adapter = GolaxyAdapter()
    adapter._rest.set_tokens("tok", "refresh")
    return adapter


def recorder():
    """Return (events_list, async_callback) for capturing emitted events."""
    events: list = []

    async def cb(*args):
        events.append(args)

    return events, cb


async def start_black(adapter: GolaxyAdapter, **cfg_kwargs) -> str:
    """Start a human-Black game (AI does not open) and return the game_id."""
    if not hasattr(adapter._rest, "engine_genmove") or not isinstance(adapter._rest.engine_genmove, AsyncMock):
        adapter._rest.engine_genmove = AsyncMock()
    cfg = EngineGameConfig(level=1100, human_color="B", **cfg_kwargs)
    start = await adapter.start_engine_game(cfg)
    return start.session.game_id


# --------------------------------------------------------------------------- #
# 1-3: happy-path start / submit                                              #
# --------------------------------------------------------------------------- #


async def test_human_black_submit_one_move():
    adapter = make_adapter()
    adapter._rest.engine_genmove = AsyncMock(return_value=GenmoveResult(coord=AI_COORD, prob=0.19))
    start = await adapter.start_engine_game(EngineGameConfig(level=1100, human_color="B"))
    assert start.first_ai_move is None
    game_id = start.session.game_id
    ctx = adapter._engine_games[game_id]

    col, row = 3, 3
    human_coord = katrain_to_golaxy(col, row)
    move = await adapter.submit_engine_move(game_id, col, row)

    ai_pt = golaxy_to_katrain(AI_COORD)
    assert isinstance(ai_pt, Move)
    assert isinstance(move, PlatformMove)
    assert (move.col, move.row) == (ai_pt.col, ai_pt.row)
    assert move.color == "W"
    assert move.move_number == 2
    assert move.game_id == game_id
    assert ctx.moves == [human_coord, AI_COORD]


async def test_human_white_start_opens_with_ai():
    adapter = make_adapter()
    adapter._rest.engine_genmove = AsyncMock(return_value=GenmoveResult(coord=AI_COORD, prob=0.19))
    start = await adapter.start_engine_game(EngineGameConfig(level=1100, human_color="W"))

    assert isinstance(start, EngineGameStart)
    fm = start.first_ai_move
    assert fm is not None
    ai_pt = golaxy_to_katrain(AI_COORD)
    assert (fm.col, fm.row) == (ai_pt.col, ai_pt.row)
    assert fm.color == "B"
    assert fm.move_number == 1
    ctx = adapter._engine_games[start.session.game_id]
    assert ctx.moves == [AI_COORD]


async def test_human_black_start_no_ai_move():
    adapter = make_adapter()
    adapter._rest.engine_genmove = AsyncMock(return_value=GenmoveResult(coord=AI_COORD, prob=0.19))
    start = await adapter.start_engine_game(EngineGameConfig(level=1100, human_color="B"))
    assert start.first_ai_move is None
    ctx = adapter._engine_games[start.session.game_id]
    assert ctx.moves == []
    adapter._rest.engine_genmove.assert_not_awaited()


# --------------------------------------------------------------------------- #
# 4-7: retry / commit discipline (the correctness core)                       #
# --------------------------------------------------------------------------- #


async def test_retryable_reuses_same_proposed_moves_and_commits_once():
    adapter = make_adapter()
    game_id = await start_black(adapter)
    ctx = adapter._engine_games[game_id]

    calls: list[list[int]] = []

    def side_effect(*, moves, **kwargs):
        calls.append(list(moves))
        if len(calls) == 1:
            raise Retryable("transient")
        return GenmoveResult(coord=AI_COORD, prob=0.19)

    adapter._rest.engine_genmove = AsyncMock(side_effect=side_effect)

    col, row = 3, 3
    human_coord = katrain_to_golaxy(col, row)
    move = await adapter.submit_engine_move(game_id, col, row)

    # retried exactly once, both attempts saw the SAME proposed_moves
    assert len(calls) == 2
    assert calls[0] == [human_coord]
    assert calls[1] == [human_coord]
    # human move appended exactly once (length 2, not 3), AI move committed
    assert ctx.moves == [human_coord, AI_COORD]
    assert len(ctx.moves) == 2
    assert move.move_number == 2


async def test_auth_expired_refresh_then_retry_commits_once():
    adapter = make_adapter()
    game_id = await start_black(adapter)
    ctx = adapter._engine_games[game_id]

    adapter._rest.refresh_access_token = AsyncMock(return_value={"access_token": "new"})

    calls: list[list[int]] = []

    def side_effect(*, moves, **kwargs):
        calls.append(list(moves))
        if len(calls) == 1:
            raise AuthExpired("token expired")
        return GenmoveResult(coord=AI_COORD, prob=0.19)

    adapter._rest.engine_genmove = AsyncMock(side_effect=side_effect)

    refreshed, refreshed_cb = recorder()
    adapter.on_token_refreshed(refreshed_cb)

    col, row = 3, 3
    human_coord = katrain_to_golaxy(col, row)
    move = await adapter.submit_engine_move(game_id, col, row)

    adapter._rest.refresh_access_token.assert_awaited_once()
    assert len(refreshed) == 1
    assert len(calls) == 2
    assert calls[0] == calls[1] == [human_coord]
    assert ctx.moves == [human_coord, AI_COORD]
    assert move.move_number == 2


async def test_auth_expired_twice_emits_and_raises_no_commit():
    adapter = make_adapter()
    game_id = await start_black(adapter)
    ctx = adapter._engine_games[game_id]
    before = list(ctx.moves)

    adapter._rest.refresh_access_token = AsyncMock(return_value={})
    adapter._rest.engine_genmove = AsyncMock(side_effect=AuthExpired("token expired"))

    expired, expired_cb = recorder()
    adapter.on_auth_expired(expired_cb)

    with pytest.raises(AuthExpired):
        await adapter.submit_engine_move(game_id, 3, 3)

    assert len(expired) == 1
    assert ctx.moves == before == []  # no half-commit
    assert adapter._rest.engine_genmove.await_count == 2


async def test_fatal_not_retried_no_commit():
    adapter = make_adapter()
    game_id = await start_black(adapter)
    ctx = adapter._engine_games[game_id]

    mock = AsyncMock(side_effect=Fatal("bad request"))
    adapter._rest.engine_genmove = mock

    with pytest.raises(Fatal):
        await adapter.submit_engine_move(game_id, 3, 3)

    mock.assert_awaited_once()  # no retry
    assert ctx.moves == []


# --------------------------------------------------------------------------- #
# 8: AI special coord -> defensive terminal                                   #
# --------------------------------------------------------------------------- #


async def test_ai_special_coord_terminates_game():
    adapter = make_adapter()
    game_id = await start_black(adapter)
    ctx = adapter._engine_games[game_id]

    ended, ended_cb = recorder()
    adapter.on_game_ended(ended_cb)

    adapter._rest.engine_genmove = AsyncMock(return_value=GenmoveResult(coord=999, prob=0.0))

    with pytest.raises(GolaxyEngineTerminal):
        await adapter.submit_engine_move(game_id, 3, 3)

    assert ctx.status == "finished"
    assert len(ended) == 1
    assert ended[0][0] == game_id
    assert ended[0][1] == "ai_special_coord"
    # AI (human is Black) is White
    assert ended[0][2] == "W"
    # neither the human move nor a bogus AI move was committed
    assert ctx.moves == []


# --------------------------------------------------------------------------- #
# 9: resign                                                                    #
# --------------------------------------------------------------------------- #


async def test_resign_engine_game_human_black():
    adapter = make_adapter()
    game_id = await start_black(adapter)

    ended, ended_cb = recorder()
    adapter.on_game_ended(ended_cb)

    await adapter.resign_engine_game(game_id)

    assert game_id not in adapter._engine_games  # popped
    assert len(ended) == 1
    assert ended[0] == (game_id, "resign", "W")  # human Black resigns -> AI White wins


async def test_resign_engine_game_human_white_winner_black():
    adapter = make_adapter()
    adapter._rest.engine_genmove = AsyncMock(return_value=GenmoveResult(coord=AI_COORD, prob=0.1))
    start = await adapter.start_engine_game(EngineGameConfig(level=1100, human_color="W"))
    game_id = start.session.game_id

    ended, ended_cb = recorder()
    adapter.on_game_ended(ended_cb)

    await adapter.resign_engine_game(game_id)
    assert ended[0] == (game_id, "resign", "B")


async def test_resign_unknown_game_is_noop():
    adapter = make_adapter()
    ended, ended_cb = recorder()
    adapter.on_game_ended(ended_cb)
    await adapter.resign_engine_game("nope")  # must not raise
    assert ended == []


# --------------------------------------------------------------------------- #
# 10: rebuild_engine_moves                                                     #
# --------------------------------------------------------------------------- #


async def test_rebuild_engine_moves_resets_context():
    adapter = make_adapter()
    game_id = await start_black(adapter)
    ctx = adapter._engine_games[game_id]

    adapter.rebuild_engine_moves(game_id, [(3, 3), (15, 3)])
    assert ctx.moves == [katrain_to_golaxy(3, 3), katrain_to_golaxy(15, 3)]


async def test_rebuild_engine_moves_unknown_game_raises():
    adapter = make_adapter()
    with pytest.raises(KeyError):
        adapter.rebuild_engine_moves("nope", [(3, 3)])


# --------------------------------------------------------------------------- #
# 11: get_engine_levels                                                        #
# --------------------------------------------------------------------------- #


def test_get_engine_levels_returns_full_table():
    adapter = GolaxyAdapter()
    levels = adapter.get_engine_levels()
    assert levels == list_levels()
    assert len(levels) == 39


# --------------------------------------------------------------------------- #
# 12: submit on unknown / finished game                                       #
# --------------------------------------------------------------------------- #


async def test_submit_unknown_game_raises_keyerror():
    adapter = make_adapter()
    with pytest.raises(KeyError):
        await adapter.submit_engine_move("nope", 3, 3)


async def test_submit_finished_game_raises_runtimeerror():
    adapter = make_adapter()
    game_id = await start_black(adapter)
    adapter._engine_games[game_id].status = "finished"
    with pytest.raises(RuntimeError):
        await adapter.submit_engine_move(game_id, 3, 3)


# --------------------------------------------------------------------------- #
# capability flag / session shape / auth guard                                #
# --------------------------------------------------------------------------- #


def test_supports_engine_play_flag():
    assert GolaxyAdapter.supports_engine_play is True
    assert GolaxyAdapter().supports_engine_play is True


async def test_start_engine_game_requires_authentication():
    adapter = GolaxyAdapter()  # no tokens set -> not authenticated
    with pytest.raises(RuntimeError):
        await adapter.start_engine_game(EngineGameConfig(level=1100, human_color="B"))


async def test_start_engine_game_session_fields_from_level_table():
    adapter = make_adapter()
    # human Black + handicap 2 => White (the AI) is to move and opens, so the genmove
    # mock must return a valid GenmoveResult (Task B seeds handicap stones + turn logic).
    adapter._rest.engine_genmove = AsyncMock(return_value=GenmoveResult(coord=AI_COORD, prob=0.19))
    cfg = EngineGameConfig(level=1100, human_color="B", komi=6.5, rule="japanese", handicap=2)
    start = await adapter.start_engine_game(cfg)
    s = start.session

    assert isinstance(s, PlatformGameSession)
    assert s.platform == "golaxy"
    assert s.my_color == "B"
    assert s.board_size == 19
    assert s.ranked is False
    assert s.komi == 6.5
    assert s.rules == "japanese"
    assert s.handicap == 2
    assert s.time_control.main_time == 0

    level = get_level(1100)
    assert isinstance(s.opponent, OnlineUser)
    assert s.opponent.platform == "golaxy"
    assert s.opponent.user_id == "1100"
    assert s.opponent.rank_numeric == 1100.0
    assert s.opponent.username == level["name"]  # 星铠虾
    assert s.opponent.rank == level["level_name"]  # 1级


async def test_start_engine_game_unknown_level_fallback_name():
    adapter = make_adapter()
    adapter._rest.engine_genmove = AsyncMock()
    start = await adapter.start_engine_game(EngineGameConfig(level=12345, human_color="B"))
    assert start.session.opponent.username == "AI-12345"
    assert start.session.opponent.rank == "AI-12345"


async def test_engine_game_ids_are_unique_and_monotonic():
    adapter = make_adapter()
    adapter._rest.engine_genmove = AsyncMock()
    g1 = (await adapter.start_engine_game(EngineGameConfig(level=1100, human_color="B"))).session.game_id
    g2 = (await adapter.start_engine_game(EngineGameConfig(level=1100, human_color="B"))).session.game_id
    assert g1 != g2
    assert g1 == "golaxy-engine-1"
    assert g2 == "golaxy-engine-2"
