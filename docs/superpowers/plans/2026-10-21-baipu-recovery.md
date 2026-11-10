# 摆谱纠错恢复 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复摆谱纠错死锁，支持提前摆好一至两手、任意拿放顺序纠正，并用明确且不过度重复的语音、屏幕与灯协助用户恢复。

**Architecture:** 棋谱回放得到的 B(k) 是唯一盘面事实。默认核对当前及未来最多两手的合法盘面，唯一匹配才同步；歧义或超出范围由用户明确选择目标，再作真实核对。worker 实际应用基准后，前端一次提交目标手数；语音只消费已确认的交互状态，不参与推进。复用现有 worker、reducer、离线 MP3 播放器和声音设置。

**Tech Stack:** Python / NumPy / FastAPI / 现有进程内及多进程 vision worker；TypeScript / React / Vitest；pytest。无新依赖、数据库或图像模型。

---

**状态：计划文档；未实施。** 用户要求本轮完成调查、计划、Astra Max 独立审核并修改最多两轮后停止。下面所有复选框是未来实施步骤，本轮不运行其中的产品修改、发布或设备写入操作。

**版本与审核：** 本次“提前两手、边界交互与语音”修订已完成 Astra Max 独立两轮评审；首轮四项阻塞均已关闭，第二轮 Approved。详见 [本次评审记录](../reviews/2026-10-21-baipu-recovery-interaction-review.md)，其中说明受审版本及最后文案澄清。上一版 [原审核记录](../reviews/2026-10-21-baipu-recovery-plan-review.md)独立归档。本轮已停在文档阶段。

**设计依据：** [原因与流程设计](../specs/2026-10-21-baipu-recovery-design.md)。代码基线 `3da3e50360db96072ade5a3b6d0bdf596f48d987`，发布 develop 合并点 `c65e410cb148e734635ed6b5bcf782e13fab6bed`。

## Chunk 1: 从真实失败到可执行修复

### 1. 已核实的原因与范围

现场 `kifu_178448`：页面 `k=115`，等待白 P8（总第 116 手）；canonical `B(115)` 不含 P8，machine target 和实际识别盘面却都含 P8，共 116 子。唯一不一致点为 `(row=11,col=14)`。日志中 P8 白子与 J8 错色已有记录；用户确认点过“摆好了，继续”，完整点击顺序不可还原。

现有 `adopt()` 把整盘摄像头读数设为 setup target，却不更新 `k/next`；reducer 又禁止 adopt 路径提升下一手。setup 完成后 `force_sync()` 吞入 P8，界面继续等同一个 P8。真实 reducer 与 MoveDetector 已离线复现；这不是靠异常堆栈定位的崩溃，而是三份状态不一致。

本次范围为摆谱恢复、提前两手与语音引导。预览线程、标定页、识别模型、阴影/手部判据、其他棋类及全谱自动搜索不在范围内；超过两手提供显式手动对齐入口，不自动猜。稳定盘面持续漏识别仍可能延迟核对，不以“忽略缺子”掩盖该问题。

### 2. 必须保持的规则

1. 任何基准只能来自 `replayBaipuMatrix(steps,k,size)`；摄像头结果只作证据。删除摆谱 raw adopt 入口。
2. 一般恢复可接受 B(k)、B(k+1)、B(k+2)，必须精确包含颜色与 removed，且完整盘面唯一匹配。最多自动前进两手，不从棋子数量推断步数，不自动倒退；一次 applied 只提交一次 toK，而非循环调用两次 +1。
3. **撤回锁：** 明确撤回后只接受撤回目标 `B(k)`；稳定达到该目标前禁止提升下一手。重复核对、试下恢复、重连不解除该锁。达到目标后恢复正常落子识别。
4. 新的 worker 基准、页面进度和灯必须依据同一个 canonical 结果。HTTP 200 只代表命令入队；worker 的 `baipu_target_applied` 才代表基准已实际应用。
5. 恢复中不开下一手灯，正确下一手不闪蓝要求拿走；保留已有 `move_pending` 熄灯/再点灯补救。灯失败可提示，基准同步失败必须停止本批后续控制命令。
6. 复用现有遮挡、运动、多帧投票、参考检查和 degraded 置信度规则。没有有效新帧时只等，不改变棋谱或自动撤回。重复读相同 camera frame 不累计确认。
7. 新编号不能贴到旧事件上。所有摆谱事件由产生它们的 worker 写入 `{generation,revision,observation_seq}`；旧 setup 事件不驱动新摆谱流程。
8. 普通落子已由 MoveDetector 确认，不再追加一轮整盘等待；同步 canonical 目标并等 worker 应用确认即可。提子/AE 需要处理的物理变化仍应核对。

实施环境：获准实施后先用 @superpowers:using-git-worktrees 建立独立工作树，再用 @superpowers:test-driven-development 开发。下列 `.venv/bin/python` 和 UI `node_modules` 假定已在该工作树可用；优先复用已安装环境，缺依赖时按仓库 `uv sync` / UI `npm ci` 初始化一次，不能在主工作树执行本计划的产品修改。RED/GREEN 步骤和命令都在未来实施阶段执行。

### 3. 有限协议与状态设计

#### 3.1 新接口，仅摆谱消费者使用

保留旧 `/setup-mode`、`/expected-board`、`/monitor` 等接口契约。新路由使用现有 `/api/v1/vision` router：

| 请求 | 参数与结果 | 作用 |
| --- | --- | --- |
| `POST /baipu/start` | `{expected_generation:string|null}`；返回 `{generation:string}` | 与 status 读到的代号作 CAS；相等才分配随机新代号并入队 start。worker 进入无绑定的摆谱 monitor，撤臂、清理上一代摆谱上下文。已绑定对局或 local confirmation 活跃时返回 409，不能自动抢走它。 |
| `POST /baipu/target` | 下文 `TargetRequest`；返回 `{accepted:true}` | 入队 canonical 目标；不声称已应用。service 与 worker 都检查 generation，worker 再检查 revision。 |
| `POST /baipu/control` | `{generation, action:'pause'|'stop'|'recheck'}`；pause 带 revision/paused，recheck 带 revision，stop 只需 generation | pause/recheck 仅当前版生效，防止旧暂停请求晚到冻结新目标；stop 结束本代，不能影响新代。 |

同一 VisionService 保存 opaque generation token、当前 revision 和当前小型上下文，无租约服务或新持久化系统。现有 `GET /vision/status` 增加 `baipu_generation:string|null`；start 的 expected_generation 与服务现值相等才更新 token，避免浏览器 reload 后旧 start 晚到覆盖新页面，随机 token 也避免服务重启后复用整数。读取并 CAS 更新在一个同步 service 方法内完成；冲突时仍活跃的 hook 最多刷新状态重试一次，其他情况显示重试入口。

start 与 target 使用同一 worker FIFO；前端在 `usePhysicalBaipu.ts` 文件级保留一条共享 IO Promise 队列，所有 hook 实例的 start/target/control/cleanup 均串行，每次发送和 await 返回后检查各自生命周期。hook 内 queueRef 不能保证跨卸载/重挂载的顺序，不能用它代替共享队列。旧 generation 的 cleanup 无效果，不清理新页面。服务停止本代后保留最后 token 作 CAS 栅栏，单独标记 inactive；其他 owner 接管时换新 token 并标记 inactive。

仅新摆谱 HTTP 封装设5s AbortController deadline，超时必须 settle 让共享队列继续；不改全局 apiPost，也不把前端 abort 当远端未执行。未知结果仍按同版完整 body 重发/受保护 start CAS 恢复。所有会提交进度、点灯或播报的排队动作，执行前与 await 后还须核对当前 revision/选择状态，不能只核对生命周期 generation。

```ts
interface TargetRequest {
  generation: string;
  revision: number;              // 同一 generation 单调递增
  k: number;                     // 页面已确认的谱步骤，非棋子数量
  board: number[][];             // 当前已提交 B(k)，始终 canonical
  mode: 'verify' | 'apply';
  reason: 'entry' | 'wrong' | 'undo' | 'restore' | 'capture' | 'recheck' | 'advance' | 'clear' | 'pass' | 'align';
  total_steps: number;
  selected_k?: number;           // 仅用户明确选进度的 align
  candidates: Array<{ k: number; board: number[][] }>; // verify最多3个，apply/align各1个
  source_revision?: number;      // apply 快路径的落子来源
  confirmed_seq?: number;        // apply 快路径的落子证据
}
```

矩阵严格为 19×19、整数 0/1/2；0≤k≤total_steps，revision≥1。普通 verify 的候选步数在 [k,min(k+2,total_steps)]，最多3个、步数不重复；允许不同步数矩阵相同，但不能擅自选最小/最大，而要发歧义。reason=align 时仅接受一个候选，其 k=selected_k∈[0,total_steps]，用户明确选择后才能生成此请求；仍须 verify，不能用 apply 跳过盘面检查。

apply 仅一个 k+1 候选：普通落子由最近正确确认支持的“原基准加一子”，source_revision/confirmed_seq 必须对应真实缓存。显式 pass 为相同矩阵 k+1，不要求伪造 seq。两种情况都验证 base k/board 与 worker 已应用基准相符；自动两手必须走 verify，不能用单次落子证据推断两手。实际步数、pass、AE、setup 的候选由 canonical replay 构造，不能只做加两子。

处理 apply 新 revision 时，先用保存的上一版确认及已应用基准验证 source，再替换上下文；不能先清缓存/改 revision 导致所有合法 source 自己失效。确认缓存只供这一次 canonical 交接，成功后消费；同版重试走已缓存 applied，不重新消费证据。

worker 开始处理新目标时记录 `opened_monotonic`，verify 只用其后采集、camera_seq 严格递增、observation_seq 严格递增的有效帧。同版重复 target/recheck 不重建目标、不清投票、不重置窗口；已完成时重发同一个 applied 结果。更低 revision 忽略并可返回 stale 状态；更高 revision 取代旧版本，撤臂并使旧证据失效。重用相同 revision 却改变 body 属于错误，不能静默改目标。

#### 3.2 事件

```ts
type BaipuStamp = { generation: string; revision: number; observation_seq: number };
// worker 完成原子应用后才发布：
type Applied = BaipuStamp & { k: number; board: number[][] };
type BoardObserved = BaipuStamp & { board: number[][] };
// 核对提示针对当帧最接近的一个合法候选，不拼接不同时刻的棋子：
type Progress = BaipuStamp & {
  candidate_k: number;
  missing: Array<[number, number]>;
  extra: Array<[number, number, number]>;
  status: 'checking' | 'not_visible';
  observed_board?: number[][];   // 有效帧的完整处理后读数，用于诊断；不作基准
  raw_agrees: boolean;           // raw-voted是否同意该完整读数
  visibility_age_ms: number;     // worker计算的连续不可见时长，不是新观测证据
};
```

事件名为 `baipu_target_progress`、`baipu_target_applied`、`baipu_target_error`。现有 `move_confirmed/move_pending` 在摆谱拥有 monitor 时加同一 stamp；其他消费者保持原字段和行为。前端 `useVisionSync.seq` 只是接收序号，继续用于消费去重，不能当摄像头帧号。

新增 `baipu_target_ambiguous: BaipuStamp & {matched_ks:number[]}`：同一完整盘面稳定匹配多个候选时撤臂，并在本版锁定 waiting_selection；以后帧即使变成唯一匹配也不能 applied，只有新 revision 解除。用户选合法项后新 revision align verify。新增 baipu_board_observed：await 的有效新帧、两份完整矩阵一致时按盘面变化发布（每版首次也发）；只复用原推理，不增加读帧/模型任务。它是触发核对的证据，不是推进回执；核对/暂存/选择期间不以它反复重开版本。

`baipu_target_error` 附 code：source_stale（新 revision verify）、apply_failed（撤臂，新 revision verify）、unavailable/stale_generation（重新受保护 start，最多自动重试一次）、invalid_target（显示错误，不自动循环）。传输错误不伪造 worker error：若不知道完整 target 是否入队，保存并重发同版完整 body；不能只发一个 worker 可能不认识的 recheck。重发已应用 target 返回原 applied。

摆谱 monitor 的 move_confirmed 在 worker 内缓存真实来源后立即撤臂，再发带 stamp 的事件，等待目标交接；其他 monitor 不改。这样在网络错误时也不会继续接收多手并覆盖本次缓存。无网络连通时前端不能承诺远端命令已经执行，只冻结提交并显示连接状态；恢复后 start/verify 重新建立一致状态。

applied 顺序（worker 同一处理线程）：撤臂 → `_sync.reset(canonical_board)` 清除 setup/capture 旧目标 → `_sync.set_expected_board(canonical_board)` → `_expected_np=copy` → `_move_detector.force_sync(canonical_board)`（相同且已有干净基准时不重置候选）→ 保存 effective k/当前结果 → 若未暂停则布臂 → 入队 applied。任何一步失败不发 applied、不布臂，发送 error。不能调用 API RESET_SYNC：其几何/参考副作用超出恢复范围。worker 必须先入队 applied，后处理后续帧的落子事件。

新的恢复请求在 worker 生效之前，旧 worker 结果可能已经产生；前端按 generation/revision 忽略它，直到新请求核对成功。不会把暂时的旧基准当成功反馈。

#### 3.3 候选与确认策略

| 入口 | mode / 候选 | 前端提交时机 |
| --- | --- | --- |
| 进场、错子、重新核对、试下恢复、重连 | verify：B(k) 和未来最多两手；按后文 pass 边界截断 | applied.k=k 只恢复；唯一匹配 k+1/k+2，一次 guarded onReconciled 到该步 |
| 明确撤回及尚未完成撤回的其他入口 | verify：只有 `B(k)` | 到 applied 才解除撤回锁，k 不推进 |
| 正常 MoveDetector 已确认正确落子、没有提子/改色 | apply：结果候选只有 `B(k+1)`，带真实 source_revision/confirmed_seq | 暂存该决定，收到 applied 后才提交 k+1；无额外整盘/新帧等待 |
| 正常确认后有提子 | verify：当前/未来最多两手，含各候选最终 removed 结果 | 完整唯一匹配且 applied 后提交；摆回 B(k) 则恢复原等待 |
| clear/AE | verify：只接受 `B(k+1)` | 按 removed 清理完成后推进；不能继续沿用无条件 500ms 定时跳过 |
| pass、或没有物理变化的明确步骤 | 先确保当前目标已 applied，再沿用 500ms 定时发显式 pass apply，结果为相同矩阵的 k+1 | applied 后推进，不凭相同矩阵推测虚手，不因重连重复跳 |

verify 复用 config `move_confirm_frames` 对连续相同候选进行确认，不增加秒级固定等待；重复 camera_seq 不累计，候选改变或有明确差异则清零。无效帧/遮挡中断连续确认但保留目标。不能在旧帧基础上累计不同位置的“曾经正确”。正常 apply 不重新进行这轮确认。

新 verify 目标清理旧图像平均及 per-cell 投票累积（进程内优先复用 `_reset_local_accumulators(reset_motion=False)`），不重置几何/相机，不反复重置 motion 稳定状态。不为重新核对丢弃有效参考图。核对成功必须同时满足两份完整矩阵相等于候选：raw-voted（进程内为合法 deny 掩码后的 `denied_stable`，尚未 reference_check）以及 reference-corrected 的 observed_board。多进程没有该参考层时两份取同一投票结果。这是保守核对：不让参考填补掩盖真实缺子，也不绕过参考的假阳性否决；一份不符就继续核对，不合并时刻/位置。持续漏识别的代价已在设计边界中明确。

摆谱拥有 monitor 时，进程内与多进程都使用已有 read_frame_identified，并在图像平均、投票和 MoveDetector **之前**按 camera_seq 去重；normal 与 verify 共用这道门，其他消费者读帧语义不改。没有新帧就不重复推理/累计候选，仍处理命令和上报状态。verify 再校验采集时刻晚于窗口建立及观测序号。在原有单次推理结束后调用核对，不增读摄像头、不做第二次推理。无帧身份的设备报告 unavailable，不回退到“循环次数就是新帧”。

健康门控沿用 `SyncStateMachine` 的 board_detected/degraded 判据：在 sync.py 提供小型 `observe_recovery_health(...) -> (allowed, events)`，内部复用现有 `_check_degraded` 与原阈值/迟滞；正常 `update` 不改语义。恢复分支只调用一次健康门控，避免旧 setup 自动完成并产生裸完成事件。geometry_ready、motion_stable、有效识别仍是前置条件。真正有差异时发 progress；尚未看清只发 checking/not_visible，不宣称用户一定漏摆。

可见性必须覆盖 await 与 verify：两种 worker 的无帧、运动不稳定、几何不可用、健康不允许等早退分支，都显式 interrupt 确认并发布当前版本 progress.status=not_visible（只在状态变化时发，省略 observed_board、raw_agrees=false，空 missing/extra 不代表匹配）。visibility_age_ms 用 worker 单调时间计算；引用最后 observation_seq，不伪造新 camera/observation。新鲜有效画面恢复时必须发一次 checking/可见状态，即使盘面未变，让前端取消不可见 timer。没有实际推理结果不能用虚构 confidence=0 改退化判据。

重复读同 camera_seq 本身仅跳过处理，不立刻称遮挡；如果持续无新采集帧达 STUCK_MS，发布 not_visible 并带实际已持续时长，前端不再额外等10s。真正无帧/运动失败从首次失败计连续时长；前端用 age_ms+本地经过时间计提醒，不跨时钟比较绝对timestamp。暂停/选择等主动停止识别期间不累计不可见提醒。已有 worker/voice 用例应证明“模型从未成功运行也能提示不可见”。

#### 3.4 前端状态与失效规则

在已有 phase 中增加 `syncing`（命令已发，等实际应用）；`setup` 表示有效目标正在核对；`await` 只在本版应用确认之后成立。`advancing` 是已接受一次、等待页面 k 更新的屏障。恢复版本、候选盘面与撤回锁在 reducer/hook 中单点维护，不再从 raw board 构造 target。

所有摄像头路径统一为 staged → worker applied → guarded onReconciled({fromK,toK,generation,revision})。普通正确落子暂存 B(k+1) 并 apply，无新增整盘等待。applied 前不改页面/存储 k；回执中的 board 必须等于本版指定候选。页面 functional updater 仅在 prev===fromK 且本版未消费时直接写 toK/保存一次，不能连调两次 advance。自动允许 toK=fromK/+1/+2；只有明确 align 可前往用户选定步数。toK=fromK 是恢复等待，不播普通落子音；前进一/两手各最多播一次音效。末手完整 applied 后才 done/清进度。手动与采集模式保持旧流程。

applied 与下一条 move_confirmed 可能在同一 WS 批次：advancing 等页面 k/next 追上时，不消费余下事件、不越过 processedSeq；k/next catch-up effect 必须先更新 machine，事件消费 effect 再续跑。恢复到 await 后可消费同版本下 seq>applied.seq 的后续事件。若 MAX_EVENTS 裁剪导致序号缺口，启动当前 canonical 的新 verify，不能静默遗失后永久等待。测试必须证明后续落子继续，不能只验证“没 +2”。

“重新核对”的动作按当前状态决定，不能总重放旧 applied：

| 按下时状态 | 动作 |
| --- | --- |
| 未完成的 verify，目标已在 worker | 同 generation/revision 请求 progress，不重置累积 |
| target 传输结果未知、或等 ack | 重发保存的同版完整 body；已完成则返回缓存 applied |
| await，旧目标已经 applied | **新 revision verify** 当前及未来最多两手，保留 pendingUndo 限制；不能重播旧 applied 冒充新核对 |
| source_stale/apply_failed | 废弃错误 apply，新 revision canonical verify |
| 无有效 generation | 受保护 start 后 verify |

保留已提交 k，错误时停在 setup/syncing，不吞异常继续布臂/点灯。应用确认超过 5s 未到且没有 progress 时显示可重试，不无限重试终态错误。按钮沿用已有动作区：setup 超时、同步错误、或 await 超过 10s 时可用，不限于旧版 setup.stuck；manual/collect 不新增此按钮。自动补救取消或已经用过后，用户仍有明确入口。

await 10s 无推进时，仅调用现有只读 visionDetectedBoard 一次；只有完整匹配不同于 B(k) 的 canonical B(k+1) 才触发 verify。请求时捕获 lifecycle/generation/revision/k/phase 与待确认活动标记，返回时全部仍相同且仍为 await 才能触发；若同版已有未结束的 MOVE_PENDING，或请求期间出现 pending/confirmed，则取消此次自动补救，保留正常确认窗口。快照只触发核对，不能充当成功证据或基准。快照仍为 B(k) 时保持下一手灯。每 k 最多一次自动检查，主动 recheck 按上表可重新 verify；无周期重置或新增推理。

暂停先撤臂且暂停图像确认；恢复建立对应 canonical verify 目标后再解除暂停。撤回时在现有 BaipuProgress 与 k 一起保存可选 pendingUndo=true，默认缺省为 false；指定 B(k) applied 后，按 k 守卫清 false。页面重新进入也恢复该标志；WS 重连、试下和 recheck 不解除它。明确重新开始/正常完成清理标志。复用既有按用户身份隔离的 store，不新增存储服务。离开页面只发送带 generation 的 stop，取消计时器并清理本页灯；迟到响应不得 setState、改 k 或点灯。其他功能接管时先失效摆谱代号。

本次新增边界：用户明确选择“对齐手数”可以替换撤回目标，但只有所选盘面 applied 后才清 pendingUndo；取消/退出未完成的对齐保留原 k 与撤回意图。不能由重新核对、语音或自动两手识别解除撤回锁。

#### 3.5 提前两手、歧义与手动对齐

用 replayBaipuMatrix 预计算最多 B(k)/B(k+1)/B(k+2)，每个候选来自完整 steps（包括 removed），不按石子数量或“多了两颗”推断手数。普通 MoveDetector 确认一手仍走 apply 快路径。await 收到本版新鲜 baipu_board_observed，若整盘等于 B(k+2) 且不同于 B(k)，在没有已暂存提交时立即发新 revision verify；不等旧 10s timer，不额外推理。候选检查先于错色/多子诊断，合法提前摆好的子不被要求移除。若一手已暂存/正在应用，先完成它，再对新的 base 核对，不能用旧 k 再跳两手。事件与回执的 catch-up/失效规则保持。

自动窗口在 pass 或没有物理变化的步骤之前截断：不能通过最终盘面推测已经跨过虚手。到该步仍走明确的 pass 定时 apply；clear/AE 若确实改变盘面，可作为实际步骤核对。若不同 k 的最终矩阵仍相同（重复局面、特殊 setup 等），保留所有匹配项，连续确认同一匹配集合后发 ambiguous，停在原 k。页面用已有 Dialog 展示匹配手数及该步着法，用户选一项“核对此手”后新 revision align verify；不能点一下就跳谱。

选择状态契约：打开歧义/主动对齐 Dialog 时，前端同步进入 choosing 并冻结提交，保存原已提交 k、pendingUndo、恢复意图；撤臂/带当前 revision pause，不能只靠视觉遮罩。choosing 期间普通落子与旧 applied 不得改 k；选择说明可播一次，其他纠错语音停止。用户确认后先新 revision 唯一候选 verify，再按原序解除暂停；允许取消正在核对的选择。取消须立即失效临时 revision/待执行提交，按原 k+原 pendingUndo 新 revision fresh verify，再解除暂停，忽略旧 align/applied/语音回调；不能简单 unpause 原基准。已收到并提交成功的选择才关闭并作为新已提交状态；此后不把“取消”解释成无声回退。

超过自动两手范围、歧义、或用户认为当前进度不对时，恢复卡提供“对齐手数”：输入/步进选择 0..total_steps，预览该步棋盘和“核对第 N 手”，确认后只向 worker 提交这一份 canonical 候选。只选数字不改保存进度，只有新鲜核对且 applied 后直接写 toK；取消保留原 k，未完成就离开则取消临时选择，不存新手数。该入口是用户明确选择，不做全谱自动搜索；选错仍显示差异，可以换目标或取消，不要求清空整盘重来。

选择/核对过程中用户继续落子：按最新完整盘面检查，不能沿用选择前的旧观测；不能把尚未处理完的提子或额外棋子当成功。跨过终局只允许 toK≤total_steps。完成两手后给一条“已同步到第 N 手，继续摆谱”的屏幕提示，声音一次，不重放两次落子音。step 的计数仍是页面现有 steps[] 进度，不冒称双方各下了几手；pass/setup 必须显示其实际语义。

除了 move_confirmed/move_pending，摆谱的 illegal_change、board_lost、degraded、board_reacquired 也由 worker 写当前 stamp。当前版稳定 illegal_change 可启动 verify（优先排除已暂存提交/合法 ahead），处理误碰旧子而非只等用户发现；一次短暂缺帧不宣称摆错。手遮挡/光照状态没有可靠分类时只说“暂未看清”，不能凭差异推断是人手或阴影。

#### 3.6 交互与播报表（本次产品验收依据）

| 情况 | 屏幕与灯 | 自动语音与恢复 |
| --- | --- | --- |
| 应白实黑 / 应黑实白 | 屏幕“P8 需要白棋，请把黑棋换成白棋”；用移除闪灯定位，屏上画正确颜色；不同时给该点下互相矛盾的灯命令 | “这一手应摆白棋，请把标记处的黑棋换成白棋。”反向同理；换对后自动核对继续，不点确认 |
| 摆错位置/真实多子 | 屏幕给明确坐标，标出该取回点与谱上目标；只有不属于任何合法未来候选的子才称多子 | “标记处多了一颗棋子，请取回后继续。”先取回或先摆对都可以 |
| 误碰旧子/持续缺子 | 标仍需核对的位置，用“还没核对上”，不直接断言用户漏摆 | “有位置还没核对上，请检查屏幕标记处。”补回后自动收敛；不能用历史参考假装子仍在 |
| 正确落子但提子未完成 | 标出所选合法目标中确实还应拿走的位置；不把已正确落下的下一手蓝闪要求移除 | “请提走屏幕标出的棋子，拿完会自动继续。”允许先提后摆或先摆后提；完整匹配才提交 |
| 同时多处错误/候选诊断冲突 | 屏幕可标所有差异，文字先展示最明确一处；不规定修改顺序 | 一次只说最关键且确定的问题；不能按扫描顺序连续念几十个坐标。候选给出相反操作时用通用核对提示，不强猜颜色 |
| 已经提前一/两手且完整正确 | 自动核对并 applied，下一盏灯指向新进度；普通一手继续用原快路径 | 两手对齐后“已对齐棋谱，请继续摆放。”普通每手不播一句话，只保留落子音效 |
| 重复局面歧义 | 不猜手数；展示匹配步数，冻结提交并保留当前进度；跨 pass 不在自动候选内，走明确 pass 或手动对齐 | “盘面对应多个进度，请在屏幕上选择已摆到的手数。”选择后仍核对 |
| 超过自动两手/进度不确定 | 卡片可点“对齐手数”，预览目标；不自动前进任意步 | 通用核对提示一次，不声称用户违规或必须按机器节奏重摆 |
| 暂时看不清、手经过、普通阴影变化 | 保留 k，不显示成功；原视觉门控决定是否可继续 | 短暂变化不播警告。连续不可见超过现有 STUCK_MS 才一次“暂时看不清棋盘，请移开遮挡后再试”；没有证据不具体说手/阴影 |
| 网络/相机不可用 | 保留 k，显示连接状态与重试；不亮下一手成功灯 | 稳定 unavailable/error 时“识别暂时不可用，请查看屏幕后重试。”恢复后 fresh verify，不用旧读数成功 |
| 明确撤回、试下结束 | 提示应回到哪一步；撤回锁与暂停恢复规则保留 | “请把棋盘恢复到屏幕所示的局面。”只有目标 applied 才说恢复，不因点击按钮就播成功 |
| 修改正确并恢复 / 最终完成 | 恢复后显示新进度；末手提子未完不完成 | 曾有提醒的纠错结束后一次“盘面已核对，可以继续摆谱。”末手优先“这盘棋已摆完。”不同时播放恢复/两手/完成三句 |

语音给动作和颜色，坐标由屏幕文字与灯定位；首版使用固定中文 MP3，不引入实时在线 TTS、语音识别或拼接几百个坐标片段。语音是辅助：关闭、丢文件、浏览器拒播、扬声器不可用时，视觉与自动恢复仍可工作。

诊断先检查是否完整匹配合法候选，再分类差异。只有某点实际颜色不被任何允许候选接受、且所有候选在该点的非空目标颜色唯一时，才发明确换色提示；否则发通用“核对”。撤回/align 的唯一目标按该目标诊断。已有 MOVE_CONFIRMED 的错色证据沿用其确认，不再加一轮固定等待；其他 progress 差异需同一问题在 move_confirm_frames 个不同有效帧中持续（计数可与 verify 并行），无效帧中断，不能因一帧波动指责用户。

灯与具体操作不能由“最近候选”决定：Hamming最小/平局小k只可用于中性差异展示，不表示应恢复到该步，更不能要求拿回该候选之外但其他允许候选接受的正确棋子。普通恢复的多子灯/诊断排除所有允许候选中同坐标同颜色的合法占位，undo/align 则严格按指定目标。已确认正确落子且 removed 非空时，提子提示意图绑定该已确认步骤的 canonical 结果，不能因“新子1个、被提5个”距离最近 B(k) 而改成拿回新子；只提示该目标确实仍应拿走的点，候选冲突时改中性提示，完整提交仍看唯一全盘匹配。B2已有完整前缀却还有额外子时，提示可能超出自动范围、提供对齐手数，不强迫取回已合法提前的子。

#### 3.7 声音实现约束与防打扰

已读代码：BaipuSessionPage 目前仅 useSound('stone')；usePhysicalBaipu 没有 speak 命令。已有 useVoice 读取独立 voice 开关，从 /assets/sounds/voice/<name>.mp3 播放，单实例新句打断旧句；资产生成脚本为 scripts/generate_tsumego_voice.py，运行时由 server.py 的 /assets/sounds 挂载提供。复用这条链。

在新的纯函数 `baipuRecoveryFeedback.ts` 定义 `RecoveryProblem` 与 `VoiceDecision`，由 reducer 状态、canonical 候选和有编号的观测得出同一份屏幕/灯/语音意图；新 `useBaipuRecoveryVoice.ts` 只执行该意图，整页共用一个 useVoice 实例。不把 speak 放进等待目标的关键 Promise 队列，不等待音频结束后推进棋谱，不新增全局语音协调服务。

问题身份为 `{source,k,intent,kind,focusRow,focusCol,expectedColor}`，不含观测seq/revision，避免每帧/重核/WS重连重复播。同一稳定问题首次一次，不定时循环；不同纠错指令至少间隔8s，保持当前未解决focus，不因排序变化换key，只留最新有效意图、不排长队。健康阻塞与实际恢复/完成可立即打断，不受纠错8s间隔限制；成功提示在applied后且三类互斥，每回执一次。问题消失/换目标/暂停/离页取消旧句和timer；过代事件只能忽略，不能据它取消当前新句。短暂遮挡不提醒，超STUCK_MS才一次提示。

恢复卡内提供“重播提示”触控按钮（沿用现有控件，至少44×44），只重播当前仍有效的一句，不改变 k/revision、不触发核对。voice 关时说明“语音已关闭”，不暗中开启；沿用设备级 voice/sfx 两把设置，不能把关音效误当关语音。useVoice 兼容新增 playbackStatus（idle/playing/muted/unavailable），既有 speak/stop 签名保留；订阅现有 subscribeAudioPref 以在播放中关闭 voice 时立即 stop。play Promise 拒绝和 audio.onerror 标 unavailable，异步回调按当前播放身份校验，不能旧错误覆盖新句；卡片一次提示“语音未播放，可点重播”，不因失败重新开启声音或阻塞识别。

真实断线恢复：现 useVisionSync 的 onclose 不会创建新 socket，retryBind(null) 也不能重连。因此为该 hook 兼容新增 retryConnect，摆谱的“重试连接”调用它；其他消费者不改变默认策略。重试去重在途、关闭/替换旧socket，旧socket的onopen/onmessage/onclose均按实例身份丢弃；单次连接等待5s可失败并再次点击，卸载取消。只有新onopen后，摆谱生命周期才能 protected start→fresh verify，保留 k/pendingUndo。已连接的“重新核对”只处理目标，不能冒充重连。断链卡在 physical生命周期关闭时仍可见；重试中不点下一手、不播成功。用现有 useVisionSync.test.ts 的 fake WebSocket 真正触发 close→retry→open，不只翻mock布尔值。

连接重试同时保留本页 choosing/已确认的临时对齐意图：尚未确认的选择重连后只start撤臂，不能偷偷发自动entry目标；已确认待核对的目标在新代继续其唯一候选verify。只有用户取消才恢复原k/undo目标。断链时“核对此手”不可提交并显示连接原因；重试不绕过选择冻结。补一个选择中close→retry→open的既有异步用例，不能让生命周期重置将弹窗下的进度自动推进。

新增静态 VoiceName/生成脚本文案如下（中文文案逐字匹配资产；产品页面文案仍走 t()）：

| name | 文案 |
| --- | --- |
| baipu_black_to_white | 这一手应摆白棋，请把标记处的黑棋换成白棋。 |
| baipu_white_to_black | 这一手应摆黑棋，请把标记处的白棋换成黑棋。 |
| baipu_extra | 标记处多了一颗棋子，请取回后继续。 |
| baipu_check | 有位置还没核对上，请检查屏幕标记处。 |
| baipu_capture | 请提走屏幕标出的棋子，拿完会自动继续。 |
| baipu_not_visible | 暂时看不清棋盘，请移开遮挡后再试。 |
| baipu_unavailable | 识别暂时不可用，请查看屏幕后重试。 |
| baipu_choose_progress | 盘面对应多个进度，请在屏幕上选择已摆到的手数。 |
| baipu_restore | 请把棋盘恢复到屏幕所示的局面。 |
| baipu_recovered | 盘面已核对，可以继续摆谱。 |
| baipu_ahead_done | 已对齐棋谱，请继续摆放。 |
| baipu_finished | 这盘棋已摆完。 |

资产开发时生成并提交，RK3562 离线播放；不把依赖在线合成的首次等待放进用户纠错过程。脚本加 --only 白名单以只生成这12句，不重写现有围棋/标定音频；原脚本历史有服务403记录，合成一次失败可按现有离线 Tingting+ffmpeg 方式生成相同文案，不能为本需求长期排查TTS供应商。每个新增资产必须实际解码并听一次，中文方向、语速与设备音量正确，特别是“黑换白/白换黑”不能颠倒。

### 4. 文件责任与改动边界

| 文件 | 动作 / 责任 |
| --- | --- |
| `katrain/vision/baipu_recovery.py` | 新建；纯目标上下文、版本检查、完整候选比较与确认计数，不含 IO/棋规 |
| `katrain/vision/ipc.py` | 增加摆谱 control/target 两类 command；事件继续用现有 dict，不扩大 ConfirmedMove 对局契约 |
| `katrain/vision/sync.py` | 新增恢复健康门控小方法，复用既有 degraded 判据；旧 update 行为保持 |
| `katrain/vision/service.py` | 代号分配、请求检查与转发；其他识别 owner 改变时失效旧代 |
| `katrain/vision/worker_inprocess.py`、`worker.py` | 两种实际 dispatcher、帧身份、单次推理后核对、原子目标应用与事件 stamp |
| `katrain/web/api/v1/endpoints/vision.py` | 3 个摆谱路由和明确矩阵/版本验证；旧端点兼容 |
| `katrain/web/ui/src/api.ts` | 新请求/事件类型与封装；删除 raw adopt 用途的误导注释，其他 detected-board 消费者不改 |
| `katrain/web/ui/src/api/baipuApi.ts`、`baipuApi.test.ts` | 在已有进度记录增加兼容的 pendingUndo 可选字段；保存/清除与恢复意图保持一致 |
| `katrain/web/ui/src/kiosk/hooks/useVisionSync.ts`、`katrain/web/ui/src/kiosk/hooks/useVisionSync.test.ts` | 新事件、显式retryConnect与真实socket身份隔离，保留接收seq去重 |
| `katrain/web/ui/src/kiosk/hooks/physicalBaipuMachine.ts` | canonical 候选、版本、undo 锁、applied 后恢复/推进、syncing 状态 |
| `katrain/web/ui/src/kiosk/hooks/usePhysicalBaipu.ts` | 串行 IO、带版本控制、重试/失效处理、recheck 替换 adopt |
| `katrain/web/ui/src/kiosk/pages/BaipuSessionPage.tsx` | 提供 B(k..k+2)/step kinds、直接 toK 提交、进度选择、pass/AE 门控和短提示文案 |
| `katrain/web/ui/src/kiosk/hooks/baipuRecoveryFeedback.ts`、`baipuRecoveryFeedback.test.ts` | 新建纯诊断/播报决定，统一问题身份、优先级、语音和屏幕含义 |
| `katrain/web/ui/src/kiosk/hooks/useBaipuRecoveryVoice.ts`、`useBaipuRecoveryVoice.test.tsx` | 新建本页语音执行，去重、取消、重播与播放状态，不含棋谱推进 |
| `katrain/web/ui/src/kiosk/hooks/useVoice.ts`、`katrain/web/ui/src/utils/audioPrefs.test.ts` | 兼容增加播放状态与即时静音，回归现有消费者 |
| `scripts/generate_tsumego_voice.py`、`katrain/sounds/voice/baipu_*.mp3` | 加12句固定提示与 --only，复用静态挂载，不加运行时TTS依赖 |
| 下述精确测试文件 | 只覆盖此次状态完整性与最可能的旧路回归，不另建测试平台 |

### Task 0: 先确认新增交互的真实预览（未来获准实施后）

**Files:** Create `docs/superpowers/artifacts/baipu-recovery-interaction.html`；临时 Fixture `katrain/web/ui/src/kiosk/dev/BaipuRecoveryPreview.tsx`（最终删除）；预览接入点在 `katrain/web/ui/src/kiosk/pages/BaipuSessionPage.tsx`，仅 DEV 生效，生产前删除。

- [ ] **Step 1 — 基于已有系统画交互稿。** 用 @ui-ux-pro-max 读取现有 kiosk tokens、动作区和 Dialog，不另造视觉风格；产出同点错色/重播、两手成功、歧义选择、手动对齐四个同一恢复旅程状态，文案严格对照 §3.6。
- [ ] **Step 2 — 最小 Fixture 接入。** 用固定 k/候选/播放状态驱动真实页面部件，不调用识别控制接口；只有 DEV 预览入口可访问。模拟语音静音/失败必须明示为预览状态，不能流入生产。
- [ ] **Step 3 — 同 viewport 确认。** 1024×600 同时检查稿、实现截图、并排及叠加差异，记录文字、按钮44×44、动作层级、坐标/灯含义与状态差异；请用户明确确认新增交互后再进入当前切片后端阶段。Task 1 的只读事故用例整理可独立进行。
- [ ] **Step 4 — 记录确认并提交预览。** 记录在未来 verification 文档；无用户确认则留在该切片前端，不把自动化布局通过当视觉确认。Task 8 集成真实数据后删除 Fixture 和 DEV 接入，保留文档 Artifact。

### Task 1: 保存本次失败作为可重复的验收用例

**Files:** Create `tests/data/baipu_recovery_115_116.json`; Modify `katrain/web/ui/src/kiosk/hooks/physicalBaipuMachine.test.ts`, `tests/test_vision/test_move_detector.py`。

- [ ] **Step 1 — 固定证据。** 从 [持久化现场证据](../evidence/2026-10-21-baipu-recovery.json) 提取 canonical_before=B115、observed_and_erroneous_target=B116、confirmed_k=115、waiting_next=P8白与 following_move=J8黑，写入测试 fixture；不依赖临时目录。复核两矩阵差异恰好 P8，不复制整段浏览器状态或凭据。
- [ ] **Step 2 — 写 RED 用例。** reducer 测试完整模拟“错色 → setup → 下一手已在盘上 → 点击重新核对 → 成功继续两手”，断言 target 来自 canonical，P8 只被接受一次。当前版本应在 raw adopt/无法推进断言失败；不要把旧版错误行为写成期待成功。
- [ ] **Step 3 — 记录检测器边界。** Python 聚焦用例断言：`force_sync(B116)` 后再喂 B116 没有 P8 新落子；`force_sync(B115)` 后不同帧连续 B116 确认 P8。这条说明旧故障机制，保持现有检测器行为，不改它为强行重报已有子。
- [ ] **Step 4 — 运行并确认 RED。** 后端：`.venv/bin/python -m pytest tests/test_vision/test_move_detector.py -q`，应通过现有检测规则；前端（在 `katrain/web/ui`）：`npm exec vitest run src/kiosk/hooks/physicalBaipuMachine.test.ts`，新增恢复验收在旧版失败。保存失败原因，直到 Task 5 转绿。
- [ ] **Step 5 — 提交用例与 fixture。** `git add tests/data/baipu_recovery_115_116.json tests/test_vision/test_move_detector.py katrain/web/ui/src/kiosk/hooks/physicalBaipuMachine.test.ts`；`git commit -m "test: reproduce baipu recovery baseline drift"`。此测试提交后紧接实现，不作为可发布状态。

### Task 2: 实现有限的纯核对器与健康门控

**Files:** Create `katrain/vision/baipu_recovery.py`, `tests/test_vision/test_baipu_recovery.py`; Modify `katrain/vision/sync.py`, `tests/test_vision/test_sync.py`。

- [ ] **Step 1 — 写纯函数 RED 测试。** 覆盖 Bk/B1/B2、直接换色、拿放任意顺序、两手先后落子与最终提子、缺旧子、undo 只接受 Bk、窗口不跨 pass、不同步数同矩阵发歧义而非取 min/max。手动 align 选定唯一候选才可越过自动范围，仍需真实匹配。所有输入为完整当帧矩阵。
- [ ] **Step 2 — 写新鲜度 RED 测试。** started 前的 camera_ts、重复 camera_seq、旧 observation_seq、其他 gen/revision、相同 revision 改 body 均不能成功；同版 recheck 不清计数，candidate 改变清计数，无效帧中断。raw-voted 缺子而 reference 填回的例子不能成功。确认帧数从构造参数注入，测试用 2，生产读既有 config。
- [ ] **Step 3 — 运行 RED。** `.venv/bin/python -m pytest tests/test_vision/test_baipu_recovery.py -q`，应因模块/行为未实现失败。
- [ ] **Step 4 — 最小实现。** context保存immutable候选、版本/时刻/seq、匹配集合及streak、waiting_selection、applied或ambiguous缓存。Hamming仅中性展示，不决定取子/颜色/推进。歧义后本版锁定，recheck重发选择状态，不因下一帧唯一而应用；新revision才解除。下面确认逻辑使用context字段，过期/无效分支按前文处理：

公开接口为 Candidate(k:int,board:np.ndarray)、AmbiguousMatch(ks:tuple[int,...])、BaipuRecovery(generation,revision,candidates,opened_monotonic,confirm_frames)；observe(...)->Candidate|AmbiguousMatch|None；interrupt 清连续数不清目标，mark_applied 缓存实际应用结果，recheck 不重建目标。构造时 copy 数组；worker 先拒绝过代/过版，帧证据只来自真实处理线程。一个可直接落入测试文件的 RED 用例：

```python
import numpy as np
from katrain.vision.baipu_recovery import BaipuRecovery, Candidate


def test_p8_already_present_requires_two_distinct_new_frames():
    board = np.zeros((19, 19), dtype=int)
    board[11, 14] = 2
    ctx = BaipuRecovery(
        generation="page-a", revision=1,
        candidates=[Candidate(k=116, board=board)],
        opened_monotonic=10.0, confirm_frames=2,
    )
    frame = dict(raw_voted=board, observed=board,
                 observation_seq=8, camera_seq=21, camera_ts=11.0, valid=True)
    assert ctx.observe(**frame) is None
    assert ctx.observe(**frame) is None  # 同一真实摄像头帧不能凑数
    result = ctx.observe(**{**frame, "observation_seq": 9,
                           "camera_seq": 22, "camera_ts": 11.2})
    assert result is not None and result.k == 116
    assert np.array_equal(result.board, board)
```

重复帧不递增也不打断已有 streak（没有新证据）；真正无效帧/运动/遮挡应显式 interrupt。worker 只在基准应用成功后 mark_applied 缓存回执，不能在 observe 返回时提前标记成功。

```python
# 形状/取值由入口验证；每次这里只比较本帧完整结果。
if waiting_selection:
    return None  # 本版等待选择，不再自动应用
matched = tuple(sorted(c.k for c in candidates
                       if np.array_equal(observed, c.board)
                       and np.array_equal(raw_voted, c.board)))
if not matched:
    streak_ks, streak = (), 0
elif matched == streak_ks:
    streak += 1
else:
    streak_ks, streak = matched, 1
if matched and streak >= confirm_frames:
    if len(matched) > 1:
        waiting_selection = True
        return AmbiguousMatch(ks=matched)  # 不应用基准或提交手数
    return next(c for c in candidates if c.k == matched[0])
```

- [ ] **Step 5 — 健康门控测试与实现。** 测试 degraded 的原进入/退出迟滞、board_lost/恢复与正常 sync.update 原语义；恢复接口不得把一次低质图像显示成盘面匹配。`observe_recovery_health` 调用原 `_check_degraded`，发原健康事件，返回是否允许核对；不计算 legacy setup_complete、不改变阈值。
- [ ] **Step 6 — 运行 GREEN 并提交。** `.venv/bin/python -m pytest tests/test_vision/test_baipu_recovery.py tests/test_vision/test_sync.py tests/test_vision/test_sync_regressions.py -q`；预期全过。仅提交本任务的实现/测试，message `add canonical baipu recovery matching`。

### Task 3: 在两种 worker 接入真实应用确认

**Files:** Modify `katrain/vision/ipc.py`, `katrain/vision/worker_inprocess.py`, `katrain/vision/worker.py`, `tests/test_vision/test_worker_commands.py`; Create `tests/test_vision/test_baipu_recovery_worker.py`。

- [ ] **Step 1 — 两种 dispatcher 写 RED。** 用现有 fake camera/detector harness 分别创建两个 worker。start→target 后撤臂；验证相同 generation 下新 revision 生效、旧 revision/旧代 stop 无效；BIND/UNBIND/旧 monitor/geometry reset 必须结束旧摆谱上下文。
- [ ] **Step 2 — 帧与应用写 RED。** 同帧不重推理/确认，raw/reference不一致零应用；B2完整匹配应用一次，ambiguous后变唯一也零应用。真实MoveDetector遇两点同时新增不发move_confirmed，但board_observed仍触发verify；B1不额外verify。无一次模型成功，无帧/运动/几何早退仍发not_visible，恢复可见取消状态；重复camera_seq不立即称遮挡，持续冻结10s后带实际时长。旧sync目标应用后清空，baseline等于候选。
- [ ] **Step 3 — 运行 RED。** `.venv/bin/python -m pytest tests/test_vision/test_baipu_recovery_worker.py tests/test_vision/test_worker_commands.py -q`；新增协议测试应失败，既有 dispatcher 测试不得被删除。
- [ ] **Step 4 — 实现命令与唯一核对调用。** 两个dispatcher实现control/target，不解锁几何。average/vote/MoveDetector前共用去重；所有无帧/运动/几何/健康早退在await和verify均interrupt并更新not_visible，不附旧盘面、不伪造seq/置信度。可见恢复发一次checking；重复帧仅持续冻结达门槛才称不可见，主动暂停不提醒。单次推理两份矩阵按契约使用，核对中不跑旧setup完成分支。
- [ ] **Step 5 — 实现应用确认及 normal apply 校验。** 按 §3.2 应用结果候选，未成功不得布臂/发 applied；成功保存结果便于重发。normal apply 只允许同代/source_revision/confirmed_seq 支持的加一子结果；显式 pass 允许同矩阵 k+1 且不伪造 confirmed_seq。base k/board 必须与已应用结果一致，否则带 code error 并撤臂。摆谱 monitor move_confirmed 在两种 worker 的 unbound dict 分支写真实 observation_seq/stamp、缓存后立即撤臂，不改 bound 对局 ConfirmedMove 或死活题语义。
- [ ] **Step 6 — 钉住错误与兼容边界。** 在 force_sync 处注入异常：零 applied、armed=false；重复 recheck 不重复 force_sync；paused 时可应用但不布臂，resume 必须重新 verify；非摆谱 monitor、bound game、legacy setup 不新增事件编号要求。对旧接口原测试保持原样。
- [ ] **Step 7 — 运行 GREEN 并提交。** `.venv/bin/python -m pytest tests/test_vision/test_baipu_recovery_worker.py tests/test_vision/test_worker_commands.py tests/test_vision/test_service_monitor.py tests/test_vision/test_gating.py -q`；预期全部通过。message `apply baipu recovery targets atomically in both workers`。

### Task 4: 暴露窄接口，隔离页面生命周期

**Files:** Modify `katrain/vision/service.py`, `katrain/web/api/v1/endpoints/vision.py`, `tests/test_vision_api.py`; Create `tests/test_vision/test_baipu_recovery_service.py`。

- [ ] **Step 1 — service RED。** status→start CAS→新 start→旧 target/旧 stop，assert 旧代不影响新代；晚到旧 expected_generation 的 start 返回 409。已绑定会话/local confirmation 活跃 start 冲突；无 worker unavailable；同一 FIFO 收到 start/target/pause/stop 顺序明确。stop/其他 owner 接管后，旧代无效但 CAS token 不回到 null；服务重建生成的 token 不能与旧 token 碰撞。
- [ ] **Step 2 — API RED。** shape/strict整数/取值/0≤k≤total/revision 校验；普通 verify 最多3候选，只允许 k..k+2 且步数不同，重复矩阵合法并在 worker 发歧义；超过3或未选 align 却跨范围422。align 只有一个与 selected_k 一致的候选、不得 mode=apply。pass apply 单个同矩阵 k+1 合法不伪造 seq；普通 apply 仍只支持确认的一手。旧接口兼容。
- [ ] **Step 3 — 运行 RED。** `.venv/bin/python -m pytest tests/test_vision/test_baipu_recovery_service.py tests/test_vision_api.py -q`，新增路由/检查失败。
- [ ] **Step 4 — 实现最小 wrapper 与验证。** VisionService 使用 token+active 标记，原 status 返回 token；同步 start CAS 后入队，后续 target/control 验证当前 active token。发 WorkerCommand，不另开线程。body 用 strict integer/shape 验证；pause/stop 也带代号，generic monitor/bind 的所有权变更会失效旧代。API 不改浏览器进度。
- [ ] **Step 5 — GREEN 并提交。** 运行 Step 3 同命令，预期通过；检查旧 `/setup-mode`、`/expected-board`、对局 bind、死活题 monitor 用例仍绿。message `expose versioned baipu target synchronization`。

### Task 5: reducer 以 canonical 确认驱动恢复

**Files:** Modify `katrain/web/ui/src/kiosk/hooks/physicalBaipuMachine.ts`, `katrain/web/ui/src/kiosk/hooks/physicalBaipuMachine.test.ts`, `katrain/web/ui/src/kiosk/hooks/useVisionSync.ts`。

- [ ] **Step 1 — 写 RED 状态测试。** applied 验证本版候选后才 onReconciled；回执重复只消费一次。Bk 保持，B1/B2 直接提交目标 k 一次，不能连调 +1；错误颜色/歧义零推进。align 只接受明确选择的候选，取消不变进度。普通/两手/提子/pass 末手 ack 前不 done，ack 后完成一次。
- [ ] **Step 2 — undo RED。** undo 后 O=Bnext 持续出现不提升，recheck/pause/resume/reconnect 仍不能提升；O=Bk 达到确认后解锁，再放下一手才推进。该例专门防“撤回被自动抵消”。
- [ ] **Step 3 — RED 运行。** 在 `katrain/web/ui`：`npm exec vitest run src/kiosk/hooks/physicalBaipuMachine.test.ts`，预期 Task 1 与新增用例失败。
- [ ] **Step 4 — 最小状态迁移。** 增加TARGET_PROGRESS/APPLIED/ERROR/AMBIGUOUS及CHOOSING/CANCEL事件，禁止裸SETUP_COMPLETE推进。LED和页面extraMarks排除全部允许B1/B2正确占位，undo/align按唯一目标。已确认提子意图绑定该步canonical结果；补五子提子未拿/合法B2占位伴其他差异两例，不能要求取回正确新子。choosing冻结提交，取消撤销临时版并fresh verify原目标。
- [ ] **Step 5 — 保留正常路径。** MOVE_CONFIRMED 只接收当前 stamp，位置/颜色严格相等；正确后暂存 k+1，发 canonical apply 或 capture verify，phase=syncing/setup，无 matched。只有 TARGET_APPLIED 才进入 advancing、matched，并在页面 k catch-up 后 next LED 恢复。MOVE_PENDING 熄灯/RELIGHT 的 3s 机制原样覆盖。
- [ ] **Step 6 — GREEN 并提交。** 同 Step 3，预期全过，含 Task 1 P8 回归。message `reconcile baipu progress from canonical target acknowledgements`。

### Task 6: hook 串行交接、重试与页面自然操作

**Files:** Modify `katrain/web/ui/src/api.ts`（含 VisionStatusResponse）、`katrain/web/ui/src/kiosk/hooks/useVisionSync.ts`、`katrain/web/ui/src/kiosk/hooks/useVisionSync.test.ts`、`katrain/web/ui/src/api/baipuApi.ts`、`katrain/web/ui/src/api/baipuApi.test.ts`、`katrain/web/ui/src/kiosk/hooks/usePhysicalBaipu.ts`、`katrain/web/ui/src/kiosk/hooks/usePhysicalBaipu.test.tsx`、`katrain/web/ui/src/kiosk/pages/BaipuSessionPage.tsx`、`katrain/web/ui/src/kiosk/__tests__/BaipuSessionPage.test.tsx`。

- [ ] **Step 1 — API 与 options 类型。** 传入 canonical Bk/B1/B2、total_steps、step kinds、pendingUndo；窗口在 pass 前截断。onMatched 改为 onReconciled({fromK,toK,generation,revision})，只在实际 applied 后执行；functional updater 校验 prev===fromK 及消费编号，直接写 toK/存一次。align 由用户选 selected_k 后生成唯一 canonical 候选，不用快照建目标。
- [ ] **Step 2 — 写完整 hook RED。** 保留事故/错色/任意纠正顺序/undo用例，增加 B2 applied 后直接提交2步一次、重复回执不多跳、总步数边界、合法提前子不蓝闪或播错色。await 的新版 board_observed 完整匹配 B2 立即 verify，不等10s；已有 staged 一手则先完成并按新 k 重核。歧义/手动对齐先选步数再 fresh verify，取消/选错不改进度。
- [ ] **Step 3 — 写异步 RED。** 保留同版完整body/缓存ack/source失效/换代/catch-up；新增未settle HTTP5s后共享队列可退出，远端未知仍幂等重试。弹窗期间move不提交；取消已发align后旧applied晚到不提交；原k/undo新verify可恢复，旧pause不冻结新版本。用fake WebSocket实际close→retry→open：旧socket回调隔离，onopen前无新target，保留k与undo。
- [ ] **Step 4 — 运行 RED。** UI运行 `npm exec vitest run src/kiosk/hooks/useVisionSync.test.ts src/kiosk/hooks/usePhysicalBaipu.test.tsx src/kiosk/__tests__/BaipuSessionPage.test.tsx`；新socket/选择状态用例应在旧版失败，不只手动切mock布尔值。
- [ ] **Step 5 — 实现队列与事件 catch-up。** 文件级共享队列串行，新的HTTP封装5s deadline保证settle；发送/返回/提交/灯/语音均检查life与revision及choosing。protected start有限CAS重试；断链走retryConnect，等实际onopen再新start/verify。advancing不越过processedSeq，先k/next catch-up再续跑事件，裁剪缺口转verify。
- [ ] **Step 6 — 页面、持久撤回和末手。** 保持既有恢复卡/动作区；只对进度歧义/主动对齐使用原有 Dialog，不卡正常正确落子。提供按状态生效的重新核对、恢复卡内重播提示及对齐手数。pendingUndo 与 k 原子保存，指定目标 applied 才清，k=0/重挂载覆盖；手动align可显式替换目标但取消不能解除旧撤回。普通/两手/提子/pass末手都在 applied 后 done；manual/collect 保持。
- [ ] **Step 7 — 10s 补救与计时测试。** 只读快照等于 Bk/读取失败时不灭灯；等于不同的 Bnext 且 lifecycle/generation/revision/k/phase 未变、无未结束 pending 才新 verify。加入延迟快照期间收到 MOVE_PENDING 或已进入新 revision/setup 的用例，必须取消补救，不重置正常确认。每 k 最多自动检查一次，主动按钮仍按状态表可恢复。未完成 verify 的同版 recheck 不清计数；卸载取消 timer。
- [ ] **Step 8 — GREEN 并提交。** UI 运行 `npm exec vitest run src/api/baipuApi.test.ts src/kiosk/hooks/useVisionSync.test.ts src/kiosk/hooks/physicalBaipuMachine.test.ts src/kiosk/hooks/usePhysicalBaipu.test.tsx src/kiosk/__tests__/BaipuSessionPage.test.tsx`，预期全部通过；message `simplify baipu correction and guard asynchronous recovery`。

### Task 7: 把错色提醒接入现有语音链

**Files:** Create `katrain/web/ui/src/kiosk/hooks/baipuRecoveryFeedback.ts`、`katrain/web/ui/src/kiosk/hooks/baipuRecoveryFeedback.test.ts`、`katrain/web/ui/src/kiosk/hooks/useBaipuRecoveryVoice.ts`、`katrain/web/ui/src/kiosk/hooks/useBaipuRecoveryVoice.test.tsx`；Modify `katrain/web/ui/src/kiosk/hooks/useVoice.ts`、`katrain/web/ui/src/utils/audioPrefs.test.ts`、`katrain/web/ui/src/kiosk/pages/BaipuSessionPage.tsx`、`katrain/web/ui/src/kiosk/__tests__/BaipuSessionPage.test.tsx`、`scripts/generate_tsumego_voice.py`；Create §3.7每个name原样加.mp3的12个 `katrain/sounds/voice/` 文件（例如 baipu_black_to_white.mp3）。

- [ ] **Step 1 — 固定纯反馈契约。** 新类型 RecoveryProblem={kind,key,focus,expectedColor,voiceName,textKey}；deriveRecoveryFeedback 输入 canonical candidates、带版有效观测/已确认错子、恢复意图，输出单一当前问题或 null。先完整候选匹配/歧义，再诊断；当前 focus 尚未解决时保持它，不因数组排序换播。UI、灯和语音用同一问题，不分别猜测。
- [ ] **Step 2 — 写 RED 分类用例。** 正反错色、错位/多子、旧子不确定、多处冲突、undo/align唯一目标；补五子提子未拿时只说提子不拿回新子、合法B2占位与其他差异并存不误报多子、B2前缀完整但多子时提供手动对齐。用直接颜色断言name/文本方向一致。核心例：

```ts
it('应白实黑：语音明确要求黑换白，实际改正后无旧问题', () => {
  const before = Array.from({ length: 19 }, () => Array<number>(19).fill(0));
  const goal = before.map(r => [...r]); goal[11][14] = 2;
  const observed = before.map(r => [...r]); observed[11][14] = 1;
  const input = { source: 'kifu_178448', k: 115, intent: 'follow' as const,
    candidates: [{ k: 115, board: before }, { k: 116, board: goal }],
    observed, valid: true };
  expect(deriveRecoveryFeedback(input)?.voiceName).toBe('baipu_black_to_white');
  expect(deriveRecoveryFeedback({ ...input, observed: goal })).toBeNull();
});
```

- [ ] **Step 3 — 写 RED 播放策略用例。** 同一问题50帧/重核/WS重连只播一次；连续两处不同问题受8s间隔约束，timer 到时旧问题已解决则不播；短遮挡不播，超过 STUCK_MS 一次中性提示。问题修好立即 stop 旧句，保留 hadWarned 标志直到 applied 才播恢复；普通每手不说话。两手/恢复/完成成功语音互斥。重播按钮只重复当前问题，不发API、不推进或重新核对。
- [ ] **Step 4 — 运行 RED。** UI：`npm exec vitest run src/kiosk/hooks/baipuRecoveryFeedback.test.ts src/kiosk/hooks/useBaipuRecoveryVoice.test.tsx src/utils/audioPrefs.test.ts`；新增模块/策略未实现应失败，旧声音设置用例保持。
- [ ] **Step 5 — 实现纯反馈与薄语音 hook。** 独立 useVoice 实例由本页 hook 持有，输入当前问题/目标/暂停/实际 applied，输出 replay/播放状态。speak/stop 非阻塞执行，自动指令按 lifecycle/当前问题 key 校验；不串进关键识别队列。没有可靠问题分类时只给通用核对语，不拿 mean confidence 推断是手或阴影。
- [ ] **Step 6 — 兼容播放器与故障用例。** 新增 playbackStatus 与即时静音订阅，既有 speak/stop 不改调用签名。Audio.play 拒绝、audio.onerror、旧句失败晚到、用户静音/卸载时取消均有聚焦测试；失败不阻塞 onReconciled，不假装已听到。重播按钮按 voice 设置决定可用状态，页面错误提示只在真实播放失败后出现。
- [ ] **Step 7 — 生成限定资产。** scripts/generate_tsumego_voice.py 的 LINES 加 §3.7 的12句，增加 argparse --only（choices=LINES.keys，缺省保持原脚本行为）。实施时运行 `uv run --no-sync python scripts/generate_tsumego_voice.py --only baipu_black_to_white baipu_white_to_black baipu_extra baipu_check baipu_capture baipu_not_visible baipu_unavailable baipu_choose_progress baipu_restore baipu_recovered baipu_ahead_done baipu_finished`；只提交这12个新MP3，既有资产校验和不变。合成供应商一次失败可用已知离线方案，运行时不得在线合成。
- [ ] **Step 8 — GREEN 与资产验收。** 运行 Step 4 及 BaipuSessionPage 测试，全部通过；逐个用 ffprobe 解码确认时长非零，听正反换色两句及其余短语，真实 /assets/sounds/voice/<name>.mp3 返回音频且可播，不以 HTTP200 代替听验。确认改正中途旧语音立即停止，声音关闭时视觉恢复正常。提交 `add actionable baipu recovery voice guidance`。

### Task 8: 聚焦集成验收与真实预览

**Files:** Modify `katrain/web/ui/src/kiosk/__tests__/BaipuSessionRoute.test.tsx`（如现有 page 测试不能覆盖路由重连才扩展）；记录验收到 `docs/superpowers/reviews/2026-10-21-baipu-recovery-verification.md`（未来实施时创建）。

- [ ] **Step 1 — 串起事故与新增交互。** 真实 reducer/hook、canonical replay 与 mock transport 重放 P8/J8事故及错色语音→自由纠正→恢复后两手；一次提前两手直接到 toK；歧义选择/手动选错取消；撤回重挂载；重复回执/语音；短遮挡与不可用。确认页面/保存k、baseline、next、灯一致；语音不承担推进，普通/两手/提子/pass末手先 ack 后 done。
- [ ] **Step 2 — 聚焦后端回归。** 在 repo 根目录运行 `.venv/bin/python -m pytest tests/test_vision/test_baipu_recovery.py tests/test_vision/test_baipu_recovery_worker.py tests/test_vision/test_baipu_recovery_service.py tests/test_vision/test_worker_commands.py tests/test_vision/test_sync.py tests/test_vision/test_sync_regressions.py tests/test_vision/test_service_monitor.py tests/test_vision/test_gating.py tests/test_vision_api.py -q`。预期全过；仅为具体失败扩大范围，不跑与本次无关 AI/全服务套件。
- [ ] **Step 3 — 聚焦前端与生产构建。** UI 运行 `npm exec vitest run src/api/baipuApi.test.ts src/kiosk/hooks/useVisionSync.test.ts src/kiosk/hooks/physicalBaipuMachine.test.ts src/kiosk/hooks/usePhysicalBaipu.test.tsx src/kiosk/hooks/baipuRecoveryFeedback.test.ts src/kiosk/hooks/useBaipuRecoveryVoice.test.tsx src/utils/audioPrefs.test.ts src/kiosk/__tests__/BaipuSessionPage.test.tsx src/kiosk/__tests__/BaipuSessionRoute.test.tsx`，删除临时 Fixture/DEV入口后 `npm run build:smartbox-kiosk-2d`。预期全部通过，生产无模拟盘面。
- [ ] **Step 4 — 1024×600 真实页面核对。** 在本地真实 kiosk 页面显示普通等待、同点错色、核对/同步失败三个本次受影响状态，检查短文案、按钮可点、无溢出，保存代表截图。已有布局不重做设计系统；如局部文案导致布局调整，先让用户确认真实预览再继续该 UI 调整。
- [ ] **Step 5 — Astra Max 独立代码审核与修正。** 未来获准实施后按用户既定流程做代码审核，修具体问题并补对应回归；本轮只审计划，不启动代码审核或部署。
- [ ] **Step 6 — RK3562 设备验收（实施/部署另授权后）。** 独立测试进度，实际听正反错色语音，分别直接换色/先拿后放/先摆对再拿错；提前两手/含提子两手、歧义与手动选进度、撤回重进、手短暂经过、静音/重播/拒播提示各一次，恢复后再连续摆两手。记录物理改正到 applied 的帧数/耗时及FPS；普通落子不新增整盘窗口，两手检测不等10s；每帧最多一次推理。喇叭未实际听到或存在停滞，不宣称设备验收通过。
- [ ] **Step 7 — 完成前证据。** 使用 @superpowers:verification-before-completion 汇总命令、提交与真实设备结果；用户允许集成发布时再按仓库 AGENTS 顺序追 develop、合入、更新 submodule、部署。此计划没有授权现在执行任何一步发布。

### 5. 实施依赖与适度并行

Task 0 先完成同一恢复旅程新增交互的视觉确认；Task 1 事故整理可独立进行。契约稳定后 Task 2→3→4 为共享基础；Task 5 可由独立前端子代理按契约并行。Task 6 集成后，Task 7 语音闭环，Task 8 真实验收并删除 Fixture。两种 worker 由同一任务维护；不同时铺开未确认的页面切片。

### 6. 本轮计划审核与停止条件

- 原版单步计划审核归档，不代替本次新增交互/语音的审核；本次按用户新要求独立最多两轮。
- Astra Max 本次第 1 轮：审修订计划与设计，对照真实代码，重点查两手/歧义/语音和范围，主代理修改。
- Astra Max 本次第 2 轮（仅有必要时）：复核修改与剩余风险；主代理修订文档并记录结果，最多两轮。
- 两轮后报告通过/未解决项；停在文档阶段。**不执行 Task 0–8、不改产品代码、不提交部署，不因计划完成自动开始 subagent-driven-development。**
- [本次两轮评审记录](../reviews/2026-10-21-baipu-recovery-interaction-review.md)已保存，第二轮 Approved，无阻塞项；未进行第三轮或开始 Task 0–8。
