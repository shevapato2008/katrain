"""The authorized first pass is generated provenance with exact inputs."""

from copy import deepcopy
from types import SimpleNamespace

import pytest

from katrain.web.kifu.name_candidates import CandidateError, canonical_sha256, validate_candidate
from katrain.web.kifu.name_evidence import EvidenceError, registry_sha256, validate_research_record
from katrain.web.kifu.name_batch import BatchError, _image, apply_bundle, dry_run_bundle, catalog_snapshot_sha
from katrain.web.kifu.name_inventory import build_inventory
from katrain.web.core.models_db import (
    KifuAlbum, KifuPlayer, KifuPlayerName, KifuEvent, KifuEventName,
    KifuRawEventValue, KifuNameResearchEvidence,
)
from katrain.web.kifu.identity import (
    _approved_names, _qualified_name_rows, _approved_raw_event_names, _raw_event_map,
    live_event_selections, strict_raw_event_search_clause, strict_selected_event_search_ids,
    strict_display_maps,
)
from katrain.web.kifu.name_first_pass import raw_scope_rows
from katrain.web.kifu.name_coverage import coverage_report
from sqlalchemy.orm import Session
from tests.web_ui._kifu_selection_helpers import apply_reviewed_selection
from tests.web_ui.test_kifu_name_candidates import inventory, registry
from tests.web_ui.test_kifu_name_batch import engine, player_bundle, bind_fixture_candidate, registry as db_registry


def first_pass_pair():
    owner = {"kind": "player", "id": 17}
    research = {
        "owner": owner, "lang": "cn", "registry_version": "test-1",
        "registry_sha256": registry_sha256(registry()),
        "source_basis": "user_authorized_first_pass_v1",
        "scope_status": "generated_first_pass", "verification_level": "generated_first_pass",
        "original_name": "吴清源", "original_language": "und",
        "source_input": {"kind": "catalog_canonical", "owner": owner, "text": "吴清源",
                         "owner_preimage_sha256": "a" * 64},
        "generation": {"method": "retain_original"}, "candidate_name": "吴清源",
        "producer_id": "translator", "producer_model": "gpt-6-luna", "review_status": "pending",
    }
    candidate = {
        "owner": owner, "lang": "cn", "display_name": "吴清源", "decision_kind": "generated",
        "research_sha256": canonical_sha256(research),
        "generation_rule_version": "user_authorized_first_pass_v1",
        "producer_id": "translator", "producer_model": "gpt-6-luna",
        "produced_at": "2026-10-11T01:00:00Z", "review_status": "approved",
        "reviewer_id": "reviewer", "reviewer_model": "gpt-6.1-sol",
        "reviewed_at": "2026-10-11T01:01:00Z",
        "review_conclusion": "approved_first_pass_display_and_source",
        "generated_review": {"decision": "approve_generated_first_pass", "owner": owner,
                             "lang": "cn", "display_name": "吴清源",
                             "research_sha256": canonical_sha256(research),
                             "reviewer_id": "reviewer", "reviewer_model": "gpt-6.1-sol",
                             "reviewed_at": "2026-10-11T01:01:00Z"},
    }
    return candidate, research


def test_first_pass_uses_actual_source_without_external_claims():
    candidate, research = first_pass_pair()
    assert validate_research_record(research, registry())["candidate_name"] == "吴清源"
    assert validate_candidate(candidate, research, registry(), inventory())["display_name"] == "吴清源"


def test_first_pass_rejects_mixed_and_unsourced_markers():
    candidate, research = first_pass_pair()
    for key, value in (("negative_closure", {}), ("source_checks", []),
                       ("original_language_basis_url", "https://example.org")):
        bad = deepcopy(research)
        bad[key] = value
        with pytest.raises(EvidenceError):
            validate_research_record(bad, registry())
    bad = deepcopy(candidate)
    bad["decision_kind"] = "conventional"
    with pytest.raises(CandidateError):
        validate_candidate(bad, research, registry(), inventory())


def test_first_pass_keeps_common_player_rank_guard():
    candidate, research = first_pass_pair()
    research["candidate_name"] = "吴清源九段"
    research["generation"]["method"] = "transliteration"
    candidate["display_name"] = candidate["generated_review"]["display_name"] = "吴清源九段"
    candidate["research_sha256"] = candidate["generated_review"]["research_sha256"] = canonical_sha256(research)
    with pytest.raises(CandidateError, match="rank|result"):
        validate_candidate(candidate, research, registry(), inventory())


@pytest.mark.parametrize("raw", ["GNUGo3.8", "个人赛", "(;EV[broken]"])
def test_first_pass_raw_rejects_program_generic_and_damaged_values(raw):
    _candidate, research = first_pass_pair()
    owner = {"kind": "raw_event", "id": 7}
    research.update(owner=owner, original_name=raw, candidate_name="Translated title")
    research["source_input"] = {"kind": "raw_event_literal", "owner": owner, "text": raw,
                                "owner_preimage_sha256": "a" * 64}
    research["raw_scope"] = {"raw_value": raw, "slots": [
        {"album_id": 1, "slot": "event", "raw_value": raw, "event_id": None,
         "approved": True}]}
    with pytest.raises(EvidenceError, match="program|generic|damaged"):
        validate_research_record(research, registry())


def bound_player_bundle(engine):
    inv = build_inventory(engine)
    bundle, _ = player_bundle(inv)
    row, research = first_pass_pair()
    with engine.connect() as conn:
        owner_image = _image(conn, KifuPlayer.__table__, 17)
    research["source_input"]["owner_preimage_sha256"] = canonical_sha256(owner_image)
    research["registry_sha256"] = registry_sha256(db_registry())
    row["research_sha256"] = canonical_sha256(research)
    row["generated_review"]["research_sha256"] = row["research_sha256"]
    row["name_preimage_sha256"] = None
    bind_fixture_candidate(row)
    row["preimage_binding"]["captured_at"] = "2026-10-11T01:00:15Z"
    row["preimage_binding"]["bound_at"] = "2026-10-11T01:00:30Z"
    bundle["members"] = [{"owner": row["owner"], "lang": "cn"}]
    bundle["member_set_sha256"] = canonical_sha256(bundle["members"])
    bundle["candidates"] = [row]
    declaration = {"owner": row["owner"], "preimage": owner_image}
    bundle.update(bundle_format=2, catalog_sha256=catalog_snapshot_sha(engine),
                  owners=[declaration], owner_set_sha256=canonical_sha256([declaration]),
                  album_links=[], link_set_sha256=canonical_sha256([]))
    return inv, bundle, [research]


def test_first_pass_apply_read_and_retry_require_persisted_proof(engine):
    inv, bundle, research = bound_player_bundle(engine)
    assert dry_run_bundle(engine, bundle, db_registry(), inv, research)["ready"]
    result = apply_bundle(engine, bundle, db_registry(), inv, research)
    assert result["status"] == "applied"
    with engine.connect() as conn:
        name = conn.execute(KifuPlayerName.__table__.select()).mappings().one()
        evidence = conn.execute(KifuNameResearchEvidence.__table__.select()).mappings().one()
        assert evidence["research_payload"]["first_pass"]["verification_level"] == "generated_first_pass"
    with Session(engine) as db:
        query = _approved_names(db, KifuPlayerName, "player_id", {17}, "cn")
        assert len(_qualified_name_rows(db, query, KifuPlayerName, "player_id")) == 1
    assert apply_bundle(engine, bundle, db_registry(), inv, research)["status"] == "already_applied"
    with engine.begin() as conn:
        changed = deepcopy(evidence["research_payload"])
        changed.pop("first_pass")
        conn.execute(KifuNameResearchEvidence.__table__.update().values(research_payload=changed))
    with Session(engine) as db:
        query = _approved_names(db, KifuPlayerName, "player_id", {17}, "cn")
        assert _qualified_name_rows(db, query, KifuPlayerName, "player_id") == []
    with pytest.raises(BatchError):
        apply_bundle(engine, bundle, db_registry(), inv, research)
    with engine.begin() as conn:
        changed["research"].pop("source_basis")
        changed["research"].pop("scope_status")
        changed["research"].pop("verification_level")
        changed["candidate"]["generation_rule_version"] = "other-rule"
        conn.execute(KifuNameResearchEvidence.__table__.update().values(
            generation_rule_version="other-rule", research_payload=changed))
        conn.execute(KifuPlayerName.__table__.update().values(generation_rule_version="other-rule"))
    with Session(engine) as db:
        query = _approved_names(db, KifuPlayerName, "player_id", {17}, "cn")
        assert _qualified_name_rows(db, query, KifuPlayerName, "player_id") == []


def test_first_pass_canonical_owner_cas_catches_pages_drift(engine):
    inv, bundle, research = bound_player_bundle(engine)
    with engine.begin() as conn:
        conn.execute(KifuPlayer.__table__.update().where(KifuPlayer.id == 17).values(
            authoritative_pages=[{"url": "https://example.org/new"}]))
    with pytest.raises(BatchError, match="owner catalog preimage differs|source owner changed"):
        dry_run_bundle(engine, bundle, db_registry(), inv, research)


def test_first_pass_event_series_is_qualified_for_read(engine):
    with engine.begin() as conn:
        conn.execute(KifuEvent.__table__.insert().values(id=4, canonical_name="Oteai"))
        conn.execute(KifuAlbum.__table__.update().where(KifuAlbum.id == 11).values(event_id=4))
    inv, bundle, records = bound_player_bundle(engine)
    owner = {"kind": "event", "id": 4}
    with engine.connect() as conn:
        owner_image = _image(conn, KifuEvent.__table__, 4)
    research = records[0]
    research.update(owner=owner, lang="en", original_name="Oteai", candidate_name="Oteai")
    research["source_input"] = {"kind": "catalog_canonical", "owner": owner, "text": "Oteai",
                                "owner_preimage_sha256": canonical_sha256(owner_image)}
    candidate = bundle["candidates"][0]
    candidate.update(owner=owner, lang="en", display_name="Oteai", research_sha256=canonical_sha256(research))
    candidate["generated_review"].update(owner=owner, lang="en", display_name="Oteai",
                                          research_sha256=candidate["research_sha256"])
    candidate["preimage_binding"]["source_candidate_sha256"] = canonical_sha256(candidate)
    member = {"owner": owner, "lang": "en"}
    declaration = {"owner": owner, "preimage": owner_image}
    bundle.update(members=[member], member_set_sha256=canonical_sha256([member]),
                  owners=[declaration], owner_set_sha256=canonical_sha256([declaration]),
                  catalog_sha256=catalog_snapshot_sha(engine))
    assert dry_run_bundle(engine, bundle, db_registry(), inv, [research])["ready"]
    apply_bundle(engine, bundle, db_registry(), inv, [research])
    with Session(engine) as db:
        query = _approved_names(db, KifuEventName, "event_id", {4}, "en")
        assert [row.display_name for row, _ in _qualified_name_rows(db, query, KifuEventName, "event_id")] == ["Oteai"]


def test_first_pass_can_fill_existing_unlinked_catalog_player(engine):
    with engine.begin() as conn:
        conn.execute(KifuPlayer.__table__.insert().values(id=99, canonical_name="Unused"))
    inv, bundle, records = bound_player_bundle(engine)
    owner = {"kind": "player", "id": 99}
    with engine.connect() as conn:
        owner_image = _image(conn, KifuPlayer.__table__, 99)
    research = records[0]
    research.update(owner=owner, original_name="Unused", candidate_name="闲置")
    research["source_input"] = {"kind": "catalog_canonical", "owner": owner, "text": "Unused",
                                "owner_preimage_sha256": canonical_sha256(owner_image)}
    research["generation"]["method"] = "translation"
    candidate = bundle["candidates"][0]
    candidate.update(owner=owner, display_name="闲置", research_sha256=canonical_sha256(research))
    candidate["generated_review"].update(owner=owner, display_name="闲置",
                                          research_sha256=candidate["research_sha256"])
    member = {"owner": owner, "lang": "cn"}
    declaration = {"owner": owner, "preimage": owner_image}
    bundle.update(members=[member], member_set_sha256=canonical_sha256([member]),
                  owners=[declaration], owner_set_sha256=canonical_sha256([declaration]),
                  catalog_sha256=catalog_snapshot_sha(engine))
    assert dry_run_bundle(engine, bundle, db_registry(), inv, [research])["ready"]
    apply_bundle(engine, bundle, db_registry(), inv, [research])
    with Session(engine) as db:
        query = _approved_names(db, KifuPlayerName, "player_id", {99}, "cn")
        assert [row.display_name for row, _ in _qualified_name_rows(db, query, KifuPlayerName, "player_id")] == ["闲置"]


def test_first_pass_raw_title_stays_on_exact_public_direct_slot(engine):
    with engine.begin() as conn:
        conn.execute(KifuAlbum.__table__.update().where(KifuAlbum.id == 11).values(
            source="https://19x19.com", source_path="data/kifu-album/19x19/one.sgf",
            date_played="1934-10-01", board_size=19,
            sgf_content="(;FF[4]SZ[19]SO[https://19x19.com]GN[GNUGo3.8]GN[Other]GC[Other | 1手])"))
        conn.execute(KifuAlbum.__table__.insert().values(
            id=12, player_black="Black", player_white="White", event="Other",
            sgf_content="(;FF[4]EV[Other])", source_path="other.sgf"))
    apply_reviewed_selection(engine, 11)
    inv = build_inventory(engine, inventory_format=4)
    owner = {"kind": "raw_event", "id": 8}
    with engine.connect() as conn:
        owner_image = _image(conn, KifuRawEventValue.__table__, 8)
        slots = raw_scope_rows(conn, "Other")
    research = {
        "owner": owner, "lang": "en", "registry_version": "test-1",
        "registry_sha256": registry_sha256(db_registry()),
        "source_basis": "user_authorized_first_pass_v1",
        "scope_status": "generated_first_pass", "verification_level": "generated_first_pass",
        "original_name": "Other", "original_language": "und",
        "source_input": {"kind": "raw_event_literal", "owner": owner, "text": "Other",
                         "owner_preimage_sha256": canonical_sha256(owner_image)},
        "raw_scope": {"raw_value": "Other", "slots": slots},
        "generation": {"method": "translation"}, "candidate_name": "Another event",
        "producer_id": "translator", "producer_model": "gpt-6-luna", "review_status": "pending",
    }
    member = {"owner": owner, "lang": "en", "raw_value": "Other"}
    candidate = bind_fixture_candidate({
        **member, "display_name": "Another event", "decision_kind": "generated",
        "research_sha256": canonical_sha256(research),
        "generation_rule_version": "user_authorized_first_pass_v1", "name_preimage_sha256": None,
        "producer_id": "translator", "producer_model": "gpt-6-luna",
        "produced_at": "2026-10-11T01:00:00Z", "review_status": "approved",
        "reviewer_id": "reviewer", "reviewer_model": "gpt-6.1-sol",
        "reviewed_at": "2026-10-11T01:01:00Z",
        "review_conclusion": "approved_first_pass_display_and_source",
        "generated_review": {"decision": "approve_generated_first_pass", "owner": owner,
                             "lang": "en", "display_name": "Another event",
                             "research_sha256": canonical_sha256(research),
                             "reviewer_id": "reviewer", "reviewer_model": "gpt-6.1-sol",
                             "reviewed_at": "2026-10-11T01:01:00Z"},
    })
    candidate["preimage_binding"]["captured_at"] = "2026-10-11T01:00:15Z"
    candidate["preimage_binding"]["bound_at"] = "2026-10-11T01:00:30Z"
    declaration = {"owner": owner, "preimage": owner_image, "occurrence_album_ids": [11, 12],
                   "occurrence_sha256": canonical_sha256([11, 12])}
    bundle = {"bundle_format": 2, "inventory_format": inv["inventory_format"],
              "inventory_sha256": inv["sha256"], "registry_version": "test-1",
              "registry_sha256": registry_sha256(db_registry()), "rule_version": "first-pass-v1",
              "catalog_sha256": catalog_snapshot_sha(engine), "members": [member],
              "member_set_sha256": canonical_sha256([member]), "candidates": [candidate],
              "owners": [declaration], "owner_set_sha256": canonical_sha256([declaration]),
              "album_links": [], "link_set_sha256": canonical_sha256([])}
    assert dry_run_bundle(engine, bundle, db_registry(), inv, [research])["ready"]
    apply_bundle(engine, bundle, db_registry(), inv, [research])
    with Session(engine) as db:
        rows = _approved_raw_event_names(db, values={"Other"}, lang="en")
        assert len(rows) == 1
        albums = db.query(KifuAlbum).filter(KifuAlbum.id.in_([11, 12])).all()
        selected = live_event_selections(db, albums, album_ids={11})
        assert _raw_event_map(rows, albums, selected) == {
            (11, "Other", None): "Another event", (12, "Other", None): "Another event"}
        assert _raw_event_map(rows, [SimpleNamespace(id=12, event="Other", event_id=None)], {}) == {
            (12, "Other", None): "Another event"}
        assert strict_display_maps(db, albums, "en", selected_events=selected)[-1] == {
            (11, "Other", None): "Another event", (12, "Other", None): "Another event"}
        assert {item.id for item in db.query(KifuAlbum).filter(strict_raw_event_search_clause(db, {rows[0][0].id}))} == {12}
        assert strict_selected_event_search_ids(db, "Another event", {rows[0][0].id}, set()) == {11}
    coverage = coverage_report(engine, inv, languages=("en",))
    assert not any(item["slot"] == "event" and item["album_id"] in {11, 12}
                   for item in coverage["missing_examples"])
