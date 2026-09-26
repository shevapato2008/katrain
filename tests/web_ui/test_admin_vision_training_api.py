"""Dedicated-auth training API; no real worker is launched."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from jose import jwt

SECRET = "training-admin-test-secret-" * 3
PREFIX = "/api/admin/vision-training"


@pytest.fixture
def client(monkeypatch, tmp_path):
    from katrain.web.admin.app import create_admin_app

    monkeypatch.setenv("KATRAIN_MODE", "server")
    monkeypatch.setenv("KATRAIN_ADMIN_USERNAME", "admin:fan")
    monkeypatch.setenv("KATRAIN_ADMIN_PASSWORD_HASH", "$2b$12$" + "a" * 53)
    monkeypatch.setenv("KATRAIN_ADMIN_SESSION_SECRET", SECRET)
    monkeypatch.setenv("KATRAIN_ADMIN_ENV", "test")
    monkeypatch.delenv("KATRAIN_ADMIN_VISION_TRAINING", raising=False)
    return TestClient(create_admin_app(session_factory=object(), static_dir=tmp_path, bind_host="127.0.0.1"))


def auth(**changes):
    claims = {
        "sub": "admin:fan",
        "aud": "katrain-admin",
        "type": "admin_session",
        "env": "test",
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
    }
    claims.update(changes)
    return {"Authorization": "Bearer " + jwt.encode(claims, SECRET, algorithm="HS256")}


def request_body():
    return {
        "request_id": str(uuid4()),
        "dataset_id": "dataset-" + "a" * 64,
        "dataset_manifest_sha256": "b" * 64,
        "weights_id": "yolo11m",
        "augmentation": "stones-standard",
        "gpu_id": "0",
        "epochs": 2,
        "batch": 4,
        "imgsz": 640,
        "seed": 0,
        "confirmed": True,
    }


@pytest.mark.parametrize(
    "method,path,body",
    [
        ("GET", "/status", None),
        ("GET", "/datasets", None),
        ("GET", "/presets", None),
        ("GET", "/runs", None),
        ("GET", "/models", None),
        ("GET", "/runs/" + str(uuid4()), None),
        ("POST", "/runs", request_body()),
        ("POST", "/runs/" + str(uuid4()) + "/cancel", {"confirmed": True}),
    ],
)
def test_every_training_route_requires_own_admin_session(client, method, path, body):
    for headers in ({}, auth(type="access"), auth(env="local")):
        assert client.request(method, PREFIX + path, json=body, headers=headers).status_code == 401


def test_default_disabled_status_is_honest_and_never_implicitly_launches(client):
    status = client.get(PREFIX + "/status", headers=auth())
    assert status.status_code == 200
    assert status.json()["enabled"] is False and status.json()["gpu_ids"] == []
    for method, path, body in [
        ("GET", "/datasets", None),
        ("GET", "/runs", None),
        ("GET", "/models", None),
        ("POST", "/runs", request_body()),
    ]:
        response = client.request(method, PREFIX + path, json=body, headers=auth())
        assert response.status_code == 403
        assert response.headers["Cache-Control"] == "no-store"


@pytest.mark.parametrize(
    "change",
    [{"batch": True}, {"batch": 4.0}, {"epochs": "2"}, {"confirmed": "yes"}, {"shell": "anything"}, {"gpu_id": "0,1"}],
)
def test_api_rejects_unsafe_or_implicit_parameters(client, change):
    body = request_body() | change
    assert client.post(PREFIX + "/runs", json=body, headers=auth()).status_code == 422


def test_real_api_passes_explicit_confirmation_and_redacts_server_paths(client):
    body = request_body()

    class Coordinator:
        def start(self, request, *, confirmed):
            assert confirmed is True and "confirmed" not in request
            assert request["request_id"] == body["request_id"]
            return {
                "id": str(uuid4()),
                "state": "running",
                "spec": {
                    "dataset_id": request["dataset_id"],
                    "dataset_manifest_sha256": "b" * 64,
                    "weights_path": "/private/secret.pt",
                    "weights_id": "yolo11m",
                    "mode": "stones2",
                    "class_names": ["black", "white"],
                    "augmentation": "stones-standard",
                    "parameters": {
                        "project": "/private/runs/abc",
                        "epochs": 2,
                        "batch": 4,
                        "imgsz": 640,
                        "seed": 0,
                        "device": "0",
                    },
                },
                "epoch": 0,
                "total_epochs": 2,
                "metrics": {"map50": None, "precision": None, "recall": None},
                "log_tail": "",
                "error": None,
            }

    client.app.state.vision_training = Coordinator()
    response = client.post(PREFIX + "/runs", json=body, headers=auth())
    assert response.status_code == 200
    assert "/private/" not in response.text and '"spec"' not in response.text
    assert response.json()["parameters"]["batch"] == 4
