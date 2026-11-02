"""Bound-account history reads and the durable row outbox for a shared board."""

import asyncio
from copy import deepcopy
from datetime import datetime
import hashlib
import logging
import re

import httpx

from katrain.core.baipu_identity import BAIPU_REPLAY_VERSION
from katrain.web.core.baipu_history import (
    BaipuHistoryConflict,
    BaipuHistoryNotFound,
    BaipuHistoryValidationError,
    IMMUTABLE,
    validate_snapshot,
)
from katrain.web.core.remote_client import RemoteHistoryIdentityChanged

logger = logging.getLogger("katrain_web")
_HEX64 = re.compile(r"^[0-9a-f]{64}$")


class BaipuHistoryUnavailable(RuntimeError):
    code = "history_cloud_unavailable"


def _validate_remote(remote, *, record_id=None, detail=False, sent=None, receipt=False):
    """Reject incomplete receipts before they can settle a durable pending row."""
    if not isinstance(remote, dict):
        raise BaipuHistoryValidationError("Invalid cloud snapshot")
    digest = remote.get("sgf_sha256")
    version = remote.get("replay_version")
    if (
        not isinstance(digest, str)
        or not _HEX64.fullmatch(digest)
        or type(version) is not int
        or version != BAIPU_REPLAY_VERSION
    ):
        raise BaipuHistoryValidationError("Invalid cloud identity")
    expected_id = hashlib.sha256(f"baipu:{version}:{digest}".encode("ascii")).hexdigest()
    if remote.get("id") != expected_id or (record_id is not None and record_id != expected_id):
        raise BaipuHistoryValidationError("Cloud identity does not match request")
    for key in ("k", "total", "local_revision", "cloud_revision"):
        if type(remote.get(key)) is not int or remote[key] < (1 if key == "total" else 0):
            raise BaipuHistoryValidationError(f"Invalid cloud {key}")
    if remote["k"] > remote["total"] or remote.get("completed") is not (remote["k"] == remote["total"]):
        raise BaipuHistoryValidationError("Invalid cloud cursor")
    for key, bound in (("source_id", 128), ("name", 512)):
        if not isinstance(remote.get(key), str) or len(remote[key]) > bound:
            raise BaipuHistoryValidationError(f"Invalid cloud {key}")
    for key in ("updated_at", "completed_at"):
        value = remote.get(key)
        if value is None and key == "completed_at" and not remote["completed"]:
            continue
        try:
            timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if timestamp.tzinfo is None:
                raise ValueError("Timezone missing")
        except (ValueError, AttributeError, TypeError) as exc:
            raise BaipuHistoryValidationError("Invalid cloud timestamp") from exc
    if detail or receipt:
        snapshot = validate_snapshot(remote)
        if snapshot["id"] != expected_id:
            raise BaipuHistoryValidationError("Cloud SGF identity mismatch")
    if sent is not None:
        if any(remote.get(key) != sent.get(key) for key in IMMUTABLE):
            raise BaipuHistoryValidationError("Cloud immutable snapshot mismatch")
    if receipt:
        writer, sequence = remote.get("last_writer_id"), remote.get("last_writer_seq")
        if (
            writer != sent["writer_id"]
            or type(sequence) is not int
            or sequence < sent["writer_seq"]
            or (sequence == sent["writer_seq"] and remote["k"] != sent["k"])
        ):
            raise BaipuHistoryValidationError("Invalid cloud writer receipt")
    return deepcopy(remote)


class BaipuHistoryService:
    def __init__(self, repo, remote_client=None, connectivity=None):
        self.repo = repo
        self.remote_client = remote_client
        self.connectivity = connectivity
        # Set to the existing SyncWorker.run_sync by board startup. Each wake shares
        # that worker's lock; writes never wait for HTTP or recursively run the drain.
        self.wake_sync = None
        self._wake_task = None

    def _may_use_cloud(self, user_id):
        return (
            self.remote_client is not None
            and (self.connectivity is None or self.connectivity.is_online)
            and self.remote_client.cloud_session_is(user_id)
        )

    def _wake(self):
        if self.wake_sync is None or (self._wake_task is not None and not self._wake_task.done()):
            return

        async def wake():
            try:
                await self.wake_sync()
            except Exception:
                logger.warning("Could not wake history sync", exc_info=True)

        self._wake_task = asyncio.create_task(wake())

    def _decorate(self, row, authority=None):
        result = deepcopy(row)
        if authority is None:
            authority = "this_node" if self.remote_client is None else "local_cache"
        if self.remote_client is not None and result.get("sync_state") in ("pending", "conflict", "refused"):
            authority = "local_cache"
        result["authority"] = authority
        return result

    def _summary(self, row, authority=None):
        result = self._decorate(row, authority)
        result.pop("sgf_content", None)
        result.pop("conflict_remote", None)
        return result

    def _conflict(self, code, current):
        return BaipuHistoryConflict(code, self._decorate(current) if current is not None else None)

    async def open(self, user_id, data):
        if self.remote_client is None:
            return self._decorate(self.repo.open(user_id, data))
        snapshot = validate_snapshot(data)
        # An uncached cloud cursor must be discovered before creating a pending zero.
        if self._may_use_cloud(user_id):
            try:
                remote = await self.remote_client.baipu_history_get(user_id, snapshot["id"])
                remote = _validate_remote(remote, record_id=snapshot["id"], detail=True)
                winner = self.repo.adopt_clean(user_id, [remote])[0]
                return self._decorate(winner, "cloud")
            except (httpx.HTTPError, RemoteHistoryIdentityChanged, BaipuHistoryValidationError):
                pass
        row = self.repo.open(user_id, data, board=True)
        self._wake()
        return self._decorate(row)

    async def list(self, user_id, limit):
        local = self.repo.list(user_id, limit)
        if self.remote_client is None:
            return {"items": [self._summary(row) for row in local], "authority": "this_node"}
        if self._may_use_cloud(user_id):
            try:
                response = await self.remote_client.baipu_history_list(user_id, limit)
                if (
                    not isinstance(response, dict)
                    or not isinstance(response.get("items"), list)
                    or len(response["items"]) > limit
                ):
                    raise BaipuHistoryValidationError("Invalid cloud history list")
                remote = [_validate_remote(row) for row in response["items"]]
                winners = self.repo.adopt_clean(user_id, remote)
                # Read local rows again: a cursor may have changed while GET awaited.
                local = self.repo.list(user_id, limit)
                merged = {row["id"]: self._summary(row, "cloud") for row in winners}
                for row in local:
                    if row["id"] not in merged or row["sync_state"] != "synced":
                        merged[row["id"]] = self._summary(row)
                items = sorted(merged.values(), key=lambda row: (row["updated_at"], row["id"]), reverse=True)[:limit]
                return {"items": items, "authority": "cloud"}
            except (httpx.HTTPError, RemoteHistoryIdentityChanged, BaipuHistoryValidationError):
                local = self.repo.list(user_id, limit)
        return {"items": [self._summary(row) for row in local], "authority": "local_cache"}

    async def get(self, user_id, record_id):
        if not isinstance(record_id, str) or not _HEX64.fullmatch(record_id):
            raise BaipuHistoryValidationError("Invalid record identity")
        if self.remote_client is None:
            return self._decorate(self.repo.get(user_id, record_id))
        if self._may_use_cloud(user_id):
            try:
                remote = await self.remote_client.baipu_history_get(user_id, record_id)
                remote = _validate_remote(remote, record_id=record_id, detail=True)
                return self._decorate(self.repo.adopt_clean(user_id, [remote])[0], "cloud")
            except (httpx.HTTPError, RemoteHistoryIdentityChanged, BaipuHistoryValidationError):
                pass
        return self._decorate(self.repo.get(user_id, record_id))

    async def save(self, user_id, record_id, data):
        try:
            row = self.repo.save(user_id, record_id, data, board=self.remote_client is not None)
        except BaipuHistoryConflict as exc:
            raise self._conflict(exc.code, exc.current) from exc
        if self.remote_client is not None:
            self._wake()
        return self._decorate(row)

    async def accept_sync(self, user_id, record_id, data):
        if self.remote_client is not None:
            raise BaipuHistoryUnavailable("History sync requires an authoritative node")
        return self._decorate(self.repo.accept_sync(user_id, record_id, data))

    async def resolve(self, user_id, record_id, strategy, expected_local_revision):
        current = self.repo.get(user_id, record_id)
        if current["local_revision"] != expected_local_revision:
            raise self._conflict("stale_local_revision", current)
        if self.remote_client is None:
            raise BaipuHistoryUnavailable("This node has no cloud conflict to resolve")
        if not self.remote_client.cloud_session_is(user_id):
            raise self._conflict("identity_changed", current)
        if not self._may_use_cloud(user_id):
            raise BaipuHistoryUnavailable("Cloud history is offline")
        try:
            remote = await self.remote_client.baipu_history_get(user_id, record_id)
            remote = _validate_remote(remote, record_id=record_id, detail=True)
        except RemoteHistoryIdentityChanged as exc:
            raise self._conflict("identity_changed", self.repo.get(user_id, record_id)) from exc
        except (httpx.HTTPError, BaipuHistoryValidationError) as exc:
            raise BaipuHistoryUnavailable("Could not read current cloud history") from exc
        remote["_expected_writer_id"] = current["writer_id"]
        try:
            row = self.repo.resolve(user_id, record_id, strategy, remote, expected_local_revision)
        except BaipuHistoryConflict as exc:
            raise self._conflict(exc.code, exc.current) from exc
        if row["sync_state"] == "pending":
            self._wake()
        return self._decorate(row, "cloud")

    async def sync_pending(self):
        if self.remote_client is None or (self.connectivity is not None and not self.connectivity.is_online):
            return 0
        owner = self.remote_client.bound_user_id
        if not self._may_use_cloud(owner):
            return 0
        synced = 0
        # One captured snapshot per row per drain: no busy retry after a refusal,
        # malformed receipt, newer local step, or an unavailable cloud.
        for sent in self.repo.pending_snapshots(user_id=owner):
            user_id, record_id, payload = sent["user_id"], sent["id"], sent["payload"]
            if not self._may_use_cloud(user_id):
                continue
            try:
                remote = await self.remote_client.baipu_history_sync(user_id, record_id, payload)
                remote = _validate_remote(remote, record_id=record_id, sent=payload, receipt=True)
                self.repo.absorb_success(user_id, record_id, sent, remote)
                synced += 1
            except RemoteHistoryIdentityChanged:
                continue
            except httpx.HTTPStatusError as exc:
                status = exc.response.status_code
                if status == 409:
                    try:
                        body = exc.response.json()
                        conflict = body.get("detail", body)
                        remote = _validate_remote(
                            conflict.get("current"), record_id=record_id, detail=True, sent=payload
                        )
                        self.repo.absorb_conflict(user_id, record_id, sent, remote)
                    except (ValueError, AttributeError, TypeError, BaipuHistoryConflict):
                        logger.warning("Ignoring malformed history conflict for %s", record_id)
                elif status in (400, 422):
                    self.repo.mark_refused(user_id, record_id, sent, f"HTTP {status}")
            except (httpx.HTTPError, BaipuHistoryValidationError, BaipuHistoryNotFound):
                continue
        return synced
