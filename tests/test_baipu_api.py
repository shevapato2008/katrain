"""HTTP-layer tests for the 摆谱 endpoints.

Runs in the web env (fastapi installed), e.g.:
    CI=true /opt/miniconda3/envs/py311_katago/bin/python -m pytest tests/test_baipu_api.py

Uses an isolated FastAPI app mounting only the baipu router, so no DB/config is
required. The /baipu/capture tests are added in P4.
"""

from pathlib import Path

import numpy as np
import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi import FastAPI
from fastapi.testclient import TestClient

from katrain.web.api.v1.endpoints import baipu
from katrain.vision.geometry_lock import GeometryLock


@pytest.fixture(scope="module")
def client():
    app = FastAPI()
    app.include_router(baipu.router, prefix="/baipu")
    return TestClient(app)


class TestBaipuLoad:
    def test_load_returns_canonical_steps(self, client):
        resp = client.post("/baipu/load", json={"sgf": "(;SZ[19];B[pd];W[dp])"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["board_size"] == 19
        assert len(body["steps"]) == 2
        s0 = body["steps"][0]
        assert s0["kind"] == "move" and s0["color"] == "B"
        assert (s0["row"], s0["col"]) == (3, 15)  # Q16, upper-right
        assert s0["removed"] == []
        assert s0["board_hash"]

    def test_load_capture_removed_coerced(self, client):
        resp = client.post("/baipu/load", json={"sgf": "(;SZ[19];W[aa];B[ba];B[ab])"})
        assert resp.status_code == 200
        last = resp.json()["steps"][-1]
        assert last["removed"] == [{"row": 0, "col": 0}]

    def test_missing_input_is_400(self, client):
        resp = client.post("/baipu/load", json={})
        assert resp.status_code == 400

    def test_bad_sgf_is_422(self, client):
        resp = client.post("/baipu/load", json={"sgf": "this is not sgf at all"})
        assert resp.status_code == 422


class _FakeLed:
    def clear(self, *, strict=False):
        return {"ok": True, "connected": True, "shown_at": None, "errors": []}

    def set_points(self, points, *, strict=False):
        return {"ok": True, "connected": True, "shown_at": 1.0, "errors": []}


class _FakeCapture:
    def __init__(self, out_dir):
        self.out_dir = Path(out_dir)

    def grab_fresh(self, after_ts=None, settle_ms=150.0):
        return np.zeros((4, 4, 3), np.uint8), 1, 2.0

    def capture_to(self, path, after_ts=None, settle_ms=150.0):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_bytes(b"jpg")
        return path, 7, 3.0


def _geo():
    return GeometryLock(
        corners=np.zeros((4, 2), np.float32),
        points=np.zeros((19, 19, 2), np.float32),
        xs=np.linspace(0, 949, 19).astype(np.float32),
        ys=np.linspace(0, 949, 19).astype(np.float32),
        M=np.eye(3),
        Minv=np.eye(3),
        out_size=950,
        baseline=np.zeros((19, 19, 3), np.float32),
    )


class TestBaipuCaptureEndpoint:
    def _client(self, tmp_path, capture=True, geometry=True, led=True):
        app = FastAPI()
        app.include_router(baipu.router, prefix="/baipu")
        if capture:
            app.state.capture = _FakeCapture(tmp_path)
        if geometry:
            app.state.geometry = _geo()
        if led:
            app.state.led = _FakeLed()
        return TestClient(app)

    def test_404_without_capture(self, tmp_path):
        c = self._client(tmp_path, capture=False)
        r = c.post("/baipu/capture", json={"game_id": "g", "move_index": -1, "sgf": "(;SZ[19];B[pd])"})
        assert r.status_code == 404

    def test_409_without_geometry(self, tmp_path):
        c = self._client(tmp_path, geometry=False)
        r = c.post("/baipu/capture", json={"game_id": "g", "move_index": -1, "sgf": "(;SZ[19];B[pd])"})
        assert r.status_code == 409

    def test_happy_initial_frame(self, tmp_path, monkeypatch):
        monkeypatch.setattr("katrain.vision.board_qa.classify_canonical", lambda f, g: [[None] * 19 for _ in range(19)])
        c = self._client(tmp_path)
        r = c.post("/baipu/capture", json={"game_id": "g", "move_index": -1, "sgf": "(;SZ[19];B[pd];W[dp])"})
        assert r.status_code == 200
        assert r.json()["frame_kind"] == "initial_led"

    def test_move_index_out_of_range_returns_400(self, tmp_path, monkeypatch):
        monkeypatch.setattr("katrain.vision.board_qa.classify_canonical", lambda f, g: [[None] * 19 for _ in range(19)])
        c = self._client(tmp_path)
        # SGF has 2 steps (indices 0,1); move_index 99 is out of range → 400, not 500.
        r = c.post("/baipu/capture", json={"game_id": "g", "move_index": 99, "sgf": "(;SZ[19];B[pd];W[dp])"})
        assert r.status_code == 400

    def test_qa_mismatch_returns_409_with_diffs(self, tmp_path, monkeypatch):
        # physical board reads empty, but move_index 0 claims a stone is placed
        monkeypatch.setattr("katrain.vision.board_qa.classify_canonical", lambda f, g: [[None] * 19 for _ in range(19)])
        c = self._client(tmp_path)
        r = c.post("/baipu/capture", json={"game_id": "g", "move_index": 0, "sgf": "(;SZ[19];B[pd];W[dp])"})
        assert r.status_code == 409
        assert r.json()["detail"]["qa"] == "mismatch"
        assert r.json()["detail"]["diffs"]
