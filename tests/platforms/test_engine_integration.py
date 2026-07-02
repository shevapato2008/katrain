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
from katrain.web.platforms.golaxy.engine_client import GenmoveResult
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
