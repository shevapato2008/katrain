"""Storage backend abstraction for tutorial media (video / audio / page images).

See superpowers/tracks/tutorial-database/plan.md §2 for the architecture.

The database stores object *keys* (relative paths like
``tutorial_assets/<book>/video/fig_1.mp4``); the bytes live behind a
``StorageBackend``. Two implementations share this contract:

* ``LocalStorageBackend`` — bytes on disk under ``data/``, served through the
  app with HTTP Range (current behaviour; ``is_remote = False``).
* ``S3StorageBackend`` — bytes in an S3-compatible store (MinIO ≡ Aliyun OSS);
  the app 302-redirects clients to ``public_url`` (``is_remote = True``).

Swapping backends is a config change, never a schema change.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import BinaryIO, Union

# What ``put`` accepts: raw bytes or a readable binary file object.
PutData = Union[bytes, bytearray, BinaryIO]

# The on-disk / in-bucket root prefix that callers may redundantly include.
ASSET_ROOT_PREFIX = "data/"

# Cache-Control applied to media on upload (S3) and when serving locally.
# 1 day balances smooth web/SBC playback against the fact that content is still
# being regenerated under stable keys (fig_<id>.mp4) during the build-out phase —
# a stale clip self-heals within a day. For the static post-launch library you can
# raise this to ``public, max-age=31536000, immutable`` once keys stop changing
# (or switch to versioned keys / CDN purge on regen). See plan.md Task 7.
MEDIA_CACHE_CONTROL = "public, max-age=86400"


def normalize_key(key: str) -> str:
    """Canonicalise an object key and reject path traversal.

    Accepts the loose forms that flow in from the DB / frontend / callers
    (leading ``/``, an accidental ``data/`` root prefix, Windows backslashes)
    and returns a clean POSIX-style relative key. Raises ``ValueError`` on
    empty input or any ``..`` segment (the security boundary that replaces the
    old ``_safe_asset_path`` resolve check).
    """
    if not key or not key.strip():
        raise ValueError("Empty storage key")

    k = key.replace("\\", "/").strip()
    k = k.lstrip("/")
    if k.startswith(ASSET_ROOT_PREFIX):
        k = k[len(ASSET_ROOT_PREFIX):]

    # Reject traversal on the normalized, slash-split form.
    parts = k.split("/")
    if any(part == ".." for part in parts):
        raise ValueError(f"Illegal storage key (path traversal): {key!r}")

    k = k.lstrip("/")
    if not k:
        raise ValueError(f"Empty storage key after normalization: {key!r}")
    return k


class StorageBackend(ABC):
    """Contract every storage backend must satisfy."""

    #: True when clients should be 302-redirected to ``public_url`` (S3/CDN);
    #: False when the app serves bytes itself (local disk + Range).
    is_remote: bool = False

    @abstractmethod
    def put(self, key: str, data: PutData, *, content_type: str | None = None) -> None:
        """Store ``data`` at ``key`` (overwriting). ``data`` may be bytes or a
        binary file object."""

    @abstractmethod
    def exists(self, key: str) -> bool:
        """Whether an object exists at ``key``."""

    @abstractmethod
    def size(self, key: str) -> int:
        """Byte size of the object. Raises ``FileNotFoundError`` if missing."""

    @abstractmethod
    def read(self, key: str) -> bytes:
        """Return the full object bytes."""

    @abstractmethod
    def read_range(self, key: str, start: int, length: int) -> bytes:
        """Return ``length`` bytes starting at offset ``start`` (for HTTP 206)."""

    @abstractmethod
    def public_url(self, key: str) -> str:
        """A URL the client can fetch the object from. For local this is the
        app-relative ``/assets`` path; for S3 it is the CDN / reverse-proxy URL."""

    def fspath(self, key: str):
        """Local filesystem ``Path`` for ``key`` if this backend is disk-backed,
        else ``None``. Lets the app stream big files via ``FileResponse`` without
        loading them into memory. Remote backends return ``None``."""
        return None
