# RK3588 Kiosk UI 开发计划审核（Codex）

- 审核对象：`superpowers/tracks/rk3588-ui/plan.md`
- 审核依据：`superpowers/tracks/rk3588-ui/review-prompt.md`
- 日期：2026-02-17
- 结论：**有条件通过（需先修复 P0，再进入实现）**

## 总体判断
计划的方向是对的：先做 kiosk 独立壳层、快速出可点可看的前端、再接后端与硬件，能降低前期耦合风险。
但当前计划里有几项“会直接影响落地”的问题（主题切换方式、字体来源、测试策略与需求不一致），这些不是优化项，是上线阻断项。

## 关键问题清单（按严重度）

## P0（阻断）

1. 主题切换实现不具备路由响应性
- 证据：`plan.md:667` 使用 `const isKiosk = window.location.pathname.startsWith('/kiosk');`。
- 风险：只在初次渲染计算，开发态从 `/galaxy` 切到 `/kiosk` 主题可能不更新；后续若扩展多入口，会引入隐性样式错乱。
- 建议：把 `ThemeProvider` 下沉到 `GalaxyApp` / `KioskApp` 各自入口，或在 Router 内使用 `useLocation()` 驱动主题。

2. 字体方案与“无 CDN 依赖”需求冲突
- 证据：`plan.md:613` 使用 Google Fonts `@import`；需求写明本地字体（`review-prompt.md` Hardware & Environment）。
- 风险：离线/内网部署直接失效；首屏字体闪烁；区域网络下不可用。
- 建议：Phase 1 就改为本地 `@font-face`（woff2 子集），并把字体加载与回退策略写进任务。

3. “严格 TDD”与任务设计不一致
- 证据：`review-prompt.md` 写“strict TDD”，但任务 8-13 基本是 `visual verify`。
- 风险：路由、状态、交互回归不可控；后续重构 shared 层时缺乏保护网。
- 建议：至少补齐每页 1 个 smoke test（渲染+关键 CTA 可点击+关键路由跳转），并加一套 kiosk 导航集成测试。

4. 需求里“每次开机需登录”，计划里没有对应任务
- 证据：`review-prompt.md:39` 明确 login required；`plan.md` 14 个任务中无登录流/会话失效流。
- 风险：流程评估失真，后续补登录会重排路由与入口状态机。
- 建议：Phase 1 增加最小登录壳页与路由守卫（即便用 mock auth）。

## P1（高优）

1. 全局 `MuiButton.minHeight=56` 过于粗暴
- 证据：`plan.md:138`。
- 风险：在 3x2 控制按钮区会挤压信息密度；并非所有按钮都应 56。
- 建议：改成按语义分层：`touch-lg`（56）、`touch-md`（48）；默认不全局覆盖。

2. Tab 激活匹配用 `startsWith` 有误判风险
- 证据：`plan.md:381`。
- 风险：`/kiosk/livewatch` 可能命中 `/kiosk/live`；未来扩展路由会踩坑。
- 建议：使用 `matchPath` 或按 segment 精确匹配。

3. 7 英寸下导航信息密度偏高
- 现状：状态栏 40 + 底栏 64 = 104px 固定 chrome。
- 风险：例如 1024x600 仅剩 496px 高度给主内容；棋盘可视面积明显受限。
- 建议：
  - 方案 A：底栏保留 5 项，其余进“更多”；
  - 方案 B：改左侧 rail（更适配横屏）；
  - 方案 C：非游戏态显示双栏，游戏态自动收起状态栏。

4. Mock 数据随机化导致不可复现
- 证据：`plan.md:1415` `Math.random()`。
- 风险：视觉验收与问题复盘不可重复。
- 建议：使用固定 seed 或静态 fixture（`kiosk/mocks/`）。

5. BrowserRouter 深链接回刷风险未覆盖
- 风险：kiosk 访问 `/kiosk/ai/setup/free` 时若服务端未做 SPA fallback，刷新 404。
- 建议：补一个“部署约束任务”：FastAPI/静态服务器对 `/kiosk/*` 回退到 `index.html`。

6. 字体家族/字重组合偏重，嵌入式首屏成本高
- 风险：三家族 + 多字重加载会拖慢首屏、占内存。
- 建议：Phase 1 先 2 家族（Sans + Mono），Serif 仅保留标题单字重；按页面分包。

## P2（可优化）

1. `PlaceholderPage` 脚手架方案可接受，但要设置清理门槛
- 建议：定义“第几任务后禁止新增 Placeholder route”。

2. `GameControlPanel` 当前 60 行不必立即拆分
- 建议：当出现复用或超过 ~150 行再拆。

3. 单 Vite 构建可行，但应显式做入口级懒加载
- 建议：`GalaxyApp` / `KioskApp` `React.lazy`，避免互相拖包体。

## 针对评审问题的逐条回答

1. `ThemeProvider` 放哪里？
- 结论：**不要**用 `window.location.pathname` 一次性判断。
- 推荐：每个 app 自带 ThemeProvider，或 Router 内基于 `useLocation` 响应式切换。

2. 单构建是否足够？
- 结论：可以，但要加入口级 code-splitting 和路由级懒加载。

3. shared 层延后到 phase 2 是否合理？
- 结论：可接受，但需加“防复制红线”：业务逻辑一旦进入 kiosk，不允许复制 galaxy hook。

4. 色彩对比度是否达标？
- `#e8e4dc` on `#1a1714`：**14.08:1**（AA/AAA 均通过）。
- `#6b6560` on `#1a1714`：**3.11:1**（普通正文不通过 AA 4.5:1；大字可过 3:1）。
- 结论：secondary text 需提亮（建议至少到 4.5:1）。

5. 三字体是否过重？
- 结论：在 RK3588 可跑，但首屏和内存会受影响；建议收敛字重并本地子集化。

6. 8 个底部 Tab 是否过多？
- 结论：对 7 英寸偏多，建议 5 主入口 + More，或改侧边 rail。

7. `@mui/icons-material` 是否足够语义化？
- 结论：可用但区分度一般。建议为 AI/死活/棋谱定制图标或至少混合本地图标。

8. 游戏页隐藏底栏是否合理？
- 结论：合理，且应作为强约束（对弈态沉浸优先）。

9. WebSocket vs polling？
- 结论：WebSocket 正确。
- 补充：计划里要加重连、心跳、乱序/重复事件处理策略。

## 计划缺失项（建议新增任务）

1. 登录与会话壳层（mock auth + route guard）。
2. 本地字体打包与 preload 策略（移除 CDN）。
3. kiosk 导航集成测试（8 tab、全屏路由、重定向）。
4. 关键页面 smoke tests（替代纯 visual verify）。
5. `/kiosk/*` 刷新回退配置验证（开发与生产各一次）。
6. 设备真机性能基线：首屏时间、FPS、内存、WebSocket 端到端延迟。
7. 异常态 UX：引擎离线、传感器断连、网络抖动、会话过期。
8. 输入仲裁策略：物理棋盘输入与触摸输入冲突规则。

## 建议的准入门槛（Gate）

进入 Phase 2/3 前至少满足：
- P0 全部关闭。
- kiosk 关键流（登录→选模式→开始对局→退出）有自动化测试覆盖。
- 无 CDN 依赖，离线可启动。
- 在目标 RK3588 设备上完成一次性能冒烟并留档。

## 最终建议
当前计划可继续推进，但请先修复 P0 项，再开始批量页面开发。否则后续返工点会集中在路由主题、字体部署、测试补债和登录流程，成本会明显放大。
