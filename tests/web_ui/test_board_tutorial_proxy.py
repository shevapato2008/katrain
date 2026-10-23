"""K2: board-mode tutorial proxy forwards reads to RemoteAPIClient; assets → 302; errors map."""
import os
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from httpx import ASGITransport, AsyncClient

from katrain.web.server import create_app
from katrain.web.core.remote_client import RemoteAPIClient


def _http_status_error(code: int, text: str = "") -> httpx.HTTPStatusError:
    resp = MagicMock()
    resp.status_code = code
    resp.text = text
    return httpx.HTTPStatusError(f"{code}", request=MagicMock(), response=resp)


@pytest.fixture
def board_app():
    db_path = "test_board_tutorial_proxy.db"
    os.environ["KATRAIN_DATABASE_PATH"] = db_path
    if os.path.exists(db_path):
        os.remove(db_path)
    app = create_app(enable_engine=False)
    client = MagicMock()
    client.base_url = "http://up"
    client.get_tutorial_categories = AsyncMock(return_value=[{"category": "joseki", "book_count": 3}])
    client.get_tutorial_books = AsyncMock(return_value=[{"id": 1}])
    client.get_tutorial_book = AsyncMock(return_value={"id": 1, "chapters": []})
    client.get_tutorial_chapters = AsyncMock(return_value=[{"id": 9}])
    client.get_tutorial_sections = AsyncMock(return_value=[{"id": 5}])
    client.get_tutorial_section = AsyncMock(return_value={"id": 5, "figures": []})
    client.get_tutorial_figure = AsyncMock(return_value={"id": 7})
    client.get_ogs_course = AsyncMock(return_value={"chapters": [{"id": "basics"}]})
    client.get_ogs_step = AsyncMock(return_value={"page": 2, "source_id": "ogs-learning:basics:2"})
    app.state.remote_client = client
    yield app
    if os.path.exists(db_path):
        os.remove(db_path)


async def _get(app, path):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        return await ac.get(path, follow_redirects=False)


@pytest.mark.asyncio
async def test_all_json_proxies_reachable(board_app):
    assert (await _get(board_app, "/api/v1/board/tutorials/categories")).json()[0]["book_count"] == 3
    assert (await _get(board_app, "/api/v1/board/tutorials/categories/joseki/books")).status_code == 200
    assert (await _get(board_app, "/api/v1/board/tutorials/books/1")).status_code == 200
    assert (await _get(board_app, "/api/v1/board/tutorials/books/1/chapters")).json()[0]["id"] == 9
    assert (await _get(board_app, "/api/v1/board/tutorials/chapters/9/sections")).status_code == 200
    assert (await _get(board_app, "/api/v1/board/tutorials/sections/5")).status_code == 200
    assert (await _get(board_app, "/api/v1/board/tutorials/figures/7")).status_code == 200
    board_app.state.remote_client.get_tutorial_books.assert_awaited_once_with("joseki")
    board_app.state.remote_client.get_tutorial_chapters.assert_awaited_once_with(1)


@pytest.mark.asyncio
async def test_asset_redirects_to_remote_gateway(board_app):
    resp = await _get(board_app, "/api/v1/board/tutorials/assets/book/video/section_5.mp4")
    assert resp.status_code == 302
    assert resp.headers["location"] == "http://up/api/v1/tutorials/assets/book/video/section_5.mp4"


@pytest.mark.asyncio
async def test_upstream_404_passes_through(board_app):
    board_app.state.remote_client.get_tutorial_section.side_effect = _http_status_error(404, "not found")
    assert (await _get(board_app, "/api/v1/board/tutorials/sections/999")).status_code == 404


@pytest.mark.asyncio
async def test_upstream_unreachable_maps_502(board_app):
    board_app.state.remote_client.get_tutorial_categories.side_effect = httpx.ConnectError("refused")
    assert (await _get(board_app, "/api/v1/board/tutorials/categories")).status_code == 502


@pytest.mark.asyncio
async def test_not_board_mode_503():
    os.environ["KATRAIN_DATABASE_PATH"] = "test_board_tutorial_proxy_nb.db"
    app = create_app(enable_engine=False)  # no remote_client on app.state
    resp = await _get(app, "/api/v1/board/tutorials/categories")
    assert resp.status_code == 503


@pytest.mark.asyncio
async def test_ogs_course_and_step_proxy_forward_language_and_page(board_app):
    course = await _get(board_app, "/api/v1/board/tutorials/ogs-course?lang=zh-cn")
    step = await _get(board_app, "/api/v1/board/tutorials/ogs-course/steps/2?lang=en")
    assert course.status_code == 200 and course.json() == {"chapters": [{"id": "basics"}]}
    assert step.status_code == 200 and step.json()["source_id"] == "ogs-learning:basics:2"
    board_app.state.remote_client.get_ogs_course.assert_awaited_once_with("zh-cn")
    board_app.state.remote_client.get_ogs_step.assert_awaited_once_with(2, "en")


@pytest.mark.asyncio
@pytest.mark.parametrize("method,path", [
    ("get_ogs_course", "/api/v1/board/tutorials/ogs-course"),
    ("get_ogs_step", "/api/v1/board/tutorials/ogs-course/steps/2"),
])
@pytest.mark.parametrize("upstream_status", [404, 503])
async def test_ogs_proxy_preserves_upstream_status(board_app, method, path, upstream_status):
    getattr(board_app.state.remote_client, method).side_effect = _http_status_error(upstream_status, "upstream")
    response = await _get(board_app, path)
    assert response.status_code == upstream_status


@pytest.mark.asyncio
@pytest.mark.parametrize("method,path", [
    ("get_ogs_course", "/api/v1/board/tutorials/ogs-course"),
    ("get_ogs_step", "/api/v1/board/tutorials/ogs-course/steps/2"),
])
async def test_ogs_proxy_connection_failure_maps_502(board_app, method, path):
    getattr(board_app.state.remote_client, method).side_effect = httpx.ConnectError("refused")
    assert (await _get(board_app, path)).status_code == 502


@pytest.mark.asyncio
async def test_ogs_remote_client_calls_public_paths_without_auth():
    client = RemoteAPIClient(base_url="http://up", device_id="test-dev")
    response = MagicMock()
    response.json.return_value = {"ok": True}
    client._request = AsyncMock(return_value=response)
    try:
        assert await client.get_ogs_course("zh-cn") == {"ok": True}
        client._request.assert_awaited_with(
            "GET", "/api/v1/tutorials/ogs-course", params={"lang": "zh-cn"}, auth=False
        )
        assert await client.get_ogs_step(2, "en") == {"ok": True}
        client._request.assert_awaited_with(
            "GET", "/api/v1/tutorials/ogs-course/steps/2", params={"lang": "en"}, auth=False
        )
    finally:
        await client.close()
