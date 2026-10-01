"""Transactional import and conditional undo for independently reviewed names.

Only names for identities already linked in the pinned inventory are accepted.
Album identity-link proposals require a separate reviewed contract and are
rejected here; this importer never changes SGF or raw album metadata.
"""

from __future__ import annotations

from contextlib import contextmanager
from collections import defaultdict
from datetime import datetime, timezone
import hashlib

from sqlalchemy import DateTime, func, or_, select
from sqlalchemy.exc import IntegrityError

from katrain.web.core.models_db import (
    KifuAlbum, KifuAlbumSource, KifuEvent, KifuEventName, KifuNameBatch,
    KifuNameChange, KifuNameResearchEvidence, KifuNameSourceRegistry,
    KifuPlayer, KifuPlayerName, KifuRawEventName, KifuRawEventValue,
    KifuRawPlayerName, KifuRawPlayerValue, KifuSource,
)
from katrain.web.kifu.identity import normalize_alias
from katrain.web.kifu.name_candidates import CandidateError, canonical_sha256, validate_bundle
from katrain.web.kifu.name_inventory import ALBUM_COLUMNS, SOURCE_COLUMNS, _hash_row


class BatchError(ValueError):
    """A bundle cannot safely be applied to the current catalog snapshot."""


_OWNER = {
    "player": (KifuPlayer, KifuPlayerName, "player_id"),
    "event": (KifuEvent, KifuEventName, "event_id"),
    "raw_player": (KifuRawPlayerValue, KifuRawPlayerName, "raw_player_id"),
    "raw_event": (KifuRawEventValue, KifuRawEventName, "raw_event_id"),
}
_OWNER_EVIDENCE_COLUMN = {
    "player": "player_id", "event": "event_id", "raw_player": "raw_player_id", "raw_event": "raw_event_id",
}
_UNDO_TABLES = {model.__tablename__: model.__table__ for model in (
    KifuNameSourceRegistry, KifuNameResearchEvidence, KifuPlayerName, KifuEventName,
    KifuRawPlayerName, KifuRawEventName,
)}
_ADVISORY_LOCK_KEY = 720220261002


def _fail(condition: bool, message: str) -> None:
    if not condition:
        raise BatchError(message)


def _snapshot_sha(conn) -> str:
    """Recompute the inventory's full album/source hash inside this transaction."""
    digest = hashlib.sha256()
    for row in conn.execute(select(*ALBUM_COLUMNS).order_by(KifuAlbum.id)):
        _hash_row(digest, b"A", row)
    source_query = (select(*SOURCE_COLUMNS)
                    .join(KifuSource, KifuAlbumSource.source_id == KifuSource.id)
                    .order_by(KifuAlbumSource.id))
    for row in conn.execute(source_query):
        _hash_row(digest, b"S", row)
    return digest.hexdigest()


@contextmanager
def _locked_write(engine):
    conn = engine.connect()
    try:
        if engine.dialect.name == "postgresql":
            conn = conn.execution_options(isolation_level="READ COMMITTED")
            conn.begin()
            conn.exec_driver_sql("SELECT pg_advisory_xact_lock(%s)", (_ADVISORY_LOCK_KEY,))
            conn.exec_driver_sql(
                "LOCK TABLE kifu_albums, kifu_album_sources, kifu_sources, "
                "kifu_player_names, kifu_event_names, kifu_raw_player_names, kifu_raw_event_names, "
                "kifu_name_research_evidence, kifu_name_source_registry IN SHARE ROW EXCLUSIVE MODE"
            )
        elif engine.dialect.name == "sqlite":
            conn.exec_driver_sql("BEGIN IMMEDIATE")
        else:
            raise BatchError("Only PostgreSQL and SQLite are supported")
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _image(conn, table, row_id: int) -> dict | None:
    row = conn.execute(select(table).where(table.c.id == row_id)).mappings().one_or_none()
    if row is None:
        return None
    return {key: value.isoformat() if isinstance(value, datetime) else value for key, value in row.items()}


def _values_for_table(table, image: dict) -> dict:
    values = dict(image)
    for key, value in values.items():
        if value is not None and isinstance(table.c[key].type, DateTime):
            values[key] = datetime.fromisoformat(value)
    return values


def _insert(conn, model, values: dict) -> tuple[int, dict]:
    table = model.__table__
    result = conn.execute(table.insert().values(**values))
    row_id = result.inserted_primary_key[0]
    return row_id, _image(conn, table, row_id)


def _record_change(conn, batch_id: int, sequence: int, model, row_id: int,
                   before: dict | None, after: dict | None) -> None:
    conn.execute(KifuNameChange.__table__.insert().values(
        batch_id=batch_id, sequence=sequence, target_table=model.__tablename__, target_row_id=row_id,
        before_image=before, after_image=after))


def _prevalidate(bundle: dict, registry: dict, inventory: dict, evidence_records: list[dict]) -> dict:
    _fail(not bundle.get("album_links"), "album identity links require a separate approved mapping contract")
    try:
        report = validate_bundle(bundle, registry, inventory, evidence_records)
    except CandidateError as exc:
        raise BatchError(str(exc)) from exc
    _fail(report["ready"], "bundle has missing, unreviewed, rejected or conflicting name decisions: "
          + "; ".join(report["errors"][:5]))
    return report


def _check_snapshot(conn, inventory: dict) -> None:
    _fail(inventory.get("inventory_format") == 2, "inventory format 2 required")
    actual_database = conn.engine.url.render_as_string(hide_password=True)
    _fail(inventory.get("database_identifier") in {None, actual_database},
          "inventory database identifier differs from target database")
    actual = _snapshot_sha(conn)
    _fail(actual == inventory.get("sha256"), f"full database snapshot changed: expected {inventory.get('sha256')}, got {actual}")


def _check_raw_owner(conn, row: dict) -> None:
    kind = row["owner"]["kind"]
    owner_id = row["owner"]["id"]
    owner_model = _OWNER[kind][0]
    owner_row = conn.execute(select(owner_model.__table__).where(owner_model.id == owner_id)).mappings().one_or_none()
    _fail(owner_row is not None, f"owner ID missing: {kind}:{owner_id}")
    if kind.startswith("raw_"):
        _fail(owner_row["raw_value"] == row["raw_value"],
              f"raw ID {kind}:{owner_id} resolves to different spelling")
        if kind == "raw_player":
            raw_in_album = conn.scalar(select(KifuAlbum.id).where(or_(
                KifuAlbum.player_black == row["raw_value"], KifuAlbum.player_white == row["raw_value"])).limit(1))
        else:
            raw_in_album = conn.scalar(select(KifuAlbum.id).where(KifuAlbum.event == row["raw_value"]).limit(1))
        _fail(raw_in_album is not None, "raw spelling has no live album scope")
    elif kind == "player":
        linked = conn.scalar(select(KifuAlbum.id).where(or_(
            KifuAlbum.black_player_id == owner_id, KifuAlbum.white_player_id == owner_id)).limit(1))
        _fail(linked is not None, "player ID is not linked in the current album snapshot")
    else:
        linked = conn.scalar(select(KifuAlbum.id).where(KifuAlbum.event_id == owner_id).limit(1))
        _fail(linked is not None, "event ID is not linked in the current album snapshot")


def _affected_albums(conn, candidates: list[dict]) -> list[int]:
    ids = set()
    for row in candidates:
        owner = row["owner"]
        kind, target = owner["kind"], owner["id"]
        if kind == "player":
            condition = or_(KifuAlbum.black_player_id == target, KifuAlbum.white_player_id == target)
        elif kind == "event":
            condition = KifuAlbum.event_id == target
        elif kind == "raw_player":
            condition = or_(KifuAlbum.player_black == row["raw_value"],
                            KifuAlbum.player_white == row["raw_value"])
        else:
            condition = KifuAlbum.event == row["raw_value"]
        ids.update(conn.scalars(select(KifuAlbum.id).where(condition)))
    return sorted(ids)


def _check_cross_bundle_collisions(conn, candidates: list[dict]) -> None:
    languages = {row["lang"] for row in candidates
                 if row["decision_kind"] in {"conventional", "generated", "corrected"}}
    if not languages:
        return
    existing_names = defaultdict(list)
    for kind, (_owner_model, name_model, owner_column) in _OWNER.items():
        names = conn.execute(select(name_model.__table__).where(name_model.lang.in_(languages),
                                                                 name_model.status == "verified")).mappings()
        for existing in names:
            existing_names[(existing["lang"], normalize_alias(existing["display_name"]))].append(
                (kind, existing[owner_column], existing["evidence_id"]))
    for row in candidates:
        if row["decision_kind"] not in {"conventional", "generated", "corrected"}:
            continue
        owner = row["owner"]
        own_kind, own_id = owner["kind"], owner["id"]
        name_key = normalize_alias(row["display_name"])
        for kind, existing_id, evidence_id in existing_names[(row["lang"], name_key)]:
            if kind == own_kind and existing_id == own_id:
                continue
            evidence = _image(conn, KifuNameResearchEvidence.__table__, evidence_id) if evidence_id else None
            previous = (evidence or {}).get("research_payload") or {}
            previous_candidate = previous.get("candidate", {}) if isinstance(previous, dict) else {}
            _fail(row.get("collision_decision") == "distinct_people_confirmed"
                  and row.get("collision_basis")
                  and previous_candidate.get("collision_decision") == "distinct_people_confirmed"
                  and previous_candidate.get("collision_basis"),
                  f"cross-bundle normalized name collision: {row['lang']}:{name_key}")


def _inspect(conn, bundle: dict, registry: dict, inventory: dict, evidence_records: list[dict]) -> dict:
    report = _prevalidate(bundle, registry, inventory, evidence_records)
    _check_snapshot(conn, inventory)
    for candidate in bundle["candidates"]:
        _check_raw_owner(conn, candidate)
    _check_cross_bundle_collisions(conn, bundle["candidates"])
    return {**report, "bundle_sha256": canonical_sha256(bundle),
            "affected_albums": _affected_albums(conn, bundle["candidates"]),
            "estimated_undo_rows": len(bundle["candidates"]) * 2 + 1}


def dry_run_bundle(engine, bundle: dict, registry: dict, inventory: dict, evidence_records: list[dict]) -> dict:
    """Validate against the live database without issuing any write statement."""
    with engine.connect() as conn:
        return _inspect(conn, bundle, registry, inventory, evidence_records)


def _candidate_evidence(row: dict, research_by_hash: dict[str, dict], registry_id: int, revision: int) -> dict:
    owner = row["owner"]
    produced_at = datetime.fromisoformat(row["produced_at"].replace("Z", "+00:00"))
    reviewed_at = datetime.fromisoformat(row["reviewed_at"].replace("Z", "+00:00"))
    return {
        _OWNER_EVIDENCE_COLUMN[owner["kind"]]: owner["id"], "lang": row["lang"], "revision": revision,
        "source_registry_id": registry_id, "candidate_name": row["display_name"],
        "decision_kind": row["decision_kind"], "generation_rule_version": row["generation_rule_version"],
        "research_payload": {"candidate": row, "research": research_by_hash.get(row.get("research_sha256"))},
        "producer_id": row["producer_id"], "producer_model": row["producer_model"],
        "produced_at": produced_at, "reviewer_id": row["reviewer_id"],
        "reviewer_model": row["reviewer_model"], "reviewed_at": reviewed_at,
        "review_status": "approved",
    }


def _apply_candidate(conn, row: dict, research_by_hash: dict[str, dict], registry_id: int,
                     batch_id: int, sequence: int) -> int:
    owner = row["owner"]
    _owner_model, name_model, owner_column = _OWNER[owner["kind"]]
    name_table = name_model.__table__
    current = conn.execute(select(name_table).where(name_table.c[owner_column] == owner["id"],
                                                    name_table.c.lang == row["lang"])).mappings().one_or_none()
    before = _image(conn, name_table, current["id"]) if current else None
    revision = max(int(current["revision"] or 0), 0) + 1 if current else 1
    evidence_table = KifuNameResearchEvidence.__table__
    latest = conn.scalar(select(func.max(evidence_table.c.revision)).where(
        evidence_table.c[_OWNER_EVIDENCE_COLUMN[owner["kind"]]] == owner["id"],
        evidence_table.c.lang == row["lang"]))
    revision = max(revision, int(latest or 0) + 1)
    evidence_id, evidence_after = _insert(
        conn, KifuNameResearchEvidence, _candidate_evidence(row, research_by_hash, registry_id, revision))
    _record_change(conn, batch_id, sequence, KifuNameResearchEvidence, evidence_id, None, evidence_after)
    sequence += 1
    desired = {"display_name": row["display_name"], "status": "verified",
               "decision_kind": row["decision_kind"], "generation_rule_version": row["generation_rule_version"],
               "revision": revision, "evidence_id": evidence_id}
    if owner["kind"] in {"player", "event"}:
        desired["verified_at"] = datetime.fromisoformat(row["reviewed_at"].replace("Z", "+00:00"))
    if current:
        conn.execute(name_table.update().where(name_table.c.id == current["id"]).values(**desired))
        name_id = current["id"]
    else:
        inserted = {owner_column: owner["id"], "lang": row["lang"], **desired}
        name_id, _ = _insert(conn, name_model, inserted)
    after = _image(conn, name_table, name_id)
    _record_change(conn, batch_id, sequence, name_model, name_id, before, after)
    return sequence + 1


def apply_bundle(engine, bundle: dict, registry: dict, inventory: dict, evidence_records: list[dict]) -> dict:
    """Apply exactly one reviewed finite bundle in one locked transaction."""
    bundle_hash = canonical_sha256(bundle)
    with _locked_write(engine) as conn:
        previous = conn.execute(select(KifuNameBatch).where(KifuNameBatch.bundle_sha256 == bundle_hash)).mappings().one_or_none()
        if previous is not None:
            _fail(previous["status"] == "applied", "bundle was previously undone; issue a new reviewed revision")
            return {"status": "already_applied", "batch_id": previous["id"], "change_count": 0}
        report = _inspect(conn, bundle, registry, inventory, evidence_records)
        registry_id, _registry_after = _source_registry_for_batch(conn, registry, bundle)
        batch_id, _ = _insert(conn, KifuNameBatch, {
            "bundle_sha256": bundle_hash, "inventory_sha256": inventory["sha256"],
            "source_registry_id": registry_id,
            "reviewed_artifact": {"bundle": bundle, "research_hashes": sorted(
                canonical_sha256(item) for item in evidence_records)},
            "status": "pending",
        })
        sequence = 1
        # Keep the immutable registry snapshot because the retained audit batch references it.
        research_by_hash = {canonical_sha256(item): item for item in evidence_records}
        for candidate in bundle["candidates"]:
            sequence = _apply_candidate(conn, candidate, research_by_hash, registry_id, batch_id, sequence)
        conn.execute(KifuNameBatch.__table__.update().where(KifuNameBatch.id == batch_id).values(
            status="applied", applied_at=datetime.now(timezone.utc)))
        return {"status": "applied", "batch_id": batch_id, "change_count": sequence - 1,
                "affected_albums": report["affected_albums"]}


def _source_registry_for_batch(conn, registry: dict, bundle: dict) -> tuple[int, dict | None]:
    """Insert pinned registry if needed; the batch row preserves it for later audit."""
    table = KifuNameSourceRegistry.__table__
    found = conn.execute(select(table).where(table.c.version == registry["version"],
                                             table.c.sha256 == bundle["registry_sha256"])).mappings().one_or_none()
    if found:
        _fail(found["registry"] == registry, "stored registry contents differ from pinned registry")
        return found["id"], None
    return _insert(conn, KifuNameSourceRegistry, {"version": registry["version"],
                                                 "sha256": bundle["registry_sha256"], "registry": registry})


def batch_status(engine, batch_id: int) -> dict:
    with engine.connect() as conn:
        row = conn.execute(select(KifuNameBatch).where(KifuNameBatch.id == batch_id)).mappings().one_or_none()
        _fail(row is not None, f"batch {batch_id} not found")
        count = conn.scalar(select(func.count()).select_from(KifuNameChange)
                            .where(KifuNameChange.batch_id == batch_id))
        return {"batch_id": batch_id, "status": row["status"], "bundle_sha256": row["bundle_sha256"],
                "inventory_sha256": row["inventory_sha256"], "change_count": count}


def undo_batch(engine, batch_id: int) -> dict:
    """Undo each unchanged after-image in reverse order, retaining later edits."""
    with _locked_write(engine) as conn:
        batch = conn.execute(select(KifuNameBatch).where(KifuNameBatch.id == batch_id)).mappings().one_or_none()
        _fail(batch is not None, f"batch {batch_id} not found")
        _fail(batch["status"] in {"applied", "partial_undo"}, "batch is not applied")
        changes = conn.execute(select(KifuNameChange).where(KifuNameChange.batch_id == batch_id)
                               .order_by(KifuNameChange.sequence.desc())).mappings().all()
        reverted = skipped = already_reverted = 0
        for change in changes:
            table = _UNDO_TABLES.get(change["target_table"])
            _fail(table is not None, f"undo target table is not allowlisted: {change['target_table']}")
            current = _image(conn, table, change["target_row_id"])
            if current == change["before_image"]:
                already_reverted += 1
                continue
            if current != change["after_image"]:
                skipped += 1
                continue
            try:
                with conn.begin_nested():
                    before = change["before_image"]
                    if before is None:
                        conn.execute(table.delete().where(table.c.id == change["target_row_id"]))
                    else:
                        conn.execute(table.update().where(table.c.id == change["target_row_id"])
                                     .values(**_values_for_table(table, before)))
            except IntegrityError:
                # A later edit may still reference this row. Never delete it.
                skipped += 1
                continue
            reverted += 1
        status = "undone" if skipped == 0 else "partial_undo"
        conn.execute(KifuNameBatch.__table__.update().where(KifuNameBatch.id == batch_id).values(status=status))
        return {"batch_id": batch_id, "status": status, "reverted": reverted,
                "already_reverted": already_reverted, "skipped": skipped}
