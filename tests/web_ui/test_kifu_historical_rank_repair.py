"""Historical CAS repair freezes bounded, private, reversible decisions."""

from copy import deepcopy
import importlib.util
import json
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select, update
from katrain.web.core import models_db as m

MATCHED = "2026-11-03T00:00:00+00:00"


@pytest.fixture
def engine():
    engine = create_engine("sqlite:///:memory:")
    m.Base.metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(
            m.KifuPlayer.__table__.insert(),
            [
                {"id": 11, "canonical_name": "棋手甲"},
                {"id": 12, "canonical_name": "棋手乙"},
            ],
        )
        conn.execute(
            m.KifuSource.__table__.insert(),
            [
                {"id": 3, "source_key": "CWI"},
                {"id": 4, "source_key": "19x19"},
            ],
        )
        game(conn, 1, "1960-01-01", "8p")
        game(conn, 2, "1968-08-01", "", family="CWI")
        game(conn, 3, "1970-01-01", "9d", family="CWI")
        game(conn, 4, "1950", "", hidden="excluded")
    yield engine
    engine.dispose()


def game(conn, ident, day, rank, *, family="19x19", hidden=None):
    path = f"data/kifu-album/{'19x19' if family == '19x19' else 'Go_Seigen'}/{ident}.sgf"
    conn.execute(
        m.KifuAlbum.__table__.insert().values(
            id=ident,
            source_path=path,
            sgf_content=f"(;SZ[19]PB[棋手甲]PW[棋手乙]BR[{rank}]WR[1p]DT[{day}];B[aa])",
            player_black="棋手甲",
            player_white="棋手乙",
            black_player_id=11,
            white_player_id=12,
            black_rank=rank,
            white_rank="1p",
            date_played=day,
            date_sort=day,
            list_hidden_reason=hidden,
        )
    )
    conn.execute(
        m.KifuAlbumSource.__table__.insert().values(
            album_id=ident,
            source_id=4 if family == "19x19" else 3,
            origin_path=path,
            match_method="source_path",
        )
    )


def prepare(conn, **kwargs):
    from katrain.web.kifu.historical_rank_repair import prepare_manifest

    return prepare_manifest(conn, matched_at=MATCHED, **kwargs)


def apply(conn, manifest):
    from katrain.web.kifu.historical_rank_repair import apply_in_transaction, manifest_sha256

    return apply_in_transaction(conn, manifest, expected_sha256=manifest_sha256(manifest))


def undo(conn, manifest):
    from katrain.web.kifu.historical_rank_repair import undo_in_transaction, manifest_sha256

    return undo_in_transaction(conn, manifest, expected_sha256=manifest_sha256(manifest))


def test_prepare_censuses_every_slot_but_changes_only_public_meaningful_targets(engine):
    with engine.begin() as conn:
        manifest = prepare(conn)
        assert manifest["census"]["albums"] == 4
        assert manifest["census"]["slots"] == 8
        assert manifest["census"]["excluded_slots"] == 2
        changes = [c for part in manifest["parts"] for c in part["changes"]]
        assert {(c["album_id"], c["side"]) for c in changes} == {(2, "black"), (3, "black")}
        assert {c["snapshot_after"]["origin"] for c in changes} == {"historical_prior", "historical_type"}
        assert not list(conn.execute(select(m.KifuAlbumRankSnapshot.id)))
        assert not list(conn.execute(select(m.KifuNameBatch.id)))
        assert "sgf_content" not in json.dumps(manifest)


def test_census_does_not_assume_album_primary_keys_start_at_one(engine):
    with engine.begin() as conn:
        game(conn, 0, "1900", "1p", hidden="excluded")
        assert prepare(conn)["census"]["albums"] == 5


def test_public_apply_shares_large_original_body_across_all_slots_and_verification(engine):
    """A reviewed legal part must not fetch one 128 KiB basis 100 times."""
    from sqlalchemy import event
    from katrain.web.kifu.historical_ranks import MAX_BODY_BYTES

    with engine.begin() as conn:
        conn.execute(m.KifuAlbumSource.__table__.delete().where(m.KifuAlbumSource.album_id != 1))
        conn.execute(m.KifuAlbum.__table__.delete().where(m.KifuAlbum.id != 1))
        body = conn.execute(select(m.KifuAlbum.sgf_content).where(m.KifuAlbum.id == 1)).scalar_one()
        body = body.replace("(;", "(;C[" + "x" * (131142 - len(body.encode()) - 3) + "]", 1)
        assert len(body.encode()) == 131142
        conn.execute(update(m.KifuAlbum).where(m.KifuAlbum.id == 1).values(sgf_content=body))
        for ident in range(2, 102):
            game(conn, ident, "1968-08-01", "", family="CWI")
        reads = []

        def observe_body(conn, cursor, statement, parameters, context, executemany):
            if statement.lstrip().splitlines()[0].strip() == "SELECT kifu_albums.sgf_content" and parameters[0] == 1:
                reads.append(len(body.encode()))

        event.listen(engine, "before_cursor_execute", observe_body)
        try:
            manifest = prepare(conn)
            assert reads == [131142, 131142]  # One original read in each finite preparation part.
            reads.clear()
            part = manifest["parts"][0]
            assert len(part["changes"]) == 99
            apply(conn, part)
            assert sum(reads) <= MAX_BODY_BYTES
            assert reads == [131142]
            assert len(list(conn.execute(select(m.KifuAlbumRankSnapshot.id)))) == 99
            reads.clear()
            assert apply(conn, part)["status"] == "already_applied"
            assert reads == [131142]
            reads.clear()
            undo(conn, part)
            assert reads == [131142]
        finally:
            event.remove(engine, "before_cursor_execute", observe_body)


def test_public_apply_rejects_combined_reviewed_unique_evidence_over_part_budget(engine):
    """Individually valid frozen decisions still share one finite apply budget."""
    from katrain.web.kifu.historical_rank_repair import MAX_PART_CHANGES
    from katrain.web.kifu.historical_ranks import MAX_BODY_BYTES
    from sqlalchemy import event

    with engine.begin() as conn:
        target_ids = []
        for number in range(34):
            name, player_id = f"Owner {number}", 1000 + number
            conn.execute(m.KifuPlayer.__table__.insert().values(id=player_id, canonical_name=name))
            for offset, day, rank in ((0, "1960-01-01", "8p"), (1, "1968-08-01", "")):
                ident = 100 + 2 * number + offset
                path = f"data/kifu-album/19x19/{ident}.sgf"
                body = f"(;PB[{name}]PW[棋手乙]BR[{rank}]WR[1p]DT[{day}];B[aa])"
                if offset == 0:
                    body = body.replace("(;", "(;C[" + "x" * (250000 - len(body.encode()) - 3) + "]", 1)
                else:
                    target_ids.append(ident)
                conn.execute(
                    m.KifuAlbum.__table__.insert().values(
                        id=ident,
                        source_path=path,
                        sgf_content=body,
                        player_black=name,
                        player_white="棋手乙",
                        black_player_id=player_id,
                        white_player_id=12,
                        black_rank=rank,
                        white_rank="1p",
                        date_played=day,
                        date_sort=day,
                    )
                )
                conn.execute(
                    m.KifuAlbumSource.__table__.insert().values(
                        album_id=ident,
                        source_id=4,
                        origin_path=path,
                        match_method="source_path",
                    )
                )
        pieces = [prepare(conn, album_ids=[ident])["parts"][0] for ident in target_ids]
        part = deepcopy(pieces[0])
        part["changes"] = [change for piece in pieces for change in piece["changes"]]
        part["basis_bindings"] = [change["basis_binding"] for change in part["changes"]]
        assert len(part["changes"]) == 34 <= MAX_PART_CHANGES
        assert 34 * 250000 > MAX_BODY_BYTES
        reads = []

        def observe_body(conn, cursor, statement, parameters, context, executemany):
            if statement.lstrip().splitlines()[0].strip() == "SELECT kifu_albums.sgf_content" and parameters[
                0
            ] in range(100, 168, 2):
                reads.append(250000)

        event.listen(engine, "before_cursor_execute", observe_body)
        try:
            with pytest.raises(ValueError, match="resource|budget|limit"):
                apply(conn, part)
        finally:
            event.remove(engine, "before_cursor_execute", observe_body)
        assert sum(reads) <= MAX_BODY_BYTES
        assert len(reads) < 34
        assert not list(conn.execute(select(m.KifuAlbumRankSnapshot.id)))
        assert not list(conn.execute(select(m.KifuNameBatch.id)))


def test_apply_retry_and_undo_restore_exact_rows_and_leave_raw_and_journals(engine):
    with engine.begin() as conn:
        raw = [dict(r) for r in conn.execute(select(m.KifuAlbum.__table__)).mappings()]
        sources = [dict(r) for r in conn.execute(select(m.KifuAlbumSource.__table__)).mappings()]
        manifest = prepare(conn)
        first = apply(conn, manifest)
        assert apply(conn, manifest)["status"] == "already_applied"
        artifact = conn.execute(
            select(m.KifuNameBatch.reviewed_artifact).where(m.KifuNameBatch.id == first["batch_id"])
        ).scalar_one()
        assert len(artifact["basis_bindings"]) == 2
        game(conn, 5, "1971-01-01", "9p")
        assert apply(conn, manifest)["status"] == "already_applied"
        assert undo(conn, manifest)["status"] == "undone"
        assert undo(conn, manifest)["status"] == "already_undone"
        assert not list(conn.execute(select(m.KifuAlbumRankSnapshot.id)))
        assert len(list(conn.execute(select(m.KifuNameChange.id)))) == 2
        assert [
            dict(r) for r in conn.execute(select(m.KifuAlbum.__table__).where(m.KifuAlbum.id <= 4)).mappings()
        ] == raw
        assert [
            dict(r)
            for r in conn.execute(select(m.KifuAlbumSource.__table__).where(m.KifuAlbumSource.album_id <= 4)).mappings()
        ] == sources


@pytest.mark.parametrize("damage", ["raw", "visibility", "source", "snapshot"])
def test_first_apply_refuses_any_complete_beforeimage_drift(engine, damage):
    with engine.begin() as conn:
        manifest = prepare(conn)
        if damage == "source":
            conn.execute(update(m.KifuAlbumSource).where(m.KifuAlbumSource.album_id == 2).values(match_method="later"))
        elif damage == "snapshot":
            conn.execute(
                m.KifuAlbumRankSnapshot.__table__.insert().values(
                    album_id=2,
                    side="black",
                    snapshot={"version": "later"},
                    snapshot_sha256="f" * 64,
                    publication_key="other",
                    native_batch_id=999,
                )
            )
        else:
            conn.execute(
                update(m.KifuAlbum)
                .where(m.KifuAlbum.id == 2)
                .values(**({"event": "later"} if damage == "raw" else {"list_hidden_reason": "later"}))
            )
        with pytest.raises(ValueError, match="preimage|beforeimage"):
            apply(conn, manifest)
        assert not list(conn.execute(select(m.KifuNameBatch.id)))


def test_first_apply_new_nearer_typed_conflict_refuses_whole_part(engine):
    with engine.begin() as conn:
        manifest = prepare(conn)
        game(conn, 5, "1967-06-01", "9d")
        with pytest.raises(ValueError, match="qualification|cohort"):
            apply(conn, manifest)
        assert not list(conn.execute(select(m.KifuAlbumRankSnapshot.id)))


def test_existing_legacy_snapshot_is_cas_corrected_and_old_journal_preserved(engine):
    from katrain.web.kifu.source_rank_repair import prepare_rank_manifest, apply_rank_manifest, rank_manifest_sha256

    with engine.begin() as conn:
        old = prepare_rank_manifest(conn)
        old_result = apply_rank_manifest(conn, old, expected_sha256=rank_manifest_sha256(old))
        original = dict(conn.execute(select(m.KifuAlbumRankSnapshot.__table__)).mappings().one())
        old_id = original["id"]
        old_journal = [dict(r) for r in conn.execute(select(m.KifuNameChange.__table__)).mappings()]
        manifest = prepare(conn, album_ids=[3])
        assert manifest["census"]["albums"] == 4
        result = apply(conn, manifest)
        row = conn.execute(select(m.KifuAlbumRankSnapshot.__table__)).mappings().one()
        assert row["id"] == old_id and row["snapshot"]["display_rank"] == "9p"
        journal = (
            conn.execute(select(m.KifuNameChange.__table__).where(m.KifuNameChange.batch_id == result["batch_id"]))
            .mappings()
            .one()
        )
        assert journal["before_image"] == original
        undo(conn, manifest)
        assert dict(conn.execute(select(m.KifuAlbumRankSnapshot.__table__)).mappings().one()) == original
        assert [
            dict(r)
            for r in conn.execute(
                select(m.KifuNameChange.__table__).where(m.KifuNameChange.batch_id == old_result["batch_id"])
            ).mappings()
        ] == old_journal


def test_invalid_legacy_current_afterimage_is_preserved_as_a_refusal(engine):
    from katrain.web.kifu.source_rank_repair import prepare_rank_manifest, apply_rank_manifest, rank_manifest_sha256

    with engine.begin() as conn:
        old = prepare_rank_manifest(conn)
        apply_rank_manifest(conn, old, expected_sha256=rank_manifest_sha256(old))
        conn.execute(update(m.KifuAlbumRankSnapshot).values(native_batch_id=999))
        manifest = prepare(conn)
        assert manifest["refusals"]["invalid_legacy_afterimage"] == 1
        assert all(c["album_id"] != 3 for p in manifest["parts"] for c in p["changes"])


def test_apply_never_commits_the_callers_transaction(engine):
    with engine.connect() as conn:
        transaction = conn.begin()
        manifest = prepare(conn)
        apply(conn, manifest)
        transaction.rollback()
    with engine.connect() as conn:
        assert not list(conn.execute(select(m.KifuAlbumRankSnapshot.id)))
        assert not list(conn.execute(select(m.KifuNameBatch.id)))


def test_standalone_artifact_keeps_original_basis_visible_to_native_compensation(engine):
    from katrain.web.kifu.historical_ranks import assert_retained_rank_basis

    with engine.begin() as conn:
        manifest = prepare(conn)
        apply(conn, manifest)
        with pytest.raises(ValueError, match="dependency"):
            assert_retained_rank_basis(conn, [{"album_id": 1}])
        undo(conn, manifest)
        assert_retained_rank_basis(conn, [{"album_id": 1}])


def test_api_reads_standalone_current_journal_and_falls_back_after_corruption(engine):
    from types import SimpleNamespace
    from katrain.web.kifu.player_ranks import lookup_album_rank_snapshots
    from katrain.web.kifu.name_parse import parse_player
    from katrain.web.api.v1.endpoints.kifu import _rank_displays

    with engine.begin() as conn:
        apply(conn, prepare(conn))
        album = SimpleNamespace(
            **dict(conn.execute(select(m.KifuAlbum.__table__).where(m.KifuAlbum.id == 2)).mappings().one())
        )
        black, white = parse_player(album.player_black, album.black_rank), parse_player(
            album.player_white, album.white_rank
        )
        values = _rank_displays(album, black, white, lookup_album_rank_snapshots(conn, [2]))
        assert values["display_black_rank"] == "8p"
        assert values["black_rank_source"]["source_as_of"] == "1960-01-01"
        conn.execute(
            update(m.KifuAlbumRankSnapshot)
            .where(m.KifuAlbumRankSnapshot.album_id == 2)
            .values(publication_key="corrupt")
        )
        values = _rank_displays(album, black, white, lookup_album_rank_snapshots(conn, [2]))
        assert values["display_black_rank"] == ""


def test_native_evidence_undo_waits_for_standalone_repair_undo(tmp_path):
    from katrain.kifu_ingest.catalog import undo_publication
    from tests.web_ui.test_kifu_historical_rank_native import prepared
    from tests.web_ui.test_kifu_incremental_catalog import make_engine, publish

    engine = make_engine(tmp_path / "native-repair-dependency.db")
    with engine.begin() as conn:
        # The independently imported historical target retains its source type
        # after rank undo; A must not also own that source type's creation.
        conn.execute(m.KifuSource.__table__.insert().values(source_key="19x19"))
    source = prepared(engine, item="99501", raw="7p", day="2026-01-01")
    receipt = publish(engine, source)
    target = prepared(engine, item="99502", day="2026-02-01")["games"][0]
    with engine.begin() as conn:
        conn.execute(
            m.KifuAlbum.__table__.insert().values(
                id=5000,
                source_path=target["origin_path"],
                sgf_content=target["sgf_content"],
                player_black="Black Alias",
                player_white="White Alias",
                black_player_id=17,
                white_player_id=18,
                black_rank="",
                date_played="2026-02-01",
                date_sort="2026-02-01",
            )
        )
        source_id = conn.execute(select(m.KifuSource.id).where(m.KifuSource.source_key == "19x19")).scalar_one()
        conn.execute(
            m.KifuAlbumSource.__table__.insert().values(
                album_id=5000,
                source_id=source_id,
                origin_path=target["origin_path"],
                match_method="source_path",
            )
        )
        manifest = prepare(conn, album_ids=[5000])
        apply(conn, manifest)
    with pytest.raises(ValueError, match="basis dependency"):
        undo_publication(engine, receipt["batch_id"])
    with engine.begin() as conn:
        undo(conn, manifest)
    assert undo_publication(engine, receipt["batch_id"])["status"] == "undone"
    engine.dispose()


def test_corrupt_current_afterimage_refuses_retry_and_entire_undo(engine):
    with engine.begin() as conn:
        manifest = prepare(conn)
        apply(conn, manifest)
        conn.execute(
            update(m.KifuAlbumRankSnapshot).where(m.KifuAlbumRankSnapshot.album_id == 3).values(publication_key="later")
        )
        with pytest.raises(ValueError, match="afterimage|journal"):
            apply(conn, manifest)
        with pytest.raises(ValueError, match="afterimage|journal"):
            undo(conn, manifest)
        assert len(list(conn.execute(select(m.KifuAlbumRankSnapshot.id)))) == 2


def test_unknown_is_reported_without_writing_and_existing_v3_is_never_replaced(engine):
    with engine.begin() as conn:
        game(conn, 6, "1940-01-01", "", family="CWI")
        manifest = prepare(conn)
        assert manifest["refusals"]["no_prior_original"] == 1
        assert all(c["album_id"] != 6 for p in manifest["parts"] for c in p["changes"])
        apply(conn, manifest)
        second = prepare(conn)
        assert second["census"]["existing_v3_slots"] == 2
        assert not second["parts"]


def test_cli_defaults_to_readonly_private_export_without_dsn_argument(engine, tmp_path, capsys):
    path = Path(__file__).resolve().parents[2] / "scripts" / "repair_historical_kifu_ranks.py"
    spec = importlib.util.spec_from_file_location("repair_historical_cli", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    output = tmp_path / "private.json"
    assert module.main(["--matched-at", MATCHED, "--output", str(output)], engine=engine) == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary["status"] == "prepared"
    assert output.stat().st_mode & 0o777 == 0o600
    with engine.begin() as conn:
        assert not list(conn.execute(select(m.KifuNameBatch.id)))
        assert not list(conn.execute(select(m.KifuAlbumRankSnapshot.id)))


def test_manifest_hash_and_database_binding_are_required(engine):
    from katrain.web.kifu.historical_rank_repair import apply_in_transaction, manifest_sha256

    with engine.begin() as conn:
        manifest = prepare(conn)
        with pytest.raises(ValueError, match="SHA"):
            apply_in_transaction(conn, manifest, expected_sha256="0" * 64)
        manifest = deepcopy(manifest)
        manifest["parts"][0]["database_identity"] = {"dialect": "wrong"}
        with pytest.raises(ValueError, match="database|part|binding"):
            apply_in_transaction(conn, manifest, expected_sha256=manifest_sha256(manifest))


def test_cli_finite_parts_stop_after_failure_and_report_exact_committed_scope(engine, tmp_path, capsys):
    from katrain.web.kifu.historical_rank_repair import manifest_sha256

    path = Path(__file__).resolve().parents[2] / "scripts" / "repair_historical_kifu_ranks.py"
    spec = importlib.util.spec_from_file_location("repair_historical_cli_parts", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with engine.begin() as conn:
        for ident in range(5, 106):
            game(conn, ident, "1972-01-01", "9pro")
        manifest = prepare(conn)
        assert len(manifest["parts"]) == 2
        assert all(
            len({c["album_id"] for c in p["changes"]}) <= 100 and len(p["changes"]) <= 200 for p in manifest["parts"]
        )
        changed_id = manifest["parts"][1]["changes"][0]["album_id"]
        conn.execute(update(m.KifuAlbum).where(m.KifuAlbum.id == changed_id).values(event="drift"))
    output, audit = tmp_path / "reviewed.json", tmp_path / "result.json"
    output.write_text(json.dumps(manifest), encoding="utf-8")
    output.chmod(0o600)
    assert (
        module.main(
            [
                "--apply",
                "--manifest",
                str(output),
                "--expected-sha256",
                manifest_sha256(manifest),
                "--audit-output",
                str(audit),
            ],
            engine=engine,
        )
        == 2
    )
    result = json.loads(capsys.readouterr().out)
    assert result["failed_part"] == 2
    assert [p["part"] for p in result["completed_parts"]] == [1]
    assert json.loads(audit.read_text())["completed_parts"] == result["completed_parts"]
    with engine.begin() as conn:
        assert len(list(conn.execute(select(m.KifuNameBatch.id)))) == 1
        assert len(list(conn.execute(select(m.KifuAlbumRankSnapshot.id)))) == len(manifest["parts"][0]["changes"])


def test_portable_decisions_ignore_local_album_source_and_player_ids(engine):
    with engine.begin() as conn:
        before = [c["snapshot_after"] for p in prepare(conn)["parts"] for c in p["changes"]]
        conn.execute(
            update(m.KifuAlbumSource).values(
                id=m.KifuAlbumSource.id + 100,
                source_id=m.KifuAlbumSource.source_id + 100,
                album_id=m.KifuAlbumSource.album_id + 100,
            )
        )
        conn.execute(update(m.KifuSource).values(id=m.KifuSource.id + 100))
        conn.execute(update(m.KifuPlayer).values(id=m.KifuPlayer.id + 100))
        conn.execute(
            update(m.KifuAlbum).values(
                id=m.KifuAlbum.id + 100,
                black_player_id=m.KifuAlbum.black_player_id + 100,
                white_player_id=m.KifuAlbum.white_player_id + 100,
            )
        )
        after = [c["snapshot_after"] for p in prepare(conn)["parts"] for c in p["changes"]]
        assert before == after


def test_disposable_postgresql_readonly_prepare_cas_rollback_and_source_lock():
    """Opt-in: create/drop one UUID schema; never touch public/shared rows."""
    import os
    from uuid import uuid4
    from sqlalchemy import text
    from sqlalchemy.exc import DBAPIError

    dsn = os.getenv("KIFU_STANDARDIZATION_TEST_PG_DSN") or os.getenv("KIFU_RANK_TEST_POSTGRES")
    if not dsn:
        pytest.skip("set KIFU_STANDARDIZATION_TEST_PG_DSN for disposable PostgreSQL verification")
    schema = "historical_rank_repair_" + uuid4().hex
    control = create_engine(dsn, hide_parameters=True)
    with control.begin() as admin:
        admin.execute(text(f"CREATE SCHEMA {schema}"))
    pg = create_engine(
        dsn, connect_args={"options": f"-csearch_path={schema}"}, isolation_level="READ COMMITTED", hide_parameters=True
    )
    try:
        m.Base.metadata.create_all(pg)
        with pg.begin() as conn:
            conn.execute(
                m.KifuPlayer.__table__.insert(),
                [
                    {"id": 11, "canonical_name": "棋手甲"},
                    {"id": 12, "canonical_name": "棋手乙"},
                ],
            )
            conn.execute(
                m.KifuSource.__table__.insert(),
                [
                    {"id": 3, "source_key": "CWI"},
                    {"id": 4, "source_key": "19x19"},
                ],
            )
            game(conn, 1, "1960-01-01", "8p")
            game(conn, 2, "1968-08-01", "", family="CWI")
        with pg.connect() as conn:
            with conn.begin():
                conn.exec_driver_sql("SET TRANSACTION READ ONLY")
                manifest = prepare(conn)
                assert manifest["census"]["changed_slots"] == 1
                assert not list(conn.execute(select(m.KifuNameBatch.id)))
            transaction = conn.begin()
            apply(conn, manifest)
            # Source owners and possible new cohort members cannot change while
            # this reviewed part is being written.
            with pg.connect() as concurrent:
                concurrent.exec_driver_sql("SET LOCAL lock_timeout = '100ms'")
                with pytest.raises(DBAPIError):
                    concurrent.execute(
                        update(m.KifuAlbumSource).where(m.KifuAlbumSource.album_id == 1).values(match_method="later")
                    )
                concurrent.rollback()
            transaction.rollback()
        with pg.begin() as conn:
            assert not list(conn.execute(select(m.KifuAlbumRankSnapshot.id)))
            assert not list(conn.execute(select(m.KifuNameBatch.id)))
            apply(conn, manifest)
        with pg.begin() as conn:
            assert apply(conn, manifest)["status"] == "already_applied"
            assert undo(conn, manifest)["status"] == "undone"
            assert not list(conn.execute(select(m.KifuAlbumRankSnapshot.id)))
    finally:
        pg.dispose()
        with control.begin() as admin:
            admin.execute(text(f"DROP SCHEMA {schema} CASCADE"))
        control.dispose()
