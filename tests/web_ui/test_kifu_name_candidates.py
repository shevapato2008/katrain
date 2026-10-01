"""Approved display decisions require exact scope, evidence and independent review."""

from copy import deepcopy
import hashlib
import json

import pytest

from katrain.web.kifu.name_candidates import (
    CandidateError,
    canonical_sha256,
    classification_template_sha256,
    validate_bundle,
    validate_candidate,
    render_event_components,
)
from katrain.web.kifu.name_evidence import registry_sha256
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


def test_discovery_only_and_incomplete_research_do_not_approve_conventional_name():
    discovery = research(source_checks=[check(source_id="wd", url="https://www.wikidata.org/wiki/Q1")])
    with pytest.raises(CandidateError):
        validate_candidate(candidate(research_sha256=canonical_sha256(discovery)), discovery, registry(), inventory())
    incomplete = research(scope_status="incomplete", candidate_name="", source_checks=[check(
        status="unavailable", candidate_name="", url="https://example.org/go", http_status=429,
        body_sha256="", body_excerpt="", observed_lang="", language_basis="")])
    with pytest.raises(CandidateError):
        validate_candidate(candidate(research_sha256=canonical_sha256(incomplete)), incomplete, registry(), inventory())


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


def test_generated_name_requires_completed_negative_scope_and_reading_basis():
    negative = research(scope_status="not_found_in_scope", candidate_name="", source_checks=[check(
        status="not_found", candidate_name="", identity_basis="", body_excerpt="Search finished with no Russian name",
        search_scope="All player names", scope_complete=True)])
    generated = candidate(display_name="Го Сэйгэн", decision_kind="generated",
                          research_sha256=canonical_sha256(negative), generation_rule_version="ja-ru-v1")
    assert validate_candidate(generated, negative, registry(), inventory())["decision_kind"] == "generated"
    with pytest.raises(CandidateError):
        validate_candidate(candidate(decision_kind="generated", generation_rule_version="ja-ru-v1"),
                           research(), registry(), inventory())
    missing_reading = deepcopy(negative)
    missing_reading.pop("reading_basis_url")
    with pytest.raises(CandidateError):
        validate_candidate({**generated, "research_sha256": canonical_sha256(missing_reading)},
                           missing_reading, registry(), inventory())
    with pytest.raises(CandidateError, match="script"):
        validate_candidate({**generated, "display_name": "Go Seigen"}, negative, registry(), inventory())


def test_pending_is_reported_but_never_upgraded_to_approved():
    pending = candidate(review_status="pending", reviewer_id="", reviewer_model="",
                        reviewed_at="", review_conclusion="")
    report = validate_bundle(bundle(candidates=[pending]), registry(), inventory(), [research()])
    assert report["pending"] == 1 and report["approved"] == 0 and not report["ready"]


def test_unselected_contradictory_research_for_same_owner_language_blocks_bundle():
    negative = research(scope_status="not_found_in_scope", candidate_name="", source_checks=[check(
        status="not_found", candidate_name="", identity_basis="", body_excerpt="Completed Russian search, no name",
        search_scope="All indexed profiles", scope_complete=True)])
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
