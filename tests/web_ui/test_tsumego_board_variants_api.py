"""The same opt-in detail contract works on the cloud and after the board proxy."""

import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from katrain.web.api.v1.endpoints import tsumego
from katrain.web.core.db import get_db


SOURCE = dict(
    id="source-9",
    level="15k",
    category="capturing",
    hint="黑先",
    boardSize=9,
    initialBlack=["ba"],
    initialWhite=["aa"],
    sgfContent="(;SZ[9]AB[ba]AW[aa];B[ab])",
)


@pytest.mark.asyncio
@pytest.mark.parametrize("board_mode", [False, True])
@pytest.mark.parametrize("status", ["adapted", "unavailable"])
async def test_detail_variant_preserves_identity_default_and_old_cloud_signature(monkeypatch, board_mode, status):
    app = FastAPI()
    app.include_router(tsumego.router, prefix="/api/v1/tsumego")
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = SimpleNamespace(
        id=SOURCE["id"],
        level=SOURCE["level"],
        category=SOURCE["category"],
        hint=SOURCE["hint"],
        board_size=SOURCE["boardSize"],
        initial_black=SOURCE["initialBlack"],
        initial_white=SOURCE["initialWhite"],
        sgf_content=SOURCE["sgfContent"],
    )
    app.dependency_overrides[get_db] = lambda: db
    remote = AsyncMock(return_value=SOURCE)
    if board_mode:
        app.state.repository_dispatcher = SimpleNamespace(tsumego_get_problem=remote)
    adapted = {
        **SOURCE,
        "boardSize": 19 if status == "adapted" else 9,
        "board_variant": dict(
            status=status,
            source_size=9,
            target_size=19,
            policy_version="test",
            source_sha256="test",
            offset=[0, 0],
            reason="保留原题" if status == "unavailable" else "局部提子",
        ),
    }
    calls = []
    monkeypatch.setitem(
        sys.modules,
        "katrain.web.content.board_variants",
        SimpleNamespace(
            adapt_tsumego_detail=lambda detail: calls.append(detail) or adapted,
        ),
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        assert (await client.get(f'/api/v1/tsumego/problems/{SOURCE["id"]}')).json() == SOURCE
        assert calls == []
        response = await client.get(f'/api/v1/tsumego/problems/{SOURCE["id"]}?board_variant=kiosk19')
        assert response.status_code == 200 and response.json() == adapted
        assert calls == [SOURCE]
    if board_mode:
        assert remote.await_args_list[-1].args == (SOURCE["id"],)
        assert remote.await_args_list[-1].kwargs == {}


@pytest.mark.asyncio
@pytest.mark.parametrize("problem_id,status", [("124386", "adapted"), ("108018", "unavailable")])
async def test_real_source_variant_is_derived_after_the_board_read_without_changing_source(problem_id, status):
    import copy
    import json
    from pathlib import Path

    sources = json.loads((Path(__file__).parent / "data/kiosk19_sources.json").read_text())
    source = next(item for item in sources["tsumego"] if item["id"] == problem_id)
    before = copy.deepcopy(source)
    remote = AsyncMock(return_value=source)
    app = FastAPI()
    app.include_router(tsumego.router, prefix="/api/v1/tsumego")
    app.dependency_overrides[get_db] = lambda: None
    app.state.repository_dispatcher = SimpleNamespace(tsumego_get_problem=remote)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(f"/api/v1/tsumego/problems/{problem_id}?board_variant=kiosk19")
        assert response.status_code == 200
        result = response.json()
        assert result["id"] == problem_id and result["board_variant"]["status"] == status
        if status == "adapted":
            assert result["boardSize"] == 19 and "SZ[19]" in result["sgfContent"]
            assert result["initialBlack"] != source["initialBlack"]
            assert ";B[sj]" in result["sgfContent"] and ";B[sk];W[sj];B[si]" in result["sgfContent"]
        else:
            assert {key: result[key] for key in source} == source
            assert result["board_variant"]["reason"]
        assert (await client.get(f"/api/v1/tsumego/problems/{problem_id}")).json() == before
    assert source == before
