"""Server side of the ambient LED brightness loop (2026-09-22): one led_glow reading per lamp steers the guidance
brightness toward LED_GLOW_TARGET by the square root of the ratio (the glow grows ~brightness^2)."""

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


def _run(scale, score, ok=True):
    led = _Led(scale)
    app = SimpleNamespace(state=SimpleNamespace(led=led))
    _adjust_led_brightness(app, {"row": 15, "col": 15, "ok": ok, "score": score}, logging.getLogger("t"))
    return led


def test_a_glow_four_times_the_target_halves_the_brightness():
    led = _run(1.0, 4 * LED_GLOW_TARGET)
    assert led.set_calls == [pytest.approx(0.5)]


def test_a_glow_near_the_target_changes_nothing():
    assert _run(0.5, LED_GLOW_TARGET * 1.1).set_calls == []


def test_a_dim_glow_brightens_but_a_lamp_already_at_full_brightness_stops_there():
    assert _run(0.3, LED_GLOW_TARGET / 4).guidance_scale == pytest.approx(0.6)
    assert _run(1.0, LED_GLOW_TARGET / 4).set_calls == []  # daylight: cannot go brighter


def test_one_reading_moves_the_brightness_at_most_by_the_step_limits():
    assert _run(1.0, 100 * LED_GLOW_TARGET).guidance_scale == pytest.approx(0.5)
    assert _run(0.1, LED_GLOW_TARGET / 100).guidance_scale == pytest.approx(0.2)
    assert _run(MIN_GUIDANCE_SCALE, 100 * LED_GLOW_TARGET).set_calls == []  # already at the floor


def test_a_glow_that_grows_with_the_square_of_the_brightness_settles_instead_of_swinging():
    # 2026-09-22 night, (17,4): stepping by the ratio itself went 0.21 -> 0.16 -> 0.39 -> 0.16 -> 0.08
    scale, seen = 1.0, []
    for _ in range(6):  # one lamp per move
        led = _run(scale, 4 * LED_GLOW_TARGET * scale**2)  # the glow at full brightness: 4x the target
        scale = led.guidance_scale
        seen.append(scale)
    assert seen[-1] == seen[-2] and 0.8 <= 4 * seen[-1] ** 2 <= 1.25
    assert all(b <= a for a, b in zip(seen, seen[1:]))  # never overshoots back up


def test_an_unusable_reading_changes_nothing():
    for ok, score in ((False, 5 * LED_GLOW_TARGET), (True, 0.0)):
        assert _run(1.0, score, ok=ok).set_calls == []
