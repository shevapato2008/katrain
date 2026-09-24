"""Guidance-lamp glow measurement for the ambient LED brightness loop (2026-09-22).

On the RK3562 at night a full-brightness lamp shone through the white stone placed on it and the stone was
not recognised until the lamp went out (verified by clearing the lamp: recognised at 0.75 1.5 s later). The
vision worker measures a bare lit lamp's glow before the player places the stone; the server dims or
brightens the guidance lamps from it.
"""

from types import SimpleNamespace
from unittest.mock import patch

import numpy as np

from katrain.vision.ipc import CommandType, WorkerCommand
from katrain.vision.worker_inprocess import (
    GLOW_SETTLE_FRAMES,
    InProcessAdapter,
    measure_led_glow,
    reference_clipped_fraction,
)

H = W = 1100
SPACING = 50.0


def _geometry():
    cols, rows = np.meshgrid(np.arange(19), np.arange(19))
    points = np.stack([100 + cols * SPACING, 100 + rows * SPACING], axis=-1).astype(np.float32)  # [row][col] = (x, y)
    return SimpleNamespace(points=points, source_width=W, source_height=H)


def _lamp(row, col, amplitude, channel=1, sigma=6.0):
    """A lit frame: a Gaussian glow on the given BGR channel centred on the (row, col) intersection."""
    frame = np.zeros((H, W, 3), np.uint8)
    y, x = np.mgrid[0:H, 0:W]
    cx, cy = 100 + col * SPACING, 100 + row * SPACING
    glow = amplitude * np.exp(-((x - cx) ** 2 + (y - cy) ** 2) / (2 * sigma**2))
    frame[..., channel] = np.clip(glow, 0, 255).astype(np.uint8)
    return frame


DARK = np.zeros((H, W, 3), np.uint8)


def test_a_brighter_lamp_scores_higher_on_its_own_colour_channel():
    dim = measure_led_glow(DARK, _lamp(5, 7, 60), _geometry(), 5, 7)
    bright = measure_led_glow(DARK, _lamp(5, 7, 120), _geometry(), 5, 7)
    assert dim.ok and bright.ok
    assert 1.6 < bright.score / dim.score < 2.4  # roughly proportional: the loop scales brightness by the ratio
    red = measure_led_glow(DARK, _lamp(5, 7, 120, channel=2), _geometry(), 5, 7)
    assert red.ok and abs(red.score - bright.score) < 1e-6


def test_a_lamp_somewhere_else_is_not_this_points_glow():
    result = measure_led_glow(DARK, _lamp(12, 3, 120), _geometry(), 5, 7)
    assert not result.ok and result.score == 0.0


def _adapter():
    with patch("katrain.vision.worker_inprocess.StoneDetector"):
        adapter = InProcessAdapter({"board_size": 19}, camera=None)
    adapter._geometry = _geometry()
    return adapter


def _glow_events(adapter):
    events = []
    while not adapter._event_queue.empty():
        evt = adapter._event_queue.get_nowait()
        if isinstance(evt, dict) and evt.get("type") == "led_glow":
            events.append(evt["data"])
    return events


def test_a_newly_lit_lamp_is_measured_against_the_frame_from_before_it_came_on():
    adapter = _adapter()
    adapter._last_raw = DARK
    adapter._cmd_queue.put(WorkerCommand(action=CommandType.SET_LIT_POINTS, data={"points": [[5, 7]]}))
    adapter._drain_commands()
    assert adapter._glow_ref is DARK and adapter._glow_pending == {(5, 7)}
    assert adapter._glow_wait == GLOW_SETTLE_FRAMES
    adapter._measure_pending_glow(_lamp(5, 7, 120))
    [event] = _glow_events(adapter)
    assert event["row"] == 5 and event["col"] == 7 and event["ok"] and event["score"] > 0
    assert adapter._glow_pending == set()  # one measurement per lamp


def test_a_lamp_with_a_stone_already_on_it_is_not_measured():
    adapter = _adapter()
    adapter._last_raw = DARK
    adapter._last_stable_board = np.zeros((19, 19), dtype=int)
    adapter._last_stable_board[5][7] = 2  # the player already put the white stone there
    adapter._cmd_queue.put(WorkerCommand(action=CommandType.SET_LIT_POINTS, data={"points": [[5, 7]]}))
    adapter._drain_commands()
    adapter._measure_pending_glow(_lamp(5, 7, 120))
    assert _glow_events(adapter) == []


def test_a_lamp_is_measured_once_until_a_new_lamp_comes_on():
    adapter = _adapter()
    adapter._last_raw = DARK
    adapter._cmd_queue.put(WorkerCommand(action=CommandType.SET_LIT_POINTS, data={"points": [[5, 7]]}))
    adapter._drain_commands()
    adapter._measure_pending_glow(_lamp(5, 7, 120))
    _glow_events(adapter)
    # the brightness change re-sends the same lit set: later readings caught the stone already on the lamp
    adapter._cmd_queue.put(WorkerCommand(action=CommandType.SET_LIT_POINTS, data={"points": [[5, 7]]}))
    adapter._drain_commands()
    assert adapter._glow_pending == set()


# ── 2026-09-24 代码评审:反光判据与「一次观测一个读数」 ──────────────────────────
#
# 评审挖出的根因:`reason` 当不了反光判别器。白灯纯绿 (0,255,0)、黑灯纯红,BGR 通道 0(蓝)
# 按构造没有灯信号 ⇒ 必然 low_signal 且 score=0.0;三通道全失败时 max 返回第一个 ⇒ reason
# **恒为**蓝通道的 low_signal。反光、手挡住、串口掉线、几何锁过期、整帧过曝全是同一个字符串。


def _glare_reference(row, col, radius=40):
    """灯亮之前那一帧里,这个交点上已经有一片死白的镜面反光。"""
    ref = np.zeros((H, W, 3), np.uint8)
    y, x = np.mgrid[0:H, 0:W]
    cx, cy = 100 + col * SPACING, 100 + row * SPACING
    ref[((x - cx) ** 2 + (y - cy) ** 2) <= radius**2] = 255
    return ref


def test_the_glare_probe_measures_this_lamps_own_roi():
    """判据量的是**这盏灯自己那个 ROI**里死白像素的比例。

    (「量的是参考帧不是亮帧」这条不在这里验 —— 这个函数只收得到一帧,选哪一帧是调用点的事,
    见下面那条 call-site 用例。)"""
    assert reference_clipped_fraction(_glare_reference(5, 7), _geometry(), 5, 7) > 0.02
    assert reference_clipped_fraction(DARK, _geometry(), 5, 7) == 0.0
    # 手挡在灯上:参考帧那儿是手,不是死白 —— 这正是 reason 分不开、而这个数分得开的那一类
    hand = np.full((H, W, 3), 90, np.uint8)
    assert reference_clipped_fraction(hand, _geometry(), 5, 7) == 0.0
    # 别处的反光不算这个点的
    assert reference_clipped_fraction(_glare_reference(12, 3), _geometry(), 5, 7) == 0.0


def test_a_located_lamp_outranks_a_failed_channel_that_happens_to_score_higher():
    """三通道取 max 原来只按 score 排 —— 而 `ambiguous_blobs` 是唯一带非零 score 的失败
    (那是落败的那团光的权重,不是「找到灯了」的证据),于是一个失败的通道能压过真找到灯的通道。"""
    frame = _lamp(5, 7, 120)  # 绿通道:一盏干净的灯
    y, x = np.mgrid[0:H, 0:W]
    cx, cy = 100 + 7 * SPACING, 100 + 5 * SPACING
    for dx in (-22, 22):  # 红通道:两团等亮的光,分不清,但每团都比绿灯亮
        blob = 200 * np.exp(-((x - cx - dx) ** 2 + (y - cy) ** 2) / (2 * 6.0**2))
        frame[..., 2] = np.clip(frame[..., 2].astype(np.float32) + blob, 0, 255).astype(np.uint8)
    result = measure_led_glow(DARK, frame, _geometry(), 5, 7)
    assert result.ok, "找到灯的那个通道被一个失败的通道压过去了"


def test_one_observation_produces_one_reading_however_many_lamps_it_lit():
    """补多手(lag 恢复:`to_place` 里有几手就点几盏)时这一批灯全在**同一帧、同一个亮度**下量出来 ——
    它们是一次观测的 N 个样本,不是 N 次观测。逐个发出去,服务端就把同一个偏差修正 N 遍、
    每遍还乘在上一遍改过的亮度上:实测 6 盏 4x 偏亮把亮度从 1.0 一路打到 0.08 地板(正确答案 0.5),
    第 3 盏就已经暗到人看不见灯。"""
    adapter = _adapter()
    adapter._last_raw = DARK
    points = [[5, 7], [5, 8], [6, 7], [9, 2]]
    adapter._cmd_queue.put(WorkerCommand(action=CommandType.SET_LIT_POINTS, data={"points": points}))
    adapter._drain_commands()
    frame = _lamp(5, 7, 120)
    for row, col in ((5, 8), (6, 7), (9, 2)):
        frame = np.maximum(frame, _lamp(row, col, 120))
    adapter._measure_pending_glow(frame)
    assert len(_glow_events(adapter)) == 1, "一次观测发了不止一个读数 = 同一个偏差会被修正多遍"


def test_a_batch_steers_on_the_clean_lamp_when_only_some_are_lost():
    """挑法要挑**测到灯的**那个:四盏里只有一盏没被挡住,就该拿它来调,而不是拿被挡住的那盏。"""
    adapter = _adapter()
    adapter._last_raw = DARK
    points = [[5, 7], [5, 8], [6, 7], [9, 2]]
    adapter._cmd_queue.put(WorkerCommand(action=CommandType.SET_LIT_POINTS, data={"points": points}))
    adapter._drain_commands()
    adapter._measure_pending_glow(_lamp(9, 2, 120))  # 只有 (9,2) 这盏真亮着
    [event] = _glow_events(adapter)
    assert (event["row"], event["col"]) == (9, 2) and event["ok"]


def test_a_lamp_hidden_by_glare_carries_the_evidence_on_the_event():
    """调用点这一半:判据取自**灯亮之前**那一帧,而且要真的到得了服务端。"""
    adapter = _adapter()
    adapter._last_raw = _glare_reference(5, 7)  # 灯亮之前这里就已经是一片死白
    adapter._cmd_queue.put(WorkerCommand(action=CommandType.SET_LIT_POINTS, data={"points": [[5, 7]]}))
    adapter._drain_commands()
    adapter._measure_pending_glow(_lamp(5, 7, 120))  # 灯亮了,但反光已经把那些像素钉在 255
    [event] = _glow_events(adapter)
    assert not event["ok"], "反光下灯本来就测不到 —— 测得到就说明这个夹具没造出反光"
    assert event["clipped"] > 0.02


def test_a_lamp_bright_enough_to_clip_its_own_pixels_is_not_called_glare():
    """反方向:判据要是错量了**亮帧**,一盏亮到自己把像素打饱和的灯就会被当成反光去调得更亮。"""
    adapter = _adapter()
    adapter._last_raw = DARK
    adapter._cmd_queue.put(WorkerCommand(action=CommandType.SET_LIT_POINTS, data={"points": [[5, 7]]}))
    adapter._drain_commands()
    adapter._measure_pending_glow(_lamp(5, 7, 255, sigma=20.0))  # 一大团打饱和的灯光
    [event] = _glow_events(adapter)
    assert event["clipped"] == 0.0


def test_the_real_producer_drives_the_real_consumer_through_the_event(caplog):
    """把接缝焊上:真跑 `_measure_pending_glow` 造出事件 dict,**原样**喂给 `_adjust_led_brightness`。

    其余用例两边各自用自造夹具 —— 服务端那边手打 `clipped=0.30`,worker 这边只看自己发出的 dict。
    于是两边中间那条缝没有任何闸:生产者改个键名、或者不再算这个数,两边的用例都照绿,而板上
    反光处理整条失效。09-24 之前 `reason` 就是这么过去的(消费者与生产者之间没有一条 import 边)。
    """
    import logging as _logging

    from katrain.web.server import _adjust_led_brightness

    def one_event(reference, lit_frame):
        adapter = _adapter()
        adapter._last_raw = reference
        adapter._cmd_queue.put(WorkerCommand(action=CommandType.SET_LIT_POINTS, data={"points": [[5, 7]]}))
        adapter._drain_commands()
        adapter._measure_pending_glow(lit_frame)
        [event] = _glow_events(adapter)
        return event

    def brightness_after(event, scale=0.6, settled=True):
        app = SimpleNamespace(
            state=SimpleNamespace(
                led=SimpleNamespace(guidance_scale=scale, set_guidance_scale=lambda v: None),
                led_glow_settled=settled,
                hardware_vision_dir=None,
            )
        )
        app.state.led.set_guidance_scale = lambda v: setattr(app.state.led, "guidance_scale", v)
        _adjust_led_brightness(app, event, _logging.getLogger("seam"))
        return app.state.led.guidance_scale, app.state.led_glow_settled

    # 灯被一片真的镜面反光吃掉 -> 生产者算出的 clipped 必须真的让消费者调亮并解锁
    scale, settled = brightness_after(one_event(_glare_reference(5, 7), _lamp(5, 7, 120)))
    assert scale > 0.6 and settled is False

    # 手挡在灯上(参考帧那儿是手,不是死白)-> 同样测不到灯,但**不许**调亮
    hand = np.full((H, W, 3), 90, np.uint8)
    scale, settled = brightness_after(one_event(hand, hand))
    assert scale == 0.6 and settled is True
