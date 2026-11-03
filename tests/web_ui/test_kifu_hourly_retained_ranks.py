"""An additional exact source cannot replace the original owner's frozen rank."""

from copy import deepcopy

import pytest
from sqlalchemy import event, select, update

from katrain.kifu_ingest import catalog, ranks
from katrain.web.core.models_db import (
    KifuAlbum,
    KifuAlbumSource,
    KifuAlbumRankSnapshot,
    KifuNameBatch,
    KifuNameChange,
    KifuPlayerRankHistory,
)
from katrain.web.kifu.name_candidates import canonical_sha256
from tests.web_ui.test_kifu_historical_rank_native import prepared, WHEN
from tests.web_ui.test_kifu_incremental_catalog import make_engine, publish


@pytest.mark.parametrize("old_snapshot", [False, True])
def test_new_exact_v3_source_retains_original_snapshot_or_honest_absence(tmp_path, old_snapshot):
    engine = make_engine(tmp_path / "retained.db")
    original = prepared(engine, "99101", raw="9p")
    if not old_snapshot:
        original["format"] = catalog.FORMAT
        original.pop("rank_facts")
        for game in original["games"]:
            game.pop("rank_snapshots")
            game.pop("rank_observations")
    first = publish(engine, original)
    with engine.connect() as conn:
        before = [dict(row) for row in conn.execute(select(KifuAlbumRankSnapshot.__table__)).mappings()]
        facts = conn.scalars(select(KifuPlayerRankHistory.id)).all()
    incoming = prepared(engine, "99102", raw="9p")
    receipt = publish(engine, incoming)
    assert receipt["games"][0]["album_id"] == first["games"][0]["album_id"]
    assert receipt["games"][0]["action"] == "reused"
    assert {row["status"] for row in receipt["rank_outcomes"]} == ({"retained"} if old_snapshot else {"deferred"})
    ranks.validate_rank_outcomes(incoming, receipt)
    with engine.connect() as conn:
        assert [dict(row) for row in conn.execute(select(KifuAlbumRankSnapshot.__table__)).mappings()] == before
        assert conn.scalars(select(KifuPlayerRankHistory.id)).all() == facts
        assert (
            conn.scalar(select(KifuAlbum.source_path).where(KifuAlbum.id == first["games"][0]["album_id"]))
            == original["games"][0]["origin_path"]
        )
    assert publish(engine, incoming) == receipt
    assert catalog.undo_publication(engine, receipt["batch_id"])["status"] == "undone"
    with engine.connect() as conn:
        assert [dict(row) for row in conn.execute(select(KifuAlbumRankSnapshot.__table__)).mappings()] == before


def test_same_batch_exact_v3_sources_keep_first_original_and_snapshot(tmp_path):
    engine = make_engine(tmp_path / "same-batch.db")
    value = prepared(engine, "99111", raw="9p")
    second = prepared(engine, "99112", raw="9p")
    value["games"].extend(second["games"])
    value["rank_facts"].update(second["rank_facts"])
    receipt = publish(engine, value)
    assert receipt["games"][0]["album_id"] == receipt["games"][1]["album_id"]
    assert [row["status"] for row in receipt["rank_outcomes"]] == ["applied", "applied", "retained", "retained"]
    assert publish(engine, value) == receipt


def test_retained_v3_rejects_recreated_local_basis_binding(tmp_path):
    from tests.web_ui.test_kifu_historical_rank_native import seed_prior

    engine = make_engine(tmp_path / "basis-rebind.db")
    seed_prior(engine)
    publish(engine, prepared(engine, "99131"))
    with engine.begin() as conn:
        conn.execute(update(KifuAlbumSource).where(KifuAlbumSource.album_id == 12).values(id=999))
    incoming = prepared(engine, "99132")
    with pytest.raises(ValueError, match="local binding"):
        publish(engine, incoming)


def test_same_original_v3_reuse_cannot_reauthorize_a_broken_old_journal(tmp_path):
    engine = make_engine(tmp_path / "same-original-authority.db")
    value = prepared(engine, "99161", raw="9p")
    receipt = publish(engine, value)
    with engine.begin() as conn:
        change = (
            conn.execute(
                select(KifuNameChange.__table__).where(
                    KifuNameChange.batch_id == receipt["batch_id"],
                    KifuNameChange.target_table == KifuAlbumRankSnapshot.__tablename__,
                )
            )
            .mappings()
            .first()
        )
        after = deepcopy(change["after_image"])
        after["snapshot_sha256"] = "0" * 64
        conn.execute(update(KifuNameChange).where(KifuNameChange.id == change["id"]).values(after_image=after))
    again = deepcopy(value)
    again["publication_key"] += "-new-receipt"
    with pytest.raises(ValueError, match="journal changed"):
        publish(engine, again)


@pytest.mark.parametrize("had_snapshot", [False, True])
def test_rank_disposition_replay_and_undo_reject_changed_retained_state(tmp_path, had_snapshot):
    engine = make_engine(tmp_path / "state-cas.db")
    original = prepared(engine, "99141", raw="9p")
    if not had_snapshot:
        original["format"] = catalog.FORMAT
        original.pop("rank_facts")
        original["games"][0].pop("rank_snapshots")
        original["games"][0].pop("rank_observations")
    first = publish(engine, original)
    incoming = prepared(engine, "99142", raw="9p")
    receipt = publish(engine, incoming)
    with engine.begin() as conn:
        if had_snapshot:
            conn.execute(update(KifuAlbumRankSnapshot).values(publication_key="changed-after-freeze"))
        else:
            old_snapshot = prepared(engine, "99141", raw="9p")["games"][0]["rank_snapshots"]["black"]
            conn.execute(
                KifuAlbumRankSnapshot.__table__.insert().values(
                    album_id=first["games"][0]["album_id"],
                    side="black",
                    snapshot=old_snapshot,
                    snapshot_sha256=old_snapshot["content_sha256"],
                    publication_key="later-row",
                    native_batch_id=first["batch_id"],
                )
            )
    with pytest.raises(ValueError, match="snapshot CAS changed"):
        publish(engine, incoming)
    with pytest.raises(ValueError, match="snapshot CAS changed"):
        catalog.undo_publication(engine, receipt["batch_id"])


def test_prod_matching_outcomes_allow_first_apply_and_exact_original_retry(tmp_path):
    engines = [make_engine(tmp_path / f"{name}-ok.db") for name in ("test", "prod")]
    for engine in engines:
        publish(engine, prepared(engine, "99151", raw="9p"))
    incoming = prepared(engines[0], "99152", raw="9p")
    expected = publish(engines[0], incoming)["rank_outcomes"]
    receipt = catalog.publish_manifest(
        engines[1], incoming, expected_manifest_sha256=canonical_sha256(incoming), expected_rank_outcomes=expected
    )
    assert (
        catalog.publish_manifest(
            engines[1], incoming, expected_manifest_sha256=canonical_sha256(incoming), expected_rank_outcomes=expected
        )
        == receipt
    )


def test_prod_retained_outcome_is_test_frozen_cas_before_any_business_write(tmp_path):
    engines = [make_engine(tmp_path / f"{name}.db") for name in ("test", "prod")]
    for index, engine in enumerate(engines):
        old = prepared(engine, "99121", raw="9p")
        if index:
            with engine.connect() as conn:
                frozen = ranks.freeze_historical_game_ranks(conn, old["games"], matched_at="2026-11-02T00:00:00+00:00")[
                    0
                ]
            old["games"][0].update({key: frozen[key] for key in ("rank_snapshots", "rank_observations")})
            old["rank_facts"] = frozen["rank_facts"]
        publish(engine, old)
    incoming = prepared(engines[0], "99122", raw="9p")
    receipt = publish(engines[0], incoming)
    writes = []
    event.listen(
        engines[1],
        "before_cursor_execute",
        lambda c, cur, sql, p, ctx, many: (
            writes.append(sql) if sql.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE")) else None
        ),
    )
    with pytest.raises(ValueError, match="rank outcome"):
        catalog.publish_manifest(
            engines[1],
            incoming,
            expected_manifest_sha256=canonical_sha256(incoming),
            expected_rank_outcomes=receipt["rank_outcomes"],
        )
    assert writes == []
