"""着手评价的判据测试。

这里守三类东西：
  1. 判级本身（含每个档位的上下边界）；
  2. 两个配置形状闸（梯子必须升序 / 玄妙断点必须降序）——
     katrain/config.json 正是栽在方向反了上，所以显式挡住；
  3. 生成的 TS 常量与 yaml 不同步时要红。
"""

import copy
import os
import subprocess
import sys

import pytest

from katrain.core import move_grade
from katrain.core.move_grade import UNRATED, grade_move, load_config, points_lost_in_search

CFG = load_config()
PL = CFG["ladder_points"]


def tm(move, score_lead, prior=0.5, visits=500):
    return {"move": move, "score_lead": score_lead, "prior": prior, "visits": visits}


def grade(**kw):
    base = dict(
        prev_top_moves=[tm("D4", 0.0, prior=0.5)],
        prev_visits=500,
        actual_move="D4",
        actual_player="B",
        actual_score_lead=0.0,
        actual_winrate=0.5,
        move_number=30,
    )
    base.update(kw)
    return grade_move(**base)


# --------------------------------------------------------------------------- 判级

@pytest.mark.parametrize(
    "loss,expected",
    [
        (0.0, "very_good"),
        (PL["very_good"] - 0.01, "very_good"),
        (PL["very_good"], "playable"),          # 边界归上一档
        (PL["playable"] - 0.01, "playable"),
        (PL["playable"], "inaccuracy"),
        (PL["inaccuracy"] - 0.01, "inaccuracy"),
        (PL["inaccuracy"], "mistake"),
        (PL["mistake"] - 0.01, "mistake"),
        (PL["mistake"], "blunder"),
        (99.0, "blunder"),
    ],
)
def test_ladder_boundaries_black(loss, expected):
    """黑方：scoreLead 越大越好，所以实战手比最佳低 loss 目。"""
    g = grade(
        prev_top_moves=[tm("D4", 10.0), tm("Q16", 10.0 - loss)],
        actual_move="Q16",
        actual_player="B",
    )
    assert g["grade"] == expected
    assert g["points_lost"] == pytest.approx(loss)


def test_ladder_white_sign_is_flipped():
    """白方：scoreLead 越小越好。同样亏 4 目应判失误，而不是被算成收益。"""
    g = grade(
        prev_top_moves=[tm("D4", -10.0), tm("Q16", -6.0)],
        actual_move="Q16",
        actual_player="W",
        actual_score_lead=-6.0,
    )
    assert g["points_lost"] == pytest.approx(4.0)
    assert g["grade"] == "mistake"


def test_top_move_is_best_not_brilliant_when_prior_is_high():
    g = grade(prev_top_moves=[tm("D4", 0.0, prior=0.60)])
    assert g["grade"] == "best"
    assert g["brilliance"] is None


def test_low_prior_top_move_is_brilliant():
    g = grade(prev_top_moves=[tm("D4", 0.0, prior=0.02)])
    assert g["grade"] == "brilliant"
    assert g["brilliance"] == 3          # levels_prior [0.05,0.03,0.02,0.01,0] -> <0.03 => 3


def test_brilliance_levels_are_monotone():
    seen = [
        grade(prev_top_moves=[tm("D4", 0.0, prior=p)])["brilliance"]
        for p in (0.09, 0.04, 0.025, 0.015, 0.005)
    ]
    assert seen == [1, 2, 3, 4, 5]


def test_brilliant_requires_the_top_move():
    """低 prior 但没走首选，不给妙手。"""
    g = grade(
        prev_top_moves=[tm("D4", 0.0, prior=0.01), tm("Q16", -0.2, prior=0.01)],
        actual_move="Q16",
    )
    assert g["grade"] == "very_good"
    assert g["brilliance"] is None


def test_no_brilliant_in_a_decided_position_by_score():
    """借自 Chess.com：已经完全赢定时不给妙手。"""
    limit = CFG["brilliant"]["require_undecided"]["max_abs_score_lead"]
    inside = grade(prev_top_moves=[tm("D4", 0.0, prior=0.01)], actual_score_lead=limit)
    outside = grade(prev_top_moves=[tm("D4", 0.0, prior=0.01)], actual_score_lead=limit + 0.1)
    assert inside["grade"] == "brilliant"
    assert outside["grade"] == "best"


def test_no_brilliant_in_a_decided_position_by_winrate():
    lo, hi = CFG["brilliant"]["require_undecided"]["winrate_band"]
    assert grade(prev_top_moves=[tm("D4", 0.0, prior=0.01)], actual_winrate=hi)["grade"] == "brilliant"
    assert grade(prev_top_moves=[tm("D4", 0.0, prior=0.01)], actual_winrate=hi + 0.01)["grade"] == "best"


def test_endgame_prior_threshold_is_tightened():
    """官子段 policy 天然更平，同一个 prior 在官子不该算妙手。"""
    scale = CFG["brilliant"]["phase_prior_scale"]["endgame"]
    prior = CFG["brilliant"]["max_prior"] * scale * 1.05      # 中盘算妙手，官子不算
    assert grade(prev_top_moves=[tm("D4", 0.0, prior=prior)], move_number=100)["grade"] == "brilliant"
    assert grade(prev_top_moves=[tm("D4", 0.0, prior=prior)], move_number=200)["grade"] == "best"


def test_low_visits_rows_are_unrated():
    g = grade(prev_visits=CFG["metric"]["min_visits"] - 1)
    assert g["grade"] == UNRATED
    assert g["points_lost"] is None


def test_low_visits_downgrades_brilliant_to_best_but_still_grades():
    """visits 够评级、但不够判妙手时，仍然要给出 best，不能整行作废。"""
    v = CFG["brilliant"]["min_visits"] - 1
    assert v >= CFG["metric"]["min_visits"]
    g = grade(prev_top_moves=[tm("D4", 0.0, prior=0.01)], prev_visits=v)
    assert g["grade"] == "best"


def test_unanalyzed_parent_is_unrated_not_a_mistake():
    """上一手没分析时必须是 unrated —— 绝不能默认成失误。"""
    assert grade(prev_top_moves=[])["grade"] == UNRATED
    assert grade(prev_top_moves=None)["grade"] == UNRATED
    assert grade(actual_move=None)["grade"] == UNRATED


# --------------------------------------------------------------------------- 估计量来源

def test_points_lost_prefers_the_same_search():
    pl, src = points_lost_in_search([tm("D4", 10.0), tm("Q16", 7.0)], "Q16", "B", 999.0)
    assert src == "in_search"
    assert pl == pytest.approx(3.0)          # 用的是候选里的 7.0，不是回退的 999


def test_points_lost_falls_back_across_searches():
    pl, src = points_lost_in_search([tm("D4", 10.0)], "Q16", "B", 7.0)
    assert src == "two_search"
    assert pl == pytest.approx(3.0)


def test_points_lost_uses_the_best_scoring_candidate_not_order_zero():
    """order 是按 playSelectionValue 排的，实测 17.7%~34.4% 的局面里 order-0
    不是 scoreLead 最优的。用 order-0 会算出负损失。"""
    pl, _ = points_lost_in_search([tm("D4", 5.0), tm("Q16", 8.0)], "Q16", "B", 8.0)
    assert pl == pytest.approx(0.0)          # 不是 -3.0


def test_points_lost_never_negative():
    pl, _ = points_lost_in_search([tm("D4", 5.0)], "Q16", "B", 9.0)
    assert pl == 0.0


# --------------------------------------------------------------------------- 配置形状闸

def test_ascending_ladder_gate_rejects_a_flipped_list():
    """katrain/config.json 就是栽在方向反了上（提交 6f544a3c）。这里必须红。"""
    bad = copy.deepcopy(CFG)
    bad["ladder_points"] = {"very_good": 16.0, "playable": 8.0, "inaccuracy": 4.0, "mistake": 2.0}
    with pytest.raises(ValueError, match="ascending"):
        move_grade._validate(bad)


def test_ascending_ladder_gate_accepts_the_shipped_list():
    move_grade._validate(copy.deepcopy(CFG))          # 绿分支也要跑到


def test_descending_brilliance_gate_rejects_a_flipped_list():
    bad = copy.deepcopy(CFG)
    bad["brilliant"]["levels_prior"] = [0.0, 0.01, 0.02, 0.03, 0.05]
    with pytest.raises(ValueError, match="descending"):
        move_grade._validate(bad)


def test_tier_order_gate_rejects_a_reordered_table():
    bad = copy.deepcopy(CFG)
    bad["tiers"] = list(reversed(bad["tiers"]))
    with pytest.raises(ValueError, match="tiers must be exactly"):
        move_grade._validate(bad)


# --------------------------------------------------------------------------- 生成物同步

def test_generated_ts_is_in_sync():
    """改了 yaml 却忘了跑 --emit-ts 时必须红。

    变异记录：把 yaml 里 blunder 的 color 改成 #000000 而不重新生成，
    本用例会红（实测）。
    """
    with open(move_grade.TS_PATH, encoding="utf-8") as f:
        on_disk = f.read()
    assert on_disk == move_grade.emit_ts(), (
        "gradeTiers.generated.ts is stale -- run `python -m katrain.core.move_grade --emit-ts`"
    )


def test_generated_ts_carries_every_tier_and_the_limit():
    with open(move_grade.TS_PATH, encoding="utf-8") as f:
        ts = f.read()
    for t in CFG["tiers"]:
        assert '"%s"' % t["id"] in ts
        assert t["color"] in ts
    assert "PER_SIDE_LIMIT = %d" % CFG["display"]["per_side_limit"] in ts


# --------------------------------------------------------------------------- 部署边界

@pytest.mark.parametrize("req", ["requirements-web.txt", "pyproject.toml"])
def test_pyyaml_is_declared_where_the_yaml_is_actually_read(req):
    """只有 web/desktop 侧会读 yaml —— cron 用的是生成的字面量副本，
    所以 requirements-cron.txt **不该**出现 pyyaml（它也不在镜像里）。"""
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(root, req), encoding="utf-8") as f:
        assert "pyyaml" in f.read().lower()


def test_cron_requirements_do_not_grow_a_yaml_dependency():
    """cron 镜像里没有 PyYAML，也不该有 —— 它用的是生成的字面量 CONFIG。

    如果哪天有人往 katrain/cron 里写了 `import yaml` 再来加这条依赖，
    develop 的 tests/web_ui/test_cron_import_boundary.py 会先红；
    这条是从另一头守：别把依赖悄悄加进来。
    """
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(root, "requirements-cron.txt"), encoding="utf-8") as f:
        assert "yaml" not in f.read().lower()


# --------------------------------------------------------------------------- 生成给 cron 的副本

def test_generated_cron_module_is_in_sync():
    """改了 yaml 或 move_grade_core.py 却忘了跑 --emit 时必须红。

    cron 侧不能 import katrain.core、也没有 PyYAML，所以它用的是这份生成物。
    不同步的后果是「阈值改了但报告没变」，而且不会有任何报错。

    变异记录：把 yaml 里 ladder_points.mistake 改成 7.0 而不重新生成，本用例会红（实测）。
    """
    with open(move_grade.CRON_PATH, encoding="utf-8") as f:
        on_disk = f.read()
    assert on_disk == move_grade.emit_cron(), (
        "katrain/cron/move_grade.py is stale -- run `python -m katrain.core.move_grade --emit`"
    )


def test_generated_cron_module_imports_nothing():
    """生成物必须零 import：katrain/cron 的镜像里既没有 katrain.core，
    第三方也只有 requirements-cron.txt 那几个。任何一条 import 溜进去
    都只在容器里炸，而 cron 崩了在屏上就是「报告一直排队」。"""
    import ast

    with open(move_grade.CRON_PATH, encoding="utf-8") as f:
        tree = ast.parse(f.read())
    imports = [n for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom))]
    assert not imports, f"generated cron module must be import-free, found {len(imports)}"


def test_cron_and_core_agree_on_a_grade():
    """同一手棋在两侧必须判出同一档 —— 逻辑是逐字节副本，这条守的是「副本真的是副本」。"""
    import importlib.util

    spec = importlib.util.spec_from_file_location("cron_move_grade", move_grade.CRON_PATH)
    cron = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cron)

    cases = [
        ([tm("D4", 0.0, prior=0.02)], "D4", "B", 0.0, 0.5, 30),
        ([tm("D4", 10.0), tm("Q16", 6.0)], "Q16", "B", 6.0, 0.5, 30),
        ([tm("D4", -10.0), tm("Q16", -9.6)], "Q16", "W", -9.6, 0.5, 200),
    ]
    for top, mv, player, lead, wr, n in cases:
        a = grade_move(
            prev_top_moves=top, prev_visits=500, actual_move=mv, actual_player=player,
            actual_score_lead=lead, actual_winrate=wr, move_number=n,
        )
        b = cron.grade(
            prev_top_moves=top, prev_visits=500, actual_move=mv, actual_player=player,
            actual_score_lead=lead, actual_winrate=wr, move_number=n,
        )
        assert a == b, f"core and cron disagree on {mv}: {a} vs {b}"


def test_phase_boundaries():
    assert move_grade.phase_of(0) == "opening"
    assert move_grade.phase_of(59) == "opening"
    assert move_grade.phase_of(60) == "midgame"
    assert move_grade.phase_of(149) == "midgame"
    assert move_grade.phase_of(150) == "endgame"
    assert move_grade.phase_of(400) == "endgame"


def test_report_task_move_models_are_mirrors():
    """katrain/cron/models.py 是 katrain/web/core/models_db.py 的手抄镜像。

    只给一边加列时，report_analyze 的 `if hasattr(record, key)` 会**静默丢掉**
    新字段 —— 不报错、不告警，只是数据永远是 NULL。所以这条闸必须存在。

    变异记录：从 cron/models.py 删掉 `brilliance` 一列，本用例会红（实测）。
    """
    from katrain.cron.models import ReportTaskMoveDB
    from katrain.web.core.models_db import ReportTaskMove

    cron_cols = {c.name: type(c.type).__name__ for c in ReportTaskMoveDB.__table__.columns}
    web_cols = {c.name: type(c.type).__name__ for c in ReportTaskMove.__table__.columns}
    assert cron_cols == web_cols


def test_every_grade_column_is_returned_by_the_moves_api():
    """服务端算出来却没在响应里的列，前端等于不存在。"""
    from katrain.web.api.v1.endpoints.reports import ReportTaskMoveResponse

    fields = set(ReportTaskMoveResponse.model_fields)
    for col in ("grade", "points_lost", "points_lost_source", "is_top_move",
                "top_prior", "brilliance", "root_visits"):
        assert col in fields, f"{col} is stored but never delivered"


# --------------------------------------------------------------------------- 桌面端梯子

def test_packaged_eval_thresholds_are_descending():
    """katrain/config.json 的 trainer/eval_thresholds 必须降序。

    core/utils.py 的 evaluation_class 是 `while points_lost < thresholds[i]: i += 1`，
    只有降序才成立。提交 6f544a3c 把它翻成升序后，六级梯子塌成两级：
    <0.5 → class 5，**>=0.5 全部 → class 0**（被 EVAL_COLORS 画成最差色）。
    base_katrain.py 首次启动整份复制这个文件、不做合并，所以新装用户直接继承。

    变异记录：把这个数组改回 [0.5,1.0,2.0,4.0,8.0,16.0]，本用例与下面那条都会红（实测）。
    """
    import json

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(root, "katrain", "config.json"), encoding="utf-8") as f:
        th = json.load(f)["trainer"]["eval_thresholds"]
    assert th == sorted(th, reverse=True), f"eval_thresholds must be descending, got {th}"


def test_packaged_eval_thresholds_give_six_distinct_classes():
    """方向对不对，用 evaluation_class 的行为来判，而不是只看数组长相。"""
    import json

    from katrain.core.utils import evaluation_class

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(root, "katrain", "config.json"), encoding="utf-8") as f:
        th = json.load(f)["trainer"]["eval_thresholds"]
    classes = {evaluation_class(pl, th) for pl in (0.0, 0.2, 0.7, 2.0, 4.0, 8.0, 20.0)}
    assert len(classes) == 6, f"ladder collapsed to {len(classes)} rungs: {sorted(classes)}"


# --------------------------------------------------------------------------- 阈值合一

def test_all_python_threshold_sites_agree_with_the_yaml():
    """同一个「失误 / 疑问手」阈值以前散在四处，其中 cron/analysis_repo.py 用的是
    -1.0 而其余三处是 -1.5 —— 同一手棋在直播页和报告页会得到不同结论。

    这条闸量的是**运行期取到的值**，不是源码文本：写死的字面量换个写法就能绕过
    文本匹配，但绕不过这里。

    变异记录：把 live/models.py 的 mistake_threshold 改回写死的 -3.0 而 yaml 改成
    inaccuracy: 4.0，本用例会红（实测）。
    """
    from katrain.web.live.models import LiveConfig, MoveAnalysis

    ladder = load_config()["ladder_points"]
    cfg = LiveConfig()
    assert cfg.mistake_threshold == -ladder["inaccuracy"]
    assert cfg.questionable_threshold == -ladder["playable"]

    flags = MoveAnalysis.classify_move(-ladder["playable"])
    assert flags["is_questionable"] is True
    assert flags["is_mistake"] is False

    flags = MoveAnalysis.classify_move(-ladder["inaccuracy"])
    assert flags["is_mistake"] is True


def test_research_panels_derive_their_thresholds_from_the_generated_module():
    """两个研究面板双胞胎以前各写死一份阈值（全仓第五、第六份）。

    判据落在「有没有从生成的常量取值」上，而不是「有没有出现某个数字」——
    后者换个写法就能绕过。
    """
    import glob

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    # 枚举现存的面板，而不是写死路径：kiosk 那份双胞胎已被 develop 的
    # e395690a 删掉，写死路径的断言会在合并时红得莫名其妙。
    panels = glob.glob(
        os.path.join(root, "katrain", "web", "ui", "src", "**", "ResearchAnalysisPanel.tsx"),
        recursive=True,
    )
    # 逐项断言对「整项没了」免疫 —— 全删光时上面的循环会空转并静默通过。
    assert panels, "no ResearchAnalysisPanel found; did the gate outlive its target?"
    for path in panels:
        with open(path, encoding="utf-8") as f:
            src = f.read()
        rel = os.path.relpath(path, root)
        assert "GRADE_LADDER_POINTS.inaccuracy" in src, rel
        assert "GRADE_LADDER_POINTS.playable" in src, rel
