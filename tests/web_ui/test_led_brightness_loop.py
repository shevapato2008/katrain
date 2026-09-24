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


def _run(scale, score, ok=True, area=450):
    led = _Led(scale)
    app = SimpleNamespace(state=SimpleNamespace(led=led))
    reading = {"row": 15, "col": 15, "ok": ok, "score": score, "area": area}
    _adjust_led_brightness(app, reading, logging.getLogger("t"))
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


def test_a_glow_larger_than_any_lamp_is_not_the_lamp():
    # 2026-09-22 night, (7,18): score 645k over 21108 px, peak 55 -- the whole scene changed
    assert _run(0.5, 10 * LED_GLOW_TARGET, area=21108).set_calls == []
    assert _run(0.5, 10 * LED_GLOW_TARGET, area=1975).set_calls == [pytest.approx(0.25)]  # a full-brightness lamp


# ── 目标值本身的闸(2026-09-24 上板实测后补) ───────────────────────────────────────
#
# 上面每一条用例都写成「相对 LED_GLOW_TARGET」—— 于是**目标定错时它们全部照绿**。
# 09-24 就是这么过去的:目标 60000 让环把亮度精确地调到「读数 = 60000」,而 60000 恰恰是
# 白子认不出来的读数。Fan 的第一手白子从 10:43:32 到 10:59:01 整整 16 分钟没进检测板,
# `caught_up` 一直为假,编排器挂着 lag 暂停,整局卡住 —— 而这一族用例一条都没红。
#
# 所以这两条断言**不许引用 LED_GLOW_TARGET**,只认实测锚点的字面量。
RECOGNISABLE_GLOW = 35_000.0    # 09-22 17:35 实测:这个读数下,压在亮灯上的白子仍能认出
UNRECOGNISABLE_GLOW = 60_000.0  # 09-24 实测:环调到这个读数,白子 16 分钟没认出来(认出时 W0.45 擦线)
FIELD_BARE_LAMP = 79_056.0      # 09-24 10:43:32 裸灯实测读数(满亮度)


def test_the_target_is_not_above_a_glow_white_stones_are_known_to_survive():
    """白子透光:灯比这个读数亮,它就不是一颗白子而是一团光。

    环只能在**裸灯**上测(子压上去之后 led_glow 读的就不是灯了),所以每颗子只有一次
    调整机会 —— 目标定高了不会在下一帧自我纠正,而是整局卡死。宁可偏暗。
    """
    assert LED_GLOW_TARGET <= RECOGNISABLE_GLOW
    assert LED_GLOW_TARGET < UNRECOGNISABLE_GLOW


def test_the_brightest_reading_seen_on_the_board_lands_in_one_step_at_a_survivable_glow():
    """79056 是 09-24 那局裸灯的实测读数,一次读数就要压到白子活得下来的亮度。

    断言落在**预测读数**上而不是 scale 上:scale 是手段,读数才是白子认不认得出的那个量。
    glow ~ brightness²,所以新读数 = 旧读数 × scale²。
    """
    led = _run(1.0, FIELD_BARE_LAMP)
    assert led.set_calls, "这个读数必须触发一次调整,不能落进死区"
    predicted = FIELD_BARE_LAMP * led.guidance_scale**2
    assert predicted <= RECOGNISABLE_GLOW
    # 也不能暗到人看不见灯
    assert led.guidance_scale > MIN_GUIDANCE_SCALE * 2
