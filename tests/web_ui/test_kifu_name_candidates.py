"""Approved display decisions require exact scope, evidence and independent review."""

from copy import deepcopy
import hashlib
import json
from urllib.parse import quote_plus

import pytest

from katrain.web.kifu.name_candidates import (
    CandidateError,
    _CLASSIFICATION_TEMPLATES,
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

V1_CLASSIFICATION_HASHES = {
    "cn": "4b864b74926267422fe6e79deb1d5e07d8335f26b988572b5997c419b850a0f2",
    "de": "9b83178cc2f5d276d60eeb0c29f36aa5a0725ca7147acc5fc07e7d5b7e616e67",
    "en": "d2fe9f66756b2dce50f40a4720094400086609e46eca25fe39121e772dd0a3d8",
    "es": "987c30b656d2b1eda6ae8443c10b75d69754269138b4ea8c51aac04169ac5d1b",
    "fr": "9db6505579a02b8b148b0fb582b750e8dc5fc1cb1e8aa17dab371e6f4e318768",
    "jp": "95ed2396c392776bb3d11396459b7b14db237317d04f81e6787922d0edc3ec93",
    "ko": "113d6243d3d057e796a7368992738ca497dc4da3244a6fc659197754b0a980eb",
    "ru": "208f36b8b066dcf27372527cfd59ac6f7d5fa80b09c7df58d9664495409d2bfa",
    "tr": "d1278e77e3e1a6d211b538a4b6fab65876bd6490e4c61207736f7d37aa15de3e",
    "tw": "b951e6c8a4394471ca3c6792b629c34fca75916b21aab5e4fca95b9b6b9dbf77",
    "ua": "f13576de8ac5dc01e2feacbdb11f9b8b51a2a68df48eca597ef2bae0d9fbc5aa",
}
V2_GENERIC_DISPLAYS = {
    "个人赛": dict(zip(LANGS, (
        "Individual tournament", "个人赛", "個人賽", "個人戦", "개인전", "Einzelturnier",
        "Torneo individual", "Tournoi individuel", "Индивидуальный турнир", "Bireysel turnuva",
        "Індивідуальний турнір",
    ))),
    "段位赛": dict(zip(LANGS, (
        "Dan-rank tournament", "段位赛", "段位賽", "段位戦", "단위(段位) 관련 대회", "Dan-Grad-Turnier",
        "Torneo de grados dan", "Tournoi de grades dan", "Турнир по данам", "Dan derecesi turnuvası",
        "Турнір за данами",
    ))),
}


def v2_classification_candidate(raw, lang, owner=None):
    row = candidate(owner=owner or {"kind": "raw_event", "id": 8}, lang=lang, raw_value=raw,
                    display_name=V2_GENERIC_DISPLAYS[raw][lang], decision_kind="generic",
                    research_sha256="", generation_rule_version="classification-v2")
    templates = {**_CLASSIFICATION_TEMPLATES[lang],
                 "rank_event": V2_GENERIC_DISPLAYS["段位赛"][lang],
                 "individual_event": V2_GENERIC_DISPLAYS["个人赛"][lang]}
    row["template_review"].update(version="classification-v2", sha256=canonical_sha256({
        "version": "classification-v2", "lang": lang, "templates": templates,
    }))
    return row


def v2_generic_bundle(raw="个人赛"):
    inv = inventory()
    inv["album_associations"].append([3, "Black", "White", raw, None, None, None])
    owner = {"kind": "raw_event", "id": 8}
    declaration = {"owner": owner, "preimage": {"id": 8, "raw_value": raw,
                   "category": "generic_event_description", "review_status": "approved"},
                   "occurrence_album_ids": [3], "occurrence_sha256": canonical_sha256([3])}
    members = [member(owner, lang, raw) for lang in LANGS]
    proposed = bundle(members=members, candidates=[v2_classification_candidate(raw, lang) for lang in LANGS],
                      bundle_format=2, catalog_sha256="b" * 64, owners=[declaration],
                      owner_set_sha256=canonical_sha256([declaration]), album_links=[],
                      link_set_sha256=canonical_sha256([]))
    return proposed, inv


def test_classification_v1_template_hashes_remain_frozen():
    assert {lang: classification_template_sha256(lang) for lang in LANGS} == V1_CLASSIFICATION_HASHES


@pytest.mark.parametrize("raw", V2_GENERIC_DISPLAYS)
@pytest.mark.parametrize("lang", LANGS)
def test_classification_v2_accepts_exact_reviewed_generic_displays(raw, lang):
    proposed, inv = v2_generic_bundle(raw)
    row = next(row for row in proposed["candidates"] if row["lang"] == lang)
    assert validate_candidate(row, None, registry(), inv) == row
    assert classification_template_sha256(lang, version="classification-v2") == row["template_review"]["sha256"]
    assert classification_template_sha256(lang) != row["template_review"]["sha256"]


@pytest.mark.parametrize("raw,lang", [("个人赛", "en"), ("个人赛", "ru"), ("段位赛", "ko")])
def test_classification_versions_reject_old_text_mixed_review_and_changed_hash(raw, lang):
    proposed, inv = v2_generic_bundle(raw)
    row = next(row for row in proposed["candidates"] if row["lang"] == lang)
    key = "rank_event" if raw == "段位赛" else "individual_event"
    for bad in (
        {**row, "generation_rule_version": "classification-v1"},
        {**row, "generation_rule_version": "classification-v3"},
        {**row, "display_name": _CLASSIFICATION_TEMPLATES[lang][key]},
        {**row, "template_review": {**row["template_review"], "version": "classification-v1"}},
        {**row, "template_review": {**row["template_review"], "sha256": classification_template_sha256(lang)}},
        {**row, "template_review": {**row["template_review"], "sha256": "c" * 64}},
    ):
        with pytest.raises(CandidateError):
            validate_candidate(bad, None, registry(), inv)


@pytest.mark.parametrize("raw", V2_GENERIC_DISPLAYS)
def test_classification_v2_bundle_requires_all_eleven_approved_under_same_version(raw):
    proposed, inv = v2_generic_bundle(raw)
    assert validate_bundle(proposed, registry(), inv, [])["ready"]
    for change in ("missing_language", "missing_candidate", "pending", "v1_language", "legacy_manifest"):
        bad = deepcopy(proposed)
        if change == "missing_language":
            bad["members"].pop()
            bad["candidates"].pop()
            bad["member_set_sha256"] = canonical_sha256(bad["members"])
        elif change == "missing_candidate":
            bad["candidates"].pop()
        elif change == "pending":
            bad["candidates"][-1].update(review_status="pending", reviewer_id="", reviewer_model="",
                                         reviewed_at="", review_conclusion="")
        elif change == "v1_language":
            # cn text is unchanged; its old approval is nevertheless a different protocol.
            row = next(row for row in bad["candidates"] if row["lang"] == "cn")
            row["generation_rule_version"] = "classification-v1"
            row["template_review"].update(version="classification-v1", sha256=classification_template_sha256("cn"))
        else:
            bad["bundle_format"] = 1
        report = validate_bundle(bad, registry(), inv, [])
        assert not report["ready"], change


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
    assert report["errors"] == ["missing candidate: event:3:ru", "linked identity lacks all five approved language names: event:3"]


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


ARCHIVE_DISPLAYS = dict(zip(LANGS, (
    "Hoensha archive game", "方圆社史料棋局", "方圓社史料棋局", "方円社の棋譜（史料）",
    "호엔샤(方円社) 관련 옛 기보", "Historische Partie aus dem Hoensha-Archiv",
    "Partida histórica del archivo de Hoensha", "Partie historique des archives de la Hoensha",
    "Историческая партия из архива Хоэнся", "Hoensha arşivinden tarihî go partisi",
    "Історична партія з архіву Хоенся",
)))


def archive_registry():
    result = registry()
    result["sources"].extend([
        {"id": "cwi-go", "tier": "language_go", "home_url": "https://homepages.cwi.nl/~aeb/go/games/", "language": "en"},
        {"id": "nihon-kiin-archive-jp", "tier": "official", "home_url": "https://archive.nihonkiin.or.jp/", "language": "ja"},
    ])
    return result


def archive_declaration(inv, owner, tmp_path, ids=None):
    ids = ids or [3]
    rows = [dict(zip(inv["association_columns"], row)) for row in inv["album_associations"] if row[0] in ids]
    checks = []
    for source_id, url, body in (
        ("cwi-go", "https://homepages.cwi.nl/~aeb/go/games/games/Hoensha/", b"Hoensha historical game collection"),
        ("nihon-kiin-archive-jp", "https://archive.nihonkiin.or.jp/history/05.html", "方円社の歴史".encode()),
    ):
        path = tmp_path / f"{source_id}.body"
        path.write_bytes(body)
        checks.append({"source_id": source_id, "url": url, "fetched_at": "2026-10-02T09:00:00Z",
                       "body_sha256": hashlib.sha256(body).hexdigest(), "body_path": str(path),
                       "body_excerpt": body.decode(), "context_basis": "Historical organization and preserved games, no event identity"})
    basis = {"version": "archive-description-v1", "raw_value": "Hoensha game", "category": "archive_source_description",
             "inventory_sha256": inv["sha256"], "occurrence_rows": rows,
             "occurrence_rows_sha256": canonical_sha256(rows), "occurrence_sha256": canonical_sha256(ids),
             "source_context": "Reviewed CWI Hoensha corpus; archive is editorial source context", "source_checks": checks}
    return {"owner": owner, "create": {"raw_value": "Hoensha game", "category": "archive_source_description",
            "parser_version": "archive-description-v1"}, "occurrence_album_ids": ids,
            "occurrence_sha256": canonical_sha256(ids), "category_review": {
                "status": "approved", "producer_id": "researcher-1", "producer_model": "gpt-6-luna",
                "produced_at": "2026-10-02T10:00:00Z", "reviewer_id": "category-reviewer-2",
                "reviewer_model": "gpt-6-sol", "reviewed_at": "2026-10-02T10:30:00Z",
                "category_basis": "Bounded historical CWI corpus, not a named event",
                "archive_basis": basis, "archive_basis_sha256": canonical_sha256(basis)}}


def archive_candidate(inv, declaration, lang):
    row = candidate(owner=declaration["owner"], raw_value="Hoensha game", lang=lang,
                    display_name=ARCHIVE_DISPLAYS[lang], decision_kind="archive_description",
                    research_sha256="", generation_rule_version="archive-description-v1")
    row["archive_basis_sha256"] = declaration["category_review"]["archive_basis_sha256"]
    row["archive_scope_sha256"] = canonical_sha256({"inventory_sha256": inv["sha256"], "declaration": declaration})
    row["template_review"] = {"version": "archive-description-v1", "lang": lang,
                              "sha256": canonical_sha256({"version": "archive-description-v1", "lang": lang,
                                  "raw_value": "Hoensha game", "category": "archive_source_description", "display_name": row["display_name"]}),
                              "reviewer_id": row["reviewer_id"], "reviewer_model": row["reviewer_model"],
                              "reviewed_at": row["reviewed_at"], "conclusion": "Reviewed exact editorial archive description"}
    return row


def archive_bundle(tmp_path):
    inv = inventory()
    inv["association_columns"].append("sources")
    for row in inv["album_associations"]:
        row.append([])
    inv["album_associations"].append([3, "Black", "White", "Hoensha game", None, None, None,
                                      [[3, 2, "CWI", "data/kifu-album/CWI_History_Full/Hoensha/A02-1.sgf", "source_path"]]])
    owner = {"kind": "raw_event", "ref": "hoensha-archive"}
    declaration = archive_declaration(inv, owner, tmp_path)
    members = [member(owner, lang, "Hoensha game") for lang in LANGS]
    proposed = bundle(members=members, candidates=[archive_candidate(inv, declaration, lang) for lang in LANGS],
                      bundle_format=2, catalog_sha256="b" * 64, owners=[declaration],
                      owner_set_sha256=canonical_sha256([declaration]), album_links=[],
                      link_set_sha256=canonical_sha256([]), registry_sha256=registry_sha256(archive_registry()))
    return proposed, inv


def test_archive_description_accepts_exact_eleven_strings_without_changing_parser(tmp_path):
    from katrain.web.kifu.name_parse import parse_event
    proposed, inv = archive_bundle(tmp_path)
    report = validate_bundle(proposed, archive_registry(), inv, [])
    assert report["ready"], report["errors"]
    assert report["approved"] == 11
    assert parse_event("Hoensha game", None).category == "unclassified_pending"


def _rebind_archive_scope(proposed):
    declaration = proposed["owners"][0]
    review = declaration["category_review"]
    basis = review["archive_basis"]
    basis["occurrence_rows_sha256"] = canonical_sha256(basis["occurrence_rows"])
    review["archive_basis_sha256"] = canonical_sha256(basis)
    for row in proposed["candidates"]:
        row["archive_basis_sha256"] = review["archive_basis_sha256"]
        row["archive_scope_sha256"] = canonical_sha256({"inventory_sha256": basis["inventory_sha256"],
                                                         "declaration": declaration})
    proposed["owner_set_sha256"] = canonical_sha256(proposed["owners"])


def test_archive_description_accepts_only_reviewed_honinbo_shuho_path(tmp_path):
    for prefix, filename, expected in (
        ("data/kifu-album/", "206.sgf", True),
        ("data/kifu-album/", "999.sgf", False),
        ("other/", "206.sgf", False),
    ):
        proposed, inv = archive_bundle(tmp_path)
        inv["album_associations"][-1][-1][0][3] = (
            f"{prefix}CWI_History_Full/ancient/Honinbo_Shuho/{filename}"
        )
        _rebind_archive_scope(proposed)
        report = validate_bundle(proposed, archive_registry(), inv, [])
        assert report["ready"] is expected, report["errors"]


def test_archive_description_checks_shift_jis_retained_excerpt(tmp_path):
    proposed, inv = archive_bundle(tmp_path)
    check = proposed["owners"][0]["category_review"]["archive_basis"]["source_checks"][1]
    body = "方円社の歴史".encode("shift_jis")
    from pathlib import Path
    Path(check["body_path"]).write_bytes(body)
    check["body_sha256"] = hashlib.sha256(body).hexdigest()
    check["body_excerpt"] = "方円社の歴史"
    _rebind_archive_scope(proposed)
    report = validate_bundle(proposed, archive_registry(), inv, [])
    assert report["ready"], report["errors"]


@pytest.mark.parametrize("change", ["owner", "raw", "version", "category", "parser_version", "basis_missing",
    "body_hash", "body_content", "registry_source", "basis_signature", "non_independent", "early_review",
    "scope_hash", "source_context", "source_path", "occurrence_row", "event_id", "template_text", "template_hash",
    "missing_language", "pending", "legacy_format", "old_owner_category", "identity_owner"])
def test_archive_description_rejects_unbound_or_wrong_scope(tmp_path, change):
    proposed, inv = archive_bundle(tmp_path)
    declaration = proposed["owners"][0]
    review = declaration["category_review"]
    basis = review["archive_basis"]
    if change == "owner":
        for item in [declaration, *proposed["members"], *proposed["candidates"]]:
            item["owner"]["kind"] = "raw_player"
    elif change == "raw":
        declaration["create"]["raw_value"] = "Hoensha Game"
    elif change in {"category", "parser_version"}:
        declaration["create"][change] = "unclassified_pending" if change == "category" else "parser-v1"
    elif change == "version":
        proposed["candidates"][0]["generation_rule_version"] = "archive-description-v2"
    elif change == "basis_missing":
        del review["archive_basis"]
    elif change == "body_hash":
        basis["source_checks"][0]["body_sha256"] = "c" * 64
    elif change == "body_content":
        from pathlib import Path
        Path(basis["source_checks"][0]["body_path"]).write_bytes(b"Changed capture")
    elif change == "registry_source":
        basis["source_checks"][0]["source_id"] = "unregistered"
    elif change == "basis_signature":
        review["archive_basis_sha256"] = "c" * 64
    elif change == "non_independent":
        review["reviewer_id"] = review["producer_id"]
    elif change == "early_review":
        review["reviewed_at"] = "2026-10-02T08:00:00Z"
    elif change == "source_context":
        basis["source_context"] = ""
    elif change == "source_path":
        basis["occurrence_rows"][0]["sources"][0][3] = "unreviewed/other.sgf"
    elif change == "occurrence_row":
        basis["occurrence_rows"][0]["player_black"] = "Wrong"
    elif change == "event_id":
        basis["occurrence_rows"][0]["event_id"] = 1
    elif change == "template_text":
        proposed["candidates"][0]["display_name"] = "Hoensha tournament"
    elif change == "template_hash":
        proposed["candidates"][0]["template_review"]["sha256"] = classification_template_sha256("en")
    elif change == "missing_language":
        proposed["members"].pop()
        proposed["candidates"].pop()
        proposed["member_set_sha256"] = canonical_sha256(proposed["members"])
    elif change == "pending":
        proposed["candidates"][-1].update(review_status="pending", reviewer_id="", reviewer_model="", reviewed_at="", review_conclusion="")
    elif change == "legacy_format":
        proposed["bundle_format"] = 1
    elif change == "old_owner_category":
        declaration["preimage"] = declaration.pop("create") | {"id": 9, "category": "unclassified_pending"}
        for item in [declaration, *proposed["members"], *proposed["candidates"]]:
            item["owner"] = {"kind": "raw_event", "id": 9}
    elif change == "identity_owner":
        proposed["owners"].append({"owner": {"kind": "event", "id": 3}, "preimage": {"id": 3, "canonical_name": "Hoensha"}})
    # Rebind unrelated hashes, so each rejection tests the changed evidence itself.
    if change not in {"basis_missing", "basis_signature"}:
        basis["occurrence_rows_sha256"] = canonical_sha256(basis["occurrence_rows"])
        review["archive_basis_sha256"] = canonical_sha256(basis)
    for row in proposed["candidates"]:
        row["archive_basis_sha256"] = review["archive_basis_sha256"]
        row["archive_scope_sha256"] = canonical_sha256({"inventory_sha256": inv["sha256"], "declaration": declaration})
    if change == "scope_hash":
        proposed["candidates"][0]["archive_scope_sha256"] = "c" * 64
    proposed["owner_set_sha256"] = canonical_sha256(proposed["owners"])
    proposed["member_set_sha256"] = canonical_sha256(proposed["members"])
    assert not validate_bundle(proposed, archive_registry(), inv, [])["ready"], change


def positive_ja_ko_fixture():
    """Synthetic captured bodies for the narrowly scoped normative evidence contract."""
    def capture(url, body, role, lang="ja"):
        return {"url": url, "http_status": 200, "fetched_at": "2026-10-02T10:00:00Z",
                "body_text": body, "body_sha256": hashlib.sha256(body.encode()).hexdigest(),
                "body_excerpt": body, "locator": "synthetic fixture paragraph", "source_role": role,
                "observed_lang": lang}
    reading_capture = capture("https://example.org/go", "呉清源 ご せいげん Professional Go player", "professional_archive")
    roles = {"personal_names": "P000146", "kana_table": "P000108", "japanese_details": "P000129"}
    positive = {
        "version": 1,
        "identity": {"owner": {"kind": "player", "id": 17}, "original_name": "呉清源",
                     "reading": "ご せいげん", "status": "verified", "method": "reviewed_owner_binding",
                     "basis": "Historical profile matched the existing physical owner", "capture": reading_capture},
        "reading": {"surname": "ご", "given": "せいげん", "capture": reading_capture},
        "rules": [{"role": role, "capture": capture(
            f"https://www.korean.go.kr/front/page/pageView.do?mn_id=97&page_id={page}",
            f"{page} 실제 일본어 인명 표기 규정", "normative_rule", "ko")} for role, page in roles.items()],
        "explanation": {"surname": "고", "given": "세이겐", "output": "고 세이겐",
                        "rule_applications": [{"rule_role": role, "locator": "synthetic fixture paragraph",
                                              "input": "ご せいげん", "output": "고 세이겐",
                                              "reason": "Reviewed surname/given, initial/medial and applicable kana"}
                                             for role in roles]},
        "conflict_queries": [{"role": role, "query": query,
                              "capture": capture(f"https://example.org/search?q={role}",
                                                 "Usable search results for " + query, "search_results", "ko"),
                              "relevant_results": [], "conclusion": "no_unresolved_conflict"}
                             for role, query in [("original_go", "呉清源 바둑"),
                                                 ("candidate_go", "고 세이겐 바둑")]],
        "unresolved_conflicts": [],
    }
    evidence = research(lang="ko", source_basis="normative_ja_ko_v1", scope_status="generated_from_original",
                        generation_rule_version="nikl-ja-ko-personal-name-v1", candidate_name="고 세이겐",
                        positive_generation=positive,
                        source_checks=[check(observed_lang="ja", candidate_name="呉清源",
                                             body_excerpt=reading_capture["body_excerpt"],
                                             body_sha256=reading_capture["body_sha256"])])
    row = approved_generated(candidate(lang="ko", display_name="고 세이겐", decision_kind="generated",
                                       research_sha256=canonical_sha256(evidence),
                                       generation_rule_version="nikl-ja-ko-personal-name-v1"), evidence)
    row["generated_review"].update(positive_generation_sha256=canonical_sha256(positive),
                                   identity_input_review="approved", rule_review="approved", output_review="approved")
    return evidence, row


def test_positive_ja_ko_research_and_pending_then_exact_approved_candidate():
    from katrain.web.kifu.name_evidence import validate_research_record
    evidence, row = positive_ja_ko_fixture()
    assert validate_research_record(evidence, registry())["scope_status"] == "generated_from_original"
    pending = {**row, "review_status": "pending", "reviewer_id": "", "reviewer_model": "", "reviewed_at": "", "review_conclusion": ""}
    assert validate_candidate(pending, evidence, registry(), inventory())["decision_kind"] == "generated"
    assert validate_candidate(row, evidence, registry(), inventory()) == row


@pytest.mark.parametrize("change", [
    "wrong_owner_kind", "wrong_target", "wrong_source", "wrong_rule", "hash", "reading",
    "rule_page", "failed_query", "wrong_query_tokens", "unresolved", "unknown_field", "negative_closure",
])
def test_positive_ja_ko_rejects_invalid_evidence_boundaries(change):
    from katrain.web.kifu.name_evidence import EvidenceError, validate_research_record
    evidence, _ = positive_ja_ko_fixture()
    positive = evidence["positive_generation"]
    if change == "wrong_owner_kind": evidence["owner"]["kind"] = "event"
    elif change == "wrong_target": evidence["lang"] = "jp"
    elif change == "wrong_source": evidence["original_language"] = "ko"
    elif change == "wrong_rule": evidence["generation_rule_version"] = "arbitrary-v1"
    elif change == "hash": positive["reading"]["capture"]["body_sha256"] = "b" * 64
    elif change == "reading": positive["reading"]["given"] = "guess"
    elif change == "rule_page": positive["rules"][0]["capture"]["url"] = "https://www.korean.go.kr/other"
    elif change == "failed_query": positive["conflict_queries"][0]["capture"]["http_status"] = 403
    elif change == "wrong_query_tokens": positive["conflict_queries"][1]["query"] = "something else"
    elif change == "unresolved": positive["unresolved_conflicts"] = ["Different sourced reading"]
    elif change == "unknown_field": positive["invented"] = True
    elif change == "negative_closure": evidence["negative_closure"] = {}
    with pytest.raises(EvidenceError): validate_research_record(evidence, registry())


@pytest.mark.parametrize("change", ["early_review", "output", "research_hash", "review_hash", "input_review", "rule"])
def test_positive_ja_ko_rejects_inexact_or_early_review(change):
    evidence, row = positive_ja_ko_fixture()
    if change == "early_review":
        evidence["positive_generation"]["rules"][0]["capture"]["fetched_at"] = "2026-10-02T12:00:00Z"
        row["research_sha256"] = canonical_sha256(evidence)
        row["generated_review"].update(research_sha256=row["research_sha256"],
            positive_generation_sha256=canonical_sha256(evidence["positive_generation"]))
    elif change == "output": row["display_name"] = "다른 이름"
    elif change == "research_hash": row["research_sha256"] = "b" * 64
    elif change == "review_hash": row["generated_review"]["positive_generation_sha256"] = "b" * 64
    elif change == "input_review": row["generated_review"]["identity_input_review"] = "pending"
    elif change == "rule": row["generation_rule_version"] = "arbitrary-v1"
    with pytest.raises(CandidateError): validate_candidate(row, evidence, registry(), inventory())


def positive_zh_ko_fixture(owner_id=5498):
    from katrain.web.kifu.name_zh_ko import RULE_BODY_SHA256, RULE_URL, used_entries

    values = {5498: ("王宏伟", "Wang Hongwei", [["wang"], ["hong", "wei"]], "왕훙웨이"),
              5739: ("翁子瑜", "Weng Ziyu", [["weng"], ["zi", "yu"]], "웡쯔위")}
    han, latin, words, hangul = values[owner_id]
    owner = {"kind": "player", "id": owner_id}

    def capture(url, body, role, lang):
        return {"url": url, "http_status": 200, "fetched_at": "2026-10-08T21:50:12Z",
                "body_text": body, "body_sha256": hashlib.sha256(body.encode()).hexdigest(),
                "body_excerpt": body, "locator": "person row", "source_role": role,
                "observed_lang": lang}

    profile = capture(f"https://db.u-go.net/{owner_id}/", f"{han} {latin} Citizenship: CHN",
                      "published_player_profile", "en")
    search = capture(f"https://db.u-go.net/?q={latin.replace(' ', '+')}",
                     f"U-Go professional Go player search: {han} {latin} links to profile",
                     "professional_go_search", "en")
    original = capture("https://wqapi.cwql.org.cn/playerInfo/professional/list",
                       f"playerName {han} professional player", "official_roster", "zh-Hans")
    rule = {"url": RULE_URL, "http_status": 200, "fetched_at": "2026-10-08T21:30:16Z",
            "body_sha256": RULE_BODY_SHA256, "source_role": "normative_rule", "observed_lang": "ko",
            "table_locator": "Chapter 2 Table 5, raw HTML line 1573; note line 1578",
            "scope_locator": "Chapter 4 section 2 item 1, raw HTML line 13706",
            "tone_locator": "Chapter 3 Chinese section item 1, raw HTML line 6666"}
    positive = {
        "version": 1,
        "scope": {"modern_mainland": True, "ordinary_mandarin": True, "personal_name": True,
                  "basis": "Same person in a CHN Go profile and Chinese professional roster",
                  "unresolved_reading_variants": []},
        "identity": {"owner": deepcopy(owner), "original_name": han, "status": "verified",
                     "method": "reviewed_owner_binding", "basis": "Exact owner and Han name matched",
                     "capture": original},
        "reading": {"published": latin, "system": "pinyin-syllables-v1", "reading_words": words,
                    "determination": "Reviewed complete ordinary Hanyu Pinyin in mainland Go context",
                    "capture": profile},
        "rule": {"capture": rule, "used_entries": used_entries(words),
                 "output": hangul, "format": "joined_surname_given_project_format"},
        "contrary_checks": [
            {"role": "original_go", "query": latin, "search_scope": "U-Go professional Go player database search",
             "status": "found", "capture": search, "relevant_matches": [f"{han} {latin}"],
             "resolution": "Same person and no conflicting reading", "conventional_gate_qualified": False},
            {"role": "candidate_go", "query": hangul,
             "search_scope": "Literal scan of saved Daum Chinese Go player roster",
             "status": "found",
             "capture": capture("https://example.org/korean-roster", f"{hangul} {han} Go",
                                "reference_go_roster", "ko"),
             "relevant_matches": [f"{hangul} {han}"],
             "resolution": "Matching community usage; no qualified conventional source",
             "conventional_gate_qualified": False},
        ],
        "unresolved_conflicts": [], "source_anchors": [],
    }
    reg = registry()
    reg["sources"].append({"id": "cwa", "tier": "official", "home_url": "https://wqapi.cwql.org.cn/",
                           "language": "zh-Hans"})
    evidence = research(owner=owner, lang="ko", registry_sha256=registry_sha256(reg),
                        source_basis="normative_zh_ko_v1", scope_status="generated_from_original",
                        generation_rule_version="nikl-zh-ko-personal-name-v1", original_name=han,
                        original_language="zh-Hans", original_language_basis_url=original["url"],
                        reading=latin, reading_basis_url=profile["url"], candidate_name=hangul,
                        positive_zh_ko=positive,
                        source_checks=[check(owner=owner, source_id="cwa", url=original["url"],
                                             observed_lang="zh-Hans", candidate_name=han,
                                             body_excerpt=original["body_excerpt"],
                                             body_sha256=original["body_sha256"])])
    row = candidate(owner=owner, lang="ko", display_name=hangul, decision_kind="generated",
                    research_sha256=canonical_sha256(evidence),
                    generation_rule_version="nikl-zh-ko-personal-name-v1")
    row.update(producer_id=evidence["producer_id"], producer_model=evidence["producer_model"],
               produced_at="2026-10-08T21:55:00Z", reviewed_at="2026-10-08T22:00:00Z",
               review_conclusion="approved_generated_display_and_rule")
    row["generated_review"] = {
        "decision": "approve_generated", "display_name": hangul, "owner": owner, "lang": "ko",
        "generation_rule_version": row["generation_rule_version"], "research_sha256": row["research_sha256"],
        "original_name": han, "reading": latin, "reading_words": words,
        "reading_basis_url": profile["url"], "used_entries": positive["rule"]["used_entries"],
        "positive_zh_ko_sha256": canonical_sha256(positive), "identity_input_review": "approved",
        "rule_review": "approved", "output_review": "approved", "reviewer_id": row["reviewer_id"],
        "reviewer_model": row["reviewer_model"], "reviewed_at": row["reviewed_at"],
        "reason": "Checked exact sourced reading, finite NIKL entries and full output",
    }
    return evidence, row, reg


@pytest.mark.parametrize("words,expected", [
    ([["huang"], ["jia", "yin"]], "황자인"),
    ([["yang"], ["yi", "lun"]], "양이룬"),
    ([["ke"], ["pei", "chen"]], "커페이천"),
    ([["wang"], ["zi", "han"]], "왕쯔한"),
])
def test_positive_zh_ko_four_reviewed_finite_outputs(words, expected):
    from katrain.web.kifu.name_zh_ko import render_name

    assert render_name(words) == expected


def positive_zh_ko_modern_fixture(owner_id):
    from katrain.web.kifu.name_zh_ko import used_entries

    cases = {
        6531: ("黃家胤", "zh-Hant", "Huang Jia-Yin", [["huang"], ["jia", "yin"]], "황자인",
               "https://taiwangorg.blogspot.com/2022/12/blog-post_91.html", None, None),
        5115: ("杨以伦", "zh-Hans", "Yang Yilun", [["yang"], ["yi", "lun"]], "양이룬",
               "https://db.u-go.net/2275/", None, None),
        5214: ("柯沛辰", "zh-Hans", "Ke Peichen", [["ke"], ["pei", "chen"]], "커페이천",
               "https://goratings.org/zh/players/2480.html", 2480,
               "https://www.haifong.org/profession/venue/ACBF499C50310A39B5ED50FBD5B1E4E3"),
        5543: ("王紫涵", "zh-Hans", "Wang Zihan", [["wang"], ["zi", "han"]], "왕쯔한",
               "https://www.goratings.org/zh/players/2445.html", 2445,
               "https://www.haifong.org/profession/venue/B15AD71345F8FF8D7E2E8FC2D7037F82"),
    }
    han, lang, latin, words, hangul, original_url, pair_id, authority_url = cases[owner_id]
    evidence, row, reg = positive_zh_ko_fixture()
    owner = {"kind": "player", "id": owner_id}

    def capture(url, body, observed):
        return {"url": url, "http_status": 200, "fetched_at": "2026-10-08T21:50:12Z",
                "body_text": body, "body_sha256": hashlib.sha256(body.encode()).hexdigest(),
                "body_excerpt": body, "locator": "player heading", "source_role": "published_player_profile",
                "observed_lang": observed}

    original_body = f"{han} {latin}" if pair_id is None else f"{han} {authority_url}"
    original = capture(original_url, original_body, lang)
    if pair_id is None:
        reading = original if owner_id == 6531 else capture(original_url, f"{han} {latin}", "en")
    else:
        reading = capture(f"https://www.goratings.org/en/players/{pair_id}.html",
                          f"{latin} {authority_url}", "en")
    positive = evidence["positive_zh_ko"]
    positive["scope"] = {"modern_standard_mandarin": True, "ordinary_mandarin": True,
                         "personal_name": True, "basis": f"Reviewed published {han}/{latin} Go profile",
                         "unresolved_reading_variants": []}
    positive["identity"].update(owner=deepcopy(owner), original_name=han, capture=original)
    positive["reading"].update(published=latin, reading_words=words, capture=reading)
    if pair_id is not None:
        positive["reading"]["profile_pair"] = {"provider": "goratings", "player_id": pair_id,
                                                 "original_url": original_url, "authority_url": authority_url}
    positive["rule"].update(used_entries=used_entries(words), output=hangul)
    positive["contrary_checks"][0]["query"] = latin
    positive["contrary_checks"][0]["capture"]["url"] = f"https://db.u-go.net/?q={quote_plus(latin)}"
    positive["contrary_checks"][0]["capture"]["body_text"] = f"Go search {han} {latin}"
    positive["contrary_checks"][0]["capture"]["body_excerpt"] = f"Go search {han} {latin}"
    positive["contrary_checks"][0]["capture"]["body_sha256"] = hashlib.sha256(
        f"Go search {han} {latin}".encode()).hexdigest()
    positive["contrary_checks"][0]["relevant_matches"] = [f"{han} {latin}"]
    positive["contrary_checks"][1]["query"] = hangul
    positive["contrary_checks"][1]["capture"]["body_text"] = f"{hangul} {han} Go"
    positive["contrary_checks"][1]["capture"]["body_excerpt"] = f"{hangul} {han} Go"
    positive["contrary_checks"][1]["capture"]["body_sha256"] = hashlib.sha256(
        f"{hangul} {han} Go".encode()).hexdigest()
    positive["contrary_checks"][1]["relevant_matches"] = [f"{hangul} {han}"]
    evidence.update(owner=owner, original_name=han, original_language=lang,
                    original_language_basis_url=original_url, reading=latin,
                    reading_basis_url=reading["url"], candidate_name=hangul)
    source_id = "taiwan" if owner_id == 6531 else "ugo" if owner_id == 5115 else "goratings"
    reg["sources"].append({"id": source_id, "tier": "language_go", "home_url":
                           "https://taiwangorg.blogspot.com/" if owner_id == 6531 else
                           "https://db.u-go.net/" if owner_id == 5115 else "https://goratings.org/",
                           "language": lang})
    evidence["registry_sha256"] = registry_sha256(reg)
    evidence["source_checks"] = [check(owner=owner, source_id=source_id, url=original_url,
                                       observed_lang=lang, query=han, candidate_name=han,
                                       body_excerpt=original["body_excerpt"],
                                       body_sha256=original["body_sha256"])]
    row.update(owner=owner, display_name=hangul, research_sha256=canonical_sha256(evidence))
    row["generated_review"].update(owner=owner, display_name=hangul, research_sha256=row["research_sha256"],
                                   original_name=han, reading=latin, reading_words=words,
                                   reading_basis_url=reading["url"], used_entries=positive["rule"]["used_entries"],
                                   positive_zh_ko_sha256=canonical_sha256(positive))
    return evidence, row, reg


@pytest.mark.parametrize("owner_id", [6531, 5115, 5214, 5543])
def test_positive_zh_ko_modern_scope_and_actual_profile_shapes(owner_id):
    from katrain.web.kifu.name_evidence import validate_positive_zh_ko_candidate

    evidence, row, reg = positive_zh_ko_modern_fixture(owner_id)
    assert validate_positive_zh_ko_candidate(row, evidence, reg) == row


def test_positive_zh_ko_traditional_original_rejects_simplified_page_label():
    from katrain.web.kifu.name_evidence import EvidenceError, validate_research_record

    evidence, _, reg = positive_zh_ko_modern_fixture(6531)
    evidence["positive_zh_ko"]["identity"]["capture"]["observed_lang"] = "zh-Hans"
    with pytest.raises(EvidenceError):
        validate_research_record(evidence, reg)


@pytest.mark.parametrize("change", ["mixed_scope", "false_scope", "pair_id", "pair_url", "pair_params",
                                     "pair_authority", "pair_provider_as_authority",
                                     "original_hash", "reading_hash", "missing_original", "missing_latin"])
def test_positive_zh_ko_modern_pair_rejects_unbound_pages(change):
    from katrain.web.kifu.name_evidence import EvidenceError, validate_research_record

    evidence, _, reg = positive_zh_ko_modern_fixture(5214)
    positive = evidence["positive_zh_ko"]
    pair = positive["reading"]["profile_pair"]
    if change == "mixed_scope": positive["scope"]["modern_mainland"] = True
    elif change == "false_scope": positive["scope"]["modern_standard_mandarin"] = False
    elif change == "pair_id": pair["player_id"] = 2445
    elif change == "pair_url": pair["original_url"] = "https://goratings.org/zh/players/2445.html"
    elif change == "pair_params":
        positive["reading"]["capture"]["url"] += ";extra"
        evidence["reading_basis_url"] = positive["reading"]["capture"]["url"]
    elif change == "pair_authority": pair["authority_url"] = "https://other.example/"
    elif change == "pair_provider_as_authority":
        old = pair["authority_url"]
        pair["authority_url"] = "https://goratings.org/players/2480"
        for capture in (positive["identity"]["capture"], positive["reading"]["capture"]):
            capture["body_text"] = capture["body_excerpt"] = capture["body_text"].replace(old, pair["authority_url"])
            capture["body_sha256"] = hashlib.sha256(capture["body_text"].encode()).hexdigest()
        evidence["source_checks"][0]["body_excerpt"] = positive["identity"]["capture"]["body_excerpt"]
        evidence["source_checks"][0]["body_sha256"] = positive["identity"]["capture"]["body_sha256"]
    elif change == "original_hash": positive["identity"]["capture"]["body_sha256"] = "b" * 64
    elif change == "reading_hash": positive["reading"]["capture"]["body_sha256"] = "b" * 64
    elif change in {"missing_original", "missing_latin"}:
        capture = (positive["identity"]["capture"] if change == "missing_original"
                   else positive["reading"]["capture"])
        capture["body_text"] = capture["body_excerpt"] = f"Other player {pair['authority_url']}"
        capture["body_sha256"] = hashlib.sha256(capture["body_text"].encode()).hexdigest()
    with pytest.raises(EvidenceError):
        validate_research_record(evidence, reg)


@pytest.mark.parametrize("owner_id", [5498, 5739])
def test_positive_zh_ko_accepts_only_reviewed_first_batch_inputs(owner_id):
    from katrain.web.kifu.name_evidence import validate_positive_zh_ko_candidate, validate_research_record
    evidence, row, reg = positive_zh_ko_fixture(owner_id)
    assert validate_research_record(evidence, reg)["owner"] == evidence["owner"]
    assert validate_positive_zh_ko_candidate(row, evidence, reg) == row


@pytest.mark.parametrize("owner_id", [5498, 5739])
def test_positive_zh_ko_keeps_actual_pinyin_and_roster_literal_queries(owner_id):
    from katrain.web.kifu.name_evidence import validate_research_record
    evidence, _, reg = positive_zh_ko_fixture(owner_id)
    original, korean = evidence["positive_zh_ko"]["contrary_checks"]
    assert original["query"] == evidence["reading"]
    assert korean["query"] == evidence["candidate_name"]
    assert validate_research_record(evidence, reg)["owner"] == evidence["owner"]


def test_positive_zh_ko_accepts_exact_han_name_query_in_go_corpus():
    from katrain.web.kifu.name_evidence import validate_research_record
    evidence, _, reg = positive_zh_ko_fixture()
    item = evidence["positive_zh_ko"]["contrary_checks"][0]
    item["query"] = evidence["original_name"]
    item["capture"]["url"] = f"https://db.u-go.net/?q={quote_plus(item['query'])}"
    assert validate_research_record(evidence, reg)["owner"] == evidence["owner"]


@pytest.mark.parametrize("change", ["owner", "source", "language", "reading", "segments", "unknown_syllable",
                                     "rule_hash", "rule_url", "body_hash", "scope", "conflict", "mixed_ja",
                                     "generic_marker", "wrong_output", "conventional_usage", "missing_scope",
                                     "wrong_scope", "wrong_query", "wrong_query_url"])
def test_positive_zh_ko_rejects_wrong_or_partial_evidence(change):
    from katrain.web.kifu.name_evidence import EvidenceError, validate_research_record
    evidence, _, reg = positive_zh_ko_fixture()
    positive = evidence["positive_zh_ko"]
    if change == "owner": positive["identity"]["owner"]["id"] = 1
    elif change == "source": evidence["reading_basis_url"] = "https://other.example/"
    elif change == "language": evidence["original_language"] = "ja"
    elif change == "reading": positive["reading"]["published"] = "Lin Qinghai"
    elif change == "segments": positive["reading"]["reading_words"] = [["wang", "hong"], ["wei"]]
    elif change == "unknown_syllable": positive["reading"]["reading_words"][1][0] = "xu"
    elif change == "rule_hash": positive["rule"]["capture"]["body_sha256"] = "b" * 64
    elif change == "rule_url": positive["rule"]["capture"]["url"] = "https://example.org/rules"
    elif change == "body_hash": positive["reading"]["capture"]["body_sha256"] = "b" * 64
    elif change == "scope": positive["scope"]["ordinary_mandarin"] = False
    elif change == "conflict": positive["unresolved_conflicts"] = ["other reading"]
    elif change == "mixed_ja": evidence["positive_generation"] = {}
    elif change == "generic_marker": evidence["positive_generation"] = True
    elif change == "wrong_output": positive["rule"]["output"] = "다른이름"
    elif change == "conventional_usage": positive["contrary_checks"][1]["conventional_gate_qualified"] = True
    elif change == "missing_scope": positive["contrary_checks"][0]["search_scope"] = ""
    elif change == "wrong_scope": positive["contrary_checks"][1]["search_scope"] = "Unrelated movie corpus"
    elif change == "wrong_query": positive["contrary_checks"][0]["query"] = "Unrelated person"
    elif change == "wrong_query_url": positive["contrary_checks"][0]["query"] = evidence["original_name"]
    with pytest.raises(EvidenceError): validate_research_record(evidence, reg)


@pytest.mark.parametrize("change", ["output", "review_hash", "review_words", "early_review", "producer",
                                     "pending", "rule"])
def test_positive_zh_ko_rejects_inexact_or_early_candidate_review(change):
    from katrain.web.kifu.name_evidence import EvidenceError, validate_positive_zh_ko_candidate
    evidence, row, reg = positive_zh_ko_fixture()
    if change == "output": row["display_name"] = "다른이름"
    elif change == "review_hash": row["generated_review"]["positive_zh_ko_sha256"] = "b" * 64
    elif change == "review_words": row["generated_review"]["reading_words"] = [["wang"], ["hongwei"]]
    elif change == "early_review": row["reviewed_at"] = "2026-10-08T21:00:00Z"
    elif change == "producer": row["reviewer_id"] = row["producer_id"]
    elif change == "pending": row["review_status"] = "pending"
    elif change == "rule": row["generation_rule_version"] = "nikl-ja-ko-personal-name-v1"
    with pytest.raises(EvidenceError): validate_positive_zh_ko_candidate(row, evidence, reg)


def test_positive_zh_ko_accepts_actual_search_tool_transcript_without_http_claim():
    from katrain.web.kifu.name_evidence import validate_positive_zh_ko_candidate
    evidence, row, reg = positive_zh_ko_fixture()
    body = '{"query":"Wang Hongwei","result":"王宏伟 Wang Hongwei same player"}'
    item = evidence["positive_zh_ko"]["contrary_checks"][0]
    item["capture"] = {"capture_kind": "web_tool_response", "queried_at": "2026-10-08T21:56:01Z",
                       "response_status": "completed_with_results", "body_text": body,
                       "body_sha256": hashlib.sha256(body.encode()).hexdigest(),
                       "body_excerpt": body, "locator": "result 1", "source_role": "search_tool_response",
                       "observed_lang": "mul"}
    row["research_sha256"] = canonical_sha256(evidence)
    row["generated_review"]["research_sha256"] = row["research_sha256"]
    row["generated_review"]["positive_zh_ko_sha256"] = canonical_sha256(evidence["positive_zh_ko"])
    assert validate_positive_zh_ko_candidate(row, evidence, reg) == row


def test_positive_zh_ko_not_found_cannot_hide_captured_matching_name():
    from katrain.web.kifu.name_evidence import EvidenceError, validate_research_record
    evidence, _, reg = positive_zh_ko_fixture()
    item = evidence["positive_zh_ko"]["contrary_checks"][1]
    item["status"] = "not_found"
    item["relevant_matches"] = []
    with pytest.raises(EvidenceError): validate_research_record(evidence, reg)


def test_positive_zh_ko_professional_korean_name_routes_to_conventional_review():
    from katrain.web.kifu.name_evidence import EvidenceError, validate_research_record
    evidence, _, reg = positive_zh_ko_fixture()
    evidence["positive_zh_ko"]["contrary_checks"][1]["capture"]["source_role"] = "professional_go_profile"
    with pytest.raises(EvidenceError): validate_research_record(evidence, reg)


@pytest.mark.parametrize("role", ["official_go_roster", "official_roster"])
def test_positive_zh_ko_official_korean_roster_hit_routes_to_conventional_review(role):
    from katrain.web.kifu.name_evidence import EvidenceError, validate_research_record
    evidence, _, reg = positive_zh_ko_fixture()
    # The captured row contains this owner's exact Han and Korean names.
    evidence["positive_zh_ko"]["contrary_checks"][1]["capture"]["source_role"] = role
    with pytest.raises(EvidenceError): validate_research_record(evidence, reg)


def test_positive_zh_ko_unrelated_official_roster_hit_can_be_resolved():
    from katrain.web.kifu.name_evidence import validate_research_record
    evidence, _, reg = positive_zh_ko_fixture()
    item = evidence["positive_zh_ko"]["contrary_checks"][1]
    item["capture"]["source_role"] = "official_go_roster"
    item["capture"]["body_text"] = "왕훙웨이 王鸿薇 is a different person"
    item["capture"]["body_excerpt"] = item["capture"]["body_text"]
    item["capture"]["body_sha256"] = hashlib.sha256(item["capture"]["body_text"].encode()).hexdigest()
    item["relevant_matches"] = ["왕훙웨이 王鸿薇"]
    item["resolution"] = "Different Han name and different owner; not the Go player 王宏伟"
    assert validate_research_record(evidence, reg)["owner"] == evidence["owner"]


@pytest.mark.parametrize("relevant_matches", [["왕훙웨이", "王宏伟"], []])
def test_positive_zh_ko_official_same_person_row_cannot_hide_in_relevant_match_grouping(relevant_matches):
    from katrain.web.kifu.name_evidence import EvidenceError, validate_research_record
    evidence, _, reg = positive_zh_ko_fixture()
    item = evidence["positive_zh_ko"]["contrary_checks"][1]
    item["capture"]["source_role"] = "official_go_roster"
    item["relevant_matches"] = relevant_matches
    item["resolution"] = "Same Go player 王宏伟 has published official Korean name 왕훙웨이"
    with pytest.raises(EvidenceError): validate_research_record(evidence, reg)


@pytest.mark.parametrize("queried_form", ["han", "pinyin"])
def test_positive_zh_ko_not_found_cannot_hide_single_queried_original_form(queried_form):
    from katrain.web.kifu.name_evidence import EvidenceError, validate_research_record
    evidence, _, reg = positive_zh_ko_fixture()
    item = evidence["positive_zh_ko"]["contrary_checks"][0]
    form = evidence["original_name"] if queried_form == "han" else evidence["reading"]
    item["query"] = form
    item["status"] = "not_found"
    item["relevant_matches"] = []
    item["capture"]["url"] = f"https://db.u-go.net/?q={quote_plus(form)}"
    item["capture"]["body_text"] = f"U-Go professional Go player result: {form}"
    item["capture"]["body_excerpt"] = item["capture"]["body_text"]
    item["capture"]["body_sha256"] = hashlib.sha256(item["capture"]["body_text"].encode()).hexdigest()
    with pytest.raises(EvidenceError): validate_research_record(evidence, reg)


def test_registry_version_fits_persisted_column(tmp_path):
    from katrain.web.kifu.name_evidence import EvidenceError, load_registry
    reg = registry()
    reg["version"] = "v" * 65
    path = tmp_path / "registry.json"
    path.write_text(json.dumps(reg), encoding="utf-8")
    with pytest.raises(EvidenceError): load_registry(path)
