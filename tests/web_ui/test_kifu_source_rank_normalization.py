"""Source convention is authority only through an exact trusted album link."""

from copy import deepcopy
from hashlib import sha256

import pytest


def policy(raw, source):
    from katrain.web.kifu.source_rank_normalization import normalize_source_rank

    return normalize_source_rank(raw, source_key=source)


@pytest.mark.parametrize(
    "raw,source,display,system",
    [
        ("7d", "CWI", "7段", "dan_unspecified"),
        ("7dan", "CWI", "7段", "dan_unspecified"),
        ("7d", None, "7段", "dan_unspecified"),
        ("7d", "19x19", "7d", "amateur_dan"),
        ("7p", "19x19", "7p", "professional_dan"),
        ("七段", "19x19", "7段", "dan_unspecified"),
        ("6d ama", "CWI", "6d", "amateur_dan"),
        ("1k ama", "CWI", "1k", "kyu"),
        ("业余六段", "CWI", "6d", "amateur_dan"),
        ("1k", "CWI", "1k", "kyu"),
    ],
)
def test_source_policy(raw, source, display, system):
    assert policy(raw, source) == {"display_rank": display, "rank_value": int(display[0]), "rank_system": system}


def test_qualifiers_and_insei_never_become_professional():
    assert policy("provisional 3d", "CWI") is None
    assert policy("7d & 7d", "CWI") is None
    assert policy("院生", "19x19") is None


def test_bound_snapshot_uppercase_nested_date_path_and_spoof_refusal():
    from katrain.web.kifu.source_rank_normalization import build_source_snapshot, validate_source_snapshot

    album = {
        "id": 9,
        "source_path": "data/kifu-album/Go_Seigen/1989/1989-01-17.SGF",
        "sgf_content": "(;PB[Yoda]PW[Go]BR[7d]WR[9d];B[aa])",
        "black_rank": "7d",
        "black_player_id": None,
    }
    link = {
        "id": 4,
        "album_id": 9,
        "source_id": 2,
        "source_key": "CWI",
        "origin_path": album["source_path"],
        "match_method": "source_path",
    }
    snapshot = build_source_snapshot(album, "black", link)
    assert snapshot["display_rank"] == "7段"
    assert validate_source_snapshot(snapshot, album=album, side="black", source_links=[link]) == snapshot
    for field, value in [
        ("id", 10),
        ("black_rank", "8d"),
        ("sgf_content", "(;BR[7d])"),
        ("black_player_id", 57),
        ("source_path", "forged"),
    ]:
        damaged = {**album, field: value}
        with pytest.raises(ValueError):
            validate_source_snapshot(snapshot, album=damaged, side="black", source_links=[link])
    for field, value in [("source_key", "19x19"), ("id", 5), ("album_id", 10), ("origin_path", "forged")]:
        with pytest.raises(ValueError):
            validate_source_snapshot(snapshot, album=album, side="black", source_links=[{**link, field: value}])
    with pytest.raises(ValueError):
        build_source_snapshot(album, "black", {**link, "source_key": "19x19"})


@pytest.mark.parametrize(
    "raw,expected,system",
    [
        ("7p", "7p", "professional_dan"),
        ("7d", "7d", "amateur_dan"),
        ("1k", "1k", "kyu"),
        ("业余六段", "6d", "amateur_dan"),
        ("6d ama", "6d", "amateur_dan"),
    ],
)
def test_future_starpoint_ingestion_uses_known_source_policy(raw, expected, system):
    from katrain.kifu_ingest.ranks import (
        freeze_game_ranks,
        validate_manifest_ranks,
        display_rank_for_game_slot,
        FORMAT_V2,
    )
    from tests.test_kifu_rank_freeze import game

    item = game(raw_rank=raw)
    frozen = freeze_game_ranks(item)
    snapshot = frozen["rank_snapshots"]["black"]
    validate_manifest_ranks(
        {
            "format": FORMAT_V2,
            "games": [
                {**item, "rank_snapshots": frozen["rank_snapshots"], "rank_observations": frozen["rank_observations"]}
            ],
            "rank_facts": frozen["rank_facts"],
        }
    )
    assert snapshot["rank_system"] == system
    assert display_rank_for_game_slot(snapshot, raw)["rank"] == expected


def test_future_starpoint_snapshot_cannot_relabel_explicit_amateur():
    from katrain.kifu_ingest.ranks import freeze_game_ranks, snapshot_sha256, validate_rank_snapshot
    from tests.test_kifu_rank_freeze import game

    snapshot = freeze_game_ranks(game(raw_rank="6d ama"))["rank_snapshots"]["black"]
    snapshot.update(display_rank="6p", rank_system="professional_dan")
    snapshot["content_sha256"] = snapshot_sha256(snapshot)
    with pytest.raises(ValueError):
        validate_rank_snapshot(snapshot)
