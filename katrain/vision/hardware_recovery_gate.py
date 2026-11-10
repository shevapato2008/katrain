"""Small admission barrier shared by physical transactions and USB recovery."""

from __future__ import annotations

import threading


class _Token:
    def __init__(self, gate, recovery):
        self._gate = gate
        self._recovery = recovery
        self._closed = False

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def close(self):
        gate = self._gate
        with gate._lock:
            if self._closed:
                return
            self._closed = True
            if self._recovery:
                if gate._recovery is self:
                    gate._recovery = None
            else:
                gate._users -= 1


class HardwareRecoveryGate:
    def __init__(self):
        self._lock = threading.Lock()
        self._users = 0
        self._recovery = None
        self._generation = 0

    @property
    def active(self):
        with self._lock:
            return self._recovery is not None

    @property
    def generation(self):
        with self._lock:
            return self._generation

    def try_use(self):
        with self._lock:
            if self._recovery is not None:
                return None
            self._users += 1
            return _Token(self, False)

    def try_recovery(self):
        with self._lock:
            if self._recovery is not None or self._users:
                return None
            self._generation += 1
            self._recovery = _Token(self, True)
            return self._recovery
