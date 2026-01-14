import pytest
import os
import sqlite3
from katrain.web.core.auth import SQLiteUserRepository

@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / "test_users.db")

@pytest.fixture
def repo(db_path):
    repo = SQLiteUserRepository(db_path)
    repo.init_db()
    return repo

def test_create_and_get_user(repo):
    repo.create_user("testuser", "hashed_pass")
    user = repo.get_user_by_username("testuser")
    assert user is not None
    assert user["username"] == "testuser"
    assert user["hashed_password"] == "hashed_pass"

def test_get_nonexistent_user(repo):
    user = repo.get_user_by_username("nonexistent")
    assert user is None

def test_duplicate_user(repo):
    repo.create_user("user1", "pass1")
    # Should probably raise a specific error, e.g. ValueError or IntegrityError
    with pytest.raises(ValueError, match="User already exists"):
        repo.create_user("user1", "pass2")

def test_list_users(repo):
    repo.create_user("user1", "p1")
    repo.create_user("user2", "p2")
    users = repo.list_users()
    assert len(users) == 2
    usernames = [u["username"] for u in users]
    assert "user1" in usernames
    assert "user2" in usernames
