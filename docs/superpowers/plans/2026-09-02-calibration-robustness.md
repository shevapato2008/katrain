# 实体棋盘标定健壮性 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让摄像头曝光跟随环境光，让 LED 几何标定在失败时说得出为什么、在部分锚点看不见时仍能完成。

**Architecture:** 四层各补一处。①把已经写好但没接线的软件 AE 接上（`CameraHub` 转发三个成员给 `CameraManager`）。②标定入口加一道曝光闸，过曝/欠曝当场拒绝并说清楚。③锚点定位从「整幅找最亮团」改成「四角全画幅 → 用四角单应预测九星 ROI」。④检测阶段从全有全无改成容缺，把拟合阶段本来就有的 4 个外点余量释放出来。全程把 `attempts` 的诊断落到日志和 API。

**Tech Stack:** Python 3.11 / OpenCV 4.11 / numpy 1.26 / pytest；目标硬件 RK3562 + HBV UVC 摄像头 + ESP32-S3 驱动的 19×19 WS2812。

**Spec:** `docs/superpowers/plans/2026-09-02-physical-board-spec.md`

## Global Constraints

- 仓库 `vendor/katrain`（子模块）。分支从 `develop` 切出。
- **D2③ 硬规则：LED 绝不为几何标定自动闪灯。** 本计划不新增任何自动重标路径。
- 不得破坏现有测试：`pytest tests/test_led_geometry_calibrator.py tests/test_geometry_calibration_service.py tests/test_camera_hub.py tests/test_vision/` 当前全绿。
- 现有测试骨架直接复用：`tests/test_led_geometry_calibrator.py:66-121` 的 `FakeLed` / `FakeCapture` / `_synthetic_camera_points()`；`tests/test_camera_hub.py:5-27` 的 `FakeCamera`。
- 阈值常量一律**具名**并写进模块顶部，禁止行内魔数。
- 每个任务结束提交一次，commit message 前缀 `fix(vision):` 或 `feat(vision):`。

---

### Task 1: CameraHub 转发运行时相机控制

把 `CameraManager` 已有的曝光控制 API 透过 `CameraHub` 暴露出去，让 `worker_inprocess._run_ae` 不再落进 advisory 分支。

**Files:**
- Modify: `katrain/web/core/camera_hub.py`（在 `grab_burst` 之后追加）
- Test: `tests/test_camera_hub.py`

**Interfaces:**
- Produces: `CameraHub.request_controls(exposure: float | None = None, auto_exposure: float | None = None) -> None`、`CameraHub.controls_effective -> bool | None`、`CameraHub.initial_exposure -> float | None`。三者签名与 `CameraManager`（`katrain/vision/camera.py:261/270/278`）一致，`worker_inprocess.py:222/229/233` 靠 `getattr` 发现它们。

- [ ] **Step 1: 写失败测试**

追加到 `tests/test_camera_hub.py` 末尾：

```python
class ControlCamera(FakeCamera):
    def __init__(self):
        super().__init__()
        self.control_calls = []
        self.controls_effective = True
        self.initial_exposure = 166.0

    def request_controls(self, exposure=None, auto_exposure=None):
        self.control_calls.append((exposure, auto_exposure))


def test_camera_hub_forwards_runtime_controls_to_the_camera():
    camera = ControlCamera()
    hub = CameraHub(CameraHubConfig(device_id=0), camera=camera)
    hub.start()

    hub.request_controls(exposure=120.0, auto_exposure=0.25)

    assert camera.control_calls == [(120.0, 0.25)]
    assert hub.controls_effective is True
    assert hub.initial_exposure == 166.0


def test_camera_hub_controls_are_inert_before_start():
    hub = CameraHub(CameraHubConfig(device_id=0), camera=None)

    hub.request_controls(exposure=120.0)

    assert hub.controls_effective is None
    assert hub.initial_exposure is None
```

- [ ] **Step 2: 跑测试确认它红**

Run: `pytest tests/test_camera_hub.py -k runtime_controls -v`
Expected: FAIL —— `AttributeError: 'CameraHub' object has no attribute 'request_controls'`

- [ ] **Step 3: 实现**

在 `katrain/web/core/camera_hub.py` 的 `grab_burst` 方法之后追加：

```python
    # -- runtime camera controls (software AE) ------------------------------- #
    # worker_inprocess._run_ae 通过 getattr 发现这三个成员;缺任何一个都会让软件 AE
    # 永久落进 advisory 模式(见 worker_inprocess.py:222/229/233)。CameraHub 是
    # board 模式下真正传给 VisionService 的对象(server.py:546),所以转发必须在这里。

    def request_controls(self, exposure: float | None = None, auto_exposure: float | None = None) -> None:
        if self._camera is None:
            return
        self._camera.request_controls(exposure=exposure, auto_exposure=auto_exposure)

    @property
    def controls_effective(self) -> bool | None:
        return getattr(self._camera, "controls_effective", None) if self._camera is not None else None

    @property
    def initial_exposure(self) -> float | None:
        return getattr(self._camera, "initial_exposure", None) if self._camera is not None else None
```

- [ ] **Step 4: 跑测试确认它绿**

Run: `pytest tests/test_camera_hub.py -v`
Expected: PASS（含原有用例）

- [ ] **Step 5: 变异验证 —— 证明这条闸真的钉住了行为**

把 `request_controls` 的转发那一行改成 `return`，重跑 Step 4，**必须变红**；红了再改回来。
判据：红的是 `test_camera_hub_forwards_runtime_controls_to_the_camera`，不是别的用例。

- [ ] **Step 6: 提交**

```bash
git add katrain/web/core/camera_hub.py tests/test_camera_hub.py
git commit -m "fix(vision): CameraHub 转发运行时曝光控制,软件 AE 不再永久 advisory"
```

- [ ] **Step 7: 板上验收（这一步不能用 jsdom/单测顶替）**

前提：板上已 rsync 本次改动并 `systemctl restart smartbox-katrain`。

```bash
ssh rk3562-direct 'journalctl -u smartbox-katrain -b --no-pager | grep -i "AE:" | head -5'
```

Expected：**不再出现** `AE: camera has no runtime controls — advisory mode only`。
若出现 `AE: exposure controls ineffective on this platform — advisory mode only`，
说明 `controls_effective` 回读为 False —— 那是 HBV 模组的真实能力问题，记录下来，
**不要**为了让日志好看去删那条分支。

再看亮度是否进带：

```bash
ssh rk3562-direct 'journalctl -u smartbox-katrain --since "-3min" --no-pager | grep worker_inprocess | tail -5'
```

Expected：`bright=` 落在 `[120,170]` 且尾注为 `(ok)`。

---

### Task 2: 标定诊断落地（日志 + 失败 status）

`attempts` 已经算出来了，只是被丢掉。先补这一层 —— 后面每个任务的验收都要靠它。

**Files:**
- Modify: `katrain/vision/led_geometry_calibrator.py`（模块顶部加 logger；`_locate_anchor` 每次 attempt 后打一行）
- Modify: `katrain/web/core/geometry_calibration_service.py:191-198`（失败路径保留 attempts）
- Test: `tests/test_geometry_calibration_service.py`

**Interfaces:**
- Consumes: `CalibrationResult.attempts: tuple[dict, ...]`（已存在，`led_geometry_calibrator.py:61`）。
- Produces: `GET /api/v1/geometry/status` 在 `phase == 'failed'` 时 `metrics` 含 `attempts: list[dict]`，每项键为 `row/col/color/ok/peak/area/margin/reason`。前端计划（`2026-09-02-ingame-calibration-recovery.md` Task 4）消费它。

- [ ] **Step 1: 写失败测试**

追加到 `tests/test_geometry_calibration_service.py`：

```python
def test_failed_calibration_keeps_attempts_in_metrics():
    """失败时 attempts 必须留在 status 里 —— 它是唯一能分辨 low_signal /
    ambiguous_blobs / show_failed 的东西(见 spec §2.3)。"""
    led, capture = FakeLed(), FreshFakeCapture()
    attempts = ({"row": 0, "col": 0, "color": "green", "ok": False, "peak": 8.1,
                 "area": 0, "margin": None, "reason": "low_signal"},)

    class FailingCalibrator:
        def __init__(self, **_kwargs):
            pass

        def calibrate(self):
            return CalibrationResult(ok=False, reason="anchor_not_found:0,0", attempts=attempts)

    service = GeometryCalibrationService(
        led=led, capture=capture, calibrator_factory=FailingCalibrator, save_path="/tmp/unused.npz",
    )
    service.start(trigger="manual", empty_confirmed=True)
    service.wait(5)

    status = service.status()
    assert status["phase"] == "failed"
    assert status["error"] == "anchor_not_found:0,0"
    assert status["metrics"]["attempts"] == [dict(attempts[0])]
```

> ⚠️ `GeometryCalibrationService` 的构造签名以仓库当前实现为准；照 `tests/test_geometry_calibration_service.py` 里已有用例的构造方式抄，不要凭这段示例猜参数名。

- [ ] **Step 2: 跑测试确认它红**

Run: `pytest tests/test_geometry_calibration_service.py -k attempts -v`
Expected: FAIL —— `KeyError: 'attempts'`

- [ ] **Step 3: 实现（两处）**

`katrain/vision/led_geometry_calibrator.py` 模块顶部（import 之后）加：

```python
import logging

logger = logging.getLogger(__name__)
```

`_locate_anchor` 里 `attempts.append({...})` 之后立刻加：

```python
            logger.info(
                "geometry anchor (%d,%d) %s: ok=%s peak=%.1f area=%s margin=%s reason=%s",
                row, col, color_name, result.ok, result.peak, result.area, result.margin, result.reason,
            )
```

`katrain/web/core/geometry_calibration_service.py` 的失败分支（当前 `:194-198`）改成：

```python
            if not result.ok or result.lock is None:
                with self._lock:
                    self._status["phase"] = "failed"
                    self._status["error"] = result.reason or "calibration_failed"
                    # 失败诊断是这一层唯一的可观测出口 —— 丢掉它,任何人都分不清
                    # low_signal / ambiguous_blobs / show_failed(见 spec §2.3)。
                    self._status["metrics"] = {"attempts": [dict(a) for a in result.attempts]}
                return
```

- [ ] **Step 4: 跑测试确认它绿**

Run: `pytest tests/test_geometry_calibration_service.py -v`
Expected: PASS

- [ ] **Step 5: 变异验证**

把 `self._status["metrics"] = {...}` 那行删掉，重跑 —— 必须红在新用例上；红了改回来。

- [ ] **Step 6: 提交**

```bash
git add katrain/vision/led_geometry_calibrator.py katrain/web/core/geometry_calibration_service.py tests/test_geometry_calibration_service.py
git commit -m "feat(vision): 标定失败时保留逐锚点诊断(日志 + status.metrics.attempts)"
```

- [ ] **Step 7: 板上验收**

在**明亮环境**下从设置屏点一次「重新开始标定」（这一步必须人触发，D2③），然后：

```bash
ssh rk3562-direct 'journalctl -u smartbox-katrain --since "-3min" --no-pager | grep "geometry anchor" | head -20'
ssh rk3562-direct 'curl -s http://127.0.0.1:8081/api/v1/geometry/status | python3 -m json.tool | head -40'
```

Expected：日志出现 13 行以内的 `geometry anchor (r,c) green: ok=... peak=...`；
status 的 `metrics.attempts` 非空。**这一步之前 journal 里这类行命中数是 0**（spec §2.3），
所以「有输出」本身就是这个任务的验收。

---

### Task 3: 标定前的曝光闸

过曝时差分恒为 0，检测器必然在噪声里游走（spec §2.2）。与其让它跑完 13 颗再报一个误导性的 `not_enough_inliers`，不如在第一颗之前就拒绝，并说清楚是环境问题。

**Files:**
- Modify: `katrain/vision/led_geometry_calibrator.py`（新增 `check_frame_exposure`；`calibrate()` 开头调用）
- Test: `tests/test_led_geometry_calibrator.py`

**Interfaces:**
- Consumes: `katrain.vision.auto_exposure.meter_brightness(warped, margin_cells=1.0, grid_size=19) -> BrightnessStats(median, clip_frac, shadow_frac)`（`katrain/vision/auto_exposure.py:34`）。
  ⚠️ 它是为**已 warp 的方形盘面**写的；标定阶段还没有几何，只有原始帧。因此这里**不复用它**，改用整帧灰度中位数 + 削顶比例，常量独立命名。
- Produces: `CalibrationResult.reason` 新增两个取值 `frame_overexposed` / `frame_underexposed`。
  **前端必须为这两个值各准备一条文案**（见前端计划 Task 4）—— 契约要求「声明的取值要有人产生、产生的取值要有人消费」。

- [ ] **Step 1: 写失败测试**

追加到 `tests/test_led_geometry_calibrator.py`：

```python
from katrain.vision.led_geometry_calibrator import check_frame_exposure


def test_check_frame_exposure_rejects_blown_out_frame():
    frame = np.full((480, 640, 3), 253, np.uint8)

    ok, reason, stats = check_frame_exposure(frame)

    assert ok is False
    assert reason == "frame_overexposed"
    assert stats["median"] == pytest.approx(253, abs=1)
    assert stats["clip_frac"] > 0.5


def test_check_frame_exposure_rejects_black_frame():
    frame = np.full((480, 640, 3), 2, np.uint8)

    ok, reason, _stats = check_frame_exposure(frame)

    assert ok is False
    assert reason == "frame_underexposed"


def test_check_frame_exposure_accepts_the_band_that_worked_in_the_dark():
    # 01:32 那次成功标定时盘面中位 ≈150(spec §2.1 表)。
    frame = np.full((480, 640, 3), 150, np.uint8)

    ok, reason, _stats = check_frame_exposure(frame)

    assert ok is True
    assert reason is None


def test_calibrate_fails_fast_on_overexposed_frame_without_flashing_any_led():
    led = FakeLed()
    capture = FakeCapture(led, _synthetic_camera_points())
    capture._frame = lambda: np.full((900, 1000, 3), 253, np.uint8)

    result = LedGeometryCalibrator(led=led, capture=capture).calibrate()

    assert result.ok is False
    assert result.reason == "frame_overexposed"
    # D2③ + 用户体验:环境不行的时候不要先闪 13 颗灯再说不行。
    assert led.attempts == []
```

- [ ] **Step 2: 跑测试确认它红**

Run: `pytest tests/test_led_geometry_calibrator.py -k exposure -v`
Expected: FAIL —— `ImportError: cannot import name 'check_frame_exposure'`

- [ ] **Step 3: 实现**

`katrain/vision/led_geometry_calibrator.py` 模块顶部常量区加：

```python
# 标定入口的曝光闸。判据来自 spec §2.2 的实测:
#   01:32 暗处成功那次盘面中位 ≈150、逐锚点 peak 94-198;
#   白天 bright=254(60% 像素 ≥250)时 13 颗里 12 颗定位到噪声。
# 这两个数不是审美偏好,是「亮减暗差分还剩不剩信号」的边界。
EXPOSURE_MEDIAN_MAX = 245.0   # 高于此:盘面接近削顶,lit-dark 差分趋近 0
EXPOSURE_MEDIAN_MIN = 20.0    # 低于此:整帧欠曝,LED 之外什么都看不见
EXPOSURE_CLIP_FRAC_MAX = 0.35  # >=250 的像素占比上限
```

在 `detect_led_centroid` 之前加：

```python
def check_frame_exposure(frame: np.ndarray) -> tuple[bool, str | None, dict]:
    """标定入口的曝光闸:过曝时 lit-dark 差分恒为 0,检测器只会在噪声里游走。

    量的是**原始整帧**而不是 warp 后的盘面 —— 标定阶段还没有几何可用,
    auto_exposure.meter_brightness 那条路在这里走不通。"""
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if frame.ndim == 3 else frame
    small = gray[::4, ::4]
    stats = {
        "median": float(np.median(small)),
        "clip_frac": float((small >= 250).mean()),
        "shadow_frac": float((small <= 10).mean()),
    }
    if stats["median"] >= EXPOSURE_MEDIAN_MAX or stats["clip_frac"] >= EXPOSURE_CLIP_FRAC_MAX:
        return False, "frame_overexposed", stats
    if stats["median"] <= EXPOSURE_MEDIAN_MIN:
        return False, "frame_underexposed", stats
    return True, None, stats
```

在 `LedGeometryCalibrator.calibrate()` 的 `try:` 之后、`total = len(CALIBRATION_ANCHORS)` 之前插入：

```python
            probe, _seq, _ts = self.capture.grab_fresh(settle_ms=0.0)
            if probe is None:
                return CalibrationResult(ok=False, reason="no_frames")
            ok, reason, stats = check_frame_exposure(probe)
            logger.info(
                "geometry exposure gate: ok=%s reason=%s median=%.0f clip=%.3f",
                ok, reason, stats["median"], stats["clip_frac"],
            )
            if not ok:
                return CalibrationResult(ok=False, reason=reason, attempts=({"exposure": stats},))
```

- [ ] **Step 4: 跑测试确认它绿**

Run: `pytest tests/test_led_geometry_calibrator.py -v`
Expected: PASS（含原有全部用例 —— `FakeCapture._frame` 返回的是灰度 90 的帧，落在带内）

- [ ] **Step 5: 契约闸 —— 新增的取值必须有人消费**

Run: `grep -rn "frame_overexposed\|frame_underexposed" katrain/web/ui/src | grep -v __tests__`
Expected: 现在为空。**这是预期的**——它由前端计划 Task 4 补上。
把这条写进本任务的提交信息，别让它变成一个没人认领的取值（见 `feedback_declared_value_needs_a_producer`）。

- [ ] **Step 6: 提交**

```bash
git add katrain/vision/led_geometry_calibrator.py tests/test_led_geometry_calibrator.py
git commit -m "feat(vision): 标定入口加曝光闸,过曝/欠曝当场拒绝且不闪灯

新增 reason 取值 frame_overexposed / frame_underexposed,
消费方在 2026-09-02-ingame-calibration-recovery.md Task 4。"
```

---

### Task 4: 自适应闪光亮度

标定固定用 96/255，暗处 peak 94-198（充裕），白天折算约 7-28（不够）。直接提到 255 会让暗处削顶、质心被拉偏，所以**先试 96，只在 `low_signal` 时对同一颗重试 255**。

**Files:**
- Modify: `katrain/vision/led_geometry_calibrator.py`（`COLOR_ATTEMPTS` 结构 + `_locate_anchor` 重试）
- Test: `tests/test_led_geometry_calibrator.py`

**Interfaces:**
- Produces: `attempts` 每项新增 `level: int` 键（96 或 255）。Task 2 已把 attempts 透出到 status，前端按原样展示即可，不需要新契约。

- [ ] **Step 1: 写失败测试**

```python
def test_locate_anchor_retries_at_full_brightness_when_signal_is_weak():
    """白天 96 档折算 peak≈7-28、闸是 20(spec §2.2)。弱信号必须换满亮度再试一次,
    而不是直接判 anchor_not_found。"""
    led = FakeLed()
    points = _synthetic_camera_points()

    class DimCapture(FakeCapture):
        def _frame(self):
            frame = np.full((900, 1000, 3), 150, np.uint8)
            if self.led.current is not None:
                x, y = self.camera_points[self.led.current]
                # 96 档在这个场景下只抬 8 个灰阶(低于 peak>=20 的闸);255 档抬 40。
                lift = 40 if max(self.led.rgb) == 255 else 8
                cv2.circle(frame, (round(x), round(y)), 8, (0, 150 + lift, 0), -1)
            return frame

    capture = DimCapture(led, points)
    result = LedGeometryCalibrator(led=led, capture=capture).calibrate()

    assert result.ok is True
    levels = [a.get("level") for a in result.attempts if a.get("ok")]
    assert levels and all(level == 255 for level in levels)
    assert any(a["reason"] == "low_signal" and a["level"] == 96 for a in result.attempts)


def test_dark_room_still_succeeds_at_the_dim_level_only():
    """暗处 96 档就够(peak 94-198),不许无谓地把灯拉满 —— 削顶会把质心拉偏。"""
    led = FakeLed()
    capture = FakeCapture(led, _synthetic_camera_points())

    result = LedGeometryCalibrator(led=led, capture=capture).calibrate()

    assert result.ok is True
    assert all(a["level"] == 96 for a in result.attempts if a.get("ok"))
```

- [ ] **Step 2: 跑测试确认它红**

Run: `pytest tests/test_led_geometry_calibrator.py -k brightness -v`
Expected: FAIL —— `KeyError: 'level'` 或 `assert result.ok is True` 失败

- [ ] **Step 3: 实现**

把 `COLOR_ATTEMPTS`（当前 `:162-166`）改成只描述通道与颜色名，亮度另立一档：

```python
    # (通道, 颜色名) —— 亮度由 FLASH_LEVELS 决定,不再写死在 RGB 里。
    COLOR_CHANNELS = ((1, "green"), (2, "red"), (0, "blue"))
    # 先暗后亮:暗处 96 档 peak 94-198 已充裕且不削顶;只在 low_signal 时才拉满。
    FLASH_LEVELS = (96, 255)

    @staticmethod
    def _rgb_for(channel: int, level: int) -> tuple[int, int, int]:
        """channel 用的是 BGR 序(detect_led_centroid 的 channel 参数),SETI 要 RGB。"""
        rgb = [0, 0, 0]
        rgb[{0: 2, 1: 1, 2: 0}[channel]] = level
        return tuple(rgb)
```

`_locate_anchor` 的循环改成双层，内层按亮度重试；**只有 `low_signal` 才升亮度**，
`ambiguous_blobs` 升亮度只会让噪声一起变亮，没有意义：

```python
    def _locate_anchor(self, row: int, col: int, attempts: list[dict]):
        for channel, color_name in self.COLOR_CHANNELS:
            for level in self.FLASH_LEVELS:
                if self.cancel_event.is_set():
                    return None
                cleared = self.led.clear(strict=True)
                if not cleared.get("ok"):
                    attempts.append({"row": row, "col": col, "color": color_name,
                                     "level": level, "reason": "clear_failed"})
                    break
                dark, _seq, _ts = self.capture.grab_fresh(
                    after_ts=cleared.get("shown_at"), settle_ms=self.settle_ms)
                shown = self.led.set_rgb_points(
                    [{"row": row, "col": col, "rgb": self._rgb_for(channel, level)}], strict=True)
                if not shown.get("ok"):
                    attempts.append({"row": row, "col": col, "color": color_name,
                                     "level": level, "reason": "show_failed"})
                    break
                lit, _seq, _ts = self.capture.grab_fresh(
                    after_ts=shown.get("shown_at"), settle_ms=self.settle_ms)
                if dark is None or lit is None:
                    attempts.append({"row": row, "col": col, "color": color_name,
                                     "level": level, "reason": "no_frame"})
                    break
                result = detect_led_centroid(dark, lit, channel=channel)
                attempts.append({
                    "row": row, "col": col, "color": color_name, "level": level,
                    "ok": result.ok, "peak": result.peak, "area": result.area,
                    "margin": result.margin, "reason": result.reason,
                })
                logger.info(
                    "geometry anchor (%d,%d) %s@%d: ok=%s peak=%.1f area=%s margin=%s reason=%s",
                    row, col, color_name, level, result.ok, result.peak,
                    result.area, result.margin, result.reason,
                )
                if result.ok:
                    point = (float(result.centroid[0]), float(result.centroid[1]))
                    self.anchor_observer(row, col, point, color_name)
                    return result.centroid
                if result.reason != "low_signal":
                    break  # 只有信号弱才值得升亮度
        return None
```

> Task 2 里加的那行 `logger.info` 被这一段取代（多了 `@level`）。删掉旧的那一行，别留两处。

- [ ] **Step 4: 跑测试确认它绿**

Run: `pytest tests/test_led_geometry_calibrator.py -v`
Expected: PASS

- [ ] **Step 5: 变异验证 —— 要红得对**

把 `FLASH_LEVELS` 改成 `(96,)`，重跑：`test_locate_anchor_retries_at_full_brightness_when_signal_is_weak` **必须红**，
`test_dark_room_still_succeeds_at_the_dim_level_only` **必须仍绿**。两条都对上了再改回来。

- [ ] **Step 6: 提交**

```bash
git add katrain/vision/led_geometry_calibrator.py tests/test_led_geometry_calibrator.py
git commit -m "feat(vision): 标定闪光自适应亮度,弱信号时对同一锚点重试满亮度"
```

---

### Task 5: 锚点搜索 ROI 化

`detect_led_centroid` 在整幅 1920×1080 里找最亮团，而 `peak>=20` 这个闸是照小窗口定的。实测白天有两颗锚点被右上角眩光区抢走（spec §2.2）。四角没有先验只能全画幅找；九星有 —— 四角一确定，单应就能把它们的位置预测到一格以内。

**Files:**
- Modify: `katrain/vision/led_geometry_calibrator.py`（`detect_led_centroid` 加 `roi` 参数；`calibrate()` 两遍走）
- Test: `tests/test_led_geometry_calibrator.py`

**Interfaces:**
- Consumes: `CALIBRATION_ANCHORS`（`:16-30`，前 4 项即四角，顺序 `(0,0) (0,18) (18,18) (18,0)`）。
- Produces: `detect_led_centroid(dark, lit, *, channel, roi=None)`，`roi = (cx, cy, radius_px)` 或 `None`。
  `_locate_anchor(row, col, attempts, roi=None)` 增加同名关键字参数。

- [ ] **Step 1: 写失败测试**

```python
def test_detect_led_centroid_ignores_a_brighter_blob_outside_the_roi():
    """白天实测:(15,9) 被画面右上角眩光抢走,报到 (1807,142) 而真值在 (1286,629)。
    ROI 内没有更亮的东西时,ROI 外再亮也不许赢。"""
    dark = np.full((900, 1000, 3), 120, np.uint8)
    lit = dark.copy()
    cv2.circle(lit, (300, 400), 8, (120, 170, 120), -1)   # 真 LED:抬 50
    cv2.circle(lit, (900, 80), 20, (120, 240, 120), -1)   # 眩光:抬 120,更亮更大

    without_roi = detect_led_centroid(dark, lit, channel=1)
    with_roi = detect_led_centroid(dark, lit, channel=1, roi=(300.0, 400.0, 60.0))

    assert without_roi.centroid == pytest.approx((900, 80), abs=3.0)   # 现状:被抢走
    assert with_roi.ok is True
    assert with_roi.centroid == pytest.approx((300, 400), abs=2.0)


def test_calibrate_uses_corner_homography_to_roi_the_star_points():
    led = FakeLed()
    points = _synthetic_camera_points()

    class GlareCapture(FakeCapture):
        def _frame(self):
            frame = super()._frame()
            # 常驻的一块「更亮的假货」,位置固定在角落,任何锚点的 ROI 都够不到它。
            cv2.circle(frame, (970, 20), 18, (255, 255, 255), -1)
            return frame

    capture = GlareCapture(led, points)
    result = LedGeometryCalibrator(led=led, capture=capture).calibrate()

    assert result.ok is True
    assert result.lock is not None
    # 九星必须落回它们真正的位置,而不是那块假货。
    for (row, col), got in zip(CALIBRATION_ANCHORS[4:], result.lock.diag["anchors"][4:]):
        want = points[(row, col)]
        assert (got["camera"][0], got["camera"][1]) == pytest.approx(tuple(want), abs=3.0)
```

> ⚠️ `result.lock.diag["anchors"]` 的结构以 `_build_lock`（`led_geometry_calibrator.py:257-305`）当前实现为准；若键名不同，照实现改测试，别改实现去迁就测试。

- [ ] **Step 2: 跑测试确认它红**

Run: `pytest tests/test_led_geometry_calibrator.py -k roi -v`
Expected: FAIL —— `TypeError: detect_led_centroid() got an unexpected keyword argument 'roi'`

- [ ] **Step 3: 实现（三处）**

① `detect_led_centroid` 签名与 blur 之后加 ROI 掩码：

```python
def detect_led_centroid(
    dark: np.ndarray, lit: np.ndarray, *, channel: int, roi: tuple[float, float, float] | None = None
) -> LedCentroidResult:
    """Find the dominant positive light blob in a lit-minus-dark frame.

    ``roi`` = (cx, cy, radius_px)。给了就只在这个圆内找 —— peak>=20 这个闸是照
    73x73 的小窗口定的,用在整幅 1920x1080 上等于「找画面里最亮的噪声团」(spec §2.2)。"""
    if dark.shape != lit.shape or dark.ndim != 3:
        return LedCentroidResult(ok=False, reason="shape_mismatch")
    delta = lit[..., channel].astype(np.float32) - dark[..., channel].astype(np.float32)
    delta = cv2.GaussianBlur(delta, (5, 5), 0)
    if roi is not None:
        cx, cy, radius = roi
        keep = np.zeros(delta.shape, np.uint8)
        cv2.circle(keep, (int(round(cx)), int(round(cy))), max(1, int(round(radius))), 1, -1)
        delta = np.where(keep.astype(bool), delta, 0.0)
    peak = float(delta.max(initial=0.0))
    ...  # 以下不变
```

② 模块级新增 ROI 预测：

```python
ROI_CELLS = 1.5  # ROI 半径 = 1.5 个格距。棋盘不会在一次标定里移动超过这个量级。
ROI_RADIUS_MIN_PX = 24.0


def predict_anchor_roi(homography: np.ndarray, row: int, col: int) -> tuple[float, float, float]:
    """用四角拟出的临时单应预测某锚点的像素位置,半径按**该处局部**格距算 ——
    透视下近端格子比远端大,用全局常数会在一端过紧、另一端过松。"""
    here = cv2.perspectiveTransform(np.array([[[float(col), float(row)]]], np.float32), homography)[0][0]
    diag = cv2.perspectiveTransform(
        np.array([[[float(col) + 1.0, float(row) + 1.0]]], np.float32), homography)[0][0]
    local_cell = float(np.hypot(diag[0] - here[0], diag[1] - here[1])) / float(np.sqrt(2.0))
    return float(here[0]), float(here[1]), max(ROI_RADIUS_MIN_PX, ROI_CELLS * local_cell)
```

③ `calibrate()` 改成两遍：前 4 颗（四角）全画幅，随后用 `cv2.getPerspectiveTransform` 求临时单应，后 9 颗带 ROI：

```python
            corner_h = None
            for index, (row, col) in enumerate(CALIBRATION_ANCHORS, start=1):
                if self.cancel_event.is_set():
                    return CalibrationResult(ok=False, reason="cancelled", attempts=tuple(attempts))
                phase = "flashing_corners" if index <= 4 else "verifying"
                self.progress(phase, index - 1, total)
                roi = predict_anchor_roi(corner_h, row, col) if corner_h is not None else None
                centroid = self._locate_anchor(row, col, attempts, roi=roi)
                if centroid is None:
                    return CalibrationResult(ok=False, reason=f"anchor_not_found:{row},{col}",
                                             attempts=tuple(attempts))
                detected.append(((row, col), centroid))
                if index == 4:
                    # CALIBRATION_ANCHORS[:4] 是四角,顺序 (0,0)(0,18)(18,18)(18,0)。
                    src = np.array([[float(c), float(r)] for (r, c) in CALIBRATION_ANCHORS[:4]], np.float32)
                    dst = np.array([p for _anchor, p in detected[:4]], np.float32)
                    corner_h = cv2.getPerspectiveTransform(src, dst)
```

- [ ] **Step 4: 跑测试确认它绿**

Run: `pytest tests/test_led_geometry_calibrator.py -v`
Expected: PASS

- [ ] **Step 5: 变异验证 —— 到达性**

在 `predict_anchor_roi` 第一行加 `raise AssertionError("unreachable")`，重跑：
`test_calibrate_uses_corner_homography_to_roi_the_star_points` **必须红**。
红了说明这条路真的被走到了（不是被短路绕过），改回来。

- [ ] **Step 6: 提交**

```bash
git add katrain/vision/led_geometry_calibrator.py tests/test_led_geometry_calibrator.py
git commit -m "fix(vision): 九星锚点改用四角单应预测的 ROI 搜索,不再被画面别处的强光抢走"
```

- [ ] **Step 7: 板上验收**

在**明亮**环境下人工触发一次标定，读 Task 2 落地的日志：

```bash
ssh rk3562-direct 'journalctl -u smartbox-katrain --since "-5min" --no-pager | grep "geometry anchor"'
```

Expected：九星那 9 行的 `peak` 与四角同量级；**不再出现**「两颗锚点的检测坐标彼此只差几个像素」
这种长相（spec §2.2 里 (9,3) 与 (9,9) 只差 2.6px 是旧行为的指纹）。

---

### Task 6: 检测阶段容缺

拟合阶段允许 13 个里有 4 个外点（`min_inliers=9`），但检测阶段少 1 颗就中止 —— 那份余量永远用不上（spec §2.2）。

**Files:**
- Modify: `katrain/vision/led_geometry_calibrator.py`（`calibrate()` 的中止条件）
- Test: `tests/test_led_geometry_calibrator.py`

**Interfaces:**
- Produces: `CalibrationResult.reason` 新增 `too_few_anchors`（定位成功数 < `MIN_LOCATED_ANCHORS`）。
  `anchor_not_found:{row},{col}` **保留**给「一颗都没找到就该停」以外的场景不再产生 —— 前端已有的那条文案改指 `too_few_anchors`（前端计划 Task 4）。

- [ ] **Step 1: 写失败测试**

```python
def test_calibrate_tolerates_up_to_four_missing_anchors():
    """min_inliers=9 已经允许 13 个里有 4 个外点;检测阶段不该比拟合阶段更严。"""
    led = FakeLed()
    points = _synthetic_camera_points()
    invisible = {(3, 3), (9, 15)}

    class PartialCapture(FakeCapture):
        def _frame(self):
            if self.led.current in invisible:
                return np.full((900, 1000, 3), 90, np.uint8)  # 这两颗任何颜色都看不见
            return super()._frame()

    result = LedGeometryCalibrator(led=led, capture=PartialCapture(led, points)).calibrate()

    assert result.ok is True
    assert result.lock is not None


def test_calibrate_stops_when_too_few_anchors_are_located():
    led = FakeLed()
    points = _synthetic_camera_points()
    visible = {(0, 0), (0, 18), (18, 18), (18, 0)}

    class MostlyBlindCapture(FakeCapture):
        def _frame(self):
            if self.led.current not in visible:
                return np.full((900, 1000, 3), 90, np.uint8)
            return super()._frame()

    result = LedGeometryCalibrator(led=led, capture=MostlyBlindCapture(led, points)).calibrate()

    assert result.ok is False
    assert result.reason == "too_few_anchors"
    # 诊断必须活着 —— 用户要知道是哪几颗没找到。
    assert sum(1 for a in result.attempts if a.get("ok")) == 4
```

- [ ] **Step 2: 跑测试确认它红**

Run: `pytest tests/test_led_geometry_calibrator.py -k missing_anchors -v`
Expected: FAIL —— `assert result.reason == 'too_few_anchors'`，实际是 `'anchor_not_found:3,3'`

- [ ] **Step 3: 实现**

模块顶部加常量（**与拟合阶段同源，不许各写一个数**）：

```python
MIN_LOCATED_ANCHORS = 9  # 必须与 fit_geometry_from_anchors 的 min_inliers 同值
```

`calibrate()` 里把「找不到就 return」改成「记下来继续」，循环后统一判：

```python
                centroid = self._locate_anchor(row, col, attempts, roi=roi)
                if centroid is None:
                    continue  # 容缺:拟合阶段本来就允许 4 个外点
                detected.append(((row, col), centroid))
                if len(detected) == 4 and corner_h is None:
                    ...  # 四角单应,同 Task 5
            if len(detected) < MIN_LOCATED_ANCHORS:
                return CalibrationResult(ok=False, reason="too_few_anchors", attempts=tuple(attempts))
```

> ⚠️ 四角单应那一段的触发条件从 `index == 4` 改成 `len(detected) == 4 and corner_h is None`
> —— 有锚点缺失时 `index` 和 `len(detected)` 不再同步。
> 另：四角里若有缺失，`getPerspectiveTransform` 需要正好 4 点，此时前 4 个 `detected`
> 可能已经混进九星，单应仍然可解（四点不共线即可），ROI 半径按局部格距算，误差可接受。

- [ ] **Step 4: 跑测试确认它绿**

Run: `pytest tests/test_led_geometry_calibrator.py -v`
Expected: PASS

- [ ] **Step 5: 变异验证 —— 跨过边界**

把 `MIN_LOCATED_ANCHORS` 改成 `4`：`test_calibrate_stops_when_too_few_anchors_are_located` **必须变绿失败**
（即断言 `ok is False` 那条会红）。这证明测试钉的是「≥9」这个边界而不是「连到某个数」。改回 9。

- [ ] **Step 6: 提交**

```bash
git add katrain/vision/led_geometry_calibrator.py tests/test_led_geometry_calibrator.py
git commit -m "fix(vision): 检测阶段容缺至多 4 颗锚点,释放拟合阶段本就有的外点余量

新增 reason 取值 too_few_anchors,消费方在
2026-09-02-ingame-calibration-recovery.md Task 4。"
```

---

### Task 7: LED 非严格路径不再吞掉固件错误

一次点 361 颗只亮约 200 颗（固件 `MAX_ON 200`），而 HTTP 回 `ok:true`、161 条 `ERR maxon` 被存进没人读的对象、零日志（spec §2.8）。这不是标定链上的缺陷，但它**骗过了本次排查一整晚**。

**Files:**
- Modify: `katrain/web/core/led_service.py`（`_run_batch` 的错误处理 + `_submit` 非严格分支）
- Test: `tests/test_led_service.py`（若不存在则新建，参照 `tests/test_geometry_calibration_service.py` 的 Fake 风格）

**Interfaces:**
- Produces: 非严格路径的串口错误进 `logger.warning`；`LedService.last_errors: list[str]` 保存最近一批的错误，供 `/api/v1/led/status` 透出 `last_errors`。
  **不改** `/led/points` 的返回体（它已经返回过 `ok:true` 且调用方不等它），避免动到中继键集。

- [ ] **Step 1: 写失败测试**

```python
def test_non_strict_batch_logs_firmware_errors_instead_of_swallowing_them(caplog):
    """MAX_ON=200:第 201 颗起固件回 ERR maxon。非严格路径以前把它们存进
    没人读的对象、一行日志都不打 —— HTTP 说 ok,盘上半块不亮。"""
    serial = FakeSerial(replies=["OK", "ERR maxon", "OK"])
    service = LedService(LedServiceConfig(enabled=True, serial_port="/dev/null"), serial=serial)

    with caplog.at_level(logging.WARNING):
        service.set_points([{"row": 0, "col": 0, "color": "green"}], strict=False)
        service.drain()  # 等 worker 线程把这一批跑完

    assert any("ERR maxon" in record.message for record in caplog.records)
    assert service.last_errors == ["ERR maxon"]
```

> ⚠️ `FakeSerial` / `LedService` 的注入方式以仓库当前实现为准（`led_service.py:92-120` 的构造与
> `_Batch`）。若现有实现没有可注入的 serial，本任务的第一步就是**只加注入点**，不改行为，
> 单独提交，再做本任务其余部分。

- [ ] **Step 2: 跑测试确认它红**

Run: `pytest tests/test_led_service.py -k swallow -v`
Expected: FAIL

- [ ] **Step 3: 实现**

`_run_batch` 里 `self._finish(batch, ok=not errors, ...)` 之前加：

```python
        if errors:
            # 非严格路径的调用方拿不到这些 errors(HTTP 早在 _submit 里就回了 ok:true),
            # 所以这里是它们唯一的出口。MAX_ON / ERR range 之类都会走到这。
            logger.warning("LED batch reported %d firmware error(s): %s", len(errors), "; ".join(errors[:5]))
        self._last_errors = list(errors)
```

并加只读属性：

```python
    @property
    def last_errors(self) -> List[str]:
        """最近一批串口错误。非严格路径的 ok:true 只代表「入队了」,这里才是真相。"""
        return list(self._last_errors)
```

`katrain/web/api/v1/endpoints/led.py` 的 `led_status` 追加该字段：

```python
@router.get("/status")
async def led_status(request: Request):
    led = _get_led(request)
    return {"connected": led.is_connected(), "last_errors": led.last_errors}
```

- [ ] **Step 4: 跑测试确认它绿**

Run: `pytest tests/test_led_service.py -v`
Expected: PASS

- [ ] **Step 5: 板上验收 —— 用真的 MAX_ON 触发**

```bash
ssh rk3562-direct 'python3 -c "import json;print(json.dumps({\"points\":[{\"row\":r,\"col\":c,\"color\":\"green\"} for r in range(19) for c in range(19)]}))" > /tmp/all.json
curl -s -X POST http://127.0.0.1:8081/api/v1/led/points -H "Content-Type: application/json" --data @/tmp/all.json; echo
sleep 2
curl -s http://127.0.0.1:8081/api/v1/led/status; echo
journalctl -u smartbox-katrain --since "-1min" --no-pager | grep -i "firmware error"
curl -s -X POST http://127.0.0.1:8081/api/v1/led/clear'
```

Expected：`/led/status` 的 `last_errors` 非空且含 `ERR maxon`；journal 有一行 warning。
**验完记得 clear。**

- [ ] **Step 6: 提交**

```bash
git add katrain/web/core/led_service.py katrain/web/api/v1/endpoints/led.py tests/test_led_service.py
git commit -m "fix(led): 非严格路径不再吞掉固件错误,ERR maxon 进日志与 /led/status"
```

---

## 整体验收（全部任务完成后跑一次）

- [ ] `pytest tests/ -q` 全绿，**读退出码**：`pytest tests/ -q; echo "exit=$?"`
- [ ] 板上部署（按 `project_board_deploy_recipe`：子模块要单独 `git -C vendor/katrain archive <gitlink sha>`）
- [ ] `journalctl` 里 **不再有** `AE: camera has no runtime controls`
- [ ] `bright=` 在白天与夜间都落在 `[120,170]` 且尾注 `(ok)`
- [ ] **明亮环境**下人工触发标定：应当**快速失败**并报 `frame_overexposed`（不是跑完 13 颗再报 `not_enough_inliers`）
- [ ] **暗环境**下人工触发标定：13/13 通过，`confidence >= 0.90`，`attempts` 里 `level` 全为 96
- [ ] 摆一黑一白两颗子，`journalctl | grep worker_inprocess`：`stones` 计数正确、`mean_conf > 0.5`

> ⚠️ 「暗环境能过」这一条在 2026-09-02 之前就是真的（01:32 那次 conf 0.954）。
> **它不能作为本计划生效的证据** —— 生效的判据是上面那条「明亮环境下快速失败并说得出原因」，
> 以及 Task 5 之后九星锚点不再被眩光抢走。
