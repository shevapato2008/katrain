from fastapi import FastAPI
from fastapi.testclient import TestClient

from katrain.web.api.v1.endpoints.vision import router


def test_vision_status_returns_disabled_status_when_service_is_not_enabled():
    app = FastAPI()
    app.include_router(router, prefix="/api/v1/vision")
    client = TestClient(app)

    response = client.get("/api/v1/vision/status")

    assert response.status_code == 200
    assert response.json() == {
        "enabled": False,
        "camera_connected": False,
        "pose_locked": False,
        "sync_state": "idle",
        "bound_session_id": None,
    }
