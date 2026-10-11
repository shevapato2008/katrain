"""Exact independently reviewed Korean event links (737 approve, 19 new HOLD)."""

import gzip
import hashlib
import json
from pathlib import Path

from sqlalchemy import func, select, text, update
from sqlalchemy.orm import Session

from katrain.web.core.models_db import (
    KifuAlbum,
    KifuAlbumSource,
    KifuEvent,
    KifuEventAlias,
    KifuEventEdition,
    KifuPlayer,
    KifuSource,
)
from katrain.web.kifu.event_next3_exact import _digest, _equal, _name_key, _rows

ROOT = Path(__file__).resolve().parents[3]
DECISION_PATH = "docs/resource/kifu-event-next-after-china-ahan-independent-decision-astra-2026-10-04.json"
DECISION_SHA = "749e066920dcdc0fc181074f15c10128e7f277ba87d98d699e87bc5638595d80"
REBASE_PATH = "docs/resource/kifu-event-next-after-china-ahan-postahan-independent-exact-rebase-astra-2026-10-04.json"
REBASE_SHA = "f7bf5374be594ca994bbadf6a26ae6af6e2cc6d9864bc2be181b18776548bd3f"
DATABASES = {"test": "katrain_db", "prod": "katrain_prod_20260725"}
FROZEN = {
    "test": (
        "docs/resource/kifu-event-next-after-china-ahan-TEST-postahan-independent-preimage-astra-2026-10-04.json.gz",
        "25f8a768566d70531c4b56d3a1129c00643c0aab2fb893499aac069c5f1c6a49",
    ),
    "prod": (
        "docs/resource/kifu-event-next-after-china-ahan-PROD-postahan-independent-preimage-astra-2026-10-04.json.gz",
        "aef54aaa158b040fd7a002bf55656cd64554a382fa69a8f51a999e9eafbc3599",
    ),
}
FAMILY_NAMES = {"kr_gs_caltex": "韩国GS加德士杯", "kr_womens_guksu": "韩国女子国手战"}
SNAPSHOT_KEYS = (
    "albums",
    "album_sources",
    "sources",
    "events",
    "aliases",
    "editions",
    "players",
    "existing_hold_event_slots",
    "statistics",
)


def _pinned(path, expected):
    raw = (ROOT / path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError(f"pinned evidence SHA differs: {path}")
    return json.loads(gzip.decompress(raw) if raw[:2] == b"\x1f\x8b" else raw)


def _same_rows(current, frozen):
    return len(current) == len(frozen) and all(_equal(a, b) for a, b in zip(current, frozen))


def _collision_key(value):
    return _name_key(value).replace("體", "体")


def _snapshot(db, ids, player_ids, prior_hold_ids):
    holds = db.execute(
        select(KifuAlbum.id, KifuAlbum.event_id, KifuAlbum.event_edition_id)
        .where(KifuAlbum.id.in_(prior_hold_ids))
        .order_by(KifuAlbum.id)
    ).all()
    return {
        "albums": _rows(db, KifuAlbum, KifuAlbum.id.in_(ids)),
        "album_sources": _rows(db, KifuAlbumSource, KifuAlbumSource.album_id.in_(ids)),
        "sources": _rows(db, KifuSource),
        "events": _rows(db, KifuEvent),
        "aliases": _rows(db, KifuEventAlias),
        "editions": _rows(db, KifuEventEdition),
        "players": _rows(db, KifuPlayer, KifuPlayer.id.in_(player_ids)),
        "existing_hold_event_slots": [
            {"id": id_, "event_id": event_id, "event_edition_id": edition_id} for id_, event_id, edition_id in holds
        ],
        "statistics": {
            "albums": db.scalar(select(func.count()).select_from(KifuAlbum)),
            "event_links": db.scalar(select(func.count(KifuAlbum.event_id))),
            "edition_links": db.scalar(select(func.count(KifuAlbum.event_edition_id))),
        },
    }


def _validate_ahan_rebase(environment, frozen, info):
    before = _pinned(info["original_preimage"]["path"], info["original_preimage"]["file_sha256"])
    applied_plan = _pinned(info["ahan_applied_plan"]["path"], info["ahan_applied_plan"]["file_sha256"])
    _pinned(info["ahan_committed_event_postimage"]["path"], info["ahan_committed_event_postimage"]["file_sha256"])
    if (
        applied_plan["environment"] != environment
        or applied_plan["database"] != DATABASES[environment]
        or applied_plan["counts"] != {"approved": 793, "held": 8, "prior_held": 4265}
    ):
        raise ValueError("Ahan applied plan identity differs")
    for key in info["unchanged_keys"]:
        if before[key] != frozen[key]:
            raise ValueError(f"Ahan unrelated {key} drift differs")
    for key, sha in info["unchanged_rows_sha256"].items():
        if _digest(frozen[key]) != sha:
            raise ValueError(f"Ahan unchanged {key} SHA differs")
    added = info["added_event_row"]
    expected_events = sorted(before["events"] + [added], key=lambda row: row["id"])
    if (
        _digest(added) != info["added_event_row_sha256"]
        or added["id"] != 89
        or added["canonical_name"] != "中国阿含桐山杯"
        or frozen["events"] != expected_events
        or not _same_rows(before["events"], applied_plan["snapshot"]["events"])
        or _digest(before["events"]) != info["catalog_before_sha256"]
        or _digest(frozen["events"]) != info["catalog_after_sha256"]
    ):
        raise ValueError("Ahan exact catalog rebase differs")
    expected_stats = dict(before["statistics"])
    expected_stats["event_links"] += 793
    if (
        before["statistics"] != info["statistics_before"]
        or frozen["statistics"] != expected_stats
        or frozen["statistics"] != info["statistics_after"]
        or info["candidate_overlap_with_ahan_approved_ids"]
        or info["candidate_album_drift"]
        or not info["all_4273_hold_slots_unchanged"]
    ):
        raise ValueError("Ahan exact statistics/scope rebase differs")


def evidence(environment):
    if environment not in DATABASES:
        raise ValueError("unknown environment")
    decision = _pinned(DECISION_PATH, DECISION_SHA)
    rebase = _pinned(REBASE_PATH, REBASE_SHA)
    if (
        decision.get("format") != "kifu-event-next-after-china-ahan-independent-decision-v1"
        or rebase.get("format") != "kifu-event-next-after-china-ahan-independent-exact-rebase-v1"
        or rebase["unrelated_drift_accepted"] is not False
    ):
        raise ValueError("independent decision/rebase format differs")
    for item in decision["inputs"].values():
        raw = (ROOT / item["path"]).read_bytes()
        if hashlib.sha256(raw).hexdigest() != item["file_sha256"]:
            raise ValueError(f"pinned evidence SHA differs: {item['path']}")
    if (
        len(decision["approved"]) != 737
        or len(decision["held"]) != 19
        or len(decision["prior_hold_union_ids"]) != 4273
        or _digest(decision["prior_hold_union_ids"]) != decision["prior_hold_union_sha256"]
    ):
        raise ValueError("independent scope differs")
    for kind in ("approved", "held"):
        records, ids = decision[kind], decision[kind + "_ids"]
        if (
            [r["id"] for r in records] != ids
            or _digest(ids) != decision[kind + "_id_sha256"]
            or _digest(records) != decision[kind + "_records_sha256"]
        ):
            raise ValueError(f"independent {kind} member SHA differs")
    ids = sorted(decision["approved_ids"] + decision["held_ids"])
    if (
        len(set(ids)) != 756
        or ids != decision["candidate_ids"]
        or _digest(ids) != decision["candidate_id_sha256"]
        or set(ids) & set(decision["prior_hold_union_ids"])
    ):
        raise ValueError("independent album/HOLD partition differs")
    families = {row["family_key"]: row for row in decision["families"]}
    if len(decision["families"]) != 2 or {k: v["canonical_name"] for k, v in families.items()} != FAMILY_NAMES:
        raise ValueError("independent event identities differ")
    for key, family in families.items():
        if family["action"] != "create_exact_type_if_absent" or family["existing_event_id_by_environment"] != {
            "TEST": None,
            "PROD": None,
        }:
            raise ValueError("independent create target differs")
        for kind in ("approved", "held"):
            family_ids = [r["id"] for r in decision[kind] if r["family_key"] == key]
            if (
                family_ids != family[kind + "_ids"]
                or len(family_ids) != family[kind + "_count"]
                or _digest(family_ids) != family[kind + "_id_sha256"]
            ):
                raise ValueError("independent family membership differs")
    for kind in ("approved", "held"):
        for row in decision[kind]:
            expected_name = FAMILY_NAMES[row["family_key"]] if kind == "approved" else None
            if (
                row["target_canonical_name"] != expected_name
                or row["target_event_edition_id"] is not None
                or row["target_event_id_by_environment"] != {"TEST": None, "PROD": None}
                or row["decision"] != ("APPROVE_EVENT_TYPE_ONLY" if kind == "approved" else "HOLD")
            ):
                raise ValueError("independent row target differs")
    frozen_by_env = {}
    for candidate in DATABASES:
        info = decision["environments"][candidate.upper()]
        rebase_info = rebase["environments"][candidate.upper()]
        if (
            info["database"] != DATABASES[candidate]
            or (info["preimage"]["path"], info["preimage"]["file_sha256"]) != FROZEN[candidate]
            or rebase_info["post_ahan_preimage"] != info["preimage"]
        ):
            raise ValueError("independent environment pin differs")
        frozen = _pinned(*FROZEN[candidate])
        if (
            len(frozen["albums"]) != 756
            or [r["id"] for r in frozen["albums"]] != ids
            or frozen["statistics"] != info["before_statistics"]
        ):
            raise ValueError("frozen exact album/statistics scope differs")
        for key, checksum in (
            ("albums", "album_rows_sha256"),
            ("album_sources", "album_sources_sha256"),
            ("events", "catalog_preimage_sha256"),
            ("aliases", "alias_preimage_sha256"),
            ("editions", "edition_preimage_sha256"),
            ("sources", "sources_preimage_sha256"),
            ("players", "players_preimage_sha256"),
            ("existing_hold_event_slots", "prior_hold_event_slots_sha256"),
        ):
            if _digest(frozen[key]) != info[checksum]:
                raise ValueError(f"independent frozen {key} SHA differs")
        if [r["id"] for r in frozen["existing_hold_event_slots"]] != decision["prior_hold_union_ids"] or any(
            r["event_id"] is not None or r["event_edition_id"] is not None for r in frozen["existing_hold_event_slots"]
        ):
            raise ValueError("frozen prior HOLD scope differs")
        albums = {r["id"]: r for r in frozen["albums"]}
        associations = {}
        for row in frozen["album_sources"]:
            associations.setdefault(row["album_id"], []).append(row)
        for record in decision["approved"] + decision["held"]:
            album = albums[record["id"]]
            row_env = record["environments"][candidate.upper()]
            if (
                _digest(album) != row_env["album_preimage_sha256"]
                or _digest(associations.get(record["id"], [])) != row_env["album_sources_preimage_sha256"]
                or hashlib.sha256(album["sgf_content"].encode()).hexdigest() != record["sgf_sha256"]
                or album["event_id"] is not None
                or album["event_edition_id"] is not None
                or any(album[k] != v for k, v in record["raw_preimage"].items())
            ):
                raise ValueError(f"independent album/source preimage differs: {record['id']}")
        _validate_ahan_rebase(candidate, frozen, rebase_info)
        frozen_by_env[candidate] = frozen
    return decision, frozen_by_env[environment], DECISION_SHA


def _capture(db, decision, frozen, environment, decision_sha):
    database = (
        db.scalar(text("SELECT current_database()")) if db.bind.dialect.name == "postgresql" else DATABASES[environment]
    )
    if database != DATABASES[environment]:
        raise ValueError("database differs")
    snapshot = _snapshot(
        db,
        decision["approved_ids"] + decision["held_ids"],
        [r["id"] for r in frozen["players"]],
        decision["prior_hold_union_ids"],
    )
    for key in SNAPSHOT_KEYS:
        matches = snapshot[key] == frozen[key] if key == "statistics" else _same_rows(snapshot[key], frozen[key])
        if not matches:
            raise ValueError(f"frozen {key} differs")
    keys = {_collision_key(name) for name in FAMILY_NAMES.values()}
    if any(_collision_key(r["canonical_name"]) in keys for r in snapshot["events"]) or any(
        _collision_key(r["alias"]) in keys or _collision_key(r["normalized_alias"]) in keys for r in snapshot["aliases"]
    ):
        raise ValueError("approved new event type collides")
    return {
        "format": "kifu-event-korean-two-exact-plan-v1",
        "environment": environment,
        "database": database,
        "decision_sha256": decision_sha,
        "frozen_file_sha256": FROZEN[environment][1],
        "post_ahan_rebase_sha256": REBASE_SHA,
        "targets": dict(FAMILY_NAMES),
        "snapshot": snapshot,
        "counts": {"approved": 737, "held": 19, "prior_held": 4273},
    }


def capture(engine, environment):
    decision, frozen, sha = evidence(environment)
    with Session(engine) as db:
        if engine.dialect.name == "postgresql":
            db.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"))
        return _capture(db, decision, frozen, environment, sha)


def _expected(plan, decision, targets):
    result = json.loads(json.dumps(plan["snapshot"]))
    albums = {r["id"]: r for r in result["albums"]}
    for row in decision["approved"]:
        albums[row["id"]]["event_id"] = targets[row["family_key"]]
    result["statistics"]["event_links"] += len(decision["approved"])
    return result


def _verify_final(engine, decision, plan, targets, inserted, applied):
    with Session(engine) as db:
        if engine.dialect.name == "postgresql":
            db.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"))
        current = _snapshot(
            db,
            decision["approved_ids"] + decision["held_ids"],
            [r["id"] for r in plan["snapshot"]["players"]],
            decision["prior_hold_union_ids"],
        )
        expected = _expected(plan, decision, targets) if applied else plan["snapshot"]
        if applied:
            expected["events"] += inserted
            expected["events"].sort(key=lambda r: r["id"])
        if current != expected:
            raise ValueError("independent posttransaction full scope differs")
        database = (
            db.scalar(text("SELECT current_database()")) if engine.dialect.name == "postgresql" else plan["database"]
        )
        if database != plan["database"]:
            raise ValueError("independent posttransaction database differs")


def run(engine, environment, plan, *, apply=False, plan_sha256=None, approved_plan_sha256=None):
    if apply and (not plan_sha256 or plan_sha256 != approved_plan_sha256):
        raise ValueError("separately approved plan SHA required")
    decision, frozen, sha = evidence(environment)
    if plan.get("format") != "kifu-event-korean-two-exact-plan-v1" or plan.get("environment") != environment:
        raise ValueError("plan format/environment differs")
    with Session(engine) as db:
        tx = db.begin()
        try:
            if engine.dialect.name == "postgresql":
                db.execute(
                    text(
                        "LOCK TABLE kifu_albums,kifu_album_sources,kifu_sources,kifu_events,"
                        "kifu_event_aliases,kifu_event_editions,kifu_players IN SHARE ROW EXCLUSIVE MODE"
                    )
                )
            if _capture(db, decision, frozen, environment, sha) != plan:
                raise ValueError("full captured plan preimage differs")
            targets = {}
            for family, name in FAMILY_NAMES.items():
                event = KifuEvent(canonical_name=name)
                db.add(event)
                db.flush()
                targets[family] = event.id
            for row in decision["approved"]:
                changed = db.execute(
                    update(KifuAlbum)
                    .where(
                        KifuAlbum.id == row["id"],
                        KifuAlbum.event_id.is_(None),
                        KifuAlbum.event_edition_id.is_(None),
                        KifuAlbum.event == row["raw_preimage"]["event"],
                        KifuAlbum.date_played == row["raw_preimage"]["date_played"],
                    )
                    .values(event_id=targets[row["family_key"]])
                )
                if changed.rowcount != 1:
                    raise ValueError(f"event CAS failed: {row['id']}")
            db.flush()
            after = _snapshot(
                db,
                decision["approved_ids"] + decision["held_ids"],
                [r["id"] for r in plan["snapshot"]["players"]],
                decision["prior_hold_union_ids"],
            )
            inserted = [r for r in after["events"] if r["id"] in targets.values()]
            if len(inserted) != 2 or {r["id"]: r["canonical_name"] for r in inserted} != {
                targets[family]: name for family, name in FAMILY_NAMES.items()
            }:
                raise ValueError("new event target binding differs")
            expected = _expected(plan, decision, targets)
            expected["events"] += inserted
            expected["events"].sort(key=lambda r: r["id"])
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
