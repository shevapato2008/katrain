"""PandanetPollJob: poll Pandanet-IGS for professional game relays.

Connects via TCP, lists games, filters for professional (type=P),
fetches moves and upserts to DB. Runs as an independent job since
Pandanet uses a persistent TCP connection (not HTTP like other sources).
"""

import logging

from katrain.cron import config
from katrain.cron.jobs.base import BaseJob
from katrain.cron.clients.pandanet import PandanetClient
from katrain.cron.db import SessionLocal
from katrain.cron.models import LiveMatchDB, PRIORITY_LIVE_NEW, PRIORITY_LIVE_BACKFILL
from katrain.cron.analysis_repo import AnalysisRepo

logger = logging.getLogger("katrain_cron.poll_pandanet")


class PandanetPollJob(BaseJob):
    name = "poll_pandanet"
    interval_seconds = 300  # Check every 5 minutes

    async def run(self) -> None:
        client = PandanetClient()
        try:
            await client.connect()
            games = await client.get_games()
            # Filter for professional matches only (type=P)
            pro_games = [g for g in games if g.get("type") == "P"]

            if not pro_games:
                self.logger.debug("No professional games on Pandanet-IGS")
                return

            self.logger.info("Found %d professional games on Pandanet-IGS", len(pro_games))

            db = SessionLocal()
            try:
                repo = AnalysisRepo(db)
                for game in pro_games:
                    await self._process_game(client, repo, game, db)
            except Exception:
                db.rollback()
                self.logger.exception("PandanetPollJob DB error")
            finally:
                db.close()
        except Exception:
            self.logger.exception("PandanetPollJob connection error")
        finally:
            await client.disconnect()

    async def _process_game(self, client: PandanetClient, repo: AnalysisRepo, game: dict, db) -> None:
        """Fetch moves for a game and upsert to DB."""
        moves = await client.get_moves(game["id"])
        row = PandanetClient.parse_match_to_row(game, moves)
        if not row:
            return

        existing = db.query(LiveMatchDB).filter(LiveMatchDB.match_id == row["match_id"]).first()
        if existing:
            old_count = len(existing.moves) if existing.moves else 0
            new_count = len(moves)

            # Update moves if we have more
            if moves and new_count > old_count:
                existing.moves = moves
                existing.move_count = new_count
                db.commit()

                # Create analysis tasks for new moves
                start = 0 if old_count == 0 else old_count + 1
                new_move_nums = list(range(start, new_count + 1))
                repo.create_pending(existing.match_id, new_move_nums, PRIORITY_LIVE_NEW, moves)
                self.logger.info(
                    "Pandanet %s: %d -> %d moves (%d new tasks)",
                    existing.match_id, old_count, new_count, len(new_move_nums),
                )
        else:
            db.add(LiveMatchDB(**row))
            db.commit()

            # Create initial analysis tasks
            if moves:
                move_nums = list(range(0, len(moves) + 1))
                repo.create_pending(row["match_id"], move_nums, PRIORITY_LIVE_NEW, moves)

            self.logger.info(
                "New Pandanet match: %s (%s vs %s, %d moves)",
                row["match_id"], row["player_black"], row["player_white"], len(moves),
            )
