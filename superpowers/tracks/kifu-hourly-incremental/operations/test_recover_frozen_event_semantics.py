"""Exact incident SQLite checks; no cloud writes or paid calls."""

from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import importlib.util
import json
import os
from pathlib import Path
import sys

import pytest
from sqlalchemy import create_engine, select, update
from katrain.cron.models import CronJobControlDB
from katrain.kifu_ingest.state import metadata, items, batches
from katrain.web.core.models_db import KifuNameBatch, KifuAlbum, KifuAlbumSource, KifuSource
from katrain.web.kifu.name_candidates import canonical_sha256

HERE = Path(__file__).parent
EXPORT = Path(
    os.getenv("KIFU_SEMANTIC_RECOVERY_FIXTURE", "/tmp/kifu-hourly-incremental-20261019/hourly-first-failure-evidence")
)
NOW = datetime(2026, 10, 20, 5, 20, tzinfo=timezone.utc)
INDICES = {1, 2, 7, 8, 9, 11, 12, 13}


def helper():
    path = HERE / "recover_frozen_event_semantics.py"
    assert path.exists(), "semantic recovery helper not implemented"
    sys.path.insert(0, str(HERE))
    spec = importlib.util.spec_from_file_location("semantic_recovery_operator", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def inputs(tmp_path):
    source = EXPORT / "pending-recovery/91315699-ae8fd9d9f9f4a0bd.json"
    if not source.exists():
        pytest.skip("exact operational incident export required")
    oldpath = tmp_path / "old.json"
    oldpath.write_bytes(source.read_bytes())
    old = json.loads(oldpath.read_text())
    curated = tmp_path / "curated.json"
    curated.write_bytes((EXPORT / "curated-event-corrections.json").read_bytes())
    replacements = []
    for row in json.loads(curated.read_text())["corrections"]:
        d = deepcopy(old["decisions"][row["index"]])
        for field in ("displays", "methods", "original_language"):
            d[field] = deepcopy(row[field])
        d["producer"] = {
            "id": "fixture-producer",
            "model": "offline-fixture",
            "request_id": "new-p-" + str(row["index"]),
            "at": "2026-10-20T05:10:00Z",
        }
        d["review"] = {
            "id": "fixture-reviewer",
            "model": "offline-fixture",
            "request_id": "new-r-" + str(row["index"]),
            "at": "2026-10-20T05:11:00Z",
            "decision": "approve",
            "content_sha256": canonical_sha256({k: v for k, v in d.items() if k != "review"}),
        }
        replacements.append(d)
    return oldpath, old, curated, replacements


def test_candidate_changes_exact_curated_eight_and_keeps_source_payload(tmp_path):
    m = helper()
    oldpath, old, curated, replacements = inputs(tmp_path)
    new = m.make_candidate(oldpath, replacements, curated)
    assert old["games"] == new["games"]
    assert {i for i, (a, b) in enumerate(zip(old["decisions"], new["decisions"])) if a != b} == INDICES
    assert new["publication_key"] == "19x19-event-recovery-" + canonical_sha256(new["decisions"])[:24]
    wrong = deepcopy(replacements)
    wrong[0]["displays"]["en"] += " wrong"
    wrong[0]["review"]["content_sha256"] = canonical_sha256({k: v for k, v in wrong[0].items() if k != "review"})
    with pytest.raises(ValueError):
        m.make_candidate(oldpath, wrong, curated)


@pytest.fixture
def incident(tmp_path, monkeypatch):
    m = helper()
    source, old, curated, replacements = inputs(tmp_path)
    root = tmp_path / "stage"
    (root / "packages").mkdir(parents=True)
    (root / "pending-recovery").mkdir()
    (root / "sgf").mkdir()
    oldpath = root / "packages" / "old-ae8.json"
    oldpath.write_bytes(source.read_bytes())
    new = m.make_candidate(oldpath, replacements, curated)
    pending = root / "pending-recovery" / "new-semantic.json"
    pending.write_text(json.dumps(new, ensure_ascii=False, sort_keys=True))
    receipt = json.loads((EXPORT / "TEST-B72-metric-increment.json").read_text())["native_applied_receipt"]
    verification = json.loads((EXPORT / "run61884-TEST-verification.json").read_text())
    undo = {"batch_id": 880, "status": "undone", "batch_ids": [880, 881, 882], "reverted": 461}
    engine = create_engine("sqlite:///" + str(tmp_path / "state.sqlite"))
    metadata.create_all(engine)
    for model in (CronJobControlDB, KifuNameBatch, KifuAlbum, KifuSource, KifuAlbumSource):
        model.__table__.create(engine)
    staged = {}
    with engine.begin() as c:
        c.execute(
            CronJobControlDB.__table__.insert().values(
                job_name="kifu_ingest",
                paused=True,
                reason="semantic recovery fixture",
                changed_at=NOW,
                changed_by="fixture",
            )
        )
        for id in undo["batch_ids"]:
            c.execute(
                KifuNameBatch.__table__.insert().values(
                    id=id,
                    bundle_sha256=canonical_sha256(old) if id == 880 else str(id).zfill(64),
                    inventory_sha256="0" * 64,
                    source_registry_id=1,
                    status="undone",
                    reviewed_artifact={"receipt": receipt, "undo_receipt": undo} if id == 880 else {},
                )
            )
        c.execute(
            batches.insert().values(
                batch_uuid="old-ae8",
                publication_key=old["publication_key"],
                manifest_sha256=canonical_sha256(old),
                status="retry_wait",
                resume_phase="test_verified",
                test_receipt=receipt,
                test_verification=verification,
                attempts=1,
                error="receiver exited with status 2",
                created_at=NOW,
                updated_at=NOW,
            )
        )
        for g in old["games"]:
            sourceid = g["source_item_id"]
            p = root / "sgf" / (sourceid + ".sgf")
            p.write_text(g["sgf_content"])
            assert sha256(p.read_bytes()).hexdigest() == g["raw_sha256"]
            staged[sourceid] = {
                "external_id": sourceid,
                "raw_sgf_path": str(p),
                "raw_sha256": g["raw_sha256"],
                "status": "downloaded",
            }
            c.execute(
                items.insert().values(
                    source_key="19x19",
                    external_id=sourceid,
                    raw_sha256=g["raw_sha256"],
                    sgf_sha256=g["sgf_sha256"],
                    staging_path=str(p),
                    source_metadata={"canary": sourceid},
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
        "new": {"publication_key": new["publication_key"], "manifest_sha256": canonical_sha256(new)},
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
        "template": {k: new["decisions"][17][k] for k in ("kind", "key", "displays", "original_language", "methods")},
    }

    @contextmanager
    def sqlite_lock(_):
        yield True

    monkeypatch.setattr(m, "_session_lock", sqlite_lock)
    return m, engine, root, oldpath, pending, curated, undo, proof, old, new


def snapshot(e):
    with e.connect() as c:
        return [dict(r) for r in c.execute(select(items).order_by(items.c.external_id)).mappings()], [
            dict(r) for r in c.execute(select(batches).order_by(batches.c.id)).mappings()
        ]


def test_dryrun_and_commit_rename_recovery_preserve_real_old_test_receipts(incident, monkeypatch):
    m, e, root, oldpath, pending, curated, undo, proof, old, new = incident
    before = snapshot(e)
    oldbytes = oldpath.read_bytes()
    assert m.recover(e, root, oldpath, pending, curated, undo, proof, now=NOW)["mode"] == "dry_run"
    assert snapshot(e) == before and oldpath.read_bytes() == oldbytes
    replace = m.os.replace

    def crash(*_):
        raise OSError("crash after DB commit")

    monkeypatch.setattr(m.os, "replace", crash)
    with pytest.raises(OSError):
        m.recover(e, root, oldpath, pending, curated, undo, proof, apply=True, now=NOW)
    rows, bs = snapshot(e)
    assert bs[0]["status"] == "quarantined" and bs[1]["status"] == "names_ready"
    assert (
        bs[0]["test_receipt"] == before[1][0]["test_receipt"]
        and bs[0]["test_verification"] == before[1][0]["test_verification"]
    )
    assert bs[0]["stats"]["native_test_undo_receipt"] == undo
    assert all(bs[1][f] is None for f in ("test_receipt", "test_verification", "prod_receipt", "prod_verification"))
    for a, b in zip(before[0], rows):
        assert {k: v for k, v in a.items() if k != "publication_key"} == {
            k: v for k, v in b.items() if k != "publication_key"
        }
        assert b["publication_key"] == new["publication_key"]
    committed = snapshot(e)
    monkeypatch.setattr(m.os, "replace", replace)
    assert m.recover(e, root, oldpath, pending, curated, undo, proof, apply=True, now=NOW)["mode"] == "recovered_rename"
    assert m.recover(e, root, oldpath, pending, curated, undo, proof, apply=True, now=NOW)["mode"] == "already_complete"
    assert snapshot(e) == committed and oldpath.read_bytes() == oldbytes


@pytest.mark.parametrize(
    "conflict",
    [
        "native_not_undone",
        "undo_mismatch",
        "old_receipt_mismatch",
        "old_verification_mismatch",
        "stale_proof",
        "mixed_item_key",
        "source_presence",
        "new_native",
    ],
)
def test_failed_preflight_never_changes_state_or_packets(incident, conflict):
    m, e, root, oldpath, pending, curated, undo, proof, old, new = incident
    with e.begin() as c:
        if conflict == "native_not_undone":
            c.execute(update(KifuNameBatch).where(KifuNameBatch.id == 880).values(status="applied"))
        elif conflict == "old_receipt_mismatch":
            c.execute(update(batches).values(test_receipt={"bad": True}))
        elif conflict == "old_verification_mismatch":
            c.execute(update(batches).values(test_verification={"bad": True}))
        elif conflict == "mixed_item_key":
            c.execute(
                update(items)
                .where(items.c.external_id == old["games"][0]["source_item_id"])
                .values(publication_key=new["publication_key"])
            )
        elif conflict == "source_presence":
            c.execute(
                KifuAlbum.__table__.insert().values(
                    player_black="fixture",
                    player_white="fixture",
                    sgf_content="(;SZ[19])",
                    source_path=old["games"][0]["origin_path"],
                )
            )
        elif conflict == "new_native":
            c.execute(
                KifuNameBatch.__table__.insert().values(
                    id=900,
                    bundle_sha256=canonical_sha256(new),
                    inventory_sha256="0" * 64,
                    source_registry_id=1,
                    status="applied",
                    reviewed_artifact={"publication_key": new["publication_key"]},
                )
            )
    if conflict == "undo_mismatch":
        undo = deepcopy(undo)
        undo["reverted"] += 1
    if conflict == "stale_proof":
        proof = deepcopy(proof)
        proof["checked_at"] = (NOW - timedelta(minutes=11)).isoformat()
    before = snapshot(e)
    raw = oldpath.read_bytes()
    candidate = pending.read_bytes()
    with pytest.raises(ValueError):
        m.recover(e, root, oldpath, pending, curated, undo, proof, apply=True, now=NOW)
    assert snapshot(e) == before and oldpath.read_bytes() == raw and pending.read_bytes() == candidate


def test_real_undo_export_envelope_is_checked_against_native_receipt(incident):
    m, e, root, oldpath, pending, curated, undo, proof, _, _ = incident
    envelope = {
        "undo_receipt": undo,
        "before_counts": {"total": 176621, "public": 176362},
        "after_counts": {"total": 176549, "public": 176290},
        "queue_untouched": True,
    }
    assert m.recover(e, root, oldpath, pending, curated, envelope, proof, now=NOW)["mode"] == "dry_run"
