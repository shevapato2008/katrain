"""Task B: Golaxy adapter seeds handicap stones + decides who opens.

Two things under test:

1. **Consistency with the local board (the important one).** The manager auto-places
   the N standard handicap stones on the LOCAL KaTrain board via
   ``sgf_parser.place_handicap_stones(n)``. The stateless Golaxy genmove tunnel must
   be seeded with the SAME stone positions (converted to Golaxy coords), or the local
   board and Golaxy's engine disagree on the position. So we cross-check
   ``_handicap_stones(n)`` against KaTrain's own placement — we do NOT re-derive the
   formula in the test; we call the real ``place_handicap_stones`` and convert its
   ``AB`` setup back through ``katrain_to_golaxy``.

2. **Turn logic.** After N black handicap stones the side-to-move is White; with no
   handicap it is Black. The AI opens exactly when the side-to-move equals the AI's
   color, so the existing 分先 (handicap 0) behavior does not regress.

The tunnel is mocked by monkeypatching ``GolaxyAdapter._genmove_committing`` so no
network / httpx is touched. Async tests need no decorator (``asyncio_mode=auto``).
"""

from __future__ import annotations

import pytest

from katrain.core.sgf_parser import Move as KMove, SGFNode
from katrain.web.platforms.golaxy.adapter import (
    EngineGameConfig,
    GolaxyAdapter,
    _handicap_stones,
)
from katrain.web.platforms.golaxy.coords import katrain_to_golaxy
from katrain.web.platforms.models import PlatformMove


# --------------------------------------------------------------------------- #
# Cross-check: adapter seed == KaTrain's own place_handicap_stones (converted) #
# --------------------------------------------------------------------------- #


def _katrain_handicap_golaxy_set(n: int, board_size: int = 19) -> set[int]:
    """The Golaxy-coord SET of KaTrain's OWN handicap placement for n stones.

    Builds a real SGFNode, runs the same place_handicap_stones the manager relies
    on (non-tygem, the default), reads back the "AB" setup property, parses each SGF
    coord to (col, row) and converts via katrain_to_golaxy. This is the ground truth
    the adapter must match — not the impl formula.
    """
    node = SGFNode(properties={"SZ": str(board_size)})
    node.place_handicap_stones(n)  # default tygem=False, exactly what manager/game use
    ab = node.get_list_property("AB", [])
    coords = [KMove.from_sgf(c, board_size=(board_size, board_size)).coords for c in ab]
    return {katrain_to_golaxy(x, y, board_size) for (x, y) in coords}


@pytest.mark.parametrize("n", [2, 3, 4, 5, 6, 7, 8, 9])
def test_handicap_stones_match_katrain_placement(n):
    """The adapter's seeded stones MUST equal KaTrain's place_handicap_stones
    positions (converted to Golaxy coords). This is the whole point of the task."""
    seeded = _handicap_stones(n)
    expected = _katrain_handicap_golaxy_set(n)
    assert len(seeded) == n  # exactly n stones, no duplicates dropped
    assert set(seeded) == expected


def test_handicap_stones_empty_for_low_counts():
    assert _handicap_stones(0) == []
    assert _handicap_stones(1) == []


def test_handicap_stones_hand_computed_values():
    """Belt-and-suspenders explicit coords for a few n, so a regression in the
    KaTrain-side helper cannot silently move BOTH sides together.

    Golaxy coord = row * 19 + col for (col, row) 0-indexed from top-left.
    For 19x19: near=3, far=15, middle=9.
      (3,3)->60  (15,15)->300  (15,3)->72  (3,15)->288
      (9,9)->180  (3,9)->174  (15,9)->186  (9,3)->66  (9,15)->294
    """
    assert set(_handicap_stones(2)) == {60, 300}
    assert set(_handicap_stones(4)) == {60, 72, 288, 300}
    assert set(_handicap_stones(9)) == {60, 66, 72, 174, 180, 186, 288, 294, 300}


# --------------------------------------------------------------------------- #
# Turn logic: who opens + how ctx.moves is seeded                             #
# --------------------------------------------------------------------------- #


def _make_adapter_recording() -> tuple[GolaxyAdapter, list]:
    """Adapter marked connected, with _genmove_committing replaced by a recorder.

    The recorder appends the (proposed_moves) snapshot it was called with, commits
    ctx.moves the way the real method would (proposed + [ai_coord]) and returns a stub
    PlatformMove. Returns (adapter, calls) where calls is a list of proposed_moves lists.
    """
    adapter = GolaxyAdapter()
    adapter._rest.set_tokens("tok", "refresh")

    calls: list[list[int]] = []
    AI_COORD = 200  # arbitrary valid on-board coord for the stub

    async def fake_genmove_committing(ctx, proposed_moves):
        calls.append(list(proposed_moves))
        ctx.moves = list(proposed_moves) + [AI_COORD]
        ai_color = "W" if ctx.config.human_color == "B" else "B"
        return PlatformMove(col=0, row=0, color=ai_color, move_number=len(ctx.moves), game_id=ctx.game_id)

    adapter._genmove_committing = fake_genmove_committing  # type: ignore[assignment]
    return adapter, calls


async def test_human_black_handicap4_ai_white_opens():
    adapter, calls = _make_adapter_recording()
    expected = sorted(_katrain_handicap_golaxy_set(4))
    start = await adapter.start_engine_game(EngineGameConfig(level=1100, human_color="B", handicap=4))
    ctx = adapter._engine_games[start.session.game_id]

    # ctx.moves started as the 4 handicap coords (then the stub committed an AI move).
    assert sorted(ctx.moves[:4]) == expected
    # AI (White) opened once, seeing exactly the 4 handicap coords as proposed_moves.
    assert len(calls) == 1
    assert sorted(calls[0]) == expected
    assert start.first_ai_move is not None


async def test_human_white_handicap4_no_ai_open():
    adapter, calls = _make_adapter_recording()
    expected = sorted(_katrain_handicap_golaxy_set(4))
    start = await adapter.start_engine_game(EngineGameConfig(level=1100, human_color="W", handicap=4))
    ctx = adapter._engine_games[start.session.game_id]

    # Human is White; after 4 black handicap stones it is White's turn -> human plays,
    # AI does NOT open. ctx.moves is exactly the 4 seeded handicap coords.
    assert sorted(ctx.moves) == expected
    assert len(ctx.moves) == 4
    assert calls == []
    assert start.first_ai_move is None


async def test_human_black_handicap0_no_ai_open():
    adapter, calls = _make_adapter_recording()
    start = await adapter.start_engine_game(EngineGameConfig(level=1100, human_color="B", handicap=0))
    ctx = adapter._engine_games[start.session.game_id]

    # 分先, human Black: Black to move == human -> AI does not open, empty move list.
    assert ctx.moves == []
    assert calls == []
    assert start.first_ai_move is None


async def test_human_white_handicap0_ai_black_opens_no_regression():
    adapter, calls = _make_adapter_recording()
    start = await adapter.start_engine_game(EngineGameConfig(level=1100, human_color="W", handicap=0))
    ctx = adapter._engine_games[start.session.game_id]

    # 分先, human White: Black to move == AI -> AI opens on an EMPTY move list
    # (the existing behavior that must not regress).
    assert len(calls) == 1
    assert calls[0] == []
    assert start.first_ai_move is not None
