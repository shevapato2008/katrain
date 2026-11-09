"""Restricted Linux adapter for the verified four-port smartbox USB hub.

Only the fixed child entry point below performs USBDEVFS_RESET. It inherits the
coordinator's operation lock and revalidates the complete topology immediately
before ioctl. No shell, port power changes, or driver unbinding are involved.
"""

from __future__ import annotations

import ctypes
import fcntl
import os
import re
import stat
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path


class UsbControl(ctypes.Structure):
    _fields_ = [
        ("bRequestType", ctypes.c_uint8),
        ("bRequest", ctypes.c_uint8),
        ("wValue", ctypes.c_uint16),
        ("wIndex", ctypes.c_uint16),
        ("wLength", ctypes.c_uint16),
        ("timeout", ctypes.c_uint32),
        ("data", ctypes.c_void_p),
    ]


USBDEVFS_CONTROL = (3 << 30) | (ctypes.sizeof(UsbControl) << 16) | (ord("U") << 8)
USBDEVFS_RESET = (ord("U") << 8) | 20


@dataclass(frozen=True)
class PortSnapshot:
    number: int
    connected: bool
    powered: bool
    enabled: bool
    reset: bool
    over_current: bool
    child_identity: tuple[str, str] | None = None
    child_path: str | None = None

    @property
    def candidate(self):
        return (
            self.connected
            and self.powered
            and not self.enabled
            and not self.reset
            and not self.over_current
            and self.child_identity is None
        )


@dataclass(frozen=True)
class HubSnapshot:
    valid: bool
    hub_path: str = "1-1"
    identity: tuple[str, str] | None = None
    ports: dict[int, PortSnapshot] = field(default_factory=dict)
    reason: str = ""


class LinuxUsbHub:
    HUB_ID = ("1a40", "0101")
    TARGETS = {3: ("303a", "1001"), 4: ("0ac8", "0346")}

    def __init__(
        self,
        hub_path="1-1",
        camera_port=4,
        led_port=3,
        *,
        sysfs_root="/sys/bus/usb/devices",
        usbfs_root="/dev/bus/usb",
        camera_alias="/dev/smartbox-cam",
        led_alias="/dev/smartbox-led",
    ):
        if hub_path != "1-1" or not re.fullmatch(r"[1-9][0-9]*-[1-9][0-9]*(?:\.[1-9][0-9]*)*", hub_path):
            raise ValueError("Only the verified 1-1 hub topology is supported")
        if (camera_port, led_port) != (4, 3):
            raise ValueError("Only camera port 4 and LED port 3 are supported")
        self.hub_path = hub_path
        self.sysfs_root = Path(sysfs_root)
        self.usbfs_root = Path(usbfs_root)
        self.aliases = {4: Path(camera_alias), 3: Path(led_alias)}
        self._opened_address = None

    def _read(self, path, name):
        return (path / name).read_text().strip().lower()

    def _identity(self, path):
        return self._read(path, "idVendor"), self._read(path, "idProduct")

    def _address(self):
        hub = self.sysfs_root / self.hub_path
        if (
            self._identity(hub) != self.HUB_ID
            or int(self._read(hub, "bDeviceClass"), 16) != 9
            or int(self._read(hub, "maxchild")) != 4
        ):
            raise ValueError("Hub identity/class/port count changed")
        address = (int(self._read(hub, "busnum")), int(self._read(hub, "devnum")))
        if not all(1 <= n <= 999 for n in address):
            raise ValueError("Invalid USB address")
        return address

    def _open_usbfs(self):
        address = self._address()
        path = self.usbfs_root / f"{address[0]:03d}" / f"{address[1]:03d}"
        before = os.stat(path, follow_symlinks=False)
        fd = os.open(path, os.O_RDWR | os.O_CLOEXEC | os.O_NOFOLLOW)
        try:
            opened = os.fstat(fd)
            if not stat.S_ISCHR(opened.st_mode) or (before.st_dev, before.st_ino, before.st_rdev) != (
                opened.st_dev,
                opened.st_ino,
                opened.st_rdev,
            ):
                raise ValueError("USB device changed during open")
            # usbfs uses the standard USB character major/minor mapping.
            if opened.st_rdev and (
                os.major(opened.st_rdev) != 189 or os.minor(opened.st_rdev) != (address[0] - 1) * 128 + address[1] - 1
            ):
                raise ValueError("USB character address mismatch")
            if self._address() != address:
                raise ValueError("USB address changed during open")
            self._opened_address = address
            return fd
        except BaseException:
            os.close(fd)
            raise

    @staticmethod
    def _control(fd, request_type, request, value, index, length):
        data = ctypes.create_string_buffer(length)
        control = UsbControl(request_type, request, value, index, length, 1000, ctypes.addressof(data))
        if fcntl.ioctl(fd, USBDEVFS_CONTROL, control) != length:
            raise ValueError("Short USB control response")
        return data.raw

    def _alias_matches(self, alias, child):
        if not os.path.lexists(alias):
            return True
        # A dangling alias is not proof of a device and is unsafe to operate on.
        target = alias.resolve(strict=True)
        info = target.stat()
        if not stat.S_ISCHR(info.st_mode):
            return False
        class_name = "video4linux" if alias == self.aliases[4] else "tty"
        # Resolve the kernel class entry, then find its exact USB device ancestor.
        class_root = self.sysfs_root.parent.parent.parent / "class"
        device = (class_root / class_name / target.name / "device").resolve(strict=True)
        return child.resolve() in (device, *device.parents)

    def _snapshot_fd(self, fd):
        if self._address() != self._opened_address:
            raise ValueError("USB address reused")
        descriptor = self._control(fd, 0xA0, 6, 0x2900, 0, 9)
        if descriptor[0] < 9 or descriptor[1] != 0x29 or descriptor[2] != 4:
            raise ValueError("Unexpected hub descriptor")
        ports = {}
        # Reject every unexpected direct child, including an unconfigured port.
        prefix = self.hub_path + "."
        for entry in self.sysfs_root.iterdir():
            if entry.name.startswith(prefix) and ":" not in entry.name:
                suffix = entry.name[len(prefix) :]
                if suffix not in {"3", "4"}:
                    raise ValueError("Unexpected USB child")
        for number in range(1, 5):
            raw = self._control(fd, 0xA3, 0, 0, number, 4)
            status, change = int.from_bytes(raw[:2], "little"), int.from_bytes(raw[2:], "little")
            child = self.sysfs_root / f"{self.hub_path}.{number}"
            ident = self._identity(child) if child.exists() else None
            port = PortSnapshot(
                number,
                bool(status & 1),
                bool(status & 0x100),
                bool(status & 2),
                bool(status & 0x10),
                bool(status & 8),
                ident,
                child.name if ident else None,
            )
            if port.over_current or change & 8 or port.reset or not port.powered:
                raise ValueError("Unsafe USB port status")
            if number not in self.TARGETS and (port.connected or ident):
                raise ValueError("Unconfigured connected port")
            if ident and (ident != self.TARGETS[number] or not port.connected):
                raise ValueError("USB child identity/status mismatch")
            if number in self.aliases and not self._alias_matches(self.aliases[number], child):
                raise ValueError("Device alias does not identify expected USB child")
            ports[number] = port
        if self._address() != self._opened_address:
            raise ValueError("USB address changed while reading ports")
        return HubSnapshot(True, self.hub_path, self.HUB_ID, ports)

    def snapshot(self):
        fd = None
        try:
            fd = self._open_usbfs()
            return self._snapshot_fd(fd)
        except (OSError, ValueError, IndexError) as exc:
            return HubSnapshot(False, self.hub_path, reason=str(exc))
        finally:
            if fd is not None:
                os.close(fd)

    def start_reset(self, lock_fd, expected_candidates):
        # The only child option narrows operation to the already stable targets.
        if expected_candidates not in ((3,), (4,), (3, 4)):
            raise ValueError("Invalid stable USB candidate set")
        expected_mask = sum(1 << (port - 1) for port in expected_candidates)
        # Production child accepts no topology, paths, executable or reset options.
        if (
            self.sysfs_root != Path("/sys/bus/usb/devices")
            or self.usbfs_root != Path("/dev/bus/usb")
            or self.aliases != {4: Path("/dev/smartbox-cam"), 3: Path("/dev/smartbox-led")}
        ):
            raise ValueError("Reset only supports the fixed production adapter")
        return subprocess.Popen(
            [
                sys.executable,
                "-m",
                "katrain.web.core.linux_usb_hub",
                "--locked-child",
                str(lock_fd),
                str(expected_mask),
            ],
            pass_fds=(lock_fd,),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )


def _locked_child(lock_fd, expected_mask):
    if type(expected_mask) is not int or expected_mask not in (4, 8, 12):
        return 2
    info = os.fstat(lock_fd)
    if not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) != 0o600:
        return 2
    # Taking the already inherited lock is harmless; acquiring a separate fd must fail.
    fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    adapter = LinuxUsbHub()
    fd = adapter._open_usbfs()
    try:
        snapshot = adapter._snapshot_fd(fd)
        if (
            not snapshot.valid
            or sum(1 << (p - 1) for p in (3, 4) if snapshot.ports[p].candidate) != expected_mask
            or not all(snapshot.ports[p].connected for p in (3, 4))
            or any(snapshot.ports[p].child_identity is None and not snapshot.ports[p].candidate for p in (3, 4))
        ):
            return 3
        # This is deliberately the only destructive ioctl in this module.
        fcntl.ioctl(fd, USBDEVFS_RESET, 0)
        return 0
    finally:
        os.close(fd)


if __name__ == "__main__":
    if (
        len(sys.argv) != 4
        or sys.argv[1] != "--locked-child"
        or not sys.argv[2].isdigit()
        or sys.argv[3] not in {"4", "8", "12"}
    ):
        raise SystemExit(2)
    try:
        raise SystemExit(_locked_child(int(sys.argv[2]), int(sys.argv[3])))
    except (OSError, ValueError):
        raise SystemExit(2)
