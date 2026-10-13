# 曝光标定与光照提示：独立计划审核

2026-10-12，第 1 轮（最多 2 轮），GPT-6-astra / max。

审核对象为 `docs/superpowers/plans/2026-10-12-rk-exposure-calibration.md` 的两个 chunk、`LED-ROOT-CAUSE.md`、`LED-DEBUG-DECISION.md`，并核对 camera、geometry service/API、calibrator、local worker/IPC/service/controller、相关前端类型/页面/语音及现有聚焦测试。只做静态计划审核；未修改应用、运行设备操作或部署，未将探索草稿视为通过。

**结论：需要以下三处有限修正，本轮暂不 GO。** 主方向、五步设计、现有窗口范围及发布边界成立；无需重新设计页面或扩大测试。修正计划后进行第 2 轮复核，无需再让用户笼统确认方案。

## 必须修正

### R1 · 高：标定阶段的严重曝光提示缺少可达的生产者

计划 Task 2 只接受 `frame_overexposed/frame_underexposed` 加标定 gate 证据，Task 3 只改 calibrator 的 probe。但现役 `hardware_auto_then_lock` 在严重亮/暗时可能先因无法进入 `[120,170]` 返回 `controls_effective=False`（`camera.py:464–508`）；geometry 随即抛锁定失败，根本不会调用 `LedGeometryCalibrator.calibrate()` 的曝光闸（`geometry_calibration_service.py:323–326,392–401,552–560`）。于是最需要提醒移开遮挡或更换位置的场景只会显示“曝光没有锁定”，不会出现承诺的光照弹窗/语音。

最小修正：把“锁定是否成功”与“是否有严格的新鲜严重曝光证据”分开。保留真实锁定失败、不闪灯、不持久化；在明确控制失败后，可用有界的新鲜 probe 补充独立光照证据，并明确它在 geometry 状态中的字段、样本条件及 UI 消费条件。复用现有严格阈值；不能由 `False`、AE 目标带超界或 timeout 推导过亮/过暗。控制仍 pending、帧陈旧或样本不足时，继续只报告真实曝光/取帧失败，不播放换光提示。也可采用同等小的 camera-owner 证据出口，但必须把生产路径写清。

聚焦验收：控制明确失败后，持续且足量的真实极暗/极亮新帧能产生对应提示；同样的控制失败加正常画面、以及 pending 超时加缓存帧都不能产生光照提示。原始锁定失败语义、旧 geometry 和不进入锚点循环均保留。

### R2 · 高：未确认的严重曝光必须同时阻断普通错误的提前终止

Task 3 规定同向至少 3 帧且跨度至少 1 秒，并禁止单个严重帧提交 candidate；但没有明确未满 1 秒时是否继续执行棋盘差异拒绝。现有 controller 在 3 次相同 `no_stone/multiple_stones/illegal_move` 后直接结束窗口（`local_confirmation.py:204–258`）。在默认 8fps 下，严重画面识别为空盘可在远少于 1 秒时以 `no_stone` 退出，worker 永远无法累计到 confirmed；“先处理 lighting 再做差异判断”不足以消除这条路径。

最小修正：明确有严重曝光证据但尚未 confirmed 的 observation 只继续等待，既不提交，也不累计/触发普通棋盘错误；清空该次普通错误 streak 与点标记。confirmed 则立即以精确光照 reason 结束。恢复为正常的新帧后走原有完整确认处理。worker 必须让这些真实新帧的曝光证据到达 controller，不用假棋盘或虚构 observation 代替。

聚焦验收：从第一张 severe 帧开始、模拟识别结果持续空盘的整条 worker→controller 路径，在满 1 秒前保持窗口，满条件后返回光照 reason；另测夹入普通/运动/失帧时复位，以及单帧 severe 携带 candidate 不能入谱。不要只用直接构造 `confirmed=True` 的 observation 证明此旅程。

### R3 · 中：补齐实际前端契约与单声道约束

- Task 2 文件及契约需加入 `katrain/web/ui/src/api.ts`：当前 `LocalConfirmationState.reason` 是封闭 union，不含两个新 reason（第 18–23 行）。同时明确 `geometryApi.ts` 的 `metrics.exposure` 结构；当前 `metrics?: Record<string, number | null>`（第 57 行）不能描述后端已有的 exposure 字典，更不能可靠消费 R1 的证据。不要用 `any` 或无依据的类型断言掩盖两端不一致。
- LocalConfirmGame 已有 `useVoice()` 播放开局/操作说明（第 41–47 行），而该 hook 的单声道只在各自实例内生效。光照提示复用页面现有的 `speak/stop`，或传给共享 dialog；几何页可独占自己的 hook。不得另建一个会与说明同时播放的独立实例，无需新增全局音频框架。
- 明确标定重试的 episode 规则。`geometry_revision` 在 `start()` 和失败时不变，只在成功/沿用/重定位时增加，不能充当一次标定的 ID。建议同一轮轮询只播一次，显式开始下一次标定重新允许一次提示；用页面内 attempt 身份即可。若决定同页同 revision 的重试也持续抑制，必须明确记录这是产品行为，不能称为“每次标定一次”。本地对局保留计划已规定的 game/node/reason 去重，不因 recognizing 的临时 null 或 request_id 变化重播。

## 已认可、实施时继续守住

- 三次 `grab_fresh` 不是三帧新图；按 monotonic 等待 `None→True/False`、真正 manual=1 读回、取消和独立 rollback 的方向正确。现有 camera generation 校验可复用，只有交错测试证明缺陷才局部修改 camera。
- 明确 30 秒是单次 controls 等待预算，rollback 独立计时；取帧阻塞需计入剩余预算与取消响应。已取消时不额外排入不必要的 manual 收敛，仍完成原模式恢复并保留原错误/停止阶段。
- 五步和 `stopped_phase`、所有 ACTIVE 消费点、13 个锚点计数、严格阈值与原始 warp 测量均适当。光照累积仅属于现有本地确认窗口；不增加常驻识别或全天候监控。
- LED 当前满亮度出光及 3→1 的现场证据成立；历史锁后亮度变化的物理原因仍未解释。实机不成功时保留精确失败，不把测试通过写成硬件验收通过。
- 代表 viewport、两段离线音频、聚焦验证及最终独立代码审查足够。发布时保护后来新开的棋局、数据盘备份、同目录替换、保留旧静态资源与两云分批切换的约束成立。

第 2 轮只复核 R1–R3 是否形成可执行的 producer/consumer、终止条件和 episode 契约，不追加页面重做、全语言/全状态截图、全 GPU 回归或监控基础设施。

## 第 2 轮：GO（最终计划审核）

2026-10-12，GPT-6-astra / max；复核 `524aee1ce` 中的计划修订，仅检查 R1–R3。

**GO。三组阻塞已在计划中闭合，批准按修订计划进入开发，无需第三轮计划审核或额外用户确认。**

- **R1 已解决：** 明确控制最终失败/非 manual 后保留原错误并禁止 LED，仅用控制不再 pending 后取得的 3 个不同、请求后新鲜 seq/ts 帧补充严格 gate 证据；`metrics.exposure.reason/confirmed` 与 UI 消费条件一致。正常画面、缓存及样本不足不产生光照告警。
- **R2 已解决：** controller 在元数据校验后、棋盘形状/差异/候选处理前消费曝光证据；严重但未 confirmed 时清空普通错误 streak/points 并继续等待，阻断提前 `no_stone` 拒绝与候选提交。计划已要求第一张严重帧开始的 worker→controller 聚焦验证。
- **R3 已解决：** 已列出 `api.ts` reason union、准确的 nested metrics 类型及页面共享 `speak/stop`；标定同页同 revision 同方向重试抑制重复弹窗/语音是明确的产品规则，诊断保留，成功新 revision、换方向或重新进入允许提示，不再冒充 attempt 身份。

后续按已约定顺序执行共享基础 → 前端 Fixture 与代表视觉 GO → 光照后端 → 独立最终代码审核至通过 → 合并发布及实机验收。此 GO 仅批准计划可执行性，不代表冻结草稿、尚未执行的测试或实机标定已经通过；实现细节由该计划内的聚焦验证及最终代码审核确认。本轮只追加本审核记录，未修改应用或操作设备。
