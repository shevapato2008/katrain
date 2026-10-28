"""Materialize the existing name proof on the caller's business transaction.

The derived rows contain decisions and finite membership, not proof artifacts.
No function here commits, opens another connection, or calls a model/network.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import logging
import os
import resource
import sys
from time import monotonic

from sqlalchemy import String, and_, cast, delete, func, literal, or_, select
from sqlalchemy.orm import Session

from katrain.web.core import models_db as business
from katrain.web.kifu import identity, prepared_models as m
from katrain.web.kifu.name_raw_player_scope import PreparedRawPlayerScope, raw_player_scope_slot
from katrain.web.kifu.prepared_read import current_policy_signature, read_state


class PreparationError(ValueError):
    pass


@dataclass(frozen=True)
class PrepareBudget:
    max_albums: int = 500
    max_seconds: float = 1800
    max_bytes: int = 512 * 1024 * 1024
    max_relation_bytes: int = 2 * 1024 * 1024 * 1024


class _Budget:
    def __init__(self, value=None, conn=None):
        self.value = value or PrepareBudget()
        self.started = monotonic()
        self.conn = conn

    def check(self, albums=()):
        if len(albums) > self.value.max_albums:
            raise PreparationError(f"preparation album closure exceeds budget ({len(albums)})")
        if monotonic() - self.started > self.value.max_seconds:
            raise PreparationError("preparation time budget exceeded")
        peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        if sys.platform != "darwin":
            peak *= 1024
        if peak > self.value.max_bytes:
            raise PreparationError("preparation memory budget exceeded")
        if self.conn is not None and self.conn.dialect.name == "postgresql":
            size = self.conn.scalar(
                select(sum(func.pg_total_relation_size(table.name) for table in m.metadata.tables.values()))
            )
            if size > self.value.max_relation_bytes:
                raise PreparationError("prepared relations exceed size budget")


_SPECS = {
    "player": (business.KifuPlayer, business.KifuPlayerName, "player_id", business.KifuPlayerAlias),
    "event": (business.KifuEvent, business.KifuEventName, "event_id", business.KifuEventAlias),
    "raw_player": (business.KifuRawPlayerValue, business.KifuRawPlayerName, "raw_player_id", None),
    "raw_event": (business.KifuRawEventValue, business.KifuRawEventName, "raw_event_id", None),
}
_OWNER_TABLES = {spec[0].__tablename__: kind for kind, spec in _SPECS.items()}
_NAME_TABLES = {spec[1].__tablename__: kind for kind, spec in _SPECS.items()}
_ALIAS_TABLES = {spec[3].__tablename__: kind for kind, spec in _SPECS.items() if spec[3]}


def _chunks(values, size=400):
    values = list(values)
    for offset in range(0, len(values), size):
        yield values[offset : offset + size]


def _key(*parts):
    return json.dumps(parts, ensure_ascii=False, separators=(",", ":"))


def _rows(db, model, ids):
    return [row for chunk in _chunks(ids) for row in db.query(model).filter(model.id.in_(chunk))]


def _upsert(conn, table, rows, keys):
    if not rows:
        return
    if conn.dialect.name == "postgresql":
        from sqlalchemy.dialects.postgresql import insert
    elif conn.dialect.name == "sqlite":
        from sqlalchemy.dialects.sqlite import insert
    else:
        raise PreparationError("unsupported preparation database")
    for chunk in _chunks(rows, 500):
        statement = insert(table).values(chunk)
        updates = {key: getattr(statement.excluded, key) for key in chunk[0] if key not in keys}
        if updates:
            statement = statement.on_conflict_do_update(index_elements=[table.c[key] for key in keys], set_=updates)
        else:
            statement = statement.on_conflict_do_nothing(index_elements=[table.c[key] for key in keys])
        conn.execute(statement)


def _dependencies(conn, target_kind, targets):
    for keys in _chunks([str(key) for key in targets]):
        conn.execute(
            delete(m.dependencies).where(
                m.dependencies.c.target_kind == target_kind, m.dependencies.c.target_key.in_(keys)
            )
        )
    rows = [
        {"target_kind": target_kind, "target_key": str(target_key), "input_kind": kind, "input_key": str(key)}
        for target_key, inputs in targets.items()
        for kind, key in sorted(set(inputs))
    ]
    _upsert(conn, m.dependencies, rows, ("target_kind", "target_key", "input_kind", "input_key"))


def _proof_inputs(db, kind, name, evidence, creation_changes, batch_cache):
    """Retain row and absent-collection watches even when the proof rejected a row."""
    owner_model, name_model, owner_col, _alias = _SPECS[kind]
    owner_id = getattr(name, owner_col)
    result = {
        (name_model.__tablename__, str(name.id)),
        (owner_model.__tablename__, str(owner_id)),
        ("owner", _key(kind, owner_id)),
        ("token", _key(kind, name.lang, identity.normalize_alias(name.display_name))),
    }
    if kind.startswith("raw_"):
        owner = db.get(owner_model, owner_id)
        if owner is not None:
            result.add(("raw_scope", _key(kind, owner.raw_value)))
    evidence_ids = {name.evidence_id} if name.evidence_id else set()
    batch_ids = set()
    if evidence is not None:
        result.add((business.KifuNameSourceRegistry.__tablename__, str(evidence.source_registry_id)))
        payload = evidence.research_payload or {}

        def visit(value, context=None):
            if isinstance(value, list):
                for item in value:
                    visit(item, context)
            elif isinstance(value, dict):
                if type(value.get("batch_id")) is int:
                    batch_ids.add(value["batch_id"])
                if type(value.get("album_id")) is int:
                    result.add((business.KifuAlbum.__tablename__, str(value["album_id"])))
                    result.add(("album_sources", str(value["album_id"])))
                    result.add((business.KifuAlbumEventSelection.__tablename__, str(value["album_id"])))
                if type(value.get("source_id")) is int:
                    result.add((business.KifuSource.__tablename__, str(value["source_id"])))
                if type(value.get("base_name_id")) is int:
                    result.add((business.KifuEventName.__tablename__, str(value["base_name_id"])))
                if type(value.get("base_evidence_id")) is int:
                    evidence_ids.add(value["base_evidence_id"])
                if type(value.get("series_event_id")) is int:
                    result.add((business.KifuEvent.__tablename__, str(value["series_event_id"])))
                if value.get("kind") == "existing_locale" and type(value.get("name_id")) is int:
                    result.add((name_model.__tablename__, str(value["name_id"])))
                    source = db.get(name_model, value["name_id"])
                    if source and source.evidence_id:
                        evidence_ids.add(source.evidence_id)
                if context in {"source_name", "source_evidence", "source_batch", "owner_preimage"}:
                    table = {
                        "source_name": business.KifuPlayerName,
                        "source_evidence": business.KifuNameResearchEvidence,
                        "source_batch": business.KifuNameBatch,
                        "owner_preimage": business.KifuPlayer,
                    }[context]
                    if type(value.get("id")) is int:
                        result.add((table.__tablename__, str(value["id"])))
                        if context == "source_batch":
                            batch_ids.add(value["id"])
                owner = value.get("owner")
                if isinstance(owner, dict) and owner.get("kind") in _SPECS and type(owner.get("id")) is int:
                    result.add((_SPECS[owner["kind"]][0].__tablename__, str(owner["id"])))
                for field, item in value.items():
                    if field == "occurrence_album_ids" and isinstance(item, list):
                        result.update(
                            (business.KifuAlbum.__tablename__, str(album_id))
                            for album_id in item
                            if type(album_id) is int
                        )
                    visit(item, field)

        visit(payload)
    # Creation ledgers also identify a method whose mutable discriminator was erased.
    missing = {
        row_id
        for row_id in evidence_ids
        if (business.KifuNameResearchEvidence.__tablename__, row_id) not in creation_changes
    }
    for row_id in missing:
        creation_changes[business.KifuNameResearchEvidence.__tablename__, row_id] = []
    if missing:
        for change in db.query(business.KifuNameChange).filter(
            business.KifuNameChange.target_table == business.KifuNameResearchEvidence.__tablename__,
            business.KifuNameChange.target_row_id.in_(missing),
        ):
            creation_changes[change.target_table, change.target_row_id].append(change)
    changes = list(creation_changes.get((name_model.__tablename__, name.id), ()))
    changes.extend(
        change
        for evidence_id in evidence_ids
        for change in creation_changes.get((business.KifuNameResearchEvidence.__tablename__, evidence_id), ())
    )
    for change in changes:
        batch_ids.add(change.batch_id)
        result.add((business.KifuNameChange.__tablename__, str(change.id)))
    result.update((business.KifuNameResearchEvidence.__tablename__, str(row_id)) for row_id in evidence_ids)
    for batch_id in batch_ids - batch_cache.keys():
        batch_cache[batch_id] = db.get(business.KifuNameBatch, batch_id)
    for batch in (batch_cache[batch_id] for batch_id in batch_ids if batch_cache[batch_id] is not None):
        result.add((business.KifuNameBatch.__tablename__, str(batch.id)))
        result.add((business.KifuNameSourceRegistry.__tablename__, str(batch.source_registry_id)))
    return result


def _raw_description(name, proof):
    semantic = {"raw_type": "unrestricted", "record_label": False, "linked_event_ids": [], "linked_unlinked": False}
    if isinstance(proof, PreparedRawPlayerScope):
        semantic["raw_type"] = "finite_player"
        semantic["frozen_member_count"] = len(proof.members)
    elif isinstance(proof, dict):
        if "first_pass" in proof:
            semantic.update(
                raw_type="first_pass",
                record_label=bool(proof.get("record_label")),
                frozen_member_count=len(proof["first_pass"]),
            )
        elif "linked_literal" in proof:
            semantic.update(
                raw_type="linked_literal",
                frozen_member_count=len(proof["linked_literal"]),
                linked_unlinked=any(row["event_id"] is None for row in proof["linked_literal"]),
                linked_event_ids=sorted(
                    {row["event_id"] for row in proof["linked_literal"] if row["event_id"] is not None}
                ),
            )
        elif name.decision_kind == "archive_description":
            semantic["raw_type"] = "archive_description"
        else:
            semantic["raw_type"] = "composed"
    elif name.decision_kind == "translated":
        semantic["raw_type"] = "translated"
    return semantic


def _finite_album_ids(proof):
    if isinstance(proof, PreparedRawPlayerScope):
        return {album_id for album_id, _slot in proof.members}
    if not isinstance(proof, dict):
        return set()
    if "first_pass" in proof:
        return {row["album_id"] for row in proof["first_pass"]}
    if "linked_literal" in proof:
        return {row["id"] for row in proof["linked_literal"]}
    if "declaration" in proof:
        return set(proof["declaration"]["occurrence_album_ids"])
    return {album_id for entry in proof["scope"]["content"]["raws"] for album_id in entry["occurrence_album_ids"]}


def _finite_members(db, kind, qualified):
    finite = [(name, raw, proof) for name, raw, proof in qualified if proof is not None]
    ids = set().union(*(_finite_album_ids(proof) for _name, _raw, proof in finite)) if finite else set()
    albums = _rows(db, business.KifuAlbum, ids)
    physical_selected = {
        album_id
        for chunk in _chunks(ids)
        for album_id, in db.query(business.KifuAlbumEventSelection.album_id).filter(
            business.KifuAlbumEventSelection.album_id.in_(chunk)
        )
    }
    selected = identity.live_event_selections(db, albums, album_ids=physical_selected)
    linked = identity._linked_live_members(db, qualified) if kind == "raw_event" else set()
    result = {}
    for name, raw, proof in finite:
        members = []
        if kind == "raw_player":
            for album in albums:
                for slot in ("black", "white"):
                    if raw_player_scope_slot(proof, album, slot, raw):
                        members.append(
                            {
                                "album_id": album.id,
                                "slot": slot,
                                "event_id": None,
                                "selection_id": None,
                                "semantic": {
                                    "display": True,
                                    "search": True,
                                    "context": proof.members[album.id, slot],
                                    "raw_value": raw,
                                },
                            }
                        )
        else:
            mapping = identity._raw_event_map(
                [(name, raw, proof)], albums, selected, selected_ids=physical_selected, linked_members=linked
            )
            frozen = _finite_album_ids(proof)
            for album in albums:
                if album.id not in frozen:
                    continue
                if "first_pass" in proof:
                    allowed = next(
                        (row for row in proof["first_pass"] if row["album_id"] == album.id and row["slot"] == "event"),
                        None,
                    )
                    search = bool(
                        allowed
                        and allowed["approved"]
                        and allowed["duplicate_of_id"] is None
                        and allowed["list_hidden_reason"] is None
                        and album.event == raw
                        and album.event_id == allowed["event_id"]
                        and album.duplicate_of_id is None
                        and album.id not in physical_selected
                    )
                elif "linked_literal" in proof:
                    search = (album.id, raw, album.event_id) in linked
                elif name.decision_kind == "archive_description":
                    search = album.event == raw and album.event_id is None
                else:
                    search = album.event == raw and album.event_id == proof["dependencies"]["series_event_id"]
                display = album.event == raw and album.id not in selected and (album.id, raw, album.event_id) in mapping
                if search or display:
                    members.append(
                        {
                            "album_id": album.id,
                            "slot": "event",
                            "event_id": album.event_id,
                            "selection_id": None,
                            "semantic": {"display": display, "search": search, "raw_value": raw},
                        }
                    )
                if album.id in selected:
                    selected_raw, event_id = selected[album.id]
                    if selected_raw == raw and (album.id, raw, event_id) in mapping:
                        members.append(
                            {
                                "album_id": album.id,
                                "slot": "selected_event",
                                "event_id": event_id,
                                "selection_id": album.id,
                                "semantic": {"display": True, "raw_value": raw},
                            }
                        )
        result[name.id] = members
    return result


def _prepare_owners(conn, db, targets, budget):
    """One proof read per domain/owner batch, including rejected verified rows."""
    prepared_count = 0
    for kind, owner_ids in targets.items():
        if not owner_ids:
            continue
        budget.check()
        owner_model, name_model, owner_col, alias_model = _SPECS[kind]
        owners = {row.id: row for row in _rows(db, owner_model, owner_ids)}
        source_rows = [
            row
            for chunk in _chunks(owner_ids)
            for row in db.query(name_model).filter(getattr(name_model, owner_col).in_(chunk))
        ]
        evidence_ids = {row.evidence_id for row in source_rows if row.evidence_id}
        evidence = {row.id: row for row in _rows(db, business.KifuNameResearchEvidence, evidence_ids)}
        creation_changes = {(name_model.__tablename__, row.id): [] for row in source_rows}
        creation_changes.update(
            {(business.KifuNameResearchEvidence.__tablename__, row_id): [] for row_id in evidence_ids}
        )
        clauses = [
            and_(
                business.KifuNameChange.target_table == name_model.__tablename__,
                business.KifuNameChange.target_row_id.in_([row.id for row in source_rows]),
            ),
            and_(
                business.KifuNameChange.target_table == business.KifuNameResearchEvidence.__tablename__,
                business.KifuNameChange.target_row_id.in_(evidence_ids),
            ),
        ]
        for change in db.query(business.KifuNameChange).filter(or_(*clauses)):
            creation_changes[change.target_table, change.target_row_id].append(change)
        batch_cache = {}
        if kind == "raw_player":
            qualified = identity._approved_raw_player_names(db, values={row.raw_value for row in owners.values()})
        elif kind == "raw_event":
            qualified = identity._approved_raw_event_names(db, values={row.raw_value for row in owners.values()})
        else:
            qualified = identity._qualified_name_rows(
                db, identity._approved_names(db, name_model, owner_col, set(owner_ids)), name_model, owner_col
            )
        eligible = {row[0].id: row for row in qualified}
        finite_members = _finite_members(db, kind, qualified) if kind.startswith("raw_") else {}
        values, inputs_by_source = [], {}
        for name in source_rows:
            approved = name.id in eligible
            semantic = {
                "decision_kind": name.decision_kind,
                "evidence_id": name.evidence_id,
                "generation_rule_version": name.generation_rule_version,
                "public_primary": bool(
                    approved
                    and getattr(name, owner_col) in owners
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
                owner = owners.get(getattr(name, owner_col))
                semantic["raw_value"] = owner.raw_value if owner else None
                semantic.update(
                    _raw_description(name, eligible[name.id][2])
                    if approved
                    else {"raw_type": "ineligible", "record_label": False, "linked_event_ids": []}
                )
            authorization = set()
            if kind == "player" and approved:
                # The SQL exact class remains distinct from normalize_alias. Most
                # names have one owner and never need the finite-group proof.
                query = identity._approved_names(db, name_model, owner_col).filter(
                    or_(
                        name_model.display_name == name.display_name,
                        func.lower(name_model.display_name) == name.display_name.lower(),
                    )
                )
                ids = {value for value, in query.with_entities(name_model.player_id)}
                if len(ids) > 1:
                    rows = identity._qualified_name_rows(db, query, name_model, owner_col)
                    rows = [
                        (row, proof)
                        for row, proof in rows
                        if identity.normalize_alias(row.display_name) == identity.normalize_alias(name.display_name)
                    ]
                    authorization = identity._finite_shared_player_ids(
                        db, rows, identity.normalize_alias(name.display_name)
                    )
            values.append(
                {
                    "name_kind": kind,
                    "source_key": str(name.id),
                    "source_name_id": name.id,
                    "lang": name.lang,
                    "display_name": name.display_name,
                    "normalized_term": identity.normalize_alias(name.display_name),
                    "match_class": "approved_exact",
                    "owner_id": getattr(name, owner_col),
                    "eligible": approved,
                    "exact_group_authorized_ids": sorted(authorization),
                    "semantic": semantic,
                    "valid": True,
                    "policy_version": m.POLICY_VERSION,
                }
            )
            inputs_by_source[str(name.id)] = _proof_inputs(
                db, kind, name, evidence.get(name.evidence_id), creation_changes, batch_cache
            )
        if alias_model is not None:
            for chunk in _chunks(owner_ids):
                for alias in db.query(alias_model).filter(getattr(alias_model, owner_col).in_(chunk)):
                    source_key = "alias:" + str(alias.id)
                    values.append(
                        {
                            "name_kind": kind,
                            "source_key": source_key,
                            "source_name_id": None,
                            "lang": "*",
                            "display_name": alias.alias,
                            "normalized_term": alias.normalized_alias,
                            "match_class": "legacy_alias",
                            "owner_id": getattr(alias, owner_col),
                            "eligible": True,
                            "exact_group_authorized_ids": [],
                            "semantic": {},
                            "valid": True,
                            "policy_version": m.POLICY_VERSION,
                        }
                    )
                    inputs_by_source[source_key] = {
                        (alias_model.__tablename__, str(alias.id)),
                        ("owner", _key(kind, getattr(alias, owner_col))),
                        ("token", _key(kind, "*", identity.normalize_alias(alias.alias))),
                    }
        previous = (
            conn.execute(select(m.names).where(m.names.c.name_kind == kind, m.names.c.owner_id.in_(owner_ids)))
            .mappings()
            .all()
        )
        live_sources = {(row["source_key"], row["lang"], row["match_class"]) for row in values}
        for ids in _chunks([row["id"] for row in previous]):
            conn.execute(delete(m.members).where(m.members.c.prepared_name_id.in_(ids)))
            conn.execute(
                delete(m.dependencies).where(
                    m.dependencies.c.target_kind == "name",
                    m.dependencies.c.target_key.in_([str(value) for value in ids]),
                )
            )
        obsolete_ids = []
        for row in previous:
            if (row["source_key"], row["lang"], row["match_class"]) not in live_sources:
                obsolete_ids.append(row["id"])
        for ids in _chunks(obsolete_ids):
            conn.execute(delete(m.names).where(m.names.c.id.in_(ids)))
        _upsert(conn, m.names, values, ("name_kind", "source_key", "lang", "match_class"))
        current = (
            conn.execute(select(m.names).where(m.names.c.name_kind == kind, m.names.c.owner_id.in_(owner_ids)))
            .mappings()
            .all()
        )
        member_values = []
        dependency_values = {}
        for row in current:
            dependency_values[row["id"]] = inputs_by_source[row["source_key"]]
            member_values.extend(
                dict(value, prepared_name_id=row["id"]) for value in finite_members.get(row["source_name_id"], ())
            )
        _dependencies(conn, "name", dependency_values)
        _upsert(conn, m.members, member_values, ("prepared_name_id", "album_id", "slot"))
        prepared_count += len(values)
    return prepared_count


def _slot_approval(album, maps, obscured, selected):
    """The pure selection part of identity.strict_slot_approvals."""
    players, events, canonical, raw_players, raw_events = maps
    raw, event_id = selected.get(album.id, (album.event, album.event_id))
    black = (
        players.get(album.black_player_id)
        if album.black_player_id
        else identity._raw_player_slot(raw_players, album, "black")
    )
    white = (
        players.get(album.white_player_id)
        if album.white_player_id
        else identity._raw_player_slot(raw_players, album, "white")
    )
    if event_id:
        event = events.get(event_id)
        linked = raw_events.get((album.id, raw, event_id))
        if linked is not None:
            event = linked
        elif identity.parse_event(raw, None).category == "formal_event_candidate":
            event = (
                identity._raw_event_value(raw_events, album.id, raw, event_id)
                if event and canonical.get(event_id) == "Oteai"
                else None
            )
        elif event:
            event = identity._raw_event_value(
                raw_events,
                album.id,
                raw,
                event_id,
                None if identity.structure_event(raw or "")["components"] else event,
            )
    else:
        event = (
            ("hidden", None)
            if identity._empty_event(raw)
            else identity._raw_event_value(raw_events, album.id, raw or "", event_id)
        )
    return black, white, None if album.id in obscured else event


def _display_maps(albums, rows, member_rows, lang, canonical, *, approvals=False):
    players, events, raw_players, raw_events = {}, {}, {}, {}
    by_name = {}
    for member in member_rows:
        by_name.setdefault(member["prepared_name_id"], []).append(member)
    for row in rows:
        if row["match_class"] != "approved_exact" or not row["eligible"] or row["lang"] != lang:
            continue
        semantic = row["semantic"]
        value = (
            ("record_label" if semantic.get("record_label") else semantic["decision_kind"], semantic["evidence_id"])
            if approvals
            else row["display_name"]
        )
        kind, owner_id = row["name_kind"], row["owner_id"]
        if kind == "player":
            players[owner_id] = value
        elif kind == "event":
            if approvals or owner_id in canonical:
                events[owner_id] = value
        elif kind == "raw_player":
            raw = semantic["raw_value"]
            scope = None
            if semantic["raw_type"] == "finite_player":
                scope = PreparedRawPlayerScope(
                    raw,
                    {
                        (member["album_id"], member["slot"]): member["semantic"]["context"]
                        for member in by_name.get(row["id"], ())
                    },
                )
            raw_players[raw] = value, scope
        elif kind == "raw_event":
            raw = semantic["raw_value"]
            if semantic["raw_type"] == "unrestricted":
                raw_events[raw] = value
            elif semantic["raw_type"] == "translated":
                for album in albums:
                    if (
                        album.event == raw
                        and album.event_id is None
                        and album.duplicate_of_id is None
                        and album.list_hidden_reason is None
                        and not getattr(album, "_prepared_has_selection", False)
                    ):
                        raw_events[album.id, raw, None] = value
            else:
                for member in by_name.get(row["id"], ()):
                    if member["semantic"].get("display"):
                        raw_events[member["album_id"], raw, member["event_id"]] = value
    return players, events, canonical, raw_players, raw_events


def _legacy_names(db, album, lang, rows, players, events, canonical, hints):
    legacy_players, legacy_events = {}, {}
    for row in rows:
        if row["name_kind"] in {"player", "event"} and row["lang"] == lang and row["semantic"].get("legacy_display"):
            if row["name_kind"] == "player":
                legacy_players[row["owner_id"]] = row["display_name"]
            elif row["owner_id"] in canonical:
                legacy_events[row["owner_id"]] = row["display_name"]
    black = identity.parse_player(album.player_black, None).name
    white = identity.parse_player(album.player_white, None).name
    if lang == "cn":
        from katrain.web.kifu.first_pass_cn import player_name

        for owner_id, name in players.items():
            if any("\u3400" <= char <= "\u9fff" for char in name):
                legacy_players.setdefault(owner_id, name)
        black = player_name(album.player_black) or black
        white = player_name(album.player_white) or white
    linked = canonical.get(album.event_id)
    translated = legacy_events.get(album.event_id)
    event = identity.display_event_name(album.event, translated, lang, linked_canonical_name=linked)
    if translated is None:
        event = hints.get(album.id) or identity.display_event_name(
            album.event, linked if lang == "cn" else None, lang, linked_canonical_name=linked
        )
    return legacy_players.get(album.black_player_id) or black, legacy_players.get(album.white_player_id) or white, event


def _selection_inputs(conn, album_ids):
    """Capture the same finite history collections used by the selection prover."""
    from katrain.web.kifu.event_selection import _selection_name_history

    inputs = set()
    related_albums = set(album_ids)
    history = _selection_name_history(conn, set(album_ids))
    if history is None:
        return inputs
    batches, changes = history
    for batch_id, batch in batches.items():
        inputs.add((business.KifuNameBatch.__tablename__, str(batch_id)))
        inputs.add((business.KifuNameSourceRegistry.__tablename__, str(batch["source_registry_id"])))
        artifact = batch.get("reviewed_artifact") or {}
        bundle = artifact.get("bundle") or {}
        for link in bundle.get("album_links", ()):
            if isinstance(link, dict) and type(link.get("album_id")) is int:
                related_albums.add(link["album_id"])
        for change in changes[batch_id]:
            inputs.add((business.KifuNameChange.__tablename__, str(change["id"])))
            inputs.add((change["target_table"], str(change["target_row_id"])))
            for image in (change["before_image"], change["after_image"]):
                if isinstance(image, dict):
                    for kind, fields in (
                        ("raw_player", ("player_black", "player_white")),
                        ("raw_event", ("event", "selected_raw")),
                    ):
                        inputs.update(
                            ("raw_scope", _key(kind, image[field]))
                            for field in fields
                            if isinstance(image.get(field), str)
                        )
                    if change["target_table"] == business.KifuAlbum.__tablename__:
                        related_albums.add(change["target_row_id"])
                    for field, model in (
                        ("black_player_id", business.KifuPlayer),
                        ("white_player_id", business.KifuPlayer),
                        ("player_id", business.KifuPlayer),
                        ("event_id", business.KifuEvent),
                        ("raw_player_id", business.KifuRawPlayerValue),
                        ("raw_event_id", business.KifuRawEventValue),
                        ("evidence_id", business.KifuNameResearchEvidence),
                    ):
                        if type(image.get(field)) is int:
                            inputs.add((model.__tablename__, str(image[field])))
    for album_id in related_albums:
        inputs.update(
            {
                (business.KifuAlbum.__tablename__, str(album_id)),
                ("album_sources", str(album_id)),
                (business.KifuAlbumEventSelection.__tablename__, str(album_id)),
            }
        )
    for chunk in _chunks(related_albums):
        for row in conn.execute(
            select(business.KifuAlbumSource.__table__).where(business.KifuAlbumSource.album_id.in_(chunk))
        ).mappings():
            inputs.add((business.KifuAlbumSource.__tablename__, str(row["id"])))
            inputs.add((business.KifuSource.__tablename__, str(row["source_id"])))
    return inputs


def _prepare_displays(conn, db, album_ids, budget, *, refresh_invalid_names=False):
    budget.check(album_ids)
    albums = _rows(db, business.KifuAlbum, album_ids)
    existing_ids = {album.id for album in albums}
    for chunk in _chunks(set(album_ids) - existing_ids):
        conn.execute(delete(m.displays).where(m.displays.c.album_id.in_(chunk)))
        conn.execute(delete(m.members).where(m.members.c.album_id.in_(chunk)))
        conn.execute(
            delete(m.dependencies).where(
                m.dependencies.c.target_kind.in_(("display", "selection")),
                m.dependencies.c.target_key.in_([str(value) for value in chunk]),
            )
        )
    if not albums:
        return 0
    selections = {
        row["album_id"]: row
        for row in conn.execute(
            select(business.KifuAlbumEventSelection.__table__).where(
                business.KifuAlbumEventSelection.album_id.in_(existing_ids)
            )
        ).mappings()
    }
    selected = identity.live_event_selections(db, albums, album_ids=set(selections))
    obscured = identity.obscured_program_event_ids(db, albums, selected_events=selected)
    owner_ids = {
        "player": {value for album in albums for value in (album.black_player_id, album.white_player_id) if value},
        "event": {album.event_id for album in albums if album.event_id}
        | {event_id for _raw, event_id in selected.values() if event_id},
    }
    for kind, raw_values in (
        ("raw_player", {value for album in albums for value in (album.player_black, album.player_white)}),
        ("raw_event", {album.event or "" for album in albums} | {raw for raw, _event_id in selected.values()}),
    ):
        model = _SPECS[kind][0]
        owner_ids[kind] = {
            row_id for chunk in _chunks(raw_values) for row_id, in db.query(model.id).filter(model.raw_value.in_(chunk))
        }
    conditions = [
        and_(m.names.c.name_kind == kind, m.names.c.owner_id.in_(ids)) for kind, ids in owner_ids.items() if ids
    ]
    rows = conn.execute(select(m.names).where(or_(*conditions))).mappings().all() if conditions else []
    if refresh_invalid_names:
        # Initial checkpoints may span normal writes. Refresh only invalid
        # owners actually needed by this display page, leaving their dirty keys
        # for the complete final closure and keeping initial coverage unready.
        targets = {kind: set() for kind in _SPECS}
        for row in rows:
            if not row["valid"] or row["policy_version"] != m.POLICY_VERSION:
                targets[row["name_kind"]].add(row["owner_id"])
        for kind, ids in targets.items():
            for chunk in _chunks(ids, budget.value.max_albums):
                _prepare_owners(conn, db, {kind: set(chunk)}, budget)
        if any(targets.values()):
            rows = conn.execute(select(m.names).where(or_(*conditions))).mappings().all()
    if any(not row["valid"] or row["policy_version"] != m.POLICY_VERSION for row in rows):
        raise PreparationError("display depends on an unprepared name")
    member_rows = conn.execute(select(m.members).where(m.members.c.album_id.in_(existing_ids))).mappings().all()
    players = {row.id: row.canonical_name for row in _rows(db, business.KifuPlayer, owner_ids["player"])}
    canonical = {row.id: row.canonical_name for row in _rows(db, business.KifuEvent, owner_ids["event"])}
    sources = {album.id: set() for album in albums}
    source_inputs = {album.id: set() for album in albums}
    for link, source in (
        db.query(business.KifuAlbumSource, business.KifuSource)
        .join(business.KifuSource, business.KifuAlbumSource.source_id == business.KifuSource.id)
        .filter(business.KifuAlbumSource.album_id.in_(existing_ids))
    ):
        sources[link.album_id].add(source.source_key)
        source_inputs[link.album_id].update(
            {
                (business.KifuAlbumSource.__tablename__, str(link.id)),
                (business.KifuSource.__tablename__, str(source.id)),
            }
        )
    dependency_values = {}
    for album in albums:
        album._prepared_has_selection = album.id in selections
    outputs, approvals_by_lang = [], {}
    for lang in m.NAME_LANGUAGES:
        maps = _display_maps(albums, rows, member_rows, lang, canonical)
        approval_maps = _display_maps(albums, rows, member_rows, lang, canonical, approvals=True)
        approvals_by_lang[lang] = {
            album.id: _slot_approval(album, approval_maps, obscured, selected) for album in albums
        }
        hints = {}
        if not identity.strict_names_enabled() and lang == "cn":
            from katrain.web.kifu.first_pass_cn import event_hints

            hints = event_hints(db, albums, canonical, selected_events=selected)
        for album in albums:
            fallback = (
                None
                if identity.strict_names_enabled()
                else _legacy_names(db, album, lang, rows, players, {}, canonical, hints)
            )
            black, white, event = identity.resolve_strict_display(
                album, lang, *maps, obscured_event_ids=obscured, selected_events=selected, fallback_names=fallback
            )
            approval = approvals_by_lang[lang][album.id]
            outputs.append(
                {
                    "album_id": album.id,
                    "name_lang": lang,
                    "valid": True,
                    "policy_version": m.POLICY_VERSION,
                    "player_black": black,
                    "player_white": white,
                    "event": event,
                    "black_name_source": list(approval[0]) if approval[0] else None,
                    "white_name_source": list(approval[1]) if approval[1] else None,
                    "event_name_source": list(approval[2]) if approval[2] else None,
                    "obscured": album.id in obscured,
                    "selection_id": album.id if album.id in selected else None,
                    "strict_outputs": {"sources": sorted(sources[album.id])},
                }
            )
    _upsert(conn, m.displays, outputs, ("album_id", "name_lang"))
    # Search still accepts all historical name locales, even though public
    # displays deliberately materialize only the five current name languages.
    search_languages = {
        row["lang"]
        for row in rows
        if row["name_kind"] == "raw_event" and row["eligible"] and row["lang"] in identity.LANGUAGES
    }
    for lang in search_languages - approvals_by_lang.keys():
        maps = _display_maps(albums, rows, member_rows, lang, canonical, approvals=True)
        approvals_by_lang[lang] = {album.id: _slot_approval(album, maps, obscured, selected) for album in albums}
    selection_inputs = _selection_inputs(conn, set(selections)) if selections else set()
    for album in albums:
        inputs = {
            (business.KifuAlbum.__tablename__, str(album.id)),
            ("album_sources", str(album.id)),
            (business.KifuAlbumEventSelection.__tablename__, str(album.id)),
        } | source_inputs[album.id]
        album_owners = {
            "player": {value for value in (album.black_player_id, album.white_player_id) if value},
            "event": {value for value in (album.event_id, selected.get(album.id, (None, None))[1]) if value},
            "raw_player": {
                row["owner_id"]
                for row in rows
                if row["name_kind"] == "raw_player"
                and row["semantic"].get("raw_value") in {album.player_black, album.player_white}
            },
            "raw_event": {
                row["owner_id"]
                for row in rows
                if row["name_kind"] == "raw_event"
                and row["semantic"].get("raw_value") in {album.event, selected.get(album.id, (None, None))[0]}
            },
        }
        for kind, ids in album_owners.items():
            inputs.update(("owner", _key(kind, owner_id)) for owner_id in ids)
        # Raw scope watches belong to the name/selection proof that actually
        # reads a cohort. A new canonical game with the same literal must not
        # dirty every other display which merely falls back to that literal.
        for row in rows:
            if row["source_name_id"] is not None and row["owner_id"] in album_owners.get(row["name_kind"], ()):
                inputs.add((_SPECS[row["name_kind"]][1].__tablename__, str(row["source_name_id"])))
        if album.id in selections:
            inputs.add((business.KifuEventSelectionBatch.__tablename__, str(selections[album.id]["batch_id"])))
            inputs |= selection_inputs
        dependency_values[album.id] = inputs
    _dependencies(conn, "display", dependency_values)
    # Selected search approval is independent of the later query substring. A
    # physical but rejected selection is deliberately retained in business SQL.
    selected_members = []
    conn.execute(delete(m.members).where(m.members.c.album_id.in_(existing_ids), m.members.c.slot == "selected_event"))
    for album in albums:
        if album.id not in selected or album.duplicate_of_id is not None or album.event != "GNUGo3.8":
            continue
        raw, event_id = selected[album.id]
        structured = (
            bool(identity.structure_event(raw)["components"])
            or identity.parse_event(raw, None).category == "formal_event_candidate"
        )
        identity_allowed = not structured or any(
            values[album.id][2] is not None for values in approvals_by_lang.values()
        )
        for row in rows:
            if not row["eligible"] or row["match_class"] != "approved_exact":
                continue
            semantic = row["semantic"]
            if row["name_kind"] == "event" and row["owner_id"] == event_id:
                selected_members.append(
                    {
                        "prepared_name_id": row["id"],
                        "album_id": album.id,
                        "slot": "selected_event",
                        "event_id": event_id,
                        "selection_id": album.id,
                        "semantic": {"identity_search": identity_allowed, "raw_value": raw, "display": False},
                    }
                )
            elif row["name_kind"] == "raw_event" and semantic.get("raw_value") == raw:
                approved = approvals_by_lang.get(row["lang"], {}).get(album.id, (None, None, None))[2]
                allowed = semantic.get("decision_kind") != "translated" and approved == (
                    semantic.get("decision_kind"),
                    semantic.get("evidence_id"),
                )
                display = any(
                    member["prepared_name_id"] == row["id"]
                    and member["album_id"] == album.id
                    and member["slot"] == "selected_event"
                    and member["semantic"].get("display")
                    for member in member_rows
                )
                selected_members.append(
                    {
                        "prepared_name_id": row["id"],
                        "album_id": album.id,
                        "slot": "selected_event",
                        "event_id": event_id,
                        "selection_id": album.id,
                        "semantic": {"selected_search": allowed, "raw_value": raw, "display": display},
                    }
                )
    _upsert(conn, m.members, selected_members, ("prepared_name_id", "album_id", "slot"))
    budget.check(album_ids)
    return len(albums)


def _expand_targets(conn, db, dirty):
    from katrain.web.kifu.prepared_migration import INPUT_TABLES

    owners = {kind: set() for kind in _SPECS}
    albums, inputs, tokens, raw_scopes = set(), set(), set(), set()
    for change in dirty:
        table, row_key = change["input_kind"], change["input_key"]
        if table in INPUT_TABLES and row_key == "*":
            raise PreparationError("collection invalidation requires an explicit full prepare: " + table)
        if table not in INPUT_TABLES or not any(
            isinstance(change.get(field), dict) for field in ("old_values", "new_values")
        ):
            raise PreparationError("unresolved preparation input: " + table)
        inputs.add((table, str(row_key)))
        for value in (change.get("old_values"), change.get("new_values")):
            if not isinstance(value, dict):
                continue
            if table in _OWNER_TABLES:
                owners[_OWNER_TABLES[table]].add(value["id"])
            kind = _NAME_TABLES.get(table) or _ALIAS_TABLES.get(table) or value.get("name_kind")
            if kind in _SPECS:
                owner_id = value.get(_SPECS[kind][2])
                if owner_id is not None:
                    owners[kind].add(owner_id)
                display = value.get("display_name", value.get("candidate_name", value.get("alias")))
                if isinstance(display, str):
                    tokens.add((kind, value.get("lang", "*"), identity.normalize_alias(display)))
                if isinstance(value.get("raw_value"), str):
                    raw_scopes.add((kind, value["raw_value"]))
            # Album FKs are display inputs, not an instruction to reprove every
            # historical game of those canonical owners. Source owner/name rows
            # and actual reverse dependencies above select proof targets.
            for kind, fields in (
                ("raw_player", ("player_black", "player_white")),
                ("raw_event", ("event", "selected_raw")),
            ):
                raw_scopes.update((kind, value[field]) for field in fields if isinstance(value.get(field), str))
            if table == business.KifuAlbum.__tablename__:
                albums.add(value["id"])
            if type(value.get("album_id")) is int:
                albums.add(value["album_id"])
                inputs.add(("album_sources", str(value["album_id"])))
            if table == business.KifuNameChange.__tablename__:
                inputs.add((business.KifuNameBatch.__tablename__, str(value["batch_id"])))
                inputs.add((value["target_table"], str(value["target_row_id"])))
                if value["target_table"] in {
                    business.KifuAlbum.__tablename__,
                    business.KifuAlbumEventSelection.__tablename__,
                }:
                    albums.add(value["target_row_id"])
        if table == business.KifuAlbum.__tablename__:
            albums.add(int(row_key))
        elif table == business.KifuAlbumEventSelection.__tablename__:
            albums.add(int(row_key))
    for kind, lang, token in tokens:
        inputs.add(("token", _key(kind, lang, token)))
        # Include negative verified names, not only currently public rows.
        for row in conn.execute(
            select(m.names.c.owner_id).where(
                m.names.c.name_kind == kind, m.names.c.lang == lang, m.names.c.normalized_term == token
            )
        ):
            if row.owner_id is not None:
                owners[kind].add(row.owner_id)
    for kind, raw in raw_scopes:
        inputs.add(("raw_scope", _key(kind, raw)))
        model = _SPECS[kind][0]
        owners[kind].update(row_id for row_id, in db.query(model.id).filter(model.raw_value == raw))
    # Reverse dependencies can add a source-dependent name, which can in turn
    # affect other proof families. Iterate the finite row/owner graph to closure.
    seen_inputs = set()
    while inputs - seen_inputs:
        pending = inputs - seen_inputs
        seen_inputs |= pending
        for chunk in _chunks(pending, 150):
            clauses = [
                and_(m.dependencies.c.input_kind == kind, m.dependencies.c.input_key.in_((str(key), "*")))
                for kind, key in chunk
            ]
            for target_kind, target_key in conn.execute(
                select(m.dependencies.c.target_kind, m.dependencies.c.target_key).where(or_(*clauses)).distinct()
            ):
                if target_kind in {"display", "selection"}:
                    albums.add(int(target_key))
                elif target_kind == "name":
                    row = conn.execute(select(m.names).where(m.names.c.id == int(target_key))).mappings().first()
                    if row and row["name_kind"] in owners and row["owner_id"] is not None:
                        owners[row["name_kind"]].add(row["owner_id"])
        for kind, ids in owners.items():
            for owner_id in ids:
                inputs.add(("owner", _key(kind, owner_id)))
            if ids:
                for row in conn.execute(
                    select(m.names).where(m.names.c.name_kind == kind, m.names.c.owner_id.in_(ids))
                ).mappings():
                    if row["source_name_id"] is not None:
                        inputs.add((_SPECS[kind][1].__tablename__, str(row["source_name_id"])))
                    if row["semantic"].get("raw_value") is not None:
                        inputs.add(("raw_scope", _key(kind, row["semantic"]["raw_value"])))
                    inputs.add(("token", _key(kind, row["lang"], row["normalized_term"])))
    for kind, ids in owners.items():
        if not ids:
            continue
        if kind == "player":
            condition = or_(business.KifuAlbum.black_player_id.in_(ids), business.KifuAlbum.white_player_id.in_(ids))
        elif kind == "event":
            condition = or_(
                business.KifuAlbum.event_id.in_(ids),
                business.KifuAlbum.id.in_(
                    select(business.KifuAlbumEventSelection.album_id).where(
                        business.KifuAlbumEventSelection.event_id.in_(ids)
                    )
                ),
            )
        else:
            model = _SPECS[kind][0]
            raws = {raw for chunk in _chunks(ids) for raw, in db.query(model.raw_value).filter(model.id.in_(chunk))}
            raws |= {raw for raw_kind, raw in raw_scopes if raw_kind == kind}
            if kind == "raw_player":
                condition = or_(business.KifuAlbum.player_black.in_(raws), business.KifuAlbum.player_white.in_(raws))
            else:
                condition = or_(
                    business.KifuAlbum.event.in_(raws),
                    business.KifuAlbum.id.in_(
                        select(business.KifuAlbumEventSelection.album_id).where(
                            business.KifuAlbumEventSelection.selected_raw.in_(raws)
                        )
                    ),
                )
        albums.update(album_id for album_id, in db.query(business.KifuAlbum.id).filter(condition))
    return owners, albums


def _assert_coverage(conn):
    if conn.execute(
        select(m.names.c.id).where(or_(~m.names.c.valid, m.names.c.policy_version != m.POLICY_VERSION)).limit(1)
    ).first():
        raise PreparationError("unresolved invalid name")
    missing = (
        select(business.KifuAlbum.id)
        .outerjoin(
            m.displays,
            and_(
                m.displays.c.album_id == business.KifuAlbum.id,
                m.displays.c.valid,
                m.displays.c.policy_version == m.POLICY_VERSION,
            ),
        )
        .group_by(business.KifuAlbum.id)
        .having(func.count(m.displays.c.name_lang) != len(m.NAME_LANGUAGES))
        .limit(1)
    )
    if conn.execute(missing).first():
        raise PreparationError("incomplete five-language album coverage")
    for kind, (_owner, model, owner_column, alias_model) in _SPECS.items():
        source = model.__table__
        match = and_(
            m.names.c.name_kind == kind,
            m.names.c.match_class == "approved_exact",
            m.names.c.source_name_id == source.c.id,
            m.names.c.source_key == cast(source.c.id, String),
            m.names.c.lang == source.c.lang,
            m.names.c.owner_id == source.c[owner_column],
            m.names.c.display_name == source.c.display_name,
            m.names.c.valid,
            m.names.c.policy_version == m.POLICY_VERSION,
        )
        if conn.execute(select(source.c.id).outerjoin(m.names, match).where(m.names.c.id.is_(None)).limit(1)).first():
            raise PreparationError("unprepared source name: " + kind)
        if alias_model is not None:
            source = alias_model.__table__
            match = and_(
                m.names.c.name_kind == kind,
                m.names.c.match_class == "legacy_alias",
                m.names.c.source_key == literal("alias:") + cast(source.c.id, String),
                m.names.c.owner_id == source.c[owner_column],
                m.names.c.lang == "*",
                m.names.c.valid,
                m.names.c.policy_version == m.POLICY_VERSION,
            )
            if conn.execute(
                select(source.c.id).outerjoin(m.names, match).where(m.names.c.id.is_(None)).limit(1)
            ).first():
                raise PreparationError("unprepared source alias: " + kind)


def verify_coverage(conn):
    """Read-only publication/enable gate; does not repair or change readiness."""
    value = read_state(conn)
    if value is None:
        raise PreparationError("explicit prepared-search migration is required")
    if (
        value["policy_version"] != m.POLICY_VERSION
        or value["policy_signature"] != current_policy_signature()
        or not value["initial_coverage_complete"]
    ):
        raise PreparationError("incomplete preparation policy or coverage")
    if conn.execute(select(m.dirty.c.input_key).limit(1)).first():
        raise PreparationError("unresolved dirty preparation inputs")
    _assert_coverage(conn)
    if conn.execute(
        select(m.members.c.album_id)
        .outerjoin(business.KifuAlbum, business.KifuAlbum.id == m.members.c.album_id)
        .outerjoin(m.names, m.names.c.id == m.members.c.prepared_name_id)
        .where(
            or_(
                business.KifuAlbum.id.is_(None),
                m.names.c.id.is_(None),
                ~m.names.c.valid,
                m.names.c.policy_version != m.POLICY_VERSION,
            )
        )
        .limit(1)
    ).first():
        raise PreparationError("unresolved finite membership")
    return {
        "albums": conn.scalar(select(func.count()).select_from(business.KifuAlbum)),
        "names": conn.scalar(select(func.count()).select_from(m.names)),
        "displays": conn.scalar(select(func.count()).select_from(m.displays)),
        "members": conn.scalar(select(func.count()).select_from(m.members)),
        "ready": bool(value["ready"]),
        "policy_version": m.POLICY_VERSION,
    }


def prepare_changed(conn, dirty_keys=None, *, policy_version=m.POLICY_VERSION, budget=None):
    """Consume a complete finite dirty closure without committing the caller."""
    value = read_state(conn)
    if value is None:
        return {"installed": False, "ready": False, "names": 0, "albums": 0}
    value = conn.execute(select(m.state).where(m.state.c.id == 1).with_for_update()).mappings().one()
    if (
        policy_version != m.POLICY_VERSION
        or value["policy_version"] != policy_version
        or value["policy_signature"] != current_policy_signature()
    ):
        raise PreparationError("policy changed; an explicit full prepare is required")
    if not value["initial_coverage_complete"]:
        return {"installed": True, "ready": False, "deferred": True, "names": 0, "albums": 0}
    dirty = list(conn.execute(select(m.dirty)).mappings())
    if dirty_keys is not None:
        requested = {
            (row["input_kind"], row["input_key"]) if isinstance(row, dict) else tuple(row) for row in dirty_keys
        }
        dirty = [row for row in dirty if (row["input_kind"], row["input_key"]) in requested]
    limit = _Budget(budget, conn)
    with Session(bind=conn, expire_on_commit=False) as db:
        owners, albums = _expand_targets(conn, db, dirty)
        limit.check()
        count = sum(
            _prepare_owners(conn, db, {kind: set(chunk)}, limit)
            for kind, ids in owners.items()
            for chunk in _chunks(ids, limit.value.max_albums)
        )
        album_count = sum(
            _prepare_displays(conn, db, set(chunk), limit) for chunk in _chunks(albums, limit.value.max_albums)
        )
        _refresh_generic_overrides(conn, db, albums)
    for row in dirty:
        conn.execute(
            delete(m.dirty).where(m.dirty.c.input_kind == row["input_kind"], m.dirty.c.input_key == row["input_key"])
        )
    remaining = conn.execute(select(m.dirty.c.input_key).limit(1)).first() is not None
    if not remaining:
        _assert_coverage(conn)
    conn.execute(
        m.state.update()
        .where(m.state.c.id == 1)
        .values(
            ready=not remaining, prepared_at=datetime.now(timezone.utc), phase="complete" if not remaining else "dirty"
        )
    )
    return {"installed": True, "ready": not remaining, "names": count, "albums": album_count}


def maintain_after_write(conn, *, budget=None):
    """Normal writer hook; pre-coverage installations leave work for the CLI."""
    value = read_state(conn)
    if value is None:
        result = {"installed": False, "ready": False, "names": 0, "albums": 0}
    elif not value["initial_coverage_complete"]:
        result = {"installed": True, "ready": False, "deferred": True, "names": 0, "albums": 0}
    else:
        result = prepare_changed(conn, budget=budget)
    logging.getLogger(__name__).info(
        "kifu_search_writer_prepare %s",
        json.dumps(
            {
                "policy_signature": current_policy_signature(),
                "policy_version": m.POLICY_VERSION,
                "build_sha": os.getenv("KATRAIN_BUILD_SHA", "unknown"),
                **result,
            },
            separators=(",", ":"),
        ),
    )
    return result


def emergency_undo_status(conn):
    """Report an explicitly requested undo's guarded invalid state, without proof."""
    value = read_state(conn)
    if value is None:
        result = {"search_prepared_installed": False, "search_ready": False, "search_repair_required": False}
    else:
        dirty = conn.execute(select(m.dirty.c.input_key).limit(1)).first() is not None
        if dirty:
            conn.execute(m.state.update().where(m.state.c.id == 1).values(ready=False))
        ready = bool(value["ready"] and value["initial_coverage_complete"] and not dirty)
        result = {"search_prepared_installed": True, "search_ready": ready, "search_repair_required": not ready}
    logging.getLogger(__name__).info(
        "kifu_search_emergency_undo %s",
        json.dumps(
            {
                "policy_signature": current_policy_signature(),
                "build_sha": os.getenv("KATRAIN_BUILD_SHA", "unknown"),
                **result,
            },
            separators=(",", ":"),
        ),
    )
    return result


def _prepare_generic(conn, db):
    from katrain.web.kifu.first_pass_cn import _hints, _display_event_candidate, valid_override_search_ids
    from katrain.web.kifu.library_search import HISTORICAL_PLAYER_ALIASES

    values = []
    for display, terms in HISTORICAL_PLAYER_ALIASES.items():
        values.append(("historical_player", display, display, {"terms": list(terms)}))
    players, events, overrides = _hints()
    for raw, display in players.items():
        values.append(("provisional_player", _key(raw), display, {"raw_value": raw}))
    for (raw, canonical), display in events.items():
        if raw and not any("\u3400" <= char <= "\u9fff" for char in raw):
            values.append(
                (
                    "provisional_event",
                    _key(raw, canonical),
                    _display_event_candidate(raw, display),
                    {"raw_value": raw, "canonical_name": canonical},
                )
            )
    approved_ids = valid_override_search_ids(db, set(overrides))
    for album_id in approved_ids:
        values.append(("provisional_album", str(album_id), overrides[album_id][2], {"album_id": album_id}))
    conn.execute(delete(m.names).where(m.names.c.match_class == "generic"))
    rows = [
        {
            "name_kind": kind,
            "source_key": key,
            "source_name_id": None,
            "lang": "cn",
            "display_name": display,
            "normalized_term": identity.normalize_alias(display),
            "match_class": "generic",
            "owner_id": None,
            "eligible": True,
            "exact_group_authorized_ids": [],
            "semantic": semantic,
            "valid": True,
            "policy_version": m.POLICY_VERSION,
        }
        for kind, key, display, semantic in values
    ]
    _upsert(conn, m.names, rows, ("name_kind", "source_key", "lang", "match_class"))


def _refresh_generic_overrides(conn, db, album_ids):
    from katrain.web.kifu.first_pass_cn import _hints, valid_override_search_ids

    overrides = _hints()[2]
    affected = set(album_ids) & overrides.keys()
    if not affected:
        return
    conn.execute(
        delete(m.names).where(
            m.names.c.name_kind == "provisional_album",
            m.names.c.source_key.in_([str(album_id) for album_id in affected]),
        )
    )
    values = []
    for album_id in valid_override_search_ids(db, affected):
        display = overrides[album_id][2]
        values.append(
            {
                "name_kind": "provisional_album",
                "source_key": str(album_id),
                "source_name_id": None,
                "lang": "cn",
                "display_name": display,
                "normalized_term": identity.normalize_alias(display),
                "match_class": "generic",
                "owner_id": None,
                "eligible": True,
                "exact_group_authorized_ids": [],
                "semantic": {"album_id": album_id},
                "valid": True,
                "policy_version": m.POLICY_VERSION,
            }
        )
    _upsert(conn, m.names, values, ("name_kind", "source_key", "lang", "match_class"))


def begin_full_prepare(conn):
    """Transfer existing collection dirtiness into a durable full-scan obligation.

    The operator must disable search first. New dirtiness recorded after this
    checkpoint remains queued; a later TRUNCATE therefore cannot be consumed by
    an older scan. The caller owns the same writer lock and transaction as the
    first initial batch.
    """
    if read_state(conn) is None:
        raise PreparationError("explicit prepared-search migration is required")
    value = conn.execute(select(m.state).where(m.state.c.id == 1).with_for_update()).mappings().one()
    if value["enabled"]:
        raise PreparationError("disable prepared search before a full prepare")
    from katrain.web.kifu.prepared_migration import INPUT_TABLES

    if conn.execute(
        select(m.dirty.c.input_kind)
        .where(m.dirty.c.input_key == "*", m.dirty.c.input_kind.not_in(INPUT_TABLES))
        .limit(1)
    ).first():
        raise PreparationError("unresolved unknown collection input")
    consumed = conn.execute(select(func.count()).select_from(m.dirty).where(m.dirty.c.input_key == "*")).scalar_one()
    conn.execute(
        m.state.update()
        .where(m.state.c.id == 1)
        .values(ready=False, initial_coverage_complete=False, phase="unprepared", cursor=None)
    )
    conn.execute(delete(m.dirty).where(m.dirty.c.input_key == "*"))
    return {"ready": False, "phase": "unprepared", "consumed_collections": consumed}


def prepare_initial_batch(conn, *, batch_size=500, budget=None):
    """Advance a bounded, resumable names-then-displays checkpoint."""
    if not isinstance(batch_size, int) or batch_size < 1 or batch_size > 500:
        raise PreparationError("initial batch size must be between 1 and 500")
    value = read_state(conn)
    if value is None:
        raise PreparationError("explicit prepared-search migration is required")
    value = conn.execute(select(m.state).where(m.state.c.id == 1).with_for_update()).mappings().one()
    signature = current_policy_signature()
    if value["phase"] == "unprepared" or value["policy_signature"] != signature:
        for table in (m.members, m.dependencies, m.displays, m.names):
            conn.execute(delete(table))
        conn.execute(
            m.state.update()
            .where(m.state.c.id == 1)
            .values(
                policy_version=m.POLICY_VERSION,
                policy_signature=signature,
                ready=False,
                initial_coverage_complete=False,
                phase="names",
                cursor={"kind": 0, "owner": 0},
            )
        )
        value = dict(value, phase="names", cursor={"kind": 0, "owner": 0}, initial_coverage_complete=False)
    limit = _Budget(budget, conn)
    if value["initial_coverage_complete"]:
        return prepare_changed(conn, budget=budget)
    with Session(bind=conn, expire_on_commit=False) as db:
        if value["phase"] == "names":
            cursor = value["cursor"] or {"kind": 0, "owner": 0}
            kind = tuple(_SPECS)[cursor["kind"]]
            owner, name, owner_column, alias = _SPECS[kind]
            sources = [select(owner.id.label("owner_id")), select(getattr(name, owner_column).label("owner_id"))]
            if alias is not None:
                sources.append(select(getattr(alias, owner_column).label("owner_id")))
            all_owners = sources[0].union(*sources[1:]).subquery()
            ids = [
                row_id
                for row_id, in db.query(all_owners.c.owner_id)
                .filter(all_owners.c.owner_id > cursor["owner"])
                .order_by(all_owners.c.owner_id)
                .limit(batch_size)
            ]
            count = _prepare_owners(conn, db, {kind: set(ids)}, limit)
            if len(ids) == batch_size:
                cursor = {"kind": cursor["kind"], "owner": ids[-1]}
                phase = "names"
            elif cursor["kind"] + 1 < len(_SPECS):
                cursor = {"kind": cursor["kind"] + 1, "owner": 0}
                phase = "names"
            else:
                _prepare_generic(conn, db)
                cursor, phase = {"album": 0}, "displays"
            conn.execute(m.state.update().where(m.state.c.id == 1).values(phase=phase, cursor=cursor))
            return {"ready": False, "phase": phase, "cursor": cursor, "names": count, "albums": 0}
        cursor = value["cursor"] or {"album": 0}
        ids = [
            row_id
            for row_id, in db.query(business.KifuAlbum.id)
            .filter(business.KifuAlbum.id > cursor["album"])
            .order_by(business.KifuAlbum.id)
            .limit(batch_size)
        ]
        count = _prepare_displays(conn, db, set(ids), limit, refresh_invalid_names=True)
        conn.execute(
            m.state.update().where(m.state.c.id == 1).values(cursor={"album": ids[-1] if ids else cursor["album"]})
        )
        if len(ids) == batch_size:
            return {"ready": False, "phase": "displays", "names": 0, "albums": count}
    # Every current album has now been covered. Reconcile writes made during an
    # earlier checkpoint before this transaction is allowed to mark ready.
    conn.execute(m.state.update().where(m.state.c.id == 1).values(initial_coverage_complete=True))
    result = prepare_changed(conn, budget=budget)
    result["albums"] += count
    return result


def prepare_all(conn, *, budget=None):
    """Small-catalog convenience; the CLI commits each initial batch instead."""
    while True:
        result = prepare_initial_batch(conn, budget=budget)
        if result["ready"]:
            return result
