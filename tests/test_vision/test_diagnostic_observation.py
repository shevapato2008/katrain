"""Read-only diagnostic observation of the one real recognition chain.

The observer must never change what the chain computes: same inference count, same boards,
same state, with or without it. It only copies what one processing batch already produced.
"""

from unittest.mock import MagicMock, patch

import numpy as np

from katrain.vision.board_state import BoardStateExtractor
from katrain.vision.config import DEFAULT_MARGIN_CELLS, BoardConfig
from katrain.vision.stone_detector import Detection
from tests.test_vision.board_state_corpus import IMG, grid_to_px

CFG = BoardConfig(margin_cells=DEFAULT_MARGIN_CELLS)


def _det(row, col, cls, conf, dx=0.0):
    x, y = grid_to_px(CFG, float(col) + dx, float(row))
    return Detection(x_center=x, y_center=y, class_id=cls, confidence=conf, bbox=(x - 20, y - 20, x + 20, y + 20))


class _Backend:
    def __init__(self):
        self.calls = 0
        self._imgsz = 960
        self.output = []

    def load(self, model_path, meta_path=None):
        self.loaded = model_path

    def detect(self, image, confidence_threshold, iou_threshold=None):
        self.calls += 1
        return list(self.output)


def _detector(imgsz=960):
    from katrain.vision.stone_detector import StoneDetector

    backend = _Backend()
    with patch("katrain.vision.inference.create_backend", return_value=backend):
        detector = StoneDetector("model.pt", backend="ultralytics", imgsz=imgsz)
    return detector, backend


def test_detect_observed_is_one_inference_with_the_same_result_as_detect():
    detector, backend = _detector()
    duplicate = _det(4, 4, 0, 0.9)
    backend.output = [_det(4, 4, 0, 0.95), duplicate, _det(10, 10, 1, 0.8)]
    plain = detector.detect(np.zeros((IMG, IMG, 3), np.uint8))
    calls = backend.calls
    nms, deduped = detector.detect_observed(np.zeros((IMG, IMG, 3), np.uint8))
    assert backend.calls == calls + 1
    assert len(nms) == 3 and len(deduped) == len(plain) == 2
    assert [(d.class_id, d.confidence) for d in deduped] == [(d.class_id, d.confidence) for d in plain]


def test_requested_imgsz_reaches_the_ultralytics_backend():
    detector, backend = _detector(imgsz=640)
    assert backend._imgsz == 640 and detector.imgsz == 640
    _, default_backend = _detector()
    assert default_backend._imgsz == 960


def test_frame_averager_reports_exactly_the_frames_it_averaged():
    from katrain.vision.temporal import FrameAverager

    averager = FrameAverager(3)
    frame = np.zeros((4, 4, 3), np.uint8)
    for seq in (1, 2, 3, 4):
        averager.add(frame, ident=seq)
    assert averager.contributors == (2, 3, 4)
    averager.reset()
    assert averager.contributors == ()
    averager.add(frame)
    assert averager.contributors == (None,)
    assert FrameAverager(1).add(frame, ident=9) is frame


class _ScriptedDetector:
    instance = None

    def __init__(self, model_path, backend="ultralytics", confidence_threshold=0.5, **kwargs):
        self.confidence_threshold = confidence_threshold
        self.script = []
        self.calls = 0
        _ScriptedDetector.instance = self

    def _next(self):
        self.calls += 1
        frame = self.script.pop(0) if self.script else []
        return [d for d in frame if d.confidence >= self.confidence_threshold]

    def detect(self, image):
        return self._next()

    def detect_observed(self, image):
        found = self._next()
        return list(found), list(found)


class _Camera:
    is_connected = True

    def __init__(self, frames):
        self.frames, self.seq, self.worker = frames, 0, None

    def _tick(self):
        self.frames -= 1
        self.seq += 1
        if self.frames <= 0:
            self.worker._running = False
        return np.full((10, 10, 3), self.seq, dtype=np.uint8)

    def read_frame(self):
        return self._tick()

    def read_frame_identified(self):
        frame = self._tick()
        return frame, self.seq, float(self.seq)


def _run(script, observer=None):
    from katrain.vision.worker_inprocess import InProcessAdapter

    with patch("katrain.vision.worker_inprocess.StoneDetector", _ScriptedDetector):
        worker = InProcessAdapter(
            {"board_size": 19, "enhance": "off", "auto_exposure": "off"}, camera=_Camera(len(script))
        )
    worker._camera.worker = worker
    worker.needs_frames = lambda: True
    worker._running = True
    worker._config["capture_fps"] = 100000
    worker._motion_is_stable = MagicMock(return_value=True)
    worker._warp_frame = lambda frame: (np.full((IMG, IMG, 3), int(frame[0, 0, 0]), dtype=np.uint8), True)
    extractor = BoardStateExtractor(CFG)
    worker._active_extractor = lambda: extractor
    worker._maybe_send_preview = MagicMock()
    _ScriptedDetector.instance.script = [list(frame) for frame in script]
    if observer is not None:
        worker.set_observer(observer, interval=0.0)
    worker._loop()
    return worker, _ScriptedDetector.instance


SCRIPT = [[_det(3, 3, 0, 0.9), _det(5, 6, 1, 0.8, dx=0.3)]] * 4 + [[_det(3, 3, 0, 0.9)]] * 3


def test_observer_changes_nothing_the_chain_computes():
    plain, plain_detector = _run(SCRIPT)
    snapshots = []
    observed, observed_detector = _run(SCRIPT, observer=snapshots.append)
    assert np.array_equal(plain._last_stable_board, observed._last_stable_board)
    assert np.array_equal(plain._prev_observed_board, observed._prev_observed_board)
    assert plain_detector.calls == observed_detector.calls == len(SCRIPT)
    assert plain._observation_seq == observed._observation_seq
    assert len(snapshots) == len(SCRIPT)


def test_a_snapshot_holds_one_batch_from_raw_frame_to_published_board():
    snapshots = []
    _run(SCRIPT, observer=snapshots.append)
    snap = snapshots[3]
    assert snap["camera_seq"] == 4 and int(snap["raw"][0, 0, 0]) == 4
    assert int(snap["pure_warped"][0, 0, 0]) == 4  # this batch's own frame, before averaging
    assert snap["contributors"][-1] == 4 and len(snap["contributors"]) >= 2
    assert len(snap["nms"]) == 2 and [tier for _, tier in snap["filtered"]] == ["keep", "keep"]
    assert snap["projection"][3][3] == 1 and snap["projection"][5][6] == 2
    assert snap["assigned"][3][3] == 1 and snap["published"].shape == (19, 19)
    last = snapshots[-1]
    assert last["assigned"][5][6] == 0 and last["published"][5][6] == 0


def test_a_broken_observer_cannot_stop_recognition():
    def explode(snapshot):
        raise RuntimeError("observer bug")

    worker, detector = _run(SCRIPT, observer=explode)
    assert detector.calls == len(SCRIPT) and worker._observation_seq == len(SCRIPT)


def test_camera_hub_reads_a_frame_with_its_identity_under_one_lock():
    from katrain.web.core.camera_hub import CameraHub, CameraHubConfig

    hub = CameraHub(CameraHubConfig(device_id=0))
    inner = MagicMock()
    inner.read_frame_identified.return_value = ("frame", 7, 1.5)
    hub._camera = inner
    assert hub.read_frame_identified() == ("frame", 7, 1.5)
    hub._camera = None
    assert hub.read_frame_identified() == (None, 0, 0.0)
