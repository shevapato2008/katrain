# 开局前标定：Task 1 独立前端审核

2026-10-12，独立前端审核与用户视觉代理。审核基线 `4c91118d5`，首轮实现 `15dcda990165d4630092c374cb2ada7837211119`，最终复审提交 `fd0f2087cb944126c1e361d61cc817ff9c07ecfc`。依据 [实施计划](../../superpowers/plans/2026-10-12-local-calibration-before-start.md)、[已通过的计划审核](PRESTART-PLAN-REVIEW.md) 与 [既有设计](DESIGN.md)。本审核不操作浏览器、设备或生产服务，不修改产品代码。

**最终结论：规格 GO、代码质量 GO、视觉 GO。首轮 F1 已关闭，Task 1 通过，允许进入 Task 2。** 这是前端切片与视觉确认，不代表尚未实现的后端预检、设备计时暂停或生产发布已验收；本次代码复审不增加正式计划审核轮次。

## 规格审核：GO

首轮在 `15dcda990` 发现以下真实集成时序问题，给出 NOT GO 后已完成最小修复：

**F1：成功绑定后的旧 pose 状态会再次锁存恢复提示。** `GamePage.tsx:418-430` 仅在 `retryBind()` 之前刷新视觉状态；真实 bind 成功且原局 GET state 已返回后直接清除 `localRecovery.required`。如果绑定前的 `visionStatus.poseLocked` 仍为 false，紧接着的 render 会经 `needsRecovery`（403-405）重新把 required 置为 true；随后普通轮询获得 true 也不会清除该 latch，用户需要再次点击才能离开恢复界面。

这不是假设中的非法状态：`worker_inprocess.py:423-426` 在几何变更时把本地 bootstrap 置为 unavailable，`1638-1649` 仅在真实 reference ready 后确认 pose。首轮临时 Fixture 的 `/vision/status` 直接把 geometry ready 映射为 pose locked，提前消除了这段真实时序。

**F1 复审：已关闭。** `fd0f2087c` 使两个 context 的 refresh 返回实际快照；真实 bind 与原局 GET state 成功后，再读取视觉和几何状态，检查原 session/game/revision、boundSessionId、camera、pose、geometry、model 与 recognition 就绪，才更新权威原局并清除恢复 latch。读取失败或状态未就绪仍保持封锁。新增回归覆盖“绑定前 pose=false、绑定后才 ready、无需第二次点击”。`VisionContext.tsx` 的返回类型和返回值扩展由本用户代理明确批准，属于 F1 必要范围；没有扩大到后端或轮询基础设施。ignored Fixture 也已拆开 geometry ready 与 bind 后的 pose ready。

其它规格已核对：

- 实体 19 路 preflight 先于 createSession、gameSetup、活动局写入和导航；pending 防重入，失败保留设置；离页使旧请求失效，仅清理本次新建而未发布的会话。
- required/degraded/failed/cancelled 展示既有标定组件，设置组件保持挂载；完成后回到设置，重新点击才开局。未知设备状态保留实体意图；明确屏幕选择、实际无视觉设备和非 19 路沿用原逻辑。
- 仅移除本地 game route 的外层输入守卫；其它业务路由的 guard 未改。原 GamePage、会话 hook 和棋谱在标定覆盖期间保持挂载，刷新已有局使用当前几何状态，提供外框对齐、空盘标定、重新检查和原退出流程。
- 恢复调用真实 `retryBind()` 并读取原 session 的权威 GET state；旧 session/game/revision 结果被拒绝，普通轮询不会自动重复绑定。正常新局首轮 pose=false 的准备态没有直接锁存为恢复失败。
- 本次没有伪造 `timer.paused`，时钟仍消费服务端快照；后端暂停和 preflight 为 Task 2 已批准契约，尚未实现不计为 Task 1 缺陷。屏幕选点、逐手确认和落子声音链路未改。

## 代码质量审核：GO

F1 修复后没有剩余阻塞。改动复用已有 API/context、标定页面、原局绑定与对话框，没有新增业务模拟数据、识别管线或页面级基础设施；临时网络 Fixture 位于 ignored output，未被 git 跟踪。

本审核独立执行了以下聚焦检查：

- `git diff --check 4c91118d5..fd0f2087c`：通过。
- `npx vitest run src/kiosk/pages/GamePage.test.tsx -t 'one recovery click finishes'`：1 PASS、89 skipped、exit 0。执行的是 F1 候选；随后核对稳定提交的产品与测试内容一致，产品工作树干净。
- 阅读完整产品差异、相关测试和真实 worker/bind 边界；核对其它业务 guard、屏幕确认及声音代码未改。

root/实现者提供的验证为：首轮 8 文件 143 PASS，退出可达小修后 2 文件 97 PASS；F1 新回归先 RED、修复后 GREEN，最终 4 文件 102 PASS、`tsc -b` exit 0、source eslint 0 errors / 7 条既有 hooks warning、diff check 通过。原 GamePage test probe 的 1 条 render 写 globals lint error 为已知基线。本审核没有把这些结果冒称为独立重复执行，也未扩大到无关回归。

## 视觉审核：GO

root 唯一控制 Mac Chrome 的真实前端运行时，viewport 为 1024×600，本审核独立查看参考、实现、同尺寸并排、叠加及差异图后作出用户代理视觉确认。复用既有设计系统，按 ui-ux-pro-max 核对布局、层级、触控、文案和状态；没有重新设计页面。

| 代表旅程 / 对比 | 核对结果与可接受差异 |
| --- | --- |
| 设置 → 标定 → 返回设置 | 顶栏、左盘/右设置栏、字体、木纹、图标与玉绿主操作沿用原界面；姓名「小明 / 小红」、日本规则、60分+3×30秒保留。设置页不自动开局。`setup-before.png` 含姓名输入时的键盘；完整布局以 `setup-restored.png` 核对，不为键盘状态追加重拍。 |
| 既有标定参考 → 开局前标定 | 并排与叠加图中的相机容器、右侧硬件状态、五步列表及底部操作几何对齐。返回改为「返回设置」，标题说明先处理标定再开局；参考的已完成状态与本次未标定状态、单/双操作按钮差异符合阶段语义。相机照片与 SVG 替身的画面差异不用于评价识别。 |
| 既有本地对局 → 原局恢复 / 恢复后 | 中央棋盘、双侧玩家卡、显示键、业务键和确认键位置对齐；恢复提示作为既有侧边 Dialog 覆盖，未重新排布或清空棋盘。四个操作完整可见、分行合理，新增操作最小高度 44px；琥珀色突出「对齐外框」，明确有子可用、不亮灯，以及空盘流程须取子后摆回。恢复后仍为同 session、3 手、3 子，原姓名保留。名字、落点、时钟、按钮可用性和确认键文案差异均对应 Fixture 与输入状态，没有非预期构图变化。 |

已检查的证据位于 `output/rk-local-prestart/`：`setup-before.png`、`setup-calibration.png`、`setup-restored.png`、`game-recovery.png`、`game-restored.png`、`preview-receipt.json`，以及 `visual-compare/` 下 calibration、game、recovery 三组 `side-by-side` / `overlay` / `difference`。参考为 `output/rk-exposure-release/rk-calibration-ready.png`、`rk-screen-confirmed.png` 和本目录 `DESIGN.md`。

运行时收据记录：标定前没有 create，标定后不自动 create；恢复没有创建新会话，URL 与绑定目标均为 `demo-original`，3 手 / 3 子不变，两旅程 page errors 均为空。截图中的计时字段属于隔离网络 Fixture；本次没有据此宣称真实相机、reference 识别、后端暂停或 RK 设备验收通过。F1 不改变视觉布局，无需因这次状态同步修复重做视觉矩阵。

另已独立读取 root 在修正 Fixture 上取得的 `f1-preview-receipt.json` 与 `game-f1-restored.png`：几何 ready、pose 尚未 ready 的起点，经一次「重新检查」后 bind 仅增加 1 次，原 URL、3 手、3 子保持，create 为 0、confirmation reason 清除、恢复 Dialog 消失、page errors 为空。这份真实 Chrome 前端运行时证据与独立聚焦测试共同支持 F1 关闭；Fixture 的 timerPaused=false 仍仅是模拟服务端快照。
