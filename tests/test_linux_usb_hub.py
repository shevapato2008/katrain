import ctypes
import fcntl
import os
import stat
import struct
from types import SimpleNamespace
from pathlib import Path

import pytest

from katrain.web.core.linux_usb_hub import LinuxUsbHub, UsbControl, USBDEVFS_CONTROL, USBDEVFS_RESET


def fake_usb(tmp_path, monkeypatch, statuses=None):
    root = tmp_path / "sys" / "bus" / "usb" / "devices"
    root.mkdir(parents=True)
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
    dev = tmp_path / "dev"
    usbfs = dev / "bus" / "usb"
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
        if request == 0x80685600:  # VIDIOC_QUERYCAP, no streaming or frame reads.
            flags = fcntl.fcntl(fd, fcntl.F_GETFL)
            assert flags & os.O_ACCMODE == os.O_RDONLY
            assert flags & os.O_NONBLOCK
            arg.capabilities, arg.device_caps = struct.unpack("<II", os.pread(fd, 8, 0))
            return 0
        assert request == USBDEVFS_RESET
        return 0

    monkeypatch.setattr("katrain.web.core.linux_usb_hub.fcntl.ioctl", ioctl)
    # Model only the character-device boundary; sysfs ancestry and validation run unchanged.
    real_stat, real_fstat = os.stat, os.fstat
    char_devices = {}

    def character_info(info, rdev):
        values = {name: getattr(info, name) for name in dir(info) if name.startswith("st_")}
        values.update(st_mode=stat.S_IFCHR | 0o600, st_rdev=rdev)
        return SimpleNamespace(**values)

    def device_stat(path, **kwargs):
        info = real_stat(path, **kwargs)
        if stat.S_ISREG(info.st_mode):
            node = Path(path)
            if node == usbfs / "001" / "007":
                char_devices[info.st_dev, info.st_ino] = os.makedev(189, 6)
            elif node.parent == dev and node.name.startswith("video") and node.name[5:].isdigit():
                char_devices[info.st_dev, info.st_ino] = os.makedev(81, int(node.name[5:]))
        rdev = char_devices.get((info.st_dev, info.st_ino))
        return character_info(info, rdev) if rdev is not None else info

    def device_fstat(fd):
        info = real_fstat(fd)
        rdev = char_devices.get((info.st_dev, info.st_ino))
        return character_info(info, rdev) if rdev is not None else info

    monkeypatch.setattr(os, "stat", device_stat)
    monkeypatch.setattr(os, "fstat", device_fstat)
    adapter = LinuxUsbHub(sysfs_root=root, usbfs_root=usbfs, camera_alias=tmp_path / "cam", led_alias=tmp_path / "led")
    child(root, 3, "303a", "1001")
    return adapter, root, statuses, calls


def child(root, port, vid, pid):
    path = root / f"1-1.{port}"
    path.mkdir(exist_ok=True)
    (path / "idVendor").write_text(vid)
    (path / "idProduct").write_text(pid)
    (path / "busnum").write_text("1")
    (path / "devnum").write_text(str(10 + port))
    (path / "serial").write_text(f"unit-{port}")
    return path


def camera(adapter, root, vid="0ac8", pid="0346", *, caps=0x80000001, device_caps=1, alias=False):
    usb_child = child(root, 4, vid, pid)
    interface = usb_child / "1-1.4:1.0"
    interface.mkdir()
    (interface / "bInterfaceClass").write_text("0e")
    driver = root.parent / "drivers" / "uvcvideo"
    driver.mkdir(parents=True, exist_ok=True)
    (interface / "driver").symlink_to(driver)
    video = interface / "video4linux" / "video0"
    video.mkdir(parents=True)
    (video / "index").write_text("0")
    (video / "dev").write_text("81:0")
    (video / "device").symlink_to(interface)
    classes = root.parent.parent.parent / "class" / "video4linux"
    classes.mkdir(parents=True, exist_ok=True)
    (classes / "video0").symlink_to(video)
    node = adapter.usbfs_root.parent.parent / "video0"
    node.write_bytes(struct.pack("<II", caps, device_caps))
    if alias:
        adapter.aliases[4].symlink_to(node)
    return usb_child, interface, video, node


@pytest.mark.parametrize("vid,pid", [("0ac8", "0346"), ("0bdc", "2710"), ("1234", "5678")])
@pytest.mark.parametrize("alias", [False, True])
def test_camera_port_accepts_uvc_capture_independent_of_vid(tmp_path, monkeypatch, vid, pid, alias):
    adapter, root, statuses, calls = fake_usb(tmp_path, monkeypatch)
    camera(adapter, root, vid, pid, alias=alias)
    snapshot = adapter.snapshot()
    assert snapshot.valid, snapshot.reason
    assert snapshot.ports[4].child_identity == (vid, pid)
    assert snapshot.ports[4].child_address == (1, 14)
    assert snapshot.ports[4].child_serial == "unit-4"
    assert not snapshot.ports[4].candidate
    assert any(request == 0x80685600 for request, _ in calls)


@pytest.mark.parametrize("defect", ["non-video", "unbound", "wrong-driver", "index", "no-node", "no-class"])
def test_camera_requires_complete_uvc_primary_node_evidence(tmp_path, monkeypatch, defect):
    adapter, root, statuses, calls = fake_usb(tmp_path, monkeypatch)
    usb_child, interface, video, node = camera(adapter, root)
    if defect == "non-video":
        (interface / "bInterfaceClass").write_text("ff")
    elif defect == "unbound":
        (interface / "driver").unlink()
    elif defect == "wrong-driver":
        (interface / "driver").unlink()
        other = root.parent / "drivers" / "other"
        other.mkdir()
        (interface / "driver").symlink_to(other)
    elif defect == "index":
        (video / "index").write_text("1")
    elif defect == "no-node":
        node.unlink()
    else:
        (root.parent.parent.parent / "class" / "video4linux" / "video0").unlink()
    assert not adapter.snapshot().valid


@pytest.mark.parametrize("caps,device_caps", [(0x80000001, 0x00800000), (0x80000001, 0), (0x00800000, 1)])
def test_camera_selected_node_must_have_its_own_capture_capability(tmp_path, monkeypatch, caps, device_caps):
    adapter, root, statuses, calls = fake_usb(tmp_path, monkeypatch)
    camera(adapter, root, caps=caps, device_caps=device_caps, alias=True)
    assert not adapter.snapshot().valid


@pytest.mark.parametrize("caps,device_caps", [(1, 0), (0x80001000, 0x1000)])
def test_camera_accepts_legacy_or_multiplanar_capture_capability(tmp_path, monkeypatch, caps, device_caps):
    adapter, root, statuses, calls = fake_usb(tmp_path, monkeypatch)
    camera(adapter, root, caps=caps, device_caps=device_caps)
    value = adapter.snapshot()
    assert value.valid, value.reason


def test_camera_alias_cannot_select_metadata_instead_of_capture(tmp_path, monkeypatch):
    adapter, root, statuses, calls = fake_usb(tmp_path, monkeypatch)
    usb_child, interface, video, node = camera(adapter, root)
    metadata = video.parent / "video1"
    metadata.mkdir()
    (metadata / "index").write_text("1")
    (metadata / "dev").write_text("81:1")
    (metadata / "device").symlink_to(interface)
    (root.parent.parent.parent / "class" / "video4linux" / "video1").symlink_to(metadata)
    metadata_node = node.with_name("video1")
    metadata_node.write_bytes(struct.pack("<II", 0x80000001, 0x00800000))
    adapter.aliases[4].symlink_to(metadata_node)
    assert not adapter.snapshot().valid


@pytest.mark.parametrize("target", ["dangling", "regular", "other-child"])
def test_camera_alias_rejects_dangling_noncharacter_and_other_child(tmp_path, monkeypatch, target):
    adapter, root, statuses, calls = fake_usb(tmp_path, monkeypatch)
    usb_child, interface, video, node = camera(adapter, root)
    if target == "dangling":
        adapter.aliases[4].symlink_to(node.with_name("missing"))
    elif target == "regular":
        regular = tmp_path / "regular-file"
        regular.touch()
        adapter.aliases[4].symlink_to(regular)
    else:
        other = child(root, 3, "303a", "1001") / "1-1.3:1.0"
        other.mkdir()
        (video / "device").unlink()
        (video / "device").symlink_to(other)
        adapter.aliases[4].symlink_to(node)
    assert not adapter.snapshot().valid


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
    camera(adapter, root)
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
        camera(adapter, root)
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
    camera(adapter, root)
    statuses[4] = 0x103
    (root / "1-1.3" / "idVendor").unlink()
    (root / "1-1.3" / "idProduct").unlink()
    for name in ("busnum", "devnum", "serial"):
        (root / "1-1.3" / name).unlink()
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


def test_snapshot_exposes_dynamic_hub_and_esp_address_and_serial(tmp_path, monkeypatch):
    adapter, root, statuses, calls = fake_usb(tmp_path, monkeypatch)
    esp = root / "1-1.3"
    (esp / "busnum").write_text("1")
    (esp / "devnum").write_text("13")
    (esp / "serial").write_text("dynamic-esp-unit-a\n")
    value = adapter.snapshot()
    assert value.valid
    assert value.address == (1, 7)
    assert value.ports[3].child_address == (1, 13)
    assert value.ports[3].child_serial == "dynamic-esp-unit-a"
