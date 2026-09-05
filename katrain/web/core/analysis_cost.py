# katrain/web/core/analysis_cost.py
"""算力 → credits 的换算。

单位约定（全局唯一）：1 credit = 1 AU = 1000 visits @ cost_factor 1.0。
不引入第二种货币 —— 额度桶是计数器，账本是单池积分。

这里是纯函数：不碰 DB、不读 settings 之外的任何东西，便于单测和在
预扣（用估算手数）与结算（用实际手数）两端复用同一条式子。
"""
import math
from typing import Optional

VISITS_PER_CREDIT = 1000

# 取自 KataGo 官方 docs/NetworkArchitectures.md 的 cost/eval 一列。
# 该文档自称 "extremely approximate"，所以这些值只用于**相对**计价，
# 换模型时必须在生产 GPU 上实测 `katago benchmark` 再调（裁决 D8）。
MODEL_COST_FACTOR = {
    "b28": 1.0,
    "b18": 0.45,
    "b40": 3.0,
    "tf3-b11c768": 1.1,
}
DEFAULT_MODEL = "b28"


def default_factor(model: Optional[str]) -> float:
    """未知模型一律按 1.0 计 —— 宁可少收，不可因为字符串拼错就多收。"""
    if not model:
        return MODEL_COST_FACTOR[DEFAULT_MODEL]
    return MODEL_COST_FACTOR.get(model, MODEL_COST_FACTOR[DEFAULT_MODEL])


def report_cost(moves: int, visits_per_move: int, model: Optional[str] = None) -> int:
    """一份复盘的 credits 成本。

    注意：**今天没有任何调用方传 `model`**，`MODEL_COST_FACTOR` 那张表目前是
    文档（裁决 D8：不换 b40，要换先在生产 GPU 上实测 benchmark），不是活配置。
    别以为它已经接线了。

    moves 为 0 时返回 0（还没分析过任何一手，不该收钱）；
    其余情况向上取整且下界为 1（分析发生了就不能免费）。
    """
    if moves < 0 or visits_per_move < 0:
        raise ValueError("moves 与 visits_per_move 必须 >= 0")
    if moves == 0 or visits_per_move == 0:
        return 0
    visits = moves * visits_per_move * default_factor(model)
    return max(1, math.ceil(visits / VISITS_PER_CREDIT))
