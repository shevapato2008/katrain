"""Stage every raw kifu name for Chinese-first identity review.

This command classifies raw SGF values. It does not create identities, link
albums, approve names, or rewrite the original game metadata.
"""

import argparse
from collections import Counter
import gzip
import hashlib
import json
import os
from pathlib import Path

from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

from katrain.web.core.models_db import KifuAlbum
from katrain.web.kifu.catalog_preprocess_events import (
    event_series_review_queue,
    prepare_event_raw_values,
    upsert_event_raw_values,
)
from katrain.web.kifu.catalog_preprocess_players import (
    prepare_player_raw_values,
    upsert_player_raw_values,
)


def load_inventory(path: Path, expected_sha256: str | None) -> dict:
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if expected_sha256 is not None and digest != expected_sha256:
        raise ValueError("inventory file SHA-256 differs from the pinned value")
    payload = gzip.decompress(raw) if raw[:2] == b"\x1f\x8b" else raw
    inventory = json.loads(payload)
    if not isinstance(inventory, dict):
        raise ValueError("inventory must be a JSON object")
    return inventory


def _check_live_raw_values(db: Session, players: list[dict], events: list[dict], null_player_slots: int) -> None:
    """Reject a stale snapshot before production writes."""
    expected_players = Counter({row["raw_value"]: row["parsed_data"]["occurrences"] for row in players})
    if null_player_slots:
        expected_players[None] = null_player_slots
    expected_events = Counter({row["parsed_data"]["original_raw_value"]: row["parsed_data"]["occurrences"]
                               for row in events})
    actual_players, actual_events = Counter(), Counter()
    result = db.execute(select(KifuAlbum.player_black, KifuAlbum.player_white, KifuAlbum.event)
                        .execution_options(stream_results=True))
    for black, white, event in result:
        actual_players.update((black, white))
        actual_events[event] += 1
    if actual_players != expected_players or actual_events != expected_events:
        raise ValueError("live album raw names differ from the pinned inventory")


def preprocess(inventory: dict, db: Session | None = None) -> dict:
    """Return a complete report; write only when the caller supplies a session."""
    players = prepare_player_raw_values(inventory)
    events = prepare_event_raw_values(inventory)
    game_count = inventory["counts"]["all"]
    player_slots = sum(row["parsed_data"]["occurrences"] for row in players)
    null_player_slots = game_count * 2 - player_slots
    if null_player_slots < 0:
        raise ValueError("player slots do not reconcile with game count")
    if sum(row["parsed_data"]["occurrences"] for row in events) != game_count:
        raise ValueError("event slots do not reconcile with game count")
    categories = Counter()
    for row in players:
        categories[row["category"]] += row["parsed_data"]["occurrences"]
    event_categories = Counter()
    for row in events:
        event_categories[row["category"]] += row["parsed_data"]["occurrences"]
    report = {
        "games": game_count,
        "player_slots": game_count * 2,
        "null_player_slots": null_player_slots,
        "player_raw_values": len(players),
        "player_slots_by_category": dict(sorted(categories.items())),
        "event_raw_values": len(events),
        "event_games_by_category": dict(sorted(event_categories.items())),
        "provisional_event_series_cores": len(event_series_review_queue(events)),
    }
    if db is not None:
        _check_live_raw_values(db, players, events, null_player_slots)
        report["player_upsert"] = upsert_player_raw_values(db, players)
        report["event_upsert"] = upsert_event_raw_values(db, events)
    return report


def run_against_database(inventory: dict, engine, *, apply: bool) -> dict:
    """Preview or apply the same writes; a preview always rolls back."""
    with Session(engine) as db:
        transaction = db.begin()
        try:
            if engine.dialect.name == "postgresql":
                # Keep the live raw-value check valid until staging commits.
                db.execute(text("LOCK TABLE kifu_albums IN SHARE MODE"))
                # A reviewer must not approve a raw row during its upsert.
                db.execute(text("LOCK TABLE kifu_raw_player_values IN SHARE ROW EXCLUSIVE MODE"))
                db.execute(text("LOCK TABLE kifu_raw_event_values IN SHARE ROW EXCLUSIVE MODE"))
            report = preprocess(inventory, db)
            if apply:
                transaction.commit()
            else:
                transaction.rollback()
        except BaseException:
            transaction.rollback()
            raise
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--expected-sha256", help="required for --apply; SHA-256 of exact inventory file bytes")
    parser.add_argument("--database-url", help="defaults to KATRAIN_DATABASE_URL")
    parser.add_argument("--db-dry-run", action="store_true", help="preview live writes and roll them back")
    parser.add_argument("--event-queue", type=Path, help="write frequency-ordered provisional event cores")
    parser.add_argument("--apply", action="store_true", help="stage values in one transaction")
    args = parser.parse_args()
    if args.apply and args.db_dry_run:
        parser.error("choose --apply or --db-dry-run")
    if (args.apply or args.db_dry_run) and not args.expected_sha256:
        parser.error("database run requires --expected-sha256")
    inventory = load_inventory(args.inventory, args.expected_sha256)
    if not args.apply and not args.db_dry_run:
        report = preprocess(inventory)
    else:
        url = args.database_url or os.getenv("KATRAIN_DATABASE_URL")
        if not url:
            parser.error("database run requires a database URL")
        engine = create_engine(url)
        try:
            report = run_against_database(inventory, engine, apply=args.apply)
        finally:
            engine.dispose()
    if args.event_queue:
        rows = prepare_event_raw_values(inventory)
        args.event_queue.write_text(
            json.dumps(event_series_review_queue(rows), ensure_ascii=False, sort_keys=True), encoding="utf-8"
        )
    report["database_mode"] = "apply" if args.apply else "dry_run" if args.db_dry_run else "offline"
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
