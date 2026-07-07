"""Local filesystem storage backend — bytes under ``data/`` (current behaviour).

``is_remote = False`` → the app serves bytes itself with HTTP Range; clients are
never redirected. This reproduces today's ``ASSET_BASE = Path("data")`` logic
behind the ``StorageBackend`` contract so ``STORAGE_BACKEND=local`` is a no-op.
"""
from __future__ import annotations

from pathlib import Path

from katrain.web.core.storage.base import PutData, StorageBackend, normalize_key

ASSETS_URL_PREFIX = "/api/v1/tutorials/assets"


class LocalStorageBackend(StorageBackend):
    is_remote = False

    def __init__(self, base_dir: str | Path = "data"):
        self._base = Path(base_dir)

    def _path(self, key: str) -> Path:
        return self._base / normalize_key(key)

    def put(self, key: str, data: PutData, *, content_type: str | None = None) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(data, (bytes, bytearray)):
            path.write_bytes(bytes(data))
        else:
            with open(path, "wb") as f:
                # Stream in chunks to avoid loading large videos fully in memory.
                for chunk in iter(lambda: data.read(1024 * 1024), b""):
                    f.write(chunk)

    def exists(self, key: str) -> bool:
        path = self._path(key)
        return path.exists() and path.is_file()

    def size(self, key: str) -> int:
        return self._path(key).stat().st_size

    def read(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def read_range(self, key: str, start: int, length: int) -> bytes:
        with open(self._path(key), "rb") as f:
            f.seek(start)
            return f.read(length)

    def list_keys(self, prefix: str) -> set[str]:
        root = self._path(prefix)
        if not root.is_dir():
            return set()
        return {p.relative_to(self._base).as_posix() for p in root.rglob("*") if p.is_file()}

    def public_url(self, key: str) -> str:
        return f"{ASSETS_URL_PREFIX}/{normalize_key(key)}"

    def fspath(self, key: str) -> Path:
        return self._path(key)
