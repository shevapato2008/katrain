"""Inventory-wide, provisional player spelling classification.

Raw spellings are not identities. This module does not create player IDs or
approve any raw-to-player association.
"""

from collections import Counter

from sqlalchemy import select

from katrain.web.core.models_db import KifuRawPlayerValue
from katrain.web.kifu.name_parse import parse_player


PLAYER_PARSER_VERSION = "catalog-player-v1"


def prepare_player_raw_values(inventory: dict) -> list[dict]:
    """Validate the shared format-2/3/4 all scope and group non-null values."""
    try:
        if inventory["inventory_format"] not in (2, 3, 4):
            raise ValueError("player preprocessing requires inventory format 2, 3, or 4")
        count = inventory["counts"]["all"]
        columns = inventory["association_columns"]
        albums = inventory["album_associations"]
        scope = inventory["scopes"]["all"]
        summary = scope["values"]["player"]
        scope_ids = scope["album_ids"]
        detail_ids = inventory["detail_ids"]
    except (KeyError, TypeError) as exc:
        raise ValueError("incomplete player inventory") from exc

    if (not isinstance(count, int) or count < 0 or not isinstance(columns, list)
            or len(columns) != len(set(columns))
            or not {"id", "player_black", "player_white"}.issubset(columns)
            or not isinstance(albums, list) or not isinstance(summary, list)
            or not isinstance(scope_ids, list) or not isinstance(detail_ids, list)
            or len(albums) != count or len(scope_ids) != count or len(detail_ids) != count):
        raise ValueError("incomplete player inventory")

    index = {key: columns.index(key) for key in ("id", "player_black", "player_white")}
    slot_counts = Counter()
    game_counts = Counter()
    album_ids = []
    for album in albums:
        if not isinstance(album, list) or len(album) != len(columns):
            raise ValueError("invalid album association row")
        album_id = album[index["id"]]
        if not isinstance(album_id, int):
            raise ValueError("invalid album ID")
        album_ids.append(album_id)
        black, white = album[index["player_black"]], album[index["player_white"]]
        if not all(value is None or isinstance(value, str) for value in (black, white)):
            raise ValueError("invalid player raw value")
        slot_counts.update((black, white))
        game_counts.update({black, white})

    if (len(set(album_ids)) != count or len(set(scope_ids)) != count or len(set(detail_ids)) != count
            or set(album_ids) != set(scope_ids) or set(album_ids) != set(detail_ids)):
        raise ValueError("duplicate or missing album in player inventory")

    seen = set()
    for item in summary:
        if not isinstance(item, dict) or not {"value", "occurrences", "affected_games"}.issubset(item):
            raise ValueError("invalid player summary row")
        value = item["value"]
        if value is not None and not isinstance(value, str):
            raise ValueError("invalid player summary value")
        if value in seen:
            raise ValueError("duplicate player summary value")
        seen.add(value)
        if (item["occurrences"] != slot_counts[value]
                or item["affected_games"] != game_counts[value]):
            raise ValueError("player summary does not match album slots")
    if seen != set(slot_counts) or sum(slot_counts.values()) != count * 2:
        raise ValueError("incomplete player summary")

    rows = []
    for raw_value in sorted((value for value in slot_counts if value is not None), key=lambda value: value.encode("utf-8")):
        parsed = parse_player(raw_value, None)
        rows.append({
            "raw_value": raw_value,
            "category": parsed.category,
            "parsed_data": {
                "name": parsed.name,
                "base_name": parsed.name,
                "embedded_rank": parsed.embedded_rank,
                "slot_count": slot_counts[raw_value],
                "occurrences": slot_counts[raw_value],
                "affected_games": game_counts[raw_value],
                "confidence": parsed.confidence,
                "exceptions": list(parsed.exceptions),
            },
            "parser_version": PLAYER_PARSER_VERSION,
        })
    return rows


def upsert_player_raw_values(db, rows: list[dict]) -> dict[str, int]:
    """Write prepared rows in the caller's transaction; preserve reviewed rows."""
    table = KifuRawPlayerValue.__table__
    raw_values = [row["raw_value"] for row in rows]
    if len(raw_values) != len(set(raw_values)) or any(not isinstance(value, str) for value in raw_values):
        raise ValueError("prepared player rows require distinct non-null raw values")

    existing = {}
    for offset in range(0, len(raw_values), 500):
        chunk = raw_values[offset:offset + 500]
        for stored in db.execute(select(
            table.c.raw_value, table.c.category, table.c.parsed_data,
            table.c.parser_version, table.c.review_status,
        ).where(table.c.raw_value.in_(chunk))).mappings():
            existing[stored["raw_value"]] = stored

    result = {"inserted": 0, "updated": 0, "unchanged": 0, "protected": 0}
    inserts = []
    for row in rows:
        raw_value = row["raw_value"]
        stored = existing.get(raw_value)
        if stored is None:
            inserts.append({key: row[key] for key in ("raw_value", "category", "parsed_data", "parser_version")})
            continue
        if stored["review_status"] != "pending" or stored["parser_version"] != PLAYER_PARSER_VERSION:
            result["protected"] += 1
            continue
        changes = {key: row[key] for key in ("category", "parsed_data", "parser_version") if stored[key] != row[key]}
        if changes:
            updated = db.execute(table.update().where(
                table.c.raw_value == raw_value,
                table.c.review_status == "pending",
                table.c.parser_version == PLAYER_PARSER_VERSION,
            ).values(**changes))
            if updated.rowcount != 1:
                raise ValueError("raw player review changed during staging")
            result["updated"] += 1
        else:
            result["unchanged"] += 1
    if inserts:
        db.execute(table.insert(), inserts)
    result["inserted"] = len(inserts)
    return result
