"""APScheduler wrapper that registers and runs all cron jobs."""

import asyncio
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from katrain.cron import config

logger = logging.getLogger("katrain_cron.scheduler")


class CronScheduler:
    """Manages all scheduled jobs and the persistent AnalyzeJob loop."""

    def __init__(self):
        self._scheduler = AsyncIOScheduler()
        self._analyze_task: asyncio.Task | None = None
        self._shutdown_event = asyncio.Event()

    async def start(self):
        """Register jobs, start scheduler, and run until shutdown."""
        from katrain.cron.jobs.fetch_list import FetchListJob
        from katrain.cron.jobs.poll_moves import PollMovesJob
        from katrain.cron.jobs.translate import TranslateJob
        from katrain.cron.jobs.analyze import AnalyzeJob

        # Interval jobs
        interval_jobs = [
            (FetchListJob, config.FETCH_LIST_INTERVAL, config.FETCH_LIST_ENABLED),
            (PollMovesJob, config.POLL_MOVES_INTERVAL, config.POLL_MOVES_ENABLED),
            (TranslateJob, config.TRANSLATE_INTERVAL, config.TRANSLATE_ENABLED),
        ]

        for job_cls, interval, enabled in interval_jobs:
            if not enabled:
                logger.info("Job %s is disabled, skipping", job_cls.name)
                continue
            job = job_cls()
            self._scheduler.add_job(
                job.run,
                "interval",
                seconds=interval,
                id=job.name,
                name=job.name,
                max_instances=1,
                misfire_grace_time=interval,
            )
            logger.info("Registered job %s (interval=%ds)", job.name, interval)

        self._scheduler.start()
        logger.info("Scheduler started")

        # AnalyzeJob runs as a persistent async loop, not via APScheduler interval
        if config.ANALYZE_ENABLED:
            analyze_job = AnalyzeJob()
            self._analyze_task = asyncio.create_task(self._run_analyze_loop(analyze_job))
            logger.info("AnalyzeJob persistent loop started")
        else:
            logger.info("AnalyzeJob is disabled, skipping")

        # Block until shutdown signal
        await self._shutdown_event.wait()

    async def _run_analyze_loop(self, job):
        """Run AnalyzeJob.run() continuously, restarting on unexpected errors."""
        while not self._shutdown_event.is_set():
            try:
                await job.run()
            except asyncio.CancelledError:
                logger.info("AnalyzeJob cancelled")
                break
            except Exception:
                logger.exception("AnalyzeJob crashed, restarting in 10s")
                await asyncio.sleep(10)

    async def shutdown(self):
        """Graceful shutdown: stop scheduler, cancel analyze loop."""
        logger.info("Shutting down scheduler")
        self._scheduler.shutdown(wait=False)
        if self._analyze_task and not self._analyze_task.done():
            self._analyze_task.cancel()
            try:
                await self._analyze_task
            except asyncio.CancelledError:
                pass
        self._shutdown_event.set()
        logger.info("Scheduler shut down")
