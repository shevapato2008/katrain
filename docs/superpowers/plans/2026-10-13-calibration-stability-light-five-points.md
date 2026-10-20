# 棋盘标定：稳定启动、光线恢复与五点定位 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 用户按“开始标定”后，手离开且棋盘稳定才亮第一盏灯；遮挡或异常光线时熄灯暂停并保留已定位点；正常标定用四角加天元共五点，页面与语音诚实反映状态。

**Architecture:** 后端标定线程拥有暂停、恢复、曝光重检和五点结果；`/geometry/status` 是前端唯一状态来源。复用 `MotionFilter.is_stable_with_regions`，对 RK3562 实际浅色棋盘建立网格可见性判据，防止静止的手蒙混过关；现有暖木色外框检测器只能作可选证据。标定亮灭帧要求 V4L2 手动曝光；标定线程结束时由设备现有 `resume_vision` 将相机交还硬件 AE，识别 worker 的硬件 AE 稳定闸控制识别暂停与恢复。前端沿用现有标定屏、按钮、`SmartBox Kai` 字体和 `useVoice` 设置；只增加必要的提示状态。

**Tech Stack:** Python/OpenCV/FastAPI；React/TypeScript/Vitest；RK3562 + V4L2 摄像头 + LED；1024×600 kiosk。

---

## 已确认的事实与边界

- 已确认的视觉基准：[交互稿](../../design/2026-10-13-calibration-flow/index.html)。用户要求实际页面中文使用霞鹜楷体，不再修改交互稿。现有 `katrain/web/ui/src/kiosk-shell/fonts.css` 已载入霞鹜文楷分片，`tokens.css` 的中文回退族为 `SmartBox Kai`；实际页面复用此族，不添加字体包。
- 现有 `MotionFilter.is_stable_with_regions` 在 `katrain/vision/motion_filter.py`；首帧返回稳定，所以必须累计连续稳定采样，不能见到一次 `True` 就点灯。`build_motion_roi_mask` 在 `katrain/vision/motion_roi.py`。
- 现有算法在 `katrain/vision/led_geometry_calibrator.py` 采 13 点，`MIN_LOCATED_ANCHORS=9`。直接截成五点会必然失败；四角恰好可拟合任意单应，必须让天元作为独立误差校验，不能用五点拟合后只看训练残差。
- RK3562 2026-10-13 15:55 一轮实测：曝光闸 `median=176, clip=0` 判通过，首点亮斑面积 `12211`（正常记录多为几十到几百），后来 7 点 ROI 回退。现有光线闸只挡极端整帧过曝/欠曝，且失败才出结果；它不能支撑用户期望的实时提示。该日志提示亮斑异常，但**不能仅凭面积断言是手还是眩光**，上板时须对照原始画面。
- 设备 `/geometry/status` 的失败轮显示首四角三点落在画面底部附近，与 2026-10-13 实拍空盘的四角几何明显不符；这是后续 ROI 偏移和 `not_enough_inliers` 的直接原因。五点方案必须在接受每个角点前检查它与板面网格的位置关系，不能只靠亮斑强度和四角彼此的非退化性。
- 从 RK3562 原始流取出的当前浅色空盘帧（1920×1080）上，`geometry_detect.detect_board_raw` 返回 `None`；该检测器的 HSV 暖木色前提不适用于此盘。稳定闸不得把它当作唯一外框来源，否则首灯永远等不到。优先用当前有效锁作为 ROI 候选并核验网格是否仍对齐；首次标定或旧锁不可信时，要用与盘色无关的线网/轮廓证据建立 ROI，并以实机手遮样本验证。
- 当前围棋引导语由 `useVoice.ts` 播放 `katrain/sounds/voice/*.mp3`，统一受 `audioPrefs.ts` 的 `voice` 开关控制；`scripts/generate_tsumego_voice.py` 使用 `zh-CN-XiaoxiaoNeural`。设计稿的浏览器朗读已移除。新语音必须沿用这条音频与设置链路。
- 页面运行中现有动作区只有一颗“取消标定”，保留；`ready`/`failed`/`cancelled` 的现有动作不重设计。`GeometryCalibrationScreen` 同时用于设置入口与实体盘守卫，两条入口均须验收。

## 文件责任与契约

| 文件 | 本轮责任 |
|---|---|
| `katrain/vision/led_geometry_calibrator.py` | 五点顺序、中心独立校验、每点开始前/采集中稳定性与光线检查、暂停后重试当前点 |
| `katrain/vision/calibration_stability.py`（新增） | 小尺寸帧上的连续稳定判定；复用 `MotionFilter` 和棋盘 ROI，不藏 LED/HTTP 状态 |
| `katrain/web/core/geometry_calibration_service.py` | 标定线程的暂停条件、取消唤醒、曝光重检、状态/进度、成功或失败时的曝光恢复 |
| `katrain/web/api/v1/endpoints/geometry.py`、`katrain/web/ui/src/api/geometryApi.ts` | `status` 的暂停原因与 `POST /recheck-lighting` 契约 |
| `katrain/web/ui/src/kiosk/context/GeometryContext.tsx`、`GeometryCalibrationScreen.tsx`、`BaipuSessionRoute.tsx`、`VisionSetupPage.tsx`、`katrain/web/ui/src/kiosk-shell/go-screens.css`、中文 `.po` | 等待移手、标定中、遮挡暂停、光线弹窗与按钮；原始画面保持实时流；两条入口与文案一致 |
| `katrain/web/ui/src/kiosk/hooks/useVoice.ts`、`scripts/generate_tsumego_voice.py`、`katrain/sounds/voice/` | 新提示 ID、同音色 MP3、同一个语音开关，不增加第二套播放器/设置 |

`status.phase` 新增 `waiting_stable`（有移动但遮挡未证实）、`obstructed`（棋盘网格可见性不足）、`lighting_paused`、`lighting_rechecking`；`pause_reason` 为 `board_motion | board_occluded | frame_overexposed | frame_underexposed | null`。`progress.total=5`、`progress.current` 是已经确认的点数；`detected_anchors` 仍是已锁定点的权威列表。取消、失败和暂停均不发布半成品几何锁。暂停时 LED 必须全灭。`POST /recheck-lighting` 只在光线暂停态有效，其他状态回 409；请求把 phase 置为 `lighting_rechecking`，前端直到后端返回新状态才允许再按，取消可随时唤醒等待线程。进入 `obstructed` 才说“检测到遮挡”，纯移动只说“画面不稳定”。

正常路径：点击 → 提示移手 → 先让硬件 AE 在不点灯的情况下尝试恢复可见亮度 → 棋盘 ROI 连续稳定、外框和网格可见 → 在无遮挡空盘上再次收敛并锁曝光 → 重置稳定计数并再次检查 → 逐个采四角和天元 → 天元独立校验 → 稳定后拍空盘基线 → 发布锁 → 设备硬件 AE 接管实时画面，worker 稳定闸控制识别恢复。首次 AE 必须早于网格等待：2026-10-13 17:50 实机暗帧整帧中位 23 时网格检测返回 None，先等待网格会误报遮挡。遮挡路径在任何未完成点或基线阶段熄灯、保留 `detected_anchors`、稳定后重试当前采集。光线路径熄灯、展示过亮/过暗和调整建议、等待“调整后重新检测”、重新收敛并验证后重试该点；不足以定性原因时显示普通“画面不稳定”，不误报光线。

## Chunk 1：真实前端状态与视觉确认

### Task 1：临时状态 Fixture 与实际页面

**Files:** Modify `GeometryCalibrationScreen.tsx`, `go-screens.css`, `GeometryCalibrationScreen.test.tsx`；临时 Fixture 仅放 `katrain/web/ui/tests/fixtures/`，集成后删除。

- [x] 先加组件测试：`waiting_empty` 显示移手提示；`obstructed` 显示“已暂停”、已定位点保留；`lighting_paused` 按原因显示过亮/过暗弹窗；所有运行态动作区仍只有“取消标定”；五点是一行步骤，不分“四角/天元”两行。
- [x] 运行聚焦 Vitest，确认新增断言先失败（10 项）；实现后 54 项通过。
- [x] 用临时 Fixture 渲染四个关键状态；四步为“等待棋盘稳定 / 确认并锁定曝光 / 定位棋盘 / 生成空盘基线”，第三步仅说“五个灯依次点亮”。中文使用现有 `var(--font-serif)` / `SmartBox Kai`，不拷贝设计稿的 `PingFang SC`。
- [ ] 在 1024×600 真运行时截取等待、遮挡和亮/暗弹窗；与已确认参考图同尺寸看并排与叠加差异，重点核对文字、按钮、画面空间和对话框。实际截图已生成，待用户确认后进入后端切片；Fixture 删除条件为真实 `/geometry/status` 已驱动全部状态。

### Task 2：状态契约在前端落位

**Files:** Modify `geometryApi.ts`, `GeometryContext.tsx`, `GeometryCalibrationScreen.tsx`, `katrain/web/ui/src/kiosk/pages/BaipuSessionRoute.tsx`；Test `GeometryCalibrationScreen.test.tsx`, `katrain/web/ui/src/kiosk/__tests__/BaipuSessionRoute.test.tsx`。

- [x] 为四种新增 phase 和 `pause_reason` 加 TypeScript 类型；`GeometryContext` 与 `BaipuSessionRoute` 的运行态集合同时更新，防止标定暂停时摆谱页挂载并抢 LED。保留 `detected_anchors` 作为进度真值，无状态时不编造 `5/5`。
- [x] 增加 `GeometryAPI.recheckLighting()` 和 Context 动作；弹窗内同时保留“取消标定”（调用现有 cancel）和“调整后重新检测”。重检相位禁止重复按；请求错误在弹窗提示。
- [x] 把新 phase 加入 Context 轮询活动态；画面仍来自原始 MJPEG 流，不截停、不放旧帧。
- [ ] 聚焦组件测试和 `npm run build:kiosk-2d` 已通过；暂停态持续预览待后端实机集成时人工确认。

前端视觉证据：`visual/2026-10-13-calibration/` 中的 `waiting`、`paused`、`over`、`under` 各有同尺寸设计图、实际 React 截图、并排图和边缘差异图。实际图使用 2026-10-13 从 RK3562 原始流取得的空盘帧；摄像头视野与交互稿的示意盘构图不同，保留真实画面。实际页面字体资源 `SmartBox Kai` 在浏览器检查通过。

## Chunk 2：稳定等待、遮挡与五点几何

### Task 3：连续稳定判据

**Files:** Create `katrain/vision/calibration_stability.py`；Test `tests/test_vision/test_calibration_stability.py`。

- [ ] 先写测试：首帧不得立即放行；连续稳定若干帧后放行；棋盘 ROI 内移动会清零稳定计数；ROI 外小动作不致误判；外框不可见不放行；一只完全静止、遮住盘内网格的手也不放行；取消立即退出等待。
- [ ] 用 `MotionFilter.is_stable_with_regions` 判断 1/4 尺寸帧。当前有效且未漂移的锁可提供 ROI 候选，但必须在当前帧上复核线网；首次标定使用与盘色无关的线网/轮廓定位。`geometry_detect.detect_board_raw` 仅作可选候选，不能作为唯一前提。再检查内部网格线段可见比例，静止遮挡不能只靠帧差判为“空盘”。连续稳定与可见比例阈值由上板空盘/手遮样本确定，首帧仅初始化。
- [ ] 修改 `GeometryCalibrationService._run()`：挂起 worker 后先等待稳定再调用 `_converge_exposure()`；硬件自动→手动切换后清空 MotionFilter 历史并再次等待稳定，第一盏灯前复核网格可见；失败/取消时恢复进入本轮前的控制模式。
- [ ] 在 RK3562 检查外框与网格可见性检测耗时、空盘误拒率、静止手误放行率；若真机上不可靠，保持“等待/无法确认棋盘”，不得静默降级为首帧放行。

### Task 4：五点采样与独立天元校验

**Files:** Modify `led_geometry_calibrator.py`、`geometry_calibration_service.py`；Test `tests/test_led_geometry_calibrator.py`, `tests/test_geometry_calibration_service.py`。

- [ ] 先写失败测试：只采 `(0,0),(0,18),(18,18),(18,0),(9,9)`；四角拟合后天元投影误差超过阈值拒绝发布；角点错位（含 2026-10-13 实测的三角点挤到画面底部）、天元错位、缺帧均可诊断；正常五点成功且 `progress.total=5`。
- [ ] 将四角单应与天元留出校验写成明确函数。接受角点前，对照当前帧的可见网格位置拒绝异常大亮斑或落在盘外/错误角的质心；阈值用盘面格距表达，并用已有 RK3562 锚点历史回放选择。不得从同五点拟合残差自证正确。失败最多重拍未确认点；不能拿已被遮挡的点凑满五点。
- [ ] 为正常角点延长单次亮灯持有时间，以现有 `HOLD_EXTRA_FRAMES/HOLD_STEP_MS` 为基础；记录每点耗时，避免超过原 13 点流程总时长。差分仍要求手动曝光模式已读回生效。
- [ ] 更新 `progress`、成功质量指标、README 和所有 `13/13` 文案/测试；保留旧持久化格式的读取兼容性。跑上述两个聚焦 pytest 文件。

### Task 5：采样中遮挡暂停并保留已定位点

**Files:** Modify `calibration_stability.py`, `led_geometry_calibrator.py`, `geometry_calibration_service.py`, `_ACTIVE_CALIBRATION_PHASES` in `endpoints/geometry.py`；Test 两个标定 pytest 文件。

- [ ] 先写线程/假相机测试：点击后静止的手仍在时 LED 调用数为零；第 3 点后遮挡进入 `obstructed`、灯灭、前 3 点不变；移手稳定后只重试第 4 点；第五点后基线采集被手挡时五点保留、基线重拍；取消会唤醒阻塞并灭灯；曝光切换造成的整帧亮度变化不得被当成“手已离开”。
- [ ] 采样前用连续稳定闸，亮灯帧之间只比较相同 LED 状态的帧；检测到运动或网格遮挡时丢弃当前未确认的亮灭帧、清灯、等待稳定，再取新的帧对。基线 8 帧也检查稳定与可见性，任一帧被遮挡则保留五点、整组重拍。`anchor_observer` 只在当前点最终确认后触发一次。
- [ ] 用设备日志/预览核对手挡首灯、手挡中途和手持续停留的状态；不满足可观测判据时不宣称遮挡已经被解决。

## Chunk 3：光线恢复、语音与设备验收

### Task 6：光线暂停与曝光重检

**Files:** Modify `geometry_calibration_service.py`, `led_geometry_calibrator.py`, `endpoints/geometry.py`, `geometryApi.ts`；Test `tests/test_geometry_calibration_service.py`, `tests/test_geometry_api.py`。

- [ ] 先写测试：过曝/欠曝时 `phase=lighting_paused` 且 LED 灭、点数保留；无按钮确认不偷跑；重检中 `phase=lighting_rechecking` 且重复请求 409；重检仍不合格保持暂停；重检合格重新锁曝光并只重试当前点；取消优先于重检；失败/取消恢复原 AE 策略。
- [ ] 保留现有极端曝光闸，增加棋盘范围内的持续光线质量判定；先在设备“开窗帘/关窗帘/开灯”采样中位数、削顶率及 LED 信号，再定提示阈值，避免仅凭整帧 `median=176` 或异常 blob 面积猜原因。仅在能判明亮/暗时发对应提示。
- [x] `recheck-lighting` 通过线程事件唤醒；服务先用硬件 AE 收敛、读回确认手动锁，再重新拍当前点。等待期间状态可轮询，原始预览继续显示实时画面。标定线程结束时由设备 `resume_vision` 恢复硬件 AE。

### Task 7：同音色语音和弹窗

**Files:** Modify `useVoice.ts`, `scripts/generate_tsumego_voice.py`, `GeometryCalibrationScreen.tsx`；Create `katrain/sounds/voice/calibration_*.mp3`；Test `audioPrefs.test.ts`, `GeometryCalibrationScreen.test.tsx`。

- [ ] 文案定为短句：“请移开手，保持棋盘上方无遮挡。”“正在标定，请不要遮挡棋盘。”“检测到遮挡，请移开手。”“光线太亮，请拉上窗帘，避开直射光。”“光线太暗，请打开室内灯。”“棋盘标定完成。”
- [ ] 将语音 ID 放进现有 `VoiceName` 与同一生成脚本，按 `zh-CN-XiaoxiaoNeural` 生成并试听 MP3；声音仍走 `useVoice`、`kiosk_audio_voice`。当前本机 Edge TTS 返回 403；如仍不可用，先完成非语音代码，不以浏览器 `speechSynthesis` 或别的音色冒充，通过可用的同服务环境生成后再交付语音验收。
- [ ] 进入一个新状态只播一次，轮询不重复播；离开标定页或取消时停止。光线弹窗给具体操作、保留点数和“调整后重新检测”；动作区保持原有一颗取消键。
- [ ] 聚焦组件与语音开关测试；试听实体设备或同型号扬声器，确认音色和做题语音一致。

### Task 8：集成与 RK3562 实测

**Files:** 删除临时 Fixture；更新 `katrain/web/ui/src/kiosk/pages/VisionSetupPage.tsx`、`katrain/i18n/locales/cn/LC_MESSAGES/katrain.po` 的 13 点副标题；必要时更新 `katrain/vision/README.md` 和本计划中的实测记录。

- [ ] 跑聚焦 pytest、Vitest 和一次 kiosk 生产构建；不追加与本次路径无关的全量测试。
- [ ] 在 RK3562 完成：移动的手和静止的手遮第一个点、完成 2–3 点后遮挡、基线阶段遮挡、强光与暗光调节、取消/重试、原始画面实时更新、正常五点成功、旧锁失败后可沿用/重定位。记录每个状态的服务时间戳、预览变化时间、五点总耗时，以及光线变化到预览和识别链路生效的延迟（至少各 5 次，报中位数和最慢值）。
- [ ] 将同尺寸的实际页面和参考图并排/叠加核对；检查 `SmartBox Kai` 的计算字族和实机字形。后端真实状态已接入后删除 Fixture；只在实际五点锁通过空盘自检和棋子识别时判为完成。

## 验收与风险

## 新增切片：移动阴影不干扰标定和对局（2026-10-13）

**需求边界：** 人体投在棋盘上的软阴影移动时，标定不误报“手遮挡”、不丢已定位点，对局不把阴影当棋子或落子；网格/棋子已因极暗不可辨时仍需安全暂停并提示光线不足。以当前白色实物盘和 RK3562 摄像头采样为准。

- [x] 采同一段真实阴影变化的原始帧、识别状态和检测棋盘；记录阴影前、中、后可见性、运动比率与误检，区分阴影和手的症状。标定状态仍需重测。
- [x] 在 `tests/test_vision/test_calibration_stability.py` 加真实阴影帧，保留“静止手挡网格不得亮灯”的反例；只针对证实的原因修正稳定判据。
- [ ] 在 `MotionFilter`、`worker_inprocess`、参考帧/棋盘状态各边界定位对局误判源；先写阴影变化时棋盘不变、真实落子仍能识别的聚焦测试，再做最小修复。不得靠一律跳帧实现“免疫”。
- [ ] RK3562 重测移动阴影 3 次，核对空盘无假子、标定点保留并完成、灯不会在真手遮挡时亮、两条链路恢复时间；只跑相应聚焦测试并保留一次实际 1024×600 页面检查。

### 2026-10-13 实机进度

- 19:15 MacBook 语音倒计时下采集真实身体移动阴影 85 帧，棋盘中位亮度 165→123，网格全程可见；旧运动过滤在阴影窗口 24 帧中拒绝 13 帧，识别日志出现 `roi:0.486`、`roi:0.394` 的错误运动拒绝，但检测棋盘保持 0 子，无最终假落子。新算法对局部亮度做 19×19 均值归一化后再比较纹理，仍用真实遮手截图和断光帧验证拒绝。相同 85 帧回放的阴影窗口里，标定等待和采样均 24/24 放行。RK3562 设备 1080p 运动判断实测中位由旧 19.9 毫秒降至新 14.3 毫秒；优化版已部署，等待移动阴影的第二次现场复测。聚焦 Python 测试 221 项通过。
- RK3562 已部署并完成一次真实五点标定。18:05:16 在暗场暂停后按“调整后重新检测”，硬件 AE 于 18:05:17 把画面中位亮度从 9 拉到 161；18:05:46 点亮第一灯，18:06:07 确认第五点，18:06:14 发布新几何锁。天元留出误差 1.80 像素，空盘基线自检通过，`geometry_ready` 与 `recognition_ready` 均为真。结束后 V4L2 `exposure_auto=3`，原始预览实测中位亮度 153，首帧获取 0.13 秒。
- 暗场 `lighting_paused / frame_underexposed`、0/5 进度保持、重检返回暂停以及开灯后恢复，已在设备上验证。灯前网格检测耗时中位约 44 毫秒。聚焦测试：Python 142 项、前端 55 项通过。
- 三轮关灯/开灯实测时，MacBook 以同一语音先说操作，再逐秒播报 5、4、3、2、1；同时采原始 MJPEG、识别 MJPEG、RK3562 屏幕和识别 worker 日志。原始流 434 帧，帧间隔中位 0.242 秒、P95 0.462 秒；识别流 246 帧，帧间隔中位 0.414 秒、P95 0.792 秒。以原始流首个亮/暗帧为基准，识别流对应变化分别滞后 0.590/0.471/0.977 秒及 0.290/0.579/0.503 秒；亮场三次中位 0.590 秒、最慢 0.977 秒。识别 worker 在开灯后恢复的日志时间与原始首个亮帧相差一个采样帧以内。语音口令与人工拨动开关不同步，以上不是物理开关到传感器成像的绝对延迟。全关灯的暗场中位亮度仅 0–1；无入射光时 AE 无法凭空恢复画面。
- 18:52 首次真实手遮实测：遮住棋盘中央后约 2 秒进入 `obstructed`，0/5 且 LED 灭；移手后屏幕显示网格完整，状态却仍卡在 `obstructed`。保存移手后的原始帧，复现出正常阈值找不到网格边框、反向阈值可找到的根因。增加该帧回归测试并修复双阈值候选检测。
- 修复后的复测进入 `obstructed` 后恢复并依次定位 5 点；屏幕截图显示倒计时后约 5 秒时手已不在棋盘上，所以这轮只证明短暂遮挡可恢复，不能算持续遮挡和中途保点实机验收。该轮在基线阶段因 8 帧中少 1 帧而失败，追到 `CameraHub.grab_burst` 遇到生命周期锁冲突时会跳过帧；五点标定改为最多重拍整组 3 次，并以首组 7 帧、次组 8 帧的测试固定。
- 19:04 修复后的空盘实测从启动到 `ready` 43.86 秒，五点均定位、独立天元校验及空盘基线通过；`rms_residual=1.27` 像素，`max_residual=2.83` 像素，设备 `preflight.ready=true`，结束后 V4L2 `exposure_auto=3`。
- 19:08 再用 MacBook 播报操作和五秒倒计时测试中途遮挡。手在四角已定位、天元未定位时进入画面；`hand_now` 后 0.22 秒进入 `obstructed`，四点保留、LED 熄灭；屏幕在遮挡初期和约 9 秒后均显示手、`4/5` 与暂停。播报移手后 0.61 秒回到 `waiting_stable`，只补天元与空盘基线；从启动到 `ready` 70.1 秒，`rms_residual=0.56` 像素，`preflight.ready=true`，V4L2 `exposure_auto=3`。这覆盖“中途持续遮挡、保留已锁点、自动继续”的实机验收。
- 六条新语音的代码、共享播放器和设置已接通；同音色 MP3 尚未生成。Mac、RK3562 和另一台服务器上的 Edge TTS 7.2.8 均返回 403。用户已确认本轮先保留文字提示，语音音频后补；不能把静默播放当作语音验收通过。MacBook 的 `say` 只用于这次人工测试的开关灯/手遮挡口令，不是产品音频。
- 20:00 针对左侧实时画面在设备上用中央 LED 六次切换测延迟。旧 MJPEG 页面原始预览从 LED 请求到显示变化常见 0.4–0.7 秒，最慢 1.9 秒，说明浏览器会显示积压帧；标定期间若用户切到“俯视矫正”，原组件还会撤下视频形成空白。现改为单张最新 JPEG 拉取、同一时刻只保留一个请求，在 canvas 显示，并在活动标定中强制使用原始画面。新方案并发采样原始流与设备浏览器像素的六次结果：原始预览中位 0.348 秒、最慢 0.409 秒；俯视预览中位 0.378 秒、最慢 0.548 秒（均为 LED HTTP 请求发出到页面像素变化，不含人工操作时间）。1024×600 实机截图确认重启后预览可恢复且有实时画面；Python 聚焦测试 166 项通过。
- 20:09 阴影实测定位到标定稳定闸的原始帧缩图使用线性插值，棋盘细线与相机噪声产生混叠；服务日志在移动阴影的 13 秒内报告 ROI 变化比 0.065–0.071，超过 0.035 门槛，而浏览器的面积平均预览图回放正常。改成面积平均后，20:14 的第三轮实测在阴影仍移动时已亮天元灯（20:14:10，阴影结束口令 20:14:20），五点均定位；独立天元误差合格。此轮最后的旧式空盘 HSV 基线自检因移动光照报 5 个假白子，没有发布新几何。对局 `ReferenceFrame` 则按当前照片和棋局矩阵动态建立，两者不能混成一份。已实现并通过聚焦测试的“仅重试基线、不重闪五灯”修复尚未部署，等待确认标定是否允许盘上有子，再决定旧式颜色基线的处理。
- 20:23 部署“仅重拍基线、最多两次”的修复后，空盘正常五点实测 `ready`、`5/5`、RMS 0.77 像素、最大误差 1.71 像素，`preflight.ready=true`（4.36 秒）。本轮没有移动阴影；阴影持续到基线末尾时能否靠自动重拍收尾，仍需后续实机覆盖。新的用户要求是标定初始画面不一定为空盘；正在确认是否要求五灯标定本身允许棋子，避免把 `GeometryLock.baseline` 误写成有子图片并让传统摆谱 QA 漏判。

- 正常启动前没有任何 LED 点亮；等待、遮挡、亮/暗暂停均可取消；已确认点不因暂停丢失。
- 五点锁必须经天元独立校验与现有空盘自检；校验不过宁可给诊断，不发布错误几何。用户只看五点进度，不需知道正在亮哪个灯。
- 光线提示来自设备上可复现的图像/信号判据，不能把手影误称为“太暗”。实时预览与识别使用同一相机控制状态，标定期间的手动锁仅为 LED 差分服务。
- `MotionFilter` 只证明“近期没有运动”，不能证明一只静止的手不存在；首次放行还要求外框和内部网格可见，且有静止手覆盖的实机反例测试。每点亮灭帧与最终空盘基线也做遮挡复核；若实机仍误放行，不满足首灯验收，必须收集遮挡帧修正可见性判据。
- 实际页面的字体只复用仓库现有霞鹜文楷资源；交互稿不再修改。
