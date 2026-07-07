#!/usr/bin/env python3
"""Migrate tutorial media (video/audio/page images) from the local filesystem
into the configured S3-compatible object store (MinIO phase 1 / Aliyun OSS phase 2).

Task 5 of superpowers/tracks/tutorial-database/plan.md.

* Idempotent: an object already present with the same byte size is skipped, so
  re-runs are cheap and safe.
* Non-destructive (D8): local files are never touched — the object store is a
  distribution copy, local stays the authoritative mirror.
* Verifies counts at the end (every local file must exist in the bucket).

Usage (run with the SAME storage env the app uses, i.e. STORAGE_BACKEND=s3):
    KATRAIN_STORAGE_BACKEND=s3 \
    KATRAIN_S3_ENDPOINT_URL=http://localhost:9000 \
    KATRAIN_S3_BUCKET=tutorial-assets \
    KATRAIN_S3_ACCESS_KEY=... KATRAIN_S3_SECRET_KEY=... \
    python scripts/migrate_assets_to_minio.py [--data-dir DIR] [--book SLUG]
                                              [--force] [--dry-run]

Equivalent one-liner with the MinIO client:
    mc mirror ./data/tutorial_assets local/tutorial-assets/tutorial_assets
"""
import argparse
import mimetypes
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))

from katrain.web.core.storage import get_storage_backend  # noqa: E402
from katrain.web.core.storage.base import normalize_key  # noqa: E402


def iter_asset_files(root: Path, book: str | None):
    base = root if book is None else (root / book)
    if not base.exists():
        raise SystemExit(f"Asset dir not found: {base}")
    for path in sorted(base.rglob("*")):
        if path.is_file():
            yield path


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--data-dir",
        default=str(REPO_ROOT / "data" / "tutorial_assets"),
        help="Local tutorial_assets directory (default: <repo>/data/tutorial_assets)",
    )
    ap.add_argument("--book", default=None, help="Only migrate one book slug subdir")
    ap.add_argument("--force", action="store_true", help="Re-upload even if size matches")
    ap.add_argument("--dry-run", action="store_true", help="Report actions without uploading")
    args = ap.parse_args()

    data_dir = Path(args.data_dir).resolve()
    # Key root is the parent of tutorial_assets so keys look like "tutorial_assets/<book>/..."
    key_root = data_dir.parent

    backend = get_storage_backend()
    if not backend.is_remote:
        raise SystemExit(
            "STORAGE_BACKEND is not a remote (s3) backend — nothing to migrate to. "
            "Set KATRAIN_STORAGE_BACKEND=s3 and the S3_* env vars."
        )

    print(f"Source : {data_dir}")
    print(f"Target : {backend.__class__.__name__} (bucket via S3_* config)")
    print(f"Mode   : {'DRY RUN' if args.dry_run else 'UPLOAD'}{' (force)' if args.force else ''}\n")

    uploaded = skipped = failed = total = 0
    for path in iter_asset_files(data_dir, args.book):
        total += 1
        key = normalize_key(str(path.relative_to(key_root)))
        local_size = path.stat().st_size

        if not args.force and backend.exists(key) and backend.size(key) == local_size:
            skipped += 1
            continue

        if args.dry_run:
            print(f"  would upload  {key}  ({local_size} B)")
            uploaded += 1
            continue

        content_type = mimetypes.guess_type(key)[0]
        try:
            with open(path, "rb") as f:
                backend.put(key, f, content_type=content_type)
            uploaded += 1
            if uploaded % 100 == 0:
                print(f"  ...{uploaded} uploaded")
        except Exception as e:  # noqa: BLE001
            failed += 1
            print(f"  FAILED  {key}: {e}")

    print(f"\nScanned {total} files: {uploaded} uploaded, {skipped} skipped, {failed} failed.")

    # ── verification (count parity) ─────────────────────────────────────────
    if args.dry_run:
        return
    print("Verifying every local file exists in the bucket...")
    missing = [
        normalize_key(str(p.relative_to(key_root)))
        for p in iter_asset_files(data_dir, args.book)
        if not backend.exists(normalize_key(str(p.relative_to(key_root))))
    ]
    if missing:
        print(f"  ✗ {len(missing)} objects missing, e.g. {missing[:5]}")
        raise SystemExit(1)
    print(f"  ✓ all {total} local files present in bucket. Local copies untouched (D8).")


if __name__ == "__main__":
    main()
