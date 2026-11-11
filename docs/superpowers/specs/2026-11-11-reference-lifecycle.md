# Reference lifecycle approved specification and implementation authorization

Authorization recorded 2026-11-11 (Asia/Shanghai): user explicitly requested “修改吧。完成后别忘了独立astra max智能体代码审核。再一起提交、部署吧。” Implementation is now authorized; deployment/push/device actions remain owned by the root coordinator. The proposal's historical “未授权” wording below is retained verbatim as evidence of its earlier review stage, and is superseded by this authorization note.

Base: `7f3a60a929da87f4f8696bb66d1fe86b5801daf1` (published A/E18 fix, not yet applied to devices).

- Frozen proposal SHA256: `77f7288a53562716687722e1883b3447765bb226108d8a44b9b837b043ee50af`.
- Approved cause review SHA256: `7f7e2a63988d92d655f2b9796a8b26f1ae77ddb44fe2faa139c220716e570f33`.
- Approved final solution review SHA256: `513d1da14aa89d7608fd819a98937ed55c802db8c7c50dd79d90d71756550e35`.
- Implementation plan: `../plans/2026-11-11-reference-lifecycle.md`.

The complete frozen proposal follows, byte-for-byte after the marker; the original diagnostic artifact is not edited. No third design cycle is authorized or necessary. Production has no reference_trace.py: do not import the temporary recorder, collectors, SCP tooling or debug-source overrides into this release.

<!-- BEGIN VERBATIM APPROVED PROPOSAL -->
# B：参考保留与逐手交接修复提案（第二稿，最终方案审核稿）

阶段：仅方案，未授权实现。原因已经独立Astra Max审核接受；本稿一次性回应方案首轮R1–R4，替代SHA256为49f0951a67171dfd8f94aa0740a1f54ad0a349e69ee9cef43ac7de71733280c3的第一稿。首轮评审文件为reference-solution-astra-review1.json，SHA256为1c5f3a6f69b768ba5510ee2d405c672869587ced5e6f2e7b4f64e4a26b9924f2。本稿未改产品、未运行模型/设备测试。同一第二轮有限补充仅闭合CameraHub透传、实时LED资格锁边界和明确的advisory曝光阈值，不开启第三轮设计。

## 一、已接受的原因与本次承诺

000002空盘确实被采纳并保存，随后相同会话再次BIND无条件清除了运行参考，000004因此没有旧参考。000039则是旧15被保留；expected16更新没有同步建新参考，之后原始观察已为17，不能满足expected16，导致16参考缺席。具体重复bind的浏览器入口及18:42:33的首个失败guard仍未知，无需追加现场取证。

另一个必须解决的已知风险是：现有pre-vote和voted都来自8帧平均后的模型输入，参考照片却是未平均图。即使两张矩阵相同、camera_seq相同，也不能证明未平均照片没有新出现的子。本稿不再把这两张矩阵称为“照片标签证明”。独立合成复现已经证明此路径能造成照片有子、参考地图空，并触发无限空标签否决；它不证明历史16窗口发生过这种污染。

推荐交付：同源BIND按真实连续性保留照片；用**一次针对实际未平均图的见证推理**把照片与地图绑定；最多保留一份5秒/8合格观察的候选，真正提交成功后以精确回执交接；历史标签限制到仍与当前记录一致的格；持续矛盾证据不能被旧空标签静默永久压住。没有真实合格16帧时明确limited，不追造16照片、不把17照片贴成16、不阻塞正常游戏等参考。

这消除已知的跨平均窗口绑定错误，不保证分类器永不漏子或误判。41/42旧参考实际未否决C16，B不能被宣传为解决A的服务端轮次拒绝。

## 二、三个小方案及选择

| 方案 | 权衡 |
|---|---|
| **推荐：每次新地图/刷新/候选采纳前做一次未平均见证** | 可利用正常8帧识别产生的候选，额外复核它真实照片；增加有上限的现有模型调用，必须公开成本。 |
| 只允许可证明模型输入唯一贡献帧就是照片本帧的情况 | 不增加推理，但大部分平稳8帧输入不能建完整参考，错过16后明确limited；可能长期缺少完整参考。不作为主要方案。 |
| 每手阻塞等待参考或放宽LED/运动guard | 增加延迟且挡不住人继续摆子；放宽guard会制造错误证据。不采用。 |

第一方案仍使用同一个detector实例、同一个worker，不加后台识别循环、第二相机、视频缓存或训练系统。性能若不能接受，应明确退到第二方案，而不是保留“零额外推理且照片已证明”的错误承诺。

## 三、R1：真正的未平均照片见证与空标签权限

### 1. 每条像素写入路径都必须同源

普通目标采集、候选照片暂存/提升、每60秒的periodic refresh都采用同一资格函数，不能让refresh绕过它吞入新子。

在现有运动/geometry/灯光/曝光条件合格、平均流pre-vote/voted已给出待验证整板之后，保留本次实际未平均warp的BGR副本（即生成ref_gray的同一数组，尚未进FrameAverager和CLAHE）。对这个副本单独执行既有enhance_for_inference和**同一detector实例的一次detect**；不用FrameAverager，不调用摄像头。全盘赋值使用不带上一观察/稳定盘/expected填补的无历史状态方式，不写回主识别器的hysteresis、投票、MoveDetector或promoter。

只有该见证整板等于欲关联的实际整板，且见证检测未发现额外LED/不可用曝光，才有资格将对应ref_gray写入ReferenceFrame。pre-vote/voted仍是主流稳定性条件，见证才关闭“平均流是16、未平均照片已17”的时序缺口。见证不允许拿另一张较新照片，也不能因候选token正确而跳过。

普通capture：见证必须等于当前目标。候选：见证等于候选整板，但仍不代表游戏已接受；没有接收回执不能成为reference。refresh：见证必须等于该照片将携带的完整地图且目标身份仍一致；失败就保留旧像素、标limited，不能只刷新照片而沿用空标签。已有旧参考不因失败获得更强权限。

### 2. 次数、内存及失败后行为

每个目标版本最多一次普通建图见证；每个实际ConfirmedMove.token最多一次候选见证；每份当前参考每60秒至多一次刷新见证。相同位置已完成有效见证的候选提升不再推理。失败不逐帧重试：该目标limited，下一真实目标版本或明确恢复代次才重新获得普通建图预算。一次失败不影响合法落子识别。

为处理旧空标签矛盾，下面另有**每份参考至多一次**的冲突见证；整板一次同时检查所有当前争议格。无预算时只撤销相应空标签权限，不能继续静默无限压制。这个上限是明确性能取舍，不能暗中扩成按每格每帧运行。

已有实测普通推理约0.26秒可作为成本量级参考，额外调用预计增加相近一次推理及预处理，但本提案**没有RK实测增量、不能承诺毫秒数或零掉帧**。同一worker同步见证会短暂推迟下一次普通循环。额外持久内存仍只有一张约1.1MiB灰度候选及小矩阵；见证期间约3.3MiB BGR副本和现有推理工作区是短暂成本。采用前须接受这个性能预算；实现后只做一次代表性设备验收，不在方案阶段重跑模型/benchmark。

### 3. 分类器仍可能错，不能无限信旧空标签

历史有效格首先要求reference.board==expected，已接受的新白/黑子不能被旧空标签否决。但这还不足以处理“照片与地图同时漏了一颗真实子”。

增加局部、由新证据触发的权限撤回：未经参考修正的平均流在同一空标签格累计达到现有move_confirm_frames次有置信度支撑的非空观察时（复用本参考已有disagree计数，灯/无图/运动不计），冻结争议格并使用上面的单次冲突见证。该阈值是证据出现次数，**不是给所有格设置全局若干秒放行计时器**。

- 未平均见证也看见该子：撤销这些格的旧空标签否决权限，让原有确认及游戏合法性继续判定；不得仅靠像素相似宣布“没有子”。
- 未平均见证仍为空或与平均流冲突：状态为disputed/limited，这些格同样不能被旧参考静默无限压住，但也不自动提交该子；沿既有低置信/歧义确认通道请求用户判断，沿用冷却和deny_stone处理。
- 该参考冲突见证预算已用完：新持续争议格进入相同disputed通道，不增推理，不回到无限否决。

这明确改变了旧“空标签可永久压制”的局部权限，代价是某些长期模型假阳性需要用户确认一次；不能把这写成没有行为权衡。当前current参考同样适用，避免同源见证的一次语义漏检被升级为永久事实。新参考恢复权限必须重新经过同源见证；把同一张争议图简单重命名不重置权限。

最小回归复用现有independent-average-capture-reproduction的确定性平均延迟案例，分别覆盖普通capture、候选和refresh：未平均17/平均16不能安装current16的空标签照片；另验证单次语义漏检后持续非空证据进入撤权/歧义路径，不能无限静默否决。无需真实模型运行。

## 四、R2：真实相机接口及LED关灯完成边界

### 1. 小型camera元数据，不假设已有stream_id

camera.py目前只有read_frame_identified返回seq/ts；重连可发生在read内部，controls_effective前后都为True也不能证明中间没换控制。本提案明确增加一个小接口 `read_frame_with_metadata()`，返回帧和不可变FrameMetadata，均来自同一_frame_lock保存的最新帧条目。元数据包含stream_generation、frame_seq、camera_read_monotonic、controls_requested_generation、controls_applied_generation、controls_effective和controls_completed_at。

stream_generation由camera owner在每次成功open/reopen时递增；_mark_disconnected/close使当前状态不可用。复用现有_controls_generation、request_controls和_apply_pending_controls，补一个applied_generation及完成时刻。reader在cap.read前后检查stream/control代次未变；若中间改变，这张帧的控制归属标unknown，不猜测。把完成的元数据与_frame同时发布；消费端不能用读完后才查到的全局最新generation给旧帧补标签。

free模式也调用这个元数据接口，与trace开关无关，只是锁内多复制几个标量，不增加采集。测试相机不提供接口时，普通落子照常；**禁用跨BIND照片保留及新的完整参考/候选提升，状态limited/unavailable**，不能虚构generation。既有照片若仍能比较只能受限历史使用，并受R1争议撤权约束。

**生产CameraHub接线补充：**server.py:938创建CameraHub、:976将其作为VisionService(frame_source=camera_hub)，service.py:138再传入InProcessAdapter；worker收到的是Hub。必须在`katrain/web/core/camera_hub.py`新增同名read_frame_with_metadata，沿用现有read_frame_identified(:313–320)的非阻塞_lifecycle_lock和_can_read()（含启动/USB/startup门）。可读且底层支持时，直接原样返回CameraManager的(frame, immutable FrameMetadata)；锁忙、USB阻断、未启动或底层缺接口返回(None,None)/显式unavailable。Hub不在read_frame后另查controls拼元数据，不建立第二套generation，不重写seq/ts。free worker读取的是这个Hub接口。一个Hub(fake manager)用例检查帧/metadata原样身份及锁/USB门即可。

有控制能力的相机要求requested==applied、effective=True、帧归属已知且时间晚于控制完成和稳定边界；pending/unknown不合格。明确不支持控制的owner可标effective=False的advisory模式，但仍需真实stream/request代次、无pending、两张不同序号稳定帧通过check_frame_exposure。

**曝光阈值纠正：**实际check_frame_exposure只有单帧median/clip/shadow统计及过曝/欠曝门；_LocalWindow.observe_lighting只累计坏帧和时间。不存在前稿声称的“既有board-median漂移稳定阈值”，该措辞撤回。此处明确新增、仅供advisory参考资格的保守常量`REFERENCE_ADVISORY_MEDIAN_DELTA=5.0`：同stream/control、LED边界之后的两张不同序号稳定帧，对同一未平均warp使用check_frame_exposure的降采样灰度median，绝对差<=5.0（8bit灰度0–255）才通过；差>5或任一帧不合格就limited，不运行见证、不提升参考。常量是本提案的初始策略，未做RK现场标定，不能声称设备已验证或硬件曝光锁定。普通free也执行这个已有单帧曝光检查及新增两帧差检查，不能借local-window中才执行的检查作担保。fake测试只需差值5/6及pending边界，不增加现场测试。相机不提供所需事实则按上段禁用新参考资格。

### 2. LED意图不等于已经熄灭

不把SET_LIT_POINTS([])或_led.clear(strict=False)的入队成功当作dark。LedService._run_batch已在SHOW成功ACK时得到shown_at；增加**单个不可变lighting快照**，标明最近请求的LED代次、成功SHOW的代次、该批最终是否全灭、shown_at及连接代次。所有会改变显示的set_points/clear/RGB路径都更新请求代次；未知命令、失败、重连及新亮灯请求立即撤销全灭资格。

**实时资格补充，取代仅靠orchestrator tick的设计：**tick只可以转发显示状态，不能作为采集资格权威。实际LedService所有set_points/clear/set_rgb_points最终进入_submit；_submit已有_usb_lock，_finish也在此锁内提交结果，begin_usb_recovery同样持有它。增加的lighting request代次、ACK快照和生命周期失效标记统一由这个现有_usb_lock保护。_submit必须在任何新显示批次入队/可被串口线程执行**之前**，同步递增request代次并撤销dark资格；失败/丢批也不能恢复旧dark。set_rgb_points等入口准备命令期间尚未显示，不需提前声称灯变了；实际请求进入统一_submit即失效。相机无关的LED断线/open/close/recovery生命周期更新也在同锁下撤资格。SHOW成功只在其batch request代次仍是最新、连接代次一致、最终全灭且无错误时发布dark ACK；旧ACK不能覆盖较新亮灯意图。

生产server把现有LedService作为`lighting_owner`传入VisionService，再由service.start传到InProcessAdapter；不增加新owner。worker在普通capture、候选暂存、候选提升、refresh和BIND保留资格的入口直接从这个owner读取最新快照，不依赖orchestrator是否tick/早退。参考见证推理前记下lighting token，推理后再验证；NPU期间不持LED锁。

最终创建/替换/提升动作使用一个小接口`LedService.try_commit_reference_lighting(token, local_commit)`：持现有_usb_lock，核验最新request/ACK/连接代次、dark及USB状态仍与token一致后，仅执行worker本地参考/候选对象与预算的短赋值；否则返回False并limited。local_commit不调用service、trace/回调、LED、摄像头或推理，不获取其他owner锁；追踪输出移到锁外。新请求要么先在同锁撤资格、使提交失败，要么发生在参考提交之后，二者有明确顺序，没有“新灯已请求但tick尚未清旧dark”的窗口。锁不跨串口等待、NPU或图像处理；既有intent_lock→usb_lock方向保留，commit不反向获取intent_lock。worker命令属于同一worker线程，binding/target在此短提交期间也不被另线程改写。

这个同步检查在paused、attention及awaiting_removal导致orchestrator早退时仍生效，因为执行点在LedService统一_submit及worker最终采纳，不在tick。只能拿到异步lighting缓存而无法访问上述owner门的路径，明确禁用新参考/候选提升及跨bind照片保留，降为limited，不能把缓存当即时有效证明。配置明确LED禁用时使用固定no-light门；未知/断开不等于无灯。这个接口只保护采集与采纳的资格，不把新亮灯误说成应该删除已正确拍摄的历史照片。

照片资格要求camera_read_monotonic晚于`shown_at+200ms`，并且已经取得两张不同frame_seq、同stream/control代次的稳定post-boundary帧；末帧曝光合格、同源见证没有LED检测。旧于ACK、仅逻辑空集合、只有一个新帧或恢复中的图一律拒绝建图/候选/refresh。200ms加两帧是本提案的保守操作边界，不冒充传感器曝光时间或绝对光学无漏光证明；若硬件仍有可见灯或不满足检查，就limited。持续照明误判仍由R1局部争议撤权而非永久否决兜底。

### 3. 同源BIND的保留条件

普通BIND继续epoch+1、清旧move/候选、重绑sync，不扩大local-confirmation早退。service复用binding_game_identity，同时比较session对象、sessionId、模式及worker实例代次，传递稳定源nonce和允许保留意图。worker在执行BIND时比较实际新接口的stream/control/geometry/lighting连续性；只有全部与参考资格一致、无pending/recovery时保留照片。信息缺失走保守清除。新game复用sessionId、模式变化、worker重启、geometry改变、USB/相机重开、控制改变、显式RESET_SYNC/UNBIND都不能继承。

保留图先是历史；新epoch的expected发布后才重关联到相同实际目标，BIND到SET_EXPECTED之间不能用旧目标建立新current。参考若之前已被失效清除，不因重复绑定复活。

本节新增文件明确包括camera.py、camera_hub.py、led_service.py及server/service到worker的lighting_owner接线；没有假称这些generation/ACK字段已经存在。orchestrator只转发显示状态，采纳权限不靠它的tick。有限fake测试覆盖观察之间完成的reopen/control变化、pending controls、Hub原子透传/缺metadata、帧早于关灯ACK/settle、新亮灯请求在资格读数与最终采纳之间进入_submit（不调用tick也必须拒绝）、advisory median差5/6即可，不做USB故障战役。

## 五、R3：精确接受回执及FIFO顺序

第一阶段**仅为实际本地free-vs-AI提交**做候选交接；远端PvP、platform gateway、ranked等未提供精确本地提交结果的路径不生成候选接受回执，仍可在当前目标有同源合格帧时直接建参考，其他时候limited。不能把远端请求HTTP成功当作某个本地node的照片归属。

现在_submit_confirmed_move返回节流float，_do_play没有不可变接受结果；A修复也不自动提供B回执。B明确增加一个内部、可选的“提交快照收集器”参数，沿WebKaTrain.__call__传入_do_play。只在_do_play现有ai_ladder_commit_lock内部、game.play真正成功并记下end事实后、释放锁及广播/启动后续AI之前执行。收集器不是外部回调：只复制已提交game/node/parent的身份和真实stones，构造不可变board，并把service命令入队；无await、无相机/LED/模型工作。非法落子、最小用时限制未落成、EndgameConflict等played=False路径绝不能调用。

回执包含：源nonce/worker代次、捕获的VisionBindingSource及binding_epoch、原ConfirmedMove.token（三元组）、候选基线revision/node、实际accepted node/parent、接受整板副本，以及本次权威发布得到的目标revision。收集器在游戏提交锁内验证基线node/source仍匹配，采用既有“commit lock→service metadata lock”锁序检查source并入队。坐标转换用实际提交node的stones；不在锁外读“current”来认领某个稍后AI节点。

service提供一个限定的 `publish_accepted_reference` 操作：在同一_metadata_lock内验证源、发布精确接受board/node对应SET_EXPECTED_BOARD（已有相同发布可复用revision），随后入队ACCEPT_REFERENCE_CANDIDATE。如source检查失败，不排任何提升命令。这个位置在现有真正落子提交期间，不能移到外层finally或伪称float就是receipt。

规定同一service→worker FIFO的顺序：

1. 成功提交锁内：SET_EXPECTED_BOARD(实际accepted17, revisionR) → ACCEPT_REFERENCE_CANDIDATE(token, accepted17, R)。
2. 后续AI/导航发布可在其后排新的SET_EXPECTED_BOARD(18或其他位置)。
3. 外层_submit_owned_confirmed_move的finally继续发布最新权威，再RELEASE_CONFIRMED_MOVE(token)；B回执已经在成功提交时入队，所以RELEASE不会先删掉成功候选。

拒绝路径无接受回执，finally仍按现有规则释放/重布防，候选被撤销。回执、release、reset及bind都精确匹配token/源；旧epoch回执不能提升。新命令不回滚game/cursor/expected。A最终权威helper是本地合法性/位置读数的前提；B将在A合并后接入这一个收集器，不假定A已经实现它，不在本提案重做A。

候选只有一份，TTL仍5秒或8个后续合格观察（先到为准），拒绝/释放/换epoch/模式/控制/geometry/reset即清；slot occupied不追加仓库。主流合法落子不因候选见证失败、超期或参考limited而停顿。

## 六、R4：迟到回执一律不替换较新目标的参考

使用service每次真实目标变化生成的expected_revision，加源nonce、epoch、node_id和board摘要组成TargetKey；同盘不同node、undo和新分支都产生新revision。它表示发布代次，不用棋子数或node depth排序。

**收紧第一稿：ACCEPT只有在其完整TargetKey等于worker当前TargetKey时才有资格提升。** 若当前目标已18，accepted17迟到，一律丢弃，哪怕暂时还没有18参考，也不把17改成唯一历史仓库。这样无需比较含糊树上年代，也不会覆盖已建current18；所有已有reference对象、预算与权限原样保留。

正常FIFO里回执17会在发布18之前处理，因而仍能利用真实17帧；若异步迟到错过，就诚实limited，不追求补齐历史。合法undo到17会获得新revision，例如R20；旧17回执R17仍丢弃，新的干净17同源见证可建current(R20)，因此不阻挡真正导航/新代次。重复同token回执幂等，不刷新预算、不重写照片；当前已有同TargetKey更晚合格照片时，旧候选也丢弃（比较同stream内的frame_seq；不可比则保守丢弃）。

## 七、当前/历史状态与物理不可能性

保留一个ReferenceFrame、一份候选和少量元数据。reference_position保存真实照片的TargetKey/帧身份/资格；reference_target是当前记录；reference_status为current/pending/limited/unavailable；historical valid_cells要求标签与当前expected一致，再结合usable、lit/released和R1争议权限。expected改变即失去“完整current”称谓，已批准的新子格不套旧空标签。current也只是经过明确同源检查的模型证据，不是无误地面真值。

目标更新后暂为pending；5秒没建current转limited或unavailable，但不暂停识别、不触发自动resync、不处罚用户尚未摆AI子。后续新位置/明确恢复代次的合格图可恢复。16-only窗口没合格帧就确实没有16照片：不能从17倒造、不能恢复已过期历史，也不会增加一手白棋或绕过规则。

vision/status添加reference_status、目标/照片node与revision、简短reason。不能并入recognition_ready制造设备断线/A恢复弹窗。UI沿现有状态位置显示一项非阻断文案，优先级低于摆子/缺子/设备提醒，最多一张目标viewport预览确认；不得另开模态框。比较图标“历史参考15；当前目标16”并保持真实源。具体文案是后续轻量UX确认项，不影响本稿证据权限契约。

## 八、准确涉及范围与最少验证

| 文件 | 限定改动 |
|---|---|
| katrain/vision/camera.py | 一个带owner stream/control代次的原子帧元数据读取接口；显式unknown，不监控系统。 |
| katrain/web/core/camera_hub.py | 生产路径原样透传read_frame_with_metadata及原有生命周期/USB门；不再造generation。 |
| katrain/web/core/led_service.py | 复用SHOW ACK/shown_at；统一_submit在现有_usb_lock下先撤资格，公开快照及同锁短采纳门，覆盖全部显示写入口。 |
| katrain/web/core/physical_play_orchestrator.py | 原tick可转发lighting显示状态；不负责即时采纳资格，不改expected或增加串口等待。 |
| katrain/vision/service.py、ipc.py | BIND保留nonce/实例代次、接受回执与状态字段，FIFO和source验证。 |
| katrain/vision/worker_inprocess.py | 一次同源见证、一候选槽、资格/连续性、局部空标签争议权限、TargetKey提升规则。 |
| katrain/web/interface.py | _do_play提交锁内的限定不可变快照收集器；既有落子规则不变。 |
| katrain/web/server.py | 将既有lighting_owner接到VisionService；仅本地free提交传入收集器，拒绝无receipt；finally仍release，不能复用float充当结果。 |
| vision API status、UI api.ts/VisionContext、现有PhysicalPlayStatusChip/GamePage | 小型状态契约与非阻断显示，A完成后顺序整合。 |
| reference_trace.py | 已启用诊断时标明current/historical/valid-cell，不加永久采集或SCP功能。 |

沿用当前测试与复现工具，不建新框架：

1. 2→4同源重复BIND照片保留但epoch/旧事件隔离不变；换game同session、worker/模式/geometry/camera/control边界不能保留。用一组参数化fake覆盖R2边界和post-LED-ACK帧。
2. 原平均延迟复现覆盖普通/candidate/refresh，禁止17图/16标签；同源见证仍可能一次语义错判时，持续矛盾走局部撤权/歧义，不无限静默空标签否决。
3. 本地成功提交、较新target发布和final RELEASE交错：只认实际accepted node，receipt在release前入队。拒绝、错误token、旧epoch、过期、不合格见证都不提升。
4. current18已捕获→17回执：对象/预算/权限不变；undo的新revision可正常建参考，旧receipt不能借board相同复活。
5. 一次状态组件/API检查和一个viewport预览。设备/性能验收只在方案接受与实现后单独进行，不在本轮追加模型、相机或USB实验。

## 九、审核结论应对应的边界

本稿推荐接受的性能取舍是一份有限快照加每次明确采纳动作至多一次现有模型见证，另每份参考至多一次争议见证；不是零额外NPU。若用户不接受该成本，明确使用single-contributor-only备选并承认参考经常limited，不能删掉见证却保留同等安全承诺。

R1关闭已知平均源错配并撤销持续争议的永久空标签权；R2新增真实可读owner元数据和ACK后帧边界；R3在实际play提交锁内制作精确接受命令；R4丢弃所有不属于当前目标的迟到回执。仍不保证分类器零语义错误、不保证每手物理上都有合格照片，也不声称本B方案修复了A轮次/缓存问题。
