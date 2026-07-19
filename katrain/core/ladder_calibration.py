"""Pure calibration primitives: fail-closed engine-agnostic game loop + Elo math. No
network, no engine coupling. Ambiguous outcomes -> inconclusive (never a win)."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Awaitable, Callable, List, Optional, Tuple, Union

MoveVal = Union[int, str]  # our_move: int|"pass"|"unavailable"; golaxy_move: int|"pass"|"resign"|"terminal"


def elo_from_winrate(wins: float, conclusive_games: int) -> Tuple[float, float, float]:
    if conclusive_games <= 0:
        return (0.0, float("-inf"), float("inf"))
    p = wins / conclusive_games
    eps = 1.0 / (2 * conclusive_games + 2)

    def elo(x):
        x = min(1 - 1e-9, max(1e-9, x))
        return -400.0 * math.log10(1.0 / x - 1.0)

    pc = min(1 - eps, max(eps, p))
    se = math.sqrt(max(pc * (1 - pc), eps) / conclusive_games)
    return (elo(pc), elo(min(1 - eps, max(eps, pc - 1.96 * se))), elo(min(1 - eps, max(eps, pc + 1.96 * se))))


@dataclass
class GameOutcome:
    our_color: str
    result: str  # our_win|our_loss|inconclusive_score|inconclusive_unsettled|inconclusive_engine|inconclusive_terminal
    our_win: bool
    num_moves: int
    black_score: Optional[float]
    conclusive: bool
    end_reason: str = "move_cap"  # our_pass | golaxy_pass | golaxy_resign | golaxy_terminal | move_cap


async def play_one_game(
    *,
    our_move: Callable[[List[int]], Awaitable[MoveVal]],
    golaxy_move: Callable[[List[int]], Awaitable[MoveVal]],
    adjudicate: Callable[[List[int]], Awaitable[Tuple[Optional[float], bool]]],
    our_color: str,
    board_size: int = 19,
    move_cap: int = 400,
) -> GameOutcome:
    """Alternate our engine & Golaxy on a shared history of ONLY valid Golaxy wire coords
    (NO sentinel ever appended; G1). Trust only VERIFIED stops (H1): our-'pass' and a
    smoke-verified golaxy-'pass' adjudicate; a verified golaxy-'resign' is our win; an
    UNVERIFIED golaxy-'terminal' (out-of-board/malformed) is inconclusive_terminal — never
    scored. our-'unavailable' -> inconclusive_engine. move_cap -> adjudicate."""
    history: List[int] = []  # valid Golaxy wire coords only
    to_play = "B"
    end_reason = "move_cap"

    for _ in range(move_cap):
        is_our_turn = to_play == our_color
        val = await (our_move if is_our_turn else golaxy_move)(history)
        if val == "unavailable":  # our_move only: no certified move -> inconclusive
            return GameOutcome(our_color, "inconclusive_engine", False, len(history), None, False, "our_pass")
        if val == "resign":  # golaxy_move only, VERIFIED: opponent conceded -> our win
            return GameOutcome(our_color, "our_win", True, len(history), None, True, "golaxy_resign")
        if val == "terminal":  # golaxy_move only, UNVERIFIED/malformed -> never scored
            return GameOutcome(our_color, "inconclusive_terminal", False, len(history), None, False, "golaxy_terminal")
        if val == "pass":  # our-pass (trusted) OR golaxy verified-pass -> adjudicate
            end_reason = "our_pass" if is_our_turn else "golaxy_pass"
            break
        history.append(int(val))  # guaranteed a real wire coord
        to_play = "W" if to_play == "B" else "B"

    black_score, settled = await adjudicate(history)
    if black_score is None or not math.isfinite(black_score):
        return GameOutcome(our_color, "inconclusive_score", False, len(history), None, False, end_reason)
    if not settled:
        return GameOutcome(our_color, "inconclusive_unsettled", False, len(history), black_score, False, end_reason)
    winner = "B" if black_score > 0 else "W"
    our_win = winner == our_color
    return GameOutcome(
        our_color, "our_win" if our_win else "our_loss", our_win, len(history), black_score, True, end_reason
    )
