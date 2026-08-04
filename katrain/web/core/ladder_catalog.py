"""Which ladder rungs can actually be played, and how they map onto positions.

The 41-tier catalogue in katrain/core/ladder.py has holes: 10 rungs (准1段…准8段,
准9段, 职业顶尖) carry no strength recipe at all, because no candidate has passed
screening yet. Those are not merely uncertified -- there is no configuration to
run, and no development switch conjures one.

A ladder with holes cannot be walked: a placement search would seat an opponent
that does not exist, and a promotion would move a user onto a rung they can never
play. So placement and promotion operate over the *playable* rungs, numbered
1..N by strength. Today N == 31. As calibration fills the holes, N grows toward
41 and the missing 准N段 tiers appear between the ranks that already exist.

This module is the only place that knows the mapping. `ladder_progress` does the
arithmetic in position space and stays free of the catalogue.
"""

from __future__ import annotations

from typing import Optional, Tuple

from katrain.core.ladder import LADDER_LEVELS, get_level


def playable_rungs() -> Tuple[int, ...]:
    """Catalogue rungs that have a strength recipe, weakest first.

    Computed per call rather than cached: `_CERTIFIED_RUNGS` and the recipe table
    are module state, and a stale snapshot would be a silent strength error.
    """
    return tuple(level.rung for level in LADDER_LEVELS if level.recipe is not None)


def position_count() -> int:
    return len(playable_rungs())


def rung_at(position: int) -> int:
    """1-based position -> catalogue rung."""
    rungs = playable_rungs()
    if type(position) is not int or not 1 <= position <= len(rungs):
        raise ValueError(f"ladder position out of range 1..{len(rungs)}: {position!r}")
    return rungs[position - 1]


def position_of(rung: int) -> int:
    """Catalogue rung -> 1-based position. Raises if the rung is not playable."""
    rungs = playable_rungs()
    try:
        return rungs.index(rung) + 1
    except ValueError:
        raise ValueError(f"rung {rung} has no strength recipe and is not on the playable ladder") from None


def rank_name(rung: int) -> str:
    return get_level(rung).rank_name


def legacy_rank_to_position(rank: Optional[str]) -> Optional[int]:
    """Seed value for the placement window, from the legacy `20k`..`12d` rank.

    Legacy ranks name catalogue rungs (20k..1k -> 1..20, 1d..9d -> 22,24,..38);
    those are all playable today, but if one ever is not, we take the nearest
    playable rung at or below it so the seed never lands in a hole.
    """
    rung = _legacy_rank_to_rung(rank)
    if rung is None:
        return None
    rungs = playable_rungs()
    below = [i for i, r in enumerate(rungs, start=1) if r <= rung]
    return below[-1] if below else 1


def _legacy_rank_to_rung(rank: Optional[str]) -> Optional[int]:
    if not isinstance(rank, str):
        return None
    text = rank.strip().lower()
    if len(text) < 2 or not text[:-1].isdigit():
        return None
    n = int(text[:-1])
    if text.endswith("k"):
        return (20 - n) + 1 if 1 <= n <= 20 else None
    if text.endswith("d"):
        if n < 1:
            return None
        return min(22 + (n - 1) * 2, 38)  # 1d -> 22, 9d -> 38; stronger clamps to 9段
    return None
