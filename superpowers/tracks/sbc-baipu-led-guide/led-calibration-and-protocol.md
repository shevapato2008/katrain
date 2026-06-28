# LED 串口协议 + (row,col)↔索引 相机自动标定（参考实现）

> 配套 `prd.md`（track `sbc-baipu-led-guide`）。本文件给出两段可直接拿走的骨架代码：
> **(A) ESP32-S3 固件串口协议骨架**（在现有 `smartbox-hardware-design/debug/led_bring_up_pio` 上扩展）；
> **(B) 主机侧相机自动标定脚本**（锁定棋盘几何后，逐颗点灯→相机定位→生成权威 361 项 LUT）。
>
> ⚠️ 设计原则:**主机持有权威 LUT,固件只认"原始链索引" `SETI`。** 原因——固件注释链序(UL→UR→LL→LR)与
> PCB 走线(UL→LL→LR→UR)冲突 + 子板物理旋转未知,(row,col)↔索引**不可靠地从公式推定**,必须实测。
> 让主机持 LUT → 重标定只改一个 JSON,固件零改动;摆谱时主机把 (row,col) 翻成 idx 再发 `SETI`。

---

## A. 串口协议（USB-serial @115200，行式 ASCII）

帧缓冲模型:`SETI/CLEAR` 改缓冲,`SHOW` 才真正渲染(`FastLED.show()`),避免逐颗刷新闪烁。

| 命令 | 含义 | 回复 |
|---|---|---|
| `SETI <idx> <r> <g> <b>` | 暂存链索引 idx∈[0,360] 的颜色(主刀命令) | `OK` / `ERR range` |
| `SHOW` | 渲染帧缓冲 | `OK` |
| `CLEAR` | 缓冲全灭(需 `SHOW` 生效)或 `CLEAR!` 立即灭 | `OK` |
| `BRIGHT <v>` | 全局亮度,钳到 `MAX_BRIGHT=40` | `OK v=<clamped>` |
| `SCAN [ms]` | 逐颗 0→360 自检扫描,每颗打印 `IDX <i>` | 逐行 + `DONE` |
| `STATUS` | 版本/亮灯数/亮度/uptime | 文本 |
| `SET <row> <col> <r> <g> <b>` | (可选)板坐标,用固件内 LUT;未标定则 `ERR nolut` | `OK`/`ERR` |
| `MAPSET <row> <col> <idx>` | (可选)上传一项 LUT;`MAPSAVE` 存 NVS | `OK` |

约束:固件维护 `MAX_ON`(同亮上限,防过流)与 `MAX_BRIGHT`。摆谱只亮 1–2 颗,天然安全。

---

## B. ESP32-S3 固件骨架（C++ / Arduino / FastLED）

```cpp
// 在 smartbox-hardware-design/debug/led_bring_up_pio/src/main.cpp 基础上扩展
#include <Arduino.h>
#include <FastLED.h>

#define DATA_PIN     4
#define NUM_LEDS     361
#define COLOR_ORDER  GRB
#define MAX_ON       20      // 同亮上限,防过流
#define MAX_BRIGHT   40

CRGB leds[NUM_LEDS];

static int countOn() {                 // 帧缓冲里非黑的灯数
  int n = 0; for (int i = 0; i < NUM_LEDS; i++) if (leds[i]) n++; return n;
}

void setup() {
  Serial.begin(115200);
  FastLED.addLeds<WS2812B, DATA_PIN, COLOR_ORDER>(leds, NUM_LEDS);
  FastLED.setBrightness(MAX_BRIGHT);
  FastLED.setMaxPowerInVoltsAndMilliamps(5, 1500);
  FastLED.clear(true);
  Serial.println("READY");
}

// --- 行式命令解析 ---
String buf;
void handleLine(const String& line);

void loop() {
  while (Serial.available()) {
    char c = (char)Serial.read();
    if (c == '\n' || c == '\r') { if (buf.length()) { handleLine(buf); buf = ""; } }
    else if (buf.length() < 64)  buf += c;
  }
}

void handleLine(const String& s) {
  // 极简分词
  char cmd[16] = {0}; int a, b, r, g, bl, ms;
  if (sscanf(s.c_str(), "%15s", cmd) != 1) { Serial.println("ERR parse"); return; }

  if (!strcmp(cmd, "SETI")) {
    if (sscanf(s.c_str(), "%*s %d %d %d %d", &a, &r, &g, &bl) != 4) { Serial.println("ERR args"); return; }
    if (a < 0 || a >= NUM_LEDS) { Serial.println("ERR range"); return; }
    CRGB col(r, g, bl);
    // 过流保护:新增一个亮点且已达上限则拒绝
    if (col && !leds[a] && countOn() >= MAX_ON) { Serial.println("ERR maxon"); return; }
    leds[a] = col; Serial.println("OK");

  } else if (!strcmp(cmd, "SHOW"))   { FastLED.show(); Serial.println("OK"); }
  else if   (!strcmp(cmd, "CLEAR"))  { FastLED.clear(false); Serial.println("OK"); }
  else if   (!strcmp(cmd, "CLEAR!")) { FastLED.clear(true);  Serial.println("OK"); }
  else if   (!strcmp(cmd, "BRIGHT")) {
    if (sscanf(s.c_str(), "%*s %d", &a) != 1) { Serial.println("ERR args"); return; }
    if (a > MAX_BRIGHT) a = MAX_BRIGHT; if (a < 0) a = 0;
    FastLED.setBrightness(a); FastLED.show(); Serial.printf("OK v=%d\n", a);

  } else if (!strcmp(cmd, "SCAN")) {           // 自检/人工标定:逐颗点亮
    ms = 80; sscanf(s.c_str(), "%*s %d", &ms);
    for (int i = 0; i < NUM_LEDS; i++) {
      FastLED.clear(); leds[i] = CRGB::White; FastLED.show();
      Serial.printf("IDX %d\n", i); delay(ms);
    }
    FastLED.clear(true); Serial.println("DONE");

  } else if (!strcmp(cmd, "STATUS")) {
    Serial.printf("v1 on=%d bright=%d up=%lu\n", countOn(), MAX_BRIGHT, millis());

  } else { Serial.println("ERR cmd"); }
}
// SET <row> <col> ... / MAPSET / MAPSAVE：如需固件侧 LUT 再加(默认走主机侧 LUT + SETI)。
```

---

## C. 主机侧相机自动标定脚本（Python，生成权威 LUT）

前置:**棋盘几何已锁定**(autoresearch `board-detection/data/session.npz`,含 `M/out_size/xs/ys`)。
原理:逐颗点亮链索引 i,相机抓帧 warp 到正视,在 361 个交叉点邻域找"相对全灭基线最亮"的点 → `idx→(row,col)`。

```python
#!/usr/bin/env python3
"""LED 相机自动标定:链索引 idx -> 棋盘 (row,col),生成 361 项权威 LUT。
用法: python led_calibrate.py --session <session.npz> --port /dev/ttyACM0 --cam 0 --out led_lut.json
"""
import argparse, json, time
import numpy as np, cv2, serial

def cmd(ser, line, wait=0.0):
    ser.write((line + "\n").encode()); ser.flush()
    if wait: time.sleep(wait)
    return ser.readline().decode(errors="ignore").strip()

def grab_warped(cap, M, out):
    for _ in range(4): cap.read()                 # 丢旧帧
    ok, f = cap.read()
    if not ok: raise RuntimeError("camera read failed")
    return cv2.warpPerspective(f, M, (out, out))

def patch_brightness(gray, x, y, r):
    h, w = gray.shape
    x0, y0 = max(0, int(x-r)), max(0, int(y-r))
    x1, y1 = min(w, int(x+r)+1), min(h, int(y+r)+1)
    p = gray[y0:y1, x0:x1]
    return float(p.mean()) if p.size else 0.0

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--session", required=True); ap.add_argument("--port", required=True)
    ap.add_argument("--cam", type=int, default=0); ap.add_argument("--out", default="led_lut.json")
    ap.add_argument("--num", type=int, default=361); ap.add_argument("--settle", type=float, default=0.18)
    a = ap.parse_args()

    s = np.load(a.session)
    M, out = s["M"], int(s["out_size"])
    xs, ys = s["xs"], s["ys"]                       # 各 19 个,warped 像素坐标
    spacing = float(np.median(np.diff(xs))); r = max(4.0, spacing*0.30)

    ser = serial.Serial(a.port, 115200, timeout=1.0); time.sleep(2.0); ser.reset_input_buffer()
    cap = cv2.VideoCapture(a.cam)
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920); cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
    time.sleep(2.0)                                 # 等自动对焦/曝光

    cmd(ser, "CLEAR!"); 
    base = cv2.cvtColor(grab_warped(cap, M, out), cv2.COLOR_BGR2GRAY).astype(np.int32)

    idx2rc = {}
    for i in range(a.num):
        cmd(ser, "CLEAR"); cmd(ser, f"SETI {i} 255 255 255"); cmd(ser, "SHOW", wait=a.settle)
        g = cv2.cvtColor(grab_warped(cap, M, out), cv2.COLOR_BGR2GRAY).astype(np.int32)
        d = np.clip(g - base, 0, 255).astype(np.uint8)        # 相对基线的增量
        best, bv = None, -1.0
        for rr in range(19):
            for cc in range(19):
                v = patch_brightness(d, xs[cc], ys[rr], r)
                if v > bv: bv, best = v, (rr, cc)
        idx2rc[i] = {"row": best[0], "col": best[1], "score": round(bv, 1)}
        print(f"idx {i:3d} -> {best}  score={bv:.1f}")
    cmd(ser, "CLEAR!"); cap.release(); ser.close()

    # 自检:应命中恰好 num 个互异交叉点
    seen = {}
    for i, v in idx2rc.items():
        k = (v["row"], v["col"]); seen.setdefault(k, []).append(i)
    dup = {k: v for k, v in seen.items() if len(v) > 1}
    missing = [(rr, cc) for rr in range(19) for cc in range(19) if (rr, cc) not in seen]
    if dup:     print("⚠️ 重复(可能坏灯/接错/标定噪声):", dup)
    if missing: print(f"⚠️ 缺失 {len(missing)} 个交叉点:", missing[:10], "...")

    rc2idx = {f"{v['row']},{v['col']}": int(i) for i, v in idx2rc.items()}  # 摆谱用
    json.dump({"idx2rc": idx2rc, "rc2idx": rc2idx,
               "dup": {f"{k[0]},{k[1]}": v for k, v in dup.items()},
               "missing": [list(m) for m in missing]},
              open(a.out, "w"), ensure_ascii=False, indent=2)
    print(f"\n保存 {a.out}  ({len(rc2idx)}/{a.num} 唯一映射)")

if __name__ == "__main__":
    main()
```

---

## D. 使用流程

1. **固件**:把 A 段协议合进 `led_bring_up_pio` 烧录;`STATUS`/`SCAN` 自检整链 361 灯无断点。
2. **锁定几何**:在 autoresearch 侧 `calibrate_ui.py` 标定 → `session.npz`(或复用产品 `grid_calibrator` 结果,见 PRD §7 待决)。
3. **自动标定**:`python led_calibrate.py --session …/session.npz --port /dev/ttyACM0 --cam 0`
   → 30 秒生成 `led_lut.json`,并报告坏灯/接错(dup/missing)。
4. **摆谱用**:rk3588-ui 的 LED 服务加载 `led_lut.json` 的 `rc2idx`,把 SGF 第 i 手的 (row,col) 翻成 idx,发 `SETI idx <红/绿> ; SHOW`。
5. **重布线/换板**:只需重跑第 3 步刷新 `led_lut.json`,固件与上层代码零改动。

> 兜底(无相机时):用固件 `SCAN` 逐颗点亮,人工记录每个 `IDX i` 的物理 (row,col),手填 `led_lut.json`。

---

## E. 完整调用图：从 UI 按钮到 `rc2idx`（as-built, 2026-06-28）

> 实测代码现状（与 A–D 的早期骨架略有出入）：默认 LUT 是 `led_service.rc2idx` 公式（经验证双射，
> 可用 `--led-lut-path` JSON 覆盖）；几何锁定走 `geometry_lock` + `GeometryCalibrationService`，
> P11 漂移在线重定位走 `fiducial_recalibrate`。设计原则不变：**固件只认原始链索引 `SETI`，
> (row,col)→idx 的映射全部在主机端 `rc2idx`。**

### 全景（4 层 + 两个入口）

```
[前端 kiosk UI]                         [FastAPI 端点]                        [服务/核心层]                                 [LED 驱动]              [映射]
─────────────────                       ───────────────                       ────────────────                              ──────────             ──────

A. 摆谱（每手落子 / 提子）
 BaipuSessionPage.tsx
   baipu-confirm 按钮  (:443) ─┐
   baipu-removed 按钮  (:456) ─┼─► doCapture() (:208)
                               │     └► BaipuAPI.capture()                  POST /baipu/capture
                               │        (baipuApi.ts:93) ───────────────►   baipu_capture() (baipu.py:103)
                               │                                              └► run_capture() (baipu_capture.py)
                               │                                                   ├─ 制导灯       ─► led.set_points()      (:352) ─► led_service.set_points()      (:188) ─► self._lut(r,c) ─┐
                               │                                                   └─ P11 基准灯    ─► led.set_rgb_points()  (:170) ─► led_service.set_rgb_points()  (:205) ─► self._lut(r,c) ─┤
                                                                                      (_run_fiducial_calibration)                                                                              │
B. 几何标定 / 开机锁定棋盘                                                                                                                                                                     │
 VisionSetupPage.tsx ─┐                                                                                                                                                                      │
 PhysicalBoardGuard.tsx┼─► useGeometry()  (GeometryContext.tsx)                                                                                                                              │
                       │     ├► GeometryAPI.calibrate()  (geometryApi.ts:85) ─►  POST /geometry/calibrate                                                                                     │
                       │     │                                                     geometry_calibrate() (geometry.py:69)                                                                      │
                       │     │                                                      └► GeometryCalibrationService.start()                                                                     │
                       │     │                                                          └► LedGeometryCalibrator (led_geometry_calibrator.py)                                                 │
                       │     │                                                              └► led.set_rgb_points() (:230) ─► led_service.set_rgb_points() (:205) ─► self._lut(r,c) ──────────┤
                       │     └► GeometryAPI.lock()       (geometryApi.ts:70) ─►  POST /geometry/lock → _run_lock() (geometry.py:178)                                                          │
                       │                                                          [仅 led.clear() 熄灯做空盘自检，不经 rc2idx]                                                                  │
                       │                                                                                                                                                                      ▼
C. 手动 / 调试直连                                                                                                                                          self._lut = _load_lut() (:111)
 (前端调试面板 / curl) ──► POST /led/point(s) (led.py:43,50) ─► led.set_points() ─► led_service.set_points() (:188) ─► self._lut(r,c) ────────────────────►  默认 return rc2idx (:143)
                                                                                                                                                            └─► rc2idx() (led_service.py:40)
D. 独立诊断工具（不经 UI / API，你手动跑）                                                                                                                       └─ serp() (:36) 子板蛇形
 p11_live_overlay.py  按 'r' 重锁 ─► relock() (:74) ─► led.set_rgb_points() ─► led_service.set_rgb_points() (:205) ─► self._lut(r,c) ─► rc2idx
```

### 真正触发 `rc2idx` 的运行时端点（汇总）

| 入口 | 触发路径 | 经过的 LedService 方法 |
|---|---|---|
| 摆谱制导灯 | `BaipuSessionPage` → `/baipu/capture` → `run_capture` → `baipu_capture.py:352` | `set_points` |
| P11 在线漂移重定位 | 同上 → `run_capture` → `_run_fiducial_calibration` → `baipu_capture.py:170` | `set_rgb_points` |
| 开机/几何标定锁盘 | `VisionSetupPage`/`PhysicalBoardGuard` → `/geometry/calibrate` → `GeometryCalibrationService` → `LedGeometryCalibrator` → `led_geometry_calibrator.py:230` | `set_rgb_points` |
| 手动/调试点灯 | `/led/point(s)` → `led.py:43,50` | `set_points` |
| 独立诊断（实时叠加工具） | `p11_live_overlay.py:74` `relock()` | `set_rgb_points` |

**不经过 `rc2idx` 的路径**（只发 `CLEAR/SHOW`，无 (row,col) 映射，却是调用最频繁的）：
`led.clear()` —— `server.py:1786`（failsafe）、`baipu_capture.py:168/172/360`、`geometry_calibration_service.py:79/207`、
`geometry.py:237`（lock 熄灯）、`led_geometry_calibrator.py:207/217/225`、`p11_live_overlay.py:72/76/104/160`。

### 依赖装配（`server.py` lifespan）

`app.state.led`（:396，`LedService` 实例，持 `self._lut`）· `app.state.capture`（:409）· `app.state.geometry`（:419，已锁几何）·
`app.state.geometry_calibration`（:437，`GeometryCalibrationService`）· `app.state.baipu_fiducial_mode`（:412，默认 `every-move`）。
端点全部通过 `request.app.state.*` 取这些单例，故"谁调用 LED"最终都收敛到同一个 `LedService.self._lut → rc2idx`。

### 设备端固件（链路另一端，不参与 (row,col) 映射）

`smartbox-hardware-design/debug/led_bring_up_pio/src/main.cpp`：`loop()` 拼行 → `handleLine()` 分发
`SETI/SHOW/CLEAR/CLEAR!/BRIGHT/SCAN/AUTO/STOP/STATUS`，只写 `leds[idx]`（原始链索引）。固件**零** (row,col) 概念。
（旧的 `saiboard/software/esp32s3/main/main.c` 曾有设备端映射 `_row_col_to_nr`，是已弃用的 WiFi-JSON 固件，不在此链路。）

### 测试

`tests/test_led_service.py`：`:60-67` 断言 8 个角/边界映射值；`:70` 验证双射；`:100` 断言最终 `SETI` 行用 `rc2idx` 算出的 idx；`:136` 用 `rc2idx` 校验 `set_points` 输出。
