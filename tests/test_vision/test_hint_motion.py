"""Hint auto-dismiss uses hand motion even while move detection is paused."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import numpy as np
import pytest

from katrain.vision.config_service import VisionServiceConfig
from katrain.vision.motion_filter import MotionFilter
from katrain.vision.service import VisionService
from katrain.vision.worker import _VisionWorkerLoop
from katrain.vision.worker_inprocess import InProcessAdapter


@pytest.mark.parametrize("worker_type", [_VisionWorkerLoop, InProcessAdapter])
def test_paused_worker_records_hand_motion_but_not_small_hint_lamp_blink(worker_type):
    worker = worker_type.__new__(worker_type)
    worker._paused = True
    worker._motion_filter = MotionFilter()
    worker._motion_mask = lambda frame: np.ones(frame.shape[:2], dtype=bool)
    worker._averager = MagicMock()
    worker._last_motion_log = None
    worker._last_motion_at = None
    frame = np.zeros((200, 200, 3), dtype=np.uint8)
    assert worker._motion_is_stable(frame)

    lamps = frame.copy()
    for row, col in ((30, 30), (30, 150), (150, 30), (150, 150), (90, 90)):
        lamps[row : row + 5, col : col + 5] = 255
    assert worker._motion_is_stable(lamps)
    assert worker._last_motion_at is None

    hand = lamps.copy()
    hand[50:130, 60:140] = 200
    assert not worker._motion_is_stable(hand)
    assert worker._last_motion_at is not None


def test_vision_service_reads_latest_worker_motion_without_a_websocket_viewer():
    service = VisionService(VisionServiceConfig())
    service._worker = MagicMock()
    service._worker.get_status.return_value = SimpleNamespace(last_motion_at=123.0)

    assert getattr(service, "last_motion_at", None) == 123.0

