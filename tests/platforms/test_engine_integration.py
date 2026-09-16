"""Part B: real-stack engine-play integration regression.

Proves the FULL manager -> gateway -> adapter -> real KaTrain session path applies
moves in [human, then AI] ORDER (the #1 bug an external review flagged). Everything
here is REAL — a real SessionManager (NullEngine), real PlatformManager, real
PlatformCommandGateway, real GolaxyAdapter and a real KaTrain game tree. The ONLY
thing mocked is the network genmove boundary (adapter._rest.engine_genmove); no
httpx call is ever made.

ORDER (not membership) is asserted by walking the real game tree's main line from
current_node up via .parent, collecting each node's .move (Move with .coords and
.player), then reversing to chronological order.
"""

from unittest.mock import AsyncMock

import pytest

from katrain.web.platforms.gateway import PlatformCommandGateway
from katrain.web.platforms.golaxy.adapter import EngineGameConfig, GolaxyAdapter
from katrain.web.platforms.golaxy.coords import katrain_to_golaxy
from katrain.web.platforms.golaxy.engine_client import GenmoveResult, Retryable
from katrain.web.platforms.manager import PlatformManager
from katrain.web.session import SessionManager


def _main_line(session):
    """Ordered chronological list of (player, coords) for the session's real game tree."""
    node = session.katrain.game.current_node
    line = []
    while node is not None:
        if node.move is not None:
            line.append((node.move.player, node.move.coords))
        node = node.parent
    line.reverse()
    return line


def _genmove_for(col, row, board_size=19, prob=0.5):
    """A GenmoveResult whose coord decodes to KaTrain (col, row)."""
    return GenmoveResult(coord=katrain_to_golaxy(col, row, board_size), prob=prob)


def _build_stack(genmove_side_effect=None, genmove_return=None):
    sm = SessionManager(enable_engine=False)
    pm = PlatformManager(sm)
    gateway = PlatformCommandGateway(pm, sm)
    adapter = GolaxyAdapter()
    pm.register_adapter(adapter)
    # Look connected without hitting the network.
    adapter._rest.set_tokens("tok", "refresh")
    mock = AsyncMock()
    if genmove_side_effect is not None:
        mock.side_effect = genmove_side_effect
    else:
        mock.return_value = genmove_return
    adapter._rest.engine_genmove = mock
    return sm, pm, gateway, adapter


@pytest.mark.asyncio
async def test_human_black_move_order_on_real_session():
    """Human Black plays first, then the AI reply (White) — in that exact order."""
    # AI (White) will reply at (15, 3).
    sm, pm, gateway, adapter = _build_stack(genmove_return=_genmove_for(15, 3))

    config = EngineGameConfig(level=1100, human_color="B")
    session_id = await pm.start_engine_game("golaxy", config, user_id=1)
    session = sm.get_session(session_id)

    # No AI opening for human Black — empty board before the human moves.
    assert _main_line(session) == []

    await gateway.play_move(session_id, 3, 3, user_id=1)

    # Exactly two moves, human Black FIRST then AI White SECOND.
    assert _main_line(session) == [("B", (3, 3)), ("W", (15, 3))]

    # The network boundary was exercised (and only there).
    adapter._rest.engine_genmove.assert_awaited_once()


@pytest.mark.asyncio
async def test_human_white_move_order_on_real_session():
    """Human White: AI (Black) opens on start, then [AI black, human white, AI black]."""
    # Call 1 (AI opening, Black) -> (3, 3); Call 2 (AI reply, Black) -> (16, 16).
    sm, pm, gateway, adapter = _build_stack(genmove_side_effect=[_genmove_for(3, 3), _genmove_for(16, 16)])

    config = EngineGameConfig(level=1100, human_color="W")
    session_id = await pm.start_engine_game("golaxy", config, user_id=1)
    session = sm.get_session(session_id)

    # AI (Black) has already opened after start_engine_game.
    assert _main_line(session) == [("B", (3, 3))]

    await gateway.play_move(session_id, 15, 15, user_id=1)

    # Three moves in order: AI black, human white, AI black.
    assert _main_line(session) == [("B", (3, 3)), ("W", (15, 15)), ("B", (16, 16))]

    assert adapter._rest.engine_genmove.await_count == 2


@pytest.mark.asyncio
async def test_ai_special_coord_ends_the_local_game_without_result():
    """X9: genmove 回一个盘外坐标(星阵的停一手 / 认输都解成 UnknownSpecial)。"""
    from katrain.web.platforms.gateway import PlatformMoveRejectedError

    sm, pm, gateway, adapter = _build_stack(genmove_return=GenmoveResult(coord=361, prob=0.0))
    pm._setup_callbacks(adapter)
    config = EngineGameConfig(level=1100, human_color="B")
    session_id = await pm.start_engine_game("golaxy", config, user_id=1)
    session = sm.get_session(session_id)

    with pytest.raises(PlatformMoveRejectedError) as exc_info:
        await gateway.play_move(session_id, 3, 3, user_id=1)

    assert exc_info.value.reason == "game_ended"
    assert _main_line(session) == [("B", (3, 3))]
    assert session.katrain.game.end_result == "Void"
    assert session.katrain.get_state()["end_result"] == "Void"
    assert not pm.is_platform_game(session_id)


TUNNEL_TIMEOUT = Retryable("Golaxy genmove network error: ReadTimeout")


async def _human_black_move_waiting_on_the_tunnel(reply):
    """开一盘人执黑的星阵人机局，让落子请求停在可控的 genmove 网络边界。"""
    import asyncio

    entered, release = asyncio.Event(), asyncio.Event()

    async def genmove_waits_for_release(**_kwargs):
        entered.set()
        await release.wait()
        if isinstance(reply, Exception):
            raise reply
        return reply

    sm, pm, gateway, adapter = _build_stack(genmove_side_effect=genmove_waits_for_release)
    pm._setup_callbacks(adapter)
    session_id = await pm.start_engine_game("golaxy", EngineGameConfig(level=1100, human_color="B"), user_id=1)
    session = sm.get_session(session_id)
    move_task = asyncio.create_task(gateway.play_move(session_id, 3, 3, user_id=1))
    await entered.wait()
    return gateway, session_id, session, move_task, release


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "reply",
    [_genmove_for(15, 3), GenmoveResult(coord=361, prob=0.0), TUNNEL_TIMEOUT],
    ids=["ai_move", "ai_special_coord", "tunnel_timeout"],
)
async def test_resign_during_the_tunnel_wait_stands_against_the_late_reply(reply):
    """等待 AI 时认输后，迟到的落点、终局或超时都不能复活或改写该局。"""
    from katrain.web.platforms.gateway import PlatformMoveRejectedError

    gateway, session_id, session, move_task, release = await _human_black_move_waiting_on_the_tunnel(reply)

    await gateway.resign(session_id, user_id=1)
    resigned = session.katrain.game.end_result
    assert resigned and resigned.endswith("+R")

    release.set()
    with pytest.raises(PlatformMoveRejectedError) as exc_info:
        await move_task

    assert exc_info.value.reason == "game_ended"
    assert session.katrain.game.end_result == resigned
    assert _main_line(session) == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "reply", [GenmoveResult(coord=361, prob=0.0), TUNNEL_TIMEOUT], ids=["ai_special_coord", "tunnel_timeout"]
)
async def test_new_game_during_the_tunnel_wait_is_not_touched_by_the_late_reply(reply):
    """等待期间换局后，迟到的回复不能结束或改动新局。"""
    from katrain.web.platforms.gateway import PlatformMoveRejectedError

    gateway, session_id, session, move_task, release = await _human_black_move_waiting_on_the_tunnel(reply)

    with session.lock:
        session.katrain("new_game")

    release.set()
    with pytest.raises(PlatformMoveRejectedError) as exc_info:
        await move_task

    assert session.katrain.game.end_result is None
    assert _main_line(session) == []
    assert exc_info.value.reason == "position_changed"
