"""Processed udev records accelerate recovery without owning camera I/O."""

import os
import subprocess
import threading
import time

import pytest


def monitor_module():
    from katrain.vision import device_events

    return device_events


class PipeProcess:
    def __init__(self):
        read_fd, self.write_fd = os.pipe()
        self.stdout = os.fdopen(read_fd, "rb", buffering=0)
        self.exited = False
        self.terminated = False

    def send(self, value):
        os.write(self.write_fd, value.encode())

    def poll(self):
        return 0 if self.exited else None

    def terminate(self):
        self.terminated = True
        self.finish()

    def kill(self):
        self.finish()

    def finish(self):
        if not self.exited:
            self.exited = True
            os.close(self.write_fd)

    def wait(self, timeout=None):
        return 0


def record(action="add", node="/dev/video7", links="/dev/smartbox-cam", capabilities=":capture:", devpath=None):
    return (
        "UDEV [123.0] event\n"
        f"ACTION={action}\nSUBSYSTEM=video4linux\nDEVNAME={node}\n"
        f"DEVLINKS={links}\nID_V4L_CAPABILITIES={capabilities}\n"
        f"DEVPATH={devpath or '/devices/camera/' + node.rsplit('/', 1)[-1]}\n\n"
    )


def started_monitor(monkeypatch, callback, path="/dev/smartbox-cam"):
    module = monitor_module()
    monkeypatch.setattr(module.sys, "platform", "linux")
    monkeypatch.setattr(module.os.path, "exists", lambda _path: False)
    process = PipeProcess()
    process.send(
        "monitor will print the received events for:\nUDEV - the event which udev sends out after rule processing\n\n"
    )
    calls = []

    def popen(argv, **kwargs):
        calls.append((argv, kwargs))
        return process

    monkeypatch.setattr(module.subprocess, "Popen", popen)
    monitor = module.UdevDeviceMonitor(path, callback)
    assert monitor.start()
    return monitor, process, calls


def test_exact_alias_capture_matching_and_duplicate_arrival(monkeypatch):
    events, received = [], threading.Event()

    def callback(action):
        events.append(action)
        if len(events) == 2:
            received.set()

    monitor, process, calls = started_monitor(monkeypatch, callback)
    try:
        process.send(record(links="/dev/smartbox-cam-extra"))
        process.send(record(node="/dev/video8", capabilities=":metadata:"))
        process.send(record())
        process.send(record())
        process.send(record("remove", links="", capabilities=""))
        assert received.wait(1)
        assert events == ["add", "remove"]
        argv, kwargs = calls[0]
        assert argv == ["udevadm", "monitor", "--udev", "--subsystem-match=video4linux", "--property"]
        assert kwargs.get("shell", False) is False
        assert kwargs["stderr"] == subprocess.DEVNULL
    finally:
        monitor.stop()


def test_alias_renumber_and_same_alias_new_device_emit_new_arrival(monkeypatch):
    events, received = [], threading.Event()

    def callback(action):
        events.append(action)
        if len(events) == 5:
            received.set()

    monitor, process, _calls = started_monitor(monkeypatch, callback)
    try:
        process.send(record())
        process.send(record("remove", links=""))
        process.send(record(node="/dev/video9"))
        # A delayed remove for the preceding node must not invalidate the new one.
        process.send(record("remove"))
        process.send(record("remove", node="/dev/video9", links=""))
        process.send(record(node="/dev/video9", devpath="/devices/replacement/video9"))
        assert received.wait(1)
        assert events == ["add", "remove", "add", "remove", "add"]
    finally:
        monitor.stop()


def test_existing_alias_records_capture_devname_for_removal(monkeypatch):
    module = monitor_module()
    monkeypatch.setattr(module.sys, "platform", "linux")
    monkeypatch.setattr(module.os.path, "exists", lambda _path: True)
    monkeypatch.setattr(module.os.path, "realpath", lambda _path: "/dev/video7")
    process = PipeProcess()
    process.send("UDEV - the event which udev sends out after rule processing\n\n")
    monkeypatch.setattr(module.subprocess, "Popen", lambda *args, **kwargs: process)
    actions, received = [], threading.Event()
    monitor = module.UdevDeviceMonitor("/dev/smartbox-cam", lambda action: (actions.append(action), received.set()))
    try:
        assert monitor.start()
        process.send(record("remove", links="", capabilities=""))
        assert received.wait(1)
        assert actions == ["remove"]
    finally:
        monitor.stop()


def test_monitor_bounds_bad_records_and_handles_child_exit_without_respawn(monkeypatch):
    events, received = [], threading.Event()
    monitor, process, calls = started_monitor(monkeypatch, lambda action: (events.append(action), received.set()))
    try:
        process.send("X=" + "x" * 40000 + "\n" + record())
        process.send(record())
        assert received.wait(1)
        process.finish()
        monitor._thread.join(1)
        assert not monitor._thread.is_alive()
        assert len(calls) == 1
        assert events == ["add"]
    finally:
        monitor.stop()


def test_monitor_unavailable_or_nonlinux_is_optional(monkeypatch):
    module = monitor_module()
    calls = []

    def missing(*args, **kwargs):
        calls.append(args)
        raise FileNotFoundError("udevadm missing")

    monkeypatch.setattr(module.subprocess, "Popen", missing)
    monkeypatch.setattr(module.sys, "platform", "darwin")
    assert module.UdevDeviceMonitor("/dev/smartbox-cam", lambda _: None).start() is False
    assert calls == []
    monkeypatch.setattr(module.sys, "platform", "linux")
    monitor = module.UdevDeviceMonitor("/dev/smartbox-cam", lambda _: None)
    assert monitor.start() is False
    monitor.stop()
    assert len(calls) == 1


def test_child_exit_before_subscription_falls_back_and_stop_is_bounded(monkeypatch):
    module = monitor_module()
    monkeypatch.setattr(module.sys, "platform", "linux")
    process = PipeProcess()
    process.finish()
    monkeypatch.setattr(module.subprocess, "Popen", lambda *args, **kwargs: process)
    monitor = module.UdevDeviceMonitor("/dev/smartbox-cam", lambda _: pytest.fail("unexpected callback"))
    started = time.monotonic()
    assert monitor.start() is False
    monitor.stop()
    assert time.monotonic() - started < 1


def test_stop_during_monitor_start_has_no_late_callback(monkeypatch):
    module = monitor_module()
    monkeypatch.setattr(module.sys, "platform", "linux")
    process = PipeProcess()
    spawned = threading.Event()

    def popen(*args, **kwargs):
        spawned.set()
        return process

    monkeypatch.setattr(module.subprocess, "Popen", popen)
    actions = []
    monitor = module.UdevDeviceMonitor("/dev/smartbox-cam", actions.append)
    starter = threading.Thread(target=monitor.start)
    starter.start()
    assert spawned.wait(1)
    monitor.stop()
    starter.join(1)
    assert not starter.is_alive()
    assert actions == []
    assert process.terminated


def test_alias_does_not_follow_unrelated_camera_reusing_old_capture_node(monkeypatch):
    actions, removed = [], threading.Event()

    def callback(action):
        actions.append(action)
        if action == "remove":
            removed.set()

    monitor, process, _calls = started_monitor(monkeypatch, callback)
    try:
        process.send(record())
        process.send(record("remove", links=""))
        assert removed.wait(1)
        process.send(record(links="/dev/unrelated-camera"))
        process.finish()
        monitor._thread.join(1)
        assert actions == ["add", "remove"]
    finally:
        monitor.stop()


def test_new_node_at_identical_alias_and_devpath_is_a_distinct_arrival(monkeypatch):
    from types import SimpleNamespace

    actions, received = [], threading.Event()

    def callback(action):
        actions.append(action)
        received.set()

    monitor, process, _calls = started_monitor(monkeypatch, callback)
    module = monitor_module()
    original_stat = module.os.stat
    inode = [10]

    def stat(path, **kwargs):
        if path == "/dev/video7":
            return SimpleNamespace(st_dev=1, st_ino=inode[0], st_rdev=7)
        return original_stat(path, **kwargs)

    monkeypatch.setattr(module.os, "stat", stat)
    try:
        process.send(record())
        assert received.wait(1)
        received.clear()
        inode[0] = 20
        process.send(record())
        assert received.wait(0.5)
        assert actions == ["add", "add"]
    finally:
        monitor.stop()
