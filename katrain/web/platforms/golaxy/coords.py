"""Coordinate translation for Golaxy / 星阵围棋 (19x19.com) human-vs-AI play.

Golaxy encodes a board point as a single integer:

    coord = (19 - boardRow) * 19 + colIndex

- boardRow: 1..19, with 19 at the TOP of the board.
- colIndex: 0..18 left-to-right (letters A=0, B=1, ..., H=7, J=8 [I is
  skipped], K=9, ..., T=18). colIndex numerically matches KaTrain's `col`.
- Intuition: it is the 0..(N*N-1) index counting from the top-left corner,
  row-major (row first, then column).

KaTrain uses 0-indexed (col, row) from the top-left: col 0..N-1 left-to-right,
row 0..N-1 top-to-bottom (row 0 = top) -- see katrain/web/platforms/coords.py.

Since Golaxy boardRow=19 is the top and KaTrain row=0 is the top,
`row = 19 - boardRow` (i.e. `boardRow = board_size - row` for board_size=19),
so substituting into the coord formula:

    coord = (19 - boardRow) * 19 + colIndex = row * 19 + col

This module is intentionally dependency-free (no GTP/SGF helpers) -- it only
knows about KaTrain (col, row) <-> Golaxy int coord.

`golaxy_to_katrain` is the *decode* direction for untrusted network input: it
never raises and never returns a bogus Move for a bad coord -- any value
outside [0, board_size*board_size) comes back as UnknownSpecial(raw) so the
caller can turn it into a defensive game-termination rather than forwarding
garbage into `session.katrain("play", coords=...)`.

PASS/RESIGN real wire encodings were NOT captured as of this iteration. The
`Pass`/`Resign` result types exist so later code can pattern-match on them,
but `golaxy_to_katrain` does not (and must not) produce them yet -- it has no
verified sentinel values to recognize. A later task will map real captured
sentinels to Pass/Resign once observed on the wire.

`katrain_to_golaxy` is the *encode* direction for a known-valid human/board
move originating on our side: out-of-range col/row is a programming error,
so it raises ValueError (naming the bad value) rather than silently clamping.
"""

from __future__ import annotations

from dataclasses import dataclass


class GolaxyCoordResult:
    """Base class for the typed result of golaxy_to_katrain.

    Never instantiated directly -- use one of the subclasses below.
    """


@dataclass(frozen=True)
class Move(GolaxyCoordResult):
    """A normal on-board point, in KaTrain (col, row) convention."""

    col: int
    row: int


@dataclass(frozen=True)
class Pass(GolaxyCoordResult):
    """Golaxy pass. Encoding UNKNOWN this iteration -- golaxy_to_katrain
    does not currently produce this; provided for future pattern-matching."""


@dataclass(frozen=True)
class Resign(GolaxyCoordResult):
    """Golaxy resign. Encoding UNKNOWN this iteration -- golaxy_to_katrain
    does not currently produce this; provided for future pattern-matching."""


@dataclass(frozen=True)
class UnknownSpecial(GolaxyCoordResult):
    """Any coord outside [0, board_size*board_size) -- negative, too large,
    or otherwise not a valid on-board index. Carries the raw int for
    logging. golaxy_to_katrain returns this instead of raising or guessing."""

    raw: int


def katrain_to_golaxy(col: int, row: int, board_size: int = 19) -> int:
    """KaTrain (col, row), 0-indexed from top-left -> Golaxy int coord.

    `col`/`row` must be a known-valid on-board point (0 <= col,row <
    board_size); this is for encoding our own moves, not untrusted input.
    Raises ValueError naming the bad value if out of range.
    """
    if not (0 <= col < board_size):
        raise ValueError(f"col out of range for board_size={board_size}: {col}")
    if not (0 <= row < board_size):
        raise ValueError(f"row out of range for board_size={board_size}: {row}")
    return row * board_size + col


def golaxy_to_katrain(coord: int, board_size: int = 19) -> GolaxyCoordResult:
    """Golaxy int coord -> typed result in KaTrain (col, row) convention.

    Returns Move(col, row) for a valid on-board index. Returns
    UnknownSpecial(raw=coord) for anything outside
    [0, board_size*board_size) -- this function never raises, so it is safe
    to call directly on untrusted values coming off the wire.
    """
    if not (0 <= coord < board_size * board_size):
        return UnknownSpecial(raw=coord)
    row, col = divmod(coord, board_size)
    return Move(col=col, row=row)
