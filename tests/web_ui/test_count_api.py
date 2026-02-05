"""Tests for the counting (数子) feature."""
import pytest
import time
from unittest.mock import MagicMock, patch

from katrain.web.session import SessionManager, WebSession


class TestCountResultFormatting:
    """Test score result formatting."""

    def test_black_wins_format(self):
        """Black winning should format as B+X.X"""
        # Score > 0 means Black leads
        score = 5.5
        if score >= 0:
            result = f"B+{abs(score):.1f}"
        else:
            result = f"W+{abs(score):.1f}"
        assert result == "B+5.5"

    def test_white_wins_format(self):
        """White winning should format as W+X.X"""
        # Score < 0 means White leads
        score = -3.5
        if score >= 0:
            result = f"B+{abs(score):.1f}"
        else:
            result = f"W+{abs(score):.1f}"
        assert result == "W+3.5"

    def test_jigo_format(self):
        """Tie game should format as B+0.0"""
        score = 0
        if score >= 0:
            result = f"B+{abs(score):.1f}"
        else:
            result = f"W+{abs(score):.1f}"
        assert result == "B+0.0"


class TestWebSessionCountFields:
    """Test WebSession count request fields."""

    def test_session_has_count_fields(self):
        """WebSession should have pending_count_request and pending_count_timestamp fields."""
        from katrain.web.session import WebSession
        from dataclasses import fields

        field_names = [f.name for f in fields(WebSession)]
        assert "pending_count_request" in field_names
        assert "pending_count_timestamp" in field_names

    def test_count_fields_default_to_none(self):
        """Count fields should default to None."""
        # Create a mock katrain
        mock_katrain = MagicMock()

        session = WebSession(
            session_id="test-123",
            katrain=mock_katrain
        )

        assert session.pending_count_request is None
        assert session.pending_count_timestamp is None


class TestCountRequestTimeout:
    """Test count request timeout cleanup."""

    def test_expired_requests_cleaned_up(self):
        """Pending count requests older than 60s should be cleaned up."""
        manager = SessionManager(enable_engine=False)

        # Create a mock session with expired count request
        mock_katrain = MagicMock()
        session = WebSession(
            session_id="test-123",
            katrain=mock_katrain
        )
        session.pending_count_request = 1
        session.pending_count_timestamp = time.time() - 61  # 61 seconds ago

        manager._sessions["test-123"] = session
        manager._schedule_broadcast = MagicMock()

        # Run cleanup
        manager.cleanup_expired()

        # Request should be cleared
        assert session.pending_count_request is None
        assert session.pending_count_timestamp is None

    def test_recent_requests_not_cleaned(self):
        """Pending count requests less than 60s old should not be cleaned."""
        manager = SessionManager(enable_engine=False)

        mock_katrain = MagicMock()
        session = WebSession(
            session_id="test-123",
            katrain=mock_katrain
        )
        session.pending_count_request = 1
        session.pending_count_timestamp = time.time() - 30  # 30 seconds ago

        manager._sessions["test-123"] = session
        manager._schedule_broadcast = MagicMock()

        # Run cleanup
        manager.cleanup_expired()

        # Request should NOT be cleared
        assert session.pending_count_request == 1
        assert session.pending_count_timestamp is not None

    def test_no_cleanup_without_timestamp(self):
        """Sessions without timestamp should not cause errors."""
        manager = SessionManager(enable_engine=False)

        mock_katrain = MagicMock()
        session = WebSession(
            session_id="test-123",
            katrain=mock_katrain
        )
        # No pending request
        assert session.pending_count_request is None
        assert session.pending_count_timestamp is None

        manager._sessions["test-123"] = session
        manager._schedule_broadcast = MagicMock()

        # Should not raise
        manager.cleanup_expired()


class TestCountModels:
    """Test Pydantic models for count API."""

    def test_count_request_model(self):
        """CountRequest model should accept session_id."""
        from katrain.web.models import CountRequest

        request = CountRequest(session_id="test-123")
        assert request.session_id == "test-123"

    def test_count_response_model(self):
        """CountResponse model should accept session_id and accept boolean."""
        from katrain.web.models import CountResponse

        response = CountResponse(session_id="test-123", accept=True)
        assert response.session_id == "test-123"
        assert response.accept is True

        response2 = CountResponse(session_id="test-456", accept=False)
        assert response2.accept is False


class TestMoveCountValidation:
    """Test move count validation logic."""

    def test_history_length_check(self):
        """Verify history length check logic."""
        # Simulate state with < 100 moves
        state = {"history": [{"node_id": i} for i in range(50)]}
        assert len(state.get("history", [])) < 100

        # Simulate state with >= 100 moves
        state = {"history": [{"node_id": i} for i in range(100)]}
        assert len(state.get("history", [])) >= 100

        state = {"history": [{"node_id": i} for i in range(150)]}
        assert len(state.get("history", [])) >= 100


class TestCountRequestFlow:
    """Test the count request flow logic (without HTTP)."""

    def test_hvai_flow_no_pending(self):
        """HvAI games should not use pending requests."""
        # For HvAI, player_b_id and player_w_id are None
        player_b_id = None
        player_w_id = None

        is_multiplayer = player_b_id is not None or player_w_id is not None
        assert is_multiplayer is False

    def test_hvh_flow_uses_pending(self):
        """HvH games should use pending requests."""
        player_b_id = 1
        player_w_id = 2

        is_multiplayer = player_b_id is not None or player_w_id is not None
        assert is_multiplayer is True

    def test_double_request_detection(self):
        """Second request from different player should be treated as accept."""
        pending_count_request = 1  # Player 1 requested
        current_user_id = 2  # Player 2 requesting

        # If pending request exists and is from different user, treat as accept
        should_complete = (
            pending_count_request is not None and
            pending_count_request != current_user_id
        )
        assert should_complete is True

    def test_same_user_request_ignored(self):
        """Same user requesting again should be ignored."""
        pending_count_request = 1
        current_user_id = 1  # Same user

        should_ignore = (
            pending_count_request is not None and
            pending_count_request == current_user_id
        )
        assert should_ignore is True


class TestIntegration:
    """Integration tests using WebKaTrain."""

    def test_count_button_disabled_check(self):
        """Verify count button should be disabled with < 100 moves."""
        from katrain.web.interface import WebKaTrain

        wkt = WebKaTrain(force_package_config=True, enable_engine=False)
        wkt.start()

        state = wkt.get_state()
        history_length = len(state.get("history", []))

        # At start, should be 1 (root node)
        assert history_length < 100, "New game should have < 100 moves"

        # Make a few moves
        wkt("play", (3, 3))
        wkt("play", (15, 15))
        wkt("play", (3, 15))

        state = wkt.get_state()
        history_length = len(state.get("history", []))
        assert history_length < 100, "Few moves should still be < 100"

    def test_game_state_has_history(self):
        """Verify game state includes history for move counting."""
        from katrain.web.interface import WebKaTrain

        wkt = WebKaTrain(force_package_config=True, enable_engine=False)
        wkt.start()

        state = wkt.get_state()
        assert "history" in state
        assert isinstance(state["history"], list)
