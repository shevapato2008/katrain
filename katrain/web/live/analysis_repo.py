"""Repository for live analysis database operations."""

from datetime import datetime
from typing import Optional
import logging

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from katrain.web.core.models_db import LiveMatchDB, LiveAnalysisDB, AnalysisStatusEnum
from katrain.web.live.models import LiveMatch, MoveAnalysis, TopMove, MatchSource, MatchStatus

logger = logging.getLogger("katrain_web")


# Priority constants
PRIORITY_LIVE_NEW = 1000       # Live match new move (highest)
PRIORITY_USER_VIEW = 500       # User is currently viewing this position
PRIORITY_LIVE_BACKFILL = 100   # Backfill historical moves in live match
PRIORITY_FINISHED = 10         # Finished match analysis


class LiveAnalysisRepo:
    """Repository for managing live match analysis data in the database."""

    def __init__(self, db: Session):
        self.db = db

    # ==================== Match Operations ====================

    def get_or_create_match(self, match: LiveMatch) -> LiveMatchDB:
        """Get existing match record or create a new one."""
        db_match = self.db.query(LiveMatchDB).filter(
            LiveMatchDB.match_id == match.id
        ).first()

        if db_match:
            # Update existing match with latest data
            db_match.status = match.status.value
            db_match.result = match.result
            db_match.move_count = match.move_count
            # Only update moves if new data has moves (don't overwrite with empty list)
            if match.moves:
                db_match.moves = match.moves
            db_match.current_winrate = match.current_winrate
            db_match.current_score = match.current_score
            db_match.sgf_content = match.sgf
            self.db.commit()
            return db_match

        # Create new match record
        db_match = LiveMatchDB(
            match_id=match.id,
            source=match.source.value,
            source_id=match.source_id,
            tournament=match.tournament,
            round_name=match.round_name,
            match_date=match.date,
            player_black=match.player_black,
            player_white=match.player_white,
            black_rank=match.black_rank,
            white_rank=match.white_rank,
            status=match.status.value,
            result=match.result,
            move_count=match.move_count,
            moves=match.moves,
            current_winrate=match.current_winrate,
            current_score=match.current_score,
            sgf_content=match.sgf,
            board_size=getattr(match, 'board_size', 19) or 19,
            komi=getattr(match, 'komi', 7.5) or 7.5,
            rules=getattr(match, 'rules', 'chinese') or 'chinese',
        )
        self.db.add(db_match)
        self.db.commit()
        self.db.refresh(db_match)
        return db_match

    def update_katago_stats(self, match_id: str, winrate: float, score: float) -> Optional[LiveMatchDB]:
        """Update KataGo analysis stats for a match.

        Called when analysis completes for the latest move.

        Args:
            match_id: The match ID
            winrate: Black's winrate from KataGo (0-1)
            score: Black's score lead from KataGo

        Returns:
            Updated match record or None if not found
        """
        db_match = self.db.query(LiveMatchDB).filter(
            LiveMatchDB.match_id == match_id
        ).first()

        if db_match:
            db_match.katago_winrate = winrate
            db_match.katago_score = score
            self.db.commit()
            self.db.refresh(db_match)

        return db_match

    def get_match(self, match_id: str) -> Optional[LiveMatchDB]:
        """Get match by ID."""
        return self.db.query(LiveMatchDB).filter(
            LiveMatchDB.match_id == match_id
        ).first()

    # ==================== Analysis Operations ====================

    def get_analysis(self, match_id: str, move_number: int) -> Optional[LiveAnalysisDB]:
        """Get analysis for a specific move."""
        return self.db.query(LiveAnalysisDB).filter(
            and_(
                LiveAnalysisDB.match_id == match_id,
                LiveAnalysisDB.move_number == move_number
            )
        ).first()

    def get_all_analysis(self, match_id: str) -> list[LiveAnalysisDB]:
        """Get all analysis records for a match."""
        return self.db.query(LiveAnalysisDB).filter(
            LiveAnalysisDB.match_id == match_id
        ).order_by(LiveAnalysisDB.move_number).all()

    def get_successful_analysis(self, match_id: str) -> dict[int, MoveAnalysis]:
        """Get all successful analysis as a dict keyed by move number."""
        records = self.db.query(LiveAnalysisDB).filter(
            and_(
                LiveAnalysisDB.match_id == match_id,
                LiveAnalysisDB.status == AnalysisStatusEnum.SUCCESS.value
            )
        ).all()

        result = {}
        for record in records:
            result[record.move_number] = self._db_to_move_analysis(match_id, record)
        return result

    def create_pending_analysis(
        self,
        match_id: str,
        move_numbers: list[int],
        priority: int = PRIORITY_FINISHED,
        moves: Optional[list[str]] = None
    ) -> list[LiveAnalysisDB]:
        """Create pending analysis records for multiple moves.

        Args:
            match_id: The match ID
            move_numbers: List of move numbers to analyze
            priority: Priority level for the analysis task
            moves: Optional list of moves to populate actual_move/actual_player
        """
        created = []
        for move_num in move_numbers:
            # Check if record already exists
            existing = self.get_analysis(match_id, move_num)
            if existing:
                # Update priority if higher
                if priority > existing.priority:
                    existing.priority = priority
                    self.db.commit()
                continue

            # Determine actual move and player if moves are provided
            actual_move = None
            actual_player = None
            if moves and move_num > 0 and move_num <= len(moves):
                actual_move = moves[move_num - 1]
                actual_player = "B" if move_num % 2 == 1 else "W"

            record = LiveAnalysisDB(
                match_id=match_id,
                move_number=move_num,
                status=AnalysisStatusEnum.PENDING.value,
                priority=priority,
                actual_move=actual_move,
                actual_player=actual_player,
            )
            self.db.add(record)
            created.append(record)

        if created:
            self.db.commit()
            for record in created:
                self.db.refresh(record)

        return created

    def update_analysis_result(
        self,
        match_id: str,
        move_number: int,
        winrate: float,
        score_lead: float,
        top_moves: list[dict],
        ownership: Optional[list[list[float]]] = None,
        delta_score: Optional[float] = None,
        delta_winrate: Optional[float] = None,
        is_brilliant: bool = False,
        is_mistake: bool = False,
        is_questionable: bool = False
    ) -> Optional[LiveAnalysisDB]:
        """Update analysis record with results."""
        record = self.get_analysis(match_id, move_number)
        if not record:
            logger.warning(f"Analysis record not found: {match_id} move {move_number}")
            return None

        record.status = AnalysisStatusEnum.SUCCESS.value
        record.winrate = winrate
        record.score_lead = score_lead
        record.top_moves = top_moves
        record.ownership = ownership
        record.delta_score = delta_score
        record.delta_winrate = delta_winrate
        record.is_brilliant = is_brilliant
        record.is_mistake = is_mistake
        record.is_questionable = is_questionable
        record.analyzed_at = datetime.now()
        record.error_message = None

        self.db.commit()
        self.db.refresh(record)
        return record

    def mark_running(self, match_id: str, move_number: int) -> Optional[LiveAnalysisDB]:
        """Mark analysis as running."""
        record = self.get_analysis(match_id, move_number)
        if record:
            record.status = AnalysisStatusEnum.RUNNING.value
            self.db.commit()
        return record

    def mark_failed(
        self,
        match_id: str,
        move_number: int,
        error: str,
        max_retries: int = 3
    ) -> Optional[LiveAnalysisDB]:
        """Mark analysis as failed and optionally reset to pending for retry."""
        record = self.get_analysis(match_id, move_number)
        if not record:
            return None

        record.retry_count += 1
        record.error_message = error

        if record.retry_count >= max_retries:
            record.status = AnalysisStatusEnum.FAILED.value
            logger.warning(f"Analysis permanently failed: {match_id} move {move_number}: {error}")
        else:
            # Reset to pending for retry
            record.status = AnalysisStatusEnum.PENDING.value
            logger.info(f"Analysis retry scheduled: {match_id} move {move_number} (attempt {record.retry_count})")

        self.db.commit()
        self.db.refresh(record)
        return record

    def get_pending_analysis(self, limit: int = 10) -> list[LiveAnalysisDB]:
        """Get pending analysis tasks ordered by priority (highest first)."""
        return self.db.query(LiveAnalysisDB).filter(
            LiveAnalysisDB.status == AnalysisStatusEnum.PENDING.value
        ).order_by(
            LiveAnalysisDB.priority.desc(),
            LiveAnalysisDB.created_at.asc()
        ).limit(limit).all()

    def get_unanalyzed_moves(self, match_id: str, max_move: int) -> list[int]:
        """Get list of move numbers that haven't been analyzed yet."""
        analyzed = self.db.query(LiveAnalysisDB.move_number).filter(
            LiveAnalysisDB.match_id == match_id
        ).all()
        analyzed_set = {r[0] for r in analyzed}

        # Return moves from 0 to max_move that haven't been analyzed
        return [i for i in range(max_move + 1) if i not in analyzed_set]

    def get_queue_size(self) -> int:
        """Get number of pending analysis tasks."""
        return self.db.query(LiveAnalysisDB).filter(
            LiveAnalysisDB.status == AnalysisStatusEnum.PENDING.value
        ).count()

    def boost_priority(self, match_id: str, move_numbers: list[int], priority: int) -> int:
        """Boost priority for specific moves (e.g., user is viewing these positions)."""
        count = 0
        for move_num in move_numbers:
            record = self.get_analysis(match_id, move_num)
            if record and record.priority < priority:
                record.priority = priority
                count += 1
        if count:
            self.db.commit()
        return count

    # ==================== Cleanup Methods ====================

    def delete_invalid_match(self, match_id: str) -> bool:
        """Delete a match and all its analysis records.

        Args:
            match_id: The match ID to delete

        Returns:
            True if match was deleted, False if not found
        """
        # Delete analysis records first (due to foreign key)
        self.db.query(LiveAnalysisDB).filter(
            LiveAnalysisDB.match_id == match_id
        ).delete()

        # Delete match record
        deleted = self.db.query(LiveMatchDB).filter(
            LiveMatchDB.match_id == match_id
        ).delete()

        self.db.commit()
        return deleted > 0

    def cleanup_failed_analyses(self) -> int:
        """Remove all failed analysis records for matches without valid moves data.

        Returns:
            Number of records deleted
        """
        # Find matches with no moves
        matches_without_moves = self.db.query(LiveMatchDB.match_id).filter(
            or_(
                LiveMatchDB.moves.is_(None),
                LiveMatchDB.move_count == 0
            )
        ).all()

        match_ids = [m[0] for m in matches_without_moves]

        if not match_ids:
            return 0

        # Delete failed analyses for these matches
        deleted = self.db.query(LiveAnalysisDB).filter(
            and_(
                LiveAnalysisDB.match_id.in_(match_ids),
                LiveAnalysisDB.status == AnalysisStatusEnum.FAILED.value
            )
        ).delete(synchronize_session=False)

        self.db.commit()
        logger.info(f"Cleaned up {deleted} failed analyses for matches without moves")
        return deleted

    def get_analysis_stats(self) -> dict:
        """Get statistics about analysis records.

        Returns:
            Dict with counts by status
        """
        from sqlalchemy import func

        stats = self.db.query(
            LiveAnalysisDB.status,
            func.count(LiveAnalysisDB.id)
        ).group_by(LiveAnalysisDB.status).all()

        return {status: count for status, count in stats}

    def reset_failed_for_match(self, match_id: str) -> int:
        """Reset all failed analyses to pending for a match.

        This is used after moves data has been recovered for a match.

        Args:
            match_id: The match ID

        Returns:
            Number of records reset
        """
        records = self.db.query(LiveAnalysisDB).filter(
            and_(
                LiveAnalysisDB.match_id == match_id,
                LiveAnalysisDB.status == AnalysisStatusEnum.FAILED.value
            )
        ).all()

        count = 0
        for record in records:
            record.status = AnalysisStatusEnum.PENDING.value
            record.retry_count = 0
            record.error_message = None
            count += 1

        if count:
            self.db.commit()
            logger.info(f"Reset {count} failed analyses for {match_id}")

        return count

    def get_matches_without_moves(self) -> list[LiveMatchDB]:
        """Get matches that have no moves data.

        Returns:
            List of matches with empty or null moves
        """
        from sqlalchemy import func
        from katrain.web.core.db import engine

        array_len = func.jsonb_array_length if engine.dialect.name == "postgresql" else func.json_array_length

        return self.db.query(LiveMatchDB).filter(
            or_(
                LiveMatchDB.moves.is_(None),
                array_len(LiveMatchDB.moves) == 0
            )
        ).all()

    # ==================== Helper Methods ====================

    def _db_to_move_analysis(self, match_id: str, record: LiveAnalysisDB) -> MoveAnalysis:
        """Convert database record to MoveAnalysis Pydantic model."""
        top_moves = []
        if record.top_moves:
            for tm in record.top_moves:
                top_moves.append(TopMove(
                    move=tm.get("move", ""),
                    visits=tm.get("visits", 0),
                    winrate=tm.get("winrate", 0.5),
                    score_lead=tm.get("score_lead", 0.0),
                    prior=tm.get("prior", 0.0),
                    pv=tm.get("pv", []),
                    psv=tm.get("psv", 0.0),  # playSelectionValue for ranking
                ))

        return MoveAnalysis(
            match_id=match_id,
            move_number=record.move_number,
            move=record.actual_move,
            player=record.actual_player,
            winrate=record.winrate or 0.5,
            score_lead=record.score_lead or 0.0,
            top_moves=top_moves,
            ownership=record.ownership,
            is_brilliant=record.is_brilliant or False,
            is_mistake=record.is_mistake or False,
            is_questionable=record.is_questionable or False,
            delta_score=record.delta_score or 0.0,
            delta_winrate=record.delta_winrate or 0.0,
        )
