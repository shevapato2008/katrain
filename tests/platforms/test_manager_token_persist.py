"""Tests for PlatformManager's token-refresh persistence.

Problem under test: a token refreshed mid-session used to only be logged
(`_on_token_refreshed`), so it was lost on the next reconnect. The manager must
now bind the emitting platform at callback-registration time (the callback
carries only auth_data, not which platform emitted it), merge the refreshed
fields into the existing stored auth_data, and persist via the credential store.

Network-free: a fake in-memory credential store stands in for
PlatformCredentialStore, and a minimal PlatformAdapter stub stands in for a real
platform adapter. Driving via the real PlatformAdapter._emit (rather than calling
_on_token_refreshed directly) exercises the lambda-binding done in
_setup_callbacks.

Tests are async (asyncio_mode=auto in pyproject.toml).
"""

from __future__ import annotations

import pytest

from katrain.web.platforms.base import PlatformAdapter
from katrain.web.platforms.manager import PlatformManager
from katrain.web.platforms.models import PlatformCredentials


class FakeCredentialStore:
    """In-memory stand-in for PlatformCredentialStore, keyed by (user_id, platform)."""

    def __init__(self):
        self._store: dict[tuple[int, str], PlatformCredentials] = {}

    def save_credentials(self, user_id: int, credentials: PlatformCredentials) -> None:
        self._store[(user_id, credentials.platform)] = credentials

    def load_credentials(self, user_id: int, platform: str):
        return self._store.get((user_id, platform))


class StubAdapter(PlatformAdapter):
    """Minimal concrete PlatformAdapter — connect always succeeds."""

    platform_name = "golaxy"

    async def connect(self, credentials: PlatformCredentials) -> bool:
        self._connected = True
        return True

    async def disconnect(self) -> None:
        self._connected = False

    async def submit_move(self, game_id: str, col: int, row: int) -> bool:
        return True

    async def submit_pass(self, game_id: str) -> bool:
        return True

    async def resign(self, game_id: str) -> None:
        return None


class MockSessionManager:
    """Not exercised by these tests — only connect_platform + the callback are used."""


def make_manager():
    store = FakeCredentialStore()
    pm = PlatformManager(session_manager=MockSessionManager(), credential_store=store)
    return pm, store


async def test_owner_recorded_and_persisted_on_refresh():
    pm, store = make_manager()
    adapter = StubAdapter()
    pm.register_adapter(adapter)

    creds = PlatformCredentials("golaxy", "13800138000", {"access_token": "OLD", "refresh_token": "R1"})
    success = await pm.connect_platform("golaxy", creds, user_id=7)
    assert success is True

    await adapter._emit("token_refreshed", {"access_token": "NEW", "refresh_token": "R2"})

    saved = store.load_credentials(7, "golaxy")
    assert saved is not None
    assert saved.auth_data["access_token"] == "NEW"
    assert saved.auth_data["refresh_token"] == "R2"


async def test_merge_preserves_existing_keys():
    pm, store = make_manager()
    adapter = StubAdapter()
    pm.register_adapter(adapter)

    creds = PlatformCredentials(
        "golaxy", "13800138000", {"access_token": "OLD", "refresh_token": "R1", "user_code": "U"}
    )
    await pm.connect_platform("golaxy", creds, user_id=7)

    await adapter._emit("token_refreshed", {"access_token": "NEW", "refresh_token": "R2"})

    saved = store.load_credentials(7, "golaxy")
    assert saved.auth_data["access_token"] == "NEW"
    assert saved.auth_data["refresh_token"] == "R2"
    assert saved.auth_data["user_code"] == "U"


async def test_unknown_platform_skipped_no_raise():
    pm, store = make_manager()

    # No connect_platform call was ever made for "unknown" -> no recorded owner.
    await pm._on_token_refreshed("unknown", {"access_token": "X"})

    assert store.load_credentials(7, "unknown") is None
    assert store._store == {}


# --- Finding A: initial connect must persist the RESULTING tokens, not the ---
# --- transient login secret (e.g. sms_code) that connect() exchanges away. ---


class GolaxyLikeAdapter(StubAdapter):
    """Simulates Golaxy: connect() exchanges a one-time sms_code for tokens that
    live only in the adapter; get_auth_data() exposes them (as GolaxyAdapter does)."""

    def __init__(self):
        super().__init__()
        self._auth: dict = {}

    async def connect(self, credentials: PlatformCredentials) -> bool:
        if credentials.auth_data.get("sms_code"):
            # sms_code -> tokens (the real adapter stores these on its REST client)
            self._auth = {"access_token": "AT", "refresh_token": "RT", "user_code": None}
        self._connected = True
        return True

    def get_auth_data(self) -> dict:
        return dict(self._auth)


class OgsLikeAdapter(StubAdapter):
    """An adapter WITHOUT get_auth_data (like OGS) — must keep the old behavior."""

    platform_name = "ogs"


async def test_initial_connect_persists_real_token_not_sms_code():
    pm, store = make_manager()
    adapter = GolaxyLikeAdapter()
    pm.register_adapter(adapter)

    creds = PlatformCredentials("golaxy", "13800138000", {"sms_code": "123456"})
    assert await pm.connect_platform("golaxy", creds, user_id=7) is True

    saved = store.load_credentials(7, "golaxy")
    assert saved is not None
    # The exchanged tokens must be persisted so a restart can reconnect without a fresh SMS.
    assert saved.auth_data.get("access_token") == "AT"
    assert saved.auth_data.get("refresh_token") == "RT"
    # None-valued fields (user_code) are not written over anything.
    assert "user_code" not in saved.auth_data or saved.auth_data["user_code"]


async def test_initial_connect_without_get_auth_data_saves_input_unchanged():
    pm, store = make_manager()
    adapter = OgsLikeAdapter()
    pm.register_adapter(adapter)

    creds = PlatformCredentials("ogs", "player", {"password": "pw"})
    assert await pm.connect_platform("ogs", creds, user_id=9) is True

    saved = store.load_credentials(9, "ogs")
    assert saved is not None
    # No get_auth_data -> behavior unchanged: the input credentials are stored as-is.
    assert saved.auth_data == {"password": "pw"}
