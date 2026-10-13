# 本地逐手确认 · 独立代码审核与验收决定

日期：2026-10-12。范围：`feature/kiosk-local-play` 基于 `9a36555a9bc9cc6bdb16d77fe8fb71f6b177a1c8` 的本次提交前改动。按用户授权独立审核，采用 AGENTS.md 的比例原则；既有 1024×600 视觉已获用户确认，本轮只核对代表性真实联调画面。

## 代码审核：PASS

本轮发现的 Important 问题已修正并复核，当前没有待修的 Critical / Important 代码问题。审核集中于本次真实风险：合法棋谱提交、并发及取消、双钟、准备状态、完整视觉管线与旧接口隔离。

| 审核发现与修正 | 代码位置与可验证依据 |
| --- | --- |
| 识别中旧认输接口仍可终结游戏 | `katrain/web/server.py:1092` 的 `guard_session_terminator` 现在也检查确认暂停；真实并发 HTTP 探针验证认输返回 409，棋局不终结。旧 `/api/move`（同文件 `:1360`）对本地局拒绝，普通 vision 自动提交分支也拒绝本地局。 |
| 删除会话后晚到候选仍可入谱 | `katrain/web/server.py:1168` 的移除 hook 调用 `LocalConfirmationController.close`（`katrain/web/core/local_confirmation.py:54`）；controller 的 `_closed` 参与最终提交校验并关闭匹配窗口。独立探针先确认开窗、再 DELETE、随后交付合法候选，结果 accepted=false，棋局仍在根节点。该探针曾真实复现旧代码 accepted=true，修正后通过。 |
| 视觉清理异常可能留下永久暂停 | `katrain/web/core/local_confirmation.py:144` 把初始广播纳入 try；`:280` 起清理视觉、恢复暂停、缓存结果和清除活动请求采用嵌套 finally。注入 `cancel_local_window` 异常后仍释放暂停与 `_active`，通过独立探针。 |
| 同会话新局与显式 bootstrap 重试误用旧状态 | `katrain/vision/service.py:205` readiness 同时匹配 session、game 与模式代际；`katrain/vision/worker_inprocess.py:1636` 新局清理旧 reference 并重新 bootstrap。重试等待本次代际，旧 unavailable 不会让请求立即失败。新增两项回归测试通过；同局重复绑定仍保留参考。 |
| 准备失败无可操作的恢复方式，未起钟却显示倒数 | `katrain/web/ui/src/kiosk/pages/GamePage.tsx:423` 的实体普通确认先进行一次显式绑定准备重试，虚手不调用相机；准备失败投影 unavailable，`LocalConfirmGame.tsx:81` 提示先整理成屏幕盘面。`katrain/web/interface.py:722` 的本地局有效 paused 包含未 clock_started。 |

## 核对的功能边界

- 屏幕预选独立于权威 stones / node；确认请求绑定 game、node、颜色和 request_id。相同进行中请求共享结果，另一 id 返回冲突；缓存先于旧节点检查，响应使用当前权威状态。
- 原时钟暂停状态保留；确认前核实已超时，识别期间双钟不扣时，成功换方、失败保留原方。虚手沿用原终局流程，不开识别窗口。普通成功仅使用已有带 after_node_id 的音效链路。
- 实体窗口要求 `InProcessAdapter`、实际 reference_check=on、合格初始参考与点击后的不同新帧。等待阶段的 gate 位于模型推理之前；相机采集保持运行。候选继续通过原多帧、置信峰及疑似子后处理；controller 另核验真实规则预演后的完整盘面及提子。
- 成功参考更新只使用窗口缓存的原始投票/观测/灰度帧，并保留原捕获守卫；失败不销毁参考。token、模式代际与最终节点校验阻断旧事件。local 观测不进入旧自动落子或错误弹窗协议。

## 独立验证证据

1. `.venv/bin/python -m pytest -q tests/test_local_move_confirmation.py tests/test_vision/test_local_confirmation_window.py --tb=short --show-capture=no`：**29 passed，5.40 秒**。覆盖成功、无子、多子、合法提子/提子未清、超时恢复、虚手、幂等、新帧、reference 守卫及准备代际。
2. 四项临时真实 TestClient 并发/异常审查探针：**4 passed，3.30 秒**。分别验证认输 busy、删除后迟到候选、相同请求并发只开一窗且其它 id 冲突、清理异常释放暂停。探针不进入生产代码，也未扩展为额外测试框架。
3. `git diff --check` 通过。测试使用临时 SQLite 与既有隔离 fixture，未写用户真实业务库；仅有现有 passlib/crypt 弃用警告。
4. 阅读真实联调 [Playwright 记录](../../../output/local-confirm-runtime/browser-integration.txt)，并检查同为 1024×600 的[初始画面](./integration-screen.png)、[最后预选 F6](./integration-screen-selected.png)及[确认后换白方](./integration-screen-accepted.png)。测试使用真实生产 API 代码、临时数据库中的真实认证/会话、实际 Vite 页面与 WebSocket，没有业务 Fixture。先点 E5、再点 F6，确认前 node=0、请求=0、落子音=0；确认仅发 1 个请求，coords=[5,5]；随后 node=1、turn=W、last_move=[5,5]、preview=null、local_confirmation=idle、timer.paused=false。Media.play 仅记录一次 stone3.wav，调用时页头已为第 1 手，pageerrors 为空。这里验证的是音频触发与画面顺序，不冒充实体扬声器测量。
5. 实施代理另报告受影响后端 **167 passed**、视觉相关 **140 passed**、最新前端三文件 **88 passed**，`build:kiosk-2d` 成功。这些是实施代理的较广验证记录；本审核独立执行并核对的证据为前四项。

## 用户代理验收与发布决定

**GO：代码审核与屏幕软件验收通过，允许继续已授权的 feature/develop 集成、SmartBox 精确子模块引用发布及两云选择性部署。** 真实预选、提交、换方、时钟恢复与画面后单次落子音均已取得联调证据；无需再追加视觉截图轮次。测试环境使用 NullEngine，画面的引擎不可用提醒不代表本次确认功能失败。

本决定对应上述已审核的改动；合并新 develop 如产生影响本次行为的冲突，需针对冲突结果复核。部署仍需执行现役版本、实际资源与代表页核验；软件 GO 不等于云端已经发布。

**RK3562 激活/实机验收：未通过，待继续。** 目前没有真实设备连接/实体盘验收证据，不能宣称设备已部署或功能已整体验收完成。实体完整管线的测试证明软件边界，不证明 RK3562 上的实际延时、相机/模型配置和物理摆盘效果。发布继续按 [RELEASE-DECISION.md](./RELEASE-DECISION.md) 的顺序、范围和既有局保护要求执行；联网不可达不阻止独立的软件集成及两云工作。
