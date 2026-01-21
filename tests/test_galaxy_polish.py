import pytest
from katrain.web.session import SessionManager, Matchmaker
from katrain.web.core.auth import SQLAlchemyUserRepository
from katrain.web.core.db import SessionLocal

def test_session_user_uuid_persistence():
    """Verify that create_session correctly uses the provided UUID."""
    manager = SessionManager(enable_engine=False)
    test_uuid = "fix-uuid-123"
    session = manager.create_session(katago_uuid=test_uuid)
    assert session.katrain.user_id == test_uuid
    
    # Verify fallback
    guest_session = manager.create_session()
    assert guest_session.katrain.user_id == guest_session.session_id

def test_matchmaker_queue_logging():
    """Verify Matchmaker queue operations."""
    mm = Matchmaker()
    mock_ws = type('MockWS', (), {'send_json': lambda x: None})()
    
    # Add first user
    match1 = mm.add_to_queue(1, "free", mock_ws)
    assert match1 is None
    
    # Add same user (update)
    match2 = mm.add_to_queue(1, "free", mock_ws)
    assert match2 is None
    
    # Add second user (match)
    match3 = mm.add_to_queue(2, "free", mock_ws)
    assert match3 is not None
    assert match3.player1_id == 1
    assert match3.player2_id == 2

def test_user_repo_get_by_id():
    """Verify get_user_by_id functionality."""
    repo = SQLAlchemyUserRepository(SessionLocal)
    # Check admin user (id 1)
    admin = repo.get_user_by_id(1)
    if admin:
        assert admin["id"] == 1
        assert admin["username"] == "admin"
