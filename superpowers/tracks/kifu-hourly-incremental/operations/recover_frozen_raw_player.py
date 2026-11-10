"""One-off recovery of frozen72 / decision17; no model or publisher calls.

--prepare consumes an already actually produced/reviewed replacement decision and
writes a candidate outside packages. Default recovery is dry-run. --apply requires
fresh root-collected PROD proof, the existing session lock and a paused B job.
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

OLD_FILE_SHA = "b01b1c63eb07842a7ece2f927ffef8815e656c7ab22f5ca4093c439f6f88d083"
OLD_SHA = "8604c27f9b9a9b47a6e2309938144f45d6e05d05efd0c80cf5736b53fad9e96d"
OLD_KEY = "19x19-batch-dd279a0c3a6e99f61304827b"
RECEIPTS = ("test_receipt", "test_verification", "prod_receipt", "prod_verification")


def require(ok, message):
    if not ok:
        raise ValueError(message)


def read_file(path):
    path = Path(path)
    require(path.is_file() and not path.is_symlink(), "missing or unsafe file: " + str(path))
    return path.read_bytes()


def old_packet(path):
    raw = read_file(path)
    require(sha256(raw).hexdigest() == OLD_FILE_SHA, "old frozen file hash differs")
    old = json.loads(raw)
    require(canonical_sha256(old) == OLD_SHA and old["publication_key"] == OLD_KEY, "old frozen identity differs")
    require(len(old["games"]) == 72 and len(old["decisions"]) == 18, "expected exactly72 games/18 decisions")
    _validate_manifest(old, OLD_SHA)
    return old


def make_candidate(old_path, replacement):
    old = old_packet(old_path)
    previous = old["decisions"][17]
    validate_decision(replacement)
    require(
        previous["kind"] == replacement["kind"] == "raw_player" and previous["key"] == replacement["key"] == "姜勋",
        "only decision17姜勋 is recoverable",
    )
    fields = {"original_language", "methods", "producer", "review", "cn_conversion_note"}
    require(
        {k: v for k, v in replacement.items() if k not in fields}
        == {k: v for k, v in previous.items() if k not in fields},
        "replacement changed immutable text, sources or finite source_items",
    )
    methods = dict(previous["methods"], jp="transliteration")
    require(
        replacement["original_language"] == "und" and replacement["methods"] == methods,
        "replacement differs from retained native template",
    )
    require(
        all(replacement[role]["request_id"] != previous[role]["request_id"] for role in ("producer", "review")),
        "replacement needs new actual producer/reviewer requests",
    )
    new = deepcopy(old)
    new["decisions"][17] = deepcopy(replacement)
    new["publication_key"] = "19x19-recovery-" + canonical_sha256(replacement)[:24]
    _validate_manifest(new, canonical_sha256(new))
    return new


def proof_check(proof, old, new, now):
    require(proof.get("version") == "kifu-frozen-recovery-proof-v1", "PROD proof version differs")
    checked = datetime.fromisoformat(proof["checked_at"].replace("Z", "+00:00"))
    require(
        checked.tzinfo is not None and 0 <= (now - checked).total_seconds() <= 600,
        "PROD proof must be fresh within10 minutes",
    )
    for label, packet in [("old", old), ("new", new)]:
        require(
            proof.get(label)
            == {"publication_key": packet["publication_key"], "manifest_sha256": canonical_sha256(packet)},
            "PROD proof packet binding differs",
        )
    require(proof.get("source_ids") == sorted(g["source_item_id"] for g in old["games"]), "PROD proof source72 differs")
    expected = {
        "old_digest": True,
        "old_key": True,
        "new_digest": True,
        "new_key": True,
        "source_presence": 0,
        "source_link_count": 0,
        "source_primary_count": 0,
    }
    require(
        proof.get("native_absent") == expected
        and all(proof["native_absent"][k] is True for k in ("old_digest", "old_key", "new_digest", "new_key")),
        "PROD has native presence or absence proof is incomplete",
    )
    d = new["decisions"][17]
    require(
        proof.get("template") == {k: d[k] for k in ("kind", "key", "displays", "original_language", "methods")},
        "PROD qualified template differs from approved replacement",
    )


def native_absent(conn, old, new):
    """Exact packet identities and actual source link/primary presence, no JSON-array scan."""
    keys = [old["publication_key"], new["publication_key"]]
    digests = [canonical_sha256(old), canonical_sha256(new)]
    for digest in digests:
        require(
            conn.scalar(select(func.count()).select_from(KifuNameBatch).where(KifuNameBatch.bundle_sha256 == digest))
            == 0,
            "TEST native bundle receipt exists",
        )
    for key in keys:
        require(
            conn.scalar(
                select(func.count())
                .select_from(KifuNameBatch)
                .where(cast(KifuNameBatch.reviewed_artifact, Text).contains(key))
            )
            == 0,
            "TEST native publication key text exists; reconcile any conservative match",
        )
    paths = [g["origin_path"] for g in old["games"]]
    linked = conn.scalar(
        select(func.count())
        .select_from(KifuAlbumSource)
        .join(KifuSource, KifuSource.id == KifuAlbumSource.source_id)
        .where(KifuSource.source_key == "19x19", KifuAlbumSource.origin_path.in_(paths))
    )
    primary = conn.scalar(select(func.count()).select_from(KifuAlbum).where(KifuAlbum.source_path.in_(paths)))
    require(linked == primary == 0, "TEST has native source link/primary presence for source72")


def fsync_directory(path):
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def recover(engine, root, old_path, candidate_path, proof, *, apply=False, now=None):
    now = now or datetime.now(timezone.utc)
    root, old_path, candidate_path = Path(root), Path(old_path), Path(candidate_path)
    require(root.is_absolute() and root.is_dir() and not root.is_symlink(), "unsafe stage root")
    require(
        candidate_path.parent == root / "pending-recovery" and not candidate_path.parent.is_symlink(),
        "candidate must be outside scan range in pending-recovery",
    )
    require(
        old_path.parent == root / "packages" and not old_path.parent.is_symlink(), "old packet must remain in packages"
    )
    target = root / "packages" / candidate_path.name
    require(
        not target.is_symlink() and os.stat(candidate_path.parent).st_dev == os.stat(target.parent).st_dev,
        "candidate rename must stay on same filesystem",
    )
    old = old_packet(old_path)
    raw = read_file(candidate_path if candidate_path.exists() else target)
    new = json.loads(raw)
    require(
        new == make_candidate(old_path, new["decisions"][17]), "candidate differs outside decision17/publication key"
    )
    proof_check(proof, old, new, now)
    if candidate_path.exists() and target.exists():
        require(read_file(target) == raw, "exposed candidate bytes differ")
    stage = json.loads(read_file(root / "manifest.json"))
    games = {g["source_item_id"]: g for g in old["games"]}
    ids = sorted(games)
    marker = {
        "old_key": OLD_KEY,
        "old_sha256": OLD_SHA,
        "new_key": new["publication_key"],
        "new_sha256": canonical_sha256(new),
        "candidate_file_sha256": sha256(raw).hexdigest(),
    }
    reason = "superseded by " + new["publication_key"]
    with _session_lock(engine) as acquired:
        require(acquired, "B session lock is held by another run")
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
            found = [
                dict(r)
                for r in conn.execute(
                    select(batches)
                    .where(batches.c.publication_key.in_([OLD_KEY, new["publication_key"]]))
                    .with_for_update()
                ).mappings()
            ]
            by_key = {r["publication_key"]: r for r in found}
            previous = by_key.get(OLD_KEY)
            following = by_key.get(new["publication_key"])
            require(
                previous is not None
                and previous["manifest_sha256"] == OLD_SHA
                and all(previous[f] is None for f in RECEIPTS),
                "old batch identity/receipts differ",
            )
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
                len(rows) == 72
                and {r["external_id"] for r in rows} == set(ids)
                and all(r["source_key"] == "19x19" for r in rows),
                "source72 task membership differs",
            )
            post = (
                previous["status"] == "quarantined"
                and previous["resume_phase"] == "names_ready"
                and previous["error"] == reason
                and (previous.get("stats") or {}).get("frozen_recovery") == marker
            )
            if post:
                require(
                    following is not None
                    and following["status"] == "names_ready"
                    and following["resume_phase"] is None
                    and following["attempts"] == 0
                    and following["error"] is None
                    and following["manifest_sha256"] == canonical_sha256(new)
                    and all(following[f] is None for f in RECEIPTS),
                    "incomplete switched batch state",
                )
            else:
                require(
                    previous["status"] == "retry_wait"
                    and previous["resume_phase"] == "names_ready"
                    and following is None,
                    "not the complete expected prestate",
                )
                require(candidate_path.exists() and not target.exists(), "prestate candidate must be pending only")
            expected_key = new["publication_key"] if post else OLD_KEY
            for row in rows:
                game = games[row["external_id"]]
                staged = stage["items"][row["external_id"]]
                path = root / "sgf" / (row["external_id"] + ".sgf")
                require(
                    row["status"] == "names_ready"
                    and row["resume_phase"] is None
                    and row["publication_key"] == expected_key,
                    "mixed item phase/key state",
                )
                require(
                    all(row[f] is None for f in (*RECEIPTS, "test_album_id", "prod_album_id")),
                    "item publication receipt/ID exists",
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
            native_absent(conn, old, new)
            # Recheck proof age after bounded readonly native checks, before any write.
            proof_check(proof, old, new, datetime.now(timezone.utc) if engine.dialect.name == "postgresql" else now)
            if apply and not post:
                # Durable pending name and bytes must exist before committing membership.
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
                    "frozen_recovery": marker,
                    "prod_absence_proof_sha256": canonical_sha256(proof),
                }
                changed = conn.execute(
                    batches.update()
                    .where(
                        batches.c.id == previous["id"],
                        batches.c.status == "retry_wait",
                        batches.c.resume_phase == "names_ready",
                    )
                    .values(
                        status="quarantined",
                        error=reason,
                        stats=stats,
                        next_retry_at=None,
                        attempts=previous["attempts"] + 1,
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
            for directory in (target.parent, candidate_path.parent):
                fsync_directory(directory)
            mode = "recovered_rename" if post else "switched"
        else:
            require(read_file(target) == raw, "completed package differs")
            mode = "already_complete"
        require(
            read_file(old_path) and sha256(read_file(old_path)).hexdigest() == OLD_FILE_SHA, "old frozen bytes changed"
        )
    return {"mode": mode, "source_count": 72, "new_key": new["publication_key"], "package_path": str(target)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--old-packet", type=Path, required=True)
    parser.add_argument("--stage-root", type=Path, default=Path("/app/data/kifu_ingest"))
    parser.add_argument("--replacement-decision", type=Path)
    parser.add_argument("--candidate", type=Path)
    parser.add_argument("--prod-proof", type=Path)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--prepare", action="store_true")
    mode.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if args.prepare:
        require(
            args.replacement_decision is not None and args.candidate is None and args.prod_proof is None,
            "prepare takes replacement-decision only",
        )
        new = make_candidate(args.old_packet, json.loads(read_file(args.replacement_decision)))
        directory = args.stage_root / "pending-recovery"
        require(
            args.stage_root.is_dir() and not args.stage_root.is_symlink() and not directory.is_symlink(),
            "unsafe pending root",
        )
        directory.mkdir(exist_ok=True)
        path = directory / (new["games"][0]["source_item_id"] + "-" + canonical_sha256(new)[:16] + ".json")
        raw = json.dumps(new, ensure_ascii=False, sort_keys=True).encode()
        if path.exists():
            require(read_file(path) == raw, "pending candidate exists with different bytes")
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
                    "candidate_path": str(path),
                    "publication_key": new["publication_key"],
                    "manifest_sha256": canonical_sha256(new),
                    "file_sha256": sha256(raw).hexdigest(),
                    "paid_requests": 0,
                }
            )
        )
        return
    require(
        args.candidate is not None and args.prod_proof is not None and args.replacement_decision is None,
        "dry-run/apply require candidate and prod-proof",
    )
    from katrain.cron.db import engine

    print(
        json.dumps(
            recover(
                engine,
                args.stage_root,
                args.old_packet,
                args.candidate,
                json.loads(read_file(args.prod_proof)),
                apply=args.apply,
            )
        )
    )


if __name__ == "__main__":
    main()
