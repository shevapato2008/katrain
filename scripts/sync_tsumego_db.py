#!/usr/bin/env python3
"""
Sync data/life-n-death/ SGF files to database.

Usage:
  python scripts/sync_tsumego_db.py --dry-run  # Preview changes
  python scripts/sync_tsumego_db.py            # Apply changes
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.orm import Session
from katrain.web.core.db import engine, Base
from katrain.web.core.models_db import TsumegoProblem
from katrain.core.sgf_parser import SGF


DATA_DIR = Path("data/life-n-death")


def parse_category(comment: str) -> str:
    if "手筋" in comment:
        return "tesuji"
    elif "官子" in comment:
        return "endgame"
    return "life-death"


def parse_sgf_file(sgf_path: Path, level: str) -> dict:
    """Parse SGF file and return problem data."""
    with open(sgf_path, "r", encoding="utf-8") as f:
        sgf_content = f.read()

    root = SGF.parse_sgf(sgf_content)
    comment = (root.get_property("C", "") or "") + (root.get_property("GC", "") or "")
    pl = root.get_property("PL", "B") or "B"

    return {
        "id": sgf_path.stem,
        "level": level.lower(),
        "category": parse_category(comment),
        "hint": "黑先" if pl.upper() == "B" else "白先",
        "board_size": root.board_size[0],
        "initial_black": root.get_list_property("AB", []),
        "initial_white": root.get_list_property("AW", []),
        "sgf_content": sgf_content,
        "source": root.get_property("SO", ""),
    }


def sync_database(dry_run: bool = False):
    """Sync SGF files to database."""
    # Collect all SGF files
    sgf_data = {}
    for level_dir in DATA_DIR.iterdir():
        if not level_dir.is_dir() or level_dir.name.startswith("."):
            continue
        for sgf_file in level_dir.glob("*.sgf"):
            try:
                data = parse_sgf_file(sgf_file, level_dir.name)
                sgf_data[data["id"]] = data
            except Exception as e:
                print(f"  ERROR: {sgf_file}: {e}")

    print(f"Found {len(sgf_data)} SGF files")

    # Ensure tables exist
    Base.metadata.create_all(engine)

    stats = {"inserted": 0, "updated": 0, "unchanged": 0, "orphaned": []}

    with Session(engine) as db:
        existing = {p.id: p for p in db.query(TsumegoProblem).all()}

        for problem_id, data in sgf_data.items():
            if problem_id in existing:
                record = existing[problem_id]
                needs_update = (
                    record.level != data["level"] or
                    record.category != data["category"] or
                    record.sgf_content != data["sgf_content"]
                )
                if needs_update:
                    if not dry_run:
                        for key, value in data.items():
                            setattr(record, key, value)
                        record.updated_at = datetime.utcnow()
                    stats["updated"] += 1
                    print(f"  UPDATE: {problem_id} (level: {record.level} -> {data['level']})")
                else:
                    stats["unchanged"] += 1
            else:
                if not dry_run:
                    db.add(TsumegoProblem(**data))
                stats["inserted"] += 1
                print(f"  INSERT: {problem_id} ({data['level']}/{data['category']})")

        # Check orphans
        for problem_id in existing:
            if problem_id not in sgf_data:
                stats["orphaned"].append(problem_id)
                print(f"  WARNING: {problem_id} in DB but no SGF file")

        if not dry_run:
            db.commit()

    print(f"\nSync {'(DRY RUN) ' if dry_run else ''}complete:")
    print(f"  Inserted: {stats['inserted']}")
    print(f"  Updated: {stats['updated']}")
    print(f"  Unchanged: {stats['unchanged']}")
    if stats["orphaned"]:
        print(f"  Orphaned: {len(stats['orphaned'])} (not auto-deleted)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Preview changes only")
    args = parser.parse_args()
    sync_database(dry_run=args.dry_run)
