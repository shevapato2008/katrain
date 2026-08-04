"""Placement and promotion arithmetic for rated play on the strength ladder.

Pure functions over plain integers: no database, no FastAPI, no engine, and no
knowledge of the 41-tier catalogue. Everything here works in *position* space --
1..N over the rungs that are actually playable -- and `ladder_catalog` does the
position<->rung mapping. That split exists because the catalogue has holes (see
ladder_catalog), so raw rung numbers are not a contiguous scale to search.

Rules, from superpowers/tracks/golaxy-ai-ladder-parity/2026-08-04-41-tier-rated-play-integration-design.md
and its upstream 2026-08-03 design:

  - The ladder rank is the user's ONLY rank. It moves on ladder games against the
    AI and on nothing else; human-vs-human play never touches it.
  - A user with no rank plays 5 placement games: a binary search over a window of
    PLACEMENT_WINDOW positions seeded from their legacy rank. 5 comparisons
    resolve exactly 32 starting points, so the window collapses to one position.
  - After placement: +1 per win, -1 per loss; at +3 promote one position and
    reset to 0, at -3 demote one position and reset to 0; saturating at both ends.
  - Inconclusive games never reach here -- they are dropped before settlement.
"""

from __future__ import annotations

from typing import Optional, Tuple

#: Placement: a window resolved by 5 binary comparisons (2**5 == 32).
PLACEMENT_WINDOW = 32
PLACEMENT_GAMES = 5

#: |net wins| that moves you one position.
NET_WIN_THRESHOLD = 3

#: The window is centred below the seed so a placed user can fall as well as climb.
_WINDOW_BACKOFF = 16


def seed_placement_window(seed_position: Optional[int], n_positions: int) -> Tuple[int, int]:
    """The inclusive candidate window placement searches.

    The window is ALWAYS exactly PLACEMENT_WINDOW wide, even when the playable
    ladder is shorter. Keeping the width a power of two is what makes placement
    take exactly PLACEMENT_GAMES games on every branch; a 31-wide window would
    collapse after four games on some branches and then overshoot on the fifth.
    Search slots above the ladder's top clamp onto the top position, so with a
    short ladder the strongest position is simply reachable by more than one
    sequence -- which is the right answer for "beat everything you were shown".

    With no seed the window starts at the bottom, which is why an unplaced user
    cannot be placed above position PLACEMENT_WINDOW; higher tiers are reached by
    promotion.
    """
    if n_positions < 1:
        raise ValueError(f"ladder must have at least one playable position, got {n_positions}")
    last_start = max(1, n_positions - PLACEMENT_WINDOW + 1)
    start = 1 if seed_position is None else min(max(seed_position - _WINDOW_BACKOFF, 1), last_start)
    return start, start + PLACEMENT_WINDOW - 1


def placement_opponent(lo: int, hi: int, n_positions: int) -> int:
    """The position to play next in the binary search, clamped onto the ladder."""
    if not 1 <= lo <= hi:
        raise ValueError(f"invalid placement window: {lo}..{hi}")
    return min((lo + hi) // 2, n_positions)


def placement_apply(lo: int, hi: int, won: bool) -> Tuple[int, int]:
    """Narrow the window by one result. Beating `mid` means you are above it.

    Operates on raw search slots, not the clamped opponent, so the window keeps
    halving cleanly even where several slots map to the same position.
    """
    if not 1 <= lo <= hi:
        raise ValueError(f"invalid placement window: {lo}..{hi}")
    mid = (lo + hi) // 2
    return (mid + 1, hi) if won else (lo, mid)


def placement_settled(lo: int, hi: int, n_positions: int) -> Optional[int]:
    """The resolved position once the window has collapsed, else None."""
    return min(lo, n_positions) if lo == hi else None


def apply_ladder_result(position: int, net_wins: int, won: bool, n_positions: int) -> Tuple[int, int]:
    """One settled game for a placed user -> (new position, new net wins).

    At both ends the position saturates but the counter still resets, so a player
    parked at the top does not bank an unbounded credit that would later carry
    them through a losing run.
    """
    if not 1 <= position <= n_positions:
        raise ValueError(f"position out of range 1..{n_positions}: {position!r}")
    net = net_wins + (1 if won else -1)
    if net >= NET_WIN_THRESHOLD:
        return min(position + 1, n_positions), 0
    if net <= -NET_WIN_THRESHOLD:
        return max(position - 1, 1), 0
    return position, net
