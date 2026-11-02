"""Reviewed display dedup keeps original source content and guarded journals."""

from copy import deepcopy
import importlib

import pytest
from sqlalchemy import create_engine, select, update

from katrain.web.core.models_db import Base, KifuAlbum, KifuAlbumSource, KifuPlayer, KifuSource, KifuDedupBatch


def module():
    assert importlib.util.find_spec("katrain.web.kifu.catalog_standardization"), "reviewed dedup is missing"
    return importlib.import_module("katrain.web.kifu.catalog_standardization")


def sgf(extra="", comment="original", moves=32):
    sequence = "".join(f';{"B" if i % 2 == 0 else "W"}[{chr(97+i%19)}{chr(97+i//19)}]' for i in range(moves))
    return f"(;FF[4]SZ[19]PB[Black]PW[White]DT[1989-01-17]KM[5.5]RE[B+R]{extra}C[{comment}]{sequence})"


@pytest.fixture
def engine(tmp_path):
    result = create_engine(f'sqlite:///{tmp_path / "catalog.db"}')
    Base.metadata.create_all(result)
    with result.begin() as conn:
        conn.execute(
            KifuPlayer.__table__.insert(), [{"id": 1, "canonical_name": "Black"}, {"id": 2, "canonical_name": "White"}]
        )
        conn.execute(KifuSource.__table__.insert(), [{"id": 1, "source_key": "CWI"}, {"id": 2, "source_key": "19x19"}])
        for album_id, source_id in [(25055, 1), (140858, 2)]:
            path = f"fixture/{album_id}.sgf"
            conn.execute(
                KifuAlbum.__table__.insert().values(
                    id=album_id,
                    black_player_id=1,
                    white_player_id=2,
                    player_black="Black",
                    player_white="White",
                    date_played="1989-01-17",
                    komi=5.5,
                    handicap=0,
                    result="B+R",
                    board_size=19,
                    move_count=32,
                    source_path=path,
                    sgf_content=sgf(comment=str(album_id)),
                )
            )
            conn.execute(
                KifuAlbumSource.__table__.insert().values(
                    album_id=album_id, source_id=source_id, origin_path=path, match_method="source_path"
                )
            )
    yield result
    result.dispose()


def prepare(engine):
    with engine.connect() as conn:
        return module().prepare_dedup_manifest(conn)


def apply(engine, manifest):
    with engine.begin() as conn:
        return module().apply_dedup_manifest(conn, manifest, expected_sha256=module().dedup_manifest_sha256(manifest))


def test_source_first_canonical_and_journaled_roundtrip(engine):
    m = module()
    manifest = prepare(engine)
    assert manifest["groups"][0]["canonical_album_id"] == 140858
    assert manifest["groups"][0]["duplicate_album_ids"] == [25055]
    before = deepcopy(manifest["groups"][0]["members"])
    first = apply(engine, manifest)
    assert first["duplicates_hidden"] == 1
    assert apply(engine, manifest)["idempotent"] is True
    with engine.connect() as conn:
        assert conn.scalar(select(KifuAlbum.duplicate_of_id).where(KifuAlbum.id == 25055)) == 140858
        assert conn.scalar(select(KifuAlbum.sgf_content).where(KifuAlbum.id == 25055)) == sgf(comment="25055")
        proof = m.verified_display_duplicate(conn, 25055)
        assert proof["canonical_album_id"] == 140858
        assert proof["sgf_sha256"] != proof["canonical_sgf_sha256"]
        assert (
            conn.scalar(
                select(KifuAlbumSource.match_method).where(
                    KifuAlbumSource.album_id == 140858, KifuAlbumSource.origin_path == "fixture/25055.sgf"
                )
            )
            == "reviewed_same_game"
        )
    with engine.begin() as conn:
        m.undo_dedup_manifest(conn, manifest, expected_sha256=m.dedup_manifest_sha256(manifest))
    assert prepare(engine)["groups"][0]["members"] == before


@pytest.mark.parametrize("change", ["setup", "turn", "pass", "size", "color", "bad-coordinate", "multi-move"])
def test_full_operation_identity_keeps_board_semantics(change):
    m = module()
    original = sgf()
    changed = {
        "setup": sgf("AB[dd]"),
        "turn": sgf("PL[W]"),
        "pass": original.replace(";B[aa]", ";B[]"),
        "size": original.replace("SZ[19]", "SZ[20]"),
        "color": original.replace(";B[aa]", ";W[aa]"),
        "bad-coordinate": original.replace(";B[aa]", ";B[zz]"),
        "multi-move": original.replace(";B[aa]", ";B[aa]W[bb]"),
    }[change]
    try:
        assert m.full_operation_fingerprint(original) != m.full_operation_fingerprint(changed)
    except ValueError:
        assert change in ("bad-coordinate", "multi-move")


def test_setup_ranges_expand_and_comments_do_not_change_identity():
    m = module()
    assert m.full_operation_fingerprint(sgf("AB[aa:bb]")) == m.full_operation_fingerprint(
        sgf("AB[aa][ab][ba][bb]", comment="other")
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("date_played", "1989"),
        ("black_player_id", None),
        ("white_player_id", 1),
        ("komi", 6.5),
        ("result", "W+R"),
        ("rules", "japanese"),
        ("list_hidden_reason", "excluded"),
    ],
)
def test_uncertain_or_conflicting_groups_are_report_only(engine, field, value):
    with engine.begin() as conn:
        conn.execute(update(KifuAlbum).where(KifuAlbum.id == 25055).values(**{field: value}))
        if field == "rules":
            conn.execute(update(KifuAlbum).where(KifuAlbum.id == 140858).values(rules="chinese"))
        if field == "black_player_id":
            conn.execute(update(KifuAlbum).where(KifuAlbum.id == 25055).values(player_black="Unresolved"))
    manifest = prepare(engine)
    assert manifest["groups"] == []


def test_drift_refuses_entire_batch_and_undo_refuses_new_sources(engine):
    m = module()
    manifest = prepare(engine)
    with engine.begin() as conn:
        conn.execute(update(KifuAlbum).where(KifuAlbum.id == 25055).values(event="changed"))
    with pytest.raises(ValueError, match="preimage"):
        apply(engine, manifest)
    with engine.connect() as conn:
        assert conn.scalar(select(KifuDedupBatch.id)) is None
    with engine.begin() as conn:
        conn.execute(update(KifuAlbum).where(KifuAlbum.id == 25055).values(event=None))
    apply(engine, manifest)
    with engine.begin() as conn:
        conn.execute(
            KifuAlbumSource.__table__.insert().values(
                album_id=140858, source_id=2, origin_path="later.sgf", match_method="source_path"
            )
        )
    with pytest.raises(ValueError, match="afterimage"):
        with engine.begin() as conn:
            m.undo_dedup_manifest(conn, manifest, expected_sha256=m.dedup_manifest_sha256(manifest))


def test_ordinary_cross_sgf_pointer_cannot_claim_reviewed_proof(engine):
    with engine.begin() as conn:
        conn.execute(update(KifuAlbum).where(KifuAlbum.id == 25055).values(duplicate_of_id=140858))
    with engine.connect() as conn, pytest.raises(ValueError, match="journal"):
        module().verified_display_duplicate(conn, 25055)


def test_native_publication_original_retry_and_new_source_survive_reviewed_dedup(tmp_path):
    from hashlib import sha256
    from tests.web_ui.test_kifu_incremental_catalog import make_engine, manifest, publish

    engine = make_engine(tmp_path / "native.db")

    def native(source_id, comment):
        value = manifest(source_id)
        game = value["games"][0]
        game["sgf_content"] = (
            sgf(comment=comment)
            .replace("PB[Black]", "PB[Black Alias]")
            .replace("DT[1989-01-17]", "DT[2026-02-01]")
            .replace("KM[5.5]", "EV[Summer Cup]KM[5.5]")
        )
        game["sgf_sha256"] = game["raw_sha256"] = sha256(game["sgf_content"].encode()).hexdigest()
        return value

    first = native("111", "first")
    second = native("112", "second")
    first_receipt = publish(engine, first)
    second_receipt = publish(engine, second)
    canonical = first_receipt["games"][0]["album_id"]
    original = second_receipt["games"][0]["album_id"]
    manifest_dedup = prepare(engine)
    assert manifest_dedup["groups"][0]["canonical_album_id"] == canonical
    apply(engine, manifest_dedup)
    assert publish(engine, second) == second_receipt
    # A fresh publication of the original source must find its exact owner,
    # despite the same path also being aggregated onto the canonical record.
    again = deepcopy(second)
    again["publication_key"] = "retry-under-new-key"
    assert publish(engine, again)["games"][0]["album_id"] == original
    third = deepcopy(second)
    third["publication_key"] = "new-original-source"
    third["games"][0].update(source_item_id="113", origin_path="fixture/113.sgf")
    assert publish(engine, third)["games"][0]["album_id"] == original
    with engine.connect() as conn:
        assert module().verified_display_duplicate(conn, original)["canonical_album_id"] == canonical
        assert (
            conn.scalar(
                select(KifuAlbumSource.id).where(
                    KifuAlbumSource.album_id == canonical,
                    KifuAlbumSource.origin_path == "fixture/113.sgf",
                    KifuAlbumSource.match_method == "reviewed_same_game",
                )
            )
            is not None
        )
    engine.dispose()


def test_forged_identity_claim_in_manifest_is_refused(engine):
    manifest = prepare(engine)
    manifest["groups"][0]["ordered_player_ids"] = [999, 998]
    with pytest.raises(ValueError, match="identity"):
        apply(engine, manifest)


def test_http_replay_can_prove_original_detail_and_distinct_public_canonical(engine):
    from katrain.kifu_ingest.sync import _validate_public_card
    from katrain.web.kifu.name_candidates import canonical_sha256

    m = module()
    manifest = prepare(engine)
    apply(engine, manifest)
    with engine.connect() as conn:
        proof = m.verified_display_duplicate(conn, 25055)
    game = {
        "sgf_content": sgf(comment="25055"),
        "sgf_sha256": proof["sgf_sha256"],
        "metadata": {"date_played": "1989-01-17", "player_black": "Black"},
    }
    detail = {
        "displays": {"display_player_black": "Black", "display_player_white": "White", "display_event": "Original"}
    }
    card = {
        "album_id": 25055,
        "lang": "cn",
        "query": "1989-01-17",
        "page": 1,
        "page_size": 100,
        "displays": detail["displays"],
        "display_duplicate": proof,
        "original_sgf_sha256": proof["sgf_sha256"],
        "canonical_card": {
            "album_id": 140858,
            "sgf_sha256": proof["canonical_sgf_sha256"],
            "displays": {
                "display_player_black": "Black",
                "display_player_white": "White",
                "display_event": "Canonical",
            },
        },
    }
    _validate_public_card(card, game, 25055, detail, {}, False)
    card["display_duplicate"] = {**proof, "album_id": 140858}
    with pytest.raises(ValueError, match="duplicate"):
        _validate_public_card(card, game, 25055, detail, {}, False)


@pytest.mark.parametrize("canonical_reimport", [False, True])
def test_actual_http_replay_checks_original_and_public_canonical(tmp_path, canonical_reimport):
    import asyncio
    from hashlib import sha256
    import httpx
    from sqlalchemy.orm import Session
    from katrain.core.sgf_parser import SGF
    from katrain.kifu_ingest.sync import verify_album_api
    from katrain.web.api.v1.endpoints.kifu import read_album_detail_legacy
    from tests.web_ui.test_kifu_incremental_catalog import make_engine, manifest, publish

    engine = make_engine(tmp_path / "http-native.db")
    values = []
    for item in ("211", "212"):
        value = manifest(item)
        game = value["games"][0]
        game["sgf_content"] = SGF.parse_sgf(
            sgf(comment=item)
            .replace("PB[Black]", "PB[Black Alias]")
            .replace("DT[1989-01-17]", "DT[2026-02-01]")
            .replace("KM[5.5]", "EV[Summer Cup]KM[5.5]")
        ).sgf()
        if canonical_reimport and item == "212":
            game["sgf_content"] += "\n"
        game["sgf_sha256"] = game["raw_sha256"] = sha256(game["sgf_content"].encode()).hexdigest()
        values.append(value)
    receipts = [publish(engine, value) for value in values]
    if canonical_reimport:
        again = deepcopy(values[1])
        again["publication_key"] = "canonical-byte-reimport"
        again["games"][0].update(source_item_id="213", origin_path="fixture/213.sgf")
        game = again["games"][0]
        game["sgf_content"] = SGF.parse_sgf(game["sgf_content"]).sgf()
        game["sgf_sha256"] = game["raw_sha256"] = sha256(game["sgf_content"].encode()).hexdigest()
        receipts[1] = publish(engine, again)
        values[1] = again
    apply(engine, prepare(engine))

    def response(request):
        with Session(engine) as db:
            if request.url.path.endswith("/albums"):
                ids = db.scalars(select(KifuAlbum.id).where(KifuAlbum.duplicate_of_id.is_(None))).all()
                items = [read_album_detail_legacy(db, album_id, lang="cn").model_dump() for album_id in ids]
                return httpx.Response(200, json={"items": items, "total": len(items)})
            album_id = int(request.url.path.rsplit("/", 1)[-1])
            return httpx.Response(
                200, json=read_album_detail_legacy(db, album_id, lang=request.url.params.get("lang", "cn")).model_dump()
            )

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(response)) as client:
            return await verify_album_api(client, "http://fixture.test", values[1], receipts[1])

    assert asyncio.run(run())["status"] == "verified"
    engine.dispose()


def test_combined_cli_requires_frozen_hash_and_exports_beforeimages(engine, tmp_path):
    from scripts import standardize_kifu_catalog as cli

    with engine.connect() as conn:
        manifest = cli.prepare_manifest(conn)
    artifact = tmp_path / "repair.json"
    cli.export_manifest(manifest, artifact)
    cli.export_manifest(manifest, artifact)  # an exact repeat keeps the durable original
    assert artifact.exists() and artifact.with_suffix(".json.sha256").exists()
    with pytest.raises(ValueError, match="hash"):
        with engine.begin() as conn:
            cli.apply_manifest(conn, manifest, expected_sha256="0" * 64)
    with engine.begin() as conn:
        report = cli.apply_manifest(conn, manifest, expected_sha256=cli.manifest_sha256(manifest))
    assert report["dedup"]["duplicates_hidden"] == 1
    with engine.begin() as conn:
        cli.undo_manifest(conn, manifest, expected_sha256=cli.manifest_sha256(manifest))
    assert prepare(engine)["summary"]["duplicates_to_hide"] == 1


@pytest.mark.parametrize("drift", ["source", "name", "pointer"])
def test_native_retry_refuses_unjournaled_or_changed_proof(tmp_path, drift):
    from hashlib import sha256
    from tests.web_ui.test_kifu_incremental_catalog import make_engine, manifest, publish
    from katrain.web.core.models_db import KifuRawEventName

    engine = make_engine(tmp_path / "drift.db")
    values = []
    for item in ("311", "312"):
        value = manifest(item)
        game = value["games"][0]
        game["sgf_content"] = (
            sgf(comment=item)
            .replace("PB[Black]", "PB[Black Alias]")
            .replace("DT[1989-01-17]", "DT[2026-02-01]")
            .replace("KM[5.5]", "EV[Summer Cup]KM[5.5]")
        )
        game["sgf_sha256"] = game["raw_sha256"] = sha256(game["sgf_content"].encode()).hexdigest()
        values.append(value)
    receipts = [publish(engine, value) for value in values]
    original = receipts[1]["games"][0]["album_id"]
    apply(engine, prepare(engine))
    with engine.begin() as conn:
        if drift == "source":
            conn.execute(
                update(KifuAlbumSource).where(KifuAlbumSource.album_id == original).values(origin_path="changed.sgf")
            )
        elif drift == "name":
            conn.execute(update(KifuRawEventName).values(display_name="unaudited changed display"))
        else:
            conn.execute(update(KifuAlbum).where(KifuAlbum.id == original).values(duplicate_of_id=11))
    with pytest.raises(ValueError):
        publish(engine, values[1])
    engine.dispose()


def test_legacy_exact_reimport_attaches_original_and_reviewed_provenance(engine, tmp_path, monkeypatch):
    from scripts import import_kifu
    from katrain.core.sgf_parser import SGF
    from katrain.web.kifu.catalog_backfill import backfill_catalog
    from sqlalchemy.orm import Session

    # The legacy importer canonicalizes serialized SGF before comparing bytes.
    with engine.begin() as conn:
        conn.execute(
            update(KifuAlbum).where(KifuAlbum.id == 25055).values(sgf_content=SGF.parse_sgf(sgf(comment="25055")).sgf())
        )
    apply(engine, prepare(engine))
    incoming = tmp_path / "incoming"
    incoming.mkdir()
    (incoming / "original-again.sgf").write_text(sgf(comment="25055"))
    monkeypatch.setattr(import_kifu, "DATA_DIR", incoming)
    monkeypatch.setattr(import_kifu, "engine", engine)
    import_kifu.import_kifu()
    with engine.connect() as conn:
        assert conn.scalar(select(KifuAlbum.duplicate_of_id).where(KifuAlbum.id == 25055)) == 140858
        assert (
            conn.scalar(
                select(KifuAlbumSource.id).where(
                    KifuAlbumSource.album_id == 25055, KifuAlbumSource.match_method == "exact_sgf"
                )
            )
            is not None
        )
        assert (
            conn.scalar(
                select(KifuAlbumSource.id).where(
                    KifuAlbumSource.album_id == 140858,
                    KifuAlbumSource.origin_path.like("%original-again.sgf"),
                    KifuAlbumSource.match_method == "reviewed_same_game",
                )
            )
            is not None
        )
    with Session(engine) as db:
        report = backfill_catalog(db, None, dry_run=True, dedupe=True, scan_mainlines=False)
    assert report["pointer_conflicts"] == 0


def test_combined_rank_dedup_repeat_and_atomic_refusal(engine):
    from scripts import standardize_kifu_catalog as cli
    from katrain.web.core.models_db import KifuAlbumRankSnapshot

    with engine.begin() as conn:
        for album_id, source in [(25055, "Go_Seigen"), (140858, "19x19")]:
            path = f"data/kifu-album/{source}/{album_id}.sgf"
            rank = "7d" if album_id == 25055 else "7p"
            conn.execute(
                update(KifuAlbum)
                .where(KifuAlbum.id == album_id)
                .values(source_path=path, black_rank=rank, sgf_content=sgf(f"BR[{rank}]", comment=str(album_id)))
            )
            conn.execute(update(KifuAlbumSource).where(KifuAlbumSource.album_id == album_id).values(origin_path=path))
    with engine.connect() as conn:
        manifest = cli.prepare_manifest(conn)
    assert len(manifest["ranks"]["changes"]) == 1
    with engine.begin() as conn:
        conn.execute(update(KifuAlbum).where(KifuAlbum.id == 140858).values(event="unrelated changed event"))
        with pytest.raises(ValueError, match="preimage"):
            cli.apply_manifest(conn, manifest, expected_sha256=cli.manifest_sha256(manifest))
        assert conn.scalar(select(KifuAlbumRankSnapshot.id)) is None
        conn.execute(update(KifuAlbum).where(KifuAlbum.id == 140858).values(event=None))
    with engine.begin() as conn:
        cli.apply_manifest(conn, manifest, expected_sha256=cli.manifest_sha256(manifest))
    with engine.begin() as conn:
        assert cli.apply_manifest(conn, manifest, expected_sha256=cli.manifest_sha256(manifest))["dedup"]["idempotent"]
    with engine.begin() as conn:
        cli.undo_manifest(conn, manifest, expected_sha256=cli.manifest_sha256(manifest))
    with engine.connect() as conn:
        assert conn.scalar(select(KifuAlbumRankSnapshot.id)) is None


def test_disposable_postgresql_apply_undo(tmp_path):
    """Opt-in PG proof uses a new schema and never touches the shared tables."""
    import os
    from uuid import uuid4
    from sqlalchemy import text
    from scripts import standardize_kifu_catalog as cli

    dsn = os.getenv("KIFU_STANDARDIZATION_TEST_PG_DSN")
    if not dsn:
        pytest.skip("set KIFU_STANDARDIZATION_TEST_PG_DSN for disposable PostgreSQL verification")
    schema = "kifu_m3_" + uuid4().hex
    control = create_engine(dsn)
    with control.begin() as conn:
        conn.execute(text(f"CREATE SCHEMA {schema}"))
    pg = create_engine(dsn, connect_args={"options": f"-csearch_path={schema}"})
    try:
        Base.metadata.create_all(pg)
        with pg.begin() as conn:
            conn.execute(
                KifuPlayer.__table__.insert(),
                [{"id": 1, "canonical_name": "Black"}, {"id": 2, "canonical_name": "White"}],
            )
            conn.execute(
                KifuSource.__table__.insert(), [{"id": 1, "source_key": "CWI"}, {"id": 2, "source_key": "19x19"}]
            )
            for album_id, source_id, family, rank in [(1, 1, "Go_Seigen", "7d"), (2, 2, "19x19", "7p")]:
                path = f"data/kifu-album/{family}/{album_id}.sgf"
                conn.execute(
                    KifuAlbum.__table__.insert().values(
                        id=album_id,
                        black_player_id=1,
                        white_player_id=2,
                        player_black="Black",
                        player_white="White",
                        date_played="1989-01-17",
                        black_rank=rank,
                        komi=5.5,
                        handicap=0,
                        result="B+R",
                        source_path=path,
                        sgf_content=sgf(f"BR[{rank}]", comment=str(album_id)),
                    )
                )
                conn.execute(
                    KifuAlbumSource.__table__.insert().values(
                        album_id=album_id, source_id=source_id, origin_path=path, match_method="source_path"
                    )
                )
        with pg.connect() as conn:
            manifest = cli.prepare_manifest(conn)
        cli.export_manifest(manifest, tmp_path / "postgres-beforeimages.json")
        with pg.begin() as conn:
            result = cli.apply_manifest(conn, manifest, expected_sha256=cli.manifest_sha256(manifest))
            assert result["dedup"]["duplicates_hidden"] == 1
        with pg.begin() as conn:
            assert cli.apply_manifest(conn, manifest, expected_sha256=cli.manifest_sha256(manifest))["dedup"][
                "idempotent"
            ]
        with pg.begin() as conn:
            cli.undo_manifest(conn, manifest, expected_sha256=cli.manifest_sha256(manifest))
        with pg.connect() as conn:
            assert conn.scalar(select(KifuAlbum.duplicate_of_id).where(KifuAlbum.id == 1)) is None
            assert module().prepare_dedup_manifest(conn)["summary"]["duplicates_to_hide"] == 1
    finally:
        pg.dispose()
        with control.begin() as conn:
            conn.execute(text(f"DROP SCHEMA {schema} CASCADE"))
        control.dispose()


def test_manifest_cannot_override_starpoint_canonical_preference(engine):
    manifest = prepare(engine)
    group = manifest["groups"][0]
    group["canonical_album_id"] = 25055
    group["duplicate_album_ids"] = [140858]
    with pytest.raises(ValueError, match="canonical"):
        apply(engine, manifest)


def test_two_starpoint_sources_use_stable_original_id(engine):
    with engine.begin() as conn:
        conn.execute(update(KifuAlbumSource).where(KifuAlbumSource.album_id == 25055).values(source_id=2))
    assert prepare(engine)["groups"][0]["canonical_album_id"] == 25055


def test_sgf_metadata_conflict_cannot_hide_behind_stale_album_columns(engine):
    with engine.begin() as conn:
        conn.execute(
            update(KifuAlbum)
            .where(KifuAlbum.id == 25055)
            .values(sgf_content=sgf(comment="25055").replace("KM[5.5]", "KM[6.5]"))
        )
    assert prepare(engine)["groups"] == []


@pytest.mark.parametrize("bad", [sgf() + "(;B[aa])", "not-sgf", sgf().replace("B[aa]", "B[aaa]")])
def test_incomplete_or_multi_game_input_is_report_only(bad):
    with pytest.raises(ValueError):
        module().full_operation_fingerprint(bad)


def test_original_source_link_identity_is_an_exact_precondition(engine):
    from sqlalchemy import delete

    manifest = prepare(engine)
    with engine.begin() as conn:
        conn.execute(delete(KifuAlbumSource).where(KifuAlbumSource.album_id == 25055))
        conn.execute(
            KifuAlbumSource.__table__.insert().values(
                id=999, album_id=25055, source_id=1, origin_path="fixture/25055.sgf", match_method="source_path"
            )
        )
    with pytest.raises(ValueError, match="source.*preimage"):
        apply(engine, manifest)


def test_sgf_date_disagreement_is_not_precise_same_game_evidence(engine):
    with engine.begin() as conn:
        conn.execute(
            update(KifuAlbum)
            .where(KifuAlbum.id == 25055)
            .values(sgf_content=sgf(comment="25055").replace("DT[1989-01-17]", "DT[1990-01-17]"))
        )
    assert prepare(engine)["groups"] == []


def test_sgf_ordered_identity_conflict_cannot_hide_behind_scalar_fk(engine):
    with engine.begin() as conn:
        conn.execute(
            update(KifuAlbum)
            .where(KifuAlbum.id == 25055)
            .values(sgf_content=sgf(comment="25055").replace("PB[Black]", "PB[White]"))
        )
    assert prepare(engine)["groups"] == []


def test_reviewed_yoda_exact_pair_refuses_new_conflicting_identity(engine):
    import json
    from pathlib import Path
    from katrain.web.core.models_db import KifuPlayerAlias

    rows = json.loads((Path(__file__).resolve().parents[1] / "data/kifu_metadata_reviewed_target.json").read_text())
    with engine.begin() as conn:
        conn.execute(update(KifuPlayer).where(KifuPlayer.id == 1).values(canonical_name="吴清源"))
        conn.execute(
            KifuPlayer.__table__.insert(),
            [{"id": 57, "canonical_name": "依田纪基"}, {"id": 99, "canonical_name": "Different player"}],
        )
        for row in rows:
            values = {key: value for key, value in row.items() if key in KifuAlbum.__table__.columns and key != "id"}
            conn.execute(update(KifuAlbum).where(KifuAlbum.id == row["id"]).values(**values))
            conn.execute(
                update(KifuAlbumSource)
                .where(KifuAlbumSource.album_id == row["id"])
                .values(origin_path=row["source_path"])
            )
    manifest = prepare(engine)
    assert manifest["groups"][0]["canonical_album_id"] == 140858
    assert manifest["groups"][0]["reviewed_identity"]["ordered_player_ids"] == [57, 1]
    with engine.begin() as conn:
        conn.execute(
            KifuPlayerAlias.__table__.insert().values(
                player_id=99, alias="Yoda Norimoto", normalized_alias="yoda norimoto"
            )
        )
    with pytest.raises(ValueError, match="identity"):
        apply(engine, manifest)
    assert prepare(engine)["groups"] == []


def test_verified_display_without_source_cannot_grant_missing_player_identity(engine):
    from katrain.web.core.models_db import KifuPlayerName

    with engine.begin() as conn:
        conn.execute(
            update(KifuAlbum)
            .where(KifuAlbum.id == 25055)
            .values(
                black_player_id=None,
                player_black="Unapproved Alias",
                sgf_content=sgf(comment="25055").replace("PB[Black]", "PB[Unapproved Alias]"),
            )
        )
        conn.execute(
            KifuPlayerName.__table__.insert().values(
                player_id=1, lang="en", display_name="Unapproved Alias", status="verified", reference_url=None
            )
        )
    assert prepare(engine)["groups"] == []


def _search_repair_fixture(engine, monkeypatch):
    from scripts import standardize_kifu_catalog as cli
    from tests.web_ui.test_kifu_search_publication import ES
    from katrain.web.kifu import search_sync

    with engine.begin() as conn:
        for album_id, family, rank in [(25055, "Go_Seigen", "7d"), (140858, "19x19", "7p")]:
            path = f"data/kifu-album/{family}/{album_id}.sgf"
            conn.execute(
                update(KifuAlbum)
                .where(KifuAlbum.id == album_id)
                .values(source_path=path, black_rank=rank, sgf_content=sgf(f"BR[{rank}]", comment=str(album_id)))
            )
            conn.execute(update(KifuAlbumSource).where(KifuAlbumSource.album_id == album_id).values(origin_path=path))
        path = "data/kifu-album/Go_Seigen/160000.sgf"
        conn.execute(
            KifuAlbum.__table__.insert().values(
                id=160000,
                player_black="Black",
                player_white="White",
                black_player_id=1,
                white_player_id=2,
                black_rank="5d",
                date_played="1989-01-18",
                result="B+R",
                source_path=path,
                sgf_content=sgf("BR[5d]").replace("DT[1989-01-17]", "DT[1989-01-18]"),
            )
        )
        conn.execute(
            KifuAlbumSource.__table__.insert().values(
                album_id=160000, source_id=1, origin_path=path, match_method="source_path"
            )
        )
    with engine.connect() as conn:
        manifest = cli.prepare_manifest(conn)
    assert len(manifest["ranks"]["changes"]) == 2
    es = ES()
    monkeypatch.setenv("KIFU_SEARCH_SYNC_MODE", "enabled")
    monkeypatch.setenv("KIFU_SEARCH_BACKEND", "elasticsearch")
    monkeypatch.setenv("KIFU_STRICT_NAMES", "0")
    monkeypatch.setattr(search_sync, "_writer_client", lambda: es)
    return cli, manifest, search_sync, es


def test_catalog_repair_es_gate_precedes_sql_and_refreshes_exact_changed_ids(engine, monkeypatch):
    from katrain.web.core.models_db import KifuAlbumRankSnapshot

    cli, manifest, sync, es = _search_repair_fixture(engine, monkeypatch)
    assert hasattr(cli, "write_manifest"), "repair needs the current post-commit search coordinator"
    original = cli.apply_rank_manifest

    def ranks(conn, *args, **kwargs):
        assert es.state["status"] == "pending"
        assert es.state["operation_type"] == "sync_ids"
        assert es.state["operation_ref"] == {"album_ids": [25055, 140858, 160000]}
        return original(conn, *args, **kwargs)

    monkeypatch.setattr(cli, "apply_rank_manifest", ranks)
    project = sync._project_actions

    def committed_projection(conn, scope):
        assert scope.album_ids == {25055, 140858, 160000}
        assert es.state["status"] == "pending"
        with engine.connect() as observer:
            assert observer.scalar(select(KifuAlbum.duplicate_of_id).where(KifuAlbum.id == 25055)) == 140858
            assert len(observer.scalars(select(KifuAlbumRankSnapshot.id)).all()) == 2
        return project(conn, scope)

    monkeypatch.setattr(sync, "_project_actions", committed_projection)
    result = cli.write_manifest(engine, manifest, mode="apply", expected_sha256=cli.manifest_sha256(manifest))
    assert result["search"] == {"status": "synced", "album_ids": [25055, 140858, 160000]}
    assert es.events == ["pending", "refresh", "ready"]
    docs = {a["_id"]: a["_source"] for a in es.actions if a["_id"].startswith("album:")}
    assert docs["album:25055"]["list_visible"] is False
    assert docs["album:140858"]["list_visible"] is True
    assert docs["album:140858"]["metadata"]["sources"] == ["19x19", "CWI"]
    assert "album:160000" in docs


def test_catalog_repair_es_failure_blocks_stale_hits_and_original_retry_recovers(engine, monkeypatch):
    from katrain.web.api.v1.endpoints.kifu import _checked_search_state
    from katrain.web.kifu.search_es import SearchUnavailable

    cli, manifest, sync, es = _search_repair_fixture(engine, monkeypatch)
    assert hasattr(cli, "write_manifest"), "repair needs the current post-commit search coordinator"
    es.fail_bulk = True
    with pytest.raises(sync.SearchIndexPending) as raised:
        cli.write_manifest(engine, manifest, mode="apply", expected_sha256=cli.manifest_sha256(manifest))
    assert raised.value.operation_ref == {"album_ids": [25055, 140858, 160000]}
    assert es.state["status"] == "pending"
    with engine.connect() as conn:
        assert conn.scalar(select(KifuAlbum.duplicate_of_id).where(KifuAlbum.id == 25055)) == 140858
    with pytest.raises(SearchUnavailable):
        _checked_search_state({"found": True, "_index": "kifu-test-1", "_source": deepcopy(es.state)})
    es.fail_bulk = False
    assert cli.write_manifest(engine, manifest, mode="apply", expected_sha256=cli.manifest_sha256(manifest))["dedup"][
        "idempotent"
    ]
    assert es.state["status"] == "ready"
    assert (
        _checked_search_state({"found": True, "_index": "kifu-test-1", "_source": deepcopy(es.state)})["status"]
        == "ready"
    )
    docs = {a["_id"]: a["_source"] for a in es.actions if a["_id"].startswith("album:")}
    assert docs["album:25055"]["list_visible"] is False
    cli.write_manifest(engine, manifest, mode="undo", expected_sha256=cli.manifest_sha256(manifest))
    assert es.state["status"] == "ready"
    docs = {a["_id"]: a["_source"] for a in es.actions if a["_id"].startswith("album:")}
    assert docs["album:25055"]["list_visible"] is True
    assert docs["album:140858"]["metadata"]["sources"] == ["19x19"]


def test_catalog_repair_preimage_refusal_restores_es_gate_and_rolls_back_sql(engine, monkeypatch):
    from katrain.web.core.models_db import KifuAlbumRankSnapshot

    cli, manifest, sync, es = _search_repair_fixture(engine, monkeypatch)
    assert hasattr(cli, "write_manifest"), "repair needs the current post-commit search coordinator"
    with engine.begin() as conn:
        conn.execute(update(KifuAlbum).where(KifuAlbum.id == 140858).values(event="independent change"))
    with pytest.raises(ValueError, match="preimage"):
        cli.write_manifest(engine, manifest, mode="apply", expected_sha256=cli.manifest_sha256(manifest))
    assert es.state["status"] == "ready"
    assert es.events == ["pending", "ready"]
    assert es.actions == []
    with engine.connect() as conn:
        assert conn.scalar(select(KifuAlbum.duplicate_of_id).where(KifuAlbum.id == 25055)) is None
        assert conn.scalar(select(KifuAlbumRankSnapshot.id)) is None


def test_production_cli_uses_es_coordinator_for_apply_and_undo(engine, monkeypatch, tmp_path):
    from datetime import datetime, timezone
    import json

    cli, manifest, sync, es = _search_repair_fixture(engine, monkeypatch)
    path = tmp_path / "reviewed.json"
    cli.export_manifest(manifest, path)
    digest = cli.manifest_sha256(manifest)
    preflight = tmp_path / "preflight.json"
    preflight.write_text(
        json.dumps(
            {
                "format": "kifu-deployed-writer-preflight-v1",
                "database_identity": manifest["database_identity"],
                "manifest_sha256": digest,
                "status": "compatible",
                "verified_contracts": list(cli.CONTRACTS),
                "deployed_build_sha": "a" * 40,
                "checked_at": datetime.now(timezone.utc).isoformat(),
            }
        )
    )
    common = [
        "--database-url",
        str(engine.url),
        "--manifest",
        str(path),
        "--sha256",
        digest,
        "--audit-dir",
        str(tmp_path / "audit"),
    ]
    assert cli.main(["apply", *common, "--writer-preflight", str(preflight)]) == 0
    assert es.events == ["pending", "refresh", "ready"]
    assert cli.main(["apply", *common, "--writer-preflight", str(preflight)]) == 0
    assert cli.main(["undo", *common]) == 0
    assert es.events == ["pending", "refresh", "ready"] * 3
    with engine.connect() as conn:
        assert conn.scalar(select(KifuAlbum.duplicate_of_id).where(KifuAlbum.id == 25055)) is None
