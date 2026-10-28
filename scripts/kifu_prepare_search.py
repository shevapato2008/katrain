#!/usr/bin/env python3
"""Explicit prepared-search administration; migrate defaults to dry-run."""

import argparse
from contextlib import contextmanager
import hashlib
import json
import math
import re
import resource
import sys
from pathlib import Path
from time import monotonic
from types import SimpleNamespace

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import create_engine, func, inspect, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from katrain.web.core.config import settings
from katrain.web.core import models_db as business
from katrain.web.kifu import identity, prepared_models as m
from katrain.web.kifu.prepare_search import (
    PrepareBudget,
    PreparationError,
    begin_full_prepare,
    prepare_changed,
    prepare_initial_batch,
)
from katrain.web.kifu.prepared_migration import INPUT_TABLES, apply_migration, migration_plan, verify_schema
from katrain.web.kifu.prepared_read import current_policy_signature, read_state


MIB = 1024 * 1024
MAX_RELATION_BYTES = 2 * 1024 * MIB
SPECS = {
    "player": (business.KifuPlayer, business.KifuPlayerName, "player_id", business.KifuPlayerAlias),
    "event": (business.KifuEvent, business.KifuEventName, "event_id", business.KifuEventAlias),
    "raw_player": (business.KifuRawPlayerValue, business.KifuRawPlayerName, "raw_player_id", None),
    "raw_event": (business.KifuRawEventValue, business.KifuRawEventName, "raw_event_id", None),
}


def _bounded_number(maximum, *, integer=False):
    def parse(value):
        try:
            number = int(value) if integer else float(value)
        except ValueError as exc:
            raise argparse.ArgumentTypeError("a positive number is required") from exc
        if not math.isfinite(number) or number <= 0 or number > maximum:
            raise argparse.ArgumentTypeError(f"must be greater than 0 and at most {maximum}")
        return number

    return parse


def _rss_bytes():
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return int(peak if sys.platform == "darwin" else peak * 1024)


def _remaining(started, maximum):
    remaining = maximum - (monotonic() - started)
    if remaining <= 0:
        raise PreparationError("preparation time budget exceeded; resume the last committed checkpoint")
    return remaining


def _timeout(conn, seconds):
    if conn.dialect.name == "postgresql":
        conn.execute(
            text("SELECT set_config('statement_timeout', :timeout, true)"),
            {"timeout": f"{max(1, int(seconds * 1000))}ms"},
        )


@contextmanager
def _writer_transaction(engine, *, seconds=30):
    """Use the business writers' order, yielding promptly to an active writer."""
    from katrain.web.kifu.name_batch import _ADVISORY_LOCK_KEY

    started = monotonic()
    with engine.connect() as conn:
        try:
            if conn.dialect.name == "postgresql":
                conn.begin()
                _timeout(conn, seconds)
                conn.execute(text("SELECT set_config('lock_timeout', '1000ms', true)"))
                for key in (_ADVISORY_LOCK_KEY, 720220261003):
                    if not conn.scalar(text("SELECT pg_try_advisory_xact_lock(:key)"), {"key": key}):
                        raise PreparationError("writer busy; retry later with --resume")
                conn.exec_driver_sql("LOCK TABLE " + ", ".join(INPUT_TABLES) + " IN SHARE ROW EXCLUSIVE MODE")
            elif conn.dialect.name == "sqlite":
                conn.exec_driver_sql("PRAGMA foreign_keys=ON")
                conn.exec_driver_sql("PRAGMA busy_timeout=1000")
                conn.exec_driver_sql("BEGIN IMMEDIATE")
            else:
                raise PreparationError("unsupported preparation database")
            yield conn
            _remaining(started, seconds)
            conn.commit()
        except BaseException:
            conn.rollback()
            raise


def _schema_required(engine):
    result = verify_schema(engine)
    if not result["ok"]:
        raise PreparationError("explicit migration/valid prepared schema required: " + "; ".join(result["errors"]))


def _state_required(conn):
    value = read_state(conn)
    if value is None:
        raise PreparationError("explicit prepared-search migration is required")
    return value


def _coverage(conn):
    from katrain.web.kifu.prepare_search import verify_coverage

    result = verify_coverage(conn)
    return {"ok": True, **(result or {})}


def _sample_proof(conn, albums, checkpoint):
    """Exercise only source owners/raw values in the small-field album sample."""
    players = {value for album in albums for value in (album.black_player_id, album.white_player_id) if value}
    events = {album.event_id for album in albums if album.event_id}
    raws = {
        "raw_player": {value for album in albums for value in (album.player_black, album.player_white)},
        "raw_event": {album.event or "" for album in albums},
    }
    selection = business.KifuAlbumEventSelection
    for raw, event_id in conn.execute(
        select(selection.selected_raw, selection.event_id).where(selection.album_id.in_([album.id for album in albums]))
    ):
        raws["raw_event"].add(raw)
        if event_id is not None:
            events.add(event_id)
    physical, qualified, finite_members, owners = 0, 0, 0, 0
    physical_by_kind, name_widths = {}, []
    proof_started = monotonic()
    with Session(bind=conn) as db:
        for kind, (owner_model, model, owner_column, _alias) in SPECS.items():
            checkpoint()
            if kind.startswith("raw_"):
                values = raws[kind]
                ids = {row_id for row_id, in db.query(owner_model.id).filter(owner_model.raw_value.in_(values))}
            else:
                ids = players if kind == "player" else events
            owners += len(ids)
            names = (
                db.query(model.display_name, model.lang, model.decision_kind, model.generation_rule_version)
                .filter(getattr(model, owner_column).in_(ids))
                .all()
            )
            physical_by_kind[kind] = len(names)
            physical += len(names)
            name_widths.extend(len(json.dumps(list(row), ensure_ascii=False).encode()) for row in names)
            if kind == "raw_player":
                rows = identity._approved_raw_player_names(db, values=raws[kind])
            elif kind == "raw_event":
                rows = identity._approved_raw_event_names(db, values=raws[kind])
            else:
                rows = identity._qualified_name_rows(
                    db, identity._approved_names(db, model, owner_column, ids), model, owner_column
                )
            qualified += len(rows)
            if kind.startswith("raw_"):
                from katrain.web.kifu.prepare_search import _finite_album_ids

                # Signed finite scopes may include members outside the sampled
                # albums. Count their complete proof closure, never truncate it.
                finite_members += sum(len(_finite_album_ids(row[2])) * 2 for row in rows if row[2] is not None)
            checkpoint()
    return {
        "albums": len(albums),
        "owners": owners,
        "physical_names": physical,
        "physical_names_by_kind": physical_by_kind,
        "mean_name_payload_bytes": sum(name_widths) / max(1, len(name_widths)),
        "mean_album_value_bytes": sum(
            len(json.dumps([album.player_black, album.player_white, album.event], ensure_ascii=False).encode())
            for album in albums
        )
        / max(1, len(albums)),
        "qualified_names": qualified,
        "finite_member_upper_bound": finite_members,
        "proof_seconds": monotonic() - proof_started,
        "proof_observed": True,
        "scope": "sample owners/raw values; complete relevant finite proofs; unsampled closures are estimates",
    }


def plan(engine, args):
    started, rss_before = monotonic(), _rss_bytes()
    with engine.connect() as conn:
        transaction = conn.begin()
        if conn.dialect.name == "postgresql":
            conn.exec_driver_sql("SET TRANSACTION READ ONLY")

        def checkpoint():
            _timeout(conn, _remaining(started, args.max_seconds))
            if _rss_bytes() > 512 * MIB:
                raise PreparationError("plan memory budget exceeded")

        try:
            checkpoint()
            existing = set(inspect(conn).get_table_names())
            missing = set(INPUT_TABLES) - existing
            if missing:
                raise PreparationError("missing business inputs: " + ", ".join(sorted(missing)))
            album = business.KifuAlbum.__table__
            counts = {
                "detail_albums": conn.scalar(select(func.count()).select_from(album)),
                "visible_albums": conn.scalar(
                    select(func.count())
                    .select_from(album)
                    .where(album.c.duplicate_of_id.is_(None), album.c.list_hidden_reason.is_(None))
                ),
            }
            owner_counts, name_counts, alias_counts, languages = {}, {}, {}, {}
            for kind, (owner, model, _column, alias) in SPECS.items():
                checkpoint()
                owner_counts[kind] = conn.scalar(select(func.count()).select_from(owner))
                grouped = conn.execute(select(model.lang, func.count()).group_by(model.lang)).all()
                languages[kind] = {lang: count for lang, count in grouped}
                name_counts[kind] = sum(count for _lang, count in grouped)
                alias_counts[kind] = conn.scalar(select(func.count()).select_from(alias)) if alias else 0
            counts.update(owners=owner_counts, names=name_counts, aliases=alias_counts, languages=languages)
            checkpoint()
            columns = ("id", "black_player_id", "white_player_id", "event_id", "player_black", "player_white", "event")
            size = min(args.sample_albums, counts["detail_albums"])
            if size == counts["detail_albums"]:
                bands = [(0, size)]
            else:
                head, middle = (size + 2) // 3, (size + 1) // 3
                tail = size - head - middle
                bands = [
                    (0, head),
                    ((counts["detail_albums"] - middle) // 2, middle),
                    (counts["detail_albums"] - tail, tail),
                ]
            albums, ranges = [], []
            for offset, length in bands:
                if not length:
                    continue
                checkpoint()
                rows = (
                    conn.execute(
                        select(*(album.c[column] for column in columns))
                        .order_by(album.c.id)
                        .offset(offset)
                        .limit(length)
                    )
                    .mappings()
                    .all()
                )
                albums.extend(SimpleNamespace(**row) for row in rows)
                if rows:
                    ranges.append([rows[0]["id"], rows[-1]["id"]])
            sample = _sample_proof(conn, albums, checkpoint)
            sample.update(strategy="head/middle/tail by ordered album id", id_ranges=ranges)
            unobserved = [kind for kind in SPECS if name_counts[kind] and not sample["physical_names_by_kind"][kind]]
            sample["unobserved_name_families"] = unobserved
            checkpoint()
            name_total = sum(name_counts.values()) + sum(alias_counts.values())
            from katrain.web.kifu.first_pass_cn import _hints
            from katrain.web.kifu.library_search import HISTORICAL_PLAYER_ALIASES

            hint_players, hint_events, hint_overrides = _hints()
            generic_upper_bound = (
                len(HISTORICAL_PLAYER_ALIASES) + len(hint_players) + len(hint_events) + len(hint_overrides)
            )
            counts["generic_name_upper_bound"] = generic_upper_bound
            rows = {
                "names": name_total + generic_upper_bound,
                "displays": counts["detail_albums"] * len(m.NAME_LANGUAGES),
            }
            sample_scale = counts["detail_albums"] / max(1, sample["albums"])
            rows["members"] = math.ceil(sample["finite_member_upper_bound"] * sample_scale * 2)
            rows["dependencies"] = name_total * 24 + math.ceil(counts["detail_albums"] * 9.03 * 2)
            rows.update(state=1, dirty=0)
            # PostgreSQL 15.15 measured 1,000-album fixture: 5,000 displays=925,696B,
            # 9,030 shared album dependencies=2,236,416B, 2,942 names=1,908,736B.
            # These already include relation/index overhead. Adjust for sampled
            # UTF-8 values, reserve metadata room, and double dependency density;
            # do not multiply each album's shared dependencies by five languages.
            relation_model = {
                "basis": "PostgreSQL 15.15 isolated 1000-album mechanical canonical fixture; sampled UTF-8 widths; raw density uncalibrated",
                "names_bytes_per_row": math.ceil(1908736 / 2942 + sample["mean_name_payload_bytes"] * 2),
                "displays_bytes_per_row": math.ceil(
                    925696 / 5000 + max(0, sample["mean_album_value_bytes"] - 64) + 192
                ),
                "dependencies_bytes_per_row": math.ceil(2236416 / 9030),
                "members_bytes_per_row": 1024,
                "dependency_density_reserve": 2,
                "member_density_reserve": 2,
            }
            estimated_bytes = (
                32768
                + 24576
                + 16384
                + sum(
                    rows[kind] * relation_model[kind + "_bytes_per_row"]
                    for kind in ("names", "displays", "members", "dependencies")
                )
            )
            estimated_seconds = max(
                (monotonic() - started) * sample_scale * 2,
                sample["proof_seconds"] * sum(owner_counts.values()) / max(1, sample["owners"]) * 2,
            )
            estimated_rss = _rss_bytes() + max(
                8 * MIB, (_rss_bytes() - rss_before) * min(500, counts["detail_albums"]) // max(1, sample["albums"])
            )
            limits = {"seconds": 1800, "relation_bytes": MAX_RELATION_BYTES, "rss_bytes": 512 * MIB}
            estimate = {"seconds": estimated_seconds, "relation_bytes": estimated_bytes, "rss_bytes": estimated_rss}
            exceeded = [key for key, value in estimate.items() if value > limits[key]]
            return {
                "ok": not exceeded and not unobserved,
                "ready": False,
                "read_only": True,
                "counts": counts,
                "sample": sample,
                "estimated_rows": rows,
                "estimate": estimate,
                "relation_model": relation_model,
                "limits": limits,
                "member_universal_upper_bound": 2 * counts["detail_albums"] * sum(name_counts.values()),
                "exceeded": exceeded,
                "elapsed_seconds": monotonic() - started,
                "policy_signature": current_policy_signature(),
                "estimate_basis": "bounded proof/UTF-8 sample with measured PG row/index overhead; unsampled finite closures remain estimates",
            }
        finally:
            transaction.rollback()


def prepare(engine, args):
    started, committed = monotonic(), 0
    _schema_required(engine)
    result = {"ready": False}
    try:
        with engine.connect() as conn:
            value = _state_required(conn)
            if args.full and value["enabled"]:
                raise PreparationError("disable prepared search explicitly before prepare --full")
            if (
                value["phase"] != "unprepared"
                and not value["initial_coverage_complete"]
                and not (args.resume or args.full)
            ):
                raise PreparationError("checkpoint exists; pass --resume to continue")
            if value["enabled"] and (
                not value["initial_coverage_complete"] or value["policy_signature"] != current_policy_signature()
            ):
                raise PreparationError("disable prepared search before rebuilding its coverage/policy")
        while True:
            remaining = _remaining(started, args.max_seconds)
            with _writer_transaction(engine, seconds=min(30, remaining)) as conn:
                if args.full and committed == 0:
                    begin_full_prepare(conn)
                pending = prepare_initial_batch(
                    conn,
                    batch_size=args.batch_size,
                    budget=PrepareBudget(
                        max_albums=args.batch_size, max_seconds=min(30, remaining), max_bytes=args.max_memory_mib * MIB
                    ),
                )
                _remaining(started, args.max_seconds)
            committed += 1
            result = pending
            if result["ready"]:
                break
        return {
            "ok": True,
            **result,
            "committed_batches": committed,
            "elapsed_seconds": monotonic() - started,
            "policy_signature": current_policy_signature(),
        }
    except (PreparationError, SQLAlchemyError) as exc:
        return {
            "ok": False,
            "ready": False,
            "reason": _error_reason(exc),
            "committed_batches": committed,
            "last_committed_batch": result,
            "elapsed_seconds": monotonic() - started,
        }


def _comparison_cases(path, count):
    if not path:
        raise ValueError("comparison not yet observed; --compare-queries must name the frozen actual casefile")
    try:
        data = Path(path).read_bytes()
        document = json.loads(data)
    except (OSError, ValueError) as exc:
        raise ValueError("comparison not observed; cannot read the JSON casefile") from exc
    if not isinstance(document, dict) or document.get("version") != 1 or not isinstance(document.get("cases"), list):
        raise ValueError("comparison requires a version=1 casefile with cases")
    if len(document["cases"]) < count:
        raise ValueError(f"comparison requires at least {count} frozen cases")
    cases, seen = document["cases"][:count], set()
    for case in cases:
        if not isinstance(case, dict) or any(
            not isinstance(case.get(key), str) or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,80}", case[key])
            for key in ("id", "category")
        ):
            raise ValueError("comparison case id/category must be opaque ASCII identifiers")
        if case["id"] in seen:
            raise ValueError("comparison case ids must be unique")
        seen.add(case["id"])
        params = case.get("params")
        if not isinstance(params, dict) or set(params) - {"q", "player_id", "lang", "page", "page_size"}:
            raise ValueError("comparison case params contain unsupported keys")
        if (
            ("q" in params and not isinstance(params["q"], str))
            or ("player_id" in params and (type(params["player_id"]) is not int or params["player_id"] < 1))
            or ("q" in params and "player_id" in params)
        ):
            raise ValueError("comparison requires q or a positive player_id, not both")
        if (
            params.get("lang", "cn") not in m.NAME_LANGUAGES
            or any(
                type(params.get(key, default)) is not int or params.get(key, default) < 1
                for key, default in (("page", 1), ("page_size", 20))
            )
            or params.get("page_size", 20) > 100
        ):
            raise ValueError("comparison case language/page/page_size is invalid")
    return cases, hashlib.sha256(data).hexdigest()


def _compare(conn, cases, manifest_sha256):
    from katrain.web.api.v1.endpoints.kifu import _read_prepared_album_page, read_album_page_legacy

    observed = []
    with Session(bind=conn) as db:
        for case in cases:
            # The caller has verified coverage, policy, and dirty in this same
            # snapshot. Bypass only enabled: the ordinary public helper would
            # otherwise compare legacy with itself before cutover.
            prepared = _read_prepared_album_page(db, **case["params"]).model_dump(mode="json")
            legacy = read_album_page_legacy(db, **case["params"]).model_dump(mode="json")
            digest = lambda value: hashlib.sha256(
                json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()
            observed.append(
                {
                    "id": case["id"],
                    "category": case["category"],
                    "equivalent": prepared == legacy,
                    "prepared_sha256": digest(prepared),
                    "legacy_sha256": digest(legacy),
                }
            )
    return {
        "observed": True,
        "ok": all(case["equivalent"] for case in observed),
        "manifest_sha256": manifest_sha256,
        "cases": observed,
    }


def verify(engine, args):
    _schema_required(engine)
    comparison = {"observed": False, "requested": args.compare_sample, "reason": "comparison not requested"}
    cases, manifest_sha256 = None, None
    if args.compare_sample:
        try:
            cases, manifest_sha256 = _comparison_cases(args.compare_queries, args.compare_sample)
        except ValueError as exc:
            comparison["reason"] = str(exc)
    with engine.connect() as conn:
        if conn.dialect.name == "postgresql":
            conn = conn.execution_options(isolation_level="REPEATABLE READ")
        with conn.begin():
            if conn.dialect.name == "postgresql":
                conn.exec_driver_sql("SET TRANSACTION READ ONLY")
            _timeout(conn, 30)
            state = dict(_state_required(conn))
            if not state["initial_coverage_complete"] or not state["ready"]:
                raise PreparationError("incomplete prepared coverage")
            if state["policy_version"] != m.POLICY_VERSION or state["policy_signature"] != current_policy_signature():
                raise PreparationError("policy mismatch")
            if conn.execute(select(m.dirty).limit(1)).first():
                raise PreparationError("unresolved dirty inputs")
            coverage = _coverage(conn) if args.all_coverage or cases else {"ok": True, "all_coverage_observed": False}
            if cases:
                comparison = {"requested": args.compare_sample, **_compare(conn, cases, manifest_sha256)}
            return {
                "ok": not args.compare_sample or comparison.get("ok", False),
                "state": state,
                "coverage": coverage,
                "comparison": comparison,
                "policy_signature": current_policy_signature(),
            }


def switch(engine, *, enabled, expected_policy_version=None):
    if not enabled:
        # Rollback must remain available if a guard or derived index is broken.
        # Only the existing singleton is needed; this never repairs/drops data.
        with engine.begin() as conn:
            _timeout(conn, 30)
            if conn.dialect.name == "postgresql":
                conn.execute(text("SELECT set_config('lock_timeout', '1000ms', true)"))
            _state_required(conn)
            conn.execute(m.state.update().where(m.state.c.id == 1).values(enabled=False))
        return {"ok": True, "enabled": False, "policy_signature": current_policy_signature()}
    _schema_required(engine)
    with _writer_transaction(engine) as conn:
        _schema_required(conn)
        value = _state_required(conn)
        if enabled:
            if expected_policy_version != m.POLICY_VERSION or value["policy_version"] != expected_policy_version:
                raise PreparationError("policy version mismatch")
            if not value["initial_coverage_complete"]:
                raise PreparationError("incomplete initial coverage")
            if value["policy_signature"] != current_policy_signature():
                raise PreparationError("policy signature mismatch")
            prepare_changed(conn, budget=PrepareBudget(max_seconds=30))
            _coverage(conn)
            value = _state_required(conn)
            if not value["ready"] or conn.execute(select(m.dirty).limit(1)).first():
                raise PreparationError("coverage/dirty closure is not ready")
        conn.execute(m.state.update().where(m.state.c.id == 1).values(enabled=enabled))
    return {"ok": True, "enabled": enabled, "policy_signature": current_policy_signature()}


def _error_reason(exc):
    if isinstance(exc, SQLAlchemyError):
        # Driver errors can echo a database URL or business bind values. Retain a
        # useful operator category without printing credentials or proof data.
        return f"database operation refused ({type(exc).__name__}); inspect local database logs; no uncommitted batch retained"
    return str(exc)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", default=settings.DATABASE_URL)
    sub = parser.add_subparsers(dest="command", required=True)
    migrate = sub.add_parser("migrate")
    mode = migrate.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    sub.add_parser("verify-schema")
    planning = sub.add_parser("plan")
    planning.add_argument("--max-seconds", type=_bounded_number(30), default=30)
    planning.add_argument("--sample-albums", type=_bounded_number(1000, integer=True), default=1000)
    preparation = sub.add_parser("prepare")
    preparation.add_argument("--batch-size", type=_bounded_number(500, integer=True), default=500)
    preparation.add_argument("--max-seconds", type=_bounded_number(1800), default=1800)
    preparation.add_argument("--max-memory-mib", type=_bounded_number(512, integer=True), default=512)
    preparation_mode = preparation.add_mutually_exclusive_group()
    preparation_mode.add_argument("--resume", action="store_true")
    preparation_mode.add_argument("--full", action="store_true", help="start an explicit disabled full rebuild")
    verification = sub.add_parser("verify")
    verification.add_argument("--all-coverage", action="store_true")
    verification.add_argument("--compare-sample", type=_bounded_number(24, integer=True), default=0)
    verification.add_argument(
        "--compare-queries", type=Path, help="frozen version=1 load casefile; compare its first N cases"
    )
    enable = sub.add_parser("enable")
    enable.add_argument("--expected-policy-version", type=int, required=True)
    sub.add_parser("disable")
    args = parser.parse_args(argv)
    engine = create_engine(args.database_url, pool_pre_ping=True)
    try:
        if args.command == "migrate":
            result = apply_migration(engine) if args.apply else migration_plan(engine)
        elif args.command == "verify-schema":
            result = verify_schema(engine)
        elif args.command == "plan":
            result = plan(engine, args)
        elif args.command == "prepare":
            result = prepare(engine, args)
        elif args.command == "verify":
            result = verify(engine, args)
        else:
            result = switch(
                engine,
                enabled=args.command == "enable",
                expected_policy_version=getattr(args, "expected_policy_version", None),
            )
        print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
        return 0 if result.get("ok", not result.get("missing_inputs")) else 1
    except (PreparationError, SQLAlchemyError, ValueError) as exc:
        print(json.dumps({"ok": False, "ready": False, "reason": _error_reason(exc)}, ensure_ascii=False))
        return 1
    finally:
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
