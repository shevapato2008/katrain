"""Server side of the ambient LED brightness loop (2026-09-22): one led_glow reading per lamp steers the guidance
brightness toward LED_GLOW_TARGET by the square root of the ratio (the glow grows ~brightness^2)."""

import json
import logging
from types import SimpleNamespace

import pytest

from katrain.web.core.led_service import MIN_GUIDANCE_SCALE
from katrain.web.server import (
    LED_GLARE_BRIGHTEN_STEP,
    LED_GLOW_TARGET,
    _adjust_led_brightness,
    _load_guidance_scale,
)


class _Led:
    def __init__(self, scale=1.0):
        self.guidance_scale = scale
        self.set_calls = []

    def set_guidance_scale(self, scale):
        self.set_calls.append(scale)
        self.guidance_scale = scale


def _app(scale=1.0, settled=False, hardware_vision_dir=None):
    """一个跨多次读数保留状态的 app —— 锁定位和落盘都挂在 app.state 上,`_run` 那种
    每次新建的写法看不见它们(旧用例正因如此对本文件新增的三条规则完全免疫)。"""
    return SimpleNamespace(
        state=SimpleNamespace(led=_Led(scale), led_glow_settled=settled, hardware_vision_dir=hardware_vision_dir)
    )


GLARE = 0.30  # 参考帧里 30% 的 ROI 已经死白 = 一片盖住灯的镜面反光
NO_GLARE = 0.0  # 手挡住 / 灯没亮 / 几何锁指错地方:参考帧在那儿是正常曝光


def _read(app, score, ok=True, area=450, reason="", clipped=NO_GLARE, row=15, col=15):
    reading = {
        "row": row,
        "col": col,
        "ok": ok,
        "score": score,
        "area": area,
        "reason": reason,
        "clipped": clipped,
    }
    _adjust_led_brightness(app, reading, logging.getLogger("t"))
    return app.state.led


def _run(scale, score, ok=True, area=450):
    return _read(_app(scale), score, ok=ok, area=area)


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
RECOGNISABLE_GLOW = 35_000.0  # 09-22 17:35 实测:这个读数下,压在亮灯上的白子仍能认出
UNRECOGNISABLE_GLOW = 60_000.0  # 09-24 实测:环调到这个读数,白子 16 分钟没认出来(认出时 W0.45 擦线)
FIELD_BARE_LAMP = 79_056.0  # 09-24 10:43:32 裸灯实测读数(满亮度)


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

    ⚠️ 已知未验证的前提:这里的「预测」用的是实现自己假设的平方律,现场**还没有**调整后的
    复测读数做第二个锚点。真实指数若小于 2,实际读数比这里预测的更暗(闸偏保守);若大于 2,
    这条闸会偏乐观。下次上板时补一条「调整后裸灯读数」的实测值,把 predicted 换成字面量。
    """
    led = _run(1.0, FIELD_BARE_LAMP)
    assert led.set_calls, "这个读数必须触发一次调整,不能落进死区"
    predicted = FIELD_BARE_LAMP * led.guidance_scale**2
    assert predicted <= RECOGNISABLE_GLOW
    # 也不能暗到人看不见灯
    assert led.guidance_scale > MIN_GUIDANCE_SCALE * 2


# ── Fan 2026-09-24 定的四条规则 ────────────────────────────────────────────────
#
# 现场:重启把引导亮度重置回满亮度 1.0(`_guidance_scale` 从不落盘),开局第一手 AI 落子的灯
# 以满亮度点亮,裸灯读数 79056;白子透光,压上去就是一团光,16 分钟没进检测板、整局卡死。
#
#   1 收敛到目标后锁定,正常读数不再动它   2 亮度落盘,重启从它起步
#   3 灯落在镜面反光上、相机读不出来 ⇒ 调亮全局   4 调亮同时解锁,让干净读数收回来
#
# 规则 3 为什么改全局而不是只对那一个点(Fan 的裁定):已经调好的那个全局值本身也只是在未知条件下
# 取的一次样 —— 没人记录第一次收敛时那盏灯底下有没有反光,所以它没有当基准的资格。
# 规则 4 是规则 3 的必然推论:不解锁则一次反光永久锁死高亮度,之后所有位置的白子都认不出来。


def test_once_converged_a_normal_reading_no_longer_moves_the_brightness():
    """规则 1「如非必要就不再变化」—— 这里是「非必要」那一半:偏差在 2 倍以内就别动它。"""
    app = _app(0.6, settled=True)
    _read(app, LED_GLOW_TARGET / 0.6)  # ratio 0.6:出了死区,本来会调暗
    assert app.state.led.set_calls == []
    _read(app, LED_GLOW_TARGET / 1.8)  # ratio 1.8:出了死区,本来会调亮
    assert app.state.led.set_calls == []
    assert app.state.led_glow_settled is True


def test_a_reading_off_by_more_than_twice_reopens_the_loop():
    """规则 1 的另一半:偏到 2 倍以上就是「必要」。

    没有这条,锁定之后**唯一的出路是调亮**(反光那条),于是:天黑了环回不来;更要命的是
    上次落盘的要是个坏值,它活过每一次重启,而仓里没有任何接口/按钮/命令行能清掉那个文件 ——
    盒子就永久性地对这个环失聪了。这条让坏值自己走出来。
    """
    app = _app(1.0, settled=True)  # 落盘回来的坏值:满亮度 + 已锁定
    _read(app, FIELD_BARE_LAMP)  # 09-24 那次的裸灯读数,ratio 0.44
    assert app.state.led.guidance_scale < 1.0, "偏了一倍多还锁着,就是 09-24 那个状态"
    assert app.state.led_glow_settled is False  # 重新开环,让它收敛到对的值


def test_a_reading_inside_the_deadband_is_what_latches_it():
    app = _app(0.6)
    assert app.state.led_glow_settled is False
    _read(app, LED_GLOW_TARGET)  # 正中目标 = 死区内
    assert app.state.led_glow_settled is True
    assert app.state.led.set_calls == []  # 落进死区本来就不该动


def test_a_lamp_lost_in_specular_glare_brightens_and_unlatches():
    # 期望值写**字面量**(0.6 × 1.25)而不是 import LED_GLARE_BRIGHTEN_STEP 再乘一遍 ——
    # 那样写期望值和被测值同源,把常量改错也照绿,正是 LED_GLOW_TARGET 那个洞的翻版。
    app = _app(0.6, settled=True)
    _read(app, 0.0, ok=False, reason="low_signal", clipped=GLARE)
    assert app.state.led.guidance_scale == pytest.approx(0.75)
    assert app.state.led_glow_settled is False


def test_glare_can_brighten_at_most_once_per_convergence():
    """棘轮闸。调亮的同时解锁,而调亮又只在已锁定时发生 ⇒ 一次收敛之后最多抬一步。

    去掉 `and settled`:0.665 →1.25→ 0.831 →1.25→ 1.00,两次误判就回到 09-24 那个卡死
    16 分钟的亮度**并落盘**;而 led_glow 只在有新灯点亮时才产生,白子认不出就没有下一个读数,
    环再也下不来 —— 唯一出口是 5 分钟熄灯 failsafe,正是这次要消灭的那个绕法。
    """
    app = _app(0.665, settled=True)
    for _ in range(6):  # 连着六盏灯全被反光吃掉
        _read(app, 0.0, ok=False, reason="low_signal", clipped=GLARE)
    assert app.state.led.guidance_scale == pytest.approx(0.665 * 1.25)
    assert app.state.led.set_calls == [pytest.approx(0.665 * 1.25)]  # 只抬了一次


def test_glare_while_still_converging_does_nothing():
    """还没调好就撞上反光:手上没有「已知安全的值」可以往上抬一步,只能等下一盏干净的灯。"""
    app = _app(0.6, settled=False)
    _read(app, 0.0, ok=False, reason="low_signal", clipped=GLARE)
    assert app.state.led.set_calls == []
    assert app.state.led_glow_settled is False


def test_a_glare_brighten_cannot_overshoot_past_what_white_stones_survive():
    """反光调亮是在「灯根本看不见」时盲调的一步,一步都不许把读数推过白子认不出的那条线。

    最坏情形:已经收敛在目标上限(读数 = RECOGNISABLE_GLOW)时撞上反光,再抬一步。
    glow ~ brightness² ⇒ 抬 k 倍之后读数 = 读数 × k²。两个界都是现场锚点的字面量,
    所以把 1.25 改成 1.4 这条会红 —— 上一条测试(字面量期望值)挡不住这个方向。
    """
    worst_case_glow = RECOGNISABLE_GLOW * LED_GLARE_BRIGHTEN_STEP**2
    assert worst_case_glow < UNRECOGNISABLE_GLOW, f"一步反光调亮会把读数推到 {worst_case_glow:.0f}"


def test_a_failure_that_is_not_glare_changes_nothing_and_keeps_the_latch():
    """判据必须落在 clipped 上,不能落在 reason 上。

    这四种原因**在 reason 上是同一个字符串**:白灯纯绿 (0,255,0)、黑灯纯红,BGR 通道 0(蓝)
    按构造没有灯信号 ⇒ 必然 low_signal 且 score=0.0;三通道全失败时 max 返回第一个 ⇒ reason
    恒为蓝通道的 low_signal。原来那版用 reason 当判据,等于把下面每一种都当成反光去调亮。
    """
    for cause in ("手挡在灯上", "串口掉线灯根本没亮", "几何锁过期 ROI 指到别处", "两团光分不清"):
        app = _app(0.6, settled=True)
        _read(app, 0.0, ok=False, reason="low_signal", clipped=NO_GLARE)
        assert app.state.led.set_calls == [], cause
        assert app.state.led_glow_settled is True, cause


def test_after_a_glare_brighten_the_next_clean_reading_pulls_it_back_down():
    """规则 4 的要害:反光调亮之后必须能收回来,否则一次反光就把整盘白子毁掉。"""
    app = _app(0.6, settled=True)
    _read(app, 0.0, ok=False, reason="low_signal", clipped=GLARE)
    brightened = app.state.led.guidance_scale
    assert brightened > 0.6
    # 下一盏灯不在反光上,读数明显偏亮 ⇒ 环该把亮度压回去。
    # 这里**不**拿实现自己的平方律去推算「下一次读数应该是多少」:那样构造出来的输入和被测的
    # 算法同源,平方律错了测试也照样自洽。只用「比目标亮得多」这一条与平方律无关的性质。
    _read(app, LED_GLOW_TARGET * 3)
    assert app.state.led.guidance_scale < brightened


def test_the_learned_brightness_survives_a_restart(tmp_path):
    """规则 2 —— 这一条直接对着 09-24 那次故障:重启回满亮度,用户就要先卡一手。"""
    app = _app(1.0, hardware_vision_dir=str(tmp_path))
    _read(app, 4 * LED_GLOW_TARGET)  # 学到一个更暗的值
    learned = app.state.led.guidance_scale
    assert learned < 1.0
    assert (tmp_path / "led" / "guidance.json").exists()

    fresh = _app(1.0, hardware_vision_dir=str(tmp_path))  # 重启:LedService 又是 1.0
    _load_guidance_scale(fresh, logging.getLogger("t"))
    assert fresh.state.led.guidance_scale == pytest.approx(learned)


def test_settling_without_a_scale_change_still_writes_the_latch(tmp_path):
    """落盘条件里那半个 `or now_settled != settled` 专为这一格存在。

    读数正中死区时 scale 一点不动,但「已经调好了」这件事必须活过重启 —— 否则每次开机都要
    重新收敛一遍,而「重新收敛」的代价是让用户先卡一手(09-24 那次故障的成本正是这个)。
    写回 `if changed:` 这一条就会红;顺带把落盘的 JSON 字段和取值一起钉死。
    """
    app = _app(0.6, hardware_vision_dir=str(tmp_path))
    _read(app, LED_GLOW_TARGET)  # ratio = 1.0,正中死区
    assert app.state.led.set_calls == []  # 亮度确实没动
    saved = json.loads((tmp_path / "led" / "guidance.json").read_text(encoding="utf-8"))
    assert saved == {"guidance_scale": pytest.approx(0.6), "settled": True}

    fresh = _app(1.0, hardware_vision_dir=str(tmp_path))  # 重启
    _load_guidance_scale(fresh, logging.getLogger("t"))
    assert fresh.state.led_glow_settled is True  # 不必再收敛一遍
    assert fresh.state.led.guidance_scale == pytest.approx(0.6)


def test_a_corrupt_state_file_does_not_block_startup(tmp_path):
    (tmp_path / "led").mkdir()
    (tmp_path / "led" / "guidance.json").write_text("{not json", encoding="utf-8")
    app = _app(1.0, hardware_vision_dir=str(tmp_path))
    _load_guidance_scale(app, logging.getLogger("t"))
    assert app.state.led.guidance_scale == 1.0  # 回落到默认,不抛


def test_without_a_hardware_vision_dir_nothing_is_persisted_and_nothing_breaks():
    app = _app(1.0)  # 没配 --hardware-vision-dir
    _read(app, 4 * LED_GLOW_TARGET)
    assert app.state.led.guidance_scale < 1.0  # 内存里照常生效
    _load_guidance_scale(app, logging.getLogger("t"))  # 不抛
