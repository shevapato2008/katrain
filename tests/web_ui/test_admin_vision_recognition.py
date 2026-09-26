"""Recognition maps a stone back to the same intersection the dataset labeler put its box on."""

import numpy as np
from types import SimpleNamespace


def test_recognized_intersection_equals_labeled_intersection():
    from katrain.vision.board_state import BLACK, WHITE
    from katrain.vision.config import DEFAULT_MARGIN_CELLS
    from katrain.vision.stone_detector import Detection
    from katrain.vision.tools import baipu_autolabel
    from katrain.vision.warp import margin_px_for
    from katrain.web.admin.vision_recognition import board_diff, expected_board, recognize_board

    out_size = 950
    spacing = (out_size - 1) / 18
    grid = np.array([spacing * i for i in range(19)], dtype=np.float32)
    geometry = SimpleNamespace(M=np.eye(3), out_size=out_size, source_width=out_size, source_height=out_size)
    pad = margin_px_for(out_size, DEFAULT_MARGIN_CELLS)
    placed = {(3, 15): 0, (9, 9): 1, (16, 2): 0}

    class Detector:
        def detect(self, image):
            found = []
            for (row, col), class_id in placed.items():
                x, y = baipu_autolabel.grid_point(row, col, grid + pad, grid + pad)
                found.append(
                    Detection(
                        x_center=x, y_center=y, class_id=class_id, confidence=0.9, bbox=(x - 20, y - 20, x + 20, y + 20)
                    )
                )
            return found

    board = recognize_board(np.zeros((out_size, out_size, 3), np.uint8), geometry, Detector())
    assert {(int(r), int(c)): int(board[r, c]) for r, c in zip(*np.nonzero(board))} == {
        (3, 15): BLACK,
        (9, 9): WHITE,
        (16, 2): BLACK,
    }
    steps = [
        {"kind": "move", "row": 3, "col": 15, "color": "B", "removed": []},
        {"kind": "move", "row": 9, "col": 9, "color": "W", "removed": []},
    ]
    missing, extra = board_diff(board, expected_board(steps, 1))
    assert missing == [] and extra == [{"row": 16, "col": 2}]
