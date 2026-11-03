"""Opt-in expression-index checks use only disposable local PostgreSQL schemas."""

from copy import deepcopy
import importlib
import os
from time import monotonic
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, event, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError

from katrain.kifu_ingest import catalog
from katrain.web.core import models_db as m
from katrain.web.kifu import historical_ranks


def operator():
    assert importlib.util.find_spec("scripts.kifu_source_receipts_index"), "explicit receipt index operator missing"
    return importlib.import_module("scripts.kifu_source_receipts_index")


@pytest.fixture
def pg():
    dsn = os.getenv("KIFU_STANDARDIZATION_TEST_PG_DSN")
    if not dsn:
        pytest.skip("set KIFU_STANDARDIZATION_TEST_PG_DSN for a disposable local PostgreSQL schema")
    assert make_url(dsn).host in {"127.0.0.1", "localhost"}
    schema = "receipt_index_" + uuid4().hex
    admin = create_engine(dsn, hide_parameters=True)
    with admin.begin() as conn:
        conn.exec_driver_sql(f'CREATE SCHEMA "{schema}"')
    engine = create_engine(dsn, hide_parameters=True, connect_args={"options": f"-csearch_path={schema}"})
    try:
        m.Base.metadata.create_all(engine)
        with engine.begin() as conn:
            registry_id = conn.execute(
                m.KifuNameSourceRegistry.__table__.insert().values(
                    version="receipt-index-test", sha256="0" * 64, registry={}
                )
            ).inserted_primary_key[0]
        yield engine, schema, registry_id
    finally:
        engine.dispose()
        with admin.begin() as conn:
            conn.exec_driver_sql(f'DROP SCHEMA "{schema}" CASCADE')
        admin.dispose()


def add_batch(conn, registry_id, ident, artifact, status="applied"):
    conn.execute(
        m.KifuNameBatch.__table__.insert().values(
            id=ident,
            bundle_sha256=f"{ident:064x}",
            inventory_sha256="0" * 64,
            source_registry_id=registry_id,
            status=status,
            reviewed_artifact=artifact,
        )
    )


def source(album_id=991):
    return dict(
        source_key="19x19",
        source_item_id="99101",
        album_id=album_id,
        origin_path="data/kifu-album/19x19/99101.sgf",
        raw_sha256="a" * 64,
        sgf_sha256="b" * 64,
        album_sgf_sha256="b" * 64,
    )


def test_check_does_not_run_ddl_and_apply_verifies_definition(pg):
    tool = operator()
    engine, schema, _ = pg
    seen = []
    event.listen(engine, "before_cursor_execute", lambda conn, cursor, sql, *args: seen.append(sql))
    status = tool.check_index(engine, schema=schema)
    assert status["state"] == "missing"
    assert not any(sql.lstrip().upper().startswith(("CREATE", "DROP", "ANALYZE", "ALTER")) for sql in seen)
    with engine.connect() as conn:
        database = conn.exec_driver_sql("SELECT current_database()").scalar_one()
    result = tool.apply_index(engine, schema=schema, expected_database=database, analyze=True)
    assert result["state"] == "ready" and result["index"]["valid"] and result["index"]["ready"]
    assert result["index"]["definition_matches"] and result["analyzed"]
    assert tool.check_index(engine, schema=schema)["oid"] == result["index"]["oid"]


def _plan_uses(plan, index):
    return plan.get("Index Name") == index or any(_plan_uses(child, index) for child in plan.get("Plans", []))


def test_actual_receipt_query_uses_index_without_changing_authority_or_bounds(pg, monkeypatch):
    tool = operator()
    engine, schema, registry = pg
    receipt = source()
    with engine.begin() as conn:
        add_batch(conn, registry, 1, dict(publication_format=catalog.FORMAT, sources=[receipt]))
        add_batch(conn, registry, 2, dict(publication_format=catalog.FORMAT_V2, sources=[receipt]))
        add_batch(conn, registry, 3, dict(publication_format=catalog.FORMAT, sources=[source(992)]), status="pending")
        baseline = catalog._source_records(conn, {("19x19", "99101")})
        assert baseline == {("19x19", "99101"): receipt}
        # Orphan original receipts remain visible; a registry-based shortcut
        # must never hide them from the later exact source/album guard.
        with pytest.raises(ValueError, match="published SGF differs"):
            catalog._check_source_receipts(conn, list(baseline.values()))
        conn.execute(
            text(
                """INSERT INTO kifu_name_batches
            (id,bundle_sha256,inventory_sha256,source_registry_id,status,reviewed_artifact)
            SELECT i,lpad(to_hex(i),64,'0'),repeat('0',64),:registry,'applied',
                   json_build_object('publication_format','unrelated-name-review',
                     'payload',repeat(md5(i::text),16384),
                     'sources',json_build_array(json_build_object('source_key','19x19','source_item_id','99101','album_id',-1)))
            FROM generate_series(100,1053) AS i"""
            ),
            dict(registry=registry),
        )
        conn.exec_driver_sql("ANALYZE kifu_name_batches")
    captured = []

    def capture(conn, cursor, statement, parameters, context, many):
        if "json_array_elements" in statement:
            captured.append((statement, deepcopy(parameters)))

    event.listen(engine, "before_cursor_execute", capture)
    try:
        with engine.connect() as conn:
            before_started = monotonic()
            before_timed_out = False
            try:
                assert catalog._source_records(conn, {("19x19", "99101")}) == baseline
            except DBAPIError as exc:
                assert exc.orig.pgcode == "57014"  # The unchanged five-second bound.
                before_timed_out = True
            before_ms = (monotonic() - before_started) * 1000
            count_sql, params = captured[0]
            unindexed = conn.exec_driver_sql("EXPLAIN (FORMAT JSON) " + count_sql, params).scalar_one()[0]["Plan"]
            assert not _plan_uses(unindexed, tool.INDEX_NAME)
            database = conn.exec_driver_sql("SELECT current_database()").scalar_one()
        result = tool.apply_index(engine, schema=schema, expected_database=database, analyze=True)
        assert result["state"] == "ready"
        captured.clear()
        with engine.connect() as conn:
            after_started = monotonic()
            assert catalog._source_records(conn, {("19x19", "99101")}) == baseline
            after_ms = (monotonic() - after_started) * 1000
            with pytest.raises(ValueError, match="published SGF differs"):
                catalog._check_source_receipts(conn, list(baseline.values()))
            assert captured[0] == (count_sql, params)
            conn.exec_driver_sql("SET LOCAL statement_timeout='5s'")
            explain = conn.exec_driver_sql("EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) " + count_sql, params).scalar_one()[
                0
            ]
            assert _plan_uses(explain["Plan"], tool.INDEX_NAME)
            assert explain["Execution Time"] < 5000 and after_ms < 5000
            for name, value in [("MAX_SCALAR_ROWS", 1), ("MAX_SCALAR_BYTES", 1)]:
                with monkeypatch.context() as scoped:
                    scoped.setattr(historical_ranks, name, value)
                    with pytest.raises(ValueError, match="receipt integrity resource limit"):
                        catalog._source_records(conn, {("19x19", "99101")})
        with engine.begin() as conn:
            add_batch(conn, registry, 4, dict(publication_format=catalog.FORMAT_V2, sources=[source(993)]))
            with pytest.raises(ValueError, match="conflicting committed source receipts"):
                catalog._source_records(conn, {("19x19", "99101")})
        print(
            dict(
                unrelated_rows=954,
                payload_bytes_per_row=524288,
                before_ms=round(before_ms, 2),
                before_timed_out=before_timed_out,
                indexed_lookup_ms=round(after_ms, 2),
                indexed_count_execution_ms=explain["Execution Time"],
            )
        )
    finally:
        event.remove(engine, "before_cursor_execute", capture)


@pytest.mark.parametrize(
    "definition",
    [
        "status",
        "status,(reviewed_artifact ->> '\"publication_format\"')",
        "status,(reviewed_artifact ->> 'publication_ format')",
        "status COLLATE \"C\",(reviewed_artifact ->> 'publication_format')",
        "status text_pattern_ops,(reviewed_artifact ->> 'publication_format')",
    ],
)
def test_foreign_definition_and_database_mismatch_never_mutate(pg, definition):
    tool = operator()
    engine, schema, _ = pg
    with engine.begin() as conn:
        database = conn.exec_driver_sql("SELECT current_database()").scalar_one()
        conn.exec_driver_sql(f"CREATE INDEX {tool.INDEX_NAME} ON kifu_name_batches({definition})")
    before = tool.check_index(engine, schema=schema)
    assert before["state"] == "mismatched"
    seen = []
    event.listen(engine, "before_cursor_execute", lambda conn, cursor, sql, *args: seen.append(sql))
    result = tool.apply_index(engine, schema=schema, expected_database=database, analyze=True)
    assert result["state"] == "refused" and result["index"]["oid"] == before["oid"]
    with pytest.raises(ValueError, match="database does not match"):
        tool.apply_index(engine, schema=schema, expected_database=database + "_wrong")
    assert not any(sql.lstrip().upper().startswith(("CREATE", "DROP", "ANALYZE", "ALTER")) for sql in seen)
    assert tool.check_index(engine, schema=schema) == before


def test_old_snapshot_timeout_reports_invalid_index_and_never_drops_it(pg):
    tool = operator()
    engine, schema, _ = pg
    seen = []
    event.listen(engine, "before_cursor_execute", lambda conn, cursor, sql, *args: seen.append(sql))
    with engine.connect().execution_options(isolation_level="REPEATABLE READ") as reader:
        database = reader.exec_driver_sql("SELECT current_database()").scalar_one()
        reader.exec_driver_sql("SELECT count(*) FROM kifu_name_batches").scalar_one()
        started = monotonic()
        result = tool.apply_index(
            engine, schema=schema, expected_database=database, timeout_ms=1500, lock_timeout_ms=200
        )
        assert monotonic() - started < 4
        assert result["state"] == "failed" and result["sqlstate"] in {"55P03", "57014"}
        assert result["index"]["state"] == "invalid" and result["index"]["oid"] is not None
        assert not result["index"]["valid"] and result["index"]["definition_matches"]
    oid = result["index"]["oid"]
    seen.clear()
    retry = tool.apply_index(engine, schema=schema, expected_database=database)
    assert retry["state"] == "refused" and retry["index"]["oid"] == oid
    assert not any(sql.lstrip().upper().startswith(("CREATE", "DROP", "ANALYZE", "ALTER")) for sql in seen)
