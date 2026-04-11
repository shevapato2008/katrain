import asyncio
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session

from katrain.web.core import models_db
from katrain.web.core.router import RequestRouter

logger = logging.getLogger("katrain_web.report")
MAX_RETRIES = 3

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
        grid.append([float(v) for v in raw[start:start + board_size]])
    return grid


class ReportAnalyzerService:
    def __init__(
        self,
        session_factory,
        router: RequestRouter,
        poll_interval: float = 2.0,
        max_concurrent_tasks: int = 3,
    ):
        self.session_factory = session_factory
        self.router = router
        self.poll_interval = poll_interval
        self.max_concurrent_tasks = max(1, max_concurrent_tasks)
        self._running = False
        self._task: asyncio.Task | None = None
        self._workers: set[asyncio.Task] = set()

    def start(self):
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._analysis_loop())
        logger.info("ReportAnalyzerService started")

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        for worker in list(self._workers):
            worker.cancel()
        if self._workers:
            await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers.clear()
        logger.info("ReportAnalyzerService stopped")

    async def _analysis_loop(self):
        while self._running:
            try:
                self._prune_finished_workers()
                self._reset_stale_tasks()
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

    def _reset_stale_tasks(self):
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=5)
        with self.session_factory() as db:
            stale_tasks = (
                db.query(models_db.ReportTask)
                .filter(
                    models_db.ReportTask.status == "running",
                    models_db.ReportTask.updated_at.is_not(None),
                    models_db.ReportTask.updated_at < cutoff,
                )
                .all()
            )
            if not stale_tasks:
                return
            for task in stale_tasks:
                task.status = "pending"
                task.error_message = "Recovered stale running task"
            db.commit()

    def _prune_finished_workers(self) -> None:
        done = {worker for worker in self._workers if worker.done()}
        for worker in done:
            try:
                worker.result()
            except asyncio.CancelledError:
                pass
            except Exception:
                logger.exception("Unhandled report worker error")
        self._workers.difference_update(done)

    def _claim_pending_task(self) -> int | None:
        with self.session_factory() as db:
            task = (
                db.query(models_db.ReportTask)
                .filter(models_db.ReportTask.status == "pending")
                .order_by(models_db.ReportTask.created_at.asc(), models_db.ReportTask.id.asc())
                .first()
            )
            if not task:
                return None
            task.status = "running"
            task.started_at = task.started_at or datetime.now(timezone.utc)
            task.completed_at = None
            task.error_message = None
            db.commit()
            return task.id

    def _get_resume_move_number(self, db: Session, task_id: int) -> int:
        latest = (
            db.query(models_db.ReportTaskMove)
            .filter(models_db.ReportTaskMove.task_id == task_id)
            .order_by(models_db.ReportTaskMove.move_number.desc(), models_db.ReportTaskMove.id.desc())
            .first()
        )
        if not latest:
            return 0
        return latest.move_number + 1

    def _mark_task_for_retry_or_failure(self, task: models_db.ReportTask, message: str) -> None:
        task.retry_count = (task.retry_count or 0) + 1
        task.error_message = message
        task.completed_at = None
        task.status = "pending" if task.retry_count < MAX_RETRIES else "failed"

    def _build_top_moves(self, move_infos: list[dict[str, Any]]) -> list[dict[str, Any]]:
        top_moves = []
        for move_info in move_infos[:10]:
            top_moves.append(
                {
                    "move": move_info.get("move"),
                    "visits": move_info.get("visits"),
                    "winrate": move_info.get("winrate"),
                    "score_lead": move_info.get("scoreLead"),
                    "prior": move_info.get("prior"),
                    "pv": move_info.get("pv"),
                    "psv": move_info.get("playSelectionValue", 0.0),
                }
            )
        return top_moves

    async def _process_task(self, task_id: int):
        with self.session_factory() as db:
            task = db.query(models_db.ReportTask).filter(models_db.ReportTask.id == task_id).first()
            if not task:
                return
            game = db.query(models_db.UserGame).filter(models_db.UserGame.id == task.user_game_id).first()
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
            with self.session_factory() as db:
                task = db.query(models_db.ReportTask).filter(models_db.ReportTask.id == task_id).first()
                if not task:
                    return
                if result is None:
                    self._mark_task_for_retry_or_failure(task, f"Analysis failed at move {move_number}")
                    db.commit()
                    return

                record = (
                    db.query(models_db.ReportTaskMove)
                    .filter(
                        models_db.ReportTaskMove.task_id == task_id,
                        models_db.ReportTaskMove.move_number == move_number,
                    )
                    .first()
                )
                if not record:
                    record = models_db.ReportTaskMove(task_id=task_id, move_number=move_number)
                    db.add(record)

                for key, value in result.items():
                    if hasattr(record, key):
                        setattr(record, key, value)

                task.analyzed_moves = max(task.analyzed_moves, move_number)
                db.commit()

        with self.session_factory() as db:
            task = db.query(models_db.ReportTask).filter(models_db.ReportTask.id == task_id).first()
            if task:
                task.status = "completed"
                task.retry_count = 0
                task.analyzed_moves = len(moves)
                task.completed_at = datetime.now(timezone.utc)
                task.error_message = None
                db.commit()

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
        payload = {
            "id": f"report_{task_id}_{move_number}",
            "rules": rules,
            "komi": komi,
            "boardXSize": board_size,
            "boardYSize": board_size,
            "analyzeTurns": [len(played)],
            "maxVisits": requested_visits,
            "initialStones": [],
            "initialPlayer": "B",
            "moves": played,
            "includeOwnership": True,
            "includePolicy": False,
            "overrideSettings": {"reportAnalysisWinratesAs": "BLACK"},
        }

        last_exc = None
        for attempt in range(3):
            try:
                response = await self.router.route(payload)
                break
            except Exception as exc:
                last_exc = exc
                if attempt < 2:
                    logger.info("Report analysis retry %d for task %s move %s", attempt + 1, task_id, move_number)
                    await asyncio.sleep(2)
        else:
            logger.warning("Report analysis request failed for task %s move %s: %s", task_id, move_number, last_exc)
            return None

        root_info = response.get("rootInfo", {})
        move_infos = response.get("moveInfos", [])
        ownership = _ownership_grid(response.get("ownership"), board_size)

        actual_move = moves[move_number - 1][1] if move_number > 0 else None
        actual_player = moves[move_number - 1][0] if move_number > 0 else None

        previous_score = None
        previous_winrate = None
        if move_number > 0:
            with self.session_factory() as db:
                prev = (
                    db.query(models_db.ReportTaskMove)
                    .filter(
                        models_db.ReportTaskMove.task_id == task_id,
                        models_db.ReportTaskMove.move_number == move_number - 1,
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

        return {
            "status": "success",
            "winrate": winrate,
            "score_lead": score_lead,
            "visits": max((m.get("visits", 0) for m in move_infos[:1]), default=0),
            "top_moves": self._build_top_moves(move_infos),
            "ownership": ownership,
            "actual_move": actual_move,
            "actual_player": actual_player,
            "delta_score": delta_score,
            "delta_winrate": delta_winrate,
        }
