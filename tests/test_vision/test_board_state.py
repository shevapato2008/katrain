import numpy as np
import pytest
from katrain.vision.board_state import BoardStateExtractor, EMPTY, BLACK, WHITE
from katrain.vision.config import BoardConfig
from katrain.vision.coordinates import grid_to_physical
from katrain.vision.stone_detector import Detection


class TestBoardStateConstants:
    def test_constants(self):
        assert EMPTY == 0
        assert BLACK == 1
        assert WHITE == 2


@pytest.fixture
def extractor():
    return BoardStateExtractor()


@pytest.fixture
def cfg():
    return BoardConfig()


class TestDetectionsToBoard:
    def test_empty_detections(self, extractor):
        board = extractor.detections_to_board([], img_w=640, img_h=480)
        assert board.shape == (19, 19)
        assert np.all(board == EMPTY)

    def test_single_black_stone_at_origin(self, extractor, cfg):
        x_pixel = cfg.border_width_mm / cfg.total_width * 640
        y_pixel = cfg.border_length_mm / cfg.total_length * 480
        detections = [Detection(x_center=x_pixel, y_center=y_pixel, class_id=0, confidence=0.95)]
        board = extractor.detections_to_board(detections, img_w=640, img_h=480)
        assert board[0][0] == BLACK

    def test_white_stone_at_tengen(self, extractor, cfg):
        x_pixel = (cfg.border_width_mm + cfg.board_width_mm / 2) / cfg.total_width * 640
        y_pixel = (cfg.border_length_mm + cfg.board_length_mm / 2) / cfg.total_length * 480
        detections = [Detection(x_center=x_pixel, y_center=y_pixel, class_id=1, confidence=0.9)]
        board = extractor.detections_to_board(detections, img_w=640, img_h=480)
        assert board[9][9] == WHITE

    def test_conflict_resolution_highest_confidence_wins(self, extractor, cfg):
        """Two detections at same grid point — higher confidence wins."""
        x_mm, y_mm = grid_to_physical(5, 5, config=cfg)
        x_px = x_mm / cfg.total_width * 640
        y_px = y_mm / cfg.total_length * 480
        # Low-confidence black, then high-confidence white at same point
        detections = [
            Detection(x_center=x_px, y_center=y_px, class_id=0, confidence=0.6),
            Detection(x_center=x_px, y_center=y_px, class_id=1, confidence=0.9),
        ]
        board = extractor.detections_to_board(detections, img_w=640, img_h=480)
        assert board[5][5] == WHITE  # higher confidence wins


class TestBoardToString:
    def test_empty_board_string(self):
        board = np.zeros((19, 19), dtype=int)
        result = BoardStateExtractor.board_to_string(board)
        assert len(result.strip().split("\n")) == 19

    def test_board_with_stones(self):
        board = np.zeros((19, 19), dtype=int)
        board[3][3] = BLACK
        board[15][15] = WHITE
        result = BoardStateExtractor.board_to_string(board)
        lines = result.strip().split("\n")
        assert "B" in lines[3]
        assert "W" in lines[15]


class TestLedGuard:
    def _det(self, x, y, class_id, conf=0.9):
        return Detection(x_center=x, y_center=y, class_id=class_id, confidence=conf)

    def test_led_detections_are_ignored(self):
        ex = BoardStateExtractor()
        img = 950
        # a black stone at grid (0,0) -> pixel ~ (0,0); a red LED (class 2) at grid (1,1)
        dets = [self._det(2, 2, 0), self._det(int(1 / 18 * img), int(1 / 18 * img), 2)]
        board = ex.detections_to_board(dets, img_w=img, img_h=img)
        assert board[0][0] == BLACK
        # LED (class_id=2) must NOT have written anything (would have been 3 with the +1 bug)
        assert set(int(v) for v in np.unique(board)) <= {0, BLACK, WHITE}
        assert board[1][1] == 0

    def test_white_still_maps_to_white(self):
        ex = BoardStateExtractor()
        board = ex.detections_to_board([self._det(2, 2, 1)], img_w=950, img_h=950)
        assert board[0][0] == WHITE


class TestOccupancyAwareAssignment:
    def _det_at_cell(self, row, col, class_id, img, cfg, conf=0.9, off_px=(0.0, 0.0)):
        from katrain.vision.coordinates import grid_to_pixel

        px, py = grid_to_pixel(col, row, img, img, cfg)  # grid_to_pixel takes (pos_x=col, pos_y=row)
        return Detection(x_center=px + off_px[0], y_center=py + off_px[1], class_id=class_id, confidence=conf)

    def test_collision_reassigns_to_neighbor_not_dropped(self, cfg):
        ex = BoardStateExtractor()
        img = 950
        spacing_px = img / 18.0
        a = self._det_at_cell(5, 5, 0, img, cfg)  # exactly on (5,5)
        b = self._det_at_cell(5, 5, 0, img, cfg, off_px=(0.42 * spacing_px, 0.0))  # rounds to (5,5), leans to col6
        board = ex.detections_to_board([a, b], img_w=img, img_h=img, occupancy_aware=True)
        assert board[5][5] == BLACK
        assert board[5][6] == BLACK  # loser reassigned to nearest empty neighbor, not silently dropped
        assert int((board != EMPTY).sum()) == 2

    def test_backward_compat_default_drops_collision(self, cfg):
        ex = BoardStateExtractor()
        img = 950
        spacing_px = img / 18.0
        a = self._det_at_cell(5, 5, 0, img, cfg)
        b = self._det_at_cell(5, 5, 0, img, cfg, off_px=(0.42 * spacing_px, 0.0))
        board = ex.detections_to_board([a, b], img_w=img, img_h=img)  # default occupancy_aware=False
        assert int((board != EMPTY).sum()) == 1  # legacy: one wins, the other is dropped

    def test_occupancy_ignores_led(self, cfg):
        ex = BoardStateExtractor()
        img = 950
        dets = [self._det_at_cell(5, 5, 0, img, cfg), self._det_at_cell(7, 7, 2, img, cfg)]  # class 2 = led_red
        board = ex.detections_to_board(dets, img_w=img, img_h=img, occupancy_aware=True)
        assert board[5][5] == BLACK
        assert int((board != EMPTY).sum()) == 1  # LED not placed
