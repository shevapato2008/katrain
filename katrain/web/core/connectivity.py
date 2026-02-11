"""Network connectivity manager for board mode.

See design.md Section 4.6 for the full specification.
Monitors remote server health, manages online/offline transitions,
and triggers sync on reconnection.
"""

import asyncio
import logging
from typing import Optional

from katrain.web.core.remote_client import RemoteAPIClient
from katrain.web.core.sync_worker import SyncWorker

logger = logging.getLogger("katrain_web")

# Thresholds (design.md Section 4.6)
HEALTH_CHECK_INTERVAL = 10  # seconds
RTT_THRESHOLD_MS = 5000  # 5s — above this counts as failure
FAILURES_TO_OFFLINE = 3  # consecutive failures before switching to offline
SUCCESSES_TO_ONLINE = 2  # consecutive successes before switching to online
IN_FLIGHT_TIMEOUT = 10  # seconds to wait for in-flight requests before switching offline


class ConnectivityManager:
    """Background task that monitors remote server health and manages online/offline state.

    Only active when KATRAIN_MODE=board.
    """

    def __init__(
        self,
        remote_client: RemoteAPIClient,
        sync_worker: Optional[SyncWorker] = None,
    ):
        self._remote_client = remote_client
        self._sync_worker = sync_worker
        self._is_online: bool = False
        self._consecutive_failures: int = 0
        self._consecutive_successes: int = 0
        self._task: Optional[asyncio.Task] = None
        self._on_status_change_callbacks = []

    @property
    def is_online(self) -> bool:
        return self._is_online

    def on_status_change(self, callback):
        """Register a callback for online/offline transitions.

        callback(is_online: bool) will be called on each transition.
        """
        self._on_status_change_callbacks.append(callback)

    def start(self):
        """Start the background health check loop."""
        if self._task is not None:
            return
        self._task = asyncio.create_task(self._health_loop())
        logger.info("ConnectivityManager started")

    async def stop(self):
        """Stop the background health check loop."""
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
            logger.info("ConnectivityManager stopped")

    async def _health_loop(self):
        """Periodically check remote server health."""
        while True:
            try:
                result = await self._remote_client.check_health()
                ok = result["ok"] and result["rtt_ms"] < RTT_THRESHOLD_MS

                if ok:
                    self._consecutive_successes += 1
                    self._consecutive_failures = 0
                else:
                    self._consecutive_failures += 1
                    self._consecutive_successes = 0

                await self._evaluate_state()

            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.debug(f"Health check error: {e}")
                self._consecutive_failures += 1
                self._consecutive_successes = 0
                await self._evaluate_state()

            await asyncio.sleep(HEALTH_CHECK_INTERVAL)

    async def _evaluate_state(self):
        """Evaluate whether to transition online/offline based on counters."""
        was_online = self._is_online

        if self._is_online and self._consecutive_failures >= FAILURES_TO_OFFLINE:
            # Online → Offline
            self._is_online = False
            logger.warning(
                f"Switching to OFFLINE (consecutive failures: {self._consecutive_failures})"
            )

        elif not self._is_online and self._consecutive_successes >= SUCCESSES_TO_ONLINE:
            # Offline → Online
            self._is_online = True
            logger.info(
                f"Switching to ONLINE (consecutive successes: {self._consecutive_successes})"
            )

            # Trigger sync on reconnection
            if self._sync_worker:
                asyncio.create_task(self._trigger_sync())

        if was_online != self._is_online:
            for cb in self._on_status_change_callbacks:
                try:
                    cb(self._is_online)
                except Exception as e:
                    logger.error(f"Status change callback error: {e}")

    async def _trigger_sync(self):
        """Trigger sync worker when coming back online."""
        try:
            synced = await self._sync_worker.run_sync()
            if synced:
                logger.info(f"Post-reconnection sync: {synced} items synced")
        except Exception as e:
            logger.error(f"Post-reconnection sync failed: {e}")

    async def force_check(self) -> bool:
        """Force an immediate health check. Returns current online status."""
        result = await self._remote_client.check_health()
        ok = result["ok"] and result["rtt_ms"] < RTT_THRESHOLD_MS
        if ok:
            self._consecutive_successes += 1
            self._consecutive_failures = 0
        else:
            self._consecutive_failures += 1
            self._consecutive_successes = 0
        await self._evaluate_state()
        return self._is_online
