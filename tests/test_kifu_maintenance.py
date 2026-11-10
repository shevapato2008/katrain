import asyncio
import copy
import hashlib
import json
from pathlib import Path

import pytest

from katrain.kifu_ingest import maintenance
from katrain.kifu_ingest.source_19x19 import SourceError
from katrain.kifu_ingest.staging import Stage, staging_writer_lock


def fixture_stage(tmp_path):
    stage = Stage(tmp_path.resolve())
    for i in maintenance.LEGACY_7004_IDS:
        stage.remember({"id": i, "original": "keep"})
        stage.fail(i, SourceError("source business error: 7004"))
    stage.manifest["items"][maintenance.LEGACY_7004_IDS[0]]["last_error"] += " extra"
    stage.remember({"id": "123"})
    stage.fail("123", SourceError("source business error: 7004"))
    stage._persist()
    return stage


def test_finite_migration_default_dry_run_apply_preserves_and_digest_rollback(tmp_path):
    stage = fixture_stage(tmp_path)
    pre = stage.manifest_path.read_bytes()
    records = copy.deepcopy(stage.manifest["items"])
    preview = maintenance.migrate_legacy_7004(stage.root)
    assert len(preview["matched_ids"]) == 6
    assert stage.manifest_path.read_bytes() == pre
    assert not (stage.root / "maintenance").exists()
    result = maintenance.migrate_legacy_7004(stage.root, apply=True)
    audit = json.loads(Path(result["audit_path"]).read_text())
    assert audit["pre_sha256"] == hashlib.sha256(pre).hexdigest()
    updated = Stage(stage.root).manifest["items"]
    for i in result["matched_ids"]:
        assert updated[i]["metadata"] == records[i]["metadata"]
        assert updated[i]["last_error"] == records[i]["last_error"]
        assert updated[i]["attempts"] == records[i]["attempts"]
        assert updated[i]["status"] == "failed"
        assert updated[i]["next_retry_at"] is None
        assert updated[i]["recent"]["terminal"] is True
    assert updated["123"] == records["123"]
    assert Path(audit["backup_path"]).read_bytes() == pre
    dry = maintenance.rollback(stage.root, result["audit_path"])
    assert dry["dry_run"] is True
    assert stage.manifest_path.read_bytes() != pre
    maintenance.rollback(stage.root, result["audit_path"], apply=True)
    assert stage.manifest_path.read_bytes() == pre


def test_rollback_refuses_concurrent_manifest_or_backup_change(tmp_path):
    stage = fixture_stage(tmp_path)
    result = maintenance.migrate_legacy_7004(stage.root, apply=True)
    stage = Stage(stage.root)
    stage.remember({"id": "999"})
    with pytest.raises(ValueError, match="postimage"):
        maintenance.rollback(stage.root, result["audit_path"], apply=True)


def test_manual_restore_one_id_is_audited_and_keeps_old_evidence(tmp_path):
    stage = fixture_stage(tmp_path)
    migrated = maintenance.migrate_legacy_7004(stage.root, apply=True)
    i = migrated["matched_ids"][0]
    before = copy.deepcopy(Stage(stage.root).manifest["items"][i])
    result = maintenance.restore_item(stage.root, i)
    assert result["dry_run"] is True
    result = maintenance.restore_item(stage.root, i, apply=True)
    item = Stage(stage.root).manifest["items"][i]
    assert item["metadata"] == before["metadata"] and item["attempts"] == before["attempts"]
    assert item["last_error"] == before["last_error"]
    assert item["recent"]["terminal"] is False
    audit = json.loads(Path(result["audit_path"]).read_text())
    assert audit["before_items"][i] == before
    assert Path(migrated["audit_path"]).exists()


def test_writer_lock_excludes_another_writer_and_symlink(tmp_path):
    with staging_writer_lock(tmp_path.resolve()):
        with pytest.raises(BlockingIOError):
            with staging_writer_lock(tmp_path.resolve()):
                pass
    (tmp_path / ".writer.lock").unlink()
    outside = tmp_path / "outside"
    outside.write_text("safe")
    (tmp_path / ".writer.lock").symlink_to(outside)
    with pytest.raises((ValueError, OSError)):
        with staging_writer_lock(tmp_path.resolve()):
            pass
    assert outside.read_text() == "safe"


def test_history_root_is_independent_and_explicit_finite_pages(tmp_path):
    hourly, history = tmp_path / "hourly", tmp_path / "history"

    class Source:
        calls = []
        deadline = None
        requests = 0
        max_requests = 500

        async def fetch_page(self, page):
            self.calls.append(("page", page))
            return [{"id": page + 1}]

        async def fetch_sgf(self, i):
            self.calls.append(("sgf", i))
            return "(;GM[1]SZ[19];B[aa])"

    for path in (hourly, hourly / "nested", tmp_path):
        with pytest.raises(ValueError, match="independent"):
            asyncio.run(
                maintenance.collect_history(
                    Source(), path.resolve(), hourly.resolve(), pages=2, max_downloads=1, max_requests=10, seconds=2
                )
            )
    source = Source()
    result = asyncio.run(
        maintenance.collect_history(
            source,
            history.resolve(),
            hourly.resolve(),
            start_page=100,
            pages=2,
            max_downloads=1,
            max_requests=10,
            seconds=2,
        )
    )
    assert source.calls[0] == ("page", 100)
    assert len([x for x in source.calls if x[0] == "sgf"]) == 1
    assert result["downloaded"] == 1
    assert not hourly.exists()


def test_cli_defaults_migration_to_dryrun(tmp_path, capsys):
    stage = fixture_stage(tmp_path)
    raw = stage.manifest_path.read_bytes()
    assert maintenance.main(["migrate-7004", "--staging-root", str(stage.root)]) == 0
    assert json.loads(capsys.readouterr().out)["dry_run"] is True
    assert stage.manifest_path.read_bytes() == raw


def test_restore_then_reobserve_preserves_prior_change_evidence(tmp_path):
    from katrain.kifu_ingest import recent
    from datetime import datetime, timezone

    now = datetime(2026, 10, 23, tzinfo=timezone.utc).timestamp()
    metadata = {
        "id": 1,
        "pb": "Original",
        "playTime": {"date": {"year": 2026, "month": 10, "day": 23}, "time": {"hour": 0, "minute": 0, "second": 0}},
    }
    stage = Stage(tmp_path.resolve())
    stage.remember(metadata)
    stage.save_sgf("1", "(;GM[1]SZ[19];B[aa])")

    class Source:
        async def fetch_page(self, page):
            return [{**metadata, "pb": "Changed"}] if page == 0 else []

        async def fetch_sgf(self, i):
            return "(;GM[1]SZ[19];W[bb])"

    asyncio.run(recent.discover_recent(Source(), stage, published_ids={"1"}, wall_clock=lambda: now))
    old_path = stage.root / stage.manifest["items"]["1"]["recent"]["change_evidence"]
    old_evidence = old_path.read_bytes()
    maintenance.restore_item(stage.root, "1", apply=True)
    stage = Stage(stage.root)
    asyncio.run(recent.discover_recent(Source(), stage, published_ids={"1"}, wall_clock=lambda: now + 1))
    assert old_path.read_bytes() == old_evidence
    assert stage.root / stage.manifest["items"]["1"]["recent"]["change_evidence"] != old_path
