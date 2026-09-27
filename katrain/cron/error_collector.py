"""Cron's copy of `katrain/web/core/error_collector.py` (the cron image ships only `katrain/cron/`).

Error tracking: a logging handler that groups ERROR records by fingerprint into `error_groups`.

Guard rails for the hot path: `emit` only appends to a bounded in-memory queue (full → drop and
count); a daemon thread flushes every few seconds through its own one-connection engine with a
short statement timeout; nothing here ever raises into the caller. Records from this module's own
logger are ignored (no recursion). Samples are scrubbed (phones, e-mails, JWTs, bearer tokens,
key=/password= pairs) and capped. No request data, headers or locals are recorded.

The cron image cannot import this module; `katrain/cron/error_collector.py` is its copy and must
compute the same fingerprint (a test pins that).
"""

from __future__ import annotations

import collections
import hashlib
import logging
import os
import re
import threading
import traceback
from datetime import datetime, timedelta, timezone

LOGGER_NAME = "katrain_cron.error_collector"
log = logging.getLogger(LOGGER_NAME)
SAMPLE_LIMIT = 4096
TEMPLATE_LIMIT = 500
_SCRUB = [
    (re.compile(r"eyJ[\w-]+\.[\w-]+(?:\.[\w-]+)?"), "<jwt>"),
    (re.compile(r"(?i)bearer\s+\S+"), "Bearer <redacted>"),
    (re.compile(r"(?i)\b(key|password|passwd|secret|token|api_key|apikey)=\S+"), r"\1=<redacted>"),
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"), "<email>"),
    (re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)"), "<phone>"),
]


def scrub(text: str) -> str:
    for pattern, replacement in _SCRUB:
        text = pattern.sub(replacement, text)
    return text


def build_id() -> str:
    return (os.getenv("KATRAIN_BUILD_SHA") or "unknown").strip()[:64] or "unknown"


def location(record: logging.LogRecord) -> str:
    """The three innermost frames as file:function (no line numbers, so edits don't split groups)."""
    if record.exc_info and record.exc_info[2] is not None:
        frames = traceback.extract_tb(record.exc_info[2])[-3:]
        return " < ".join(f"{os.path.basename(f.filename)}:{f.name}" for f in reversed(frames))[:400]
    return f"{os.path.basename(record.pathname)}:{record.funcName}"[:400]


def fingerprint(process: str, record: logging.LogRecord) -> str:
    exc_type = record.exc_info[0].__name__ if record.exc_info and record.exc_info[0] else ""
    key = "|".join([process, record.name, exc_type, str(record.msg)[:TEMPLATE_LIMIT], location(record)])
    return hashlib.sha256(key.encode("utf-8", "replace")).hexdigest()[:40]


def dedicated_factory(database_url: str):
    """One connection, 2 s statement timeout: the collector must never compete with requests."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    kwargs: dict = {"pool_pre_ping": True}
    if database_url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
    else:
        kwargs.update(pool_size=1, max_overflow=0, connect_args={"options": "-c statement_timeout=2000"})
    return sessionmaker(bind=create_engine(database_url, **kwargs))


class ErrorCollector(logging.Handler):
    def __init__(self, session_factory, process="cron", *, max_queue=1000, flush_interval=5.0, max_groups=5000, retention_days=30):
        super().__init__(level=logging.ERROR)
        self.process, self.session_factory = process, session_factory
        self.max_queue, self.flush_interval = max_queue, flush_interval
        self.max_groups, self.retention = max_groups, timedelta(days=retention_days)
        self._queue: collections.deque = collections.deque()
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._last_prune: datetime | None = None
        self.dropped = self.overflow = 0
        self.last_flush_at: datetime | None = None
        self.last_flush_ok: bool | None = None

    def _job(self) -> str | None:
        from katrain.cron.run_recorder import current_job

        return current_job.get()

    def _event(self, record: logging.LogRecord) -> dict:
        try:
            message = record.getMessage()
        except Exception:  # a malformed log call is still an error worth keeping
            message = f"{record.msg} {record.args!r}"
        if record.exc_info and record.exc_info[1] is not None:
            tail = "".join(traceback.format_exception(*record.exc_info)[-12:])
            message = f"{message}\n{tail}"
        return {
            "fingerprint": fingerprint(self.process, record),
            "logger": record.name[:128],
            "exc_type": record.exc_info[0].__name__[:128] if record.exc_info and record.exc_info[0] else None,
            "template": str(record.msg)[:TEMPLATE_LIMIT],
            "location": location(record),
            "job": self._job(),
            "sample": scrub(message)[:SAMPLE_LIMIT],
            "at": datetime.fromtimestamp(record.created, timezone.utc),
        }

    def emit(self, record: logging.LogRecord) -> None:
        try:
            if record.name == LOGGER_NAME or record.name.startswith(LOGGER_NAME + "."):
                return
            with self._lock:
                if len(self._queue) >= self.max_queue:
                    self.dropped += 1
                    return
            event = self._event(record)
            with self._lock:
                self._queue.append(event)
        except Exception:  # a logging handler must never interrupt its caller
            pass

    def _drain(self) -> list[dict]:
        with self._lock:
            events = list(self._queue)
            self._queue.clear()
        return events

    def _model(self):
        from katrain.cron.models import ErrorGroupDB

        return ErrorGroupDB

    def flush(self) -> bool:
        events = self._drain()
        now = datetime.now(timezone.utc)
        if not events:
            self.last_flush_at, self.last_flush_ok = now, True
            return True
        merged: dict[str, dict] = {}
        for event in events:
            entry = merged.setdefault(event["fingerprint"], {**event, "n": 0, "first": event["at"]})
            entry.update(sample=event["sample"], at=event["at"], job=event["job"] or entry["job"])
            entry["n"] += 1
        Group = self._model()
        try:
            from sqlalchemy import func, select

            with self.session_factory() as db:
                total = db.scalar(select(func.count()).select_from(Group))
                for fp, entry in merged.items():
                    row = db.scalar(select(Group).where(Group.fingerprint == fp))
                    if row is not None:
                        row.count += entry["n"]
                        row.last_seen, row.sample, row.build = entry["at"], entry["sample"], build_id()
                        if row.resolved_at is not None:
                            row.resolved_at = row.resolved_by = None
                            row.state_changed_at = now
                        continue
                    if total >= self.max_groups:
                        self.overflow += entry["n"]
                        continue
                    total += 1
                    db.add(
                        Group(
                            fingerprint=fp, process=self.process, logger=entry["logger"], exc_type=entry["exc_type"],
                            template=entry["template"], location=entry["location"], job=entry["job"],
                            first_seen=entry["first"], last_seen=entry["at"], state_changed_at=now,
                            count=entry["n"], sample=entry["sample"], build=build_id(),
                        )
                    )
                db.commit()
            self.last_flush_ok = True
        except Exception as exc:
            self.dropped += len(events)
            self.last_flush_ok = False
            log.warning("error collector flush failed: %s", type(exc).__name__)
        self.last_flush_at = now
        self.prune()
        return bool(self.last_flush_ok)

    def prune(self, force: bool = False) -> None:
        now = datetime.now(timezone.utc)
        if not force and self._last_prune is not None and now - self._last_prune < timedelta(hours=1):
            return
        self._last_prune = now
        Group = self._model()
        try:
            from sqlalchemy import delete

            with self.session_factory() as db:
                db.execute(delete(Group).where(Group.last_seen < now - self.retention))
                db.commit()
        except Exception as exc:
            log.warning("error collector prune failed: %s", type(exc).__name__)

    def stats(self) -> dict:
        with self._lock:
            queued = len(self._queue)
        return {
            "collector": {
                "last_flush_at": self.last_flush_at.isoformat() if self.last_flush_at else None,
                "last_flush_ok": self.last_flush_ok,
                "dropped": self.dropped,
                "overflow": self.overflow,
                "queued": queued,
            }
        }

    def start(self, loggers=("",)) -> "ErrorCollector":
        for name in loggers:
            target = logging.getLogger(name)
            if self not in target.handlers:
                target.addHandler(self)
        self._thread = threading.Thread(target=self._run, name="error-collector", daemon=True)
        self._thread.start()
        return self

    def _run(self) -> None:
        while not self._stop.wait(self.flush_interval):
            self.flush()

    def stop(self) -> None:
        self._stop.set()
        logging.getLogger().removeHandler(self)
        self.flush()
