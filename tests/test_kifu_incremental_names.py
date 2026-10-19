import asyncio
import json
from hashlib import sha256

import httpx
import pytest

from katrain.kifu_ingest.names import NeedsCredentials, NameRejected, NameServiceError, QwenNameService, wiki_sources


ITEM = {"source_key": "19x19", "source_item_id": "123", "slot": "black", "sgf_sha256": "a" * 64}
CANDIDATE = {
    "displays": {"cn": "柯洁", "tw": "柯潔", "jp": "柯潔", "ko": "커제", "en": "Ke Jie"},
    "original_language": "cn",
    "methods": {
        "cn": "retain_original",
        "tw": "orthographic_conversion",
        "jp": "retain_original",
        "ko": "transliteration",
        "en": "transliteration",
    },
    "source_urls": [],
}


def run(coro):
    return asyncio.run(coro)


def qwen_reply(content, request_id):
    return httpx.Response(
        200,
        json={
            "id": request_id,
            "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
            "choices": [{"message": {"content": json.dumps(content, ensure_ascii=False)}}],
        },
    )


def mock_service(replies, **kwargs):
    calls = []

    def handle(request):
        calls.append(request)
        answer = replies.pop(0)
        return answer if isinstance(answer, httpx.Response) else qwen_reply(answer, f"response-{len(calls)}")

    client = httpx.AsyncClient(transport=httpx.MockTransport(handle))
    return (
        QwenNameService(client, key="test-secret", max_total_tokens=kwargs.pop("max_total_tokens", 10000), **kwargs),
        client,
        calls,
    )


def test_two_distinct_requests_produce_catalog_decision_and_hash():
    from katrain.kifu_ingest.catalog import review_content_sha256, validate_decision

    service, client, calls = mock_service([CANDIDATE, {"decision": "approve"}])

    async def check():
        async with client:
            return await service.translate_and_review("player", "柯洁", [ITEM])

    result = run(check())
    assert validate_decision(result) == result
    assert result["review"]["content_sha256"] == review_content_sha256(result)
    assert result["producer"]["request_id"] != result["review"]["request_id"]
    assert len(calls) == 2
    assert all(c.headers["authorization"] == "Bearer test-secret" for c in calls)
    assert json.loads(calls[0].content)["response_format"] == {"type": "json_object"}
    assert json.loads(calls[0].content)["max_tokens"] == 1024
    assert result["producer"]["usage"]["total_tokens"] == 150
    assert result["review"]["usage"]["total_tokens"] == 150
    assert result["producer"]["request_attempts"] == 1


def test_event_producer_prompt_lists_exact_digit_tokens_for_every_language():
    key = "第12届国手山脉杯世界赛8强赛"
    candidate = {
        "displays": {lang: f"{key} ({lang} 12 8)" for lang in ("cn", "tw", "jp", "ko", "en")},
        "original_language": "cn",
        "methods": {lang: "translation" for lang in ("cn", "tw", "jp", "ko", "en")},
        "source_urls": [],
    }
    candidate["displays"]["cn"] = key
    candidate["methods"]["cn"] = "retain_original"
    service, client, calls = mock_service([candidate, {"decision": "approve"}])

    async def check():
        async with client:
            await service.translate_and_review("raw_event", key, [{**ITEM, "slot": "event"}])

    run(check())
    body = json.loads(calls[0].content)
    prompt = json.loads(body["messages"][1]["content"])
    assert prompt["required_digit_tokens"] == ["12", "8"]
    assert "Each of cn, tw, jp, ko and en" in prompt["digit_rule"]
    assert "12" in prompt["digit_rule"] and "8" in prompt["digit_rule"]
    assert "original" in prompt["digit_rule"]
    assert prompt["required_cn_literal"] == key
    assert "character for character" in prompt["cn_literal_rule"]
    assert prompt["output_shape"]["displays"] == ["cn", "tw", "jp", "ko", "en"]
    assert set(prompt["allowed_methods"]) == {
        "retain_original", "orthographic_conversion", "transliteration", "translation"
    }
    assert "required_digit_tokens literally" in body["messages"][0]["content"]


def test_token_budget_stops_before_another_paid_request():
    service, client, calls = mock_service([CANDIDATE, {"decision": "approve"}], max_total_tokens=1200)

    async def check():
        async with client:
            await service.translate_and_review("player", "柯洁", [ITEM])
            with pytest.raises(NameServiceError, match="token budget"):
                await service.translate_and_review("player", "柯洁", [ITEM])

    run(check())
    assert len(calls) == 2
    assert service.tokens_used == 300


def test_reservation_happens_before_http_and_unknown_charge_is_retained():
    events = []

    def handle(request):
        events.append("http")
        return httpx.Response(429)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handle))

    def reserve(amount):
        events.append(("reserve", amount))
        if len(events) > 2:
            raise NameServiceError("Qwen token budget exhausted")
        return "reservation-1"

    async def check():
        async with client:
            with pytest.raises(NameServiceError, match="token budget"):
                await QwenNameService(
                    client,
                    key="test-secret",
                    max_total_tokens=100000,
                    reserve_call=reserve,
                    settle_call=lambda *_: pytest.fail("unknown usage must retain reservation"),
                ).translate_and_review("player", "柯洁", [ITEM])

    run(check())
    assert events[0][0] == "reserve" and events[0][1] > 1024
    assert events[1] == "http"
    assert len(events) == 3


def test_narrowed_scope_uses_fresh_independent_review_without_regeneration():
    from katrain.kifu_ingest.catalog import review_content_sha256, validate_decision

    second = {**ITEM, "source_item_id": "124"}
    decision = {
        "kind": "raw_player",
        "key": "柯洁",
        "displays": CANDIDATE["displays"],
        "methods": CANDIDATE["methods"],
        "original_language": "cn",
        "sources": [],
        "source_items": [ITEM, second],
        "producer": {
            "id": "qwen-producer",
            "model": "qwen-plus",
            "request_id": "old-producer",
            "at": "2026-10-19T00:00:00Z",
        },
    }
    decision["review"] = {
        "id": "qwen-reviewer",
        "model": "qwen-plus",
        "request_id": "old-review",
        "at": "2026-10-19T00:00:01Z",
        "decision": "approve",
        "content_sha256": review_content_sha256(decision),
    }
    service, client, calls = mock_service([{"decision": "approve"}])

    async def check():
        async with client:
            return await service.review_existing_decision(decision, [ITEM])

    narrowed = run(check())
    assert validate_decision(narrowed) == narrowed
    assert narrowed["source_items"] == [ITEM]
    assert narrowed["producer"] == decision["producer"]
    assert narrowed["review"]["request_id"] != decision["review"]["request_id"]
    assert len(calls) == 1
    assert json.loads(json.loads(calls[0].content)["messages"][1]["content"])["source_items"] == [ITEM]


def test_actual_attempts_and_usage_are_audited_including_retry():
    audit = []
    service, client, calls = mock_service(
        [httpx.Response(429), CANDIDATE, {"decision": "approve"}],
        audit_call=lambda entry: audit.append(entry),
    )

    async def check():
        async with client:
            return await service.translate_and_review("player", "柯洁", [ITEM])

    decision = run(check())
    assert decision["producer"]["request_attempts"] == 2
    assert [entry["status_code"] for entry in audit] == [429, 200, 200]
    assert audit[1]["usage"]["total_tokens"] == 150
    assert len(calls) == 3


def test_missing_key_makes_no_http_request():
    calls = []
    client = httpx.AsyncClient(transport=httpx.MockTransport(lambda request: calls.append(request)))

    async def check():
        async with client:
            with pytest.raises(NeedsCredentials):
                await QwenNameService(client, key="").translate_and_review("player", "柯洁", [ITEM])

    run(check())
    assert not calls


def test_missing_token_budget_makes_no_http_request():
    calls = []
    client = httpx.AsyncClient(transport=httpx.MockTransport(lambda request: calls.append(request)))

    async def check():
        async with client:
            with pytest.raises(NameServiceError, match="token budget"):
                await QwenNameService(client, key="test-secret").translate_and_review("player", "柯洁", [ITEM])

    run(check())
    assert not calls


@pytest.mark.parametrize(
    "candidate",
    [
        {**CANDIDATE, "displays": {**CANDIDATE["displays"], "en": ""}},
        httpx.Response(200, json={"id": "bad", "choices": [{"message": {"content": "{broken"}}]}),
        httpx.Response(200, json={"id": "cut", "choices": [{"finish_reason": "length", "message": {"content": "{}"}}]}),
        {**CANDIDATE, "source_urls": ["https://invented.example/person"]},
    ],
)
def test_invalid_producer_fails_closed(candidate):
    service, client, calls = mock_service([candidate, candidate])

    async def check():
        async with client:
            with pytest.raises(NameRejected):
                await service.translate_and_review("player", "柯洁", [ITEM])

    run(check())
    assert len(calls) <= 2


def test_rejected_review_fails_closed_after_at_most_one_repair():
    service, client, calls = mock_service([CANDIDATE, {"decision": "reject"}, CANDIDATE, {"decision": "reject"}])

    async def check():
        async with client:
            with pytest.raises(NameRejected):
                await service.translate_and_review("player", "柯洁", [ITEM])

    run(check())
    assert len(calls) == 4
    repaired_prompt = json.loads(calls[2].content)["messages"][1]["content"]
    assert "independent review rejected" in repaired_prompt


@pytest.mark.parametrize("status", [401, 402])
def test_auth_and_billing_fail_without_retry_or_logging_key(status, caplog):
    service, client, calls = mock_service([httpx.Response(status, json={"message": "test-secret"})])

    async def check():
        async with client:
            with pytest.raises(NameServiceError):
                await service.translate_and_review("player", "柯洁", [ITEM])

    run(check())
    assert len(calls) == 1
    assert "test-secret" not in caplog.text


def test_rate_limit_has_finite_retry():
    service, client, calls = mock_service([httpx.Response(429), httpx.Response(429)])

    async def check():
        async with client:
            with pytest.raises(NameServiceError):
                await service.translate_and_review("player", "柯洁", [ITEM])

    run(check())
    assert len(calls) == 2


def test_item_budget_refuses_excess_before_http():
    service, client, calls = mock_service([CANDIDATE, {"decision": "approve"}], max_items=1)

    async def check():
        async with client:
            await service.translate_and_review("player", "柯洁", [ITEM])
            with pytest.raises(NameServiceError, match="budget"):
                await service.translate_and_review("player", "柯洁", [ITEM])

    run(check())
    assert len(calls) == 2


def test_source_evidence_is_preserved_and_unknown_url_rejected():
    excerpt = "Ke Jie is a Chinese professional Go player."
    source = {
        "url": "https://en.wikipedia.org/wiki/Ke_Jie",
        "lang": "en",
        "title": "Ke Jie",
        "retrieved_at": "2026-10-18T00:00:00+00:00",
        "excerpt": excerpt,
        "content_sha256": sha256(excerpt.encode()).hexdigest(),
    }
    candidate = {**CANDIDATE, "source_urls": [source["url"]]}
    service, client, _ = mock_service([candidate, {"decision": "approve"}])

    async def check():
        async with client:
            return await service.translate_and_review("player", "柯洁", [ITEM], sources=[source])

    result = run(check())
    assert result["sources"] == [source]


def test_wikipedia_sources_are_real_search_and_langlink_results():
    calls = []

    def handle(request):
        calls.append(request)
        if request.url.params.get("list") == "search":
            return httpx.Response(
                200, json={"query": {"search": [{"title": "Ke Jie", "snippet": "Chinese Go player"}]}}
            )
        return httpx.Response(
            200,
            json={
                "query": {"pages": {"12": {"langlinks": [{"lang": "ja", "*": "柯潔"}, {"lang": "ko", "*": "커제"}]}}}
            },
        )

    async def check():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
            return await wiki_sources("柯洁", client, languages=("en",))

    result = run(check())
    assert result["status"] == "available"
    assert len(calls) == 2
    assert {s["lang"] for s in result["sources"]} == {"en", "ja", "ko"}
    assert all(s["content_sha256"] == sha256(s["excerpt"].encode()).hexdigest() for s in result["sources"])
    assert result["sources"][0]["url"] == "https://en.wikipedia.org/wiki/Ke_Jie"


def test_wikipedia_error_is_marked_unavailable():
    def handle(request):
        raise httpx.RemoteProtocolError("down")

    async def check():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
            return await wiki_sources("柯洁", client, languages=("en",))

    result = run(check())
    assert result == {"status": "unavailable", "sources": []}


def test_chinese_orthographic_conversion_requires_explanation():
    converted = {
        **CANDIDATE,
        "displays": {**CANDIDATE["displays"], "cn": "柯洁"},
        "methods": {**CANDIDATE["methods"], "cn": "orthographic_conversion"},
        "cn_conversion_note": "Traditional 潔 is simplified as 洁.",
    }
    service, client, calls = mock_service([converted, {"decision": "approve"}])

    async def check():
        async with client:
            return await service.translate_and_review("player", "柯潔", [ITEM])

    result = run(check())
    assert result["displays"]["cn"] == "柯洁"
    assert len(calls) == 2


def test_invalid_source_binding_spends_no_model_requests():
    service, client, calls = mock_service([])

    async def check():
        async with client:
            with pytest.raises(ValueError, match="source_items"):
                await service.translate_and_review("player", "柯洁", [{**ITEM, "sgf_sha256": "bad"}])

    run(check())
    assert not calls
