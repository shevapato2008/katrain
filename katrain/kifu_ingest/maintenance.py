"""Explicit bounded collection and audited offline stage maintenance.

No database, translation, model, or publication operations are available here.
Writers share .writer.lock with hourly collection; stop older cron versions
that do not yet honor this lock before applying maintenance.
"""

import argparse
import asyncio
import copy
import hashlib
import json
import os
from pathlib import Path
import time
from uuid import uuid4

import httpx

from katrain.kifu_ingest.source_19x19 import Source19x19
from katrain.kifu_ingest.staging import Stage, _id, discover_and_download, staging_writer_lock

LEGACY_7004_IDS = ("7923089", "7926016", "7928067", "7928304", "7929649", "7929673", "7929683")


def _root(root):
    path = Path(root)
    if not path.is_absolute() or path.is_symlink():
        raise ValueError("staging root must be an absolute non-symlink directory")
    return path.resolve()


def _read(path):
    if path.is_symlink() or not path.is_file():
        raise ValueError("maintenance input must be a regular non-symlink file")
    return path.read_bytes()


def _manifest(root):
    raw = _read(root / "manifest.json")
    document = json.loads(raw)
    if not isinstance(document, dict) or not isinstance(document.get("items"), dict):
        raise ValueError("invalid stage manifest")
    return raw, document


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _write_change(root, action, before_raw, after, matched, *, details=None, after_raw=None):
    directory = root / "maintenance"
    if directory.is_symlink():
        raise ValueError("unsafe maintenance directory")
    directory.mkdir(mode=0o700, exist_ok=True)
    key = uuid4().hex
    backup_path, audit_path = directory / f"{key}.before.json", directory / f"{key}.audit.json"
    if after_raw is None:
        after_raw = json.dumps(after, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
    before = json.loads(before_raw)
    audit = {
        "version": 1,
        "action": action,
        "staging_root": str(root),
        "created_at": time.time(),
        "pre_sha256": _sha(before_raw),
        "post_sha256": _sha(after_raw),
        "backup_path": str(backup_path),
        "matched_ids": matched,
        "before_items": {i: before["items"][i] for i in matched},
        "after_items": {i: after["items"][i] for i in matched},
        "details": details or {},
    }
    Stage._atomic(backup_path, before_raw)
    Stage._atomic(audit_path, json.dumps(audit, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8"))
    # All callers acquired the writer lock before loading the exact preimage.
    if _sha(_read(root / "manifest.json")) != audit["pre_sha256"]:
        raise ValueError("manifest preimage changed before apply")
    Stage._atomic(root / "manifest.json", after_raw)
    return {
        "dry_run": False,
        "matched_ids": matched,
        "audit_path": str(audit_path),
        "pre_sha256": audit["pre_sha256"],
        "post_sha256": audit["post_sha256"],
    }


def migrate_legacy_7004(staging_root, *, apply=False):
    """Only the seven exact failed/error matches; default is a read-only preview."""
    root = _root(staging_root)

    def operation():
        before_raw, manifest = _manifest(root)
        matched = [
            i
            for i in LEGACY_7004_IDS
            if i in manifest["items"]
            and manifest["items"][i].get("status") == "failed"
            and manifest["items"][i].get("last_error") == "source business error: 7004"
            and not manifest["items"][i].get("recent", {}).get("terminal")
        ]
        if not apply or not matched:
            return {"dry_run": not apply, "matched_ids": matched, "pre_sha256": _sha(before_raw)}
        for i in matched:
            item = manifest["items"][i]
            item["next_retry_at"] = None
            item.setdefault("recent", {}).update(terminal=True, classification="legacy_shared_7004", error_code=7004)
        return _write_change(root, "migrate-7004", before_raw, manifest, matched)

    if apply:
        with staging_writer_lock(root):
            return operation()
    return operation()


def restore_item(staging_root, external_id, *, apply=False):
    """Explicit one-ID retry reset; preserve originals, total attempts and evidence."""
    root, external_id = _root(staging_root), _id(external_id)

    def operation():
        before_raw, manifest = _manifest(root)
        if external_id not in manifest["items"]:
            raise ValueError("unknown external_id")
        item = manifest["items"][external_id]
        if not apply:
            return {"dry_run": True, "matched_ids": [external_id], "item": copy.deepcopy(item)}
        observation = item.setdefault("recent", {})
        observation.update(
            terminal=False,
            retry_pending=False,
            failure_attempts=0,
            last_checked_at=None,
            classification="manual_restore",
        )
        item["next_retry_at"] = 0
        if item["status"] == "failed":
            item["status"] = "downloaded" if item.get("raw_sgf_path") else "pending"
        return _write_change(root, "restore-item", before_raw, manifest, [external_id])

    if apply:
        with staging_writer_lock(root):
            return operation()
    return operation()


def rollback(staging_root, audit_path, *, apply=False):
    """Restore the exact backup only while the current postimage still matches."""
    root = _root(staging_root)
    path = Path(audit_path)
    directory = root / "maintenance"
    if directory.is_symlink() or path.parent != directory or path.is_symlink():
        raise ValueError("audit must be inside the stage maintenance directory")

    def operation():
        audit = json.loads(_read(path))
        if audit.get("staging_root") != str(root):
            raise ValueError("audit staging root mismatch")
        backup = Path(audit["backup_path"])
        if backup.parent != directory:
            raise ValueError("backup must be inside the stage maintenance directory")
        old_raw = _read(backup)
        if _sha(old_raw) != audit["pre_sha256"]:
            raise ValueError("backup preimage digest mismatch")
        current_raw, current = _manifest(root)
        if _sha(current_raw) != audit["post_sha256"]:
            raise ValueError("manifest postimage changed; rollback refused")
        if not apply:
            return {"dry_run": True, "matched_ids": audit["matched_ids"], "audit_path": str(path)}
        # Keep a separate rollback audit/preimage; neither prior record is deleted.
        result = _write_change(
            root,
            "rollback",
            current_raw,
            json.loads(old_raw),
            audit["matched_ids"],
            details={"rolled_back_audit": str(path)},
            after_raw=old_raw,
        )
        return result

    if apply:
        with staging_writer_lock(root):
            return operation()
    return operation()


async def collect_history(
    source,
    staging_root,
    hourly_staging_root,
    *,
    pages,
    max_downloads,
    max_requests,
    seconds,
    start_page=0,
    clock=time.monotonic,
):
    """Manual finite collection into an independent root; never prepares/publishes."""
    root, hourly = _root(staging_root), _root(hourly_staging_root)
    configured = _root(os.getenv("CRON_KIFU_INGEST_STAGING_DIR", "/app/data/kifu_ingest"))
    if any(root == other or root in other.parents or other in root.parents for other in (hourly, configured)):
        raise ValueError("history staging root must be independent of hourly staging root")
    for name, value, maximum in (
        ("pages", pages, 100),
        ("max_downloads", max_downloads, 100),
        ("max_requests", max_requests, 500),
        ("seconds", seconds, 1800),
    ):
        if type(value) is not int or not 1 <= value <= maximum:
            raise ValueError(f"{name} must be between 1 and {maximum}")
    if type(start_page) is not int or start_page < 0:
        raise ValueError("start_page must be nonnegative")
    deadline = clock() + seconds
    source.deadline = min(source.deadline, deadline) if source.deadline is not None else deadline
    source.max_requests = min(source.max_requests, source.requests + max_requests)

    class Pages:
        async def fetch_page(self, page):
            return await source.fetch_page(start_page + page)

        async def fetch_sgf(self, external_id):
            return await source.fetch_sgf(external_id)

    with staging_writer_lock(root):
        stage = Stage(root)
        stage.manifest["collection_mode"] = "manual-history"
        stage._persist()
        return await asyncio.wait_for(
            discover_and_download(
                Pages(),
                stage,
                max_head_pages=pages,
                max_rolling_pages=0,
                max_downloads=max_downloads,
                deadline=deadline,
                clock=clock,
            ),
            max(0, deadline - clock()),
        )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("migrate-7004", "restore-item", "rollback", "collect-history"):
        command = commands.add_parser(name)
        command.add_argument("--staging-root", required=True)
        if name != "collect-history":
            command.add_argument("--apply", action="store_true", help="write changes; default is dry-run")
        if name == "restore-item":
            command.add_argument("--external-id", required=True)
        elif name == "rollback":
            command.add_argument("--audit", required=True)
        elif name == "collect-history":
            command.add_argument(
                "--hourly-staging-root", default=os.getenv("CRON_KIFU_INGEST_STAGING_DIR", "/app/data/kifu_ingest")
            )
            command.add_argument("--start-page", type=int, default=0)
            for field in ("pages", "max-downloads", "max-requests", "seconds"):
                command.add_argument("--" + field, type=int, required=True)
    args = parser.parse_args(argv)
    if args.command == "migrate-7004":
        result = migrate_legacy_7004(args.staging_root, apply=args.apply)
    elif args.command == "restore-item":
        result = restore_item(args.staging_root, args.external_id, apply=args.apply)
    elif args.command == "rollback":
        result = rollback(args.staging_root, args.audit, apply=args.apply)
    else:

        async def collect():
            async with httpx.AsyncClient() as client:
                return await collect_history(
                    Source19x19(client),
                    args.staging_root,
                    args.hourly_staging_root,
                    pages=args.pages,
                    max_downloads=args.max_downloads,
                    max_requests=args.max_requests,
                    seconds=args.seconds,
                    start_page=args.start_page,
                )

        result = asyncio.run(collect())
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
