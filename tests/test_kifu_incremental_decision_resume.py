"""A completed finite review survives a later name-service failure unchanged."""

from copy import deepcopy
from hashlib import sha256

import pytest

from katrain.kifu_ingest import orchestration
from katrain.kifu_ingest.catalog import review_content_sha256, validate_decision
from katrain.kifu_ingest.names import NameRejected, NameServiceError, QwenNameService
from katrain.kifu_ingest.staging import Stage
from katrain.web.kifu.name_candidates import canonical_sha256


LANGUAGES = ("cn", "tw", "jp", "ko", "en")


def _stage_game(stage, source_id, *, black="Black", white="White", event="Match"):
    move = "aa" if int(source_id) % 2 else "ab"
    stage.remember({"id": source_id})
    stage.save_sgf(
        source_id,
        f"(;FF[4]GM[1]SZ[19]PB[{black}]PW[{white}]EV[{event}]DT[2026-02-01];B[{move}])",
    )
    return stage.manifest["items"][source_id]


def _mock_catalog(monkeypatch, *, unresolved_players=(), templates=None):
    monkeypatch.setattr(
        orchestration,
        "lookup_qualified_identities",
        lambda _engine, *, player_values, event_values: {
            "player": {
                raw: (
                    {"status": "unresolved"}
                    if raw in unresolved_players
                    else {"status": "qualified", "canonical_name": raw}
                )
                for raw in player_values
            },
            "event": {raw: {"status": "unresolved"} for raw in event_values},
        },
    )
    monkeypatch.setattr(orchestration, "qualified_raw_event_templates", lambda *a, **kw: {"templates": {}})
    monkeypatch.setattr(
        orchestration, "qualified_raw_player_templates", lambda *a, **kw: {"templates": deepcopy(templates or {})}
    )

    async def no_wiki(*args):
        return {"status": "unavailable", "sources": []}

    monkeypatch.setattr(orchestration, "wiki_sources", no_wiki)


def _qualified_target(request):
    return {
        "status": "checked",
        "request_sha256": canonical_sha256(request),
        "results": ["qualified"] * len(request["instructions"]),
    }


def _request(kind, key, members, context, sources):
    return {
        "kind": kind,
        "key": key,
        "source_items": deepcopy(members),
        "context": deepcopy(context),
        "template_sources": deepcopy(sources),
    }


class ReviewedNames:
    key = "fixture-only-no-provider"

    def __init__(self, label, *, on_translate=None, on_narrow=None):
        self.label = label
        self.on_translate = on_translate
        self.on_narrow = on_narrow
        self.calls = []
        self.narrow_calls = []
        self.issued = []

    async def translate_and_review(self, kind, key, members, *, sources, context):
        request = _request(kind, key, members, context, sources)
        self.calls.append(request)
        if self.on_translate:
            self.on_translate(request)
        candidate = {
            "displays": (context or {}).get("verified_reuse_displays", {lang: key for lang in LANGUAGES}),
            "methods": (context or {}).get("verified_reuse_methods", {lang: "retain_original" for lang in LANGUAGES}),
            "original_language": (context or {}).get("verified_reuse_original_language", "en"),
            "source_urls": [source["url"] for source in sources],
        }
        QwenNameService._candidate(candidate, kind, key, sources, context)
        request_id = f"{self.label}-{kind}-{key}-{len(self.calls)}"
        decision = {
            "kind": kind,
            "key": key,
            **{field: deepcopy(candidate[field]) for field in ("displays", "methods", "original_language")},
            "sources": deepcopy(sources),
            "source_items": deepcopy(members),
            "producer": {
                "id": "fixture-producer",
                "model": "fixture-model",
                "request_id": "producer-" + request_id,
                "at": "2026-10-01T00:00:00Z",
                "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
                "request_attempts": 1,
            },
        }
        decision["review"] = {
            "id": "fixture-independent-reviewer",
            "model": "fixture-model",
            "request_id": "reviewer-" + request_id,
            "at": "2026-10-01T00:00:01Z",
            "usage": {"prompt_tokens": 80, "completion_tokens": 20, "total_tokens": 100},
            "request_attempts": 1,
            "decision": "approve",
            "content_sha256": review_content_sha256(decision),
        }
        validate_decision(decision)
        self.issued.append(deepcopy(decision))
        return decision

    async def review_existing_decision(self, decision, members):
        self.narrow_calls.append((deepcopy(decision), deepcopy(members)))
        if self.on_narrow:
            self.on_narrow(decision, members)
        assert 0 < len(members) < len(decision["source_items"])
        narrowed = {**deepcopy(decision), "source_items": deepcopy(members)}
        narrowed["review"] = {
            **decision["review"],
            "request_id": f"narrow-{self.label}-{decision['key']}-{len(self.narrow_calls)}",
            "at": "2026-10-01T00:00:02Z",
            "content_sha256": review_content_sha256(narrowed),
        }
        validate_decision(narrowed)
        self.issued.append(deepcopy(narrowed))
        return narrowed


async def _prepare(items, stage, names, **kwargs):
    return await orchestration.prepare_staged_games(
        items,
        engine=object(),
        client=object(),
        names=names,
        check_identities=_qualified_target,
        decision_store=stage,
        **kwargs,
    )


@pytest.mark.asyncio
async def test_completed_event_review_persists_before_budget_failure_and_resumes_without_repay(tmp_path, monkeypatch):
    stage = Stage(tmp_path)
    items = [_stage_game(stage, "41", event="First Match"), _stage_game(stage, "42", event="Second Match")]
    _mock_catalog(monkeypatch)

    def stop_second(request):
        if request["key"] == "Second Match":
            # Check the real disk record while the original preparation is still
            # inside the second provider call, before it unwinds on the budget.
            assert Stage(tmp_path).load_name_decision(first.calls[0]) == first.issued[0]
            raise NameServiceError("budget")

    first = ReviewedNames("initial", on_translate=stop_second)
    with pytest.raises(NameServiceError, match="budget"):
        await _prepare(items, stage, first)
    completed = deepcopy(first.issued[0])
    assert [call["key"] for call in first.calls] == ["First Match", "Second Match"]
    assert Stage(tmp_path).load_name_decision(first.calls[0]) == completed

    def first_must_not_be_repaid(request):
        assert request["key"] == "Second Match"

    restarted = Stage(tmp_path)
    resumed = ReviewedNames("resumed", on_translate=first_must_not_be_repaid)
    manifest = await _prepare(restarted.items(), restarted, resumed)
    assert [call["key"] for call in resumed.calls] == ["Second Match"]
    assert manifest["decisions"][0] == completed
    assert manifest["decisions"][0]["producer"] == completed["producer"]
    assert manifest["decisions"][0]["review"] == completed["review"]
    assert len(manifest["games"]) == len(manifest["decisions"]) == 2
    assert all(validate_decision(decision) == decision for decision in manifest["decisions"])
    orchestration._validated(manifest)


@pytest.mark.asyncio
async def test_changed_finite_scope_or_verified_template_context_requires_fresh_review(tmp_path, monkeypatch):
    stage = Stage(tmp_path)
    first_item = _stage_game(stage, "51", black="Alice")
    source = {
        "url": "https://example.org/players/alice",
        "lang": "en",
        "title": "Fixture player record",
        "retrieved_at": "2026-09-30T00:00:00Z",
        "excerpt": "Alice",
        "content_sha256": sha256(b"Alice").hexdigest(),
    }
    templates = {
        "Alice": {
            "displays": {lang: "Alice" for lang in LANGUAGES},
            "methods": {lang: "retain_original" for lang in LANGUAGES},
            "original_language": "en",
            "sources": [source],
        }
    }
    _mock_catalog(monkeypatch, unresolved_players={"Alice"}, templates=templates)
    # The event is already covered; this case isolates player scope/template drift.
    monkeypatch.setattr(
        orchestration,
        "qualified_raw_event_templates",
        lambda *a, **kw: {"templates": {"Match": {"displays": {lang: "Match" for lang in LANGUAGES}}}},
    )
    original = ReviewedNames("original")
    first_manifest = await _prepare([first_item], stage, original)
    no_repayment = ReviewedNames("same", on_translate=lambda request: pytest.fail("exact review was paid again"))
    assert (await _prepare([first_item], Stage(tmp_path), no_repayment))["decisions"] == first_manifest["decisions"]

    second_item = _stage_game(stage, "52", black="Alice")
    expanded = ReviewedNames("expanded")
    expanded_manifest = await _prepare([first_item, second_item], stage, expanded)
    assert len(expanded.calls) == 1
    expanded_decision = expanded_manifest["decisions"][0]
    assert {member["source_item_id"] for member in expanded_decision["source_items"]} == {"51", "52"}
    assert expanded_decision["review"]["request_id"] != first_manifest["decisions"][0]["review"]["request_id"]

    templates["Alice"]["original_language"] = "und"
    templates["Alice"]["sources"][0]["url"] = "https://example.org/players/alice-revised"
    changed = ReviewedNames("new-template")
    changed_manifest = await _prepare([first_item, second_item], Stage(tmp_path), changed)
    assert len(changed.calls) == 1
    fresh = changed_manifest["decisions"][0]
    assert fresh["source_items"] == expanded_decision["source_items"]
    assert fresh["original_language"] == "und"
    assert fresh["sources"][0]["url"].endswith("alice-revised")
    assert fresh["review"]["request_id"] != expanded_decision["review"]["request_id"]
    assert validate_decision(fresh) == fresh
    orchestration._validated(changed_manifest)


@pytest.mark.asyncio
async def test_completed_narrowed_review_is_saved_before_later_narrowing_budget_failure(tmp_path, monkeypatch):
    stage = Stage(tmp_path)
    good = _stage_game(stage, "61", black="Alice", event="Shared Match")
    bad = _stage_game(stage, "62", black="Alice", white="Bad", event="Shared Match")
    _mock_catalog(monkeypatch, unresolved_players={"Alice", "Bad"})

    def reject_bad(request):
        if request["key"] == "Bad":
            raise NameRejected("bad name")

    def stop_later_narrow(decision, members):
        if decision["key"] == "Shared Match":
            narrowed_alice = first.issued[-1]
            assert narrowed_alice["key"] == "Alice"
            request = _request("raw_player", "Alice", narrowed_alice["source_items"], None, [])
            assert Stage(tmp_path).load_name_decision(request) == narrowed_alice
            raise NameServiceError("budget")

    first = ReviewedNames("initial", on_translate=reject_bad, on_narrow=stop_later_narrow)
    isolated = []
    with pytest.raises(NameServiceError, match="budget"):
        await _prepare([good, bad], stage, first, isolated=isolated)
    assert isolated == [("62", "bad name")]
    assert [decision["key"] for decision, _members in first.narrow_calls] == ["Alice", "Shared Match"]
    alice = deepcopy(first.issued[-1])
    assert [member["source_item_id"] for member in alice["source_items"]] == ["61"]
    assert alice["review"]["request_id"].startswith("narrow-")

    resumed = ReviewedNames(
        "resumed",
        on_translate=lambda request: pytest.fail("narrowed Alice paid again") if request["key"] == "Alice" else None,
    )
    manifest = await _prepare([good], Stage(tmp_path), resumed)
    assert [request["key"] for request in resumed.calls] == ["Shared Match"]
    assert manifest["decisions"][0] == alice
    assert [game["source_item_id"] for game in manifest["games"]] == ["61"]
    orchestration._validated(manifest)
