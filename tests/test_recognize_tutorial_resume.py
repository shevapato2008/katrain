"""Interrupted recognition keeps detection-only figures pending; all writes isolated."""

from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

APP = Path(__file__).parents[1]
spec = importlib.util.spec_from_file_location("catalog_resume", APP / "scripts/recognize_tutorial_book.py")
r = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r)
FIXTURE = APP / "tests/data/recognition_resume_ko.json"


def states():
    assert (
        hashlib.sha256(FIXTURE.read_bytes()).hexdigest()
        == "7d09841198c879c5c3477a6dd86cf1f9df06843886104e545bd1e899109fc2fa"
    )
    return json.loads(FIXTURE.read_text())


def assemble_fixture(tmp_path, monkeypatch, pending):
    fixture = states()
    complete = fixture["complete_state"]
    source = {
        **fixture["source_metadata"],
        "pages": [deepcopy(s["page"]) for s in (complete, pending)],
        "baseline_references": sum(len(s["page"]["references"]) for s in (complete, pending)),
    }
    runner = r.BookRunner("ko", output=tmp_path)
    # Two copied real page states scope this unit test; source validation and
    # recognition launch are separate boundaries, never bypassed in production.
    monkeypatch.setattr(runner, "validate_sources", lambda value: None)
    monkeypatch.setattr(runner, "launch", lambda *args: pytest.fail("model launch forbidden"))
    monkeypatch.setattr(runner, "jobs", lambda *args: pytest.fail("model requests forbidden"))
    for directory in ("raw", "cache"):
        path = tmp_path / directory / "untouched.bin"
        path.parent.mkdir()
        path.write_bytes(b"existing successful evidence stays unchanged")
    for state in (complete, pending):
        r.write(runner.state_path(state["page"]["page"]), state)
    before = {
        str(path.relative_to(tmp_path)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in tmp_path.rglob("*")
        if path.is_file()
    }
    original_source = deepcopy(source)
    actual = runner.assemble(source)
    assert source == original_source
    assert all(hashlib.sha256((tmp_path / name).read_bytes()).hexdigest() == sha for name, sha in before.items())
    return actual, complete


def test_real_detection_only_resume_is_pending_and_preserves_complete_figures(tmp_path, monkeypatch):
    pending = states()["detection_only_state"]
    assert pending["page"]["page"] == 241
    assert all("result" not in figure for figure in pending["figures"])
    actual, complete = assemble_fixture(tmp_path, monkeypatch, pending)
    outcome = next(row for row in actual["page_outcomes"] if row["page"] == 241)
    assert outcome["status"] == "not_requested"
    assert outcome["detection_status"] == "complete"
    assert outcome["recognition_errors"] == []
    assert actual["summary"]["pending_pages"] == 1
    assert actual["summary"]["failed_pages"] == 0
    assert actual["summary"]["pages_recognized_validated"] == 1
    assert actual["summary"]["completed"] == len(complete["figures"])
    assert actual["figures"] == complete["figures"] + pending["figures"]
    assert all("result" not in f for f in actual["figures"] if f["page"] == 241)


def test_explicit_saved_failure_remains_failed_even_with_pending_peer(tmp_path, monkeypatch):
    pending = states()["detection_only_state"]
    failed = pending["figures"][0]
    failed["result"] = {"complete": False, "error": "isolated explicit recognition failure control"}
    actual, _ = assemble_fixture(tmp_path, monkeypatch, pending)
    outcome = next(row for row in actual["page_outcomes"] if row["page"] == 241)
    assert outcome["status"] == "failed"
    assert outcome["recognition_errors"] == [{"id": failed["id"], "error": failed["result"]["error"]}]
    assert actual["summary"]["failed_pages"] == 1
    assert "result" not in actual["figures"][-1]
