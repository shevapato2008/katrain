# Kiosk 物理棋盘对弈（一期）验收清单（PRD §7）

> **状态说明**：Tasks 1–14 已由 subagent-driven 流程实现 + 逐任务评审通过（见 `.superpowers/sdd/progress.md`）。
> 下方 **软件回归门** 已在开发机（Mac，无 SBC 硬件）通过；**实机验收（1–14 项）** 需在 SBC + 摄像头 + LED 棋盘 + 实体棋子在场时由人工执行并记录。

## 软件回归门（每次实机前必跑；开发机已验证）

| 项 | 命令 | 结果 |
|---|---|---|
| 后端全量回归 | `CI=true uv run pytest tests` | ✅ 无新增失败：修复 Task 9 引入的 1 处快照回归（`test_vision_api` 补 `led_connected`，commit 8d349853）后回到基线 **53 failed + 10 errors**（均为预存 engine/GPU/env 依赖用例，非本轨道引入） |
| 本轨道用例 | `pytest tests/test_vision/ tests/test_vision_api.py tests/test_vision_bind_state.py tests/test_physical_play.py tests/test_physical_play_orchestrator.py tests/test_hint_api.py tests/web_ui/test_ranked_rules.py` | ✅ 296 passed |
| 前端全量单测 | `cd katrain/web/ui && npx vitest run` | ✅ 420 passed（61 files） |
| 双构建 + 边界门 | `npm run build && npm run build:kiosk-2d`（含 `verify:kiosk-2d`） | ✅ 两个构建绿；kiosk 边界 grep 门 exit 0（无 three.js/`/galaxy/`/非 board live API） |

**基线来源**：develop@96e64f53，Task 1 执行时实测 53 failed + 10 errors（PRD 草稿写的 37 已过时）。

## 实机启动参数（SBC）

```bash
python -m katrain --ui web --port 8001 \
  --vision-model <model.onnx|.rknn> \
  --led-serial-port /dev/ttyACM0 \
  --hint-engine local --hint-top-n 3
```

## 实机验收项（人工执行，逐项记 PASS/FAIL + 现象）

> 记录格式：在「结果」列填 `PASS` / `FAIL`，「现象/备注」列记观察到的具体行为或异常。

| # | 验收项 | 关键判据 | 结果 | 现象/备注 |
|---|---|---|---|---|
| 1 | **纯物理闭环** | 整盘只在物理盘摆子；每手 AI 灯色正确（黑→红/白→绿）、摆子后 ≤2 tick 熄灯；提子蓝灯与落子灯同批、拿除后灭；终局清灯；退出后 `led/status` 无残灯 | | |
| 2 | **让子局** | AiSetupPage 设 4 子 → 开局 4 红灯全亮 → 逐个摆黑子灯逐灭 → AI(白) 正常行棋 | | |
| 3 | **四类异常** | ①AI 摆错点→灯不灭+mismatch 对话框列错点→纠正后消退；②多摆一子→~3s 蓝灯+「请拿走」→拿走恢复；③手遮挡 10s→board_lost 遮罩→移开消退；④挪动棋盘→PoseLostBanner→点「重新定位」恢复。**全程 LED 无一次为几何自动闪灯（D2③）** | | |
| 4 | **AI 支招** | 自由局点按钮→白灯 3 点闪+面板胜率/目差；显示期间摆子→不注入；关闭后摆→正常注入；`--hint-engine off` 重启→按钮报「支招功能未开放」 | | |
| 5 | **升降级** | 支招按钮不可见 + `curl POST /api/v1/hint` → 403；悔棋按钮不可见 + `/api/undo` → 403；落子后「确认中」chip 出现 | | |
| 6 | **悔棋恢复**（自由局） | 悔 2 手→蓝灯指示待拿除 2 子+CaptureGuide→拿除→续弈 3 手无错乱 | | |
| 7 | **健壮性** | 中途拔 LED USB→对局继续、徽标红、无日志刷屏；重插→徽标绿、下次状态变化灯恢复。拔摄像头→相机徽标红+恢复后识别回归。长考 >5min→灯灭（失效保护）→下手 AI 灯重亮 | | |
| 8 | **NPU（R2 风险项）** | `--vision-model *.rknn` 跑第 1 项闭环；记录单帧推理耗时 + 3 帧确认端到端延迟（目标 <1s；CPU 对照 ~2s） | | |
| 9 | **拥挤盘面重标定（R3 风险项）** | 中盘 150+ 子挪动棋盘→验证 auto-unlock→重新定位成功率与精度；数据决定二期前是否需 P12 补强 | | |
| 10 | **摆谱回归** | 进摆谱页走一遍 LED 引导（下一手灯/提子闪/离开清灯）确认行为不变 | | |
| 11 | **灯态重申（评审 A）** | AI 落子灯亮后长考 >5min 不摆——失效保护熄灯后 ≤240s（`led_reassert_interval_s`）自动回亮，无需新状态；`curl POST /api/v1/led/clear` 手动清灯后同样自动恢复 | | |
| 12 | **抢跑回归（Codex B1）** | AI 灯亮(未摆)→用户先下自己一手→该手**不注入**、其位**无蓝灯**；摆上 AI 子后 ≤3s 用户那手自动确认注入，棋谱顺序正确、无重复/非法着手日志 | | |
| 13 | **逃生舱** | 持续失同步→30s toast→120s 对话框；「已按指示恢复」摆好后续弈正常；再制造→「改用屏幕落子」→LED 清灯、屏幕点击落子续弈到终局 | | |
| 14 | **活子被拿走（Codex B2）** | 偷偷拿走一颗双方均未提的活子→走 mismatch 对话框（missing 列该子）+红/绿灯补回，**不得** CaptureGuide 秒开秒关 | | |

## 实机验收前必读的已知限制 / 潜在硬件缺陷

- **⚠️ SET_GEOMETRY 子进程缺失（预存缺陷，Task 7 发现，非本轨道引入）**：`katrain/vision/worker.py`（SBC 子进程分发器 `_process_commands`）**没有** `SET_GEOMETRY` 处理分支（`worker_inprocess.py` 有）——`grep -c SET_GEOMETRY` = 0/1。若第 3 项④或第 9 项的重标定链路依赖 `VisionService.set_geometry()` 推送到子进程 worker，将在真机上**静默失效**。（注：`POST /api/v1/geometry/calibrate` 走的是 `GeometryCalibrationService`，落盘 `geometry_lock.npz`，未必经 `set_geometry` 命令——需实机确认新几何是否被子进程 worker 实际采用。）**这是实机验收第 3④/第 9 项的头号排查点**；若失效，需给 `worker.py:_process_commands` 补 `SET_GEOMETRY` 分支（与 `worker_inprocess.py` 对称）。
- **Q4 暂停窗口一帧竞态**：AI 数字落子到 PAUSE 命令生效之间（~1 worker 帧），抢跑的一手可能已被确认注入；此时它是合法用户着手，仅温和违反「先摆 AI 子」政策，无棋局损坏（弃用 hold 方案后的残余最坏情形）。第 12 项观察。
- 抢跑的子在等待期会被 sync 判为 unexpected，5 帧后弹 mismatch 对话框（missing 列出 AI 子）——对话框文案兼作「请先摆 AI 子」引导；逃生舱 120s 兜底。
- ambiguous「忽略」后该子已进 MoveDetector 基线，靠 resetSync/恢复流兜底。
- 「改用屏幕落子」后本局不再自动回到物理模式（重进对局页才重新 bind），一期接受。
- ranked 反作弊：`/api/undo` 已 403；但 `/api/nav`（ScoreGraph 点击导航）**未**禁用——一期范围外，若实机发现可经 nav 回退等效悔棋，记入二期跟进（见 `.superpowers/sdd/progress.md` Task 13 备注）。

## 记录 / 提交

实机执行后回填上表并提交：
```bash
git add superpowers/tracks/kiosk-physical-play/acceptance-checklist.md
git commit -m "docs(kiosk-physical-play): acceptance run record (PRD §7)"
```
