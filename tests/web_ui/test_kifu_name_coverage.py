"""Coverage counts actual approved displays for each album slot and language."""

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from katrain.web.core.models_db import (
    Base,
    KifuAlbum,
    KifuAlbumEventSelection,
    KifuEventSelectionBatch,
    KifuNameResearchEvidence,
    KifuNameSourceRegistry,
    KifuPlayer,
    KifuPlayerName,
    KifuRawEventName,
    KifuRawEventValue,
)
from katrain.web.kifu.name_coverage import coverage_report
from katrain.web.kifu.name_inventory import build_inventory
from katrain.web.kifu.provenance import sgf_sha256


def _catalog():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        player = KifuPlayer(canonical_name="Go Seigen")
        registry = KifuNameSourceRegistry(version="test", sha256="a" * 64, registry={})
        db.add_all([player, registry])
        db.flush()
        evidence = KifuNameResearchEvidence(
            player_id=player.id, lang="cn", revision=1, source_registry_id=registry.id,
            candidate_name="吴清源", decision_kind="conventional", generation_rule_version="test-v1",
            research_payload={}, producer_id="researcher", producer_model="gpt-6-luna",
            reviewer_id="reviewer", reviewer_model="gpt-6-sol",
            reviewed_at=datetime.now(timezone.utc), review_status="approved",
        )
        db.add(evidence)
        db.flush()
        db.add(KifuPlayerName(
            player_id=player.id, lang="cn", display_name="吴清源", status="verified",
            decision_kind="conventional", generation_rule_version="test-v1",
            revision=1, evidence_id=evidence.id,
        ))
        db.add(KifuAlbum(
            player_black="Go Seigen", player_white="Unlinked White", black_player_id=player.id,
            event="Oteai", date_played="1934-10-10", sgf_content="(;B[aa])", source_path="a.sgf",
        ))
        db.commit()
    return engine


def test_coverage_counts_real_approved_slots_and_missing_fallbacks():
    engine = _catalog()
    try:
        inventory = build_inventory(engine)
        result = coverage_report(engine, inventory, languages=("cn",), batch_size=1)
        assert result["inventory_sha256"] == inventory["sha256"]
        assert result["albums"] == 1
        assert result["languages"]["cn"]["slots"] == 3
        assert result["languages"]["cn"]["approved"] == 1
        assert result["languages"]["cn"]["missing"] == 2
        assert result["languages"]["cn"]["by_decision"] == {"conventional": 1}
        assert result["complete"] is False  # One language never proves all eleven.
        assert {row["slot"] for row in result["missing_examples"]} == {"white", "event"}
    finally:
        engine.dispose()


def test_coverage_rejects_a_snapshot_that_no_longer_matches_album_metadata():
    engine = _catalog()
    try:
        inventory = build_inventory(engine)
        with Session(engine) as db:
            album = db.query(KifuAlbum).one()
            album.player_black = "Changed after snapshot"
            db.commit()
        with pytest.raises(RuntimeError, match="snapshot drift"):
            coverage_report(engine, inventory, languages=("cn",), batch_size=1)
    finally:
        engine.dispose()


def test_missing_digest_is_stable_across_database_page_sizes():
    engine = _catalog()
    try:
        with Session(engine) as db:
            db.add(KifuAlbum(
                player_black="Another", player_white="Player", event="Another event",
                sgf_content="(;B[pp])", source_path="b.sgf",
            ))
            db.commit()
        inventory = build_inventory(engine)
        one = coverage_report(engine, inventory, languages=("cn", "ru"), batch_size=1)
        two = coverage_report(engine, inventory, languages=("cn", "ru"), batch_size=2)
        assert one["missing_sha256"] == two["missing_sha256"]
        assert one["languages"] == two["languages"]
    finally:
        engine.dispose()


def test_absent_event_is_an_explicit_empty_display_decision():
    engine = _catalog()
    try:
        with Session(engine) as db:
            album = db.query(KifuAlbum).one()
            album.event = None
            db.commit()
        inventory = build_inventory(engine)
        result = coverage_report(engine, inventory, languages=("cn",), batch_size=1)
        counts = result["languages"]["cn"]
        assert counts["approved"] == 2
        assert counts["missing"] == 1
        assert counts["by_decision"] == {"conventional": 1, "hidden": 1}
        assert {gap["slot"] for gap in result["missing_examples"]} == {"white"}
    finally:
        engine.dispose()


def test_selected_event_coverage_tracks_live_sgf_and_reports_drift():
    engine = _catalog()
    raw = "第5届韩国最强棋士战预选"
    sgf = (
        "(;FF[4]SZ[19]SO[https://19x19.com]"
        f"GN[GNUGo3.8]GN[{raw}]GC[{raw} | 194手];B[aa])"
    )
    try:
        with Session(engine) as db:
            value = KifuRawEventValue(raw_value=raw, category="game_description", review_status="approved")
            db.add(value)
            db.flush()
            registry = db.query(KifuNameSourceRegistry).one()
            evidence = KifuNameResearchEvidence(
                raw_event_id=value.id, lang="cn", revision=1, source_registry_id=registry.id,
                candidate_name="韩国最强棋士战预选", decision_kind="conventional",
                generation_rule_version="test-v1", research_payload={},
                producer_id="researcher", producer_model="gpt-6-luna",
                reviewer_id="reviewer", reviewer_model="gpt-6-sol",
                reviewed_at=datetime.now(timezone.utc), review_status="approved",
            )
            db.add(evidence)
            db.flush()
            db.add(KifuRawEventName(
                raw_event_id=value.id, lang="cn", display_name="韩国最强棋士战预选",
                status="verified", decision_kind="conventional", generation_rule_version="test-v1",
                revision=1, evidence_id=evidence.id,
            ))
            album = KifuAlbum(
                player_black="Black", player_white="White", event="GNUGo3.8",
                sgf_content=sgf, source="https://19x19.com",
                source_path="data/kifu-album/19x19/coverage.sgf",
            )
            db.add(album)
            db.flush()
            reviewed_at = datetime.now(timezone.utc)
            batch = KifuEventSelectionBatch(
                bundle_sha256="a" * 64, member_set_sha256="b" * 64, reviewed_artifact={},
                producer_id="producer", reviewer_id="reviewer", reviewed_at=reviewed_at, status="applied",
            )
            db.add(batch)
            db.flush()
            db.add(KifuAlbumEventSelection(
                album_id=album.id, batch_id=batch.id, selected_raw=raw, sgf_sha256=sgf_sha256(sgf),
                property_name="GN", property_index=1, status="approved",
                rule_version="19x19-gnugo-second-gn-v1", reviewer_id="reviewer", reviewed_at=reviewed_at,
            ))
            db.commit()
            album_id = album.id
        inventory = build_inventory(engine)
        assert inventory["inventory_format"] == 3
        before = coverage_report(engine, inventory, languages=("cn",), batch_size=1)
        assert before["languages"]["cn"]["approved"] == 2
        assert before["event_selection_drift"] == 0
        with Session(engine) as db:
            db.query(KifuAlbum).filter(KifuAlbum.id == album_id).one().sgf_content += " "
            db.commit()
        after = coverage_report(engine, inventory, languages=("cn",), batch_size=2)
        assert after["event_selection_drift"] == 1
        assert after["event_selection_sha256"] != before["event_selection_sha256"]
        assert {gap["slot"] for gap in after["missing_examples"] if gap["album_id"] == album_id} == {
            "black", "white", "event"
        }
        assert after["complete"] is False
    finally:
        engine.dispose()
