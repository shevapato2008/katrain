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


class FakeVision:
    def __init__(self):
        self.monitor_calls = []
        self.pause_calls = []
        self.arm_calls = []
        self.expected_boards = []

    def set_monitor(self, active):
        self.monitor_calls.append(active)

    def set_paused(self, paused):
        self.pause_calls.append(paused)

    def set_move_armed(self, armed):
        self.arm_calls.append(armed)

    def set_expected_board(self, board):
        self.expected_boards.append(board)


@pytest.fixture
def client_with_vision():
    app = FastAPI()
    app.include_router(vision.router, prefix="/api/v1/vision")
    fake = FakeVision()
    app.state.vision = fake
    return TestClient(app), fake


class TestMonitorPauseArmExpectedBoard:
    def test_monitor(self, client_with_vision):
        client, fake = client_with_vision
        r = client.post("/api/v1/vision/monitor", json={"active": True})
        assert r.status_code == 200 and fake.monitor_calls == [True]

    def test_pause(self, client_with_vision):
        client, fake = client_with_vision
        r = client.post("/api/v1/vision/pause", json={"paused": True})
        assert r.status_code == 200 and fake.pause_calls == [True]

    def test_move_detection(self, client_with_vision):
        client, fake = client_with_vision
        r = client.post("/api/v1/vision/move-detection", json={"armed": True})
        assert r.status_code == 200 and fake.arm_calls == [True]

    def test_expected_board(self, client_with_vision):
        client, fake = client_with_vision
        board = [[0] * 19 for _ in range(19)]
        board[3][3] = 1
        r = client.post("/api/v1/vision/expected-board", json={"board": board})
        assert r.status_code == 200
        assert fake.expected_boards[-1][3][3] == 1
