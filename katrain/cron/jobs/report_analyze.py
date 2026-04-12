"""ReportAnalyzerJob: persistent async loop for user game report analysis.

Migrated from katrain.web.report.analyzer.ReportAnalyzerService.
Uses the cron-side KataGo engine (port 8002) instead of the web gameplay engine.
"""

import asyncio
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any

from katrain.cron import config
from katrain.cron.clients.katago import KataGoClient
from katrain.cron.db import SessionLocal
from katrain.cron.jobs.base import BaseJob
from katrain.cron.models import ReportTaskDB, ReportTaskMoveDB, UserGameDB

logger = logging.getLogger("katrain_cron.report_analyze")

MAX_RETRIES = 3

# SGF parsing patterns
SGF_MOVE_RE = re.compile(r";([BW])\[([a-z]{0,2})\]", re.IGNORECASE)
SGF_SIZE_RE = re.compile(r"SZ\[(\d+)\]")
SGF_KOMI_RE = re.compile(r"KM\[([^\]]+)\]")
SGF_RULES_RE = re.compile(r"RU\[([^\]]+)\]", re.IGNORECASE)


def _sgf_to_gtp(sgf_coord: str, board_size: int) -> str:
    if not sgf_coord:
        return "pass"
    col_idx = ord(sgf_coord[0].lower()) - ord("a")
    row_idx = ord(sgf_coord[1].lower()) - ord("a")
    col_char = chr(ord("A") + col_idx + (1 if col_idx >= 8 else 0))
    display_row = board_size - row_idx
    return f"{col_char}{display_row}"


def _parse_sgf(sgf: str) -> tuple[int, float, str, list[tuple[str, str]]]:
    board_size = int(SGF_SIZE_RE.search(sgf or "")[1]) if SGF_SIZE_RE.search(sgf or "") else 19

    komi_match = SGF_KOMI_RE.search(sgf or "")
    try:
        komi = float(komi_match[1]) if komi_match else 7.5
    except ValueError:
        komi = 7.5

    rules_match = SGF_RULES_RE.search(sgf or "")
    rules = (rules_match[1].strip().lower() if rules_match else "chinese") or "chinese"

    moves: list[tuple[str, str]] = []
    for color, coord in SGF_MOVE_RE.findall(sgf or ""):
        gtp = _sgf_to_gtp(coord, board_size) if coord else "pass"
        moves.append((color.upper(), gtp))
    return board_size, komi, rules, moves


def _ownership_grid(raw: Any, board_size: int) -> list[list[float]] | None:
    if not isinstance(raw, list):
        return None
    grid: list[list[float]] = []
    for y in range(board_size):
        start = y * board_size
        grid.append([float(v) for v in raw[start : start + board_size]])
    return grid


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

    # ── Task management ──

    def _reset_stale_tasks(self):
        """Reset all running tasks back to pending on startup.

        A restart kills all workers, so any task still marked "running"
        was interrupted and must be re-queued.  The resume logic in
        _get_resume_move_number will skip already-analyzed moves.
        """
        with SessionLocal() as db:
            running_tasks = (
                db.query(ReportTaskDB)
                .filter(ReportTaskDB.status == "running")
                .all()
            )
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

            board_size, komi, rules, moves = _parse_sgf(game.sgf_content)
            requested_visits = task.requested_visits or 500
            resume_from = self._get_resume_move_number(db, task_id)
            task.status = "running"
            task.total_moves = len(moves)
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
                board_size=board_size,
                komi=komi,
                rules=rules,
                moves=moves,
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
        board_size: int,
        komi: float,
        rules: str,
        moves: list[tuple[str, str]],
        move_number: int,
        requested_visits: int,
    ) -> dict[str, Any] | None:
        played = [[color, coord] for color, coord in moves[:move_number]]

        # Per-move retry (3 attempts, 2s delay)
        last_exc = None
        for attempt in range(3):
            try:
                response = await self._katago.analyze(
                    request_id=f"report_{task_id}_{move_number}",
                    moves=played,
                    rules=rules,
                    komi=komi,
                    board_size=board_size,
                    max_visits=requested_visits,
                    analyze_turns=[len(played)],
                    include_ownership=True,
                    include_policy=False,
                    initial_stones=[],
                    initial_player="B",
                    priority=config.REPORT_ANALYSIS_PRIORITY,
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

        root_info = response.get("rootInfo", {})
        move_infos = response.get("moveInfos", [])
        ownership = _ownership_grid(response.get("ownership"), board_size)

        actual_move = moves[move_number - 1][1] if move_number > 0 else None
        actual_player = moves[move_number - 1][0] if move_number > 0 else None

        # Compute delta relative to previous move
        previous_score = None
        previous_winrate = None
        if move_number > 0:
            with SessionLocal() as db:
                prev = (
                    db.query(ReportTaskMoveDB)
                    .filter(
                        ReportTaskMoveDB.task_id == task_id,
                        ReportTaskMoveDB.move_number == move_number - 1,
                    )
                    .first()
                )
                if prev:
                    previous_score = prev.score_lead
                    previous_winrate = prev.winrate

        score_lead = root_info.get("scoreLead", 0.0)
        winrate = root_info.get("winrate", 0.5)

        delta_score = None
        delta_winrate = None
        if previous_score is not None and previous_winrate is not None and actual_player:
            if actual_player == "B":
                delta_score = score_lead - previous_score
                delta_winrate = winrate - previous_winrate
            else:
                delta_score = previous_score - score_lead
                delta_winrate = previous_winrate - winrate

        # Build top moves
        top_moves = []
        for mi in move_infos[:10]:
            top_moves.append(
                {
                    "move": mi.get("move"),
                    "visits": mi.get("visits"),
                    "winrate": mi.get("winrate"),
                    "score_lead": mi.get("scoreLead"),
                    "prior": mi.get("prior"),
                    "pv": mi.get("pv"),
                    "psv": mi.get("playSelectionValue", 0.0),
                }
            )

        return {
            "status": "success",
            "winrate": winrate,
            "score_lead": score_lead,
            "visits": max((m.get("visits", 0) for m in move_infos[:1]), default=0),
            "top_moves": top_moves,
            "ownership": ownership,
            "actual_move": actual_move,
            "actual_player": actual_player,
            "delta_score": delta_score,
            "delta_winrate": delta_winrate,
        }
