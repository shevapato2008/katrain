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

#: The board every rung was measured on. Fixed here rather than taken from the
#: request, for the same reason the rung is: a rung's rank name describes its
#: strength in a 19x19 Chinese-rules 7.5-komi game and nothing else (every
#: calibration campaign ran exactly that -- see
#: superpowers/tracks/golaxy-ai-ladder-parity/calibration/run_selfplay.py), so a
#: client that could ask for 9x9 would be seating an opponent whose measured
#: strength no longer describes the game being played, and banking the result.
#: The player still chooses their seat and their clock.
LADDER_BOARD_SIZE = 19
LADDER_RULES = "chinese"
LADDER_KOMI = 7.5

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
class Settlement:
    """What one settled game did to the rank. Returned by `settle_game` so the
    caller can tell the user, rather than re-deriving a delta from two reads.

    `rung_before` is None during placement (there is no rank yet); `rung_after` is
    None during placement until the search collapses on the last game.
    """

    won: bool
    is_placement: bool
    net_wins_before: int
    net_wins_after: int
    threshold: int
    rung_before: Optional[int]
    rung_after: Optional[int]
    placement_games_done: Optional[int]
    placement_games_total: Optional[int]

    @property
    def moved(self) -> int:
        """+1 promoted, -1 demoted, 0 stayed. Placement games never 'move'."""
        if self.is_placement or self.rung_before is None or self.rung_after is None:
            return 0
        return (position_of(self.rung_after) > position_of(self.rung_before)) - (
            position_of(self.rung_after) < position_of(self.rung_before)
        )


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


def settle_game(session, user_id: int, game_id: str, opponent_rung: int, won: bool) -> Optional[Settlement]:
    """Record one conclusive ladder game and move the rank. Returns what it did,
    or None if this game_id was already settled.

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
    rung_before = user.ai_ladder_rung

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
        return None
    return Settlement(
        won=won,
        is_placement=entry.is_placement,
        net_wins_before=entry.net_wins_before,
        net_wins_after=entry.net_wins_after,
        threshold=NET_WIN_THRESHOLD,
        rung_before=rung_before,
        rung_after=entry.rung_after,
        placement_games_done=user.ai_ladder_placement_games if entry.is_placement else None,
        placement_games_total=PLACEMENT_GAMES if entry.is_placement else None,
    )


def rung_display_name(rung: int) -> str:
    return get_level(rung).rank_name
