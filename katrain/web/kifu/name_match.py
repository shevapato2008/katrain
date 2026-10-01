"""Conservative album identity proposals from an immutable name inventory.

An exact, unique alias is still only a proposal. Identity evidence, date/sponsor
checks and review happen before any database link is changed.
"""

from collections import defaultdict
from collections.abc import Iterable, Iterator, Mapping

from katrain.web.kifu.identity import normalize_alias
from katrain.web.kifu.name_parse import parse_event, parse_player


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
    player_index = _alias_index(player_aliases)
    event_index = _alias_index(event_aliases)
    for values in inventory["album_associations"]:
        album = dict(zip(columns, values))
        for side, raw_field, id_field in (
            ("black", "player_black", "black_player_id"),
            ("white", "player_white", "white_player_id"),
        ):
            raw = album[raw_field]
            parsed = parse_player(raw, None)
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
        non_events = {"empty", "program_source_label", "generic_event_description", "game_description"}
        if parsed.category == "corrupt_data":
            excluded = "corrupt_pending"
        elif parsed.category in non_events:
            excluded = "non_identity"
        else:
            excluded = None
        lookup = parsed.event_candidate or raw or ""
        ids = sorted(event_index.get(normalize_alias(lookup), ())) if not excluded else []
        yield {
            "album_id": album["id"],
            "side": "event",
            "raw_value": raw,
            "lookup_name": lookup,
            "components": {"year": parsed.year, "season": parsed.season},
            "existing_id": album["event_id"],
            "candidate_ids": ids,
            "status": _status(album["event_id"], ids, excluded=excluded),
            "exceptions": list(parsed.exceptions),
        }
