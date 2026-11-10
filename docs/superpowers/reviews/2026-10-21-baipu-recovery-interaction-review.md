# 摆谱交互与语音修订：Astra Max 独立评审记录

日期：2026-10-21。评审模型：GPT-6 Astra / Max；独立代理：`/root/astra_baipu_interaction_review`。

本次由用户新增要求触发，范围为提前两手、边界交互和语音。旧版单步计划的报告保留在另一文件，不计入本次两轮。

## 结果

- Round 1：Issues Found，四项必要修改；主代理修订计划与设计。
- Round 2/2：Approved，四项阻塞均关闭，无剩余阻塞，不追加第三轮。
- 仅做代码只读核对和文档修订；没有实现产品、运行产品测试、SSH或部署。评审通过表示计划可供后续获准实施，不表示设备功能已经可用。

| 首轮问题 | 计划的处理 |
| --- | --- |
| 最近候选误导取子与提子提示 | Hamming只中性展示，全候选正确占位受保护，已确认提子绑定步骤结果 |
| 歧义与对齐取消 | 本版锁定等待选择；弹窗冻结提交，取消新版本核对原k/undo，旧回执失效 |
| 无模型结果时不可见状态不到达 | await/verify早退都更新可见性，不造观测，实际持续时长避免双10秒 |
| 真实WebSocket缺重连 | 显式retryConnect、socket身份隔离、实际onopen后start/verify，真实fake-WebSocket用例 |

采纳非阻塞建议：新摆谱HTTP/连接有5s上限，保证共享队列可退出；未知远端结果仍幂等恢复。两点同帧由board_observed唤起核对而不改MoveDetector；跨pass不自动推断。

版本说明：Round 2报告对其读取的427行主计划给出Approved。收口时按其非阻塞意见同步设计稿“8s只限纠错指令”；另由主代理在同一choosing/重连契约下补两行，明确选择中重连仍保留冻结/选定目标，不能静默走entry。没有声称这两行又经过第三轮独立审核。下面保留两轮原报告原结论，末尾空白规范化。

相关：[实施计划](../plans/2026-10-21-baipu-recovery.md)、[设计与根因](../specs/2026-10-21-baipu-recovery-design.md)、[旧版报告](2026-10-21-baipu-recovery-plan-review.md)。

---

## 正式 Round 1 原报告

# Plan Review — Chunk 1 — 交互/语音修订 Round 1

**Status: Issues Found**

评审对象：`docs/superpowers/plans/2026-10-21-baipu-recovery.md`，本轮读取版本共410行；参考 `docs/superpowers/specs/2026-10-21-baipu-recovery-design.md`。这是新增“两手、边界交互、语音”内容的第一次正式评审，不沿用旧版两轮通过结论。

按 writing-plans 检查了文件责任、接口、状态迁移、RED/GREEN步骤，并只读对照真实 `useVoice`、`audioPrefs`、`usePhysicalBaipu`、`physicalBaipuMachine`、`BaipuSessionPage`、`useVisionSync`、replay、两种 worker、MoveDetector、SyncStateMachine、service 和音频生成脚本。未修改产品代码、未执行产品测试、未SSH、未部署。

## 阻塞项：四处最小补充

### R1. 最近候选的差异不能直接成为取子指令；提子提示还缺确定目标

**文档位置：** §3.6第175、187行；Task 2 Step 4第266行；Task 5 Step 4第344行；Task 7 Step 1第365行。

Task 2要求按最小Hamming距离、平局较小k选择提示候选，Task 5又要求setupLeds使用该候选；这与“合法提前子不要求拿走”和“候选操作冲突用中性提示”并不等价。

具体例子：正确下一手会提掉五子，用户先落子、尚未提子。此时O与B(k)只差新落的一子，与B(k+1)却差五子；最近候选必然是B(k)。照该候选诊断会把正确新子视为extra，或过滤掉新子后没有任何提子指导。现有 `physicalBaipuMachine.ts:85` 和 `BaipuSessionPage.tsx:403` 仅排除旧next一个点，也不能保护允许B(k+2)中的其他合法子。

**最小修改：**

- 明确最近候选仅供中性差异展示，不能凭它生成取子/换色命令或决定推进。
- 普通恢复的移除灯和明确“多子”诊断排除所有允许候选中相同坐标、相同颜色的合法占位；undo/align按唯一指定目标执行。
- 正确落子已确认且有removed时，明确以该已确认步骤的canonical结果作为提子提示意图；不能让Hamming重新选回B(k)。若仍有候选操作冲突，给中性提示。完整匹配与提交仍按原候选集合进行。
- 在现有Task 5/7测试中各补一个代表例：五子提子尚未完成、B2合法占位与其他差异并存。无需新增测试平台。

### R2. 歧义/手动对齐没有完整的“等待选择—取消”状态契约

**文档位置：** §3.2第101行；§3.5第160–164行；Task 2第306–309行；Task 5 Step 1第341行；Task 6 Step 2/6第353、357行。

计划说发ambiguous时撤臂，但matcher示例下一帧仍可返回唯一Candidate。撤臂只停MoveDetector，不停verify，因此用户正在选手数时盘面变化仍可能自动applied。主动打开对齐Dialog也没有规定暂停正常提交。取消虽然规定“不改k”，却未规定如何失效已发送的align revision；其迟到applied仍可能提交选错的步数，或worker已应用临时目标而页面恢复旧k。

**最小修改：**

- ambiguous在本revision锁定为等待用户选择，不再自动产生applied；后续只用新revision解除。
- 打开选择Dialog时立即在前端冻结提交并撤臂/暂停，保存原已提交k与pendingUndo；处理可能已在途的事件，不能只靠Dialog视觉遮罩。
- 确认选择后新revision做唯一目标fresh verify；取消则失效临时目标，用原k及原pendingUndo建立新revision verify，再按正常恢复顺序解除暂停。取消后忽略旧align回执。
- 在现有异步测试中补“弹窗期间来普通落子”“ambiguous后盘面变唯一但未选择”“取消后旧align applied晚到”即可。

### R3. 无推理结果的路径仍缺可到达的not_visible状态

**文档位置：** §3.3第122–128行；§3.6第180行；Task 3 Step 2/4第320、322行；Task 7 Step 3第381行。

已有代码在运动不稳定时跳过推理，且 `should_feed_sync_frame` 会跳过sync更新（`gating.py:39`，`worker_inprocess.py:1133/1580`，`worker.py:565`）。计划有interrupt要求，却未明确这些早退分支如何向前端更新可见性；只在“单次推理结束后”发布进度，持续运动/无有效画面时可能永远没有not_visible输入，承诺的10s语音也无法开始。await阶段同样需要该状态，不能只覆盖verify。

**最小修改：**

- 两种worker的无帧、运动未稳定、几何/健康不允许等分支显式中断核对连续数，并给当前摆谱目标发布状态变化的checking/not_visible；不附旧盘面当新证据。
- 健康/可见性事件可引用最后观测编号，由WS接收seq消费；不得伪造一次新摄像头观测。重复同camera_seq仅跳过处理，不累计、不重推理，也不要仅因一轮重复读取就宣称遮挡。
- 前端以连续不可见状态计STUCK_MS，恢复有效观测即取消旧提示；在已有worker/voice测试分别覆盖“没有一次模型成功结果也能进入不可见状态”和“短暂运动无语音”。

### R4. 真实WS没有重连入口，文档的网络重试目前无法落地

**文档位置：** §3.4第144–152行；文件表第230行；Task 5 Files第339行；Task 6第354–358行；Task 8第390–394行。

`useVisionSync.ts:112–145` 只在effect启动时创建WebSocket，onclose只设connected=false；依赖未变就不会再连接。现有retryBind对摆谱的null session也直接返回false（第92行）。计划目前对该文件仅安排新事件类型，却反复依赖“重连后start/verify”。真实连接断开后，目标recheck无法让新applied事件回来；仅在hook测试中手工翻转visionConnected会掩盖这个缺口。

**最小修改：**

- 在原hook提供显式retryConnect，由摆谱断线卡使用；保持其他消费者默认行为即可，不加自动重连服务。
- 重试关闭/替换旧socket，去重在途重试和旧socket回调；等新onopen后再受保护start并fresh verify，保留k与pendingUndo。
- 页面区分“重试连接”和已有连接上的“重新核对”。
- 将现有 `src/kiosk/hooks/useVisionSync.test.ts` 纳入Files及验证命令，用fake WebSocket实际触发close→retry→open；断言旧socket晚到消息不会提交，新连接才启动新目标。无需把路由测试扩成新的测试层。

## 非阻塞建议

- **两手触发的最小证明：** 在现有Task 3/6用真实MoveDetector验证“两个新点同帧出现、detector因并列候选不发move_confirmed，但board_observed仍触发一次verify”。现有 `move_detector.py:400–406` 明确会抑制这种单步确认。再断言仅B1时不因board_observed重开verify、verify中不因后续hint重开窗口。总体方案已经能承载这些行为，建议把它们写成具名验收，不改检测器。
- **共享队列可退出：** 新摆谱HTTP封装宜写明有限超时/取消和未知结果按同版重发。当前 `api.ts:483–500` 没有deadline；如果旧fetch长期不settle，文件级共享Promise队列会让“5s后可重试”按钮仍排在它后面。可在新封装内复用项目已有AbortController/race模式，不改全局API基础设施；加一个未settle请求的聚焦用例足够。
- **表述校正：** 第178行“跨虚手歧义”与第160行“窗口在pass前截断”不是同一行为。明确跨pass不自动推断，沿既定pass流程或用户显式对齐；不要承诺自动生成并未纳入候选的跨pass匹配项。

## 已认可的部分

- canonical B(k..k+2)、一次guarded toK提交、末手applied后完成、undo持久锁、pass不由相同盘面推断，契约方向一致；不用逐次+1模拟批量推进。
- 用独立board_observed唤起两手verify，不增加模型推理，能解决现有MoveDetector对同时两子的单步歧义。普通单手继续使用确认快路径。
- 正反换色语音文案方向正确；固定12条MP3复用现有资源链。问题key、8s间隔、立即取消、静音订阅、播放失败身份校验与重播不改棋谱已覆盖主要风险。
- 一个chunk、Task 0–8文件责任与RED/GREEN命令可用。修正以上契约后可按现有任务执行；不需要追加平台、全量审计或更多评审轮次。

**下一步：** 主代理只修文档，按上述最小范围补齐后做最后Round 2复核。当前不能标Approved，也没有实施授权。

---

## 正式 Round 2 原报告

# Plan Review — Chunk 1 — 交互/语音修订 Round 2/2

**Status: Approved**

复核对象：`docs/superpowers/plans/2026-10-21-baipu-recovery.md`，本轮读取版本共427行；参考同名设计稿及Round 1报告。本轮仅复核首轮必要修正及相关契约一致性，没有扩张审查范围。

## 首轮问题复核

| 问题 | 修订位置 | 结论 |
| --- | --- | --- |
| R1 最近候选误导取子、提子意图不确定 | 计划§3.6第199行，Task 2第280行，Task 5第361行，Task 7第383行；设计第87行 | 已关闭。Hamming仅中性展示，全候选合法占位受到保护，已确认提子绑定该步骤结果；五子提子与合法B2伴随差异均有聚焦验收。 |
| R2 歧义/对齐选择与取消不完整 | 计划第105、170、280、311–325、361、371行；设计第70行 | 已关闭。歧义本版锁定；choosing冻结提交；选择用新revision，取消废弃临时版后核对原k/undo。旧pause、旧回执及排队提交均受版本/选择状态保护。 |
| R3 无有效推理时not_visible不可到达 | 计划第99、134–136、337、339行；设计第97行 | 已关闭。await/verify的早退路径产生可见性状态，不伪造观测；重复帧不立即告警，实际不可见时长避免双重等待，恢复可见取消计时，主动暂停不告警。 |
| R4 真实WebSocket缺少重连入口 | 计划第211、244、367、371–376、411行；设计第70行 | 已关闭。显式retryConnect包含socket身份隔离、在途去重和连接期限；新onopen后才start/fresh verify，保留k/undo。真实fake WebSocket测试及执行命令已纳入。 |

## 相关一致性复核

- 两手仍通过board_observed触发一次verify，真实MoveDetector两点同帧不确认的情况已列入验收；B1保持快路径，核对/暂存/选择期间不会反复重开窗口。
- toK仍由worker applied后幂等提交；pass截断、undo锁、末手提子确认与选择取消没有改成摄像头盘面直接覆盖棋谱。
- 新摆谱HTTP和显式连接尝试有5s期限，超时要求settle；未知远端结果仍按同版重发/CAS处理，没有把abort当作远端未执行。
- 正反换色文案、固定离线资产、问题去重、停止旧句、即时静音、播放失败身份校验保持闭合。过代事件仅忽略，不能取消新句；健康与实际恢复/完成不受纠错8s间隔限制。
- 文件责任、RED/GREEN步骤和验证命令已覆盖本轮修正。没有增加新的识别、语音或重连基础设施。

## 剩余项

**阻塞项：无。**

**非阻塞文案建议：** 设计稿第91行仍写“不同问题自动语音至少相隔8s”，计划第207行已准确限定为“不同纠错指令”。建议将设计稿同步为“不同纠错指令至少相隔8s；健康阻塞和实际恢复/完成可立即打断”，避免实施者误读。详细实施契约已有明确规则，此文案统一不需要第三轮评审。

本结论仅表示计划可进入后续获准的实施阶段，不表示功能已实现或设备已验收。未改产品代码、未运行产品测试、未SSH、未部署。已完成最多两轮独立评审，现停止；不启动Task 0–8。
