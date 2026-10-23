import asyncio
from datetime import datetime, timedelta, timezone
import hashlib
import json

import pytest

from katrain.kifu_ingest import recent
from katrain.kifu_ingest.source_19x19 import SourceBudgetExceeded, SourceError, SourceRateLimited
from katrain.kifu_ingest.staging import Stage

SGF = "(;GM[1]FF[4]SZ[19];B[aa])"
NOW = datetime(2026, 10, 23, 0, 30, tzinfo=timezone.utc)
LEGACY = ("7923089", "7926016", "7928067", "7928304", "7929649", "7929673", "7929683")


def meta(i, when=NOW, **extra):
    local = when.astimezone(recent.SOURCE_TIMEZONE)
    return {
        "id": i,
        "pb": "Black",
        "pw": "White",
        "gamename": "Match",
        "playTime": {
            "date": {"year": local.year, "month": local.month, "day": local.day},
            "time": {"hour": local.hour, "minute": local.minute, "second": local.second},
        },
        **extra,
    }


class Source:
    def __init__(self, pages, failures=None, sgfs=None):
        self.pages, self.failures, self.sgfs = pages, failures or {}, sgfs or {}
        self.calls = []

    async def fetch_page(self, page):
        self.calls.append(("page", page))
        result = self.pages.get(page, [])
        if isinstance(result, Exception):
            raise result
        return result

    async def fetch_sgf(self, i):
        self.calls.append(("sgf", i))
        if i in self.failures:
            raise self.failures[i]
        return self.sgfs.get(i, SGF)


def run(source, stage, **kwargs):
    return asyncio.run(
        recent.discover_recent(source, stage, wall_clock=kwargs.pop("wall_clock", lambda: NOW.timestamp()), **kwargs)
    )


def test_legacy_seven_failures_never_block_head_and_later_page_new(tmp_path):
    stage = Stage(tmp_path.resolve())
    for i in LEGACY:
        stage.remember(meta(i, NOW - timedelta(days=2000)))
        stage.fail(i, SourceError("source business error: 7004"))
    stage.manifest["rolling_cursor"] = 1786
    source = Source({0: [meta(1, NOW - timedelta(days=8))], 1: [meta(2)]})
    result = run(source, stage, max_head_pages=2)
    assert source.calls == [("page", 0), ("page", 1), ("sgf", "2")]
    assert result["eligible_ids"] == ["2"]
    assert stage.manifest["rolling_cursor"] == 1786
    assert not set(LEGACY).intersection(result["eligible_ids"])


def test_window_boundaries_timezone_midnight_delayed_upload_unknown_and_dedup(tmp_path):
    entries = [
        meta(1, NOW - timedelta(days=7)),
        meta(2, NOW),
        meta(3, NOW - timedelta(days=7, seconds=1)),
        meta(4, NOW + timedelta(seconds=1)),
        meta(5, NOW - timedelta(hours=8), createTime={"anything": "late upload"}),
        {"id": 6},
        {**meta(7), "playTime": {"date": {"year": 2026, "month": 10, "day": 22}}},
        {**meta(8), "playTime": {"date": {"year": 2026, "month": 2, "day": 30}, "time": {}}},
    ]
    source = Source({0: entries, 1: [meta(1), meta(5)]})
    result = run(source, Stage(tmp_path.resolve()), max_head_pages=2)
    assert set(result["eligible_ids"]) == {"1", "2", "5"}
    assert len([c for c in source.calls if c == ("sgf", "1")]) == 1
    assert result["coverage"]["unknown_match_time"] == 3
    assert result["coverage"]["out_of_window"] == 2
    assert result["coverage"]["head_unique_ids"] == 8
    assert result["coverage"]["boundary_in_window"] is True
    assert result["status"] == "partial"  # A capped overlap is never whole-source caught_up.


def test_terminal_7004_and_invalid_sgf_not_retried_next_round(tmp_path):
    stage = Stage(tmp_path.resolve())
    source = Source(
        {0: [meta(1), meta(2), meta(3)]}, failures={"1": SourceError("missing", retryable=False)}, sgfs={"2": "not sgf"}
    )
    result = run(source, stage)
    assert result["eligible_ids"] == ["3"]
    assert set(result["quarantined_ids"]) == {"1", "2"}
    retry = Source({0: [meta(1), meta(2), meta(3)]})
    run(retry, Stage(tmp_path.resolve()))
    assert ("sgf", "1") not in retry.calls and ("sgf", "2") not in retry.calls


def test_429_defers_entire_source_without_bad_item_attempt(tmp_path):
    stage = Stage(tmp_path.resolve())
    source = Source({0: [meta(1), meta(2)]}, failures={"1": SourceRateLimited(120)})
    result = run(source, stage)
    assert result["deferred_until"] == NOW.timestamp() + 120
    assert stage.manifest["items"]["1"]["attempts"] == 0
    assert ("sgf", "2") not in source.calls
    waiting = Source({0: [meta(3)]})
    run(waiting, Stage(tmp_path.resolve()))
    assert waiting.calls == []


def test_cooldown_three_round_limit_does_not_block_other_games(tmp_path):
    stage = Stage(tmp_path.resolve())
    stamp = [NOW.timestamp()]
    for round_no, delta in enumerate((0, 300, 900), 1):
        stamp[0] = NOW.timestamp() + delta
        source = Source({0: [meta(1), meta(2)]}, failures={"1": SourceError("temporary")})
        result = run(source, stage, wall_clock=lambda: stamp[0])
        assert stage.manifest["items"]["1"]["attempts"] == round_no
        assert "2" in result["eligible_ids"]
        if round_no < 3:
            assert stage.manifest["items"]["1"]["next_retry_at"] == stamp[0] + 300 * 2 ** (round_no - 1)
            early = Source({0: [meta(1)]})
            run(early, stage, wall_clock=lambda: stamp[0] + 1)
            assert ("sgf", "1") not in early.calls
    assert stage.manifest["items"]["1"]["next_retry_at"] is None
    assert stage.manifest["items"]["1"]["recent"]["terminal"] is True


def test_shared_attempt_budget_continues_fairly_and_unpublished_unchanged_remains_eligible(tmp_path):
    stage = Stage(tmp_path.resolve())
    page = [meta(i) for i in range(1, 5)]
    first = run(Source({0: page}), stage, max_head_pages=1, max_downloads=2)
    assert first["eligible_ids"] == ["1", "2"]
    second_source = Source({0: page})
    second = run(second_source, Stage(tmp_path.resolve()), max_head_pages=1, max_downloads=2)
    assert [c[1] for c in second_source.calls if c[0] == "sgf"] == ["3", "4"]
    assert set(second["eligible_ids"]) == {"3", "4"}
    third = run(Source({0: page}), stage, max_head_pages=1, max_downloads=4)
    assert set(third["eligible_ids"]) == {"1", "2", "3", "4"}
    assert first["coverage"]["sgf_attempt_cap"] is True


def test_published_baseline_and_counter_changes_never_become_imports(tmp_path):
    stage = Stage(tmp_path.resolve())
    first = run(Source({0: [meta(1, analyzeCount=1)]}), stage, published_ids={"1"})
    assert first["eligible_ids"] == []
    assert stage.manifest["items"]["1"]["recent"]["raw_sha256"] == hashlib.sha256(SGF.encode()).hexdigest()
    second = run(Source({0: [meta(1, analyzeCount=7, favouriteCount=20)]}), stage, published_ids={"1"})
    assert second["changed_ids"] == [] and second["eligible_ids"] == []


@pytest.mark.parametrize("change", ["sgf", "metadata"])
def test_same_id_change_retains_original_success_and_both_evidence(tmp_path, change):
    stage = Stage(tmp_path.resolve())
    original_meta = meta(1)
    stage.remember(original_meta)
    original_path = stage.save_sgf("1", SGF)
    stage.manifest["items"]["1"]["status"] = "success"
    stage._persist()
    new_meta = meta(1, gamename="Corrected") if change == "metadata" else original_meta
    new_sgf = "(;GM[1]SZ[19];W[bb])" if change == "sgf" else SGF
    source = Source({0: [new_meta]}, sgfs={"1": new_sgf})
    result = run(source, stage, published_ids={"1"})
    item = stage.manifest["items"]["1"]
    assert result["changed_ids"] == result["quarantined_ids"] == ["1"]
    assert item["status"] == "success" and item["metadata"] == original_meta
    assert original_path.read_text() == SGF
    evidence = json.loads((stage.root / item["recent"]["change_evidence"]).read_text())
    assert evidence["before"]["metadata"] == original_meta
    assert evidence["after"]["metadata"] == new_meta
    if change == "sgf":
        assert evidence["after"]["raw_sha256"] == hashlib.sha256(new_sgf.encode()).hexdigest()
        assert (stage.root / evidence["after"]["raw_sgf_path"]).read_text() == new_sgf
    else:
        assert evidence["after"]["raw_sha256"] is None
        assert evidence["after"]["raw_sgf_path"] is None
        assert not any(phase == "sgf" for phase, _ in source.calls)
    again = Source({0: [new_meta]})
    run(again, stage, published_ids={"1"})
    assert not any(c[0] == "sgf" for c in again.calls)


def test_bounded_absent_head_rechecks_and_fair_order(tmp_path):
    stage = Stage(tmp_path.resolve())
    run(Source({0: [meta(i) for i in range(1, 25)]}), stage)
    source = Source({0: [meta(30)]})
    result = run(source, stage, published_ids={str(i) for i in range(1, 25)})
    assert source.calls[0] == ("page", 0)
    assert len([c for c in source.calls if c[0] == "sgf"]) == 21
    assert result["coverage"]["recheck_selected"] == 20
    assert result["eligible_ids"] == ["30"]
    assert result["coverage"]["recheck_deferred"] == 4


def test_bounded_lookup_occurs_after_head_and_only_for_candidates(tmp_path):
    source = Source({0: [meta(1)], 1: [meta(2)]})
    observed = []

    def lookup(ids):
        observed.append((ids, list(source.calls)))
        return {"1"}

    result = run(source, Stage(tmp_path.resolve()), max_head_pages=2, published_lookup=lookup)
    assert observed == [({"1", "2"}, [("page", 0), ("page", 1)])]
    assert result["eligible_ids"] == ["2"]


@pytest.mark.parametrize(
    "kwargs",
    [{"max_head_pages": 11}, {"max_downloads": 101}, {"window_days": 15}, {"max_requests": 241}, {"max_rechecks": 21}],
)
def test_hard_caps_rejected(tmp_path, kwargs):
    with pytest.raises(ValueError):
        run(Source({}), Stage(tmp_path.resolve()), **kwargs)


def test_source_budget_does_not_count_item_failure_and_deadline_wraps_wait(tmp_path):
    stage = Stage(tmp_path.resolve())
    result = run(Source({0: [meta(1)]}, failures={"1": SourceBudgetExceeded("cap")}), stage)
    assert result["coverage"]["source_budget_exhausted"] is True
    assert stage.manifest["items"]["1"]["attempts"] == 0

    class Slow(Source):
        async def fetch_page(self, page):
            await asyncio.sleep(1)
            return []

    result = run(Slow({}), stage, deadline=__import__("time").monotonic() + 0.02)
    assert result["coverage"]["time_budget_exhausted"] is True


def test_manual_preparation_quarantine_remains_terminal_next_round(tmp_path):
    from katrain.kifu_ingest.preparation import derive_metadata

    stage = Stage(tmp_path.resolve())
    run(Source({0: [meta(1)]}), stage)
    with pytest.raises(ValueError, match="conflicts") as failure:
        derive_metadata("(;PB[Different]PW[White]EV[Match];B[aa])", meta(1))

    class PermanentPreparationError(ValueError):
        retryable = False

    stage.fail("1", PermanentPreparationError(str(failure.value)))
    source = Source({0: [meta(1)]})
    result = run(source, stage)
    assert source.calls == [("page", 0), ("page", 1)]
    assert result["eligible_ids"] == []
    assert result["quarantined_ids"] == ["1"]


def test_excluded_ids_are_never_fetched_or_prepared(tmp_path):
    source = Source({0: [meta(1), meta(2)]})
    result = run(source, Stage(tmp_path.resolve()), excluded_ids={"1"})
    assert ("sgf", "1") not in source.calls
    assert result["eligible_ids"] == ["2"]


def test_no_sgf_budget_does_not_prepare_unobserved_existing_raw(tmp_path):
    stage = Stage(tmp_path.resolve())
    stage.remember(meta(1))
    stage.save_sgf("1", SGF)
    result = run(Source({0: [meta(1)]}), stage, max_downloads=0)
    assert result["eligible_ids"] == []


def test_real_source_http_ceiling_is_shared_by_head_and_sgf(tmp_path):
    import httpx
    from katrain.kifu_ingest.source_19x19 import Source19x19

    calls = []

    def handle(req):
        calls.append(req)
        data = {"gameMetaList": [meta(1), meta(2)]} if req.method == "GET" else {"sgf": SGF}
        return httpx.Response(200, json={"code": 0, "data": data})

    async def check():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
            source = Source19x19(client, list_interval=(0, 0), sgf_interval=(0, 0))
            result = await recent.discover_recent(
                source, Stage(tmp_path.resolve()), max_head_pages=2, max_requests=3, wall_clock=lambda: NOW.timestamp()
            )
            assert source.requests == 3
            assert result["eligible_ids"] == ["1"]
            assert result["coverage"]["source_budget_exhausted"] is True
            assert result["coverage"]["source_http_attempts"] == 3

    asyncio.run(check())
    assert len(calls) == 3


def test_failures_consume_attempt_budget_but_no_failure_streak_aborts_valid_game(tmp_path):
    bad = {str(i): SourceError("transient") for i in range(1, 8)}
    source = Source({0: [meta(i) for i in range(1, 9)]}, failures=bad)
    result = run(source, Stage(tmp_path.resolve()), max_downloads=8)
    assert result["eligible_ids"] == ["8"]
    assert result["coverage"]["sgf_attempts"] == 8
    limited = run(
        Source({0: [meta(i) for i in range(1, 9)]}, failures=bad),
        Stage((tmp_path / "limited").resolve()),
        max_downloads=2,
    )
    assert limited["coverage"]["sgf_attempts"] == 2
    assert limited["coverage"]["sgf_attempt_cap"] is True


def test_persistent_absent_last_checked_rotates_across_rounds(tmp_path):
    stage = Stage(tmp_path.resolve())
    run(Source({0: [meta(i) for i in range(1, 25)]}), stage)
    published = {str(i) for i in range(1, 25)}
    first = Source({})
    run(first, stage, published_ids=published, wall_clock=lambda: NOW.timestamp() + 60)
    second = Source({})
    run(second, Stage(tmp_path.resolve()), published_ids=published, wall_clock=lambda: NOW.timestamp() + 120)
    checked_first = {i for phase, i in first.calls if phase == "sgf"}
    checked_second = [i for phase, i in second.calls if phase == "sgf"]
    assert not set(checked_second[:4]).intersection(checked_first)


def test_terminal_candidate_is_reported_even_when_new_candidate_exhausts_budget(tmp_path):
    stage = Stage(tmp_path.resolve())
    run(Source({0: [meta(1)]}, failures={"1": SourceError("missing", retryable=False)}), stage)
    result = run(Source({0: [meta(2), meta(1)]}), stage, max_downloads=0)
    assert result["quarantined_ids"] == ["1"]


@pytest.mark.parametrize("budget,sgf_error", [(100, SourceError("temporary")), (0, None)])
def test_metadata_change_is_saved_before_sgf_failure_or_budget_deferral(tmp_path, budget, sgf_error):
    stage = Stage(tmp_path.resolve())
    original = meta(1)
    stage.remember(original)
    raw_path = stage.save_sgf("1", SGF)
    stage.manifest["items"]["1"]["status"] = "success"
    stage._persist()
    updated = meta(1, gamename="Corrected")
    source = Source({0: [updated]}, failures={"1": sgf_error} if sgf_error else {})
    result = run(source, stage, published_ids={"1"}, max_downloads=budget)
    saved = Stage(stage.root).manifest["items"]["1"]
    assert result["candidate_ids"] == ["1"]
    assert result["changed_ids"] == result["quarantined_ids"] == ["1"]
    assert not any(phase == "sgf" for phase, _ in source.calls)
    assert saved["status"] == "success" and saved["metadata"] == original
    assert raw_path.read_text() == SGF
    assert saved["recent"]["seen_metadata"] == updated
    evidence = json.loads((stage.root / saved["recent"]["change_evidence"]).read_text())
    assert evidence["before"]["metadata"] == original
    assert evidence["before"]["raw_sha256"] == hashlib.sha256(SGF.encode()).hexdigest()
    assert evidence["after"]["metadata"] == updated
    assert evidence["after"]["raw_sha256"] is None
    assert evidence["after"]["raw_sgf_path"] is None
    assert evidence["after"]["raw_status"] == "not_fetched"


def test_new_and_unchanged_metadata_is_durable_before_sgf_request(tmp_path):
    stage = Stage(tmp_path.resolve())
    run(Source({0: [meta(1)]}), stage)
    changed_counters = meta(1, analyzeCount=100)
    new_metadata = meta(2)

    class AssertDurable(Source):
        async def fetch_sgf(self, external_id):
            saved = Stage(stage.root).manifest["items"]
            assert saved["1"]["recent"]["seen_metadata"] == changed_counters
            assert saved["2"]["recent"]["seen_metadata"] == new_metadata
            assert saved["1"]["metadata"] == meta(1)
            return await super().fetch_sgf(external_id)

    run(AssertDurable({0: [changed_counters, new_metadata]}), stage)
    deferred = run(Source({0: [meta(3)]}), stage, max_downloads=0)
    assert deferred["candidate_ids"] == ["3", "1", "2"]
    saved = Stage(stage.root).manifest["items"]["3"]
    assert saved["recent"]["seen_metadata"] == meta(3)
    assert saved["recent"]["seen_metadata_sha256"] == recent.metadata_sha256(meta(3))


@pytest.mark.parametrize(
    "head_error", [SourceRateLimited(120), SourceBudgetExceeded("source request budget exhausted")]
)
def test_partial_head_never_treats_unresolved_published_item_as_unpublished(tmp_path, head_error):
    stage = Stage(tmp_path.resolve())
    run(Source({0: [meta(1)]}), stage)
    original = stage.manifest["items"]["1"].copy()
    lookup_calls = []

    def lookup(ids):
        lookup_calls.append(ids)
        return {"1"}

    result = run(Source({0: [meta(1)], 1: head_error}), stage, published_lookup=lookup)
    assert result["eligible_ids"] == []
    assert result["coverage"]["publication_authority_complete"] is False
    assert result["status"] == "partial"
    assert lookup_calls == []
    assert result["candidate_ids"] == ["1"]
    assert stage.manifest["items"]["1"]["status"] == original["status"]
    assert stage.manifest["items"]["1"]["raw_sha256"] == original["raw_sha256"]


def test_publication_lookup_deadline_returns_partial_and_keeps_scanned_metadata(tmp_path):
    import time

    stage = Stage(tmp_path.resolve())

    async def lookup(ids):
        await asyncio.sleep(1)
        return {"1"}

    source = Source({0: [meta(1)]})
    result = run(source, stage, max_head_pages=1, published_lookup=lookup, deadline=time.monotonic() + 0.02)
    assert result["status"] == "partial"
    assert result["eligible_ids"] == []
    assert result["coverage"]["publication_authority_complete"] is False
    assert result["coverage"]["time_budget_exhausted"] is True
    saved = Stage(stage.root).manifest["items"]["1"]
    assert saved["recent"]["seen_metadata"] == meta(1)
    assert saved["status"] == "pending"
    assert not any(phase == "sgf" for phase, _ in source.calls)


def test_existing_unpublished_raw_waits_for_current_successful_recheck(tmp_path):
    stage = Stage(tmp_path.resolve())
    run(Source({0: [meta(1)]}), stage)
    deferred = run(Source({0: [meta(1)]}), stage, max_downloads=0)
    assert deferred["eligible_ids"] == []
    assert deferred["checked_ids"] == []
    assert Stage(stage.root).manifest["items"]["1"]["raw_sha256"]
    continued = run(Source({0: [meta(1)]}), Stage(stage.root), max_downloads=1)
    assert continued["checked_ids"] == ["1"]
    assert continued["eligible_ids"] == ["1"]
