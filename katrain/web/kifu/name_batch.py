"""Transactional import and conditional undo for independently reviewed names."""

from __future__ import annotations

from contextlib import contextmanager
from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import re

from sqlalchemy import DateTime, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from katrain.web.core.models_db import (
    KifuAlbum, KifuAlbumEventSelection, KifuAlbumSource, KifuEvent, KifuEventAlias, KifuEventName, KifuNameBatch,
    KifuNameChange, KifuNameResearchEvidence, KifuNameSourceRegistry,
    KifuPlayer, KifuPlayerAlias, KifuPlayerName, KifuRawEventName, KifuRawEventValue,
    KifuRawPlayerName, KifuRawPlayerValue, KifuSource,
)
from katrain.web.kifu.identity import normalize_alias
from katrain.web.kifu.name_candidates import (
    ARCHIVE_DESCRIPTION_CATEGORY, ARCHIVE_DESCRIPTION_RAW, ARCHIVE_DESCRIPTION_VERSION,
    CandidateError, archive_description_scope, canonical_sha256, validate_bundle,
)
from katrain.web.kifu.name_composition import base_candidate_sha256
from katrain.web.kifu.name_inventory import ALBUM_COLUMNS, SOURCE_COLUMNS, _hash_row, _selection_supplement
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
    KifuRawPlayerValue, KifuRawEventValue, KifuAlbum, KifuAlbumEventSelection,
)}
_ADVISORY_LOCK_KEY = 720220261002
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_TEAM_RAW = "团体赛"
_TEAM_OWNER_ID = 73686
_TEAM_ALL_IDS_SHA256 = "39fee6c73115534d2c206b0eaa4fc834cb6bc624dafdf147a3955fb09a9ea967"
_TEAM_ELIGIBLE_IDS_SHA256 = "8dc603a8278797dd57a271b76f2316cca40c49ed36465001c8d5d9e77f9605bb"
_TEAM_EXCLUDED_IDS_SHA256 = "84e87533c0b750f6bbae1d9dc2df2b738f1075f9e937e65dce7c82cf91ad074b"


def _fail(condition: bool, message: str) -> None:
    if not condition:
        raise BatchError(message)


def _snapshot_parts(conn, *, inventory_format=None) -> tuple[str, dict | None, str]:
    """Recompute the full and base album/source hashes in one transaction."""
    digest = hashlib.sha256()
    for row in conn.execute(select(*ALBUM_COLUMNS).order_by(KifuAlbum.id)):
        _hash_row(digest, b"A", row)
    source_query = (select(*SOURCE_COLUMNS)
                    .join(KifuSource, KifuAlbumSource.source_id == KifuSource.id)
                    .order_by(KifuAlbumSource.id))
    for row in conn.execute(source_query):
        _hash_row(digest, b"S", row)
    base_sha256 = digest.hexdigest()
    selection = _selection_supplement(conn, inventory_format=inventory_format)
    if selection is not None:
        _hash_row(digest, b"E", (selection["selection_format"], selection["sha256"]))
    return digest.hexdigest(), selection, base_sha256


def _snapshot_sha(conn, *, inventory_format=None) -> tuple[str, dict | None]:
    full_sha256, selection, _ = _snapshot_parts(conn, inventory_format=inventory_format)
    return full_sha256, selection


def _catalog_sha(conn) -> str:
    """Hash catalog owners and aliases, including currently unlinked identities."""
    digest = hashlib.sha256()
    for model in (KifuPlayer, KifuEvent, KifuPlayerAlias, KifuEventAlias,
                  KifuRawPlayerValue, KifuRawEventValue):
        table = model.__table__
        # Preserve the pre-pages catalog hash used by already signed bundles.
        # Append-only biography sources are not part of a player's identity.
        columns = (table.c.id, table.c.canonical_name, table.c.created_at) if model is KifuPlayer else (table,)
        for row in conn.execute(select(*columns).order_by(table.c.id)).mappings():
            image = {key: value.isoformat() if isinstance(value, datetime) else value
                     for key, value in row.items()}
            digest.update(model.__tablename__.encode("utf-8") + b":")
            digest.update(canonical_sha256(image).encode("ascii") + b"\n")
    return digest.hexdigest()


def catalog_snapshot_sha(engine) -> str:
    """Produce the v2 catalog supplement hash using only SELECT statements."""
    with engine.connect() as conn:
        return _catalog_sha(conn)


def _approved_name_snapshot(conn) -> list[dict]:
    """Capture complete current approved-name/evidence images in the caller's transaction."""
    from katrain.web.kifu.identity import _approved_names, _qualified_name_rows, _approved_raw_event_names

    def image(model, row):
        return {
            column.name: value.isoformat() if isinstance(value := getattr(row, column.name), datetime) else value
            for column in model.__table__.columns
        }

    snapshot = []
    with Session(bind=conn) as db:
        for kind, (owner_model, name_model, owner_column) in _OWNER.items():
            query = _approved_names(db, name_model, owner_column)
            entities = ()
            if kind.startswith("raw_"):
                query = query.join(owner_model, getattr(name_model, owner_column) == owner_model.id).filter(
                    owner_model.review_status == "approved"
                )
                entities = (owner_model.raw_value,)
            rows = _qualified_name_rows(db, query, name_model, owner_column, *entities)
            composed_ids = {name.id for name, _, *_ in rows if name.decision_kind == "composed"}
            if composed_ids:
                composed_ids = {name.id for name, _, _ in _approved_raw_event_names(db, name_ids=composed_ids)}
            for name, evidence, *_ in rows:
                if name.decision_kind == "composed" and name.id not in composed_ids:
                    continue
                snapshot.append(
                    {
                        "owner": {"kind": kind, "id": getattr(name, owner_column)},
                        "lang": name.lang,
                        "display_name": name.display_name,
                        "decision_kind": name.decision_kind,
                        "review_status": "approved",
                        "name_sha256": canonical_sha256(image(name_model, name)),
                        "evidence_sha256": canonical_sha256(image(KifuNameResearchEvidence, evidence)),
                    }
                )
    return sorted(snapshot, key=lambda row: (row["owner"]["kind"], row["owner"]["id"], row["lang"]))


def orthographic_alias_snapshot(conn):
    """Exact existing player aliases, for collision review; no alias writes."""
    table = KifuPlayerAlias.__table__
    return [
        {"owner": {"kind": "player", "id": row["player_id"]}, "name": row["alias"]}
        for row in conn.execute(select(table).order_by(table.c.id)).mappings()
    ]


def approved_name_snapshot(engine) -> list[dict]:
    """Read the snapshot that finite transliteration reviewers must sign before apply."""
    with engine.connect() as conn:
        return _approved_name_snapshot(conn)


@contextmanager
def _locked_write(engine):
    conn = engine.connect()
    try:
        if engine.dialect.name == "postgresql":
            conn = conn.execution_options(isolation_level="READ COMMITTED")
            conn.begin()
            conn.exec_driver_sql("SELECT pg_advisory_xact_lock(%s)", (_ADVISORY_LOCK_KEY,))
            conn.exec_driver_sql("SELECT pg_advisory_xact_lock(%s)", (720220261003,))
            conn.exec_driver_sql(
                "LOCK TABLE kifu_albums, kifu_album_sources, kifu_sources, "
                "kifu_players, kifu_events, kifu_player_aliases, kifu_event_aliases, "
                "kifu_raw_player_values, kifu_raw_event_values, "
                "kifu_player_names, kifu_event_names, kifu_raw_player_names, kifu_raw_event_names, "
                "kifu_name_research_evidence, kifu_name_source_registry, "
                "kifu_album_event_selections, kifu_event_selection_batches IN SHARE ROW EXCLUSIVE MODE"
            )
        elif engine.dialect.name == "sqlite":
            # CLI engines do not share the application's connect hook. Undo relies
            # on FK rejection when a later edit still references batch evidence.
            conn.exec_driver_sql("PRAGMA foreign_keys=ON")
            _fail(conn.exec_driver_sql("PRAGMA foreign_keys").scalar_one() == 1,
                  "SQLite foreign-key enforcement is required for name batch writes")
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


def _primary_key(table):
    return table.c.album_id if table.name == KifuAlbumEventSelection.__tablename__ else table.c.id


def _image(conn, table, row_id: int) -> dict | None:
    row = conn.execute(select(table).where(_primary_key(table) == row_id)).mappings().one_or_none()
    if row is None:
        return None
    return {key: value.isoformat() if isinstance(value, datetime) else value for key, value in row.items()}


def _team_raw_scope(conn) -> dict:
    """Freeze the one approved mixed raw scope, including complete album and source-link images."""
    def image(row):
        return {key: value.isoformat() if isinstance(value, datetime) else value for key, value in row.items()}

    albums = [image(row) for row in conn.execute(select(KifuAlbum.__table__).where(
        KifuAlbum.event == _TEAM_RAW).order_by(KifuAlbum.id)).mappings()]
    all_ids = [album["id"] for album in albums]
    eligible_ids = [album["id"] for album in albums if album["event_id"] is None]
    excluded_ids = [album["id"] for album in albums if album["event_id"] == 73]
    _fail(len(all_ids) == 324 and canonical_sha256(all_ids) == _TEAM_ALL_IDS_SHA256
          and len(eligible_ids) == 294 and canonical_sha256(eligible_ids) == _TEAM_ELIGIBLE_IDS_SHA256
          and len(excluded_ids) == 30 and canonical_sha256(excluded_ids) == _TEAM_EXCLUDED_IDS_SHA256
          and len(eligible_ids) + len(excluded_ids) == len(all_ids)
          and all(album["duplicate_of_id"] is None and album["list_hidden_reason"] is None for album in albums),
          "team raw title partition differs from the fixed 324/294/30 scope")
    selected = conn.scalar(select(KifuAlbumEventSelection.album_id).where(or_(
        KifuAlbumEventSelection.album_id.in_(all_ids),
        KifuAlbumEventSelection.selected_raw == _TEAM_RAW)).limit(1))
    _fail(selected is None, "team raw title gained selected event scope")
    links = [image(row) for row in conn.execute(select(KifuAlbumSource.__table__).where(
        KifuAlbumSource.album_id.in_(all_ids)).order_by(KifuAlbumSource.album_id, KifuAlbumSource.id)).mappings()]
    by_album = defaultdict(list)
    for link in links:
        by_album[link["album_id"]].append(link)
    _fail(len(links) == len(by_album) == 324, "team raw title source links differ from captured scope")
    rows = [{"album": album, "source_links": by_album[album["id"]]} for album in albums]
    review_scope = {"version": "team1-fixed-mixed-scope-v1", "all_count": 324, "eligible_count": 294,
                    "excluded_linked_count": 30, "excluded_event_id": 73,
                    "all_ids_sha256": _TEAM_ALL_IDS_SHA256,
                    "eligible_ids_sha256": _TEAM_ELIGIBLE_IDS_SHA256,
                    "excluded_linked_ids_sha256": _TEAM_EXCLUDED_IDS_SHA256,
                    "album_scope_sha256": canonical_sha256(rows)}
    return {"rows": rows, "all_ids": all_ids, "review_scope": review_scope}


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
        if candidate["decision_kind"] == "composed":
            capture = candidate.get("preimage_binding", {}).get("capture_sha256")
            _fail(isinstance(capture, str) and _SHA256.fullmatch(capture) is not None,
                  "composed name preimage requires capture SHA-256")
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


def _prevalidate(
    bundle: dict, registry: dict, inventory: dict, evidence_records: list[dict], *, approved_snapshot=None
) -> dict:
    _fail(bundle.get("bundle_format") in {2, 3, 4} or not bundle.get("album_links"),
          "album identity links require bundle format 2, 3 or 4")
    try:
        report = validate_bundle(
            bundle, registry, inventory, evidence_records, approved_name_snapshot=approved_snapshot
        )
    except CandidateError as exc:
        raise BatchError(str(exc)) from exc
    _fail(report["ready"], "bundle has missing, unreviewed, rejected or conflicting name decisions: "
          + "; ".join(report["errors"][:5]))
    _fail(report["write_ready"], "bundle name preimages are not write-ready: "
          + "; ".join(report["write_errors"][:5]))
    if bundle.get("bundle_format") == 4:
        referenced = sorted(row["research_sha256"] for row in bundle["candidates"]
                            if row.get("research_sha256"))
        referenced.extend(
            sorted(
                {
                    row["source_anchor_sha256"]
                    for row in bundle["candidates"]
                    if row.get("decision_kind") == "transliterated"
                }
            )
        )
        referenced.sort()
        supplied = sorted(canonical_sha256(row) for row in evidence_records)
        _fail(supplied == referenced, "unreferenced research or missing candidate evidence in v4 bundle")
    return report


def _check_snapshot(conn, inventory: dict) -> tuple[dict[str, set[int]], dict[int, set[int]]]:
    _fail(inventory.get("inventory_format") in {2, 3, 4}, "inventory format 2, 3 or 4 required")
    actual_database = conn.engine.url.render_as_string(hide_password=True)
    _fail(inventory.get("database_identifier") in {None, actual_database},
          "inventory database identifier differs from target database")
    actual, selection, base_sha256 = _snapshot_parts(conn, inventory_format=inventory["inventory_format"])
    if inventory["inventory_format"] == 4:
        _fail(base_sha256 == inventory.get("base_sha256"), "base album/source snapshot changed")
    _fail((selection is None and inventory["inventory_format"] == 2)
          or (selection is not None and inventory["inventory_format"] in {3, 4}
              and selection == inventory.get("event_selection")),
          "event selection supplement changed")
    _fail(actual == inventory.get("sha256"), f"full database snapshot changed: expected {inventory.get('sha256')}, got {actual}")
    selected_scope = defaultdict(set)
    selected_events = defaultdict(set)
    for row in selection["rows"] if selection is not None else ():
        album_id, raw = row[:2]
        selected_scope[raw].add(album_id)
        if inventory["inventory_format"] == 4 and row[7] is not None:
            selected_events[row[7]].add(album_id)
    return selected_scope, selected_events


def _check_catalog(conn, bundle: dict) -> None:
    if bundle["bundle_format"] in {2, 3, 4} or bundle.get("primary_orthographic") is not None:
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
            current = _image(conn, table, owner["id"])
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
                archive = (kind == "raw_event" and created.get("raw_value") == ARCHIVE_DESCRIPTION_RAW
                           and created.get("category") == ARCHIVE_DESCRIPTION_CATEGORY
                           and created.get("parser_version") == ARCHIVE_DESCRIPTION_VERSION)
                _fail(set(created) == ({"raw_value", "category", "parser_version"} if archive
                                      else {"raw_value", "category"}), "new raw create fields not allowlisted")
                parsed = (parse_player(created["raw_value"], None) if kind == "raw_player"
                          else parse_event(created["raw_value"], None))
                _fail(archive or created["category"] == parsed.category,
                      f"new raw category differs from conservative parser: {_owner_ref(owner)}")
                existing = conn.scalar(select(model.id).where(model.raw_value == created["raw_value"]).limit(1))
                _fail(existing is None, f"new raw value already exists: {_owner_ref(owner)}")


def _check_album_links(conn, bundle: dict) -> None:
    raw_scope_cache = {}
    source_batch_cache = {}
    if bundle["bundle_format"] == 4:
        from katrain.web.kifu.event_selection import _raw_scope_sha256

    for link in bundle["album_links"]:
        album = conn.execute(select(KifuAlbum).where(KifuAlbum.id == link["album_id"])).mappings().one_or_none()
        _fail(album is not None, f"album link row vanished: {link['album_id']}")
        sgf_content = album["sgf_content"]
        _fail(isinstance(sgf_content, str) and
              hashlib.sha256(sgf_content.encode("utf-8")).hexdigest() == link["production_sgf_sha256"],
              f"album link {link['album_id']} SGF content differs from reviewed preimage")
        for field in ("player_black", "player_white", "event", "date_played", "round_name",
                      "black_rank", "white_rank"):
            _fail(album[field] == link["expected"][field],
                  f"album link {link['album_id']} expected {field} differs from live row")
        if link["slot"] == "selected_event":
            current = _image(conn, KifuAlbumEventSelection.__table__, link["album_id"])
            _fail(current == link["selection_before_image"] and current["event_id"] is None,
                  "selected event complete preimage changed")
            _fail(canonical_sha256(current) == link["selection_before_sha256"],
                  "selected event preimage SHA changed")
            _fail(_raw_scope_sha256(conn, current["selected_raw"], raw_scope_cache, source_batch_cache)
                  == link["raw_scope_sha256"], "selected event raw scope changed")
            continue
        column = {"black": "black_player_id", "white": "white_player_id", "event": "event_id"}[link["slot"]]
        _fail(album[column] == link["expected"]["old_id"],
              f"album link {link['album_id']} expected old ID differs from live row")


def _check_raw_owner(conn, row: dict, link_targets: set[str] | None = None,
                     selected_scope: dict[str, set[int]] | None = None,
                     selected_events: dict[int, set[int]] | None = None) -> None:
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
        if kind == "raw_event" and row["decision_kind"] == "translated":
            from katrain.web.kifu.raw_event_translation import eligible_raw_title_owner

            _fail(eligible_raw_title_owner(owner_row),
                  "literal raw title needs an approved readable raw owner")
            direct = conn.execute(select(KifuAlbum.id, KifuAlbum.event_id,
                                         KifuAlbum.duplicate_of_id, KifuAlbum.list_hidden_reason)
                                  .where(KifuAlbum.event == row["raw_value"])).all()
            review = owner_row["review_metadata"] or {}
            if owner_id == _TEAM_OWNER_ID and row["raw_value"] == _TEAM_RAW and review.get("team_scope"):
                team = _team_raw_scope(conn)
                _fail(review["team_scope"] == team["review_scope"]
                      and review["scope_sha256"] == team["review_scope"]["album_scope_sha256"],
                      "team raw title signed album scope changed")
            else:
                _fail(bool(direct) and all(event_id is None and duplicate_id is None and hidden is None
                                           for _, event_id, duplicate_id, hidden in direct),
                      "literal raw title needs only public unlinked direct albums")
            _fail(not (selected_scope or {}).get(row["raw_value"])
                  and conn.scalar(select(KifuAlbumEventSelection.album_id).where(
                      KifuAlbumEventSelection.album_id.in_([album_id for album_id, *_ in direct])).limit(1)) is None,
                  "literal raw title cannot include selected event scope")
        if kind == "raw_event" and (owner_row["category"] == ARCHIVE_DESCRIPTION_CATEGORY
                                    or owner_row["parser_version"] == ARCHIVE_DESCRIPTION_VERSION):
            _fail(row["decision_kind"] == "archive_description"
                  and row["generation_rule_version"] == ARCHIVE_DESCRIPTION_VERSION,
                  "archive owner permits only its dedicated description decision and version")
        if kind == "raw_player":
            raw_in_album = conn.scalar(select(KifuAlbum.id).where(or_(
                KifuAlbum.player_black == row["raw_value"], KifuAlbum.player_white == row["raw_value"])).limit(1))
        else:
            raw_in_album = conn.scalar(select(KifuAlbum.id).where(KifuAlbum.event == row["raw_value"]).limit(1))
        _fail(raw_in_album is not None or (kind == "raw_event" and bool((selected_scope or {}).get(row["raw_value"]))),
              "raw spelling has no live album scope")
    elif kind == "player":
        linked = conn.scalar(select(KifuAlbum.id).where(or_(
            KifuAlbum.black_player_id == owner_id, KifuAlbum.white_player_id == owner_id)).limit(1))
        _fail(linked is not None or _owner_ref(row["owner"]) in (link_targets or set()),
              "player ID is not linked in the current album snapshot or approved links")
    else:
        linked = conn.scalar(select(KifuAlbum.id).where(KifuAlbum.event_id == owner_id).limit(1))
        _fail(linked is not None or bool((selected_events or {}).get(owner_id))
              or _owner_ref(row["owner"]) in (link_targets or set()),
              "event ID is not linked in the current album snapshot or approved links")


def _affected_albums(conn, candidates: list[dict], links: list[dict] | None = None,
                     selected_scope: dict[str, set[int]] | None = None,
                     selected_events: dict[int, set[int]] | None = None) -> list[int]:
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
        if kind == "raw_event":
            ids.update((selected_scope or {}).get(row["raw_value"], ()))
        elif kind == "event":
            ids.update((selected_events or {}).get(target, ()))
    ids.update(link["album_id"] for link in links or ())
    return sorted(ids)


def _check_cross_bundle_collisions(conn, candidates: list[dict], *, resolved_refs=None) -> None:
    from katrain.web.kifu.raw_event_translation import VERSION as RAW_TITLE_VERSION, eligible_literal_raw_name
    languages = {
        row["lang"]
        for row in candidates
        if row["decision_kind"] in {"conventional", "generated", "corrected", "composed", "transliterated", "translated"}
    }
    if not languages:
        return
    existing_names = defaultdict(list)
    for kind, (_owner_model, name_model, owner_column) in _OWNER.items():
        names = conn.execute(select(name_model.__table__).where(name_model.lang.in_(languages),
                                                                 name_model.status == "verified")).mappings()
        for existing in names:
            existing_names[(existing["lang"], normalize_alias(existing["display_name"]))].append(
                (kind, existing[owner_column], existing["evidence_id"], dict(existing)))
    for row in candidates:
        if row["decision_kind"] not in {"conventional", "generated", "corrected", "composed", "transliterated", "translated"}:
            continue
        owner = row["owner"]
        own_kind, own_id = owner["kind"], owner.get("id")
        if "ref" in owner and resolved_refs is not None:
            own_id = resolved_refs.get(_owner_ref(owner))
            _fail(type(own_id) is int and own_id > 0, "applied symbolic owner resolution is missing")
        name_key = normalize_alias(row["display_name"])
        for kind, existing_id, evidence_id, existing_name in existing_names[(row["lang"], name_key)]:
            if kind == own_kind and existing_id == own_id:
                continue
            evidence = _image(conn, KifuNameResearchEvidence.__table__, evidence_id) if evidence_id else None
            if (own_kind == kind == "raw_event" and row["decision_kind"] == "translated"
                    and row["generation_rule_version"] == RAW_TITLE_VERSION
                    and row["review_status"] == "approved" and "id" in owner
                    and eligible_literal_raw_name(existing_name, evidence or {},
                                                  _image(conn, KifuRawEventValue.__table__, existing_id) or {})):
                continue
            previous = (evidence or {}).get("research_payload") or {}
            previous_candidate = previous.get("candidate", {}) if isinstance(previous, dict) else {}
            _fail(
                row["decision_kind"] not in {"composed", "transliterated"}
                and row.get("generation_rule_version") != "primary-orthographic-v1"
                and previous_candidate.get("decision_kind") not in {"composed", "transliterated"}
                and previous_candidate.get("generation_rule_version") != "primary-orthographic-v1"
                and row.get("collision_decision") == "distinct_people_confirmed"
                and row.get("collision_basis")
                and previous_candidate.get("collision_decision") == "distinct_people_confirmed"
                and previous_candidate.get("collision_basis"),
                f"cross-bundle normalized name collision: {row['lang']}:{name_key}",
            )


def _inspect(
    conn, bundle: dict, registry: dict, inventory: dict, evidence_records: list[dict], *, approved_snapshot=None
) -> dict:
    if (
        bundle.get("transliteration") is not None or bundle.get("primary_orthographic") is not None
    ) and approved_snapshot is None:
        approved_snapshot = _approved_name_snapshot(conn)
    report = _prevalidate(bundle, registry, inventory, evidence_records, approved_snapshot=approved_snapshot)
    selected_scope, selected_events = _check_snapshot(conn, inventory)
    _check_catalog(conn, bundle)
    if bundle.get("primary_orthographic") is not None:
        aliases = orthographic_alias_snapshot(conn)
        for signed in bundle["primary_orthographic"]["batches"]:
            _fail(signed["content"]["known_aliases"] == aliases, "orthographic known alias snapshot changed")
    if bundle["bundle_format"] in {2, 3, 4}:
        _check_owner_manifest(conn, bundle)
        _check_album_links(conn, bundle)
    _check_name_preimages(conn, bundle["candidates"])
    link_targets = {_owner_ref(link["target"]) for link in bundle.get("album_links", ())}
    for candidate in bundle["candidates"]:
        _check_raw_owner(conn, candidate, link_targets, selected_scope, selected_events)
    _check_cross_bundle_collisions(conn, bundle["candidates"])
    return {**report, "bundle_sha256": canonical_sha256(bundle),
            "affected_albums": _affected_albums(conn, bundle["candidates"], bundle.get("album_links"),
                                                 selected_scope, selected_events),
            "estimated_undo_rows": len(bundle["candidates"]) * 2
            + len(bundle.get("album_links", ())) + sum("ref" in owner["owner"] for owner in bundle.get("owners", ()))}


def _check_bundle_hash(bundle, expected_bundle_sha256):
    if bundle.get("bundle_format") == 4 or expected_bundle_sha256 is not None:
        _fail(isinstance(expected_bundle_sha256, str) and _SHA256.fullmatch(expected_bundle_sha256) is not None,
              "trusted external bundle SHA-256 is required")
        _fail(canonical_sha256(bundle) == expected_bundle_sha256, "trusted bundle SHA-256 mismatch")


def dry_run_bundle(engine, bundle: dict, registry: dict, inventory: dict, evidence_records: list[dict],
                   *, expected_bundle_sha256: str | None = None) -> dict:
    """Validate against the live database without issuing any write statement."""
    _check_bundle_hash(bundle, expected_bundle_sha256)
    with engine.connect() as conn:
        return _inspect(conn, bundle, registry, inventory, evidence_records)


def _composition_evidence(conn, row: dict, composition: dict, resolved: dict[str, int]) -> dict:
    """Bind immutable approvals to the same-language base just written under this lock."""
    _fail(row["owner"]["kind"] == "raw_event", "composed names require raw event owners")
    series_id = resolved[_owner_ref(row["series_owner"])]
    base = conn.execute(select(KifuEventName.__table__).where(
        KifuEventName.event_id == series_id, KifuEventName.lang == row["lang"])).mappings().one_or_none()
    _fail(base is not None and base["status"] == "verified", "composed base name is missing or unapproved")
    evidence = _image(conn, KifuNameResearchEvidence.__table__, base["evidence_id"])
    candidate = ((evidence or {}).get("research_payload") or {}).get("candidate")
    _fail(evidence is not None and evidence["review_status"] == "approved"
          and evidence["event_id"] == series_id and evidence["lang"] == row["lang"]
          and evidence["revision"] == base["revision"]
          and evidence["candidate_name"] == base["display_name"]
          and isinstance(candidate, dict) and base_candidate_sha256(candidate) == row["base_candidate_sha256"],
          "composed base evidence differs from approved dependency")
    rule = next(rule for rule in composition["rules"] if rule["content"]["lang"] == row["lang"])
    return {
        "version": composition["version"], "rule": rule, "scope": composition["scope"],
        "dependencies": {
            "series_event_id": series_id, "base_name_id": base["id"],
            "base_evidence_id": base["evidence_id"], "base_revision": base["revision"],
            "base_candidate_sha256": row["base_candidate_sha256"],
            "composition_rule_sha256": row["composition_rule_sha256"],
            "raw_scope_sha256": row["raw_scope_sha256"],
            "scope_sha256": canonical_sha256(composition["scope"]),
        },
    }


def _candidate_evidence(
    row: dict,
    research_by_hash: dict[str, dict],
    registry_id: int,
    revision: int,
    owner_id: int,
    composition: dict | None = None,
    transliteration: dict | None = None,
    raw_display_scope: dict | None = None,
    archive_description: dict | None = None,
    primary_orthographic: dict | None = None,
) -> dict:
    owner = row["owner"]
    produced_at = datetime.fromisoformat(row["produced_at"].replace("Z", "+00:00"))
    reviewed_at = datetime.fromisoformat(row["reviewed_at"].replace("Z", "+00:00"))
    payload = {"candidate": row, "research": research_by_hash.get(row.get("research_sha256"))}
    if primary_orthographic is not None:
        payload["primary_orthographic"] = primary_orthographic
    if composition is not None:
        payload["composition"] = composition
    if transliteration is not None:
        payload["transliteration"] = transliteration
    if raw_display_scope is not None:
        payload["raw_display_scope"] = raw_display_scope
    if archive_description is not None:
        payload["archive_description"] = archive_description
    return {
        _OWNER_EVIDENCE_COLUMN[owner["kind"]]: owner_id, "lang": row["lang"], "revision": revision,
        "source_registry_id": registry_id, "candidate_name": row["display_name"],
        "decision_kind": row["decision_kind"], "generation_rule_version": row["generation_rule_version"],
        "research_payload": payload,
        "producer_id": row["producer_id"], "producer_model": row["producer_model"],
        "produced_at": produced_at, "reviewer_id": row["reviewer_id"],
        "reviewer_model": row["reviewer_model"], "reviewed_at": reviewed_at,
        "review_status": "approved",
    }


def _apply_candidate(conn, row: dict, research_by_hash: dict[str, dict], registry_id: int,
                     batch_id: int, sequence: int, resolved: dict[str, int] | None = None,
                     composition: dict | None = None, raw_display_scope: dict | None = None,
                     archive_description: dict | None = None) -> int:
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
    composed = _composition_evidence(conn, row, composition, resolved) if row["decision_kind"] == "composed" else None
    transliteration = (
        {"batch_id": batch_id, "source_anchor": research_by_hash[row["source_anchor_sha256"]]}
        if row["decision_kind"] == "transliterated"
        else None
    )
    evidence_id, evidence_after = _insert(
        conn,
        KifuNameResearchEvidence,
        _candidate_evidence(
            row,
            research_by_hash,
            registry_id,
            revision,
            owner_id,
            composed,
            transliteration,
            (
                {"batch_id": batch_id, "scope_sha256": canonical_sha256(raw_display_scope)}
                if raw_display_scope is not None
                else None
            ),
            archive_description,
            (
                {"batch_id": batch_id, "source_anchor": research_by_hash[row["source_anchor_sha256"]]}
                if row.get("generation_rule_version") == "primary-orthographic-v1"
                else None
            ),
        ),
    )
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
    table = KifuAlbumEventSelection.__table__ if bundle["bundle_format"] == 4 else KifuAlbum.__table__
    model = KifuAlbumEventSelection if bundle["bundle_format"] == 4 else KifuAlbum
    grouped = defaultdict(list)
    for link in bundle.get("album_links", ()):
        grouped[link["album_id"]].append(link)
    for row_id, links in sorted(grouped.items()):
        before = _image(conn, table, row_id)
        changes = {}
        if bundle["bundle_format"] == 4:
            _fail(before == links[0]["selection_before_image"], "selected event complete preimage changed")
        for link in links:
            column = {"black": "black_player_id", "white": "white_player_id", "event": "event_id", "selected_event": "event_id"}[link["slot"]]
            target_id = resolved[_owner_ref(link["target"])]
            _fail(before[column] == link["expected"]["old_id"], "album link changed after snapshot check")
            if before[column] != target_id:
                changes[column] = target_id
        if not changes:
            continue
        conn.execute(table.update().where(_primary_key(table) == row_id).values(**changes))
        after = _image(conn, table, row_id)
        _record_change(conn, batch_id, sequence, model, row_id, before, after)
        sequence += 1
    return sequence


def _check_applied_v4(conn, batch, bundle):
    from katrain.web.kifu.event_selection import verified_selection_rows

    _fail(batch["reviewed_artifact"].get("bundle") == bundle, "applied bundle artifact changed")
    changes = conn.execute(select(KifuNameChange.__table__).where(
        KifuNameChange.batch_id == batch["id"])).mappings().all()
    resolved = batch["reviewed_artifact"].get("resolved_refs", {})
    expected_targets = {(KifuAlbumEventSelection.__tablename__, link["album_id"])
                        for link in bundle["album_links"]}
    for declaration in bundle["owners"]:
        owner = declaration["owner"]
        model = _OWNER[owner["kind"]][0]
        owner_id = resolved.get(_owner_ref(owner))
        _fail(type(owner_id) is int and owner_id > 0, "applied batch owner resolution is missing")
        if "id" in owner:
            _fail(owner_id == owner["id"], "applied batch existing owner resolution changed")
            live_owner = _image(conn, model.__table__, owner_id)
            _fail(live_owner is not None and all(
                live_owner.get(key) == value for key, value in declaration["preimage"].items()),
                "applied batch existing owner preimage changed")
        else:
            expected_targets.add((model.__tablename__, owner_id))
    changes_by_target = {(change["target_table"], change["target_row_id"]): change for change in changes}
    for candidate in bundle["candidates"]:
        owner = candidate["owner"]
        _owner_model, name_model, owner_column = _OWNER[owner["kind"]]
        owner_id = resolved.get(_owner_ref(owner))
        name = conn.execute(select(name_model.__table__).where(
            name_model.__table__.c[owner_column] == owner_id,
            name_model.lang == candidate["lang"])).mappings().one_or_none()
        _fail(name is not None, "applied batch name after-image missing")
        expected_targets.add((name_model.__tablename__, name["id"]))
        expected_targets.add((KifuNameResearchEvidence.__tablename__, name["evidence_id"]))
        name_change = changes_by_target.get((name_model.__tablename__, name["id"]))
        preimage = candidate.get("name_preimage_sha256")
        _fail(name_change is not None and preimage == (
            canonical_sha256(name_change["before_image"]) if name_change["before_image"] is not None else None),
            "applied batch name preimage differs from signed candidate")
        _fail(name["status"] == "verified" and name["display_name"] == candidate["display_name"]
              and name["decision_kind"] == candidate["decision_kind"]
              and name["generation_rule_version"] == candidate["generation_rule_version"],
              "applied batch name differs from signed candidate")
        evidence = conn.execute(select(KifuNameResearchEvidence.__table__).where(
            KifuNameResearchEvidence.id == name["evidence_id"])).mappings().one_or_none()
        _fail(evidence is not None and evidence["revision"] == name["revision"],
              "applied batch candidate evidence missing or revised")
        evidence_change = changes_by_target.get((KifuNameResearchEvidence.__tablename__, name["evidence_id"]))
        _fail(evidence_change is not None and evidence_change["before_image"] is None,
              "applied batch evidence creation ledger changed")
        payload = evidence["research_payload"]
        _fail(isinstance(payload, dict) and payload.get("candidate") == candidate,
              "applied batch evidence differs from signed candidate")
        research = payload.get("research")
        research_hash = candidate.get("research_sha256")
        _fail((canonical_sha256(research) == research_hash) if research_hash else research is None,
              "applied batch research differs from signed candidate")
        transliteration = None
        if candidate["decision_kind"] == "transliterated":
            proof = payload.get("transliteration")
            _fail(
                isinstance(proof, dict)
                and proof.get("batch_id") == batch["id"]
                and canonical_sha256(proof.get("source_anchor")) == candidate["source_anchor_sha256"],
                "applied transliteration source proof changed",
            )
            transliteration = {"batch_id": batch["id"], "source_anchor": proof["source_anchor"]}
        expected_evidence = _candidate_evidence(
            candidate,
            {research_hash: research} if research_hash else {},
            batch["source_registry_id"],
            name["revision"],
            owner_id,
            (
                _composition_evidence(conn, candidate, bundle["composition"], resolved)
                if candidate["decision_kind"] == "composed"
                else None
            ),
            transliteration,
            ({"batch_id": batch["id"], "scope_sha256": candidate["raw_display_scope_sha256"]}
             if "raw_display_scope_sha256" in candidate else None),
        )
        for key, value in expected_evidence.items():
            stored = evidence[key]
            if isinstance(value, datetime) and isinstance(stored, datetime) and stored.tzinfo is None:
                value = value.replace(tzinfo=None)
            _fail(stored == value, "applied batch evidence differs from signed candidate")
    actual_targets = {(change["target_table"], change["target_row_id"]) for change in changes}
    _fail(actual_targets == expected_targets and len(changes) == len(expected_targets),
          "applied batch full ledger changed")
    for change in changes:
        table = _UNDO_TABLES.get(change["target_table"])
        _fail(table is not None and _image(conn, table, change["target_row_id"]) == change["after_image"],
              "applied batch current after-image changed")
    table = KifuAlbumEventSelection.__table__
    ids = [link["album_id"] for link in bundle["album_links"]]
    selections = conn.execute(select(table).where(table.c.album_id.in_(ids))).mappings().all()
    proofs = verified_selection_rows(conn, selections)
    _fail(all(proofs.get(album_id, {}).get("name_batch_id") == batch["id"] for album_id in ids),
          "applied selection target or ledger proof changed")

def apply_bundle(engine, bundle: dict, registry: dict, inventory: dict, evidence_records: list[dict],
                 *, expected_bundle_sha256: str | None = None) -> dict:
    """Apply exactly one reviewed finite bundle in one locked transaction."""
    _check_bundle_hash(bundle, expected_bundle_sha256)
    bundle_hash = canonical_sha256(bundle)
    has_transliteration = bundle.get("transliteration") is not None or bundle.get("primary_orthographic") is not None
    with _locked_write(engine) as conn:
        previous = conn.execute(select(KifuNameBatch).where(KifuNameBatch.bundle_sha256 == bundle_hash)).mappings().one_or_none()
        if previous is not None:
            _fail(previous["status"] == "applied", "bundle was previously undone; issue a new reviewed revision")
            if has_transliteration:
                _prevalidate(
                    bundle,
                    registry,
                    inventory,
                    evidence_records,
                    approved_snapshot=previous["reviewed_artifact"].get("approved_name_snapshot"),
                )
                _fail(
                    previous["reviewed_artifact"].get("bundle") == bundle
                    and previous["reviewed_artifact"].get("research_hashes")
                    == sorted(canonical_sha256(record) for record in evidence_records),
                    "applied transliteration artifact changed",
                )
                changes = (
                    conn.execute(select(KifuNameChange).where(KifuNameChange.batch_id == previous["id"]))
                    .mappings()
                    .all()
                )
                _fail(
                    changes
                    and all(
                        _image(conn, _UNDO_TABLES[change["target_table"]], change["target_row_id"])
                        == change["after_image"]
                        for change in changes
                    ),
                    "applied transliteration after-image changed",
                )
                _check_cross_bundle_collisions(
                    conn, bundle["candidates"], resolved_refs=previous["reviewed_artifact"].get("resolved_refs", {})
                )
            if bundle["bundle_format"] == 4:
                _prevalidate(
                    bundle,
                    registry,
                    inventory,
                    evidence_records,
                    approved_snapshot=previous["reviewed_artifact"].get("approved_name_snapshot"),
                )
                _check_applied_v4(conn, previous, bundle)
            return {"status": "already_applied", "batch_id": previous["id"], "change_count": 0}
        approved_snapshot = _approved_name_snapshot(conn) if has_transliteration else None
        report = _inspect(conn, bundle, registry, inventory, evidence_records, approved_snapshot=approved_snapshot)
        registry_id, _registry_after = _source_registry_for_batch(conn, registry, bundle)
        batch_id, _ = _insert(
            conn,
            KifuNameBatch,
            {
                "bundle_sha256": bundle_hash,
                "inventory_sha256": inventory["sha256"],
                "source_registry_id": registry_id,
                "reviewed_artifact": {
                    "bundle": bundle,
                    "research_hashes": sorted(canonical_sha256(item) for item in evidence_records),
                    **({"approved_name_snapshot": approved_snapshot} if has_transliteration else {}),
                    **(
                        {
                            "orthographic_anchors": [
                                item for item in evidence_records if item.get("evidence_kind") == "primary_orthographic"
                            ],
                            "orthographic_anchor_hashes": sorted(
                                canonical_sha256(item)
                                for item in evidence_records
                                if item.get("evidence_kind") == "primary_orthographic"
                            ),
                        }
                        if bundle.get("primary_orthographic") is not None
                        else {}
                    ),
                },
                "status": "pending",
            },
        )
        sequence = 1
        # Keep the immutable registry snapshot because the retained audit batch references it.
        resolved, sequence = _apply_owners(conn, bundle, batch_id, sequence)
        if bundle["bundle_format"] != 4:
            sequence = _apply_links(conn, bundle, batch_id, sequence, resolved)
        research_by_hash = {canonical_sha256(item): item for item in evidence_records}
        for candidate in sorted(bundle["candidates"], key=lambda row: row["decision_kind"] == "composed"):
            raw_scope = next((declaration.get("raw_display_scope") for declaration in bundle.get("owners", ())
                              if declaration["owner"] == candidate["owner"]), None)
            archive = (archive_description_scope(bundle["inventory_sha256"], next(
                declaration for declaration in bundle["owners"] if declaration["owner"] == candidate["owner"]))
                if candidate["decision_kind"] == "archive_description" else None)
            sequence = _apply_candidate(conn, candidate, research_by_hash, registry_id, batch_id, sequence,
                                        resolved if bundle["bundle_format"] in {2, 3, 4} else None,
                                        bundle.get("composition"), raw_scope, archive)
        if bundle["bundle_format"] == 4:
            sequence = _apply_links(conn, bundle, batch_id, sequence, resolved)
        if bundle["bundle_format"] in {2, 3, 4}:
            artifact = {
                "bundle": bundle,
                "research_hashes": sorted(canonical_sha256(item) for item in evidence_records),
                "resolved_refs": resolved,
                **({"approved_name_snapshot": approved_snapshot} if has_transliteration else {}),
                **(
                    {
                        "orthographic_anchors": [
                            item for item in evidence_records if item.get("evidence_kind") == "primary_orthographic"
                        ],
                        "orthographic_anchor_hashes": sorted(
                            canonical_sha256(item)
                            for item in evidence_records
                            if item.get("evidence_kind") == "primary_orthographic"
                        ),
                    }
                    if bundle.get("primary_orthographic") is not None
                    else {}
                ),
            }
            conn.execute(
                KifuNameBatch.__table__.update().where(KifuNameBatch.id == batch_id).values(reviewed_artifact=artifact)
            )
        conn.execute(
            KifuNameBatch.__table__.update()
            .where(KifuNameBatch.id == batch_id)
            .values(status="applied", applied_at=datetime.now(timezone.utc))
        )
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


def _retained_composition_dependency(conn, table, row_id: int, before_image: dict | None) -> bool:
    """Block undo only when its restored image would break a retained JSON dependency."""
    key = {KifuEventName.__tablename__: "base_name_id",
           KifuNameResearchEvidence.__tablename__: "base_evidence_id"}.get(table.name)
    if key is None:
        return False
    query = select(KifuNameResearchEvidence.research_payload).where(
        KifuNameResearchEvidence.decision_kind == "composed")
    if key == "base_name_id":
        # Only current verified names constrain the live base version. Historical
        # evidence still protects its base evidence row from deletion below.
        query = query.where(KifuNameResearchEvidence.id.in_(select(KifuRawEventName.evidence_id).where(
            KifuRawEventName.status == "verified")))
    payloads = conn.scalars(query)
    for payload in payloads:
        if not isinstance(payload, dict):
            continue
        dependency = ((payload.get("composition") or {}).get("dependencies") or {})
        if dependency.get(key) != row_id:
            continue
        if before_image is None or not (
            before_image.get("event_id") == dependency.get("series_event_id")
            and before_image.get("lang") == payload.get("candidate", {}).get("lang")
            and before_image.get("revision") == dependency.get("base_revision")
        ):
            return True
        if key == "base_name_id":
            if (before_image.get("status") != "verified"
                    or before_image.get("evidence_id") != dependency.get("base_evidence_id")):
                return True
        else:
            candidate = (before_image.get("research_payload") or {}).get("candidate")
            if (before_image.get("review_status") != "approved" or not isinstance(candidate, dict)
                    or base_candidate_sha256(candidate) != dependency.get("base_candidate_sha256")):
                return True
    return False


def undo_batch(engine, batch_id: int) -> dict:
    """Undo each unchanged after-image in reverse order, retaining later edits."""
    with _locked_write(engine) as conn:
        batch = conn.execute(select(KifuNameBatch).where(KifuNameBatch.id == batch_id)).mappings().one_or_none()
        _fail(batch is not None, f"batch {batch_id} not found")
        bundle = batch["reviewed_artifact"].get("bundle")
        _fail(isinstance(bundle, dict) and canonical_sha256(bundle) == batch["bundle_sha256"],
              "batch artifact changed")
        has_selection_change = conn.execute(select(KifuNameChange.id).where(
            KifuNameChange.batch_id == batch_id,
            KifuNameChange.target_table == KifuAlbumEventSelection.__tablename__).limit(1)).first()
        _fail(has_selection_change is None or bundle.get("bundle_format") == 4,
              "selected event artifact changed")
        if isinstance(bundle, dict) and bundle.get("bundle_format") == 4:
            _fail(batch["status"] == "applied", "v4 batch is not applied")
            _fail(canonical_sha256(bundle) == batch["bundle_sha256"], "v4 batch artifact changed")
            _check_applied_v4(conn, batch, bundle)
            changes = conn.execute(select(KifuNameChange).where(KifuNameChange.batch_id == batch_id)
                                   .order_by(KifuNameChange.sequence.desc())).mappings().all()
            try:
                for change in changes:
                    table = _UNDO_TABLES.get(change["target_table"])
                    _fail(table is not None, f"undo target table is not allowlisted: {change['target_table']}")
                    _fail(_image(conn, table, change["target_row_id"]) == change["after_image"],
                          "v4 batch after-image changed")
                    _fail(not _retained_composition_dependency(
                        conn, table, change["target_row_id"], change["before_image"]),
                          "retained composed evidence blocks atomic v4 undo")
                    before = change["before_image"]
                    if before is None:
                        conn.execute(table.delete().where(_primary_key(table) == change["target_row_id"]))
                    else:
                        conn.execute(table.update().where(_primary_key(table) == change["target_row_id"])
                                     .values(**_values_for_table(table, before)))
            except IntegrityError as exc:
                raise BatchError("dependent row blocks atomic v4 undo") from exc
            conn.execute(KifuNameBatch.__table__.update().where(KifuNameBatch.id == batch_id)
                         .values(status="undone"))
            return {"batch_id": batch_id, "status": "undone", "reverted": len(changes),
                    "already_reverted": 0, "skipped": 0}
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
            if _retained_composition_dependency(conn, table, change["target_row_id"], change["before_image"]):
                skipped += 1
                continue
            try:
                with conn.begin_nested():
                    before = change["before_image"]
                    if before is None:
                        conn.execute(table.delete().where(_primary_key(table) == change["target_row_id"]))
                    else:
                        conn.execute(table.update().where(_primary_key(table) == change["target_row_id"])
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
