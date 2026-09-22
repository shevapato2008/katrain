"""Server side of the ambient LED brightness loop (2026-09-22): a led_glow reading steers the guidance
brightness toward LED_GLOW_TARGET and asks vision to measure the same lamp again at the new brightness."""

import logging
from types import SimpleNamespace

import pytest

from katrain.web.core.led_service import MIN_GUIDANCE_SCALE
from katrain.web.server import LED_GLOW_TARGET, _adjust_led_brightness


class _Led:
    def __init__(self, scale=1.0):
        self.guidance_scale = scale
        self.set_calls = []

    def set_guidance_scale(self, scale):
        self.set_calls.append(scale)
        self.guidance_scale = scale


class _Vision:
    def __init__(self):
        self.remeasured = 0

    def remeasure_led_glow(self):
        self.remeasured += 1


def _run(scale, score, ok=True):
    led, vision = _Led(scale), _Vision()
    app = SimpleNamespace(state=SimpleNamespace(led=led, vision=vision))
    _adjust_led_brightness(app, {"row": 15, "col": 15, "ok": ok, "score": score}, logging.getLogger("t"))
    return led, vision


def test_a_glow_twice_the_target_halves_the_brightness_and_measures_again():
    led, vision = _run(1.0, 2 * LED_GLOW_TARGET)
    assert led.guidance_scale == pytest.approx(0.5)
    assert vision.remeasured == 1


def test_a_glow_near_the_target_changes_nothing():
    led, vision = _run(0.5, LED_GLOW_TARGET * 1.1)
    assert led.set_calls == [] and vision.remeasured == 0


def test_a_dim_glow_brightens_but_a_lamp_already_at_full_brightness_stops_there():
    led, vision = _run(0.3, LED_GLOW_TARGET / 2)
    assert led.guidance_scale == pytest.approx(0.6) and vision.remeasured == 1
    led, vision = _run(1.0, LED_GLOW_TARGET / 4)  # daylight: cannot go brighter, must not re-measure forever
    assert led.set_calls == [] and vision.remeasured == 0


def test_one_reading_moves_the_brightness_at_most_by_the_step_limits():
    led, _ = _run(1.0, 100 * LED_GLOW_TARGET)
    assert led.guidance_scale == pytest.approx(0.4)
    led, _ = _run(0.1, LED_GLOW_TARGET / 100)
    assert led.guidance_scale == pytest.approx(0.25)
    led, _ = _run(MIN_GUIDANCE_SCALE, 100 * LED_GLOW_TARGET)
    assert led.set_calls == []  # already at the floor


def test_an_unusable_reading_changes_nothing():
    for reading in ({"ok": False, "score": 5 * LED_GLOW_TARGET}, {"ok": True, "score": 0.0}):
        led, vision = _run(1.0, reading["score"], ok=reading["ok"])
        assert led.set_calls == [] and vision.remeasured == 0
