"""Board-mode Report contract: reports and deletes are remote-only."""

import uuid
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from katrain.web.core import models_db
from katrain.web.core.auth import SQLAlchemyUserRepository
from katrain.web.core.db import Base
from katrain.web.core.repository import RepositoryDispatcher, RemoteUserGameRepository
from katrain.web.core.user_game_repo import UserGameAnalysisRepository, UserGameRepository
from katrain.web.server import create_app


class _Connectivity:
    def __init__(self, online: bool):
        self.is_online = online


@pytest.fixture
def board_app(tmp_path, monkeypatch):
    database_path = tmp_path / "board-report.db"
    engine = create_engine(f"sqlite:///{database_path}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    monkeypatch.setenv("KATRAIN_DATABASE_PATH", str(database_path))
    app = create_app(enable_engine=False)
    app.state.user_repo = SQLAlchemyUserRepository(session_factory)
    app.state.user_game_repo = UserGameRepository(session_factory)
    app.state.user_game_analysis_repo = UserGameAnalysisRepository(session_factory)
    app.state.report_session_factory = session_factory

    remote = MagicMock()
    remote.login = AsyncMock(return_value={"access_token": "remote-token", "token_type": "bearer"})
    task = {
        "id": 41,
        "user_game_id": "remote-game",
        "status": "completed",
        "report_type": "normal",
        "total_moves": 2,
        "analyzed_moves": 2,
        "requested_visits": 500,
    }
    remote.list_reports = AsyncMock(return_value=[task])
    remote.get_report_summary = AsyncMock(return_value={"pending": 0, "running": 0, "completed": 1, "failed": 0})
    remote.get_report = AsyncMock(return_value=task)
    remote.create_report = AsyncMock(return_value=task)
    remote.retry_report = AsyncMock(return_value={**task, "status": "pending"})
    remote.get_report_moves = AsyncMock(return_value=[{"id": 9, "task_id": 41, "move_number": 1, "actual_move": "Q16"}])
    remote.delete_user_game = AsyncMock(return_value={"status": "deleted"})

    local_user_games = MagicMock(wraps=app.state.user_game_repo)
    dispatcher = RepositoryDispatcher(
        connectivity_manager=_Connectivity(online=True),
        remote_tsumego=MagicMock(),
        remote_kifu=MagicMock(),
        remote_user_games=RemoteUserGameRepository(remote),
        local_user_game_repo=local_user_games,
        remote_client=remote,
    )
    app.state.repository_dispatcher = dispatcher
    app.state.remote_client = remote
    app.state._test_remote = remote
    app.state._test_connectivity = dispatcher._connectivity
    app.state._test_local_user_games = local_user_games
    yield app
    engine.dispose()


async def _login_headers(app):
    username = f"board-report-{uuid.uuid4().hex[:8]}"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/auth/login", json={"username": username, "password": "password"})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.mark.asyncio
async def test_board_report_endpoints_forward_to_remote_without_local_report_writes(board_app):
    headers = await _login_headers(board_app)
    async with AsyncClient(transport=ASGITransport(app=board_app), base_url="http://test") as client:
        assert (await client.get("/api/v1/reports/", headers=headers)).json()[0]["id"] == 41
        assert (await client.get("/api/v1/reports/summary", headers=headers)).json()["completed"] == 1
        assert (await client.get("/api/v1/reports/41", headers=headers)).json()["id"] == 41
        assert (await client.get("/api/v1/reports/41/moves", headers=headers)).json()[0]["actual_move"] == "Q16"
        created = await client.post(
            "/api/v1/reports/",
            headers=headers,
            json={"user_game_id": "remote-game", "report_type": "normal", "force": True},
        )
        assert created.status_code == 200
        assert (await client.post("/api/v1/reports/41/retry", headers=headers)).status_code == 200

    remote = board_app.state._test_remote
    remote.list_reports.assert_awaited_once_with()
    remote.get_report_summary.assert_awaited_once_with()
    remote.get_report.assert_awaited_once_with(41)
    remote.get_report_moves.assert_awaited_once_with(41)
    remote.create_report.assert_awaited_once_with(
        {"user_game_id": "remote-game", "report_type": "normal", "force": True}
    )
    remote.retry_report.assert_awaited_once_with(41)

    db = board_app.state.report_session_factory()
    try:
        assert db.query(models_db.ReportTask).count() == 0
        assert db.query(models_db.ReportTaskMove).count() == 0
    finally:
        db.close()


@pytest.mark.asyncio
async def test_board_delete_user_game_is_remote_only(board_app):
    headers = await _login_headers(board_app)
    async with AsyncClient(transport=ASGITransport(app=board_app), base_url="http://test") as client:
        response = await client.delete("/api/v1/user-games/remote-game", headers=headers)

    assert response.status_code == 200
    assert response.json() == {"status": "deleted"}
    board_app.state._test_remote.delete_user_game.assert_awaited_once_with("remote-game")
    board_app.state._test_local_user_games.delete.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "method,path,json_body",
    [
        ("GET", "/api/v1/reports/", None),
        ("GET", "/api/v1/reports/summary", None),
        ("GET", "/api/v1/reports/41", None),
        ("GET", "/api/v1/reports/41/moves", None),
        ("POST", "/api/v1/reports/", {"user_game_id": "remote-game", "report_type": "normal"}),
        ("POST", "/api/v1/reports/41/retry", None),
        ("DELETE", "/api/v1/user-games/remote-game", None),
    ],
)
async def test_board_remote_only_operations_return_recoverable_503_offline(board_app, method, path, json_body):
    headers = await _login_headers(board_app)
    board_app.state._test_connectivity.is_online = False
    async with AsyncClient(transport=ASGITransport(app=board_app), base_url="http://test") as client:
        response = await client.request(method, path, headers=headers, json=json_body)

    assert response.status_code == 503
    expected_detail = "Remote server unavailable" if method == "DELETE" else "Remote report service unavailable"
    assert response.json()["detail"] == expected_detail
    if method == "POST" and path == "/api/v1/reports/":
        db = board_app.state.report_session_factory()
        try:
            assert db.query(models_db.ReportTask).count() == 0
        finally:
            db.close()
    if method == "DELETE":
        board_app.state._test_local_user_games.delete.assert_not_called()


@pytest.mark.asyncio
async def test_board_report_connection_failure_returns_recoverable_503(board_app):
    headers = await _login_headers(board_app)
    board_app.state._test_remote.get_report.side_effect = httpx.ConnectError("refused")
    async with AsyncClient(transport=ASGITransport(app=board_app), base_url="http://test") as client:
        response = await client.get("/api/v1/reports/41", headers=headers)

    assert response.status_code == 503
    assert response.json()["detail"] == "Remote report service unavailable"


@pytest.mark.asyncio
async def test_board_create_report_timeout_returns_503_without_local_pending_task(board_app):
    headers = await _login_headers(board_app)
    request = httpx.Request("POST", "http://up/api/v1/reports/")
    board_app.state._test_remote.create_report.side_effect = httpx.ReadTimeout("timed out", request=request)
    async with AsyncClient(transport=ASGITransport(app=board_app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/reports/",
            headers=headers,
            json={"user_game_id": "remote-game", "report_type": "normal"},
        )

    assert response.status_code == 503
    assert response.json()["detail"] == "Remote report service unavailable"
    db = board_app.state.report_session_factory()
    try:
        assert db.query(models_db.ReportTask).count() == 0
    finally:
        db.close()


@pytest.mark.asyncio
async def test_board_create_report_read_error_returns_503_without_local_pending_task(board_app):
    headers = await _login_headers(board_app)
    request = httpx.Request("POST", "http://up/api/v1/reports/")
    board_app.state._test_remote.create_report.side_effect = httpx.ReadError("connection reset", request=request)
    async with AsyncClient(transport=ASGITransport(app=board_app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/reports/",
            headers=headers,
            json={"user_game_id": "remote-game", "report_type": "normal"},
        )

    assert response.status_code == 503
    assert response.json()["detail"] == "Remote report service unavailable"
    db = board_app.state.report_session_factory()
    try:
        assert db.query(models_db.ReportTask).count() == 0
    finally:
        db.close()


@pytest.mark.asyncio
async def test_board_delete_protocol_error_returns_503_without_local_delete(board_app):
    headers = await _login_headers(board_app)
    request = httpx.Request("DELETE", "http://up/api/v1/user-games/remote-game")
    board_app.state._test_remote.delete_user_game.side_effect = httpx.RemoteProtocolError(
        "invalid response", request=request
    )
    async with AsyncClient(transport=ASGITransport(app=board_app), base_url="http://test") as client:
        response = await client.delete("/api/v1/user-games/remote-game", headers=headers)

    assert response.status_code == 503
    assert response.json()["detail"] == "Remote server unavailable"
    board_app.state._test_local_user_games.delete.assert_not_called()


@pytest.mark.asyncio
async def test_board_report_upstream_server_failure_returns_recoverable_503(board_app):
    headers = await _login_headers(board_app)
    upstream_response = httpx.Response(
        500,
        text="upstream failed",
        request=httpx.Request("GET", "http://up/api/v1/reports/41"),
    )
    board_app.state._test_remote.get_report.side_effect = httpx.HTTPStatusError(
        "500", request=upstream_response.request, response=upstream_response
    )
    async with AsyncClient(transport=ASGITransport(app=board_app), base_url="http://test") as client:
        response = await client.get("/api/v1/reports/41", headers=headers)

    assert response.status_code == 503
    assert response.json()["detail"] == "Remote report service unavailable"


@pytest.mark.asyncio
async def test_board_report_upstream_json_error_detail_is_preserved(board_app):
    headers = await _login_headers(board_app)
    upstream_response = httpx.Response(
        404,
        json={"detail": "Report task not found"},
        request=httpx.Request("GET", "http://up/api/v1/reports/999"),
    )
    board_app.state._test_remote.get_report.side_effect = httpx.HTTPStatusError(
        "404", request=upstream_response.request, response=upstream_response
    )
    async with AsyncClient(transport=ASGITransport(app=board_app), base_url="http://test") as client:
        response = await client.get("/api/v1/reports/999", headers=headers)

    assert response.status_code == 404
    assert response.json() == {"detail": "Report task not found"}
