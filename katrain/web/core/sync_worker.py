"""Offline sync queue worker for board mode.

See design.md Sections 4.5.2–4.5.6 for the full state machine and retry logic.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from katrain.web.core.models_db import SyncQueueEntry
from katrain.web.core.remote_client import RemoteAPIClient

logger = logging.getLogger("katrain_web")

# Lease timeout: if locked_at exceeds this, treat as crashed worker
LEASE_TIMEOUT_SECONDS = 300  # 5 minutes
MAX_BACKOFF_SECONDS = 300  # 5 minutes cap


class RetryableError(Exception):
    """Server 5xx or network timeout — safe to retry."""


class PermanentError(Exception):
    """Client 4xx (except 409) — not retryable."""


class SyncWorker:
    """Processes sync_queue items sequentially with exponential backoff.

    Uses an asyncio.Lock to ensure only one sync run at a time.
    """

    def __init__(
        self,
        session_factory,
        remote_client: RemoteAPIClient,
    ):
        self._session_factory = session_factory
        self._remote_client = remote_client
        self._sync_lock = asyncio.Lock()

    async def run_sync(self) -> int:
        """Process all pending sync items. Returns count of successfully synced items.

        Skips if another sync is already running (lock held).
        """
        if self._sync_lock.locked():
            logger.debug("Sync already running, skipping")
            return 0

        async with self._sync_lock:
            return await self._process_queue()

    async def _process_queue(self) -> int:
        synced = 0
        db: Session = self._session_factory()
        try:
            now = datetime.utcnow()
            items = (
                db.query(SyncQueueEntry)
                .filter(
                    SyncQueueEntry.status == "pending",
                    (SyncQueueEntry.next_retry_at.is_(None)) | (SyncQueueEntry.next_retry_at <= now),
                )
                .order_by(SyncQueueEntry.created_at)
                .all()
            )

            for item in items:
                if self._remote_client.auth_required:
                    logger.warning("Auth required — pausing sync queue")
                    break

                item.status = "in_progress"
                item.locked_at = datetime.utcnow()
                db.commit()

                try:
                    await self._execute_item(item)
                    item.status = "completed"
                    item.synced_at = datetime.utcnow()
                    db.commit()
                    synced += 1
                    logger.info(f"Synced: {item.operation} [{item.idempotency_key[:8]}]")
                except RetryableError as e:
                    self._schedule_retry(item, str(e))
                    db.commit()
                except PermanentError as e:
                    item.status = "failed"
                    item.last_error = str(e)
                    db.commit()
                    logger.warning(f"Permanent failure: {item.operation} [{item.idempotency_key[:8]}]: {e}")
        finally:
            db.close()

        if synced:
            logger.info(f"Sync complete: {synced} items synced")
        return synced

    async def _execute_item(self, item: SyncQueueEntry):
        """Execute a single sync queue item against the remote API."""
        try:
            resp = await self._remote_client._request(
                item.method,
                item.endpoint,
                json=item.payload,
            )
            item.last_http_status = resp.status_code

            if 200 <= resp.status_code < 300:
                return  # Success
            elif resp.status_code == 409:
                # Idempotent duplicate — treat as success
                logger.info(f"409 Conflict (idempotent duplicate): {item.operation}")
                return
            elif 400 <= resp.status_code < 500:
                raise PermanentError(f"HTTP {resp.status_code}: {resp.text[:200]}")
            else:
                raise RetryableError(f"HTTP {resp.status_code}: {resp.text[:200]}")
        except (RetryableError, PermanentError):
            raise
        except Exception as e:
            raise RetryableError(f"Network error: {e}")

    def _schedule_retry(self, item: SyncQueueEntry, error: str):
        """Apply exponential backoff and reschedule item."""
        item.retry_count += 1
        item.last_error = error

        if item.retry_count >= item.max_retries:
            item.status = "failed"
            logger.warning(f"Max retries reached: {item.operation} [{item.idempotency_key[:8]}]")
        else:
            backoff = min(2**item.retry_count * 10, MAX_BACKOFF_SECONDS)
            item.status = "pending"
            item.next_retry_at = datetime.utcnow() + timedelta(seconds=backoff)
            item.locked_at = None
            logger.info(
                f"Retry scheduled: {item.operation} [{item.idempotency_key[:8]}] "
                f"attempt {item.retry_count}/{item.max_retries} in {backoff}s"
            )

    def recover_stale_leases(self):
        """Reset in_progress items whose lease has expired (worker crash recovery).

        Called at startup per design Section 4.5.6 step 5.
        """
        db: Session = self._session_factory()
        try:
            cutoff = datetime.utcnow() - timedelta(seconds=LEASE_TIMEOUT_SECONDS)
            stale = (
                db.query(SyncQueueEntry)
                .filter(
                    SyncQueueEntry.status == "in_progress",
                    SyncQueueEntry.locked_at < cutoff,
                )
                .all()
            )
            for item in stale:
                item.status = "pending"
                item.locked_at = None
                logger.info(f"Recovered stale lease: {item.operation} [{item.idempotency_key[:8]}]")
            if stale:
                db.commit()
                logger.info(f"Recovered {len(stale)} stale sync items")
        finally:
            db.close()

    def get_queue_stats(self) -> dict:
        """Return sync queue statistics for heartbeat reporting."""
        db: Session = self._session_factory()
        try:
            from sqlalchemy import func as sa_func

            pending = db.query(sa_func.count(SyncQueueEntry.id)).filter(
                SyncQueueEntry.status.in_(["pending", "in_progress"])
            ).scalar() or 0
            failed = db.query(sa_func.count(SyncQueueEntry.id)).filter(
                SyncQueueEntry.status == "failed"
            ).scalar() or 0

            oldest = (
                db.query(SyncQueueEntry.created_at)
                .filter(SyncQueueEntry.status.in_(["pending", "in_progress"]))
                .order_by(SyncQueueEntry.created_at)
                .first()
            )
            oldest_age_sec = 0
            if oldest and oldest[0]:
                oldest_age_sec = int((datetime.utcnow() - oldest[0]).total_seconds())

            return {
                "pending": pending,
                "failed": failed,
                "queue_depth": pending + failed,
                "oldest_unsynced_age_sec": oldest_age_sec,
            }
        finally:
            db.close()
