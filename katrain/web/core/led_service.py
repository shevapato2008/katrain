"""LED serial service — drives the ESP32-S3 LED board over a line-ASCII protocol.

The host holds the (row,col)->chain-index LUT (Appendix A of the track plan,
empirically confirmed 2026-06-15) and addresses raw chain indices; the firmware
just writes a frame buffer scaled by a global BRIGHT.

Two paths (plan §2.1):
  * UI-tolerant   (strict=False): enqueue and return immediately; failures are
    silently dropped (the screen, not the LED, is authoritative for navigation).
  * capture-strict(strict=True):  block until the serial `SHOW` is acked, return
    a `shown_at` monotonic timestamp; a failure means the frame MUST NOT be
    written to the training manifest.

Hardware-free testability: a `serial_factory` callable produces the serial port,
so tests inject a fake (no pyserial / no board required). Real-board bring-up
tests are deferred to hardware day.
"""

from __future__ import annotations

import logging
import os
import queue
import re
import sys
import threading
import time
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional

log = logging.getLogger("katrain_web")

# --------------------------------------------------------------------------- #
# LED (row,col) -> chain-index LUT  (Appendix A — row=0 TOP, col=0 LEFT)
# Chain order UL→LL→LR→UR; serpentine sub-boards; UL/LL normal, LR vflip, UR 180°.
# --------------------------------------------------------------------------- #


def serp(lr: int, lc: int, cols: int) -> int:
    return lr * cols + lc + 1 if lr % 2 == 0 else (lr + 1) * cols - lc


def rc2idx(row: int, col: int) -> int:
    """Canonical (row,col), row,col ∈ [0,18], row=0 top -> raw chain index [0,360]."""
    if row <= 9 and col <= 9:
        return serp(row, col, 10) - 1  # UL 0..99
    if row >= 10 and col <= 9:
        return 100 + serp(row - 10, col, 10) - 1  # LL 100..189
    if row >= 10 and col >= 10:
        return 190 + serp(18 - row, col - 10, 9) - 1  # LR 190..270 (vertical flip)
    return 271 + serp(9 - row, 18 - col, 9) - 1  # UR 271..360 (180°)


# Frame-buffer RGB (0-255); actual output is scaled by the firmware's global BRIGHT.
COLOR_RGB: Dict[str, tuple] = {
    "black": (255, 0, 0),  # black stone -> red LED
    "white": (0, 255, 0),  # white stone -> green LED
    "remove": (0, 0, 255),  # capture/removal -> blue LED
    "hint": (255, 255, 255),  # AI hint / celebration -> white LED
    "flash": (255, 255, 255),  # wrong/extra stone -> bright white, blinked client-side (occlusion-proof)
    "red": (255, 0, 0),
    "green": (0, 255, 0),
    "blue": (0, 0, 255),
}


# Lower bound of the guidance brightness scale: the lamps must stay visible to the player.
MIN_GUIDANCE_SCALE = 0.08


def _scaled(value: int, scale: float) -> int:
    """A colour channel at `scale`; a lit channel never rounds down to fully off."""
    return 0 if value <= 0 else max(1, int(round(value * scale)))


def validate_lut(fn: Callable[[int, int], int]) -> bool:
    """A LUT is valid iff it maps all 361 points bijectively onto [0,360]."""
    seen = set()
    for r in range(19):
        for c in range(19):
            idx = fn(r, c)
            if not (0 <= idx <= 360) or idx in seen:
                return False
            seen.add(idx)
    return len(seen) == 361


@dataclass
class LedServiceConfig:
    enabled: bool = False
    serial_port: str = ""
    baud_rate: int = 115200
    max_bright: int = 255
    handshake_timeout: float = 2.0
    lut_path: Optional[str] = None


@dataclass(frozen=True)
class ReferenceLightingSnapshot:
    request_revision: int
    shown_revision: Optional[int]
    connection_generation: int
    all_dark: bool
    shown_at: Optional[float]
    available: bool


_SENTINEL = object()
_USB_WAKE = object()
_LINK_TIMEOUT = 0.2
_LINK_INTERVAL = 2.0
_LINK_RETRY_INTERVAL = 10.0
_LINK_MAX_AGE = 6.0
_STRICT_TIMEOUT = 5.0
_WRITE_TIMEOUT = 0.2
_LINK_LINE = re.compile(
    r"LINK cc=(OPEN|RD|RA) cc_raw=\d+ cc_mv=\d+ "
    r"ack=(OK|WEAK|ABSENT) ack_raw=\d+ ack_mv=\d+ link=(UP|DOWN|CABLE_ONLY)"
)


class _Batch:
    __slots__ = (
        "commands",
        "wants_show_at",
        "event",
        "result",
        "deadline",
        "real_deadline",
        "cancelled",
        "generation",
        "guidance_revision",
        "finished",
        "request_revision",
        "final_dark",
        "io_started",
    )

    def __init__(self, commands: List[str], strict: bool):
        self.commands = commands
        self.wants_show_at = any(c.startswith("SHOW") for c in commands)
        self.event = threading.Event() if strict else None
        self.result: Dict = {}
        self.deadline = None
        self.real_deadline = None
        self.cancelled = False
        self.generation = None
        self.guidance_revision = None
        self.finished = False
        self.request_revision = None
        self.io_started = False
        # Only a known, completely dark frame followed by a final SHOW can
        # authenticate reference capture. An intermediate blackout cannot.
        lit = None
        known = True
        for command in commands:
            parts = command.split()
            if command == "CLEAR":
                lit = set()
            elif command == "SHOW":
                pass
            elif len(parts) == 5 and parts[0] == "SETI":
                try:
                    index, red, green, blue = map(int, parts[1:])
                    if not (0 <= index <= 360 and all(0 <= value <= 255 for value in (red, green, blue))):
                        known = False
                    elif lit is not None:
                        if red or green or blue:
                            lit.add(index)
                        else:
                            lit.discard(index)
                except ValueError:
                    known = False
            else:
                known = False
        self.final_dark = bool(known and lit == set() and commands and commands[-1] == "SHOW")


class LedService:
    """Background serial worker driving the LED board (plan §2.1)."""

    def __init__(
        self,
        config: LedServiceConfig,
        serial_factory: Optional[Callable[[], object]] = None,
        clock: Callable[[], float] = time.monotonic,
        reconnect_interval: float = 5.0,
    ):
        self.config = config
        self._serial_factory = serial_factory or self._default_serial_factory
        self._clock = clock
        self._reconnect_interval = reconnect_interval

        self._lut = self._load_lut(config.lut_path)
        self._queue: "queue.Queue" = queue.Queue(maxsize=10)
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._serial = None
        self._device_lease = None
        self._connected = False
        self._last_reconnect = 0.0
        self._last_errors: List[str] = []
        # One immutable snapshot keeps HTTP readers independent of serial I/O.
        self._board_link = None  # (monotonic timestamp, link, cc, ack)
        self._next_link_poll = 0.0
        self._link_response_pending = False
        self._link_partial_line = False
        # Set once pyserial itself is missing — a permanent condition, so we stop
        # retrying (and stop logging) instead of hammering every reconnect_interval.
        self._serial_unavailable = False
        self._reconnect_blocked = False
        self._generation = 0
        self._link_failures = 0
        self._alias_missing = False
        # Guidance brightness (MIN_GUIDANCE_SCALE..1): multiplies every set_points colour. Steered by the
        # ambient-light loop (server `_adjust_led_brightness`, fed by the vision worker's led_glow
        # readings) — at night full brightness shines through a white stone and it is no longer
        # recognised. Calibration (set_rgb_points) is never scaled.
        self._guidance_scale = 1.0
        self._last_guidance: Optional[List[Dict]] = None
        self._intent_lock = threading.RLock()
        self._guidance_revision = 0
        self._recovery_needed = False
        self._usb_lock = threading.RLock()
        self._usb_request = None
        self._usb_close_failed = False
        self._usb_wake = threading.Event()
        self._usb_startup_check = None
        self._current_batch = None
        self._reference_request_revision = 0
        self._reference_shown_revision = None
        self._reference_shown_at = None
        self._reference_all_dark = False
        self._reference_stopping = False

    def _invalidate_reference_lighting(self) -> None:
        """Caller holds _usb_lock; revoke ACK authority without doing I/O."""
        self._reference_all_dark = False
        self._reference_shown_revision = None
        self._reference_shown_at = None

    def reference_lighting_snapshot(self) -> ReferenceLightingSnapshot:
        """Return the live LED owner's immutable reference-capture authority."""
        with self._usb_lock:
            available = bool(
                self._connected
                and self._serial is not None
                and self._usb_request is None
                and not self._usb_close_failed
                and not self._stop.is_set()
                and not self._reference_stopping
            )
            return ReferenceLightingSnapshot(
                request_revision=self._reference_request_revision,
                shown_revision=self._reference_shown_revision,
                connection_generation=self._generation,
                all_dark=available and self._reference_all_dark,
                shown_at=self._reference_shown_at,
                available=available,
            )

    def try_commit_reference_lighting(self, token: ReferenceLightingSnapshot, local_commit: Callable[[], None]) -> bool:
        """Adopt worker-local state while the token is still the live dark ACK.

        The callback must only perform short local assignments. It must not do
        I/O, image/model work, callbacks into other owners, or acquire their locks.
        """
        with self._usb_lock:
            current = self.reference_lighting_snapshot()
            if (
                not isinstance(token, ReferenceLightingSnapshot)
                or token != current
                or not current.available
                or not current.all_dark
                or current.shown_revision != current.request_revision
                or current.shown_at is None
            ):
                return False
            local_commit()
            return True

    def _register_reference_request(self, batch: _Batch) -> None:
        """Caller holds _usb_lock, before a display batch can run or enqueue."""
        self._reference_request_revision += 1
        self._invalidate_reference_lighting()
        batch.request_revision = self._reference_request_revision
        batch.generation = self._generation

    def set_usb_startup_check(self, callback) -> None:
        self._usb_startup_check = callback

    def _usb_paused(self) -> bool:
        with self._usb_lock:
            return self._usb_request is not None or self._usb_close_failed

    def _startup_allowed(self) -> bool:
        try:
            return self._usb_startup_check is None or bool(self._usb_startup_check())
        except Exception:
            log.exception("LED USB startup check failed")
            return False

    def begin_usb_recovery(self, timeout=2.0) -> bool:
        deadline = time.monotonic() + max(0.0, timeout)
        with self._intent_lock, self._usb_lock:
            if self._usb_close_failed or self._stop.is_set() or self._thread is None or not self._thread.is_alive():
                return False
            if self._usb_request is not None:
                return self._usb_request["acked"]
            request = {"event": threading.Event(), "deadline": deadline, "acked": False}
            self._usb_request = request
            self._generation += 1
            self._invalidate_reference_lighting()
            self._guidance_revision += 1
            self._last_guidance = None
            self._recovery_needed = False
            # Wake strict callers immediately, even when a native serial call
            # still prevents the worker from acknowledging quiescence.
            if self._current_batch is not None:
                self._current_batch.cancelled = True
                self._finish(self._current_batch, ok=False, shown_at=None, errors=["USB recovery"])
            while True:
                try:
                    batch = self._queue.get_nowait()
                except queue.Empty:
                    break
                if isinstance(batch, _Batch):
                    batch.cancelled = True
                    self._finish(batch, ok=False, shown_at=None, errors=["USB recovery"])
            try:
                self._queue.put_nowait(_USB_WAKE)
            except queue.Full:
                # A pre-request submit can finish queueing during the drain.
                # A full queue already wakes the worker, which checks the pause
                # before taking its next item.
                pass
        request["event"].wait(max(0.0, deadline - time.monotonic()))
        with self._usb_lock:
            if self._usb_request is request and request["acked"]:
                return True
            if self._usb_request is request:
                self._usb_request = None
        self._usb_wake.set()
        return False

    def end_usb_recovery(self) -> None:
        with self._usb_lock:
            self._invalidate_reference_lighting()
            request, self._usb_request = self._usb_request, None
            if request is not None:
                request["event"].set()
            self._last_reconnect = float("-inf")
        self._usb_wake.set()

    def _quiesce_usb(self) -> bool:
        with self._usb_lock:
            request = self._usb_request
        if request is None:
            return False
        if not request["acked"]:
            # Serial close remains on this worker. Keep the existing lease
            # throughout the pause so another owner cannot open during reset.
            closed = self._close_serial(release_lease=False, require_closed=True)
            with self._usb_lock:
                if self._usb_request is request:
                    request["acked"] = bool(
                        closed and not self._stop.is_set() and time.monotonic() <= request["deadline"]
                    )
                    if not request["acked"]:
                        self._usb_request = None
                request["event"].set()
        if self._usb_paused():
            self._usb_wake.wait(0.2)
            self._usb_wake.clear()
            return True
        return False

    # -- LUT --------------------------------------------------------------- #
    def _load_lut(self, lut_path: Optional[str]) -> Callable[[int, int], int]:
        if lut_path:
            try:
                import json

                with open(lut_path, "r", encoding="utf-8") as fh:
                    table = json.load(fh)  # {"row,col": idx} or [[...]] grid
                mapping = {}
                if isinstance(table, dict):
                    for k, v in table.items():
                        r, c = (int(x) for x in k.split(","))
                        mapping[(r, c)] = int(v)
                else:
                    for r, rowvals in enumerate(table):
                        for c, v in enumerate(rowvals):
                            mapping[(r, c)] = int(v)
                fn = lambda r, c: mapping[(r, c)]  # noqa: E731
                if validate_lut(fn):
                    log.info("LED LUT loaded from %s", lut_path)
                    return fn
                log.error("LED LUT at %s failed validation; using built-in formula", lut_path)
            except Exception as e:
                log.error("Failed to load LED LUT %s (%s); using built-in formula", lut_path, e)
        return rc2idx

    # -- lifecycle --------------------------------------------------------- #
    def _default_serial_factory(self):
        import serial  # pyserial — imported lazily so the module loads without it

        return serial.Serial(
            self.config.serial_port,
            self.config.baud_rate,
            timeout=self.config.handshake_timeout,
            write_timeout=_WRITE_TIMEOUT,
        )

    def start(self) -> None:
        if self._usb_close_failed:
            raise RuntimeError("LED USB close remains unconfirmed")
        if self._thread is not None and self._thread.is_alive():
            return
        if self._thread is not None or self._stop.is_set():
            # The previous worker is finished: discard its stop sentinel and
            # queued commands rather than handing them to the new lifecycle.
            self._queue = queue.Queue(maxsize=10)
        with self._usb_lock:
            self._reference_stopping = False
            self._invalidate_reference_lighting()
            self._stop.clear()
        self._reconnect_blocked = False
        self._open_serial()
        self._thread = threading.Thread(target=self._worker, name="led-serial", daemon=True)
        try:
            self._thread.start()
        except BaseException:
            self._thread = None
            self._close_serial()
            raise

    def stop(self) -> None:
        with self._usb_lock:
            self._reference_stopping = True
            self._invalidate_reference_lighting()
        if self._thread is None:
            if not self._usb_close_failed:
                self._close_serial()
            return
        # Blackout via the WORKER (strict) so all serial I/O stays on one thread,
        # then tear down. No post-join serial access → no main/worker race.
        if not self._usb_paused():
            try:
                self.clear(strict=True)
            except Exception:
                pass
        with self._usb_lock:
            self._stop.set()
            self._connected = False
        self.end_usb_recovery()
        try:
            self._queue.put_nowait(_SENTINEL)
        except queue.Full:
            pass
        if self._thread:
            self._thread.join(timeout=3)
            if self._thread.is_alive():
                # A blocked open still owns the device. The worker closes any
                # late result and releases its lease before it exits.
                return
        if not self._usb_close_failed:
            self._close_serial()
        self._thread = None

    def is_connected(self) -> bool:
        """Board B transport only; capture transactions retain this meaning."""
        return self._connected

    def board_status(self) -> Dict:
        """Read cached Board A power acknowledgement; never query serial here."""
        snapshot = self._board_link
        if not self._connected or snapshot is None or self._clock() - snapshot[0] > _LINK_MAX_AGE:
            return {"connected": None, "board_link": None, "cc": None, "ack": None}
        _, link, cc, ack = snapshot
        return {"connected": link == "UP", "board_link": link, "cc": cc, "ack": ack}

    def is_board_connected(self) -> Optional[bool]:
        return self.board_status()["connected"]

    @property
    def last_errors(self) -> List[str]:
        """Firmware/serial errors from the most recently completed batch only —
        not an accumulated history. A batch with no errors overwrites this back to
        [], EVEN IF it immediately follows a failing one (e.g. a plain CLEAR sent
        right after a batch that hit `ERR maxon`) — so this is a snapshot of "right
        now", not a log of everything that went wrong. For history, read the
        journal: every batch with errors also goes through `log.warning(...)` in
        _run_batch. The non-strict path's HTTP `ok: true` only means "enqueued";
        this is where its real outcome — e.g. firmware `ERR maxon` when a request
        exceeds MAX_ON, or the serial connection dropping mid-batch — surfaces."""
        return list(self._last_errors)

    # -- public API -------------------------------------------------------- #
    def set_points(self, points: List[Dict], *, strict: bool = False) -> Dict:
        """Light a set of points. Each point: {row, col, color}.

        Returns {ok, connected, shown_at, errors}. For strict=False this reflects
        only enqueue success; for strict=True it reflects the actual SHOW ack.
        """
        with self._intent_lock:
            if self._usb_paused():
                return self._usb_rejected()
            self._guidance_revision += 1
            self._last_guidance = [dict(point) for point in points] if not strict else None
            self._recovery_needed = bool(self._last_guidance)
            commands = self._guidance_commands(points)
            if not strict:
                return self._submit(commands, strict=False, guidance_revision=self._guidance_revision)
        return self._submit(commands, strict=True)

    def _guidance_commands(self, points: List[Dict]) -> List[str]:
        scale = self._guidance_scale
        commands = ["CLEAR"]
        for p in points:
            row, col, color = p.get("row"), p.get("col"), p.get("color", "black")
            if row is None or col is None or not (0 <= row <= 18 and 0 <= col <= 18):
                continue
            idx = self._lut(row, col)
            r, g, b = (_scaled(v, scale) for v in COLOR_RGB.get(str(color), COLOR_RGB["black"]))
            commands.append(f"SETI {idx} {r} {g} {b}")
        commands.append("SHOW")
        return commands

    @property
    def guidance_scale(self) -> float:
        return self._guidance_scale

    def set_guidance_scale(self, scale: float) -> None:
        """Set the guidance brightness and re-show whatever guidance is lit right now at it."""
        self._guidance_scale = min(1.0, max(MIN_GUIDANCE_SCALE, float(scale)))
        with self._intent_lock:
            if self._last_guidance:
                self.set_points(self._last_guidance, strict=False)

    def set_rgb_points(self, points: List[Dict], *, strict: bool = False, blank_before: bool = False) -> Dict:
        """Light explicit RGB points; optionally SHOW a blackout first in the same batch."""
        with self._intent_lock:
            self._guidance_revision += 1
            self._last_guidance = None
            self._recovery_needed = False
        commands = ["CLEAR", "SHOW", "CLEAR"] if blank_before else ["CLEAR"]
        for point in points:
            row, col = point.get("row"), point.get("col")
            rgb = point.get("rgb")
            if row is None or col is None or not (0 <= row <= 18 and 0 <= col <= 18):
                continue
            if not isinstance(rgb, (list, tuple)) or len(rgb) != 3:
                continue
            red, green, blue = (max(0, min(255, int(value))) for value in rgb)
            commands.append(f"SETI {self._lut(row, col)} {red} {green} {blue}")
        commands.append("SHOW")
        return self._submit(commands, strict=strict)

    def clear(self, *, strict: bool = False) -> Dict:
        with self._intent_lock:
            self._guidance_revision += 1
            self._last_guidance = None
            self._recovery_needed = False
            if not strict:
                return self._submit(["CLEAR", "SHOW"], strict=False)
        return self._submit(["CLEAR", "SHOW"], strict=True)

    # -- queue plumbing ---------------------------------------------------- #
    def _submit(self, commands: List[str], *, strict: bool, guidance_revision=None) -> Dict:
        batch = _Batch(commands, strict)
        with self._usb_lock:
            self._register_reference_request(batch)
            if self._usb_request is not None or self._usb_close_failed or self._stop.is_set():
                return self._usb_rejected()
        log.info("[DIAG-LED] submit %d leds", sum(1 for c in commands if c.startswith("SETI")))
        batch.guidance_revision = guidance_revision
        if strict:
            batch.deadline = self._clock() + _STRICT_TIMEOUT
            batch.real_deadline = time.monotonic() + _STRICT_TIMEOUT
            try:
                self._queue.put(batch, timeout=min(3.0, self._batch_remaining(batch)))
            except queue.Full:
                return {"ok": False, "connected": self._connected, "shown_at": None, "errors": ["queue full"]}
            with self._usb_lock:
                if self._usb_request is not None or batch.generation != self._generation:
                    batch.cancelled = True
                    self._finish(batch, ok=False, shown_at=None, errors=["USB recovery"])
            if not batch.event.wait(timeout=max(0.0, self._batch_remaining(batch))):
                with self._usb_lock:
                    # Completion can win while this caller waits for the lock.
                    # A finished old batch no longer owns the current display.
                    if batch.finished:
                        return batch.result
                    batch.cancelled = True
                    if batch.io_started or batch.request_revision == self._reference_request_revision:
                        self._invalidate_reference_lighting()
                return {"ok": False, "connected": self._connected, "shown_at": None, "errors": ["timeout"]}
            return batch.result
        # UI-tolerant: enqueue, dropping the oldest item if the queue is full.
        try:
            self._queue.put_nowait(batch)
        except queue.Full:
            try:
                dropped = self._queue.get_nowait()
                self._finish(dropped, ok=False, shown_at=None, errors=["queue full"])
            except queue.Empty:
                pass
            try:
                self._queue.put_nowait(batch)
            except queue.Full:
                pass
        return {"ok": True, "connected": self._connected, "shown_at": None, "errors": []}

    def _usb_rejected(self) -> Dict:
        return {"ok": False, "connected": self._connected, "shown_at": None, "errors": ["USB recovery"]}

    # -- worker ------------------------------------------------------------ #
    def _worker(self) -> None:
        try:
            while not self._stop.is_set():
                if self._quiesce_usb():
                    continue
                try:
                    item = self._queue.get(timeout=0.2)
                except queue.Empty:
                    if self._serial is None:
                        self._maybe_reconnect()
                    self._maybe_poll_board_link()
                    continue
                if item is _SENTINEL:
                    break
                if item is _USB_WAKE:
                    continue
                with self._usb_lock:
                    self._current_batch = item
                    paused = self._usb_request is not None
                if paused:
                    self._finish(item, ok=False, shown_at=None, errors=["USB recovery"])
                    continue
                if item.cancelled or (item.deadline is not None and self._batch_remaining(item) <= 0):
                    self._finish(item, ok=False, shown_at=None, errors=["timeout"])
                    self._maybe_poll_board_link()
                    continue
                if self._serial is None:
                    self._maybe_reconnect(batch=item)
                # A batch dequeued before open still belongs to its original
                # connection, even if the reconnect succeeded in this iteration.
                if item.generation is not None and item.generation != self._generation:
                    self._finish(item, ok=False, shown_at=None, errors=["connection changed"])
                    self._maybe_poll_board_link()
                    continue
                if self._serial is None:
                    self._finish(item, ok=False, shown_at=None, errors=["not connected"])
                    continue
                try:
                    self._run_batch(item)
                except Exception as e:
                    log.warning("LED serial error: %s", e)
                    self._close_serial()
                    self._finish(item, ok=False, shown_at=None, errors=[str(e)])
                self._maybe_poll_board_link()
        finally:
            if not self._usb_close_failed:
                self._close_serial(release_lease=True)

    def _run_batch(self, batch: _Batch) -> None:
        errors: List[str] = []
        shown_at = None
        if batch.deadline is None:
            batch.deadline = self._clock() + _STRICT_TIMEOUT
            batch.real_deadline = time.monotonic() + _STRICT_TIMEOUT
        for cmd in batch.commands:
            if self._usb_paused():
                errors.append("USB recovery")
                break
            with self._usb_lock:
                superseded = (
                    batch.request_revision is not None and batch.request_revision != self._reference_request_revision
                )
            if superseded:
                errors.append("display request replaced")
                break
            if batch.generation is not None and batch.generation != self._generation:
                errors.append("connection changed")
                break
            if batch.guidance_revision is not None and batch.guidance_revision != self._guidance_revision:
                errors.append("guidance replaced")
                break
            if batch.cancelled or self._batch_remaining(batch) <= 0 or self._stop.is_set():
                errors.append("timeout" if not self._stop.is_set() else "stopped")
                if batch.io_started:
                    self._close_serial()
                break
            # As in the open handshake, each display command needs its own
            # response. A buffered prior ACK cannot certify the final SHOW.
            # Preserve an unfinished LINK line for the existing ACK parser;
            # discarding its buffered tail would leave framing out of sync.
            if not self._link_partial_line:
                self._drain_prewrite_input()
            batch.io_started = True
            ok, resp = self._send_and_ack(cmd, deadline=batch.deadline, real_deadline=batch.real_deadline)
            if batch.cancelled or self._batch_remaining(batch) <= 0:
                errors.append("timeout")
                self._close_serial()
                break
            if not ok:
                errors.append(f"{cmd} -> {resp}")
                if not resp.startswith("ERR"):
                    self._close_serial()
                    break
            if cmd.startswith("SHOW") and ok:
                shown_at = self._clock()
        if errors:
            # _run_batch runs for both strict and non-strict batches: the strict
            # caller is still blocked on batch.event and gets these errors back
            # through batch.result (set in _finish below), so for it this line is
            # just an extra trace. The non-strict caller already got its ok:true
            # back in _submit() and never sees batch.result at all — for IT, this
            # log line (and last_errors, also updated in _finish) is the only
            # remaining exit. MAX_ON / ERR range and friends all land here.
            log.warning("LED batch reported %d firmware error(s): %s", len(errors), "; ".join(errors[:5]))
        if not errors and batch.guidance_revision == self._guidance_revision:
            # A frame sent while Board A was down must be refreshed after UP.
            self._recovery_needed = self.is_board_connected() is False
        self._finish(batch, ok=not errors, shown_at=None if errors else shown_at, errors=errors)

    def _batch_remaining(self, batch: _Batch) -> float:
        return min(batch.deadline - self._clock(), batch.real_deadline - time.monotonic())

    def _write(self, data: bytes, deadline: float, real_deadline: float) -> None:
        remaining = min(deadline - self._clock(), real_deadline - time.monotonic())
        if remaining <= 0:
            raise TimeoutError("serial deadline")
        self._serial.write_timeout = min(_WRITE_TIMEOUT, remaining)
        written = self._serial.write(data)
        if written is not None and written != len(data):
            raise TimeoutError("incomplete serial write")

    def _read_protocol_line(self, deadline: float, real_deadline: float) -> bytes:
        port = self._serial
        read = getattr(port, "read", None)
        data = bytearray()
        for _ in range(256):
            remaining = min(deadline - self._clock(), real_deadline - time.monotonic())
            if remaining <= 0:
                break
            port.timeout = remaining
            chunk = read(1) if callable(read) else port.readline()
            if not chunk:
                break
            data.extend(chunk)
            if chunk.endswith(b"\n") or not callable(read):
                break
        return bytes(data)

    def _send_and_ack(self, cmd: str, *, deadline=None, real_deadline=None) -> tuple:
        deadline = min(
            deadline if deadline is not None else float("inf"), self._clock() + self.config.handshake_timeout
        )
        real_deadline = min(
            real_deadline if real_deadline is not None else float("inf"),
            time.monotonic() + self.config.handshake_timeout,
        )
        self._write((cmd + "\n").encode("ascii"), deadline, real_deadline)
        # Read response lines until OK/ERR or a couple of blanks (READY etc. ignored).
        for _ in range(4):
            raw = self._read_protocol_line(deadline, real_deadline)
            if self._clock() >= deadline or time.monotonic() >= real_deadline:
                break
            if self._link_partial_line:
                # LINK's timed-out prefix still owns the rest of this line,
                # including an "OK ..." tail. Release it only at the newline.
                if raw.endswith(b"\n"):
                    self._link_partial_line = False
                    self._link_response_pending = False
                continue
            if raw and not raw.endswith(b"\n"):
                if self._link_response_pending:
                    self._link_partial_line = True
                continue
            line = raw.decode("ascii", errors="replace").strip()
            if not line:
                continue
            if line.startswith("LINK ") or (line == "ERR cmd" and self._link_response_pending):
                # A timed-out LINK owns its late response, never CLEAR/SHOW's ACK.
                self._link_response_pending = False
                continue
            if line.startswith("OK"):
                return True, line
            if line.startswith("ERR"):
                return False, line
            # other chatter (READY/STATUS) — keep reading
        return False, "no-ack"

    def _maybe_poll_board_link(self) -> None:
        # Called only between complete batches, including when the queue is busy.
        if self._stop.is_set() or self._usb_paused() or self._serial is None:
            return
        if self._clock() < self._next_link_poll:
            return
        if self._linux_alias_absent():
            return
        try:
            self._poll_board_link()
        except Exception as exc:
            log.warning("LED LINK read failed: %s", exc)
            self._close_serial()

    def _poll_board_link(self) -> None:
        """Worker-only standalone LINK read with a total 200 ms timeout budget."""
        self._board_link = None
        port = self._serial
        previous_timeout = getattr(port, "timeout", None)
        deadline = self._clock() + _LINK_TIMEOUT
        real_deadline = time.monotonic() + _LINK_TIMEOUT
        legacy = False
        try:
            port.timeout = _LINK_TIMEOUT
            # Buffered late status belongs to the previous query. An unfinished
            # line must retain its framing and be consumed through its newline.
            if not self._link_partial_line:
                self._drain_prewrite_input()
            self._link_response_pending = True
            self._write(b"LINK\n", deadline, real_deadline)
            for _ in range(8):
                remaining = min(deadline - self._clock(), real_deadline - time.monotonic())
                if remaining <= 0:
                    break
                port.timeout = remaining
                line = self._read_link_line(deadline, real_deadline).decode("ascii", errors="replace").strip()
                if not line:
                    break
                if line.startswith("LINK "):
                    self._link_response_pending = False
                    match = _LINK_LINE.fullmatch(line)
                    if match:
                        cc, ack, link = match.groups()
                        # Mirror v7 firmware: ACK OK wins even when CC is OPEN.
                        expected = "UP" if ack == "OK" else "DOWN" if cc == "OPEN" else "CABLE_ONLY"
                        if link == expected:
                            self._board_link = (self._clock(), link, cc, ack)
                    break
                if line.startswith("ERR"):
                    self._link_response_pending = False
                    legacy = line == "ERR cmd"
                    break
        finally:
            port.timeout = previous_timeout
            self._next_link_poll = self._clock() + (_LINK_RETRY_INTERVAL if legacy else _LINK_INTERVAL)
        if self._board_link is not None or legacy:
            self._link_failures = 0
        else:
            self._link_failures += 1
            if self._link_failures >= 3:
                self._close_serial()
                return
        if self.is_board_connected() is not True:
            self._recovery_needed = bool(self._last_guidance)
        elif self.is_board_connected() is True:
            self._recover_guidance()

    def _recover_guidance(self) -> None:
        # Recovery is a fresh full frame from the current intent. Never replay
        # commands from a calibration/capture transaction or a former session.
        with self._intent_lock:
            if not self._recovery_needed or not self._last_guidance:
                return
            batch = _Batch(self._guidance_commands(self._last_guidance), strict=False)
            with self._usb_lock:
                self._register_reference_request(batch)
            batch.guidance_revision = self._guidance_revision
        self._run_batch(batch)

    def _read_link_line(self, deadline: float, real_deadline: float) -> bytes:
        port = self._serial
        read = getattr(port, "read", None)
        if not callable(read):
            # Minimal serial adapters used by callers/tests may only offer lines.
            raw = port.readline()
            if self._link_partial_line:
                if raw.endswith(b"\n"):
                    self._link_partial_line = False
                return b""
            if raw and not raw.endswith(b"\n"):
                self._link_partial_line = True
                return b""
            return raw
        # pyserial's generic readline may restart the timeout per byte. Set the
        # remaining budget for each read instead, including unterminated chatter.
        data = bytearray()
        for _ in range(256):
            remaining = min(deadline - self._clock(), real_deadline - time.monotonic())
            if remaining <= 0:
                break
            port.timeout = remaining
            chunk = read(1)
            if not chunk:
                break
            data.extend(chunk)
            if chunk == b"\n":
                if self._link_partial_line:
                    self._link_partial_line = False
                    data.clear()
                    continue
                return bytes(data)
        self._link_partial_line = self._link_partial_line or bool(data)
        return b""

    def _finish(self, batch, *, ok: bool, shown_at, errors: List[str]) -> None:
        if batch is _SENTINEL or not isinstance(batch, _Batch):
            # Not a real batch of commands (nothing was actually attempted), so
            # there is no outcome to record — leave last_errors as-is.
            return
        # ALL finish paths converge here — a clean completion (with or without
        # firmware errors) from _run_batch, a real serial exception from _worker's
        # except-Exception handler, and "not connected" from _worker directly — so
        # this is the one place that can update last_errors for every one of them.
        # (It used to be set only in _run_batch's own call site, which meant a
        # serial exception left last_errors — and /led/status — stuck on
        # whatever the previous batch reported.)
        with self._usb_lock:
            if batch.finished:
                return
            batch.finished = True
            if not ok:
                # A rejected old request that never reached serial cannot
                # invalidate a newer frame's successful dark SHOW.
                if batch.io_started or batch.request_revision == self._reference_request_revision:
                    self._invalidate_reference_lighting()
            elif (
                batch.request_revision == self._reference_request_revision
                and batch.generation == self._generation
                and self.reference_lighting_snapshot().available
            ):
                self._reference_shown_revision = batch.request_revision if shown_at is not None else None
                self._reference_shown_at = shown_at
                self._reference_all_dark = batch.final_dark and shown_at is not None
            if self._current_batch is batch:
                self._current_batch = None
            self._last_errors = list(errors)
            batch.result = {"ok": ok, "connected": self._connected, "shown_at": shown_at, "errors": errors}
            if batch.event is not None:
                batch.event.set()

    # -- serial helpers ---------------------------------------------------- #
    def _wait_for_boot_ready(self, *, deadline=None, real_deadline=None) -> None:
        """Give a freshly opened ESP32 a bounded chance to announce READY."""
        deadline = min(
            deadline if deadline is not None else float("inf"), self._clock() + self.config.handshake_timeout
        )
        real_deadline = min(
            real_deadline if real_deadline is not None else float("inf"),
            time.monotonic() + self.config.handshake_timeout,
        )
        for _ in range(32):
            raw = self._read_protocol_line(deadline, real_deadline)
            if not raw or self._clock() >= deadline or time.monotonic() >= real_deadline:
                return
            if raw.endswith(b"\n") and raw.strip().startswith(b"READY"):
                return

    def _drain_prewrite_input(self) -> None:
        """Discard stale input without letting a partial line consume a read timeout."""
        reset_input_buffer = getattr(self._serial, "reset_input_buffer", None)
        if callable(reset_input_buffer):
            reset_input_buffer()
            return

        # pyserial exposes reset_input_buffer, but keep serial-compatible test or
        # adapter objects safe too: a zero timeout makes readline nonblocking.
        missing = object()
        previous_timeout = getattr(self._serial, "timeout", missing)
        if previous_timeout is missing:
            return
        try:
            self._serial.timeout = 0
            deadline = self._clock() + self.config.handshake_timeout
            for _ in range(32):
                if self._clock() >= deadline or not getattr(self._serial, "in_waiting", 0):
                    break
                read = getattr(self._serial, "read", None)
                if callable(read):
                    read(min(256, getattr(self._serial, "in_waiting", 0)))
                else:
                    self._serial.readline()
        finally:
            self._serial.timeout = previous_timeout

    def _open_serial(self, *, batch=None) -> None:
        if self._usb_paused() or not self._startup_allowed():
            return
        if self._linux_alias_absent():
            return
        with self._usb_lock:
            if self._usb_request is not None or self._usb_close_failed or self._stop.is_set():
                return
            self._generation += 1
            self._connected = False
            self._invalidate_reference_lighting()
        self._board_link = None
        self._next_link_poll = 0.0
        self._link_response_pending = False
        self._link_partial_line = False
        self._link_failures = 0
        if self._device_lease is None:
            # Imported here so standalone LED users can load this leaf module
            # without importing the web application package.
            from katrain.web.core.device_lease import DeviceLease

            self._device_lease = DeviceLease.acquire("led", self.config.serial_port)
        try:
            self._serial = self._serial_factory()
            if (
                self._stop.is_set()
                or self._usb_paused()
                or (
                    batch is not None
                    and (batch.cancelled or (batch.deadline is not None and self._batch_remaining(batch) <= 0))
                )
            ):
                self._close_serial()
                return

            # A USB-open can reset the ESP32. Wait for its boot banner (or a
            # bounded timeout), then discard boot chatter before the blackout.
            self._wait_for_boot_ready(
                deadline=batch.deadline if batch is not None else None,
                real_deadline=batch.real_deadline if batch is not None else None,
            )

            deadline = self._clock() + self.config.handshake_timeout
            real_deadline = time.monotonic() + self.config.handshake_timeout
            if batch is not None and batch.deadline is not None:
                deadline = min(deadline, batch.deadline)
                real_deadline = min(real_deadline, batch.real_deadline)
            # BRIGHT renders the retained MCU buffer. Clear and SHOW must each
            # receive a fresh ACK before brightness can expose that buffer.
            for command in ("CLEAR", "SHOW", f"BRIGHT {self.config.max_bright}"):
                if self._stop.is_set() or self._usb_paused():
                    break
                # Each command needs its own response; buffered boot input or
                # an extra prior ACK must never authenticate this step.
                self._drain_prewrite_input()
                ok, _ = self._send_and_ack(command, deadline=deadline, real_deadline=real_deadline)
                if not ok:
                    break
            else:
                with self._usb_lock:
                    if not self._stop.is_set() and not self._usb_paused():
                        self._connected = True
                        self._recovery_needed = bool(self._last_guidance)
                        log.info("LED serial opened on %s", self.config.serial_port)
                        return

            self._close_serial()
            log.warning("LED serial handshake failed (%s)", self.config.serial_port)
        except ImportError as e:
            # pyserial not installed — permanent, not a transient device hiccup.
            # Log once and disable reconnect so we don't spam the log every cycle.
            self._close_serial()
            self._serial_unavailable = True
            log.warning(
                "LED disabled: pyserial not installed (%s). Run `pip install pyserial` to enable LED guidance.",
                e,
            )
        except Exception as e:
            self._close_serial()
            log.warning("LED serial open failed (%s): %s", self.config.serial_port, e)

    def _maybe_reconnect(self, *, batch=None) -> None:
        if self._stop.is_set() or self._usb_paused() or self._serial_unavailable or self._reconnect_blocked:
            return  # Missing pyserial is permanent; a lease conflict requires explicit stop/start.
        was_missing = self._alias_missing
        if self._linux_alias_absent():
            return
        now = self._clock()
        if not was_missing and now - self._last_reconnect < self._reconnect_interval:
            return
        self._last_reconnect = now
        from katrain.web.core.device_lease import DeviceBusy

        try:
            self._open_serial(batch=batch)
        except DeviceBusy as exc:
            self._reconnect_blocked = True
            self._last_errors = [str(exc)]
            log.warning("LED serial unavailable: %s", exc)

    def _linux_alias_absent(self) -> bool:
        if sys.platform != "linux" or not os.path.isabs(self.config.serial_port):
            return False
        self._alias_missing = not os.path.exists(self.config.serial_port)
        if self._alias_missing and self._serial is not None:
            self._close_serial()
        return self._alias_missing

    def _close_serial(self, *, release_lease=None, require_closed=False) -> bool:
        with self._usb_lock:
            if self._serial is not None:
                self._generation += 1
            self._connected = False
            self._invalidate_reference_lighting()
        self._recovery_needed = bool(self._last_guidance)
        self._board_link = None
        self._link_response_pending = False
        self._link_partial_line = False
        if self._serial is not None:
            try:
                self._serial.close()
            except Exception as exc:
                if require_closed:
                    # A failed USB quiescence must keep ownership of the live
                    # handle. Neither end() nor stop() may open a second handle
                    # or let another owner take the lease after this failure.
                    with self._usb_lock:
                        self._usb_close_failed = True
                    self._last_errors = [f"USB close failed: {exc}"]
                    log.warning("LED USB close failed; retaining device ownership: %s", exc)
                    return False
        self._serial = None
        if release_lease is None:
            release_lease = not self._usb_paused()
        if release_lease and self._device_lease is not None:
            self._device_lease.release()
            self._device_lease = None
        return True
