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
from katrain.vision.coordinates import continuous_grid_pos, pixel_to_physical
from katrain.vision.stone_detector import Detection

EMPTY = 0
BLACK = 1
WHITE = 2

# Detections that collide on an already-claimed intersection are spilled to the nearest empty
# neighbour only if at least this confident (a sloppily-placed real stone); a weaker collider is
# treated as a duplicate/false positive and dropped, so it can't manufacture a phantom stone.
SPILL_MIN_CONFIDENCE = 0.6


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

    def __init__(self, config: BoardConfig | None = None):
        self.config = config or BoardConfig()

    def _grid_cell(self, det, img_w: int, img_h: int) -> tuple[int, int] | None:
        """Nearest intersection (row, col) for a detection, or None when it is off-board.

        The geometry-lock warp includes a 1-cell blank margin; an object sitting in that
        margin (cable, marker, glare) must be DROPPED, not clamped to the nearest border
        intersection — clamping once turned a red object beside the top-right corner into
        a phantom T19 move. Up to half a cell of overshoot still rounds onto the edge row,
        so sloppily placed border stones keep working."""
        x_mm, y_mm = pixel_to_physical(det.x_center, det.y_center, img_w, img_h, self.config)
        fx, fy = continuous_grid_pos(x_mm, y_mm, self.config)
        cy, cx = int(round(fy)), int(round(fx))
        gs = self.config.grid_size
        if 0 <= cy < gs and 0 <= cx < gs:
            return cy, cx
        return None

    @staticmethod
    def _passes_hysteresis(det, cy: int, cx: int, prev_board, add_threshold) -> bool:
        """Two-tier confidence gate (weak-light flicker fix): detections arrive filtered
        at the lower "keep" threshold; one below ``add_threshold`` may only SUSTAIN a
        same-color stone already present in ``prev_board`` (the last stable board) — it
        can never add a new stone. Disabled when add_threshold is None."""
        if add_threshold is None or det.confidence >= add_threshold:
            return True
        return prev_board is not None and int(prev_board[cy][cx]) == det.class_id + 1

    def detections_to_board(
        self,
        detections: list[Detection],
        img_w: int,
        img_h: int,
        occupancy_aware: bool = False,
        masked_cells: set | None = None,
        prev_board: np.ndarray | None = None,
        add_threshold: float | None = None,
    ) -> np.ndarray:
        """Convert detected stones to a grid_size x grid_size board matrix.

        ``masked_cells`` (row, col) intersections are dropped from assignment — used to
        ignore detections landing on lit-and-expected-empty intersections during LED hint
        display, where a lit LED can be misdetected as a stone (R7.1).

        ``prev_board``/``add_threshold`` enable confidence hysteresis — see
        ``_passes_hysteresis``.
        """
        gs = self.config.grid_size
        board = np.zeros((gs, gs), dtype=int)
        if occupancy_aware:
            return self._assign_occupancy_aware(
                board, detections, img_w, img_h, masked_cells, prev_board, add_threshold
            )

        confidence = np.zeros((gs, gs), dtype=float)
        for det in detections:
            if det.class_id not in STONE_CLASS_IDS:
                continue  # LED guidance classes (led_red/led_green) are not board stones
            cell = self._grid_cell(det, img_w, img_h)
            if cell is None:
                continue  # off-board detection (warp-margin object) — never clamp onto a border point
            pos_y, pos_x = cell
            if masked_cells and (pos_y, pos_x) in masked_cells:
                continue  # lit-and-expected-empty intersection: presume LED glare, not a stone
            if not self._passes_hysteresis(det, pos_y, pos_x, prev_board, add_threshold):
                continue
            if det.confidence > confidence[pos_y][pos_x]:
                board[pos_y][pos_x] = det.class_id + 1  # 0→BLACK(1), 1→WHITE(2)
                confidence[pos_y][pos_x] = det.confidence
        return board

    def _assign_occupancy_aware(
        self,
        board: np.ndarray,
        detections: list[Detection],
        img_w: int,
        img_h: int,
        masked_cells: set | None = None,
        prev_board: np.ndarray | None = None,
        add_threshold: float | None = None,
    ) -> np.ndarray:
        gs = board.shape[0]
        items = []
        for det in detections:
            if det.class_id not in STONE_CLASS_IDS:
                continue
            x_mm, y_mm = pixel_to_physical(det.x_center, det.y_center, img_w, img_h, self.config)
            fx, fy = continuous_grid_pos(x_mm, y_mm, self.config)
            residual = math.hypot(fx - round(fx), fy - round(fy))
            items.append((residual, det, fx, fy))
        # Highest confidence claims its intersection first (matches the legacy "highest-confidence
        # wins" semantics); residual only breaks ties between equally confident detections. A
        # lower-confidence detection that then lands on an occupied point is either a sloppily
        # placed real stone (spill it to the nearest empty neighbour) or a duplicate/false positive
        # (drop it) — decided by SPILL_MIN_CONFIDENCE, so a weak FP can't spawn a phantom.
        items.sort(key=lambda t: (-t[1].confidence, t[0]))
        for _, det, fx, fy in items:
            cy, cx = int(round(fy)), int(round(fx))
            if not (0 <= cy < gs and 0 <= cx < gs):
                continue  # off-board detection (warp-margin object) — never clamp onto a border point
            if masked_cells and (cy, cx) in masked_cells:
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
