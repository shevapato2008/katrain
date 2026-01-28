"""Live match polling service.

Periodically fetches match data from external APIs and updates the cache.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Callable, Optional, TYPE_CHECKING

from katrain.web.core.db import SessionLocal
from katrain.web.live.cache import LiveCache
from katrain.web.live.clients import XingZhenClient, WeiqiOrgClient
from katrain.web.live.clients.upcoming import UpcomingScraper
from katrain.web.live.models import LiveConfig, LiveMatch, MatchStatus
from katrain.web.live.analysis_repo import LiveAnalysisRepo, PRIORITY_LIVE_NEW, PRIORITY_LIVE_BACKFILL

if TYPE_CHECKING:
    from katrain.web.live.analyzer import LiveAnalyzer

logger = logging.getLogger("katrain_web.live.poller")


class LivePoller:
    """Polling service for live match data.

    Features:
    - Periodic list refresh from both data sources
    - More frequent polling for active live matches
    - Automatic move detection and update
    - Callbacks for new moves (for triggering analysis)
    - Database persistence for matches
    """

    def __init__(
        self,
        cache: LiveCache,
        config: Optional[LiveConfig] = None,
        xingzhen_client: Optional[XingZhenClient] = None,
        weiqi_org_client: Optional[WeiqiOrgClient] = None,
    ):
        self.cache = cache
        self.config = config or LiveConfig()

        # Initialize clients
        self.xingzhen = xingzhen_client or XingZhenClient(
            base_url=self.config.xingzhen_api_base
        )
        self.weiqi_org = weiqi_org_client or WeiqiOrgClient(
            base_url=self.config.weiqi_org_api_base
        )

        # Upcoming events scraper
        self.upcoming_scraper = UpcomingScraper()

        # Polling state
        self._running = False
        self._tasks: list[asyncio.Task] = []

        # Analyzer reference (set by service)
        self._analyzer: Optional["LiveAnalyzer"] = None

        # Callbacks
        self._on_new_move: Optional[Callable[[LiveMatch, int], None]] = None
        self._on_match_end: Optional[Callable[[LiveMatch], None]] = None

    def set_analyzer(self, analyzer: "LiveAnalyzer") -> None:
        """Set the analyzer reference for triggering analysis on new moves."""
        self._analyzer = analyzer

    def set_on_new_move(self, callback: Callable[[LiveMatch, int], None]) -> None:
        """Set callback for when a new move is detected.

        Args:
            callback: Function(match, move_number) called when new move detected
        """
        self._on_new_move = callback

    def set_on_match_end(self, callback: Callable[[LiveMatch], None]) -> None:
        """Set callback for when a match ends.

        Args:
            callback: Function(match) called when match finishes
        """
        self._on_match_end = callback

    async def start(self) -> None:
        """Start the polling service."""
        if self._running:
            logger.warning("Poller already running")
            return

        self._running = True
        logger.info("Starting live poller")

        # Initial fetch
        await self._refresh_match_list()
        await self._refresh_upcoming()

        # Start background tasks
        self._tasks = [
            asyncio.create_task(self._list_poll_loop()),
            asyncio.create_task(self._live_poll_loop()),
            asyncio.create_task(self._cleanup_loop()),
            asyncio.create_task(self._upcoming_poll_loop()),
        ]

    async def stop(self) -> None:
        """Stop the polling service."""
        self._running = False

        for task in self._tasks:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        self._tasks.clear()
        logger.info("Live poller stopped")

    async def _list_poll_loop(self) -> None:
        """Background loop to refresh match list periodically."""
        while self._running:
            try:
                await asyncio.sleep(self.config.list_interval)
                await self._refresh_match_list()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in list poll loop: {e}")
                await asyncio.sleep(10)  # Brief pause before retry

    async def _live_poll_loop(self) -> None:
        """Background loop to poll live matches for new moves."""
        while self._running:
            try:
                await asyncio.sleep(self.config.moves_interval)
                await self._poll_live_matches()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in live poll loop: {e}")
                await asyncio.sleep(5)

    async def _cleanup_loop(self) -> None:
        """Background loop to clean up old cached data."""
        while self._running:
            try:
                await asyncio.sleep(3600)  # Every hour
                await self.cache.cleanup()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")

    async def _upcoming_poll_loop(self) -> None:
        """Background loop to refresh upcoming events periodically.

        Runs every 2 hours since tournament schedules don't change frequently.
        """
        while self._running:
            try:
                await asyncio.sleep(7200)  # Every 2 hours
                await self._refresh_upcoming()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in upcoming poll loop: {e}")
                await asyncio.sleep(300)  # 5 min pause before retry

    async def _refresh_upcoming(self) -> None:
        """Refresh upcoming events from official Go association websites."""
        logger.info("Refreshing upcoming events from official sources...")
        try:
            upcoming = await self.upcoming_scraper.fetch_all()
            if upcoming:
                await self.cache.set_upcoming(upcoming)
                logger.info(f"Updated cache with {len(upcoming)} upcoming events")
            else:
                logger.info("No upcoming events found from official sources")
        except Exception as e:
            logger.error(f"Failed to refresh upcoming events: {e}")

    async def _refresh_match_list(self) -> None:
        """Refresh the full match list from all sources."""
        logger.info("Refreshing match list from all sources...")
        all_matches: list[LiveMatch] = []

        # Fetch from XingZhen (live matches)
        if self.config.xingzhen_enabled:
            try:
                raw_live = await self.xingzhen.get_live_matches()
                for raw in raw_live:
                    try:
                        match = self.xingzhen.parse_match(raw)
                        if match:  # parse_match returns None for invalid data
                            all_matches.append(match)
                    except Exception as e:
                        logger.warning(f"Failed to parse XingZhen match: {e}")

                # Also get recent history
                raw_history = await self.xingzhen.get_history(page=0, size=30)
                for raw in raw_history:
                    try:
                        match = self.xingzhen.parse_match(raw)
                        # Skip None and avoid duplicates
                        if match and not any(m.id == match.id for m in all_matches):
                            all_matches.append(match)
                    except Exception as e:
                        logger.warning(f"Failed to parse XingZhen history match: {e}")

            except Exception as e:
                logger.error(f"Failed to fetch from XingZhen: {e}")

        # Fetch from weiqi.org (recent finished games)
        if self.config.weiqi_org_enabled:
            try:
                raw_list = await self.weiqi_org.get_battle_list(page_num=1, page_size=30)
                for raw in raw_list:
                    try:
                        match = self.weiqi_org.parse_match(raw)
                        # Avoid duplicates (unlikely since different sources)
                        if not any(m.id == match.id for m in all_matches):
                            all_matches.append(match)
                    except Exception as e:
                        logger.warning(f"Failed to parse WeiqiOrg match: {e}")
            except Exception as e:
                logger.error(f"Failed to fetch from WeiqiOrg: {e}")

        # Update cache
        if all_matches:
            await self.cache.update_matches(all_matches)
            live_count = sum(1 for m in all_matches if m.status == MatchStatus.LIVE)
            finished_count = len(all_matches) - live_count
            logger.info(f"Updated cache: {live_count} live, {finished_count} finished matches")

            # Persist matches to database
            await self._persist_matches(all_matches)

            # Set featured match (first live match, or most recent finished)
            live_matches = [m for m in all_matches if m.status == MatchStatus.LIVE]
            if live_matches:
                # Pick the one with most moves (most active)
                featured = max(live_matches, key=lambda m: m.move_count)
                await self.cache.set_featured_match(featured.id)
            else:
                # Pick most recent finished
                finished = [m for m in all_matches if m.status == MatchStatus.FINISHED]
                if finished:
                    featured = max(finished, key=lambda m: m.date)
                    await self.cache.set_featured_match(featured.id)

    async def _persist_matches(self, matches: list[LiveMatch]) -> None:
        """Persist matches to database.

        For new matches or matches without moves, fetches moves via /situation API.

        Args:
            matches: List of matches to persist
        """
        try:
            for match in matches:
                # Check if match needs moves data
                needs_moves = not match.moves or len(match.moves) == 0

                if needs_moves:
                    # Check if already in DB with moves
                    with SessionLocal() as db:
                        repo = LiveAnalysisRepo(db)
                        db_match = repo.get_match(match.id)
                        if db_match and db_match.moves and len(db_match.moves) > 0:
                            # DB already has moves, no need to fetch
                            needs_moves = False

                if needs_moves and match.source.value == "xingzhen":
                    # Fetch moves from /situation API
                    try:
                        situation = await self.xingzhen.get_situation(match.source_id)
                        if situation:
                            moves_data = situation.get("moves")
                            if moves_data:
                                if isinstance(moves_data, str):
                                    match.moves = self.xingzhen._parse_moves_string(moves_data)
                                elif isinstance(moves_data, list):
                                    match.moves = [str(m) for m in moves_data]
                                logger.info(f"Fetched {len(match.moves)} moves for {match.id}")
                    except Exception as e:
                        logger.warning(f"Failed to fetch moves for {match.id}: {e}")

                # Persist to database
                with SessionLocal() as db:
                    repo = LiveAnalysisRepo(db)
                    repo.get_or_create_match(match)

                # Update analyzer's cache if available (only if has moves)
                if self._analyzer and match.moves and len(match.moves) > 0:
                    self._analyzer.update_match_cache(match)

        except Exception as e:
            logger.error(f"Failed to persist matches: {e}")

    async def _poll_live_matches(self) -> None:
        """Poll live matches for new moves."""
        live_matches = await self.cache.get_live_matches()

        if live_matches:
            logger.debug(f"Polling {len(live_matches)} live matches for new moves")

        for match in live_matches:
            if match.source.value == "xingzhen":
                await self._poll_xingzhen_match(match)
            # Note: weiqi.org matches are always finished, no need to poll

    async def _poll_xingzhen_match(self, match: LiveMatch) -> None:
        """Poll a single XingZhen match for updates."""
        try:
            situation = await self.xingzhen.get_situation(match.source_id)
            if not situation:
                return

            # Check for new moves
            new_move_count = situation.get("moveNum") or situation.get("moveCount") or 0
            old_move_count = match.move_count

            if new_move_count > old_move_count:
                # New moves detected
                logger.info(f"New moves in {match.id}: {old_move_count} -> {new_move_count}")

                # Update match data
                match.move_count = new_move_count
                match.current_winrate = situation.get("winrate") or situation.get("blackWinrate") or match.current_winrate
                match.current_score = situation.get("score") or situation.get("blackScore") or match.current_score

                # Update moves list
                moves_data = situation.get("moves") or situation.get("moveList")
                if moves_data:
                    if isinstance(moves_data, str):
                        match.moves = self.xingzhen._parse_moves_string(moves_data)
                    elif isinstance(moves_data, list):
                        match.moves = [str(m) for m in moves_data]

                match.last_updated = datetime.now(timezone.utc)
                await self.cache.update_match(match)

                # Persist to database and trigger analysis
                await self._persist_and_analyze(match, old_move_count, new_move_count)

                # Trigger callback
                if self._on_new_move:
                    try:
                        self._on_new_move(match, new_move_count)
                    except Exception as e:
                        logger.error(f"Error in new move callback: {e}")

            # Check for match end
            status_code = situation.get("liveStatus")
            if status_code == 40:  # Finished
                result = situation.get("result") or situation.get("matchResult")
                await self.cache.mark_match_finished(match.id, result)

                if self._on_match_end:
                    # Refetch the updated match
                    updated_match = await self.cache.get_match(match.id)
                    if updated_match:
                        try:
                            self._on_match_end(updated_match)
                        except Exception as e:
                            logger.error(f"Error in match end callback: {e}")

        except Exception as e:
            logger.warning(f"Failed to poll match {match.id}: {e}")

    async def _persist_and_analyze(
        self,
        match: LiveMatch,
        old_move_count: int,
        new_move_count: int,
    ) -> None:
        """Persist match to database and create analysis tasks for new moves.

        Args:
            match: The updated match
            old_move_count: Previous move count
            new_move_count: New move count
        """
        try:
            with SessionLocal() as db:
                repo = LiveAnalysisRepo(db)

                # Persist or update match in database
                repo.get_or_create_match(match)

                # Create pending analysis for new moves (high priority for live)
                new_moves = list(range(old_move_count, new_move_count + 1))
                if new_moves:
                    repo.create_pending_analysis(
                        match_id=match.id,
                        move_numbers=new_moves,
                        priority=PRIORITY_LIVE_NEW,
                        moves=match.moves,
                    )
                    logger.info(f"[LIVE] Created {len(new_moves)} analysis tasks for {match.id} (moves {old_move_count}->{new_move_count})")

            # Update analyzer's match cache
            if self._analyzer:
                self._analyzer.update_match_cache(match)

        except Exception as e:
            logger.error(f"Failed to persist match {match.id}: {e}")

    async def fetch_match_detail(self, match_id: str) -> Optional[LiveMatch]:
        """Fetch detailed data for a specific match.

        This includes full SGF and moves list.
        """
        match = await self.cache.get_match(match_id)
        if not match:
            return None

        if match.source.value == "xingzhen":
            # Fetch situation for latest data
            # Response: {"liveMatch": {...}, "moves": "73,60,300,..."}
            situation = await self.xingzhen.get_situation(match.source_id)
            if situation:
                # Extract match info from liveMatch sub-object
                live_match_data = situation.get("liveMatch", {})
                match.move_count = live_match_data.get("moveNum") or match.move_count
                match.current_winrate = live_match_data.get("winrate") if live_match_data.get("winrate") is not None else match.current_winrate
                match.result = live_match_data.get("gameResult") or match.result

                # Extract moves from top-level "moves" field
                moves_data = situation.get("moves")
                if moves_data:
                    if isinstance(moves_data, str):
                        match.moves = self.xingzhen._parse_moves_string(moves_data)
                    elif isinstance(moves_data, list):
                        match.moves = [str(m) for m in moves_data]

            # Try to get SGF if available
            if not match.sgf:
                analysis = await self.xingzhen.get_analysis(match.source_id)
                if analysis and "sgf" in analysis:
                    match.sgf = analysis["sgf"]

        elif match.source.value == "weiqi_org":
            # Fetch detail with SGF
            detail = await self.weiqi_org.get_battle_detail(match.source_id)
            if detail:
                match = self.weiqi_org.parse_match({}, detail)
                await self.cache.update_match(match)

        match.last_updated = datetime.now(timezone.utc)
        await self.cache.update_match(match)
        return match

    async def force_refresh(self) -> None:
        """Force an immediate refresh of all match data."""
        await self._refresh_match_list()
