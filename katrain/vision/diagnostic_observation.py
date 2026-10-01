"""Diagnostic-only derivations over one recognition batch. Nothing here feeds back into recognition."""

from __future__ import annotations

import numpy as np

from katrain.vision.board_state import BLACK, EMPTY, WHITE

STONE_VALUE = {0: BLACK, 1: WHITE}


def diagnostic_projection(extractor, detections, img_w: int, img_h: int) -> np.ndarray:
    """Stage 5 "原始定位投影": each stone box's RAW continuous grid position rounded to the nearest point.

    Off-board positions are dropped and the most confident box wins a cell. No parallax, sticky
    assignment, spill, masking or history -- the difference to the real assignment is exactly what
    those corrections did. Read-only: extractor.parallax_points never touches extractor state.
    """
    size = extractor.config.grid_size
    board = np.full((size, size), EMPTY, dtype=int)
    best = np.full((size, size), -1.0)
    for fy_raw, fx_raw, _fy, _fx, class_id, confidence in extractor.parallax_points(detections, img_w, img_h):
        if class_id not in STONE_VALUE:
            continue
        row, col = int(round(fy_raw)), int(round(fx_raw))
        if 0 <= row < size and 0 <= col < size and confidence > best[row, col]:
            board[row, col], best[row, col] = STONE_VALUE[class_id], confidence
    return board
