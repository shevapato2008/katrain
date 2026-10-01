"""Resolve multilingual kifu names without changing original SGF metadata."""

import os
import unicodedata

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from katrain.web.core.models_db import (
    KifuAlbumSource,
    KifuEvent,
    KifuEventAlias,
    KifuEventName,
    KifuNameResearchEvidence,
    KifuPlayerAlias,
    KifuPlayerName,
    KifuRawEventName,
    KifuRawEventValue,
    KifuRawPlayerName,
    KifuRawPlayerValue,
    KifuSource,
)
from katrain.web.kifu.name_parse import parse_event, parse_player
from katrain.web.kifu.name_structure import structure_event

LANGUAGES = frozenset({"en", "cn", "tw", "jp", "ko", "de", "es", "fr", "ru", "tr", "ua"})
_DECISIONS = frozenset({"conventional", "generated", "generic", "hidden", "placeholder", "error", "corrected"})
_UNAVAILABLE_LABELS = {
    "en": ("Player name unverified", "Event name unverified"),
    "cn": ("棋手姓名待核实", "赛事名称待核实"),
    "tw": ("棋手姓名待核實", "賽事名稱待核實"),
    "jp": ("棋士名は未確認", "棋戦名は未確認"),
    "ko": ("기사 이름 미확인", "대회 이름 미확인"),
    "de": ("Spielername ungeprüft", "Turniername ungeprüft"),
    "es": ("Nombre del jugador sin verificar", "Nombre del torneo sin verificar"),
    "fr": ("Nom du joueur non vérifié", "Nom du tournoi non vérifié"),
    "ru": ("Имя игрока не проверено", "Название турнира не проверено"),
    "tr": ("Oyuncu adı doğrulanmadı", "Turnuva adı doğrulanmadı"),
    "ua": ("Ім’я гравця не перевірено", "Назву турніру не перевірено"),
}


def strict_unavailable_label(lang: str, kind: str) -> str:
    """A visible coverage gap, distinct from a reviewed placeholder or damaged value."""
    return _UNAVAILABLE_LABELS[lang][0 if kind == "player" else 1]


def strict_names_enabled() -> bool:
    """Activate only after the full catalog has passed coverage review."""
    return os.getenv("KIFU_STRICT_NAMES", "").lower() in {"1", "true", "yes"}


def _approved_names(db: Session, model, owner_column: str, ids: set[int] | None = None, lang: str | None = None):
    """Reject legacy verified rows and evidence for another owner or revision."""
    owner = getattr(model, owner_column)
    evidence_owner = getattr(KifuNameResearchEvidence, owner_column)
    query = (
        db.query(model)
        .join(KifuNameResearchEvidence, model.evidence_id == KifuNameResearchEvidence.id)
        .filter(
            owner == evidence_owner,
            model.lang == KifuNameResearchEvidence.lang,
            model.status == "verified",
            KifuNameResearchEvidence.review_status == "approved",
            KifuNameResearchEvidence.producer_model.isnot(None),
            KifuNameResearchEvidence.reviewer_model.isnot(None),
            KifuNameResearchEvidence.reviewer_id.isnot(None),
            KifuNameResearchEvidence.reviewed_at.isnot(None),
            KifuNameResearchEvidence.reviewer_id != KifuNameResearchEvidence.producer_id,
            model.revision == KifuNameResearchEvidence.revision,
            model.decision_kind == KifuNameResearchEvidence.decision_kind,
            model.decision_kind.in_(_DECISIONS),
            model.generation_rule_version == KifuNameResearchEvidence.generation_rule_version,
            model.display_name == KifuNameResearchEvidence.candidate_name,
        )
    )
    if ids is not None:
        query = query.filter(owner.in_(ids))
    if lang is not None:
        query = query.filter(model.lang == lang)
    return query


def strict_matching_names(db: Session, query: str) -> tuple[set[int], set[int], set[str], set[str]]:
    """Only unique approved identity names expand across languages."""
    needle = normalize_alias(query)
    if not needle:
        return set(), set(), set(), set()
    identity_matches = []
    for model, owner in ((KifuPlayerName, "player_id"), (KifuEventName, "event_id")):
        rows = _approved_names(db, model, owner).filter(
            or_(model.display_name == query, func.lower(model.display_name) == query.lower())
        )
        identity_matches.append({getattr(row, owner) for row in rows if normalize_alias(row.display_name) == needle})
    player_ids, event_ids = identity_matches
    if len(player_ids) + len(event_ids) != 1:
        player_ids, event_ids = set(), set()
    raw_matches = []
    for model, value_model, owner in (
        (KifuRawPlayerName, KifuRawPlayerValue, "raw_player_id"),
        (KifuRawEventName, KifuRawEventValue, "raw_event_id"),
    ):
        rows = (
            _approved_names(db, model, owner)
            .join(value_model, getattr(model, owner) == value_model.id)
            .filter(
                value_model.review_status == "approved",
                or_(model.display_name == query, func.lower(model.display_name) == query.lower()),
            )
            .with_entities(model.display_name, value_model.raw_value)
        )
        matches = {raw for display, raw in rows if normalize_alias(display) == needle}
        raw_matches.append(matches if len(matches) == 1 else set())
    return player_ids, event_ids, *raw_matches


def strict_display_maps(db: Session, albums: list, lang: str):
    """Read names for the current page in bounded, batched queries."""
    player_ids = {v for album in albums for v in (album.black_player_id, album.white_player_id) if v}
    event_ids = {album.event_id for album in albums if album.event_id}
    raw_players = {v for album in albums for v in (album.player_black, album.player_white) if v is not None}
    raw_events = {album.event or "" for album in albums}
    players = {
        row.player_id: row.display_name for row in _approved_names(db, KifuPlayerName, "player_id", player_ids, lang)
    }
    event_rows = (
        _approved_names(db, KifuEventName, "event_id", event_ids, lang)
        .join(KifuEvent, KifuEventName.event_id == KifuEvent.id)
        .with_entities(KifuEventName.event_id, KifuEventName.display_name, KifuEvent.canonical_name)
        .all()
    )
    events = {row.event_id: row.display_name for row in event_rows}
    canonical = {row.event_id: row.canonical_name for row in event_rows}
    raw_maps = []
    for model, value_model, owner, values in (
        (KifuRawPlayerName, KifuRawPlayerValue, "raw_player_id", raw_players),
        (KifuRawEventName, KifuRawEventValue, "raw_event_id", raw_events),
    ):
        rows = (
            _approved_names(db, model, owner, lang=lang)
            .join(value_model, getattr(model, owner) == value_model.id)
            .filter(value_model.review_status == "approved", value_model.raw_value.in_(values))
            .with_entities(value_model.raw_value, model.display_name)
        )
        raw_maps.append({raw: display for raw, display in rows})
    album_ids = [album.id for album in albums]
    sources: dict[int, set[str]] = {album_id: set() for album_id in album_ids}
    if album_ids:
        for album_id, source_key in (
            db.query(KifuAlbumSource.album_id, KifuSource.source_key)
            .join(KifuSource, KifuAlbumSource.source_id == KifuSource.id)
            .filter(KifuAlbumSource.album_id.in_(album_ids))
        ):
            sources[album_id].add(source_key)
    return players, events, canonical, {k: sorted(v) for k, v in sources.items()}, *raw_maps


def _empty_event(raw: str | None) -> bool:
    """An absent SGF event has one explicit, language-independent empty display."""
    return parse_event(raw, None).category == "empty"


def strict_slot_approvals(db: Session, albums: list, lang: str) -> dict[int, tuple[tuple[str, int | None] | None, ...]]:
    """Return approved decision/evidence for each visible slot; None is a coverage gap.

    Structured events need both an approved identity name and their own approved
    exact raw-event display; CWI editions additionally require an Oteai identity.
    An absent event has an explicit empty decision with
    no evidence row because there is no source value to research. Queries remain
    bounded by the supplied album page.
    """
    player_ids = {v for album in albums for v in (album.black_player_id, album.white_player_id) if v}
    event_ids = {album.event_id for album in albums if album.event_id}
    raw_player_values = {v for album in albums for v in (album.player_black, album.player_white)}
    raw_event_values = {album.event or "" for album in albums}
    entity_approvals = []
    for model, owner, ids in (
        (KifuPlayerName, "player_id", player_ids),
        (KifuEventName, "event_id", event_ids),
    ):
        rows = _approved_names(db, model, owner, ids, lang).with_entities(
            getattr(model, owner), model.decision_kind, model.evidence_id
        )
        entity_approvals.append({key: (decision, evidence_id) for key, decision, evidence_id in rows})
    raw_approvals = []
    for model, value_model, owner, values in (
        (KifuRawPlayerName, KifuRawPlayerValue, "raw_player_id", raw_player_values),
        (KifuRawEventName, KifuRawEventValue, "raw_event_id", raw_event_values),
    ):
        rows = (
            _approved_names(db, model, owner, lang=lang)
            .join(value_model, getattr(model, owner) == value_model.id)
            .filter(value_model.review_status == "approved", value_model.raw_value.in_(values))
            .with_entities(value_model.raw_value, model.decision_kind, model.evidence_id)
        )
        raw_approvals.append({raw: (decision, evidence_id) for raw, decision, evidence_id in rows})
    canonical = dict(db.query(KifuEvent.id, KifuEvent.canonical_name).filter(KifuEvent.id.in_(event_ids)))
    players, events = entity_approvals
    raw_players, raw_events = raw_approvals
    result = {}
    for album in albums:
        black = players.get(album.black_player_id) if album.black_player_id else raw_players.get(album.player_black)
        white = players.get(album.white_player_id) if album.white_player_id else raw_players.get(album.player_white)
        if album.event_id:
            event_approval = events.get(album.event_id)
            if parse_event(album.event, None).category == "formal_event_candidate":
                event_approval = (
                    raw_events.get(album.event) if event_approval and canonical.get(album.event_id) == "Oteai" else None
                )
            elif event_approval:
                event_approval = raw_events.get(
                    album.event, None if structure_event(album.event or "")["components"] else event_approval
                )
        else:
            event_approval = ("hidden", None) if _empty_event(album.event) else raw_events.get(album.event or "")
        result[album.id] = black, white, event_approval
    return result


def strict_fallback(raw: str | None, lang: str, kind: str) -> str:
    """An explicit localized fallback keeps malformed SGF outside display fields."""
    from katrain.web.kifu.name_candidates import _CLASSIFICATION_TEMPLATES

    labels = _CLASSIFICATION_TEMPLATES[lang]
    if kind == "player":
        category = parse_player(raw, None).category
        if category == "corrupt_pending":
            return labels["player_error"]
        if category == "placeholder":
            return labels["placeholder"]
        return strict_unavailable_label(lang, kind)
    category = parse_event(raw, None).category
    if _empty_event(raw):
        return ""
    if category == "corrupt_data":
        return labels["event_error"]
    return strict_unavailable_label(lang, kind)


def resolve_strict_display(
    album,
    lang: str,
    players: dict[int, str],
    events: dict[int, str],
    canonical_events: dict[int, str],
    raw_players: dict[str, str],
    raw_events: dict[str, str],
) -> tuple[str, str, str]:
    """Resolve the three visible name slots from the same maps used by coverage checks."""
    black = players.get(album.black_player_id) if album.black_player_id else raw_players.get(album.player_black)
    white = players.get(album.white_player_id) if album.white_player_id else raw_players.get(album.player_white)
    event_name = events.get(album.event_id) if album.event_id else raw_events.get(album.event or "")
    if album.event_id and event_name is not None:
        if parse_event(album.event, None).category == "formal_event_candidate":
            displayed_event = raw_events.get(album.event) if canonical_events.get(album.event_id) == "Oteai" else None
        else:
            displayed_event = raw_events.get(
                album.event, None if structure_event(album.event or "")["components"] else event_name
            )
    else:
        displayed_event = event_name
    return (
        black if black is not None else strict_fallback(album.player_black, lang, "player"),
        white if white is not None else strict_fallback(album.player_white, lang, "player"),
        displayed_event if displayed_event is not None else strict_fallback(album.event, lang, "event"),
    )


def normalize_alias(value: str) -> str:
    """Normalize spacing, width and case while preserving the original script."""
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def split_player_rank(raw: str | None) -> tuple[str, str | None]:
    """Separate an unambiguous Chinese dan suffix from a player's raw SGF name."""
    parsed = parse_player(raw, None)
    return parsed.name, parsed.embedded_rank


def player_identity_name(raw: str | None) -> str:
    return split_player_rank(raw)[0]


def event_identity_name(raw: str | None) -> str:
    """Find a provisional identity lookup key without approving the event."""
    return parse_event(raw, None).event_candidate or raw or ""


def identity_lookup_name(kind: str, raw: str | None) -> str:
    return event_identity_name(raw) if kind == "event" else player_identity_name(raw)


def display_event_name(
    raw: str | None, translated: str | None, lang: str, *, linked_canonical_name: str | None
) -> str | None:
    """Decorate a CWI edition only for a linked Oteai with a verified name."""
    parsed = parse_event(raw, None)
    if parsed.category != "formal_event_candidate":
        return translated or raw
    if not translated or linked_canonical_name != "Oteai":
        return raw
    year, season = parsed.year, parsed.season
    labels = {
        "en": ("Spring", "Autumn"),
        "cn": ("春季", "秋季"),
        "tw": ("春季", "秋季"),
        "jp": ("春季", "秋季"),
        "ko": ("봄", "가을"),
        "de": ("Frühjahr", "Herbst"),
        "es": ("primavera", "otoño"),
        "fr": ("printemps", "automne"),
        "ru": ("весна", "осень"),
        "tr": ("ilkbahar", "sonbahar"),
        "ua": ("весна", "осінь"),
    }
    if lang not in labels:
        return raw
    label = labels[lang][0 if season.casefold() == "spring" else 1]
    if lang in {"cn", "tw", "jp"}:
        return f"{year}年{label}{translated}"
    if lang == "ko":
        return f"{year}년 {label} {translated}"
    return f"{translated} · {label} {year}"


def matching_entity_ids(db: Session, query: str, *, exact: bool) -> tuple[set[int], set[int]]:
    needle = normalize_alias(query)
    if not needle:
        return set(), set()
    player_query = db.query(KifuPlayerAlias.player_id)
    event_query = db.query(KifuEventAlias.event_id)
    if exact:
        player_query = player_query.filter(KifuPlayerAlias.normalized_alias == needle)
        event_query = event_query.filter(KifuEventAlias.normalized_alias == needle)
    else:
        player_query = player_query.filter(KifuPlayerAlias.normalized_alias.contains(needle, autoescape=True))
        event_query = event_query.filter(KifuEventAlias.normalized_alias.contains(needle, autoescape=True))
    return {row[0] for row in player_query.distinct()}, {row[0] for row in event_query.distinct()}


def display_maps(
    db: Session, albums: list, lang: str
) -> tuple[dict[int, str], dict[int, str], dict[int, str], dict[int, list[str]]]:
    """Load one page's verified names and provenance in three batched queries."""
    player_ids = {value for album in albums for value in (album.black_player_id, album.white_player_id) if value}
    event_ids = {album.event_id for album in albums if album.event_id}
    album_ids = [album.id for album in albums]
    players = {}
    events = {}
    event_canonical_names = {}
    sources: dict[int, set[str]] = {album_id: set() for album_id in album_ids}
    if player_ids:
        players = {
            row.player_id: row.display_name
            for row in db.query(KifuPlayerName).filter(
                KifuPlayerName.player_id.in_(player_ids),
                KifuPlayerName.lang == lang,
                KifuPlayerName.status == "verified",
            )
        }
    if event_ids:
        event_rows = (
            db.query(KifuEventName.event_id, KifuEventName.display_name, KifuEvent.canonical_name)
            .join(KifuEvent, KifuEventName.event_id == KifuEvent.id)
            .filter(
                KifuEventName.event_id.in_(event_ids),
                KifuEventName.lang == lang,
                KifuEventName.status == "verified",
            )
            .all()
        )
        events = {row.event_id: row.display_name for row in event_rows}
        event_canonical_names = {row.event_id: row.canonical_name for row in event_rows}
    if album_ids:
        for album_id, source_key in (
            db.query(KifuAlbumSource.album_id, KifuSource.source_key)
            .join(KifuSource, KifuAlbumSource.source_id == KifuSource.id)
            .filter(KifuAlbumSource.album_id.in_(album_ids))
        ):
            sources[album_id].add(source_key)
    return players, events, event_canonical_names, {album_id: sorted(keys) for album_id, keys in sources.items()}
