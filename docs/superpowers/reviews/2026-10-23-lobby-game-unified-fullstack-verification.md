# 大厅对局统一版面与真实领地验证

日期：2026-10-23。基线 `5016186ed`，隔离分支 `feature/lobby-game-unified-20261023`，工作树 `/Users/fan/.config/superpowers/worktrees/katrain-kiosk-debug/lobby-game-unified-20261023`。

实现提交：`0e223cb454458e549874e98ce3159a3c4283a652`（后端）；`351b28dc4947d80b656ad8bea493daf1180a0c94`（前端）。保持本地可审阅；未 push、未合并 develop、未部署、未重启生产服务。原有 `fb19e95c2`、`5016186ed` 和主工作树其他调查文件不受影响。最终只读检查确认主分支仍为 `fix/kiosk-ui-debug@5016186ed`，另一个任务新增的 `docs/superpowers/reviews/2026-10-23-golaxy-hourly-kifu-sync-investigation.md` 保持未跟踪原状；本次不在主工作树集成。

## 实现与数据边界

大厅真实页 `/kiosk/play/pvp/room/:session_id` 使用独立 `LobbyGamePanel`，沿用 `GamePage` 的对局、数子、认输、退出、实体盘和终局处理。普通对局显示四个 `109×50` 操作：领地、数子、停一手、认输；坐标/手数同尺寸。玩家姓名、执色、提子、回合、本人座位、贴目和门槛均读真实 `gameState`。生产没有设计 fixture 的 fan、在线棋友、空盘或状态切换控制器。

领地链路：`useLobbyTerritory` → 既有认证 API transport → `POST /api/pvp/territory {session_id}` → 盒端当前代次/房间映射 → 现有 `PvpBoxBridge.forward_action` → 中央同名端点 → 服务端当前树快照 → 既有 `app.state.router.local_client.analyze`。KataGo 200 visits、30 秒超时、只请求归属；响应只含会话/局面身份、路数、手数、ownership、黑白预计区域和 stale。盒端重新校验、投影字段，不应用云端 state，也不广播私人结果。

中央只允许正在进行的普通真人大厅 free 对局，调用者必须实际占 B/W 座位；两座位都为正整数真人账号。拒绝旁观者、无登录、AI/机器人、平台/OGS、升降级及本地单用户局。实际大厅创建代码使用旧 `human` 拼写，窄守卫兼容它和 `player:human`；没有修改全局 Player 语义或通用分析权限。服务端取自己的 node path、setup、rules、komi、initialPlayer 和 moves，不信任客户端棋盘。跨 await 复用 `temporary_analysis_lease` 并在 finally 清理；中央同房间 singleflight。返回前复核参与者、终局、当前 session/room/generation 与局面。

客户端不在挂载或每手自动请求。点击有 loading，失败可再次点击“领地”重试；结果可隐藏/显示。换手、换局、换会话、终局、断线及禁用代次会清除/丢弃旧结果。归属转换为现有 EngineOverlay，未写回共享 gameState，不修改 analysis、终局、数子协商、计时、棋谱或记录。领地只是私人参考；正式结果仍用既有终局数子或认输流程。

## 最终验证

控制 agent 在最终前后端提交后独立执行以下命令。

工作树根目录：

```sh
./.venv/bin/python -m pytest -q tests/web_ui/test_pvp_territory.py tests/web_ui/test_pvp_box_routes.py tests/web_ui/test_pvp_box_bridge.py tests/web_ui/test_ai_ladder_territory.py --tb=short
```

结果：**96 passed，3 个既有 fixture failures**。其中新增领地 48 例全部通过（39 中央用例、9 盒端用例），包含真实 `create_multiplayer_session` 形态、B/W 权限、服务端快照、只读私有投影、引擎失败/非法结果、异步局面失效、取消清理、房间映射与登录代次变化。关联既有桥接/升降级领地覆盖没有新增失败。

`katrain/web/ui` 目录：

```sh
npx vitest run src/kiosk/components/game/LobbyGamePanel.test.tsx src/kiosk/pages/GamePage.test.tsx src/kiosk/hooks/useLobbyTerritory.test.tsx src/hooks/useGameSession.connection.test.tsx src/hooks/useGameSession.test.ts src/kiosk/components/game/GameControlPanel.test.tsx src/kiosk/components/game/GameControlPanel.clock.test.tsx src/api.lobbyTerritory.test.ts
npm run build:smartbox-kiosk-2d
KATRAIN_PW_VISUAL_PORT=5187 npx playwright test --config=playwright.visual.config.ts tests/kiosk-screen-06a-lobby-game.spec.ts --workers=1
```

结果：**8 个 Vitest 文件、178 tests 通过；生产构建 exit 0；3 个 Playwright 用例通过**。严格 Box SSO 和 kiosk 边界检查通过（无 legacy localStorage token 访问、无 three.js / galaxy / live API 进入 kiosk bundle）。`git diff --check` 通过。

Vitest 包括真实大厅操作 wiring、既有 GamePage/面板/时钟/会话回归、新 hook 错误重试和失效、重复点击、断线后重连同局面不复活旧结果。数子身份查询失败只禁用数子，不连带禁止合法停一手或认输。Playwright 使用真实 React runtime、真实字体/棋盘/logo 资源，网络和 socket fixture 仅在测试中；检查领地请求、错误重试、结果、换手清除、正式数子请求/应答和中央断线重连。

### 既有失败与限制

关联套件以下三个旧用例在新端点不会执行的路径中失败：

- `test_box_state_and_touchscreen_move_forward_to_central_without_local_commit`：期望 200、实际 409。
- `test_box_resign_uses_central_terminal_action_without_local_settlement`：期望 200、实际 409。
- `test_normal_central_game_end_preserves_result_without_outage_and_releases_sockets`：SGF 响应为 409 错误，没有 `sgf` 字段。

后端 worker 将 `git show 43047884d:katrain/web/server.py` 加载为隔离模块，并仅替换这三个测试中的 `create_app`，三项均同样失败。原因是旧 fixture 中裸 `MagicMock.local_confirmation_in_progress` 为真，撞上基线已有的确认中 409 守卫。本次没有修改这些测试或守卫。主会话告知的 `PhysicalBoardGuard.test.tsx:62` 旧文案预期失败与本次无关，未扩改。

没有调用真实 GPU 或操作两台真实设备；引擎与网络契约通过 deterministic fake 验证，浏览器使用隔离测试数据。因此尚不声称完成生产实机验收或上线。

## 同尺寸视觉核对

批准参考：`/Users/fan/Repositories/katrain-kiosk-ui-redesign/output/playwright/lobby-game-four-actions-1024.png`。本次未修改 sibling 设计仓库。

浏览器实测 `1024×600`：board `[16,70,516,516]`，rail `[548,70,460,516]`，header 62、paired seats 104、status 152；6 个动作/显示按钮均 `109×50`，gap 8；8 枚图标均 `22×22`；无页面或右栏溢出。

控制 agent 实际查看了参考图、实现图、并排图和 50% 叠加图，另查看数子等待与领地结果状态。构图、几何、卡片层级、18/22/28 正文字号、配色、石子、圆角和软键材质已对齐。先发现的地图/手数图标过大已在大厅作用域修正并加入真实浏览器尺寸检查。

明确差异：

- 共享顶栏维持当前生产的品牌/时间字号与结构；未扩张本切片修改全局壳。
- 当前触屏模式显示“请在棋盘落黑子”，实体盘模式显示识别同步提示；不把设计的实体盘说明硬编码到触屏。
- 规则副行复用真实开局格式“19 路 · 中国规则 · 贴目 7.5 · 不让子”，设计 fixture 的“分先”为等义标签。
- 手数使用现有 `list-numbers`，领地复用 `map-trifold`，与坐标网格区分，语义对应批准稿。
- 页脚用真实门槛和“仅供参考，正式胜负以数子为准”，移除“设计示意”；结果时补充真实领地区域。
- 中央断线保持既有全页“盘面未知”重连操作，不继续展示无法确认的旧棋盘；字号已调整为 18/28。

证据保留在本工作树忽略目录 `output/playwright/lobby-game-unified/`：

- `reference-1024.png`
- `normal-1024x600.png`
- `territory-error-1024x600.png`
- `territory-result-1024x600.png`
- `count-pending-1024x600.png`
- `disconnected-1024x600.png`
- `comparison-side-by-side.png`
- `comparison-overlay.png`
- `comparison-difference.png`

## 独立评审

计划：Astra Max 一轮 Approved，见 `2026-10-23-lobby-game-plan-review.md`。

规范审查：独立 reviewer 已 Approved，见 `2026-10-23-lobby-game-spec-review.md`。

Astra Max 最终代码审查：**Approved**，审查范围 `5016186ed..351b28dc4947d80b656ad8bea493daf1180a0c94`，无 material findings。审核者独立执行 48 后端 + 33 前端聚焦测试均通过、diff check 通过。见 `2026-10-23-lobby-game-astra-code-review.md`。代码未在审核后修改；后续提交仅收录本验证文档、计划勾选与独立评审记录。
