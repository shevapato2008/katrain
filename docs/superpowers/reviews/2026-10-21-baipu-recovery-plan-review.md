# 摆谱纠错恢复计划：审核与修订记录

日期：2026-10-21。独立审核模型：GPT-6 Astra，Max reasoning。审核代理：`/root/astra_baipu_recovery_design`。

用户要求最多两轮，本记录保留两轮原始结论，不将主代理最后修订冒称为独立审核通过。没有第三轮，没有产品代码实施、服务重启或设备写入。

## 最终文档修订对应表（主代理记录）

| 审核项 | 最终计划处理 |
| --- | --- |
| R1 末手提前结束 | 所有 camera 推进 staged → applied → guarded commit；普通 apply 不加整盘等待，末手 ack 后完成 |
| R2 旧 start/跨实例请求 | 文件级共享 IO 队列 + status/start 有限 CAS + opaque token；旧 cleanup 无效 |
| R3 重试无法收敛 | 完整 body 同版重发；source 失效新 revision verify；失代重新 start |
| R4 同批下一手被丢弃 | advancing 暂停消费不越过 processedSeq，页面 catch-up 后续跑；截断缺口重新 verify |
| R5 重复帧/参考填补 | 平均/投票/正常 MoveDetector 前帧去重；verify 同时核对 raw-voted 与 reference-corrected |
| R6 正常等待被打断 | 10s 只读 presence，完整匹配 Bnext 才核对，正常 Bk 不灭灯 |
| N1 撤回意图丢失 | 既有 BaipuProgress 增加可选 pendingUndo，指定目标 applied 后才清除 |
| Round 2 最后入口修正 | 未完成核对同版；未知回执重发完整 target；已 applied 的 await 主动核对新 revision。按钮覆盖 await 超时/错误；晚到 presence 校验 phase/revision，正常 pending 时取消自动补救。Task 6 补两条对应 hook 用例 |

最终计划中的这些修订由主代理写回。正式 Round 2 对所审版本仍为 Issues Found；其报告允许主代理补最后一项后停止，本记录不声称又经过一次独立批准。

相关文件：[实施计划](../plans/2026-10-21-baipu-recovery.md)、[原因与流程设计](../specs/2026-10-21-baipu-recovery-design.md)、[现场矩阵证据](../evidence/2026-10-21-baipu-recovery.json)。

---

## 以下保留正式第 1 轮报告

# 摆谱纠错恢复实施计划：正式审核 Round 1 / 2

日期：2026-10-21

结论：**Issues Found**

审核对象：`docs/superpowers/plans/2026-10-21-baipu-recovery.md`（243 行版本）及对应设计稿。下列行号均指该版本；主代理尚未写回讨论中的修订。此次只读审查当前代码并写本报告，未实施、提交、SSH 或部署。

## 已认可的部分

- 根因表述与现场矩阵、实际 reducer 和 worker 代码一致：`k=115`，target/检测盘面含 P8 白子，raw adopt 保留旧进度后将下一手吞入基准。完整点击顺序没有被过度断言。
- 以 canonical B(k)/B(k+1) 为唯一候选、禁止全谱自动跳步、删除 raw adopt、worker 实际应用后回执的方向正确。
- 撤回先达到 B(k) 才解除提升限制，已解决设计预读发现的撤回立即反弹问题。
- 沿用现有 worker、reducer、存储和测试工具即可；不需要新数据库、租约服务、图像模型或额外推理。

## Blocking：实施前必须写清的修正

### R1 — 普通落子先推进，会让末手在目标应用前关闭整个识别流程

**计划位置：97–100、114、205、212 行。**

**代码依据：** `BaipuSessionPage.tsx:222` 的 advance 立即设置 done；`:269` 的 physical enabled 只允许 guiding；`:280` 在 done 清除保存进度。

计划让正常 move_confirmed 先推进 k，再交接 apply/capture verify。末手因此先 done、关闭 hook 并清进度，最终 apply 或提子核对还没完成就被取消。这个缺口也使普通推进与设计的提交边界不一致。

**最小修正：** 采用讨论中更统一的规则：所有 camera 推进先暂存候选 k+1，只有对应 worker applied 才调用 guarded onMatched。普通正确落子使用已有 confirmed_seq 立即 apply canonical Bnext，不增加新帧或整盘确认；提子使用 verify。TargetRequest 的 k/board 始终指当前已提交 Bk，结果候选另列。pass 同矩阵有明确独立规则，不要求伪造落子 confirmed_seq。

**聚焦验收：** 普通末手、末手提子、末手 pass；ack 前不 done/清存储，ack 后恰好完成一次。无需增加 pendingFinal 系统。

### R2 — hook 内的队列无法保证跨组件实例的 start 顺序

**计划位置：50、120、214、216 行。**

**代码依据：** `usePhysicalBaipu.ts` 的 queueRef/genRef 都属于 hook 实例。

旧实例的 start 在途时卸载，新实例有独立 Promise 队列，可以先启动并获得代号；旧 start 后到却再生成新代号，反而使新页面失效。只检查旧实例的返回值或给 stop 带 generation，不能阻止服务端已执行的晚到 start。

**最小修正：** 同一页面进程中的 start/target/control/cleanup 使用文件级共享串行队列。若保留整页 reload 也隔离晚到 start 的保证，采用讨论中的有限 start CAS：status 返回当前 opaque generation，start 带 expected_generation；不符则冲突，只有仍活跃的调用方可刷新并重试一次。generation 使用新 token，revision 保持整数。无需给普通 target/control 增加新协调层。

**聚焦验收：** 两个真实 hook 实例卸载/重挂载并使旧 start 延迟；旧 start/cleanup 不夺走新实例目标。CAS 另外验证晚到旧请求被拒绝即可。

### R3 — 所有错误都“同版 recheck”并不能恢复

**计划位置：66、116、183–184、214、216 行。**

source_revision/confirmed_seq 已失效时，重试同版 apply 永远不能通过。target 请求若在入队前失败，只发送携带 revision 的 recheck 也没有目标可查；start 失败时甚至没有 generation 可用。把这些情况都写成“点重新核对、重试同版”会产生新的永久等待。

**最小修正：** 给 error 增加少量明确 reason，并规定动作：传输结果未知时重发保存的同版完整 target，worker 已应用则返回缓存回执；apply 证据失效时增加 revision 降级 canonical verify；无有效 generation 时按受保护的 start 流程重新开始。真实应用失败保持撤臂和未提交状态，再按对应可重试路径处理。不能吞错后继续布臂/点灯。

**聚焦验收：** target 未入队的网络失败、已入队但 ack 丢失、apply 证据过期各一例，最终均有可走通的重试路径且不重复提交。

### R4 — applied 和下一手事件同批到达，不能只防重复而丢掉下一手

**计划位置：87、114、205、214 行。**

**代码依据：** 当前 hook 会在处理每条事件前推进 processedSeq；reducer 在 advancing 下忽略 MOVE_CONFIRMED。

worker 先发 applied、随后下一帧发 move_confirmed，但 React 可以在同一次渲染交付这两条事件。第一条使前端进入 advancing；第二条若直接忽略且标为已消费，物理下一手已经被 detector 收进基准，之后不会再次报同一落子。仅断言“旧 k 没有 +2”不足以证明能继续。

**最小修正：** 采用讨论中的无新队列方案：推进屏障下暂停消费，不推进那条事件的 processedSeq；页面 k/next 追上并先更新 machine 后，再消费余下事件。若 MAX_EVENTS 截断导致待处理事件丢失，明确进入新的 canonical verify，不能静默跳过。

**聚焦验收：** 同一批 applied + 下一手 move_confirmed，先提交一次，页面同步后再正确处理下一手，无需用户拿起重放。

### R5 — 新鲜帧门控必须覆盖正常确认，核对输入也必须明确

**计划位置：34、68、102–108、180、182–183 行。**

**代码依据：** `worker_inprocess.py:1093`、`:1223` 当前只为 observer/local 模式使用帧身份；`:1295` 投票与 `:1380` 后的 MoveDetector 每轮运行。`worker.py:277`、`:314`、`:385` 也以循环驱动。`worker_inprocess.py:741` 会用 reference.board 替换不一致格点。

仅在 verify matcher 末端拒绝重复 camera_seq，不能阻止 normal MoveDetector 用同一个相机帧累计确认，随后 apply 又把这个 confirmed_seq 作为合法证据。计划中的 observed 也未明确是哪一份矩阵；只比较 reference-corrected 结果可能把参考补回的格点当成当前实测匹配。

**最小修正：** 摆谱拥有 monitor 时，在平均、投票和 MoveDetector 前共用 identified-frame 去重门控；正常路径和 verify 使用同一新鲜度规则，其他消费者保持原行为。无效帧须中断 verify streak，不能只不调用 matcher。核对输入明确采用讨论中的双检查：reference-corrected 与 raw-voted（进程内 denied_stable，尚未 reference_check）都匹配候选才累计；多进程没有该参考层时两者相同。保留原参考否决，不新增阈值或模型。

**聚焦验收：** 重复同一 camera_seq 既不能完成 verify，也不能生成可供 apply 使用的正常确认；raw-voted 缺子但参考填回匹配时不 applied；不同有效新帧恢复后能继续。

### R6 — 10 秒无条件核对会改变正常等待行为

**计划位置：118、218 行。**

用户正常思考超过 10 秒，就会离开 await、熄掉下一手灯、清平均/投票并进入额外确认窗口；恰好正在累计的正常落子也可能被重置。这与“不干扰正常落子快路径”的规则冲突，而且扩大了原始纠错需求。

**最小修正：** 使用讨论中的只读 presence 检查：只有当前检测读数符合 canonical Bnext、且仍没有对应推进时，才触发一次 fresh verify。快照只触发核对，绝不能作为完成证据。检查失败或正常 Bk 不改变状态/灯；用户仍能主动重新核对。保持有限触发，不添加持续推理或无限重试。

**聚焦验收：** 正常等待超过 10 秒不灭灯/重置；已有下一手且未推进时可经 fresh verify 恢复。

## 非阻塞：建议同步明确的边界

### N1 — 将撤回意图与已保存进度一起保留，避免重进页面又反弹

**计划位置：31、120、202、216 行。**

现稿明确覆盖 WS 重连，但新组件从保存的 k 恢复时拿不到内存 undo 锁。若撤回后尚未拿子就退出/重进，会再次把旧实体盘面认成 B(k+1)。这不是扩大存储系统的理由。

认可主代理提出的最小落点：`src/api/baipuApi.ts` 的 BaipuProgress 增加可选 pendingUndo，默认 false；撤回保存 k 时一起写 true；仅对应指定 B(k) 的 applied 在 k 守卫下清除。沿用现有身份隔离存储，补 `baipuApi.test.ts` 和一个重挂载用例。若不采用，必须明确撤回锁仅保证 hook 仍存在的 WS 重连，不能泛称跨页面恢复；采用此小字段更符合已保存撤回的用户预期。

## 收口

上述修正可在当前文件与协议范围内完成，不建议扩展审核或测试平台。主代理已经提出与 R1–R6 对应的最小方向；它们尚未写回受审文件，因此本轮结论仍是 Issues Found。

修订后正式 Round 2 只复核这些改动、协议内部一致性及明确剩余风险；最多两轮后停止，不实施 Task 1–7。

---

## 以下保留正式第 2 轮报告

# 摆谱纠错恢复实施计划：正式审核 Round 2 / 2

日期：2026-10-21

结论：**Issues Found — 剩余 1 项必要修正；本轮后停止审核。**

审核版本：`docs/superpowers/plans/2026-10-21-baipu-recovery.md`，285 行版本及配套设计稿。此次只复核首轮问题及修订的一致性，未修改主计划、产品代码或测试，未执行实施步骤、SSH、提交或部署。

## 首轮问题的复核结果

| 项目 | 结果与对应位置 |
| --- | --- |
| R1 末手提前结束 | 已解决。107–110、124、243、247、259 行统一 staged → applied → commit；普通 apply 不增加新帧，末手自然在确认之后 done。 |
| R2 跨实例 start 乱序 | 已解决。48–54、233、236、256、258 行明确共享 IO 队列、start CAS、opaque token 及有限冲突重试。 |
| R3 错误重试永久卡住 | 主体已解决。70–74、93、128、256 行区分完整同版 body 重发、source 失效转新 verify、generation 失效重新 start；剩余主动 recheck 边界见下。 |
| R4 同批下一手事件丢失 | 已解决。95、126、256、258 行明确 worker 确认后撤臂，前端推进屏障不越过 processedSeq，catch-up 后继续；缓存裁剪转 verify。 |
| R5 相同帧与参考填补 | 已解决。112–118、167–211、222–225 行明确推理前去重、无效帧 interrupt、双矩阵匹配、apply 先验证旧来源再替换上下文。普通确认维持原窗口。 |
| R6 正常等待被无条件打断 | 主体已解决。130、260 行改为只读 presence 条件触发，正常 Bk 不改变灯；在途正常确认的最终入口守卫见下。 |
| N1 重挂载丢失撤回意图 | 已解决。132、145、254、259、267 行沿用 BaipuProgress 增加可选 pendingUndo，并覆盖 k=0、按 k 清除和重挂载。 |

纯 helper 的签名、双矩阵比较和相机帧去重示例已足以直接落入测试。normal apply 的 pass 例外不伪造 confirmed_seq；统一提交边界与末手处理一致。没有必要再增加会话服务、数据库、图像推理或新的测试平台。

## 剩余必要修正：明确“主动重新核对”和“在途重试”的入口状态

**位置：74、128、130、254、260 行；配套设计稿第 97 行。**

现稿将 recheck 定义为按当前 generation/revision 更新、不新建窗口，已完成版本只重发缓存 applied；同时又把 await 下的主动 recheck 作为一次自动 presence 检查之后的人工恢复入口。两者并不等价：当前 revision 已 applied 后，用户再放上下一手或碰掉旧子，控制 recheck 只返回旧回执，不会重新观察现在的盘面。自动 presence 每个 k 只检查一次，不能替代这个人工入口。

**最小修正是补一张状态表，不新增接口：**

- verify 尚未完成：同版 control recheck，保留当前确认窗口。
- target 是否入队/是否应用未知：按现有规则重发同版完整 target 或取缓存回执，保证幂等。
- 当前版本已应用且页面处于 await，用户主动“重新核对”：增加 revision，发送 canonical verify；保留 pendingUndo 约束。不能只请求旧版本缓存 applied。
- 10s presence 响应准备触发 verify 时，除 lifecycle/k/board 外，还必须确认 generation/revision 和 phase 仍为发起检查时的 await。若期间收到 MOVE_PENDING、正常确认正在累计，取消或延后这次自动补救，不能重置该正常窗口；用户仍可通过上述主动入口核对。

最后一条是首轮 R6 的收口：只读快照也可能恰好在普通下一手确认途中完整匹配 Bnext，此时直接开 verify 仍会清除原累计并增加一次整盘等待。

**只需补两条已有 hook 测试：**

1. 已 applied 的 await 中主动 recheck 发新 revision verify，旧缓存 applied 不能冒充新核对结果；未完成 setup 中重复点击仍沿用原版且不清 streak。
2. presence 请求在途期间出现 MOVE_PENDING、或已进入其他 revision/setup 时，晚到快照不启动 verify、不熄灯、不重置正常确认。

## 结束条件

以上是最后一轮的唯一剩余必要修正，主代理可以直接补入计划与对应测试步骤后停止，不开启第三轮审核。此报告对所读 285 行版本保留 Issues Found；不能将尚未写回的修正表述为已经独立复核通过。

将 Task 1 的证据源从临时目录改为已保存的 `docs/superpowers/evidence/2026-10-21-baipu-recovery.json` 属于证据持久化，不改变方案语义，不需要新增审核轮次。产品实现和设备验证仍留待用户之后授权。
