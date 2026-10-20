"""Pure album metadata derivation shared by staging and publication validation."""

from __future__ import annotations

import re
import math

from katrain.core.sgf_parser import SGF
from katrain.web.kifu.event_selection import selected_second_gn
from katrain.web.kifu.name_parse import parse_player


def normalize_date(raw_date):
    if not raw_date:
        return None
    match = re.search(r"(?<!\d)(\d{4})(?:-(\d{2}))?(?:-(\d{2}))?", str(raw_date))
    return f"{match[1]}-{match[2] or '00'}-{match[3] or '00'}" if match else None


def _search_text(data):
    fields = (
        "player_black",
        "player_white",
        "black_rank",
        "white_rank",
        "event",
        "result",
        "date_played",
        "place",
        "round_name",
        "source",
    )
    return " ".join(str(data.get(field) or "") for field in fields if data.get(field)).lower()


def _moves(root):
    count = 0
    node = root
    while node.children:
        node = node.children[0]
        if node.move:
            count += 1
    return count


def _source_values(source_metadata):
    if source_metadata is None:
        return {}
    if not isinstance(source_metadata, dict):
        raise ValueError("source metadata must be an object")
    values = {}
    aliases = {
        "player_black": ("player_black", "pb", "blackName"),
        "player_white": ("player_white", "pw", "whiteName"),
        "event": ("event", "gamename"),
        "date_played": ("date_played", "datePlayed"),
        "black_rank": ("black_rank", "br"),
        "white_rank": ("white_rank", "wr"),
        "result": ("result", "re", "gameResult"),
        "place": ("place", "pc"),
        "round_name": ("round_name", "ro"),
        "source": ("source", "so"),
        "rules": ("rules", "ru", "rule"),
        "komi": ("komi", "km"),
        "handicap": ("handicap", "ha"),
        "board_size": ("board_size", "sz", "boardSize"),
    }
    for field, keys in aliases.items():
        candidates = [source_metadata[key] for key in keys if source_metadata.get(key) not in (None, "")]
        if candidates:
            if any(str(value) != str(candidates[0]) for value in candidates[1:]):
                raise ValueError(f"source metadata conflicts within {field}")
            values[field] = candidates[0]
    play_time = source_metadata.get("playTime")
    if "date_played" not in values and isinstance(play_time, dict):
        date = play_time.get("date")
        if isinstance(date, dict) and isinstance(date.get("year"), int):
            values["date_played"] = "-".join(
                [str(date["year"]), *(f"{date[key]:02d}" for key in ("month", "day") if isinstance(date.get(key), int))]
            )
    return values


def _coerce(field, value):
    if field in {"komi"}:
        number = float(value)
        if not math.isfinite(number):
            raise ValueError("komi must be finite")
        return number
    if field in {"handicap", "board_size"}:
        return int(value)
    return str(value)


def derive_metadata(content, source_metadata=None, source_key="19x19"):
    """Preserve SGF text while deriving importer-compatible album columns.

    SGF wins whenever it has a value. A conflicting source value quarantines the
    item; source metadata fills only fields the SGF actually lacks.
    """
    if source_key != "19x19":
        raise ValueError("unsupported source key")
    if not isinstance(content, str):
        raise ValueError("SGF content must be text")
    root = SGF.parse_sgf(content)
    source = _source_values(source_metadata)
    game_names = [value for value in (root.get_list_property("GN") or []) if value]
    selected = selected_second_gn(root, source_key)
    explicit_event = root.get_property("EV")
    if not explicit_event and len(set(game_names)) > 1 and selected is None:
        raise ValueError("ambiguous GN values require explicit selection review")
    event = explicit_event or selected or (game_names[0] if game_names else None)
    sgf = {
        "player_black": root.get_property("PB"),
        "player_white": root.get_property("PW"),
        "black_rank": root.get_property("BR"),
        "white_rank": root.get_property("WR"),
        "event": event,
        "result": root.get_property("RE"),
        "date_played": root.get_property("DT"),
        "place": root.get_property("PC"),
        "komi": root.komi if "KM" in root.properties else None,
        "handicap": root.handicap if "HA" in root.properties else None,
        "board_size": root.board_size[0] if "SZ" in root.properties else None,
        "rules": root.get_property("RU"),
        "round_name": root.get_property("RO"),
        "source": root.get_property("SO") or root.get_property("US"),
    }
    data = {}
    for field, sgf_value in sgf.items():
        source_value = source.get(field)
        if sgf_value not in (None, "") and source_value not in (None, ""):
            if field in {"player_black", "player_white"}:
                slot = field.removeprefix("player_")
                matches = (
                    parse_player(sgf_value, sgf.get(f"{slot}_rank")).name
                    == parse_player(source_value, source.get(f"{slot}_rank")).name
                )
            else:
                matches = _coerce(field, sgf_value) == _coerce(field, source_value)
            if not matches:
                raise ValueError(f"source metadata conflicts with SGF {field}")
        value = sgf_value if sgf_value not in (None, "") else source_value
        if value not in (None, ""):
            data[field] = _coerce(field, value)
    for slot in ("black", "white"):
        field, rank_field = f"player_{slot}", f"{slot}_rank"
        parsed = parse_player(data.get(field), data.get(rank_field))
        if not parsed.name or parsed.category == "corrupt_pending" or "rank_conflict" in parsed.exceptions:
            raise ValueError(f"invalid {slot} player or rank")
        if parsed.display_rank:
            data[rank_field] = parsed.display_rank
    if not data.get("event"):
        raise ValueError("SGF/source lacks event")
    data["date_sort"] = normalize_date(data.get("date_played")) or normalize_date(root.get_property("DTX"))
    data["handicap"] = data.get("handicap", root.handicap)
    data["board_size"] = data.get("board_size", root.board_size[0])
    if data["board_size"] != 19:
        raise ValueError("only 19x19 SGF boards are supported")
    data["move_count"] = _moves(root)
    if source_metadata and source_metadata.get("moveNum") not in (None, ""):
        if int(source_metadata["moveNum"]) != data["move_count"]:
            raise ValueError("source metadata conflicts with SGF move count")
    data["search_text"] = _search_text(data)
    return data
