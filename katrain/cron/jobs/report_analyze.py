"""ReportAnalyzerJob: persistent async loop for user game report analysis.

Migrated from katrain.web.report.analyzer.ReportAnalyzerService.
Uses the cron-side KataGo engine (port 8002) instead of the web gameplay engine.
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from katrain.cron import config
from katrain.cron.clients.katago import KataGoClient
from katrain.cron.db import SessionLocal
from katrain.cron.jobs.base import BaseJob
from katrain.cron.models import ReportTaskDB, ReportTaskMoveDB, UserGameDB
from katrain.cron.sgf import ParsedGame, parse_game
from katrain.cron.report_position import position_snapshot

logger = logging.getLogger("katrain_cron.report_analyze")

MAX_RETRIES = 3


class ReportAnalyzerJob(BaseJob):
    """Persistent async loop that processes pending report tasks.

    Maintains up to ``max_concurrent_tasks`` workers, each processing one
    report task move-by-move via cron's KataGo engine (port 8002).
    """

    name = "report_analyze"
    interval_seconds = 0  # Persistent loop, not interval-driven

    def __init__(self):
        super().__init__()
        self._running = True
        self._katago = KataGoClient()
        self._workers: set[asyncio.Task] = set()
        self.max_concurrent_tasks = max(1, config.REPORT_CONCURRENCY)
        self.poll_interval = config.REPORT_POLL_INTERVAL
        self.last_iteration_at: datetime | None = None

    async def run(self) -> None:
        self._running = True

        # Startup health check: warn early if KataGo is unreachable
        healthy = await self._katago.health_check()
        if not healthy:
            logger.error("KataGo at %s is not reachable — report analysis will fail", config.KATAGO_URL)

        # Crash recovery: reset stale running tasks
        self._reset_stale_tasks()

        stale_check_counter = 0

        while self._running:
            self.last_iteration_at = datetime.now(timezone.utc)
            try:
                self._prune_finished_workers()
                stale_check_counter += 1
                if stale_check_counter >= 60:  # ~every 60 poll cycles
                    self._reset_runtime_stale_tasks()
                    stale_check_counter = 0
                while self._running and len(self._workers) < self.max_concurrent_tasks:
                    claimed_task_id = self._claim_pending_task()
                    if not claimed_task_id:
                        break
                    worker = asyncio.create_task(self._process_task(claimed_task_id))
                    self._workers.add(worker)
                await asyncio.sleep(self.poll_interval)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Unhandled report analysis loop error")
                await asyncio.sleep(self.poll_interval)

    def stop(self):
        self._running = False

    def heartbeat_stats(self) -> dict:
        return {"in_flight": len(self._workers), "capacity": self.max_concurrent_tasks}

    # ── Task management ──

    def _reset_stale_tasks(self):
        """Reset all running tasks back to pending on startup.

        A restart kills all workers, so any task still marked "running"
        was interrupted and must be re-queued.  The resume logic in
        _get_resume_move_number will skip already-analyzed moves.
        """
        with SessionLocal() as db:
            running_tasks = db.query(ReportTaskDB).filter(ReportTaskDB.status == "running").all()
            if not running_tasks:
                return
            for task in running_tasks:
                task.status = "pending"
                task.error_message = None
            db.commit()
            logger.info("Reset %d interrupted report tasks to pending", len(running_tasks))

    def _reset_runtime_stale_tasks(self):
        """Reset tasks stuck in running for more than 30 minutes.

        Catches cases where a worker died silently without updating the DB.
        The task will be re-queued and resume from the last analyzed move.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=30)
        with SessionLocal() as db:
            stale_tasks = (
                db.query(ReportTaskDB)
                .filter(
                    ReportTaskDB.status == "running",
                    ReportTaskDB.updated_at < cutoff,
                )
                .all()
            )
            if not stale_tasks:
                return
            for task in stale_tasks:
                task.status = "pending"
                task.error_message = "Reset: stale running task"
            db.commit()
            logger.info("Reset %d stale running report tasks to pending", len(stale_tasks))

    def _prune_finished_workers(self) -> None:
        done = {w for w in self._workers if w.done()}
        for w in done:
            try:
                w.result()
            except asyncio.CancelledError:
                pass
            except Exception:
                logger.exception("Unhandled report worker error")
        self._workers.difference_update(done)

    def _claim_pending_task(self) -> int | None:
        with SessionLocal() as db:
            task = (
                db.query(ReportTaskDB)
                .filter(ReportTaskDB.status == "pending")
                .order_by(ReportTaskDB.created_at.asc(), ReportTaskDB.id.asc())
                .first()
            )
            if not task:
                return None
            task.status = "running"
            task.started_at = task.started_at or datetime.now(timezone.utc)
            task.completed_at = None
            task.error_message = None
            db.commit()
            logger.info("Claimed report task %d (type=%s, visits=%d)", task.id, task.report_type, task.requested_visits)
            return task.id

    def _get_resume_move_number(self, db, task_id: int) -> int:
        latest = (
            db.query(ReportTaskMoveDB)
            .filter(ReportTaskMoveDB.task_id == task_id)
            .order_by(ReportTaskMoveDB.move_number.desc(), ReportTaskMoveDB.id.desc())
            .first()
        )
        if not latest:
            return 0
        return latest.move_number + 1

    def _mark_task_for_retry_or_failure(self, task: ReportTaskDB, message: str) -> None:
        task.retry_count = (task.retry_count or 0) + 1
        task.error_message = message
        task.completed_at = None
        task.status = "pending" if task.retry_count < MAX_RETRIES else "failed"

    # ── Task processing ──

    async def _process_task(self, task_id: int):
        with SessionLocal() as db:
            task = db.query(ReportTaskDB).filter(ReportTaskDB.id == task_id).first()
            if not task:
                return
            game = db.query(UserGameDB).filter(UserGameDB.id == task.user_game_id).first()
            if not game or not game.sgf_content:
                task.status = "failed"
                task.error_message = "Game or SGF content not found"
                db.commit()
                return

            # 授权时冻结的指纹对不上 ⇒ 棋谱在排队期间被改过。
            # 继续跑会拼出「旧棋谱前缀 + 新棋谱后缀」的报告，且用户付的是旧棋谱的钱。
            if task.sgf_hash:
                import hashlib

                if hashlib.sha256(game.sgf_content.encode("utf-8")).hexdigest() != task.sgf_hash:
                    task.status = "failed"
                    task.error_message = "棋谱在排队期间被修改，请重新发起复盘"
                    db.commit()
                    return

            parsed = parse_game(game.sgf_content)
            if parsed.dropped_midgame_setup or parsed.invalid_moves:
                task.status = "failed"
                task.error_message = "棋谱包含分析引擎无法忠实还原的中途摆子或无效着手"
                db.commit()
                return
            moves = parsed.moves
            requested_visits = task.requested_visits or 500
            resume_from = self._get_resume_move_number(db, task_id)
            expected_sha = config.KATAGO_EXPECTED_MODEL_SHA256
            if expected_sha and (task.model_sha256 not in (None, expected_sha) or (resume_from and not task.model_sha256)):
                task.status = "failed"
                task.error_message = "已有棋谱报告使用旧版或未知模型，不能混合续跑；请联系管理员处理"
                db.commit()
                return
            task.status = "running"
            # total_moves 由 web 在建任务时解析并写死（那是计价的操作数）。
            # 这里只在它缺失时兜底 —— 覆盖它会让「已付费的手数」与「实际分析的手数」
            # 脱钩，客户端就能靠少报手数白嫖算力。
            if not task.total_moves:
                task.total_moves = len(moves)
            paid_moves = task.total_moves
            moves = moves[:paid_moves]
            task.analyzed_moves = min(task.analyzed_moves or 0, len(moves))
            task.started_at = task.started_at or datetime.now(timezone.utc)
            task.completed_at = None
            task.error_message = None
            db.commit()

        if resume_from > 0:
            logger.info("Resuming task %d from move %d/%d", task_id, resume_from, len(moves))

        for move_number in range(resume_from, len(moves) + 1):
            if not self._running:
                return

            result = await self._analyze_position(
                task_id=task_id,
                parsed=parsed,
                move_number=move_number,
                requested_visits=requested_visits,
            )
            with SessionLocal() as db:
                task = db.query(ReportTaskDB).filter(ReportTaskDB.id == task_id).first()
                if not task:
                    return
                if result is None:
                    self._mark_task_for_retry_or_failure(task, f"Analysis failed at move {move_number}")
                    db.commit()
                    return

                if expected_sha:
                    if task.model_sha256 not in (None, expected_sha):
                        task.status = "failed"
                        task.error_message = "报告模型在分析过程中发生变化"
                        db.commit()
                        return
                    task.model_sha256 = expected_sha

                record = (
                    db.query(ReportTaskMoveDB)
                    .filter(
                        ReportTaskMoveDB.task_id == task_id,
                        ReportTaskMoveDB.move_number == move_number,
                    )
                    .first()
                )
                if not record:
                    record = ReportTaskMoveDB(task_id=task_id, move_number=move_number)
                    db.add(record)

                for key, value in result.items():
                    if hasattr(record, key):
                        setattr(record, key, value)

                task.analyzed_moves = max(task.analyzed_moves, move_number)
                db.commit()

        with SessionLocal() as db:
            task = db.query(ReportTaskDB).filter(ReportTaskDB.id == task_id).first()
            if task:
                task.status = "completed"
                task.retry_count = 0
                task.analyzed_moves = len(moves)
                task.completed_at = datetime.now(timezone.utc)
                task.error_message = None
                db.commit()
                logger.info("Report task %d completed (%d moves)", task_id, len(moves))

    # ── KataGo analysis ──

    async def _analyze_position(
        self,
        task_id: int,
        parsed: ParsedGame,
        move_number: int,
        requested_visits: int,
    ) -> dict[str, Any] | None:
        board_size = parsed.board_size
        moves = parsed.moves
        played = [[color, coord] for color, coord in moves[:move_number]]

        # 人类倾向：给每个候选点带上「该档人类会下这一点的概率」。
        # 只要 moveInfos[].humanPrior，**不需要 includePolicy**（那是全盘 humanPolicy 数组的开关，
        # 2026-08-31 本机 KataGo v1.18.0 实跑对照过：不带 includePolicy 时 humanPrior 照常返回）。
        # 引擎没加载人类模型时设了 profile 会让整条 query 失败，所以用配置一键可关。
        extra_override: dict[str, Any] = {}
        if config.HUMAN_SL_PROFILE:
            extra_override["humanSLProfile"] = config.HUMAN_SL_PROFILE
            extra_override["rootNumSymmetriesToSample"] = config.HUMAN_SL_SYMMETRIES

        # Per-move retry (3 attempts, 2s delay)
        last_exc = None
        for attempt in range(3):
            try:
                response = await self._katago.analyze(
                    request_id=f"report_{task_id}_{move_number}",
                    moves=played,
                    rules=parsed.rules,
                    komi=parsed.komi,
                    board_size=board_size,
                    max_visits=requested_visits,
                    analyze_turns=[len(played)],
                    include_ownership=True,
                    include_policy=False,
                    initial_stones=parsed.initial_stones,
                    initial_player=parsed.initial_player,
                    priority=config.REPORT_ANALYSIS_PRIORITY,
                    extra_override=extra_override or None,
                )
                break
            except Exception as exc:
                last_exc = exc
                if attempt < 2:
                    logger.info("Report analysis retry %d for task %s move %s", attempt + 1, task_id, move_number)
                    await asyncio.sleep(2)
        else:
            logger.warning("Report analysis failed for task %s move %s: %s", task_id, move_number, last_exc)
            return None

        # :8002 的包装器用 **HTTP 200 + {"error": ...}** 表达拒绝（2026-08-31 实测：
        # 非法 profile 回的是 200，body 里 error/field 两个键），所以 raise_for_status()
        # 放行。不在这里拦一道的话，rootInfo 缺失会被 .get 兜成 {} ⇒ 落库 winrate=0.5、
        # score_lead=0、top_moves=[]，而任务照样被标 completed —— 用户拿到一份「生成成功」
        # 的报告：整局笔直 50%、零条 AI 推荐、全部未评级，日志里一个字都没有。
        # 返 None 会走已有的重试/标失败路径，那是界面上可见、用户能自助重试的失败。
        if isinstance(response, dict) and response.get("error"):
            logger.error(
                "KataGo rejected query for task %s move %s: %s (field=%s)",
                task_id,
                move_number,
                response.get("error"),
                response.get("field"),
            )
            return None

        previous = None
        if move_number > 0:
            with SessionLocal() as db:
                previous = (
                    db.query(ReportTaskMoveDB)
                    .filter(ReportTaskMoveDB.task_id == task_id, ReportTaskMoveDB.move_number == move_number - 1)
                    .first()
                )
                return position_snapshot(response, parsed, move_number, previous, config.HUMAN_SL_PROFILE or None)
        return position_snapshot(response, parsed, move_number, previous, config.HUMAN_SL_PROFILE or None)
