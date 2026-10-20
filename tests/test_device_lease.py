"""Shared camera and LED leases must work with a read-only service home."""

import os
import subprocess
import sys

import pytest

from katrain.web.core.device_lease import DeviceLease


@pytest.mark.parametrize("kind", ["camera", "led"])
def test_explicit_lease_dir_works_without_writable_home_and_blocks_peer(tmp_path, monkeypatch, kind):
    lease_dir = tmp_path / "shared-leases"
    unusable_home = tmp_path / "home-is-a-file"
    unusable_home.touch()
    monkeypatch.setenv("HOME", str(unusable_home))
    monkeypatch.setenv("SMARTBOX_DEVICE_LEASE_DIR", str(lease_dir))
    device = f"test-{kind}"

    lease = DeviceLease.acquire(kind, device)
    try:
        assert len(list(lease_dir.glob(f"{kind}-*.lock"))) == 1
        script = """import sys
from katrain.web.core.device_lease import DeviceBusy, DeviceLease
try:
    lease = DeviceLease.acquire(sys.argv[1], sys.argv[2])
except DeviceBusy:
    sys.exit(0)
else:
    lease.release()
    sys.exit(1)
"""
        result = subprocess.run(
            [sys.executable, "-c", script, kind, device],
            env=os.environ.copy(), capture_output=True, text=True, timeout=5,
        )
        assert result.returncode == 0, result.stderr
    finally:
        lease.release()


def test_lease_dir_defaults_to_home_when_unset(tmp_path, monkeypatch):
    monkeypatch.delenv("SMARTBOX_DEVICE_LEASE_DIR", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    lease = DeviceLease.acquire("camera", "home-fallback")
    try:
        assert len(list((tmp_path / ".katrain" / "device-leases").glob("camera-*.lock"))) == 1
    finally:
        lease.release()


def test_home_fallback_keeps_distinct_devices_independent(tmp_path, monkeypatch):
    monkeypatch.delenv("SMARTBOX_DEVICE_LEASE_DIR", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    first = DeviceLease.acquire("camera", "/dev/video0")
    try:
        second = DeviceLease.acquire("camera", "/dev/video1")
        second.release()
        assert len(list((tmp_path / ".katrain" / "device-leases").glob("camera-*.lock"))) == 2
    finally:
        first.release()


@pytest.mark.parametrize("kind,target_name", [("camera", "video73"), ("led", "ttyACM0")])
def test_absent_alias_keeps_peer_out_after_hotplug(tmp_path, monkeypatch, kind, target_name):
    monkeypatch.setenv("SMARTBOX_DEVICE_LEASE_DIR", str(tmp_path / "leases"))
    alias = tmp_path / f"smartbox-{kind}"
    target = tmp_path / target_name
    owner = DeviceLease.acquire(kind, str(alias))
    try:
        target.touch()
        alias.symlink_to(target)
        script = """import sys
from katrain.web.core.device_lease import DeviceBusy, DeviceLease
try:
    peer = DeviceLease.acquire(sys.argv[1], sys.argv[2])
except DeviceBusy:
    sys.exit(0)
else:
    peer.release()
    sys.exit(1)
"""
        for peer_device in (alias, target):
            result = subprocess.run(
                [sys.executable, "-c", script, kind, str(peer_device)],
                env=os.environ.copy(), capture_output=True, text=True, timeout=5,
            )
            assert result.returncode == 0, f"peer {peer_device} acquired lease: {result.stderr}"
        retarget = tmp_path / f"new-{target_name}"
        retarget.touch()
        alias.unlink()
        alias.symlink_to(retarget)
        for peer_device in (alias, retarget):
            result = subprocess.run(
                [sys.executable, "-c", script, kind, str(peer_device)],
                env=os.environ.copy(), capture_output=True, text=True, timeout=5,
            )
            assert result.returncode == 0, f"retargeted peer {peer_device} acquired lease: {result.stderr}"
    finally:
        owner.release()

    peer = DeviceLease.acquire(kind, str(target))
    peer.release()
