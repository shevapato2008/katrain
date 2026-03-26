"""FetchListJob: pull match list from XingZhen API into DB."""

import logging
from datetime import datetime

from katrain.cron.jobs.base import BaseJob
from katrain.cron.clients.xingzhen import XingZhenClient
from katrain.cron.db import SessionLocal
from katrain.cron.models import LiveMatchDB

logger = logging.getLogger("katrain_cron.fetch_list")


class FetchListJob(BaseJob):
    name = "fetch_list"
    interval_seconds = 60

    async def run(self) -> None:
        client = XingZhenClient()

        # Fetch live + recent history
        live_raw = await client.get_live_matches()
        history_raw = await client.get_history(page=0, size=20)
        all_raw = live_raw + history_raw

        if not all_raw:
            self.logger.debug("No matches returned from XingZhen")
            return

        db = SessionLocal()
        try:
            upserted = 0
            for raw in all_raw:
                row = XingZhenClient.parse_match_to_row(raw)
                if row is None:
                    continue
                existing = db.query(LiveMatchDB).filter(LiveMatchDB.match_id == row["match_id"]).first()
                if existing:
                    # Update mutable fields
                    existing.status = row["status"]
                    existing.result = row.get("result")
                    existing.move_count = row["move_count"]
                    existing.current_winrate = row["current_winrate"]
                    existing.current_score = row["current_score"]
                    if row["moves"]:
                        existing.moves = row["moves"]
                else:
                    db.add(LiveMatchDB(**row))
                upserted += 1

            db.commit()
            self.logger.info("FetchListJob: upserted %d matches from %d raw records", upserted, len(all_raw))
        except Exception:
            db.rollback()
            self.logger.exception("FetchListJob failed")
        finally:
            db.close()
