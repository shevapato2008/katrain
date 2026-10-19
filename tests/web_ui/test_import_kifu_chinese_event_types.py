from scripts.import_kifu_chinese_event_types import (
    build_china_a_league_plan, build_china_womens_league_plan, build_samsung_cup_plan,
    clean_type, edition_for_row, select_plan,
)


def row(*components):
    return {"structure": {"components": [dict(kind=kind, value=value) for kind, value in components]}}


def split(**overrides):
    return {"year": None, "edition": None, **overrides}


def test_chinese_year_edition_and_english_ordinal_components():
    assert edition_for_row(row(("edition", "第42期")), split()) == (("edition_number", 42), None)
    assert edition_for_row(row(("edition", "四十二届")), split()) == (("edition_number", 42), None)
    assert edition_for_row(row(("edition", "11th")), split()) == (("edition_number", 11), None)
    assert edition_for_row(row(), split(year="2007")) == (("year", 2007), 2007)


def test_selection_keeps_sponsor_and_rejects_stage_or_generic_type():
    assert clean_type("金立手机杯围甲联赛")
    assert clean_type("日本龙星战")
    assert not clean_type("台湾棋王赛初赛胜部")
    assert not clean_type("日本龙星战决胜淘汰赛")
    assert not clean_type("名人战")


def test_existing_only_plan_requires_existing_canonical_ids():
    from scripts.import_kifu_chinese_event_types import EXISTING_CANONICAL_TYPES

    names = sorted(EXISTING_CANONICAL_TYPES | {"台湾海峰杯职业围棋赛"})
    albums = [[i, name, name, None, "2020-01-01"] for i, name in enumerate(names, 1)]
    plan = {"version": 1, "inventory_sha256": "x", "total_albums": len(names),
            "selected_series": names, "series_names": {name: name for name in names},
            "albums": albums, "raw_counts": {name: 1 for name in names}}
    report = {"selected_games_by_type": {name: 1 for name in names}}
    narrowed, result = select_plan(plan, report, "existing-only")
    assert set(narrowed["selected_series"]) == EXISTING_CANONICAL_TYPES
    assert set(narrowed["require_existing_types"]) == EXISTING_CANONICAL_TYPES
    assert result["selected_albums"] == 7


def test_samsung_spellings_share_one_type_and_edition_scope():
    from scripts.import_kifu_chinese_event_types import SAMSUNG_CUP_CANONICAL, SAMSUNG_CUP_SOURCE_TYPES

    names = sorted(SAMSUNG_CUP_SOURCE_TYPES)
    plan = {"version": 1, "inventory_sha256": "x", "total_albums": len(names),
            "selected_series": names, "series_names": {name: name for name in names},
            "albums": [[i, name, name, ["edition_number", 18], "2013-06-01"] for i, name in enumerate(names, 1)],
            "raw_counts": {name: 1 for name in names}}
    report = {"selected_games_by_type": {name: 1 for name in names}}
    narrowed, result = select_plan(plan, report, "samsung-cup")
    assert narrowed["selected_series"] == [SAMSUNG_CUP_CANONICAL]
    assert all(row[2] == SAMSUNG_CUP_CANONICAL for row in narrowed["albums"])
    assert set(narrowed["series_aliases"][SAMSUNG_CUP_CANONICAL]) == SAMSUNG_CUP_SOURCE_TYPES
    assert result["source_type_count"] == 6


def test_china_a_league_merges_sponsors_only_with_matching_explicit_season():
    from scripts.import_kifu_chinese_event_types import CHINA_A_LEAGUE_CANONICAL, CHINA_A_LEAGUE_SOURCE_TYPES

    names = sorted(CHINA_A_LEAGUE_SOURCE_TYPES)
    rows = [[i, name, name, ["year", 2017], "2017-06-01"] for i, name in enumerate(names, 1)]
    rows.append([len(rows) + 1, "华为手机围甲无届次", "华为手机围甲", None, "2017-06-01"])
    plan = {"version": 1, "inventory_sha256": "x", "total_albums": len(rows),
            "selected_series": names, "series_names": {name: name for name in names},
            "albums": rows, "raw_counts": {name: 1 for name in names}}
    inventory = {"association_columns": ["id", "date_played"],
                 "album_associations": [[i, "2017-06-01"] for i in range(1, len(rows) + 1)]}
    narrowed, report = build_china_a_league_plan(plan, inventory)
    assert narrowed["selected_series"] == [CHINA_A_LEAGUE_CANONICAL]
    assert len(narrowed["albums"]) == len(names)
    assert all(row[3] == ["edition_number", 19] for row in narrowed["albums"])
    assert report["held_without_matching_season"] == {"华为手机围甲": 1}


def test_china_womens_league_preserves_sponsor_aliases_and_explicit_edition():
    from scripts.import_kifu_chinese_event_types import CHINA_WOMENS_LEAGUE_CANONICAL, CHINA_WOMENS_LEAGUE_SOURCE_TYPES

    names = sorted(CHINA_WOMENS_LEAGUE_SOURCE_TYPES)
    plan = {"version": 1, "inventory_sha256": "x", "total_albums": len(names),
            "selected_series": names, "series_names": {name: name for name in names},
            "albums": [[i, name, name, ["edition_number", 12], "2025-06-01"] for i, name in enumerate(names, 1)],
            "raw_counts": {name: 1 for name in names}}
    inventory = {"association_columns": ["id", "date_played"],
                 "album_associations": [[i, "2025-06-01"] for i in range(1, len(names) + 1)]}
    narrowed, report = build_china_womens_league_plan(plan, inventory)
    assert len(narrowed["albums"]) == len(names)
    assert narrowed["selected_series"] == [CHINA_WOMENS_LEAGUE_CANONICAL]
    assert set(narrowed["series_aliases"][CHINA_WOMENS_LEAGUE_CANONICAL]) == CHINA_WOMENS_LEAGUE_SOURCE_TYPES
    assert report["held_without_matching_edition"] == {}


def test_samsung_cup_holds_wrong_edition_but_keeps_type_link():
    from scripts.import_kifu_chinese_event_types import SAMSUNG_CUP_CANONICAL, SAMSUNG_CUP_SOURCE_TYPES

    names = sorted(SAMSUNG_CUP_SOURCE_TYPES)
    rows = [[i, name, name, ["edition_number", 1], "1996-06-01"] for i, name in enumerate(names, 1)]
    rows.extend([[30426, "第5届三星杯预选", "三星杯", ["edition_number", 5], "2003-06-22"],
                 [40000, "2003三星杯半决赛第二局", "三星杯", ["year", 2003], "2003-11-01"]])
    plan = {"version": 1, "inventory_sha256": "x", "total_albums": len(rows),
            "selected_series": names, "series_names": {name: name for name in names},
            "albums": rows, "raw_counts": {name: 1 for name in names}}
    inventory = {"association_columns": ["id", "date_played"],
                 "album_associations": [[i, "1996-06-01"] for i in range(1, len(names) + 1)] +
                                       [[30426, "2003-06-22"], [40000, "2003-11-01"]]}
    narrowed, report = build_samsung_cup_plan(plan, {"selected_games_by_type": {name: 1 for name in names}}, inventory)
    assert narrowed["selected_series"] == [SAMSUNG_CUP_CANONICAL]
    assert narrowed["albums"][-2][3] is None
    assert narrowed["albums"][-1][3] == ["edition_number", 8]
    assert report["edition_link_held_games"] == 1
