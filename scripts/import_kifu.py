#!/usr/bin/env python3
"""
Import SGF files from data/kifu-album/ into the kifu_albums table.

Usage:
  python scripts/import_kifu.py --dry-run  # Preview changes
  python scripts/import_kifu.py            # Apply changes
"""

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.orm import Session
from katrain.web.core.db import engine, Base
from katrain.web.core.models_db import KifuAlbum
from katrain.core.sgf_parser import SGF


DATA_DIR = Path("data/kifu-album")


def count_moves(root) -> int:
    """Count total moves by traversing the main line."""
    count = 0
    node = root
    while node.children:
        node = node.children[0]
        if node.move:
            count += 1
    return count


def normalize_date(raw_date: str | None) -> str | None:
    """Normalize SGF date to a sortable ISO-prefix string.

    Examples:
        "1926"           -> "1926-00-00"
        "1928-09-04,05"  -> "1928-09-04"
        "1934-11-25,26"  -> "1934-11-25"
        "1952-08-08"     -> "1952-08-08"
        None             -> None
    """
    if not raw_date:
        return None
    # Extract the first date-like portion (YYYY or YYYY-MM-DD)
    m = re.match(r"(\d{4})(?:-(\d{2}))?(?:-(\d{2}))?", raw_date)
    if not m:
        return None
    year = m.group(1)
    month = m.group(2) or "00"
    day = m.group(3) or "00"
    return f"{year}-{month}-{day}"


def build_search_text(data: dict) -> str:
    """Concatenate searchable fields into a single lowercased string."""
    parts = [
        data.get("player_black", ""),
        data.get("player_white", ""),
        data.get("black_rank", "") or "",
        data.get("white_rank", "") or "",
        data.get("event", "") or "",
        data.get("result", "") or "",
        data.get("date_played", "") or "",
        data.get("place", "") or "",
        data.get("round_name", "") or "",
        data.get("source", "") or "",
    ]
    return " ".join(p for p in parts if p).lower()


def parse_sgf_file(sgf_path: Path) -> dict:
    """Parse SGF file and return kifu album data."""
    root = SGF.parse_file(str(sgf_path))
    # Use root.sgf() for encoding-safe UTF-8 output instead of raw file read
    # (SGF.parse_file handles encoding detection; root.sgf() serializes cleanly)
    sgf_content = root.sgf()

    date_played = root.get_property("DT")

    data = {
        "player_black": root.get_property("PB", "Unknown"),
        "player_white": root.get_property("PW", "Unknown"),
        "black_rank": root.get_property("BR"),
        "white_rank": root.get_property("WR"),
        "event": root.get_property("EV") or root.get_property("GN"),
        "result": root.get_property("RE"),
        "date_played": date_played,
        "date_sort": normalize_date(date_played),
        "place": root.get_property("PC"),
        "komi": root.komi if "KM" in root.properties else None,
        "handicap": root.handicap,
        "board_size": root.board_size[0],
        "rules": root.get_property("RU"),
        "round_name": root.get_property("RO"),
        "source": root.get_property("SO") or root.get_property("US"),
        "move_count": count_moves(root),
        "sgf_content": sgf_content,
        "source_path": str(sgf_path.relative_to(DATA_DIR.parent.parent)),
    }
    data["search_text"] = build_search_text(data)
    return data


def import_kifu(dry_run: bool = False):
    """Import all SGF files from DATA_DIR into database."""
    if not DATA_DIR.exists():
        print(f"ERROR: Data directory not found: {DATA_DIR}")
        sys.exit(1)

    # Collect all SGF files
    sgf_files = sorted(DATA_DIR.rglob("*.sgf"))
    print(f"Found {len(sgf_files)} SGF files in {DATA_DIR}")

    # Ensure tables exist
    Base.metadata.create_all(engine)

    total = len(sgf_files)
    stats = {"inserted": 0, "skipped": 0, "errors": 0}
    error_files = []

    with Session(engine) as db:
        existing_paths = {
            r.source_path for r in db.query(KifuAlbum.source_path).all()
        }
        print(f"Existing records in DB: {len(existing_paths)}")

        for i, sgf_path in enumerate(sgf_files, 1):
            rel_path = str(sgf_path.relative_to(DATA_DIR.parent.parent))
            if rel_path in existing_paths:
                stats["skipped"] += 1
            else:
                try:
                    data = parse_sgf_file(sgf_path)
                    if not dry_run:
                        db.add(KifuAlbum(**data))
                    stats["inserted"] += 1
                except Exception as e:
                    stats["errors"] += 1
                    error_files.append(f"{sgf_path.name}: {e}")

            if i % 500 == 0 or i == total:
                print(
                    f"  Progress: {i}/{total} ({i * 100 // total}%)"
                    f" | inserted={stats['inserted']} skipped={stats['skipped']} errors={stats['errors']}"
                )

        if not dry_run:
            db.commit()

    mode = "(DRY RUN) " if dry_run else ""
    print(f"\nImport {mode}complete:")
    print(f"  Inserted: {stats['inserted']}")
    print(f"  Skipped (already exists): {stats['skipped']}")
    print(f"  Errors: {stats['errors']}")
    if error_files:
        print(f"\nError details ({len(error_files)} files):")
        for err in error_files:
            print(f"  {err}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Import kifu album SGF files into database")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes only")
    args = parser.parse_args()
    import_kifu(dry_run=args.dry_run)
