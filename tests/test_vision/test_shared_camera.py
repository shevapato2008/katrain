from unittest.mock import MagicMock, patch

from katrain.vision.config_service import VisionServiceConfig
from katrain.vision.service import VisionService
from katrain.vision.worker_inprocess import InProcessAdapter


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
