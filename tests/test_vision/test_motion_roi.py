import numpy as np
import pytest

import katrain.vision.motion_roi as motion_roi
from katrain.vision.motion_roi import MotionRoiMaskCache, build_motion_roi_mask


FRAME_SHAPE = (200, 300, 3)
CURRENT_CORNERS = [(60, 40), (240, 40), (240, 160), (60, 160)]


def test_mask_fills_board_and_expands_one_mean_grid_spacing():
    mask = build_motion_roi_mask(FRAME_SHAPE, CURRENT_CORNERS)

    assert mask.dtype == np.bool_
    assert mask.shape == FRAME_SHAPE[:2]
    assert mask[100, 100]
    assert mask[40 - 7, 150]
    assert not mask[40 - 10, 150]


def test_mask_scales_corners_from_calibration_resolution():
    source_corners = [(120, 80), (480, 80), (480, 320), (120, 320)]

    mask = build_motion_roi_mask(FRAME_SHAPE, source_corners, source_size=(600, 400))

    assert mask[100, 100]
    assert mask[40 - 7, 150]
    assert not mask[40 - 10, 150]


def test_old_lock_without_source_size_uses_current_pixel_space():
    mask = build_motion_roi_mask(FRAME_SHAPE, CURRENT_CORNERS, source_size=(None, None))

    assert mask[100, 100]
    assert mask[40 - 7, 150]


def test_noncontiguous_float32_corners_are_supported():
    corners = np.array([(60, 40, 0), (240, 40, 0), (240, 160, 0), (60, 160, 0)], dtype=np.float32)[:, :2]

    mask = build_motion_roi_mask(FRAME_SHAPE, corners)

    assert mask is not None
    assert mask[100, 100]


MALFORMED = [(60, 40), (240, 40), (240, 160)]
NONFINITE = [(60, 40), (240, 40), (240, np.nan), (60, 160)]
DEGENERATE = [(60, 40), (120, 80), (180, 120), (240, 160)]
WHOLLY_OFFSCREEN = [(-500, -400), (-300, -400), (-300, -200), (-500, -200)]


@pytest.mark.parametrize("corners", [MALFORMED, NONFINITE, DEGENERATE, WHOLLY_OFFSCREEN])
def test_invalid_corners_return_none(corners):
    assert build_motion_roi_mask(FRAME_SHAPE, corners) is None


def test_partially_clipped_board_remains_valid():
    corners = [(-20, 40), (240, 40), (240, 160), (-20, 160)]

    mask = build_motion_roi_mask(FRAME_SHAPE, corners)

    assert mask is not None
    assert mask[100, 10]


def test_board_just_outside_left_edge_is_rejected_before_rounding():
    corners = [(-10, 40), (-0.1, 40), (-0.1, 160), (-10, 160)]

    assert build_motion_roi_mask(FRAME_SHAPE, corners) is None


def test_implausibly_huge_board_returns_none_without_kernel_allocation(monkeypatch):
    corners = [(-1e8, 40), (1e8, 40), (1e8, 160), (-1e8, 160)]

    def fail_kernel_allocation(*args, **kwargs):
        raise AssertionError("must reject implausibly large dilation radius")

    monkeypatch.setattr(motion_roi.cv2, "getStructuringElement", fail_kernel_allocation)

    assert build_motion_roi_mask(FRAME_SHAPE, corners) is None


def test_cache_reuses_mask_and_source_dimensions_are_part_of_key():
    cache = MotionRoiMaskCache()
    first = cache.get(FRAME_SHAPE, CURRENT_CORNERS)
    second = cache.get(FRAME_SHAPE, CURRENT_CORNERS)
    scaled = cache.get(FRAME_SHAPE, CURRENT_CORNERS, source_size=(600, 400))

    assert first is second
    assert scaled is not first


def test_cache_reuses_none_for_invalid_geometry(monkeypatch):
    calls = 0
    original_builder = motion_roi.build_motion_roi_mask

    def counting_builder(*args, **kwargs):
        nonlocal calls
        calls += 1
        return original_builder(*args, **kwargs)

    monkeypatch.setattr(motion_roi, "build_motion_roi_mask", counting_builder)
    cache = MotionRoiMaskCache()
    corners = [(-500, -400), (-300, -400), (-300, -200), (-500, -200)]

    assert cache.get(FRAME_SHAPE, corners) is None
    assert cache.get(FRAME_SHAPE, corners) is None
    assert calls == 1


def test_invalidate_forces_mask_rebuild():
    cache = MotionRoiMaskCache()
    first = cache.get(FRAME_SHAPE, CURRENT_CORNERS)
    cache.invalidate()
    second = cache.get(FRAME_SHAPE, CURRENT_CORNERS)

    assert second is not first
    np.testing.assert_array_equal(second, first)
