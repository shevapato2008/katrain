"""Small prepared-read contracts. This module never performs name proof or DDL."""

import hashlib
import json
from functools import lru_cache
from pathlib import Path

from sqlalchemy import and_, false, func, or_, select, text

from katrain.web.core.models_db import KifuAlbum, KifuAlbumEventSelection, KifuEvent
from katrain.web.kifu import prepared_models as m
from katrain.web.kifu.identity import normalize_alias
from katrain.web.kifu.name_first_pass import VERSION as FIRST_PASS_VERSION


class PreparedSearchNotReady(RuntimeError):
    code = "kifu_search_not_ready"

    def __init__(self, reason="unprepared"):
        self.reason = reason
        super().__init__(self.code + ": " + reason)


@lru_cache(maxsize=1)
def _static_policy_digest():
    root = Path(__file__).parent
    digest = hashlib.sha256()
    # One process-wide digest of local policy code/static hints, never DB proof.
    # Include new policy modules automatically; do not recurse into artifact trees.
    for path in sorted([*root.glob("*.py"), *root.joinpath("data").glob("*")]):
        if path.is_file():
            digest.update(path.name.encode())
            digest.update(path.read_bytes())
    return digest.hexdigest()


def current_policy_signature():
    from katrain.web.kifu.identity import strict_names_enabled

    payload = [m.POLICY_VERSION, strict_names_enabled(), m.NAME_LANGUAGES, "other-locales=en", _static_policy_digest()]
    return hashlib.sha256(json.dumps(payload, separators=(",", ":")).encode()).hexdigest()


def read_state(db):
    # An installation that has never explicitly migrated remains on the legacy path.
    dialect = db.bind.dialect.name if hasattr(db, "bind") else db.dialect.name
    if dialect == "postgresql":
        exists = db.execute(text("SELECT to_regclass('kifu_search_prepared_state') IS NOT NULL")).scalar_one()
    else:
        exists = db.execute(
            text("SELECT 1 FROM sqlite_master WHERE type='table' AND name='kifu_search_prepared_state'")
        ).first()
    if not exists:
        return None
    value = db.execute(select(m.state).where(m.state.c.id == 1)).mappings().first()
    if value is None:
        raise PreparedSearchNotReady("missing_state")
    return value


def require_ready(db, *, expected_policy_version=m.POLICY_VERSION):
    value = read_state(db)
    if value is None or not value["enabled"]:
        return None
    if not value["ready"] or not value["initial_coverage_complete"]:
        raise PreparedSearchNotReady("incomplete_coverage")
    if value["policy_version"] != expected_policy_version or value["policy_signature"] != current_policy_signature():
        raise PreparedSearchNotReady("policy_mismatch")
    if db.execute(select(m.dirty.c.input_key).limit(1)).first() is not None:
        raise PreparedSearchNotReady("dirty")
    return value


def begin_read_snapshot(db):
    """Set PostgreSQL options before the fresh reader Session issues any SQL.

    Explicit legacy comparison helpers can share a caller-owned transaction. The
    HTTP workers always construct a fresh Session, so the options apply before
    its first query and cover state, candidates, count, page and current metadata.
    """
    if db.get_bind().dialect.name == "postgresql" and not db.in_transaction():
        db.connection(execution_options={"isolation_level": "REPEATABLE READ", "postgresql_readonly": True})


def _checked_names(rows):
    for row in rows:
        if not row["valid"] or row["policy_version"] != m.POLICY_VERSION or not isinstance(row["semantic"], dict):
            raise PreparedSearchNotReady("invalid_name")
    return rows


def read_displays(db, album_ids, lang):
    """Read only this page's already resolved names and source keys."""
    if not album_ids:
        return {}
    rows = (
        db.execute(select(m.displays).where(m.displays.c.album_id.in_(album_ids), m.displays.c.name_lang == lang))
        .mappings()
        .all()
    )
    result = {}
    for row in rows:
        outputs = row["strict_outputs"]
        if (
            not row["valid"]
            or row["policy_version"] != m.POLICY_VERSION
            or not isinstance(row["player_black"], str)
            or not isinstance(row["player_white"], str)
            or row["event"] is not None
            and not isinstance(row["event"], str)
            or not isinstance(outputs, dict)
            or not isinstance(outputs.get("sources"), list)
            or not all(isinstance(value, str) for value in outputs["sources"])
        ):
            raise PreparedSearchNotReady("invalid_display")
        result[row["album_id"]] = row
    if set(result) != set(album_ids):
        raise PreparedSearchNotReady("missing_display")
    return result


def _exact_rows(db, query):
    return _checked_names(
        db.execute(
            select(m.names).where(
                m.names.c.match_class == "approved_exact",
                or_(m.names.c.display_name == query, func.lower(m.names.c.display_name) == query.lower()),
            )
        )
        .mappings()
        .all()
    )


def _alias_ids(db, query, *, exact, exact_rows=()):
    needle = normalize_alias(query)
    if not needle:
        return set(), set()
    term = m.names.c.normalized_term
    rows = _checked_names(
        db.execute(
            select(m.names).where(
                m.names.c.match_class == "legacy_alias",
                term == needle if exact else term.contains(needle, autoescape=True),
            )
        )
        .mappings()
        .all()
    )
    players = {row["owner_id"] for row in rows if row["eligible"] and row["name_kind"] == "player"}
    events = {row["owner_id"] for row in rows if row["eligible"] and row["name_kind"] == "event"}
    if exact:
        players.update(
            row["owner_id"]
            for row in exact_rows
            if row["eligible"]
            and row["name_kind"] == "player"
            and row["lang"] == "tw"
            and row["display_name"] == query
            and row["normalized_term"] == needle
            and row["semantic"].get("decision_kind") == "generated"
            and row["semantic"].get("generation_rule_version") == "primary-orthographic-v1"
        )
    return players, events


def _matching_names(rows, query):
    """Apply the old exact SQL candidates' normalization and group decisions."""
    needle = normalize_alias(query)
    matches = [row for row in rows if row["eligible"] and row["normalized_term"] == needle]
    players = {row["owner_id"] for row in matches if row["name_kind"] == "player"}
    events = {row["owner_id"] for row in matches if row["name_kind"] == "event"}
    raw_players = [row for row in matches if row["name_kind"] == "raw_player"]
    raw_events = [row for row in matches if row["name_kind"] == "raw_event"]
    player_raws = {row["semantic"]["raw_value"] for row in raw_players}
    event_raws = {row["semantic"]["raw_value"] for row in raw_events}
    shared = bool(
        len(players) > 1
        and not events
        and not event_raws
        and any(set(row["exact_group_authorized_ids"]) == players for row in matches if row["name_kind"] == "player")
    )
    raw_titles = (
        not players
        and not events
        and not player_raws
        and len(event_raws) > 1
        and all(row["semantic"].get("decision_kind") == "translated" for row in raw_events)
    )
    linked_formal = (
        not players
        and len(events) == 1
        and not player_raws
        and bool(raw_events)
        and all(
            row["semantic"].get("decision_kind") == "translated"
            and row["semantic"].get("raw_type") == "linked_literal"
            and row["semantic"].get("frozen_member_count", 0) > 0
            and not row["semantic"].get("linked_unlinked", False)
            and set(row["semantic"].get("linked_event_ids", ())) <= events
            for row in raw_events
        )
    )
    raw_player_group = (
        bool(player_raws)
        and (len(players) <= 1 or shared)
        and not events
        and not event_raws
        and all(
            row["semantic"].get("generation_rule_version") == FIRST_PASS_VERSION
            and row["semantic"].get("raw_type") == "finite_player"
            and row["semantic"].get("frozen_member_count", 0) > 0
            for row in raw_players
        )
    )
    raw_event_group = (
        bool(raw_events)
        and not players
        and len(events) <= 1
        and not player_raws
        and all(
            row["semantic"].get("raw_type") in {"first_pass", "linked_literal"}
            and not row["semantic"].get("record_label")
            and row["semantic"].get("frozen_member_count", 0) > 0
            for row in raw_events
        )
    )
    if len(players) + len(events) + len(player_raws) + len(event_raws) != 1 and not any(
        (raw_titles, linked_formal, raw_player_group, raw_event_group, shared and (not player_raws or raw_player_group))
    ):
        return set(), set(), set(), []
    return players, events, player_raws, raw_events


def _selected_event_ids(db, query, raw_names, event_ids):
    raw_name_ids = {row["source_name_id"] for row in raw_names}
    raw_aliases = {
        row["semantic"]["raw_value"] for row in raw_names if row["semantic"].get("decision_kind") != "translated"
    }
    # Preserve the database's literal contains semantics, including its case
    # behavior. Rejected physical selections affect this candidate stage too.
    clauses = [KifuAlbumEventSelection.selected_raw.contains(query, autoescape=True)]
    if raw_aliases:
        clauses.append(KifuAlbumEventSelection.selected_raw.in_(raw_aliases))
    if event_ids:
        clauses.append(KifuAlbumEventSelection.event_id.in_(event_ids))
    selected_raws = select(KifuAlbumEventSelection.selected_raw).where(or_(*clauses)).distinct()
    rows = _checked_names(
        db.execute(
            select(
                m.names,
                m.members.c.album_id,
                m.members.c.event_id,
                m.members.c.semantic.label("member_semantic"),
            )
            .join(m.members, m.members.c.prepared_name_id == m.names.c.id)
            .where(
                m.names.c.match_class == "approved_exact",
                m.names.c.eligible.is_(True),
                m.members.c.slot == "selected_event",
                m.members.c.semantic["raw_value"].as_string().in_(selected_raws),
            )
        )
        .mappings()
        .all()
    )
    result = set()
    for row in rows:
        member = row["member_semantic"]
        if not isinstance(member, dict) or not isinstance(member.get("raw_value"), str):
            raise PreparedSearchNotReady("invalid_selection")
        raw = member["raw_value"]
        if row["name_kind"] == "event" and row["event_id"] in event_ids and member.get("identity_search"):
            result.add(row["album_id"])
        elif (
            row["name_kind"] == "raw_event"
            and member.get("selected_search")
            and (query.lower() in raw.lower() or row["source_name_id"] in raw_name_ids)
        ):
            result.add(row["album_id"])
    return result


def _member_clause(name_ids, slots):
    return KifuAlbum.id.in_(
        select(m.members.c.album_id).where(
            m.members.c.prepared_name_id.in_(name_ids),
            m.members.c.slot.in_(slots),
            m.members.c.semantic["search"].as_boolean().is_(True),
        )
    )


def _raw_player_clause(rows, raw_values):
    clauses, finite_ids = [], []
    for row in rows:
        semantic = row["semantic"]
        raw = semantic.get("raw_value")
        if not row["eligible"] or row["name_kind"] != "raw_player" or raw not in raw_values:
            continue
        if semantic.get("raw_type") == "finite_player":
            finite_ids.append(row["id"])
        else:
            clauses.extend(
                (
                    (KifuAlbum.player_black == raw) & KifuAlbum.black_player_id.is_(None),
                    (KifuAlbum.player_white == raw) & KifuAlbum.white_player_id.is_(None),
                )
            )
    if finite_ids:
        clauses.append(_member_clause(finite_ids, ("black", "white")))
    return or_(*clauses) if clauses else false()


def _raw_event_clause(rows):
    clauses, finite_ids = [], []
    for row in rows:
        semantic, raw = row["semantic"], row["semantic"]["raw_value"]
        if semantic.get("raw_type") == "unrestricted":
            clauses.append(KifuAlbum.event == raw)
        elif semantic.get("raw_type") == "translated":
            clauses.append(
                (KifuAlbum.event == raw)
                & KifuAlbum.event_id.is_(None)
                & ~KifuAlbum.id.in_(select(KifuAlbumEventSelection.album_id))
            )
        else:
            finite_ids.append(row["id"])
    if finite_ids:
        clauses.append(_member_clause(finite_ids, ("event",)))
    return or_(*clauses) if clauses else false()


def _generic_rows(db, query):
    rows = _checked_names(
        db.execute(
            select(m.names).where(
                m.names.c.match_class == "generic",
                or_(
                    and_(
                        m.names.c.name_kind == "historical_player",
                        m.names.c.display_name == query.removeprefix("本因坊"),
                    ),
                    and_(m.names.c.name_kind != "historical_player", m.names.c.display_name == query),
                    and_(
                        m.names.c.name_kind == "provisional_event",
                        len(query) >= 3,
                        m.names.c.display_name.contains(query, autoescape=True),
                    ),
                ),
            )
        )
        .mappings()
        .all()
    )
    # Discovery uses SQL, while the original provisional-event hint match is a
    # Python substring test (case sensitive even on SQLite's default LIKE).
    return [
        row
        for row in rows
        if row["eligible"]
        and (
            row["name_kind"] != "provisional_event"
            or row["display_name"] == query
            or len(query) >= 3
            and query in row["display_name"]
        )
    ]


def search_filter(db, *, query=None, player_id=None, lang="cn", strict=True):
    """Return one shared count/page predicate and optional player-first priority."""
    if player_id is not None:
        rows = _checked_names(
            db.execute(
                select(m.names).where(
                    m.names.c.name_kind == "player",
                    m.names.c.match_class == "approved_exact",
                    m.names.c.owner_id == player_id,
                )
            )
            .mappings()
            .all()
        )
        public = any(row["eligible"] and row["semantic"].get("public_primary") for row in rows)
        return (
            or_(KifuAlbum.black_player_id == player_id, KifuAlbum.white_player_id == player_id) if public else false()
        ), None
    if not query:
        return None, None
    rows = _exact_rows(db, query) if normalize_alias(query) else []
    players, events, raw_players, raw_events = _matching_names(rows, query)
    shared_players = set(players) if len(players) > 1 else set()
    selected = _selected_event_ids(db, query, raw_events, events)
    if not strict:
        legacy_players, legacy_events = _alias_ids(db, query, exact=True, exact_rows=rows)
        players |= legacy_players
        events |= legacy_events
    exact_raw_event = bool(raw_events) and not players and not events and not raw_players
    exact_player = len(players) == 1 and not events and not raw_players and not raw_events
    player_with_raw = len(players) == 1 and bool(raw_players) and not events and not raw_events and not selected
    player_only = (exact_player or player_with_raw) and not selected
    shared = bool(shared_players) and not events and not raw_events
    priority = None
    generic = _generic_rows(db, query) if not strict else []
    if exact_player:
        owner = next(iter(players))
        predicate = or_(KifuAlbum.black_player_id == owner, KifuAlbum.white_player_id == owner)
    elif player_with_raw:
        owner = next(iter(players))
        predicate = or_(
            KifuAlbum.black_player_id == owner,
            KifuAlbum.white_player_id == owner,
            _raw_player_clause(rows, raw_players),
        )
    elif shared:
        predicate = or_(KifuAlbum.black_player_id.in_(shared_players), KifuAlbum.white_player_id.in_(shared_players))
        if raw_players:
            predicate = or_(predicate, _raw_player_clause(rows, raw_players))
    elif len(events) == 1 and not players and not raw_players and not raw_events:
        predicate = KifuAlbum.event_id == next(iter(events))
    elif exact_raw_event:
        predicate = _raw_event_clause(raw_events)
    else:
        partial_players, partial_events = (set(), set()) if strict else _alias_ids(db, query, exact=False)
        terms = [query.lower()]
        terms.extend(
            term for row in generic if row["name_kind"] == "historical_player" for term in row["semantic"]["terms"]
        )
        priority = or_(
            *(
                func.lower(field).contains(term, autoescape=True)
                for field in (KifuAlbum.player_black, KifuAlbum.player_white)
                for term in terms
            )
        )
        clauses = [KifuAlbum.search_text.contains(query.lower(), autoescape=True), priority]
        if partial_players:
            clauses.extend(
                (KifuAlbum.black_player_id.in_(partial_players), KifuAlbum.white_player_id.in_(partial_players))
            )
        if partial_events:
            clauses.append(KifuAlbum.event_id.in_(partial_events))
        if strict or raw_players or raw_events:
            if players:
                clauses.extend((KifuAlbum.black_player_id.in_(players), KifuAlbum.white_player_id.in_(players)))
            if events:
                clauses.append(KifuAlbum.event_id.in_(events))
            if raw_players:
                clauses.append(_raw_player_clause(rows, raw_players))
            if raw_events:
                clauses.append(_raw_event_clause(raw_events))
        predicate = or_(*clauses)
    if selected and not shared:
        predicate = or_(predicate, KifuAlbum.id.in_(selected))
    if not strict and lang == "cn" and not exact_raw_event and not shared and not player_only:
        provisional_players = {
            row["semantic"]["raw_value"] for row in generic if row["name_kind"] == "provisional_player"
        }
        provisional_events = {
            (row["semantic"]["raw_value"], row["semantic"]["canonical_name"])
            for row in generic
            if row["name_kind"] == "provisional_event"
        }
        provisional_albums = {row["semantic"]["album_id"] for row in generic if row["name_kind"] == "provisional_album"}
        if provisional_players:
            predicate = or_(
                predicate,
                KifuAlbum.player_black.in_(provisional_players),
                KifuAlbum.player_white.in_(provisional_players),
            )
        if len(provisional_events) <= 200 and not exact_player:
            no_selection = ~KifuAlbum.id.in_(select(KifuAlbumEventSelection.album_id))
            unlinked = {raw for raw, canonical in provisional_events if canonical is None}
            if unlinked:
                predicate = or_(predicate, KifuAlbum.event_id.is_(None) & KifuAlbum.event.in_(unlinked) & no_selection)
            for canonical in {name for _, name in provisional_events if name is not None}:
                raws = {raw for raw, name in provisional_events if name == canonical}
                owners = select(KifuEvent.id).where(KifuEvent.canonical_name == canonical)
                predicate = or_(predicate, KifuAlbum.event.in_(raws) & KifuAlbum.event_id.in_(owners) & no_selection)
        if provisional_albums and not exact_player:
            predicate = or_(predicate, KifuAlbum.id.in_(provisional_albums))
    return predicate, priority
