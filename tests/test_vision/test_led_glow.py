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
from katrain.vision.worker_inprocess import GLOW_SETTLE_FRAMES, InProcessAdapter, measure_led_glow

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
