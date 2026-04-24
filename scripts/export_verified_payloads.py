"""Export all human-verified board_payload data to per-book JSON files.

These files are meant to be tracked in git, ensuring that manually corrected
board positions are never lost — even if the database is wiped.

Usage:
    python scripts/export_verified_payloads.py                  # export all books
    python scripts/export_verified_payloads.py --book-slug X    # export one book
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Allow running from repo root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "data" / "verified_board_payloads"


def get_db_url() -> str:
    """Resolve database URL from environment or config.json."""
    url = os.getenv("KATRAIN_DATABASE_URL")
    if url:
        return url
    for path in [Path.home() / ".katrain" / "config.json", Path("katrain/config.json")]:
        try:
            if path.exists():
                data = json.loads(path.read_text())
                if "server" in data and "database_url" in data["server"]:
                    return data["server"]["database_url"]
        except Exception:
            pass
    return "sqlite:///./db.sqlite3"


QUERY = text("""
    SELECT
        f.id AS figure_id,
        f.figure_label,
        f.page,
        f.board_payload,
        f.recognition_debug,
        s.title AS section_title,
        c.title AS chapter_title,
        b.slug AS book_slug,
        b.title AS book_title
    FROM tutorial_figures f
    JOIN tutorial_sections s ON f.section_id = s.id
    JOIN tutorial_chapters c ON s.chapter_id = c.id
    JOIN tutorial_books b ON c.book_id = b.id
    WHERE f.recognition_debug::text LIKE '%"human_verified": true%'
    ORDER BY b.slug, f.id
""")


def export_verified(db: Session, book_slug_filter: str | None = None) -> dict[str, int]:
    """Export verified figures grouped by book. Returns {slug: count}."""
    result = db.execute(QUERY)
    rows = result.fetchall()

    # Group by book
    books: dict[str, dict] = {}
    for row in rows:
        r = dict(row._mapping)
        slug = r["book_slug"]
        if book_slug_filter and slug != book_slug_filter:
            continue
        if slug not in books:
            books[slug] = {
                "book_slug": slug,
                "book_title": r["book_title"],
                "exported_at": datetime.now(timezone.utc).isoformat(),
                "figures": [],
            }

        # Extract verified_at / verified_by from recognition_debug
        debug = r["recognition_debug"] or {}
        if isinstance(debug, str):
            debug = json.loads(debug)

        books[slug]["figures"].append({
            "figure_id": r["figure_id"],
            "figure_label": r["figure_label"],
            "page": r["page"],
            "section_title": r["section_title"],
            "chapter_title": r["chapter_title"],
            "board_payload": r["board_payload"],
            "verified_at": debug.get("verified_at"),
            "verified_by": debug.get("verified_by"),
        })

    # Write per-book JSON files
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    counts = {}
    for slug, data in books.items():
        data["figure_count"] = len(data["figures"])
        out_path = OUTPUT_DIR / f"{slug}.json"

        # Diff against existing file
        old_count = 0
        if out_path.exists():
            try:
                old_data = json.loads(out_path.read_text(encoding="utf-8"))
                old_count = old_data.get("figure_count", 0)
            except Exception:
                pass

        out_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        counts[slug] = len(data["figures"])
        diff = len(data["figures"]) - old_count
        diff_str = f" (+{diff})" if diff > 0 else f" ({diff})" if diff < 0 else ""
        print(f"  {slug}: {len(data['figures'])} verified figures{diff_str} -> {out_path.name}")

    return counts


def main():
    parser = argparse.ArgumentParser(description="Export verified board payloads to git-tracked JSON")
    parser.add_argument("--book-slug", help="Export only this book slug")
    args = parser.parse_args()

    db_url = get_db_url()
    engine = create_engine(db_url)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()

    try:
        print(f"Exporting verified board payloads to {OUTPUT_DIR}/")
        counts = export_verified(db, args.book_slug)
        total = sum(counts.values())
        print(f"\nTotal: {total} verified figures across {len(counts)} book(s)")
        if not counts:
            print("No verified figures found.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
