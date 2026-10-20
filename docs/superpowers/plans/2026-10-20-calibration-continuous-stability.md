# Calibration Continuous Stability Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 静止空盘完成首次曝光和稳定确认后，连续完成五点定位与八帧基线，仅在新鲜画面证明异常时暂停并重试当前步骤。

**Architecture:** 保持现有 `configure_live(before_capture, frame_guard, anchor_roi, on_lighting)` 契约。服务区分首次/曝光后的完整稳定闸与点间的连续检查；稳定闸和捕获监测衔接帧历史，真实异常才重建基准。五点校准器验证每次采样的 seq/ts，并逐帧采集、立即检查基线，保留既有拟合、质量和发布条件。

**Tech Stack:** 现有 Python、NumPy、OpenCV、pytest；共享 FastAPI 服务与 React 页面使用现有状态，无新依赖。

---

## Chunk 1: 范围、证据与接口

### 输入与已核查代码

- PRD：`/Users/fan/Repositories/smartbox-software-gomoku-features/docs/superpowers/specs/2026-10-20-katrain-calibration-continuous-stability-prd.md`，截图说明已在 SmartBox 提交 `35759408`。
- 工作目录：`/private/tmp/katrain-calibration-stability`，独立 checkout，分支 `fix/calibration-continuous-stability`，起点为 `fix/kiosk-ui-debug`。
- 不改主目录 `/Users/fan/Repositories/katrain-kiosk-debug`，不修改 SmartBox 工作树，不部署或合并。后续集成到当前 kiosk bug 分支由主 agent 执行。
- `katrain/vision/led_geometry_calibrator.py:687,724`：每点及基线的 `before_capture` 均调用服务稳定闸。
- `katrain/web/core/geometry_calibration_service.py:805-852`：检查帧前无条件清运动历史，发送 `waiting_stable/board_motion`；默认需要首帧加四帧稳定。初始两次曝光后的闸门另行存在。
- `katrain/vision/calibration_stability.py:116-156`：稳定与采集各有独立 MotionFilter，放行后服务还清掉 `capture_motion`，导致首个捕获帧缺少与放行帧的比较。
- `katrain/vision/camera.py:642-667`：`grab_fresh` 超时可返回缓存帧，调用者必须验证 `seq` 和 `ts > after_ts + settle_ms / 1000`。
- `LedGeometryCalibrator._locate_anchor:515-519`：灭灯帧为 `None` 仍可能点灯；`_hold_min:591-597` 缺帧会使用已有子集。五点路径必须阻止缺/旧帧被接受。
- `FivePointLedGeometryCalibrator.calibrate:736-747`：`grab_burst(8)` 完成后才逐帧 guard，不能及时发现基线中途异常，且 burst 不返回帧身份。
- 共享页面 `GeometryCalibrationScreen.tsx` 按现有 phase 映射步骤；不需要改 UI 即可消除正常点间第一步闪回。

### 固定接口与不变量

| 边界 | 契约 |
| --- | --- |
| `before_capture(phase, current, total)` | LED 熄灭；先获取并校验新鲜灭灯帧；持续稳定时一次检查即返回；异常或历史失效时等完整稳定序列；返回前恢复请求的 phase/current。 |
| `frame_guard(frame, dark)` | 对每张已验证新鲜的帧检查运动/遮挡；灭灯帧还检查盘面光线；抛 `CalibrationInterrupted` 或 `LightingInterrupted` 前使连续稳定历史失效。 |
| `on_lighting(reason)` | 保留光线暂停、用户重检、曝光收敛；曝光变化前后的运动历史不能混用，恢复后重建稳定基准。 |
| `anchor_roi(row, col)` | 保持现有返回值和几何含义。 |
| 点重试 | 当前未确认点的异常不丢弃已确认点、不重复通知已确认点；取消优先退出，LED 熄灭。 |
| 实体手部遮挡 | 手覆盖网格时，即使保持静止，也不得点灯；点内发现遮挡立即 clear，遮挡持续时不重闪，移手并重新积累完整稳定序列后只重试当前未确认点。 |
| 正常人物阴影 | 只有阴影、网格仍可见且满足既有曝光质量时继续标定，不进入遮挡/移动/光线暂停；保留 `illumination_invariant=True` 与全部既有运动/质量阈值，不以提速改动抗阴影逻辑。 |
| 基线重试 | 保持八张可信帧；任一运动/遮挡/光线异常即丢弃整组；恢复后重拍整组，不重闪前五点。 |
| 硬件/帧失败 | 未取得可信灭灯帧不得点灯；缺帧/缓存帧不能贡献稳定证据或成功锁；保留有界失败/既有取消行为。 |
| 发布 | 保留四角拟合、天元独立校验、held-out 空盘检查、完整几何和取消发布边界；不改锁格式或质量阈值。 |
| 取消优先级 | 五点路径在采样前后、dark guard 返回后/实际点灯前、锚点确认通知前、`_build_lock` 返回后/成功返回前检查取消；取消后不得再次亮灯、追加锚点通知或返回成功锁，沿既有 finally clear，不增加锁或取消协议。 |

**资源限制：** 复用现有 640 宽缩图、网格 ROI 和运动过滤器。稳定成功时复用已计算的缩图/掩码衔接 capture history，避免重复全尺寸网格检测。不开新线程、服务、状态协议或通用相机框架。

### 并行与文件所有权

两位 fresh implementer 可在同一隔离 checkout 并行工作，但只修改自己的文件；开始前共享上表契约。不可直接套用已撤回 WIP；实现必须从获审计划和红灯测试开始。

| Worker | 独占写入文件 | 依赖/交付 |
| --- | --- | --- |
| A：稳定连续性与状态 | `katrain/vision/calibration_stability.py`、`katrain/web/core/geometry_calibration_service.py`、`tests/test_vision/test_calibration_stability.py`、`tests/test_geometry_calibration_service.py` | 保持 configure_live 契约；初始稳定放行衔接捕获基准；真实异常清历史；正常点间单帧检查；真实状态。 |
| B：五点采样可信度 | `katrain/vision/led_geometry_calibrator.py`、`tests/test_led_geometry_calibrator.py` | 保持 configure_live 契约；五点帧身份校验、缺帧不点灯、hold 可信与取消、基线逐帧 guard/整组重拍。 |
| Integrator：组合验收 | 优先使用 A/B 已有测试文件中的一个组合用例；A/B 停止写入后才修改；可更新本计划的执行记录 | 两组提交合并结果与真实服务+真实五点路径的聚焦验收；负责统一提交，避免 worker 互相暂存文件。 |

并行风险仅在回调时序：A 负责 before_capture 自身采样的新鲜度，B 负责校准器采样的新鲜度；两个调用方分别维护自己的 seq/ts，不能互相假定已验证。基线现在会边采边 guard，A 的异常失效必须同步生效。整合测试证明两者组合，不能仅测试 mock 回调。

## Chunk 2: 实施任务

### Task A: 复用连续稳定历史并诚实报告状态

**Files:**
- Modify: `katrain/vision/calibration_stability.py` (`CalibrationStabilityGate.observe/reset/capture_reason`)
- Modify: `katrain/web/core/geometry_calibration_service.py` (`_wait_stable/_guard_live_frame/_wait_lighting/_run`)
- Test: `tests/test_vision/test_calibration_stability.py`
- Test: `tests/test_geometry_calibration_service.py`

- [ ] **A1: 添加会失败的稳定连续性和状态测试。**
  使用已有 `tests/data/rk3562_empty_board_20261013.jpg` 和返回合法递增 seq/ts 的 fake capture；fake 必须满足请求的 after_ts+settle，不能用重复帧身份充数。在服务 `_run()` 接入保持真实 configure_live 的测试校准器，走五次点回调及一次基线回调，记录每次 capture 时的 phase/pause_reason/current/detected_anchors。

  断言首次两次曝光后完整闸仍存在；进入点流程后六次 before_capture 各取一张可信灭灯帧，正常点间没有 `waiting_stable`/`board_motion`；phase 依次闪角、校验天元、建基线，current 不回退，已确认点计数只增加一次。

  增加首个捕获帧相对稳定放行帧移动的测试；应抛 `CalibrationInterrupted`，历史归零。保留既有初始静止手遮挡不点灯的行为测试，并修正该 fake 忽略 settle 的问题。第 3 点遮挡的真实组合恢复由 C1 验收，不能仅用 mock guard 抛异常替代。

  明确新增阴影回归 `test_capture_guard_accepts_shadow_round_trip_without_repriming`：用真实 `rk3562_shadow_before_20261013.jpg` 建立稳定基准，直接通过真实服务 `_guard_live_frame` 执行 **before → shadow → before**（shadow 为 `rk3562_shadow_during_20261013.jpg`）。不得先调用 `observe(shaded)` 替换待比较的 capture baseline；断言每次 guard 均通过、无暂停，且下一点 before_capture 继续一次新鲜灭灯检查即放行。保留 LED 局部亮度不误报测试。实体手部 crop 只用于已有 MotionFilter 回归，不冒充完整五点成功盘面。

- [ ] **A2: 运行红灯测试并记录实际失败原因。**

  ```bash
  /Users/fan/Repositories/katrain/.venv/bin/python -m pytest -q tests/test_geometry_calibration_service.py::test_live_calibration_reuses_stability_between_all_five_points_and_baseline tests/test_geometry_calibration_service.py::test_stability_release_checks_motion_in_the_first_capture_frame tests/test_geometry_calibration_service.py::test_capture_guard_accepts_shadow_round_trip_without_repriming
  ```

  A1 使用上述实际新增 test 名；若实现者更名，须同步命令，或直接用实际 node id 逐项运行并汇报，不能用宽泛 `-k` 漏测。当前预期红灯：正常六次 before_capture 各要五帧；首个 capture MotionFilter 没有基准而接受移动。阴影兼容用例允许起点已通过，仍必须纳入绿灯回归；不能为了制造红灯改变正常判据。

- [ ] **A3: 实现最小连续检查。**

  建议保留内部方法并新增关键字参数，避免修改公共契约：

  ```python
  def _wait_stable(gate, resume_phase, current, *, reset=True):
      cleared = led.clear(strict=True)
      require_clear_success(cleared)
      if reset:
          gate.reset()
      cutoff = max(now(), cleared['shown_at'])
      last_seq = -1
      while not cancelled:
          frame, seq, ts = capture.grab_fresh(after_ts=cutoff, settle_ms=120)
          check_cancel_before_any_acceptance()
          require_frame_and_identity(seq > last_seq, ts > cutoff + 0.120)
          last_seq, cutoff = seq, ts
          check_whole_exposure_or_pause_and_reconverge()
          ready, reason = gate.observe(frame)
          if not ready:
              report_observed_reason(reason)  # 首张新帧之后才报告
              continue
          check_board_lighting_or_pause_and_reconverge()
          progress(resume_phase, current, 5)
          return
  ```

  `require_*` 等名字是伪码步骤，不要求引入这些 helper。`_run` 的两次曝光后等待使用 `reset=True`；configure_live 的 before_capture 使用 `reset=False`。不能在循环开始无证据先报 board_motion。

  `observe` 放行时用已算出的 small/mask 衔接 `capture_motion`，移除服务放行后的无条件 capture reset；正常 guard 仍持续检查所有帧，LED 点亮不写入只比较灭灯帧的稳定历史。guard 检测运动/遮挡后重置稳定与捕获历史，设置真实暂停原因并抛现有异常；校准器负责立即 clear 并回到当前点。光线异常同样使基准失效，沿用现有 on_lighting 流程。

  若新鲜帧缺失或身份无效，保守失败为 `no_frames`（或现有等价错误），不得无限用缓存积累稳定或继续点灯。光线重检缺帧不得伪报为过暗后继续；取消在等待前后均优先退出。LED clear 失败不得继续采集放行。

- [ ] **A4: 运行 A 的聚焦套件。**

  ```bash
  /Users/fan/Repositories/katrain/.venv/bin/python -m pytest -q tests/test_vision/test_calibration_stability.py tests/test_geometry_calibration_service.py tests/test_vision/test_motion_filter.py::test_moving_body_shadow_keeps_board_motion_stable tests/test_vision/test_motion_filter.py::test_illumination_invariant_filter_still_rejects_hand_and_no_light
  ```

  期望所有相关测试通过，包含现有真实手部出现/移开与人物阴影两条 MotionFilter 回归（该文件只读，不扩大 A 的写入所有权）；额外覆盖曝光重检后首帧不立即放行、缺/旧帧不放行、取消退出。只扩展本次实际风险，不改页面布局或全局相机代码。

- [ ] **A5: 向 integrator 交付变更和测试结果。**
  给出修改文件、契约是否保持、红灯/绿灯命令、未覆盖的设备项；不暂存或提交 B 的文件。

### Task B: 五点路径的新鲜采样与逐帧基线监测

**Files:**
- Modify: `katrain/vision/led_geometry_calibrator.py` (`_locate_anchor/_hold_min` 的小型采样 hook 与 FivePoint 专用实现、FivePoint.calibrate)
- Test: `tests/test_led_geometry_calibrator.py`

- [ ] **B1: 添加会失败的帧可信度和基线时序测试。**
  参数化 None 帧、seq 重复、ts 重复、ts 未晚于 `after_ts + settle`；分别注入第 3 点灭灯、亮灯、hold 样本，以及基线中途。断言无可信灭灯帧时不发该点 LED 命令；亮灯/hold 缺旧帧不能确认点或发布锁；失败/取消最终灯灭。

  基线用第三张帧抛 `CalibrationInterrupted` 的序列，确认 guard 在采第 4 张前执行；前组立即丢弃，恢复后恰好完整八帧重拍，五个已确认点不重闪。保留/调整已有“短 burst 三次重试”用例，使其通过新的逐帧采样路径注入短组，测试业务行为，不测试已移除的 grab_burst 调用次数。

  增加确定性的回调取消注入：dark guard 内设 cancel，返回后不得 `set_rgb_points`；最后一张 hold 的 guard 或 centroid 处理结束前设 cancel，不得再调用 anchor_observer；`_build_lock` 包装回调先构建再设 cancel，返回后不得 `ok=True`。断言取消后无下一次采样、无后续 LED 命令、无新增锚点通知/成功锁，finally 后灯灭。不能只测试采样 hook 内取消。

- [ ] **B2: 运行新增测试确认红灯。**

  ```bash
  /Users/fan/Repositories/katrain/.venv/bin/python -m pytest -q tests/test_led_geometry_calibrator.py::test_five_point_rejects_untrusted_capture_frames tests/test_led_geometry_calibrator.py::test_five_point_baseline_guards_before_the_next_capture tests/test_led_geometry_calibrator.py::test_five_point_cancel_from_dark_guard_does_not_light tests/test_led_geometry_calibrator.py::test_five_point_cancel_before_anchor_confirmation tests/test_led_geometry_calibrator.py::test_five_point_cancel_during_lock_build_does_not_succeed
  ```

  B1 使用上述实际新增 test 名（参数化节点可直接指定函数名）；更名须同步实际 node id，不能漏选。预期当前缺/旧灭灯帧仍可能点灯、hold 缺帧仍成功、基线先采完八帧后才调用 guard、guard/处理回调取消后仍可能点灯/确认/成功返回。确认失败是这些行为，而非 fake 没遵守新鲜帧契约。

- [ ] **B3: 实现五点专用的新鲜帧入口。**
  保持旧十三点逻辑的采集/缺帧语义；可在基类增加默认直通 `_grab_fresh` hook，将 `_locate_anchor/_hold_min` 的三处直接调用转为 hook，FivePoint 覆盖该 hook 验证帧身份。还要处理 `FivePoint.calibrate:715-718` 仅用于 shape 的第四处直接抓帧：优先复用最近一张可信帧的 shape 去掉额外采样；如保留则同样走新鲜度与取消校验。每轮 calibrate 初始化五点路径的 last_seq/last_ts；不修改全局 CameraManager。

  ```python
  def _grab_fresh(after_ts=None, settle_ms=0):
      cutoff = max(after_ts if after_ts is not None else now(), last_ts)
      check_cancel()
      frame, seq, ts = capture.grab_fresh(after_ts=cutoff, settle_ms=settle_ms)
      check_cancel()
      if (frame is None or seq is not integer or seq <= last_seq
              or ts is not finite or ts <= cutoff + settle_ms / 1000):
          raise FivePointFrameMissing('no_frames')
      last_seq, last_ts = seq, ts
      return frame, seq, ts
  ```

  异常名是实现建议，可用更小的等价设计，但必须区分取消、运动/光线暂停和不可用帧。五点顶层把帧失败转换为 `CalibrationResult(ok=False, reason='no_frames')`；基线采样捕获同类缺帧以执行已有最多三次整组采集重试。hook 必须在暗帧缺失时打断流程，确保不会走到 `set_rgb_points`。取消不消耗失败重试额度，也不能被转换成成功或一般缺帧。

  采样 hook 外的五点取消检查同样必要：`_guard_frame(dark)` 返回后/真正发送 LED 前检查；hold 最终 guard、图像合成与 centroid 检测后，在确认 anchor_observer 前检查。取消须直接沿当前 finally clear 返回 `CalibrationResult(ok=False, reason='cancelled')`，不能因 guard 已结束而继续动作。沿已有 Event/异常流程实现，不引入新锁或取消协议。

  修改 tests 中 fake capture 的帧身份生成，使它满足 requested after_ts+settle 且严格递增，采用逻辑时间而非实际 sleep；只校正 fake 契约，不放宽生产检查。

- [ ] **B4: 把八帧基线改为逐帧采样、立即检查。**
  保留基线前 before_capture（A 会执行连续新鲜灭灯检查）、LED clear 严格成功检查、三次缺帧整组重试和 BaselineNotEmpty 上限。

  ```python
  for burst_attempt in range(3):
      frames = []
      for _ in range(8):
          check_cancel()
          frame, seq, ts = grab_valid_fresh(settle_ms=100)
          frame_guard(frame, dark=True)  # 在下一张采样前检查
          frames.append(frame)
      if len(frames) == 8:
          break
  # 只有全八帧可信才 _build_lock；运动/光线异常走现有外层恢复循环。
  ```

  可以用小型 FivePoint 私有方法表达，不能再依赖不带身份的 `grab_burst`。约 100 ms 的采样间隔保持原基线资源/时间预算；不新增忙轮询。运动/遮挡/光线异常传播到现有异常分支，立即熄灯（基线本已熄灯）、丢弃整组、只重试当前基线。取消在 `_build_lock` 前再次检查，**`_build_lock` 返回后、成功结果返回前也再次检查**，确保耗时构建中取消不能返回成功锁；服务现有发布取消边界继续保留。

- [ ] **B5: 运行 B 的整个聚焦文件并交付。**

  ```bash
  /Users/fan/Repositories/katrain/.venv/bin/python -m pytest -q tests/test_led_geometry_calibrator.py
  ```

  期望旧十三点检测/容错、五点拟合与天元阈值、短组重试、held-out 基线检查仍通过；汇报新鲜度拒绝和取消证据。

## Chunk 3: 集成、独立审核与交付

### Task C: 组合验证与发布边界

**Files:**
- Review: A/B 的所有修改文件及共享页面的现有状态映射
- Test: 在 A/B 停止写入后使用已有测试文件补最小真实组合用例；不另建测试框架
- Update: 本计划的执行记录

- [x] **C1: 串行整合 A/B，并执行一次真实组合验收。**
  使用真实 FivePoint 校准器、真实 CalibrationStabilityGate、服务 configure_live 回调和可信相机序列；可以替换硬件、曝光控制和持久化，不能把待验证的稳定/guard/重试逻辑全部 mock 掉。验证静止五点成功时六次点前/基线前检查均不重建稳定闸；基线异常恢复和 confirmed anchors 有组合覆盖；实际 final fit/基线质量路径至少保留一个已有成功测试。若 A/B 用例已充分覆盖组合，复用而不重复新增。

  **实体手遮挡的组合硬验收：** 在第 3 点的采样过程中，以已有真实白盘 fixture 加现有 ellipse 手部遮挡构造产生真实网格不可见帧，而非令 mock guard 主动抛异常。硬件 fake 记录 clear/show/capture/anchor 事件。至少连续送入多张完全相同的遮挡帧，证明手静止也不被当成稳定；遮挡首次被识别后立即 clear，遮挡持续期间不再 show；前两个 confirmed anchors 保留；移手后首帧不能立即点灯，要积累完整稳定序列，随后只重试第 3 点并继续。用真实 service + gate + FivePoint 完成这一断言，不将真实手部 crop 冒充全盘 fixture。

  **正常人物阴影的组合硬验收：** 复用 A1 的真实 before→shadow→before guard 转换及下一点连续检查证据，结合真实 FivePoint 路径证明只有阴影时不触发等待/遮挡/光线暂停。不可先 observe(shaded) 重设 capture 比较基准，不改 `illumination_invariant` 或阈值迁就测试。

- [x] **C2: 执行最低充分回归并检查 diff。**

  ```bash
  /Users/fan/Repositories/katrain/.venv/bin/python -m pytest -q tests/test_vision/test_calibration_stability.py tests/test_led_geometry_calibrator.py tests/test_geometry_calibration_service.py tests/test_vision/test_motion_filter.py::test_moving_body_shadow_keeps_board_motion_stable tests/test_vision/test_motion_filter.py::test_illumination_invariant_filter_still_rejects_hand_and_no_light
  git diff --check
  git diff --stat
  ```

  起点这三文件套件为 **173 passed in 10.19s**。只在发现新的具体风险或失败时扩展测试。无需前端构建/全状态截图，因页面与状态协议未变；以状态时序验证四步展示依据。

- [ ] **C3: Astra Max 独立代码审核，并修复直至通过。**
  由主 agent 另派 Astra Max；审核 PRD 全部验收边界、帧 freshness cutoff、history 交接、真实异常 reset、LED clear/取消、八帧完整性与旧十三点兼容性。审查范围限本次 diff；实现者修复后重复相关聚焦测试。计划阶段先由 Astra Max 独立审核本计划，最多两轮审改，获通过才进入 Task A/B。

- [ ] **C4: 统一提交可 review 结果，反馈设备验收缺口。**
  integrator 仅暂存自己的明确变更路径，提交 `preserve stability through five-point calibration`；报告分支、commit、套件输出和风险。不能以本地 fixture 的运行时间宣称 RK3562 性能或硬件通过。

  设备待验：同一 RK3562、同一相机/盘面/光线，分别记录改前/后从首次点灯到锁发布及各阶段耗时；正常空盘、第 3 点真实遮挡/移动、基线异常、光线重检、相机/LED 失败、取消；围棋和五子棋各验一轮。已有日志带单调/系统时间可用于阶段计算；如不足，仅在现有步骤日志加 elapsed/frames，不引入遥测基础设施。五子棋接入保持现有服务构造、共享路由和页面，SmartBox 子模块更新待 KaTrain 结果正式合入后按用户发布授权执行。

  已知跨产品基线依赖：SmartBox `gomoku/api/gomoku_api/vision/hardware.py:953-959` 传入 `allow_existing_reuse=False`，本次隔离 KaTrain 基线构造器没有该参数，而 SmartBox 当前 vendor 版本已有该参数且工作树另有未解决状态。这不是本次连续稳定性修改引入的问题；本任务不修 SmartBox 冲突或顺手补构造器。交付须写明“当前隔离基线未证明可直接替换五子棋 vendor；正式集成后再做兼容验收”，不能仅据状态契约未变宣称两产品都通过。

### 执行记录

- [x] 完整 PRD 已读取，根因和采集缺口已亲自核对源码。
- [x] 隔离 checkout 已建立；未改主工作目录。
- [x] 初始三文件聚焦基线：173 passed。
- [x] 按用户指定流程，先前未审 WIP 已另存 `/private/tmp/katrain-calibration-stability-wip.patch`，并恢复其三处 tracked 改动；本计划编写前 tracked 工作树干净。
- [x] Astra Max 计划审核第 1 轮：`Issues Found`，报告 `/private/tmp/katrain-calibration-plan-review-1.md`；要求补齐实体静止手遮挡/真实阴影成对硬验收，以及 guard/确认/构建结束后的取消优先边界。
- [x] 同一规划者完成唯一一轮修订：新增真实组合遮挡事件序列、未预先 observe 阴影的 guard 往返测试、两条 MotionFilter 聚焦回归、点灯/通知/成功返回前取消检查与确定性注入；同时补齐第四处 shape 取帧、精确测试 node 和五子棋既有集成依赖。仅修改计划，未改实现；本记录不代表审核通过。
- [x] Astra Max 第 2 轮计划审核：Approved；A/B 依获审计划实施。
- [x] 两位 fresh worker 已完成并停止写入。A 报告精确三个新增节点的红绿验证，A4 聚焦检查 146 passed；B 报告指定 21 个参数化节点红绿验证，整个校准器文件 66 passed。C 未改动 A/B 生产实现。
- [x] C1 新增真实组合测试，位于 `tests/test_geometry_calibration_service.py`：`test_real_five_point_chain_keeps_stability_and_accepts_person_shadow[stable/shadow]`、`test_real_five_point_chain_still_hand_pauses_only_the_unconfirmed_point`、`test_real_five_point_chain_discards_interrupted_baseline_without_reflashing`，四个节点 4 passed in 4.40s。
  - 正常/真实人物阴影路径：初始两次曝光后的闸门各五帧，六次后续 before_capture 各一帧，复用同一 gate；点流程无等待/遮挡/光线暂停，五个锚点各确认一次。真实阴影置于第 3 点 hold，实际采样直接经历 before→shadow→before，未 observe(shadow) 偷换稳定基准。
  - 第 3 点首次亮灯采样注入真实白盘加指定 ellipse 手遮挡，真实 guard 识别后下一个硬件事件立即 clear；随后连续三张完全相同的遮挡帧仍阻止 show。前两个锚点保留，移手后的第一张清晰帧不点灯，累积 required_frames=4 张稳定清晰帧后只重试第 3 点。首轮两个失败来自测试将恢复清晰帧误估为初始闸门的五张，已修正断言；生产阈值及实现未改。
  - 基线第 3 张真实遮挡打断前组；恢复后恰好八张新帧、每张请求 settle_ms=100，传给构建的帧对象全部来自新组；五点各只闪一次，五个已确认锚点均保留。
  - 替身边界：相机/LED、曝光控制、持久化、最终漂移准备；组合中用记录函数替换最终 `_build_lock` 避免重复昂贵基线构建，真实五点 fit、稳定闸、guard、逐帧采样和所有重试均实际运行。真实 fit/`_build_lock` 成功证据继续由既有 `test_five_point_calibrator_only_flashes_five_positions` 提供；本轮完整回归包含该节点。
- [x] C2 指定完整回归：**216 passed in 14.05s**，日志 `/private/tmp/katrain-calibration-combined-tests.txt`；`git diff --check` exit 0。当前 tracked diff 为五个文件 819 insertions / 68 deletions（计划仍为未跟踪文件，未计入 stat）；本轮仅新增组合测试与更新本执行记录。
- [x] C3 按 spec → quality 顺序完成两个独立 Astra Max 审核：规范审核 A/B `Spec compliant`、C1/C2 符合计划；最终代码质量审核 `Approved`，Critical/Important/Minor 均无待修问题。报告分别为 `/private/tmp/katrain-calibration-spec-review.md` 和 `/private/tmp/katrain-calibration-code-review.md`。最终质量审核者独立运行同一聚焦命令：216 passed in 13.99s，`git diff --check` exit 0。
- [x] 主 agent 已将五个已审代码/测试文件及本计划应用当前 `fix/kiosk-ui-debug` 工作区，逐文件内容与独立 checkout 一致；当前工作区最终聚焦回归 **216 passed in 15.29s**，`git diff --check` exit 0。
- [x] 已审结果在独立 checkout 的 `fix/calibration-continuous-stability` 分支统一保存提交；保留该 checkout 供后续集成。用户当前工作区仅应用改动，原 Git 管理目录位于只读范围，未在原分支提交或推送。
- [ ] RK3562 同设备改前/后阶段耗时、围棋/五子棋实机及正式 SmartBox 子模块兼容验收仍待执行；尚未合并或部署。
