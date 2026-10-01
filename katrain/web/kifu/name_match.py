"""Conservative album identity proposals from an immutable name inventory.

An exact, unique alias is still only a proposal. Identity evidence, date/sponsor
checks and review happen before any database link is changed.
"""

from collections import defaultdict
from collections.abc import Iterable, Iterator, Mapping
import re

from katrain.web.kifu.identity import normalize_alias
from katrain.web.kifu.name_parse import parse_event, parse_player
from katrain.web.kifu.name_structure import structure_event


def _alias_index(aliases: Mapping[str, Iterable[int]]) -> dict[str, set[int]]:
    result: dict[str, set[int]] = defaultdict(set)
    for spelling, entity_ids in aliases.items():
        key = normalize_alias(spelling)
        if key:
            result[key].update(entity_ids)
    return result


def _status(existing_id: int | None, candidates: list[int], *, excluded: str | None) -> str:
    if excluded:
        return excluded
    if existing_id is not None:
        if candidates and candidates != [existing_id]:
            return "existing_link_conflict"
        return "existing_link"
    if len(candidates) > 1:
        return "ambiguous"
    if candidates:
        return "review_candidate"
    return "raw_display_required"


def propose_album_matches(
    inventory: dict,
    *,
    player_aliases: Mapping[str, Iterable[int]],
    event_aliases: Mapping[str, Iterable[int]],
) -> Iterator[dict]:
    """Yield one read-only proposal per black, white and event slot.

    Alias maps must contain only independently sourced candidate aliases. Even
    a unique match remains pending review, because date, opponent and historical
    tournament identity can disambiguate otherwise identical spellings.
    """
    columns = inventory["association_columns"]
    required = {
        "id", "player_black", "player_white", "event", "round_name",
        "black_rank", "white_rank", "date_played",
        "black_player_id", "white_player_id", "event_id",
    }
    if inventory.get("inventory_format") != 2 or not required.issubset(columns):
        raise ValueError("inventory_format 2 with date, round and ranks is required")
    player_index = _alias_index(player_aliases)
    event_index = _alias_index(event_aliases)
    for values in inventory["album_associations"]:
        album = dict(zip(columns, values))
        for side, raw_field, rank_field, id_field in (
            ("black", "player_black", "black_rank", "black_player_id"),
            ("white", "player_white", "white_rank", "white_player_id"),
        ):
            raw = album[raw_field]
            parsed = parse_player(raw, album[rank_field])
            excluded = (
                "corrupt_pending" if parsed.category == "corrupt_pending"
                else "non_identity" if parsed.category == "placeholder"
                else None
            )
            ids = sorted(player_index.get(normalize_alias(parsed.name), ())) if not excluded else []
            yield {
                "album_id": album["id"],
                "side": side,
                "raw_value": raw,
                "lookup_name": parsed.name,
                "parsed_rank": parsed.embedded_rank,
                "existing_id": album[id_field],
                "candidate_ids": ids,
                "status": _status(album[id_field], ids, excluded=excluded),
                "exceptions": list(parsed.exceptions),
            }

        raw = album["event"]
        parsed = parse_event(raw, None)
        structure = structure_event(raw or "")
        non_events = {"empty", "program_source_label", "generic_event_description", "game_description"}
        if parsed.category == "corrupt_data":
            excluded = "corrupt_pending"
        elif parsed.category in non_events:
            excluded = "non_identity"
        else:
            excluded = None
        lookup = parsed.event_candidate or structure["core"] or raw or ""
        ids = sorted(event_index.get(normalize_alias(lookup), ())) if not excluded else []
        exceptions = list(parsed.exceptions)
        if structure["grammar"] != "unparsed":
            exceptions.append("family_identity_review")
        components = {part["kind"]: part["value"] for part in structure["components"]}
        date = album["date_played"] or ""
        date_year = re.fullmatch(r"([12]\d{3})(?:-\d{2}-\d{2})?", date)
        if components.get("year") and date_year and components["year"] != date_year.group(1):
            exceptions.append("event_year_date_mismatch")
        round_season = re.search(r"\b(Spring|Fall)\b", album["round_name"] or "", re.IGNORECASE)
        if (
            components.get("season")
            and round_season
            and components["season"].casefold() != round_season.group(1).casefold()
        ):
            exceptions.append("event_season_round_mismatch")
        yield {
            "album_id": album["id"],
            "side": "event",
            "raw_value": raw,
            "lookup_name": lookup,
            "components": {"year": components.get("year"), "season": components.get("season")},
            "structure": structure,
            "existing_id": album["event_id"],
            "candidate_ids": ids,
            "status": _status(album["event_id"], ids, excluded=excluded),
            "exceptions": exceptions,
        }
