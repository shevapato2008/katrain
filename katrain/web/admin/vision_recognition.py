"""One-shot board recognition on the admin camera's locked geometry, and exact comparison with SGF truth.

Serve geometry equals train geometry: the same resolution-adjusted homography and one-cell margin
the dataset labeler uses. Only black/white stones are compared; LED classes never count.
"""

from __future__ import annotations

import numpy as np

from katrain.vision.board_state import BLACK, EMPTY, WHITE, BoardStateExtractor
from katrain.vision.config import DEFAULT_MARGIN_CELLS, BoardConfig
from katrain.vision.warp import adjust_M_for_resolution, warp_with_margin


def recognize_board(frame, geometry, detector, matrix=None) -> np.ndarray:
    base = geometry.M if matrix is None else matrix
    M = adjust_M_for_resolution(
        base,
        (getattr(geometry, "source_width", None), getattr(geometry, "source_height", None)),
        (frame.shape[1], frame.shape[0]),
    )
    warped = warp_with_margin(frame, M, int(geometry.out_size), margin_cells=DEFAULT_MARGIN_CELLS)
    height, width = warped.shape[:2]
    extractor = BoardStateExtractor(BoardConfig(margin_cells=DEFAULT_MARGIN_CELLS))
    board = extractor.detections_to_board(detector.detect(warped), img_w=width, img_h=height, occupancy_aware=True)
    return np.asarray(board, dtype=int)


def expected_board(steps, move_index: int) -> np.ndarray:
    from katrain.core.baipu import expected_board_from_steps

    values = {"B": BLACK, "W": WHITE, None: EMPTY}
    return np.array([[values[cell] for cell in row] for row in expected_board_from_steps(steps, move_index, 19)], int)


def board_diff(observed: np.ndarray, expected: np.ndarray) -> tuple[list[dict], list[dict]]:
    """missing: expected stones not seen with the right colour; extra: stones where the board should be empty."""
    observed = np.asarray(observed, dtype=int)
    missing = [
        {"row": int(r), "col": int(c)} for r, c in zip(*np.nonzero((expected != EMPTY) & (observed != expected)))
    ]
    extra = [{"row": int(r), "col": int(c)} for r, c in zip(*np.nonzero((expected == EMPTY) & (observed != EMPTY)))]
    return missing, extra


def board_string(board: np.ndarray) -> str:
    return "".join(str(int(value)) for value in np.asarray(board, dtype=int).reshape(-1))
