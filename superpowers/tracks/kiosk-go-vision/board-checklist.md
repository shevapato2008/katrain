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
  第 3④ 项)—— `PoseLostBanner` 已被 `RecalibrationModal` 取代
  (`katrain/web/ui/src/kiosk/components/game/RecalibrationModal.tsx:14-15` 的注释自述
  "Promoted from the old PoseLostBanner top Alert to a Dialog"),本赛道 Z3 又把 `PoseLostBanner`
  组件本身删掉了(PRD §3 Z3;组件当前仍在 `katrain/web/ui/src/kiosk/components/physical/PoseLostBanner.tsx`,
  只有自己的测试消费,验证过零生产消费者)。下面第 3 项「人工出口」按 `RecalibrationModal` 重写。
- **「`SET_GEOMETRY` 子进程缺失」**(原 `acceptance-checklist.md` 「实机验收前必读的已知限制」段)——
  账本给出的删除理由是「盒上走 `InProcessAdapter`,不成立」。**本次复核有出入,记在这里以免被当成
  已解决**:
  - `katrain/web/server.py:4329` `process_mode="worker" if settings.KATRAIN_MODE == "board" else "inprocess"`
    —— 盒上(`KATRAIN_MODE=="board"`)选的其实是 `"worker"`,即子进程 `VisionWorkerProcess`
    (`katrain/vision/worker.py`),**不是** `InProcessAdapter`(`katrain/vision/worker_inprocess.py`,
    那是非 board 模式走的路)。
  - `katrain/vision/worker.py:666-763` 的 `_process_commands` 逐条核过,确认**没有**
    `CommandType.SET_GEOMETRY` 分支(对照 `katrain/vision/worker_inprocess.py:1161-1162` 有)。
  - `GeometryCalibrationService` 的 `on_success` 回调 `promote_geometry`
    (`katrain/web/server.py:855-861`,注册在 `:891`)在**每次标定成功后**(不只是服务启动时)
    都调用 `vision_service.set_geometry(lock)` → `VisionService.set_geometry`
    (`katrain/vision/service.py:182-184`)把 `SET_GEOMETRY` 命令发进 worker 的命令队列——盒上这条
    队列的消费端(`worker.py`)读不懂这个命令,新几何在这条路径上不会落到正在跑的子进程里。
  - 连带确认:本清单第 2 项判据①要看的 `vision parallax auto: nadir=(…)` 日志,整段视差自动推导
    逻辑(`mount_parallax_for_lock`)**只写在** `worker_inprocess.py:277-298` 里,`worker.py`
    完全没有——即使 `SET_GEOMETRY` 被接住,盒上子进程也不会打这行日志。
  - 这不是本任务范围内的代码修复,**本次不重新把它列为清单条目**;但如果第 2 项判据①在真机上
    始终不出现,先查这里,不要当成识别本身出问题。`worker.py` / `worker_inprocess.py` 两套并行
    实现互相漏功能,是这条代码库里已经见过的坑。

---

## 1. 满盘外框精度(V1 自动重定位的闸)

- **前置**:RK3562 + 摄像头 + 实体盘;**这台机器上只跑这一家服务**(2G 内存)。
  先在**空盘**上跑一次 LED 13 点标定并成功 —— 这次的角点就是真值;**之后盘和相机都不许再动**。
- **操作**(量具是 Task 8b 加的真帧模式,`--live` 与 `live_gate` 这次一并落地,本任务不实现):
  1. 空盘先跑一次(对照):`uv run python -m katrain.vision.tools.outer_corner_accuracy --live http://127.0.0.1:8081`
     (真值取 `/api/v1/geometry/layout`,帧取 `/api/v1/geometry/stream` —— 两个路由已在
     `katrain/web/api/v1/endpoints/geometry.py:168` 和 `:150`)。
  2. 轻手摆到约 60 子(别碰盘),再跑一次;有余力摆到约 150 子跑第三次。
  **不带 `--live` 跑出来的是合成图**,只是下界(默认阈值 0.12 见
  `katrain/vision/tools/outer_corner_accuracy.py:5`),不能当这道闸。
- **判据**:每一次都 `GATE(<0.12 cells, >=80% frames detected) = True`。
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

- **前置**:第 1 项已过闸,`AUTO_RELOCATE_ON_DRIFT = True`(翻开位置见
  `superpowers/tracks/kiosk-go-vision/plan.md:882`;结构闸 `Scenario.RUNTIME_RECALIBRATION.allows_led()`
  为假,已在 `katrain/vision/calibration_strategy.py:29,32-33` 存在,重定位绝不亮灯)。对局中。
- **操作**:推动棋盘约 1 格(别拿子),观察屏幕与日志。
- **判据**(2026-09-23 补,三条都用 develop 已经在打的日志,不另造量具):
  1. `journalctl` 里 `vision parallax auto: nadir=(…)`(打点位置见上面「已删除的过期项」第二条的
     连带确认,若始终不出现先查那里)在重定位前后是**同一条边**(这台盒子 col 18 那条,
     nadir ≈ (19.61, 9.0));屏上不该进标定台。
  2. 从推盘到新锁生效这段窗口里,**棋谱里没有进任何一手幻影落子**(PRD §2.1 R3,
     「不挂起识别」的代价在这里量)。
  3. 重定位后 ≥ 30 手,`board delta:` 行(`katrain/vision/worker.py:607`)里 `@<距离>` 的中位数
     照实记下,与 LED 锁下的数(09-22 那局 0.150 格,`superpowers/tracks/vision-optimizations/README.md:48`)
     并排写 —— **只记录、不当开关判据**,30 手中位数自己就有噪声。
- **记录**:①的边名/坐标、②有没有幻影落子、③中位数,三项都写回本节。

## 3. 人工出口(V1 对齐外框 · 手动恢复路径)

- **前置**:第 1 项已过闸。让盘面进入 `degraded` 态(标定屏状态格显示「已失效」,
  `katrain/web/ui/src/kiosk/components/vision/GeometryCalibrationScreen.tsx:325`)——可用挪盘触发,
  或用 `RecalibrationModal`(`katrain/web/ui/src/kiosk/components/game/RecalibrationModal.tsx`)的
  「重新标定」路径。盘上留几颗子,不清空。
- **操作**:按「对齐外框」(V1 新增的无灯出口;当前 `RecalibrationModal` 只有需要清空棋盘的 LED
  「重新标定」按钮,`:76` `t('Recalibrate', '重新标定')`——V1 落地后这里要加一个不需要清盘的
  outer-corner 出口,操作时对照当时的按钮文案)。
- **判据**:盘上有子也能恢复到 `ready`;nadir 日志同第 2 项判据①(同一条边)。
- **记录**:恢复前/后的 phase、nadir 坐标,写回本节。

## 4. 无灯首标 —— ⛔ V3 本轮不做,留位

- V3(无灯标定)Fan 已裁定本轮不做(`superpowers/tracks/kiosk-go-vision/prd.md:186`)。以后若立项,
  只留一条朝向判据:在一个不对称的点(如 3-4)摆一颗子,屏上必须是同一个点。

## 5. 取消后沿用(V2 的验收)

- **前置**:标定跑到一半。
- **操作**:按「取消标定」(`katrain/web/ui/src/kiosk/components/vision/GeometryCalibrationScreen.tsx:506`
  `t('vision:cancel_calibration', '取消标定')`),再按「沿用上次标定」
  (`:517-520` `t('vision:reuse_calibration', '沿用上次标定')`)。
- **判据**:`cancelled` 态下「沿用上次标定」可按(白名单放开见
  `katrain/web/core/geometry_calibration_service.py:196`;前端 `canReuse` 判别见同文件
  `GeometryCalibrationScreen.tsx:342`),按下后恢复识别,继续下棋不受影响。
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
`superpowers/tracks/vision-optimizations/README.md:51-54`。

## 记录 / 提交

实机执行后回填上表并提交:

```bash
git add superpowers/tracks/kiosk-go-vision/board-checklist.md
git commit -m "docs(vision): 回填上板清单第 N 项实测结果"
```
