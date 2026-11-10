"""The finite canonical correction authorizes only its proven current rows."""

from copy import deepcopy
from hashlib import sha256

import pytest
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from katrain.kifu_ingest import catalog
from katrain.kifu_ingest.preparation import derive_metadata
from katrain.kifu_ingest.ranks import FORMAT_V2, freeze_historical_game_ranks
from katrain.web.api.v1.endpoints import kifu
from katrain.web.core import models_db as m
from katrain.web.kifu import historical_ranks, name_batch, numadate_canonical_correction as correction
from katrain.web.kifu.name_candidates import canonical_sha256 as digest
from katrain.web.kifu.player_ranks import lookup_album_rank_snapshots
from katrain.web.kifu.name_parse import parse_player
from katrain.web.kifu.source_rank_normalization import normalize_source_rank
from tests.web_ui.test_kifu_numadate_canonical_correction import (
    NEW,
    SCOPE,
    correction_engine,
    legacy_manifest,
    prepared,
    state,
)
from tests.web_ui.test_kifu_incremental_catalog import publish
from tests.web_ui.test_kifu_rank_snapshots_api import detail, listing


def applied(engine):
    plan = prepared(engine)
    receipt = correction.apply_correction(engine, plan, expected_sha256=digest(plan))
    return plan, receipt


def test_corrected_overlays_share_one_real_verification_per_page(correction_engine, monkeypatch):
    plan, receipt = applied(correction_engine)
    verify = correction.verify_correction
    calls = []

    def counted(conn, batch_id, **kwargs):
        calls.append((batch_id, deepcopy(kwargs.get("expected_rows"))))
        return verify(conn, batch_id, **kwargs)

    monkeypatch.setattr(correction, "verify_correction", counted)
    with Session(correction_engine) as db:
        for lang in ("cn", "tw", "jp", "en", "ko"):
            calls.clear()
            page = listing(db, lang)
            assert len(calls) == 1 and calls[0][0] == receipt["batch_id"]
            assert {row["id"] for row in calls[0][1]} == {186520, 233062}
            assert all(set(row) == set(m.KifuAlbumRankSnapshot.__table__.c.keys()) for row in calls[0][1])
            cards = {card.id: card for card in page.items}
            for target in plan["targets"]:
                old = target["snapshot_before"]
                side = old["side"]
                snapshot = target["expected_snapshot"]
                for card in (cards[old["album_id"]], detail(db, old["album_id"], lang)):
                    assert getattr(card, f"display_{side}_rank") == snapshot["display_rank"]
                    assert getattr(card, f"{side}_rank_origin") == "source"
                    proof = getattr(card, f"{side}_rank_source")
                    assert proof["snapshot_sha256"] == snapshot["content_sha256"]
                    assert proof["snapshot_sha256"] != old["snapshot_sha256"]
                    assert proof["source_ref"] == snapshot["source_ref"]
                    assert getattr(card, f"{side}_rank") == snapshot["raw_rank"]


@pytest.mark.parametrize("damage", ["old_authority", "owner", "journal", "undone", "forged", "mixed_format"])
def test_invalid_correction_authority_falls_back_to_original_source(correction_engine, damage):
    _, receipt = applied(correction_engine)
    with correction_engine.begin() as conn:
        if damage == "owner":
            conn.execute(update(m.KifuPlayer).where(m.KifuPlayer.id == 5364).values(canonical_name="Different"))
        elif damage == "undone":
            conn.execute(
                update(m.KifuNameBatch).where(m.KifuNameBatch.id == receipt["batch_id"]).values(status="undone")
            )
        elif damage == "journal":
            conn.execute(
                update(m.KifuNameChange)
                .where(
                    m.KifuNameChange.batch_id == receipt["batch_id"],
                    m.KifuNameChange.target_table == m.KifuAlbumRankSnapshot.__tablename__,
                )
                .values(after_image=None)
            )
        elif damage == "old_authority":
            conn.execute(update(m.KifuNameBatch).where(m.KifuNameBatch.id == 2189).values(status="undone"))
        else:
            batch = name_batch._image(conn, m.KifuNameBatch.__table__, receipt["batch_id"])
            forged = {"format": correction.FORMAT, "manifest_sha256": batch["bundle_sha256"]}
            if damage == "mixed_format":
                forged.update(publication_format=FORMAT_V2, publication_key=receipt["publication_key"])
            conn.execute(
                update(m.KifuNameBatch).where(m.KifuNameBatch.id == batch["id"]).values(reviewed_artifact=forged)
            )
        for album_id, side, *_ in SCOPE:
            row = dict(
                conn.execute(
                    select(m.KifuAlbumRankSnapshot.__table__).where(
                        m.KifuAlbumRankSnapshot.album_id == album_id,
                        m.KifuAlbumRankSnapshot.side == side,
                    )
                )
                .mappings()
                .one()
            )
            with pytest.raises(ValueError):
                catalog._assert_retained_rank_row(conn, row, {}, resource=historical_ranks.EvidenceBudget())
    with Session(correction_engine) as db:
        for album_id, side, _, _, rank, *_ in SCOPE:
            card = detail(db, album_id)
            assert (
                getattr(card, f"display_{side}_rank") == normalize_source_rank(rank, source_key="19x19")["display_rank"]
            )
            assert getattr(card, f"{side}_rank") == rank
            assert getattr(card, f"{side}_rank_origin") == "source"
            assert getattr(card, f"{side}_rank_source") is None


def test_reader_does_not_hide_unexpected_verifier_failure(correction_engine, monkeypatch):
    applied(correction_engine)

    def broken(*args, **kwargs):
        raise RuntimeError("unexpected verifier fault")

    monkeypatch.setattr(correction, "verify_correction", broken)
    with correction_engine.connect() as conn, pytest.raises(RuntimeError, match="unexpected verifier fault"):
        lookup_album_rank_snapshots(conn, [124026, 178495])


def test_retained_rank_accepts_real_correction_and_shares_budget(correction_engine, monkeypatch):
    _, receipt = applied(correction_engine)
    resource = historical_ranks.EvidenceBudget()
    verify = correction.verify_correction
    seen = []

    def counted(conn, batch_id, **kwargs):
        seen.append(kwargs.get("resource"))
        return verify(conn, batch_id, **kwargs)

    monkeypatch.setattr(correction, "verify_correction", counted)
    with correction_engine.connect() as conn:
        for album_id, side, *_ in SCOPE:
            row = dict(
                conn.execute(
                    select(m.KifuAlbumRankSnapshot.__table__).where(
                        m.KifuAlbumRankSnapshot.album_id == album_id,
                        m.KifuAlbumRankSnapshot.side == side,
                    )
                )
                .mappings()
                .one()
            )
            catalog._assert_retained_rank_row(conn, row, {}, resource=resource)
            assert row["native_batch_id"] == receipt["batch_id"]
    assert seen == [resource, resource]
    assert resource.used_bytes > 0


def test_api_correction_proof_is_bound_to_row_snapshot_and_batch(correction_engine):
    applied(correction_engine)
    with Session(correction_engine) as db:
        snapshots = lookup_album_rank_snapshots(db.connection(), [124026, 178495])
        record = db.get(m.KifuAlbum, 124026)
        black = parse_player(record.player_black, record.black_rank)
        white = parse_player(record.player_white, record.white_rank)
        row = snapshots[(124026, "black")]
        assert kifu._rank_displays(record, black, white, snapshots)["black_rank_source"] is not None
        for key, value in (
            ("row_id", 233062),
            ("snapshot_sha256", "a" * 64),
            ("batch_id", -1),
            ("batch_sha256", "b" * 64),
        ):
            damaged = deepcopy(snapshots)
            damaged[(124026, "black")]["_canonical_correction_verified"][key] = value
            assert kifu._rank_displays(record, black, white, damaged)["black_rank_source"] is None
        row.pop("_canonical_correction_verified")
        assert kifu._rank_displays(record, black, white, snapshots)["black_rank_source"] is None


def test_original_alias_replay_and_new_strict_v3_publish_preserve_correction(correction_engine):
    original = legacy_manifest(correction_engine)
    with correction_engine.connect() as conn:
        original_receipt = conn.scalar(select(m.KifuNameBatch.reviewed_artifact).where(m.KifuNameBatch.id == 876))[
            "receipt"
        ]
    _, receipt = applied(correction_engine)
    before = state(correction_engine)
    assert publish(correction_engine, original) == original_receipt
    assert state(correction_engine) == before

    # The subsequent frozen publication uses the new exact canonical owner.
    body = f"(;SZ[19]PB[Other]PW[{NEW}]BR[1p]WR[七段]EV[Summer Cup]DT[2026-11-01];B[bb])"
    game = {
        "source_key": "19x19",
        "source_item_id": "92045923",
        "origin_path": "data/kifu-album/19x19/92045923.sgf",
        "sgf_content": body,
        "raw_sha256": sha256(body.encode()).hexdigest(),
        "sgf_sha256": sha256(body.encode()).hexdigest(),
        "metadata": derive_metadata(body),
        "identities": {"black": {"canonical_name": "Other"}, "white": {"canonical_name": NEW}},
    }
    with correction_engine.connect() as conn:
        frozen = freeze_historical_game_ranks(conn, [game], matched_at="2026-11-04T02:00:00+00:00")[0]
    game.update({key: frozen[key] for key in ("rank_snapshots", "rank_observations")})
    assert game["rank_snapshots"]["white"]["player_ref"] == {"canonical_name": NEW}
    assert game["rank_observations"]["white"] in frozen["rank_facts"]
    incoming = {
        "format": FORMAT_V2,
        "publication_key": "19x19-0ef-style-synthetic",
        "decisions": [],
        "games": [game],
        "rank_facts": frozen["rank_facts"],
    }

    def refuse_undo():
        snapshot = state(correction_engine)
        for batch_id in (receipt["batch_id"], receipt["child_batch_id"]):
            with pytest.raises(name_batch.BatchError, match="canonical correction.*does not support undo"):
                name_batch.undo_batch(correction_engine, batch_id)
        assert state(correction_engine) == snapshot

    refuse_undo()
    published = publish(correction_engine, incoming)
    assert publish(correction_engine, incoming) == published
    with correction_engine.connect() as conn:
        album_id = published["games"][0]["album_id"]
        assert conn.scalar(select(m.KifuAlbum.white_player_id).where(m.KifuAlbum.id == album_id)) == 5364
        assert (
            conn.scalar(select(m.KifuPlayerRankHistory.id).where(m.KifuPlayerRankHistory.player_id == 5364)) is not None
        )
        assert set(correction.verify_correction(conn, receipt["batch_id"])["rows"]) == {186520, 233062}
        snapshots = lookup_album_rank_snapshots(conn, [124026, 178495])
        assert all(snapshots[(album_id, side)].get("_canonical_correction_verified") for album_id, side, *_ in SCOPE)
    with Session(correction_engine) as db:
        for album_id, side, *_ in SCOPE:
            assert getattr(detail(db, album_id), f"{side}_rank_source") is not None
    refuse_undo()
