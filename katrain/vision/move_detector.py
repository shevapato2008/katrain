"""
Detects newly placed stones by comparing consecutive board states.

Only detects "new stone added" — automatically handles captures (removed opponent stones
are ignored). Provides force_sync() for undo/endgame scenarios.
"""

import numpy as np

from katrain.vision.board_state import EMPTY

# --- per-cell reputation -----------------------------------------------------
# Measured on RK3562 2026-09-20: vision (18,13) produced 69 candidate flashes across
# 3 processes (405 seconds lit) and was auto-confirmed twice at 0.50-0.57 confidence,
# while the device's global add gate was 0.40 and its ambiguous gate 0.42. Raising
# those globals would have blocked it — and would equally have blocked the genuinely
# weak stones the low gates exist for (one real stone never entered its game all day).
# So the extra bar is charged per intersection, to the ones that have actually lied.
# Only ONE signal is charged: a candidate that appeared and then ran out of miss grace
# without confirming. A "confirmed twice in a short window" signal was deliberately NOT
# added — the caller-owned-baseline contract makes an unactioned confirmation re-fire on
# purpose, so penalising repeats would condemn a legitimate weak stone that is waiting on
# the user's confirmation card.
#
# Fix round 1: a suspect cell's EXTRA BAR IS THE AMBIGUOUS ROUTING GATE ONLY (applied by
# the workers via SUSPECT_CONFIDENCE_BONUS) — never the confirmation frame count. An
# earlier version doubled required_frames here for a suspect cell; that was wrong,
# because "abandonment is what a real stone never does" is false — the class docstring's
# own miss_grace paragraph says a marginal-confidence stone blinks out for a frame or
# two, so a weak real stone oscillating near the keep gate produces exactly the abandon
# signature this module charges, which is the measured profile of that day's own F2
# casualties (a real stone that never entered its game). Worse, the frame count gates
# detect_new_move's return value, which sits upstream of BOTH auto-play and the
# ambiguous card (the promoter only runs when no candidate is pending at all) — so a
# suspect cell that could never assemble the doubled count confirmed nowhere, ever: the
# silent, permanent loss the fix was meant to prevent, manufactured by the fix itself.
# The routing gate alone is sufficient against the measured event: real confirmed moves
# on this box peak at p25=0.72 (config_service.py), the (18,13) phantom auto-confirmed
# at 0.50 and 0.57 (already its peak values), and 0.42 + 0.25 = 0.67 sits strictly
# between the two — so the phantom is routed to the card deterministically, and the
# large majority of real moves still clear the routing gate and auto-play; a real move
# too weak to clear it still reaches the user via the card, never vanishes. Accrual
# (~1 point per abandon cycle, every >= miss_grace + 2 frames) outruns decay (1 point
# per 300 frames) for a cell that keeps producing candidates, so such a cell stays
# suspect indefinitely — that is now fine, because the only cost of staying suspect is
# a confirmation tap, never a lost move.
SUSPICION_ABANDON = 1  # became a candidate, then vanished without confirming
SUSPICION_THRESHOLD = 3  # at or above this, the cell is suspect
SUSPICION_DECAY_FRAMES = 300  # every N frames every cell loses a point
SUSPECT_CONFIDENCE_BONUS = 0.25  # extra the ambiguous gate demands from a suspect cell (workers only)

# Simultaneous diffs at or above this count are scene disruption (a hand sweeping
# across the board, the board being moved), not "a phantom next to a real stone".
# Below it, every changed cell is simply its own candidate. The old rule was
# `> 1` — which made the WHOLE BOARD the criterion for whether YOUR move counts,
# and on RK3562 2026-09-20 one persistent edge phantom kept a real stone from ever
# entering its game.
DISRUPTION_THRESHOLD = 4


class MoveDetector:
    """Detects new moves by comparing board states across frames.

    ``miss_grace``: a marginal-confidence stone can blink out of the observed board for
    a frame or two (a confidence dip or a cell-rounding wobble absorbed by voting); a
    zero-tolerance counter would reset on every blink and NEVER accumulate
    ``consistency_frames``, leaving the stone permanently unconfirmable. A pending move
    therefore survives up to ``miss_grace`` consecutive absent frames with its count
    frozen; only a longer absence (stone actually removed / noise gone) abandons it.
    Changes at or above ``disruption_threshold`` cells in one frame still hard-reset —
    that is scene disruption, not flicker. Below it every changed cell is its own
    candidate with its own streak, so a phantom elsewhere on the board can no longer
    starve a real move (RK3562 2026-09-20: it starved one for an entire game).

    THE CALLER OWNS THE BASELINE: ``detect_new_move`` does NOT advance ``prev_board``
    when it confirms — call ``force_sync()`` once the move has actually been accepted
    downstream. Advancing at confirm time silenced detection permanently whenever the
    confirmed move was then diverted (low-confidence prompt the user never answered,
    out-of-turn rejection, gateway rejection): the baseline already contained the
    stone, no game update ever arrived to re-sync it, and no move could fire again.
    An unactioned confirm therefore re-fires every ``consistency_frames`` frames;
    callers gate re-emission (cooldowns) rather than losing the move forever.
    """

    def __init__(
        self, consistency_frames: int = 3, miss_grace: int = 2, disruption_threshold: int = DISRUPTION_THRESHOLD
    ):
        self.consistency_frames = consistency_frames
        self.miss_grace = miss_grace
        self.disruption_threshold = disruption_threshold
        self.prev_board: np.ndarray | None = None
        # (row, col, color) -> {"count": int, "misses": int, "first_seen": int}
        self._candidates: dict[tuple[int, int, int], dict[str, int]] = {}
        self._suspicion: dict[tuple[int, int], int] = {}
        self._frame_index = 0

    def _leader(self) -> tuple[int, int, int] | None:
        """Candidate closest to confirming: longest streak, oldest first-seen breaks ties."""
        if not self._candidates:
            return None
        return min(
            self._candidates,
            key=lambda k: (-self._candidates[k]["count"], self._candidates[k]["first_seen"]),
        )

    @property
    def pending_move(self) -> tuple[int, int, int] | None:
        """The leading candidate. Read by both workers every frame (confidence-peak
        tracking and the "confirming" chip). Read-only on purpose: there is now more
        than one candidate, so any assignment site would be a bug."""
        return self._leader()

    @property
    def count(self) -> int:
        """Consecutive sightings of the leading candidate."""
        leader = self._leader()
        return 0 if leader is None else self._candidates[leader]["count"]

    def _penalize(self, cell: tuple[int, int], points: int) -> None:
        self._suspicion[cell] = self._suspicion.get(cell, 0) + points

    def _decay_suspicion(self) -> None:
        """Every cell loses one point, every SUSPICION_DECAY_FRAMES frames.

        Frames, not wall-clock: what is being decayed is "how many chances has this
        cell had to lie", which is counted in observations. (Contrast the missing-stone
        hold in SyncStateMachine, which measures real elapsed occlusion and therefore
        must use wall-clock.)
        """
        for cell in list(self._suspicion):
            if self._suspicion[cell] <= 1:
                del self._suspicion[cell]
            else:
                self._suspicion[cell] -= 1

    def suspicion_of(self, row: int, col: int) -> int:
        """Accumulated evidence that this intersection produces candidates that are not moves."""
        return self._suspicion.get((row, col), 0)

    def is_suspect(self, row: int, col: int) -> bool:
        return self.suspicion_of(row, col) >= SUSPICION_THRESHOLD

    def reset_suspicion(self) -> None:
        """Clear all reputation state — session UNBIND only.

        Deliberately NOT called from force_sync: force_sync runs on every
        expected-board push (several times a second while the engine streams), so
        clearing there would mean the counter could never accumulate.
        """
        self._suspicion.clear()

    def detect_new_move(
        self, board: np.ndarray, ignore_cells: set | None = None, *, required_frames: int | None = None
    ) -> tuple[int, int, int] | None:
        """
        Compare current board with previous accepted state.

        ``required_frames``: how many sightings confirm THIS move, overriding
        ``consistency_frames`` for this call only. The caller passes a smaller number
        when it can already see the stone clearly (see the confidence-adaptive gate in
        the workers). None — including "the caller has no confidence reading yet" —
        keeps the full ``consistency_frames``: an unknown stone is a weak stone, and the
        slow path is the safe one. The value is read fresh on every frame rather than
        stored, so a candidate whose confidence decays mid-window is held to the longer
        count instead of being confirmed on the strength of one good early frame.

        ``ignore_cells``: (row, col) intersections that can never be a new move — the
        frame's removal-lit ∩ expected-empty mask. A stone physically sitting on a
        just-captured / removal-lit point is a leftover the system is asking the user to
        REMOVE, not a placement; treating it as an addition re-injects a phantom move onto
        the captured point. The mask is re-derived every frame, so it protects durably even
        after the streaming SET_EXPECTED_BOARD force-syncs ``prev_board`` back to the bare
        digital board (which would otherwise resurrect the leftover as an EMPTY→stone diff).

        Returns:
            (row, col, color) if a single new stone is confirmed, None otherwise.
            Only detects stones added to empty positions (captures are ignored).
        """
        self._frame_index += 1
        if self._frame_index % SUSPICION_DECAY_FRAMES == 0:
            self._decay_suspicion()

        if self.prev_board is None:
            self.prev_board = board.copy()
            return None

        # Find positions where a stone was added to a previously empty intersection
        diff_positions = []
        for r in range(board.shape[0]):
            for c in range(board.shape[1]):
                if ignore_cells and (r, c) in ignore_cells:
                    continue
                if self.prev_board[r][c] == EMPTY and board[r][c] != EMPTY:
                    diff_positions.append((r, c, int(board[r][c])))

        if len(diff_positions) >= self.disruption_threshold:
            # Scene disruption: abandon everything, and charge nobody — this is not
            # any one cell's fault.
            self._candidates.clear()
            return None

        # `required_frames` is evidence about ONE stone: the caller measured the
        # confidence peak of whichever cell was leading when it called (the workers read
        # peak_for(pending_move) immediately before this call). Capture that cell BEFORE
        # the candidate update, and let only it use the shortcut — otherwise a confident
        # real stone hands its 3-frame fast path to a weak phantom sharing the frame, and
        # the phantom auto-plays two frames early.
        #
        # Note (fix round 1): this restriction is kept as a cheap invariant, not as a
        # tested branch. Before the suspect frame-count multiplier was removed, a suspect
        # leader could need MORE sightings than the shortcut granted, so a non-leader
        # candidate confirming on the leader's shortcut was an observable leak
        # (test_the_fast_path_is_not_lent_to_another_candidate, dropped in fix round 1).
        # Without the multiplier, `fast_cell` is captured once per call as whichever key
        # already has the highest count (ties broken by first_seen) BEFORE this frame's
        # counts are bumped, and `ready` is later sorted the same way — so a non-leader
        # key can never reach a count that lets it overtake the leader within the same
        # call, whether or not it were (wrongly) granted the shortcut. The restriction
        # still guards against a future change to that ordering; it just has no scenario
        # left in this file that can distinguish "restriction present" from "restriction
        # removed".
        #
        # Controller amendment (2026-09-21): the paragraph above is only half the story.
        # `ready` is built from `current` (this frame's diffs) but `fast_cell` is taken
        # from ALL candidates, including ones absent this frame but still inside
        # miss_grace. So a miss-graced leader that is absent THIS frame is not in
        # `ready` at all, leaving a second candidate alone in it — eligible for a
        # fast-path allowance that was measured on a different stone entirely. See
        # test_fast_path_not_lent_to_a_miss_graced_leaders_neighbor, which reproduces
        # this with the plain constants (no suspicion involved).
        fast_cell = self._leader()

        current = {(r, c, clr) for r, c, clr in diff_positions}

        # Age out candidates that are not visible this frame. A marginal stone blinks,
        # so a short absence only freezes the streak (miss_grace); a longer one
        # abandons the candidate and charges that cell a point of suspicion.
        for key in list(self._candidates):
            if key in current:
                continue
            cand = self._candidates[key]
            cand["misses"] += 1
            if cand["misses"] > self.miss_grace:
                self._penalize((key[0], key[1]), SUSPICION_ABANDON)
                del self._candidates[key]

        for key in current:
            cand = self._candidates.get(key)
            if cand is None:
                self._candidates[key] = {"count": 1, "misses": 0, "first_seen": self._frame_index}
            else:
                cand["count"] += 1
                cand["misses"] = 0

        if not current:
            return None

        fast_needed = self.consistency_frames if required_frames is None else max(1, int(required_frames))
        ready = []
        for key in current:
            # Fix round 1 (Task 3) removed the suspect frame-count multiplier: it gated
            # detect_new_move's return, which sits upstream of BOTH auto-play and the
            # ambiguous card, so a suspect cell that could not assemble enough sightings
            # confirmed nowhere at all — silent loss, the worst F2 outcome, manufactured
            # by the F1 fix. A suspect cell now confirms on the same count as an honest
            # one; only the workers' post-confirmation ambiguous-routing gate (raised by
            # SUSPECT_CONFIDENCE_BONUS) decides auto-play vs. card. Do not reintroduce an
            # `is_suspect` check here.
            needed = fast_needed if key == fast_cell else self.consistency_frames
            if self._candidates[key]["count"] >= needed:
                ready.append(key)
        if not ready:
            return None

        ready.sort(key=lambda k: (-self._candidates[k]["count"], self._candidates[k]["first_seen"]))
        move = ready[0]
        if len(ready) > 1:
            runner_up = ready[1]
            lead, second = self._candidates[move], self._candidates[runner_up]
            if lead["count"] == second["count"] and lead["first_seen"] == second["first_seen"]:
                # Two stones that appeared on the same frame and advanced in lockstep is
                # genuine ambiguity, not a phantom beside a real stone. Emit nothing.
                return None

        # Baseline deliberately NOT advanced (see class docstring): the caller
        # force_syncs once the move is actually accepted downstream.
        del self._candidates[move]
        return move

    def force_sync(self, board: np.ndarray) -> None:
        """Force-update the reference board (for undo, endgame cleanup, manual reset).

        Clears candidates but NOT reputation — force_sync runs on every expected-board
        push, so clearing reputation here would mean it never accumulates. Use
        reset_suspicion() for that.
        """
        self.prev_board = board.copy()
        self._candidates.clear()


class PendingConfidencePeak:
    """Peak cell-confidence of the current pending move across its confirmation window.

    A marginal stone's per-frame confidence oscillates around the ambiguous gate
    (far-side stones on the Mac rig confirm at 0.32-0.53 instantaneous), so gating
    card-vs-autoplay on the single confirm-frame value is a coin flip. The peak over
    the whole multi-frame window is the best view the detector ever had of the stone
    and is far more stable — gate on that instead.

    Scoped to ONE window: the peak resets whenever the pending cell changes or clears,
    so state never goes stale across moves. Cross-cell leaks are impossible — a confirm
    requires the same cell pending for the entire window, and ``gate_confidence`` only
    applies the peak to that cell. An unbacked (spill-assigned) cell never appears in
    conf_map, so its peak stays 0.0 and it still routes to the ambiguous dialog.
    """

    def __init__(self) -> None:
        self._cell: tuple[int, int] | None = None
        self._peak: float = 0.0

    def observe(self, pending: tuple | None, conf_map: dict) -> None:
        """Feed one frame: the current pending move (before detect_new_move) + cell confidences."""
        if pending is None:
            self._cell = None
            self._peak = 0.0
            return
        cell = (pending[0], pending[1])
        if cell != self._cell:
            self._cell = cell
            self._peak = 0.0
        conf = conf_map.get(cell, 0.0)
        if conf > self._peak:
            self._peak = conf

    def gate_confidence(self, row: int, col: int, instant_conf: float) -> float:
        """Confidence to compare against the ambiguous gate: max(instant, window peak)."""
        if self._cell == (row, col):
            return max(instant_conf, self._peak)
        return instant_conf

    def peak_for(self, pending: tuple | None) -> float | None:
        """Window peak for ``pending``, or None when this window is about someone else.

        None means "no reading", which callers must treat as "not confident" rather than
        as a zero — the confidence-adaptive confirmation gate relies on that distinction
        to keep an unmeasured stone on the slow path.
        """
        if pending is None or self._cell != (pending[0], pending[1]):
            return None
        return self._peak


class AmbiguousPromoter:
    """Promotes a persistently sub-add-confidence stone to a user confirmation prompt.

    Confidence hysteresis gives a real stone that never crosses the ADD threshold no
    path onto the board: keep-tier detections may only sustain existing stones. A real
    stone persists frame after frame, while glare/noise flickers — so a cell whose
    sub-add detection survives ``promote_frames`` CONSECUTIVE frames is worth asking
    the user about (ambiguous_stone -> AmbiguousMoveCard -> confirm plays the move).

    ``step()`` is fed the per-frame candidate cells (already filtered by the worker to
    sub-add confidence, empty in the stable and expected boards, unmasked). It returns
    at most one ``(row, col, class_id, confidence)`` per call; an emitted cell enters a
    ``cooldown_frames`` cooldown so a declined prompt doesn't immediately re-fire.

    ``miss_grace``: like MoveDetector, a marginal stone blinks — a cell absent for up to
    this many consecutive frames keeps its streak frozen instead of restarting from 0.
    """

    def __init__(self, promote_frames: int = 12, cooldown_frames: int = 120, miss_grace: int = 2):
        self.promote_frames = promote_frames
        self.cooldown_frames = cooldown_frames
        self.miss_grace = miss_grace
        self._streaks: dict[tuple[int, int], int] = {}
        self._misses: dict[tuple[int, int], int] = {}
        self._cooldowns: dict[tuple[int, int], int] = {}

    def step(self, candidates: dict) -> tuple[int, int, int, float] | None:
        """Feed one frame's candidate cells {(r,c): (confidence, class_id)}."""
        for cell in list(self._cooldowns):
            self._cooldowns[cell] -= 1
            if self._cooldowns[cell] <= 0:
                del self._cooldowns[cell]

        for cell in list(self._streaks):
            if cell in candidates:
                continue
            self._misses[cell] = self._misses.get(cell, 0) + 1
            if self._misses[cell] > self.miss_grace:
                del self._streaks[cell]
                del self._misses[cell]
        for cell in candidates:
            self._streaks[cell] = self._streaks.get(cell, 0) + 1
            self._misses.pop(cell, None)

        # Only cells PRESENT this frame may fire (a graced-absent cell must reappear
        # first — never prompt for something not currently detected).
        ready = [c for c in candidates if self._streaks.get(c, 0) >= self.promote_frames and c not in self._cooldowns]
        if not ready:
            return None
        # One prompt at a time: longest streak wins, confidence breaks ties.
        cell = max(ready, key=lambda c: (self._streaks[c], candidates[c][0]))
        conf, class_id = candidates[cell]
        self._cooldowns[cell] = self.cooldown_frames
        self._streaks.pop(cell, None)
        self._misses.pop(cell, None)
        return (cell[0], cell[1], class_id, conf)

    def reset(self) -> None:
        """Clear all state (session unbind / sync reset — a declined prompt resets sync)."""
        self._streaks.clear()
        self._misses.clear()
        self._cooldowns.clear()
