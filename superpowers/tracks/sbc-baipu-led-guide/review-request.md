# 评审需求：Kiosk 摆谱 + LED 引导落子（`sbc-baipu-led-guide`）

> 交给外部评审者（Codex / Gemini）。你们在本仓库内以**只读**方式运行，可直接读文件。
> 目标分支：`feature/rk3588-ui`。评审对象：本目录下的 `plan.md`（实施计划 v2）。

---

## 0. 你的任务（一句话）

**独立评审 `plan.md` 这份实施计划**：找出其中的**正确性 bug、架构风险、遗漏、以及更优方案**。
**鼓励挑战我们的既定决策**——如果你认为某个决策是错的或有更简单的做法，请直说并给理由。

我们**不需要**你复述已知问题（见 §3「已做工作」）。我们要的是**新视角 / 我们漏掉的 / 你不同意的**。

---

## 1. 背景（30 秒）

- **KaTrain**：围棋 AI 教学软件，集成 KataGo。有桌面(Kivy)与 Web(FastAPI+React) 双 UI；本工作只在 **Web/kiosk** 侧。
- **智能棋盘**项目：棋盘下方有 **361 颗 WS2812 LED**（19×19），由 ESP32-S3 经 USB 串口驱动；上方有 USB 相机。
- **本 track 要做什么**：一个 kiosk「**摆谱**」模式——按已知 SGF **逐手用 LED 点亮下一手落子点**引导人工摆子，**每步带灯拍照**，照片落到 katrain 文件夹；把「照片 + manifest + SGF」交给另一个仓 `autoresearch` 训练 YOLO 棋子识别（**SGF = ground-truth 标签**，因为旧的合成数据 sim-to-real 失败，必须用本设备实拍真数据）。
- **为什么要 LED 引导**：棋盘无方向刻度，旋转 90° 有 4 种摆放歧义，人工照 SGF 摆极易摆错污染数据；LED 点亮唯一落子点可消除歧义。
- **跨 3 个仓库**（本 track 只建 katrain 侧）：
  - `katrain-rk3588-ui`（本仓）：摆谱 UI + 串口 LED 服务 + 拍照。
  - `smartbox-hardware-design`：ESP32-S3 固件（**协议固件已烧好并实测通过**）。
  - `autoresearch/board-detection`（`~/Repositories/autoresearch/board-detection`）：几何标定 + YOLO 标签写出 + 训练。

---

## 2. 必读材料（按顺序）

| # | 文件 | 作用 |
|---|---|---|
| 1 | `superpowers/tracks/sbc-baipu-led-guide/plan.md` | **评审主对象**：4 阶段实施计划 + 决策表 + 附录 A(LED LUT 公式) + §10 修订记录 |
| 2 | `superpowers/tracks/sbc-baipu-led-guide/prd.md` | 原始需求/动机/验收 |
| 3 | `superpowers/tracks/sbc-baipu-led-guide/led-calibration-and-protocol.md` | LED 串口协议 + 标定方法（含固件骨架与相机标定脚本参考） |
| 4 | `CLAUDE.md` 的「SBC 构建边界契约」节 | **硬约束**：kiosk 构建不得 import `three`/`@react-three`/`galaxy`/`Board3D` |

**关键代码（计划会改/复用，建议抽查）**：
- 前端复用：`katrain/web/ui/src/components/live/LiveBoard.tsx`、`components/PlayerCard.tsx`、`utils/sgfSerializer.ts`、`kiosk/pages/KifuPage.tsx`(骨架参考)、`kiosk/KioskApp.tsx`、`kiosk/components/layout/navTabs.tsx`
- 后端模式：`katrain/web/server.py`（`_lifespan_board` ~L214-335 + `lifespan` 关停 ~L30-55）、`katrain/web/api/v1/endpoints/vision.py`、`katrain/web/api/v1/api.py`、`katrain/vision/camera.py`、`katrain/vision/service.py`、`katrain/vision/grid_calibrator.py`(待退役)
- 提子逻辑现状：`katrain/core/game.py`(后端真值) + `LiveBoard.tsx` 内 `removeCaptures`(前端，被 3 处重复)
- 几何迁移来源：`~/Repositories/autoresearch/board-detection/autocal.py`、`detect.py`、`calibrate.py`、`stones.py`、`data/session.npz`、`docs/METHOD_autocal_2026-06-15.md`

---

## 3. 已做的工作（**别重复这些**）

1. **需求已澄清**（brainstorming）：采集用带灯拍(方案 B)、确认用触屏、提子需检测提示、相机接 Mac、只建 katrain 侧。
2. **硬件已实测打通**：协议固件已烧；Mac→串口→单颗 LED 控制 OK；**(row,col)→链索引映射已用纯公式锁定并实测验证**（横/竖线扫描整齐 + idx0=(0,0)顶左 + 9 星位精准命中）。→ **LED 不需要相机标定**。公式见 `plan.md` 附录 A。
3. **7 路并行代码研究** + **67-agent 多镜头对抗式内部评审**（71 findings：31 real + 24 partial）已并入计划 v2，见 `plan.md` §10 修订记录。已发现并修的包括：坐标系反转、状态机 off-by-one、服务关停缺失、manifest 未定义、session.npz 字段兼容、相机互斥、LedService 并发、测试覆盖等。

> 所以：**重点找 §10 之外的问题**，或对 §10 修订/§ 决策表提出更优方案。

---

## 4. 我们的关键决策（**请逐条审视、可挑战**）

摘自 `plan.md` 决策表，附我们的理由——请判断每条是否成立、有无更优解：

1. **坐标系**：全链路统一「规范坐标 `(row,col)`，row=0 顶部、col=0 左」(= LED LUT 约定)。`goBoard` 输出规范坐标，**LED 直接用、不反转**；仅在喂 LiveBoard 渲染时于边界转换。
   - *挑战点*：这是不是最不易错的方案？把转换收口到 LiveBoard 边界 vs 别处，哪个更稳？
2. **提子在前端共享 util** `goBoard.ts` 算（非后端），并借机收敛 3 处重复实现。
   - *挑战点*：前端重算 vs 后端单一真值（`game.py`），数据正确性与可维护性权衡是否选对？
3. **拍照走独立 `CaptureService`**（包 `CameraManager`），与 YOLO `VisionService` **运行时互斥**。
   - *挑战点*：两个相机 owner 的设计是否有更干净的方案？
4. **带灯拍时序**：确认后拍；照片 = 已落子 0..k + 下一手 k+1 的灯；manifest 每张带 `{stones_through_move, next_move}`。
   - *挑战点*：这个时序能否真正稳定产出干净的 4 类标签？边界(首帧/末帧/pass/让子)处理对不对？手是否可能入镜？
5. **采集限 19×19**；**pass** 不点灯不拍；**让子(AB/AW)** 当前导手同色引导。
6. **Ko/非法手不校验**——摆谱重放已知合法 SGF，`reconstructBoard` 镜像 SGF。
   - *挑战点*：人若照灯摆错（摆到非点亮处）目前无校验兜底，这对数据纯净度是否够？需不需要轻量视觉校验？
7. **几何识别**：迁移 autoresearch `autocal` 进 katrain，退役 `grid_calibrator.py`；`session.npz` **只存 8 字段**保兼容。
   - *挑战点*：跨仓代码迁移(改 import / 去硬编码 /tmp 与 HERE/SESSION / out_size 一致性)的风险点是否盖全？
8. **选谱入口**复用 kifu 库列表（仅 19×19），不新建后端 baipu 表。

---

## 5. 重点评审问题（请针对性回答）

**A. 架构 / 分阶段**
- P1→P2→P3→P4 的拆分、依赖、解耦是否合理？有无隐藏的跨阶段依赖或顺序陷阱？
- 后端服务生命周期（`_lifespan_board` 启动 + `lifespan` 关停 + gate）是否健全？

**B. 带灯拍数据正确性（最重要）**
- §2.3 状态机 + §4.2 采集时序，能否**逐帧产出与 SGF 一致、标签干净**的照片？把每种边界(首/末/pass/让子/连环提子)走一遍，找漏洞。
- manifest schema（`plan.md` §4.2）是否足够 autoresearch 无歧义地产 4 类标签？坐标约定会不会和 autoresearch 几何对不齐？

**C. 坐标系正确性**
- 「规范坐标 row 顶部基」贯穿 goBoard→LED→manifest 是否自洽？LiveBoard 边界转换是否会出错？有没有更简方案？

**D. 后端并发 / 健壮性**
- `LedService` 线程模型（后台线程 + 有界队列 + `threading.Lock` + 串口重连）是否有竞态/死锁/丢命令风险？
- `CaptureService` 与 `VisionService` 相机互斥的运行时检查是否充分？

**E. 几何迁移（P4）**
- autocal 移植到 katrain 的可行性与坑（依赖、import、路径、`session.npz` round-trip 兼容）。

**F. 测试充分性**
- 各阶段把测试列为验收阻断项（`test_led_service`/`test_capture_service`/`test_baipu_api`/`test_geometry_lock`/`baipu.spec.ts`/`goBoard` 单测）。覆盖是否够？有无关键路径漏测？硬件在环部分如何最小化人工？

**G. 全局 / 产品视角（可选，欢迎大胆）**
- 有没有**整体上更省事、更快拿到高质量训练数据**的思路（哪怕推翻部分方案）？

---

## 6. 硬约束（不可违反，评审时请据此判断）

- **范围**：只建 katrain 侧；固件在 `smartbox-hardware-design`（已烧好，勿假设要改）；YOLO 标签/训练在 `autoresearch`。
- **前端构建边界**（CLAUDE.md）：kiosk 页只能 import 共享区 + `src/kiosk/`，**不得** import `three`/`@react-three/*`/`galaxy/**`/`components/Board3D/**`/`VideoRecorderPage`；改共享文件须 `npm run build` 与 `npm run build:kiosk-2d`(含 `verify:kiosk-2d`) 双绿。
- **LED 安全**：固件 `MAX_ON=20`、`MAX_BRIGHT=40`；主机持 LUT、固件只认链索引 `SETI`。
- **平台**：开发与采集在 macOS；相机 `cv2.VideoCapture`；串口 `/dev/cu.usbmodem2101 @115200`。

---

## 7. 期望的评审输出格式

请按下面结构给反馈，便于我们处理：

```
## 总评 (go / go-with-changes / no-go) + 一句话理由

## Top 3 必改（最高优先）
1. [严重度] 问题 — 证据(文件/plan 章节) — 建议

## 详细发现
- [Critical/High/Medium/Low] 标题
  - 类型：correctness bug / 架构风险 / 遗漏 / 决策异议 / 更优方案
  - 证据：plan.md 章节 或 代码文件:行
  - 建议：具体可执行的修法

## 对我们关键决策(§4)的判断
- 决策 1..8：同意 / 异议(+理由+替代方案)

## 你认为我们漏掉的（§3/§10 之外的新问题）
```

**评审准则**：宁可少而准——只报你**对照计划/代码核实过**的问题；对不确定的，标注「需进一步确认」。优先级以「是否阻断正确实现」为准。

---

*附：本计划已经过一轮 67-agent 内部对抗评审（见 `plan.md` §10）。期待你们带来不同的、互补的视角。*
