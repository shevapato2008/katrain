"""从摘要件重算 §C37 的全部缝表。

摘要件 `results/artifacts/ladder_seams_summary_20260814.jsonl.gz` 是六轮标定(3,972 局)
的可复算压缩:每局一行,只留出表用到的字段。**原始 checkpoint 共 1.6 GB,留在
home-ubuntu 的 `results/ladder_*_2026081[34]/`,路径见 EXPERIMENTS.md 附表。**

为什么摘要里保留 `a_color` / `our_color`:自证靠它。丢掉这两个字段,摘要就只剩
"我说 A 是强侧",而方向猜错时整张表会**静默翻转** —— 0.62 和 0.38 都是合理数,
肉眼分不出来。所以自证不是走过场,是这张表可信的唯一依据。

    python replay_seams_summary.py
"""

from __future__ import annotations

import gzip
import json
import math
from collections import defaultdict
from pathlib import Path

SUMMARY = Path(__file__).parent / "results" / "artifacts" / "ladder_seams_summary_20260814.jsonl.gz"
GATE = 0.60  # 认证闸门:Wilson 95% CI 下界。点估计只记录、不作判据。


def wilson(wins: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 1.0)
    p = wins / n
    denom = 1 + z * z / n
    centre = p + z * z / (2 * n)
    spread = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((centre - spread) / denom, (centre + spread) / denom)


def elo(p: float) -> float:
    p = min(max(p, 1e-6), 1 - 1e-6)
    return 400 * math.log10(p / (1 - p))


def main() -> int:
    buckets: dict[tuple[str, str], dict] = defaultdict(lambda: {"w": 0, "n": 0, "viol": 0, "tot": 0, "a": "", "b": ""})
    with gzip.open(SUMMARY, "rt", encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line)
            key = (row["run"], row["seam"])
            bucket = buckets[key]
            bucket["a"], bucket["b"] = row.get("a", ""), row.get("b", "")
            bucket["tot"] += 1
            if row.get("a_color") != row.get("our_color"):
                bucket["viol"] += 1
            if not row.get("conclusive"):
                continue
            bucket["n"] += 1
            bucket["w"] += 1 if row.get("our_win") else 0

    violations = {k: v["viol"] for k, v in buckets.items() if v["viol"]}
    if violations:
        print(f"❌ 自证失败:{len(violations)} 条缝的 a_color != our_color,方向不可确定,拒绝出表。")
        for key, count in violations.items():
            print(f"   {key} {count} 局")
        return 2

    total = sum(v["tot"] for v in buckets.values())
    print(f"自证 OK:{total} 局全部 a_color == our_color ⇒ our 即 A(强侧)\n")

    # 轮次名去掉共同前后缀,只留能认人的那一截(ladder_v2_seams_20260813 -> v2)
    def short(run: str) -> str:
        return run.removeprefix("ladder_").removesuffix("_20260813").removesuffix("_20260814").removesuffix("_seams")

    print(f"{'轮次':<12}{'缝':<14}{'A(强)':<18}{'B(弱)':<18}{'胜率':>7}{'战绩':>10}{'下界':>8}{'Elo':>7}  判定")
    print("-" * 100)

    passed = []
    measured = 0
    for (run, seam), b in sorted(buckets.items()):
        if b["n"] == 0:
            print(f"{short(run):<12}{seam:<14}{b['a']:<18}{b['b']:<18}{'—':>7}{'(无数据)':>10}")
            continue
        measured += 1
        rate = b["w"] / b["n"]
        low, _high = wilson(b["w"], b["n"])
        verdict = "✅" if low >= GATE else ("🟡" if low >= 0.50 else "❌")
        if low >= GATE:
            passed.append((run, seam, low))
        print(
            f"{short(run):<12}{seam:<14}{b['a']:<18}{b['b']:<18}"
            f"{rate:>6.1%}{b['w']:>5}/{b['n']:<4}{low:>8.3f}{elo(rate):>7.0f}  {verdict}"
        )

    print(f"\n总局数 {total}    过 {GATE:.2f} 下界闸的缝:{len(passed)}/{measured}")
    for run, seam, low in passed:
        print(f"   ✅ {short(run):<12}{seam:<14} 下界 {low:.3f}")
    print(
        "\n不连续 ⇒ 现行配置下没有一段连续阶梯可声称已标定 ⇒ "
        "`ladder._CERTIFIED_RUNGS` 保持 frozenset()(EXPERIMENTS.md §C37.5)。"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
