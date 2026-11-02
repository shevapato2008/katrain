"""Owner-scoped durable replay snapshots and atomic cursor synchronization.

Each method owns a short transaction. No network access or global database is used.
The same compare-and-swap guards protect SQLite and PostgreSQL; PostgreSQL also
locks the selected row to avoid unnecessary retries under simultaneous writers.
"""

from copy import deepcopy
from datetime import datetime, timezone
import re
import uuid

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from katrain.core.baipu_identity import BAIPU_REPLAY_VERSION, baipu_record_identity, sgf_sha256
from katrain.web.core.models_db import BaipuHistory
from katrain.web.kivy_compat import ensure_kivy

ensure_kivy()
from katrain.core.baipu import build_steps_from_sgf
from katrain.core.game import KaTrainSGF


class BaipuHistoryNotFound(LookupError):
    pass


class BaipuHistoryValidationError(ValueError):
    pass


class BaipuHistoryConflict(Exception):
    def __init__(self, code, current):
        self.code = code
        self.current = current
        super().__init__(code)


IMMUTABLE = ("sgf_content", "sgf_sha256", "replay_version", "total")
SNAPSHOT_FIELDS = ("source_id", "name", *IMMUTABLE)
HEX64 = re.compile(r"^[0-9a-f]{64}$")


def _now():
    return datetime.now(timezone.utc)


def _iso(value):
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return value.replace(tzinfo=value.tzinfo or timezone.utc).astimezone(timezone.utc).isoformat()


def _date(value):
    if value is None or isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, AttributeError) as exc:
        raise BaipuHistoryValidationError("Invalid timestamp") from exc


def _integer(value, name, minimum=0):
    if type(value) is not int or value < minimum:
        raise BaipuHistoryValidationError(f"Invalid {name}")
    return value


def _record_id(value):
    if not isinstance(value, str) or not HEX64.fullmatch(value):
        raise BaipuHistoryValidationError("Invalid record identity")
    return value


def _text(value, name, bound):
    if not isinstance(value, str) or len(value) > bound or "\x00" in value:
        raise BaipuHistoryValidationError(f"Invalid {name}")
    try:
        value.encode("utf-8")
    except UnicodeError as exc:
        raise BaipuHistoryValidationError(f"{name} must be valid UTF-8") from exc
    return value


def validate_snapshot(data):
    """Derive all replay facts locally, never trust client hash/version/total."""
    sgf = _text(data.get("sgf_content"), "SGF", 1024 * 1024)
    if not sgf or len(sgf.encode("utf-8")) > 1024 * 1024:
        raise BaipuHistoryValidationError("SGF must contain at most 1 MiB of UTF-8")
    source_id, name = data.get("source_id", ""), data.get("name", "")
    _text(source_id, "source ID", 128)
    _text(name, "name", 512)
    if data.get("replay_version", BAIPU_REPLAY_VERSION) != BAIPU_REPLAY_VERSION:
        raise BaipuHistoryValidationError("Unsupported replay version")
    try:
        root = KaTrainSGF.parse_sgf(sgf)
        if tuple(root.board_size) != (19, 19):
            raise ValueError("Only 19x19 physical replay is supported")
        replay = build_steps_from_sgf(sgf)
        total = len(replay["steps"])
        if total <= 0:
            raise ValueError("Replay has no steps")
    except Exception as exc:
        raise BaipuHistoryValidationError(f"Invalid physical replay: {exc}") from exc
    digest = sgf_sha256(sgf)
    if data.get("sgf_sha256", digest) != digest or data.get("total", total) != total:
        raise BaipuHistoryValidationError("Snapshot hash or step count does not match SGF")
    return dict(
        id=baipu_record_identity(sgf),
        source_id=source_id,
        name=name,
        sgf_content=sgf,
        sgf_sha256=digest,
        replay_version=BAIPU_REPLAY_VERSION,
        total=total,
    )


class BaipuHistoryRepository:
    def __init__(self, session_factory):
        self.session_factory = session_factory

    @staticmethod
    def _snapshot(row):
        result = {column.name: deepcopy(getattr(row, column.name)) for column in BaipuHistory.__table__.columns}
        result["id"] = result.pop("record_id")
        result["completed"] = result["k"] == result["total"]
        result["updated_at"] = _iso(result["updated_at"])
        result["completed_at"] = _iso(result["completed_at"])
        result["last_writer_id"] = result["writer_id"]
        result["last_writer_seq"] = result["writer_seq"]
        return result

    @staticmethod
    def _query(user_id, record_id):
        return select(BaipuHistory).where(BaipuHistory.user_id == user_id, BaipuHistory.record_id == record_id)

    def _mutate(self, user_id, record_id, change):
        _record_id(record_id)
        for _ in range(8):
            with self.session_factory.begin() as db:
                row = db.execute(self._query(user_id, record_id).with_for_update()).scalar_one_or_none()
                if row is None:
                    raise BaipuHistoryNotFound(record_id)
                values = change(self._snapshot(row))
                if not values:
                    return self._snapshot(row)
                conditions = [BaipuHistory.user_id == user_id, BaipuHistory.record_id == record_id]
                for field in ("local_revision", "cloud_revision", "writer_id", "writer_seq", "sync_state"):
                    conditions.append(getattr(BaipuHistory, field) == getattr(row, field))
                affected = db.execute(
                    update(BaipuHistory).where(*conditions).values(**values),
                    execution_options={"synchronize_session": False},
                ).rowcount
                if affected == 1:
                    db.expire(row)
                    return self._snapshot(row)
        raise BaipuHistoryConflict("stale_local_revision", self.get(user_id, record_id))

    @staticmethod
    def _new(user_id, snapshot, *, board=False):
        values = {key: snapshot[key] for key in SNAPSHOT_FIELDS}
        return BaipuHistory(
            user_id=user_id,
            record_id=snapshot["id"],
            **values,
            k=0,
            local_revision=0,
            cloud_revision=0,
            writer_id=uuid.uuid4().hex,
            writer_seq=0,
            pending_base_revision=0 if board else None,
            sync_state="pending" if board else "synced",
            updated_at=_now(),
        )

    def open(self, user_id, data, board=False):
        snapshot = validate_snapshot(data)
        try:
            with self.session_factory.begin() as db:
                row = db.execute(self._query(user_id, snapshot["id"])).scalar_one_or_none()
                if row is None:
                    row = self._new(user_id, snapshot, board=board)
                    db.add(row)
                    db.flush()
                return self._snapshot(row)
        except IntegrityError:
            return self.get(user_id, snapshot["id"])

    def get(self, user_id, record_id):
        _record_id(record_id)
        with self.session_factory() as db:
            row = db.execute(self._query(user_id, record_id)).scalar_one_or_none()
            if row is None:
                raise BaipuHistoryNotFound(record_id)
            return self._snapshot(row)

    def list(self, user_id, limit=30):
        _integer(limit, "limit", 1)
        if limit > 100:
            raise BaipuHistoryValidationError("Limit exceeds 100")
        with self.session_factory() as db:
            rows = db.execute(
                select(BaipuHistory)
                .where(BaipuHistory.user_id == user_id)
                .order_by(BaipuHistory.updated_at.desc(), BaipuHistory.record_id)
                .limit(limit)
            ).scalars()
            return [self._snapshot(row) for row in rows]

    def save(self, user_id, record_id, data, board=False):
        k = _integer(data.get("k"), "cursor")
        expected = _integer(data.get("expected_local_revision"), "local revision")
        mutation = data.get("mutation_id")
        if not isinstance(mutation, str) or not 1 <= len(mutation) <= 128:
            raise BaipuHistoryValidationError("Invalid mutation ID")
        mutation_payload = dict(k=k, expected_local_revision=expected)

        def change(row):
            if k > row["total"]:
                raise BaipuHistoryValidationError("Cursor exceeds total")
            if row["last_mutation_id"] == mutation:
                if row["last_mutation_payload"] == mutation_payload:
                    return None
                raise BaipuHistoryConflict("stale_local_revision", row)
            if expected != row["local_revision"]:
                raise BaipuHistoryConflict("stale_local_revision", row)
            now = _now()
            values = dict(
                k=k,
                completed_at=(row["completed_at"] or now) if k == row["total"] else None,
                updated_at=now,
                local_revision=row["local_revision"] + 1,
                last_mutation_id=mutation,
                last_mutation_payload=mutation_payload,
            )
            values["completed_at"] = _date(values["completed_at"])
            if board:
                values["writer_seq"] = row["writer_seq"] + 1
                if row["sync_state"] == "synced":
                    values.update(sync_state="pending", pending_base_revision=row["cloud_revision"])
            else:
                values.update(
                    writer_id=uuid.uuid4().hex,
                    writer_seq=0,
                    cloud_revision=row["cloud_revision"] + 1,
                    sync_state="synced",
                    pending_base_revision=None,
                    conflict_remote=None,
                )
            return values

        return self._mutate(user_id, record_id, change)

    @staticmethod
    def _immutable(row, incoming):
        if any(key in incoming and row[key] != incoming[key] for key in IMMUTABLE):
            raise BaipuHistoryConflict("immutable_snapshot_mismatch", row)

    def accept_sync(self, user_id, record_id, data):
        _record_id(record_id)
        snapshot = validate_snapshot(data)
        if snapshot["id"] != record_id:
            try:
                current = self.get(user_id, record_id)
            except BaipuHistoryNotFound:
                raise BaipuHistoryValidationError("Snapshot identity does not match path")
            raise BaipuHistoryConflict("immutable_snapshot_mismatch", current)
        k = _integer(data.get("k"), "cursor")
        sequence = _integer(data.get("writer_seq"), "writer sequence")
        expected = _integer(data.get("expected_revision"), "cloud revision")
        writer = data.get("writer_id")
        if not isinstance(writer, str) or not 1 <= len(writer) <= 128 or k > snapshot["total"]:
            raise BaipuHistoryValidationError("Invalid writer or cursor")

        def change(row):
            self._immutable(row, snapshot)
            if row["writer_id"] == writer:
                if sequence < row["writer_seq"]:
                    return None
                if sequence == row["writer_seq"]:
                    if k == row["k"] and expected == row["last_sync_expected_revision"]:
                        return None
                    raise BaipuHistoryConflict("cloud_progress_conflict", row)
            elif expected != row["cloud_revision"]:
                raise BaipuHistoryConflict("cloud_progress_conflict", row)
            now = _now()
            return dict(
                k=k,
                completed_at=(_date(row["completed_at"]) or now) if k == row["total"] else None,
                updated_at=now,
                local_revision=row["local_revision"] + 1,
                cloud_revision=row["cloud_revision"] + 1,
                writer_id=writer,
                writer_seq=sequence,
                sync_state="synced",
                pending_base_revision=None,
                conflict_remote=None,
                last_mutation_id=None,
                last_mutation_payload=None,
                last_sync_expected_revision=expected,
            )

        # The first cloud acceptance is revision 1 even for sequence zero/open.
        try:
            with self.session_factory.begin() as db:
                existing = db.execute(self._query(user_id, record_id)).scalar_one_or_none()
                if existing is None:
                    if expected != 0:
                        raise BaipuHistoryConflict("cloud_progress_conflict", None)
                    row = self._new(user_id, snapshot)
                    now = _now()
                    row.k, row.writer_id, row.writer_seq = k, writer, sequence
                    row.local_revision = row.cloud_revision = 1
                    row.last_sync_expected_revision = expected
                    row.completed_at = now if k == row.total else None
                    db.add(row)
                    db.flush()
                    return self._snapshot(row)
        except IntegrityError:
            pass  # Concurrent insertion: compare against its committed winner.
        return self._mutate(user_id, record_id, change)

    def pending_snapshots(self, user_id=None):
        with self.session_factory() as db:
            query = select(BaipuHistory).where(BaipuHistory.sync_state == "pending")
            if user_id is not None:
                query = query.where(BaipuHistory.user_id == user_id)
            rows = db.execute(query.order_by(BaipuHistory.updated_at).limit(100)).scalars()
            result = []
            for row in rows:
                current = self._snapshot(row)
                current["payload"] = {
                    key: deepcopy(current[key]) for key in (*SNAPSHOT_FIELDS, "k", "writer_id", "writer_seq")
                }
                current["payload"]["expected_revision"] = current["pending_base_revision"]
                result.append(current)
            return result

    @staticmethod
    def _same_writer(row, sent):
        return row["writer_id"] == sent.get("writer_id")

    def absorb_success(self, user_id, record_id, sent, remote):
        revision = _integer(remote.get("cloud_revision"), "cloud revision")
        for key, bound in (("source_id", 128), ("name", 512)):
            if key in remote:
                _text(remote[key], key, bound)

        def change(row):
            if not self._same_writer(row, sent):
                return None
            values = dict(cloud_revision=max(row["cloud_revision"], revision))
            if (
                row["sync_state"] == "pending"
                and row["writer_seq"] == sent.get("writer_seq")
                and remote.get("last_writer_id", remote.get("writer_id")) == row["writer_id"]
                and remote.get("last_writer_seq", remote.get("writer_seq")) == row["writer_seq"]
                and remote.get("k") == row["k"]
            ):
                values.update(sync_state="synced", pending_base_revision=None, conflict_remote=None)
                values.update({key: remote[key] for key in ("source_id", "name") if key in remote})
            return values

        return self._mutate(user_id, record_id, change)

    def absorb_conflict(self, user_id, record_id, sent, remote):
        def change(row):
            if not self._same_writer(row, sent) or row["sync_state"] not in ("pending", "conflict"):
                return None
            self._immutable(row, remote)
            return dict(sync_state="conflict", conflict_remote=deepcopy(remote))

        return self._mutate(user_id, record_id, change)

    def mark_refused(self, user_id, record_id, sent, reason):
        def change(row):
            if not self._same_writer(row, sent) or row["sync_state"] != "pending":
                return None
            return dict(sync_state="refused")

        return self._mutate(user_id, record_id, change)

    @staticmethod
    def _remote_summary(remote):
        _record_id(remote.get("id"))
        for key, bound in (("source_id", 128), ("name", 512)):
            if key in remote:
                _text(remote[key], key, bound)
        if remote.get("replay_version") != BAIPU_REPLAY_VERSION or not HEX64.fullmatch(remote.get("sgf_sha256", "")):
            raise BaipuHistoryValidationError("Invalid cloud identity")
        total = _integer(remote.get("total"), "total", 1)
        if _integer(remote.get("k"), "cursor") > total:
            raise BaipuHistoryValidationError("Cursor exceeds total")
        _integer(remote.get("cloud_revision"), "cloud revision")
        _date(remote.get("updated_at"))
        _date(remote.get("completed_at"))

    def adopt_clean(self, user_id, remote_records):
        if len(remote_records) > 100:
            raise BaipuHistoryValidationError("Too many records")
        winners = []
        for remote in remote_records:
            self._remote_summary(remote)
            record_id = remote["id"]

            def change(row):
                self._immutable(row, remote)
                if row["sync_state"] != "synced" or remote["cloud_revision"] <= row["cloud_revision"]:
                    return None
                return dict(
                    k=remote["k"],
                    completed_at=_date(remote.get("completed_at")) if remote["k"] == row["total"] else None,
                    updated_at=_date(remote["updated_at"]),
                    cloud_revision=remote["cloud_revision"],
                    local_revision=row["local_revision"] + 1,
                    **{key: remote[key] for key in ("source_id", "name") if key in remote},
                )

            try:
                winner = self._mutate(user_id, record_id, change)
            except BaipuHistoryNotFound:
                if "sgf_content" not in remote:
                    winners.append(deepcopy(remote))
                    continue
                snapshot = validate_snapshot(remote)
                if snapshot["id"] != record_id:
                    raise BaipuHistoryValidationError("Cloud identity does not match SGF")
                try:
                    with self.session_factory.begin() as db:
                        row = self._new(user_id, snapshot)
                        row.k = remote["k"]
                        row.cloud_revision = remote["cloud_revision"]
                        row.completed_at = _date(remote.get("completed_at")) if row.k == row.total else None
                        row.updated_at = _date(remote["updated_at"])
                        db.add(row)
                        db.flush()
                        winner = self._snapshot(row)
                except IntegrityError:
                    winner = self._mutate(user_id, record_id, change)
            winners.append(winner)
        return winners

    def resolve(self, user_id, record_id, strategy, remote, expected_local_revision):
        if strategy not in ("use_cloud", "keep_local"):
            raise BaipuHistoryValidationError("Invalid resolution strategy")
        _integer(expected_local_revision, "local revision")
        self._remote_summary(remote)

        def change(row):
            if (
                row["local_revision"] != expected_local_revision
                or row["sync_state"] not in ("conflict", "refused")
                or remote.get("_expected_writer_id") != row["writer_id"]
            ):
                raise BaipuHistoryConflict("stale_local_revision", row)
            self._immutable(row, remote)
            now = _now()
            values = dict(
                writer_id=uuid.uuid4().hex,
                writer_seq=0,
                local_revision=row["local_revision"] + 1,
                cloud_revision=max(row["cloud_revision"], remote["cloud_revision"]),
                updated_at=now,
                last_mutation_id=None,
                last_mutation_payload=None,
            )
            if strategy == "use_cloud":
                values.update(
                    k=remote["k"],
                    completed_at=_date(remote.get("completed_at")) if remote["k"] == row["total"] else None,
                    sync_state="synced",
                    pending_base_revision=None,
                    conflict_remote=None,
                    **{key: remote[key] for key in ("source_id", "name") if key in remote},
                )
            else:
                values.update(sync_state="pending", pending_base_revision=remote["cloud_revision"])
            return values

        return self._mutate(user_id, record_id, change)
