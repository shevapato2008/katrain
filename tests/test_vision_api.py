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
        "led_connected": False,
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
class _FakeOrch:
    def __init__(self):
        self.resynced = 0

    def resync(self):
        self.resynced += 1


class _FakeVision:
    def __init__(self):
        self.reset_calls = 0

    def reset_sync(self, expected=None):
        self.reset_calls += 1


def _reset_app(with_orch: bool):
    app = FastAPI()
    app.include_router(vision.router, prefix="/vision")
    app.state.vision = _FakeVision()
    if with_orch:
        app.state.physical_play = _FakeOrch()
    return app


def test_sync_reset_drives_orchestrator_resync_when_present():
    app = _reset_app(with_orch=True)
    response = TestClient(app).post("/vision/sync/reset")  # no body -> adopt defaults to "digital"
    assert response.status_code == 200 and response.json() == {"ok": True}
    assert app.state.physical_play.resynced == 1
    # orchestrator owns the reset sequence; the endpoint must not double-drive vision directly
    assert app.state.vision.reset_calls == 0


def test_sync_reset_physical_adopt_bypasses_orchestrator():
    # Ambiguous-stone 忽略 wants physical-adopt: keep the camera board as baseline, NOT the
    # trust-digital resync (which would re-push the digital board and re-detect the stone).
    app = _reset_app(with_orch=True)
    response = TestClient(app).post("/vision/sync/reset", json={"adopt": "physical"})
    assert response.status_code == 200
    assert app.state.physical_play.resynced == 0  # orchestrator bypassed
    assert app.state.vision.reset_calls == 1  # plain physical-adopt reset instead


def test_sync_reset_falls_back_to_vision_without_orchestrator():
    app = _reset_app(with_orch=False)
    response = TestClient(app).post("/vision/sync/reset")
    assert response.status_code == 200
    assert app.state.vision.reset_calls == 1
