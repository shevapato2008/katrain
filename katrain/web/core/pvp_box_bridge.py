"""Local-to-central room identities for a physical SmartBox PvP game."""

from __future__ import annotations

from dataclasses import dataclass
from threading import RLock
from typing import Any, Callable
from urllib.parse import urlsplit

import httpx
from websockets.asyncio.client import connect as ws_connect


@dataclass(frozen=True)
class PvpBoxRoom:
    generation: int
    central_user_id: int
    central_session_id: str
    local_session_id: str
    local_user_id: int
    my_color: str


class PvpBoxRooms:
    """Keep active room mappings independent of short-lived lobby sockets."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._by_central: dict[tuple[int, str], PvpBoxRoom] = {}
        self._by_local: dict[tuple[int, str], PvpBoxRoom] = {}

    def attach(
        self,
        generation: int,
        central_user_id: int,
        central_session_id: str,
        local_session_id: str,
        local_user_id: int,
        my_color: str,
    ) -> PvpBoxRoom:
        if type(generation) is not int or generation <= 0:
            raise ValueError("generation must be positive")
        if type(central_user_id) is not int or central_user_id <= 0:
            raise ValueError("central user ID must be positive")
        if type(local_user_id) is not int or local_user_id <= 0:
            raise ValueError("local user ID must be positive")
        if not central_session_id or not local_session_id:
            raise ValueError("room IDs must be present")
        if my_color not in ("B", "W") or type(my_color) is not str:
            raise ValueError("my color must be B or W")

        central_key = (generation, central_session_id)
        local_key = (generation, local_session_id)
        with self._lock:
            old = self._by_central.get(central_key)
            if old is not None:
                if (old.local_session_id, old.central_user_id, old.local_user_id, old.my_color) != (
                    local_session_id,
                    central_user_id,
                    local_user_id,
                    my_color,
                ):
                    raise ValueError("central room is already mapped differently")
                return old
            if local_key in self._by_local:
                raise ValueError("local room is already mapped differently")
            room = PvpBoxRoom(
                generation, central_user_id, central_session_id, local_session_id, local_user_id, my_color
            )
            self._by_central[central_key] = room
            self._by_local[local_key] = room
            return room

    def for_central(self, generation: int, session_id: str) -> PvpBoxRoom | None:
        with self._lock:
            return self._by_central.get((generation, session_id))

    def for_local(self, generation: int, session_id: str) -> PvpBoxRoom | None:
        with self._lock:
            return self._by_local.get((generation, session_id))

    def lobby_disconnected(self, generation: int) -> None:
        """A route change closes the lobby socket; the active game keeps its mapping."""

    def end_room(self, generation: int, central_session_id: str) -> PvpBoxRoom | None:
        with self._lock:
            room = self._by_central.pop((generation, central_session_id), None)
            if room is not None:
                self._by_local.pop((generation, room.local_session_id), None)
            return room

    def discard_local(self, local_session_id: str) -> None:
        """Forget a mirror after SessionManager removes or expires it."""
        with self._lock:
            for key, room in list(self._by_local.items()):
                if room.local_session_id == local_session_id:
                    self._by_local.pop(key, None)
                    self._by_central.pop((room.generation, room.central_session_id), None)

    def revoke_generation(self, generation: int) -> list[PvpBoxRoom]:
        with self._lock:
            rooms = [room for (room_generation, _), room in self._by_central.items() if room_generation == generation]
            for room in rooms:
                self._by_central.pop((generation, room.central_session_id), None)
                self._by_local.pop((generation, room.local_session_id), None)
            return rooms


class PvpBoxAuthError(RuntimeError):
    """The local generation or its cloud credential no longer belongs to this user."""


class PvpBoxRemoteError(RuntimeError):
    """The central server did not supply an authoritative answer."""


class PvpBoxBridge:
    """Narrow authenticated projections between one box user and the central lobby."""

    def __init__(
        self,
        remote: Any,
        box_sso: Any,
        rooms: PvpBoxRooms,
        make_mirror: Callable[[int, str, str], str],
        discard_mirror: Callable[[str], None] | None = None,
    ):
        self.remote = remote
        self.box_sso = box_sso
        self.rooms = rooms
        self.make_mirror = make_mirror
        self.discard_mirror = discard_mirror
        self._create_lock = RLock()

    @staticmethod
    def newer_state(current: dict | None, incoming: dict) -> dict:
        """Do not roll a mirror back when a move reply races a newer room frame."""
        if not current or current.get("game_id") != incoming.get("game_id"):
            return incoming
        old_index, new_index = current.get("current_node_index"), incoming.get("current_node_index")
        if type(old_index) is int and type(new_index) is int and old_index > new_index:
            return current
        return incoming

    def check_user(self, generation: int, local_user_id: int) -> None:
        if (
            not self.box_sso.validates(generation)
            or self.box_sso.active_user_id != local_user_id
            or str(self.remote.bound_user_id) != str(local_user_id)
            or not self.remote.is_authenticated
        ):
            raise PvpBoxAuthError("Box session is no longer current")

    async def request(
        self,
        generation: int,
        local_user_id: int,
        method: str,
        path: str,
        *,
        json: Any = None,
        params: dict | None = None,
    ):
        self.check_user(generation, local_user_id)
        try:
            kwargs = {"json": json} if json is not None else {}
            if params is not None:
                kwargs["params"] = params
            response = await self.remote._request(method, path, **kwargs)
        except (httpx.HTTPError, TimeoutError) as exc:
            raise PvpBoxRemoteError("Central lobby disconnected") from exc
        self.check_user(generation, local_user_id)
        if response.status_code in (401, 403):
            raise PvpBoxAuthError("Central credential expired")
        if response.status_code >= 500:
            raise PvpBoxRemoteError("Central lobby unavailable")
        return response

    async def get_json(self, generation: int, local_user_id: int, path: str):
        response = await self.request(generation, local_user_id, "GET", path)
        if not response.is_success:
            raise PvpBoxRemoteError(f"Central lobby returned HTTP {response.status_code}")
        return response.json()

    async def identity(self, generation: int, local_user_id: int) -> dict[str, int]:
        user = await self.get_json(generation, local_user_id, "/api/v1/auth/me")
        user_id = user.get("id") if isinstance(user, dict) else None
        if type(user_id) is not int or user_id <= 0:
            raise PvpBoxRemoteError("Central identity unavailable")
        return {"user_id": user_id}

    async def upstream_websocket(self, generation: int, local_user_id: int, path: str):
        # A REST identity read refreshes an expired access token before the WebSocket
        # handshake. The cloud token remains in this process, never in the box URL.
        await self.identity(generation, local_user_id)
        self.check_user(generation, local_user_id)
        token = self.remote._access_token
        if not token:
            raise PvpBoxAuthError("Central credential unavailable")
        target = urlsplit(self.remote.base_url)
        if target.scheme not in ("http", "https") or not target.netloc or not path.startswith("/"):
            raise PvpBoxRemoteError("Central WebSocket URL is invalid")
        origin = f"{target.scheme}://{target.netloc}"
        url = f"{'wss' if target.scheme == 'https' else 'ws'}://{target.netloc}{path}"
        return ws_connect(url, origin=origin, additional_headers={"Cookie": f"sb_token={token}"}, open_timeout=10)

    def _room(self, generation: int, local_user_id: int, central_user_id: int, central_session_id: str, color: str):
        self.check_user(generation, local_user_id)
        with self._create_lock:
            room = self.rooms.for_central(generation, central_session_id)
            if room is not None:
                if (room.central_user_id, room.local_user_id, room.my_color) != (central_user_id, local_user_id, color):
                    raise PvpBoxAuthError("Room belongs to another user")
                return room
            local_session_id = self.make_mirror(local_user_id, color, central_session_id)
            try:
                self.check_user(generation, local_user_id)
                return self.rooms.attach(
                    generation, central_user_id, central_session_id, local_session_id, local_user_id, color
                )
            except Exception:
                if self.discard_mirror is not None:
                    self.discard_mirror(local_session_id)
                raise

    def revoke_generation(self, generation: int) -> list[PvpBoxRoom]:
        with self._create_lock:
            return self.rooms.revoke_generation(generation)

    def rewrite_match(self, generation: int, local_user_id: int, central_user_id: int, message: dict) -> dict:
        room = self._room(generation, local_user_id, central_user_id, message["session_id"], message["my_color"])
        return {**message, "session_id": room.local_session_id, "central_session_id": room.central_session_id}

    def rewrite_active_games(
        self, generation: int, local_user_id: int, central_user_id: int, games: list[dict]
    ) -> list[dict]:
        self.check_user(generation, local_user_id)
        result = []
        for game in games:
            color = (
                "B"
                if game.get("player_b_id") == central_user_id
                else "W" if game.get("player_w_id") == central_user_id else None
            )
            if color is None:
                result.append(game)
                continue
            room = self._room(generation, local_user_id, central_user_id, game["session_id"], color)
            result.append({**game, "session_id": room.local_session_id, "central_session_id": room.central_session_id})
        return result

    def rewrite_state(self, generation: int, local_session_id: str, state: dict) -> dict:
        room = self.rooms.for_local(generation, local_session_id)
        if room is None:
            raise PvpBoxAuthError("Room is no longer current")
        self.check_user(generation, room.local_user_id)
        return {**state, "game_type": "pvp_lobby", "platform_my_color": room.my_color, "my_color": room.my_color}

    async def fetch_state(self, generation: int, local_session_id: str) -> dict:
        room = self.rooms.for_local(generation, local_session_id)
        if room is None:
            raise PvpBoxAuthError("Room is no longer current")
        response = await self.request(
            generation, room.local_user_id, "GET", "/api/state", params={"session_id": room.central_session_id}
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("session_id") != room.central_session_id or not isinstance(payload.get("state"), dict):
            raise PvpBoxRemoteError("Central state response is invalid")
        return {
            **payload,
            "session_id": room.local_session_id,
            "state": self.rewrite_state(generation, room.local_session_id, payload["state"]),
        }

    async def forward_move(self, generation: int, local_session_id: str, *, coords: list[int] | None) -> dict:
        return await self.forward_action(
            generation, local_session_id, "POST", "/api/move", {"coords": coords, "pass_move": coords is None}
        )

    async def forward_action(
        self, generation: int, local_session_id: str, method: str, path: str, body: dict | None = None
    ) -> dict:
        room = self.rooms.for_local(generation, local_session_id)
        if room is None:
            raise PvpBoxAuthError("Room is no longer current")
        if method == "GET":
            response = await self.request(
                generation, room.local_user_id, method, path, params={"session_id": room.central_session_id}
            )
        else:
            response = await self.request(
                generation,
                room.local_user_id,
                method,
                path,
                json={**(body or {}), "session_id": room.central_session_id},
            )
        response.raise_for_status()
        payload = response.json()
        if (
            not isinstance(payload, dict)
            or payload.get("session_id", room.central_session_id) != room.central_session_id
        ):
            raise PvpBoxRemoteError("Central action response is invalid")
        result = {**payload}
        if "session_id" in result:
            result["session_id"] = room.local_session_id
        if isinstance(result.get("state"), dict):
            result["state"] = self.rewrite_state(generation, room.local_session_id, result["state"])
        return result
