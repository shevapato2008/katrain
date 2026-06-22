from unittest.mock import MagicMock, patch

import numpy as np

from katrain.vision.config_service import VisionServiceConfig
from katrain.vision.service import VisionService
from katrain.vision.worker_inprocess import InProcessAdapter
from tests.test_geometry_lock import _synth


def test_inprocess_adapter_does_not_own_injected_camera():
    camera = MagicMock()
    camera.is_connected = True

    with patch("katrain.vision.worker_inprocess.StoneDetector"):
        adapter = InProcessAdapter({"model_path": "dummy.onnx"}, camera=camera)

    adapter.stop()

    camera.open.assert_not_called()
    camera.close.assert_not_called()


def test_vision_service_uses_inprocess_adapter_for_shared_camera():
    camera = MagicMock()
    config = VisionServiceConfig(enabled=True, model_path="dummy.onnx", process_mode="worker")

    with patch("katrain.vision.worker_inprocess.StoneDetector"), patch.object(InProcessAdapter, "start"):
        service = VisionService(config, frame_source=camera)
        service.start()

    assert isinstance(service._worker, InProcessAdapter)
    assert service._worker._camera is camera


def test_shared_camera_adapter_requires_geometry_and_uses_locked_transform():
    camera = MagicMock()
    camera.is_connected = True
    frame = np.zeros((32, 48, 3), np.uint8)
    geometry = _synth()
    geometry.out_size = 20
    geometry.M = np.eye(3)

    with patch("katrain.vision.worker_inprocess.StoneDetector"):
        adapter = InProcessAdapter({"model_path": "dummy.onnx"}, camera=camera)
    adapter._board_finder = MagicMock()

    assert adapter._warp_frame(frame) == (None, False)
    adapter.set_geometry(geometry)
    warped, found = adapter._warp_frame(frame)

    assert found is True
    assert warped.shape == (20, 20, 3)
    adapter._board_finder.find_focus.assert_not_called()
