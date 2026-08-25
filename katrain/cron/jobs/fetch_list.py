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

        all_rows, live_ids_by_source = await registry.fetch_all_matches_with_liveness()

        # NOTE: no early `return` when `all_rows` is empty. An empty upstream is a real
        # answer ("nothing is live"), and acting on it is the whole point of the demotion
        # pass below — bailing out here is what left finished games sitting in 正在直播
        # for weeks (upstream reported 0 live while the page still showed 49).
        if not all_rows:
            self.logger.debug("No matches returned from any source")

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
                        # New row has higher priority — remove the old one.
                        #
                        # 但旧行可能已经被 `live_analysis.match_id` 外键引用，删就报
                        # ForeignKeyViolation。那个错在 `db.commit()` 时才炸，会把**整轮**
                        # 一起回滚 —— 包括下面的降级。测试机上实测：
                        # "update or delete on table live_matches violates foreign key
                        #  constraint live_analysis_match_id_fkey"，于是 fetch_list 每轮
                        # 都报 FetchListJob failed，降级写进去又被回滚掉。
                        # 放进 savepoint：删不掉就退回「跳过这条新行」，不连累这一轮。
                        try:
                            with db.begin_nested():
                                db.delete(dup)
                                db.flush()
                        except Exception:
                            self.logger.warning(
                                "FetchListJob: %s 仍被引用，删不掉，跳过来自 %s 的重复行",
                                dup.match_id,
                                row["source"],
                            )
                            skipped += 1
                            continue
                    db.add(LiveMatchDB(**row))
                    upserted += 1

            demoted = _demote_matches_no_longer_live(db, live_ids_by_source, self.logger)

            db.commit()
            self.logger.info(
                "FetchListJob: upserted %d, skipped %d dups, demoted %d (sources: %s)",
                upserted,
                skipped,
                demoted,
                ", ".join(registry.sources),
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


def _demote_matches_no_longer_live(db, live_ids_by_source: dict[str, set[str]], logger) -> int:
    """Mark rows still flagged ``live`` that their source no longer lists as live.

    Only sources **present** in ``live_ids_by_source`` are touched: a missing key means the
    live query failed this round, and a failed request says nothing about whether a game is
    still being played. Demoting on failure would wipe the live list every time the upstream
    hiccups — the mirror image of the bug this function fixes.

    Nothing here is destructive: if the match shows up as live again, the upsert above puts
    ``status`` back, so a flaky upstream self-corrects on the next round.
    """
    demoted = 0
    for source_name, live_ids in live_ids_by_source.items():
        query = db.query(LiveMatchDB).filter(
            LiveMatchDB.source == source_name,
            LiveMatchDB.status == "live",
        )
        if live_ids:
            query = query.filter(~LiveMatchDB.match_id.in_(live_ids))
        stale = query.all()
        for match in stale:
            match.status = "finished"
            demoted += 1
        if stale:
            logger.info(
                "FetchListJob: %s no longer lists %d match(es) as live, marked finished",
                source_name,
                len(stale),
            )
    return demoted
