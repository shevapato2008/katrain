"""Golden images: manifests are listed with their problems, released only when sound, links are signed."""

import hashlib
import json

import pytest

boto3 = pytest.importorskip("boto3")
moto = pytest.importorskip("moto")

from fastapi.testclient import TestClient  # noqa: E402
from passlib.context import CryptContext  # noqa: E402
from sqlalchemy import create_engine, select  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from katrain.web.admin.artifacts import ArtifactConfig  # noqa: E402
from katrain.web.core.models_db import AdminAuditLog, Base  # noqa: E402

IMAGE = b"fake golden image bytes" * 100


def manifest(**overrides):
    base = {"version": "1.4.2", "board": "rk3562", "file": "smartbox-rk3562-1.4.2.img.xz", "sha256": hashlib.sha256(IMAGE).hexdigest(), "size": len(IMAGE), "uploaded_by": "provision:fan", "uploaded_at": "2026-09-27T01:00:00Z"}
    return {**base, **overrides}


@pytest.fixture
def env(monkeypatch, tmp_path):
    from katrain.web.admin.app import create_admin_app

    monkeypatch.setenv("KATRAIN_ADMIN_USERNAME", "admin:fan")
    monkeypatch.setenv("KATRAIN_ADMIN_PASSWORD_HASH", CryptContext(schemes=["bcrypt"]).hash("local-only-password"))
    monkeypatch.setenv("KATRAIN_ADMIN_SESSION_SECRET", "s" * 48)
    monkeypatch.setenv("KATRAIN_ADMIN_ENV", "test")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "test")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "test")
    with moto.mock_aws():
        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket="golden-images")
        s3.put_object(Bucket="golden-images", Key="rk3562/1.4.2/smartbox-rk3562-1.4.2.img.xz", Body=IMAGE)
        s3.put_object(Bucket="golden-images", Key="rk3562/1.4.2/manifest.json", Body=json.dumps(manifest()))
        s3.put_object(Bucket="golden-images", Key="rk3562/1.4.3/manifest.json", Body=json.dumps(manifest(version="1.4.3")))  # file missing
        s3.put_object(Bucket="golden-images", Key="rk3576/0.9/manifest.json", Body=b"not json")
        engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(bind=engine)
        factory = sessionmaker(bind=engine)
        app = create_admin_app(session_factory=factory, static_dir=tmp_path)
        app.state.artifact_config = ArtifactConfig("https://s3.amazonaws.com", "https://s3.amazonaws.com", "golden-images", "test", "test")
        client = TestClient(app)
        token = client.post("/api/admin/auth/login", json={"username": "admin:fan", "password": "local-only-password"})
        yield client, {"Authorization": f"Bearer {token.json()['access_token']}"}, factory


def by_prefix(client, headers):
    return {i["prefix"]: i for i in client.get("/api/admin/artifacts", headers=headers).json()["images"]}


def test_every_manifest_is_listed_with_its_problems(env):
    client, headers, _ = env
    assert client.get("/api/admin/artifacts").status_code == 401
    images = by_prefix(client, headers)
    assert images["rk3562/1.4.2/"]["problems"] == [] and images["rk3562/1.4.2/"]["status"] == "candidate"
    assert images["rk3562/1.4.3/"]["problems"] == ["manifest 指向的文件不存在"]
    assert images["rk3576/0.9/"]["problems"] and images["rk3576/0.9/"]["manifest"] is None


def test_release_is_audited_and_refused_for_a_broken_image(env):
    client, headers, factory = env
    post = lambda prefix, status, note="验收通过可发": client.post("/api/admin/artifacts/status", headers=headers, json={"prefix": prefix, "status": status, "note": note})  # noqa: E731
    assert post("rk3562/1.4.3/", "released").status_code == 409
    assert post("rk3562/1.4.2/", "released", note="短").status_code == 422
    assert post("rk3562/1.4.2/", "released").status_code == 200
    assert post("rk3562/1.4.2/", "released").status_code == 409
    assert by_prefix(client, headers)["rk3562/1.4.2/"]["status"] == "released"
    assert post("nope/", "revoked").status_code == 404
    with factory() as db:
        assert [a.action for a in db.scalars(select(AdminAuditLog).where(AdminAuditLog.target_type == "golden_image"))] == ["artifact_status"]


def test_download_links_are_signed_short_lived_and_withheld_for_revoked_images(env):
    client, headers, _ = env
    link = client.post("/api/admin/artifacts/link", headers=headers, json={"prefix": "rk3562/1.4.2/"}).json()
    assert "X-Amz-Signature" in link["url"] and "X-Amz-Expires=43200" in link["url"] and link["sha256"] == hashlib.sha256(IMAGE).hexdigest()
    assert client.post("/api/admin/artifacts/link", headers=headers, json={"prefix": "rk3562/1.4.3/"}).status_code == 409
    client.post("/api/admin/artifacts/status", headers=headers, json={"prefix": "rk3562/1.4.2/", "status": "revoked", "note": "发现刷机后无法启动"})
    assert client.post("/api/admin/artifacts/link", headers=headers, json={"prefix": "rk3562/1.4.2/"}).status_code == 409


def test_unconfigured_library_says_so(env):
    client, headers, _ = env
    client.app.state.artifact_config = None
    assert client.get("/api/admin/artifacts", headers=headers).json()["state"] == "unconfigured"
