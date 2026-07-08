"""masked_cells drops detections landing on lit-and-expected-empty intersections (R7.1)."""

import numpy as np

from katrain.vision.board_state import BoardStateExtractor
from katrain.vision.stone_detector import Detection


def _det(cx, cy, class_id=1, conf=0.9):
    return Detection(class_id=class_id, confidence=conf, x_center=cx, y_center=cy)


class TestMasking:
    def test_masked_cell_detection_dropped(self):
        ex = BoardStateExtractor()
        # 用 extractor 自己的坐标系造一个落在 (row 0, col 0) 的检测：
        # 先不加 mask 确认它落在哪个格，再对该格做 mask 断言消失。
        img_w = img_h = 800
        d = _det(30, 30)
        base = ex.detections_to_board([d], img_w, img_h, occupancy_aware=True)
        cells = list(zip(*np.nonzero(base)))
        assert len(cells) == 1
        cell = (int(cells[0][0]), int(cells[0][1]))
        masked = ex.detections_to_board([d], img_w, img_h, occupancy_aware=True, masked_cells={cell})
        assert masked.sum() == 0

    def test_unmasked_cells_unaffected(self):
        ex = BoardStateExtractor()
        d = _det(30, 30)
        out = ex.detections_to_board([d], 800, 800, occupancy_aware=True, masked_cells={(18, 18)})
        assert out.sum() > 0

    def test_cell_confidences_maps_max_conf(self):
        ex = BoardStateExtractor()
        d = _det(30, 30, conf=0.42)
        conf = ex.cell_confidences([d], 800, 800)
        assert len(conf) == 1 and abs(list(conf.values())[0] - 0.42) < 1e-9
