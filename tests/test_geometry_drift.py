import cv2
import numpy as np

from katrain.vision.geometry_drift import GeometryDriftMonitor


def _grid(size=400, spacing=40):
    image = np.full((size, size, 3), 100, np.uint8)
    for pos in range(20, size, spacing):
        cv2.line(image, (pos, 0), (pos, size - 1), (20, 20, 20), 2)
        cv2.line(image, (0, pos), (size - 1, pos), (20, 20, 20), 2)
    cv2.circle(image, (73, 91), 8, (180, 180, 180), -1)
    return image


def _translate(image, dx, dy, brightness=0):
    matrix = np.float32([[1, 0, dx], [0, 1, dy]])
    moved = cv2.warpAffine(image, matrix, (image.shape[1], image.shape[0]), borderMode=cv2.BORDER_REFLECT)
    return np.clip(moved.astype(np.int16) + brightness, 0, 255).astype(np.uint8)


def test_brightness_change_and_small_shift_do_not_degrade():
    reference = _grid()
    monitor = GeometryDriftMonitor(reference, cell_spacing_px=40, threshold_cells=0.10, consecutive_frames=3)

    bright = monitor.update(_translate(reference, 0, 0, brightness=35))
    small = monitor.update(_translate(reference, 2, 1))

    assert bright.degraded is False
    assert small.degraded is False


def test_large_shift_requires_three_consecutive_frames():
    reference = _grid()
    monitor = GeometryDriftMonitor(reference, cell_spacing_px=40, threshold_cells=0.10, consecutive_frames=3)

    first = monitor.update(_translate(reference, 9, 0))
    second = monitor.update(_translate(reference, 9, 0))
    third = monitor.update(_translate(reference, 9, 0))

    assert first.degraded is False
    assert second.degraded is False
    assert third.degraded is True
    assert third.shift_cells > 0.20
