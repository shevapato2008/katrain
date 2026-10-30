"""Same-snapshot name decisions and finite album projections for Elasticsearch.

The context qualifies names once. Album batches only check their actual slots,
current selected GN, sources and existing display rules. Nothing commits or
imports an HTTP endpoint, and no prepared relation is used.
"""

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from time import monotonic

from sqlalchemy import func, or_

from katrain.web.core.models_db import (
    KifuAlbum,
    KifuAlbumEventSelection,
    KifuAlbumSource,
    KifuEvent,
    KifuEventAlias,
    KifuEventName,
    KifuPlayer,
    KifuPlayerAlias,
    KifuPlayerName,
    KifuSource,
    KifuNameResearchEvidence,
    KifuRawPlayerValue,
    KifuRawPlayerName,
    KifuRawEventValue,
    KifuRawEventName,
)
from katrain.web.kifu import identity
from katrain.web.kifu.name_parse import parse_event, parse_player
from katrain.web.kifu.name_raw_player_scope import raw_player_scope_slot
from katrain.web.kifu.name_structure import structure_event
from katrain.web.kifu.round_names import display_round_name
from katrain.web.kifu.search_documents import (
    NAME_LANGUAGES,
    SCHEMA_VERSION,
    album_document_id,
    alias_document_id,
    document,
    public_player_document_id,
    term_document_id,
)
from katrain.web.kifu.search_terms import classify_qualified_names


_METADATA_FIELDS = tuple(
    column.name
    for column in KifuAlbum.__table__.columns
    if column.name not in {"sgf_content", "search_text", "source_path", "created_at"}
)


def _group(rows, key):
    grouped = defaultdict(list)
    for row in rows:
        grouped[key(row)].append(row)
    return dict(grouped)


_HINT_POLICY_CACHE = None


def _provisional_disabled_queries(events, checkpoint=None):
    """Preserve the original >200 raw-title expansion cap without album lists.

    Only frequent substrings need a negative policy record. Extending frequent
    prefixes avoids materializing every possible substring of the static asset.
    The cache contains immutable asset facts, never database qualification.
    """
    global _HINT_POLICY_CACHE
    if _HINT_POLICY_CACHE is not None and _HINT_POLICY_CACHE[0] is events:
        return _HINT_POLICY_CACHE[1]
    from katrain.web.kifu.first_pass_cn import _display_event_candidate

    weights = Counter(
        _display_event_candidate(raw, display)
        for (raw, _), display in events.items()
        if raw and not any("\u3400" <= char <= "\u9fff" for char in raw)
    )
    disabled = {display for display, count in weights.items() if count > 200}
    prefixes = None
    for width in range(3, max(map(len, weights), default=0) + 1):
        counts = Counter()
        for position, (display, count) in enumerate(weights.items()):
            if checkpoint is not None and position % 500 == 0:
                checkpoint()
            pieces = {
                display[offset : offset + width]
                for offset in range(len(display) - width + 1)
                if prefixes is None or display[offset : offset + width - 1] in prefixes
            }
            for piece in pieces:
                counts[piece] += count
        prefixes = {piece for piece, count in counts.items() if count > 200}
        disabled.update(prefixes)
        if not prefixes:
            break
    _HINT_POLICY_CACHE = (events, frozenset(disabled))
    return _HINT_POLICY_CACHE[1]


@dataclass
class ProjectionContext:
    db: object
    strict_mode: bool
    player_rows: list
    event_rows: list
    raw_player_rows: list
    raw_event_rows: list
    players: dict
    events: dict
    player_aliases: dict
    event_aliases: dict
    legacy_players: dict
    legacy_events: dict
    stats: dict
    _classification_docs: dict = field(default_factory=dict)

    def __post_init__(self):
        self.raw_players_by_value = _group(self.raw_player_rows, lambda row: row[1])
        self.raw_events_by_value = _group(self.raw_event_rows, lambda row: row[1])
        self.player_names = {(name.lang, name.player_id): name for name, _ in self.player_rows}
        self.event_names = {(name.lang, name.event_id): name for name, _ in self.event_rows}

    def classification_documents(self):
        return list(self._classification_docs.values())

    @property
    def term_document_ids(self):
        return {key for key in self._classification_docs if key.startswith("term:")}

    def classification_actions(self, owners=(), terms=()):
        """Replace affected keys and delete revoked names retained by the journal."""
        owner_refs = {f"{kind}:{owner_id}" for kind, owner_id in owners}
        keys = {
            key
            for key, value in self._classification_docs.items()
            if owner_refs.intersection(value["_source"].get("diagnostics", {}).get("owners", ()))
        }
        keys.update(key for term in terms for key in (term_document_id(term), alias_document_id(term)))
        keys.update(public_player_document_id(owner_id) for kind, owner_id in owners if kind == "player")
        return [
            (
                {"_op_type": "index", **self._classification_docs[key]}
                if key in self._classification_docs
                else {"_op_type": "delete", "_id": key}
            )
            for key in sorted(keys)
        ]


def _classification_documents(context, checkpoint=None):
    groups = {}
    self_terms = getattr(context, "classification_terms", None)
    for kind, rows in (
        ("player", context.player_rows),
        ("event", context.event_rows),
        ("raw_player", context.raw_player_rows),
        ("raw_event", context.raw_event_rows),
    ):
        for row in rows:
            name = row[0]
            if (
                not identity.normalize_alias(name.display_name)
                or self_terms is not None
                and name.display_name.lower() not in self_terms
            ):
                continue
            group = groups.setdefault(name.display_name.lower(), defaultdict(list))
            group[kind].append(row)
    docs = {}
    for position, (term, rows) in enumerate(groups.items()):
        if checkpoint is not None and position % 100 == 0:
            checkpoint()
        player_rows = rows["player"]
        shared = (
            identity._finite_shared_player_ids(context.db, player_rows, identity.normalize_alias(term))
            if len({name.player_id for name, _ in player_rows}) > 1 and not rows["event"] and not rows["raw_event"]
            else set()
        )
        classification = classify_qualified_names(
            player_rows,
            rows["event"],
            rows["raw_player"],
            rows["raw_event"],
            shared_player_ids=shared,
            strict=context.strict_mode,
        )
        if not context.strict_mode:
            # matching_entity_ids has one literal-only generated-TW supplement.
            # It must not inherit the aliases table's NFKC/casefold equivalence.
            spellings = defaultdict(set)
            for name, _ in player_rows:
                if (
                    name.lang == "tw"
                    and name.decision_kind == "generated"
                    and name.generation_rule_version == "primary-orthographic-v1"
                ):
                    spellings[name.display_name].add(name.player_id)
            if spellings:
                classification["legacy_player_spellings"] = {
                    spelling: sorted(ids) for spelling, ids in spellings.items()
                }
        refs = sorted({f"{kind}:{getattr(row[0], kind + '_id')}" for kind, values in rows.items() for row in values})
        key = term_document_id(term)
        docs[key] = document(
            key, {"doc_kind": "term", "term": term, "classification": classification, "diagnostics": {"owners": refs}}
        )
    aliases = defaultdict(lambda: {"player_ids": set(), "event_ids": set(), "owners": set()})
    if not context.strict_mode:
        for kind, values in (("player", context.player_aliases), ("event", context.event_aliases)):
            for owner_id, names in values.items():
                for name in names:
                    aliases[name][kind + "_ids"].add(owner_id)
                    aliases[name]["owners"].add(f"{kind}:{owner_id}")
    for term, value in aliases.items():
        key = alias_document_id(term)
        docs[key] = document(
            key,
            {
                "doc_kind": "term",
                "term": term,
                "classification": {
                    "strict": False,
                    "player_ids": sorted(value["player_ids"]),
                    "event_ids": sorted(value["event_ids"]),
                },
                "diagnostics": {"owners": sorted(value["owners"])},
            },
        )
    public_ids = {
        name.player_id
        for name, _ in context.player_rows
        if name.player_id in context.players
        and name.lang in identity.PRIMARY_NAME_LANGUAGES
        and name.decision_kind not in {"hidden", "error", "placeholder"}
        and name.display_name.strip()
    }
    if not context.strict_mode:
        from katrain.web.kifu.first_pass_cn import _hints

        for query in sorted(_provisional_disabled_queries(_hints()[1], checkpoint)):
            key = term_document_id(query)
            if key not in docs:
                docs[key] = document(
                    key,
                    {"doc_kind": "term", "term": query.lower(), "classification": {"strict": False, "mode": "generic"}},
                )
            docs[key]["_source"]["classification"].setdefault("provisional_event_disabled_queries", []).append(query)
    for player_id in context.players:
        key = public_player_document_id(player_id)
        docs[key] = document(
            key,
            {
                "doc_kind": "public_player",
                "player_id": player_id,
                "classification": {"public": player_id in public_ids, "strict": context.strict_mode},
                "diagnostics": {"owners": [f"player:{player_id}"]},
            },
        )
    return docs


def _finite_scope(db, records, owner_refs, terms):
    """The touched page, changed owners and exact-name collision set only."""
    owners = {kind: set() for kind in ("player", "event", "raw_player", "raw_event")}
    for kind, owner_id in owner_refs:
        if kind in owners:
            owners[kind].add(owner_id)
    owners["player"].update(
        value for album in records for value in (album.black_player_id, album.white_player_id) if value
    )
    owners["event"].update(album.event_id for album in records if album.event_id)
    raw_players = {value for album in records for value in (album.player_black, album.player_white)}
    raw_events = {album.event or "" for album in records}
    ids = {album.id for album in records}
    if ids:
        for raw, event_id in db.query(KifuAlbumEventSelection.selected_raw, KifuAlbumEventSelection.event_id).filter(
            KifuAlbumEventSelection.album_id.in_(ids)
        ):
            raw_events.add(raw)
            if event_id:
                owners["event"].add(event_id)
    for kind, model, values in (
        ("raw_player", KifuRawPlayerValue, raw_players),
        ("raw_event", KifuRawEventValue, raw_events),
    ):
        for owner_id, raw in db.query(model.id, model.raw_value).filter(
            or_(model.id.in_(owners[kind]), model.raw_value.in_(values))
        ):
            owners[kind].add(owner_id)
            values.add(raw)
    exact_terms = set(terms)
    for kind, model in (
        ("player", KifuPlayerName),
        ("event", KifuEventName),
        ("raw_player", KifuRawPlayerName),
        ("raw_event", KifuRawEventName),
    ):
        exact_terms.update(
            display
            for (display,) in db.query(model.display_name).filter(getattr(model, kind + "_id").in_(owners[kind]))
        )
    lower_terms = {term.lower() for term in exact_terms}
    # Each SQL exact/lower collision is qualified regardless of whether it is
    # on the touched page. An unrelated owner never triggers a proof read.
    for kind, model in (("raw_player", KifuRawPlayerName), ("raw_event", KifuRawEventName)):
        owners[kind].update(
            owner_id
            for (owner_id,) in db.query(getattr(model, kind + "_id")).filter(
                func.lower(model.display_name).in_(lower_terms)
            )
        )
    raw_players.update(
        raw for (raw,) in db.query(KifuRawPlayerValue.raw_value).filter(KifuRawPlayerValue.id.in_(owners["raw_player"]))
    )
    raw_events.update(
        raw for (raw,) in db.query(KifuRawEventValue.raw_value).filter(KifuRawEventValue.id.in_(owners["raw_event"]))
    )
    base_ids = set()
    if owners["raw_event"]:
        for (base_id,) in (
            db.query(KifuNameResearchEvidence.research_payload["composition"]["dependencies"]["base_name_id"])
            .join(KifuRawEventName, KifuRawEventName.evidence_id == KifuNameResearchEvidence.id)
            .filter(KifuRawEventName.raw_event_id.in_(owners["raw_event"]))
        ):
            if type(base_id) is int:
                base_ids.add(base_id)
    return owners, lower_terms, raw_players, raw_events, base_ids


def build_projection_context(db, strict_mode, *, records=None, owner_refs=None, terms=(), checkpoint=None):
    """Qualify names once; optional touched inputs bound incremental work."""
    started = monotonic()
    if checkpoint is not None:
        checkpoint()
    finite = records is not None or owner_refs is not None
    scope = _finite_scope(db, list(records or ()), owner_refs or (), terms) if finite else None
    batch_contexts = {}
    queries = []
    for kind, model in (("player", KifuPlayerName), ("event", KifuEventName)):
        query = identity._approved_names(db, model, kind + "_id")
        if scope is not None:
            owners, lower_terms, _, _, base_ids = scope
            query = query.filter(
                or_(
                    getattr(model, kind + "_id").in_(owners[kind]),
                    func.lower(model.display_name).in_(lower_terms),
                    model.id.in_(base_ids if kind == "event" else ()),
                )
            )
        queries.append(
            identity._qualified_name_rows(
                db, query, model, kind + "_id", orthographic_batch_contexts=batch_contexts, checkpoint=checkpoint
            )
        )
    player_rows, event_rows = queries
    raw_players = identity._approved_raw_player_names(
        db,
        orthographic_batch_contexts=batch_contexts,
        values=scope[2] if scope is not None else None,
        checkpoint=checkpoint,
    )
    raw_events = identity._approved_raw_event_names(
        db,
        orthographic_batch_contexts=batch_contexts,
        values=scope[3] if scope is not None else None,
        qualified_event_names={name.id: (name, evidence) for name, evidence in event_rows},
        checkpoint=checkpoint,
    )
    owner_ids = {
        "player": {name.player_id for name, _ in player_rows},
        "event": {name.event_id for name, _ in event_rows},
    }
    if scope is not None:
        for kind in owner_ids:
            owner_ids[kind].update(scope[0][kind])
    players_query = db.query(KifuPlayer.id, KifuPlayer.canonical_name)
    events_query = db.query(KifuEvent.id, KifuEvent.canonical_name)
    if finite:
        players_query = players_query.filter(KifuPlayer.id.in_(owner_ids["player"]))
        events_query = events_query.filter(KifuEvent.id.in_(owner_ids["event"]))
    players, events = dict(players_query), dict(events_query)
    aliases = []
    for kind, model in (("player", KifuPlayerAlias), ("event", KifuEventAlias)):
        grouped = defaultdict(set)
        if not strict_mode:
            query = db.query(getattr(model, kind + "_id"), model.normalized_alias)
            if finite:
                current_keys = {
                    alias
                    for (alias,) in db.query(model.normalized_alias).filter(
                        getattr(model, kind + "_id").in_(owner_ids[kind])
                    )
                }
                current_keys.update(identity.normalize_alias(term) for term in scope[1])
                query = query.filter(
                    or_(getattr(model, kind + "_id").in_(owner_ids[kind]), model.normalized_alias.in_(current_keys))
                )
            for owner_id, alias in query:
                grouped[owner_id].add(alias)
        aliases.append({key: sorted(value) for key, value in grouped.items()})
    legacy = []
    for kind, model in (("player", KifuPlayerName), ("event", KifuEventName)):
        query = db.query(model).filter(
            model.status == "verified",
            model.evidence_id.is_(None),
            model.decision_kind.is_(None),
            model.generation_rule_version.is_(None),
            model.revision.is_(None),
        )
        if finite:
            query = query.filter(getattr(model, kind + "_id").in_(owner_ids[kind]))
        legacy.append(
            {(getattr(name, kind + "_id"), name.lang): name.display_name for name in ([] if strict_mode else query)}
        )
    counts = {
        "player": len(player_rows),
        "event": len(event_rows),
        "raw_player": len(raw_players),
        "raw_event": len(raw_events),
    }
    context = ProjectionContext(
        db,
        bool(strict_mode),
        player_rows,
        event_rows,
        raw_players,
        raw_events,
        players,
        events,
        *aliases,
        *legacy,
        {
            "qualified_names": counts,
            "unique_owners": len(players)
            + len(events)
            + len({name.raw_player_id for name, _, _ in raw_players})
            + len({name.raw_event_id for name, _, _ in raw_events}),
            "batch_contexts": len(batch_contexts),
            "projected_albums": 0,
            "finite": finite,
        },
    )
    context.classification_terms = scope[1] if scope is not None else None
    if checkpoint is not None:
        checkpoint()
    context._classification_docs = _classification_documents(context, checkpoint)
    if checkpoint is not None:
        checkpoint()
    for entry in context._classification_docs.values():
        entry["_source"]["schema_version"] = SCHEMA_VERSION
    context.stats["context_seconds"] = monotonic() - started
    context.stats["classification_documents"] = len(context._classification_docs)
    return context


def _maps(context, albums, lang, raw_players, raw_events, selected, selected_ids, linked_members, *, approvals=False):
    def value(name):
        return (name.decision_kind, name.evidence_id) if approvals else name.display_name

    player_ids = {value for album in albums for value in (album.black_player_id, album.white_player_id) if value}
    event_ids = {album.event_id for album in albums if album.event_id} | {
        event_id for _, event_id in selected.values() if event_id
    }
    players = {
        owner_id: value(context.player_names[lang, owner_id])
        for owner_id in player_ids
        if (lang, owner_id) in context.player_names
    }
    events = {
        owner_id: value(context.event_names[lang, owner_id])
        for owner_id in event_ids
        if owner_id in context.events and (lang, owner_id) in context.event_names
    }
    canonical = {owner_id: context.events[owner_id] for owner_id in events}
    raw_player_map = {raw: (value(name), scope) for name, raw, scope in raw_players if name.lang == lang}
    raw_event_map = identity._raw_event_map(
        [row for row in raw_events if row[0].lang == lang],
        albums,
        selected,
        approvals=approvals,
        selected_ids=selected_ids,
        linked_members=linked_members,
    )
    return players, events, canonical, raw_player_map, raw_event_map


def _slot_approval(album, maps, obscured, selected):
    """The original strict_slot_approvals assembly, using already qualified maps."""
    players, events, canonical, raw_players, raw_events = maps
    event_raw, event_id = selected.get(album.id, (album.event, album.event_id))
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
        approval = events.get(event_id)
        linked = raw_events.get((album.id, event_raw, event_id))
        if linked is not None:
            approval = linked
        elif parse_event(event_raw, None).category == "formal_event_candidate":
            approval = (
                identity._raw_event_value(raw_events, album.id, event_raw, event_id)
                if approval and canonical.get(event_id) == "Oteai"
                else None
            )
        elif approval:
            approval = identity._raw_event_value(
                raw_events,
                album.id,
                event_raw,
                event_id,
                None if structure_event(event_raw or "")["components"] else approval,
            )
    else:
        approval = (
            ("hidden", None)
            if identity._empty_event(event_raw)
            else identity._raw_event_value(raw_events, album.id, event_raw or "", event_id)
        )
    return black, white, None if album.id in obscured else approval


def _fallback_names(context, album, lang, event_hints):
    black = parse_player(album.player_black, album.black_rank)
    white = parse_player(album.player_white, album.white_rank)
    black_name = context.legacy_players.get((album.black_player_id, lang))
    white_name = context.legacy_players.get((album.white_player_id, lang))
    if lang == "cn":
        from katrain.web.kifu.first_pass_cn import player_name

        for side, owner_id in (("black", album.black_player_id), ("white", album.white_player_id)):
            canonical = context.players.get(owner_id, "")
            if (owner_id, lang) not in context.legacy_players and any(
                "\u3400" <= char <= "\u9fff" for char in canonical
            ):
                if side == "black":
                    black_name = black_name or canonical
                else:
                    white_name = white_name or canonical
        black_hint, white_hint = player_name(album.player_black), player_name(album.player_white)
    else:
        black_hint = white_hint = None
    canonical = (
        context.events.get(album.event_id)
        if lang == "cn"
        else (context.events.get(album.event_id) if (album.event_id, lang) in context.legacy_events else None)
    )
    translated = context.legacy_events.get((album.event_id, lang))
    event = (
        identity.display_event_name(album.event, translated, lang, linked_canonical_name=canonical)
        if (album.event_id, lang) in context.legacy_events
        else (
            event_hints.get(album.id)
            or identity.display_event_name(
                album.event, canonical if lang == "cn" else None, lang, linked_canonical_name=canonical
            )
        )
    )
    return black_name or black_hint or black.name, white_name or white_hint or white.name, event


def display_for_language(source, lang):
    """Five stored name languages; the round follows the actual requested UI locale."""
    value = dict(source["display"][identity.name_display_language(lang)])
    value["round_name"] = display_round_name(source["metadata"].get("round_name"), lang)
    return value


def project_album_batch(context, records):
    """Project a finite batch without requalifying any canonical/raw name proof."""
    records = list(records)
    if not records:
        return []
    db = context.db
    ids = {album.id for album in records}
    selected = identity.live_event_selections(db, records)
    selected_ids = {
        album_id
        for (album_id,) in db.query(KifuAlbumEventSelection.album_id).filter(KifuAlbumEventSelection.album_id.in_(ids))
    }
    obscured = identity.obscured_program_event_ids(db, records, selected_events=selected)
    raw_player_values = {value for album in records for value in (album.player_black, album.player_white)}
    raw_event_values = {album.event or "" for album in records} | {raw for raw, _ in selected.values()}
    raw_players = [row for raw in raw_player_values for row in context.raw_players_by_value.get(raw, ())]
    raw_events = [row for raw in raw_event_values for row in context.raw_events_by_value.get(raw, ())]
    linked = identity._linked_live_members(db, raw_events, candidate_ids=ids)
    sources = defaultdict(set)
    for album_id, source_key in (
        db.query(KifuAlbumSource.album_id, KifuSource.source_key)
        .join(KifuSource, KifuAlbumSource.source_id == KifuSource.id)
        .filter(KifuAlbumSource.album_id.in_(ids))
    ):
        sources[album_id].add(source_key)
    hints = {}
    if not context.strict_mode:
        from katrain.web.kifu.first_pass_cn import event_hints

        hints = event_hints(db, records, context.events, selected_events=selected)
    displays = {album.id: {} for album in records}
    approval_languages = set(NAME_LANGUAGES) | {
        name.lang for name, _, _ in raw_events if name.lang in identity.LANGUAGES
    }
    approvals = {}
    for lang in sorted(approval_languages):
        maps = _maps(context, records, lang, raw_players, raw_events, selected, selected_ids, linked)
        approval_maps = _maps(
            context, records, lang, raw_players, raw_events, selected, selected_ids, linked, approvals=True
        )
        approvals[lang] = {album.id: _slot_approval(album, approval_maps, obscured, selected) for album in records}
        if lang not in NAME_LANGUAGES:
            continue
        for album in records:
            fallback = None if context.strict_mode else _fallback_names(context, album, lang, hints)
            black, white, event = identity.resolve_strict_display(
                album, lang, *maps, obscured_event_ids=obscured, selected_events=selected, fallback_names=fallback
            )
            displays[album.id][lang] = {"player_black": black, "player_white": white, "event": event}
    direct_name_ids = defaultdict(set)
    selected_name_ids = defaultdict(set)
    selected_raw_allowed = set()
    for name, raw, proof in raw_events:
        # Per-name eligibility is small and finite; no evidence/batch checker
        # runs here. Reuse the original raw slot map semantics.
        per_name = identity._raw_event_map(
            [(name, raw, proof)], records, selected, selected_ids=selected_ids, linked_members=linked
        )
        for album in records:
            if album.event == raw:
                if identity._raw_event_value(per_name, album.id, raw, album.event_id) is not None:
                    direct_name_ids[album.id].add(name.id)
            if album.id in selected and name.decision_kind != "translated":
                selected_raw, _ = selected[album.id]
                approval = approvals.get(name.lang, {}).get(album.id, (None, None, None))[2]
                if selected_raw == raw and approval == (name.decision_kind, name.evidence_id):
                    selected_name_ids[album.id].add(name.id)
                    selected_raw_allowed.add(album.id)
    provisional_players, provisional_events, provisional_overrides = {}, {}, {}
    if not context.strict_mode:
        from katrain.web.kifu.first_pass_cn import _hints, _display_event_candidate, valid_override_search_ids

        provisional_players, event_values, overrides = _hints()
        provisional_events = {
            (raw, canonical): _display_event_candidate(raw, display)
            for (raw, canonical), display in event_values.items()
            if raw and not any("\u3400" <= char <= "\u9fff" for char in raw)
        }
        provisional_overrides = {
            album_id: overrides[album_id][2] for album_id in valid_override_search_ids(db, ids.intersection(overrides))
        }
    docs = []
    for album in records:
        player_name_ids = {
            name.id
            for name, raw, scope in raw_players
            for slot in ("black", "white")
            if getattr(album, f"player_{slot}") == raw
            and getattr(album, f"{slot}_player_id") is None
            and (scope is None or raw_player_scope_slot(scope, album, slot, raw))
        }
        source = {
            "doc_kind": "album",
            "schema_version": SCHEMA_VERSION,
            "id": album.id,
            "album_id": album.id,
            "black_player_id": album.black_player_id,
            "white_player_id": album.white_player_id,
            "event_id": album.event_id,
            "date_sort": album.date_sort,
            "list_visible": album.duplicate_of_id is None and album.list_hidden_reason is None,
            "player_black_lower": (album.player_black or "").lower(),
            "player_white_lower": (album.player_white or "").lower(),
            "search_text": album.search_text or "",
            "player_aliases": sorted(
                {
                    alias
                    for player_id in (album.black_player_id, album.white_player_id)
                    for alias in context.player_aliases.get(player_id, ())
                }
            ),
            "event_aliases": context.event_aliases.get(album.event_id, []),
            "raw_player_name_ids": sorted(player_name_ids),
            "raw_event_name_ids": sorted(direct_name_ids[album.id]),
            "selected_event_name_ids": sorted(selected_name_ids[album.id]),
            "metadata": {
                **{key: getattr(album, key) for key in _METADATA_FIELDS},
                "sources": sorted(sources[album.id]),
            },
            "display": displays[album.id],
        }
        if not context.strict_mode:
            source["provisional_player_names"] = sorted(
                {
                    provisional_players[raw]
                    for raw in (album.player_black, album.player_white)
                    if raw in provisional_players
                }
            )
            provisional_event = (
                provisional_events.get((album.event, context.events.get(album.event_id)))
                if album.event_id is None or album.event_id in context.events
                else None
            )
            source["provisional_event_names"] = (
                [provisional_event] if provisional_event and album.id not in selected_ids else []
            )
            source["provisional_override_names"] = (
                [provisional_overrides[album.id]] if album.id in provisional_overrides else []
            )
        if album.id in selected:
            raw, event_id = selected[album.id]
            structured = (
                bool(structure_event(raw)["components"]) or parse_event(raw, None).category == "formal_event_candidate"
            )
            if not structured or any(value[album.id][2] is not None for value in approvals.values()):
                source["selected_event_id"] = event_id
            if album.id in selected_raw_allowed:
                source["selected_event_raw_lower"] = raw.lower()
        docs.append(document(album_document_id(album.id), source))
    context.stats["projected_albums"] += len(records)
    return docs
