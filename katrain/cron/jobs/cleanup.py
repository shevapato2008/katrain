"""CleanupJob: periodic cleanup of old matches, analysis data, and expired upcoming events."""

import logging
from datetime import datetime, timedelta

from sqlalchemy import and_, text

from katrain.cron import config
from katrain.cron.jobs.base import BaseJob
from katrain.cron.db import SessionLocal
from katrain.cron.models import LiveMatchDB, LiveAnalysisDB, UpcomingMatchDB

logger = logging.getLogger("katrain_cron.cleanup")


class CleanupJob(BaseJob):
    """Periodic cleanup of old data to prevent database growth.

    Cleans up:
    1. Finished matches older than retention period
    2. Analysis data for deleted matches
    3. Expired upcoming events (scheduled_time < now)
    """

    name = "cleanup"
    interval_seconds = 86400  # 24 hours

    async def run(self) -> None:
        db = SessionLocal()
        try:
            stats = {
                "matches_deleted": 0,
                "analysis_deleted": 0,
                "upcoming_deleted": 0,
            }

            # 1. Delete old finished matches
            match_cutoff = datetime.utcnow() - timedelta(days=config.CLEANUP_MATCH_RETENTION_DAYS)
            old_matches = (
                db.query(LiveMatchDB)
                .filter(
                    and_(
                        LiveMatchDB.status == "finished",
                        LiveMatchDB.updated_at < match_cutoff,
                    )
                )
                .all()
            )

            old_match_ids = [m.match_id for m in old_matches]

            if old_match_ids:
                # Delete analysis for these matches first (foreign key)
                analysis_deleted = (
                    db.query(LiveAnalysisDB)
                    .filter(LiveAnalysisDB.match_id.in_(old_match_ids))
                    .delete(synchronize_session=False)
                )
                stats["analysis_deleted"] = analysis_deleted

                # Delete the matches
                matches_deleted = (
                    db.query(LiveMatchDB)
                    .filter(LiveMatchDB.match_id.in_(old_match_ids))
                    .delete(synchronize_session=False)
                )
                stats["matches_deleted"] = matches_deleted

            # 2. Delete orphaned analysis (match_id not in live_matches)
            # This handles edge cases where matches were deleted manually
            orphan_sql = text("""
                DELETE FROM live_analysis
                WHERE match_id NOT IN (SELECT match_id FROM live_matches)
            """)
            result = db.execute(orphan_sql)
            orphan_count = result.rowcount
            if orphan_count > 0:
                stats["analysis_deleted"] += orphan_count
                self.logger.info("Deleted %d orphaned analysis records", orphan_count)

            # 3. Delete expired upcoming events
            upcoming_deleted = (
                db.query(UpcomingMatchDB)
                .filter(UpcomingMatchDB.scheduled_time < datetime.utcnow())
                .delete(synchronize_session=False)
            )
            stats["upcoming_deleted"] = upcoming_deleted

            db.commit()

            if any(v > 0 for v in stats.values()):
                self.logger.info(
                    "CleanupJob completed: matches=%d, analysis=%d, upcoming=%d",
                    stats["matches_deleted"],
                    stats["analysis_deleted"],
                    stats["upcoming_deleted"],
                )
            else:
                self.logger.debug("CleanupJob: nothing to clean")

        except Exception:
            db.rollback()
            self.logger.exception("CleanupJob failed")
        finally:
            db.close()
