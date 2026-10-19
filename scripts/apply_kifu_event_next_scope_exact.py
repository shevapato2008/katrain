"""Capture, compare, dry-run, apply, and verify Astra's exact 743 event-type links.

Input is a JSON payload: mode, environment, decision_path, and for plan/dry/apply/verify
the two captures or the compared plan. Capture/plan/verify are read only. Dry rolls back.
Apply requires the compared plan SHA-256 as approved_plan_sha256.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path

from sqlalchemy import create_engine, text


DECISION_SHA = "84eace6d50f3029fc4dcd353b1b3e31dece649376c6fccae2d595263c32d5088"
DATABASES = {"TEST": "katrain_db", "PROD": "katrain_prod_20260725"}
CHINA_JAPAN = "中日围棋对抗赛"
BEST_TEN = "日本职业十杰战"
ROW_COLUMNS = ("id", "event", "date_played", "date_sort", "source", "source_path", "player_black",
               "player_white", "result", "event_id", "event_edition_id", "duplicate_of_id",
               "black_player_id", "white_player_id", "sgf_content")
IDENTITY_COLUMNS = ("id", "event", "date_played", "date_sort", "source", "source_path", "player_black",
                    "player_white", "result", "event_id", "event_edition_id", "duplicate_of_id", "sgf_md5", "sgf_sha256")


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def checked_decision(path):
    path = Path(path)
    if hashlib.sha256(path.read_bytes()).hexdigest() != DECISION_SHA:
        raise ValueError("decision digest differs")
    decision = json.loads(path.read_text())
    approved, held = decision["approved"], decision["held"]
    targets = decision["event_targets"]
    if (len(approved), len(held)) != (743, 453) or len({r["id"] for r in approved + held}) != 1196:
        raise ValueError("decision partition differs")
    if ({k: (v["canonical_name"], v["event_id"], v["approved_count"]) for k, v in targets.items()}
            != {"china_japan_regular_exchange": (CHINA_JAPAN, None, 637),
                "japan_professional_best_ten": (BEST_TEN, 44, 106)}):
        raise ValueError("decision targets differ")
    for key, target in targets.items():
        ids = [r["id"] for r in approved if r["target_event_key"] == key]
        if ids != target["approved_ids"]:
            raise ValueError("approved IDs differ from target list")
    if any(r["decision"] != "approve_event_type_only" or r["target_event_edition_id"] is not None
           or r["before"]["event_id"] is not None or r["before"]["event_edition_id"] is not None
           for r in approved):
        raise ValueError("approved type-only preimage differs")
    if any(r["decision"] != "hold" for r in held):
        raise ValueError("hold decision differs")
    return decision


def expected_identity(row):
    return {key: (row["before"][key] if key in {"event_id", "event_edition_id", "duplicate_of_id"}
                  else row[key]) for key in IDENTITY_COLUMNS}


def read_scope(conn, decision):
    ids = sorted(r["id"] for r in decision["approved"] + decision["held"])
    rows = conn.execute(text("SELECT " + ",".join(ROW_COLUMNS) + " FROM kifu_albums WHERE id=ANY(:ids) ORDER BY id"),
                        {"ids": ids})
    live = []
    for record in rows:
        row = dict(zip(ROW_COLUMNS, record))
        sgf = row.pop("sgf_content")
        row["sgf_md5"] = hashlib.md5(sgf.encode()).hexdigest()
        row["sgf_sha256"] = hashlib.sha256(sgf.encode()).hexdigest()
        live.append(row)
    if [r["id"] for r in live] != ids:
        raise ValueError("album ID scope differs")
    frozen = {r["id"]: expected_identity(r) for r in decision["approved"] + decision["held"]}
    if any({k: row[k] for k in IDENTITY_COLUMNS} != frozen[row["id"]] for row in live):
        raise ValueError("album identity or SGF preimage differs")
    return live


def read_catalog(conn, environment):
    events = [dict(r) for r in conn.execute(text("SELECT id,canonical_name FROM kifu_events ORDER BY id")).mappings()]
    aliases = [dict(r) for r in conn.execute(text(
        "SELECT event_id,alias FROM kifu_event_aliases WHERE alias=:name OR normalized_alias=:name ORDER BY event_id,alias"),
        {"name": CHINA_JAPAN}).mappings()]
    names = [r for r in events if r["canonical_name"].strip() == CHINA_JAPAN]
    if names or aliases:
        raise ValueError("China-Japan event type or alias collision; review before creating")
    best = [r for r in events if r["canonical_name"] == BEST_TEN]
    if len(best) != 1 or (environment == "PROD" and best[0]["id"] != 44):
        raise ValueError("Japanese Pro Best Ten catalog identity differs")
    return {"japan_professional_best_ten": best[0]["id"], "china_japan_regular_exchange": None}, digest(events)


def capture(conn, decision, environment):
    if environment not in DATABASES or conn.scalar(text("SELECT current_database()")) != DATABASES[environment]:
        raise ValueError("database environment differs")
    rows = read_scope(conn, decision)
    targets, catalog_sha = read_catalog(conn, environment)
    identity = [{k: row[k] for k in IDENTITY_COLUMNS} for row in rows]
    out = {"version": 1, "environment": environment, "database": DATABASES[environment],
           "decision_sha256": DECISION_SHA, "identity_sha256": digest(identity),
           "player_fk_sha256": digest([[r["id"], r["black_player_id"], r["white_player_id"]] for r in rows]),
           "catalog_sha256": catalog_sha, "target_ids": targets,
           "approved_ids": sorted(r["id"] for r in decision["approved"]),
           "held_ids": sorted(r["id"] for r in decision["held"]), "rows": rows}
    out["sha256"] = digest(out)
    return out


def checked_capture(value, decision, environment):
    if digest({k: v for k, v in value.items() if k != "sha256"}) != value.get("sha256"):
        raise ValueError("capture digest differs")
    if value["environment"] != environment or value["database"] != DATABASES[environment] or value["decision_sha256"] != DECISION_SHA:
        raise ValueError("capture environment or decision differs")
    if value["approved_ids"] != sorted(r["id"] for r in decision["approved"]) or value["held_ids"] != sorted(r["id"] for r in decision["held"]):
        raise ValueError("capture scope differs")
    rows = value["rows"]
    if [r["id"] for r in rows] != sorted(value["approved_ids"] + value["held_ids"]):
        raise ValueError("capture rows differ")
    frozen = {r["id"]: expected_identity(r) for r in decision["approved"] + decision["held"]}
    if any({k: r[k] for k in IDENTITY_COLUMNS} != frozen[r["id"]] for r in rows):
        raise ValueError("capture identity differs")
    if digest([{k: r[k] for k in IDENTITY_COLUMNS} for r in rows]) != value["identity_sha256"]:
        raise ValueError("capture identity digest differs")
    if digest([[r["id"], r["black_player_id"], r["white_player_id"]] for r in rows]) != value["player_fk_sha256"]:
        raise ValueError("capture player FK digest differs")
    targets = value["target_ids"]
    if targets["china_japan_regular_exchange"] is not None or not isinstance(targets["japan_professional_best_ten"], int):
        raise ValueError("capture target IDs differ")
    if environment == "PROD" and targets["japan_professional_best_ten"] != 44:
        raise ValueError("PROD target ID 44 differs")


def compare_captures(test, prod):
    for value, environment in ((test, "TEST"), (prod, "PROD")):
        if digest({k: v for k, v in value.items() if k != "sha256"}) != value.get("sha256"):
            raise ValueError(f"{environment} capture digest differs")
        if value["environment"] != environment or value["database"] != DATABASES[environment]:
            raise ValueError("capture environment differs")
    for key in ("decision_sha256", "identity_sha256", "approved_ids", "held_ids"):
        if test[key] != prod[key]:
            raise ValueError(f"TEST/PROD identity or scope differs: {key}")
    result = {"version": 1, "decision_sha256": test["decision_sha256"],
              "identity_sha256": test["identity_sha256"], "TEST": test, "PROD": prod}
    result["sha256"] = digest(result)
    return result


def checked_plan(plan, decision):
    if digest({k: v for k, v in plan.items() if k != "sha256"}) != plan.get("sha256"):
        raise ValueError("plan digest differs")
    checked_capture(plan["TEST"], decision, "TEST")
    checked_capture(plan["PROD"], decision, "PROD")
    if compare_captures(plan["TEST"], plan["PROD"]) != plan:
        raise ValueError("plan comparison differs")


def checked_applied_target_ids(applied, captured):
    keys = {"china_japan_regular_exchange", "japan_professional_best_ten"}
    if (not isinstance(applied, dict) or set(applied) != keys
            or any(type(value) is not int or value <= 0 for value in applied.values())
            or applied["japan_professional_best_ten"] != captured["japan_professional_best_ten"]
            or applied["china_japan_regular_exchange"] == applied["japan_professional_best_ten"]):
        raise ValueError("applied target IDs differ from captured distinct event identities")
    return applied


def postimage(conn, decision, before, target_ids):
    ids = sorted(r["id"] for r in decision["approved"] + decision["held"])
    rows = [dict(r) for r in conn.execute(text(
        "SELECT id,event,event_id,event_edition_id,date_played,date_sort,source,source_path,player_black,player_white,"
        "result,duplicate_of_id,black_player_id,white_player_id,sgf_content FROM kifu_albums WHERE id=ANY(:ids) ORDER BY id"),
        {"ids": ids}).mappings()]
    if len(rows) != len(ids):
        raise ValueError("postimage scope differs")
    approved = {r["id"]: r["target_event_key"] for r in decision["approved"]}
    by_id = {r["id"]: r for r in before["rows"]}
    for row in rows:
        original = by_id[row["id"]]
        expected_id = target_ids[approved[row["id"]]] if row["id"] in approved else original["event_id"]
        if row["event_id"] != expected_id or row["event_edition_id"] is not None:
            raise ValueError("postimage event link differs")
        for key in ("event", "date_played", "date_sort", "source", "source_path", "player_black", "player_white", "result",
                    "duplicate_of_id", "black_player_id", "white_player_id"):
            if row[key] != original[key]:
                raise ValueError(f"postimage {key} differs")
        if hashlib.sha256(row["sgf_content"].encode()).hexdigest() != original["sgf_sha256"]:
            raise ValueError("postimage SGF differs")


def execute(payload):
    mode = payload["mode"]
    decision = checked_decision(payload.get("decision_path", Path(__file__).resolve().parents[1] /
                                       "docs/resource/kifu-event-next-scope-independent-decision-astra-2026-10-04.json"))
    if mode == "plan":
        test, prod = payload["TEST"], payload["PROD"]
        checked_capture(test, decision, "TEST")
        checked_capture(prod, decision, "PROD")
        return compare_captures(test, prod)
    if mode not in {"capture", "dry", "apply", "verify"}:
        raise ValueError("unsupported mode")
    environment = payload["environment"]
    if environment not in DATABASES:
        raise ValueError("unknown environment")
    plan = payload.get("plan")
    if mode != "capture":
        checked_plan(plan, decision)
        if mode == "apply" and payload.get("approved_plan_sha256") != plan["sha256"]:
            raise ValueError("explicit approved plan digest missing")
    engine = create_engine(os.environ["KATRAIN_DATABASE_URL"])
    try:
        with engine.connect() as conn:
            tx = conn.begin()
            try:
                if mode in {"capture", "verify"}:
                    conn.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"))
                if mode == "capture":
                    result = capture(conn, decision, environment)
                    tx.rollback()
                    return result
                before = plan[environment]
                if mode == "verify":
                    if conn.scalar(text("SELECT current_database()")) != DATABASES[environment]:
                        raise ValueError("database environment differs")
                    targets = dict(before["target_ids"])
                    applied_targets = checked_applied_target_ids(payload.get("applied_target_ids"), targets)
                    current = [dict(r) for r in conn.execute(text("SELECT id,canonical_name FROM kifu_events WHERE id=ANY(:ids)"),
                        {"ids": list(applied_targets.values())}).mappings()]
                    if {r["id"]: r["canonical_name"] for r in current} != {
                            applied_targets["china_japan_regular_exchange"]: CHINA_JAPAN,
                            targets["japan_professional_best_ten"]: BEST_TEN}:
                        raise ValueError("postimage event catalog differs")
                    postimage(conn, decision, before, applied_targets)
                    tx.rollback()
                    return {"verified": 743, "held": 453, "plan_sha256": plan["sha256"]}
                conn.execute(text("LOCK TABLE kifu_albums, kifu_events, kifu_event_aliases IN SHARE ROW EXCLUSIVE MODE"))
                if capture(conn, decision, environment) != before:
                    raise ValueError("live capture changed")
                new_id = conn.scalar(text("INSERT INTO kifu_events (canonical_name) VALUES (:name) RETURNING id"),
                                     {"name": CHINA_JAPAN})
                targets = dict(before["target_ids"], china_japan_regular_exchange=new_id)
                by_id = {r["id"]: r for r in before["rows"]}
                sql = text("""UPDATE kifu_albums SET event_id=:target WHERE id=:id
                    AND event IS NOT DISTINCT FROM :event AND date_played IS NOT DISTINCT FROM :date_played
                    AND date_sort IS NOT DISTINCT FROM :date_sort AND source IS NOT DISTINCT FROM :source
                    AND source_path IS NOT DISTINCT FROM :source_path AND player_black IS NOT DISTINCT FROM :player_black
                    AND player_white IS NOT DISTINCT FROM :player_white AND result IS NOT DISTINCT FROM :result
                    AND black_player_id IS NOT DISTINCT FROM :black_player_id
                    AND white_player_id IS NOT DISTINCT FROM :white_player_id
                    AND duplicate_of_id IS NULL AND event_id IS NULL AND event_edition_id IS NULL""")
                for item in decision["approved"]:
                    row = by_id[item["id"]]
                    if conn.execute(sql, {**row, "target": targets[item["target_event_key"]]}).rowcount != 1:
                        raise ValueError(f"album CAS failed: {item['id']}")
                postimage(conn, decision, before, targets)
                if mode == "apply":
                    tx.commit()
                else:
                    tx.rollback()
                return {"mode": mode, "environment": environment, "updated": 743, "held": 453,
                        "target_ids": targets, "plan_sha256": plan["sha256"], "committed": mode == "apply"}
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
