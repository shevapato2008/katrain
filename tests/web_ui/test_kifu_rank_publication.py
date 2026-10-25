"""Native v2 ranks are portable, journaled and independent of current profile."""

from copy import deepcopy

import pytest
from sqlalchemy import select

from katrain.kifu_ingest import catalog
from katrain.kifu_ingest.preparation import derive_metadata
from katrain.kifu_ingest.ranks import FORMAT_V2, freeze_game_ranks
from katrain.web.core.models_db import KifuAlbum, KifuAlbumRankSnapshot, KifuNameBatch, KifuPlayerRankHistory
from katrain.web.kifu import name_batch
from katrain.web.kifu.name_candidates import canonical_sha256
from tests.web_ui.test_kifu_incremental_catalog import make_engine, manifest, publish, state


def ranked(source_id="99999001", raw="7p", day="2026-02-01", library=None):
    value = manifest(source_id, black="Black")
    game = value["games"][0]
    from hashlib import sha256

    sgf = game["sgf_content"].replace("DT[2026-02-01]", f"BR[{raw}]DT[{day}]")
    game.update(
        sgf_content=sgf,
        sgf_sha256=sha256(sgf.encode()).hexdigest(),
        raw_sha256=sha256(sgf.encode()).hexdigest(),
        origin_path=f"data/kifu-album/19x19/{source_id}.sgf",
        metadata=derive_metadata(sgf),
        identities={"black": {"canonical_name": "Black"}, "white": {"canonical_name": "White"}},
    )
    decision = freeze_game_ranks(game, library_facts=library or {}, matched_at="2026-10-01T00:00:00Z")
    game.update({key: decision[key] for key in ("rank_snapshots", "rank_observations")})
    value.update(format=FORMAT_V2, rank_facts=decision["rank_facts"])
    return value


def rank_state(engine):
    with engine.connect() as conn:
        return {
            model.__tablename__: [
                name_batch._image(conn, model.__table__, key) for key in conn.scalars(select(model.id))
            ]
            for model in (KifuPlayerRankHistory, KifuAlbumRankSnapshot)
        }


def test_v2_source_history_snapshots_date_journal_and_cross_database_ids(tmp_path):
    value = ranked()
    for suffix, players in (("a", (17, 18)), ("b", (217, 218))):
        engine = make_engine(tmp_path / f"{suffix}.db", players=players)
        before = rank_state(engine)
        result = publish(engine, value)
        with engine.connect() as conn:
            history = conn.execute(select(KifuPlayerRankHistory)).mappings().one()
            assert history["player_id"] == players[0]
            assert history["source_as_of"].isoformat() == "2026-02-01"
            snapshot = (
                conn.execute(select(KifuAlbumRankSnapshot).where(KifuAlbumRankSnapshot.side == "black"))
                .mappings()
                .one()
            )
            assert snapshot["rank_fact_id"] == history["id"]
            assert snapshot["snapshot"]["player_ref"] == {"canonical_name": "Black"}
        assert publish(engine, value) == result
        assert catalog.undo_publication(engine, result["batch_id"])["status"] == "undone"
        assert rank_state(engine) == before


def test_old_pack_replay_keeps_frozen_seven_while_current_advances_to_eight(tmp_path):
    engine = make_engine(tmp_path / "replay.db")
    old = ranked()
    receipt = publish(engine, old)
    publish(engine, ranked("99999002", "8p", "2026-03-01"))
    before = rank_state(engine)
    assert publish(engine, old) == receipt
    assert rank_state(engine) == before
    from katrain.web.kifu.player_ranks import lookup_library_rank_facts

    latest = lookup_library_rank_facts(engine, [{"id": 17, "canonical_name": "Black", "status": "qualified"}])
    next_blank = ranked("99999003", "", "2026-04-01", {"Black": latest[17]["fact"]})
    assert next_blank["games"][0]["rank_snapshots"]["black"]["display_rank"] == "8p"
    with engine.connect() as conn:
        assert conn.scalar(select(KifuPlayerRankHistory.rank_value).where(KifuPlayerRankHistory.is_current)) == 8
        snapshot = conn.scalar(
            select(KifuAlbumRankSnapshot.snapshot).where(
                KifuAlbumRankSnapshot.album_id == receipt["games"][0]["album_id"], KifuAlbumRankSnapshot.side == "black"
            )
        )
        assert snapshot["display_rank"] == "7p"


def test_source_alias_rank_publishes_under_the_existing_canonical_owner(tmp_path):
    engine = make_engine(tmp_path / "alias-rank.db")
    value = ranked()
    game = value["games"][0]
    from hashlib import sha256

    game["sgf_content"] = game["sgf_content"].replace("PB[Black]", "PB[Black Alias]")
    game["sgf_sha256"] = game["raw_sha256"] = sha256(game["sgf_content"].encode()).hexdigest()
    game["metadata"] = derive_metadata(game["sgf_content"])
    decision = freeze_game_ranks(game)
    game.update({key: decision[key] for key in ("rank_snapshots", "rank_observations")})
    value["rank_facts"] = decision["rank_facts"]
    receipt = publish(engine, value)
    assert publish(engine, value) == receipt
    with engine.connect() as conn:
        assert conn.scalar(select(KifuPlayerRankHistory.player_id)) == 17


def test_undo_fact_creator_rejects_later_reference_without_any_mutation(tmp_path):
    engine = make_engine(tmp_path / "dependency.db")
    first = ranked()
    receipt = publish(engine, first)
    fact = next(iter(first["rank_facts"].values()))
    publish(engine, ranked("99999002", "", "2026-03-01", {"Black": fact}))
    before, rank_before = state(engine), rank_state(engine)
    with pytest.raises(ValueError, match="depend|refer"):
        catalog.undo_publication(engine, receipt["batch_id"])
    assert state(engine) == before
    assert rank_state(engine) == rank_before


def test_inactive_older_fact_status_change_is_journaled_and_undone(tmp_path):
    engine = make_engine(tmp_path / "older-conflict.db")
    publish(engine, ranked("99999001", "8p", "2026-03-01"))
    before = rank_state(engine)
    result = publish(engine, ranked("99999002", "9p", "2026-02-01"))
    with engine.connect() as conn:
        current = conn.execute(select(KifuPlayerRankHistory).where(KifuPlayerRankHistory.is_current)).mappings().one()
        assert (current["rank_value"], current["status"]) == (8, "conflict")
    catalog.undo_publication(engine, result["batch_id"])
    assert rank_state(engine) == before


def test_retained_receipt_blocks_fact_undo_even_when_no_later_snapshot_was_written(tmp_path):
    engine = make_engine(tmp_path / "receipt-reference.db")
    first = ranked()
    receipt = publish(engine, first)
    before = rank_state(engine)
    reference = deepcopy(first)
    reference["publication_key"] = "reference-same-frozen-snapshot"
    publish(engine, reference)
    assert rank_state(engine) == before
    full_before = state(engine)
    with pytest.raises(ValueError, match="dependent applied rank receipt"):
        catalog.undo_publication(engine, receipt["batch_id"])
    assert state(engine) == full_before
    assert rank_state(engine) == before


def test_rank_only_correction_has_finite_fast_path_and_preserves_original_receipt(tmp_path, monkeypatch):
    engine = make_engine(tmp_path / "correction.db")
    original = manifest("99999001", black="Black")
    original["games"][0]["origin_path"] = "data/kifu-album/19x19/99999001.sgf"
    original["games"][0]["identities"] = {"black": {"canonical_name": "Black"}, "white": {"canonical_name": "White"}}
    original_receipt = publish(engine, original)
    grade = ranked("99999002", "7p", "2026-03-01")
    publish(engine, grade)
    value = deepcopy(original)
    game = value["games"][0]
    game["identities"] = {"black": {"canonical_name": "Black"}, "white": {"canonical_name": "White"}}
    decision = freeze_game_ranks(game, library_facts={"Black": next(iter(grade["rank_facts"].values()))})
    game.update({key: decision[key] for key in ("rank_snapshots", "rank_observations")})
    game["rank_correction"] = {
        "original_manifest_sha256": canonical_sha256(original),
        "expected_snapshots": {"black": None, "white": None},
    }
    value.update(
        format=FORMAT_V2, mode="rank_only", publication_key="correction-one", rank_facts=decision["rank_facts"]
    )
    before = state(engine)
    ranks_before = rank_state(engine)
    for name in ("warm_sgf_cache", "_identity_indexes", "_source_records", "_apply_decisions"):
        monkeypatch.setattr(catalog, name, lambda *a, **kw: pytest.fail("rank-only entered whole-library/name path"))
    wrong_cas = deepcopy(value)
    wrong_cas["games"][0]["rank_correction"]["expected_snapshots"]["black"] = "f" * 64
    with pytest.raises(ValueError, match="CAS"):
        publish(engine, wrong_cas)
    wrong_identity = deepcopy(value)
    wrong_game = wrong_identity["games"][0]
    wrong_game["identities"]["black"] = {"canonical_name": "White"}
    wrong_decision = freeze_game_ranks(wrong_game)
    wrong_game.update({key: wrong_decision[key] for key in ("rank_snapshots", "rank_observations")})
    wrong_identity["rank_facts"] = wrong_decision["rank_facts"]
    with pytest.raises(ValueError, match="original canonical identity"):
        publish(engine, wrong_identity)
    assert state(engine) == before
    assert rank_state(engine) == ranks_before
    receipt = publish(engine, value)
    assert receipt["games"][0]["album_id"] == original_receipt["games"][0]["album_id"]
    assert receipt["games"][0]["action"] == "rank_corrected"
    assert publish(engine, value) == receipt
    after = state(engine)
    assert after[KifuAlbum.__table__] == before[KifuAlbum.__table__]
    assert after[KifuNameBatch.__table__][: len(before[KifuNameBatch.__table__])] == before[KifuNameBatch.__table__]
    catalog.undo_publication(engine, receipt["batch_id"])
    assert rank_state(engine)[KifuAlbumRankSnapshot.__tablename__] == [
        row
        for row in rank_state(engine)[KifuAlbumRankSnapshot.__tablename__]
        if row["album_id"] != receipt["games"][0]["album_id"]
    ]
