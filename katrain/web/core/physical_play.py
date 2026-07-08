"""Physical-play LED planning: pure diff between the authoritative digital board
and the observed physical board. No I/O, no clocks — fully unit-testable.

LED semantics (PRD D2): missing digital stone -> stone-color lamp (black stone ->
red LED "black", white -> green LED "white"); stone that must come off -> blue
("remove"). One set_points batch mixes colors (LedService batches are clear+set).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

import numpy as np

EMPTY, BLACK, WHITE = 0, 1, 2
STONE_LED_COLOR = {BLACK: "black", WHITE: "white"}


@dataclass
class PhysicalPlayConfig:
    tick_interval_s: float = 0.5
    reminder_after_s: float = 30.0  # Q4: nag toast when board lags the game
    escalate_after_s: float = 120.0  # review B: escape-hatch dialog when still lagging
    led_reassert_interval_s: float = 240.0  # review A: re-send lamps before the 300s idle failsafe
    extra_stone_debounce_ticks: int = 6  # ~3s at default tick before an unexpected stone gets blue
    hint_top_n: int = 3  # Q2 defaults
    hint_blink_period_s: float = 0.8
    hint_timeout_s: float = 30.0
    hint_max_visits: int = 100
    hint_engine: str = "cloud"  # "local" | "cloud" | "off" — 支招 is an analysis query, so
    # prefer the strong cloud GPU; RequestRouter degrades to local when CLOUD_KATAGO_URL is unset.


@dataclass
class LedPlan:
    points: List[Dict]  # ready for LedService.set_points(...)
    caught_up: bool  # nothing left to place/remove (Q4 gate)
    to_place: Set[Tuple[int, int]] = field(default_factory=set)
    to_remove: Set[Tuple[int, int]] = field(default_factory=set)


class LedPlanner:
    """Tracks expected-board transitions and computes the LED batch each tick.

    Coordinates are vision-grid (row 0 = top), identical to the LED LUT convention.
    """

    def __init__(self, config: PhysicalPlayConfig):
        self.config = config
        self._prev_expected: Optional[np.ndarray] = None
        self._removal_pending: Set[Tuple[int, int]] = set()
        self._extra_counts: Dict[Tuple[int, int], int] = {}
        # Guidance scope: placement lamps light ONLY for stones the human has not yet
        # physically placed — AI moves and root-setup (handicap) stones. A human's own
        # move was necessarily observed by vision (that observation IS the move source),
        # so its cell lands in _observed_once immediately and never lights. This also
        # breaks the lamp-glare feedback loop (red lamp under a black stone reads as
        # led_red -> stone "missing" -> lamp stays on) for human stones entirely.
        self._observed_once: Set[Tuple[int, int]] = set()
        self._guided_colors: Optional[Set[int]] = None  # None = no player info: guide all colors
        self._setup_cells: Set[Tuple[int, int]] = set()

    def reset(self) -> None:
        self._prev_expected = None
        self._removal_pending = set()
        self._extra_counts = {}
        self._observed_once = set()
        self._guided_colors = None
        self._setup_cells = set()

    def reconcile(self, expected: np.ndarray) -> None:
        """Manual recovery (resync): drop stuck removal / extra-debounce state and
        re-baseline to the CURRENT digital board, WITHOUT wiping placement tracking.

        An un-clearable removal — a physical stone the camera keeps seeing at a
        captured/undone point (LED glare or a white false-negative) — otherwise keeps
        `_removal_pending` non-empty forever, so `caught_up` never returns True and the
        orchestrator leaves move detection paused (the kiosk "确认中" deadlock). After
        reconcile the still-present stone degrades to a non-blocking cleanup extra
        (debounced blue lamp, excluded from the caught_up gate).

        `_observed_once` / `_guided_colors` / `_setup_cells` are preserved so
        already-placed stones don't spuriously re-light as placement targets."""
        self._prev_expected = expected.copy()
        # Carry each still-pending removal PAST the debounce so it re-surfaces as a blue
        # cleanup extra on the very next tick. Otherwise it re-enters tick() as a raw extra
        # with count 0, and a lone HUMAN-color survivor (the common "AI captured my single
        # stone" case) is swallowed by the single-human-color "move-in-flight" exemption —
        # whose guard `count < debounce` stays True forever because the count is rebuilt
        # from the emptied `extras` every tick — so its removal lamp would be suppressed
        # permanently instead of "degraded to a debounced blue lamp" as promised above.
        self._extra_counts = {p: self.config.extra_stone_debounce_ticks for p in self._removal_pending}
        self._removal_pending = set()

    def set_context(self, guided_colors: Optional[Set[int]], setup_cells: Set[Tuple[int, int]]) -> None:
        """Player context from the game state: which stone colors are AI-played (need
        placement lamps) and which cells are root-setup stones (handicap — always guided,
        regardless of color). guided_colors None means unknown -> guide everything."""
        self._guided_colors = guided_colors
        self._setup_cells = setup_cells

    def on_expected(self, expected: np.ndarray) -> None:
        """Record a new authoritative board. Stones that vanished from the digital
        board (captures, undo) become removal-pending; re-occupied points cancel."""
        if self._prev_expected is not None:
            gone = (self._prev_expected != EMPTY) & (expected == EMPTY)
            for r, c in zip(*np.nonzero(gone)):
                self._removal_pending.add((int(r), int(c)))
            # A NEW digital stone re-arms guidance for its cell: forget any stale
            # observation (e.g. the cell held a different stone earlier in the game).
            fresh = (self._prev_expected == EMPTY) & (expected != EMPTY)
            for r, c in zip(*np.nonzero(fresh)):
                self._observed_once.discard((int(r), int(c)))
        self._removal_pending = {p for p in self._removal_pending if expected[p] == EMPTY}
        self._prev_expected = expected.copy()

    def _needs_guidance(self, expected: np.ndarray, p: Tuple[int, int]) -> bool:
        if p in self._setup_cells:
            return True  # handicap / root-setup stones are guided regardless of color
        if self._guided_colors is None:
            return True  # no player info -> legacy behavior (guide all colors)
        return int(expected[p]) in self._guided_colors

    def tick(self, expected: np.ndarray, observed: np.ndarray) -> LedPlan:
        # A pending removal is done once the stone is physically gone.
        self._removal_pending = {p for p in self._removal_pending if observed[p] != EMPTY}

        # A guidance target seen occupied (any stone class — wrong color surfaces via the
        # sync anomaly flow, not a standing lamp) is satisfied FOREVER: a later vision
        # flicker on that cell must not relight the lamp. Real disappearance is handled
        # by the independent sync missing_anomaly -> mismatch-dialog path.
        for r, c in zip(*np.nonzero((expected != EMPTY) & (observed != EMPTY))):
            self._observed_once.add((int(r), int(c)))

        # Placement guidance: digital stone on an EMPTY physical point, never yet
        # observed placed, and within guidance scope (AI colors + setup cells).
        missing = {(int(r), int(c)) for r, c in zip(*np.nonzero((expected != EMPTY) & (observed == EMPTY)))}
        to_place = {p for p in missing if p not in self._observed_once and self._needs_guidance(expected, p)}

        # Unexpected stones (never in the digital board) debounce into blue cleanup lamps
        # — covers leftover stones at game start. Suspended entirely while a placement is
        # pending (Q4 redesign): the user's premature stone must never get a 'remove' lamp
        # while they still owe the AI's stone.
        if to_place:
            self._extra_counts = {}
            debounced: Set[Tuple[int, int]] = set()
        else:
            extras = {
                (int(r), int(c)) for r, c in zip(*np.nonzero((expected == EMPTY) & (observed != EMPTY)))
            } - self._removal_pending
            # A SINGLE unexpected stone of a HUMAN color is (with overwhelming likelihood)
            # the player's own move racing through confirmation — a cleanup lamp here is
            # not just wrong, it used to be fatal: the lamp's cell was masked from vision,
            # the stone vanished from the observed board, stopped being an extra, the lamp
            # went out, the stone came back... an oscillation that kept the first move of
            # a game permanently unregistrable. AI-color extras and multi-stone piles are
            # genuine cleanup situations and still lamp. The exemption only applies to a
            # stone that has NOT already crossed the debounce as part of a cleanup pile:
            # when the user clears a multi-stone pile down to one, the survivor keeps its
            # lamp instead of suddenly being reinterpreted as a "move".
            if self._guided_colors is not None and len(extras) == 1:
                p = next(iter(extras))
                if (
                    int(observed[p]) not in self._guided_colors
                    and self._extra_counts.get(p, 0) < self.config.extra_stone_debounce_ticks
                ):
                    extras = set()
            self._extra_counts = {p: self._extra_counts.get(p, 0) + 1 for p in extras}
            debounced = {p for p, n in self._extra_counts.items() if n >= self.config.extra_stone_debounce_ticks}

        to_remove = self._removal_pending | debounced

        points = [{"row": r, "col": c, "color": STONE_LED_COLOR[int(expected[r][c])]} for r, c in sorted(to_place)] + [
            {"row": r, "col": c, "color": "remove"} for r, c in sorted(to_remove)
        ]

        # Debounced extras guide cleanup but don't block move injection (Q4 gate).
        caught_up = not to_place and not self._removal_pending
        return LedPlan(points=points, caught_up=caught_up, to_place=to_place, to_remove=to_remove)
