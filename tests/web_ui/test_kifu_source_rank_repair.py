"""Frozen full-corpus rank manifests use guarded reversible journals."""

from copy import deepcopy
import pytest
from sqlalchemy import create_engine, select, update
from katrain.web.core import models_db as m


@pytest.fixture
def conn():
    engine = create_engine("sqlite:///:memory:")
    m.Base.metadata.create_all(engine)
    with engine.begin() as conn:
        for name in ("Black", "White"):
            conn.execute(m.KifuPlayer.__table__.insert().values(canonical_name=name))
        conn.execute(m.KifuSource.__table__.insert(), [dict(id=1, source_key="CWI"), dict(id=2, source_key="19x19")])
        for i, family, path, rank in [
            (1, 1, "Go_Seigen/1989-01-17.sgf", "7d"),
            (2, 2, "19x19/123.sgf", "7p"),
            (3, 1, "CWI_Jowa/nested/1830.SGF", "6d"),
        ]:
            conn.execute(
                m.KifuAlbum.__table__.insert().values(
                    id=i,
                    player_black="Black",
                    player_white="White",
                    black_player_id=1,
                    white_player_id=2,
                    black_rank=rank,
                    white_rank="9p",
                    date_played="1989-01-17",
                    date_sort="1989-01-17",
                    source_path="data/kifu-album/" + path,
                    sgf_content=f"(;SZ[19]PB[Black]PW[White]BR[{rank}]WR[9p]DT[1989-01-17];B[aa];W[bb])",
                )
            )
            conn.execute(
                m.KifuAlbumSource.__table__.insert().values(
                    album_id=i, source_id=family, origin_path="data/kifu-album/" + path, match_method="source_path"
                )
            )
        yield conn
    engine.dispose()


def test_whole_corpus_manifest_apply_retry_undo_preserve_raw(conn):
    from katrain.web.kifu.source_rank_repair import (
        prepare_rank_manifest,
        apply_rank_manifest,
        undo_rank_manifest,
        rank_manifest_sha256,
    )

    original = [dict(x) for x in conn.execute(select(m.KifuAlbum.__table__)).mappings()]
    manifest = prepare_rank_manifest(conn)
    assert manifest["census"]["albums"] == 3 and manifest["census"]["slots"] == 6
    assert len(manifest["changes"]) == 2
    digest = rank_manifest_sha256(manifest)
    assert apply_rank_manifest(conn, manifest, expected_sha256=digest)["status"] == "applied"
    assert apply_rank_manifest(conn, manifest, expected_sha256=digest)["status"] == "already_applied"
    assert [dict(x) for x in conn.execute(select(m.KifuAlbum.__table__)).mappings()] == original
    rows = list(conn.execute(select(m.KifuAlbumRankSnapshot.__table__)).mappings())
    assert len(rows) == 2 and all(x["rank_fact_id"] is None and x["native_batch_id"] > 0 for x in rows)
    assert undo_rank_manifest(conn, manifest, expected_sha256=digest)["status"] == "undone"
    assert undo_rank_manifest(conn, manifest, expected_sha256=digest)["status"] == "already_undone"
    assert not list(conn.execute(select(m.KifuAlbumRankSnapshot.id)))


def test_frozen_preimage_drift_refuses_without_partial_write(conn):
    from katrain.web.kifu.source_rank_repair import prepare_rank_manifest, apply_rank_manifest, rank_manifest_sha256

    manifest = prepare_rank_manifest(conn)
    conn.execute(update(m.KifuAlbumSource).where(m.KifuAlbumSource.album_id == 3).values(origin_path="changed"))
    with pytest.raises(ValueError, match="preimage"):
        apply_rank_manifest(conn, manifest, expected_sha256=rank_manifest_sha256(manifest))
    assert not list(conn.execute(select(m.KifuAlbumRankSnapshot.id)))
    assert not list(conn.execute(select(m.KifuNameBatch.id)))


def test_existing_snapshot_untouched_and_undo_refuses_later_edit(conn):
    from katrain.web.kifu.source_rank_repair import (
        prepare_rank_manifest,
        apply_rank_manifest,
        undo_rank_manifest,
        rank_manifest_sha256,
    )

    conn.execute(
        m.KifuAlbumRankSnapshot.__table__.insert().values(
            album_id=1,
            side="white",
            snapshot={"old": "v1"},
            snapshot_sha256="a" * 64,
            native_batch_id=17,
            publication_key="existing",
        )
    )
    manifest = prepare_rank_manifest(conn)
    assert manifest["census"]["existing_snapshot_slots"] == 1
    digest = rank_manifest_sha256(manifest)
    apply_rank_manifest(conn, manifest, expected_sha256=digest)
    assert conn.execute(
        select(m.KifuAlbumRankSnapshot.snapshot).where(m.KifuAlbumRankSnapshot.publication_key == "existing")
    ).scalar_one() == {"old": "v1"}
    conn.execute(
        update(m.KifuAlbumRankSnapshot).where(m.KifuAlbumRankSnapshot.album_id == 3).values(publication_key="later")
    )
    with pytest.raises(ValueError, match="journal|changed"):
        undo_rank_manifest(conn, manifest, expected_sha256=digest)
    assert len(list(conn.execute(select(m.KifuAlbumRankSnapshot.id)))) == 3


def test_api_prefers_valid_overlay_and_invalid_falls_back_honestly(conn):
    from types import SimpleNamespace
    from katrain.web.kifu.source_rank_repair import prepare_rank_manifest, apply_rank_manifest, rank_manifest_sha256
    from katrain.web.kifu.player_ranks import lookup_album_rank_snapshots
    from katrain.web.kifu.name_parse import parse_player
    from katrain.web.api.v1.endpoints.kifu import _rank_displays

    manifest = prepare_rank_manifest(conn)
    apply_rank_manifest(conn, manifest, expected_sha256=rank_manifest_sha256(manifest))
    record = SimpleNamespace(
        **dict(conn.execute(select(m.KifuAlbum.__table__).where(m.KifuAlbum.id == 1)).mappings().one())
    )
    parsed = parse_player(record.player_black, record.black_rank)
    snapshots = lookup_album_rank_snapshots(conn, [record.id])
    value = _rank_displays(record, parsed, parse_player(record.player_white, record.white_rank), snapshots)
    assert (
        value["display_black_rank"] == "7p" and value["black_rank_source"]["policy_version"] == "trusted-source-rank-v2"
    )
    row = snapshots[(record.id, "black")]
    row["snapshot"] = {**row["snapshot"], "display_rank": "8p"}
    value = _rank_displays(record, parsed, parse_player(record.player_white, record.white_rank), snapshots)
    assert value["display_black_rank"] == "7段" and value["black_rank_source"] is None


@pytest.mark.parametrize("damage", ["date", "identity", "grade", "source", "operation"])
def test_counterpart_refinement_requires_all_historical_bindings(conn, damage):
    from katrain.web.kifu.source_rank_repair import prepare_rank_manifest

    values = {
        "date": {"date_played": "1989-01-18"},
        "identity": {"black_player_id": 2},
        "grade": {"black_rank": "8p"},
        "operation": {"sgf_content": "(;SZ[19];B[ab];W[bb])"},
    }
    if damage == "source":
        conn.execute(update(m.KifuAlbumSource).where(m.KifuAlbumSource.album_id == 2).values(origin_path="forged"))
    else:
        conn.execute(update(m.KifuAlbum).where(m.KifuAlbum.id == 2).values(**values[damage]))
    manifest = prepare_rank_manifest(conn)
    slot = next(x for x in manifest["changes"] if x["album_id"] == 1)
    assert slot["snapshot_after"]["display_rank"] == "7段"
    assert slot["counterpart_before"] is None


def test_rank_manifest_tamper_and_counterpart_preimage_drift_refuse(conn):
    from katrain.web.kifu.source_rank_repair import prepare_rank_manifest, apply_rank_manifest, rank_manifest_sha256

    manifest = prepare_rank_manifest(conn)
    assert manifest["census"]["professional_refinements"] == 1
    conn.execute(update(m.KifuAlbum).where(m.KifuAlbum.id == 2).values(black_rank="8p"))
    with pytest.raises(ValueError, match="counterpart preimage"):
        apply_rank_manifest(conn, manifest, expected_sha256=rank_manifest_sha256(manifest))
    assert not list(conn.execute(select(m.KifuNameBatch.id)))


@pytest.mark.parametrize("damage", ["sgf_rank", "sgf_date", "variation"])
def test_sgf_evidence_not_only_mutable_metadata_must_agree(conn, damage):
    from katrain.web.kifu.source_rank_repair import prepare_rank_manifest

    sgf = conn.execute(select(m.KifuAlbum.sgf_content).where(m.KifuAlbum.id == 2)).scalar_one()
    if damage == "sgf_rank":
        sgf = sgf.replace("BR[7p]", "BR[8p]")
    elif damage == "sgf_date":
        sgf = sgf.replace("DT[1989-01-17]", "DT[1989-01-18]")
    else:
        sgf = "(;SZ[19]BR[7p]WR[9p]DT[1989-01-17];B[aa](;W[bb])(;W[cc]))"
    conn.execute(update(m.KifuAlbum).where(m.KifuAlbum.id == 2).values(sgf_content=sgf))
    slot = next(x for x in prepare_rank_manifest(conn)["changes"] if x["album_id"] == 1)
    assert slot["snapshot_after"]["display_rank"] == "7段"


def test_disposable_postgresql_rank_transaction_and_source_lock(monkeypatch):
    """Opt-in integration test, always inside a fresh schema in the disposable DB."""
    import os
    import uuid
    from sqlalchemy import text
    from sqlalchemy.exc import DBAPIError

    url = os.environ.get("KIFU_RANK_TEST_POSTGRES")
    if not url:
        pytest.skip("set KIFU_RANK_TEST_POSTGRES to a disposable PostgreSQL database")
    from katrain.web.kifu.source_rank_repair import (
        prepare_rank_manifest,
        apply_rank_manifest,
        undo_rank_manifest,
        rank_manifest_sha256,
    )

    schema = "rank_repair_test_" + uuid.uuid4().hex
    engine = create_engine(url)
    with engine.begin() as admin:
        admin.exec_driver_sql("CREATE SCHEMA " + schema)
    try:
        with engine.connect() as first, engine.connect() as second:
            first.exec_driver_sql("SET search_path TO " + schema)
            second.exec_driver_sql("SET search_path TO " + schema)
            m.Base.metadata.create_all(first)
            first.commit()
            second.commit()
            first.execute(
                m.KifuPlayer.__table__.insert(),
                [dict(id=1, canonical_name="Black"), dict(id=2, canonical_name="White")],
            )
            first.execute(
                m.KifuSource.__table__.insert(), [dict(id=1, source_key="CWI"), dict(id=2, source_key="19x19")]
            )
            first.execute(
                m.KifuAlbum.__table__.insert().values(
                    id=1,
                    player_black="Black",
                    player_white="White",
                    black_rank="7d",
                    white_rank="9p",
                    black_player_id=1,
                    white_player_id=2,
                    date_played="1989-01-17",
                    source_path="data/kifu-album/Go_Seigen/1989.sgf",
                    sgf_content="(;PB[Black]PW[White]BR[7d]WR[9p]DT[1989-01-17];B[aa])",
                )
            )
            first.execute(
                m.KifuAlbumSource.__table__.insert().values(
                    album_id=1,
                    source_id=1,
                    origin_path="data/kifu-album/Go_Seigen/1989.sgf",
                    match_method="source_path",
                )
            )
            first.execute(
                m.KifuAlbum.__table__.insert().values(
                    id=2,
                    player_black="Black",
                    player_white="White",
                    black_player_id=1,
                    white_player_id=2,
                    black_rank="7p",
                    white_rank="9p",
                    date_played="1989-01-17",
                    source_path="data/kifu-album/19x19/123.sgf",
                    sgf_content="(;PB[Black]PW[White]BR[7p]WR[9p]DT[1989-01-17];B[aa])",
                )
            )
            first.execute(
                m.KifuAlbumSource.__table__.insert().values(
                    album_id=2, source_id=2, origin_path="data/kifu-album/19x19/123.sgf", match_method="source_path"
                )
            )
            first.commit()
            manifest = prepare_rank_manifest(first)
            assert len(manifest["historical_cohorts"]) == 1
            manifest_sha = rank_manifest_sha256(manifest)
            apply_rank_manifest(first, manifest, expected_sha256=manifest_sha)
            second.exec_driver_sql("SET LOCAL lock_timeout = '150ms'")
            # Row locks alone do not block a new source-authorized competing album.
            with pytest.raises(DBAPIError):
                second.execute(
                    m.KifuAlbum.__table__.insert().values(
                        id=3,
                        player_black="Black",
                        player_white="White",
                        black_player_id=1,
                        white_player_id=2,
                        black_rank="7d",
                        white_rank="9p",
                        date_played="1989-01-17",
                        source_path="data/kifu-album/19x19/124.sgf",
                        sgf_content="(;BR[7d]WR[9p]DT[1989-01-17];B[aa])",
                    )
                )
            second.rollback()
            second.exec_driver_sql("SET LOCAL lock_timeout = '150ms'")
            with pytest.raises(DBAPIError):
                second.execute(
                    update(m.KifuAlbumSource).where(m.KifuAlbumSource.album_id == 1).values(origin_path="concurrent")
                )
            second.rollback()
            second.exec_driver_sql("SET LOCAL lock_timeout = '150ms'")
            with pytest.raises(DBAPIError):
                second.execute(
                    m.KifuPlayerAlias.__table__.insert().values(player_id=2, alias="Black", normalized_alias="black")
                )
            second.rollback()
            first.commit()
            assert apply_rank_manifest(second, manifest, expected_sha256=manifest_sha)["status"] == "already_applied"
            second.commit()
            assert undo_rank_manifest(second, manifest, expected_sha256=manifest_sha)["status"] == "undone"
            second.commit()
            assert second.scalar(select(m.KifuAlbum.black_rank).where(m.KifuAlbum.id == 1)) == "7d"
            assert not list(second.execute(select(m.KifuAlbumRankSnapshot.id)))
            second.rollback()
    finally:
        with engine.begin() as admin:
            admin.exec_driver_sql("DROP SCHEMA " + schema + " CASCADE")
        engine.dispose()


@pytest.mark.parametrize("damage", ["batch", "publication", "journal", "row_hash", "source_link"])
def test_invalid_audit_or_source_binding_uses_unspecified_fallback(conn, damage):
    from types import SimpleNamespace
    from katrain.web.kifu.source_rank_repair import prepare_rank_manifest, apply_rank_manifest, rank_manifest_sha256
    from katrain.web.kifu.player_ranks import lookup_album_rank_snapshots
    from katrain.web.kifu.name_parse import parse_player
    from katrain.web.api.v1.endpoints.kifu import _rank_displays

    manifest = prepare_rank_manifest(conn)
    apply_rank_manifest(conn, manifest, expected_sha256=rank_manifest_sha256(manifest))
    record = SimpleNamespace(
        **dict(conn.execute(select(m.KifuAlbum.__table__).where(m.KifuAlbum.id == 1)).mappings().one())
    )
    snapshots = lookup_album_rank_snapshots(conn, [1])
    row = snapshots[(1, "black")]
    if damage == "batch":
        row["_batch_status"] = "pending"
    elif damage == "publication":
        row["publication_key"] = "arbitrary-sentinel"
    elif damage == "journal":
        row["_journal_after"] = None
    elif damage == "row_hash":
        row["snapshot_sha256"] = "0" * 64
    else:
        snapshots[(1, "sources")][0]["source_id"] = 1000
    result = _rank_displays(
        record,
        parse_player(record.player_black, record.black_rank),
        parse_player(record.player_white, record.white_rank),
        snapshots,
    )
    assert result["display_black_rank"] == "7段" and result["black_rank_source"] is None


def test_conflicting_typed_amateur_counterpart_refuses_pro_refinement(conn):
    from katrain.web.kifu.source_rank_repair import prepare_rank_manifest

    original = dict(conn.execute(select(m.KifuAlbum.__table__).where(m.KifuAlbum.id == 2)).mappings().one())
    original.pop("created_at")
    original.update(
        id=4,
        source_path="data/kifu-album/19x19/124.sgf",
        black_rank="7d",
        white_rank="9d",
        sgf_content=original["sgf_content"].replace("BR[7p]", "BR[7d]").replace("WR[9p]", "WR[9d]"),
    )
    conn.execute(m.KifuAlbum.__table__.insert().values(**original))
    conn.execute(
        m.KifuAlbumSource.__table__.insert().values(
            album_id=4, source_id=2, origin_path=original["source_path"], match_method="source_path"
        )
    )
    slot = next(x for x in prepare_rank_manifest(conn)["changes"] if x["album_id"] == 1)
    assert slot["snapshot_after"]["display_rank"] == "7段"


def test_reviewed_yoda_target_records_historical_official_evidence_without_profile_grade(conn):
    from katrain.web.kifu.source_rank_repair import prepare_rank_manifest, apply_rank_manifest, rank_manifest_sha256

    conn.execute(update(m.KifuPlayer).where(m.KifuPlayer.id == 1).values(canonical_name="依田纪基"))
    conn.execute(update(m.KifuPlayer).where(m.KifuPlayer.id == 2).values(canonical_name="吴清源"))
    conn.execute(
        update(m.KifuAlbum)
        .where(m.KifuAlbum.id == 1)
        .values(
            player_black="Yoda Norimoto",
            player_white="Go Seigen",
            black_player_id=None,
            white_rank="9d",
            sgf_content="(;SZ[19]PB[Yoda Norimoto]PW[Go Seigen]BR[7d]WR[9d]DT[1989-01-17];B[aa];W[bb])",
        )
    )
    path = "data/kifu-album/19x19/41563564.sgf"
    conn.execute(
        update(m.KifuAlbum)
        .where(m.KifuAlbum.id == 2)
        .values(
            source_path=path,
            player_black="依田纪基",
            player_white="吴清源",
            sgf_content="(;SZ[19]PB[依田纪基]PW[吴清源]BR[7p]WR[9p]DT[1989-01-17];B[aa];W[bb])",
        )
    )
    conn.execute(update(m.KifuAlbumSource).where(m.KifuAlbumSource.album_id == 2).values(origin_path=path))
    manifest = prepare_rank_manifest(conn)
    target = [x["snapshot_after"] for x in manifest["changes"] if x["album_id"] == 1]
    assert [x["display_rank"] for x in target] == ["7p", "9p"]
    assert manifest["census"]["reviewed_target_slots"] == 2
    proof = target[0]["evidence"]["reviewed_identity"]["historical_official"]
    assert [(x["grade"], x["valid_from"]) for x in proof] == [("7p", "1987"), ("9p", "1950")]
    assert target[0]["player_id"] is None
    apply_rank_manifest(conn, manifest, expected_sha256=rank_manifest_sha256(manifest))
    assert conn.scalar(select(m.KifuAlbum.black_player_id).where(m.KifuAlbum.id == 1)) is None


def _add_competing_counterpart(conn, *, album_id=4, rank="7d"):
    original = dict(conn.execute(select(m.KifuAlbum.__table__).where(m.KifuAlbum.id == 2)).mappings().one())
    original.pop("created_at")
    original.update(
        id=album_id,
        source_path=f"data/kifu-album/19x19/competitor-{album_id}.sgf",
        black_rank=rank,
        sgf_content=original["sgf_content"].replace("BR[7p]", f"BR[{rank}]"),
    )
    conn.execute(m.KifuAlbum.__table__.insert().values(**original))
    conn.execute(
        m.KifuAlbumSource.__table__.insert().values(
            album_id=album_id, source_id=2, origin_path=original["source_path"], match_method="source_path"
        )
    )


def test_new_conflicting_counterpart_refuses_entire_frozen_rank_batch(conn):
    from katrain.web.kifu.source_rank_repair import prepare_rank_manifest, apply_rank_manifest, rank_manifest_sha256

    manifest = prepare_rank_manifest(conn)
    slot = next(c for c in manifest["changes"] if c["album_id"] == 1)
    assert slot["snapshot_after"]["display_rank"] == "7p"
    _add_competing_counterpart(conn)
    fresh = prepare_rank_manifest(conn)
    assert next(c for c in fresh["changes"] if c["album_id"] == 1)["snapshot_after"]["display_rank"] == "7段"
    with pytest.raises(ValueError, match="cohort"):
        apply_rank_manifest(conn, manifest, expected_sha256=rank_manifest_sha256(manifest))
    assert not list(conn.execute(select(m.KifuNameBatch.id)))
    assert not list(conn.execute(select(m.KifuAlbumRankSnapshot.id)))


def test_applied_frozen_rank_ignores_later_new_counterpart_and_profiles(conn):
    from katrain.web.kifu.source_rank_repair import prepare_rank_manifest, apply_rank_manifest, rank_manifest_sha256

    manifest = prepare_rank_manifest(conn)
    digest = rank_manifest_sha256(manifest)
    apply_rank_manifest(conn, manifest, expected_sha256=digest)
    _add_competing_counterpart(conn)
    assert apply_rank_manifest(conn, manifest, expected_sha256=digest)["status"] == "already_applied"
    row = conn.execute(
        select(m.KifuAlbumRankSnapshot.snapshot).where(m.KifuAlbumRankSnapshot.album_id == 1)
    ).scalar_one()
    assert row["display_rank"] == "7p"


@pytest.mark.parametrize("damage", ["nonselected_grade", "new_trusted_source", "new_matching_professional"])
def test_frozen_professional_cohort_pins_all_members_and_source_absence(conn, damage):
    from sqlalchemy import delete
    from katrain.web.kifu.source_rank_repair import prepare_rank_manifest, apply_rank_manifest, rank_manifest_sha256

    if damage != "new_matching_professional":
        _add_competing_counterpart(conn, rank="7p" if damage == "nonselected_grade" else "7d")
        if damage == "new_trusted_source":
            conn.execute(delete(m.KifuAlbumSource).where(m.KifuAlbumSource.album_id == 4))
    manifest = prepare_rank_manifest(conn)
    assert next(c for c in manifest["changes"] if c["album_id"] == 1)["snapshot_after"]["display_rank"] == "7p"
    if damage == "nonselected_grade":
        conn.execute(update(m.KifuAlbum).where(m.KifuAlbum.id == 4).values(black_rank="7d"))
    elif damage == "new_trusted_source":
        path = conn.scalar(select(m.KifuAlbum.source_path).where(m.KifuAlbum.id == 4))
        conn.execute(
            m.KifuAlbumSource.__table__.insert().values(
                album_id=4, source_id=2, origin_path=path, match_method="source_path"
            )
        )
    else:
        _add_competing_counterpart(conn, rank="7p")
    with pytest.raises(ValueError, match="cohort"):
        apply_rank_manifest(conn, manifest, expected_sha256=rank_manifest_sha256(manifest))
    assert not list(conn.execute(select(m.KifuNameBatch.id)))
    assert not list(conn.execute(select(m.KifuAlbumRankSnapshot.id)))


def test_unfrozen_old_manifest_refuses_before_any_batch_write(conn):
    from katrain.web.kifu.source_rank_repair import prepare_rank_manifest, apply_rank_manifest, rank_manifest_sha256

    old_manifest = prepare_rank_manifest(conn)
    del old_manifest["historical_cohorts"]
    with pytest.raises(ValueError, match="manifest shape"):
        apply_rank_manifest(conn, old_manifest, expected_sha256=rank_manifest_sha256(old_manifest))
    assert not list(conn.execute(select(m.KifuNameBatch.id)))
    assert not list(conn.execute(select(m.KifuAlbumRankSnapshot.id)))


@pytest.mark.parametrize("album_id,raw_name", [(1, "White"), (2, "White"), (2, "Unindexed Alias")])
def test_historical_refinement_refuses_raw_sgf_identity_contradictions(conn, album_id, raw_name):
    from katrain.web.kifu.source_rank_repair import prepare_rank_manifest

    sgf = conn.scalar(select(m.KifuAlbum.sgf_content).where(m.KifuAlbum.id == album_id))
    conn.execute(
        update(m.KifuAlbum)
        .where(m.KifuAlbum.id == album_id)
        .values(sgf_content=sgf.replace("PB[Black]", f"PB[{raw_name}]"))
    )
    manifest = prepare_rank_manifest(conn)
    slot = next(c for c in manifest["changes"] if c["album_id"] == 1)
    assert slot["snapshot_after"]["display_rank"] == "7段"


def test_old_artifact_with_conflicting_raw_sgf_identity_refuses_first_apply(conn):
    from hashlib import sha256
    from katrain.web.kifu.source_rank_repair import prepare_rank_manifest, apply_rank_manifest, rank_manifest_sha256
    from katrain.web.kifu.source_rank_normalization import snapshot_digest

    manifest = prepare_rank_manifest(conn)
    sgf = conn.scalar(select(m.KifuAlbum.sgf_content).where(m.KifuAlbum.id == 2)).replace("PB[Black]", "PB[White]")
    conn.execute(update(m.KifuAlbum).where(m.KifuAlbum.id == 2).values(sgf_content=sgf))
    sgf_hash = sha256(sgf.encode()).hexdigest()
    # Reproduce the artifact emitted by the former raw-name-blind preparer.
    for change in manifest["changes"]:
        if change["counterpart_before"] is not None:
            change["counterpart_before"]["sgf_sha256"] = sgf_hash
            snapshot = change["snapshot_after"]
            snapshot["evidence"]["counterpart"]["sgf_sha256"] = sgf_hash
            snapshot["content_sha256"] = snapshot_digest(snapshot)
    for cohort in manifest["historical_cohorts"]:
        for member in cohort["members"]:
            if member["id"] == 2:
                member["sgf_sha256"] = sgf_hash
    manifest["corpus_sha256"] = prepare_rank_manifest(conn)["corpus_sha256"]
    with pytest.raises(ValueError, match="identity"):
        apply_rank_manifest(conn, manifest, expected_sha256=rank_manifest_sha256(manifest))
    assert not list(conn.execute(select(m.KifuNameBatch.id)))
    assert not list(conn.execute(select(m.KifuAlbumRankSnapshot.id)))


@pytest.mark.parametrize("alias_owner,expected", [(1, "7p"), (2, "7段")])
def test_different_raw_name_requires_approved_exact_same_identity(conn, alias_owner, expected):
    from katrain.web.kifu.source_rank_repair import prepare_rank_manifest
    from katrain.web.kifu.identity import normalize_alias

    sgf = conn.scalar(select(m.KifuAlbum.sgf_content).where(m.KifuAlbum.id == 2))
    conn.execute(
        update(m.KifuAlbum)
        .where(m.KifuAlbum.id == 2)
        .values(sgf_content=sgf.replace("PB[Black]", "PB[Approved Alias]"))
    )
    conn.execute(
        m.KifuPlayerAlias.__table__.insert().values(
            player_id=alias_owner, alias="Approved Alias", normalized_alias=normalize_alias("Approved Alias")
        )
    )
    slot = next(c for c in prepare_rank_manifest(conn)["changes"] if c["album_id"] == 1)
    assert slot["snapshot_after"]["display_rank"] == expected


def test_known_raw_and_scalar_agreement_cannot_override_conflicting_fk(conn):
    from katrain.web.kifu.source_rank_repair import prepare_rank_manifest

    sgf = conn.scalar(select(m.KifuAlbum.sgf_content).where(m.KifuAlbum.id == 2))
    conn.execute(
        update(m.KifuAlbum)
        .where(m.KifuAlbum.id == 2)
        .values(player_black="White", sgf_content=sgf.replace("PB[Black]", "PB[White]"))
    )
    slot = next(c for c in prepare_rank_manifest(conn)["changes"] if c["album_id"] == 1)
    assert slot["snapshot_after"]["display_rank"] == "7段"


def test_changed_approved_identity_refuses_first_apply_but_frozen_retry_stays_stable(conn):
    from sqlalchemy import delete
    from katrain.web.kifu.source_rank_repair import prepare_rank_manifest, apply_rank_manifest, rank_manifest_sha256
    from katrain.web.kifu.identity import normalize_alias

    manifest = prepare_rank_manifest(conn)
    manifest_hash = rank_manifest_sha256(manifest)
    alias = dict(player_id=2, alias="Black", normalized_alias=normalize_alias("Black"))
    conn.execute(m.KifuPlayerAlias.__table__.insert().values(**alias))
    with pytest.raises(ValueError, match="identity"):
        apply_rank_manifest(conn, manifest, expected_sha256=manifest_hash)
    assert not list(conn.execute(select(m.KifuNameBatch.id)))
    conn.execute(delete(m.KifuPlayerAlias))
    apply_rank_manifest(conn, manifest, expected_sha256=manifest_hash)
    conn.execute(m.KifuPlayerAlias.__table__.insert().values(**alias))
    assert apply_rank_manifest(conn, manifest, expected_sha256=manifest_hash)["status"] == "already_applied"
    snapshot = conn.scalar(select(m.KifuAlbumRankSnapshot.snapshot).where(m.KifuAlbumRankSnapshot.album_id == 1))
    assert snapshot["display_rank"] == "7p"
