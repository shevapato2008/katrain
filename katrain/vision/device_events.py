"""Optional processed-udev notifications; camera lifecycle stays with its owner."""

from __future__ import annotations

import logging
import os
import select
import subprocess
import sys
import threading
from collections.abc import Callable

logger = logging.getLogger(__name__)


class UdevDeviceMonitor:
    """Watch one configured camera alias or its recorded capture DEVNAME.

    A monitor is used for one hub lifecycle. Failure leaves timer reconciliation
    available; this helper never respawns the child or touches a capture handle.
    """

    START_TIMEOUT_S = 0.5
    STOP_TIMEOUT_S = 0.5
    MAX_LINE_BYTES = 4096
    MAX_RECORD_BYTES = 32768
    ARGV = ["udevadm", "monitor", "--udev", "--subsystem-match=video4linux", "--property"]

    def __init__(self, device_path: int | str, callback: Callable[[str], None]):
        self._path = f"/dev/video{device_path}" if isinstance(device_path, int) else device_path
        self._callback = callback
        self._present = os.path.isabs(self._path) and os.path.exists(self._path)
        self._devname = os.path.realpath(self._path) if self._present else None
        self._devpath: str | None = None
        self._last_add: tuple[str, str, tuple[int, int, int] | None] | None = None
        self._lock = threading.Lock()
        self._callback_lock = threading.Lock()
        self._stop = threading.Event()
        self._ready = threading.Event()
        self._subscribed = False
        self._started = False
        self._process = None
        self._thread: threading.Thread | None = None

    def start(self) -> bool:
        """Subscribe before initial reconciliation, or return False for fallback."""
        with self._lock:
            if self._started or self._stop.is_set():
                return self._subscribed and not self._stop.is_set()
            self._started = True
            if sys.platform != "linux" or not os.path.isabs(self._path):
                return False
            try:
                self._process = subprocess.Popen(
                    self.ARGV, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=0
                )
                self._thread = threading.Thread(target=self._run, daemon=True, name="camera-udev")
                self._thread.start()
            except (OSError, RuntimeError):
                logger.debug("Camera udev monitor unavailable; retaining timer recovery", exc_info=True)
                self._ready.set()
        self._ready.wait(self.START_TIMEOUT_S)
        if not self._subscribed or self._stop.is_set():
            self.stop()
            return False
        return True

    def stop(self) -> None:
        """Bound child shutdown and prevent callbacks after this method returns."""
        with self._callback_lock:
            self._stop.set()
            self._ready.set()
        with self._lock:
            process, thread = self._process, self._thread
            if process is not None and process.poll() is None:
                try:
                    process.terminate()
                except OSError:
                    pass
        if thread is not None and thread.ident is not None and thread is not threading.current_thread():
            thread.join(self.STOP_TIMEOUT_S)
        if process is not None:
            try:
                process.wait(timeout=self.STOP_TIMEOUT_S)
            except subprocess.TimeoutExpired:
                try:
                    process.kill()
                    process.wait(timeout=self.STOP_TIMEOUT_S)
                except (OSError, subprocess.TimeoutExpired):
                    pass
            if thread is None or not thread.is_alive():
                process.stdout.close()

    def _run(self) -> None:
        process = self._process
        line = bytearray()
        properties: dict[str, str] = {}
        record_bytes = 0
        discard = False
        try:
            while not self._stop.is_set():
                readable, _, _ = select.select([process.stdout], [], [], 0.1)
                if not readable:
                    if process.poll() is not None:
                        return
                    continue
                chunk = os.read(process.stdout.fileno(), 4096)
                if not chunk:
                    return
                for value in chunk:
                    if value != 10:
                        if len(line) < self.MAX_LINE_BYTES:
                            line.append(value)
                        else:
                            discard = True
                        continue
                    text = line.decode("utf-8", errors="replace").strip()
                    line.clear()
                    if not text:
                        if not discard:
                            self._handle_record(properties)
                        properties = {}
                        record_bytes = 0
                        discard = False
                        continue
                    # udevadm emits its banner after enabling the udev listener.
                    if text.startswith("UDEV") and text[4:].lstrip().startswith(("-", "[")):
                        self._subscribed = True
                        self._ready.set()
                    record_bytes += len(text)
                    if record_bytes > self.MAX_RECORD_BYTES:
                        discard = True
                    if not discard and "=" in text:
                        key, value = text.split("=", 1)
                        if key in {"ACTION", "SUBSYSTEM", "DEVNAME", "DEVLINKS", "DEVPATH", "ID_V4L_CAPABILITIES"}:
                            properties[key] = value
        except (OSError, ValueError):
            logger.debug("Camera udev monitor stopped; retaining timer recovery", exc_info=True)
        finally:
            self._ready.set()
            # Reap an exited optional child immediately; no restart loop is needed.
            if process.poll() is not None:
                process.wait(timeout=self.STOP_TIMEOUT_S)
                process.stdout.close()

    def _handle_record(self, properties: dict[str, str]) -> None:
        action = properties.get("ACTION")
        if action not in {"add", "remove"} or properties.get("SUBSYSTEM") != "video4linux":
            return
        capabilities = properties.get("ID_V4L_CAPABILITIES", "")
        if capabilities and "capture" not in capabilities.split(":"):
            return
        devname = properties.get("DEVNAME", "")
        devpath = properties.get("DEVPATH", "")
        if not devname.startswith("/dev/video") or not devname[len("/dev/video") :].isdigit():
            return
        if action == "add":
            links = properties.get("DEVLINKS", "").split()
            alias_matches = os.path.exists(self._path) and os.path.realpath(self._path) == devname
            if self._path not in links and devname != self._path and not alias_matches:
                return
            try:
                node = os.stat(devname)
                node_identity = node.st_dev, node.st_ino, node.st_rdev
            except OSError:
                node_identity = None
            identity = devname, devpath, node_identity
            if self._present and self._last_add == identity:
                return
            self._devname, self._devpath = devname, devpath
            self._present, self._last_add = True, identity
        else:
            if not self._present or devname != self._devname:
                return
            if self._devpath and devpath and self._devpath != devpath:
                return
            self._present, self._last_add = False, None
        with self._callback_lock:
            if not self._stop.is_set():
                self._callback(action)
