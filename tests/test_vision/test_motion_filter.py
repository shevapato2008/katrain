import numpy as np
import pytest
from katrain.vision.motion_filter import MotionFilter


@pytest.fixture
def mf():
    return MotionFilter(change_ratio_threshold=0.05, pixel_diff_threshold=30)


class TestMotionFilter:
    def test_first_frame_is_stable(self, mf):
        frame = np.ones((480, 640, 3), dtype=np.uint8) * 128
        assert mf.is_stable(frame) is True

    def test_identical_frames_are_stable(self, mf):
        frame = np.ones((480, 640, 3), dtype=np.uint8) * 128
        mf.is_stable(frame)
        assert mf.is_stable(frame.copy()) is True

    def test_large_change_is_unstable(self, mf):
        frame1 = np.zeros((480, 640, 3), dtype=np.uint8)
        mf.is_stable(frame1)
        frame2 = np.ones((480, 640, 3), dtype=np.uint8) * 200
        assert mf.is_stable(frame2) is False

    def test_small_change_is_stable(self, mf):
        frame1 = np.ones((480, 640, 3), dtype=np.uint8) * 128
        mf.is_stable(frame1)
        frame2 = np.ones((480, 640, 3), dtype=np.uint8) * 130
        assert mf.is_stable(frame2) is True

    def test_localized_bright_spot_stable(self, mf):
        """A single bright pixel should not trigger instability (unlike max-diff approach)."""
        frame1 = np.ones((480, 640, 3), dtype=np.uint8) * 128
        mf.is_stable(frame1)
        frame2 = frame1.copy()
        frame2[100, 100] = [255, 255, 255]  # one bright pixel
        assert mf.is_stable(frame2) is True

    def test_recovers_after_motion(self, mf):
        frame1 = np.ones((480, 640, 3), dtype=np.uint8) * 128
        mf.is_stable(frame1)
        frame2 = np.ones((480, 640, 3), dtype=np.uint8) * 255
        assert mf.is_stable(frame2) is False
        assert mf.is_stable(frame2.copy()) is True
