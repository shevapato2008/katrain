"""Resolve multilingual kifu names without changing original SGF metadata."""

import re
import unicodedata

from sqlalchemy.orm import Session

from katrain.web.core.models_db import (
    KifuAlbumSource,
    KifuEventAlias,
    KifuEventName,
    KifuPlayerAlias,
    KifuPlayerName,
    KifuSource,
)

LANGUAGES = frozenset({"en", "cn", "tw", "jp", "ko", "de", "es", "fr", "ru", "tr", "ua"})
_CWI_OTEAI = re.compile(r"JapanPromotionTournament,([12]\d{3}),(Spring|Fall)\Z", re.IGNORECASE)
_EMBEDDED_DAN = re.compile(r"(.{2,}?)\s*([一二三四五六七八九])段\Z")


def normalize_alias(value: str) -> str:
    """Normalize spacing, width and case while preserving the original script."""
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def split_player_rank(raw: str | None) -> tuple[str, str | None]:
    """Separate an unambiguous Chinese dan suffix from a player's raw SGF name."""
    text = (raw or "").strip()
    match = _EMBEDDED_DAN.fullmatch(text)
    return (match.group(1).strip(), f"{match.group(2)}段") if match else (text, None)


def player_identity_name(raw: str | None) -> str:
    return split_player_rank(raw)[0]


def event_identity_name(raw: str | None) -> str:
    """Treat a sourced CWI Oteai edition as the Oteai event identity."""
    if raw and _CWI_OTEAI.fullmatch(raw.strip()):
        return "JapanPromotionTournament"
    return raw or ""


def identity_lookup_name(kind: str, raw: str | None) -> str:
    return event_identity_name(raw) if kind == "event" else player_identity_name(raw)


def display_event_name(raw: str | None, translated: str | None, lang: str) -> str | None:
    """Keep the year and session when presenting a recognized CWI Oteai edition."""
    match = _CWI_OTEAI.fullmatch((raw or "").strip())
    if not match:
        return translated or raw
    translated = translated or "Oteai"
    year, season = match.groups()
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


def display_maps(db: Session, albums: list, lang: str) -> tuple[dict[int, str], dict[int, str], dict[int, list[str]]]:
    """Load one page's verified names and provenance in three batched queries."""
    player_ids = {value for album in albums for value in (album.black_player_id, album.white_player_id) if value}
    event_ids = {album.event_id for album in albums if album.event_id}
    album_ids = [album.id for album in albums]
    players = {}
    events = {}
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
        events = {
            row.event_id: row.display_name
            for row in db.query(KifuEventName).filter(
                KifuEventName.event_id.in_(event_ids),
                KifuEventName.lang == lang,
                KifuEventName.status == "verified",
            )
        }
    if album_ids:
        for album_id, source_key in (
            db.query(KifuAlbumSource.album_id, KifuSource.source_key)
            .join(KifuSource, KifuAlbumSource.source_id == KifuSource.id)
            .filter(KifuAlbumSource.album_id.in_(album_ids))
        ):
            sources[album_id].add(source_key)
    return players, events, {album_id: sorted(keys) for album_id, keys in sources.items()}
