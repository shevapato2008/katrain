"""Approved display decisions require exact scope, evidence and independent review."""

from copy import deepcopy
import hashlib
import json

import pytest

from katrain.web.kifu.name_candidates import (
    CandidateError,
    canonical_sha256,
    classification_template_sha256,
    _occurrence_indexes,
    identity_scope_sha256,
    validate_bundle,
    validate_candidate,
    render_event_components,
)
from katrain.web.kifu.name_evidence import (
    negative_closure_evidence_sha256, negative_closure_scope_sha256,
    negative_closure_template_sha256, registry_sha256,
)
from scripts.kifu_name_candidates import main


LANGS = ("en", "cn", "tw", "jp", "ko", "de", "es", "fr", "ru", "tr", "ua")


def registry():
    return {
        "version": "test-1",
        "language_tags": {lang: {"cn": "zh-Hans", "tw": "zh-Hant", "jp": "ja", "ua": "uk"}.get(lang, lang)
                          for lang in LANGS},
        "sources": [
            {"id": "go", "tier": "language_go", "home_url": "https://example.org/", "language": "ru"},
            {"id": "wd", "tier": "discovery", "home_url": "https://www.wikidata.org/", "language": "mul"},
        ],
        "language_scopes": {lang: {"required_source_ids": ["go"], "complete_for_negative_claims": True}
                            for lang in LANGS},
    }


def inventory():
    return {
        "inventory_format": 2,
        "sha256": "a" * 64,
        "association_columns": ["id", "player_black", "player_white", "event", "black_player_id", "white_player_id", "event_id"],
        "album_associations": [
            [1, "吴清源九段", "Unknown", "GNUGo3.8", 17, None, None],
            [2, "吴清源九段", "木谷实", "JapanPromotionTournament,1934,Fall", 17, 18, 3],
        ],
    }


def check(status="found", **updates):
    item = {
        "owner": {"kind": "player", "id": 17}, "source_id": "go", "query": "Go Seigen",
        "status": status, "url": "https://example.org/go", "fetched_at": "2026-10-02T10:00:00Z",
        "http_status": 200, "body_sha256": hashlib.sha256(b"body").hexdigest(),
        "body_excerpt": "Profile for Го Сэйгэн", "observed_lang": "ru", "language_basis": "reviewed_text",
        "candidate_name": "Го Сэйгэн", "identity_basis": "Same historical player",
    }
    item.update(updates)
    return item


def research(**updates):
    item = {
        "owner": {"kind": "player", "id": 17}, "lang": "ru", "registry_version": "test-1",
        "registry_sha256": registry_sha256(registry()), "scope_status": "found",
        "candidate_name": "Го Сэйгэн", "source_checks": [check()],
        "original_name": "呉清源", "original_language": "ja",
        "original_language_basis_url": "https://example.org/go",
        "reading": "ご せいげん", "reading_basis_url": "https://example.org/go",
        "producer_id": "researcher-1", "producer_model": "gpt-6-luna", "review_status": "pending",
    }
    item.update(updates)
    return item


def candidate(**updates):
    item = {
        "owner": {"kind": "player", "id": 17}, "lang": "ru", "display_name": "Го Сэйгэн",
        "decision_kind": "conventional", "research_sha256": canonical_sha256(research()),
        "generation_rule_version": "none", "producer_id": "researcher-1", "producer_model": "gpt-6-luna",
        "produced_at": "2026-10-02T10:01:00Z", "review_status": "approved",
        "reviewer_id": "reviewer-2", "reviewer_model": "gpt-6-luna",
        "reviewed_at": "2026-10-02T11:00:00Z", "review_conclusion": "confirmed profile and Russian usage",
    }
    item.update(updates)
    if item["decision_kind"] in {"generic", "hidden", "placeholder", "error"} and item["review_status"] == "approved":
        item["template_review"] = {
            "version": "classification-v1", "lang": item["lang"],
            "sha256": classification_template_sha256(item["lang"]),
            "reviewer_id": item["reviewer_id"], "reviewer_model": item["reviewer_model"],
            "reviewed_at": item["reviewed_at"], "conclusion": "Reviewed this language's classification phrases",
        }
    return item


def approved_generated(row, evidence):
    row = {**row, "review_conclusion": "approved_generated_display_and_rule"}
    row["generated_review"] = {
        "decision": "approve_generated", "display_name": row["display_name"],
        "owner": row["owner"], "lang": row["lang"],
        "generation_rule_version": row["generation_rule_version"],
        "research_sha256": row["research_sha256"],
        "original_name": evidence["original_name"], "reading": evidence["reading"],
        "reading_basis_url": evidence["reading_basis_url"],
        "reviewer_id": row["reviewer_id"], "reviewer_model": row["reviewer_model"],
        "reviewed_at": row["reviewed_at"],
        "reason": "Checked the exact spelling against the named rule and sourced reading",
    }
    return row


def member(owner=None, lang="ru", raw_value=None):
    item = {"owner": owner or {"kind": "player", "id": 17}, "lang": lang}
    if raw_value is not None:
        item["raw_value"] = raw_value
    return item


def bundle(*, members=None, candidates=None, **updates):
    items = members or [member()]
    result = {
        "bundle_format": 1, "inventory_format": 2, "inventory_sha256": "a" * 64,
        "registry_version": "test-1", "registry_sha256": registry_sha256(registry()),
        "rule_version": "candidate-v1", "members": items,
        "member_set_sha256": canonical_sha256(items), "candidates": candidates if candidates is not None else [candidate()],
    }
    result.update(updates)
    return result


def test_conventional_approved_name_requires_professional_target_language_body_and_independent_signature():
    assert validate_candidate(candidate(), research(), registry(), inventory())["review_status"] == "approved"
    for changes in (
        {"reviewer_id": "researcher-1"}, {"reviewer_model": ""}, {"reviewed_at": ""},
        {"review_conclusion": ""}, {"research_sha256": "b" * 64},
        {"display_name": "Go Seigen"}, {"owner": {"kind": "player", "id": 18}},
        {"lang": "ua"},
    ):
        with pytest.raises(CandidateError):
            validate_candidate(candidate(**changes), research(), registry(), inventory())


def test_write_ready_requires_independently_reviewed_preimage_binding():
    original = candidate()
    row = {**original, "name_preimage_sha256": None}
    before = validate_bundle(bundle(candidates=[row]), registry(), inventory(), [research()])
    assert before["ready"] and not before["write_ready"]
    binding = {
        "actor_id": "binder-3", "actor_model": "gpt-6.1-sol",
        "captured_at": "2026-10-02T10:05:00Z", "bound_at": "2026-10-02T10:10:00Z",
        "name_preimage_sha256": None, "source_candidate_sha256": canonical_sha256(original),
        "capture_sha256": "a" * 64,
    }
    ready = validate_bundle(bundle(candidates=[{**row, "preimage_binding": binding}]),
                            registry(), inventory(), [research()])
    assert ready["write_ready"]
    for bad in (
        {**binding, "actor_id": row["reviewer_id"]},
        {**binding, "bound_at": "2026-10-02T11:01:00Z"},
        {**binding, "captured_at": "2026-10-02T10:11:00Z"},
        {**binding, "name_preimage_sha256": "b" * 64},
        {**binding, "source_candidate_sha256": ""},
        {**binding, "capture_sha256": ""},
    ):
        report = validate_bundle(bundle(candidates=[{**row, "preimage_binding": bad}]),
                                 registry(), inventory(), [research()])
        assert report["ready"] and not report["write_ready"]


def test_approved_conventional_name_cannot_precede_its_source_capture():
    later = research(source_checks=[check(fetched_at="2026-10-03T10:00:00Z")])
    with pytest.raises(CandidateError, match="source capture"):
        validate_candidate(candidate(research_sha256=canonical_sha256(later)),
                           later, registry(), inventory())


def test_discovery_only_and_incomplete_research_do_not_approve_conventional_name():
    discovery = research(source_checks=[check(source_id="wd", url="https://www.wikidata.org/wiki/Q1")])
    with pytest.raises(CandidateError):
        validate_candidate(candidate(research_sha256=canonical_sha256(discovery)), discovery, registry(), inventory())
    incomplete = research(scope_status="incomplete", candidate_name="", source_checks=[check(
        status="unavailable", candidate_name="", url="https://example.org/go", http_status=429,
        body_sha256="", body_excerpt="", observed_lang="", language_basis="")])
    with pytest.raises(CandidateError):
        validate_candidate(candidate(research_sha256=canonical_sha256(incomplete)), incomplete, registry(), inventory())


def test_reviewed_wikipedia_article_can_support_conventional_name_but_wikidata_label_cannot():
    sources = registry()
    sources["sources"].append({"id": "ru-wp", "tier": "wikipedia_article",
                               "home_url": "https://ru.wikipedia.org/", "language": "ru"})
    passage = "Го Сэйгэн — профессиональный игрок го"
    article = check(source_id="ru-wp", url="https://ru.wikipedia.org/wiki/Го_Сэйгэн",
                    body_excerpt=passage,
                    article_evidence={"revision_id": "123456", "title": "Го Сэйгэн",
                                      "passage": passage,
                                      "passage_sha256": hashlib.sha256(passage.encode()).hexdigest(),
                                      "subject_identity": "Original name 呉清源 matches this player"},
                    identity_corroboration={"source_id": "go", "url": "https://example.org/go-seigen",
                                            "fetched_at": "2026-10-02T10:05:00Z", "http_status": 200,
                                            "body_sha256": hashlib.sha256(b"professional source").hexdigest(),
                                            "body_excerpt": "Professional archive: 呉清源, Go Seigen",
                                            "original_name": "呉清源", "identity_basis": "Same original name"})
    evidence = research(registry_sha256=registry_sha256(sources), source_checks=[article])
    proposed = candidate(research_sha256=canonical_sha256(evidence))
    assert validate_candidate(proposed, evidence, sources, inventory())["decision_kind"] == "conventional"
    article["identity_corroboration"]["fetched_at"] = "2026-10-03T10:00:00Z"
    evidence["source_checks"] = [article]
    with pytest.raises(CandidateError, match="source capture"):
        validate_candidate(candidate(research_sha256=canonical_sha256(evidence)),
                           evidence, sources, inventory())


def test_conflicting_found_names_need_explicit_exclusion_reason():
    conflicting = research(source_checks=[check(), check(candidate_name="Го Сейген",
                                                          body_excerpt="Alternate Го Сейген")])
    proposed = candidate(research_sha256=canonical_sha256(conflicting))
    with pytest.raises(CandidateError, match="conflicting"):
        validate_candidate(proposed, conflicting, registry(), inventory())
    proposed["excluded_candidates"] = [{"source_id": "go", "candidate_name": "Го Сейген",
                                         "reason": "Independent reviewer checked contemporary profile and selected preferred form"}]
    with pytest.raises(CandidateError, match="Sol"):
        validate_candidate(proposed, conflicting, registry(), inventory())
    proposed["reviewer_model"] = "gpt-6-sol"
    proposed["conflict_adjudication"] = {
        "agent_id": "reviewer-2", "model": "gpt-6-sol", "decided_at": "2026-10-02T10:30:00Z",
        "rationale": "Compared historical spellings against the identified player profile",
        "source_urls": ["https://example.org/go"],
    }
    assert validate_candidate(proposed, conflicting, registry(), inventory())["review_status"] == "approved"
    with pytest.raises(CandidateError, match="gpt-6-sol"):
        validate_candidate({**proposed, "reviewer_model": "gpt-6-astra"},
                           conflicting, registry(), inventory())
    with pytest.raises(CandidateError, match="gpt-6-sol"):
        validate_candidate({**proposed, "conflict_adjudication": {
            **proposed["conflict_adjudication"], "decided_at": "2026-10-02T12:00:00Z"}},
                           conflicting, registry(), inventory())


def test_pending_sol_producer_can_document_conflict_without_reviewer_signature():
    evidence = research(
        producer_model="gpt-6-sol",
        source_checks=[check(), check(candidate_name="Го Сейген", url="https://example.org/alternate",
                                      body_excerpt="Alternate Го Сейген")],
    )
    pending = candidate(
        producer_model="gpt-6-sol", research_sha256=canonical_sha256(evidence),
        review_status="pending", reviewer_id="", reviewer_model="", reviewed_at="", review_conclusion="",
        excluded_candidates=[{"source_id": "go", "candidate_name": "Го Сейген",
                              "reason": "The alternate requires independent language review"}],
        conflict_adjudication={
            "agent_id": "researcher-1", "model": "gpt-6-sol", "decided_at": "2026-10-02T10:30:00Z",
            "rationale": "Compared the two attested Russian spellings and retained both for review",
            "source_urls": ["https://example.org/go", "https://example.org/alternate"],
        },
    )
    assert validate_candidate(pending, evidence, registry(), inventory())["review_status"] == "pending"
    with pytest.raises(CandidateError, match="source URLs"):
        validate_candidate({**pending, "conflict_adjudication": {
            **pending["conflict_adjudication"], "source_urls": ["https://example.org/go"]}},
                           evidence, registry(), inventory())
    lightweight_evidence = {**evidence, "producer_model": "gpt-6-luna"}
    with pytest.raises(CandidateError, match="Sol"):
        validate_candidate({**pending, "producer_model": "gpt-6-luna",
                            "research_sha256": canonical_sha256(lightweight_evidence)},
                           lightweight_evidence, registry(), inventory())


def test_conflict_decision_and_approval_follow_all_attested_source_captures():
    late = research(source_checks=[
        check(),
        check(candidate_name="Го Сейген", url="https://example.org/alternate",
              body_excerpt="Alternate Го Сейген", fetched_at="2026-10-02T12:00:00Z"),
    ])
    approved = candidate(
        research_sha256=canonical_sha256(late), reviewer_model="gpt-6-sol",
        excluded_candidates=[{"source_id": "go", "candidate_name": "Го Сейген",
                              "reason": "Independently compared both attested forms"}],
        conflict_adjudication={
            "agent_id": "reviewer-2", "model": "gpt-6-sol", "decided_at": "2026-10-02T10:30:00Z",
            "rationale": "Compared both attested forms against the player identity",
            "source_urls": ["https://example.org/go", "https://example.org/alternate"],
        },
    )
    with pytest.raises(CandidateError, match="source|capture"):
        validate_candidate(approved, late, registry(), inventory())
    report = validate_bundle(bundle(candidates=[approved]), registry(), inventory(), [late])
    assert not report["ready"] and not report["write_ready"]

    fresh = deepcopy(late)
    fresh["source_checks"][1]["fetched_at"] = "2026-10-02T10:10:00Z"
    approved["research_sha256"] = canonical_sha256(fresh)
    assert validate_candidate(approved, fresh, registry(), inventory())["review_status"] == "approved"

    pending_research = deepcopy(late)
    pending_research["producer_model"] = "gpt-6-sol"
    pending = {**approved, "producer_model": "gpt-6-sol", "research_sha256": canonical_sha256(pending_research),
               "review_status": "pending", "reviewer_id": "", "reviewer_model": "", "reviewed_at": "",
               "review_conclusion": "", "conflict_adjudication": {
                   **approved["conflict_adjudication"], "agent_id": approved["producer_id"]}}
    with pytest.raises(CandidateError, match="source|capture"):
        validate_candidate(pending, pending_research, registry(), inventory())
    pending_research["source_checks"][1]["fetched_at"] = "2026-10-02T10:10:00Z"
    pending["research_sha256"] = canonical_sha256(pending_research)
    assert validate_candidate(pending, pending_research, registry(), inventory())["review_status"] == "pending"


def test_generated_name_requires_completed_negative_scope_and_reading_basis():
    negative = research(scope_status="not_found_in_scope", candidate_name="", source_checks=[check(
        status="not_found", candidate_name="", identity_basis="", body_excerpt="Search finished with no Russian name",
        search_scope="All player names", scope_complete=True, negative_outcome="no_target_string")])
    generated = approved_generated(candidate(display_name="Го Сэйгэн", decision_kind="generated",
                                             research_sha256=canonical_sha256(negative),
                                             generation_rule_version="ja-ru-v1"), negative)
    assert validate_candidate(generated, negative, registry(), inventory())["decision_kind"] == "generated"
    with pytest.raises(CandidateError, match="generated review"):
        validate_candidate({**generated, "review_conclusion": "rejected: invented spelling"},
                           negative, registry(), inventory())
    for change in ({"display_name": "Другое имя"}, {"owner": {"kind": "player", "id": 18}},
                   {"lang": "ua"}, {"generation_rule_version": "other-rule"},
                   {"reading": "other reading"}, {"research_sha256": "0" * 64},
                   {"reviewer_id": "someone-else"}, {"decision": "reject_generated"}):
        bad = deepcopy(generated)
        bad["generated_review"].update(change)
        with pytest.raises(CandidateError, match="generated review"):
            validate_candidate(bad, negative, registry(), inventory())
    with pytest.raises(CandidateError, match="generated review"):
        validate_candidate({key: value for key, value in generated.items() if key != "generated_review"},
                           negative, registry(), inventory())
    with pytest.raises(CandidateError):
        validate_candidate(candidate(decision_kind="generated", generation_rule_version="ja-ru-v1"),
                           research(), registry(), inventory())
    missing_reading = deepcopy(negative)
    missing_reading.pop("reading_basis_url")
    with pytest.raises(CandidateError):
        validate_candidate({**generated, "research_sha256": canonical_sha256(missing_reading)},
                           missing_reading, registry(), inventory())
    with pytest.raises(CandidateError, match="script"):
        validate_candidate({**generated, "display_name": "Go Seigen",
                            "generated_review": {**generated["generated_review"], "display_name": "Go Seigen"}},
                           negative, registry(), inventory())


def test_finite_negative_closure_only_opens_generated_candidate_for_its_owner():
    sources = registry()
    sources["language_scopes"]["ru"]["complete_for_negative_claims"] = False
    negative = research(registry_sha256=registry_sha256(sources), source_lang="ja",
                        scope_status="not_found_in_scope", candidate_name="", source_checks=[check(
                            status="not_found", candidate_name="", identity_basis="",
                            body_excerpt="Search completed without a Russian name", check_id="go-search",
                            method="site_search", response_sha256="a" * 64, completeness="complete",
                            searched_forms=["Го Сэйгэн"], entity_field_scope=None, scan_id="go-profiles",
                            page_index=1, page_count=1, next_page_url="", pagination_exhausted=True,
                            pagination_basis="No next-page link",
                            search_scope="Indexed profiles", scope_complete=True,
                            negative_outcome="no_target_string")])
    negative["negative_closure"] = {
        "version": 1, "owner": negative["owner"], "lang": "ru", "source_lang": "ja",
        "scope_id": "player-17-ru", "scope_version": "1", "registry_sha256": negative["registry_sha256"],
        "required_check_ids": ["go-search"], "scope_boundary": "Indexed profiles only",
        "required_checks": [{"check_id": "go-search", "source_id": "go", "method": "site_search",
                             "query": "Go Seigen", "url": "https://example.org/go",
                             "searched_forms": ["Го Сэйгэн"], "entity_field_scope": None,
                             "scan_id": "go-profiles", "page_index": 1, "page_count": 1,
                             "next_page_url": "", "pagination_exhausted": True,
                             "pagination_basis": "No next-page link"}], "known_leads": [],
        "retained_limitations": ["Printed sources"], "reviewer_id": "scope-reviewer",
        "reviewer_model": "gpt-6-astra", "reviewed_at": "2026-10-02T11:00:00Z",
        "conclusion": "approved_not_found_in_scope", "reason": "No admissible Russian name in this scope",
    }
    negative["negative_closure"]["scope_template_sha256"] = negative_closure_template_sha256(negative)
    negative["negative_closure"]["scope_sha256"] = negative_closure_scope_sha256(negative)
    negative["negative_closure"]["evidence_sha256"] = negative_closure_evidence_sha256(negative)
    generated = approved_generated(candidate(decision_kind="generated", generation_rule_version="ja-ru-v1",
                                             research_sha256=canonical_sha256(negative),
                                             reviewed_at="2026-10-02T11:01:00Z"), negative)
    assert validate_candidate(generated, negative, sources, inventory())["decision_kind"] == "generated"
    with pytest.raises(CandidateError, match="negative closure"):
        validate_candidate({**generated, "reviewed_at": "2026-10-02T10:59:00Z",
                            "generated_review": {**generated["generated_review"],
                                                 "reviewed_at": "2026-10-02T10:59:00Z"}},
                           negative, sources, inventory())
    with pytest.raises(CandidateError, match="negative closure"):
        validate_candidate({**generated, "reviewed_at": "2026-10-02T11:00:00Z",
                            "generated_review": {**generated["generated_review"],
                                                 "reviewed_at": "2026-10-02T11:00:00Z"}},
                           negative, sources, inventory())
    changed = deepcopy(negative)
    changed["owner"] = {"kind": "player", "id": 18}
    changed["source_checks"][0]["owner"] = changed["owner"]
    with pytest.raises(CandidateError):
        validate_candidate({**generated, "research_sha256": canonical_sha256(changed)},
                           changed, sources, inventory())
    unsigned = deepcopy(negative)
    del unsigned["negative_closure"]
    with pytest.raises(CandidateError):
        validate_candidate({**generated, "research_sha256": canonical_sha256(unsigned)},
                           unsigned, sources, inventory())
    event_research = deepcopy(negative)
    event_research["owner"] = {"kind": "event", "id": 3}
    event_research["source_checks"][0]["owner"] = event_research["owner"]
    event_research["negative_closure"]["owner"] = event_research["owner"]
    event_research["original_name"] = "大手合"
    event_research["reading"] = ""
    event_research["reading_basis_url"] = ""
    event_research["negative_closure"]["scope_template_sha256"] = negative_closure_template_sha256(event_research)
    event_research["negative_closure"]["scope_sha256"] = negative_closure_scope_sha256(event_research)
    event_research["negative_closure"]["evidence_sha256"] = negative_closure_evidence_sha256(event_research)
    event_candidate = {**generated, "owner": event_research["owner"],
                       "research_sha256": canonical_sha256(event_research)}
    with pytest.raises(CandidateError, match="reading"):
        validate_candidate(event_candidate, event_research, sources, inventory())


def secondary_generated(lang="ru"):
    sources = registry()
    target = sources["language_tags"][lang]
    sources["sources"][0]["language"] = target
    sources["language_scopes"][lang] = {"required_source_ids": ["go", "wd"],
                                         "complete_for_negative_claims": False}
    negative = research(lang=lang, registry_sha256=registry_sha256(sources), source_lang="ja",
                        scope_status="not_found_in_scope", candidate_name="", source_checks=[])
    common = dict(status="not_found", candidate_name="", identity_basis="", observed_lang=target,
                  body_excerpt="Completed target-language search: no matching name", completeness="complete",
                  searched_forms=["Go Seigen", "呉清源"], response_sha256="b" * 64,
                  page_index=1, page_count=1, search_scope="Listed exact-name checks",
                  scope_complete=True, negative_outcome="no_target_string")
    negative["source_checks"] = [
        check(**common, check_id="professional", method="site_search", entity_field_scope=None,
              scan_id="go-search", next_page_url="https://example.org/search?page=2",
              continuation_href="/search?page=2", continuation_excerpt='<a href="/search?page=2">Next</a>',
              pagination_exhausted=False, pagination_basis="Stop after page 1; page 2 remains unsearched"),
        check(**common, check_id="wikidata", source_id="wd", method="entity_api", scan_id="q1-fields",
              url=f"https://www.wikidata.org/w/api.php?action=wbgetentities&ids=Q1&languages={target}&props=labels%7Caliases%7Csitelinks&format=json",
              entity_field_scope={"entity_id": "Q1", "requested_lang": target,
                                  "fields": ["labels", "aliases", "sitelinks"], "sitelink_site": target + "wiki"},
              next_page_url="", pagination_exhausted=True, pagination_basis="Single exact entity response"),
    ]
    negative["source_checks"][0]["body_excerpt"] += " " + negative["source_checks"][0]["continuation_excerpt"]
    negative["source_checks"][1]["body_excerpt"] = json.dumps({"entities": {"Q1": {"id": "Q1"}}})
    negative["source_checks"][1]["entity_identity_evidence"] = {
        "api_url": "https://www.wikidata.org/w/api.php?action=wbgetentities&ids=Q1&languages=ja&props=labels&format=json",
        "fetched_at": "2026-10-02T10:05:00Z", "http_status": 200, "response_sha256": "c" * 64,
        "body_excerpt": json.dumps({"entities": {"Q1": {"id": "Q1", "labels": {
            "ja": {"language": "ja", "value": negative["original_name"]}}}}}, ensure_ascii=False),
        "identity_basis": "Original Japanese name and career dates identify this player",
    }
    fields = ("check_id", "source_id", "method", "query", "url", "searched_forms", "entity_field_scope",
              "scan_id", "page_index", "page_count", "next_page_url", "pagination_exhausted", "pagination_basis")
    negative["negative_closure"] = {
        "version": 2, "search_policy": "secondary_reasonable_v1", "bounded_scan_ids": ["go-search"],
        "unsearched_source_ids": [],
        "owner": negative["owner"], "lang": lang, "source_lang": "ja", "scope_id": "reasonable-player-17",
        "scope_version": "1", "registry_sha256": negative["registry_sha256"],
        "scope_boundary": "Listed exact entity and first indexed professional page only",
        "retained_limitations": ["go-search: https://example.org/search?page=2 onward remains unsearched", "Print publications"],
        "required_check_ids": [item["check_id"] for item in negative["source_checks"]],
        "required_checks": [{field: item[field] for field in fields} for item in negative["source_checks"]],
        "known_leads": [], "reviewer_id": "scope-reviewer", "reviewer_model": "gpt-6-astra",
        "reviewed_at": "2026-10-02T11:00:00Z", "conclusion": "approved_not_found_in_scope",
        "reason": "No admissible name found within this reasonable search scope",
    }
    closure = negative["negative_closure"]
    closure["scope_template_sha256"] = negative_closure_template_sha256(negative)
    closure["scope_sha256"] = negative_closure_scope_sha256(negative)
    closure["evidence_sha256"] = negative_closure_evidence_sha256(negative)
    display = {"ru": "Го Сэйгэн", "ua": "Ґо Сейґен"}.get(lang, "Go Seigen")
    row = approved_generated(candidate(lang=lang, display_name=display, decision_kind="generated",
                                       generation_rule_version=f"ja-{lang}-v1",
                                       research_sha256=canonical_sha256(negative),
                                       reviewed_at="2026-10-02T11:01:00Z"), negative)
    return row, negative, sources


@pytest.mark.parametrize("lang", ["de", "es", "fr", "ru", "tr", "ua"])
def test_secondary_reasonable_closure_opens_only_independently_reviewed_generated_candidate(lang):
    row, negative, sources = secondary_generated(lang)
    assert validate_candidate(row, negative, sources, inventory())["decision_kind"] == "generated"
    report = validate_bundle(bundle(members=[member(lang=lang)], candidates=[row],
                                    registry_sha256=registry_sha256(sources)), sources, inventory(), [negative])
    assert report["ready"] and not report["write_ready"]  # Existing preimage gate still applies.
    for mutation in ("unsigned", "self_review", "early_review", "missing_reading", "rule", "stale_hash"):
        bad_row, bad_evidence = deepcopy(row), deepcopy(negative)
        if mutation == "unsigned":
            bad_row.pop("generated_review")
        elif mutation == "self_review":
            bad_row["reviewer_id"] = bad_row["producer_id"]
        elif mutation == "early_review":
            bad_row["reviewed_at"] = bad_row["generated_review"]["reviewed_at"] = "2026-10-02T11:00:00Z"
        elif mutation == "missing_reading":
            bad_evidence["reading"] = ""
            bad_evidence["reading_basis_url"] = ""
            bad_evidence["negative_closure"]["evidence_sha256"] = negative_closure_evidence_sha256(bad_evidence)
            bad_row["research_sha256"] = canonical_sha256(bad_evidence)
        elif mutation == "rule":
            bad_row["generation_rule_version"] = "different-rule"
        else:
            bad_evidence["negative_closure"]["bounded_scan_ids"] = []
        with pytest.raises(CandidateError):
            validate_candidate(bad_row, bad_evidence, sources, inventory())


def test_pending_is_reported_but_never_upgraded_to_approved():
    pending = candidate(review_status="pending", reviewer_id="", reviewer_model="",
                        reviewed_at="", review_conclusion="")
    report = validate_bundle(bundle(candidates=[pending]), registry(), inventory(), [research()])
    assert report["pending"] == 1 and report["approved"] == 0 and not report["ready"]


def test_unselected_contradictory_research_for_same_owner_language_blocks_bundle():
    negative = research(scope_status="not_found_in_scope", candidate_name="", source_checks=[check(
        status="not_found", candidate_name="", identity_basis="", body_excerpt="Completed Russian search, no name",
        search_scope="All indexed profiles", scope_complete=True, negative_outcome="no_target_string")])
    report = validate_bundle(bundle(), registry(), inventory(), [research(), negative])
    assert not report["ready"]
    assert any("multiple research records" in error for error in report["errors"])


def test_finite_inventory_member_set_detects_missing_extra_duplicate_and_changed_snapshot():
    assert validate_bundle(bundle(), registry(), inventory(), [research()])["ready"]
    for bad in (
        bundle(candidates=[]),
        bundle(candidates=[candidate(), candidate()]),
        bundle(members=[member({"kind": "player", "id": 999})], member_set_sha256=canonical_sha256([member({"kind": "player", "id": 999})])),
    ):
        report = validate_bundle(bad, registry(), inventory(), [research()])
        assert not report["ready"]
    with pytest.raises(CandidateError, match="inventory hash"):
        validate_bundle(bundle(inventory_sha256="b" * 64), registry(), inventory(), [research()])
    with pytest.raises(CandidateError, match="member set hash"):
        validate_bundle(bundle(member_set_sha256="b" * 64), registry(), inventory(), [research()])


def test_raw_owner_requires_exact_snapshot_spelling_and_non_event_cannot_be_hidden_as_generic():
    raw = {"kind": "raw_event", "id": 9}
    hidden = candidate(owner=raw, lang="ru", display_name="", decision_kind="hidden",
                       research_sha256="", generation_rule_version="classification-v1")
    approved = validate_candidate({**hidden, "raw_value": "GNUGo3.8"}, None, registry(), inventory())
    assert approved["decision_kind"] == "hidden"
    for raw_value in ("JapanPromotionTournament,1934,Fall", "missing"):
        with pytest.raises(CandidateError):
            validate_candidate({**hidden, "raw_value": raw_value}, None, registry(), inventory())
    with pytest.raises(CandidateError):
        validate_candidate({**hidden, "raw_value": "GNUGo3.8", "decision_kind": "generic",
                            "display_name": "турнир"}, None, registry(), inventory())


def test_unknown_player_uses_localized_placeholder_instead_of_disappearing():
    placeholder = candidate(owner={"kind": "raw_player", "id": 21}, raw_value="Unknown", lang="ru",
                            display_name="Неизвестный игрок", decision_kind="placeholder",
                            research_sha256="", generation_rule_version="classification-v1")
    assert validate_candidate(placeholder, None, registry(), inventory())["display_name"] == "Неизвестный игрок"
    with pytest.raises(CandidateError, match="template"):
        validate_candidate({**placeholder, "template_review": {}}, None, registry(), inventory())
    with pytest.raises(CandidateError, match="template"):
        validate_candidate({**placeholder, "display_name": "Go Seigen"}, None, registry(), inventory())
    with pytest.raises(CandidateError):
        validate_candidate({**placeholder, "display_name": "", "decision_kind": "hidden"},
                           None, registry(), inventory())
    with pytest.raises(CandidateError):
        validate_candidate({**placeholder, "raw_value": "吴清源九段"}, None, registry(), inventory())


def test_distinct_id_same_language_name_is_flagged_for_identity_review():
    inv = inventory()
    other = candidate(owner={"kind": "player", "id": 18})
    other_research = research(owner={"kind": "player", "id": 18},
                              source_checks=[check(owner={"kind": "player", "id": 18})])
    other["research_sha256"] = canonical_sha256(other_research)
    members = [member(), member({"kind": "player", "id": 18})]
    report = validate_bundle(bundle(members=members, member_set_sha256=canonical_sha256(members),
                                    candidates=[candidate(), other]), registry(), inv,
                             [research(), other_research])
    assert not report["ready"]
    assert any("collision" in error for error in report["errors"])
    both_reviewed = [{**row, "collision_decision": "distinct_people_confirmed",
                      "collision_basis": "Official player IDs and dates distinguish the two people"}
                     for row in (candidate(), other)]
    report = validate_bundle(bundle(members=members, member_set_sha256=canonical_sha256(members),
                                    candidates=both_reviewed), registry(), inv, [research(), other_research])
    assert report["ready"]


def test_collision_uses_normalized_width_case_and_space():
    inv = inventory()
    other = candidate(owner={"kind": "player", "id": 18}, display_name="ＧО  СЭЙГЭН")
    other_research = research(owner={"kind": "player", "id": 18}, candidate_name="ＧО  СЭЙГЭН",
                              source_checks=[check(owner={"kind": "player", "id": 18},
                                                   candidate_name="ＧО  СЭЙГЭН",
                                                   body_excerpt="Player ＧО  СЭЙГЭН")])
    other["research_sha256"] = canonical_sha256(other_research)
    first = candidate(display_name="GО СЭЙГЭН")
    first_research = research(candidate_name="GО СЭЙГЭН", source_checks=[check(
        candidate_name="GО СЭЙГЭН", body_excerpt="Player GО СЭЙГЭН")])
    first["research_sha256"] = canonical_sha256(first_research)
    members = [member(), member({"kind": "player", "id": 18})]
    report = validate_bundle(bundle(members=members, member_set_sha256=canonical_sha256(members),
                                    candidates=[first, other]), registry(), inv,
                             [first_research, other_research])
    assert not report["ready"] and any("collision" in error for error in report["errors"])


def test_same_raw_id_cannot_claim_different_spellings_across_languages():
    inv = inventory()
    inv["album_associations"].append([3, "Black", "White", "Engine3.8", None, None, None])
    members = [member({"kind": "raw_event", "id": 7}, "ru", "GNUGo3.8"),
               member({"kind": "raw_event", "id": 7}, "en", "Engine3.8")]
    report = validate_bundle(bundle(members=members, member_set_sha256=canonical_sha256(members),
                                    candidates=[]), registry(), inv, [])
    assert not report["ready"]
    assert any("different raw spellings" in error for error in report["errors"])


def test_unreviewed_generic_event_and_corrupt_player_error_are_explicit():
    generic = candidate(owner={"kind": "raw_event", "id": 8}, lang="ru", raw_value="段位赛",
                        display_name="Турнир разрядов", decision_kind="generic", research_sha256="",
                        generation_rule_version="classification-v1")
    inv = inventory()
    inv["album_associations"].append([3, "崔珪昞]BR[九段", "Unknown", "段位赛", None, None, None])
    assert validate_candidate(generic, None, registry(), inv)["decision_kind"] == "generic"
    spaced = {**generic, "raw_value": " 段位赛 "}
    inv["album_associations"].append([4, "Black", "White", " 段位赛 ", None, None, None])
    assert validate_candidate(spaced, None, registry(), inv)["display_name"] == "Турнир разрядов"
    with pytest.raises(CandidateError, match="template"):
        validate_candidate({**spaced, "display_name": "Личный турнир"}, None, registry(), inv)
    error = candidate(owner={"kind": "raw_player", "id": 8}, lang="ru", raw_value="崔珪昞]BR[九段",
                      display_name="Ошибка в имени игрока", decision_kind="error", research_sha256="",
                      generation_rule_version="classification-v1")
    assert validate_candidate(error, None, registry(), inv)["decision_kind"] == "error"


def test_event_components_are_rendered_separately_from_approved_core_name():
    assert render_event_components("Oteai", {"year": "1934", "season": "Fall", "edition": "4届", "round": "3轮"}, "en") == "Oteai · 1934 · Fall · 4th · Round 3"
    assert render_event_components("大手合", {"year": "1934", "season": "Fall"}, "cn") == "大手合 · 1934年 · 秋"
    with pytest.raises(CandidateError):
        render_event_components("Oteai", {"year": "1934", "season": "Maybe"}, "en")
    for lang in LANGS:
        rendered = render_event_components("Oteai", {"year": "1934", "season": "Spring",
                                                     "edition": "4届", "round": "3轮", "game": "2局"}, lang)
        assert rendered.startswith("Oteai · ") and len(rendered.split(" · ")) == 6
        if lang not in {"cn", "tw"}:
            assert "届" not in rendered and "期" not in rendered
    assert "第4届" in render_event_components("大手合", {"edition": "四届"}, "cn")
    assert "4th" in render_event_components("Oteai", {"edition": "四届"}, "en")
    for lang in LANGS:
        assert render_event_components("Honinbo", {"edition": "28th"}, lang)
    assert render_event_components("Honinbo", {"edition": "28th"}, "en") == "Honinbo · 28th"
    for malformed in ("11st", "0th", "28rd"):
        with pytest.raises(CandidateError, match="invalid event edition"):
            render_event_components("Honinbo", {"edition": malformed}, "en")


def test_cli_report_is_read_only_and_reports_missing_approval(tmp_path, capsys):
    paths = {key: tmp_path / f"{key}.json" for key in ("registry", "inventory", "bundle", "evidence")}
    for key, value in (("registry", registry()), ("inventory", inventory()), ("bundle", bundle())):
        paths[key].write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    paths["evidence"].write_text(json.dumps(research(), ensure_ascii=False) + "\n", encoding="utf-8")
    args = ["validate", "--registry", str(paths["registry"]), "--inventory", str(paths["inventory"]),
            "--bundle", str(paths["bundle"]), "--evidence", str(paths["evidence"])]
    assert main(args) == 0
    assert json.loads(capsys.readouterr().out)["ready"]
    pending = candidate(review_status="pending", reviewer_id="", reviewer_model="", reviewed_at="", review_conclusion="")
    paths["bundle"].write_text(json.dumps(bundle(candidates=[pending]), ensure_ascii=False), encoding="utf-8")
    assert main(args) == 1
    assert json.loads(capsys.readouterr().out)["pending"] == 1


def test_v2_raw_value_symbolic_owner_is_pinned_to_all_inventory_occurrences():
    owner = {"kind": "raw_event", "ref": "program-label"}
    declaration = {"owner": owner, "create": {"raw_value": "GNUGo3.8", "category": "program_source_label"},
                   "occurrence_album_ids": [1], "occurrence_sha256": canonical_sha256([1]),
                   "category_review": {"status": "approved", "producer_id": "researcher-1",
                                       "producer_model": "gpt-6-luna", "produced_at": "2026-10-02T10:00:00Z",
                                       "reviewer_id": "reviewer-2", "reviewer_model": "gpt-6-luna",
                                       "reviewed_at": "2026-10-02T10:30:00Z",
                                       "category_basis": "Parser and SGF context identify a program label"}}
    one_member = member(owner, "ru", "GNUGo3.8")
    row = candidate(owner=owner, lang="ru", raw_value="GNUGo3.8", display_name="",
                    decision_kind="hidden", research_sha256="", generation_rule_version="classification-v1")
    proposed = bundle(members=[one_member], member_set_sha256=canonical_sha256([one_member]),
                      candidates=[row], bundle_format=2, catalog_sha256="b" * 64,
                      owners=[declaration], owner_set_sha256=canonical_sha256([declaration]),
                      album_links=[], link_set_sha256=canonical_sha256([]))
    assert validate_bundle(proposed, registry(), inventory(), [])["ready"]
    bad = deepcopy(proposed)
    bad["owners"][0]["occurrence_album_ids"] = []
    bad["owners"][0]["occurrence_sha256"] = canonical_sha256([])
    bad["owner_set_sha256"] = canonical_sha256(bad["owners"])
    assert not validate_bundle(bad, registry(), inventory(), [])["ready"]
    purported = research(owner=owner, lang="ru", candidate_name="Турнир",
                         original_name="GNUGo3.8", original_language="en",
                         source_checks=[check(owner=owner, candidate_name="Турнир",
                                              body_excerpt="A page calls this Турнир")])
    inconsistent = deepcopy(proposed)
    inconsistent["candidates"][0].update(display_name="Турнир", decision_kind="conventional",
                                          research_sha256=canonical_sha256(purported),
                                          generation_rule_version="none")
    assert not validate_bundle(inconsistent, registry(), inventory(), [purported])["ready"]
    assert any("category" in message for message in
               validate_bundle(inconsistent, registry(), inventory(), [purported])["errors"])


def test_v2_occurrence_index_counts_one_game_but_both_slots_for_duplicate_raw_player():
    associations = {
        11: {"player_black": "Same", "player_white": "Same", "event": "Cup"},
        12: {"player_black": "Other", "player_white": "Same", "event": "Cup"},
    }
    player_games, event_games, player_slots, event_slots = _occurrence_indexes(associations)
    assert player_games["Same"] == [11, 12]
    assert player_slots["Same"] == [[11, "black"], [11, "white"], [12, "white"]]
    assert event_games["Cup"] == [11, 12]
    assert event_slots["Cup"] == [[11, "event"], [12, "event"]]


def test_selected_event_is_a_v3_raw_scope_but_legacy_bundle_cannot_claim_it():
    from katrain.web.kifu.name_inventory import SELECTION_COLUMNS, _hash_row

    inv = inventory()
    rows = [[1, "Selected Cup", "a" * 64, "reviewer", "2026-10-02T10:00:00", 3, "b" * 64]]
    digest = hashlib.sha256()
    _hash_row(digest, b"E", (1, SELECTION_COLUMNS))
    for row in rows:
        _hash_row(digest, b"E", row)
    inv.update(inventory_format=3, event_selection={
        "selection_format": 1, "columns": list(SELECTION_COLUMNS), "rows": rows, "sha256": digest.hexdigest(),
    })
    raw_owner = {"kind": "raw_event", "id": 9}
    selected = candidate(owner=raw_owner, raw_value="Selected Cup", lang="ru", display_name="Кубок",
                         research_sha256="")
    source = check(owner=raw_owner, candidate_name="Кубок", body_excerpt="Кубок: Selected Cup")
    evidence = research(owner=raw_owner, candidate_name="Кубок", source_checks=[source])
    selected["research_sha256"] = canonical_sha256(evidence)
    assert validate_candidate(selected, evidence, registry(), inv)["display_name"] == "Кубок"
    for bad in ([], [[1, "Other Cup", *rows[0][2:]]]):
        changed = deepcopy(inv)
        changed["event_selection"]["rows"] = bad
        digest = hashlib.sha256()
        _hash_row(digest, b"E", (1, SELECTION_COLUMNS))
        for row in bad:
            _hash_row(digest, b"E", row)
        changed["event_selection"]["sha256"] = digest.hexdigest()
        with pytest.raises(CandidateError):
            validate_candidate(selected, evidence, registry(), changed)
    old = bundle(members=[member(raw_owner, raw_value="Selected Cup")], candidates=[selected])
    old["member_set_sha256"] = canonical_sha256(old["members"])
    with pytest.raises(CandidateError, match="format"):
        validate_bundle(old, registry(), inv, [evidence])


def _selected_v4_case():
    from katrain.web.kifu.name_inventory import SELECTION_COLUMNS, _hash_row

    columns = list(inventory()["association_columns"]) + [
        "source", "source_path", "date_played", "round_name", "board_size", "black_rank", "white_rank",
    ]
    first = [1, "Black", "White", "GNUGo3.8", None, None, None,
             "collection", "archive/game.sgf", "1934-10-01", "final", 19, "9d", "8d"]
    second = [2, "Black", "White", "Selected Cup", None, None, 3,
              "collection", "archive/other.sgf", "1934-10-02", "final", 19, "9d", "8d"]
    source_image = {
        "album_id": 1, "event_id": None, "batch_id": 7, "selected_raw": "Selected Cup",
        "sgf_sha256": "c" * 64, "property_name": "GN", "property_index": 1,
        "status": "approved", "rule_version": "19x19-gnugo-second-gn-v1",
        "reviewer_id": "selection-reviewer", "reviewed_at": "2026-10-02T09:00:00+00:00",
        "created_at": "2026-10-02T09:00:00+00:00",
    }
    selection_columns = [*SELECTION_COLUMNS, "event_id", "source_after_image", "source_after_sha256",
                         "name_batch_id", "name_proof_sha256"]
    selection_row = [1, "Selected Cup", "c" * 64, "selection-reviewer",
                     "2026-10-02T09:00:00+00:00", 7, "d" * 64,
                     None, source_image, canonical_sha256(source_image), None, None]
    digest = hashlib.sha256()
    _hash_row(digest, b"E", (2, tuple(selection_columns)))
    _hash_row(digest, b"E", selection_row)
    inv = inventory()
    inv.update(inventory_format=4, base_sha256="e" * 64,
               association_columns=columns, album_associations=[first, second],
               event_selection={"selection_format": 2, "columns": selection_columns,
                                "rows": [selection_row], "sha256": digest.hexdigest()})
    target = {"kind": "event", "id": 3}
    declaration = {"owner": target, "preimage": {"canonical_name": "Selected Cup"},
                   "identity_context": {"start_date": "1934-01-01", "end_date": "1934-12-31",
                                        "region": "Japan"}}
    album = dict(zip(columns, first))
    expected = {key: album[key] for key in (
        "player_black", "player_white", "event", "date_played", "round_name", "black_rank", "white_rank")}
    expected["old_id"] = None
    link = {
        "album_id": 1, "slot": "selected_event", "association_sha256": canonical_sha256(album),
        "production_sgf_sha256": "c" * 64, "expected": expected, "target": target,
        "raw_scope_sha256": canonical_sha256([[1, "selected_event"], [2, "event"]]),
        "selection_batch_id": 7, "selection_bundle_sha256": "d" * 64,
        "selection_before_image": source_image, "selection_before_sha256": canonical_sha256(source_image),
        "identity_review": {
            "status": "approved", "producer_id": "identity-researcher", "producer_model": "gpt-6-luna",
            "produced_at": "2026-10-02T09:30:00Z", "reviewer_id": "identity-reviewer",
            "reviewer_model": "gpt-6-astra", "reviewed_at": "2026-10-02T11:00:00Z",
            "scope_frozen_at": "2026-10-02T10:00:00Z", "review_conclusion": "approved exact selection",
            "identity_basis": "Source identifies this tournament and edition",
            "event_period": {"start_date": "1934-01-01", "end_date": "1934-12-31"},
            "event_region": "Japan",
            "event_period_basis": "Contemporary record dates this tournament to 1934",
            "event_region_basis": "Contemporary record places it in Japan",
            "source_checks": [{"url": "https://example.org/event", "body_sha256": "f" * 64,
                               "fetched_at": "2026-10-02T09:20:00Z",
                               "body_excerpt": "1934 Selected Cup in Japan",
                               "identity_match": "Same event and edition"}],
        },
    }
    event_member = member(target)
    proposed = bundle(members=[event_member], candidates=[], bundle_format=4,
                      inventory_format=4, inventory_sha256=inv["sha256"],
                      catalog_sha256="b" * 64, owners=[declaration],
                      member_set_sha256=canonical_sha256([event_member]),
                      owner_set_sha256=canonical_sha256([declaration]), album_links=[link],
                      link_set_sha256=canonical_sha256([link]))
    link["identity_review"]["scope_sha256"] = identity_scope_sha256(proposed, [link], declaration)
    proposed["link_set_sha256"] = canonical_sha256([link])
    return inv, proposed


def test_v4_selected_event_scope_accepts_exact_source_proof_and_requires_all_event_names():
    inv, proposed = _selected_v4_case()
    report = validate_bundle(proposed, registry(), inv, [])
    assert not report["ready"]
    assert report["errors"] == ["missing candidate: event:3:ru", "linked identity lacks all eleven approved language names: event:3"]


def test_v4_selected_event_scope_signature_changes_with_source_batch_and_after_image():
    inv, proposed = _selected_v4_case()
    link = proposed["album_links"][0]
    original = link["identity_review"]["scope_sha256"]
    for field, value in (("selection_bundle_sha256", "a" * 64),
                         ("selection_before_sha256", "a" * 64),
                         ("selection_before_image", {**link["selection_before_image"], "selected_raw": "Other"}),
                         ("raw_scope_sha256", "a" * 64)):
        changed = deepcopy(link)
        changed[field] = value
        assert identity_scope_sha256(proposed, [changed], proposed["owners"][0]) != original


def test_v4_selected_event_rejects_wrong_target_context_and_ordinary_link():
    inv, proposed = _selected_v4_case()
    for change in ("event_period", "event_region"):
        bad = deepcopy(proposed)
        bad["album_links"][0]["identity_review"][change] = "wrong"
        bad["link_set_sha256"] = canonical_sha256(bad["album_links"])
        report = validate_bundle(bad, registry(), inv, [])
        assert any(change in error for error in report["errors"])
    bad = deepcopy(proposed)
    bad["album_links"][0]["slot"] = "event"
    bad["link_set_sha256"] = canonical_sha256(bad["album_links"])
    assert any("selected_event" in error for error in validate_bundle(bad, registry(), inv, [])["errors"])
    old = deepcopy(proposed)
    old["bundle_format"] = old["inventory_format"] = inv["inventory_format"] = 3
    with pytest.raises(CandidateError, match="supplement"):
        validate_bundle(old, registry(), inv, [])


def test_v3_inventory_cannot_authorize_selected_event_slot():
    from katrain.web.kifu.name_inventory import SELECTION_COLUMNS, _hash_row

    inv, proposed = _selected_v4_case()
    row = inv["event_selection"]["rows"][0][:len(SELECTION_COLUMNS)]
    digest = hashlib.sha256()
    _hash_row(digest, b"E", (1, SELECTION_COLUMNS))
    _hash_row(digest, b"E", row)
    inv["inventory_format"] = 3
    inv["event_selection"] = {"selection_format": 1, "columns": list(SELECTION_COLUMNS),
                              "rows": [row], "sha256": digest.hexdigest()}
    proposed["bundle_format"] = proposed["inventory_format"] = 3
    report = validate_bundle(proposed, registry(), inv, [])
    assert any("album_link[0]" in error for error in report["errors"])


def test_v4_selected_event_rejects_borrowed_or_mutated_source_proof():
    inv, proposed = _selected_v4_case()
    for field, value in (("selection_bundle_sha256", "a" * 64),
                         ("selection_batch_id", 8),
                         ("selection_before_sha256", "a" * 64),
                         ("selection_before_image", {**proposed["album_links"][0]["selection_before_image"],
                                                     "selected_raw": "Other Cup"}),
                         ("production_sgf_sha256", "a" * 64),
                         ("raw_scope_sha256", "a" * 64)):
        bad = deepcopy(proposed)
        bad["album_links"][0][field] = value
        bad["link_set_sha256"] = canonical_sha256(bad["album_links"])
        report = validate_bundle(bad, registry(), inv, [])
        assert any("album_link[0]" in error for error in report["errors"]), field


def test_v4_selected_event_requires_original_base_and_exact_gn_rule():
    from katrain.web.kifu.name_inventory import SELECTION_COLUMNS_V4, _hash_row

    inv, proposed = _selected_v4_case()
    missing_base = deepcopy(inv)
    del missing_base["base_sha256"]
    with pytest.raises(CandidateError, match="base"):
        validate_bundle(proposed, registry(), missing_base, [])
    bad_rule = deepcopy(inv)
    row = bad_rule["event_selection"]["rows"][0]
    row[8]["rule_version"] = "other-rule"
    row[9] = canonical_sha256(row[8])
    digest = hashlib.sha256()
    _hash_row(digest, b"E", (2, SELECTION_COLUMNS_V4))
    _hash_row(digest, b"E", row)
    bad_rule["event_selection"]["sha256"] = digest.hexdigest()
    with pytest.raises(CandidateError, match="after-image"):
        validate_bundle(proposed, registry(), bad_rule, [])


def test_v4_inventory_linked_selection_requires_name_batch_proof():
    from katrain.web.kifu.name_inventory import SELECTION_COLUMNS_V4, _hash_row
    from katrain.web.kifu.name_candidates import _selection_rows

    inv, _ = _selected_v4_case()
    row = inv["event_selection"]["rows"][0]
    row[7] = 3
    digest = hashlib.sha256()
    _hash_row(digest, b"E", (2, SELECTION_COLUMNS_V4))
    _hash_row(digest, b"E", row)
    inv["event_selection"]["sha256"] = digest.hexdigest()
    with pytest.raises(CandidateError, match="name proof"):
        _selection_rows(inv)


def test_v4_selected_event_rejects_irrelevant_owner_and_non_event_member():
    inv, proposed = _selected_v4_case()
    unrelated = {"owner": {"kind": "event", "id": 19},
                 "preimage": {"canonical_name": "Other Cup"},
                 "identity_context": {"start_date": "1934-01-01", "end_date": "1934-12-31",
                                      "region": "Japan"}}
    bad = deepcopy(proposed)
    bad["owners"].append(unrelated)
    bad["owner_set_sha256"] = canonical_sha256(bad["owners"])
    assert any("irrelevant" in error for error in validate_bundle(bad, registry(), inv, [])["errors"])
    bad = deepcopy(proposed)
    bad["members"].append(member())
    bad["member_set_sha256"] = canonical_sha256(bad["members"])
    assert any("only event" in error for error in validate_bundle(bad, registry(), inv, [])["errors"])
    bad = deepcopy(proposed)
    new_raw = {"owner": {"kind": "raw_event", "ref": "selected-raw"},
               "create": {"raw_value": "Selected Cup", "category": "formal_event_candidate"},
               "occurrence_album_ids": [1, 2], "occurrence_sha256": canonical_sha256([1, 2])}
    bad["owners"].append(new_raw)
    bad["owner_set_sha256"] = canonical_sha256(bad["owners"])
    assert any("raw field" in error for error in validate_bundle(bad, registry(), inv, [])["errors"])


def test_v4_selected_event_rejects_invalid_or_out_of_range_period():
    inv, proposed = _selected_v4_case()
    for invalid_date, end_date in (("1934-02-30", "1934-12-31"), ("1934-01-01", "1934-09-30")):
        bad = deepcopy(proposed)
        bad["owners"][0]["identity_context"]["start_date"] = invalid_date
        bad["owners"][0]["identity_context"]["end_date"] = end_date
        bad["album_links"][0]["identity_review"]["event_period"] = {
            "start_date": invalid_date, "end_date": end_date}
        bad["album_links"][0]["identity_review"]["scope_sha256"] = identity_scope_sha256(
            bad, bad["album_links"], bad["owners"][0])
        bad["link_set_sha256"] = canonical_sha256(bad["album_links"])
        bad["owner_set_sha256"] = canonical_sha256(bad["owners"])
        report = validate_bundle(bad, registry(), inv, [])
        assert any("period" in error for error in report["errors"])


def test_v4_selected_event_requires_evidence_and_production_before_scope_freeze():
    inv, proposed = _selected_v4_case()
    for field, value in (("produced_at", "2026-10-02T10:01:00Z"),
                         ("produced_at", "2026-10-02T09:10:00Z"),
                         ("scope_frozen_at", "2026-10-02T09:15:00Z")):
        bad = deepcopy(proposed)
        bad["album_links"][0]["identity_review"][field] = value
        bad["link_set_sha256"] = canonical_sha256(bad["album_links"])
        assert any("chronology" in error for error in validate_bundle(bad, registry(), inv, [])["errors"])
    for fetched in (None, "2026-10-02T09:35:00Z", "2026-10-02T10:01:00Z", "2026-10-02T09:20:00"):
        bad = deepcopy(proposed)
        if fetched is None:
            del bad["album_links"][0]["identity_review"]["source_checks"][0]["fetched_at"]
        else:
            bad["album_links"][0]["identity_review"]["source_checks"][0]["fetched_at"] = fetched
        bad["link_set_sha256"] = canonical_sha256(bad["album_links"])
        assert any("chronology" in error for error in validate_bundle(bad, registry(), inv, [])["errors"])


def test_v4_selected_event_checks_year_and_multi_day_album_dates():
    inv, proposed = _selected_v4_case()
    date_index = inv["association_columns"].index("date_played")
    for played, allowed in (("1934", True), ("1973", False),
                            ("1934-09-04,05", True), ("1934-09-04,05,07", True),
                            ("1934-12-31,1935-01-01", False),
                            ("1934-09-04,99", False), ("1934-09", True),
                            ("1934-09-04,10-02", False),
                            ("circa 1934", False), (None, False)):
        changed_inventory = deepcopy(inv)
        changed_bundle = deepcopy(proposed)
        changed_inventory["album_associations"][0][date_index] = played
        album = dict(zip(changed_inventory["association_columns"], changed_inventory["album_associations"][0]))
        link = changed_bundle["album_links"][0]
        link["association_sha256"] = canonical_sha256(album)
        link["expected"]["date_played"] = played
        link["identity_review"]["scope_sha256"] = identity_scope_sha256(
            changed_bundle, [link], changed_bundle["owners"][0])
        changed_bundle["link_set_sha256"] = canonical_sha256([link])
        report = validate_bundle(changed_bundle, registry(), changed_inventory, [])
        assert any("album date" in error for error in report["errors"]) is not allowed, played
    narrowed_inventory = deepcopy(inv)
    narrowed_bundle = deepcopy(proposed)
    narrowed_inventory["album_associations"][0][date_index] = "1934"
    album = dict(zip(narrowed_inventory["association_columns"], narrowed_inventory["album_associations"][0]))
    link = narrowed_bundle["album_links"][0]
    link["association_sha256"] = canonical_sha256(album)
    link["expected"]["date_played"] = "1934"
    narrowed_bundle["owners"][0]["identity_context"]["start_date"] = "1934-09-01"
    narrowed_bundle["owners"][0]["identity_context"]["end_date"] = "1934-09-30"
    link["identity_review"]["event_period"] = {"start_date": "1934-09-01", "end_date": "1934-09-30"}
    link["identity_review"]["scope_sha256"] = identity_scope_sha256(
        narrowed_bundle, [link], narrowed_bundle["owners"][0])
    narrowed_bundle["owner_set_sha256"] = canonical_sha256(narrowed_bundle["owners"])
    narrowed_bundle["link_set_sha256"] = canonical_sha256([link])
    report = validate_bundle(narrowed_bundle, registry(), narrowed_inventory, [])
    assert any("period excludes album date" in error for error in report["errors"])
    narrowed_inventory["album_associations"][0][date_index] = "1934-09-04,1934-10-01,02"
    album = dict(zip(narrowed_inventory["association_columns"], narrowed_inventory["album_associations"][0]))
    link["association_sha256"] = canonical_sha256(album)
    link["expected"]["date_played"] = album["date_played"]
    narrowed_bundle["owners"][0]["identity_context"]["start_date"] = "1934-09-01"
    narrowed_bundle["owners"][0]["identity_context"]["end_date"] = "1934-10-01"
    link["identity_review"]["event_period"] = {"start_date": "1934-09-01", "end_date": "1934-10-01"}
    link["identity_review"]["scope_sha256"] = identity_scope_sha256(
        narrowed_bundle, [link], narrowed_bundle["owners"][0])
    narrowed_bundle["owner_set_sha256"] = canonical_sha256(narrowed_bundle["owners"])
    narrowed_bundle["link_set_sha256"] = canonical_sha256([link])
    report = validate_bundle(narrowed_bundle, registry(), narrowed_inventory, [])
    assert any("period excludes album date" in error for error in report["errors"])


def test_v4_selected_event_accepts_eleven_independently_reviewed_event_names():
    inv, proposed = _selected_v4_case()
    sources = [{"id": lang, "tier": "language_go", "home_url": "https://example.org/",
                "language": lang} for lang in LANGS]
    full_registry = registry()
    full_registry["sources"] = sources
    full_registry["language_scopes"] = {
        lang: {"required_source_ids": [lang], "complete_for_negative_claims": True} for lang in LANGS
    }
    proposed["registry_sha256"] = registry_sha256(full_registry)
    target = proposed["owners"][0]["owner"]
    members, candidates, evidence = [], [], []
    for lang in LANGS:
        display = f"Cup {lang}"
        language_tag = full_registry["language_tags"][lang]
        source_check = check(owner=target, source_id=lang, observed_lang=language_tag,
                             candidate_name=display, body_excerpt=f"Event profile for {display}",
                             identity_basis="Same 1934 event in Japan")
        record = research(owner=target, lang=lang, registry_sha256=proposed["registry_sha256"],
                          candidate_name=display, original_name="Selected Cup",
                          source_checks=[source_check])
        evidence.append(record)
        members.append(member(target, lang))
        candidates.append(candidate(owner=target, lang=lang, display_name=display,
                                    research_sha256=canonical_sha256(record)))
    proposed["members"] = members
    proposed["member_set_sha256"] = canonical_sha256(members)
    proposed["candidates"] = candidates
    report = validate_bundle(proposed, full_registry, inv, evidence)
    assert report["ready"], report["errors"]
    assert report["approved"] == 11
    new = deepcopy(proposed)
    new_evidence = deepcopy(evidence)
    new_owner = {"kind": "event", "ref": "selected-cup"}
    new["owners"][0]["owner"] = new_owner
    new["owners"][0]["create"] = new["owners"][0].pop("preimage")
    new["owner_set_sha256"] = canonical_sha256(new["owners"])
    new["album_links"][0]["target"] = new_owner
    for name_member, row, record in zip(new["members"], new["candidates"], new_evidence):
        name_member["owner"] = new_owner
        row["owner"] = new_owner
        record["owner"] = new_owner
        record["source_checks"][0]["owner"] = new_owner
        row["research_sha256"] = canonical_sha256(record)
    new["member_set_sha256"] = canonical_sha256(new["members"])
    new["album_links"][0]["identity_review"]["scope_sha256"] = identity_scope_sha256(
        new, new["album_links"], new["owners"][0])
    new["link_set_sha256"] = canonical_sha256(new["album_links"])
    report = validate_bundle(new, full_registry, inv, new_evidence)
    assert report["ready"], report["errors"]


def test_v2_new_person_cannot_link_with_only_one_language_name():
    new_owner = {"kind": "player", "ref": "historical-player"}
    declaration = {"owner": new_owner, "create": {"canonical_name": "呉清源"}}
    one_member = member(new_owner, "ru")
    one_research = research(owner=new_owner, source_checks=[check(owner=new_owner)])
    row = candidate(owner=new_owner, research_sha256=canonical_sha256(one_research))
    proposed = bundle(members=[one_member], member_set_sha256=canonical_sha256([one_member]),
                      candidates=[row], bundle_format=2, catalog_sha256="b" * 64,
                      owners=[declaration], owner_set_sha256=canonical_sha256([declaration]),
                      album_links=[], link_set_sha256=canonical_sha256([]))
    report = validate_bundle(proposed, registry(), inventory(), [one_research])
    assert not report["ready"]
    assert any("eleven" in error or "link" in error for error in report["errors"])
