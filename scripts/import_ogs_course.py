#!/usr/bin/env python3
"""Read-only OGS plan by default; apply only to the pinned TEST database/storage."""

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from katrain.web.core.config import settings
from katrain.web.tutorials.catalog_import import CatalogImportError, S3PageAssets, verify_apply_target
from katrain.web.tutorials.ogs_import import (
    OgsImportError,
    create_ogs_tables,
    import_ogs_course,
    plan_ogs_course,
    validate_bundle,
)

EXPECTED_TARGET = {
    "expected_db_system_id": 7596941912817897507,
    "expected_db_name": "katrain_db",
    "expected_s3_endpoint": "http://minio:9000",
    "expected_s3_bucket": "tutorial-assets",
    "expected_media_public_base": "https://go.sailorvoyage.top/media",
}


def argument_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", required=True, type=Path)
    parser.add_argument("--report-dir", required=True, type=Path)
    parser.add_argument("--screenshot-root", type=Path)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--apply", action="store_true")
    modes.add_argument("--dry-run", action="store_true")
    for key in EXPECTED_TARGET:
        parser.add_argument("--" + key.replace("_", "-"), type=int if key == "expected_db_system_id" else str)
    return parser


def main(argv=None):
    args = argument_parser().parse_args(argv)
    engine = None
    report = {"mode": "apply" if args.apply else "dry_run"}
    try:
        explicit = {key: getattr(args, key) for key in EXPECTED_TARGET}
        if args.apply and explicit != EXPECTED_TARGET:
            raise OgsImportError(
                "wrong_test_target", "Apply requires all explicit identities of the pinned TEST target"
            )
        bundle = validate_bundle(json.loads(args.bundle.read_text(encoding="utf-8")), require_full=True)
        engine = create_engine(settings.DATABASE_URL, echo=False, pool_pre_ping=True)
        sessions = sessionmaker(bind=engine, expire_on_commit=False)
        if args.apply:
            with sessions() as db:
                report["target"] = verify_apply_target(db, settings, **explicit)
            create_ogs_tables(engine)
            report.update(
                import_ogs_course(
                    sessions,
                    bundle,
                    screenshot_root=args.screenshot_root,
                    asset_store=S3PageAssets(),
                    require_full=True,
                )
            )
        else:
            with sessions() as db:
                if engine.dialect.name == "postgresql":
                    db.execute(text("SET TRANSACTION READ ONLY"))
                elif engine.dialect.name == "sqlite":
                    db.execute(text("PRAGMA query_only=ON"))
                report.update(plan_ogs_course(db, bundle, require_full=True))
        code = 1 if report["status"] == "conflict" else 0
    except Exception as exc:
        if getattr(exc, "report", None):
            report.update(exc.report)
        error = (
            exc.as_dict()
            if isinstance(exc, CatalogImportError)
            else {"code": "ogs_import_failed", "message": "OGS import stopped", "exception": type(exc).__name__}
        )
        report.update(status="failed", error=error)
        code = 2
    finally:
        if engine is not None:
            engine.dispose()
    args.report_dir.mkdir(parents=True, exist_ok=True)
    (args.report_dir / "ogs-import.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {key: report[key] for key in ("mode", "status", "book_id", "counts", "error") if key in report},
            ensure_ascii=False,
        )
    )
    return code


if __name__ == "__main__":
    raise SystemExit(main())
