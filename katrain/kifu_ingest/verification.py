"""Finite verification GETs and local checkpoints of completely checked albums."""

import asyncio
import json
import math
import os
from pathlib import Path
import stat
from urllib.parse import urlsplit, urlunsplit

import httpx

from katrain.kifu_ingest.staging import Stage
from katrain.web.kifu.name_candidates import canonical_sha256


ALGORITHM_VERSION = "album-api-five-languages-public-card-v1"
RANK_ALGORITHM_VERSION = "album-api-five-languages-public-card-ranks-v2"
CHECKPOINT_TTL = 24 * 60 * 60
_MAX_CHECKPOINT_BYTES = 8 * 1024 * 1024
_TRANSIENT = (httpx.TimeoutException, httpx.NetworkError, httpx.RemoteProtocolError)


def normalized_target(base_url):
    parsed = urlsplit(base_url)
    if (
        parsed.scheme.lower() not in ("http", "https")
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("album API target must be an HTTP base URL")
    scheme, host, port = parsed.scheme.lower(), parsed.hostname.lower(), parsed.port
    if ":" in host:
        host = f"[{host}]"
    authority = host if port is None or port == {"http": 80, "https": 443}[scheme] else f"{host}:{port}"
    return urlunsplit((scheme, authority, parsed.path.rstrip("/"), "", ""))


def _finite_number(value):
    return type(value) in (int, float) and math.isfinite(value)


class VerificationDeadlineExceeded(TimeoutError):
    """The caller's absolute monotonic verification budget was exhausted."""


class VerificationGET:
    def __init__(self, client, *, timeout, deadline, clock, sleep):
        if not _finite_number(timeout) or timeout <= 0:
            raise ValueError("verification timeout must be finite and positive")
        if deadline is not None and not _finite_number(deadline):
            raise ValueError("verification deadline must be finite")
        self.client, self.timeout, self.deadline = client, timeout, deadline
        self.clock, self.sleep = clock, sleep

    def remaining(self):
        remaining = float("inf") if self.deadline is None else self.deadline - self.clock()
        if remaining <= 0:
            raise VerificationDeadlineExceeded("album API verification deadline exhausted")
        return remaining

    async def get(self, url, params):
        for attempt in range(2):
            timeout = min(self.timeout, self.remaining())
            try:
                response = await asyncio.wait_for(self.client.get(url, params=params, timeout=timeout), timeout=timeout)
            except _TRANSIENT + (TimeoutError,) as exc:
                remaining = self.remaining()
                if attempt:
                    if isinstance(exc, TimeoutError):
                        raise TimeoutError("album API request wall-clock timeout") from exc
                    raise
                try:
                    await asyncio.wait_for(self.sleep(min(0.25, remaining)), timeout=remaining)
                except TimeoutError:
                    self.remaining()
                    raise
            else:
                self.remaining()
                return response


class AlbumCheckpoint:
    """A writer-locked local stage may reuse only exact-bound, unexpired evidence.

    The caller owns the stage writer lock. This journal never changes batch state;
    its entries are validated again before they can contribute returned checks.
    """

    def __init__(self, directory, manifest, receipt, target, languages, validate, wall_clock, *, algorithm=None):
        self.directory = Path(directory) if directory is not None else None
        self.wall_clock, self.validate = wall_clock, validate
        self.binding = {
            "manifest_sha256": canonical_sha256(manifest),
            "receipt_sha256": canonical_sha256(receipt),
            "target": target,
            "algorithm": ALGORITHM_VERSION if algorithm is None else algorithm,
            "languages": list(languages),
        }
        self.completed = {}
        if self.directory is None:
            return
        self.path = self.directory / f"{canonical_sha256(self.binding)}.json"
        self._safe_path()
        if not self.path.exists():
            return
        try:
            fd = os.open(self.path, os.O_RDONLY | os.O_NOFOLLOW)
            with os.fdopen(fd, "rb") as handle:
                info = os.fstat(handle.fileno())
                if not stat.S_ISREG(info.st_mode) or not 0 < info.st_size <= _MAX_CHECKPOINT_BYTES:
                    raise ValueError("checkpoint must be a bounded regular file")
                raw = handle.read(info.st_size + 1)
                if len(raw) != info.st_size:
                    raise ValueError("checkpoint changed during read")
            record = json.loads(raw)
            if not isinstance(record, dict) or set(record) != {"version", "binding", "completed", "content_sha256"}:
                raise ValueError("checkpoint structure is invalid")
            payload = {key: value for key, value in record.items() if key != "content_sha256"}
            if (
                type(record["version"]) is not int
                or record["version"] != 1
                or record["binding"] != self.binding
                or record["content_sha256"] != canonical_sha256(payload)
                or not isinstance(record["completed"], dict)
            ):
                raise ValueError("checkpoint content or binding is invalid")
            now = self.wall_clock()
            if not _finite_number(now):
                raise ValueError("checkpoint clock is invalid")
            for key, completed in record["completed"].items():
                self.validate(key, completed)
                timestamp = completed["completed_at"]
                if not _finite_number(timestamp) or timestamp > now:
                    raise ValueError("checkpoint completion time is invalid")
                if now - timestamp < CHECKPOINT_TTL:
                    self.completed[key] = completed
        except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
            raise ValueError("album verification checkpoint is corrupt or inconsistent") from exc

    def _safe_path(self):
        if not self.directory.is_absolute():
            raise ValueError("checkpoint directory must be absolute")
        for directory in (self.directory, *self.directory.parents):
            if directory.is_symlink() or directory.exists() and not directory.is_dir():
                raise ValueError("checkpoint directory is unsafe")
        if self.path.is_symlink() or self.path.exists() and not self.path.is_file():
            raise ValueError("checkpoint file is unsafe")

    def get(self, key):
        completed = self.completed.get(key)
        if completed is not None:
            age = self.wall_clock() - completed["completed_at"]
            if not 0 <= age < CHECKPOINT_TTL:
                del self.completed[key]
                return None
        return completed

    def save(self, key, completed):
        if self.directory is None:
            return
        self.validate(key, completed)
        self._safe_path()
        self.directory.mkdir(parents=True, exist_ok=True)
        self._safe_path()
        self.completed[key] = completed
        payload = {"version": 1, "binding": self.binding, "completed": self.completed}
        record = {**payload, "content_sha256": canonical_sha256(payload)}
        Stage._atomic(self.path, json.dumps(record, ensure_ascii=False, sort_keys=True).encode("utf-8"))
