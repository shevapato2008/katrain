"""
Combines stone detection results with coordinate mapping to produce a 19x19 board state.

Two assignment modes:
- legacy (occupancy_aware=False): each detection independently round()s to the nearest
  intersection; same-cell collisions resolved by highest confidence (loser dropped).
- occupancy-aware (occupancy_aware=True): detections are assigned greedily to the nearest
  EMPTY intersection (by sub-cell distance), so a collided detection is reassigned to its
  nearest empty neighbor instead of being silently lost. This is the two-step design's
  step 2; the temporal "one new stone on an empty point" constraint lives in MoveDetector.
"""

import math

import numpy as np

from katrain.vision.classes import STONE_CLASS_IDS
from katrain.vision.config import BoardConfig
from katrain.vision.coordinates import apply_parallax, continuous_grid_pos, pixel_to_physical
from katrain.vision.parallax import ParallaxParams
from katrain.vision.stone_detector import Detection

EMPTY = 0
BLACK = 1
WHITE = 2

# Detections that collide on an already-claimed intersection are spilled to the nearest empty
# neighbour only if at least this confident (a sloppily-placed real stone); a weaker collider is
# treated as a duplicate/false positive and dropped, so it can't manufacture a phantom stone.
SPILL_MIN_CONFIDENCE = 0.6

# Sticky assignment: a detection whose continuous position sits within this many cells of a
# same-color stone in the PREVIOUS raw observed board snaps to that cell instead of rounding.
# A stone placed near a cell boundary otherwise alternates cells frame-to-frame (measured
# bimodal ~0.4-cell box sway), and the per-cell 2-frame voting then never stabilizes it.
# Genuinely adjacent stones sit >= 1.0 cells apart, safely outside this radius.
STICKY_RADIUS = 0.65

# Presence sustain: stones do not vanish into thin air. A cell holding a stone in the last
# STABLE board keeps it as long as ANY detection (any class — the model intermittently
# misreads a dark stone as led_red or flips its color for a few frames, and LED classes are
# excluded from occupancy) sits within this radius. Only a true removal — no detection near
# the cell at all — lets the stone leave the board via the normal voting flow.
SUSTAIN_RADIUS = 0.6

# Colour invariant: an established stone does not change colour. Measured on RK3562
# 2026-09-20: 65 colour flips on already-placed points in a single game, one point
# (vision (17,15)) flipping 41 times over 27 minutes, 8 of which reached the client
# as "the board does not match the game". The digital board held one colour throughout.
#
# The release window matters as much as the invariant. sync.py's wrong-colour branch is
# the ONLY way the system can tell the user "you placed the wrong colour there", and it
# is live today. A disagreement that PERSISTS this many consecutive frames is therefore
# let through, so that branch stays reachable — one frame of the other colour is noise,
# several seconds of it is a real wrong-colour placement.
COLOR_FLIP_RELEASE_FRAMES = 15


def _nearest_empty_cell(board: np.ndarray, fy: float, fx: float, max_r: int = 1):
    """Empty cell nearest the continuous position (fy=row, fx=col), searching a
    (2*max_r+1)^2 box around the rounded cell. None if every candidate is occupied."""
    gs = board.shape[0]
    cy = max(0, min(gs - 1, int(round(fy))))
    cx = max(0, min(gs - 1, int(round(fx))))
    best = None
    best_d = None
    for dy in range(-max_r, max_r + 1):
        for dx in range(-max_r, max_r + 1):
            ny, nx = cy + dy, cx + dx
            if 0 <= ny < gs and 0 <= nx < gs and board[ny][nx] == EMPTY:
                d = (ny - fy) ** 2 + (nx - fx) ** 2
                if best is None or d < best_d:
                    best_d = d
                    best = (ny, nx)
    return best


class BoardStateExtractor:
    """Converts a list of stone detections into a board state matrix."""

    def __init__(self, config: BoardConfig | None = None, parallax: ParallaxParams | None = None):
        self.config = config or BoardConfig()
        # Stone-parallax correction (vision-stone-parallax track). Only the geometry-lock extractor
        # ever gets one: the nadir is calibrated in that warp's grid, and the BoardFinder warp uses a
        # different basis. None = off, bit-identical to the pre-parallax behaviour.
        self.parallax = parallax
        # (row, col) -> consecutive frames this established cell has been read as the
        # other colour. Instance state, so it only applies to the occupancy-aware path
        # and only to the extractor instance actually in use. worker.py holds a single
        # instance, so this is moot there. worker_inprocess.py (the one that actually
        # runs on the RK3562) holds two instances (margin-aware for the geometry-lock
        # warp, plain for the BoardFinder fallback) and picks one per frame via
        # _active_extractor(), keyed on self._geometry — which DOES change mid-game:
        # GeometryCalibrationService's always-on drift monitor calls invalidate_geometry()
        # on a detected board/camera bump, not just at startup. The consequence is
        # bounded: on a switch, the other instance's streak/released state starts fresh,
        # so colour protection restarts rather than getting stuck suppressed or stuck
        # released.
        self._color_flip_streak: dict[tuple[int, int], int] = {}
        # Cells whose flip has been released and must KEEP being released until the
        # caller's stable board adopts the new colour — the workers need two consecutive
        # agreeing frames to change it, so a one-frame release would never land.
        self._color_flip_released: set[tuple[int, int]] = set()

    def _positions(self, det, img_w: int, img_h: int) -> tuple[float, float, float, float, bool]:
        """(fx_raw, fy_raw, fx, fy, on_board) for a detection. The ONLY caller of apply_parallax -- it is
        not idempotent, so every consumer must take its (fx, fy) from here, corrected exactly once.

        on_board is False when EITHER the raw or the corrected position rounds off the grid, and an
        off-board detection keeps its RAW position as (fx, fy). The correction pulls points toward the
        nadir; letting it move a warp-margin object would let that object reach cells it cannot reach
        today -- not only as a new stone, but through sticky assignment and presence sustain, where it
        kept a just-removed edge stone alive in review. Off-board detections therefore behave exactly
        as they do without the correction."""
        x_mm, y_mm = pixel_to_physical(det.x_center, det.y_center, img_w, img_h, self.config)
        fx_raw, fy_raw = continuous_grid_pos(x_mm, y_mm, self.config)
        if self.parallax is None:
            return fx_raw, fy_raw, fx_raw, fy_raw, self._on_board(fx_raw, fy_raw)
        fx, fy = apply_parallax(fx_raw, fy_raw, self.parallax.nadir, self.parallax.k)
        if self._on_board(fx_raw, fy_raw) and self._on_board(fx, fy):
            return fx_raw, fy_raw, fx, fy, True
        return fx_raw, fy_raw, fx_raw, fy_raw, False

    def _on_board(self, fx: float, fy: float) -> bool:
        gs = self.config.grid_size
        return 0 <= int(round(fy)) < gs and 0 <= int(round(fx)) < gs

    def _grid_cell(self, det, img_w: int, img_h: int) -> tuple[int, int] | None:
        """Nearest intersection (row, col) for a detection, or None when it is off-board.

        The geometry-lock warp includes a 1-cell blank margin; an object sitting in that
        margin (cable, marker, glare) must be DROPPED, not clamped to the nearest border
        intersection — clamping once turned a red object beside the top-right corner into
        a phantom T19 move. Up to half a cell of overshoot still rounds onto the edge row,
        so sloppily placed border stones keep working.

        With parallax on, off-board means EITHER the raw or the corrected position rounds off the
        grid (see _positions): otherwise the correction would drag a margin object in a ~0.2-cell band
        outside the far/side edges back onto the board."""
        _, _, fx, fy, on_board = self._positions(det, img_w, img_h)
        return (int(round(fy)), int(round(fx))) if on_board else None

    @staticmethod
    def _passes_hysteresis(det, cy: int, cx: int, prev_board, add_threshold) -> bool:
        """Two-tier confidence gate (weak-light flicker fix): detections arrive filtered
        at the lower "keep" threshold; one below ``add_threshold`` may only SUSTAIN a
        same-color stone already present in ``prev_board`` (the last stable board) — it
        can never add a new stone. Disabled when add_threshold is None."""
        if add_threshold is None or det.confidence >= add_threshold:
            return True
        return prev_board is not None and int(prev_board[cy][cx]) == det.class_id + 1

    def detection_points(self, detections: list[Detection], img_w: int, img_h: int) -> list:
        """Continuous grid positions of ALL detections (any class, off-board included): [(fy, fx, class_id,
        confidence)], corrected when on-board by both the raw and the corrected position; raw otherwise.
        Used by presence sustain and delta diagnostics."""
        pts = []
        for det in detections:
            _, _, fx, fy, _ = self._positions(det, img_w, img_h)
            pts.append((fy, fx, det.class_id, det.confidence))
        return pts

    def parallax_points(self, detections: list[Detection], img_w: int, img_h: int) -> list:
        """detection_points with the raw position kept alongside, for diagnostics only:
        [(fy_raw, fx_raw, fy, fx, class_id, confidence)]."""
        pts = []
        for det in detections:
            fx_raw, fy_raw, fx, fy, _ = self._positions(det, img_w, img_h)
            pts.append((fy_raw, fx_raw, fy, fx, det.class_id, det.confidence))
        return pts

    def detections_to_board(
        self,
        detections: list[Detection],
        img_w: int,
        img_h: int,
        occupancy_aware: bool = False,
        masked_cells: set | None = None,
        prev_board: np.ndarray | None = None,
        add_threshold: float | None = None,
        sticky_board: np.ndarray | None = None,
    ) -> np.ndarray:
        """Convert detected stones to a grid_size x grid_size board matrix.

        ``masked_cells`` (row, col) intersections are dropped from assignment — used to
        ignore detections landing on lit-and-expected-empty intersections during LED hint
        display, where a lit LED can be misdetected as a stone (R7.1).

        ``prev_board``/``add_threshold`` enable confidence hysteresis — see
        ``_passes_hysteresis``. ``prev_board`` (the last stable board) also drives
        presence sustain; ``sticky_board`` (the previous frame's raw observed board)
        drives sticky assignment. Both occupancy-aware only.
        """
        gs = self.config.grid_size
        board = np.zeros((gs, gs), dtype=int)
        if occupancy_aware:
            return self._assign_occupancy_aware(
                board, detections, img_w, img_h, masked_cells, prev_board, add_threshold, sticky_board
            )

        confidence = np.zeros((gs, gs), dtype=float)
        for det in detections:
            if det.class_id not in STONE_CLASS_IDS:
                continue  # LED guidance classes (led_red/led_green) are not board stones
            cell = self._grid_cell(det, img_w, img_h)
            if cell is None:
                continue  # off-board detection (warp-margin object) — never clamp onto a border point
            pos_y, pos_x = cell
            if (
                masked_cells
                and (pos_y, pos_x) in masked_cells
                and (prev_board is None or int(prev_board[pos_y][pos_x]) == EMPTY)
            ):
                continue  # lit EMPTY intersection: presume LED glare, not a stone (adds only)
            if not self._passes_hysteresis(det, pos_y, pos_x, prev_board, add_threshold):
                continue
            if det.confidence > confidence[pos_y][pos_x]:
                board[pos_y][pos_x] = det.class_id + 1  # 0→BLACK(1), 1→WHITE(2)
                confidence[pos_y][pos_x] = det.confidence
        return board

    @staticmethod
    def _sticky_cell(sticky_board, board, fy: float, fx: float, color: int):
        """Same-color stone cell from the previous raw board within STICKY_RADIUS of the
        detection's continuous position (and still unclaimed this frame), or None."""
        if sticky_board is None:
            return None
        gs = sticky_board.shape[0]
        cy = int(round(fy))
        cx = int(round(fx))
        best = None
        best_d = None
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                ny, nx = cy + dy, cx + dx
                if not (0 <= ny < gs and 0 <= nx < gs):
                    continue
                if int(sticky_board[ny][nx]) != color or board[ny][nx] != EMPTY:
                    continue
                d = math.hypot(fy - ny, fx - nx)
                if d <= STICKY_RADIUS and (best is None or d < best_d):
                    best, best_d = (ny, nx), d
        return best

    def _assign_occupancy_aware(
        self,
        board: np.ndarray,
        detections: list[Detection],
        img_w: int,
        img_h: int,
        masked_cells: set | None = None,
        prev_board: np.ndarray | None = None,
        add_threshold: float | None = None,
        sticky_board: np.ndarray | None = None,
    ) -> np.ndarray:
        gs = board.shape[0]
        positions = [self._positions(det, img_w, img_h) for det in detections]
        # any class, for sustain -- same content as detection_points(), without recomputing it
        all_points = [(fy, fx, det.class_id, det.confidence) for det, (_, _, fx, fy, _) in zip(detections, positions)]
        items = []
        for det, (_, _, fx, fy, on_board) in zip(detections, positions):
            if det.class_id not in STONE_CLASS_IDS:
                continue
            residual = math.hypot(fx - round(fx), fy - round(fy))
            items.append((residual, det, fx, fy, on_board))
        # Highest confidence claims its intersection first (matches the legacy "highest-confidence
        # wins" semantics); residual only breaks ties between equally confident detections. A
        # lower-confidence detection that then lands on an occupied point is either a sloppily
        # placed real stone (spill it to the nearest empty neighbour) or a duplicate/false positive
        # (drop it) — decided by SPILL_MIN_CONFIDENCE, so a weak FP can't spawn a phantom.
        items.sort(key=lambda t: (-t[1].confidence, t[0]))
        for _, det, fx, fy, on_board in items:
            sticky = self._sticky_cell(sticky_board, board, fy, fx, det.class_id + 1)
            if sticky is not None:
                cy, cx = sticky  # boundary-straddling stone stays on its established cell
            else:
                if not on_board:
                    continue  # off-board detection (warp-margin object) — never clamp onto a border point
                cy, cx = int(round(fy)), int(round(fx))
            # Lit-cell mask blocks ADDITIONS only: lamp glare on an EMPTY point must not
            # become a phantom stone (R7.1), but a stone already established at a lit
            # cell keeps being recognized — dropping its detections blinded vision to
            # the very stone a "remove" lamp pointed at (lamp/recognition oscillation)
            # and force-cleared removal tracking while the stone was still on the board.
            if masked_cells and (cy, cx) in masked_cells and (prev_board is None or int(prev_board[cy][cx]) == EMPTY):
                continue
            if not self._passes_hysteresis(det, cy, cx, prev_board, add_threshold):
                continue
            if board[cy][cx] == EMPTY:
                board[cy][cx] = det.class_id + 1
                continue
            if det.confidence < SPILL_MIN_CONFIDENCE:
                continue  # weak collider on an occupied point -> drop (don't manufacture a phantom)
            cell = _nearest_empty_cell(board, fy, fx, max_r=1)
            if cell is None:
                continue  # no empty cell within 1 ring -> cannot place a second stone on one point
            ny, nx = cell
            board[ny][nx] = det.class_id + 1

        # Presence sustain: a stone from the last stable board stays while a detection
        # still sits on it — see SUSTAIN_RADIUS. At UNLIT cells any class counts (the
        # model misreads a dark stone as led_red / flips its color for a few frames);
        # at LIT cells (masked = a remove lamp is burning there) only STONE classes
        # count — after the user removes the stone the lamp's own glare reads as an
        # led class, and counting it would keep the just-removed stone alive forever
        # (removal deadlock: removal_pending never clears, the game stays paused).
        if prev_board is not None and all_points:
            for r, c in zip(*np.where((prev_board != EMPTY) & (board == EMPTY))):
                lit = bool(masked_cells) and (int(r), int(c)) in masked_cells
                if any(
                    math.hypot(fy - r, fx - c) <= SUSTAIN_RADIUS and (not lit or cls in STONE_CLASS_IDS)
                    for fy, fx, cls, _ in all_points
                ):
                    board[r][c] = prev_board[r][c]

        # Colour invariant (see COLOR_FLIP_RELEASE_FRAMES). Runs after presence sustain,
        # so a cell that sustain just resurrected already carries prev's colour and is
        # not re-examined here.
        if prev_board is not None:
            flipped = {
                (int(r), int(c))
                for r, c in zip(*np.where((prev_board != EMPTY) & (board != EMPTY) & (board != prev_board)))
            }
            for cell in list(self._color_flip_streak):
                if cell not in flipped:
                    del self._color_flip_streak[cell]  # agreed again — start over
            for cell in list(self._color_flip_released):
                if cell not in flipped:
                    # No longer a disagreement: either the stable board adopted the new
                    # colour (the release landed) or the stone left. Either way, done.
                    self._color_flip_released.discard(cell)
            for cell in flipped:
                if cell in self._color_flip_released:
                    continue  # latched open until the stable board adopts it
                r, c = cell
                streak = self._color_flip_streak.get(cell, 0) + 1
                if streak >= COLOR_FLIP_RELEASE_FRAMES:
                    del self._color_flip_streak[cell]
                    self._color_flip_released.add(cell)  # a real wrong-colour placement
                else:
                    self._color_flip_streak[cell] = streak
                    board[r][c] = int(prev_board[r][c])
        else:
            self._color_flip_streak.clear()
            self._color_flip_released.clear()
        return board

    def cell_top(self, detections: list[Detection], img_w: int, img_h: int) -> dict:
        """Highest-confidence stone detection per rounded intersection, WITH its class:
        {(row, col): (confidence, class_id)}. Used by the sub-add ambiguous promotion
        (a stone stuck below the add threshold needs its color for the prompt)."""
        out: dict[tuple[int, int], tuple[float, int]] = {}
        for det in detections:
            if det.class_id not in STONE_CLASS_IDS:
                continue
            key = self._grid_cell(det, img_w, img_h)
            if key is None:
                continue
            if key not in out or det.confidence > out[key][0]:
                out[key] = (det.confidence, det.class_id)
        return out

    def cell_confidences(self, detections: list[Detection], img_w: int, img_h: int) -> dict:
        """Max detection confidence per rounded intersection — used to classify a
        pending move as confirmed vs ambiguous (PRD §3.4 ambiguous_stone)."""
        out: dict[tuple[int, int], float] = {}
        for det in detections:
            if det.class_id not in STONE_CLASS_IDS:
                continue
            key = self._grid_cell(det, img_w, img_h)
            if key is None:
                continue  # off-board detection must not vouch for a border intersection
            out[key] = max(out.get(key, 0.0), det.confidence)
        return out

    @staticmethod
    def board_to_string(board: np.ndarray) -> str:
        symbols = {EMPTY: ".", BLACK: "B", WHITE: "W"}
        lines = []
        for row in board:
            lines.append(" ".join(symbols[int(v)] for v in row))
        return "\n".join(lines)
