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


def upload_file(key: str, local_path, *, content_type: str | None = None) -> bool:
    """Write-through helper for media generators (Task 6).

    Per D8 the generator always writes the canonical copy to local disk; this
    pushes that file to the object store *only when the backend is remote*
    (for the local backend the disk file already is the store, so it's a no-op).
    Failures are logged and swallowed — a missing upload can be re-synced by the
    migration script — so a single bad upload never aborts a batch run.
    Returns True if an upload happened and succeeded.
    """
    import logging

    backend = get_storage_backend()
    if not backend.is_remote:
        return False
    try:
        with open(local_path, "rb") as f:
            backend.put(key, f, content_type=content_type)
        return True
    except Exception as e:  # noqa: BLE001 — best-effort write-through
        logging.getLogger("katrain_web").warning("Object-store upload failed for %s: %s", key, e)
        return False
