"""Inventory every raw SGF event spelling without deciding tournament identity."""

from collections import Counter, defaultdict

from sqlalchemy import select

from katrain.web.core.models_db import KifuRawEventValue
from katrain.web.kifu.name_parse import parse_event
from katrain.web.kifu.name_structure import RULE_VERSION, structure_event

NULL_EVENT_SENTINEL = "␀KIFU_NULL_EVENT"
PARSER_VERSION = f"{RULE_VERSION}-catalog-v1"
NON_SERIES_CATEGORIES = frozenset({
    "empty", "generic_event_description", "game_description", "program_source_label", "corrupt_data",
})


def _inventory_event_counts(inventory, expected_games):
    """Compare the aggregate EV counts with one raw EV slot per album."""
    if not isinstance(inventory, dict) or inventory.get("inventory_format") not in {2, 3, 4}:
        raise ValueError("inventory_format 2, 3 or 4 is required")
    total = inventory.get("counts", {}).get("all")
    if type(total) is not int or total < 0 or (expected_games is not None and total != expected_games):
        raise ValueError("event inventory has the wrong album count")
    columns = inventory.get("association_columns")
    associations = inventory.get("album_associations")
    if (not isinstance(columns, list) or not isinstance(associations, list)
            or "id" not in columns or "event" not in columns):
        raise ValueError("event inventory requires album associations")
    id_index, event_index = columns.index("id"), columns.index("event")
    ids = set()
    association_counts = Counter()
    for association in associations:
        if not isinstance(association, list) or len(association) != len(columns):
            raise ValueError("malformed event album association")
        album_id, raw = association[id_index], association[event_index]
        if type(album_id) is not int or album_id < 1 or album_id in ids:
            raise ValueError("duplicate or invalid album ID in event inventory")
        if raw is not None and not isinstance(raw, str):
            raise ValueError("raw event value must be text or null")
        ids.add(album_id)
        association_counts[raw] += 1
    if len(ids) != total:
        raise ValueError("event inventory album count differs from associations")

    try:
        rows = inventory["scopes"]["all"]["values"]["event"]
        distinct = inventory["distinct_values"]["all"]["event"]
    except (KeyError, TypeError):
        raise ValueError("event value summary is missing") from None
    if not isinstance(rows, list) or type(distinct) is not int or distinct != len(rows):
        raise ValueError("event distinct count differs from value rows")
    summary_counts = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("malformed event value row")
        raw = row.get("value")
        count = row.get("occurrences")
        if raw is not None and not isinstance(raw, str):
            raise ValueError("raw event value must be text or null")
        if raw in summary_counts:
            raise ValueError("duplicate raw event value in inventory")
        if type(count) is not int or count < 1 or row.get("affected_games") != count:
            raise ValueError("invalid event occurrence count")
        summary_counts[raw] = count
    if summary_counts != association_counts or sum(summary_counts.values()) != total:
        raise ValueError("event value counts differ from album associations")
    if NULL_EVENT_SENTINEL in summary_counts:
        raise ValueError("raw event collides with reserved null sentinel")
    return summary_counts


def prepare_event_raw_values(inventory, *, expected_games=None):
    """Return exact raw values and review hints after complete slot reconciliation."""
    counts = _inventory_event_counts(inventory, expected_games)
    rows = []
    for original in sorted(counts, key=lambda value: (value is not None, (value or "").encode("utf-8"))):
        parsed = parse_event(original, None)
        structure = structure_event(original or "")
        core = structure["core"] if parsed.category not in NON_SERIES_CATEGORIES else None
        rows.append({
            "raw_value": NULL_EVENT_SENTINEL if original is None else original,
            "category": parsed.category,
            "parsed_data": {
                "original_raw_value": original,
                "occurrences": counts[original],
                "series_core": core,
                "parse_exceptions": list(parsed.exceptions),
                "structure": structure,
            },
            "parser_version": PARSER_VERSION,
            "review_status": "pending",
        })
    return rows


def upsert_event_raw_values(db, rows):
    """Insert or refresh derived hints, leaving existing review decisions intact.

    The caller owns the transaction. No event IDs or album foreign keys change.
    """
    raw_values = [row["raw_value"] for row in rows]
    if len(set(raw_values)) != len(raw_values):
        raise ValueError("duplicate prepared raw event value")
    for row in rows:
        if (row["raw_value"] == NULL_EVENT_SENTINEL) != (row["parsed_data"]["original_raw_value"] is None):
            raise ValueError("reserved null sentinel mapping is inconsistent")
    table = KifuRawEventValue.__table__
    stats = {"inserted": 0, "updated": 0, "unchanged": 0, "protected": 0}
    for start in range(0, len(rows), 500):
        batch = rows[start:start + 500]
        existing = {
            item["raw_value"]: item for item in db.execute(
                select(table).where(table.c.raw_value.in_([row["raw_value"] for row in batch]))
            ).mappings()
        }
        to_insert = []
        for row in batch:
            raw = row["raw_value"]
            item = existing.get(raw)
            if item is None:
                to_insert.append(row)
                stats["inserted"] += 1
                continue
            if (raw == NULL_EVENT_SENTINEL
                    and (item["parsed_data"] or {}).get("original_raw_value", object()) is not None):
                raise ValueError("existing raw event collides with reserved null sentinel")
            if item["review_status"] != "pending" or item["parser_version"] != row["parser_version"]:
                stats["protected"] += 1
                continue
            derived = {field: row[field] for field in ("category", "parsed_data", "parser_version")}
            if all(item[field] == value for field, value in derived.items()):
                stats["unchanged"] += 1
            else:
                updated = db.execute(table.update().where(
                    table.c.id == item["id"],
                    table.c.review_status == "pending",
                    table.c.parser_version == row["parser_version"],
                ).values(**derived))
                if updated.rowcount != 1:
                    raise ValueError("raw event review changed during staging")
                stats["updated"] += 1
        if to_insert:
            db.execute(table.insert(), to_insert)
    return stats


def event_series_review_queue(rows):
    """Group provisional series cores by frequency for human review only."""
    grouped = defaultdict(list)
    for row in rows:
        parsed_data = row["parsed_data"]
        core = parsed_data["series_core"]
        if core:
            grouped[core].append({
                "raw_value": parsed_data["original_raw_value"],
                "occurrences": parsed_data["occurrences"],
            })
    queue = []
    for core, members in grouped.items():
        members.sort(key=lambda item: (-item["occurrences"], item["raw_value"].encode("utf-8")))
        queue.append({
            "series_core": core,
            "occurrences": sum(member["occurrences"] for member in members),
            "raw_value_count": len(members),
            "raw_values": members,
            "review_status": "pending",
        })
    queue.sort(key=lambda item: (-item["occurrences"], item["series_core"].encode("utf-8")))
    return queue
