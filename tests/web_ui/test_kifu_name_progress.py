"""Progress uses actual approval resolution and preserves regressions."""

from datetime import datetime, timezone

import pytest
from sqlalchemy.orm import Session

from katrain.web.core.models_db import (
    KifuAlbum, KifuNameResearchEvidence, KifuPlayerName, KifuRawPlayerName, KifuRawPlayerValue,
)
from katrain.web.kifu.identity import LANGUAGES
from scripts.kifu_name_progress import progress_delta, progress_report
from tests.web_ui.test_kifu_name_coverage import _catalog


def test_progress_excludes_legacy_and_partial_names_and_counts_raw_separately():
    engine = _catalog()
    try:
        with Session(engine) as db:
            player_id = db.query(KifuPlayerName.player_id).scalar()
            db.add(KifuPlayerName(player_id=player_id, lang="en", display_name="Legacy", status="verified"))
            db.query(KifuAlbum).update({KifuAlbum.event: ""})
            db.commit()
        report = progress_report(engine, batch_size=1)
        assert len(report["languages"]) == 11
        assert report["players"]["total"] == 1
        assert report["players"]["complete_11"] == 0
        assert report["players"]["by_language"]["cn"] == 1
        assert report["players"]["by_language"]["en"] == 0
        assert report["albums"]["total"] == 1
        assert report["albums"]["complete_11"] == 0
        assert report["albums"]["by_slot_complete_11"] == {"black": 0, "white": 0, "event": 1}
        assert report["unlinked_raw_values"]["players"] == {
            "total": 1, "complete_11": 0, "complete_11_ratio": 0.0,
            "complete_11_all_occurrences": 0,
        }
        assert report["unlinked_raw_values"]["events"]["total"] == 0
        assert progress_report(engine, batch_size=20)["albums"] == report["albums"]
        with Session(engine) as db:
            db.query(KifuPlayerName).delete()
            db.commit()
        after = progress_report(engine)
        assert progress_delta(after, report)["players"]["by_language"]["cn"] == -1
        with pytest.raises(ValueError, match="environment"):
            progress_delta(after, {**report, "environment": "prod"})
        with pytest.raises(ValueError, match="database_identity"):
            progress_delta(after, {**report, "database_identity": "other/database"})
    finally:
        engine.dispose()


def test_completed_player_and_both_sides_only_count_after_all_eleven_approved_names():
    engine = _catalog()
    try:
        with Session(engine) as db:
            player_id = db.query(KifuPlayerName.player_id).scalar()
            registry_id = db.query(KifuNameResearchEvidence.source_registry_id).scalar()
            album = db.query(KifuAlbum).one()
            album.white_player_id = player_id
            album.player_white = "Go Seigen"
            album.event = ""
            for lang in sorted(LANGUAGES - {"cn"}):
                display = f"Go Seigen {lang}"
                evidence = KifuNameResearchEvidence(
                    player_id=player_id, lang=lang, revision=1, source_registry_id=registry_id,
                    candidate_name=display, decision_kind="conventional", generation_rule_version="test-v1",
                    research_payload={}, producer_id="researcher", producer_model="gpt-6-luna",
                    reviewer_id="reviewer", reviewer_model="gpt-6-sol",
                    reviewed_at=datetime.now(timezone.utc), review_status="approved",
                )
                db.add(evidence)
                db.flush()
                db.add(KifuPlayerName(
                    player_id=player_id, lang=lang, display_name=display, status="verified",
                    decision_kind="conventional", generation_rule_version="test-v1",
                    revision=1, evidence_id=evidence.id,
                ))
            db.commit()
        report = progress_report(engine)
        assert report["players"]["complete_11"] == 1
        assert report["players"]["complete_11_ratio"] == 1.0
        assert report["albums"]["both_players_complete_11"] == 1
        assert report["albums"]["complete_11"] == 1
        assert report["albums"]["complete_11_ratio"] == 1.0
        with Session(engine) as db:
            name = db.query(KifuPlayerName).filter_by(lang="ua").one()
            db.get(KifuNameResearchEvidence, name.evidence_id).review_status = "pending"
            db.commit()
        revoked = progress_report(engine)
        assert revoked["players"]["complete_11"] == 0
        assert revoked["albums"]["complete_11"] == 0
    finally:
        engine.dispose()


def test_unlinked_raw_name_object_counts_only_all_eleven_qualified_rows():
    engine = _catalog()
    try:
        with Session(engine) as db:
            registry_id = db.query(KifuNameResearchEvidence.source_registry_id).scalar()
            raw = KifuRawPlayerValue(raw_value="Unlinked White", category="readable", review_status="approved")
            db.add(raw)
            db.flush()
            for lang in sorted(LANGUAGES):
                display = f"White {lang}"
                evidence = KifuNameResearchEvidence(
                    raw_player_id=raw.id, lang=lang, revision=1, source_registry_id=registry_id,
                    candidate_name=display, decision_kind="conventional", generation_rule_version="test-v1",
                    research_payload={}, producer_id="researcher", producer_model="gpt-6-luna",
                    reviewer_id="reviewer", reviewer_model="gpt-6-sol",
                    reviewed_at=datetime.now(timezone.utc), review_status="approved",
                )
                db.add(evidence)
                db.flush()
                db.add(KifuRawPlayerName(
                    raw_player_id=raw.id, lang=lang, display_name=display, status="verified",
                    decision_kind="conventional", generation_rule_version="test-v1",
                    revision=1, evidence_id=evidence.id,
                ))
            db.commit()
        report = progress_report(engine)
        assert report["unlinked_raw_values"]["players"]["complete_11"] == 1
        assert report["unlinked_raw_values"]["players"]["complete_11_all_occurrences"] == 1
        with Session(engine) as db:
            row = db.query(KifuRawPlayerName).filter_by(lang="ua").one()
            db.get(KifuNameResearchEvidence, row.evidence_id).review_status = "pending"
            db.commit()
        assert progress_report(engine)["unlinked_raw_values"]["players"]["complete_11"] == 0
    finally:
        engine.dispose()
