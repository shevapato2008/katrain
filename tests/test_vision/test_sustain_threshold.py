"""Presence "sustain" tier (2026-09-22): a stone already on the stable board survives detections
down to confidence_sustain (0.20); new stones, cards and confidence statistics still only see
detections >= confidence_keep (0.30).

Board evidence: far-side white stones in a dense cluster dropped below 0.30 for up to 45 s while
the scene was static, and each drop surfaced as a "missing stone" board-mismatch prompt.
"""

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from katrain.vision.board_state import BoardStateExtractor
from katrain.vision.config import DEFAULT_MARGIN_CELLS, BoardConfig
from katrain.vision.config_service import DEFAULT_CONFIDENCE_SUSTAIN, VisionServiceConfig
from katrain.vision.stone_detector import Detection
from tests.test_vision.board_state_corpus import IMG, grid_to_px

CFG = BoardConfig(margin_cells=DEFAULT_MARGIN_CELLS)
BLACK, WHITE = 1, 2


def test_default_sustain_is_020_and_never_above_keep():
    assert DEFAULT_CONFIDENCE_SUSTAIN == 0.20
    board = VisionServiceConfig(confidence_threshold=0.40, confidence_keep=0.30).to_worker_config()
    assert board["confidence_sustain"] == pytest.approx(0.20)
    low_keep = VisionServiceConfig(confidence_threshold=0.40, confidence_keep=0.15).to_worker_config()
    assert low_keep["confidence_sustain"] == pytest.approx(0.15)
    explicit = VisionServiceConfig(confidence_keep=0.30, confidence_sustain=0.25).to_worker_config()
    assert explicit["confidence_sustain"] == pytest.approx(0.25)


class _ThresholdDetector:
    """Stands in for StoneDetector: returns the scripted detections at or above its threshold."""

    instance = None

    def __init__(self, model_path, backend="ultralytics", confidence_threshold=0.5, **kwargs):
        self.confidence_threshold = confidence_threshold
        self.script = []
        _ThresholdDetector.instance = self

    def detect(self, image):
        frame = self.script.pop(0) if self.script else []
        return [d for d in frame if d.confidence >= self.confidence_threshold]


def _adapter(config, camera=None):
    from katrain.vision.worker_inprocess import InProcessAdapter

    with patch("katrain.vision.worker_inprocess.StoneDetector", _ThresholdDetector):
        adapter = InProcessAdapter(
            {"board_size": 19, "enhance": "off", "auto_exposure": "off", **config}, camera=camera
        )
    adapter.needs_frames = lambda: True
    return adapter


def test_detector_runs_at_the_sustain_threshold_only_when_configured():
    _adapter({"confidence_threshold": 0.40, "confidence_keep": 0.30, "confidence_sustain": 0.20})
    assert _ThresholdDetector.instance.confidence_threshold == pytest.approx(0.20)
    _adapter({"confidence_threshold": 0.40, "confidence_keep": 0.30})  # no sustain key: unchanged
    assert _ThresholdDetector.instance.confidence_threshold == pytest.approx(0.30)


def _det(row, col, cls, conf):
    x, y = grid_to_px(CFG, float(col), float(row))
    return Detection(x_center=x, y_center=y, class_id=cls, confidence=conf, bbox=(x - 20, y - 20, x + 20, y + 20))


class _ScriptedCamera:
    is_connected = True

    def __init__(self, frames):
        self.frames = frames
        self.worker = None

    def read_frame(self):
        self.frames -= 1
        if self.frames <= 0:
            self.worker._running = False
        return np.zeros((10, 10, 3), dtype=np.uint8)


def _run(config, script):
    """Drive the real loop over ``script`` (one detection list per frame); return (stable board, means)."""
    camera = _ScriptedCamera(len(script))
    worker = _adapter(config, camera=camera)
    camera.worker = worker
    worker._running = True
    worker._config["capture_fps"] = 100000
    worker._motion_is_stable = MagicMock(return_value=True)
    worker._warp_frame = MagicMock(return_value=(np.zeros((IMG, IMG, 3), dtype=np.uint8), True))
    worker._averager = MagicMock()
    worker._averager.add.side_effect = lambda frame: frame
    extractor = BoardStateExtractor(CFG)
    worker._active_extractor = lambda: extractor
    worker._maybe_send_preview = MagicMock()
    _ThresholdDetector.instance.script = [list(frame) for frame in script]
    means = []
    real_mean = __import__("katrain.vision.worker_inprocess", fromlist=["x"]).mean_detection_confidence

    def spy(dets):
        means.append([d.confidence for d in dets])
        return real_mean(dets)

    with patch("katrain.vision.worker_inprocess.mean_detection_confidence", side_effect=spy):
        worker._loop()
    return worker._last_stable_board, means


SUSTAIN = {"confidence_threshold": 0.40, "confidence_keep": 0.30, "confidence_sustain": 0.20}
PLACED = [[_det(3, 3, 1, 0.50)]] * 3  # a white stone lands and is confirmed on the stable board
WEAK = [[_det(3, 3, 1, 0.25)]] * 6  # ...then the detector only sees it at 0.25


def test_a_placed_stone_survives_detections_between_sustain_and_keep():
    board, _ = _run(SUSTAIN, PLACED + WEAK)
    assert int(board[3][3]) == WHITE


def test_without_the_sustain_tier_the_same_stone_is_lost():
    """Control: the same input at the old keep-only threshold drops the stone (the device symptom)."""
    board, _ = _run({"confidence_threshold": 0.40, "confidence_keep": 0.30}, PLACED + WEAK)
    assert int(board[3][3]) == 0


def test_a_sustain_tier_detection_never_adds_a_stone_on_an_empty_point():
    board, _ = _run(SUSTAIN, PLACED + [[_det(3, 3, 1, 0.50), _det(9, 9, 0, 0.25)]] * 6)
    assert int(board[9][9]) == 0 and int(board[3][3]) == WHITE


def test_a_sustain_tier_detection_of_the_other_colour_does_not_recolour_a_stone():
    board, _ = _run(SUSTAIN, PLACED + [[_det(3, 3, 0, 0.25)]] * 20)
    assert int(board[3][3]) == WHITE


def test_confidence_statistics_never_see_the_sustain_tier():
    """mean_confidence drives DEGRADED mode; sub-keep boxes must not drag it down."""
    _, means = _run(SUSTAIN, PLACED + WEAK)
    assert means and all(c >= 0.30 for frame in means for c in frame)
    assert means[-1] == []  # the 0.25 frames contribute nothing
