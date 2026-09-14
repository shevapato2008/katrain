# 实体棋盘：曝光 / LED 标定 / 对局内恢复 —— 规格

**日期**：2026-09-02
**取证平台**：RK3562 P04（`ssh rk3562-direct`），unit `smartbox-katrain`，`127.0.0.1:8081`
**代码**：`vendor/katrain`（子模块，合并目标 `develop`）

这是两份实现计划共同的规格来源：

- `2026-09-02-calibration-robustness.md`（后端 / 视觉）
- `2026-09-02-ingame-calibration-recovery.md`（契约 + 前端）

---

## 1. 用户报的症状

1. 进围棋模块，用实体棋盘开一局自由对弈，**摄像头认不出棋子**（盘上摆了一黑一白）。
2. 设置页「棋盘标定」点「重新开始标定」，**看不到灯亮**，标定最终失败。
3. 自由对弈 / 升降级对弈等对弈模块里**没有「重新校准」按钮**。
4. 系统自动检测出需要校准，**弹窗出来一瞬间就自己消失了**。

## 2. 已查证的事实

证据等级：【实测】= 在板上或本机真跑出来的；【读码】= 指到 `文件:行`；【推断】= 由前两者推出、未直接取证。

### 2.1 摄像头曝光在 board 模式下是冻住的 —— 症状 1 的根因

- 【读码】`CameraHubConfig.lock_exposure` 默认 `True`（`katrain/web/core/camera_hub.py:16`）→
  `katrain/vision/camera.py:169` 在 `open()` 时把 v4l2 `exposure_auto` 由 3（自动）改成 1（手动）。
- 【读码】`CameraHubConfig.exposure` 默认 `None`（`camera_hub.py:17`）⇒ `camera.py:170-171`
  那个 `if self._exposure is not None` **从未成立** ⇒ `CAP_PROP_EXPOSURE` 一次都没被写过，
  曝光停在驱动 default。
- 【实测】板上 v4l2 读回：`exposure_absolute=166`、`gain=64`、`brightness=0` —— **三者都等于 driver default**；
  唯一被改过的控制是 `exposure_auto`（default=3 → value=1）。
- 【读码】本该接手的软件 AE 永不作动：board 模式传给 `VisionService` 的是 `CameraHub`
  （`katrain/web/server.py:546`），而 `CameraHub` **没有 `request_controls`**，于是
  `katrain/vision/worker_inprocess.py:233-236` 命中 `request is None` 分支，打印
  `AE: camera has no runtime controls — advisory mode only`。
- 【读码】`CameraManager` **有**完整的运行时控制 API：`request_controls`（`camera.py:261`）、
  `controls_effective`（`:270`）、`initial_exposure`（`:278`），由 reader 线程在
  `_apply_pending_controls`（`:282-300`）中应用，且带**回读校验**。这条路只是没被接上。

**后果**（【实测】，同一天同一台机器，只有天光在变；`bright` = `meter_brightness(warped).median`，目标带 `[120,170]`）：

| 时刻 | bright | YOLO 检出 |
|---|---|---|
| 01:30 前夜 | **1 (low)** 全黑 | 0 |
| 08:51 | 177 | 3–11 子，conf 0.44–0.73 |
| 09:41 | 221 | 9 子 |
| 09:43 | 231 | **0** |
| 10:35–11:14 | **254 (high)**，60% 像素 ≥250 | **0** |
| 手工 `v4l2-ctl -c exposure_auto=3` 之后 | **128–153 (ok)** | 恢复 |

> ⚠️ 反直觉的一点：`exposure_absolute` 166→10000（60×）**无效**，因为
> `exposure_auto_priority=0` 把积分时间钳在帧周期（≈33ms）内 —— **只能往下调不能往上调**。
> 反向扫描当场见效：exp=50 → median 161；gain=0 → 124；`exposure_auto=3` → 143。
> 「曝光控制是死的」这个判断是错的，别再据此下结论。

### 2.2 LED 几何标定：暗处能过，白天必挂 —— 症状 2 的根因

- 【读码】锚点定位 = **整幅 1920×1080 的（亮帧 − 暗帧）单通道差分里找最亮连通块**
  （`katrain/vision/led_geometry_calibrator.py:64-98`）。唯一信号门是 `peak >= 20`（`:74`），
  外加 `area >= 3`（`:81`）与 `margin(最强/次强) >= 1.3`（`:91`）。
  **没有 ROI、没有颜色判据、没有过曝/欠曝前置门。**
- 【读码】标定固定用 `(0,96,0)/(96,0,0)/(0,0,96)` 三色轮试（`:162-166`），
  而 REST `/led/points` 走的 `COLOR_RGB` 是 255 档（`katrain/web/core/led_service.py:52-61`）
  —— 标定的闪光只有测试页的 **96/255 ≈ 37.6%**。
- 【实测】01:32（漆黑）那次**成功**标定，逐锚点存在锁文件 `diag.attempts` 里：
  13/13 首色（绿）一次命中，`peak` **93.9 – 198.0**，中位 140.7，rms 2.43px，confidence 0.954。
- 【实测】白天（`bright≈153`，已开自动曝光）用**满亮度 `(0,255,0)`** 逐点重测：
  `peak` 只有 **18.2 – 74.1**；(18,0) 为 18.2 直接 `low_signal`；(15,9) 与 (18,0)
  两颗落到画面右上角眩光区的假位置（margin 仅 2.88 / 2.17）。
  折算到标定器真实的 96 档 ≈ **7 – 28**，而闸门是 20。
- 【实测】11:09 那次失败（`bright=254` 过曝）：13 个锚点全部「检测到」，但只有 (0,0) 是真的
  （偏 9.0px），其余 12 颗偏 299–1590px 且全部落在画面左暗边 `x∈[27,273]`；
  (9,3) 与 (9,9) 在棋盘上隔 6 格，检测结果却只差 **2.6px**。RANSAC 内点 4 < 9 ⇒ `not_enough_inliers`。
- 【读码】`fit_geometry_from_anchors` 需要 `min_inliers=9`（`:105`）、RANSAC 重投影阈值
  `max(2.0, spacing*0.25) = 13.18px`（`:119`）；`not_enough_inliers` 在 `:127` 产生。
- 【读码】**检测阶段全有全无**：`:197-200` 13 颗少 1 颗就当场 `anchor_not_found:{row},{col}` 中止 ⇒
  拟合阶段那份「允许 4 个外点」的余量永远用不上。

**灯是亮的。** 标定全程 `strict=True`（`led_geometry_calibrator.py:225/230`），
`led_service._submit` 的 strict 分支阻塞等固件 ACK（`led_service.py:226-233`）；SHOW 没 ACK 会走
`anchor_not_found` 而不是 `not_enough_inliers`。用户看不到灯，是因为屏上预览过曝成纯白 +
每颗只亮约 0.35 秒 + 亮度只有 37.6%。

> ⚠️ 日志里的 `[DIAG-LED] submit N leds` **证明不了灯发出去了** —— 那行在
> `led_service.py:224`，是 `_submit` 的第一行，在入队和串口写之前。

### 2.3 标定这一层是哑的

- 【读码】`led_geometry_calibrator._locate_anchor` 逐次把 `peak/area/margin/reason` 记进
  `attempts`（`:236-248`），但 `geometry_calibration_service.py:191-195` 在失败路径上
  **直接丢弃 `result.attempts`**，且 `metrics` 只在成功时填（`:205-209`）。
- 【实测】`katrain/web/core/geometry_calibration_service.py` 与
  `katrain/vision/led_geometry_calibrator.py` **一行日志都没有**：全 journal 2449 行里
  `geometry|calibrat|anchor|inlier` 命中 0（同管道 `DIAG-LED` 命中 135，过滤器有效）。

### 2.4 `pose_locked` 语义错位 —— 症状 4 的根因

- 【读码】`katrain/vision/worker_inprocess.py:468-470`：

  ```python
  pose_lock_status = "locked" if self._sync.state not in (SyncState.UNBOUND, SyncState.CALIBRATING) else "unlocked"
  ```

  ⇒ `pose_locked` 的真实含义是「**这一局绑上了没有**」，**完全由 `sync_state` 派生**，
  它无法表达「棋盘被挪了」。真正的棋盘位移走 `BOARD_LOST`，那时 `pose_locked` 仍报 **true**。
- 【读码】前端把它当「标定丢失」用：
  - `GamePage.tsx:406` `recalOpen = physicalPlay && !visionStatus.poseLocked && !isGameOver`
    → 弹琥珀色 `RecalibrationModal`，标题「**棋盘可能被移动**」。
  - `GamePage.tsx:423` `poseLocked === false` → 开关排显示「**标定丢失 · 请重新标定**」。
- 【读码】真正的「棋盘被挪」信号是 `geometryStatus.phase === 'degraded'` + `error === 'board_moved'`，
  由漂移监视器产生（`geometry_calibration_service.py:266-282`）。
  **对局屏没有任何弹窗接这个信号**（`VisionSyncOverlay` 里的 `degraded` 是另一回事：
  视觉同步事件的「检测质量下降，请检查光线」toast，`VisionSyncOverlay.tsx:64-68`）。

⇒ **这个弹窗为它自己那句文案所描述的情况永远不会触发；它只在「还没绑定」时误报一次。**

### 2.5 弹窗为什么会「自己消失」 —— 两条并列机制，都是真缺陷

【读码】`GamePage.tsx:621-629`：

```tsx
{physicalPlay && (
  <RecalibrationModal
    key={String(visionStatus.poseLocked)}
    open={recalOpen && !escalationOpen}
    onClose={() => undefined}     // "Intentionally inert"
  />
)}
```

**机制 α（语义错位自愈）**：进对局时未绑定 ⇒ `pose_locked=false` ⇒ 弹窗出现（**假警报**）；
绑定后离开 `CALIBRATING` ⇒ `pose_locked` 翻 true ⇒ 同一次提交里 `key` 由 `"false"` 变 `"true"`，
React **卸载**旧实例、挂载一个 `open=false` 的新实例 ⇒ **不播 MUI 退场动画，瞬间消失**。
此后 SYNCED/DEGRADED/BOARD_LOST/MISMATCH_WARNING 全报 `locked=true` ⇒ 本局内不再出现。
> 【推断】未在板上取证。取证方式：绑一局后连续 `curl /vision/status` 看 `pose_locked` 是否翻 true。
> 离开 `CALIBRATING` 有四个出口（`sync.py:171 / :249 / :305 / :406`），**四条都会翻 true**。

**机制 β（dismissed 闩）**：`RecalibrationModal.tsx:56` 把 MUI `Dialog` 的 `onClose` 绑到
`handleDismiss`（`:50-53`），而 MUI 在**点背景 / 按 Esc** 时都会触发 `onClose` ⇒ 置 `dismissed=true`；
父组件那个惰性 `onClose` 拦不住。触摸屏上一次误触盘外区域即关闭。
`dismissed` 是**本次实例内**的闩，复位只靠 `key` 翻值；白天 `pose_locked` 稳定 false ⇒
**这一局之内不会再出现**（跨挂载会复位）。

**判别**：弹窗消失后，「标定丢失 · 请重新标定」那句话**还在** ⇒ β（`poseLocked` 仍 false）；
**不在了** ⇒ α（已翻锁）。**两条都要修。**

【实测】板上 60+ 秒连续轮询（各 65 次）：`/vision/status` 与 `/geometry/status`
**一次没抖、0 失败**；后端 `enabled` 是 `self._config.enabled`（`vision/service.py:81`），
`_config` 只在构造时赋值 ⇒ **`isVisionEnabled` 在进程生命周期内是常量，不会抖**。

### 2.6 症状 3：对局屏确实没有常驻标定入口

- 【实测】`GamePage.tsx` 里 `calibrate` / `geometry` / `vision-setup` 命中数为 0；
  页级唯一图标键是「重置识别」（`:680-684`，走 `visionResetSync`，**不是标定**）。
- 【读码】全仓只有两处能到 `/kiosk/vision/setup`：设置屏（`SettingsPage.tsx:230`）与做题屏
  （`TsumegoProblemPage.tsx:465-469`）。板上构建产物同样只有这两处。
- 【读码】对局进行中，「退出对局」是唯一的导航出口，而它在未终局时**强制认输** ⇒
  「去重新标定」= 弃掉这盘棋，共 4 下点击。
- 【读码】`PhysicalBoardGuard.tsx:26-30` 的放行条件要求 `status.phase === 'ready'`。
  它**没有「只在进入时判一次」的闩**，几何相位一变就把整屏（连同正在进行的对局与
  RecalibrationModal）换成 `GeometryCalibrationScreen`。
  【实测】板上此刻 `phase="failed"`（用户 11:09 那几次失败留下的）而
  `session_calibrated=true`、`geometry_ready=true`、锁 confidence=0.954 完全有效 ⇒
  **现在只要选「实体盘」开局就会被标定台接管，压根到不了 GamePage。**
- 【读码】按弹窗里那颗「重新标定」在白天的实际后果**不是「没反应」**：
  `POST /geometry/calibrate` 立刻回 202 且 body 是 `phase='waiting_empty'` ⇒ `json()` 不抛 ⇒
  弹窗 `error` 保持 null、`busy` 立刻复位；真正的失败在后台线程里才写成 `'failed'`。
  可见后果是**整个对局屏在 ≤1 秒内被 PhysicalBoardGuard 换成标定台**。

### 2.7 `physicalPlay` 的唯一真实翻假路径

【读码】`GamePage.tsx:205-207`：

```tsx
const physicalPlay = isVisionEnabled && playOnBoard
  && (session.gameState?.board_size?.[0] ?? 19) === 19;
```

三个乘数里 `isVisionEnabled`（进程常量）与 `playOnBoard`（`:204` 挂载时读一次）在一局内恒定。
`?? 19` 在 19 路局里**不会**造成翻假 —— `:352` 有 `if (!session.gameState) return <CircularProgress/>` 早退，
到得了 `:621` 就说明 `gameState` 非空。
**但「9/13 路 + 偏好为实体盘」这个组合会让它从真翻假一次**，而没有任何代码阻止该组合发生
（偏好默认 `true`，选路数不写偏好，`PlayInputGuard` 不看路数）。

### 2.8 顺带确认的两条（不是缺陷）

- `COLOR_RGB["white"] = (0,255,0)`（`led_service.py:54`）：语义是**棋子颜色**不是灯颜色
  （白棋 → 绿灯）。主机侧无通道换序，GRB 重排在固件 FastLED 里。
- 「一次点 361 颗只亮约 200 颗」是**固件同亮上限**，不是供电下垂：
  `smartbox-hardware-design/debug/led_bring_up_pio/src/main.cpp:44` `#define MAX_ON 200`，
  `:136` 第 201 颗起回 `ERR maxon`。
  **但 `/led/points` 走 `strict=False`，`led_service.py:246` 在串口线程跑之前就返回 `ok:true`，
  那 161 条 ERR 被存进没人读的对象、一行日志都不打** —— 这是一条独立的状态不诚实缺陷。

### 2.9 现有测试的覆盖

【实测】`GamePage` 两份 + `PhysicalBoardGuard` **44/44 过**，15 个 vision 相关 spec **66/66 过**，
两次退出码均为 0（读的是 `${pipestatus[1]}`）。但：

- `GamePage.test.tsx` 里 `physicalPlay` 的三个输入在**任何单个测试内部从不翻转** ⇒
  结构上抓不到「`physicalPlay` 翻假导致卸载」。
- `poseLocked === undefined`、`visionStatus` 取数失败、Dialog backdrop 点击 —— **三档一档都没有测试**。
- `RecalibrationModal` **连自己的 spec 文件都不存在**。
- 后端 `tests/test_led_geometry_calibrator.py` 已有 `FakeLed` / `FakeCapture` /
  `_synthetic_camera_points()` 骨架（`:66-121`），新测试直接复用。

---

## 3. 要求（两份计划共同遵守）

### R1 硬规则

- **D2③：LED 绝不为几何标定自动闪灯。** 重新标定**只能**由用户触发。任何自动重标方案一律否决。
- 生产代码不得残留模拟业务数据；状态必须诚实 —— 加载中、错误、空态不得伪装成成功。
- 不得破坏现有 44/44 + 66/66 测试。

### R2 判据必须落在下游结果上

- 「命令发出去了」不算数，要「固件 ACK 了」或「下游状态变了」。
- jsdom 无布局引擎、MUI 过渡行为与真浏览器不同 ⇒
  **凡结论是「真浏览器里的挂载时序/动画表现」的，jsdom 测试无权作证**，
  必须在板上用 CDP 复核（配方见 `project_board_kiosk_cdp_acceptance`）。

### R3 部署现实

- 板上 `/root/smartbox-software` **不是 git 仓库**，是 rsync 副本。
- `vendor/katrain` 是子模块，`git archive` **带不走它**；前端产物 `static-kiosk-2d/` 是 gitignored，
  要单独 `npm run build:smartbox-kiosk-2d` + `rsync --delete`。
- 前端改动上板后必须 CDP `Page.reload(ignoreCache=True)`，否则 kiosk 拿的还是旧包
  （`StaticFiles` 不发 `Cache-Control`）。
- 板上 2GB 内存互斥：起围棋前先停别的棋类，验完还原。

### R4 环境前提（写进用户可见文案）

LED 几何标定依赖「LED 亮度 > 环境光在盘面上的反射」。当前硬件在**明亮日光**下无法满足。
计划要做的是把这条约束**变成可见、可诊断、可缓解**的，而不是假装它不存在。

---

## 4. 不在范围内

- 换摄像头模组 / 加补光灯 / 改 PCB —— 硬件方案另议。
- 把 YOLO 模型重训到能在过曝下工作。
- `MAX_ON=200` 的固件改动（属 `smartbox-hardware-design` 仓）；本计划只修**主机侧把 `ERR maxon` 吞掉**这一半。
