"""HTTP-layer tests for the 摆谱 endpoints.

Runs in the web env (fastapi installed), e.g.:
    CI=true /opt/miniconda3/envs/py311_katago/bin/python -m pytest tests/test_baipu_api.py

Uses an isolated FastAPI app mounting only the baipu router, so no DB/config is
required. The /baipu/capture tests are added in P4.
"""

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi import FastAPI
from fastapi.testclient import TestClient

from katrain.web.api.v1.endpoints import baipu


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
