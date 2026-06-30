"""K3: catalog GETs get Cache-Control + weak ETag; If-None-Match → 304; /assets untouched."""
import pytest
from fastapi import FastAPI, Response
from httpx import ASGITransport, AsyncClient

from katrain.web.core.catalog_cache import CATALOG_CACHE_CONTROL, add_catalog_cache_middleware


def _stub_app() -> FastAPI:
    app = FastAPI()

    @app.get("/api/v1/tutorials/categories")
    async def categories():
        return [{"category": "joseki"}]

    @app.get("/api/v1/tutorials/assets/{p:path}")
    async def asset(p: str):
        return Response(content=b"\x00\x01", media_type="video/mp4")

    add_catalog_cache_middleware(app)
    return app


async def _get(app, path, headers=None):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        return await ac.get(path, headers=headers or {})


@pytest.mark.asyncio
async def test_catalog_gets_cache_control_and_weak_etag():
    resp = await _get(_stub_app(), "/api/v1/tutorials/categories")
    assert resp.status_code == 200
    assert resp.headers["cache-control"] == CATALOG_CACHE_CONTROL
    assert resp.headers["etag"].startswith('W/"')
    assert resp.json() == [{"category": "joseki"}]


@pytest.mark.asyncio
async def test_if_none_match_returns_304():
    app = _stub_app()
    etag = (await _get(app, "/api/v1/tutorials/categories")).headers["etag"]
    again = await _get(app, "/api/v1/tutorials/categories", headers={"If-None-Match": etag})
    assert again.status_code == 304
    assert again.headers["etag"] == etag
    assert again.content == b""


@pytest.mark.asyncio
async def test_assets_path_not_touched():
    resp = await _get(_stub_app(), "/api/v1/tutorials/assets/x/y.mp4")
    assert "etag" not in {k.lower() for k in resp.headers}
