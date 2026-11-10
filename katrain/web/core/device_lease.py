"""Nonblocking ownership of a local camera or serial device.

Processes must share SMARTBOX_DEVICE_LEASE_DIR, or the same HOME when unset.
"""

from __future__ import annotations

import errno
import fcntl
import hashlib
import os
import sys
from pathlib import Path


class DeviceBusy(RuntimeError):
    """The configured device is already owned by another service."""


class DeviceLease:
    def __init__(self, handle):
        self._handle = handle

    @classmethod
    def acquire(cls, kind: str, device_id: int | str) -> "DeviceLease":
        configured_dir = os.environ.get("SMARTBOX_DEVICE_LEASE_DIR")
        if configured_dir:
            lease_dir = Path(configured_dir)
            if not lease_dir.is_absolute():
                raise ValueError("SMARTBOX_DEVICE_LEASE_DIR must be absolute")
            # SmartBox has one camera and one LED controller. A kind-wide lock
            # survives alias creation and also blocks direct /dev node callers.
            lock_name = f"{kind}-device.lock"
        else:
            lease_dir = Path.home() / ".katrain" / "device-leases"
            identity = str(device_id)
            # Preserve multi-device behavior for non-SmartBox installations.
            if kind == "camera" and sys.platform == "linux" and isinstance(device_id, int) and device_id > 9:
                identity = f"/dev/video{device_id}"
            if identity.startswith("/"):
                identity = str(Path(identity).resolve())
            digest = hashlib.sha256(f"{kind}\0{identity}".encode("utf-8")).hexdigest()
            lock_name = f"{kind}-{digest}.lock"
        lease_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        handle = (lease_dir / lock_name).open("a+b")
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
