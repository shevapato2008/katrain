# 本地对弈逐手确认实施计划

**目标：** 实体盘按确认后才识别；屏幕盘可反复改选，确认后才入谱换方；成功入谱画面更新后播放一次落子音效。

**架构：** 沿用现有 GamePage、Board、计时器、识别服务与 WebSocket 音效链路。新增本地双方面板和隔离的屏幕预选状态；后端统一拥有确认请求、回合、计时和棋谱。当前工作区已是 feature/kiosk-local-play 的独立 worktree，不再套建工作区。

**技术栈：** React/TypeScript、现有 kiosk CSS、FastAPI/Python、现有相机识别服务、Vitest/Playwright/pytest。

## 本次切片与验收

- [x] develop 同步；HTML 设计稿及 gpt-6-astra max 独立视觉审核；用户确认设计稿。
- [x] 屏幕版补充：预选可多次移动，仅一个最后落子标识；确认前不改棋局，不播放落子音效。
- [x] 前端：`src/kiosk/components/game/LocalConfirmGame.tsx` 与样式还原三栏；`src/components/Board.tsx` 新增独立预选标记；`src/kiosk/hooks/useLocalMoveConfirmation.ts` 管理预选/发送状态。
- [x] 接入：`src/kiosk/pages/GamePage.tsx` 仅在进行中的 pvp_local 使用新布局；等待方可认输，提交中锁定，终局仍走原组件。由服务端能力字段启用，旧服务端保持原流程。
- [x] 契约草案：`src/api.ts` 定义 `/api/local/confirm`，请求绑定 session/game/node/color/request_id，输入 screen/physical，动作 move/pass；响应为状态及成功/可重试结果。前端不生成真实棋局或相机结果。
- [x] 针对性前端测试：反复改选不发请求；确认只提交最后一点一次；失败保留预选；状态换局/换手清理预选；等待方认输归属；提交锁定。
- [x] 使用测试侧 HTTP/WebSocket Fixture 运行真实 kiosk GamePage，不新增生产 Demo 路由。1024×600 拍参考/实现/并排/叠加/差异，用户确认实现视觉后才进入后端阶段。
  - 真实运行时、对照图与 161 项相关测试完成，kiosk 2D 构建通过；见设计目录 `RUNTIME-REVIEW.md`。用户于 2026-10-12 明确确认实际前端，后端阶段已获授权。
- [x] 后端：在 `katrain/web/server.py`、现有 session/vision/physical orchestration 中加入最小确认流程。暂停当前钟后使用点击后的稳定帧，单手合法变化且提子拿净才接受；失败恢复本方，有限超时关闭识别。屏幕版提交选定坐标，走同一回合与幂等约束。
- [x] 覆盖真实确认边界：多子/无子/未拿净/遮挡超时、并发重复与迟到请求、计时成功/失败、虚手、终局、屏幕模式不启动识别。
- [x] 音效：复用已有服务端 sound 事件和 `useGameSession` 画面完成后播放机制；预选、失败、重复回执不响，成功一手只响一次。开局接逐手确认语音。
- [x] 集成验收：删除临时业务 Fixture；跑受影响前后端测试和 kiosk 2D 构建；代码审核并修正实际问题。
- [ ] 发布：feature/develop 已合并推送（`0b086a7c1`），SmartBox 精确引用已推送（`a4a21cde7`），完整 web 与严格 2D 产物通过；两云 web 已部署并验收（见 `RELEASE-RESULT.md`），RK3562 仍因连接阻塞未部署/验收。设备候选包已准备，详见 `RK-RELEASE.md`。

## 状态与资源约束

确认接口返回 `state.local_confirmation`（idle/recognizing、错误原因和位置）。没有确认能力的服务端不得被前端伪装成已接入。预选独立于 `state.stones`、`last_move` 和手数；真实节点变化即失效。物理模式不连续注入落子，保持采集与曝光/标定就绪，仅按确认启用识别。**必须完整复用自由对弈现有识别算法及后处理，包括参考帧消除假阳性；不另建简化的单帧算法。** 启停时验证参考帧/稳定计数/迟到检测事件处理，结果产生后关闭识别。识别暂停时间由后端结算，刷新不重开请求、不无限停钟。仅本机处理帧，不新增图像持久化或传输。

原型的 SVG 棋盘会替换为现有真实 Canvas 棋盘，保留既有棋子/木纹材质。坐标和手数显示偏好保留，移到落子说明中的显示设置，不占确认操作区域。

## 自主推进授权

2026-10-12 用户确认前端并授权继续完整实施、测试、审核、合并、推送与 RK3562 部署。用户休息期间，后续需要用户判断的方案取舍和验收决策，由独立 `gpt-6-astra / max` agent 代为决策并记录，按结论推进。
