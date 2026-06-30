"""K1: RemoteAPIClient tutorial read-only methods forward to the right paths, auth=False."""
from unittest.mock import AsyncMock, MagicMock
from urllib.parse import quote

import pytest

from katrain.web.core.remote_client import RemoteAPIClient


def _client_with_capture():
    c = RemoteAPIClient(base_url="http://up", device_id="test-dev")
    captured = {}

    async def fake_request(method, path, *, json=None, params=None, auth=True):
        captured.update(method=method, path=path, auth=auth)
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        resp.json = MagicMock(return_value={"ok": True})
        return resp

    c._request = AsyncMock(side_effect=fake_request)
    return c, captured


@pytest.mark.asyncio
async def test_categories_path_and_public():
    c, cap = _client_with_capture()
    assert await c.get_tutorial_categories() == {"ok": True}
    assert (cap["method"], cap["path"], cap["auth"]) == ("GET", "/api/v1/tutorials/categories", False)


@pytest.mark.asyncio
async def test_books_url_encodes_category():
    c, cap = _client_with_capture()
    await c.get_tutorial_books("围棋 入门")
    assert cap["path"] == f"/api/v1/tutorials/categories/{quote('围棋 入门')}/books"
    assert cap["auth"] is False


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "call, expected_path",
    [
        (lambda c: c.get_tutorial_book(7), "/api/v1/tutorials/books/7"),
        (lambda c: c.get_tutorial_chapters(7), "/api/v1/tutorials/books/7/chapters"),
        (lambda c: c.get_tutorial_sections(12), "/api/v1/tutorials/chapters/12/sections"),
        (lambda c: c.get_tutorial_section(34), "/api/v1/tutorials/sections/34"),
        (lambda c: c.get_tutorial_figure(56), "/api/v1/tutorials/figures/56"),
    ],
)
async def test_id_based_paths(call, expected_path):
    c, cap = _client_with_capture()
    await call(c)
    assert cap["path"] == expected_path
    assert cap["auth"] is False
