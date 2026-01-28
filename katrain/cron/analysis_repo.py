"""Analysis task queue DB operations for katrain-cron.

Uses FOR UPDATE SKIP LOCKED for safe concurrent task pickup.
"""

import logging
from datetime import datetime
from typing import Optional

from sqlalchemy import and_, text
from sqlalchemy.orm import Session

from katrain.cron.models import (
    LiveAnalysisDB,
    LiveMatchDB,
    PRIORITY_LIVE_NEW,
    PRIORITY_LIVE_BACKFILL,
    PRIORITY_FINISHED,
)

logger = logging.getLogger("katrain_cron.analysis_repo")


class AnalysisRepo:
    """DB operations for the analysis task queue."""

    def __init__(self, db: Session):
        self.db = db

    # ── Task queue ───────────────────────────────────────────

    def fetch_pending(self, limit: int) -> list[LiveAnalysisDB]:
        """Fetch and atomically mark pending tasks as running.

        Uses FOR UPDATE SKIP LOCKED on PostgreSQL to prevent duplicate pickup.
        Falls back to plain SELECT on SQLite (single-instance assumption).
        """
        from katrain.cron.db import engine

        if engine.dialect.name == "postgresql":
            # Raw SQL for FOR UPDATE SKIP LOCKED (not expressible via ORM)
            sql = text("""
                UPDATE live_analysis
                SET status = 'running'
                WHERE id IN (
                    SELECT id FROM live_analysis
                    WHERE status = 'pending'
                    ORDER BY priority DESC, created_at ASC
                    LIMIT :lim
                    FOR UPDATE SKIP LOCKED
                )
                RETURNING id, match_id, move_number, priority, status
            """)
            rows = self.db.execute(sql, {"lim": limit}).fetchall()
            self.db.commit()
            if not rows:
                return []
            ids = [r.id for r in rows]
            return self.db.query(LiveAnalysisDB).filter(LiveAnalysisDB.id.in_(ids)).all()
        else:
            # SQLite fallback — no row-level locking
            records = (
                self.db.query(LiveAnalysisDB)
                .filter(LiveAnalysisDB.status == "pending")
                .order_by(LiveAnalysisDB.priority.desc(), LiveAnalysisDB.created_at.asc())
                .limit(limit)
                .all()
            )
            for r in records:
                r.status = "running"
            self.db.commit()
            return records

    def peek_highest_pending_priority(self) -> Optional[int]:
        """Return the highest priority among pending tasks, or None."""
        row = (
            self.db.query(LiveAnalysisDB.priority)
            .filter(LiveAnalysisDB.status == "pending")
            .order_by(LiveAnalysisDB.priority.desc())
            .limit(1)
            .first()
        )
        return row[0] if row else None

    def reset_stale_running(self) -> int:
        """Reset all 'running' tasks back to 'pending' (crash recovery)."""
        count = (
            self.db.query(LiveAnalysisDB)
            .filter(LiveAnalysisDB.status == "running")
            .update({"status": "pending"})
        )
        self.db.commit()
        if count:
            logger.info("Reset %d stale running tasks to pending", count)
        return count

    # ── Result persistence ───────────────────────────────────

    def save_result(
        self,
        record_id: int,
        winrate: float,
        score_lead: float,
        top_moves: list[dict],
        ownership: Optional[list[list[float]]] = None,
    ) -> None:
        """Mark a task as success and store analysis results."""
        record = self.db.query(LiveAnalysisDB).get(record_id)
        if not record:
            return
        record.status = "success"
        record.winrate = winrate
        record.score_lead = score_lead
        record.top_moves = top_moves
        record.ownership = ownership
        record.analyzed_at = datetime.utcnow()
        record.error_message = None
        self.db.commit()

    def mark_failed(self, record_id: int, error: str, max_retries: int = 3) -> None:
        """Increment retry count; reset to pending if retries remain."""
        record = self.db.query(LiveAnalysisDB).get(record_id)
        if not record:
            return
        record.retry_count += 1
        record.error_message = error
        if record.retry_count >= max_retries:
            record.status = "failed"
            logger.warning("Analysis permanently failed id=%d: %s", record_id, error)
        else:
            record.status = "pending"
            logger.info("Analysis retrying id=%d attempt=%d", record_id, record.retry_count)
        self.db.commit()

    def mark_pending(self, record_id: int) -> None:
        """Reset a running task back to pending (used by preemption)."""
        record = self.db.query(LiveAnalysisDB).get(record_id)
        if record:
            record.status = "pending"
            self.db.commit()

    # ── Match helpers ────────────────────────────────────────

    def get_match(self, match_id: str) -> Optional[LiveMatchDB]:
        return self.db.query(LiveMatchDB).filter(LiveMatchDB.match_id == match_id).first()

    def update_katago_stats(self, match_id: str, winrate: float, score: float) -> None:
        """Update katago_winrate/katago_score on the match."""
        match = self.get_match(match_id)
        if match:
            match.katago_winrate = winrate
            match.katago_score = score
            self.db.commit()

    # ── Delta classification ─────────────────────────────────

    def compute_and_store_delta(self, record: LiveAnalysisDB) -> None:
        """Compute delta_score/delta_winrate vs previous move and classify."""
        if record.move_number == 0:
            return
        prev = (
            self.db.query(LiveAnalysisDB)
            .filter(
                and_(
                    LiveAnalysisDB.match_id == record.match_id,
                    LiveAnalysisDB.move_number == record.move_number - 1,
                    LiveAnalysisDB.status == "success",
                )
            )
            .first()
        )
        if not prev or prev.winrate is None or record.winrate is None:
            return

        # Delta from previous position to this position
        # Positive delta means move was good for the player who played it
        delta_wr = record.winrate - prev.winrate
        delta_sc = record.score_lead - (prev.score_lead or 0.0)

        # If white played, invert (because winrate/score are from Black perspective)
        if record.actual_player == "W":
            delta_wr = -delta_wr
            delta_sc = -delta_sc

        record.delta_winrate = delta_wr
        record.delta_score = delta_sc
        record.is_brilliant = delta_sc > 2.0
        record.is_mistake = delta_sc < -3.0
        record.is_questionable = -3.0 <= delta_sc < -1.0
        self.db.commit()

    # ── Pending task creation ────────────────────────────────

    def create_pending(
        self,
        match_id: str,
        move_numbers: list[int],
        priority: int,
        moves: Optional[list[str]] = None,
    ) -> int:
        """Create pending analysis tasks. Skips if already exists (upsert priority)."""
        created = 0
        for mn in move_numbers:
            existing = (
                self.db.query(LiveAnalysisDB)
                .filter(
                    and_(
                        LiveAnalysisDB.match_id == match_id,
                        LiveAnalysisDB.move_number == mn,
                    )
                )
                .first()
            )
            if existing:
                if priority > existing.priority and existing.status == "pending":
                    existing.priority = priority
                continue

            actual_move = None
            actual_player = None
            if moves and 0 < mn <= len(moves):
                actual_move = moves[mn - 1]
                actual_player = "B" if mn % 2 == 1 else "W"

            self.db.add(
                LiveAnalysisDB(
                    match_id=match_id,
                    move_number=mn,
                    status="pending",
                    priority=priority,
                    actual_move=actual_move,
                    actual_player=actual_player,
                )
            )
            created += 1

        if created:
            self.db.commit()
        return created
