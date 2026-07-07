# Review Request: Kiosk 跨平台对弈 — 星阵围棋 (Golaxy) 人机对弈接入开发计划

> **致审阅者（Gemini / Codex）**：这是一份**开发计划的审核请求**。请审阅下述计划的架构决策、任务分解、测试策略与风险清单，按文末「审阅输出格式」返回意见。**代码尚未开始编写** —— 现在是纠正设计问题成本最低的时刻。
>
> 待审文档（与本文件同目录）：
> - **[`plan.md`](./plan.md)** — 实施计划（主审对象）
> - **[`golaxy-protocol.md`](./golaxy-protocol.md)** — 协议逆向参考（2026-07-02 实盘抓包验证，作为计划的事实依据）
>
> 仓库根目录 `CLAUDE.md` 含项目全局约定（构建边界等）。审阅时可直接读仓库代码。

---

## 1. 项目背景

**KaTrain** 是一个围棋对弈/教学应用（Python FastAPI 后端 + React/Vite 前端），部署形态之一是运行在 RK3562/RK3588 SBC 上的**智能棋盘 kiosk 终端**（实体棋盘 + 摄像头识别落子 + LED 引导）。

kiosk 有一个「跨平台对弈」功能：通过 platform adapter 架构把 KaTrain 棋盘接入第三方围棋平台。目前 **OGS 已端到端跑通**（参考实现），**星阵围棋 (Golaxy, 19x19.com)** 卡片显示「即将支持」。

**本期目标**：让星阵卡片可用，跑通**人机对弈（vs 星阵 AI bot）**完整闭环：

```
用户在 kiosk 选星阵 bot + 级别 → 在棋盘落子
  → KaTrain 后端调星阵 genmove 隧道 → 拿到 AI 回招 → 显示在棋盘
```

## 2. 关键事实（已实盘验证，无需重新调研）

以下来自 2026-07-02 真实账号登录 + XHR hook 抓包（详见 `golaxy-protocol.md`），**审阅时请当作已确认的事实**：

1. 星阵人机对弈是**无状态 REST genmove 隧道** —— 没有 WebSocket、没有服务器端 gameId、没有对局会话。客户端每手把**完整着手历史**（CSV of coord ints）发给 `GET /api/engine/dcnn/tunnel/genmove`，拿回 AI 下一手 `{coord, prob}`。
2. 坐标编码 `coord = (19 - boardRow) * 19 + colIndex`（0..360，左上角起先行后列），已用 9 手实盘对照验证。
3. AI 强度参数 `level` = bot 的 `eloScore`，全 39 级表已从客户端 Vuex 抓出。
4. 鉴权（手机号 OAuth2：密码 / 短信验证码 / refresh_token）**已在 `katrain/web/platforms/golaxy/adapter.py` 实现并验证可用**。隧道用非标准 header `Auth_token: <access_token>`。
5. 星阵的社交 WebSocket 只承载在线状态/心跳，与人机着手无关；`/api/social/wsgame/*` 是人人对弈路径，人机不用。

**两个已知的未捕获数据**（计划已列为开发中补齐项）：PASS 的 coord 编码；`resign=6` 参数的确切语义。

## 3. 核心架构决策（请重点审这里）

现有跨平台脚手架（OGS 已验证）：

| 组件 | 文件 | 职责 |
|---|---|---|
| `PlatformAdapter` 抽象 | `katrain/web/platforms/base.py` | `connect` / `submit_move` / `on_opponent_move` 事件流 |
| `PlatformManager` | `katrain/web/platforms/manager.py` | `start_platform_game()`，管理带 gameId 的 `PlatformGameSession` |
| `PlatformCommandGateway` | `katrain/web/platforms/gateway.py` | 棋盘落子 → 提交远程 → ACK → 本地落子 |
| REST 端点 | `katrain/web/api/v1/endpoints/platforms.py` | 前端入口 |
| 星阵 adapter | `katrain/web/platforms/golaxy/adapter.py` | 鉴权已实现；现有 `submit_move` 走人人对弈 gameroom 路径 |
| kiosk 前端 | `katrain/web/ui/src/kiosk/pages/PlatformConnectPage.tsx` | golaxy 被 `comingSoon:true` 挡住 |

**计划的核心设计**（plan.md §3）：

1. **人机局 = 「KaTrain 本地对局 + 星阵引擎作为对方」的会话**。因为隧道无状态、KaTrain 自己持有 moves 列表，所以用**合成的本地 game_id** 标识 engine-game 上下文 `{moves: list[int], config: {level, komi, rule, handicap, human_color, board_size}}`。
2. **engine-play 单独一条路径，不复用现有人人对弈 `submit_move`**。`submit_move(game_id, ...)` 内部按 game_id 是否属于 engine context 分流（保持人人对弈路径向后兼容）。
3. **提交人类手 + 获取 AI 回招在同一次隧道调用内同步完成**：人类手编码 append → 调隧道 → AI coord append → 通过既有 `on_opponent_move` 回调抛给 manager → 广播到棋盘。这样 manager / gateway / 前端棋盘**几乎零改动**——它们已经会处理「我方落子 → 对方落子回来」。
4. 人类执白时：`start_engine_game` 创建后立即调一次 genmove 让 AI（黑）先下。
5. **adapter 与端点跑在服务端**（token 不下发到 kiosk 终端）；board 模式下前端经既有 board-proxy 访问 `/api/v1/platforms/*`。

## 4. 实施阶段概要（详见 plan.md §4）

- **Phase 0** — 环境与基线：`uv sync`、`CI=true uv run pytest tests` 绿色基线、通读 OGS 参考链路。
- **Phase 1** — 坐标编解码 + genmove 客户端（纯函数，TDD，以实盘 9 手对照为金标准单测；协议层用 respx/httpx mock）。
- **Phase 2** — Adapter engine-play 方法 + 本地 game context（`start_engine_game`、engine 分流、resign、mock 单测状态机）。
- **Phase 3** — Manager / Gateway 接线 + REST 端点（`POST /{platform}/engine/start`；落子复用既有 gateway 通道；FastAPI TestClient 测试）。
- **Phase 4** — 前端 kiosk：去掉 comingSoon、人机设置页（39 级表选择器）、对局页接线；两套构建（`npm run build` + `npm run build:kiosk-2d`）都必须绿。
- **Phase 5** — 真机端到端验证（真账号一次性）：连续多手核对 AI 回招；抓 PASS/终局行为；board 模式代理验证。

每个 Phase 有自动化 Verification + 人工 review checkpoint。

## 5. 明确的非目标（请勿建议加回来）

以下是**有意排除**的本期范围，审阅时请不要把它们作为「缺失」提出（除非你认为排除本身会导致本期设计不可扩展）：

- 人人对弈（gameroom / STOMP）、升降级对弈、联棋、高水平对弈
- 计时（本期固定不计时）
- 服务端数子/胜负判定（终局只支持 resign 与自然停手）
- 野狐 (fox)、OGS 的改动
- 3D 棋盘 / galaxy 相关（kiosk 构建禁止引入 three.js，见 CLAUDE.md「SBC 构建边界契约」）
- 星阵官方合作/API 条款问题（用户已明确：本期只做技术打通，法律合规另行讨论）

## 6. 希望重点审阅的问题

### A. 架构
1. 「engine-play = 同步一问一答装进 `on_opponent_move` 回调模型」是否合理？有没有更契合现有 adapter 抽象的做法？
2. 合成本地 game_id + `submit_move` 内部按 game_id 分流（engine vs gameroom），这个双路径设计有没有向后兼容或可维护性隐患？是否应该干脆用独立的方法名（如 `submit_engine_move`）而不是分流？
3. `manager._on_opponent_move` 目前是「扫描 active games」找 context——单局 OK，但计划建议「如需可让 PlatformMove 带 game_id」。这个并发/多会话隐患需要本期就修，还是可以留到多局需求出现时？
4. 无状态隧道意味着 KaTrain 的 moves 列表是唯一真状态。**悔棋、断线重连、服务重启、页面刷新**这些场景下状态恢复的设计计划里没有展开——这是不是 Phase 2/3 必须补的任务？

### B. 协议与健壮性
5. genmove 是同步阻塞调用（棋盘落子 → 等 AI 回招）。高级别 bot 思考时间未知，**HTTP 超时怎么设、超时后 moves 列表如何保持一致**（重试会不会导致 AI 下两手）？计划只提到「处理超时」，是否需要更具体的幂等/重试设计？
6. `code != "0"` 的错误码语义未知（token 过期？非法 moves？风控？）。仅透传错误是否足够，还是应该在 Phase 1 就设计错误分类（可重试 vs 需重新登录 vs 终止对局）？
7. PASS coord 未知 + AI 认输的表示方式未知。计划的处置是「UI 禁用 pass、只留 resign」——如果**AI 主动 pass 或认输**（返回特殊 coord），当前设计会怎么失败？需要防御性处理吗？
8. Token 生命周期：access_token 过期时 engine 路径的自动 refresh —— 计划列为风险但没有对应的实施任务，是否应该在 Phase 2 显式加任务 + 测试？

### C. 测试策略
9. 「纯函数 TDD + 协议层 mock + 端点 TestClient + 真机只在 Phase 5 一次」这个分层够不够？有没有值得加的测试类型（如 moves 列表状态机的 property-based 测试）？
10. 金标准对照表只有 9 手 + 2 个反解，覆盖了角/边/天元吗（Phase 1 Verification 提到要测边界）？你认为还需要哪些必测坐标？

### D. 前端
11. 39 级表放前端常量 vs 后端 `/{platform}/engine/levels` 端点，计划两可。你的建议及理由？
12. kiosk 构建边界（禁 three.js，改 shared 文件要跑两套构建）在 Phase 4 的约束够明确吗？

### E. 整体
13. Phase 划分和依赖顺序是否合理？有没有应该拆开或合并的 Phase？
14. plan.md §8 风险清单有没有遗漏的重大风险？
15. Definition of done（§9）是否可验证、有没有漏项？

## 7. 审阅输出格式

请按以下分级返回意见，每条注明针对 plan.md 的章节号（或本文件 §6 的问题编号）：

1. **🔴 Blocking** — 不改会导致返工/事故的设计问题，必须在开工前解决
2. **🟡 Important** — 强烈建议采纳，但可以在对应 Phase 内解决
3. **🟢 Minor / Nit** — 可选改进
4. **❓ Questions** — 需要计划作者澄清的疑问

若你有仓库访问权限，欢迎核对计划引用的代码现状（`katrain/web/platforms/` 下 `base.py` / `manager.py` / `gateway.py` / `golaxy/adapter.py` / `ogs/`，测试在 `tests/platforms/`）；若认为计划对现有代码的描述与实际不符，请作为 Blocking 提出。

---

*Generated 2026-07-02 · branch `feature/kiosk-play-golaxy` · worktree `/Users/fan/Repositories/katrain-kiosk-play-golaxy`*
