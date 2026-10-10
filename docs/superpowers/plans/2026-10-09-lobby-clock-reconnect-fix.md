# 对战大厅时钟与重连修复计划

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development or superpowers:executing-plans. Keep verification focused on the reported regressions.

**Goal:** Galaxy 观战刷新继续使用服务端当前时钟；实体 kiosk 在服务短暂重启后自动恢复大厅；大厅标题使用现有楷体。

**Architecture:** 保留现有服务端时钟权威和参与者权限。只对本地自有多人对局的 HTTP 读取与 WS 首帧生成当前状态；盒端中央对局继续使用现有桥接。前端在收到新的用时快照后重置插值基线，非行棋方不使用行棋方的读秒用时。Kiosk 大厅瞬断后退避重连，身份撤销不自动重连，不自动重发匹配或邀请。

**Tech Stack:** FastAPI / WebKaTrain、React / Vitest、Playwright、Docker、RK3562 Chromium CDP。

## Task 1：观战时钟

Files: `katrain/web/server.py`, `tests/web_ui/test_game_termination_and_chat_identity.py`, `katrain/web/ui/src/components/PlayerCard.tsx`, `PlayerCard.test.tsx`。

- [ ] 先加 HTTP 与 WS 首帧回归：缓存帧旧、服务端钟已前进；刷新和另一个观众必须得到当前值，观众不得启动钟。
- [ ] 对自有多人局在会话锁内生成当前状态并保存快照；保留已结束、远端、单人局的现有处理和权限。
- [ ] 先加读秒快照回归；新用时快照首次 render 即使用零插值，防止 effect 归零前误触发超时或声音；非行棋方传入零节点用时；只依据新用时数据更新基线，观众人数变化不重置钟。加入最后一段读秒有效快照不提前触发 onTimeout 的用例。
- [ ] 运行相关计时、只读观战和 PlayerCard 测试。

## Task 2：实体大厅恢复（独立 agent）

Files: `katrain/web/ui/src/kiosk/pages/LobbyPage.tsx`, `LobbyPage.test.tsx`, `katrain/web/server.py` 的盒端大厅 WS 认证错误映射, `tests/web_ui/test_pvp_box_routes.py`。

- [ ] 用真实截图、日志确认断线原因；先加服务重启后的失败用例。
- [ ] 瞬断后自动退避重连；断线期间保持诚实提示、关闭匹配等待；身份拒绝/撤销不重试，卸载与账号切换清理旧连接。
- [ ] 盒端 bridge.identity 的 PvpBoxAuthError 与上游 WS 1008 必须保留为认证终止（BOX_SESSION_REVOKED / 1008），不能统一转换为可重试的 1013；用现有盒端路由用例验证两处边界。
- [ ] 验证重连不重发业务消息，相关 UI 回归通过。

## Task 3：字体与交付

Files: `katrain/web/ui/src/galaxy/pages/HvHLobbyPage.css`。

- [ ] 局部标题覆盖全局 sans 标题规则，继承当前页面楷体；一次真实预览检查实际字体。
- [ ] GPT-6-astra max 独立审核计划与最终改动；修复重要问题后合并。
- [ ] 构建普通 Web 与严格盒端 UI；追最新 develop、推 feature、合入 develop、更新 smartbox main 子模块指针。
- [ ] 部署测试、正式和盒端围棋增量，保留数据与回滚版本。实际两位观众/刷新读数一致；实体大厅能在上游 WS 瞬断后恢复，确认字体截图。

范围：不新增 kiosk 观战入口，不改变段位/匹配规则，不清理磁盘或修改凭据。
