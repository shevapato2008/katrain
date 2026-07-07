# 智星盒 StellaBox Kiosk UI 重设计 — 前端设计文档

> Track 状态：**方向已选（③ 棋盘台 Board Console）**，主界面/对弈模块视觉稿已定；逐模块细化中。
> 目标设备：**7 英寸触摸屏**（设计基准 1024×600 横屏），触控优先，主屏内容一屏可见、不滚动。
> 语言：中文优先（英文字体采用 Anthropic 主站风格）。
> 品牌：**智星盒 StellaBox**（旧名「弈航 / Yìháng」已废弃 2026-07-06；artifact 与本文档已改，**代码级改名待办**见 §7.6）。

## 1. 背景与问题

当前 kiosk UI 直接沿用网页端外壳（`KioskLayout` → 72px 左侧 `NavigationRail`，图标 22px、标签 11px），在 7″ 小屏上：
- 左栏图标/文字过小，与右侧硕大的操作按钮**比例失衡**；
- 整体观感“太丑”（扁平纯黑 + 无层次）。

用户诉求：先把**主界面**重做好看，再逐模块推进；给多个方案做成 artifact 对比后再定。

## 2. 三个方案（导航立场不同）与决策

用同一套基础（Anthropic 字体 + 围棋/棋盘题材 + 7″ 1024×600 一屏可见 + 大触控靶）做了三版，差异在**导航模型与气质**：

| 方案 | 导航 | 气质 | 定位 |
|---|---|---|---|
| ① 墨枰 Ink Goban | **保留**左栏，加宽到 132px（图标+中文+英文小注，选中态如“点亮的棋子”） | 暖色深调·漆盘夜色 | 想保留熟悉左栏、只修比例 |
| ② 素纸 Paper Launcher | 主屏**取消**左栏，改启动台；对弈为主砖；进模块内才出返回/子导航 | 浅暖纸质·通透 | 想与旧版最大反差、最静 |
| ③ 棋盘台 Board Console | 导航移到**底部 Dock**（拇指可达）；左侧常驻“智能棋盘实时台” | 冷调石板·仪表台 | 突出智能棋盘硬件形态、触控最顺手 |

**决策（2026-07-04，用户拍板）：采用 ③ 棋盘台 Board Console。**
理由：底部 Dock 在 7″ 横屏上拇指最好点；左侧常驻“智能棋盘台”把摄像头/标定/LED 这套硬件形态摆到第一位，正是这台设备与纯软件 App 的区别。

## 3. 关键修正（本轮）：Dock 选中态必须驱动内容

初版 ③ 有个语义错误：Dock 选中「对弈」，右侧却展示“主页式仪表盘”（开始对弈大按钮 + 继续上一局 + 死活/研究 小卡）。
**修正：选中「对弈」→ 右侧展示「对弈 hub」本身** = 人机对弈（自由对弈 / 升降级对弈）+ 人人对弈（本地对局 / 在线大厅 / 跨平台对弈），即 PlayPage 的内容。左侧“智能棋盘台”作为**常驻面板**保留（对弈前看棋盘是否已连接/标定，天然相关）。“继续上一局”作为对弈相关的轻量条保留在 hub 顶部。

> 通则：**Dock 的当前项决定右侧内容**；左侧智能棋盘台在对弈相关场景常驻，切到其它模块时右侧整体更换（其它模块内容后续逐个设计）。

## 4. 设计系统

### 4.1 屏幕
- 基准 **1024×600 横屏**（7″ 常见面板）。主屏一屏可见、无滚动。
- 触控靶：Dock 项整格可点（≈120×70）；主操作卡 ≥ 56px 高。
- **仅横屏**：kiosk 只做 1024×600 横屏，**竖屏（600×1024）不做**（2026-07-06 定）。既有的 hub 竖屏规范（play-hub-states §4）保留为历史参考，不再新增。

### 4.2 字体（Anthropic 主站风格）
- 英文/拉丁：**Newsreader**（编辑气质衬线，用于品牌字/问候语）+ **Hanken Grotesk**（Styrene 风格的无衬线，用于 UI/标签/正文）。
- 中文：暂用系统 CJK（PingFang SC / Noto Sans SC）回退，未指定。
- ⚠️ Anthropic 真身字体（Styrene / 其衬线）为商用授权，未内嵌；此处用开源近似替身，已以 base64 内嵌进 artifact（见 `artifacts/fonts.css`）。**若拿到真身字体文件，直接替换即可。**
- 🚫 **kiosk 全局禁用 emoji**：SBC 只自托管 Noto Sans SC + JetBrains Mono，**无 emoji 字体 → 彩色 emoji 一律显豆腐块/乱码**（kiosk-physical-tsumego PRD T9 定位的「答对乱码」正是 🎉 缺字形）。所有图标、状态、类别标记**一律用 MUI SVG 图标**（如庆祝用 `EmojiEvents` 奖杯，非 🎉）；galaxy 桌面端可用 emoji（有系统字体），但 kiosk 换皮时必须替换掉。

### 4.3 配色（③ 石板令牌）
```
--slate  #0f1416   底
--raise  #18211f   卡面
--raise2 #1d2725   内嵌/次级卡
--hair   #2b3a35   分隔线
--ice    #eef3f1   主文字
--sub    #93a49d   次文字
--dim    #5f716b   弱文字
--jade   #58b57a   主强调（选中/主操作，沿用现应用绿）
--jade-d #26463a   jade 暗
--amber  #e0a24a   状态/警示（需校准、继续上一局）
--wood   #caa66f   棋盘木色（仅作旧占位/回退；实际盘面用 galaxy `board.png` 木纹，见 §4.6）
```
黑白子令牌 `#111` / `#f2ece0` 仅为回退色；**实际棋子用 galaxy `B_stone.png` / `W_stone.png` 图渲染**（§4.6）。

### 4.4 外壳结构（③）
```
┌ Header  智星盒 StellaBox · logo ··········· fan  22:40 ┐   高 50
├───────────────┬────────────────────────────────────────┤
│  智能棋盘台    │  <当前 Dock 项的内容>                   │
│  (常驻)        │  例：对弈 → 问候 + 继续上一局 +          │
│  · 19×19 实时  │       人机对弈(自由/升降级)              │
│  · 摄像头/标定 │       人人对弈(本地/在线/跨平台)         │   主区
│    /LED 状态   │                                         │
├───────────────┴────────────────────────────────────────┤
│  ▣对弈  ✦死活  ⚗研究  ▤棋谱  ▦摆谱  ▷直播  🎓教程  ⚙设置 │   Dock 高 86
└─────────────────────────────────────────────────────────┘
```
- Header：品牌字（Newsreader）+ 用户 + 时钟。（原 `StatusBar` 的引擎/摄像头/标定指示下沉到左侧棋盘台的状态格。）
- 左侧“智能棋盘台”：19×19 实时盘面 + 三个状态格（摄像头 已连接 / 标定 需校准 / LED 就绪）。
- Dock：8 项等宽大靶，选中项抬升为 jade 实底。
- **Dock 图标 = galaxy 同款**（`@mui/icons-material`，source `GalaxySidebar.tsx`），mockup 内嵌其原始 SVG path，实现期直接用同名组件：

  | Dock 项 | MUI 图标 | 对应 galaxy 项 |
  |---|---|---|
  | 对弈 | `SportsEsports` | Play |
  | 死活 | `Extension` | Tsumego |
  | 研究 | `Science` | Research |
  | 棋谱 | `LibraryBooks` | 棋谱库 |
  | 摆谱 | `GridOn` | *(galaxy 无此项，取棋盘格意象)* |
  | 直播 | `LiveTv` | Live |
  | 教程 | `MenuBook` | Tutorials |
  | 设置 | `Settings` | Settings |

  > ⚠️ 现有 `kiosk/navTabs.tsx` 有两处与 galaxy 不一致（棋谱=MenuBook 应改 LibraryBooks；教程=School 应改 MenuBook），实现期一并对齐。

- **对弈 hub 按钮图标 = galaxy `PlayMenu.tsx` 同款**（有对应就一致，无对应取最近 MUI）：

  | hub 按钮 | MUI 图标 | galaxy 对应 |
  |---|---|---|
  | 自由对弈 | `SmartToy` | Play vs AI (Free) |
  | 升降级 | `SportsEsports` | Rated Game vs AI |
  | 本地对局 | `Groups` | Human vs Human（galaxy 用 `Person`，多人取 Groups）|
  | 在线大厅 | `Public` | *(galaxy 无单列，取在线球体)* |
  | 跨平台 / 跨平台对弈 | `Hub` | *(galaxy 无此模式)* |

- **对弈 hub 六按钮等大**：人机(自由/升降级/跨平台) + 人人(本地/在线/跨平台) 统一为 `3fr` 等宽网格，两行六格同尺寸；自由对弈仅以 **jade 底色**标为主操作，不再靠尺寸/箭头区分（用户 2026-07-06 要求）。
- **品牌 logo = galaxy 既有设计图**（`katrain/img/logo-white.png`，火箭+星球+星辰），kiosk header 复用同一张，不再用 CSS 画的占位标记；artifact 内嵌为 base64。

### 4.5 对弈 hub 交互规范（Phase 1，见 `artifacts/play-hub-states.html`）
- **交互五态**（主卡/次卡/chip/Dock/继续条）：默认 → 悬停（卡上移 `-1px` + border 提亮；chip 换 `--raise2`）→ 按压（`scale .97`，大卡 `.985`，亮度 `.94`）→ 聚焦（`0 0 0 2px 底, 0 0 0 4px rgba(88,181,122,.75)`，`:focus-visible`，供键盘/遥控）→ 禁用（透明度 `.4` + `grayscale(.5)`，`pointer-events:none`）。
- **动效**：`130ms` · `cubic-bezier(.2,.7,.3,1)`；`prefers-reduced-motion` 时去位移只留色变。
- **触控靶**：Dock 格 ≈ `120×70`；主卡 ≥ `64` 高；chip ≥ `48` 高（≥44 基线）。
- **异步/数据态**：等级 加载中（skeleton `1.4s` + spinner `1s`）/ 失败（错误条 + 重试，主卡置禁用）/ 空（提示查引擎）；「继续上一局」无数据时整条隐藏、hub 上移；开始中主卡转 spinner「创建对局中…」。
- **强调色语义**：jade 主/选中 · amber 进行中/待校准 · error(`#e2685c`) 失败。
- ~~**竖屏**：`OrientationContext.isPortrait` 走 600×1024 排布~~ —— **竖屏已放弃（2026-07-06），仅横屏**；此规范作历史参考，不落地。

### 4.6 棋盘与棋子（galaxy 同款渲染，铁律：对齐真实页面）

所有出现盘面的地方（左侧棋盘台预览、设置页预览、对局中大盘）**必须与 galaxy 网页端棋盘视觉一致**。取值全部来自 galaxy 源码 `components/Board.tsx` + `components/board/boardUtils.ts`，非臆造：

| 元素 | galaxy 实现 | mockup 复刻 |
|---|---|---|
| 木纹底 | `katrain/img/board.png` 拉伸铺满 | `<image href="board.png" preserveAspectRatio="none"/>`（base64 内嵌） |
| 网格线 | `strokeStyle rgba(0,0,0,.7)`, `lineWidth 1.2` | `stroke="rgba(0,0,0,.7)" stroke-width="1"` |
| 星位 | `fillStyle rgba(0,0,0,.85)`, `r = gridSize*0.11` | `fill="rgba(0,0,0,.85)" r="2.2"`（格距 20） |
| 棋子 | `B_stone.png`/`W_stone.png`，`stoneSize = gridSize*0.505`，`drawImage(pos.x-stoneSize, pos.y-stoneSize, stoneSize*2, stoneSize*2)` | `<use href="#sb|#sw">` 边长 `20.2`（≈格距*1.01），居中交叉点 |
| 最后一手 | 对比色描边环：`lastPlayer==="B" ? rgba(255,255,255,.95) : rgba(0,0,0,.95)`，`shadowBlur 8`（**非** 填色/贴图；`inner.png` 已加载但未被 `drawImage`，实为遗留） | 黑子→白环、白子→黑环，`r=6 stroke-width=1.6`（旧稿的 jade `#58b57a` 环已弃） |

**mockup 工程细节**：棋子 PNG 较大（B/W 各 ≈200KB base64），若每颗子内联 base64 会把单文件撑到 8MB。改用 SVG `<symbol id="sb|sw">` + `<use>` 精灵表，**base64 每份文档只存一次**，全盘 `<use>` 引用；隐藏 `<svg width=0 height=0>` 承载 `<defs>`，跨 `<svg>` 按 id 全局解析（浏览器标准精灵技法，已 Playwright 本地渲染验证黑/白两色 + 两种描边环均正确）。构建脚本：`scratchpad/build_{d3,playflow,gamestates}.py`（`stone_defs()` 注入 + `board_svg()` 生成）。

## 5. 各模块内容映射（设计意图，逐个细化）

| Dock 项 | 右侧内容（意图） | 状态 |
|---|---|---|
| 对弈 | 人机(自由/升降级/**跨平台**) + 人人(本地/在线/**跨平台**) hub + 继续上一局 | ✅ hub 视觉稿已定；**页面流已切透**（hub→设置→对局中+4 态，见 §5.1） |
| 死活 | 难度 hub（levels grid）→ 题型/单元/题目列表 drilldown → 沉浸解题页 | ✅ 视觉稿（难度 hub + 解题页 + 物理 5 态，见 §5.2） |
| 研究 | 编辑摆棋(快速建议) → 全局 AI 扫描 → 分析报告 | ✅ 视觉稿（三屏 + 5 子态，见 §5.3） |
| 棋谱 | 赛事棋谱库(列表+预览→在研究中打开) | ✅ 视觉稿（列表+预览+空态，见 §5.4） |
| 摆谱 | LED 引导实体摆子 + 拍照采集（kiosk 独有） | ✅ 视觉稿（选谱+引导+拍照+提子 4 屏，见 §5.5） |
| 直播 | 职业赛事观战(列表+KataGo 解说观战) | ✅ 视觉稿（列表+观战，见 §5.6） |
| 教程 | 只读 4 级目录 → 图解+视频学习页 | ✅ 视觉稿（目录+章节树+学习页，见 §5.7） |
| 设置 | 单页设置 + 棋盘几何标定 | ✅ 视觉稿（含语言/账户修正，见 §5.8） |

（“智能棋盘台”是否在**所有**模块常驻，还是仅对弈/对局相关模块常驻，见 §7。）

### 5.1 对弈模块 · 页面流（纵向先切透一条链路）

对弈不是单页，是多页链路。用户 2026-07-06 定：**纵向先切透一条链路**（自由对弈 hub→设置→对局中），建立设置页/对局页的骨架与模式，其余模式（升降级/本地/在线/跨平台）复用同骨架、仅换字段。路由据现有 `kiosk/KioskApp.tsx`：

| 页面 | 现有路由 | 现有组件 | 设计状态 |
|---|---|---|---|
| 对弈 hub | `/play` | `PlayPage` | ✅ 视觉稿（§4.4/§4.5，`d3` + `play-hub-states`） |
| 自由对弈设置 | `/play/ai/setup/:mode` | `AiSetupPage` | ✅ 稿（`play-flow` 左屏） |
| 对局中（人机） | `/play/ai/game/:sessionId` | `GamePage` | ✅ 稿（`play-flow` 右屏 + `game-states` 4 态） |
| 本地对局设置 | `/play/pvp/setup` | *(现为 Placeholder)* | 复用设置页骨架，待细化 |
| 在线大厅 | `/play/pvp/lobby` | `LobbyPage` | 待设计 |
| 跨平台连接/大厅/引擎设置 | `/play/cross-platform*` | `PlatformConnect/Lobby/EngineSetupPage` | 复用设置页骨架，待细化 |

**① 自由对弈设置页**（`play-flow` 左屏）：左「棋盘台预览」console（示意让 2 子）+ 右表单 —— 棋盘(9/13/19) · 规则(中/日/韩/AGA) · 我执(黑/白) · AI 策略(拟人/KataGo/领地/影响/策略) · 棋力 slider · 让子 slider · 贴目 slider · 用时开关 → **开始对弈** jade CTA。字段取自 `AiSetupPage.tsx` 现有控件，与 galaxy `PlayMenu` 模式对齐。

> ⚠️ 与「补全自由对弈设置面板」计划（`tracks/kiosk-play-golaxy/`）交界：那条计划开放**贴目/规则/让子**后端透传（隧道本已支持，前后端 `extra="forbid"` 收窄）。本设置页 UI 是其前端落点；实现期两者对齐。

**② 对局中 GamePage**（`play-flow` 右屏，沉浸式）：顶栏 退出+对局元信息+可视开关；中间大盘；右栏 玩家卡(pcard：AI·拟人 白 / fan 黑，含时钟/读秒/提子)+可视 toggle(手数/坐标/领地/建议)+**胜率走势图**(galaxy `ScoreGraph`/`TrendChart` 同款：胜率折线 + 目差 + 当前手标记；kiosk `GameControlPanel` 本就 import `ScoreGraph`——2026-07-07 补，此前遗漏)+操作(悔棋/停一手/数子/认输)；底部 amber 提示条「AI 已落子 **R16** · 请在实体棋盘对应交叉点摆放白子」——**这是 kiosk 物理对弈的核心**：AI 落子后引导用户在实体棋盘摆子（对齐 [[project_kiosk_physical_play]]）。

**③ 对局中 · 4 状态**（`game-states`，同骨架仅右栏/提示/遮罩变）：
- **A 轮到 AI 思考中** — AI 卡「思考中…」点动画，操作禁用，jade spinner 提示条。
- **B 需校准挡屏** — amber 模态「重新标定 / 仍要继续」，文案「无需 LED,对齐外框即可」（对齐 [[feedback_no_auto_led_geometry]]：几何标定绝不自动亮灯）。
- **C 终局数子** — 地盘着色 + 死子淡化(opacity .4)红叉；结果卡「黑胜 4.5 子」+ 目数拆解 + 继续对弈/确认终局。
- **D 认输确认** — error 红模态 取消/确认认输。

> 竖屏变体不做 —— kiosk 仅横屏（2026-07-06 定）。

### 5.2 死活模块 · 页面流（Phase 2，见 `artifacts/tsumego-flow.html`）

**关键事实**：kiosk 死活**已全量建成**（非占位），6 条路由 + 与 galaxy 共用同一套解题引擎（`hooks/useTsumegoProblem.ts` · `context/TsumegoProgressContext.tsx` · `components/tsumego/TsumegoBoard.tsx`）。故本模块是**视觉换皮**，不是新功能。IA 是 5 级线性下钻 + 解题页：

| 页面 | 现有 kiosk 路由 | 现有组件 | 设计状态 |
|---|---|---|---|
| 难度 hub | `/tsumego` | `TsumegoPage` | ✅ 稿（`tsumego-flow` ①） |
| 题型 | `/tsumego/:level` | `TsumegoCategoriesPage`（+「全部题目」快捷卡） | 复用浏览骨架，待细化 |
| 单元（20 题/单元） | `/tsumego/:level/:category` | `TsumegoUnitsPage` | 复用浏览骨架，待细化 |
| 题目列表 | `.../:unit`、`/all` | `TsumegoUnitListPage`/`TsumegoLevelPage`（`ProblemCard`+`MiniBoard` 缩略） | 复用浏览骨架，待细化 |
| 解题页 | `/tsumego/problem/:id` | `TsumegoProblemPage`（`<PhysicalBoardGuard requireRecognition>`） | ✅ 稿（`tsumego-flow` ②） |

**① 难度 hub**（Dock「死活」选中）：**全宽浏览、无左侧棋盘台**（浏览页无实时盘面，让位给卡片网格）。标题「死活题 · 选择难度级别」+「继续练习」卡（承接 [[对弈]] 的继续上一局模式）+ 难度卡网格（15K…7D，级 kyu 白 / 段 dan jade，进度 5 点 `ProgressDots`，「上次」练到的档位 jade 高亮）。级差弱→强排序。kiosk 刻意**不做**每档完成度大统计（SBC 太贵，源码注释所述），只显示总题数 + 进度点。

**② 沉浸解题页**：顶栏 返回 + 面包屑（死活 › 3 段 › 死活题 › 第 N 题）+「实体棋盘 已连接·可摆子作答」标；左大盘（galaxy `TsumegoBoard` 同款：`board.png` + `B/W_stone` + 最后一手对比环 + 提示态绿点）；右栏 = 级/题型 chip · 黑先/白先 + `hint` 文案（如「黑先杀白」）· 状态条 · 用时/尝试/上次 · 悔棋/重置/提示/试下 · 上一题/下一题（末题→返回单元）。

**关键设计决定**：
- **智能棋盘台作用域（部分回答 §7「棋盘台作用域」开放问题）**：console 只在**有实时盘面**的场景出现 —— 对弈 hub/对局、死活解题页（此处即题目盘本身，沉浸呈现）。**浏览类页面（死活难度/题型/单元/列表）一律全宽无 console**。
- **实体棋盘维度（双输入并存，用户强调「实体非常重要」）**：解题页有「使用物理棋盘」**开关**（opt-in，记忆上次，默认关；T1）。**屏点选 + 实体摆子两种输入始终并存**（TR1）。物理模式走一套相位机（源 `kiosk-physical-tsumego` track 的 `physicalTsumegoMachine`）：`off → clearing(清盘) → setup(黑阶段红灯→白阶段绿灯,摆一颗灭一颗) → ready(做题,move arm) → replying(应手点棋色灯,替对方摆子) / removing(答错蓝灯闪+界面列待拿除子+语音) → solved(奖杯庆祝+空点白灯双闪) → clearing_next(换题清盘)`。**三通道反馈**（T5）：界面 + 语音（edge-tts 预生成）+ LED。**LED 色语义固定**：黑→红 / 白→绿 / 拿除→蓝 / 提示·庆祝→白。对齐 [[project_kiosk_physical_play]]、`kiosk-physical-tsumego` track（PRD/plan 在另一 worktree `/Users/fan/Repositories/katrain-kiosk-physical-tsumego`，**尚未开发完**）。已出 5 状态稿（`tsumego-states.html`）。
- **盘面坐标**：真实 `TsumegoBoard` 显示 A–T/1–19 坐标；mockup 暂省（复用 §4.6 对弈盘 SVG，保视觉一致）。实现期坐标由 `TsumegoBoard` 自带。
- **图标（galaxy/kiosk 同款 MUI）**：nav=`Extension`；解题=`Undo`(悔棋)·`Replay`(重置)·`Lightbulb`(提示)·`Explore`/`ExploreOff`(试下/退出)·`NavigateBefore`/`NavigateNext`(上/下一题)·`FormatListBulleted`(返回单元)；题型「全部题目」=`GridView`；题型 emoji：死活 ⚔️ / 手筋 ✨ / 官子 🎯。

**§5.2 已出稿**：③ 解题**物理各状态**（`tsumego-states.html`）：A 摆放黑棋(红灯)/B 做题中(双输入)/C 应手(绿灯)/D 答错拿除(蓝灯)/E 答对(奖杯图标+空点白灯双闪)——全程 MUI 图标无 emoji（§4.2）。

**§5.2 待补**：纯屏幕态（提示绿点 / 不正确抖动+红 / 试下模式，物理模式关时）；浏览下钻 3 屏（题型/单元/列表 + `MiniBoard` 缩略卡 + 完成度边框态）；清盘/换题过渡态细化。

### 5.3 研究模块 · 页面流（Phase 2，见 `artifacts/research-flow.html`）

**关键事实**：kiosk 研究**当前只有一个 setup 占位页**（`ResearchPage.tsx`：玩家/规则/编辑工具网格/开始 表单，盘面是空占位、手数导航是死的），点「开始研究」直接跳到通用对局盘 `GamePage`——**没有真正的分析视图**。真正的复盘体验在 **galaxy `ResearchPage`**（693 行，两级状态机）。故本模块**不是换皮，是把 galaxy 研究功能下沉到 kiosk**。IA：

| 页面 | 现有 kiosk 路由 | 现有组件 | 设计状态 |
|---|---|---|---|
| 编辑摆棋（L1） | `/kiosk/research` | `ResearchPage`（占位表单） | ✅ 稿（`research-flow` ①）— **需补齐为可编辑盘** |
| AI 分析中（L2a） | *(galaxy 内联态，无独立路由)* | galaxy `handleStartAnalysis`+`analysisProgress` 轮询 | ✅ 稿（`research-flow` ②） |
| 分析报告（L2b） | *(现跳 `GamePage`)* | galaxy `ResearchAnalysisPanel`/`Board.tsx` | ✅ 稿（`research-flow` ③）— **需新建，不再跳通用对局盘** |

**① 编辑摆棋**（Dock「研究」选中 → 直接进，无 hub）：**盘面居中 + 右栏**。右栏 = 研究模式 chip · 规则 chips(棋盘/规则/贴目) · **编辑工具 12 格**（交替/摆黑/摆白/清空 · 手数/移动/删除/坐标 · 建议/领地/打开/保存，取自 galaxy `ResearchToolbar`）· 建议开时盘上标 **AI 候选点**（快速分析 200 visits，galaxy `quickAnalyze`）· **开始研究** jade CTA（全局扫描 500 visits/手）。**智能棋盘台作用域**：研究全程有实时盘面，L1 保留 Dock（模块入口，便于切走）；L2 分析/报告转沉浸 `.stop` 顶栏、无 Dock（同解题页）。

**② AI 分析中**：沉浸居中——烧瓶图标 + 旋转环 + 进度条 + 已分析手数 / 进度% / 预计剩余(ETA) + **取消分析回到编辑**。对齐 galaxy L2a（`ScienceIcon` + `LinearProgress` + `analysisProgress` 每秒轮询 + ETA 计算）。

**③ 分析报告**：沉浸——顶栏「返回编辑」+ 面包屑；左复盘盘（galaxy `Board.tsx` 同款：最后一手对比环 + **eval 色点**候选手 blunder红→excellent绿 + 领地）；右栏 = **胜率条**(黑/白 % + 目差) · **AI 推荐表**(着手/推荐度/目差/胜率，top-3 + 实战手 amber 高亮，对齐 `ResearchAnalysisPanel` 与 `AiAnalysis` 同构) · **走势图**(胜率 SVG 折线 + 当前手标记，可点跳转) + **妙手/问题手** tab(按 score delta 分类) · 底部 **手数导航**(首/上/滑块/自动播放/下/末，`Slider`+autoplay)。

**关键设计决定**：
- **不做 9/13 路选择**：kiosk 物理盘固定 19 路（同对弈决定，[[project_kiosk_physical_play]]）；小盘仅屏上有意义，本期只做 19 路。
- **eval 色点语义**：沿用 galaxy `Board.tsx` `EVAL_COLORS`（blunder→excellent 红→绿），非 kiosk 自定义。
- **图标（MUI，无 emoji · §4.2）**：nav=`Science`；工具=`SwapHoriz`(交替)/石子圆点(摆黑白)/`ClearAll`(清空)/`Tag`(手数)/`OpenWith`(移动)/`Backspace`(删除)/坐标/`Lightbulb`(建议)/`Terrain`(领地)/`FolderOpen`(打开)/`Save`(保存)；分析中=`Science`+`Close`；报告=`Edit`(返回编辑)/`SkipPrevious`·`NavigateBefore`·`PlayArrow`·`NavigateNext`·`SkipNext`(导航)。

**§5.3 已补子态**（`research-states.html`，在线 `91ab54b8`）：摆子模式(摆黑 ghost 落子预览)/删除模式(红叉待删标记)/领地叠加(ownership 暗亮格 + 黑白目数)/分析失败(引擎无响应+重试)/从棋谱库打开(modal 列赛事 kifu→在研究中打开)。**§5.3 待补**：摆白/移动 place-mode（与摆黑/删除同构，未单独出）；分析空态（空盘直接开始）。**落地注意**：③ 需**新建** kiosk 分析报告页（现直接跳通用 `GamePage`），复用 galaxy `ResearchAnalysisPanel`；`Board.tsx` 属**共享地带**（改动双构建）。

### 5.4 棋谱模块 · 页面流（Phase 2，见 `artifacts/kifu-flow.html`）

**关键事实**：棋谱**不是**个人云存档，是**只读赛事棋谱库**（`kifu_albums` DB 表）。**无本地/云端 tab、无上传/删除、无登录专属态、卡片无缩略图**。kiosk `KifuPage` 与 galaxy `KifuLibraryPage` 近乎同构：左列表 + 右预览两栏。IA：

| 页面 | 现有 kiosk 路由 | 现有组件 | 设计状态 |
|---|---|---|---|
| 棋谱库（列表+预览） | `/kiosk/kifu` | `KifuPage` | ✅ 稿（`kifu-flow` ①②） |
| 详情/查看器 | `/kiosk/kifu/:id` | *(现为 `PlaceholderPage`)* | 不单独做——打开走研究 |
| 打开一局 | → `/kiosk/research/session/:id` | `GamePage`(共享面) | 复用研究面，无专属查看器 |

**① 棋谱库主屏**（Dock「棋谱」选中）：**左列表**（标题「棋谱库」+ 总数 + **单搜索框**（棋手/赛事/年份，kiosk 350ms 防抖）+ 卡片列表 + 分页 20/页）+ **右预览**（选中一局→`LiveBoard` 盘面 + 手数滑块[首/上/下/末] + **在研究中打开** jade CTA）。**卡片**：赛事/轮次/日期/手数 + 黑子·棋手·段位 · `ResultBadge`(黑中盘胜等) · 段位·棋手·白子；胜方加粗（对齐 `KifuPage` 卡片，**无缩略图**）。
**② 空态 / 未选中**：搜索无结果→左「未找到棋谱」+ 关键词提示（galaxy 有此态，kiosk 缺，本稿补）；未选中→右「选择一局棋谱预览」占位。

**关键设计决定**：
- **console 作用域**：棋谱是浏览页，但右预览本身即盘面——**两栏浏览+预览**，非左侧常驻 console（预览盘随选中即时出）。Dock 保留（模块入口）。
- **图标对齐**：Dock「棋谱」现 kiosk 用 `MenuBook`，应改 galaxy 同款 `LibraryBooks`（实现期一并，同 §4.4 注）。
- **打开=研究**：无独立 kifu 查看器；「在研究中打开」建 research 会话跳 `GamePage`（`kifu/:id` 占位路由不启用）。

**§5.4 待补**：预览加载 skeleton（galaxy `SkeletonCards`）；分页跳转态。现仅单搜索框（源码无筛选/排序，保持一致）。**摆谱（Baipu）是独立模块**，不并入棋谱（源 `navTabs.tsx:25` / `BaipuListPage`）。

### 5.5 摆谱模块 · 页面流（Phase 2，见 `artifacts/baipu-flow.html`）

**关键事实**：摆谱（Baipu）**不是**存局/打谱库，是 **kiosk 独有的 LED 引导实体摆子 + 摄像头采集工具**（无 galaxy 版）。选一局 19 路 SGF（棋谱库或导入）→ 后端展开 `steps[]` → 前端逐手：LED 点亮下一手交叉点、操作者摆真子、点「确认落子」→ 快门拍照写帧。目的 = **operator-trusted 训练数据采集**（对齐 [[project_baipu_led_track]]）。相位机 `guiding→确认→await_removal→advance→done`（`BaipuSessionPage`）。IA：

| 页面 | 现有 kiosk 路由 | 现有组件 | 设计状态 |
|---|---|---|---|
| 选谱 picker | `/kiosk/baipu` | `BaipuListPage` | ✅ 稿（`baipu-flow` ①） |
| 引导会话 | `/kiosk/baipu/session/:source` | `BaipuSessionPage`（`PhysicalBoardGuard`，**无** requireRecognition） | ✅ 稿（②③④） |

**① 选谱**（Dock「摆谱」选中）：左（标题「摆谱」+「仅 19 路」+ 导入本地 SGF + 搜索 + **最近 resume chips** + kifu 卡片 + 分页）+ 右（`LiveBoard` 终局预览 + 开始摆谱）。数据源复用 `KifuAPI`。
**② 引导摆子**：顶栏「落子·<色>」+ k/N 手 + 已采集 N 帧 + LED/相机 health dots；中盘 **下一手 LED 引导环**（红=黑 / 绿=白）；右栏 双 PlayerPanel(当前手高亮) + **下一手大色块 chip**(含 LED 色) + 最近保存文件名 + **确认落子·拍照**(88px 大靶) + 重新点灯/撤回/退出。
**③ 拍照中挡屏**：安全全屏遮罩「正在拍照 · 请勿伸手进入棋盘上方」（`capturePending` barrier，防手入镜）。
**④ 提子移除**：被提子 **蓝灯**标记 + 底部蓝条「这一手提掉 N 子 · 请从实体棋盘拿走」+「已移除 N 子·继续」蓝按钮（`await_removal` 态）。

**关键设计决定**：
- **LED 色语义固定**（同死活/物理对弈）：黑→红 / 白→绿 / 提子→蓝（源 `BaipuSessionPage` LedAPI；对齐 [[project_kiosk_physical_play]]）。
- **operator-trusted**：确认即真值，识别不在采集决策路径（仅需几何锁定，不要求 recognition）。
- **无 galaxy 版**：纯 kiosk 硬件功能。**无 emoji**：相机/快门/health 全 MUI 图标。

**§5.5 待补**：DriftBanner 几何漂移态；采集失败条；resume/undo/exit 三确认弹窗；capture 服务 disabled（dev/纯屏）态。

### 5.6 直播模块 · 页面流（Phase 2，见 `artifacts/live-flow.html`）

**关键事实**：直播 = **只读职业赛事观战**（星阵/弈客/IGS 抓取的职业对局，**非视频流、非用户观战、无弹幕/观众数**），叠 KataGo 实时解说。轮询更新（列表 30s · 对局 5s，非 websocket）。kiosk 与 galaxy 共用 `components/live/*`；kiosk board 模式走只读代理 `/api/v1/board/live`。IA：

| 页面 | 现有 kiosk 路由 | 现有组件 | 设计状态 |
|---|---|---|---|
| 直播列表 | `/kiosk/live` | `LivePage` | ✅ 稿（`live-flow` ①） |
| 观战 | `/kiosk/live/:matchId` | `LiveMatchPage` | ✅ 稿（②） |

**① 列表**（Dock「直播」选中）：左 `LiveBoard` 预览(不轮询分析) + PlaybackBar(含**跟播最新** sync) + 进入直播；右 标题 + **热门对局/即将开始** tabs + 「直播中(N)」+「历史」分区 + `MatchCard`（红脉冲 live dot + 赛事 + **来源徽章**星阵/弈客/IGS + 手数 + 双方棋手/段位 + 黑白胜率条）。
**② 观战**：顶栏 返回 + 黑vs白 + live chip + 来源；左盘(AI 推荐点标记 + 最后一手环)；右栏 `MatchInfo` + **试下/形势/手数/AI** 4 toggle + `AiAnalysis` 表(着手/推荐度/目差/胜率，实战手高亮) + `TrendChart` 胜率走势 + PlaybackBar(跟播最新)。

**关键设计决定**：kiosk 触屏**点选**看 PV（galaxy 是 hover）；board 模式**只读**（写操作抛错，评论已 defer）；列表预览**不轮询**分析（省算力）。**§5.6 待补**：即将开始 tab 列表态；对局结束态；无直播空态；PV 预览浮层。

### 5.7 教程模块 · 页面流（Phase 2，见 `artifacts/tutorial-flow.html`）

**关键事实**：教程 = **只读 4 级目录浏览器**（分类→书目→章节/小节树→图解学习页），镜像 galaxy（kiosk 走只读 `TutorialReadAPI`，剥离 galaxy 编辑/标注列）。学习页**视频优先**（"Option B" 已实现，[[project_sbc_tutorial_parity]]）：棋盘图解 + 该图教学视频 / 讲解+音频。数字化教科书，**非交互做题**（做题在死活）。**无进度追踪**（源码本就无）。IA：

| 页面 | 现有 kiosk 路由 | 现有组件 | 设计状态 |
|---|---|---|---|
| 分类目录 | `/kiosk/tutorial` | `TutorialCategoriesPage` | ✅ 稿（`tutorial-flow` ①） |
| 书目 | `/kiosk/tutorial/:category` | `TutorialBooksPage` | ✅ 稿（② 左栏） |
| 章节树 | `/kiosk/tutorial/book/:bookId` | `TutorialBookDetailPage` | ✅ 稿（② 右栏） |
| 学习页 | `/kiosk/tutorial/section/:sectionId` | `TutorialSectionPage` | ✅ 稿（③） |

**① 分类目录**（Dock「教程」选中）：分类卡网格（入门/死活基础/布局/中盘/官子/定式，jade 图标 + 简介 + N 本·N 节）。
**② 书目 + 章节树**：左 书目列表(分类内，选中高亮) + 右 章节 accordion + 小节行(编号·标题·N 图·▶有视频)。
**③ 学习页**（沉浸）：顶栏 面包屑 + **图 X (i/N) 图序导航**；左 `SGFBoard` 图解(手数滑块 + 全盘/局部 toggle)；右 **视频播放器**(poster+播放+进度) + 图解说明 vcard + 讲解语音(视频缺则 narration+audio 兜底)。

**关键设计决定**：Dock「教程」= `MenuBook`（§5.4 把 棋谱 改 `LibraryBooks` 后 MenuBook 空出，对齐 galaxy）。只读——无编辑/标注/审核列。**§5.7 待补**：无视频 fallback 态；加载/错误态。

### 5.8 设置模块 · 页面流（Phase 2，见 `artifacts/settings-flow.html`）

**关键事实**：设置 = **单页**（`SettingsPage`，非 tab/drilldown）+ 几何标定子页（`VisionSetupPage`→`GeometryCalibrationWorkspace`）。据真实控件盘点出稿，并**主动修正两处 + 补一处**：

| 区块 | 真实控件 | 本稿处理 |
|---|---|---|
| 实体棋盘 | 「重新标定棋盘」→ `/kiosk/vision/setup` | 保留 + 加 摄像头/LED/标定 状态格 |
| 屏幕方向 | 4 档 0/90/180/270 | **仅横屏 0°/180°**（去竖屏，竖屏已放弃 §4.1） |
| 死活练习 | switch 做对后自动进入下一题 | 保留 |
| 语言 | chips 中/英/**日/韩**（且 cosmetic 无效、违规） | **仅 中/英**（去日韩，符 [[feedback_language_zh_en]]；实现期须真正接 i18n） |
| 外部平台 | 4 卡 99/野狐/腾讯/新浪（装饰） | 保留 + 标「敬请期待」 |
| 账户/退出 | **kiosk 现无任何登出控件** | **补 账户 + 退出登录**（标「建议补充」） |

**② 棋盘几何标定**：双路实时画面（原始摄像头透视盘 + 俯视校正方盘，四角绿点 anchor）+ 状态(摄像头/LED) + 上次标定 metrics(内点 13/13 · RMS · 最大残差) + **使用上次标定** / **重新标定** + amber 提示「先清空棋盘 · 手动触发 · 不会自动点亮 LED」。

**关键设计决定**：几何标定**用户手动触发、绝不自动亮灯**（铁律 [[feedback_no_auto_led_geometry]]）。**§5.8 待补**：标定进行中相位(清空/暗参考/角点/校验/建基线 进度)；失败诊断卡(anchor 未找到/棋盘移动/非空基线)；语言·账户接真实逻辑。**架构注**：[[project_geometry_recalib_arch]] 定 no-LED 外框重标为 PRIMARY、LED demote 为手动 fallback——现 `GeometryCalibrationWorkspace` 仍走 LED 角点，实现期与该方向对齐。

## 6. 落地映射（现有代码，供实现期参考）

- `katrain/web/ui/src/kiosk/components/layout/KioskLayout.tsx` — 横屏走 `NavigationRail`、竖屏走 `TopTabBar`；新设计横屏改为 **Header + 左棋盘台 + 内容 + 底 Dock**。
- `.../layout/NavigationRail.tsx`（72px 左栏，图标 22/标签 11）→ 替换为**底部 Dock 组件**（大靶、选中抬升）。
- `.../layout/StatusBar.tsx`（40px，引擎/摄像头/标定指示 + 用户 + 时钟）→ 拆分为 Header（品牌+用户+时钟）+ 左侧棋盘台状态格。
- `.../layout/navTabs.tsx` — 8 个 tab（对弈/死活/研究/棋谱/摆谱/直播/教程/设置）不变，仅呈现形态变。
- `.../pages/PlayPage.tsx` — 对弈 hub 内容（人机/人人 ModeCard）即右侧内容来源；视觉换皮。
- `.../pages/AiSetupPage.tsx` — 自由对弈设置页（§5.1①）；控件已存在，换皮为左预览+右表单布局。
- `.../pages/GamePage.tsx` + `components/game/GameControlPanel.tsx` — 对局中（§5.1②③）；沉浸式换皮 + 4 态。
- 盘面渲染共用 `components/Board.tsx` + `components/board/boardUtils.ts`（§4.6 取值来源，**共享地带**，改动波及 galaxy + kiosk 两构建）。
- 死活（§5.2）换皮：`kiosk/pages/Tsumego*.tsx`（6 页已建）+ `kiosk/components/tsumego/*`；解题盘为 `components/tsumego/TsumegoBoard.tsx`（**独立** canvas 盘，非 `Board.tsx`），缩略图 `components/MiniBoard.tsx`（自动裁到题目区域）。共用引擎 `hooks/useTsumegoProblem.ts`、进度 `context/TsumegoProgressContext.tsx`、`api/tsumegoApi.ts`——**只换皮不动逻辑**。
- 研究（§5.3）**下沉 galaxy 功能**（非纯换皮）：现 `kiosk/pages/ResearchPage.tsx` 仅占位表单，`GamePage` 是「开始研究」的落地页。目标态要把 galaxy 的 `galaxy/pages/ResearchPage.tsx`(693 行两级机) + `galaxy/components/research/{ResearchAnalysisPanel,ResearchToolbar,ResearchSetupPanel}.tsx` 的功能移到 kiosk：L1 编辑用 `galaxy/hooks/useResearchBoard.ts` + `components/live/LiveBoard.tsx`（`aiMarkers`/`ownership` 叠加）；L2 报告用 `components/Board.tsx`（**共享地带**）+ 复刻 `ResearchAnalysisPanel`（胜率条/AI 推荐表/走势图/妙手·问题手/滑块导航）。API：`quickAnalyze`(200 visits) · `analysisScan`+`analysisProgress`(500 visits) · 会话 `hooks/useResearchSession.ts`。**③ 分析报告页 kiosk 尚不存在，需新建**（现跳 `GamePage`）。
- 遵守 SBC 双构建契约（根 `CLAUDE.md`）：共享地带改动需 `npm run build` 与 `build:kiosk-2d` 双绿。

## 7. 待定 / 下一步

1. ~~**竖屏变体**~~：**已放弃（2026-07-06）** —— kiosk 仅横屏 1024×600，竖屏一律不出稿、不落地。既有 hub 竖屏规范（play-hub-states §4）留作历史参考。
2. **左侧棋盘台的作用域**：全局常驻，还是仅对弈/对局相关模块显示。
3. **真身字体**：拿到 Anthropic Styrene/衬线文件后替换 `fonts.css`。
4. **逐模块设计**：死活 → 研究 → … 按 §5 依次出稿。
5. **实现**：视觉锁定后另开实现分支，按 §6 映射改造外壳组件（保持双构建绿）。
6. **品牌代码级改名（弈航→智星盒 / StellaBox）**：仅 artifact + 本文档已改；**代码未动**。涉及面（2026-07-06 清点）：
   - galaxy：`GalaxySidebar.tsx`(名+副标"棋道导航者"+logo alt)、`LoginModal.tsx`、`Dashboard.tsx`(欢迎语)、`GalaxySidebar.test.tsx`
   - 共享组件：`TopBar.tsx`、`Sidebar.tsx`、`LoginDialog.tsx`、`RegisterDialog.tsx`
   - kiosk：`StatusBar.tsx`、`LoginPage.tsx` + `__tests__/{KioskApp,StatusBar,KioskLayout}.test.tsx`
   - **法律 ToS**：`legal/terms.ts`（"弈航 BoardNavi" 主体名，法律文本，需人工/法务确认，勿盲改）
   - **logo 图片资源**：`/assets/img/logo{,-white}.png`（图内即"弈航"字样，需重做图，非文本替换）
   - 英文名：代码里旧英文名是 **BoardNavi**（非 Yìháng），统一改 **StellaBox** 时一并替换
   > 属跨构建改动（galaxy+kiosk+共享+i18n+测试），单独立项执行、双构建绿；法务/图片资源单独处理。

## 8. Artifacts 索引

本地文件（`artifacts/`，用 `@import ./fonts.css`、`./board.png`、`./B_stone.png`、`./W_stone.png` 相对引用；构建脚本在 `scratchpad/build_*.py` 内联为 base64）：
- `d3-board-console.html` — **选中方案（对弈 hub）** — 主控台 + 智能棋盘台 + Dock
- `play-hub-states.html` — **对弈 hub 完整规范**（交互五态 + 异步/数据态 + 竖屏 + 动效数值，Phase 1）— 已全面同步 d3 组件体系（logo / 等大 `.opt` 网格 / galaxy MUI 图标 / 木纹棋盘棋子）
- `play-flow-setup-game.html` — **对弈流程**：自由对弈设置页（左预览+右表单）+ 对局中 GamePage（§5.1①②）
- `game-states.html` — **对局中 4 态**：AI思考中 / 需校准挡屏 / 终局数子 / 认输确认（§5.1③）
- `tsumego-flow.html` — **死活模块锚点两屏**：难度 hub + 沉浸解题页（§5.2 · Phase 2）
- `tsumego-states.html` — **死活物理解题 5 态**：摆放黑棋/做题中/应手/答错拿除/答对（§5.2 · LED 三通道 · 无 emoji）
- `research-flow.html` — **研究模块三屏**：编辑摆棋(快速建议) → AI 分析中(进度+ETA) → 分析报告(胜率条/AI推荐/走势图)（§5.3 · 对齐 galaxy `ResearchPage`）
- `research-states.html` — **研究子态**：摆子/删除模式 · 领地叠加 · 分析失败 · 从棋谱库打开（§5.3）
- `kifu-flow.html` — **棋谱模块**：赛事棋谱库列表+预览 + 搜索空态（§5.4 · 只读 kifu 库）
- `baipu-flow.html` — **摆谱模块**：选谱 + LED 引导摆子 + 拍照挡屏 + 提子移除（§5.5 · kiosk 独有 LED 采集）
- `live-flow.html` — **直播模块**：职业赛事观战列表 + KataGo 解说观战（§5.6 · 只读观战）
- `tutorial-flow.html` — **教程模块**：分类目录 + 章节树 + 图解视频学习页（§5.7 · 只读 4 级）
- `settings-flow.html` — **设置模块**：单页设置(语言/账户修正) + 棋盘几何标定（§5.8）
- `d1-ink-goban.html` / `d2-paper-launcher.html` — 备选①②
- 盘面资源 `board.png` / `B_stone.png` / `W_stone.png` 从 `katrain/img/` 拷入，供本地预览与构建内联（§4.6）。（galaxy 的 `inner.png` 未使用，未拷入。）

在线（claude.ai artifact，boardstone 对齐 galaxy 版）：
- ③ 棋盘台（选中/对弈 hub）: https://claude.ai/code/artifact/a9ef18ea-6272-48a7-92ef-bafaa8447eea
- 对弈 hub 完整规范（状态+竖屏）: https://claude.ai/code/artifact/5e13c101-0942-46dc-ac65-d184793d08b6
- 对弈流程（设置→对局中）: https://claude.ai/code/artifact/ddd9a8c7-9aeb-426e-9194-191e655fb179
- 对局中 4 态: https://claude.ai/code/artifact/6cb8e990-6900-4c9d-87d5-87e0610dee9c
- 死活 · 难度 hub + 解题页（Phase 2）: https://claude.ai/code/artifact/916fad3d-a5de-4631-a74a-8dcb88910505
- 死活 · 物理解题 5 态: https://claude.ai/code/artifact/fd0be9ae-a149-410e-a5eb-11c599f76dce
- 研究 · 编辑摆棋 + 分析中 + 分析报告（Phase 2）: https://claude.ai/code/artifact/28a2a9e2-b92f-44a0-a1a4-12e82e228826
- 研究子态 · 摆子/删除/领地/失败/打开棋谱: https://claude.ai/code/artifact/91ab54b8-356b-4724-bef0-44b651156335
- 棋谱 · 赛事棋谱库列表+预览+空态: https://claude.ai/code/artifact/b5cf5849-248c-4b71-acb3-ef8ade09ec5e
- 摆谱 · 选谱+LED引导摆子+拍照+提子: https://claude.ai/code/artifact/a2adfad7-6397-4666-b264-fdc2a3546304
- 直播 · 赛事观战列表+KataGo解说观战: https://claude.ai/code/artifact/fe9787a1-5879-4e50-a930-fa2b61ccc3f8
- 教程 · 分类目录+章节树+图解视频学习页: https://claude.ai/code/artifact/02767307-dba5-439d-bf62-8af43f83132f
- 设置 · 设置主页(语言/账户修正)+棋盘几何标定: https://claude.ai/code/artifact/c93e74c2-7754-4f40-b306-bdbe4fd8e44b
- ① 墨枰 Ink Goban: https://claude.ai/code/artifact/9166cdb5-e53c-4775-b58b-5b602b0ffb50
- ② 素纸 Paper Launcher: https://claude.ai/code/artifact/be57a6cd-44e5-4e64-8643-3aa1f99a9530

> 注：artifact 版把字体/图片 base64 内嵌（CSP 需自包含）；`artifacts/` 本地版用相对引用，避免仓库里存多份大字体/图片。
> 全部对弈 artifact（d3 / play-hub-states / play-flow / game-states）现共用同一组件体系（等大 `.opt` 网格 · galaxy MUI 图标 · logo）与 galaxy 盘面/棋子，已 Playwright 本地渲染逐一核对。
