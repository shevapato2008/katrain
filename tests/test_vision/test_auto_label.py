import numpy as np
import pytest

from katrain.vision.config import BoardConfig
from katrain.vision.coordinates import grid_to_pixel
from katrain.vision.tools.auto_label import (
    LabeledStone,
    StoneColor,
    classify_intersection,
    draw_verification,
    label_board_image,
    write_yolo_labels,
)


@pytest.fixture
def board_config():
    return BoardConfig()


def make_hsv_board(width=640, height=680, base_hue=20, base_sat=80, base_val=140):
    """Create a synthetic HSV board image with wood-like color."""
    img = np.full((height, width, 3), (base_hue, base_sat, base_val), dtype=np.uint8)
    return img


def place_stone_hsv(hsv_img, px, py, color, radius=15):
    """Draw a stone in HSV space at pixel (px, py)."""
    h, w = hsv_img.shape[:2]
    yy, xx = np.ogrid[:h, :w]
    mask = (xx - px) ** 2 + (yy - py) ** 2 <= radius**2
    if color == "black":
        hsv_img[mask] = (0, 0, 30)
    elif color == "white":
        hsv_img[mask] = (0, 10, 220)


class TestClassifyIntersection:
    def test_empty_wood(self):
        hsv = make_hsv_board(100, 100)
        result = classify_intersection(hsv, 50, 50, half_patch=5)
        assert result == StoneColor.EMPTY

    def test_black_stone(self):
        hsv = make_hsv_board(100, 100)
        hsv[45:56, 45:56] = (0, 0, 30)
        result = classify_intersection(hsv, 50, 50, half_patch=5)
        assert result == StoneColor.BLACK

    def test_white_stone(self):
        hsv = make_hsv_board(100, 100)
        hsv[45:56, 45:56] = (0, 10, 220)
        result = classify_intersection(hsv, 50, 50, half_patch=5)
        assert result == StoneColor.WHITE

    def test_edge_clamping(self):
        hsv = make_hsv_board(100, 100)
        result = classify_intersection(hsv, 0, 0, half_patch=5)
        assert result == StoneColor.EMPTY

    def test_custom_thresholds(self):
        hsv = make_hsv_board(100, 100)
        hsv[45:56, 45:56] = (0, 0, 90)
        result = classify_intersection(hsv, 50, 50, half_patch=5, black_v_max=80)
        assert result == StoneColor.EMPTY
        result = classify_intersection(hsv, 50, 50, half_patch=5, black_v_max=100)
        assert result == StoneColor.BLACK


class TestLabelBoardImage:
    def test_empty_board(self, board_config):
        hsv = make_hsv_board()
        bgr = np.full_like(hsv, (140, 119, 139))
        labels = label_board_image(bgr, config=board_config)
        assert len(labels) == 0

    def test_single_black_stone(self, board_config):
        width, height = 640, 680
        hsv = make_hsv_board(width, height)
        px, py = grid_to_pixel(3, 3, width, height, board_config)
        place_stone_hsv(hsv, px, py, "black")
        bgr = cv2_hsv_to_bgr(hsv)
        labels = label_board_image(bgr, config=board_config)
        assert len(labels) == 1
        assert labels[0].color == StoneColor.BLACK
        assert labels[0].grid_x == 3
        assert labels[0].grid_y == 3

    def test_multiple_stones(self, board_config):
        width, height = 640, 680
        hsv = make_hsv_board(width, height)
        positions = [(0, 0, "black"), (9, 9, "white"), (18, 18, "black")]
        for gx, gy, color in positions:
            px, py = grid_to_pixel(gx, gy, width, height, board_config)
            place_stone_hsv(hsv, px, py, color)
        bgr = cv2_hsv_to_bgr(hsv)
        labels = label_board_image(bgr, config=board_config)
        assert len(labels) == 3
        colors = {(l.grid_x, l.grid_y): l.color for l in labels}
        assert colors[(0, 0)] == StoneColor.BLACK
        assert colors[(9, 9)] == StoneColor.WHITE
        assert colors[(18, 18)] == StoneColor.BLACK


class TestWriteYoloLabels:
    def test_writes_correct_format(self, tmp_path):
        labels = [
            LabeledStone(grid_x=0, grid_y=0, color=StoneColor.BLACK, pixel_x=10, pixel_y=10),
            LabeledStone(grid_x=9, grid_y=9, color=StoneColor.WHITE, pixel_x=320, pixel_y=340),
        ]
        output_path = tmp_path / "test.txt"
        write_yolo_labels(labels, output_path, img_w=640, img_h=680)

        lines = output_path.read_text().strip().split("\n")
        assert len(lines) == 2

        parts0 = lines[0].split()
        assert parts0[0] == "0"  # black = class 0
        assert len(parts0) == 5
        x, y, w, h = [float(v) for v in parts0[1:]]
        assert 0.0 <= x <= 1.0
        assert 0.0 <= y <= 1.0
        assert 0.0 < w < 1.0
        assert 0.0 < h < 1.0

        parts1 = lines[1].split()
        assert parts1[0] == "1"  # white = class 1

    def test_empty_labels(self, tmp_path):
        output_path = tmp_path / "empty.txt"
        write_yolo_labels([], output_path, img_w=640, img_h=680)
        assert output_path.read_text() == ""

    def test_bbox_size(self, tmp_path):
        labels = [LabeledStone(grid_x=9, grid_y=9, color=StoneColor.BLACK, pixel_x=320, pixel_y=340)]
        output_path = tmp_path / "test.txt"
        write_yolo_labels(labels, output_path, img_w=640, img_h=680)
        parts = output_path.read_text().strip().split()
        w, h = float(parts[3]), float(parts[4])
        assert abs(w - 0.052) < 0.01
        assert abs(h - 0.048) < 0.01


class TestDrawVerification:
    def test_returns_image(self, board_config):
        img = np.zeros((680, 640, 3), dtype=np.uint8)
        labels = [
            LabeledStone(grid_x=3, grid_y=3, color=StoneColor.BLACK, pixel_x=100, pixel_y=100),
            LabeledStone(grid_x=9, grid_y=9, color=StoneColor.WHITE, pixel_x=320, pixel_y=340),
        ]
        result = draw_verification(img, labels)
        assert result.shape == img.shape
        assert not np.array_equal(result, img)


def cv2_hsv_to_bgr(hsv_img):
    """Helper to convert HSV to BGR for label_board_image which expects BGR input."""
    import cv2

    return cv2.cvtColor(hsv_img, cv2.COLOR_HSV2BGR)
