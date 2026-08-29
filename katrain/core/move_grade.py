"""着手评价（move grade）—— 加载配置、判级、生成下游产物。

分工：
  * ``move_grade.yaml``       阈值与档位的**可编辑真源**（人只改这一份）。
  * ``move_grade_core.py``    判级逻辑，只用标准库、函数显式收 ``cfg``。
  * 本文件                    读 yaml + 绑定 cfg 的薄封装 + 生成器。

为什么要拆：``Dockerfile.cron`` 只 ``COPY katrain/cron/``，镜像里没有
``katrain.core``、也没有 PyYAML（``tests/web_ui/test_cron_import_boundary.py``
守这条）。所以 cron 侧用的是本文件生成的 ``katrain/cron/move_grade.py`` ——
同一套逻辑 + 一份字面量 CONFIG，不跨包、不加依赖。

生成两样东西：

    python -m katrain.core.move_grade --emit

  1. ``katrain/cron/move_grade.py``（cron 用，stdlib-only）
  2. ``katrain/web/ui/src/features/analysis/gradeTiers.generated.ts``（前端用）

两者与 yaml 不同步时 ``tests/test_move_grade.py`` 会红。
"""

from __future__ import annotations

import functools
import json
import os
import pprint
from typing import Any, Dict, List, Optional, Sequence

import yaml

from katrain.core.move_grade_core import (  # noqa: F401  (re-exported)
    TIER_ORDER,
    UNRATED,
    brilliance_level as _brilliance_level,
    grade_move as _grade_move,
    phase_of as _phase_of,
    points_lost_in_search,
    validate as _validate,
)

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(HERE, "move_grade.yaml")
CORE_PATH = os.path.join(HERE, "move_grade_core.py")

CRON_PATH = os.path.normpath(os.path.join(HERE, "..", "cron", "move_grade.py"))
TS_PATH = os.path.normpath(
    os.path.join(HERE, "..", "web", "ui", "src", "features", "analysis", "gradeTiers.generated.ts")
)


@functools.lru_cache(maxsize=1)
def load_config(path: str = CONFIG_PATH) -> Dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    _validate(cfg)
    return cfg


def tiers() -> List[Dict[str, Any]]:
    return load_config()["tiers"]


def tier_ids() -> List[str]:
    return [t["id"] for t in tiers()]


def phase_of(move_number: int, cfg: Optional[Dict[str, Any]] = None) -> str:
    return _phase_of(move_number, cfg or load_config())


def brilliance_level(prior: float, cfg: Optional[Dict[str, Any]] = None) -> int:
    return _brilliance_level(prior, cfg or load_config())


def grade_move(
    *,
    prev_top_moves: Optional[Sequence[Dict[str, Any]]],
    prev_visits: Optional[int],
    actual_move: Optional[str],
    actual_player: Optional[str],
    actual_score_lead: Optional[float],
    actual_winrate: Optional[float],
    move_number: int,
    cfg: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return _grade_move(
        prev_top_moves,
        prev_visits,
        actual_move,
        actual_player,
        actual_score_lead,
        actual_winrate,
        move_number,
        cfg or load_config(),
    )


# ---------------------------------------------------------------------------
# 生成 cron 侧模块（stdlib-only，逻辑与 move_grade_core.py 逐字节相同）
# ---------------------------------------------------------------------------

CRON_HEADER = '''"""AUTO-GENERATED from katrain/core/move_grade.yaml + move_grade_core.py -- DO NOT EDIT.

    python -m katrain.core.move_grade --emit

katrain/cron 不能 import katrain.core（Dockerfile.cron 只 COPY katrain/cron/），
也没有 PyYAML，所以阈值在这里是一份**字面量**，判级逻辑是 move_grade_core.py 的
逐字节副本。要改阈值请改 katrain/core/move_grade.yaml 再重新生成 ——
tests/test_move_grade.py::test_generated_cron_module_is_in_sync 会守住不同步。
"""

'''

CRON_FOOTER = '''

# ── 绑定 CONFIG 的薄封装，签名与 katrain.core.move_grade 一致 ──


def grade(
    *,
    prev_top_moves,
    prev_visits,
    actual_move,
    actual_player,
    actual_score_lead,
    actual_winrate,
    move_number,
):
    return grade_move(
        prev_top_moves,
        prev_visits,
        actual_move,
        actual_player,
        actual_score_lead,
        actual_winrate,
        move_number,
        CONFIG,
    )


def ladder():
    return CONFIG["ladder_points"]
'''


def _core_body() -> str:
    """move_grade_core.py 去掉模块 docstring 之后的正文。"""
    with open(CORE_PATH, encoding="utf-8") as f:
        src = f.read()
    end = src.index('"""', src.index('"""') + 3) + 3
    return src[end:].lstrip("\n")


def emit_cron() -> str:
    cfg = load_config()
    return (
        CRON_HEADER
        # 用 pprint 而不是 json.dumps + 字符串替换：后者对独占一行的 `null`
        # 匹配不上，会生成 `NameError: name 'null' is not defined` 的模块，
        # 而且是**导入时**才炸 —— 在容器里就是「报告一直排队」。
        + "CONFIG = "
        + pprint.pformat(cfg, indent=4, width=100, sort_dicts=False)
        + "\n\n\n"
        + _core_body()
        + CRON_FOOTER
    )


# ---------------------------------------------------------------------------
# 生成前端常量
# ---------------------------------------------------------------------------

TS_HEADER = """// AUTO-GENERATED from katrain/core/move_grade.yaml -- DO NOT EDIT BY HAND.
// Regenerate:  python -m katrain.core.move_grade --emit
// A test (tests/test_move_grade.py::test_generated_ts_is_in_sync) fails if this
// file drifts from the yaml.
"""


def emit_ts() -> str:
    cfg = load_config()
    rows = []
    for t in cfg["tiers"]:
        rows.append(
            "  { id: %s, i18nKey: %s, zh: %s, color: %s, bad: %s },"
            % (
                json.dumps(t["id"]),
                json.dumps(t["i18n"]),
                json.dumps(t["zh"], ensure_ascii=False),
                json.dumps(t["color"]),
                "true" if t["bad"] else "false",
            )
        )
    phases = cfg["display"]["phases"]
    phase_rows = [
        "  { id: %s, from: %d, to: %s }," % (json.dumps(k), v[0], "null" if v[1] is None else v[1])
        for k, v in phases.items()
    ]
    return (
        TS_HEADER
        + "\nexport type GradeId =\n"
        + "".join('  | %s\n' % json.dumps(t["id"]) for t in cfg["tiers"])
        + '  | "unrated";\n\n'
        + "export interface GradeTier {\n"
        + "  id: GradeId;\n  i18nKey: string;\n  zh: string;\n  color: string;\n  bad: boolean;\n}\n\n"
        + "export const GRADE_TIERS: readonly GradeTier[] = [\n"
        + "\n".join(rows)
        + "\n] as const;\n\n"
        + "export const GRADE_BY_ID: Readonly<Record<string, GradeTier>> = Object.fromEntries(\n"
        + "  GRADE_TIERS.map((t) => [t.id, t]),\n);\n\n"
        + "export const BAD_GRADES: readonly GradeId[] = GRADE_TIERS.filter((t) => t.bad).map((t) => t.id);\n\n"
        + "export const GRADE_LADDER_POINTS = {\n"
        + "".join(
            "  %s: %s,\n" % (k, cfg["ladder_points"][k])
            for k in ("very_good", "playable", "inaccuracy", "mistake")
        )
        + "} as const;\n\n"
        + "export const PER_SIDE_LIMIT = %d;\n\n" % cfg["display"]["per_side_limit"]
        + "export const SHOW_TRUNCATED_TOTAL = %s;\n\n"
        % ("true" if cfg["display"]["show_truncated_total"] else "false")
        + "export interface GradePhase {\n  id: string;\n  from: number;\n  to: number | null;\n}\n\n"
        + "export const GRADE_PHASES: readonly GradePhase[] = [\n"
        + "\n".join(phase_rows)
        + "\n] as const;\n"
    )


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="move grade config tool")
    ap.add_argument("--emit", action="store_true", help="regenerate the cron module and the TS constants")
    args = ap.parse_args()
    if args.emit:
        for path, text in ((CRON_PATH, emit_cron()), (TS_PATH, emit_ts())):
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)
            print("wrote", path)
    else:
        print(json.dumps(load_config(), ensure_ascii=False, indent=2))
