"""Exact type-only links for the independently reviewed 514-album event scope."""

import gzip
import hashlib
import json
from pathlib import Path

from sqlalchemy import select, text, update
from sqlalchemy.orm import Session

from katrain.web.core.models_db import (
    KifuAlbum, KifuAlbumSource, KifuEvent, KifuEventAlias, KifuEventEdition,
    KifuPlayer, KifuSource,
)
from katrain.web.kifu.event_next3_exact import _digest, _equal, _name_key as _base_name_key, _rows


ROOT = Path(__file__).resolve().parents[3]
DECISION_PATH = "docs/resource/kifu-event-next514-independent-decision-astra-2026-10-04.json"
DECISION_SHA = "d310278775a8a1b5e08062b271485effdce8e3e58ac5eb218639cdd66b60ce3e"
DATABASES = {"test": "katrain_db", "prod": "katrain_prod_20260725"}
FROZEN = {
    "test": ("docs/resource/kifu-event-next514-TEST-post-next3-independent-preimage-astra-2026-10-04.json.gz",
             "21846202d6ad6752f9bb58607763c9ccca03fae19a3c7411305088bf63ddd122"),
    "prod": ("docs/resource/kifu-event-next514-PROD-post-next3-independent-preimage-astra-2026-10-04.json.gz",
             "d3054848f81ec6c1c9cd72f3f67befe1c2d39005d79b00718b6d8ab6a0cabe32"),
}
PRE_NEXT3 = {
    "test": ("docs/resource/kifu-event-next514-TEST-independent-preimage-astra-2026-10-04.json.gz",
             "8a25aac09df8ddc3c91bd504dcaef5c1d5fb64b11f51e13bbe9d50904bab6094"),
    "prod": ("docs/resource/kifu-event-next514-PROD-independent-preimage-astra-2026-10-04.json.gz",
             "e174b4db7148e95d28fb4e1fa936cbdf4106d4237f62d5d568b8d4583efbc0d1"),
}
NEXT3_PLAN = {
    "test": ("docs/resource/kifu-event-next3-TEST-applied-plan-2026-10-04.json.gz",
             "42729bf088e9e8646d51c011b1a13ac3734a5cf01fe8f068f35b3bbf0fa5de5d"),
    "prod": ("docs/resource/kifu-event-next3-PROD-applied-plan-2026-10-04.json.gz",
             "3c9fdb2ce84b72d6d5d0b42fcde1ce1a9496494d84022d63de338eb829f5dfca"),
}


def _pinned(path, expected):
    raw = (ROOT / path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError(f"pinned evidence SHA differs: {path}")
    return json.loads(gzip.decompress(raw) if raw[:2] == b"\x1f\x8b" else raw)


def _snapshot(db, ids, player_ids):
    return {
        "albums": _rows(db, KifuAlbum, KifuAlbum.id.in_(ids)),
        "album_sources": _rows(db, KifuAlbumSource, KifuAlbumSource.album_id.in_(ids)),
        "sources": _rows(db, KifuSource),
        "events": _rows(db, KifuEvent),
        "aliases": _rows(db, KifuEventAlias),
        "editions": _rows(db, KifuEventEdition),
        "players": _rows(db, KifuPlayer, KifuPlayer.id.in_(player_ids)),
    }


def _same_rows(current, frozen):
    return len(current) == len(frozen) and all(_equal(a, b) for a, b in zip(current, frozen))


def _name_key(value):
    return _base_name_key(value).replace("體", "体")


def _validate_next3_catalog_rebase(environment, before, after, applied_plan):
    if applied_plan["database"] != DATABASES[environment] or len(applied_plan["snapshot"]["catalog"]) != 74:
        raise ValueError("next3 applied catalog plan differs")
    original_catalog = applied_plan["snapshot"]["catalog"]
    if not _same_rows(after["events"][:74], original_catalog):
        raise ValueError("next3 original catalog preimage differs")
    new_rows = after["events"][74:]
    expected_names = {79: "台湾友士杯十段赛", 80: "韩国KBS杯围棋王战", 81: "台湾联电杯职业围棋赛"}
    if len(new_rows) != 3 or {row["id"]: row["canonical_name"] for row in new_rows} != expected_names:
        raise ValueError("exact next3 catalog addition differs")
    for key in ("albums", "album_sources", "sources", "aliases", "editions", "players"):
        if not _same_rows(before[key], after[key]):
            raise ValueError(f"next3 intervening {key} drift differs")
    if environment == "test" and not _same_rows(before["events"], after["events"]):
        raise ValueError("TEST next3 catalog capture differs")
    if environment == "prod" and not _same_rows(before["events"], original_catalog):
        raise ValueError("PROD next3 old catalog differs")


def _capture(db, decision, frozen, environment, decision_sha):
    database = db.scalar(text("SELECT current_database()")) if db.bind.dialect.name == "postgresql" else DATABASES[environment]
    if database != DATABASES[environment]:
        raise ValueError("database differs")
    ids = decision["approved_ids"] + decision["held_ids"]
    snapshot = _snapshot(db, ids, [row["id"] for row in frozen["players"]])
    for key in ("albums", "album_sources", "sources", "events", "aliases", "editions", "players"):
        if not _same_rows(snapshot[key], frozen[key]):
            raise ValueError(f"frozen {key} differs")
    if any(row["event_id"] is not None or row["event_edition_id"] is not None for row in snapshot["albums"]):
        raise ValueError("reviewed event/edition preimage differs")
    targets = decision["targets"]
    existing = targets["existing"]
    event = next((row for row in snapshot["events"] if row["id"] == existing["id"]), None)
    if event is None or event["canonical_name"] != existing["canonical_name"]:
        raise ValueError("existing event target catalog differs")
    new_names = [item["canonical_name"] for item in targets["create"]]
    keys = {_name_key(name) for name in new_names}
    if (len(keys) != 2 or any(_name_key(row["canonical_name"]) in keys for row in snapshot["events"])
            or any(_name_key(row["alias"]) in keys or _name_key(row["normalized_alias"]) in keys
                   for row in snapshot["aliases"])):
        raise ValueError("approved new event type collides")
    return {"format": "kifu-event-next514-exact-plan-v1", "environment": environment,
            "database": database, "decision_sha256": decision_sha,
            "frozen_file_sha256": FROZEN[environment][1], "targets": targets, "snapshot": snapshot,
            "counts": {"approved": len(decision["approved_ids"]), "held": len(decision["held_ids"])}}


def capture(engine, environment):
    decision, frozen, decision_sha = evidence(environment)
    with Session(engine) as db:
        if engine.dialect.name == "postgresql":
            db.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"))
        return _capture(db, decision, frozen, environment, decision_sha)


def _expected(plan, decision, targets):
    result = json.loads(json.dumps(plan["snapshot"]))
    albums = {row["id"]: row for row in result["albums"]}
    for row in decision["approved"]:
        albums[row["id"]]["event_id"] = targets[row["family_key"]]
    return result


def _verify_final(engine, decision, plan, targets, inserted_rows, applied):
    with Session(engine) as db:
        if engine.dialect.name == "postgresql":
            db.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"))
        current = _snapshot(db, decision["approved_ids"] + decision["held_ids"],
                            [row["id"] for row in plan["snapshot"]["players"]])
        expected = _expected(plan, decision, targets) if applied else plan["snapshot"]
        if applied:
            expected["events"] += inserted_rows
            expected["events"].sort(key=lambda row: row["id"])
        if current != expected:
            raise ValueError("independent posttransaction full scope differs")
        database = db.scalar(text("SELECT current_database()")) if engine.dialect.name == "postgresql" else plan["database"]
        if database != plan["database"]:
            raise ValueError("independent posttransaction database differs")


def run(engine, environment, plan, *, apply=False, plan_sha256=None, approved_plan_sha256=None):
    if apply and (not plan_sha256 or plan_sha256 != approved_plan_sha256):
        raise ValueError("separately approved plan SHA required")
    decision, frozen, decision_sha = evidence(environment)
    if plan.get("format") != "kifu-event-next514-exact-plan-v1" or plan.get("environment") != environment:
        raise ValueError("plan format/environment differs")
    with Session(engine) as db:
        tx = db.begin()
        try:
            if engine.dialect.name == "postgresql":
                db.execute(text("LOCK TABLE kifu_albums,kifu_album_sources,kifu_sources,kifu_events,"
                                "kifu_event_aliases,kifu_event_editions,kifu_players IN SHARE ROW EXCLUSIVE MODE"))
            if _capture(db, decision, frozen, environment, decision_sha) != plan:
                raise ValueError("full captured plan preimage differs")
            targets = {decision["targets"]["existing"]["family_key"]: decision["targets"]["existing"]["id"]}
            for item in decision["targets"]["create"]:
                event = KifuEvent(canonical_name=item["canonical_name"])
                db.add(event)
                db.flush()
                targets[item["family_key"]] = event.id
            for row in decision["approved"]:
                changed = db.execute(update(KifuAlbum).where(
                    KifuAlbum.id == row["id"], KifuAlbum.event_id.is_(None),
                    KifuAlbum.event_edition_id.is_(None), KifuAlbum.event == row["raw_preimage"]["event"],
                    KifuAlbum.date_played == row["raw_preimage"]["date_played"])
                    .values(event_id=targets[row["family_key"]]))
                if changed.rowcount != 1:
                    raise ValueError(f"event CAS failed: {row['id']}")
            db.flush()
            after = _snapshot(db, decision["approved_ids"] + decision["held_ids"],
                              [row["id"] for row in plan["snapshot"]["players"]])
            inserted = [row for row in after["events"] if row["id"] in
                        {targets[item["family_key"]] for item in decision["targets"]["create"]}]
            if len(inserted) != 2 or {row["id"]: row["canonical_name"] for row in inserted} != {
                    targets[item["family_key"]]: item["canonical_name"] for item in decision["targets"]["create"]}:
                raise ValueError("new event target binding differs")
            expected = _expected(plan, decision, targets)
            expected["events"] += inserted
            expected["events"].sort(key=lambda row: row["id"])
            if after != expected:
                raise ValueError("in-transaction full postimage differs")
            tx.commit() if apply else tx.rollback()
        except BaseException:
            tx.rollback()
            raise
    try:
        _verify_final(engine, decision, plan, targets, inserted, apply)
    except BaseException as exc:
        if apply:
            raise RuntimeError("commit succeeded; independent postcommit verification failed") from exc
        raise
    return {"committed": apply, "created_event_ids": targets if apply else {}, **plan["counts"]}


def evidence(environment):
    decision = _pinned(DECISION_PATH, DECISION_SHA)
    if decision.get("format") != "kifu-event-next514-independent-decision-v1":
        raise ValueError("independent decision format differs")
    for item in decision["inputs"].values():
        path, expected = item["path"], item["file_sha256"]
        raw = (ROOT / path).read_bytes()
        if hashlib.sha256(raw).hexdigest() != expected:
            raise ValueError(f"pinned evidence SHA differs: {path}")
    if len(decision["approved"]) != 474 or len(decision["held"]) != 40:
        raise ValueError("independent approved/HOLD count differs")
    for kind in ("approved", "held"):
        records, ids = decision[kind], decision[kind + "_ids"]
        if ([row["id"] for row in records] != ids or _digest(ids) != decision["held_id_sha256" if kind == "held" else "approved_id_sha256"]
                or _digest(records) != decision[kind + "_records_sha256"]):
            raise ValueError(f"independent {kind} member SHA differs")
    if len(set(decision["approved_ids"] + decision["held_ids"])) != 514 or set(decision["approved_ids"]) & set(decision["held_ids"]):
        raise ValueError("independent exact album partition differs")
    families = {item["family_key"]: item for item in decision["families"]}
    if ({key: item["canonical_name"] for key, item in families.items()} !=
            {"china_japan_short": "中日围棋对抗赛", "china_bawang": "中国围棋霸王战",
             "xin_tiyu": "中国新体育杯"}):
        raise ValueError("independent event type identities differ")
    existing = families["china_japan_short"]
    if existing["action"] != "reuse_existing_type" or existing["existing_event_id_by_environment"] != {
            "PROD": 75, "TEST": 75}:
        raise ValueError("existing event target differs")
    create = [families[key] for key in ("china_bawang", "xin_tiyu")]
    if any(item["action"] != "create_exact_type_if_absent" for item in create):
        raise ValueError("new event type action differs")
    for key, item in families.items():
        approved_ids = [row["id"] for row in decision["approved"] if row["family_key"] == key]
        held_ids = [row["id"] for row in decision["held"] if row["family_key"] == key]
        if (approved_ids != item["approved_ids"] or held_ids != item["held_ids"] or
                len(approved_ids) != item["approved_count"] or len(held_ids) != item["held_count"] or
                _digest(approved_ids) != item["approved_id_sha256"] or
                _digest(held_ids) != item["held_id_sha256"] or
                any(row["target_canonical_name"] != item["canonical_name"] for row in decision["approved"]
                    if row["family_key"] == key)):
            raise ValueError(f"independent family membership/target differs: {key}")
    decision = dict(decision)
    decision["targets"] = {"existing": {"family_key": "china_japan_short", "id": 75,
                                        "canonical_name": "中日围棋对抗赛"},
                           "create": [{"family_key": item["family_key"], "canonical_name": item["canonical_name"]}
                                      for item in create]}
    frozen_by_env = {}
    for candidate in DATABASES:
        info = decision["environments"][candidate.upper()]
        if (info["database"] != DATABASES[candidate] or
                info["preimage"]["file_sha256"] != FROZEN[candidate][1] or
                info["initial_preimage"]["file_sha256"] != PRE_NEXT3[candidate][1] or
                info["next3_catalog_rebase"]["applied_plan"]["file_sha256"] != NEXT3_PLAN[candidate][1]):
            raise ValueError("independent environment evidence pin differs")
        before = _pinned(*PRE_NEXT3[candidate])
        frozen = _pinned(*FROZEN[candidate])
        applied = _pinned(*NEXT3_PLAN[candidate])
        _validate_next3_catalog_rebase(candidate, before, frozen, applied)
        observed_additions = frozen["events"][74:]
        approved_additions = info["next3_catalog_rebase"]["catalog_rows_added_since_next3_plan"]
        if len(observed_additions) != len(approved_additions) or any(
                not _equal(a, b) for a, b in zip(observed_additions, approved_additions)):
            raise ValueError("independent next3 catalog addition differs")
        if len(frozen["albums"]) != 514 or {row["id"] for row in frozen["albums"]} != set(decision["approved_ids"] + decision["held_ids"]):
            raise ValueError("frozen exact album scope differs")
        for key, checksum in (("albums", "album_rows_sha256"), ("album_sources", "album_sources_sha256"),
                              ("events", "catalog_preimage_sha256"), ("aliases", "alias_preimage_sha256"),
                              ("editions", "edition_preimage_sha256"), ("sources", "sources_preimage_sha256"),
                              ("players", "players_preimage_sha256")):
            if _digest(frozen[key]) != info[checksum]:
                raise ValueError(f"independent frozen {key} SHA differs")
        album_by_id = {row["id"]: row for row in frozen["albums"]}
        sources_by_album = {}
        for row in frozen["album_sources"]:
            sources_by_album.setdefault(row["album_id"], []).append(row)
        for record in decision["approved"] + decision["held"]:
            album = album_by_id[record["id"]]
            record_env = record["environments"][candidate.upper()]
            if (_digest(album) != record_env["album_preimage_sha256"] or
                    _digest(sources_by_album.get(record["id"], [])) != record_env["album_sources_preimage_sha256"] or
                    hashlib.sha256(album["sgf_content"].encode()).hexdigest() != record["sgf_sha256"] or
                    album["event_id"] is not None or album["event_edition_id"] is not None):
                raise ValueError(f"independent frozen album/source identity differs: {record['id']}")
            for key, value in record["raw_preimage"].items():
                if album[key] != value:
                    raise ValueError(f"independent raw preimage differs: {record['id']}/{key}")
        frozen_by_env[candidate] = frozen
    return decision, frozen_by_env[environment], DECISION_SHA
