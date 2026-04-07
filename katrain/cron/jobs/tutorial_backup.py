"""TutorialBackupJob: daily export of tutorial tables to compressed JSON."""

import gzip
import json
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import text

from katrain.cron import config
from katrain.cron.db import SessionLocal
from katrain.cron.jobs.base import BaseJob

logger = logging.getLogger("katrain_cron.tutorial_backup")

TUTORIAL_TABLES = [
    "tutorial_books",
    "tutorial_chapters",
    "tutorial_sections",
    "tutorial_figures",
    "training_samples",
]


def _rows_to_dicts(result) -> list[dict]:
    """Convert SQLAlchemy result rows to JSON-serializable dicts."""
    rows = []
    for row in result:
        d = dict(row._mapping)
        # Convert datetime objects to ISO strings
        for k, v in d.items():
            if hasattr(v, "isoformat"):
                d[k] = v.isoformat()
        rows.append(d)
    return rows


class TutorialBackupJob(BaseJob):
    """Export tutorial tables to gzipped JSON daily. Retains recent backups."""

    name = "tutorial_backup"
    interval_seconds = 86400  # 24 hours

    async def run(self) -> None:
        backup_dir = Path(config.TUTORIAL_BACKUP_DIR)
        backup_dir.mkdir(parents=True, exist_ok=True)

        db = SessionLocal()
        try:
            data = {"timestamp": datetime.utcnow().isoformat() + "Z", "tables": {}, "counts": {}}

            for table in TUTORIAL_TABLES:
                result = db.execute(text(f"SELECT * FROM {table}"))  # noqa: S608
                rows = _rows_to_dicts(result)
                data["tables"][table] = rows
                data["counts"][table] = len(rows)

            # Count verified figures
            result = db.execute(
                text("SELECT COUNT(*) FROM tutorial_figures WHERE recognition_debug::text LIKE '%\"human_verified\": true%'")
            )
            data["verified_figure_count"] = result.scalar() or 0

            # Write gzipped JSON
            ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            backup_path = backup_dir / f"backup_{ts}.json.gz"
            json_bytes = json.dumps(data, ensure_ascii=False, default=str).encode("utf-8")
            with gzip.open(backup_path, "wb") as f:
                f.write(json_bytes)

            size_mb = backup_path.stat().st_size / (1024 * 1024)
            self.logger.info(
                "Backup saved: %s (%.1f MB) — %s, verified=%d",
                backup_path.name,
                size_mb,
                ", ".join(f"{t}={c}" for t, c in data["counts"].items()),
                data["verified_figure_count"],
            )

            # Purge old backups
            retention = timedelta(days=config.TUTORIAL_BACKUP_RETENTION_DAYS)
            cutoff = datetime.utcnow() - retention
            purged = 0
            for f in sorted(backup_dir.glob("backup_*.json.gz")):
                try:
                    # Parse timestamp from filename: backup_YYYYMMDD_HHMMSS.json.gz
                    file_ts = datetime.strptime(f.stem.replace("backup_", "").replace(".json", ""), "%Y%m%d_%H%M%S")
                    if file_ts < cutoff:
                        f.unlink()
                        purged += 1
                except (ValueError, OSError):
                    continue
            if purged:
                self.logger.info("Purged %d old backup(s)", purged)

        except Exception:
            self.logger.exception("TutorialBackupJob failed")
        finally:
            db.close()
