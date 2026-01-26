"""Live broadcasting service - main entry point.

Integrates cache, poller, and analyzer with database persistence.
"""

import asyncio
import logging
from typing import Optional

from katrain.web.core.db import SessionLocal
from katrain.web.live.cache import LiveCache
from katrain.web.live.models import LiveConfig, LiveMatch, MoveAnalysis, MatchStatus
from katrain.web.live.poller import LivePoller
from katrain.web.live.analyzer import LiveAnalyzer
from katrain.web.live.analysis_repo import LiveAnalysisRepo, PRIORITY_FINISHED

logger = logging.getLogger("katrain_web.live")


class LiveService:
    """Main service class for live broadcasting functionality.

    This class manages the lifecycle of:
    - LiveCache: In-memory storage for match data
    - LivePoller: Background polling from external APIs
    - LiveAnalyzer: KataGo analysis integration with DB persistence
    """

    def __init__(
        self,
        config: Optional[LiveConfig] = None,
        katago_url: Optional[str] = None,
    ):
        self.config = config or LiveConfig()
        self.katago_url = katago_url

        # Initialize components
        self.cache = LiveCache(
            max_live_matches=100,
            max_finished_matches=200,
            finished_retention_hours=168,  # 7 days
        )

        self.poller = LivePoller(
            cache=self.cache,
            config=self.config,
        )

        # Initialize analyzer if local KataGo is enabled
        if self.config.use_local_katago:
            self.analyzer = LiveAnalyzer(
                config=self.config,
                katago_url=self.katago_url,
            )
            # Connect poller to analyzer
            self.poller.set_analyzer(self.analyzer)
            self.poller.set_on_new_move(self._on_new_move)
        else:
            self.analyzer = None

        self._started = False
        self._analysis_cron_task: Optional[asyncio.Task] = None

    def _on_new_move(self, match: LiveMatch, move_number: int) -> None:
        """Callback when poller detects a new move."""
        if self.analyzer:
            # The poller already creates pending analysis records
            # Just update the analyzer's match cache
            self.analyzer.update_match_cache(match)

    async def start(self) -> None:
        """Start the live service (polling, analysis, etc.)."""
        if self._started:
            logger.warning("Live service already started")
            return

        logger.info("Starting live broadcasting service")

        # Start poller
        await self.poller.start()

        # Start analyzer if enabled
        if self.analyzer:
            await self.analyzer.start()

            # Start analysis cron job for finished matches
            self._analysis_cron_task = asyncio.create_task(self._analysis_cron_loop())

        self._started = True
        logger.info("Live broadcasting service started")

    async def stop(self) -> None:
        """Stop the live service."""
        if not self._started:
            return

        logger.info("Stopping live broadcasting service")

        # Stop cron task
        if self._analysis_cron_task:
            self._analysis_cron_task.cancel()
            try:
                await self._analysis_cron_task
            except asyncio.CancelledError:
                pass

        # Stop analyzer
        if self.analyzer:
            await self.analyzer.stop()

        # Stop poller
        await self.poller.stop()

        self._started = False
        logger.info("Live broadcasting service stopped")

    async def _analysis_cron_loop(self) -> None:
        """Background cron job to schedule analysis for all matches.

        Runs periodically to find matches that need analysis and create
        pending analysis records for them.

        Note: Moves are now fetched in _persist_matches() when matches are first
        discovered. This cron job just schedules analysis for matches with moves.
        """
        # Run immediately on startup, then every 5 minutes
        first_run = True

        while True:
            try:
                if not first_run:
                    await asyncio.sleep(300)  # Every 5 minutes after first run
                first_run = False

                # Phase 1: Recover any matches that still don't have moves (fallback)
                await self._recover_matches_without_moves()

                # Phase 2: Schedule analysis for matches with moves
                scheduled_count = 0

                with SessionLocal() as db:
                    repo = LiveAnalysisRepo(db)

                    # Get all matches from DB that have moves
                    from katrain.web.core.models_db import LiveMatchDB
                    from sqlalchemy import func

                    matches_with_moves = db.query(LiveMatchDB).filter(
                        LiveMatchDB.moves.isnot(None),
                        func.jsonb_array_length(LiveMatchDB.moves) > 0
                    ).all()

                    for db_match in matches_with_moves:
                        # Find unanalyzed moves
                        unanalyzed = repo.get_unanalyzed_moves(db_match.match_id, db_match.move_count)

                        if unanalyzed:
                            # Schedule analysis at low priority for finished matches
                            priority = PRIORITY_FINISHED if db_match.status == "finished" else PRIORITY_FINISHED * 2
                            repo.create_pending_analysis(
                                match_id=db_match.match_id,
                                move_numbers=unanalyzed,
                                priority=priority,
                                moves=db_match.moves,
                            )
                            scheduled_count += len(unanalyzed)

                if scheduled_count > 0:
                    logger.info(f"Cron job scheduled {scheduled_count} moves for analysis")

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in analysis cron loop: {e}")
                await asyncio.sleep(60)

    async def _recover_matches_without_moves(self) -> None:
        """Check database for matches without moves and try to fetch them.

        This recovers from the bug where moves were overwritten with empty lists.
        """
        try:
            with SessionLocal() as db:
                repo = LiveAnalysisRepo(db)
                matches_without_moves = repo.get_matches_without_moves()

                if not matches_without_moves:
                    return

                logger.info(f"Found {len(matches_without_moves)} matches without moves in DB")

                recovered_count = 0
                for db_match in matches_without_moves:
                    # Try to fetch from API
                    try:
                        detailed = await self.poller.fetch_match_detail(db_match.match_id)
                        if detailed and detailed.moves:
                            # Update database with moves
                            db_match.moves = detailed.moves
                            db.commit()

                            # Reset failed analyses for this match
                            reset_count = repo.reset_failed_for_match(db_match.match_id)

                            logger.info(
                                f"Recovered moves for {db_match.match_id}: "
                                f"{len(detailed.moves)} moves, reset {reset_count} failed analyses"
                            )
                            recovered_count += 1
                    except Exception as e:
                        logger.warning(f"Failed to recover moves for {db_match.match_id}: {e}")

                if recovered_count > 0:
                    logger.info(f"Recovered moves for {recovered_count} matches")

        except Exception as e:
            logger.error(f"Error in recover_matches_without_moves: {e}")

    async def request_analysis(self, match_id: str, move_range: Optional[tuple] = None) -> int:
        """Request analysis for a match.

        Args:
            match_id: The match to analyze
            move_range: Optional (start, end) tuple, defaults to full game

        Returns:
            Number of analysis tasks created
        """
        if not self.analyzer:
            logger.warning("Analyzer not enabled")
            return 0

        match = await self.cache.get_match(match_id)
        if not match:
            logger.warning(f"Match not found: {match_id}")
            return 0

        if move_range:
            start, end = move_range
        else:
            start, end = 0, match.move_count

        # Update cache and create pending analysis records
        self.analyzer.update_match_cache(match)
        return await self.analyzer.request_analysis(match_id, (start, end))

    async def get_match_analysis(self, match_id: str) -> dict[int, MoveAnalysis]:
        """Get all completed analysis for a match.

        Args:
            match_id: The match ID

        Returns:
            Dict mapping move_number to MoveAnalysis
        """
        if self.analyzer:
            return await self.analyzer.get_match_analysis(match_id)

        # Fallback to DB directly if no analyzer
        with SessionLocal() as db:
            repo = LiveAnalysisRepo(db)
            return repo.get_successful_analysis(match_id)

    async def preload_analysis(self, match_id: str) -> dict[int, MoveAnalysis]:
        """Preload analysis for a match when user enters the page.

        This also boosts priority for any pending analysis.

        Args:
            match_id: The match ID

        Returns:
            Dict mapping move_number to MoveAnalysis
        """
        # Get completed analysis
        analysis = await self.get_match_analysis(match_id)

        # If user is viewing, boost priority of pending analysis
        match = await self.cache.get_match(match_id)
        if match and self.analyzer:
            # Boost priority for moves around current position
            move_numbers = list(range(max(0, match.move_count - 10), match.move_count + 1))
            await self.analyzer.boost_user_view_priority(match_id, move_numbers)

        return analysis

    @property
    def is_running(self) -> bool:
        """Check if the service is running."""
        return self._started

    async def recover_match_moves(self, match_id: str) -> dict:
        """Manually recover moves for a specific match.

        This fetches the match detail from the API and updates the database,
        then resets any failed analyses.

        Args:
            match_id: The match ID to recover

        Returns:
            Dict with recovery results
        """
        result = {
            "match_id": match_id,
            "moves_fetched": 0,
            "failed_analyses_reset": 0,
            "error": None,
        }

        try:
            # Fetch from API
            detailed = await self.poller.fetch_match_detail(match_id)
            if not detailed or not detailed.moves:
                result["error"] = "Could not fetch moves from API"
                return result

            result["moves_fetched"] = len(detailed.moves)

            # Update database
            with SessionLocal() as db:
                repo = LiveAnalysisRepo(db)
                repo.get_or_create_match(detailed)

                # Reset failed analyses
                reset_count = repo.reset_failed_for_match(match_id)
                result["failed_analyses_reset"] = reset_count

            logger.info(f"Recovered match {match_id}: {result}")

        except Exception as e:
            result["error"] = str(e)
            logger.error(f"Error recovering match {match_id}: {e}")

        return result

    async def get_analysis_stats(self) -> dict:
        """Get statistics about the analysis system.

        Returns:
            Dict with queue size, status counts, etc.
        """
        stats = {
            "queue_size": 0,
            "by_status": {},
            "matches_without_moves": 0,
        }

        try:
            with SessionLocal() as db:
                repo = LiveAnalysisRepo(db)
                stats["queue_size"] = repo.get_queue_size()
                stats["by_status"] = repo.get_analysis_stats()
                stats["matches_without_moves"] = len(repo.get_matches_without_moves())
        except Exception as e:
            logger.error(f"Error getting analysis stats: {e}")

        return stats


def create_live_service(config: Optional[LiveConfig] = None) -> LiveService:
    """Factory function to create a LiveService instance.

    Args:
        config: Optional configuration. If not provided, defaults are used.

    Returns:
        LiveService instance (not started)
    """
    return LiveService(config=config)
