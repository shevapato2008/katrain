"""The finite category CAS shares the existing transaction journal and undo."""

from copy import deepcopy
import hashlib

import pytest
from sqlalchemy import select

from katrain.web.core.models_db import (
    KifuAlbum,
    KifuAlbumSource,
    KifuEvent,
    KifuEventAlias,
    KifuNameBatch,
    KifuNameChange,
    KifuPlayer,
    KifuPlayerAlias,
    KifuRawEventName,
    KifuRawEventValue,
    KifuRawPlayerValue,
    KifuSource,
)
from katrain.web.kifu.name_batch import BatchError, _catalog_sha, _image, undo_batch
from katrain.web.kifu.name_candidates import canonical_sha256
from katrain.web.kifu.name_evidence import registry_sha256
from katrain.web.kifu.name_inventory import build_inventory
from scripts.kifu_raw2134_categories import apply_plan, inspect_plan
from tests.web_ui.test_kifu_name_batch import engine
from tests.web_ui.test_kifu_name_candidates import archive_declaration, archive_registry


def fixture_plan(engine, tmp_path):
    expected = {"段位赛": 901, "个人赛": 638, "Hoensha game": 595}
    scope = {}
    album_id = 100
    with engine.begin() as conn:
        conn.execute(KifuSource.__table__.insert().values(id=2, source_key="CWI"))
        for raw_id, (raw, count) in enumerate(expected.items(), 20):
            conn.execute(
                KifuRawEventValue.__table__.insert().values(
                    id=raw_id,
                    raw_value=raw,
                    category="unclassified_pending" if raw == "Hoensha game" else "generic_event_description",
                    parser_version="event-components-v5-catalog-v1",
                    review_status="pending",
                )
            )
            ids = list(range(album_id, album_id + count))
            scope[raw_id] = ids
            conn.execute(
                KifuAlbum.__table__.insert(),
                [
                    {
                        "id": ident,
                        "player_black": "A",
                        "player_white": "B",
                        "event": raw,
                        "date_played": "1880-01-01",
                        "sgf_content": f"(;EV[{raw}])",
                        "source_path": f"data/kifu-album/CWI_History_Full/Hoensha/{ident}.sgf",
                    }
                    for ident in ids
                ],
            )
            if raw == "Hoensha game":
                conn.execute(
                    KifuAlbumSource.__table__.insert(),
                    [
                        {
                            "album_id": ident,
                            "source_id": 2,
                            "origin_path": f"data/kifu-album/CWI_History_Full/Hoensha/{ident}.sgf",
                            "match_method": "source_path",
                        }
                        for ident in ids
                    ],
                )
            album_id += count
    inventory = build_inventory(engine, inventory_format=4)
    registry = archive_registry()
    plan = {
        "operation": "raw2134-category-v1",
        "bundle_format": 2,
        "inventory_sha256": inventory["sha256"],
        "registry_version": registry["version"],
        "registry_sha256": registry_sha256(registry),
        "producer_id": "producer-1",
        "producer_model": "gpt-6-astra",
        "produced_at": "2026-10-02T10:00:00Z",
        "review_status": "approved",
        "reviewer_id": "reviewer-2",
        "reviewer_model": "gpt-6-astra",
        "reviewed_at": "2026-10-02T11:00:00Z",
        "review_conclusion": "Finite category, no event identity",
        "changes": [],
    }
    with engine.connect() as conn:
        plan["catalog_sha256"] = _catalog_sha(conn)
        for raw_id, ids in scope.items():
            before = _image(conn, KifuRawEventValue.__table__, raw_id)
            after = deepcopy(before)
            if before["raw_value"] == "Hoensha game":
                declaration = archive_declaration(inventory, {"kind": "raw_event", "id": raw_id}, tmp_path, ids=ids)
                review = declaration["category_review"]
                after.update(category="archive_source_description", parser_version="archive-description-v1")
            else:
                review = {
                    key: value
                    for key, value in plan.items()
                    if key
                    in {"producer_id", "producer_model", "produced_at", "reviewer_id", "reviewer_model", "reviewed_at"}
                }
                review.update(status="approved", category_basis="Generic label without formal series identity")
            after.update(review_status="approved", review_metadata=review)
            change = {"before": before, "after": after, "occurrence_album_ids": ids}
            if before["raw_value"] == "Hoensha game":
                declaration.pop("create")
                declaration["preimage"] = after
                change["archive_declaration"] = declaration
            plan["changes"].append(change)
        after_by_id = {c["after"]["id"]: c["after"] for c in plan["changes"]}
        digest = hashlib.sha256()
        for model in (KifuPlayer, KifuEvent, KifuPlayerAlias, KifuEventAlias, KifuRawPlayerValue, KifuRawEventValue):
            for row in conn.execute(select(model.__table__.c.id).order_by(model.__table__.c.id)):
                image = _image(conn, model.__table__, row.id)
                if model is KifuPlayer:
                    image = {k: image[k] for k in ("id", "canonical_name", "created_at")}
                if model is KifuRawEventValue:
                    image = after_by_id.get(row.id, image)
                digest.update((model.__tablename__ + ":" + canonical_sha256(image) + "\n").encode())
        plan["catalog_after_sha256"] = digest.hexdigest()
    return plan, registry


def test_readonly_dry_run_apply_replay_and_existing_undo(engine, tmp_path):
    plan, registry = fixture_plan(engine, tmp_path)
    with engine.connect() as conn:
        assert inspect_plan(conn, plan, registry)["albums"] == 2134
        assert conn.scalar(select(KifuNameBatch.id)) is None
        assert _catalog_sha(conn) == plan["catalog_sha256"]
    result = apply_plan(engine, plan, registry, canonical_sha256(plan))
    assert result["change_count"] == 3
    assert apply_plan(engine, plan, registry, canonical_sha256(plan))["change_count"] == 0
    with engine.connect() as conn:
        assert _catalog_sha(conn) == plan["catalog_after_sha256"]
        assert conn.scalar(select(KifuRawEventName.id)) is None
        assert len(list(conn.scalars(select(KifuNameChange.id)))) == 3
        assert not list(conn.scalars(select(KifuAlbum.event_id).where(KifuAlbum.event_id.isnot(None))))
    assert undo_batch(engine, result["batch_id"])["reverted"] == 3
    with engine.connect() as conn:
        assert _catalog_sha(conn) == plan["catalog_sha256"]


def test_cas_rejects_changed_source_or_unapproved_plan_without_writes(engine, tmp_path):
    plan, registry = fixture_plan(engine, tmp_path)
    unsigned = dict(plan, review_status="pending")
    for field in ("reviewer_id", "reviewer_model", "reviewed_at", "review_conclusion"):
        unsigned.pop(field)
    with pytest.raises(BatchError, match="not independently approved"):
        apply_plan(engine, unsigned, registry, canonical_sha256(unsigned))
    with engine.begin() as conn:
        first = conn.scalar(select(KifuAlbumSource.id).where(KifuAlbumSource.source_id == 2).limit(1))
        conn.execute(
            KifuAlbumSource.__table__.update().where(KifuAlbumSource.id == first).values(origin_path="different.sgf")
        )
    with pytest.raises(BatchError, match="archive source/album context changed"):
        apply_plan(engine, plan, registry, canonical_sha256(plan))
    with engine.connect() as conn:
        assert conn.scalar(select(KifuNameBatch.id)) is None
        assert _catalog_sha(conn) == plan["catalog_sha256"]
