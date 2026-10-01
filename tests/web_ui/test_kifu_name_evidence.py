"""Evidence discovery must never turn a search failure into an approved name."""

import hashlib
import json

import pytest

from katrain.web.kifu.name_evidence import (
    EvidenceError,
    capture_source_check,
    load_registry,
    product_language_tag,
    registry_sha256,
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


def test_not_found_requires_completed_defined_scope_and_documented_searches():
    no_hit = _check(status="not_found", candidate_name="", identity_basis="", body_excerpt="Search results, no matching player", search_scope="All indexed player results", scope_complete=True)
    record = _record(scope_status="not_found_in_scope", candidate_name="", source_checks=[no_hit, _check("wd", status="not_found", candidate_name="", identity_basis="", url="https://www.wikidata.org/wiki/Q1", body_excerpt="Search results, no matching label", label_lang="ru", search_scope="Entity labels and aliases", scope_complete=True)])
    assert validate_research_record(record, _registry())["scope_status"] == "not_found_in_scope"
    with pytest.raises(EvidenceError, match="scope"):
        validate_research_record({**record, "source_checks": [no_hit]}, _registry())
    incomplete = _registry()
    incomplete["language_scopes"]["ru"]["complete_for_negative_claims"] = False
    with pytest.raises(EvidenceError, match="scope"):
        validate_research_record({**record, "registry_sha256": registry_sha256(incomplete)}, incomplete)
    with pytest.raises(EvidenceError, match="scope"):
        validate_research_record({**record, "source_checks": [{**no_hit, "scope_complete": False}, record["source_checks"][1]]}, _registry())


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
