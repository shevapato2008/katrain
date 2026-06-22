# PRD：Kiosk 摆谱 + LED 引导落子（为 YOLO 真实训练数据采集服务）

- **Track**: `sbc-baipu-led-guide`
- **目标分支**: `feature/rk3588-ui`（RK3588 kiosk 模式）
- **作者**: fan
- **日期**: 2026-06-14
- **状态**: 草案 (Draft)
- **范围**: kiosk「摆谱」模式 —— 按已知 SGF 逐手用 LED 引导人工摆子；**做到能正常摆谱即可**。
  附带定义「确认落子 → 截帧 → 写 YOLO 标签」的对接契约（实际的训练数据写出在 `autoresearch/board-detection` 侧完成，本模块只暴露事件/接口）。

---

## 1. 背景与动机

智能棋盘的棋子识别走「先经典 MVP 攒真实数据 → 训 YOLO → 导 RKNN」路线（见 `~/Repositories/autoresearch/board-detection/docs/SESSION_2026-06-14.md`）。
YOLO 必须用**本设备实拍**的真实棋盘数据训练（旧的合成数据 sim-to-real 已证实失败）。最高效的标注方式是 **SGF 当 ground truth**：

> 按一盘已知 SGF 逐手摆子，因为棋盘几何锁定（361 交叉点像素坐标已知）+ SGF 告诉每点该是黑/白/空 → **每帧自动得到完美标签**，无需分类器猜测。

**核心障碍**：棋盘无方向刻度，**旋转 90° 会有 4 种摆放歧义**，人工照 SGF 摆子极易摆错位置/方向，污染数据。
**解法**：用棋盘下方的 **361 颗 WS2812 LED**（硬件已跑通）点亮「下一手落子点」（红=黑、绿=白），人照灯摆子，**消除一切位置歧义**，并可顺带校验摆放正确性。

本模块产出一个 kiosk「摆谱」界面（参考元萝卜：左电子棋盘 / 右双棋手当前方高亮 / N/total 进度），驱动 LED 引导，并在每次确认后触发数据采集。

---

## 2. 整体流程（用户定义，已细化）

```
选谱(SGF) → 进入摆谱
  └─ 循环每一手 i：
       1. 点亮第 i 手落子点的 LED（红=黑 / 绿=白），电子棋盘高亮该点 + 当前方棋手卡高亮
       2. 人把对应颜色的棋子摆到亮灯处
       3. 人按「确认」键
       4. 采集帧（见 §4.5 的 LED-灭灯决策）→ 锁定几何 + SGF 真值 → 写出该帧 YOLO 标签
       5. 第 i 手 LED 熄灭，电子棋盘落子，进度 +1，点亮第 i+1 手 LED
  └─ 到谱尾：结束，汇总本盘采集了多少帧
```

---

## 3. 现状可复用资产（已核实，含文件路径）

### 3.1 UI（kiosk，React/Vite/TS，`npm run build:kiosk-2d`）
| 用途 | 文件 | 说明 |
|---|---|---|
| 路由/新增页 | `katrain/web/ui/src/kiosk/KioskApp.tsx` | 新增 `<Route>`；新页放 `src/kiosk/pages/` |
| 导航 Tab | `katrain/web/ui/src/kiosk/components/layout/navTabs.tsx` | `primaryTabs` 注册入口 |
| 逐手棋盘组件 | `katrain/web/ui/src/components/live/LiveBoard.tsx` | 已支持 `moves/stoneColors/currentMove`、当前手高亮、让子、提子；2D，kiosk 安全 |
| 棋手卡 | `katrain/web/ui/src/components/PlayerCard.tsx` | 名/段位/提子数 + `active` 高亮（边框+阴影），直接做"当前方高亮" |
| SGF→走子 | `katrain/web/ui/src/utils/sgfSerializer.ts` | `sgfToMoves()` → `{moves[], stoneColors[], metadata}`，逐手取 (row,col,color,moveNo) |
| 参考实现 | `katrain/web/ui/src/kiosk/pages/KifuPage.tsx` | 已有"逐手预览 + N/total 进度（line 348）+ 导航"，摆谱页以此为骨架 |
| 选谱来源 | `types/kifu.ts` + 现有 kifu 库（track `sbc-kifu-library-parity`） | 复用棋谱选择入口 |

### 3.2 相机 / 视觉（**已存在**，prod 集成层，track `sbc-visual-ver2`）
| 用途 | 文件 | 说明 |
|---|---|---|
| 相机采集 | `katrain/vision/camera.py` `CameraManager` | cv2.VideoCapture，USB 设备发现/重连，对焦预热，`.read_frame()` |
| 视觉服务 | `katrain/vision/service.py` `VisionService` | 绑定 session、`set_expected_board()`、`enter_setup_mode()`、`get_preview_jpeg()`、`get_confirmed_move()` |
| REST/WS | `katrain/web/api/v1/endpoints/vision.py` + `/ws/vision` | `/vision/status` `/vision/stream` `/vision/detected-board` `/vision/setup-mode` `/vision/pose-lock/confirm` |
| 网格标定 | `katrain/vision/grid_calibrator.py` | Hough 19×19 网格 → 精确交叉点（产线一次性） |
| 设置页 | `katrain/web/ui/src/kiosk/pages/VisionSetupPage.tsx` | 标定/锁定 UI |
| 推理后端 | `katrain/vision/inference/{onnx,rknn,ultralytics}_backend.py` | **含 RKNN** —— 训练好的 YOLO 最终插这里 |

> 摆谱采集**复用 `camera.py` / `VisionService` 抓帧**，不另写采集代码。`set_expected_board()` 可把 SGF 当前局面喂给视觉服务做"摆放正确性校验"。

### 3.3 会话 / SGF（后端）
- `katrain/core/sgf_parser.py`（`Move`/`SGFNode`、board_size、handicap）
- `katrain/web/session.py`（`WebSession`/`SessionManager`、broadcast）
- REST：`POST /api/session`、`POST /api/sgf/load`、`POST /api/redo`、`GET /api/state`

### 3.4 i18n
- 后端 `katrain/core/lang.py`（`i18n._('key')`，`.po/.mo` in `katrain/i18n/locales/{lang}/`），校验 `i18n.py`
- 前端 `katrain/web/ui/src/i18n.ts`（`i18n.t('key', default)`）

### 3.5 ⚠️ 当前**不存在**、必须新建
- **主机↔ESP32 的串口/LED 控制**：全仓 0 处 `serial/pyserial/esp32/ttyUSB/LED`。需从零建一个 LED 服务（§4.4）。

---

## 4. 需求详述

### 4.1 摆谱页 UI（R1）
- 路由 `/kiosk/baipu/:kifuId`（或从 kifu 库进入时携带 SGF）。布局参考元萝卜：
  - **左**：`LiveBoard`，渲染到第 i 手，高亮"下一手"待摆点。
  - **右**：两张 `PlayerCard`（黑/白），`active` 高亮当前行棋方；顶部 `N/total` 进度条（复用 KifuPage line 348 模式）。
  - **底部控件**：`确认`（核心）、`上一手`、`下一手/跳过`、`重新点灯`、`退出`。
- 触屏友好尺寸；不得 import `galaxy/**`、`Board3D/**`、`three`。

### 4.2 LED 引导（R2）
- 进入第 i 手：点亮该落子点 LED，**红=黑棋、绿=白棋**（与右侧当前方一致）。
- 同一时刻原则上只亮 1 颗（远低于 `MAX_ON=20` 限制）；可选把"刚摆好的上一手"用暗色微亮做已落子提示（计入 MAX_ON）。
- 颜色/亮度遵守固件 `MAX_BRIGHT=40` 上限。

### 4.3 摆放状态机（R3）
状态：`IDLE → GUIDING(i) → PLACED_WAIT_CONFIRM → CAPTURING → ADVANCE → GUIDING(i+1) → … → DONE`
- `确认` 触发 `CAPTURING`；采集完成才 `ADVANCE`。
- `上一手`：回退 i，重新点灯（用于摆错重来）。
- 异常：采集失败 / 校验摆错 → 停在当前手并提示，不前进。

### 4.4 LED 控制契约（R4）—— 本模块最核心的新建部分

**架构**：在后端起一个 **LED 串口服务**（Python，pyserial），随 `_lifespan_board()` 启动管理（与 vision worker 同模式），对前端暴露 REST/WS。前端摆谱页只调 REST，不直接碰串口。

**主机↔ESP32 串口协议**（USB-serial @115200，行式 ASCII，幂等、可读、易调试）：
| 命令 | 含义 | 回复 |
|---|---|---|
| `SET <row> <col> <r> <g> <b>` | 暂存 (row,col)∈[0,18]² 的颜色到帧缓冲 | `OK`/`ERR` |
| `SHOW` | 渲染帧缓冲（`FastLED.show()`） | `OK` |
| `CLEAR` | 全灭 | `OK` |
| `BRIGHT <v>` | 全局亮度，钳到 `MAX_BRIGHT=40` | `OK` |
| `SCAN [ms]` | 逐颗扫描（bring-up/标定用） | 逐行 `IDX <i> ROW <r> COL <c>` |
| `STATUS` | 版本/亮灯数/亮度 | 文本 |
- 固件侧维护 `MAX_ON` 计数防过流；摆谱只亮 1–2 颗,天然安全。
- REST 封装：`POST /api/led/point {row,col,color}`、`POST /api/led/clear`、`POST /api/led/calibrate/scan`。

**(row,col) ↔ 灯链索引映射 —— 见 §6（必须实测标定，不能只靠公式）。**

### 4.5 数据采集对接（R5）—— 与 autoresearch 的契约
- `确认` 后的采集时序（**推荐：灭灯拍**，见下决策）：
  1. （推荐方案）`CLEAR` 关掉下一手 LED → 等 ~150ms 稳定 + 确认手已离开画面 → 抓帧。
  2. 用 `CameraManager`/`VisionService.get_preview_jpeg()` 抓一帧原图。
  3. 该帧的 ground-truth 局面 = SGF 第 i 手后的盘面（仅黑/白/空）；结合**锁定几何**（autoresearch `session.npz` 的 361 交叉点像素坐标 + warp）→ 为每个有子点写一个 YOLO box（类别 black/white、框心=交叉点、框边=k×格距）。
  4. 写出 `image_{game}_{move:03d}.jpg` + 同名 `.txt`（YOLO 格式）。
- **本模块只负责**：暴露"第 i 手已确认、可采集"的事件 + 当前 SGF 局面 + 抓帧接口。**标签写出在 autoresearch 侧**（它持有锁定几何与训练集格式）。两侧通过一个采集事件（REST/WS 或共享触发）对接。

> **关键决策（LED 在不在照片里）**：
> - **方案 A（推荐）：灭灯拍** —— 拍照瞬间所有 LED 灭。优点:标签最干净(只 2 类 black/white)、与产品「记谱」模式(无 LED)分布一致、状态机简单。
> - 方案 B（用户初版思路）：下一手 LED 亮着拍 —— 则必须**多加 led_red/led_green 两类标签**(发光点位置=SGF 下一手、颜色已知,可从 SGF 推出)，让模型学会"发光点≠棋子"。仅当产品在读盘时也常亮 LED 才需要。
> - 建议先按 A 跑；若后续要 LED 鲁棒性,再补一遍 B 的带灯数据做增强。**此项请拍板**（见 §8）。

### 4.6 摆放正确性校验（R6，可选增强）
- 既然有 vision 服务：确认时可让 `VisionService` 检测当前盘面与 SGF 期望盘面比对；若"新子不在第 i 手期望点"→ 提示"摆错位置"，不前进。这把 LED 引导 + 视觉校验闭环，进一步保证数据零污染。
- 经典差分检测器（autoresearch `stones.py`）也可作此校验的轻量替代。

---

## 5. 验收标准（本模块"能正常摆谱"为准）
1. 从棋谱库选一盘 SGF 进入摆谱页，左棋盘逐手渲染、右双棋手当前方高亮、`N/total` 正确。
2. 每进入一手，正确落子点 LED 按 黑红/白绿 点亮；`上一手/下一手` 切换时 LED 同步更新。
3. 按 `确认` 后：LED 状态正确切换到下一手，进度 +1；到谱尾正确结束。
4. **LED 点位准确**：经 §6 标定后，任意手点亮的物理 LED 与电子棋盘高亮点、SGF 落子点三者一致（全 361 点抽测无错位）。
5. 串口服务断连/重连健壮（拔插 USB 不崩）。
6. 采集对接：每次确认产生一个"可采集"事件 + 可取到当前 SGF 局面与一帧图（标签写出由 autoresearch 验收）。
7. 双构建均绿：`npm run build` 与 `npm run build:kiosk-2d`（`verify:kiosk-2d`，无 three/@react-three）。

---

## 6. 附：LED (row,col)↔索引 映射、标定与固件改动

> **配套参考代码见同目录 [`led-calibration-and-protocol.md`](./led-calibration-and-protocol.md)**，内含可直接拿走的两段骨架：
> (A) **ESP32-S3 固件串口协议骨架**（行式 ASCII：`SETI/SHOW/CLEAR/BRIGHT/SCAN/STATUS` + 帧缓冲 + `MAX_ON`/`MAX_BRIGHT` 保护）；
> (B) **主机侧相机自动标定脚本** `led_calibrate.py`（锁定几何后逐颗点灯→相机定位交叉点→生成权威 `led_lut.json`，并自检坏灯/接错）。
> 设计取向：**主机持权威 LUT、固件只认原始链索引 `SETI`**，重布线只需重跑标定刷新 JSON。

### 6.1 已知（来自 PCB 脚本与固件）
- 4 子板：UL`P_10x10`、UR`P_10x9`、LL`P_9x10`、LR`P_9x9`，共 361。几何：列距 22mm、行距 23.7mm。
- 子板内**蛇形**（`generate_pcb_placement_v3.py`）：偶数行 L→R `idx=row*cols+col+1`(rot 0°)；奇数行 R→L `idx=(row+1)*cols-col`(rot 180°)。
- **⚠️ 链序冲突(必须实测裁决)**：
  - 固件注释(`main.cpp` L4)：`UL → UR → LL → LR`。
  - PCB 脚本 `SUBBOARDS` 的 J_OUT 串接：`UL(J_OUT BL) → LL(J_OUT BR) → LR(J_OUT TR) → UR(末端)`，即 `UL → LL → LR → UR`。
  - 且各子板 `j_in_corner` 不同(TL/TL/BL/BR)，拼装物理旋转无法只从脚本确定。
- → **不能只靠公式推 LUT**，否则会整片错位。

### 6.2 权威标定法（必做，二选一或都做）
**(a) 相机自动标定（推荐，锁定几何后）**：
```
确保棋盘几何已锁定(session.npz 有 361 交叉点像素坐标)
for i in 0..360:
    串口 SCAN 或 SET 让"链索引 i"单独点亮一个已知颜色 → SHOW
    抓帧 → 在交叉点邻域找最亮/该色 blob → 取最近交叉点 (row,col)
    LUT_idx2rc[i] = (row,col)
反转得 LUT_rc2idx[(row,col)] = i        # 摆谱用这个
自检：必须命中恰好 361 个互异交叉点；缺失/重复 → 报接线/坏灯
```
30 秒生成权威 361 项 LUT，对链序冲突、蛇形方向、子板旋转**全免疫**,并顺带做坏灯/接错检测。
**(b) 人工目视标定**：改 bring-up 固件逐颗点亮并串口打印 `idx`，人记录每个 idx 的物理 (row,col)。无相机时的兜底。

### 6.3 固件改动（`smartbox-hardware-design/.../led_bring_up_pio`）
- 加上 §4.4 串口命令解析(行式)。
- 内置 `LUT_rc2idx`(标定产出，可硬编码或上电从主机下发并存 NVS)。
- 保留 `SCAN` 给标定/自检。
- 维持 `MAX_ON`/`MAX_BRIGHT` 保护。

---

## 7. 影响面与风险
- **LED 链序冲突(高)**：见 §6.1，未实测标定前禁止信任公式；标定 LUT 为唯一权威。
- **新建串口服务**：仓内无先例，按 vision worker 模式放 `_lifespan_board()`；USB 设备号变更/重连参考 `camera.py` 的 sysfs 方案。
- **与现有 vision 管线(`sbc-visual-ver2`)的关系(需对齐)**：prod 已有 `katrain/vision/`(board_finder/grid_calibrator/onnx+rknn 后端 + setup/pose-lock)。本采集应**复用其相机与几何锁定**,而训练产出的 YOLO 最终插其 `rknn_backend`。autoresearch 的经典实验轨与之有重叠,整体路线需在主 session 理顺(本 PRD 不决断)。
- **采集与 LED 灭灯时序**：拍照须在手离开 + 画面稳定后；灭灯拍(方案 A)避免 LED 污染标签。
- **构建边界**：新前端文件仅 import 共享区 + `src/kiosk/`。

## 8. 待确认问题
1. **LED 灭灯拍 vs 带灯拍**(§4.5)：默认采纳 A(灭灯拍、2 类标签)?
2. **「确认」是物理按键还是触屏按钮**?(物理键更顺手,需 GPIO/串口上报;触屏最简单)
3. **串口 LED 服务归属**：独立 Python 进程 vs 并入 vision worker 子进程?
4. **采集事件通道**：摆谱(rk3588-ui)与标签写出(autoresearch)如何对接——REST 回调 / 共享目录 / 直接在 rk3588-ui 内写标签?
5. **与 `sbc-visual-ver2` vision 管线合并**:几何锁定用哪套(autoresearch `calibrate_ui` vs prod `grid_calibrator`)?

## 9. 实施阶段（本模块；做到能正常摆谱即止）
- **P1 摆谱 UI**：路由 + 摆谱页(LiveBoard + 双 PlayerCard 高亮 + N/total) + 选谱进入 + 上一手/下一手/确认 状态机(先不接 LED,用屏幕高亮跑通逻辑)。
- **P2 LED 服务 + 协议**：串口服务 + REST + 固件命令解析。
- **P3 LED 标定**：§6.2 相机自动标定生成 LUT,全 361 点抽测一致。
- **P4 采集对接**：确认→可采集事件 + 抓帧接口(标签写出对接 autoresearch)。

## 10. 关键文件清单
- 前端(新增,kiosk)：`src/kiosk/pages/BaipuPage.tsx`、`KioskApp.tsx`(路由)、`navTabs.tsx`(入口)。
- 前端(复用)：`components/live/LiveBoard.tsx`、`components/PlayerCard.tsx`、`utils/sgfSerializer.ts`、`kiosk/pages/KifuPage.tsx`(参考)。
- 后端(新增)：`katrain/web/.../led_service.py`(串口) + `katrain/web/api/v1/endpoints/led.py`(REST);`server.py` `_lifespan_board()` 注册。
- 后端(复用)：`katrain/vision/camera.py`、`katrain/vision/service.py`、`katrain/web/api/v1/endpoints/vision.py`、`katrain/core/sgf_parser.py`。
- 固件：`smartbox-hardware-design/debug/led_bring_up_pio/src/main.cpp`(加串口协议 + LUT)。
- 标定/采集脚本：`autoresearch/board-detection/`(锁定几何 + YOLO 标签写出)。
</content>
</invoke>
