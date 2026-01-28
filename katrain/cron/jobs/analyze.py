"""AnalyzeJob: flight-window KataGo analysis with preemption."""

import asyncio
import logging
from typing import Optional

from katrain.cron import config
from katrain.cron.jobs.base import BaseJob
from katrain.cron.clients.katago import KataGoClient
from katrain.cron.db import SessionLocal
from katrain.cron.analysis_repo import AnalysisRepo
from katrain.cron.models import LiveMatchDB

logger = logging.getLogger("katrain_cron.analyze")


class AnalyzeJob(BaseJob):
    """Persistent async loop maintaining a flight window of concurrent KataGo requests."""

    name = "analyze"
    interval_seconds = 0  # Not interval-driven; runs as persistent loop
    window_size = config.ANALYSIS_WINDOW_SIZE
    request_timeout = config.ANALYSIS_REQUEST_TIMEOUT
    preempt_threshold = config.ANALYSIS_PREEMPT_THRESHOLD

    def __init__(self):
        super().__init__()
        self._running = True
        self._katago = KataGoClient()

    async def run(self) -> None:
        self._running = True

        # Crash recovery
        db = SessionLocal()
        try:
            repo = AnalysisRepo(db)
            repo.reset_stale_running()
        finally:
            db.close()

        # In-flight tracking: record_id -> asyncio.Task
        in_flight: dict[int, asyncio.Task] = {}
        priorities: dict[int, int] = {}

        # Initial fill
        await self._fill_window(in_flight, priorities)

        while self._running:
            if not in_flight:
                await asyncio.sleep(5)
                await self._fill_window(in_flight, priorities)
                continue

            done, _ = await asyncio.wait(in_flight.values(), return_when=asyncio.FIRST_COMPLETED)

            for completed in done:
                rid = self._find_key(in_flight, completed)
                if rid is None:
                    continue
                del in_flight[rid]
                del priorities[rid]

                try:
                    result = completed.result()
                    self._handle_result(rid, result)
                except asyncio.CancelledError:
                    pass  # Preempted — already reset to pending
                except Exception as exc:
                    self._handle_failure(rid, str(exc))

            # Preemption check
            await self._maybe_preempt(in_flight, priorities)

            # Refill
            slots = self.window_size - len(in_flight)
            if slots > 0:
                await self._fill_slots(in_flight, priorities, slots)

    # ── Window management ────────────────────────────────────

    async def _fill_window(self, in_flight: dict, priorities: dict) -> None:
        await self._fill_slots(in_flight, priorities, self.window_size - len(in_flight))

    async def _fill_slots(self, in_flight: dict, priorities: dict, slots: int) -> None:
        if slots <= 0:
            return
        db = SessionLocal()
        try:
            repo = AnalysisRepo(db)
            pending = repo.fetch_pending(limit=slots)
            for record in pending:
                task = asyncio.create_task(self._send_analysis(record))
                in_flight[record.id] = task
                priorities[record.id] = record.priority
        finally:
            db.close()

    async def _send_analysis(self, record) -> dict:
        """Build and send one analysis request to KataGo, with timeout."""
        # Load match data for moves and rules
        db = SessionLocal()
        try:
            match = db.query(LiveMatchDB).filter(LiveMatchDB.match_id == record.match_id).first()
            if not match or not match.moves:
                return {"error": f"No moves for match {record.match_id}", "record_id": record.id}

            moves = match.moves
            rules = match.rules or "chinese"
            komi = match.komi or 7.5
            board_size = match.board_size or 19
        finally:
            db.close()

        # Build move sequence up to the analyzed position
        move_seq = []
        for i, mv in enumerate(moves[: record.move_number]):
            player = "B" if (i % 2 == 0) else "W"
            move_seq.append([player, mv])

        request_id = f"cron_{record.match_id}_{record.move_number}"

        response = await asyncio.wait_for(
            self._katago.analyze(
                request_id=request_id,
                moves=move_seq,
                rules=rules,
                komi=komi,
                board_size=board_size,
                priority=record.priority,
            ),
            timeout=self.request_timeout,
        )

        response["_record_id"] = record.id
        response["_match_id"] = record.match_id
        response["_move_number"] = record.move_number
        return response

    # ── Result handling ──────────────────────────────────────

    def _handle_result(self, record_id: int, result: dict) -> None:
        if "error" in result and "_record_id" not in result:
            # KataGo returned an error
            self._handle_failure(record_id, result.get("error", "Unknown error"))
            return

        parsed = KataGoClient.parse_result(result)
        if parsed is None:
            self._handle_failure(record_id, result.get("error", "Parse failed"))
            return

        db = SessionLocal()
        try:
            repo = AnalysisRepo(db)
            repo.save_result(
                record_id=record_id,
                winrate=parsed["winrate"],
                score_lead=parsed["score_lead"],
                top_moves=parsed["top_moves"],
                ownership=parsed.get("ownership"),
            )

            # Compute delta classification
            record = db.query(LiveMatchDB).filter(False).first()  # just to trigger model load
            from katrain.cron.models import LiveAnalysisDB
            analysis = db.query(LiveAnalysisDB).get(record_id)
            if analysis:
                repo.compute_and_store_delta(analysis)

                # Update match katago stats if this is the latest move
                match_id = result.get("_match_id", analysis.match_id)
                repo.update_katago_stats(match_id, parsed["winrate"], parsed["score_lead"])

            logger.debug("Analysis success id=%d wr=%.3f sc=%.1f", record_id, parsed["winrate"], parsed["score_lead"])
        except Exception:
            logger.exception("Failed to save analysis result id=%d", record_id)
        finally:
            db.close()

    def _handle_failure(self, record_id: int, error: str) -> None:
        db = SessionLocal()
        try:
            repo = AnalysisRepo(db)
            repo.mark_failed(record_id, error)
        finally:
            db.close()

    # ── Preemption ───────────────────────────────────────────

    async def _maybe_preempt(self, in_flight: dict, priorities: dict) -> None:
        if not in_flight:
            return
        db = SessionLocal()
        try:
            repo = AnalysisRepo(db)
            highest = repo.peek_highest_pending_priority()
        finally:
            db.close()

        if highest is None:
            return

        lowest_key = min(priorities, key=priorities.get)
        lowest_pri = priorities[lowest_key]

        if highest - lowest_pri >= self.preempt_threshold:
            # Cancel the low-priority in-flight task
            in_flight[lowest_key].cancel()
            del in_flight[lowest_key]
            del priorities[lowest_key]
            # Reset back to pending
            db = SessionLocal()
            try:
                repo = AnalysisRepo(db)
                repo.mark_pending(lowest_key)
            finally:
                db.close()
            logger.info("Preempted id=%d (pri=%d) for pending pri=%d", lowest_key, lowest_pri, highest)

    # ── Utilities ────────────────────────────────────────────

    @staticmethod
    def _find_key(mapping: dict[int, asyncio.Task], task: asyncio.Task) -> Optional[int]:
        for k, v in mapping.items():
            if v is task:
                return k
        return None

    def stop(self):
        self._running = False
