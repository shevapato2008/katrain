"""Finite Elasticsearch projections after a real PostgreSQL business commit.

The existing writer's session advisory locks cover the gate, transaction,
projection and refresh. Receipts and native before/after journals remain the
recovery authority; this module adds no business journal or database table.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import os
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from katrain.web.core.models_db import (
    KifuAlbum,
    KifuAlbumEventSelection,
    KifuEventSelectionBatch,
    KifuNameBatch,
    KifuNameChange,
    KifuNameResearchEvidence,
    KifuPlayerName,
    KifuEventName,
    KifuRawPlayerName,
    KifuRawEventName,
)
from katrain.web.kifu.identity import strict_names_enabled
from katrain.web.kifu.name_candidates import canonical_sha256
from katrain.web.kifu.search_documents import SCHEMA_VERSION

STATE_ID = "sync-state"


class SearchIndexPending(RuntimeError):
    """Business data may be committed; repair this original operation, never undo it."""

    def __init__(self, operation_ref, message="search_index_pending"):
        self.operation_ref = operation_ref
        super().__init__(f"{message}; repair the original operation reference")


@dataclass
class ChangeScope:
    album_ids: set[int] = field(default_factory=set)
    owners: set[tuple[str, int]] = field(default_factory=set)
    terms: set[str] = field(default_factory=set)
    changed_owners: set[tuple[str, int]] = field(default_factory=set)

    def merge(self, other):
        self.album_ids.update(other.album_ids)
        self.owners.update(other.owners)
        self.terms.update(other.terms)
        self.changed_owners.update(other.changed_owners)
        return self


@dataclass
class SyncToken:
    client: object
    state: dict
    scope: ChangeScope


def sync_mode():
    mode = os.getenv("KIFU_SEARCH_SYNC_MODE", "disabled").lower()
    if mode not in {"disabled", "bootstrap", "enabled"}:
        raise ValueError("KIFU_SEARCH_SYNC_MODE must be disabled, bootstrap or enabled")
    if mode != "enabled" and os.getenv("KIFU_SEARCH_BACKEND", "legacy").lower() != "legacy":
        raise ValueError("Elasticsearch reads require enabled writer sync")
    if mode == "bootstrap" and os.getenv("KIFU_SEARCH_BOOTSTRAP_QUIESCENT") != "1":
        raise ValueError("bootstrap requires the explicit quiescent initial-build window")
    return mode


def _writer_client():
    from katrain.web.kifu.search_es import ElasticsearchClient, SearchSettings

    return ElasticsearchClient(SearchSettings.from_env(role="writer"))


def _collect_scope(value, scope):
    """Extract only explicit IDs/scopes/text from original native audit images."""
    if isinstance(value, dict):
        owner = value.get("owner")
        if isinstance(owner, dict) and owner.get("kind") in {"player", "event", "raw_player", "raw_event"}:
            if type(owner.get("id")) is int and owner["id"] > 0:
                scope.owners.add((owner["kind"], owner["id"]))
        for key, item in value.items():
            if key == "album_id" and type(item) is int and item > 0:
                scope.album_ids.add(item)
            elif key in {"affected_album_ids", "occurrence_album_ids", "album_ids"} and isinstance(item, list):
                scope.album_ids.update(x for x in item if type(x) is int and x > 0)
            elif key in {
                "player_id",
                "black_player_id",
                "white_player_id",
                "event_id",
                "raw_player_id",
                "raw_event_id",
            }:
                if type(item) is int and item > 0:
                    kind = {"black_player_id": "player", "white_player_id": "player"}.get(key, key.removesuffix("_id"))
                    scope.owners.add((kind, item))
            elif key in {"display_name", "canonical_name", "raw_value", "selected_raw", "alias"} and isinstance(
                item, str
            ):
                if item.strip():
                    scope.terms.add(item.strip().lower())
            _collect_scope(item, scope)
    elif isinstance(value, (tuple, list)):
        for item in value:
            _collect_scope(item, scope)


def _batch_scope(conn, batch_id):
    scope = ChangeScope()
    batch = conn.execute(select(KifuNameBatch.__table__).where(KifuNameBatch.id == batch_id)).mappings().one_or_none()
    if batch is None:
        raise SearchIndexPending({"batch_id": batch_id}, "original search repair journal is missing")
    artifact = batch["reviewed_artifact"]
    if not isinstance(artifact, dict):
        raise SearchIndexPending({"batch_id": batch_id}, "original search repair artifact is missing")
    _collect_scope(artifact, scope)
    receipt = artifact.get("receipt")
    guard = artifact.get("undo_guard")
    ids = {batch_id}
    if isinstance(receipt, dict):
        if (
            not isinstance(guard, dict)
            or guard.get("version") != "kifu-publication-undo-v1"
            or guard.get("receipt_sha256") != canonical_sha256(receipt)
            or guard.get("sources_sha256") != canonical_sha256(artifact.get("sources"))
        ):
            raise SearchIndexPending({"batch_id": batch_id}, "original publication receipt changed")
        ids.update(x for x in (receipt.get("reviewed_name_batch_id"), receipt.get("name_batch_id")) if x is not None)
        journals = guard.get("batches")
        if (
            not isinstance(journals, list)
            or len(journals) != len(ids)
            or {row.get("batch_id") for row in journals} != ids
        ):
            raise SearchIndexPending({"batch_id": batch_id}, "original publication journal membership changed")
        for journal in journals:
            digest = conn.scalar(select(KifuNameBatch.bundle_sha256).where(KifuNameBatch.id == journal["batch_id"]))
            columns = (
                KifuNameChange.sequence,
                KifuNameChange.target_table,
                KifuNameChange.target_row_id,
                KifuNameChange.before_image,
                KifuNameChange.after_image,
            )
            changes = [
                dict(row)
                for row in conn.execute(
                    select(*columns)
                    .where(KifuNameChange.batch_id == journal["batch_id"])
                    .order_by(KifuNameChange.sequence)
                ).mappings()
            ]
            if digest != journal.get("bundle_sha256") or canonical_sha256(changes) != journal.get("journal_sha256"):
                raise SearchIndexPending({"batch_id": batch_id}, "original publication journal changed")
    else:
        original = artifact.get("bundle", artifact.get("plan"))
        if not isinstance(original, dict) or canonical_sha256(original) != batch["bundle_sha256"]:
            raise SearchIndexPending({"batch_id": batch_id}, "original name or duplicate artifact changed")
    for change in conn.execute(select(KifuNameChange.__table__).where(KifuNameChange.batch_id.in_(ids))).mappings():
        _collect_scope(change["before_image"], scope)
        _collect_scope(change["after_image"], scope)
        if change["target_table"] == KifuAlbum.__tablename__:
            scope.album_ids.add(change["target_row_id"])
        if change["target_table"] == KifuAlbumEventSelection.__tablename__:
            scope.album_ids.add(change["target_row_id"])
        for kind, table in {
            "player": "kifu_players",
            "event": "kifu_events",
            "raw_player": "kifu_raw_player_values",
            "raw_event": "kifu_raw_event_values",
        }.items():
            if change["target_table"] == table:
                scope.owners.add((kind, change["target_row_id"]))
                scope.changed_owners.add((kind, change["target_row_id"]))
        changed = ChangeScope()
        _collect_scope(change["before_image"], changed)
        _collect_scope(change["after_image"], changed)
        if change["target_table"] in {
            "kifu_player_names",
            "kifu_event_names",
            "kifu_player_aliases",
            "kifu_event_aliases",
            "kifu_name_research_evidence",
        }:
            scope.changed_owners.update(changed.owners)
    return _expand_scope(conn, scope)


def _expand_scope(conn, scope):
    """Newly public canonical owners can expose old albums through indexed FKs."""
    players = {oid for kind, oid in scope.changed_owners if kind == "player"}
    events = {oid for kind, oid in scope.changed_owners if kind == "event"}
    if scope.album_ids:
        for black, white, event in conn.execute(
            select(KifuAlbum.black_player_id, KifuAlbum.white_player_id, KifuAlbum.event_id).where(
                KifuAlbum.id.in_(scope.album_ids)
            )
        ):
            scope.owners.update(("player", value) for value in (black, white) if value is not None)
            if event is not None:
                scope.owners.add(("event", event))
    if players:
        # Keep the two indexed branches distinct; never scan the album catalog.
        scope.album_ids.update(conn.scalars(select(KifuAlbum.id).where(KifuAlbum.black_player_id.in_(players))))
        scope.album_ids.update(conn.scalars(select(KifuAlbum.id).where(KifuAlbum.white_player_id.in_(players))))
    if events:
        scope.album_ids.update(conn.scalars(select(KifuAlbum.id).where(KifuAlbum.event_id.in_(events))))
        scope.album_ids.update(
            conn.scalars(select(KifuAlbumEventSelection.album_id).where(KifuAlbumEventSelection.event_id.in_(events)))
        )
    specs = {
        "player": (KifuPlayerName, "player_id"),
        "event": (KifuEventName, "event_id"),
        "raw_player": (KifuRawPlayerName, "raw_player_id"),
        "raw_event": (KifuRawEventName, "raw_event_id"),
    }
    for kind, (model, column) in specs.items():
        owner_ids = {oid for owner_kind, oid in scope.owners if owner_kind == kind}
        if not owner_ids:
            continue
        for row in conn.execute(select(model.__table__).where(getattr(model, column).in_(owner_ids))).mappings():
            _collect_scope(dict(row), scope)
            if row["evidence_id"] is not None:
                payload = conn.scalar(
                    select(KifuNameResearchEvidence.research_payload).where(
                        KifuNameResearchEvidence.id == row["evidence_id"]
                    )
                )
                _collect_scope(payload, scope)
    return scope


def _operation_batch(conn, kind, ref):
    if kind in {"name_apply", "duplicate_apply", "catalog_publish"}:
        key = ref.get("bundle_sha256") if kind in {"name_apply", "duplicate_apply"} else ref.get("manifest_sha256")
        if not isinstance(key, str) or not re.fullmatch(r"[0-9a-f]{64}", key):
            return None
        return (
            conn.execute(select(KifuNameBatch.__table__).where(KifuNameBatch.bundle_sha256 == key))
            .mappings()
            .one_or_none()
        )
    if kind in {"name_undo", "duplicate_undo", "catalog_undo", "sync_batch"} and type(ref.get("batch_id")) is int:
        return (
            conn.execute(select(KifuNameBatch.__table__).where(KifuNameBatch.id == ref["batch_id"]))
            .mappings()
            .one_or_none()
        )
    if kind == "event_apply" and isinstance(ref.get("bundle_sha256"), str):
        return (
            conn.execute(
                select(KifuEventSelectionBatch.__table__).where(
                    KifuEventSelectionBatch.bundle_sha256 == ref["bundle_sha256"]
                )
            )
            .mappings()
            .one_or_none()
        )
    if kind in {"event_undo", "sync_event_batch"} and type(ref.get("batch_id")) is int:
        return (
            conn.execute(select(KifuEventSelectionBatch.__table__).where(KifuEventSelectionBatch.id == ref["batch_id"]))
            .mappings()
            .one_or_none()
        )
    return None


def _operation_scope(conn, kind, ref):
    if kind == "sync_ids":
        return _expand_scope(conn, ChangeScope(album_ids=set(ref["album_ids"])))
    if kind == "manual_import":
        return _manual_scope(conn, ref)
    batch = _operation_batch(conn, kind, ref)
    if batch is None:
        return ChangeScope()
    if kind.startswith("event_") or kind == "sync_event_batch":
        from katrain.web.kifu.event_selection import _audit_images_match_review

        artifact = batch["reviewed_artifact"]
        if (
            not isinstance(artifact, dict)
            or not isinstance(artifact.get("bundle"), dict)
            or canonical_sha256(artifact["bundle"]) != batch["bundle_sha256"]
            or not _audit_images_match_review(batch)
        ):
            raise SearchIndexPending(ref, "original event-selection artifact changed")
        scope = ChangeScope()
        _collect_scope(artifact, scope)
        return _expand_scope(conn, scope)
    return _batch_scope(conn, batch["id"])


def _operation_outcome(conn, kind, ref):
    """Only a durable, recognized original journal may resolve an old pending."""
    if not isinstance(ref, dict):
        return "unknown"
    if kind == "manual_import":
        # Imports commit multiple chunks; always repair finite keys, never claim
        # the original import succeeded based on an absent native receipt.
        _read_manual_record(ref)
        return "committed"
    if (
        kind == "sync_ids"
        and isinstance(ref.get("album_ids"), list)
        and all(type(value) is int and value > 0 for value in ref["album_ids"])
    ):
        return "committed"
    batch = _operation_batch(conn, kind, ref)
    if kind in {"name_apply", "duplicate_apply", "event_apply", "catalog_publish"}:
        key = ref.get("bundle_sha256") if kind != "catalog_publish" else ref.get("manifest_sha256")
        if not isinstance(key, str) or not re.fullmatch(r"[0-9a-f]{64}", key):
            return "unknown"
        if kind == "catalog_publish" and (
            not isinstance(ref.get("publication_key"), str) or not ref["publication_key"]
        ):
            return "unknown"
        if batch is None:
            return "not_committed"
        artifact = batch.get("reviewed_artifact")
        if not isinstance(artifact, dict) or batch["status"] != "applied":
            return "unknown"
        if kind == "catalog_publish":
            return (
                "committed"
                if (
                    artifact.get("manifest_sha256") == key and artifact.get("publication_key") == ref["publication_key"]
                )
                else "unknown"
            )
        document = artifact.get("plan" if kind == "duplicate_apply" else "bundle")
        return "committed" if isinstance(document, dict) and canonical_sha256(document) == key else "unknown"
    if kind in {"name_undo", "duplicate_undo", "event_undo", "catalog_undo"}:
        if batch is None:
            return "unknown"
        return (
            "not_committed"
            if batch["status"] == "applied"
            else ("committed" if batch["status"] in {"undone", "partial_undo"} else "unknown")
        )
    if kind in {"sync_batch", "sync_event_batch"}:
        return "committed" if batch is not None else "unknown"
    return "unknown"


def _validate_state(client, state, index):
    if (
        not isinstance(state, dict)
        or state.get("status") not in {"ready", "pending"}
        or state.get("doc_kind") != "sync_state"
        or state.get("schema_version") != SCHEMA_VERSION
        or type(state.get("epoch")) is not int
        or state["epoch"] < 0
        or state.get("strict_mode") is not strict_names_enabled()
        or state.get("target_index") != index
    ):
        raise SearchIndexPending((state or {}).get("operation_ref"), "search index target or state is incompatible")


def _ready(token):
    if token.client.resolve_index() != token.state["target_index"]:
        raise SearchIndexPending(token.state["operation_ref"], "search alias changed during publication")
    state = {**token.state, "status": "ready", "operation_type": None, "operation_ref": None}
    token.client.put_document(STATE_ID, state, index=state["target_index"], refresh=True)


def _apply_projection(conn, token):
    scope = token.scope.merge(_operation_scope(conn, token.state["operation_type"], token.state["operation_ref"]))
    actions = _project_actions(conn, scope)
    if actions:
        from katrain.web.kifu.search_es import iter_bulk_batches

        for batch in iter_bulk_batches(actions):
            response = token.client.bulk(batch, index=token.state["target_index"], retry_transient=True)
            if response.get("errors") or any(
                next(iter(item.values())).get("error") for item in response.get("items", [])
            ):
                raise RuntimeError("Elasticsearch bulk contains failed items")
    token.client.refresh(index=token.state["target_index"])
    _ready(token)
    if token.state["operation_type"] == "manual_import":
        _summarize_manual(token.state["operation_ref"], scope)


def begin_sync(conn, operation_type, operation_ref):
    mode = sync_mode()
    if mode == "bootstrap":
        bootstrap_client = _writer_client()
        try:
            if bootstrap_client.alias_exists():
                raise ValueError("bootstrap bypass requires no active search alias")
        finally:
            bootstrap_client.close()
    if mode != "enabled":
        return None
    client = _writer_client()
    try:
        index = client.resolve_index()
        state = client.get_document(STATE_ID, index=index).get("_source")
        _validate_state(client, state, index)
        if state["status"] == "pending":
            outcome = _operation_outcome(conn, state.get("operation_type"), state.get("operation_ref"))
            old = SyncToken(client, state, ChangeScope())
            if outcome == "committed":
                _apply_projection(conn, old)
            elif outcome == "not_committed":
                _ready(old)
            else:
                raise SearchIndexPending(state.get("operation_ref"), "unresolved earlier search publication")
        scope = _operation_scope(conn, operation_type, operation_ref)
        pending = {
            **state,
            "doc_kind": "sync_state",
            "status": "pending",
            "epoch": state["epoch"] + 1,
            "operation_type": operation_type,
            "operation_ref": operation_ref,
            "target_index": index,
        }
        client.put_document(STATE_ID, pending, index=index, refresh=True)
        return SyncToken(client, pending, scope)
    except SearchIndexPending:
        client.close()
        raise
    except Exception as exc:
        client.close()
        raise SearchIndexPending(operation_ref, "search gate could not be established") from exc


def finish_sync(conn, token):
    if token is None:
        return
    try:
        _apply_projection(conn, token)
    except Exception as exc:
        if isinstance(exc, SearchIndexPending):
            raise
        raise SearchIndexPending(token.state["operation_ref"]) from exc
    finally:
        token.client.close()


def cancel_sync(token):
    """Known database rollback, and no album bulk was attempted."""
    if token is None:
        return
    try:
        _ready(token)
        if token.state["operation_type"] == "manual_import":
            _summarize_manual(token.state["operation_ref"], token.scope)
    except Exception as exc:
        raise SearchIndexPending(
            token.state["operation_ref"], "rollback completed but search gate remains pending"
        ) from exc
    finally:
        token.client.close()


def _project_actions(conn, scope):
    from katrain.web.kifu.search_projection import build_projection_context, project_album_batch

    with Session(bind=conn) as db:
        records = db.query(KifuAlbum).filter(KifuAlbum.id.in_(scope.album_ids)).all() if scope.album_ids else []
        context = build_projection_context(
            db, strict_mode=strict_names_enabled(), records=records, owner_refs=scope.owners, terms=scope.terms
        )
        documents = project_album_batch(context, records)
        existing = {record.id for record in records}
        actions = [{"_op_type": "index", **document} for document in documents]
        actions.extend(
            {"_op_type": "delete", "_id": f"album:{album_id}"} for album_id in sorted(scope.album_ids - existing)
        )
        # Projection owns exact classification IDs, including removal of terms
        # whose last qualified owner was revoked by this transaction.
        actions.extend(context.classification_actions(scope.owners, scope.terms))
        return actions


def sync_ids(engine, album_ids, *, operation_ref=None):
    from katrain.web.kifu.name_batch import _locked_write

    if sync_mode() != "enabled":
        raise ValueError("search repair requires enabled sync mode")
    ids = sorted(set(album_ids))
    if any(type(album_id) is not int or album_id <= 0 for album_id in ids):
        raise ValueError("finite positive album IDs required")
    ref = {"album_ids": ids}
    with _locked_write(engine, search_operation=("sync_ids", ref)):
        pass
    return {"status": "synced", "album_ids": ids}


def sync_batch(engine, batch_id, *, batch_type="name"):
    from katrain.web.kifu.name_batch import _locked_write

    if sync_mode() != "enabled":
        raise ValueError("search repair requires enabled sync mode")
    if batch_type not in {"name", "event"} or type(batch_id) is not int or batch_id <= 0:
        raise ValueError("existing name/event batch ID required")
    kind = "sync_batch" if batch_type == "name" else "sync_event_batch"
    with _locked_write(engine, search_operation=(kind, {"batch_id": batch_id})) as conn:
        if _operation_batch(conn, kind, {"batch_id": batch_id}) is None:
            raise ValueError("original batch not found")
    return {"status": "synced", "batch_id": batch_id}


def recover_pending(engine):
    if sync_mode() != "enabled":
        raise ValueError("search recovery requires enabled sync mode")
    from katrain.web.kifu.name_batch import _locked_write

    with _locked_write(engine, _search_maintenance=True) as conn:
        client = _writer_client()
        try:
            index = client.resolve_index()
            state = client.get_document(STATE_ID, index=index).get("_source")
            _validate_state(client, state, index)
            if state["status"] == "pending":
                outcome = _operation_outcome(conn, state.get("operation_type"), state.get("operation_ref"))
                token = SyncToken(client, state, ChangeScope())
                if outcome == "committed":
                    _apply_projection(conn, token)
                elif outcome == "not_committed":
                    _ready(token)
                else:
                    raise SearchIndexPending(state.get("operation_ref"), "original operation cannot be resolved")
            return {"status": "ready", "epoch": state["epoch"]}
        finally:
            client.close()


def _atomic_private_json(path, record):
    import json
    from pathlib import Path
    from uuid import uuid4

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    for parent in (path.parent, *path.parents):
        if parent.is_symlink():
            raise ValueError("manual import recovery directory must not be a symlink")
    if path.is_symlink():
        raise ValueError("manual import recovery record must not be a symlink")
    temporary = path.with_name("." + path.name + "." + uuid4().hex)
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(record, handle, ensure_ascii=False, sort_keys=True)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if temporary.exists():
            temporary.unlink()


def _read_manual_record(ref):
    import json
    from pathlib import Path
    import stat

    if (
        not isinstance(ref, dict)
        or not isinstance(ref.get("record_path"), str)
        or not isinstance(ref.get("input_sha256"), str)
    ):
        raise ValueError("manual import recovery reference is missing")
    path = Path(ref["record_path"])
    if not path.is_absolute() or path.is_symlink():
        raise ValueError("manual import recovery record path is unsafe")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, "r", encoding="utf-8") as handle:
        info = os.fstat(handle.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o777 != 0o600 or info.st_size > 256 * 1024:
            raise ValueError("manual import recovery record must be private and bounded")
        record = json.load(handle)
    if (
        not isinstance(record, dict)
        or record.get("version") != 1
        or record.get("status") != "pending"
        or record.get("input_sha256") != ref["input_sha256"]
        or record.get("record_sha256") != ref.get("record_sha256")
        or canonical_sha256({key: value for key, value in record.items() if key != "record_sha256"})
        != record.get("record_sha256")
        or not isinstance(record.get("source_paths"), list)
        or not 0 < len(record["source_paths"]) <= 500
    ):
        raise ValueError("manual import original recovery record changed")
    for row in record["source_paths"]:
        if (
            not isinstance(row, dict)
            or set(row) != {"source_path", "old_album_id"}
            or not isinstance(row["source_path"], str)
            or not row["source_path"]
            or len(row["source_path"]) > 4096
            or row["old_album_id"] is not None
            and (type(row["old_album_id"]) is not int or row["old_album_id"] <= 0)
        ):
            raise ValueError("manual import original source key is invalid")
    return record


def prepare_manual_import(path, input_sha256, source_paths):
    """One CLI recovery record, written before pending or any business mutation.

    This file contains deterministic source keys and previous IDs only. It is
    replaced by a small summary after refresh, never used as a work queue.
    """
    import json
    from pathlib import Path

    path = Path(path).absolute()
    if path.exists():
        if path.is_symlink():
            raise ValueError("manual import recovery record path is unsafe")
        old = json.loads(path.read_text(encoding="utf-8"))
        if old.get("status") != "repaired":
            raise ValueError("unresolved manual import recovery record; repair it before importing")
    if not isinstance(source_paths, list) or not 0 < len(source_paths) <= 500:
        raise ValueError("manual import requires 1 to 500 finite source keys")
    record = {"version": 1, "status": "pending", "input_sha256": input_sha256, "source_paths": source_paths}
    record["record_sha256"] = canonical_sha256(record)
    _atomic_private_json(path, record)
    ref = {"record_path": str(path), "input_sha256": input_sha256, "record_sha256": record["record_sha256"]}
    _read_manual_record(ref)
    return ref


def _manual_scope(conn, ref):
    from katrain.web.core.models_db import KifuAlbumSource

    record = _read_manual_record(ref)
    keys = [row["source_path"] for row in record["source_paths"]]
    scope = ChangeScope(album_ids={row["old_album_id"] for row in record["source_paths"] if row["old_album_id"]})
    scope.album_ids.update(conn.scalars(select(KifuAlbum.id).where(KifuAlbum.source_path.in_(keys))))
    scope.album_ids.update(conn.scalars(select(KifuAlbumSource.album_id).where(KifuAlbumSource.origin_path.in_(keys))))
    return _expand_scope(conn, scope)


def _summarize_manual(ref, scope):
    record = _read_manual_record(ref)
    _atomic_private_json(
        ref["record_path"],
        {
            "version": 1,
            "status": "repaired",
            "input_sha256": record["input_sha256"],
            "record_sha256": record["record_sha256"],
            "source_count": len(record["source_paths"]),
            "affected_album_count": len(scope.album_ids),
        },
    )


def repair_manual_import(engine, path):
    """Repair finite current keys without claiming the interrupted import succeeded."""
    import json
    from pathlib import Path
    from katrain.web.kifu.name_batch import _locked_write

    path = Path(path).absolute()
    recover_pending(engine)
    record = json.loads(path.read_text(encoding="utf-8"))
    if record.get("status") == "repaired":
        return {"status": "repaired", "original_import_status": "unknown"}
    ref = {
        "record_path": str(path),
        "input_sha256": record.get("input_sha256"),
        "record_sha256": record.get("record_sha256"),
    }
    _read_manual_record(ref)
    with _locked_write(engine, search_operation=("manual_import", ref)):
        pass
    return {"status": "repaired", "original_import_status": "unknown"}
