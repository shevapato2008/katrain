# OGS 棋盘字母标记对齐修复实施计划

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 OGS 题目的字母及数字标记准确居中于对应交叉点或棋子，消除“看到的选项位置”和实际落子位置不一致的问题。

**Architecture:** 修复 Kiosk 共用 `OgsCourseBoard` 的 SVG 文本定位。标记、棋子、网格和点击热区沿用同一套原始点位，保留现有裁剪及 Kiosk19 坐标适配；无需逐题改数据库或答案树。以一个共享组件的局部修改解决全课程同类问题。

**Tech Stack:** React / TypeScript、SVG、现有 Vitest / Testing Library、Chromium 浏览器与 RK3562 Kiosk。

---

## 执行记录（2026-11-19）

修复及四步发布已执行：develop `bfbe3d560`，SmartBox main `32a0f895`，home-ubuntu / ucloud-v100 / RK3562 均已安装并校验前端。独立 Astra Max 计划与代码审核通过；43 项聚焦测试通过，严格 Kiosk 与 Galaxy 构建通过。实际浏览器验证 B 判错、重试后 A 判对；RK3562 ABC 几何偏差最大 0.004661 格，符合 ≤0.1 格要求。

盒端在验收中有外部操作连续翻页，因此暂停额外点击、模式切换和临时游客清理，保持现场 Go 模式及音量 0，等待会话协调回复。未将外部作答计为本代理的交互验收。

[完整发布与验收回执](../../../output/ogs-label-alignment-20261119/final-result.json)。以下为实施前保留的原计划。

## 当前结论与范围

用户要求：找出截图中类似 ABC 不在交叉点上的题目，并写修改计划。本轮交付到清单与计划为止，尚未修改产品代码、部署或重新制作视频。

完整清单：[可筛选 HTML](../../../superpowers/tracks/tutorial-database/ogs-label-alignment-audit-2026-11-19.html)、[CSV](../../../superpowers/tracks/tutorial-database/ogs-label-alignment-audit-2026-11-19.csv)、[JSON 与证据摘要](../../../superpowers/tracks/tutorial-database/ogs-label-alignment-audit-2026-11-19.json)。

### 数据范围

2026-11-19 对正式环境课程做只读采集：7 章、248 课、3,551 步。原始数据和前端实际使用的 `kiosk19` 适配结果均已检查。

| 章节 | 受影响课程 | 带字母的步骤（可含编号） | 纯数字编号步骤 | 合计步骤 | 标记数量 |
|---|---:|---:|---:|---:|---:|
| 1 入门知识 | 3 | 3 | 1 | 4 | 8 |
| 2 基本规则 | 8 | 22 | 7 | 29 | 35 |
| 3 基础技巧 | 11 | 49 | 17 | 66 | 111 |
| 4 初学者等级1 | 11 | 42 | 45 | 87 | 99 |
| 5 初学者等级2 | 25 | 142 | 61 | 203 | 438 |
| 6 初学者等级3 | 42 | 344 | 52 | 396 | 941 |
| 7 初学者等级4 | 18 | 192 | 13 | 205 | 655 |
| **合计** | **118** | **794** | **196** | **990** | **2,287** |

- 756 步是落子题，234 步是观察选择题；观察题上的标记也应准确，仍保留原有题型。
- 1,840 个标记在空点，447 个标记在已有棋子上（黑子 286，白子 161）。
- 标记内容包含 A–H、X，以及 1–12；本次数据没有小写字母。两位数也使用同一段有偏移的代码。
- 没有发现标记点越出棋盘或裁剪可视范围。适配到 19 路的题保留原始与适配坐标，不能把两套坐标混用。
- 与 2026-11-17 TEST book 80 快照比较，3,551 步的 stable ID、lesson ID、步骤、API 页 ID、棋盘大小、先手、棋子、letters、shapes、viewport 共 10 项字段零差异。正式环境 book 11 与 TEST book 80 的本地 ID 不用于跨环境匹配。
- 数量来自全量数据扫描及共享代码检查，不等于逐题截图审核。其他形状符号未纳入本次确认的 990 步。

### 已复现的根因

`katrain/web/ui/src/kiosk/tutorial/OgsCourseBoard.tsx` 的交叉点、棋子和点击热区使用 `position(n) = (n + 0.5) * 100`；`step.letters` 文本却使用 `y={position(y) - 31}`，且采用默认字母基线，导致文字中心进一步向上偏移。

截图对应 `ogs-learning:bl4-opening-4:1`（7.4《布局》第 1/8 步，API page 3006）：

| 标记 | 原始点位（0 起始） | 正确棋盘坐标 | 交叉点 SVG 中心 | 当前文本锚点 |
|---|---|---|---|---|
| A | [7,15] | H4 | [750,1550] | [750,1519] |
| B | [7,16] | H3 | [750,1650] | [750,1619] |
| C | [8,16] | J3 | [850,1650] | [850,1619] |

在实际 1024×600 浏览器中，三者 `getBBox()` 测得的视觉中心均向上偏约 **0.562 格 / 12.25px**。点击热区在正确点位。已发布的 `ddfe7d8d1a11acf290e2dfc42a78753c944ee1ad` 含有同样代码；现有测试刚好使用这一题，却只检查字母存在与点击回调，没有检查对齐。

在浏览器临时测量元素上试算 `y=position(y)` 配合 `dominant-baseline="central"`，A/B/C 及 10/11/12 的文本包围盒中心回到交叉点；测量元素已移除，没有改变应用文件。最终仍需修复后的真实页面与设备确认。

### 文件职责与最小改动

| 文件 | 用途 | 计划改动 |
|---|---|---|
| `katrain/web/ui/src/kiosk/tutorial/OgsCourseBoard.tsx` | 渲染网格、棋子、标记和点击热区 | 仅统一 letters 文本的纵向锚点与基线 |
| `katrain/web/ui/src/kiosk/tutorial/OgsCourseBoard.test.tsx` | 该组件的现有回归测试 | 扩充截图对应的坐标对齐断言与少量边界夹具 |
| `katrain/web/ui/src/kiosk/pages/OgsCoursePages.test.tsx` | 课程流程与落子交互回归 | 默认直接运行；仅发现本次回归时才修改 |
| `katrain/web/ui/src/kiosk/tutorial/ogsExercise.test.ts` | 规则及答案树判定回归 | 直接运行，原则上无需修改 |

不新增标记坐标字段、后端接口、通用渲染框架或运行时修复脚本。此次问题位于互动棋盘；没有证据要求修改 Admin 静态识别图、其他棋盘组件或音视频文件。

## Chunk 1: 标记居中修复与验收

实施前使用 @superpowers:using-git-worktrees，从最新 `origin/develop` 建立隔离分支 `fix/ogs-board-label-alignment-20261119`，工作树固定为 `/Users/fan/.config/superpowers/worktrees/katrain-admin-console/ogs-board-label-alignment-20261119`。保留主工作区已有未提交改动；以下命令均指向这个修复工作树，本轮写计划不执行这些命令。

### Task 1: 在现有复现题中补上对齐回归

**Files:** Modify/Test: `katrain/web/ui/src/kiosk/tutorial/OgsCourseBoard.test.tsx`

- [ ] **Step 1:** 沿用现有 `openingStep`，在现有裁剪测试中加入以下对齐断言，不复制整份课程数据：

```tsx
for (const [label, x, y] of [
  ['A', 7, 15], ['B', 7, 16], ['C', 8, 16],
] as const) {
  const marker = within(svg).getByText(label);
  const hit = screen.getByTestId(`ogs-point-${x}-${y}`);
  expect(marker.getAttribute('x')).toBe(hit.getAttribute('cx'));
  expect(marker.getAttribute('y')).toBe(hit.getAttribute('cy'));
}
```

现有的点击 A 对应热区后回调 `[7,15]`、裁剪 `viewBox`、等比例棋子尺寸等断言继续保留。这个测试约束“标记锚点与落子点一致”；视觉文字中心另由 Task 3 在真实浏览器测量，不能用 JSDOM 的结果代替视觉验收。

- [ ] **Step 2:** 运行并确认旧实现失败，预期 A 的文本 y=1519 而热区 cy=1550：

```bash
cd /Users/fan/.config/superpowers/worktrees/katrain-admin-console/ogs-board-label-alignment-20261119/katrain/web/ui
npm test -- src/kiosk/tutorial/OgsCourseBoard.test.tsx
```

### Task 2: 修正共享文本定位，补齐必要的代表数据

**Files:** Modify: `katrain/web/ui/src/kiosk/tutorial/OgsCourseBoard.tsx`; Test: `katrain/web/ui/src/kiosk/tutorial/OgsCourseBoard.test.tsx`

- [ ] **Step 1:** 只修改 `step.letters` 的 `<text>`：去掉固定 `-31` 偏移，明确使用中央基线；保留 x、字体大小计算、字重、描边、颜色和图层顺序。

```tsx
return showPoint(x, y) ? <text
  key={`l${point}`}
  x={position(x)}
  y={position(y)}
  textAnchor="middle"
  dominantBaseline="central"
  fontSize={annotationFontSize}
  fontWeight="bold"
  fill="#183c28"
  paintOrder="stroke"
  stroke="#f3d496"
  strokeWidth="8"
>{label}</text> : null;
```

保持原始 `[x,y]`、Kiosk19 偏移策略、viewport、点击半径和题目的答案路径完全一致。不能把题目坐标往上移动来迁就错误文字，也不能将正确落点替换成当前字母所在的格间位置。

- [ ] **Step 2:** 在同一个测试文件中，用参数化小夹具覆盖 9、13、19 路，以及裁剪和棋子上标记。夹具沿用真实数据的对应点位：

| 来源 | 检查目标 |
|---|---|
| 1.2 `self-capture` 第1步，page7 | 原9路 → Kiosk19 后 A=[18,0]、B=[17,1]、C=[14,5]；转换后的绝对坐标仍正确 |
| 1.3 `eyes` 第1步，page10 | 原生9路 A=[3,2]、B=[4,8]；下边缘标记不被裁掉 |
| 1.4 `ko` 第5步，page18 | 原生13路，白子上的 `1`=[0,10]；左边缘与棋子上标记居中 |
| 6.8 `bl3-joseki-1` 第7步，page2017 | 原生19路两位数 `10`=[1,14]、`11`=[1,16]、`12`=[2,13]；不得串到相邻点 |
| 7.4 `bl4-opening-4` 第1步，page3006 | 19×10 裁剪；ABC 与落子热区一致 |

选课编号以清单中的 `course_code` 为准；稳定 source ID / page 是夹具定位权威。只提取渲染所需的点位和最小合法题型，不复制 990 道题及答案树到测试文件。用原始与 `kiosk19` 两组代表片段，防止把适配坐标当成原始坐标。

棋子上的编号与该夹具的预期交叉点中心及棋子图像中心比较，不查找点击热区：`puzzle` 在已有棋子处不会生成热区。字母基线的实际效果以 Task 3 的浏览器测量为准。

- [ ] **Step 3:** 运行聚焦回归，预期全部通过，答案判定、已有课程流程和裁剪行为无回归：

```bash
cd /Users/fan/.config/superpowers/worktrees/katrain-admin-console/ogs-board-label-alignment-20261119/katrain/web/ui
npm test -- src/kiosk/tutorial/OgsCourseBoard.test.tsx src/kiosk/pages/OgsCoursePages.test.tsx src/kiosk/tutorial/ogsExercise.test.ts
```

### Task 3: 同尺寸真实预览与用户确认

**Files:** 默认不增改文件；若出现可复现的字体裁切，只在 `OgsCourseBoard.tsx` 范围内作最小调整。

- [ ] **Step 1:** 用现有真实课程预览和 1024×600 viewport 重开 7.4 第1步，使用实际 Kiosk 字体和棋子样式。对照用户参考图，保存修复前后同尺寸画面，做一张并排和一张叠加对比；核对棋盘几何、文字中心、层级及文案。保持静音，不播放视频音频。
- [ ] **Step 2:** 浏览器实测 A/B/C 的文字包围盒中心与交叉点中心的差值（用 `getBBox()` 和 `getScreenCTM()` 同一坐标系转换）。水平、垂直误差均不超过 **0.1 格**，且文字清楚指向唯一交叉点。检验基线与字体实际效果，不能仅看 SVG 属性或自动测试通过。
- [ ] **Step 3:** 只补看上表中的 9路边缘、13路白子编号、19路两位编号，以及一个黑子编号例子（2.15 `bp-ko` 第1步，page167，黑子 C5 / [2,4] 上的 `1`）。确认居中、不裁切、描边可读、不遮挡触控。相邻 shape 符号与临时实体盘 `×` 各看一个现有例子，防止局部样式误伤；未证实的其他符号问题另列，不扩大本次修复。
- [ ] **Step 4:** 在截图题上实际点击 A 对应交叉点，确认走 H4 并依旧判对；B/C 保留各自 H3/J3。用一个原题已有的错误分支验证错误提示、重试和步骤切换。保留观察选择题原有作答方式。
- [ ] **Step 5:** 把上述真实预览提供用户确认。全量 990 步由清单与共同渲染路径覆盖，不做 990 轮截图/模型审核。若字体及屏幕像素舍入仍有偏差，修正同一组件后仅复测受影响样本。

### Task 4: 构建、提交与后续发布边界

**Files:** 只提交本修复实际修改的组件和测试；保护当前工作区其他音视频相关改动。

- [ ] **Step 1:** 在干净的修复工作树中运行现有严格 Kiosk 构建，预期构建及校验退出码为 0：

```bash
cd /Users/fan/.config/superpowers/worktrees/katrain-admin-console/ogs-board-label-alignment-20261119/katrain/web/ui
npm run build:smartbox-kiosk-2d
```

不把主工作区未提交的音视频改动打入修复包。

- [ ] **Step 2:** 检查局部 diff，仅精确暂存本修复文件；聚焦代码审查和用户预览通过后提交：

```bash
cd /Users/fan/.config/superpowers/worktrees/katrain-admin-console/ogs-board-label-alignment-20261119
git diff --check
git diff -- katrain/web/ui/src/kiosk/tutorial/OgsCourseBoard.tsx katrain/web/ui/src/kiosk/tutorial/OgsCourseBoard.test.tsx
git add katrain/web/ui/src/kiosk/tutorial/OgsCourseBoard.tsx katrain/web/ui/src/kiosk/tutorial/OgsCourseBoard.test.tsx
git commit -m "fix OGS board annotation alignment"
```

- [ ] **Step 3:** 发布属于后续实施阶段，遵循项目四步流程：追上 develop 并推送修复分支 → 合入并推送 develop → 更新并推送 SmartBox vendor/katrain 指针 → 部署两台服务器及此次相关 RK3562 前端并核对版本。该修改不需要迁移教程数据库、改答案树或重新传输视频文件。
- [ ] **Step 4:** 部署后在 RK3562 以 1024×600 实机复核 7.4 第1步及一个数字标记样本，静音确认落子与判定；记录发布 commit 和部署版本后方可宣称修复完成。

## 验收标准

1. ABC 及数字标记在所属交叉点或棋子中心清楚显示，不再悬在两条线之间。
2. 看到的标记、触控落点和答案判定使用同一坐标；9/13/19 路及 Kiosk19 适配、裁剪均正常。
3. 题目、初始棋局、来源、答案树、章节及已有视频编排保持原数据语义。
4. 聚焦回归、真实同尺寸预览、用户视觉确认，以及实际部署后的 RK3562 检查分别有明确结果。

## 计划复核记录

2026-11-19 独立计划审查通过。审查中修正了黑子编号样本，并明确棋子上的标记不依赖点击热区进行测试。本记录表示清单和实施计划完成，产品修复尚未执行。
