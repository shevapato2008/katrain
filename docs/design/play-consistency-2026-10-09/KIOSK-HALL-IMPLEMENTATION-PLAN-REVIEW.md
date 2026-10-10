# Kiosk Hall Implementation Plan Review

**Final / Round 2: Approved. M1 resolved; no remaining must-fix plan findings.**

**Round 1: Changes requested — 1 must-fix.**

独立审核：GPT-6-astra，max。审核对象为 `docs/superpowers/plans/2026-10-09-kiosk-hall-star-alignment.md`，并核对已批准 v3 HTML、当前工作区的大厅/观战页面、会话状态与 WebSocket 生命周期、中央/盒子桥接及对应测试。未修改实现代码，未运行实现验收。

## Must-fix

**M1 — 明确 HTTP 观众变化如何送达已连接的 Galaxy 房间，避免人数无限期陈旧。**

- 计划 Task 2 数据规则 6（第 48 行）仅承诺 HTTP presence 变化反映在后续读取或状态广播；Task 4 同时要求 Galaxy 房间显示权威观战人数。
- `katrain/web/ui/src/hooks/useGameSession.ts:180` 与 `useSessionBase.ts:69` 只在连接时读取状态，没有周期轮询。`katrain/web/api/pvp_spectator.py:66` 的快照读取也不会广播；`server.py:1099` 的状态读取只刷新缓存。`session.py:341` 的 `_on_state` 由实际状态更新触发，不能保证在棋手长考或对局结束后再次发生。
- 因此，Galaxy 已显示 1 人时，另一名用户通过 kiosk HTTP 加入，Galaxy 可能一直显示 1；HTTP 用户离开并超过 10 秒 TTL 后，也可能一直保留过期人数。大厅下一次 GET 得到正确值，不会自动更新房间里的 WebSocket 客户端。
- 最小修正：计划写明 HTTP 身份并集发生变化时发送既有 `spectator_count` 事件，并明确无其他读取/落子时的过期通知期限及触发点。例如在有 HTTP presence 的会话内安排一个可取消的最近过期回调，过期时仅重算人数并按需广播；会话销毁时取消。也可复用已有维护机制，但需写清最大延迟。保留 `count` 原始 socket 语义，无需引擎请求、数据库、新轮询接口或前端计时器。
- 在已有 presence/观战测试内补两个聚焦场景：已连接 WS 观察者收到另一 HTTP 用户加入后的新人数；所有 HTTP 请求停止且没有棋盘更新时，超过规定期限后 WS 收到扣除人数。重复心跳和同身份 WS+HTTP 不应增加人数。

## 其余结论

- 会话内身份并集、排除两席、负数机器人身份、不伪造 socket、monotonic TTL、懒清理与会话销毁边界均可沿用现有结构，无需持久化服务。
- 增量新增 `spectator_count`，保留 `sockets_count`/事件 `count`，符合现有兼容要求。严格盒子的观战 GET 已原样转发中央响应；他人棋局保留云端 ID，自己的棋局才映射本地 ID，与计划一致。
- 大厅 v3 的尺寸、标签、邀请确认和键盘交互有已批准 Artifact 支撑。任务边界与文件归属清楚；现有未提交工作需继续保留。
- 直接受影响的现有 WS 权限/读取测试是 `tests/web_ui/test_game_termination_and_chat_identity.py`；盒子回归可直接使用 `test_pvp_box_routes.py`、`test_pvp_box_bridge.py`，不必另建验证基础设施。

修正 M1 后可进入第二轮且最后一轮计划审核。无需扩展视觉范围或开展全量回归。

## Round 2 — final

2026-10-10，GPT-6-astra，max。复核修订后的 Task 2 规则 6 及对应测试计划，**Approved**。

- HTTP touch 导致唯一观众人数变化时立即推送既有事件；静止房间的 HTTP TTL 过期由单个会话内回调通知，闭合 M1 的加入和离开两种场景。
- 回调只计算 presence，不读取引擎或棋局状态；只在仍有 HTTP 成员时续排，并验证当前注册的会话对象，销毁时取消。实现范围与当前需求相称。
- 计划明确保留旧 `count`/`sockets_count` 的原始 socket 语义，并以确定性时钟/调度验证无落子、无后续 GET 的通知，无需真实等待 10 秒或新增测试基础设施。

实施时，人数变化比较必须以修剪前的已知人数或最近已发布人数为基准，避免第一次 `count()` 已懒清理导致过期回调把变化吞掉；这是 M1 的实现注意点，由已计划的无活动过期测试验证。

两轮计划审核已完成，可以按文件归属开展前后端实现。此批准针对实施计划，实际代码、视觉和测试结果仍按计划验收；本轮未修改实现代码。
