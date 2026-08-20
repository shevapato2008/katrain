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

## 7. 仍然未决，不许自己定（`kiosk-design-alignment.md` §4）

这两条 Fan 至今没答复，碰到了要停下来问，**不要私下约定**：

1. **破坏性按钮的长相**：象棋模板是「屏上实心 accent、二次确认框里才变红」，
   国象和围棋现版是「屏上就描边」。两派都自洽但不能同时成立。
2. **挡局时左边画不画盘**：参考图画完整棋盘（起始局面），围棋现版是虚线空态。
   参考那样画等于摆一个**不是这一局**的局面。
