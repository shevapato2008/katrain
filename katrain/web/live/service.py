"""Live broadcasting service - main entry point.

Reads match data and analysis results from the database (populated by katrain-cron).
Maintains in-memory caches for fast API responses.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

from katrain.web.core.db import SessionLocal
from katrain.web.live.cache import LiveCache
from katrain.web.live.models import LiveConfig, LiveMatch, MoveAnalysis, MatchStatus, MatchSource

logger = logging.getLogger("katrain_web.live")

# DB refresh intervals (seconds)
_MATCH_REFRESH_INTERVAL = 5
_CLEANUP_INTERVAL = 3600  # 1 hour


class LiveService:
    """Main service class for live broadcasting functionality.

    In the cron-based architecture, this service is read-only:
    - katrain-cron handles polling, analysis, and translation
    - This service reads from the shared PostgreSQL database
    - In-memory caches provide fast API responses
    """

    def __init__(self, config: Optional[LiveConfig] = None):
        self.config = config or LiveConfig()

        # In-memory match cache
        self.cache = LiveCache(
            max_live_matches=100,
            max_finished_matches=200,
            finished_retention_hours=168,  # 7 days
        )

        self._started = False
        self._refresh_task: Optional[asyncio.Task] = None
        self._cleanup_task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        """Start the live service (DB refresh loops)."""
        if self._started:
            logger.warning("Live service already started")
            return

        logger.info("Starting live broadcasting service")

        # Initial load from DB
        await self._load_matches_from_db()

        # Start background refresh loops
        self._refresh_task = asyncio.create_task(self._db_refresh_loop())
        self._cleanup_task = asyncio.create_task(self._cache_cleanup_loop())

        self._started = True
        logger.info("Live broadcasting service started")

    async def stop(self) -> None:
        """Stop the live service."""
        if not self._started:
            return

        logger.info("Stopping live broadcasting service")

        for task in (self._refresh_task, self._cleanup_task):
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        self._started = False
        logger.info("Live broadcasting service stopped")

    # ── DB refresh ────────────────────────────────────────────

    async def _db_refresh_loop(self) -> None:
        """Periodically load matches from DB into cache."""
        while True:
            try:
                await asyncio.sleep(_MATCH_REFRESH_INTERVAL)
                await self._load_matches_from_db()
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Error in DB refresh loop")
                await asyncio.sleep(30)

    async def _load_matches_from_db(self) -> None:
        """Load all live + recent finished matches from DB into LiveCache."""
        from katrain.web.core.models_db import LiveMatchDB

        try:
            with SessionLocal() as db:
                db_matches = db.query(LiveMatchDB).all()

                matches = []
                for row in db_matches:
                    match = _db_match_to_model(row)
                    if match:
                        matches.append(match)

            await self.cache.update_matches(matches)
        except Exception:
            logger.exception("Failed to load matches from DB")

    async def _cache_cleanup_loop(self) -> None:
        """Periodically clean up expired cache entries."""
        while True:
            try:
                await asyncio.sleep(_CLEANUP_INTERVAL)
                await self.cache.cleanup()
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Error in cache cleanup loop")

    # ── Read-only query methods ───────────────────────────────

    async def get_match_analysis(self, match_id: str) -> dict[int, MoveAnalysis]:
        """Get all completed analysis for a match from the database."""
        from katrain.web.live.analysis_repo import LiveAnalysisRepo

        with SessionLocal() as db:
            repo = LiveAnalysisRepo(db)
            return repo.get_successful_analysis(match_id)

    async def preload_analysis(self, match_id: str) -> dict[int, MoveAnalysis]:
        """Preload analysis for a match when user enters the page.

        Read-only: returns completed analysis from DB.
        Priority boosting is handled by katrain-cron.
        """
        return await self.get_match_analysis(match_id)

    async def get_analysis_stats(self) -> dict:
        """Get statistics about the analysis system."""
        from katrain.web.live.analysis_repo import LiveAnalysisRepo

        stats = {
            "queue_size": 0,
            "by_status": {},
        }

        try:
            with SessionLocal() as db:
                repo = LiveAnalysisRepo(db)
                stats["queue_size"] = repo.get_queue_size()
                stats["by_status"] = repo.get_analysis_stats()
        except Exception:
            logger.exception("Error getting analysis stats")

        return stats

    @property
    def is_running(self) -> bool:
        """Check if the service is running."""
        return self._started


def create_live_service(config: Optional[LiveConfig] = None) -> LiveService:
    """Factory function to create a LiveService instance."""
    return LiveService(config=config)


def _db_match_to_model(row) -> Optional[LiveMatch]:
    """Convert a LiveMatchDB row to a LiveMatch pydantic model."""
    try:
        source = MatchSource(row.source) if row.source in MatchSource.__members__.values() else MatchSource.XINGZHEN
        status = MatchStatus.LIVE if row.status == "live" else MatchStatus.FINISHED

        return LiveMatch(
            id=row.match_id,
            source=source,
            source_id=row.source_id or "",
            tournament=row.tournament or "",
            round_name=row.round_name,
            date=row.match_date or datetime.now(timezone.utc),
            player_black=row.player_black or "",
            player_white=row.player_white or "",
            black_rank=row.black_rank,
            white_rank=row.white_rank,
            status=status,
            result=row.result,
            move_count=row.move_count or 0,
            current_winrate=row.current_winrate or 0.5,
            current_score=row.current_score or 0.0,
            katago_winrate=row.katago_winrate,
            katago_score=row.katago_score,
            sgf=row.sgf_content,
            moves=list(row.moves) if row.moves else [],
            last_updated=row.updated_at or row.created_at or datetime.now(timezone.utc),
            board_size=row.board_size or 19,
            komi=row.komi if row.komi is not None else 7.5,
            rules=row.rules or "chinese",
        )
    except Exception:
        logger.exception("Failed to convert DB match %s", getattr(row, "match_id", "?"))
        return None
