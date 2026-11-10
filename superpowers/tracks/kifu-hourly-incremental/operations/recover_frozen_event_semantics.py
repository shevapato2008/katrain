"""Finite semantic supersede of undone TEST880; consumes real signed decisions only.

Keep this operator next to recover_frozen_raw_player.py. --prepare only writes a
pending candidate. Default recovery is dry-run; --apply requires actual undo and
fresh PROD evidence, paused B and the existing session lock. No publisher/model.
"""

import argparse
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
from uuid import uuid4

from sqlalchemy import Text, cast, func, or_, select
from katrain.cron.jobs.kifu_ingest import _session_lock
from katrain.cron.models import CronJobControlDB
from katrain.kifu_ingest.catalog import _validate_manifest, validate_decision
from katrain.kifu_ingest.state import batches, items
from katrain.web.core.models_db import KifuNameBatch, KifuAlbum, KifuAlbumSource, KifuSource
from katrain.web.kifu.name_candidates import canonical_sha256
from recover_frozen_raw_player import require, read_file, fsync_directory, proof_check, RECEIPTS

OLD_FILE_SHA = "70bd7d0936ae9bef18762f6d4fa8f1322aa93d10d3b0c3baea50e63de3de70a3"
OLD_SHA = "ae8fd9d9f9f4a0bde3ea72e20b74c64b0b3e041848dbb5f50d73a3b7d935e019"
OLD_KEY = "19x19-recovery-a5425ac6c5b3d96d9bc23d3b"
CURATED_SHA = "31da8dd74851959cf838c35c7d8e5a21f9d5f46227622c89e1a1479e27668efb"
OLD_RECEIPT_SHA = "2c5083117da9cca4cef1fc1be68d6564a314f40d50e606183b28e3ac407397ef"
OLD_VERIFICATION_SHA = "586fec94b199a446e3d46eb96c1b832a94eb440333e80ac3f29c77406d41d60a"
INDICES = {1, 2, 7, 8, 9, 11, 12, 13}


def old_packet(path):
    raw = read_file(path)
    require(sha256(raw).hexdigest() == OLD_FILE_SHA, "old ae8 file bytes differ")
    old = json.loads(raw)
    require(old["publication_key"] == OLD_KEY and canonical_sha256(old) == OLD_SHA, "old ae8 identity differs")
    require(len(old["games"]) == 72 and len(old["decisions"]) == 18, "expected exactly72/18")
    _validate_manifest(old, OLD_SHA)
    return old


def make_candidate(old_path, replacements, curated_path):
    old = old_packet(old_path)
    raw = read_file(curated_path)
    require(sha256(raw).hexdigest() == CURATED_SHA, "curated file SHA differs from approved version")
    curated = json.loads(raw)
    rows = curated["corrections"]
    require({r["index"] for r in rows} == INDICES and len(rows) == 8, "curated index set differs")
    require(curated["source_manifest"]["file_sha256"] == OLD_FILE_SHA, "curated source binding differs")
    require(isinstance(replacements, list) and len(replacements) == 8, "need exactly8 actually reviewed decisions")
    by_key = {(d["kind"], d["key"]): d for d in replacements}
    require(len(by_key) == 8, "duplicate replacement key")
    new = deepcopy(old)
    for row in rows:
        index = row["index"]
        previous = old["decisions"][index]
        decision = by_key.get((previous["kind"], previous["key"]))
        require(isinstance(decision, dict), "reviewed correction missing")
        validate_decision(decision)
        for field in ("kind", "key", "displays", "methods", "original_language", "sources", "source_items"):
            require(decision[field] == row[field], "reviewed decision differs from exact curated " + field)
        mutable = {"displays", "methods", "producer", "review", "cn_conversion_note"}
        require(
            {k: v for k, v in decision.items() if k not in mutable}
            == {k: v for k, v in previous.items() if k not in mutable},
            "decision changed original language, source scope or other immutable fields",
        )
        require(
            all(decision[role]["request_id"] != previous[role]["request_id"] for role in ("producer", "review")),
            "correction needs new actual producer/reviewer requests",
        )
        new["decisions"][index] = deepcopy(decision)
    new["publication_key"] = "19x19-event-recovery-" + canonical_sha256(new["decisions"])[:24]
    _validate_manifest(new, canonical_sha256(new))
    return new


def native_evidence(conn, old, new, undo):
    native = conn.execute(select(KifuNameBatch.__table__).where(KifuNameBatch.id == 880)).mappings().one_or_none()
    require(
        native is not None and native["bundle_sha256"] == OLD_SHA and native["status"] == "undone",
        "native TEST880 is not actually undone",
    )
    artifact = native["reviewed_artifact"]
    require(
        isinstance(undo, dict)
        and undo.get("batch_id") == 880
        and undo.get("status") == "undone"
        and undo == artifact.get("undo_receipt"),
        "supplied undo does not match actual native undo receipt",
    )
    require(canonical_sha256(artifact.get("receipt")) == OLD_RECEIPT_SHA, "original native880 receipt differs")
    require(
        undo.get("batch_ids") == [880, 881, 882] and type(undo.get("reverted")) is int and undo["reverted"] > 0,
        "native undo membership/outcome differs",
    )
    children = list(
        conn.execute(select(KifuNameBatch.id, KifuNameBatch.status).where(KifuNameBatch.id.in_(undo["batch_ids"])))
    )
    require(
        len(children) == 3 and all(status == "undone" for _, status in children), "native undo child status differs"
    )
    require(
        conn.scalar(
            select(func.count()).select_from(KifuNameBatch).where(KifuNameBatch.bundle_sha256 == canonical_sha256(new))
        )
        == 0,
        "new TEST native bundle exists",
    )
    require(
        conn.scalar(
            select(func.count())
            .select_from(KifuNameBatch)
            .where(cast(KifuNameBatch.reviewed_artifact, Text).contains(new["publication_key"]))
        )
        == 0,
        "new TEST publication key text exists",
    )
    paths = [g["origin_path"] for g in old["games"]]
    linked = conn.scalar(
        select(func.count())
        .select_from(KifuAlbumSource)
        .join(KifuSource, KifuSource.id == KifuAlbumSource.source_id)
        .where(KifuSource.source_key == "19x19", KifuAlbumSource.origin_path.in_(paths))
    )
    primary = conn.scalar(select(func.count()).select_from(KifuAlbum).where(KifuAlbum.source_path.in_(paths)))
    require(linked == primary == 0, "TEST source72 still present after undo")


def recover(engine, root, old_path, candidate_path, curated_path, undo, proof, *, apply=False, now=None):
    now = now or datetime.now(timezone.utc)
    require(isinstance(undo, dict), "undo input must be an object")
    undo = undo.get("undo_receipt", undo)
    require(
        undo == {"batch_id": 880, "status": "undone", "batch_ids": [880, 881, 882], "reverted": 461},
        "expected the exact native TEST880 undo461 outcome",
    )
    root, old_path, candidate_path = Path(root), Path(old_path), Path(candidate_path)
    require(root.is_absolute() and root.is_dir() and not root.is_symlink(), "unsafe existing stage root")
    require(
        old_path.parent == root / "packages" and not old_path.parent.is_symlink(), "old packet must stay in packages"
    )
    require(
        candidate_path.parent == root / "pending-recovery" and not candidate_path.parent.is_symlink(),
        "candidate must be pending outside scanner",
    )
    target = root / "packages" / candidate_path.name
    require(
        not target.is_symlink() and os.stat(candidate_path.parent).st_dev == os.stat(target.parent).st_dev,
        "rename must stay on one filesystem",
    )
    old = old_packet(old_path)
    raw = read_file(candidate_path if candidate_path.exists() else target)
    new = json.loads(raw)
    require(
        new == make_candidate(old_path, [new["decisions"][i] for i in sorted(INDICES)], curated_path),
        "candidate changes extra decisions or games",
    )
    proof_check(proof, old, new, now)
    if candidate_path.exists() and target.exists():
        require(read_file(target) == raw, "pending/exposed candidate bytes differ")
    stage = json.loads(read_file(root / "manifest.json"))
    games = {g["source_item_id"]: g for g in old["games"]}
    ids = sorted(games)
    marker = {
        "old_key": OLD_KEY,
        "old_sha256": OLD_SHA,
        "new_key": new["publication_key"],
        "new_sha256": canonical_sha256(new),
        "candidate_file_sha256": sha256(raw).hexdigest(),
        "curated_file_sha256": CURATED_SHA,
        "undo_receipt_sha256": canonical_sha256(undo),
        "old_test_receipt_sha256": OLD_RECEIPT_SHA,
        "old_test_verification_sha256": OLD_VERIFICATION_SHA,
    }
    reason = "superseded after native TEST880 undo by " + new["publication_key"]
    with _session_lock(engine) as acquired:
        require(acquired, "B session lock held by another run")
        with engine.begin() as conn:
            control = (
                conn.execute(
                    select(CronJobControlDB.__table__)
                    .where(CronJobControlDB.job_name == "kifu_ingest")
                    .with_for_update()
                )
                .mappings()
                .one_or_none()
            )
            require(control is not None and control["paused"] is True, "kifu_ingest must remain paused")
            found = {
                r["publication_key"]: dict(r)
                for r in conn.execute(
                    select(batches)
                    .where(batches.c.publication_key.in_([OLD_KEY, new["publication_key"]]))
                    .with_for_update()
                ).mappings()
            }
            previous = found.get(OLD_KEY)
            following = found.get(new["publication_key"])
            require(previous is not None and previous["manifest_sha256"] == OLD_SHA, "old batch missing or differs")
            require(
                canonical_sha256(previous["test_receipt"]) == OLD_RECEIPT_SHA
                and canonical_sha256(previous["test_verification"]) == OLD_VERIFICATION_SHA,
                "original durable TEST receipt/verification differs",
            )
            require(
                previous["prod_receipt"] is None and previous["prod_verification"] is None,
                "old batch already has PROD publication",
            )
            post = (
                previous["status"] == "quarantined"
                and previous["resume_phase"] == "test_verified"
                and previous["error"] == reason
                and (previous.get("stats") or {}).get("semantic_recovery") == marker
                and (previous.get("stats") or {}).get("native_test_undo_receipt") == undo
            )
            if post:
                require(
                    following is not None
                    and following["status"] == "names_ready"
                    and following["resume_phase"] is None
                    and following["manifest_sha256"] == canonical_sha256(new)
                    and following["attempts"] == 0
                    and following["error"] is None
                    and following["next_retry_at"] is None
                    and all(following[f] is None for f in RECEIPTS),
                    "incomplete switched poststate",
                )
            else:
                require(
                    previous["status"] == "retry_wait"
                    and previous["resume_phase"] == "test_verified"
                    and following is None,
                    "not the complete expected prestate",
                )
                require(candidate_path.exists() and not target.exists(), "prestate candidate must be pending only")
            rows = [
                dict(r)
                for r in conn.execute(
                    select(items)
                    .where(
                        or_(
                            items.c.publication_key.in_([OLD_KEY, new["publication_key"]]),
                            (items.c.source_key == "19x19") & items.c.external_id.in_(ids),
                        )
                    )
                    .order_by(items.c.external_id)
                    .with_for_update()
                ).mappings()
            ]
            require(
                len(rows) == 72 and {r["external_id"] for r in rows} == set(ids), "source72 task membership differs"
            )
            for row in rows:
                game = games[row["external_id"]]
                staged = stage["items"][row["external_id"]]
                path = root / "sgf" / (row["external_id"] + ".sgf")
                require(
                    row["source_key"] == "19x19"
                    and row["status"] == "names_ready"
                    and row["resume_phase"] is None
                    and row["publication_key"] == (new["publication_key"] if post else OLD_KEY),
                    "mixed item key/phase",
                )
                require(
                    all(row[f] is None for f in (*RECEIPTS, "test_album_id", "prod_album_id")),
                    "item has publication receipt/ID",
                )
                require(
                    row["raw_sha256"]
                    == game["raw_sha256"]
                    == staged["raw_sha256"]
                    == sha256(read_file(path)).hexdigest(),
                    "raw SGF hash differs",
                )
                require(
                    row["sgf_sha256"] == game["sgf_sha256"] == sha256(game["sgf_content"].encode()).hexdigest(),
                    "canonical SGF hash differs",
                )
                require(
                    row["staging_path"] == staged["raw_sgf_path"] == str(path) and staged["status"] == "downloaded",
                    "staging path/phase differs",
                )
            native_evidence(conn, old, new, undo)
            proof_check(proof, old, new, datetime.now(timezone.utc) if engine.dialect.name == "postgresql" else now)
            if apply and not post:
                fd = os.open(candidate_path, os.O_RDONLY)
                try:
                    os.fsync(fd)
                finally:
                    os.close(fd)
                fsync_directory(candidate_path.parent)
                fsync_directory(root)
                conn.execute(
                    batches.insert().values(
                        batch_uuid=str(uuid4()),
                        publication_key=new["publication_key"],
                        manifest_sha256=canonical_sha256(new),
                        status="names_ready",
                        attempts=0,
                        created_at=now,
                        updated_at=now,
                    )
                )
                stats = {
                    **(previous.get("stats") or {}),
                    "semantic_recovery": marker,
                    "native_test_undo_receipt": deepcopy(undo),
                    "prod_absence_proof_sha256": canonical_sha256(proof),
                }
                changed = conn.execute(
                    batches.update()
                    .where(
                        batches.c.id == previous["id"],
                        batches.c.status == "retry_wait",
                        batches.c.resume_phase == "test_verified",
                    )
                    .values(
                        status="quarantined",
                        error=reason,
                        stats=stats,
                        attempts=previous["attempts"] + 1,
                        next_retry_at=None,
                        updated_at=now,
                    )
                )
                require(changed.rowcount == 1, "old batch changed concurrently")
                changed = conn.execute(
                    items.update()
                    .where(
                        items.c.source_key == "19x19",
                        items.c.external_id.in_(ids),
                        items.c.status == "names_ready",
                        items.c.publication_key == OLD_KEY,
                    )
                    .values(publication_key=new["publication_key"])
                )
                require(changed.rowcount == 72, "item membership changed concurrently")
        if not apply:
            return {
                "mode": "dry_run",
                "source_count": 72,
                "new_key": new["publication_key"],
                "package_path": str(target),
            }
        if candidate_path.exists():
            os.replace(candidate_path, target)
            fsync_directory(candidate_path.parent)
            fsync_directory(target.parent)
            mode = "recovered_rename" if post else "switched"
        else:
            require(read_file(target) == raw, "completed package differs")
            mode = "already_complete"
        require(sha256(read_file(old_path)).hexdigest() == OLD_FILE_SHA, "old packet bytes changed")
    return {"mode": mode, "source_count": 72, "new_key": new["publication_key"], "package_path": str(target)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--old-packet", type=Path, required=True)
    parser.add_argument("--curated", type=Path, required=True)
    parser.add_argument("--stage-root", type=Path, default=Path("/app/data/kifu_ingest"))
    parser.add_argument("--replacement-decisions", type=Path)
    parser.add_argument("--candidate", type=Path)
    parser.add_argument("--undo-receipt", type=Path)
    parser.add_argument("--prod-proof", type=Path)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--prepare", action="store_true")
    mode.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if args.prepare:
        require(
            args.replacement_decisions is not None
            and args.candidate is None
            and args.undo_receipt is None
            and args.prod_proof is None,
            "prepare consumes reviewed replacements only",
        )
        new = make_candidate(args.old_packet, json.loads(read_file(args.replacement_decisions)), args.curated)
        directory = args.stage_root / "pending-recovery"
        require(
            args.stage_root.is_dir() and not args.stage_root.is_symlink() and not directory.is_symlink(),
            "unsafe pending root",
        )
        directory.mkdir(exist_ok=True)
        raw = json.dumps(new, ensure_ascii=False, sort_keys=True).encode()
        path = directory / (new["games"][0]["source_item_id"] + "-" + canonical_sha256(new)[:16] + ".json")
        if path.exists():
            require(read_file(path) == raw, "candidate file collision")
        else:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "wb") as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
        fsync_directory(directory)
        fsync_directory(args.stage_root)
        print(
            json.dumps(
                {
                    "mode": "prepared_only",
                    "path": str(path),
                    "publication_key": new["publication_key"],
                    "manifest_sha256": canonical_sha256(new),
                    "file_sha256": sha256(raw).hexdigest(),
                    "paid_requests": 0,
                }
            )
        )
        return
    require(
        args.candidate is not None
        and args.undo_receipt is not None
        and args.prod_proof is not None
        and args.replacement_decisions is None,
        "dry-run/apply require candidate, actual undo receipt and fresh PROD proof",
    )
    from katrain.cron.db import engine

    print(
        json.dumps(
            recover(
                engine,
                args.stage_root,
                args.old_packet,
                args.candidate,
                args.curated,
                json.loads(read_file(args.undo_receipt)),
                json.loads(read_file(args.prod_proof)),
                apply=args.apply,
            )
        )
    )


if __name__ == "__main__":
    main()
