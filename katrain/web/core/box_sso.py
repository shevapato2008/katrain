"""Strict SmartBox bridge state and browser credential selection."""

from __future__ import annotations

import hmac
from pathlib import Path
from typing import Any

from katrain.web.core.config import settings

BRIDGE_KEY_HEADER = "x-smartbox-bridge-key"
GO_COOKIE_NAME = "sb_go_token"
LOOPBACK_HOSTS = {"127.0.0.1", "::1"}

# Reserved local account for guest mode (see superpowers/tracks/box-sso-2026-07-13
# guest-mode spec). Nobody may register or log in as this username directly --
# only the guest-bootstrap bridge endpoint may mint tokens for it.
GUEST_USERNAME = "guest"


def is_guest_user(user: Any) -> bool:
    return user is not None and getattr(user, "username", None) == GUEST_USERNAME


def strict_box_sso_enabled() -> bool:
    return settings.KATRAIN_MODE == "board" and settings.KATRAIN_BOX_SSO


class BoxSSOState:
    def __init__(self, bridge_key_path: str):
        self.bridge_key_path = Path(bridge_key_path)
        self.active_generation: int | None = None
        # Which local user_id this box generation was activated for -- set by
        # bootstrap/guest-bootstrap, read (and cleared) by the endpoint layer
        # on box_sso_clear so it can release that user's platform connections
        # (see PlatformManager.release_user). None if never set (e.g. a box
        # running an older client, or a generation activated before this was
        # added) -- the caller must treat that as "nothing to release", not
        # guess a user.
        self.active_user_id: int | None = None
        self._sockets: set[Any] = set()

    def authorize_bridge(self, client_host: str | None, presented_key: str | None) -> bool:
        if client_host not in LOOPBACK_HOSTS or not presented_key:
            return False
        try:
            expected = self.bridge_key_path.read_text(encoding="utf-8").strip()
        except OSError:
            return False
        return bool(expected) and hmac.compare_digest(expected, presented_key)

    async def activate(self, generation: int, user_id: int | None = None) -> None:
        if isinstance(generation, bool) or generation <= 0:
            raise ValueError("generation must be a positive integer")
        if self.active_generation is not None and generation != self.active_generation:
            await self._close_sockets("Box generation replaced")
        self.active_generation = generation
        self.active_user_id = user_id

    def validates(self, generation: Any) -> bool:
        return (
            isinstance(generation, int)
            and not isinstance(generation, bool)
            and generation == self.active_generation
        )

    def register_socket(self, websocket: Any) -> None:
        self._sockets.add(websocket)

    def discard_socket(self, websocket: Any) -> None:
        self._sockets.discard(websocket)

    async def clear(self, generation: int) -> bool:
        if not self.validates(generation):
            return False
        self.active_generation = None
        self.active_user_id = None
        await self._close_sockets("Box session revoked")
        return True

    async def _close_sockets(self, reason: str) -> None:
        sockets = tuple(self._sockets)
        self._sockets.clear()
        for websocket in sockets:
            try:
                await websocket.close(code=1008, reason=reason)
            except Exception:
                pass


def resolve_http_token(request: Any, header_token: str | None) -> str | None:
    if strict_box_sso_enabled():
        return request.cookies.get(GO_COOKIE_NAME)
    return request.cookies.get("sb_token") or header_token


def resolve_websocket_token(websocket: Any) -> str | None:
    expected_origin = f"{'https' if websocket.url.scheme == 'wss' else 'http'}://{websocket.url.netloc}"
    if strict_box_sso_enabled():
        if websocket.headers.get("origin") != expected_origin:
            return None
        return websocket.cookies.get(GO_COOKIE_NAME)
    if "token" in websocket.query_params:
        return websocket.query_params.get("token")
    if websocket.headers.get("origin") != expected_origin:
        return None
    return websocket.cookies.get("sb_token")
