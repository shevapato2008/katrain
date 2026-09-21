# vision-stone-parallax

棋子成像视差修正。摄像头斜着俯拍,棋子有厚度,成像位置沿背离镜头方向系统性外移,
远端棋子越过半格线被判到邻近交点。本赛道在坐标映射链里补上这一步修正。

一句话结论:**偏移是以 nadir 为中心、系数 k = (H−h)/H 的一次位似,反向是精确解,
k 在仿射变换下不变,所以可以直接做在连续网格坐标上。**

## 文件

| 文件 | 内容 |
|---|---|
| `prd.md` | 本轮需求。背景、不要动的、三条需求条目(含根因行号与验收)、非目标、风险 |
| `design.md` | 实现设计。修正落在哪一层、标定文件格式与读写时机、诊断日志格式、失败即拒绝的标定工具设计 |
| `geometry.md` | 推导、实测输入、h 为什么取厚度一半、两个精确模型的校核、现场标定、边界 |
| `plan.md` | 按任务拆分的实现计划(Task 1–9),每个任务的文件、约束、验收条目 |
| `handoff.md` | 上板交接。部署步骤、固定摆位复现故障的流程、标定步骤、事先定死的判定阈值、待填的对照数据表 |
| `parallax_correct.py` | 参考实现。`correct` / `forward` / `to_point` / `apply_parallax` / `fit_from_samples`;自带 361 点往返自检 |
| `verify_quadric.py` | 校核脚本。切锥 ∩ 平面(模型 A)、像平面椭圆中心反投(模型 B) |
| `offsets-361.csv` | 361 点偏移表,`python3 parallax_correct.py --csv` 生成 |

交互网页(矢量场 / 热力图 / 剩余容差 / 逐点表,h 与位姿可调):
Claude 制品「棋子视差修正」 https://claude.ai/artifact/4vUjiEzESaf78WCTTUEscs

## 跑一遍

需要 numpy。这台机器上是 `/opt/homebrew/bin/python3`(系统 `python3` 没装 numpy)。

```
python3 parallax_correct.py          # 自检：361 点往返 + snap
python3 parallax_correct.py --csv    # 生成 offsets-361.csv
python3 verify_quadric.py            # 线性公式 vs 精确二次曲面的残差
```

2026-09-21 在本机跑过,输出:

```
K = 0.989689   nadir = (0.0, -70.545)   H = 339.4424   h = 3.5
往返自检 361 点全过；snap 全部回到原交点
最大偏移 5.014 mm @ A19   (dx -2.222, dy -4.495)
远端剩余摆子容差 6.505 mm（半格 11.0）

模型 A 残差  max 0.0528  mean 0.02986 mm    (占半格 0.480%)
模型 B 残差  max 0.1809  mean 0.12691 mm    (占半格 1.645%)
```

## 接进流水线的位置

`katrain/vision/board_state.py` 的 `BoardStateExtractor._positions`,在 `continuous_grid_pos` 之后、
取整之前;是 `apply_parallax` 唯一的调用点。`coordinates.py` 的 `physical_to_grid` 本身不动 ——
`tests/test_vision/test_warp_consistency.py:46-47` 还把它当纯几何断言用。

## 硬件侧的真源

几何来自 `smartbox-hardware-design` 仓库:

- Fusion 文档 `ver9-camera-mount-fixed-j2`
- `output/camera-mount-ver9/verification.json`(`lens_mm`、光轴、俯角)
- `3d-modeling/camera-arm-摄像头杆/v9-cad/棋子视差修正-说明.md`(硬件侧同一份结论)
