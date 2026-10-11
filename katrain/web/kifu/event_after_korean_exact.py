"""Exact type-only links for the independently reviewed 1,209/476 decision."""

import gzip
import hashlib
import json
from pathlib import Path

from sqlalchemy import func, inspect, select, text, update
from sqlalchemy.orm import Session

from katrain.web.core.models_db import KifuAlbum, KifuEvent
from katrain.web.kifu.event_korean_two_exact import _collision_key, _same_rows, _snapshot as _base_snapshot
from katrain.web.kifu.event_next3_exact import _digest

ROOT = Path(__file__).resolve().parents[3]
DECISION_PATH = "docs/resource/kifu-event-after-korean-two-next-independent-decision-astra-2026-10-04.json"
DECISION_SHA = "264606394e2ad40dfec332ae660f8b281372cd4b6d30e6e8d646962ed487289b"
SOURCE_PATH = "docs/resource/kifu-event-after-korean-two-next-independent-sources-astra-2026-10-04.json"
SOURCE_SHA = "55e99d3bf69fecbd7630bd92538d89f8508169e3e03e6608900347c7ec7a8489"
REBASE_PATH = "docs/resource/kifu-event-after-korean-two-next-post-top20-independent-exact-rebase-2026-10-04.json"
REBASE_SHA = "54deecc86c3cf2db41760b7be7af654f262008d35dd76fa34bbbd3c2ee09e926"
TOP20_PATH = "docs/resource/kifu-player-exact-anchor-top20-independent-decision-astra-2026-10-04.json"
TOP20_SHA = "6d53699a34bbcc4006020b9089977d4ca44eb4e192cd70db6021edb21dc5f39b"
DATABASES = {"test": "katrain_db", "prod": "katrain_prod_20260725"}
FROZEN = {
    "test": (
        "docs/resource/kifu-event-after-korean-two-next-TEST-independent-full-preimage-astra-2026-10-04.json.gz",
        "1c7eea811ecf6122e3ebb6cd565d7ba92647eb87302aff75362fe69c92ccbb6d",
    ),
    "prod": (
        "docs/resource/kifu-event-after-korean-two-next-PROD-independent-full-preimage-astra-2026-10-04.json.gz",
        "1ca0670bf2c336e750f06478a7732ec2d30f504f02fa53176db0c1f9fe50253b",
    ),
}
REBASED = {
    "test": (
        "docs/resource/kifu-event-after-korean-two-next-TEST-post-top20-independent-full-preimage-2026-10-04.json.gz",
        "35c812de4a131b5a7e57367f64184c0d483f67075b96a518d79e155708831ea5",
    ),
    "prod": (
        "docs/resource/kifu-event-after-korean-two-next-PROD-post-top20-independent-full-preimage-2026-10-04.json.gz",
        "a74d2c192c36889da965d2f1765326fc478b8e6279b713f76267038bb61ffa53",
    ),
}
TOP20_PLANS = {
    "test": (
        "docs/resource/kifu-player-anchor-top20-TEST-captured-plan-2026-10-04.json.gz",
        "f900cde8311614122ea3527d70f5786560621fb2c60a8c8660c61b38f5f784de",
    ),
    "prod": (
        "docs/resource/kifu-player-anchor-top20-PROD-captured-plan-2026-10-04.json.gz",
        "17ea7cb99b2fccb56a74f87f9fe6c2f5d7beef370348fc67177e83a4eb31eb91",
    ),
}
FAMILY_NAMES = {"cn_lanke": "衢州烂柯杯中国围棋冠军赛", "kr_kiwang": "韩国棋王战", "kr_ten": "韩国十段战"}
FAMILY_COUNTS = {"cn_lanke": (561, 471), "kr_kiwang": (353, 4), "kr_ten": (295, 1)}
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
    "album_columns",
    "global_counts",
)
PLAN_FORMAT = "kifu-event-after-korean-exact-plan-v1"


def _pin_bytes(path, expected):
    raw = (ROOT / path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError(f"pinned evidence SHA differs: {path}")
    return raw


def _pinned(path, expected):
    raw = _pin_bytes(path, expected)
    return json.loads(gzip.decompress(raw) if raw[:2] == b"\x1f\x8b" else raw)


def _snapshot(db, ids, player_ids, prior_hold_ids):
    result = _base_snapshot(db, ids, player_ids, prior_hold_ids)
    result["album_columns"] = [column["name"] for column in inspect(db.connection()).get_columns("kifu_albums")]
    result["global_counts"] = {
        "games": result["statistics"]["albums"],
        "event_links": result["statistics"]["event_links"],
        "player_links": db.scalar(select(func.count(KifuAlbum.black_player_id)))
        + db.scalar(select(func.count(KifuAlbum.white_player_id))),
    }
    return result


def _validate_top20_rebase(environment, decision, original, fresh, rebase, top20):
    info = rebase["environments"][environment.upper()]
    for field, pinned in (
        ("original_preimage", FROZEN),
        ("post_top20_preimage", REBASED),
        ("top20_applied_plan", TOP20_PLANS),
    ):
        if (info[field]["path"], info[field]["file_sha256"]) != pinned[environment]:
            raise ValueError("top20 rebase environment pin differs")
    plan = _pinned(*TOP20_PLANS[environment])
    if (
        info["database"] != DATABASES[environment]
        or fresh["format"] != original["format"]
        or fresh["environment"] != environment.upper()
        or fresh["meta"]["database"] != DATABASES[environment]
        or plan["format"] != "kifu-player-anchor-top20-exact-plan-v1"
        or plan["environment"] != environment
        or plan["database"] != DATABASES[environment]
        or plan["decision_sha256"] != TOP20_SHA
        or plan["counts"] != {"approved": 1933, "held": 1415}
        or info["unexpected_drift"]
    ):
        raise ValueError("top20 rebase identity/scope differs")
    expected = {key: json.loads(json.dumps(original[key])) for key in SNAPSHOT_KEYS if key != "global_counts"}
    albums = {row["id"]: row for row in expected["albums"]}
    records = {row["id"]: row for row in decision["approved"] + decision["held"]}
    top_albums = {row["id"]: row for row in plan["snapshot"]["albums"]}
    catalog = {row["id"]: row for row in plan["snapshot"]["catalog"]["players"]}
    associations = {}
    for row in original["album_sources"]:
        associations.setdefault(row["album_id"], []).append(row)
    deltas = []
    targets = set()
    for row in top20["approved"]:
        id_, side = row["album_id"], row["side"]
        if id_ not in albums:
            continue
        album, record, field = albums[id_], records[id_], side + "_player_id"
        row_env = row["environments"][environment.upper()]
        target = row["target_player_id_by_environment"][environment.upper()]
        before_sha, source_sha = _digest(album), _digest(associations.get(id_, []))
        if (
            side not in ("black", "white")
            or row["decision"] != "APPROVE_EXISTING_PLAYER_FK"
            or album[field] is not None
            or album != top_albums[id_]
            or before_sha != row_env["album_preimage_sha256"]
            or source_sha != row_env["album_sources_preimage_sha256"]
            or row_env["proposed_change"] != {field: {"from": None, "to": target}}
            or album["player_" + side] != row["raw"]
            or hashlib.sha256(album["sgf_content"].encode()).hexdigest() != row["sgf_sha256"]
            or _digest(catalog[target]) != row_env["target_player_row_sha256"]
        ):
            raise ValueError(f"top20 original approved slot differs: {id_}/{side}")
        album[field] = target
        targets.add(target)
        deltas.append(
            {
                "album_id": id_,
                "side": side,
                "field": field,
                "raw": row["raw"],
                "before": None,
                "after": target,
                "before_full_row_sha256": before_sha,
                "after_full_row_sha256": _digest(album),
                "album_sources_sha256": source_sha,
                "sgf_sha256": row["sgf_sha256"],
                "event_decision": record["decision"],
                "event_family_key": record["family_key"],
                "event_original_record_sha256": _digest(record),
                "top20_approved_record_sha256": _digest(row),
                "target_player_row_sha256": _digest(catalog[target]),
            }
        )
    if (
        len(deltas) != 29
        or len({row["album_id"] for row in deltas}) != 29
        or deltas != info["exact_player_deltas"]
        or _digest(deltas) != info["exact_player_deltas_sha256"]
        or [[row["album_id"], row["side"]] for row in deltas]
        != rebase["scope"]["candidate_top20_approved_intersection_slots"]
    ):
        raise ValueError("top20 exact 29-slot rebase differs")
    original_ids = [row["id"] for row in original["players"]]
    added_ids = sorted(targets - set(original_ids))
    added = [catalog[id_] for id_ in added_ids]
    expected["players"] = sorted(original["players"] + added, key=lambda row: row["id"])
    referenced = sorted(
        {
            row[field]
            for row in albums.values()
            for field in ("black_player_id", "white_player_id")
            if row[field] is not None
        }
    )
    if (
        len(added) != 3
        or added_ids != info["newly_referenced_player_ids"]
        or added != info["newly_referenced_player_rows"]
        or _digest(added) != info["newly_referenced_player_rows_sha256"]
        or original_ids != info["original_referenced_player_ids"]
        or referenced != info["rebased_referenced_player_ids"]
        or referenced != [row["id"] for row in expected["players"]]
    ):
        raise ValueError("top20 exact referenced-player rebase differs")
    before_counts = plan["snapshot"]["global_counts"]
    expected["global_counts"] = dict(before_counts)
    expected["global_counts"]["player_links"] += 1933
    if (
        before_counts != info["global_counts_before"]
        or _digest(before_counts) != info["global_counts_before_sha256"]
        or expected["global_counts"] != info["global_counts_after"]
        or info["global_counts_delta"] != {"games": 0, "event_links": 0, "player_links": 1933}
        or before_counts["games"] != original["statistics"]["albums"]
        or before_counts["event_links"] != original["statistics"]["event_links"]
    ):
        raise ValueError("top20 exact global-count rebase differs")
    for key in SNAPSHOT_KEYS:
        if fresh[key] != expected[key] or _digest(fresh[key]) != info["guard_sha256_after"][key]:
            raise ValueError(f"top20 exact {key} reconstruction differs")
        if key != "global_counts" and _digest(original[key]) != info["guard_sha256_before"][key]:
            raise ValueError(f"top20 original {key} SHA differs")


def evidence(environment):
    if environment not in DATABASES:
        raise ValueError("unknown environment")
    decision = _pinned(DECISION_PATH, DECISION_SHA)
    _pin_bytes(SOURCE_PATH, SOURCE_SHA)
    if (
        decision.get("format") != "kifu-event-after-korean-two-next-independent-decision-v1"
        or decision.get("status") != "APPROVE_EVENT_TYPE_ONLY_WITH_EXACT_HOLDS"
        or (decision["source_evidence_file"]["path"], decision["source_evidence_file"]["file_sha256"])
        != (SOURCE_PATH, SOURCE_SHA)
    ):
        raise ValueError("independent decision/source identity differs")
    for item in [
        decision["candidate_bundle"],
        decision["candidate_markdown"],
        decision["mainline_audit_file"],
        *decision["original_preimages"].values(),
    ]:
        _pin_bytes(item["path"], item["file_sha256"])
    if (
        len(decision["approved"]) != 1209
        or len(decision["held"]) != 476
        or len(decision["prior_hold_union_ids"]) != 4292
        or _digest(decision["prior_hold_union_ids"]) != decision["prior_hold_union_sha256"]
        or decision["prior_hold_releases"]
        or decision["candidate_prior_hold_intersection_ids"]
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
    hold_ids = sorted(decision["held_ids"] + decision["prior_hold_union_ids"])
    if (
        len(set(ids)) != 1685
        or ids != decision["candidate_ids"]
        or _digest(ids) != decision["candidate_id_sha256"]
        or set(ids) & set(decision["prior_hold_union_ids"])
        or len(set(hold_ids)) != 4768
        or hold_ids != decision["post_review_total_hold_union_ids"]
        or _digest(hold_ids) != decision["post_review_total_hold_union_sha256"]
    ):
        raise ValueError("independent album/HOLD partition differs")
    families = {row["family_key"]: row for row in decision["families"]}
    if (
        len(decision["families"]) != 3
        or {k: v["canonical_name"] for k, v in families.items()} != FAMILY_NAMES
        or decision["canonical_targets"] != FAMILY_NAMES
    ):
        raise ValueError("independent event identities differ")
    for key, family in families.items():
        if (
            family["new_type_required"] is not True
            or family["target_event_id_by_environment"] != {"TEST": None, "PROD": None}
            or family["target_event_edition_id"] is not None
            or (family["approved_count"], family["held_count"]) != FAMILY_COUNTS[key]
        ):
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
        if (
            info["database"] != DATABASES[candidate]
            or (info["preimage"]["path"], info["preimage"]["file_sha256"]) != FROZEN[candidate]
        ):
            raise ValueError("independent environment pin differs")
        frozen = _pinned(*FROZEN[candidate])
        if (
            frozen["format"] != "kifu-event-after-korean-two-next-independent-full-preimage-v1"
            or frozen["environment"] != candidate.upper()
            or frozen["meta"]["database"] != DATABASES[candidate]
            or [r["id"] for r in frozen["albums"]] != ids
            or frozen["statistics"] != info["statistics_before"]
            or frozen["album_columns"] != info["album_columns"]
            or set(frozen["album_columns"]) != {c.name for c in KifuAlbum.__table__.columns}
            or any(set(row) != set(frozen["album_columns"]) for row in frozen["albums"])
        ):
            raise ValueError("frozen exact album/statistics/schema scope differs")
        for key in SNAPSHOT_KEYS:
            if key == "global_counts":
                continue
            if _digest(frozen[key]) != info["guard_sha256"][key]:
                raise ValueError(f"independent frozen {key} SHA differs")
        if [r["id"] for r in frozen["existing_hold_event_slots"]] != decision["prior_hold_union_ids"] or any(
            r["event_id"] is not None or r["event_edition_id"] is not None for r in frozen["existing_hold_event_slots"]
        ):
            raise ValueError("frozen prior HOLD scope differs")
        if [r["id"] for r in frozen["players"]] != info["referenced_player_ids"]:
            raise ValueError("frozen referenced player scope differs")
        albums = {r["id"]: r for r in frozen["albums"]}
        associations = {}
        for row in frozen["album_sources"]:
            associations.setdefault(row["album_id"], []).append(row)
        for record in decision["approved"] + decision["held"]:
            album = albums[record["id"]]
            row_env = record["environments"][candidate.upper()]
            proposed = (
                {
                    "event_id": {
                        "from": None,
                        "to_existing_id": None,
                        "to_canonical_name": record["target_canonical_name"],
                    }
                }
                if record["decision"] == "APPROVE_EVENT_TYPE_ONLY"
                else {}
            )
            if (
                _digest(album) != row_env["album_preimage_sha256"]
                or _digest(associations.get(record["id"], [])) != row_env["album_sources_preimage_sha256"]
                or hashlib.sha256(album["sgf_content"].encode()).hexdigest() != record["sgf_sha256"]
                or album["event_id"] is not None
                or album["event_edition_id"] is not None
                or row_env["before_event_id"] is not None
                or row_env["before_event_edition_id"] is not None
                or row_env["proposed_change"] != proposed
                or any(album[k] != v for k, v in record["raw_preimage"].items())
                or any(album[k] != row_env[k] for k in ("black_player_id", "white_player_id"))
            ):
                raise ValueError(f"independent album/source preimage differs: {record['id']}")
        frozen_by_env[candidate] = frozen
    rebase = _pinned(REBASE_PATH, REBASE_SHA)
    top20 = _pinned(TOP20_PATH, TOP20_SHA)
    if (
        rebase.get("format") != "kifu-event-after-korean-two-next-post-top20-independent-exact-rebase-v1"
        or rebase.get("status") != "APPROVE_EXACT_REBASE_ONLY"
        or rebase["unrelated_drift_accepted"] is not False
        or rebase["database_writes"] != 0
        or (rebase["event_decision"]["path"], rebase["event_decision"]["file_sha256"]) != (DECISION_PATH, DECISION_SHA)
        or (rebase["top20_player_decision"]["path"], rebase["top20_player_decision"]["file_sha256"])
        != (TOP20_PATH, TOP20_SHA)
        or rebase["scope"]["event_approval_changes"]
        or rebase["scope"]["prior_hold_releases"]
        or rebase["scope"]["canonical_targets"] != FAMILY_NAMES
    ):
        raise ValueError("independent exact rebase identity differs")
    for key in (
        "approved_id_sha256",
        "approved_records_sha256",
        "held_id_sha256",
        "held_records_sha256",
        "candidate_id_sha256",
        "prior_hold_union_sha256",
        "post_review_total_hold_union_sha256",
    ):
        if rebase["scope"][key] != decision[key]:
            raise ValueError("independent exact rebase decision scope differs")
    for key in ("top20_commit_receipt", "independent_readonly_capture_script"):
        _pin_bytes(rebase[key]["path"], rebase[key]["file_sha256"])
    for candidate in DATABASES:
        fresh = _pinned(*REBASED[candidate])
        _validate_top20_rebase(candidate, decision, frozen_by_env[candidate], fresh, rebase, top20)
        frozen_by_env[candidate] = fresh
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
        matches = (
            snapshot[key] == frozen[key]
            if key in ("statistics", "album_columns", "global_counts")
            else _same_rows(snapshot[key], frozen[key])
        )
        if not matches:
            raise ValueError(f"frozen {key} differs")
    keys = {_collision_key(name) for name in FAMILY_NAMES.values()}
    if any(_collision_key(r["canonical_name"]) in keys for r in snapshot["events"]) or any(
        _collision_key(r["alias"]) in keys or _collision_key(r["normalized_alias"]) in keys for r in snapshot["aliases"]
    ):
        raise ValueError("approved new event type collides")
    return {
        "format": PLAN_FORMAT,
        "environment": environment,
        "database": database,
        "decision_sha256": decision_sha,
        "frozen_file_sha256": REBASED[environment][1],
        "original_frozen_file_sha256": FROZEN[environment][1],
        "rebase_sha256": REBASE_SHA,
        "top20_applied_plan_sha256": TOP20_PLANS[environment][1],
        "source_manifest_sha256": SOURCE_SHA,
        "targets": dict(FAMILY_NAMES),
        "snapshot": snapshot,
        "counts": {
            "approved": len(decision["approved_ids"]),
            "held": len(decision["held_ids"]),
            "prior_held": len(decision["prior_hold_union_ids"]),
        },
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
    result["global_counts"]["event_links"] += len(decision["approved"])
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
    if plan.get("format") != PLAN_FORMAT or plan.get("environment") != environment:
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
            if len(inserted) != 3 or {r["id"]: r["canonical_name"] for r in inserted} != {
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
