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

    def test_high_confidence_keeps_cell_over_centered_low_confidence(self, cfg):
        # Review #1: a high-confidence real stone (slightly off-center) must keep the contested
        # cell over a dead-centered low-confidence false positive — confidence beats residual.
        ex = BoardStateExtractor()
        img = 950
        spacing_px = img / 18.0
        a = self._det_at_cell(5, 5, 0, img, cfg, conf=0.95, off_px=(0.30 * spacing_px, 0.0))  # real, off-center
        b = self._det_at_cell(5, 5, 1, img, cfg, conf=0.55)  # centered low-confidence FP (white)
        board = ex.detections_to_board([a, b], img_w=img, img_h=img, occupancy_aware=True)
        assert board[5][5] == BLACK  # high-confidence A keeps the cell, not centered FP B

    def test_low_confidence_collider_dropped_not_spilled(self, cfg):
        # Review #2: a low-confidence detection colliding on an occupied point is treated as a
        # duplicate/false positive and DROPPED, not spilled to an empty neighbor (no phantom).
        ex = BoardStateExtractor()
        img = 950
        spacing_px = img / 18.0
        a = self._det_at_cell(5, 5, 0, img, cfg, conf=0.9)  # real stone on (5,5)
        b = self._det_at_cell(5, 5, 0, img, cfg, conf=0.55, off_px=(0.42 * spacing_px, 0.0))  # weak collider
        board = ex.detections_to_board([a, b], img_w=img, img_h=img, occupancy_aware=True)
        assert board[5][5] == BLACK
        assert board[5][6] == EMPTY  # dropped, not spilled
        assert int((board != EMPTY).sum()) == 1


class TestConfidenceHysteresis:
    """Two-tier confidence gate (weak-light flicker fix): a below-add detection may only
    SUSTAIN a same-color stone already in prev_board — never add a new one."""

    def _det_at_cell(self, row, col, class_id, img, cfg, conf=0.9):
        from katrain.vision.coordinates import grid_to_pixel

        px, py = grid_to_pixel(col, row, img, img, cfg)
        return Detection(x_center=px, y_center=py, class_id=class_id, confidence=conf)

    @pytest.mark.parametrize("occupancy_aware", [False, True])
    def test_weak_detection_cannot_add_new_stone(self, cfg, occupancy_aware):
        ex = BoardStateExtractor()
        img = 950
        weak = self._det_at_cell(5, 5, 0, img, cfg, conf=0.35)  # below add=0.45
        board = ex.detections_to_board(
            [weak],
            img_w=img,
            img_h=img,
            occupancy_aware=occupancy_aware,
            prev_board=np.zeros((19, 19), dtype=int),
            add_threshold=0.45,
        )
        assert board[5][5] == EMPTY

    @pytest.mark.parametrize("occupancy_aware", [False, True])
    def test_weak_detection_sustains_existing_same_color_stone(self, cfg, occupancy_aware):
        ex = BoardStateExtractor()
        img = 950
        prev = np.zeros((19, 19), dtype=int)
        prev[5][5] = BLACK  # stone confirmed there in the last stable board
        weak = self._det_at_cell(5, 5, 0, img, cfg, conf=0.35)  # same color, below add
        board = ex.detections_to_board(
            [weak],
            img_w=img,
            img_h=img,
            occupancy_aware=occupancy_aware,
            prev_board=prev,
            add_threshold=0.45,
        )
        assert board[5][5] == BLACK  # kept: keep-tier confidence suffices for occupied cell

    @pytest.mark.parametrize("occupancy_aware", [False, True])
    def test_weak_detection_of_other_color_does_not_flip_stone(self, cfg, occupancy_aware):
        ex = BoardStateExtractor()
        img = 950
        prev = np.zeros((19, 19), dtype=int)
        prev[5][5] = BLACK
        weak_white = self._det_at_cell(5, 5, 1, img, cfg, conf=0.35)  # different color
        board = ex.detections_to_board(
            [weak_white],
            img_w=img,
            img_h=img,
            occupancy_aware=occupancy_aware,
            prev_board=prev,
            add_threshold=0.45,
        )
        # The weak wrong-color detection never becomes a WHITE stone in either mode. In the
        # occupancy-aware (live) path, presence sustain reads it as "the black stone is
        # still physically there, momentarily misread" and keeps BLACK; the legacy path
        # simply drops it.
        assert board[5][5] != WHITE
        if occupancy_aware:
            assert board[5][5] == BLACK
        else:
            assert board[5][5] == EMPTY

    @pytest.mark.parametrize("occupancy_aware", [False, True])
    def test_strong_detection_adds_regardless_of_prev(self, cfg, occupancy_aware):
        ex = BoardStateExtractor()
        img = 950
        strong = self._det_at_cell(5, 5, 0, img, cfg, conf=0.8)
        board = ex.detections_to_board(
            [strong],
            img_w=img,
            img_h=img,
            occupancy_aware=occupancy_aware,
            prev_board=np.zeros((19, 19), dtype=int),
            add_threshold=0.45,
        )
        assert board[5][5] == BLACK

    @pytest.mark.parametrize("occupancy_aware", [False, True])
    def test_no_add_threshold_keeps_legacy_behavior(self, cfg, occupancy_aware):
        ex = BoardStateExtractor()
        img = 950
        weak = self._det_at_cell(5, 5, 0, img, cfg, conf=0.35)
        board = ex.detections_to_board([weak], img_w=img, img_h=img, occupancy_aware=occupancy_aware)
        assert board[5][5] == BLACK  # hysteresis disabled -> anything past detector threshold lands


class TestOffBoardDetections:
    """Warp-margin objects must be DROPPED, never clamped onto a border intersection.

    Regression for the phantom T19 move: a red object in the 1-cell warp margin beside
    the top-right corner was detected as a black stone and clamped to the nearest border
    point (row 0, col 18), then injected as a real move."""

    IMG = 640

    def _margined_extractor(self):
        return BoardStateExtractor(BoardConfig(margin_cells=1.0))

    def _det_at_grid(self, fx, fy, class_id=0, conf=0.9):
        # continuous grid pos -> pixel in a 1-cell-margin warp (20 cells across the image)
        x_px = (1 + fx) / 20 * self.IMG
        y_px = (1 + fy) / 20 * self.IMG
        return Detection(x_center=x_px, y_center=y_px, class_id=class_id, confidence=conf)

    @pytest.mark.parametrize("occupancy_aware", [False, True])
    def test_margin_object_never_becomes_border_stone(self, occupancy_aware):
        ex = self._margined_extractor()
        phantom = self._det_at_grid(fx=18.9, fy=-0.9)  # in the margin, beside the corner
        board = ex.detections_to_board([phantom], img_w=self.IMG, img_h=self.IMG, occupancy_aware=occupancy_aware)
        assert np.all(board == EMPTY)

    @pytest.mark.parametrize("occupancy_aware", [False, True])
    def test_slight_overshoot_still_maps_to_edge_row(self, occupancy_aware):
        # A sloppily placed border stone displaced <0.5 cell outward must keep working.
        ex = self._margined_extractor()
        stone = self._det_at_grid(fx=18.3, fy=-0.3)
        board = ex.detections_to_board([stone], img_w=self.IMG, img_h=self.IMG, occupancy_aware=occupancy_aware)
        assert board[0][18] == BLACK

    def test_cell_confidences_ignore_off_board_detections(self):
        ex = self._margined_extractor()
        phantom = self._det_at_grid(fx=18.9, fy=-0.9, conf=0.8)
        assert ex.cell_confidences([phantom], img_w=self.IMG, img_h=self.IMG) == {}


class TestCellTop:
    IMG = 640

    def _det_at_grid(self, fx, fy, class_id=0, conf=0.9):
        cfg = BoardConfig(margin_cells=1.0)
        x_px = (1 + fx) / 20 * self.IMG
        y_px = (1 + fy) / 20 * self.IMG
        return Detection(x_center=x_px, y_center=y_px, class_id=class_id, confidence=conf)

    def _extractor(self):
        return BoardStateExtractor(BoardConfig(margin_cells=1.0))

    def test_highest_confidence_with_class(self):
        ex = self._extractor()
        dets = [
            self._det_at_grid(3, 3, class_id=0, conf=0.42),
            self._det_at_grid(3.1, 3, class_id=1, conf=0.38),  # same cell, weaker white
            self._det_at_grid(5, 5, class_id=1, conf=0.7),
        ]
        top = ex.cell_top(dets, img_w=self.IMG, img_h=self.IMG)
        assert top[(3, 3)] == (0.42, 0)
        assert top[(5, 5)] == (0.7, 1)

    def test_off_board_and_led_classes_excluded(self):
        ex = self._extractor()
        dets = [
            self._det_at_grid(18.9, -0.9, class_id=0, conf=0.9),  # warp margin
            self._det_at_grid(3, 3, class_id=2, conf=0.9),  # led_red
        ]
        assert ex.cell_top(dets, img_w=self.IMG, img_h=self.IMG) == {}


class TestPresenceSustain:
    """Stones do not vanish into thin air: an established stone survives frames where the
    model misreads it (led_red / wrong color); it leaves only when NO detection is near."""

    IMG = 950

    def _det_at_cell(self, row, col, class_id, conf, cfg):
        from katrain.vision.coordinates import grid_to_physical

        x_mm, y_mm = grid_to_physical(col, row, config=cfg)
        return Detection(
            x_center=x_mm / cfg.total_width * self.IMG,
            y_center=y_mm / cfg.total_length * self.IMG,
            class_id=class_id,
            confidence=conf,
        )

    def _run(self, dets, prev):
        cfg = BoardConfig()
        ex = BoardStateExtractor(cfg)
        return ex.detections_to_board(
            dets, img_w=self.IMG, img_h=self.IMG, occupancy_aware=True, prev_board=prev, add_threshold=0.40
        )

    def _prev_black(self):
        prev = np.zeros((19, 19), dtype=int)
        prev[5][5] = BLACK
        return prev

    def test_led_misread_keeps_stone(self):
        cfg = BoardConfig()
        dets = [self._det_at_cell(5, 5, 2, 0.6, cfg)]  # black stone read as led_red
        board = self._run(dets, self._prev_black())
        assert board[5][5] == BLACK

    def test_color_flip_keeps_original_stone(self):
        cfg = BoardConfig()
        dets = [self._det_at_cell(5, 5, 1, 0.35, cfg)]  # black stone read as weak white
        board = self._run(dets, self._prev_black())
        assert board[5][5] == BLACK

    def test_true_removal_clears_cell(self):
        board = self._run([], self._prev_black())  # nothing detected anywhere near
        assert board[5][5] == EMPTY

    def test_distant_detection_does_not_sustain(self):
        cfg = BoardConfig()
        dets = [self._det_at_cell(5, 7, 2, 0.6, cfg)]  # led two cells away
        board = self._run(dets, self._prev_black())
        assert board[5][5] == EMPTY


class TestStickyAssignment:
    """A boundary-straddling detection stays on the cell it held in the previous raw board
    instead of re-rounding every frame (bimodal wobble broke per-cell voting)."""

    IMG = 950

    def _det_at_grid(self, fy, fx, class_id=0, conf=0.6):
        cfg = BoardConfig()
        gs = cfg.grid_size - 1
        x_px = (fx * cfg.board_width_mm / gs) / cfg.total_width * self.IMG
        y_px = (fy * cfg.board_length_mm / gs) / cfg.total_length * self.IMG
        return Detection(x_center=x_px, y_center=y_px, class_id=class_id, confidence=conf)

    def _run(self, dets, sticky):
        ex = BoardStateExtractor(BoardConfig())
        return ex.detections_to_board(
            dets, img_w=self.IMG, img_h=self.IMG, occupancy_aware=True, sticky_board=sticky
        )

    def test_snaps_to_established_cell(self):
        sticky = np.zeros((19, 19), dtype=int)
        sticky[5][2] = BLACK  # previous frame put the stone on col 2
        board = self._run([self._det_at_grid(5, 2.55)], sticky)  # rounds to col 3 without sticky
        assert board[5][2] == BLACK
        assert board[5][3] == EMPTY

    def test_out_of_radius_rounds_normally(self):
        sticky = np.zeros((19, 19), dtype=int)
        sticky[5][2] = BLACK
        board = self._run([self._det_at_grid(5, 2.75)], sticky)  # 0.75 > radius
        assert board[5][3] == BLACK

    def test_other_color_does_not_attract(self):
        sticky = np.zeros((19, 19), dtype=int)
        sticky[5][2] = WHITE
        board = self._run([self._det_at_grid(5, 2.55)], sticky)  # black det, white sticky
        assert board[5][3] == BLACK
        assert board[5][2] == EMPTY

    def test_adjacent_new_stone_unaffected(self):
        sticky = np.zeros((19, 19), dtype=int)
        sticky[5][2] = BLACK
        board = self._run([self._det_at_grid(5, 2.05), self._det_at_grid(5, 3.05)], sticky)
        assert board[5][2] == BLACK  # established stone stays
        assert board[5][3] == BLACK  # genuinely adjacent stone keeps its own cell

    def test_no_sticky_board_is_legacy_behavior(self):
        board = self._run([self._det_at_grid(5, 2.55)], None)
        assert board[5][3] == BLACK


class TestMaskBlocksAddsOnly:
    """回归（首手落子不识别）：亮灯格遮蔽只阻止"新增"幻影（R7.1 眩光），绝不驱逐
    已确立的子——否则"请拿走"蓝灯会让系统看不见它所指的那颗子（灯/识别死循环），
    并使 removal_pending 在子还在盘上时误自清。"""

    IMG = 950

    def _det(self, row, col, class_id=0, conf=0.6):
        cfg = BoardConfig()
        x_mm, y_mm = grid_to_physical(col, row, config=cfg)
        return Detection(
            x_center=x_mm / cfg.total_width * self.IMG,
            y_center=y_mm / cfg.total_length * self.IMG,
            class_id=class_id,
            confidence=conf,
        )

    def _run(self, dets, masked, prev):
        ex = BoardStateExtractor(BoardConfig())
        return ex.detections_to_board(
            dets,
            img_w=self.IMG,
            img_h=self.IMG,
            occupancy_aware=True,
            masked_cells=masked,
            prev_board=prev,
            add_threshold=0.40,
        )

    def test_established_stone_at_lit_cell_keeps_being_recognized(self):
        prev = np.zeros((19, 19), dtype=int)
        prev[5][5] = BLACK
        board = self._run([self._det(5, 5, 0, 0.6)], {(5, 5)}, prev)
        assert board[5][5] == BLACK

    def test_glare_on_empty_lit_cell_still_blocked(self):
        prev = np.zeros((19, 19), dtype=int)  # cell empty in last stable board
        board = self._run([self._det(5, 5, 1, 0.6)], {(5, 5)}, prev)
        assert board[5][5] == EMPTY

    def test_no_prev_board_blocks_conservatively(self):
        board = self._run([self._det(5, 5, 0, 0.6)], {(5, 5)}, None)
        assert board[5][5] == EMPTY
