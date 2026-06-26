"""Endpoint tests for GET /api/v1/tutorials/assets/{path} across backends.

Task 3 of superpowers/tracks/tutorial-database/plan.md. Verifies local Range
serving is unchanged and remote backends 302-redirect to the public URL.

Uses the httpx AsyncClient + ASGITransport pattern (matches tests/web_ui/*),
since starlette's sync TestClient is incompatible with the pinned httpx.
"""
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from katrain.web.core.storage.base import normalize_key
from katrain.web.core.storage.local import LocalStorageBackend

KEY = "tutorial_assets/book/video/fig_1.mp4"
PAYLOAD = bytes(range(256))  # 256 bytes


def _make_app(backend, monkeypatch):
    from katrain.web.core import storage as storage_mod
    from katrain.web.api.v1.endpoints import tutorials

    monkeypatch.setattr(storage_mod, "_backend", backend)
    backend.put(KEY, PAYLOAD)
    app = FastAPI()
    app.include_router(tutorials.router, prefix="/api/v1/tutorials")
    return app


class _RemoteBackend(LocalStorageBackend):
    """Local on disk but advertises is_remote=True with a CDN-style public URL."""

    is_remote = True

    def public_url(self, key):
        return f"https://cdn.example.com/{normalize_key(key)}"


@pytest.fixture
def app_local(tmp_path, monkeypatch):
    return _make_app(LocalStorageBackend(base_dir=tmp_path), monkeypatch)


@pytest.fixture
def app_remote(tmp_path, monkeypatch):
    return _make_app(_RemoteBackend(base_dir=tmp_path), monkeypatch)


async def _get(app, path, **kw):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        return await ac.get(f"/api/v1/tutorials/assets/{path}", **kw)


# ── local backend ──────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_local_full_get_200(app_local):
    r = await _get(app_local, KEY)
    assert r.status_code == 200
    assert r.headers["accept-ranges"] == "bytes"
    assert "max-age" in r.headers.get("cache-control", "")
    assert len(r.content) == 256


@pytest.mark.asyncio
async def test_local_range_206(app_local):
    r = await _get(app_local, KEY, headers={"Range": "bytes=10-19"})
    assert r.status_code == 206
    assert r.headers["content-range"] == "bytes 10-19/256"
    assert r.content == PAYLOAD[10:20]


@pytest.mark.asyncio
async def test_local_missing_404(app_local):
    r = await _get(app_local, "tutorial_assets/book/video/nope.mp4")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_local_traversal_rejected(app_local):
    r = await _get(app_local, "..%2f..%2fetc%2fpasswd")
    assert r.status_code in (400, 404)


# ── remote backend ─────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_remote_redirects_302(app_remote):
    r = await _get(app_remote, KEY, follow_redirects=False)
    assert r.status_code == 302
    assert r.headers["location"] == f"https://cdn.example.com/{KEY}"


@pytest.mark.asyncio
async def test_remote_missing_404(app_remote):
    r = await _get(app_remote, "tutorial_assets/book/video/nope.mp4", follow_redirects=False)
    assert r.status_code == 404
