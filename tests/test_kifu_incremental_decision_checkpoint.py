"""Exact approved decisions survive a later budget stop without changing their review."""

from copy import deepcopy
import json
import os
import stat

import pytest

from katrain.kifu_ingest.catalog import review_content_sha256, validate_decision
from katrain.kifu_ingest.staging import Stage
from katrain.web.kifu.name_candidates import canonical_sha256


LIMIT = 1024 * 1024


def request():
    return {
        "kind": "raw_player",
        "key": "New Player",
        "source_items": [
            {"source_key": "19x19", "source_item_id": source_id, "slot": "black", "sgf_sha256": source_id * 64}
            for source_id in ("1", "2")
        ],
        "context": {"verified_reuse_displays": None},
        "template_sources": [],
    }


def approved(value):
    decision = {
        "kind": value["kind"],
        "key": value["key"],
        "displays": {lang: value["key"] for lang in ("cn", "tw", "jp", "ko", "en")},
        "methods": {lang: "retain_original" for lang in ("cn", "tw", "jp", "ko", "en")},
        "original_language": "en",
        "source_items": deepcopy(list(reversed(value["source_items"]))),
        "sources": [],
        "producer": {
            "id": "producer",
            "model": "qwen-plus",
            "request_id": "actual-producer-request",
            "at": "2026-10-20T01:00:00Z",
            "usage": {"total_tokens": 1144},
            "request_attempts": 1,
        },
        "review": {
            "id": "reviewer",
            "model": "qwen-plus",
            "request_id": "actual-reviewer-request",
            "at": "2026-10-20T01:00:01Z",
            "decision": "approve",
            "usage": {"total_tokens": 399},
        },
    }
    resign(decision)
    return decision


def resign(decision):
    decision["review"]["content_sha256"] = review_content_sha256(decision)


def checkpoint_path(stage, value):
    return stage.root / "name-decisions" / f"{canonical_sha256(value)}.json"


def test_missing_checkpoint_is_lazy_and_does_not_change_stage_inventory(tmp_path):
    stage = Stage(tmp_path)
    before = sorted(path.name for path in tmp_path.iterdir())
    manifest = deepcopy(stage.manifest)
    assert stage.load_name_decision(request()) is None
    assert sorted(path.name for path in tmp_path.iterdir()) == before
    assert stage.manifest == manifest and stage.items() == []


def test_restart_returns_whole_approved_decision_without_mutating_signed_members(tmp_path):
    stage = Stage(tmp_path)
    value = request()
    decision = approved(value)
    original_request, original_decision = deepcopy(value), deepcopy(decision)
    stage.save_name_decision(value, decision)
    loaded = Stage(tmp_path).load_name_decision(value)
    assert loaded == original_decision and validate_decision(loaded) == original_decision
    assert loaded["source_items"] == list(reversed(value["source_items"]))
    assert value == original_request and decision == original_decision
    assert stat.S_IMODE(checkpoint_path(stage, value).stat().st_mode) == 0o600
    assert stat.S_IMODE((tmp_path / "name-decisions").stat().st_mode) == 0o700
    assert stage.items() == [] and Stage(tmp_path).manifest == stage.manifest


@pytest.mark.parametrize("field", ["key", "context", "template_sources", "member", "sgf"])
def test_any_exact_request_change_misses_the_checkpoint(tmp_path, field):
    stage = Stage(tmp_path)
    value = request()
    stage.save_name_decision(value, approved(value))
    different = deepcopy(value)
    if field == "key":
        different["key"] = "Another Player"
    elif field == "context":
        different["context"] = {"verified_reuse_displays": {"en": "New Player"}}
    elif field == "template_sources":
        different["template_sources"] = [{"url": "https://example.org/changed"}]
    elif field == "member":
        different["source_items"].pop()
    else:
        different["source_items"][0]["sgf_sha256"] = "a" * 64
    assert Stage(tmp_path).load_name_decision(different) is None


@pytest.mark.parametrize("fault", ["review", "kind", "key", "add", "drop", "sgf"])
def test_save_rejects_invalid_review_or_different_finite_binding(tmp_path, fault):
    stage = Stage(tmp_path)
    value = request()
    decision = approved(value)
    if fault == "review":
        decision["review"]["decision"] = "reject"
    elif fault == "kind":
        decision["kind"] = "player"
    elif fault == "key":
        decision["key"] = "Another Player"
    elif fault == "add":
        decision["source_items"].append({**decision["source_items"][0], "source_item_id": "3"})
    elif fault == "drop":
        decision["source_items"].pop()
    else:
        decision["source_items"][0]["sgf_sha256"] = "f" * 64
    resign(decision)
    with pytest.raises(ValueError):
        stage.save_name_decision(value, decision)
    assert not (tmp_path / "name-decisions").exists()


@pytest.mark.parametrize("fault", ["json", "version", "hash", "request", "decision", "review_metadata", "members"])
def test_corrupt_or_mismatched_record_fails_closed_without_rewriting_it(tmp_path, fault):
    stage = Stage(tmp_path)
    value = request()
    stage.save_name_decision(value, approved(value))
    path = checkpoint_path(stage, value)
    record = json.loads(path.read_text())
    if fault == "json":
        raw = b'{"truncated":'
    else:
        if fault == "version":
            record["version"] = 2
        elif fault == "hash":
            record["request_sha256"] = "0" * 64
        elif fault == "request":
            record["request"]["context"] = {"different": True}
        elif fault == "decision":
            record["decision"]["displays"]["en"] = "Unreviewed change"
        elif fault == "review_metadata":
            record["decision"]["review"]["usage"]["total_tokens"] += 1
        else:
            record["decision"]["source_items"].pop()
            resign(record["decision"])
        raw = json.dumps(record).encode()
    path.write_bytes(raw)
    with pytest.raises(ValueError):
        Stage(tmp_path).load_name_decision(value)
    assert path.read_bytes() == raw


@pytest.mark.parametrize("location", ["directory", "file"])
def test_checkpoint_load_and_save_reject_symlinks(tmp_path, location):
    stage = Stage(tmp_path)
    value = request()
    outside = tmp_path / "outside"
    if location == "directory":
        outside.mkdir()
        (tmp_path / "name-decisions").symlink_to(outside, target_is_directory=True)
    else:
        (tmp_path / "name-decisions").mkdir()
        outside.write_text("untouched")
        checkpoint_path(stage, value).symlink_to(outside)
    for operation in (
        lambda: stage.load_name_decision(value),
        lambda: stage.save_name_decision(value, approved(value)),
    ):
        with pytest.raises(ValueError):
            operation()
    assert list(outside.iterdir()) == [] if location == "directory" else outside.read_text() == "untouched"


def test_checkpoint_read_and_write_are_bounded(tmp_path):
    stage = Stage(tmp_path)
    value = request()
    oversized = approved(value)
    oversized["audit_detail"] = "x" * LIMIT
    resign(oversized)
    with pytest.raises(ValueError):
        stage.save_name_decision(value, oversized)
    (tmp_path / "name-decisions").mkdir(exist_ok=True)
    checkpoint_path(stage, value).write_bytes(b" " * (LIMIT + 1))
    with pytest.raises(ValueError):
        stage.load_name_decision(value)


def test_checkpoint_atomic_write_preserves_previous_review_on_replace_failure(tmp_path, monkeypatch):
    stage = Stage(tmp_path)
    value = request()
    decision = approved(value)
    stage.save_name_decision(value, decision)
    path = checkpoint_path(stage, value)
    before = path.read_bytes()
    changed = deepcopy(decision)
    changed["review"]["request_id"] = "another-actual-review"

    def fail_replace(*args):
        raise OSError("simulated interrupted atomic replacement")

    monkeypatch.setattr(os, "replace", fail_replace)
    with pytest.raises(OSError):
        stage.save_name_decision(value, changed)
    assert path.read_bytes() == before and not list(path.parent.glob("*.tmp"))
    assert stage.load_name_decision(value) == decision


def test_first_checkpoint_fsyncs_renamed_record_and_lazy_directory(tmp_path, monkeypatch):
    stage = Stage(tmp_path)
    seen = set()
    real_fsync = os.fsync

    def fsync(fd):
        info = os.fstat(fd)
        if stat.S_ISDIR(info.st_mode):
            seen.add(info.st_ino)
        real_fsync(fd)

    monkeypatch.setattr(os, "fsync", fsync)
    value = request()
    stage.save_name_decision(value, approved(value))
    assert {tmp_path.stat().st_ino, (tmp_path / "name-decisions").stat().st_ino} <= seen


@pytest.mark.parametrize("fault", ["extra", "missing", "members", "not_json"])
def test_checkpoint_request_requires_only_exact_opaque_json_fields(tmp_path, fault):
    stage = Stage(tmp_path)
    value = request()
    decision = approved(value)
    if fault == "extra":
        value["api_key"] = "must-not-be-a-checkpoint-field"
    elif fault == "missing":
        del value["context"]
    elif fault == "members":
        value["source_items"] = tuple(value["source_items"])
    else:
        value["context"] = object()
    for operation in (lambda: stage.load_name_decision(value), lambda: stage.save_name_decision(value, decision)):
        with pytest.raises(ValueError):
            operation()
