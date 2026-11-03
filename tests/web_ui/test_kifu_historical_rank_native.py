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


@pytest.mark.parametrize(
    "other_day,other_rank,expected",
    [
        ("2024-11-03", "7段", (("source", "7段"), ("source", "9段"))),
        ("2024-11-02", "7段", (("historical_type", "7p"), ("historical_type", "9p"))),
        ("2024-11-03", "9段", (("historical_type", "9p"), ("historical_type", "9p"))),
    ],
)
def test_native_batch_preparation_publishes_original_bare_consistency(tmp_path, other_day, other_rank, expected):
    engine = make_engine(tmp_path / "bare-consistency.db")
    seed_prior(engine, raw="6p", day="2000-01-06")
    values = [
        prepared(engine, item="99701", raw=other_rank, day=other_day),
        prepared(engine, item="99702", raw="9段", day="2024-11-03"),
    ]
    games = [value["games"][0] for value in values]
    with engine.connect() as conn:
        frozen = ranks.freeze_historical_game_ranks(conn, games, matched_at=WHEN)
    for game, result, grade in zip(games, frozen, expected):
        game.update({key: result[key] for key in ("rank_snapshots", "rank_observations")})
        snapshot = game["rank_snapshots"]["black"]
        assert (snapshot["origin"], snapshot["display_rank"]) == grade
        if snapshot["origin"] == "source":
            assert snapshot["refusal_reason"] == "incompatible_bare_observation" and not snapshot["basis"]
    manifest = {
        **values[0],
        "games": games,
        "rank_facts": ranks.merge_rank_facts(*(result["rank_facts"] for result in frozen)),
    }
    receipt = publish(engine, manifest)
    with Session(engine) as db:
        for published, grade, game in zip(receipt["games"], expected, games):
            card = detail(db, published["album_id"])
            assert (card.black_rank_origin, card.display_black_rank) == grade
            assert card.sgf_content == game["sgf_content"]
    assert publish(engine, manifest) == receipt


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


def repaired_legacy_publication(
    engine, *, games=1, source_metadata=None, before_repair=None, repair_games=None, professional_black=True
):
    """Publish frozen V1 slots, then apply an actual reviewed historical repair."""
    from datetime import datetime, timezone
    from katrain.web.kifu import historical_rank_repair as repair, player_ranks
    from tests.test_kifu_rank_sources import CAPTURES

    identity_evidence = {}
    if professional_black:
        # The local synthetic owner has an independently approved official
        # subject capture. Keep existing five-language fixture proofs intact.
        capture = deepcopy(next(item for item in CAPTURES if item["canonical_name"] == "高星"))
        with engine.begin() as conn:
            registry_id = conn.execute(
                m.KifuNameSourceRegistry.__table__.insert().values(
                    version="supersession-official-fixture", sha256="d" * 64, registry={}
                )
            ).inserted_primary_key[0]
            owner = {"kind": "player", "id": 17}
            payload = {
                "candidate": {"owner": owner, "display_name": capture["approved_name"]},
                "research": {
                    "owner": owner,
                    "candidate_name": capture["approved_name"],
                    "original_name": capture["original_name"],
                    "source_checks": [{"identity_bridges": [capture["capture"]]}],
                },
            }
            evidence_id = conn.execute(
                m.KifuNameResearchEvidence.__table__.insert().values(
                    player_id=17,
                    lang="xx",
                    revision=1,
                    source_registry_id=registry_id,
                    candidate_name=capture["approved_name"],
                    decision_kind="conventional",
                    generation_rule_version="none",
                    research_payload=payload,
                    producer_id="fixture-producer",
                    producer_model="test",
                    reviewer_id="fixture-reviewer",
                    reviewer_model="test",
                    reviewed_at=datetime(2026, 11, 3, tzinfo=timezone.utc),
                    review_status="approved",
                )
            ).inserted_primary_key[0]
            conn.execute(
                m.KifuPlayerName.__table__.insert().values(
                    player_id=17,
                    lang="xx",
                    display_name=capture["approved_name"],
                    status="verified",
                    revision=1,
                    evidence_id=evidence_id,
                    decision_kind="conventional",
                    generation_rule_version="none",
                )
            )
            identity_evidence["Black"] = player_ranks.lookup_professional_identity_evidence(conn, [17])[17]
    values = []
    for index in range(games):
        value = prepared(engine, item=str(99600 + index), raw="九段")
        game = value["games"][0]
        sgf = game["sgf_content"].replace("DT[2026-02-01]", f"WR[七段]C[fixture-{index}]")
        game.update(
            sgf_content=sgf,
            raw_sha256=sha256(sgf.encode()).hexdigest(),
            sgf_sha256=sha256(sgf.encode()).hexdigest(),
            source_metadata=(
                deepcopy(source_metadata)
                if source_metadata is not None
                else {"playTime": {"date": {"year": 2026, "month": 2, "day": 1}}}
            ),
        )
        game["metadata"] = derive_metadata(sgf, game["source_metadata"])
        frozen = ranks.freeze_game_ranks(game, matched_at=WHEN, identity_evidence=identity_evidence)
        game.update({key: frozen[key] for key in ("rank_snapshots", "rank_observations")})
        values.append((value, frozen))
    value = {
        **values[0][0],
        "games": [entry[0]["games"][0] for entry in values],
        "rank_facts": ranks.merge_rank_facts(*(entry[1]["rank_facts"] for entry in values)),
    }
    receipt = publish(engine, value)
    if before_repair is not None:
        before_repair(value, receipt)
    with engine.begin() as conn:
        envelope = repair.prepare_manifest(
            conn,
            matched_at="2026-11-04T00:00:00Z",
            album_ids=[game["album_id"] for game in receipt["games"][:repair_games]],
        )
        assert len(envelope["parts"]) == 1
        part = envelope["parts"][0]
        assert len(part["changes"]) == (games if repair_games is None else repair_games) * 2
        result = repair.apply_in_transaction(conn, part, expected_sha256=repair.manifest_sha256(part))
    return value, receipt, part, result


def authority_state(engine):
    from tests.web_ui.test_kifu_incremental_catalog import state
    from tests.web_ui.test_kifu_rank_publication import rank_state

    return state(engine), rank_state(engine)


def test_supersession_exact_applied_historical_repair_replays_original_without_writes(tmp_path):
    from katrain.web.kifu.name_candidates import canonical_sha256

    engine = make_engine(tmp_path / "supersession.db")
    value, receipt, part, _ = repaired_legacy_publication(engine, games=5)
    original = deepcopy(value), deepcopy(receipt), canonical_sha256(value)
    assert value["games"][0]["rank_snapshots"]["black"]["rank_system"] == "professional_dan"
    assert all(change["snapshot_after"]["rank_system"] == "dan_unspecified" for change in part["changes"])
    assert all(change["snapshot_after"]["target_date"] is None for change in part["changes"])
    assert all(change["snapshot_after"]["refusal_reason"] == "untrusted_target_date" for change in part["changes"])
    before = authority_state(engine)
    assert publish(engine, value) == receipt
    assert authority_state(engine) == before
    assert (value, receipt, canonical_sha256(value)) == original


@pytest.mark.parametrize(
    "damage",
    [
        "original_journal",
        "missing_journal",
        "missing_successor",
        "second_hop",
        "before",
        "after",
        "part",
        "binding",
        "pending",
        "undone",
        "generic",
        "owner",
        "raw",
        "sgf",
        "fact",
    ],
)
def test_supersession_rejects_inexact_authority_and_keeps_original_fact_guard(tmp_path, damage):
    engine = make_engine(tmp_path / f"supersession-{damage}.db")
    value, receipt, part, result = repaired_legacy_publication(engine)
    change = part["changes"][0]
    with engine.begin() as conn:
        journal = m.KifuNameChange.__table__
        slot = (journal.c.target_table == m.KifuAlbumRankSnapshot.__tablename__) & (
            journal.c.target_row_id == change["snapshot_before"]["id"]
        )
        if damage in {"original_journal", "missing_journal"}:
            query = journal.delete() if damage == "missing_journal" else journal.update().values(after_image={})
            conn.execute(query.where(slot, journal.c.batch_id == receipt["batch_id"]))
        elif damage == "missing_successor":
            conn.execute(journal.delete().where(slot, journal.c.batch_id == result["batch_id"]))
        elif damage == "second_hop":
            from katrain.web.kifu import historical_rank_repair as repair

            forged = deepcopy(part)
            # Even a self-consistent applied part may not skip through an
            # intermediate successor to reach the original native journal.
            first_after = conn.scalar(
                select(journal.c.after_image).where(slot, journal.c.batch_id == result["batch_id"])
            )
            forged["changes"][0]["snapshot_before"] = first_after
            forged_sha = repair.manifest_sha256(forged)
            conn.execute(
                m.KifuNameBatch.__table__.update()
                .where(m.KifuNameBatch.id == result["batch_id"])
                .values(bundle_sha256=forged_sha, reviewed_artifact=repair._artifact(forged))
            )
            conn.execute(
                m.KifuAlbumRankSnapshot.__table__.update()
                .where(m.KifuAlbumRankSnapshot.native_batch_id == result["batch_id"])
                .values(publication_key="historical-rank:" + forged_sha)
            )
            for row in conn.execute(select(journal).where(journal.c.batch_id == result["batch_id"])).mappings():
                after = {**row["after_image"], "publication_key": "historical-rank:" + forged_sha}
                conn.execute(
                    journal.update()
                    .where(journal.c.id == row["id"])
                    .values(
                        after_image=after,
                        **(
                            {"before_image": first_after}
                            if row["target_row_id"] == change["snapshot_before"]["id"]
                            else {}
                        ),
                    )
                )
        elif damage in {"before", "after"}:
            conn.execute(
                journal.update().where(slot, journal.c.batch_id == result["batch_id"]).values(**{damage + "_image": {}})
            )
        elif damage in {"part", "binding", "generic"}:
            artifact = deepcopy(
                conn.scalar(select(m.KifuNameBatch.reviewed_artifact).where(m.KifuNameBatch.id == result["batch_id"]))
            )
            if damage == "generic":
                artifact["format"] = ranks.FORMAT_V2
            elif damage == "part":
                artifact["part"]["changes"][0]["snapshot_before"]["publication_key"] = "forged"
            else:
                artifact["part"]["basis_bindings"][0]["target"]["source_id"] += 1
                artifact["part"]["basis_bindings"][0]["content_sha256"] = ranks.snapshot_sha256(
                    artifact["part"]["basis_bindings"][0]
                )
            conn.execute(
                m.KifuNameBatch.__table__.update()
                .where(m.KifuNameBatch.id == result["batch_id"])
                .values(reviewed_artifact=artifact)
            )
        elif damage in {"pending", "undone"}:
            conn.execute(
                m.KifuNameBatch.__table__.update().where(m.KifuNameBatch.id == result["batch_id"]).values(status=damage)
            )
        elif damage == "fact":
            conn.execute(m.KifuPlayerRankHistory.__table__.update().values(rank_value=1))
        else:
            changes = {
                "owner": {"black_player_id": 18},
                "raw": {"black_rank": "8段"},
                "sgf": {"sgf_content": value["games"][0]["sgf_content"].replace("B[bb]", "B[dd]")},
            }
            conn.execute(
                m.KifuAlbum.__table__.update()
                .where(m.KifuAlbum.id == receipt["games"][0]["album_id"])
                .values(**changes[damage])
            )
    before = authority_state(engine)
    with pytest.raises(ValueError, match="rank fact content/hash mismatch" if damage == "fact" else None):
        publish(engine, value)
    assert authority_state(engine) == before


def test_publication_context_is_db_derived_and_read_only(tmp_path, monkeypatch):
    from katrain.kifu_ingest import catalog
    from katrain.web.kifu import historical_rank_repair as repair
    from katrain.web.kifu.name_candidates import canonical_sha256

    engine = make_engine(tmp_path / "context.db")
    value, receipt, _, _ = repaired_legacy_publication(engine, games=2)
    resolver = getattr(catalog, "resolve_rank_publication_context", None)
    assert callable(resolver), "bounded read-only publication context resolver is missing"
    before = authority_state(engine)
    monkeypatch.setattr(repair, "_lock_writer", lambda *a, **kw: pytest.fail("context acquired writer lock"))
    monkeypatch.setattr(
        historical_ranks := __import__("katrain.web.kifu.historical_ranks", fromlist=[""]),
        "verify_initial_rank_decisions",
        lambda *a, **kw: pytest.fail("context reselected initial decisions"),
    )
    context = resolver(engine, canonical_sha256(value), canonical_sha256(receipt))
    assert context["version"] == "kifu-rank-publication-context-v1"
    assert context["manifest_sha256"] == canonical_sha256(value)
    assert context["receipt_sha256"] == canonical_sha256(receipt)
    assert context["content_sha256"] == ranks.snapshot_sha256(context)
    assert len(context["slots"]) == 4
    assert {slot["expected"]["rank"] for slot in context["slots"]} == {"9段", "7段"}
    assert all(slot["predecessor_after_sha256"] == slot["successor_before_sha256"] for slot in context["slots"])
    assert authority_state(engine) == before
    with pytest.raises(ValueError):
        resolver(engine, canonical_sha256(value), "a" * 64)


def test_supersession_partial_repair_keeps_unchanged_slots_exact(tmp_path):
    from katrain.kifu_ingest import catalog
    from katrain.web.kifu import historical_rank_repair as repair
    from katrain.web.kifu.name_candidates import canonical_sha256

    engine = make_engine(tmp_path / "partial.db")
    captured = {}

    def before_repair(value, receipt):
        # Keep only four games in the legitimate finite repair below.
        captured.update(value=value, receipt=receipt)
        context = catalog.resolve_rank_publication_context(engine, canonical_sha256(value), canonical_sha256(receipt))
        assert context["slots"] == []

    value, receipt, part, result = repaired_legacy_publication(
        engine, games=18, before_repair=before_repair, repair_games=4
    )
    before = authority_state(engine)
    assert publish(engine, value) == receipt
    context = catalog.resolve_rank_publication_context(engine, canonical_sha256(value), canonical_sha256(receipt))
    assert len(context["slots"]) == 8
    assert len(receipt["games"]) * 2 - len(context["slots"]) == 28
    assert authority_state(engine) == before


def test_supersession_rejects_self_consistently_rehashed_false_binding(tmp_path):
    from katrain.web.kifu import historical_rank_repair as repair

    engine = make_engine(tmp_path / "rehashed.db")
    value, _, part, result = repaired_legacy_publication(engine)
    forged = deepcopy(part)
    for change in forged["changes"]:
        binding = change["basis_binding"]
        binding["target"]["source_id"] += 100
        binding["content_sha256"] = ranks.snapshot_sha256(binding)
    forged["basis_bindings"] = [change["basis_binding"] for change in forged["changes"]]
    forged_sha = repair.manifest_sha256(forged)
    with engine.begin() as conn:
        conn.execute(
            m.KifuNameBatch.__table__.update()
            .where(m.KifuNameBatch.id == result["batch_id"])
            .values(bundle_sha256=forged_sha, reviewed_artifact=repair._artifact(forged))
        )
        conn.execute(
            m.KifuAlbumRankSnapshot.__table__.update()
            .where(m.KifuAlbumRankSnapshot.native_batch_id == result["batch_id"])
            .values(publication_key="historical-rank:" + forged_sha)
        )
        for row in conn.execute(
            select(m.KifuNameChange.__table__).where(m.KifuNameChange.batch_id == result["batch_id"])
        ).mappings():
            after = {**row["after_image"], "publication_key": "historical-rank:" + forged_sha}
            conn.execute(
                m.KifuNameChange.__table__.update().where(m.KifuNameChange.id == row["id"]).values(after_image=after)
            )
    before = authority_state(engine)
    with pytest.raises(ValueError, match="exact target/basis binding changed"):
        publish(engine, value)
    assert authority_state(engine) == before


def test_publication_context_shared_body_cache_and_pre_fetch_limits(tmp_path, monkeypatch):
    import time
    from sqlalchemy import event
    from katrain.kifu_ingest import catalog
    from katrain.web.kifu import historical_ranks
    from katrain.web.kifu.name_candidates import canonical_sha256

    engine = make_engine(tmp_path / "resource.db")
    value, receipt, _, _ = repaired_legacy_publication(engine, games=5)
    budgets, reads, statements = [], [], []
    original_init = historical_ranks.EvidenceBudget.__init__

    def budget_init(self, **kwargs):
        original_init(self, **kwargs)
        budgets.append(self)

    def observe(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)
        if statement.splitlines()[0].strip() == "SELECT kifu_albums.sgf_content":
            reads.append(parameters)
        assert not statement.lstrip().upper().startswith(("INSERT ", "UPDATE ", "DELETE ", "LOCK "))
        assert "FOR UPDATE" not in statement.upper()

    monkeypatch.setattr(historical_ranks.EvidenceBudget, "__init__", budget_init)
    event.listen(engine, "before_cursor_execute", observe)
    try:
        context = catalog.resolve_rank_publication_context(engine, canonical_sha256(value), canonical_sha256(receipt))
        assert len(context["slots"]) == 10 and len(budgets) == 1
        assert len(reads) == 5
        assert budgets[0].used_bytes == sum(len(game["sgf_content"].encode()) for game in value["games"])
        with pytest.raises(ValueError, match="deadline"):
            catalog.resolve_rank_publication_context(
                engine, canonical_sha256(value), canonical_sha256(receipt), deadline=time.monotonic() - 1
            )
        statements.clear()
        monkeypatch.setattr(historical_ranks, "MAX_SCALAR_BYTES", 100)
        with pytest.raises(ValueError, match="JSON resource"):
            catalog.resolve_rank_publication_context(engine, canonical_sha256(value), canonical_sha256(receipt))
        assert not any(statement.startswith("SELECT kifu_name_batches.id,") for statement in statements)
    finally:
        event.remove(engine, "before_cursor_execute", observe)


def test_publication_context_disposable_postgresql_repeatable_read_only_snapshot(monkeypatch):
    """Opt-in PostgreSQL proof stays consistent during a concurrent row change."""
    import os
    from uuid import uuid4
    from sqlalchemy import create_engine, text
    from katrain.kifu_ingest import catalog
    from katrain.web.kifu import historical_rank_repair as repair
    from katrain.web.kifu.name_candidates import canonical_sha256
    from tests.web_ui import test_kifu_incremental_catalog as fixture_catalog

    dsn = os.getenv("KIFU_STANDARDIZATION_TEST_PG_DSN")
    if not dsn:
        pytest.skip("set KIFU_STANDARDIZATION_TEST_PG_DSN for disposable PostgreSQL verification")
    schema = "rank_publication_context_" + uuid4().hex
    control = create_engine(dsn, hide_parameters=True)
    with control.begin() as admin:
        admin.execute(text(f"CREATE SCHEMA {schema}"))
    engine = create_engine(
        dsn, connect_args={"options": f"-csearch_path={schema}"}, isolation_level="READ COMMITTED", hide_parameters=True
    )
    try:
        # Use the existing exact catalog fixture against this UUID schema.
        with monkeypatch.context() as patch:
            patch.setattr(fixture_catalog, "create_engine", lambda *args, **kwargs: engine)
            fixture_catalog.make_engine("unused")
        value, receipt, _, _ = repaired_legacy_publication(engine)
        original_identity = repair._database_identity
        observed = []

        def identity(conn):
            observed.append(
                (
                    conn.exec_driver_sql("SHOW transaction_isolation").scalar_one(),
                    conn.exec_driver_sql("SHOW transaction_read_only").scalar_one(),
                )
            )
            assert observed[-1] == ("repeatable read", "on")
            result = original_identity(conn)
            with engine.begin() as concurrent:
                concurrent.execute(
                    m.KifuAlbumRankSnapshot.__table__.update()
                    .where(m.KifuAlbumRankSnapshot.album_id == receipt["games"][0]["album_id"])
                    .values(snapshot_sha256="a" * 64)
                )
            return result

        with monkeypatch.context() as patch:
            patch.setattr(repair, "_database_identity", identity)
            context = catalog.resolve_rank_publication_context(
                engine, canonical_sha256(value), canonical_sha256(receipt)
            )
        assert len(context["slots"]) == 2 and observed == [("repeatable read", "on")]
        with pytest.raises(ValueError):
            catalog.resolve_rank_publication_context(engine, canonical_sha256(value), canonical_sha256(receipt))
        with engine.connect() as conn:
            assert conn.get_isolation_level() == "READ COMMITTED"
            assert conn.exec_driver_sql("SHOW transaction_read_only").scalar_one() == "off"
    finally:
        engine.dispose()
        with control.begin() as admin:
            admin.execute(text(f"DROP SCHEMA {schema} CASCADE"))
        control.dispose()


@pytest.mark.parametrize("damage", ["oversized", "owner"])
def test_publication_context_external_library_fact_preflights_before_legacy_body_read(tmp_path, monkeypatch, damage):
    from katrain.kifu_ingest import catalog
    from katrain.web.kifu import historical_ranks, player_ranks
    from katrain.web.kifu.name_candidates import canonical_sha256
    from tests.web_ui.test_kifu_rank_publication import ranked

    engine = make_engine(tmp_path / f"external-{damage}.db")
    source = ranked("99801", "7p", "2026-01-01")
    source_receipt = publish(engine, source)
    fact = next(iter(source["rank_facts"].values()))
    value = ranked("99802", "", "2026-02-01", {"Black": fact})
    receipt = publish(engine, value)
    context = catalog.resolve_rank_publication_context(engine, canonical_sha256(value), canonical_sha256(receipt))
    assert context["slots"] == []
    with engine.begin() as conn:
        if damage == "oversized":
            conn.execute(
                m.KifuAlbum.__table__.update()
                .where(m.KifuAlbum.id == source_receipt["games"][0]["album_id"])
                .values(sgf_content="x" * (historical_ranks.MAX_SGF_BYTES + 1))
            )
        else:
            conn.execute(
                m.KifuAlbum.__table__.update()
                .where(m.KifuAlbum.id == source_receipt["games"][0]["album_id"])
                .values(black_player_id=18)
            )
    monkeypatch.setattr(
        player_ranks,
        "verify_rank_fact_for_player",
        lambda *a, **kw: pytest.fail("legacy full-body read called before finite source preflight"),
    )
    with pytest.raises(ValueError, match="resource|source"):
        catalog.resolve_rank_publication_context(engine, canonical_sha256(value), canonical_sha256(receipt))
