"""board 模式棋谱库:连不上云端是 503,不是空库(N9)。

以前 `RepositoryDispatcher.kifu_*` 离线回空列表 / None ⇒ 列表端点 200 空、详情端点 404,
屏 15 写「没有对得上的谱 · 换棋手名再试」—— 人会去反复换关键词,而真实原因是没网。
判据落在**端点给出的状态码**上:前端靠 503 分出「要联网」和「没搜到」。
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from fastapi import HTTPException

from katrain.web.api.v1.endpoints import kifu
from katrain.web.core.repository import RemoteKifuRepository, RepositoryDispatcher


class _Connectivity:
    def __init__(self, online: bool):
        self.is_online = online


def _dispatcher(online=True, *, search=None, get=None):
    remote = MagicMock()
    remote.search_kifu = search or AsyncMock(return_value={"items": [], "total": 0, "page": 1, "page_size": 6})
    remote.get_kifu = get or AsyncMock(return_value={"id": 7})
    return RepositoryDispatcher(
        connectivity_manager=_Connectivity(online),
        remote_tsumego=MagicMock(),
        remote_kifu=RemoteKifuRepository(remote),
        remote_user_games=MagicMock(),
        local_user_game_repo=MagicMock(),
        remote_client=remote,
    )


def _request(dispatcher):
    return SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(repository_dispatcher=dispatcher)))


def _status_error(code):
    request = httpx.Request("GET", "https://cloud.example/api/v1/kifu/albums/7")
    return httpx.HTTPStatusError("upstream", request=request, response=httpx.Response(code, request=request))


@pytest.mark.asyncio
async def test_offline_list_is_503_not_an_empty_library():
    with pytest.raises(HTTPException) as exc:
        await kifu.list_kifu_albums(request=_request(_dispatcher(online=False)), q=None, page=1, page_size=6, db=None)
    assert exc.value.status_code == 503
    assert exc.value.detail == "Remote kifu service unavailable"


@pytest.mark.asyncio
async def test_offline_detail_is_503_not_not_found():
    with pytest.raises(HTTPException) as exc:
        await kifu.get_kifu_album(request=_request(_dispatcher(online=False)), album_id=7, db=None)
    assert exc.value.status_code == 503


@pytest.mark.asyncio
async def test_cloud_unreachable_is_503():
    d = _dispatcher(search=AsyncMock(side_effect=httpx.ConnectError("refused")))
    with pytest.raises(HTTPException) as exc:
        await kifu.list_kifu_albums(request=_request(d), q=None, page=1, page_size=6, db=None)
    assert exc.value.status_code == 503


@pytest.mark.asyncio
async def test_cloud_404_stays_404():
    d = _dispatcher(get=AsyncMock(side_effect=_status_error(404)))
    with pytest.raises(HTTPException) as exc:
        await kifu.get_kifu_album(request=_request(d), album_id=7, db=None)
    assert exc.value.status_code == 404
    assert exc.value.detail == "Kifu album 7 not found"


@pytest.mark.asyncio
async def test_online_passes_through():
    # 非空数据和非默认参数:丢掉远端结果或查询参数都必须红,不能拿空库兜底当成功。
    payload = {"items": [{"id": 23, "event": "三星杯"}], "total": 19, "page": 3, "page_size": 6}
    detail = {"id": 23, "sgf_content": "(;SZ[19];B[pd])"}
    search = AsyncMock(return_value=payload)
    get = AsyncMock(return_value=detail)
    d = _dispatcher(search=search, get=get)
    listed = await kifu.list_kifu_albums(request=_request(d), q="三星杯", page=3, page_size=6, db=None)
    assert listed == payload
    search.assert_awaited_once_with(q="三星杯", page=3, page_size=6)
    assert await kifu.get_kifu_album(request=_request(d), album_id=23, db=None) == detail
    get.assert_awaited_once_with(23)


@pytest.mark.asyncio
@pytest.mark.parametrize("endpoint", ["list", "detail"])
@pytest.mark.parametrize("upstream_status, expected_status", [(403, 403), (500, 503)])
async def test_cloud_errors_keep_4xx_and_map_5xx(endpoint, upstream_status, expected_status):
    remote_call = AsyncMock(side_effect=_status_error(upstream_status))
    d = _dispatcher(**{"search" if endpoint == "list" else "get": remote_call})
    with pytest.raises(HTTPException) as exc:
        if endpoint == "list":
            await kifu.list_kifu_albums(request=_request(d), q=None, page=1, page_size=6, db=None)
        else:
            await kifu.get_kifu_album(request=_request(d), album_id=7, db=None)
    assert exc.value.status_code == expected_status
    assert exc.value.detail == (
        "Remote kifu service unavailable" if expected_status == 503 else "Remote kifu request failed (403)"
    )
