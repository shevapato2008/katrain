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

| 稿子 | 实际 | 做法 |
|---|---|---|
| 「落子」画成「屏幕 / 实体盘」两段**可选** | `isVisionEnabled` 由后端 `/api/v1/vision/status` 给，**全仓没有任何地方能让用户切** | 改成 `.igfix` 读数（虚线边），照实说这一局会落在哪儿 |
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
| 「落子」两段**可选** | 同屏 02：`isVisionEnabled` 用户切不了。这一屏尤其不能画成可选——本地对局那条路由外面套着 `<PhysicalBoardGuard requireRecognition>`，盘没标定过时进去的是**标定工作台**，不是对局 | `KioskApp.tsx:91`、`components/vision/PhysicalBoardGuard.tsx` |
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
