"""In-memory cache for live match data."""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from katrain.web.live.models import LiveMatch, MatchStatus, MoveAnalysis, UpcomingMatch

logger = logging.getLogger("katrain_web.live.cache")


class LiveCache:
    """Thread-safe in-memory cache for live match data.

    Stores:
    - Currently live matches (refreshed frequently)
    - Recent finished matches (kept for a configurable period)
    - Upcoming match schedule
    """

    def __init__(
        self,
        max_live_matches: int = 100,
        max_finished_matches: int = 200,
        finished_retention_hours: int = 168,  # 7 days
    ):
        self.max_live_matches = max_live_matches
        self.max_finished_matches = max_finished_matches
        self.finished_retention = timedelta(hours=finished_retention_hours)

        self._lock = asyncio.Lock()

        # Match storage: id -> LiveMatch
        self._live_matches: dict[str, LiveMatch] = {}
        self._finished_matches: dict[str, LiveMatch] = {}

        # Upcoming matches
        self._upcoming: list[UpcomingMatch] = []

        # Featured match (most important live match)
        self._featured_match_id: Optional[str] = None

        # Timestamps
        self._last_list_update: Optional[datetime] = None
        self._last_cleanup: Optional[datetime] = None

    async def get_live_matches(self) -> list[LiveMatch]:
        """Get all currently live matches, sorted by importance/date."""
        async with self._lock:
            matches = list(self._live_matches.values())
        # Sort: featured first, then by move count (more active), then by date
        return sorted(matches, key=lambda m: (m.id != self._featured_match_id, -m.move_count, m.date), reverse=False)

    async def get_finished_matches(self, limit: int = 50) -> list[LiveMatch]:
        """Get recent finished matches, sorted by date (newest first)."""
        async with self._lock:
            matches = list(self._finished_matches.values())
        matches.sort(key=lambda m: m.date, reverse=True)
        return matches[:limit]

    async def get_all_matches(self, limit: int = 100) -> list[LiveMatch]:
        """Get all matches (live first, then finished), sorted appropriately."""
        live = await self.get_live_matches()
        finished = await self.get_finished_matches(limit=limit - len(live))
        return live + finished

    async def get_match(self, match_id: str) -> Optional[LiveMatch]:
        """Get a specific match by ID."""
        async with self._lock:
            if match_id in self._live_matches:
                return self._live_matches[match_id]
            return self._finished_matches.get(match_id)

    async def get_featured_match(self) -> Optional[LiveMatch]:
        """Get the current featured match (most important live match)."""
        if self._featured_match_id:
            return await self.get_match(self._featured_match_id)

        # Fall back to first live match or most recent finished
        live = await self.get_live_matches()
        if live:
            return live[0]

        finished = await self.get_finished_matches(limit=1)
        if finished:
            return finished[0]

        return None

    async def set_featured_match(self, match_id: str) -> None:
        """Set the featured match ID."""
        self._featured_match_id = match_id

    async def update_match(self, match: LiveMatch) -> None:
        """Update or insert a match into the cache."""
        async with self._lock:
            if match.status == MatchStatus.LIVE:
                self._live_matches[match.id] = match
                # If it was previously in finished, remove it
                self._finished_matches.pop(match.id, None)
            else:
                self._finished_matches[match.id] = match
                # If it was previously live, remove it
                self._live_matches.pop(match.id, None)

    async def update_matches(self, matches: list[LiveMatch]) -> None:
        """Bulk update matches."""
        async with self._lock:
            for match in matches:
                if match.status == MatchStatus.LIVE:
                    self._live_matches[match.id] = match
                    self._finished_matches.pop(match.id, None)
                else:
                    self._finished_matches[match.id] = match
                    self._live_matches.pop(match.id, None)

            self._last_list_update = datetime.now(timezone.utc)

    async def mark_match_finished(self, match_id: str, result: Optional[str] = None) -> None:
        """Mark a live match as finished and move it to finished cache."""
        async with self._lock:
            if match_id in self._live_matches:
                match = self._live_matches.pop(match_id)
                match.status = MatchStatus.FINISHED
                if result:
                    match.result = result
                match.last_updated = datetime.now(timezone.utc)
                self._finished_matches[match.id] = match

                # Clear featured if it was this match
                if self._featured_match_id == match_id:
                    self._featured_match_id = None

    async def get_upcoming(self) -> list[UpcomingMatch]:
        """Get upcoming matches."""
        async with self._lock:
            # Filter out past matches
            now = datetime.now(timezone.utc)
            return [m for m in self._upcoming if m.scheduled_time > now]

    async def set_upcoming(self, matches: list[UpcomingMatch]) -> None:
        """Set the upcoming matches list."""
        async with self._lock:
            self._upcoming = sorted(matches, key=lambda m: m.scheduled_time)

    async def cleanup(self) -> int:
        """Remove expired finished matches and enforce limits.

        Returns:
            Number of matches removed
        """
        removed = 0
        now = datetime.now(timezone.utc)
        cutoff = now - self.finished_retention

        async with self._lock:
            # Remove expired finished matches
            expired = [
                mid for mid, match in self._finished_matches.items()
                if match.last_updated < cutoff
            ]
            for mid in expired:
                del self._finished_matches[mid]
                removed += 1

            # Enforce max finished matches (keep newest)
            if len(self._finished_matches) > self.max_finished_matches:
                sorted_ids = sorted(
                    self._finished_matches.keys(),
                    key=lambda mid: self._finished_matches[mid].date,
                    reverse=True,
                )
                for mid in sorted_ids[self.max_finished_matches:]:
                    del self._finished_matches[mid]
                    removed += 1

            # Enforce max live matches (keep most active)
            if len(self._live_matches) > self.max_live_matches:
                sorted_ids = sorted(
                    self._live_matches.keys(),
                    key=lambda mid: self._live_matches[mid].move_count,
                    reverse=True,
                )
                for mid in sorted_ids[self.max_live_matches:]:
                    del self._live_matches[mid]
                    removed += 1

            self._last_cleanup = now

        if removed > 0:
            logger.info(f"Cache cleanup: removed {removed} matches")

        return removed

    async def get_stats(self) -> dict:
        """Get cache statistics."""
        async with self._lock:
            return {
                "live_count": len(self._live_matches),
                "finished_count": len(self._finished_matches),
                "upcoming_count": len(self._upcoming),
                "featured_id": self._featured_match_id,
                "last_list_update": self._last_list_update.isoformat() if self._last_list_update else None,
                "last_cleanup": self._last_cleanup.isoformat() if self._last_cleanup else None,
            }

    async def clear(self) -> None:
        """Clear all cached data."""
        async with self._lock:
            self._live_matches.clear()
            self._finished_matches.clear()
            self._upcoming.clear()
            self._featured_match_id = None
            self._last_list_update = None
            self._last_cleanup = None

    async def store_analysis(
        self, match_id: str, move_number: int, analysis: MoveAnalysis
    ) -> None:
        """Store analysis data for a specific move in a match.

        Args:
            match_id: The match ID
            move_number: The move number (0-indexed position)
            analysis: The analysis result
        """
        async with self._lock:
            # Find the match in either live or finished
            match = self._live_matches.get(match_id)
            if not match:
                match = self._finished_matches.get(match_id)

            if match:
                match.analysis[move_number] = analysis
                logger.debug(f"Stored analysis for {match_id} move {move_number}")

    async def get_analysis(
        self, match_id: str, move_number: Optional[int] = None
    ) -> dict:
        """Get analysis data for a match.

        Args:
            match_id: The match ID
            move_number: Specific move number, or None for all

        Returns:
            Dict of move_number -> MoveAnalysis if move_number is None,
            or single MoveAnalysis if move_number specified
        """
        async with self._lock:
            match = self._live_matches.get(match_id)
            if not match:
                match = self._finished_matches.get(match_id)

            if not match:
                return {}

            if move_number is not None:
                return match.analysis.get(move_number)

            return dict(match.analysis)

    async def get_analyzed_move_count(self, match_id: str) -> int:
        """Get the number of analyzed moves for a match."""
        async with self._lock:
            match = self._live_matches.get(match_id)
            if not match:
                match = self._finished_matches.get(match_id)

            if not match:
                return 0

            return len(match.analysis)
