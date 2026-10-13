"""Finite, reviewed raw-player display membership shared by import and reads."""

from dataclasses import dataclass

from katrain.web.kifu.name_evidence import EvidenceError, validate_transliteration_review


CONTEXT_FIELDS = (
    "duplicate_of_id", "player_black", "player_white", "event", "round_name",
    "black_rank", "white_rank", "date_played", "black_player_id", "white_player_id", "event_id",
)


@dataclass(frozen=True)
class PreparedRawPlayerScope:
    raw_value: str
    members: dict[tuple[int, str], dict]


def prepare_raw_player_scope(scope):
    """Verify one persisted signature, then index its finite slots for a read."""
    content = validate_transliteration_review(scope, "approved_raw_display_scope")
    members = content.get("slots")
    if not isinstance(members, list) or not members or not isinstance(content.get("raw_value"), str):
        raise EvidenceError("raw-player display scope is incomplete")
    indexed = {}
    for member in members:
        if not isinstance(member, dict) or set(member) != {"album_id", "slot", "context"}:
            raise EvidenceError("raw-player display slot invalid")
        album_id, slot, context = member["album_id"], member["slot"], member["context"]
        if (type(album_id) is not int or slot not in {"black", "white"}
                or not isinstance(context, dict) or set(context) != set(CONTEXT_FIELDS)
                or context[f"player_{slot}"] != content["raw_value"]
                or context[f"{slot}_player_id"] is not None or (album_id, slot) in indexed):
            raise EvidenceError("raw-player display slot context invalid")
        indexed[(album_id, slot)] = context
    return PreparedRawPlayerScope(content["raw_value"], indexed)


def validate_raw_player_scope(scope, inventory_sha256, raw_value, eligible_slots, contexts):
    """Check a signed subset of exact, unlinked slots in the pinned inventory."""
    content = validate_transliteration_review(scope, "approved_raw_display_scope")
    if (content.get("inventory_sha256") != inventory_sha256 or content.get("raw_value") != raw_value
            or not isinstance(content.get("applicability_basis"), str)
            or not content["applicability_basis"].strip()
            or not isinstance(content.get("slots"), list) or not content["slots"]):
        raise EvidenceError("raw-player scope inventory, spelling or slots invalid")
    seen = set()
    for member in content["slots"]:
        if not isinstance(member, dict) or set(member) != {"album_id", "slot", "context"}:
            raise EvidenceError("raw-player scope member invalid")
        album_id, slot = member["album_id"], member["slot"]
        key = (album_id, slot)
        context = member["context"]
        if (type(album_id) is not int or key in seen or key not in eligible_slots
                or not isinstance(context, dict) or set(context) != set(CONTEXT_FIELDS)
                or context != contexts.get(album_id)
                or context[f"player_{slot}"] != raw_value or context[f"{slot}_player_id"] is not None):
            raise EvidenceError("raw-player scope member differs from unlinked inventory slot")
        seen.add(key)
    if content["slots"] != sorted(content["slots"], key=lambda member: (member["album_id"], member["slot"])):
        raise EvidenceError("raw-player scope slots must be sorted")
    return content


def raw_player_scope_slot(scope, album, slot, raw_value):
    """Fail closed when a signed member or any bound album context has drifted."""
    if slot not in {"black", "white"}:
        return False
    try:
        prepared = scope if isinstance(scope, PreparedRawPlayerScope) else prepare_raw_player_scope(scope)
        if prepared.raw_value != raw_value or getattr(album, f"{slot}_player_id") is not None:
            return False
        return prepared.members.get((album.id, slot)) == {field: getattr(album, field) for field in CONTEXT_FIELDS}
    except (EvidenceError, KeyError, TypeError, AttributeError):
        return False
