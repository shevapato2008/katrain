"""Exact, independently reviewed China Ahan event type links (793 approve, 8 HOLD)."""

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
from katrain.web.kifu.event_next3_exact import _digest, _equal, _name_key, _rows

ROOT = Path(__file__).resolve().parents[3]
DECISION_PATH = "docs/resource/kifu-event-china-ahan-independent-decision-astra-2026-10-04.json"
DECISION_SHA = "53c88b3efb87e0d331aaa27a9a35512129bc5d6896c378d1f0da4f6769f1f891"
DATABASES = {"test": "katrain_db", "prod": "katrain_prod_20260725"}
FROZEN = {
    "test": ("docs/resource/kifu-event-china-ahan-TEST-independent-preimage-astra-2026-10-04.json.gz",
             "faad5227926d3b94adb82c0d45f300b8fba44be0e14adb7ed5c695dd3767bc6d"),
    "prod": ("docs/resource/kifu-event-china-ahan-PROD-independent-preimage-astra-2026-10-04.json.gz",
             "c0c7741efd5fd3ecd43d701165cce578ad69bd40a5b78b9b9bbbd8010a398ffa"),
}
TARGET = "中国阿含桐山杯"
FAMILY = "china_ahan_tongshan"
PLAYER_DECISION = ("docs/resource/kifu-player-new33-secondbatch-independent-slot-decision-astra-2026-10-04.json",
                   "dde6d06c6ada0b1520a9854a212a8a28de3e72809abffe2ccc2945e44bb795fb")
PLAYER_RECEIPT = ("docs/resource/kifu-player-new33-secondbatch-applied-2026-10-04.md",
                  "14eb870851cd0e6c3404491f7e321900ed432d4f8c762923e95affaaaecc488f")
PLAYER_PLAN = {
    "test": ("docs/resource/kifu-player-new33-secondbatch-TEST-applied-plan-2026-10-04.json.gz",
             "84986ba4751a59449d1f7befc7e86993d47cd885849d83c82b2fb6193f6e8706"),
    "prod": ("docs/resource/kifu-player-new33-secondbatch-PROD-applied-plan-2026-10-04.json.gz",
             "58147904aa8bc84258948cfe3f4711ed10d5105e0f1b7aab497289ca99f05adc"),
}
PLAYER_NEW_ID_START = {"test": 12588, "prod": 6819}
SNAPSHOT_KEYS = ("albums", "album_sources", "sources", "events", "aliases", "editions", "players",
                 "prior_hold_event_slots")


def _pinned(path, expected):
    raw = (ROOT / path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError(f"pinned evidence SHA differs: {path}")
    return json.loads(gzip.decompress(raw) if raw[:2] == b"\x1f\x8b" else raw)


def _same_rows(current, frozen):
    return len(current) == len(frozen) and all(_equal(a, b) for a, b in zip(current, frozen))


def _hold_slots(db, ids):
    rows = db.execute(select(KifuAlbum.id, KifuAlbum.event_id, KifuAlbum.event_edition_id)
                      .where(KifuAlbum.id.in_(ids)).order_by(KifuAlbum.id)).all()
    return [{"id": id_, "event_id": event_id, "event_edition_id": edition_id}
            for id_, event_id, edition_id in rows]


def _snapshot(db, ids, player_ids, prior_hold_ids, new_player_ids=()):
    return {"albums": _rows(db, KifuAlbum, KifuAlbum.id.in_(ids)),
            "album_sources": _rows(db, KifuAlbumSource, KifuAlbumSource.album_id.in_(ids)),
            "sources": _rows(db, KifuSource), "events": _rows(db, KifuEvent),
            "aliases": _rows(db, KifuEventAlias), "editions": _rows(db, KifuEventEdition),
            "players": _rows(db, KifuPlayer, KifuPlayer.id.in_(player_ids)),
            "prior_hold_event_slots": _hold_slots(db, prior_hold_ids),
            "new33_target_players": _rows(db, KifuPlayer, KifuPlayer.id.in_(new_player_ids))}


def _collision_key(value):
    return _name_key(value).replace("體", "体")


def _player_rebase(decision, frozen, environment):
    player_decision = _pinned(*PLAYER_DECISION)
    if hashlib.sha256((ROOT / PLAYER_RECEIPT[0]).read_bytes()).hexdigest() != PLAYER_RECEIPT[1]:
        raise ValueError("new33 applied receipt SHA differs")
    plan = _pinned(*PLAYER_PLAN[environment])
    if (player_decision["format"] != "kifu-player-new33-independent-exact-slot-decision-secondbatch-v1" or
            plan["database"] != DATABASES[environment] or plan["environment"] != environment or
            plan["decision_sha256"] != PLAYER_DECISION[1] or len(player_decision["identities"]) != 16 or
            len(player_decision["approved_slots"]) != 2755):
        raise ValueError("new33 applied evidence identity differs")
    names = [row["chinese_canonical"] for row in player_decision["identities"]]
    targets = {name: PLAYER_NEW_ID_START[environment] + index for index, name in enumerate(names)}
    frozen_by_id = {row["id"]: row for row in frozen["albums"]}
    plan_by_id = {row["id"]: row for row in plan["snapshot"]["albums"]}
    expected = json.loads(json.dumps(frozen["albums"]))
    expected_by_id = {row["id"]: row for row in expected}
    overlap = [row for row in player_decision["approved_slots"] if row["album_id"] in frozen_by_id]
    if len(overlap) != 24 or len({row["album_id"] for row in overlap}) != 24:
        raise ValueError("new33 Ahan overlap differs")
    for row in overlap:
        album_id, side = row["album_id"], row["side"]
        if (not _equal(frozen_by_id[album_id], plan_by_id[album_id]) or row["old_fk"] is not None or
                row["target_canonical_name"] not in targets or side not in ("black", "white") or
                frozen_by_id[album_id][side + "_player_id"] is not None or
                row["raw"] != frozen_by_id[album_id]["player_" + side]):
            raise ValueError(f"new33 Ahan shared preimage differs: {album_id}")
        expected_by_id[album_id][side + "_player_id"] = targets[row["target_canonical_name"]]
    return expected, targets


def evidence(environment):
    if environment not in DATABASES:
        raise ValueError("unknown environment")
    decision = _pinned(DECISION_PATH, DECISION_SHA)
    if decision.get("format") != "kifu-event-china-ahan-independent-decision-v1":
        raise ValueError("independent decision format differs")
    for item in decision["inputs"].values():
        raw = (ROOT / item["path"]).read_bytes()
        if hashlib.sha256(raw).hexdigest() != item["file_sha256"]:
            raise ValueError(f"pinned evidence SHA differs: {item['path']}")
    if (len(decision["approved"]) != 793 or len(decision["held"]) != 8 or
            len(decision["prior_hold_union_ids"]) != 4265 or
            _digest(decision["prior_hold_union_ids"]) != decision["prior_hold_union_sha256"]):
        raise ValueError("independent scope differs")
    for kind in ("approved", "held"):
        records, ids = decision[kind], decision[kind + "_ids"]
        if (len(records) != len(ids) or [row["id"] for row in records] != ids or
                _digest(ids) != decision[kind + "_id_sha256"] or
                _digest(records) != decision[kind + "_records_sha256"]):
            raise ValueError(f"independent {kind} member SHA differs")
    ids = decision["approved_ids"] + decision["held_ids"]
    if len(set(ids)) != 801 or set(ids) & set(decision["prior_hold_union_ids"]):
        raise ValueError("independent album/HOLD partition differs")
    if (len(decision["families"]) != 1 or decision["families"][0]["family_key"] != FAMILY or
            decision["families"][0]["canonical_name"] != TARGET or
            decision["families"][0]["action"] != "create_exact_type_if_absent" or
            decision["families"][0]["approved_ids"] != decision["approved_ids"] or
            decision["families"][0]["held_ids"] != decision["held_ids"]):
        raise ValueError("independent target/family differs")
    for row in decision["approved"] + decision["held"]:
        expected_name = TARGET if row["decision"] == "APPROVE_EVENT_TYPE_ONLY" else None
        if row["family_key"] != FAMILY or row["target_canonical_name"] != expected_name or row["target_event_edition_id"] is not None:
            raise ValueError("independent row target differs")
    frozen_by_env = {}
    rebases = {}
    for candidate in DATABASES:
        info = decision["environments"][candidate.upper()]
        if (info["database"] != DATABASES[candidate] or info["preimage"]["path"] != FROZEN[candidate][0] or
                info["preimage"]["file_sha256"] != FROZEN[candidate][1]):
            raise ValueError("independent environment evidence pin differs")
        frozen = _pinned(*FROZEN[candidate])
        if len(frozen["albums"]) != 801 or {r["id"] for r in frozen["albums"]} != set(ids):
            raise ValueError("frozen exact album scope differs")
        for key, checksum in (("albums", "album_rows_sha256"), ("album_sources", "album_sources_sha256"),
                              ("events", "catalog_preimage_sha256"), ("aliases", "alias_preimage_sha256"),
                              ("editions", "edition_preimage_sha256"), ("sources", "sources_preimage_sha256"),
                              ("players", "players_preimage_sha256"),
                              ("prior_hold_event_slots", "prior_hold_event_slots_sha256")):
            if _digest(frozen[key]) != info[checksum]:
                raise ValueError(f"independent frozen {key} SHA differs")
        if ([r["id"] for r in frozen["prior_hold_event_slots"]] != decision["prior_hold_union_ids"] or
                any(r["event_id"] is not None or r["event_edition_id"] is not None
                    for r in frozen["prior_hold_event_slots"])):
            raise ValueError("frozen prior HOLD scope differs")
        albums = {r["id"]: r for r in frozen["albums"]}
        sources_by_album = {}
        for source in frozen["album_sources"]:
            sources_by_album.setdefault(source["album_id"], []).append(source)
        for record in decision["approved"] + decision["held"]:
            album = albums[record["id"]]
            record_env = record["environments"][candidate.upper()]
            if (_digest(album) != record_env["album_preimage_sha256"] or
                    _digest(sources_by_album.get(record["id"], [])) != record_env["album_sources_preimage_sha256"] or
                    hashlib.sha256(album["sgf_content"].encode()).hexdigest() != record["sgf_sha256"] or
                    album["event_id"] is not None or album["event_edition_id"] is not None or
                    any(album[key] != value for key, value in record["raw_preimage"].items())):
                raise ValueError(f"independent album/source preimage differs: {record['id']}")
        rebases[candidate] = _player_rebase(decision, frozen, candidate)
        frozen_by_env[candidate] = frozen
    return decision, frozen_by_env[environment], DECISION_SHA, rebases[environment]


def _capture(db, decision, frozen, environment, decision_sha, rebase):
    database = db.scalar(text("SELECT current_database()")) if db.bind.dialect.name == "postgresql" else DATABASES[environment]
    if database != DATABASES[environment]:
        raise ValueError("database differs")
    snapshot = _snapshot(db, decision["approved_ids"] + decision["held_ids"],
                         [row["id"] for row in frozen["players"]], decision["prior_hold_union_ids"],
                         rebase[1].values())
    for key in SNAPSHOT_KEYS:
        expected = rebase[0] if key == "albums" else frozen[key]
        if not _same_rows(snapshot[key], expected):
            raise ValueError(f"frozen {key} differs")
    if ({row["id"]: row["canonical_name"] for row in snapshot["new33_target_players"]} !=
            {id_: name for name, id_ in rebase[1].items()}):
        raise ValueError("new33 target player catalog differs")
    if any(row["event_id"] is not None or row["event_edition_id"] is not None for row in snapshot["albums"]):
        raise ValueError("reviewed event/edition preimage differs")
    target_key = _collision_key(TARGET)
    if (any(_collision_key(row["canonical_name"]) == target_key for row in snapshot["events"]) or
            any(_collision_key(row["alias"]) == target_key or
                _collision_key(row["normalized_alias"]) == target_key for row in snapshot["aliases"])):
        raise ValueError("approved new event type collides")
    return {"format": "kifu-event-china-ahan-exact-plan-v1", "environment": environment,
            "database": database, "decision_sha256": decision_sha,
            "frozen_file_sha256": FROZEN[environment][1],
            "new33_applied_plan_sha256": PLAYER_PLAN[environment][1], "target_canonical_name": TARGET,
            "snapshot": snapshot, "counts": {"approved": 793, "held": 8, "prior_held": 4265}}


def capture(engine, environment):
    decision, frozen, sha, rebase = evidence(environment)
    with Session(engine) as db:
        if engine.dialect.name == "postgresql":
            db.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"))
        return _capture(db, decision, frozen, environment, sha, rebase)


def _expected(plan, decision, target_id):
    result = json.loads(json.dumps(plan["snapshot"]))
    albums = {row["id"]: row for row in result["albums"]}
    for row in decision["approved"]:
        albums[row["id"]]["event_id"] = target_id
    return result


def _verify_final(engine, decision, plan, target_id, inserted, applied):
    with Session(engine) as db:
        if engine.dialect.name == "postgresql":
            db.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"))
        current = _snapshot(db, decision["approved_ids"] + decision["held_ids"],
                            [row["id"] for row in plan["snapshot"]["players"]], decision["prior_hold_union_ids"],
                            [row["id"] for row in plan["snapshot"]["new33_target_players"]])
        expected = _expected(plan, decision, target_id) if applied else plan["snapshot"]
        if applied:
            expected["events"] += [inserted]
            expected["events"].sort(key=lambda row: row["id"])
        if current != expected:
            raise ValueError("independent posttransaction full scope differs")
        database = db.scalar(text("SELECT current_database()")) if engine.dialect.name == "postgresql" else plan["database"]
        if database != plan["database"]:
            raise ValueError("independent posttransaction database differs")


def run(engine, environment, plan, *, apply=False, plan_sha256=None, approved_plan_sha256=None):
    if apply and (not plan_sha256 or plan_sha256 != approved_plan_sha256):
        raise ValueError("separately approved plan SHA required")
    decision, frozen, sha, rebase = evidence(environment)
    if plan.get("format") != "kifu-event-china-ahan-exact-plan-v1" or plan.get("environment") != environment:
        raise ValueError("plan format/environment differs")
    with Session(engine) as db:
        tx = db.begin()
        try:
            if engine.dialect.name == "postgresql":
                db.execute(text("LOCK TABLE kifu_albums,kifu_album_sources,kifu_sources,kifu_events,"
                                "kifu_event_aliases,kifu_event_editions,kifu_players IN SHARE ROW EXCLUSIVE MODE"))
            if _capture(db, decision, frozen, environment, sha, rebase) != plan:
                raise ValueError("full captured plan preimage differs")
            event = KifuEvent(canonical_name=TARGET)
            db.add(event)
            db.flush()
            target_id = event.id
            for row in decision["approved"]:
                changed = db.execute(update(KifuAlbum).where(
                    KifuAlbum.id == row["id"], KifuAlbum.event_id.is_(None),
                    KifuAlbum.event_edition_id.is_(None), KifuAlbum.event == row["raw_preimage"]["event"],
                    KifuAlbum.date_played == row["raw_preimage"]["date_played"])
                    .values(event_id=target_id))
                if changed.rowcount != 1:
                    raise ValueError(f"event CAS failed: {row['id']}")
            db.flush()
            after = _snapshot(db, decision["approved_ids"] + decision["held_ids"],
                              [row["id"] for row in plan["snapshot"]["players"]], decision["prior_hold_union_ids"],
                              [row["id"] for row in plan["snapshot"]["new33_target_players"]])
            inserted_rows = [row for row in after["events"] if row["id"] == target_id]
            if len(inserted_rows) != 1 or inserted_rows[0]["canonical_name"] != TARGET:
                raise ValueError("new event target binding differs")
            inserted = inserted_rows[0]
            expected = _expected(plan, decision, target_id)
            expected["events"] += [inserted]
            expected["events"].sort(key=lambda row: row["id"])
            if after != expected:
                raise ValueError("in-transaction full postimage differs")
            tx.commit() if apply else tx.rollback()
        except BaseException:
            tx.rollback()
            raise
    try:
        _verify_final(engine, decision, plan, target_id, inserted, apply)
    except BaseException as exc:
        if apply:
            raise RuntimeError("commit succeeded; independent postcommit verification failed") from exc
        raise
    return {"committed": apply, "created_event_id": target_id if apply else None, **plan["counts"]}
