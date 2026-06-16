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
    max_bright: int = 40
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

        return serial.Serial(self.config.serial_port, self.config.baud_rate, timeout=2)

    def start(self) -> None:
        self._stop.clear()
        self._open_serial()
        self._thread = threading.Thread(target=self._worker, name="led-serial", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        # Best-effort blackout, then tear down the worker + port.
        try:
            self.clear(strict=False)
        except Exception:
            pass
        self._stop.set()
        try:
            self._queue.put_nowait(_SENTINEL)
        except queue.Full:
            pass
        if self._thread:
            self._thread.join(timeout=3)
        self._send_now("CLEAR!")  # final hard clear if the port is still open
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

    def clear(self, *, strict: bool = False) -> Dict:
        return self._submit(["CLEAR", "SHOW"], strict=strict)

    # -- queue plumbing ---------------------------------------------------- #
    def _submit(self, commands: List[str], *, strict: bool) -> Dict:
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
    def _open_serial(self) -> None:
        try:
            self._serial = self._serial_factory()
            self._connected = True
            # Drain boot banner, set global brightness.
            self._send_now(f"BRIGHT {self.config.max_bright}")
            log.info("LED serial opened on %s", self.config.serial_port)
        except Exception as e:
            self._serial = None
            self._connected = False
            log.warning("LED serial open failed (%s): %s", self.config.serial_port, e)

    def _maybe_reconnect(self) -> None:
        now = self._clock()
        if now - self._last_reconnect < self._reconnect_interval:
            return
        self._last_reconnect = now
        self._open_serial()

    def _send_now(self, cmd: str) -> None:
        if self._serial is None:
            return
        try:
            self._serial.write((cmd + "\n").encode("ascii"))
        except Exception:
            pass

    def _close_serial(self) -> None:
        if self._serial is not None:
            try:
                self._serial.close()
            except Exception:
                pass
        self._serial = None
        self._connected = False
