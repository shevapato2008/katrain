"""Tests for the LED serial service using a FAKE serial port (no pyserial, no board).

Real-board bring-up (single-LED control, star-point landing) is verified on
hardware day; these tests lock the host-side logic: LUT correctness, color/RGB
mapping, the strict SHOW-ack path, queue-full dropping, and reconnect.
"""

import threading

import pytest

from katrain.web.core.led_service import (
    LedService,
    LedServiceConfig,
    rc2idx,
    serp,
    validate_lut,
    COLOR_RGB,
)


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
