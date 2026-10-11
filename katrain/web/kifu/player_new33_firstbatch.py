"""Exact first-batch new33 player links, with pinned next3 event rebase."""

import gzip
import hashlib
import json
from pathlib import Path

from sqlalchemy import or_, select, text, update
from sqlalchemy.orm import Session

from katrain.web.core.models_db import (
    KifuAlbum, KifuAlbumSource, KifuEvent, KifuEventEdition, KifuPlayer,
    KifuPlayerAlias, KifuPlayerName, KifuRawPlayerValue, KifuSource,
)


ROOT = Path(__file__).resolve().parents[3]
DECISION_PATH = "docs/resource/kifu-player-new33-firstbatch-independent-slot-decision-2026-10-04.json"
DECISION_SHA = "81dfb98ae8afe8ffbaa4fab5154dd31017df368af96b50773e57c03e98e94433"
SUPPLEMENT_PATH = "docs/resource/kifu-player-new33-firstbatch-next3-exact-rebase-2026-10-04.json"
SUPPLEMENT_SHA = "f2716b79e9b053434a7e3bd118bf8c46413752ddfe0878afdc444379ffa47021"
DATABASES = {"test": "katrain_db", "prod": "katrain_prod_20260725"}
FORMAT = "kifu-player-new33-firstbatch-exact-plan-v1"
TABLES = {
    "sources": KifuSource, "events": KifuEvent, "event_editions": KifuEventEdition,
    "players": KifuPlayer, "aliases": KifuPlayerAlias, "names": KifuPlayerName,
}


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _digest(value):
    return _sha(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode())


def _pin(path, expected):
    raw = (ROOT / path).read_bytes()
    if _sha(raw) != expected:
        raise ValueError(f"pinned evidence SHA differs: {path}")
    return json.loads(gzip.decompress(raw) if raw[:2] == b"\x1f\x8b" else raw) if path.endswith((".json", ".json.gz")) else raw


def _member_hash(rows):
    return _digest([[row["album_id"], row["side"], row["raw"]] for row in rows])


def _base(row, columns):
    return {key: row[key] for key in columns}


def _sorted(rows):
    return sorted(rows, key=lambda row: row["id"])


def _same_rows(actual, expected, label):
    if _sorted(actual) != _sorted(expected):
        raise ValueError(f"{label} preimage differs")


def evidence(environment):
    if environment not in DATABASES:
        raise ValueError("unknown environment")
    decision = _pin(DECISION_PATH, DECISION_SHA)
    supplement = _pin(SUPPLEMENT_PATH, SUPPLEMENT_SHA)
    if (decision["format"] != "kifu-player-new33-independent-exact-slot-decision-firstbatch-v1"
            or supplement["format"] != "kifu-player-new33-firstbatch-next3-exact-rebase-v1"
            or supplement["base_slot_decision"]["file_sha256"] != DECISION_SHA):
        raise ValueError("decision/supplement identity differs")
    for item in decision["inputs"].values():
        _pin(item["path"], item["file_sha256"])
    for key in ("event_identity_decision", "event_applied_receipt"):
        item = supplement[key]
        _pin(item["path"], item["file_sha256"])
    frozen_info = decision["inputs"]["exact_capture"]
    if supplement["original_exact_capture"]["file_sha256"] != frozen_info["file_sha256"]:
        raise ValueError("original capture pin differs")
    frozen = _pin(frozen_info["path"], frozen_info["file_sha256"])
    approved, held = decision["approved_slots"], decision["held_slots"]
    if (len(approved), len(held), _member_hash(approved), _member_hash(held)) != (
            1451, 5922, decision["approved_slot_members_sha256"], decision["held_slot_members_sha256"]):
        raise ValueError("approved/HOLD exact membership differs")
    target_fields = ("album_id", "side", "raw", "target_canonical_name", "target_ids")
    if _digest([{key: row[key] for key in target_fields} for row in approved]) != decision[
            "approved_slot_targets_sha256"]:
        raise ValueError("approved target membership differs")
    expected = {}
    for candidate in DATABASES:
        source = frozen[candidate]
        if source["database"] != DATABASES[candidate] or len(source["albums"]) != 7168 or len(source["slots"]) != 7373:
            raise ValueError("frozen environment or full scope differs")
        env_info = supplement["environment_evidence"][candidate]
        actual_info = env_info["actual_readonly_postimage_capture"]
        actual = _pin(actual_info["path"], actual_info["file_sha256"])
        plan_info = env_info["applied_event_plan"]
        event_plan = _pin(plan_info["path"], plan_info["file_sha256"])
        if (actual["database"] != DATABASES[candidate] or actual["environment"] != candidate
                or event_plan["database"] != DATABASES[candidate]
                or event_plan["decision_sha256"] != supplement["event_identity_decision"]["file_sha256"]):
            raise ValueError("next3 applied evidence identity differs")
        full_events = event_plan["snapshot"]["catalog"]
        full_editions = event_plan["snapshot"]["editions"]
        if len(full_events) != 74 or len(full_editions) != 1535:
            raise ValueError("next3 global event catalog scope differs")
        for label, referenced, full in (("event", source["events"], full_events),
                                        ("edition", source["event_editions"], full_editions)):
            indexed = {row["id"]: row for row in full}
            if len(indexed) != len(full) or any(indexed.get(row["id"]) != row for row in referenced):
                raise ValueError(f"frozen referenced {label} catalog differs from pinned global plan")
        albums = {row["id"]: _base(row, decision["database_album_columns"]) for row in source["albums"]}
        actual_albums = {row["id"]: row for row in actual["albums"]}
        event_plan_albums = {row["id"]: row for row in event_plan["snapshot"]["albums"]}
        rebases = supplement["exact_album_rebases"][candidate]
        if len(rebases) != 272 or set(actual_albums) != {row["album_id"] for row in rebases}:
            raise ValueError("next3 exact rebase membership differs")
        for change in rebases:
            album_id = change["album_id"]
            original = albums[album_id]
            after = dict(original, event_id=change["after_event_id"])
            if (change["changed_columns"] != ["event_id"] or change["before_event_id"] is not None
                    or original["event_id"] is not None or change["before_event_edition_id"] != original["event_edition_id"]
                    or change["after_event_edition_id"] != original["event_edition_id"]
                    or _digest(original) != change["original_decision_album_row_sha256"]
                    or _digest(_base(event_plan_albums[album_id], decision["database_album_columns"]))
                    != change["applied_event_plan_album_row_sha256"]
                    or _digest(after) != change["derived_postimage_album_row_sha256"]
                    or actual_albums[album_id] != after
                    or _digest(actual_albums[album_id]) != change["actual_current_album_row_sha256"]
                    or _sha(after["sgf_content"].encode()) != change["actual_sgf_sha256"]):
                raise ValueError(f"next3 exact album rebase differs: {album_id}")
            albums[album_id] = after
        original_associations = {row["id"]: row for row in source["album_sources"]}
        for row in actual["album_sources"]:
            if row != original_associations[row["id"]]:
                raise ValueError(f"next3 source association differs: {row['id']}")
        if actual["sources"] != source["sources"]:
            raise ValueError("next3 source catalog differs")
        event_additions = supplement["exact_event_catalog_additions"][candidate]["exact_new_event_rows"]
        event_catalog_proof = supplement["exact_event_catalog_additions"][candidate]
        if (actual["event_catalog"] != event_additions
                or _digest(event_additions) != event_catalog_proof["exact_new_event_rows_sha256"]
                or _digest(source["events"] + event_additions) != event_catalog_proof[
                    "expected_referenced_event_catalog_with_appended_rows_sha256"]
                or {row["id"] for row in full_events} & {row["id"] for row in event_additions}):
            raise ValueError("next3 event catalog additions differ")
        for hold in supplement["unchanged_event_hold_expectations"][candidate]:
            row = albums[hold["album_id"]]
            if (_digest(row) != hold["unchanged_full_album_row_sha256"] or row["event_id"] != hold["expected_event_id"]
                    or row["event_edition_id"] != hold["expected_event_edition_id"]):
                raise ValueError(f"event HOLD album differs: {hold['album_id']}")
        expected[candidate] = {
            "albums": _sorted(list(albums.values())), "slots": source["slots"],
            "album_sources": _sorted(source["album_sources"]), "sources": _sorted(source["sources"]),
            "events": _sorted(full_events + event_additions), "event_editions": _sorted(full_editions),
            "catalog": {key: _sorted(rows) for key, rows in source["catalog"].items()},
            "raw_staging": _sorted(source["raw_staging"]),
        }
    frozen_slots = {(r["album_id"], r["side"], r["raw"]) for r in frozen["test"]["slots"]}
    approved_keys = {(r["album_id"], r["side"], r["raw"]) for r in approved}
    held_keys = {(r["album_id"], r["side"], r["raw"]) for r in held}
    if (len(approved_keys), len(held_keys)) != (1451, 5922) or approved_keys & held_keys or approved_keys | held_keys != frozen_slots:
        raise ValueError("decision slot partition differs")
    identities = {item["raw"]: item for item in decision["identities"]}
    if len(identities) != 8:
        raise ValueError("first batch identity scope differs")
    for candidate in DATABASES:
        source = frozen[candidate]
        album_by_id = {row["id"]: row for row in source["albums"]}
        slots = {(row["album_id"], row["side"]): row for row in source["slots"]}
        associations = {}
        for row in source["album_sources"]:
            associations.setdefault(row["album_id"], []).append(row)
        catalog = {row["id"]: row for row in source["catalog"]["players"]}
        preimages = decision["catalog_and_ancillary_preimages"][candidate]
        if (_digest(source["catalog"]) != preimages["full_catalog_sha256"]
                or _digest(source["raw_staging"]) != preimages["raw_staging_sha256"]
                or _digest(source["sources"]) != preimages["source_catalog_sha256"]
                or _digest(source["events"]) != preimages["event_catalog_sha256"]
                or _digest(source["event_editions"]) != preimages["edition_catalog_sha256"]):
            raise ValueError("frozen catalog/staging digest differs")
        for row in approved + held:
            album_id, side, raw = row["album_id"], row["side"], row["raw"]
            album = album_by_id[album_id]
            slot = slots[(album_id, side)]
            before = row["preimages"][candidate]
            opponent_side = "white" if side == "black" else "black"
            opponent_id = album[opponent_side + "_player_id"]
            opponent = catalog.get(opponent_id)
            if (slot["raw"] != raw or slot["current_fk"] is not None or row["old_fk"] is not None
                    or album["player_" + side] != raw or album[side + "_player_id"] is not None
                    or row["date_played"] != album["date_played"] or row["event"] != album["event"]
                    or row["rank"] != album[side + "_rank"] or row["opponent_raw"] != album["player_" + opponent_side]
                    or row["opponent_rank"] != album[opponent_side + "_rank"]
                    or row["sgf_sha256"] != album["sgf_sha256"]
                    or before["current_fk"] is not None or before["opponent_fk"] != opponent_id
                    or _digest(_base(album, decision["database_album_columns"])) != before["album_row_sha256"]
                    or _digest(album) != before["captured_album_record_sha256"]
                    or _digest(slot) != before["captured_slot_sha256"]
                    or _digest(associations.get(album_id, [])) != before["source_associations_sha256"]
                    or (opponent is None and before["opponent_catalog_row_sha256"] is not None)
                    or (opponent is not None and _digest(opponent) != before["opponent_catalog_row_sha256"])):
                raise ValueError(f"frozen reviewed slot preimage differs: {candidate}/{album_id}/{side}")
            identity = identities.get(raw)
            if row in approved:
                if (identity is None or row["decision"] != "APPROVE_EXACT_NULL_PLAYER_FK"
                        or row["target_canonical_name"] != identity["chinese_canonical"]
                        or row["target_ids"][candidate] != identity["target_ids"][candidate]):
                    raise ValueError(f"approved identity target differs: {album_id}/{side}")
            elif row["decision"] == "APPROVE_EXACT_NULL_PLAYER_FK":
                raise ValueError(f"HOLD slot approved: {album_id}/{side}")
    return frozen, decision, supplement, expected[environment]


def _row(obj, keys):
    return {key: getattr(obj, key).isoformat() if hasattr(getattr(obj, key), "isoformat")
            else getattr(obj, key) for key in keys}


def _rows(db, model, keys, criterion=None):
    query = select(model)
    if criterion is not None:
        query = query.where(criterion)
    return _sorted([_row(obj, keys) for obj in db.scalars(query)])


def _snapshot(db, frozen, expected):
    source = frozen
    ids = [row["id"] for row in source["albums"]]
    raws = source["raws"]
    album_keys = list(expected["albums"][0])
    albums = _rows(db, KifuAlbum, album_keys, KifuAlbum.id.in_(ids))
    scoped = db.scalars(select(KifuAlbum).where(or_(KifuAlbum.player_black.in_(raws), KifuAlbum.player_white.in_(raws))))
    slots = sorted([{"album_id": album.id, "side": side, "raw": getattr(album, "player_" + side),
                     "current_fk": None, "opponent_raw": getattr(album, "player_white" if side == "black" else "player_black"),
                     "opponent_fk": getattr(album, "white_player_id" if side == "black" else "black_player_id")}
                    for album in scoped for side in ("black", "white")
                    if getattr(album, "player_" + side) in raws and getattr(album, side + "_player_id") is None],
                   key=lambda row: (row["album_id"], row["side"]))
    associations = _rows(db, KifuAlbumSource, list(source["album_sources"][0]), KifuAlbumSource.album_id.in_(ids))
    result = {"albums": albums, "slots": slots, "album_sources": associations,
              "raw_staging": _rows(db, KifuRawPlayerValue, list(source["raw_staging"][0]),
                                   KifuRawPlayerValue.raw_value.in_(raws))}
    for label, model in TABLES.items():
        template = source["catalog"][label] if label in ("players", "aliases", "names") else source[label]
        result[label if label not in ("players", "aliases", "names") else "_" + label] = _rows(db, model, list(template[0]))
    result["catalog"] = {key: result.pop("_" + key) for key in ("players", "aliases", "names")}
    return result


def validate_snapshot(snapshot, expected, decision, environment):
    for key in ("albums", "slots", "album_sources", "sources", "events", "event_editions", "raw_staging"):
        if snapshot[key] != expected[key]:
            raise ValueError(f"{key} preimage differs")
    for key in ("players", "aliases", "names"):
        if snapshot["catalog"][key] != expected["catalog"][key]:
            raise ValueError(f"{key} catalog preimage differs")
    owner = decision["catalog_and_ancillary_preimages"][environment]["existing_sugiuchi_owner"]["player"]
    if owner not in snapshot["catalog"]["players"]:
        raise ValueError("Sugiuchi existing owner differs")


def _database(db, environment):
    name = db.scalar(text("SELECT current_database()")) if db.bind.dialect.name == "postgresql" else DATABASES[environment]
    if name != DATABASES[environment]:
        raise ValueError("database differs")
    return name


def _capture(db, environment, frozen, decision, expected):
    database = _database(db, environment)
    snapshot = _snapshot(db, frozen[environment], expected)
    validate_snapshot(snapshot, expected, decision, environment)
    return {"format": FORMAT, "environment": environment, "database": database,
            "decision_sha256": DECISION_SHA, "supplement_sha256": SUPPLEMENT_SHA,
            "snapshot": snapshot, "counts": {"approved": 1451, "held": 5922}}


def capture(engine, environment):
    frozen, decision, _, expected = evidence(environment)
    with Session(engine) as db:
        if engine.dialect.name == "postgresql":
            db.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"))
        return _capture(db, environment, frozen, decision, expected)


def _after(plan, approved, targets, new_rows):
    result = json.loads(json.dumps(plan["snapshot"]))
    albums = {row["id"]: row for row in result["albums"]}
    changed = {(row["album_id"], row["side"]) for row in approved}
    for row in approved:
        raw = row["raw"]
        albums[row["album_id"]][row["side"] + "_player_id"] = targets[raw]
    result["slots"] = [slot for slot in result["slots"] if (slot["album_id"], slot["side"]) not in changed]
    for slot in result["slots"]:
        opposite = "white" if slot["side"] == "black" else "black"
        slot["opponent_fk"] = albums[slot["album_id"]][opposite + "_player_id"]
    result["catalog"]["players"] = _sorted(result["catalog"]["players"] + new_rows)
    return result


def run(engine, environment, plan, *, apply=False, plan_sha256=None, approved_plan_sha256=None):
    if apply and (not plan_sha256 or plan_sha256 != approved_plan_sha256):
        raise ValueError("separately approved plan SHA required")
    frozen, decision, _, expected = evidence(environment)
    if (plan.get("format") != FORMAT or plan.get("environment") != environment
            or plan.get("decision_sha256") != DECISION_SHA or plan.get("supplement_sha256") != SUPPLEMENT_SHA):
        raise ValueError("plan identity differs")
    approved = decision["approved_slots"]
    new_names = {item["raw"]: item["chinese_canonical"] for item in decision["identities"]
                 if item["target_ids"][environment] is None}
    if len(new_names) != 7:
        raise ValueError("new canonical scope differs")
    with Session(engine) as db:
        tx = db.begin()
        try:
            if engine.dialect.name == "postgresql":
                db.execute(text("LOCK TABLE kifu_albums,kifu_album_sources,kifu_sources,kifu_players,"
                                "kifu_player_aliases,kifu_player_names,kifu_raw_player_values,kifu_events,"
                                "kifu_event_editions IN SHARE ROW EXCLUSIVE MODE"))
            if _capture(db, environment, frozen, decision, expected) != plan:
                raise ValueError("full captured plan preimage differs")
            targets = {item["raw"]: item["target_ids"][environment] for item in decision["identities"]}
            created = {}
            for raw, canonical in new_names.items():
                obj = KifuPlayer(canonical_name=canonical)
                db.add(obj)
                db.flush()
                targets[raw] = obj.id
                created[raw] = obj.id
            if len(set(targets.values())) != 8:
                raise ValueError("distinct player target binding differs")
            for row in approved:
                side = row["side"]
                field = KifuAlbum.black_player_id if side == "black" else KifuAlbum.white_player_id
                raw_field = KifuAlbum.player_black if side == "black" else KifuAlbum.player_white
                changed = db.execute(update(KifuAlbum).where(
                    KifuAlbum.id == row["album_id"], raw_field == row["raw"],
                    KifuAlbum.date_played == row["date_played"], field.is_(None))
                    .values({field: targets[row["raw"]]}))
                if changed.rowcount != 1:
                    raise ValueError(f"slot CAS failed: {row['album_id']}/{side}")
            db.flush()
            actual = _snapshot(db, frozen[environment], expected)
            additions = [row for row in actual["catalog"]["players"] if row["id"] in set(created.values())]
            if len(additions) != 7 or {row["canonical_name"] for row in additions} != set(new_names.values()):
                raise ValueError("created player catalog differs")
            wanted = _after(plan, approved, targets, additions)
            if actual != wanted:
                raise ValueError("in-transaction full postimage differs")
            tx.commit() if apply else tx.rollback()
        except BaseException:
            tx.rollback()
            raise
    with Session(engine) as independent:
        if engine.dialect.name == "postgresql":
            independent.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"))
        final = _snapshot(independent, frozen[environment], expected)
        if _database(independent, environment) != plan["database"] or final != (wanted if apply else plan["snapshot"]):
            raise RuntimeError("independent posttransaction full-scope verification differs")
    return {"committed": apply, "created_player_ids": created if apply else {}, **plan["counts"]}
