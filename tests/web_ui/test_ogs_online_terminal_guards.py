"""A remote OGS game must not be adjudicated by local multiplayer endpoints."""

from unittest.mock import MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from katrain.web.api.v1.endpoints.auth import get_current_user, get_current_user_optional
from katrain.web.models import User
from katrain.web.server import create_app
from katrain.web.session import WebSession


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "path,extra",
    [
        ("/api/count/request", {}),
        ("/api/count/respond", {"accept": True}),
        ("/api/timeout", {}),
        ("/api/multiplayer/leave", {}),
    ],
)
async def test_local_terminal_endpoint_cannot_end_online_game(path, extra):
    app = create_app(enable_engine=False)
    katrain = MagicMock()
    katrain.game_type = "pvp_online"
    session = WebSession(session_id="ogs-game", katrain=katrain, user_id=7, player_b_id=7, player_w_id=-1)
    session.game_type = "pvp_online"
    app.state.session_manager._sessions[session.session_id] = session
    user = User(id=7, username="owner")
    app.dependency_overrides[get_current_user_optional] = lambda: user
    app.dependency_overrides[get_current_user] = lambda: user

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(path, json={"session_id": session.session_id, **extra})

    assert response.status_code == 409
    katrain.assert_not_called()
