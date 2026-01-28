"""PollMovesJob: poll live games for new moves, create pending analysis tasks."""

import logging

from katrain.cron.jobs.base import BaseJob
from katrain.cron.clients.xingzhen import XingZhenClient, _parse_moves
from katrain.cron.db import SessionLocal
from katrain.cron.models import LiveMatchDB, PRIORITY_LIVE_NEW, PRIORITY_LIVE_BACKFILL
from katrain.cron.analysis_repo import AnalysisRepo

logger = logging.getLogger("katrain_cron.poll_moves")


class PollMovesJob(BaseJob):
    name = "poll_moves"
    interval_seconds = 3

    async def run(self) -> None:
        db = SessionLocal()
        try:
            live_matches = db.query(LiveMatchDB).filter(LiveMatchDB.status == "live").all()
            if not live_matches:
                return

            client = XingZhenClient()
            repo = AnalysisRepo(db)

            for match in live_matches:
                await self._poll_one(client, repo, match, db)
        except Exception:
            db.rollback()
            self.logger.exception("PollMovesJob failed")
        finally:
            db.close()

    async def _poll_one(self, client: XingZhenClient, repo: AnalysisRepo, match: LiveMatchDB, db) -> None:
        situation = await client.get_situation(match.source_id)
        if not situation:
            return

        # Extract match data (may be nested under "liveMatch")
        md = situation.get("liveMatch", situation)
        new_status = "live" if md.get("liveStatus", 0) == 0 else "finished"

        # Parse moves
        moves_data = situation.get("moves") or md.get("moves") or md.get("moveList")
        new_moves = _parse_moves(moves_data)

        old_count = len(match.moves) if match.moves else 0
        old_status = match.status
        new_count = len(new_moves)

        # Update match record
        if new_moves:
            match.moves = new_moves
        match.move_count = new_count
        match.status = new_status
        match.result = md.get("gameResult") or md.get("result") or match.result

        wr = md.get("winrate")
        if wr is not None:
            match.current_winrate = wr
        sc = md.get("score") or md.get("blackScore")
        if sc is not None:
            match.current_score = sc

        db.commit()

        # Create analysis tasks for new moves
        if new_count > old_count:
            # New moves get highest priority
            new_move_nums = list(range(old_count + 1, new_count + 1))
            repo.create_pending(match.match_id, new_move_nums, PRIORITY_LIVE_NEW, new_moves)
            self.logger.info(
                "New moves for %s: %d -> %d (created %d tasks)",
                match.match_id, old_count, new_count, len(new_move_nums),
            )

        # When match transitions to finished, backfill any missing analysis
        if new_status == "finished" and old_status != "finished":
            all_nums = list(range(0, new_count + 1))
            created = repo.create_pending(match.match_id, all_nums, PRIORITY_LIVE_BACKFILL, new_moves)
            if created:
                self.logger.info("Backfill %d tasks for finished match %s", created, match.match_id)
