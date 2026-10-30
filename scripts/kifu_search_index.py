#!/usr/bin/env python3
"""Bounded, explicit administration of the disposable kifu search index.

Run on the ES host so --disk-path measures the actual storage filesystem. The
operator owns ingest admission/pause and deployment; this tool never changes it.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import resource
import shutil
import sys
from time import monotonic, time

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import create_engine, func, select, text
from sqlalchemy.orm import Session, load_only
from katrain.web.core.config import settings
from katrain.web.core.models_db import KifuAlbum
from katrain.web.kifu.identity import strict_names_enabled
from katrain.web.kifu.search_es import (
    ElasticsearchClient,
    INDEX_MAPPING,
    MAX_RESULT_WINDOW,
    SCHEMA_VERSION,
    STATE_DOCUMENT_ID,
    SearchSettings,
    encode_bulk,
    iter_bulk_batches,
)

GIB = 1024**3
MAX_STORE_BYTES = 2 * GIB
MAX_BUILD_SECONDS = 1800


def emit(value):
    print(json.dumps(value, ensure_ascii=False, sort_keys=True, default=str), flush=True)


def require_bootstrap(deadline, *, minimum_seconds=MAX_BUILD_SECONDS):
    if (
        os.getenv("KIFU_SEARCH_BACKEND", "legacy") != "legacy"
        or os.getenv("KIFU_SEARCH_SYNC_MODE") != "bootstrap"
        or os.getenv("KIFU_SEARCH_BOOTSTRAP_QUIESCENT") != "1"
    ):
        raise ValueError("build requires legacy reads, bootstrap mode and explicit quiescent writers")
    if deadline is None or deadline - time() < minimum_seconds:
        raise ValueError("at least 30 minutes must remain in the existing writer maintenance window")


def candidate_name(alias):
    return alias + "-" + datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S") + "-" + os.urandom(3).hex()


def disk_free(path):
    return shutil.disk_usage(path).free


def index_stats(client, index):
    response = client.request("GET", f"/{index}/_stats/store,translog,docs")
    totals = response.get("_all", {}).get("total", {})
    result = {
        "store_bytes": totals.get("store", {}).get("size_in_bytes"),
        "translog_bytes": totals.get("translog", {}).get("size_in_bytes"),
        "docs": totals.get("docs", {}).get("count"),
    }
    if response.get("_shards", {}).get("failed") != 0 or any(
        type(value) is not int or value < 0 for value in result.values()
    ):
        raise RuntimeError("candidate index stats are incomplete")
    return result


def checkpoint(client, index, started, disk_path):
    stats = index_stats(client, index)
    if monotonic() - started > MAX_BUILD_SECONDS:
        raise RuntimeError("30 minute build limit exceeded")
    if stats["store_bytes"] > MAX_STORE_BYTES:
        raise RuntimeError("2 GiB total index store limit exceeded")
    if disk_free(disk_path) < 15 * GIB:
        raise RuntimeError("host free space crossed 15 GiB stop threshold")
    return stats


@contextmanager
def locked_snapshot(engine, *, deadline=None):
    """Original writer lock plus one read-only repeatable-read PG snapshot."""
    from katrain.web.kifu.name_batch import _locked_write

    with _locked_write(engine, lock_timeout_ms=10000, _search_maintenance=True):
        # The lock holder prevents relevant writers; this separate read-only
        # transaction supplies one snapshot for metadata, classifications, albums.
        with engine.connect().execution_options(isolation_level="REPEATABLE READ") as conn:
            with conn.begin():
                conn.execute(text("SET TRANSACTION READ ONLY"))
                remaining = max(1, int((deadline or (time() + MAX_BUILD_SECONDS)) - time()))
                conn.execute(text("SELECT set_config('statement_timeout', :value, true)"), {"value": f"{remaining}s"})
                with Session(bind=conn, autoflush=False) as db:
                    yield db


def album_records(db, after=0, limit=500):
    columns = [
        getattr(KifuAlbum, column.name) for column in KifuAlbum.__table__.columns if column.name != "sgf_content"
    ]
    return (
        db.query(KifuAlbum)
        .options(load_only(*columns))
        .filter(KifuAlbum.id > after)
        .order_by(KifuAlbum.id)
        .limit(limit)
        .all()
    )


def source_counts(db):
    ids = list(db.scalars(select(KifuAlbum.id).order_by(KifuAlbum.id)))
    visible = db.scalar(
        select(func.count())
        .select_from(KifuAlbum)
        .where(KifuAlbum.duplicate_of_id.is_(None), KifuAlbum.list_hidden_reason.is_(None))
    )
    if len(ids) > MAX_RESULT_WINDOW:
        raise ValueError("source albums exceed the approved 200000 result window")
    return ids, visible


def album_ids(client, index, *, check=None):
    ids, after = set(), None
    while True:
        body = {"size": 1000, "_source": ["id"], "query": {"term": {"doc_kind": "album"}}, "sort": [{"id": "asc"}]}
        if after is not None:
            body["search_after"] = after
        if check:
            check()
        response = client.search(body, index=index)
        hits = response["hits"]["hits"]
        if not hits:
            break
        for hit in hits:
            value = hit["_source"]["id"]
            if type(value) is not int or value in ids:
                raise RuntimeError("invalid or duplicate album ID in candidate")
            ids.add(value)
        after = hits[-1]["sort"]
    return ids


def validate_candidate(client, index, source_ids, visible_count, classifications, samples, *, check=None):
    if album_ids(client, index, check=check) != set(source_ids):
        raise RuntimeError("candidate album ID set differs from the source snapshot")
    visible = client.search(
        {"size": 0, "query": {"bool": {"filter": [{"term": {"doc_kind": "album"}}, {"term": {"list_visible": True}}]}}},
        index=index,
    )
    if visible["hits"]["total"]["value"] != visible_count:
        raise RuntimeError("candidate visible count differs from the source snapshot")
    mapping = client.request("GET", f"/{index}/_mapping")
    if mapping.get(index, {}).get("mappings") != INDEX_MAPPING:
        raise RuntimeError("candidate mapping differs from the approved schema")
    expected = [*classifications, *samples]
    for batch in iter_bulk_batches(expected):
        if check:
            check()
        docs = client.mget([doc["_id"] for doc in batch], index=index)["docs"]
        for want, got in zip(batch, docs):
            if not got.get("found") or got.get("_index") != index or got.get("_source") != want["_source"]:
                raise RuntimeError("candidate classification/sample differs from the source snapshot")
    classified = client.search({"size": 0, "query": {"terms": {"doc_kind": ["term", "public_player"]}}}, index=index)
    if classified["hits"]["total"]["value"] != len(classifications):
        raise RuntimeError("candidate classification count differs from the source snapshot")
    return {
        "album_count": len(source_ids),
        "visible_count": visible_count,
        "classification_count": len(classifications),
        "sample_count": len(samples),
        "schema_version": SCHEMA_VERSION,
    }


def _sample_ids(ids):
    if len(ids) <= 24:
        return set(ids)
    return {ids[round(i * (len(ids) - 1) / 23)] for i in range(24)}


def project_snapshot(db, *, check=None):
    from katrain.web.kifu.search_projection import build_projection_context, project_album_batch

    context = build_projection_context(db, strict_mode=strict_names_enabled(), checkpoint=check)
    return context, project_album_batch


def do_plan(engine, args):
    with Session(engine) as db:
        ids, visible = source_counts(db)
    return {
        "command": "plan",
        "mutating": False,
        "schema_version": SCHEMA_VERSION,
        "source_albums": len(ids),
        "visible_albums": visible,
        "index_alias": os.getenv("KIFU_ES_INDEX_ALIAS", "kifu-search"),
        "backend": os.getenv("KIFU_SEARCH_BACKEND", "legacy"),
        "strict_mode": strict_names_enabled(),
        "expected_album_batches": (len(ids) + 499) // 500,
        "host_free_bytes": disk_free(args.disk_path),
        "required_start_free_bytes": 25 * GIB,
        "stop_free_bytes": 15 * GIB,
        "max_store_bytes": MAX_STORE_BYTES,
        "max_seconds": MAX_BUILD_SECONDS,
        "pause_scope": "operator-controlled ingest admission; original publication/name locks",
    }


def do_build(engine, client, args):
    require_bootstrap(args.lock_deadline_epoch)
    if client.alias_exists():
        raise RuntimeError("initial build requires an absent search alias")
    if engine.dialect.name != "postgresql":
        raise ValueError("initial build requires PostgreSQL read-only snapshot")
    if disk_free(args.disk_path) < 25 * GIB:
        raise RuntimeError("initial build requires 10 GiB additional peak plus 15 GiB reserve")
    index = args.index or candidate_name(client.settings.index_alias)
    if not index.startswith(client.settings.index_alias + "-"):
        raise ValueError("candidate must use the configured alias prefix")
    started, created, refresh_restored, audit = monotonic(), False, False, {"index": index, "status": "building"}
    try:

        def context_check():
            if monotonic() - started > MAX_BUILD_SECONDS or time() >= args.lock_deadline_epoch:
                raise RuntimeError("30 minute build/maintenance limit exceeded")
            if disk_free(args.disk_path) < 15 * GIB:
                raise RuntimeError("host free space crossed 15 GiB stop threshold")

        with locked_snapshot(engine, deadline=min(args.lock_deadline_epoch, time() + MAX_BUILD_SECONDS)) as db:
            ids, visible = source_counts(db)
            context_started = monotonic()
            context, project = project_snapshot(db, check=context_check)
            context_check()
            context_seconds = monotonic() - context_started
            classifications = list(context.classification_documents())
            client.create_index(index)
            created = True
            # Tokenizer/sample acceptance uses this very candidate, before its
            # first 1000 albums. Probe docs are deleted before source import.
            audit["language_probe"] = verify_language_probe(client, index)
            classification_bytes = 0
            for batch in iter_bulk_batches(classifications):
                classification_bytes += len(encode_bulk(batch))
                client.bulk(batch, index=index, retry_transient=True)
                checkpoint(client, index, started, args.disk_path)
            album_bytes, album_count, after, projection_seconds = 0, 0, 0, 0.0
            samples, wanted_samples = [], _sample_ids(ids)
            sample_reported = False
            while True:
                records = album_records(db, after, min(500, max(1, 1000 - album_count)) if album_count < 1000 else 500)
                if not records:
                    break
                batch_started = monotonic()
                documents = list(project(context, records))
                projection_seconds += monotonic() - batch_started
                samples.extend(doc for doc in documents if doc["_source"]["id"] in wanted_samples)
                for batch in iter_bulk_batches(documents):
                    album_bytes += len(encode_bulk(batch))
                    client.bulk(batch, index=index, retry_transient=True)
                album_count += len(records)
                after = records[-1].id
                db.expunge_all()
                stats = checkpoint(client, index, started, args.disk_path)
                if not sample_reported and (album_count >= 1000 or album_count == len(ids)):
                    client.refresh(index=index)
                    stats = checkpoint(client, index, started, args.disk_path)
                    audit["first_sample"] = {
                        "albums": album_count,
                        "album_ndjson_bytes": album_bytes,
                        "classification_documents": len(classifications),
                        "classification_ndjson_bytes": classification_bytes,
                        "context_seconds": context_seconds,
                        "projection_seconds": projection_seconds,
                        "projection_metrics": getattr(context, "stats", {}),
                        "rss_peak_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
                        * (1 if sys.platform == "darwin" else 1024),
                        **stats,
                    }
                    emit({"sample": audit["first_sample"]})
                    sample_reported = True
            client.update_settings({"refresh_interval": "1s"}, index=index)
            refresh_restored = True
            client.refresh(index=index)
            audit["verification"] = validate_candidate(
                client,
                index,
                ids,
                visible,
                classifications,
                samples,
                check=lambda: checkpoint(client, index, started, args.disk_path),
            )
            audit["stats"] = checkpoint(client, index, started, args.disk_path)
            state = {
                "doc_kind": "sync_state",
                "schema_version": SCHEMA_VERSION,
                "strict_mode": strict_names_enabled(),
                "status": "ready",
                "epoch": 0,
                "operation_type": None,
                "operation_ref": None,
                "target_index": index,
                "diagnostics": {"verification": audit["verification"], "language_probe": audit["language_probe"]},
            }
            client.put_document(STATE_DOCUMENT_ID, state, index=index, refresh=True)
            audit.update(
                status="verified_candidate",
                elapsed_seconds=monotonic() - started,
                album_ndjson_bytes=album_bytes,
                classification_ndjson_bytes=classification_bytes,
            )
            return audit
    except BaseException as error:
        audit.update(status="failed", failure_type=type(error).__name__, elapsed_seconds=monotonic() - started)
        if created or getattr(error, "created_index", None) == index:
            try:
                if not refresh_restored:
                    client.update_settings({"refresh_interval": "1s"}, index=index)
                audit["stats"] = index_stats(client, index)
                client.delete_index(index)
                audit["candidate_deleted"] = True
            except Exception as cleanup_error:
                audit["cleanup_required"] = type(cleanup_error).__name__
        emit({"audit": audit})
        raise


def do_check(engine, client, args):
    require_bootstrap(args.lock_deadline_epoch, minimum_seconds=1)
    if not args.index:
        raise ValueError("check requires an explicit concrete --index")
    with locked_snapshot(engine, deadline=args.lock_deadline_epoch) as db:
        ids, visible = source_counts(db)
        context, project = project_snapshot(db)
        classifications = list(context.classification_documents())
        records = db.query(KifuAlbum).filter(KifuAlbum.id.in_(_sample_ids(ids))).all()
        return validate_candidate(client, args.index, ids, visible, classifications, list(project(context, records)))


def do_activate(client, args):
    require_bootstrap(args.lock_deadline_epoch, minimum_seconds=1)
    if not args.index:
        raise ValueError("activate requires explicit concrete --index")
    state = client.get_document(STATE_DOCUMENT_ID, index=args.index).get("_source", {})
    verification = state.get("diagnostics", {}).get("verification", {})
    if (
        state.get("status") != "ready"
        or state.get("schema_version") != SCHEMA_VERSION
        or state.get("strict_mode") is not strict_names_enabled()
        or state.get("target_index") != args.index
        or verification.get("schema_version") != SCHEMA_VERSION
        or not state.get("diagnostics", {}).get("language_probe")
    ):
        raise RuntimeError("candidate lacks complete readiness verification")
    if client.alias_exists() and client.resolve_index() != args.index:
        raise RuntimeError("initial activation cannot replace an active search index")
    client.activate(args.index)
    if client.resolve_index() != args.index:
        raise RuntimeError("alias activation verification failed")
    return {"status": "activated", "index": args.index, "schema_version": SCHEMA_VERSION}


# Real language probe is intentionally small; it is installed below alongside
# language fixtures and is called by build before any business documents.

LANGUAGE_FIXTURES = {
    "cn": ("第12届国手山脉杯世界赛半决赛", "国手 山脉 半决赛", "12", "１２"),
    "tw": ("第6屆嵊州杯中國王中王爭霸賽總決賽", "嵊州 王中王 總決賽", "6", "６"),
    "jp": ("52期日本天元戦挑戦手合5番勝負第2局1-0", "天元戦 挑戦手合", "52", "５２"),
    "ko": ("제12회 국수산맥배 세계전 결승 신진서 VS 리웨이칭", "국수산맥 결승", "12", "１２"),
    "en": (
        "20th Changqi Cup China Professional Go Championship Final Best-of-3 Game 2: 0–1",
        "Changqi Cup Final",
        "2",
        "２",
    ),
}


def verify_language_probe(client, index):
    """Real analyzer + AND/no-hit/order/width checks in the SAME candidate."""
    documents = [
        {
            "_id": "language-probe:" + language,
            "_source": {"doc_kind": "language_probe", "display": {language: {"event": values[0]}}},
        }
        for language, values in LANGUAGE_FIXTURES.items()
    ]
    report = {}
    try:
        client.bulk(documents, index=index)
        client.refresh(index=index)
        for language, (event, query, ascii_number, wide_number) in LANGUAGE_FIXTURES.items():
            field = "display." + language + ".event.words"
            words = INDEX_MAPPING["properties"]["display"]["properties"][language]["properties"]["event"]["fields"][
                "words"
            ]
            tokens = {}
            for kind, analyzer, value in (
                ("index", words["analyzer"], event),
                ("query", words["search_analyzer"], query),
                ("ascii_number", words["search_analyzer"], ascii_number),
                ("wide_number", words["search_analyzer"], wide_number),
            ):
                analyzed = client.request("POST", f"/{index}/_analyze", json={"analyzer": analyzer, "text": value})
                tokens[kind] = [item["token"] for item in analyzed.get("tokens", [])]
                if not tokens[kind]:
                    raise RuntimeError("language analyzer returned no tokens: " + language + ":" + kind)
            if tokens["ascii_number"] != tokens["wide_number"]:
                raise RuntimeError("language full/half width numeric mismatch: " + language)

            def query_ids(value):
                response = client.search(
                    {
                        "size": 10,
                        "query": {
                            "bool": {
                                "filter": [
                                    {"term": {"doc_kind": "language_probe"}},
                                    {"match": {field: {"query": value, "operator": "and"}}},
                                ]
                            }
                        },
                    },
                    index=index,
                )
                return {hit["_id"] for hit in response["hits"]["hits"]}

            want = {"language-probe:" + language}
            if query_ids(query) != want or query_ids(" ".join(reversed(query.split()))) != want:
                raise RuntimeError("language AND/order must-hit failed: " + language)
            if query_ids(query + " qzxunmatched987654321"):
                raise RuntimeError("language AND negative query unexpectedly matched: " + language)
            report[language] = {
                "tokens": tokens,
                "must_hit": True,
                "must_not_hit": True,
                "reordered": True,
                "numeric_width": True,
            }
        return report
    finally:
        client.bulk([{"_op_type": "delete", "_id": doc["_id"]} for doc in documents], index=index)
        client.refresh(index=index)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("plan", "build", "check", "refresh", "sync-ids", "sync-batch", "activate"))
    parser.add_argument("--database-url", default=settings.DATABASE_URL)
    parser.add_argument("--index")
    parser.add_argument("--disk-path", default="/")
    parser.add_argument("--lock-deadline-epoch", type=float)
    parser.add_argument("--ids", type=int, nargs="+")
    parser.add_argument("--batch-id", type=int)
    parser.add_argument("--batch-type", choices=("name", "event"), default="name")
    args = parser.parse_args(argv)
    engine = create_engine(args.database_url, pool_pre_ping=True)
    try:
        if args.command == "plan":
            result = do_plan(engine, args)
        elif args.command in {"sync-ids", "sync-batch"}:
            from katrain.web.kifu.search_sync import sync_batch, sync_ids

            if args.command == "sync-ids":
                if not args.ids:
                    raise ValueError("sync-ids requires finite --ids")
                result = sync_ids(engine, args.ids)
            else:
                if not args.batch_id:
                    raise ValueError("sync-batch requires original --batch-id")
                result = sync_batch(engine, args.batch_id, batch_type=args.batch_type)
        else:
            with ElasticsearchClient(SearchSettings.from_env(role="admin")) as client:
                if args.command == "build":
                    result = do_build(engine, client, args)
                elif args.command == "check":
                    result = do_check(engine, client, args)
                elif args.command == "activate":
                    result = do_activate(client, args)
                else:
                    if not args.index:
                        raise ValueError("refresh requires explicit --index")
                    client.refresh(index=args.index)
                    result = {"status": "refreshed", "index": args.index}
        emit(result)
        return 0
    except (ValueError, RuntimeError) as error:
        emit({"status": "failed", "error_type": type(error).__name__, "message": str(error)})
        return 1
    finally:
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
