"""
Combines stone detection results with coordinate mapping to produce a 19x19 board state.
Uses confidence-based conflict resolution when multiple detections map to the same grid point.
"""

import numpy as np

from katrain.vision.config import BoardConfig
from katrain.vision.coordinates import pixel_to_physical, physical_to_grid
from katrain.vision.stone_detector import Detection

EMPTY = 0
BLACK = 1
WHITE = 2


class BoardStateExtractor:
    """Converts a list of stone detections into a board state matrix."""

    def __init__(self, config: BoardConfig | None = None):
        self.config = config or BoardConfig()

    def detections_to_board(self, detections: list[Detection], img_w: int, img_h: int) -> np.ndarray:
        """Convert detected stones to a grid_size x grid_size board matrix."""
        gs = self.config.grid_size
        board = np.zeros((gs, gs), dtype=int)
        confidence = np.zeros((gs, gs), dtype=float)

        for det in detections:
            x_mm, y_mm = pixel_to_physical(det.x_center, det.y_center, img_w, img_h, self.config)
            pos_x, pos_y = physical_to_grid(x_mm, y_mm, self.config)
            if det.confidence > confidence[pos_y][pos_x]:
                board[pos_y][pos_x] = det.class_id + 1  # 0→BLACK(1), 1→WHITE(2)
                confidence[pos_y][pos_x] = det.confidence
        return board

    @staticmethod
    def board_to_string(board: np.ndarray) -> str:
        symbols = {EMPTY: ".", BLACK: "B", WHITE: "W"}
        lines = []
        for row in board:
            lines.append(" ".join(symbols[int(v)] for v in row))
        return "\n".join(lines)
