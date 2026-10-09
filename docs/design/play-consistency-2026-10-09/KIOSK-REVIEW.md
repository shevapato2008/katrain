# kiosk 独立规格、代码与视觉审核

**Spec compliance：Approved。Code + visual：Approved。Ready to merge：Yes（本报告范围）。**

审核日期：2026-10-09。基线：`9f28d43d`，对象为当前未提交差异。先按已批准计划 Chunk 4 与用户最新裁定完成规格审核，再依 `requesting-code-review` 模板检查代码和真实截图。未修改生产代码、提交或部署；Galaxy 已单独审核，本报告不重复审核。

## 范围与规格结果

- 保留 RK3562 原大厅布局，仅修正字体栈、他人对局卡的观战入口及对应说明。未应用已撤回的 kiosk 重排。
- 他人棋局进入 `/kiosk/play/pvp/watch/:sessionId`，传递中央房间 ID；自己的棋局保留原 room 路径。
- 新 `PvpSpectatorPage.tsx` 使用现有 `KioskPagebar`、`GoBoardSvg` 与 `golaxy-spectator.css`。显示真实棋盘、双方姓名/段位、手数和状态；没有历史、分析、下棋或实体盘操作。
- 未定级可直接邀请任意段位空闲棋友，包括机器人；只有快速匹配要求定级。现有在线、忙碌、席位预留与失败回滚继续生效。
- 新只读 GET 使用既有云桥和 viewer/state 读取闭包，不创建参与者镜像；串行轮询、隐藏暂停、作用域隔离、错误重试、终局/404 与结算状态均实现。

**规格审核结果已先行报告：Approved。**

## Strengths / 代码检查

- `api/pvp_spectator.py:22` 要求登录并先验证安全 session ID。中央只接受 `free/pvp_lobby` 且双方席位均为严格整数的大厅会话，再调用既有 `guard_session_viewer` 与 `session_state_for_read`；私有单人局、升降级局及跨平台局不由本端点公开。
- `api/pvp_spectator.py:27` 在严格盒子模式只经 `PvpBoxBridge.request` 读取中央同一路径。现有桥在请求前后核对 generation、活跃本地用户和云凭证归属；返回内容再次核对中央 ID、公开标记与 state。401、404、503 有独立路径，云凭证没有进入响应或浏览器 URL。
- 姓名/段位沿用现有 active multiplayer 的用户、公开机器人名单与段位来源。接口只注册 GET，页面只发 GET；没有本地会话查找/创建、镜像建立、落子、计时回调或 vision/LED/engine 动作。
- 前端房间、用户、token、认证态共同限定已显示数据与请求。取消加序号校验阻止旧响应写回；轮询在当前读取完成后延迟 2 秒，离开或隐藏时取消。错误明确标记上次同步盘面并提供重试，已取得终局可在后续 404 时保留。
- 坐标使用现有 core/GTP 转换，未额外翻转纵轴。`awaiting_count` 优先显示“结算中”，结算及终局不显示“轮到落子”或当前执子高亮。
- 实际路由位于 `KioskAuthGuard` 内且未进入 `PlayInputGuard`；对应测试直接挂载 `KioskRoutes` 验证了这一边界。

## Issues

### Critical（必须修复）

无。

### Important（应在交付前修复）

无。

### Minor（可选）

无需要单独追踪的本次问题。

## 视觉核对（1024×600）

实际查看了大厅与观战的 reference/implementation 并排图、overlay 和 diff，没有只依靠 CSS 或自动化几何断言。

| 页面 | 观察结果 |
| --- | --- |
| 大厅 | 顶栏、返回、标题、快速匹配/邀请棋友卡、双栏与列表高度保持原构图。标题/快速匹配/邀请棋友/元数据中文已呈现楷体；字宽变化与不同列表滚动条产生少量文字及行内对齐差异，未造成布局重排或主操作裁切。人数、手数、时钟和观战说明为预期内容差异。 |
| 只读观战 | 木纹棋盘、坐标、棋子、页控条、474px 左栏及右侧面板与星阵参考骨架一致。棋盘区域两者均为 `x=16, y=114, width=474, height=472`。右侧将缺失的时钟/成员/历史控制替换为真实姓名段位、对局状态和只读说明，符合本期范围。返回大厅清晰可达，未看到裁切或重叠。 |

证据文件：`rk3562-hall-reference.png`、`kiosk-hall-implementation.png`、`kiosk-hall-{side-by-side,overlay,diff}.png`、`kiosk-golaxy-spectator-reference.png`、`kiosk-spectator-implementation.png`、`kiosk-spectator-{side-by-side,overlay,diff}.png`。

`kiosk-runtime-checks.json` 的 CDP 实际字形证据确认：大厅标题、快速匹配、元数据中文及观战中文标题/姓名均为 LXGW WenKai Regular/Bold。kiosk 原有拉丁/数字字体保留，中文通过完整共享栈回退到楷体。该记录还验证未定级邀请发出 `invite`、快速匹配显示定级指引、中央 ID 观战跳转及返回大厅；没有记录运行时错误。

## 验证与 Assessment

- 主任务提供的最新聚焦结果：pytest **48/48**（新增观战 17 + 大厅边界 31）；kiosk Vitest **29/29**（LobbyPage + PvpSpectatorPage，包含真实路由守卫与结算断言），随后受影响前端 6 文件合跑 **111/111**；TypeScript 通过。独立检查了相关测试与生产代码边界，未重复全量测试。
- 主任务最终 `build:smartbox-kiosk-2d` 通过，包含严格 SSO 与不引入 Galaxy/three/live 的边界检查；完整前端构建亦通过。
- 审核期间执行 `git diff --check`，通过。
- **当前 kiosk 改动可以继续集成，没有阻塞交付的问题。** 此结论是实现、局部运行预览及边界检查通过，不代表已部署或已完成实体 RK3562 发布验收。旧 `REVIEW.md` 的 kiosk 重排结论仍作废。
