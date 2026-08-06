# galaxy 网页端改版 · 实施计划（历史计划，待重写）

> **2026-08-06 用户确认后的权威规格：**
> `docs/superpowers/specs/2026-08-06-galaxy-board-template-ladder-design.md`
>
> 本计划中的 S0 worktree 是可行性实验，不能直接合并；字体、品牌、左栏折叠与首个页面顺序均已改变。
> 后续实施计划必须依据新规格重新生成。

> 2026-08-06 · 依据 `design.md`（本目录）与设计稿
> https://claude.ai/code/artifact/80e082f4-d9e9-4e7b-82ad-0439bb7e0b4f
>
> **状态：S5 已完成并自验；S0–S4 等待视觉确认。**
> 按用户级 CLAUDE.md，四图对比 + 明确确认之前不进入 S0–S4 的实现阶段——那几个切片改的是
> 设计稿本身还没被确认的结构，抢跑就是等着返工。S5 是纯词表修复，**与视觉方向无关、
> 无返工风险**，所以先做掉了。S0 的 0.1/0.2 另外还卡在 `design.md` §3.2 的正文字体决策上。

---

## 切片划分原则

按**用户旅程**切，不按技术层切。每个切片结束时产品是真实可部署、状态诚实的。
共享基础只建当前切片需要的最小部分（S0），不提前泛化。

**共享基础未稳定前不并行铺开多个切片** —— S0 动的是 `theme.ts` 与两个新壳层组件，
它一变，后面每个切片都要返工。S0 合并前不开 S1。

---

## S0 · 共享基础（最小）

**目标**：字体真的加载、壳层有顶栏、模块牌有组件、按钮尺寸有令牌。此切片之后界面已经换了脸，
但没有一个页面的布局被改动。

| # | 做什么 | 文件 |
|---|---|---|
| 0.1 | 字体入库 + `@font-face`（`font-display:swap`） | **`src/galaxy/assets/fonts/`** + galaxy 作用域样式文件 |
| 0.2 | `fontFamily` 改成 WenKai 栈；数字栈单列一个 token | `src/theme.ts:34-46` |
| 0.3 | 新增 `GalaxyTopBar`（52px，品牌 + 全局状态） | `src/galaxy/components/layout/GalaxyTopBar.tsx`（新） |
| 0.4 | `MainLayout` 改成「顶栏 + （左边栏 + 内容）」两层 | `src/galaxy/components/layout/MainLayout.tsx` |
| 0.5 | 新增 `ModulePlate`（返回印 + 标题 + 副标题 + 可选 chip） | `src/galaxy/components/layout/ModulePlate.tsx`（新） |
| 0.6 | 按钮尺寸令牌 48/40/32；先**只加不改**，逐页迁移 | `src/theme.ts` |

**S0 的阻塞项：正文字体策略（2026-08-06 已实测，只差拍板）**

设计稿的 170KB 子集**在生产里不成立**（10 个启用语种 + 运行时才知道的用户名/赛事名/棋手名，
冻结字符集必出豆腐块）。已经拿真字体量过一轮，数在 `design.md` §3.2：

- 中文界面首屏地板 **318.8 KB**；按频次分片实际拉 **324.6 KB**（差 2%）；整套字面 24.5 MB
- **同样切法、只换排序，按码位分片就退化成拉 1951.2 KB**（33/40 片命中）
  —— 分片顺序是成败关键，不是实现细节
- 「按界面用字做一次性子集」是最差解：808 KB **且照样出豆腐块**

**结论：A（频次序 `unicode-range` 分片）可行且推荐**，可行性已不是问题，
剩下的只是「值不值这 325 KB」这一句产品判断。拿到答复再动 0.1/0.2；0.3–0.6 不依赖它。
实现时需要一份汉字频次表（通用规范汉字表一级字表 3500 字）来定分片顺序。

**已排除的风险（复核后撤回）**：我先前担心改 `theme.fontFamily` 会波及 kiosk —— **不会**。
`KioskApp.tsx:125` 用自己的 `kioskTheme`（`src/kiosk/theme.ts`，SANS/SERIF/MONO 独立定义），
MUI 嵌套 `ThemeProvider` 传对象是整体替换而非合并；`zenTheme` 只被 `AppRouter.tsx` 与 `ZenModeApp.tsx` 引用。

### S0 实施记录（2026-08-06，worktree `feature/galaxy-ui-s0`，**未提交未推送**）

工作树：`/Users/fan/Repositories/katrain-galaxy-s0`（主树有 290 条 calibration 脏条目，隔离开做）。

| # | 落点 |
|---|---|
| 0.1 | `scripts/build_wenkai_chunks.py` → 234 片 + 品牌 4 KB + 数字 36 KB，共 **238 文件 / 49 MB** |
| 0.2 | `theme.ts` 导出 `FONT_BODY` / `FONT_NUM` / `BTN`，`fontFamily` 换掉从未加载过的 Manrope |
| 0.3 | `GalaxyTopBar.tsx`（新）52px，品牌 + 全局状态，**不放模块名/返回** |
| 0.4 | `MainLayout.tsx` 两块 → 三块 |
| 0.5 | `ModulePlate.tsx`（新）返回印 + 标题 + 副标题 + chip，`flex:none` |
| 0.6 | 按钮令牌 48/40/32（`BTN`），只加不改 |
| 附带 | 左边栏 240 → 216、删品牌块、`height:100vh` → `100%`、导航区独立可滚 |
| 附带 | 非法务品牌改名 弈航/Galaxy Go → 智星盒（`Dashboard` `LoginModal` + 词表 2 键 × 11 语种）|

**闸的结果**
- tsc 干净；`vitest run src/galaxy` **72 绿**（新增 GalaxyTopBar 3 条）
- 两个 build 绿；**kiosk dist 22892 KB vs 基线 22896 KB（未增长）**，`wenkai-*` 在 kiosk dist 中 **0 个**
- 承重实测 **10/10 全过**，1440×900 与 1024×768 各一轮，清单见 `s0-loadbearing-checklist.md`
  （先写死关系式再读数；导航注入 40 项灌到溢出后才量）
- 字体**真的在渲染**，不是声明了事：`document.fonts.check('16px "LXGW WenKai"')` = true；
  拉丁串 48px 实测 WenKai 656.9 ≠ 系统 sans 616.4 ≠ Long Cang 541.3
- 分片按需加载被证实：**236 个 face 里只下载 12 个**

**实测推翻了我自己在 §3.2 写的估算**：那里的 325 KB 是**单字重**的数。
页面同时要 400 与 500，实际首屏 **12 个请求 / 约 511 KB**。仍在可接受范围，但账要记对。

**没做的**：`ModulePlate` 建好了但还没挂到任何页面上 —— 挂它就是改页面版式，那是 S1。
S0 之后「界面换了脸，但没有一个页面的布局被改动」这句仍然成立。

**闸**
- `npm run build` 与 `npm run build:kiosk-2d` 都绿
- **kiosk dist 体积不因字体增长** —— 这是「字体没走 `public/`、没走 `main.tsx` 那三个全局 css」的证据。
  记录改动前后 `static-kiosk-2d/` 的体积差。
  ⚠️ **基线必须是同一 commit 上现跑的一次构建，不能拿磁盘上现成的 dist 当基线。**
  `static-kiosk-2d/` 被 `.gitignore:52` 忽略，磁盘上那份可能是任意历史状态构建的。
  2026-08-06 实测：磁盘上的陈旧 dist 是 22068 KB，同一 commit 现构建两次都是 **22896 KB**——
  差的这 828 KB 与本次改动无关。照旧写法量，会把陈旧基线的差值当成字体引入的回归。
- 承重实测：`MainLayout` 从两块变三块，改的是「可用高度怎么传下去」那条链 —— 触发。
  在 1440×900 与 1024×768 下量：内容区 `clientHeight` = 视口高 − 52；左边栏导航区
  `scrollHeight > clientHeight` 时能滚且滚得动。**量之前把导航项灌到超出**。

**回滚**：0.1–0.2 与 0.3–0.5 可分别独立回滚。

---

## S1 · 对局中（棋盘页样板）

**目标**：把 `design.md` R1 在一条真实旅程上跑通。其余三个棋盘页在 S2 照抄这一版。

| # | 做什么 | 文件 |
|---|---|---|
| 1.1 | 删掉棋盘上方横条 | `galaxy/pages/GamePage.tsx:340-354` |
| 1.2 | 删掉浮在棋盘上的绝对定位提示叠层，内容移进右边栏 | `GamePage.tsx:268-280` |
| 1.3 | 右边栏顶部挂 `ModulePlate`（模块名 + 阶梯段位 + 手数 + 返回） | `components/game/RightSidebarPanel.tsx` |
| 1.4 | 右边栏 500 → 340（xl 380 / md 320） | `RightSidebarPanel.tsx:106` |
| 1.5 | 8 个 `ItemToggle` 瓦片 → 真 `<button>`；显示开关改两列 40px 网格 | `RightSidebarPanel.tsx:156-254` |
| 1.6 | 底部 6 个 `IconButton` 补 `aria-label` | `RightSidebarPanel.tsx:271-323` |

**闸**
- **四图对比**（参考图 / 实现截图 / 并排 / 差异），1440×900 同视口
- 承重实测，先把右边栏内容灌到溢出：
  - 棋盘边长实测 ≈ **828**（设计稿实测值），不是 700
  - 该滚的是 `.x-rail__s` 本身：`scrollHeight > clientHeight`，写入大 `scrollTop` 读回非 0，
    真浏览器派发滚轮后 `scrollTop` 变化不为 0
  - 模块牌与底部动作在滚到底时仍然可见（它们 `flex:none`，不在滚动容器里）
- 无回归：`GamePage.aiLadder.test.tsx` 绿

---

## S2 · 其余三个棋盘页照抄

| # | 做什么 | 文件 |
|---|---|---|
| 2.1 | 研究页：删分析态横条、摆子工具栏与走子条下沉进右边栏 | `ResearchPage.tsx:420-444,596-650` · `components/research/ResearchToolbar.tsx` |
| 2.2 | 死活题：删横条与面包屑，模块牌接手；右边栏 320 → 与其它页一致 | `TsumegoProblemPage.tsx:365-398,405-413` |
| 2.3 | 复盘：删返回+标题行 | `ReportDetailPage.tsx:113-123` |
| 2.4 | 直播 / 棋谱库同样处理 | `LiveMatchPage.tsx:117-124` · `LivePage.tsx:65-69` · `KifuLibraryPage` |
| 2.5 | `LiveBoard` 的 400 硬底：每个调用点传 `minContainerHeight`，或去掉 | `components/live/LiveBoard.tsx:738` |
| 2.6 | 研究页两个状态用两个棋盘组件（`LiveBoard` 400 / `Board` 200）→ 统一 | `ResearchPage.tsx:448,578` |

**闸**：每页一次四图对比；2.5 必须承重实测（矮窗口下棋盘不被裁），
量之前把窗口高度压到 600 以下。

---

## S3 · 内容页与左边栏

| # | 做什么 | 文件 |
|---|---|---|
| 3.1 | 首页加「你的阶梯段位」卡片（档位 / 净胜分 / 最近五局） | `galaxy/pages/Dashboard.tsx` |
| 3.2 | 左边栏补「首页」入口；导航区独立可滚；身份块 `flex:none` | `GalaxySidebar.tsx:49-57,60-69` |
| 3.3 | 段位读 `ai_ladder_rung`，不读 `users.rank` | `GalaxySidebar.tsx:167,172` |
| 3.4 | 对局 hub 三张卡不等大；升降级卡带段位 | `PlayMenu.tsx` |
| 3.5 | 升降级设置页：三列（阶梯 / 账本 / 条件）；「不计入」升成整屏状态 | `AiSetupPage.tsx` · `features/aiLadder/AiLadderSetupOpponent.tsx` |

**闸**：3.2 承重实测（窗口高 600 时底部身份块可达）；其余四图对比。

---

## S4 · 响应式

| # | 做什么 |
|---|---|
| 4.1 | 应用根挂 `container-type:inline-size`；四档规则按 `design.md` §7 |
| 4.2 | 左边栏 ≤1199 收成 64 图标条 |
| 4.3 | 右边栏 ≤1199 收到 320；<900 落到棋盘下方；左边栏变底部标签栏 |
| 4.4 | 删掉两处「宽度不够就整块消失且无替代入口」 | `LivePage.tsx:111` · `HvHLobbyPage.tsx:310` |
| 4.5 | 竖屏档坐标默认关闭（开关保留） |

**闸**：四个宽度档（1536 / 1200 / 900 / 430）各一次四图对比 + 承重实测。
实测清单见 `design.md` §7 的棋盘边长表，那些数字是设计稿量出来的，实现要对得上。

---

## S5 · 词表与 i18n 收敛 ✅ 已完成（2026-08-06）

**先做了全量审计**，不再按最初那张凭印象列的清单办事。审计脚本比对「源码里 `t('…')` 请求的键」
与「en.po 里真有的 msgid」，排除测试文件与模板字符串动态键：

```
UI 请求的不同键 993 → 词表里没有 377
  其中 kiosk 独占        315   ← 不属于本 track
      shared/components   38   ← 不属于本 track
      ZenModeApp            4
      kiosk+shared          6
      galaxy 相关          13   ← 本切片范围
```

**galaxy 的真实缺口是 13 个键，不是最初写的 6 个**；反过来 377 这个总数也说明
「i18n 已经做完了」是错的。缺键的后果是渲染 `t()` 的第二参数，而两边错得方向相反：
galaxy 侧写死英文（`t('ok','OK')`、`t('common:cancel','Cancel')`），
kiosk 侧写死中文（`t('common:cancel','取消')`）——前者对中文用户漏英文，后者对英文用户漏中文。

| # | 做了什么 | 结果 |
|---|---|---|
| 5.1 | `common:cancel` / `common:retry` 补进词表 | ✅ 两个键此前**根本不在 en.po**，6 处调用全在吃兜底 |
| 5.2 | 「清空/清除」统一 | ✅ `live:clear` 由「清除」改「清空」，与 `research:clear`/`report:clear` 一致 |
| 5.3 | `ok` / `accept` / `reject` | ✅ 补齐；`GamePage:333`、`GameRoomPage:261,262` 不再恒显英文 |
| 5.4 | `GameRoomPage.tsx:166` 写死的 `Back to Lobby` | ✅ 改走已存在的 `game_room:back_to_lobby`（同文件 :234 早就在用） |
| 5.5 | 写死英文串 | ✅ `ChatPanel`（标题 + 输入框占位）、`AudioPlayer`（播放/暂停/音频不可用）；两个组件都补了 `useTranslation()` 钩子 |
| — | 审计额外发现 | ✅ `Tutorials` `Stone Effect` `3D` `tsumego:loadError` `tsumego:noData` `research:cancel_*` `research:continue_analysis` |
| 5.6 | 清理孤立 `ladder:*` 键 | ⛔ **不做**，见下 |

共 19 个键 × 11 语种写进 `scripts/batch_translate_galaxy.py` 并编译。
**闸**：审计脚本复跑 → galaxy 缺键 **13 → 0**；`tsc --noEmit` 干净；`vitest run src/galaxy` 69 绿；
两个 build 都绿且 kiosk 边界校验通过。逐键读**编译后的 .mo**（不是 .po）确认没有回落到键名本身。

**两件实测出来的事实**（都与最初的假设不符）：
- **实际启用的是 10 个语种，不是 11。** `i18n.py:19` 有 `INACTIVE_LANGS = ["es"]`，
  西班牙语的 .mo 根本不编译。es 的译文照写进 .po 备着，但别指望它在运行时生效。
- `tsumego:loadError` 原来的兜底文案是
  `Failed to load tsumego data. Please run: python scripts/sync_tsumego_db.py`
  ——把运维命令摆给终端用户。已按「从用户这一侧写」重写，代码里的兜底同步改掉。

**5.6 为什么不做**：52 个（不是 54）`ladder:*` 键确实没有引用，也确认了没有 `` t(`ladder:${…}`) ``
这类动态拼键。但它们是 `ladder:your_rank`、`ladder:placement_progress`、`ladder:to_promote`、
`ladder:recent_n` 这一批——**恰好就是 S3.5 要建的升降级设置页需要的文案**。
现在删、S3 再补回来是纯粹的来回折腾。等 S3.5 做完再按那时的真实引用清一次。

---

## S6 · 品牌清理（需要产品决策，不是设计能定的）

`弈航 / BoardNavi` 出现在：`Dashboard.tsx:89`、`LoginModal.tsx:75`、`GalaxySidebar.tsx:75,78`，
以及整份 `src/legal/terms.ts`（用户服务协议正文，反复出现「弈航团队」「弈航账号」）。

**只换左上角会让同一屏出现两个品牌名。** 但协议正文改名涉及法律主体，
需要产品与法务确认「智星盒」与「弈航」的关系（是替换、还是公司名 vs 产品名并存）。
**在拿到答复前不动 `terms.ts`。**

---

## 不在本计划内

- `theme.ts:56` 的 `padding:'8px 16px'` 是否让 `size` 失效 —— **推论未实测**，先量再说
- `theme.ts:58-60` 全局 hover `scale(1.02)` 是否保留 —— 产品判断
- kiosk 是否跟随换字体 —— 见 S0 风险条
- **kiosk 侧 315 个缺键 + shared/components 38 个**（S5 审计出来的，见
  `audit_i18n_keys.py`）。不在本 track 范围，但这是笔真账：kiosk 的兜底基本都写死中文，
  意味着 kiosk 换到任何非中文语种都会大面积漏中文。要单开一轮，别混进 galaxy 改版。
  复现：`uv run python superpowers/tracks/galaxy-ui-redesign/audit_i18n_keys.py --area kiosk`

---

## 依赖顺序

```
S0 ──┬── S1 ── S2
     ├── S3
     └── S4        (S4 依赖 S1/S2/S3 的结构已定)
S5、S6 与上面并行，互不阻塞
```
