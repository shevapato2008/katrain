# 摆谱纠错恢复 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复“错色 → 纠正 → 点击继续 → 基准吞掉下一手”的摆谱死锁，让用户按任意拿放顺序恢复当前或下一手，同时保留明确撤回的含义。

**Architecture:** 棋谱回放得到的 `B(k)` 是唯一盘面事实。摆谱沿用现有 reducer、worker 图像处理和串行队列，增加一个小型、仅摆谱使用的目标同步协议：worker 对当前/下一手候选核对，实际同步 canonical 基准后发回带生命周期和目标版本的确认；前端收到确认才结束恢复。正常落子仍用已有 MoveDetector 快路径，不每手重新跑整盘纠错。

**Tech Stack:** Python / NumPy / FastAPI / 现有进程内及多进程 vision worker；TypeScript / React / Vitest；pytest。无新依赖、数据库或图像模型。

---

**状态：计划文档；未实施。** 用户要求本轮完成调查、计划、Astra Max 独立审核并修改最多两轮后停止。下面所有复选框是未来实施步骤，本轮不运行其中的产品修改、发布或设备写入操作。

**审核状态：** 已完成正式两轮。第 1 轮六项问题、第 2 轮最后的主动重核/在途确认入口问题均已按意见修订；第 2 轮报告原结论保留 Issues Found，最终修订未追加第三轮独立复核。详见 [审核与修订记录](../reviews/2026-10-21-baipu-recovery-plan-review.md)。

**设计依据：** [原因与流程设计](../specs/2026-10-21-baipu-recovery-design.md)。代码基线 `3da3e50360db96072ade5a3b6d0bdf596f48d987`，发布 develop 合并点 `c65e410cb148e734635ed6b5bcf782e13fab6bed`。

## Chunk 1: 从真实失败到可执行修复

### 1. 已核实的原因与范围

现场 `kifu_178448`：页面 `k=115`，等待白 P8（总第 116 手）；canonical `B(115)` 不含 P8，machine target 和实际识别盘面却都含 P8，共 116 子。唯一不一致点为 `(row=11,col=14)`。日志中 P8 白子与 J8 错色已有记录；用户确认点过“摆好了，继续”，完整点击顺序不可还原。

现有 `adopt()` 把整盘摄像头读数设为 setup target，却不更新 `k/next`；reducer 又禁止 adopt 路径提升下一手。setup 完成后 `force_sync()` 吞入 P8，界面继续等同一个 P8。真实 reducer 与 MoveDetector 已离线复现；这不是靠异常堆栈定位的崩溃，而是三份状态不一致。

本次修改只覆盖摆谱的恢复与目标交接。预览线程、标定页、识别模型、阴影/手部判据、其他棋类及全谱跳步不在范围内。稳定盘面持续漏识别仍可能延迟核对；本次不以“忽略缺子”掩盖该问题。

### 2. 必须保持的规则

1. 任何基准只能来自 `replayBaipuMatrix(steps,k,size)`；摄像头结果只作证据。删除摆谱 raw adopt 入口。
2. 一般恢复可接受 `B(k)` 或 `B(k+1)`，精确包含颜色与 `removed`。匹配前者只恢复等待，匹配后者只推进一次。不自动倒退或跨多手。
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
| `POST /baipu/control` | `{generation, action:'pause'|'stop'|'recheck'}`；pause 另带 `paused:bool`；recheck 带 revision | 暂停、按同一版本重发状态、或结束本代。stop 同步清除 monitor/pause/armed/摆谱上下文；过时代号不能影响新代。 |

同一 VisionService 保存 opaque generation token、当前 revision 和当前小型上下文，无租约服务或新持久化系统。现有 `GET /vision/status` 增加 `baipu_generation:string|null`；start 的 expected_generation 与服务现值相等才更新 token，避免浏览器 reload 后旧 start 晚到覆盖新页面，随机 token 也避免服务重启后复用整数。读取并 CAS 更新在一个同步 service 方法内完成；冲突时仍活跃的 hook 最多刷新状态重试一次，其他情况显示重试入口。

start 与 target 使用同一 worker FIFO；前端在 `usePhysicalBaipu.ts` 文件级保留一条共享 IO Promise 队列，所有 hook 实例的 start/target/control/cleanup 均串行，每次发送和 await 返回后检查各自生命周期。hook 内 queueRef 不能保证跨卸载/重挂载的顺序，不能用它代替共享队列。旧 generation 的 cleanup 无效果，不清理新页面。服务停止本代后保留最后 token 作 CAS 栅栏，单独标记 inactive；其他 owner 接管时换新 token 并标记 inactive。

```ts
interface TargetRequest {
  generation: string;
  revision: number;              // 同一 generation 单调递增
  k: number;                     // 页面已确认的谱步骤，非棋子数量
  board: number[][];             // 当前已提交 B(k)，始终 canonical
  mode: 'verify' | 'apply';
  reason: 'entry' | 'wrong' | 'undo' | 'restore' | 'capture' | 'recheck' | 'advance' | 'clear' | 'pass';
  candidates: Array<{ k: number; board: number[][] }>; // 可提交结果，1–2个
  source_revision?: number;      // apply 快路径的落子来源
  confirmed_seq?: number;        // apply 快路径的落子证据
}
```

矩阵严格为 19×19、整数 0/1/2；k 非负整数，revision 至少 1；候选 k 只允许请求 k 或 k+1，不重复。verify 允许 1–2 候选；相同矩阵的两个候选不允许自动选择更大 k。apply 恰好一个 k+1 候选：普通落子只能是本代最近正确落子对应的“原基准加一子”，不能绕过移子/提子核对；其 source_revision/confirmed_seq 必须与 worker 缓存的最近确认一致。显式 pass 的候选与当前矩阵相同，不要求或伪造 confirmed_seq。两种情况都要验证请求 B(k) 与 worker 当前已应用基准、effective k 相符。其余情况发带编号的 baipu_target_error，保持撤臂。

处理 apply 新 revision 时，先用保存的上一版确认及已应用基准验证 source，再替换上下文；不能先清缓存/改 revision 导致所有合法 source 自己失效。确认缓存只供这一次 canonical 交接，成功后消费；同版重试走已缓存 applied，不重新消费证据。

worker 开始处理新目标时记录 `opened_monotonic`，verify 只用其后采集、camera_seq 严格递增、observation_seq 严格递增的有效帧。同版重复 target/recheck 不重建目标、不清投票、不重置窗口；已完成时重发同一个 applied 结果。更低 revision 忽略并可返回 stale 状态；更高 revision 取代旧版本，撤臂并使旧证据失效。重用相同 revision 却改变 body 属于错误，不能静默改目标。

#### 3.2 事件

```ts
type BaipuStamp = { generation: string; revision: number; observation_seq: number };
// worker 完成原子应用后才发布：
type Applied = BaipuStamp & { k: number; board: number[][] };
// 核对提示针对当帧最接近的一个合法候选，不拼接不同时刻的棋子：
type Progress = BaipuStamp & {
  candidate_k: number;
  missing: Array<[number, number]>;
  extra: Array<[number, number, number]>;
  status: 'checking' | 'not_visible';
};
```

事件名为 `baipu_target_progress`、`baipu_target_applied`、`baipu_target_error`。现有 `move_confirmed/move_pending` 在摆谱拥有 monitor 时加同一 stamp；其他消费者保持原字段和行为。前端 `useVisionSync.seq` 只是接收序号，继续用于消费去重，不能当摄像头帧号。

`baipu_target_error` 附 code：source_stale（新 revision verify）、apply_failed（撤臂，新 revision verify）、unavailable/stale_generation（重新受保护 start，最多自动重试一次）、invalid_target（显示错误，不自动循环）。传输错误不伪造 worker error：若不知道完整 target 是否入队，保存并重发同版完整 body；不能只发一个 worker 可能不认识的 recheck。重发已应用 target 返回原 applied。

摆谱 monitor 的 move_confirmed 在 worker 内缓存真实来源后立即撤臂，再发带 stamp 的事件，等待目标交接；其他 monitor 不改。这样在网络错误时也不会继续接收多手并覆盖本次缓存。无网络连通时前端不能承诺远端命令已经执行，只冻结提交并显示连接状态；恢复后 start/verify 重新建立一致状态。

applied 顺序（worker 同一处理线程）：撤臂 → `_sync.reset(canonical_board)` 清除 setup/capture 旧目标 → `_sync.set_expected_board(canonical_board)` → `_expected_np=copy` → `_move_detector.force_sync(canonical_board)`（相同且已有干净基准时不重置候选）→ 保存 effective k/当前结果 → 若未暂停则布臂 → 入队 applied。任何一步失败不发 applied、不布臂，发送 error。不能调用 API RESET_SYNC：其几何/参考副作用超出恢复范围。worker 必须先入队 applied，后处理后续帧的落子事件。

新的恢复请求在 worker 生效之前，旧 worker 结果可能已经产生；前端按 generation/revision 忽略它，直到新请求核对成功。不会把暂时的旧基准当成功反馈。

#### 3.3 候选与确认策略

| 入口 | mode / 候选 | 前端提交时机 |
| --- | --- | --- |
| 进场、错子、重新核对、试下恢复、重连 | verify：`B(k)` 与不同于它的 `B(k+1)`；仅有实际物理变化的步骤可提升 | applied.k=k 只恢复；=k+1 调用一次 guarded onMatched |
| 明确撤回及尚未完成撤回的其他入口 | verify：只有 `B(k)` | 到 applied 才解除撤回锁，k 不推进 |
| 正常 MoveDetector 已确认正确落子、没有提子/改色 | apply：结果候选只有 `B(k+1)`，带真实 source_revision/confirmed_seq | 暂存该决定，收到 applied 后才提交 k+1；无额外整盘/新帧等待 |
| 正常确认后有提子 | verify：`B(k)` 与 `B(k+1)`，保留拿放自由 | 提子等物理变化完成且 applied 后才提交 k+1；若摆回 B(k) 则恢复原等待 |
| clear/AE | verify：只接受 `B(k+1)` | 按 removed 清理完成后推进；不能继续沿用无条件 500ms 定时跳过 |
| pass、或没有物理变化的明确步骤 | 先确保当前目标已 applied，再沿用 500ms 定时发显式 pass apply，结果为相同矩阵的 k+1 | applied 后推进，不凭相同矩阵推测虚手，不因重连重复跳 |

verify 复用 config `move_confirm_frames` 对连续相同候选进行确认，不增加秒级固定等待；重复 camera_seq 不累计，候选改变或有明确差异则清零。无效帧/遮挡中断连续确认但保留目标。不能在旧帧基础上累计不同位置的“曾经正确”。正常 apply 不重新进行这轮确认。

新 verify 目标清理旧图像平均及 per-cell 投票累积（进程内优先复用 `_reset_local_accumulators(reset_motion=False)`），不重置几何/相机，不反复重置 motion 稳定状态。不为重新核对丢弃有效参考图。核对成功必须同时满足两份完整矩阵相等于候选：raw-voted（进程内为合法 deny 掩码后的 `denied_stable`，尚未 reference_check）以及 reference-corrected 的 observed_board。多进程没有该参考层时两份取同一投票结果。这是保守核对：不让参考填补掩盖真实缺子，也不绕过参考的假阳性否决；一份不符就继续核对，不合并时刻/位置。持续漏识别的代价已在设计边界中明确。

摆谱拥有 monitor 时，进程内与多进程都使用已有 read_frame_identified，并在图像平均、投票和 MoveDetector **之前**按 camera_seq 去重；normal 与 verify 共用这道门，其他消费者读帧语义不改。没有新帧就不重复推理/累计候选，仍处理命令和上报状态。verify 再校验采集时刻晚于窗口建立及观测序号。在原有单次推理结束后调用核对，不增读摄像头、不做第二次推理。无帧身份的设备报告 unavailable，不回退到“循环次数就是新帧”。

健康门控沿用 `SyncStateMachine` 的 board_detected/degraded 判据：在 sync.py 提供小型 `observe_recovery_health(...) -> (allowed, events)`，内部复用现有 `_check_degraded` 与原阈值/迟滞；正常 `update` 不改语义。恢复分支只调用一次健康门控，避免旧 setup 自动完成并产生裸完成事件。geometry_ready、motion_stable、有效识别仍是前置条件。真正有差异时发 progress；尚未看清只发 checking/not_visible，不宣称用户一定漏摆。

#### 3.4 前端状态与失效规则

在已有 phase 中增加 `syncing`（命令已发，等实际应用）；`setup` 表示有效目标正在核对；`await` 只在本版应用确认之后成立。`advancing` 是已接受一次、等待页面 k 更新的屏障。恢复版本、候选盘面与撤回锁在 reducer/hook 中单点维护，不再从 raw board 构造 target。

所有摄像头路径统一为 staged → worker applied → guarded onMatched(expectedK)，包括普通 move_confirmed。普通正确落子只暂存 canonical B(k+1)，发 apply；没有新帧或整盘确认窗口。applied 前不更新页面/存储 k；applied 后 target 精确等于返回候选，只有 k=当前k+1 才 matched 一次。页面 k 更新若来自本次 applied，只更新 next/灯，不能重新发送旧 B(k)。末手因此在最终 canonical（含提子）applied 之后才进入 done/清进度，不会提前卸载物理 hook。手动和采集模式仍沿用原推进。

applied 与下一条 move_confirmed 可能在同一 WS 批次：advancing 等页面 k/next 追上时，不消费余下事件、不越过 processedSeq；k/next catch-up effect 必须先更新 machine，事件消费 effect 再续跑。恢复到 await 后可消费同版本下 seq>applied.seq 的后续事件。若 MAX_EVENTS 裁剪导致序号缺口，启动当前 canonical 的新 verify，不能静默遗失后永久等待。测试必须证明后续落子继续，不能只验证“没 +2”。

“重新核对”的动作按当前状态决定，不能总重放旧 applied：

| 按下时状态 | 动作 |
| --- | --- |
| 未完成的 verify，目标已在 worker | 同 generation/revision 请求 progress，不重置累积 |
| target 传输结果未知、或等 ack | 重发保存的同版完整 body；已完成则返回缓存 applied |
| await，旧目标已经 applied | **新 revision verify** 当前 canonical B(k)/B(k+1)，才能核对后来放上的下一手；保留 pendingUndo 限制 |
| source_stale/apply_failed | 废弃错误 apply，新 revision canonical verify |
| 无有效 generation | 受保护 start 后 verify |

保留已提交 k，错误时停在 setup/syncing，不吞异常继续布臂/点灯。应用确认超过 5s 未到且没有 progress 时显示可重试，不无限重试终态错误。按钮沿用已有动作区：setup 超时、同步错误、或 await 超过 10s 时可用，不限于旧版 setup.stuck；manual/collect 不新增此按钮。自动补救取消或已经用过后，用户仍有明确入口。

await 10s 无推进时，仅调用现有只读 visionDetectedBoard 一次；只有完整匹配不同于 B(k) 的 canonical B(k+1) 才触发 verify。请求时捕获 lifecycle/generation/revision/k/phase 与待确认活动标记，返回时全部仍相同且仍为 await 才能触发；若同版已有未结束的 MOVE_PENDING，或请求期间出现 pending/confirmed，则取消此次自动补救，保留正常确认窗口。快照只触发核对，不能充当成功证据或基准。快照仍为 B(k) 时保持下一手灯。每 k 最多一次自动检查，主动 recheck 按上表可重新 verify；无周期重置或新增推理。

暂停先撤臂且暂停图像确认；恢复建立对应 canonical verify 目标后再解除暂停。撤回时在现有 BaipuProgress 与 k 一起保存可选 pendingUndo=true，默认缺省为 false；指定 B(k) applied 后，按 k 守卫清 false。页面重新进入也恢复该标志；WS 重连、试下和 recheck 不解除它。明确重新开始/正常完成清理标志。复用既有按用户身份隔离的 store，不新增存储服务。离开页面只发送带 generation 的 stop，取消计时器并清理本页灯；迟到响应不得 setState、改 k 或点灯。其他功能接管时先失效摆谱代号。

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
| `katrain/web/ui/src/kiosk/hooks/useVisionSync.ts` | 新事件类型，仍保留接收 seq 去重 |
| `katrain/web/ui/src/kiosk/hooks/physicalBaipuMachine.ts` | canonical 候选、版本、undo 锁、applied 后恢复/推进、syncing 状态 |
| `katrain/web/ui/src/kiosk/hooks/usePhysicalBaipu.ts` | 串行 IO、带版本控制、重试/失效处理、recheck 替换 adopt |
| `katrain/web/ui/src/kiosk/pages/BaipuSessionPage.tsx` | 提供 B(k+1)/step kind，guarded 推进、pass/AE 门控和短提示文案 |
| 下述精确测试文件 | 只覆盖此次状态完整性与最可能的旧路回归，不另建测试平台 |

### Task 1: 保存本次失败作为可重复的验收用例

**Files:** Create `tests/data/baipu_recovery_115_116.json`; Modify `katrain/web/ui/src/kiosk/hooks/physicalBaipuMachine.test.ts`, `tests/test_vision/test_move_detector.py`。

- [ ] **Step 1 — 固定证据。** 从 [持久化现场证据](../evidence/2026-10-21-baipu-recovery.json) 提取 canonical_before=B115、observed_and_erroneous_target=B116、confirmed_k=115、waiting_next=P8白与 following_move=J8黑，写入测试 fixture；不依赖临时目录。复核两矩阵差异恰好 P8，不复制整段浏览器状态或凭据。
- [ ] **Step 2 — 写 RED 用例。** reducer 测试完整模拟“错色 → setup → 下一手已在盘上 → 点击重新核对 → 成功继续两手”，断言 target 来自 canonical，P8 只被接受一次。当前版本应在 raw adopt/无法推进断言失败；不要把旧版错误行为写成期待成功。
- [ ] **Step 3 — 记录检测器边界。** Python 聚焦用例断言：`force_sync(B116)` 后再喂 B116 没有 P8 新落子；`force_sync(B115)` 后不同帧连续 B116 确认 P8。这条说明旧故障机制，保持现有检测器行为，不改它为强行重报已有子。
- [ ] **Step 4 — 运行并确认 RED。** 后端：`.venv/bin/python -m pytest tests/test_vision/test_move_detector.py -q`，应通过现有检测规则；前端（在 `katrain/web/ui`）：`npm exec vitest run src/kiosk/hooks/physicalBaipuMachine.test.ts`，新增恢复验收在旧版失败。保存失败原因，直到 Task 5 转绿。
- [ ] **Step 5 — 提交用例与 fixture。** `git add tests/data/baipu_recovery_115_116.json tests/test_vision/test_move_detector.py katrain/web/ui/src/kiosk/hooks/physicalBaipuMachine.test.ts`；`git commit -m "test: reproduce baipu recovery baseline drift"`。此测试提交后紧接实现，不作为可发布状态。

### Task 2: 实现有限的纯核对器与健康门控

**Files:** Create `katrain/vision/baipu_recovery.py`, `tests/test_vision/test_baipu_recovery.py`; Modify `katrain/vision/sync.py`, `tests/test_vision/test_sync.py`。

- [ ] **Step 1 — 写纯函数 RED 测试。** 覆盖 Bk/Bnext、错色直接替换、先拿后放、先放对再拿错、先补旧子/先放下一手、提子任意顺序、真缺子、undo 只能 Bk、相同矩阵不能隐式跳 pass。所有顺序都喂完整当帧矩阵，不把不同帧的子拼成目标。
- [ ] **Step 2 — 写新鲜度 RED 测试。** started 前的 camera_ts、重复 camera_seq、旧 observation_seq、其他 gen/revision、相同 revision 改 body 均不能成功；同版 recheck 不清计数，candidate 改变清计数，无效帧中断。raw-voted 缺子而 reference 填回的例子不能成功。确认帧数从构造参数注入，测试用 2，生产读既有 config。
- [ ] **Step 3 — 运行 RED。** `.venv/bin/python -m pytest tests/test_vision/test_baipu_recovery.py -q`，应因模块/行为未实现失败。
- [ ] **Step 4 — 最小实现。** 一个 context 保存 immutable candidates、generation/revision、打开时刻、最后两种 seq、当前候选/连续数、applied 结果。候选选择只用矩阵相等；提示选 Hamming 距离最小候选，平局选较小 k；返回决定而不自己改 worker。候选确认逻辑如下，过期/无效分支按前述表处理：

公开接口固定为 `Candidate(k:int,board:np.ndarray)`、`BaipuRecovery(generation,revision,candidates,opened_monotonic,confirm_frames)`；`observe(*,raw_voted,observed,observation_seq,camera_seq,camera_ts,valid) -> Candidate|None`；`interrupt()` 清连续数不清目标；`mark_applied(candidate)` 缓存应用结果；`recheck()` 返回缓存结果/当前 progress 而不重建。构造时 copy 数组，防调用方改目标。generation/revision 过期在 worker 调用前拒绝，observe 不接受前端填写的帧证据。一个可直接落入测试文件的 RED 用例：

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
matched = [c for c in candidates
           if np.array_equal(observed, c.board)
           and np.array_equal(raw_voted, c.board)]
candidate = min(matched, key=lambda c: c.k) if matched else None
if candidate is None:
    streak_k, streak = None, 0
elif candidate.k == streak_k:
    streak += 1
else:
    streak_k, streak = candidate.k, 1
if candidate is not None and streak >= confirm_frames:
    return candidate  # worker 应用成功后再标记 applied 并发布
```

- [ ] **Step 5 — 健康门控测试与实现。** 测试 degraded 的原进入/退出迟滞、board_lost/恢复与正常 sync.update 原语义；恢复接口不得把一次低质图像显示成盘面匹配。`observe_recovery_health` 调用原 `_check_degraded`，发原健康事件，返回是否允许核对；不计算 legacy setup_complete、不改变阈值。
- [ ] **Step 6 — 运行 GREEN 并提交。** `.venv/bin/python -m pytest tests/test_vision/test_baipu_recovery.py tests/test_vision/test_sync.py tests/test_vision/test_sync_regressions.py -q`；预期全过。仅提交本任务的实现/测试，message `add canonical baipu recovery matching`。

### Task 3: 在两种 worker 接入真实应用确认

**Files:** Modify `katrain/vision/ipc.py`, `katrain/vision/worker_inprocess.py`, `katrain/vision/worker.py`, `tests/test_vision/test_worker_commands.py`; Create `tests/test_vision/test_baipu_recovery_worker.py`。

- [ ] **Step 1 — 两种 dispatcher 写 RED。** 用现有 fake camera/detector harness 分别创建两个 worker。start→target 后撤臂；验证相同 generation 下新 revision 生效、旧 revision/旧代 stop 无效；BIND/UNBIND/旧 monitor/geometry reset 必须结束旧摆谱上下文。
- [ ] **Step 2 — 帧与应用写 RED。** 用具有 read_frame_identified 的 fake camera 喂重复 seq、旧 timestamp、无帧、遮挡/运动和正确新帧。assert 同一 camera_seq 不重复调用 detector，也不能产生 normal confirmed_seq；只有不同有效帧推进确认。raw 与 reference 矩阵不一致时零 applied。测试旧 setup/capture target 在应用后清空，expected_np/detector.prev_board 精确等于同一 canonical。start 清理上代帧去重值；相机重连/帧身份不可用时不靠循环次数接受，先 unavailable 后受保护 start/verify。
- [ ] **Step 3 — 运行 RED。** `.venv/bin/python -m pytest tests/test_vision/test_baipu_recovery_worker.py tests/test_vision/test_worker_commands.py -q`；新增协议测试应失败，既有 dispatcher 测试不得被删除。
- [ ] **Step 4 — 实现命令与唯一核对调用。** 增加 BAIPU_CONTROL、BAIPU_TARGET；start 设置代号并撤臂，target verify 开新窗口但不解锁几何。两种 worker 在 average/vote/MoveDetector 前共用摆谱帧去重，重复帧仍处理命令/状态，不推理/计数；无效帧显式 interrupt matcher。进程内复用 reset accumulator，使用同次推理产生的 raw-voted/reference-corrected 两矩阵；多进程按 §3.3 对应。核对活跃时不再运行 legacy setup 完成分支。
- [ ] **Step 5 — 实现应用确认及 normal apply 校验。** 按 §3.2 应用结果候选，未成功不得布臂/发 applied；成功保存结果便于重发。normal apply 只允许同代/source_revision/confirmed_seq 支持的加一子结果；显式 pass 允许同矩阵 k+1 且不伪造 confirmed_seq。base k/board 必须与已应用结果一致，否则带 code error 并撤臂。摆谱 monitor move_confirmed 在两种 worker 的 unbound dict 分支写真实 observation_seq/stamp、缓存后立即撤臂，不改 bound 对局 ConfirmedMove 或死活题语义。
- [ ] **Step 6 — 钉住错误与兼容边界。** 在 force_sync 处注入异常：零 applied、armed=false；重复 recheck 不重复 force_sync；paused 时可应用但不布臂，resume 必须重新 verify；非摆谱 monitor、bound game、legacy setup 不新增事件编号要求。对旧接口原测试保持原样。
- [ ] **Step 7 — 运行 GREEN 并提交。** `.venv/bin/python -m pytest tests/test_vision/test_baipu_recovery_worker.py tests/test_vision/test_worker_commands.py tests/test_vision/test_service_monitor.py tests/test_vision/test_gating.py -q`；预期全部通过。message `apply baipu recovery targets atomically in both workers`。

### Task 4: 暴露窄接口，隔离页面生命周期

**Files:** Modify `katrain/vision/service.py`, `katrain/web/api/v1/endpoints/vision.py`, `tests/test_vision_api.py`; Create `tests/test_vision/test_baipu_recovery_service.py`。

- [ ] **Step 1 — service RED。** status→start CAS→新 start→旧 target/旧 stop，assert 旧代不影响新代；晚到旧 expected_generation 的 start 返回 409。已绑定会话/local confirmation 活跃 start 冲突；无 worker unavailable；同一 FIFO 收到 start/target/pause/stop 顺序明确。stop/其他 owner 接管后，旧代无效但 CAS token 不回到 null；服务重建生成的 token 不能与旧 token 碰撞。
- [ ] **Step 2 — API RED。** 按 §3.1 写 contract tests：19×19之外、布尔/浮点/3 值、负 k/revision、超过两候选、候选 k 越界/重复、verify 相同矩阵不同 k、不合法 mode 字段组合应 422。apply 显式 pass 同矩阵只有一个 k+1 候选合法，普通 apply 必须带 source。旧 API body/response 兼容，只在 status 新增可选 baipu_generation；accepted 不等同 applied。
- [ ] **Step 3 — 运行 RED。** `.venv/bin/python -m pytest tests/test_vision/test_baipu_recovery_service.py tests/test_vision_api.py -q`，新增路由/检查失败。
- [ ] **Step 4 — 实现最小 wrapper 与验证。** VisionService 使用 token+active 标记，原 status 返回 token；同步 start CAS 后入队，后续 target/control 验证当前 active token。发 WorkerCommand，不另开线程。body 用 strict integer/shape 验证；pause/stop 也带代号，generic monitor/bind 的所有权变更会失效旧代。API 不改浏览器进度。
- [ ] **Step 5 — GREEN 并提交。** 运行 Step 3 同命令，预期通过；检查旧 `/setup-mode`、`/expected-board`、对局 bind、死活题 monitor 用例仍绿。message `expose versioned baipu target synchronization`。

### Task 5: reducer 以 canonical 确认驱动恢复

**Files:** Modify `katrain/web/ui/src/kiosk/hooks/physicalBaipuMachine.ts`, `katrain/web/ui/src/kiosk/hooks/physicalBaipuMachine.test.ts`, `katrain/web/ui/src/kiosk/hooks/useVisionSync.ts`。

- [ ] **Step 1 — 写 RED 状态测试。** 所有 camera 路径都在 applied 匹配 gen/revision/candidate 后才 matched；普通正确 move 只 stage apply，不先推进。重复 applied 最多一次，旧事件/错误颜色零次。恢复到 Bk 保持 k，Bnext 推进一步。加普通末手、末手提子、末手 pass 用例：ack 前不 done/清进度，ack 后恰好完成一次。
- [ ] **Step 2 — undo RED。** undo 后 O=Bnext 持续出现不提升，recheck/pause/resume/reconnect 仍不能提升；O=Bk 达到确认后解锁，再放下一手才推进。该例专门防“撤回被自动抵消”。
- [ ] **Step 3 — RED 运行。** 在 `katrain/web/ui`：`npm exec vitest run src/kiosk/hooks/physicalBaipuMachine.test.ts`，预期 Task 1 与新增用例失败。
- [ ] **Step 4 — 最小状态迁移。** SETUP 输入当前 canonical 候选、reason、版本；增加 TARGET_PROGRESS/TARGET_APPLIED/TARGET_ERROR；移除通过裸 SETUP_COMPLETE 或 missing/extra 自行提升的能力。old setup 事件不参与摆谱决定。setupLeds 使用 progress 对应的候选矩阵；同点错色不同时亮互相矛盾的补子/移子灯；合法下一手不会被蓝闪要求移除。撤回例外按 Bk 正常提示拿走。
- [ ] **Step 5 — 保留正常路径。** MOVE_CONFIRMED 只接收当前 stamp，位置/颜色严格相等；正确后暂存 k+1，发 canonical apply 或 capture verify，phase=syncing/setup，无 matched。只有 TARGET_APPLIED 才进入 advancing、matched，并在页面 k catch-up 后 next LED 恢复。MOVE_PENDING 熄灯/RELIGHT 的 3s 机制原样覆盖。
- [ ] **Step 6 — GREEN 并提交。** 同 Step 3，预期全过，含 Task 1 P8 回归。message `reconcile baipu progress from canonical target acknowledgements`。

### Task 6: hook 串行交接、重试与页面自然操作

**Files:** Modify `katrain/web/ui/src/api.ts`（含 VisionStatusResponse）、`katrain/web/ui/src/api/baipuApi.ts`、`katrain/web/ui/src/api/baipuApi.test.ts`、`katrain/web/ui/src/kiosk/hooks/usePhysicalBaipu.ts`、`katrain/web/ui/src/kiosk/hooks/usePhysicalBaipu.test.tsx`、`katrain/web/ui/src/kiosk/pages/BaipuSessionPage.tsx`、`katrain/web/ui/src/kiosk/__tests__/BaipuSessionPage.test.tsx`。

- [ ] **Step 1 — API 与 options 类型。** 增加 status/start CAS/target/control 封装；options 传 current k/board、canonical nextBoard、step kind、下一手坐标、pendingUndo。adopt 改 recheck，主动恢复不读 raw board 作目标；只有 10s presence 补救可以只读 visionDetectedBoard。onMatched(expectedK) 仅 applied 后执行，页面 functional updater 在 prev===expectedK 时 +1 并保存，写同一 k 幂等。
- [ ] **Step 2 — 写完整 hook RED。** mock HTTP + 带 stamp WS 重演错色→直接换色→recheck→applied→继续两手；另测先补旧子/先放下一手、同点颜色错、undo 与重复按钮。核对中点击不重置，同版未知 ack 重发完整 body，await 主动点击新 revision verify；旧 k 缓存 applied 不能冒充新结果。gen 只检验等值隔离，同代 revision 单调；请求全为 canonical，最终 k/保存值/next/LED/expected 一致。
- [ ] **Step 3 — 写异步 RED。** target 入队前网络失败重发完整同版 body、已应用 ack 丢失同版返回缓存、source_stale 新 revision verify、无 generation protected start 各一例。两个 hook 真实卸载/重挂载用共享队列，旧延迟 start/cleanup 不夺新目标。暂停/卸载后回调不得提交/点灯。同批 applied+下一 move 在 k catch-up 后继续正确接受，MAX_EVENTS 丢 seq 转 verify；不能只断言“没 +2”。
- [ ] **Step 4 — 运行 RED。** 在 UI 目录：`npm exec vitest run src/kiosk/hooks/usePhysicalBaipu.test.tsx src/kiosk/__tests__/BaipuSessionPage.test.tsx`；旧 adopt 用例需替换为新语义，不能仅改 mock 使旧断言绿。
- [ ] **Step 5 — 实现队列与事件 catch-up。** 文件级共享 Promise 队列串行所有实例 IO，局部 genRef 只负责废弃本实例回调，worker token 独立保存。status/start CAS 冲突最多刷新一次；关键错误终止该批，按 code 转移，灯失败独立 ledOk。stop/pause/recheck 用带代号接口，删除旧无归属 cleanup。事件消费遇 advancing 先 break 不越过 processedSeq；将 k/next catch-up effect 放在消费 effect 前，追上后续跑余事件；检测序号裁剪缺口转 verify。
- [ ] **Step 6 — 页面、持久撤回和末手。** 文案按 §3.4 改，不增加页面/弹窗或改整体布局；现有动作区在 setup 超时、同步错误或 await 超过 10s 显示重新核对。BaipuProgress 增加 pendingUndo?:boolean，缺省 false；撤回与新 k 一起存 true，指定 B(k) applied 后按 k 守卫清 false，跨重挂载重建锁，k=0 的标志也读取。重新开始/完成清标志。camera pass timer 等当前 applied 后 stage 显式 pass；clear/AE 走移子核对；manual/collect 保持。camera matched 来自 applied，advance 原 done/清存储可保留，但普通/提子/pass 三种末手测试钉住先后顺序。
- [ ] **Step 7 — 10s 补救与计时测试。** 只读快照等于 Bk/读取失败时不灭灯；等于不同的 Bnext 且 lifecycle/generation/revision/k/phase 未变、无未结束 pending 才新 verify。加入延迟快照期间收到 MOVE_PENDING 或已进入新 revision/setup 的用例，必须取消补救，不重置正常确认。每 k 最多自动检查一次，主动按钮仍按状态表可恢复。未完成 verify 的同版 recheck 不清计数；卸载取消 timer。
- [ ] **Step 8 — GREEN 并提交。** UI 运行 `npm exec vitest run src/api/baipuApi.test.ts src/kiosk/hooks/physicalBaipuMachine.test.ts src/kiosk/hooks/usePhysicalBaipu.test.tsx src/kiosk/__tests__/BaipuSessionPage.test.tsx`，预期全部通过；message `simplify baipu correction and guard asynchronous recovery`。

### Task 7: 聚焦集成验收与真实预览

**Files:** Modify `katrain/web/ui/src/kiosk/__tests__/BaipuSessionRoute.test.tsx`（如现有 page 测试不能覆盖路由重连才扩展）；记录验收到 `docs/superpowers/reviews/2026-10-21-baipu-recovery-verification.md`（未来实施时创建）。

- [ ] **Step 1 — 串起事故链。** 真实 reducer/hook、canonical replay 与 mock transport（不写第二套状态机）重放 B115/P8、J8 应黑实白、拿放/撤回/重新核对，恢复后连续两手。断言页面/保存 k、worker canonical baseline、next 一致。主动恢复按钮不走 raw snapshot；10s presence 检查只触发 fresh verify。包括 pendingUndo 跨重挂载及普通/提子/pass 末手先 ack 后 done。
- [ ] **Step 2 — 聚焦后端回归。** 在 repo 根目录运行 `.venv/bin/python -m pytest tests/test_vision/test_baipu_recovery.py tests/test_vision/test_baipu_recovery_worker.py tests/test_vision/test_baipu_recovery_service.py tests/test_vision/test_worker_commands.py tests/test_vision/test_sync.py tests/test_vision/test_sync_regressions.py tests/test_vision/test_service_monitor.py tests/test_vision/test_gating.py tests/test_vision_api.py -q`。预期全过；仅为具体失败扩大范围，不跑与本次无关 AI/全服务套件。
- [ ] **Step 3 — 聚焦前端与生产构建。** UI 目录运行 `npm exec vitest run src/api/baipuApi.test.ts src/kiosk/hooks/physicalBaipuMachine.test.ts src/kiosk/hooks/usePhysicalBaipu.test.tsx src/kiosk/__tests__/BaipuSessionPage.test.tsx src/kiosk/__tests__/BaipuSessionRoute.test.tsx`，再 `npm run build:smartbox-kiosk-2d`。预期全过、tsc 和 strict 2d manifest 检查通过。
- [ ] **Step 4 — 1024×600 真实页面核对。** 在本地真实 kiosk 页面显示普通等待、同点错色、核对/同步失败三个本次受影响状态，检查短文案、按钮可点、无溢出，保存代表截图。已有布局不重做设计系统；如局部文案导致布局调整，先让用户确认真实预览再继续该 UI 调整。
- [ ] **Step 5 — Astra Max 独立代码审核与修正。** 未来获准实施后按用户既定流程做代码审核，修具体问题并补对应回归；本轮只审计划，不启动代码审核或部署。
- [ ] **Step 6 — RK3562 设备验收（另获实施/部署授权后）。** 使用新测试棋谱/单独测试进度，避免覆盖当前用户盘局。黑摆白后直接换黑、先拿后放、先放对再拿错、下一手已在盘上 recheck、撤回后不自动反弹、提子任意顺序、手遮挡后恢复各一次；记录最后一次有效物理改正到 worker applied/界面下一步的耗时，确认数与当时 FPS；恢复后连续摆两手。普通落子确认延迟不应因本改动多出整盘 verify 窗口；纠错每个有效帧最多一次推理、无周期性重新等待。未达标不宣称设备通过。
- [ ] **Step 7 — 完成前证据。** 使用 @superpowers:verification-before-completion 汇总命令、提交与真实设备结果；用户允许集成发布时再按仓库 AGENTS 顺序追 develop、合入、更新 submodule、部署。此计划没有授权现在执行任何一步发布。

### 5. 实施依赖与适度并行

Task 1 → Task 2 → Task 3 → Task 4 为共享协议基础；Task 5 可在 Task 2–4 开发时由独立前端子代理针对本文已固定契约并行，不能自行改协议。Task 6 等 Task 4、5 完成后集成；Task 7 收口。worker_inprocess.py 和 worker.py 由同一任务维护，避免两个代理各自发明不同命令语义。共享状态未稳定前不同时实施多个页面旅程。

### 6. 本轮计划审核与停止条件

- 设计预读仅作准备，不算正式实施计划审核。
- Astra Max 正式第 1 轮：审本计划与设计、对照真实代码，指出遗漏和不可实施部分；主代理修改。
- Astra Max 正式第 2 轮：复核修改和剩余风险；主代理修订文档并记录最终结论。最多两轮，不追加第三轮流程。
- 两轮后报告通过/未解决项；停在文档阶段。**不执行 Task 1–7、不改产品代码、不提交部署，不因计划完成自动开始 subagent-driven-development。**
- 正式审核记录：[两轮报告与修订对应表](../reviews/2026-10-21-baipu-recovery-plan-review.md)。没有第三轮审核或独立批准最终修订的声明。
