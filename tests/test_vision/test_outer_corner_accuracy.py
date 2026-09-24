"""Task 9 (P12): the crowded-board accuracy GATE logic (deterministic, injected detectors).

The synthetic-render → real-detector measurement is a benchmark (run via __main__ / hardware);
here we lock the GATE's measurement + thresholding so it can't silently mis-pass.
"""

import io

import cv2
import numpy as np

from katrain.vision.tools.outer_corner_accuracy import (
    corner_error_cells,
    dense_stones,
    gate,
    grab_mjpeg_frames,
    grid_error_cells,
    live_gate,
    measure,
    measure_real,
    render_board,
)

QUAD = np.array([[260, 150], [1010, 170], [1040, 690], [240, 660]], np.float64)


def test_dense_stones_fill_fraction():
    rng = np.random.default_rng(0)
    assert len(dense_stones(0.0, rng)) == 0
    assert len(dense_stones(0.8, rng)) == round(0.8 * 361)
    assert len(dense_stones(1.0, rng)) == 361


def test_corner_error_zero_for_identical_quad():
    assert corner_error_cells(QUAD, QUAD) < 1e-6


def test_corner_error_scales_with_displacement():
    noisy = QUAD + np.array([6, 0])  # shift all corners 6px
    err = corner_error_cells(noisy, QUAD)
    assert err > 0.0
    # 6px on a ~40px camera cell ≈ 0.15 cells — sanity bound
    assert 0.05 < err < 0.5


def test_measure_perfect_detector_passes_gate():
    res = measure(detect_fn=lambda frame: QUAD.copy(), fills=(0.0, 0.8), rotations=(0.0,), base_quad=QUAD)
    assert all(e is not None and e < 1e-6 for e in res.values())
    assert gate(res, max_error_cells=0.12) is True


def test_measure_noisy_detector_fails_gate():
    res = measure(detect_fn=lambda frame: QUAD + np.array([20, 0]), fills=(0.0,), rotations=(0.0,), base_quad=QUAD)
    assert gate(res, max_error_cells=0.12) is False


def test_render_board_produces_frame():
    f = render_board(QUAD, fill_pct=0.5, frame_size=(1280, 720))
    assert f.shape == (720, 1280, 3) and int(f.max()) > 0


def test_gate_false_when_no_detections():
    assert gate({(0.0, 0.0): None}, max_error_cells=0.12) is False


def _blank_frames(n):
    return [np.zeros((720, 1280, 3), np.uint8) for _ in range(n)]


def test_measure_real_scores_every_frame_against_the_reference_quad():
    dets = iter([QUAD.copy(), QUAD + np.array([20, 0]), None])
    res = measure_real(_blank_frames(3), QUAD, detect_fn=lambda f: next(dets))
    assert res[0] < 1e-6
    assert res[1] > 0.12
    assert res[2] is None
    # 一帧超差整组就不过 —— 闸不许靠平均把坏帧抹掉
    assert gate(res, max_error_cells=0.12) is False


def test_measure_real_passes_when_every_detection_is_close():
    res = measure_real(_blank_frames(2), QUAD, detect_fn=lambda f: QUAD + np.array([1, 0]))
    assert gate(res, max_error_cells=0.12) is True


def test_live_gate_needs_most_frames_detected():
    """十帧里只认出一帧、那一帧还合格 —— 不许算过:`gate()` 会丢掉所有 None,样本太少的「过」不是证据。"""
    assert live_gate({0: 0.01, 1: None}) is False
    assert live_gate({i: 0.05 for i in range(8)} | {8: None, 9: None}) is True  # 8/10 且都合格
    assert live_gate({i: 0.05 for i in range(7)} | {i: None for i in range(7, 10)}) is False


def test_one_bad_corner_is_not_hidden_by_the_median():
    """**反向闸。** 一个角偏 20px、三个角全对:四角中位数是 0(2026-09-24 实测),
    网格最大误差是 0.55 格。真机闸量的必须是交叉点,不是四角的中位数。"""
    one_bad = QUAD.copy()
    one_bad[2] += np.array([20.0, 0.0])
    assert corner_error_cells(one_bad, QUAD) == 0.0  # 旧量法的盲区,钉住它存在
    assert grid_error_cells(one_bad, QUAD) > 0.12
    res = measure_real(_blank_frames(1), QUAD, detect_fn=lambda f: one_bad)
    assert gate(res, max_error_cells=0.12) is False


def test_grab_mjpeg_frames_reads_the_kiosk_stream_format(monkeypatch):
    # 用服务端真正写流的那个函数造字节 —— 流格式一改,这条就红
    from katrain.web.api.v1.endpoints.geometry import _mjpeg_part

    ok, jpg = cv2.imencode(".jpg", np.full((48, 64, 3), 128, np.uint8))
    assert ok
    body = b"".join(_mjpeg_part(jpg.tobytes()) for _ in range(3))

    class _Resp(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            self.close()

    monkeypatch.setattr("urllib.request.urlopen", lambda url, timeout=None: _Resp(body))
    frames = grab_mjpeg_frames("http://box/api/v1/geometry/stream", 2)
    assert len(frames) == 2
    assert frames[0].shape == (48, 64, 3)
