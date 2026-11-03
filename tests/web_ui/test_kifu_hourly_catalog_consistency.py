"""Finite hourly candidates preserve full-game evidence and honest ES timings."""

import logging
from copy import deepcopy

import pytest
from sqlalchemy import event, select, update

from katrain.web.core.models_db import KifuAlbum, KifuAlbumSource
from katrain.web.kifu import catalog_standardization as dedup, search_sync
from tests.web_ui.test_kifu_catalog_standardization import engine, sgf
from tests.web_ui.test_kifu_search_publication import ES


def test_finite_semantic_candidate_keeps_metadata_and_original_sources(engine):
    with engine.begin() as conn:
        conn.execute(update(KifuAlbum).where(KifuAlbum.id == 25055).values(event="Different source title"))
        manifest = dedup.prepare_dedup_manifest(conn, candidate_album_ids=[25055])
        assert manifest["groups"][0]["canonical_album_id"] == 140858
        originals = {m["album"]["id"]: m["album"]["sgf_content"] for m in manifest["groups"][0]["members"]}
        dedup.apply_dedup_manifest(conn, manifest, expected_sha256=dedup.dedup_manifest_sha256(manifest))
        assert dict(conn.execute(select(KifuAlbum.id, KifuAlbum.sgf_content)).all()) == originals
        assert (
            conn.scalar(
                select(KifuAlbumSource.album_id).where(
                    KifuAlbumSource.origin_path == "fixture/25055.sgf", KifuAlbumSource.match_method == "source_path"
                )
            )
            == 25055
        )


def test_finite_same_players_and_day_different_operations_stay_distinct(engine):
    with engine.begin() as conn:
        conn.execute(
            update(KifuAlbum).where(KifuAlbum.id == 25055).values(sgf_content=sgf().replace(";B[aa]", ";B[ss]"))
        )
        assert dedup.prepare_dedup_manifest(conn, candidate_album_ids=[25055])["groups"] == []


def test_finite_never_loads_unrelated_sgfs_or_source_links(engine):
    with engine.begin() as conn:
        conn.execute(
            KifuAlbum.__table__.insert().values(
                id=9,
                player_black="B",
                player_white="W",
                source_path="unrelated",
                sgf_content="invalid",
                date_played="2000-01-01",
            )
        )
    statements = []
    event.listen(engine, "before_cursor_execute", lambda c, cursor, sql, p, ctx, many: statements.append(sql))
    with engine.connect() as conn:
        assert dedup.prepare_dedup_manifest(conn, candidate_album_ids=[25055])["summary"]["albums_scanned"] == 2
    body_reads = [sql for sql in statements if "kifu_albums.sgf_content" in sql and "length(" not in sql.lower()]
    link_reads = [sql for sql in statements if "FROM kifu_album_sources" in sql]
    assert body_reads and all("WHERE" in sql for sql in body_reads)
    assert link_reads and all("WHERE" in sql for sql in link_reads)


@pytest.mark.parametrize("limit", ["MAX_BODY_ROWS", "MAX_SGF_BYTES", "MAX_BODY_BYTES"])
def test_finite_resource_overflow_defers_whole_cohort_before_body(engine, monkeypatch, limit):
    monkeypatch.setattr(dedup, limit, 1)
    statements = []
    event.listen(engine, "before_cursor_execute", lambda c, cursor, sql, p, ctx, many: statements.append(sql))
    with engine.connect() as conn:
        manifest = dedup.prepare_dedup_manifest(conn, candidate_album_ids=[25055])
    assert manifest["groups"] == []
    assert manifest["summary"]["resource_deferred_cohorts"] == 1
    assert manifest["excluded"][0]["reason"] == "resource_deferred"
    assert not [sql for sql in statements if "kifu_albums.sgf_content" in sql and "length(" not in sql.lower()]


def test_projection_logs_safe_stage_timings_and_keeps_pending_on_failure(monkeypatch, caplog):
    es = ES()
    ref = {"private": "token-secret", "source": "(;secret-sgf)"}
    es.state.update(status="pending", operation_type="catalog_publish", operation_ref=ref)
    token = search_sync.SyncToken(es, deepcopy(es.state), search_sync.ChangeScope(album_ids={1}))
    monkeypatch.setattr(search_sync, "_operation_scope", lambda *args: search_sync.ChangeScope())
    monkeypatch.setattr(search_sync, "_project_actions", lambda *args: [{"_op_type": "delete", "_id": "album:1"}])
    with caplog.at_level(logging.INFO, logger=search_sync.__name__):
        search_sync._apply_projection(None, token)
    records = [record for record in caplog.records if record.msg == "kifu_search_sync_stage %s"]
    assert [record.stage for record in records] == ["projection", "bulk", "refresh_ready"]
    assert all(record.action_count == 1 and record.elapsed_ms >= 0 for record in records)
    assert all(record.operation_ref_sha256 == search_sync.canonical_sha256(ref) for record in records)
    assert all('"elapsed_ms"' in record.getMessage() for record in records)
    assert all(
        "token-secret" not in str(record.__dict__) and "secret-sgf" not in str(record.__dict__) for record in records
    )
    assert token.state["operation_ref"] == ref
    es.fail_bulk = True
    es.state.update(status="pending", operation_type="catalog_publish", operation_ref=ref)
    with pytest.raises(RuntimeError), caplog.at_level(logging.INFO, logger=search_sync.__name__):
        search_sync._apply_projection(None, token)
    assert es.state["status"] == "pending"
    assert caplog.records[-1].stage == "bulk" and caplog.records[-1].outcome == "error"
