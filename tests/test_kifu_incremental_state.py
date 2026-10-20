"""Durable orchestration state; SQLite verifies portable Core behavior, not PG locks."""

import pytest
from sqlalchemy import create_engine, inspect

from katrain.kifu_ingest.state import Conflict, StateStore, metadata


HASH_A = "a" * 64
HASH_B = "b" * 64


@pytest.fixture
def store():
    engine = create_engine("sqlite:///:memory:")
    metadata.create_all(engine)
    yield StateStore(engine)
    engine.dispose()


def test_constructor_and_read_do_not_create_tables():
    engine = create_engine("sqlite:///:memory:")
    state = StateStore(engine)
    assert state.snapshot_status() == {"batches": {}, "items": {}}
    assert inspect(engine).get_table_names() == []
    engine.dispose()


def test_source_identity_and_content_are_immutable(store):
    first = store.remember_item("19x19", "42", raw_sha256=HASH_A)
    assert store.remember_item("19x19", "42", raw_sha256=HASH_A)["id"] == first["id"]
    with pytest.raises(Conflict, match="content changed"):
        store.remember_item("19x19", "42", raw_sha256=HASH_B)
    for source, external in (("other", "42"), ("19x19", "+42"), ("19x19", "٤٢")):
        with pytest.raises(ValueError):
            store.remember_item(source, external)


def test_publication_key_hash_is_pinned_and_uuid_stable(store):
    first = store.register_batch("hour-1", HASH_A)
    assert store.register_batch("hour-1", HASH_A)["batch_uuid"] == first["batch_uuid"]
    with pytest.raises(Conflict, match="different manifest"):
        store.register_batch("hour-1", HASH_B)


def test_item_cas_and_ordering(store):
    store.remember_item("19x19", "42", raw_sha256=HASH_A)
    row = store.advance_item("19x19", "42", "downloaded", expected_status="discovered", staging_path="s/42.sgf")
    assert row["status"] == "downloaded"
    with pytest.raises(Conflict, match="status changed"):
        store.advance_item("19x19", "42", "downloaded", expected_status="discovered", staging_path="other")
    with pytest.raises(Conflict, match="illegal transition"):
        store.advance_item("19x19", "42", "names_ready", expected_status="downloaded")
    with pytest.raises(Conflict, match="illegal transition"):
        store.advance_item("19x19", "42", "discovered", expected_status="downloaded")


def test_published_is_not_verified_and_receipts_are_immutable(store):
    store.register_batch("hour-1", HASH_A)
    for status, preceding in (("downloaded", "discovered"), ("parsed", "downloaded"), ("names_ready", "parsed")):
        store.advance_batch("hour-1", status, expected_status=preceding)
    receipt = {"batch_id": 7, "status": "applied"}
    published = store.advance_batch("hour-1", "test_published", expected_status="names_ready", receipt=receipt)
    assert published["status"] == "test_published"
    assert published["test_receipt"] == receipt
    assert published["test_verification"] is None
    assert store.snapshot_status()["batches"]["test_published"] == 1
    assert store.advance_batch("hour-1", "test_published", expected_status="names_ready", receipt=receipt) == published
    with pytest.raises(Conflict):
        store.advance_batch("hour-1", "test_published", expected_status="names_ready", receipt={"batch_id": 8})
    with pytest.raises(ValueError, match="receipt"):
        store.advance_batch("hour-1", "test_verified", expected_status="test_published")
    verified = store.advance_batch(
        "hour-1", "test_verified", expected_status="test_published", receipt={"api_ok": True}
    )
    assert verified["test_receipt"] == receipt
    assert verified["test_verification"] == {"api_ok": True}


def test_retry_preserves_resume_phase_and_prior_publication(store):
    store.remember_item("19x19", "42", raw_sha256=HASH_A)
    store.advance_item("19x19", "42", "downloaded", expected_status="discovered")
    waiting = store.advance_item("19x19", "42", "retry_wait", expected_status="downloaded", error="temporary")
    assert (waiting["resume_phase"], waiting["attempts"]) == ("downloaded", 1)
    with pytest.raises(Conflict, match="illegal transition"):
        store.advance_item("19x19", "42", "parsed", expected_status="retry_wait")
    store.advance_item("19x19", "42", "downloaded", expected_status="retry_wait")
    store.advance_item("19x19", "42", "parsed", expected_status="downloaded", sgf_sha256=HASH_B)
    store.advance_item("19x19", "42", "names_ready", expected_status="parsed")
    store.advance_item("19x19", "42", "test_published", expected_status="names_ready", receipt={"batch_id": 7})
    with pytest.raises(Conflict, match="content changed"):
        store.remember_item("19x19", "42", raw_sha256=HASH_A, sgf_sha256=HASH_A)


def test_lost_orchestration_receipt_can_be_replayed(store):
    store.register_batch("hour-1", HASH_A)
    for status, preceding in (("downloaded", "discovered"), ("parsed", "downloaded"), ("names_ready", "parsed")):
        store.advance_batch("hour-1", status, expected_status=preceding)
    receipt = {"batch_id": 7, "manifest_sha256": HASH_A}
    # Native catalog publication may commit before this journal receives its receipt.
    # Replaying native publication yields the same receipt, which can be recorded here.
    first = store.advance_batch("hour-1", "test_published", expected_status="names_ready", receipt=receipt)
    assert store.advance_batch("hour-1", "test_published", expected_status="names_ready", receipt=receipt) == first
    assert first["test_receipt"] == receipt
    assert first["test_verification"] is None
    with pytest.raises(Conflict, match="illegal transition"):
        store.advance_batch("hour-1", "prod_published", expected_status="test_published", receipt=receipt)


def test_recovery_cannot_skip_test_verification(store):
    store.register_batch("hour-1", HASH_A)
    for status, preceding in (("downloaded", "discovered"), ("parsed", "downloaded"), ("names_ready", "parsed")):
        store.advance_batch("hour-1", status, expected_status=preceding)
    with pytest.raises(Conflict, match="illegal transition"):
        store.advance_batch("hour-1", "prod_published", expected_status="names_ready", receipt={"batch_id": 7})


def test_prod_publication_adds_target_mapping_without_changing_pinned_source(store):
    store.register_batch("hour-1", HASH_A)
    store.remember_item("19x19", "42", raw_sha256=HASH_A)
    for status, preceding, extra in (
        ("downloaded", "discovered", {}),
        ("parsed", "downloaded", {"sgf_sha256": HASH_B}),
        ("names_ready", "parsed", {"publication_key": "hour-1"}),
        ("test_published", "names_ready", {"receipt": {"batch_id": 7}, "test_album_id": 41}),
        ("test_verified", "test_published", {"receipt": {"api_ok": True}}),
    ):
        store.advance_item("19x19", "42", status, expected_status=preceding, **extra)
    row = store.advance_item(
        "19x19", "42", "prod_published", expected_status="test_verified", receipt={"batch_id": 8}, prod_album_id=123
    )
    assert row["test_album_id"] == 41
    assert row["prod_album_id"] == 123
    assert row["raw_sha256"] == HASH_A
    assert row["sgf_sha256"] == HASH_B
    with pytest.raises(Conflict):
        store.advance_item(
            "19x19", "42", "prod_synced", expected_status="prod_published", receipt={"api_ok": True}, prod_album_id=124
        )


def test_sql_compiles_for_postgresql_without_dialect_specific_upsert():
    from sqlalchemy.dialects import postgresql
    from katrain.kifu_ingest.state import batches, items

    assert "kifu_ingest_batches" in str(batches.insert().compile(dialect=postgresql.dialect()))
    assert "kifu_ingest_items" in str(items.update().compile(dialect=postgresql.dialect()))
