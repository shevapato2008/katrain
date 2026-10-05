"""The first-24 raw owner approval changes categories without changing games."""

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
