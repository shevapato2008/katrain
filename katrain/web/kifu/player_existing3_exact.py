"""Pinned existing-player links for exactly three independently confirmed raw identities."""

import copy
import hashlib
import json
from datetime import date, datetime

from sqlalchemy import JSON, bindparam, text

DATABASES = {"prod": "katrain_prod_20260725", "test": "katrain_db"}
TARGETS = {
    "中小野田智己": {"prod": 352, "test": 353},
    "桥本雄二郎": {"prod": 486, "test": 487},
    "高梨圣健": {"prod": 564, "test": 565},
}
COUNTS = {"中小野田智己": 210, "桥本雄二郎": 104, "高梨圣健": 93}
FORMAT = "kifu-player-existing3-exact-plan-v1"
# Draft captures pin the candidate inventory; applying requires a separate review artifact.
PROPOSAL_SHA = "c952885eded99264c9aab9ceabce3a4183357e89433d58b1beec474d5ca356f4"
TABLES = (
    "kifu_albums",
    "kifu_players",
    "kifu_player_aliases",
    "kifu_player_names",
    "kifu_raw_player_values",
    "kifu_album_sources",
)


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def digest(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def _json(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json(item) for item in value]
    return value


def _rows(c, sql, params):
    rows = [_json(dict(row)) for row in c.execute(text(sql), params).mappings()]
    if c.dialect.name == "sqlite":
        for row in rows:
            for key in ("parsed_data", "review_metadata"):
                if isinstance(row.get(key), str):
                    row[key] = json.loads(row[key])
    return rows


def snapshot(c, environment):
    if environment not in DATABASES:
        raise ValueError("unknown environment")
    if c.dialect.name == "postgresql" and c.scalar(text("SELECT current_database()")) != DATABASES[environment]:
        raise ValueError("database/environment mismatch")
    params = {f"raw{i}": raw for i, raw in enumerate(TARGETS)}
    params.update({f"id{i}": ids[environment] for i, ids in enumerate(TARGETS.values())})
    raws, ids = ":raw0,:raw1,:raw2", ":id0,:id1,:id2"
    albums = _rows(
        c, f"SELECT * FROM kifu_albums WHERE player_black IN ({raws}) OR player_white IN ({raws}) ORDER BY id", params
    )
    slots = [
        [row["id"], side, row["player_" + side], TARGETS[row["player_" + side]][environment]]
        for row in albums
        for side in ("black", "white")
        if row["player_" + side] in TARGETS and row[side + "_player_id"] is None
    ]
    return {
        "albums": albums,
        "slots": sorted(slots),
        "players": _rows(c, f"SELECT * FROM kifu_players WHERE id IN ({ids}) ORDER BY id", params),
        "aliases": _rows(c, f"SELECT * FROM kifu_player_aliases WHERE player_id IN ({ids}) ORDER BY id", params),
        "names": _rows(c, f"SELECT * FROM kifu_player_names WHERE player_id IN ({ids}) ORDER BY id", params),
        "raw_rows": _rows(c, f"SELECT * FROM kifu_raw_player_values WHERE raw_value IN ({raws}) ORDER BY id", params),
        "album_sources": _rows(
            c,
            f"SELECT s.* FROM kifu_album_sources s JOIN kifu_albums a ON a.id=s.album_id WHERE a.player_black IN ({raws}) OR a.player_white IN ({raws}) ORDER BY s.id",
            params,
        ),
    }


def validate(plan, environment):
    if (
        plan.get("format") != FORMAT
        or plan.get("environment") != environment
        or plan.get("database") != DATABASES.get(environment)
        or plan.get("targets") != TARGETS
        or not isinstance(plan.get("review_sha256"), str)
        or len(plan["review_sha256"]) != 64
    ):
        raise ValueError("plan identity/target mismatch")
    frozen = plan["snapshot"]
    if digest(frozen) != plan["snapshot_sha256"]:
        raise ValueError("plan preimage SHA mismatch")
    owners = {row["id"]: row for row in frozen["players"]}
    if set(owners) != {ids[environment] for ids in TARGETS.values()}:
        raise ValueError("existing target ID mismatch")
    if len(frozen["raw_rows"]) != 3 or {row["raw_value"] for row in frozen["raw_rows"]} != set(TARGETS):
        raise ValueError("raw review scope mismatch")
    albums = {row["id"]: row for row in frozen["albums"]}
    if len(albums) != len(frozen["albums"]):
        raise ValueError("duplicate album preimage")
    expected = sorted(
        [row["id"], side, row["player_" + side], TARGETS[row["player_" + side]][environment]]
        for row in albums.values()
        for side in ("black", "white")
        if row["player_" + side] in TARGETS and row[side + "_player_id"] is None
    )
    if frozen["slots"] != expected or {raw: sum(slot[2] == raw for slot in expected) for raw in TARGETS} != COUNTS:
        raise ValueError("exact 407 NULL-slot membership/target mismatch")
    for row in albums.values():
        for side in ("black", "white"):
            raw = row["player_" + side]
            if raw in TARGETS and row[side + "_player_id"] not in (None, TARGETS[raw][environment]):
                raise ValueError("raw already has conflicting owner")


def capture(engine, environment, review_sha256):
    with engine.connect() as c:
        tx = c.begin()
        try:
            if c.dialect.name == "postgresql":
                c.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"))
            frozen = snapshot(c, environment)
        finally:
            tx.rollback()
    plan = {
        "format": FORMAT,
        "environment": environment,
        "database": DATABASES[environment],
        "targets": TARGETS,
        "review_sha256": review_sha256,
        "snapshot": frozen,
        "snapshot_sha256": digest(frozen),
    }
    validate(plan, environment)
    return plan


def postimage(plan):
    result = copy.deepcopy(plan["snapshot"])
    albums = {row["id"]: row for row in result["albums"]}
    for album_id, side, raw, target in result["slots"]:
        albums[album_id][side + "_player_id"] = target
    result["slots"] = []
    for row in result["raw_rows"]:
        metadata = dict(row["review_metadata"] or {})
        metadata.update(
            kind="reviewed_exact_slot_person_link",
            player_id=TARGETS[row["raw_value"]][plan["environment"]],
            review_sha256=plan["review_sha256"],
            exact_plan_preimage_sha256=plan["snapshot_sha256"],
            held_album_ids=[],
        )
        row.update(review_status="approved", review_metadata=metadata)
    return result


def run(engine, environment, plan, *, apply=False, plan_sha256=None, approved_plan_sha256=None):
    validate(plan, environment)
    if apply and (not plan_sha256 or approved_plan_sha256 != plan_sha256):
        raise ValueError("matching approved plan SHA required")
    if apply and plan["review_sha256"] == PROPOSAL_SHA:
        raise ValueError("draft proposal SHA is not an independent review decision")
    wanted = postimage(plan)
    with engine.connect() as c:
        tx = c.begin()
        try:
            if c.dialect.name == "postgresql":
                c.execute(text("SET LOCAL lock_timeout='5s'"))
                c.execute(text("LOCK TABLE " + ",".join(TABLES) + " IN SHARE ROW EXCLUSIVE MODE"))
            if snapshot(c, environment) != plan["snapshot"]:
                raise ValueError("live preimage differs; capture and review a fresh plan")
            for album_id, side, raw, target in plan["snapshot"]["slots"]:
                changed = c.execute(
                    text(
                        f"UPDATE kifu_albums SET {side}_player_id=:target WHERE id=:id AND player_{side}=:raw AND {side}_player_id IS NULL"
                    ),
                    {"id": album_id, "raw": raw, "target": target},
                )
                if changed.rowcount != 1:
                    raise ValueError("NULL-slot compare-and-swap failed")
            for row in wanted["raw_rows"]:
                changed = c.execute(
                    text(
                        "UPDATE kifu_raw_player_values SET review_status=:status, review_metadata=:metadata "
                        "WHERE id=:id AND raw_value=:raw"
                    ).bindparams(bindparam("metadata", type_=JSON)),
                    {
                        "id": row["id"],
                        "raw": row["raw_value"],
                        "status": row["review_status"],
                        "metadata": row["review_metadata"],
                    },
                )
                if changed.rowcount != 1:
                    raise ValueError("raw review row mismatch")
            if snapshot(c, environment) != wanted:
                raise ValueError("transaction postimage differs")
            tx.commit() if apply else tx.rollback()
        except BaseException:
            tx.rollback()
            raise
    with engine.connect() as c:
        if snapshot(c, environment) != (wanted if apply else plan["snapshot"]):
            raise RuntimeError("independent posttransaction verification failed")
    return {"committed": apply, "linked_slots": 407, "created_player_ids": [], "raw_review_rows": 3}
