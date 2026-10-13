"""Performance page: Grafana is embedded only from an operator-configured origin; nothing is probed or faked."""

import json

import pytest
from fastapi.testclient import TestClient
from passlib.context import CryptContext
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from katrain.web.admin.performance import load_grafana
from katrain.web.core.models_db import Base

HOST = {"title": "主机概览", "url": "http://127.0.0.1:3000/d/host/overview?kiosk"}
GPU = {"title": "KataGo GPU", "url": "http://127.0.0.1:3000/d/gpu/katago?kiosk&refresh=10s"}


def _client(monkeypatch, tmp_path, dashboards=None):
    from katrain.web.admin.app import create_admin_app

    monkeypatch.setenv("KATRAIN_ADMIN_USERNAME", "admin:fan")
    monkeypatch.setenv("KATRAIN_ADMIN_PASSWORD_HASH", CryptContext(schemes=["bcrypt"]).hash("local-only-password"))
    monkeypatch.setenv("KATRAIN_ADMIN_SESSION_SECRET", "s" * 48)
    monkeypatch.setenv("KATRAIN_ADMIN_ENV", "test")
    if dashboards is None:
        monkeypatch.delenv("KATRAIN_ADMIN_GRAFANA_DASHBOARDS", raising=False)
    else:
        monkeypatch.setenv("KATRAIN_ADMIN_GRAFANA_DASHBOARDS", dashboards)
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    client = TestClient(create_admin_app(session_factory=sessionmaker(bind=engine), static_dir=tmp_path))
    token = client.post("/api/admin/auth/login", json={"username": "admin:fan", "password": "local-only-password"})
    return client, {"Authorization": f"Bearer {token.json()['access_token']}"}


def test_unconfigured_reports_unconfigured_and_allows_no_frames(monkeypatch, tmp_path):
    client, headers = _client(monkeypatch, tmp_path)
    assert client.get("/api/admin/performance").status_code == 401
    body = client.get("/api/admin/performance", headers=headers).json()
    assert body == {"state": "unconfigured", "error": None, "origin": None, "dashboards": [], "env": "test"}
    csp = client.get("/api/admin/health").headers["content-security-policy"]
    assert "frame-src" not in csp and "default-src 'self'" in csp


def test_configured_dashboards_are_listed_and_only_their_origin_may_be_framed(monkeypatch, tmp_path):
    client, headers = _client(monkeypatch, tmp_path, json.dumps([HOST, GPU]))
    body = client.get("/api/admin/performance", headers=headers).json()
    assert body["state"] == "configured" and body["origin"] == "http://127.0.0.1:3000"
    assert [(d["id"], d["title"], d["url"]) for d in body["dashboards"]] == [
        ("0", "主机概览", HOST["url"]),
        ("1", "KataGo GPU", GPU["url"]),
    ]
    csp = client.get("/api/admin/health").headers["content-security-policy"]
    assert csp.endswith("; frame-src http://127.0.0.1:3000")


def test_invalid_configuration_is_reported_not_embedded(monkeypatch, tmp_path):
    client, headers = _client(monkeypatch, tmp_path, "not json")
    body = client.get("/api/admin/performance", headers=headers).json()
    assert body["state"] == "invalid" and body["dashboards"] == [] and body["error"]
    assert "frame-src" not in client.get("/api/admin/health").headers["content-security-policy"]


@pytest.mark.parametrize(
    "entries, reason",
    [
        ([], "at least one"),
        ([{"title": "x", "url": "javascript:alert(1)"}], "http"),
        ([{"title": "x", "url": "http://user:pw@127.0.0.1:3000/d/a"}], "credentials"),
        ([{"title": "x", "url": "http://127.0.0.1:3000/d/a?auth_token=abc"}], "credentials"),
        ([{"title": "x", "url": "http://127.0.0.1:3000/d/a?apiKey=abc"}], "credentials"),
        ([HOST, {"title": "y", "url": "http://127.0.0.1:3001/d/b"}], "same origin"),
        ([{"title": "", "url": HOST["url"]}], "title"),
        ([{"title": "x" * 41, "url": HOST["url"]}], "title"),
        ([{"title": "x", "url": HOST["url"], "extra": 1}], "title and url"),
        ([HOST] * 13, "at most"),
    ],
)
def test_each_unsafe_or_ambiguous_entry_rejects_the_whole_configuration(entries, reason):
    result = load_grafana(json.dumps(entries))
    assert result["state"] == "invalid" and reason in result["error"] and result["dashboards"] == []
