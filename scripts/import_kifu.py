#!/usr/bin/env python3
"""
Import SGF files from data/kifu-album/ into the kifu_albums table.

Usage:
  python scripts/import_kifu.py --dry-run  # Preview changes
  python scripts/import_kifu.py            # Apply changes
  python scripts/import_kifu.py --no-dedupe-content  # Explicitly allow identical SGFs as separate rows
  python scripts/import_kifu.py --dedupe-mainline-years 1950 1978
  # Matching main lines with differing SGF metadata are reported, then imported.
"""

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.orm import Session
from katrain.web.core.db import engine, Base
from katrain.web.core.models_db import KifuAlbum
from katrain.web.kifu.identity import identity_lookup_name, normalize_alias
from katrain.web.kifu.provenance import audited_alias_ids, ensure_album_source, mainline_signature, sgf_sha256
from katrain.core.sgf_parser import SGF


DATA_DIR = Path("data/kifu-album")
COMMIT_EVERY = 500


def _audited_identity_id(aliases: dict[str, dict[str, int | None]], kind: str, raw: str | None) -> int | None:
    raw_key = normalize_alias(raw or "")
    lookup_key = normalize_alias(identity_lookup_name(kind, raw))
    target = aliases[kind].get(lookup_key)
    if raw_key != lookup_key and raw_key in aliases[kind] and aliases[kind][raw_key] != target:
        return None
    return target


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
    # Historical records may start with "ca." or other explanatory text.
    m = re.search(r"(?<!\d)(\d{4})(?:-(\d{2}))?(?:-(\d{2}))?", raw_date)
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
    event = root.get_property("EV") or root.get_property("GN")
    game_names = root.get_list_property("GN") or []
    if (
        "EV" not in root.properties
        and sgf_path.relative_to(DATA_DIR).parts[0] == "19x19"
        and root.get_property("SO") == "https://19x19.com"
        and len(game_names) == 2
        and game_names[0] == "GNUGo3.8"
        and game_names[1]
        and (root.get_property("GC") or "").startswith(game_names[1])
    ):
        # This source stores its program label before the actual game name.
        event = game_names[1]

    data = {
        "player_black": root.get_property("PB", "Unknown"),
        "player_white": root.get_property("PW", "Unknown"),
        "black_rank": root.get_property("BR"),
        "white_rank": root.get_property("WR"),
        "event": event,
        "result": root.get_property("RE"),
        "date_played": date_played,
        # DTX often records a publication date, so use it for approximate
        # sorting only; do not display it as the date the game was played.
        "date_sort": normalize_date(date_played) or normalize_date(root.get_property("DTX")),
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


def import_kifu(
    dry_run: bool = False, dedupe_content: bool = True, dedupe_mainline_years: tuple[int, int] | None = None
):
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
    stats = {
        "inserted": 0,
        "skipped": 0,
        "duplicate_content": 0,
        "mainline_candidates": 0,
        "source_links_added": 0,
        "errors": 0,
    }
    error_files = []
    candidate_files = []

    with Session(engine) as db:
        approved_aliases = audited_alias_ids(db)
        existing_paths = {path: album_id for album_id, path in db.query(KifuAlbum.id, KifuAlbum.source_path)}
        print(f"Existing records in DB: {len(existing_paths)}")
        existing_content_hashes: dict[str, list[int | str]] = {}
        if dedupe_content:
            for album_id, content in db.query(KifuAlbum.id, KifuAlbum.sgf_content).yield_per(1000):
                existing_content_hashes.setdefault(sgf_sha256(content), []).append(album_id)
        existing_mainlines: dict[str, str] = {}
        if dedupe_mainline_years:
            first_year, last_year = dedupe_mainline_years
            existing_games = db.query(KifuAlbum.sgf_content).filter(
                KifuAlbum.date_sort >= f"{first_year}-00-00",
                KifuAlbum.date_sort < f"{last_year + 1}-00-00",
            )
            for (sgf_content,) in existing_games.yield_per(500):
                try:
                    signature = mainline_signature(sgf_content)
                except (ValueError, IndexError):
                    continue
                if signature:
                    existing_mainlines.setdefault(signature, sgf_sha256(sgf_content))
            print(f"Existing main lines in {first_year}-{last_year}: {len(existing_mainlines)}")

        for i, sgf_path in enumerate(sgf_files, 1):
            rel_path = str(sgf_path.relative_to(DATA_DIR.parent.parent))
            if rel_path in existing_paths:
                stats["skipped"] += 1
                if not dry_run and ensure_album_source(db, existing_paths[rel_path], rel_path, "source_path"):
                    stats["source_links_added"] += 1
            else:
                try:
                    data = parse_sgf_file(sgf_path)
                    content_hash = sgf_sha256(data["sgf_content"]) if dedupe_content else None
                    owner = None
                    if dedupe_content:
                        for candidate in existing_content_hashes.get(content_hash, []):
                            content = (
                                db.get(KifuAlbum, candidate).sgf_content if isinstance(candidate, int) else candidate
                            )
                            if content == data["sgf_content"]:
                                owner = candidate
                                break
                    if owner is not None:
                        stats["duplicate_content"] += 1
                        if not dry_run and isinstance(owner, int):
                            existing = db.get(KifuAlbum, owner)
                            if existing.duplicate_of_id is not None:
                                master = db.get(KifuAlbum, existing.duplicate_of_id)
                                if master is None or master.sgf_content != data["sgf_content"]:
                                    raise ValueError("existing duplicate pointer has different SGF content")
                                owner = master.id
                            if ensure_album_source(db, owner, rel_path, "exact_sgf"):
                                stats["source_links_added"] += 1
                    else:
                        signature = mainline_signature(data["sgf_content"]) if dedupe_mainline_years else None
                        if (
                            signature
                            and signature in existing_mainlines
                            and existing_mainlines[signature] != sgf_sha256(data["sgf_content"])
                        ):
                            stats["mainline_candidates"] += 1
                            if len(candidate_files) < 100:
                                candidate_files.append(rel_path)
                        if not dry_run:
                            data["black_player_id"] = _audited_identity_id(
                                approved_aliases, "player", data["player_black"]
                            )
                            data["white_player_id"] = _audited_identity_id(
                                approved_aliases, "player", data["player_white"]
                            )
                            data["event_id"] = _audited_identity_id(approved_aliases, "event", data["event"])
                            album = KifuAlbum(**data)
                            db.add(album)
                            db.flush()
                            if ensure_album_source(db, album.id, rel_path, "source_path"):
                                stats["source_links_added"] += 1
                            existing_paths[rel_path] = album.id
                        stats["inserted"] += 1
                        if dedupe_content:
                            existing_content_hashes.setdefault(content_hash, []).append(
                                data["sgf_content"] if dry_run else album.id
                            )
                        if signature:
                            existing_mainlines.setdefault(signature, sgf_sha256(data["sgf_content"]))
                except Exception as e:
                    stats["errors"] += 1
                    error_files.append(f"{sgf_path.name}: {e}")

            if i % COMMIT_EVERY == 0 or i == total:
                if not dry_run:
                    db.commit()
                print(
                    f"  Progress: {i}/{total} ({i * 100 // total}%)"
                    f" | inserted={stats['inserted']} skipped={stats['skipped']}"
                    f" duplicates={stats['duplicate_content']} candidates={stats['mainline_candidates']}"
                    f" errors={stats['errors']}"
                )

    mode = "(DRY RUN) " if dry_run else ""
    print(f"\nImport {mode}complete:")
    print(f"  Inserted: {stats['inserted']}")
    print(f"  Skipped (already exists): {stats['skipped']}")
    print(f"  Skipped (same SGF content): {stats['duplicate_content']}")
    print(f"  Same-mainline candidates (imported): {stats['mainline_candidates']}")
    print(f"  Source links added: {stats['source_links_added']}")
    print(f"  Errors: {stats['errors']}")
    if candidate_files:
        print(f"  Candidate paths (first {len(candidate_files)}): {candidate_files}")
    if error_files:
        print(f"\nError details ({len(error_files)} files):")
        for err in error_files:
            print(f"  {err}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Import kifu album SGF files into database")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes only")
    dedupe_options = parser.add_mutually_exclusive_group()
    dedupe_options.add_argument(
        "--dedupe-content", dest="dedupe_content", action="store_true", help="deduplicate exact SGF content (default)"
    )
    dedupe_options.add_argument(
        "--no-dedupe-content", dest="dedupe_content", action="store_false", help="keep identical SGFs as separate rows"
    )
    parser.set_defaults(dedupe_content=True)
    parser.add_argument(
        "--dedupe-mainline-years",
        nargs=2,
        type=int,
        metavar=("FIRST", "LAST"),
        help="Report, but keep, games with an identical full main line in this date range",
    )
    args = parser.parse_args()
    if args.dedupe_mainline_years and args.dedupe_mainline_years[0] > args.dedupe_mainline_years[1]:
        parser.error("FIRST must be no later than LAST")
    import_kifu(
        dry_run=args.dry_run,
        dedupe_content=args.dedupe_content,
        dedupe_mainline_years=tuple(args.dedupe_mainline_years) if args.dedupe_mainline_years else None,
    )
