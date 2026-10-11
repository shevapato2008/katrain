"""Apply an independently reviewed set of exact event-stage album links."""

import argparse
import hashlib
import json
import os
from pathlib import Path

from sqlalchemy import create_engine, text


APPROVED_ASSIGNMENT_SHA = "0d5241b0d24c878dd0f809a5df49ef4c0468ac948ca863221b4da3b026258413"
APPROVED_HOLDS_SHA = "908058681b9bfce6990930c55b744e96abdf455f1f41f21b92f46051f75ee93e"
APPROVED_SGF_GUARD_SHA = "f8e562ac3ab2e7c4a1a01b0ec1f329b0a0b5cc568a0c93b27761a4864482a0e4"
COLUMNS = ("id", "event", "date_played", "event_id", "event_edition_id", "source", "source_path", "duplicate_of_id")
DATABASES = {"TEST": "katrain_db", "PROD": "katrain_prod_20260725"}


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def checked_scope(scope):
    if scope["environment"] not in DATABASES:
        raise ValueError("unknown database environment")
    rows = scope["approved_albums"]
    if len(rows) != 2328 or digest(rows) != APPROVED_ASSIGNMENT_SHA:
        raise ValueError("independent approved assignments differ")
    if any(len(row) != 10 or row[3] is not None or row[4] is not None or row[9] is not None for row in rows):
        raise ValueError("approved rows must start unlinked and remain without an edition")
    if len({row[0] for row in rows}) != len(rows):
        raise ValueError("duplicate approved album ID")
    holds = scope["held_rows"]
    if len(holds) != 1745 or digest(holds) != APPROVED_HOLDS_SHA:
        raise ValueError("reviewed holds differ")
    if {row[0] for row in holds} & {row[0] for row in rows}:
        raise ValueError("approved and held IDs overlap")
    guards = scope["sgf_guards"]
    if (len(guards) != len(rows) + len(holds) or digest(guards) != APPROVED_SGF_GUARD_SHA
            or {row[0] for row in guards} != {row[0] for row in rows} | {row[0] for row in holds}):
        raise ValueError("frozen SGF/player guard differs")
    families = scope["families"]
    expected = {24: "日本本因坊战", 37: "日本新人王战", 58: "中国围棋天元战", 59: "中国倡棋杯", 65: "中国围棋名人战"}
    if len(families) != len(expected) or {item["target_event_id"]: item["target_name"] for item in families} != expected:
        raise ValueError("approved event identities differ")
    if set(row[8] for row in rows) != set(expected):
        raise ValueError("assignment targets differ")
    return rows, holds, families


def read_sgf_guards(conn, album_ids):
    rows = conn.execute(text(
        "SELECT id,player_black,player_white,sgf_content FROM kifu_albums WHERE id=ANY(:ids) ORDER BY id"
    ), {"ids": album_ids})
    return [[album_id, black, white, hashlib.sha256(sgf.encode()).hexdigest() if sgf is not None else None]
            for album_id, black, white, sgf in rows]


def live_snapshot(conn, scope):
    approved, holds, families = checked_scope(scope)
    database = conn.scalar(text("SELECT current_database()"))
    if database != DATABASES[scope["environment"]]:
        raise ValueError("actual database differs from approved environment")
    names = [item["target_name"] for item in families]
    catalog = [dict(row) for row in conn.execute(text(
        "SELECT id, canonical_name FROM kifu_events WHERE canonical_name = ANY(:names) ORDER BY canonical_name, id"
    ), {"names": names}).mappings()]
    if len(catalog) != len(names) or {row["canonical_name"] for row in catalog} != set(names):
        raise ValueError("event catalog missing or ambiguous")
    ids = {row["canonical_name"]: row["id"] for row in catalog}
    target_map = {item["target_event_id"]: ids[item["target_name"]] for item in families}
    if scope["environment"] == "PROD" and any(source != target for source, target in target_map.items()):
        raise ValueError("PROD event IDs differ from independent review")
    album_ids = [row[0] for row in approved] + [row[0] for row in holds]
    query = "SELECT " + ",".join(COLUMNS) + " FROM kifu_albums WHERE id=ANY(:ids) ORDER BY id"
    live = [list(row) for row in conn.execute(text(query), {"ids": album_ids})]
    if len(live) != len(album_ids):
        raise ValueError("approved or held album missing")
    expected = sorted([row[:8] for row in approved] + holds)
    if live != expected:
        raise ValueError("live album preimages differ from independent review")
    if read_sgf_guards(conn, album_ids) != scope["sgf_guards"]:
        raise ValueError("live SGF or player identity differs from independent review")
    return {"database": database, "catalog": catalog,
            "approved": [{"before": row[:8], "target_event_id": target_map[row[8]]} for row in approved],
            "holds": holds, "sgf_guard_sha256": APPROVED_SGF_GUARD_SHA}


def execute(payload):
    mode, scope = payload["mode"], payload["scope"]
    if mode not in {"capture", "dry", "apply", "verify"}:
        raise ValueError("unsupported mode")
    checked_scope(scope)
    engine = create_engine(os.environ["KATRAIN_DATABASE_URL"])
    try:
        with engine.connect() as conn:
            tx = conn.begin()
            try:
                if mode == "capture":
                    conn.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"))
                    plan = live_snapshot(conn, scope)
                    plan.update(version=1, environment=scope["environment"], approval_sha256=APPROVED_ASSIGNMENT_SHA)
                    plan["sha256"] = digest(plan)
                    tx.rollback()
                    return plan
                if mode == "verify":
                    conn.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"))
                plan = payload["plan"]
                if digest({key: value for key, value in plan.items() if key != "sha256"}) != plan["sha256"]:
                    raise ValueError("frozen plan digest differs")
                if plan["approval_sha256"] != APPROVED_ASSIGNMENT_SHA or plan["environment"] != scope["environment"]:
                    raise ValueError("plan approval or environment differs")
                database = conn.scalar(text("SELECT current_database()"))
                if database != DATABASES[scope["environment"]] or plan["database"] != database:
                    raise ValueError("actual database differs from frozen plan/environment")
                expected_catalog = {item["target_name"]: item["target_event_id"] for item in scope["families"]}
                frozen_catalog = {row["canonical_name"]: row["id"] for row in plan["catalog"]}
                if len(plan["catalog"]) != len(expected_catalog) or set(frozen_catalog) != set(expected_catalog):
                    raise ValueError("frozen event catalog differs")
                if scope["environment"] == "PROD" and frozen_catalog != expected_catalog:
                    raise ValueError("PROD event IDs differ from independent review")
                expected_approved = [
                    {"before": row[:8], "target_event_id": frozen_catalog[next(
                        item["target_name"] for item in scope["families"] if item["target_event_id"] == row[8])]
                     } for row in scope["approved_albums"]
                ]
                if plan["approved"] != expected_approved or plan["holds"] != scope["held_rows"]:
                    raise ValueError("frozen plan differs from independently approved albums or holds")
                if plan["sgf_guard_sha256"] != APPROVED_SGF_GUARD_SHA:
                    raise ValueError("frozen SGF/player guard differs")
                if mode == "apply" and payload.get("approved_plan_sha256") != plan["sha256"]:
                    raise ValueError("explicit approved plan digest missing")
                if mode == "verify":
                    catalog = [dict(row) for row in conn.execute(text(
                        "SELECT id, canonical_name FROM kifu_events WHERE canonical_name = ANY(:names) "
                        "ORDER BY canonical_name, id"
                    ), {"names": list(expected_catalog)}).mappings()]
                    if catalog != plan["catalog"]:
                        raise ValueError("event catalog changed after apply")
                    ids = [item["before"][0] for item in plan["approved"]]
                    rows = [list(row) for row in conn.execute(text(
                        "SELECT " + ",".join(COLUMNS) + " FROM kifu_albums WHERE id=ANY(:ids) ORDER BY id"
                    ), {"ids": ids})]
                    expected = sorted([item["before"][:3] + [item["target_event_id"], None] + item["before"][5:]
                                       for item in plan["approved"]])
                    if rows != expected:
                        raise ValueError("postcommit approved scope differs")
                    held_ids = [row[0] for row in plan["holds"]]
                    held = [list(row) for row in conn.execute(text(
                        "SELECT " + ",".join(COLUMNS) + " FROM kifu_albums WHERE id=ANY(:ids) ORDER BY id"
                    ), {"ids": held_ids})]
                    if held != plan["holds"]:
                        raise ValueError("postcommit held scope differs")
                    if read_sgf_guards(conn, ids + held_ids) != scope["sgf_guards"]:
                        raise ValueError("postcommit SGF or players changed")
                    total = conn.scalar(text("SELECT count(*) FROM kifu_albums WHERE event_id IS NOT NULL"))
                    tx.rollback()
                    return {"mode": mode, "environment": scope["environment"], "verified": len(rows),
                            "held": len(held), "event_linked_total": total, "plan_sha256": plan["sha256"]}
                conn.execute(text("LOCK TABLE kifu_albums, kifu_events IN SHARE ROW EXCLUSIVE MODE"))
                current = live_snapshot(conn, scope)
                if current != {key: value for key, value in plan.items()
                               if key not in {"version", "environment", "approval_sha256", "sha256"}}:
                    raise ValueError("database scope changed after plan capture")
                for item in plan["approved"]:
                    row = dict(zip(COLUMNS, item["before"]))
                    row["target_event_id"] = item["target_event_id"]
                    updated = conn.execute(text("""UPDATE kifu_albums SET event_id=:target_event_id WHERE id=:id
                        AND event IS NOT DISTINCT FROM :event AND date_played IS NOT DISTINCT FROM :date_played
                        AND source IS NOT DISTINCT FROM :source AND source_path IS NOT DISTINCT FROM :source_path
                        AND duplicate_of_id IS NOT DISTINCT FROM :duplicate_of_id
                        AND event_id IS NULL AND event_edition_id IS NULL"""), row)
                    if updated.rowcount != 1:
                        raise ValueError(f"CAS failed: {row['id']}")
                ids = [item["before"][0] for item in plan["approved"]]
                after = [list(row) for row in conn.execute(text(
                    "SELECT " + ",".join(COLUMNS) + " FROM kifu_albums WHERE id=ANY(:ids) ORDER BY id"
                ), {"ids": ids})]
                expected = sorted([item["before"][:3] + [item["target_event_id"], None] + item["before"][5:]
                                   for item in plan["approved"]])
                if after != expected:
                    raise ValueError("transaction postimage mismatch")
                held_ids = [row[0] for row in plan["holds"]]
                held = [list(row) for row in conn.execute(text(
                    "SELECT " + ",".join(COLUMNS) + " FROM kifu_albums WHERE id=ANY(:ids) ORDER BY id"
                ), {"ids": held_ids})]
                if held != plan["holds"]:
                    raise ValueError("held scope changed")
                if mode == "apply":
                    tx.commit()
                else:
                    tx.rollback()
                return {"mode": mode, "environment": scope["environment"], "updated": len(after),
                        "held": len(held), "plan_sha256": plan["sha256"], "committed": mode == "apply"}
            except BaseException:
                if tx.is_active:
                    tx.rollback()
                raise
    finally:
        engine.dispose()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("payload", type=Path)
    args = parser.parse_args()
    print(json.dumps(execute(json.loads(args.payload.read_text())), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
