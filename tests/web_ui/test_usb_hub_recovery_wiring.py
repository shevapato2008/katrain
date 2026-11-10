"""Isolated board seams avoid unrelated heavyweight server import fixtures."""

import ast
import asyncio
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from katrain.vision.hardware_recovery_gate import HardwareRecoveryGate
from katrain.vision.ipc import ConfirmedMove
from katrain.web.core.config import Settings


def server_function(name, **namespace):
    path = Path(__file__).parents[2] / "katrain/web/server.py"
    tree = ast.parse(path.read_text())
    node = next(
        node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name
    )
    scope = {"asyncio": asyncio, "FastAPI": object, "nullcontext": nullcontext, **namespace}
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), "exec"), scope)
    return scope[name]


def test_usb_recovery_defaults_disabled_and_requires_explicit_env(monkeypatch):
    monkeypatch.delenv("KATRAIN_USB_HUB_RECOVERY", raising=False)
    assert Settings().KATRAIN_USB_HUB_RECOVERY is False
    monkeypatch.setenv("KATRAIN_USB_HUB_RECOVERY", "true")
    assert Settings().KATRAIN_USB_HUB_RECOVERY is True


@pytest.mark.asyncio
async def test_move_poller_holds_use_through_real_await_and_releases_on_cancel():
    import logging

    gate = HardwareRecoveryGate()
    entered = asyncio.Event()

    async def handle(*args):
        entered.set()
        assert gate.try_recovery() is None
        await asyncio.Event().wait()

    vision = SimpleNamespace(
        bound_session_id="session", recovery_gate=gate, get_confirmed_move=lambda: ConfirmedMove(col=1, row=1, color=1)
    )
    app = SimpleNamespace(state=SimpleNamespace(vision=vision, hardware_recovery_gate=gate))
    poller = server_function("_vision_move_poller", logging=logging, _handle_confirmed_move=handle)
    task = asyncio.create_task(poller(app))
    await asyncio.wait_for(entered.wait(), 1)
    assert gate.try_recovery() is None
    task.cancel()
    await task
    token = gate.try_recovery()
    assert token is not None
    token.close()


@pytest.mark.asyncio
async def test_ws_discards_already_dequeued_old_generation():
    gate = HardwareRecoveryGate()
    app = SimpleNamespace(state=SimpleNamespace(hardware_recovery_gate=gate))
    websocket = SimpleNamespace(send_json=Mock())
    item = (gate.generation, {"type": "synced"})
    with gate.try_recovery():
        pass
    send = server_function("_send_vision_generation_item", _json_safe=lambda value: value)
    await send(app, websocket, item)
    websocket.send_json.assert_not_called()


@pytest.mark.parametrize(
    "mode,enabled,platform", [("server", True, "linux"), ("board", False, "linux"), ("board", True, "darwin")]
)
def test_cloud_default_and_non_linux_do_not_prepare_recovery(monkeypatch, mode, enabled, platform):
    import sys

    monkeypatch.setattr(sys, "platform", platform)
    settings = SimpleNamespace(KATRAIN_MODE=mode, KATRAIN_USB_HUB_RECOVERY=enabled)
    app = SimpleNamespace(state=SimpleNamespace())
    assert server_function("_prepare_usb_hub_recovery", settings=settings)(app) is None
    assert app.state.hardware_recovery_gate is None
    assert app.state.usb_hub_recovery is None


def test_startup_check_installed_before_first_owner_open(monkeypatch):
    import sys
    from katrain.web.core.usb_hub_recovery import UsbHubRecovery

    monkeypatch.setattr(sys, "platform", "linux")
    checked = []
    monkeypatch.setattr(UsbHubRecovery, "startup_allowed", lambda path: checked.append(path) or False)
    app = SimpleNamespace(state=SimpleNamespace())
    settings = SimpleNamespace(KATRAIN_MODE="board", KATRAIN_USB_HUB_RECOVERY=True)
    callback = server_function("_prepare_usb_hub_recovery", settings=settings)(app)

    class Owner:
        def set_usb_startup_check(self, callback):
            self.check = callback

        def start(self, **kwargs):
            assert self.check() is False

    for _ in range(2):
        server_function("_start_hardware_owner")(Owner(), callback)
    assert checked == ["/var/lib/smartbox/usb-hub-recovery/state.json"] * 2


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "valid,alias,expected",
    [(False, "/dev/smartbox-cam", False), (True, "/dev/video0", False), (True, "/dev/smartbox-cam", True)],
)
async def test_recovery_attaches_only_complete_verified_owner_topology(monkeypatch, valid, alias, expected):
    from katrain.web.core import linux_usb_hub, usb_hub_recovery

    camera = SimpleNamespace(config=SimpleNamespace(device_id=alias), set_device_recovery=Mock())
    led = SimpleNamespace(config=SimpleNamespace(serial_port="/dev/smartbox-led"))
    vision = SimpleNamespace(set_usb_recovery_callback=Mock())
    adapter = SimpleNamespace(snapshot=lambda: SimpleNamespace(valid=valid))
    monkeypatch.setattr(linux_usb_hub, "LinuxUsbHub", lambda: adapter)
    recovery = Mock()
    monkeypatch.setattr(usb_hub_recovery, "UsbHubRecovery", recovery)
    app = SimpleNamespace(
        state=SimpleNamespace(
            hardware_recovery_gate=HardwareRecoveryGate(),
            camera_hub=camera,
            led=led,
            vision=vision,
            vision_ws_clients={},
            vision_move_queue=asyncio.Queue(),
        )
    )
    server_function("_attach_usb_hub_recovery")(app, Mock())
    assert recovery.called is expected
    assert camera.set_device_recovery.called is expected
    if expected:
        queue = asyncio.Queue()
        app.state.vision_ws_clients["client"] = queue
        queue.put_nowait((0, {"type": "old"}))
        app.state.vision_move_queue.put_nowait("old-move")
        callback = vision.set_usb_recovery_callback.call_args.args[0]
        with app.state.hardware_recovery_gate.try_recovery():
            generation = app.state.hardware_recovery_gate.generation
            queue.put_nowait((generation, {"type": "fresh"}))
            assert await asyncio.to_thread(callback, 1) is True
            assert list(queue._queue) == [(generation, {"type": "fresh"})]
            assert app.state.vision_move_queue.empty()


@pytest.mark.parametrize("missing", ["camera_hub", "led", "vision"])
def test_incomplete_owners_do_not_attach_or_inspect_usb(monkeypatch, missing):
    from katrain.web.core import linux_usb_hub

    inspect = Mock()
    monkeypatch.setattr(linux_usb_hub, "LinuxUsbHub", inspect)
    owners = {name: object() for name in ("camera_hub", "led", "vision")}
    owners[missing] = None
    app = SimpleNamespace(state=SimpleNamespace(hardware_recovery_gate=HardwareRecoveryGate(), **owners))
    server_function("_attach_usb_hub_recovery")(app, Mock())
    inspect.assert_not_called()


@pytest.mark.asyncio
async def test_ws_inflight_send_keeps_recovery_out_until_send_finishes():
    gate = HardwareRecoveryGate()
    entered, finish = asyncio.Event(), asyncio.Event()

    async def send_json(payload):
        entered.set()
        await finish.wait()

    app = SimpleNamespace(state=SimpleNamespace(hardware_recovery_gate=gate))
    websocket = SimpleNamespace(send_json=send_json)
    send = server_function("_send_vision_generation_item", _json_safe=lambda value: value)
    task = asyncio.create_task(send(app, websocket, (gate.generation, {"type": "synced"})))
    await entered.wait()
    assert gate.try_recovery() is None
    finish.set()
    await task
    token = gate.try_recovery()
    assert token is not None
    token.close()


@pytest.mark.asyncio
async def test_partial_startup_stops_recovery_before_any_owner():
    order = []

    def owner(name):
        return SimpleNamespace(stop=lambda: order.append(name))

    app = SimpleNamespace(
        state=SimpleNamespace(
            **{
                name: owner(name)
                for name in ("usb_hub_recovery", "geometry_calibration", "vision", "capture", "led", "camera_hub")
            }
        )
    )
    await server_function("_stop_board_hardware")(app)
    assert order[0] == "usb_hub_recovery"
    assert set(order) == {"usb_hub_recovery", "geometry_calibration", "vision", "capture", "led", "camera_hub"}
