"""Search writes follow real catalog commits, including replay and recovery."""

from copy import deepcopy
import importlib.util

import pytest
from sqlalchemy import create_engine, select

from katrain.web.core.models_db import Base, KifuAlbum
from katrain.web.kifu import name_batch


def module():
    assert importlib.util.find_spec("katrain.web.kifu.search_sync") is not None, "post-commit search sync is missing"
    from katrain.web.kifu import search_sync

    return search_sync


class ES:
    def __init__(self):
        self.state = {
            "doc_kind": "sync_state",
            "status": "ready",
            "schema_version": "kifu-search-v1",
            "strict_mode": False,
            "epoch": 4,
            "target_index": "kifu-test-1",
            "operation_type": None,
            "operation_ref": None,
        }
        self.actions, self.events = [], []
        self.fail_bulk = False

    def resolve_index(self):
        return "kifu-test-1"

    def get_document(self, document_id, **kwargs):
        return {"found": True, "_source": deepcopy(self.state)}

    def put_document(self, document_id, body, **kwargs):
        self.state = deepcopy(body)
        self.events.append(body["status"])

    def bulk(self, actions, **kwargs):
        self.actions.extend(deepcopy(actions))
        if self.fail_bulk:
            raise RuntimeError("ES failed")
        return {"errors": False, "items": []}

    def refresh(self, **kwargs):
        self.events.append("refresh")

    def close(self):
        pass


@pytest.fixture
def setup(tmp_path, monkeypatch):
    sync = module()
    engine = create_engine(f"sqlite:///{tmp_path}/writer.db")
    Base.metadata.create_all(engine)
    es = ES()
    monkeypatch.setenv("KIFU_SEARCH_SYNC_MODE", "enabled")
    monkeypatch.setenv("KIFU_SEARCH_BACKEND", "elasticsearch")
    monkeypatch.delenv("KIFU_STRICT_NAMES", raising=False)
    monkeypatch.setattr(sync, "_writer_client", lambda: es)
    yield sync, engine, es
    engine.dispose()


def test_rollback_restores_gate_without_album_writes(setup, monkeypatch):
    sync, engine, es = setup
    monkeypatch.setattr(sync, "_operation_scope", lambda conn, kind, ref: sync.ChangeScope())
    with pytest.raises(ValueError, match="reject"):
        with name_batch._locked_write(engine, search_operation=("name_apply", {"bundle_sha256": "a" * 64})) as conn:
            assert es.state["status"] == "pending"
            conn.execute(
                KifuAlbum.__table__.insert().values(
                    id=1, player_black="B", player_white="W", sgf_content="(;)", source_path="x"
                )
            )
            raise ValueError("reject")
    with engine.connect() as conn:
        assert conn.scalar(select(KifuAlbum.id)) is None
    assert es.actions == []
    assert es.state["status"] == "ready"
    assert es.state["epoch"] == 5


def test_sync_reads_only_after_real_commit_and_leaves_repairable_pending(setup, monkeypatch):
    sync, engine, es = setup
    monkeypatch.setattr(sync, "_operation_scope", lambda conn, kind, ref: sync.ChangeScope(album_ids={1}))

    def actions(conn, scope):
        with engine.connect() as observer:
            assert observer.scalar(select(KifuAlbum.id)) == 1
        return [{"_op_type": "index", "_id": "album:1", "_source": {"id": 1}}]

    monkeypatch.setattr(sync, "_project_actions", actions)
    es.fail_bulk = True
    with pytest.raises(sync.SearchIndexPending) as error:
        with name_batch._locked_write(engine, search_operation=("name_apply", {"bundle_sha256": "a" * 64})) as conn:
            conn.execute(
                KifuAlbum.__table__.insert().values(
                    id=1, player_black="B", player_white="W", sgf_content="(;)", source_path="x"
                )
            )
    assert error.value.operation_ref == {"bundle_sha256": "a" * 64}
    assert es.state["status"] == "pending"
    with engine.connect() as conn:
        assert conn.scalar(select(KifuAlbum.id)) == 1


def test_old_unknown_pending_blocks_new_pg_business(setup):
    sync, engine, es = setup
    es.state.update(status="pending", operation_type="unrecognized", operation_ref={"opaque": "x"})
    entered = False
    with pytest.raises(sync.SearchIndexPending):
        with name_batch._locked_write(engine, search_operation=("name_apply", {"bundle_sha256": "a" * 64})):
            entered = True
    assert not entered
    assert es.state["operation_ref"] == {"opaque": "x"}
    assert es.state["epoch"] == 4


def test_pending_before_native_journal_crash_restores_ready_same_epoch(setup):
    sync, engine, es = setup
    es.state.update(status="pending", operation_type="name_apply", operation_ref={"bundle_sha256": "b" * 64})
    assert sync.recover_pending(engine) == {"status": "ready", "epoch": 4}
    assert es.state["epoch"] == 4
    assert es.state["status"] == "ready"
    assert es.actions == []


def test_manual_prefile_is_private_bounded_and_recovers_actual_keys(setup, tmp_path):
    sync, engine, es = setup
    path = tmp_path / "manual-import.json"
    with engine.begin() as conn:
        conn.execute(
            KifuAlbum.__table__.insert().values(
                id=7, player_black="B", player_white="W", sgf_content="(;)", source_path="old.sgf"
            )
        )
    ref = sync.prepare_manual_import(
        path,
        "d" * 64,
        [{"source_path": "missing.sgf", "old_album_id": 7}, {"source_path": "new.sgf", "old_album_id": None}],
    )
    assert path.stat().st_mode & 0o777 == 0o600
    assert "(;)" not in path.read_text()
    with engine.connect() as conn:
        scope = sync._operation_scope(conn, "manual_import", ref)
    assert scope.album_ids == {7}
    with pytest.raises(ValueError, match="unresolved"):
        sync.prepare_manual_import(path, "e" * 64, [])


@pytest.mark.asyncio
@pytest.mark.parametrize("phase", ["test_published", "test_verified", "prod_published"])
async def test_durable_reentry_repairs_original_manifest_before_verification(monkeypatch, phase):
    from katrain.cron.jobs.kifu_ingest import resume_batch

    monkeypatch.setenv("KIFU_SEARCH_SYNC_MODE", "enabled")
    monkeypatch.setenv("KIFU_SEARCH_BACKEND", "elasticsearch")
    manifest = {"publication_key": "same-manifest", "games": []}
    receipt = {"batch_id": 9, "games": []}
    verification = {"status": "verified", "manifest_sha256": "d" * 64}

    class Store:
        row = {"status": phase, "test_receipt": receipt, "test_verification": verification, "prod_receipt": receipt}

        def get_batch(self, key):
            return self.row

        def advance_batch(self, key, status, *, expected_status, receipt):
            assert self.row["status"] == expected_status
            self.row = {
                **self.row,
                "status": status,
                {
                    "test_verified": "test_verification",
                    "prod_published": "prod_receipt",
                    "prod_synced": "prod_verification",
                }[status]: receipt,
            }
            return self.row

    events = []

    def local(package, digest):
        assert package is manifest and digest == "d" * 64
        events.append("local repair")
        return receipt

    def restricted(package, digest, original_verification):
        assert package is manifest and digest == "d" * 64
        if phase == "prod_published":
            assert original_verification is verification
        events.append("restricted same-manifest replay")
        return {"receipt": receipt}

    def test_verify(package, original_receipt):
        assert original_receipt is receipt
        events.append("test verify")
        return verification

    def prod_verify(package, original_receipt):
        assert original_receipt is receipt
        events.append("prod verify")
        return verification

    result = await resume_batch(
        Store(),
        manifest,
        "d" * 64,
        test_publish=local,
        test_verify=test_verify,
        sync=restricted,
        prod_verify=prod_verify,
    )
    assert result["status"] == "prod_synced"
    if phase == "prod_published":
        assert events == ["restricted same-manifest replay", "prod verify"]
    elif phase == "test_published":
        assert events == ["local repair", "test verify", "restricted same-manifest replay", "prod verify"]
    else:
        assert events == ["local repair", "restricted same-manifest replay", "prod verify"]


def test_catalog_commit_failure_retry_reuses_native_receipt_and_old_raw_scope(tmp_path, monkeypatch):
    from tests.web_ui.test_kifu_incremental_catalog import make_engine, manifest, publish
    from katrain.web.core.models_db import KifuNameBatch

    sync = module()
    monkeypatch.setenv("KIFU_SEARCH_SYNC_MODE", "disabled")
    monkeypatch.setenv("KIFU_SEARCH_BACKEND", "legacy")
    engine = make_engine(tmp_path / "catalog.db")
    es = ES()
    monkeypatch.setenv("KIFU_SEARCH_SYNC_MODE", "enabled")
    monkeypatch.setenv("KIFU_SEARCH_BACKEND", "elasticsearch")
    monkeypatch.setattr(sync, "_writer_client", lambda: es)
    seen = []

    def actions(conn, scope):
        seen.append(set(scope.album_ids))
        return [
            {"_op_type": "index", "_id": f"album:{value}", "_source": {"id": value}}
            for value in sorted(scope.album_ids)
        ]

    monkeypatch.setattr(sync, "_project_actions", actions)
    es.fail_bulk = True
    value = manifest()
    with pytest.raises(sync.SearchIndexPending):
        publish(engine, value)
    with engine.connect() as conn:
        committed_batches = list(conn.scalars(select(KifuNameBatch.id)))
        committed_albums = list(conn.scalars(select(KifuAlbum.id)))
    assert len(committed_albums) == 2
    assert 11 in seen[0]  # Existing raw-title scope, beyond the new game's ID.
    es.fail_bulk = False
    receipt = publish(engine, value)
    assert receipt["games"][0]["album_id"] != 11
    assert es.state["status"] == "ready"
    with engine.connect() as conn:
        assert list(conn.scalars(select(KifuNameBatch.id))) == committed_batches
        assert list(conn.scalars(select(KifuAlbum.id))) == committed_albums
    engine.dispose()


def test_real_publication_undo_projects_physically_deleted_id(tmp_path, monkeypatch):
    from tests.web_ui.test_kifu_incremental_catalog import make_engine, manifest, publish
    from katrain.kifu_ingest.catalog import undo_publication

    sync = module()
    monkeypatch.setenv("KIFU_SEARCH_SYNC_MODE", "disabled")
    monkeypatch.setenv("KIFU_SEARCH_BACKEND", "legacy")
    engine = make_engine(tmp_path / "undo.db")
    receipt = publish(engine, manifest())
    new_id = receipt["games"][0]["album_id"]
    monkeypatch.setenv("KIFU_SEARCH_SYNC_MODE", "enabled")
    monkeypatch.setenv("KIFU_SEARCH_BACKEND", "elasticsearch")
    es = ES()
    monkeypatch.setattr(sync, "_writer_client", lambda: es)

    def actions(conn, scope):
        existing = set(conn.scalars(select(KifuAlbum.id).where(KifuAlbum.id.in_(scope.album_ids))))
        return [{"_op_type": "delete", "_id": f"album:{value}"} for value in scope.album_ids - existing]

    monkeypatch.setattr(sync, "_project_actions", actions)
    undo_publication(engine, receipt["batch_id"])
    assert {"_op_type": "delete", "_id": f"album:{new_id}"} in es.actions
    with engine.connect() as conn:
        assert conn.scalar(select(KifuAlbum.id).where(KifuAlbum.id == new_id)) is None
    engine.dispose()


def test_pg_original_session_keys_survive_commit_through_sync(monkeypatch):
    from types import SimpleNamespace

    sync = module()
    events = []

    class Result:
        def scalar_one(self):
            return True

    class Connection:
        invalidated = False

        def execution_options(self, **kwargs):
            return self

        def begin(self):
            events.append("begin")

        def execute(self, statement, parameters=None):
            events.append(str(statement))
            return Result()

        def exec_driver_sql(self, statement, parameters=None):
            events.append((statement, parameters))
            return Result()

        def commit(self):
            events.append("commit")

        def rollback(self):
            events.append("rollback")

        def invalidate(self):
            self.invalidated = True

        def close(self):
            events.append("close")

    connection = Connection()
    engine = SimpleNamespace(dialect=SimpleNamespace(name="postgresql"), connect=lambda: connection)
    monkeypatch.setattr(sync, "begin_sync", lambda conn, *args: events.append("pending") or object())
    monkeypatch.setattr(sync, "finish_sync", lambda conn, token: events.append("sync"))
    monkeypatch.setattr(sync, "cancel_sync", lambda token: events.append("cancel"))
    with name_batch._locked_write(engine, search_operation=("name_apply", {"bundle_sha256": "a" * 64})):
        events.append("business")
    acquisitions = [
        (statement, params)
        for statement, params in (item for item in events if isinstance(item, tuple))
        if statement == "SELECT pg_advisory_lock(%s)"
    ]
    assert acquisitions == [
        ("SELECT pg_advisory_lock(%s)", (720220261002,)),
        ("SELECT pg_advisory_lock(%s)", (720220261003,)),
    ]
    assert events.index("pending") < events.index("business")
    assert events[events.index("business") + 1 : events.index("sync")] == ["commit"]
    unlock = next(
        index
        for index, item in enumerate(events)
        if isinstance(item, tuple) and item[0] == "SELECT pg_advisory_unlock(%s)"
    )
    assert events.index("sync") < unlock
    assert "cancel" not in events


def test_partial_bulk_failure_never_marks_ready(setup, monkeypatch):
    sync, engine, es = setup
    monkeypatch.setattr(sync, "_project_actions", lambda conn, scope: [{"_op_type": "delete", "_id": "album:7"}])
    es.bulk = lambda *args, **kwargs: {"errors": True, "items": [{"delete": {"status": 429, "error": "busy"}}]}
    with pytest.raises(sync.SearchIndexPending):
        with name_batch._locked_write(engine, search_operation=("sync_ids", {"album_ids": [7]})):
            pass
    assert es.state["status"] == "pending"
    assert "refresh" not in es.events


def test_target_mismatch_blocks_pg_before_pending(setup):
    sync, engine, es = setup
    es.state["target_index"] = "other-environment"
    with pytest.raises(sync.SearchIndexPending):
        with name_batch._locked_write(engine, search_operation=("sync_ids", {"album_ids": [7]})):
            pytest.fail("business transaction must not start")
    assert es.events == []


def test_native_name_undo_reentry_after_es_failure_reports_recovered_success(tmp_path, monkeypatch):
    from tests.web_ui.test_kifu_name_batch import player_bundle, registry
    from katrain.web.kifu.name_inventory import build_inventory
    from katrain.web.core.models_db import KifuRawEventValue, KifuPlayer

    sync = module()
    engine = create_engine(f"sqlite:///{tmp_path}/name-undo.db")
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(KifuPlayer.__table__.insert().values(id=17, canonical_name="吴清源"))
        conn.execute(
            KifuRawEventValue.__table__.insert().values(
                id=7, raw_value="GNUGo3.8", category="program_source_label", review_status="approved"
            )
        )
        conn.execute(
            KifuAlbum.__table__.insert().values(
                id=11,
                black_player_id=17,
                player_black="吴清源九段",
                player_white="Unknown",
                event="GNUGo3.8",
                sgf_content="(;)",
                source_path="one.sgf",
            )
        )
    inv = build_inventory(engine)
    bundle, evidence = player_bundle(inv)
    monkeypatch.setenv("KIFU_SEARCH_SYNC_MODE", "disabled")
    monkeypatch.setenv("KIFU_SEARCH_BACKEND", "legacy")
    result = name_batch.apply_bundle(engine, bundle, registry(), inv, evidence)
    monkeypatch.setenv("KIFU_SEARCH_SYNC_MODE", "enabled")
    monkeypatch.setenv("KIFU_SEARCH_BACKEND", "elasticsearch")
    es = ES()
    monkeypatch.setattr(sync, "_writer_client", lambda: es)
    monkeypatch.setattr(sync, "_project_actions", lambda conn, scope: [{"_op_type": "delete", "_id": "term:gone"}])
    es.fail_bulk = True
    with pytest.raises(sync.SearchIndexPending):
        name_batch.undo_batch(engine, result["batch_id"])
    es.fail_bulk = False
    replay = name_batch.undo_batch(engine, result["batch_id"])
    assert replay["status"] == "already_undone"
    assert es.state["status"] == "ready"
    engine.dispose()


def test_real_projection_after_publish_includes_five_displays_and_deletes_on_undo(tmp_path, monkeypatch):
    from tests.web_ui.test_kifu_incremental_catalog import make_engine, manifest, publish
    from katrain.kifu_ingest.catalog import undo_publication

    sync = module()
    monkeypatch.setenv("KIFU_SEARCH_SYNC_MODE", "disabled")
    monkeypatch.setenv("KIFU_SEARCH_BACKEND", "legacy")
    monkeypatch.setenv("KIFU_STRICT_NAMES", "1")
    engine = make_engine(tmp_path / "projected.db")
    monkeypatch.setenv("KIFU_SEARCH_SYNC_MODE", "enabled")
    monkeypatch.setenv("KIFU_SEARCH_BACKEND", "elasticsearch")
    es = ES()
    es.state["strict_mode"] = True
    monkeypatch.setattr(sync, "_writer_client", lambda: es)
    receipt = publish(engine, manifest())
    album_id = receipt["games"][0]["album_id"]
    doc = next(action["_source"] for action in es.actions if action["_id"] == f"album:{album_id}")
    assert set(doc["display"]) == {"cn", "tw", "en", "jp", "ko"}
    assert doc["display"]["en"]["event"] == "Summer Cup"
    assert doc["metadata"]["sources"] == ["19x19"]
    assert doc["list_visible"] is True
    assert any(action["_id"] == "album:11" for action in es.actions)
    es.actions.clear()
    undo_publication(engine, receipt["batch_id"])
    assert {"_op_type": "delete", "_id": f"album:{album_id}"} in es.actions
    assert es.state["status"] == "ready"
    engine.dispose()


def test_lost_commit_acknowledgement_stays_pending_and_original_journal_repairs(setup, monkeypatch):
    from sqlalchemy.engine import Connection
    from katrain.web.core.models_db import KifuNameBatch, KifuNameSourceRegistry
    from katrain.web.kifu.name_candidates import canonical_sha256

    sync, engine, es = setup
    bundle = {"fixture": "original atomic operation"}
    digest = canonical_sha256(bundle)
    real_commit = Connection.commit

    def lose_acknowledgement(conn):
        real_commit(conn)
        if conn.info.pop("lose_commit_ack", False):
            raise RuntimeError("commit acknowledgement lost")

    monkeypatch.setattr(Connection, "commit", lose_acknowledgement)
    monkeypatch.setattr(sync, "_project_actions", lambda conn, scope: [])
    with pytest.raises(sync.SearchIndexPending, match="outcome is unknown"):
        with name_batch._locked_write(engine, search_operation=("name_apply", {"bundle_sha256": digest})) as conn:
            registry_id = conn.execute(
                KifuNameSourceRegistry.__table__.insert().values(version="test", sha256="1" * 64, registry={})
            ).inserted_primary_key[0]
            conn.execute(
                KifuNameBatch.__table__.insert().values(
                    bundle_sha256=digest,
                    inventory_sha256="2" * 64,
                    source_registry_id=registry_id,
                    reviewed_artifact={"bundle": bundle},
                    status="applied",
                )
            )
            conn.info["lose_commit_ack"] = True
    assert es.state["status"] == "pending"
    epoch = es.state["epoch"]
    assert sync.recover_pending(engine) == {"status": "ready", "epoch": epoch}
    assert es.state["epoch"] == epoch
    assert es.state["status"] == "ready"


def test_existing_hidden_album_is_reprojected_with_visible_false(setup):
    sync, engine, es = setup
    with engine.begin() as conn:
        conn.execute(
            KifuAlbum.__table__.insert().values(
                id=8,
                player_black="B",
                player_white="W",
                sgf_content="(;)",
                source_path="hidden.sgf",
                list_hidden_reason="reviewed duplicate",
            )
        )
    sync.sync_ids(engine, [8])
    doc = next(action["_source"] for action in es.actions if action["_id"] == "album:8")
    assert doc["list_visible"] is False


def test_manual_real_commit_es_failure_repairs_without_reimport(setup, tmp_path, monkeypatch):
    from scripts import import_kifu
    from sqlalchemy import func

    sync, engine, es = setup
    folder = tmp_path / "data/kifu-album/19x19"
    folder.mkdir(parents=True)
    (folder / "9.sgf").write_text("(;FF[4]GM[1]PB[Black]PW[White]EV[Test];B[aa])")
    record = tmp_path / "manual-import.json"
    monkeypatch.setattr(import_kifu, "DATA_DIR", folder.parent)
    monkeypatch.setattr(import_kifu, "engine", engine)
    monkeypatch.setenv("KIFU_SEARCH_IMPORT_RECORD", str(record))
    es.fail_bulk = True
    with pytest.raises(sync.SearchIndexPending):
        import_kifu.import_kifu()
    with engine.connect() as conn:
        assert conn.scalar(select(func.count()).select_from(KifuAlbum)) == 1
    es.fail_bulk = False
    assert sync.repair_manual_import(engine, record)["original_import_status"] == "unknown"
    assert es.state["status"] == "ready"
    import json

    summary = json.loads(record.read_text())
    assert summary["status"] == "repaired"
    assert "source_paths" not in summary
    with engine.connect() as conn:
        assert conn.scalar(select(func.count()).select_from(KifuAlbum)) == 1
