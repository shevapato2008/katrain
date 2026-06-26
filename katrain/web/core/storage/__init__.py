"""Storage backend factory.

``get_storage_backend()`` returns a memoized singleton chosen by
``settings.STORAGE_BACKEND`` (``local`` | ``s3``). See
superpowers/tracks/tutorial-database/plan.md.
"""
from __future__ import annotations

from katrain.web.core.storage.base import StorageBackend, normalize_key
from katrain.web.core.storage.local import LocalStorageBackend

__all__ = ["StorageBackend", "normalize_key", "get_storage_backend"]

_backend: StorageBackend | None = None


def _build_backend() -> StorageBackend:
    from katrain.web.core.config import settings

    kind = (getattr(settings, "STORAGE_BACKEND", "local") or "local").lower()
    if kind == "s3":
        # Imported lazily so boto3 is only required when actually using S3.
        from katrain.web.core.storage.s3 import S3StorageBackend

        return S3StorageBackend()
    return LocalStorageBackend()


def get_storage_backend() -> StorageBackend:
    global _backend
    if _backend is None:
        _backend = _build_backend()
    return _backend
