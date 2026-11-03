"""Finite hourly candidates preserve full-game evidence and honest ES timings."""

import logging
from copy import deepcopy
from hashlib import sha256

import pytest
from sqlalchemy import event, select, update
from sqlalchemy.orm import Session

from katrain.web.core.models_db import (
    KifuAlbum,
    KifuAlbumSource,
    KifuSource,
    KifuNameBatch,
    KifuDedupBatch,
    KifuDedupChange,
)
from katrain.web.kifu import catalog_standardization as dedup, search_sync
from tests.web_ui.test_kifu_catalog_standardization import engine, sgf
from tests.web_ui.test_kifu_search_publication import ES
from tests.web_ui.test_kifu_incremental_catalog import make_engine, manifest as native_manifest, publish


def hourly_game(source_id, *, comment="original", source_key="19x19"):
    value = native_manifest(str(source_id))
    game = value["games"][0]
    body = (
        sgf("AB[ss]", comment=comment)
        .replace("PB[Black]", "PB[Black Alias]")
        .replace("DT[1989-01-17]", "DT[2026-02-01]EV[Summer Cup]")
        .replace("RE[B+R]", "RE[B+]")
        .replace(";B[aa]", ";B[]")
    )
    game.update(
        source_key=source_key,
        sgf_content=body,
        sgf_sha256=sha256(body.encode()).hexdigest(),
        raw_sha256=sha256(body.encode()).hexdigest(),
    )
    return value


def test_hourly_publish_dedup_replay_and_atomic_child_first_undo(tmp_path, monkeypatch):
    from katrain.kifu_ingest import catalog

    engine = make_engine(tmp_path / "hourly.db")
    first, second = hourly_game(600), hourly_game(601, comment="source title differs")
    receipt1 = publish(engine, first)
    receipt2 = publish(engine, second)
    original_receipt = deepcopy(receipt2)
    duplicate, canonical = receipt2["games"][0]["album_id"], receipt1["games"][0]["album_id"]
    with engine.connect() as conn:
        assert conn.scalar(select(KifuAlbum.duplicate_of_id).where(KifuAlbum.id == duplicate)) == canonical
        artifact = conn.scalar(select(KifuNameBatch.reviewed_artifact).where(KifuNameBatch.id == receipt2["batch_id"]))
        assert artifact["catalog_repairs"]["dedup"]["batch_id"] > 0
        assert artifact["catalog_repairs"]["affected_album_ids"] == [canonical, duplicate]
    monkeypatch.setattr(
        dedup, "prepare_dedup_manifest", lambda *a, **kw: pytest.fail("replay must not reselect candidates")
    )
    assert publish(engine, second) == original_receipt
    assert publish(engine, first) == receipt1
    outcome = catalog.undo_publication(engine, receipt2["batch_id"])
    assert outcome["status"] == "undone"
    assert catalog.undo_publication(engine, receipt2["batch_id"]) == outcome
    with engine.connect() as conn:
        assert conn.scalar(select(KifuAlbum.id).where(KifuAlbum.id == duplicate)) is None
        assert (
            conn.scalar(select(KifuAlbum.sgf_content).where(KifuAlbum.id == canonical))
            == first["games"][0]["sgf_content"]
        )
        assert conn.scalar(select(KifuAlbum.result).where(KifuAlbum.id == canonical)) == "B+"
        assert search_sync._batch_scope(conn, receipt2["batch_id"]).album_ids >= {canonical, duplicate}


def test_hourly_compensated_archive_tampering_refuses_undo_replay_and_es_scope(tmp_path):
    from katrain.kifu_ingest import catalog

    engine = make_engine(tmp_path / "archive-drift.db")
    publish(engine, hourly_game(940))
    receipt = publish(engine, hourly_game(941, comment="different source"))
    catalog.undo_publication(engine, receipt["batch_id"])
    with engine.begin() as conn:
        row = conn.execute(select(KifuDedupBatch.__table__)).mappings().one()
        summary = deepcopy(row["summary"])
        archive = summary["compensated_journal"]
        assert search_sync.canonical_sha256(archive["changes"]) == archive["journal_sha256"]
        archive["changes"][0]["sgf_sha256_before"] = "0" * 64
        conn.execute(update(KifuDedupBatch).where(KifuDedupBatch.id == row["id"]).values(summary=summary))
    with pytest.raises(ValueError, match="journal changed"):
        catalog.undo_publication(engine, receipt["batch_id"])
    with engine.connect() as conn, pytest.raises(search_sync.SearchIndexPending, match="dedup child changed"):
        search_sync._batch_scope(conn, receipt["batch_id"])


def test_hourly_compensation_archive_failure_rolls_back_child_and_parent(tmp_path, monkeypatch):
    from katrain.kifu_ingest import catalog

    engine = make_engine(tmp_path / "archive-rollback.db")
    publish(engine, hourly_game(950))
    receipt = publish(engine, hourly_game(951, comment="different source"))
    original = catalog._archive_compensated_dedup

    def crash(conn, repairs):
        original(conn, repairs)
        raise RuntimeError("crash after archive")

    monkeypatch.setattr(catalog, "_archive_compensated_dedup", crash)
    with pytest.raises(RuntimeError, match="crash after archive"):
        catalog.undo_publication(engine, receipt["batch_id"])
    with engine.connect() as conn:
        assert conn.scalar(select(KifuDedupBatch.status)) == "complete"
        assert "compensated_journal" not in conn.scalar(select(KifuDedupBatch.summary))
        assert len(conn.scalars(select(KifuDedupChange.id)).all()) == 2
        assert (
            conn.scalar(select(KifuAlbum.duplicate_of_id).where(KifuAlbum.id == receipt["games"][0]["album_id"]))
            is not None
        )


def test_ordinary_hourly_publish_never_parses_unrelated_library(tmp_path, monkeypatch):
    from katrain.kifu_ingest import catalog

    engine = make_engine(tmp_path / "bounded.db")
    monkeypatch.setattr(
        catalog, "_cached_canonical_sha", lambda *a, **kw: pytest.fail("ordinary publish warmed the library")
    )
    assert publish(engine, hourly_game(700))["status"] == "applied"


def test_native_rank_exact_and_semantic_share_one_cumulative_body_budget(tmp_path, monkeypatch):
    from katrain.kifu_ingest import ranks
    from katrain.web.kifu import historical_ranks
    from tests.web_ui.test_kifu_historical_rank_native import seed_prior, WHEN

    engine = make_engine(tmp_path / "shared-budget.db")
    seed_prior(engine)

    def named_game(item, comment):
        result = hourly_game(item, comment=comment)
        game = result["games"][0]
        game["sgf_content"] = game["sgf_content"].replace("PW[White]", "PW[White Alias]")
        game["sgf_sha256"] = game["raw_sha256"] = sha256(game["sgf_content"].encode()).hexdigest()
        game["metadata"]["player_white"] = "White Alias"
        return result

    existing = publish(engine, named_game(970, "existing semantic game"))
    value = named_game(971, "incoming semantic game")
    game = value["games"][0]
    game["origin_path"] = "data/kifu-album/19x19/971.sgf"
    game["identities"] = {"black": {"canonical_name": "Black"}, "white": {"canonical_name": "White"}}
    with engine.connect() as conn:
        frozen = ranks.freeze_historical_game_ranks(conn, [game], matched_at=WHEN)[0]
        basis = conn.scalar(select(KifuAlbum.sgf_content).where(KifuAlbum.id == 12))
        old_body = conn.scalar(select(KifuAlbum.sgf_content).where(KifuAlbum.id == existing["games"][0]["album_id"]))
    game.update({key: frozen[key] for key in ("rank_snapshots", "rank_observations")})
    value.update(format=ranks.FORMAT_V2, rank_facts=frozen["rank_facts"])
    assert game["rank_snapshots"]["black"]["origin"] == "historical_prior"
    resources = []
    original = historical_ranks.EvidenceBudget
    cap = len(game["sgf_content"].encode()) + len(basis.encode()) + len(old_body.encode()) - 1

    def bounded_resource():
        resource = original(max_bytes=cap)
        resources.append(resource)
        return resource

    monkeypatch.setattr(historical_ranks, "EvidenceBudget", bounded_resource)
    receipt = publish(engine, value)
    assert len(resources) == 1
    assert resources[0].used_bytes == len(game["sgf_content"].encode()) + len(basis.encode())
    with engine.connect() as conn:
        artifact = conn.scalar(select(KifuNameBatch.reviewed_artifact).where(KifuNameBatch.id == receipt["batch_id"]))
        assert artifact["catalog_repairs"]["dedup"]["manifest"]["summary"]["resource_deferred_cohorts"] == 1
        assert (
            conn.scalar(select(KifuAlbum.duplicate_of_id).where(KifuAlbum.id == receipt["games"][0]["album_id"]))
            is None
        )


def test_hourly_es_failure_recovers_original_pending_and_child_scope(tmp_path, monkeypatch):
    engine = make_engine(tmp_path / "es-hourly.db")
    first, second = hourly_game(800), hourly_game(801, comment="other source")
    receipt1 = publish(engine, first)
    es, scopes = ES(), []
    monkeypatch.setenv("KIFU_SEARCH_SYNC_MODE", "enabled")
    monkeypatch.setenv("KIFU_SEARCH_BACKEND", "elasticsearch")
    monkeypatch.delenv("KIFU_STRICT_NAMES", raising=False)
    monkeypatch.setattr(search_sync, "_writer_client", lambda: es)

    def actions(conn, scope):
        scopes.append(set(scope.album_ids))
        return [{"_op_type": "delete", "_id": f"album:{album_id}"} for album_id in sorted(scope.album_ids)]

    monkeypatch.setattr(search_sync, "_project_actions", actions)
    es.fail_bulk = True
    with pytest.raises(search_sync.SearchIndexPending):
        publish(engine, second)
    pending = deepcopy(es.state["operation_ref"])
    with engine.connect() as conn:
        artifact = conn.scalar(
            select(KifuNameBatch.reviewed_artifact).where(
                KifuNameBatch.bundle_sha256 == search_sync.canonical_sha256(second)
            )
        )
    receipt2 = deepcopy(artifact["receipt"])
    assert es.state["status"] == "pending"
    assert es.state["operation_ref"] == pending
    assert scopes[-1] >= {receipt1["games"][0]["album_id"], receipt2["games"][0]["album_id"]}
    es.fail_bulk = False
    assert publish(engine, second) == receipt2
    assert es.state["status"] == "ready"
    assert publish(engine, first) == receipt1


def test_hourly_api_preserves_ff4_full_operations_result_and_attribution(tmp_path):
    from katrain.web.api.v1.endpoints.kifu import read_album_detail_legacy
    from katrain.core.sgf_parser import SGF

    engine = make_engine(tmp_path / "api-hourly.db")
    value = hourly_game(900)
    receipt = publish(engine, value)
    with Session(engine) as db:
        detail = read_album_detail_legacy(db, receipt["games"][0]["album_id"], lang="cn")
    assert detail.sgf_content == value["games"][0]["sgf_content"]
    assert SGF.parse_sgf(detail.sgf_content).get_property("FF") == "4"
    assert dedup.full_operation_fingerprint(detail.sgf_content) == dedup.full_operation_fingerprint(
        value["games"][0]["sgf_content"]
    )
    assert detail.result == "B+"
    assert "19x19" in detail.sources


@pytest.mark.parametrize("drift", ["manifest", "journal", "membership", "parent_afterimage"])
def test_hourly_undo_rejects_drift_before_child_compensation(tmp_path, monkeypatch, drift):
    from katrain.kifu_ingest import catalog

    engine = make_engine(tmp_path / "undo-drift.db")
    publish(engine, hourly_game(920))
    receipt = publish(engine, hourly_game(921, comment="different source"))
    duplicate = receipt["games"][0]["album_id"]
    with engine.begin() as conn:
        artifact = deepcopy(
            conn.scalar(select(KifuNameBatch.reviewed_artifact).where(KifuNameBatch.id == receipt["batch_id"]))
        )
        if drift == "manifest":
            artifact["catalog_repairs"]["dedup"]["manifest"]["groups"][0]["operation_sha256"] = "0" * 64
        elif drift == "membership":
            artifact["catalog_repairs"]["affected_album_ids"] = [duplicate]
        elif drift == "journal":
            conn.execute(
                update(KifuDedupChange)
                .where(KifuDedupChange.batch_id == artifact["catalog_repairs"]["dedup"]["batch_id"])
                .values(sgf_sha256_before="0" * 64)
            )
        else:
            conn.execute(update(KifuAlbum).where(KifuAlbum.id == duplicate).values(event="later drift"))
        conn.execute(
            update(KifuNameBatch).where(KifuNameBatch.id == receipt["batch_id"]).values(reviewed_artifact=artifact)
        )
    monkeypatch.setattr(dedup, "undo_dedup_manifest", lambda *a, **kw: pytest.fail("child wrote before all guards"))
    with pytest.raises(ValueError):
        catalog.undo_publication(engine, receipt["batch_id"])
    with engine.connect() as conn:
        assert conn.scalar(select(KifuNameBatch.status).where(KifuNameBatch.id == receipt["batch_id"])) == "applied"
        assert conn.scalar(select(KifuAlbum.duplicate_of_id).where(KifuAlbum.id == duplicate)) is not None


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


def test_finite_never_retargets_an_existing_canonical_chain(engine):
    with engine.begin() as conn:
        conn.execute(update(KifuAlbumSource).values(source_id=1))
        original = dedup.prepare_dedup_manifest(conn)
        dedup.apply_dedup_manifest(conn, original, expected_sha256=dedup.dedup_manifest_sha256(original))
        row = dict(conn.execute(select(KifuAlbum.__table__).where(KifuAlbum.id == 25055)).mappings().one())
        row.update(id=200000, source_path="fixture/new-canonical.sgf", sgf_content=sgf(comment="new-canonical"))
        row.pop("created_at")
        conn.execute(KifuAlbum.__table__.insert().values(**row))
        conn.execute(
            KifuAlbumSource.__table__.insert().values(
                album_id=200000, source_id=2, origin_path=row["source_path"], match_method="source_path"
            )
        )
        assert dedup.prepare_dedup_manifest(conn, candidate_album_ids=[200000])["groups"] == []
        assert dedup.verified_display_duplicate(conn, 140858)["canonical_album_id"] == 25055


def test_finite_manifest_source_registry_scope_survives_unrelated_source(engine):
    with engine.begin() as conn:
        manifest = dedup.prepare_dedup_manifest(conn, candidate_album_ids=[25055])
        digest = dedup.dedup_manifest_sha256(manifest)
        dedup.apply_dedup_manifest(conn, manifest, expected_sha256=digest)
        conn.execute(KifuSource.__table__.insert().values(source_key="unrelated-later"))
        assert dedup.apply_dedup_manifest(conn, manifest, expected_sha256=digest)["idempotent"]


def test_proved_exact_original_reuses_provided_body_without_second_reservation(engine):
    from katrain.kifu_ingest import catalog
    from katrain.web.kifu.historical_ranks import EvidenceBudget

    body = catalog._canonical_sgf(sgf(comment="25055"))
    resource = EvidenceBudget(max_bytes=len(body.encode()))
    resource.remember_body(body)
    game = {
        "source_key": "19x19",
        "source_item_id": "991",
        "sgf_content": body,
        "sgf_sha256": sha256(body.encode()).hexdigest(),
        "metadata": {"player_black": "Black", "player_white": "White", "date_played": "1989-01-17"},
    }
    with engine.begin() as conn:
        conn.execute(update(KifuAlbum).where(KifuAlbum.id == 25055).values(sgf_content=body))
        matches = catalog._bounded_exact_matches(conn, game, body, {25055}, resource, [])
        assert matches == {25055}
        assert resource.used_bytes == len(body.encode())


def test_finite_legacy_null_fk_uses_identity_evidence_not_a_guess(engine):
    with engine.begin() as conn:
        conn.execute(update(KifuAlbum).where(KifuAlbum.id == 25055).values(black_player_id=None))
        assert (
            dedup.prepare_dedup_manifest(conn, candidate_album_ids=[140858])["groups"][0]["canonical_album_id"]
            == 140858
        )
        conn.execute(
            update(KifuAlbum)
            .where(KifuAlbum.id == 25055)
            .values(player_black="Unresolved", sgf_content=sgf().replace("PB[Black]", "PB[Unresolved]"))
        )
        assert dedup.prepare_dedup_manifest(conn, candidate_album_ids=[140858])["groups"] == []


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
