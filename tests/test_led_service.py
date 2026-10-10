"""Tests for the LED serial service using a FAKE serial port (no pyserial, no board).

Real-board bring-up (single-LED control, star-point landing) is verified on
hardware day; these tests lock the host-side logic: LUT correctness, color/RGB
mapping, the strict SHOW-ack path, queue-full dropping, and reconnect.
"""

import importlib.util
import logging
import subprocess
import sys
import threading
import time
import uuid
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
        self._responses = list(bright_response)

    @property
    def in_waiting(self):
        return 0

    def reset_input_buffer(self):
        self.reset_calls += 1

    def write(self, data: bytes):
        self.write_times.append((data.decode("ascii").strip(), self.clock()))

    def readline(self) -> bytes:
        if not self.ready_sent:
            self.ready_sent = True
            self.clock.advance(self.ready_delay)
            return b"READY\n"
        if self._responses:
            return (self._responses.pop(0) + "\n").encode("ascii")
        self.clock.advance(2.0)
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
            assert fake.written[1:6] == ["CLEAR", "SHOW", "CLEAR", f"SETI {rc2idx(3, 16)} 0 96 0", "SHOW"]
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
        assert calls == [(("tty-test", 57600), {"timeout": 1.25})]

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
        assert fake.written == ["BRIGHT 255"]
        assert fake._buf == []

    def test_delayed_ready_precedes_bright_and_fresh_ok_connects(self):
        clock = FakeClock()
        fake = DelayedReadySerial(clock)
        svc = LedService(
            LedServiceConfig(enabled=True, serial_port="fake", handshake_timeout=1.0),
            serial_factory=lambda: fake,
            clock=clock,
        )

        svc._open_serial()

        assert fake.reset_calls == 1
        assert fake.write_times == [("BRIGHT 255", 1000.25)]
        assert svc.is_connected() is True

    def test_ready_banner_does_not_replace_postwrite_ok(self):
        clock = FakeClock()
        fake = DelayedReadySerial(clock, bright_response=("READY still booting",))
        svc = LedService(
            LedServiceConfig(enabled=True, serial_port="fake", handshake_timeout=1.0),
            serial_factory=lambda: fake,
            clock=clock,
        )

        svc._open_serial()

        assert fake.write_times == [("BRIGHT 255", 1000.25)]
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
        assert fake.written == ["BRIGHT 255"]
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

        def fail_read():
            raise OSError("read failed")

        fake.readline = fail_read
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
        # start() writes BRIGHT first (handshake), THEN set_points([one point])
        # emits CLEAR, SETI, SHOW — script the SETI ack as the firmware error while
        # BRIGHT/CLEAR/SHOW all still ack OK.
        fake = SequencedReplySerial(replies=["OK", "OK", "ERR maxon", "OK"])
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
        self._first_batch_replies = ["OK", "OK", "ERR maxon", "OK"]  # BRIGHT, CLEAR, SETI, SHOW
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
    svc._submit = lambda commands, strict: sent.append(list(commands)) or {"ok": True}
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
        assert serial.written == ["CLEAR", "SETI 0 255 0 0", "SHOW", "CLEAR", "SHOW", "LINK"]
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
