"""Local-to-central room identities for a physical SmartBox PvP game."""

from __future__ import annotations

from dataclasses import dataclass
from threading import RLock


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

    def revoke_generation(self, generation: int) -> list[PvpBoxRoom]:
        with self._lock:
            rooms = [room for (room_generation, _), room in self._by_central.items() if room_generation == generation]
            for room in rooms:
                self._by_central.pop((generation, room.central_session_id), None)
                self._by_local.pop((generation, room.local_session_id), None)
            return rooms
