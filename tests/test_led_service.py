"""Tests for the LED serial service using a FAKE serial port (no pyserial, no board).

Real-board bring-up (single-LED control, star-point landing) is verified on
hardware day; these tests lock the host-side logic: LUT correctness, color/RGB
mapping, the strict SHOW-ack path, queue-full dropping, and reconnect.
"""

import importlib.util
import sys
import threading
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
        assert sys.modules.get("katrain.web") is _web_package_before


# --------------------------------------------------------------------------- #
# Service behaviour (fake serial)
# --------------------------------------------------------------------------- #


def _make_service(ack="OK", clock=None):
    fake = FakeSerial(ack=ack)
    svc = LedService(
        LedServiceConfig(enabled=True, serial_port="fake"), serial_factory=lambda: fake, clock=clock or (lambda: 0.0)
    )
    return svc, fake


class TestColorsAndProtocol:
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
            assert "BRIGHT 200" in fake.written
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
        assert fake.written == ["BRIGHT 200"]
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
        assert fake.write_times == [("BRIGHT 200", 1000.25)]
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

        assert fake.write_times == [("BRIGHT 200", 1000.25)]
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
        assert fake.written == ["BRIGHT 200"]
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
