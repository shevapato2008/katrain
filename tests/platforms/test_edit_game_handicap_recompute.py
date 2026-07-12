"""Task 12 follow-up bug fix: `_do_edit_game`/`_do_new_game` (katrain/web/interface.py)
call `self.game.root.place_handicap_stones(n)`, which is a pure SGF "AB"-property
mutation (sgf_parser.SGFNode.place_handicap_stones) with no reference back to the
Game/board at all. `Game.stones`/`game.board`/`get_state()["stones"]` are only
(re)computed by `Game._calculate_groups()`, called from `set_current_node()`. In
kiosk board mode `WebKaTrain.should_suppress_auto_eval()` is True, so the one
analysis call that would otherwise incidentally trigger a recompute never runs --
leaving handicap stones invisible to both the LED setup-guidance orchestrator and,
more seriously, `Game.play`'s own legality check (`_validate_move_and_update_chains`
reads game.board/chains, not the SGF properties).

Uses the real SessionManager -> WebKaTrain stack (no mocks) via
tests/platforms/conftest.py's directory-scoped `game/handicap` config hermeticity
fixture, the same pattern as test_engine_manager.py.
"""

from __future__ import annotations

from katrain.web.session import SessionManager


def test_edit_game_handicap_recomputes_board_and_chains():
    sm = SessionManager(enable_engine=False)
    session = sm.create_session()
    assert session.katrain.game.root.handicap == 0

    session.katrain("edit_game", handicap=4)

    assert session.katrain.game.root.handicap == 4
    assert len(session.katrain.game.root.placements) == 4  # AB property written
    assert len(session.katrain.game.stones) == 4  # board/chains recomputed to match
    state_stones = session.katrain.get_state()["stones"]
    assert len(state_stones) == 4
    assert all(s[0] == "B" for s in state_stones)  # handicap stones are Black


def test_edit_game_handicap_zero_clears_previously_recomputed_stones():
    """Round-trip: 4 -> 0 must also recompute (place_handicap_stones(0) clears the
    AB property; the board/chains recompute must follow it back to empty)."""
    sm = SessionManager(enable_engine=False)
    session = sm.create_session()
    session.katrain("edit_game", handicap=4)
    assert len(session.katrain.game.stones) == 4

    session.katrain("edit_game", handicap=0)

    assert session.katrain.game.root.handicap == 0
    assert session.katrain.game.root.placements == []
    assert session.katrain.game.stones == []


def test_new_game_handicap_recomputes_board_and_chains():
    """Same bug, `_do_new_game` path: place_handicap_stones runs AFTER WebGame()
    construction already computed groups once (config-seeded, since `_do_new_game`
    updates `game/handicap` config before constructing the Game). The explicit
    placement call right after must still leave game.stones/game.board correct."""
    sm = SessionManager(enable_engine=False)
    session = sm.create_session()

    session.katrain("new_game", handicap=4)

    assert session.katrain.game.root.handicap == 4
    assert len(session.katrain.game.stones) == 4
    assert len(session.katrain.get_state()["stones"]) == 4
