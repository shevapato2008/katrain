"""Build a real reviewed duplicate-GN selection for catalog tests."""

from sqlalchemy import select

from katrain.core.sgf_parser import SGF
from katrain.web.core.models_db import KifuAlbum
from katrain.web.kifu.event_selection import RULE_VERSION, apply_bundle, selected_second_gn
from katrain.web.kifu.name_candidates import canonical_sha256
from katrain.web.kifu.provenance import classify_source_path, sgf_sha256


def apply_reviewed_selection(engine, album_id: int) -> dict:
    with engine.connect() as conn:
        album = conn.execute(select(KifuAlbum.__table__).where(KifuAlbum.id == album_id)).mappings().one()
    raw = selected_second_gn(SGF.parse_sgf(album["sgf_content"]), classify_source_path(album["source_path"]))
    assert raw is not None
    member = {
        "album_id": album_id,
        "old_event": album["event"],
        "old_event_id": album["event_id"],
        "old_source": album["source"],
        "old_source_path": album["source_path"],
        "old_date_played": album["date_played"],
        "old_round_name": album["round_name"],
        "old_board_size": album["board_size"],
        "sgf_sha256": sgf_sha256(album["sgf_content"]),
        "property_name": "GN",
        "property_index": 1,
        "selected_raw": raw,
        "rule_version": RULE_VERSION,
    }
    member_hash = canonical_sha256([member])
    review = {
        "reviewer_id": "fixture-reviewer",
        "reviewer_model": "gpt-6-astra",
        "reviewed_at": "2026-10-02T11:00:00Z",
        "review_conclusion": "approved_second_gn_selection",
        "evidence_scope": {
            "member_set_sha256": member_hash,
            "album_count": 1,
            "reviewed_material": "Pinned SGF and exact duplicate-GN source preimage",
        },
        "status": "approved",
        "member_set_sha256": member_hash,
        "basis": "Fixture reviewed exact second GN and matching GC",
    }
    review["review_signature"] = canonical_sha256(review)
    bundle = {
        "selection_format": 1,
        "rule_version": RULE_VERSION,
        "members": [member],
        "member_set_sha256": member_hash,
        "producer_id": "fixture-producer",
        "producer_model": "gpt-6-luna",
        "produced_at": "2026-10-02T10:00:00Z",
        "scope_frozen_at": "2026-10-02T10:30:00Z",
        "review": review,
    }
    return apply_bundle(engine, bundle, expected_bundle_sha256=canonical_sha256(bundle))
