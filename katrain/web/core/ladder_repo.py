"""Storage for 41-tier rated play: read a user's ladder state, settle a game.

The rank and its ledger are local-authoritative. `users` is not covered by the
repository dispatcher (which only proxies tsumego / kifu / user_games), so both
sides of a settlement live in one local transaction. The finished game row may
have been written to a remote service; that is why `ai_ladder_ledger.game_id` is
a plain unique string rather than a foreign key.

Nothing here decides strength. It asks `ladder_progress` for the arithmetic and
`ladder_catalog` for the position<->rung mapping, so the rules stay in one place.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List, Optional

from sqlalchemy.exc import IntegrityError

from katrain.core.ladder import LadderUnavailable, get_level, resolve_available_rung
from katrain.web.core import models_db
from katrain.web.core.ladder_catalog import (
    legacy_rank_to_position,
    position_count,
    position_of,
    rank_name,
    rung_at,
)
from katrain.web.core.ladder_progress import (
    NET_WIN_THRESHOLD,
    PLACEMENT_GAMES,
    apply_ladder_result,
    placement_apply,
    placement_opponent,
    placement_settled,
    seed_placement_window,
)

logger = logging.getLogger("katrain_web")

#: Value of `user_games.game_type` that makes a finished game count for the ladder.
#: Server-issued only: it is set from POST /api/ladder/start-game and can never be
#: supplied by a client.
LADDER_GAME_TYPE = "ai_ladder_ranked"

RECENT_GAMES = 5


@dataclass(frozen=True)
class TierRef:
    rung: int
    rank_name: str


@dataclass(frozen=True)
class RecentGame:
    won: bool
    opponent_rung: int
    opponent_rank_name: str


@dataclass(frozen=True)
class PlacementState:
    games_done: int
    games_total: int
    lo: int
    hi: int


@dataclass(frozen=True)
class LadderState:
    """Everything GET /api/ladder/me reports, plus the opponent the server picked."""

    rung: Optional[int]
    rank_name: Optional[str]
    rung_above: Optional[TierRef]
    rung_below: Optional[TierRef]
    net_wins: int
    threshold: int
    placement: Optional[PlacementState]
    recent: List[RecentGame]
    opponent_rung: int
    playable: bool
    blocked_reason: Optional[str]


def _effective_window(user) -> tuple:
    """The placement window, persisted if a placement game has already settled.

    Derived on read rather than written on first view, so a GET never mutates the
    account. It is deterministic from `users.rank`, so the derived value and the
    later persisted one agree.
    """
    if user.ai_ladder_placement_lo is not None and user.ai_ladder_placement_hi is not None:
        return user.ai_ladder_placement_lo, user.ai_ladder_placement_hi
    return seed_placement_window(legacy_rank_to_position(user.rank), position_count())


def _tier_ref(position: int, n: int) -> Optional[TierRef]:
    if not 1 <= position <= n:
        return None
    rung = rung_at(position)
    return TierRef(rung=rung, rank_name=rank_name(rung))


def _opponent_playable(rung: int) -> tuple:
    """(playable, blocked_reason) for seating this rung right now."""
    try:
        resolve_available_rung(rung)
    except LadderUnavailable as exc:
        # `resolve_available_rung` distinguishes "never fitted" from "fitted but
        # not certified"; the UI wording differs, so keep them apart.
        reason = "no_recipe" if "unresolved recipe" in str(exc) else "not_certified"
        return False, reason
    return True, None


def read_state(session, user_id: int) -> LadderState:
    user = session.query(models_db.User).filter(models_db.User.id == user_id).one()
    n = position_count()

    if user.ai_ladder_rung is None:
        lo, hi = _effective_window(user)
        opponent_position = placement_opponent(lo, hi, n)
        opponent_rung = rung_at(opponent_position)
        playable, blocked = _opponent_playable(opponent_rung)
        return LadderState(
            rung=None,
            rank_name=None,
            rung_above=None,
            rung_below=None,
            net_wins=0,
            threshold=NET_WIN_THRESHOLD,
            placement=PlacementState(
                games_done=user.ai_ladder_placement_games or 0,
                games_total=PLACEMENT_GAMES,
                lo=lo,
                hi=hi,
            ),
            recent=[],
            opponent_rung=opponent_rung,
            playable=playable,
            blocked_reason=blocked,
        )

    position = position_of(user.ai_ladder_rung)
    opponent_rung = user.ai_ladder_rung  # placed users play their own tier
    playable, blocked = _opponent_playable(opponent_rung)
    return LadderState(
        rung=user.ai_ladder_rung,
        rank_name=rank_name(user.ai_ladder_rung),
        rung_above=_tier_ref(position + 1, n),
        rung_below=_tier_ref(position - 1, n),
        net_wins=user.ai_ladder_net_wins or 0,
        threshold=NET_WIN_THRESHOLD,
        placement=None,
        recent=_recent_games(session, user_id),
        opponent_rung=opponent_rung,
        playable=playable,
        blocked_reason=blocked,
    )


def _recent_games(session, user_id: int) -> List[RecentGame]:
    """The last few settled games, oldest first. Ledger-derived only -- the strip
    must never imply a promotion rule the ledger does not implement."""
    rows = (
        session.query(models_db.AiLadderLedger)
        .filter(models_db.AiLadderLedger.user_id == user_id)
        .order_by(models_db.AiLadderLedger.id.desc())
        .limit(RECENT_GAMES)
        .all()
    )
    return [
        RecentGame(won=r.won, opponent_rung=r.opponent_rung, opponent_rank_name=rank_name(r.opponent_rung))
        for r in reversed(rows)
    ]


def settle_game(session, user_id: int, game_id: str, opponent_rung: int, won: bool) -> bool:
    """Record one conclusive ladder game and move the rank. Returns False if this
    game_id was already settled.

    The ledger row and the users update commit together: a rank that moved without
    a ledger row would be underivable, and a ledger row without the move would
    double-count on the next game. Idempotency rides on the UNIQUE constraint --
    a replay raises IntegrityError, the transaction rolls back, nothing moves.
    """
    user = session.query(models_db.User).filter(models_db.User.id == user_id).one()
    n = position_count()

    entry = models_db.AiLadderLedger(
        user_id=user_id,
        game_id=game_id,
        opponent_rung=opponent_rung,
        won=won,
        net_wins_before=user.ai_ladder_net_wins or 0,
    )

    if user.ai_ladder_rung is None:
        lo, hi = _effective_window(user)
        lo, hi = placement_apply(lo, hi, won)
        games = (user.ai_ladder_placement_games or 0) + 1
        settled = placement_settled(lo, hi, n)

        entry.is_placement = True
        entry.rung_before = None
        entry.net_wins_after = 0
        entry.placement_lo_after = lo
        entry.placement_hi_after = hi

        user.ai_ladder_placement_lo = lo
        user.ai_ladder_placement_hi = hi
        user.ai_ladder_placement_games = games
        if settled is not None:
            user.ai_ladder_rung = rung_at(settled)
            user.ai_ladder_net_wins = 0
            entry.rung_after = user.ai_ladder_rung
    else:
        position = position_of(user.ai_ladder_rung)
        new_position, new_net = apply_ladder_result(position, user.ai_ladder_net_wins or 0, won, n)
        entry.is_placement = False
        entry.rung_before = user.ai_ladder_rung
        entry.rung_after = rung_at(new_position)
        entry.net_wins_after = new_net

        user.ai_ladder_rung = rung_at(new_position)
        user.ai_ladder_net_wins = new_net

    session.add(entry)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        logger.info("ladder settlement for game %s already recorded; ignoring replay", game_id)
        return False
    return True


def rung_display_name(rung: int) -> str:
    return get_level(rung).rank_name
