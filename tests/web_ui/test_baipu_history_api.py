"""HTTP ownership, validation and browser preconditions against isolated SQLite."""

import importlib.util

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from katrain.web.core import models_db
from katrain.web.core.auth import SQLAlchemyUserRepository, create_access_token
from katrain.web.core.config import settings

SGF = "(;SZ[19];B[aa];W[bb])"


def test_history_router_exists():
    assert importlib.util.find_spec("katrain.web.api.v1.endpoints.baipu_history") is not None


@pytest.fixture
def api(tmp_path, monkeypatch):
    from katrain.web.api.v1.endpoints.baipu_history import router
    from katrain.web.core.baipu_history import BaipuHistoryRepository
    from katrain.web.core.baipu_history_sync import BaipuHistoryService

    monkeypatch.setattr(settings, "KATRAIN_BOX_SSO", False)
    monkeypatch.setattr(settings, "KATRAIN_MODE", "server")
    engine = create_engine(f"sqlite:///{tmp_path / 'api.db'}", connect_args={"check_same_thread": False})
    models_db.Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    with factory.begin() as db:
        db.add_all(
            [
                models_db.User(id=i, uuid=f"uuid-{name}", username=name, hashed_password="x")
                for i, name in [(1, "alice"), (2, "bob"), (3, "guest")]
            ]
        )
    app = FastAPI()
    app.include_router(router, prefix="/baipu/history")
    app.state.user_repo = SQLAlchemyUserRepository(factory)
    app.state.baipu_history_service = BaipuHistoryService(BaipuHistoryRepository(factory))
    with TestClient(app) as client:
        yield client
    engine.dispose()


def auth(name="alice"):
    return {"Authorization": f'Bearer {create_access_token(data={"sub": name})}'}


def test_auth_guest_owner_and_public_shapes(api):
    assert api.get("/baipu/history").status_code == 401
    assert api.get("/baipu/history", headers=auth("guest")).status_code == 403
    assert api.post("/baipu/history/open", headers=auth("guest"), json={"sgf_content": SGF}).status_code == 403
    created = api.post(
        "/baipu/history/open", headers=auth(), json={"sgf_content": SGF, "source_id": "kifu_1", "name": "Game"}
    )
    assert created.status_code == 200, created.text
    row = created.json()
    assert row["k"] == 0 and row["total"] == 2 and row["authority"] == "this_node"
    assert "writer_id" not in row and "user_id" not in row
    response = api.get("/baipu/history", headers=auth()).json()
    assert response["authority"] == "this_node" and response["items"][0]["id"] == row["id"]
    assert "sgf_content" not in response["items"][0]
    assert api.get(f"/baipu/history/{row['id']}", headers=auth("bob")).status_code == 404
    assert (
        api.put(
            f"/baipu/history/{row['id']}",
            headers=auth("bob"),
            json={"k": 1, "expected_local_revision": 0, "mutation_id": "x"},
        ).status_code
        == 404
    )


def test_browser_identity_precondition_cas_and_extra_fields(api):
    stale = dict(auth(), **{"X-Katrain-Expected-Identity": "uuid-bob"})
    rejected = api.post("/baipu/history/open", headers=stale, json={"sgf_content": SGF})
    assert rejected.status_code == 409 and rejected.json()["detail"]["code"] == "identity_changed"
    assert api.get("/baipu/history", headers=auth()).json()["items"] == []
    row = api.post(
        "/baipu/history/open",
        headers=dict(auth(), **{"X-Katrain-Expected-Identity": "uuid-alice"}),
        json={"sgf_content": SGF},
    ).json()
    url = f"/baipu/history/{row['id']}"
    assert (
        api.put(
            url, headers=auth(), json={"k": 1, "expected_local_revision": 0, "mutation_id": "m", "user_id": 2}
        ).status_code
        == 422
    )
    saved = api.put(url, headers=auth(), json={"k": 2, "expected_local_revision": 0, "mutation_id": "m"})
    assert saved.status_code == 200 and saved.json()["completed"]
    stale_save = api.put(url, headers=auth(), json={"k": 0, "expected_local_revision": 0, "mutation_id": "n"})
    assert stale_save.status_code == 409 and stale_save.json()["detail"]["code"] == "stale_local_revision"
    assert "user_id" not in stale_save.json()["detail"]["current"]
    assert (
        api.put(url, headers=auth(), json={"k": 3, "expected_local_revision": 1, "mutation_id": "too-far"}).status_code
        == 422
    )
    assert api.get("/baipu/history?limit=101", headers=auth()).status_code == 422
    assert api.get("/baipu/history/../bad", headers=auth()).status_code in (404, 422)


def test_sync_receipts_are_owner_scoped_and_browser_save_invalidates_old_branch(api):
    from katrain.core.baipu_identity import baipu_record_identity, sgf_sha256

    record_id = baipu_record_identity(SGF)
    url = f"/baipu/history/{record_id}"
    payload = dict(
        sgf_content=SGF,
        source_id="kifu_1",
        name="Game",
        sgf_sha256=sgf_sha256(SGF),
        replay_version=2,
        total=2,
        k=1,
        writer_id="board-a",
        writer_seq=1,
        expected_revision=0,
    )
    accepted = api.put(url + "/sync", headers=auth(), json=payload)
    assert accepted.status_code == 200, accepted.text
    row = accepted.json()
    assert row["last_writer_id"] == "board-a" and row["last_writer_seq"] == 1
    assert row["cloud_revision"] == row["local_revision"] == 1
    assert "user_id" not in row and "last_mutation_payload" not in row
    assert api.put(url + "/sync", headers=auth(), json=payload).json()["cloud_revision"] == 1
    browser = api.put(url, headers=auth(), json={"k": 0, "expected_local_revision": 1, "mutation_id": "restart"})
    assert browser.status_code == 200 and browser.json()["cloud_revision"] == 2
    conflict = api.put(url + "/sync", headers=auth(), json=dict(payload, writer_seq=2))
    assert conflict.status_code == 409
    assert conflict.json()["detail"]["code"] == "cloud_progress_conflict"
    current = conflict.json()["detail"]["current"]
    assert current["sgf_content"] == SGF and current["k"] == 0
    assert "user_id" not in current and "last_mutation_payload" not in current
