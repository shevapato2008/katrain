"""Frozen-dataset transfer protocol only. No SSH implementation or API enablement.

Future adapters must hash remote bytes, scope staging to (id, manifest hash),
and publish on the same volume without replacing an existing final version.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from katrain.web.admin.vision_dataset import VisionDatasetError, _json

MAX_BYTES = 2 * 1024**3
MAX_FILE_BYTES = 64 * 1024**2
MAX_FILES = 8192
MAX_MANIFEST_BYTES = 8 * 1024**2
RESERVE_BYTES = 256 * 1024**2
DATASET_ID = re.compile(r"dataset-[0-9a-f]{64}")


class VisionTransferError(RuntimeError):
    def __init__(self, status_code, message):
        super().__init__(message)
        self.status_code = status_code


@dataclass(frozen=True)
class TransferConfig:
    enabled: bool = False
    host: str = "home-ubuntu"
    remote_root: str | None = None
    reserve_bytes: int = RESERVE_BYTES


@dataclass(frozen=True)
class FileReceipt:
    name: str
    size: int
    sha256: str


@dataclass(frozen=True)
class TransferPlan:
    dataset_id: str
    directory: Path
    manifest_sha256: str
    files: tuple[FileReceipt, ...]
    total_bytes: int


@dataclass(frozen=True)
class TransferReceipt:
    dataset_id: str
    manifest_sha256: str
    files: tuple[FileReceipt, ...]


@dataclass(frozen=True)
class RemoteSnapshot:
    available_bytes: int
    staged: TransferReceipt
    final: TransferReceipt | None = None


@dataclass(frozen=True)
class TransferResult:
    state: str
    plan: TransferPlan
    idempotent: bool = False


def _digest(path):
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        while data := handle.read(1024 * 1024):
            hasher.update(data)
    return hasher.hexdigest()


def _safe_name(name):
    return (
        isinstance(name, str)
        and bool(name)
        and "\\" not in name
        and "\x00" not in name
        and not PurePosixPath(name).is_absolute()
        and PurePosixPath(name).as_posix() == name
        and all(part not in (".", "..") for part in name.split("/"))
    )


class VisionDatasetTransfer:
    def __init__(self, builder, *, config=None, transport=None, max_bytes=MAX_BYTES):
        self.builder = builder
        self.config = config or TransferConfig()
        self.transport = transport
        if type(max_bytes) is not int or not 0 < max_bytes <= MAX_BYTES:
            raise VisionTransferError(422, "Invalid transfer size limit")
        self.max_bytes = max_bytes

    def prepare(self, dataset_id):
        if not isinstance(dataset_id, str) or not DATASET_ID.fullmatch(dataset_id):
            raise VisionTransferError(422, "Invalid frozen dataset ID")
        with self.builder.coordinator.lock:
            directory = self.builder.output_root / dataset_id
            try:
                path = directory / "manifest.json"
                if directory.is_symlink() or not directory.is_dir() or path.is_symlink():
                    raise ValueError("Invalid frozen directory")
                if not path.is_file() or not 0 < path.stat().st_size <= MAX_MANIFEST_BYTES:
                    raise ValueError("Invalid frozen manifest")
                raw = path.read_bytes()
                manifest = json.loads(raw)
                if (
                    manifest["id"] != dataset_id
                    or dataset_id != "dataset-" + hashlib.sha256(_json(manifest["identity"])).hexdigest()
                ):
                    raise ValueError("Frozen identity mismatch")
                assets = manifest["assets"]
                if not isinstance(assets, dict) or not 0 < len(assets) < MAX_FILES or "manifest.json" in assets:
                    raise ValueError("Invalid frozen assets")
                entries, total = [], 0
                for name in sorted([*assets, "manifest.json"]):
                    if not _safe_name(name):
                        raise ValueError("Unsafe frozen asset path")
                    source = directory / name
                    if any(parent.is_symlink() for parent in source.parents if parent != directory.parent):
                        raise ValueError("Symlink in frozen asset path")
                    if source.is_symlink() or not source.is_file():
                        raise ValueError("Missing frozen asset")
                    size = source.stat().st_size
                    total += size
                    if size > MAX_FILE_BYTES or total > self.max_bytes:
                        raise VisionTransferError(413, "Frozen transfer exceeds its size limit")
                    digest = _digest(source)
                    if name != "manifest.json" and digest != assets[name]:
                        raise ValueError("Frozen asset hash changed")
                    entries.append(FileReceipt(name, size, digest))
                self.builder._validate(directory, manifest)
                return TransferPlan(dataset_id, directory, hashlib.sha256(raw).hexdigest(), tuple(entries), total)
            except VisionTransferError:
                raise
            except (OSError, ValueError, TypeError, KeyError, VisionDatasetError) as exc:
                raise VisionTransferError(503, "Frozen transfer source validation failed") from exc

    def _require_enabled(self, confirmed):
        config, root = self.config, self.config.remote_root
        if (
            config.enabled is not True
            or config.host != "home-ubuntu"
            or confirmed is not True
            or self.transport is None
            or not isinstance(root, str)
            or not root.startswith("/")
            or root == "/"
            or not _safe_name(root[1:])
            or type(config.reserve_bytes) is not int
            or config.reserve_bytes < 0
        ):
            raise VisionTransferError(403, "Transfer needs a verified target, enabled adapter and single confirmation")

    @staticmethod
    def _receipt_files(receipt, plan):
        if receipt.dataset_id != plan.dataset_id or receipt.manifest_sha256 != plan.manifest_sha256:
            raise VisionTransferError(409, "Remote version identity differs from the frozen source")
        files = {entry.name: entry for entry in receipt.files}
        if len(files) != len(receipt.files) or set(files) - {entry.name for entry in plan.files}:
            raise VisionTransferError(409, "Remote version file set differs from the frozen source")
        return files

    @classmethod
    def _complete(cls, receipt, plan):
        files = cls._receipt_files(receipt, plan)
        return files == {entry.name: entry for entry in plan.files}

    def transfer(self, dataset_id, *, confirmed=False, cancel_event=None):
        self._require_enabled(confirmed)
        plan = self.prepare(dataset_id)
        cancelled = lambda: cancel_event is not None and cancel_event.is_set()
        if cancelled():
            return TransferResult("cancelled", plan)
        publish_started = False
        try:
            snapshot = self.transport.inspect(self.config, plan)
            if snapshot.final is not None:
                if not self._complete(snapshot.final, plan):
                    raise VisionTransferError(409, "Existing final version conflicts with the frozen source")
                return TransferResult("uploaded", plan, idempotent=True)
            staged = self._receipt_files(snapshot.staged, plan)
            pending = [entry for entry in plan.files if staged.get(entry.name) != entry]
            if (
                type(snapshot.available_bytes) is not int
                or snapshot.available_bytes < sum(entry.size for entry in pending) + self.config.reserve_bytes
            ):
                raise VisionTransferError(507, "Remote capacity is insufficient for the remaining files")
            for entry in pending:
                if cancelled():
                    return TransferResult("cancelled", plan)
                source = plan.directory / entry.name
                if source.stat().st_size != entry.size or _digest(source) != entry.sha256:
                    raise VisionTransferError(503, "Frozen source changed during transfer")
                self.transport.write_file(self.config, plan, entry, source, cancel_event)
            if cancelled():
                return TransferResult("cancelled", plan)
            # Never publish based on a write acknowledgement alone.
            verified = self.transport.inspect(self.config, plan)
            if not self._complete(verified.staged, plan) or self.prepare(dataset_id) != plan:
                raise VisionTransferError(503, "Staged file verification failed")
            if cancelled():
                return TransferResult("cancelled", plan)
            publish_started = True
            receipt = self.transport.publish(self.config, plan)
            try:
                if self._complete(receipt, plan):
                    return TransferResult("uploaded", plan)
            except VisionTransferError:
                pass
            return TransferResult("unverified", plan)
        except OSError:
            return TransferResult("unverified" if publish_started else "interrupted", plan)
