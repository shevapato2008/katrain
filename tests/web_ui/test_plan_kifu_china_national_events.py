import gzip
import json
from pathlib import Path

from scripts.plan_kifu_china_national_events import edition_for, select_group


ROOT = Path(__file__).resolve().parents[2]


def _plan(group, environment):
    path = ROOT / f"docs/resource/kifu-china-national-{group}-{environment}-plan-2026-10-04.json.gz"
    return json.loads(gzip.decompress(path.read_bytes()))


def test_personal_team_and_league_identities_are_separate():
    assert select_group("2019梦想天地第53届中国全国个人赛男子组第7轮") == "individual"
    assert select_group("ChineseNationalTeamTournament(Women)") == "team"
    assert select_group("1996中国围棋团体赛男子甲组第10轮") == "team"
    assert select_group("2022中国围棋甲级联赛第7轮") is None
    assert select_group("个人赛") is None
    assert select_group("团体赛") is None


def test_only_reliable_years_receive_edition_keys():
    assert edition_for("2019梦想天地第53届中国全国个人赛男子组第7轮", "2019-09-23", "individual") == ["year", 2019]
    assert edition_for("2022年中国全国围棋个人赛女子组第1轮", "2023-09-09", "individual") is None
    assert edition_for("中国围棋全国个人赛", "1988-09-01", "individual") is None
    assert edition_for("1985ChineseNationalTeamChampionships", "1985-05-05", "team") == ["year", 1985]
    assert edition_for("ChineseNationalTeamTournament(Women)", "1989-04-01", "team") is None


def test_frozen_plans_have_exact_disjoint_albums_and_type_only_holds():
    expected = {"individual": (87, 670, 359, 311), "team": (21, 419, 92, 327)}
    for environment in ("test", "prod"):
        plans = {group: _plan(group, environment) for group in expected}
        for group, (raw_values, albums, years, type_only) in expected.items():
            rows = plans[group]["albums"]
            assert len(plans[group]["raw_counts"]) == raw_values
            assert len(rows) == albums
            assert sum(row[3] is not None for row in rows) == years
            assert sum(row[3] is None for row in rows) == type_only
            assert all(len(row) == 5 for row in rows)
            assert all("比赛说明" not in row[1] for row in rows)
        assert {row[0] for row in plans["individual"]["albums"]}.isdisjoint(
            {row[0] for row in plans["team"]["albums"]}
        )


def test_team_review_holds_preserve_full_aggregate_raw_count():
    for environment in ("test", "prod"):
        plan = _plan("team", environment)
        assert {68822, 75789}.isdisjoint(row[0] for row in plan["albums"])
        assert "2000年中国围棋团体赛" not in plan["raw_counts"]
        assert all(row[1] != "2000年中国围棋团体赛" for row in plan["albums"])
        assert plan["raw_counts"]["中国围棋团体赛"] == 243
        assert sum(row[1] == "中国围棋团体赛" for row in plan["albums"]) == 242
