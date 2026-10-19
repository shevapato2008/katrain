"""Freeze and apply two independently reviewed in-place Chinese canonical corrections."""

import hashlib
import json
import os
import sys
import unicodedata
from pathlib import Path

from sqlalchemy import create_engine, text


DECISIONS = {
    "TEST": {"database": "katrain_db", "rows": [(542, "趙善津", "赵善津"), (348, "工藤紀夫", "工藤纪夫")]},
    "PROD": {"database": "katrain_prod_20260725", "rows": [(541, "趙善津", "赵善津"), (347, "工藤紀夫", "工藤纪夫")]},
}


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def normalized(value):
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def snapshot(conn, environment):
    approved = DECISIONS[environment]
    database = conn.scalar(text("SELECT current_database()"))
    if database != approved["database"]:
        raise ValueError("actual database differs from approved environment")
    ids = [row[0] for row in approved["rows"]]
    catalog = [list(row) for row in conn.execute(text(
        "SELECT id,canonical_name FROM kifu_players WHERE id=ANY(:ids) ORDER BY id"
    ), {"ids": ids})]
    if len(catalog) != 2 or catalog != sorted([[id_, old] for id_, old, _ in approved["rows"]]):
        raise ValueError("reviewed canonical preimage differs")
    keys = {normalized(value) for _, old, new in approved["rows"] for value in (old, new)}
    canonical_collisions = [list(row) for row in conn.execute(text(
        "SELECT id,canonical_name FROM kifu_players ORDER BY id"
    )) if normalized(row[1]) in keys and row[0] not in ids]
    if canonical_collisions:
        raise ValueError("other canonical identity uses reviewed spelling")
    aliases = [list(row) for row in conn.execute(text(
        "SELECT id,player_id,alias,normalized_alias FROM kifu_player_aliases ORDER BY id"
    )) if row[3] in keys or normalized(row[2]) in keys]
    if any(row[1] not in ids for row in aliases):
        raise ValueError("other alias identity uses reviewed spelling")
    if any(row[1] == id_ and normalized(row[2]) == normalized(new)
           for id_, _, new in approved["rows"] for row in aliases):
        raise ValueError("new canonical is already an alias")
    names = [list(row) for row in conn.execute(text(
        "SELECT id,player_id,lang,display_name,status,reference_url,reference_kind,decision_kind,evidence_id "
        "FROM kifu_player_names WHERE player_id=ANY(:ids) ORDER BY id"
    ), {"ids": ids})]
    fk_counts = [list(row) for row in conn.execute(text(
        "SELECT p.id,(SELECT count(*) FROM kifu_albums WHERE black_player_id=p.id),"
        "(SELECT count(*) FROM kifu_albums WHERE white_player_id=p.id) "
        "FROM kifu_players p WHERE p.id=ANY(:ids) ORDER BY p.id"
    ), {"ids": ids})]
    return {"environment": environment, "database": database, "catalog": catalog,
            "aliases": aliases, "names": names, "fk_counts": fk_counts}


def execute(payload):
    environment, mode = payload["environment"], payload["mode"]
    if environment not in DECISIONS or mode not in {"capture", "dry", "apply", "verify"}:
        raise ValueError("unsupported mode or environment")
    engine = create_engine(os.environ["KATRAIN_DATABASE_URL"])
    try:
        with engine.connect() as conn:
            tx = conn.begin()
            try:
                if mode == "capture":
                    conn.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"))
                    plan = snapshot(conn, environment)
                    plan["version"] = 1
                    plan["sha256"] = digest(plan)
                    tx.rollback()
                    return plan
                if mode == "verify":
                    conn.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"))
                plan = payload["plan"]
                if digest({k: v for k, v in plan.items() if k != "sha256"}) != plan["sha256"]:
                    raise ValueError("frozen plan digest differs")
                if plan["environment"] != environment or plan["database"] != DECISIONS[environment]["database"]:
                    raise ValueError("frozen plan environment differs")
                if mode == "apply" and payload.get("approved_sha256") != plan["sha256"]:
                    raise ValueError("separate plan approval required")
                database = conn.scalar(text("SELECT current_database()"))
                if database != plan["database"]:
                    raise ValueError("actual database differs")
                if mode == "verify":
                    ids = [row[0] for row in DECISIONS[environment]["rows"]]
                    catalog = [list(row) for row in conn.execute(text(
                        "SELECT id,canonical_name FROM kifu_players WHERE id=ANY(:ids) ORDER BY id"
                    ), {"ids": ids})]
                    expected = sorted([[id_, new] for id_, _, new in DECISIONS[environment]["rows"]])
                    if catalog != expected:
                        raise ValueError("canonical postimage differs")
                    names = [list(row) for row in conn.execute(text(
                        "SELECT id,player_id,lang,display_name,status,reference_url,reference_kind,decision_kind,evidence_id "
                        "FROM kifu_player_names WHERE player_id=ANY(:ids) ORDER BY id"
                    ), {"ids": ids})]
                    if names != plan["names"]:
                        raise ValueError("localized names changed")
                    fk_counts = [list(row) for row in conn.execute(text(
                        "SELECT p.id,(SELECT count(*) FROM kifu_albums WHERE black_player_id=p.id),"
                        "(SELECT count(*) FROM kifu_albums WHERE white_player_id=p.id) "
                        "FROM kifu_players p WHERE p.id=ANY(:ids) ORDER BY p.id"
                    ), {"ids": ids})]
                    if fk_counts != plan["fk_counts"]:
                        raise ValueError("game links changed")
                    for id_, old, _ in DECISIONS[environment]["rows"]:
                        count = conn.scalar(text(
                            "SELECT count(*) FROM kifu_player_aliases WHERE player_id=:id AND alias=:old AND normalized_alias=:key"
                        ), {"id": id_, "old": old, "key": normalized(old)})
                        if count != 1:
                            raise ValueError("old traditional alias missing")
                    tx.rollback()
                    return {"mode": mode, "environment": environment, "verified_players": 2,
                            "plan_sha256": plan["sha256"]}
                conn.execute(text(
                    "LOCK TABLE kifu_players,kifu_player_aliases,kifu_player_names,kifu_albums IN SHARE ROW EXCLUSIVE MODE"
                ))
                current = snapshot(conn, environment)
                if current != {k: v for k, v in plan.items() if k not in {"version", "sha256"}}:
                    raise ValueError("live catalog preimage changed")
                for id_, old, new in DECISIONS[environment]["rows"]:
                    changed = conn.execute(text(
                        "UPDATE kifu_players SET canonical_name=:new WHERE id=:id AND canonical_name=:old"
                    ), {"id": id_, "old": old, "new": new})
                    if changed.rowcount != 1:
                        raise ValueError("canonical compare-and-swap failed")
                    if not any(row[1] == id_ and row[3] == normalized(old) for row in plan["aliases"]):
                        conn.execute(text(
                            "INSERT INTO kifu_player_aliases(player_id,alias,normalized_alias) VALUES(:id,:old,:key)"
                        ), {"id": id_, "old": old, "key": normalized(old)})
                after = [list(row) for row in conn.execute(text(
                    "SELECT id,canonical_name FROM kifu_players WHERE id=ANY(:ids) ORDER BY id"
                ), {"ids": [row[0] for row in DECISIONS[environment]["rows"]]})]
                if after != sorted([[id_, new] for id_, _, new in DECISIONS[environment]["rows"]]):
                    raise ValueError("transaction postimage differs")
                if mode == "apply":
                    tx.commit()
                else:
                    tx.rollback()
                return {"mode": mode, "environment": environment, "updated_players": 2,
                        "plan_sha256": plan["sha256"], "committed": mode == "apply"}
            except BaseException:
                if tx.is_active:
                    tx.rollback()
                raise
    finally:
        engine.dispose()


if __name__ == "__main__":
    payload = json.loads(Path(sys.argv[1]).read_text())
    print(json.dumps(execute(payload), ensure_ascii=False, sort_keys=True))
