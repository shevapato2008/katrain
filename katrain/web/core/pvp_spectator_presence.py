"""Ephemeral, per-game observer identities shared by WebSocket and HTTP readers."""

import threading
import time
from typing import Callable, Optional


class PvpSpectatorPresence:
    HTTP_TTL_SECONDS = 10.0

    def __init__(self, clock: Callable[[], float] = time.monotonic):
        self._clock = clock
        self._lock = threading.Lock()
        self._http = {}
        self._sockets = {}
        self._published_count = 0
        self._expiry_handle = None
        self._closed = False

    @staticmethod
    def _valid_user(user_id):
        return type(user_id) is int and user_id > 0

    def touch_http(self, user_id):
        if self._valid_user(user_id):
            with self._lock:
                if not self._closed:
                    self._http[user_id] = self._clock() + self.HTTP_TTL_SECONDS

    def join_socket(self, socket, user_id):
        if self._valid_user(user_id):
            with self._lock:
                if not self._closed:
                    self._sockets[socket] = user_id

    def leave_socket(self, socket):
        with self._lock:
            self._sockets.pop(socket, None)

    def count(self, seat_ids, live_sockets) -> int:
        with self._lock:
            now = self._clock()
            self._http = {user_id: deadline for user_id, deadline in self._http.items() if deadline > now}
            self._sockets = {socket: user_id for socket, user_id in self._sockets.items() if socket in live_sockets}
            observers = set(self._http).union(self._sockets.values())
            return len(observers.difference(seat_ids))

    def mark_published(self, count: int) -> bool:
        """Compare with the last event, even if a state/list read already pruned expiry."""
        with self._lock:
            changed = count != self._published_count
            self._published_count = count
            return changed

    def next_deadline(self) -> Optional[float]:
        with self._lock:
            return min(self._http.values()) if self._http else None

    def expiry_delay(self) -> Optional[float]:
        with self._lock:
            return max(0.0, min(self._http.values()) - self._clock()) if self._http else None

    def set_expiry_handle(self, handle):
        with self._lock:
            if self._expiry_handle is not None:
                self._expiry_handle.cancel()
            if self._closed:
                if handle is not None:
                    handle.cancel()
            else:
                self._expiry_handle = handle

    def clear(self):
        with self._lock:
            self._closed = True
            self._http.clear()
            self._sockets.clear()
            if self._expiry_handle is not None:
                self._expiry_handle.cancel()
                self._expiry_handle = None
