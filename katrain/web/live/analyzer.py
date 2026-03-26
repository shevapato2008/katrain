"""KataGo analysis integration for live matches.

This module provides KataGo analysis for live match positions,
storing results in PostgreSQL for persistence and caching.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional, Callable

import httpx

from katrain.web.core.db import SessionLocal
from katrain.web.live.models import LiveConfig, LiveMatch, MoveAnalysis, TopMove
from katrain.web.live.analysis_repo import (
    LiveAnalysisRepo,
    PRIORITY_LIVE_NEW,
    PRIORITY_USER_VIEW,
    PRIORITY_LIVE_BACKFILL,
    PRIORITY_FINISHED,
)

logger = logging.getLogger("katrain_web.live.analyzer")


# Column letters for Go coordinates (skip I)
COORD_LETTERS = "ABCDEFGHJKLMNOPQRSTUVWXYZ"


def move_to_gtp(move: str) -> str:
    """Convert display coordinate (e.g., 'Q16') to GTP format.

    Display format: Q16 (column letter + row number, 1-indexed from bottom)
    GTP format: Q16 (same format, but we ensure uppercase)
    """
    if not move or move.lower() == "pass":
        return "pass"
    return move.upper()


def gtp_to_display(gtp: str, board_size: int = 19) -> str:
    """Convert GTP coordinate to display format.

    In GTP, row 1 is at the bottom, which matches Go convention.
    """
    if not gtp or gtp.lower() == "pass":
        return "pass"
    return gtp.upper()


class LiveAnalyzer:
    """Analyzes live match positions using KataGo with DB persistence.

    Features:
    - Async HTTP requests to KataGo server
    - PostgreSQL persistence for analysis results
    - Priority-based queue processing
    - Automatic move classification (brilliant/mistake/questionable)
    - Background analysis loop with retry mechanism
    """

    def __init__(
        self,
        config: Optional[LiveConfig] = None,
        katago_url: Optional[str] = None,
    ):
        self.config = config or LiveConfig()

        # KataGo HTTP endpoint
        self.katago_url = katago_url or "http://127.0.0.1:8000"
        self.analyze_path = "/analyze"
        self.timeout = 60.0  # Analysis can take time

        # Analysis state
        self._running = False
        self._task: Optional[asyncio.Task] = None

        # Callbacks
        self._on_analysis_complete: Optional[Callable[[str, int, MoveAnalysis], None]] = None

        # Cache for match data (to avoid DB lookups for move data)
        self._match_cache: dict[str, LiveMatch] = {}

    def set_on_analysis_complete(
        self, callback: Callable[[str, int, MoveAnalysis], None]
    ) -> None:
        """Set callback for when analysis completes.

        Args:
            callback: Function(match_id, move_number, analysis) called when done
        """
        self._on_analysis_complete = callback

    def update_match_cache(self, match: LiveMatch) -> None:
        """Update the match cache with latest match data."""
        self._match_cache[match.id] = match

    async def start(self) -> None:
        """Start the analyzer background task."""
        if self._running:
            logger.warning("Analyzer already running")
            return

        # Reset any stale "running" tasks to "pending" (from previous crash/restart)
        self._reset_stale_running_tasks()

        self._running = True
        self._task = asyncio.create_task(self._analysis_loop())
        logger.info(f"Live analyzer started, using KataGo at {self.katago_url}")

    def _reset_stale_running_tasks(self) -> None:
        """Reset any tasks stuck in 'running' state back to 'pending'.

        This handles the case where the service was killed while tasks were running.
        """
        try:
            with SessionLocal() as db:
                from katrain.web.core.models_db import LiveAnalysisDB, AnalysisStatusEnum

                updated = db.query(LiveAnalysisDB).filter(
                    LiveAnalysisDB.status == AnalysisStatusEnum.RUNNING.value
                ).update({
                    LiveAnalysisDB.status: AnalysisStatusEnum.PENDING.value
                })

                if updated > 0:
                    db.commit()
                    logger.info(f"Reset {updated} stale 'running' tasks to 'pending'")
        except Exception as e:
            logger.error(f"Failed to reset stale running tasks: {e}")

    async def stop(self) -> None:
        """Stop the analyzer."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Live analyzer stopped")

    async def request_analysis(
        self,
        match_id: str,
        move_range: tuple[int, int],
        priority: int = PRIORITY_LIVE_NEW,
    ) -> int:
        """Request analysis for a range of moves.

        Args:
            match_id: The match to analyze
            move_range: (start_move, end_move) inclusive
            priority: Priority level for the analysis tasks

        Returns:
            Number of new analysis tasks created
        """
        start_move, end_move = move_range
        move_numbers = list(range(start_move, end_move + 1))

        # Get moves from cache if available
        moves = None
        if match_id in self._match_cache:
            moves = self._match_cache[match_id].moves

        # Create pending analysis records in DB
        with SessionLocal() as db:
            repo = LiveAnalysisRepo(db)
            created = repo.create_pending_analysis(
                match_id=match_id,
                move_numbers=move_numbers,
                priority=priority,
                moves=moves,
            )
            return len(created)

    async def request_new_move_analysis(
        self,
        match: LiveMatch,
        move_number: int,
    ) -> None:
        """Request analysis for a newly played move with high priority.

        This is called when the poller detects a new move in a live game.
        """
        self.update_match_cache(match)

        # Create pending records for this move and previous (for delta calculation)
        moves_to_analyze = [move_number]
        if move_number > 0:
            moves_to_analyze.append(move_number - 1)

        with SessionLocal() as db:
            repo = LiveAnalysisRepo(db)
            repo.create_pending_analysis(
                match_id=match.id,
                move_numbers=moves_to_analyze,
                priority=PRIORITY_LIVE_NEW,
                moves=match.moves,
            )

    async def boost_user_view_priority(
        self,
        match_id: str,
        move_numbers: list[int],
    ) -> int:
        """Boost priority for moves the user is viewing.

        Args:
            match_id: The match ID
            move_numbers: List of move numbers user is viewing

        Returns:
            Number of records updated
        """
        with SessionLocal() as db:
            repo = LiveAnalysisRepo(db)
            return repo.boost_priority(match_id, move_numbers, PRIORITY_USER_VIEW)

    async def get_queue_size(self) -> int:
        """Get current analysis queue size."""
        with SessionLocal() as db:
            repo = LiveAnalysisRepo(db)
            return repo.get_queue_size()

    async def get_match_analysis(self, match_id: str) -> dict[int, MoveAnalysis]:
        """Get all successful analysis for a match."""
        with SessionLocal() as db:
            repo = LiveAnalysisRepo(db)
            return repo.get_successful_analysis(match_id)

    async def _analysis_loop(self) -> None:
        """Background loop processing pending analysis from DB."""
        while self._running:
            try:
                # Get pending analysis tasks from DB
                with SessionLocal() as db:
                    repo = LiveAnalysisRepo(db)
                    pending = repo.get_pending_analysis(limit=1)

                if not pending:
                    # No work, sleep briefly
                    await asyncio.sleep(self.config.analysis_interval)
                    continue

                record = pending[0]
                match_id = record.match_id
                move_number = record.move_number

                # Get match data from cache or DB
                match = self._match_cache.get(match_id)
                if not match:
                    # Try to get from DB
                    with SessionLocal() as db:
                        repo = LiveAnalysisRepo(db)
                        db_match = repo.get_match(match_id)
                        if db_match and db_match.moves:
                            # Reconstruct minimal match object for analysis
                            from katrain.web.live.models import MatchSource, MatchStatus
                            match = LiveMatch(
                                id=db_match.match_id,
                                source=MatchSource(db_match.source),
                                source_id=db_match.source_id,
                                tournament=db_match.tournament,
                                round_name=db_match.round_name,
                                date=db_match.match_date or datetime.now(timezone.utc),
                                player_black=db_match.player_black,
                                player_white=db_match.player_white,
                                black_rank=db_match.black_rank,
                                white_rank=db_match.white_rank,
                                status=MatchStatus(db_match.status),
                                result=db_match.result,
                                move_count=db_match.move_count,
                                moves=db_match.moves or [],
                                board_size=db_match.board_size or 19,
                                komi=db_match.komi or 7.5,
                                rules=db_match.rules or "chinese",
                            )
                            self._match_cache[match_id] = match

                if not match or not match.moves:
                    logger.warning(f"Cannot find match data for {match_id}")
                    with SessionLocal() as db:
                        repo = LiveAnalysisRepo(db)
                        # Use max_retries=1 to fail immediately for missing match data
                        # (no point retrying if the match doesn't exist in source)
                        repo.mark_failed(match_id, move_number, "Match data not found", max_retries=1)
                    continue

                # Mark as running
                with SessionLocal() as db:
                    repo = LiveAnalysisRepo(db)
                    repo.mark_running(match_id, move_number)

                # Perform analysis
                try:
                    analysis = await self._analyze_position(match, move_number)
                    if analysis:
                        # Store result in DB
                        with SessionLocal() as db:
                            repo = LiveAnalysisRepo(db)
                            top_moves_dicts = [
                                {
                                    "move": tm.move,
                                    "visits": tm.visits,
                                    "winrate": tm.winrate,
                                    "score_lead": tm.score_lead,
                                    "prior": tm.prior,
                                    "pv": tm.pv,
                                    "psv": tm.psv,  # playSelectionValue for ranking
                                }
                                for tm in analysis.top_moves
                            ]
                            repo.update_analysis_result(
                                match_id=match_id,
                                move_number=move_number,
                                winrate=analysis.winrate,
                                score_lead=analysis.score_lead,
                                top_moves=top_moves_dicts,
                                ownership=analysis.ownership,
                                delta_score=analysis.delta_score,
                                delta_winrate=analysis.delta_winrate,
                                is_brilliant=analysis.is_brilliant,
                                is_mistake=analysis.is_mistake,
                                is_questionable=analysis.is_questionable,
                            )

                            # Update match's KataGo stats if this is the latest move
                            if match and move_number == match.move_count:
                                repo.update_katago_stats(
                                    match_id=match_id,
                                    winrate=analysis.winrate,
                                    score=analysis.score_lead,
                                )

                        # Trigger callback
                        if self._on_analysis_complete:
                            try:
                                self._on_analysis_complete(match_id, move_number, analysis)
                            except Exception as e:
                                logger.error(f"Error in analysis callback: {e}")

                        logger.debug(f"Analysis complete: {match_id} move {move_number}")
                    else:
                        with SessionLocal() as db:
                            repo = LiveAnalysisRepo(db)
                            repo.mark_failed(match_id, move_number, "Analysis returned None")

                except Exception as e:
                    logger.error(f"Analysis failed for {match_id} move {move_number}: {e}")
                    with SessionLocal() as db:
                        repo = LiveAnalysisRepo(db)
                        repo.mark_failed(match_id, move_number, str(e))
                    await asyncio.sleep(1)  # Brief pause before next attempt

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in analysis loop: {e}")
                await asyncio.sleep(1)

    async def _analyze_position(
        self,
        match: LiveMatch,
        move_number: int,
    ) -> Optional[MoveAnalysis]:
        """Analyze a single position using KataGo.

        Args:
            match: The match containing moves
            move_number: Position to analyze (moves 0..move_number-1 played)

        Returns:
            MoveAnalysis with results, or None if failed
        """
        if not match.moves and move_number > 0:
            return None

        # Get game parameters from match data
        board_size = getattr(match, 'board_size', 19) or 19
        komi = getattr(match, 'komi', 7.5) or 7.5
        rules = getattr(match, 'rules', 'chinese') or 'chinese'

        # Build moves list up to the position
        moves_played = match.moves[:move_number] if match.moves else []

        # Build GTP move list with alternating colors
        gtp_moves = []
        for i, move in enumerate(moves_played):
            player = "B" if i % 2 == 0 else "W"
            gtp = move_to_gtp(move)
            if gtp.lower() != "pass":
                gtp_moves.append([player, gtp])

        # Build analysis query with actual game rules and komi
        query = {
            "id": f"live_{match.id}_{move_number}",
            "rules": rules,
            "komi": komi,
            "boardXSize": board_size,
            "boardYSize": board_size,
            "analyzeTurns": [len(gtp_moves)],
            "maxVisits": self.config.analysis_max_visits,
            "initialStones": [],
            "initialPlayer": "B",
            "moves": gtp_moves,
            "includeOwnership": True,
            "includePolicy": True,
            "overrideSettings": {
                "reportAnalysisWinratesAs": "BLACK",
            },
        }

        # Send request
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.katago_url}{self.analyze_path}",
                    json=query,
                )
                response.raise_for_status()
                result = response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"KataGo HTTP error: {e.response.status_code}")
            return None
        except httpx.TimeoutException:
            logger.error("KataGo analysis timeout")
            return None
        except Exception as e:
            logger.error(f"KataGo connection error: {e}")
            return None

        # Parse response
        if "error" in result:
            logger.error(f"KataGo error: {result['error']}")
            return None

        root_info = result.get("rootInfo", {})
        move_infos = result.get("moveInfos", [])

        # Extract ownership and convert to 2D grid
        ownership_grid = None
        ownership_flat = result.get("ownership")
        if ownership_flat:
            # Convert flat array to 2D grid (row major, from top-left)
            # Note: Y-axis inversion for Go convention is handled in frontend
            ownership_grid = []
            for y in range(board_size):
                row = []
                for x in range(board_size):
                    idx = y * board_size + x
                    row.append(ownership_flat[idx] if idx < len(ownership_flat) else 0.0)
                ownership_grid.append(row)

        # Extract winrate and score
        winrate = root_info.get("winrate", 0.5)
        score_lead = root_info.get("scoreLead", 0.0)

        # Build top moves
        top_moves = []
        for mi in move_infos[:10]:  # Top 10 moves
            gtp_move = mi.get("move", "")
            top_moves.append(TopMove(
                move=gtp_to_display(gtp_move, board_size),
                visits=mi.get("visits", 0),
                winrate=mi.get("winrate", 0.5),
                score_lead=mi.get("scoreLead", 0.0),
                prior=mi.get("prior", 0.0),
                pv=[gtp_to_display(m, board_size) for m in mi.get("pv", [])],
                psv=mi.get("playSelectionValue", 0.0),  # KataGo's composite ranking metric
            ))

        # Get the actual move played (if this isn't the latest position)
        actual_move = None
        actual_player = None
        if move_number < len(match.moves):
            actual_move = match.moves[move_number]
            actual_player = "B" if move_number % 2 == 0 else "W"

        # Calculate delta from previous position
        delta_score = 0.0
        delta_winrate = 0.0

        # Try to get previous analysis from DB for delta calculation
        with SessionLocal() as db:
            repo = LiveAnalysisRepo(db)
            prev_analysis = repo.get_analysis(match.id, move_number - 1) if move_number > 0 else None
            if prev_analysis and prev_analysis.winrate is not None:
                # Score is from Black's perspective
                # For Black moves, gain = current - previous
                # For White moves, gain = previous - current (since White wants lower Black score)
                if actual_player == "B":
                    delta_score = score_lead - (prev_analysis.score_lead or 0)
                    delta_winrate = winrate - (prev_analysis.winrate or 0.5)
                else:
                    delta_score = (prev_analysis.score_lead or 0) - score_lead
                    delta_winrate = (prev_analysis.winrate or 0.5) - winrate

        # Classify the move
        classification = MoveAnalysis.classify_move(
            delta_score,
            brilliant_threshold=self.config.brilliant_threshold,
            mistake_threshold=self.config.mistake_threshold,
            questionable_threshold=self.config.questionable_threshold,
        )

        return MoveAnalysis(
            match_id=match.id,
            move_number=move_number,
            move=actual_move,
            player=actual_player,
            winrate=winrate,
            score_lead=score_lead,
            top_moves=top_moves,
            ownership=ownership_grid,
            delta_score=delta_score,
            delta_winrate=delta_winrate,
            **classification,
        )

    async def schedule_match_analysis(
        self,
        match: LiveMatch,
        priority: int = PRIORITY_FINISHED,
    ) -> int:
        """Schedule analysis for all unanalyzed moves in a match.

        Args:
            match: The match to analyze
            priority: Priority level for the analysis tasks

        Returns:
            Number of new analysis tasks created
        """
        self.update_match_cache(match)

        with SessionLocal() as db:
            repo = LiveAnalysisRepo(db)
            # First ensure match exists in DB
            repo.get_or_create_match(match)

            # Find unanalyzed moves
            unanalyzed = repo.get_unanalyzed_moves(match.id, match.move_count)

            if not unanalyzed:
                return 0

            # Create pending records
            created = repo.create_pending_analysis(
                match_id=match.id,
                move_numbers=unanalyzed,
                priority=priority,
                moves=match.moves,
            )
            return len(created)
