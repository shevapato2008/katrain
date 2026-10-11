"""Exact safe6 player-FK executor. Full preimages and decision are independently pinned."""

import json
import re
import unicodedata
from datetime import datetime

from sqlalchemy import text, update
from sqlalchemy.orm import Session

from katrain.web.core.models_db import KifuAlbum, KifuPlayer
from katrain.web.kifu import player_new33_firstbatch as base

DECISION_PATH = "docs/resource/kifu-player-safe6-independent-exact-slot-decision-astra-2026-10-04.json"
DECISION_SHA = "38bf557857dd70995d094347c3573230ca5b0adf6ffd0ffaa2691c2fd68c382e"
DATABASES = base.DATABASES
FORMAT = "kifu-player-safe6-exact-plan-v1"
NEW = ("赵哲伦", "陈嘉锐")
AHAN_DECISION = ("docs/resource/kifu-event-china-ahan-independent-decision-astra-2026-10-04.json",
                 "53c88b3efb87e0d331aaa27a9a35512129bc5d6896c378d1f0da4f6769f1f891")
AHAN_RECEIPT = ("docs/resource/kifu-event-china-ahan-applied-2026-10-04.md",
                "2fadd542937159598317a8688692029987369021e5592030ad6037dda2c9b83f")
AHAN_PLAN = {
    "test": ("docs/resource/kifu-event-china-ahan-TEST-applied-plan-2026-10-04.json.gz",
             "dd96d3f50ea7f7458f2b9116f1bb7d0d45a0635c24147c36e80b9c75a4859fb4"),
    "prod": ("docs/resource/kifu-event-china-ahan-PROD-applied-plan-2026-10-04.json.gz",
             "3d8f3fe5bdb7110a2b2ff7ec2c32910e2ae7eed689a4fd7b925ba0995da245f1"),
}
AHAN_POSTIMAGE = {
    "test": ("docs/resource/kifu-event-china-ahan-TEST-postimage-2026-10-04.json",
             "72d7c994c4349d47cb6ad04a87cc342ce61a1cf8797c0bcbace3533f4d659829"),
    "prod": ("docs/resource/kifu-event-china-ahan-PROD-postimage-2026-10-04.json",
             "0ac97c1f309e0777e5ab3bf944850c170cc89b416f0128fae2633bdf3350fda0"),
}
AHAN_OVERLAP = {103194, 125109, 134804}


def _member_hash(rows):
    return base._digest([[r["album_id"], r["side"], r["raw"]] for r in rows])


def _semantic(value):
    if isinstance(value, dict):
        return {key: (_parse_timestamp(item) if key in ("created_at", "verified_at") and item is not None
                      else _semantic(item)) for key, item in value.items()}
    if isinstance(value, list):
        return [_semantic(item) for item in value]
    return value


def _parse_timestamp(value):
    value = re.sub(r"\.(\d{1,5})(?=[+-]\d{2}:\d{2}$)",
                   lambda match: "." + match.group(1).ljust(6, "0"), value)
    result = datetime.fromisoformat(value)
    if result.tzinfo is None:
        raise ValueError("timestamp must be timezone-aware")
    return result


def _owner_scan(decision, catalog, environment):
    charmap = decision["catalog_owner_scan"]["explicit_han_map"]

    def key(value):
        normalized = unicodedata.normalize("NFKC", value).casefold()
        return "".join(charmap.get(ch, ch) for ch in normalized
                       if not ch.isspace() and not unicodedata.category(ch).startswith("P"))

    for identity in decision["identities"]:
        variants = {key(value) for value in identity["variants"]}
        hits = []
        for table, fields, owner_field in (("players", ("canonical_name",), "id"),
                                           ("aliases", ("alias", "normalized_alias"), "player_id"),
                                           ("names", ("display_name",), "player_id")):
            for row in catalog[table]:
                matched = [field for field in fields if row[field] is not None and key(row[field]) in variants]
                if matched:
                    hits.append({"table": table, "row_id": row["id"], "owner_id": row[owner_field],
                                 "matched_fields": matched, "matched_values": {f: row[f] for f in matched},
                                 "row_sha256": base._digest(row)})
        proof = decision["catalog_owner_scan"]["owners"][identity["raw"]][environment]
        owners = sorted({hit["owner_id"] for hit in hits})
        resolved = sorted(set(owners) - set(proof["independently_excluded_homonym_owner_ids"]))
        target_id = identity["target_ids"][environment]
        if (hits != proof["all_hits"] or owners != proof["all_owner_ids"] or
                resolved != proof["resolved_identity_owner_ids"] or
                resolved != ([] if target_id is None else [target_id])):
            raise ValueError(f"safe6 variant-owner scan differs: {identity['raw']}")


def _equal(actual, expected):
    return _semantic(actual) == _semantic(expected)


def _validate_snapshot(snapshot, expected):
    for key in ("albums", "slots", "album_sources", "sources", "events", "event_editions", "raw_staging"):
        if not _equal(snapshot[key], expected[key]):
            raise ValueError(f"{key} preimage differs")
    for key in ("players", "aliases", "names"):
        if not _equal(snapshot["catalog"][key], expected["catalog"][key]):
            raise ValueError(f"{key} catalog preimage differs")


def _check_baseline(decision, original, environment):
    info = decision["environment_preimages"][environment]
    frozen = info["snapshot"]
    fresh = base._pin(info["fresh_capture"]["path"], info["fresh_capture"]["file_sha256"])
    context = base._pin(info["existing_target_context"]["path"], info["existing_target_context"]["file_sha256"])
    if (info["database"] != DATABASES[environment] or fresh["database"] != DATABASES[environment] or
            base._digest(frozen) != info["snapshot_sha256"] or
            any(fresh[key] != value for key, value in frozen.items()) or
            len(frozen["albums"]) != 777 or len(frozen["slots"]) != 781):
        raise ValueError("safe6 fresh full snapshot differs")
    guards = info["global_and_scope_guards"]
    for key in ("albums", "slots", "album_sources", "sources", "events", "event_editions", "raw_staging"):
        if len(frozen[key]) != guards[key]["row_count"] or base._digest(frozen[key]) != guards[key]["sha256"]:
            raise ValueError(f"safe6 {key} frozen SHA differs")
    if base._digest(frozen["catalog"]) != guards["catalog"]["sha256"]:
        raise ValueError("safe6 catalog frozen SHA differs")
    for key in ("players", "aliases", "names"):
        guard = guards["catalog"][key]
        if len(frozen["catalog"][key]) != guard["row_count"] or base._digest(frozen["catalog"][key]) != guard["sha256"]:
            raise ValueError(f"safe6 {key} frozen SHA differs")
    # The decision records complete post-secondbatch rows. Prove the ten reviewed
    # transitions against the earlier capture and its SHA-pinned applied plan.
    cross = decision["cross_batch_rebase"]["secondbatch"][environment]
    plan = base._pin(cross["applied_plan"]["path"], cross["applied_plan"]["file_sha256"])
    original_rows = {r["id"]: r for r in original[environment]["albums"]}
    plan_rows = {r["id"]: r for r in plan["snapshot"]["albums"]}
    frozen_rows = {r["id"]: r for r in frozen["albums"]}
    if len(cross["exact_album_deltas"]) != 10 or cross["changed_album_count"] != 10:
        raise ValueError("secondbatch safe6 overlap count differs")
    for delta in cross["exact_album_deltas"]:
        album_id = delta["album_id"]
        before, after = delta["before_full_album_row"], delta["after_full_album_row"]
        if (base._digest(before) != delta["before_sha256"] or base._digest(after) != delta["after_sha256"] or
                before != base._base(original_rows[album_id], decision["database_album_columns"]) or
                before != plan_rows[album_id] or after != frozen_rows[album_id] or
                len(delta["changes"]) != 1):
            raise ValueError(f"secondbatch safe6 exact album delta differs: {album_id}")
        for column, change in delta["changes"].items():
            if column not in ("black_player_id", "white_player_id") or change != {"before": None, "after": after[column]} or dict(before, **{column: after[column]}) != after:
                raise ValueError(f"secondbatch safe6 FK delta differs: {album_id}/{column}")
    if len(context) == 0:
        raise ValueError("existing target context missing")
    return frozen


def _ahan_rebase(decision, baseline, environment):
    ahan_decision = base._pin(*AHAN_DECISION)
    base._pin(*AHAN_RECEIPT)
    applied = base._pin(*AHAN_PLAN[environment])
    postimage = base._pin(*AHAN_POSTIMAGE[environment])
    if (ahan_decision["format"] != "kifu-event-china-ahan-independent-decision-v1" or
            applied["format"] != "kifu-event-china-ahan-exact-plan-v1" or
            applied["decision_sha256"] != AHAN_DECISION[1] or
            applied["database"] != DATABASES[environment] or applied["environment"] != environment or
            postimage["format"] != "kifu-ahan-safe6-overlap-postimage-v1" or
            postimage["database"] != DATABASES[environment] or postimage["environment"] != environment or
            postimage["applied_plan_sha256"] != AHAN_PLAN[environment][1]):
        raise ValueError("Ahan applied evidence identity differs")
    if baseline["events"] != applied["snapshot"]["events"]:
        raise ValueError("Ahan event catalog shared preimage differs")
    overlap = {row["id"]: row for row in postimage["overlap_albums"]}
    plan_albums = {row["id"]: row for row in applied["snapshot"]["albums"]}
    baseline_albums = {row["id"]: row for row in baseline["albums"]}
    if (set(overlap) != AHAN_OVERLAP or not AHAN_OVERLAP <= set(ahan_decision["approved_ids"]) or
            set(baseline_albums) & set(plan_albums) != AHAN_OVERLAP):
        raise ValueError("Ahan exact safe6 overlap differs")
    for album_id, after in overlap.items():
        before = baseline_albums[album_id]
        if (before != plan_albums[album_id] or before["event_id"] is not None or
                after != dict(before, event_id=89) or after["event_edition_id"] is not None):
            raise ValueError(f"Ahan full album postimage differs: {album_id}")
    event = postimage["new_event"]
    if (event["id"] != 89 or event["canonical_name"] != "中国阿含桐山杯" or
            any(row["id"] == 89 for row in baseline["events"])):
        raise ValueError("Ahan new catalog row differs")
    result = json.loads(json.dumps(baseline))
    for row in result["albums"]:
        if row["id"] in overlap:
            row["event_id"] = 89
    result["events"] = base._sorted(result["events"] + [event])
    return result


def evidence(environment):
    if environment not in DATABASES:
        raise ValueError("unknown environment")
    decision = base._pin(DECISION_PATH, DECISION_SHA)
    if decision["format"] != "kifu-player-safe6-independent-exact-slot-decision-astra-v1":
        raise ValueError("safe6 decision format differs")
    for item in decision["inputs"].values():
        base._pin(item["path"], item["file_sha256"])
    for source in decision["source_evidence"]:
        base._pin(source["raw_path"], source["raw_sha256"])
        base._pin(source["text_path"], source["text_sha256"])
    original = base._pin(decision["inputs"]["original_capture"]["path"],
                         decision["inputs"]["original_capture"]["file_sha256"])
    approved, held = decision["approved_slots"], decision["held_slots"]
    if ((len(approved), len(held)) != (601, 180) or
            _member_hash(approved) != decision["approved_slot_members_sha256"] or
            _member_hash(held) != decision["held_slot_members_sha256"] or
            base._digest(sorted([[r["album_id"], r["side"], r["raw"]] for r in approved + held])) !=
            decision["reviewed_all_slot_members_sha256"]):
        raise ValueError("safe6 exact membership differs")
    target_keys = ("album_id", "side", "raw", "target_canonical_name", "target_ids")
    if base._digest([{k: row[k] for k in target_keys} for row in approved]) != decision["approved_slot_targets_sha256"]:
        raise ValueError("safe6 exact targets differ")
    keys = [(r["album_id"], r["side"], r["raw"]) for r in approved + held]
    if len(set(keys)) != 781 or len(decision["identities"]) != 6:
        raise ValueError("safe6 slot partition differs")
    current_by_env = {}
    for candidate in DATABASES:
        frozen = _check_baseline(decision, original, candidate)
        _owner_scan(decision, frozen["catalog"], candidate)
        if {(r["album_id"], r["side"], r["raw"]) for r in frozen["slots"]} != set(keys):
            raise ValueError("safe6 frozen slot partition differs")
        albums = {r["id"]: r for r in frozen["albums"]}
        slots = {(r["album_id"], r["side"], r["raw"]): r for r in frozen["slots"]}
        associations = {}
        for row in frozen["album_sources"]:
            associations.setdefault(row["album_id"], []).append(row)
        for row in approved + held:
            album = albums[row["album_id"]]
            guard = row["preimages"][candidate]
            side, opposite = row["side"], "white" if row["side"] == "black" else "black"
            key = (row["album_id"], side, row["raw"])
            if (row["old_fk"] is not None or album[side + "_player_id"] is not None or
                    album["player_" + side] != row["raw"] or album["date_played"] != row["date_played"] or
                    album["event"] != row["event"] or album[side + "_rank"] != row["rank"] or
                    album["player_" + opposite] != row["opponent_raw"] or
                    album[opposite + "_rank"] != row["opponent_rank"] or
                    base._digest(album) != guard["album_row_sha256"] or
                    base._digest(slots[key]) != guard["slot_record_sha256"] or
                    base._digest(associations.get(row["album_id"], [])) != guard["source_associations_sha256"] or
                    base._sha(album["sgf_content"].encode()) != row["sgf_sha256"]):
                raise ValueError(f"safe6 slot preimage differs: {candidate}/{key}")
        current_by_env[candidate] = _ahan_rebase(decision, frozen, candidate)
    return decision, current_by_env[environment]


def _capture(db, environment, decision, expected):
    database = base._database(db, environment)
    frozen = {**expected, "raws": decision["scope"]["raws"]}
    snapshot = base._snapshot(db, frozen, expected)
    _validate_snapshot(snapshot, expected)
    _owner_scan(decision, snapshot["catalog"], environment)
    return {"format": FORMAT, "environment": environment, "database": database,
            "decision_sha256": DECISION_SHA, "snapshot": snapshot,
            "counts": {"approved": 601, "held": 180}}


def capture(engine, environment):
    decision, expected = evidence(environment)
    with Session(engine) as db:
        if engine.dialect.name == "postgresql":
            db.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"))
        return _capture(db, environment, decision, expected)


def run(engine, environment, plan, *, apply=False, plan_sha256=None, approved_plan_sha256=None):
    if apply and (not plan_sha256 or plan_sha256 != approved_plan_sha256):
        raise ValueError("separately approved plan SHA required")
    decision, expected = evidence(environment)
    if (plan.get("format") != FORMAT or plan.get("environment") != environment or
            plan.get("decision_sha256") != DECISION_SHA):
        raise ValueError("safe6 plan identity differs")
    approved = decision["approved_slots"]
    targets = {item["raw"]: item["target_ids"][environment] for item in decision["identities"]}
    new_names = {item["raw"]: item["chinese_canonical"] for item in decision["identities"] if item["raw"] in NEW}
    if set(new_names) != set(NEW) or any(targets[name] is not None for name in NEW) or any(
            targets[name] is None for name in targets if name not in NEW):
        raise ValueError("safe6 target identity differs")
    with Session(engine) as db:
        tx = db.begin()
        try:
            if engine.dialect.name == "postgresql":
                db.execute(text("LOCK TABLE kifu_albums,kifu_album_sources,kifu_sources,kifu_players,"
                                "kifu_player_aliases,kifu_player_names,kifu_raw_player_values,kifu_events,"
                                "kifu_event_editions IN SHARE ROW EXCLUSIVE MODE"))
            if _capture(db, environment, decision, expected) != plan:
                raise ValueError("safe6 captured plan preimage differs")
            for raw, canonical in new_names.items():
                obj = KifuPlayer(canonical_name=canonical)
                db.add(obj)
                db.flush()
                targets[raw] = obj.id
            for row in approved:
                side = row["side"]
                field = KifuAlbum.black_player_id if side == "black" else KifuAlbum.white_player_id
                raw_field = KifuAlbum.player_black if side == "black" else KifuAlbum.player_white
                changed = db.execute(update(KifuAlbum).where(
                    KifuAlbum.id == row["album_id"], raw_field == row["raw"],
                    KifuAlbum.date_played == row["date_played"], field.is_(None))
                    .values({field: targets[row["raw"]]}))
                if changed.rowcount != 1:
                    raise ValueError(f"safe6 CAS failed: {row['album_id']}/{side}")
            db.flush()
            frozen = {**expected, "raws": decision["scope"]["raws"]}
            actual = base._snapshot(db, frozen, expected)
            additions = [row for row in actual["catalog"]["players"] if row["id"] in
                         {targets[name] for name in NEW}]
            if len(additions) != 2 or {row["canonical_name"] for row in additions} != set(new_names.values()):
                raise ValueError("safe6 new player binding differs")
            wanted = base._after(plan, approved, targets, additions)
            if actual != wanted:
                raise ValueError("safe6 in-transaction full postimage differs")
            tx.commit() if apply else tx.rollback()
        except BaseException:
            tx.rollback()
            raise
    with Session(engine) as independent:
        if engine.dialect.name == "postgresql":
            independent.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"))
        final = base._snapshot(independent, frozen, expected)
        if base._database(independent, environment) != plan["database"] or final != (wanted if apply else plan["snapshot"]):
            raise RuntimeError("safe6 independent posttransaction full scope differs")
    return {"committed": apply, "created_player_ids": {name: targets[name] for name in NEW} if apply else {},
            **plan["counts"]}
