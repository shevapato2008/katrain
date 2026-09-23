"""盒上没有直播(Fan 2026-09-22:kiosk 端删掉整个直播模块,只在 galaxy 保留)。

原来 `/api/v1/board/live/*` 是给 kiosk 直播屏用的只读代理;直播屏删了之后它没有任何调用者。
这条守的是「盒上的直播后端也跟着没了」—— 代理回来了,kiosk 包里的直播调用也就有地方可去,
两边会一起悄悄长回来。kiosk 包那一半由 `katrain/web/ui/scripts/verify-kiosk.sh` 守。
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from katrain.web.server import create_app


@pytest.fixture
def board_app(tmp_path, monkeypatch):
    monkeypatch.setenv("KATRAIN_DATABASE_PATH", str(tmp_path / "board_no_live.db"))
    app = create_app(enable_engine=False)
    client = MagicMock()
    client.get_tutorial_categories = AsyncMock(return_value=[])
    app.state.remote_client = client
    return app


async def _get(app, path: str):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        return await ac.get(path)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/board/live/matches",
        "/api/v1/board/live/matches/featured",
        "/api/v1/board/live/translations?lang=cn",
    ],
)
async def test_board_has_no_live_proxy(board_app, path):
    resp = await _get(board_app, path)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_board_tutorial_proxy_still_served(board_app):
    """删直播时 `_get_remote_client` / `_proxy` 要留给教程代理 —— 这条防误删。"""
    resp = await _get(board_app, "/api/v1/board/tutorials/categories")
    assert resp.status_code == 200
    board_app.state.remote_client.get_tutorial_categories.assert_awaited_once()


def test_remote_client_has_no_live_reads():
    from katrain.web.core.remote_client import RemoteAPIClient

    assert [n for n in dir(RemoteAPIClient) if "live" in n] == []
