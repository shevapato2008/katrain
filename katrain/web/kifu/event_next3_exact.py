"""Exact type-only links for the three independently reviewed event families."""

import gzip
import hashlib
import json
import re
import unicodedata
from datetime import datetime
from pathlib import Path

from sqlalchemy import select, text, update
from sqlalchemy.orm import Session

from katrain.web.core.models_db import (
    KifuAlbum, KifuAlbumSource, KifuEvent, KifuEventAlias, KifuEventEdition, KifuPlayer, KifuSource,
)


ROOT = Path(__file__).resolve().parents[3]
DECISION_PATH = "docs/resource/kifu-event-after6810-next3-independent-decision-astra-2026-10-04.json"
DECISION_SHA = "87251ecea191f7cce337ee488e7daf82a71908dfda28455576197c9c499c872d"
DATABASES = {"test": "katrain_db", "prod": "katrain_prod_20260725"}
FAMILY_NAMES = {
    "tw_youshi_tendan": "台湾友士杯十段赛",
    "kr_kbs_badukwang": "韩国KBS杯围棋王战",
    "tw_umc_pro": "台湾联电杯职业围棋赛",
}
ALBUM_COLUMNS = tuple(column.name for column in KifuAlbum.__table__.columns)


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _digest(value):
    return _sha(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode())


def _pin_bytes(path, expected):
    raw = (ROOT / path).read_bytes()
    if _sha(raw) != expected:
        raise ValueError(f"pinned evidence SHA differs: {path}")
    return raw


def _pinned(path, expected):
    raw = _pin_bytes(path, expected)
    return json.loads(gzip.decompress(raw) if raw[:2] == b"\x1f\x8b" else raw)


def _timestamp(value):
    value = re.sub(r"\.(\d{1,5})(?=[+-]\d{2}:\d{2}$)",
                   lambda match: "." + match.group(1).ljust(6, "0"), value)
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError("created_at must be timezone-aware")
    return parsed


def _equal(a, b):
    if set(a) != set(b):
        return False
    return all(_timestamp(a[key]) == _timestamp(b[key]) if key == "created_at" and a[key] is not None
               and b[key] is not None else a[key] == b[key] for key in a)


def _row(obj):
    return {column.name: getattr(obj, column.name).isoformat() if hasattr(getattr(obj, column.name), "isoformat")
            else getattr(obj, column.name) for column in obj.__table__.columns}


def _rows(db, model, criterion=None):
    query = select(model)
    if criterion is not None:
        query = query.where(criterion)
    return sorted((_row(obj) for obj in db.scalars(query)), key=lambda row: row["id"])


def _snapshot(db, ids, player_target_ids=()):
    albums = _rows(db, KifuAlbum, KifuAlbum.id.in_(ids))
    associations = _rows(db, KifuAlbumSource, KifuAlbumSource.album_id.in_(ids))
    return {"albums": albums, "album_sources": associations, "sources": _rows(db, KifuSource),
            "catalog": _rows(db, KifuEvent), "aliases": _rows(db, KifuEventAlias),
            "editions": _rows(db, KifuEventEdition),
            "player_catalog": _rows(db, KifuPlayer, KifuPlayer.id.in_(player_target_ids))}


def _name_key(value):
    # Collision guard only; never selects albums or authorizes a link.
    return unicodedata.normalize("NFKC", value).casefold().translate(
        str.maketrans("臺灣盃圍賽職業聯電韓國戰", "台湾杯围赛职业联电韩国战"))


def _catalog_guard(snapshot):
    target_keys = {_name_key(name) for name in FAMILY_NAMES.values()}
    for row in snapshot["catalog"]:
        if _name_key(row["canonical_name"]) in target_keys:
            raise ValueError("approved new event type already exists or collides")
    for row in snapshot["aliases"]:
        if _name_key(row["alias"]) in target_keys or _name_key(row["normalized_alias"]) in target_keys:
            raise ValueError("approved new event alias collides")


def evidence(environment):
    decision = _pinned(DECISION_PATH, DECISION_SHA)
    if decision.get("format") != "kifu-event-after6810-next3-independent-decision-v1":
        raise ValueError("decision format differs")
    frozen_info = decision["inputs"]["full_prod_preimage"]
    frozen = _pinned(frozen_info["path"], frozen_info["file_sha256"])
    for key in ("producer", "producer_markdown", "producer_statistics", "source_manifest"):
        item = decision["inputs"][key]
        _pin_bytes(item["path"], item["file_sha256"])
    if len(decision["approved"]) != 2153 or len(decision["held"]) != 268 or len(frozen["albums"]) != 2421:
        raise ValueError("independent scope count differs")
    for kind in ("approved", "held"):
        rows, ids = decision[kind], decision[kind + "_ids"]
        if ([row["id"] for row in rows] != ids or _digest(rows) != decision[kind + "_records_sha256"]
                or _digest(ids) != decision["held_id_sha256" if kind == "held" else "approved_id_sha256"]):
            raise ValueError(f"independent {kind} member hash differs")
    if set(decision["approved_ids"]) & set(decision["held_ids"]) or len(set(decision["approved_ids"] + decision["held_ids"])) != 2421:
        raise ValueError("independent approved/HOLD partition differs")
    if {item["family_key"]: item["canonical_name"] for item in decision["families"]} != FAMILY_NAMES:
        raise ValueError("approved event family identity differs")
    frozen_by_id = {row["id"]: row for row in frozen["albums"]}
    if set(frozen_by_id) != set(decision["approved_ids"] + decision["held_ids"]):
        raise ValueError("frozen full album scope differs")
    for row in decision["approved"] + decision["held"]:
        original = frozen_by_id[row["id"]]
        if (row["event"] != original["event"] or row["date_played"] != original["date_played"]
                or _sha(original["sgf_content"].encode()) != row["sgf_sha256"]
                or _digest(original) != row["album_preimage_sha256"]
                or original["event_id"] is not None or original["event_edition_id"] is not None):
            raise ValueError(f"frozen reviewed album differs: {row['id']}")
    rebase = decision["existing17_player_rebase"]
    _pin_bytes(rebase["applied_record"]["path"], rebase["applied_record"]["file_sha256"])
    player_decision = _pinned(rebase["player_decision"]["path"], rebase["player_decision"]["file_sha256"])
    plans = {}
    for candidate in DATABASES:
        info = rebase["environments"][candidate]
        plans[candidate] = _pinned(info["applied_plan_path"], info["applied_plan_file_sha256"])
        if plans[candidate]["database"] != DATABASES[candidate] or plans[candidate]["decision_sha256"] != rebase["player_decision"]["file_sha256"]:
            raise ValueError("existing17 applied plan identity differs")
    changes = rebase["environments"][environment]["changes"]
    if len(changes) != 27 or len({(r["album_id"], r["column"]) for r in changes}) != 27:
        raise ValueError("exact player rebase membership differs")
    player_plan_rows = {row["id"]: row for row in plans[environment]["snapshot"]["albums"]}
    player_plan_sources = {}
    for association in plans[environment]["snapshot"]["album_sources"]:
        player_plan_sources.setdefault(association["album_id"], []).append(association)
    player_plan_catalog = {row["id"]: row for row in plans[environment]["snapshot"]["catalog"]}
    approved_player = {(row["album_id"], row["side"]): row for row in player_decision["approved_slots"]}
    bound_changes = []
    for change in changes:
        album_id, side = change["album_id"], change["side"]
        original = frozen_by_id[album_id]
        before = dict(player_plan_rows[album_id]); before.pop("sgf_sha256")
        after = dict(before); after[change["column"]] = change["new"]
        associations = player_plan_sources.get(album_id, [])
        reviewed = approved_player.get((album_id, side))
        if (change["column"] != side + "_player_id" or change["old"] is not None or
                change["raw"] != original["player_" + side] or
                change["sgf_sha256"] != _sha(original["sgf_content"].encode()) or
                _digest(before) != change["album_before_sha256"] or
                _digest(after) != change["album_after_sha256"] or
                _digest(associations) != change["source_association_sha256"] or
                player_plan_catalog.get(change["new"]) != change["target_catalog_row"] or
                reviewed is None or reviewed["target_ids"][environment] != change["new"] or
                (environment == "prod" and original[change["column"]] is not None)):
            raise ValueError(f"existing17 exact player rebase differs: {album_id}/{side}")
        bound_changes.append({**change, "_expected_album": after, "_expected_sources": associations})
    return decision, frozen, bound_changes


def _capture(db, decision, frozen, changes, environment):
    database = db.scalar(text("SELECT current_database()")) if db.bind.dialect.name == "postgresql" else DATABASES[environment]
    if database != DATABASES[environment]:
        raise ValueError("database differs")
    target_player_ids = {change["new"] for change in changes}
    snapshot = _snapshot(db, decision["approved_ids"] + decision["held_ids"], target_player_ids)
    original = {row["id"]: row for row in frozen["albums"]}
    if {row["id"] for row in snapshot["albums"]} != set(original):
        raise ValueError("reviewed album scope differs")
    deltas = {(row["album_id"], row["column"]): row["new"] for row in changes}
    bound = {change["album_id"]: change for change in changes}
    for row in snapshot["albums"]:
        album_id = row["id"]
        if row["event_id"] is not None or row["event_edition_id"] is not None:
            raise ValueError(f"reviewed NULL event/edition differs: {album_id}")
        before = original[album_id]
        if album_id in bound:
            expected_album = bound[album_id]["_expected_album"]
            if not _equal(row, expected_album):
                raise ValueError(f"reviewed complete player postimage differs: {album_id}")
            continue
        for key, value in row.items():
            if environment == "test" and key in ("black_player_id", "white_player_id", "created_at"):
                continue  # Environment-specific, bound by this full capture.
            elif not _equal({key: value}, {key: before[key]}):
                raise ValueError(f"frozen album identity differs: {album_id}/{key}")
    live_associations = {}
    for association in snapshot["album_sources"]:
        live_associations.setdefault(association["album_id"], []).append(association)
    live_player_catalog = {row["id"]: row for row in snapshot["player_catalog"]}
    if set(live_player_catalog) != target_player_ids:
        raise ValueError("reviewed player target catalog scope differs")
    for change in changes:
        album_id = change["album_id"]
        before_associations = change["_expected_sources"]
        current_associations = live_associations.get(album_id, [])
        if (len(current_associations) != len(before_associations) or
                any(not _equal(a, b) for a, b in zip(current_associations, before_associations))):
            raise ValueError(f"reviewed source association postimage differs: {album_id}")
        if not _equal(live_player_catalog[change["new"]], change["target_catalog_row"]):
            raise ValueError(f"reviewed player target catalog differs: {album_id}")
    for key in ("album_sources", "sources", "catalog", "aliases", "editions"):
        if environment == "prod":
            if len(snapshot[key]) != len(frozen[key]) or any(not _equal(a, b) for a, b in zip(snapshot[key], frozen[key])):
                raise ValueError(f"frozen {key} differs")
    if environment == "test":
        def source_identity(data):
            sources = {row["id"]: row["source_key"] for row in data["sources"]}
            return sorted((row["album_id"], row["origin_path"], row["match_method"], sources[row["source_id"]])
                          for row in data["album_sources"])
        if source_identity(snapshot) != source_identity(frozen):
            raise ValueError("frozen TEST source identity differs")
        if {row["source_key"] for row in snapshot["sources"]} != {row["source_key"] for row in frozen["sources"]}:
            raise ValueError("frozen TEST global sources differ")
    _catalog_guard(snapshot)
    return {"format": "kifu-event-next3-exact-plan-v1", "environment": environment, "database": database,
            "decision_sha256": DECISION_SHA,
            "player_rebase_plan_sha256": decision["existing17_player_rebase"]["environments"][environment]["applied_plan_file_sha256"],
            "new_canonical_names": list(FAMILY_NAMES.values()), "snapshot": snapshot,
            "counts": {"approved": 2153, "held": 268, "player_rebased": 27}}


def capture(engine, environment):
    decision, frozen, changes = evidence(environment)
    with Session(engine) as db:
        if engine.dialect.name == "postgresql":
            db.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"))
        return _capture(db, decision, frozen, changes, environment)


def _expected(plan, decision, targets):
    expected = json.loads(json.dumps(plan["snapshot"]))
    by_id = {row["id"]: row for row in expected["albums"]}
    for row in decision["approved"]:
        by_id[row["id"]]["event_id"] = targets[row["family_key"]]
    return expected


def _verify_final(engine, plan, decision, targets, applied, inserted_rows):
    with Session(engine) as db:
        if engine.dialect.name == "postgresql":
            db.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"))
        snapshot = _snapshot(db, decision["approved_ids"] + decision["held_ids"],
                             [row["id"] for row in plan["snapshot"]["player_catalog"]])
        expected = _expected(plan, decision, targets) if applied else plan["snapshot"]
        if applied:
            expected["catalog"] += inserted_rows
            expected["catalog"].sort(key=lambda row: row["id"])
            if {row["id"]: row["canonical_name"] for row in inserted_rows} != {
                    targets[key]: name for key, name in FAMILY_NAMES.items()}:
                raise ValueError("independent new event catalog binding differs")
        if snapshot != expected:
            raise ValueError("independent posttransaction full scope differs")
        database = db.scalar(text("SELECT current_database()")) if engine.dialect.name == "postgresql" else plan["database"]
        if database != plan["database"]:
            raise ValueError("independent posttransaction database differs")


def run(engine, environment, plan, *, apply=False, plan_sha256=None, approved_plan_sha256=None):
    if apply and (not plan_sha256 or plan_sha256 != approved_plan_sha256):
        raise ValueError("separately approved plan SHA required")
    decision, frozen, changes = evidence(environment)
    if plan.get("format") != "kifu-event-next3-exact-plan-v1" or plan.get("environment") != environment:
        raise ValueError("plan format/environment differs")
    with Session(engine) as db:
        tx = db.begin()
        try:
            if engine.dialect.name == "postgresql":
                db.execute(text("LOCK TABLE kifu_albums,kifu_album_sources,kifu_sources,kifu_events,"
                                "kifu_event_aliases,kifu_event_editions,kifu_players IN SHARE ROW EXCLUSIVE MODE"))
            if _capture(db, decision, frozen, changes, environment) != plan:
                raise ValueError("full captured plan preimage differs")
            targets = {}
            for key, name in FAMILY_NAMES.items():
                event = KifuEvent(canonical_name=name)
                db.add(event)
                db.flush()
                targets[key] = event.id
            for row in decision["approved"]:
                changed = db.execute(update(KifuAlbum).where(
                    KifuAlbum.id == row["id"], KifuAlbum.event_id.is_(None),
                    KifuAlbum.event_edition_id.is_(None), KifuAlbum.event == row["event"],
                    KifuAlbum.date_played == row["date_played"])
                    .values(event_id=targets[row["family_key"]]))
                if changed.rowcount != 1:
                    raise ValueError(f"event CAS failed: {row['id']}")
            db.flush()
            after = _snapshot(db, decision["approved_ids"] + decision["held_ids"],
                              [row["id"] for row in plan["snapshot"]["player_catalog"]])
            expected = _expected(plan, decision, targets)
            additions = [row for row in after["catalog"] if row["id"] in set(targets.values())]
            if len(additions) != 3 or {row["id"]: row["canonical_name"] for row in additions} != {
                    targets[key]: name for key, name in FAMILY_NAMES.items()}:
                raise ValueError("new event target binding differs")
            expected["catalog"] += additions
            expected["catalog"].sort(key=lambda row: row["id"])
            if after != expected:
                raise ValueError("in-transaction full postimage differs")
            tx.commit() if apply else tx.rollback()
        except BaseException:
            tx.rollback()
            raise
    try:
        _verify_final(engine, plan, decision, targets, apply, additions)
    except BaseException as exc:
        if apply:
            raise RuntimeError("commit succeeded; independent postcommit verification failed") from exc
        raise
    return {"committed": apply, "created_event_ids": targets if apply else {}, **plan["counts"]}
