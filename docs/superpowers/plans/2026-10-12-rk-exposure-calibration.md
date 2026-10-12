# RK曝光标定与光照提示 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复曝光控制尚未完成却被提前判失败的问题；明确展示曝光标定步骤，可靠判定影响识别的严重过亮/过暗时弹窗及语音提示，并安全部署验收。

**Architecture:** 复用现有camera owner、geometry状态、worker完整后处理及本地8秒确认窗口，不新增后台常驻曝光监控。等待完成由单调时钟预算与真实controls/mode读回决定；曝光提示复用现有严格画面阈值。新增数据只描述真实阶段和本次确认窗口的新鲜帧证据，前端负责提示及一次播放。

**Tech Stack:** Python/FastAPI、OpenCV/RKNN、React/TypeScript、既有MUI Dialog与useVoice/离线mp3、pytest/Vitest、现有Playwright CLI与RK单renderer。

## 已知事实与边界

原因证据见 `docs/design/local-confirm-2026-10-12-v2/LED-ROOT-CAUSE.md`。LED满亮度真实发光，当前模式3→1真实读回及median163/clip0正常；3次缓存帧的过早失败已稳定复现。历史亮度失稳不假归因环境，不调整曝光阈值、绕过曝光锁或恢复过期绝对曝光值。

用户要求计划独立GPT-6-astra/max审核**最多2轮**，通过后才开发；最终代码审核由独立GPT-6-astra直至通过。此前未提交的等待/五步UI草稿在流程指令到达时已冻结，不能当作审核通过/已发布；执行agent须按本计划审查、补全和验证，保留已有有效RED/GREEN证据不重做无关工作。沿用当前隔离feature worktree，不改其他工作区脏文件。

此切片覆盖标定和本地实体逐手确认时的光照检查；不承诺摄像头未运行时监控光线，也不为其它对局另造全天候monitor。静止遮挡尚无法可靠区分，所以文案先要求移开遮挡，持续不合适再换位置，不能断言必为环境光。

## Chunk 1: 曝光准备成为真实且可取消的标定阶段

### Task 1: 最小共享后端基础（独立实现agent）

**Files:** `katrain/web/core/geometry_calibration_service.py`、`katrain/web/api/v1/endpoints/geometry.py`；tests `tests/test_geometry_calibration_service.py`、`tests/test_geometry_api.py`。

- [ ] 核对草稿、运行新增延迟5旧帧回归的已有RED证据；增加真实False/模式仍3/超时/等待时取消及延迟恢复的聚焦用例。取消不得进入calibrator或持久化，保留旧geometry并执行恢复。
- [ ] 将3帧等待改成条件等待：`deadline=monotonic()+30`；None继续等、False立即失败、True还需actual current_auto_exposure接近native manual1。取帧前后检查cancel，用短Event.wait避免忙循环；到期失败，不把超时当成功。rollback独立有界等待，已置位cancel不跳过恢复，恢复失败保留原失败并写warning。
- [ ] `_run` suspend后、收敛前发布 `converging_exposure`，progress.current仍0/total13；所有backend ACTIVE判据包含该阶段，维持preview节流及旧几何不可使用。
- [ ] 在failed/cancelled前、同锁记录 `stopped_phase`（原活动phase）；start/ready/operator_reuse清空。rollback不能覆盖原停止阶段。保留所有原子发布、取消边界和worker恢复行为。
- [ ] Run `CI=true .venv/bin/python -m pytest tests/test_geometry_calibration_service.py tests/test_geometry_api.py -q`，全部通过；格式与diff-check。独立spec核对后再code-quality核对，无问题方可进入下一任务。

### Task 2: 五步UI和光照提示前端（独立实现agent）

**Files:** `katrain/web/ui/src/api/geometryApi.ts`、`src/kiosk/context/GeometryContext.tsx`、`src/kiosk/pages/BaipuSessionRoute.tsx`、`src/kiosk/components/vision/GeometryCalibrationScreen.tsx`、`src/kiosk/components/game/LocalConfirmGame.tsx`、`src/kiosk/components/vision/LightingWarningDialog.tsx`（仅若共享显示确需）、`src/kiosk/hooks/useVoice.ts`；现有对应tests。音频 `katrain/sounds/voice/lighting_overexposed.mp3` / `lighting_underexposed.mp3`，来源脚本 `scripts/generate_tsumego_voice.py` 增加两条，不重生成旧音频。

- [ ] 审查五步草稿和49项测试证据，加入曝光active/失败/取消的真实语义；现有布局测试四行断言改五行，但本轮只实际跑一个1024×600代表viewport，不重拍11语种/全状态。
- [ ] 五步依次空盘、曝光收敛并锁定、四角、九星、基线；新phase是真正第2/5。优先stopped_phase标停止阶段，旧响应用曝光error兼容fallback，其余anchors规则保留。不虚构曝光百分比，13仍仅锚点。ACTIVE消费点全部包含新phase：geometryApi类型、context300ms轮询、Baipu守卫、screen。active不能继续/沿用/重开，只能取消；固定底部按钮可达，中间沿用scroll。
- [ ] manual readback失败短诊断“曝光没有锁定”，不是“光线太强”。真实 `frame_overexposed` / `frame_underexposed` 且标定exposure gate证据或确认window权威reason出现时，打开MUI弹窗；主标题“画面过亮/过暗，暂时无法可靠识别”，正文“请移开遮挡；仍有提示时，请换到光线均匀、合适的地方再试”。只有确认严重失败才提示，pending/普通timeout不触发。
- [ ] VoiceName增两项，使用现有useVoice和语音偏好；每提示episode一次自动语音，可关闭并停止。local episode按game_id+current_node_id+reason去重，recognizing临时reason=null和request_id变化不能重置，成功换节点允许新提醒；标定按本次页面geometry_revision+reason去重。弹窗不变更棋局/重启服务，关闭后可从原页面重试。
- [ ] 以隔离的短Fixture/组件真实浏览器预览核对1024×600五步和一张警告弹窗，独立Astra max视觉GO后进入当前光照backend切片；Fixture放ignored output、真实集成前删除。仅适配既有设计，不另起Artifact/大改布局。
- [ ] Run聚焦 GeometryCalibrationScreen/BaipuSessionRoute/LocalConfirmGame/新dialog tests、`npx tsc -b`及targeted eslint。生成两段mp3并检查有效音频时长/实际播放，不在RK依赖speechSynthesis。

## Chunk 2: 确认时使用真实新鲜曝光证据

### Task 3: 光照证据与确认拒绝（独立实现agent）

**Files:** `katrain/vision/ipc.py`、`katrain/vision/worker_inprocess.py`、`katrain/vision/worker.py`（仅共用路径需要时）、`katrain/vision/led_geometry_calibrator.py`、`katrain/web/core/local_confirmation.py`；tests `tests/test_vision/test_local_confirmation_window.py`、`tests/test_local_move_confirmation.py`、`tests/test_led_geometry_calibrator.py`。

- [ ] 先写聚焦RED：严重亮/暗有效持续证据拒绝且不入谱、单帧/正常/运动/失帧/迟到或重复seq复位、AE目标带轻微超界仍可正常确认、严重单帧不得被candidate抢先提交、超时不把confirmed灯光reason覆盖成普通no_stone/timeout。
- [ ] `LocalWindowObservation.exposure`为默认None可选字典，序列化向后兼容。同一fresh raw board-warp、CLAHE/average前测median/clip_frac/shadow_frac；AE off也测，复用`check_frame_exposure`严格阈值（median>=245或clip>=0.35为over，median<=20为under），不采用AE目标[120,170]作弹窗阈值。
- [ ] 在现有 `_LocalWindow` 上累计light reason、bad_frames、first_bad_camera_ts；同方向>=3个不同新帧且跨度>=1秒才confirmed。motion/失帧/controls pending/普通帧/换方向复位；计数放看得到这些原始分支的worker，不能只靠controller收到的过滤后observations假称连续。单个严重帧清candidate并不得提交，但未confirmed不弹换光提示。
- [ ] 附加 `{reason, median, clip_frac, shadow_frac, bad_frames, span_ms, confirmed}`；原token/session/camera seq/ts保护保留。controller先处理lighting evidence再做棋盘差异/候选判断，confirmed返回明确 `frame_overexposed/frame_underexposed`，无点标记、关闭窗口/恢复同方计时，不播放落子音。普通帧完整多帧投票/denial/reference后处理照常。
- [ ] 标定曝光probe过滤重复seq/ts缓存，不用三次旧图证明光照异常；拿不到充分新鲜帧则报告no_frames或等价真实取帧失败，不能语音宣称环境光不适。现有fake camera按真实协议递增元数据，增加缓存帧回归。阈值、锚点lit-dark和拟合不修改。
- [ ] Run上述三个focused pytest文件 +共享worker相关直接受影响tests；不扩GPU/全量Python。独立spec核对后code-quality核对，照明告警与已有确认行为共同通过。

### Task 4: 集成及最终独立审核

- [ ] 删除所有预览Fixture/凭据；用真实API/WS核对曝光phase→闪灯，失败stopped_phase、取消/恢复、屏幕改选/确认/一次落子音仍保持。未知或pending不能假绿，不将模拟光照测值写生产状态。
- [ ] 由独立GPT-6-astra进行最终code review，按实际问题修复并复审**直到通过**。审查重点限于等待/取消/恢复、真实帧和gate、所有phase消费者、episode语音去重及权威确认不入坏帧；先spec合规再quality。已有充分测试不重复扩张证据体系。
- [ ] 一次1024×600实际集成图核对曝光阶段和可达按钮，沿用前一步警告预览，无实质变化不重复全状态视觉审核；用户授权max代理决策。

### Task 5: 合并、发布与RK实机验收

- [ ] fetch最新develop合入feature，相关差异验证、正常推送feature/develop；在干净SmartBox工作树只更新精确vendor/katrain gitlink并推送，保留其它人的工作区变化。
- [ ] 最终源码构建full与strict SmartBox 2D，manifest边界检查；候选与rollback放RK数据盘 `/mnt/data/smartbox-deployments/`，不删除历史文件腾根盘，不把本轮扩成磁盘清理。
- [ ] 按实际现役运行时做KaTrain-only差量：源码目标同目录temp+replace避开hardlink；静态新assets先行index-last，保留旧hash资源。记录实际source覆盖范围，不声称整个板端源码统一。仅在安全空闲重启smartbox-katrain.service，用户已允许指定AI局不保留；切换前确认无后来另起在用局。
- [ ] 两云按AGENTS完整发布链执行最小web更新（不动GPU/DB/cron/admin配置），确认空闲、保存有效compose/env/volumes和旧image；无真人会话才切，home通过才ucloud，诚实记录后端实际增量版本。
- [ ] RK唯一renderer：曝光阶段真实显示、实际13点灯定位/geometry ready或准确失败原因、旧锁不被失败覆盖、UI退出/重试、实际音频资产可播。记录相机/LED/health和SHA；若仍有真实物理失败，保留证据进一步查具体原因，不以测试替代实机成功。
- [ ] 更新计划checkbox/根因/发布记录并提交推送；关闭测试browser/隧道，删除临时Fixture，交用户检查。

## 计划审核记录

- [ ] 第1轮：独立 GPT-6-astra / max，精确上下文、无历史fork，GO或具体必要修改。
- [ ] 第2轮（仅需要时）：修正后独立复核；**最多2轮**。第二轮未过则带具体未决项找用户，不继续堆审核轮数或擅自开发。
