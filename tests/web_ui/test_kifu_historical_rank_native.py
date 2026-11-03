"""Native v3 frozen ranks share portable decisions with repair and API readers."""

from copy import deepcopy
from hashlib import sha256

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from katrain.kifu_ingest import ranks
from katrain.kifu_ingest.preparation import derive_metadata
from katrain.web.core import models_db as m
from katrain.web.kifu.historical_ranks import SNAPSHOT_VERSION
from tests.web_ui.test_kifu_incremental_catalog import make_engine, publish
from tests.web_ui.test_kifu_rank_snapshots_api import detail, listing

WHEN = "2026-11-03T00:00:00+00:00"


def prepared(engine, item="99101", raw="", day="2026-02-01"):
    sgf = f"(;SZ[19]PB[Black Alias]PW[White Alias]BR[{raw}]EV[Summer Cup]DT[{day}];B[bb];W[cc])"
    game = {
        "source_key": "19x19",
        "source_item_id": item,
        "origin_path": f"data/kifu-album/19x19/{item}.sgf",
        "sgf_content": sgf,
        "raw_sha256": sha256(sgf.encode()).hexdigest(),
        "sgf_sha256": sha256(sgf.encode()).hexdigest(),
        "metadata": derive_metadata(sgf),
        "identities": {"black": {"canonical_name": "Black"}, "white": {"canonical_name": "White"}},
    }
    freeze = getattr(ranks, "freeze_historical_game_ranks", None)
    assert freeze is not None, "native preparation must freeze portable historical v3 decisions"
    with engine.connect() as conn:
        frozen = freeze(conn, [game], matched_at=WHEN)[0]
    game.update({k: frozen[k] for k in ("rank_snapshots", "rank_observations")})
    return {
        "format": ranks.FORMAT_V2,
        "publication_key": f"v3-{item}",
        "games": [game],
        "decisions": [],
        "rank_facts": frozen["rank_facts"],
    }


def seed_prior(engine, raw="7p", day="2026-01-01", ident=12):
    sgf = f"(;PB[Black Alias]PW[White Alias]BR[{raw}]DT[{day}];B[aa])"
    path = f"data/kifu-album/19x19/{ident}.sgf"
    with engine.begin() as conn:
        source_id = conn.scalar(select(m.KifuSource.id).where(m.KifuSource.source_key == "19x19"))
        if source_id is None:
            source_id = conn.execute(m.KifuSource.__table__.insert().values(source_key="19x19")).inserted_primary_key[0]
        conn.execute(
            m.KifuAlbum.__table__.insert().values(
                id=ident,
                player_black="Black Alias",
                player_white="White Alias",
                black_player_id=17,
                white_player_id=18,
                black_rank=raw,
                date_played=day,
                date_sort=day,
                sgf_content=sgf,
                source_path=path,
            )
        )
        conn.execute(
            m.KifuAlbumSource.__table__.insert().values(
                album_id=ident, source_id=source_id, origin_path=path, match_method="source_path"
            )
        )


def test_native_v3_test_prod_replay_and_api_share_frozen_asof(tmp_path):
    engines = [make_engine(tmp_path / f"{name}.db") for name in ("test", "prod")]
    for engine in engines:
        seed_prior(engine)
    value = prepared(engines[0])
    snapshot = value["games"][0]["rank_snapshots"]["black"]
    assert (snapshot["version"], snapshot["origin"], snapshot["display_rank"]) == (
        SNAPSHOT_VERSION,
        "historical_prior",
        "7p",
    )
    assert "rank_fact_sha256" not in snapshot and value["rank_facts"] == {}
    for engine in engines:
        receipt = publish(engine, value)
        assert publish(engine, value) == receipt
        with Session(engine) as db:
            row = (
                db.query(m.KifuAlbumRankSnapshot)
                .filter_by(album_id=receipt["games"][0]["album_id"], side="black")
                .one()
            )
            assert row.rank_fact_id is None
            artifact = db.get(m.KifuNameBatch, receipt["batch_id"]).reviewed_artifact
            assert artifact["basis_bindings"][0]["basis"][0]["album_id"] == 12
            page = listing(db)
            assert page.preview.id == row.album_id
            for card in (
                next(item for item in page.items if item.id == row.album_id),
                page.preview,
                detail(db, row.album_id),
            ):
                assert card.display_black_rank == "7p"
                assert card.black_rank_source["policy_version"] == snapshot["policy_version"]
                assert card.black_rank_source["source_as_of"] == "2026-01-01"
        # This new, trusted original would invalidate initial qualification.
        # Applied replay validates frozen bindings without selecting a new rank.
        seed_prior(engine, raw="9d", day="2026-01-15", ident=991)
        from katrain.web.kifu.historical_ranks import verify_initial_rank_decisions

        with engine.connect() as conn:
            with pytest.raises(ValueError, match="qualification/cohort changed"):
                verify_initial_rank_decisions(
                    conn,
                    ranks.historical_game_targets(value["games"]),
                    [value["games"][0]["rank_snapshots"][side] for side in ("black", "white")],
                )
        assert publish(engine, value) == receipt


def test_initial_historical_qualification_drift_fails_without_writes(tmp_path):
    engine = make_engine(tmp_path / "drift.db")
    seed_prior(engine)
    value = prepared(engine)
    with engine.begin() as conn:
        conn.execute(
            m.KifuAlbum.__table__.update()
            .where(m.KifuAlbum.id == 12)
            .values(black_rank="8p", sgf_content="(;PB[Black Alias]PW[White Alias]BR[8p]DT[2026-01-01];B[aa])")
        )
    with pytest.raises(ValueError, match="qualification/cohort changed"):
        publish(engine, value)
    with engine.connect() as conn:
        assert (
            conn.scalar(select(m.KifuAlbum.id).where(m.KifuAlbum.source_path == value["games"][0]["origin_path"]))
            is None
        )


@pytest.mark.parametrize("damage", ["owner", "date", "body", "hash"])
def test_v3_manifest_rejects_wrong_portable_binding(tmp_path, damage):
    engine = make_engine(tmp_path / f"{damage}.db")
    value = prepared(engine, raw="9p")
    snapshot = value["games"][0]["rank_snapshots"]["black"]
    if damage == "owner":
        snapshot["player_ref"] = {"canonical_name": "White"}
    elif damage == "date":
        snapshot["target_date"] = "2020-01-01"
    elif damage == "body":
        snapshot["source_ref"]["sgf_sha256"] = "a" * 64
    else:
        snapshot["content_sha256"] = "a" * 64
    if damage != "hash":
        snapshot["content_sha256"] = ranks.snapshot_sha256(snapshot)
    with pytest.raises(ValueError):
        publish(engine, value)


def test_checkpoint_prefers_legacy_then_freezes_new_policy_separately(tmp_path):
    from katrain.kifu_ingest.staging import Stage

    engine = make_engine(tmp_path / "stage.db")
    stage = Stage(tmp_path / "staged")
    value = prepared(engine, raw="9p")
    game = value["games"][0]
    legacy = ranks.freeze_game_ranks(game, matched_at=WHEN)
    stage.save_rank_decision(game, legacy)
    old_path = stage._rank_decision_path(game)[0]
    original = old_path.read_bytes()
    assert stage.load_rank_decision(game) == legacy
    with pytest.raises(ValueError, match="already frozen"):
        stage.save_rank_decision(
            game,
            {
                "rank_snapshots": game["rank_snapshots"],
                "rank_observations": game["rank_observations"],
                "rank_facts": value["rank_facts"],
            },
        )
    assert old_path.read_bytes() == original
    new = prepared(engine, item="99102", raw="8p")
    new_game = new["games"][0]
    frozen = {
        "rank_snapshots": new_game["rank_snapshots"],
        "rank_observations": new_game["rank_observations"],
        "rank_facts": new["rank_facts"],
    }
    stage.save_rank_decision(new_game, frozen)
    assert stage._rank_decision_path(new_game, historical=True)[0].exists()
    assert stage.load_rank_decision(new_game) == frozen


@pytest.mark.asyncio
async def test_new_staged_preparation_uses_original_history_before_name_calls(tmp_path, monkeypatch):
    from katrain.kifu_ingest import orchestration
    from katrain.kifu_ingest.staging import Stage
    from tests.test_kifu_incremental_decision_resume import _stage_game, ReviewedNames, _qualified_target

    engine = make_engine(tmp_path / "prepare.db")
    seed_prior(engine)
    stage = Stage(tmp_path / "prepare-stage")
    item = _stage_game(stage, "99999001", black="Black Alias", white="White Alias", event="Summer Cup")
    monkeypatch.setattr(
        orchestration, "lookup_library_rank_facts", lambda *a, **kw: pytest.fail("new preparation read current profile")
    )
    value = await orchestration.prepare_staged_games(
        [item],
        engine=engine,
        client=object(),
        names=ReviewedNames("native-v3"),
        check_identities=_qualified_target,
        decision_store=stage,
    )
    assert value["games"][0]["rank_snapshots"]["black"]["origin"] == "historical_prior"
    assert value["games"][0]["rank_snapshots"]["black"]["display_rank"] == "7p"
    monkeypatch.setattr(
        orchestration, "_historical_rank_decisions", lambda *a: pytest.fail("frozen retry reread history")
    )
    assert (
        await orchestration.prepare_staged_games(
            [item],
            engine=engine,
            client=object(),
            names=ReviewedNames("native-v3-retry"),
            check_identities=_qualified_target,
            decision_store=stage,
        )
        == value
    )


def test_native_undo_protects_original_basis_even_without_fact_reference(tmp_path):
    from katrain.kifu_ingest.catalog import undo_publication

    engine = make_engine(tmp_path / "undo.db")
    source = prepared(engine, item="99201", raw="7p", day="2026-01-01")
    a = publish(engine, source)
    target = prepared(engine, item="99202", day="2026-02-01")
    assert target["games"][0]["rank_snapshots"]["black"]["origin"] == "historical_prior"
    b = publish(engine, target)
    with pytest.raises(ValueError, match="basis dependency"):
        undo_publication(engine, a["batch_id"])
    undo_publication(engine, b["batch_id"])
    assert undo_publication(engine, a["batch_id"])["status"] == "undone"


@pytest.mark.parametrize("damage", ["owner", "raw", "date", "sgf", "journal", "authority", "row_hash"])
def test_api_v3_invalid_overlay_falls_back_honestly(tmp_path, damage):
    engine = make_engine(tmp_path / f"api-{damage}.db")
    seed_prior(engine)
    value = prepared(engine)
    receipt = publish(engine, value)
    album_id = receipt["games"][0]["album_id"]
    with engine.begin() as conn:
        if damage == "owner":
            conn.execute(m.KifuAlbum.__table__.update().where(m.KifuAlbum.id == album_id).values(black_player_id=18))
        elif damage == "raw":
            conn.execute(m.KifuAlbum.__table__.update().where(m.KifuAlbum.id == album_id).values(black_rank="9d"))
        elif damage == "date":
            conn.execute(
                m.KifuAlbum.__table__.update().where(m.KifuAlbum.id == album_id).values(date_played="2026-03-01")
            )
        elif damage == "sgf":
            conn.execute(
                m.KifuAlbum.__table__.update()
                .where(m.KifuAlbum.id == album_id)
                .values(sgf_content=value["games"][0]["sgf_content"].replace("B[bb]", "B[cc]"))
            )
        elif damage == "journal":
            conn.execute(
                m.KifuNameChange.__table__.update()
                .where(
                    m.KifuNameChange.batch_id == receipt["batch_id"],
                    m.KifuNameChange.target_table == m.KifuAlbumRankSnapshot.__tablename__,
                )
                .values(after_image={})
            )
        elif damage == "row_hash":
            conn.execute(
                m.KifuAlbumRankSnapshot.__table__.update()
                .where(m.KifuAlbumRankSnapshot.album_id == album_id)
                .values(snapshot_sha256="a" * 64)
            )
        else:
            conn.execute(
                m.KifuNameBatch.__table__.update()
                .where(m.KifuNameBatch.id == receipt["batch_id"])
                .values(status="undone")
            )
    with Session(engine) as db:
        card = detail(db, album_id)
        assert card.display_black_rank == ("9d" if damage == "raw" else "")
        assert card.black_rank_origin != "historical_prior"


def test_v3_observation_can_share_earlier_fact_representative_with_legacy_checkpoint(tmp_path):
    engine = make_engine(tmp_path / "representative.db")
    fresh = prepared(engine, item="99301", raw="7p")
    original = ranks.freeze_game_ranks(fresh["games"][0], matched_at="2026-10-01T00:00:00+00:00")
    fact = next(iter(original["rank_facts"].values()))
    old = prepared(engine, item="99302")
    legacy = ranks.freeze_game_ranks(
        old["games"][0], library_facts={"Black": fact}, matched_at="2026-10-02T00:00:00+00:00"
    )
    old["games"][0].update({key: legacy[key] for key in ("rank_snapshots", "rank_observations")})
    mixed = {
        **fresh,
        "games": [old["games"][0], fresh["games"][0]],
        "rank_facts": ranks.merge_rank_facts(legacy["rank_facts"], fresh["rank_facts"]),
    }
    ranks.validate_manifest_ranks(mixed)
    assert next(iter(mixed["rank_facts"].values()))["observed_at"] == "2026-10-01T00:00:00+00:00"


@pytest.mark.parametrize("mutation", ["journal", "later_correction"])
def test_replay_rejects_changed_journal_or_later_cas_without_writing(tmp_path, mutation):
    from katrain.web.kifu.name_candidates import canonical_sha256

    engine = make_engine(tmp_path / f"replay-{mutation}.db")
    value = prepared(engine, raw="7p")
    receipt = publish(engine, value)
    if mutation == "journal":
        with engine.begin() as conn:
            conn.execute(
                m.KifuNameChange.__table__.update()
                .where(
                    m.KifuNameChange.batch_id == receipt["batch_id"],
                    m.KifuNameChange.target_table == m.KifuAlbumRankSnapshot.__tablename__,
                )
                .values(after_image={})
            )
    else:
        correction = deepcopy(value)
        correction.update(mode="rank_only", publication_key="explicit-v3-correction")
        correction["games"][0]["rank_correction"] = {
            "original_manifest_sha256": canonical_sha256(value),
            "expected_snapshots": {
                side: snapshot["content_sha256"] for side, snapshot in value["games"][0]["rank_snapshots"].items()
            },
        }
        publish(engine, correction)
    with engine.connect() as conn:
        before = [dict(row) for row in conn.execute(select(m.KifuAlbumRankSnapshot.__table__)).mappings()]
    with pytest.raises(ValueError):
        publish(engine, value)
    with engine.connect() as conn:
        assert [dict(row) for row in conn.execute(select(m.KifuAlbumRankSnapshot.__table__)).mappings()] == before


@pytest.mark.parametrize(
    "embedded,raw,expected,origin",
    [(True, "", "9p", "historical_type"), (False, "9p", "9p", "source"), (False, "", "", "unknown")],
)
def test_native_derived_rank_and_source_only_date_keep_original_semantics(tmp_path, embedded, raw, expected, origin):
    engine = make_engine(tmp_path / f"metadata-{embedded}-{raw}.db")
    seed_prior(engine)
    value = prepared(engine, item="99401")
    game = value["games"][0]
    name = "Black Alias九段" if embedded else "Black Alias"
    date = "DT[2026-02-01]" if embedded else ""
    sgf = f"(;SZ[19]PB[{name}]PW[White Alias]BR[{raw}]EV[Summer Cup]{date};B[bb];W[cc])"
    game.update(
        sgf_content=sgf,
        sgf_sha256=sha256(sgf.encode()).hexdigest(),
        raw_sha256=sha256(sgf.encode()).hexdigest(),
        source_metadata=None if embedded else {"playTime": {"date": {"year": 2026, "month": 2, "day": 1}}},
    )
    game["metadata"] = derive_metadata(sgf, game["source_metadata"])
    with engine.connect() as conn:
        frozen = ranks.freeze_historical_game_ranks(conn, [game], matched_at=WHEN)[0]
    game.update({key: frozen[key] for key in ("rank_snapshots", "rank_observations")})
    value["rank_facts"] = frozen["rank_facts"]
    snapshot = game["rank_snapshots"]["black"]
    assert (snapshot["display_rank"], snapshot["origin"]) == (expected, origin)
    if not embedded:
        assert snapshot["target_date"] is None and not snapshot["basis"]
    receipt = publish(engine, value)
    with Session(engine) as db:
        card = detail(db, receipt["games"][0]["album_id"])
        assert (card.display_black_rank, card.black_rank_origin) == (expected, origin)
        assert card.sgf_content == sgf and card.black_rank == game["metadata"].get("black_rank")
