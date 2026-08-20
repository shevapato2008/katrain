"""从摘要件重算 §C37 的全部缝表。

摘要件 `results/artifacts/ladder_seams_summary_20260814.jsonl.gz` 是六轮标定(3,972 局)
的可复算压缩:每局一行,只留出表用到的字段。**原始 checkpoint 共 1.6 GB,留在
home-ubuntu 的 `results/ladder_*_2026081[34]/`,路径见 EXPERIMENTS.md 附表。**

为什么摘要里保留 `a_color` / `our_color`:自证靠它。丢掉这两个字段,摘要就只剩
"我说 A 是强侧",而方向猜错时整张表会**静默翻转** —— 0.62 和 0.38 都是合理数,
肉眼分不出来。所以自证不是走过场,是这张表可信的唯一依据。

    python replay_seams_summary.py                       # §C37 原表（默认全部不变）
    python replay_seams_summary.py \
        --summary results/artifacts/ladder_kyu550_seams_20260820.jsonl.gz \
        --by-config --pairs --gate-point 0.550               # §C38 的口径

三个开关分别对应 §C38 与 §C37 判读口径上的三处差别，默认值一律保持 §C37 的行为，
所以不带参数跑出来的表与本文件首次提交时逐字节相同：

  --by-config   按 (A配置, B配置) 归一化方向合并**全部批次**，而不是按 (run, seam) 分桶。
                seam id 会跨 run 复用而配置不同 —— 按 id 合并 `30_31` 得 0.599，
                按配置对拆开是 0.759。这个坑踩过一次，见 EXPERIMENTS.md §C37 脚注。
  --pairs       用 complete_pair_sample 口径：一对(同一 opening、两种执色)里**两局都**
                conclusive 才计入，且必须两色齐全。默认是逐局过滤，两者数字会差几个百分点。
  --gate-point  判据换成**点估计**（Fan 2026-08-20 裁定 0.550）。默认仍是 Wilson 95%
                CI 下界 0.60 —— §C37 当时用的就是那个。
"""

from __future__ import annotations

import argparse
import gzip
import json
import math
from collections import defaultdict
from pathlib import Path

DEFAULT_SUMMARY = Path(__file__).parent / "results" / "artifacts" / "ladder_seams_summary_20260814.jsonl.gz"
GATE = 0.60  # §C37 认证闸门:Wilson 95% CI 下界。点估计只记录、不作判据。


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
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--summary", action="append", type=Path, help="摘要件，可给多次；缺省用 §C37 那份")
    parser.add_argument("--by-config", action="store_true", help="按 (A配置,B配置) 合并全部批次，而非按 (run,seam)")
    parser.add_argument("--pairs", action="store_true", help="用 complete_pair_sample 口径")
    parser.add_argument("--gate-point", type=float, default=None, help="判据改成点估计，给出闸值（如 0.550）")
    args = parser.parse_args()
    summaries = args.summary or [DEFAULT_SUMMARY]
    gate_point = args.gate_point

    buckets: dict[tuple[str, str], dict] = defaultdict(lambda: {"w": 0, "n": 0, "viol": 0, "tot": 0, "a": "", "b": ""})
    pair_rows: dict[tuple, list] = defaultdict(list)
    for path in summaries:
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            for line in handle:
                row = json.loads(line)
                key = (row.get("a", ""), row.get("b", "")) if args.by_config else (row["run"], row["seam"])
                bucket = buckets[key]
                bucket["a"], bucket["b"] = row.get("a", ""), row.get("b", "")
                bucket["tot"] += 1
                if row.get("a_color") != row.get("our_color"):
                    bucket["viol"] += 1
                    continue
                if args.pairs:
                    # 同一批次、同一条缝、同一次 pair_attempt 的两局才算一对
                    pair_rows[
                        (key, row.get("run"), row.get("seam"), row.get("pair_attempt"), row.get("opening_id"))
                    ].append(row)
                    continue
                if not row.get("conclusive"):
                    continue
                bucket["n"] += 1
                bucket["w"] += 1 if row.get("our_win") else 0

    if args.pairs:
        for (key, *_rest), games in pair_rows.items():
            if len(games) != 2 or not all(g.get("conclusive") for g in games):
                continue
            if len({g.get("color_index") for g in games}) != 2:
                continue
            buckets[key]["n"] += 2
            buckets[key]["w"] += sum(1 for g in games if g.get("our_win"))

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

    print(f"{'轮次':<14} {'缝':<16} {'A(强)':<18} {'B(弱)':<18} {'胜率':>7}{'战绩':>10}{'下界':>8}{'Elo':>7}  判定")
    print("-" * 100)

    passed = []
    measured = 0
    for (run, seam), b in sorted(buckets.items()):
        if b["n"] == 0:
            print(f"{short(run):<14} {seam:<16} {b['a']:<18} {b['b']:<18} {'—':>7}{'(无数据)':>10}")
            continue
        measured += 1
        rate = b["w"] / b["n"]
        low, _high = wilson(b["w"], b["n"])
        if gate_point is None:
            ok, verdict = low >= GATE, ("✅" if low >= GATE else ("🟡" if low >= 0.50 else "❌"))
        else:
            ok, verdict = rate >= gate_point, ("✅" if rate >= gate_point else "❌")
        if ok:
            passed.append((run, seam, low))
        print(
            f"{short(run):<14} {seam:<16} {b['a']:<18} {b['b']:<18} "
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
