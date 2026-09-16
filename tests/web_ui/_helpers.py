"""Shared test helpers for tests/web_ui.

A plain function here (unlike a plain function left in conftest.py) IS visible
to test modules via a normal `from tests.web_ui._helpers import ...` — pytest
only auto-injects *fixtures* from conftest.py into sibling module globals, not
plain functions (see R4-F5 in the box-sso guest-mode plan). Both
test_ai_game_autosave.py and test_guest_write_block.py import
`_create_user_and_login` from here so neither NameErrors.
"""

import uuid


async def _create_user_and_login(app, username="testuser"):
    """Create a user and return (headers, user_id, username)."""
    from httpx import ASGITransport, AsyncClient

    unique_name = f"{username}-{uuid.uuid4().hex[:8]}"
    from passlib.context import CryptContext

    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    hashed = pwd_context.hash("password")
    user = app.state.user_repo.create_user(unique_name, hashed)
    user_id = user["id"]

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        login_resp = await ac.post(
            "/api/v1/auth/login",
            json={"username": unique_name, "password": "password"},
        )
        assert login_resp.status_code == 200
        token = login_resp.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}, user_id, unique_name
