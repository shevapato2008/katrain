"""B3/G4 — rebuild the Golaxy engine-play move history from the CURRENT node's
root path before every genmove call, so undo/branch navigation can never send
the stateless tunnel a stale or wrong history.

Real stack throughout (mirrors test_engine_integration.py): a real
SessionManager (NullEngine), real PlatformManager, real PlatformCommandGateway,
real GolaxyAdapter and a real KaTrain game tree. Only the network genmove
boundary (adapter._rest.engine_genmove) is mocked; ctx.moves is rebuilt via the
REAL PlatformManager.rebuild_engine_context -> GolaxyAdapter.rebuild_engine_moves
path, and every assertion checks the COMPLETE integer sequence handed to the
next genmove call, not merely that some helper was invoked (review B3).
"""

from unittest.mock import AsyncMock

import pytest

from katrain.core.base_katrain import KaTrainBase
from katrain.web.platforms.gateway import PlatformCommandGateway, PlatformMoveRejectedError
from katrain.web.platforms.golaxy.adapter import EngineGameConfig, GolaxyAdapter, _handicap_stones
from katrain.web.platforms.golaxy.coords import katrain_to_golaxy
from katrain.web.platforms.golaxy.engine_client import GenmoveResult
from katrain.web.platforms.manager import PlatformManager
from katrain.web.session import SessionManager


@pytest.fixture(autouse=True)
def _hermetic_handicap_default(monkeypatch):
    """Isolate these tests from whatever "game/handicap" happens to be saved in
    THIS machine's real ~/.katrain/config.json.

    `Game.__init__` (katrain/core/game.py) silently seeds handicap stones from
    `katrain.config("game/handicap")` whenever a fresh session's `_do_new_game()`
    is called with no explicit `handicap` kwarg (the normal `SessionManager
    .create_session()` path) -- so a real dev box that has ever played a
    handicap game locally leaves stray pre-placed stones on EVERY session these
    tests create, unrelated to Task 5's rebuild logic. Force that one lookup to
    0; every other config key (and every EXPLICIT handicap this file passes via
    edit_game/EngineGameConfig) is untouched.
    """
    original_config = KaTrainBase.config

    def _patched(self, setting, default=None):
        if setting == "game/handicap":
            return 0
        return original_config(self, setting, default)

    monkeypatch.setattr(KaTrainBase, "config", _patched)


def _main_line(session):
    """Ordered chronological list of (player, coords) for the session's real
    game tree main line from current_node up via .parent (see
    test_engine_integration.py's identical helper)."""
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
    adapter._rest.set_tokens("tok", "refresh")  # looks connected, no network
    mock = AsyncMock()
    if genmove_side_effect is not None:
        mock.side_effect = genmove_side_effect
    else:
        mock.return_value = genmove_return
    adapter._rest.engine_genmove = mock
    return sm, pm, gateway, adapter


def _expected_moves(handicap, board_size, path_coords):
    """handicap-prefix + encode(path_coords) -- the exact integer sequence the
    tunnel should see."""
    return _handicap_stones(handicap, board_size) + [katrain_to_golaxy(c, r, board_size) for c, r in path_coords]


def _last_moves_kwarg(adapter):
    return adapter._rest.engine_genmove.call_args_list[-1].kwargs["moves"]


# --------------------------------------------------------------------------- #
# Case 1: 分先 (even) game — undo 2 after 3 exchanges, play again.             #
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_even_game_undo_then_play_rebuilds_full_history():
    sm, pm, gateway, adapter = _build_stack(
        genmove_side_effect=[
            _genmove_for(15, 3),
            _genmove_for(15, 4),
            _genmove_for(15, 5),
            _genmove_for(2, 2),  # AI reply after the post-undo replay
        ]
    )
    config = EngineGameConfig(level=1100, human_color="B", handicap=0)
    session_id = await pm.start_engine_game("golaxy", config, user_id=1)
    session = sm.get_session(session_id)

    await gateway.play_move(session_id, 3, 3, user_id=1)
    await gateway.play_move(session_id, 4, 4, user_id=1)
    await gateway.play_move(session_id, 5, 5, user_id=1)

    assert _main_line(session) == [
        ("B", (3, 3)),
        ("W", (15, 3)),
        ("B", (4, 4)),
        ("W", (15, 4)),
        ("B", (5, 5)),
        ("W", (15, 5)),
    ]

    session.katrain("undo", 2)
    assert _main_line(session) == [
        ("B", (3, 3)),
        ("W", (15, 3)),
        ("B", (4, 4)),
        ("W", (15, 4)),
    ]

    await gateway.play_move(session_id, 6, 6, user_id=1)

    expected = _expected_moves(0, 19, [(3, 3), (15, 3), (4, 4), (15, 4), (6, 6)])
    assert _last_moves_kwarg(adapter) == expected


# --------------------------------------------------------------------------- #
# Case 2: handicap games — undo 1 after 2 exchanges, play again.              #
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
@pytest.mark.parametrize("handicap", [2, 4, 9])
async def test_handicap_game_undo_then_play_rebuilds_prefix_plus_path(handicap):
    sm, pm, gateway, adapter = _build_stack(
        genmove_side_effect=[
            _genmove_for(13, 2),  # AI reply to human move 1
            _genmove_for(13, 4),  # AI reply to human move 2 (about to be undone)
            _genmove_for(2, 2),  # AI reply after the post-undo replay
        ]
    )
    # human White, handicap >= 2 -> side-to-move after handicap == White == human,
    # so the AI does NOT open; human plays first (no extra pre-seeded AI move to
    # account for in the expected path). Coordinates deliberately avoid
    # row/col in {3, 9, 15} -- the near/middle/far star points used by ALL of
    # handicap 2/4/9 -- so a human/AI move can never collide with a
    # pre-placed handicap stone regardless of which parametrization runs.
    config = EngineGameConfig(level=1100, human_color="W", handicap=handicap)
    session_id = await pm.start_engine_game("golaxy", config, user_id=1)
    session = sm.get_session(session_id)

    await gateway.play_move(session_id, 5, 4, user_id=1)
    await gateway.play_move(session_id, 6, 5, user_id=1)

    assert _main_line(session) == [
        ("W", (5, 4)),
        ("B", (13, 2)),
        ("W", (6, 5)),
        ("B", (13, 4)),
    ]

    session.katrain("undo", 1)
    assert _main_line(session) == [
        ("W", (5, 4)),
        ("B", (13, 2)),
        ("W", (6, 5)),
    ]

    await gateway.play_move(session_id, 7, 6, user_id=1)

    expected = _expected_moves(handicap, 19, [(5, 4), (13, 2), (6, 5), (7, 6)])
    assert _last_moves_kwarg(adapter) == expected


# --------------------------------------------------------------------------- #
# Case 3: branch navigation — undo then play a DIFFERENT move.                #
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_branch_after_undo_rebuilds_from_new_branch_not_old_main_line():
    sm, pm, gateway, adapter = _build_stack(
        genmove_side_effect=[
            _genmove_for(15, 3),
            _genmove_for(15, 4),
            _genmove_for(9, 9),  # AI reply to the NEW branch move
        ]
    )
    config = EngineGameConfig(level=1100, human_color="B", handicap=0)
    session_id = await pm.start_engine_game("golaxy", config, user_id=1)
    session = sm.get_session(session_id)

    await gateway.play_move(session_id, 3, 3, user_id=1)
    await gateway.play_move(session_id, 4, 4, user_id=1)

    # undo(n) removes n NODES (not n human/AI exchanges): 2 nodes un-does the
    # whole second exchange [B(4,4), W(15,4)], landing back on the node right
    # after the FIRST exchange -- with Black (human) to move again, so the
    # next play genuinely creates a sibling branch rather than replaying the
    # existing main line.
    session.katrain("undo", 2)
    assert _main_line(session) == [("B", (3, 3)), ("W", (15, 3))]

    # Play a DIFFERENT move than the original (4, 4) -> creates a sibling branch.
    await gateway.play_move(session_id, 7, 7, user_id=1)

    assert _main_line(session) == [("B", (3, 3)), ("W", (15, 3)), ("B", (7, 7)), ("W", (9, 9))]

    expected = _expected_moves(0, 19, [(3, 3), (15, 3), (7, 7)])
    assert _last_moves_kwarg(adapter) == expected


# --------------------------------------------------------------------------- #
# Case 4: a pass on the path -> rebuild raises -> gateway rejects loudly.      #
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_pass_on_path_rejects_loudly_never_silently_dropped():
    sm, pm, gateway, adapter = _build_stack(genmove_return=_genmove_for(15, 3))
    config = EngineGameConfig(level=1100, human_color="B", handicap=0)
    session_id = await pm.start_engine_game("golaxy", config, user_id=1)
    session = sm.get_session(session_id)

    await gateway.play_move(session_id, 3, 3, user_id=1)
    assert _main_line(session) == [("B", (3, 3)), ("W", (15, 3))]

    # Manually corrupt the tree with a pass node -- something the real engine-play
    # flow should never produce (pass_move rejects "pass_not_supported" for engine
    # games), but the rebuild path must defend against it regardless.
    session.katrain("play", coords=None)
    assert session.katrain.game.current_node.is_pass

    with pytest.raises(PlatformMoveRejectedError) as exc_info:
        await gateway.play_move(session_id, 5, 5, user_id=1)

    assert exc_info.value.reason == "engine_error"
    # The tunnel was never called for this attempt -- rejected before set_pending.
    assert adapter._rest.engine_genmove.await_count == 1  # only the first, earlier call
    ctx = pm.get_game_context(session_id)
    assert ctx.pending_action is None


# --------------------------------------------------------------------------- #
# Case 5: no undo — rebuild is idempotent, sequence unchanged from baseline.  #
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_no_undo_straight_play_rebuild_is_idempotent():
    sm, pm, gateway, adapter = _build_stack(
        genmove_side_effect=[_genmove_for(15, 3), _genmove_for(15, 4), _genmove_for(15, 5)]
    )
    config = EngineGameConfig(level=1100, human_color="B", handicap=0)
    session_id = await pm.start_engine_game("golaxy", config, user_id=1)
    session = sm.get_session(session_id)

    await gateway.play_move(session_id, 3, 3, user_id=1)
    assert _last_moves_kwarg(adapter) == _expected_moves(0, 19, [(3, 3)])

    await gateway.play_move(session_id, 4, 4, user_id=1)
    assert _last_moves_kwarg(adapter) == _expected_moves(0, 19, [(3, 3), (15, 3), (4, 4)])

    await gateway.play_move(session_id, 5, 5, user_id=1)
    assert _last_moves_kwarg(adapter) == _expected_moves(0, 19, [(3, 3), (15, 3), (4, 4), (15, 4), (5, 5)])

    assert _main_line(session) == [
        ("B", (3, 3)),
        ("W", (15, 3)),
        ("B", (4, 4)),
        ("W", (15, 4)),
        ("B", (5, 5)),
        ("W", (15, 5)),
    ]
