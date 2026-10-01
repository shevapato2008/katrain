"""Resolve multilingual kifu names without changing original SGF metadata."""

import unicodedata

from sqlalchemy.orm import Session

from katrain.web.core.models_db import (
    KifuAlbumSource,
    KifuEvent,
    KifuEventAlias,
    KifuEventName,
    KifuPlayerAlias,
    KifuPlayerName,
    KifuSource,
)
from katrain.web.kifu.name_parse import parse_event, parse_player

LANGUAGES = frozenset({"en", "cn", "tw", "jp", "ko", "de", "es", "fr", "ru", "tr", "ua"})


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
