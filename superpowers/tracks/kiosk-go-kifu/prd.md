# 围棋 kiosk · 棋谱模块（kiosk-go-kifu）需求文档

- 日期：2026-09-14
- 分支 / worktree：`feature/kiosk-go-kifu` @ `/Users/fan/Repositories/katrain-kiosk-go-kifu`（基于 develop `6f7dc629`）
- 输入：2026-09-14 三轮调研条目包 `kiosk-go-kifu.json`（K1 K2 K3 N9 N10 S5 V5 L1），本文逐条回源码核实过；行号以 `6f7dc629` 为准。
- 最高优先级口径：**Fan 2026-09-14 纠正 —— 摆谱的「拍照」只是为了收集 YOLOv11 训练数据，上线以后不需要拍照功能。**

---

## 1. 背景与目标

棋谱模块在盒上是 Dock 第三项「棋谱」（屏 15 `KifuPage`），下挂屏 16 棋谱详情（`KifuDetailPage`）和屏 17 摆谱进行中（`BaipuSessionPage`）。三屏 8 月已按共享外壳重画，但**摆谱这条路在盒上走不完**：每一次摆谱结束（返回 / 退出 / 完成）都把人送进一个没有任何出口的旧页 `/kiosk/baipu`，只能重启。更根本的是，摆谱现在整条挂在「拍照采集」上 —— 盒子为了几何标定总是带着 `--capture-camera 0` 启动，于是每按一次「确认落子」都真拍一张 1080p 照片写盘、要求几何锁有效、要求灯严格点亮，任何一环失败这一手就推进不了；进摆谱之前还要先标定摄像头。而按 Fan 的纠正，上线版摆谱根本不该拍照。

**这一轮要让盒上用户得到的：** 从棋谱详情或导入 SGF 进摆谱 → 灯指一手、人摆一手、按一下确认 → 摆完或中途退出都回到棋谱屏；不需要摄像头、不拍照、不写盘；9/13 路的谱在进门处就被如实拦下；断网时棋谱库说「要联网」而不是「没搜到」。拍照采集保留在一个默认关的采集模式开关后面，供 YOLO 训练数据采集用。

## 2. 已经做完、不要动的

- 屏 15/16/17 已按共享外壳重画（scope §22、§9），版式、承重闸（`kiosk-shell-scroll.spec.ts` 摆谱三条）、四图存档 `visual/17-baipu` 都在。本轮只改文案、判别位与出口，**不重排版式**。
- 屏 17 七条裁定（scope §22 D1–D7）：撤沉浸、退出二次确认、LED 健康点由「重新点灯」兼任、相机点删、「虚手」不做、「完成」常驻但摆完前灰、玩家卡删、盘用 `GoBoardSvg` + `replayBaipuSteps`（前端是 `steps[]` 的笨播放器，不算提子）。
- 409 分型已做（`a8eb0a6e`，2026-08-25）：`baipuApi.ts:73-78` 的 `BaipuCaptureErrorReason`，屏上几何那一种说「去设置里重新标定」。
- 屏 16 逐手回放、「去研究」深链 `?kifu_id=&analyze=1&from=kifu`、屏 15 搜索开关 / 「共 N 局」真数据 / 继续摆谱 / 最近摆过 / 直播块断网整块不渲染，均已实现并有单测。
- LED 颜色真值：黑→红 `#ff3b30`、白→绿 `#34c759`、提子→蓝 `#2f6fff`（`kiosk/constants/ledColors.ts`），屏上图例与盘上候选圈同色。LED 行列 → 灯珠索引是公式 LUT，**不依赖摄像头标定**。

## 3. 需求条目

### K1 · P0 · 摆谱结束后落进无出口的死页

**现象（已核实，比条目包多一处入口）：** `/kiosk/baipu`（`BaipuListPage.tsx`，7 月 MUI 旧皮）不在 Dock 词典里 ⇒ `dockLevelOf` 判 2（`shell/dockRoutes.ts:61-64`）⇒ 无 Dock、顶栏无主页键（`KioskLayout.tsx:55,58`），页面本身也没有页控条或任何返回（全文件唯一 `navigate` 在 `:116` 进会话）。送人进这一页的有**五处**：

| 位置 | 触发 |
|---|---|
| `BaipuSessionPage.tsx:334`、`:350` | 读谱失败 / 读谱中，页控条「← 棋谱」 |
| `BaipuSessionPage.tsx:554` | 摆完后「完成」 |
| `BaipuSessionPage.tsx:622` | 退出确认里的「退出」 |
| `KifuPage.tsx:229` | 屏 15「摆到实体盘」卡 |
| `TutorialCategoriesPage.tsx:192` | 屏 23 课程为空时「去摆谱」卡（**条目包漏了这一处**） |

设计稿里没有这一屏：稿子屏 15 注释写明「原来的『棋谱 / 摆谱 / 直播』三项收成一项」「『摆到实体盘』和『导入 SGF』进的是同一条摆谱流程，只是谱从哪儿来不一样」。它的选谱、预览、最近摆过三件事已分别被屏 15 搜索、屏 16 详情、屏 15「最近摆过」取代。

**期望：**
- 摆谱屏四处出口一律回 `/kiosk/kifu`（与返回键上写的「棋谱」一致）。
- 屏 15「摆到实体盘」卡展开名局搜索（选一局 → 屏 16 →「摆到实体盘」），不再跳转。
- 屏 23「去摆谱」卡去 `/kiosk/kifu`。
- `/kiosk/baipu` 路由保留为重定向到 `/kiosk/kifu`（旧链接不再落空），`BaipuListPage.tsx` 删除（不可达的第二套选谱实现）。

**验收：**
- 从屏 16 进摆谱，按页控条「← 棋谱」→ 退出确认「退出」，URL 为 `/kiosk/kifu`，Dock 可见；摆完按「完成」同样落在 `/kiosk/kifu`。
- 直接访问 `/kiosk/baipu` 落在 `/kiosk/kifu`。
- 屏 15 点「摆到实体盘」后搜索区（`data-testid="kifu-search"`）展开并发出 `page_size: 6` 的列表请求；屏 23「去摆谱」导航到 `/kiosk/kifu`。
- `rg -n "'/kiosk/baipu'" katrain/web/ui/src` 在非测试源码里零命中（`baipu/session/` 前缀除外）。
- 盒上（board 模式、token=null）路径与桌面相同：这几处都是纯前端导航，不读 token，按上面三条在盒上各走一遍即可。**盒上部署的必须是 `npm run build:smartbox-kiosk-2d` 的严格包**（盒子是 `KATRAIN_BOX_SSO=1`；`build:kiosk-2d` 是非严格包，`smartbox-software/provisioning/README.md:359-361` 明写不得部署到这类设备）。

**依赖与卡点：** 纯前端。改到 `KioskApp.tsx` 路由表（与 tsumego 赛道 T9 同文件）。

### K2 · P2 · 9/13 路的谱能进只认 19×19 灯阵的摆谱

**现象（已核实）：** 屏 16「摆到实体盘」只在没读到谱时灰（`KifuDetailPage.tsx:179-187`，不看路数）；屏 15「导入 SGF」读完文件直接开摆（`KifuPage.tsx:150-161`）；摆谱屏照单全收 `resp.board_size`（`BaipuSessionPage.tsx:159`），再把行列原样发给 19 路灯（`:238`）。后端 `_canon_point` 按谱自身路数换算（`katrain/core/baipu.py:39-42,70`），13 路谱会亮在实体盘左上角 13×13 区域，而 `run_capture` 还把期望盘面写死成 19（`baipu_capture.py:405,424`）。只有要删掉的 `BaipuListPage` 过滤过 19 路。现实里最可能触发的是导入本地 9/13 路 SGF（名局库几乎全是 19 路）。

**期望：**
- 摆谱屏是所有入口的唯一汇合点：读谱后 `board_size !== 19` 即进错误态，说清「这是 N 路的谱，摆不了 / 实体盘和灯都是 19 路的」，不点任何灯；同时把这份谱从「最近摆过」和本地缓存里拿掉（否则棋谱屏会留一颗点了还是摆不了的「接着摆」）。
- 屏 16「摆到实体盘」对非 19 路灰掉，原因写「这是 N 路的谱 —— 实体盘只摆得了 19 路」。

**验收：**
- 摆谱屏收到 `board_size: 13` 的读谱结果：屏上出现「这是 13 路的谱，摆不了」，`LedAPI.point` 零调用，`localStorage` 里 `baipu:recent` 不再含该 id、`baipu:sgf:<id>` 被删；页控条返回 `/kiosk/kifu`。
- 屏 16 读到 13 路谱时「摆到实体盘」为 disabled，`title` 含「13 路」。
- 19 路谱行为不变（现有 e2e 与单测照绿）。

**依赖与卡点：** 纯前端。已知不处理：非方形 SGF（`SZ[19:13]`）后端只回 `board_x`，会通过检查——名局库与常见导入里没有这种谱，记录不做。

### K4 · P0（新，来自 Fan 2026-09-14 纠正）· 上线版摆谱不拍照

**现状（逐项核实）：**

1. 盒子的 systemd drop-in（`smartbox-software/provisioning/systemd/smartbox-katrain.service.d/20-vision-led.conf`）带 `--capture-camera 0 --capture-resolution 1920x1080`——几何标定服务只在采集服务存在时才建（`server.py:686-728`），所以这个参数盒上必给 ⇒ `app.state.capture` 在盒上**恒非空**（`server.py:653-658`），`/api/v1/baipu/capture` 在盒上是活的。
2. 每按一次「确认落子」= `BaipuAPI.capture`（`BaipuSessionPage.tsx:185-208`）→ `run_capture`：几何锁为空回 409（`endpoints/baipu.py:107-109`，漂移失效会把它置空 `server.py:695-701`）；下一手的灯 `strict=True` 失败回 409（`baipu_capture.py:437-443`）；取帧 + `imwrite` 1080p 帧、矫正图与叠加图到 `~/.katrain/baipu_captures/<game>/`（`:455-481`，`_write_warp_artifacts` `:290-313`）；`auto` 模式每手还跑一次外框几何（`:421-433`）。任何失败 ⇒ `k` 不推进（`BaipuSessionPage.tsx:196`）⇒ 这一手摆不下去。开局还额外拍一张空盘帧（`:211-225`）。
3. 路由 `baipu/session/:source` 外面套着 `PhysicalBoardGuard sub="摆谱要先让摄像头看清盘面"`（`KioskApp.tsx:145`）：服务每次重启后 `session_calibrated=false`（`geometry_calibration_service.py:60-67`），不先标定就进不了摆谱——而上线版摆谱只用灯。
4. 屏上文案围着拍照写：页控条「已采集 {f} 帧」（`:403`）、折叠块「摄像头 · 这一手要采一帧 / 手不要在盘上 / 已采集 N 帧 / 最近保存」（`:463-498`）、「正在拍照，请勿伸手」遮罩（`:562-569`）、摆完「采到 {f} 帧」（`:440`）、接着摆弹窗「重新开始会覆盖已经采过的帧」（`:575`）、确认键图标 `camera`（`:523,530`）、拍完快门声（`:203`）。
5. 已有的「不拍照」分支：`/capture` 回 404 时前端判 `disabled` 并直接推进（`baipuApi.ts:111`，`BaipuSessionPage.tsx:197,205`）——但盒上永远走不到（第 1 条），而且屏上仍是整套拍照文案。

**期望（推荐方案，本轮落地）：**
- 服务端加采集模式开关：CLI `--baipu-collect` / 环境变量 `KATRAIN_BAIPU_COLLECT`，**默认关**。关着时 `/baipu/capture` 一律 404（即使采集服务存在）；新增 `GET /api/v1/baipu/mode` → `{"collect": bool}`，`collect` = 采集服务存在 **且** 开关打开。
- 前端进摆谱先问 `mode`：问不到（旧后端、网络错、非 200、3 秒内没问完——含连接挂着和 body 读不完）一律按 `collect=false`——**不知道就不拍照**；超时之后才回来的结果丢掉，不在摆谱途中把页面切到采集态。
- 上线态（`collect=false`）：不套 `PhysicalBoardGuard`（唯一例外：**标定线程正在后台跑**时——`geometry/status` 的 phase 属于 `waiting_empty / dark_reference / flashing_corners / verifying / building_baseline`——先显示标定进度与「取消标定」，跑完或取消后直接进摆谱；棋盘状态**还没读到过**（刷新直接进这条 URL 时 `GeometryProvider` 的初值就是 `required`）时也不挂摆谱屏，只给「正在检查棋盘状态」和返回键。标定屏的返回键不取消标定，而摆谱屏一挂就点灯、`/led/point` 先 CLEAR 再点，与标定逐个锚点的 clear→拍→点亮→拍互相冲掉灯；今天是守卫顺带挡住的）；「确认落子」/「已移除 N 子」只推进，不发 `/capture`、不拍开局帧、不响快门；页控条只写「第 i / n 手」；折叠块换成「灯 · 颜色对照 / 摆好再按确认」，三行图例沿用现有文案（红灯 = 放黑子 / 绿灯 = 放白子 / 蓝灯 = 该拿走，行数与现在相同）；确认键图标换 `hand-pointing`；摆完写「一共 n 手」；接着摆弹窗写「从头摆要先把盘上的子都拿下来」。灯没亮时照旧提示「照坐标自己找」，不拦摆放。
- 采集态（`collect=true`）：与今天完全一致（守卫、拍照、409 分型、遮罩、文案）。

**验收：**
- 后端：采集服务存在但未开开关时 `POST /baipu/capture` 回 404、`GET /baipu/mode` 回 `{"collect": false}`；开关打开时 `mode` 回 true、`/capture` 行为与现有测试一致；`resolve_baipu_collect(None, None)` 为 False，`KATRAIN_BAIPU_COLLECT=1` 为 True。
- 前端上线态：进 `/kiosk/baipu/session/:id` 不出现标定台（即使 `geometry/status` 为 `required`）；标定线程在跑（phase 属于上面五态）时不挂摆谱屏、显示「棋盘标定还在进行」，phase 离开这五态后直接进摆谱；`/baipu/mode` 先回而棋盘状态迟到时摆谱屏一次都不挂；`/baipu/mode` 挂起时 3 秒后按上线态进门；从第 1 手按到摆完，网络面板里 `/api/v1/baipu/capture` **零请求**；屏上无「帧」「拍照」「摄像头」字样。
- 前端采集态：`mode` 回 true 时现有 e2e 四条采集用例（初始帧、失败不推进、legacy mismatch、重开覆盖）照绿。
- 盒上验证（board 模式、token=null）：盒子不改 provisioning（开关默认关即为上线态）；在未标定状态下从屏 16 进摆谱能直接摆，`/root/.katrain/baipu_captures/` 不新增目录（服务以 root 跑、drop-in 没给 `--capture-dir`，默认 `~/.katrain/baipu_captures` 展开到 **root 的**家目录；用别的 ssh 账号看 `~` 永远是空的，等于没验）。此条需上板一次（见 §7）。
- 屏 17 上线态四图过 Fan 确认（文案与图标偏离参考图，见 §4 D6）。

**依赖与卡点：** 前后端 + 契约（`/baipu/mode`）的小切片，走 vertical-slice。开关**默认关**意味着 Mac 上采 YOLO 训练数据的启动命令要加 `--baipu-collect`（`katrain/vision/README.md` 同步改）。「开关保留还是彻底去掉」「每一手怎么推进」两件待 Fan 定（§4 D1、D2），但本方案在两种裁定下都不白做（见 D1）。

### N9（棋谱库那一半）· P2 · 断网时棋谱库说「没搜到」

**现象（已核实）：** board 模式下 `RepositoryDispatcher.kifu_list_albums` 离线或远端出错回空列表、`kifu_get_album` 回 `None`（`katrain/web/core/repository.py:251-270`）⇒ 列表端点 200 空（`endpoints/kifu.py:65-67`）、详情端点 404「not found」（`:100-104`）。屏 15 搜索写「没有对得上的谱 · 换棋手名、赛事名或者年份再试」（`KifuPage.tsx:270-274`），屏 16 写「这一局读不到」+ 原文 `Request failed 404: …`（`KifuDetailPage.tsx:243-254`）。棋谱库在盒上是在线直读，没有本地同步，真实原因是没网。仓里已有同形状的解法：`_remote_only` + `RemoteServiceUnavailableError` → 503（`repository.py:364-376`，报告端点 `reports.py:221-230` 在用）。

**期望：**
- 棋谱库两条 dispatcher 路径改走 `_remote_only`：离线、传输错误、远端 5xx ⇒ 端点 503（`detail: "Remote kifu service unavailable"`）；远端 404 ⇒ 端点 404；在线成功照旧。
- `KifuAPI` 非 2xx 抛共享的 `ApiError`（带 `status`，消息格式不变）。
- 屏 15 搜索遇 503：「棋谱库要联网才能搜 / 这台盒子现在连不上云端。摆过的谱和导入的 SGF 不受影响。」+ 重试；屏 16 遇 503：「这一局要联网才能读 / 棋谱库在云端，这台盒子现在连不上。」+ 重试。其它错误保持现状（标题 + 原文）。收起态「共 N 局」拿不到就空着（现状，不变）。

**验收：**
- 后端单测：离线 → 列表/详情 503；远端 `ConnectError` → 503；远端 404 → 详情 404；在线 → 原样返回。
- 前端单测：列表请求被 `ApiError(503)` 拒绝时屏上是「棋谱库要联网才能搜」且不印原文；详情同理；非 503 的「boom」用例照旧。
- 盒上（board 模式）：断开盒子外网后在屏 15 展开搜索，看到「要联网」而不是「没有对得上的谱」。需上板或本机 board 模式各走一次。

**依赖与卡点：** 后端 + 前端文案。与 tsumego 赛道 N9（训练营那一半）改同一个 `repository.py`（相邻函数），与 review 赛道 N24（出错块印原文）在 `KifuDetailPage` 出错块上重叠。不改 `ReportLibraryImportDialog`（review 赛道所有，它已有拒绝分支）。

## 4. 待 Fan 拍板

### D1 · 采集链去留（K4）

- **问题：** 拍照采集只为 YOLO 训练数据。上线版是把它留在开关后面，还是从代码里彻底去掉？
- **选项：** A) 留在 `--baipu-collect` 后面，默认关（本轮计划做的就是这个）；B) 彻底去掉 `/baipu/capture`、`baipu_capture.py`、屏 17 的采集态分支。
- **推荐 A。** 理由：YOLO 4 类重训（black/white/led_red/led_green）的数据正是从摆谱采的，去掉等于下次采数据时重做一遍 manifest / 几何冻结 / 同步屏障；代码留着的成本只是一个默认关的判别位和屏 17 的一条分支。无论选哪个，**上线态的代码是同一份**——选 B 时只需在 A 的基础上删掉 `collect=true` 那一支，本轮不白做。
- **不拍板时：** 按 A 落地（默认关，盒子 provisioning 不用动）。Mac 采数据要加 `--baipu-collect`。

### D2 · 上线版每一手怎么推进（K4）

- **问题：** 不拍照之后，谁来确认「这一手摆好了」？
- **选项：** A) 人按「确认落子」（本轮计划）；B) 复用实体盘识别自动推进（`/ws/vision` + `useVisionSync`，死活题 `physicalTsumegoMachine` 已在用这条前端编排路径）。
- **推荐本轮 A，B 另起一条赛道再议。** 理由：B 需要识别模型加载 + 每次开机标定（`requireRecognition` 守卫），满盘中后盘的识别精度没有真机闸（V5 那一类），而识别失败时仍然要回落到 A 的手动确认——A 是 B 的前提，不是它的替代。
- **不拍板时：** 按 A 落地，不做 B。

### D3 · 屏 16 棋谱详情加不加「送去复盘」（K3 的一半）

- **问题：** 2026-08-22 kiosk-go-shell-align 实现 agent 自裁不做（`KifuDetailPage.tsx:43-50`），与 Fan 2026-08-20「尽量和其他三种棋类保持一致」、2026-08-21「照 galaxy 有哪些按钮逐一补齐」（稿子屏 16 画了三个出口）相反，没有 Fan 亲裁，可重开。
- **核实补充：** 国象的「加入复盘」（`smartbox-software/chess/ui/src/kifu/KifuGamePage.tsx:65-110`）不是一个跳转键，是一整条切片：进页先探测「这局在不在复盘里」、按钮四态（检查中 / 可加 / 已加 / 失败）、服务端幂等。围棋这边 `POST /api/v1/reports/` 只收 `user_game_id`，名局要先经 `UserGamesAPI.create` 复制进 `user_games`（复盘屏 `ReportsPage.tsx:353-370` 的「从棋谱库导入」就这么做），没有「这份名局是否已导入」的去重键，也没有 URL 能让复盘屏定位到某一局。照国象做 = 后端去重探测 + 复盘屏落点参数，跨进 review 赛道的 `ReportsPage`。
- **选项：** A) 重开，下一轮与 review 赛道一起按国象形状做（探测 + 四态 + 落点）；B) 维持不做；C) 只加一个跳到复盘屏并打开「从棋谱库导入」的键（同一条路两个口，且不防重复导入）。
- **推荐 A。** 判据「与另三家一致」站在 A 这边，但它不是纯前端，不适合塞进本轮。
- **不拍板时：** 本轮维持两个键，`KifuDetailPage.test.tsx`「只有两个动作键」照旧守着。

### D4 · 摆谱进度与「最近摆过」只活在无痕浏览器里（N10 摆谱那一半）

- **现象（已核实）：** `baipu:recent` / `baipu:sgf:{id}` / `baipu:progress:{id}` 全在 `localStorage`（`baipuApi.ts:138-214`），盒上 chromium 是 `--incognito`（`smartbox-kiosk.service:39`）⇒ 浏览器被 OOM 杀或重启后，屏 15 的「继续摆谱」「最近摆过」清空，导入的本地 SGF 连谱带进度都没了；而实体盘上那 47 颗子还在。屏上「存在这台盒子上」（`KifuPage.tsx:327`）、「选过的谱整份存在本地，断网也摆得完」（`:332`）、「进度已经存下了」（`BaipuSessionPage.tsx:617`）在浏览器重启这件事上都不成立。
- **一条对摆谱特有的判据：** 条目包说的「不分账号」**对摆谱不是缺陷**——摆谱进度描述的是实体盘上摆着几颗子，那是**盒子级**的事实，换账号时盘上的子不会跟着消失。所以摆谱不该跟对弈 / 训练营一起按账号分。
- **选项：** A) smartbox 改持久 profile（去 `--incognito`，一次修好四个模块，但牵动盒端身份 / cookie 语义，归外壳与 box-SSO 负责人）；B) 摆谱这一半搬到盒端后端存（`~/.katrain/` 下一份 JSON，盒子级作用域，离线照样可用，前后端 + 契约小切片）；C) 维持，只把三句文案改诚实。
- **推荐：先在外壳层定 A 做不做；A 不做时摆谱走 B。** 摆谱单独做 B 而 A 随后又做了，B 就成了第二份持久层。
- **不拍板时：** 本轮不动存储也不动文案。

### D5 · 直播孤儿页 `/kiosk/live`（L1，边界项，归「直播」模块）

- **现象（已核实）：** 屏 15 拉 8 条只画 4 行（`KifuPage.tsx:94,386`），无「更多」；`/kiosk/live`（`LivePage.tsx`，MUI 旧皮，`UpcomingList` 赛程只在这页）全仓无入口、自身无返回、L2 无 Dock（`KioskApp.tsx:146`，`LiveMatchPage.tsx:59-61` 注释已写明它是孤儿）。Fan 2026-08-20 对稿外五屏只裁了「只接壳不重排」，没裁这一页删还是补入口。
- **选项：** A) 照 K1 的做法重定向到 `/kiosk/kifu` 并删页，盒上不提供赛程；B) 屏 15 直播组加「全部直播 / 赛程」入口并按共享外壳重画这一页（需要稿子）。
- **推荐：** 由直播模块定；若短期没有稿子，先 A 堵掉死页，B 等设计。
- **本轮：** 不做。它与 K1 同样动 `KioskApp.tsx` 路由表和 `KifuPage.tsx` 直播块，做的时候注意与本赛道的改动合并。

### D6 · 设计稿屏 17 / 屏 15 的上游更新（K4 衍生）

- **问题：** 参考图屏 17 是整套拍照语境（「灯指下一手，摄像头认」「摄像头 · 这一手要采一帧」「已采集 12 帧」，`smartbox-software/superpowers/shared/kiosk-shell/sample-go/go-kiosk.tmpl.html:1638-1682`）。上线态实现必然偏离，四图会一直带着这几处差异。
- **推荐：** Fan 确认上线态四图后，请稿子作者按上线态改屏 17（折叠块、页控条副标题、确认键图标），重出参考图并同批更新 `tests/helpers/reference-shots.json` 的 pin；本赛道不改另一个仓。
- **不拍板时：** 四图标签带写明偏离，参考图不动。

### D7 · 新增文案要不要补 PO（全局口径）

本轮新增 key（全部 `t('ns:key', '中文默认')`，不往 PO 加）：`baipu:pagebar_sub_placed`、`baipu:done_hint_placed`、`baipu:led_title`、`baipu:led_value`、`baipu:resume_body_placed`、`baipu:wrong_size`、`baipu:wrong_size_hint`、`baipu:guard_sub_collect`、`baipu:calib_running_title`、`baipu:calib_running_sub`、`baipu:checking_board`、`kifu:wrong_size_reason`、`kifu:list_offline`、`kifu:list_offline_hint`、`kifu:detail_offline`、`kifu:detail_offline_hint`。补不补 11 语言 PO 待 Fan 统一裁定。

## 5. 不在本轮

| 条目 | 理由 |
|---|---|
| K3b「LED 灯不亮时确认键仍可按」 | scope §22 登记的有意不照做（推翻了 sbc-baipu-led-guide 评审 D 表 :155）。按 Fan 09-14 口径重新定性：上线版灯是唯一引导，灯坏了照坐标摆正是该有的回落，**不是缺口**，关闭。 |
| K3b「409 几何 / LED 分型」 | 已由 `a8eb0a6e` 做掉；上线态根本不发 `/capture`，只在采集态出现。关闭。 |
| K3b「虚手键 / 双方玩家卡 / 相机健康点」 | scope §22 D2/D3/D5 裁定站得住（虚手在重放谱里无物理动作；摆谱没有人在下棋）。相机点在上线态更无意义（不用摄像头）。不重开。 |
| V5 摆谱部分：P11/P12 无灯外框 `auto` 真机精度与 SBC 延迟闸（`sbc-baipu-led-guide/plan.md:2509,2514,2544-2545,2571`；`baipu_capture.py:316` 默认 `auto`） | **口径更正：** 按 Fan 09-14 纠正，这些闸只关乎训练帧质量，不再是上线验收项；只在打开 `--baipu-collect` 采数据时有意义，由 YOLO 数据赛道自己决定何时补。 |
| V5 其余三块（实体对弈一期 14 项、星阵实体对弈 Task 14 / Phase D、对齐赛道 RK3562 走查） | 分别归 play-ai、cross-platform、外壳。 |
| S5 文件选择器 / 下载在 RK3562 全屏 Chromium 上能不能用 | 需上板验证，读代码定不了。K1 删掉 `BaipuListPage` 后剩三处（研究屏打开/保存、屏 15「导入 SGF」、复盘本地导入）。**屏 15「导入 SGF」若在盒上打不开文件选择器，它就是一张死卡**——上板时顺带验，结果回填本文 §7。 |
| N9 训练营那一半 | 归 tsumego 赛道（同改 `repository.py`，见 §6）。 |
| N10 对弈「继续上一局」、训练营上次位置、实体盘开关 | 归 play-ai / tsumego / 外壳；摆谱那一半见 D4。 |
| L1 直播 | 归直播模块，见 D5。 |
| 上线态误触连点 | 采集态的拍照遮罩约 1 秒，顺带挡住了连点；上线态没有它，一次双击会连跳两手（可撤回）。盒上触屏是否真会双击没有证据，**不预先加冷却**（加了会让所有逐手点击的 e2e / 四图脚本都要等时间）。上板时观察，出现再加。 |
| 非方形 SGF（`SZ[19:13]`） | 见 K2，记录不做。 |

## 6. 与其它四条赛道的协调与共享文件

### 6.0 五条赛道统一协调规则（2026-09-14 主会话写定，五份 PRD 同文）

**基线**：五个分支从 develop `6f7dc629` 开出，提交文档前已快进到 develop `bad0c1fb`。中间 28 个提交全是视觉/LED 标定与盒端登录页，**不碰任何一份 plan 要改的文件**，plan 里的行号仍然有效。五个分支在同一个仓里，彼此不用 push 就看得见：`git log feature/kiosk-go-<赛道> -- <文件>`。

**会撞的地方（按风险排序）**

1. **对局结束 → 落账 / 结算（`server.py`）：两条赛道各设计了一套，必须收成一条。**
   - 对弈·AI（N22）：新增 `_finish_ended_game`，挂 `manager.on_game_ended`，`/api/move` 自然终局改走它。
   - 跨平台（N13）：新增 `_record_platform_engine_game` / `_session_owner`，给 `_record_ai_game(_locked)` 加 `data_overrides`，在 resign / move / 视觉三处落账。
   - **规则**：终局收尾的唯一入口归对弈·AI 的 `_finish_ended_game`。跨平台照 plan 做，`data_overrides` 与 `_record_platform_engine_game` 保留为薄 helper；合并时由后合并的一方（默认对弈·AI，见下方顺序）把跨平台的三处调用点收进 `_finish_ended_game`。
   - **合并验收**：`grep -n "_record_ai_game(\|_record_platform_engine_game(" katrain/web/server.py` 里，终局路径的调用只经过 `_finish_ended_game`。两套并存就不算合完（同形状的教训见记忆「两套并行实现」）。
2. **`/api/resign` 与 `interface.py` `_do_resign`**：对弈·AI（N21）改判负方；跨平台在旁边加 `_do_end_without_result`，并在 resign 里加平台落账分支。两处 hunk 相邻，属文本冲突。N21 的判负方修正对星阵局同样成立，合并时两边都留。
3. **`GameControlPanel.tsx`（+ test）**：
   - 跨平台只动 `engineMode` 那一支的动作数组与 `.ghint`（X9-a）。
   - 对弈·AI 新建 `gameKinds.ts`（`isFreeVsAi` 保留 `engineMode` 参数），并改 `analysisActions`。
   - **归属**：`engineMode` 局的按钮集合归跨平台，其余局型归对弈·AI。
4. **`GamePage.tsx`**：
   - 跨平台改 `:335-341` `refreshItemCounts`、`:501` `handleEngineAnalysis` 两处 token 闸（X7），另加 `EndgameCard` 的 Void 说明行。
   - 对弈·AI 改 N17 / N21 / N25 / A18 等处。
   - 对弈·AI **不要顺手改那两处 token 闸**（归跨平台）。
   - `tests/kiosk-screen-05-game.spec.ts` 两家都改，后合并方保留两边断言。
5. **`KioskApp.tsx`**：训练营 T9 改 `:132` 做题路由守卫；棋谱 K1/K4 改 `:56` import 与 `:137-145` 摆谱路由。hunk 相邻，属文本冲突，两边都留。
6. **`repository.py`**：两家都只**调用** `RepositoryDispatcher._remote_only`，都不改它本身。
   - 训练营改 `tsumego_*`（`:189-225`）与 `get_all_problems`（`:98-106`）。
   - 棋谱改 `kifu_list_albums` / `kifu_get_album`（`:251-270`）。
7. **请求失败分类**：复盘赛道新建 `src/utils/requestFailure.ts`。其它赛道本轮不依赖它，**也不要另建同职责的共享文件**（各自在本页内处理即可）。五家都合并后再收口，已登记为后续项。
8. **i18n**：五家都只写 `t('ns:key','中文默认')`，本轮不改任何 `.po`（并行改 11 份 `.po` 必冲突）。合并完统一交 `katrain-i18n-expert` 补 11 种语言，各赛道交付时附新增 key 清单。补不补、何时补仍由 Fan 定。
9. **四图存档**：取图目录各家不同，不冲突。跨平台重取 01/10，对弈·AI 重取 05，训练营 11，棋谱 17，复盘 19/20。重取前按 CLAUDE.md 跑两次比对，排除抖动。

**合并顺序（默认）**：改共享文件少的先合；改得最多的最后 rebase，由它负责解冲突。
1. **复盘/报告**：只新建共享文件，不改别家的文件。
2. **棋谱**：含 P0 K1，先落 `KioskApp` / `repository`。
3. **训练营**：rebase 到棋谱之上，解 `KioskApp` / `repository` 的相邻冲突。
4. **跨平台**：落账 helper 先落。
5. **对弈·AI**：13 个 Task，最大。最后 rebase，并按第 1 条把终局收尾收成一条。

例外：单个 P0 Task 只要不碰第 1、2 条所列代码，可以拆出来先合，不必等整条赛道。例如对弈·AI 的 N17 只动 `GamePage` / `useGameSession`。

**每次合并前**：
- `git merge develop`（或 rebase），然后跑本赛道 plan 的 Global Constraints：`npm run build` 与 `npm run build:kiosk-2d`、`npx tsc -b`，再按基线 diff 跑相关测试。
- 下一家 rebase 时，对照本节查**语义**冲突，不只看 git 报不报冲突。git 报「合得干净」不等于合得对。

### 6.1 本赛道会改、可能与别家重叠的文件（writer 按 plan 列出）

| 文件 | 本赛道改什么 | 可能重叠 |
|---|---|---|
| `katrain/web/core/repository.py` | `kifu_list_albums` / `kifu_get_album`（:251-270）改走 `_remote_only` | tsumego N9 改同文件 `tsumego_*`（:189-225），相邻块 |
| `katrain/web/api/v1/endpoints/kifu.py` | 两个端点 dispatcher 分支映射 503 / 404 | review（若复盘链读棋谱库）低 |
| `katrain/web/ui/src/kiosk/KioskApp.tsx` | 删 `BaipuListPage` import 与路由改重定向；会话路由换 `BaipuSessionRoute`；:137-140 注释 | tsumego T9（做题路由的 `PhysicalBoardGuard`，:132）、直播 D5、play-ai 路由 |
| `katrain/web/ui/src/api/kifuApi.ts` | 非 2xx 抛 `ApiError` | review N24（复盘屏的棋谱库导入对话框消费 `KifuAPI.getAlbums`，消息格式不变） |
| `katrain/web/ui/src/api/baipuApi.ts` | 加 `BaipuAPI.mode()`、`forgetSgf()` | 仅本赛道（N10 若走 D4-B 也在这里） |
| `katrain/web/ui/src/kiosk/pages/KifuDetailPage.tsx` | 非 19 路灰键；503 文案 | review N24（同一个出错块）、D3 若重开 |
| `katrain/web/ui/src/kiosk/pages/KifuPage.tsx` | 「摆到实体盘」卡开搜索；503 文案 | 直播 D5（同文件直播块） |
| `katrain/web/server.py` | 新 CLI 参数 `--baipu-collect`；lifespan 设 `app.state.baipu_collect` | 任何动 lifespan / 参数表的赛道（play-ai、cross-platform），不同区段 |
| `katrain/web/ui/src/kiosk/__tests__/KioskApp.test.tsx` | 加 `KifuPage` 模块 mock 与 `/kiosk/baipu` 重定向用例 | 任何给路由表加用例的赛道（tsumego T9、直播 D5）；注意本赛道的 `KifuPage` mock 对整份文件生效 |
| `katrain/web/ui/tests/kiosk-shell-contract.spec.ts` | `MUI_ICON_BASELINE` 删 `BaipuListPage.tsx` 一行 | tsumego T5（删 `TsumegoCategoriesPage.tsx` 一行）、直播 D5（`LivePage.tsx`）——同一个数组 |
| `katrain/web/ui/tests/kiosk-shell-geometry.spec.ts` | `D2_SCREENS` 删 `/kiosk/baipu` | 直播 D5（`/kiosk/live`）同数组 |
| `katrain/web/ui/playwright.visual.config.ts`、`playwright.config.ts` | 加可选环境变量 `KATRAIN_PW_VISUAL_PORT` / `KATRAIN_PW_E2E_PORT`（设了独立端口且不复用；不设行为不变） | 其它赛道不设就不受影响；四条赛道 plan 都没改这两份配置 |
| `katrain/web/ui/tests/kiosk-shell-scroll.spec.ts` | `bootBaipu` 加 `mode` 桩、geometry 桩改为两态都挂 | 其它赛道加自己屏的闸时同文件尾部 |
| `superpowers/tracks/kiosk-go-shell-align/visual/17-baipu/**` | 重出屏 17 四图 | 任何人跑全量 `npm run fourup` 都会重写它；只提交自己那一屏目录，别人的抖动 `git checkout HEAD --` 还原 |
| `katrain/web/ui/src/kiosk/pages/TutorialCategoriesPage.tsx`（+test） | 「去摆谱」改指 `/kiosk/kifu` | 无赛道认领课程，低 |
| `katrain/web/ui/src/kiosk/components/vision/PhysicalBoardGuard.tsx`、`GeometryCalibrationScreen.tsx`、`src/kiosk/context/GeometryContext.tsx` | **只消费不改**（守卫的 `sub` prop；标定屏的 `backLabel/onBack/title/sub`；`useGeometry().status.phase`） | tsumego T9 可能改守卫接口——若改了 `sub` 以外的签名，或改了标定屏 props / 进行中 phase 名单，本赛道 `BaipuSessionRoute` 要跟 |

## 7. 验证方式

- **基线 diff：** 动手前在 worktree 里跑一次 `npx vitest run`（JSON 报告 + 默认报告的日志）与 `CI=true uv run pytest tests --continue-on-collection-errors`（环境要 `uv sync --extra web --extra vision`），记下失败**名字集合**——含 vitest 整文件加载失败、未处理异常与 pytest 收集错误，并先确认两边会话真的跑了（pytest 汇总行含 passed、无 Interrupted；vitest 跑前删旧报告、核报告 startTime 与退出码）才认「集合为空」；每个任务后只跑相关文件，收尾再全量跑一次比名字集合，不比条数。
- **前端单测（vitest，行为 / 调用级，不作布局证据）：** `KifuPage.test.tsx`（K1 卡、N9 503）、`KifuDetailPage.test.tsx`（K2 灰键、N9 503）、`TutorialCategoriesPage.test.tsx`（K1）、`KioskApp.test.tsx`（K1 重定向）、新增 `BaipuSessionPage.test.tsx`（K1 出口、K2 路数、K4 上线态不发 capture / 采集态发 capture）、新增 `BaipuSessionRoute.test.tsx`（K4 上线态不套标定守卫、标定线程在跑时不挂摆谱屏）、`src/api/baipuApi.test.ts`（K4 `mode()` 问不到当不拍、挂起超时当不拍）。
- **后端单测：** `tests/test_baipu_api.py`（K4 开关、`/mode`、capture 404；既有用例补 `baipu_collect=True`）、`tests/test_baipu_capture.py`（`resolve_baipu_collect`）、新增 `tests/web_ui/test_kifu_offline.py`（N9）。
- **类型与两套构建：** `npx tsc -b`；动了共享领地（`src/api/baipuApi.ts`、`src/api/kifuApi.ts`）⇒ `npm run build` 与 `npm run build:kiosk-2d` 都要绿，后者末尾 `✅ kiosk boundary clean`。
- **e2e（打构建产物）：** 先 `npm run build`，再 `KATRAIN_PW_E2E_PORT=8102 npx playwright test tests/baipu.spec.ts`（默认配置起真后端；跑前备份、跑后还原 `~/.katrain/config.json`）。**所有 Playwright 命令带本赛道独立端口**（视觉 `KATRAIN_PW_VISUAL_PORT=5273`）：两份配置原本写死 :5173 / :8002 并复用已在跑的服务，本机 10+ 个 worktree 并行时会测到别的赛道的服务；plan Task 0 Step 5 给配置加了默认关的环境变量开关。`kiosk-shell-scroll.spec.ts -g 摆谱`、`kiosk-shell-geometry.spec.ts`、`kiosk-shell-contract.spec.ts` 用 `--config=playwright.visual.config.ts`（vite dev server，全桩）。
- **四图关卡：** 只适用 **K4 屏 17 上线态**（文案、图标变了）。`KATRAIN_PW_VISUAL_PORT=5273 npx playwright test --config=playwright.visual.config.ts tests/kiosk-screen-17-baipu.fourup.spec.ts`，四张图逐项比对，**Fan 确认之前不进 K4 后端任务**。K1/K2/N9 改的是导航、错误态文案（参考图里没有这些态），按相称性各取一张真运行时截图给 Fan 过目即可，不做四图。
- **承重关卡：** 反查——K4 上线态折叠块三行换三行、页控条副标题变短、无新增节点，撤回改动不改变任何高度来源 ⇒ 不新增测量；但既有真浏览器闸 `kiosk-shell-scroll.spec.ts` 摆谱三条就量在这条链上（241 手造溢出、右栏 516、动作区贴底、着法块 ≥3 行），默认路径现在是上线态，必须跑绿作为证据；两条采集态用例（失败、遮罩）改为显式 `collect=true` 继续守采集态。
- **必须上板（RK3562，一次只跑一家；前端部署 `build:smartbox-kiosk-2d` 严格包，不是 `build:kiosk-2d`）：** ① K4：盒子默认 provisioning 下，未标定时从屏 16 进摆谱可直接摆完，`/root/.katrain/baipu_captures/` 无新目录（服务以 root 跑），灯色正确；设置里开始重新标定后按返回再进摆谱，先看到「棋盘标定还在进行」、取消后才进摆谱；② K1：摆完 / 退出落在棋谱屏，Dock 可见；③ N9：拔网后屏 15 搜索说「要联网」；④ 顺带记录 S5 屏 15「导入 SGF」能否弹出文件选择器、上线态有无误触连跳。结果回填本节。
