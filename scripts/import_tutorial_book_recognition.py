#!/usr/bin/env python3
"""Incrementally import a complete non-Ishida GPT book into the verified TEST catalog.

Dry run is the default and enforces a database read-only transaction. Credentials
come only from the existing private application settings/environment. Apply must
name the TEST database/storage identities; schema creation is a separate explicit
flag and creates only tutorial_recognition_candidates.
"""

import argparse
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from katrain.web.core.config import settings
from katrain.web.tutorials.catalog_import import CatalogImportError, verify_apply_target
from katrain.web.tutorials.recognition_catalog_import import (
    RecognitionImportError,
    apply_recognition,
    create_recognition_table,
    load_catalog_recognition,
    plan_recognition,
    write_recognition_reports,
)


def argument_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", required=True, type=Path)
    parser.add_argument("--book-json", required=True, type=Path)
    parser.add_argument("--pdf", required=True, type=Path)
    parser.add_argument(
        "--expected-pdf-pages", required=True, type=int, help="Actual PDF page count from independent source inventory"
    )
    parser.add_argument("--recognition-index", type=Path, help="Defaults to sibling recognition-index.json if present")
    parser.add_argument(
        "--pending-annotation-manifest",
        type=Path,
        help="Explicit hash-bound Joseki p182 candidate-only delivery; preserves both holds",
    )
    parser.add_argument("--catalog-id", required=True)
    parser.add_argument("--dataset", required=True, help="Stable recognition dataset identity; never a timestamp")
    parser.add_argument("--report-dir", required=True, type=Path)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--apply", action="store_true")
    mode.add_argument("--dry-run", action="store_true", help="Read-only plan (default)")
    parser.add_argument("--create-schema", action="store_true", help="Explicitly create only the recognition table")
    parser.add_argument("--expected-env", choices=["test"])
    parser.add_argument("--expected-db-system-id", type=int)
    parser.add_argument("--expected-db-name")
    parser.add_argument("--expected-s3-endpoint")
    parser.add_argument("--expected-s3-bucket")
    parser.add_argument("--expected-media-public-base")
    return parser


def _guard_mode(args):
    if args.create_schema and not args.apply:
        raise RecognitionImportError("--create-schema requires explicit --apply and verified TEST identity")
    if args.expected_env != "test" or os.getenv("KATRAIN_ADMIN_ENV") != "test":
        raise RecognitionImportError("all generic import modes require --expected-env test and KATRAIN_ADMIN_ENV=test")


def main(argv=None):
    args = argument_parser().parse_args(argv)
    engine, report = None, None
    mode = "apply" if args.apply else "dry_run"
    try:
        _guard_mode(args)
        index = args.recognition_index
        if index is None and args.results.with_name("recognition-index.json").exists():
            index = args.results.with_name("recognition-index.json")
        if index is None:
            raise RecognitionImportError("generic book import requires its immutable recognition index")
        batch = load_catalog_recognition(
            args.results,
            args.book_json,
            index_path=index,
            catalog_id=args.catalog_id,
            pdf_path=args.pdf,
            expected_pdf_pages=args.expected_pdf_pages,
            dataset=args.dataset,
            pending_annotation_manifest=args.pending_annotation_manifest,
        )
        engine = create_engine(settings.DATABASE_URL, echo=False, pool_pre_ping=True)
        sessions = sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
        target = None
        with sessions() as db:
            if engine.dialect.name == "postgresql":
                db.execute(text("SET TRANSACTION READ ONLY"))
            target = verify_apply_target(
                db,
                settings,
                expected_db_system_id=args.expected_db_system_id,
                expected_db_name=args.expected_db_name,
                expected_s3_endpoint=args.expected_s3_endpoint,
                expected_s3_bucket=args.expected_s3_bucket,
                expected_media_public_base=args.expected_media_public_base,
            )
        if args.apply:
            if args.create_schema:
                create_recognition_table(engine)
            # Fresh live resolution and eligibility checks occur inside the write transaction.
            report = apply_recognition(sessions, batch, catalog_id=args.catalog_id, dataset=args.dataset)
        else:
            with sessions() as db:
                if engine.dialect.name == "postgresql":
                    db.execute(text("SET TRANSACTION READ ONLY"))
                elif engine.dialect.name == "sqlite":
                    db.execute(text("PRAGMA query_only=ON"))
                report = plan_recognition(db, batch, catalog_id=args.catalog_id, dataset=args.dataset)
        value = report.as_dict()
        value["verified_target"] = target
        write_recognition_reports(args.report_dir, value)
        print(
            json.dumps(
                {
                    "mode": mode,
                    "book_id": report.book_id,
                    "source_book_id": report.source_book_id,
                    "counts": value["counts"],
                },
                ensure_ascii=False,
            )
        )
        return 1 if any(row["status"] == "failed" for row in report.rows) else 0
    except Exception as exc:
        # Database/driver exceptions can contain connection URLs; never emit their raw text.
        error = str(exc) if isinstance(exc, (RecognitionImportError, CatalogImportError)) else type(exc).__name__
        value = (
            report.as_dict()
            if report is not None
            else {"mode": mode, "catalog_id": args.catalog_id, "dataset": args.dataset, "rows": []}
        )
        value["error"] = error
        value["transaction_status"] = "rolled_back" if args.apply and report is None else "not_completed"
        try:
            write_recognition_reports(args.report_dir, value)
        except Exception:
            print("Recognition report could not be written", file=sys.stderr)
        print(f"Recognition import stopped: {error}", file=sys.stderr)
        return 2
    finally:
        if engine is not None:
            engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
