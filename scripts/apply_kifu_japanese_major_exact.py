"""Apply the independently approved Japanese major-title event IDs, type only.

Input is a JSON payload with mode, environment, decision, and (after capture) plan.
The decision is the unchanged independent-decision JSON; capture and dry never commit.
"""

import argparse
import hashlib
import json
import os
from datetime import timezone
from pathlib import Path

from sqlalchemy import create_engine, text


DECISION_SHA = "7e2f3fda3e9e22a74ddda648114634c4d01e7e2bec25afc0932183b269fcd7d7"
DATABASES = {"TEST": "katrain_db", "PROD": "katrain_prod_20260725"}
# The separately reviewed mixed11 batch changed only these frozen player FKs.
# Pin its approved plan and the resulting entire 3,199-row FK image, including
# the 3,110 rows it did not touch. Event identity and SGF decision stay intact.
MIXED11_PLAN_SHA = {
    "TEST": "1ab5318de70a4d1f0cffa0f2beb98fb5912c95efe60d4c10a7d596d5513d5321",
    "PROD": "e49f76c817a8990978faeb5aa2e9bf4c05f35e9fb95da7001e860b1d8df284a1",
}
REBASED_PLAYER_FK_SHA = {
    "TEST": "7a67b5c6c19cb45cfb7a15d40d1e35c70ccc81192a0043aeec8ffcd199eec616",
    "PROD": "818aec5201585c148dcc7019c09d83690e7e09edfcec4664c15abee46a9e4d28",
}
COLUMNS = ("id", "event", "date_played", "event_id", "event_edition_id", "source", "source_path", "duplicate_of_id")
TARGETS = {23: "日本碁圣战", 25: "日本十段战", 26: "日本棋圣战", 27: "日本名人战", 28: "日本王座战", 29: "日本天元战"}


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def checked_decision(decision, environment):
    if environment not in DATABASES:
        raise ValueError("unknown environment")
    if decision.get("decision_sha256") != DECISION_SHA or digest({k: v for k, v in decision.items() if k != "decision_sha256"}) != DECISION_SHA:
        raise ValueError("independent decision differs")
    if decision["decision"] != "PASS_REVISED_EXACT_SUBSET" or decision["format"] != "kifu-event-japanese-major-independent-decision-v1":
        raise ValueError("decision identity differs")
    approved, held = decision["approved_albums"], decision["held_rows"]
    if (len(approved), len(held)) != (1839, 1360) or any(len(r) != 10 or r[3] is not None or r[4] is not None or r[9] is not None for r in approved):
        raise ValueError("approved/held scope or link preimages differ")
    if any(len(r) != 8 or r[3] is not None or r[4] is not None for r in held):
        raise ValueError("held link preimages differ")
    if len({r[0] for r in approved + held}) != 3199 or set(r[8] for r in approved) != set(TARGETS):
        raise ValueError("scope IDs or targets differ")
    if {f["target_event_id"]: f["target_name"] for f in decision["families"]} != TARGETS:
        raise ValueError("event identities differ")
    if len(decision["assignments"]) != len(approved) or len(decision["sgf_guards"]) != 3199:
        raise ValueError("assignment or SGF scope differs")
    for key, value in (("approved_albums_sha256", approved), ("held_rows_sha256", held),
                       ("assignments_sha256", decision["assignments"]), ("sgf_guards_sha256", decision["sgf_guards"])):
        if digest(value) != decision[key]:
            raise ValueError(f"{key} differs")
    assignments = decision["assignments"]
    if any((a[0], a[1], a[2], a[3]) != (r[0], r[1], r[8], r[9]) for a, r in zip(assignments, approved)):
        raise ValueError("assignment differs from approved rows")
    guard_by_id = {r[0]: r for r in decision["sgf_guards"]}
    if set(guard_by_id) != {r[0] for r in approved + held} or any(a[6] != guard_by_id[a[0]][3] for a in assignments):
        raise ValueError("assignment SGF guard differs")
    catalog = decision["environment_catalogs"][environment]
    if catalog["database"] != DATABASES[environment] or catalog["environment"] != environment:
        raise ValueError("environment binding differs")
    if {r["id"]: r["canonical_name"] for r in catalog["catalog"]} != TARGETS or catalog["target_map"] != {v: k for k, v in TARGETS.items()}:
        raise ValueError("environment event catalog differs")
    if digest(catalog["catalog"]) != catalog["catalog_sha256"] or digest(catalog["player_fk_preimages"]) != catalog["player_fk_preimages_sha256"]:
        raise ValueError("environment catalog or player FK digest differs")
    if len(catalog["player_fk_preimages"]) != 3199 or {r[0] for r in catalog["player_fk_preimages"]} != set(guard_by_id):
        raise ValueError("environment player FK scope differs")
    return approved, held, catalog


def live_catalog(conn, names):
    return [{"id": r.id, "canonical_name": r.canonical_name,
             "created_at": r.created_at.astimezone(timezone.utc).isoformat()}
            for r in conn.execute(text("SELECT id,canonical_name,created_at FROM kifu_events WHERE canonical_name=ANY(:names) ORDER BY id"), {"names": names})]


def live_rows(conn, ids):
    return [list(r) for r in conn.execute(text("SELECT " + ",".join(COLUMNS) + " FROM kifu_albums WHERE id=ANY(:ids) ORDER BY id"), {"ids": ids})]


def live_guards(conn, ids):
    rows = conn.execute(text("SELECT id,player_black,player_white,black_player_id,white_player_id,sgf_content FROM kifu_albums WHERE id=ANY(:ids) ORDER BY id"), {"ids": ids})
    guards, fks = [], []
    for album_id, black, white, black_fk, white_fk, sgf in rows:
        guards.append([album_id, black, white, hashlib.sha256(sgf.encode()).hexdigest() if sgf is not None else None])
        fks.append([album_id, black_fk, white_fk])
    return guards, fks


def live_snapshot(conn, decision, environment):
    approved, held, catalog = checked_decision(decision, environment)
    database = conn.scalar(text("SELECT current_database()"))
    if database != catalog["database"]:
        raise ValueError("actual database differs from approved environment")
    events = live_catalog(conn, list(TARGETS.values()))
    if events != catalog["catalog"]:
        raise ValueError("full event catalog changed")
    ids = [r[0] for r in approved + held]
    if live_rows(conn, ids) != sorted([r[:8] for r in approved] + held):
        raise ValueError("approved or held eight-column preimage changed")
    guards, fks = live_guards(conn, ids)
    if guards != decision["sgf_guards"] or digest(fks) != REBASED_PLAYER_FK_SHA[environment]:
        raise ValueError("SGF, player text, or environment player FK changed")
    return {"database": database, "catalog": events, "approved": approved, "held": held,
            "sgf_guard_sha256": decision["sgf_guards_sha256"],
            "player_fk_sha256": REBASED_PLAYER_FK_SHA[environment]}


def postimage(conn, decision, environment):
    approved, held, catalog = checked_decision(decision, environment)
    ids = [r[0] for r in approved + held]
    expected = sorted([r[:3] + [r[8], None] + r[5:8] for r in approved] + held)
    if live_rows(conn, ids) != expected:
        raise ValueError("approved postimage or held preimage differs")
    if live_catalog(conn, list(TARGETS.values())) != catalog["catalog"]:
        raise ValueError("event catalog changed")
    guards, fks = live_guards(conn, ids)
    if guards != decision["sgf_guards"] or digest(fks) != REBASED_PLAYER_FK_SHA[environment]:
        raise ValueError("postimage SGF, player text, or player FK changed")


def execute(payload):
    mode, environment, decision = payload["mode"], payload["environment"], payload["decision"]
    if mode not in {"capture", "dry", "apply", "verify"}:
        raise ValueError("unsupported mode")
    approved, held, _ = checked_decision(decision, environment)
    engine = create_engine(os.environ["KATRAIN_DATABASE_URL"])
    try:
        with engine.connect() as conn:
            tx = conn.begin()
            try:
                if mode in {"capture", "verify"}:
                    conn.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"))
                if mode == "capture":
                    plan = live_snapshot(conn, decision, environment)
                    plan.update(version=2, environment=environment, decision_sha256=DECISION_SHA,
                                mixed11_plan_sha256=MIXED11_PLAN_SHA[environment])
                    plan["sha256"] = digest(plan)
                    tx.rollback()
                    return plan
                plan = payload["plan"]
                if digest({k: v for k, v in plan.items() if k != "sha256"}) != plan.get("sha256"):
                    raise ValueError("plan digest differs")
                expected_plan = {"database": DATABASES[environment], "catalog": decision["environment_catalogs"][environment]["catalog"],
                                 "approved": approved, "held": held, "sgf_guard_sha256": decision["sgf_guards_sha256"],
                                 "player_fk_sha256": REBASED_PLAYER_FK_SHA[environment],
                                 "version": 2, "environment": environment, "decision_sha256": DECISION_SHA,
                                 "mixed11_plan_sha256": MIXED11_PLAN_SHA[environment]}
                if {k: v for k, v in plan.items() if k != "sha256"} != expected_plan:
                    raise ValueError("plan differs from environment-specific decision")
                if conn.scalar(text("SELECT current_database()")) != DATABASES[environment]:
                    raise ValueError("actual database differs from approved environment")
                if mode == "verify":
                    postimage(conn, decision, environment)
                    tx.rollback()
                    return {"mode": mode, "environment": environment, "verified": len(approved), "held": len(held), "plan_sha256": plan["sha256"]}
                if mode == "apply" and payload.get("approved_plan_sha256") != plan["sha256"]:
                    raise ValueError("explicit approved plan digest missing")
                conn.execute(text("LOCK TABLE kifu_albums, kifu_events IN SHARE ROW EXCLUSIVE MODE"))
                if live_snapshot(conn, decision, environment) != {k: v for k, v in expected_plan.items() if k not in {"version", "environment", "decision_sha256", "mixed11_plan_sha256"}}:
                    raise ValueError("live scope changed after capture")
                update = text("""UPDATE kifu_albums SET event_id=:target_event_id WHERE id=:id
                    AND event IS NOT DISTINCT FROM :event AND date_played IS NOT DISTINCT FROM :date_played
                    AND source IS NOT DISTINCT FROM :source AND source_path IS NOT DISTINCT FROM :source_path
                    AND duplicate_of_id IS NOT DISTINCT FROM :duplicate_of_id
                    AND event_id IS NULL AND event_edition_id IS NULL""")
                for row in approved:
                    params = dict(zip(COLUMNS, row[:8]))
                    params["target_event_id"] = row[8]
                    if conn.execute(update, params).rowcount != 1:
                        raise ValueError(f"CAS failed: {row[0]}")
                postimage(conn, decision, environment)
                if mode == "apply":
                    tx.commit()
                else:
                    tx.rollback()
                return {"mode": mode, "environment": environment, "updated": len(approved), "held": len(held),
                        "plan_sha256": plan["sha256"], "committed": mode == "apply"}
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
