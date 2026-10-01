"""Conservative, provisional parsing of raw SGF names and event descriptions.

These results do not establish an identity or approve a translation. The raw SGF
values remain on the album; only the derived display fields use this parsing.
"""

import re
from dataclasses import dataclass


_EMBEDDED_DAN = re.compile(r"(.{2,}?)\s*([一二三四五六七八九])段\Z")
_EXPLICIT_RANK = re.compile(
    r"(?:[一二三四五六七八九十初]|[1-9]\d?)\s*[段级級]|[1-9]\d?\s*(?:[dkp]|dan|kyu|pro)", re.IGNORECASE
)
_SGF_FRAGMENT = re.compile(r"[\[\]]")
_CWI_OTEAI = re.compile(r"JapanPromotionTournament,([12]\d{3}),(Spring|Fall)\Z", re.IGNORECASE)
_PROGRAM_LABEL = re.compile(r"(?:GNU\s*Go|Engine)\s*\d+(?:\.\d+)*\Z", re.IGNORECASE)
_GAME_RESULT = re.compile(r"[黑白]?(?:执[黑白])?.*(?:中盘胜|目半胜|目胜|胜[负負])")
_GENERIC_EVENTS = frozenset({"段位赛", "段位賽", "个人赛", "個人賽"})
_PLACEHOLDERS = frozenset({"unknown", "?", "n/a", "不详", "不詳", "未知"})


@dataclass(frozen=True)
class PlayerParse:
    raw_name: str | None
    raw_rank: str | None
    name: str
    embedded_rank: str | None
    display_rank: str
    category: str
    confidence: str
    exceptions: tuple[str, ...]


@dataclass(frozen=True)
class EventParse:
    raw_event: str | None
    raw_round: str | None
    category: str
    event_candidate: str | None
    year: str | None
    season: str | None
    confidence: str
    exceptions: tuple[str, ...]


def parse_player(raw: str | None, rank: str | None) -> PlayerParse:
    """Extract only unmistakable rank data; leave identity confirmation for review."""
    text = (raw or "").strip()
    explicit = (rank or "").strip()
    exceptions = []
    if _SGF_FRAGMENT.search(text):
        name, embedded, category = "", None, "corrupt_pending"
        exceptions.append("sgf_property_fragment")
    elif not text or text.casefold() in _PLACEHOLDERS:
        name, embedded, category = text, None, "placeholder"
    else:
        match = _EMBEDDED_DAN.fullmatch(text)
        name, embedded = (match.group(1).strip(), f"{match.group(2)}段") if match else (text, None)
        category = "readable_unlinked"

    valid_explicit = bool(_EXPLICIT_RANK.fullmatch(explicit))
    if explicit and not valid_explicit:
        exceptions.append("invalid_explicit_rank")
    if valid_explicit and embedded and explicit != embedded:
        exceptions.append("rank_conflict")
    display_rank = explicit if valid_explicit else embedded or ""
    confidence = "low" if exceptions else "high" if embedded or valid_explicit else "medium"
    return PlayerParse(raw, rank, name, embedded, display_rank, category, confidence, tuple(exceptions))


def parse_event(raw: str | None, round_name: str | None) -> EventParse:
    """Classify a few unambiguous forms without asserting a tournament identity."""
    text = (raw or "").strip()
    if not text:
        return EventParse(raw, round_name, "empty", None, None, None, "high", ())
    if _SGF_FRAGMENT.search(text):
        return EventParse(raw, round_name, "corrupt_data", None, None, None, "low", ("sgf_property_fragment",))
    if _PROGRAM_LABEL.fullmatch(text):
        return EventParse(raw, round_name, "program_source_label", None, None, None, "high", ())
    match = _CWI_OTEAI.fullmatch(text)
    if match:
        year, season = match.groups()
        return EventParse(
            raw,
            round_name,
            "formal_event_candidate",
            "JapanPromotionTournament",
            year,
            season.title(),
            "medium",
            ("identity_unverified",),
        )
    if text in _GENERIC_EVENTS:
        return EventParse(raw, round_name, "generic_event_description", None, None, None, "high", ())
    if _GAME_RESULT.search(text):
        return EventParse(raw, round_name, "game_description", None, None, None, "medium", ())
    return EventParse(raw, round_name, "unclassified_pending", None, None, None, "low", ("classification_review",))
