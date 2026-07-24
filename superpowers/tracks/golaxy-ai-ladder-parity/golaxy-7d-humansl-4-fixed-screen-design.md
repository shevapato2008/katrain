# 星阵 7D 与 `rank_7d@4` 固定筛选实验设计

日期：2026-07-24

## 目标与配置

固定测试修复后的 b18+humanv0+canonical PIKL `rank_7d@4` 对星阵“7段/星奇豚”。星阵真实 API
wire level 为 `2500`，对应 core rung 29。目标为 5 个有效结果，颜色 B/W/B/W/B；不可判定局不进分母并
原色补局。

## 今日额度边界

2026-07-24 已由 9D、8D 实验消耗 16 次额度，预计只剩 4 次。runner 先取得今天可用的 4 个有效结果，
然后按用户指示尝试第 5 局：

- 若第 5 局正常开始并返回，累计 5 个有效结果后停止；
- 若星阵返回额度耗尽/7002/429，零重试停止，保留调用前 reservation；
- 额度恢复后以同一 quota ID 和账本恢复，重新调度尚缺的第 5 个有效结果。

本地 reservation 上限设为 9，以容纳一次被拒绝的尝试和少量不可判定局；这只提供可恢复空间，不会绕过
星阵服务端额度。token、断连、配置漂移同样立即停止。

## 隔离与验证

- 新 preset：`golaxy7d-rank7d4-20260724`。
- 新 quota：`golaxy7d-rank7d4-20260724-a`。
- 独立账本：`calibration/results/golaxy_7d_rank_7d_4_20260724/fixed_screen.jsonl`。
- 只访问本地 KataGo `http://127.0.0.1:8000`；启动前验证 b18/humanv0/PIKL 与星阵 rung 29/2500。
- 测试锁定 preset、B/W/B/W/B 调度、额度上限、输出路径及旧 8D/9D preset 回归。
- 结果和可能的额度拒绝 reservation 均写入本目录 `EXPERIMENTS.md`。
