"""Event title translations retain original evidence without claiming conventional usage."""

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from katrain.web.core.models_db import KifuAlbum, KifuEvent, KifuEventName, KifuNameResearchEvidence
from katrain.web.kifu.identity import strict_display_maps, strict_matching_names
from katrain.web.kifu.name_batch import BatchError, apply_bundle, dry_run_bundle
from katrain.web.kifu.name_candidates import CandidateError, canonical_sha256, validate_candidate
from katrain.web.kifu.name_evidence import EvidenceError, registry_sha256, validate_research_record
from katrain.web.kifu.name_inventory import build_inventory
from tests.web_ui.test_kifu_name_batch import bind_fixture_candidate, engine  # noqa: F401
from tests.web_ui.test_kifu_name_candidates import bundle, candidate, check, inventory, registry


def translated(lang="en", display="Tengen tournament"):
    owner = {"kind": "event", "id": 3}
    evidence = {
        "owner": owner, "lang": lang, "registry_version": "test-1",
        "registry_sha256": registry_sha256(registry()), "scope_status": "translated_from_original",
        "candidate_name": display, "translation_method": "literal_event_title",
        "original_name": "天元戦", "original_language": "ja",
        "original_language_basis_url": "https://example.org/tengen",
        "source_checks": [check(owner=owner, query="天元戦", url="https://example.org/tengen",
                                observed_lang="ja", candidate_name="天元戦", body_excerpt="日本の棋戦、天元戦。",
                                identity_basis="The title and organizer identify the existing Japanese event")],
        "producer_id": "researcher-1", "producer_model": "gpt-6-luna", "review_status": "pending",
    }
    row = candidate(owner=owner, lang=lang, display_name=display, decision_kind="translated",
                    research_sha256=canonical_sha256(evidence), generation_rule_version="event-title-translation-v1",
                    translation_method="literal_event_title", name_preimage_sha256=None,
                    review_conclusion="Checked the original competition identity and exact title translation")
    return row, evidence


@pytest.mark.parametrize("lang,display", [
    ("en", "Tengen tournament"), ("cn", "天元战"), ("tw", "天元戰"), ("jp", "天元戦"), ("ko", "천원전"),
])
def test_translated_event_accepts_original_language_identity_and_target_script(lang, display):
    row, evidence = translated(lang, display)
    assert validate_research_record(evidence, registry())["scope_status"] == "translated_from_original"
    assert validate_candidate(row, evidence, registry(), inventory()) == row
    row["display_name"] = evidence["candidate_name"] = "12345"
    row["research_sha256"] = canonical_sha256(evidence)
    with pytest.raises(CandidateError, match="script"):
        validate_candidate(row, evidence, registry(), inventory())


@pytest.mark.parametrize("owner", [
    {"kind": "player", "id": 17}, {"kind": "raw_event", "id": 3}, {"kind": "event", "ref": "new-event"},
])
def test_translation_rejects_players_raw_owners_and_new_identity_refs(owner):
    row, evidence = translated()
    evidence["owner"] = evidence["source_checks"][0]["owner"] = row["owner"] = owner
    row["research_sha256"] = canonical_sha256(evidence)
    with pytest.raises(EvidenceError, match="existing event"):
        validate_research_record(evidence, registry())
    with pytest.raises(CandidateError):
        validate_candidate(row, evidence, registry(), inventory())


@pytest.mark.parametrize("changes", [
    {"identity_basis": ""}, {"candidate_name": "Tengen tournament", "body_excerpt": "Tengen tournament"},
    {"observed_lang": "en"}, {"owner": {"kind": "event", "id": 99}},
    {"http_status": 404}, {"body_sha256": ""}, {"body_excerpt": "Different event"},
])
def test_translation_rejects_missing_identity_and_wrong_original_evidence(changes):
    _, evidence = translated()
    evidence["source_checks"][0].update(changes)
    with pytest.raises(EvidenceError):
        validate_research_record(evidence, registry())


@pytest.mark.parametrize("changes", [
    {"original_language_basis_url": "https://example.org/unrelated"},
    {"translation_method": ""}, {"lang": "ru"},
])
def test_translation_requires_bound_original_source_and_explicit_method(changes):
    _, evidence = translated()
    evidence.update(changes)
    with pytest.raises(EvidenceError):
        validate_research_record(evidence, registry())


def test_translated_event_requires_independent_review_and_cannot_claim_conventional():
    row, evidence = translated()
    for changes in ({"reviewer_id": row["producer_id"]}, {"decision_kind": "conventional"},
                    {"translation_method": "phonetic"}, {"generation_rule_version": "none"}):
        with pytest.raises(CandidateError):
            validate_candidate({**row, **changes}, evidence, registry(), inventory())


def event_bundle(engine):
    with engine.begin() as conn:
        conn.execute(KifuEvent.__table__.insert().values(id=3, canonical_name="日本天元戦"))
        conn.execute(KifuAlbum.__table__.update().values(event_id=3))
    inv = build_inventory(engine)
    row, evidence = translated()
    bind_fixture_candidate(row)
    member = {"owner": row["owner"], "lang": row["lang"]}
    proposed = bundle(members=[member], candidates=[row], inventory_sha256=inv["sha256"])
    return proposed, inv, [evidence]


def test_translated_event_import_retains_provenance_and_appears_in_display_and_search(engine):
    proposed, inv, evidence = event_bundle(engine)
    assert dry_run_bundle(engine, proposed, registry(), inv, evidence)["approved"] == 1
    apply_bundle(engine, proposed, registry(), inv, evidence)
    with Session(engine) as db:
        name = db.scalar(select(KifuEventName))
        proof = db.get(KifuNameResearchEvidence, name.evidence_id)
        assert name.decision_kind == proof.decision_kind == "translated"
        assert proof.research_payload["research"] == evidence[0]
        assert proof.research_payload["candidate"]["translation_method"] == "literal_event_title"
        album = db.get(KifuAlbum, 11)
        assert strict_display_maps(db, [album], "en")[1] == {3: "Tengen tournament"}
        assert strict_matching_names(db, "Tengen tournament")[1] == {3}


def test_translated_event_still_checks_existing_name_collisions(engine):
    proposed, inv, evidence = event_bundle(engine)
    with engine.begin() as conn:
        conn.execute(KifuEvent.__table__.insert().values(id=4, canonical_name="Other event"))
        conn.execute(KifuEventName.__table__.insert().values(
            event_id=4, lang="en", display_name="Tengen tournament", status="verified"))
    with pytest.raises(BatchError, match="collision"):
        dry_run_bundle(engine, proposed, registry(), inv, evidence)


def test_legacy_event_exact_search_requires_matching_approved_evidence(engine):
    from deploy.ucloud.kifu_cn_first_pass_legacy.identity import matching_entity_ids

    proposed, inv, evidence = event_bundle(engine)
    apply_bundle(engine, proposed, registry(), inv, evidence)
    with Session(engine) as db:
        db.add(KifuEvent(id=4, canonical_name="Other event"))
        db.commit()
        assert matching_entity_ids(db, "Tengen tournament", exact=True) == (set(), {3})
        for field, value in (("event_id", 4), ("review_status", "pending")):
            proof = db.scalar(select(KifuNameResearchEvidence))
            setattr(proof, field, value)
            db.flush()
            assert matching_entity_ids(db, "Tengen tournament", exact=True) == (set(), set())
            db.rollback()
