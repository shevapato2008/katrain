import os
import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from katrain.web.core.config import settings
from katrain.web.core.db import Base
from katrain.web.server import create_app


settings.DATABASE_URL = "sqlite:///./test_reports_api.db"


@pytest.fixture
def app():
    if os.path.exists("./test_reports_api.db"):
        os.remove("./test_reports_api.db")

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from katrain.web.core.auth import SQLAlchemyUserRepository
    from katrain.web.core.game_repo import GameRepository
    from katrain.web.core.user_game_repo import UserGameAnalysisRepository, UserGameRepository

    test_engine = create_engine(settings.DATABASE_URL, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=test_engine)
    TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

    app = create_app(enable_engine=False)
    app.state.user_repo = SQLAlchemyUserRepository(TestSessionLocal)
    app.state.game_repo = GameRepository(TestSessionLocal)
    app.state.user_game_repo = UserGameRepository(TestSessionLocal)
    app.state.user_game_analysis_repo = UserGameAnalysisRepository(TestSessionLocal)
    app.state.report_session_factory = TestSessionLocal

    yield app

    if os.path.exists("./test_reports_api.db"):
        os.remove("./test_reports_api.db")


async def _login_and_get_headers(app, username="reporter", password="password"):
    username = f"{username}-{uuid.uuid4().hex[:8]}"
    repo = app.state.user_repo
    from passlib.context import CryptContext

    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    hashed = pwd_context.hash(password)
    repo.create_user(username, hashed)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        login_resp = await ac.post(
            "/api/v1/auth/login",
            json={"username": username, "password": password},
        )
        assert login_resp.status_code == 200
        token = login_resp.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_create_report_task_requires_owned_game(app):
    headers = await _login_and_get_headers(app)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post(
            "/api/v1/reports/",
            headers=headers,
            json={"user_game_id": "missing-game", "report_type": "normal"},
        )
        assert resp.status_code == 404


@pytest.mark.asyncio
async def test_create_report_task_is_idempotent_and_moves_are_readable(app):
    headers = await _login_and_get_headers(app)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        game_resp = await ac.post(
            "/api/v1/user-games/",
            headers=headers,
            json={
                "sgf_content": "(;FF[4]SZ[19];B[pd];W[dp])",
                "source": "import",
                "move_count": 2,
                "title": "Report Game",
            },
        )
        assert game_resp.status_code == 200
        game_id = game_resp.json()["id"]

        first = await ac.post(
            "/api/v1/reports/",
            headers=headers,
            json={"user_game_id": game_id, "report_type": "normal"},
        )
        assert first.status_code == 200
        first_task = first.json()
        assert first_task["user_game_id"] == game_id
        assert first_task["report_type"] == "normal"
        assert first_task["status"] == "pending"

        second = await ac.post(
            "/api/v1/reports/",
            headers=headers,
            json={"user_game_id": game_id, "report_type": "normal"},
        )
        assert second.status_code == 200
        assert second.json()["id"] == first_task["id"]

        from katrain.web.core import models_db

        session = app.state.report_session_factory()
        try:
            move = models_db.ReportTaskMove(
                task_id=first_task["id"],
                move_number=1,
                status="success",
                winrate=0.52,
                score_lead=1.5,
                visits=500,
                top_moves=[{"move": "Q16", "visits": 500}],
                ownership=[[0.1, -0.1], [0.2, -0.2]],
                actual_move="Q16",
                actual_player="B",
            )
            session.add(move)
            session.commit()
        finally:
            session.close()

        moves_resp = await ac.get(f"/api/v1/reports/{first_task['id']}/moves", headers=headers)
        assert moves_resp.status_code == 200
        moves = moves_resp.json()
        assert len(moves) == 1
        assert moves[0]["move_number"] == 1
        assert moves[0]["actual_move"] == "Q16"


@pytest.mark.asyncio
async def test_create_report_task_force_and_report_type_create_distinct_tasks(app):
    headers = await _login_and_get_headers(app)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        game_resp = await ac.post(
            "/api/v1/user-games/",
            headers=headers,
            json={
                "sgf_content": "(;FF[4]SZ[19];B[pd];W[dp])",
                "source": "import",
                "move_count": 2,
                "title": "Force Test",
            },
        )
        assert game_resp.status_code == 200
        game_id = game_resp.json()["id"]

        normal_first = await ac.post(
            "/api/v1/reports/",
            headers=headers,
            json={"user_game_id": game_id, "report_type": "normal"},
        )
        assert normal_first.status_code == 200
        normal_first_id = normal_first.json()["id"]

        normal_forced = await ac.post(
            "/api/v1/reports/",
            headers=headers,
            json={"user_game_id": game_id, "report_type": "normal", "force": True},
        )
        assert normal_forced.status_code == 200
        assert normal_forced.json()["id"] != normal_first_id

        deep_task = await ac.post(
            "/api/v1/reports/",
            headers=headers,
            json={"user_game_id": game_id, "report_type": "deep"},
        )
        assert deep_task.status_code == 200
        assert deep_task.json()["id"] not in {normal_first_id, normal_forced.json()["id"]}
        assert deep_task.json()["requested_visits"] > normal_first.json()["requested_visits"]
