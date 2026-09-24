from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import MagicMock

from katrain.web.api.v1.endpoints.vision import router
from katrain.vision.config_service import VisionServiceConfig
from katrain.vision.ipc import CommandType
from katrain.vision.service import VisionService


def test_vision_status_returns_disabled_status_when_service_is_not_enabled():
    app = FastAPI()
    app.include_router(router, prefix="/api/v1/vision")
    client = TestClient(app)

    response = client.get("/api/v1/vision/status")

    assert response.status_code == 200
    # Matches the endpoint's disabled-state contract verbatim: the readiness
    # flags (camera/geometry/model/recognition_ready) and led_connected are all
    # part of the disabled response, not just the first five fields.
    assert response.json() == {
        "enabled": False,
        "camera_connected": False,
        "pose_locked": False,
        "sync_state": "idle",
        "bound_session_id": None,
        "camera_ready": False,
        "geometry_ready": False,
        "model_ready": False,
        "recognition_ready": False,
        "led_connected": False,
    }


def test_deny_stone_endpoint_reaches_the_worker_command_queue():
    app = FastAPI()
    app.include_router(router, prefix="/api/v1/vision")
    service = VisionService(VisionServiceConfig())
    service._worker = MagicMock()
    app.state.vision = service

    response = TestClient(app).post("/api/v1/vision/deny-stone", json={"row": 9, "col": 12})

    assert response.status_code == 200 and response.json() == {"ok": True}
    command = service._worker.send_command.call_args.args[0]
    assert command.action == CommandType.DENY_STONE
    assert command.data == {"row": 9, "col": 12}
