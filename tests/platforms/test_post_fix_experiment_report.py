from pathlib import Path
import sys

CALIBRATION = (
    Path(__file__).resolve().parents[2]
    / "superpowers"
    / "tracks"
    / "golaxy-ai-ladder-parity"
    / "calibration"
)
sys.path.insert(0, str(CALIBRATION))

from generate_post_fix_experiment_report import (  # noqa: E402
    build_report_data,
    render_report,
)


def _row(rows, player_a, player_b):
    return next(row for row in rows if row["player_a"] == player_a and row["player_b"] == player_b)


def test_report_data_freezes_latest_partial_golaxy_results():
    data = build_report_data()

    sampling = _row(data["golaxy"], "rank_6d@1", "星阵6段")
    assert (sampling["wins"], sampling["losses"], sampling["eligible_games"]) == (6, 3, 9)
    assert sampling["completion_status"] == "partial"

    b18_32 = _row(data["golaxy"], "b18@32", "星阵3星（超越人类）")
    b18_64 = _row(data["golaxy"], "b18@64", "星阵3星（超越人类）")
    assert (b18_32["wins"], b18_32["losses"], b18_32["planned_games"]) == (7, 7, 20)
    assert (b18_64["wins"], b18_64["losses"], b18_64["planned_games"]) == (7, 3, 20)
    assert b18_32["completion_status"] == b18_64["completion_status"] == "stopped"


def test_report_data_contains_all_eight_adjacent_argmax_matchups():
    data = build_report_data()
    rows = [row for row in data["selfplay"] if row["family"] == "相邻段位 argmax"]

    assert [(row["wins"], row["losses"]) for row in rows] == [
        (7, 13),
        (7, 13),
        (4, 16),
        (9, 11),
        (6, 14),
        (9, 11),
        (6, 14),
        (7, 13),
    ]
    assert all(row["complete_pairs"] == 10 for row in rows)


def test_report_keeps_all_four_pikl_40_adjacent_screenings():
    data = build_report_data()
    rows = [row for row in data["selfplay"] if row["family"] == "相邻段位 PIKL@40 筛选"]

    assert [(row["wins"], row["losses"]) for row in rows] == [(19, 1), (19, 1), (17, 3), (16, 4)]
    assert [row["inconclusive_pairs"] for row in rows] == [0, 2, 3, 7]


def test_rendered_report_is_self_contained_table_first_and_honest():
    html = render_report(build_report_data())

    assert "<!doctype html>" in html.lower()
    assert "星阵对局总表" in html
    assert "内部对局总表" in html
    assert "审计附录" in html
    assert "59 / 60" in html
    assert "99 / 100" in html
    assert "职业水平" in html and "职业顶尖" in html and "超越人类" in html
    assert "https://" not in html and "http://" not in html
    assert "<script src=" not in html and 'rel="stylesheet"' not in html
    assert 'rel="icon" href="data:,' in html
    assert html.count("<table") >= 8


def test_all_inventory_sources_exist():
    root = Path(__file__).resolve().parents[2]
    data = build_report_data()
    paths = [entry["path"] for entry in data["source_inventory"]]
    paths += [row["source"] for row in data["golaxy"] + data["selfplay"]]
    missing = sorted({path for path in paths if not (root / path).exists()})
    assert missing == []
