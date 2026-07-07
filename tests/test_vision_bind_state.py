"""Bind a session to vision and assert the expected board is seeded from katrain state."""

import pytest

pytest.importorskip("fastapi")
from fastapi import FastAPI
from fastapi.testclient import TestClient

from katrain.web.api.v1.endpoints import vision


class FakeVision:
    def __init__(self):
        self.bound = None
        self.expected_stones = None

    def bind_session(self, sid):
        self.bound = sid

    def unbind_session(self):
        self.bound = None

    def set_expected_from_stones(self, stones, board_size=19):
        self.expected_stones = stones


class FakeKatrain:
    def get_state(self):
        return {"stones": [["B", [3, 15], None, 1]], "board_size": [19, 19]}


class FakeSession:
    def __init__(self):
        self.katrain = FakeKatrain()


class FakeManager:
    def get_session(self, sid):
        return FakeSession()


def _client(vision_obj, manager):
    app = FastAPI()
    app.include_router(vision.router, prefix="/vision")
    app.state.vision = vision_obj
    app.state.session_manager = manager
    return TestClient(app, raise_server_exceptions=False)


class TestVisionBind:
    def test_bind_seeds_expected_board_from_katrain_state(self):
        fake = FakeVision()
        c = _client(fake, FakeManager())
        r = c.post("/vision/bind", json={"session_id": "s1"})
        assert r.status_code == 200
        assert fake.bound == "s1"
        assert fake.expected_stones == [["B", [3, 15], None, 1]]


class FakeOrchestrator:
    def __init__(self):
        self.bound = None
        self.unbound = False

    def on_bind(self, session_id, session):
        self.bound = session_id

    def on_unbind(self):
        self.unbound = True


class TestOrchestratorHooks:
    def test_bind_and_unbind_notify_orchestrator(self):
        fake_vision, orch = FakeVision(), FakeOrchestrator()
        c = _client(fake_vision, FakeManager())
        c.app.state.physical_play = orch
        assert c.post("/vision/bind", json={"session_id": "s1"}).status_code == 200
        assert orch.bound == "s1"
        assert c.post("/vision/unbind").status_code == 200
        assert orch.unbound is True


class FakeLed:
    def is_connected(self):
        return True


class TestStatusLed:
    def test_status_reports_led_connected(self):
        c = _client(FakeVision(), FakeManager())
        c.app.state.led = FakeLed()
        # FakeVision 缺 status 属性时按 vision=None 分支断言：
        c.app.state.vision = None
        r = c.get("/vision/status")
        assert r.status_code == 200
        assert r.json()["led_connected"] is True
