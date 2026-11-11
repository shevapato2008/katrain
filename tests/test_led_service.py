"""Tests for the LED serial service using a FAKE serial port (no pyserial, no board).

Real-board bring-up (single-LED control, star-point landing) is verified on
hardware day; these tests lock the host-side logic: LUT correctness, color/RGB
mapping, the strict SHOW-ack path, queue-full dropping, and reconnect.
"""

import importlib.util
import logging
import os
import subprocess
import sys
import threading
import time
import uuid
from dataclasses import FrozenInstanceError
from pathlib import Path
from types import SimpleNamespace

import pytest

# Load this leaf module without executing katrain.web.__init__, whose eager
# desktop interface import requires compiled locale files. Do not replace the
# real package in sys.modules: other tests may legitimately import it later.
_web_package_before = sys.modules.get("katrain.web")
_led_service_spec = importlib.util.spec_from_file_location(
    "test_led_service_leaf",
    Path(__file__).resolve().parents[1] / "katrain" / "web" / "core" / "led_service.py",
)
assert _led_service_spec is not None and _led_service_spec.loader is not None
_led_service = importlib.util.module_from_spec(_led_service_spec)
sys.modules[_led_service_spec.name] = _led_service
_led_service_spec.loader.exec_module(_led_service)
# Capture this immediately: other test modules may legitimately import the real
# package between collection and this test's execution.
_web_package_after_leaf_import = sys.modules.get("katrain.web")

LedService = _led_service.LedService
LedServiceConfig = _led_service.LedServiceConfig
rc2idx = _led_service.rc2idx
serp = _led_service.serp
validate_lut = _led_service.validate_lut
COLOR_RGB = _led_service.COLOR_RGB


class FakeSerial:
    """Minimal serial stand-in: every written command is auto-acked (configurable)."""

    def __init__(self, ack: str = "OK"):
        self.written = []
        self.ack = ack
        self._buf = []
        self.closed = False

    def write(self, data: bytes):
        self.written.append(data.decode("ascii").strip())
        self._buf.append((self.ack + "\n").encode("ascii"))

    def readline(self) -> bytes:
        return self._buf.pop(0) if self._buf else b""

    def close(self):
        self.closed = True

    def seti_lines(self):
        return [w for w in self.written if w.startswith("SETI")]


class FakeClock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self) -> float:
        return self.t

    def advance(self, seconds: float) -> None:
        self.t += seconds


class HandshakeSerial(FakeSerial):
    """Serial fake with explicit pre-write input and BRIGHT response control."""

    def __init__(self, *, initial=(), bright_response=(), clock=None, read_advance=0.0):
        super().__init__()
        self._buf = [(line + "\n").encode("ascii") for line in initial]
        self.bright_response = list(bright_response)
        self.clock = clock
        self.read_advance = read_advance

    @property
    def in_waiting(self):
        return sum(len(line) for line in self._buf)

    def reset_input_buffer(self):
        self._buf.clear()

    def read(self, size=1):
        if self.clock is not None:
            self.clock.advance(self.read_advance)
        data = bytearray()
        while size and self._buf:
            line = self._buf[0]
            take = min(size, len(line))
            data.extend(line[:take])
            size -= take
            if take == len(line):
                self._buf.pop(0)
            else:
                self._buf[0] = line[take:]
        return bytes(data)

    def write(self, data: bytes):
        command = data.decode("ascii").strip()
        self.written.append(command)
        if command.startswith("BRIGHT"):
            self._buf.extend((line + "\n").encode("ascii") for line in self.bright_response)
        else:
            self._buf.append(b"OK\n")

    def readline(self) -> bytes:
        if self.clock is not None:
            self.clock.advance(self.read_advance)
        return self._buf.pop(0) if self._buf else b""


class PartialPrewriteSerial:
    """Serial fake whose partial stale input blocks readline until it is reset."""

    def __init__(self, clock):
        self.clock = clock
        self.partial_stale = True
        self.prewrite_reads = 0
        self.reset_calls = 0
        self.written = []
        self.closed = False
        self._responses = []

    @property
    def in_waiting(self):
        return 8 if self.partial_stale else 0

    def reset_input_buffer(self):
        self.reset_calls += 1
        self.partial_stale = False

    def read(self, size=1):
        if not self.partial_stale:
            return b""
        self.partial_stale = False
        return b"OK stale"[:size]

    def write(self, data: bytes):
        self.written.append(data.decode("ascii").strip())
        if self.written[-1].startswith("BRIGHT"):
            self._responses.append(b"ERR fresh-bright\n")

    def readline(self) -> bytes:
        if self.partial_stale and not self.written:
            self.prewrite_reads += 1
            self.clock.advance(5.0)
            return b""
        if self.partial_stale:
            self.partial_stale = False
            return b"OK stale\n"
        return self._responses.pop(0) if self._responses else b""

    def close(self):
        self.closed = True


class DelayedReadySerial:
    """Serial fake that emits READY only after the board's boot-settle delay."""

    def __init__(self, clock, *, ready_delay=0.25, bright_response=("OK bright",)):
        self.clock = clock
        self.ready_delay = ready_delay
        self.ready_sent = False
        self.reset_calls = 0
        self.write_times = []
        self.closed = False
        self._bright_response = list(bright_response)
        self._responses = []

    @property
    def in_waiting(self):
        return 0

    def reset_input_buffer(self):
        self.reset_calls += 1

    def write(self, data: bytes):
        command = data.decode("ascii").strip()
        self.write_times.append((command, self.clock()))
        self._responses.extend(self._bright_response if command.startswith("BRIGHT") else ["OK"])

    def readline(self) -> bytes:
        if not self.ready_sent:
            self.ready_sent = True
            self.clock.advance(self.ready_delay)
            return b"READY\n"
        if self._responses:
            return (self._responses.pop(0) + "\n").encode("ascii")
        self.clock.advance(min(2.0, self.timeout))
        return b""

    def close(self):
        self.closed = True


# --------------------------------------------------------------------------- #
# LUT (Appendix A)
# --------------------------------------------------------------------------- #


class TestLut:
    def test_eight_checkpoints(self):
        assert rc2idx(0, 0) == 0
        assert rc2idx(9, 0) == 99
        assert rc2idx(10, 0) == 100
        assert rc2idx(18, 9) == 189
        assert rc2idx(18, 10) == 190
        assert rc2idx(10, 18) == 270
        assert rc2idx(9, 18) == 271
        assert rc2idx(0, 18) == 360

    def test_bijective_over_361_points(self):
        assert validate_lut(rc2idx) is True

    def test_serp_helper(self):
        assert serp(0, 0, 10) == 1  # first row, left to right
        assert serp(1, 0, 10) == 20  # second row, right to left


class TestModuleIsolation:
    def test_leaf_import_does_not_replace_katrain_web_package(self):
        assert _web_package_after_leaf_import is _web_package_before


# --------------------------------------------------------------------------- #
# Service behaviour (fake serial)
# --------------------------------------------------------------------------- #


def _make_service(ack="OK", clock=None):
    fake = FakeSerial(ack=ack)
    svc = LedService(
        LedServiceConfig(enabled=True, serial_port="fake"), serial_factory=lambda: fake, clock=clock or (lambda: 0.0)
    )
    return svc, fake


def test_same_led_port_is_busy_until_owner_stops():
    port = f"led-{uuid.uuid4().hex}"
    first = LedService(LedServiceConfig(enabled=True, serial_port=port), serial_factory=FakeSerial)
    second_open_calls = []

    def second_factory():
        second_open_calls.append(True)
        return FakeSerial()

    second = LedService(LedServiceConfig(enabled=True, serial_port=port), serial_factory=second_factory)
    first.start()
    try:
        with pytest.raises(RuntimeError, match="[Bb]usy|occupied"):
            second.start()
        assert second_open_calls == []
    finally:
        first.stop()
    second.start()
    try:
        assert second.is_connected()
    finally:
        second.stop()


def test_different_led_ports_do_not_block_each_other():
    port = uuid.uuid4().hex
    first = LedService(LedServiceConfig(enabled=True, serial_port=f"{port}-1"), serial_factory=FakeSerial)
    second = LedService(LedServiceConfig(enabled=True, serial_port=f"{port}-2"), serial_factory=FakeSerial)
    first.start()
    try:
        second.start()
        assert second.is_connected()
    finally:
        second.stop()
        first.stop()


def test_failed_led_open_releases_port_for_another_service():
    port = f"led-{uuid.uuid4().hex}"

    def fail_open():
        raise OSError("serial unplugged")

    first = LedService(LedServiceConfig(enabled=True, serial_port=port), serial_factory=fail_open, clock=lambda: 0.0)
    first.start()
    try:
        assert not first.is_connected()
        second = LedService(LedServiceConfig(enabled=True, serial_port=port), serial_factory=FakeSerial)
        second.start()
        try:
            assert second.is_connected()
        finally:
            second.stop()
    finally:
        first.stop()


def test_led_reconnect_conflict_requires_explicit_stop_start_after_peer_releases():
    port = f"led-{uuid.uuid4().hex}"
    clock = FakeClock()
    clock.t = 0.0
    state = {"available": False, "open_calls": 0}

    def factory():
        state["open_calls"] += 1
        if not state["available"]:
            raise OSError("serial unplugged")
        return FakeSerial()

    first = LedService(LedServiceConfig(enabled=True, serial_port=port), serial_factory=factory, clock=clock)
    peer = LedService(LedServiceConfig(enabled=True, serial_port=port), serial_factory=FakeSerial)
    first.start()
    peer.start()
    try:
        state["available"] = True
        clock.advance(10)
        assert first.clear(strict=True)["ok"] is False  # Worker reconnect encounters the peer's lease.
        peer.stop()
        clock.advance(10)

        assert first.clear(strict=True)["ok"] is False
        assert first.is_connected() is False
        assert state["open_calls"] == 1

        first.stop()
        first.start()
        assert first.clear(strict=True)["ok"] is True
        assert state["open_calls"] == 2
    finally:
        peer.stop()
        first.stop()


def test_led_stop_keeps_lease_until_blocked_reconnect_finishes(monkeypatch):
    port = f"led-{uuid.uuid4().hex}"
    reconnect_entered = threading.Event()
    reconnect_resume = threading.Event()
    fake = FakeSerial()
    calls = []

    def factory():
        calls.append(True)
        if len(calls) == 1:
            raise OSError("serial unplugged")
        reconnect_entered.set()
        assert reconnect_resume.wait(timeout=5)
        return fake

    first = LedService(LedServiceConfig(enabled=True, serial_port=port), serial_factory=factory)
    peer = LedService(LedServiceConfig(enabled=True, serial_port=port), serial_factory=FakeSerial)
    first.start()
    worker = first._thread
    original_join = worker.join
    try:
        assert reconnect_entered.wait(timeout=2)
        monkeypatch.setattr(first, "clear", lambda **kwargs: {"ok": False})
        monkeypatch.setattr(worker, "join", lambda timeout=None: original_join(timeout=0.01))
        first.stop()

        with pytest.raises(RuntimeError, match="[Bb]usy|occupied"):
            peer.start()
        assert first.is_connected() is False

        reconnect_resume.set()
        original_join(timeout=2)
        assert not worker.is_alive()
        assert fake.closed is True
        assert fake.written == []
        assert first.is_connected() is False
        peer.start()
        assert peer.is_connected() is True
    finally:
        reconnect_resume.set()
        original_join(timeout=2)
        peer.stop()
        first.stop()


def test_led_explicit_restart_discards_previous_worker_stop_sentinel(monkeypatch):
    entered = threading.Event()
    resume = threading.Event()

    class BlockedSerial(FakeSerial):
        def write(self, data):
            if data == b"CLEAR\n" and not resume.is_set():
                entered.set()
                assert resume.wait(timeout=5)
            super().write(data)

    serials = [BlockedSerial(), FakeSerial()]
    svc = LedService(
        LedServiceConfig(enabled=True, serial_port=f"led-{uuid.uuid4().hex}"),
        serial_factory=lambda: serials.pop(0),
    )
    svc.start()
    worker = svc._thread
    original_join = worker.join
    original_clear = svc.clear
    try:
        svc.set_points([], strict=False)
        assert entered.wait(timeout=2)
        monkeypatch.setattr(svc, "clear", lambda **kwargs: {"ok": False})
        monkeypatch.setattr(worker, "join", lambda timeout=None: original_join(timeout=0.01))
        svc.stop()
        resume.set()
        original_join(timeout=2)
        assert not worker.is_alive()
        assert svc._queue.qsize() == 1  # Stop sentinel was never consumed by the old worker.

        monkeypatch.setattr(svc, "clear", original_clear)
        svc.start()
        assert svc.clear(strict=True)["ok"] is True
    finally:
        resume.set()
        original_join(timeout=2)
        monkeypatch.setattr(svc, "clear", lambda **kwargs: {"ok": False})
        svc.stop()


def test_led_worker_start_failure_releases_port(monkeypatch):
    port = f"led-{uuid.uuid4().hex}"
    first = LedService(LedServiceConfig(enabled=True, serial_port=port), serial_factory=FakeSerial)
    original_start = threading.Thread.start

    def fail_thread_start(_thread):
        raise RuntimeError("worker could not start")

    monkeypatch.setattr(threading.Thread, "start", fail_thread_start)
    with pytest.raises(RuntimeError, match="worker could not start"):
        first.start()
    monkeypatch.setattr(threading.Thread, "start", original_start)

    second = LedService(LedServiceConfig(enabled=True, serial_port=port), serial_factory=FakeSerial)
    second.start()
    try:
        assert second.is_connected()
    finally:
        second.stop()


def test_led_port_lease_blocks_another_process():
    port = f"led-{uuid.uuid4().hex}"
    first = LedService(LedServiceConfig(enabled=True, serial_port=port), serial_factory=FakeSerial)
    script = """import sys
from katrain.web.core.device_lease import DeviceBusy, DeviceLease
try:
    lease = DeviceLease.acquire('led', sys.argv[1])
except DeviceBusy:
    sys.exit(0)
else:
    lease.release()
    sys.exit(1)
"""
    first.start()
    try:
        result = subprocess.run([sys.executable, "-c", script, port], capture_output=True, text=True, timeout=5)
        assert result.returncode == 0, result.stderr
    finally:
        first.stop()


class TestColorsAndProtocol:
    def test_rgb_frame_can_show_blackout_and_new_points_in_one_batch(self):
        svc, fake = _make_service()
        svc.start()
        try:
            result = svc.set_rgb_points(
                [{"row": 3, "col": 16, "rgb": (0, 96, 0)}],
                strict=True,
                blank_before=True,
            )
            assert result["ok"] is True
            assert fake.written[3:8] == ["CLEAR", "SHOW", "CLEAR", f"SETI {rc2idx(3, 16)} 0 96 0", "SHOW"]
        finally:
            svc.stop()

    def test_set_rgb_points_emits_exact_calibration_rgb(self):
        svc, fake = _make_service()
        svc.start()
        try:
            result = svc.set_rgb_points([{"row": 3, "col": 16, "rgb": (0, 96, 0)}], strict=True)
        finally:
            svc.stop()

        assert result["ok"] is True
        assert f"SETI {rc2idx(3, 16)} 0 96 0" in fake.seti_lines()

    def test_start_uses_visible_default_brightness(self):
        svc, fake = _make_service()

        svc.start()
        try:
            assert "BRIGHT 255" in fake.written
        finally:
            svc.stop()

    def test_set_points_emits_clear_seti_show_with_colors(self):
        svc, fake = _make_service()
        svc.start()
        try:
            res = svc.set_points(
                [{"row": 0, "col": 0, "color": "black"}, {"row": 0, "col": 18, "color": "white"}],
                strict=True,
            )
        finally:
            svc.stop()
        assert res["ok"] is True
        # black -> red (255,0,0) at idx 0 ; white -> green (0,255,0) at idx 360
        seti = fake.seti_lines()
        assert "SETI 0 255 0 0" in seti
        assert "SETI 360 0 255 0" in seti
        assert "CLEAR" in fake.written and "SHOW" in fake.written

    def test_remove_color_is_blue(self):
        assert COLOR_RGB["remove"] == (0, 0, 255)
        svc, fake = _make_service()
        svc.start()
        try:
            svc.set_points([{"row": 5, "col": 5, "color": "remove"}], strict=True)
        finally:
            svc.stop()
        idx = rc2idx(5, 5)
        assert f"SETI {idx} 0 0 255" in fake.seti_lines()

    def test_hint_color_maps_to_white(self):
        svc, fake = _make_service()
        svc.start()
        try:
            svc.set_points([{"row": 0, "col": 0, "color": "hint"}], strict=True)
        finally:
            svc.stop()
        assert fake.seti_lines() == ["SETI 0 255 255 255"]  # rc2idx(0,0)=0

    def test_out_of_range_points_skipped(self):
        svc, fake = _make_service()
        svc.start()
        try:
            svc.set_points(
                [{"row": 99, "col": 0, "color": "black"}, {"row": 1, "col": 1, "color": "black"}], strict=True
            )
        finally:
            svc.stop()
        assert len(fake.seti_lines()) == 1  # only the in-range point


class BootFakeSerial(FakeSerial):
    """Like FakeSerial but emits a boot 'READY' banner before the first ack,
    so the BRIGHT-ack drain in _open_serial must consume both READY and the OK."""

    def __init__(self, ack: str = "OK"):
        super().__init__(ack=ack)
        self._buf.append(b"READY\n")


class TestAckPairing:
    def test_boot_banner_and_bright_ack_consumed_so_show_ack_pairs(self):
        # Regression: if BRIGHT's ack (or the boot READY) leaked into the buffer,
        # _send_and_ack would mis-pair and SHOW's ack would never be seen.
        clock = FakeClock()
        fake = BootFakeSerial()
        svc = LedService(LedServiceConfig(enabled=True, serial_port="fake"), serial_factory=lambda: fake, clock=clock)
        svc.start()
        try:
            res = svc.set_points([{"row": 3, "col": 3, "color": "black"}], strict=True)
        finally:
            svc.stop()
        assert res["ok"] is True
        assert res["shown_at"] == clock.t  # SHOW correctly acked → barrier timestamp set


class TestConnectionHandshake:
    def test_default_serial_read_timeout_matches_handshake_deadline(self, monkeypatch):
        calls = []
        expected = object()

        def serial_constructor(*args, **kwargs):
            calls.append((args, kwargs))
            return expected

        monkeypatch.setitem(sys.modules, "serial", SimpleNamespace(Serial=serial_constructor))
        svc = LedService(LedServiceConfig(serial_port="tty-test", baud_rate=57600, handshake_timeout=1.25))

        assert svc._default_serial_factory() is expected
        assert calls == [(("tty-test", 57600), {"timeout": 1.25, "write_timeout": 0.2})]

    def test_stale_ok_is_drained_before_fresh_bright_ok_connects(self):
        clock = FakeClock()
        fake = HandshakeSerial(initial=("READY", "OK stale"), bright_response=("OK bright",), clock=clock)
        svc = LedService(
            LedServiceConfig(enabled=True, serial_port="fake", handshake_timeout=1.0),
            serial_factory=lambda: fake,
            clock=clock,
        )

        svc._open_serial()

        assert svc.is_connected() is True
        assert fake.written == ["CLEAR", "SHOW", "BRIGHT 255"]
        assert fake._buf == []
        svc._close_serial()

    def test_delayed_ready_precedes_bright_and_fresh_ok_connects(self):
        clock = FakeClock()
        fake = DelayedReadySerial(clock)
        svc = LedService(
            LedServiceConfig(enabled=True, serial_port="fake", handshake_timeout=1.0),
            serial_factory=lambda: fake,
            clock=clock,
        )

        svc._open_serial()

        assert fake.reset_calls == 3
        assert fake.write_times == [("CLEAR", 1000.25), ("SHOW", 1000.25), ("BRIGHT 255", 1000.25)]
        assert svc.is_connected() is True
        svc._close_serial()

    def test_ready_banner_does_not_replace_postwrite_ok(self):
        clock = FakeClock()
        fake = DelayedReadySerial(clock, bright_response=("READY still booting",))
        svc = LedService(
            LedServiceConfig(enabled=True, serial_port="fake", handshake_timeout=1.0),
            serial_factory=lambda: fake,
            clock=clock,
        )

        svc._open_serial()

        assert fake.write_times == [("CLEAR", 1000.25), ("SHOW", 1000.25), ("BRIGHT 255", 1000.25)]
        assert svc.is_connected() is False
        assert fake.closed is True

    def test_partial_prewrite_input_is_nonblocking_and_cannot_authenticate(self):
        clock = FakeClock()
        fake = PartialPrewriteSerial(clock)
        svc = LedService(
            LedServiceConfig(enabled=True, serial_port="fake", handshake_timeout=1.0),
            serial_factory=lambda: fake,
            clock=clock,
        )

        svc._open_serial()

        assert fake.reset_calls == 1
        assert fake.prewrite_reads == 0
        assert clock.t == 1000.0
        assert fake.written == ["CLEAR"]
        assert svc.is_connected() is False

    def test_bright_err_closes_without_connecting(self):
        fake = HandshakeSerial(bright_response=("ERR bad brightness",))
        svc = LedService(
            LedServiceConfig(enabled=True, serial_port="fake", handshake_timeout=1.0),
            serial_factory=lambda: fake,
            clock=FakeClock(),
        )

        svc._open_serial()

        assert svc.is_connected() is False
        assert svc._serial is None
        assert fake.closed is True

    def test_no_bright_ack_closes_without_connecting(self):
        clock = FakeClock()
        fake = HandshakeSerial(clock=clock, read_advance=0.5)
        svc = LedService(
            LedServiceConfig(enabled=True, serial_port="fake", handshake_timeout=1.0),
            serial_factory=lambda: fake,
            clock=clock,
        )

        svc._open_serial()

        assert svc.is_connected() is False
        assert svc._serial is None
        assert fake.closed is True

    def test_ok_arriving_after_deadline_does_not_connect(self):
        clock = FakeClock()
        fake = HandshakeSerial(bright_response=("OK late",), clock=clock, read_advance=1.1)
        svc = LedService(
            LedServiceConfig(enabled=True, serial_port="fake", handshake_timeout=1.0),
            serial_factory=lambda: fake,
            clock=clock,
        )

        svc._open_serial()

        assert svc.is_connected() is False
        assert svc._serial is None
        assert fake.closed is True

    def test_bright_write_exception_closes_without_connecting(self):
        fake = HandshakeSerial()

        def fail_write(_data):
            raise OSError("write failed")

        fake.write = fail_write
        svc = LedService(
            LedServiceConfig(enabled=True, serial_port="fake"), serial_factory=lambda: fake, clock=FakeClock()
        )

        svc._open_serial()

        assert svc.is_connected() is False
        assert svc._serial is None
        assert fake.closed is True

    def test_bright_read_exception_closes_without_connecting(self):
        fake = HandshakeSerial()

        def fail_read(size=1):
            raise OSError("read failed")

        fake.read = fail_read
        svc = LedService(
            LedServiceConfig(enabled=True, serial_port="fake"), serial_factory=lambda: fake, clock=FakeClock()
        )

        svc._open_serial()

        assert svc.is_connected() is False
        assert svc._serial is None
        assert fake.closed is True


class TestStrictPath:
    def test_strict_returns_shown_at_after_show_ok(self):
        clock = FakeClock()
        svc, fake = _make_service(clock=clock)
        svc.start()
        try:
            res = svc.set_points([{"row": 3, "col": 3, "color": "black"}], strict=True)
        finally:
            svc.stop()
        assert res["ok"] is True
        assert res["shown_at"] == clock.t  # set when SHOW acked

    def test_strict_reports_failure_on_err(self):
        svc, fake = _make_service(ack="ERR bad")
        svc.start()
        try:
            res = svc.set_points([{"row": 3, "col": 3, "color": "black"}], strict=True)
        finally:
            svc.stop()
        assert res["ok"] is False
        assert res["errors"]


class TestQueueAndConnection:
    def test_non_strict_drops_when_full_without_raising(self):
        # Do NOT start the worker, so nothing drains the queue.
        svc, _ = _make_service()
        results = [svc.set_points([{"row": 0, "col": 0, "color": "black"}], strict=False) for _ in range(25)]
        assert all(r["ok"] for r in results)  # never raises / blocks
        assert svc._queue.qsize() <= 10  # bounded

    def test_strict_when_disconnected_returns_not_ok(self):
        def boom():
            raise OSError("no device")

        svc = LedService(LedServiceConfig(enabled=True, serial_port="fake"), serial_factory=boom, clock=lambda: 0.0)
        svc.start()
        try:
            res = svc.set_points([{"row": 0, "col": 0, "color": "black"}], strict=True)
        finally:
            svc.stop()
        assert res["ok"] is False
        assert svc.is_connected() is False

    def test_reconnect_after_initial_failure(self):
        clock = FakeClock()
        state = {"fail": True}
        fake = FakeSerial()

        def factory():
            if state["fail"]:
                raise OSError("not yet")
            return fake

        svc = LedService(
            LedServiceConfig(enabled=True, serial_port="fake"),
            serial_factory=factory,
            clock=clock,
            reconnect_interval=5.0,
        )
        svc.start()
        try:
            assert svc.is_connected() is False
            state["fail"] = False
            clock.t += 10  # advance past reconnect interval
            # give the idle worker loop a moment to attempt reconnect
            for _ in range(50):
                if svc.is_connected():
                    break
                threading.Event().wait(0.02)
            assert svc.is_connected() is True
        finally:
            svc.stop()

    def test_missing_pyserial_disables_permanently_without_retry(self):
        # pyserial not installed -> ImportError is permanent (unlike a transient
        # OSError device hiccup): open once, then never retry / re-log.
        clock = FakeClock()
        state = {"attempts": 0}
        fake = FakeSerial()

        def factory():
            state["attempts"] += 1
            if state["attempts"] == 1:
                raise ImportError("No module named 'serial'")
            return fake  # would "recover" if wrongly retried — it must not

        svc = LedService(
            LedServiceConfig(enabled=True, serial_port="fake"),
            serial_factory=factory,
            clock=clock,
            reconnect_interval=5.0,
        )
        svc.start()
        try:
            assert svc.is_connected() is False
            assert svc._serial_unavailable is True
            clock.t += 100  # well past any reconnect interval
            for _ in range(20):
                threading.Event().wait(0.02)
            assert svc.is_connected() is False
            assert state["attempts"] == 1  # never retried
        finally:
            svc.stop()


class SequencedReplySerial(FakeSerial):
    """Like FakeSerial, but each write consumes the next scripted reply before
    falling back to the default ack — lets a test script a firmware ERR into the
    middle of a batch (e.g. MAX_ON exceeded) without every command failing."""

    def __init__(self, replies, ack: str = "OK"):
        super().__init__(ack=ack)
        self._replies = list(replies)

    def write(self, data: bytes):
        self.written.append(data.decode("ascii").strip())
        reply = self._replies.pop(0) if self._replies else self.ack
        self._buf.append((reply + "\n").encode("ascii"))


class TestNonStrictErrorSurfacing:
    def test_non_strict_batch_logs_firmware_errors_instead_of_swallowing_them(self, caplog):
        """MAX_ON=200:第 201 颗起固件回 ERR maxon。非严格路径以前把它们存进
        没人读的对象、一行日志都不打 —— HTTP 说 ok,盘上半块不亮。"""
        # start() writes CLEAR, SHOW, BRIGHT (handshake), THEN set_points([one point])
        # emits CLEAR, SETI, SHOW — script the SETI ack as the firmware error while
        # BRIGHT/CLEAR/SHOW all still ack OK.
        fake = SequencedReplySerial(replies=["OK", "OK", "OK", "OK", "ERR maxon", "OK"])
        svc = LedService(
            LedServiceConfig(enabled=True, serial_port="fake"), serial_factory=lambda: fake, clock=lambda: 0.0
        )
        svc.start()
        try:
            with caplog.at_level(logging.WARNING):
                svc.set_points([{"row": 0, "col": 0, "color": "green"}], strict=False)

                # Non-strict returns before the worker thread has run the batch;
                # wait (bounded) for it to actually finish instead of a fixed sleep.
                deadline = time.monotonic() + 2.0
                while time.monotonic() < deadline and not svc.last_errors:
                    time.sleep(0.005)

            assert any("ERR maxon" in record.message for record in caplog.records)
            assert len(svc.last_errors) == 1
            assert "ERR maxon" in svc.last_errors[0]
            assert svc.last_errors[0].startswith("SETI")  # the errored command, not just its ack
        finally:
            svc.stop()


class ErrorThenRaiseSerial(FakeSerial):
    """First batch's SETI acks a clean firmware ERR (an OK/ERR protocol response,
    handled inside _run_batch); every write after that raises instead (an actual
    serial exception, handled by _worker's except-Exception path). Lets a test
    prove last_errors reflects the CURRENT batch across BOTH finish paths, not
    just whichever one happened to populate it first."""

    def __init__(self):
        super().__init__(ack="OK")
        self._first_batch_replies = ["OK", "OK", "OK", "OK", "ERR maxon", "OK"]  # handshake, CLEAR, SETI, SHOW
        self.raise_after_first_batch = False

    def write(self, data: bytes):
        if self.raise_after_first_batch:
            raise OSError("device disconnected")
        self.written.append(data.decode("ascii").strip())
        reply = self._first_batch_replies.pop(0) if self._first_batch_replies else self.ack
        self._buf.append((reply + "\n").encode("ascii"))


class TestLastErrorsAggregatesAllFinishPaths:
    def test_serial_exception_batch_overwrites_last_errors_from_a_prior_firmware_error(self):
        """Regression (code review F2): last_errors used to be set only inside
        _run_batch's own success/firmware-error path, so a batch that instead hit
        the WORKER's except-Exception path (a real serial exception, e.g. the
        board disconnecting) left /led/status reporting the earlier batch's stale
        firmware error forever — exactly when the user most needs to know the
        board just went dark. Proven by running an errored batch, THEN a raising
        batch, and asserting last_errors moved to the second batch's content
        (not just "is non-empty", which can't tell an update from a coincidence)."""
        fake = ErrorThenRaiseSerial()
        svc = LedService(
            LedServiceConfig(enabled=True, serial_port="fake"), serial_factory=lambda: fake, clock=lambda: 0.0
        )
        svc.start()
        try:
            # Batch 1: a clean firmware error (SETI -> ERR maxon).
            svc.set_points([{"row": 0, "col": 0, "color": "green"}], strict=False)
            deadline = time.monotonic() + 2.0
            while time.monotonic() < deadline and not svc.last_errors:
                time.sleep(0.005)
            assert svc.last_errors and "ERR maxon" in svc.last_errors[0]  # sanity: batch 1 landed

            # Batch 2: a real serial exception, not a scripted ERR ack.
            fake.raise_after_first_batch = True
            svc.set_points([{"row": 1, "col": 1, "color": "green"}], strict=False)
            deadline = time.monotonic() + 2.0
            while time.monotonic() < deadline and "device disconnected" not in "".join(svc.last_errors):
                time.sleep(0.005)

            assert svc.last_errors == ["device disconnected"]  # batch 2's content, not batch 1's leftover
        finally:
            fake.raise_after_first_batch = False  # let stop()'s clear(strict=True) succeed cleanly
            svc.stop()


# ---------------------------------------------------------------- guidance brightness (ambient loop, 2026-09-22)


def _capturing_service():
    svc = LedService(LedServiceConfig(), serial_factory=lambda: FakeSerial())
    sent = []
    svc._submit = lambda commands, strict, **kwargs: sent.append(list(commands)) or {"ok": True}
    return svc, sent


def test_guidance_brightness_scales_every_lamp_and_never_turns_a_lit_channel_off():
    svc, sent = _capturing_service()
    svc.set_guidance_scale(0.5)
    svc.set_points(
        [
            {"row": 3, "col": 3, "color": "white"},
            {"row": 4, "col": 4, "color": "hint"},
            {"row": 5, "col": 5, "color": "black"},
        ]
    )
    assert sent[-1][1] == f"SETI {rc2idx(3, 3)} 0 128 0"
    assert sent[-1][2] == f"SETI {rc2idx(4, 4)} 128 128 128"
    assert sent[-1][3] == f"SETI {rc2idx(5, 5)} 128 0 0"
    svc.set_guidance_scale(0.0)  # clamped to the floor; a lit channel stays lit
    svc.set_points([{"row": 3, "col": 3, "color": "white"}])
    green = int(sent[-1][1].split()[3])
    assert green == round(255 * _led_service.MIN_GUIDANCE_SCALE) and green >= 1


def test_changing_the_brightness_reshows_the_lit_guidance_and_nothing_after_a_clear():
    svc, sent = _capturing_service()
    svc.set_points([{"row": 15, "col": 15, "color": "white"}])
    svc.set_guidance_scale(0.25)
    assert sent[-1] == ["CLEAR", f"SETI {rc2idx(15, 15)} 0 64 0", "SHOW"]
    svc.clear()
    count = len(sent)
    svc.set_guidance_scale(1.0)
    assert len(sent) == count  # nothing lit, nothing re-shown


def test_calibration_lamps_are_never_scaled():
    svc, sent = _capturing_service()
    svc.set_guidance_scale(0.25)
    svc.set_rgb_points([{"row": 9, "col": 9, "rgb": (0, 255, 0)}])
    assert sent[-1][1] == f"SETI {rc2idx(9, 9)} 0 255 0"


class LinkSerial(FakeSerial):
    """Production LINK emits one standalone status line, without an OK."""

    def __init__(self, response, clock):
        super().__init__()
        self.response = response
        self.clock = clock
        self.timeout = 2.0
        self.read_timeouts = []
        self.late = None
        self.command_threads = []

    def reset_input_buffer(self):
        self._buf.clear()

    def write(self, data):
        command = data.decode("ascii").strip()
        self.command_threads.append(threading.current_thread().name)
        self.written.append(command)
        if command == "LINK":
            if self.response:
                self._buf.append((self.response + "\n").encode("ascii"))
        else:
            if self.late:
                self._buf.append((self.late + "\n").encode("ascii"))
                self.late = None
            self._buf.append(b"OK\n")

    def readline(self):
        self.read_timeouts.append(self.timeout)
        if not self._buf:
            self.clock.advance(self.timeout)
        return super().readline()

    def read(self, size=1):
        self.read_timeouts.append(self.timeout)
        if not self._buf:
            self.clock.advance(self.timeout)
            return b""
        data = self._buf[0][:size]
        self._buf[0] = self._buf[0][size:]
        if not self._buf[0]:
            self._buf.pop(0)
        return data


def _link_service(response):
    clock = FakeClock()
    serial = LinkSerial(response, clock)
    svc = LedService(LedServiceConfig(enabled=True, serial_port="fake"), clock=clock)
    svc._serial = serial
    svc._connected = True  # Board B handshake succeeded, independently of Board A.
    return svc, serial, clock


def _link_line(cc="RD", ack="OK", link="UP"):
    return f"LINK cc={cc} cc_raw=1234 cc_mv=1500 ack={ack} ack_raw=3000 ack_mv=2900 link={link}"


@pytest.mark.parametrize(
    "cc,ack,link,expected",
    [
        ("RD", "OK", "UP", True),
        ("RA", "OK", "UP", True),
        ("OPEN", "OK", "UP", True),
        ("OPEN", "ABSENT", "DOWN", False),
        ("OPEN", "WEAK", "DOWN", False),
        ("RD", "WEAK", "CABLE_ONLY", False),
        ("RA", "ABSENT", "CABLE_ONLY", False),
    ],
)
def test_board_a_status_uses_firmware_ack_priority(cc, ack, link, expected):
    svc, serial, clock = _link_service(_link_line(cc, ack, link))
    assert svc.is_board_connected() is None
    svc._poll_board_link()
    assert svc.is_connected() is True
    assert svc.is_board_connected() is expected
    assert svc.board_status() == {"connected": expected, "board_link": link, "cc": cc, "ack": ack}
    assert serial.timeout == 2.0
    assert serial.read_timeouts
    assert all(0 < timeout <= 0.2 + 0.0001 for timeout in serial.read_timeouts)
    writes = list(serial.written)
    clock.advance(6.1)
    assert svc.is_board_connected() is None
    assert serial.written == writes  # Status getters never touch serial.


@pytest.mark.parametrize(
    "response",
    [
        "",
        "ERR cmd",
        "LINK cc=RD ack=OK link=UP",
        _link_line("RD", "ABSENT", "UP"),
        _link_line("OPEN", "OK", "DOWN"),
        _link_line("OPEN", "ABSENT", "CABLE_ONLY"),
        _link_line("RD", "ABSENT", "DOWN"),
        _link_line("UNKNOWN", "OK", "UP"),
        _link_line("RD", "UNKNOWN", "UP"),
        _link_line("RD", "OK", "UNKNOWN"),
        _link_line().replace("ack_raw=3000", "ack_raw=bad"),
    ],
)
def test_board_a_missing_or_invalid_status_is_unknown(response):
    svc, serial, clock = _link_service(response)
    svc._poll_board_link()
    assert svc.is_board_connected() is None
    assert svc.is_connected() is True
    assert serial.timeout == 2.0
    assert clock() <= 1000.2 + 0.0001


def test_board_a_cache_invalidates_on_failure_disconnect_and_reopen():
    svc, serial, _ = _link_service(_link_line())
    svc._poll_board_link()
    assert svc.is_board_connected() is True
    serial.response = "ERR cmd"
    svc._poll_board_link()
    assert svc.is_board_connected() is None
    serial.response = _link_line()
    svc._poll_board_link()
    svc._close_serial()
    assert svc.is_board_connected() is None
    replacement = FakeSerial()
    svc._serial_factory = lambda: replacement
    svc._open_serial()
    try:
        assert svc.is_connected() is True
        assert svc.is_board_connected() is None
    finally:
        svc._close_serial()


def test_next_link_poll_discards_buffered_late_status_instead_of_refreshing_it():
    svc, serial, _ = _link_service("")
    svc._poll_board_link()
    serial._buf.append((_link_line() + "\n").encode("ascii"))
    serial.response = _link_line("OPEN", "ABSENT", "DOWN")
    svc._poll_board_link()
    assert svc.is_board_connected() is False


def test_link_read_budget_is_total_even_when_bytes_arrive_slowly():
    svc, serial, clock = _link_service(_link_line())

    def read_one(_size):
        # A partial line trickles in; each byte uses some of the remaining budget.
        clock.advance(min(serial.timeout, 0.08))
        return b"L"

    def unbounded_readline():
        clock.advance(1.0)
        return (_link_line() + "\n").encode("ascii")

    serial.read = read_one
    serial.readline = unbounded_readline
    svc._poll_board_link()
    assert svc.is_board_connected() is None
    assert clock() <= 1000.2 + 0.0001
    assert serial.timeout == 2.0


@pytest.mark.parametrize("late", [_link_line(), "ERR cmd"])
def test_late_link_response_does_not_consume_clear_or_show_ack(late):
    svc, serial, _ = _link_service("")
    svc._poll_board_link()
    serial.late = late
    batch = _led_service._Batch(["CLEAR", "SETI 0 255 0 0", "SHOW"], strict=True)
    svc._run_batch(batch)
    assert batch.result["ok"] is True
    assert batch.result["shown_at"] is not None
    assert svc.is_board_connected() is None
    assert serial.written == ["LINK", "CLEAR", "SETI 0 255 0 0", "SHOW"]


@pytest.mark.parametrize("show_ack", [False, True])
@pytest.mark.parametrize("tail_reads", [1, 2])
def test_truncated_link_ack_tail_cannot_shift_command_acknowledgements(show_ack, tail_reads):
    svc, serial, clock = _link_service("")
    prefix, tail = _link_line().split("ack=", 1)

    def write(data):
        command = data.decode("ascii").strip()
        serial.written.append(command)
        if command == "LINK":
            serial._buf.append((prefix + "ack=").encode("ascii"))  # No newline before the 200ms deadline.
        elif command == "CLEAR":
            if tail_reads == 2:
                serial._buf.append(b"OK")  # The late tail can itself span a read timeout.
                remaining_tail = tail[2:]
            else:
                remaining_tail = tail
            serial._buf.extend([(remaining_tail + "\n").encode("ascii"), b"OK\n"])
        elif command != "SHOW" or show_ack:
            serial._buf.append(b"OK\n")

    serial.write = write
    svc._poll_board_link()
    assert svc.is_board_connected() is None
    assert clock() <= 1000.2 + 0.0001
    assert serial.timeout == 2.0
    batch = _led_service._Batch(["CLEAR", "SETI 0 255 0 0", "SHOW"], strict=True)
    svc._run_batch(batch)
    assert batch.result["ok"] is show_ack
    if show_ack:
        assert batch.result["shown_at"] is not None
        assert batch.result["errors"] == []
        assert serial._buf == []  # SHOW consumed its own ACK, not a shifted earlier one.
    else:
        assert batch.result["shown_at"] is None
        assert batch.result["errors"] == ["SHOW -> no-ack"]


@pytest.mark.parametrize("response,poll_interval", [(_link_line(), 2.0), ("ERR cmd", 10.0)])
def test_worker_polls_link_between_complete_batches_and_backs_off_old_firmware(response, poll_interval):
    svc, serial, clock = _link_service(response)
    first = _led_service._Batch(["CLEAR", "SETI 0 255 0 0", "SHOW"], strict=True)
    second = _led_service._Batch(["CLEAR", "SHOW"], strict=True)
    svc._queue.put(first)
    svc._queue.put(second)
    worker = threading.Thread(target=svc._worker, name="led-serial")
    worker.start()
    try:
        assert first.event.wait(1)
        assert second.event.wait(1)
        deadline = time.monotonic() + 1
        while serial.written.count("LINK") < 1 and time.monotonic() < deadline:
            time.sleep(0.01)
        assert serial.written == ["CLEAR", "SETI 0 255 0 0", "SHOW", "LINK", "CLEAR", "SHOW"]
        clock.advance(poll_interval - 0.1)
        time.sleep(0.25)
        assert serial.written.count("LINK") == 1
        clock.advance(0.2)
        deadline = time.monotonic() + 1
        while serial.written.count("LINK") < 2 and time.monotonic() < deadline:
            time.sleep(0.01)
        assert serial.written.count("LINK") == 2
        assert set(serial.command_threads) == {"led-serial"}
    finally:
        svc._stop.set()
        svc._queue.put(_led_service._SENTINEL)
        worker.join(timeout=1)


# Hot-plug recovery: all protocol checks use fake ports, never physical devices.


def test_reconnect_blackouts_retained_frame_before_bright_can_render_it():
    fake = FakeSerial()
    svc = LedService(LedServiceConfig(serial_port=f"led-{uuid.uuid4().hex}"), serial_factory=lambda: fake)
    try:
        svc._open_serial()
        assert svc.is_connected()
        assert fake.written == ["CLEAR", "SHOW", "BRIGHT 255"]
    finally:
        svc._close_serial()


def test_no_ack_aborts_before_seti_and_show_and_disconnects_transport():
    svc, serial, _ = _link_service(_link_line())
    serial.ack = ""
    serial.write = lambda data: serial.written.append(data.decode().strip())
    batch = _led_service._Batch(["CLEAR", "SETI 0 255 0 0", "SHOW"], strict=True)
    svc._run_batch(batch)
    assert serial.written == ["CLEAR"]
    assert batch.result["ok"] is False
    assert batch.result["connected"] is False
    assert serial.closed


@pytest.mark.parametrize("response", ["", "LINK invalid"])
def test_idle_silent_link_closes_after_three_failures_but_legacy_err_keeps_transport(response):
    svc, serial, clock = _link_service(response)
    for failure in range(3):
        svc._poll_board_link()
        if failure < 2:
            assert svc.is_connected()
            assert svc._next_link_poll == pytest.approx(clock() + 2.0)
    assert not svc.is_connected()
    assert serial.closed

    svc, serial, clock = _link_service("ERR cmd")
    for _ in range(4):
        svc._poll_board_link()
        assert svc.is_connected()
        assert svc._next_link_poll == pytest.approx(clock() + 10.0)
    svc._close_serial()


def test_due_link_poll_is_not_starved_by_queued_batches():
    svc, serial, _ = _link_service(_link_line())
    svc._queue.put(_led_service._Batch(["CLEAR", "SHOW"], strict=False))
    svc._maybe_poll_board_link()
    assert serial.written == ["LINK"]
    svc._close_serial()


def test_reconnected_transport_rejects_old_capture_batch():
    svc, serial, _ = _link_service(_link_line())
    svc._submit(["CLEAR", "SETI 0 255 0 0", "SHOW"], strict=False)
    old = svc._queue.get_nowait()
    svc._close_serial()
    replacement = FakeSerial()
    svc._serial_factory = lambda: replacement
    try:
        svc._open_serial()
        handshake = list(replacement.written)
        svc._run_batch(old)
        assert old.result["ok"] is False
        assert replacement.written == handshake
    finally:
        svc._close_serial()


def test_board_a_up_refreshes_current_guidance_once_without_reopening_board_b():
    svc, serial, _ = _link_service(_link_line("OPEN", "ABSENT", "DOWN"))
    svc._poll_board_link()
    svc.set_points([{"row": 1, "col": 1, "color": "white"}])
    svc._run_batch(svc._queue.get_nowait())
    serial.written.clear()
    serial.response = _link_line()
    svc._poll_board_link()
    assert serial.written == ["LINK", "CLEAR", f"SETI {rc2idx(1, 1)} 0 255 0", "SHOW"]
    serial.written.clear()
    svc._poll_board_link()
    assert serial.written == ["LINK"]
    assert svc._serial is serial
    svc._close_serial()


@pytest.mark.parametrize("replacement", ["clear", "rgb", "strict"])
def test_recovery_and_brightness_never_resurrect_replaced_guidance(replacement):
    svc, sent = _capturing_service()
    svc.set_points([{"row": 1, "col": 1, "color": "white"}])
    if replacement == "clear":
        svc.clear()
    elif replacement == "rgb":
        svc.set_rgb_points([{"row": 2, "col": 2, "rgb": (0, 50, 0)}])
    else:
        svc.set_points([{"row": 2, "col": 2, "color": "black"}], strict=True)
    previous = list(sent)
    svc.set_guidance_scale(0.5)
    assert sent == previous


def test_missing_linux_alias_uses_stat_and_reappearance_bypasses_reconnect_cooldown(monkeypatch):
    clock = FakeClock()
    available = {"present": False}
    calls = []
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(os.path, "exists", lambda path: available["present"])
    svc = LedService(
        LedServiceConfig(serial_port="/dev/serial/by-id/test-board"),
        serial_factory=lambda: calls.append(clock()) or FakeSerial(),
        clock=clock,
    )
    try:
        svc._open_serial()
        for _ in range(5):
            svc._maybe_reconnect()
        assert calls == []
        available["present"] = True
        clock.advance(0.2)
        svc._maybe_reconnect()
        assert len(calls) == 1
        assert svc.is_connected()
    finally:
        svc._close_serial()


def test_strict_five_second_deadline_includes_queue_wait_and_cancels_late_commands(monkeypatch):
    svc, serial, clock = _link_service(_link_line())
    captured = []
    waits = []

    class Event:
        def wait(self, timeout):
            waits.append(timeout)
            clock.advance(timeout)
            return False

        def set(self):
            pass

    class Queue:
        def put(self, batch, timeout):
            captured.append(batch)
            clock.advance(2.0)

    monkeypatch.setattr(_led_service.threading, "Event", Event)
    svc._queue = Queue()
    result = svc._submit(["CLEAR", "SETI 0 255 0 0", "SHOW"], strict=True)
    assert result["ok"] is False
    assert waits[0] <= 3.0 + 0.0001
    svc._run_batch(captured[0])
    assert serial.written == []
    svc._close_serial()


def test_all_serial_writes_have_a_finite_remaining_budget():
    svc, serial, _ = _link_service(_link_line())
    limits = []
    original_write = serial.write

    def write(data):
        limits.append(getattr(serial, "write_timeout", None))
        original_write(data)

    serial.write = write
    svc._poll_board_link()
    svc._run_batch(_led_service._Batch(["CLEAR", "SETI 0 255 0 0", "SHOW"], strict=True))
    assert limits and all(value is not None and 0 < value <= 0.2 for value in limits)
    svc._close_serial()


def test_boot_unterminated_input_cannot_extend_handshake_timeout():
    clock = FakeClock()

    class Unterminated(FakeSerial):
        timeout = 2.0

        def read(self, size=1):
            clock.advance(min(self.timeout, 0.03))
            return b"x" * size

        def readline(self):
            clock.advance(10.0)
            return b"x"

    serial = Unterminated()
    svc = LedService(LedServiceConfig(handshake_timeout=0.2), serial_factory=lambda: serial, clock=clock)
    svc._serial = serial
    svc._wait_for_boot_ready()
    assert clock() <= 1000.2 + 0.0001
    svc._close_serial()


def test_existing_linux_alias_disappearance_closes_before_any_more_commands(monkeypatch):
    svc, serial, _ = _link_service(_link_line())
    svc.config.serial_port = "/dev/serial/by-id/test-board"
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(os.path, "exists", lambda path: False)
    svc._maybe_poll_board_link()
    assert not svc.is_connected()
    assert serial.closed
    assert serial.written == []


def test_unknown_link_marks_current_guidance_for_refresh_when_up_returns():
    svc, serial, _ = _link_service(_link_line())
    svc._poll_board_link()
    svc.set_points([{"row": 1, "col": 1, "color": "white"}])
    svc._run_batch(svc._queue.get_nowait())
    serial.response = ""
    svc._poll_board_link()
    serial.written.clear()
    serial.response = _link_line()
    svc._poll_board_link()
    assert serial.written == ["LINK", "CLEAR", f"SETI {rc2idx(1, 1)} 0 255 0", "SHOW"]
    svc._close_serial()


def test_slow_strict_batch_uses_one_total_deadline_and_never_shows_partial_frame():
    clock = FakeClock()

    class SlowAck(FakeSerial):
        def read(self, size=1):
            if self._buf:
                clock.advance(min(self.timeout, 0.6))
                data = self._buf[0][:size]
                self._buf[0] = self._buf[0][size:]
                if not self._buf[0]:
                    self._buf.pop(0)
                return data
            clock.advance(self.timeout)
            return b""

    serial = SlowAck()
    svc = LedService(LedServiceConfig(handshake_timeout=2.0), clock=clock)
    svc._serial = serial
    svc._connected = True
    svc._run_batch(batch := _led_service._Batch(["CLEAR"] + [f"SETI {i} 255 0 0" for i in range(8)] + ["SHOW"], True))
    assert clock() <= 1005.0 + 0.0001
    assert batch.result["ok"] is False
    assert "SHOW" not in serial.written
    assert not svc.is_connected()


def test_timeout_during_clear_cancels_remaining_commands_even_if_ack_arrives(monkeypatch):
    svc, serial, clock = _link_service(_link_line())
    original_write = serial.write
    svc._submit(["CLEAR", "SETI 0 255 0 0", "SHOW"], strict=False)
    batch = svc._queue.get_nowait()

    def write(data):
        original_write(data)
        batch.cancelled = True

    serial.write = write
    svc._run_batch(batch)
    assert serial.written == ["CLEAR"]
    assert not svc.is_connected()
    assert batch.result["shown_at"] is None


@pytest.mark.parametrize("replacement", ["clear", "rgb", "strict"])
def test_reconnect_never_replays_strict_or_superseded_guidance(replacement):
    svc, serial, clock = _link_service(_link_line())
    svc.set_points([{"row": 1, "col": 1, "color": "white"}])
    svc._run_batch(svc._queue.get_nowait())
    if replacement == "clear":
        svc.clear()
    elif replacement == "rgb":
        svc.set_rgb_points([{"row": 2, "col": 2, "rgb": (0, 50, 0)}])
    else:
        # A strict request with no worker times out; it still invalidates guidance.
        svc._submit = lambda commands, strict: {"ok": False}
        svc.set_points([{"row": 2, "col": 2, "color": "black"}], strict=True)
    svc._close_serial()
    fresh = LinkSerial(_link_line(), clock)
    fresh._buf.append(b"READY\n")
    svc._serial_factory = lambda: fresh
    try:
        svc._open_serial()
        svc._poll_board_link()
        assert fresh.written == ["CLEAR", "SHOW", "BRIGHT 255", "LINK"]
        svc.set_guidance_scale(0.25)
        assert svc._queue.qsize() <= 1
    finally:
        svc._close_serial()


def test_clear_replaces_recovery_intent_before_later_seti_or_show():
    svc, serial, _ = _link_service(_link_line("OPEN", "ABSENT", "DOWN"))
    svc._poll_board_link()
    svc.set_points([{"row": 1, "col": 1, "color": "white"}])
    svc._run_batch(svc._queue.get_nowait())
    original_write = serial.write
    serial.written.clear()
    serial.response = _link_line()

    def write(data):
        original_write(data)
        if data == b"CLEAR\n":
            svc.clear()

    serial.write = write
    svc._poll_board_link()
    assert serial.written == ["LINK", "CLEAR"]
    serial.write = original_write
    svc._run_batch(svc._queue.get_nowait())
    assert serial.written == ["LINK", "CLEAR", "CLEAR", "SHOW"]
    svc._poll_board_link()
    assert serial.seti_lines() == []
    svc._close_serial()


def test_clear_handshake_failure_never_sends_show_or_bright():
    fake = FakeSerial(ack="ERR clear")
    svc = LedService(LedServiceConfig(serial_port=f"led-{uuid.uuid4().hex}"), serial_factory=lambda: fake)
    svc._open_serial()
    assert fake.written == ["CLEAR"]
    assert not svc.is_connected()
    assert fake.closed


def test_handshake_clear_show_and_bright_share_one_budget():
    clock = FakeClock()

    class HandshakeBudget(FakeSerial):
        def readline(self):
            if not self._buf:
                return b""
            clock.advance(min(self.timeout, 0.4))
            return super().readline()

    serial = HandshakeBudget()
    svc = LedService(
        LedServiceConfig(serial_port=f"led-{uuid.uuid4().hex}", handshake_timeout=0.7),
        serial_factory=lambda: serial,
        clock=clock,
    )
    svc._open_serial()
    assert clock() <= 1000.7 + 0.0001
    assert serial.written == ["CLEAR", "SHOW"]
    assert not svc.is_connected()


def test_partial_serial_write_is_transport_failure_and_aborts_the_batch():
    svc, serial, _ = _link_service(_link_line())
    serial.write = lambda data: serial.written.append(data.decode().strip()) or 1
    svc._queue.put(_led_service._Batch(["CLEAR", "SETI 0 255 0 0", "SHOW"], True))
    svc._queue.put(_led_service._SENTINEL)
    svc._worker()
    assert serial.written == ["CLEAR"]
    assert not svc.is_connected()
    assert serial.closed


def test_blocked_reconnect_open_returning_after_strict_deadline_sends_nothing():
    clock = FakeClock()
    serial = FakeSerial()

    def late_open():
        clock.advance(6.0)
        return serial

    svc = LedService(
        LedServiceConfig(serial_port=f"led-{uuid.uuid4().hex}"),
        serial_factory=late_open,
        clock=clock,
    )
    batch = _led_service._Batch(["CLEAR", "SETI 0 255 0 0", "SHOW"], True)
    batch.deadline = clock() + 5.0
    batch.real_deadline = time.monotonic() + 5.0
    batch.generation = svc._generation
    svc._queue.put(batch)
    svc._queue.put(_led_service._SENTINEL)
    svc._worker()
    assert batch.result["ok"] is False
    assert serial.written == []
    assert serial.closed


def test_raw_calibration_submission_is_never_tagged_as_recoverable_guidance():
    svc, serial, _ = _link_service(_link_line())
    svc.set_points([{"row": 1, "col": 1, "color": "white"}])
    svc._queue.get_nowait()
    svc._submit(["CLEAR", "SETI 0 0 50 0", "SHOW"], strict=False)
    assert svc._queue.get_nowait().guidance_revision is None
    svc._close_serial()


@pytest.mark.parametrize("operation", ["handshake", "display"])
def test_show_requires_its_own_ack_instead_of_extra_clear_ack(operation):
    class ExtraClearAck(FakeSerial):
        def reset_input_buffer(self):
            self._buf.clear()

        def write(self, data):
            command = data.decode().strip()
            self.written.append(command)
            if command == "CLEAR":
                self._buf.extend([b"OK clear\n", b"OK stale\n"])
            elif command.startswith("BRIGHT"):
                self._buf.append(b"OK bright\n")
            # SHOW deliberately never acknowledges.

    serial = ExtraClearAck()
    svc = LedService(LedServiceConfig(serial_port=f"led-{uuid.uuid4().hex}"), serial_factory=lambda: serial)
    try:
        if operation == "handshake":
            svc._open_serial()
        else:
            svc._serial = serial
            svc._connected = True
            svc.clear()
            svc._run_batch(batch := svc._queue.get_nowait())
            token = svc.reference_lighting_snapshot()
            assert not token.all_dark
            commits = []
            assert not svc.try_commit_reference_lighting(token, lambda: commits.append("unacked"))
            assert commits == []
            assert batch.result["ok"] is False
        assert not svc.is_connected()
        assert serial.written == ["CLEAR", "SHOW"]
    finally:
        svc._close_serial()


def test_board_b_reconnect_refreshes_only_latest_current_guidance_after_valid_up():
    svc, serial, clock = _link_service(_link_line())
    svc.set_points([{"row": 1, "col": 1, "color": "white"}])
    old = svc._queue.get_nowait()
    svc.set_points([{"row": 2, "col": 2, "color": "black"}])
    latest_old_connection = svc._queue.get_nowait()
    svc._close_serial()
    fresh = LinkSerial(_link_line(), clock)
    fresh._buf.append(b"READY\n")
    svc._serial_factory = lambda: fresh
    try:
        svc._open_serial()
        assert fresh.seti_lines() == []
        svc._poll_board_link()
        svc._run_batch(old)
        svc._run_batch(latest_old_connection)
        svc._poll_board_link()
        assert fresh.seti_lines() == [f"SETI {rc2idx(2, 2)} 255 0 0"]
        assert old.result["ok"] is False
        assert latest_old_connection.result["ok"] is False
    finally:
        svc._close_serial()


def test_idle_silent_transport_with_present_alias_reopens_once_after_three_link_failures(monkeypatch):
    svc, serial, clock = _link_service("")
    svc.config.serial_port = f"/dev/serial/by-id/test-{uuid.uuid4().hex}"
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(os.path, "exists", lambda path: True)
    replacement = LinkSerial(_link_line(), clock)
    replacement._buf.append(b"READY\n")
    opens = []
    svc._serial_factory = lambda: opens.append(True) or replacement
    svc._last_reconnect = clock()
    worker = threading.Thread(target=svc._worker, name="led-serial")
    worker.start()

    def wait_for(predicate):
        deadline = time.monotonic() + 2.0
        while not predicate() and time.monotonic() < deadline:
            time.sleep(0.005)
        assert predicate()

    try:
        for count in (1, 2, 3):
            wait_for(lambda: serial.written.count("LINK") >= count)
            if count < 3:
                clock.advance(2.1)
        wait_for(lambda: serial.closed)
        assert svc.is_connected() is False
        clock.advance(5.0)
        wait_for(lambda: svc.is_board_connected() is True)
        assert opens == [True]
        assert replacement.written == ["CLEAR", "SHOW", "BRIGHT 255", "LINK"]
    finally:
        svc._stop.set()
        svc._queue.put(_led_service._SENTINEL)
        worker.join(timeout=2)
        assert not worker.is_alive()


def test_usb_pause_closes_in_worker_retains_lease_and_drops_old_guidance():
    closed_threads = []
    first, second = FakeSerial(), FakeSerial()
    original_close = first.close

    def close():
        closed_threads.append(threading.current_thread().name)
        original_close()

    first.close = close
    serials = iter([first, second])
    port = f"led-{uuid.uuid4().hex}"
    svc = LedService(LedServiceConfig(serial_port=port), serial_factory=lambda: next(serials))
    peer = LedService(LedServiceConfig(serial_port=port), serial_factory=FakeSerial)
    svc.start()
    try:
        svc.set_points([{"row": 1, "col": 1, "color": "white"}])
        assert svc.begin_usb_recovery(timeout=0.5)
        assert closed_threads == ["led-serial"]
        assert not svc.is_connected()
        assert svc.set_points([{"row": 2, "col": 2}], strict=True)["ok"] is False
        assert svc.set_rgb_points([{"row": 2, "col": 2, "rgb": [1, 2, 3]}])["ok"] is False
        assert svc._last_guidance is None
        with pytest.raises(RuntimeError, match="[Bb]usy|occupied"):
            peer.start()
        svc.end_usb_recovery()
        svc.end_usb_recovery()
        deadline = time.monotonic() + 1
        while not svc.is_connected() and time.monotonic() < deadline:
            time.sleep(0.005)
        assert svc.is_connected()
        assert second.written[:3] == ["CLEAR", "SHOW", "BRIGHT 255"]
        assert second.seti_lines() == []
    finally:
        peer.stop()
        svc.stop()
        svc.stop()


def test_usb_pause_wakes_strict_waiter_but_does_not_ack_blocked_serial_or_close_cross_thread():
    entered, finish = threading.Event(), threading.Event()
    serial = FakeSerial()
    svc = LedService(LedServiceConfig(serial_port=f"led-{uuid.uuid4().hex}"), serial_factory=lambda: serial)
    svc.start()
    original_write = serial.write
    original_close = serial.close
    close_threads = []

    def write(data):
        if data == b"SETI 0 255 0 0\n":
            entered.set()
            assert finish.wait(1)
        original_write(data)

    def close():
        close_threads.append(threading.current_thread().name)
        original_close()

    serial.write, serial.close = write, close
    result = []
    waiter = threading.Thread(
        target=lambda: result.append(svc._submit(["CLEAR", "SETI 0 255 0 0", "SHOW"], strict=True))
    )
    try:
        waiter.start()
        assert entered.wait(0.5)
        assert not svc.begin_usb_recovery(timeout=0.03)
        waiter.join(0.2)
        assert result and result[0]["ok"] is False
        assert close_threads == []
        finish.set()
        waiter.join(1)
        time.sleep(0.05)
        assert "SHOW" not in serial.written[3:]
        assert all(name == "led-serial" for name in close_threads)
        assert svc.set_points([], strict=False)["ok"] is True, "late ACK left an unowned pause"
    finally:
        finish.set()
        waiter.join(1)
        svc.stop()


def test_led_startup_check_precedes_first_open_and_all_reconnects():
    allowed = threading.Event()
    opened = []
    svc = LedService(
        LedServiceConfig(serial_port=f"led-{uuid.uuid4().hex}"),
        serial_factory=lambda: opened.append(True) or FakeSerial(),
        reconnect_interval=0,
    )
    svc.set_usb_startup_check(allowed.is_set)
    svc.start()
    try:
        time.sleep(0.03)
        assert opened == []
        allowed.set()
        deadline = time.monotonic() + 1
        while not svc.is_connected() and time.monotonic() < deadline:
            time.sleep(0.005)
        assert opened == [True]
        assert svc.begin_usb_recovery(timeout=0.5)
        allowed.clear()
        svc.end_usb_recovery()
        time.sleep(0.25)
        assert opened == [True]
    finally:
        svc.stop()


def test_usb_pause_ack_waits_for_worker_serial_close_and_stop_cancels_waiter():
    entered, release, requested = threading.Event(), threading.Event(), threading.Event()
    serial = FakeSerial()
    svc = LedService(LedServiceConfig(serial_port=f"led-{uuid.uuid4().hex}"), serial_factory=lambda: serial)
    svc.start()
    original_close = serial.close

    def close():
        entered.set()
        assert release.wait(1)
        original_close()

    serial.close = close
    results = []

    def pause():
        requested.set()
        results.append(svc.begin_usb_recovery(timeout=0.5))

    waiter = threading.Thread(target=pause)
    stopper = threading.Thread(target=svc.stop)
    try:
        waiter.start()
        assert requested.wait(0.5) and entered.wait(0.5)
        assert results == []
        stopper.start()
        waiter.join(0.2)
        assert results == [False]
        release.set()
        stopper.join(1)
        assert not stopper.is_alive()
        svc.end_usb_recovery()
        svc.stop()
    finally:
        release.set()
        waiter.join(1)
        if stopper.ident is not None:
            stopper.join(1)
        svc.stop()


def test_usb_pause_full_wakeup_queue_still_acks_without_leaving_orphan_pause(monkeypatch):
    import queue

    svc = LedService(LedServiceConfig(serial_port=f"led-{uuid.uuid4().hex}"), serial_factory=FakeSerial)
    svc.start()
    original_put = svc._queue.put_nowait

    def put(item):
        if item is _led_service._USB_WAKE:
            raise queue.Full
        return original_put(item)

    monkeypatch.setattr(svc._queue, "put_nowait", put)
    try:
        assert svc.begin_usb_recovery(timeout=0.5)
    finally:
        svc.end_usb_recovery()
        svc.stop()


def test_usb_close_failure_never_acks_or_loses_handle_and_lease():
    class CloseFailureSerial(FakeSerial):
        def __init__(self):
            super().__init__()
            self.close_calls = []

        def close(self):
            self.close_calls.append(threading.current_thread().name)
            raise OSError("handle still open")

    serial = CloseFailureSerial()
    opened = []
    port = f"led-{uuid.uuid4().hex}"
    svc = LedService(
        LedServiceConfig(serial_port=port), serial_factory=lambda: opened.append(True) or serial, reconnect_interval=0
    )
    peer = LedService(LedServiceConfig(serial_port=port), serial_factory=FakeSerial)
    svc.start()
    lease = svc._device_lease
    try:
        assert svc.begin_usb_recovery(timeout=0.5) is False
        assert serial.closed is False
        assert svc._serial is serial
        assert svc._device_lease is lease
        assert not svc.is_connected()
        assert svc.set_points([{"row": 2, "col": 2}])["ok"] is False
        svc.end_usb_recovery()
        svc.end_usb_recovery()
        assert svc.begin_usb_recovery(timeout=0.01) is False
        time.sleep(0.25)
        assert opened == [True]
        assert serial.close_calls == ["led-serial"]
        with pytest.raises(RuntimeError, match="[Bb]usy|occupied"):
            peer.start()
        svc.stop()
        svc.stop()
        assert svc._serial is serial
        assert svc._device_lease is lease
        assert serial.close_calls == ["led-serial"]
        with pytest.raises(RuntimeError, match="[Bb]usy|occupied"):
            peer.start()
        with pytest.raises(RuntimeError, match="close|closed"):
            svc.start()
    finally:
        # The fake cannot be closed. Release only its test lease after every
        # ownership assertion; production retains it until process exit.
        svc.stop()
        peer.stop()
        lease.release()


def _reference_dark_service():
    svc, serial, clock = _link_service(_link_line())
    svc.clear()
    svc._run_batch(svc._queue.get_nowait())
    return svc, serial, clock


def test_reference_lighting_snapshot_requires_final_dark_show_ack_and_is_immutable():
    svc, serial, clock = _link_service(_link_line())
    assert not svc.reference_lighting_snapshot().all_dark
    svc.clear()
    pending = svc.reference_lighting_snapshot()
    assert pending.request_revision == 1 and not pending.all_dark
    svc._run_batch(svc._queue.get_nowait())
    token = svc.reference_lighting_snapshot()
    assert isinstance(token, _led_service.ReferenceLightingSnapshot)
    assert token.available and token.all_dark
    assert token.request_revision == token.shown_revision == 1
    assert token.shown_at == clock()
    assert token.connection_generation == svc._generation
    with pytest.raises(FrozenInstanceError):
        token.all_dark = False
    svc._close_serial()


@pytest.mark.parametrize("request_kind", ["points", "rgb", "clear", "raw"])
def test_reference_lighting_new_request_revokes_dark_before_queueing_without_tick(request_kind):
    svc, serial, _ = _reference_dark_service()
    old = svc.reference_lighting_snapshot()
    observed = []
    original_put = svc._queue.put_nowait

    def put(batch):
        observed.append(svc.reference_lighting_snapshot())
        return original_put(batch)

    svc._queue.put_nowait = put
    if request_kind == "points":
        svc.set_points([{"row": 1, "col": 1}])
    elif request_kind == "rgb":
        svc.set_rgb_points([{"row": 1, "col": 1, "rgb": [1, 2, 3]}])
    elif request_kind == "clear":
        svc.clear()
    else:
        svc._submit(["UNKNOWN"], strict=False)
    assert observed and observed[0].request_revision == old.request_revision + 1
    assert not observed[0].all_dark
    assert not svc.try_commit_reference_lighting(old, lambda: pytest.fail("stale commit"))
    svc._close_serial()


def test_reference_lighting_old_dark_ack_cannot_revive_new_bright_intent():
    svc, serial, _ = _link_service(_link_line())
    svc.clear()
    old = svc._queue.get_nowait()
    original_write = serial.write

    def write(data):
        original_write(data)
        if data == b"SHOW\n":
            svc.set_points([{"row": 1, "col": 1}])

    serial.write = write
    svc._run_batch(old)
    snapshot = svc.reference_lighting_snapshot()
    assert old.result["ok"]
    assert snapshot.request_revision == 2 and not snapshot.all_dark
    assert snapshot.shown_revision != snapshot.request_revision
    svc._close_serial()


@pytest.mark.parametrize(
    "commands, expected_dark",
    [
        (["CLEAR", "SHOW", "CLEAR", "SETI 0 1 0 0", "SHOW"], False),
        (["CLEAR", "SETI 0 0 0 0", "SHOW"], True),
        (["CLEAR", "SETI 0 1 0 0", "SETI 0 0 0 0", "SHOW"], True),
        (["CLEAR", "SHOW", "SETI 0 1 0 0"], False),
        (["CLEAR", "UNKNOWN", "SHOW"], False),
    ],
)
def test_reference_lighting_uses_final_display_not_intermediate_blackout(commands, expected_dark):
    svc, serial, _ = _link_service(_link_line())
    svc._submit(commands, strict=False)
    svc._run_batch(svc._queue.get_nowait())
    assert svc.reference_lighting_snapshot().all_dark is expected_dark
    svc._close_serial()


@pytest.mark.parametrize("failure", ["firmware", "drop", "timeout"])
def test_reference_lighting_failed_or_dropped_clear_never_restores_dark(failure):
    svc, serial, _ = _reference_dark_service()
    svc.clear()
    batch = svc._queue.get_nowait()
    if failure == "firmware":
        original_write = serial.write

        def write(data):
            original_write(data)
            serial._buf[-1] = b"ERR clear\n"

        serial.write = write
        svc._run_batch(batch)
    else:
        svc._finish(batch, ok=False, shown_at=None, errors=[failure])
    assert not svc.reference_lighting_snapshot().all_dark
    svc._close_serial()


@pytest.mark.parametrize("lifecycle", ["close", "open", "usb", "usb_failed", "stop"])
def test_reference_lighting_lifecycle_revokes_token_before_serial_work(lifecycle):
    svc, serial, _ = _reference_dark_service()
    token = svc.reference_lighting_snapshot()
    observed = []

    def observe():
        observed.append(svc.reference_lighting_snapshot())
        assert not svc.try_commit_reference_lighting(token, lambda: pytest.fail("lifecycle commit"))

    if lifecycle == "open":
        replacement = FakeSerial()
        svc._serial_factory = lambda: observe() or replacement
        svc._open_serial()
    elif lifecycle in ("usb", "usb_failed"):
        svc._thread = SimpleNamespace(is_alive=lambda: True)
        original_close = serial.close

        def close():
            observe()
            if lifecycle == "usb_failed":
                raise OSError("still open")
            original_close()

        serial.close = close
        recovery = threading.Thread(target=lambda: svc.begin_usb_recovery(timeout=0.5))
        recovery.start()
        deadline = time.monotonic() + 0.5
        while svc._usb_request is None and time.monotonic() < deadline:
            time.sleep(0.001)
        assert svc._usb_request is not None
        svc._quiesce_usb()
        svc.end_usb_recovery()
        recovery.join(1)
        assert not recovery.is_alive()
        svc._thread = None
    else:
        original_close = serial.close
        serial.close = lambda: observe() or original_close()
        getattr(svc, "stop" if lifecycle == "stop" else "_close_serial")()
    assert observed and all(not item.all_dark and not item.available for item in observed)
    assert not svc.reference_lighting_snapshot().all_dark or lifecycle == "open"
    svc._close_serial()


def test_reference_lighting_commit_uses_same_lock_as_new_requests():
    svc, serial, _ = _reference_dark_service()
    token = svc.reference_lighting_snapshot()
    entered, release, submitted = threading.Event(), threading.Event(), threading.Event()
    commits, results = [], []

    def commit():
        entered.set()
        assert release.wait(1)
        commits.append("adopted")

    adopter = threading.Thread(target=lambda: results.append(svc.try_commit_reference_lighting(token, commit)))
    submitter = threading.Thread(target=lambda: (svc.set_points([{"row": 1, "col": 1}]), submitted.set()))
    try:
        adopter.start()
        assert entered.wait(0.5)
        submitter.start()
        assert not submitted.wait(0.02)
        release.set()
        adopter.join(1)
        submitter.join(1)
        assert results == [True] and commits == ["adopted"]
        assert submitted.is_set() and not svc.reference_lighting_snapshot().all_dark
        assert not svc.try_commit_reference_lighting(token, lambda: commits.append("stale"))
        assert commits == ["adopted"]
    finally:
        release.set()
        adopter.join(1)
        if submitter.ident is not None:
            submitter.join(1)
        svc._close_serial()


def test_reference_lighting_superseded_raw_batch_cannot_change_new_dark_display():
    svc, serial, _ = _link_service(_link_line())
    svc.set_rgb_points([{"row": 1, "col": 1, "rgb": [1, 2, 3]}])
    stale = svc._queue.get_nowait()
    svc.clear()
    svc._run_batch(svc._queue.get_nowait())
    assert svc.reference_lighting_snapshot().all_dark
    serial.written.clear()
    svc._run_batch(stale)
    assert serial.written == []
    assert stale.result["ok"] is False
    svc._close_serial()
