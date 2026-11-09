import fcntl
import json
import os
import threading
from dataclasses import replace

import pytest

from katrain.vision.hardware_recovery_gate import HardwareRecoveryGate
from katrain.web.core.linux_usb_hub import HubSnapshot, PortSnapshot
from katrain.web.core.usb_hub_recovery import UsbHubRecovery


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now

    def advance(self, value):
        self.now += value


def snapshot(camera=0x101, led=0x103, camera_child=False, led_child=True, valid=True):
    ports = {
        i: PortSnapshot(
            i,
            bool(bits & 1),
            bool(bits & 0x100),
            bool(bits & 2),
            bool(bits & 0x10),
            bool(bits & 8),
            ident,
            f"1-1.{i}" if ident else None,
        )
        for i, bits, ident in [
            (1, 0x100, None),
            (2, 0x100, None),
            (3, led, ("303a", "1001") if led_child else None),
            (4, camera, ("0ac8", "0346") if camera_child else None),
        ]
    }
    return HubSnapshot(valid, "1-1", ("1a40", "0101"), ports)


class Operation:
    def __init__(self):
        self.returncode = None
        self.killed = False

    def poll(self):
        return self.returncode

    def kill(self):
        self.killed = True

    def wait(self, timeout=None):
        if self.returncode is None:
            raise TimeoutError
        return self.returncode


class Adapter:
    def __init__(self):
        self.value = snapshot()
        self.operations = []
        self.lock_fd = None

    def snapshot(self):
        return self.value

    def start_reset(self, lock_fd, expected_candidates):
        self.expected_candidates = expected_candidates
        self.lock_fd = lock_fd
        op = Operation()
        self.operations.append(op)
        return op


class Owner:
    def __init__(self):
        self.begins = 0
        self.ends = 0
        self.accept = True
        self.connected = False
        self.frame_ts = 0

    def begin_usb_recovery(self, timeout=2):
        self.begins += 1
        return self.accept

    def end_usb_recovery(self):
        self.ends += 1

    def is_connected(self):
        return self.connected

    def read_frame_identified(self):
        return (object(), 1, self.frame_ts) if self.connected else (None, 0, 0)

    def board_status(self):
        return {"connected": self.connected, "board_link": "UP" if self.connected else "DOWN"}


def setup_recovery(tmp_path):
    clock = Clock()
    adapter = Adapter()
    camera = Owner()
    led = Owner()
    vision = Owner()
    gate = HardwareRecoveryGate()
    path = tmp_path / "state" / "state.json"
    r = UsbHubRecovery(adapter, camera, led, vision, gate, path, clock=clock, wall_clock=clock)
    return r, adapter, camera, led, vision, gate, clock, path


def attempt(r, clock):
    r.tick()
    clock.advance(10)
    r.tick()


def test_gate_tokens_are_atomic_owned_and_idempotent():
    gate = HardwareRecoveryGate()
    use = gate.try_use()
    assert gate.try_recovery() is None
    use.close()
    use.close()
    recovery = gate.try_recovery()
    assert gate.active and gate.generation == 1
    assert gate.try_use() is None
    recovery.close()
    recovery.close()
    assert not gate.active
    with gate.try_use():
        assert gate.try_recovery() is None


def test_disabled_missing_child_once_and_state_latched_before_quiet(tmp_path):
    r, a, c, l, v, g, t, p = setup_recovery(tmp_path)
    original = v.begin_usb_recovery

    def begin(timeout=2):
        state = json.loads(p.read_text())
        assert state["latched"] and state["inflight"] and state["attempt_id"]
        return original(timeout)

    v.begin_usb_recovery = begin
    attempt(r, t)
    assert len(a.operations) == 1 and g.active
    assert a.expected_candidates == (4,)
    t.advance(100)
    r.tick()
    assert len(a.operations) == 1


@pytest.mark.parametrize(
    "value",
    [
        snapshot(camera=0x100),
        snapshot(camera=0x103),
        snapshot(camera=0x103, camera_child=True),
        snapshot(valid=False),
        snapshot(camera=0x100, led=0x100, led_child=False),
    ],
)
def test_normal_true_disconnect_and_enabled_enumeration_never_reset(tmp_path, value):
    r, a, c, l, v, g, t, p = setup_recovery(tmp_path)
    a.value = value
    attempt(r, t)
    assert not a.operations and not c.begins


def test_esp_disabled_missing_child_can_trigger_once(tmp_path):
    r, a, c, l, v, g, t, p = setup_recovery(tmp_path)
    a.value = snapshot(camera=0x103, camera_child=True, led=0x101, led_child=False)
    attempt(r, t)
    assert len(a.operations) == 1


def test_gate_busy_defers_without_consuming_episode(tmp_path):
    r, a, c, l, v, g, t, p = setup_recovery(tmp_path)
    use = g.try_use()
    attempt(r, t)
    assert not a.operations and not p.exists()
    use.close()
    r.tick()
    assert len(a.operations) == 1


@pytest.mark.parametrize("owner_name", ["camera", "led", "vision"])
def test_quiet_ack_failure_consumes_episode_and_unwinds(tmp_path, owner_name):
    r, a, c, l, v, g, t, p = setup_recovery(tmp_path)
    {"camera": c, "led": l, "vision": v}[owner_name].accept = False
    attempt(r, t)
    assert not a.operations and not g.active
    assert json.loads(p.read_text())["latched"]
    t.advance(100)
    r.tick()
    assert not a.operations


def test_enumeration_race_is_cancelled_after_quiet(tmp_path):
    r, a, c, l, v, g, t, p = setup_recovery(tmp_path)

    def begin(timeout=2):
        a.value = snapshot(camera=0x103, camera_child=True)
        return True

    l.begin_usb_recovery = begin
    attempt(r, t)
    assert not a.operations and not g.active
    assert json.loads(p.read_text())["latched"]


def test_timeout_still_running_keeps_owners_and_gate_until_true_exit(tmp_path):
    r, a, c, l, v, g, t, p = setup_recovery(tmp_path)
    attempt(r, t)
    t.advance(8)
    r.tick()
    assert a.operations[0].killed
    assert not c.ends and not l.ends and g.active
    assert not UsbHubRecovery.startup_allowed(p)
    assert not r.stop(timeout=0) and g.active
    a.operations[0].returncode = -9
    r.tick()
    assert c.ends == l.ends == 1 and not g.active
    assert UsbHubRecovery.startup_allowed(p)


def test_exit_releases_worker_but_gate_waits_new_camera_frame_and_transport(tmp_path):
    r, a, c, l, v, g, t, p = setup_recovery(tmp_path)
    attempt(r, t)
    a.operations[0].returncode = 0
    r.tick()
    assert c.ends == l.ends == v.ends == 1 and g.active
    c.connected = l.connected = True
    c.frame_ts = t.now - 1
    r.tick()
    assert g.active
    c.frame_ts = t.now + 1
    r.tick()
    assert not g.active and v.ends == 1


def test_latched_persists_restart_and_healthy_30s_rearms_but_cooldown_still_applies(tmp_path):
    r, a, c, l, v, g, t, p = setup_recovery(tmp_path)
    attempt(r, t)
    a.operations[0].returncode = 1
    r.tick()
    r.stop()
    r = UsbHubRecovery(a, c, l, v, HardwareRecoveryGate(), p, clock=t, wall_clock=t)
    attempt(r, t)
    assert len(a.operations) == 1
    a.value = snapshot(camera=0x103, camera_child=True)
    c.connected = l.connected = True
    c.frame_ts = t.now + 1
    t.advance(10)
    c.frame_ts = t.now
    r.tick()
    t.advance(30)
    c.frame_ts = t.now
    r.tick()
    assert not json.loads(p.read_text())["latched"]
    a.value = snapshot()
    r.tick()
    t.advance(10)
    r.tick()
    assert len(a.operations) == 2


def test_bad_json_disables_reset_but_free_operation_lock_allows_startup(tmp_path):
    r, a, c, l, v, g, t, p = setup_recovery(tmp_path)
    p.parent.mkdir()
    p.write_text("{bad")
    p.chmod(0o600)
    r = UsbHubRecovery(a, c, l, v, g, p, clock=t, wall_clock=t)
    attempt(r, t)
    assert not a.operations
    assert UsbHubRecovery.startup_allowed(p)


def test_unsafe_state_or_wall_clock_rollback_fail_closed(tmp_path):
    r, a, c, l, v, g, t, p = setup_recovery(tmp_path)
    attempt(r, t)
    a.operations[0].returncode = 1
    r.stop()
    t.now = 1
    r = UsbHubRecovery(a, c, l, v, HardwareRecoveryGate(), p, clock=t, wall_clock=t)
    attempt(r, t)
    assert len(a.operations) == 1
    p.unlink()
    p.symlink_to(tmp_path / "elsewhere")
    assert not UsbHubRecovery.startup_allowed(p)


def test_stop_before_attempt_never_submits(tmp_path):
    r, a, c, l, v, g, t, p = setup_recovery(tmp_path)
    r.tick()
    assert r.stop()
    t.advance(10)
    r.tick()
    assert not a.operations


def test_link_down_allows_gate_release_but_not_healthy_rearm(tmp_path):
    r, a, c, l, v, g, t, p = setup_recovery(tmp_path)
    attempt(r, t)
    a.operations[0].returncode = 0
    r.tick()
    c.connected = l.connected = True
    c.frame_ts = t.now + 1
    l.board_status = lambda: {"connected": False, "board_link": "DOWN"}
    a.value = snapshot(camera=0x103, camera_child=True)
    r.tick()
    assert not g.active
    t.advance(20)
    r.tick()
    t.advance(30)
    r.tick()
    assert json.loads(p.read_text())["latched"]


def test_external_cycle_after_settle_rearms_but_respects_global_cooldown(tmp_path):
    r, a, c, l, v, g, t, p = setup_recovery(tmp_path)
    attempt(r, t)
    a.operations[0].returncode = 1
    r.tick()
    c.connected = l.connected = True
    c.frame_ts = t.now + 1
    r.tick()
    t.advance(20)
    r.tick()
    a.value = snapshot(camera=0x100)
    r.tick()
    a.value = snapshot()
    r.tick()
    assert not json.loads(p.read_text())["latched"]
    t.advance(10)
    r.tick()
    assert len(a.operations) == 1
    t.advance(30)
    r.tick()
    assert len(a.operations) == 2


def test_own_reset_disconnect_and_unverified_reads_do_not_rearm(tmp_path):
    r, a, c, l, v, g, t, p = setup_recovery(tmp_path)
    attempt(r, t)
    a.operations[0].returncode = 1
    r.tick()
    c.connected = l.connected = True
    c.frame_ts = t.now + 1
    r.tick()
    a.value = snapshot(camera=0x100)
    r.tick()
    a.value = snapshot()
    r.tick()
    t.advance(20)
    r.tick()
    a.value = snapshot(valid=False)
    r.tick()
    a.value = snapshot()
    r.tick()
    assert json.loads(p.read_text())["latched"]


def test_contending_coordinator_does_not_clear_foreign_inflight(tmp_path):
    r, a, c, l, v, g, t, p = setup_recovery(tmp_path)
    attempt(r, t)
    other = UsbHubRecovery(a, c, l, v, HardwareRecoveryGate(), p, clock=t, wall_clock=t)
    # A stale in-memory view must not write a foreign record on lock failure.
    other._state["latched"] = False
    attempt(other, t)
    assert json.loads(p.read_text())["inflight"]
    assert len(a.operations) == 1


def test_startup_lock_is_process_exclusive_and_child_inheritance_keeps_it(tmp_path):
    import subprocess
    import sys
    from katrain.web.core.usb_hub_recovery import _lock_operation

    path = tmp_path / "state" / "state.json"
    fd = _lock_operation(path)
    child = subprocess.Popen(
        [sys.executable, "-c", "import sys; sys.stdin.buffer.read(1)"], pass_fds=(fd,), stdin=subprocess.PIPE
    )
    try:
        os.close(fd)
        assert not UsbHubRecovery.startup_allowed(path)
        child.communicate(b"x", timeout=2)
        assert UsbHubRecovery.startup_allowed(path)
    finally:
        if child.poll() is None:
            child.kill()
            child.wait()


def test_stale_camera_frame_cannot_rearm_health(tmp_path):
    r, a, c, l, v, g, t, p = setup_recovery(tmp_path)
    attempt(r, t)
    a.operations[0].returncode = 1
    r.tick()
    r.stop()
    r = UsbHubRecovery(a, c, l, v, HardwareRecoveryGate(), p, clock=t, wall_clock=t)
    a.value = snapshot(camera=0x103, camera_child=True)
    c.connected = l.connected = True
    c.frame_ts = t.now - 100
    t.advance(20)
    r.tick()
    t.advance(30)
    r.tick()
    assert json.loads(p.read_text())["latched"]


def test_unknown_extra_state_fields_disable_reset(tmp_path):
    r, a, c, l, v, g, t, p = setup_recovery(tmp_path)
    attempt(r, t)
    a.operations[0].returncode = 1
    r.stop()
    state = json.loads(p.read_text())
    state["unknown"] = True
    p.write_text(json.dumps(state))
    r = UsbHubRecovery(a, c, l, v, HardwareRecoveryGate(), p, clock=t, wall_clock=t)
    attempt(r, t)
    assert len(a.operations) == 1


def test_external_replug_can_start_new_episode_even_without_first_recovery_frame(tmp_path):
    r, a, c, l, v, g, t, p = setup_recovery(tmp_path)
    attempt(r, t)
    a.operations[0].returncode = 1
    r.tick()
    assert g.active and not c.connected
    t.advance(60)
    a.value = snapshot(camera=0x100)
    r.tick()
    a.value = snapshot()
    r.tick()
    assert not json.loads(p.read_text())["latched"]
    t.advance(10)
    r.tick()
    assert len(a.operations) == 2 and g.active


def test_rearm_must_not_overwrite_newer_cross_process_episode(tmp_path):
    r, a, c, l, v, g, t, p = setup_recovery(tmp_path)
    attempt(r, t)
    a.operations[0].returncode = 1
    r.tick()
    r.stop()
    stale = UsbHubRecovery(a, c, l, v, HardwareRecoveryGate(), p, clock=t, wall_clock=t)
    a.value = snapshot(camera=0x103, camera_child=True)
    c.connected = l.connected = True
    t.advance(20)
    c.frame_ts = t.now
    stale.tick()
    newer = json.loads(p.read_text())
    newer["attempt_id"] = "f" * 32
    newer["last_attempt"] = t.now
    p.write_text(json.dumps(newer))
    t.advance(30)
    c.frame_ts = t.now
    stale.tick()
    assert json.loads(p.read_text())["attempt_id"] == "f" * 32
    assert json.loads(p.read_text())["latched"]


def test_fifo_state_is_rejected_without_a_blocking_open(tmp_path, monkeypatch):
    from katrain.web.core import usb_hub_recovery as module

    path = tmp_path / "state" / "state.json"
    path.parent.mkdir(mode=0o700)
    os.mkfifo(path, 0o600)
    original = os.open

    def checked_open(name, flags, *args, **kwargs):
        if os.fspath(name) == os.fspath(path):
            assert flags & os.O_NONBLOCK, "state type must be verified without blocking on a FIFO"
        return original(name, flags, *args, **kwargs)

    monkeypatch.setattr(module.os, "open", checked_open)
    assert not UsbHubRecovery.startup_allowed(path)
    t = Clock()
    a = Adapter()
    c = Owner()
    l = Owner()
    v = Owner()
    r = UsbHubRecovery(a, c, l, v, HardwareRecoveryGate(), path, clock=t, wall_clock=t)
    attempt(r, t)
    assert not a.operations


def test_other_target_enumerating_is_observed_without_shared_reset(tmp_path):
    r, a, c, l, v, g, t, p = setup_recovery(tmp_path)
    a.value = snapshot(camera=0x101, led=0x103, led_child=False)
    attempt(r, t)
    assert not a.operations and not c.begins


def test_stop_during_final_snapshot_cancels_launch_after_snapshot_returns(tmp_path):
    r, a, c, l, v, g, t, p = setup_recovery(tmp_path)
    r.tick()
    t.advance(10)
    entered = threading.Event()
    release = threading.Event()
    calls = 0
    original_snapshot = a.snapshot

    def blocked_final_snapshot():
        nonlocal calls
        calls += 1
        if calls == 2:
            entered.set()
            assert release.wait(2)
        return original_snapshot()

    a.snapshot = blocked_final_snapshot
    worker = threading.Thread(target=r.tick)
    worker.start()
    try:
        assert entered.wait(2)
        assert not r.stop(timeout=0)
        assert not a.operations
    finally:
        release.set()
        worker.join(2)
    assert not worker.is_alive()
    assert not a.operations
    assert c.ends == l.ends == v.ends == 1
    assert not g.active
    assert json.loads(p.read_text())["latched"]
    assert not json.loads(p.read_text())["inflight"]


def test_stop_during_owned_launch_is_bounded_and_late_handle_is_immediately_killed(tmp_path):
    import time

    r, a, c, l, v, g, t, p = setup_recovery(tmp_path)
    r.tick()
    t.advance(10)
    entered = threading.Event()
    release = threading.Event()
    original_start = a.start_reset

    def blocked_launch(lock_fd, expected_candidates):
        entered.set()
        assert release.wait(2)
        return original_start(lock_fd, expected_candidates)

    a.start_reset = blocked_launch
    worker = threading.Thread(target=r.tick)
    worker.start()
    try:
        assert entered.wait(2)
        before = time.monotonic()
        assert not r.stop(timeout=0)
        assert time.monotonic() - before < 0.2
    finally:
        release.set()
        worker.join(2)
    assert not worker.is_alive()
    assert len(a.operations) == 1
    assert a.operations[0].killed
    assert g.active and not c.ends and not l.ends
    a.operations[0].returncode = -9
    assert r.stop(timeout=0)
    assert not g.active and c.ends == l.ends == v.ends == 1


def test_inflight_tick_delay_honors_eight_second_deadline_then_returns_to_low_frequency(tmp_path):
    r, a, c, l, v, g, t, p = setup_recovery(tmp_path)
    assert r.next_tick_delay() == 5.0
    attempt(r, t)
    assert r.next_tick_delay() == 5.0
    t.advance(5)
    assert r.next_tick_delay() == 3.0
    assert r.next_tick_delay(default=1.0) == 1.0
    t.advance(2.5)
    assert r.next_tick_delay() == 0.5
    assert not a.operations[0].killed
    t.advance(0.5)
    assert r.next_tick_delay() == 0.0
    r.tick()
    assert a.operations[0].killed
    assert g.active
    assert r.next_tick_delay() == 5.0
    assert r.next_tick_delay(default=2.0) == 2.0
    a.operations[0].returncode = -9
    r.tick()
    assert r.next_tick_delay() == 5.0


# Type-C evidence is independent of the camera's service health. These fixtures
# keep the public board_status contract while supplying verified dynamic USB IDs.
def link_snapshot(
    *, camera_fault=False, camera_connected=True, esp_address=(1, 13), serial="unit-a", hub_address=(1, 7)
):
    base = snapshot(camera=0x101 if camera_fault else 0x103, camera_child=not camera_fault)
    if not camera_connected:
        base = snapshot(camera=0x100, camera_child=False)
    esp = base.ports[3]
    ports = dict(base.ports)
    ports[3] = replace(esp, child_address=esp_address, child_serial=serial)
    return replace(base, ports=ports, address=hub_address)


def setup_link_recovery(tmp_path, initial="UP"):
    r, a, c, l, v, g, t, p = setup_recovery(tmp_path)
    l.connected = True
    l.link = initial
    l.board_status = lambda: {"connected": l.link == "UP" if l.link in ("UP", "DOWN") else None, "board_link": l.link}
    a.value = link_snapshot()
    return r, a, c, l, v, g, t, p


def complete_link_reset(r, a, c, l, t, *, serial="unit-a", address=(1, 23), link="DOWN"):
    a.operations[-1].returncode = 0
    a.value = snapshot(valid=False)
    l.connected = False
    t.advance(1)
    r.tick()
    a.value = link_snapshot(esp_address=address, serial=serial)
    l.connected = True
    l.link = link
    c.connected = True
    t.advance(1)
    c.frame_ts = t.now
    r.tick()


def start_link_reset_while_down(r, a, l, t, initial="UP"):
    r.tick()
    if initial == "UP":
        l.link = "DOWN"
        t.advance(1)
        r.tick()
    a.value = link_snapshot(camera_fault=True)
    r.tick()
    t.advance(10)
    r.tick()
    assert len(a.operations) == 1


@pytest.mark.parametrize("initial", ["UP", "DOWN"])
def test_type_c_down_ticket_survives_owned_reset_then_later_up_authorizes_once(tmp_path, initial):
    r, a, c, l, v, g, t, p = setup_link_recovery(tmp_path, initial)
    start_link_reset_while_down(r, a, l, t, initial)
    complete_link_reset(r, a, c, l, t)
    assert not g.active
    # A fresh, same-unit DOWN can remain unplugged for an arbitrary duration.
    t.advance(100)
    r.tick()
    assert json.loads(p.read_text())["latched"]
    l.link = "UP"
    a.value = link_snapshot(camera_fault=True, esp_address=(1, 23))
    c.connected = False
    r.tick()
    assert not json.loads(p.read_text())["latched"]
    t.advance(10)
    r.tick()
    assert len(a.operations) == 2
    complete_link_reset(r, a, c, l, t, address=(1, 33), link="UP")
    c.connected = False
    a.value = link_snapshot(camera_fault=True, esp_address=(1, 33))
    t.advance(600)
    r.tick()
    assert len(a.operations) == 2
    assert json.loads(p.read_text())["latched"]


def test_type_c_initial_post_reset_down_up_without_qualification_does_not_rearm(tmp_path):
    r, a, c, l, v, g, t, p = setup_link_recovery(tmp_path)
    a.value = link_snapshot(camera_fault=True)
    attempt(r, t)
    complete_link_reset(r, a, c, l, t, link="DOWN")
    t.advance(40)
    r.tick()
    l.link = "UP"
    a.value = link_snapshot(camera_fault=True, esp_address=(1, 23))
    c.connected = False
    r.tick()
    t.advance(600)
    r.tick()
    assert len(a.operations) == 1 and json.loads(p.read_text())["latched"]


def test_type_c_new_down_before_healthy_30_seconds_rearms_and_pair_before_attempt_is_merged(tmp_path):
    r, a, c, l, v, g, t, p = setup_link_recovery(tmp_path)
    a.value = link_snapshot(camera_fault=True)
    attempt(r, t)
    complete_link_reset(r, a, c, l, t, link="UP")
    t.advance(20)
    c.frame_ts = t.now
    r.tick()
    l.link = "DOWN"
    a.value = link_snapshot(camera_fault=True, esp_address=(1, 23))
    c.connected = False
    r.tick()
    assert not json.loads(p.read_text())["latched"]
    l.link = "UP"
    r.tick()
    # DOWN and UP before this attempt provide one armed budget, never two.
    t.advance(40)
    r.tick()
    assert len(a.operations) == 2
    complete_link_reset(r, a, c, l, t, address=(1, 33), link="DOWN")
    l.link = "UP"
    a.value = link_snapshot(camera_fault=True, esp_address=(1, 33))
    c.connected = False
    t.advance(600)
    r.tick()
    assert len(a.operations) == 2 and json.loads(p.read_text())["latched"]


def test_type_c_unqualified_up_down_up_inside_settle_never_authorizes_boot_edges(tmp_path):
    r, a, c, l, v, g, t, p = setup_link_recovery(tmp_path)
    a.value = link_snapshot(camera_fault=True)
    attempt(r, t)
    complete_link_reset(r, a, c, l, t, link="UP")
    l.link = "DOWN"
    a.value = link_snapshot(camera_fault=True, esp_address=(1, 23))
    c.connected = False
    t.advance(1)
    r.tick()
    l.link = "UP"
    t.advance(1)
    r.tick()
    assert json.loads(p.read_text())["latched"]
    t.advance(17)
    r.tick()
    assert json.loads(p.read_text())["latched"]
    t.advance(600)
    r.tick()
    assert len(a.operations) == 1


@pytest.mark.parametrize("broken", ["serial", "address", "unknown", "transport", "expired"])
def test_type_c_owned_ticket_is_discarded_on_identity_unknown_or_rebuild_expiry(tmp_path, broken):
    r, a, c, l, v, g, t, p = setup_link_recovery(tmp_path)
    start_link_reset_while_down(r, a, l, t)
    if broken == "expired":
        a.operations[-1].returncode = 0
        a.value = snapshot(valid=False)
        l.connected = False
        t.advance(1)
        r.tick()
        t.advance(21)
        r.tick()
        a.value = link_snapshot(esp_address=(1, 23))
        l.connected = True
        l.link = "DOWN"
        r.tick()
    else:
        complete_link_reset(r, a, c, l, t, serial="unit-b" if broken == "serial" else "unit-a")
        if broken == "address":
            a.value = link_snapshot(esp_address=(1, 24))
        if broken == "unknown":
            l.link = None
        if broken == "transport":
            l.connected = False
        r.tick()
    t.advance(60)
    l.connected = True
    l.link = "UP"
    # Identity-changing samples are followed by UP only, without a new UP->DOWN.
    addr = (1, 24) if broken == "address" else (1, 23)
    a.value = link_snapshot(camera_fault=True, esp_address=addr, serial="unit-b" if broken == "serial" else "unit-a")
    c.connected = False
    r.tick()
    t.advance(600)
    r.tick()
    assert len(a.operations) == 1 and json.loads(p.read_text())["latched"]


@pytest.mark.parametrize("initial", ["UP", "DOWN"])
def test_type_c_link_edges_alone_or_real_camera_disconnect_never_reset(tmp_path, initial):
    r, a, c, l, v, g, t, p = setup_link_recovery(tmp_path, initial)
    r.tick()
    t.advance(10)
    r.tick()
    for link in ("DOWN", "UP", "DOWN", "UP"):
        l.link = link
        t.advance(10)
        r.tick()
    assert not a.operations
    a.value = link_snapshot(camera_connected=False)
    for link in ("DOWN", "UP"):
        l.link = link
        t.advance(60)
        r.tick()
    assert not a.operations


@pytest.mark.parametrize("failure", ["quiet", "no_child_started"])
def test_type_c_failed_or_unstarted_attempt_discards_inheritable_down_ticket(tmp_path, failure):
    r, a, c, l, v, g, t, p = setup_link_recovery(tmp_path)
    r.tick()
    l.link = "DOWN"
    a.value = link_snapshot(camera_fault=True)
    r.tick()
    if failure == "quiet":
        c.accept = False
    if failure == "no_child_started":
        original = l.begin_usb_recovery

        def recovered_before_launch(timeout=2):
            a.value = link_snapshot()
            return original(timeout)

        l.begin_usb_recovery = recovered_before_launch
    t.advance(10)
    r.tick()
    attempts = len(a.operations)
    assert attempts == 0
    t.advance(60)
    c.accept = True
    l.link = "UP"
    a.value = link_snapshot(camera_fault=True)
    r.tick()
    t.advance(600)
    r.tick()
    assert len(a.operations) == attempts and json.loads(p.read_text())["latched"]


def test_type_c_owned_ticket_cannot_pass_through_present_esp_without_serial(tmp_path):
    r, a, c, l, v, g, t, p = setup_link_recovery(tmp_path)
    start_link_reset_while_down(r, a, l, t)
    a.operations[0].returncode = 0
    a.value = snapshot(valid=False)
    l.connected = False
    t.advance(1)
    r.tick()
    a.value = link_snapshot(serial=None, esp_address=(1, 23))
    l.connected = True
    t.advance(1)
    r.tick()
    l.link = "UP"
    a.value = link_snapshot(camera_fault=True, esp_address=(1, 23))
    t.advance(1)
    r.tick()
    t.advance(600)
    r.tick()
    assert len(a.operations) == 1 and json.loads(p.read_text())["latched"]


def test_type_c_owned_ticket_locks_first_serial_address_before_link_handshake(tmp_path):
    r, a, c, l, v, g, t, p = setup_link_recovery(tmp_path)
    start_link_reset_while_down(r, a, l, t)
    a.operations[0].returncode = 0
    a.value = snapshot(valid=False)
    l.connected = False
    t.advance(1)
    r.tick()
    a.value = link_snapshot(esp_address=(1, 23))
    t.advance(1)
    r.tick()
    a.value = link_snapshot(esp_address=(1, 24))
    l.connected = True
    t.advance(1)
    r.tick()
    l.link = "UP"
    a.value = link_snapshot(camera_fault=True, esp_address=(1, 24))
    t.advance(60)
    r.tick()
    t.advance(600)
    r.tick()
    assert len(a.operations) == 1 and json.loads(p.read_text())["latched"]


def test_type_c_deferred_grant_is_discarded_on_foreign_attempt_cas(tmp_path):
    r, a, c, l, v, g, t, p = setup_link_recovery(tmp_path)
    start_link_reset_while_down(r, a, l, t)
    complete_link_reset(r, a, c, l, t)
    l.link = "UP"
    a.value = link_snapshot(camera_fault=True, esp_address=(1, 23))
    c.connected = False
    r.tick()
    foreign = json.loads(p.read_text())
    foreign["attempt_id"] = "f" * 32
    foreign["last_attempt"] = t.now
    p.write_text(json.dumps(foreign))
    t.advance(60)
    r.tick()
    t.advance(600)
    r.tick()
    assert len(a.operations) == 1
    assert json.loads(p.read_text())["latched"]
    assert json.loads(p.read_text())["attempt_id"] == "f" * 32


def test_type_c_stop_restart_does_not_recreate_initial_down_ticket_for_latched_episode(tmp_path):
    r, a, c, l, v, g, t, p = setup_link_recovery(tmp_path)
    start_link_reset_while_down(r, a, l, t)
    complete_link_reset(r, a, c, l, t)
    assert r.stop()
    r = UsbHubRecovery(a, c, l, v, HardwareRecoveryGate(), p, clock=t, wall_clock=t)
    t.advance(20)
    r.tick()
    t.advance(10)
    r.tick()
    l.link = "UP"
    a.value = link_snapshot(camera_fault=True, esp_address=(1, 23))
    c.connected = False
    r.tick()
    t.advance(600)
    r.tick()
    assert len(a.operations) == 1 and json.loads(p.read_text())["latched"]


def test_type_c_carried_down_ticket_up_inside_settle_defers_one_grant(tmp_path):
    r, a, c, l, v, g, t, p = setup_link_recovery(tmp_path)
    start_link_reset_while_down(r, a, l, t)
    complete_link_reset(r, a, c, l, t)
    l.link = "UP"
    a.value = link_snapshot(camera_fault=True, esp_address=(1, 23))
    c.connected = False
    t.advance(1)
    r.tick()
    assert json.loads(p.read_text())["latched"]
    t.advance(20)
    r.tick()
    assert not json.loads(p.read_text())["latched"]
    assert len(a.operations) == 1


@pytest.mark.parametrize("new_up", [False, True])
def test_type_c_started_nonzero_child_exit_keeps_down_ticket_but_only_fresh_up_can_rearm(tmp_path, new_up):
    r, a, c, l, v, g, t, p = setup_link_recovery(tmp_path)
    start_link_reset_while_down(r, a, l, t)
    a.operations[0].returncode = 3
    a.value = snapshot(valid=False)
    l.connected = False
    t.advance(1)
    r.tick()
    a.value = link_snapshot(esp_address=(1, 23))
    l.connected = True
    l.link = "DOWN"
    t.advance(1)
    r.tick()
    t.advance(60)
    r.tick()
    assert json.loads(p.read_text())["latched"]
    l.link = "UP" if new_up else "DOWN"
    a.value = link_snapshot(camera_fault=True, esp_address=(1, 23))
    r.tick()
    assert json.loads(p.read_text())["latched"] == (not new_up)
    t.advance(10 if new_up else 600)
    r.tick()
    assert len(a.operations) == (2 if new_up else 1)


def test_type_c_consumed_carried_up_cannot_create_another_initial_down_ticket(tmp_path):
    r, a, c, l, v, g, t, p = setup_link_recovery(tmp_path)
    start_link_reset_while_down(r, a, l, t)
    complete_link_reset(r, a, c, l, t)
    l.link = "UP"
    t.advance(1)
    r.tick()
    l.link = "DOWN"
    a.value = link_snapshot(camera_fault=True, esp_address=(1, 23))
    c.connected = False
    t.advance(1)
    r.tick()
    # Both observations occurred in self-settle. DOWN must not become another
    # initial-DOWN qualification merely because the old pending UP rearms.
    for _ in range(5):
        t.advance(10)
        r.tick()
    assert len(a.operations) == 1
    t.advance(10)
    r.tick()
    assert len(a.operations) == 2
    complete_link_reset(r, a, c, l, t, address=(1, 33), link="DOWN")
    l.link = "UP"
    a.value = link_snapshot(camera_fault=True, esp_address=(1, 33))
    c.connected = False
    r.tick()
    t.advance(600)
    r.tick()
    assert len(a.operations) == 2 and json.loads(p.read_text())["latched"]


@pytest.mark.parametrize(
    "status", [{"connected": False, "board_link": "UP"}, {"connected": False, "board_link": "CABLE_ONLY"}]
)
def test_type_c_owned_ticket_rejects_malformed_link_during_rebuild(tmp_path, status):
    r, a, c, l, v, g, t, p = setup_link_recovery(tmp_path)
    start_link_reset_while_down(r, a, l, t)
    a.operations[0].returncode = 0
    a.value = snapshot(valid=False)
    l.connected = False
    t.advance(1)
    r.tick()
    a.value = link_snapshot(esp_address=(1, 23))
    l.connected = True
    normal_status = l.board_status
    l.board_status = lambda: status
    t.advance(1)
    r.tick()
    l.board_status = normal_status
    l.link = "UP"
    a.value = link_snapshot(camera_fault=True, esp_address=(1, 23))
    t.advance(1)
    r.tick()
    t.advance(600)
    r.tick()
    assert len(a.operations) == 1 and json.loads(p.read_text())["latched"]
