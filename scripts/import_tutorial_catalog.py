#!/usr/bin/env python3
"""Plan a curriculum catalog; explicitly apply only to the verified TEST target.

Database/storage credentials are inherited from the process settings. This CLI
never runs application startup, full-schema initialization, or the legacy importer.
"""

import argparse
from collections import Counter
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from katrain.web.core.config import settings
from katrain.web.tutorials.catalog_import import (
    CatalogImportError,
    CatalogResult,
    S3PageAssets,
    create_source_tables,
    import_catalog,
    plan_catalog,
    verify_apply_target,
    write_catalog_reports,
)
from katrain.web.tutorials.catalog_sources import load_catalog


def argument_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", required=True, type=Path)
    parser.add_argument(
        "--source-root", required=True, type=Path, help="Allowed curriculum root containing catalog and sources"
    )
    parser.add_argument(
        "--original-source-root", type=Path, help="Former curriculum root for relocated absolute source paths"
    )
    parser.add_argument("--report-dir", required=True, type=Path)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--apply", action="store_true", help="Apply only after verifying all explicit TEST target identities"
    )
    mode.add_argument("--dry-run", action="store_true", help="Read-only plan (the default)")
    parser.add_argument("--expected-db-system-id", type=int)
    parser.add_argument("--expected-db-name")
    parser.add_argument("--expected-s3-endpoint")
    parser.add_argument("--expected-s3-bucket")
    parser.add_argument("--expected-media-public-base")
    return parser


def _failure_results(outcomes, error, mode):
    return [
        CatalogResult(
            outcome.catalog_id,
            "failed",
            mode=mode,
            duplicate_of=outcome.duplicate_of,
            counts={"figures": len(outcome.book.figures), "pages": len(outcome.book.pages)} if outcome.book else {},
            error=outcome.error.as_dict() if outcome.error else error,
        )
        for outcome in outcomes
    ]


def main(argv=None):
    args = argument_parser().parse_args(argv)
    mode = "apply" if args.apply else "dry_run"
    outcomes = []
    results = None
    engine = None
    target = None
    try:
        if args.apply and any(
            value is None
            for value in (
                args.expected_db_system_id,
                args.expected_db_name,
                args.expected_s3_endpoint,
                args.expected_s3_bucket,
                args.expected_media_public_base,
            )
        ):
            raise CatalogImportError(
                "missing_target_identity", "Apply requires all explicit expected target identities"
            )
        outcomes = load_catalog(args.catalog, args.source_root, args.original_source_root)
        engine = create_engine(settings.DATABASE_URL, echo=False, pool_pre_ping=True)
        sessions = sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
        if args.apply:
            with sessions() as session:
                target = verify_apply_target(
                    session,
                    settings,
                    expected_db_system_id=args.expected_db_system_id,
                    expected_db_name=args.expected_db_name,
                    expected_s3_endpoint=args.expected_s3_endpoint,
                    expected_s3_bucket=args.expected_s3_bucket,
                    expected_media_public_base=args.expected_media_public_base,
                )
            create_source_tables(engine)
            results = import_catalog(sessions, outcomes, S3PageAssets())
        else:
            with sessions() as session:
                if engine.dialect.name == "postgresql":
                    session.execute(text("SET TRANSACTION READ ONLY"))
                elif engine.dialect.name == "sqlite":
                    session.execute(text("PRAGMA query_only=ON"))
                results = plan_catalog(session, outcomes)
        write_catalog_reports(args.report_dir, results, target=target)
        print(
            json.dumps(
                {"mode": mode, "summary": dict(Counter(result.status for result in results))}, ensure_ascii=False
            )
        )
        return 1 if any(result.status in {"ambiguous", "failed"} for result in results) else 0
    except Exception as exc:
        if results is not None:
            error = {
                "code": "report_write_failed",
                "exception": type(exc).__name__,
                "message": "Writing catalog reports failed; completed per-book results are preserved",
            }
        elif isinstance(exc, CatalogImportError):
            error = exc.as_dict()
        else:
            error = {
                "code": "catalog_run_failed",
                "exception": type(exc).__name__,
                "message": "Catalog run failed before completion",
            }
        if outcomes:
            try:
                write_catalog_reports(
                    args.report_dir,
                    results if results is not None else _failure_results(outcomes, error, mode),
                    target=target,
                )
            except Exception as report_exc:
                print(f"Fallback report output unavailable: {type(report_exc).__name__}", file=sys.stderr)
        if results is not None:
            print(
                json.dumps(
                    {
                        "mode": mode,
                        "summary": dict(Counter(result.status for result in results)),
                        "completed_books": [
                            {
                                "catalog_id": result.catalog_id,
                                "status": result.status,
                                "book_id": result.book_id,
                                "source_book_id": result.source_book_id,
                            }
                            for result in results
                        ],
                    },
                    ensure_ascii=False,
                )
            )
        print(f"Catalog import stopped: {error['code']}: {error['message']}", file=sys.stderr)
        return 2
    finally:
        if engine is not None:
            engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
