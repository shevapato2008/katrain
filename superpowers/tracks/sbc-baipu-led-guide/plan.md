# 实施计划：Kiosk 摆谱 + LED 引导落子（sbc-baipu-led-guide）

- **Track**: `sbc-baipu-led-guide`  ·  **分支**: `feature/rk3588-ui`  ·  **日期**: 2026-06-21（**v4**；P5 为真机联调后新增）
- **依据**: `prd.md` · `led-calibration-and-protocol.md` · `review-feedback-{codex,gemini,gstack}.md` · 4 项决策（见 §0.3）
- **状态**: **P1–P5 已实现**；**P6 待执行**，补齐 SBC 前端双实时画面、四角/361 点可视化和位移后重标定闭环。见 §11–§12 执行记录及 P6 计划。

> **For agentic workers:** REQUIRED: Use `superpowers:executing-plans` to implement P5. Steps use checkbox (`- [ ]`) syntax for tracking and follow TDD red/green verification.

> 写给「无上下文的执行者」（人或子 agent）。执行顺序 **P0(可选) → P1 → P2 → P3 → P4 → P5**。
> v2→v3 改了什么见 [§10](#10-修订记录v2v3)。

---

## 0. 目标、前置、决策

### 0.1 目标与范围
kiosk「摆谱」模式：按已知 SGF **逐手用 LED 点亮下一手落子点**引导人工摆子，**确认时做 CV 校验防摆错**，**带灯拍照**每一步，照片+manifest+SGF 落到 katrain 文件夹；交给 `autoresearch` 训练 YOLO（**SGF=ground truth**）。本 track **只建 katrain 侧**；固件已烧好；YOLO 标签/训练在 `autoresearch`。

### 0.2 已确认前置（brainstorming + 硬件实测 2026-06-15）
- **协议固件已烧** ESP32-S3：`SETI <idx> <r> <g> <b>` / `SHOW` / `CLEAR` / `CLEAR!` / `BRIGHT <v>` / `SCAN` / `STATUS`；`MAX_ON=20`、`MAX_BRIGHT=40`（全局亮度钳制，非单通道）；主机持 LUT。Mac 端口 `/dev/cu.usbmodem2101 @115200`，单颗点亮已实测。
- **LED (row,col)→链索引 = 纯公式**（实测：线扫整齐 + idx0=(0,0)顶左 + 星位命中），见 [附录 A](#附录-a확认的-led-lut公式)。
- **采集=带灯拍(方案B)**；**确认=触屏**；**相机接 Mac**。

### 0.3 关键决策（与作者逐条敲定，2026-06-16）
| # | 决策 | 选择 | 影响 |
|---|---|---|---|
| ① | 摆谱/LED 是产品功能 vs 一次性工具 | **产品功能** → 保留 LED 摆谱 | 照计划做；**并入数据去相关** + **Phase 0 分类器基准（可选门）** |
| ② | 逐手盘面/提子真值算在前端 vs 后端 | **后端权威** | 新增 `POST /baipu/load`，引擎(game.py)算真值；前端哑播放；**白送修好让子(AB/AW)**；`goBoard.ts` 收敛降级为可选清理 |
| ③ | 摆错兜底 QA 程度 | **L2 主动阻断 + 操作者覆盖** | 确认时 CV 差分校验，不一致**阻断+提示**，可改正或「确认无误继续」；manifest 记 `qa_status` |
| ④ | 采集中「上一手/下一手/跳过」 | **前进 + 单步引导撤回 + 退出重来** | 去掉「下一手/跳过」；保留物理引导的「撤回上一手」 |

### 0.4 其它已确认事实
- 全链路 **规范坐标 `(row,col)`，row=0 顶部、col=0 左**（= LED LUT，附录 A）。后端 `/baipu/load` 直接输出规范坐标；用 **branded types** + round-trip 测试封死边界。
- 采集 **限 19×19**（LED 板物理 19×19）。
- **Ko/非法手不校验**（重放合法 SGF，引擎镜像）；真正兜底的是 ③ 的人为**摆错** QA。

---

## 1. 架构与数据流

```
[BaipuListPage] 选 19×19 SGF
   └ POST /baipu/load → 后端引擎(game.py/sgf_parser)算整盘逐手真值:
        steps[k] = {kind:setup|move|pass, move_index, row, col, color, removed[], board_hash}
[BaipuSessionPage] 哑播放 steps（前端不算提子）；状态机：前进 + 单步引导撤回
   每手 k：
     GUIDING(k)  屏幕高亮 + (P2) 点亮 LED(steps[k] 颜色)；人摆子
     └「确认」
     QA(k)       (P4) led 全灭(strict ack) → 抓新帧 → stones.classify vs 期望盘面(0..k)
                  一致→放行；不一致→阻断+提示→改正 / 「确认无误继续」(override)
     CAPTURE(k)  (P4) 点亮下一手 LED(strict ack, 记 show_at) → 等 show_at 之后的新帧(缓冲已被后台线程抽空)+锁曝光 → 抓帧带灯
                  → 存 frame + manifest 条目(qa_status, frame_kind, led_point, board_hash, geometry 快照)
     → GUIDING(k+1) … 谱尾 DONE
```
- LED 命令分两路：**UI 容错路**（点屏导航，入队即返回）与 **采集强一致路**（等串口 `SHOW` 的 OK ack 才返回，拿到 `show_at`）。
- P1–P4 相机由**单一 `CaptureService`** 持有并拒绝与 `VisionService` 同开；P5 将其演进为**单一 `CameraHub`**，向几何标定、采集和实时识别发布同一帧源，移除互斥。
- 后端服务都按 `VisionService` 模式：`_lifespan_board()` 按命令行 gate 启动 + 绑 `app.state.*`；`lifespan()` 关停 `.stop()` + **强制 `led.clear()` 兜底灭灯**。

---

## P0. 分类器基准（可选，autoresearch 侧，**建议先做**）

**目的**：30 分钟低成本实验，决定 ③ 的 L2 QA 用的经典 CV（`stones.py` 空盘差分）在本橙木盘上**是否可靠**，并校准阈值；顺带验证「CV 自动标注可信度」。
- 步骤：几何锁定后，实摆若干黑/白子（含贴边/邻接/被提形态）→ `detect_stones.py`/`stones.classify` → 出 black/white/empty 混淆矩阵。
- 产出：阈值参数 + 一句结论：CV 可靠（→ L2 默认开、少误报）/ 不可靠（→ L2 退化为「每 N 手人工复核」，见 P4.3）。
- **不阻断 P1/P2**（纯前端 + LED 不依赖它）；但 **P4 的 L2 QA 强烈建议在 P0 之后**调参。

---

## P1. 摆谱 UI + 后端逐手真值（**纯屏幕，不接硬件**）

**目标**：选谱(19×19) → 会话页(LiveBoard + 双 PlayerCard 当前方高亮 + N/total) → 前进/撤回/确认 状态机；确认时若该手提子，提示移除哪些子（数据来自后端）。屏幕高亮模拟 LED；`CAPTURE/QA` 在 P1 为 no-op。

### 1.1 后端：逐手真值接口（决策 ②）
- **新建** `katrain/web/api/v1/endpoints/baipu.py` 的 `POST /baipu/load`：
  - 入参 `{sgf: str}` 或 `{kifu_id}`（见 1.2 离线来源）。
  - 用既有引擎：`katrain/core/sgf_parser.py`（已展开 AB/AW/AE）+ `katrain/core/game.py`（`_calculate_groups`/`_validate_move_and_update_chains` 已正确算提子）重建整盘，逐节点输出：
    ```json
    {
      "board_size": 19,
      "steps": [
        {"kind": "setup|move|pass", "move_index": 0, "property": "AB|AW|B|W",
         "row": 3, "col": 3, "color": "B|W|null",
         "removed": [{"row": 9, "col": 9}],
         "board_hash": "…"}
      ],
      "meta": {"player_black": "...", "player_white": "...", "handicap": 0}
    }
    ```
  - **坐标规范化**在此完成。game.py/sgf_parser 内部为 `y=0 底部`（`sgf_parser.py` 用 `board_size[1]-index-1`）；规范坐标 `row=0 顶部`。转换：**`row = (board_size-1) - y_internal`，`col = x_internal`**（仅垂直翻转，列不变）。**单测**覆盖 D4/Q16/非对称角点在 19/13/9 路，并 round-trip 校验 `规范→引擎→规范 == 恒等`，且 `规范(row,col)` 经附录 A `rc2idx` 落到正确 LED（封死垂直倒置——本链路最高风险）。
  - **per-step `removed[]` 与 `board_hash` 须在重放循环内逐节点采集**（可行性修正）：game.py 的 `last_capture` 是每手重置的瞬时态、`GameNode` 不持久化它，也无 `board_hash`。故 `/baipu/load` 必须在 `_calculate_groups` 重放时**每步收集** `last_capture`（→`removed[]`）并对当步盘面快照 `hashlib`（→`board_hash`）；不要假设引擎已存好这些。
  - `kind=setup` 不触发提子/非法判断（修 Codex#4 让子缺口）；`pass` 显式标记，`row/col/color=null`。
  - 注册进 `api.py`（prefix `/baipu`）。
- **打谱复用**：未来打谱/复盘走同一 `/baipu/load`（或抽成 `/sgf/steps`）。

### 1.2 选谱入口 + **离线 SGF 来源**（修 Codex#9）
- **新建** `katrain/web/ui/src/kiosk/pages/BaipuListPage.tsx`：以 `KifuPage.tsx` 为骨架；**过滤(非置灰) 只显示 19×19**；**空状态**（「未找到 19 路棋谱」+ 操作指引）；列表顶「继续上次会话」入口（见 1.3 resume）。
- **离线来源**：board-mode 的 kifu repository 是 **online-only**（`web/core/repository.py:245-263` 离线返回空/404）。**P1 必须加本地 SGF 来源**之一：
  - **采用 (b) 为主**：选中 kifu 时把 SGF 文本随 `/baipu/load` 一并缓存到本地（localStorage/IndexedDB，键 `kifu_id`；列表加「已缓存」区）；**(a) 文件导入为兜底**（上传/选择 .sgf → 存本地）。两条路都直接喂 `/baipu/load`。
  - 采集现场不得依赖远端网络。
- **路由** `KioskApp.tsx`：`<Route path="baipu" element={<BaipuListPage/>}/>`、`<Route path="baipu/session/:source" element={<BaipuSessionPage/>}/>`。
- **导航 Tab** `navTabs.tsx`：`primaryTabs` 插 `{label:'摆谱', icon:<GridOn/>, path:'/kiosk/baipu', pattern:'/kiosk/baipu/*'}`。

### 1.3 会话页 + 状态机 + UX
- **新建** `katrain/web/ui/src/kiosk/pages/BaipuSessionPage.tsx`：
  - 进页 `POST /baipu/load` 取 `steps`（**前端不算提子**，哑播放）。`game_id = <source>_<sessionTs>`（slug 安全，写 manifest）。
  - **布局层级（修 gstack 设计 #4，参考元萝卜）**：顶部**常驻大状态条**（`●当前色 落子 第 k/N 手 · 已采集 M 帧 · 健康点[LED/相机] · ~剩余时间`，字号 @1.5m 可读）；左 `LiveBoard`；右两张 `PlayerCard`（`active` 跟随当前色）+ **下一手色片**（= LED 色，最醒目元素）。规则：**屏幕是仪表盘，物理盘才是主体**。
  - **LiveBoard 新 prop**（不滥用 pvMoves）：`nextMovePoint?:{row,col}|null`（**高亮色须与 LED 一致**：黑→红、白→绿）、`capturedPositions?:{row,col}[]|null`（提子待移除，红闪）。**坐标边界转换**在喂 LiveBoard 时做（规范↔LiveBoard 内部 y 底部），用 branded types。
  - **状态机**（决策 ③④；P1 阶段 QA/CAPTURE 为 no-op）：
    ```
    GUIDING(k)  屏幕高亮 nextMovePoint=steps[k]; pass→直接 ADVANCE; (P2)点灯
       └「确认」(人已摆好 k)
    QA(k)       (P4)CV 校验；P1 直接通过
       └ 不一致→阻断横幅+「改正后确认」/「确认无误继续(override)」
    CHECK_REMOVE(k)  steps[k].removed 非空→AWAIT_REMOVAL(独立模式)→「已移除 N 子」
    ADVANCE(k)  屏幕落子+提子动画→盘面 0..k；k++
    CAPTURE     (P4)带灯拍；P1 no-op
    → GUIDING(k) … k==N → DONE(汇总 N 手/采集 M 帧)
    撤回上一手   (决策④)物理引导：提示「拿掉刚摆的子(并恢复被提子)」→作废该帧→回 k-1
    退出        二次确认对话框（移出控制行）→ led.clear()
    ```
    - **去掉「下一手/跳过」**（物理摆谱不摆子无法前进）。
    - **提子=独立模式（修设计#3）**：进入 AWAIT_REMOVAL 时盘面变态（暗化已落子、待移除红闪）+ 全宽横幅「请移除 N 个被提的子（闪烁处）」+ 动作键**改文案改色**为「已移除 N 子」（warning/info 色，呼应蓝灯），打断「落子-确认」节奏；完成有明确回到 place 模式的过渡。
  - **控制条人体工学（修设计#2）**：`确认` ≥88px 高、≥60% 宽、底部居中、`primary.main`、保留 scale-on-active（拇指盲按）；`撤回上一手` 次级；`重新点灯` 三级；`退出` 移出控制行到顶角 + 二次确认。规则：**会话级控件不与每手控件相邻**。
  - **轻量 resume（修设计#6）**：每次 ADVANCE 把 `{game_id,k,frames}` 存 localStorage（磁盘 manifest 为真值源）；进会话若存在未完成 manifest，提供「继续上次(第 X 手)」/「重新开始」。
  - **i18n**：`useTranslation()`。

### 1.4 P1 验收
1. 「摆谱」Tab 可达；列表只让选 19×19 + 空状态；**离线**（断远端）仍可选到本地 SGF 进会话。
2. `/baipu/load` 对**含让子(AB/AW)**与**含提子**的谱返回正确 `steps`（提子点、setup 标记、board_hash 正确）。
3. 左盘逐手渲染、右当前方高亮、`k/N` 正确；前进/撤回(物理引导文案)/确认正常；提子为独立模式。
4. 谱尾 DONE 汇总。
5. **双构建绿** + `npm run lint` 无 kiosk 越界 import。
6. **测试(阻断)**：`tests/test_baipu_load.py`（让子/提子/pass/board_hash/坐标规范化）；Playwright `baipu.spec.ts`（路由→选谱(本地)→逐手→提子独立模式→撤回→谱尾，mock /baipu/load）；坐标 branded-type round-trip 单测。

---

## P2. LED 串口服务 + 引导接入（**硬件就绪可联调**）

**目标**：`LedService` 用公式 LUT 把规范 (row,col)→idx 发 `SETI/SHOW`；两路（UI 容错 / 采集强一致）；摆谱页点亮下一手（黑红/白绿/提子蓝）。

### 2.1 LedService
- **新建** `katrain/web/core/led_service.py`：
  - `LedServiceConfig`：`enabled, serial_port, baud_rate=115200, max_bright=40, lut_path=None`。
  - `LedService`：
    - `start()`：开串口；起后台线程 + **有界队列**(`maxsize=10`)；读 `READY`；发 `BRIGHT 40`。
    - `stop()`：`CLEAR!` + 关串口 + 停线程。
    - `set_points(points, *, strict=False)`：`points=[{row,col,color}]`。**整批命令（CLEAR+多 SETI+SHOW）作为单个队列项入队**（修 Gemini#5：`queue.Queue` 本身线程安全，**去掉多余 Lock**；队满 `put_nowait`→`Full`→丢最旧）。`strict=True`（采集路）：**同步等串口逐条 OK，直到 `SHOW` 的 OK**，返回 `{ok, connected, shown_at, errors}`；`strict=False`（UI 路）：入队即返回。
    - `clear(*, strict=False)`。
    - `is_connected()`（advisory）。
    - **LUT**：默认内嵌 [附录 A](#附录-a확认的-led-lut公式) `rc2idx`；`lut_path` 给定且 `validate_lut()`(覆盖全 361、∈[0,360]) 通过则覆盖。
    - **颜色**：`black→红`、`white→绿`、`remove→蓝`。**RGB 为 0-255 帧缓冲值，实际输出由全局 `BRIGHT 40` 缩放**（修 Codex#12：用 `(0,255,0)` 之类全饱和值，亮度由 BRIGHT 钳；文档写清）。
    - **健壮性**：`pyserial timeout=1~2s`；读写包 try/except；断开标 disconnected + 线程内每 5~10s 重连；未连接时 UI 路静默丢弃，**采集路返回 `{ok:false}`（该帧不得写训练 manifest）**（修 Codex#5）。
- **gate + 兜底灭灯** `server.py`：`run_web()` 加 `--led-serial-port/--led-baud-rate/--led-lut-path`；`_lifespan_board()` 启用则 `app.state.led`。**`lifespan()` 关停 `led.stop()`**；并加**会话断开/超时兜底**（修 Gemini 新#2）：WebSocket disconnect 或 **>5 分钟**无活动（前端心跳，或 WS on_disconnect 钩子）→ 强制 `led.clear()`，避免 Kiosk LED 亮一整天。

### 2.2 LED REST
- `endpoints/led.py`（仿 vision.py），`_get_led` None→404，响应统一 `{ok, connected}`（采集路附 `shown_at, errors`）：
  - `POST /point {row,col,color}`、`POST /points {points}`、`POST /clear`、`GET /status`。校验 0..18。
  - 注册 `api.py`（prefix `/led`）。

### 2.3 前端接入
- **新建** `src/api/ledApi.ts`：`point/points/clear`。
- `BaipuSessionPage` 状态机：`GUIDING(k)`→`ledApi.point({row,col: steps[k], color: steps[k].color==='B'?'black':'white'})`（**规范坐标直接传，不反转**）；`AWAIT_REMOVAL`→`ledApi.points(steps[k].removed.map(p=>({...p,color:'remove'})))`；退出/DONE→`clear()`。UI 路 LED 失败仅记日志/状态点变灰，不阻塞屏幕。

### 2.4 P2 验收
1. `--led-serial-port /dev/cu.usbmodem2101` → `GET /led/status` connected。
2. **坐标硬件验证（关键）**：对若干**非对称**已知手（左上 3-3、右下角、边）点亮，**物理 LED == 屏幕高亮 == SGF 落子点**；黑红/白绿；提子蓝。
3. 拔插 USB 不崩、重连恢复；浏览器关闭/超时后 LED 自动灭。
4. **测试(阻断)** `tests/test_led_service.py`(mock serial)：`rc2idx` 8 校验点(附录 A)+内部点；颜色/RGB-BRIGHT；strict 路等到 SHOW OK 才返回；队满丢弃；重连。

---

## P3. 几何识别迁移 + CaptureService（相机基座，**硬件就绪**）

**目标**：把 autoresearch `autocal` 移植进 katrain，提供「锁定几何」；建立**单一相机 owner** `CaptureService`（供几何锁 + P4 采集 + QA 取帧）；退役 `grid_calibrator`。

### 3.1 CaptureService（单一相机 owner，修 Codex#8 / Gemini#1 / Gemini 新#1）
- **新建** `katrain/web/core/capture_service.py`：包 `katrain/vision/camera.py` 的 `CameraManager`。
  - `CaptureServiceConfig`：`enabled, camera_device, width, height, out_dir(默认 Path.home()/".katrain"/"baipu_captures"，init expanduser)`。
  - `start()/stop()/is_connected()`。
  - **`CameraManager` 增帧序号+时间戳**（后台读线程**每次 `cap.read()` 后在锁内**打 `time.monotonic()` 时间戳 + 递增 seq），`grab_fresh(after_ts, settle_ms) -> (frame, seq, ts)`：**轮询直到帧的读取时间戳 `ts>after_ts`** 才返回。**正确性来自时间戳门控**——只要后台线程持续读取，必然丢弃点灯前的旧帧，**不依赖 `CAP_PROP_BUFFERSIZE=1` 生效**；二者叠加更稳（修 Gemini#1 滞后帧）。`test_capture_service.py` 注入「点灯标记后延迟」验证返回的是标记后的新帧。
  - **锁曝光/白平衡**（Gemini 新#1）：`CameraManager.open()` 在 AUTOFOCUS 之后设 `cv2.CAP_PROP_AUTO_EXPOSURE`=手动档 + `CAP_PROP_AUTO_WB=0` + 固定 `CAP_PROP_EXPOSURE`，避免 LED 强光触发自动降曝把黑子压成死黑。**曝光值随相机而异（无可移植常量），列为配置项，在 P0/几何锁阶段标定**；锁定须**贯穿整个会话**（QA 无灯帧与带灯帧用同一曝光）。`test_capture_service.py` 验证 open() 后 AUTO_EXPOSURE 保持锁定。
  - `capture_to(path, after_ts) -> str`：`grab_fresh` → `Path(path).parent.mkdir(parents=True, exist_ok=True)` → `cv2.imwrite`；写失败抛异常。
  - `grab_burst(n)`（几何锁）。
- **相机互斥（运行时硬互斥，修 Codex#8）**：采集模式**默认拒绝**同时启用 `VisionService`（不只比较同 camera 参数——参数可能别名）。`_lifespan_board()` 若二者都 enabled → `RuntimeError`。CaptureService 为唯一 owner；CLI help 注明用途互斥。
- **gate**：`--capture-camera/--capture-dir`；`app.state.capture`（关停见 §2.1）。

### 3.2 几何迁移
- **复制改造**（来源 `~/Repositories/autoresearch/board-detection/`）：`autocal.py→geometry_autocal.py`、`detect.py→geometry_detect.py`、`calibrate.py→geometry_calibrate.py`、`stones.py→stone_classifier.py`（入 `katrain/vision/`，同步改内部 import）。删 `__main__` 块（消除 `/tmp/*overlay.png`）；`save_session` 的 `HERE/SESSION` 改 `save_path` 入参；`out_size` 锁定/保存统一 950。依赖仅 numpy+cv2。
- **新建** `katrain/vision/geometry_lock.py`：
  - `lock_geometry_from_frames(frames, conf_min=0.80, out_size=950) -> GeometryLock|None`；`GeometryLock` 含 8 持久化字段（`corners/points(19,19,2)/M/Minv/xs/ys/out_size/baseline`）+ 内存态 `confidence/nmatch`。
  - `save_geometry_lock`：**npz 只存 8 字段**（与 autoresearch `session.npz` round-trip 兼容；`confidence` 存旁 `.json`）。`load_geometry_lock`。
- **退役** `grid_calibrator.py`：确认无调用方；**标 deprecated 保留一个周期再删**（修 Codex D7），无悬空引用。

### 3.3 几何锁定接口（前置硬条件，修 Codex#10）
- **依赖 P2**：本接口调用 `led.clear()`，故须 P2 LedService 已启用（`--led-serial-port`）。LED 不可用时**降级**（跳过灭灯，横幅提示「请人工确认 LED 全灭 + 空盘」后继续），不要 500。
- `POST /api/v1/geometry/lock`：**先 `led.clear()`（不可用则降级）+ 要求确认空盘** → `capture.grab_burst` → `lock_geometry_from_frames` → **空盘自检**（black/white≈0，非空则拒锁/警告）→ 存 `~/.katrain/geometry_lock.npz` + sidecar 诊断 json → 返回 `{ok, confidence, nmatch, empty_self_check}`。`VisionSetupPage.tsx` 加「自动锁定几何」按钮 + conf 显示。

### 3.4 P3 验收
1. `tests/test_geometry_lock.py`：save/load round-trip，**npz 恰好 8 字段**，用 autoresearch `session.npz` 校验 schema 一致。
2. `tests/test_capture_service.py`(mock CameraManager)：`grab_fresh` 只返回 `ts>after_ts` 的帧；`capture_to` 自建目录+命名；曝光锁调用；生命周期。
3. 真机：空盘 burst → conf≥0.80 + 空盘自检过；`points` 投影回原图与交叉点吻合。
4. `grep -r grid_calibrator katrain/` 仅剩 deprecated 标记，无功能调用。

---

## P4. 带灯拍采集 + L2 QA + 交付（**硬件就绪**；依赖 P3 几何+stone_classifier）

**目标**：确认→CV 校验(L2)→带灯拍（同步屏障，无滞后/无手入镜）→落盘+富 manifest→交付 autoresearch。

### 4.1 采集 + QA 时序（决策 ③ + 同步屏障，修 Codex#1/Gemini#1/#3）
`POST /api/v1/baipu/capture` body `{game_id, move_index, override?:bool}`，后端按序：
1. **QA（L2，决策③）**：`led.clear(strict)` → `capture.grab_fresh` 取**无灯**帧 → `stone_classifier.classify(frame, geometry)` → 与期望盘面 `steps[0..k]` 差分（刚确认点出现对应色子、被提点已清空）。
   - 一致 → 继续。不一致且 `override!=true` → 返回 `409 {qa:"mismatch", move_index:k, diffs:[{row,col,expected:"B|W|empty",actual:"B|W|empty",reason:"missing|extra|color_mismatch"}]}`（**不落盘**）；前端按 diff 阻断+提示「D4 应黑却空 / K10 多了白子」+ 「改正后确认」/「确认无误继续」。override=true → 继续，`qa_status="operator_override"`（记 diffs）。
   - （阈值来自 P0 基准；P0 判定不可靠时降级为「每 N 手人工复核 overlay」，不自动阻断。）
   - 可选：把这张**无灯 QA 帧**也存为附加 no-LED 样本（配置开关）。
2. **点灯**：`led.set_points([next_point], strict=True)` 等 `SHOW` OK → 得 `show_at`（next 不存在/末手/pass → `led.clear(strict)`，无灯）。
3. **带灯抓帧**：`capture.grab_fresh(after=show_at, settle_ms≈150)`（后台线程已抽空缓冲，确保拿到点灯后的新帧；曝光已锁）→ `capture_to`。
4. **落盘 + manifest**（见 4.2）。返回 `{ok, path, qa_status}`。前端：步骤 1→3 期间禁用 确认/撤回/退出 + 屏幕显示「正在拍照，请勿伸手」；**前端收到 `/baipu/capture` 返回 200（帧已写盘）后**才帧计数跳动 + 播放「咔嚓」声（修 Gemini#3：声音是"可落下一子"的放行信号，必须在帧写盘确认之后，而非点灯瞬间）。

### 4.2 落盘 + 富 manifest（修 Codex#2/#6 / Gemini#2）
- 路径 `{out_dir}/{game_id}/frame_{seq:03d}.jpg`；**首帧把当时 `geometry_lock` 拷贝固化**到 `{out_dir}/{game_id}/geometry.npz`（修 Gemini#2：避免日后重标定毁旧数据）+ SGF 拷 `game.sgf`(UTF-8 无 BOM)。
- **加固**（Codex#6）：`game_id` Pydantic slug 校验；落盘后校验 resolved path 仍在 `out_dir` 内；**按 game_id 串行锁**；manifest **tmp+atomic replace**；**幂等**：重复 `(game_id, move_index)` 且状态一致 → `200` 返回原记录（不重拍）；冲突（seq/qa_status 不一致或 move_index 越界）→ `409`。
- **manifest.json schema**（权威）：
  ```json
  {
    "game_id": "...", "session_timestamp": "ISO8601", "board_size": 19,
    "sgf_path": "game.sgf", "geometry_path": "geometry.npz", "total_moves": 150,
    "frames": [
      {"file": "frame_000.jpg", "seq": 0,
       "frame_kind": "initial_led|after_move|final_no_led",
       "applied_move_index": -1,            // 已落到盘上的最后一手 index（initial 为 -1）
       "next_guided_move_index": 0,          // 此帧点亮的下一手 index（无灯为 null）
       "led_point": {"row":3,"col":3,"color":"black"} ,  // = 亮灯点；无灯 null
       "board_through_index": -1,            // 盘面含 0..该 index
       "board_hash": "…",
       "qa_status": "ok|operator_override|skipped"}
    ]
  }
  ```
  - `next_move:null` 不再兼表「谱尾」「pass」——由 `frame_kind` + `next_guided_move_index` 显式区分（修 Codex#2）。
  - **字段语义（autoresearch 数据契约，权威）**：`applied_move_index`=当前物理盘上已落的**最后一手** `steps[]` 索引（`initial_led` 为 -1）；`next_guided_move_index`=本帧点亮的下一手 `steps[]` 索引（无灯为 null，**跳过 pass 指向下一物理落子**）；`board_through_index`=盘面含 `steps[0..该值]`（即 = `applied_move_index`）。三者**均索引 `/baipu/load` 的 `steps[]`，非 `frames[]`**。
  - **pass 不产帧**；`frames.length = 1(initial_led) + 非 pass 落子数`，与 `steps.length` 不必相等，对齐靠 `applied_move_index` 而非数组下标。
  - **示例** `steps=[M0(0), M1(1), pass(2), M3(3)]` → `frames`：`[0]` initial_led(applied=-1, next=0) · `[1]` after_move(applied=0, next=1) · `[2]` after_move(applied=1, **next=3** 跳过 pass) · `[3]` final_no_led(applied=3, next=null)。
  - `frame_kind` 仅三值；`manual_check` 已删（P4.3「每 N 手人工复核」走 overlay，不写训练帧），避免悬空枚举。
- **强制首帧**（修 Gemini#4）：`GUIDING(0)` 首次确认前抓一张 `frame_kind=initial_led`（空盘 + move0 灯），**默认开**（好负样本）。末手 `final_no_led`（全子无灯）。pass 不拍（manifest 不产帧，状态机仅 ADVANCE）。

### 4.3 数据去相关（决策 ①(a)）
- protocol/manifest 写明并提示操作者：**跨会话/跨局变换光照、角度、曝光档、盘面填充度**；少局多样 > 多局高相关。`manifest` 可记 `capture_condition` 标签（lighting/angle…）便于 autoresearch 分层。

### 4.4 交付契约（给 autoresearch）
- 产物：`{game_id}/frame_NNN.jpg` + `game.sgf` + `geometry.npz` + `manifest.json`。
- **本 track 不写 YOLO 标签**。autoresearch 用 manifest(`board_through_index`/`led_point`/固化 `geometry.npz`)+SGF 产 4 类标签（black/white/led_red/led_green）；坐标为规范 (row 顶部基, col)。

### 4.5 P4 验收
1. **同步屏障**：人为延迟点灯，验证拍到的永远是**点灯后**的新帧（非旧灯/无灯）；曝光锁下黑子不糊。
2. **L2 QA**：故意摆错颜色/偏一路/漏提子 → 阻断+提示；改正后放行；override 路 manifest 记 `operator_override`。
3. 每手 `frame_NNN.jpg` 落盘，首帧 initial_led、末帧 final_no_led；`geometry.npz`/`game.sgf` 随谱固化；manifest 富字段齐全且与盘面一致；seq 去重、并发安全、原子写。
4. 拍照期间禁用按钮；咔嚓声 + 帧计数；「请勿伸手」提示。
5. **测试(阻断)** `tests/test_baipu_api.py`(AsyncClient + mock camera/led/geometry)：QA 阻断/override 分支、同步屏障(mock 帧 ts)、manifest schema/原子写/seq 幂等、路径包含校验。

---

## P5. LED 锚点自动标定 + 统一相机管线（2026-06-21 新增）

**Goal:** 用户首次进入任一依赖实体棋盘的功能时，清空棋盘后由 LED 四角定位、九星验证和空盘 baseline 自动建立人视角 GeometryLock；相机或棋盘位移后可从状态栏/设置页手动重标定，同时让摆谱采集和现有实时 YOLO 识别共享唯一摄像头。

**Architecture:** `CameraHub` 是 HBV 摄像头的唯一所有者，`CaptureService` 与 `VisionService` 只消费它提供的最新帧。`LedGeometryCalibrator` 使用严格 LED ACK 和点灯后新帧做 13 点 RANSAC Homography，`GeometryCalibrationService` 管理异步状态、最后有效锁和位移监测；前端 `PhysicalBoardGuard` 统一保护所有实体棋盘路由。

**Tech Stack:** Python 3.11、OpenCV、NumPy、FastAPI、React/TypeScript、MUI、pytest、Vitest。

### P5 范围和硬约束

- 规范坐标始终是**人坐视角**：`row=0` 上、`col=0` 左；LED LUT 已确认 `(0,0)→raw 0`、`(0,18)→raw 360`。摄像头位于棋盘右侧不改变规范坐标。
- 四角定位后扫描九星位：`D16/K16/Q16 · D10/K10/Q10 · D4/K4/Q4`，共 13 个已知对应点；用全部点 RANSAC 拟合，不只信任四角。
- 标定使用明确 `rgb`，不复用 `white=白棋引导色=绿色` 的业务语义；优先低亮度绿色，低置信时重试红/蓝，禁止高亮白光直接过曝。
- 任何失败/取消/异常都在 `finally` 中 `led.clear(strict=True)`；新锁全部验证通过前不得覆盖最后有效锁。
- 空盘主要由用户确认；有可用 YOLO 时额外要求 0 stones。经典 CV 对刚生成的 baseline 自检不能证明原盘无子，不作虚假保证。
- 自动标定只在一次服务运行期首次进入实体棋盘功能时触发一次；路由切换复用。对局中不得自动闪灯，位移仅进入 `degraded` 并提示清盘重标定。
- 摆谱仅要求 camera+LED+geometry；对弈/死活/研究的实时落子还要求 recognition model ready。两种能力分开上报。

### Task 1：CameraHub 成为唯一相机所有者

**Files:**
- Create: `katrain/web/core/camera_hub.py`
- Modify: `katrain/web/core/capture_service.py`
- Modify: `katrain/vision/worker_inprocess.py`
- Modify: `katrain/vision/service.py`
- Modify: `katrain/web/server.py`
- Test: `tests/test_camera_hub.py`
- Test: `tests/test_capture_service.py`
- Test: `tests/test_vision/test_shared_camera.py`

- [x] **Step 1.1: 写 CameraHub 生命周期和共享帧源失败测试**

  覆盖：相机只 `open()`/`close()` 一次；`read_frame()`、`grab_fresh()`、`grab_burst()` 保留 seq/ts；多个消费者 stop 不得关闭相机。

- [x] **Step 1.2: 运行 RED**

  Run: `/opt/miniconda3/envs/py311_katago/bin/python -m pytest -q tests/test_camera_hub.py tests/test_capture_service.py`
  Expected: FAIL（`CameraHub` 尚不存在或 CaptureService 仍直接拥有相机）。

- [x] **Step 1.3: 最小实现 CameraHub 并把 CaptureService 改为委托**

  `CameraHub.start/stop/is_connected/read_frame/grab_fresh/grab_burst` 是唯一相机生命周期边界；`CaptureService.capture_to` 只负责原子落盘。

- [x] **Step 1.4: 写 VisionService 共享帧源失败测试并运行 RED**

  注入 CameraHub 后 `InProcessAdapter` 不调用 `open/close`；无共享帧源时保持原行为。板端启用 capture+vision 时使用后台线程消费者，先不引入高带宽 multiprocessing Queue。

- [x] **Step 1.5: 实现共享帧源并移除 server 的 vision/capture RuntimeError**

  `_lifespan_board()` 先启动 CameraHub，再向 CaptureService/VisionService 注入；配置的设备或分辨率不一致时启动失败并给出明确错误。

- [x] **Step 1.6: 运行 GREEN 和回归**

  Run: `/opt/miniconda3/envs/py311_katago/bin/python -m pytest -q tests/test_camera_hub.py tests/test_capture_service.py tests/test_vision/test_shared_camera.py`
  Expected: PASS。

### Task 2：LED 13 点标定算法

**Files:**
- Create: `katrain/vision/led_geometry_calibrator.py`
- Modify: `katrain/web/core/led_service.py`
- Modify: `katrain/vision/geometry_lock.py`
- Test: `tests/test_led_geometry_calibrator.py`
- Test: `tests/test_led_service.py`

- [x] **Step 2.1: 写 raw RGB 与光斑中心检测失败测试**

  测试 `LedService.set_rgb_points([{row,col,rgb}])` 发出精确 `SETI`；合成 dark/lit 图中存在反光噪声时，检测器仍返回主连通域亮度加权中心；低信噪比、多主光斑返回结构化失败。

- [x] **Step 2.2: 运行 RED**

  Run: `/opt/miniconda3/envs/py311_katago/bin/python -m pytest -q tests/test_led_service.py tests/test_led_geometry_calibrator.py`
  Expected: FAIL（raw RGB/检测器尚不存在）。

- [x] **Step 2.3: 实现 raw RGB、帧差检测与颜色重试**

  每个锚点执行 `CLEAR→fresh dark→SETI/SHOW strict→fresh lit`；优先 `(0,96,0)`，失败再试 `(96,0,0)`、`(0,0,96)`；返回 centroid、peak、area、margin 和颜色尝试记录。

- [x] **Step 2.4: 写 13 点 RANSAC 和人视角测试并运行 RED**

  合成摄像机透视下，四角+九星包含两个离群点仍恢复 19×19 points；断言 `(0,0)`、`(0,18)`、`R16=(3,16)` 的投影和顺序；残差超阈值拒绝。

- [x] **Step 2.5: 实现标定、baseline 和 GeometryLock 诊断**

  用 `cv2.findHomography(camera_points, canonical_points, RANSAC)` 生成 `M/Minv/points`；空灯采 8 帧，以前 7 帧 baseline、最后 1 帧留出验证，再用全部 8 帧生成最终 baseline。sidecar 记录 camera identity/resolution/exposure、13 点、inlier、RMS/max residual、orientation 和重试信息。

- [x] **Step 2.6: 运行 GREEN 和几何回归**

  Run: `/opt/miniconda3/envs/py311_katago/bin/python -m pytest -q tests/test_led_geometry_calibrator.py tests/test_led_service.py tests/test_geometry_lock.py`
  Expected: PASS。

### Task 3：异步标定服务、API 与最后有效锁

**Files:**
- Create: `katrain/web/core/geometry_calibration_service.py`
- Modify: `katrain/web/api/v1/endpoints/geometry.py`
- Modify: `katrain/web/server.py`
- Modify: `katrain/web/api/v1/endpoints/baipu.py`
- Test: `tests/test_geometry_calibration_service.py`
- Test: `tests/test_geometry_api.py`

- [x] **Step 3.1: 写状态机和原子替换失败测试**

  状态：`required/waiting_empty/dark_reference/flashing_corners/verifying/building_baseline/ready/degraded/failed/cancelled`。覆盖并发 start=409、取消灭灯、失败保留旧锁、成功才替换 app 使用的 lock、服务重启后 `session_calibrated=false`。

- [x] **Step 3.2: 运行 RED**

  Run: `/opt/miniconda3/envs/py311_katago/bin/python -m pytest -q tests/test_geometry_calibration_service.py tests/test_geometry_api.py`
  Expected: FAIL。

- [x] **Step 3.3: 实现 GeometryCalibrationService**

  后台单任务运行同步标定器；锁保护 status；通过成功回调热替换 `app.state.geometry`；保存仍使用 `save_geometry_lock` 原子写。cancel 使用锚点之间检查 Event 的协作式取消，stop 必须等待任务并清灯。

- [x] **Step 3.4: 扩展 API**

  - `POST /geometry/calibrate {trigger:"auto|manual", empty_confirmed:true}` → `202`
  - `POST /geometry/cancel`
  - `GET /geometry/status` → phase/progress/session_calibrated/last_valid/metrics/error/capabilities
  - 旧 `POST /geometry/lock` 暂保留为兼容入口，内部调用同一服务，不再维护第二套算法。

- [x] **Step 3.5: 运行 GREEN 和摆谱 API 回归**

  Run: `/opt/miniconda3/envs/py311_katago/bin/python -m pytest -q tests/test_geometry_calibration_service.py tests/test_geometry_api.py tests/test_baipu_api.py tests/test_baipu_capture.py`
  Expected: PASS。

### Task 4：位移监测和实时识别复用 GeometryLock

**Files:**
- Create: `katrain/vision/geometry_drift.py`
- Modify: `katrain/vision/worker_inprocess.py`
- Modify: `katrain/vision/service.py`
- Modify: `katrain/vision/ipc.py`
- Modify: `katrain/web/core/geometry_calibration_service.py`
- Test: `tests/test_geometry_drift.py`
- Test: `tests/test_vision/test_shared_camera.py`

- [x] **Step 4.1: 写位移判定失败测试**

  用合成网格 reference/current 验证：光照整体变化不触发；小于 `0.10 cell` 不触发；连续 3 帧超过阈值进入 degraded；单帧异常不触发。

- [x] **Step 4.2: 运行 RED**

  Run: `/opt/miniconda3/envs/py311_katago/bin/python -m pytest -q tests/test_geometry_drift.py`
  Expected: FAIL。

- [x] **Step 4.3: 实现 GeometryDriftMonitor**

  使用静态网格/木纹特征匹配 + RANSAC 估计参考帧到当前帧位移，输出 shift、inlier ratio、confidence；仅监测，不在对局中点灯。

- [x] **Step 4.4: 写实时识别使用锁定 M 的失败测试**

  注入 GeometryLock 后直接 `warpPerspective(frame, M)`，不调用 `BoardFinder.find_focus`；没有锁时状态为 `geometry_required`，而不是回退到可能旋转错误的自动轮廓。

- [x] **Step 4.5: 实现 VisionService geometry 更新和能力拆分**

  `VisionStatus` 分别上报 `camera_ready/geometry_ready/model_ready/recognition_ready`。GeometryCalibrationService 成功后通知 VisionService 热更新 M；模型缺失不影响标定与摆谱采集。

- [x] **Step 4.6: 运行 GREEN**

  Run: `/opt/miniconda3/envs/py311_katago/bin/python -m pytest -q tests/test_geometry_drift.py tests/test_vision/test_shared_camera.py tests/test_vision/test_pipeline.py tests/test_vision/test_sync.py`
  Expected: PASS。

### Task 5：PhysicalBoardGuard、标定进度和手动入口

**Files:**
- Create: `katrain/web/ui/src/api/geometryApi.test.ts`
- Modify: `katrain/web/ui/src/api/geometryApi.ts`
- Create: `katrain/web/ui/src/kiosk/context/GeometryContext.tsx`
- Create: `katrain/web/ui/src/kiosk/components/vision/PhysicalBoardGuard.tsx`
- Modify: `katrain/web/ui/src/kiosk/KioskApp.tsx`
- Modify: `katrain/web/ui/src/kiosk/pages/VisionSetupPage.tsx`
- Modify: `katrain/web/ui/src/kiosk/pages/SettingsPage.tsx`
- Modify: `katrain/web/ui/src/kiosk/components/layout/StatusBar.tsx`
- Test: `katrain/web/ui/src/kiosk/__tests__/PhysicalBoardGuard.test.tsx`
- Test: `katrain/web/ui/src/kiosk/__tests__/SettingsPage.test.tsx`

- [x] **Step 5.1: 写 API 与 Guard 失败测试**

  首次进入受保护路由显示“请清空棋盘”；用户确认后启动标定并显示 0–13 点进度；ready 后放行；failed/degraded 保持阻断并可重试；路由切换不重复标定。

- [x] **Step 5.2: 运行 RED**

  Run: `cd katrain/web/ui && npm test -- src/api/geometryApi.test.ts src/kiosk/__tests__/PhysicalBoardGuard.test.tsx`
  Expected: FAIL。

- [x] **Step 5.3: 实现 GeometryContext 和 Guard**

  标定活动期 300ms poll，空闲期 3s；包装实体功能页：AI/PVP/跨平台 game、死活 problem、研究 session、摆谱 session。列表/设置/棋谱查看/直播不阻断。

- [x] **Step 5.4: 实现手动重标定入口**

  `VisionSetupPage`、设置页和 StatusBar degraded 图标统一调用同一 API；对局中点击时先提示将暂停且要求清盘。相机、几何、识别模型分别显示健康状态。

- [x] **Step 5.5: 运行 GREEN、lint 和构建**

  Run: `cd katrain/web/ui && npm test -- src/api/geometryApi.test.ts src/kiosk/__tests__/PhysicalBoardGuard.test.tsx src/kiosk/__tests__/SettingsPage.test.tsx`
  Run: `cd katrain/web/ui && npm run lint && npm run build && npm run build:kiosk-2d`
  Expected: PASS。

### Task 6：全链路验证、文档和真机验收

**Files:**
- Modify: `superpowers/tracks/sbc-baipu-led-guide/plan.md`（P5 执行记录）
- Modify: `katrain/vision/README.md`
- Test: relevant backend/frontend suites

- [x] **Step 6.1: 后端回归**

  Run: `/opt/miniconda3/envs/py311_katago/bin/python -m pytest -q tests/test_camera_hub.py tests/test_capture_service.py tests/test_led_service.py tests/test_led_geometry_calibrator.py tests/test_geometry_lock.py tests/test_geometry_calibration_service.py tests/test_geometry_api.py tests/test_geometry_drift.py tests/test_baipu_api.py tests/test_baipu_capture.py tests/test_vision`
  Expected: 0 failures。

- [x] **Step 6.2: 前端回归和构建**

  Run: `cd katrain/web/ui && npm test`
  Run: `cd katrain/web/ui && npm run lint && npm run build && npm run build:kiosk-2d`
  Expected: 0 failures。

- [x] **Step 6.3: MacBook 真机验证（移动相机项待操作者执行）**

  1. 启动 board mode，确认 `/led/status connected`、CameraHub camera 0=HBV。
  2. 首次进入摆谱，清盘后自动标定；确认 raw0 左上、raw360 右上、R16 人视角右上。
  3. 检查 13 点 residual、空盘 held-out QA、`geometry_lock.npz/json` 原子更新。
  4. 完成一手 initial_led capture，确认 `qa_status=ok`。
  5. 轻微移动相机，确认不闪灯且状态进入 degraded；手动清盘重标定后恢复 ready。
  6. 有 YOLO 模型时再验证 recognition_ready；无模型时确认摆谱仍可用且 UI 明示 model unavailable。

- [x] **Step 6.4: 更新 P5 执行记录**

  记录测试计数、硬件坐标、残差、相机身份、已知限制和启动命令；不得把诊断采集目录混入训练数据。

---

## P6. SBC 前端实时几何预览与重标定闭环（2026-06-22）

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. Follow every RED/GREEN checkpoint and update checkboxes after each task.

**Goal:** 用户只通过 KaTrain SBC 前端即可同时查看 HBV 原始画面和俯视矫正画面，确认 LED 定位的四角、完整网格和 361 个落子点，并在摄像头位移后完成自动提示与手动确认重标定。

**Architecture:** 继续使用唯一 `CameraHub` 和当前 `GeometryLock`。后端只扩展锚点快照、只读几何布局和按需矫正 MJPEG；前端用透明 Canvas 缩放绘制后端坐标，并让 `PhysicalBoardGuard` 与设置页复用同一个 `GeometryCalibrationWorkspace`。完整设计见 `docs/superpowers/specs/2026-06-22-geometry-live-preview-design.md`。

**Tech Stack:** Python 3.11、FastAPI、OpenCV、NumPy、React 19、TypeScript、MUI、Vitest、Testing Library、in-app Browser。

### Task 1：发布逐点 LED 锚点与几何版本

**Files:**
- Modify: `katrain/vision/led_geometry_calibrator.py`
- Modify: `katrain/web/core/geometry_calibration_service.py`
- Test: `tests/test_led_geometry_calibrator.py`
- Test: `tests/test_geometry_calibration_service.py`

- [x] **Step 1.1: 写 RED——成功锚点观察回调**

  在 `tests/test_led_geometry_calibrator.py` 增加：

  ```python
  def test_calibrator_reports_each_detected_anchor(fake_led, fake_capture):
      observed = []
      result = LedGeometryCalibrator(
          led=fake_led,
          capture=fake_capture,
          anchor_observer=lambda row, col, point, color: observed.append((row, col, point, color)),
      ).calibrate()
      assert result.ok
      assert [(row, col) for row, col, _point, _color in observed] == list(CALIBRATION_ANCHORS)
      assert all(color == "green" for _row, _col, _point, color in observed)
  ```

- [x] **Step 1.2: 运行 RED**

  Run: `/opt/miniconda3/envs/py311_katago/bin/python -m pytest -q tests/test_led_geometry_calibrator.py::test_calibrator_reports_each_detected_anchor`
  Expected: FAIL，`LedGeometryCalibrator.__init__` 不接受 `anchor_observer`。

- [x] **Step 1.3: 最小实现锚点回调**

  `LedGeometryCalibrator.__init__` 增加：

  ```python
  anchor_observer: Callable[[int, int, tuple[float, float], str], None] | None = None
  ```

  保存为 no-op；`_locate_anchor` 成功时调用：

  ```python
  point = (float(result.centroid[0]), float(result.centroid[1]))
  self.anchor_observer(row, col, point, color_name)
  return result.centroid
  ```

- [x] **Step 1.4: 写 RED——服务快照清空和 revision**

  在 `tests/test_geometry_calibration_service.py` 增加一个接受 `anchor_observer` 的 fake calibrator，并断言：

  ```python
  service.start(trigger="manual", empty_confirmed=True)
  service.wait(2)
  status = service.status()
  assert status["detected_anchors"] == [
      {"row": 0, "col": 0, "x": 12.5, "y": 34.5, "color": "green"}
  ]
  assert status["geometry_revision"] == 1

  service.start(trigger="manual", empty_confirmed=True)
  assert service.status()["detected_anchors"] == []
  ```

- [x] **Step 1.5: 运行 RED 并实现服务状态**

  Run: `/opt/miniconda3/envs/py311_katago/bin/python -m pytest -q tests/test_geometry_calibration_service.py`
  Expected: FAIL，缺少字段或 fake factory 参数不匹配。

  实现要求：

  ```python
  self._geometry_revision = 0
  self._detected_anchors: list[dict] = []

  def _anchor_observed(self, row, col, point, color):
      with self._lock:
          self._detected_anchors.append({
              "row": row, "col": col,
              "x": float(point[0]), "y": float(point[1]),
              "color": color,
          })
  ```

  `start()` 清空列表；calibrator factory 接收 `anchor_observer=self._anchor_observed`；成功提升锁后 revision 加一；`status()` 深拷贝列表并返回 revision。

- [x] **Step 1.6: 运行 GREEN 并提交**

  Run: `/opt/miniconda3/envs/py311_katago/bin/python -m pytest -q tests/test_led_geometry_calibrator.py tests/test_geometry_calibration_service.py`
  Expected: PASS。

  ```bash
  git add katrain/vision/led_geometry_calibrator.py katrain/web/core/geometry_calibration_service.py tests/test_led_geometry_calibrator.py tests/test_geometry_calibration_service.py
  git commit -m "publish geometry calibration anchors"
  ```

### Task 2：几何布局接口和俯视矫正流

**Files:**
- Modify: `katrain/web/api/v1/endpoints/geometry.py`
- Test: `tests/test_geometry_api.py`

- [x] **Step 2.1: 写 RED——layout 完整坐标契约**

  扩展测试 fake lock 使用可区分的四角和 `points=np.arange(19*19*2).reshape(19,19,2)`，增加：

  ```python
  def test_layout_returns_human_oriented_grid(client_with_calibration):
      body = client_with_calibration.get("/geometry/layout").json()
      assert body["frame"] == {"width": 1920, "height": 1080}
      assert body["corners"][0]["label"] == "左上"
      assert body["corners"][1]["label"] == "右上"
      assert len(body["points"]) == 19
      assert len(body["points"][0]) == 19
      assert body["revision"] == 1
      assert body["stale"] is False
  ```

  同时断言无有效几何返回 `409`，`phase=degraded` 时 `stale=true` 且仍返回旧点。

- [x] **Step 2.2: 运行 RED**

  Run: `/opt/miniconda3/envs/py311_katago/bin/python -m pytest -q tests/test_geometry_api.py -k layout`
  Expected: FAIL，路由不存在。

- [x] **Step 2.3: 实现 layout 序列化**

  在 geometry endpoint 增加 `_current_geometry(request)` 和 `_serialize_layout(lock, frame, phase, revision)`。四角严格按人视角规范输出：

  ```python
  corner_specs = (
      (0, 0, "左上"),
      (0, 18, "右上"),
      (18, 18, "右下"),
      (18, 0, "左下"),
  )
  ```

  `frame.shape[:2]` 提供真实宽高；NumPy 值全部转 Python `float`；`points` 固定 `[19][19][2]`。

- [x] **Step 2.4: 写 RED——矫正帧 helper**

  ```python
  def test_encode_warped_frame_uses_lock_size():
      frame = np.zeros((720, 1280, 3), np.uint8)
      lock = _ok_lock(out_size=64, M=np.eye(3))
      jpeg = geometry._encode_warped_frame(frame, lock)
      decoded = cv2.imdecode(np.frombuffer(jpeg, np.uint8), cv2.IMREAD_COLOR)
      assert decoded.shape[:2] == (64, 64)
  ```

  再测试 `/geometry/warped-stream` 在无 lock 时返回 `409`。

- [x] **Step 2.5: 运行 RED 并实现 warped stream**

  Run: `/opt/miniconda3/envs/py311_katago/bin/python -m pytest -q tests/test_geometry_api.py -k warped`
  Expected: FAIL，helper/路由不存在。

  `_encode_warped_frame` 必须只做现有逻辑：

  ```python
  warped = cv2.warpPerspective(frame, lock.M, (lock.out_size, lock.out_size))
  ok, jpeg = cv2.imencode(".jpg", warped, [cv2.IMWRITE_JPEG_QUALITY, 65])
  if not ok:
      raise RuntimeError("failed to encode warped geometry frame")
  return jpeg.tobytes()
  ```

  endpoint 在创建 `StreamingResponse` 前验证 lock；生成器每 200ms 读取共享 capture，检查 `await request.is_disconnected()`，不创建 capture 或后台线程。

- [x] **Step 2.6: 运行 GREEN 并提交**

  Run: `/opt/miniconda3/envs/py311_katago/bin/python -m pytest -q tests/test_geometry_api.py tests/test_capture_service.py`
  Expected: PASS。

  ```bash
  git add katrain/web/api/v1/endpoints/geometry.py tests/test_geometry_api.py
  git commit -m "expose live geometry layout previews"
  ```

### Task 3：前端几何 API 与纯绘图模型

**Files:**
- Modify: `katrain/web/ui/src/api/geometryApi.ts`
- Modify: `katrain/web/ui/src/api/geometryApi.test.ts`
- Create: `katrain/web/ui/src/kiosk/components/vision/geometryOverlay.ts`
- Create: `katrain/web/ui/src/kiosk/components/vision/geometryOverlay.test.ts`

- [x] **Step 3.1: 写 RED——API 类型和 layout 请求**

  `geometryApi.test.ts` mock fetch 返回 layout，并断言 `GeometryAPI.layout()` 请求 `/api/v1/geometry/layout`。需要定义：

  ```typescript
  export interface GeometryPoint { row: number; col: number; x: number; y: number }
  export interface GeometryAnchor extends GeometryPoint { color: string }
  export interface GeometryCorner extends GeometryPoint { label: string }
  export interface GeometryLayout {
    revision: number;
    phase: GeometryPhase;
    stale: boolean;
    frame: { width: number; height: number };
    out_size: number;
    corners: GeometryCorner[];
    points: [number, number][][];
  }
  ```

  `GeometryStatus` 增加 `geometry_revision` 和 `detected_anchors`。

- [x] **Step 3.2: 运行 RED，最小实现 API，运行 GREEN**

  Run: `cd katrain/web/ui && npm test -- --run src/api/geometryApi.test.ts`
  Expected RED: `GeometryAPI.layout is not a function`。

  实现 `layout: () => json(fetch(...))` 后重跑，Expected: PASS。

- [x] **Step 3.3: 写 RED——contain 缩放和绘图元素**

  `geometryOverlay.test.ts` 覆盖：

  ```typescript
  expect(fitContain(1000, 600, 1920, 1080)).toEqual({ scale: 1000 / 1920, offsetX: 0, offsetY: 18.75 });
  const model = buildRawGeometryModel(layout, 'ready', { width: 1000, height: 600 });
  expect(model.lines).toHaveLength(38);
  expect(model.points).toHaveLength(361);
  expect(model.corners.map((c) => c.label)).toEqual(['左上', '右上', '右下', '左下']);
  expect(model.starPoints).toHaveLength(9);
  expect(buildRawGeometryModel(layout, 'degraded', viewport).tone).toBe('stale');
  ```

  active 锚点模型单独断言只含 `detected_anchors`，不含完整网格。

- [x] **Step 3.4: 运行 RED 并实现纯函数**

  Run: `cd katrain/web/ui && npm test -- --run src/kiosk/components/vision/geometryOverlay.test.ts`
  Expected: FAIL，模块不存在。

  实现 `fitContain`、`buildRawGeometryModel`、`buildWarpedGeometryModel`；只进行缩放、偏移和绘图 primitive 组装，不计算单应矩阵。

- [x] **Step 3.5: 运行 GREEN、lint 并提交**

  Run: `cd katrain/web/ui && npm test -- --run src/api/geometryApi.test.ts src/kiosk/components/vision/geometryOverlay.test.ts`
  Run: `cd katrain/web/ui && npx eslint src/api/geometryApi.ts src/api/geometryApi.test.ts src/kiosk/components/vision/geometryOverlay.ts src/kiosk/components/vision/geometryOverlay.test.ts`
  Expected: PASS，0 lint errors。

  ```bash
  git add katrain/web/ui/src/api/geometryApi.ts katrain/web/ui/src/api/geometryApi.test.ts katrain/web/ui/src/kiosk/components/vision/geometryOverlay.ts katrain/web/ui/src/kiosk/components/vision/geometryOverlay.test.ts
  git commit -m "add frontend geometry overlay model"
  ```

### Task 4：共享双画面标定工作区

**Files:**
- Create: `katrain/web/ui/src/kiosk/components/vision/CameraGeometryOverlay.tsx`
- Create: `katrain/web/ui/src/kiosk/components/vision/GeometryVideoPanel.tsx`
- Create: `katrain/web/ui/src/kiosk/components/vision/GeometryCalibrationWorkspace.tsx`
- Create: `katrain/web/ui/src/kiosk/__tests__/GeometryCalibrationWorkspace.test.tsx`
- Modify: `katrain/web/ui/src/kiosk/context/GeometryContext.tsx`
- Modify: `katrain/web/ui/src/kiosk/components/vision/PhysicalBoardGuard.tsx`
- Modify: `katrain/web/ui/src/kiosk/pages/VisionSetupPage.tsx`
- Modify: `katrain/web/ui/src/kiosk/__tests__/PhysicalBoardGuard.test.tsx`

- [x] **Step 4.1: 写 RED——双画面、空盘确认和状态**

  在 Workspace 测试 mock GeometryContext，断言：

  ```typescript
  expect(screen.getByText('摄像头原始画面')).toBeInTheDocument();
  expect(screen.getByText('俯视矫正画面')).toBeInTheDocument();
  expect(screen.getByAltText('摄像头原始画面')).toHaveAttribute('src', '/api/v1/geometry/stream');
  expect(screen.getByRole('button', { name: '已清空，开始自动标定' })).toBeEnabled();
  ```

  点击按钮才调用 `startCalibration('auto')`；`degraded` 显示“摄像头或棋盘位置已变化”；camera/LED capability 不满足时按钮禁用；active 显示 `current/13` 和取消按钮；ready 显示 RMS/置信度及“重新标定”。

- [x] **Step 4.2: 运行 RED**

  Run: `cd katrain/web/ui && npm test -- --run src/kiosk/__tests__/GeometryCalibrationWorkspace.test.tsx`
  Expected: FAIL，组件不存在。

- [x] **Step 4.3: 实现视频卡片和 Canvas**

  `GeometryVideoPanel` 负责标题、`<img>`、错误重试和 overlay slot。`CameraGeometryOverlay` 使用 `ResizeObserver`，在 effect 中根据 `geometryOverlay.ts` 模型绘制；必须设置 canvas 的设备像素比并保持 CSS 尺寸，不能从视频帧读取像素。

  原始流固定 `/api/v1/geometry/stream`；有 layout 时矫正流使用 `/api/v1/geometry/warped-stream?revision=<revision>`，无 layout 显示等待文案。

- [x] **Step 4.4: 实现 Workspace 数据与交互**

  - status 的 revision/phase 变化时调用 `GeometryAPI.layout()`；409 表示尚无布局，不显示通用错误。
  - active 时用 status `detected_anchors` 绘制部分锚点。
  - ready/degraded 用 layout 绘制完整网格；degraded tone 为红色。
  - 启动按钮本身就是用户空盘确认，调用现有 calibrate API；绝不自动 POST。
  - cancel 调用 GeometryContext 的 `cancelCalibration()`。

- [x] **Step 4.5: 运行 GREEN**

  Run: `cd katrain/web/ui && npm test -- --run src/kiosk/__tests__/GeometryCalibrationWorkspace.test.tsx`
  Expected: PASS。

- [x] **Step 4.6: 接入 Guard 和设置页**

  `PhysicalBoardGuard` 保留 ready 放行判断，其他状态直接渲染：

  ```tsx
  return <GeometryCalibrationWorkspace mode="guard" requireRecognition={requireRecognition} />;
  ```

  `VisionSetupPage` 删除独立 stream、detected-board polling 和旧电子棋盘布局，改为同一 Workspace 的 `mode="settings"`，只保留页面返回导航。`GeometryContext` active 300ms、ready/degraded/required 1000ms 轮询。

- [x] **Step 4.7: 更新测试、双构建并提交**

  Run: `cd katrain/web/ui && npm test -- --run src/kiosk/__tests__/GeometryCalibrationWorkspace.test.tsx src/kiosk/__tests__/PhysicalBoardGuard.test.tsx src/kiosk/__tests__/SettingsPage.test.tsx src/kiosk/__tests__/StatusBar.test.tsx`
  Run: `cd katrain/web/ui && npx eslint src/kiosk/components/vision/CameraGeometryOverlay.tsx src/kiosk/components/vision/GeometryVideoPanel.tsx src/kiosk/components/vision/GeometryCalibrationWorkspace.tsx src/kiosk/context/GeometryContext.tsx src/kiosk/components/vision/PhysicalBoardGuard.tsx src/kiosk/pages/VisionSetupPage.tsx`
  Run: `cd katrain/web/ui && npm run build && npm run build:kiosk-2d`
  Expected: tests/lint/build PASS，`verify:kiosk-2d` 无 three.js。

  ```bash
  git add katrain/web/ui/src/kiosk
  git commit -m "add live geometry calibration workspace"
  ```

### Task 5：真实浏览器、真机闭环和完整回归

**Files:**
- Modify: `katrain/vision/README.md`
- Modify: `superpowers/tracks/sbc-baipu-led-guide/plan.md`（P6 执行记录）
- Test: P6 backend/frontend suites and in-app Browser

- [ ] **Step 5.1: 后端完整相关回归**

  Run:

  ```bash
  /opt/miniconda3/envs/py311_katago/bin/python -m pytest -q \
    tests/test_camera_hub.py tests/test_capture_service.py tests/test_led_service.py \
    tests/test_led_geometry_calibrator.py tests/test_geometry_lock.py \
    tests/test_geometry_calibration_service.py tests/test_geometry_api.py \
    tests/test_geometry_drift.py tests/test_baipu_api.py tests/test_baipu_capture.py tests/test_vision
  ```

  Expected: 0 failures。

- [ ] **Step 5.2: 前端回归、lint 和构建**

  Run: `cd katrain/web/ui && npm test`，记录全仓结果并与 P5 基线 `78 failed / 286 passed` 比较，P6 不得新增失败。
  Run: 本次所有变更文件的 `npx eslint ...`，Expected: 0 errors。
  Run: `npm run build && npm run build:kiosk-2d`，Expected: PASS。
  Run: `npm run lint`，记录全仓既有错误数量，不把无关修复混入 P6。

- [ ] **Step 5.3: 重启 P6 board mode 真机服务**

  停止当前 8001 服务后，从本工作树启动：

  ```bash
  KATRAIN_MODE=board /opt/miniconda3/envs/py311_katago/bin/python -m katrain \
    --ui web --host 127.0.0.1 --port 8001 --disable-engine \
    --led-serial-port /dev/cu.usbmodem2101 \
    --led-lut-path /Users/fan/.katrain/led_lut.json \
    --capture-camera 0 --capture-resolution 1920x1080 \
    --capture-dir /Users/fan/.katrain/baipu_captures --log-level info
  ```

  确认 HBV camera 0 和 LED connected；标定开始前棋盘必须为空。

- [ ] **Step 5.4: 使用 in-app Browser 模拟 SBC 操作**

  严格按 `browser:control-in-app-browser` 操作真实 `http://127.0.0.1:8001`：

  1. 设定 SBC 横屏视口（目标 1920×1080；另测窄屏堆叠）。
  2. 使用现有登录会话进入设置→棋盘标定；若会话失效，只能由用户提供/完成登录，不从代码或数据库提取密码。
  3. 验证页面身份、非空白、无框架错误 overlay、控制台无 P6 错误。
  4. 截图验证左右两路 HBV 实时画面、四角标签、38 条网格线和 361 点 Canvas。
  5. 点击“重新标定”后确认不会立即闪灯；点击“已清空，开始自动标定”才启动 LED 扫描。
  6. 在扫描中采集截图，确认已发现锚点逐个显示；完成后确认两个画面与绿色网格。
  7. 通过后端测试注入不得伪造真机视觉验收；摄像头实际位移需用户物理移动时，保留 ready→degraded UI 的自动化组件测试，并在执行记录明确人工限制。
  8. 截图保存到 `/tmp`，不加入 git，不混入训练数据。

- [ ] **Step 5.5: 文档、执行记录和最终提交**

  README 增加前端操作说明；P6 执行记录包含测试计数、浏览器视口、控制台结果、真机 metrics、截图路径和未完成的物理动作。更新 P6 状态和所有 checkbox。

  ```bash
  git diff --check
  git status --short
  git add katrain/vision/README.md superpowers/tracks/sbc-baipu-led-guide/plan.md
  git commit -m "document live geometry preview verification"
  ```

---

## 6. 不在范围
YOLO 标签/训练/RKNN（autoresearch）；固件再改（已烧）；物理确认键（用触屏）；后端 baipu 数据表（用 /baipu/load + 本地 SGF）；非 19×19；完整任意跳转 repair 流程（只做单步引导撤回）；P5 首版不实现跨进程零拷贝帧环（共享 CameraHub 时 VisionAdapter 使用后台线程，性能数据证明需要后再升级 shared-memory worker）。

## 7. 横切：构建/测试/验证
- **前端构建边界**：新页只在 `src/kiosk/` + 共享区；改共享文件 → `npm run lint && npm run build && npm run build:kiosk-2d`(含 verify:kiosk-2d)。建议写进 CLAUDE.md 合并清单。
- **后端**：`CI=true uv run pytest tests`；新服务 mock(serial/camera/geometry)。**各阶段测试为验收阻断项**。
- **格式/i18n**：`uv run black -l 120 katrain tests`；`uv run python i18n.py -todo`。
- `goBoard.ts` 收敛降级为**可选清理**（决策②后非关键路径）：若做，先补单测再让 LiveBoard/tsumego 改用 + 双构建。

## 8. 风险
- **采集时序**（最高）：LED SHOW ack + 点灯后新帧 + 曝光锁 + 手入镜屏障，缺一会污染。
- **QA 依赖经典 CV 可靠性**：P0 基准调阈值 + 人工 override 兜底；不可靠则降级人工复核。
- **相机争用**：CaptureService 单一 owner + 运行时拒绝 vision+capture 同开。
- **几何版本漂移**：geometry 随谱固化到 `{game_id}/`。
- **坐标系**：规范 (row 顶部) 全链路；branded types + round-trip + 硬件验证。
- **离线**：board-mode kifu online-only → 必须本地 SGF 来源。
- **后端真值正确性**：`/baipu/load` 复用引擎，单测覆盖让子/提子/pass。

---

## 附录 A：确认的 LED LUT 公式
实测确认（2026-06-15）。链序 `UL→LL→LR→UR`；蛇形 `serp`；UL/LL 正常、LR 垂直翻转、UR 180°。**规范坐标 row=0 顶部、col=0 左。**
```python
def serp(lr, lc, cols):
    return lr*cols + lc + 1 if lr % 2 == 0 else (lr+1)*cols - lc
def rc2idx(row, col):                       # row,col ∈ [0,18]，row=0 顶部
    if row <= 9 and col <= 9:   return        serp(row,      col,      10) - 1   # UL  0..99
    if row >= 10 and col <= 9:  return 100  + serp(row-10,   col,      10) - 1   # LL  100..189
    if row >= 10 and col >= 10: return 190  + serp(18-row,   col-10,   9)  - 1   # LR  190..270 (垂直翻转)
    return                              271  + serp(9-row,    18-col,   9)  - 1   # UR  271..360 (180°)
```
校验点：`(0,0)→0 (9,0)→99 (10,0)→100 (18,9)→189 (18,10)→190 (10,18)→270 (9,18)→271 (0,18)→360`。

## 附录 B：新增/改动文件清单
**前端(新增)**：`src/kiosk/pages/BaipuListPage.tsx`、`src/kiosk/pages/BaipuSessionPage.tsx`、`src/api/ledApi.ts`、`src/api/baipuApi.ts`(load/capture/manifest)
**前端(改)**：`src/kiosk/KioskApp.tsx`、`navTabs.tsx`、`src/components/live/LiveBoard.tsx`(+nextMovePoint/capturedPositions props，坐标边界转换)；(可选) goBoard.ts 收敛 + `useTsumegoProblem.ts`
**后端(新增)**：`katrain/web/core/led_service.py`、`katrain/web/core/capture_service.py`、`katrain/web/api/v1/endpoints/led.py`、`katrain/web/api/v1/endpoints/baipu.py`(load/capture/manifest)、`katrain/vision/geometry_{autocal,detect,calibrate}.py`、`katrain/vision/stone_classifier.py`、`katrain/vision/geometry_lock.py`
**后端(改)**：`katrain/web/server.py`(gate+lifespan 启停+相机互斥+兜底灭灯)、`katrain/web/api/v1/api.py`(注册 led/baipu)、`katrain/vision/camera.py`(帧序号/时间戳+曝光锁)、退役 `grid_calibrator.py`、(复用) `katrain/core/game.py`+`sgf_parser.py`(经 /baipu/load)
**测试(新增)**：`tests/test_baipu_load.py`、`tests/test_led_service.py`、`tests/test_capture_service.py`、`tests/test_geometry_lock.py`、`tests/test_baipu_api.py`、`katrain/web/ui/tests/baipu.spec.ts`、坐标 round-trip 单测
**固件**：无(已烧)。

---

## 10. 修订记录（v2→v3）

三方外部评审（Codex/Gemini/gstack）+ 与作者 4 项决策后的系统性改写：
- **决策①**：保留 LED 摆谱(产品功能)；加 **P0 分类器基准(可选门)** + **数据去相关**(§4.3)。
- **决策②**：**逐手真值改后端权威** `/baipu/load`(引擎算提子/让子)，前端哑播放；`goBoard.ts` 收敛降级为可选；修好让子(AB/AW)缺口(Codex#4)。
- **决策③**：**L2 QA 主动阻断 + 操作者 override**(§4.1)，manifest `qa_status`；阈值挂 P0。
- **决策④**：采集导航 **前进 + 单步引导撤回 + 退出重来**；去掉「下一手/跳过」。
- **同步屏障(Codex#1/Gemini#1)**：LED strict SHOW ack + 点灯后新帧(帧序号/时间戳)+ OpenCV 缓冲由后台线程抽空 + 曝光锁(Gemini 新#1)。
- **几何随谱固化(Gemini#2)**：首帧拷 `geometry.npz` 到 `{game_id}/`。
- **富 manifest(Codex#2)**：`frame_kind/applied_move_index/next_guided_move_index/led_point/board_through_index/board_hash/qa_status`；原子写/seq 去重/可恢复。`null` 不再兼表谱尾/pass。
- **手入镜屏障(Gemini#3)**：「请勿伸手」+ 咔嚓声 + 帧计数；capture-pending 禁用按钮。
- **强制首帧(Gemini#4)**：initial_led 默认开。
- **相机单一 owner + 硬互斥(Codex#8)**；**离线 SGF 来源(Codex#9)**；**几何锁前置 led off+空盘自检(Codex#10)**；**grid_calibrator 延迟退役(Codex D7)**。
- **/capture 加固(Codex#6)**：slug/路径包含/串行锁/原子 manifest/seq 幂等。
- **LedService**：去多余 Lock(Gemini#5)、批为单队列项、strict 路等 SHOW OK、**兜底灭灯**(Gemini 新#2)、RGB-by-BRIGHT 澄清(Codex#12)。
- **坐标 branded types + round-trip 测试(Codex#11)**。
- **设计 UX(gstack)**：状态条层级/LED 配色片、失败可见健康点+相机掉线阻断、退出移出+二次确认+resume、提子独立模式、列表过滤+空状态、拍照反馈。

**v3 验证补丁**（4-lens 对抗验证后，decisions lens=clean；以下为采纳的真缺口，其余 ~24 项为「计划层不必含执行级细节」未采纳）：
- **坐标转换公式显式化**：`row=(board_size-1)-y_internal, col=x_internal` 写进 §1.1（封死垂直倒置，最高风险）。
- **`removed[]`/`board_hash` 可行性**：game.py 无 per-node 提子/哈希，须在重放循环逐步采集（§1.1）。
- **manifest 字段语义 + 含 pass 的工作示例**（§4.2，autoresearch 数据契约）；删悬空 `manual_check`。
- **`grab_fresh` 正确性论证**：时间戳门控，不依赖 BUFFERSIZE（§3.1）。
- **曝光锁细化**：cv2 手动曝光/AWB，值随相机标定、贯穿会话（§3.1）。
- **小决断**：离线 SGF 取 (b) 缓存为主(§1.2)；灭灯超时 = 5 分钟(§2.1)；几何锁依赖 P2+降级(§3.3)；QA diff 结构化(§4.1)；幂等 200/冲突 409(§4.2)；咔嚓声在帧写盘后(§4.1)。
```

---

## 11. 执行记录（2026-06-16）

P1–P4 全部实现并提交到 `feature/rk3588-ui`（commits `410550d6` P1 · `93d2c4aa` P2 · `dd7c6fec` P3 · `df25d048` P4 · `4fce7c4e` 评审修复）。**屏幕/Mock 测试通过；真机测试（串口 LED / 实相机 / 空盘几何锁 / 带灯拍）待硬件日。**

**新增/改动（关键）**
- 后端：`katrain/core/baipu.py`（SGF→规范逐手真值 + expected_board + next_placement）；`web/core/led_service.py`、`capture_service.py`、`baipu_capture.py`；`vision/{geometry_autocal,geometry_detect,geometry_calibrate,stone_classifier,geometry_lock,board_qa}.py`（autoresearch 移植 + 锁存）；`vision/camera.py`（seq/ts + grab_fresh 时间戳门控 + 曝光锁）；endpoints `baipu/led/geometry`；`server.py` gate+lifespan+兜底灭灯+相机硬互斥；`grid_calibrator.py` 标 deprecated。
- 前端：`api/{baipuApi,ledApi,geometryApi}.ts`；`kiosk/pages/{BaipuListPage,BaipuSessionPage}.tsx`；`components/live/LiveBoard.tsx`（nextMovePoint/capturedPositions）；navTab/路由；VisionSetupPage「自动锁定几何」。

**测试**：17 core (.venv) + 49 web (py311_katago，需 fastapi/cv2) + 4 vitest + 3 Playwright(就绪)。两套构建绿（`verify:kiosk-2d` 无 three.js）；lint+tsc 净。

**对抗式评审**（5 维 find→verify，10/17 确认已修）：AE clear 入 steps、move_index 边界、LED ack 配对/stop 竞态、doCapture 卸载守卫、分页过滤说明。未修（有据）：camera close() 竞态（既有+已 try/except）、队列 drop TOCTOU（UI 容错路可接受）、多人 game_repo None（既有非本 track）。

**环境拆分**：core/vision 测试跑 `.venv`；`katrain.web.*` 因 `web/__init__.py` 预载 server→需 web 环境（`py311_katago`，fastapi 0.115/cv2 4.13）。

**硬件日联调**：`python -m katrain --ui web --led-serial-port /dev/cu.usbmodem2101 --capture-camera <dev>` → VisionSetupPage 空盘「自动锁定几何」→ 摆谱选谱→逐手带灯拍。需补：真机 LED 单点/星位、空盘锁 conf≥0.80、stones.classify 阈值(P0 基准)、同步屏障实测、Playwright e2e(起服务)。

---

## 12. P5 执行记录（2026-06-21）

**提交**：`9bac1b4c` 共享 CameraHub · `90358544` LED 13 锚点标定 · `4e5fe925` 异步标定服务/API · `abd96e7e` 漂移监测和识别热更新 · `986e7134` 全实体入口 Guard/手动重标定 · `77a9fcb1` 可选 Provider 状态栏。

**实现**：Capture、几何标定和实时识别共用 camera 0 的单一帧源；四角+九星位按绿→红→蓝回退检测，RANSAC 生成完整 19×19 几何；标定后台执行、可取消、失败保留上一有效锁、成功原子替换；会话外旧锁不直接放行。AI/PVP/跨平台对局、死活题、研究和摆谱实体入口统一要求本会话标定，设置页和状态栏均可手动重标定。摆谱只要求 geometry，需识别的入口额外要求 model/recognition ready。

**自动化验证**：后端 P5 相关套件 `207 passed`；P5 前端新增/受影响用例通过，生产构建和 kiosk-2d 构建通过，`verify:kiosk-2d` 确认无 three.js；所有本次变更 TS/TSX 文件 ESLint 通过。全仓 Vitest 的基线为 `78 failed / 286 passed`，P5 分支为 `72 failed / 295 passed`，未新增失败并修复 6 个 StatusBar/KioskLayout 失败。全仓 ESLint 仍有既有 `218 errors / 46 warnings`，不在本 track 扩散修复。

**MacBook 真机**：`HBV HD CAMERA` = AVFoundation/OpenCV camera 0，分辨率 `1920x1080`；ESP32-S3 为 `/dev/cu.usbmodem2101`，LED connected。手动标定 13/13 内点，RMS `1.458 px`、最大 `2.456 px`、confidence `0.9723`；随后自动入口标定 13/13 内点，RMS `1.385 px`、最大 `2.333 px`、confidence `0.9737`。两次均进入 ready 并在结束后灭灯。人视角 `row=0,col=0` 为左上、`row=0,col=18` 为右上；测试谱 R16 解析为 `(row=3,col=16)`，相机像素约 `(562,345)`，真机照片落在正确的人视角右上区域。

**采集验收**：`p5-hw-20260621/frame_000.jpg` 写入成功，manifest 为 `frame_kind=initial_led`、`qa_status=ok`、`next_guided_move_index=0`，冻结 `geometry.npz` 和 `game.sgf`；红灯持续时漂移监测仍保持 ready。未安装 YOLO 模型时明确返回 `model_ready=false/recognition_ready=false`，不阻断摆谱。诊断目录 `p5-hw-20260621` 仅用于验收，不并入训练集。

**启动命令**：

```bash
KATRAIN_MODE=board /opt/miniconda3/envs/py311_katago/bin/python -m katrain \
  --ui web --host 127.0.0.1 --port 8001 --disable-engine \
  --led-serial-port /dev/cu.usbmodem2101 \
  --led-lut-path /Users/fan/.katrain/led_lut.json \
  --capture-camera 0 --capture-resolution 1920x1080 \
  --capture-dir /Users/fan/.katrain/baipu_captures --log-level info
```

**剩余人工验收**：实际轻移相机，确认连续 3 帧超过阈值后进入 degraded，且不闪标定灯；清盘后从设置页重标定恢复 ready。算法路径已有确定性单测，Codex 无法代替操作者移动实体相机。
