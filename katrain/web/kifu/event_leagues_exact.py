"""Exact, independently reviewed six-league event type links."""

import gzip
import hashlib
import json
from datetime import datetime
from pathlib import Path
import re

from sqlalchemy import select, text, update
from sqlalchemy.orm import Session

from katrain.web.core.models_db import (
    KifuAlbum, KifuAlbumSource, KifuEvent, KifuEventAlias, KifuEventEdition, KifuSource,
)


ROOT = Path(__file__).resolve().parents[3]
DECISION_PATH = "docs/resource/kifu-event-after743-leagues-independent-decision-astra-2026-10-04.json"
DECISION_SHA = "8a082ab706fa6a21129baf47fd8c904088e509617d2dc5fde85b09568377e8aa"
NEXT_EVENT_REBASE_PATH = "docs/resource/kifu-player-canonical-three-next-event-rebase-independent-decision-2026-10-04.json"
NEXT_EVENT_REBASE_SHA = "aa2e104ca58ee2f884a1566fe38b664d74298960ed3616af1d51c6b3625d78b9"
PLAYER_REVIEWS = {
    "test": ("docs/resource/kifu-player-exact-canonical-three-frozen-review-test-2026-10-04.json",
             "e2e4599263d88cf931cf9e0ac454b1f46fe7353fbc11af918c82ff7d8f8d2092"),
    "prod": ("docs/resource/kifu-player-exact-canonical-three-frozen-review-prod-2026-10-04.json",
             "49379c3cca58c3a65b732c7775c22a251d04455d589847f4a9ec03be58f59ef6"),
}
DATABASES = {"test": "katrain_db", "prod": "katrain_prod_20260725"}
ALBUM_COLUMNS = tuple(column.name for column in KifuAlbum.__table__.columns if column.name != "sgf_content")
ANCILLARY = {
    "album_sources": KifuAlbumSource,
    "sources": KifuSource,
    "catalog": KifuEvent,
    "aliases": KifuEventAlias,
    "editions": KifuEventEdition,
}


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()


def pinned(path, sha):
    data = (ROOT / path).read_bytes()
    if hashlib.sha256(data).hexdigest() != sha:
        raise ValueError(f"pinned evidence SHA differs: {path}")
    return json.loads(gzip.decompress(data) if data[:2] == b"\x1f\x8b" else data)


def evidence(environment):
    decision = pinned(DECISION_PATH, DECISION_SHA)
    if decision.get("format") != "kifu-event-after743-six-leagues-independent-decision-v1":
        raise ValueError("decision format differs")
    inputs = decision["inputs"]
    pinned(inputs["producer"]["path"], inputs["producer"]["file_sha256"])
    frozen = pinned(inputs["full_PROD_preimage"]["path"], inputs["full_PROD_preimage"]["file_sha256"])
    pinned(inputs["null_inventory"]["path"], inputs["null_inventory"]["file_sha256"])
    next_event = pinned(NEXT_EVENT_REBASE_PATH, NEXT_EVENT_REBASE_SHA)
    if (next_event["committed_target_binding"]["PROD"]["china_japan_regular_exchange"] != 75
            or next_event["committed_target_binding"]["TEST"]["china_japan_regular_exchange"] != 75):
        raise ValueError("intervening event catalog decision differs")
    for records, ids, count in (("approved", "approved_ids", 6810), ("held", "held_ids", 1784)):
        if len(decision[records]) != count or len(decision[ids]) != count:
            raise ValueError(f"{records} count differs")
        if digest(decision[records]) != decision[f"{records}_records_sha256"] or digest(decision[ids]) != decision[("approved_id" if records == "approved" else "held_id") + "_sha256"]:
            raise ValueError(f"{records} member SHA differs")
        if [row["id"] for row in decision[records]] != decision[ids]:
            raise ValueError(f"{records} IDs differ")
    all_ids = set(decision["approved_ids"]) | set(decision["held_ids"])
    if len(all_ids) != 8594 or set(decision["approved_ids"]) & set(decision["held_ids"]):
        raise ValueError("reviewed partition differs")
    frozen_albums = {row["id"]: row for row in frozen["albums"]}
    if set(frozen_albums) != all_ids:
        raise ValueError("frozen album scope differs")
    for row in decision["approved"] + decision["held"]:
        original = frozen_albums[row["id"]]
        if (row["event"] != original["event"] or row["date_played"] != original["date_played"]
                or row["sgf_sha256"] != hashlib.sha256(original["sgf_content"].encode()).hexdigest()
                or original["event_id"] is not None or original["event_edition_id"] is not None):
            raise ValueError(f"frozen reviewed identity differs: {row['id']}")
    names = {item["target_event_id_at_PROD_review"]: item["canonical_name"] for item in decision["families"]}
    if names != {41: "中国围棋甲级联赛", 42: "中国女子围棋甲级联赛", 50: "韩国围棋联赛",
                 51: "韩国女子围棋联赛", 52: "韩国元老围棋联赛"}:
        raise ValueError("approved family targets differ")
    if any(row["target_event_id"] not in names or row["target_canonical_name"] != names[row["target_event_id"]]
           for row in decision["approved"]):
        raise ValueError("approved row target differs")
    review_path, review_sha = PLAYER_REVIEWS[environment]
    player_review = pinned(review_path, review_sha)
    if player_review["environment"] != environment.upper() or len(player_review["candidate_slots"]) != 1529:
        raise ValueError("three-player review differs")
    player_before = {row["id"]: row for row in player_review["live_album_preimage"]}
    player_slots = {}
    for album_id, side, raw, date, old_fk, target in player_review["candidate_slots"]:
        if album_id in all_ids:
            player_slots[(album_id, side + "_player_id")] = (old_fk, target)
    for row in player_review["held_slots"]:
        album_id = row["album_id"]
        if album_id in all_ids:
            player_slots[(album_id, row["side"] + "_player_id")] = (None, None)
    # The same frozen raw/SGF identity must underlie the player decision where scopes intersect.
    for album_id in set(player_before) & all_ids:
        album = frozen_albums[album_id]
        other = player_before[album_id]
        for key in ("event", "date_played", "date_sort", "source", "source_path",
                    "player_black", "player_white", "result", "duplicate_of_id"):
            if album[key] != other[key]:
                raise ValueError(f"overlapping player review identity differs: {album_id}/{key}")
        if hashlib.sha256(album["sgf_content"].encode()).hexdigest() != other["sgf_sha256"]:
            raise ValueError(f"overlapping player review SGF differs: {album_id}")
    return decision, frozen, player_slots


def _value(value):
    return value.isoformat() if hasattr(value, "isoformat") else value


def _rows(db, model, columns=None, criterion=None):
    query = select(model)
    if criterion is not None:
        query = query.where(criterion)
    names = columns or [column.name for column in model.__table__.columns]
    return sorted(({key: _value(getattr(obj, key)) for key in names} for obj in db.scalars(query)),
                  key=lambda row: row["id"])


def _snapshot(db, ids):
    albums = _rows(db, KifuAlbum, ALBUM_COLUMNS + ("sgf_content",), KifuAlbum.id.in_(ids))
    for row in albums:
        row["sgf_sha256"] = hashlib.sha256(row.pop("sgf_content").encode()).hexdigest()
    album_sources = _rows(db, KifuAlbumSource, criterion=KifuAlbumSource.album_id.in_(ids))
    return {"albums": albums, "album_sources": album_sources,
            "sources": _rows(db, KifuSource),
            "catalog": _rows(db, KifuEvent), "aliases": _rows(db, KifuEventAlias),
            "editions": _rows(db, KifuEventEdition)}


def _same(a, b):
    if set(a) != set(b):
        return False
    def parsed(value):
        value = re.sub(r"\.(\d{1,5})(?=[+-]\d{2}:\d{2}$)",
                       lambda match: "." + match.group(1).ljust(6, "0"), value)
        result = datetime.fromisoformat(value)
        if result.tzinfo is None:
            raise ValueError("timestamp must include timezone")
        return result
    return all(parsed(a[key]) == parsed(b[key]) if key == "created_at" else a[key] == b[key]
               for key in a)


def _frozen_identity(snapshot, frozen, player_slots, environment):
    current = {row["id"]: row for row in snapshot["albums"]}
    if set(current) != {row["id"] for row in frozen["albums"]}:
        raise ValueError("frozen album scope differs")
    for original in frozen["albums"]:
        album_id = original["id"]
        row = current[album_id]
        if row["event_id"] is not None or row["event_edition_id"] is not None:
            raise ValueError(f"reviewed NULL event/edition differs: {album_id}")
        if row["sgf_sha256"] != hashlib.sha256(original["sgf_content"].encode()).hexdigest():
            raise ValueError(f"frozen SGF differs: {album_id}")
        for key in ALBUM_COLUMNS:
            if key in ("black_player_id", "white_player_id"):
                if (album_id, key) in player_slots:
                    old, new = player_slots[(album_id, key)]
                    if environment == "prod" and original[key] != old:
                        raise ValueError(f"three-player old FK differs: {album_id}/{key}")
                    if row[key] != new:
                        raise ValueError(f"three-player post FK differs: {album_id}/{key}")
                elif environment == "prod" and row[key] != original[key]:
                    raise ValueError(f"unreviewed player FK drift: {album_id}/{key}")
            elif key == "created_at":
                if environment == "prod" and not _same({key: row[key]}, {key: original[key]}):
                    raise ValueError(f"frozen timestamp differs: {album_id}")
            elif row[key] != original[key]:
                raise ValueError(f"frozen album identity differs: {album_id}/{key}")
    if environment == "prod":
        for key in ("album_sources", "sources"):
            if len(snapshot[key]) != len(frozen[key]) or any(not _same(a, b) for a, b in zip(snapshot[key], frozen[key])):
                raise ValueError(f"frozen {key} differs")
    else:
        def source_identity(data):
            keys = {row["id"]: row["source_key"] for row in data["sources"]}
            return sorted((row["album_id"], row["origin_path"], row["match_method"], keys[row["source_id"]])
                          for row in data["album_sources"])
        if source_identity(snapshot) != source_identity(frozen):
            raise ValueError("frozen TEST source identity differs")


def _targets(snapshot, decision, environment):
    names = {item["target_event_id_at_PROD_review"]: item["canonical_name"] for item in decision["families"]}
    result = {}
    for old_id, name in names.items():
        owners = [row for row in snapshot["catalog"] if row["canonical_name"] == name]
        if len(owners) != 1 or (environment == "prod" and owners[0]["id"] != old_id):
            raise ValueError(f"event catalog target differs: {name}")
        result[str(old_id)] = owners[0]["id"]
    return result


def _capture(db, environment, decision, frozen, player_slots):
    if environment not in DATABASES:
        raise ValueError("unknown environment")
    database = db.scalar(text("SELECT current_database()")) if db.bind.dialect.name == "postgresql" else DATABASES[environment]
    if database != DATABASES[environment]:
        raise ValueError("database differs")
    ids = decision["approved_ids"] + decision["held_ids"]
    snapshot = _snapshot(db, ids)
    _frozen_identity(snapshot, frozen, player_slots, environment)
    targets = _targets(snapshot, decision, environment)
    if environment == "prod":
        for key in ("catalog", "aliases", "editions"):
            if len(snapshot[key]) != len(frozen[key]) or any(not _same(a, b) for a, b in zip(snapshot[key], frozen[key])):
                raise ValueError(f"frozen {key} differs")
    return {"format": "kifu-event-six-leagues-exact-plan-v1", "environment": environment, "database": database,
            "decision_sha256": DECISION_SHA, "approved_id_sha256": decision["approved_id_sha256"],
            "held_id_sha256": decision["held_id_sha256"], "targets": targets, "snapshot": snapshot,
            "counts": {"approved": 6810, "held": 1784}}


def capture(engine, environment):
    decision, frozen, player_slots = evidence(environment)
    with Session(engine) as db:
        if engine.dialect.name == "postgresql":
            db.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"))
        return _capture(db, environment, decision, frozen, player_slots)


def _expected(plan, decision, applied):
    expected = json.loads(json.dumps(plan["snapshot"]))
    if applied:
        by_id = {row["id"]: row for row in expected["albums"]}
        for row in decision["approved"]:
            by_id[row["id"]]["event_id"] = plan["targets"][str(row["target_event_id"])]
    return expected


def _verify_final(engine, plan, decision, applied):
    with Session(engine) as db:
        if engine.dialect.name == "postgresql":
            db.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"))
        if _snapshot(db, decision["approved_ids"] + decision["held_ids"]) != _expected(plan, decision, applied):
            raise ValueError("independent posttransaction full scope differs")
        database = db.scalar(text("SELECT current_database()")) if engine.dialect.name == "postgresql" else plan["database"]
        if database != plan["database"]:
            raise ValueError("independent posttransaction database differs")


def run(engine, environment, plan, *, apply=False, plan_sha256=None, approved_plan_sha256=None):
    if apply and (not plan_sha256 or plan_sha256 != approved_plan_sha256):
        raise ValueError("separately approved plan SHA required")
    decision, frozen, player_slots = evidence(environment)
    if plan.get("format") != "kifu-event-six-leagues-exact-plan-v1" or plan.get("environment") != environment:
        raise ValueError("plan format/environment differs")
    with Session(engine) as db:
        tx = db.begin()
        try:
            if engine.dialect.name == "postgresql":
                db.execute(text("LOCK TABLE kifu_albums,kifu_album_sources,kifu_sources,kifu_events,"
                                "kifu_event_aliases,kifu_event_editions IN SHARE ROW EXCLUSIVE MODE"))
            if _capture(db, environment, decision, frozen, player_slots) != plan:
                raise ValueError("full captured plan preimage differs")
            for row in decision["approved"]:
                album_id = row["id"]
                changed = db.execute(update(KifuAlbum).where(
                    KifuAlbum.id == album_id, KifuAlbum.event_id.is_(None),
                    KifuAlbum.event_edition_id.is_(None), KifuAlbum.event == row["event"],
                    KifuAlbum.date_played == row["date_played"])
                    .values(event_id=plan["targets"][str(row["target_event_id"])]))
                if changed.rowcount != 1:
                    raise ValueError(f"event CAS failed: {album_id}")
            db.flush()
            if _snapshot(db, decision["approved_ids"] + decision["held_ids"]) != _expected(plan, decision, True):
                raise ValueError("in-transaction full postimage differs")
            tx.commit() if apply else tx.rollback()
        except BaseException:
            tx.rollback()
            raise
    try:
        _verify_final(engine, plan, decision, apply)
    except BaseException as exc:
        if apply:
            raise RuntimeError("commit succeeded; independent postcommit verification failed") from exc
        raise
    return {"committed": apply, **plan["counts"]}
