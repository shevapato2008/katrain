# 围棋 kiosk · 视觉 / 标定 / 实体盘 赛道 PRD(kiosk-go-vision)

- 日期:2026-09-20
- 分支 / worktree(**已创建 2026-09-21**):`feature/kiosk-go-vision` @ `/Users/fan/Repositories/katrain-kiosk-go-vision`,基线 develop `7a152df1`
- 输入:2026-09-14「围棋 kiosk 缺口账本」视觉模块七条(V1–V6、N16)
- **本文所有行号都在 develop `012e2a04` 上重核过(2026-09-20)**。账本成文于 `6f7dc629`,其后 develop 在视觉这一块前进很多(`geometry_calibration_service.py` +396 行、`led_geometry_calibrator.py` +314 行、`VisionSyncOverlay.tsx` 重写、新增 `visionRecovery.ts`)——**N16 已被修掉**(见 §2),其余六条逐行复核后仍然成立。 **2026-09-21 基线移到 develop `7a152df1`**(其后 43 个提交是视觉识别稳定性与退出兜底):本文引用的文件里只有 `server.py` 行号漂移(+1),已按新基线改;这 43 个提交改的是识别链(`move_detector` / `sync` / `worker`),不碰本文的几何标定段落。

---

## 1. 背景与目标

实体盘这条链今天在盒上是能跑的:13 点 LED 标定、沿用上次标定、标定中挂起识别 worker、漂移监视、落子识别与恢复对话框、LED 引导。2026-09 那一轮还把标定期间的卡顿(「卡在 N/13」)和 board_lost 的文案都修了。

剩下的问题集中在**一件事**:**盘被碰动之后没有回得来的路**。

1. **中盘碰一下盘,这局在实体盘上基本就接不下去了。** 漂移监视判定漂移 ⇒ `phase` 变 `degraded` ⇒ 识别几何被清掉 ⇒ 守卫把整个对局屏换成标定台 ⇒ 而「重新标定」走的是 **13 点 LED 流程,要求空盘**。盘上有子就抛错 —— 也就是说,要恢复得先把这局的棋子全部拿掉。
   库里为这件事写好的东西**一件都没接上**:`CalibrationSelector` 的 `RUNTIME_RECALIBRATION` 场景(只用外框、绝不亮灯)、`OuterCornerStrategy`(`works_on_crowded_board = True`)、`DriftStateMachine` / `RotationAwareDrift` —— 生产代码里唯一的调用方是**摆谱采集**(`baipu_capture.py:241`),而它算出来的 `M` 只写进采集 manifest,不回写识别用的几何。
2. **标定跑到一半误触「取消」,上一次的标定也作废了。** 取消后 `phase = cancelled`,而 `confirm_existing` 只接受 `required` / `failed` ⇒ 「沿用上次标定」变灰,屏上还**不说为什么**(`reuseBlockedWhy` 在 `cancelled` 时是 `null`)。当初裁定「不给取消配确认弹层」的理由是「取消是廉价且可逆的」——这个前提不成立。
3. **没有 LED 的盒子做不了第一次标定。** `start()` 第一句就是 `if self.led is None: raise ValueError("LED is required for geometry calibration")`,前端 `canStart` 也要求 `ledReady`。而 `calibration_registry.py:27` 为 `INITIAL_SETUP` 配的第二条路 `empty_board_autocal`(无灯、空盘、全网格)**生产零调用**。
4. **「LED 就绪」只表示串口打开了。** `led_ready` 就是 `LedService._connected`(`led_service.py:183-184`),灯带某一段坏了屏上照样绿。

这一轮要让盒上用户得到三件事:
1. 盘被碰动后,**不清盘**也能把几何找回来(先自动试,不行再给一颗用户按的「对齐外框」——**永远不自动亮灯**,那是 Fan 的硬规矩)。
2. 误触取消之后,「沿用上次标定」还能按,而且屏上说得出为什么能按 / 不能按。
3. 没有 LED 的盒子也能完成第一次标定(无灯空盘自动标定)。

另外两件(LED 自检、真机验收回填)本轮只做能做的那部分:把「LED 就绪」这句话改准,以及把四份文档里散着的真机验收项收成**一份可执行的上板清单**。

## 2. 已经做完、不要动的

| 内容 | 出处 |
|---|---|
| **N16 已修**:board_lost 对话框不再指向那条早已不存在的「横幅中的『重新定位』」,改成「看一下摄像头有没有被挡住、棋盘有没有被挪动;挪动过的话要重新标定」 | `VisionSyncOverlay.tsx:305`(`939165a4`) |
| 标定期间挂起 / 恢复识别 worker(`on_suspend` / `on_resume`),失败或取消时把旧几何推回去 | `geometry_calibration_service.py:96-104`、`:582-592` |
| 曝光收敛与收敛后再量的顺序、失败诊断分类(`low_signal` / `ambiguous_blobs` / …) | `geometry_calibration_service.py:476-510` |
| 标定发布的原子性:先暂存、`_before_publish` 线性化取消、失败回滚(回滚失败则作废运行时几何) | `:422-474`、`:556-576` |
| 漂移监视(`GeometryDriftMonitor`,Sobel + phaseCorrelate,连续 3 帧超阈值才判漂移) | `katrain/vision/geometry_drift.py` |
| 识别落子的恢复状态机(`visionRecovery.ts`)与 `VisionSyncOverlay` 重写 | `visionRecovery.ts`、`VisionSyncOverlay.tsx` |
| **LED 绝不为几何自动点亮**(Fan 硬规矩),结构上由 `Scenario.allows_led()` 保证 | `calibration_strategy.py:26-33`;屏上那句常驻提示 `GeometryCalibrationScreen.tsx:463` |
| 标定屏的四步进度、三格状态、「没读到之前写 —」 | `GeometryCalibrationScreen.tsx:296-331` |

---

## 3. 需求条目(本轮做)

### V2 · 误触「取消标定」后,上一次的标定也用不了了 —— P1

- **现象**:标定运行中按「取消标定」⇒ `phase = cancelled` ⇒ 「沿用上次标定」变灰,**屏上不说原因**;实体盘路由(含正在下的那局)一律被标定台拦着,只能清空棋盘重跑分钟级的 LED 标定,或者重启服务。
- **根因(已核实)**:
  - `geometry_calibration_service.py:193` `if self._status["phase"] not in {"required", "failed"}: raise ValueError(...)`。
  - `GeometryCalibrationScreen.tsx:335` `canReuse = (phase === 'required' || phase === 'failed') && …`;`:336-338` 的 `reuseBlockedWhy` 只覆盖「标定进行中 / 摄像头未连接 / 这一局已经在用这次标定」,`cancelled` 时是 `null`。
  - 服务端其实**没丢东西**:`current_lock` 还在,`on_resume` 也把识别恢复到了旧几何(`:582-592`)——缺的只是一个把 `phase` 拉回 `ready` 的入口。
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
  - `geometry_calibration_service.py:628-646` `_apply_drift`:判定漂移就 `phase = "degraded"` + `on_degraded()`(`server.py:784-791` 清掉运行时几何),**没有任何恢复尝试**。
  - 标定服务固定用 `calibrator_factory=LedGeometryCalibrator`(`:82`),**不经 `CalibrationSelector`**;`build_default_selector()` 的唯一生产调用方是 `baipu_capture.py:248`,而那里算出的 `M` 只进采集 manifest。
  - `OuterCornerStrategy` 本来就是为这件事写的:`requires_led = False`、`works_on_crowded_board = True`,用的是**外框**(棋子永远挡不住外框)。
- **期望**:两条路,合起来才闭环。
  - **(a) 自动静默重定位**:漂移判定成立时,先跑一次 `Scenario.RUNTIME_RECALIBRATION`(策略表里只有 `outer_corner`,**结构上不可能亮灯**)。成功 ⇒ 用新的单应重建 lock(重算 `corners` / `points`,**保留 `baseline`**)、持久化、`on_success` 推给识别 worker、`phase` 留在 `ready`、漂移基准重置;失败 ⇒ 照今天降级成 `degraded`,并把失败原因写进 `metrics`。
  - **(b) 用户按的「对齐外框」**:`degraded` / `cancelled` / `failed` 三态下,标定屏给一颗「对齐外框(不亮灯,盘上有子也行)」,走 `Scenario.MANUAL_FALLBACK` 的 `outer_corner`(**LED 那一支本轮不接** —— 它要求空盘,而这颗键存在的理由正是盘上有子)。它是自动那条路失败后的人工出口。
  - **(c) 精度闸**:外框法在**满盘**下的真机精度没有人量过。`outer_corner_accuracy.py` 定的判据是误差 < **0.12 格**。所以:
    - 自动那条路(a)的开关**默认关**,常量写在源码里(`AUTO_RELOCATE_ON_DRIFT = False`)并在注释里点名它等的是哪一条上板闸;
    - 用户按的那条(b)**默认开** —— 它是用户主动发起的,而且今天的替代品是「清盘重来」,更差;
    - 上板闸通过后,在**同一次改动**里把常量翻成 `True` 并补一条测试。
- **验收**:
  1. pytest:注入一个假 selector,漂移成立且 `auto_relocate=True` 时不进 `degraded`,`phase` 仍 `ready`,`on_success` 被调用一次,持久化被调用一次。
  2. pytest:假 selector 返回 `ok=False` 时,行为与今天**逐字相同**(`degraded` + `on_degraded`),且 `metrics` 里能看到失败原因。
  3. pytest:`AUTO_RELOCATE_ON_DRIFT = False`(默认)时,漂移仍然直接 `degraded` —— **这一条钉住「默认关」**,免得闸没过就悄悄上线。
  4. pytest:`relocate()` 在 `degraded` / `cancelled` / `failed` 三态都能跑,且**不接受空盘要求**(盘上有子照跑);运行中(`active`)调用抛 `CalibrationBusy`。
  5. pytest(**结构闸**):`Scenario.RUNTIME_RECALIBRATION.allows_led()` 为假,且本轮新增的两条路径都没有把 `led` 传进 `CalibrationContext`。
  6. pytest:重建 lock 的纯函数 —— 给一个已知 lock 与一个平移过的 `M`,重算出的 `points` 与直接用新 `corners` 走 `grid_points_from_corners` 的结果一致,`baseline` 原样保留。
  7. vitest:`degraded` 态标定屏出现「对齐外框」键,点它调 `/api/v1/geometry/relocate`;成功后屏回到 `ready`,失败时屏上给原因。
  8. **上板**:见 §7「上板清单」第 1–3 项(满盘外框精度、对局中碰盘恢复、恢复后识别不串位)。
- **依赖**:上板闸(精度)。代码本身不依赖上板即可合并(默认关)。

### V3 · 没有 LED 的盒子做不了第一次标定 —— P2

- **现象**:LED 串口没起来(或这台机器根本没装灯带)时,「重新开始标定」按不了(`canStart` 要 `ledReady`),后端也会直接抛错。磁盘上已经有 `geometry_lock.npz` 的盒子还能「沿用上次标定」,**第一次**标定则完全没路。
- **根因(已核实)**:`geometry_calibration_service.py:126` `if self.led is None: raise ValueError("LED is required for geometry calibration")`;`GeometryCalibrationScreen.tsx:334` `canStart = cameraReady && ledReady && …`;`calibration_registry.py:27` 给 `INITIAL_SETUP` 配的 `empty_board_autocal` 生产零调用。
- **期望**:
  - `start()` 在**没有可用 LED** 时不再抛错,改走 `Scenario.INITIAL_SETUP` 的选择器 —— `led_anchor` 会因 `is_applicable`(需要 `led`)自行让位,落到 `empty_board_autocal`(无灯、空盘、产出完整 lock 含 `baseline`)。空盘仍然是硬要求(`empty_confirmed`),这一条不放开。
  - 前端 `canStart` 去掉 `ledReady`;没有 LED 时屏上说明白:「这台盒子没有灯带,用无灯方式标定:精度略低,盘上不能有子」。LED 那一格仍写「未连接」(那是事实)。
  - **有 LED 时行为一个字不变**(13 点流程仍是首选、仍是 golden reference)。
- **验收**:
  1. pytest:`led=None` 时 `start(empty_confirmed=True)` 不抛,跑完后 `phase='ready'` 且 lock 来自 `empty_board_autocal`。
  2. pytest:`led=None` 且 `empty_confirmed=False` 时仍抛 `ValueError`(空盘要求不放开)。
  3. pytest:`led` 可用时仍走 `LedGeometryCalibrator`(**回归闸**:13 点流程没有被顺手换掉)。
  4. vitest:`ledReady=false` 时「重新开始标定」可点,且屏上有那句无灯说明;`ledReady=true` 时文案不出现。
- **依赖**:无灯自动标定的真机精度**未验**⇒ 列进上板清单第 4 项;但它今天的替代品是「完全不能标定」,所以先上,不设开关。

### V4(缩范围)· 「LED 就绪」这句话不准 —— P3

- **事实**:`led_service.py:183-184` `is_connected()` 返回的是 `self._connected`,也就是**串口开没开**;`/api/v1/led/status` 同源。灯带某一段坏了、或者 UR 段那个硬件故障没修,屏上照样是绿色「就绪」。
- **本轮只做**:把话说准 —— 标定屏与设置屏那一格从「LED · 就绪 / 未连接」改成「LED · **串口已连接** / 未连接」,并在标定屏那段说明里加一句「这一格只说串口通了,不代表每颗灯都亮」。
- **本轮不做**:相机逐颗扫描的真自检(PRD `sbc-baipu-led-guide/prd.md:174` 那条「命中恰好 361 个互异交叉点」)。理由:它要人在场、要空盘、要一两分钟,而且 UR 段的硬件修复状态两个仓里都看不出来 —— **先把话说准,再谈自检**。固件侧已有 `SCAN` 命令可做人工目视 bring-up,记在上板清单第 6 项。
- **验收**:`rg "LED.*就绪" katrain/web/ui/src` 只剩改过的措辞;vitest 两屏各一条。

### V5 · 真机验收项散在四份文档里,一条都没回填 —— P3(本轮产出一份清单)

- **事实(已核实)**:`kiosk-physical-play/acceptance-checklist.md:31-44` 的 14 行结果列全空(仅 07-02 一次提交);`kiosk-golaxy-physical-play` 的 PRD 状态仍是「待 rk3562 真机验证」,plan Task 14 三项与 `kiosk-play-golaxy` §14 D1–D4 都没勾;`2026-08-20` 对齐计划 Task 20 Step 6 明写「上板走查没做」。清单本身也**过期了两处**:第 3④ 项引用的 `PoseLostBanner` 已被 `RecalibrationModal` 取代;「SET_GEOMETRY 子进程缺失」在盒上走 `InProcessAdapter`,不成立。
- **本轮只做**:把四份里**仍然成立**的真机项收成一份 `board-checklist.md`(本赛道目录下),按 Fan 的「RK3562 2G,一次只跑一家」写成可串行执行的步骤,并把本轮 V1 / V3 的闸加进去。过期的两项删掉并写明为什么。
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

## 6. 与其它赛道的协调与共享文件

### 6.0 四条新赛道统一协调规则(2026-09-20 写定,四份 PRD 同文)

**基线**:直播 / 成长 / 设置 / 视觉四条赛道都从 develop `7a152df1` 开出。上一轮五条赛道里 4 条已并入 develop,只剩 **`feature/kiosk-go-kifu`(`bd30cc39`)未合并**,它改 `KioskApp.tsx` 的路由段(:133-150)与 `KifuPage.tsx`(顶部 import、搜索卡、列表错误块)。

**会撞的地方(按风险排序)**

1. **`KifuPage.tsx` / `KioskApp.tsx` 与未合并的 kifu 分支**:直播赛道要在 `KifuPage.tsx` 的直播那一段(:378-417)加一行入口,设置赛道要删 `KioskApp.tsx` 的 `OrientationProvider` / `RotationWrapper`(:34、:41、:202-214)。两处与 kifu 的 hunk 都不相邻,属文本冲突。**规则:先合 kifu,再合这两家**;谁后合谁负责 rebase。
2. **`GeometryContext` 的状态词(`phase` / `loaded` / `capabilities`)**:设置赛道 ST5 要在设置屏说「还没问到 / 没有摄像头」,视觉赛道 V2/V3 要改标定屏说「取消了还能沿用 / 这台盒子没有 LED」。**规则:`GeometryContext.tsx` 与 `geometryApi.ts` 归视觉赛道改,设置赛道只消费**;同一件事的措辞以视觉赛道为准,设置赛道照抄。
3. **`server.py`**:成长赛道 G2 只在 `_record_ai_game_locked` 的 `data` 字典(:1830-1844)与 `_record_platform_engine_game` 的 `data_overrides`(:3615)各加一个键,**不碰终局收尾入口 `_finish_ended_game`**(上一轮定的唯一入口);视觉赛道只改挂 `GeometryCalibrationService` 的那一段(:761-826)。两处不相邻。
4. **数据库迁移**:仓里**没有 alembic**(装着包但没有 env.py / 版本链)。加列只走 `katrain/web/core/migrations.py` 的 `add_missing_columns`(在模型上加一列可空列即可,它是幂等的 `ALTER TABLE ADD COLUMN`,SQLite / PG 双兼容)。本轮只有成长赛道 G2 加一列,其余三家零迁移。
5. **i18n**:四家都只写 `t('ns:key','中文默认')`,**本轮不改任何 `.po`**(并行改 11 份必冲突)。合并完统一交 `katrain-i18n-expert`,各赛道交付时附新增 key 清单。
6. **四图存档**:直播取屏 18 与新的直播列表屏、成长 22、设置 27、视觉 26,目录各不相同。重取前按 CLAUDE.md 跑**两次**比对排除抖动(canvas 屏抖动量级 ~4500 像素,DOM 屏 ~200)。
7. **两套构建**:四家只要碰了 `src/hooks/`、`src/api/`、`src/utils/`、`src/components/` 就必须 `npm run build` 与 `npm run build:kiosk-2d` 都绿;共享文件不许 import `src/kiosk/**`。

**合并顺序(默认)**:`kifu`(上一轮遗留) → **视觉** → **设置** → **成长** → **直播**。
理由:视觉改的是标定语义,设置屏要引用它的状态词;成长动数据库和云端,要按「先测试环境再生产」单独排期(见成长 PRD §7);直播要等 kifu 落地后才动 `KifuPage.tsx`。
例外:任一赛道里**不碰上面 1–4 条**的单个 Task 可以拆出来先合。

**每次合并前**:`git merge develop`,跑本赛道 plan 的 Global Constraints(两套构建 + `npx tsc -b` + 基线 diff),并对照本节查**语义**冲突 —— git 报「合得干净」不等于合得对。

### 6.1 本赛道会改、可能与别家重叠的文件

| 文件 | 本赛道改什么 | 可能重叠 |
|---|---|---|
| `katrain/web/core/geometry_calibration_service.py` | V1 自动重定位与 `relocate()`;V2 白名单加 `cancelled`;V3 无灯首标 | 无(独占) |
| `katrain/vision/geometry_lock.py`(或新建 `relock.py`) | V1:按新单应重建 lock 的纯函数 | 摆谱链只读它,不改 |
| `katrain/web/api/v1/endpoints/geometry.py` | 新增 `POST /geometry/relocate` | 无 |
| `katrain/web/server.py`(:761-826) | V1:把 selector 与开关接进服务构造 | **成长赛道**改的是 `:1830-1844` / `:3569`,不相邻 |
| `katrain/web/ui/src/kiosk/components/vision/GeometryCalibrationScreen.tsx` | V1-b 按钮、V2 判别位与原因、V3 `canStart` 与说明、V4 措辞 | 无 |
| `katrain/web/ui/src/kiosk/context/GeometryContext.tsx`、`src/api/geometryApi.ts` | 新增 `relocate()` 动作 | **设置赛道**只消费,不改(§6.0 第 2 条) |
| `katrain/web/ui/src/kiosk/components/game/RecalibrationModal.tsx` | **本轮不改**;但 V1-b 落地后它那句「重新标定(要清盘)」就不再是唯一出路 ⇒ 登记给**对弈赛道**(A21) | play-ai |
| `katrain/web/ui/src/kiosk/components/physical/PoseLostBanner.tsx` + 测试 | 删(Z3) | 无(零消费者) |
| `katrain/i18n/locales/*/katrain.po` | **不改** | 全部 |

## 7. 验证方式

| 层 | 适用条目 | 做法 |
|---|---|---|
| 基线 diff(Python) | V1 V2 V3 | 动手前 `CI=true uv run pytest tests --continue-on-collection-errors -q`,记 `^FAILED\|^ERROR` 名字集合;收尾再跑用 `comm` 比。新 worktree 先 `uv sync --extra web`。 |
| 基线 diff(前端) | 全部 | 全量 vitest 名字集合。 |
| pytest | V1 V2 V3 | 见各条验收。重点是**两条反向闸**:`degraded` 不许沿用(V2-2)、默认不许自动重定位(V1-3)。 |
| vitest | V1-b V2 V3 V4 | 标定屏四态(`ready` / `failed` / `cancelled` / `degraded`)× 有无 LED。 |
| 结构闸 | V1 | `Scenario.RUNTIME_RECALIBRATION.allows_led()` 为假,且新路径不传 `led` —— **这是「绝不自动亮灯」那条硬规矩的代码级痕迹**,不是可选测试。 |
| 类型 / 构建 / 格式 | 全部 | `npx tsc -b`;`npm run build` + `npm run build:kiosk-2d`;`uv run black -l 120`。 |
| 四图对比 | 屏 26(标定) | 加了按钮与说明 ⇒ **触发**。`npm run fourup` 跑两次排抖动,四张一起看并**交 Fan 确认**。 |
| 承重结构实测 | 屏 26 | 标定屏右栏是「会长的东西」(四步 + 诊断 + 说明 + 两颗键,V1-b 又多一颗):把状态造到最满(`degraded` + 诊断 + 无灯说明)在真浏览器里量右栏可滚、页面不溢出、动作区不被挤出视口;再按「塌陷在最空状态下量」量一次 `ready` 且无诊断那一态。jsdom 不作数。 |
| **上板清单** | V1 V3 V4 | 产出 `board-checklist.md`(§3 V5),由 Fan 安排执行。RK3562 2G,**一次只跑一家**;测完把结果写回清单,不要只在对话里说。 |

### 上板清单(要点,细则见 `board-checklist.md`)

1. **满盘外框精度**:摆到 ~60 子,跑 `python -m katrain.vision.tools.outer_corner_accuracy`,判据 **< 0.12 格**。
2. **碰盘恢复**:对局中推动棋盘 ~1 格,`AUTO_RELOCATE_ON_DRIFT=True` 下屏上不该进标定台,继续落子识别不串位。
3. **人工出口**:`degraded` 态按「对齐外框」,盘上有子也能恢复到 `ready`。
4. **无灯首标**:拔掉 LED 串口,空盘跑一次 `empty_board_autocal`,能到 `ready` 且识别正常。
5. **取消后沿用**:标定跑到一半取消,「沿用上次标定」可按且恢复识别。
6. **LED 目视 bring-up**(可选):固件 `SCAN` 命令逐颗点亮,人眼确认 361 颗都亮、颜色对。
