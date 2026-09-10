import pytest
import os
from httpx import AsyncClient, ASGITransport
from katrain.web.server import create_app


@pytest.fixture
def app():
    # 换库 + 退出时原样还原，见 conftest.isolated_core_db 的 docstring。
    # 不还原会让别的文件里的用例静默变红（覆盖与 monkeypatch 都按对象身份匹配）。
    db_file = "test_lobby_api.db"
    if os.path.exists(db_file):
        os.remove(db_file)

    from conftest import isolated_core_db

    with isolated_core_db(f"sqlite:///{db_file}"):
        from katrain.web.core.db import engine
        from katrain.web.core.models_db import Base

        Base.metadata.create_all(bind=engine)

        app = create_app(enable_engine=False)

        # Mock repos and manager
        from katrain.web.core.auth import SQLAlchemyUserRepository
        from katrain.web.core.db import SessionLocal
        from katrain.web.session import LobbyManager

        app.state.user_repo = SQLAlchemyUserRepository(SessionLocal)
        app.state.lobby_manager = LobbyManager()

        yield app


@pytest.mark.asyncio
async def test_lobby_online_users(app):
    repo = app.state.user_repo
    from katrain.web.core.auth import get_password_hash

    user_dict = repo.create_user("user1", get_password_hash("pass1"))
    repo.create_user("user2", get_password_hash("pass2"))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Login as user1
        login_resp = await ac.post("/api/v1/auth/login", json={"username": "user1", "password": "pass1"})
        token = login_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # For now, "online" means they have an active session or connected to lobby
        # We'll manually add user1 to lobby manager for this test
        app.state.lobby_manager.add_user(user_dict["id"], None)

        response = await ac.get("/api/v1/users/online", headers=headers)
        assert response.status_code == 200
        online = response.json()
        # Should at least show user1 as online
        assert any(u["username"] == "user1" for u in online)
