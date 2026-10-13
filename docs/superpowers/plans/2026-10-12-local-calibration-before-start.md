# 本地对弈先检查标定再开局 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实体本地对弈在开始前核验当前几何；未就绪先处理标定并保留设置，已开始的原局不因几何失效被悄悄换成空盘标定页。

**Architecture:** 增加一次有界、无灯、不写盘的后端 preflight，复用原漂移参考与阈值。设置页通过它后才建局；本地 GamePage 始终保留原 session，几何失效由权威计时暂停和原页恢复提示承接。重新标定仍使用既有五步页面，外框对齐与真实 bind 验证后才恢复。

**Tech Stack:** 现有 Python/FastAPI、GeometryDriftMonitor/MotionFilter、React/TypeScript、MUI、pytest/Vitest、1024×600 kiosk 与 RK 唯一 renderer。

## 原因、授权与范围

- RK 18:53:37 建本地局，18:53:54 首手 Q16 识别，18:53:55 入谱；18:53:58 `reference dropped: geometry` 且 GamePage 的视觉 WS 卸载；用户随后手动标定成功。服务 PID 53278 全程未重启。只证明开局后几何被改变/判失效，不能断言真实移动或误判。
- `PvpLocalSetupPage.handleStart` 没有几何检查；只在对局路由套 `PlayInputGuard/PhysicalBoardGuard`。该守卫每次非 ready 都卸载子页面。`_drift_loop` 空闲暂停，开始识别后才恢复，所以缓存 ready 和一次 status refresh 不能证明目前位置有效。
- 用户明确要求标定放在开局前；已授权独立 GPT-6-astra max 替其决策，固有流程是计划审核最多两轮、subagent-driven 实现、最终独立代码审核至 GO。独立诊断已推荐本计划边界，诊断不计正式计划审核轮次。
- 沿用干净的隔离 feature worktree，不改其他工作区。只改本地人人对弈；屏幕局、其它业务的 PhysicalBoardGuard、漂移阈值、自动重定位开关及完整识别链保持原有契约。
- 当前 RK 用户局 `e79e1414c8d14cf88d1502a6cecebaa2` 已有三手，先做离线实现，不导航、不解绑、不闪灯、不重启。切换设备前重新核对在用局与用户切换时机，保留已保存棋谱/报告。
- 复用既有 DESIGN.md、设置页、五步标定与 MUI 恢复对话框，按 ui-ux-pro-max 核对触控/加载/返回，不做视觉重构。max 代理承担用户视觉确认。

## 最小契约

`POST /api/v1/geometry/preflight` 在 worker thread 中执行，返回 `{ready: boolean, reason?: string, status: GeometryStatus}`。status 的 camera/model/recognition capability 与现有 status endpoint 同口径。phase required/degraded/failed/cancelled 或缺已确认锁/原 monitor 返回需要处理，不能以 disabled 放行实体开局。busy 可 409，未知异常不假绿。

`ready=true` 必须满足：原锁、revision 和原 monitor 未变；摄像头可用；本次开始后 seq/ts 严格递增的新鲜帧；MotionFilter 第一张建比较基线不计证据；至少三张连续稳定、相关性可信且未漂移的画面。采样预算最多 8 秒，用短等待；运动、旧/重复帧、掉线、低相关性、超时或 stale identity 不能通过，也不能仅因此写 board_moved。复用既有 0.10 cell / 3 frame / correlation 判据，不用当前第一张图覆盖原参考。确认连续漂移才调用原降级路径；正常成功不点灯、不持久化、不增加 revision、不运行 13 点。

preflight 与 calibration/confirm-existing/relocate 有限互斥，monitor 更新串行化；旧结果不覆盖新 revision。空闲仍不后台取图。新增一条真实降级日志（来源/revision/shift/response/seq/ts）；不为日志造新证据系统。

本地实体局新增最小后端 `local_geometry_paused` 原因，默认/新局 false；失效或人工标定 suspend 时仅对当前绑定的实体本地局设 true。timer.paused、update_timer、clock_exhausted 和物理提交认它；用户原 timer_paused 不被覆盖。只有原局真实 reference/bind ready 校验成功后清除，不靠 geometry ready 或前端文案恢复。屏幕局与其它模式不受影响。

## Chunk 1: 前端旅程与同尺寸预览

### Task 1: 前置检查和原局恢复界面（独立实现 agent）

**Modify:** `katrain/web/ui/src/api/geometryApi.ts`、`src/kiosk/context/GeometryContext.tsx`、`src/kiosk/pages/PvpLocalSetupPage.tsx`、`src/kiosk/KioskApp.tsx`、`src/kiosk/pages/GamePage.tsx`、`src/kiosk/components/game/RecalibrationModal.tsx`、`src/kiosk/hooks/useVisionSync.ts`（只有原 session 恢复确需时）。
**Test:** 现有 `PvpLocalSetupPage.test.tsx`、`GamePage.test.tsx`、`RecalibrationModal.test.tsx`、对应 guard/rebind tests。

- [ ] 写 RED：实体开始必须先 preflight；required/stale/失败/请求未完成不能 create/gameSetup/writeActive/navigate，设置仍在；屏幕与非19路不调 preflight；位置有效才建一次局；返回/离页后旧 Promise 不开局。不得用现有“vision.enabled=true 就等于已标定”的 fake 掩盖失败。
- [ ] 增加 typed API 与 context 更新。设置页 pending 显示“检查棋盘…”且防双击；返回的需要标定状态展示既有 GeometryCalibrationScreen，PvpLocalSetupPage 本体不卸载，姓名/规则/用时仍保留。标定后返回设置再开始，不自动建局。运动/暂不确定显示短诊断可重试，不宣称光照或必定移动。
- [ ] 本地 game route 不再由外层守卫自动卸载 GamePage；其它路由不改。读取当前几何状态阻止确认/停一手。原页恢复提示保留真实棋谱，可主动“对齐外框”（不亮灯、有子可用），或主动进入既有标定页并明确会要求清盘；失败不换局、不清 SGF。刷新已有局也须保留 session，不能依赖曾经ready的永久 latch。
- [ ] geometry revision/原局恢复操作成功后，对原 session 执行现有真实 bind/bootstrap；完成前保持不可确认。明确重新标定由用户主动触发，在原 GamePage 内展示/覆盖标定组件而不卸载原会话，保留完整返回路径和原局身份。绑定按现有 SGF 验证盘面；已有棋子不被当空盘。
- [ ] 使用 ignored output 临时网络 Fixture，在1024×600预览两个关键状态：未标定的设置→标定→返回、已有三手的几何失效提示。与既有设置/对局参考同尺寸对比；独立 max 视觉 GO 后进入对应后端任务，Fixture 不进入产品。
- [ ] 聚焦 Vitest、tsc/相关 eslint 通过。按 spec 再 quality 审核，不新建全状态图矩阵。提交仅本任务文件。

## Chunk 2: 后端权威检查和计时暂停

### Task 2: 真 preflight 与原局暂停（新的独立实现 agent）

**Modify:** `katrain/web/core/geometry_calibration_service.py`、`katrain/vision/geometry_drift.py`（必要的 monitor 复用/串行接口）、`katrain/web/api/v1/endpoints/geometry.py`、`katrain/web/server.py`（失效/suspend 回调）、`katrain/web/interface.py`、`katrain/web/core/local_confirmation.py`。
**Test:** `tests/test_geometry_calibration_service.py`、`tests/test_geometry_api.py`、`tests/test_local_play_timeout.py`、`tests/test_local_move_confirmation.py`。

- [ ] 写 RED：闲时原 ready/原 monitor 下真实位置变化在 preflight 就被拦；正常稳定通过且没有灯/写盘/revision变化；运动、旧/重复帧、低相关性/掉线、不足证据及并发取锁不通过、不假写移动；第一帧不计稳定证据，正常与坏帧不能拼接累计。既有 idle 不取图测试保留。
- [ ] 最小实现上述契约和 endpoint，blocking OpenCV 在 asyncio.to_thread。核对锁顺序，不在 status 锁内等待或运行重计算；有限互斥覆盖 monitor.update，输出前复核 lock/revision/monitor。仅足够漂移证据走原 _apply_drift，保留 auto_relocate 默认关闭。
- [ ] 写 RED：已入谱实体本地局几何失效、标定 suspend 时计时停且不判超时，confirmed SGF/node 不变；geometry恢复但 reference未ready不能恢复；原局physical ready成功才解除几何暂停；玩家手动暂停、屏幕局、新局重置与确认窗口各自独立。
- [ ] 加最小暂停字段及权威边界，给实际绑定的正确 session/game 设值与广播；不调用 toggle、不冒充确认进行中、不给其它会话暂停。确认/停一手/超时直接路径不能绕过暂停，参考验证仍是现有完整算法。
- [ ] 跑上述四文件及直接受影响 timer/worker 聚焦用例，spec→quality GO。提交仅本任务文件。

## Chunk 3: 集成、发布和交付

### Task 3: 聚焦验收及正式发布（root）

- [ ] 删除临时 Fixture，真实 API/WS 验证设置预检、保存配置、原局身份和恢复动作。一次正常开局不运行13点或点灯；未就绪不显示对局已开始/不播落子引导，屏幕确认与一次落子音保持。
- [ ] 独立 GPT-6-astra max 最终 code review（先 spec，再质量）直至 GO。真实1024×600两状态复核，无实质视觉变化不重复大范围审核。
- [ ] fetch 最新 develop 合入 feature、验证并推送；FF 合入 develop 推送；干净 SmartBox release worktree 更新精确 vendor/katrain 指针，保留原工作树脏文件。
- [ ] 构建 full 与 strict2D；按现役基线做最小 web 增量，home passed 后 ucloud，保留 env/volume/GPU/DB/其它容器。RK 候选与回滚备份放数据盘，源码 temp+replace、assets-first/index-last。
- [ ] 切换前核对当前用户局；仅用户同意切换或已结束且确认保存才重启 KaTrain。实机重点验收：未标定在设置环节处理、配置保留、正常通过不闪13点；原局异常提示保留棋谱，恢复后同 session 可继续。禁止为了验收损坏用户当前标定/棋局，可用独立空闲验收局。
- [ ] 更新审核/根因/发布记录；只退出本轮测试局、不保存测试谱，删除临时 Fixture、detach native browser 并停本轮隧道；交用户检查。

## 审核计数

- [x] 正式计划第1轮：独立 GPT-6-astra max，GO，无阻塞项；见 `docs/design/local-confirm-2026-10-12-v2/PRESTART-PLAN-REVIEW.md`。
- [x] 第1轮已通过，无需第2轮；最多两轮，不用诊断/代码审核冒充计划额外轮次。
