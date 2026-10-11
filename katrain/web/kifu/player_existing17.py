"""Apply only the independently reviewed existing-owner player FK slots."""

import gzip
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path

from sqlalchemy import or_, select, text, update
from sqlalchemy.orm import Session

from katrain.web.core.models_db import (
    KifuAlbum, KifuAlbumSource, KifuEvent, KifuPlayer, KifuPlayerAlias, KifuPlayerName,
    KifuRawPlayerValue, KifuSource,
)


ROOT = Path(__file__).resolve().parents[3]
MANIFEST_PATH = "docs/resource/kifu-player-existing17-readonly-frozen-manifest-2026-10-04.json"
MANIFEST_SHA = "95cd914fb3836b78dfa44e15503afe31c8c78f942bb547d8aa888b8b5a7dfb1e"
DECISION_PATH = "docs/resource/kifu-player-existing17-independent-decision-astra-2026-10-04.json"
DECISION_SHA = "71ea900692f13ba6c499e13c9777d17c607a5a7721c5e469303ec34766cda684"
SIX_DECISION_PATH = "docs/resource/kifu-event-after743-leagues-independent-decision-astra-2026-10-04.json"
SIX_DECISION_SHA = "8a082ab706fa6a21129baf47fd8c904088e509617d2dc5fde85b09568377e8aa"
SIX_PLAN = {
    "test": ("docs/resource/kifu-event-six-leagues-TEST-applied-plan-2026-10-04.json.gz",
             "9c3b0f0a796fcecd5c08a7eb6dd04fe11c5106e96c869357eeb0c0ca2eb46ced"),
    "prod": ("docs/resource/kifu-event-six-leagues-PROD-applied-plan-2026-10-04.json.gz",
             "715ba92e45749d76bd00e9518efef3c6c7a05d07b320b5baeb8177d38667e383"),
}
DATABASES = {"test": "katrain_db", "prod": "katrain_prod_20260725"}
ALBUM_COLUMNS = tuple(column.name for column in KifuAlbum.__table__.columns)
TABLES = {
    "album_sources": KifuAlbumSource, "sources": KifuSource, "catalog": KifuPlayer,
    "aliases": KifuPlayerAlias, "names": KifuPlayerName, "raw_staging": KifuRawPlayerValue,
}


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _digest(value):
    return _sha(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode())


def _pin_bytes(path, sha):
    raw = (ROOT / path).read_bytes()
    if _sha(raw) != sha:
        raise ValueError(f"pinned evidence SHA differs: {path}")
    return raw


def _pinned(path, sha):
    raw = _pin_bytes(path, sha)
    return json.loads(gzip.decompress(raw) if raw[:2] == b"\x1f\x8b" else raw)


def _timestamp(value):
    padded = re.sub(r"\.(\d{1,5})(?=[+-]\d{2}:\d{2}$)",
                    lambda match: "." + match.group(1).ljust(6, "0"), value)
    parsed = datetime.fromisoformat(padded)
    if parsed.tzinfo is None:
        raise ValueError("timestamp must include timezone")
    return parsed


def _equal(a, b):
    if set(a) != set(b):
        return False
    return all(_timestamp(a[key]) == _timestamp(b[key]) if key == "created_at"
               and a[key] is not None and b[key] is not None else a[key] == b[key] for key in a)


def _rows(db, model, criterion=None):
    query = select(model)
    if criterion is not None:
        query = query.where(criterion)
    columns = [column.name for column in model.__table__.columns]
    return sorted(({key: getattr(obj, key).isoformat() if hasattr(getattr(obj, key), "isoformat")
                    else getattr(obj, key) for key in columns} for obj in db.scalars(query)),
                  key=lambda row: row["id"])


def _snapshot(db, frozen):
    ids = [row["id"] for row in frozen["albums"]]
    raws = frozen["raws"]
    albums = _rows(db, KifuAlbum, KifuAlbum.id.in_(ids))
    for row in albums:
        row["sgf_sha256"] = _sha(row["sgf_content"].encode())
    scoped = db.scalars(select(KifuAlbum).where(or_(
        KifuAlbum.player_black.in_(raws), KifuAlbum.player_white.in_(raws))))
    null_slots = sorted([album.id, side, getattr(album, "player_" + side)] for album in scoped
                        for side in ("black", "white")
                        if getattr(album, "player_" + side) in raws and getattr(album, side + "_player_id") is None)
    album_sources = _rows(db, KifuAlbumSource, KifuAlbumSource.album_id.in_(ids))
    source_ids = {row["source_id"] for row in album_sources}
    return {"albums": albums, "null_slots": null_slots, "album_sources": album_sources,
            "sources": _rows(db, KifuSource, KifuSource.id.in_(source_ids)),
            "event_catalog": _rows(db, KifuEvent),
            "catalog": _rows(db, KifuPlayer), "aliases": _rows(db, KifuPlayerAlias),
            "names": _rows(db, KifuPlayerName),
            "raw_staging": _rows(db, KifuRawPlayerValue, KifuRawPlayerValue.raw_value.in_(raws))}


def _event_deltas(frozen, six_decision, six_plan, environment):
    if six_plan["environment"] != environment or six_plan["decision_sha256"] != SIX_DECISION_SHA:
        raise ValueError("six-league applied plan identity differs")
    approved = {row["id"]: row for row in six_decision["approved"]}
    plan_albums = {row["id"]: row for row in six_plan["snapshot"]["albums"]}
    overlap = set(approved) & {row["id"] for row in frozen["albums"]}
    if len(overlap) != 137:
        raise ValueError("six-league player-scope overlap differs")
    originals = {row["id"]: row for row in frozen["albums"]}
    result = {}
    for album_id in overlap:
        source = originals[album_id]
        plan_row = plan_albums[album_id]
        if source["event_id"] is not None or plan_row["event_id"] is not None:
            raise ValueError(f"six-league old event link differs: {album_id}")
        for key, value in plan_row.items():
            if key == "sgf_sha256":
                if value != source[key]:
                    raise ValueError(f"six-league SGF preimage differs: {album_id}")
            elif key in source and not _equal({key: value}, {key: source[key]}):
                raise ValueError(f"six-league shared preimage differs: {album_id}/{key}")
        target = six_plan["targets"][str(approved[album_id]["target_event_id"])]
        result[album_id] = target
    return result


def _member_sets(decision, frozen, environment):
    if decision.get("format") != "kifu-player-existing17-independent-identity-slot-decision-v1":
        raise ValueError("independent decision format differs")
    approved = decision["approved_slots"]
    held = decision["held_slots"]
    if len(approved) != 3576 or len(held) != 807:
        raise ValueError("independent slot counts differ")
    def members(rows):
        return [[r["album_id"], r["side"], r["raw"]] for r in rows]
    if (_digest(members(approved)) != decision["approved_slot_members_sha256"]
            or _digest(members(held)) != decision["held_slot_members_sha256"]
            or _digest([[r["album_id"], r["side"], r["raw"], r["target_ids"][environment]]
                        for r in approved]) != decision["approved_slot_targets_sha256"][environment]):
        raise ValueError("independent exact slot hash differs")
    frozen_slots = {(r["album_id"], r["side"]): r for r in frozen["slots"]}
    if len(frozen_slots) != 4383:
        raise ValueError("frozen exact NULL slot scope differs")
    approved_keys = {(r["album_id"], r["side"]) for r in approved}
    held_keys = {(r["album_id"], r["side"]) for r in held}
    if len(approved_keys) != len(approved) or len(held_keys) != len(held) or approved_keys & held_keys:
        raise ValueError("duplicate or overlapping decision slot")
    if approved_keys | held_keys != set(frozen_slots):
        raise ValueError("independent slot partition differs")
    album_rows = {row["id"]: row for row in frozen["albums"]}
    associations = {}
    for row in frozen["album_sources"]:
        associations.setdefault(row["album_id"], []).append(row)
    identity = {entry["raw"]: entry for entry in decision["identities"]}
    if set(identity) != set(frozen["raws"]):
        raise ValueError("identity raw scope differs")
    for row in approved + held:
        album_id, side, raw = row["album_id"], row["side"], row["raw"]
        original = album_rows[album_id]
        slot = frozen_slots[(album_id, side)]
        if (slot["raw"] != raw or slot["date_played"] != row["date_played"] or
                slot["sgf_sha256"] != row["sgf_sha256"] or row["old_fk"] is not None or
                original["player_" + side] != raw or original[side + "_player_id"] is not None or
                row["event"] != original["event"] or row["sgf_sha256"] != original["sgf_sha256"] or
                row["album_preimage_sha256"][environment] != _digest(original) or
                row["source_association_preimage_sha256"][environment] != _digest(associations.get(album_id, []))):
            raise ValueError(f"independent frozen slot preimage differs: {album_id}/{side}")
        opponent = original["player_white" if side == "black" else "player_black"]
        if row["opponent_raw"] != opponent:
            raise ValueError(f"independent opponent raw differs: {album_id}/{side}")
        if row in approved:
            target = identity[raw]["targets"][environment]
            if row["decision"] != "approve_exact_null_fk" or row["target_ids"][environment] != target["id"]:
                raise ValueError(f"approved target differs: {album_id}/{side}")
            owner = next((p for p in frozen["catalog"] if p["id"] == target["id"]), None)
            if owner is None or owner["canonical_name"] != target["canonical_name"]:
                raise ValueError(f"target catalog differs: {raw}")
        elif row["decision"] != "HOLD":
            raise ValueError(f"held decision differs: {album_id}/{side}")
    return approved, held


def evidence(environment):
    manifest = _pinned(MANIFEST_PATH, MANIFEST_SHA)
    decision = _pinned(DECISION_PATH, DECISION_SHA)
    for item in (decision["inputs"]["proposal"], decision["inputs"]["source_manifest"],
                 decision["intervening_six_league_rebase"]["applied_record"]):
        _pin_bytes(item["path"], item["file_sha256"])
    if decision["inputs"]["frozen_manifest"]["file_sha256"] != MANIFEST_SHA:
        raise ValueError("independent frozen evidence pins differ")
    frozen_by_env = {}
    plans_by_env = {}
    for candidate in DATABASES:
        info = manifest["environments"][candidate]
        if decision["inputs"]["frozen_full_snapshots"][candidate]["file_sha256"] != info["file_sha256"]:
            raise ValueError("independent frozen evidence pins differ")
        frozen_by_env[candidate] = _pinned(info["path"], info["file_sha256"])
        if frozen_by_env[candidate]["database"] != DATABASES[candidate] or len(frozen_by_env[candidate]["slots"]) != 4383:
            raise ValueError("frozen environment/scope differs")
        path, sha = SIX_PLAN[candidate]
        if decision["intervening_six_league_rebase"]["environments"][candidate]["applied_plan"]["file_sha256"] != sha:
            raise ValueError("independent six-league applied plan pin differs")
        plans_by_env[candidate] = _pinned(path, sha)
    frozen = frozen_by_env[environment]
    six_decision = _pinned(SIX_DECISION_PATH, SIX_DECISION_SHA)
    _, plan_sha = SIX_PLAN[environment]
    six_plan = plans_by_env[environment]
    approved, held = _member_sets(decision, frozen, environment)
    deltas = _event_deltas(frozen, six_decision, six_plan, environment)
    rebase = decision["intervening_six_league_rebase"]
    env_rebase = rebase["environments"][environment]
    overlap_slots = [row for row in frozen["slots"] if row["album_id"] in deltas]
    overlap_approved = sum(row["album_id"] in deltas for row in approved)
    overlap_held = sum(row["album_id"] in deltas for row in held)
    if (env_rebase["applied_plan"]["file_sha256"] != plan_sha or
            _digest(env_rebase["changes"]) != env_rebase["changes_sha256"] or
            len(env_rebase["changes"]) != 137 or
            {row["album_id"]: row["new"] for row in env_rebase["changes"]} != deltas or
            (len(overlap_slots), overlap_approved, overlap_held) != (140, 123, 17) or
            any(row["column"] != "event_id" or row["old"] is not None for row in env_rebase["changes"])):
        raise ValueError("independent exact six-league rebase differs")
    return frozen, decision, approved, held, deltas


def _capture(db, frozen, decision, approved, held, deltas, environment):
    database = db.scalar(text("SELECT current_database()")) if db.bind.dialect.name == "postgresql" else DATABASES[environment]
    if database != DATABASES[environment]:
        raise ValueError("database differs")
    snapshot = _snapshot(db, frozen)
    original = {row["id"]: row for row in frozen["albums"]}
    if {row["id"] for row in snapshot["albums"]} != set(original):
        raise ValueError("album scope differs")
    for current in snapshot["albums"]:
        album_id = current["id"]
        before = original[album_id]
        for key, value in current.items():
            wanted = deltas[album_id] if key == "event_id" and album_id in deltas else before[key]
            if not _equal({key: value}, {key: wanted}):
                raise ValueError(f"frozen album preimage differs: {album_id}/{key}")
    expected_slots = sorted([r["album_id"], r["side"], r["raw"]] for r in frozen["slots"])
    if snapshot["null_slots"] != expected_slots:
        raise ValueError("exact live NULL slot scope differs")
    for key in TABLES:
        if len(snapshot[key]) != len(frozen[key]) or any(not _equal(a, b) for a, b in zip(snapshot[key], frozen[key])):
            raise ValueError(f"frozen {key} differs")
    target_rows = decision["intervening_six_league_rebase"]["environments"][environment]["target_catalog_rows"]
    current_targets = [row for row in snapshot["event_catalog"] if row["id"] in {target["id"] for target in target_rows}]
    if len(current_targets) != len(target_rows) or any(not _equal(a, b) for a, b in zip(current_targets, target_rows)):
        raise ValueError("reviewed six-league event target catalog differs")
    return {"format": "kifu-player-existing17-exact-plan-v1", "environment": environment,
            "database": database, "decision_sha256": DECISION_SHA,
            "manifest_sha256": MANIFEST_SHA, "six_league_plan_sha256": SIX_PLAN[environment][1],
            "event_rebase": {str(k): v for k, v in sorted(deltas.items())},
            "snapshot": snapshot, "counts": {"approved": len(approved), "held": len(held)}}


def capture(engine, environment):
    frozen, decision, approved, held, deltas = evidence(environment)
    with Session(engine) as db:
        if engine.dialect.name == "postgresql":
            db.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"))
        return _capture(db, frozen, decision, approved, held, deltas, environment)


def _expected(plan, approved, applied):
    result = json.loads(json.dumps(plan["snapshot"]))
    if applied:
        albums = {row["id"]: row for row in result["albums"]}
        changed = {(row["album_id"], row["side"]) for row in approved}
        for row in approved:
            albums[row["album_id"]][row["side"] + "_player_id"] = row["target_ids"][plan["environment"]]
        result["null_slots"] = [slot for slot in result["null_slots"] if (slot[0], slot[1]) not in changed]
    return result


def _verify_final(engine, frozen, plan, approved, applied):
    with Session(engine) as db:
        if engine.dialect.name == "postgresql":
            db.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"))
        if _snapshot(db, frozen) != _expected(plan, approved, applied):
            raise ValueError("independent posttransaction full-scope verification differs")
        database = db.scalar(text("SELECT current_database()")) if engine.dialect.name == "postgresql" else plan["database"]
        if database != plan["database"]:
            raise ValueError("independent posttransaction database differs")


def run(engine, environment, plan, *, apply=False,
        plan_sha256=None, approved_plan_sha256=None):
    if apply and (not plan_sha256 or plan_sha256 != approved_plan_sha256):
        raise ValueError("separately approved plan SHA required")
    frozen, decision, approved, held, deltas = evidence(environment)
    if plan.get("format") != "kifu-player-existing17-exact-plan-v1" or plan.get("environment") != environment:
        raise ValueError("plan format/environment differs")
    with Session(engine) as db:
        tx = db.begin()
        try:
            if engine.dialect.name == "postgresql":
                db.execute(text("LOCK TABLE kifu_albums,kifu_album_sources,kifu_sources,kifu_players,"
                                "kifu_player_aliases,kifu_player_names,kifu_raw_player_values,kifu_events "
                                "IN SHARE ROW EXCLUSIVE MODE"))
            if _capture(db, frozen, decision, approved, held, deltas, environment) != plan:
                raise ValueError("full captured plan preimage differs")
            for row in approved:
                side = row["side"]
                field = KifuAlbum.black_player_id if side == "black" else KifuAlbum.white_player_id
                raw_field = KifuAlbum.player_black if side == "black" else KifuAlbum.player_white
                changed = db.execute(update(KifuAlbum).where(
                    KifuAlbum.id == row["album_id"], raw_field == row["raw"],
                    KifuAlbum.date_played == row["date_played"], field.is_(None))
                    .values({field: row["target_ids"][environment]}))
                if changed.rowcount != 1:
                    raise ValueError(f"slot CAS failed: {row['album_id']}/{side}")
            db.flush()
            if _snapshot(db, frozen) != _expected(plan, approved, True):
                raise ValueError("in-transaction full postimage differs")
            tx.commit() if apply else tx.rollback()
        except BaseException:
            tx.rollback()
            raise
    try:
        _verify_final(engine, frozen, plan, approved, apply)
    except BaseException as exc:
        if apply:
            raise RuntimeError("commit succeeded; independent postcommit verification failed") from exc
        raise
    return {"committed": apply, **plan["counts"]}
