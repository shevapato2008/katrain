# Kiosk UI 重设计 · 开发交接文档（HANDOFF）

> 面向**实现期工程师**。设计定稿见 `design.md`（视觉系统 + 逐模块规范），本文件是**从视觉稿到代码的落地索引 + 工作流**。
> 目标设备：7″ **1024×600 横屏**触摸屏（仅横屏，竖屏已放弃）。品牌：**智星盒 StellaBox**。方向：**③ 棋盘台 Board Console**（Header + 底部 Dock + 有盘场景左侧/沉浸盘）。

---

## 0. 这些 artifact 是什么（先读这段）

`artifacts/*.html` 是**自包含视觉 mockup**（字体/盘面图 base64 内联），**不是生产组件**。它们的作用：
1. **锁定外观**（配色/字体/间距/触控靶/盘面棋子渲染）；
2. **锁定 IA 与交互流**（每屏对应哪个真实路由/组件、各状态长什么样）。

开发 = **把现有 kiosk React 组件"换皮"到这些稿**（个别为"新建/下沉"，见下表 `类型` 列），**不是**把 HTML 拷进 app。

**在线版**（boardstone 对齐 galaxy）URL 见 `design.md §8`；本地 `artifacts/*.html` 可直接浏览器打开预览（相对引用 `./fonts.css` `./board.png` `./B_stone.png` `./W_stone.png`）。

---

## 1. 文件 → 真实代码 映射（核心表）

所有真实路径前缀 `katrain/web/ui/src/`。路由文件 `kiosk/KioskApp.tsx`。

| Artifact 文件 | 展示什么 | 现有路由 | 现有组件 | 类型 | 规范 |
|---|---|---|---|---|---|
| `d3-board-console.html` | 外壳 + 对弈 hub（选定方案） | `/kiosk/play` | `pages/PlayPage.tsx` | 换皮 | design §4.4 |
| `play-hub-states.html` | 对弈 hub 交互五态 + 数据态 | `/kiosk/play` | `PlayPage` | 换皮 | design §4.5 |
| `play-flow-setup-game.html` | 自由对弈设置 + 对局中（含**胜率走势图**） | `/kiosk/play/ai/setup/:mode`、`/ai/game/:sessionId` | `pages/AiSetupPage.tsx`、`pages/GamePage.tsx` + `components/game/GameControlPanel.tsx` | 换皮 | design §5.1 |
| `game-states.html` | 对局中 4 态（AI思考/需校准/终局数子/认输） | 同上 | `GamePage`/`GameControlPanel` | 换皮 | design §5.1③ |
| `tsumego-flow.html` | 死活 难度 hub + 沉浸解题页 | `/kiosk/tsumego`、`/tsumego/problem/:id` | `pages/Tsumego*.tsx`(6页) · `components/tsumego/TsumegoBoard.tsx` | 换皮 | design §5.2 |
| `tsumego-states.html` | 死活物理解题 5 态（LED 三通道） | `/kiosk/tsumego/problem/:id` | `TsumegoProblemPage` + `physicalTsumegoMachine`※ | 换皮 + 接物理 | design §5.2 |
| `research-flow.html` | 研究 编辑摆棋 → 分析中 → 分析报告 | `/kiosk/research` | `pages/ResearchPage.tsx`(现占位) | **换皮 + 新建报告页** | design §5.3 |
| `research-states.html` | 研究子态（摆子/删除/领地/失败/打开棋谱） | 同上 | `ResearchPage` + galaxy `ResearchToolbar`/`ResearchAnalysisPanel` | **下沉 galaxy** | design §5.3 |
| `kifu-flow.html` | 棋谱库 列表+预览 + 空态 | `/kiosk/kifu` | `pages/KifuPage.tsx` | 换皮 | design §5.4 |
| `baipu-flow.html` | 摆谱 选谱 + LED 引导摆子 + 拍照 + 提子 | `/kiosk/baipu`、`/baipu/session/:source` | `pages/BaipuListPage.tsx`、`pages/BaipuSessionPage.tsx` | 换皮 | design §5.5 |
| `live-flow.html` | 直播 赛事列表 + KataGo 解说观战 | `/kiosk/live`、`/live/:matchId` | `pages/LivePage.tsx`、`pages/LiveMatchPage.tsx` | 换皮 | design §5.6 |
| `tutorial-flow.html` | 教程 分类→章节树→图解+视频学习页 | `/kiosk/tutorial*` | `pages/Tutorial{Categories,Books,BookDetail,Section}Page.tsx` | 换皮 | design §5.7 |
| `settings-flow.html` | 设置主页 + 棋盘几何标定 | `/kiosk/settings`、`/vision/setup` | `pages/SettingsPage.tsx`、`components/vision/GeometryCalibrationWorkspace.tsx` | 换皮 + **改语言/补账户** | design §5.8 |
| `d1-ink-goban.html` / `d2-paper-launcher.html` | 备选方案①② | — | — | 存档（未采用） | design §2 |

※ 死活物理各状态的**后端/编排**属另一 worktree `../../../../katrain-kiosk-physical-tsumego`（track `kiosk-physical-tsumego`，尚未开发完）；本 track 只出视觉稿，实现期对齐其相位机/LED/语音契约。

---

## 2. 外壳改造（所有模块共用，先做）

方向 ③ = **Header（品牌+用户+时钟）+ 内容 + 底部 Dock**，取代现有 72px 左侧 `NavigationRail`。

| 现有组件 | 改造 |
|---|---|
| `kiosk/components/layout/KioskLayout.tsx` | 横屏改为 Header + 内容 + 底 Dock（竖屏分支删） |
| `.../NavigationRail.tsx`（72px 左栏） | → **底部 Dock 组件**（8 项等宽大靶，选中抬升 jade 实底） |
| `.../StatusBar.tsx`（40px） | 拆为 Header（品牌/用户/时钟）+ 有盘场景的状态格（摄像头/标定/LED） |
| `.../navTabs.tsx` | 8 tab 不变；**修图标**：棋谱 `MenuBook`→`LibraryBooks`、教程 `School`→`MenuBook`（对齐 galaxy，见 design §4.4/§5.7） |

---

## 3. 设计系统落地（从 mockup 抽成真代码）

mockup 的 `<style>` 里已是最终值，落地时抽成 `theme.ts` / CSS 变量：
- **配色**：石板令牌（`design.md §4.3`）——`--slate/--raise/--raise2/--hair/--ice/--sub/--dim/--jade/--jade-d/--amber/--red`。
- **字体**：Newsreader（衬线/品牌）+ Hanken Grotesk（无衬线/UI）——`artifacts/fonts.css` 是**开源近似替身 base64**；拿到 Anthropic 真身字体直接替换（design §4.2）。
- **盘面/棋子**：**必须与 galaxy 一致**，取值全来自 `components/Board.tsx` + `components/board/boardUtils.ts`（design §4.6 有对照表）。真实盘直接用这些组件，无需照搬 mockup 的 SVG。
- **LED 色语义**（死活/摆谱/物理对弈统一）：黑→红 / 白→绿 / 提子/拿除→蓝 / 提示·庆祝→白。
- 🚫 **全局禁 emoji**：SBC 无 emoji 字体 → 彩色 emoji 显豆腐块。**一律 MUI SVG 图标**（庆祝用 `EmojiEvents` 奖杯，非 🎉）。mockup 已内嵌 MUI 原始 path，实现期直接用同名 `@mui/icons-material` 组件。

---

## 4. SBC 双构建契约（硬性，来自根 `CLAUDE.md`）

- 两个产物：`web/static/`（全功能，`npm run build`）与 `web/static-kiosk-2d/`（SBC kiosk，`npm run build:kiosk-2d`，**无 three.js / galaxy / 3D**）。
- **共享地带**（`components/` 非 Board3D · `hooks/` · `context/` · `api.ts`+`api/` · `utils/` · `types/` · `theme.ts` · `i18n.ts`）改动**同时影响两个构建** → push 前跑**双 build**。
- `build:kiosk-2d` 链了 `verify:kiosk-2d`（grep dist 里 three/@react-three，命中即 fail）；CI 亦跑。
- 边界规则（`eslint.config.js`）：`src/kiosk/**` 不得 import `galaxy/**` `Board3D/**` `VideoRecorderPage*`。

---

## 5. 建议实现顺序 + 每模块验收

1. **外壳**（§2）——所有模块的地基，先做。
2. **设计系统**（§3）——`theme.ts`/`fonts.css`/图标映射。
3. 逐模块换皮，**换皮优先、新建其次**：对弈 → 死活 → 棋谱 → 直播 → 教程 → 设置（换皮）；**研究**（含新建分析报告页 + 下沉 galaxy `ResearchAnalysisPanel`，最重）；**摆谱**（接 LED/相机，与硬件联调）。
4. 每模块验收：`CI=true uv run pytest tests`（若动后端）+ **`npm run build` 与 `npm run build:kiosk-2d` 双绿** + `uv run black -l 120`。
5. 视觉逐屏对照对应 artifact。

---

## 6. 落地前需产品/你拍板的开放项

- **设置·账户退出**：kiosk 现**无任何登出控件**，稿里补了「账户 + 退出登录」（标「建议补充」）——是否要？
- **设置·语言**：稿已改为**仅中/英**（原代码含日/韩且是坏的 cosmetic 控件，违反项目规则）；实现期须**真正接 i18n**（现控件无效）。
- **几何标定方向**：现 `GeometryCalibrationWorkspace` 走 LED 角点闪烁；架构决定（`project_geometry_recalib_arch`）是 **no-LED 外框重标为主、LED demote 为手动 fallback**——落地按哪个？（铁律：几何标定**绝不自动亮灯**，仅用户手动触发。）
- **棋谱语义**：确认它是**只读赛事棋谱库**（非个人云存档）——如需"我的对局"存档，是另一未建功能。
- **品牌代码级改名**（弈航/BoardNavi → 智星盒/StellaBox）：仅 artifact + design.md 已改，**代码未动**；涉 galaxy+kiosk+共享+i18n+测试+logo 图片+法律 ToS，单独立项（design §7.6）。
- 各模块 **`§5.x 待补`** 子态（加载/失败/空态、标定相位等）：确认主稿后再补稿。

---

## 7. 相关文档

- `design.md` — 设计定稿（§4 系统 · §5 逐模块 · §6 落地映射 · §7 待定 · §8 索引）
- `plan.md` — 活台账（Phase 1/1b/2 进度 + 决策表）
- 根 `CLAUDE.md` §「SBC 构建边界契约」 — 双构建硬规则
- `superpowers/tracks/kiosk-physical-tsumego/`（另一 worktree）— 死活物理落子后端/相位机
- `superpowers/tracks/sbc-baipu-led-guide/` — 摆谱 LED 采集硬件设计
