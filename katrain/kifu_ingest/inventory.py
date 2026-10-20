"""Read-only inventory of numeric 19x19 SGF sources.

This module deliberately does not choose translated names or connect to the album
database. ``sgf_content`` matches the canonical serialization used by the
existing album importer; callers decide whether a candidate can be imported.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from hashlib import sha256
import os
from pathlib import Path
import re
from typing import Callable, Iterable

import chardet

from katrain.core.sgf_parser import ParseError, SGF


_SOURCE_ID = re.compile(r"[0-9]+\Z")
_FULL_DATE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}\Z")
_ORIGIN_PREFIX = "data/kifu-album/19x19"


@dataclass(frozen=True)
class InventoryEntry:
    source_id: str
    origin_path: str
    raw_sha256: str
    sgf_sha256: str
    sgf_content: str
    date_raw: str | None
    date_status: str
    date_played: str | None
    player_black: str | None
    player_white: str | None
    black_rank: str | None
    white_rank: str | None
    ev_values: tuple[str, ...]
    gn_values: tuple[str, ...]
    gc_values: tuple[str, ...]
    source_raw: str | None
    user_raw: str | None
    event_raw: str | None
    round_raw: str | None
    result_raw: str | None
    move_count: int


@dataclass(frozen=True)
class InventoryError:
    source_id: str
    reason: str


@dataclass
class InventorySummary:
    total_sgf_files: int = 0
    known_source_paths: int = 0
    excluded_source_ids: int = 0
    invalid_source_id: int = 0
    in_range: int = 0
    out_of_range: int = 0
    date_pending: int = 0
    errors_count: int = 0
    date_min: str | None = None
    date_max: str | None = None
    errors: list[InventoryError] = field(default_factory=list)


def _full_date(value: str | None) -> date | None:
    if not isinstance(value, str) or not _FULL_DATE.fullmatch(value):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _decode_like_importer(raw: bytes) -> str:
    """Use the same SGF character-set choice and loss handling as SGF.parse_file."""
    if b"AP[foxwq]" in raw:
        encoding = "utf8"
    else:
        declared = re.search(rb"CA\[(.*?)\]", raw)
        if declared:
            encoding = declared[1].decode("ascii", errors="ignore")
        else:
            encoding = chardet.detect(raw[:300])["encoding"]
            if encoding in {"Windows-1252", "GB2312"}:
                encoding = "GBK"
    try:
        return raw.decode(encoding=encoding, errors="ignore")
    except LookupError:
        return raw.decode(encoding=SGF.DEFAULT_ENCODING, errors="ignore")


def _mainline_moves(root) -> int:
    count = 0
    node = root
    while node.children:
        node = node.children[0]
        if node.move:
            count += 1
    return count


def _entry(path: Path, source_id: str, boundary: date) -> InventoryEntry:
    raw = path.read_bytes()
    root = SGF.parse_sgf(_decode_like_importer(raw))
    canonical = root.sgf()
    date_raw = root.get_property("DT")
    parsed_date = _full_date(date_raw)
    status = "date_pending" if parsed_date is None else "in_range" if parsed_date > boundary else "out_of_range"
    ev = tuple(root.get_list_property("EV") or ())
    gn = tuple(root.get_list_property("GN") or ())
    return InventoryEntry(
        source_id=source_id,
        origin_path=f"{_ORIGIN_PREFIX}/{source_id}.sgf",
        raw_sha256=sha256(raw).hexdigest(),
        sgf_sha256=sha256(canonical.encode("utf-8")).hexdigest(),
        sgf_content=canonical,
        date_raw=date_raw,
        date_status=status,
        date_played=parsed_date.isoformat() if parsed_date else None,
        player_black=root.get_property("PB"),
        player_white=root.get_property("PW"),
        black_rank=root.get_property("BR"),
        white_rank=root.get_property("WR"),
        ev_values=ev,
        gn_values=gn,
        gc_values=tuple(root.get_list_property("GC") or ()),
        source_raw=root.get_property("SO"),
        user_raw=root.get_property("US"),
        event_raw=(ev[0] if ev and ev[0] else gn[0] if gn else None),
        round_raw=root.get_property("RO"),
        result_raw=root.get_property("RE"),
        move_count=_mainline_moves(root),
    )


def scan_inventory(
    source_dir: str | Path,
    *,
    after: str = "2026-01-30",
    known_source_paths: Iterable[str] = (),
    excluded_source_ids: Iterable[str] = (),
    on_entry: Callable[[InventoryEntry], None],
) -> InventorySummary:
    """Visit direct ``*.sgf`` children and stream every new valid candidate.

    Complete DT dates alone determine the cutoff. Known paths and excluded IDs
    are skipped before file reads. The callback owns its entries; the summary
    contains only counts, actual complete-DT bounds, and sanitized errors.
    """
    boundary = _full_date(after)
    if boundary is None:
        raise ValueError("after must be a complete ISO date")
    excluded = set(excluded_source_ids)
    if any(not isinstance(value, str) or not _SOURCE_ID.fullmatch(value) for value in excluded):
        raise ValueError("excluded source ID must contain ASCII digits only")
    known = set(known_source_paths)
    directory = Path(source_dir)
    if "kifu-album" in directory.resolve().parts:
        raise ValueError("album source directory is outside inventory scope")
    summary = InventorySummary()
    with os.scandir(directory) as entries:
        candidates = sorted(
            (entry.name for entry in entries if entry.name.endswith(".sgf") and entry.is_file(follow_symlinks=False)),
            key=lambda name: (int(name[:-4]), name) if _SOURCE_ID.fullmatch(name[:-4]) else (float("inf"), name),
        )
    for name in candidates:
        summary.total_sgf_files += 1
        source_id = name[:-4]
        if not _SOURCE_ID.fullmatch(source_id):
            summary.invalid_source_id += 1
            continue
        origin_path = f"{_ORIGIN_PREFIX}/{source_id}.sgf"
        if origin_path in known:
            summary.known_source_paths += 1
            continue
        if source_id in excluded:
            summary.excluded_source_ids += 1
            continue
        try:
            item = _entry(directory / name, source_id, boundary)
        except (OSError, ParseError, UnicodeError, ValueError, TypeError, IndexError, RecursionError) as exc:
            reason = "file_read_error" if isinstance(exc, OSError) else "sgf_parse_error"
            summary.errors.append(InventoryError(source_id=source_id, reason=reason))
            summary.errors_count += 1
            continue
        setattr(summary, item.date_status, getattr(summary, item.date_status) + 1)
        if item.date_played is not None:
            summary.date_min = min(summary.date_min, item.date_played) if summary.date_min else item.date_played
            summary.date_max = max(summary.date_max, item.date_played) if summary.date_max else item.date_played
        on_entry(item)
    return summary
