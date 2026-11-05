# Kiosk 首页「历史对局」字号对齐 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 RK3562 围棋复盘首页的「历史对局」从遗留 12.5 px 对齐到棋谱首页标题的 22 px，并聚焦核对其他一级首页同角色标题。

**Architecture:** 只在复盘页现有 `personal-games-reviewed` 作用域内补标题字号和容纳文字所需的标题行高度。继续使用现有 `KioskSecLabel`、滚动区和字号设置机制，不改全局标题默认值、数据契约或页面行为。

**Tech Stack:** React 19、TypeScript、现有普通 CSS、Vite；用浏览器实际布局验证。

**Status:** 仅计划。待 ROOT 统一独立 Astra max 计划审（最多两轮）后，由 SDD 实施并完成独立 Astra max 代码审；本计划阶段不改产品、不部署。

---

## Chunk 1: 一个复盘首页的局部字号修正

### 已核实的依据与边界

- 隔离 worktree：`/private/tmp/katrain-home-section-heading-plan-20261105`。
- 分支：`plan/kiosk-home-section-heading-size-20261105`；已 fetch 的 `origin/develop` 基线为 `fb916f12516dd510080fb736a48a825dc206bc37`。
- 该 worktree 通过 `--no-checkout` 创建并显式 sparse checkout 安全源码路径；未访问、遍历、stat 或以 git status 检查 `data/kifu-album/`。后续仍须遵守此边界，保留其他 worktree 的改动。
- 已使用 `ui-ux-pro-max`，读取现有 `docs/design/KIOSK-UNIFIED-REDESIGN-RULES-2026-10-14.md`。沿用已有 18 / 22 / 28 px 层级，不新建设计系统。
- 用户口述的棋谱首页「职业对局」，当前源码对应 `KifuPage.tsx:181` 的职业棋谱标题（翻译键 `kifu:professional_library`）；`kifuLibrary.css:88` 明确为 22 px。这里只采用该字号参照，不改文案。
- `ReportsPage.tsx:454` 的「历史对局」仍使用 `KioskSecLabel`。`kiosk-shell/seclabel.css:11` 给它 12.5 px，`personalGamesReviewed.css` 没有新版覆盖。已有复盘设计 `docs/design/kiosk-unified/personal-review.css:45` 的同角色标题也使用 22 px。
- 2026-11-05 RK3562 只读 CDP：当前 `/kiosk/report`，1024 × 600，字号设置 `large`，搜索已展开。标题实际为 12.5 px、行高 15.625 px、字距 1.5 px；标题行高 20 px。没有导航、改 DOM、改登录或改棋局。
- 保留实机参考 `/private/tmp/katrain-home-heading-before-20261105.png` 与 computed style `/private/tmp/katrain-home-heading-before-20261105.json`；参考图仅本地使用，不把用户棋局截图加入仓库。

### 聚焦检查的其他首页

| 首页 / 同角色文字 | 已有源码事实 | 本项决定 |
| --- | --- | --- |
| 棋谱：「职业棋谱」 | `pages/kifuLibrary.css:88`，22 px | 作为参照，保留 |
| 复盘：「历史对局」 | `shell/KioskSecLabel.tsx` → `kiosk-shell/seclabel.css:11`，12.5 px；实机一致 | 修为 22 px |
| 对弈：人机对弈 / 人人对弈 / 跨平台对弈 / 对局历史 | `kiosk-shell/play-redesign.css:35`，已批准新版布局明确为 20 px；顶部主标题 28 px | 记录差异，保留现有设计；不将不同布局强制统一 |
| 训练营：首页「训练营」 | `pages/trainingReviewed.css:49`，28 px | 已有大标题，保留；不扩展到二级题型/题目页 |
| 成长：「盒内段位」 | `kiosk-shell/go-screens.css:516`，22 px；次级走势 18 px | 已有层级，保留 |
| 课程：「围棋入门」/「课程目录」 | `tutorial/ogs-course.css:17,26`，28 px；课程名 22 px | 已有大标题，保留；教材二级页不纳入 |
| 设置：各设置组标题 | `kiosk-shell/go-screens.css:1322`，22 px | 已有大标题，保留 |

这次不改英文副标、局数、卡片状态、辅助说明、隐藏的「生成报告」标题或全局 `seclabel.css`。不新增字体 token、标题组件变体或业务 fixture。

### Task 1: 局部标题样式与一次代表性预览

**Files:**
- Modify: `katrain/web/ui/src/kiosk/pages/personalGamesReviewed.css:21` 附近的复盘滚动区规则。
- Read only: `katrain/web/ui/src/kiosk/pages/ReportsPage.tsx:454`、`katrain/web/ui/src/kiosk/pages/kifuLibrary.css:88`、`katrain/web/ui/src/kiosk-shell/seclabel.css:11`、`katrain/web/ui/src/kiosk-shell/tokens.css:561`。
- Test files: 不新增；纯局部 CSS 改动按用户比例原则使用 focused 布局检查和一个真实 React 运行时预览。

- [ ] **Step 1: 确认基线并实施最小 CSS**

将现有 `.personal-games-reviewed .kiosk-section--grow{min-height:0}` 扩展为下列局部规则（按现有文件风格排版）：

```css
.personal-games-reviewed .kiosk-section--grow{
  min-height:0;
  --l1-sec-label-h:30px;
}
.personal-games-reviewed .kiosk-section--grow>.kiosk-seclabel{
  align-items:center;
}
.personal-games-reviewed .kiosk-section--grow>.kiosk-seclabel h2{
  font-size:22px;
  letter-spacing:0;
}
```

30 px 容纳现有字体 22 px 的正常行高；使用既有 `--l1-sec-label-h` 让标题行和滚动渐隐起点同步，避免只放大字却仍塞进 20 px 行。选择器限于复盘历史滚动区，不改变隐藏区块或其他页面。保留现有字体、字重及字号设置自动测量逻辑。

- [ ] **Step 2: 做最低充分的源码检查**

在隔离 worktree 执行：

```bash
git diff --check -- katrain/web/ui/src/kiosk/pages/personalGamesReviewed.css
git diff -- katrain/web/ui/src/kiosk/pages/personalGamesReviewed.css
```

预期：无空白错误，产品 diff 仅含上述复盘局部规则。不新增自动化测试层，不运行全站 four-up 或全量回归；若 ROOT 统一集成已做一次 Kiosk 构建，复用该结果，不为本项重复构建。

- [ ] **Step 3: 一个 1024 × 600 真实运行时预览**

在本地真正运行的 React 页面查看 `/kiosk/report`，使用与实机参考相同的 `large` 字号和搜索展开状态。需要匿名数据时仅复用现有预览测试的 route fixture，不把数据写进生产源码；不导航或修改用户当前 RK 页面。

一次聚焦检查：

1. 用 `getComputedStyle` 确认 `.personal-games-reviewed .kiosk-section--grow>.kiosk-seclabel h2` 为 `22px`，字距 `0px`；标题行是 30 px，文字完整落在行内。
2. 确认标题、英文副标、右侧局数和放大镜互不重叠；搜索框、三条历史记录、分页及导入入口仍在原有栏内可见。只检查当前代表状态，不全状态重拍。
3. 保留一张相同 viewport 的实现截图，与上述实机参考在同一位置对看字号、基线和顶部间距；不同棋局内容不作为视觉差异缺陷。若工具链阻塞，只做一次合理修复或用更简单的浏览器方式完成此检查，不扩大任务。

预计历史区只多占 10 px 垂直空间，底部分页和导入区仍固定。若代表预览发现裁切，仅调整这组局部行几何，不重排页面或缩小其他文字。保持现有字号档位机制，不用 `!important` 或手改 `data-kiosk-base-size` 绕过。

实施预览补充：22 px / 30 px 标题行使三张卡片的可视区少了 6 px。ROOT 已批准把本页现有 `.personal-games-pagination` 高度从 52 px 调为 46 px，保留 44 px 按钮、导入入口和其他布局；代表预览验证三张卡及按钮焦点完整。这是上段允许的局部几何回归修正，产品仍仅一个 CSS 文件。

- [ ] **Step 4: 交付与提交**

将唯一产品文件的 diff、focused 检查结果和一张代表预览交给 ROOT 做要求的独立 Astra max 代码审。通过后按 ROOT 的统一交付流程提交；不得自行部署，也不追加第二套审查或全站截图流程。

建议产品提交消息：`align review home heading size`。
