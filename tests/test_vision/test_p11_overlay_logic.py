"""Task 8 (P12): the diagnostic tool's scenario routing.

The auto-drift relock path must be LED-free (RUNTIME); only the user's 'r' key may use LED.
"""
from katrain.vision.calibration_strategy import Scenario
from katrain.vision.tools.p11_live_overlay import decide_scenario


def test_auto_trigger_is_runtime_no_led():
    s = decide_scenario("auto-drift")
    assert s is Scenario.RUNTIME_RECALIBRATION
    assert s.allows_led() is False


def test_manual_r_is_manual_fallback_led_ok():
    s = decide_scenario("manual-r")
    assert s is Scenario.MANUAL_FALLBACK
    assert s.allows_led() is True


def test_unknown_trigger_defaults_to_no_led():
    assert decide_scenario("anything-else").allows_led() is False
