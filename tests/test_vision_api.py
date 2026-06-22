"""HTTP-layer tests for optional vision-service behavior."""

import pytest

pytest.importorskip("fastapi")
from fastapi import FastAPI
from fastapi.testclient import TestClient

from katrain.web.api.v1.endpoints import vision


def test_status_reports_disabled_when_vision_service_is_not_configured():
    app = FastAPI()
    app.include_router(vision.router, prefix="/vision")

    response = TestClient(app).get("/vision/status")

    assert response.status_code == 200
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
    }
