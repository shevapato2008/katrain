import asyncio
import json

import pytest

from katrain.kifu_ingest.staging import Stage, discover_and_download
from katrain.kifu_ingest.source_19x19 import SourceBudgetExceeded, SourceError, SourceRateLimited


SGF = "(;GM[1]FF[4]SZ[19];B[aa])"


class FakeSource:
    def __init__(self, pages, sgfs=None, failures=None):
        self.pages = pages
        self.sgfs = sgfs or {}
        self.failures = failures or {}
        self.page_calls = []
        self.sgf_calls = []

    async def fetch_page(self, page):
        self.page_calls.append(page)
        return self.pages.get(page, [])

    async def fetch_sgf(self, external_id):
        self.sgf_calls.append(external_id)
        if external_id in self.failures:
            raise self.failures[external_id]
        return self.sgfs.get(external_id, SGF)


def run(source, stage, known_ids=(), **kwargs):
    return asyncio.run(discover_and_download(source, stage, known_ids, **kwargs))


def test_first_known_does_not_hide_later_new_and_cross_page_duplicate(tmp_path):
    stage = Stage(tmp_path.resolve())
    source = FakeSource({0: [{"id": 1}, {"id": 2}], 1: [{"id": 2}, {"id": 3}], 2: []})
    result = run(source, stage, {"1"}, max_head_pages=2, max_rolling_pages=2)
    assert source.sgf_calls == ["2", "3"]
    assert {x["external_id"] for x in result["items"] if x["status"] == "downloaded"} == {"2", "3"}


def test_failed_download_is_persistent_and_retried_after_restart(tmp_path):
    stage = Stage(tmp_path.resolve())
    failed = FakeSource({0: [{"id": 4}]}, failures={"4": SourceError("temporary", retryable=True)})
    run(failed, stage, max_head_pages=1, max_rolling_pages=0)
    assert Stage(tmp_path.resolve()).items()[0]["status"] == "failed"
    recovered = FakeSource({0: []}, sgfs={"4": SGF})
    result = run(recovered, Stage(tmp_path.resolve()), {"4"}, max_head_pages=1, max_rolling_pages=0)
    assert recovered.sgf_calls == ["4"]
    assert result["items"][0]["status"] == "downloaded"


def test_failed_item_attempted_once_per_run_and_cannot_report_caught_up(tmp_path):
    stage = Stage(tmp_path.resolve())
    source = FakeSource(
        {0: [{"id": 13}], 1: [{"id": 13}], 2: []},
        failures={"13": SourceError("temporary", retryable=True)},
    )
    result = run(source, stage, max_head_pages=2, max_rolling_pages=3)
    assert source.sgf_calls == ["13"]
    assert result["status"] == "partial"
    assert stage.items()[0]["attempts"] == 1


def test_budget_returns_partial_and_keeps_pending_item(tmp_path):
    stage = Stage(tmp_path.resolve())
    source = FakeSource({0: [{"id": 5}, {"id": 6}]})
    result = run(source, stage, max_head_pages=1, max_rolling_pages=0, max_downloads=1)
    assert result["status"] == "partial"
    assert source.sgf_calls == ["5"]
    assert {x["external_id"] for x in stage.items()} == {"5", "6"}
    assert stage.items()[1]["status"] == "pending"


def test_source_budget_exhaustion_keeps_item_pending(tmp_path):
    stage = Stage(tmp_path.resolve())
    source = FakeSource({0: [{"id": 14}]}, failures={"14": SourceBudgetExceeded("budget")})
    result = run(source, stage, max_head_pages=1, max_rolling_pages=1)
    assert result["status"] == "partial"
    assert stage.items()[0]["status"] == "pending"
    assert stage.items()[0]["attempts"] == 0


def test_rate_limit_persists_utc_retry_time_and_skips_until_due(tmp_path):
    stage = Stage(tmp_path.resolve())
    stage.remember({"id": 15})
    now = [1000.0]
    limited = FakeSource({}, failures={"15": SourceRateLimited(120)})
    first = run(limited, stage, max_head_pages=0, max_rolling_pages=0, wall_clock=lambda: now[0])
    assert first["failures"] == 1
    assert Stage(tmp_path.resolve()).items()[0]["next_retry_at"] == 1120.0
    now[0] = 1119.0
    waiting = FakeSource({})
    run(waiting, Stage(tmp_path.resolve()), max_head_pages=0, max_rolling_pages=0, wall_clock=lambda: now[0])
    assert waiting.sgf_calls == []
    now[0] = 1120.0
    due = FakeSource({})
    run(due, Stage(tmp_path.resolve()), max_head_pages=0, max_rolling_pages=0, wall_clock=lambda: now[0])
    assert due.sgf_calls == ["15"]
    run(FakeSource({}), Stage(tmp_path.resolve()), max_head_pages=0, max_rolling_pages=0, wall_clock=lambda: now[0])


def test_list_business_error_is_reported_not_treated_as_empty_or_budget(tmp_path):
    class BrokenList(FakeSource):
        async def fetch_page(self, page):
            raise SourceError("source business error: 9")

    result = run(BrokenList({}), Stage(tmp_path.resolve()), max_head_pages=1, max_rolling_pages=1)
    assert result["status"] == "partial"
    assert result["failures"] == 1
    assert result["last_error"] == "source business error: 9"
    assert result["errors"] == [{"phase": "head", "page": 0, "error": "source business error: 9"}]


def test_page_budget_partial_has_no_source_failure(tmp_path):
    result = run(
        FakeSource({}), Stage(tmp_path.resolve()), max_head_pages=1, max_rolling_pages=1, deadline=0, clock=lambda: 0
    )
    assert result["status"] == "partial"
    assert result["failures"] == 0
    assert result["errors"] == []
    assert result["last_error"] is None


def test_rolling_cursor_resumes_with_overlap_and_empty_page_completes_pass(tmp_path):
    stage = Stage(tmp_path.resolve())
    source = FakeSource({0: [{"id": 7}], 1: [{"id": 8}], 2: [{"id": 9}], 3: []})
    first = run(source, stage, max_head_pages=1, max_rolling_pages=2)
    assert first["status"] == "partial"
    assert stage.manifest["rolling_cursor"] == 2
    second = run(source, Stage(tmp_path.resolve()), max_head_pages=1, max_rolling_pages=2)
    assert source.page_calls[-3:] == [0, 1, 2] or source.page_calls[-4:] == [0, 1, 2, 3]
    assert second["status"] == "partial"
    third = run(source, Stage(tmp_path.resolve()), max_head_pages=1, max_rolling_pages=2)
    assert third["status"] == "caught_up"


def test_same_id_changed_sgf_is_conflict_not_overwrite(tmp_path):
    stage = Stage(tmp_path.resolve())
    stage.remember({"id": 10})
    original = stage.save_sgf("10", SGF)
    with pytest.raises(ValueError, match="different"):
        stage.save_sgf("10", "(;GM[1]FF[4]SZ[19];W[bb])")
    assert original.read_bytes() == SGF.encode()


@pytest.mark.parametrize("external_id", ["../x", "/tmp/x", "1/2", "abc", "", "01\x00"])
def test_external_id_rejected(tmp_path, external_id):
    stage = Stage(tmp_path.resolve())
    with pytest.raises(ValueError):
        stage.remember({"id": external_id})


def test_symlink_target_rejected(tmp_path):
    stage = Stage(tmp_path.resolve())
    outside = tmp_path / "outside"
    outside.write_text("untouched")
    (tmp_path / "sgf" / "11.sgf").symlink_to(outside)
    stage.remember({"id": 11})
    with pytest.raises(ValueError):
        stage.save_sgf("11", SGF)
    assert outside.read_text() == "untouched"


def test_manifest_written_before_download_and_atomic_replace(tmp_path):
    stage = Stage(tmp_path.resolve())
    stage.remember({"id": 12, "pb": "原名"})
    content = json.loads((tmp_path / "manifest.json").read_text())
    assert content["items"]["12"]["metadata"]["pb"] == "原名"
    stage.save_sgf("12", SGF)
    assert not list(tmp_path.rglob("*.tmp"))
    assert (tmp_path / "sgf" / "12.sgf").read_bytes() == SGF.encode()
