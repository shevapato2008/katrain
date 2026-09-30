"""The audited kifu name seed is separate from the live-match translations."""

import json
from pathlib import Path

import pytest

from scripts.seed_kifu_translations import (
    LANGUAGES,
    coverage,
    display_name,
    inventory_from_database,
    load_seed,
    validate_seed,
)


SEED_PATH = Path(__file__).resolve().parents[2] / "docs" / "resource" / "kifu-name-seed.json"


def test_seed_has_eleven_languages_and_audited_historical_names():
    seed = load_seed(SEED_PATH)
    assert seed["languages"] == list(LANGUAGES)
    assert validate_seed(seed) == []

    assert display_name(seed, "player", "Go Seigen", "cn") == "吴清源"
    assert display_name(seed, "player", "吴清源", "en") == "Go Seigen"
    assert display_name(seed, "player", "Honinbo Dosaku", "cn") == "本因坊道策"
    assert display_name(seed, "player", "unlisted player", "ru") == "unlisted player"
    expected = {
        "en": "Go Seigen",
        "cn": "吴清源",
        "tw": "吳清源",
        "jp": "呉清源",
        "de": "Go Seigen",
        "fr": "Go Seigen",
    }
    for lang in LANGUAGES:
        assert display_name(seed, "player", "吴清源", lang) == expected.get(lang, "吴清源")
    assert display_name(seed, "event", "吴清源杯", "en") == "Wu Qingyuan Cup"
    assert display_name(seed, "event", "吴清源杯", "ru") == "吴清源杯"
    assert display_name(seed, "event", "Oteai", "jp") == "大手合"
    assert display_name(seed, "event", "大手合", "en") == "Oteai"


def test_unsupported_or_unverified_translation_falls_back_to_original():
    seed = {
        "schema_version": 1,
        "languages": list(LANGUAGES),
        "entities": [
            {
                "key": "player:example",
                "kind": "player",
                "canonical": "Example",
                "aliases": ["例子"],
                "names": {"ru": {"value": "Пример", "status": "review", "source_url": "https://example.org/p"}},
            }
        ],
    }
    assert display_name(seed, "player", "例子", "ru") == "例子"
    assert display_name(seed, "player", "例子", "de") == "例子"
    assert display_name(seed, "player", "例子", "xx") == "例子"


def test_repeating_one_alias_within_an_entity_does_not_make_it_ambiguous():
    seed = load_seed(SEED_PATH)
    seed["entities"][0]["aliases"].append("Go Seigen")
    seed["entities"][0]["alias_sources"]["Go Seigen"] = "https://en.wikipedia.org/wiki/Go_Seigen"
    assert display_name(seed, "player", "Go Seigen", "cn") == "吴清源"


def test_validation_rejects_unattributed_verified_names_and_alias_collisions():
    seed = load_seed(SEED_PATH)
    bad = json.loads(json.dumps(seed))
    bad["entities"][0]["names"]["en"]["source_url"] = ""
    bad["entities"][1]["aliases"].append("Go Seigen")
    problems = validate_seed(bad)
    assert any("source_url" in problem for problem in problems)
    assert any("alias" in problem for problem in problems)


def test_coverage_counts_distinct_original_names_and_reports_fallbacks():
    seed = load_seed(SEED_PATH)
    inventory = [
        {"kind": "player", "name": "Go Seigen"},
        {"kind": "player", "name": "Go Seigen"},
        {"kind": "player", "name": "unknown"},
        {"kind": "event", "name": "unknown event"},
    ]
    report = coverage(seed, inventory)
    assert report["player"]["distinct_names"] == 2
    assert report["player"]["linked"] == 1
    assert report["player"]["linked_rate"] == 0.5
    assert report["player"]["languages"]["cn"]["verified"] == 1
    assert report["player"]["languages"]["cn"]["verified_rate"] == 0.5
    assert report["player"]["languages"]["ru"]["fallback_total"] >= 1
    assert report["event"]["distinct_names"] == 1
    assert report["event"]["languages"]["en"]["fallback_total"] == 1


def test_coverage_rejects_invalid_inventory_kind():
    with pytest.raises(ValueError, match="kind"):
        coverage(load_seed(SEED_PATH), [{"kind": "round", "name": "Final"}])


def test_database_inventory_reads_all_distinct_raw_names(tmp_path):
    import sqlite3

    db_path = tmp_path / "album.sqlite"
    with sqlite3.connect(db_path) as db:
        db.execute("CREATE TABLE kifu_albums (player_black TEXT, player_white TEXT, event TEXT)")
        db.executemany(
            "INSERT INTO kifu_albums VALUES (?, ?, ?)",
            [("Go Seigen", "Kitani Minoru", "吴清源杯"), ("Go Seigen", "", None)],
        )

    inventory = inventory_from_database(f"sqlite:///{db_path}")
    assert {tuple(item.values()) for item in inventory} == {
        ("player", "Go Seigen"),
        ("player", "Kitani Minoru"),
        ("event", "吴清源杯"),
    }


def test_cli_validation_without_inventory_does_not_claim_zero_coverage(monkeypatch, capsys):
    from scripts.seed_kifu_translations import main

    monkeypatch.setattr("sys.argv", ["seed_kifu_translations.py"])
    assert main() == 0
    report = json.loads(capsys.readouterr().out)
    assert report["seed_entities"] == 7
    assert report["coverage"] is None
