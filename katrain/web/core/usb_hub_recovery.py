"""One-attempt USB recovery episodes, driven by CameraHub's existing loop."""

from __future__ import annotations

import fcntl
import json
import logging
import math
import os
import stat
import subprocess
import tempfile
import threading
import time
import uuid
from pathlib import Path

log = logging.getLogger(__name__)


def _checked_file(fd):
    info = os.fstat(fd)
    if (
        not stat.S_ISREG(info.st_mode)
        or info.st_uid != os.geteuid()
        or stat.S_IMODE(info.st_mode) != 0o600
        or info.st_nlink != 1
    ):
        raise ValueError("Unsafe USB recovery state/lock file")


def _parent(path):
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    info = path.parent.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) & 0o022:
        raise ValueError("Unsafe USB recovery state directory")


def _lock_operation(path):
    _parent(path)
    if os.path.lexists(path):
        fd = os.open(path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW | os.O_NONBLOCK)
        try:
            _checked_file(fd)
        finally:
            os.close(fd)
    fd = os.open(path.parent / "operation.lock", os.O_RDWR | os.O_CREAT | os.O_CLOEXEC | os.O_NOFOLLOW, 0o600)
    try:
        _checked_file(fd)
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return fd
    except BaseException:
        os.close(fd)
        raise


class UsbHubRecovery:
    STABLE_SECONDS = 10.0
    COOLDOWN_SECONDS = 60.0
    SETTLE_SECONDS = 20.0
    HEALTHY_SECONDS = 30.0
    OPERATION_SECONDS = 8.0

    def __init__(self, adapter, camera, led, vision, gate, state_path, *, clock=time.monotonic, wall_clock=time.time):
        self.adapter, self.camera, self.led, self.vision, self.gate = adapter, camera, led, vision, gate
        self.state_path = Path(state_path)
        self.clock, self.wall_clock = clock, wall_clock
        self._mutex = threading.Lock()
        # Only final launch admission and handle registration share this lock.
        # Slow USB snapshots never hold the stop/launch ownership boundary.
        self._launch_lock = threading.Lock()
        self._stopped = threading.Event()
        self._operation = None
        self._operation_lock = None
        self._token = None
        self._quiet = []
        self._candidate = None
        self._candidate_since = None
        self._last_tick = None
        self._operation_started = None
        self._killed = False
        self._finished_at = None
        self._settle_until = None
        self._healthy_since = None
        self._physical = {}
        self._external_removed = set()
        self._disabled = False
        self._state = {"schema": 1, "latched": False, "last_attempt": None, "inflight": False, "attempt_id": None}
        try:
            if os.path.lexists(self.state_path):
                _parent(self.state_path)
                fd = os.open(self.state_path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW | os.O_NONBLOCK)
                try:
                    _checked_file(fd)
                    with os.fdopen(fd, "r", closefd=False) as stream:
                        state = json.load(stream)
                finally:
                    os.close(fd)
                self._validate_state(state)
                self._state = state
                # A previous process's reset may still be live. Preserve the
                # episode, but allow owner open only through startup_allowed.
                if state["latched"]:
                    self._settle_until = self.clock() + self.SETTLE_SECONDS
            now = self.wall_clock()
            if (
                not math.isfinite(now)
                or now < 0
                or self._state["last_attempt"] is not None
                and now < self._state["last_attempt"]
            ):
                raise ValueError("USB recovery wall clock moved backwards")
        except (OSError, ValueError, TypeError, KeyError):
            self._disabled = True
            log.warning("USB automatic recovery disabled: invalid persistent state", exc_info=True)

    @staticmethod
    def _validate_state(state):
        if (
            not isinstance(state, dict)
            or set(state) != {"schema", "latched", "last_attempt", "inflight", "attempt_id"}
            or type(state["schema"]) is not int
            or state["schema"] != 1
        ):
            raise ValueError("Invalid USB recovery schema")
        if type(state["latched"]) is not bool or type(state["inflight"]) is not bool:
            raise ValueError("Invalid USB recovery episode flags")
        value = state["last_attempt"]
        if value is not None and (type(value) not in (int, float) or not math.isfinite(value) or value < 0):
            raise ValueError("Invalid USB recovery attempt time")
        attempt_id = state["attempt_id"]
        if attempt_id is not None and (
            not isinstance(attempt_id, str)
            or len(attempt_id) != 32
            or any(c not in "0123456789abcdef" for c in attempt_id)
        ):
            raise ValueError("Invalid USB recovery attempt id")
        if (state["latched"] or state["inflight"]) and (value is None or attempt_id is None):
            raise ValueError("Incomplete USB recovery episode")
        if state["inflight"] and not state["latched"]:
            raise ValueError("Inconsistent USB recovery episode")

    @staticmethod
    def startup_allowed(state_path):
        """Check the operation lock before every open; JSON validity is separate."""
        fd = None
        try:
            fd = _lock_operation(Path(state_path))
            return True
        except (OSError, ValueError):
            return False
        finally:
            if fd is not None:
                os.close(fd)

    def _persist(self, **changes):
        state = dict(self._state, **changes)
        self._validate_state(state)
        temp = None
        try:
            _parent(self.state_path)
            if os.path.lexists(self.state_path):
                fd = os.open(self.state_path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW | os.O_NONBLOCK)
                try:
                    _checked_file(fd)
                finally:
                    os.close(fd)
            fd, temp = tempfile.mkstemp(prefix=".state-", dir=self.state_path.parent)
            with os.fdopen(fd, "w") as stream:
                json.dump(state, stream, separators=(",", ":"), allow_nan=False)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp, self.state_path)
            temp = None
            directory = os.open(self.state_path.parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
            self._state = state
            return True
        except (OSError, ValueError):
            self._disabled = True
            log.warning("USB automatic recovery disabled: cannot persist episode", exc_info=True)
            return False
        finally:
            if temp is not None:
                try:
                    os.unlink(temp)
                except OSError:
                    pass

    @staticmethod
    def _candidates(snapshot):
        if not snapshot.valid or set(snapshot.ports) != {1, 2, 3, 4}:
            return ()
        # True disconnect of either target rules out a shared-hub reset.
        if not all(snapshot.ports[p].connected for p in (3, 4)):
            return ()
        if any(snapshot.ports[p].child_identity is None and not snapshot.ports[p].candidate for p in (3, 4)):
            return ()
        return tuple(p for p in (3, 4) if snapshot.ports[p].candidate)

    def _release_lock(self):
        if self._operation_lock is not None:
            os.close(self._operation_lock)
            self._operation_lock = None

    def _resume_owners(self):
        quiet, self._quiet = self._quiet, []
        # Release the owners before the worker so it can observe new frames.
        for owner in (self.camera, self.led, self.vision):
            if owner in quiet:
                try:
                    owner.end_usb_recovery()
                except Exception:
                    log.exception("Could not end USB owner pause")

    def _release_gate(self):
        if self._token is not None:
            self._token.close()
            self._token = None

    def _frame_ready(self):
        try:
            frame, _, timestamp = self.camera.read_frame_identified()
            return (
                frame is not None
                and isinstance(timestamp, (int, float))
                and math.isfinite(timestamp)
                and timestamp > self._finished_at
                and self.camera.is_connected()
            )
        except Exception:
            return False

    def _transport_ready(self):
        try:
            return bool(self.led.is_connected())
        except Exception:
            return False

    def _services_healthy(self):
        try:
            frame, _, timestamp = self.camera.read_frame_identified()
            return (
                frame is not None
                and isinstance(timestamp, (int, float))
                and math.isfinite(timestamp)
                and 0 <= self.clock() - timestamp <= 5.0
                and self.camera.is_connected()
                and self.led.is_connected()
                and self.led.board_status().get("connected") is True
            )
        except Exception:
            return False

    def _poll_operation(self, now, wait_budget=0.05):
        if self._operation is None:
            return
        try:
            code = self._operation.poll()
            if code is None and (self._stopped.is_set() or now - self._operation_started >= self.OPERATION_SECONDS):
                if not self._killed:
                    self._killed = True
                    self._operation.kill()
                try:
                    self._operation.wait(timeout=wait_budget)
                except (TimeoutError, subprocess.TimeoutExpired):
                    pass
                code = self._operation.poll()
            if code is None:
                return
        except OSError:
            # An unverified operation is still considered running.
            return
        self._operation = None
        self._finished_at = now
        self._settle_until = now + self.SETTLE_SECONDS
        self._physical.clear()
        self._external_removed.clear()
        self._persist(inflight=False)
        self._release_lock()
        self._resume_owners()
        if self._stopped.is_set():
            self._release_gate()

    def _maybe_rearm(self, snapshot, now):
        if not self._state["latched"] or self._operation is not None:
            return
        if not snapshot.valid or self._settle_until is not None and now < self._settle_until:
            self._healthy_since = None
            self._physical.clear()
            self._external_removed.clear()
            return
        # A stale inflight record is harmless only after the lock is verified free.
        lock = None
        try:
            lock = _lock_operation(self.state_path)
        except (OSError, ValueError):
            return
        try:
            # Do not let a stale coordinator rearm an episode recorded by a
            # different process after its own health observations began.
            fd = os.open(self.state_path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW | os.O_NONBLOCK)
            try:
                _checked_file(fd)
                with os.fdopen(fd, "r", closefd=False) as stream:
                    disk = json.load(stream)
                self._validate_state(disk)
            finally:
                os.close(fd)
            if disk != self._state:
                self._state = disk
                self._healthy_since = None
                self._physical.clear()
                self._external_removed.clear()
                self._settle_until = now + self.SETTLE_SECONDS
                return
            external = False
            for number in (3, 4):
                connected = snapshot.ports[number].connected
                previous = self._physical.get(number)
                if not connected:
                    self._external_removed.add(number)
                if previous is False and connected and number in self._external_removed:
                    external = True
                self._physical[number] = connected
            both_usb = all(snapshot.ports[p].connected and snapshot.ports[p].child_identity is not None for p in (3, 4))
            healthy = both_usb and self._services_healthy()
            if not healthy:
                self._healthy_since = None
            elif self._healthy_since is None:
                self._healthy_since = now
            if external or self._healthy_since is not None and now - self._healthy_since >= self.HEALTHY_SECONDS:
                self._persist(latched=False, inflight=False)
                self._healthy_since = None
                self._external_removed.clear()
        except (OSError, ValueError, TypeError):
            self._disabled = True
        finally:
            os.close(lock)

    def next_tick_delay(self, default=5.0):
        """Let the existing owner loop wake at a live operation's kill deadline."""
        operation, started, killed = self._operation, self._operation_started, self._killed
        if operation is None or started is None or killed:
            return default
        return min(default, max(0.0, started + self.OPERATION_SECONDS - self.clock()))

    def tick(self):
        if not self._mutex.acquire(blocking=False):
            return
        try:
            now, wall = self.clock(), self.wall_clock()
            if (
                not all(math.isfinite(t) for t in (now, wall))
                or self._last_tick is not None
                and now < self._last_tick
                or self._state["last_attempt"] is not None
                and wall < self._state["last_attempt"]
            ):
                self._disabled = True
            self._last_tick = now
            self._poll_operation(now)
            if self._operation is not None:
                return
            if self._stopped.is_set():
                self._resume_owners()
                self._release_gate()
                return
            if self._token is not None:
                if self._frame_ready() and self._transport_ready():
                    self._release_gate()
            if self._disabled:
                return
            snapshot = self.adapter.snapshot()
            self._maybe_rearm(snapshot, now)
            candidate = self._candidates(snapshot)
            if not candidate:
                self._candidate = self._candidate_since = None
                return
            if candidate != self._candidate:
                self._candidate, self._candidate_since = candidate, now
                return
            if now - self._candidate_since < self.STABLE_SECONDS or self._state["latched"]:
                return
            last = self._state["last_attempt"]
            if last is not None and wall - last < self.COOLDOWN_SECONDS:
                return
            retained_barrier = self._token is not None
            if self._token is None:
                self._token = self.gate.try_recovery()
                if self._token is None:
                    return
            consumed = False
            try:
                self._operation_lock = _lock_operation(self.state_path)
                # Another coordinator may have completed between observation and
                # flock acquisition. Re-read its episode under this same lock.
                if self.state_path.exists():
                    fd = os.open(self.state_path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
                    try:
                        _checked_file(fd)
                        with os.fdopen(fd, "r", closefd=False) as stream:
                            disk = json.load(stream)
                        self._validate_state(disk)
                    finally:
                        os.close(fd)
                    self._state = disk
                    if disk["last_attempt"] is not None and wall < disk["last_attempt"]:
                        self._disabled = True
                        return
                    if (
                        disk["latched"]
                        or disk["last_attempt"] is not None
                        and wall - disk["last_attempt"] < self.COOLDOWN_SECONDS
                    ):
                        return
                if self._stopped.is_set() or not self._persist(
                    latched=True, last_attempt=wall, inflight=True, attempt_id=uuid.uuid4().hex
                ):
                    return
                consumed = True
                for owner in (self.vision, self.camera, self.led):
                    if self._stopped.is_set() or not owner.begin_usb_recovery(timeout=2.0):
                        return
                    self._quiet.append(owner)
                if self._candidates(self.adapter.snapshot()) != candidate:
                    return
                with self._launch_lock:
                    # Once admitted here, this launch owns the operation through
                    # handle registration. stop() must cross the same boundary;
                    # a timeout reports the already owned launch as incomplete.
                    if self._stopped.is_set():
                        return
                    self._operation = self.adapter.start_reset(self._operation_lock, candidate)
                    self._operation_started = self.clock()
                    self._killed = False
                if self._stopped.is_set():
                    # A bounded stop may have returned while Popen was pending.
                    # Reap its late handle without needing another owner tick.
                    self._poll_operation(self.clock(), wait_budget=0.0)
            except (OSError, ValueError, TypeError):
                self._disabled = True
                log.warning("USB recovery attempt cancelled", exc_info=True)
            finally:
                if self._operation is None:
                    if consumed:
                        self._persist(inflight=False)
                    self._release_lock()
                    self._resume_owners()
                    if not retained_barrier:
                        self._release_gate()
        finally:
            self._mutex.release()

    def stop(self, timeout=2.0):
        self._stopped.set()
        deadline = time.monotonic() + max(0.0, timeout)
        # Cancel immediately, then establish that no launch remains between its
        # admission check and handle registration. Never wait here for USB I/O.
        if not self._launch_lock.acquire(timeout=max(0.0, deadline - time.monotonic())):
            return False
        self._launch_lock.release()
        if not self._mutex.acquire(timeout=max(0.0, deadline - time.monotonic())):
            return False
        try:
            self._poll_operation(self.clock(), max(0.0, min(0.05, deadline - time.monotonic())))
            if self._operation is not None:
                return False
            self._resume_owners()
            self._release_gate()
            return True
        finally:
            self._mutex.release()
