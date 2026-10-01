"""Evidence discovery must never turn a search failure into an approved name."""

import hashlib
import json
from copy import deepcopy

import pytest

from katrain.web.kifu.name_evidence import (
    EvidenceError,
    capture_source_check,
    load_registry,
    product_language_tag,
    registry_sha256,
    negative_closure_evidence_sha256,
    source_plan,
    validate_research_record,
)
from scripts.kifu_name_research import main


def _registry():
    tags = {"ua": "uk", "jp": "ja", "cn": "zh-Hans", "tw": "zh-Hant", "ru": "ru"}
    return {
        "version": "test-1",
        "language_tags": tags,
        "sources": [
            {"id": "ru-go", "tier": "language_go", "home_url": "https://example.org/", "language": "ru"},
            {"id": "wd", "tier": "discovery", "home_url": "https://www.wikidata.org/", "language": "mul"},
        ],
        "language_scopes": {lang: {"required_source_ids": ["ru-go", "wd"],
                                   "complete_for_negative_claims": lang == "ru"} for lang in tags},
    }


def _check(source="ru-go", **updates):
    check = {
        "owner": {"kind": "player", "id": 17},
        "source_id": source,
        "query": "Go Seigen",
        "status": "found",
        "url": "https://example.org/go-seigen",
        "fetched_at": "2026-10-02T10:00:00Z",
        "http_status": 200,
        "body_sha256": hashlib.sha256("Го Сэйгэн".encode()).hexdigest(),
        "body_excerpt": "Го Сэйгэн — профессиональный игрок го",
        "observed_lang": "ru",
        "language_basis": "reviewed_text",
        "candidate_name": "Го Сэйгэн",
        "identity_basis": "Professional profile identifies Go Seigen",
    }
    check.update(updates)
    return check


def _record(owner=None, **updates):
    record = {
        "owner": owner or {"kind": "player", "id": 17},
        "lang": "ru",
        "registry_version": "test-1",
        "registry_sha256": registry_sha256(_registry()),
        "scope_status": "found",
        "candidate_name": "Го Сэйгэн",
        "source_checks": [_check()],
        "original_name": "呉清源",
        "original_language": "ja",
        "original_language_basis_url": "https://example.org/go-seigen",
        "reading": "ご せいげん",
        "reading_basis_url": "https://example.org/go-seigen",
        "producer_id": "research-001",
        "producer_model": "gpt-6-luna",
        "review_status": "pending",
    }
    record.update(updates)
    return record


def _finite_negative():
    registry = _registry()
    record = _record(
        lang="ua", source_lang="ja", scope_status="not_found_in_scope", candidate_name="",
        source_checks=[
            _check(source_id="ru-go", check_id="professional", status="not_found", candidate_name="",
                   identity_basis="", observed_lang="uk", body_excerpt="Search found no Ukrainian name",
                   search_scope="Named pages and indexed results", scope_complete=True,
                   negative_outcome="no_target_string", method="site_search",
                   response_sha256="a" * 64),
            _check("wd", check_id="wikidata-uk", status="not_found", candidate_name="", identity_basis="",
                   url="https://www.wikidata.org/wiki/Q1", observed_lang="uk",
                   body_excerpt="Q1 has no uk label or alias", search_scope="Q1 exact uk labels and aliases",
                   scope_complete=True, negative_outcome="no_target_string", method="entity_api",
                   response_sha256="b" * 64),
        ],
    )
    for check in record["source_checks"]:
        check["completeness"] = "complete"
    record["negative_closure"] = {
        "version": 1, "owner": record["owner"], "lang": "ua", "source_lang": "ja",
        "scope_id": "oteai-uk-pilot", "scope_version": "1", "registry_sha256": record["registry_sha256"],
        "required_check_ids": ["professional", "wikidata-uk"],
        "scope_boundary": "Named pages, indexed search, and exact Q1 uk fields",
        "retained_limitations": ["Unindexed forum posts and print publications"],
        "reviewer_id": "negative-reviewer", "reviewer_model": "gpt-6-astra",
        "reviewed_at": "2026-10-02T11:00:00Z", "conclusion": "approved_not_found_in_scope",
        "reason": "All listed checks finished without an admissible Ukrainian name",
    }
    record["negative_closure"]["evidence_sha256"] = negative_closure_evidence_sha256(record)
    return record


def test_finite_negative_closure_binds_exact_identity_scope_checks_and_reading():
    record = _finite_negative()
    assert _registry()["language_scopes"]["ua"]["complete_for_negative_claims"] is False
    assert validate_research_record(record, _registry())["scope_status"] == "not_found_in_scope"
    for change in (
        {"owner": {"kind": "player", "id": 18}}, {"lang": "ru"}, {"source_lang": "zh"},
        {"reading": "別の読み"}, {"original_name": "別人"},
        {"source_checks": [record["source_checks"][0]]},
    ):
        with pytest.raises(EvidenceError):
            validate_research_record({**record, **change}, _registry())
    for change in ({"scope_id": "other"}, {"required_check_ids": ["professional"]},
                   {"registry_sha256": "0" * 64}, {"reviewer_id": record["producer_id"]}):
        bad = deepcopy(record)
        bad["negative_closure"].update(change)
        with pytest.raises(EvidenceError):
            validate_research_record(bad, _registry())


def test_finite_negative_closure_rejects_unfinished_and_unsupported_checks():
    record = _finite_negative()
    for change in ({"completeness": "partial"}, {"status": "unavailable"},
                   {"negative_outcome": "rejected_leads", "rejected_leads": []},
                   {"response_sha256": ""}):
        bad = deepcopy(record)
        bad["source_checks"][0].update(change)
        bad["negative_closure"]["evidence_sha256"] = negative_closure_evidence_sha256(bad)
        with pytest.raises(EvidenceError):
            validate_research_record(bad, _registry())


def test_finite_negative_closure_preserves_independently_rejected_leads():
    record = _finite_negative()
    check = record["source_checks"][0]
    check["negative_outcome"] = "rejected_leads"
    check["rejected_leads"] = [{
        "original_name": "Отеай", "candidate_name": "Отеай", "url": "https://example.org/forum",
        "body_sha256": "c" * 64, "body_excerpt": "Russian discussion of Отеай",
        "observed_lang": "ru", "language_basis": "reviewed_text",
        "rejection_basis": "Russian discussion, not Ukrainian usage",
        "reviewer_id": "lead-reviewer", "reviewer_model": "gpt-6-sol",
        "reviewed_at": "2026-10-02T10:30:00Z", "decision": "rejected_for_target_language",
    }]
    record["negative_closure"]["evidence_sha256"] = negative_closure_evidence_sha256(record)
    assert validate_research_record(record, _registry())["scope_status"] == "not_found_in_scope"
    late = deepcopy(record)
    late["source_checks"][0]["rejected_leads"][0]["reviewed_at"] = "2026-10-02T12:00:00Z"
    late["negative_closure"]["evidence_sha256"] = negative_closure_evidence_sha256(late)
    with pytest.raises(EvidenceError, match="lead review"):
        validate_research_record(late, _registry())
    for missing in ("original_name", "observed_lang", "rejection_basis", "decision", "body_excerpt"):
        bad = deepcopy(record)
        bad["source_checks"][0]["rejected_leads"][0].pop(missing)
        bad["negative_closure"]["evidence_sha256"] = negative_closure_evidence_sha256(bad)
        with pytest.raises(EvidenceError):
            validate_research_record(bad, _registry())


def test_finite_scope_records_foreign_language_pages_without_counting_them_as_target_searches():
    record = _finite_negative()
    foreign = deepcopy(record["source_checks"][0])
    foreign.update(check_id="russian-page", observed_lang="ru", query="Oteai on named Russian page",
                   url="https://example.org/pro-go-2", body_excerpt="Russian page has no Ukrainian Oteai term",
                   search_scope="Named Russian page body")
    record["source_checks"].append(foreign)
    record["negative_closure"]["required_check_ids"].append("russian-page")
    record["negative_closure"]["evidence_sha256"] = negative_closure_evidence_sha256(record)
    assert validate_research_record(record, _registry())["scope_status"] == "not_found_in_scope"
    record["source_checks"][0]["observed_lang"] = "ru"
    record["negative_closure"]["evidence_sha256"] = negative_closure_evidence_sha256(record)
    with pytest.raises(EvidenceError, match="target-language|target"):
        validate_research_record(record, _registry())


@pytest.mark.parametrize("product,expected", [("ua", "uk"), ("jp", "ja"), ("cn", "zh-Hans"), ("tw", "zh-Hant")])
def test_product_language_mapping(product, expected):
    assert product_language_tag(product, _registry()) == expected


def test_repository_source_registry_is_versioned_and_has_all_product_languages():
    registry = load_registry()
    assert registry["version"]
    assert set(registry["language_tags"]) == {"en", "cn", "tw", "jp", "ko", "de", "es", "fr", "ru", "tr", "ua"}
    assert set(registry["language_scopes"]) == set(registry["language_tags"])
    assert all(source["home_url"].startswith("https://") for source in registry["sources"])
    assert len(registry_sha256(registry)) == 64
    assert registry["language_scopes"]["ua"]["complete_for_negative_claims"] is False
    assert all(source["tier"] == "wikipedia_article" for source in registry["sources"]
               if source["id"].startswith("wikipedia-"))
    assert next(source for source in registry["sources"] if source["id"] == "wikidata")["tier"] == "discovery"
    assert [source["id"] for source in source_plan("ru", registry)] == [
        "rusgolib", "wikipedia-ru", "wikidata"]
    pilot_sources = {source["id"]: source for source in registry["sources"]}
    assert {pilot_sources[source_id]["tier"] for source_id in (
        "china-sport", "pts-tw", "baduk-mobile", "cyberoro", "centrocultural-sol",
        "gofed-be", "gomagic-ru", "go-school-tr", "asialogy-tr", "merdiven-go-tr"
    )} == {"official", "language_go", "reference"}


def test_source_plan_places_professional_references_before_discovery_leads():
    assert [source["id"] for source in source_plan("ru", _registry())] == ["ru-go", "wd"]


def test_found_record_stays_pending_and_uses_exact_owner_and_language():
    first = validate_research_record(_record(), _registry())
    second = validate_research_record(_record(owner={"kind": "player", "id": 18},
                                              source_checks=[_check(owner={"kind": "player", "id": 18})]), _registry())
    assert first["owner_key"] == "player:17:ru"
    assert second["owner_key"] == "player:18:ru"
    assert first["review_status"] == "pending"
    assert first["source_checks"][0]["observed_lang"] == "ru"
    with pytest.raises(EvidenceError, match="owner"):
        validate_research_record(_record(owner={"kind": "player", "id": 18}), _registry())


def test_record_is_bound_to_exact_registry_contents():
    with pytest.raises(EvidenceError, match="hash"):
        validate_research_record(_record(registry_sha256="0" * 64), _registry())


def test_completed_research_needs_original_name_language_and_reading_basis():
    for field in ("original_name", "original_language", "original_language_basis_url", "reading_basis_url"):
        with pytest.raises(EvidenceError, match="original|reading"):
            validate_research_record(_record(**{field: ""}), _registry())


@pytest.mark.parametrize("change", [
    {"body_excerpt": ""},
    {"body_sha256": ""},
    {"url": ""},
    {"observed_lang": "en"},
    {"observed_lang": "mul"},
    {"language_basis": "fallback"},
    {"http_status": 429},
    {"fetched_at": "tomorrow-ish"},
])
def test_a_found_name_requires_url_real_body_and_actual_target_language(change):
    with pytest.raises(EvidenceError):
        validate_research_record(_record(source_checks=[_check(**change)]), _registry())


def test_wikidata_mul_and_fallback_labels_are_only_discovery_leads():
    wd_check = _check("wd", url="https://www.wikidata.org/wiki/Q1", observed_lang="ru", label_lang="mul")
    with pytest.raises(EvidenceError):
        validate_research_record(_record(source_checks=[wd_check]), _registry())
    wd_check["label_lang"] = "ru"
    wd_check["fallback"] = True
    with pytest.raises(EvidenceError):
        validate_research_record(_record(source_checks=[wd_check]), _registry())


def test_discovery_hit_needs_a_separate_explicit_api_label_response():
    check = _check("wd", url="https://www.wikidata.org/wiki/Q1", label_lang="ru", fallback=False)
    with pytest.raises(EvidenceError, match="API label"):
        validate_research_record(_record(source_checks=[check]), _registry())
    label = {"language": "ru", "value": "Го Сэйгэн"}
    check["label_evidence"] = {
        "api_url": "https://www.wikidata.org/wiki/Special:EntityData/Q1.json",
        "fetched_at": "2026-10-02T10:01:00Z",
        "http_status": 200,
        "response_sha256": hashlib.sha256(json.dumps(label, ensure_ascii=False).encode()).hexdigest(),
        "body_excerpt": json.dumps(label, ensure_ascii=False),
        "json_pointer": "/entities/Q1/labels/ru",
        "label": label,
        "fallback": False,
    }
    assert validate_research_record(_record(source_checks=[check]), _registry())["review_status"] == "pending"
    check["observed_lang"] = "en"  # Wikidata page chrome may be English while its API label is Russian.
    assert validate_research_record(_record(source_checks=[check]), _registry())["review_status"] == "pending"
    check["observed_lang"] = "ru"
    for change in ({"language": "mul"}, {"value": "Go Seigen"}):
        bad = {**check, "label_evidence": {**check["label_evidence"], "label": {**label, **change}}}
        with pytest.raises(EvidenceError):
            validate_research_record(_record(source_checks=[bad]), _registry())
    bad = {**check, "label_evidence": {**check["label_evidence"], "fallback": True}}
    with pytest.raises(EvidenceError):
        validate_research_record(_record(source_checks=[bad]), _registry())
    bad = {**check, "label_evidence": {**check["label_evidence"], "body_excerpt": '{"language":"ru","value":"Wrong"}'}}
    with pytest.raises(EvidenceError):
        validate_research_record(_record(source_checks=[bad]), _registry())
    bad = {**check, "label_lang": "mul"}
    with pytest.raises(EvidenceError):
        validate_research_record(_record(source_checks=[bad]), _registry())
    bad = {**check, "label_evidence": {**check["label_evidence"],
                                       "api_url": "https://www.wikidata.org/wiki/Special:EntityData/Q2.json"}}
    with pytest.raises(EvidenceError, match="entity"):
        validate_research_record(_record(source_checks=[bad]), _registry())


def test_target_language_wikipedia_article_needs_revision_passage_and_separate_identity_source():
    registry = _registry()
    registry["sources"].append({"id": "ru-wp", "tier": "wikipedia_article",
                                "home_url": "https://ru.wikipedia.org/", "language": "ru"})
    passage = "Го Сэйгэн — профессиональный игрок го"
    article = _check("ru-wp", url="https://ru.wikipedia.org/wiki/Го_Сэйгэн",
                     article_evidence={"revision_id": "123456", "title": "Го Сэйгэн",
                                       "passage": passage,
                                       "passage_sha256": hashlib.sha256(passage.encode()).hexdigest(),
                                       "subject_identity": "Japanese name 呉清源 identifies this player"},
                     identity_corroboration={"source_id": "ru-go", "url": "https://example.org/go-seigen",
                                             "fetched_at": "2026-10-02T10:05:00Z", "http_status": 200,
                                             "body_sha256": hashlib.sha256(b"separate page").hexdigest(),
                                             "body_excerpt": "Professional archive: 呉清源, Go Seigen",
                                             "original_name": "呉清源",
                                             "identity_basis": "Same original name and career dates"})
    record = _record(registry_sha256=registry_sha256(registry), source_checks=[article])
    assert validate_research_record(record, registry)["review_status"] == "pending"
    for mutation in (
        {"article_evidence": {**article["article_evidence"], "revision_id": ""}},
        {"article_evidence": {**article["article_evidence"], "passage_sha256": "0" * 64}},
        {"identity_corroboration": {**article["identity_corroboration"], "original_name": "Another"}},
        {"identity_corroboration": {**article["identity_corroboration"], "url": article["url"]}},
    ):
        with pytest.raises(EvidenceError):
            validate_research_record({**record, "source_checks": [{**article, **mutation}]}, registry)


def test_not_found_requires_completed_defined_scope_and_documented_searches():
    no_hit = _check(status="not_found", candidate_name="", identity_basis="", body_excerpt="Search results, no matching player", search_scope="All indexed player results", scope_complete=True, negative_outcome="no_target_string")
    record = _record(scope_status="not_found_in_scope", candidate_name="", source_checks=[no_hit, _check("wd", status="not_found", candidate_name="", identity_basis="", url="https://www.wikidata.org/wiki/Q1", body_excerpt="Search results, no matching label", label_lang="ru", search_scope="Entity labels and aliases", scope_complete=True, negative_outcome="no_target_string")])
    assert validate_research_record(record, _registry())["scope_status"] == "not_found_in_scope"
    with pytest.raises(EvidenceError, match="scope"):
        validate_research_record({**record, "source_checks": [no_hit]}, _registry())
    incomplete = _registry()
    incomplete["language_scopes"]["ru"]["complete_for_negative_claims"] = False
    with pytest.raises(EvidenceError, match="scope"):
        validate_research_record({**record, "registry_sha256": registry_sha256(incomplete)}, incomplete)
    with pytest.raises(EvidenceError, match="scope"):
        validate_research_record({**record, "source_checks": [{**no_hit, "scope_complete": False}, record["source_checks"][1]]}, _registry())
    with pytest.raises(EvidenceError, match="outcome"):
        validate_research_record({**record, "source_checks": [{**no_hit, "negative_outcome": ""},
                                                        record["source_checks"][1]]}, _registry())


def test_negative_scope_distinguishes_reviewed_rejected_lead_from_no_string():
    lead = {"candidate_name": "Го Сэйгэн", "url": "https://example.org/lead",
            "body_sha256": hashlib.sha256(b"lead page").hexdigest(),
            "body_excerpt": "Found Го Сэйгэн but this profile describes another person",
            "rejection_basis": "Different birth date and original name",
            "reviewer_id": "independent-2", "reviewer_model": "gpt-6-sol",
            "reviewed_at": "2026-10-02T11:00:00Z"}
    rejected = _check(status="not_found", candidate_name="", identity_basis="",
                      body_excerpt="Search returned an ambiguous name", search_scope="All indexed profiles",
                      scope_complete=True, negative_outcome="rejected_leads", rejected_leads=[lead])
    wd = _check("wd", status="not_found", candidate_name="", identity_basis="",
                url="https://www.wikidata.org/wiki/Q1", body_excerpt="No target label",
                search_scope="All entity labels", scope_complete=True,
                negative_outcome="no_target_string")
    record = _record(scope_status="not_found_in_scope", candidate_name="", source_checks=[rejected, wd])
    assert validate_research_record(record, _registry())["scope_status"] == "not_found_in_scope"
    with pytest.raises(EvidenceError, match="rejected lead"):
        validate_research_record({**record, "source_checks": [{**rejected, "rejected_leads": []}, wd]}, _registry())


def test_unavailable_page_is_incomplete_not_absence():
    record = _record(scope_status="incomplete", candidate_name="", source_checks=[
        _check(status="unavailable", url="https://example.org/go-seigen", http_status=429, body_sha256="", body_excerpt="", candidate_name="", observed_lang="", language_basis=""),
    ])
    assert validate_research_record(record, _registry())["scope_status"] == "incomplete"
    with pytest.raises(EvidenceError):
        validate_research_record({**record, "scope_status": "not_found_in_scope"}, _registry())


def test_record_cannot_claim_approval_or_mix_owner_types():
    with pytest.raises(EvidenceError, match="pending"):
        validate_research_record(_record(review_status="approved"), _registry())
    with pytest.raises(EvidenceError, match="review"):
        validate_research_record(_record(reviewer_id="same-agent"), _registry())
    with pytest.raises(EvidenceError, match="owner"):
        validate_research_record(_record(owner={"kind": "player", "id": 17, "raw_player_id": 9}), _registry())


def test_research_can_bind_a_new_bundle_local_symbolic_owner_without_fake_db_id():
    owner = {"kind": "player", "ref": "go-seigen-1934"}
    linked_check = _check(owner=owner)
    validated = validate_research_record(_record(owner=owner, source_checks=[linked_check]), _registry())
    assert validated["owner_key"] == "player:@go-seigen-1934:ru"
    for invalid in ({"kind": "player", "ref": ""}, {"kind": "player", "ref": "go", "id": 17},
                    {"kind": "event", "ref": "../../escape"}):
        with pytest.raises(EvidenceError, match="owner"):
            validate_research_record(_record(owner=invalid, source_checks=[_check(owner=invalid)]), _registry())


def test_capture_cli_accepts_symbolic_owner_and_keeps_it_exact(tmp_path, monkeypatch):
    from scripts import kifu_name_research

    owner = {"kind": "player", "ref": "go-seigen-1934"}
    source = tmp_path / "tasks.jsonl"
    source.write_text(json.dumps({"owner": owner, "lang": "ru", "source_id": "ru-go",
                                  "query": "Go Seigen", "url": "https://example.org/go"}) + "\n", encoding="utf-8")
    monkeypatch.setattr(kifu_name_research, "capture_source_check",
                        lambda task, *_args, **_kwargs: {"owner": task["owner"], "status": "incomplete"})
    rows = list(kifu_name_research._capture_rows(source, _registry(), min_interval=0, max_attempts=1))
    assert rows[0]["owner"] == owner and rows[0]["source_check"]["owner"] == owner


def test_capture_retries_transient_error_and_never_infers_not_found():
    from email.message import Message
    from urllib.error import HTTPError

    calls = []
    pauses = []
    body = '<html lang="ru"><body>Го Сэйгэн — профессиональный игрок го</body></html>'.encode()

    class Response:
        status = 200
        url = "https://example.org/go-seigen"
        headers = Message()

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self, _limit):
            return body

    def open_url(_request, *, timeout):
        calls.append(timeout)
        if len(calls) == 1:
            raise HTTPError("https://example.org/go-seigen", 429, "Too many requests", Message(), None)
        return Response()

    task = {"owner": {"kind": "player", "id": 17}, "lang": "ru", "source_id": "ru-go", "query": "Go Seigen", "url": "https://example.org/go-seigen",
            "candidate_name": "Го Сэйгэн", "identity_basis": "Profile identifies Go Seigen"}
    found = capture_source_check(task, _registry(), open_url=open_url, sleep=pauses.append)
    assert found["status"] == "found"
    assert found["owner"] == task["owner"]
    assert found["observed_lang"] == "ru"
    assert found["body_sha256"] == hashlib.sha256(body).hexdigest()
    assert len(calls) == 2 and pauses == [1.0]
    no_candidate = capture_source_check({**task, "candidate_name": "Missing"}, _registry(), open_url=open_url)
    assert no_candidate["status"] == "incomplete"
    assert no_candidate["candidate_name"] == ""


def test_capture_rejects_page_language_fallback():
    from email.message import Message

    class Response:
        status = 200
        url = "https://example.org/go-seigen"
        headers = Message()

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self, _limit):
            return b'<html lang="en"><body>Go Seigen</body></html>'

    task = {"owner": {"kind": "player", "id": 17}, "lang": "ru", "source_id": "ru-go", "query": "Go Seigen", "url": "https://example.org/go-seigen",
            "candidate_name": "Go Seigen", "identity_basis": "Profile identifies Go Seigen"}
    check = capture_source_check(task, _registry(), open_url=lambda *_args, **_kw: Response())
    assert check["status"] == "incomplete"
    assert check["observed_lang"] == "en"


def test_discovery_html_language_does_not_prove_label_language_or_no_fallback():
    from email.message import Message

    class Response:
        status = 200
        url = "https://www.wikidata.org/wiki/Q1"
        headers = Message()

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self, _limit):
            return '<html lang="ru"><body>Го Сэйгэн</body></html>'.encode()

    task = {"owner": {"kind": "player", "id": 17}, "lang": "ru", "source_id": "wd", "query": "Go Seigen",
            "url": "https://www.wikidata.org/wiki/Q1", "candidate_name": "Го Сэйгэн",
            "identity_basis": "Entity Q1 is Go Seigen", "label_lang": "ru", "fallback": False}
    check = capture_source_check(task, _registry(), open_url=lambda *_args, **_kw: Response())
    assert check["status"] == "incomplete"
    assert "Го Сэйгэн" in check["body_excerpt"]
    assert "label_lang" not in check
    assert "fallback" not in check


def test_cli_validates_pending_jsonl_atomically(tmp_path):
    registry_path = tmp_path / "registry.json"
    source_path = tmp_path / "input.jsonl"
    output_path = tmp_path / "validated.jsonl"
    registry_path.write_text(json.dumps(_registry()), encoding="utf-8")
    source_path.write_text(json.dumps(_record(), ensure_ascii=False) + "\n", encoding="utf-8")
    assert main(["--registry", str(registry_path), "validate", "--input", str(source_path), "--output", str(output_path)]) == 0
    row = json.loads(output_path.read_text(encoding="utf-8"))
    assert row["owner_key"] == "player:17:ru"
    output_path.write_text("existing", encoding="utf-8")
    source_path.write_text(json.dumps(_record(review_status="approved")) + "\n", encoding="utf-8")
    with pytest.raises(EvidenceError):
        main(["--registry", str(registry_path), "validate", "--input", str(source_path), "--output", str(output_path)])
    assert output_path.read_text(encoding="utf-8") == "existing"
