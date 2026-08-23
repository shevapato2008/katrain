# 围棋 kiosk 对齐共享外壳 · 范围与决策（2026-08-20，Fan 已确认）

目标：把围棋 kiosk 界面对齐到已有的十屏设计稿。**这是搬运，不是重新设计** ——
四棋类里其他三家（象棋/国象/五子棋）已经对齐，围棋是最后一家。

## 0. 设计正本在另一个仓，不在 katrain

| 东西 | 路径（`/Users/fan/Repositories/smartbox-software/superpowers/shared/kiosk-shell/`） |
|---|---|
| **规范**（四棋类共享，1160 行，最高权威） | `kiosk-shell-spec.md` |
| **围棋十屏设计稿**（= Fan 给的 artifact） | `sample-go/go-kiosk.html`（标题「智星盒 · 围棋 · 全模块设计稿 · 样板（十屏）」） |
| **十张参考图**（四图对比的参考物） | `sample-go/shots/01-play.png … 10-settings.png` |
| 共享外壳资产 | `assets/{tokens.css,fonts.css,fonts/}` |

其他三家的对齐实现可直接参照：`smartbox-software/{chess,xiangqi,gomoku}/ui/src/`。
**它们已经对齐，是「对齐后长什么样」的活样本。**

⚠️ 另有六个 `smartbox-software-*` 兄弟工作树（chess-features / xq-resign / gomoku-features …），
每个都有一份 `kiosk-shell-spec.md`。以 `smartbox-software`（无后缀）那份为准，动手前
`diff` 一下确认没分叉。

## 1. 已经做过的部分（不要重做）

`superpowers/tracks/golaxy-ai-ladder-parity/kiosk-design-alignment.md`（542 行）记录了
2026-08-11/12 那一轮 —— 它**只对齐了升降级挡局屏**。已完成的：

- `katrain/web/ui/src/kiosk-shell/` 已从上游抄进来（`tokens.css` 991 行 + `fonts.css` +
  `fonts/` 202 个 woff2 + `go-tokens.css` + `seclabel.css` + `icons/house.svg`），
  `MANIFEST.sha256` **209/209 校验通过**
- 品牌字「智星盒」已接上龙藏行楷（`Header.tsx:148`），闸补了下界
- 颜色**本来就是对的**：`kiosk/theme.ts` 的 jade `#58b57a` / slate `#0f1416` /
  raise `#18211f` / hair `#2b3a35` 与稿子逐字一致

**必读该文档的这几节**（都是踩过的坑，重复踩代价很高）：
§0 问题定位、§4 两个未决开放问题、§7「自动最小尺寸吃掉溢出出路」、§13 刻度不跟着执棋方翻、
§16「按快门前等真像素」、§17.1「任何『不许超过 N』的断言都要问 0 是不是最优解」、
§17.2 反查清单（哪些类该接、哪些不该接）。

## 2. 病灶的精确形状

**颜色对，几何从来没接进来。** 另三家 `main.tsx` 都有：

```ts
import '@shared/kiosk-shell/assets/tokens.css'   // 991 行结构 token
```

围棋 grep **零命中**。抄进来之后也只有 **3 个消费点**：`OptionChips.tsx`、
`KioskAiLadderBlockingPanel.tsx`、`blockingPanel.css`。

反查结论（`kiosk-design-alignment.md` §17.2）：**共享外壳 112 个类，81 个零引用**。
其中 **A 组 = 屏上确实有、但自己手写了一套**，是本轮的主要工作面：

| 组 | 共享类 | 围棋现在用什么 |
|---|---|---|
| 顶栏 | `.kiosk-topbar` + `__logo/__brand/__brand-zh/__brand-en/__rule/__game/__right/__user/__avatar/__clock/__home/__home-icon`（13 个） | `components/layout/Header.tsx` 全手写 |
| 镜像栏 | `.kiosk-console` + `__title/__frame/__sync`（4 个） | `SmartBoardConsole.tsx` 手写 |
| 模式卡 | `.kiosk-card` / `.kiosk-cards` / `.kiosk-card__t` / `.kiosk-card__tile`（4 个） | `pages/PlayPage.tsx` 手写 |
| L1 两栏 | `.kiosk-layout-l1` | `components/layout/KioskLayout.tsx` 手写 |
| 主行动 | `.kiosk-primary-action` | MUI `Button` |
| 悬浮滚动条 | `.kiosk-scrollzone` / `.kiosk-scrollbar` | 原生隐藏滚动条（**规范 §5.2 要求画一条**，未做） |

**B 组（对应的屏还没做）零引用是正常的，不要接。** A 组每一条单独判断，不整批处理。

## 3. 十屏 → 路由映射

| # | 稿子 screen | 路由 | 页面文件 | 本轮 |
|---|---|---|---|---|
| 01 | play 对弈·首页 | `/play` | `pages/PlayPage.tsx` | ✅ |
| 02 | game 对局中 | `/play/ai/game/:sessionId` | `pages/GamePage.tsx` | ✅ |
| 03 | training 训练营 | `/tsumego` | `pages/TsumegoPage.tsx` / `TsumegoCategoriesPage.tsx` | ✅ |
| 04 | units 单元列表 | `/tsumego/:level/:category` | `TsumegoUnitListPage.tsx` / `TsumegoUnitsPage.tsx` | ✅ |
| 05 | puzzle 做题屏 | `/tsumego/problem/:problemId` | `TsumegoProblemPage.tsx` | ✅ |
| 06 | kifu 棋谱 | `/kifu` | `pages/KifuPage.tsx` | ✅ |
| 07 | review 复盘 | `/report` | `pages/ReportsPage.tsx` | ✅ |
| 08 | growth 成长 | **不存在** | **不存在** | ❌ 见决策一 |
| 09 | courses 课程 | `/tutorial` | `pages/Tutorial*.tsx` | ✅ |
| 10 | settings 设置 | `/settings` | `pages/SettingsPage.tsx` | ✅ |

## 4. 决策一 · 成长屏本轮跳过

稿子有这屏（盒内段位 Rank / 升降的规矩 / 能力诊断未接后端 / 按对手强度），但**围棋整条不存在**：
无路由、无页面、`katrain/web/api/` 下 **grep `growth` 零命中**（五子棋、象棋那边有
`test_growth_db.py` / `test_growth_api.py`）。

Fan 2026-08-20 裁定：**本轮跳过**。理由是它是新功能不是改版，带后端；混进来会把一条纯表现层
赛道变成全栈赛道，且卡在后端。**登记成独立赛道，本轮不碰。**

## 5. 决策二 · 稿外五屏只接壳

围棋 kiosk 现有路由比稿子多出五块，稿子没画：
`baipu`（摆谱）、`live`（直播）、`research`（研究）、`cross-platform`（跨平台对弈）、
`vision/setup`（视觉标定）。

Fan 2026-08-20 裁定：**只接壳，不重排版式** —— 把顶栏 / Dock / L1 两栏这层共享壳接上，
让它们不再是视觉孤岛；**内容区维持现状**。

⚠️ 明确不做：不照规范 §5 自己推导这五屏的版式。**没有稿子当依据，四图对比就没有参照物，
那等于我自己发明设计。** 有版式疑问就停下来问，不要自行决定。

## 6. 硬闸

- **`.kiosk` 作用域**：`tokens.css` 整份定义在 `.kiosk { … }` 里。渲染到 `.kiosk` 外面，
  `var()` **静默求空**、字体掉回 sans、`color-mix` 整条作废，**且不报错**（国象踩过）。
  用到这套 token 的子树，根节点必须挂 `.kiosk`。
- **两个变量 `tokens.css` 不定义**：`--paper` 和 `--accent-soft`，必须由棋类补
  （`go-tokens.css` 已经赋了值）。漏掉就是上面那条静默求空。
- **kiosk 构建边界**：`npm run build:kiosk-2d` 必须绿（禁 three.js / `@react-three/*` /
  `/galaxy/*` / `/record`）。同时跑 `npm run build`，共享领地改动两边都受影响。
- **类型检查**：`npx tsc --noEmit` **是空的**（根 tsconfig `files: []` + references）。用 `npx tsc -b`。
- **承重实测**：改的是外观 token 不是盒子链，但**改完余量数一定会变**，四图和余量表都要重打。
  规范 §5.2 那条悬浮滚动条是新增承重面，`overflow-y:auto` + `scrollTop` 真能推那条闸不能丢。
- **取图**：按快门前等真像素（§16 那条竞态曾被误判成回归）。设备基准 **1024×600**。

## 7. 已裁定（Fan 2026-08-20 授权自决：「相似功能的模块尽量和其他三种棋类的 kiosk 界面保持一致」）

原来这两条挂着「不许自己定」。Fan 把裁量权交回来了并给了判据 —— **去看那三家同一个模块
怎么做的，照做**。两条都这么定出来的：

1. **破坏性按钮的长相 → 照抄五子棋。**
   三家里只有五子棋在 `.kiosk-actions` 里真摆了「认输」这颗键，而且**类名和围棋设计稿
   一模一样**（`gomoku/ui/src/play/GameRail.tsx:373` 的 `className="danger"`，围棋稿
   `go-kiosk.tmpl.html:305` 的 `class="danger"`）。它的样式是一行
   （`gomoku/ui/src/index.css:1619`）：`color: var(--bad)` +
   `border-color: color-mix(in srgb, var(--bad) 35%, var(--hair))` ——
   **形状、尺寸、内边距、背景一律不动，只有字色和边框着一点红。**
   稿子上 `.danger` 零样式不是「设计意图是不区分」，是稿子没写全。
   ⇒ 详见计划 **D7**。二次确认框本轮不新造（稿子没画）。

2. **挡局时左边画不画盘 → 画，但画空盘 + 一行说明，不摆起始局面。**
   国象把这条规矩写在 `chess/ui/src/shell/BoardConsole.tsx` 的注释里：
   「**不画局面**：盒子上还没有传感盘，盘面数据一个字节都拿不到，摆一个开局局面上去
   就是拿装饰冒充状态。空盘 + 一行说明，才是今天的真相。」它渲染的是 `EMPTY_FEN`。
   **围棋现状已经就是这个形态**：`SmartBoardConsole.tsx` 传 `moves ?? []` 给 `LiveBoard`
   （真盘面网格、零颗子），叠一条 `实时预览暂不可用 · no live feed`。
   ⇒ 参考图上那个完整开局局面是**样张**，不搬。这条登记为预期差异。
   ⇒ 详见计划 **D11**。

## 8. 基线（2026-08-20，动手前实测）

**判据从此是「基线 diff」，不是「全绿」** —— `lint` 和单测本来就是红的，按文件名判
「看着不相关」会把自己造的污染归给既有噪声。

| 项 | 基线 | 怎么复现 |
|---|---|---|
| `npm test` | **1 个文件红 / 1 条红**，1233 通过、5 跳过（共 1239） | `cd katrain/web/ui && npm test` |
| 那一条红是谁 | `src/kiosk/__tests__/GamePageEngine.test.tsx` → `confirming resign from the error dialog fires the resign action AND closes the error dialog`（`mockClearPhysicalEngineError` 期望 1 次实得 0 次） | — |
| `npx eslint .` | **315 problems（258 errors / 57 warnings），178 个文件** | `npx eslint . \| tail -3` |
| `npx tsc -b` | **绿**（注意：不是 `tsc --noEmit`，根 tsconfig 是 `files: []` + references，`--noEmit` 检查 0 个文件） | — |
| `npm run build` | **绿** | — |
| `npm run build:kiosk-2d` | **绿**，末尾 `✅ kiosk boundary clean` | — |
| `src/kiosk-shell/MANIFEST.sha256` | **209/209 OK**（Task 6 之后应变 290） | `shasum -a 256 -c MANIFEST.sha256 \| grep -c ': OK$'` |

⚠️ **计划里写的「3 个文件红 / 6 条红」是过期的**：那三条多出来的红是
`ReportsPage.test.tsx` / `ReportsPage.polling.test.tsx` 的 `Test timed out in 5000ms`，
**跟机器负载走，不稳定**。连跑两遍确认过：稳定复现的只有上面那一条。
⇒ Task 16 重写 `ReportsPage` 时，别拿「它们绿了」当功劳，也别拿「它们红了」当回归 ——
先看是不是又超时了。

### 已知的「负载相关」不稳定名单（会随机在全量跑里变红，单独跑绿）

同一族毛病，判据一律是**单独跑一遍**，绿就不算回归：

| 文件 | 观察到的红 | 取证 |
|---|---|---|
| `src/kiosk/pages/ReportsPage.test.tsx` | `Test timed out in 5000ms`；2026-08-20 全量跑里还见过 `selects an imported game when it is present after current-page reconciliation` | 单独跑 **22/22 全绿** |
| `src/kiosk/__tests__/ReportsPage.polling.test.tsx` | 同上 | — |
| `src/galaxy/pages/tutorials/TutorialFigurePage.test.tsx` | 2026-08-20 Task 5 全量跑里红 `saves narration text without regenerating audio`；**单独跑却红在另一条** `lets the user edit narration and regenerate audio` | 连跑 3 遍单独跑 **2/2 全绿×3**；`src/galaxy/` 本轮一个字没动 |

⚠️ **两次红在不同的用例上**，这本身就是「不是我改坏的」的证据形状：确定性的破坏会稳定命中同一条。

`~/.katrain/config.json` 已备份到 `~/.katrain/config.json.bak-20260820`
（`python -m katrain --ui web` 退出时会重写它）。

---

## 9. 收尾（2026-08-23，Task 20）

### 9.1 十三屏重画完了，另外十四屏仍是「外壳已接」

`sample-go/build.py` 的进度带就是这张表的正本（可点击原型每屏都标着）。
本轮重画：**01 对弈 · 05 对局 · 11 训练营 · 12 单元 · 13 题目 · 14 做题 · 15 棋谱 ·
16 棋谱详情 · 19 复盘 · 20 复盘报告 · 23 课程 · 27 设置**（十二屏），
另加 **D2 稿外五屏只接壳**（摆谱 / 直播 / 研究 / 跨平台 / 标定）。

**没排到的十四屏**：02/03/04 开局设置、06 在线大厅、07/08/09/10 跨平台四屏、
17 摆谱、18 直播、21 研究、22 成长、24 课程书目、25 课程小节、26 标定。
它们在 MUI 图标白名单里按 (A)/(B) 两类各自注明了理由。

### 9.2 「重跑四图零字节变化」这条验收**前提不成立**

计划 Task 20 Step 3 要求重跑全部四图、确认零字节变化，「有变化说明有非确定性」。
2026-08-23 实测：重跑一遍，**27 个 PNG 全变**。查下去不是非确定性的 bug，是
**抗锯齿抖动**——拿 `01-play--implementation.png` 新旧两张逐像素比：

| 量 | 值 |
|---|---|
| 差异像素 | **135 / 614,400（0.02%）** |
| 最大通道差 | **9 / 255** |
| 差异分布 | 包围盒 `[28,10]–[998,580]`，**散落全图**（不是某一块内容变了） |

⇒ 字体栅格化在两次进程之间有 ±9 的亚像素抖动。**「零字节」这个判据本身用不了。**
能用的替代判据两条，都比它强：
1. 四图闸每次跑都打印 `both / refOnly / implOnly` 三个数——**内容变了这三个数会变一个量级**，
   而抖动只让它们动几百（实测 15-kifu 抖了 258，占 0.8%）。
2. 承重和契约那两组闸本来就是逐像素量真浏览器的，它们才是「实现和代码同步」的证明。

这一轮那 27 个 PNG 的改动**已撤回**——它们不携带任何信息。

### 9.3 D4 的答复（计划要求动手前先核实的那一条）

**逐手数据里有「第二名着法评分」**：`report_task_moves.top_moves` 是十个候选，
每个带 `winrate` / `score_lead` / `prior`，`endpoints/reports.py:85` 原样吐出；
第 N 手的候选在**第 N−1 行**里。⇒ 第三格照稿子写「妙手」。

但更要紧的是：**妙手根本不用 `top_moves`** —— 仓里早有一份口径
（`reportModel.ts:192` / `cron/analysis_repo.py:185` / `live/models.py:67`，
都是 `delta_score >= 2`）。国象把妙手撤成「漏着」的理由**转不过来**：
它的分析跑在盒子自己身上（噪声 45cp），围棋的报告是 cron 离线跑的。

### 9.4 本轮**没做**的（每条都写清判据）

| 没做的 | 判据 |
|---|---|
| 成长屏 | D1：独立赛道 |
| `ResearchPage` 三条手写面包屑条 | 864 行、四个渲染分支、三处结构各不相同，动它超出「接壳」。**第三次登记** |
| 木纹贴图 `--oak` | D6：那张图不在共享资产包、不在 MANIFEST 管辖内，抄它等于往仓里塞一份没人核的二进制 |
| `.kiosk-wip.have` 的蓝不跟 `--info` | G2：上游的事 |
| `.kiosk-tag--live` 该提上游 | 「直播中」不是胜负也不是警告，共享的四个 tag 里没有它的位置 |
| 刻度轨道那条**不变式**该提上游 | 「刻度带的节距必须等于盘的线节距」——本轮在 `TsumegoBoard` / `GoBoardSvg` / `LiveBoard` 上各实现了一遍 |
| `immersive` 抽顶栏与规范 §5 铁律 1 冲突 | Task 4 登记；本轮**在屏 20 上修掉了那一处**（它留下一条 56 高的空带），其余四屏照旧 |
| 训练营「每日一题」 | Task 12：稿子没画 |
| 单元列表「已掌握判据」那句话 | Task 13：规范要求但稿子没画 |
| 上游 `MANIFEST.sha256` 本身的 sha256 | Task 6 |
| `.kiosk-slider` / `.kiosk-swatch` 仍无第一个消费者 | Task 18：它们要调的设置项本身不存在 |
| `AiLadderStatusCard` 还没重画 | Task 18：它只在点开对话框之后才出现 |
| `SOURCE_LABEL` 三份拷贝 | Task 15：合并要动 galaxy |
| `GameHistoryPage` 已无入口 | 计划建议并进 `ReportsPage`，**落地前要跟 Fan 确认**；本轮只做了复盘屏那一半（它现在列的就是全部对局） |
| RK3562 上板走查 | Task 20 Step 6：**要板子**，没做 |

### 9.5 稿子这一轮被实现反过来纠正的地方（该提上游）

| 屏 | 稿子写的 | 实际 |
|---|---|---|
| 19 复盘 | 行尾只有一个状态标 | 规范 §11 要四态各有各的样子 + 就地干活不跳页；国象稿子同处画的就是「标 + 药丸键」 |
| 19 复盘 | 这一屏没画搜索 | **稿子自己的 `.sbox` 注释把复盘列进了「有搜索的四屏」** |
| 19 复盘 | 第三张卡「接口还没有 · 即将上线」 | 两条导入路都在跑 |
| 19 复盘 | 旁注「升降级局下完也不给复盘」 | 没有任何实现；带 ranked 闸的是**对局进行中**的选点白灯；国象稿子明写两者同一条复盘线 |
| 23 课程 | 同时画三张分类卡和「现在能练的」 | 那两块按定义不共存（环里的「—」说明还没对过账） |
| 23 课程 | 组标题右端「每类几本，由接口返回」 | 那一格按规范放的是**数据** |

## 10. 补上那两个时间戳（2026-08-23）

§9.4 里那条「`ReportTaskStatus` 不吐时间戳」和 §9.5 里那条「20 报告 · 用了 6 分 12 秒」
**已销账，两行都从表里删掉了**——它们说的是同一件事的两头，现在两头都不成立了。

### 改了什么

| 层 | 改动 |
|---|---|
| 契约 | `ReportTaskStatus` + `_task_to_dict` 吐 `started_at` / `completed_at`（ISO 8601，可为 null） |
| 后端 | `POST /reports/{id}/retry` **两个章一起清**，不只是 `completed_at` |
| 前端 | `ReportTaskSummary` 跟着加两个 `string \| null`；屏 20 的 `.rhead` 副行按稿子写「每手算 N 次 · 用了 D」 |
| 共享 | `kiosk/utils/durationLabel.ts`——`durationLabel` 从 `ResearchPage` 抽出来（现在两个消费者），另加 `elapsedSeconds` |

**表结构没动**：两列一直都在，cron（`report_analyze.py:188/232/287`）一直在写，
少的只是 `_task_to_dict` 那两行。

### 为什么 `/retry` 也要清 `started_at`

cron 认领时写的是 `started_at = started_at or now()`——**粘的**。而 `/retry` 只受理
`status == "failed"` 的任务，也就是已经把 `MAX_RETRIES` 用完了的；这种任务可以在
那儿躺一夜再被人点重试。只清 `completed_at` 的话，下一次跑完算出来的跨度会把那一夜
算进去，屏上就是「六分钟的分析用了 14 小时」。清掉之后 cron 下次认领重新盖章，
这一对的含义收敛成「**这一轮尝试**跑了多久」。

### 拿不到就不写，这一条没变

`elapsedSeconds` 在三种情况下返回 `null`，屏上退回「每手算 N 次 · M 手」那句本来就真的话：
① 两个章任一为空（云端还没更新的盒子就是这一档）；② 解析不出；③ **算出负数**——
那意味着两个章的时钟对不上，写「用了 0 秒」是编的。三条各有一条闸，变异实测都会红。

### 承重反查：触发了，量下来不受影响

副行文字变长会不会动到下面那块自己滚的重点手列表？**先写死期望再读数**：

| 量 | 期望 | 实测 |
|---|---|---|
| `.rhead` 高度（短行「40 手」） | —— | **60** |
| `.rhead` 高度（长行「用了 128分36秒」） | 与短行相等 | **60** |
| `.rhead` 高度（强行顶成两行） | 与短行相等 | **60** |
| 两行时 `p` 底边 − `.rhead` 底边 | ≤ 0（不许溢出卡片） | **−4px** |
| `railOverflow` / `navBottom == railBottom` | ≤ 0 / 相等 | 既有断言，绿 |

⇒ `.rhead` 是 `height:60px; flex:none` + 内容 `align-items:center`，副行长短既不长高
也不溢出，滚动区可用高度不随这一行变。**量出来是「不受影响」，就没有新的承重断言要留**
——第一版写过一条「副行不许换行」，理由写的是「`.rhead` 会跟着长高」，实测把这个理由
证伪了，于是降成 `console.log` 记录。硬留一条理由是假的闸比没有更坏。

留下的那一条是**另一回事**：几何闸的 fixture 里那两个章带了断言
（`progressText` 必须含「用了 128分36秒」），守的是「这组几何量的是不是最坏那一档」——
谁把 fixture 里的章删掉，下面整组断言会悄悄退回去量短行，而且照样全绿。

### 两份 fixture 造的数据故意不一样

四图闸造 `6分12秒`（**对齐稿子**，那一关看静止一帧对不对）；
几何闸造 `128分36秒`（**最坏那一档**，那一关量交互之后对不对）。
四图那三个计数因此从 `both=35704 refOnly=29694 implOnly=28565`
变成 `both=35810 refOnly=29588 implOnly=28655`——**refOnly 掉的 106 全进了 both**，
就是稿子上那行字终于在实现里有了对应的墨。

### 还差一处：数字两侧的空格

稿子写「用了 6 **空格** 分 12 **空格** 秒」，实现写「用了 6分12秒」。同一行里
「每手算 2000 次」是留空的，所以这是**行内不一致，稿子是对的**。没改的理由：
`research:time_min_sec` 这个 msgid **三处共用**（galaxy 研究屏、kiosk 研究屏、这一屏），
另两处是**每秒跳的 ETA 计数**，紧凑反而更合适；改它要动 11 个语言，
另铸一套并存的键则是给同一个概念留两套约定。**为一句话的字距，两条路都比这处差值贵。**
真要改，走 `katrain-i18n-expert`，和别的 `review:*` 键（本分支铸的 20 多个键
**目前一个都不在 PO 里**）一起做一轮。

### 顺手修的一个不在计划里的东西

`ReportDetailPage.tsx` 里有两个**裸 NUL 字节**——`join('\0')` / `split('\0')` 那对分隔符
写成了字面量而不是转义。运行时完全正确（`tsc -b` 一直是绿的），但它让整个文件被
判成 binary：`grep -I` 静默跳过，**返回空结果而不报错**。查这一轮的改动点时就在这儿
吃过一次假的「没有匹配」。改成 `'\u0000'`，语义不变。全仓扫过，只有这一个文件中招。

## 11. D2「稿外五屏」那条裁定的前提**已经不成立**（2026-08-23 查明）

D2（§5）写的是「摆谱 / 直播 / 研究 / 跨平台 / 标定，**稿子没画这五屏**，
没有参照物就没有四图闸，所以只接壳」。那是按**十屏稿**裁的。

8-21 那轮稿子扩到 27 屏时，这五屏**全部画进去了**，参考图也全出了：
`sample-go/shots/` 下 **27 张一张不缺**（`01-play.png` … `27-settings.png`，
含 `17-baipu` / `18-live` / `21-research` / `26-calib` / 跨平台四屏 / `22-growth`）。
逐张看过 `02-setup-free` 和 `21-research`：都是完整画好的屏，右栏俱全，不是占位。

⇒ **剩下的每一屏都有参照物、都能上四图闸。** D2 那条「只接壳」从此只对
「Task 19 当时那一轮」成立，不能再拿它当以后不重画的理由。

### 27 屏此刻的账

| 状态 | 屏 |
|---|---|
| 已按稿重画 **15** | 01 对弈 · **02 自由对弈开局** · **03 升降级开局** · 05 对局 · 05′ 跨平台对局 · 11 训练营 · 12 单元 · 13 题目 · 14 做题 · 15 棋谱 · 16 棋谱详情 · 19 复盘 · 20 复盘报告 · 23 课程 · 27 设置 |
| 只接了外壳 **11** | 04 本地对局开局 · 06 在线大厅 · 07/08/09 跨平台三屏 · 17 摆谱 · 18 直播 · 21 研究 · 24 课程书目 · 25 课程小节 · 26 标定 |
| 还没有这一屏 **1** | 22 成长（D1，需要新建路由/页面，且 Dock 要从六项变七项——是新建不是重画） |

## 12. 屏 02 / 03 开局设置（2026-08-23）

两屏**同一个组件**（`pages/AiSetupPage.tsx`，`:mode` 分岔），所以外壳一起对齐。
右栏从「两列 MUI 下拉 + `overflow:hidden`」整块换成稿子的 `.setgrp` 体系。

### 新写进 `go-screens.css` 的（借类名之前先 grep 过住在哪儿）

`.setgrp` / `.setgrp-scroll` / `.inputgrp` / `.igrow` / `.iglab` / `.igfix` /
`.catpick` / `.catstep` / `.cattrack` / `.catticks` / `.catmeta` / `.setexplain` /
`.ranked-state__stakes` / `.kiosk-optseg .disc`。

共享包里**本来就有、一条都没重写**：`.kiosk-optseg` / `.kiosk-seclabel` + `.secval` /
`.kiosk-opthint` / `.kiosk-side` / `.kiosk-scrollzone` / `.kiosk-primary-action`。
`.ranked-state__stakes` 果然又是住在象棋/国象自己的 `<style>` 里 —— 这是同一个形状的第五次。

### 新构件三个

`shell/KioskOptSeg`（光秃秃的分段控件，行内那种用法要它）、`shell/KioskStepTrack`
（档位轨 `.catpick` + `.catmeta`）、`goBoard.ts` 的 `handicapStones()`。
`components/common/OptionChips` 改成 `KioskSecLabel + KioskOptSeg + hint` 拼出来；
`shell/KioskSecLabel` 的 `en` 从必填放宽成可选。

### 四处「稿子那一处不成立」，都按实现来

> ⚠️ **第一行在 2026-08-23 当天被推翻了，见 §15。** 「全仓没有任何地方能让用户切」是错的
> ——做题屏早就有这颗开关。稿子是对的，那一格现在是两段可选。下表保留原样，
> 因为**错的判据比错的结论值钱**：它示范了「我没找到」被写成「不存在」是什么样子。

| 稿子 | 实际 | 做法 |
|---|---|---|
| ~~「落子」画成「屏幕 / 实体盘」两段**可选**~~ **（已推翻，见 §15）** | ~~`isVisionEnabled` 由后端 `/api/v1/vision/status` 给，**全仓没有任何地方能让用户切**~~ | ~~改成 `.igfix` 读数~~ → 按稿子画成两段可选 |
| 「我执」三项（含**随机**） | kiosk 这一屏和 galaxy `AiLadderRatedSetup` **两处都只给黑白** | 两项。第三项是搬象棋骨架带来的（象棋 ranked 随机是象棋自己的规则） |
| 赌注「胜 · 升到 4 级 / 负 · 退到 6 级」 | `core/ai_ladder_ranked.py:1503-1506`：每局 ±1，**到 ±3 才动档**；而且「升到几级」这块屏拿不到（状态里没有整份阶梯目录） | 按净胜分说话：到点写「升一档 / 退一档」，没到点写「净胜分 +N」 |
| AI 策略五条各配一句说明 | 稿子只写了「拟人」那一条 | 只写那一条。另外四条是**对引擎行为的断言**，仓里没有出处，不编。`.kiosk-opthint` 定高，留空不让下面的组跳 |

另外两处是**贴目档数**（稿子说明里那句「(6.5 / 7.5 / 0)」不是控件规格，实现是
0.5–7.5 共 15 档，收成三档是删功能）和**规则那四条说明**（稿子只给中国规则那一条，
其余三条是围棋常识不是产品声明，照同一口径写下来）。

### 四图当场看出来的两个真 bug

1. **让子局的盘上一颗子都没有。** `KioskSetupBoard` 恒画空盘，注释里的理由写着
   「围棋这一局的起始局面就是空盘」——**那句话只对不让子的那一局成立**。
   规范 §11 明写左边那块盘画的是「按下按钮后**真会出现**的那个局面」。
   补了 `handicapStones()`，算式照后端 `core/sgf_parser.py:374` 那一份；
   实测 19 路 2 子 = `Q16` + `D4`，和稿子那一帧逐点相同。
   **闸点名是哪两个点，不是数个数** —— 数个数的话摆错位置照样绿。
2. **净胜分为负时符号写成 `+-1`。** 无脑前缀 `+`，而负数自己带着一个。
   `net_score = −2` 那条闸当场逮到。

### 一处我自己编的，四图比出来才发现

给升降级那半屏写了一段 `.setnote`。**稿子 03 屏根本没有这一段** ——
该说的话已经在页控条副标和「对手」那组的提示行里说过了。删掉。
**稿子上没有的东西，写出来通顺也还是编的。**

### 承重反查：触发，量了

这一屏**是这一轮才第一次能滚的**（上一版右栏是 `overflow:hidden` 的两列表单，
装不下的后果是裁切不是滚）。闸写在 `kiosk-shell-scroll.spec.ts`：

| 量 | 期望（先写死） | 实测 |
|---|---|---|
| 右栏宽 | 460 | 460 |
| 滚动区溢出量 | > 100（没造出溢出，下面都是空的） | 造出来了 |
| 真滚轮拨十二下后 `scrollTop` | > 0（程序化能滚 ≠ 拨得动） | > 0 |
| 滚到底剩余 | ≤ 1 | ≤ 1 |
| 最后一组「用时」下缘 | ≤ 滚动区下缘 | 成立 |
| `railOverflow` | ≤ 0（溢出该由滚动区吃掉，不能顶破右栏） | ≤ 0 |
| 「开始对局」底边 | = 右栏底，且**滚前滚后同一个数** | 相等 |

**变异演示做了三次，前两次不红**：`.setgrp-scroll` 去掉 `flex:1`、`.setgrp` 从
`flex:none` 改成 `flex:1` —— 都绿。查下去这条链是**共享外壳在扛**
（`tokens.css:531` 的 `.kiosk-scrollzone { min-height: 0 }`），我新加那两条 CSS 不承重。
第三次把主行动键挪进滚动区，当场红在「滚过之后主行动键动了」那一条 —— 闸是活的，
守的是**那件事**，不是我那两条 CSS。

### 屏 03 剩一块**没换壳**（登记）

「对手」那一格实现里仍是 `AiLadderSetupOpponent`（MUI 框）。它手上是六种诚实状态：
加载 / 出错重试 / 定级赛进度 / 已定档 / 档位不可挑战 / 未认证档试坐 / 成绩在途，
而稿子只画了「已定档」那一种。换壳要把六种都搬过来，**而它同时是 galaxy 那屏的消费者**
（`galaxy/pages/AiSetupPage.tsx:557`），在原地改样式会把另一家一起改了。

### 稿子这一屏有一处上一轮**该改而没改到**

03 屏那行提示写「提示、形势判断、**复盘**一律封掉」。2026-08-23 已经查明后端那道闸
（`interface.py:877` 的 `ANALYSIS_ACTIONS`）关的是**对局中那棵树上的动作**，
离线报告走另一条路。那一轮说「规范、围棋稿、计划书三处一并更正」——**只改到了复盘相关那两处，
这一屏漏了**。实现按更正后的口径写「变化图」。**稿子待改（在 smartbox 仓）。**

### 顺带统一的一处

主行动键文案：稿子四个里三个是「开始对局」、一个是「开始计分局」，而实现三屏都写
「开始对弈」（`t('Start Game', …)`，PO 里就是这个词）。**三屏一起换成 `setup:start`**
（屏 02 / 04 本地对局 / 09 跨平台人机）—— 只改一屏会留下「02 说对局、04/09 说对弈」的分叉。
`Black Stone` / `White Stone` 两个键也另铸：PO 里那两条是「● 黑」「○ 白」，
那个圆点是接外壳之前拿字符当棋子用的，现在子由 `.disc.b` 画，再借那条 msgid
屏上会出现「● 执黑」两颗子。契约闸（`t(key, 中文默认值)` 不许和 PO 说两回事）当场逮到这三条。

## 13. 四图取图**依赖真后端** —— §9.2 那次全量撤回把这件事盖住了（2026-08-23）

跑完全量视觉闸后照例比存档，发现两张不是抖动：

| 屏 | 差异像素 | 最大通道差 |
|---|---|---|
| 05 对局 | **212 952 / 614 400（34.660%）** | 253 |
| 15 棋谱 | 616 / 614 400（0.100%） | 214 |

**先证明不是这一轮的回归**：把改动全部摘掉、拿 HEAD 自己的代码跑一遍，
得到的是**一模一样的 212 952**。⇒ 存档在 HEAD 上就已经落后 34%。

### 根因：`/assets/img/*` 走代理到 :8001，而视觉这一套不起后端

`playwright.visual.config.ts` 不起 Python 后端；`components/Board`（canvas）要的
`B_stone.png` / `W_stone.png` / `board.png` / `inner.png` / `topmove.png` 全是
ECONNREFUSED，于是它画出**一块空盘**——木纹和子一颗都没有。
而 `helpers/fourup.ts` 的 `stubShellAssets` **只 stub 了 logo 一张**。

四图闸**照样报绿**：它跑完、打印三个计数、不判阈值。
这就是 §9.2 自己写下的那句话反过来咬了一口——「后端起着就绿、一停就红的东西不叫闸」，
**取图同理：一张随后端在不在而变的实现图，不是这一屏的实现图。**

⇒ `stubShellAssets` 改成把六张图一起从仓里喂进去。修完屏 05 的差从
**34.660% 收到 0.218%**，`both` 从 42 274 涨到 48 993（`refOnly` 掉的 6 719 全进了 `both`）。

### §9.2 那条「PNG 全撤回」的判断**对了一半**

「抗锯齿抖动」那部分是真的（27-settings / 19-review / 20-report 这一轮量到的最大通道差
分别是 1 / 1 / 5，纯抖动）。但**一刀切撤回，把 05 对局那 34% 的真差一起撤了** ——
存档因此在「后端起着」的那一版上冻了半年。
判据补一条：**撤回之前先量最大通道差**——个位数是抖动，两百多是内容。

### 还欠一条（登记）

翻译表也走后端（`/api/translations` → `server.py:2111`，读的是编译好的 `.mo`）。
没后端时 `t()` 全部回退到默认值：屏 05 因此写「chinese 规则」「KataGo · 5k」而不是
「中国规则」「5 级」——修完贴图后剩下的那 0.218% 就是它。
**屏 02 / 03 不受影响**：这两屏的 `t()` 默认值本来就是中文（那是本分支铸新键的写法），
回退和不回退是同一句话。要根治得在 `helpers/fourup.ts` 里解 cn PO 喂给
`/api/translations` —— 那是另一件事，本轮不做。

### 这一轮的存档口径

本赛道 `visual/` 下**只提交屏 02 / 03 两个新目录**；其余被全量跑改脏的一律
`git checkout HEAD --` 撤回（它们这一轮没改过内容，而且是在贴图缺失的环境下拍的，
比存档更差）。修完贴图之后重拍 05 / 15 是**另一次的事**，且要等翻译表那条也解决，
否则拍出来仍然带着英文回退。

## 14. 屏 04 本地对局 · 开局设置（2026-08-23）

和屏 02/03 同一副骨架（左盘 516 + 16 + 右栏 460，右栏整栏滚，主行动键钉栏底），
**但是另一个页面组件**（`pages/PvpLocalSetupPage.tsx`）。它上一版根本没接过外壳：
左边是 `LiveBoard`、右边一整套 MUI（`TextField` × 2、`Slider` × 4、`Switch` × 2）。

差别是这一边**没有引擎对手** ⇒ 没有棋力、没有 AI 策略、也没有「我执」；
多出来的是**两个姓名输入**——四家里只有围棋有，因为面对面下完要记谱，谱上得有名字。

### 复用，没有新构件

`KioskOptSeg` / `KioskStepTrack` / `KioskSecLabel` / `KioskScrollZone` / `KioskPagebar` /
`KioskSetupBoard` / `handicapStones()` / `.setgrp` 那一族 CSS，全部来自屏 02/03 那一轮。
新写的只有 **`.nameinput` 一条**（稿子那颗「点此输入」药丸的可输入版本）和
**`utils/setupOptions.ts`**（用时七档 + 规则四条说明，从 `AiSetupPage` 原样搬出来）。

提 `setupOptions.ts` 的理由**不是「看着通用」，是它们是契约**：用时每一档写死了送给后端的
四个字段（`time_enabled` / `main_time` / `byo_length` / `byo_periods`），
各屏各抄一份的话，改一档要记得改三处，而漏改的那一处**不会红**，
只会让某一屏悄悄送出另一套时限。

### 稿子这一屏有**四处**不成立，都按仓里的事实写

| 稿子 | 实际 | 出处 |
|---|---|---|
| ~~「落子」两段**可选**~~ **（已推翻，见 §15）** | ~~同屏 02：`isVisionEnabled` 用户切不了~~。**稿子是对的**：它现在是真开关，而且 `PhysicalBoardGuard` 那条理由恰好反了——守卫会挡人，正说明这颗开关必须接到守卫上 | `KioskApp.tsx:95`、`components/vision/PlayInputGuard.tsx` |
| 「白方 · **贴目**的一方」 | **反了。** 贴目是**黑方贴给白方**的，白方是**收**的那一方 ⇒ 写「后行 · 收下贴目的一方」 | `core/game.py:372`：黑棋分数 `- self.komi` |
| 「不接引擎，没有提示也**没有形势判断**」 | 前半句对、后半句不对。`pvp_local` **不在** `SCORING_GAME_TYPES` 里 ⇒ `analysis_allowed` 为真，对局屏那颗**「领地」照样能按**，而领地就是形势判断。真正关掉的是**胜负走势图**（`evalAllowed` 把两人局排除）和 **AI 支招**（`hintVisible` 要求 `game_type === 'free'`） | `interface.py:253/261`、`GameControlPanel.tsx:113`、`GamePage.tsx:451` |
| 「段位只有**在线大厅的定级队列**会改」 | 定级赛不在在线大厅，在**「升降级对弈」**——在线大厅那句挡人的话原文就是「先在『升降级对弈』打完 5 局定级赛」。权威是 `RANK_MOVING_GAME_TYPES = ("ai_ladder_ranked",)`，注释逐字写着「Exactly one, by design」 | `LobbyPage.tsx:151`、`interface.py:258` |

后两条都在同一段 `.setnote` 上。**这类文案是最容易编的一类：它说的是别的屏上的事。**
两句都改成有出处的版本，并留了一条闸盯着（`note` 里不许出现「形势判断」和「在线大厅」）。

### 稿子上有、实现里做法不同的一处（不是错，是静态稿画不出来）

「点此输入」在稿子里是一颗 `.kiosk-btn--pill`。真页面上它**必须真能打字** ⇒
换成 `<input class="nameinput">`：同高 26、同圆角、同描边、同字号，宽度放到 116
（药丸只装得下那四个字，输入框还要装得下人名）。
**不做「点药丸弹一层输入」**——那是稿子上没有的一层流程，而且弹层正好盖住左边那块盘。

留空时送出去的是**空串**，后端因此不写 SGF 的 `PB`/`PW`，对局屏回落到「黑方 / 白方」。
**前端不替用户编名字**——编出来的名字会被写进棋谱。屏上那句「留空就记成『黑方 / 白方』」
和送出去的载荷得对得上，两边各有一条断言。

### 承重反查：触发，量了，而且**变异证明它量的是屏 04 自己**

这一屏也是这一轮才第一次「能滚 / 主行动键钉得住底」。原来那条只跑屏 02 的闸
**参数化成两屏各跑一次**（`SETUP_SCREENS`）：它们共用 `.setgrp` 那套类，
但**骨架各自手写**——屏 04 完全可能把主行动键写进滚动区里，而屏 02 的那条闸对此一无所知。
**同一条承重链上可以有不止一处断点；判据能转，结论不能转。**

变异：把 `PvpLocalSetupPage` 的主行动键搬进 `<KioskScrollZone>` 里边 ⇒
屏 04 那条当场红在「`ctaBottom` 没贴着右栏底」（586 → 530），而**屏 02 那条照样绿**。

### 棘轮往下走了三格

- `MUI_ICON_BASELINE` 摘掉 `PvpLocalSetupPage.tsx`（`PlayArrow` / `ArrowBack` 换成外壳）
- `PO_OVERRIDES_DEFAULT_BASELINE` 摘掉它的 `Black` / `White` 两条（另铸
  `setup:black_side` / `setup:white_side`：PO 里那两条是「黑棋 / 白棋」说的是**子**，
  这里说的是**人**）；同一条名单里 `Byoyomi only 30s x3` **跟着文件搬**到
  `utils/setupOptions.ts`，不是新漂的
- `eslint src/kiosk` 从 108 降到 **107**（顺手清掉那个测试文件里的 `as any`）

### 四图三计数

`04-setup-local both=39432 refOnly=22347 implOnly=28491`（两次跑一模一样）。

## 15. 「落子」那颗开关：我把稿子判错了，Fan 一句话问回来（2026-08-23）

Fan 看四图时问：「相比参考图，为什么最终实现都没有屏幕选项？」

### 错在哪

屏 02 我写的判据是：

> `isVisionEnabled` 由后端给，**全仓没有任何地方能让用户切它**。照画就是摆一个戳不动的旋钮。

前半句成立（`VisionContext` 只有 `refreshStatus`，没有 setter，3 秒轮询一次后端）。
**后半句是错的**：`TsumegoProblemPage.tsx:626` 有一颗 `role="switch"` 的「实体棋盘」，
偏好持久化在 `tsumegoUnits.ts:116` 的 `kiosk_tsumego_physical` 里，
而且**正是稿子画的那个语义**——开要看条件、关永远允许、旁边一行说明为什么开不了。

这条错误的形状是**「我没找到」被写成了「不存在」**：我 grep 的是 `isVisionEnabled` 的
消费者，而那颗开关根本不叫这个名字——它是**另一个位**。

### 真实的形状是三段，我塌成了一段

| 段 | 是什么 | 谁说了算 |
|---|---|---|
| ① 这台盒子能不能 | `visionStatus.enabled && recognitionReady`，外加这一局是不是 19 路 | 后端 + 这一屏的路数 |
| ② 这一局想不想 | 用户偏好 | **`utils/playInput.ts`（这次新加）** |
| ③ 实际落在哪 | ① 且 ② | 派生 |

第一版的 `.igfix` 读数只答得出 ③——它**不是假话**，但它把 ② 整个抹掉了，
而 ② 在别的屏上明明存在。**判据错了，结论碰巧不假，这比结论假更难发现。**

### 接法：三个地方，缺一个就是半截开关

1. **`utils/playInput.ts`** —— 偏好 + 那个三段合成函数。
   **和做题屏是两把键**，因为两边默认值必须相反：做题默认关（要主动选），
   对弈默认**开**（盘就摆在面前，而且那正是这次改动之前的行为 ⇒ **纯增量**）。
   硬凑一把键的话总有一家默认值是错的，而错的那一家不报错，只会静默把人放到另一块盘上。
2. **`components/vision/PlayInputGuard.tsx`** —— 对局那四条路由外面。
   `PhysicalBoardGuard requireRecognition` 本身没错，错的是它**被无条件套在对局上**：
   人在开局设置屏刚选了「屏幕」，进来还是被推去标定工作台。
   **不改 `PhysicalBoardGuard` 自己**——做题屏也用它，而做题的偏好是另一把键。
3. **`GamePage`** —— 14 处 `isVisionEnabled` 全部换成 `physicalPlay = isVisionEnabled
   && playOnBoard && 19 路`。偏好**只在挂载时读一次**：这一局落在哪儿是开局那一刻定的
   （屏上写着「开局后不可改」），中途跟着 localStorage 变会把人从一块已经摆着子的盘上赶下来。

### 顺带发现的第二个「我自己编的」

第一版把说明行做成常驻。**稿子 03 屏那一组到「路数」那行就结束了，没有说明行** ——
常驻会把它下面每一组都往下推一行。四图当场量出来：`refOnly` 从 10283 涨到 **12152**。
改成「计分局只在实体盘那段灰掉时说话」之后降到 **10052**，比原来还低。
**这是上一轮「给升降级编了一段 `.setnote`」的同一个错，隔了一天又犯一次。**

### 三屏四图都变好了（同一台机器、同一组桩，只差这一处）

| 屏 | both | refOnly | implOnly |
|---|---|---|---|
| 02 自由 | 38526 → **38775** | 22275 → **22026** | 26994 → **25784** |
| 03 升降级 | 52691 → **52922** | 10283 → **10052** | 15472 → **13895** |
| 04 本地 | 39432 → **39511** | 22347 → **22268** | 28491 → **26419** |

九个数**没有一个变差**。

### 证明它是纯增量

屏 05 对局的实现图重跑：**87/614400 像素变化，最大通道差 5** ——
按 §13 补的那条判据（个位数是抖动、两百多是内容），`GamePage` 那 14 处改完之后
默认路径**画出来的东西一模一样**。变异也做了：把 `hardwareFault` 那一处改回
`isVisionEnabled`，新加的那条当场红。

## 16. 扫描类的闸要说清扫的是代码还是文本（2026-08-23，判据从象棋那支转过来）

象棋那支在他们自己的树上实测出来一条：新加的扫描闸把示例代码写进了**自己的
docstring**，于是变异还原之后它照样红——**扫描面没说清是代码还是文本，散文就会被当成缺陷。**

反查本仓：`kiosk-shell-contract.spec.ts` 里三条闸，**三种不同的扫描面**——
闸三早就抹注释了，闸一按行粗判（`t.startsWith('*') / '//' / '/*'`），闸二**扫生文本**。
同一个文件里三种，本身就是味道。

### 转的是判据，不是他们的做法

他们连**字符串字面量**一起抹掉，因为他们找的是 `now + 900` 那种**算术**。
这里两条闸找的东西**恰恰住在字符串里**——`from '@mui/icons-material'`、`height: '50vh'`——
照抄会让两条闸一起变成永远绿的空闸（这就是「闸量错了对象」那条）。
⇒ 统一成一个 `codeOnly()`：**只抹注释，不动字符串**。

### 今天还没被咬到，但棘轮受不起这一下

先量了一遍：现有基线里**没有**「只在注释里命中」的条目，两条闸今天是干净的。
修它是因为**假红的收场方式特别坏**：两条闸都是 `toEqual` 的单向棘轮，
一个干净文件被报成缺陷，最可能的处理是「加进白名单」——棘轮从此永远带着一条不成立的账，
而棘轮只许缩。而我写的中文注释里天天出现这两个字符串。

### 四条分支各跑过一次

| 变异 | 新扫描面 | 旧扫描面（HEAD） |
|---|---|---|
| ① 真代码 `height: '50vh'` | **红** ✔ | 红 |
| ② 块注释里 `height: 50vh,后来撤了` | **绿** ✔ | **红**（多出 `utils/playInput.ts`） |
| ③ 真 `import { Gear } from '@mui/icons-material'` | **红** ✔ | 红 |
| ④ 行注释里「别从 `@mui/icons-material` 引图标」 | **绿** ✔ | **红**（多出 `shell/KioskOptSeg.tsx`） |

②④ 那两列右边是**同一处变异在旧扫描面上重跑**出来的——不是推的，是量的。
②暴露的正是旧写法的具体漏洞：按行判注释漏掉「块注释里不以 `*` 开头的中间行」。

## 17. 屏 06 在线大厅 —— 稿子照国象重做（2026-08-23，Fan 裁定）

Fan：「按照国际象棋的界面设计做对战大厅的设计。」

### 国象那一组在哪

**不在仓里。** 国象大厅是**八屏**（05L/05M/05N/05O/05P/05Q/05R/05S），只活在一个已发布的
artifact 里（`fbc085e7-1cae-4f3b-82c2-ed5808d017c2`），`sample-chess/README-lobby-screens-debt.md`
记的就是这笔债：「仓库里 grep 不到这八屏，找的人会以为它不存在，而实现是照着它做的」。

⇒ 我把围棋这一组**写进了 `sample-go/go-kiosk.tmpl.html` 正本**，`build.py` 能重建、
`gate.mjs` 能扫、`shots/` 有图。**那笔债不欠第二次。**

### 先查家底：围棋大厅接的是谁

| 数据 | 出处 |
|---|---|
| 在线棋友 | `GET /api/v1/users/online` → `User{id,username,rank,elo_points,avatar_url}` |
| 进行中的对局 | `GET /api/v1/games/active/multiplayer` → `session_id / player_b(名字) / player_w(名字) / spectator_count / move_count` |
| 匹配 · 邀请 | `ws /ws/lobby`（`server.py:2285`）：`start_matchmaking{free\|rated}` / `stop_matchmaking` / `invite` / `accept_invite` → `match_found` / `invitation` / `lobby_update` |

**三个入口全在 katrain 自己的进程里** —— 围棋**不走**共享大厅平台
（`lobby-platform/api/lobby_api/lobby_ui.py:14` 原话：「围棋不在内：它不接共享后端（D1），
大厅屏由 katrain 自己托管」，`LOBBY_UI_GAMES = ("chess","xiangqi","gomoku")`）。
⇒ 象棋那支报的 reaper / `claim_stall` 激励反向，**围棋不存在**——不是修好了，是那套机制没接。

### 照搬要改的四处，每一处都是「围棋给不出国象那个数」

| 国象 | 围棋 | 做法 |
|---|---|---|
| 大厅只有一种对局（自由，不计等级） | 有**两种**：`game_type: free\|rated`，rated 要先定级（`server.py:2337 PLACEMENT_REQUIRED`） | 主行动上面加一条分段；未定级时排位那段**灰掉 + 一行说明为什么**（和开局设置三屏同一条规矩） |
| 对局卡上双方带「等级 + 等级分」 | `/games/active/multiplayer` 只回**两个名字字符串** | 换成**执黑 / 执白** —— 那是这个接口唯一多给出来的事实，而且观战第一眼要认的就是哪边执黑 |
| 棋友行四态 + 我的状态下拉 + 已关注 + 四个筛选标签 | `/ws/lobby` 没有 set-status，全仓没有 follow，也没有可筛的维度 | 都不画；状态只留**算得出的两态**（空闲 / 对局中，后者靠比对左栏的名字） |
| 房间有钟（15+10） | `create_multiplayer_session(pb,pw,b_name,w_name)`（`server.py:2360`）**不带任何时钟参数** | 一个字都不写时限。**不是「不限时」，是没有那个字段** |

外加一处**国象有、围棋不能照画**：邀请的 60 秒倒计时。围棋的 `invite` 只是把消息转给对方
（`server.py:2402-2427`），**没有 TTL、没有撤回、没有拒绝** ⇒ 收到邀请那屏**不画进度条**：
画一条走完就归零的条，而后端在归零时什么都不做，那是拿动画伪造一个不存在的裁定。

### ⚠️ 这一屏依赖的后端契约（画了，今天喂不出来）

**段位那一列。** `/users/online` 回 `User.rank` / `User.elo_points`，而全仓**没有任何一处写
这两个字段**（`UPDATE users SET` 只出现在 `billing.py`，改的是 credits）⇒ 每个人恒为
「20k / 0」，实现里那句 `rank==='20k' && !elo → 无段位` 等于把整列写死成一个词。
围棋**有**真段位，它在阶梯那张表里（`ai_ladder_ranked.has_ladder_rank`）。
⇒ **这一列上线的前提是 `/users/online` 去 join 一下阶梯，不是前端凑一个数。**

另两条同类，都在屏上标了：「拒绝」今天只能本地关弹窗（没有 decline 消息）；
观战有数据通路（多余的 session socket 就是观众）但**没有路由和只读盘**。

### 闸抓到的四条几何问题（都是真的，都改了）

| 闸报的 | 真浏览器量出来的 | 改法 |
|---|---|---|
| `[lobby-match/inbox] cdlg 超 14` | `.cdlg{inset:0}` 一路找到 `.kiosk-content`（带 14px 上下内边距）⇒ 弹层 544 高、中间区只有 516 | `[data-screen^="lobby"] .kiosk-layout-a{position:relative}` —— 它是**弹层的定位原点**，不是装饰 |
| `[lobby-guest] rsecond 内容被裁 3、rail 被裁 2` | **我自己加的 44px 触控伪元素**把 40 高的按钮撑破了 | 把 `.rsecond` 自己做到 44，伪元素撤掉。**能把盒子做够就别拿伪元素凑** |
| `[lobby-guest] 空带 72` | `align-self:start` 让面板吊在上半屏 | 栏铺满，靠共享的 `.rrule{margin:auto 0 0}` 把按钮顶到栏底 |
| `[lobby] gamelist 空带 258` | 只画了 2 局 | 标 `data-grows`（闸的正式逃生口：「会随对局长满」）**并且**把稿子填成 5 局 —— 标了闸放行不代表稿子该画成空的 |

### 稿子自己对不上的两处（填完列表才露出来）

计数还写着「2 局 / 6 人」而列表已经 5 局 / 14 人；木木和一只鸽子在左栏正在下棋、右栏却写「空闲」。
**实现正是拿左栏的名字去比对右栏算这个状态的**，稿子自相矛盾，照着做的人不知道该信哪一份。
⇒ 两份对齐，三个模态屏的背景也统一成主屏那一份（上一版三屏各写各的）。
顺带定了一条排序：**名单按「能不能邀请」排，空闲的在上面** —— 忙起来的盒子上，
20 个「对局中」压在前面就得滚到底才找得到能约的人，而这一屏存在的理由就是找人。

### 状态

`build.py` 重建通过（27 → **30 屏**：06 / 06b / 06c / 06d），`gate.mjs` **799 条全过**，
`shots/` 出了四张新参考图。**稿子在 smartbox 仓，尚未提交** —— 等 Fan 看过。

### 顺带查实一条：在 `sample-go` 里「下游存档图全变了」是**取图位移，不是内容变**

插进三屏之后，`shots/` 里 **22 张下游图全部变脏，最大通道差 ~223** —— 按 §13 那条判据
（个位数=抖动、两百多=内容）该判成「内容变了」。查下来不是：

1. **先排除「图本来就旧」**：把 tmpl / build.py / gate.mjs 摘回 HEAD 重跑一遍，
   `shots/` **逐字节复现 HEAD 的存档**（只剩我那三张新的未跟踪）。图不旧。
2. **签名很干净**：`01-play … 05-game`（插入点**之前**）**一张都没变**，
   `07 … 27`（插入点之后）**全变**。
3. **差在哪**：`07-platform` 的变化像素铺满全图（10.03%），而变化最多的几行是
   **y=110–113 和 y=1198–1201 的整宽行**（2048/2048 像素）—— 那是边框整条挪了，
   也就是**整屏在纵向偏了不到一个像素**。
4. 内容本身逐眼看过是对的（还是那三张平台卡、那三条能力标签）。

⇒ 原因：闸是按元素截图的，2× DPR 下元素的绝对 Y 一变，**亚像素相位就变**。
我在 06 后面插了三屏，后面每一台设备都下移了 —— 于是它们的截图全部重采样一遍。

**补一条判据（`sample-go` 专用）：这个仓里往中间插屏之后，「插入点之后的图全变」是预期的，
而 §13 那条最大通道差**分辨不出它** —— 半像素位移落在白字深底上照样打到 223。
真正能分辨的是**插入点签名**：改动点之前的图必须一张都不变。变了才是事故。
（顺带:这也意味着**不能拿存档图的稳定性来查这个仓的回归** —— 任何加字的改动还会
重新子集化字库,66 面 → 70 面、65 面字节不同,那是另一条同向的噪声源。）

---

## §18 屏 06 在线大厅 —— 实现（2026-08-24）

Fan 看过四张稿子后放行（「可以」）。稿子已提交进 smartbox `main`（`b40fa8f99`，未推），
实现按它做。四帧的四图产物在 `visual/06-lobby/1024x600/`。

| 帧 | 路由 / 触发 | both | refOnly | implOnly |
|---|---|---|---|---|
| 06 主屏 | `/kiosk/play/pvp/lobby` | 21306 | 21716 | 17541 |
| 06b 未登录 | 同上，无 token | 15391 | 9328 | 6921 |
| 06c 匹配中 | 点「开始匹配」 | 10309 | 13579 | 9628 |
| 06d 收到邀请 | 服务端推 `invitation` | 14712 | 11822 | 6977 |

### 和稿子的四处不同，每一处都写在四图标签带里

1. **段位那一列没有实现。** 这是本屏唯一一处「实现比稿子少」。理由就是 §17 登记的那条契约：
   `/users/online` 回的 `User.rank` / `elo_points` 全仓没有任何一处写（`UPDATE users SET`
   只在 `core/billing.py` 改 credits，`models_db.py:75` 的默认值 `"20k"` 从注册那天起没动过）。
   今天照画只有两种结果：每个人恒显「20k / 0」，或按现有那句 `rank==='20k' && !elo → 无段位`
   把整列写死成一个词 —— 而**定过级的人会被这一列说成没定过级**。位置和宽度稿子里定死了
   （`.rk`，62px，名字之后第一格），`/users/online` join 上阶梯就补。
2. **06d 那行小字改了。** 稿子写「不接受就一直挂着 —— 邀请没有期限」只说了一半：后端连
   decline 都没有，这颗「拒绝」只关掉本地这个窗、对面收不到任何东西。⇒ 写成
   「拒绝只关掉这个窗 —— 对面收不到回音，邀请也没有期限」。
3. **06d 副行去掉「业余 3 段 · 」。** `invitation` 只有 `from_id` / `from_name` / `mode`。
4. **06b `fact` 那行小字改了。** 稿子那句承诺的正是第 1 条里没上的段位列。

### 稿子注释里一句错的，已在提交里改掉

「全仓没有 follow」——**接口是有的**（`/api/v1/users/follow/{username}`、`/users/following`，
galaxy 的 `FriendsPanel` 在用）。真实理由是**盒内一个入口都没有** ⇒ 关注集恒为空，
拿它做筛选是一个永远筛不出东西的标签。结论没变，理由换成成立的那一个。
（这和 8-23 屏 02/04 那次是同一个形状：**「我没找到」写成了「不存在」**。）

### 实现过程中量出来的三个错

1. **无限刷新。** `useTranslation()` 的 `t` 每次渲染都是新函数，写进 `useCallback`/`useEffect`
   依赖 ⇒ `/ws/lobby` 那个 effect 每帧重跑：新开 socket、新起定时器、再拉一次两个列表 →
   setState → 再渲染。表现是四图那一步 `waitForLoadState('networkidle')` **永远等不到**。
   ⇒ effect 里一个 `t` 都不留：失败存布尔、通知存事件，译文渲染时才求（顺带修好「切语言后
   屏上还留着上一种语言那句」）。
2. **hooks 顺序错（旧代码就有）。** 「没登录就早退」写在一部分 hooks 中间，`/ws/lobby` 那个
   `useEffect` 排在它后面 ⇒ 访客那一帧比登录那一帧少注册一个 hook，同一个组件实例上登录一次
   当场抛 `Rendered more hooks than during the previous render`。已把早退挪到所有 hook 之后。
3. **认不出的行会白屏。** `await res.json()` 是 `unknown`，`as ActiveGame[]` 只是让类型检查闭嘴；
   少一个 `session_id`，`.slice(0,4)` 当场抛，而这一屏上面没有 error boundary。
   `navigation.integration.test.tsx` 真的这么炸过（它那个兜底 fetch 对所有 URL 回同一份分类数组）。
   ⇒ 整行丢掉：认不出的行本来也没法观战。

### 承重结构实测（真浏览器 1024×600，造到 12 局 / 20 人）

这一屏是这套外壳里**第一处「同一屏两个滚动区」**。判据先写死再读数，全部在
`tests/kiosk-shell-scroll.spec.ts` 尾部两条：

| 量什么 | 关系式 | 实测 |
|---|---|---|
| 该滚的是谁 | 两个 `.kiosk-side__scroll` 各自 `scrollHeight > clientHeight` | 都 > 100 |
| 手指拨得动吗 | 在左栏上派发 12 次真滚轮 ⇒ 左栏 `scrollTop > 0` **且右栏 == 0** | 成立（反向同样成立） |
| 两条拇指各回各栏 | 左栏拇指 `right < 右栏 left` | 成立（变异后跳到 **1005**） |
| 栏没被顶破 | `.lobbycol` 自己 `scrollHeight - clientHeight <= 0` | 两栏都 ≤ 0 |
| 主行动键 | 高 48、`bottom == 栏底`、滚过不动 | 成立 |
| 弹层没被裁 | `.cdlg` 高 == `.kiosk-layout-a` 高，且 `bottom <= .kiosk-content bottom` | 516 / 586 |

**变异记录（三条真跑过、一条没红）**

- `.gamelist.kiosk-scrollzone{position:static}` ⇒ 「左栏拇指跑到右栏」当场红，右缘 < 548 → **1005**。
- 去掉 `.lobby-layout{position:relative}` ⇒ 「弹层不是布局根那么高」红，`cdlg` 高 **516 → 544**。
- 去掉 `roster` 的 `sort` / 把访客早退挪回 hooks 中间 ⇒ 单测两条各自红（后者报的正是那句 React 错）。
- **没红的一条**：稿子多一条 `.kiosk-primary-action{flex:none}`（理由「名单一溢出主按钮被压成 24」），
  去掉它 `cta.h === 48` **照样绿**。原因是实现这一屏的列表用共享 `KioskScrollZone`
  （`.kiosk-section--grow{flex:1; min-height:0}`），空间全由它让出来，栏本身从不溢出。
  ⇒ **那条 CSS 没有照抄**：抄一条挡不住任何东西的规则比没有更坏，下一个读到它的人会以为
  这儿有过一个已经被治住的故障。高度断言留着，但注明它今天**没有红分支**。

### 一处几何是照着参考图补的，不是审美

稿子里组标题和列表是 `.lobbycol` 的两个兄弟，中间隔着栏距 12，**外加**组标题自己的
`margin-bottom: 6`；搬进 `KioskScrollZone` 之后两者同属一节，只剩那 6。
表现是**上面对不齐、下面对得齐**（底下几块钉着栏底不动，只有列表白多出 12 的高度）。
补回 `margin-top: var(--rail-gap)`，渐隐起点跟着下移同样多。
补之前 both=12628 / refOnly=30394，补之后 **both=21306 / refOnly=21716**。

### 顺带清掉的

- `src/kiosk/__tests__/LobbyPage.test.tsx`（旧 6 条）**删除** —— 它测的是旧版面
  （「张三 (B) vs 李四 (W)」「观战」按钮），每一条的意图都被新的
  `src/kiosk/pages/LobbyPage.test.tsx`（14 条）覆盖且更严。同一个页面两份同名测试是重复陷阱。
- 契约闸两条名单摘掉 `LobbyPage.tsx`：MUI 图标那条，和 PO 名单里它那**九条**
  （`lobby:title` 源码写「在线大厅」、cn PO 却是「多人游戏大厅」—— 九条全是这个形状，
  重画时逐条换成了这一屏自己的新 key）。

### 基线 diff（判据是名字集合，不是条数）

- **vitest**：新增红 **0**。稳定红只有既有那条 `GamePageEngine … resign from the error dialog`
  （在 HEAD 上同样红）；`ReportsPage … 计分局下完了照样能分析` 在全量跑里两边**各红过一次**，
  是既有的跨用例串扰，不是本轮引入。
- **playwright**：26 红，**两边完全同一批**（`comm` 名字集合空差）。它们要真引擎 / 真登录，
  这台机器上 `local: error_502`。
