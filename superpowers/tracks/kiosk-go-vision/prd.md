# 围棋 kiosk · 视觉 / 标定 / 实体盘 赛道 PRD(kiosk-go-vision)

- 日期:2026-09-20
- 分支 / worktree(**已创建 2026-09-21**):`feature/kiosk-go-vision` @ `/Users/fan/Repositories/katrain-kiosk-go-vision`,基线 develop `7a152df1` → **2026-09-23 起 `a586026b`**(合入 origin/develop `3fb7ac5c`)
- 输入:2026-09-14「围棋 kiosk 缺口账本」视觉模块七条(V1–V6、N16)
- **本文所有行号都在 develop `012e2a04` 上重核过(2026-09-20)**。账本成文于 `6f7dc629`,其后 develop 在视觉这一块前进很多(`geometry_calibration_service.py` +396 行、`led_geometry_calibrator.py` +314 行、`VisionSyncOverlay.tsx` 重写、新增 `visionRecovery.ts`)——**N16 已被修掉**(见 §2),其余六条逐行复核后仍然成立。 **2026-09-21 基线移到 develop `7a152df1`**(其后 43 个提交是视觉识别稳定性与退出兜底):本文引用的文件里只有 `server.py` 行号漂移(+1),已按新基线改;这 43 个提交改的是识别链(`move_detector` / `sync` / `worker`),不碰本文的几何标定段落。
- **2026-09-23 基线再移到 `a586026b`**(本分支合入 origin/develop `3fb7ac5c`)。其间 develop 进了 26 个视觉提交(视差校正、0.20 维持档、参照帧比对、没人用摄像头时停识别、LED 标定每锚点连拍、指引灯随环境光调亮度、标定屏推流缩放)。逐条对过本文六条:**根因全部仍在,没有一个提交碰它们**;但它们都是几何锁的**下游消费者**,由此给 V1 / V3 / V4 加了约束,写在 **§2.1**。本文行号已在 `a586026b` 上重核。
- **2026-09-24 再合一次 develop(`a512aa6a`)**:又进了一轮识别优化 —— 影子框去重(`board_state.drop_shadow_boxes`,`51faae2a` 等),以及摆谱接摄像头(`49dbe8db` 等,顺手把此前漏进 `.po` 的 key 补齐,`test_kiosk_i18n.py` 因此**转绿**)。本文引用的几何标定 / 标定屏 / 左栏 / `server.py` 几处一行没动,行号仍然有效;`set_geometry` 那条交付口没动;影子去重依赖几何精度,已补进 §2.1。

---

## 1. 背景与目标

实体盘这条链今天在盒上是能跑的:13 点 LED 标定、沿用上次标定、标定中挂起识别 worker、漂移监视、落子识别与恢复对话框、LED 引导。2026-09 那一轮还把标定期间的卡顿(「卡在 N/13」)和 board_lost 的文案都修了。

剩下的问题集中在**一件事**:**盘被碰动之后没有回得来的路**。

1. **中盘碰一下盘,这局在实体盘上基本就接不下去了。** 漂移监视判定漂移 ⇒ `phase` 变 `degraded` ⇒ 识别几何被清掉 ⇒ 守卫把整个对局屏换成标定台 ⇒ 而「重新标定」走的是 **13 点 LED 流程,要求空盘**。盘上有子就抛错 —— 也就是说,要恢复得先把这局的棋子全部拿掉。
   库里为这件事写好的东西**一件都没接上**:`CalibrationSelector` 的 `RUNTIME_RECALIBRATION` 场景(只用外框、绝不亮灯)、`OuterCornerStrategy`(`works_on_crowded_board = True`)、`DriftStateMachine` / `RotationAwareDrift` —— 生产代码里唯一的调用方是**摆谱采集**(`baipu_capture.py:241`),而它算出来的 `M` 只写进采集 manifest,不回写识别用的几何。
2. **标定跑到一半误触「取消」,上一次的标定也作废了。** 取消后 `phase = cancelled`,而 `confirm_existing` 只接受 `required` / `failed` ⇒ 「沿用上次标定」变灰,屏上还**不说为什么**(`reuseBlockedWhy` 在 `cancelled` 时是 `null`)。当初裁定「不给取消配确认弹层」的理由是「取消是廉价且可逆的」——这个前提不成立。
3. **没有 LED 的盒子做不了第一次标定。** `start()` 第一句就是 `if self.led is None: raise ValueError("LED is required for geometry calibration")`,前端 `canStart` 也要求 `ledReady`。而 `calibration_registry.py:27` 为 `INITIAL_SETUP` 配的第二条路 `empty_board_autocal`(无灯、空盘、全网格)**生产零调用**。
4. **「LED 就绪」只表示串口打开了。** `led_ready` 就是 `LedService._connected`(`led_service.py:199-200`),灯带某一段坏了屏上照样绿。

这一轮要让盒上用户得到三件事:
1. 盘被碰动后,**不清盘**也能把几何找回来(先自动试,不行再给一颗用户按的「对齐外框」——**永远不自动亮灯**,那是 Fan 的硬规矩)。
2. 误触取消之后,「沿用上次标定」还能按,而且屏上说得出为什么能按 / 不能按。
3. 没有 LED 的盒子也能完成第一次标定(无灯空盘自动标定)。

另外两件(LED 自检、真机验收回填)本轮只做能做的那部分:把「LED 就绪」这句话改准,以及把四份文档里散着的真机验收项收成**一份可执行的上板清单**。

## 2. 已经做完、不要动的

| 内容 | 出处 |
|---|---|
| **N16 已修**:board_lost 对话框不再指向那条早已不存在的「横幅中的『重新定位』」,改成「看一下摄像头有没有被挡住、棋盘有没有被挪动;挪动过的话要重新标定」 | `VisionSyncOverlay.tsx:305`(`939165a4`) |
| 标定期间挂起 / 恢复识别 worker(`on_suspend` / `on_resume`),失败或取消时把旧几何推回去 | `geometry_calibration_service.py:99-107`、`:585-597` |
| 曝光收敛与收敛后再量的顺序、失败诊断分类(`low_signal` / `ambiguous_blobs` / …) | `geometry_calibration_service.py:479-513` |
| 标定发布的原子性:先暂存、`_before_publish` 线性化取消、失败回滚(回滚失败则作废运行时几何) | `:425-477`、`:559-579` |
| 漂移监视(`GeometryDriftMonitor`,Sobel + phaseCorrelate,连续 3 帧超阈值才判漂移) | `katrain/vision/geometry_drift.py` |
| 识别落子的恢复状态机(`visionRecovery.ts`)与 `VisionSyncOverlay` 重写 | `visionRecovery.ts`、`VisionSyncOverlay.tsx` |
| **LED 绝不为几何自动点亮**(Fan 硬规矩),结构上由 `Scenario.allows_led()` 保证 | `calibration_strategy.py:26-33`;屏上那句常驻提示 `GeometryCalibrationScreen.tsx:468` |
| 标定屏的四步进度、三格状态、「没读到之前写 —」 | `GeometryCalibrationScreen.tsx:303-338` |

### 2.1 09-21 至 09-23 的识别优化:本赛道在它们上游,**不改它们**(2026-09-23 新增)

这批改动全部已上线(总表见 `superpowers/tracks/vision-optimizations/README.md`)。它们都不碰 V1–V5 的根因,但**都读几何锁**。本赛道要换的恰好是几何锁,所以接口约束写在这里:

| develop 上的改动 | 它怎么接几何锁 | 对本赛道的约束 |
|---|---|---|
| 视差校正,参数从锁推出(`f522fe53`,`parallax.py` `mount_parallax_for_lock`) | worker `set_geometry` 每收到一把锁就重推一次;**朝镜头的是哪条边,由锁的四角顺序决定**。盒上 LED 锁里朝镜头的是 col 18 那条边(`docs/2026-09-22-kiosk-device-session.md` §2) | V1 重建出的锁**四角顺序必须与旧锁一致**(见 R2) |
| 参照帧比对,影子模式(`4c70eefb`…`c70cf925`,`reference_frame.py`) | `set_geometry` 里 `_invalidate_reference("geometry")`,参照帧跟着新几何重取 | 新锁必须走 `set_geometry`(R1),参照帧就会作废并重取,本赛道不用另做 |
| 0.20 维持档(`cc943f1c` / `c9d1d69e`,`board_state.py`) | 在锁的网格坐标里判断「棋谱里已有的子」 | 朝向错了,「已有的子」整盘对不上(R2) |
| 没人用摄像头时停识别 / 漂移检测 / 1080p 解码(`275625ec`) | 标定服务新参数 `drift_needed`;相机空闲 3 s 后只出队不解码 | V1 自动那条只在漂移循环里触发 ⇒ 只在有人下实体棋时才会跑,正合适。**构造函数保留 `drift_needed`**;取帧照旧用 `grab_fresh()`,它会把相机唤醒 |
| LED 标定每颗锚点亮约 1 s 连拍取最小(`de40f28c`) | 只影响 13 点流程 | 重新标定变得更慢,V1「不清盘」的价值因此更大 |
| 指引灯亮度随环境光调(`88b2b1e9` / `7821edb3`,`led_service.py` `set_guidance_scale`) | 不读几何 | V4 只改措辞,不碰 `led_service.py` |
| 影子框去重(`51faae2a` 等,09-24 合入,`board_state.drop_shadow_boxes`) | 一个石子框离最近交叉点(视差校正后)≥ `SHADOW_MIN_OFFSET = 0.35` 格、又与更靠近交点的同尺寸框重叠,才被当作影子丢掉 —— **直接用锁的网格判「离交点多远」** | 重定位后的几何误差必须远小于 0.35 格,否则真子会被推到「像影子」那一侧;V1 的上板精度闸 0.12 格满足这一条。朝向错了则整盘错位,同样落在 R2 |
| 标定屏推流缩放 `?scale=`(`de40f28c`,`geometry.py` `_downscale`、屏上 `RAW_STREAM_SCALE`) | 覆盖层坐标要乘回缩放比 | V1-b / V2 / V4 改同一个屏文件,**保留这两个常量与 `onImageLoad` 的乘回** |

**规则**

- **R1 · 唯一交付口。** 新几何只经 `on_success` → `server.py` 的 `promote_geometry` → `vision.set_geometry(lock)`。`set_geometry` 会重置运动滤波、作废参照帧、重推视差。**不许**直接去改 worker / extractor,也**不许**原地改旧锁对象(relock 用 `dataclasses.replace` 出新对象)。
- **R2 · 朝向连续。** LED 锁的四角按**棋盘行列**排(`led_geometry_calibrator.py` 的 `_build_lock`,`diag.orientation = "seated_human"`);外框法和无灯自动标定按**画面位置**排(`geometry_detect.sort_corners`)。两种排法不一定一致;不一致时直接拿外框法的结果建锁,整张网格会转 90° 或 180°:识别坐标、维持档、视差都会跟着转(视差在自动模式下会对着那把转错的锁自己重推,算得自洽,但坐标已经错了,它救不回来)。**重建时必须把外框四角重排成离旧锁四角最近的那一种**;若最近与次近分不开(盘转了约 45°),就拒绝,当作失败处理。2026-09-23 已在 scratchpad 里用真模块做过原型:不对齐时,旋转顺序的锁重定位后,视差推出的镜头落点(nadir)会换到另一条边;对齐后,4 种旋转顺序的 nadir 全部留在原边,镜像顺序的四角也对得上(原型与用例见 plan Task 3)。
- **R3 · 自动重定位期间不挂起识别。** 挂起(`on_suspend` 把 worker 几何清空)会让 `recognition_ready` 掉下来,`PhysicalBoardGuard` 就会把对局屏卸载、换成标定台,这正是 V1 要避免的事。代价是:从判定漂移到新锁推下去,中间还有几秒 worker 按旧几何识别。这段窗口今天就有(漂移要连续 3 帧才判定),**本赛道不声称下游一定兜得住**,改成上板实测(§7 上板清单第 2 项:碰盘过程中不许有幻影落子进棋谱)。
- **R4 · 这批优化的文件一行不改**(以合进来的 develop 为准:`git diff $(git merge-base HEAD origin/develop)`,不写死提交号 —— 再合 develop 时 develop 自己改这些文件不算本赛道的改动)。 `katrain/vision/{worker_inprocess,board_state,parallax,parallax_store,reference_frame,camera,service}.py`、`katrain/web/core/led_service.py`;`server.py` 只许改 `GeometryCalibrationService(...)` 构造那一段(`:885-897`),**不碰** `_vision_needs_frames` / `_adjust_led_brightness` / 视觉命令行参数。收尾核对见 plan Task 10 Step 2b。
- **R5 · 这批优化自带的测试收尾必须原样全绿**:`tests/test_vision/` 下 `test_parallax_*`、`test_board_state_parallax`、`test_board_state_golden`、`test_board_state_shadow`、`test_shadow_phantom`、`test_reference_frame`、`test_sustain_threshold`、`test_vision_idle`、`test_led_glow`、`test_worker_commands`、`test_calibrate_parallax`,以及 `tests/web_ui/test_led_brightness_loop.py`、`tests/test_led_service.py`、`tests/test_geometry_calibration_service.py` 里的 `drift_needed` 用例。

---

## 3. 需求条目(本轮做)

### V2 · 误触「取消标定」后,上一次的标定也用不了了 —— P1

- **现象**:标定运行中按「取消标定」⇒ `phase = cancelled` ⇒ 「沿用上次标定」变灰,**屏上不说原因**;实体盘路由(含正在下的那局)一律被标定台拦着,只能清空棋盘重跑分钟级的 LED 标定,或者重启服务。
- **根因(已核实)**:
  - `geometry_calibration_service.py:196` `if self._status["phase"] not in {"required", "failed"}: raise ValueError(...)`。
  - `GeometryCalibrationScreen.tsx:342` `canReuse = (phase === 'required' || phase === 'failed') && …`;`:343-345` 的 `reuseBlockedWhy` 只覆盖「标定进行中 / 摄像头未连接 / 这一局已经在用这次标定」,`cancelled` 时是 `null`。
  - 服务端其实**没丢东西**:`current_lock` 还在,`on_resume` 也把识别恢复到了旧几何(`:595`)——缺的只是一个把 `phase` 拉回 `ready` 的入口。
- **期望**:
  - 服务端 `confirm_existing` 的白名单加上 `cancelled`(**不加 `degraded`** —— 那一态是「这份几何已知是错的」,沿用它等于用错的几何去识别;它的出路是 V1)。
  - 前端 `canReuse` 同步放开 `cancelled`;`reuseBlockedWhy` 补上 `degraded` 那一支的原因(「棋盘挪动过,上次的标定对不上了」),让「按不了」永远有话说。
  - **V6 顺带解决**:当初「不给取消配确认弹层」的理由是「取消廉价且可逆」——V2 落地后这句话**重新成立**,所以仍然不加确认层;把这条前提与日期写进 `GeometryCalibrationScreen.tsx` 那段注释,别让下一个人再从一个过期前提出发。
- **验收**:
  1. pytest:`cancel()` 之后 `confirm_existing()` 成功,`phase` 回到 `ready`,`session_calibrated` 为真。
  2. pytest:`degraded` 之后 `confirm_existing()` 仍然抛 `ValueError`(**这一条是反向闸**,防止顺手把 degraded 一起放开)。
  3. vitest:`phase='cancelled'` 且 `last_valid` 时「沿用上次标定」可点;`phase='degraded'` 时不可点**且**屏上出现原因那句。
  4. vitest:`phase='required'` / `'failed'` 的既有行为不变。
- **依赖**:无。后端一行白名单 + 前端判别位与文案。

### V1 · 盘被碰动后只能清盘重来 —— P1

- **现象**:对局 / 做题中把盘碰动 ⇒ 屏上换成标定台 ⇒ 「重新标定」要求空盘 ⇒ 这局在实体盘上接不下去。
- **根因(已核实)**:
  - `geometry_calibration_service.py:635-653` `_apply_drift`:判定漂移就 `phase = "degraded"` + `on_degraded()`(`server.py:862-869` 清掉运行时几何),**没有任何恢复尝试**。
  - 标定服务固定用 `calibrator_factory=LedGeometryCalibrator`(`:82`),**不经 `CalibrationSelector`**;`build_default_selector()` 的唯一生产调用方是 `baipu_capture.py:248`,而那里算出的 `M` 只进采集 manifest。
  - `OuterCornerStrategy` 本来就是为这件事写的:`requires_led = False`、`works_on_crowded_board = True`,用的是**外框**(棋子永远挡不住外框)。
- **期望**:两条路,合起来才闭环。
  - **(a) 自动静默重定位**:漂移判定成立时,先跑一次 `Scenario.RUNTIME_RECALIBRATION`(策略表里只有 `outer_corner`,**结构上不可能亮灯**)。成功 ⇒ 用新的单应重建 lock(重算 `corners` / `points`,**四角按旧锁朝向重排**(§2.1 R2),**保留 `baseline`**)、`on_success` 推给识别 worker(§2.1 R1)、`phase` 留在 `ready`、漂移基准重置;失败 ⇒ 照今天降级成 `degraded`,并把失败原因写进 `metrics`。**不写盘**:磁盘上那份是 LED 13 点的 golden reference,外框法只是本次开机的运行时修正,重启后回到 `required`,可以「沿用上次标定」(2026-09-23 更正:原稿这里写的是「持久化」,与 plan 的「不写盘」矛盾,以 plan 为准)。重定位期间**不挂起识别**(§2.1 R3)。
  - **(b) 用户按的「对齐外框」**:`degraded` / `cancelled` / `failed` 三态下,标定屏给一颗「对齐外框(不亮灯,盘上有子也行)」,走 `Scenario.MANUAL_FALLBACK` 的 `outer_corner`(**LED 那一支本轮不接** —— 它要求空盘,而这颗键存在的理由正是盘上有子)。它是自动那条路失败后的人工出口。
  - **(c) 精度闸**:外框法在**满盘**下的真机精度没有人量过。`outer_corner_accuracy.py` 定的判据是误差 < **0.12 格**。所以:
    - 自动那条路(a)的开关**默认关**,常量写在源码里(`AUTO_RELOCATE_ON_DRIFT = False`)并在注释里点名它等的是哪一条上板闸;
    - 用户按的那条(b)**默认开** —— 它是用户主动发起的,而且今天的替代品是「清盘重来」,更差;
    - 上板闸通过后,在**同一次改动**里把常量翻成 `True` 并补一条测试。
- **验收**:
  1. pytest:注入一个假 selector,漂移成立且 `auto_relocate=True` 时不进 `degraded`,`phase` 仍 `ready`,`on_success` 被调用一次,**持久化零次**、**`on_suspend` 零次**(后两条钉住「不写盘」与 §2.1 R3)。
  2. pytest:假 selector 返回 `ok=False` 时,终态与今天相同(`degraded` + `on_degraded` 一次),且 `metrics` 里能看到失败原因。
  3. pytest:`AUTO_RELOCATE_ON_DRIFT = False`(默认)时,漂移仍然直接 `degraded` —— **这一条钉住「默认关」**,免得闸没过就悄悄上线。
  4. pytest:`relocate()` 在 `degraded` / `cancelled` / `failed` 三态都能跑,且**不接受空盘要求**(盘上有子照跑);运行中(`active`)调用抛 `CalibrationBusy`。
  5. pytest(**结构闸**):`Scenario.RUNTIME_RECALIBRATION.allows_led()` 为假,且本轮新增的两条路径都没有把 `led` 传进 `CalibrationContext`。
  6. pytest:重建 lock 的纯函数 —— 给一个已知 lock 与一个平移过的 `M`,重算出的 `points` 与直接用新 `corners` 走 `grid_points_from_corners` 的结果一致,`baseline` 原样保留。
  7. vitest:`degraded` 态标定屏出现「对齐外框」键,点它调 `/api/v1/geometry/relocate`;成功后屏回到 `ready`,失败时屏上给原因。
  8. **上板**:见 §7「上板清单」第 1–3 项(满盘外框精度、对局中碰盘恢复、恢复后识别不串位)。
  9. pytest(**朝向闸**,2026-09-23 新增):旧锁四角是画面顺序转过 0/1/2/3 格的四种、再加一种镜像顺序,外框法给的都是画面顺序的单应;重建后四角顺序与旧锁一致,`points[0][0]` 只随平移移动;**`mount_parallax_for_lock(新锁).nadir == mount_parallax_for_lock(旧锁).nadir`**(这一条直接守住 develop 的视差校正)。盘转了约 45°、最近与次近排法分不开时抛 `ValueError("orientation_ambiguous")`。
  10. 收尾:§2.1 R4 的文件相对合进来的 develop 零改动,R5 的测试原样全绿。
- **依赖**:上板闸(精度)。代码本身不依赖上板即可合并(默认关)。

### V3 · 没有 LED 的盒子做不了第一次标定 —— P2 · ⛔ **本轮不做(Fan 2026-09-23 裁定,§4)**

> **2026-09-23 为什么不做**:① 在售的盒子都装了灯带,这一条只在串口起不来时有用;② 合并 develop 后发现一个前置没解决 —— 无灯自动标定按**画面位置**排四角,LED 锁按**棋盘行列**排(§2.1 R2)。有旧锁可对齐时能像 V1 一样重排(但无灯出的是**整把锁**,`points` 与 `baseline` 都要跟着转);**从来没标过的盒子没有旧锁可对**,朝向只能靠一条装机约定,而这条约定仓里没有。朝向错了,屏上 AI 落在 A 点、用户照屏幕摆在实体盘的 A 点,摄像头却把它读成转过的另一点 —— 对弈直接对不上。下面保留原需求,留给以后立项时用;届时先补下面「朝向前置」那条。

- **现象**:LED 串口没起来(或这台机器根本没装灯带)时,「重新开始标定」按不了(`canStart` 要 `ledReady`),后端也会直接抛错。磁盘上已经有 `geometry_lock.npz` 的盒子还能「沿用上次标定」,**第一次**标定则完全没路。
- **根因(已核实)**:`geometry_calibration_service.py:129` `if self.led is None: raise ValueError("LED is required for geometry calibration")`;`GeometryCalibrationScreen.tsx:341` `canStart = cameraReady && ledReady && …`;`calibration_registry.py:27` 给 `INITIAL_SETUP` 配的 `empty_board_autocal` 生产零调用。
- **期望**:
  - `start()` 在**没有可用 LED** 时不再抛错,改走 `Scenario.INITIAL_SETUP` 的选择器 —— `led_anchor` 会因 `is_applicable`(需要 `led`)自行让位,落到 `empty_board_autocal`(无灯、空盘、产出完整 lock 含 `baseline`)。空盘仍然是硬要求(`empty_confirmed`),这一条不放开。
  - 前端 `canStart` 去掉 `ledReady`;没有 LED 时屏上说明白:「这台盒子没有灯带,用无灯方式标定:精度略低,盘上不能有子」。LED 那一格仍写「未连接」(那是事实)。
  - **有 LED 时行为一个字不变**(13 点流程仍是首选、仍是 golden reference)。
  - **朝向前置(2026-09-23 新增)**:磁盘上有旧锁时,把无灯锁整体转到旧锁朝向(`corners` 重排,`points` / `baseline` 用同一个 `np.rot90` / 转置);没有旧锁时用哪条装机约定,**先定下来再做**,并进上板清单第 4 项核一次(在一个不对称的点上摆一颗子,看屏上是不是同一个点)。
- **验收**:
  1. pytest:`led=None` 时 `start(empty_confirmed=True)` 不抛,跑完后 `phase='ready'` 且 lock 来自 `empty_board_autocal`。
  2. pytest:`led=None` 且 `empty_confirmed=False` 时仍抛 `ValueError`(空盘要求不放开)。
  3. pytest:`led` 可用时仍走 `LedGeometryCalibrator`(**回归闸**:13 点流程没有被顺手换掉)。
  4. vitest:`ledReady=false` 时「重新开始标定」可点,且屏上有那句无灯说明;`ledReady=true` 时文案不出现。
  5. pytest:有旧锁时,无灯锁的四角顺序与旧锁一致,`mount_parallax_for_lock` 的 nadir 落在同一条边(与 V1 验收 9 同一个判据)。
- **依赖**:无灯自动标定的真机精度**未验**⇒ 列进上板清单第 4 项;朝向约定未定(见上)。原稿的「先上、不设开关」基于「替代品是完全不能标定」,这一点仍成立,但 2026-09-23 起要先过朝向前置。

### V4(缩范围)· 「LED 就绪」这句话不准 —— P3

- **事实**:`led_service.py:199-200` `is_connected()` 返回的是 `self._connected`,也就是**串口开没开**;`/api/v1/led/status` 同源。灯带某一段坏了、或者 UR 段那个硬件故障没修,屏上照样是绿色「就绪」。
- **本轮只做**:把话说准 —— 标定屏与设置屏那一格从「LED · 就绪 / 未连接」改成「LED · **串口已连接** / 未连接」,并在标定屏那段说明里加一句「这一格只说串口通了,不代表每颗灯都亮」。
- **2026-09-23 范围再缩**:
  - **设置屏已经做完** —— 设置赛道照本条改了(`SettingsPage.tsx:280-287`,`3b8af0a2`),key `settings:led_serial_connected` 11 语种已入库(`d3b446a8`)。本赛道**不再碰 `SettingsPage.tsx`**。
  - 标定屏那一格**复用同一个 key** `t('settings:led_serial_connected', '串口已连接')`:同一件事只有一种说法(设置屏注释写的就是「措辞照抄标定屏」),而且零新增译文。
  - **左栏 `GoConsoleRail.tsx:70` 改成「已连接」**(Fan 2026-09-23 裁定,§4):与同一栏摄像头那格一样的三个字,宽度已经验证过。左栏太窄,放不下「串口已连接」五个字;「已连接」本身也只说连上了,不声称每颗灯都亮。
  - **设计稿同步(只改源头,不重拍)**:稿子里这组状态格是一个共享常量 `STATUS`(smartbox `superpowers/shared/kiosk-shell/sample-go/go-kiosk.tmpl.html:2484`),五个屏都在画(对弈 / 训练 / 棋谱 / 课程 / 标定)。而它们的参考图分别钉在 smartbox 的**四条分支**上(`reference-shots.json`:01-play 在跨平台稿分支,15-kifu 在棋谱列表稿分支,26-calib 在大厅稿分支,11–14 在 main),几条分支上还有别的会话在干活。所以本轮**只改 smartbox main 上那一个常量并重建两份 HTML**;已钉的参考图不重拍、不重钉,等各分支下次合 main 重拍时自然带上。在那之前,四图里这一个词的差异是**已知差异**,判图时照此核对,不算回归。

- **本轮不做**:相机逐颗扫描的真自检(PRD `sbc-baipu-led-guide/prd.md:174` 那条「命中恰好 361 个互异交叉点」)。理由:它要人在场、要空盘、要一两分钟,而且 UR 段的硬件修复状态两个仓里都看不出来 —— **先把话说准,再谈自检**。固件侧已有 `SCAN` 命令可做人工目视 bring-up,记在上板清单第 6 项。
- **验收**:`rg -n "LED.*就绪" katrain/web/ui/src --glob '!*.test.*'` 零命中;标定屏、左栏 vitest 各一条(设置屏的那条设置赛道已有);smartbox 模板里 `["LED", "已连接", "good"]`。

### V5 · 真机验收项散在四份文档里,一条都没回填 —— P3(本轮产出一份清单)

- **事实(已核实)**:`kiosk-physical-play/acceptance-checklist.md:31-44` 的 14 行结果列全空(仅 07-02 一次提交);`kiosk-golaxy-physical-play` 的 PRD 状态仍是「待 rk3562 真机验证」,plan Task 14 三项与 `kiosk-play-golaxy` §14 D1–D4 都没勾;`2026-08-20` 对齐计划 Task 20 Step 6 明写「上板走查没做」。清单本身也**过期了两处**:第 3④ 项引用的 `PoseLostBanner` 已被 `RecalibrationModal` 取代;「SET_GEOMETRY 子进程缺失」在盒上走 `InProcessAdapter`,不成立。
- **本轮只做**:把四份里**仍然成立**的真机项收成一份 `board-checklist.md`(本赛道目录下),按 Fan 的「RK3562 2G,一次只跑一家」写成可串行执行的步骤,并把本轮 V1 的闸加进去(V3 那一项标「本轮不做」留位)。过期的两项删掉并写明为什么。
  **2026-09-23 补**:V1 那几项要用上 develop 已经在打的两行日志,不另造量具 —— `vision parallax auto: nadir=(…)`(重定位前后必须是同一条边,核朝向)与 `board delta:` 行里的 `@<距离>`(落子到交叉点的距离,09-22 那一局中位数 0.150 格,核重定位后有没有变差)。vision-optimizations 自己待上板的项(参照帧从影子模式转正的阈值、指引灯亮度的整局验证)**只列指针不抄**,它们归那条线(`vision-optimizations/README.md`)。
- **不做**:上板执行本身(要人在场 + 实体盘 + 灯带 + 摄像头),由 Fan 定时机。
- **验收**:`board-checklist.md` 每一项都有:前置条件 / 操作 / **判据(数或现象)** / 记录位置;每一项都能指到本仓或 smartbox 的一行代码或一份文档。

### Z3(顺带清理)· `PoseLostBanner` 零消费者

- `kiosk/components/physical/PoseLostBanner.tsx` 自 `RecalibrationModal` 上线后就没有生产消费者(只剩自己的测试)。N16 的修复已经把屏上指向它的最后一句话去掉了。
- **本轮**:删组件与它的测试。**归属说明**:它在账本里挂「外壳/横切」(Z3),但它是视觉这条链的死代码,顺手清掉;若将来另立横切赛道,这一条已经不在了。

---

## 4. 待 Fan 拍板

### V1-c · 自动静默重定位的默认开关何时翻成 `True` —— **Fan 2026-09-21 已确认「默认关」**

- **裁定**:本轮实现后默认 **关**(`AUTO_RELOCATE_ON_DRIFT = False`)。翻开它的前置是上板闸:**满盘下外框法的几何误差 < 0.12 格**(判据来自 `katrain/vision/tools/outer_corner_accuracy.py:5`),以及「碰盘 → 自动恢复 → 继续下棋不串位」实测(`board-checklist.md` 第 1–2 项)。
- 这条与 `sbc-baipu-led-guide` plan 修订说明第 9 条同一条规矩(「默认切到 auto 必须在真机 GATE 通过之后」)。
- **仍待 Fan**:上板时间(RK3562 + 摄像头 + 灯带 + 实体棋子,人在场,一次只跑一家)。闸过之后,把常量翻成 `True` **要和上板结果写在同一次提交里**。
- ⚠️ 注意这不影响**用户按的**那颗「对齐外框」:它默认可用,因为它是用户主动发起的,而它今天的替代品是「清盘重来」。

### V4 · LED 真自检要不要排期

- 做:一次相机逐颗扫描(361 点),能报出接线错 / 坏灯 / 整段不亮,代价是一次一两分钟的人在场流程 + 一个新界面。
- 不做:维持「串口已连接」这句准确但弱的话,坏灯只能靠用户发现引导不亮。
- **推荐**:排在硬件 v4(TX 缓冲修复)之后再做 —— 在硬件故障还在的机器上,自检只会天天报红,而红了也没有修法。

### V3 · 无灯标定出来的精度如果明显低于 13 点,要不要在屏上长期标注

- 若上板实测无灯标定的误差明显大于 LED 13 点,建议在标定完成后的状态格里长期标一句「无灯标定」,让后续识别问题有个解释的起点。**要不要这一句由 Fan 定**(它是长期占屏的文案)。

### V3 · 本轮做不做 —— ✅ **Fan 2026-09-23 裁定:本轮不做**

- **裁定:本轮不做**,plan Task 6 整体跳过(保留原文,留给以后立项)。理由见 §3 V3 开头:在售盒子都有灯带,收益只在串口起不来时才有;而「从没标过的盒子用哪条朝向约定」得先定,不然做出来的是一把方向可能错了的锁。
- 要做的话:先定朝向约定,再按 §3 V3「朝向前置」做,上板清单第 4 项多核一条朝向。
- 不做的代价:串口起不来、磁盘上也没有旧锁的盒子,今天照样标定不了(与现状相同,不是回退)。

### V4 · 左栏(`GoConsoleRail`)那格「LED 就绪」要不要跟着改稿 —— ✅ **Fan 2026-09-23 裁定:改成「已连接」,设计稿同步**

- 标定屏和设置屏会改成「串口已连接」,左栏还是「就绪」,**同一件事会有两种说法**。
- 左栏照的是设计稿 `sample-go/01-play.png`,所以改字等于改稿;另外左栏很窄,「串口已连接」五个字放不下。
- **推荐**:左栏改成「已连接」(与同一栏里摄像头那格一样的三个字,宽度已经验证过),设计稿同步改;确认之后,作为一个单独的小提交跟 V4 走。
- **裁定**:照推荐。落地时核到设计稿同步的代价比预想大(参考图钉在四条分支上,见 §3 V4),所以「同步」收成**只改 smartbox main 上那一个常量**,参考图不重拍;做法与已知差异写在 §3 V4。

---

## 5. 不在本轮

| 条目 | 类别 | 一句理由 |
|---|---|---|
| LED 真自检(361 点扫描) | 待 Fan / 等硬件 | 见 §4。 |
| 上板执行 | 需人在场 | 本轮只产出清单(§3 V5)。 |
| `DriftStateMachine` / `RotationAwareDrift` 接进主链 | 未立项 | 本轮只接 `CalibrationSelector`(旋转感知那一层要先有真机漂移数据才谈得上调参)。 |
| 摆谱采集那条链(`baipu_capture.py`)的默认模式 | 归 baipu 赛道 | 它自己的 GATE 在 `sbc-baipu-led-guide/plan.md:2544`。 |
| A21 对局中「棋盘可能被移动」弹层的文案与去向 | 归对弈赛道 | 它在 `RecalibrationModal`/`GamePage`,归 play-ai;**但本轮 V1-b 的「对齐外框」落地后,那段文案要跟着改** —— 已在 §6.1 登记。 |
| 设置屏那一组的三格与入口 | 归设置赛道 | 见 §6.0 第 2 条:本赛道给措辞,设置赛道照抄。 |
| YOLO 识别精度、相机参数 | 归 yolo 赛道 | 与几何标定是两条链。 |
| 识别链本身:视差、参照帧、维持档、闲置停识别、指引灯亮度 | 归 vision-optimizations | 09-21 至 09-23 刚上线;本赛道只通过 `set_geometry` 给它们喂锁,一行不改(§2.1 R4)。 |

## 6. 与其它赛道的协调与共享文件

### 6.0 四条新赛道统一协调规则(2026-09-20 写定,四份 PRD 同文)

**基线**:直播 / 成长 / 设置 / 视觉四条赛道都从 develop `7a152df1` 开出。上一轮五条赛道里 4 条已并入 develop,只剩 **`feature/kiosk-go-kifu`(`bd30cc39`)未合并**,它改 `KioskApp.tsx` 的路由段(:133-150)与 `KifuPage.tsx`(顶部 import、搜索卡、列表错误块)。

**会撞的地方(按风险排序)**

1. **`KifuPage.tsx` / `KioskApp.tsx` 与未合并的 kifu 分支**:直播赛道要在 `KifuPage.tsx` 的直播那一段(:378-417)加一行入口,设置赛道要删 `KioskApp.tsx` 的 `OrientationProvider` / `RotationWrapper`(:34、:41、:202-214)。两处与 kifu 的 hunk 都不相邻,属文本冲突。**规则:先合 kifu,再合这两家**;谁后合谁负责 rebase。
2. **`GeometryContext` 的状态词(`phase` / `loaded` / `capabilities`)**:设置赛道 ST5 要在设置屏说「还没问到 / 没有摄像头」,视觉赛道 V2/V3 要改标定屏说「取消了还能沿用 / 这台盒子没有 LED」。**规则:`GeometryContext.tsx` 与 `geometryApi.ts` 归视觉赛道改,设置赛道只消费**;同一件事的措辞以视觉赛道为准,设置赛道照抄。
3. **`server.py`**:成长赛道 G2 只在 `_record_ai_game_locked` 的 `data` 字典(:1830-1844)与 `_record_platform_engine_game` 的 `data_overrides`(:3615)各加一个键,**不碰终局收尾入口 `_finish_ended_game`**(上一轮定的唯一入口);视觉赛道只改挂 `GeometryCalibrationService` 的那一段(:761-826;**在视觉分支 `a586026b` 上是 `:835-897`**,构造调用在 `:885-897`)。两处不相邻。
4. **数据库迁移**:仓里**没有 alembic**(装着包但没有 env.py / 版本链)。加列只走 `katrain/web/core/migrations.py` 的 `add_missing_columns`(在模型上加一列可空列即可,它是幂等的 `ALTER TABLE ADD COLUMN`,SQLite / PG 双兼容)。本轮只有成长赛道 G2 加一列,其余三家零迁移。
5. **i18n**:四家都只写 `t('ns:key','中文默认')`,**本轮不改任何 `.po`**(并行改 11 份必冲突)。合并完统一交 `katrain-i18n-expert`,各赛道交付时附新增 key 清单。
   **⚠️ 2026-09-23 视觉赛道核到这条已经被取代(只改了本份 PRD)**:(另:这条闸在 develop 上此刻就是红的,见 §7「i18n 闸」一行。)develop 在 09-21 合进了 `tests/web_ui/test_kiosk_i18n.py`,要求 `src/kiosk` 下**每一个** `t('key','中文')` 在 11 个语种里都有真译文(不许空、不许 TODO)。照「不改 `.po`」做,新 key 一进来这条闸就红。设置赛道实际已经各自补译(`d3b446a8`,15 key × 11 语种)。所以视觉赛道的做法是:**新 key 在本赛道内用 `katrain-i18n-expert` 补齐 11 语种**;能复用的现成 key 就复用(V4 复用 `settings:led_serial_connected`)。`.po` 是按条目追加,与别家冲突时手工合并条目即可。
6. **四图存档**:直播取屏 18 与新的直播列表屏、成长 22、设置 27、视觉 26,目录各不相同。重取前按 CLAUDE.md 跑**两次**比对排除抖动(canvas 屏抖动量级 ~4500 像素,DOM 屏 ~200)。
7. **两套构建**:四家只要碰了 `src/hooks/`、`src/api/`、`src/utils/`、`src/components/` 就必须 `npm run build` 与 `npm run build:kiosk-2d` 都绿;共享文件不许 import `src/kiosk/**`。

**合并顺序(默认)**:`kifu`(上一轮遗留) → **视觉** → **设置** → **成长** → **直播**。
理由:视觉改的是标定语义,设置屏要引用它的状态词;成长动数据库和云端,要按「先测试环境再生产」单独排期(见成长 PRD §7);直播要等 kifu 落地后才动 `KifuPage.tsx`。
例外:任一赛道里**不碰上面 1–4 条**的单个 Task 可以拆出来先合。

**每次合并前**:`git merge develop`,跑本赛道 plan 的 Global Constraints(两套构建 + `npx tsc -b` + 基线 diff),并对照本节查**语义**冲突 —— git 报「合得干净」不等于合得对。

### 6.1 本赛道会改、可能与别家重叠的文件

| 文件 | 本赛道改什么 | 可能重叠 |
|---|---|---|
| `katrain/web/core/geometry_calibration_service.py` | V1 自动重定位与 `relocate()`;V2 白名单加 `cancelled`(V3 无灯首标本轮不做) | 无(独占) |
| `katrain/vision/geometry_lock.py`(或新建 `relock.py`) | V1:按新单应重建 lock 的纯函数 | 摆谱链只读它,不改 |
| `katrain/web/api/v1/endpoints/geometry.py` | 新增 `POST /geometry/relocate` | 无 |
| `katrain/web/server.py`(:885-897,只改构造调用;`_vision_needs_frames` / `_adjust_led_brightness` 不碰) | V1:把开关接进服务构造(保留 `drift_needed=`) | **成长赛道**改的是 `:1830-1844` / `:3615`,不相邻 |
| `katrain/web/ui/src/kiosk/components/vision/GeometryCalibrationScreen.tsx` | V1-b 按钮、V2 判别位与原因、V4 措辞(V3 本轮不做,`canStart` 不动);**保留 `RAW_STREAM_SCALE` / `WARPED_STREAM_SCALE` 与 `onImageLoad` 的乘回**(§2.1) | 无 |
| `katrain/web/ui/src/kiosk/context/GeometryContext.tsx`、`src/api/geometryApi.ts` | 新增 `relocate()` 动作 | **设置赛道**只消费,不改(§6.0 第 2 条) |
| `katrain/web/ui/src/kiosk/components/game/RecalibrationModal.tsx` | **本轮不改**;但 V1-b 落地后它那句「重新标定(要清盘)」就不再是唯一出路 ⇒ 登记给**对弈赛道**(A21) | play-ai |
| `katrain/web/ui/src/kiosk/components/physical/PoseLostBanner.tsx` + 测试 | 删(Z3) | 无(零消费者) |
| `katrain/vision/tools/outer_corner_accuracy.py` | 加真帧模式 `--live`(上板清单第 1 项要用) | 无 |
| `katrain/i18n/locales/*/katrain.po` | V1-b 新增 4 个 `vision:relocate*` key,用 `katrain-i18n-expert` 补 11 语种(§6.0 第 5 条更正);V4 复用现成 key | 按条目追加,冲突时合并条目 |
| `katrain/web/ui/src/kiosk/pages/SettingsPage.tsx` | **不改**(V4 那一格设置赛道已改完) | — |
| `katrain/web/ui/src/kiosk/components/layout/GoConsoleRail.tsx` + `.test.tsx` | V4:「就绪」→「已连接」(Fan 2026-09-23 裁定) | 共享左栏,对弈 / 棋谱 / 报告等屏都在用;只改一个词 |
| smartbox `superpowers/shared/kiosk-shell/sample-go/go-kiosk.tmpl.html`(+ 重建的 `go-kiosk.html` / `go-kiosk-proto.html`) | V4 设计稿同步:`STATUS` 里 LED 那格改「已连接」;**只在 smartbox main 上本地提交,参考图不重拍** | 另一个仓;main 工作树里有别人未提交的 `vendor/*`,只 `git add` 这三个文件 |
| §2.1 R4 列的识别优化文件 | **一行不改** | vision-optimizations |

## 7. 验证方式

| 层 | 适用条目 | 做法 |
|---|---|---|
| 基线 diff(Python) | V1 V2 | 动手前 `CI=true uv run pytest tests --continue-on-collection-errors -q`,记 `^FAILED\|^ERROR` 名字集合;收尾再跑用 `comm` 比。新 worktree 先 `uv sync --extra web --extra vision`(光 `--extra web` 没有 OpenCV,视觉测试会在收集阶段全部报错,混进基线,2026-09-23 实测)。 |
| 基线 diff(前端) | 全部 | 全量 vitest 名字集合。 |
| pytest | V1 V2 | 见各条验收。重点是**两条反向闸**:`degraded` 不许沿用(V2-2)、默认不许自动重定位(V1-3)。 |
| vitest | V1-b V2 V4 | 标定屏四态(`ready` / `failed` / `cancelled` / `degraded`);左栏 LED 那格的新措辞。 |
| 结构闸 | V1 | `Scenario.RUNTIME_RECALIBRATION.allows_led()` 为假,且新路径不传 `led` —— **这是「绝不自动亮灯」那条硬规矩的代码级痕迹**,不是可选测试。 |
| 朝向闸 | V1 | V1 验收 9:四种旋转顺序与一种镜像顺序的旧锁,重建后四角顺序不变、视差 nadir 同一条边;45° 时拒绝。 |
| 识别优化回归闸 | 全部 | §2.1 R4 的文件相对 `git merge-base HEAD origin/develop` 零改动;R5 的测试原样全绿(2026-09-24 在 `a512aa6a` 上实测 362 条全过)。 |
| i18n 闸 | V1-b V4 | `tests/web_ui/test_kiosk_i18n.py` 全绿(2026-09-24 在 `a512aa6a` 上实测 12 passed;09-23 时它曾因摆谱 / 棋谱漏译的 16 个 key 红着,develop `7cc6c5d4` 已补)。另加一条按本赛道范围切的判据:`… 2>&1 \| grep -c "'vision:"` 为 0 —— 万一收尾时别的赛道又让它变红,整体结果就看不出本赛道的缺译,这一条仍然看得出。 |
| 类型 / 构建 / 格式 | 全部 | `npx tsc -b`;`npm run build` + `npm run build:kiosk-2d`;`uv run black -l 120`。 |
| 四图对比 | 屏 26(标定) | 加了按钮与说明 ⇒ **触发**。`npm run fourup` 跑两次排抖动,四张一起看并**交 Fan 确认**。 |
| 承重结构实测 | 屏 26 | 标定屏右栏是「会长的东西」(四步 + 诊断 + 说明 + 两颗键,V1-b 又多一颗):把状态造到最满(`degraded` + 诊断 + 对齐失败的原因那句)在真浏览器里量右栏可滚、页面不溢出、动作区不被挤出视口;再按「塌陷在最空状态下量」量一次 `ready` 且无诊断那一态。jsdom 不作数。 |
| **上板清单** | V1 V2 V4 | 产出 `board-checklist.md`(§3 V5),由 Fan 安排执行。RK3562 2G,**一次只跑一家**;测完把结果写回清单,不要只在对话里说。 |

### 上板清单(要点,细则见 `board-checklist.md`)

1. **满盘外框精度**:空盘先跑一次 LED 13 点标定当真值,之后盘和相机都不动;空盘、约 60 子各跑一次 `python -m katrain.vision.tools.outer_corner_accuracy --live http://127.0.0.1:8081`(真值取 `/api/v1/geometry/layout` 的 LED 角点,帧取 `/api/v1/geometry/stream`),判据每次都 **< 0.12 格**。
   **2026-09-21 更正**:原稿写的是不带参数跑这个工具 —— 它只渲染**合成**棋盘、从不读相机,在板上跑和在 Mac 上跑结果一样,量不到真盘。真帧模式由 plan Task 8b 补上;不带 `--live` 的结果只是下界,不能当这道闸。
2. **碰盘恢复**:对局中推动棋盘 ~1 格,`AUTO_RELOCATE_ON_DRIFT=True` 下屏上不该进标定台,继续落子识别不串位。2026-09-23 补三条判据:① 日志 `vision parallax auto: nadir=(…)` 在重定位前后是**同一条边**(这台盒子是 col 18 那条,nadir ≈ (19.61, 9.0));② 从推盘到新锁生效这段窗口里,**棋谱里没有进任何一手幻影落子**(§2.1 R3:不挂起识别的代价在这里量);③ 重定位后至少 30 手,`board delta:` 行里 `@<距离>` 的中位数照实记下,与同一台盒子在 LED 锁下的数(09-22 那局 0.150 格)并排写。**这个数只记录,不当开关判据**:30 手的中位数自己就有噪声。
3. **人工出口**:`degraded` 态按「对齐外框」,盘上有子也能恢复到 `ready`;nadir 日志同上一条 ①。
4. **无灯首标**(⛔ V3 本轮不做,这一项留给以后):拔掉 LED 串口,空盘跑一次 `empty_board_autocal`,能到 `ready` 且识别正常;**朝向**:在一个不对称的点(如 3-4)摆一颗子,屏上必须是同一个点。
5. **取消后沿用**:标定跑到一半取消,「沿用上次标定」可按且恢复识别。
6. **LED 目视 bring-up**(可选):固件 `SCAN` 命令逐颗点亮,人眼确认 361 颗都亮、颜色对。
