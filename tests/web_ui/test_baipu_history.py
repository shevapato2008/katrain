"""Durable baipu cursor protocol; every database here is disposable."""

import importlib.util
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from katrain.web.core import models_db

SGF = "(;GM[1]FF[4]SZ[19];B[aa];W[bb];B[cc])"


def test_history_repository_exists():
    assert importlib.util.find_spec("katrain.web.core.baipu_history") is not None


@pytest.fixture
def history(tmp_path):
    from katrain.web.core.baipu_history import BaipuHistoryRepository

    engine = create_engine(f"sqlite:///{tmp_path / 'history.db'}", connect_args={"check_same_thread": False})
    models_db.Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    with factory.begin() as db:
        db.add_all([models_db.User(id=i, username=f"u{i}", hashed_password="x") for i in (1, 2)])
    yield BaipuHistoryRepository(factory), factory
    engine.dispose()


def opened(repo, board=False, user=1):
    return repo.open(user, dict(sgf_content=SGF, source_id="kifu_1", name="Example"), board=board)


def saved(repo, row, k, board=False, mutation="m1"):
    return repo.save(
        row["user_id"],
        row["id"],
        dict(k=k, expected_local_revision=row["local_revision"], mutation_id=mutation),
        board=board,
    )


def payload(row, **changes):
    keys = ("source_id", "name", "sgf_content", "sgf_sha256", "replay_version", "total", "k", "writer_id", "writer_seq")
    result = {key: row[key] for key in keys}
    result["expected_revision"] = row["pending_base_revision"] or 0
    result.update(changes)
    return result


def test_open_owner_identity_and_restart_persistence(history):
    from katrain.web.core.baipu_history import BaipuHistoryRepository, BaipuHistoryNotFound

    repo, factory = history
    row = opened(repo)
    assert row["k"] == 0 and row["total"] == 3 and row["replay_version"] == 2
    assert len(row["id"]) == 64 and row["sgf_content"] == SGF
    progress = saved(repo, row, 2)
    assert opened(BaipuHistoryRepository(factory))["k"] == 2
    assert opened(repo, user=2)["id"] == row["id"]
    with pytest.raises(BaipuHistoryNotFound):
        repo.get(2, "a" * 64)
    assert repo.list(1, 30)[0]["local_revision"] == progress["local_revision"]


def test_save_cas_idempotency_completion_and_decreasing_cursor(history):
    from katrain.web.core.baipu_history import BaipuHistoryConflict

    repo, _ = history
    row = opened(repo)
    done = saved(repo, row, 3)
    assert done["completed"] and done["completed_at"]
    assert done["cloud_revision"] == row["cloud_revision"] + 1
    assert saved(repo, row, 3) == done
    with pytest.raises(BaipuHistoryConflict) as stale:
        saved(repo, row, 1, mutation="stale")
    assert stale.value.code == "stale_local_revision"
    with pytest.raises(BaipuHistoryConflict):
        saved(repo, done, 2, mutation="m1")
    restarted = saved(repo, done, 0, mutation="restart")
    assert restarted["k"] == 0 and not restarted["completed"] and restarted["completed_at"] is None
    assert restarted["writer_id"] != done["writer_id"]


@pytest.mark.parametrize(
    "data",
    [
        dict(sgf_content="(;SZ[9];B[aa])"),
        dict(sgf_content="(;SZ[19:9];B[aa])"),
        dict(sgf_content="(;SZ[19])"),
        dict(sgf_content="bad"),
        dict(sgf_content=SGF, name="n" * 513),
        dict(sgf_content=SGF, source_id="s" * 129),
        dict(sgf_content="x" * (1024 * 1024 + 1)),
    ],
)
def test_invalid_snapshot_rejected(history, data):
    from katrain.web.core.baipu_history import BaipuHistoryValidationError

    repo, _ = history
    with pytest.raises(BaipuHistoryValidationError):
        repo.open(1, data)
    assert repo.list(1, 30) == []


def test_cloud_writer_protocol_and_immutable_snapshot(history):
    from katrain.web.core.baipu_history import BaipuHistoryConflict, BaipuHistoryValidationError

    repo, _ = history
    row = opened(repo, board=True)
    request = payload(row, k=2, writer_seq=2)
    accepted = repo.accept_sync(2, row["id"], request)
    assert accepted["k"] == 2 and accepted["cloud_revision"] == 1
    assert repo.accept_sync(2, row["id"], request) == accepted
    assert repo.accept_sync(2, row["id"], payload(row, k=0, writer_seq=1))["k"] == 2
    with pytest.raises(BaipuHistoryConflict):
        repo.accept_sync(2, row["id"], dict(request, k=1))
    with pytest.raises(BaipuHistoryConflict) as other:
        repo.accept_sync(2, row["id"], dict(request, writer_id="another", expected_revision=0))
    assert other.value.code == "cloud_progress_conflict"
    undo = repo.accept_sync(2, row["id"], dict(request, k=0, writer_seq=3))
    assert undo["k"] == 0 and undo["cloud_revision"] == 2
    with pytest.raises(BaipuHistoryConflict) as immutable:
        repo.accept_sync(
            2,
            row["id"],
            dict(
                request,
                sgf_content=SGF.replace("aa", "ab"),
                sgf_sha256=__import__("hashlib").sha256(SGF.replace("aa", "ab").encode()).hexdigest(),
                writer_seq=4,
            ),
        )
    assert immutable.value.code == "immutable_snapshot_mismatch"
    for bad in [dict(request, k=4), dict(request, replay_version=1), dict(request, sgf_sha256="a" * 64)]:
        with pytest.raises(BaipuHistoryValidationError):
            repo.accept_sync(2, row["id"], bad)


def test_receipts_preserve_newer_cursor_pending_base_and_conflict(history):
    repo, _ = history
    row = opened(repo, board=True)
    first = saved(repo, row, 1, board=True)
    second = saved(repo, first, 2, board=True, mutation="m2")
    receipt = dict(first, cloud_revision=4)
    repo.absorb_success(1, row["id"], first, receipt)
    current = repo.get(1, row["id"])
    assert (current["k"], current["sync_state"], current["cloud_revision"], current["pending_base_revision"]) == (
        2,
        "pending",
        4,
        0,
    )
    remote = dict(row, k=3, cloud_revision=5)
    repo.absorb_conflict(1, row["id"], second, remote)
    repo.absorb_success(1, row["id"], first, receipt)
    current = repo.get(1, row["id"])
    assert current["sync_state"] == "conflict" and current["conflict_remote"]["k"] == 3
    third = saved(repo, current, 0, board=True, mutation="m3")
    assert third["sync_state"] == "conflict" and not repo.pending_snapshots()


def test_adopt_clean_returns_actual_winner_and_never_rebases_dirty(history):
    repo, _ = history
    row = opened(repo, board=True)
    remote = dict(row, cloud_revision=2, k=1)
    winner = repo.adopt_clean(1, [remote])[0]
    assert winner["k"] == 0 and winner["sync_state"] == "pending"
    repo.absorb_success(1, row["id"], row, dict(row, cloud_revision=3))
    clean = repo.get(1, row["id"])
    assert clean["sync_state"] == "synced"
    assert repo.adopt_clean(1, [remote])[0]["cloud_revision"] == 3
    fresh = repo.adopt_clean(1, [dict(remote, cloud_revision=4)])[0]
    assert fresh["k"] == 1 and fresh["writer_id"] == row["writer_id"]
    changed = saved(repo, fresh, 2, board=True)
    assert repo.adopt_clean(1, [dict(remote, cloud_revision=5)])[0]["k"] == 2
    assert repo.get(1, row["id"])["pending_base_revision"] == changed["pending_base_revision"] == 4


def test_resolution_rotates_writer_cas_and_late_receipt(history):
    from katrain.web.core.baipu_history import BaipuHistoryConflict

    repo, _ = history
    row = saved(repo, opened(repo, board=True), 2, board=True)
    remote = dict(row, k=1, cloud_revision=8)
    repo.absorb_conflict(1, row["id"], row, remote)
    conflict = repo.get(1, row["id"])
    guarded = dict(remote, _expected_writer_id=conflict["writer_id"])
    updated = saved(repo, conflict, 3, board=True, mutation="racing")
    with pytest.raises(BaipuHistoryConflict):
        repo.resolve(1, row["id"], "use_cloud", guarded, conflict["local_revision"])
    resolved = repo.resolve(1, row["id"], "keep_local", guarded, updated["local_revision"])
    assert resolved["k"] == 3 and resolved["writer_id"] != row["writer_id"]
    assert resolved["writer_seq"] == 0 and resolved["pending_base_revision"] == 8
    assert resolved["local_revision"] == updated["local_revision"] + 1
    repo.absorb_success(1, row["id"], row, dict(remote, cloud_revision=9))
    assert repo.get(1, row["id"]) == resolved


def test_pending_snapshots_are_copied_and_refusal_stops_sends(history):
    repo, _ = history
    row = opened(repo, board=True)
    pending = repo.pending_snapshots()[0]
    assert pending["user_id"] == 1 and pending["payload"]["expected_revision"] == 0
    pending["payload"]["k"] = 3
    assert repo.get(1, row["id"])["k"] == 0
    repo.mark_refused(1, row["id"], row, "invalid request")
    assert repo.get(1, row["id"])["sync_state"] == "refused"
    assert repo.pending_snapshots() == []


def test_reused_writer_sequence_requires_identical_request(history):
    from katrain.web.core.baipu_history import BaipuHistoryConflict

    repo, _ = history
    local = opened(repo, board=True)
    request = payload(local, k=1, writer_seq=1)
    repo.accept_sync(2, local["id"], request)
    with pytest.raises(BaipuHistoryConflict):
        repo.accept_sync(2, local["id"], dict(request, expected_revision=999))


def test_superseded_receipt_does_not_settle_different_cursor(history):
    repo, _ = history
    local = saved(repo, opened(repo, board=True), 1, board=True)
    repo.absorb_success(
        1, local["id"], local, dict(local, k=2, last_writer_seq=local["writer_seq"] + 1, cloud_revision=4)
    )
    current = repo.get(1, local["id"])
    assert current["k"] == 1 and current["sync_state"] == "pending"


def test_competing_local_saves_only_one_cas_wins(history):
    from katrain.web.core.baipu_history import BaipuHistoryConflict
    from threading import Barrier

    repo, _ = history
    row = opened(repo, board=True)
    gate = Barrier(2)

    def write(k):
        gate.wait()
        try:
            return saved(repo, row, k, board=True, mutation=f"concurrent-{k}")
        except BaipuHistoryConflict as exc:
            return exc

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(write, (1, 2)))
    assert sum(isinstance(item, dict) for item in results) == 1
    assert repo.get(1, row["id"])["local_revision"] == 1


def test_postgres_competing_cloud_writers_are_atomic():
    """Opt-in only; the permitted target is the disposable local test container."""
    import os
    from threading import Barrier
    from sqlalchemy.engine import make_url
    from katrain.web.core.baipu_history import BaipuHistoryRepository, BaipuHistoryConflict

    url = os.environ.get("BAIPU_TEST_POSTGRES_URL")
    if not url:
        pytest.skip("Set BAIPU_TEST_POSTGRES_URL to the disposable local test database")
    target = make_url(url)
    assert target.host == "127.0.0.1" and target.port == 15439 and target.database == "baipu_history_test"
    engine = create_engine(url)
    models_db.User.__table__.create(engine, checkfirst=True)
    models_db.BaipuHistory.__table__.create(engine, checkfirst=True)
    factory = sessionmaker(bind=engine)
    with factory.begin() as db:
        user = models_db.User(username=f'baipu-cas-{__import__("uuid").uuid4().hex}', hashed_password="x")
        db.add(user)
        db.flush()
        user_id = user.id
    repo = BaipuHistoryRepository(factory)
    try:
        row = opened(repo, user=user_id)
        gate = Barrier(2)

        def write(writer):
            gate.wait()
            try:
                return repo.accept_sync(user_id, row["id"], payload(row, writer_id=writer, writer_seq=1, k=1))
            except BaipuHistoryConflict as exc:
                return exc

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(write, ("writer-a", "writer-b")))
        assert sum(isinstance(item, dict) for item in results) == 1
        assert sum(isinstance(item, BaipuHistoryConflict) for item in results) == 1
        current = repo.get(user_id, row["id"])
        assert current["cloud_revision"] == current["local_revision"] == 1
    finally:
        with factory.begin() as db:
            db.query(models_db.BaipuHistory).filter_by(user_id=user_id).delete()
            db.query(models_db.User).filter_by(id=user_id).delete()
        engine.dispose()


@pytest.mark.parametrize("field", ["record_id", "sgf_sha256"])
def test_database_rejects_non_hex_identity(history, field):
    from sqlalchemy import update
    from sqlalchemy.exc import IntegrityError

    repo, factory = history
    row = opened(repo)
    with pytest.raises(IntegrityError):
        with factory.begin() as db:
            db.execute(
                update(models_db.BaipuHistory).where(models_db.BaipuHistory.user_id == 1).values(**{field: "z" * 64})
            )


def test_same_sgf_different_labels_reuses_authoritative_identity(history):
    repo, _ = history
    local = opened(repo, board=True)
    cloud = repo.open(2, {"sgf_content": SGF, "source_id": "personal_2", "name": "Authoritative title"})
    accepted = repo.accept_sync(2, local["id"], payload(local, k=1, writer_seq=1))
    assert accepted["source_id"] == cloud["source_id"] and accepted["name"] == cloud["name"]
    pending = saved(repo, local, 1, board=True)
    repo.absorb_success(
        1,
        local["id"],
        pending,
        dict(
            accepted,
            writer_id=pending["writer_id"],
            writer_seq=pending["writer_seq"],
            last_writer_id=pending["writer_id"],
            last_writer_seq=pending["writer_seq"],
        ),
    )
    settled = repo.get(1, local["id"])
    assert settled["sync_state"] == "synced" and settled["name"] == cloud["name"]


@pytest.mark.parametrize(
    "data",
    [
        {"sgf_content": "(;SZ[19]C[\ud800];B[aa])"},
        {"sgf_content": SGF, "name": "\ud800"},
        {"sgf_content": "(;SZ[19]C[\x00];B[aa])"},
        {"sgf_content": SGF, "source_id": "bad\x00source"},
    ],
)
def test_snapshot_must_be_database_safe_utf8(history, data):
    from katrain.web.core.baipu_history import BaipuHistoryValidationError

    repo, _ = history
    with pytest.raises(BaipuHistoryValidationError):
        repo.open(1, data)


def test_keep_local_retains_conflict_evidence_until_current_sequence_receipt(history):
    repo, _ = history
    old_branch = saved(repo, opened(repo, board=True), 2, board=True)
    remote = dict(old_branch, k=1, cloud_revision=8)
    conflict = repo.absorb_conflict(1, old_branch["id"], old_branch, remote)
    evidence = conflict["conflict_remote"]
    resolved = repo.resolve(
        1,
        old_branch["id"],
        "keep_local",
        dict(remote, _expected_writer_id=conflict["writer_id"]),
        conflict["local_revision"],
    )
    assert resolved["sync_state"] == "pending" and resolved["conflict_remote"] == evidence

    # An acknowledgement for the abandoned writer cannot settle its replacement.
    repo.absorb_success(1, old_branch["id"], old_branch, dict(remote, cloud_revision=9))
    assert repo.get(1, old_branch["id"])["conflict_remote"] == evidence

    current = saved(repo, resolved, 3, board=True, mutation="after-resolution")
    # An intermediate receipt remembers cloud revision but retains newer progress
    # and the evidence while the newer sequence still awaits acceptance.
    repo.absorb_success(1, current["id"], resolved, dict(resolved, cloud_revision=10))
    pending = repo.get(1, current["id"])
    assert pending["sync_state"] == "pending" and pending["conflict_remote"] == evidence
    assert pending["cloud_revision"] == 10 and pending["pending_base_revision"] == 8

    settled = repo.absorb_success(1, current["id"], current, dict(current, cloud_revision=11))
    assert settled["sync_state"] == "synced" and settled["conflict_remote"] is None
    assert settled["pending_base_revision"] is None and settled["k"] == 3
