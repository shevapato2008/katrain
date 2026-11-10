"""Focused SQLite checks for this exact incident; point KIFU_RECOVERY_PACKET at the frozen export."""

from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import importlib.util
import json
import os
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select, update
from katrain.cron.models import CronJobControlDB
from katrain.kifu_ingest.state import metadata, items, batches
from katrain.web.core.models_db import KifuNameBatch, KifuAlbum, KifuAlbumSource, KifuSource
from katrain.web.kifu.name_candidates import canonical_sha256

NOW = datetime(2026, 10, 20, 4, 0, tzinfo=timezone.utc)
HERE = Path(__file__).parent


def helper():
    path = HERE / "recover_frozen_raw_player.py"
    assert path.exists(), "recovery helper is not implemented"
    spec = importlib.util.spec_from_file_location("recovery_operator", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def incident(tmp_path, monkeypatch):
    m = helper()
    frozen = Path(
        os.getenv(
            "KIFU_RECOVERY_PACKET",
            "/tmp/kifu-hourly-incremental-20261019/hourly-first-failure-evidence/frozen-72.packet.json",
        )
    )
    if not frozen.exists():
        pytest.skip("exact frozen incident export is required for this one-off operator test")
    root = tmp_path / "stage"
    (root / "packages").mkdir(parents=True)
    (root / "sgf").mkdir()
    old_path = root / "packages" / "old.json"
    old_path.write_bytes(frozen.read_bytes())
    old = json.loads(old_path.read_text())
    replacement = deepcopy(old["decisions"][17])
    replacement["original_language"] = "und"
    replacement["methods"]["jp"] = "transliteration"
    replacement["producer"] = {
        "id": "offline-fixture-producer",
        "model": "fixture-only",
        "request_id": "offline-producer-new",
        "at": "2026-10-20T03:50:00Z",
    }
    replacement["review"] = {
        "id": "offline-fixture-reviewer",
        "model": "fixture-only",
        "request_id": "offline-reviewer-new",
        "at": "2026-10-20T03:51:00Z",
        "decision": "approve",
        "content_sha256": canonical_sha256({k: v for k, v in replacement.items() if k != "review"}),
    }
    candidate = m.make_candidate(old_path, replacement)
    pending = root / "pending-recovery"
    pending.mkdir()
    candidate_path = pending / ("new-" + canonical_sha256(candidate)[:16] + ".json")
    candidate_path.write_text(json.dumps(candidate, ensure_ascii=False, sort_keys=True))
    engine = create_engine("sqlite:///" + str(tmp_path / "state.sqlite"))
    metadata.create_all(engine)
    CronJobControlDB.__table__.create(engine)
    KifuNameBatch.__table__.create(engine)
    for model in (KifuAlbum, KifuSource, KifuAlbumSource):
        model.__table__.create(engine)
    staged = {}
    with engine.begin() as c:
        c.execute(
            CronJobControlDB.__table__.insert().values(
                job_name="kifu_ingest",
                paused=True,
                reason="offline recovery fixture",
                changed_at=NOW,
                changed_by="fixture",
            )
        )
        c.execute(
            batches.insert().values(
                batch_uuid="fixture-old",
                publication_key=old["publication_key"],
                manifest_sha256=canonical_sha256(old),
                status="retry_wait",
                resume_phase="names_ready",
                attempts=1,
                error="original incident error",
                created_at=NOW,
                updated_at=NOW,
            )
        )
        for game in old["games"]:
            source_id = game["source_item_id"]
            path = root / "sgf" / (source_id + ".sgf")
            path.write_text(game["sgf_content"])
            assert sha256(path.read_bytes()).hexdigest() == game["raw_sha256"]
            staged[source_id] = {
                "external_id": source_id,
                "raw_sgf_path": str(path),
                "raw_sha256": game["raw_sha256"],
                "status": "downloaded",
            }
            c.execute(
                items.insert().values(
                    source_key="19x19",
                    external_id=source_id,
                    raw_sha256=game["raw_sha256"],
                    sgf_sha256=game["sgf_sha256"],
                    staging_path=str(path),
                    source_metadata={"canary": source_id},
                    status="names_ready",
                    publication_key=old["publication_key"],
                    attempts=0,
                    created_at=NOW,
                    updated_at=NOW,
                )
            )
    (root / "manifest.json").write_text(json.dumps({"items": staged}))
    proof = {
        "version": "kifu-frozen-recovery-proof-v1",
        "checked_at": NOW.isoformat(),
        "old": {"publication_key": old["publication_key"], "manifest_sha256": canonical_sha256(old)},
        "new": {"publication_key": candidate["publication_key"], "manifest_sha256": canonical_sha256(candidate)},
        "source_ids": sorted(staged),
        "native_absent": {
            "old_digest": True,
            "old_key": True,
            "new_digest": True,
            "new_key": True,
            "source_presence": 0,
            "source_link_count": 0,
            "source_primary_count": 0,
        },
        "template": {k: deepcopy(replacement[k]) for k in ["kind", "key", "displays", "original_language", "methods"]},
    }

    @contextmanager
    def sqlite_lock(_):
        yield True

    monkeypatch.setattr(m, "_session_lock", sqlite_lock)
    return m, engine, root, old_path, candidate_path, proof, old, candidate


def snapshot(engine):
    with engine.connect() as c:
        return [dict(r) for r in c.execute(select(items).order_by(items.c.external_id)).mappings()], [
            dict(r) for r in c.execute(select(batches).order_by(batches.c.id)).mappings()
        ]


def test_dry_run_preserves_all_bytes_state_and_only_decision17_can_change(incident):
    m, e, root, old_path, candidate_path, proof, old, new = incident
    before = snapshot(e)
    files = {str(p.relative_to(root)): p.read_bytes() for p in root.rglob("*") if p.is_file()}
    assert m.recover(e, root, old_path, candidate_path, proof, now=NOW)["mode"] == "dry_run"
    assert snapshot(e) == before
    assert files == {str(p.relative_to(root)): p.read_bytes() for p in root.rglob("*") if p.is_file()}
    assert old["games"] == new["games"] and old["decisions"][:17] == new["decisions"][:17]
    bad = deepcopy(new["decisions"][17])
    bad["source_items"] = bad["source_items"][:-1]
    with pytest.raises(ValueError):
        m.make_candidate(old_path, bad)


def test_commit_then_rename_crash_is_resumable_without_retargeting_twice(incident, monkeypatch):
    m, e, root, old_path, candidate_path, proof, old, new = incident
    original = old_path.read_bytes()
    before, _ = snapshot(e)
    replace = m.os.replace

    def crash(*_):
        raise OSError("simulated crash after DB commit")

    monkeypatch.setattr(m.os, "replace", crash)
    with pytest.raises(OSError):
        m.recover(e, root, old_path, candidate_path, proof, apply=True, now=NOW)
    after, rows = snapshot(e)
    assert rows[0]["status"] == "quarantined" and rows[1]["status"] == "names_ready"
    for left, right in zip(before, after):
        assert {k: v for k, v in left.items() if k != "publication_key"} == {
            k: v for k, v in right.items() if k != "publication_key"
        }
        assert right["publication_key"] == new["publication_key"]
    committed = snapshot(e)
    monkeypatch.setattr(m.os, "replace", replace)
    result = m.recover(e, root, old_path, candidate_path, proof, apply=True, now=NOW)
    assert result["mode"] == "recovered_rename" and Path(result["package_path"]).exists()
    assert snapshot(e) == committed and old_path.read_bytes() == original
    assert m.recover(e, root, old_path, candidate_path, proof, apply=True, now=NOW)["mode"] == "already_complete"
    assert snapshot(e) == committed


@pytest.mark.parametrize(
    "conflict", ["receipt", "mixed_key", "not_paused", "stale_proof", "native_receipt", "native_source", "raw_hash"]
)
def test_preflight_conflicts_leave_state_and_packet_unchanged(incident, conflict):
    m, e, root, old_path, candidate_path, proof, old, new = incident
    with e.begin() as c:
        if conflict == "receipt":
            c.execute(
                update(items)
                .where(items.c.external_id == old["games"][0]["source_item_id"])
                .values(test_receipt={"unexpected": True})
            )
        elif conflict == "mixed_key":
            c.execute(
                update(items)
                .where(items.c.external_id == old["games"][0]["source_item_id"])
                .values(publication_key=new["publication_key"])
            )
        elif conflict == "not_paused":
            c.execute(update(CronJobControlDB).values(paused=False))
        elif conflict == "native_receipt":
            c.execute(
                KifuNameBatch.__table__.insert().values(
                    bundle_sha256=canonical_sha256(old),
                    inventory_sha256="0" * 64,
                    source_registry_id=1,
                    status="applied",
                    reviewed_artifact={"publication_key": old["publication_key"]},
                )
            )
        elif conflict == "native_source":
            c.execute(
                KifuAlbum.__table__.insert().values(
                    player_black="fixture",
                    player_white="fixture",
                    sgf_content="(;SZ[19])",
                    source_path=old["games"][0]["origin_path"],
                )
            )
    if conflict == "raw_hash":
        (root / "sgf" / (old["games"][0]["source_item_id"] + ".sgf")).write_text("changed")
    if conflict == "stale_proof":
        proof["checked_at"] = (NOW - timedelta(minutes=11)).isoformat()
    before = snapshot(e)
    raw = old_path.read_bytes()
    with pytest.raises(ValueError):
        m.recover(e, root, old_path, candidate_path, proof, apply=True, now=NOW)
    assert snapshot(e) == before and old_path.read_bytes() == raw and candidate_path.exists()


def test_optional_note_change_requires_actual_new_review_content_hash(incident):
    m, _, _, old_path, _, _, _, candidate = incident
    replacement = deepcopy(candidate["decisions"][17])
    replacement.pop("cn_conversion_note", None)
    with pytest.raises(ValueError):
        m.make_candidate(old_path, replacement)
    replacement["review"]["content_sha256"] = canonical_sha256({k: v for k, v in replacement.items() if k != "review"})
    assert "cn_conversion_note" not in m.make_candidate(old_path, replacement)["decisions"][17]
