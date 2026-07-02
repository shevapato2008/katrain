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
from katrain.vision.coordinates import continuous_grid_pos, physical_to_grid, pixel_to_physical
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

    def detections_to_board(
        self,
        detections: list[Detection],
        img_w: int,
        img_h: int,
        occupancy_aware: bool = False,
        masked_cells: set | None = None,
    ) -> np.ndarray:
        """Convert detected stones to a grid_size x grid_size board matrix.

        ``masked_cells`` (row, col) intersections are dropped from assignment — used to
        ignore detections landing on lit-and-expected-empty intersections during LED hint
        display, where a lit LED can be misdetected as a stone (R7.1).
        """
        gs = self.config.grid_size
        board = np.zeros((gs, gs), dtype=int)
        if occupancy_aware:
            return self._assign_occupancy_aware(board, detections, img_w, img_h, masked_cells)

        confidence = np.zeros((gs, gs), dtype=float)
        for det in detections:
            if det.class_id not in STONE_CLASS_IDS:
                continue  # LED guidance classes (led_red/led_green) are not board stones
            x_mm, y_mm = pixel_to_physical(det.x_center, det.y_center, img_w, img_h, self.config)
            pos_x, pos_y = physical_to_grid(x_mm, y_mm, self.config)
            if masked_cells and (pos_y, pos_x) in masked_cells:
                continue  # lit-and-expected-empty intersection: presume LED glare, not a stone
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
            cy = max(0, min(gs - 1, int(round(fy))))
            cx = max(0, min(gs - 1, int(round(fx))))
            if masked_cells and (cy, cx) in masked_cells:
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

    def cell_confidences(self, detections: list[Detection], img_w: int, img_h: int) -> dict:
        """Max detection confidence per rounded intersection — used to classify a
        pending move as confirmed vs ambiguous (PRD §3.4 ambiguous_stone)."""
        out: dict[tuple[int, int], float] = {}
        for det in detections:
            if det.class_id not in STONE_CLASS_IDS:
                continue
            x_mm, y_mm = pixel_to_physical(det.x_center, det.y_center, img_w, img_h, self.config)
            pos_x, pos_y = physical_to_grid(x_mm, y_mm, self.config)
            key = (pos_y, pos_x)
            out[key] = max(out.get(key, 0.0), det.confidence)
        return out

    @staticmethod
    def board_to_string(board: np.ndarray) -> str:
        symbols = {EMPTY: ".", BLACK: "B", WHITE: "W"}
        lines = []
        for row in board:
            lines.append(" ".join(symbols[int(v)] for v in row))
        return "\n".join(lines)
