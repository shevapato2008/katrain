# Kiosk 在线大厅 v3 实现规格审核

**Approved。未发现本轮规格缺失或超出已批准范围的阻塞项。**

2026-10-10。独立审核 `feature/admin-console` 工作区中的大厅 v3 与真实观战人数切片，以 `9f28d43d` 为基线，依据 [实施计划](../../superpowers/plans/2026-10-09-kiosk-hall-star-alignment.md)、已批准的 `index.html?surface=kiosk&view=hall` 和 [v3 设计审核](KIOSK-HALL-V3-REVIEW.md)。此前已批准的 Galaxy 页面统一、直接邀请和 kiosk 只读观战工作作为既有上下文，不重新扩大审核范围。本结论为规格符合性审核，后续代码质量与视觉审核单独进行。

- **大厅呈现与真实数据符合方案。** `LobbyPage.tsx` / `LobbyPage.css` 保留现有控制器，采用 48px 页控条、68px 操作卡、330px 标签列表、90px 棋局卡及 58px 棋友行。实际查看 games、players 的参考/实现并排、叠加及差异图；运行记录确认大厅框 `16/248/992/330`，首卡 `24/304/484/90`。中文实际字形为 LXGW WenKai，卡片具有木色 28px 识别图标、黑白棋子和执子文字。生产页面从 API 读取棋友、棋局和人数，没有设计样例数据或逐卡棋盘请求。
- **用户旅程符合方案。** `LobbyPage.tsx:17`、`:197`、`:254` 实现具名弹窗、焦点循环/恢复、Escape 取消匹配、标签方向键/Home/End、邀请卡切换并聚焦名单、同段位筛选、本人/忙碌禁邀及一次确认发送。只有快速匹配需要定级；未定级可邀请其他段位。自己的棋局回原房间，他人的棋局进入原生只读观战。列表按账号作用域展示并取消/忽略过期请求，重连、邀请接收、错误重试继续可用。错误截图及运行记录显示列表随告警缩短，未溢出 1024×600。
- **真实人数契约完整落地。** `pvp_spectator_presence.py:8` 按正整数认证用户 ID 合并 HTTP 与存活 WebSocket，去重并排除双方棋手；HTTP 使用单调时钟和 10 秒 TTL。`pvp_spectator.py:56` 在公共房间授权和权威状态读取成功后登记 HTTP 观看；未授权、私有房间及读取失败路径不登记。`session.py:249` 实现入场变化推送、单个可取消的最近到期回调、安静房间到期推送及会话删除/替换/关闭清理，回调不读取引擎状态、不刷新会话存活时间。`server.py:4148` 的 WS 登记和 `finally` 清理保持对应。
- **兼容与中央权威符合方案。** `games.py:28`、`pvp_spectator.py:27` 在严格盒子模式转发中央结果，桥接不可用时不退回本地统计。原 `sockets_count` 与事件 `count` 仍表示 socket 数；新增 `spectator_count` 经初始状态、状态更新、人数事件和 HTTP 快照传播。`api.ts:1`、两处会话 hook、`GameRoomPage.tsx:200`、`PvpSpectatorPage.tsx:138`、`LobbyPage.tsx:276` 使用有效非负整数，无值或非法值显示“观战人数未返回”。未修改外部 Golaxy 房间契约、动作权限、升降级或机器人调度。

核对了 `test_pvp_spectator_presence.py`、`test_pvp_spectator.py`、大厅与观战页面测试、房间及两处 hook 的增量测试，覆盖身份去重、双方排除、单调 TTL、HTTP 加入/静默到期推送、生命周期、中央转发及上述交互。实际浏览器证据见 [运行检查记录](kiosk-hall-v3-runtime-checks.json)。本审查直接执行的 `git diff --check` 通过；聚焦测试与构建的实际执行结果由主任务统一归档，未重复运行全量检查。

人数保留已批准的时间语义：HTTP 观众停止心跳后最多约 10 秒过期，大厅在下一次列表刷新反映；不宣称瞬时离开检测。本结论不代表生产发布或部署完成。
