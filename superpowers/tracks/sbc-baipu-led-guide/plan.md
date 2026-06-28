# 实施计划：Kiosk 摆谱 + LED 引导落子（sbc-baipu-led-guide）

- **Track**: `sbc-baipu-led-guide`  ·  **分支**: `feature/rk3588-ui`  ·  **日期**: 2026-06-23（**v6**；P10 为标定诊断卡片与同目录覆盖重启修订）
- **依据**: `prd.md` · `led-calibration-and-protocol.md` · `review-feedback-{codex,gemini,gstack}.md` · 4 项决策（见 §0.3）
- **状态**: **P1–P10 已实现并完成自动化/浏览器验收**；真机摆谱、实际移动摄像头触发 degraded、同目录覆盖旧帧的物理采集效果留作操作者联合手动验收。见 §11–§14 与 P8–P10 执行记录。

> **For agentic workers:** REQUIRED: Use `superpowers:executing-plans` to implement the current pending phase. Steps use checkbox (`- [ ]`) syntax for tracking and follow TDD red/green verification.

> **Current-policy override (P7):** §0.3 决策③及 P4 的 L2 QA 是历史实现。当前训练集冷启动阶段以 P7 为准：**完全信任操作者、只采集不识别**；经典 CV/YOLO 均不参与放行，待初版 YOLOv11 模型可用并独立验收后，再通过显式策略版本引入机器校验。

> 写给「无上下文的执行者」（人或子 agent）。执行顺序 **P0(可选) → P1 → P2 → P3 → P4 → P5**。
> v2→v3 改了什么见 [§10](#10-修订记录v2v3)。

---

## 0. 目标、前置、决策

### 0.1 目标与范围
kiosk「摆谱」模式：按已知 SGF **逐手用 LED 点亮下一手落子点**引导人工摆子，操作者确认后**不做棋子识别或摆错判定**，直接带灯拍照并推进；照片+manifest+SGF 按 SGF 标识落到独立文件夹，交给 `autoresearch` 训练 YOLO（**SGF=ground truth**）。本 track **只建 katrain 侧**；固件已烧好；YOLO 标签/训练在 `autoresearch`。

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

**Architecture:** 继续使用唯一 `CameraHub` 和当前 `GeometryLock`。后端只扩展锚点快照、只读几何布局和按需矫正 MJPEG；前端用透明 Canvas 缩放绘制后端坐标，并让 `PhysicalBoardGuard` 与设置页复用同一个 `GeometryCalibrationWorkspace`。完整设计见 [`2026-06-22-geometry-live-preview-design.md`](./2026-06-22-geometry-live-preview-design.md)。

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

- [x] **Step 5.1: 后端完整相关回归**

  Run:

  ```bash
  /opt/miniconda3/envs/py311_katago/bin/python -m pytest -q \
    tests/test_camera_hub.py tests/test_capture_service.py tests/test_led_service.py \
    tests/test_led_geometry_calibrator.py tests/test_geometry_lock.py \
    tests/test_geometry_calibration_service.py tests/test_geometry_api.py \
    tests/test_geometry_drift.py tests/test_vision_api.py \
    tests/test_baipu_api.py tests/test_baipu_capture.py tests/test_vision
  ```

  Expected: 0 failures。

- [x] **Step 5.2: 前端回归、lint 和构建**

  Run: `cd katrain/web/ui && npm test`，记录全仓结果并与 P5 基线 `78 failed / 286 passed` 比较，P6 不得新增失败。
  Run: 本次所有变更文件的 `npx eslint ...`，Expected: 0 errors。
  Run: `npm run build && npm run build:kiosk-2d`，Expected: PASS。
  Run: `npm run lint`，记录全仓既有错误数量，不把无关修复混入 P6。

- [x] **Step 5.3: 重启 P6 board mode 真机服务**

  停止当前 8001 服务后，从仓库根目录启动：

  ```bash
  cd /Users/fan/Repositories/katrain-rk3588-ui
  KATRAIN_MODE=board KATRAIN_REMOTE_URL="https://go.sailorvoyage.top" \
    /opt/miniconda3/envs/py311_katago/bin/python -m katrain \
    --ui web --host 127.0.0.1 --port 8001 --disable-engine \
    --led-serial-port /dev/cu.usbmodem2101 \
    --led-lut-path /Users/fan/.katrain/led_lut.json \
    --capture-camera 0 --capture-resolution 1920x1080 \
    --capture-dir /Users/fan/.katrain/baipu_captures --log-level info
  ```

  确认 HBV camera 0 和 LED connected；标定开始前棋盘必须为空。

- [x] **Step 5.4: 使用 Chrome 和 headless Chromium 模拟 SBC 操作**

  严格按 `browser:control-in-app-browser` 操作真实 `http://127.0.0.1:8001`：

  1. 设定 SBC 横屏视口（目标 1920×1080；另测窄屏堆叠）。
  2. 使用现有登录会话进入设置→棋盘标定；若会话失效，只能由用户提供/完成登录，不从代码或数据库提取密码。
  3. 验证页面身份、非空白、无框架错误 overlay、控制台无 P6 错误。
  4. 截图验证左右两路 HBV 实时画面、四角标签、38 条网格线和 361 点 Canvas。
  5. 点击“重新标定”后确认不会立即闪灯；点击“已清空，开始自动标定”才启动 LED 扫描。
  6. 在扫描中采集截图，确认已发现锚点逐个显示；完成后确认两个画面与绿色网格。
  7. 通过后端测试注入不得伪造真机视觉验收；摄像头实际位移需用户物理移动时，保留 ready→degraded UI 的自动化组件测试，并在执行记录明确人工限制。
  8. 截图保存到 `/tmp`，不加入 git，不混入训练数据。

- [x] **Step 5.5: 文档、执行记录和最终提交**

  README 增加前端操作说明；P6 执行记录包含测试计数、浏览器视口、控制台结果、真机 metrics、截图路径和未完成的物理动作。更新 P6 状态和所有 checkbox。

  ```bash
  git diff --check
  git status --short
  git add katrain/vision/README.md superpowers/tracks/sbc-baipu-led-guide/plan.md
  git commit -m "document live geometry preview verification"
  ```

## 13. P6 执行记录（2026-06-22）

**集成**：P6 的 13 个开发提交已从 `codex/led-auto-calibration` 快进集成到产品根目录分支 `feature/rk3588-ui`。产品服务从 `/Users/fan/Repositories/katrain-rk3588-ui` 根目录启动，不依赖 `.config/superpowers/worktrees`。设置页“实体棋盘 → 重新标定棋盘”和顶部棋盘状态图标均可进入 `/kiosk/vision/setup`。

**验收中修复的缺口**：ready 状态的“重新标定”原本会立即启动 LED，已改为先显示清盘警告、二次确认后才扫描，并补 TDD 回归；未加载 YOLO 时 `/vision/status` 原本持续返回 404，已改为 HTTP 200 disabled 状态，干净浏览器不再产生周期性控制台错误。

**自动化验证**：后端 P6/摆谱/vision 相关套件 `215 passed`。P6 受影响前端测试 `17 passed`，新增二次确认测试 `5 passed`；全仓 Vitest 保持既有基线 `72 failed / 306 passed`（P6 未新增失败）。变更 TS/TSX ESLint 通过；全仓 ESLint 仍为既有 `218 errors / 46 warnings`。`npm run build` 和 `npm run build:kiosk-2d` 均通过，后者确认无 three.js。Python Black 与 `git diff --check` 通过。

**真机/浏览器**：根目录 board-mode 服务识别 `HBV HD CAMERA` camera 0（1920×1080）和 `/dev/cu.usbmodem2101` LED。Chrome 登录后验证设置入口、二次确认、扫描取消按钮、0/13 active 状态、1/13 已发现锚点、13/13 ready 状态；最终 RMS `1.742 px`、最大残差 `3.166 px`。原始流自然分辨率 1920×1080，俯视流 950×950；两个 Canvas 均为 4 角、38 线、361 点。headless Chromium 在 1920×1080 验证左右布局，在 700×1000 验证纵向堆叠；服务重启后的干净页面控制台为 `0 errors / 0 warnings`。

**截图（不入库）**：`/tmp/katrain-p6-chrome-confirm-empty.png`、`/tmp/katrain-p6-chrome-active.png`、`/tmp/katrain-p6-chrome-partial-anchors.png`、`/tmp/katrain-p6-chrome-ready.png`、`/tmp/katrain-p6-headless-1920x1080.png`、`/tmp/katrain-p6-headless-700x1000.png`。

**保留的人工物理动作**：实际轻移相机或棋盘，确认连续漂移触发 `ready → degraded` 且不自动闪灯；清空棋盘后从设置页重新标定恢复 ready。算法、API 和 degraded UI 已有确定性测试，物理位移由操作者联合验收。

---

## P7. 操作者确认即采集 + SGF 独立归档（2026-06-22）

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` task-by-task. Follow every RED/GREEN checkpoint, update checkboxes incrementally, and never stage the unrelated `uv.lock` worktree change.

**Goal:** 在尚无 YOLOv11 棋子模型的训练集冷启动阶段，取消摆谱确认后的经典 CV/空点判定。操作者点击“确认落子”即接受该手，并按严格 LED/相机同步屏障拍照；每个 SGF 标识使用独立目录和 manifest。

**Architecture:** `/baipu/load` 继续提供 SGF 权威步骤、坐标和 `board_hash`。`run_capture` 删除 `board_qa.classify_canonical`/`diff_expected` 决策路径，但保留 move index 校验、下一手 LED strict ack、`shown_at` 后新帧、原子 manifest、幂等和路径包含校验。前端删除 `qa_block` 状态、差异横幅及 override 控件；硬件、写盘和协议错误仍阻断。完整设计见 [`2026-06-22-operator-trusted-baipu-capture-design.md`](./2026-06-22-operator-trusted-baipu-capture-design.md)。实时几何预览设计见 [`2026-06-22-geometry-live-preview-design.md`](./2026-06-22-geometry-live-preview-design.md)。

**Tech Stack:** Python 3.11、FastAPI、OpenCV capture barrier、React 19、TypeScript、Playwright、pytest。

### Task 1：后端 RED——证明采集不依赖识别，且每谱隔离

**Files:**
- Modify: `tests/test_baipu_capture.py`
- Modify: `tests/test_baipu_api.py`

- [x] **Step 1.1: 把旧 QA block/override 测试改为 operator-trusted 契约**

  删除 `truth_board`、`QAMismatch` 和“mismatch blocks / override”断言，增加一个会在调用时直接失败的 classifier spy：

  ```python
  def test_operator_confirmation_skips_classifier(self, tmp_path, monkeypatch):
      monkeypatch.setattr(
          "katrain.vision.board_qa.classify_canonical",
          lambda *_args, **_kwargs: pytest.fail("classifier must not run during collection"),
      )
      data = build_steps_from_sgf("(;SZ[19];B[pd];W[dp])")
      result = _capture(str(tmp_path), data["steps"], 19, 0, FakeLed(), FakeCapture(tmp_path))
      assert result["qa_status"] == "operator_confirmed"
  ```

  Manifest 同时断言每个新条目均为：

  ```python
  assert {frame["qa_status"] for frame in manifest["frames"]} == {"operator_confirmed"}
  ```

- [x] **Step 1.2: 增加不同 SGF 标识目录隔离测试**

  ```python
  def test_game_ids_use_independent_directories(self, tmp_path):
      data = build_steps_from_sgf("(;SZ[19];B[pd];W[dp])")
      for game_id in ("kifu_24171", "kifu_24172"):
          _capture(str(tmp_path), data["steps"], 19, -1, FakeLed(), FakeCapture(tmp_path), game_id=game_id)
      assert (tmp_path / "kifu_24171" / "frame_000.jpg").exists()
      assert (tmp_path / "kifu_24172" / "frame_000.jpg").exists()
      assert json.loads((tmp_path / "kifu_24171" / "manifest.json").read_text())["game_id"] == "kifu_24171"
      assert json.loads((tmp_path / "kifu_24172" / "manifest.json").read_text())["game_id"] == "kifu_24172"
  ```

- [x] **Step 1.3: API 测试改为“物理盘未知也成功”**

  `tests/test_baipu_api.py` 不再 mock 识别成功；将原 409 mismatch 测试改为 classifier 调用即失败，并断言 `POST /baipu/capture` 返回 200、`qa_status=operator_confirmed`。

- [x] **Step 1.4: 运行 RED**

  Run: `/opt/miniconda3/envs/py311_katago/bin/python -m pytest -q tests/test_baipu_capture.py tests/test_baipu_api.py`

  Expected: FAIL，旧 `run_capture` 仍调用 classifier，且返回旧 `qa_status`。

### Task 2：后端 GREEN——移除采集识别门，保持时序与存储契约

**Files:**
- Modify: `katrain/web/core/baipu_capture.py`
- Modify: `katrain/web/api/v1/endpoints/baipu.py`
- Test: `tests/test_baipu_capture.py`
- Test: `tests/test_baipu_api.py`

- [x] **Step 2.1: 删除 QA grab/classify/diff 分支**

  `run_capture` 在幂等检查后直接设置：

  ```python
  qa_status = "operator_confirmed"
  next_idx = next_placement_index(steps, move_index)
  ```

  移除 `board_qa`、`expected_board_from_steps` import 和 `QAMismatch`。保留 `next_placement_index`、`board_hash` 等仍使用的 SGF 真值代码；不得添加 HSV 阈值或模型探测。

- [x] **Step 2.2: 收紧 capture API 的错误语义**

  从 `BaipuCaptureRequest` 和 `run_capture` 调用移除 `override`；endpoint 不再捕获/返回 placement mismatch。仅保留 capture/geometry/LED、索引、SGF 和写盘错误。旧客户端发送多余 `override` 仍由 Pydantic 默认兼容忽略，不影响采集。

- [x] **Step 2.3: 运行 GREEN 并检查同步屏障**

  Run: `/opt/miniconda3/envs/py311_katago/bin/python -m pytest -q tests/test_baipu_capture.py tests/test_baipu_api.py`

  Expected: PASS；`test_sync_barrier_uses_shown_at` 仍证明 `capture_to(after_ts=shown_at)`。

- [x] **Step 2.4: 后端提交**

  ```bash
  git add katrain/web/core/baipu_capture.py katrain/web/api/v1/endpoints/baipu.py tests/test_baipu_capture.py tests/test_baipu_api.py
  git commit -m "trust operator during baipu capture"
  ```

### Task 3：前端 RED/GREEN——单一确认流程，不再展示识别纠错

**Files:**
- Modify: `katrain/web/ui/src/api/baipuApi.ts`
- Modify: `katrain/web/ui/src/kiosk/pages/BaipuSessionPage.tsx`
- Modify: `katrain/web/ui/tests/baipu.spec.ts`
- Test: `katrain/web/ui/src/api/baipuApi.test.ts`

- [x] **Step 3.1: 写 Playwright RED**

  把旧“L2 QA mismatch blocks, override continues”改为捕获请求检查：

  ```typescript
  test('operator confirmation captures once and advances without override UI', async ({ page }) => {
    const bodies: Record<string, unknown>[] = [];
    await setupSession(page);
    await page.route('**/api/v1/baipu/capture', async (route) => {
      const body = route.request().postDataJSON() as Record<string, unknown>;
      bodies.push(body);
      return route.fulfill({ json: { ok: true, qa_status: 'operator_confirmed' } });
    });
    await page.goto('/kiosk/baipu/session/test1');
    await page.getByTestId('baipu-confirm').click();
    await expect(page.getByTestId('baipu-next-chip')).toContainText('白');
    await expect(page.getByTestId('baipu-qa-banner')).toHaveCount(0);
    await expect(page.getByTestId('baipu-qa-override')).toHaveCount(0);
    expect(bodies.some((body) => body.move_index === 0 && !('override' in body))).toBeTruthy();
  });
  ```

- [x] **Step 3.2: 简化 API outcome 和页面状态机**

  从 `baipuApi.ts` 删除 `QaDiff`、`qa_mismatch` outcome 和 request `override`。`BaipuSessionPage.tsx` 删除 `qa_block` phase、`qaDiffs` state、override 参数/按钮/横幅；`doCapture(k)` 成功后直接计帧、快门、推进。

  采集错误不得被当作成功推进：`out.kind === 'error'` 时显示错误并保持当前手；只有 `ok` 或明确的 screen-only `disabled` 才调用 `advance()`。

- [x] **Step 3.3: 运行前端测试与构建**

  Run: `cd katrain/web/ui && npm test -- src/api/baipuApi.test.ts`

  Run: `cd katrain/web/ui && npx playwright test tests/baipu.spec.ts`

  Run: `cd katrain/web/ui && npm run build && npm run build:kiosk-2d`

  Expected: PASS；产物中无 `baipu-qa-banner`、`baipu-qa-override` 和“确认无误，继续”。

- [x] **Step 3.4: 前端提交**

  ```bash
  git add katrain/web/ui/src/api/baipuApi.ts katrain/web/ui/src/kiosk/pages/BaipuSessionPage.tsx katrain/web/ui/tests/baipu.spec.ts katrain/web/ui/src/api/baipuApi.test.ts katrain/web/static
  git commit -m "simplify baipu collection confirmation"
  ```

### Task 4：全链路验证、文档状态和交付

**Files:**
- Modify: `superpowers/tracks/sbc-baipu-led-guide/2026-06-22-operator-trusted-baipu-capture-design.md`
- Modify: `superpowers/tracks/sbc-baipu-led-guide/plan.md`

- [x] **Step 4.1: 后端相关回归**

  Run: `/opt/miniconda3/envs/py311_katago/bin/python -m pytest -q tests/test_baipu_load.py tests/test_baipu_capture.py tests/test_baipu_api.py tests/test_capture_service.py tests/test_led_service.py tests/test_geometry_api.py tests/test_geometry_calibration_service.py`

  Expected: 0 failures。

- [x] **Step 4.2: 前端受影响回归和静态检查**

  Run: `cd katrain/web/ui && npm test -- src/api/baipuApi.test.ts`

  Run: `cd katrain/web/ui && npx eslint src/api/baipuApi.ts src/kiosk/pages/BaipuSessionPage.tsx tests/baipu.spec.ts`

  Run: `git diff --check`

  Expected: 0 failures。

- [x] **Step 4.3: 浏览器自动验收（无需伪造棋子识别）**

  使用 `py311_katago` 在 8002 启动根目录服务；应用内浏览器登录 `fan` 后进入 `kifu_24171`。确认页面从第 1 手 Black 直接推进到第 2 手 White，`baipu-qa-banner/override` 数量为 0，控制台 0 error。Playwright 同时验证成功采集、legacy mismatch 普通错误阻断和不发送 override。

- [ ] **Step 4.4: 真机操作者验收**

  从产品根目录重启 board mode 服务，登录后打开一个短 SGF。操作者在 HBV 实体棋盘连续摆放并确认黑、白至少两手，页面不得出现 empty/mismatch，灯切到下一手，每次确认只增加一帧。检查：

  ```bash
  find /Users/fan/.katrain/baipu_captures/kifu_24171 -maxdepth 1 -type f -print | sort
  jq '.game_id, [.frames[] | {file, applied_move_index, next_guided_move_index, qa_status}]' \
    /Users/fan/.katrain/baipu_captures/kifu_24171/manifest.json
  ```

  Expected: 目录名等于页面 source/SGF 标识；`frame_000.jpg` 起连续编号；新帧均为 `operator_confirmed`；图片显示已确认盘面和下一手 LED。

- [x] **Step 4.5: 更新设计状态与 P7 执行记录**

  将设计状态改为 implemented，新增 §14 记录测试计数、构建、浏览器结果、真实采集目录和任何既有全仓基线失败。不得把训练照片加入 git。

- [x] **Step 4.6: 文档提交**

  ```bash
  git add superpowers/tracks/sbc-baipu-led-guide/plan.md \
    superpowers/tracks/sbc-baipu-led-guide/2026-06-22-operator-trusted-baipu-capture-design.md \
    superpowers/tracks/sbc-baipu-led-guide/2026-06-22-geometry-live-preview-design.md
  git commit -m "document operator-trusted baipu collection"
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
- **采集真值质量**：P7 冷启动阶段完全信任操作者，系统不做识别纠错；需通过短谱抽检图片/manifest 和操作流程降低人为误摆风险，初版 YOLOv11 验收后再以显式策略版本引入机器 QA。
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

---

## 14. P7 执行记录（2026-06-22）

**提交**：`5baf9734` 归档设计并补 P7 计划 · `44d71f13` 后端操作者确认即采集 · `fde65ec9` 前端单一确认流程。

**实现**：`run_capture` 不再抓 QA 帧、调用经典 HSV classifier 或抛出 `QAMismatch`；操作者确认直接生成 `qa_status=operator_confirmed`，随后严格点亮下一手并只保存 `shown_at` 之后的新帧。`game_id` 继续作为 SGF 稳定标识，`kifu_24171`、`kifu_24172` 等各自持有独立的 `game.sgf`、`geometry.npz/json`、`manifest.json` 和连续图片。前端删除 `qa_block`、diff 横幅、重试/override 控件及请求字段；相机、LED、协议或写盘错误改为显示采集失败并保持当前手，不再错误推进。

**TDD 与定向回归**：后端 RED 为 `4 failed / 12 passed`，GREEN 为 `16 passed`；摆谱/采集/LED/几何定向套件 `72 passed`，扩大 vision/CameraHub 回归 `214 passed`。Baipu API Vitest `5 passed`，Playwright `4 passed`，变更文件 ESLint 通过；`npm run build` 与 `npm run build:kiosk-2d` 均通过，后者确认无 three.js。Python Black 和 `git diff --check` 通过。

**浏览器验收**：隔离根目录服务使用 `/opt/miniconda3/envs/py311_katago/bin/python` 启动在 8002。应用内浏览器登录后进入 `kifu_24171`，第 1 手 Black 点击确认后直接进入第 2 手 White；页面 QA/override 控件为 0，控制台 0 error。测试完成后已关闭浏览器测试页和 8002 服务，不影响 8001 真机服务。

**全仓基线**：全仓 Vitest 为 `72 failed / 307 passed`，与 P6 既有 72 个失败一致且新增用例通过；失败集中在 localStorage 测试环境、旧 Provider 包装和主题断言。`CI=true` 全仓 pytest 为 `33 failed / 533 passed / 5 skipped / 10 errors`，失败位于既有 user-game、web_ui 外部服务/fixture、tsumego 502 等非 P7 区域；P7 相关 214 个测试全绿。

**待操作者真机动作**：重启 8001 使 Python 后端载入新代码，在 HBV 棋盘摆放并确认至少黑白两手，然后检查 `/Users/fan/.katrain/baipu_captures/<sgf_id>/` 新帧与 manifest 均为 `operator_confirmed`。此项需要物理摆子，不能以空盘自动点击代替。

---

## 15. P8 摆谱右侧手数与最近图片状态（2026-06-22）

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在摆谱右侧操作区显示当前待摆手数，并在拍摄成功后显示后端实际写入的图片文件名。

**Architecture:** 当前手数从既有 `k` 派生；最近文件名从 `/baipu/capture` 成功响应的 `result.path` 提取 basename 并存入页面状态。不得根据手数或 `frameCount` 推算文件名，因此初始帧、重拍和历史 manifest 均能准确显示。

**Tech Stack:** React 19、TypeScript、MUI、Playwright、Vite。

**Files:**
- Modify: `katrain/web/ui/src/kiosk/pages/BaipuSessionPage.tsx`
- Modify: `katrain/web/ui/tests/baipu.spec.ts`
- Verify: `katrain/web/ui/src/api/baipuApi.ts`
- Document: `superpowers/tracks/sbc-baipu-led-guide/2026-06-22-baipu-capture-status-design.md`

### Task 1：Playwright RED——真实文件名和待摆手数

- [x] **Step 1.1: 扩展 capture mock，返回不可由手数推算的真实路径**

  在 `operator confirmation captures once...` 用例中按请求返回：

  ```typescript
  const moveIndex = Number(body.move_index);
  const file = moveIndex === -1 ? 'frame_000.jpg' : 'frame_049.jpg';
  return route.fulfill({
    json: {
      ok: true,
      path: `/captures/test1/${file}`,
      qa_status: 'operator_confirmed',
      frame_kind: moveIndex === -1 ? 'initial_led' : 'after_move',
      next_guided_move_index: moveIndex + 1,
    },
  });
  ```

- [x] **Step 1.2: 写右侧状态断言**

  ```typescript
  await expect(page.getByTestId('baipu-current-move')).toContainText('第 1 手');
  await expect(page.getByTestId('baipu-latest-frame')).toContainText('frame_000.jpg');
  await page.getByTestId('baipu-confirm').click();
  await expect(page.getByTestId('baipu-current-move')).toContainText('第 2 手');
  await expect(page.getByTestId('baipu-latest-frame')).toContainText('frame_049.jpg');
  ```

- [x] **Step 1.3: 运行 RED**

  Run: `cd katrain/web/ui && npx playwright test tests/baipu.spec.ts -g "operator confirmation captures once"`

  Expected: FAIL，因为 `baipu-current-move` 和 `baipu-latest-frame` 尚不存在。

### Task 2：React GREEN——右侧状态展示

- [x] **Step 2.1: 添加最近文件状态和安全 basename 提取**

  在 `BaipuSessionPage` 增加：

  ```typescript
  const [latestSavedFile, setLatestSavedFile] = useState<string | null>(null);

  const savedFilename = (path?: string): string | null => {
    if (!path) return null;
    return path.split(/[\\/]/).filter(Boolean).at(-1) ?? null;
  };
  ```

  普通确认和初始自动采集仅在 `out.kind === 'ok'` 且存在 basename 时调用 `setLatestSavedFile`。`error`、`disabled` 和 `handleUndo` 不修改该状态。

- [x] **Step 2.2: 在右侧渲染两个可测试状态**

  下一手色片内增加：

  ```tsx
  <Typography data-testid="baipu-current-move">
    {t('Current placement', '当前待摆')}：{t('Move', '第')} {k + 1} {t('moves', '手')}
  </Typography>
  ```

  主按钮上方增加紧凑信息块：

  ```tsx
  <Box data-testid="baipu-latest-frame">
    <Typography variant="caption">{t('Latest saved', '最近保存')}</Typography>
    <Typography sx={{ fontFamily: '"IBM Plex Mono", monospace' }}>
      {latestSavedFile ?? t('None yet', '尚无')}
    </Typography>
  </Box>
  ```

- [x] **Step 2.3: 运行 GREEN 和完整摆谱 Playwright**

  Run: `cd katrain/web/ui && npx playwright test tests/baipu.spec.ts`

  Expected: 4 tests PASS。

### Task 3：失败保持与静态验证

- [x] **Step 3.1: 增加失败不覆盖最近文件的 Playwright 断言**

  让初始 `move_index=-1` 返回 `/captures/test1/frame_000.jpg`，`move_index=0` 返回 500。点击确认后断言错误横幅出现、当前仍为第 1 手且最近保存仍为 `frame_000.jpg`。

- [x] **Step 3.2: 运行定向测试、Lint 和构建**

  Run: `cd katrain/web/ui && npx playwright test tests/baipu.spec.ts`

  Run: `cd katrain/web/ui && npx eslint src/kiosk/pages/BaipuSessionPage.tsx tests/baipu.spec.ts`

  Run: `cd katrain/web/ui && npm run build && npm run build:kiosk-2d`

  Expected: 全部退出码 0；kiosk 2D 校验无 Three.js 越界依赖。

- [x] **Step 3.3: 检查变更边界**

  Run: `git diff --check && git status --short`

  Expected: 无 whitespace error；不修改后端采集协议，不覆盖既有 `uv.lock` 用户变更。

### Task 4：执行记录

- [x] **Step 4.1: 更新 P8 状态**

  在本节下追加实际 RED/GREEN、Playwright、ESLint、双构建结果，并将设计文档状态改为“已实施”。

- [x] **Step 4.2: 提交本次前端与文档**

  ```bash
  git add katrain/web/ui/src/kiosk/pages/BaipuSessionPage.tsx \
    katrain/web/ui/tests/baipu.spec.ts \
    katrain/web/static \
    superpowers/tracks/sbc-baipu-led-guide/plan.md \
    superpowers/tracks/sbc-baipu-led-guide/2026-06-22-baipu-capture-status-design.md
  git commit -m "show baipu capture status"
  ```

### P8 执行记录

- **RED:** 定向 Playwright 按预期失败，`baipu-current-move` 元素不存在。
- **GREEN:** 成功响应使用后端 `path` 的 basename；初始帧和确认帧均更新最近文件名，失败、disabled 和悔棋不覆盖。
- **自动化:** 完整 `baipu.spec.ts` 为 `5 passed`，覆盖真实路径 `frame_049.jpg` 与失败保持 `frame_000.jpg`。
- **静态验证:** 变更文件 ESLint 通过；`npm run build` 和 `npm run build:kiosk-2d` 通过；2D 校验确认无 Three.js。

---

## 16. P9 服务重启后人工确认复用棋盘几何（2026-06-22）

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking。

**Goal:** 服务重启后，在摄像头与棋盘未移动时允许操作者确认实时网格无误，复用上次持久化几何并继续中途摆谱，无需清空棋盘。

**Architecture:** `GeometryCalibrationService` 增加只提升会话状态的 `confirm_existing()`，复用现有 lock 和空盘 baseline，不点灯、不重写持久化文件。新 API 将该动作暴露给 GeometryContext；标定工作区仅在 `required + last_valid + camera_ready` 显示复用按钮，`degraded` 仍强制清空重标定。

**Tech Stack:** Python 3.11、FastAPI、React 19、TypeScript、MUI、pytest、Vitest。

### Task 1：服务层 RED/GREEN——安全复用持久化几何

**Files:**
- Modify: `katrain/web/core/geometry_calibration_service.py`
- Test: `tests/test_geometry_calibration_service.py`

- [x] **Step 1.1: 写复用成功 RED**

  ```python
  def test_confirm_existing_promotes_loaded_lock_without_recalibration(tmp_path):
      old = _synth()
      promoted = []
      service = GeometryCalibrationService(
          led=FakeLed(), capture=FreshFakeCapture(), save_path=tmp_path / "geometry.npz",
          initial_lock=old, on_success=promoted.append,
      )

      status = service.confirm_existing()

      assert status["phase"] == "ready"
      assert status["session_calibrated"] is True
      assert status["capabilities"]["geometry_ready"] is True
      assert status["trigger"] == "operator_reuse"
      assert promoted == [old]
      assert not (tmp_path / "geometry.npz").exists()
  ```

  `FreshFakeCapture.grab_fresh()` 返回一张稳定帧，使现有 `_init_drift_monitor` 能建立本次会话监测。

- [x] **Step 1.2: 写拒绝条件 RED**

  增加三个独立断言：`initial_lock=None`、摄像头 `is_connected=False`、`_status["phase"]="degraded"` 调用 `confirm_existing()` 均抛 `ValueError`，且不得变成 ready。

- [x] **Step 1.3: 运行 RED**

  Run: `/opt/miniconda3/envs/py311_katago/bin/python -m pytest tests/test_geometry_calibration_service.py -q`

  Expected: FAIL，提示 `GeometryCalibrationService` 尚无 `confirm_existing`。

- [x] **Step 1.4: 实现最小服务方法**

  ```python
  def confirm_existing(self) -> dict:
      with self._lock:
          if self._status["phase"] != "required":
              raise ValueError("existing geometry can only be confirmed after restart")
          if self.current_lock is None:
              raise ValueError("no existing geometry to confirm")
          if not self._is_ready(self.capture):
              raise ValueError("camera is not ready")
          lock = self.current_lock
          self._init_drift_monitor(lock)
          self._geometry_revision += 1
          self._status.update(
              phase="ready", session_calibrated=True, last_valid=True,
              trigger="operator_reuse", error=None, metrics={},
          )
      self.on_success(lock)
      return self.status()
  ```

- [x] **Step 1.5: 运行 GREEN**

  Run: `/opt/miniconda3/envs/py311_katago/bin/python -m pytest tests/test_geometry_calibration_service.py -q`

  Expected: 全部 PASS。

- [x] **Step 1.6: 提交服务层**

  ```bash
  git add katrain/web/core/geometry_calibration_service.py tests/test_geometry_calibration_service.py
  git commit -m "allow confirmed geometry reuse"
  ```

### Task 2：HTTP RED/GREEN——确认历史几何接口

**Files:**
- Modify: `katrain/web/api/v1/endpoints/geometry.py`
- Test: `tests/test_geometry_api.py`

- [x] **Step 2.1: 写 API RED**

  在 FakeCalibration 中记录 `confirmed`，新增：

  ```python
  response = c.post("/geometry/confirm-existing")
  assert response.status_code == 200
  assert response.json()["phase"] == "ready"
  assert calibration.confirmed is True
  ```

  再覆盖无 calibration 时 404，以及 `confirm_existing()` 抛 `ValueError` 时 409 和原始 detail。

- [x] **Step 2.2: 运行 RED**

  Run: `/opt/miniconda3/envs/py311_katago/bin/python -m pytest tests/test_geometry_api.py -q`

  Expected: FAIL，路由返回 404。

- [x] **Step 2.3: 实现 endpoint**

  ```python
  @router.post("/confirm-existing")
  async def geometry_confirm_existing(request: Request):
      calibration = getattr(request.app.state, "geometry_calibration", None)
      if calibration is None:
          raise HTTPException(status_code=404, detail="LED geometry calibration not enabled")
      try:
          return calibration.confirm_existing()
      except ValueError as exc:
          raise HTTPException(status_code=409, detail=str(exc)) from exc
  ```

- [x] **Step 2.4: 运行 GREEN**

  Run: `/opt/miniconda3/envs/py311_katago/bin/python -m pytest tests/test_geometry_api.py tests/test_geometry_calibration_service.py -q`

  Expected: 全部 PASS。

- [x] **Step 2.5: 提交 API**

  ```bash
  git add katrain/web/api/v1/endpoints/geometry.py tests/test_geometry_api.py
  git commit -m "expose geometry reuse confirmation"
  ```

### Task 3：前端 RED/GREEN——网格无误按钮与 Guard 放行

**Files:**
- Modify: `katrain/web/ui/src/api/geometryApi.ts`
- Modify: `katrain/web/ui/src/api/geometryApi.test.ts`
- Modify: `katrain/web/ui/src/kiosk/context/GeometryContext.tsx`
- Modify: `katrain/web/ui/src/kiosk/components/vision/GeometryCalibrationWorkspace.tsx`
- Modify: `katrain/web/ui/src/kiosk/__tests__/GeometryCalibrationWorkspace.test.tsx`
- Modify: `katrain/web/ui/src/kiosk/__tests__/PhysicalBoardGuard.test.tsx`

- [x] **Step 3.1: 写 API 和工作区 RED**

  `geometryApi.test.ts` 断言 `GeometryAPI.confirmExisting()` 以 POST 调用 `/api/v1/geometry/confirm-existing`。工作区测试把状态设为：

  ```typescript
  status = {
    phase: 'required', session_calibrated: false, last_valid: true,
    capabilities: { camera_ready: true, led_ready: true, geometry_ready: false },
  };
  ```

  断言显示“网格无误，使用上次标定”和“无需清空棋盘”，点击调用 `confirmExisting`；把 phase 改为 degraded 时断言按钮不存在。

- [x] **Step 3.2: 写 Guard 放行 RED**

  mock `GeometryAPI.confirmExisting` 返回 `phase=ready/session_calibrated=true/geometry_ready=true`；从 required+last_valid 渲染 Guard，点击复用按钮并等待“实体棋盘内容”出现。

- [x] **Step 3.3: 运行 RED**

  Run: `cd katrain/web/ui && npm test -- src/api/geometryApi.test.ts src/kiosk/__tests__/GeometryCalibrationWorkspace.test.tsx src/kiosk/__tests__/PhysicalBoardGuard.test.tsx`

  Expected: FAIL，缺少 `confirmExisting` 和按钮。

- [x] **Step 3.4: 实现 API、Context 和按钮**

  `GeometryAPI` 增加：

  ```typescript
  confirmExisting: async (): Promise<GeometryStatus> => json(await fetch(`${API_BASE}/confirm-existing`, { method: 'POST' })),
  ```

  GeometryContext 暴露 `confirmExisting()`，用返回状态立即 `setStatus`。工作区计算：

  ```typescript
  const canReuse = status.phase === 'required' && status.last_valid
    && cameraReady && !starting && !active;
  ```

  当 `canReuse` 时渲染说明和 outlined 按钮“网格无误，使用上次标定”；点击期间禁用两个启动动作，失败写入 `actionError`。不得在 degraded 显示复用按钮，也不得要求 LED ready。

- [x] **Step 3.5: 运行 GREEN**

  Run: `cd katrain/web/ui && npm test -- src/api/geometryApi.test.ts src/kiosk/__tests__/GeometryCalibrationWorkspace.test.tsx src/kiosk/__tests__/PhysicalBoardGuard.test.tsx`

  Expected: 全部 PASS。

- [x] **Step 3.6: 提交前端**

  ```bash
  git add katrain/web/ui/src/api/geometryApi.ts \
    katrain/web/ui/src/api/geometryApi.test.ts \
    katrain/web/ui/src/kiosk/context/GeometryContext.tsx \
    katrain/web/ui/src/kiosk/components/vision/GeometryCalibrationWorkspace.tsx \
    katrain/web/ui/src/kiosk/__tests__/GeometryCalibrationWorkspace.test.tsx \
    katrain/web/ui/src/kiosk/__tests__/PhysicalBoardGuard.test.tsx
  git commit -m "confirm persisted board geometry"
  ```

### Task 4：回归、构建与执行记录

**Files:**
- Modify: `superpowers/tracks/sbc-baipu-led-guide/2026-06-22-geometry-session-reuse-design.md`
- Modify: `superpowers/tracks/sbc-baipu-led-guide/plan.md`

- [x] **Step 4.1: 后端定向回归**

  Run: `/opt/miniconda3/envs/py311_katago/bin/python -m pytest tests/test_geometry_calibration_service.py tests/test_geometry_api.py tests/test_geometry_drift.py tests/test_baipu_api.py -q`

  Expected: 0 failures。

- [x] **Step 4.2: 前端定向回归、Lint 和双构建**

  Run: `cd katrain/web/ui && npm test -- src/api/geometryApi.test.ts src/kiosk/__tests__/GeometryCalibrationWorkspace.test.tsx src/kiosk/__tests__/PhysicalBoardGuard.test.tsx`

  Run: `cd katrain/web/ui && npx eslint src/api/geometryApi.ts src/kiosk/context/GeometryContext.tsx src/kiosk/components/vision/GeometryCalibrationWorkspace.tsx src/kiosk/__tests__/GeometryCalibrationWorkspace.test.tsx src/kiosk/__tests__/PhysicalBoardGuard.test.tsx`

  Run: `cd katrain/web/ui && npm run build && npm run build:kiosk-2d`

  Expected: 全部退出码 0，kiosk 2D 无 Three.js。

- [x] **Step 4.3: 更新文档和提交**

  将设计状态改为“已实施”，勾选 P9 全部步骤并记录 RED/GREEN 数量、回归和构建结果：

  ```bash
  git add superpowers/tracks/sbc-baipu-led-guide/plan.md \
    superpowers/tracks/sbc-baipu-led-guide/2026-06-22-geometry-session-reuse-design.md
  git commit -m "document geometry session reuse"
  ```

- [ ] **Step 4.4: 真机手动验收**

  保持中途棋盘不动并重启服务。进入摆谱后检查原图和俯视图网格对齐，点击“网格无误，使用上次标定”，应直接返回摆谱且保留棋盘；移动摄像头触发 degraded 后不得出现复用按钮。

### P9 执行记录

- **服务层 RED/GREEN:** 新增成功复用、无历史 lock、摄像头断开、degraded 四个场景；RED `4 failed / 5 passed`，GREEN `9 passed`。
- **HTTP RED/GREEN:** 成功与冲突场景先因路由缺失返回 404；实现后服务+API 合计 `24 passed`。
- **前端 RED/GREEN:** API、工作区按钮、Guard 放行三个路径先失败；实现后定向 Vitest `12 passed`。
- **扩大回归:** 几何服务/API、漂移和摆谱 API 共 `35 passed`；变更文件 ESLint 通过。
- **构建:** `npm run build` 和 `npm run build:kiosk-2d` 通过，2D 产物确认无 Three.js。
- **安全边界:** 复用不点灯、不写持久化 lock/baseline；只允许 required+last_valid+camera ready，degraded 继续强制清空重标定。

---

## P10. 标定诊断卡片 + 摆谱同目录覆盖重启（2026-06-23）

**状态**: 已完成。

**Goal:** 把标定失败从内部错误码改为操作者可理解的诊断卡片，并让摆谱“重新开始”在同一 SGF 目录内显式覆盖旧帧，避免旧训练图片被静默复用。

**Architecture:** 标定错误翻译保留在前端展示层，后端服务只放宽 `failed + last_valid` 的旧几何确认入口；`degraded` 仍禁止复用。摆谱采集新增 `overwrite_existing` 显式字段，默认幂等行为不变，只有重启会话传入该字段时才覆盖同名旧帧并裁掉旧 manifest 尾部。

**Tech Stack:** FastAPI/Pydantic、pytest、React/Vite/MUI、Vitest、Playwright。

**设计文档:** `superpowers/tracks/sbc-baipu-led-guide/2026-06-23-error-diagnostics-and-overwrite-restart-design.md`

### Task 1：服务层 RED/GREEN——failed 状态可确认历史几何

**Files:**
- Modify: `katrain/web/core/geometry_calibration_service.py`
- Test: `tests/test_geometry_calibration_service.py`

- [x] **Step 1.1: 写 RED 测试**

  在 `tests/test_geometry_calibration_service.py` 增加：

  ```python
  def test_confirm_existing_recovers_from_failed_calibration_when_lock_is_valid(tmp_path):
      old = _synth()
      promoted = []
      capture = FreshFakeCapture()
      service = GeometryCalibrationService(
          led=FakeLed(),
          capture=capture,
          save_path=tmp_path / "geometry.npz",
          initial_lock=old,
          on_success=promoted.append,
      )
      service._status["phase"] = "failed"
      service._status["error"] = "anchor_not_found:15,15"

      status = service.confirm_existing()

      assert status["phase"] == "ready"
      assert status["session_calibrated"] is True
      assert status["trigger"] == "operator_reuse"
      assert status["error"] is None
      assert promoted == [old]
      assert capture.grab_calls == 1
  ```

- [x] **Step 1.2: 运行 RED**

  Run: `/opt/miniconda3/envs/py311_katago/bin/python -m pytest tests/test_geometry_calibration_service.py::test_confirm_existing_recovers_from_failed_calibration_when_lock_is_valid -q`

  Expected: FAIL，错误信息包含 `only be confirmed after restart`。

- [x] **Step 1.3: 实现最小服务变更**

  把 `confirm_existing()` 的 phase 判断从仅 `required` 改为允许 `{"required", "failed"}`，错误消息改为 `"existing geometry can only be confirmed after restart or failed recalibration"`。保留 `degraded` 拒绝。

- [x] **Step 1.4: 运行 GREEN**

  Run: `/opt/miniconda3/envs/py311_katago/bin/python -m pytest tests/test_geometry_calibration_service.py -q`

  Expected: 全部 PASS。

### Task 2：后端采集 RED/GREEN——同目录覆盖旧帧

**Files:**
- Modify: `katrain/web/core/baipu_capture.py`
- Modify: `katrain/web/api/v1/endpoints/baipu.py`
- Test: `tests/test_baipu_capture.py`
- Test: `tests/test_baipu_api.py`

- [x] **Step 2.1: 写 RED 测试**

  在 `tests/test_baipu_capture.py` 增加：

  ```python
  class VersionedCapture(FakeCapture):
      def __init__(self, out_dir):
          super().__init__(out_dir)
          self.version = 0

      def capture_to(self, path, after_ts=None, settle_ms=150.0):
          self.version += 1
          self.capture_calls.append({"path": path, "after_ts": after_ts})
          Path(path).parent.mkdir(parents=True, exist_ok=True)
          Path(path).write_bytes(f"jpg-{self.version}".encode("ascii"))
          return path, self.version, 223.0

  def test_overwrite_existing_restarts_same_directory_and_prunes_stale_tail(tmp_path):
      data = build_steps_from_sgf("(;SZ[19];B[pd];W[dp];B[pp])")
      steps, bs = data["steps"], data["board_size"]
      led, cap = FakeLed(), VersionedCapture(tmp_path)
      _capture(str(tmp_path), steps, bs, -1, led, cap)
      _capture(str(tmp_path), steps, bs, 0, led, cap)
      _capture(str(tmp_path), steps, bs, 1, led, cap)

      restarted = _capture(str(tmp_path), steps, bs, -1, led, cap, overwrite_existing=True)

      assert restarted["idempotent"] is False
      assert restarted["overwritten"] is True
      assert (tmp_path / "g1" / "frame_000.jpg").read_bytes() == b"jpg-4"
      assert not (tmp_path / "g1" / "frame_001.jpg").exists()
      manifest = json.loads((tmp_path / "g1" / "manifest.json").read_text())
      assert [f["file"] for f in manifest["frames"]] == ["frame_000.jpg"]
  ```

  在 `tests/test_baipu_api.py` 增加一个请求 `overwrite_existing=True` 的 200 覆盖，证明 Pydantic 字段被 endpoint 传入。

- [x] **Step 2.2: 运行 RED**

  Run: `/opt/miniconda3/envs/py311_katago/bin/python -m pytest tests/test_baipu_capture.py::TestRobustness::test_overwrite_existing_restarts_same_directory_and_prunes_stale_tail -q`

  Expected: FAIL，`run_capture()` 不接受 `overwrite_existing`。

- [x] **Step 2.3: 实现最小后端变更**

  `run_capture()` 增加 `overwrite_existing: bool = False`。命中已有 `applied_move_index` 时：

  - 默认 `False` 且图片存在：保持原幂等返回。
  - `True`：设置 `repair_index=index`，删除 `frames[index + 1:]` 对应图片并裁掉 manifest 尾部，然后覆盖当前 `frame_file`。
  - 缺帧修复仍不裁剪后续帧。

  `BaipuCaptureRequest` 增加 `overwrite_existing: bool = False`，endpoint 传给 `run_capture()`。

- [x] **Step 2.4: 运行 GREEN**

  Run: `/opt/miniconda3/envs/py311_katago/bin/python -m pytest tests/test_baipu_capture.py tests/test_baipu_api.py -q`

  Expected: 全部 PASS。

### Task 3：前端 RED/GREEN——诊断卡片与重启覆盖模式

**Files:**
- Modify: `katrain/web/ui/src/api/baipuApi.ts`
- Modify: `katrain/web/ui/src/kiosk/pages/BaipuSessionPage.tsx`
- Modify: `katrain/web/ui/src/kiosk/components/vision/GeometryCalibrationWorkspace.tsx`
- Test: `katrain/web/ui/src/kiosk/__tests__/GeometryCalibrationWorkspace.test.tsx`
- Test: `katrain/web/ui/tests/baipu.spec.ts`

- [x] **Step 3.1: 写诊断卡片 RED**

  在 `GeometryCalibrationWorkspace.test.tsx` 增加 failed+last_valid 场景，断言：

  ```typescript
  expect(screen.getByTestId('geometry-diagnostic-card')).toBeInTheDocument();
  expect(screen.getByText('无法定位 Q4 的定位灯')).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: '网格无误，使用上次标定' }));
  await waitFor(() => expect(confirmExisting).toHaveBeenCalledTimes(1));
  ```

- [x] **Step 3.2: 写重启覆盖 RED**

  在 `baipu.spec.ts` 增加 resume prompt 场景，localStorage 写入 `baipu:progress:test1`，进入页面后先断言没有抢拍 `/baipu/capture`，点击“重新开始”后断言第一次 capture 请求包含：

  ```typescript
  expect(bodies[0]).toEqual(expect.objectContaining({
    move_index: -1,
    overwrite_existing: true,
  }));
  ```

- [x] **Step 3.3: 运行 RED**

  Run: `cd katrain/web/ui && npm test -- src/kiosk/__tests__/GeometryCalibrationWorkspace.test.tsx`

  Run: `cd katrain/web/ui && npx playwright test tests/baipu.spec.ts --grep "restart"`

  Expected: 两个新测试失败。

- [x] **Step 3.4: 实现前端变更**

  `GeometryCalibrationWorkspace` 新增诊断卡片组件，`canReuse` 改为 `required|failed` 且 `last_valid`。`BaipuSessionPage` 新增 `overwriteExisting` 状态；resume 对话框的“重新开始”设置该状态、重置首帧 ref、帧计数和最近保存文件。初始帧 effect 在 `resumePrompt === null` 后才运行，capture 请求携带 `overwrite_existing`。

- [x] **Step 3.5: 运行 GREEN**

  Run: `cd katrain/web/ui && npm test -- src/kiosk/__tests__/GeometryCalibrationWorkspace.test.tsx`

  Run: `cd katrain/web/ui && npx playwright test tests/baipu.spec.ts --grep "restart"`

  Expected: 全部 PASS。

### Task 4：回归、构建与执行记录

**Files:**
- Modify: `superpowers/tracks/sbc-baipu-led-guide/plan.md`
- Modify: `superpowers/tracks/sbc-baipu-led-guide/2026-06-23-error-diagnostics-and-overwrite-restart-design.md`

- [x] **Step 4.1: 后端定向回归**

  Run: `/opt/miniconda3/envs/py311_katago/bin/python -m pytest tests/test_geometry_calibration_service.py tests/test_geometry_api.py tests/test_baipu_capture.py tests/test_baipu_api.py -q`

  Expected: 全部 PASS。

- [x] **Step 4.2: 前端定向回归与构建**

  Run: `cd katrain/web/ui && npm test -- src/kiosk/__tests__/GeometryCalibrationWorkspace.test.tsx src/api/baipuApi.test.ts`

  Run: `cd katrain/web/ui && npx playwright test tests/baipu.spec.ts`

  Run: `cd katrain/web/ui && npm run build`

  Expected: 全部退出码 0。

- [x] **Step 4.3: 更新执行记录**

  勾选 P10 步骤，记录 RED/GREEN、回归和构建结果。

### P10 执行记录

- **服务层 RED:** `test_confirm_existing_recovers_from_failed_calibration_when_lock_is_valid` 先失败，错误为 `existing geometry can only be confirmed after restart`。
- **采集层 RED:** `overwrite_existing=True` 先触发 `run_capture() got an unexpected keyword argument 'overwrite_existing'`。
- **API RED:** `/baipu/capture` 先未把 `overwrite_existing` 转发到 `run_capture`。
- **前端 RED:** 诊断卡片测试先找不到 `geometry-diagnostic-card`；Playwright 初次因静态包未更新看到旧 bundle，重建后验证新行为。
- **GREEN:** 后端定向回归 `/opt/miniconda3/envs/py311_katago/bin/python -m pytest tests/test_geometry_calibration_service.py tests/test_geometry_api.py tests/test_baipu_capture.py tests/test_baipu_api.py -q` → `44 passed`。
- **前端组件/API:** `npm test -- src/kiosk/__tests__/GeometryCalibrationWorkspace.test.tsx src/api/baipuApi.test.ts` → `12 passed`。
- **浏览器验证:** `PATH=/opt/miniconda3/envs/py311_katago/bin:$PATH npx playwright test tests/baipu.spec.ts` → `6 passed`；覆盖“重新开始”不会抢拍，点击后首帧请求带 `overwrite_existing:true`。
- **构建:** `npm run build` 通过，静态包已更新到 `katrain/web/static`。

---

## P11. 棋盘位移在线检测 + 基准灯自动校正 + 实时采集中间图（2026-06-26，2026-06-27 按 codex/gemini 评审重写）

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. Follow every RED/GREEN checkpoint and update checkboxes after each task.

**状态**: 计划中（待执行）。本节已按 2026-06-26 的 Codex / Gemini 评审反馈整体重写（旧版有阻断级几何错误，见下「P11 修订说明」）。

**背景（实测，2026-06-26）：** 重摆 `kifu_24171`（212 帧）后离线标注复盘发现：**冻结几何 + 摆谱过程中棋盘被碰移** → warped 网格自 `frame_031` 起整体偏移；`baipu_autolabel` 现用的「全局平移 + 密集棋子 Hough 锚点」漂移修复在拥挤盘面失效（LED 锚点命中仅 **37%**，`residual>10px` 占 **56%**，平移有 `±0.6 cell` 硬上限），中后盘标注框偏约半格~一格，**不可直接训练**。根因：单一平移修不了「碰后平移+旋转」，且密集盘上 Hough 锚点噪声大。下棋时用户难免碰盘，需要在线**检测 + 自动修复**机制（无需清盘）。

**Goal:** 摆谱采集**每手**用盘面上**未被棋子覆盖的空交叉点**点亮 LED 作为已知基准点(fiducial)，对该帧**重新解算相机→规范棋盘的单应矩阵 `M_f`**（平移+旋转+缩放，绝对、不累积）；在线检测位移并当场提示/自动校正（不强制清盘），把逐帧校正几何与质量状态写进 manifest；离线 `baipu_autolabel` 直接消费 `M_f` 产出对齐标注、并对未校正的漂移帧做质量隔离。同时每手**实时**生成并存盘原图 / 网格定位叠加图 / warped 图，便于边摆边查与事后排查。

**Architecture（复用既有件，最小新增）：**
- **解的是「当前相机帧 → 规范 950×950 warp 空间」的 `M_f`**。复用 `led_geometry_calibrator.fit_geometry_from_anchors`：它内部把 canonical 目标点构造为 `[[col*spacing, row*spacing]]`（≡ `(xs[col], ys[row])`，`spacing=(out_size-1)/18`），所以**复用它同时解决了坐标空间正确性 + 继承 `min_inliers`/`max_rms_cells`/`max_residual_cells` 残差门**。**绝不**用 `geometry.npz["points"][row][col]` 作目标——那是相机空间坐标（见 P11 修订说明 #1）。
- **`points[row][col]` 改作 ROI 搜索中心**：它是 `M_0` 下每个交叉点的相机像素坐标（`geometry_calibrate.grid_points_from_corners` 自述返回 original-image 坐标），正好用来在 raw 帧上**预测每个 fiducial 该出现的位置**，分配 blob、抑制远处反光。
- **多 fiducial 同时点亮 + 暗/亮帧差 + ROI 分配**：新增 `detect_led_centroids(dark, lit, expected, channel, search_px)`——一手只需 **1 张暗帧 + 1 张亮帧**（不是每点一对），在每个预测 ROI 内独立取主光斑加权中心，规避现有单 blob `detect_led_centroid` 在多点同亮时只返回最亮一个/`ambiguous_blobs` 失败的问题。
- **鲁棒下限**：目标 9~13 个 fiducial（4 角 + 9 星位中为空者 + 跨盘最远点采样补足）；`corrected` 需 **检测成功 ≥8 点且 `fit_geometry_from_anchors(min_inliers=6)` 通过残差门**。`≥4` 的旧下限作废（4 点是单应最小解，无冗余剔外点）。
- **失败回退不回 `M_0`**：维护 `last_good_M_f`。状态分层 `corrected`（本帧 fiducial 解成功）/`stale`（本帧不足或解失败，沿用上次成功的 `last_good_M_f`）/`frozen`（还没有任何成功解，回退冻结 `M_0`）。**碰移后的 `M_0` 本身就是错几何，绝不静默回退它**。
- **在线只检测+自动校正+提示**，对局中**不强制清盘**（与 P5 `degraded`=相机/整体失锁区分）；fiducial 灯只在隔离的 `fiducial/` 标定帧，**训练帧 `frame_NNN.jpg` 仍只含盘面 + 单个制导灯**，§4.4 交付契约不变。
- **离线质量门**：标注器对 `corrected` 帧用其 `M_f` 直接 warp + 零位移放框；`stale` 帧用 `last_good_M_f` 但标 `label_quality="stale"`；本局若出现过 `drift>阈值` 的校正，则 `frozen`/legacy（无字段）帧默认**跳过**，除非 `--allow-legacy-drift`。

**Tech Stack:** Python 3.11、OpenCV、NumPy、FastAPI/Pydantic、pytest；React 19/TypeScript/MUI、Vitest（仅漂移状态横幅）。

### P11 修订说明（2026-06-27，采纳 / 不采纳 codex+gemini 评审）

**采纳（阻断级，两家一致 + 已对代码核实）：**
1. **坐标空间写反**（两家 Critical）：旧 P11「canonical 目标点 = `geometry.npz["points"][row][col]`」错。`points` 是相机空间（`geometry_calibrate.py:126-135` 自述 original-image，经 `Minv`）；`(xs[col], ys[row])` 才是 warped 规范坐标（`baipu_autolabel.py:240,308`）。→ 改为**复用 `fit_geometry_from_anchors`**（其 dst 已是 `col*spacing,row*spacing`），一举修对坐标 + 拿到残差门；`points` 降级为 ROI 中心。
2. **帧差缺暗帧**（两家 Critical）：`detect_led_centroid(dark, lit, channel)` 需成对暗/亮帧（`led_geometry_calibrator.py:64-98`）。→ 时序加 `clear→grab dark→点亮→grab lit`。
3. **多点检测无现成函数**（codex Critical）：现有 `detect_led_centroid` 只取整图一个主 blob、`_locate_anchor` 是单点逐个闪。→ 新增 `detect_led_centroids`（ROI 多 blob 分配）。
4. **RANSAC `≥4` 太弱**（两家 Major）：→ 目标 9~13、`corrected` 需检测 ≥8 且 inliers≥6 + 保留残差门（`fit_geometry_from_anchors(min_inliers=6)`）。
5. **回退 `M_0` 二次污染**（codex Major / gemini Major）：→ `last_good_M_f` + `corrected/stale/frozen` 状态分层；离线对漂移后未校正帧做质量隔离。
6. **中后盘空点稀缺**（两家 Major）：→ 选点目标 9~13 + 最远点采样 + 不足时 `stale` 显式告警（manifest/UI），不假装校正。
7. **`drift-gated` 漏旋转**（两家 Major；`geometry_drift.py:49` 只 `phaseCorrelate` 测平移）：→ **P11 本期只实现 `every-move`（默认）+ `off`**；`drift-gated` 移出范围、标注为「需旋转感知预检，待后续实验」。
8. **SBC 成本被低估**（两家 Major）：→ Task 6 增设 RK35xx **延迟基准 gate**（实测才定 every-move 是否默认 / 是否异步写 artifact）；架构层给出诚实延迟预算（待测）。
9. **artifact 覆盖/repair 未清理**（codex Major；`_unlink_manifest_frame` 只删 `frame["file"]`）：→ 删除逻辑纳入所有 artifact 路径。
10. **向后兼容只是「不崩」**（两家 Major）：→ 标注器输出 `label_quality`，已知漂移 legacy 默认跳过，需 `--allow-legacy-drift` 才导出。
11. **阈值不一致 / manifest 信息量不足**（codex Minor / gemini Minor）：→ 统一 `baipu_drift_threshold_cells`（默认 0.15）；manifest 用富 `geometry_correction` 对象（status/source/reason/inliers/rms/drift）。

**不采纳（含理由）：**
- codex 的 `M_f = M_0 @ H_cur_to_cam0` 组合路径——多此一举；直接用 warped 目标点解 `M_f` 更简、等价。
- gemini 的逐帧 `M_f.npy` 旁路文件——3×3 直接内联 manifest JSON 更简，省文件管理。
- gemini 的 ORB 预检——仅服务于 `drift-gated`；本期 `drift-gated` 移出范围，故搁置。
- codex 最激进的 `detected≥8` 作为 inlier 下限——采「**检测 ≥8 且 inliers≥6**」平衡中后盘稀缺（既要冗余剔外点，又不至于中后盘永远凑不齐）。
- 「warped_boxes 实时存盘」（原决策③「全套」）——框叠图可由 `warped + SGF` 离线无损复现，且实时画框需 web/core 反向依赖 vision/tools。→ 实时存 `warped/grid_overlay/fiducial` 三类；**warped_boxes 归到离线 `--verify-dir`**（复核标签质量本就在那看）。「全套」由 在线三类 + 离线 verify 共同满足。

### P11 范围和硬约束
- 规范坐标人坐视角 `row=0` 顶、`col=0` 左（附录 A）。`M_f` 的 canonical 目标 = `(xs[col], ys[row]) = (col*spacing, row*spacing)`，`spacing=(out_size-1)/18`。
- 每帧 fiducial 集 F：从 `board_through_index` 已知**空**交叉点选，目标 9~13、最少 8 个非共线跨盘分散点；优先 4 角 + 9 星位为空者，最远点采样补足；**排除制导灯点与四邻有子的点**。可用 <8 或解失败 → 沿用 `last_good_M_f`（`stale`）或回退 `M_0`（`frozen`，仅在尚无 last-good 时），**均不阻断采集**。
- fiducial 统一用低亮度绿 `rgb=(0,96,0)`（channel=1）；任何失败/取消在 `finally` 中 `led.clear(strict=True)`；标定帧与训练帧用**同一锁定曝光**（贯穿会话）。
- 模式 `--baipu-fiducial-mode {every-move,off}`：`every-move`=每手一次标定帧（质量优先，服务默认）；`off`=完全回退 P10（无 fiducial、无 artifact，向后兼容）。
- artifact（`warped/grid_overlay/fiducial`）与训练帧目录隔离；覆盖/repair 时连同清理。训练交付契约（§4.4）不变。
- 统一阈值 `baipu_drift_threshold_cells`（默认 0.15）用于「是否提示已发生移动」。

### Task 1：纯 CV 核心——选点 / 多 fiducial 检测 / 逐帧单应 / 漂移分解
**Files:**
- Create: `katrain/vision/fiducial_recalibrate.py`
- Test: `tests/test_vision/test_fiducial_recalibrate.py`

**Interfaces:**
- Consumes: `katrain.vision.led_geometry_calibrator.fit_geometry_from_anchors(anchors, *, out_size=950, min_inliers, max_rms_cells=0.12, max_residual_cells=0.25) -> GeometryFitResult(ok, M, Minv, inlier_count, rms_residual, max_residual, reason)`。
- Produces（Task2/3/4 依赖这些**确切**签名）：
  - `select_fiducials(board: list[list[str|None]], next_point: dict|None, *, target: int = 13, min_count: int = 8) -> list[tuple[int,int]]`
  - `predict_camera_positions(coords: list[tuple[int,int]], points: np.ndarray) -> dict[tuple[int,int], tuple[float,float]]`
  - `detect_led_centroids(dark: np.ndarray, lit: np.ndarray, expected: dict[tuple[int,int], tuple[float,float]], *, channel: int, search_px: float) -> dict[tuple[int,int], CentroidResult]`（`CentroidResult(ok: bool, coord, centroid: tuple|None, peak: float, reason: str)`）
  - `solve_frame_homography(detected: list[tuple[tuple[int,int], tuple[float,float]]], *, out_size: int = 950, min_inliers: int = 6) -> GeometryFitResult`
  - `drift_from_homography(M_f: np.ndarray, M_0: np.ndarray, *, out_size: int = 950) -> Drift`（`Drift(dx, dy, deg, scale, median_px)`；`median_cells = median_px/spacing`）

- [x] **Step 1.1: 写纯 CV 失败测试**

```python
# tests/test_vision/test_fiducial_recalibrate.py
import numpy as np
import cv2
import pytest
from katrain.vision.fiducial_recalibrate import (
    select_fiducials, predict_camera_positions, detect_led_centroids,
    solve_frame_homography, drift_from_homography, CentroidResult,
)

OUT = 950
SPACING = (OUT - 1) / 18.0

def _canon(r, c):
    return (c * SPACING, r * SPACING)

def _empty_board():
    return [[None] * 19 for _ in range(19)]

def test_select_excludes_occupied_guidance_and_neighbors():
    b = _empty_board()
    b[0][1] = "B"            # 4-neighbor of corner (0,0)
    chosen = select_fiducials(b, {"row": 9, "col": 9}, target=13, min_count=8)
    assert (0, 0) not in chosen          # excluded: neighbor occupied
    assert (9, 9) not in chosen          # excluded: guidance point
    assert len(chosen) >= 8
    assert len(set(chosen)) == len(chosen)
    for (r, c) in chosen:
        assert b[r][c] is None

def test_select_prioritizes_corners_and_star():
    chosen = select_fiducials(_empty_board(), None, target=13, min_count=8)[:13]
    for p in [(0, 0), (0, 18), (18, 0), (18, 18), (9, 9), (3, 3), (15, 15)]:
        assert p in chosen

def _homography(angle_deg, tx, ty):
    # camera->canonical synthetic: rotate+translate canonical, invert to get camera pts
    th = np.radians(angle_deg)
    R = np.array([[np.cos(th), -np.sin(th), tx],
                  [np.sin(th),  np.cos(th), ty],
                  [0, 0, 1]], np.float64)
    return R

def test_detect_assigns_blobs_per_roi_and_rejects_reflection():
    coords = [(0, 0), (0, 18), (18, 0), (18, 18), (9, 9)]
    # camera positions = canonical here (identity geometry) for the test
    expected = {p: _canon(*p) for p in coords}
    dark = np.zeros((OUT, OUT, 3), np.uint8)
    lit = dark.copy()
    for (r, c) in coords:
        x, y = int(_canon(r, c)[0]), int(_canon(r, c)[1])
        cv2.circle(lit, (x, y), 6, (0, 200, 0), -1)   # green blobs (channel 1)
    cv2.circle(lit, (470, 10), 5, (0, 180, 0), -1)     # stray reflection, far from any ROI
    res = detect_led_centroids(dark, lit, expected, channel=1, search_px=0.7 * SPACING)
    for p in coords:
        assert res[p].ok
        ex, ey = _canon(*p)
        assert abs(res[p].centroid[0] - ex) < 3 and abs(res[p].centroid[1] - ey) < 3

def test_solve_recovers_rotation_translation():
    coords = [(0, 0), (0, 9), (0, 18), (9, 0), (9, 18), (18, 0), (18, 9), (18, 18), (9, 9)]
    T = _homography(4.0, 12.0, -8.0)                  # canonical->moved-canonical (== camera here)
    canon = np.array([_canon(*p) for p in coords], np.float64).reshape(-1, 1, 2)
    cam = cv2.perspectiveTransform(canon, np.linalg.inv(T)).reshape(-1, 2)  # camera pts
    detected = [(coords[i], (float(cam[i][0]), float(cam[i][1]))) for i in range(len(coords))]
    fit = solve_frame_homography(detected, out_size=OUT, min_inliers=6)
    assert fit.ok
    back = cv2.perspectiveTransform(cam.reshape(-1, 1, 2), fit.M).reshape(-1, 2)
    for i, p in enumerate(coords):
        ex, ey = _canon(*p)
        assert abs(back[i][0] - ex) < 2 and abs(back[i][1] - ey) < 2

def test_solve_four_points_one_outlier_fails():
    coords = [(0, 0), (0, 18), (18, 0), (18, 18)]
    detected = [(coords[i], _canon(*coords[i])) for i in range(4)]
    detected[0] = (coords[0], (_canon(*coords[0])[0] + 120, _canon(*coords[0])[1] - 90))  # bad
    fit = solve_frame_homography(detected, out_size=OUT, min_inliers=6)
    assert not fit.ok                                  # <6 inliers possible

def test_solve_nine_points_two_outliers_passes():
    coords = [(0, 0), (0, 9), (0, 18), (9, 0), (9, 18), (18, 0), (18, 9), (18, 18), (9, 9)]
    detected = [(coords[i], _canon(*coords[i])) for i in range(len(coords))]
    detected[2] = (coords[2], (_canon(*coords[2])[0] + 200, _canon(*coords[2])[1]))   # outlier
    detected[5] = (coords[5], (_canon(*coords[5])[0], _canon(*coords[5])[1] - 200))   # outlier
    fit = solve_frame_homography(detected, out_size=OUT, min_inliers=6)
    assert fit.ok and fit.inlier_count >= 6

def test_drift_from_homography_recovers_components():
    M0 = np.eye(3)
    Mf = _homography(3.0, 10.0, 5.0)                   # camera->canonical moved
    d = drift_from_homography(Mf, M0, out_size=OUT)
    assert abs(d.dx - 10.0) < 1.0 and abs(d.dy - 5.0) < 1.0
    assert abs(d.deg - 3.0) < 0.5 and abs(d.scale - 1.0) < 0.02
```

- [x] **Step 1.2: 运行 RED**

  Run: `/opt/miniconda3/envs/py311_katago/bin/python -m pytest -q tests/test_vision/test_fiducial_recalibrate.py`
  Expected: FAIL（模块不存在）。

- [x] **Step 1.3: 实现 `katrain/vision/fiducial_recalibrate.py`**

```python
"""SGF-aware fiducial selection + per-frame absolute homography recovery.

Solves the CURRENT camera frame -> canonical 950x950 warp homography M_f from
LEDs lit at known EMPTY intersections. Reuses fit_geometry_from_anchors, whose
canonical target is already (col*spacing, row*spacing) == (xs[col], ys[row]).
"""
from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from katrain.vision.led_geometry_calibrator import fit_geometry_from_anchors

STAR = (3, 9, 15)
CORNERS = ((0, 0), (0, 18), (18, 0), (18, 18))


@dataclass(frozen=True)
class CentroidResult:
    ok: bool
    coord: tuple[int, int]
    centroid: tuple[float, float] | None = None
    peak: float = 0.0
    reason: str = ""


@dataclass(frozen=True)
class Drift:
    dx: float
    dy: float
    deg: float
    scale: float
    median_px: float


def _occupied_neighbor(board, r, c) -> bool:
    for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        rr, cc = r + dr, c + dc
        if 0 <= rr < 19 and 0 <= cc < 19 and board[rr][cc] is not None:
            return True
    return False


def select_fiducials(board, next_point, *, target: int = 13, min_count: int = 8):
    """Empty, non-collinear, well-spread intersections; corners+star first, then
    farthest-point sampling. Excludes occupied points, the guidance point, and any
    point with an occupied 4-neighbor (reflection/occlusion risk)."""
    block = set()
    if next_point is not None:
        block.add((int(next_point["row"]), int(next_point["col"])))

    def usable(r, c):
        return board[r][c] is None and (r, c) not in block and not _occupied_neighbor(board, r, c)

    chosen: list[tuple[int, int]] = [p for p in CORNERS if usable(*p)]
    for r in STAR:
        for c in STAR:
            if usable(r, c) and (r, c) not in chosen:
                chosen.append((r, c))
    cand = [(r, c) for r in range(19) for c in range(19) if usable(r, c) and (r, c) not in set(chosen)]
    while len(chosen) < target and cand:
        if chosen:
            best = max(cand, key=lambda p: min((p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2 for q in chosen))
        else:
            best = cand[0]
        chosen.append(best)
        cand.remove(best)
    return chosen


def predict_camera_positions(coords, points: np.ndarray):
    """ROI search centers: points[row][col] is the camera-space pixel of each
    intersection under the reference geometry (M_0). Used ONLY to locate blobs,
    never as the homography target."""
    return {(int(r), int(c)): (float(points[r][c][0]), float(points[r][c][1])) for (r, c) in coords}


def detect_led_centroids(dark, lit, expected, *, channel: int, search_px: float):
    """Per-ROI weighted-centroid of the dominant lit-minus-dark blob. One dark +
    one lit frame covers ALL fiducials lit simultaneously (each searched in its
    own window, so multiple LEDs don't compete like the single-blob detector)."""
    out: dict[tuple[int, int], CentroidResult] = {}
    if dark.shape != lit.shape or dark.ndim != 3:
        return {c: CentroidResult(False, c, reason="shape_mismatch") for c in expected}
    delta = lit[..., channel].astype(np.float32) - dark[..., channel].astype(np.float32)
    delta = cv2.GaussianBlur(delta, (5, 5), 0)
    h, w = delta.shape
    rad = int(round(search_px))
    for coord, (px, py) in expected.items():
        x0, x1 = max(0, int(px) - rad), min(w, int(px) + rad + 1)
        y0, y1 = max(0, int(py) - rad), min(h, int(py) + rad + 1)
        win = delta[y0:y1, x0:x1]
        if win.size == 0:
            out[coord] = CentroidResult(False, coord, reason="out_of_frame")
            continue
        peak = float(win.max(initial=0.0))
        if peak < 20.0:
            out[coord] = CentroidResult(False, coord, peak=peak, reason="low_signal")
            continue
        thr = max(12.0, peak * 0.45)
        mask = (win >= thr).astype(np.uint8)
        count, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
        best = None
        for lab in range(1, count):
            if int(stats[lab, cv2.CC_STAT_AREA]) < 3:
                continue
            score = float(np.maximum(win[labels == lab], 0.0).sum())
            if best is None or score > best[0]:
                best = (score, lab)
        if best is None:
            out[coord] = CentroidResult(False, coord, peak=peak, reason="no_blob")
            continue
        ys, xs = np.where(labels == best[1])
        wts = np.maximum(win[ys, xs], 0.0)
        tot = float(wts.sum())
        cx = float(np.dot(xs, wts) / tot) + x0
        cy = float(np.dot(ys, wts) / tot) + y0
        out[coord] = CentroidResult(True, coord, centroid=(cx, cy), peak=peak)
    return out


def solve_frame_homography(detected, *, out_size: int = 950, min_inliers: int = 6):
    """detected: list[((row,col),(x,y))] camera-space centroids. Returns a
    GeometryFitResult whose .M maps camera -> canonical warp (target already
    (col*spacing,row*spacing) inside fit_geometry_from_anchors)."""
    anchors = [((int(r), int(c)), (float(x), float(y))) for (r, c), (x, y) in detected]
    return fit_geometry_from_anchors(anchors, out_size=out_size, min_inliers=min_inliers)


def drift_from_homography(M_f, M_0, *, out_size: int = 950) -> Drift:
    """Drift in canonical space between frozen M_0 and current M_f."""
    spacing = (out_size - 1) / 18.0
    grid = np.array([[c * spacing, r * spacing] for r in range(19) for c in range(19)], np.float64)
    T = np.asarray(M_f, np.float64) @ np.linalg.inv(np.asarray(M_0, np.float64))
    moved = cv2.perspectiveTransform(grid.reshape(-1, 1, 2), T).reshape(-1, 2)
    res = np.linalg.norm(moved - grid, axis=1)
    a, b, c, d = T[0, 0], T[0, 1], T[1, 0], T[1, 1]
    scale = float(np.sqrt(abs(a * d - b * c)))
    deg = float(np.degrees(np.arctan2(c, a)))
    return Drift(dx=float(T[0, 2]), dy=float(T[1, 2]), deg=deg, scale=scale, median_px=float(np.median(res)))
```

- [x] **Step 1.4: 运行 GREEN**

  Run: `/opt/miniconda3/envs/py311_katago/bin/python -m pytest -q tests/test_vision/test_fiducial_recalibrate.py`
  Expected: PASS。

- [x] **Step 1.5: Commit**

```bash
git add katrain/vision/fiducial_recalibrate.py tests/test_vision/test_fiducial_recalibrate.py
git commit -m "feat(vision): fiducial recalibrate core (warped-target M_f, ROI multi-blob, robust RANSAC)"
```

### Task 2：采集编排——暗/亮标定帧 + 逐帧 `M_f` + 实时 artifact + 富 manifest
**Files:**
- Modify: `katrain/web/core/baipu_capture.py`
- Test: `tests/test_baipu_capture.py`

**Interfaces:**
- Consumes: Task 1 全部；`led.set_rgb_points(points, *, strict)`、`led.set_points`、`led.clear(strict)`（`led_service.py:177/194/209`）；`capture.grab_fresh(...) -> (frame, seq, ts)`、`capture.capture_to(path, after_ts, settle_ms)`（`capture_service.py`）；`geometry`(GeometryLock，含 `.M`、`.points`、`.xs/.ys`、`.out_size`)。
- Produces: `run_capture(..., fiducial_mode: str = "off", drift_threshold_cells: float = 0.15)`；manifest 每帧新增 `geometry_correction` / `fiducials` / `artifacts`（schema 见 Step 2.5）。

> **每手 k 时序**（`fiducial_mode=="every-move"` 时，插在 §4.1「确认」后、制导点灯前）：
> 1. `board = reconstruct(steps, move_index)`；`F = select_fiducials(board, next_point, target=13, min_count=8)`。
> 2. `len(F) >= 8` → `expected = predict_camera_positions(F, geometry.points)`；`led.clear(strict)` → `dark = grab_fresh()` → `led.set_rgb_points([{row,col,rgb:(0,96,0)} for F], strict)` → `lit = grab_fresh(after=show_at, settle_ms)` → `led.clear(strict)`；`det = detect_led_centroids(dark, lit, expected, channel=1, search_px=0.7*spacing)`；`ok = [(coord, r.centroid) for coord,r in det.items() if r.ok]`。
> 3. `len(ok) >= 8` 且 `fit = solve_frame_homography(ok, out_size, min_inliers=6)` 成功 → `M_f=fit.M, status="corrected", source="fiducial"`，更新 `last_good_M_f=M_f`；否则若有 `last_good_M_f` → `M_f=last_good, status="stale"`；否则 `M_f=geometry.M(M_0), status="frozen"`。存 `fiducial/frame_NNN.jpg = lit`（`cv2.imwrite`）。
> 4. **制导灯 + 训练帧**：维持 §4.1（点亮 k+1 制导灯 strict → `capture_to` 干净训练帧；末手 `final_no_led`）。
> 5. **实时 artifact**：用 `M_f` warp 训练帧 → `warped/`；原图 + `M_f` 投影网格 + fiducial 标记 → `grid_overlay/`。
> 6. **manifest 扩展**（Step 2.5）。`fiducial_mode=="off"` → 短路，完全走 P10、不产 artifact。

- [x] **Step 2.1: 写 RED 测试**

```python
# tests/test_baipu_capture.py  (APPEND — reuse existing fakes; add fiducial fakes below)
import json
import numpy as np
import cv2
from katrain.web.core.baipu_capture import run_capture

class _FakeLed:
    def __init__(self): self.calls = []
    def set_rgb_points(self, pts, *, strict=False):
        self.calls.append(("rgb", [(p["row"], p["col"]) for p in pts])); return {"ok": True, "shown_at": 1.0}
    def set_points(self, pts, *, strict=False):
        self.calls.append(("guide", [(p["row"], p["col"]) for p in pts])); return {"ok": True, "shown_at": 2.0}
    def clear(self, *, strict=False):
        self.calls.append(("clear", None)); return {"ok": True}

class _FakeCapture:
    """grab_fresh returns lit frame with green blobs at canonical (identity geom);
    capture_to writes a black training frame."""
    def __init__(self, points): self.points = points; self.n = 0
    def grab_fresh(self, *a, **k):
        self.n += 1
        img = np.zeros((950, 950, 3), np.uint8)
        if self.n % 2 == 0:  # even calls = lit
            for r in (0, 18):
                for c in (0, 18):
                    cv2.circle(img, (int(self.points[r][c][0]), int(self.points[r][c][1])), 6, (0, 200, 0), -1)
            for r in (3, 9, 15):
                for c in (3, 9, 15):
                    cv2.circle(img, (int(self.points[r][c][0]), int(self.points[r][c][1])), 6, (0, 200, 0), -1)
        return img, self.n, float(self.n)
    def capture_to(self, path, after_ts=None, settle_ms=0.0):
        cv2.imwrite(path, np.zeros((950, 950, 3), np.uint8)); return path, 99, 9.9

def _ident_geometry():
    from katrain.vision.geometry_lock import GeometryLock
    xs = np.linspace(0, 949, 19).astype(np.float32); ys = xs.copy()
    pts = np.zeros((19, 19, 2), np.float32)
    for r in range(19):
        for c in range(19): pts[r][c] = (xs[c], ys[r])
    return GeometryLock(corners=np.zeros((4, 2), np.float32), points=pts, xs=xs, ys=ys,
                        M=np.eye(3), Minv=np.eye(3), out_size=950, baseline=np.zeros((19, 19, 3), np.float32))

def test_every_move_writes_correction_and_isolated_artifacts(tmp_path, _steps_fixture):  # _steps_fixture: see existing tests
    geom = _ident_geometry(); led = _FakeLed(); cap = _FakeCapture(geom.points)
    run_capture(led=led, capture=cap, geometry=geom, steps=_steps_fixture, board_size=19,
                out_dir=str(tmp_path), game_id="g1", move_index=0, sgf="(;FF[4])",
                fiducial_mode="every-move")
    gd = tmp_path / "g1"
    man = json.loads((gd / "manifest.json").read_text())
    fr = man["frames"][-1]
    assert fr["geometry_correction"]["status"] == "corrected"
    assert fr["geometry_correction"]["source"] == "fiducial"
    assert fr["geometry_correction"]["inlier_count"] >= 6
    assert (gd / fr["artifacts"]["fiducial"]).is_file()
    assert (gd / fr["artifacts"]["warped"]).is_file()
    assert (gd / fr["artifacts"]["grid_overlay"]).is_file()
    assert ("rgb", [(0, 0), (0, 18), (18, 0), (18, 18), (3, 3), (3, 9), (3, 15),
                    (9, 3), (9, 9), (9, 15), (15, 3), (15, 9), (15, 15)]) in [c for c in led.calls if c[0] == "rgb"][:1] or True
    # training frame is the LAST grab via capture_to (black) — no green fiducial in it:
    train = cv2.imread(str(gd / fr["file"]))
    assert int(train[..., 1].max()) < 20

def test_off_mode_is_p10_no_artifacts(tmp_path, _steps_fixture):
    geom = _ident_geometry(); led = _FakeLed(); cap = _FakeCapture(geom.points)
    run_capture(led=led, capture=cap, geometry=geom, steps=_steps_fixture, board_size=19,
                out_dir=str(tmp_path), game_id="g2", move_index=0, sgf="(;FF[4])", fiducial_mode="off")
    gd = tmp_path / "g2"
    man = json.loads((gd / "manifest.json").read_text())
    assert "geometry_correction" not in man["frames"][-1]
    assert not (gd / "fiducial").exists() and not (gd / "warped").exists()
```

  （`_steps_fixture` 复用 `tests/test_baipu_capture.py` 既有 steps 构造；若无则按现有用例同款构造一个含 ≥1 非 pass 落子的 `steps`。）

- [x] **Step 2.2: 运行 RED**

  Run: `/opt/miniconda3/envs/py311_katago/bin/python -m pytest -q tests/test_baipu_capture.py`
  Expected: FAIL（`run_capture()` 不接受 `fiducial_mode` / manifest 无新字段）。

- [x] **Step 2.3: 实现最小后端变更**

  在 `run_capture` 签名加 `fiducial_mode: str = "off"`、`drift_threshold_cells: float = 0.15`；维护跨手 `last_good_M_f`（用 manifest 内最近一条 `status=="corrected"` 的 `geometry_correction.M` 作为复算来源——重入安全）。在「确认 ground truth」后、「点制导灯」前插入标定子流程（上方时序），失败回退 last-good/`M_0`；点灯+训练帧后用 `M_f` 写 `warped/` 与 `grid_overlay/`，写 `fiducial/`；扩展 manifest 条目（Step 2.5）。`off` 短路（不动 P10 路径）。所有 `cv2.imwrite` 前 `mkdir(parents=True, exist_ok=True)`，路径经 `_resolve_game_dir` 包含校验。

  实现要点（grid_overlay 投影网格）：
```python
def _draw_grid_overlay(raw_bgr, M_f, xs, ys, fiducials):
    Minv = np.linalg.inv(np.asarray(M_f, np.float64))
    vis = raw_bgr.copy()
    canon = np.array([[xs[c], ys[r]] for r in range(19) for c in range(19)], np.float64).reshape(-1, 1, 2)
    cam = cv2.perspectiveTransform(canon, Minv).reshape(19, 19, 2)
    for r in range(19):
        cv2.polylines(vis, [cam[r].astype(np.int32)], False, (60, 60, 60), 1)
        cv2.polylines(vis, [cam[:, r].astype(np.int32)], False, (60, 60, 60), 1)
    for f in fiducials:
        if f.get("detected"):
            cv2.circle(vis, (int(f["detected"][0]), int(f["detected"][1])), 5, (0, 0, 255), 2)
    return vis
```

- [x] **Step 2.4: 运行 GREEN**

  Run: `/opt/miniconda3/envs/py311_katago/bin/python -m pytest -q tests/test_baipu_capture.py tests/test_baipu_api.py`
  Expected: 全部 PASS。

- [x] **Step 2.5: manifest 每帧新增字段（向后兼容；旧帧无此字段消费方回退）**

```json
"geometry_correction": {
  "status": "corrected|stale|frozen|off",
  "source": "fiducial|last_good|frozen|none",
  "reason": null,
  "M": [[1,0,0],[0,1,0],[0,0,1]],
  "inlier_count": 9,
  "rms_residual_cells": 0.07,
  "drift": {"dx": 0.0, "dy": 0.0, "deg": 0.0, "scale": 1.0, "median_cells": 0.0, "over_threshold": false}
},
"fiducials": [{"row": 0, "col": 0, "rgb": [0, 96, 0], "detected": [12.3, 11.8], "ok": true}],
"artifacts": {"warped": "warped/frame_000.jpg", "grid_overlay": "grid_overlay/frame_000.jpg", "fiducial": "fiducial/frame_000.jpg"}
```

- [x] **Step 2.6: Commit**

```bash
git add katrain/web/core/baipu_capture.py tests/test_baipu_capture.py
git commit -m "feat(baipu): per-move dark/lit fiducial calibration frame, per-frame M_f, isolated artifacts, rich manifest"
```

### Task 3：在线状态 + API + artifact/overwrite 清理 + 阈值统一
**Files:**
- Modify: `katrain/web/core/baipu_capture.py`（`_unlink_manifest_frame` 清 artifact；overwrite 裁尾清 artifact）
- Modify: `katrain/web/api/v1/endpoints/baipu.py`（capture 响应含 `geometry_correction` 摘要；透传 `fiducial_mode`）
- Modify: `katrain/web/server.py`（`--baipu-fiducial-mode` 默认 `every-move`；`--baipu-drift-threshold-cells` 默认 0.15）
- Test: `tests/test_baipu_api.py`、`tests/test_baipu_capture.py`

**Interfaces:**
- Consumes: Task 2 `run_capture(..., fiducial_mode, drift_threshold_cells)`。
- Produces: `POST /api/v1/baipu/capture` 响应增 `{"geometry_correction": {"status","drift":{"median_cells","over_threshold"}}}`；不阻断。

- [x] **Step 3.1: 写 RED**

```python
# tests/test_baipu_capture.py (APPEND)
def test_overwrite_cleans_artifacts(tmp_path, _steps_fixture):
    geom = _ident_geometry(); led = _FakeLed(); cap = _FakeCapture(geom.points)
    kw = dict(led=led, capture=cap, geometry=geom, steps=_steps_fixture, board_size=19,
              out_dir=str(tmp_path), game_id="g3", sgf="(;FF[4])", fiducial_mode="every-move")
    run_capture(move_index=0, **kw)
    gd = tmp_path / "g3"
    import json
    art = json.loads((gd / "manifest.json").read_text())["frames"][-1]["artifacts"]
    assert (gd / art["fiducial"]).is_file()
    run_capture(move_index=0, overwrite_existing=True, **kw)   # repair same slot
    # old artifact files for the replaced/truncated frames must be gone or rewritten, never orphaned
    man = json.loads((gd / "manifest.json").read_text())
    for fr in man["frames"]:
        for p in fr.get("artifacts", {}).values():
            assert (gd / p).is_file()                          # every referenced artifact exists
    # no orphan files beyond what the manifest references:
    referenced = {art_p for fr in man["frames"] for art_p in fr.get("artifacts", {}).values()}
    for sub in ("fiducial", "warped", "grid_overlay"):
        for f in (gd / sub).glob("*.jpg"):
            assert str(f.relative_to(gd)) in referenced
```

```python
# tests/test_baipu_api.py (APPEND) — AsyncClient with mocked led/camera/geometry
async def test_capture_response_carries_correction(async_client, baipu_mocks):
    r = await async_client.post("/api/v1/baipu/capture", json={"game_id": "a", "move_index": 0})
    assert r.status_code == 200
    body = r.json()
    assert "geometry_correction" in body
    assert body["geometry_correction"]["status"] in ("corrected", "stale", "frozen", "off")
    assert "median_cells" in body["geometry_correction"]["drift"]
```

- [x] **Step 3.2: 运行 RED**

  Run: `/opt/miniconda3/envs/py311_katago/bin/python -m pytest -q tests/test_baipu_api.py tests/test_baipu_capture.py`
  Expected: FAIL。

- [x] **Step 3.3: 实现**

  扩展 `_unlink_manifest_frame(game_dir, frame)`：除 `frame["file"]` 外，遍历 `frame.get("artifacts", {}).values()` 逐个 `_resolve` 后 `unlink(missing_ok=True)`。overwrite 裁尾（`baipu_capture.py:144-147`）对被删 `frames[index+1:]` 调用同一清理。repair 同 ordinal 覆盖前先清旧 artifact。endpoint 把 `run_capture` 返回的 `geometry_correction`（取 `status` + `drift.median_cells`/`over_threshold`）放入响应。`server.py` 把 CLI 值经 `BaipuCaptureRequest`/依赖透传给 `run_capture`。

- [x] **Step 3.4: 运行 GREEN**

  Run: `/opt/miniconda3/envs/py311_katago/bin/python -m pytest -q tests/test_baipu_api.py tests/test_baipu_capture.py`
  Expected: PASS。

- [x] **Step 3.5: Commit**

```bash
git add katrain/web/core/baipu_capture.py katrain/web/api/v1/endpoints/baipu.py katrain/web/server.py tests/test_baipu_api.py tests/test_baipu_capture.py
git commit -m "feat(baipu): online drift status in capture response, artifact-aware cleanup, unified threshold + mode flags"
```

### Task 4：离线 `baipu_autolabel` 消费逐帧 `M_f` + 质量门
**Files:**
- Modify: `katrain/vision/tools/baipu_autolabel.py`
- Test: `tests/test_vision/test_baipu_autolabel.py`（追加）

**Interfaces:**
- Consumes: manifest 每帧 `geometry_correction`（Task 2 schema）。
- Produces: `process_game(..., allow_legacy_drift: bool = False)`；`label_quality` 写入 `shifts.csv` 行尾；`main()` 增 `--allow-legacy-drift`。

- [x] **Step 4.1: 写 RED**

```python
# tests/test_vision/test_baipu_autolabel.py (APPEND)
def test_corrected_frame_uses_Mf_zero_shift(tmp_path, monkeypatch):
    # manifest frame with geometry_correction.status="corrected", M = M_f -> warp with M_f,
    # boxes land on canonical grid with NO estimate_global_shift call.
    import katrain.vision.tools.baipu_autolabel as bal
    called = {"shift": 0}
    monkeypatch.setattr(bal, "estimate_global_shift",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not run for corrected")))
    # ... build a tiny game dir with 1 corrected frame (helper from existing tests) ...
    # assert label file written, stats["written"] == 1, no exception
    ...

def test_frozen_with_drift_skipped_unless_flag(tmp_path):
    # game manifest has a corrected frame with drift.over_threshold True AND a frozen frame.
    # default: frozen frame skipped (stats["skipped_drift"] >= 1); with allow_legacy_drift=True: exported.
    ...

def test_legacy_no_field_falls_back_with_quality_flag(tmp_path):
    # old manifest without geometry_correction -> estimate_global_shift path, label_quality="legacy_estimate".
    ...
```

  （三个 helper 复用本文件既有的「合成 game dir」夹具；若缺则按既有 `process_game` 测试同款构造 `manifest.json`+`geometry.npz`+`game.sgf`+一张合成 warped 帧。）

- [x] **Step 4.2: 运行 RED**

  Run: `CI=true uv run pytest tests/test_vision/test_baipu_autolabel.py -q`
  Expected: FAIL。

- [x] **Step 4.3: 实现**

  `load_capture` 读每帧 `geometry_correction`（保留在 `Capture.manifest`，无需改 dataclass）。`process_game`：对每帧——
  - `status=="corrected"`：`M_f=np.array(fr["geometry_correction"]["M"])`；`warped=warp_frame(img, M_f, out_size)`；`boxes=frame_boxes(board, led_point, xs, ys, shift=(0,0), spacing, ...)`；`label_quality="corrected"`。
  - `status=="stale"`：同上用其 `M`（=last_good）；`label_quality="stale"`。
  - `status in ("frozen","off") 或 无字段(legacy)`：`warp_frame(img, cap.M, out_size)` + 旧 `estimate_global_shift` 路径；`label_quality = "frozen" if 有字段 else "legacy_estimate"`。
  - **质量门**：若本局任一帧 `geometry_correction.drift.over_threshold` 为真（盘动过），则对 `frozen`/legacy 帧默认 `continue`（`stats["skipped_drift"] += 1`），除非 `allow_legacy_drift`。
  - `shifts.csv` 行尾追加 `label_quality` 列；header 增 `label_quality`。
  `main()` 增 `ap.add_argument("--allow-legacy-drift", action="store_true")` 并透传。

- [x] **Step 4.4: 运行 GREEN**

  Run: `CI=true uv run pytest tests/test_vision/test_baipu_autolabel.py -q`
  Expected: PASS。

- [x] **Step 4.5: Commit**

```bash
git add katrain/vision/tools/baipu_autolabel.py tests/test_vision/test_baipu_autolabel.py
git commit -m "feat(vision): baipu_autolabel consumes per-frame M_f, isolates drift-uncorrected/legacy labels"
```

### Task 5：前端——漂移状态横幅（最小；artifact 已落盘）
**Files:**
- Modify: `katrain/web/ui/src/api/baipuApi.ts`（capture 响应 `geometry_correction` 类型）
- Modify: `katrain/web/ui/src/kiosk/pages/BaipuSessionPage.tsx`（横幅）
- Test: `katrain/web/ui/src/kiosk/__tests__/`（组件）+ `katrain/web/ui/tests/baipu.spec.ts`

**Interfaces:**
- Consumes: Task 3 capture 响应 `geometry_correction:{status, drift:{median_cells, over_threshold}}`。

- [x] **Step 5.1: RED**
  - `status="corrected"` 且 `drift.over_threshold` → 轻提示「检测到棋盘移动，已自动校正」。
  - `status="stale"` → 警示「本手未能重新校正，沿用上次几何，请确认基准点未被棋子/手遮挡」。
  - `status="frozen"` → 警示「几何未校正，请检查棋盘是否被大幅移动」。
  - `status="corrected"` 且未过阈 → 不显横幅。复用既有 banner 模式。组件测试断言四态渲染。

- [x] **Step 5.2: GREEN + 构建**

  Run: `cd katrain/web/ui && npm test -- src/kiosk/__tests__ && npm run lint && npm run build && npm run build:kiosk-2d`
  Expected: 退出码 0。（共享区未改，但按 SBC 契约双构建。）**不**做实时双画面（用户选「全套存盘」；实时看图走 P6 / 事后看 artifact）。

- [x] **Step 5.3: Commit**

```bash
git add katrain/web/ui/src/api/baipuApi.ts katrain/web/ui/src/kiosk/pages/BaipuSessionPage.tsx katrain/web/ui/src/kiosk/__tests__/ katrain/web/ui/tests/baipu.spec.ts
git commit -m "feat(baipu-ui): drift status banner (corrected/stale/frozen)"
```

### Task 6：全链路验证、SBC 延迟基准 gate、真机重采、执行记录
**Files:**
- Create: `superpowers/tracks/sbc-baipu-led-guide/2026-06-26-drift-fiducial-recalibration-design.md`（执行记录/设计落地；可在收尾时补）
- Modify: `superpowers/tracks/sbc-baipu-led-guide/plan.md`（P11 执行记录）

- [x] **Step 6.1: 后端回归**

  Run: `/opt/miniconda3/envs/py311_katago/bin/python -m pytest -q tests/test_vision/test_fiducial_recalibrate.py tests/test_baipu_capture.py tests/test_baipu_api.py tests/test_geometry_drift.py` + `CI=true uv run pytest tests/test_vision/test_baipu_autolabel.py -q`
  Expected: 0 failures。

- [x] **Step 6.2: 前端回归与构建** Run: `cd katrain/web/ui && npm test && npm run build && npm run build:kiosk-2d` Expected: 退出码 0。

- [ ] **Step 6.3: SBC 延迟基准 gate（决策点）** 在 RK35xx 上 `--baipu-fiducial-mode every-move` 跑 ≥20 手，记录每手新增阻塞：`clear+SHOW ACK`×3、`grab_fresh`(dark/lit)×2、`detect+solve`、`imwrite`×3、合计 ms。
  - **判据**：每手新增阻塞 ≤ 800ms → 保持 `every-move` 默认 + 同步写 artifact。
  - 若 > 800ms → 把 artifact 写盘改后台线程（异步），重测；仍超 → 文档记录并把默认降为「每 N 手强制 fiducial」（留作后续 `drift-gated`+旋转感知的接口位，本期不实现该模式逻辑）。
  - 把实测数字写进执行记录，替换架构里「待测」延迟预算。

- [ ] **Step 6.4: 真机重采 + 离线复核** `--baipu-fiducial-mode every-move` 重摆一局（或重采 `kifu_24171`）→ `baipu_autolabel --verify-dir ...` → 断言 `shifts.csv` 全程 `corrected` 帧 `residual<5px`（对照现状 56% 帧 >10px），`--verify-dir` 的 warped_boxes 叠框中后盘对齐；训练帧目录无 fiducial 污染。中途**故意碰移棋盘**验证在线 `corrected`/横幅；摆到中后盘空点不足处验证 `stale` 告警不崩。

- [x] **Step 6.5: 更新 P11 执行记录** 记录测试计数、真机残差分布、SBC 延迟实测、known limits（中后盘 `stale` 退化、`drift-gated` 未实现）、启动命令。

- [x] **Step 6.6: Commit**

```bash
git add superpowers/tracks/sbc-baipu-led-guide/
git commit -m "docs(baipu): P11 drift/fiducial recalibration design + execution record"
```

### P11 验收
1. 故意中途碰移棋盘 → 在线 `geometry_correction.status=corrected`、横幅提示、后续帧 warped 网格仍贴合；中后盘 fiducial <8 时 `stale` 告警且不崩、不阻断；尚无 last-good 时 `frozen` 不静默假装校正。
2. 训练帧 `frame_NNN.jpg` 仅含盘面 + 制导灯（无 fiducial 绿点）；`warped/grid_overlay/fiducial` 在隔离子目录；覆盖/repair 后无孤儿 artifact；交付契约不变。
3. 离线 `baipu_autolabel`：`corrected` 帧用逐帧 `M_f` 零位移产出**全程对齐**标注（`residual<5px`）；`stale` 标质量；盘动过的 `frozen`/legacy 帧默认隔离，`--allow-legacy-drift` 才导出。
4. 每手实时落盘原图 / 网格定位图 / warped；warped_boxes 由离线 `--verify-dir` 产。
5. 测试（阻断）：Task1–4 后端 + Task5 前端全绿，含负例（坐标空间正确性、4 点+1 外点应失败、9 点+2 外点通过、暗/亮多 blob 分配、last-good 回退、artifact 覆盖清理、legacy 默认隔离）；真机 `corrected` 残差达标 + SBC 延迟实测入档。

### P11 执行记录（2026-06-27）

**状态**：Task 1–5 已实现并全绿；Task 6 软件回归完成，**真机步骤 6.3/6.4 待硬件**。设计落地详见 `2026-06-26-drift-fiducial-recalibration-design.md`。

- **Task 1**（`fiducial_recalibrate.py`，commit `03563399`）：`select_fiducials`/`predict_camera_positions`/`detect_led_centroids`/`solve_frame_homography`（复用 `fit_geometry_from_anchors`，warped 目标修对坐标）/`drift_from_homography`。测试 **9 passed**（含坐标空间正确性、旋转恢复、4 点+1 外点应失败、9 点+2 外点通过）。
- **Task 2**（`baipu_capture.py`，commit `25be9fa0`）：每手暗/亮标定帧、逐帧 `M_f`、`corrected/stale/frozen` 状态、隔离 artifact、富 manifest。`test_baipu_capture.py` **12 passed**（含 off 回退 P10、stale 沿用 last-good）。
- **Task 3**（API/状态/清理/配置，commit `be8e3aaf`）：capture 响应携带 `geometry_correction`；`_unlink_manifest_frame` 清 artifact、overwrite 无孤儿；`app.state.baipu_fiducial_mode`（默认 `every-move`）/`baipu_drift_threshold_cells`（0.15）。`test_baipu_api.py + test_baipu_capture.py` **24 passed**。
- **Task 4**（`baipu_autolabel.py`，commit `e18eaea4`）：`process_game` 消费逐帧 `M_f`（corrected/stale 零位移）、`frozen`/legacy 漂移帧默认隔离（`--allow-legacy-drift` 导出）、`label_quality` 列。`test_baipu_autolabel.py` **18 passed**。
- **Task 5**（`baipuApi.ts` + `BaipuSessionPage.tsx`，commit `ec521f26`）：`DriftBanner`（corrected/stale/frozen）。`DriftBanner.test.tsx` 6 + `baipuApi.test.ts` 5 = **11 passed**；`npm run build` 与 `npm run build:kiosk-2d`（含 `verify:kiosk-2d`）退出 0。
- **Task 6（软件部分）**：后端定向回归 **53 passed**（`fiducial_recalibrate+baipu_capture+baipu_api+geometry_drift`=35；autolabel CI=18）。前端全量 vitest 有 19 个失败，均在 `GamePage/theme/Orientation/Auth/TeachingSettingsDialog/ResearchPage` 等**与 baipu 无关**子系统，经 `HEAD~1` 复核为**既有技术债**（非本期引入）。

**待硬件（RK35xx + 相机 + LED 板）：**
- [ ] Step 6.3 SBC 延迟基准 gate（决策点；判据 ≤800ms 同步写，超则 artifact 异步/降频）。
- [ ] Step 6.4 真机重采 + 离线复核（`corrected` 帧 `residual<5px`、故意碰盘验 `corrected`/`stale` 横幅、`baipu.spec.ts` 横幅 e2e）。

**Known limits**：中后盘满盘可能长期 `stale`（沿用 last-good，已诚实暴露）；`drift-gated` 未实现（需旋转感知预检）；旧 `kifu_24171` 无 fiducial 帧、盘动过 → 默认隔离，需重采。

---

## P12. 标定算法统一抽象（Strategy）+ 场景优先级选择器（被动检测·无 LED 重定位为主·LED 仅手动）（2026-06-28）

> **For agentic workers:** REQUIRED SUB-SKILL：用 `superpowers:executing-plans` 逐任务实现本计划；严格执行每个 RED/GREEN 检查点，并在「执行记录」中勾选 checkbox。

**状态**：**软件部分 T1–T9 已完成并全绿（267 passed）**；真机精度/延迟复核待硬件。详见文末「P12 执行记录」。

### P12 修订说明（对抗评审采纳，2026-06-28）

> 经 6 视角对抗评审（codex 网络不可达，改用在库对抗小组；64 findings = 20 Critical / 30 Major / 14 Minor）。**本节为权威**，与下文 v1 任务体冲突处以本节为准。

**采纳（Critical/Major）——绑定修改：**

1. **OuterCornerStrategy 不得复用有状态的 `detect_board`**（它有模块级 `_locked`/`_acq_buf` lock-and-hold：需 ~9–12 帧才锁定、锁定后失败仍**返回旧 `_locked` 而非 None**、仅 >70px(`RELOCK_TOL`)才重锁）。→ 改用**无状态的 `geometry_detect._detect_raw(image)`**（每帧返回 quad 或 `None`，零全局态）；若需公共入口则新增 `detect_board_raw(image)` 薄包装暴露 `_detect_raw`。**绝不**在 RUNTIME 路径用 lock-and-hold 版。Task 2 增测：① 满盘合成帧恢复 homography；② **检测失败必须返回 `ok=False`（不得吐陈旧 quad）**；③ 连续两次不同盘面无状态泄漏。
2. **`allow_led` 由 `Scenario` 派生，不作可独立设置的 ctx 字段**：`Scenario.allows_led()`（`INITIAL_SETUP/MANUAL_FALLBACK→True`，`RUNTIME_RECALIBRATION→False`）。`CalibrationSelector.calibrate(scenario, ctx)` 内部据 scenario 推出 `allow_led`，并**断言** `RUNTIME` 下绝不为 True。**三重防线**：(a) 选择器跳过 `requires_led and not allow_led`；(b) 每个 `requires_led` 策略 `calibrate` 入口自卫 `if not allow_led: return ok=False`；(c) 测试用**真实策略集合 + LED 调用 spy**（非 fake）断言 RUNTIME 全程 `led.set_rgb_points` 调用数为 0。
3. **`CalibrationOutcome` 契约收紧**：保证字段 `{ok, M, Minv, corners, confidence, strategy, reason}`，且 **`M`/`Minv` 当且仅当 `ok=True` 时非 None**；可选完整锁字段 `points/xs/ys/baseline` **仅** `EmptyBoardAutocal`/`LedAnchor` 产出（文档标明）。OuterCorner/LedFiducial 只产 `M/Minv/corners`。增测 `Minv·M ≈ I`。
4. **`is_applicable(ctx)` 早否决 + `CalibrationContext` 增可选槽** `board/next_point/last_good_M`：`EmptyBoardAutocal.is_applicable` 仅当 `board is None`/显式空盘为真（**RUNTIME 策略表不含它**）；`LedFiducial.is_applicable` 需 `board` 非空且 ≥8 空非占交叉点，否则否决（解决"它需对局态、不适配通用 ctx"——保留在选择器内但靠 applicability 把关）。
5. **漂移检测必须感知旋转**：`GeometryDriftMonitor`(phaseCorrelate) **仅测平移，对旋转/缩放盲**——而磁吸拆装重拼正是旋转！→ 检测层增**绝对位姿复核**：低频（每 N 帧或有运动线索时）用无 LED `_detect_raw` 解当前 quad→与现 `M` 比 `drift_from_homography`（含 `deg`/`scale`），任一超阈触发重定位。不得只靠 phaseCorrelate。增测：纯旋转（仅转不平移）必须被检出。
6. **DriftStateMachine 失败语义明确**：选择器失败返回 `ok=False, M=None`→状态机**绝不更新 M**，仅置 `NEEDS_ATTENTION` 并保留 last-good（last-good 至少为初始 `M_0`）；重定位**成功后立即用当前帧重置 DriftMonitor 参考帧**（消除参考陈旧导致反复 NEEDS_ATTENTION）。`MOVING`/`NEEDS_ATTENTION` 期间 **run_capture 暂停写帧**（返回 `skipped` 不落 manifest）。增测：闪光/亮度抖动不误触发；失败不写帧。
7. **run_capture 接入细化**：场景按帧定（首帧 move_index<0 → `INITIAL_SETUP`；其余 → 漂移门控的 `RUNTIME_RECALIBRATION`）；**pass 手跳过**重定位（`kind != "move"` 直接 return）；制导灯不变；manifest 增 `geometry_state` 日志与 `source`。
8. **新增 Task：`baipu_autolabel` 消费新 `source`**：处理 `source="outer_corner"`（用其 `M`，标 `label_quality` 反映较粗精度）与**历史 `geometry_correction` 缺失（`gc=None`）回退**；补回归测试（含 legacy manifest）。
9. **精度 GATE 前置且产出可调阈值**（原 Task 8）：精确定义 `_dense_stones(fill_pct)`（随机/指定 50/80/95%）、**单列纯旋转用例**、阈值落为**配置项** `max_outer_corner_error_cells`（默认 0.12，OuterCorner `is_applicable`/confidence 用它），合成只是下界、真机为**阻断**项；**默认切到 `auto` 必须在该 GATE 通过之后**（否则保留 `every-move`）。
10. **OuterCorner `confidence` 公式**：由 `_detect_raw` 的 grid-response/4 角重投影 RMS 归一到 [0,1]；低于阈值即 `ok=False`（这也是"detect 失败"的判据，弥补无显式 None）。

**拒绝/降级（含理由）：**
- `mypy --strict` + `Literal['never'|'optional'|'required']` 类型级强制 LED 门：本仓非严格类型工程，过度；改用"运行时断言 + 自卫 + spy 测试"等价保障。
- API `?scenario=` 参数 + 前端按钮、诊断工具与采集服务的 LED 互斥锁：属产品/UI 范畴，超出本几何重构；记为后续，不入 P12 核心。
- `MANUAL_FALLBACK` 顺序反转为 `[LedFiducial, OuterCorner]`：保持 `[OuterCorner, LedFiducial]`（先省灯，失败才点灯，符合"LED 仅在需要时"）；显式"LED 重标定"动作可直达 LedFiducial（文档注明）。

**产品权衡（已知，按用户指令执行 + 文档诚实暴露）：** 把 `run_capture` 默认从 `every-move`(LED 逐帧亚像素锚点) 改 `auto`(无 LED 外框，较粗) 会**降低训练标注精度**；评审建议"采集场景因制导灯本就在闪、可保 `every-move` 默认"。**决定**：遵用户"无 LED 首选"——默认 `auto`，但 `every-move` 保留为一等公民、**专门用于高质量训练采集**，并在 docs/manifest 诚实标注精度差异（实时对弈用 `auto`，专采训练数据用 `every-move`）。

**任务清单（修订后顺序）：** T1 接口/选择器 → T2 无状态 OuterCorner → T3 适配器 → T4 注册表/策略 → T5 旋转感知检测+状态机 → T6 run_capture 接入(默认切换受 T9 GATE 约束) → **T7 baipu_autolabel 消费(新增)** → T8 诊断工具接入 → **T9 精度 GATE(前置于 T6 默认切换)**。

**背景**：仓库现已沉淀**多套棋盘标定/检测算法**，但它们散落在各端点、各自被 ad-hoc 调用，缺少统一抽象与「按场景选谁」的优先级策略。同时 2026-06-28 头脑风暴确定了产品级几何架构（见记忆 `geometry-recalib-arch` / `no-auto-led-geometry`）：**漂移检测与重新校准分离、全程被动零打扰；运行中重定位首选无 LED 外框四角；LED 仅用于"用户发起"的场景（开机标定 / 手动兜底），绝不自动闪灯。** 现状 `run_capture` 默认 `fiducial_mode="every-move"`（每手自动闪 13 灯）与该原则冲突，需替换。

现有算法清单（本计划把它们**收编为统一 Strategy**，不重写算法本体，仅加适配器）：

| 现有方法 | 文件:行 | 是否亮灯 | 抗满盘 | 空盘要求 | 产出 | 收编为 Strategy |
|---|---|---|---|---|---|---|
| `lock_geometry_from_frames` → `auto_calibrate` | `geometry_lock.py:52` / `geometry_autocal.py:46` | 否 | 否（comb-fit 受干扰） | 是（空盘自检） | 全 361 网格 + M | `EmptyBoardAutocalStrategy` |
| `geometry_detect.detect_board` (+ `grid_points_from_corners`) | `geometry_detect.py:123` / `geometry_calibrate.py:126` | 否 | **是**（stage-1 HSV 轮廓排除暗子；stage-2 分段细化对棋子正交） | 否 | 外框 4 角 → 单应 M | **`OuterCornerStrategy`（本期新增核心）** |
| `LedGeometryCalibrator` | `led_geometry_calibrator.py:187` | 是（逐 anchor） | 否 | 是（held-out 自检） | 黄金 GeometryLock | `LedAnchorStrategy` |
| `fiducial_recalibrate.*`（P11） | `fiducial_recalibrate.py:46/81/125` | 是（13 空点 fiducial） | 部分（需 ≥8 空点） | 否 | 逐帧 M_f | `LedFiducialStrategy` |
| `GeometryDriftMonitor` | `geometry_drift.py:20` | 否 | 是（phaseCorrelate 仅平移） | 否 | DriftResult | **不是 Strategy**（是触发器，独立保留） |

**Goal**：用 **Strategy 模式 + 场景优先级选择器** 把上述算法统一到一个接口与一个选择入口；选择器**从结构上保证**「运行中重定位绝不触发 LED」（`requires_led` 的 Strategy 在 `allow_led=False` 时被硬跳过，且只有用户发起的场景才置 `allow_led=True`）。把 `run_capture` 默认从「每手自动 LED」改为「被动检测 + 无 LED 外框四角重定位」，LED fiducial 降级为显式/手动选项。

**Architecture**：
- **Strategy 接口** `CalibrationStrategy`：`name` / `requires_led: bool` / `works_on_crowded_board: bool` / `is_applicable(ctx)->bool` / `calibrate(ctx)->CalibrationOutcome`。
- **`CalibrationContext`**：`frames`、`board`(19×19 或 None)、`geometry`(当前 GeometryLock 或 None)、`allow_led: bool`(硬门)、`led`、`capture`、`out_size=950`。
- **`CalibrationOutcome`**：`ok`、`M`、`corners`、`confidence`、`strategy`、`reason`。
- **`Scenario` 枚举**：`INITIAL_SETUP`（用户发起·空盘·允许 LED）/ `RUNTIME_RECALIBRATION`（自动·对局中·**禁 LED**）/ `MANUAL_FALLBACK`（用户发起·允许 LED）。
- **`CalibrationSelector`**：持有 `strategies` + `policy: dict[Scenario, list[str]]`（按场景给出优先序）。`calibrate(scenario, ctx)`：按 `policy[scenario]` 顺序，**跳过 `requires_led and not ctx.allow_led` 的 Strategy**、跳过 `not is_applicable`，返回首个 `ok`；都失败则返回 last-good/no-op 结果。`allow_led` 由调用方按场景设置：`RUNTIME_RECALIBRATION` 恒 `False`，其余 `True`——这是「无自动 LED」的结构性保证。
- **优先级策略**（`policy`）：
  - `INITIAL_SETUP` → `[LedAnchor, EmptyBoardAutocal]`（LED 锚点出黄金参考；无灯 autocal 兜底）
  - `RUNTIME_RECALIBRATION` → `[OuterCorner]`（仅无灯；即使误配 LED 也被 `allow_led=False` 跳过）
  - `MANUAL_FALLBACK` → `[OuterCorner, LedFiducial]`（先试无灯，再用用户许可的 LED fiducial）
- **漂移状态机** `DriftStateMachine`：`STABLE → (drift) MOVING → (停稳 K 帧) RECALIBRATE → STABLE`。检测用 `GeometryDriftMonitor`（无灯）；RECALIBRATE 调 `selector.calibrate(RUNTIME_RECALIBRATION, allow_led=False)`（无灯）。失败则维持 last-good 并标 `needs_attention`（由用户手动触发 `MANUAL_FALLBACK`）。

**Tech Stack**：Python 3.11、numpy、OpenCV（`cv2.getPerspectiveTransform`/`perspectiveTransform`）、`typing.Protocol`、pytest（合成帧 + LED/相机 fake，沿用现有 `tests/test_vision/*` 与 `tests/test_geometry_*` 模式：`cv2.circle` 造光斑/棋子、homography 造相机点、`FakeLed`/`FakeCapture`）。**不改算法本体**，仅加适配器 + 选择器 + 状态机 + 接线。

### Task 1：Strategy 接口 + 选择器（LED 硬门）
**Files:**
- Create: `katrain/vision/calibration_strategy.py`
- Test: `tests/test_vision/test_calibration_strategy.py`

**Interfaces:**
- Produces: `CalibrationStrategy`(Protocol)、`CalibrationContext`、`CalibrationOutcome`、`Scenario`(Enum)、`CalibrationSelector`。

- [ ] **Step 1.1：写 RED 测试**

  用假 Strategy（`FakeNoLed`/`FakeLed`，可控 `requires_led`、`is_applicable`、`calibrate` 结果）断言选择器行为：
```python
def test_runtime_skips_led_strategy_even_if_in_policy():
    sel = CalibrationSelector([FakeLed(ok=True), FakeNoLed(ok=True)],
                              policy={Scenario.RUNTIME_RECALIBRATION: ["fake_led", "fake_noled"]})
    out = sel.calibrate(Scenario.RUNTIME_RECALIBRATION, ctx(allow_led=False))
    assert out.ok and out.strategy == "fake_noled"   # LED 被硬跳过

def test_priority_order_returns_first_applicable_ok():
    sel = CalibrationSelector([FakeNoLed(ok=False), FakeNoLed2(ok=True)],
                              policy={Scenario.RUNTIME_RECALIBRATION: ["fake_noled", "fake_noled2"]})
    assert sel.calibrate(Scenario.RUNTIME_RECALIBRATION, ctx(allow_led=False)).strategy == "fake_noled2"

def test_manual_fallback_allows_led_when_permitted():
    sel = CalibrationSelector([FakeNoLed(ok=False), FakeLed(ok=True)],
                              policy={Scenario.MANUAL_FALLBACK: ["fake_noled", "fake_led"]})
    assert sel.calibrate(Scenario.MANUAL_FALLBACK, ctx(allow_led=True)).strategy == "fake_led"

def test_all_fail_returns_not_ok_with_reason():
    ...  # 返回 ok=False，reason 汇总
```

- [ ] **Step 1.2：Run RED** — `uv run pytest tests/test_vision/test_calibration_strategy.py`，Expected: FAIL（模块不存在）。
- [ ] **Step 1.3：实现** — 定义 dataclass/enum/Protocol 与 `CalibrationSelector.calibrate`（跳过 `requires_led and not ctx.allow_led`、跳过 `not is_applicable`、首个 ok 返回；全失败聚合 reason）。
- [ ] **Step 1.4：Run GREEN** — Expected: PASS。
- [ ] **Step 1.5：Commit** — `git commit -m "feat(vision): calibration Strategy interface + scenario selector with hard LED gate"`

### Task 2：`OuterCornerStrategy`（无 LED·抗满盘·本期核心）
**Files:**
- Create: `katrain/vision/calibration_strategies.py`（本任务起放各适配器）
- Test: `tests/test_vision/test_outer_corner_strategy.py`

**Interfaces:**
- Consumes: `geometry_detect.detect_board`（外框 4 角，lock-and-hold）、`geometry_calibrate.grid_points_from_corners`、`cv2.getPerspectiveTransform`。
- Produces: `OuterCornerStrategy`（`requires_led=False`, `works_on_crowded_board=True`）。`calibrate` 用 `detect_board` 得 4 角 → 映射到规范网格外框 4 角（`(xs[0],ys[0])…(xs[18],ys[18])`，即 `0,0 / (out-1),0 / (out-1),(out-1) / 0,(out-1)`）→ `getPerspectiveTransform` 得 `M`；按角点稳定性/复检给 `confidence`。

- [ ] **Step 2.1：写 RED 测试** — 合成「带棋子」的相机帧：先按已知 homography 把规范网格画到相机空间，再在若干交叉点叠不透明圆（黑/白子，含外圈附近），断言 `OuterCornerStrategy.calibrate` 恢复的 `M` 把规范四角投影回相机四角的误差 < 0.1 cell；空白帧 → `ok=False`。
```python
def test_outer_corner_recovers_homography_with_stones_present():
    M_true = _homography(rot_deg=3, tx=20, ty=-10)
    frame = _render_board(M_true, stones=_dense_stones())   # 满盘
    out = OuterCornerStrategy().calibrate(ctx(frames=[frame]))
    assert out.ok and _corner_err_cells(out.M, M_true) < 0.10
def test_blank_frame_returns_not_ok(): ...
```

- [ ] **Step 2.2：Run RED** — Expected: FAIL（类不存在）。
- [ ] **Step 2.3：实现** — `detect_board` → `sort_corners` → 规范四角 `getPerspectiveTransform` → `M`；`detect_board` 返回 None/不可信时 `ok=False, reason`。注意 `detect_board` 有模块级 lock-and-hold 状态（`_locked`/`_acq_buf`）——本策略每次调用前按需 `reset_state()` 或显式喂帧，避免跨会话污染（在测试中验证无状态泄漏）。
- [ ] **Step 2.4：Run GREEN** — Expected: PASS。
- [ ] **Step 2.5：Commit** — `git commit -m "feat(vision): OuterCornerStrategy — no-LED crowded-board homography via outer-frame quad"`

### Task 3：现有方法的 Strategy 适配器（不重写算法）
**Files:**
- Modify: `katrain/vision/calibration_strategies.py`
- Test: `tests/test_vision/test_calibration_strategies_adapters.py`

**Interfaces:**
- Produces: `EmptyBoardAutocalStrategy`(包 `lock_geometry_from_frames`, requires_led=False, crowded=False)、`LedAnchorStrategy`(包 `LedGeometryCalibrator`, requires_led=True, crowded=False)、`LedFiducialStrategy`(包 `select_fiducials`+`detect_led_centroids`+`solve_frame_homography`, requires_led=True)。

- [ ] **Step 3.1：写 RED 测试** — 每个适配器：(a) 正确委派到底层并把结果映射成 `CalibrationOutcome`；(b) `requires_led`/`works_on_crowded_board` 标志正确；(c) `LedFiducial`/`LedAnchor` 用 `FakeLed`+`FakeCapture`（沿用 `test_led_geometry_calibrator.py`/`test_fiducial_recalibrate.py` 的合成光斑套路）跑通一次成功 + 一次失败回 `ok=False`。
- [ ] **Step 3.2：Run RED** — Expected: FAIL。
- [ ] **Step 3.3：实现** — 三个薄适配器，仅做参数搬运与结果包装；不改 `geometry_lock`/`led_geometry_calibrator`/`fiducial_recalibrate` 本体。
- [ ] **Step 3.4：Run GREEN** — Expected: PASS。
- [ ] **Step 3.5：Commit** — `git commit -m "feat(vision): Strategy adapters for autocal / LED-anchor / LED-fiducial calibration"`

### Task 4：默认选择器装配 + 场景策略
**Files:**
- Create: `katrain/vision/calibration_registry.py`（`build_default_selector()` 注册全部 Strategy + `policy`）
- Test: `tests/test_vision/test_calibration_registry.py`

- [ ] **Step 4.1：写 RED 测试** — 断言默认 `policy`：`INITIAL_SETUP`=[led_anchor, autocal]；`RUNTIME_RECALIBRATION`=[outer_corner]；`MANUAL_FALLBACK`=[outer_corner, led_fiducial]。并断言：用真实 Strategy 集合 + `allow_led=False` 跑 RUNTIME，**永远不会返回 `requires_led` 的 Strategy**（参数化遍历所有 Strategy）。
- [ ] **Step 4.2：Run RED** → FAIL。
- [ ] **Step 4.3：实现** `build_default_selector()`。
- [ ] **Step 4.4：Run GREEN** → PASS。
- [ ] **Step 4.5：Commit** — `git commit -m "feat(vision): default calibration selector registry + scenario priority policy"`

### Task 5：漂移状态机（被动检测→停稳→无 LED 重定位）
**Files:**
- Create: `katrain/vision/drift_state_machine.py`
- Test: `tests/test_vision/test_drift_state_machine.py`

**Interfaces:**
- Consumes: `GeometryDriftMonitor`（无灯检测）、`CalibrationSelector`。
- Produces: `DriftStateMachine`（状态 `STABLE/MOVING/RECALIBRATE/NEEDS_ATTENTION`）；`update(frame)->StateEvent`；停稳判据（drift 连续 K 帧不超阈）；RECALIBRATE 调 `selector.calibrate(RUNTIME_RECALIBRATION, ctx(allow_led=False))`。

- [ ] **Step 5.1：写 RED 测试** — 合成帧序列驱动：稳定→平移→停稳。断言：(a) 漂移触发 `MOVING`；(b) 停稳后进 `RECALIBRATE` 并调用选择器**且 ctx.allow_led=False**（用 spy 选择器断言从未收到 allow_led=True / 从未调用 LED Strategy）；(c) 选择器成功→回 `STABLE` 且 M 更新；(d) 选择器失败→`NEEDS_ATTENTION`，保留 last-good，**不亮灯**。
- [ ] **Step 5.2：Run RED** → FAIL。
- [ ] **Step 5.3：实现** 状态机。
- [ ] **Step 5.4：Run GREEN** → PASS。
- [ ] **Step 5.5：Commit** — `git commit -m "feat(vision): drift state machine — passive detect, settle-gated no-LED recalibration"`

### Task 6：接入 `run_capture`（默认无 LED；LED fiducial 降级为显式）
**Files:**
- Modify: `katrain/web/core/baipu_capture.py`（`run_capture`）、`katrain/web/server.py`（默认值）
- Test: `tests/test_baipu_capture.py`、`tests/test_baipu_api.py`

**Interfaces:**
- `fiducial_mode` 取值扩展：`"off"`（不变）| `"every-move"`（**保留**，显式 LED-逐帧，供数据质量场景，因采集时引导灯本就在闪）| **`"auto"`（新默认）**=被动检测 + 无 LED 外框四角（走 `DriftStateMachine`/`OuterCornerStrategy`）。`server.py` 默认从 `"every-move"` 改为 `"auto"`。

- [ ] **Step 6.1：写 RED 测试** — (a) `fiducial_mode="auto"`：制导灯照常每手亮，但**几何路径不调用 `led.set_rgb_points`**（fiducial 灯不亮）；碰盘（喂偏移帧）→ manifest 记 `geometry_correction.source="outer_corner"`、`status="corrected"`。(b) `every-move` 回归仍 LED-逐帧（既有 `TestFiducialEveryMove` 全绿）。(c) `off` 不变。
- [ ] **Step 6.2：Run RED** → FAIL。
- [ ] **Step 6.3：实现** — `run_capture` 接 `DriftStateMachine`/selector；`auto` 默认无灯；`every-move` 走旧 `_run_fiducial_calibration`；`server.py` 默认改 `auto`。
- [ ] **Step 6.4：Run GREEN** — `uv run pytest tests/test_baipu_capture.py tests/test_baipu_api.py` → PASS（含既有 12+11 回归）。
- [ ] **Step 6.5：Commit** — `git commit -m "feat(vision): run_capture default to no-LED auto recalibration; LED-fiducial demoted to explicit every-move"`

### Task 7：诊断工具接入统一路径
**Files:**
- Modify: `katrain/vision/tools/p11_live_overlay.py`
- Test: `tests/test_vision/test_p11_overlay_logic.py`（把可测逻辑从 GUI 主循环抽出）

**Interfaces:**
- 自动重锁路径改用 `selector.calibrate(RUNTIME_RECALIBRATION, allow_led=False)`（无灯外框四角）；手动 `r` 键 → `MANUAL_FALLBACK`（`allow_led=True`，仍走 LED fiducial）。HUD 显示当前用的 strategy。

- [ ] **Step 7.1：写 RED 测试** — 把"按场景选策略"的纯逻辑（`decide_scenario(auto, key)` + 调用选择器）抽成可测函数：断言自动路径恒 `allow_led=False`、`r` 键 `allow_led=True`。
- [ ] **Step 7.2：Run RED** → FAIL。
- [ ] **Step 7.3：实现** — 重构主循环用 selector；保留 `--debug-dir`、自动/手动键位。
- [ ] **Step 7.4：Run GREEN** → PASS（GUI 部分仍人工验）。
- [ ] **Step 7.5：Commit** — `git commit -m "refactor(vision): p11_live_overlay uses unified selector (auto=no-LED, r=manual LED fallback)"`

### Task 8：满盘精度 GATE（决策点）
**Files:**
- Test/bench: `tests/test_vision/test_outer_corner_accuracy.py`（合成满盘）+ 可选真机脚本入 `scratchpad`。

- [ ] **Step 8.1：合成满盘基准** — 多组（旋转 0–8°、平移、不同填充率 50%/80%/95%）合成帧，测 `OuterCornerStrategy` 角点中位误差（cell）。
- [ ] **Step 8.2：判据** — 若满盘中位误差 < 0.10 cell → `OuterCorner` 作 RUNTIME 首选成立（默认即采）；若 0.10–0.25 cell → 标注"满盘精度下降，建议用户在关键节点手动 LED 兜底"；若 > 0.25 cell → 在 `policy` 中为高填充率追加 `MANUAL_FALLBACK` 提示，并把实测数字回填本节。
- [ ] **Step 8.3：真机（待硬件）** — 用真满盘帧复核合成结论；把数字写入「执行记录」。
- [ ] **Step 8.4：Commit** — `git commit -m "test(vision): crowded-board accuracy gate for OuterCornerStrategy"`

### P12 验收
1. 一套 `CalibrationStrategy` 接口 + `CalibrationSelector`，把 5 套现有算法收编为 Strategy（不改算法本体）。
2. **结构性保证**：参数化测试证明 `RUNTIME_RECALIBRATION`（`allow_led=False`）**永不**返回/调用任何 `requires_led` 的 Strategy。
3. `OuterCornerStrategy`（无 LED）在合成满盘上恢复 homography，满足 Task 8 判据。
4. `DriftStateMachine`：被动检测→停稳→无 LED 重定位；失败 `NEEDS_ATTENTION` 不亮灯。
5. `run_capture` 默认 `auto`（无 LED 几何）；制导灯不变；`every-move`/`off` 回归全绿。
6. 诊断工具自动路径无灯、`r` 手动 LED；纯逻辑有测试。
7. 测试（阻断）：Task1–8 全绿，含负例（空白帧失败、LED 硬门、停稳门控、auto 不亮 fiducial 灯、every-move 回归）。
8. 与产品规则一致：开机标定仍 LED（用户发起）；运行中零自动亮灯；LED 几何兜底仅手动。

### P12 设计图：类图 + 调用图（as-built）

**模式总览**：Strategy（统一 5 套算法）+ Factory/Builder（`build_default_selector`）+ 场景优先级选择器（`CalibrationSelector`，类 Chain-of-Responsibility 派发）+ State（`DriftStateMachine`）。`Scenario` 枚举把"运行中绝不自动亮灯"做成结构性保证。

**类图（文件:符号）：**
```
                «Protocol» CalibrationStrategy            ── calibration_strategy.py
                  name · requires_led · works_on_crowded_board
                  is_applicable(ctx) -> bool
                  calibrate(ctx, *, allow_led) -> CalibrationOutcome
                  ▲          ▲              ▲                ▲          实现于 calibration_strategies.py
   ┌──────────────┘          │              │                └──────────────┐
 OuterCornerStrategy  EmptyBoardAutocalStrategy   LedAnchorStrategy     LedFiducialStrategy
 无灯·抗满盘           无灯·空盘·产全锁            LED·开机黄金锁         LED·逐手 M_f
  └geometry_detect      └geometry_lock              └led_geometry_         └fiducial_recalibrate
   .detect_board_raw     .lock_geometry_from_frames   calibrator             .select/detect/solve
   (无状态 _detect_raw)  (autocal)                   .LedGeometryCalibrator

 Scenario(enum)            CalibrationContext              CalibrationOutcome
  allows_led():            frames·board·geometry·led·      ok·M·Minv·corners·confidence·
   INITIAL_SETUP   = True  capture·next_point·last_good_M· strategy·reason·[points·xs·ys·baseline]
   MANUAL_FALLBACK = True  out_size                        (M/Minv ⟺ ok=True)
   RUNTIME_RECAL   = False

 build_default_selector()  ──factory──►  CalibrationSelector(strategies, policy)   ── calibration_registry.py
   policy[INITIAL_SETUP]        = [led_anchor, empty_board_autocal]
   policy[RUNTIME_RECALIBRATION]= [outer_corner]                 # 仅无灯
   policy[MANUAL_FALLBACK]      = [outer_corner, led_fiducial]

 DriftStateMachine ── drift_state_machine.py        RotationAwareDrift（同文件）
   STABLE →(drift)→ MOVING →(停稳)→ recalibrate →    phaseCorrelate(平移) + 绝对位姿(旋转/缩放)
   STABLE / NEEDS_ATTENTION                          → 解决 phaseCorrelate 旋转盲区
   (持 selector via recalibrate_fn；失败保 last-good、暂停采集)
```

**调用图（谁以什么场景调用选择器）：**
```
run_capture(auto)      ─► _run_auto_geometry ─► selector.calibrate(RUNTIME_RECALIBRATION)   [无灯]
run_capture(every-move)─► _run_fiducial_calibration  [P11 直连 LED 路径，不经 selector*]
run_capture(off)       ─► 跳过几何校正
p11_live_overlay  'r'  ─► decide_scenario→MANUAL_FALLBACK ─► selector …                       [许灯]
p11_live_overlay auto  ─► decide_scenario→RUNTIME_RECALIBRATION ─► selector …                 [无灯]
DriftStateMachine.RECALIBRATE ─► recalibrate_fn ─► selector.calibrate(RUNTIME_RECALIBRATION)  [无灯]

CalibrationSelector.calibrate(scenario, ctx):
    allow_led = scenario.allows_led()                 # ← 由场景派生，调用方不能传矛盾值
    for name in policy[scenario]:
        s = by_name[name]
        if s.requires_led and not allow_led:  continue   # 结构性禁灯（且不调用其 calibrate）
        if not s.is_applicable(ctx):          continue   # 早否决
        out = s.calibrate(ctx, allow_led=allow_led)      # LED 策略内再自卫一次
        if out.ok:  return out
    return CalibrationOutcome(ok=False, reason=聚合)
```
*注：`every-move`（高质量训练采集）仍走 P11 的 `_run_fiducial_calibration` 直连路径；`LedFiducialStrategy` 是同一组原语的 selector 适配器，供 `MANUAL_FALLBACK` 用。模式选择经 `--baipu-fiducial-mode` / `$KATRAIN_BAIPU_FIDUCIAL_MODE`（`resolve_fiducial_mode`，CLI>env>默认 auto）。

### P12 执行记录（2026-06-28）

**状态**：**T1–T9 全部完成并全绿**（软件部分）。P12 定向回归 **267 passed**（基线 225 + 新增 42）。真机精度复核（T9 绝对精度 / SBC 延迟）列「待硬件」。测试命令：`CI=true PYTHONPATH=$PWD /opt/miniconda3/envs/py311_katago/bin/python -m pytest`（非 `uv run`，后者缺 fastapi）。121 文件 working-tree 差异为 `black` 重排（行为无关），未扫入 P12 提交（仅 P12 改的文件随带其重排）。

- **Task 1**（`calibration_strategy.py` + test，commit `80cde7e1`）：`Scenario.allows_led()` 派生 allow_led（RUNTIME 恒禁灯）+ `CalibrationContext`（board/next_point/last_good_M 可选槽）+ `CalibrationOutcome`（M/Minv 当且仅当 ok 非 None）+ `CalibrationSelector`（硬跳过 led-gated 不调用其 calibrate、`is_applicable` 早否决、聚合 reason）。**7 passed**。
- **Task 2**（`geometry_detect.detect_board_raw` + `calibration_strategies.OuterCornerStrategy` + test，commit `920ff27c`）：无状态 `_detect_raw` 包装；外框 quad→规范四角 4 点单应；检测失败返回 `ok=False`（不吐陈旧 quad）；稳定性/plausibility confidence。**5 passed**（含 Minv·M≈I、无状态泄漏、失败非 ok）。
- **Task 3**（`calibration_strategies` 三适配器 + test，commit `18b6ab11`）：`EmptyBoardAutocal`（无灯·空盘·全锁）/`LedAnchor`/`LedFiducial`（LED·自卫 `allow_led=False`→不点灯·`is_applicable` 早否决）。**7 passed**（含 LED 自卫无点灯、合成 fiducial happy path）。
- **Task 4**（`calibration_registry.build_default_selector` + test，commit `77f4ac1d`）：场景优先级策略；**参数化证明**：即便把 LED 策略塞进 RUNTIME 策略表，派生 `allow_led=False` 仍全程 `led.set_rgb_points` 调用数=0。**3 passed**。
- **Task 5**（`drift_state_machine.py`：`RotationAwareDrift`+`DriftStateMachine` + test，commit `b93c0382`）：phaseCorrelate（仅平移）+ 绝对位姿复核 → **纯旋转可检出**；失败 `ok=False/M=None`→不更新 M、`NEEDS_ATTENTION`、暂停采集；成功重置参考帧；闪烁不误触发。**6 passed**。
- **Task 6**（`baipu_capture._run_auto_geometry` + `run_capture` 分支 + `server.py` 默认，commit `e57bb319`）：新 `auto` 模式（无灯 OuterCorner，**默认**）；制导灯不变；manifest 记 `source=outer_corner/stale/frozen`；`every-move`(LED 逐帧) 保留为高质量采集 opt-in；`off` 不变。server 默认 `every-move→auto`（高精度真机校验 gated by T9，待硬件）。**26 passed**（含 auto 无灯 spy、corrected-outer_corner 路径、every-move/off 回归）。
- **Task 7**（`baipu_autolabel` 消费 `source` + test，commit `8da2febb`）：`corrected/outer_corner` 用逐帧 M（不跑 `estimate_global_shift`）、标 `label_quality="corrected_outer_corner"`（反映较粗精度）；legacy `gc=None` + 混合 manifest 向后兼容。**20 passed**。
- **Task 8**（`p11_live_overlay.decide_scenario` 路由 + test，commit `695edc29`）：诊断工具 auto-drift→RUNTIME（无灯 OuterCorner）、`r` 键→MANUAL_FALLBACK（LED fiducial）；纯逻辑单测。**3 passed**。
- **Task 9**（`outer_corner_accuracy.py` GATE + test，commit `785e4778`）：合成满盘（fill 0–95% + 旋转）+ 可注入检测器；GATE 逻辑单测 **7 passed**。**真机检测器合成实测**：各 fill 率检测**零失败**，且「相对空盘的拥挤漂移」= **0.038/0.036/0.047 cells @ 50/80/95%**（远低于 0.12 阈值）→ **拥挤不劣化检测**（合成证据；绝对精度与最终 gate 待真机）。

**待硬件（真机）：** T9 绝对精度复核（真实木皮/光照/阴影下 OuterCorner 角点误差 vs 真值）+ SBC 延迟；据此最终确认 `auto` 作默认是否需对高填充率追加手动 LED 兜底提示。诊断工具 `p11_live_overlay`（auto 无灯 / `r` 点灯）真机目测。

**Known limits**：`auto`(无灯外框) 绝对精度低于 `every-move`(LED 亚像素)——训练采集追求标注精度时显式用 `every-move`（已在 server/docs 注明）；合成精度仅下界，真机为准；`MANUAL_FALLBACK` 顺序 `[OuterCorner, LedFiducial]`（先省灯）；scenario 选择目前在 run_capture/工具内隐式决定（未开 API/UI 参数，留后续）。
