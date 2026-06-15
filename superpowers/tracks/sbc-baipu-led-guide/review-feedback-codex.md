## 总评：go-with-changes

计划方向可执行，但 P3 采集链还不能作为“SGF = ground truth”的可靠数据生产线：LED 命令完成、相机新帧、manifest 索引、SGF setup 语义和人工误摆兜底都需要在实施前收紧。

> 说明：当前 Codex 环境未注册名为 `adversarial-review` 的 skill；本评审按 `review-request.md` 的对抗式评审准则执行，并对计划与本仓代码做了抽查核实。

## Top 3 必改（最高优先）

1. [High] LED 与拍照之间缺少“物理已生效 + 新帧已到达”的同步屏障
   — 证据：`plan.md:137-140` 把 LED 写入放进后台队列，`plan.md:152-153` 的 REST 响应只表达 `{ok, connected}`，`plan.md:206` 只等 150ms 后拍；现有 `CameraManager.read_frame()` 只是返回后台线程保存的 latest frame（`katrain/vision/camera.py:171-181`），没有时间戳/序号。
   — 建议：`LedService.set_points/clear` 对采集路径必须返回命令完成结果，至少等到 `SHOW` 的 OK/ERR；`CaptureService` 或 `CameraManager` 增加 frame sequence/timestamp，`/baipu/capture` 等待 “LED SHOW 完成之后产生的新 frame” 再落盘。否则 manifest 标了 `next_move`，照片里可能还是旧灯、无灯或上一手灯。

2. [High] manifest 当前 schema 对 pass、setup、可选首帧、末帧和帧/手数关系表达不足
   — 证据：状态机同时写了 pass “直接 ADVANCE(不点灯/不拍)”（`plan.md:104-106`）、CAPTURE 后用 `stones_through_move=k-1,next_move=moves[k]`（`plan.md:110-113`）、又定义末帧 `next_move=null`（`plan.md:116`）；manifest 只存 `stones_through_move` 与 `next_move`（`plan.md:185-203`）。
   — 建议：把每帧语义改成显式索引：`frame_kind`（`initial_led|after_move|final_no_led|manual_check`）、`applied_move_index`、`next_guided_move_index`、`led_point`、`board_through_index`、`board_hash`。`next_move:null` 不应同时表示“谱尾无灯”和“中间 pass 无灯”。pass 策略也要明确：capture 是否寻找下一手非 pass 点亮，还是完全不拍 pass 邻接帧。

3. [High] 数据纯净度没有兜底：一次误摆会污染后续所有帧
   — 证据：PRD 已把摆放正确性校验列为可选增强（`prd.md:132-134`），但计划决策表选择 Ko/非法不校验（`plan.md:34`），P1/P3 验收只要求 UI/manifest 一致（`plan.md:119-125`, `plan.md:212-216`），没有物理棋盘与 SGF 的最小校验。
   — 建议：至少做轻量 QA，而不是等训练失败再发现：基于几何点的差分/patch 检测确认“刚确认的点出现了对应颜色棋子、被提子点已清空”，或每 N 手弹出人工复核 overlay；发现不一致时标记 session dirty、停止自动交付，manifest 写 `qa_status`/`discard_reason`。不必先上 YOLO。

## 详细发现

- [High] `goBoard.ts` 计划需要的 `isSetup` 信息，当前 `sgfToMoves()` 根本没有返回
  - 类型：correctness bug / 遗漏
  - 证据：计划接口包含 `MoveBoardStep.isSetup`（`plan.md:67-72`），会话页只调用 `sgfToMoves()` 得到 `{moves, stoneColors, metadata}`（`plan.md:93-95`）；实际 `sgfToMoves()` 也只返回这三项（`katrain/web/ui/src/utils/sgfSerializer.ts:157-217`），AB/AW 被压平成普通 moves（`sgfSerializer.ts:182-193`）。
  - 建议：先扩展 SGF 解析结果为结构化 step：`{kind:'setup'|'move', nodeIndex, property:'AB'|'AW'|'B'|'W', row, col, color}`。setup 不能按普通落子触发提子/非法判断。若要支持 AE 或矩形 setup，优先复用后端 SGF parser；后端已支持 AB/AW/AE 展开（`katrain/core/sgf_parser.py:250-286`）和规则重建（`katrain/core/game.py:132-143`）。

- [High] LED REST “入队即成功”会让采集时序不可证明
  - 类型：correctness bug / 架构风险
  - 证据：`LedService.set_points` 被设计为队列入队，队满还会丢最旧（`plan.md:137-140`）；P3 采集只在前端点亮下一手后等待 150ms（`plan.md:206`）。
  - 建议：LED API 分普通 UI 容错路径和采集强一致路径。采集路径应返回 `{ok, connected, seq, shown_at, errors}`，并在串口线程读到每条 `SETI`/`SHOW` OK 后才完成请求；如果 LED 未确认显示，当前帧不能写入可训练 manifest。

- [High] `/baipu/capture` 的落盘路径和 manifest 追加缺少并发与输入约束
  - 类型：correctness bug / 健壮性
  - 证据：endpoint body 接受任意 `game_id:str, seq:int`，直接拼 `{out_dir}/{game_id}/frame_{seq:03d}.jpg`（`plan.md:183-188`）；没有说明 `game_id` 正则、路径归一化、seq 去重、双击确认、manifest 原子写。
  - 建议：Pydantic 约束 `game_id` 为安全 slug，`seq>=0`；落盘后校验 resolved path 仍在 `out_dir`；每个 `game_id` 用 lock 串行 capture，manifest 用 `tmp` + atomic replace；重复 `seq` 要么幂等返回原记录，要么 409。前端在 capture pending 时禁用“确认/下一手/退出”。

- [High] `上一手/下一手/跳过` 与真实棋盘物理状态会脱节
  - 类型：产品流程 / 数据正确性
  - 证据：计划把这些控件列为会话底部常规操作（`plan.md:97`），但状态机只描述前端 `k` 回退/推进，没有描述如何要求操作者撤回已摆棋子、恢复被提子或作废已拍帧。
  - 建议：采集模式下把“上一手/下一手/跳过”改成显式 repair flow：进入后停止采集、清灯、展示目标 `boardAt(k)` 与需增删的点，用户复核后从新的 `seq` 继续；已拍帧标记 `superseded_by` 或整个 session dirty。简单版本：首版只允许“退出重来”，不要允许谱中任意跳转。

- [Medium] CaptureService 与 VisionService 的互斥判断不应只比较同一 camera 参数
  - 类型：架构风险 / 健壮性
  - 证据：计划只在 `_vision_config.enabled` 且 `_capture_config.enabled` 指向同一相机时抛错（`plan.md:180`）；现有 VisionService 会起 worker 进程并打开相机（`katrain/web/server.py:319-327`, `katrain/vision/worker.py:135-158`），CameraManager 自身没有跨进程 owner 锁（`katrain/vision/camera.py:107-155`）。
  - 建议：采集模式默认拒绝同时启用 VisionService，不要只比较 `0`、`"0"`、`/dev/...` 这类可能别名的设备参数。更稳的方案是引入 `CameraOwner`/file lock，或者让 CaptureService 成为唯一相机 owner，vision/geometry/capture 都从它取帧。

- [Medium] 复用 kifu 列表会在 board-mode 离线采集时无谱可选
  - 类型：产品流程遗漏
  - 证据：计划决定复用 kifu 库列表（`plan.md:36`, `plan.md:87-88`）；但当前 board-mode 的 kifu repository 是 online-only，离线直接返回空列表/404（`katrain/web/core/repository.py:245-263`）。
  - 建议：P1 同时加一个本地 SGF 导入/最近采集缓存入口，或把所选 kifu 的 SGF 缓存在本地。采集现场不应依赖远端网络可用。

- [Medium] P4 几何锁定需要把“空盘、LED 全灭、baseline 自检”写成硬性前置
  - 类型：遗漏
  - 证据：计划只说 `grab_burst(n)` 取空盘帧（`plan.md:237`）；autoresearch 的 `baseline` 是由空盘 warps 生成的每点 HSV 基线（`/Users/fan/Repositories/autoresearch/board-detection/autocal.py:85-88`, `stones.py:63-69`）。如果 LED 或棋子残留进入 burst，后续 classic/diff 校验会系统性偏。
  - 建议：`POST /geometry/lock` 先调用 `led.clear()` 并要求用户确认空盘；保存前运行 empty self-check（black/white 近 0）并把 `empty_self_check` 写 sidecar json。测试加入“非空 baseline 拒锁/警告”。

- [Medium] 前端共享提子 util 的坐标契约还不够硬
  - 类型：架构风险 / 测试遗漏
  - 证据：LiveBoard 内部使用 Go 坐标 y=0 底部（`LiveBoard.tsx:44-64`），绘制工具也明确 grid y 被反转（`boardUtils.ts:45-58`）；计划让新 `goBoard.ts` 输出 row=0 顶部，再由 BaipuSessionPage 转给 LiveBoard（`plan.md:80-84`, `plan.md:98-101`）。同时它还计划改 `useTsumegoProblem.ts`，该 hook 直接使用 `[x,y]` 自由落子坐标（`useTsumegoProblem.ts:29-31`, `useTsumegoProblem.ts:336-355`）。
  - 建议：不要让一个函数同时暗含 `row/col top-origin` 和 `x/y bottom-origin`。定义类型别名或 branded types：`BoardPointTop`、`GoPointBottom`。`goBoard` 单测必须覆盖 D4/Q16/角点在 19、13、9 路下的 round-trip，以及 LiveBoard click 坐标与 SGF 坐标互转。

- [Low] LED RGB 数值与 `MAX_BRIGHT=40` 的表述冲突
  - 类型：正确性/文档一致性
  - 证据：计划说颜色映射“≤MAX_BRIGHT”（`plan.md:143`），但给了 `(80,0,0)`、`(0,80,0)`、`(0,0,120)`；固件协议里的 `MAX_BRIGHT` 是全局亮度钳制，不是单通道 SETI 值（`led-calibration-and-protocol.md:19-23`, `led-calibration-and-protocol.md:88-91`）。
  - 建议：要么把 SETI RGB 改成不超过 40，要么明确“RGB 为 0-255 帧缓冲值，实际输出由全局 BRIGHT 40 缩放”。否则后续测试/固件实现容易各按一种理解写。

## 对我们关键决策(§4)的判断

- 决策 1（坐标系）：同意，但必须用类型和测试封死边界转换。规范 `(row,col)` 顶部基给 LED/manifest 是正确方向；LiveBoard 边界转换也比到处反转稳。
- 决策 2（前端共享 util 算提子）：有条件同意。UI 预览可以前端算；但训练 manifest 的真值最好由结构化 SGF step 或后端 parser 校验。当前 `sgfToMoves()` 信息不足，不能直接支撑 `isSetup` 和完整 SGF 语义。
- 决策 3（独立 CaptureService）：部分同意。独立服务比滥用 VisionService 清晰，但相机 owner 要集中化或强互斥，不能只靠同 camera 参数比较。
- 决策 4（带灯拍时序）：部分异议。带灯拍能服务 4 类标签，但必须增加 LED ack、新帧等待、hand/motion 稳定检测、pass/final 显式 schema；否则照片和 manifest 无法证明一致。
- 决策 5（19×19、pass、让子）：19×19 同意；pass/让子不同意当前简化。pass 不拍可以，但 manifest 需要表达跳过；让子/setup 不能只当普通同色落子。
- 决策 6（Ko/非法不校验）：异议。Ko 不是重点，人类误摆才是重点。至少需要轻量视觉/差分校验或人工 QA gate。
- 决策 7（迁移 autocal）：同意方向，但 P4 应保留 `grid_calibrator.py` deprecated 一个周期而非立即删除，且 geometry lock 要明确 LED off、empty baseline self-check、sidecar 诊断。
- 决策 8（复用 kifu 入口）：部分同意。复用 UI/API 可以省事，但要补本地 SGF 导入或离线缓存，否则 board-mode 离线采集会卡在无列表。

## 你认为我们漏掉的（§3/§10 之外的新问题）

- 采集需要端到端“同步证明”：LED `SHOW` ack、相机 frame sequence、capture timestamp、manifest timestamp 应在同一条记录里可审计。
- manifest 需要可恢复/可去重：双击、刷新页面、重进同一 `game_id`、中途断电都要能判断哪些 frame 可用。
- 前端 SGF 解析必须保留 setup/move/node 信息；否则 `isSetup`、让子、AE、pass 都只能靠猜。
- 采集流程需要 correction/repair 模式，不能把棋谱浏览里的“上一手/下一手”原样搬进物理采集。
- 离线采集入口需要本地 SGF 来源；现有 board-mode kifu 是 online-only。
- P4 几何锁定和 P3 采集虽然可分阶段，但如果要做数据 QA，几何锁定至少应成为“强烈建议/可选阻断”。
