"""Reversible Chinese display hints for the initial full-catalog pass.

Hints are scoped to exact raw text and the linked event's canonical name. They
never change the SGF, the catalog identity, or the reviewed-name status.
"""

from __future__ import annotations

from functools import lru_cache
import gzip
import hashlib
import json
from pathlib import Path
import re

from sqlalchemy import text
from sqlalchemy.orm import Session

from katrain.web.core.models_db import KifuAlbum

try:  # The older production reader has no selected-event ORM model yet.
    from katrain.web.core.models_db import KifuAlbumEventSelection
except ImportError:  # pragma: no cover - exercised by the production compatibility image
    KifuAlbumEventSelection = None


_ASSET = Path(__file__).resolve().parent / "data/cn_first_pass_2026-10-05.json.gz"
_OTEAI_EDITION = re.compile(r"JapanPromotionTournament,([12]\d{3}),(Spring|Fall)\Z", re.IGNORECASE)


@lru_cache(maxsize=1)
def _hints():
    if not _ASSET.exists():
        return {}, {}, {}
    with gzip.open(_ASSET, "rt", encoding="utf-8") as stream:
        payload = json.load(stream)
    if payload.get("format") != "kifu-cn-first-pass-v1":
        raise ValueError("Unsupported Chinese kifu display asset")
    players = {raw: entry["display"] for raw, entry in payload["player_raw"].items()}
    events = {(raw, canonical): value for raw, canonical, value in payload["event_raw_canonical"]}
    overrides = {album_id: (raw, digest, value) for album_id, raw, digest, value in payload["event_album_sgf"]}
    return players, events, overrides


def player_name(raw: str | None) -> str | None:
    return _hints()[0].get(raw)


def _display_event_candidate(raw: str | None, candidate: str) -> str:
    if candidate != "大手合":
        return candidate
    match = _OTEAI_EDITION.fullmatch((raw or "").strip())
    if match:
        season = "春季" if match.group(2).casefold() == "spring" else "秋季"
        return f"{match.group(1)}年{season}大手合"
    if raw:
        year = re.search(r"\b(?:18|19|20)\d{2}\b", raw)
        if year:
            return f"{year.group()}年大手合"
    return candidate


def search_raw_names(chinese_name: str) -> tuple[set[str], set[tuple[str, str | None]], set[int]]:
    """Expand Chinese display searches to a bounded set of romanized SGF spellings."""
    players, events, overrides = _hints()
    player_raws = {raw for raw, display in players.items() if display == chinese_name}
    event_keys = {
        (raw, canonical) for (raw, canonical), display in events.items()
        if (chinese_name == _display_event_candidate(raw, display)
            or (len(chinese_name) >= 3 and chinese_name in _display_event_candidate(raw, display)))
        and raw and not any("\u3400" <= ch <= "\u9fff" for ch in raw)
    }
    album_ids = {album_id for album_id, (_, _, display) in overrides.items() if display == chinese_name}
    return player_raws, event_keys if len(event_keys) <= 200 else set(), album_ids


def valid_override_search_ids(db: Session, album_ids: set[int]) -> set[int]:
    """Do not search under a stale SGF label or superseded event selection."""
    if not album_ids:
        return set()
    overrides = _hints()[2]
    selected = _selected_album_ids(db, album_ids)
    valid = set()
    for album_id, raw, event_id, content in db.query(
        KifuAlbum.id, KifuAlbum.event, KifuAlbum.event_id, KifuAlbum.sgf_content
    ).filter(KifuAlbum.id.in_(album_ids)):
        if album_id in selected or event_id is not None:
            continue
        expected_raw, expected_hash, _ = overrides[album_id]
        if raw == expected_raw and hashlib.sha256(content.encode("utf-8")).hexdigest() == expected_hash:
            valid.add(album_id)
    return valid


def _selected_album_ids(db: Session, album_ids: set[int]) -> set[int]:
    if not album_ids:
        return set()
    if KifuAlbumEventSelection is None:
        # The legacy production ORM predates this table, but the live database has it.
        rows = db.execute(
            text("SELECT album_id FROM kifu_album_event_selections WHERE album_id = ANY(:album_ids)"),
            {"album_ids": list(album_ids)},
        )
    else:
        rows = db.query(KifuAlbumEventSelection.album_id).filter(
            KifuAlbumEventSelection.album_id.in_(album_ids)
        )
    return {row[0] for row in rows}


def event_hints(
    db: Session, albums: list[KifuAlbum], canonical_names: dict[int, str], *, selected_events=None
) -> dict[int, str]:
    """Resolve page hints, checking source bytes for SGF-derived overrides in one query."""
    _, event_names, overrides = _hints()
    selected_events = selected_events or {}
    selected_ids = _selected_album_ids(db, {album.id for album in albums})
    result = {}
    to_verify = {}
    for album in albums:
        if album.id in selected_events or album.id in selected_ids:
            continue  # A reviewed selection outranks the raw SGF hint.
        raw = album.event
        canonical = canonical_names.get(album.event_id)
        candidate = event_names.get((raw, canonical))
        if candidate:
            result[album.id] = _display_event_candidate(raw, candidate)
        if album.event_id is None and album.id in overrides:
            expected_raw, expected_hash, display = overrides[album.id]
            if raw == expected_raw:
                to_verify[album.id] = (expected_hash, display)
    if to_verify:
        for album_id, content in db.query(KifuAlbum.id, KifuAlbum.sgf_content).filter(
            KifuAlbum.id.in_(to_verify)
        ):
            expected_hash, display = to_verify[album_id]
            if hashlib.sha256(content.encode("utf-8")).hexdigest() == expected_hash:
                result[album_id] = display
    return result
