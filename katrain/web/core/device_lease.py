"""Nonblocking, process-wide ownership of a local camera or serial device."""

from __future__ import annotations

import errno
import fcntl
import hashlib
from pathlib import Path


class DeviceBusy(RuntimeError):
    """The configured device is already owned by another service."""


class DeviceLease:
    def __init__(self, handle):
        self._handle = handle

    @classmethod
    def acquire(cls, kind: str, device_id: int | str) -> "DeviceLease":
        identity = str(device_id)
        if identity.startswith("/"):
            identity = str(Path(identity).resolve())
        digest = hashlib.sha256(f"{kind}\0{identity}".encode("utf-8")).hexdigest()
        lease_dir = Path.home() / ".katrain" / "device-leases"
        lease_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        handle = (lease_dir / f"{kind}-{digest}.lock").open("a+b")
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            handle.close()
            if exc.errno in (errno.EACCES, errno.EAGAIN):
                raise DeviceBusy(f"{kind} device {device_id} is busy (occupied)") from exc
            raise
        return cls(handle)

    def release(self) -> None:
        if self._handle is not None:
            fcntl.flock(self._handle.fileno(), fcntl.LOCK_UN)
            self._handle.close()
            self._handle = None
