"""Finite raw owner approvals change review status without changing games."""

from copy import deepcopy

import pytest
from sqlalchemy import select

from katrain.web.core.models_db import KifuAlbum, KifuRawEventValue
from katrain.web.kifu.name_batch import BatchError, _image, undo_batch
from katrain.web.kifu.name_candidates import canonical_sha256
from scripts.kifu_raw_event_title_owners import RAW_VALUES, apply_plan, inspect_plan, prepare_plan
from tests.web_ui.test_kifu_name_batch import engine  # noqa: F401
from tests.web_ui.test_kifu_name_candidates import registry


def owner_fixture(engine):
    records, members = [], []
    next_album = 1000
    with engine.begin() as conn:
        for index, raw in enumerate(RAW_VALUES):
            owner_id = 100 + index
            count = 265 if index == 0 else 206 if index == 7 else 1
            ids = list(range(next_album, next_album + count))
            next_album += count
            conn.execute(KifuRawEventValue.__table__.insert().values(
                id=owner_id, raw_value=raw, category="unclassified_pending", parser_version="original-parser",
                parsed_data={"raw": raw}, review_status="pending"))
            conn.execute(KifuAlbum.__table__.insert(), [
                {"id": album_id, "player_black": "A", "player_white": "B", "event": raw,
                 "sgf_content": f"(;EV[{raw}])", "source_path": f"{album_id}.sgf", "black_rank": "1d"}
                for album_id in ids
            ])
            before = _image(conn, KifuRawEventValue.__table__, owner_id)
            records.append({"raw_value": raw, "owners": {"TEST": {"raw_event_id": owner_id,
                                                                       "preimage": before}}})
            members.append({"raw_value": raw, "album_ids": ids})
    return {"records": records, "member_manifest": {"TEST": {"members": members}}}


def test_first24_owner_plan_is_cas_scoped_and_undoable(engine):
    manifest = owner_fixture(engine)
    plan = prepare_plan(engine, manifest, "TEST", registry(), producer_id="producer-1",
                        producer_model="gpt-6-sol", reviewer_id="reviewer-2", reviewer_model="gpt-6-astra",
                        review_conclusion="Reviewed each literal raw title without event identity claims")
    assert "profile" not in plan
    with engine.connect() as conn:
        assert inspect_plan(conn, plan, registry(), canonical_sha256(manifest))["albums"] == 493
    tampered = deepcopy(plan)
    tampered["changes"][0]["after"]["category"] = "formal_event_candidate"
    with engine.connect() as conn, pytest.raises(BatchError):
        inspect_plan(conn, tampered, registry(), canonical_sha256(manifest))
    self_reviewed = deepcopy(plan)
    self_reviewed["reviewer_id"] = self_reviewed["producer_id"]
    with engine.connect() as conn, pytest.raises(BatchError):
        inspect_plan(conn, self_reviewed, registry(), canonical_sha256(manifest))
    with engine.begin() as conn:
        conn.execute(KifuAlbum.__table__.update().where(KifuAlbum.id == 1000).values(black_rank="2d"))
    with engine.connect() as conn, pytest.raises(BatchError):
        inspect_plan(conn, plan, registry(), canonical_sha256(manifest))
    with engine.begin() as conn:
        conn.execute(KifuAlbum.__table__.update().where(KifuAlbum.id == 1000).values(black_rank="1d"))
    applied = apply_plan(engine, plan, registry(), canonical_sha256(manifest), canonical_sha256(plan))
    with engine.connect() as conn:
        assert conn.scalar(select(KifuRawEventValue.review_status).where(KifuRawEventValue.id == 100)) == "approved"
        assert conn.scalar(select(KifuAlbum.event_id).where(KifuAlbum.id == 1000)) is None
    undo_batch(engine, applied["batch_id"])
    with engine.connect() as conn:
        assert conn.scalar(select(KifuRawEventValue.review_status).where(KifuRawEventValue.id == 100)) == "pending"


AGON_RAWS = (
    "第11届阿含桐山杯本选第1轮", "第11届阿含桐山杯本选第2轮", "第11届阿含桐山杯本选第3轮",
    "第11届阿含桐山杯本选第4轮", "第11届阿含桐山杯本选第一轮", "第12届阿含桐山杯本选第一轮",
    "第12届阿含桐山杯本选第二轮", "第16届阿含桐山杯本选第2轮", "第16届阿含桐山杯本选第3轮",
    "第十届阿含桐山杯本选第一轮",
)
CMB_RAWS = ("第9届招商银行杯第3轮", "第9届招商银行杯第一轮")


def finite_fixture(engine, raws, counts):
    records, members = [], []
    next_album = 2000
    with engine.begin() as conn:
        for index, (raw, count) in enumerate(zip(raws, counts)):
            owner_id = 200 + index
            ids = list(range(next_album, next_album + count))
            next_album += count
            conn.execute(KifuRawEventValue.__table__.insert().values(
                id=owner_id, raw_value=raw, category="unclassified_pending", parser_version="original-parser",
                parsed_data={"raw": raw}, review_status="pending"))
            conn.execute(KifuAlbum.__table__.insert(), [
                {"id": album_id, "player_black": "A", "player_white": "B", "event": raw,
                 "sgf_content": f"(;EV[{raw}])", "source_path": f"{album_id}.sgf"}
                for album_id in ids
            ])
            before = _image(conn, KifuRawEventValue.__table__, owner_id)
            records.append({"raw_value": raw, "owners": {"TEST": {"raw_event_id": owner_id, "preimage": before}}})
            members.append({"raw_value": raw, "album_ids": ids})
    return {"records": records, "member_manifest": {"TEST": {"members": members}}}


@pytest.mark.parametrize("profile,raws,counts,total", [
    ("agon10", AGON_RAWS, (49, 24, 14, 7, 5, 60, 25, 1, 1, 19), 205),
    ("cmb2", CMB_RAWS, (1, 1), 2),
])
def test_next_finite_profiles_pin_raws_and_game_totals(engine, profile, raws, counts, total):
    manifest = finite_fixture(engine, raws, counts)
    kwargs = {"producer_id": "producer-1", "producer_model": "gpt-6-sol",
              "reviewer_id": "reviewer-2", "reviewer_model": "gpt-6-astra",
              "review_conclusion": "Reviewed exact literal raw titles"}
    with pytest.raises(BatchError):
        prepare_plan(engine, manifest, "TEST", registry(), **kwargs)
    with pytest.raises(BatchError):
        prepare_plan(engine, manifest, "TEST", registry(), profile="arbitrary", **kwargs)
    plan = prepare_plan(engine, manifest, "TEST", registry(), profile=profile, **kwargs)
    with engine.connect() as conn:
        assert inspect_plan(conn, plan, registry(), canonical_sha256(manifest), profile=profile) == {
            "ready": True, "raw_owners": len(raws), "albums": total, "name_writes": 0, "fk_writes": 0}
        with pytest.raises(BatchError):
            inspect_plan(conn, plan, registry(), canonical_sha256(manifest))
    wrong_raw = deepcopy(manifest)
    wrong_raw["records"][0]["raw_value"] += "X"
    with pytest.raises(BatchError):
        prepare_plan(engine, wrong_raw, "TEST", registry(), profile=profile, **kwargs)
    wrong_count = deepcopy(manifest)
    wrong_count["records"].pop()
    with pytest.raises(BatchError):
        prepare_plan(engine, wrong_count, "TEST", registry(), profile=profile, **kwargs)
    with engine.begin() as conn:
        conn.execute(KifuAlbum.__table__.update().where(KifuAlbum.id == 2000).values(black_rank="2d"))
    with engine.connect() as conn, pytest.raises(BatchError):
        inspect_plan(conn, plan, registry(), canonical_sha256(manifest), profile=profile)
    with engine.begin() as conn:
        conn.execute(KifuAlbum.__table__.update().where(KifuAlbum.id == 2000).values(black_rank=None))
    applied = apply_plan(engine, plan, registry(), canonical_sha256(manifest), canonical_sha256(plan), profile=profile)
    assert applied["change_count"] == len(raws)
    undo_batch(engine, applied["batch_id"])
    with engine.connect() as conn:
        assert conn.scalar(select(KifuRawEventValue.review_status).where(KifuRawEventValue.id == 200)) == "pending"


@pytest.mark.parametrize("profile,raws,counts", [
    ("agon10", AGON_RAWS, (48, 24, 14, 7, 5, 60, 25, 1, 1, 19)),
    ("cmb2", CMB_RAWS, (1, 2)),
])
def test_finite_profile_rejects_changed_game_total(engine, profile, raws, counts):
    manifest = finite_fixture(engine, raws, counts)
    with pytest.raises(BatchError):
        prepare_plan(engine, manifest, "TEST", registry(), profile=profile,
                     producer_id="producer-1", producer_model="gpt-6-sol",
                     reviewer_id="reviewer-2", reviewer_model="gpt-6-astra",
                     review_conclusion="Reviewed exact literal raw titles")
