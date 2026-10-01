"""Transactional import and conditional undo for independently reviewed names."""

from __future__ import annotations

from contextlib import contextmanager
from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import re

from sqlalchemy import DateTime, func, or_, select
from sqlalchemy.exc import IntegrityError

from katrain.web.core.models_db import (
    KifuAlbum, KifuAlbumSource, KifuEvent, KifuEventAlias, KifuEventName, KifuNameBatch,
    KifuNameChange, KifuNameResearchEvidence, KifuNameSourceRegistry,
    KifuPlayer, KifuPlayerAlias, KifuPlayerName, KifuRawEventName, KifuRawEventValue,
    KifuRawPlayerName, KifuRawPlayerValue, KifuSource,
)
from katrain.web.kifu.identity import normalize_alias
from katrain.web.kifu.name_candidates import CandidateError, canonical_sha256, validate_bundle
from katrain.web.kifu.name_inventory import ALBUM_COLUMNS, SOURCE_COLUMNS, _hash_row
from katrain.web.kifu.name_parse import parse_event, parse_player


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
    KifuRawPlayerName, KifuRawEventName, KifuPlayer, KifuEvent,
    KifuRawPlayerValue, KifuRawEventValue, KifuAlbum,
)}
_ADVISORY_LOCK_KEY = 720220261002
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


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


def _catalog_sha(conn) -> str:
    """Hash catalog owners and aliases, including currently unlinked identities."""
    digest = hashlib.sha256()
    for model in (KifuPlayer, KifuEvent, KifuPlayerAlias, KifuEventAlias,
                  KifuRawPlayerValue, KifuRawEventValue):
        table = model.__table__
        for row in conn.execute(select(table).order_by(table.c.id)).mappings():
            image = {key: value.isoformat() if isinstance(value, datetime) else value
                     for key, value in row.items()}
            digest.update(model.__tablename__.encode("utf-8") + b":")
            digest.update(canonical_sha256(image).encode("ascii") + b"\n")
    return digest.hexdigest()


def catalog_snapshot_sha(engine) -> str:
    """Produce the v2 catalog supplement hash using only SELECT statements."""
    with engine.connect() as conn:
        return _catalog_sha(conn)


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
                "kifu_players, kifu_events, kifu_player_aliases, kifu_event_aliases, "
                "kifu_raw_player_values, kifu_raw_event_values, "
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


def _name_preimage_sha256(conn, owner: dict, lang: str) -> str | None:
    """Hash the complete existing name row, or record that no row exists."""
    _owner_model, name_model, owner_column = _OWNER[owner["kind"]]
    table = name_model.__table__
    row_id = conn.scalar(select(table.c.id).where(
        table.c[owner_column] == owner["id"], table.c.lang == lang))
    return canonical_sha256(_image(conn, table, row_id)) if row_id is not None else None


def name_preimage_sha256(engine, owner: dict, lang: str) -> str | None:
    """Capture a read-only name preimage before an independently reviewed bundle is signed."""
    _fail(owner.get("kind") in _OWNER and type(owner.get("id")) is int and owner["id"] > 0,
          "existing name owner ID required")
    with engine.connect() as conn:
        return _name_preimage_sha256(conn, owner, lang)


def _check_name_preimages(conn, candidates: list[dict]) -> None:
    for candidate in candidates:
        _fail("name_preimage_sha256" in candidate, "name preimage is missing from reviewed candidate")
        expected = candidate["name_preimage_sha256"]
        _fail(expected is None or (isinstance(expected, str) and _SHA256.fullmatch(expected) is not None),
              "name preimage must be null or a lowercase SHA-256")
        owner = candidate["owner"]
        if "ref" in owner:
            _fail(expected is None, "new owner name preimage must be absent")
            continue
        actual = _name_preimage_sha256(conn, owner, candidate["lang"])
        _fail(actual == expected, f"name preimage changed: {_owner_ref(owner)}:{candidate['lang']}")


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
    _fail(bundle.get("bundle_format") == 2 or not bundle.get("album_links"),
          "album identity links require bundle format 2")
    try:
        report = validate_bundle(bundle, registry, inventory, evidence_records)
    except CandidateError as exc:
        raise BatchError(str(exc)) from exc
    _fail(report["ready"], "bundle has missing, unreviewed, rejected or conflicting name decisions: "
          + "; ".join(report["errors"][:5]))
    _fail(report["write_ready"], "bundle name preimages are not write-ready: "
          + "; ".join(report["write_errors"][:5]))
    return report


def _check_snapshot(conn, inventory: dict) -> None:
    _fail(inventory.get("inventory_format") == 2, "inventory format 2 required")
    actual_database = conn.engine.url.render_as_string(hide_password=True)
    _fail(inventory.get("database_identifier") in {None, actual_database},
          "inventory database identifier differs from target database")
    actual = _snapshot_sha(conn)
    _fail(actual == inventory.get("sha256"), f"full database snapshot changed: expected {inventory.get('sha256')}, got {actual}")


def _check_catalog(conn, bundle: dict) -> None:
    if bundle["bundle_format"] == 2:
        actual = _catalog_sha(conn)
        _fail(actual == bundle["catalog_sha256"],
              f"catalog supplement snapshot changed: expected {bundle['catalog_sha256']}, got {actual}")


def _owner_ref(owner: dict) -> str:
    return f"{owner['kind']}:@{owner['ref']}" if "ref" in owner else f"{owner['kind']}:{owner['id']}"


def _reviewed_collision(declaration: dict) -> bool:
    review = declaration.get("alias_collision_review")
    return bool(isinstance(review, dict) and review.get("status") == "approved"
                and review.get("producer_id") and review.get("producer_model")
                and review.get("reviewer_id") and review.get("reviewer_model")
                and review["reviewer_id"] != review["producer_id"]
                and review.get("basis") and review.get("source_urls"))


def _check_owner_manifest(conn, bundle: dict) -> None:
    proposed_names = defaultdict(list)
    for declaration in bundle["owners"]:
        owner = declaration["owner"]
        kind = owner["kind"]
        model = _OWNER[kind][0]
        table = model.__table__
        if "id" in owner:
            current = conn.execute(select(table).where(table.c.id == owner["id"])).mappings().one_or_none()
            _fail(current is not None, f"owner preimage missing: {_owner_ref(owner)}")
            expected = declaration["preimage"]
            _fail(all(current.get(key) == value for key, value in expected.items()),
                  f"owner catalog preimage differs: {_owner_ref(owner)}")
        else:
            created = declaration["create"]
            if kind in {"player", "event"}:
                _fail(set(created) == {"canonical_name"}, "new identity create fields not allowlisted")
                target = normalize_alias(created["canonical_name"])
                for earlier in proposed_names[(kind, target)]:
                    _fail(_reviewed_collision(declaration) and _reviewed_collision(earlier),
                          f"new identities share a normalized canonical name: {_owner_ref(owner)}")
                proposed_names[(kind, target)].append(declaration)
                canonical_collision = any(normalize_alias(value) == target for value in conn.scalars(
                    select(model.canonical_name)))
                alias_model = KifuPlayerAlias if kind == "player" else KifuEventAlias
                alias_collision = any(normalize_alias(value) == target for value in conn.scalars(
                    select(alias_model.alias)))
                _fail(not (canonical_collision or alias_collision) or _reviewed_collision(declaration),
                      f"new identity alias collision needs independent review: {_owner_ref(owner)}")
            else:
                _fail(set(created) == {"raw_value", "category"}, "new raw create fields not allowlisted")
                parsed = (parse_player(created["raw_value"], None) if kind == "raw_player"
                          else parse_event(created["raw_value"], None))
                _fail(created["category"] == parsed.category,
                      f"new raw category differs from conservative parser: {_owner_ref(owner)}")
                existing = conn.scalar(select(model.id).where(model.raw_value == created["raw_value"]).limit(1))
                _fail(existing is None, f"new raw value already exists: {_owner_ref(owner)}")


def _check_album_links(conn, bundle: dict) -> None:
    for link in bundle["album_links"]:
        album = conn.execute(select(KifuAlbum).where(KifuAlbum.id == link["album_id"])).mappings().one_or_none()
        _fail(album is not None, f"album link row vanished: {link['album_id']}")
        for field in ("player_black", "player_white", "event", "date_played", "round_name",
                      "black_rank", "white_rank"):
            _fail(album[field] == link["expected"][field],
                  f"album link {link['album_id']} expected {field} differs from live row")
        column = {"black": "black_player_id", "white": "white_player_id", "event": "event_id"}[link["slot"]]
        _fail(album[column] == link["expected"]["old_id"],
              f"album link {link['album_id']} expected old ID differs from live row")


def _check_raw_owner(conn, row: dict, link_targets: set[str] | None = None) -> None:
    kind = row["owner"]["kind"]
    if "ref" in row["owner"]:
        if kind.startswith("raw_"):
            owner_model = _OWNER[kind][0]
            found = conn.scalar(select(owner_model.id).where(owner_model.raw_value == row["raw_value"]).limit(1))
            _fail(found is None, "new raw ref duplicates an existing raw ID/spelling")
        return
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
        _fail(linked is not None or _owner_ref(row["owner"]) in (link_targets or set()),
              "player ID is not linked in the current album snapshot or approved links")
    else:
        linked = conn.scalar(select(KifuAlbum.id).where(KifuAlbum.event_id == owner_id).limit(1))
        _fail(linked is not None or _owner_ref(row["owner"]) in (link_targets or set()),
              "event ID is not linked in the current album snapshot or approved links")


def _affected_albums(conn, candidates: list[dict], links: list[dict] | None = None) -> list[int]:
    ids = set()
    for row in candidates:
        owner = row["owner"]
        kind, target = owner["kind"], owner.get("id")
        if kind == "player":
            if target is None:
                continue
            condition = or_(KifuAlbum.black_player_id == target, KifuAlbum.white_player_id == target)
        elif kind == "event":
            if target is None:
                continue
            condition = KifuAlbum.event_id == target
        elif kind == "raw_player":
            condition = or_(KifuAlbum.player_black == row["raw_value"],
                            KifuAlbum.player_white == row["raw_value"])
        else:
            condition = KifuAlbum.event == row["raw_value"]
        ids.update(conn.scalars(select(KifuAlbum.id).where(condition)))
    ids.update(link["album_id"] for link in links or ())
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
        own_kind, own_id = owner["kind"], owner.get("id")
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
    _check_catalog(conn, bundle)
    if bundle["bundle_format"] == 2:
        _check_owner_manifest(conn, bundle)
        _check_album_links(conn, bundle)
    _check_name_preimages(conn, bundle["candidates"])
    link_targets = {_owner_ref(link["target"]) for link in bundle.get("album_links", ())}
    for candidate in bundle["candidates"]:
        _check_raw_owner(conn, candidate, link_targets)
    _check_cross_bundle_collisions(conn, bundle["candidates"])
    return {**report, "bundle_sha256": canonical_sha256(bundle),
            "affected_albums": _affected_albums(conn, bundle["candidates"], bundle.get("album_links")),
            "estimated_undo_rows": len(bundle["candidates"]) * 2
            + len(bundle.get("album_links", ())) + sum("ref" in owner["owner"] for owner in bundle.get("owners", ()))}


def dry_run_bundle(engine, bundle: dict, registry: dict, inventory: dict, evidence_records: list[dict]) -> dict:
    """Validate against the live database without issuing any write statement."""
    with engine.connect() as conn:
        return _inspect(conn, bundle, registry, inventory, evidence_records)


def _candidate_evidence(row: dict, research_by_hash: dict[str, dict], registry_id: int,
                        revision: int, owner_id: int) -> dict:
    owner = row["owner"]
    produced_at = datetime.fromisoformat(row["produced_at"].replace("Z", "+00:00"))
    reviewed_at = datetime.fromisoformat(row["reviewed_at"].replace("Z", "+00:00"))
    return {
        _OWNER_EVIDENCE_COLUMN[owner["kind"]]: owner_id, "lang": row["lang"], "revision": revision,
        "source_registry_id": registry_id, "candidate_name": row["display_name"],
        "decision_kind": row["decision_kind"], "generation_rule_version": row["generation_rule_version"],
        "research_payload": {"candidate": row, "research": research_by_hash.get(row.get("research_sha256"))},
        "producer_id": row["producer_id"], "producer_model": row["producer_model"],
        "produced_at": produced_at, "reviewer_id": row["reviewer_id"],
        "reviewer_model": row["reviewer_model"], "reviewed_at": reviewed_at,
        "review_status": "approved",
    }


def _apply_candidate(conn, row: dict, research_by_hash: dict[str, dict], registry_id: int,
                     batch_id: int, sequence: int, resolved: dict[str, int] | None = None) -> int:
    owner = row["owner"]
    owner_id = resolved[_owner_ref(owner)] if resolved is not None else owner["id"]
    _owner_model, name_model, owner_column = _OWNER[owner["kind"]]
    name_table = name_model.__table__
    current = conn.execute(select(name_table).where(name_table.c[owner_column] == owner_id,
                                                    name_table.c.lang == row["lang"])).mappings().one_or_none()
    before = _image(conn, name_table, current["id"]) if current else None
    revision = max(int(current["revision"] or 0), 0) + 1 if current else 1
    evidence_table = KifuNameResearchEvidence.__table__
    latest = conn.scalar(select(func.max(evidence_table.c.revision)).where(
        evidence_table.c[_OWNER_EVIDENCE_COLUMN[owner["kind"]]] == owner_id,
        evidence_table.c.lang == row["lang"]))
    revision = max(revision, int(latest or 0) + 1)
    evidence_id, evidence_after = _insert(
        conn, KifuNameResearchEvidence, _candidate_evidence(row, research_by_hash, registry_id, revision, owner_id))
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
        inserted = {owner_column: owner_id, "lang": row["lang"], **desired}
        name_id, _ = _insert(conn, name_model, inserted)
    after = _image(conn, name_table, name_id)
    _record_change(conn, batch_id, sequence, name_model, name_id, before, after)
    return sequence + 1


def _apply_owners(conn, bundle: dict, batch_id: int, sequence: int) -> tuple[dict[str, int], int]:
    resolved = {}
    for declaration in bundle.get("owners", ()):
        owner = declaration["owner"]
        token = _owner_ref(owner)
        if "id" in owner:
            resolved[token] = owner["id"]
            continue
        model = _OWNER[owner["kind"]][0]
        created = dict(declaration["create"])
        if owner["kind"].startswith("raw_"):
            created["review_status"] = "approved"
            created["review_metadata"] = declaration["category_review"]
        row_id, after = _insert(conn, model, created)
        _record_change(conn, batch_id, sequence, model, row_id, None, after)
        sequence += 1
        resolved[token] = row_id
    return resolved, sequence


def _apply_links(conn, bundle: dict, batch_id: int, sequence: int, resolved: dict[str, int]) -> int:
    table = KifuAlbum.__table__
    grouped = defaultdict(list)
    for link in bundle.get("album_links", ()):
        grouped[link["album_id"]].append(link)
    for row_id, links in sorted(grouped.items()):
        before = _image(conn, table, row_id)
        changes = {}
        for link in links:
            column = {"black": "black_player_id", "white": "white_player_id", "event": "event_id"}[link["slot"]]
            target_id = resolved[_owner_ref(link["target"])]
            _fail(before[column] == link["expected"]["old_id"], "album link changed after snapshot check")
            if before[column] != target_id:
                changes[column] = target_id
        if not changes:
            continue
        conn.execute(table.update().where(table.c.id == row_id).values(**changes))
        after = _image(conn, table, row_id)
        _record_change(conn, batch_id, sequence, KifuAlbum, row_id, before, after)
        sequence += 1
    return sequence


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
        resolved, sequence = _apply_owners(conn, bundle, batch_id, sequence)
        sequence = _apply_links(conn, bundle, batch_id, sequence, resolved)
        research_by_hash = {canonical_sha256(item): item for item in evidence_records}
        for candidate in bundle["candidates"]:
            sequence = _apply_candidate(conn, candidate, research_by_hash, registry_id, batch_id, sequence,
                                        resolved if bundle["bundle_format"] == 2 else None)
        if bundle["bundle_format"] == 2:
            artifact = {"bundle": bundle, "research_hashes": sorted(canonical_sha256(item)
                         for item in evidence_records), "resolved_refs": resolved}
            conn.execute(KifuNameBatch.__table__.update().where(KifuNameBatch.id == batch_id)
                         .values(reviewed_artifact=artifact))
        conn.execute(KifuNameBatch.__table__.update().where(KifuNameBatch.id == batch_id).values(
            status="applied", applied_at=datetime.now(timezone.utc)))
        return {"status": "applied", "batch_id": batch_id, "change_count": sequence - 1,
                "affected_albums": report["affected_albums"], "resolved_refs": resolved}


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
