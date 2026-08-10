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

#: Operations whose meaning depends on the order they are applied in, per user.
#: A rank is a state machine driven by its games: replaying game 3 before game 2
#: lands on a different rung, and skipping a stuck game 2 silently loses a result.
#: Everything else in the queue is order-independent (a kifu) or latest-wins (tsumego
#: progress), so one stuck item there must not stall the rest of the queue.
ORDERED_OPERATIONS = frozenset({"settle_ai_ladder_ranked"})

#: 4xx codes that mean "not now" rather than "not ever", so a revive should try them
#: again. 404 and 405 earn their place the hard way: a board can be running ahead of the
#: server it syncs to, and a route that does not exist yet is not a request the server
#: understood and rejected. Measured, not guessed -- a server whose SPA catch-all answers
#: unknown paths replies 405 to a POST, not 404 (observed against the production cloud on
#: 2026-08-05, before it had /api/v1/ai-ladder/settlements).
TRANSIENT_CLIENT_STATUSES = frozenset({404, 405, 408, 425, 429})


def _is_permanent_refusal(http_status) -> bool:
    if http_status is None:
        return False  # never got an answer -- that is the network, not a refusal
    return 400 <= http_status < 500 and http_status not in TRANSIENT_CLIENT_STATUSES


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
        ai_ladder_repo=None,
    ):
        self._session_factory = session_factory
        self._remote_client = remote_client
        # Present on a board: lets a synced settlement bring the cloud's answer back,
        # so an account that also played elsewhere stops showing two different ranks.
        self._ai_ladder_repo = ai_ladder_repo
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

            blocked_users: set = set()
            for item in items:
                if self._remote_client.auth_required:
                    logger.warning("Auth required — pausing sync queue")
                    break

                if item.operation in ORDERED_OPERATIONS:
                    if item.user_id in blocked_users:
                        # An earlier item for this user has not landed. Sending this one
                        # now would apply their games out of order.
                        continue
                    if not self._may_send_for(item):
                        blocked_users.add(item.user_id)
                        continue

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
                    if item.operation in ORDERED_OPERATIONS:
                        blocked_users.add(item.user_id)
                except PermanentError as e:
                    item.status = "failed"
                    item.last_error = str(e)
                    db.commit()
                    logger.warning(f"Permanent failure: {item.operation} [{item.idempotency_key[:8]}]: {e}")
                    if item.operation in ORDERED_OPERATIONS:
                        blocked_users.add(item.user_id)
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
                self._absorb_response(item, resp)
                return  # Success
            elif resp.status_code == 409:
                if item.operation == "settle_ai_ladder_ranked":
                    try:
                        body = resp.json()
                        lifecycle = body.get("lifecycle", body) if isinstance(body, dict) else None
                        if isinstance(lifecycle, dict) and lifecycle.get("state") == "settled" and isinstance(
                            lifecycle.get("receipt"), dict
                        ):
                            self._absorb_response(item, resp)
                            return
                    except Exception:
                        pass
                    raise PermanentError(f"HTTP 409 without settled receipt: {resp.text[:200]}")
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

    def _absorb_response(self, item: SyncQueueEntry, resp) -> None:
        """Take back what the server decided, where the server is the one who decides.

        For a rank, that is the whole point of syncing: the cloud re-ran the settlement
        against every device's games, so its profile supersedes the local one. A reply
        we cannot parse is not a reason to fail an item that the server accepted.
        """
        if item.operation != "settle_ai_ladder_ranked" or self._ai_ladder_repo is None:
            return
        try:
            body = resp.json()
            profile = body.get("profile") if isinstance(body, dict) else None
            if not profile or item.user_id is None:
                return
            if self._ai_ladder_repo.adopt_remote_profile(int(item.user_id), profile):
                logger.info(f"Adopted cloud AI ladder profile for user {item.user_id}")
        except Exception as e:
            logger.warning(f"Could not apply sync response for {item.operation}: {e}")

    def _may_send_for(self, item: SyncQueueEntry) -> bool:
        """Whether the remote session currently belongs to the item's owner.

        A board is a shared device: the remote client holds ONE cloud session, whoever
        logged in last. Posting a queued rank event under someone else's token would
        move the wrong person's rank, so an ownerless or mismatched session means wait,
        not send. Fail closed — an unbound session is not proof of anything.
        """
        bound = getattr(self._remote_client, "bound_user_id", None)
        if bound is None or item.user_id is None:
            logger.info(
                "Holding %s [%s]: no bound cloud session to attribute it to",
                item.operation,
                item.idempotency_key[:8],
            )
            return False
        if str(bound) != str(item.user_id):
            logger.info(
                "Holding %s [%s]: queued for user %s, cloud session is user %s",
                item.operation,
                item.idempotency_key[:8],
                item.user_id,
                bound,
            )
            return False
        return True

    def revive_retryable_failures(self) -> int:
        """Put network-failed items back in the queue. Called on reconnection.

        Retry budget exhaustion means "the network was bad for a while", not "this can
        never work" — but `failed` is terminal, so without this a settlement dropped
        during an outage stays dropped forever with nothing surfacing it. A 4xx is a
        different animal: the server understood and refused, so retrying it is noise.
        """
        db: Session = self._session_factory()
        try:
            revived = 0
            rows = db.query(SyncQueueEntry).filter(SyncQueueEntry.status == "failed").all()
            for item in rows:
                if _is_permanent_refusal(item.last_http_status):
                    continue  # the server refused it on the merits; retrying changes nothing
                item.status = "pending"
                item.retry_count = 0
                item.next_retry_at = None
                item.locked_at = None
                revived += 1
            if revived:
                db.commit()
                logger.info(f"Revived {revived} sync items after reconnection")
            return revived
        finally:
            db.close()

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

            pending = (
                db.query(sa_func.count(SyncQueueEntry.id))
                .filter(SyncQueueEntry.status.in_(["pending", "in_progress"]))
                .scalar()
                or 0
            )
            failed = db.query(sa_func.count(SyncQueueEntry.id)).filter(SyncQueueEntry.status == "failed").scalar() or 0

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
