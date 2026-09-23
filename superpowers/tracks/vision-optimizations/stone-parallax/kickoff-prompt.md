# 启动 prompt(贴进 Claude Code session)

下面 `---` 之间的全文直接粘贴。

---

# 赛道:棋子成像视差修正(vision-stone-parallax)

## 0. 你在哪

- 仓库 `/Users/fan/Repositories/katrain-kiosk-debug`,当前分支 `fix/kiosk-ui-debug` @ `7a152df1`
- 赛道目录 `superpowers/tracks/vision-optimizations/stone-parallax/`

**动手前先读完这四个,不要跳**:

1. `superpowers/tracks/vision-optimizations/stone-parallax/README.md` — 索引
2. `superpowers/tracks/vision-optimizations/stone-parallax/prd.md` — 本轮需求(三条需求条目,带根因行号与验收)
3. `superpowers/tracks/vision-optimizations/stone-parallax/geometry.md` — 公式推导、实测输入、二次曲面校核
4. `superpowers/tracks/vision-optimizations/stone-parallax/parallax_correct.py` — 参考实现

然后读这几处源码(PRD 里的根因就指着它们):

- `katrain/vision/coordinates.py` 全文(只有 55 行)
- `katrain/vision/board_state.py:100-134`
- `katrain/vision/config.py:14-48`(`BoardConfig`)
- `katrain/vision/worker.py:440-495`(`ambiguous_stone` 事件)
- `tests/test_vision/test_warp_consistency.py`

`parallax_correct.py` 和 `verify_quadric.py` 可以直接跑,验证结论是真的
(本机 numpy 在 `/opt/homebrew/bin/python3`,系统 `python3` 没装):

```
/opt/homebrew/bin/python3 superpowers/tracks/vision-optimizations/stone-parallax/parallax_correct.py
/opt/homebrew/bin/python3 superpowers/tracks/vision-optimizations/stone-parallax/verify_quadric.py
```

## 1. 已经确认的结论 —— 别重新推导,也别绕过

这些是 2026-09-21 从 Fusion 实测几何推出来并做过独立校核的,直接当输入用:

1. **偏移 = 以 nadir 为中心、系数 k = (H−h)/H 的一次位似**,反向是精确解,不用迭代。
   与俯角、焦距、FOV、畸变无关(前提:已做过透视矫正,在棋盘平面坐标里算)。
2. **k 在仿射变换下不变**。`pixel_to_physical` + `continuous_grid_pos` 合起来是仿射映射,
   所以修正可以**直接做在连续网格坐标 (fx, fy) 上,k 不用换算**,只要 nadir 表示成同一
   坐标系里的一对数。实现是两行。
3. **nadir 必须现场标定,不许把 CAD 值写死**。`config.py:22-23` 的 `BoardConfig` 默认
   424.2 × 454.5(标准日式盘),ver9 实物网格是 396.0 × 426.6;加上 warp 的四角顺序决定
   (fx,fy) 的原点与行列方向 —— 搬 CAD 数会搬错符号。标定模型 `D = m·P + (1−m)·C`
   对 (m, C) 线性,最小二乘即可,见 `parallax_correct.py::fit_from_samples`。
4. **`physical_to_grid` 本身不要动** —— `tests/test_vision/test_warp_consistency.py:46-47`
   把它当纯几何断言用。修正插在 `board_state.py` 的两个调用点上。
5. **边距 DROP 行为不许回归**。`board_state.py:100-114` 的注释记着一次事故:
   clamp 曾把角外的红色物体变成幽灵 T19。修正不能把边距里的假目标推回盘内。
6. **未标定时整条修正必须是恒等映射**,行为与今天逐位相同。
7. **这不是识别率问题,是坐标映射问题。** 不碰 YOLO 权重、不重训、不碰
   warp / board_finder / geometry_lock / 四角检测。

如果你在任何阶段发现上面某一条是错的,**停下来告诉我**,不要自己改结论往下走。

## 2. 五个阶段,每个阶段之间停下来等我确认

### 阶段 1 · 设计(模型:opus 5,技能:brainstorming)

切到 opus 5(`/model opus`),用 **brainstorming** 技能。

- 把 PRD 的三条需求条目过一遍,**主动向我提问**,把设计上没定的东西问清楚。
  我预期你至少会问到:修正开关配置挂在哪(`BoardConfig` / `VisionConfig` /
  `calibration_registry` / `geometry_lock`)、标定工具的交互形态、
  诊断字段怎么加才不破坏既有消费方、这一轮要不要同时处理 `detection_points`
  的元组扩位。
- 产出写进 `superpowers/tracks/vision-optimizations/stone-parallax/design.md`。
- 顺手把 `prd.md` 开头的「分支 / worktree:待定」补上(建议
  `feature/vision-stone-parallax`,用 superpowers 的 **using-git-worktrees** 技能开)。
- **门槛**:我说「设计通过」才进阶段 2。

### 阶段 2 · 计划(模型:opus 5,技能:writing-plans)

用 **writing-plans** 技能,产出 `superpowers/tracks/vision-optimizations/stone-parallax/plan.md`。

要求:

- bite-sized 任务,TDD,频繁提交。每个任务写清:改哪些文件、写什么测试、怎么跑、
  验收标准是什么。
- **plan.md 的验收项要能逐条对上 `prd.md` §3 里每条需求的验收清单**,一条不落。
- 必须包含这两个任务,别漏:
  - 「修正关掉(nadir 为 None)时,`board_state` 两处输出与修正前逐位相同」的回归测试
  - 标定工具本身(含 `h_implied` 落在 2–8 mm 之外要报标定失败,不许静默写入)
- 计划里要写明每个任务用哪个 python(仓库自己的 venv 还是 `/opt/homebrew/bin/python3`)。

### 阶段 3 · 计划评审(命令:`/codex:adversarial-review`)

**注意这是 slash command,不是 skill**,而且它审的是 git 工作区的改动,不是任意文档。
所以:先确保 `design.md` 和 `plan.md` 已经落盘(untracked 也算可审),然后跑

```
/codex:adversarial-review --wait --scope working-tree 重点审 superpowers/tracks/vision-optimizations/stone-parallax/plan.md 与 design.md：方案是否正确、任务拆分是否可执行、验收是否可证伪、是否漏掉 prd.md §3 的验收项、是否违反 prd.md §1 的七条约束
```

- 拿到反馈**回到阶段 2 改计划**,改完再审一次。
- **最多两轮**。两轮之后还有 P0 级分歧,停下来把分歧点列给我,我来拍。

### 阶段 4 · 开发(模型:sonnet 5,技能:subagent-driven-development)

切到 sonnet 5(`/model sonnet`),用 **subagent-driven-development** 技能并行执行 plan.md。

- subagent 不继承你的上下文。**每个 subagent 的 prompt 里必须自带**:它要改的文件、
  §1 里与它相关的约束条款、验收标准。别让它自己去猜。
- 每个任务完成后跑该任务的测试;全绿再进下一个。
- 任何 subagent 提出要改 §1 的结论、要动 YOLO / warp / `physical_to_grid`,
  **停下来问我**,不要批准。

### 阶段 5 · 代码审核(模型:opus 5)

切回 opus 5。

**先看清楚再动手**:本机 `/code-review` 这个 slash command 走的是 `gh pr diff`,
**审的是 PR,不是本地未提交的改动**。所以你有两条路,自己判断并告诉我你选哪条:

- (a) 先开 PR,再 `/code-review <PR>`;
- (b) 本地改动直接用 superpowers 的 **requesting-code-review** 技能审。

审核意见回到阶段 4 改,改完重审,**直到通过为止**。
收尾用 superpowers 的 **verification-before-completion** 技能。

## 3. 收尾动作

1. 把实测标定出来的 `k`、`nadir`、`rms`、`h_implied` 写进 `geometry.md` 末尾,
   注明是哪副棋子、哪次标定。
2. 更新 `prd.md`:每条需求标上完成状态;§5 风险里已经排除的划掉。
3. 上板验证的对照数据(修正前后 `ambiguous_stone` 里 `unbacked=True` 的计数)
   记进 `superpowers/tracks/vision-optimizations/stone-parallax/` 下的一份 handoff。

## 4. 现在开始

先读 §0 列的四个文档和五处源码,然后进入**阶段 1**,用 brainstorming 技能开始向我提问。
不要跳过阶段,不要在我确认之前往下走。
