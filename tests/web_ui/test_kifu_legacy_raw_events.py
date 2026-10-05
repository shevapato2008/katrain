"""The legacy bridge shares approvals and finite archive scope with strict reads."""

from datetime import datetime, timezone
import importlib.util

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from katrain.web.core.models_db import (
    KifuAlbum,
    KifuAlbumEventSelection,
    KifuEvent,
    KifuEventSelectionBatch,
    KifuNameResearchEvidence,
    KifuRawEventName,
    KifuRawEventValue,
)
from katrain.web.kifu.identity import _approved_raw_event_names
from katrain.web.kifu.legacy_raw_events import reviewed_raw_event_hints, reviewed_raw_event_search_clause
from katrain.web.kifu.name_batch import apply_bundle, undo_batch
from katrain.web.kifu.name_candidates import canonical_sha256
from katrain.web.kifu.name_inventory import build_inventory
from tests.web_ui.test_kifu_name_batch import (
    LANGS,
    _archive_fixture_bundle,
    _v2_wrap,
    approved_bundle,
    bind_fixture_candidate,
    engine,
    registry,
)
from tests.web_ui.test_kifu_name_candidates import archive_registry, v2_classification_candidate, V2_GENERIC_DISPLAYS
from scripts.build_kifu_raw2134_overlay import rules_source


def generic_bundle(engine, raw):
    with engine.begin() as conn:
        conn.execute(
            KifuAlbum.__table__.insert().values(
                id=12,
                player_black="Alpha",
                player_white="Beta",
                event=raw,
                sgf_content=f"(;PB[Alpha]PW[Beta]EV[{raw}])",
                source_path="generic.sgf",
            )
        )
    inv = build_inventory(engine, inventory_format=4)
    owner = {"kind": "raw_event", "ref": "generic"}
    declaration = {
        "owner": owner,
        "create": {"raw_value": raw, "category": "generic_event_description"},
        "occurrence_album_ids": [12],
        "occurrence_sha256": canonical_sha256([12]),
        "category_review": {
            "status": "approved",
            "producer_id": "researcher-1",
            "producer_model": "gpt-6-luna",
            "produced_at": "2026-10-02T10:00:00Z",
            "reviewer_id": "reviewer-2",
            "reviewer_model": "gpt-6-luna",
            "reviewed_at": "2026-10-02T10:30:00Z",
            "category_basis": "Exact generic description, no series identity",
        },
    }
    bundle = approved_bundle(inv)
    bundle["inventory_format"] = 4
    bundle["candidates"] = []
    for lang in LANGS:
        row = v2_classification_candidate(raw, lang, owner)
        row["name_preimage_sha256"] = None
        bundle["candidates"].append(bind_fixture_candidate(row))
    bundle["members"] = [{"owner": owner, "lang": lang, "raw_value": raw} for lang in LANGS]
    bundle["member_set_sha256"] = canonical_sha256(bundle["members"])
    return inv, _v2_wrap(engine, inv, bundle, [declaration], [])


def check_display_search(db, raw, expected, expected_ids):
    albums = db.query(KifuAlbum).all()
    for lang, display in expected.items():
        hints = reviewed_raw_event_hints(db, albums, lang)
        assert {key for key, value in hints.items() if value == display} == expected_ids
        assert (
            set(db.scalars(select(KifuAlbum.id).where(reviewed_raw_event_search_clause(db, display)))) == expected_ids
        )
        assert any(
            name.display_name == display for name, _, _ in _approved_raw_event_names(db, values={raw}, lang=lang)
        )


@pytest.mark.parametrize("raw", ["段位赛", "个人赛"])
def test_generic_eleven_languages_and_revocation(engine, raw):
    inv, bundle = generic_bundle(engine, raw)
    applied = apply_bundle(engine, bundle, registry(), inv, [])
    with Session(engine) as db:
        check_display_search(db, raw, V2_GENERIC_DISPLAYS[raw], {12})
        evidence = db.query(KifuNameResearchEvidence).filter_by(lang="en").one()
        evidence.review_status = "pending"
        db.commit()
        assert reviewed_raw_event_hints(db, db.query(KifuAlbum).all(), "en") == {}
        assert (
            list(
                db.scalars(
                    select(KifuAlbum.id).where(reviewed_raw_event_search_clause(db, V2_GENERIC_DISPLAYS[raw]["en"]))
                )
            )
            == []
        )
        evidence.review_status = "approved"
        db.commit()
        name = db.query(KifuRawEventName).filter_by(lang="en").one()
        name.revision += 1
        db.commit()
        assert reviewed_raw_event_hints(db, db.query(KifuAlbum).all(), "en") == {}
        name.revision -= 1
        db.commit()
    undo_batch(engine, applied["batch_id"])
    with Session(engine) as db:
        assert reviewed_raw_event_hints(db, db.query(KifuAlbum).all(), "en") == {}


def test_archive_uses_existing_rules_and_live_scope(engine, tmp_path):
    from tests.web_ui.test_kifu_name_candidates import ARCHIVE_DISPLAYS

    inv, bundle, _ = _archive_fixture_bundle(engine, tmp_path)
    apply_bundle(engine, bundle, archive_registry(), inv, [])
    with Session(engine) as db:
        check_display_search(db, "Hoensha game", ARCHIVE_DISPLAYS, {12, 13})
        db.add(
            KifuAlbum(
                id=14,
                player_black="A",
                player_white="B",
                event="Hoensha game",
                sgf_content="(;)",
                source_path="new.sgf",
            )
        )
        db.add(KifuEvent(id=1, canonical_name="Unrelated"))
        db.commit()
        db.get(KifuAlbum, 12).event_id = 1
        db.commit()
        check_display_search(db, "Hoensha game", ARCHIVE_DISPLAYS, {13})
        now = datetime.now(timezone.utc)
        batch = KifuEventSelectionBatch(
            bundle_sha256="a" * 64,
            member_set_sha256="b" * 64,
            reviewed_artifact={},
            producer_id="selection-producer",
            reviewer_id="selection-reviewer",
            reviewed_at=now,
            status="applied",
        )
        db.add(batch)
        db.flush()
        selected = KifuAlbumEventSelection(
            album_id=13,
            batch_id=batch.id,
            selected_raw="Other GN",
            sgf_sha256="c" * 64,
            property_name="GN",
            property_index=1,
            status="approved",
            rule_version="fixture",
            reviewer_id="selection-reviewer",
            reviewed_at=now,
        )
        db.add(selected)
        db.commit()
        check_display_search(db, "Hoensha game", ARCHIVE_DISPLAYS, set())
        db.delete(selected)
        db.commit()
        raw = db.query(KifuRawEventValue).filter_by(raw_value="Hoensha game").one()
        raw.review_metadata = dict(raw.review_metadata, category_basis="later changed decision")
        db.commit()
        assert reviewed_raw_event_hints(db, db.query(KifuAlbum).all(), "en") == {}
        assert (
            list(db.scalars(select(KifuAlbum.id).where(reviewed_raw_event_search_clause(db, ARCHIVE_DISPLAYS["en"]))))
            == []
        )


def test_packaged_rules_are_current_pure_validators(tmp_path):
    from katrain.web.kifu import name_candidates as current

    path = tmp_path / "rules.py"
    path.write_text(rules_source())
    spec = importlib.util.spec_from_file_location("packaged_raw_rules", path)
    rules = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(rules)
    for lang in LANGS:
        assert rules.classification_template_sha256(
            lang, "classification-v2"
        ) == current.classification_template_sha256(lang, "classification-v2")
        assert rules.archive_description_template_sha256(lang) == current.archive_description_template_sha256(lang)
    assert rules._ARCHIVE_HONINBO_SHUHO_FILES == current._ARCHIVE_HONINBO_SHUHO_FILES
    with pytest.raises(rules.CandidateError):
        rules.validate_archive_description_scope({})
