"""Only pure frozen-batch compilation may survive a request boundary."""

from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
import hashlib
import marshal

import pytest
from sqlalchemy import event
from sqlalchemy.orm import Session

from katrain.web.core.models_db import (
    KifuNameBatch,
    KifuNameChange,
    KifuNameResearchEvidence,
    KifuPlayer,
    KifuNameSourceRegistry,
)
from katrain.web.kifu import name_candidates
from katrain.web.kifu.compiled_first_pass import _CACHE, _CompiledFirstPassCache
from katrain.web.kifu.name_batch import apply_bundle
from tests.web_ui.test_kifu_identity_context import read_player
from tests.web_ui.test_kifu_name_batch import engine, registry
from tests.web_ui.test_kifu_name_first_pass import bound_player_bundle, bound_raw_player_bundle


@pytest.fixture(autouse=True)
def clear_compiled_cache():
    _CACHE.clear()
    yield
    _CACHE.clear()


def test_first_pass_compiles_same_frozen_batch_once_across_fresh_requests(engine, monkeypatch):
    inventory, bundle, research = bound_player_bundle(engine)
    apply_bundle(engine, bundle, registry(), inventory, research)
    digests = {"bundle": 0, "member": 0}
    original = name_candidates.canonical_sha256

    def observe(value):
        if value == bundle:
            digests["bundle"] += 1
        elif value == bundle["candidates"][0]:
            digests["member"] += 1
        return original(value)

    monkeypatch.setattr(name_candidates, "canonical_sha256", observe)
    for _request in range(2):
        with Session(engine) as db:
            assert len(read_player(db, {})) == 1
    # Frozen membership compiles once; each request still hashes its live payload.
    assert digests == {"bundle": 1, "member": 3}


@pytest.mark.parametrize("original, changed", [(17, 17.0), (True, 1), (0.0, -0.0)])
def test_first_pass_cross_request_compilation_rejects_changed_json_types(engine, original, changed):
    inventory, bundle, research = bound_player_bundle(engine)
    bundle["json_number_probe"] = original
    applied = apply_bundle(engine, bundle, registry(), inventory, research)
    with Session(engine) as db:
        assert len(read_player(db, {})) == 1
        held = db.get(KifuNameBatch, applied["batch_id"])
        artifact = deepcopy(held.reviewed_artifact)
    artifact["bundle"]["json_number_probe"] = changed
    with engine.begin() as conn:
        conn.execute(
            KifuNameBatch.__table__.update()
            .where(KifuNameBatch.id == applied["batch_id"])
            .values(reviewed_artifact=artifact)
        )
    with Session(engine) as db:
        assert read_player(db, {}) == []


@pytest.mark.parametrize("column, value", [("status", "undone"), ("bundle_sha256", "f" * 64)])
def test_cross_request_cache_observes_current_batch_scalars(engine, column, value):
    inventory, bundle, research = bound_player_bundle(engine)
    applied = apply_bundle(engine, bundle, registry(), inventory, research)
    with Session(engine) as db:
        assert len(read_player(db, {})) == 1
    with engine.begin() as conn:
        conn.execute(
            KifuNameBatch.__table__.update().where(KifuNameBatch.id == applied["batch_id"]).values({column: value})
        )
    with Session(engine) as db:
        assert read_player(db, {}) == []


@pytest.mark.parametrize("target", ["owner", "evidence", "ledger"])
def test_cross_request_cache_still_reads_mutable_dependencies(engine, target):
    inventory, bundle, research = bound_player_bundle(engine)
    applied = apply_bundle(engine, bundle, registry(), inventory, research)
    with Session(engine) as db:
        first = read_player(db, {})
        evidence_id = first[0][1].id
    with engine.begin() as conn:
        if target == "owner":
            conn.execute(KifuPlayer.__table__.update().where(KifuPlayer.id == 17).values(canonical_name="Changed"))
        elif target == "evidence":
            conn.execute(
                KifuNameResearchEvidence.__table__.update()
                .where(KifuNameResearchEvidence.id == evidence_id)
                .values(review_status="pending")
            )
        else:
            conn.execute(
                KifuNameChange.__table__.update()
                .where(
                    KifuNameChange.batch_id == applied["batch_id"],
                    KifuNameChange.target_table == "kifu_name_research_evidence",
                    KifuNameChange.target_row_id == evidence_id,
                )
                .values(after_image={"changed": True})
            )
    with Session(engine) as db:
        assert read_player(db, {}) == []


def test_cached_proof_refreshes_held_creation_ledger_within_request(engine):
    inventory, bundle, research = bound_player_bundle(engine)
    applied = apply_bundle(engine, bundle, registry(), inventory, research)
    with Session(engine) as db:
        first = read_player(db, {})
        held = (
            db.query(KifuNameChange)
            .filter_by(
                batch_id=applied["batch_id"],
                target_table="kifu_name_research_evidence",
                target_row_id=first[0][1].id,
            )
            .one()
        )
        with engine.begin() as conn:
            conn.execute(
                KifuNameChange.__table__.update()
                .where(KifuNameChange.id == held.id)
                .values(after_image={"changed": True})
            )
        assert read_player(db, {}) == []
        assert held.after_image == {"changed": True}


def test_cache_private_decode_isolates_input_and_each_reader():
    cache = _CompiledFirstPassCache()
    source = (frozenset({"candidate"}), frozenset({"research"}), [{"display": "original"}])
    cache.put("key", source)
    source[2][0]["display"] = "input mutation"
    first = cache.get("key")
    assert first[2] == [{"display": "original"}]
    first[2][0]["display"] = "reader mutation"
    assert cache.get("key")[2] == [{"display": "original"}]


def test_cache_limits_entries_bytes_and_rejects_oversize():
    value = (frozenset({"candidate"}), frozenset({"research"}), [{"display": "original"}])
    size = len(marshal.dumps(value))
    cache = _CompiledFirstPassCache(max_entries=3, max_bytes=2 * size, max_entry_bytes=size)
    cache.put("a", value)
    cache.put("b", value)
    assert cache.get("a") == value
    cache.put("c", value)
    assert cache.get("b") is None
    assert cache.get("a") == cache.get("c") == value
    cache.put("oversize", (*value[:2], ["x" * (size * 2)]))
    assert cache.get("oversize") is None
    entries = _CompiledFirstPassCache(max_entries=1)
    entries.put("a", value)
    entries.put("b", value)
    assert entries.get("a") is None
    assert entries.get("b") == value


def test_cache_concurrent_readers_receive_private_values():
    cache = _CompiledFirstPassCache()
    value = (frozenset({"candidate"}), frozenset({"research"}), [{"display": "original"}])
    cache.put("key", value)

    def read(index):
        for _ in range(20):
            result = cache.get("key")
            assert result[2][0]["display"] == "original"
            result[2][0]["display"] = index
            cache.put((index, _), value)

    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(read, range(4)))
    assert cache.get("key") == value


def test_miss_reads_artifact_and_new_guard_together(engine, monkeypatch):
    inventory, bundle, research = bound_player_bundle(engine)
    applied = apply_bundle(engine, bundle, registry(), inventory, research)
    original_get = _CACHE.get
    original_put = _CACHE.put
    inserted = []
    changed = False

    def change_after_header(key):
        nonlocal changed
        if not changed:
            changed = True
            with engine.begin() as conn:
                conn.execute(
                    KifuNameBatch.__table__.update()
                    .where(KifuNameBatch.id == applied["batch_id"])
                    .values(inventory_sha256="e" * 64)
                )
                artifact = (
                    conn.execute(KifuNameBatch.__table__.select().where(KifuNameBatch.id == applied["batch_id"]))
                    .mappings()
                    .one()["reviewed_artifact"]
                )
                artifact["unsigned_metadata_probe"] = "new row"
                conn.execute(
                    KifuNameBatch.__table__.update()
                    .where(KifuNameBatch.id == applied["batch_id"])
                    .values(reviewed_artifact=artifact)
                )
        return original_get(key)

    def capture_put(key, compiled):
        inserted.append(key)
        original_put(key, compiled)

    monkeypatch.setattr(_CACHE, "get", change_after_header)
    monkeypatch.setattr(_CACHE, "put", capture_put)
    with Session(engine) as db:
        assert len(read_player(db, {})) == 1
    with engine.connect() as conn:
        from sqlalchemy import Text, cast, select

        artifact_text = conn.execute(
            select(cast(KifuNameBatch.reviewed_artifact, Text)).where(KifuNameBatch.id == applied["batch_id"])
        ).scalar_one()
    assert len(inserted) == 1
    assert inserted[0][3] == "e" * 64
    assert inserted[0][-1] == hashlib.sha256(artifact_text.encode("utf-8")).hexdigest()


def test_cache_hit_does_not_load_deferred_artifact(engine):
    inventory, bundle, research = bound_player_bundle(engine)
    apply_bundle(engine, bundle, registry(), inventory, research)
    with Session(engine) as db:
        assert len(read_player(db, {})) == 1
    loaded = []

    def capture(batch, context):
        loaded.append("reviewed_artifact" in batch.__dict__)

    event.listen(KifuNameBatch, "load", capture)
    try:
        with Session(engine) as db:
            assert len(read_player(db, {})) == 1
    finally:
        event.remove(KifuNameBatch, "load", capture)
    assert loaded == [False]


def test_raw_player_cache_hit_expires_held_old_artifact_before_scope_read(engine):
    from katrain.web.kifu.identity import _approved_raw_player_names

    inventory, bundle, research = bound_raw_player_bundle(engine)
    applied = apply_bundle(engine, bundle, registry(), inventory, research)

    def read(db):
        return _approved_raw_player_names(db, values={"李元赫九段"}, lang="en", orthographic_batch_contexts={})

    with Session(engine) as held_session:
        held = held_session.get(KifuNameBatch, applied["batch_id"])
        assert len(read(held_session)) == 1
        artifact = deepcopy(held.reviewed_artifact)
        artifact["bundle"]["metadata_probe"] = "current legal bundle"
        with engine.begin() as conn:
            conn.execute(
                KifuNameBatch.__table__.update()
                .where(KifuNameBatch.id == held.id)
                .values(reviewed_artifact=artifact, bundle_sha256=name_candidates.canonical_sha256(artifact["bundle"]))
            )
        # Another request warms the new, valid content while A holds old JSON.
        with Session(engine) as fresh_session:
            assert len(read(fresh_session)) == 1
        assert len(read(held_session)) == 1
        assert held.reviewed_artifact == artifact


def test_cold_batches_compile_serially_and_release_full_json_before_return(engine, monkeypatch):
    from katrain.web.kifu import compiled_first_pass

    with Session(engine) as db:
        source = KifuNameSourceRegistry(version="serial", sha256="b" * 64, registry={})
        db.add(source)
        db.flush()
        ids = []
        for index in range(3):
            bundle = {"candidates": [{"id": index}], "padding": str(index) * (1024 * 1024)}
            batch = KifuNameBatch(
                bundle_sha256=name_candidates.canonical_sha256(bundle),
                inventory_sha256="c" * 64,
                source_registry_id=source.id,
                reviewed_artifact={"bundle": bundle, "research_hashes": []},
                status="applied",
            )
            db.add(batch)
            db.flush()
            ids.append(batch.id)
        db.commit()
    compile_original = compiled_first_pass.compile_first_pass
    with Session(engine) as db:

        def compile_one(status, digest, artifact):
            loaded = [
                row
                for row in db.identity_map.values()
                if isinstance(row, KifuNameBatch) and "reviewed_artifact" in row.__dict__
            ]
            assert len(loaded) == 1, "cold artifacts must not accumulate before compilation"
            return compile_original(status, digest, artifact)

        monkeypatch.setattr(compiled_first_pass, "compile_first_pass", compile_one)
        batches, compiled = compiled_first_pass.read_compiled_first_pass(db, set(ids))
        assert set(batches) == set(compiled) == set(ids)
        assert all(value is not None for value in compiled.values())
        assert all("reviewed_artifact" not in batch.__dict__ for batch in batches.values())


@pytest.mark.parametrize("drift", ["artifact", "status", "source"])
def test_serial_compilation_still_rechecks_same_connection_uncommitted_drift(engine, drift):
    inventory, bundle, research = bound_player_bundle(engine)
    applied = apply_bundle(engine, bundle, registry(), inventory, research)
    with engine.begin() as conn, Session(bind=conn) as db:
        assert len(read_player(db, {})) == 1
        held_batch = db.get(KifuNameBatch, applied["batch_id"])
        held_owner = db.get(KifuPlayer, 17)
        if drift == "artifact":
            artifact = deepcopy(held_batch.reviewed_artifact)
            artifact["bundle"]["changed_probe"] = True
            conn.execute(
                KifuNameBatch.__table__.update()
                .where(KifuNameBatch.id == held_batch.id)
                .values(reviewed_artifact=artifact)
            )
        elif drift == "status":
            conn.execute(
                KifuNameBatch.__table__.update().where(KifuNameBatch.id == held_batch.id).values(status="undone")
            )
        else:
            conn.execute(
                KifuPlayer.__table__.update()
                .where(KifuPlayer.id == held_owner.id)
                .values(canonical_name="Changed source")
            )
        assert read_player(db, {}) == []
