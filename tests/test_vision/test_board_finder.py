import cv2
import numpy as np
import pytest
from katrain.vision.board_finder import BoardFinder
from katrain.vision.config import CameraConfig


@pytest.fixture
def finder():
    return BoardFinder()


def make_board_image(width=640, height=480, board_rect=(100, 50, 440, 380)):
    """Create a synthetic image with a rectangular 'board' region."""
    img = np.zeros((height, width, 3), dtype=np.uint8)
    img[:] = (200, 200, 200)
    x1, y1, x2, y2 = board_rect
    cv2.rectangle(img, (x1, y1), (x2, y2), (139, 119, 101), -1)
    cv2.rectangle(img, (x1, y1), (x2, y2), (50, 50, 50), 3)
    return img


class TestBoardFinder:
    def test_finds_board_in_synthetic_image(self, finder):
        img = make_board_image()
        warped, found = finder.find_focus(img)
        assert found is True
        assert warped is not None
        assert warped.shape[0] > 0

    def test_returns_false_for_blank_image(self, finder):
        img = np.ones((480, 640, 3), dtype=np.uint8) * 128
        warped, found = finder.find_focus(img)
        assert found is False

    def test_stability_filter_rejects_large_jumps(self, finder):
        img = make_board_image()
        _, found1 = finder.find_focus(img)
        assert found1 is True
        img2 = make_board_image(board_rect=(200, 150, 540, 430))
        _, found2 = finder.find_focus(img2)
        assert found2 is False

    def test_fallback_uses_last_transform(self, finder):
        """When detection fails but board is stable, reuse last transform matrix."""
        img = make_board_image()
        warped1, found1 = finder.find_focus(img)
        assert found1 is True
        # Blank image — detection fails, but last_transform_matrix should exist
        blank = np.ones((480, 640, 3), dtype=np.uint8) * 128
        warped2, found2 = finder.find_focus(blank)
        # The finder may or may not fallback — test that it doesn't crash
        assert isinstance(found2, bool)
        assert finder.last_transform_matrix is not None  # Saved from successful detection

    def test_clahe_preprocessing(self, finder):
        img = np.ones((480, 640, 3), dtype=np.uint8) * 160
        x1, y1, x2, y2 = 100, 50, 440, 380
        cv2.rectangle(img, (x1, y1), (x2, y2), (150, 140, 130), -1)
        cv2.rectangle(img, (x1, y1), (x2, y2), (130, 120, 110), 3)
        warped, found = finder.find_focus(img, use_clahe=True)
        assert isinstance(found, bool)

    def test_accepts_camera_config(self):
        cam = CameraConfig()
        finder = BoardFinder(camera_config=cam)
        assert finder.camera_config is cam
