"""Freeze and transact the reviewed 2026-10-04 Zhou Heyang B/C repair.

Reads one JSON payload (capture/dry/apply/verify) and prints one JSON result.
Dry performs the real mutations, rolls them back, then compares the full preimage.
Apply requires an explicitly supplied frozen-plan digest. No alias is created.
"""

import copy
import hashlib
import json
import os
import sys
import unicodedata
from pathlib import Path

from sqlalchemy import create_engine, text


DECISION_SHA256 = "a2a444ceeb7895ab03ba7a912c823431adb30b9e84f5e73c0f2389024888d1ef"
FORMAT = "kifu-player-zhou-exact-dedup-plan-v1"
SPELLINGS = ("周鹤洋", "周鶴洋", "周鹤样", "周鹤羊")
TABLES = (
    "kifu_album_sources", "kifu_albums", "kifu_name_research_evidence", "kifu_player_aliases",
    "kifu_player_names", "kifu_players", "kifu_raw_player_values", "kifu_sources",
)
EXPECTED_FKS = {
    ("public", "kifu_albums", ("black_player_id",), "kifu_players", ("id",)),
    ("public", "kifu_albums", ("white_player_id",), "kifu_players", ("id",)),
    ("public", "kifu_name_research_evidence", ("player_id",), "kifu_players", ("id",)),
    ("public", "kifu_player_aliases", ("player_id",), "kifu_players", ("id",)),
    ("public", "kifu_player_names", ("player_id",), "kifu_players", ("id",)),
}


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(value):
    return hashlib.sha256(encoded(value).encode()).hexdigest()


def normalized(value):
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def scope(environment):
    if environment not in {"TEST", "PROD"}:
        raise ValueError("unsupported environment")
    test = environment == "TEST"
    survivor = 1048 if test else 4193
    return {
        "database": "katrain_db" if test else "katrain_prod_20260725",
        "survivor": survivor,
        "players": [[1028, "周鶴洋"], [1048, "周鹤洋"], [9988, "周鹤样"], [9989, "周鹤羊"]]
        if test else [[4193, "周鹤样"], [4194, "周鹤羊"]],
        "retire": [1028, 9988, 9989] if test else [4194],
        "delete_name_ids": [5133, 5134, 5135, 5136, 5137] if test else [],
        "rename": None if test else [4193, "周鹤样", "周鹤洋"],
        "aliases_to_create": [],
        "metadata_repoints": [[10145, 9988, 1048], [10148, 9989, 1048]] if test else [[10148, 4194, 4193]],
        "inventory_sha256": "cc46067736fa3895c85963d88fdacd91aaf6dd1d2b5da3dc843d3df26a8d237c" if test
        else "51102a1992e24aec038cb0d04d7c65a2fd5ffb1083e0e528e931e53cefca1845",
        "slots": [
            {"album_id": 87152, "side": "white", "old_fk": 9988 if test else 4193, "new_fk": survivor,
             "raw": "周鹤样", "opponent": "金承俊", "date": "2005-10-14", "result": "W+R", "moves": 150,
             "sgf_sha256": "30aa83fc32380a89161e660551a22b941cb2bf1e7855645438b983806651eaa6"},
            {"album_id": 148135, "side": "black", "old_fk": 9989 if test else 4194, "new_fk": survivor,
             "raw": "周鹤羊", "opponent": "赵守洵", "date": "2006-06-15", "result": "B+R", "moves": 211,
             "sgf_sha256": "6af57520297a303ac5cb4aa81ee01e04d5f49d49754a9209f43195c4871771f6"},
        ],
    }


def require_equal_preimage(expected, current):
    if expected != current:
        raise ValueError("full preimage changed")


def require_no_references(counts):
    remaining = {key: value for key, value in counts.items() if value}
    if remaining:
        raise ValueError(f"remaining references prevent deletion: {remaining}")


def repoint_raw(before, old_id, new_id):
    metadata = before.get("review_metadata")
    if before.get("review_status") != "pending" or not isinstance(metadata, dict) or metadata.get("player_id") != old_id:
        raise ValueError("raw preimage differs from reviewed pending pointer")
    after = copy.deepcopy(before)
    after["review_metadata"]["player_id"] = new_id
    return after


def foreign_keys(conn):
    rows = [dict(row) for row in conn.execute(text("""
        SELECT n.nspname AS schema, c.relname AS table, k.conname AS constraint,
               ARRAY(SELECT a.attname FROM unnest(k.conkey) WITH ORDINALITY x(attnum,ord)
                     JOIN pg_attribute a ON a.attrelid=k.conrelid AND a.attnum=x.attnum ORDER BY ord) AS columns,
               rn.nspname AS target_schema, rc.relname AS target_table,
               ARRAY(SELECT a.attname FROM unnest(k.confkey) WITH ORDINALITY x(attnum,ord)
                     JOIN pg_attribute a ON a.attrelid=k.confrelid AND a.attnum=x.attnum ORDER BY ord) AS target_columns,
               pg_get_constraintdef(k.oid) AS definition
        FROM pg_constraint k JOIN pg_class c ON c.oid=k.conrelid JOIN pg_namespace n ON n.oid=c.relnamespace
        JOIN pg_class rc ON rc.oid=k.confrelid JOIN pg_namespace rn ON rn.oid=rc.relnamespace
        WHERE k.contype='f' AND k.confrelid IN ('public.kifu_players'::regclass, 'public.kifu_player_names'::regclass)
        ORDER BY n.nspname,c.relname,k.conname
    """)).mappings()]
    keys = {(r["schema"], r["table"], tuple(r["columns"]), r["target_table"], tuple(r["target_columns"])) for r in rows}
    if keys != EXPECTED_FKS or any(r["target_schema"] != "public" for r in rows):
        raise ValueError("incoming FK schema differs; review new references before deletion")
    return rows


def json_rows(conn, table, where="TRUE", params=None):
    if table not in TABLES:
        raise ValueError("unreviewed table")
    return list(conn.scalars(text(f"SELECT to_jsonb(t) FROM public.{table} t WHERE {where} ORDER BY t.id"), params or {}))


def snapshot(conn, spec):
    database = conn.scalar(text("SELECT current_database()"))
    if database != spec["database"]:
        raise ValueError("actual database differs from approved environment")
    ids = [p[0] for p in spec["players"]]
    params = {"ids": ids, "id_strings": [str(i) for i in ids], "album_ids": [87152, 148135],
              "raw_ids": [10145, 10148], "spellings": list(SPELLINGS)}
    state = {"database": database, "foreign_keys": foreign_keys(conn)}
    state["players"] = json_rows(conn, "kifu_players", "t.id=ANY(:ids)", params)
    for key, table in (("names", "kifu_player_names"), ("aliases", "kifu_player_aliases"),
                       ("evidence", "kifu_name_research_evidence")):
        state[key] = json_rows(conn, table, "t.player_id=ANY(:ids)", params)
    state["albums"] = json_rows(conn, "kifu_albums",
                                "t.id=ANY(:album_ids) OR t.black_player_id=ANY(:ids) OR t.white_player_id=ANY(:ids)", params)
    state["raw_rows"] = json_rows(conn, "kifu_raw_player_values",
                                  "t.id=ANY(:raw_ids) OR t.raw_value=ANY(:spellings) "
                                  "OR t.review_metadata->>'player_id'=ANY(:id_strings)", params)
    album_ids = [a["id"] for a in state["albums"]]
    state["album_sources"] = json_rows(conn, "kifu_album_sources", "t.album_id=ANY(:ids)", {"ids": album_ids})
    source_ids = sorted({r["source_id"] for r in state["album_sources"]})
    state["sources"] = json_rows(conn, "kifu_sources", "t.id=ANY(:ids)", {"ids": source_ids})
    keys = {normalized(n) for n in SPELLINGS}
    state["collision_players"] = [r for r in json_rows(conn, "kifu_players") if normalized(r["canonical_name"]) in keys]
    state["collision_aliases"] = [r for r in json_rows(conn, "kifu_player_aliases")
                                   if normalized(r["alias"]) in keys or normalized(r["normalized_alias"]) in keys]
    return state


def validate_preimage(state, spec):
    expected_players = spec["players"]
    if [[r["id"], r["canonical_name"]] for r in state["players"]] != expected_players:
        raise ValueError("reviewed player identities differ")
    if state["collision_players"] != state["players"] or state["collision_aliases"] or state["aliases"] or state["evidence"]:
        raise ValueError("canonical/alias collision or unreviewed catalog reference")
    expected_names = {}
    if spec["survivor"] == 1048:
        for owner, first_id, jp, ko in ((1028, 5133, "チョウ・カヨウ", "주학양"),
                                        (1048, 5233, "チョウ・ホーヤン", "저우 헤양")):
            for offset, (lang, name) in enumerate((('en', 'Zhou Heyang'), ('cn', '周鹤洋'), ('tw', '周鶴洋'), ('jp', jp), ('ko', ko))):
                expected_names[first_id + offset] = (owner, lang, name, "review", "legacy_unverified")
    actual_names = {r["id"]: (r["player_id"], r["lang"], r["display_name"], r["status"], r["reference_kind"])
                    for r in state["names"]}
    if actual_names != expected_names:
        raise ValueError("legacy five-language name preimage differs")
    albums = {a["id"]: a for a in state["albums"]}
    ids = {p[0] for p in spec["players"]}
    approved_old_slots = {(s["album_id"], s["side"], s["old_fk"]) for s in spec["slots"]}
    for slot in spec["slots"]:
        a = albums.get(slot["album_id"], {})
        side = slot["side"]
        other = "white" if side == "black" else "black"
        actual = (a.get(f"{side}_player_id"), a.get(f"player_{side}"), a.get(f"player_{other}"),
                  a.get("date_played"), a.get("result"), a.get("move_count"))
        wanted = (slot["old_fk"], slot["raw"], slot["opponent"], slot["date"], slot["result"], slot["moves"])
        if actual != wanted or hashlib.sha256(a.get("sgf_content", "").encode()).hexdigest() != slot["sgf_sha256"]:
            raise ValueError(f"exact reviewed album/SGF differs: {slot['album_id']}")
        if a.get(f"{other}_player_id") in ids:
            raise ValueError("same-person opponent FK")
    for a in state["albums"]:
        for side in ("black", "white"):
            owner = a[f"{side}_player_id"]
            if owner in spec["retire"] and (a["id"], side, owner) not in approved_old_slots:
                raise ValueError("unreviewed extra album reference to retiring player")
    raw_by_id = {r["id"]: r for r in state["raw_rows"]}
    for raw_id, slot in zip((10145, 10148), spec["slots"]):
        r = raw_by_id.get(raw_id, {})
        if (r.get("raw_value") != slot["raw"] or r.get("review_status") != "pending"
                or r.get("review_metadata") != {"player_id": slot["old_fk"], "kind": "provisional_person_link",
                                                 "inventory_sha256": spec["inventory_sha256"]}):
            raise ValueError("reviewed raw metadata preimage differs")
    allowed = {(raw_id, str(old)) for raw_id, old, _ in spec["metadata_repoints"]}
    for r in state["raw_rows"]:
        pointer = str((r.get("review_metadata") or {}).get("player_id"))
        if pointer in {str(i) for i in spec["retire"]} and (r["id"], pointer) not in allowed:
            raise ValueError("unreviewed extra raw metadata reference to retiring player")


def expected_postimage(before, spec):
    after = copy.deepcopy(before)
    for key in ("players", "collision_players"):
        after[key] = [r for r in after[key] if r["id"] not in spec["retire"]]
        if spec["rename"]:
            for r in after[key]:
                if r["id"] == spec["rename"][0]:
                    r["canonical_name"] = spec["rename"][2]
    after["names"] = [r for r in after["names"] if r["id"] not in spec["delete_name_ids"]]
    for a in after["albums"]:
        for slot in spec["slots"]:
            if a["id"] == slot["album_id"]:
                a[f"{slot['side']}_player_id"] = slot["new_fk"]
    for index, r in enumerate(after["raw_rows"]):
        for raw_id, old, new in spec["metadata_repoints"]:
            if r["id"] == raw_id:
                after["raw_rows"][index] = repoint_raw(r, old, new)
    return after


def build_plan(environment, before):
    spec = scope(environment)
    validate_preimage(before, spec)
    plan = {
        "format": FORMAT, "environment": environment, "decision_sha256": DECISION_SHA256,
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "scope": spec, "preimage": before, "postimage_sha256": digest(expected_postimage(before, spec)),
        "archive": {
            "id_map": [[old, spec["survivor"]] for old in spec["retire"]],
            "players": [r for r in before["players"] if r["id"] in spec["retire"]],
            "names": [r for r in before["names"] if r["id"] in spec["delete_name_ids"]],
        },
        "counts": {"changed_fk_slots": sum(s["old_fk"] != s["new_fk"] for s in spec["slots"]),
                   "protected_exact_slots": sum(s["old_fk"] == s["new_fk"] for s in spec["slots"]),
                   "metadata_repoints": len(spec["metadata_repoints"]), "deleted_players": len(spec["retire"]),
                   "archived_deleted_names": len(spec["delete_name_ids"]), "canonical_renames": int(bool(spec["rename"])),
                   "created_aliases": 0},
    }
    plan["sha256"] = digest(plan)
    return plan


def validate_plan(plan, environment):
    rebuilt = build_plan(environment, plan["preimage"])
    if plan != rebuilt:
        raise ValueError("frozen plan digest, code, environment, or scope differs")


def cas(conn, table, before, assignments=None):
    if table not in {"kifu_players", "kifu_player_names", "kifu_albums", "kifu_raw_player_values"}:
        raise ValueError("unreviewed mutation table")
    where = "t.id=:id AND to_jsonb(t)=CAST(:before AS jsonb)"
    params = {"id": before["id"], "before": encoded(before)}
    if assignments is None:
        query = f"DELETE FROM public.{table} t WHERE {where}"
    else:
        allowed = {"kifu_players": {"canonical_name"}, "kifu_albums": {"black_player_id", "white_player_id"},
                   "kifu_raw_player_values": {"review_metadata"}}
        if len(assignments) != 1 or not set(assignments) <= allowed.get(table, set()):
            raise ValueError("unreviewed mutation column")
        column, value = next(iter(assignments.items()))
        params["value"] = encoded(value) if column == "review_metadata" else value
        value_sql = "CAST(:value AS json)" if column == "review_metadata" else ":value"
        query = f"UPDATE public.{table} t SET {column}={value_sql} WHERE {where}"
    result = conn.execute(text(query), params)
    if result.rowcount != 1:
        raise ValueError(f"full-row CAS failed: {table}/{before['id']}")


def reference_counts(conn, retire_ids):
    counts = {}
    for r in foreign_keys(conn):
        # All identifiers have already matched the fixed EXPECTED_FKS set.
        table, column = r["table"], r["columns"][0]
        counts[f"{table}.{column}"] = conn.scalar(
            text(f"SELECT count(*) FROM public.{table} WHERE {column}=ANY(:ids)"), {"ids": retire_ids})
    counts["raw_metadata.player_id"] = conn.scalar(text(
        "SELECT count(*) FROM public.kifu_raw_player_values WHERE review_metadata->>'player_id'=ANY(:ids)"
    ), {"ids": [str(i) for i in retire_ids]})
    return counts


def mutate(conn, plan):
    spec, before = plan["scope"], plan["preimage"]
    albums = {r["id"]: r for r in before["albums"]}
    raw_rows = {r["id"]: r for r in before["raw_rows"]}
    if spec["rename"]:
        player = next(r for r in before["players"] if r["id"] == spec["rename"][0])
        cas(conn, "kifu_players", player, {"canonical_name": spec["rename"][2]})
    for slot in spec["slots"]:
        if slot["old_fk"] != slot["new_fk"]:
            cas(conn, "kifu_albums", albums[slot["album_id"]], {f"{slot['side']}_player_id": slot["new_fk"]})
    for raw_id, old, new in spec["metadata_repoints"]:
        row = raw_rows[raw_id]
        cas(conn, "kifu_raw_player_values", row, {"review_metadata": repoint_raw(row, old, new)["review_metadata"]})
    for row in plan["archive"]["names"]:
        cas(conn, "kifu_player_names", row)
    counts = reference_counts(conn, spec["retire"])
    require_no_references(counts)
    for row in plan["archive"]["players"]:
        cas(conn, "kifu_players", row)
    return counts


def execute(payload):
    mode, environment = payload["mode"], payload["environment"]
    if mode not in {"capture", "dry", "apply", "verify"}:
        raise ValueError("unsupported mode")
    spec = scope(environment)
    plan = payload.get("plan")
    if mode == "apply" and (not payload.get("approved_sha256") or payload["approved_sha256"] != (plan or {}).get("sha256")):
        raise ValueError("explicit approved plan digest required")
    if mode != "capture":
        validate_plan(plan, environment)
    engine = create_engine(os.environ["KATRAIN_DATABASE_URL"])
    try:
        with engine.connect() as conn:
            tx = conn.begin()
            try:
                if mode in {"capture", "verify"}:
                    conn.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"))
                conn.execute(text("SET LOCAL lock_timeout='5s'"))
                conn.execute(text("SET LOCAL statement_timeout='90s'"))
                if mode in {"dry", "apply"}:
                    conn.execute(text("LOCK TABLE " + ",".join("public." + t for t in TABLES) + " IN SHARE ROW EXCLUSIVE MODE"))
                current = snapshot(conn, spec)
                if mode == "capture":
                    result = build_plan(environment, current)
                    tx.rollback()
                    return result
                if mode == "verify":
                    require_equal_preimage(expected_postimage(plan["preimage"], spec), current)
                    tx.rollback()
                    return {"mode": mode, "environment": environment, "plan_sha256": plan["sha256"], "verified": True}
                require_equal_preimage(plan["preimage"], current)
                counts = mutate(conn, plan)
                after = snapshot(conn, spec)
                require_equal_preimage(expected_postimage(current, spec), after)
                if digest(after) != plan["postimage_sha256"]:
                    raise ValueError("transaction postimage digest differs")
                result = {"mode": mode, "environment": environment, "plan_sha256": plan["sha256"],
                          "counts": plan["counts"], "remaining_references_before_delete": counts,
                          "postimage_sha256": digest(after), "committed": mode == "apply"}
                if mode == "apply":
                    tx.commit()
                else:
                    tx.rollback()
                    with conn.begin():
                        conn.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"))
                        require_equal_preimage(current, snapshot(conn, spec))
                    result["rollback_preimage_unchanged"] = True
                    result["rollback_preimage_sha256"] = digest(current)
                return result
            except BaseException:
                if tx.is_active:
                    tx.rollback()
                raise
    finally:
        engine.dispose()


if __name__ == "__main__":
    print(encoded(execute(json.loads(Path(sys.argv[1]).read_text()))))
