"""Task 1 (P12): CalibrationStrategy interface + scenario-driven CalibrationSelector.

The structural guarantee under test: allow_led is DERIVED from Scenario (not a settable
field), and RUNTIME_RECALIBRATION can never light an LED — a requires_led strategy is
skipped (its calibrate() is never even called) whenever the scenario forbids LED.
"""
import numpy as np
import pytest

from katrain.vision.calibration_strategy import (
    CalibrationContext,
    CalibrationOutcome,
    CalibrationSelector,
    Scenario,
)


def _ctx(**kw):
    base = dict(frames=[np.zeros((10, 10, 3), np.uint8)], board=None, geometry=None, led=None, capture=None)
    base.update(kw)
    return CalibrationContext(**base)


class _Fake:
    """A minimal strategy double that records whether calibrate() ran."""

    def __init__(self, name, *, requires_led=False, crowded=True, applicable=True, ok=True):
        self.name = name
        self.requires_led = requires_led
        self.works_on_crowded_board = crowded
        self._applicable = applicable
        self._ok = ok
        self.calibrate_called = False
        self.last_allow_led = None

    def is_applicable(self, ctx):
        return self._applicable

    def calibrate(self, ctx, *, allow_led):
        self.calibrate_called = True
        self.last_allow_led = allow_led
        # defense-in-depth self-guard (修订说明 #2b)
        if self.requires_led and not allow_led:
            return CalibrationOutcome(ok=False, strategy=self.name, reason="led_forbidden")
        if not self._ok:
            return CalibrationOutcome(ok=False, strategy=self.name, reason="fail")
        M = np.eye(3, dtype=np.float64)
        return CalibrationOutcome(ok=True, M=M, Minv=M, corners=None, confidence=0.9, strategy=self.name, reason="")


def test_scenario_allows_led_mapping():
    assert Scenario.INITIAL_SETUP.allows_led() is True
    assert Scenario.MANUAL_FALLBACK.allows_led() is True
    assert Scenario.RUNTIME_RECALIBRATION.allows_led() is False


def test_runtime_skips_led_strategy_and_never_calls_it():
    led = _Fake("fake_led", requires_led=True, ok=True)
    noled = _Fake("fake_noled", requires_led=False, ok=True)
    sel = CalibrationSelector([led, noled], policy={Scenario.RUNTIME_RECALIBRATION: ["fake_led", "fake_noled"]})
    out = sel.calibrate(Scenario.RUNTIME_RECALIBRATION, _ctx())
    assert out.ok and out.strategy == "fake_noled"
    assert led.calibrate_called is False  # hard skip — calibrate never invoked


def test_priority_order_returns_first_applicable_ok():
    a = _Fake("a", ok=False)
    b = _Fake("b", ok=True)
    sel = CalibrationSelector([a, b], policy={Scenario.RUNTIME_RECALIBRATION: ["a", "b"]})
    assert sel.calibrate(Scenario.RUNTIME_RECALIBRATION, _ctx()).strategy == "b"


def test_is_applicable_vetoes_without_calling_calibrate():
    a = _Fake("a", applicable=False, ok=True)
    b = _Fake("b", ok=True)
    sel = CalibrationSelector([a, b], policy={Scenario.RUNTIME_RECALIBRATION: ["a", "b"]})
    out = sel.calibrate(Scenario.RUNTIME_RECALIBRATION, _ctx())
    assert out.strategy == "b"
    assert a.calibrate_called is False


def test_manual_fallback_allows_led():
    noled = _Fake("noled", requires_led=False, ok=False)
    led = _Fake("led", requires_led=True, ok=True)
    sel = CalibrationSelector([noled, led], policy={Scenario.MANUAL_FALLBACK: ["noled", "led"]})
    out = sel.calibrate(Scenario.MANUAL_FALLBACK, _ctx())
    assert out.ok and out.strategy == "led"
    assert led.last_allow_led is True


def test_all_fail_returns_not_ok_with_aggregated_reason():
    a = _Fake("a", ok=False)
    b = _Fake("b", ok=False)
    sel = CalibrationSelector([a, b], policy={Scenario.RUNTIME_RECALIBRATION: ["a", "b"]})
    out = sel.calibrate(Scenario.RUNTIME_RECALIBRATION, _ctx())
    assert out.ok is False and out.M is None and "a" in out.reason and "b" in out.reason


def test_outcome_contract_failure_has_no_M():
    out = CalibrationOutcome(ok=False, reason="x")
    assert out.M is None and out.Minv is None
    ok = CalibrationOutcome(ok=True, M=np.eye(3), Minv=np.eye(3), confidence=1.0, strategy="s")
    assert ok.M is not None and ok.Minv is not None
