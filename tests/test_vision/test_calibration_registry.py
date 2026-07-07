"""Task 4 (P12): default selector registry + scenario priority policy.

The core safety assertion (修订说明 #2c): with the REAL strategy set, RUNTIME_RECALIBRATION
never invokes a requires_led strategy and never lights an LED.
"""
import numpy as np

from katrain.vision.calibration_registry import build_default_selector
from katrain.vision.calibration_strategy import CalibrationContext, Scenario


class _SpyLed:
    def __init__(self):
        self.rgb_calls = 0

    def clear(self, *, strict=False):
        return {"ok": True}

    def set_rgb_points(self, points, *, strict=False):
        self.rgb_calls += 1
        return {"ok": True, "shown_at": 1.0}


def test_default_policy_shape():
    sel = build_default_selector()
    pol = sel._policy
    assert pol[Scenario.INITIAL_SETUP] == ["led_anchor", "empty_board_autocal"]
    assert pol[Scenario.RUNTIME_RECALIBRATION] == ["outer_corner"]
    assert pol[Scenario.MANUAL_FALLBACK] == ["outer_corner", "led_fiducial"]


def test_runtime_policy_contains_no_led_strategy():
    sel = build_default_selector()
    for name in sel._policy[Scenario.RUNTIME_RECALIBRATION]:
        assert sel._by_name[name].requires_led is False


def test_runtime_never_lights_led_even_if_policy_polluted():
    # Maliciously place LED strategies first in the RUNTIME policy; the derived allow_led=False
    # must hard-skip them (calibrate never called → no led.set_rgb_points).
    sel = build_default_selector()
    sel._policy[Scenario.RUNTIME_RECALIBRATION] = ["led_anchor", "led_fiducial", "outer_corner"]
    led = _SpyLed()
    ctx = CalibrationContext(
        frames=[np.zeros((720, 1280, 3), np.uint8)], board=None, led=led, capture=object()
    )
    out = sel.calibrate(Scenario.RUNTIME_RECALIBRATION, ctx)
    assert led.rgb_calls == 0  # no LED ever lit during runtime
    # outer_corner runs on the blank frame and fails to detect → overall not ok, but LED-free.
    assert out.ok is False
