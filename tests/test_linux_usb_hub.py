import ctypes
import os
import stat
from pathlib import Path

import pytest

from katrain.web.core.linux_usb_hub import LinuxUsbHub, UsbControl, USBDEVFS_CONTROL, USBDEVFS_RESET


def fake_usb(tmp_path, monkeypatch, statuses=None):
    root = tmp_path / "sys"
    root.mkdir()
    hub = root / "1-1"
    hub.mkdir()
    for key, value in {
        "idVendor": "1a40",
        "idProduct": "0101",
        "bDeviceClass": "09",
        "maxchild": "4",
        "busnum": "1",
        "devnum": "7",
    }.items():
        (hub / key).write_text(value)
    usbfs = tmp_path / "dev"
    (usbfs / "001").mkdir(parents=True)
    (usbfs / "001" / "007").touch()
    statuses = statuses or {1: 0x100, 2: 0x100, 3: 0x103, 4: 0x101}
    calls = []

    def ioctl(fd, request, arg=0):
        calls.append((request, arg))
        if request == USBDEVFS_CONTROL:
            if arg.bRequest == 6:
                ctypes.memmove(arg.data, bytes([9, 0x29, 4, 0, 0, 0, 0, 0, 0]), 9)
                return 9
            assert (arg.bRequestType, arg.bRequest, arg.wValue, arg.wLength, arg.timeout) == (0xA3, 0, 0, 4, 1000)
            ctypes.memmove(arg.data, statuses[arg.wIndex].to_bytes(2, "little") + b"\0\0", 4)
            return 4
        return 0

    monkeypatch.setattr("katrain.web.core.linux_usb_hub.fcntl.ioctl", ioctl)
    # Real adapters require a character usbfs device; fixture checks the same dev identity against fstat.
    monkeypatch.setattr("katrain.web.core.linux_usb_hub.stat.S_ISCHR", lambda mode: stat.S_ISREG(mode))
    adapter = LinuxUsbHub(sysfs_root=root, usbfs_root=usbfs, camera_alias=tmp_path / "cam", led_alias=tmp_path / "led")
    child(root, 3, "303a", "1001")
    return adapter, root, statuses, calls


def child(root, port, vid, pid):
    path = root / f"1-1.{port}"
    path.mkdir(exist_ok=True)
    (path / "idVendor").write_text(vid)
    (path / "idProduct").write_text(pid)
    return path


def test_snapshot_reads_all_ports_and_decodes_verified_candidate(tmp_path, monkeypatch):
    adapter, root, statuses, calls = fake_usb(tmp_path, monkeypatch)
    snapshot = adapter.snapshot()
    assert snapshot.valid, snapshot.reason
    assert snapshot.hub_path == "1-1"
    assert snapshot.ports[4].candidate
    assert snapshot.ports[3].child_identity == ("303a", "1001")
    assert len([c for c in calls if c[0] == USBDEVFS_CONTROL and c[1].bRequest == 0]) == 4
    assert USBDEVFS_CONTROL == (3 << 30 | ctypes.sizeof(UsbControl) << 16 | ord("U") << 8)


@pytest.mark.parametrize("port,bits", [(1, 0x101), (2, 0x103), (3, 0x109), (4, 0x109), (4, 0x111), (4, 0x1)])
def test_unknown_connected_overcurrent_reset_or_no_power_rejected(tmp_path, monkeypatch, port, bits):
    adapter, root, statuses, calls = fake_usb(tmp_path, monkeypatch)
    statuses[port] = bits
    assert not adapter.snapshot().valid


@pytest.mark.parametrize(
    "key,value", [("idVendor", "ffff"), ("idProduct", "0000"), ("bDeviceClass", "00"), ("maxchild", "5")]
)
def test_hub_identity_and_topology_are_exact(tmp_path, monkeypatch, key, value):
    adapter, root, statuses, calls = fake_usb(tmp_path, monkeypatch)
    (root / "1-1" / key).write_text(value)
    assert not adapter.snapshot().valid


def test_enabled_missing_child_is_not_candidate_and_existing_child_is_not_candidate(tmp_path, monkeypatch):
    adapter, root, statuses, calls = fake_usb(tmp_path, monkeypatch)
    statuses[4] = 0x103
    assert not adapter.snapshot().ports[4].candidate
    statuses[4] = 0x101
    child(root, 4, "0ac8", "0346")
    assert not adapter.snapshot().ports[4].candidate


def test_child_identity_alias_and_unconfigured_children_rejected(tmp_path, monkeypatch):
    adapter, root, statuses, calls = fake_usb(tmp_path, monkeypatch)
    (root / "1-1.3" / "idVendor").write_text("ffff")
    assert not adapter.snapshot().valid
    (root / "1-1.3" / "idVendor").write_text("303a")
    child(root, 1, "1234", "5678")
    assert not adapter.snapshot().valid


def test_existing_alias_must_resolve_under_expected_usb_child(tmp_path, monkeypatch):
    adapter, root, statuses, calls = fake_usb(tmp_path, monkeypatch)
    alias = tmp_path / "led"
    alias.symlink_to("/dev/null")
    assert not adapter.snapshot().valid


def test_strict_hub_path_and_fresh_address_prevent_reset(tmp_path, monkeypatch):
    with pytest.raises(ValueError):
        LinuxUsbHub(hub_path="1-1/../2-1")
    adapter, root, statuses, calls = fake_usb(tmp_path, monkeypatch)
    original = adapter._open_usbfs

    def changed():
        fd = original()
        (root / "1-1" / "devnum").write_text("8")
        return fd

    monkeypatch.setattr(adapter, "_open_usbfs", changed)
    assert not adapter.snapshot().valid
    assert not any(c[0] == USBDEVFS_RESET for c in calls)


def test_alias_sysfs_lookup_uses_sys_class_and_expected_child(tmp_path, monkeypatch):
    # Assert the real /sys hierarchy rather than relying on a permissive missing alias.
    from types import SimpleNamespace

    adapter = LinuxUsbHub()
    expected = Path("/sys/bus/usb/devices/1-1.3")
    alias = Path("/dev/smartbox-led")
    target = Path("/dev/ttyACM0")
    monkeypatch.setattr(os.path, "lexists", lambda path: True)
    seen = []
    original_resolve = Path.resolve

    def resolve(path, strict=False):
        seen.append(path)
        if path == alias:
            return target
        if path == Path("/sys/class/tty/ttyACM0/device"):
            return expected / "1-1.3:1.0" / "ttyACM0"
        if path == expected:
            return expected
        raise FileNotFoundError(path)

    monkeypatch.setattr(Path, "resolve", resolve)
    monkeypatch.setattr(Path, "stat", lambda path, **kw: SimpleNamespace(st_mode=stat.S_IFCHR))
    assert adapter._alias_matches(alias, expected)


@pytest.mark.parametrize("appeared, unsafe", [(True, False), (False, True), (False, False)])
def test_fixed_child_final_recheck_cancels_enum_race_and_unsafe_ports(tmp_path, monkeypatch, appeared, unsafe):
    import katrain.web.core.linux_usb_hub as module
    from katrain.web.core.usb_hub_recovery import _lock_operation

    adapter, root, statuses, calls = fake_usb(tmp_path, monkeypatch)
    lock = _lock_operation(tmp_path / "state" / "state.json")
    if appeared:
        child(root, 4, "0ac8", "0346")
        statuses[4] = 0x103
    if unsafe:
        statuses[1] = 0x101
    monkeypatch.setattr(module, "LinuxUsbHub", lambda: adapter)
    try:
        try:
            result = module._locked_child(lock, 8)
        except ValueError:
            result = 2
        resets = [call for call in calls if call[0] == USBDEVFS_RESET]
        assert len(resets) == (0 if appeared or unsafe else 1)
        assert (result == 0) == (not appeared and not unsafe)
    finally:
        os.close(lock)


def test_fixed_child_rejects_new_candidate_replacing_stable_camera_candidate(tmp_path, monkeypatch):
    import katrain.web.core.linux_usb_hub as module
    from katrain.web.core.usb_hub_recovery import _lock_operation

    adapter, root, statuses, calls = fake_usb(tmp_path, monkeypatch)
    assert tuple(p for p in (3, 4) if adapter.snapshot().ports[p].candidate) == (4,)
    # Between parent validation and child execution, the original candidate
    # recovers and a different port enters the disabled/missing-child state.
    child(root, 4, "0ac8", "0346")
    statuses[4] = 0x103
    (root / "1-1.3" / "idVendor").unlink()
    (root / "1-1.3" / "idProduct").unlink()
    (root / "1-1.3").rmdir()
    statuses[3] = 0x101
    monkeypatch.setattr(module, "LinuxUsbHub", lambda: adapter)
    lock = _lock_operation(tmp_path / "state" / "state.json")
    try:
        assert module._locked_child(lock, 8) == 3
        assert not any(request == USBDEVFS_RESET for request, _ in calls)
    finally:
        os.close(lock)


@pytest.mark.parametrize("expected_candidates,mask", [((3,), 4), ((4,), 8), ((3, 4), 12)])
def test_fixed_child_launch_carries_only_parent_stable_candidate_mask(monkeypatch, expected_candidates, mask):
    import katrain.web.core.linux_usb_hub as module

    calls = []
    monkeypatch.setattr(module.subprocess, "Popen", lambda argv, **kwargs: calls.append((argv, kwargs)))
    LinuxUsbHub().start_reset(7, expected_candidates)
    argv, kwargs = calls[0]
    assert argv[-3:] == ["--locked-child", "7", str(mask)]
    assert kwargs["pass_fds"] == (7,)


@pytest.mark.parametrize("mask", [0, 1, 2, 7, 15, True, "8"])
def test_fixed_child_rejects_masks_outside_verified_targets(mask):
    import katrain.web.core.linux_usb_hub as module

    assert module._locked_child(-1, mask) == 2
