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

from sqlalchemy import and_, create_engine, func, inspect, or_, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, load_only

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

# Actual isolated PostgreSQL relation + index measurements, never business density.
# Write timing is PG EXPLAIN execution/planning plus a Mac client process-CPU proxy;
# it excludes SSH wall time and is not a runtime performance promise.
PG_CALIBRATION = {
    "names": {
        "bytes_per_row": 1908736 / 2942,
        "body_bytes": 96.602,
        "write_seconds_per_row": (0.076681 + 0.096801) / 1000,
    },
    "displays": {"bytes_per_row": 212.992, "body_bytes": 75.537, "write_seconds_per_row": (0.052127 + 0.087397) / 1000},
    "dependencies": {
        "bytes_per_row": 294.912,
        "body_bytes": 35.345,
        "write_seconds_per_row": (0.060038 + 0.027545) / 1000,
    },
    "members:black": {
        "bytes_per_row": 557.056,
        "body_bytes": 363,
        "write_seconds_per_row": (0.096182 + 0.055897) / 1000,
    },
    "members:white": {
        "bytes_per_row": 557.056,
        "body_bytes": 363,
        "write_seconds_per_row": (0.095011 + 0.052895) / 1000,
    },
    "members:event": {
        "bytes_per_row": 245.760,
        "body_bytes": 80,
        "write_seconds_per_row": (0.082293 + 0.045093) / 1000,
    },
    "members:selected_event": {
        "bytes_per_row": 262.144,
        "body_bytes": 79,
        "write_seconds_per_row": (0.081554 + 0.048633) / 1000,
    },
}


def _json_bytes(conn, value):
    encoded = (conn.dialect._json_serializer or json.dumps)(value)
    return len(encoded if isinstance(encoded, bytes) else encoded.encode("utf-8"))


def _body_bytes(conn, table, row):
    from sqlalchemy import JSON

    size = 0
    for key, value in row.items():
        if key not in table.c:
            continue
        kind = table.c[key].type
        if isinstance(kind, JSON):
            if value is not None or not kind.none_as_null:
                size += _json_bytes(conn, value)
        elif isinstance(value, str):
            size += len(value.encode("utf-8"))
    return size


def _dependency_bytes(conn, row):
    """Retain the six-digit target-key width used by the PG calibration."""
    return _body_bytes(conn, m.dependencies, row) + max(0, 6 - len(row["target_key"].encode("utf-8")))


def _scope_dependency_inputs(inputs, scope_ids, payload):
    """Split accepted finite scopes only; independent source anchors stay fixed."""
    anchors = set()

    def visit(value, in_scope=False):
        if isinstance(value, list):
            for item in value:
                visit(item, in_scope)
        elif isinstance(value, dict):
            if not in_scope:
                if type(value.get("album_id")) is int:
                    anchors.add(value["album_id"])
                if isinstance(value.get("occurrence_album_ids"), list):
                    anchors.update(item for item in value["occurrence_album_ids"] if type(item) is int)
            for key, item in value.items():
                visit(item, in_scope or key in {"raw_scope", "raw_display_scope", "scope", "declaration"})

    visit(payload)
    scope = {
        (kind, str(key))
        for kind, key in inputs
        if kind in {business.KifuAlbum.__tablename__, "album_sources", business.KifuAlbumEventSelection.__tablename__}
        and str(key).isdigit()
        and int(key) in scope_ids
        and int(key) not in anchors
    }
    return inputs - scope, scope


def _width_add(widths, key, size):
    value = widths.setdefault(key, {"rows": 0, "bytes": 0, "max": 0})
    value["rows"] += 1
    value["bytes"] += size
    value["max"] = max(value["max"], size)


def _global_proof_metadata(conn, checkpoint):
    """Count scalar proof references once, without fetching whole JSON payloads."""
    result = {}
    with Session(bind=conn) as db:
        for kind, (owner, model, owner_column, alias) in SPECS.items():
            checkpoint("metadata:" + kind)
            name_owners = dict(db.query(model.id, getattr(model, owner_column)))
            dependency_owners = set(name_owners.values())
            owner_ids = {row_id for row_id, in db.query(owner.id)} | dependency_owners
            if alias is not None:
                alias_owners = {row_id for row_id, in db.query(getattr(alias, owner_column))}
                dependency_owners.update(alias_owners)
                owner_ids.update(alias_owners)
            owner_pages = {owner_id: offset // 500 for offset, owner_id in enumerate(sorted(owner_ids))}
            value = {
                "groups": 0,
                "group_page_calls": 0,
                "owner_pages": math.ceil(len(owner_ids) / 500),
                "names": len(name_owners),
                "largest_group": 0,
                "named_owners": len(set(name_owners.values())),
                "dependency_owners": len(dependency_owners),
            }
            checkpoint(
                completed={
                    "metadata:" + kind + ":names": value["names"],
                    "metadata:" + kind + ":owner_pages": value["owner_pages"],
                }
            )
            for group in identity.iter_name_proof_groups(db, model, name_owners):
                value["groups"] += 1
                value["group_page_calls"] += len({owner_pages[name_owners[row_id]] for row_id in group})
                value["largest_group"] = max(value["largest_group"], len(group))
                checkpoint(
                    completed={
                        "metadata:" + kind + ":groups": value["groups"],
                        "metadata:" + kind + ":group_page_calls": value["group_page_calls"],
                    }
                )
            result[kind] = value
            del name_owners, owner_ids, owner_pages, dependency_owners
            db.expunge_all()
    return result


def _estimate_plan(counts, sample, peak_bytes):
    """Keep source-name, complete-proof-group and album dimensions separate."""
    scale = counts["detail_albums"] / max(1, sample["albums"])
    names = sum(counts["names"].values()) + sum(counts["aliases"].values())
    full_slots = sample.get("member_slots_full_scope", {})
    slots = {
        slot: 2 * max(full_slots.get(slot, 0), math.ceil(sample["member_slots"].get(slot, {}).get("rows", 0) * scale))
        for slot in set(full_slots) | set(sample["member_slots"])
    }
    owner_counts = sample.get("dependency_owners_by_kind", {})
    fixed_samples = sample.get("name_dependency_fixed_rows_by_kind", sample["name_dependency_rows_by_kind"])
    for kind, number in fixed_samples.items():
        if number and (
            not owner_counts.get(kind) or "dependency_owners" not in counts.get("proof_groups", {}).get(kind, {})
        ):
            raise PreparationError("owner dependency measurement unavailable")
    name_deps = sum(
        math.ceil(
            fixed_samples.get(kind, 0)
            * counts.get("proof_groups", {}).get(kind, {}).get("dependency_owners", 0)
            / max(1, owner_counts.get(kind, 0))
            * 2
        )
        for kind in SPECS
    )
    scope_deps = 2 * max(
        sample.get("name_dependency_scope_rows_full", 0),
        math.ceil(sample.get("name_dependency_scope_rows_sample", 0) * scale),
    )
    rows = {
        "names": names + counts["generic_name_upper_bound"],
        "displays": counts["detail_albums"] * len(m.NAME_LANGUAGES),
        "members": sum(slots.values()),
        "dependencies": name_deps
        + scope_deps
        + 3 * sum(counts["aliases"].values())
        + math.ceil(sample["display_dependency_rows_sample"] * scale * 2),
        "state": 1,
        "dirty": 0,
    }
    unknown, model = [], {
        "basis": "PostgreSQL 15.15 isolated heap + all indexes; observed source widths; 2x density reserve",
        "dependency_density_reserve": 2,
        "member_density_reserve": 2,
        "member_slots": slots,
        "name_dependency_fixed_rows": name_deps,
        "name_dependency_scope_rows": scope_deps,
        "name_dependency_scope_basis": "Accepted finite scope album edges only; independent source anchors and unverified scopes remain fixed",
        "fixed_dependency_projection_unit": "Owner UNION, not source-name rows",
        "alias_dependency_reserve_rows": 3 * sum(counts["aliases"].values()),
        "alias_dependency_reserve_basis": "Conservative extra reserve on top of the measured owner UNION; not actual per-name stored edges",
        "rss_basis": "Observed full-process peak plus retained 8MiB buffer; no rescaling of an already observed peak",
    }
    model["write_time_basis"] = (
        "PG EXPLAIN execution + planning plus Mac client process CPU proxy; excludes SSH wall; 2x time reserve"
    )
    model["proof_time_basis"] = (
        "max(complete-group calls across 500-owner pages, physical-name growth); 2x time reserve"
    )
    storage, writes = 32768 + 24576 + 16384, 0
    relation_bytes = {}
    storage_known, writes_known = True, True
    workloads = [
        (key, rows[key], sample.get("row_widths", {}).get(key, {})) for key in ("names", "displays", "dependencies")
    ]
    workloads.extend(
        (
            "members:" + slot,
            number,
            sample["member_slots"].get(slot, sample.get("member_widths_full_scope", {}).get(slot, {})),
        )
        for slot, number in slots.items()
    )
    for key, number, width in workloads:
        if not number:
            continue
        calibration = PG_CALIBRATION.get(key, {})
        mean_width = width.get("bytes", 0) / max(1, width.get("rows", 0))
        base = calibration.get("bytes_per_row")
        if base is None:
            storage_known = False
            unknown.append(key + ":storage")
        else:
            coefficient = base + max(0, mean_width - calibration.get("body_bytes", 0))
            if key == "displays":
                coefficient += 192  # Retain the original metadata reserve.
            model[key + "_bytes_per_row"] = coefficient
            relation_bytes[key] = math.ceil(number * coefficient)
            storage += relation_bytes[key]
        seconds = calibration.get("write_seconds_per_row")
        if seconds is None:
            writes_known = False
            unknown.append(key + ":write_time")
        else:
            writes += number * seconds * max(1, mean_width / max(1, calibration.get("body_bytes", 1)))
    proof, construction = 0, 0
    for kind in SPECS:
        timing = sample.get("timings_by_kind", {}).get(kind, {})
        metadata = counts.get("proof_groups", {}).get(kind, {})
        full_groups = metadata.get("group_page_calls", metadata.get("groups", 0))
        groups = timing.get("groups", 0)
        if full_groups and not groups:
            unknown.append(kind + ":proof_time")
        name_scale = counts["names"][kind] / max(1, sample["physical_names_by_kind"].get(kind, 0))
        proof += timing.get("proof_seconds", 0) * max(full_groups / max(1, groups), name_scale)
        construction += (
            timing.get("member_seconds", 0) + timing.get("dependency_seconds", 0) + timing.get("metadata_seconds", 0)
        ) * name_scale
    display = sample.get("display_seconds")
    if display is None:
        unknown.append("displays:construction_time")
    known_time = writes_known and display is not None and not any(value.endswith(":proof_time") for value in unknown)
    estimate = {
        "seconds": (
            2 * (proof + construction + (display or 0) * scale + writes + sample.get("global_metadata_seconds", 0))
            if known_time
            else None
        ),
        "relation_bytes": storage if storage_known else None,
        "rss_bytes": peak_bytes + 8 * MIB,
        "proof_seconds": proof,
        "source_construction_seconds": construction,
        "display_construction_seconds": display * scale if display is not None else None,
        "write_seconds": writes if writes_known else None,
    }
    model["estimated_bytes_by_relation_or_slot"] = relation_bytes
    return rows, estimate, model, unknown


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
    from katrain.web.kifu import prepare_search as core

    sample_ids = {album.id for album in albums}
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
    physical, qualified, owners = 0, 0, 0
    physical_by_kind, name_widths, widths, timings, dependency_counts, fixed_counts = {}, [], {}, {}, {}, {}
    dependency_owners_by_kind = {}
    full_slot_widths = {}
    full_scope_inputs, sampled_scope_inputs = set(), set()
    derived_names, sample_members, full_member_keys, calibration_members = [], {}, set(), {}
    proxy_ids = {}
    proof_started = monotonic()
    with Session(bind=conn) as db:
        for kind, (owner_model, model, owner_column, alias_model) in SPECS.items():
            checkpoint("proof:" + kind)
            kind_started = monotonic()
            timing = {"groups": 0, "proof_seconds": 0, "member_seconds": 0, "dependency_seconds": 0}
            dependency_counts[kind] = 0
            fixed_counts[kind] = 0
            source_inputs, fixed_source_inputs, kind_refs = {}, {}, []
            owner_inputs, owner_fixed, representatives = {}, {}, {}
            inputs_checked = 0
            if kind.startswith("raw_"):
                values = raws[kind]
                raw_owners = dict(
                    db.query(owner_model.id, owner_model.raw_value).filter(owner_model.raw_value.in_(values))
                )
                ids = set(raw_owners)
            else:
                ids = players if kind == "player" else events
            existing_owners = {row_id for row_id, in db.query(owner_model.id).filter(owner_model.id.in_(ids))}
            owners += len(ids)
            names = (
                db.query(model.id, model.display_name, model.lang, model.decision_kind, model.generation_rule_version)
                .filter(getattr(model, owner_column).in_(ids))
                .all()
            )
            physical_by_kind[kind] = len(names)
            physical += len(names)
            checkpoint(completed={"physical_names:" + kind: len(names)}, check=False)
            name_widths.extend(_json_bytes(conn, list(row[1:])) for row in names)
            # Group complete proof batches using scalar IDs before loading payloads.
            # Count each original full proof, then release it before the next group.
            for group in identity.iter_name_proof_groups(db, model, {row.id for row in names}):
                checkpoint("proof:" + kind)
                timing["groups"] += 1
                started = monotonic()
                if kind == "raw_player":
                    rows = identity._approved_raw_player_names(db, values=raws[kind], name_ids=group)
                elif kind == "raw_event":
                    rows = identity._approved_raw_event_names(db, values=raws[kind], name_ids=group)
                else:
                    rows = identity._qualified_name_rows(
                        db,
                        identity._approved_names(db, model, owner_column, ids).filter(model.id.in_(group)),
                        model,
                        owner_column,
                    )
                try:
                    timing["proof_seconds"] += monotonic() - started
                    qualified += len(rows)
                    checkpoint(
                        completed={"proof:" + kind + ":groups": timing["groups"], "qualified_names_total": qualified},
                        check=False,
                    )
                    checkpoint("name_dependencies:" + kind, check=False)
                    eligible = {row[0].id: row for row in rows}
                    source_rows = db.query(model).filter(model.id.in_(group)).all()
                    evidence_ids = {name.evidence_id for name in source_rows if name.evidence_id}
                    evidence_rows = {
                        row.id: row
                        for row in db.query(business.KifuNameResearchEvidence).filter(
                            business.KifuNameResearchEvidence.id.in_(evidence_ids)
                        )
                    }
                    creation_changes = {(model.__tablename__, name.id): [] for name in source_rows}
                    creation_changes.update(
                        {(business.KifuNameResearchEvidence.__tablename__, row_id): [] for row_id in evidence_ids}
                    )
                    changes = business.KifuNameChange
                    for change in db.query(*core._CHANGE_REFS).filter(
                        or_(
                            and_(changes.target_table == model.__tablename__, changes.target_row_id.in_(group)),
                            and_(
                                changes.target_table == business.KifuNameResearchEvidence.__tablename__,
                                changes.target_row_id.in_(evidence_ids),
                            ),
                        )
                    ):
                        creation_changes[change.target_table, change.target_row_id].append(change)
                    batch_cache = {}
                    started = monotonic()
                    for name in source_rows:
                        proxy = proxy_ids.setdefault((kind, name.id), len(proxy_ids) + 1)
                        approved = name.id in eligible
                        semantic = {
                            "decision_kind": name.decision_kind,
                            "evidence_id": name.evidence_id,
                            "generation_rule_version": name.generation_rule_version,
                            "public_primary": bool(
                                approved
                                and getattr(name, owner_column) in existing_owners
                                and name.lang in identity.PRIMARY_NAME_LANGUAGES
                                and name.decision_kind not in {"hidden", "error", "placeholder"}
                                and name.display_name.strip()
                            ),
                            "legacy_display": bool(
                                name.status == "verified"
                                and name.evidence_id is None
                                and name.decision_kind is None
                                and name.generation_rule_version is None
                                and name.revision is None
                            ),
                        }
                        if kind.startswith("raw_"):
                            semantic["raw_value"] = raw_owners[getattr(name, owner_column)]
                            semantic.update(
                                core._raw_description(name, eligible[name.id][2])
                                if approved
                                else {"raw_type": "ineligible", "record_label": False, "linked_event_ids": []}
                            )
                        ref = {
                            "id": proxy,
                            "name_kind": kind,
                            "source_key": str(name.id),
                            "source_name_id": name.id,
                            "owner_id": getattr(name, owner_column),
                            "match_class": "approved_exact",
                            "eligible": approved,
                            "lang": name.lang,
                            "display_name": name.display_name,
                            "normalized_term": identity.normalize_alias(name.display_name),
                            "semantic": semantic,
                            "exact_group_authorized_ids": [],
                            "valid": True,
                            "policy_version": m.POLICY_VERSION,
                        }
                        derived_names.append(ref)
                        kind_refs.append(ref)
                        owner_key = kind, ref["owner_id"]
                        representatives[owner_key] = min(representatives.get(owner_key, proxy), proxy)
                        _width_add(widths, "names", _body_bytes(conn, m.names, ref))
                        inputs = set(
                            core._proof_inputs(
                                db, kind, name, evidence_rows.get(name.evidence_id), creation_changes, batch_cache
                            )
                        )
                        source_inputs[ref["source_key"]] = inputs
                        inputs_checked += len(inputs)
                        scope_ids = (
                            core._finite_album_ids(eligible[name.id][2])
                            if kind.startswith("raw_") and approved
                            else set()
                        )
                        fixed, scope = _scope_dependency_inputs(
                            inputs,
                            scope_ids,
                            (
                                evidence_rows[name.evidence_id].research_payload
                                if name.evidence_id in evidence_rows
                                else {}
                            ),
                        )
                        fixed_source_inputs[ref["source_key"]] = fixed
                    # UNION is associative: release per-source sets after this
                    # packet, but retain each owner's union across all packets.
                    for accumulated, by_source in ((owner_inputs, source_inputs), (owner_fixed, fixed_source_inputs)):
                        for owner_key, inputs in core._owner_dependency_inputs(kind_refs, by_source).items():
                            accumulated.setdefault(owner_key, set()).update(inputs)
                    source_inputs.clear()
                    fixed_source_inputs.clear()
                    kind_refs.clear()
                    timing["dependency_seconds"] += monotonic() - started
                    started = monotonic()
                    if kind.startswith("raw_"):
                        checkpoint(
                            "live_member:" + kind, {"source_inputs_checked:" + kind: inputs_checked}, check=False
                        )
                        members = core._finite_members(db, kind, rows)
                        for name_id, values in members.items():
                            proxy = proxy_ids[kind, name_id]
                            for value in values:
                                row = dict(value, prepared_name_id=proxy)
                                key = proxy, row["album_id"], row["slot"]
                                full_member_keys.add(key)
                                _width_add(full_slot_widths, row["slot"], _body_bytes(conn, m.members, row))
                                slot_rows = calibration_members.setdefault(row["slot"], [])
                                if len(slot_rows) < 32 and row["slot"] != "selected_event":
                                    slot_rows.append(row)
                                if row["album_id"] in sample_ids:
                                    sample_members[key] = row
                        del members
                    timing["member_seconds"] += monotonic() - started
                finally:
                    del rows
                    if "eligible" in locals():
                        del eligible, source_rows, evidence_rows, creation_changes, batch_cache
                    db.expire_all()
                    db.expunge_all()
                checkpoint(
                    completed={
                        "source_inputs_checked:" + kind: inputs_checked,
                        "member_rows_full_scope": len(full_member_keys),
                        "member_rows_sample": len(sample_members),
                    }
                )
            if alias_model is not None:
                for alias in db.query(alias_model).filter(getattr(alias_model, owner_column).in_(ids)):
                    source_key = "alias:" + str(alias.id)
                    proxy = proxy_ids.setdefault((kind, source_key), len(proxy_ids) + 1)
                    owner_id = getattr(alias, owner_column)
                    ref = {
                        "id": proxy,
                        "name_kind": kind,
                        "source_key": source_key,
                        "source_name_id": None,
                        "owner_id": owner_id,
                        "match_class": "legacy_alias",
                        "eligible": True,
                        "lang": "*",
                        "display_name": alias.alias,
                        "normalized_term": alias.normalized_alias,
                        "semantic": {},
                        "exact_group_authorized_ids": [],
                        "valid": True,
                        "policy_version": m.POLICY_VERSION,
                    }
                    kind_refs.append(ref)
                    derived_names.append(ref)
                    _width_add(widths, "names", _body_bytes(conn, m.names, ref))
                    source_inputs[source_key] = {
                        (alias_model.__tablename__, str(alias.id)),
                        ("owner", core._key(kind, owner_id)),
                        ("token", core._key(kind, "*", identity.normalize_alias(alias.alias))),
                    }
                    fixed_source_inputs[source_key] = source_inputs[source_key]
            # Alias inputs join the same accumulated owner union, including an
            # owner whose names were checked in several different proof groups.
            for accumulated, by_source in ((owner_inputs, source_inputs), (owner_fixed, fixed_source_inputs)):
                for owner_key, inputs in core._owner_dependency_inputs(kind_refs, by_source).items():
                    accumulated.setdefault(owner_key, set()).update(inputs)
            for ref in kind_refs:
                owner_key = kind, ref["owner_id"]
                representatives[owner_key] = min(representatives.get(owner_key, ref["id"]), ref["id"])
            dependency_owners_by_kind[kind] = len(owner_inputs)
            for owner_key, inputs in owner_inputs.items():
                fixed = owner_fixed[owner_key]
                dependency_counts[kind] += len(inputs)
                fixed_counts[kind] += len(fixed)
                for input_kind, input_key in inputs - fixed:
                    key = owner_key, input_kind, input_key
                    full_scope_inputs.add(key)
                    if int(input_key) in sample_ids:
                        sampled_scope_inputs.add(key)
                for input_kind, input_key in inputs:
                    dependency = {
                        "target_kind": "name",
                        "target_key": str(representatives[owner_key]),
                        "input_kind": input_kind,
                        "input_key": str(input_key),
                    }
                    _width_add(widths, "dependencies", _dependency_bytes(conn, dependency))
            del source_inputs, fixed_source_inputs, kind_refs, owner_inputs, owner_fixed, representatives
            timing["owners"] = len(ids)
            timing["metadata_seconds"] = max(
                0,
                monotonic()
                - kind_started
                - timing["proof_seconds"]
                - timing["member_seconds"]
                - timing["dependency_seconds"],
            )
            timings[kind] = timing
            checkpoint(completed={"owner_dependencies:" + kind: dependency_counts[kind]})
        display_started = monotonic()
        display_dependencies = _sample_displays(conn, db, sample_ids, derived_names, sample_members, widths, checkpoint)
        display_seconds = monotonic() - display_started
    slots = {}
    for row in sample_members.values():
        _width_add(slots, row["slot"], _body_bytes(conn, m.members, row))
        bucket = calibration_members.setdefault(row["slot"], [])
        if len(bucket) < 32:
            bucket.append(row)
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
        "member_rows_full_scope": len(full_member_keys),
        "member_slots_full_scope": {slot: value["rows"] for slot, value in full_slot_widths.items()},
        "member_widths_full_scope": full_slot_widths,
        "member_rows_sample": len(sample_members),
        "member_slots": slots,
        "name_dependency_rows_by_kind": dependency_counts,
        "dependency_owners_by_kind": dependency_owners_by_kind,
        "name_dependency_storage_basis": "Owner UNION of all checked source names and aliases across proof groups; one representative target per owner",
        "name_dependency_fixed_rows_by_kind": fixed_counts,
        "name_dependency_scope_rows_full": len(full_scope_inputs),
        "name_dependency_scope_rows_sample": len(sampled_scope_inputs),
        "display_dependency_rows_sample": display_dependencies,
        "row_widths": widths,
        "timings_by_kind": timings,
        "display_seconds": display_seconds,
        "proof_seconds": sum(value["proof_seconds"] for value in timings.values()),
        "source_measure_seconds": monotonic() - proof_started,
        "_member_calibration_rows": [row for values in calibration_members.values() for row in values],
        "proof_observed": True,
        "scope": "sample owners/raw values; complete relevant finite proofs; unsampled closures are estimates",
        "member_full_scope_phase": "name-phase rows; selected_event rows are replaced by the original display-stage helper within sampled albums",
    }


def _sample_displays(conn, db, sample_ids, names, members, widths, checkpoint):
    from katrain.web.kifu import prepare_search as core

    dependency_count = 0
    for chunk in core._chunks(sorted(sample_ids), 500):
        checkpoint("display")
        albums = (
            db.query(business.KifuAlbum)
            .options(
                load_only(
                    *(
                        getattr(business.KifuAlbum, key)
                        for key in (*core.CONTEXT_FIELDS, "id", "list_hidden_reason", "source_path", "event_edition_id")
                    )
                )
            )
            .filter(business.KifuAlbum.id.in_(chunk))
            .all()
        )
        selections = {
            row["album_id"]: row
            for row in conn.execute(
                select(business.KifuAlbumEventSelection.__table__).where(
                    business.KifuAlbumEventSelection.album_id.in_(chunk)
                )
            ).mappings()
        }
        selected = identity.live_event_selections(db, albums, album_ids=set(selections))
        obscured = identity.obscured_program_event_ids(db, albums, selected_events=selected)
        event_ids = {album.event_id for album in albums if album.event_id} | {
            event_id for _raw, event_id in selected.values() if event_id
        }
        canonical = dict(
            db.query(business.KifuEvent.id, business.KifuEvent.canonical_name).filter(
                business.KifuEvent.id.in_(event_ids)
            )
        )
        players = dict(
            db.query(business.KifuPlayer.id, business.KifuPlayer.canonical_name).filter(
                business.KifuPlayer.id.in_(
                    {value for album in albums for value in (album.black_player_id, album.white_player_id) if value}
                )
            )
        )
        sources, source_inputs = {album.id: set() for album in albums}, {album.id: set() for album in albums}
        for link_id, album_id, source_id, source_key in (
            db.query(
                business.KifuAlbumSource.id,
                business.KifuAlbumSource.album_id,
                business.KifuSource.id,
                business.KifuSource.source_key,
            )
            .join(business.KifuSource, business.KifuAlbumSource.source_id == business.KifuSource.id)
            .filter(business.KifuAlbumSource.album_id.in_(chunk))
        ):
            sources[album_id].add(source_key)
            source_inputs[album_id].update(
                {
                    (business.KifuAlbumSource.__tablename__, str(link_id)),
                    (business.KifuSource.__tablename__, str(source_id)),
                }
            )
        before_members = [row for row in members.values() if row["album_id"] in chunk]
        approvals = {}
        languages = set(m.NAME_LANGUAGES) | {
            row["lang"]
            for row in names
            if row["name_kind"] == "raw_event" and row["eligible"] and row["lang"] in identity.LANGUAGES
        }
        for album in albums:
            album._prepared_has_selection = album.id in selections
        for lang in languages:
            maps = core._display_maps(albums, names, before_members, lang, canonical, approvals=True)
            approvals[lang] = {album.id: core._slot_approval(album, maps, obscured, selected) for album in albums}
            if lang not in m.NAME_LANGUAGES:
                continue
            maps = core._display_maps(albums, names, before_members, lang, canonical)
            hints = {}
            if not identity.strict_names_enabled() and lang == "cn":
                from katrain.web.kifu.first_pass_cn import event_hints

                hints = event_hints(db, albums, canonical, selected_events=selected)
            for album in albums:
                fallback = (
                    None
                    if identity.strict_names_enabled()
                    else core._legacy_names(db, album, lang, names, players, {}, canonical, hints)
                )
                black, white, event = identity.resolve_strict_display(
                    album, lang, *maps, obscured_event_ids=obscured, selected_events=selected, fallback_names=fallback
                )
                approval = approvals[lang][album.id]
                display = {
                    "album_id": album.id,
                    "name_lang": lang,
                    "player_black": black,
                    "player_white": white,
                    "event": event,
                    "black_name_source": list(approval[0]) if approval[0] else None,
                    "white_name_source": list(approval[1]) if approval[1] else None,
                    "event_name_source": list(approval[2]) if approval[2] else None,
                    "strict_outputs": {"sources": sorted(sources[album.id])},
                }
                _width_add(widths, "displays", _body_bytes(conn, m.displays, display))
        # Preserve production's whole <=500-album selection-history union.
        selection_inputs = core._selection_inputs(conn, set(selections)) if selections else set()
        for album in albums:
            inputs = core._album_display_dependencies(
                album,
                names,
                selected_event=selected.get(album.id),
                selection=selections.get(album.id),
                source_inputs=source_inputs[album.id],
                selection_inputs=selection_inputs,
            )
            dependency_count += len(inputs)
            for input_kind, input_key in inputs:
                value = {
                    "target_kind": "display",
                    "target_key": str(album.id),
                    "input_kind": input_kind,
                    "input_key": str(input_key),
                }
                _width_add(widths, "dependencies", _dependency_bytes(conn, value))
            for key in [key for key in members if key[1] == album.id and key[2] == "selected_event"]:
                del members[key]
            for row in core._selected_event_members(
                album, names, before_members, selected_event=selected.get(album.id), approvals_by_lang=approvals
            ):
                members[row["prepared_name_id"], row["album_id"], row["slot"]] = row
        db.expunge_all()
        checkpoint(
            completed={
                "display_rows": widths.get("displays", {}).get("rows", 0),
                "display_dependency_rows": dependency_count,
            }
        )
    return dependency_count


def plan(engine, args):
    started, rss_before = monotonic(), _rss_bytes()
    progress = {"phase": "initial_counts", "completed": {}}
    with engine.connect() as conn:
        transaction = conn.begin()
        if conn.dialect.name == "postgresql":
            conn.exec_driver_sql("SET TRANSACTION READ ONLY")

        def checkpoint(phase=None, completed=None, *, check=True):
            if completed:
                progress["completed"].update({key: value for key, value in completed.items() if type(value) is int})
            remaining = args.max_seconds - (monotonic() - started)
            if remaining <= 0:
                raise PreparationError("plan sampling time budget exceeded")
            if _rss_bytes() > 512 * MIB:
                raise PreparationError("plan memory budget exceeded")
            if phase is not None:
                progress["phase"] = phase
            if check:
                _timeout(conn, remaining)

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
            checkpoint(completed=counts, check=False)
            owner_counts, name_counts, alias_counts, languages = {}, {}, {}, {}
            for kind, (owner, model, _column, alias) in SPECS.items():
                checkpoint("counts:" + kind)
                owner_counts[kind] = conn.scalar(select(func.count()).select_from(owner))
                grouped = conn.execute(select(model.lang, func.count()).group_by(model.lang)).all()
                languages[kind] = {lang: count for lang, count in grouped}
                name_counts[kind] = sum(count for _lang, count in grouped)
                alias_counts[kind] = conn.scalar(select(func.count()).select_from(alias)) if alias else 0
                checkpoint(
                    completed={"source_names:" + kind: name_counts[kind], "owners:" + kind: owner_counts[kind]},
                    check=False,
                )
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
            metadata_started = monotonic()
            counts["proof_groups"] = _global_proof_metadata(conn, checkpoint)
            metadata_seconds = monotonic() - metadata_started
            sample = _sample_proof(conn, albums, checkpoint)
            sample.pop("_member_calibration_rows", None)  # Only a direct private Python caller may capture primitives.
            sample["global_metadata_seconds"] = metadata_seconds
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
            rows, estimate, relation_model, uncertainty = _estimate_plan(counts, sample, _rss_bytes())
            limits = {"seconds": 1800, "relation_bytes": MAX_RELATION_BYTES, "rss_bytes": 512 * MIB}
            exceeded = [key for key, maximum in limits.items() if estimate[key] is not None and estimate[key] > maximum]
            return {
                "ok": not exceeded and not unobserved and not uncertainty,
                "ready": False,
                "read_only": True,
                "counts": counts,
                "sample": sample,
                "estimated_rows": rows,
                "estimate": estimate,
                "relation_model": relation_model,
                "limits": limits,
                "uncertainty": uncertainty,
                "sampling_seconds_limit": args.max_seconds,
                "sampling_window_basis": "Root explicitly changed 30s to 120s after a complete fresh 1000-album diagnostic took 51.149s; original 30s gate did not pass",
                "exceeded": exceeded,
                "elapsed_seconds": monotonic() - started,
                "policy_signature": current_policy_signature(),
                "estimate_basis": "Live member PK density within sampled albums; per-source-name and per-album dependency sets; complete proof-group counts; actual Connection JSON serializer; isolated PG storage/write calibration; unsampled density remains an estimate",
            }
        except (PreparationError, SQLAlchemyError, ValueError) as exc:
            reason = (
                str(exc)
                if isinstance(exc, PreparationError)
                and str(exc) in {"plan sampling time budget exceeded", "plan memory budget exceeded"}
                else (
                    _error_reason(exc)
                    if isinstance(exc, SQLAlchemyError)
                    else "plan stopped (" + type(exc).__name__ + ")"
                )
            )
            return {
                "ok": False,
                "ready": False,
                "read_only": True,
                "reason": reason,
                "phase": progress["phase"],
                "completed": progress["completed"],
                "elapsed_seconds": monotonic() - started,
                "peak_rss_bytes": _rss_bytes(),
                "sampling_seconds_limit": args.max_seconds,
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
    planning.add_argument("--max-seconds", type=_bounded_number(120), default=120)
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
