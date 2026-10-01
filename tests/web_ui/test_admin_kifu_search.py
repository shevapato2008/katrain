"""The capture page searches the environment's kifu library through an admin-only read."""

from fastapi.testclient import TestClient
from passlib.context import CryptContext
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from katrain.web.core.models_db import Base, KifuAlbum


def _album(index, black, white, event, date, sgf="(;SZ[19];B[pd];W[dp])", size=19):
    return KifuAlbum(
        player_black=black,
        player_white=white,
        event=event,
        date_played=date,
        date_sort=date,
        result="B+R",
        board_size=size,
        move_count=2,
        handicap=0,
        sgf_content=sgf,
        source_path=f"test/{index}.sgf",
        search_text=f"{black} {white} {event} {date}".lower(),
    )


def _client(monkeypatch, tmp_path):
    from katrain.web.admin.app import create_admin_app

    monkeypatch.setenv("KATRAIN_ADMIN_USERNAME", "admin:fan")
    monkeypatch.setenv("KATRAIN_ADMIN_PASSWORD_HASH", CryptContext(schemes=["bcrypt"]).hash("local-only-password"))
    monkeypatch.setenv("KATRAIN_ADMIN_SESSION_SECRET", "s" * 48)
    monkeypatch.setenv("KATRAIN_ADMIN_ENV", "test")
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(bind=engine)
    with factory() as db:
        db.add_all(
            [
                _album(1, "柯洁", "申真谞", "应氏杯决赛", "2025-11-02"),
                _album(2, "申真谞", "柯洁", "应氏杯决赛", "2025-11-04"),
                _album(3, "芈昱廷", "唐韦星", "围甲联赛", "2024-06-01"),
                _album(4, "小棋盘", "对手", "九路赛", "2024-01-01", sgf="(;SZ[9];B[ee])", size=9),
            ]
        )
        db.commit()
    client = TestClient(create_admin_app(session_factory=factory, static_dir=tmp_path))
    token = client.post("/api/admin/auth/login", json={"username": "admin:fan", "password": "local-only-password"})
    return client, {"Authorization": f"Bearer {token.json()['access_token']}"}


def test_kifu_search_requires_admin_and_filters_to_19x19(monkeypatch, tmp_path):
    client, headers = _client(monkeypatch, tmp_path)
    assert client.get("/api/admin/kifu/albums?q=柯洁").status_code == 401

    found = client.get("/api/admin/kifu/albums?q=柯洁", headers=headers)
    assert found.status_code == 200
    body = found.json()
    assert body["total"] == 2
    assert [item["date_played"] for item in body["items"]] == ["2025-11-04", "2025-11-02"]
    assert "sgf_content" not in body["items"][0]

    everything = client.get("/api/admin/kifu/albums", headers=headers).json()
    assert everything["total"] == 3
    assert all(item["board_size"] == 19 for item in everything["items"])


def test_kifu_detail_returns_sgf_for_capture_import(monkeypatch, tmp_path):
    client, headers = _client(monkeypatch, tmp_path)
    album = client.get("/api/admin/kifu/albums?q=围甲", headers=headers).json()["items"][0]
    assert client.get(f"/api/admin/kifu/albums/{album['id']}").status_code == 401
    detail = client.get(f"/api/admin/kifu/albums/{album['id']}", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["sgf_content"] == "(;SZ[19];B[pd];W[dp])"
    assert client.get("/api/admin/kifu/albums/99999", headers=headers).status_code == 404


def test_kifu_search_bounds_paging(monkeypatch, tmp_path):
    client, headers = _client(monkeypatch, tmp_path)
    assert client.get("/api/admin/kifu/albums?page_size=101", headers=headers).status_code == 422
    assert client.get("/api/admin/kifu/albums?q=" + "x" * 101, headers=headers).status_code == 422
