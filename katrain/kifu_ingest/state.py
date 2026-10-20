"""Small durable orchestration journal for numeric 19x19 source items.

This is independent of the native album transaction. On recovery, reconcile
publication against the native catalog receipt before advancing this journal.
Only the numbered SQL migration creates production tables.
"""

from __future__ import annotations

from datetime import datetime, timezone
import re
from uuid import uuid4

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Table,
    UniqueConstraint,
    func,
    inspect,
    select,
    update,
)
from sqlalchemy.exc import IntegrityError


metadata = MetaData()
PHASES = (
    "discovered",
    "downloaded",
    "parsed",
    "names_ready",
    "test_published",
    "test_verified",
    "prod_published",
    "prod_synced",
)
EXCEPTIONS = {"retry_wait", "quarantined"}
RECEIPT_COLUMNS = {
    "test_published": "test_receipt",
    "test_verified": "test_verification",
    "prod_published": "prod_receipt",
    "prod_synced": "prod_verification",
}
SHA = re.compile(r"[0-9a-f]{64}\Z")
NUMERIC_ID = re.compile(r"[0-9]+\Z")

batches = Table(
    "kifu_ingest_batches",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("batch_uuid", String(36), nullable=False, unique=True),
    Column("publication_key", String(160), nullable=False, unique=True),
    Column("manifest_sha256", String(64), nullable=False),
    Column("status", String(24), nullable=False),
    Column("resume_phase", String(24)),
    Column("test_receipt", JSON),
    Column("test_verification", JSON),
    Column("prod_receipt", JSON),
    Column("prod_verification", JSON),
    Column("stats", JSON),
    Column("attempts", Integer, nullable=False),
    Column("error", String(512)),
    Column("next_retry_at", DateTime(timezone=True)),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    CheckConstraint("attempts >= 0", name="ck_kifu_ingest_batches_attempts"),
)

items = Table(
    "kifu_ingest_items",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("source_key", String(16), nullable=False),
    Column("external_id", String(64), nullable=False),
    Column("raw_sha256", String(64)),
    Column("sgf_sha256", String(64)),
    Column("staging_path", String(512)),
    Column("source_metadata", JSON),
    Column("status", String(24), nullable=False),
    Column("resume_phase", String(24)),
    Column("attempts", Integer, nullable=False),
    Column("error", String(512)),
    Column("next_retry_at", DateTime(timezone=True)),
    Column("publication_key", String(160), ForeignKey("kifu_ingest_batches.publication_key")),
    Column("test_album_id", Integer),
    Column("prod_album_id", Integer),
    Column("test_receipt", JSON),
    Column("test_verification", JSON),
    Column("prod_receipt", JSON),
    Column("prod_verification", JSON),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    CheckConstraint("source_key = '19x19'", name="ck_kifu_ingest_items_source"),
    CheckConstraint("attempts >= 0", name="ck_kifu_ingest_items_attempts"),
    UniqueConstraint("source_key", "external_id", name="uq_kifu_ingest_items_source"),
)


class Conflict(ValueError):
    """The persisted identity, phase or receipt conflicts with this attempt."""


def _now():
    return datetime.now(timezone.utc)


def _hash(value, name):
    if value is not None and (not isinstance(value, str) or not SHA.fullmatch(value)):
        raise ValueError(f"{name} must be a lowercase SHA-256")


def _identity(source_key, external_id):
    if source_key != "19x19" or not isinstance(external_id, str) or not NUMERIC_ID.fullmatch(external_id):
        raise ValueError("only numeric 19x19 external IDs are supported")


def _row(conn, table, *conditions):
    found = conn.execute(select(table).where(*conditions)).mappings().one_or_none()
    return dict(found) if found is not None else None


def _transition(current, target, resume_phase):
    if current in PHASES:
        if target in EXCEPTIONS:
            if current == "prod_synced":
                raise Conflict("illegal transition after sync")
            return current
        if target not in PHASES:
            raise ValueError("unknown status")
        if PHASES.index(target) == PHASES.index(current) + 1:
            return None
    elif current in EXCEPTIONS:
        if target == "quarantined" and current == "retry_wait":
            return resume_phase
        if target == resume_phase:
            return None
    raise Conflict("illegal transition")


class StateStore:
    """Operate on a caller-owned SQLAlchemy Engine; never creates schema or Engine."""

    def __init__(self, engine):
        self.engine = engine

    def remember_item(
        self, source_key, external_id, *, raw_sha256=None, sgf_sha256=None, staging_path=None, source_metadata=None
    ):
        _identity(source_key, external_id)
        _hash(raw_sha256, "raw_sha256")
        _hash(sgf_sha256, "sgf_sha256")
        if source_metadata is not None and not isinstance(source_metadata, dict):
            raise ValueError("source_metadata must be an object")
        conditions = (items.c.source_key == source_key, items.c.external_id == external_id)
        with self.engine.begin() as conn:
            existing = _row(conn, items, *conditions)
            if existing is None:
                now = _now()
                try:
                    with conn.begin_nested():
                        conn.execute(
                            items.insert().values(
                                source_key=source_key,
                                external_id=external_id,
                                raw_sha256=raw_sha256,
                                sgf_sha256=sgf_sha256,
                                staging_path=staging_path,
                                source_metadata=source_metadata,
                                status="discovered",
                                attempts=0,
                                created_at=now,
                                updated_at=now,
                            )
                        )
                except IntegrityError:
                    # A concurrent discovery won the unique source identity.
                    existing = _row(conn, items, *conditions)
                    if existing is None:
                        raise
                else:
                    existing = _row(conn, items, *conditions)
            for field, given in (("raw_sha256", raw_sha256), ("sgf_sha256", sgf_sha256)):
                if given is not None and existing[field] is not None and given != existing[field]:
                    raise Conflict("source ID content changed; explicit revision required")
            return existing

    def register_batch(self, publication_key, manifest_sha256):
        if not isinstance(publication_key, str) or not publication_key.strip() or len(publication_key) > 160:
            raise ValueError("publication_key is required")
        _hash(manifest_sha256, "manifest_sha256")
        if manifest_sha256 is None:
            raise ValueError("manifest_sha256 is required")
        condition = batches.c.publication_key == publication_key
        with self.engine.begin() as conn:
            existing = _row(conn, batches, condition)
            if existing is None:
                now = _now()
                try:
                    with conn.begin_nested():
                        conn.execute(
                            batches.insert().values(
                                batch_uuid=str(uuid4()),
                                publication_key=publication_key,
                                manifest_sha256=manifest_sha256,
                                status="discovered",
                                attempts=0,
                                created_at=now,
                                updated_at=now,
                            )
                        )
                except IntegrityError:
                    existing = _row(conn, batches, condition)
                    if existing is None:
                        raise
                else:
                    existing = _row(conn, batches, condition)
            if existing["manifest_sha256"] != manifest_sha256:
                raise Conflict("publication key names a different manifest")
            return existing

    def advance_item(
        self,
        source_key,
        external_id,
        status,
        *,
        expected_status,
        receipt=None,
        raw_sha256=None,
        sgf_sha256=None,
        staging_path=None,
        source_metadata=None,
        publication_key=None,
        test_album_id=None,
        prod_album_id=None,
        error=None,
        next_retry_at=None,
    ):
        _identity(source_key, external_id)
        _hash(raw_sha256, "raw_sha256")
        _hash(sgf_sha256, "sgf_sha256")
        if source_metadata is not None and not isinstance(source_metadata, dict):
            raise ValueError("source_metadata must be an object")
        changes = {
            key: value
            for key, value in (
                ("raw_sha256", raw_sha256),
                ("sgf_sha256", sgf_sha256),
                ("staging_path", staging_path),
                ("source_metadata", source_metadata),
                ("publication_key", publication_key),
                ("test_album_id", test_album_id),
                ("prod_album_id", prod_album_id),
            )
            if value is not None
        }
        return self._advance(
            items,
            (items.c.source_key == source_key, items.c.external_id == external_id),
            status,
            expected_status,
            receipt,
            changes,
            error,
            next_retry_at,
        )

    def advance_batch(
        self, publication_key, status, *, expected_status, receipt=None, stats=None, error=None, next_retry_at=None
    ):
        if stats is not None and not isinstance(stats, dict):
            raise ValueError("stats must be an object")
        changes = {"stats": stats} if stats is not None else {}
        return self._advance(
            batches,
            (batches.c.publication_key == publication_key,),
            status,
            expected_status,
            receipt,
            changes,
            error,
            next_retry_at,
        )

    def _advance(self, table, conditions, status, expected_status, receipt, changes, error, next_retry_at):
        if status not in PHASES and status not in EXCEPTIONS:
            raise ValueError("unknown status")
        if status in RECEIPT_COLUMNS and not isinstance(receipt, dict):
            raise ValueError("publication/verification receipt is required")
        if receipt is not None and status not in RECEIPT_COLUMNS:
            raise ValueError("receipt does not belong to this phase")
        if status in EXCEPTIONS and not error and status == "retry_wait":
            raise ValueError("retry_wait requires an error")
        with self.engine.begin() as conn:
            old = _row(conn, table, *conditions)
            if old is None:
                raise Conflict("state row not found")
            for field in ("raw_sha256", "sgf_sha256"):
                if field in changes and old[field] is not None and changes[field] != old[field]:
                    raise Conflict("source ID content changed; explicit revision required")
            receipt_column = RECEIPT_COLUMNS.get(status)
            if old["status"] == status:
                if (
                    receipt_column
                    and old[receipt_column] == receipt
                    and all(old[key] == value for key, value in changes.items())
                ):
                    return old
                raise Conflict("status changed or stored receipt differs")
            if old["status"] != expected_status:
                raise Conflict("status changed")
            resume_phase = _transition(old["status"], status, old["resume_phase"])
            if old["status"] in ("test_published", "test_verified", "prod_published"):
                # Source bytes and publication membership are pinned after TEST publication.
                pinned = {"raw_sha256", "sgf_sha256", "staging_path", "source_metadata", "publication_key"}
                if any(key in pinned and old[key] != value for key, value in changes.items()):
                    raise Conflict("published state is immutable")
            for field, phase in (("test_album_id", "test_published"), ("prod_album_id", "prod_published")):
                if field in changes:
                    if old[field] is not None and old[field] != changes[field]:
                        raise Conflict("target mapping is immutable")
                    if old[field] is None and status != phase:
                        raise Conflict("target mapping requires matching publication")
            if status in RECEIPT_COLUMNS and old[receipt_column] is not None and old[receipt_column] != receipt:
                raise Conflict("stored receipt differs")
            values = dict(changes, status=status, resume_phase=resume_phase, updated_at=_now())
            if receipt_column:
                values[receipt_column] = receipt
            if status in EXCEPTIONS:
                values.update(error=error, next_retry_at=next_retry_at, attempts=old["attempts"] + 1)
            else:
                values.update(error=None, next_retry_at=None)
            result = conn.execute(update(table).where(*conditions, table.c.status == expected_status).values(**values))
            if result.rowcount != 1:
                raise Conflict("status changed")
            return _row(conn, table, *conditions)

    def snapshot_status(self):
        """Counts only; on an un-migrated database, this read remains read-only."""
        present = set(inspect(self.engine).get_table_names())
        result = {"batches": {}, "items": {}}
        with self.engine.connect() as conn:
            for label, table in (("batches", batches), ("items", items)):
                if table.name in present:
                    result[label] = dict(
                        conn.execute(select(table.c.status, func.count()).group_by(table.c.status)).all()
                    )
        return result
