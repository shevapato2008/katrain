"""Dataset provenance and conservative SGF duplicate evidence."""

import hashlib

from sqlalchemy.orm import Session

from katrain.core.sgf_parser import SGF
from katrain.web.core.models_db import (
    KifuAlbumSource,
    KifuEventAlias,
    KifuEventName,
    KifuPlayerAlias,
    KifuPlayerName,
    KifuSource,
)
from katrain.web.kifu.identity import normalize_alias


_CWI_FOLDERS = frozenset({"cwi_history_full", "cwi_1950_1978", "cwi_dosaku", "cwi_jowa", "cwi_shusaku", "go_seigen"})


def classify_source_path(source_path: str | None) -> str:
    """Classify only explicit dataset folders; SGF SO/US is not a dataset."""
    parts = (source_path or "").replace("\\", "/").casefold().split("/")
    try:
        folder = parts[parts.index("kifu-album") + 1]
    except (ValueError, IndexError):
        return "unknown"
    if folder in _CWI_FOLDERS:
        return "CWI"
    if folder == "19x19":
        return "19x19"
    return "unknown"


def sgf_sha256(sgf_content: str) -> str:
    return hashlib.sha256(sgf_content.encode("utf-8")).hexdigest()


def audited_alias_ids(db: Session) -> dict[str, dict[str, int | None]]:
    """Load aliases for imports; None marks a conflicting or unapproved alias."""
    result = {}
    for kind, alias_model, name_model, fk in (
        ("player", KifuPlayerAlias, KifuPlayerName, "player_id"),
        ("event", KifuEventAlias, KifuEventName, "event_id"),
    ):
        approved_ids = {
            row[0]
            for row in db.query(getattr(name_model, fk)).filter(
                name_model.status == "verified", name_model.reference_url.isnot(None)
            )
        }
        alias_ids: dict[str, set[int]] = {}
        for alias, entity_id in db.query(alias_model.normalized_alias, getattr(alias_model, fk)):
            alias_ids.setdefault(normalize_alias(alias), set()).add(entity_id)
        result[kind] = {}
        for alias, ids in alias_ids.items():
            entity_id = next(iter(ids)) if len(ids) == 1 else None
            result[kind][alias] = entity_id if entity_id in approved_ids else None
    return result


def mainline_signature(sgf_content: str) -> str | None:
    """Candidate evidence only: metadata and setup may differ."""
    root = SGF.parse_sgf(sgf_content)
    moves = []
    node = root
    while node.children:
        node = node.children[0]
        if node.move:
            moves.append(str(node.move))
    if len(moves) < 30:
        return None
    value = f"{root.board_size};" + ";".join(moves)
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def ensure_album_source(db: Session, album_id: int, origin_path: str, match_method: str) -> bool:
    """Add one idempotent provenance link; return whether it was created."""
    source_key = classify_source_path(origin_path)
    source = db.query(KifuSource).filter_by(source_key=source_key).one_or_none()
    if source is None:
        source = KifuSource(source_key=source_key, display_name=source_key)
        db.add(source)
        db.flush()
    existing = (
        db.query(KifuAlbumSource.id).filter_by(album_id=album_id, source_id=source.id, origin_path=origin_path).first()
    )
    if existing:
        return False
    db.add(KifuAlbumSource(album_id=album_id, source_id=source.id, origin_path=origin_path, match_method=match_method))
    db.flush()
    return True


def source_links_snapshot(db: Session, album_id: int) -> list[dict]:
    rows = db.query(KifuAlbumSource).filter_by(album_id=album_id).all()
    return sorted(
        (
            {"source_id": row.source_id, "origin_path": row.origin_path, "match_method": row.match_method}
            for row in rows
        ),
        key=lambda item: (item["source_id"], item["origin_path"], item["match_method"]),
    )
