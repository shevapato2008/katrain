"""APScheduler wrapper that registers and records all cron jobs."""

import asyncio
import logging
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from katrain.cron import config
from katrain.cron.db import SessionLocal
from katrain.cron.run_recorder import RunRecorder, install_error_capture

logger = logging.getLogger("katrain_cron.scheduler")


class CronScheduler:
    """Manages all scheduled jobs and persistent loop jobs (Analyze, ReportAnalyze)."""

    def __init__(self):
        self._scheduler = AsyncIOScheduler()
        self._analyze_task: asyncio.Task | None = None
        self._report_analyze_task: asyncio.Task | None = None
        self._heartbeat_task: asyncio.Task | None = None
        self._shutdown_event = asyncio.Event()
        self._recorder = RunRecorder(SessionLocal)
        self._loop_jobs: dict = {}

    async def start(self):
        """Register jobs, start scheduler, and run until shutdown."""
        from katrain.cron.jobs.fetch_list import FetchListJob
        from katrain.cron.jobs.poll_moves import PollMovesJob
        from katrain.cron.jobs.poll_pandanet import PandanetPollJob
        from katrain.cron.jobs.translate import TranslateJob
        from katrain.cron.jobs.analyze import AnalyzeJob
        from katrain.cron.jobs.fetch_upcoming import FetchUpcomingJob
        from katrain.cron.jobs.cleanup import CleanupJob
        from katrain.cron.jobs.tutorial_backup import TutorialBackupJob

        # Interval jobs
        interval_jobs = [
            (FetchListJob, config.FETCH_LIST_INTERVAL, config.FETCH_LIST_ENABLED),
            (PollMovesJob, config.POLL_MOVES_INTERVAL, config.POLL_MOVES_ENABLED),
            (PandanetPollJob, config.PANDANET_POLL_INTERVAL, config.PANDANET_ENABLED),
            (TranslateJob, config.TRANSLATE_INTERVAL, config.TRANSLATE_ENABLED),
            (FetchUpcomingJob, config.FETCH_UPCOMING_INTERVAL, config.FETCH_UPCOMING_ENABLED),
            (CleanupJob, config.CLEANUP_INTERVAL, config.CLEANUP_ENABLED),
            (TutorialBackupJob, config.TUTORIAL_BACKUP_INTERVAL, config.TUTORIAL_BACKUP_ENABLED),
        ]

        install_error_capture()
        registry = [(job_cls.name, "interval", interval, enabled) for job_cls, interval, enabled in interval_jobs]
        registry.extend(
            [
                ("analyze", "loop", None, config.ANALYZE_ENABLED),
                ("report_analyze", "loop", None, config.REPORT_ANALYZE_ENABLED),
            ]
        )
        registered = self._recorder.register(registry)
        for _ in range(12):
            if registered or self._shutdown_event.is_set():
                break
            logger.warning("cron status tables are unavailable; retrying registration in 5s")
            try:
                await asyncio.wait_for(self._shutdown_event.wait(), timeout=5)
            except asyncio.TimeoutError:
                pass
            if self._shutdown_event.is_set():
                return
            registered = self._recorder.ensure_registered()

        if self._shutdown_event.is_set():
            return

        self._scheduler.start()
        logger.info("Scheduler started")

        # The immediate first run also goes through APScheduler's max_instances limit.
        for job_cls, interval, enabled in interval_jobs:
            if not enabled:
                logger.info("Job %s is disabled, skipping", job_cls.name)
                continue
            self._schedule(job_cls(), interval)
            logger.info("Registered job %s (interval=%ds)", job_cls.name, interval)

        # AnalyzeJob runs as a persistent async loop, not via APScheduler interval
        if config.ANALYZE_ENABLED:
            analyze_job = AnalyzeJob()
            self._loop_jobs["analyze"] = analyze_job
            self._analyze_task = asyncio.create_task(self._run_analyze_loop(analyze_job))
            logger.info("AnalyzeJob persistent loop started")
        else:
            logger.info("AnalyzeJob is disabled, skipping")

        # ReportAnalyzerJob: persistent loop for user game report analysis
        if config.REPORT_ANALYZE_ENABLED:
            from katrain.cron.jobs.report_analyze import ReportAnalyzerJob

            report_job = ReportAnalyzerJob()
            self._loop_jobs["report_analyze"] = report_job
            self._report_analyze_task = asyncio.create_task(self._run_analyze_loop(report_job))
            logger.info("ReportAnalyzerJob persistent loop started (concurrency=%d)", config.REPORT_CONCURRENCY)
        else:
            logger.info("ReportAnalyzerJob is disabled, skipping")

        self._heartbeat_task = asyncio.create_task(
            self._recorder.heartbeat_forever(self._loop_jobs, config.HEARTBEAT_INTERVAL, self._shutdown_event)
        )

        await self._shutdown_event.wait()

    def _schedule(self, job, interval: int) -> None:
        self._scheduler.add_job(
            self._recorder.run,
            "interval",
            args=[job],
            seconds=interval,
            id=job.name,
            name=job.name,
            max_instances=1,
            misfire_grace_time=interval,
            next_run_time=datetime.now(timezone.utc),
        )

    async def _run_analyze_loop(self, job):
        """Run a persistent loop, recording unexpected exits before restart."""
        token = self._recorder.enter_loop(job.name)
        try:
            while not self._shutdown_event.is_set():
                self._recorder.loop_started(job.name)
                try:
                    await job.run()
                except asyncio.CancelledError:
                    logger.info("%s cancelled", job.name)
                    break
                except Exception as exc:
                    logger.exception("%s crashed, restarting in 10s", job.name)
                    self._recorder.record_loop_crash(job.name, exc)
                    await asyncio.sleep(10)
        finally:
            self._recorder.exit_loop(token)

    async def shutdown(self):
        """Graceful shutdown: stop scheduler, loops and heartbeat."""
        logger.info("Shutting down scheduler")
        self._shutdown_event.set()
        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)
        for task in [self._analyze_task, self._report_analyze_task, self._heartbeat_task]:
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        logger.info("Scheduler shut down")
