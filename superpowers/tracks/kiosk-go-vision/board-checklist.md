# 视觉/标定 上板验收清单(kiosk-go-vision)

> 来源:PRD §3 V5、§7「上板清单」。把散在 `kiosk-physical-play` / `kiosk-golaxy-physical-play` /
> `sbc-baipu-led-guide` 三份旧文档里**仍然成立**的真机项收成一份,过期的删掉并写明原因(见下)。
> 本清单本身**不执行**——执行需要 RK3562 + 摄像头 + 灯带 + 实体棋子,人在场,由 Fan 安排时机
> (PRD §3 V5「不做」)。
>
> **前置总述**:RK3562 只有 2G 内存,**这台机器上只跑这一家服务**,下列各项按顺序**串行**执行,
> 不并发起两个 katrain/KataGo 进程(`superpowers/tracks/kiosk-go-vision/prd.md:154`)。第 4 项本轮
> 不做,留位。每项测完把结果**写回本文件**(照抄下面「记录」栏的字段),不要只在对话里口头报告
> (`superpowers/tracks/kiosk-go-vision/prd.md:273`)。

## 已从旧清单中删除的过期项

- **「挪动棋盘 → 横幅『重新定位』」**(原 `superpowers/tracks/kiosk-physical-play/acceptance-checklist.md`
  第 3④ 项)—— `PoseLostBanner` 先被 `RecalibrationModal` 取代
  (`katrain/web/ui/src/kiosk/components/game/RecalibrationModal.tsx:14-15` 的注释自述
  "Promoted from the old PoseLostBanner top Alert to a Dialog"),本赛道 Z3 又把 `PoseLostBanner`
  组件本身删掉了(PRD §3 Z3;`katrain/web/ui/src/kiosk/components/physical/PoseLostBanner.tsx`
  **已不存在**——`git log --follow` 上最后一条是 `b4da1b12`「删掉零消费者的 PoseLostBanner」)。
  下面第 3 项「人工出口」按 `RecalibrationModal` + V1 新增的「对齐外框」重写。
- **「`SET_GEOMETRY` 子进程缺失」**(原 `acceptance-checklist.md` 「实机验收前必读的已知限制」段)——
  过期,不成立:盒上走的是 `InProcessAdapter`,不是子进程 `VisionWorkerProcess`(`worker.py`)。
  `katrain/web/server.py:744-757` 里 `VisionService(vision_config, frame_source=camera_hub)`
  总是带着 `frame_source`;`katrain/vision/service.py:42-45` 的判断
  `if self._config.process_mode == "inprocess" or self._frame_source is not None:` 只要
  `frame_source` 非空就选中 `InProcessAdapter`,`server.py:4329` 的 `process_mode="worker"` 在盒上
  从未真正生效。`InProcessAdapter`(`worker_inprocess.py`)本身有 `SET_GEOMETRY` 分支
  (`:1161-1162`),这条旧发现不适用。

---

## 1. 满盘外框精度(V1 自动重定位的闸)

- **前置**:RK3562 + 摄像头 + 实体盘;**这台机器上只跑这一家服务**(2G 内存)。
  先在**空盘**上跑一次 LED 13 点标定并成功 —— 这次的角点就是真值;**之后盘和相机都不许再动**。
- **操作**(量具是 Task 8b 加的真帧模式,`--live` 与 `live_gate` 已落地,见
  `katrain/vision/tools/outer_corner_accuracy.py` 的 `__main__` 块,`:176-212`):
  1. 空盘先跑一次(对照):`uv run python -m katrain.vision.tools.outer_corner_accuracy --live http://127.0.0.1:8081`
     (真值取 `/api/v1/geometry/layout`,帧取 `/api/v1/geometry/stream` —— 两个路由在
     `katrain/web/api/v1/endpoints/geometry.py:187` 和 `:169`;工具侧取图见 `outer_corner_accuracy.py:196`
     和 `:202`)。
  2. 轻手摆到约 60 子(别碰盘),再跑一次;有余力摆到约 150 子跑第三次。
  **不带 `--live` 跑出来的是合成图**,只是下界(默认阈值 0.12 见
  `katrain/vision/tools/outer_corner_accuracy.py:5`),不能当这道闸。
- **判据**:每一次都 `GATE(<0.12 cells, >=80% frames detected) = True`(打印在
  `outer_corner_accuracy.py:212`,判的是 `live_gate()` 的返回值,`:123-130`;`live_gate` 逐帧算的是
  `grid_error_cells`——19×19 网格最大误差,不是角点中位误差,`:107-120`,由 `measure_real` 调用,
  `:133-146`)。
  空盘那次就已 ≥ 0.12 ⇒ 外框法与 LED 法本身有系统偏差,同样算不过。
  摆子时碰了盘 ⇒ 这组作废,回空盘重标重测。`detected k/n` 照实记;低于八成 `live_gate` 就判不过 ——
  十帧只认出一两帧时「那一两帧合格」样本太少,算不了证据(Codex 第 2 轮)。
- **记录**:每次的 `detected` 与 `max` 写回本文件这一节 + 在 PR 里贴一行。**过了才允许把
  `AUTO_RELOCATE_ON_DRIFT` 翻成 `True`,并且要和结果同一次提交。**

| 轮次 | detected k/n | max(cells) | 结果 |
|---|---|---|---|
| 空盘(真值) | | | |
| ~60 子 | | | |
| ~150 子(选测) | | | |

## 2. 碰盘恢复(V1 自动重定位·串位判据)

- **前置**:第 1 项已过闸,`AUTO_RELOCATE_ON_DRIFT = True`(开关定义于
  `katrain/web/core/geometry_calibration_service.py:38`,默认 `False`;翻开前置的说明就写在它上面的注释
  `:31-37`)。**翻开前还缺一件事:识别栅栏**——自动重定位期间不挂起识别,worker 仍按旧几何识别几秒,
  这条尚未接的前置写在 PRD §4「V1-c · 自动静默重定位的默认开关何时翻成 `True`」
  (`superpowers/tracks/kiosk-go-vision/prd.md:172`)。结构闸 `Scenario.RUNTIME_RECALIBRATION.allows_led()`
  为假,已在 `katrain/vision/calibration_strategy.py:29,32-33` 存在,重定位绝不亮灯。对局中。
- **操作**:推动棋盘约 1 格(别拿子),观察屏幕与日志。
- **判据**(2026-09-23 补,三条都用 develop 已经在打的日志,不另造量具):
  1. `journalctl` 里 `vision parallax auto: nadir=(…)`(打点在 `katrain/vision/worker_inprocess.py:293`)
     在重定位前后是**同一条边**(这台盒子 col 18 那条,nadir ≈ (19.61, 9.0));屏上不该进标定台。
  2. 从推盘到新锁生效这段窗口里,**棋谱里没有进任何一手幻影落子**(PRD §2.1 R3,
     「不挂起识别」的代价在这里量)。
  3. 重定位后 ≥ 30 手,`board delta:` 行(`katrain/vision/worker_inprocess.py:587`)里 `@<距离>` 的中位数
     照实记下,与 LED 锁下的数(09-22 那局 0.150 格,`superpowers/tracks/vision-optimizations/README.md:48`)
     并排写 —— **只记录、不当开关判据**,30 手中位数自己就有噪声。
- **记录**:①的边名/坐标、②有没有幻影落子、③中位数,三项都写回本节。

## 3. 人工出口(V1 对齐外框 · 手动恢复路径)

- **前置**:第 1 项已过闸。让盘面进入 `degraded` / `cancelled` / `failed` 三态之一(标定屏状态格
  `degraded` 显示「已失效」,`katrain/web/ui/src/kiosk/components/vision/GeometryCalibrationScreen.tsx:347`)
  ——可用挪盘触发 `degraded`,或用 `RecalibrationModal`
  (`katrain/web/ui/src/kiosk/components/game/RecalibrationModal.tsx`,「重新标定」按钮文案在 `:76`)
  走清盘的 LED 路径退回 `failed`/`cancelled`。盘上留几颗子,不清空。
- **操作**:按「对齐外框」按钮 —— 已实现,`data-testid="calib-relocate"`
  (`GeometryCalibrationScreen.tsx:551`),只在 `phase ∈ {degraded, cancelled, failed}` 且
  `status.last_valid` 为真时渲染(条件在 `:547`),按下后调用前端 `relocate()`(`handleRelocate`,
  `:227-243`),打到 `POST /api/v1/geometry/relocate`(`katrain/web/api/v1/endpoints/geometry.py:150-151`),
  服务端由 `GeometryCalibrationService.relocate()` 处理(`katrain/web/core/geometry_calibration_service.py:760-774`,
  走 `Scenario.MANUAL_FALLBACK`,`allowed_phases=_RELOCATABLE_PHASES = {"degraded","cancelled","failed"}`,
  `:42`)。不亮灯、不要求空盘。
- **判据**:盘上有子也能恢复到 `ready`;nadir 日志同第 2 项判据①(同一条边)。
  **失败路径要一并验**:画面里找不到外框 / 挪得太远时,请求走 400,前端把 `relocateError` 写进状态
  (`:233-239`),渲染成诊断卡 `data-testid="geometry-diagnostic-card"`
  (`GeometryCalibrationScreen.tsx:463-464`,`kind="relocate"`,标题「没对上」,内容按错误类型分
  「画面里找不到棋盘外框,挪开挡住边框的东西再试一次」或「再试一次;一直不行就清空棋盘重新标定」,
  错误分支在 `:233-239`、诊断卡构造逻辑在 `:380-382`)——确认这张卡出现、且不是一片空白。
- **记录**:恢复前/后的 phase、nadir 坐标、(若触发了失败路径)诊断卡文案,写回本节。

## 4. 无灯首标 —— ⛔ V3 本轮不做,留位

- V3(无灯标定)Fan 已裁定本轮不做(`superpowers/tracks/kiosk-go-vision/prd.md:186`)。以后若立项,
  只留一条朝向判据:在一个不对称的点(如 3-4)摆一颗子,屏上必须是同一个点。

## 5. 取消后沿用(V2 的验收)

- **前置**:标定跑到一半。
- **操作**:按「取消标定」(`katrain/web/ui/src/kiosk/components/vision/GeometryCalibrationScreen.tsx:540`
  `t('vision:cancel_calibration', '取消标定')`),再按「沿用上次标定」
  (`:570` `t('vision:reuse_calibration', '沿用上次标定')`,按钮可按受 `canReuse` 控制,`:567`)。
- **判据**:`cancelled` 态下「沿用上次标定」可按(白名单放开见 `_REUSABLE_PHASES = {"required", "failed",
  "cancelled"}`,`katrain/web/core/geometry_calibration_service.py:228`,由 `confirm_existing()`
  在 `:230-238` 校验;**`degraded` 不在表里** —— 那一态的出路是第 3 项的「对齐外框」,不是沿用。
  前端 `canReuse` 判别见 `GeometryCalibrationScreen.tsx:366-367`),按下后恢复识别,继续下棋不受影响。
- **记录**:取消前的 phase、按下「沿用上次标定」后是否恢复识别,写回本节。

## 6. LED 目视 bring-up(可选)

- **前置**:能接串口终端(如 `screen /dev/ttyACM0 115200`)。
- **操作**:发固件 `SCAN [ms]` 命令,逐颗 0→360 自检扫描
  (`superpowers/tracks/sbc-baipu-led-guide/led-calibration-and-protocol.md:23`)。
- **判据**:人眼确认 361 颗都亮、颜色对,`IDX <i>` 逐行打印无跳号、无断点。
- **记录**:是否 361 颗全亮,有无断点/错色,写回本节。

---

## vision-optimizations 自己待上板的项(不抄,只指针)

参照帧从影子模式转正的阈值、指引灯亮度的整局验证,归那条线,细则见
`superpowers/tracks/vision-optimizations/README.md:51-53`。

## 记录 / 提交

实机执行后回填上表并提交:

```bash
git add superpowers/tracks/kiosk-go-vision/board-checklist.md
git commit -m "docs(vision): 回填上板清单第 N 项实测结果"
```
