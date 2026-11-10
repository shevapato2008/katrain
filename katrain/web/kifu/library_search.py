"""Small, conservative candidates for the existing kifu library reader."""

from sqlalchemy import func, literal, or_

from katrain.web.core.models_db import (
    KifuAlbumEventSelection,
    KifuEventName,
    KifuPlayer,
    KifuPlayerName,
    KifuRawEventName,
    KifuRawPlayerName,
)
from katrain.web.kifu.identity import (
    PRIMARY_NAME_LANGUAGES,
    _approved_names,
    _qualified_name_rows,
    matching_entity_ids,
    normalize_alias,
)

# The archive uses Japanese romanizations while many kiosk users search in Chinese.
HISTORICAL_PLAYER_ALIASES = {
    "吴清源": ("go seigen",),
    "吳清源": ("吴清源", "go seigen"),
    "道策": ("honinbo dosaku",),
    "丈和": ("honinbo jowa", "kadono jowa", "kadono matsunosuke", "todani matsunosuke"),
    "秀策": ("shusaku", "yasuda eisai"),
    "木谷实": ("kitani minoru",),
    "木谷實": ("木谷实", "kitani minoru"),
}


def unique_exact_player_id(db, query: str, *, strict: bool, orthographic_batch_contexts=None) -> int | None:
    """Prove the current exact-player case without loading unrelated proof JSON.

    Potential collisions deliberately fall back to the complete reader. Legacy
    aliases retain that reader unless their exact expansion is the same owner.
    """
    if not normalize_alias(query):
        return None
    candidates = []
    for kind, model, owner in (
        ("player", KifuPlayerName, "player_id"),
        ("event", KifuEventName, "event_id"),
        ("raw_player", KifuRawPlayerName, "raw_player_id"),
        ("raw_event", KifuRawEventName, "raw_event_id"),
    ):
        candidates.append(
            _approved_names(db, model, owner)
            .filter(or_(model.display_name == query, func.lower(model.display_name) == query.lower()))
            .with_entities(
                literal(kind).label("kind"), model.id.label("name_id"), getattr(model, owner).label("owner_id")
            )
        )
    rows = candidates[0].union_all(*candidates[1:]).all()
    player_ids = {row.owner_id for row in rows if row.kind == "player"}
    if len(player_ids) != 1 or any(row.kind != "player" for row in rows):
        return None
    player_id = next(iter(player_ids))
    names = _approved_names(db, KifuPlayerName, "player_id", {player_id}).filter(
        KifuPlayerName.id.in_([row.name_id for row in rows])
    )
    qualified = _qualified_name_rows(
        db, names, KifuPlayerName, "player_id", orthographic_batch_contexts=orthographic_batch_contexts
    )
    needle = normalize_alias(query)
    if not any(normalize_alias(name.display_name) == needle for name, _ in qualified):
        return None
    if not strict:
        legacy_players, legacy_events = matching_entity_ids(
            db, query, exact=True, orthographic_batch_contexts=orthographic_batch_contexts
        )
        if legacy_events or legacy_players - {player_id}:
            return None
        # This is exactly the old `exact_player` case. That case already skips
        # provisional and historical hints, so those cannot add omitted albums.
    # This includes stale/unapproved selections: only the full selected-event
    # reader can decide that they are ineligible, so never skip it on a guess.
    if (
        db.query(KifuAlbumEventSelection.album_id)
        .filter(KifuAlbumEventSelection.selected_raw.contains(query, autoescape=True))
        .first()
        is not None
    ):
        return None
    return player_id


def public_player_id(db, player_id: int, *, orthographic_batch_contexts=None) -> bool:
    """An explicit identity is public only with a currently qualified primary name."""
    names = (
        _approved_names(db, KifuPlayerName, "player_id", {player_id})
        .join(KifuPlayer, KifuPlayer.id == KifuPlayerName.player_id)
        .filter(
            KifuPlayerName.lang.in_(PRIMARY_NAME_LANGUAGES),
            KifuPlayerName.decision_kind.notin_({"hidden", "error", "placeholder"}),
            func.length(func.trim(KifuPlayerName.display_name)) > 0,
        )
    )
    return bool(
        _qualified_name_rows(
            db, names, KifuPlayerName, "player_id", orthographic_batch_contexts=orthographic_batch_contexts
        )
    )
