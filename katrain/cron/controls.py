"""Admin controls for cron: pause state and run-now commands, polled every POLL_S seconds.

Pause only applies to interval jobs (loop jobs run continuously). A paused job's scheduled runs
are skipped by the recorder and recorded as `paused`. Run-now moves the APScheduler job's next run
to now, so it still goes through the recorder and `max_instances=1`. Every command is answered:
`done`, or `rejected` with a note — never silently dropped.
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import update

from katrain.cron.models import CronJobCommandDB, CronJobControlDB

POLL_S = 10
COMMAND_TTL = timedelta(minutes=10)
logger = logging.getLogger("katrain_cron.controls")


class ControlPoller:
    def __init__(self, session_factory, recorder, scheduler):
        self.session_factory, self.recorder, self.scheduler = session_factory, recorder, scheduler
        self.started_at = datetime.now(timezone.utc)

    def poll(self, commands: bool = True) -> bool:
        try:
            with self.session_factory() as db:
                paused = {row.job_name: row.reason for row in db.query(CronJobControlDB).filter(CronJobControlDB.paused.is_(True))}
                self.recorder.paused = paused
                if not commands:
                    return True
                now = datetime.now(timezone.utc)
                for command in db.query(CronJobCommandDB).filter(CronJobCommandDB.state == "pending").order_by(CronJobCommandDB.id):
                    requested = command.requested_at if command.requested_at.tzinfo else command.requested_at.replace(tzinfo=timezone.utc)
                    job = self.scheduler.get_job(command.job_name)
                    if command.command != "run_now":
                        state, note = "rejected", "未知命令"
                    elif requested < self.started_at or now - requested > COMMAND_TTL:
                        state, note = "rejected", "已过期：cron 当时没在线领取，没有补跑"
                    elif job is None:
                        state, note = "rejected", "该任务没有在本 cron 进程里调度（可能被配置停用或是常驻循环）"
                    elif command.job_name in paused:
                        state, note = "rejected", "任务已暂停，先恢复再运行"
                    elif command.job_name in self.recorder.running:
                        state, note = "rejected", "任务正在运行，这次没有再排一次"
                    else:
                        state, note = "done", "已交给调度器立即运行"
                    # Claim the command atomically so a second cron process cannot act on it too.
                    claimed = db.execute(
                        update(CronJobCommandDB)
                        .where(CronJobCommandDB.id == command.id, CronJobCommandDB.state == "pending")
                        .values(state=state, note=note, handled_at=now)
                    )
                    if claimed.rowcount == 1 and state == "done":
                        job.modify(next_run_time=now)
                db.commit()
            return True
        except Exception as exc:  # tables may not exist yet (web not upgraded); keep cron running
            logger.warning("cron controls poll failed: %s", type(exc).__name__)
            return False

    async def poll_forever(self, shutdown: asyncio.Event) -> None:
        while not shutdown.is_set():
            await asyncio.to_thread(self.poll)
            try:
                await asyncio.wait_for(shutdown.wait(), timeout=POLL_S)
            except asyncio.TimeoutError:
                pass
