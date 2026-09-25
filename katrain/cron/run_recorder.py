"""Persist cron status and run history for the read-only admin console.

Recorder writes are best effort: a missing table or unavailable database must not
stop the jobs themselves. The web process creates the shared tables.
"""

import asyncio
import contextvars
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy import delete

from katrain.cron.models import CronJobRunDB, CronJobStatusDB

logger = logging.getLogger("katrain_cron.recorder")
ERROR_TEXT_LIMIT = 2000
RECORD_EVERY_RUN_MIN_INTERVAL = 60
PREVIOUS_PROCESS_EXITED = "cron 进程在这次运行结束前退出了（重启、部署或被杀）"


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class ErrorSink:
    count: int = 0
    first: str | None = None
    last: str | None = None
    last_at: datetime | None = None

    def add(self, message: str) -> None:
        message = message[:ERROR_TEXT_LIMIT]
        self.count += 1
        if self.first is None:
            self.first = message
        self.last = message
        self.last_at = utcnow()


_current_sink: contextvars.ContextVar[ErrorSink | None] = contextvars.ContextVar("cron_error_sink", default=None)


class ErrorCapture(logging.Handler):
    def __init__(self):
        super().__init__(level=logging.ERROR)

    def emit(self, record: logging.LogRecord) -> None:
        sink = _current_sink.get()
        if sink is None:
            return
        try:
            message = f"[{record.name}] {record.getMessage()}"
            if record.exc_info and record.exc_info[1] is not None:
                error = record.exc_info[1]
                message += f": {type(error).__name__}: {error}"
            sink.add(message)
        except Exception:  # A logging handler must not interrupt its caller.
            pass


def install_error_capture() -> None:
    root = logging.getLogger()
    if not any(isinstance(handler, ErrorCapture) for handler in root.handlers):
        root.addHandler(ErrorCapture())


@dataclass
class _LoopState:
    sink: ErrorSink = field(default_factory=ErrorSink)
    last_crash_at: datetime | None = None


class RunRecorder:
    def __init__(self, session_factory, clock=utcnow):
        self._session_factory = session_factory
        self._clock = clock
        self._registry: list[tuple[str, str, int | None, bool]] = []
        self._intervals: dict[str, int | None] = {}
        self._process_started_at: datetime | None = None
        self._registered = False
        self._loops: dict[str, _LoopState] = {}

    def register(self, jobs: list[tuple[str, str, int | None, bool]]) -> bool:
        self._registry = list(jobs)
        self._intervals = {name: interval for name, _kind, interval, _enabled in jobs}
        self._process_started_at = self._clock()
        self._registered = False
        return self.ensure_registered()

    def ensure_registered(self) -> bool:
        if not self._registered and self._registry:
            self._registered = self._write(self._register_rows, self._process_started_at) is True
        return self._registered

    def _register_rows(self, db, started):
        now = self._clock()
        names = [job[0] for job in self._registry]
        db.execute(delete(CronJobStatusDB).where(CronJobStatusDB.job_name.notin_(names)))
        stale = db.query(CronJobRunDB).filter(CronJobRunDB.status == "running", CronJobRunDB.started_at < started)
        latest_stale = {}
        for run in stale:
            run.status, run.finished_at, run.error = "failed", now, PREVIOUS_PROCESS_EXITED
            run.error_count = max(run.error_count or 0, 1)
            if run.job_name not in latest_stale or run.started_at > latest_stale[run.job_name]:
                latest_stale[run.job_name] = run.started_at
        for name, kind, interval, enabled in self._registry:
            row = db.get(CronJobStatusDB, name)
            if row is None:
                row = CronJobStatusDB(job_name=name, consecutive_failures=0)
                db.add(row)
            stale_started = latest_stale.get(name)
            if stale_started is not None:
                last_started = row.last_started_at
                if last_started is None or last_started.replace(tzinfo=timezone.utc) <= stale_started.replace(
                    tzinfo=timezone.utc
                ):
                    row.last_started_at = stale_started
                    row.last_finished_at = now
                    row.last_status = "failed"
                    row.last_error = PREVIOUS_PROCESS_EXITED
                    row.consecutive_failures = (row.consecutive_failures or 0) + 1
            row.kind, row.interval_seconds, row.enabled = kind, interval, enabled
            row.process_started_at = started
            row.heartbeat_at = row.updated_at = now
        return True

    async def run(self, job) -> None:
        name = job.name
        keep = (self._intervals.get(name) or 0) >= RECORD_EVERY_RUN_MIN_INTERVAL
        started = self._clock()
        monotonic_start = time.monotonic()
        run_id = self._write(self._start_rows, name, started, keep)
        sink = ErrorSink()
        token = _current_sink.set(sink)
        error: Exception | None = None
        cancelled = False
        try:
            await job.run()
        except asyncio.CancelledError:
            cancelled = True
            raise
        except Exception as exc:
            error = exc
            raise
        finally:
            _current_sink.reset(token)
            if not cancelled:
                result = "failed" if error is not None else ("errors" if sink.count else "success")
                detail = f"{type(error).__name__}: {error}"[:ERROR_TEXT_LIMIT] if error is not None else sink.first
                duration_ms = int((time.monotonic() - monotonic_start) * 1000)
                self._write(self._finish_rows, name, run_id, started, result, detail, sink.count, duration_ms, keep)

    def _start_rows(self, db, name, started, keep):
        row = db.get(CronJobStatusDB, name)
        if row is not None:
            row.last_started_at, row.last_status, row.updated_at = started, "running", started
        if not keep:
            return None
        run = CronJobRunDB(job_name=name, started_at=started, status="running", error_count=0)
        db.add(run)
        db.flush()
        return run.id

    def _finish_rows(self, db, name, run_id, started, result, detail, error_count, duration_ms, keep):
        now = self._clock()
        row = db.get(CronJobStatusDB, name)
        if row is not None:
            row.last_finished_at, row.last_status = now, result
            row.last_duration_ms, row.updated_at = duration_ms, now
            if result == "success":
                row.last_success_at, row.consecutive_failures = now, 0
            else:
                row.last_error = detail
                row.consecutive_failures = (row.consecutive_failures or 0) + 1
        run = db.get(CronJobRunDB, run_id) if run_id is not None else None
        if run is not None:
            run.finished_at, run.status, run.duration_ms = now, result, duration_ms
            run.error_count, run.error = error_count, detail
        elif not keep and result != "success":
            db.add(
                CronJobRunDB(
                    job_name=name,
                    started_at=started,
                    finished_at=now,
                    status=result,
                    duration_ms=duration_ms,
                    error_count=error_count,
                    error=detail,
                )
            )

    def enter_loop(self, name: str) -> contextvars.Token:
        return _current_sink.set(self._loops.setdefault(name, _LoopState()).sink)

    def exit_loop(self, token: contextvars.Token) -> None:
        _current_sink.reset(token)

    def loop_started(self, name: str) -> None:
        self._write(self._loop_started_rows, name, self._clock())

    def _loop_started_rows(self, db, name, now):
        row = db.get(CronJobStatusDB, name)
        if row is not None:
            row.last_started_at, row.last_status, row.updated_at = now, "running", now

    def record_loop_crash(self, name: str, error: BaseException) -> None:
        now = self._clock()
        self._loops.setdefault(name, _LoopState()).last_crash_at = now
        detail = f"{type(error).__name__}: {error}"[:ERROR_TEXT_LIMIT]
        self._write(self._loop_crash_rows, name, now, detail)

    def _loop_crash_rows(self, db, name, now, detail):
        row = db.get(CronJobStatusDB, name)
        if row is not None:
            row.last_status, row.last_error, row.updated_at = "failed", detail, now
            row.consecutive_failures = (row.consecutive_failures or 0) + 1
        db.add(
            CronJobRunDB(job_name=name, started_at=now, finished_at=now, status="failed", error_count=1, error=detail)
        )

    def heartbeat(self, loop_jobs: dict) -> None:
        self.ensure_registered()
        snapshot = {}
        for name, job in loop_jobs.items():
            state = self._loops.setdefault(name, _LoopState())
            stats = dict(job.heartbeat_stats())
            stats["errors_total"] = state.sink.count
            stats["last_error_at"] = state.sink.last_at.isoformat() if state.sink.last_at else None
            snapshot[name] = (getattr(job, "last_iteration_at", None), stats, state.sink.last, state.last_crash_at)
        self._write(self._heartbeat_rows, self._clock(), snapshot)

    def _heartbeat_rows(self, db, now, snapshot):
        for row in db.query(CronJobStatusDB).filter(CronJobStatusDB.job_name.in_(list(self._intervals))):
            row.heartbeat_at = row.updated_at = now
            if row.job_name not in snapshot:
                continue
            iteration_at, stats, last_error, last_crash_at = snapshot[row.job_name]
            row.loop_iteration_at, row.loop_stats = iteration_at, stats
            if last_error:
                row.last_error = last_error
            if iteration_at is not None and (last_crash_at is None or iteration_at > last_crash_at):
                row.consecutive_failures = 0

    async def heartbeat_forever(self, loop_jobs: dict, interval: float, stop: asyncio.Event) -> None:
        while not stop.is_set():
            self.heartbeat(loop_jobs)
            try:
                await asyncio.wait_for(stop.wait(), timeout=interval)
            except asyncio.TimeoutError:
                pass

    def _write(self, operation, *args):
        try:
            with self._session_factory() as db:
                result = operation(db, *args)
                db.commit()
                return result
        except Exception:
            logger.warning("cron run recorder write failed (%s)", operation.__name__, exc_info=True)
            return None
