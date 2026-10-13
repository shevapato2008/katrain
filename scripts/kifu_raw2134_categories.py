"""Finite CAS approval of the three reviewed raw-event descriptions (no names/FKs).

Uses the existing name-batch lock, change journal and undo command. Dry-run is
read-only. A separately reviewed plan and exact hash are mandatory for apply.
"""

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path

from sqlalchemy import create_engine, select, text

from katrain.web.core.models_db import (
    KifuAlbum,
    KifuAlbumEventSelection,
    KifuAlbumSource,
    KifuNameBatch,
    KifuRawEventName,
    KifuRawEventValue,
    KifuSource,
)
from katrain.web.kifu.name_batch import (
    BatchError,
    _catalog_sha,
    _fail,
    _image,
    _insert,
    _locked_write,
    _record_change,
    _source_registry_for_batch,
    _values_for_table,
)
from katrain.web.kifu.name_candidates import (
    _check_signature,
    canonical_sha256,
    validate_archive_description_scope,
)
from katrain.web.kifu.name_evidence import registry_sha256
from katrain.web.kifu.name_inventory import ASSOCIATION_COLUMNS

EXPECTED = {"段位赛": 901, "个人赛": 638, "Hoensha game": 595}
ALLOWED_FIELDS = {"category", "parser_version", "review_status", "review_metadata"}


def inspect_plan(conn, plan, registry):
    _check_signature(plan)
    _fail(plan.get("review_status") == "approved", "category plan is not independently approved")
    _fail(
        plan.get("operation") == "raw2134-category-v1" and plan.get("bundle_format") == 2,
        "unknown finite category operation",
    )
    _fail(plan.get("registry_sha256") == registry_sha256(registry), "registry differs")
    changes = plan.get("changes", [])
    _fail(
        len(changes) == 3 and {c["before"]["raw_value"] for c in changes} == set(EXPECTED),
        "category plan must contain exactly the three reviewed raw values",
    )
    _fail(_catalog_sha(conn) == plan["catalog_sha256"], "catalog preimage changed")
    for change in changes:
        before, after = change["before"], change["after"]
        raw = before["raw_value"]
        _fail(
            set(before) == set(after) and {k for k in before if before[k] != after[k]} <= ALLOWED_FIELDS,
            "category plan changes fields outside finite approval",
        )
        _fail(
            before["review_status"] == "pending" and after["review_status"] == "approved",
            "category approval requires pending owner preimage",
        )
        _fail(_image(conn, KifuRawEventValue.__table__, before["id"]) == before, "raw owner preimage changed")
        _fail(
            conn.scalar(select(KifuRawEventName.id).where(KifuRawEventName.raw_event_id == before["id"]).limit(1))
            is None,
            "raw owner already has names",
        )
        ids = list(
            conn.execute(
                text(
                    "SELECT id FROM kifu_albums WHERE event=:raw AND event_id IS NULL AND duplicate_of_id IS NULL "
                    "AND list_hidden_reason IS NULL ORDER BY id"
                ),
                {"raw": raw},
            ).scalars()
        )
        _fail(len(ids) == EXPECTED[raw] and ids == change["occurrence_album_ids"], "raw occurrence scope changed")
        review = after["review_metadata"]
        _check_signature(
            dict(review, review_status=review.get("status"), review_conclusion=review.get("category_basis"))
        )
        _fail(review.get("status") == "approved", "raw category review is pending")
        if raw == "Hoensha game":
            declaration = change["archive_declaration"]
            _fail(
                declaration["preimage"] == after
                and declaration["category_review"] == review
                and declaration["owner"] == {"kind": "raw_event", "id": before["id"]},
                "archive declaration differs from approved owner after-image",
            )
            validate_archive_description_scope(
                {"inventory_sha256": plan["inventory_sha256"], "declaration": declaration},
                registry=registry,
                check_files=True,
            )
            rows = [
                dict(r, sources=[])
                for r in conn.execute(
                    select(*(getattr(KifuAlbum, key) for key in ASSOCIATION_COLUMNS[:-1]))
                    .where(KifuAlbum.id.in_(ids))
                    .order_by(KifuAlbum.id)
                ).mappings()
            ]
            by_id = {r["id"]: r for r in rows}
            for source in conn.execute(
                select(
                    KifuAlbumSource.album_id,
                    KifuAlbumSource.id,
                    KifuAlbumSource.source_id,
                    KifuSource.source_key,
                    KifuAlbumSource.origin_path,
                    KifuAlbumSource.match_method,
                )
                .join(KifuSource, KifuSource.id == KifuAlbumSource.source_id)
                .where(KifuAlbumSource.album_id.in_(ids))
                .order_by(KifuAlbumSource.id)
            ):
                by_id[source[0]]["sources"].append(list(source[1:]))
            _fail(rows == review["archive_basis"]["occurrence_rows"], "archive source/album context changed")
            _fail(
                conn.scalar(
                    select(KifuAlbumEventSelection.album_id).where(KifuAlbumEventSelection.album_id.in_(ids)).limit(1)
                )
                is None,
                "archive scope gained a selected event",
            )
        else:
            _fail(
                after["category"] == "generic_event_description"
                and after["parser_version"] == before["parser_version"],
                "generic category or parser version changed",
            )
    return {"ready": True, "raw_owners": 3, "albums": sum(EXPECTED.values()), "name_writes": 0, "fk_writes": 0}


def apply_plan(engine, plan, registry, expected_sha256):
    digest = canonical_sha256(plan)
    _fail(digest == expected_sha256, "category plan hash differs from independently reviewed bytes")
    with _locked_write(engine) as conn:
        previous = (
            conn.execute(select(KifuNameBatch.__table__).where(KifuNameBatch.bundle_sha256 == digest))
            .mappings()
            .one_or_none()
        )
        if previous:
            _fail(
                previous["status"] == "applied" and previous["reviewed_artifact"]["bundle"] == plan,
                "prior category batch is not an unchanged applied plan",
            )
            _fail(
                all(_image(conn, KifuRawEventValue.__table__, c["after"]["id"]) == c["after"] for c in plan["changes"]),
                "category replay after-image changed",
            )
            return {"status": "already_applied", "batch_id": previous["id"], "change_count": 0}
        report = inspect_plan(conn, plan, registry)
        registry_id, _ = _source_registry_for_batch(conn, registry, plan)
        batch_id, _ = _insert(
            conn,
            KifuNameBatch,
            {
                "bundle_sha256": digest,
                "inventory_sha256": plan["inventory_sha256"],
                "source_registry_id": registry_id,
                "reviewed_artifact": {"bundle": plan},
                "status": "pending",
            },
        )
        for sequence, change in enumerate(plan["changes"], 1):
            before, after = change["before"], change["after"]
            table = KifuRawEventValue.__table__
            conn.execute(
                table.update()
                .where(table.c.id == before["id"])
                .values(**_values_for_table(table, {k: after[k] for k in ALLOWED_FIELDS}))
            )
            _fail(_image(conn, table, before["id"]) == after, "raw category after-image differs")
            _record_change(conn, batch_id, sequence, KifuRawEventValue, before["id"], before, after)
        _fail(_catalog_sha(conn) == plan["catalog_after_sha256"], "category catalog after-image differs")
        conn.execute(
            KifuNameBatch.__table__.update()
            .where(KifuNameBatch.id == batch_id)
            .values(status="applied", applied_at=datetime.now(timezone.utc))
        )
        return dict(report, status="applied", batch_id=batch_id, change_count=3)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("dry-run", "apply"))
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--expected-plan-sha256", required=True)
    args = parser.parse_args()
    plan, registry = json.loads(args.plan.read_text()), json.loads(args.registry.read_text())
    _fail(canonical_sha256(plan) == args.expected_plan_sha256, "category plan hash differs")
    engine = create_engine(os.environ["KATRAIN_DATABASE_URL"])
    if args.mode == "dry-run":
        with engine.connect() as conn:
            result = inspect_plan(conn, plan, registry)
    else:
        result = apply_plan(engine, plan, registry, args.expected_plan_sha256)
    print(json.dumps(result, ensure_ascii=False))
