#!/usr/bin/env python3
"""Backfill missing analysis tasks for a match.

Usage:
    python scripts/backfill_analysis.py <match_id>
    python scripts/backfill_analysis.py xingzhen_180777
    python scripts/backfill_analysis.py --list-finished  # List finished matches without full analysis

Environment:
    KATRAIN_DATABASE_URL - Database connection URL (required)
"""

import argparse
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def backfill_match(match_id: str, priority: int = 100) -> int:
    """Backfill analysis tasks for a single match. Returns number of tasks created."""
    from katrain.cron.db import SessionLocal
    from katrain.cron.analysis_repo import AnalysisRepo
    from katrain.cron.models import LiveMatchDB

    db = SessionLocal()
    try:
        match = db.query(LiveMatchDB).filter(LiveMatchDB.match_id == match_id).first()
        if not match:
            print(f"Error: Match '{match_id}' not found")
            return 0

        if not match.moves:
            print(f"Error: Match '{match_id}' has no moves")
            return 0

        repo = AnalysisRepo(db)
        all_nums = list(range(0, match.move_count + 1))
        created = repo.create_pending(match.match_id, all_nums, priority, list(match.moves))

        print(f"Match: {match_id}")
        print(f"  Move count: {match.move_count}")
        print(f"  Status: {match.status}")
        print(f"  Tasks created: {created}")

        return created
    finally:
        db.close()


def list_incomplete_matches(limit: int = 20):
    """List finished matches that don't have complete analysis."""
    from sqlalchemy import text
    from katrain.cron.db import SessionLocal

    db = SessionLocal()
    try:
        # Find matches where analysis count < move_count + 1
        sql = text("""
            SELECT
                m.match_id,
                m.move_count,
                m.status,
                m.player_black,
                m.player_white,
                COUNT(a.id) as analyzed,
                m.move_count + 1 - COUNT(a.id) as missing
            FROM live_matches m
            LEFT JOIN live_analysis a ON m.match_id = a.match_id AND a.status = 'success'
            WHERE m.status = 'finished' AND m.move_count > 0
            GROUP BY m.match_id, m.move_count, m.status, m.player_black, m.player_white
            HAVING COUNT(a.id) < m.move_count + 1
            ORDER BY missing DESC
            LIMIT :limit
        """)
        rows = db.execute(sql, {"limit": limit}).fetchall()

        if not rows:
            print("All finished matches have complete analysis.")
            return

        print(f"{'Match ID':<25} {'Moves':>6} {'Done':>6} {'Missing':>8} {'Players'}")
        print("-" * 80)
        for row in rows:
            players = f"{row.player_black} vs {row.player_white}"
            if len(players) > 30:
                players = players[:27] + "..."
            print(f"{row.match_id:<25} {row.move_count:>6} {row.analyzed:>6} {row.missing:>8} {players}")

    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description="Backfill missing analysis tasks")
    parser.add_argument("match_id", nargs="?", help="Match ID to backfill (e.g., xingzhen_180777)")
    parser.add_argument("--list-finished", action="store_true", help="List finished matches with incomplete analysis")
    parser.add_argument("--priority", type=int, default=100, help="Priority for new tasks (default: 100)")
    parser.add_argument("--all-incomplete", action="store_true", help="Backfill all incomplete finished matches")
    parser.add_argument("--limit", type=int, default=20, help="Limit for --list-finished (default: 20)")

    args = parser.parse_args()

    if not os.getenv("KATRAIN_DATABASE_URL"):
        print("Error: KATRAIN_DATABASE_URL environment variable not set")
        sys.exit(1)

    if args.list_finished:
        list_incomplete_matches(args.limit)
    elif args.all_incomplete:
        from sqlalchemy import text
        from katrain.cron.db import SessionLocal

        db = SessionLocal()
        sql = text("""
            SELECT m.match_id
            FROM live_matches m
            LEFT JOIN live_analysis a ON m.match_id = a.match_id AND a.status = 'success'
            WHERE m.status = 'finished' AND m.move_count > 0
            GROUP BY m.match_id, m.move_count
            HAVING COUNT(a.id) < m.move_count + 1
        """)
        rows = db.execute(sql).fetchall()
        db.close()

        total_created = 0
        for row in rows:
            created = backfill_match(row.match_id, args.priority)
            total_created += created

        print(f"\nTotal tasks created: {total_created}")
    elif args.match_id:
        backfill_match(args.match_id, args.priority)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
