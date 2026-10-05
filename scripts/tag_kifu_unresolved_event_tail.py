"""Pin and hide the 250 reviewed unresolved-event games from the public list.

The source games and their SGF stay in kifu_albums. Each environment gets its
own exact plan; the ten games with SGF-backed Chinese event overrides stay listed.
"""

from __future__ import annotations

import argparse
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path

from sqlalchemy import bindparam, create_engine, text
from sqlalchemy.engine import make_url


REASON = "unresolved_event_tail_2026_10_05"
FORMAT = "kifu-album-list-hide-v1"
DATABASES = {"prod": "katrain_prod_20260725", "test": "katrain_db"}


def read_json(path: Path):
    with (gzip.open(path, "rt", encoding="utf-8") if path.suffix == ".gz" else path.open(encoding="utf-8")) as stream:
        return json.load(stream)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(inventory_path: Path, asset_path: Path, residual_path: Path, environment: str) -> dict:
    inventory, asset, residual = map(read_json, (inventory_path, asset_path, residual_path))
    if make_url(inventory["database_identifier"]).database != DATABASES[environment]:
        raise ValueError("inventory belongs to another environment")
    raw_counts = {row["raw"]: row["games"] for row in residual["raws"]
                  if row["category"] == "unclassified_pending"}
    if len(raw_counts) != 238 or sum(raw_counts.values()) != 250:
        raise ValueError("reviewed tail changed")
    overrides = {row[0]: {"event": row[1], "sgf_sha256": row[2]}
                 for row in asset["event_album_sgf"]}
    columns = {name: i for i, name in enumerate(inventory["association_columns"])}
    candidates = [row for row in inventory["album_associations"]
                  if row[columns["duplicate_of_id"]] is None
                  and row[columns["event_id"]] is None
                  and row[columns["event"]] in raw_counts]
    visible_overrides = sorted(
        [{"id": row[columns["id"]], **overrides[row[columns["id"]]]} for row in candidates
         if row[columns["id"]] in overrides
         and overrides[row[columns["id"]]]["event"] == row[columns["event"]]],
        key=lambda row: row["id"],
    )
    protected_ids = {row["id"] for row in visible_overrides}
    targets = sorted(
        [{"id": row[columns["id"]], "event": row[columns["event"]],
          "date_played": row[columns["date_played"]]} for row in candidates
         if row[columns["id"]] not in protected_ids],
        key=lambda row: row["id"],
    )
    if len(candidates) != 260 or len(visible_overrides) != 10 or len(targets) != 250:
        raise ValueError("exact target/override membership changed")
    if Counter(row["event"] for row in targets) != Counter(raw_counts):
        raise ValueError("exact raw frequencies changed")
    return {"format": FORMAT, "environment": environment, "database": DATABASES[environment],
            "reason": REASON, "inventory_sha256": sha256(inventory_path),
            "asset_sha256": sha256(asset_path), "residual_sha256": sha256(residual_path),
            "targets": targets, "visible_overrides": visible_overrides}


def run(engine, plan: dict, *, apply: bool) -> dict:
    if (plan.get("format") != FORMAT or plan.get("database") != DATABASES.get(plan.get("environment"))
            or plan.get("reason") != REASON or len(plan.get("targets", [])) != 250
            or len(plan.get("visible_overrides", [])) != 10):
        raise ValueError("unexpected hide plan")
    expected = {row["id"]: (row["event"], row["date_played"]) for row in plan["targets"]}
    protected = {row["id"]: (row["event"], row["sgf_sha256"]) for row in plan["visible_overrides"]}
    if len(expected) != 250 or len(protected) != 10 or set(expected) & set(protected):
        raise ValueError("duplicate or overlapping album IDs")
    raws = sorted({event for event, _ in expected.values()} | {event for event, _ in protected.values()})
    select_scope = text("""
        SELECT id,event,event_id,duplicate_of_id,date_played,list_hidden_reason
        FROM kifu_albums WHERE event IN :raws AND event_id IS NULL AND duplicate_of_id IS NULL
        ORDER BY id
    """).bindparams(bindparam("raws", expanding=True))
    select_protected = text("""
        SELECT id,encode(sha256(convert_to(sgf_content,'UTF8')),'hex') AS sgf_sha256
        FROM kifu_albums WHERE id IN :ids ORDER BY id
    """).bindparams(bindparam("ids", expanding=True))
    update = text("""
        UPDATE kifu_albums SET list_hidden_reason=:reason
        WHERE id IN :ids AND list_hidden_reason IS NULL AND event_id IS NULL
          AND duplicate_of_id IS NULL
    """).bindparams(bindparam("ids", expanding=True))
    with engine.connect() as conn:
        transaction = conn.begin()
        try:
            if conn.dialect.name != "postgresql" or conn.scalar(text("SELECT current_database()")) != plan["database"]:
                raise ValueError("database/environment mismatch")
            conn.execute(text("SET LOCAL lock_timeout='5s'"))
            conn.execute(text("LOCK TABLE kifu_albums IN SHARE ROW EXCLUSIVE MODE"))
            conn.execute(text("ALTER TABLE kifu_albums ADD COLUMN IF NOT EXISTS list_hidden_reason VARCHAR(64)"))
            rows = conn.execute(select_scope, {"raws": raws}).mappings().all()
            live = {row["id"]: (row["event"], row["date_played"], row["list_hidden_reason"]) for row in rows}
            if len(rows) != 260 or set(live) != set(expected) | set(protected):
                raise ValueError("live unresolved-event scope changed")
            if any(live[id_] != (event, date, None) for id_, (event, date) in expected.items()):
                raise ValueError("target album preimage changed")
            if any(live[id_][0] != event or live[id_][2] is not None for id_, (event, _) in protected.items()):
                raise ValueError("protected album preimage changed")
            hashes = {row["id"]: row["sgf_sha256"] for row in conn.execute(
                select_protected, {"ids": sorted(protected)}).mappings()}
            if hashes != {id_: sha for id_, (_, sha) in protected.items()}:
                raise ValueError("SGF-backed Chinese event override changed")
            changed = conn.execute(update, {"reason": REASON, "ids": sorted(expected)}).rowcount
            if changed != 250:
                raise ValueError("hide update changed an unexpected number of rows")
            transaction.commit() if apply else transaction.rollback()
        except BaseException:
            transaction.rollback()
            raise
    if apply:
        with engine.connect() as conn:
            hidden = conn.scalar(text("SELECT count(*) FROM kifu_albums WHERE list_hidden_reason=:reason"),
                                 {"reason": REASON})
            if hidden != 250:
                raise RuntimeError("post-commit hidden count differs from plan")
    return {"environment": plan["environment"], "committed": apply, "hidden_games": 250,
            "retained_sgf_overrides": 10, "reason": REASON}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    make = sub.add_parser("build")
    make.add_argument("--inventory", type=Path, required=True)
    make.add_argument("--asset", type=Path, required=True)
    make.add_argument("--residual", type=Path, required=True)
    make.add_argument("--environment", choices=DATABASES, required=True)
    make.add_argument("--output", type=Path, required=True)
    for action in ("dry-run", "apply"):
        command = sub.add_parser(action)
        command.add_argument("--plan", type=Path, required=True)
        command.add_argument("--plan-sha256", required=True)
        command.add_argument("--database-url", required=True)
    args = parser.parse_args()
    if args.command == "build":
        payload = build(args.inventory, args.asset, args.residual, args.environment)
        args.output.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
                               encoding="utf-8")
        print(json.dumps({"plan_sha256": sha256(args.output), "targets": len(payload["targets"]),
                          "protected": len(payload["visible_overrides"])}, ensure_ascii=False))
        return
    if sha256(args.plan) != args.plan_sha256:
        raise ValueError("plan file SHA mismatch")
    engine = create_engine(args.database_url)
    try:
        print(json.dumps(run(engine, read_json(args.plan), apply=args.command == "apply"), ensure_ascii=False))
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
