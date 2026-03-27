"""FetchListJob: pull match list from multiple sources into DB."""

import logging
from datetime import datetime

from katrain.cron import config
from katrain.cron.jobs.base import BaseJob
from katrain.cron.clients.registry import SourceRegistry
from katrain.cron.db import SessionLocal
from katrain.cron.models import LiveMatchDB

logger = logging.getLogger("katrain_cron.fetch_list")

# When the same match appears from multiple sources, prefer the higher-priority source
SOURCE_PRIORITY = {"xingzhen": 0, "yike": 1}


class FetchListJob(BaseJob):
    name = "fetch_list"
    interval_seconds = 60

    async def run(self) -> None:
        registry = self._build_registry()
        if not registry.sources:
            self.logger.warning("No sources enabled, skipping FetchListJob")
            return

        all_rows = await registry.fetch_all_matches()
        if not all_rows:
            self.logger.debug("No matches returned from any source")
            return

        # Deduplicate within this batch
        all_rows = _deduplicate(all_rows)

        db = SessionLocal()
        try:
            upserted = 0
            skipped = 0
            for row in all_rows:
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
                    upserted += 1
                else:
                    # DB-level dedup: skip if same match already exists from a higher-priority source
                    dup = (
                        db.query(LiveMatchDB)
                        .filter(
                            LiveMatchDB.player_black == row["player_black"],
                            LiveMatchDB.player_white == row["player_white"],
                            LiveMatchDB.source != row["source"],
                        )
                        .first()
                    )
                    if dup and SOURCE_PRIORITY.get(dup.source, 99) <= SOURCE_PRIORITY.get(row["source"], 99):
                        skipped += 1
                        continue
                    elif dup:
                        # New row has higher priority — remove the old one
                        db.delete(dup)
                    db.add(LiveMatchDB(**row))
                    upserted += 1

            db.commit()
            self.logger.info(
                "FetchListJob: upserted %d, skipped %d dups (sources: %s)",
                upserted, skipped, ", ".join(registry.sources),
            )
        except Exception:
            db.rollback()
            self.logger.exception("FetchListJob failed")
        finally:
            db.close()

    @staticmethod
    def _build_registry() -> SourceRegistry:
        registry = SourceRegistry()
        if config.YIKE_ENABLED:
            from katrain.cron.clients.yike import YikeWeiQiClient
            registry.register("yike", YikeWeiQiClient())
        if config.XINGZHEN_ENABLED:
            from katrain.cron.clients.xingzhen import XingZhenClient
            registry.register("xingzhen", XingZhenClient())
        return registry


def _deduplicate(rows: list[dict]) -> list[dict]:
    """Keep preferred source when the same match appears from multiple sources.

    Dedup key: (player_black, player_white, match_date as date).
    Priority: yike > xingzhen.
    """
    by_key: dict[tuple, dict] = {}
    for row in rows:
        date_part = row["match_date"].date() if isinstance(row["match_date"], datetime) else row["match_date"]
        key = (row["player_black"], row["player_white"], date_part)
        existing = by_key.get(key)
        if existing is None or SOURCE_PRIORITY.get(row["source"], 99) < SOURCE_PRIORITY.get(existing["source"], 99):
            by_key[key] = row
    return list(by_key.values())
