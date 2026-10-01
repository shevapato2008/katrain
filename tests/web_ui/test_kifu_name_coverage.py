"""Coverage counts actual approved displays for each album slot and language."""

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from katrain.web.core.models_db import (
    Base,
    KifuAlbum,
    KifuNameResearchEvidence,
    KifuNameSourceRegistry,
    KifuPlayer,
    KifuPlayerName,
)
from katrain.web.kifu.name_coverage import coverage_report
from katrain.web.kifu.name_inventory import build_inventory


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
