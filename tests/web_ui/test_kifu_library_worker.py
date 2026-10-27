"""The local list owns its Session in a worker and leaves async routing responsive."""

import asyncio
from threading import Event, get_ident

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from katrain.web.api.v1.endpoints import kifu
from tests.web_ui.test_kifu_offline import _dispatcher


def _app(factory):
    app = FastAPI()
    app.include_router(kifu.router, prefix="/kifu")
    app.dependency_overrides[kifu.get_kifu_session_factory] = lambda: factory

    @app.get("/ping")
    async def ping():
        return {"ok": True}

    return app


@pytest.mark.asyncio
async def test_each_local_request_constructs_queries_and_closes_its_session_in_one_worker(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'owned.db'}")
    seen = []
    opened = []

    class OwnedSession(Session):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            opened.append(self)
            seen.append(("open", id(self), get_ident()))

        def close(self):
            seen.append(("close", id(self), get_ident()))
            super().close()

    def read(db, **params):
        seen.append(("query", id(db), get_ident()))
        assert db.execute(text("SELECT 1")).scalar_one() == 1
        return kifu.KifuAlbumListResponse(items=[], total=0, page=params["page"], page_size=params["page_size"])

    monkeypatch.setattr(kifu, "read_album_page", read)
    factory = sessionmaker(bind=engine, class_=OwnedSession)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=_app(factory)), base_url="http://test") as client:
        first = await client.get("/kifu/albums")
        second = await client.get("/kifu/albums")
    assert first.status_code == second.status_code == 200
    assert len(opened) == 2 and opened[0] is not opened[1]
    assert [entry[0] for entry in seen] == ["open", "query", "close"] * 2
    for offset in (0, 3):
        assert len({entry[1] for entry in seen[offset : offset + 3]}) == 1
        assert len({entry[2] for entry in seen[offset : offset + 3]}) == 1
        assert seen[offset][2] != get_ident()
    assert "kifu_worker;dur=" in first.headers["server-timing"]
    assert "kifu_queue;dur=" in first.headers["server-timing"]
    engine.dispose()


@pytest.mark.asyncio
async def test_blocked_local_read_does_not_block_an_unrelated_async_route(monkeypatch):
    started, release = Event(), Event()

    def read(db, **params):
        started.set()
        assert release.wait(5), "test did not release local reader"
        return kifu.KifuAlbumListResponse(items=[], total=0, page=1, page_size=20)

    monkeypatch.setattr(kifu, "read_album_page", read)
    engine = create_engine("sqlite:///:memory:")
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=_app(sessionmaker(bind=engine))), base_url="http://test"
    ) as client:
        listing = asyncio.create_task(client.get("/kifu/albums"))
        try:
            assert await asyncio.to_thread(started.wait, 2)
            ping = await asyncio.wait_for(client.get("/ping"), timeout=1)
            assert ping.json() == {"ok": True}
        finally:
            release.set()
            response = await listing
        assert response.status_code == 200
    engine.dispose()


@pytest.mark.asyncio
async def test_player_id_validation_and_async_remote_forwarding():
    from unittest.mock import AsyncMock

    search = AsyncMock(return_value={"items": [], "total": 0, "page": 2, "page_size": 20})
    app = _app(None)
    app.state.repository_dispatcher = _dispatcher(search=search)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        assert (await client.get("/kifu/albums?player_id=0")).status_code == 422
        assert (await client.get("/kifu/albums?player_id=7&q=abc")).status_code == 422
        result = await client.get("/kifu/albums?player_id=7&page=2&lang=jp")
    assert result.status_code == 200
    search.assert_awaited_once_with(player_id=7, page=2, page_size=20, lang="jp")
