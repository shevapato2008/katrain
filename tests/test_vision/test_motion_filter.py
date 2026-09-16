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

    def test_roi_motion_rejects_when_full_frame_change_is_below_five_percent(self, mf):
        previous = np.zeros((10, 10, 3), dtype=np.uint8)
        next_frame = previous.copy()
        next_frame[0, 0] = 255
        roi_mask = np.zeros((10, 10), dtype=bool)
        roi_mask[:2, :2] = True
        mf.is_stable_with_regions(previous, roi_mask)

        stable, roi_ratio, full_ratio = mf.is_stable_with_regions(next_frame, roi_mask)

        assert stable is False
        assert roi_ratio == pytest.approx(0.25)
        assert full_ratio == pytest.approx(0.01)

    def test_motion_outside_roi_is_stable_below_global_guard(self, mf):
        previous = np.zeros((10, 10, 3), dtype=np.uint8)
        next_frame = previous.copy()
        next_frame[:2, 2:] = 255
        roi_mask = np.zeros((10, 10), dtype=bool)
        roi_mask[:2, :2] = True
        mf.is_stable_with_regions(previous, roi_mask)

        stable, roi_ratio, full_ratio = mf.is_stable_with_regions(next_frame, roi_mask)

        assert stable is True
        assert roi_ratio == pytest.approx(0.0)
        assert full_ratio == pytest.approx(0.16)

    def test_large_full_frame_change_rejects_even_when_roi_is_quiet(self, mf):
        previous = np.zeros((10, 10, 3), dtype=np.uint8)
        next_frame = previous.copy()
        next_frame[:, 2:] = 255
        roi_mask = np.zeros((10, 10), dtype=bool)
        roi_mask[:, :2] = True
        mf.is_stable_with_regions(previous, roi_mask)

        stable, roi_ratio, full_ratio = mf.is_stable_with_regions(next_frame, roi_mask)

        assert stable is False
        assert roi_ratio == pytest.approx(0.0)
        assert full_ratio == pytest.approx(0.8)

    @pytest.mark.parametrize("roi_mask", [None, np.zeros((10, 10), dtype=bool)])
    def test_missing_or_empty_mask_falls_back_to_full_frame(self, mf, roi_mask):
        previous = np.zeros((10, 10, 3), dtype=np.uint8)
        next_frame = previous.copy()
        next_frame[:1, :] = 255
        mf.is_stable_with_regions(previous, roi_mask)

        stable, roi_ratio, full_ratio = mf.is_stable_with_regions(next_frame, roi_mask)

        assert stable is False
        assert roi_ratio is None
        assert full_ratio == pytest.approx(0.1)

    @pytest.mark.parametrize(
        "previous,next_frame",
        [
            (np.zeros((10, 10, 3), dtype=np.uint8), np.zeros((8, 10, 3), dtype=np.uint8)),
            (np.zeros((10, 10, 3), dtype=np.uint8), np.zeros((10, 10), dtype=np.uint8)),
            (np.zeros((10, 10), dtype=np.uint8), np.zeros((10, 10, 3), dtype=np.uint8)),
        ],
    )
    def test_dimension_or_channel_layout_change_establishes_a_fresh_baseline(self, mf, previous, next_frame):
        mf.is_stable_with_regions(previous)

        stable, roi_ratio, full_ratio = mf.is_stable_with_regions(next_frame)

        assert stable is True
        assert roi_ratio is None
        assert full_ratio == pytest.approx(0.0)
        assert mf.is_stable_with_regions(next_frame)[0] is True

    def test_reset_establishes_a_fresh_baseline(self, mf):
        first = np.zeros((10, 10, 3), dtype=np.uint8)
        second = np.ones((10, 10, 3), dtype=np.uint8) * 255
        mf.is_stable_with_regions(first)
        mf.reset()

        stable, roi_ratio, full_ratio = mf.is_stable_with_regions(second)

        assert stable is True
        assert roi_ratio is None
        assert full_ratio == pytest.approx(0.0)

    def test_rejected_frame_becomes_the_next_comparison_baseline(self, mf):
        first = np.zeros((10, 10, 3), dtype=np.uint8)
        rejected = np.ones((10, 10, 3), dtype=np.uint8) * 255
        mf.is_stable_with_regions(first)
        assert mf.is_stable_with_regions(rejected)[0] is False

        stable, roi_ratio, full_ratio = mf.is_stable_with_regions(rejected.copy())

        assert stable is True
        assert roi_ratio is None
        assert full_ratio == pytest.approx(0.0)
