"""Tests for GolaxyAdapter.connect's SMS-code login branch.

The network is mocked at the GolaxyRestClient boundary (login_sms / login_password
as AsyncMock) so these tests never touch httpx. Covers: SMS login success (emits
token_refreshed once), SMS login failure, the password-path regression when no
sms_code is present, and the all-empty auth_data failure case.

Tests are async (asyncio_mode=auto in pyproject.toml).
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from katrain.web.platforms.golaxy.adapter import GolaxyAdapter
from katrain.web.platforms.models import PlatformCredentials


def recorder():
    """Return (events_list, async_callback) for capturing emitted events."""
    events: list = []

    async def cb(*args):
        events.append(args)

    return events, cb


async def test_sms_login_success():
    adapter = GolaxyAdapter()
    adapter._rest.login_sms = AsyncMock(return_value={"access_token": "tok", "refresh_token": "ref"})

    refreshed, refreshed_cb = recorder()
    adapter.on_token_refreshed(refreshed_cb)

    creds = PlatformCredentials("golaxy", "13800138000", {"sms_code": "1234"})
    result = await adapter.connect(creds)

    assert result is True
    assert adapter.is_connected is True
    adapter._rest.login_sms.assert_awaited_once_with("13800138000", "1234")
    assert len(refreshed) == 1


async def test_sms_login_failure():
    adapter = GolaxyAdapter()
    adapter._rest.login_sms = AsyncMock(side_effect=RuntimeError("bad code"))

    creds = PlatformCredentials("golaxy", "13800138000", {"sms_code": "wrong"})
    result = await adapter.connect(creds)

    assert result is False
    assert adapter.is_connected is False


async def test_password_path_still_taken_without_sms_code():
    """Regression: no sms_code in auth_data -> falls through to password login."""
    adapter = GolaxyAdapter()
    adapter._rest.login_sms = AsyncMock()
    adapter._rest.login_password = AsyncMock(return_value={"access_token": "tok", "refresh_token": "ref"})

    creds = PlatformCredentials("golaxy", "13800138000", {"password": "pw"})
    result = await adapter.connect(creds)

    assert result is True
    assert adapter.is_connected is True
    adapter._rest.login_password.assert_awaited_once_with("13800138000", "pw")
    adapter._rest.login_sms.assert_not_awaited()


async def test_no_token_no_sms_no_password_returns_false():
    adapter = GolaxyAdapter()

    creds = PlatformCredentials("golaxy", "13800138000", {})
    result = await adapter.connect(creds)

    assert result is False
    assert adapter.is_connected is False
