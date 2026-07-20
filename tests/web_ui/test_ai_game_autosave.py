"""Tests for auto-saving AI (single-player) games to user_games on game completion."""

import uuid
from unittest.mock import MagicMock, patch
import threading

import pytest
from httpx import ASGITransport, AsyncClient

from katrain.web.core.config import settings

from tests.web_ui._helpers import _create_user_and_login

settings.DATABASE_URL = "sqlite:///./test_ai_autosave.db"


def _make_mock_session(user_id, sgf="(;FF[4]SZ[19];B[pd];W[dp])", end_result="B+R"):
    """Create a mock WebSession for a single-player AI game."""
    session = MagicMock()
    session.session_id = uuid.uuid4().hex
    session.user_id = user_id
    session.player_b_id = None  # Not multiplayer
    session.player_w_id = None
    session.mode = "play"
    session.game_type = "free"
    session.lock = threading.Lock()
    session.sockets = set()
    session.pending_count_request = None
    session.pending_count_timestamp = None
    # Pre-existing test-fixture bug (unrelated to guest mode): a bare MagicMock()
    # auto-vivifies ANY attribute access, so `getattr(session, "_recorded", False)`
    # in `_record_ai_game` never sees the intended False default and the game is
    # silently never recorded. A real WebSession explicitly initializes this to
    # False; the fake session double must do the same.
    session._recorded = False

    # Mock katrain
    katrain = MagicMock()
    katrain.get_sgf.return_value = sgf

    # Mock game
    game = MagicMock()
    game.end_result = end_result
    game.current_node.end_state = end_result
    game.current_node.player = "B"  # Last move was by Black
    game.current_node.score = 5.5
    katrain.game = game

    # Mock players_info
    black_player = MagicMock()
    black_player.name = "testuser"
    black_player.human = True
    black_player.ai = False
    black_player.calculated_rank = None
    # Same MagicMock-auto-vivification trap as `_recorded` above: `_record_ai_game`
    # falls back to `sgf_rank` when `calculated_rank` is falsy, via
    # `getattr(players_info["B"], "sgf_rank", None)` — an unset attribute on a
    # bare MagicMock() is NOT None, it's a fresh child Mock, which then fails to
    # bind as a SQL parameter. Must be set explicitly on both sides.
    black_player.sgf_rank = None

    white_player = MagicMock()
    white_player.name = ""
    white_player.human = False
    white_player.ai = True
    white_player.calculated_rank = "5d"
    white_player.sgf_rank = None

    katrain.players_info = {"B": black_player, "W": white_player}

    # Mock get_state
    katrain.get_state.return_value = {
        "board_size": [19, 19],
        "komi": 7.5,
        "ruleset": "chinese",
        "history": [{"move": [3, 15]}, {"move": [3, 3]}],
        "end_result": end_result,
        "players_info": {
            "B": {"player_type": "player:human", "name": "testuser"},
            "W": {"player_type": "player:ai", "name": ""},
        },
    }

    session.katrain = katrain
    return session


@pytest.mark.asyncio
async def test_resign_ai_game_auto_saves(app):
    """When a logged-in user resigns an AI game, it should be saved to user_games."""
    headers, user_id, username = await _create_user_and_login(app)
    mock_session = _make_mock_session(user_id)
    mock_session.katrain.players_info["B"].name = username

    # Inject mock session into the session manager
    app.state.session_manager._sessions[mock_session.session_id] = mock_session

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Verify no games exist yet
        games_resp = await ac.get("/api/v1/user-games/", headers=headers)
        assert games_resp.status_code == 200
        assert games_resp.json()["total"] == 0

        # Resign the AI game
        resign_resp = await ac.post(
            "/api/resign",
            headers=headers,
            json={"session_id": mock_session.session_id},
        )
        assert resign_resp.status_code == 200

        # Verify a game was auto-saved
        games_resp = await ac.get("/api/v1/user-games/", headers=headers)
        assert games_resp.status_code == 200
        data = games_resp.json()
        assert data["total"] == 1

        game = data["items"][0]
        assert game["source"] == "play_ai"
        assert game["result"] == "B+R"
        assert game["player_black"] == username
        assert game["player_white"] == "AI (5d)"
        assert game["game_type"] == "free"
        assert game["category"] == "game"
        assert game["move_count"] == 2


@pytest.mark.asyncio
async def test_timeout_ai_game_auto_saves(app):
    """When an AI game times out, it should be saved to user_games."""
    headers, user_id, username = await _create_user_and_login(app)
    mock_session = _make_mock_session(user_id, end_result="W+T")
    mock_session.katrain.players_info["B"].name = username

    app.state.session_manager._sessions[mock_session.session_id] = mock_session

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        timeout_resp = await ac.post(
            "/api/timeout",
            headers=headers,
            json={"session_id": mock_session.session_id},
        )
        assert timeout_resp.status_code == 200

        games_resp = await ac.get("/api/v1/user-games/", headers=headers)
        assert games_resp.status_code == 200
        data = games_resp.json()
        assert data["total"] == 1

        game = data["items"][0]
        assert game["source"] == "play_ai"
        assert game["result"] == "W+T"


@pytest.mark.asyncio
async def test_ai_game_not_saved_when_no_user(app):
    """Anonymous users should NOT have games auto-saved."""
    mock_session = _make_mock_session(user_id=None)
    mock_session.user_id = None

    app.state.session_manager._sessions[mock_session.session_id] = mock_session

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resign_resp = await ac.post(
            "/api/resign",
            json={"session_id": mock_session.session_id},
        )
        assert resign_resp.status_code == 200
        # No user to check games for, but no crash either


@pytest.mark.asyncio
async def test_ai_game_saves_with_ai_name_fallback(app):
    """AI player name falls back to 'AI' when no calculated_rank is available."""
    headers, user_id, username = await _create_user_and_login(app)
    mock_session = _make_mock_session(user_id)
    mock_session.katrain.players_info["B"].name = username
    mock_session.katrain.players_info["W"].calculated_rank = None  # No rank available

    app.state.session_manager._sessions[mock_session.session_id] = mock_session

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resign_resp = await ac.post(
            "/api/resign",
            headers=headers,
            json={"session_id": mock_session.session_id},
        )
        assert resign_resp.status_code == 200

        games_resp = await ac.get("/api/v1/user-games/", headers=headers)
        game = games_resp.json()["items"][0]
        assert game["player_white"] == "AI"


@pytest.mark.asyncio
async def test_ai_game_visible_in_report_page(app):
    """Auto-saved AI games should appear in the report module's game list."""
    headers, user_id, username = await _create_user_and_login(app)
    mock_session = _make_mock_session(user_id)
    mock_session.katrain.players_info["B"].name = username

    app.state.session_manager._sessions[mock_session.session_id] = mock_session

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Resign the game
        await ac.post(
            "/api/resign",
            headers=headers,
            json={"session_id": mock_session.session_id},
        )

        # The report page reads from the same user-games endpoint
        games_resp = await ac.get("/api/v1/user-games/", headers=headers)
        assert games_resp.status_code == 200
        data = games_resp.json()
        assert data["total"] == 1
        game = data["items"][0]
        assert game["source"] == "play_ai"

        # Verify the game has SGF content (needed for report generation)
        detail_resp = await ac.get(f"/api/v1/user-games/{game['id']}", headers=headers)
        assert detail_resp.status_code == 200
        detail = detail_resp.json()
        assert detail["sgf_content"] == "(;FF[4]SZ[19];B[pd];W[dp])"

        # Verify a report can be created for this game
        report_resp = await ac.post(
            "/api/v1/reports/",
            headers=headers,
            json={"user_game_id": game["id"], "report_type": "normal"},
        )
        assert report_resp.status_code == 200
        assert report_resp.json()["user_game_id"] == game["id"]


@pytest.mark.asyncio
async def test_multiplayer_game_not_double_saved(app):
    """Multiplayer games should use their own save path, not _record_ai_game."""
    headers, user_id, username = await _create_user_and_login(app)

    # Create a multiplayer-like session (has player_b_id and player_w_id)
    mock_session = _make_mock_session(user_id)
    mock_session.player_b_id = user_id
    mock_session.player_w_id = user_id + 1  # Different user

    app.state.session_manager._sessions[mock_session.session_id] = mock_session

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resign_resp = await ac.post(
            "/api/resign",
            headers=headers,
            json={"session_id": mock_session.session_id},
        )
        assert resign_resp.status_code == 200

        # Multiplayer games are saved via record_multiplayer_game, not user_game_repo.create
        # So user-games list should show the multiplayer-saved records, not AI-saved ones
        games_resp = await ac.get(
            "/api/v1/user-games/",
            headers=headers,
            params={"source": "play_ai"},
        )
        assert games_resp.json()["total"] == 0
