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
        self._sockets: set[Any] = set()

    def authorize_bridge(self, client_host: str | None, presented_key: str | None) -> bool:
        if client_host not in LOOPBACK_HOSTS or not presented_key:
            return False
        try:
            expected = self.bridge_key_path.read_text(encoding="utf-8").strip()
        except OSError:
            return False
        return bool(expected) and hmac.compare_digest(expected, presented_key)

    async def activate(self, generation: int) -> None:
        """换一代 = 换一个人。**代号只许往前走。**

        代号是上一个人的凭据失效的唯一依据(`validates` 只认当前这一代)。倒退或复用一个代号,
        等于把上一个人的 cookie 重新变成有效的 —— 那个人还能读到现在这个人的成长数据。

        今天 launcher 发的代号是 `max(持久高水位, 上一代) + 1`(smartbox-software
        `setup-wizard/app/services/box_identity.py`),严格递增。但那是**另一个仓**的行为:
        这里不该把自己的安全性建在它身上,闸要建在操作数所在的这一侧。

        ⚠️ `active_generation` 只在内存里:服务一重启它就是 None,此时任何正整数都接受
        (重启已经让所有旧 cookie 失效了,没有可被复活的东西)。
        """
        if isinstance(generation, bool) or generation <= 0:
            raise ValueError("generation must be a positive integer")
        if self.active_generation is not None and generation < self.active_generation:
            raise ValueError("generation must not go backwards")
        if self.active_generation is not None and generation != self.active_generation:
            await self._close_sockets("Box generation replaced")
        self.active_generation = generation

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
