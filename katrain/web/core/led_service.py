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
import queue
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
    max_bright: int = 200
    handshake_timeout: float = 2.0
    lut_path: Optional[str] = None


_SENTINEL = object()


class _Batch:
    __slots__ = ("commands", "wants_show_at", "event", "result")

    def __init__(self, commands: List[str], strict: bool):
        self.commands = commands
        self.wants_show_at = any(c.startswith("SHOW") for c in commands)
        self.event = threading.Event() if strict else None
        self.result: Dict = {}


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
        self._connected = False
        self._last_reconnect = 0.0
        # Set once pyserial itself is missing — a permanent condition, so we stop
        # retrying (and stop logging) instead of hammering every reconnect_interval.
        self._serial_unavailable = False

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
        )

    def start(self) -> None:
        self._stop.clear()
        self._open_serial()
        self._thread = threading.Thread(target=self._worker, name="led-serial", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        # Blackout via the WORKER (strict) so all serial I/O stays on one thread,
        # then tear down. No post-join serial access → no main/worker race.
        try:
            self.clear(strict=True)
        except Exception:
            pass
        self._stop.set()
        try:
            self._queue.put_nowait(_SENTINEL)
        except queue.Full:
            pass
        if self._thread:
            self._thread.join(timeout=3)
        self._close_serial()

    def is_connected(self) -> bool:
        return self._connected

    # -- public API -------------------------------------------------------- #
    def set_points(self, points: List[Dict], *, strict: bool = False) -> Dict:
        """Light a set of points. Each point: {row, col, color}.

        Returns {ok, connected, shown_at, errors}. For strict=False this reflects
        only enqueue success; for strict=True it reflects the actual SHOW ack.
        """
        commands = ["CLEAR"]
        for p in points:
            row, col, color = p.get("row"), p.get("col"), p.get("color", "black")
            if row is None or col is None or not (0 <= row <= 18 and 0 <= col <= 18):
                continue
            idx = self._lut(row, col)
            r, g, b = COLOR_RGB.get(str(color), COLOR_RGB["black"])
            commands.append(f"SETI {idx} {r} {g} {b}")
        commands.append("SHOW")
        return self._submit(commands, strict=strict)

    def set_rgb_points(self, points: List[Dict], *, strict: bool = False) -> Dict:
        """Light points with explicit RGB values for calibration and diagnostics."""
        commands = ["CLEAR"]
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
        return self._submit(["CLEAR", "SHOW"], strict=strict)

    # -- queue plumbing ---------------------------------------------------- #
    def _submit(self, commands: List[str], *, strict: bool) -> Dict:
        log.info("[DIAG-LED] submit %d leds", sum(1 for c in commands if c.startswith("SETI")))
        batch = _Batch(commands, strict)
        if strict:
            try:
                self._queue.put(batch, timeout=3)
            except queue.Full:
                return {"ok": False, "connected": self._connected, "shown_at": None, "errors": ["queue full"]}
            if not batch.event.wait(timeout=5):
                return {"ok": False, "connected": self._connected, "shown_at": None, "errors": ["timeout"]}
            return batch.result
        # UI-tolerant: enqueue, dropping the oldest item if the queue is full.
        try:
            self._queue.put_nowait(batch)
        except queue.Full:
            try:
                self._queue.get_nowait()
            except queue.Empty:
                pass
            try:
                self._queue.put_nowait(batch)
            except queue.Full:
                pass
        return {"ok": True, "connected": self._connected, "shown_at": None, "errors": []}

    # -- worker ------------------------------------------------------------ #
    def _worker(self) -> None:
        while not self._stop.is_set():
            try:
                item = self._queue.get(timeout=0.2)
            except queue.Empty:
                if self._serial is None:
                    self._maybe_reconnect()
                continue
            if item is _SENTINEL:
                break
            if self._serial is None:
                self._maybe_reconnect()
            if self._serial is None:
                self._finish(item, ok=False, shown_at=None, errors=["not connected"])
                continue
            try:
                self._run_batch(item)
            except Exception as e:
                log.warning("LED serial error: %s", e)
                self._connected = False
                self._close_serial()
                self._finish(item, ok=False, shown_at=None, errors=[str(e)])

    def _run_batch(self, batch: _Batch) -> None:
        errors: List[str] = []
        shown_at = None
        for cmd in batch.commands:
            ok, resp = self._send_and_ack(cmd)
            if not ok:
                errors.append(f"{cmd} -> {resp}")
            if cmd.startswith("SHOW") and ok:
                shown_at = self._clock()
        self._finish(batch, ok=not errors, shown_at=shown_at, errors=errors)

    def _send_and_ack(self, cmd: str) -> tuple:
        self._serial.write((cmd + "\n").encode("ascii"))
        # Read response lines until OK/ERR or a couple of blanks (READY etc. ignored).
        for _ in range(4):
            line = self._serial.readline().decode("ascii", errors="replace").strip()
            if not line:
                continue
            if line.startswith("OK"):
                return True, line
            if line.startswith("ERR"):
                return False, line
            # other chatter (READY/STATUS) — keep reading
        return False, "no-ack"

    def _finish(self, batch, *, ok: bool, shown_at, errors: List[str]) -> None:
        if batch is _SENTINEL or not isinstance(batch, _Batch):
            return
        batch.result = {"ok": ok, "connected": self._connected, "shown_at": shown_at, "errors": errors}
        if batch.event is not None:
            batch.event.set()

    # -- serial helpers ---------------------------------------------------- #
    def _wait_for_boot_ready(self) -> None:
        """Give a freshly opened ESP32 a bounded chance to announce READY."""
        deadline = self._clock() + self.config.handshake_timeout
        boot_data = b""

        while self._clock() < deadline:
            waiting = getattr(self._serial, "in_waiting", 0)
            read_available = getattr(self._serial, "read", None)
            if waiting and callable(read_available):
                # pyserial read(n) is nonblocking for bytes reported in_waiting,
                # unlike readline() on an unterminated boot banner.
                chunk = read_available(waiting)
                if not chunk:
                    break
                boot_data += chunk
            else:
                line = self._serial.readline()
                boot_data += line
                if not line:
                    # A normal pyserial readline just waited through its timeout.
                    break

            if self._clock() >= deadline:
                break
            if any(line.strip().startswith(b"READY") for line in boot_data.splitlines()):
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
                self._serial.readline()
        finally:
            self._serial.timeout = previous_timeout

    def _open_serial(self) -> None:
        try:
            self._serial = self._serial_factory()
            self._connected = False

            # A USB-open can reset the ESP32. Wait for its boot banner (or a
            # bounded timeout), then discard boot chatter before BRIGHT.
            self._wait_for_boot_ready()

            # Discard all buffered input before BRIGHT. In particular, a stale OK
            # or an unterminated partial line must never authenticate a connection.
            self._drain_prewrite_input()

            self._serial.write(f"BRIGHT {self.config.max_bright}\n".encode("ascii"))
            deadline = self._clock() + self.config.handshake_timeout
            while self._clock() < deadline:
                line = self._serial.readline().decode("ascii", errors="replace").strip()
                if self._clock() >= deadline:
                    break
                if line.startswith("OK"):
                    self._connected = True
                    log.info("LED serial opened on %s", self.config.serial_port)
                    return
                if line.startswith("ERR"):
                    break

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

    def _maybe_reconnect(self) -> None:
        if self._serial_unavailable:
            return  # pyserial missing — never recoverable by retrying
        now = self._clock()
        if now - self._last_reconnect < self._reconnect_interval:
            return
        self._last_reconnect = now
        self._open_serial()

    def _close_serial(self) -> None:
        if self._serial is not None:
            try:
                self._serial.close()
            except Exception:
                pass
        self._serial = None
        self._connected = False
