# Membership plan — Astra Max review, round 1

**Verdict: Needs revision. Critical: 0. Important: 6.**

评审对象：`docs/superpowers/plans/2026-11-01-membership-usage-and-payments.md`，完整257行、全部4个Chunk；本轮按一轮计。背景稿仅用于补充，冲突处以计划为准。本轮只读源码并写本评审；未实现产品代码、运行GPU、访问生产、读取env/私钥、提交或推送。

计划的主体方向可执行。需要修改的是以下具体边界；不要求另建钱包、认证平台、消息系统或通用支付中台。

## I1 — 直接代理引擎的v1入口未进入明确改造清单，仍可绕过新收费路径

**计划位置：** §3.3（127–132行）、Task 7 Files / 7.1 / 7.5（217–223行）。列举了`server.py`里的旧分析入口和`/api/pvp/territory`，但没有明确覆盖下面三个现存入口，Task 7文件清单也没有它们。

**源码证据：**

- `katrain/web/api/v1/endpoints/analysis.py:15–36`的`/api/v1/analysis/analyze`把客户端`data.payload`直接交给`router_instance.route`并返回结果；没有账务授权。
- 同文件`48–76`的`/quick-analyze`不需要会话，使用客户端`max_visits`，直接返回候选着法和ownership。关闭公网原始`/analyze`并不能关闭这个已登录的HTTP代理。
- `katrain/web/api/v1/endpoints/hint.py:66–111`经过`DefaultHintGate`后直接调用路由器；`core/hint_gate.py:31–45`明确是配置门控，`settle`为空实现。该入口可以选择cloud引擎。
- 三者仍由`api/v1/api.py:31,48`挂载。

**影响：** 按现有明确文件清单完成新接口和按钮后，Free或额度耗尽用户仍能直接取得同类云端分析；领地与实体棋盘支招也可能各自调用引擎，无法兑现一次分析只扣一次。

**最小修改：** 把上述文件、三个路由及`HintGate`加入Task 7的必做矩阵。v2启用后，统一复用同一已授权operation，或明确拒绝旧raw payload入口；不要只给新按钮收费。为这三个实际路由各补一条Free拒绝/无引擎调用断言，并用一次授权结果验证领地和hint共用，不扩大到无关认证重构。

## I2 — 全额退款规则尚未封闭报告结果的交付口

**计划位置：** §1.3（59行）、§3.2（121–122行）、Task 4.3（188行）。v2规定未完整交付则全额退还，并允许复用“未交付前缀”，但没有规定现有报告读取接口怎样隔离这些前缀。

**源码证据：**

- `katrain/cron/jobs/report_analyze.py:230–274`每分析一个局面就单独持久化，最终`completed`在276–284行才设置。
- `katrain/web/api/v1/endpoints/reports.py:511–539`只校验报告归属，随后返回全部`ReportTaskMove`，不检查任务是否completed或预留是否已退款。
- `ReportTaskMoveResponse`在同文件102–124行直接包含`top_moves`和`ownership`，因此这是真正可使用的分析结果，不只是进度。

**影响：** v2运行中或最终失败的报告，其已完成局面仍能被读取；退款后这些结果也仍可访问。所谓“未交付前缀”实际已交付，完整报告全额退款与独立互动收费边界不闭合。

**最小修改：** 明确v2只在完整报告通过校验并由operation成功结算后交付分析内容；运行中仅返回进度，failed/refunded不返回分析行。可保留内部断点数据供重新授权后的重试复用，legacy保留原读取语义。报告结果GET可触发既定同锁序的终态结算，避免completed到后台结算之间的假失败。增加一个“有前缀→失败退款→读取无分析→重新授权完整成功→重复读取免费”的聚焦用例。

## I3 — 删除棋谱及旧运维重排会越过v2任务/receipt生命周期

**计划位置：** §3.1（98–100行）、§3.2（118–123行）、Task 4（184–191行）、Task 9.6。计划处理了正常结算、retry和通用TTL，但未包含现存的任务删除及重排写入者。

**源码证据：**

- `katrain/web/core/user_game_repo.py:377–405`直接删除个人棋谱；`models_db.py:1371,1460`会级联删除报告任务及逐手结果。
- `core/report_reaper.py:17–48`只扫描`reason="report"`的旧credits预扣，从旧ref格式解析task id，再直接调用旧`billing.refund`。它不知道会员双桶或`BillingOperation`；`server.py:4455–4461`仍周期执行它。
- `katrain/cron/jobs/requeue_reports.py:110–130`会删除completed任务的所有结果并重设pending，仅写legacy的`billing_exempt_reason`，没有operation授权或v2状态分流。
- `tests/web_ui/test_report_reaper.py:26–45`已经明确记录“删棋谱导致预扣孤儿”的真实既有生命周期。

**影响：** 删除活跃v2报告可能留下永远reserved的双桶/operation；若沿用旧credit reason/ref，旧回收器又可能绕过operation直接退款。运维旧重排会删除已付结果，并让已committed的operation重新跑任务，破坏交付与授权的一致性。

**最小修改：** 在Task 4纳入`user_game_repo.py`、`report_reaper.py`、`requeue_reports.py`。一期最小方案是在同一用户锁下拒绝删除存在未结束v2报告的棋谱，并让旧requeue明确跳过/拒绝v2任务；终态删除不得级联删除账务receipt或再次退款。旧回收器必须排除v2资金记录，由v2 operation统一管理。只增加活跃删除、终态删除保留receipt、旧requeue不改v2三个针对性回归，不必新增取消任务平台。

## I4 — Kiosk本地局面如何成为云端可授权对象，尚缺可执行契约

**计划位置：** §3.3（127、129、132行）、Task 5.3（199行）、Task 7.2（220行）、Task 8.6（237行）。服务端从“有权访问的会话/棋谱”构造局面与盒端仅添加转发方法，不能自动组成普通Kiosk对局的完整链路。

**源码证据：**

- `katrain/web/session.py:65,97–114,172–178`的session是各进程内存中的UUID与字典；`server.py:1257–1286`在本机manager建会话。普通盒端session不会因为登录同一云端账号而出现在云端manager里。
- `interface.py:414–450`当前远端分析只按`CLOUD_KATAGO_URL`构造HTTP引擎，不把本地session同步成云端业务对象。
- PVP的远端转发另有`pvp_territory.py:114–140`的room映射；这个专用桥不能作为普通本地对局已经可转发的证据。
- `core/repository.py:369–381`已经提供`cloud_session_is(user_id)`，因为RemoteAPIClient是共享盒子的进程单例；`_remote_only`（422–434行）本身不做该身份绑定检查。新付费方法只复用后者不足以避免甲的本地请求使用乙的云端token。

**影响：** 只转发session_id会在云端404，阶段A双端真实互动无法交付；为了“修通”而信任本机user_id、任意engine payload或旧的进程token，则可能错扣账户或绕开profile/ranked限制。

**最小修改：** 在§3.3冻结一种最小方案：例如盒端在本地归属检查后提交有界完整SGF/局面历史快照，云端用已认证账号、既有ranked守卫和服务端合法性/profile校验生成fingerprint与operation；或先同步为云端用户棋谱，再引用云端id和版本。明确选择其一，不引入第三方API Key。local session_id只用于盒端显示关联，不能作为云端可加载对象。新billing/analysis转发必须核对既有cloud_session绑定，并隔离切账号后的响应。增加“云端不存在本地session也能完成一次付费分析”和“共享盒切账号不读/扣前后另一个人的账”两个契约测试。

## I5 — 报告深度的交付校验仍会把不足500/2000 visits的结果当完成

**计划位置：** §1.2（48–49行）、Task 4.3、Task 7.2。计划在短互动里要求校验root visits，但没有把这个验收要求接入真实报告worker；报告又是会员1/4份及wallet价格的商品基准。

**源码证据：**

- `katrain/cron/jobs/report_analyze.py:313–327`向引擎传入requested_visits。
- `katrain/cron/clients/katago.py:98–101`调用`validate_result`时没有传min_visits；该参数默认值在106行为1，121行因此只要求root visits至少1。
- `tests/web_ui/test_cron_katago_contract.py:29–54`虽有2000 visits校验测试，却是手工向静态helper传`min_visits=2000`，不能证明真实`analyze()`调用链使用了该深度。
- `report_analyze.py:276–284`按遍历完成标记报告completed，不会再依据requested_visits检查各位置深度。

**影响：** 深度报告可能以4份权益结算，交付的却只是低深度结果。仅测试helper、只给短互动加验证，不能兑现报告商品承诺。

**最小修改：** Task 4明确冻结并验证v2报告profile：实际`analyze()`/worker按任务请求深度验证最终root visits、模型与ownership，缺失/不足按失败处理；legacy行为按既定兼容策略分流。用mock HTTP走真实client调用链测试“请求2000返回500不能completed/结算”，无需真实GPU。同时冻结N手报告包含0..N共N+1个位置的完整性口径，保留现有按N手计价的既定产品决策，避免通过手数等于N就误判缺初始/末局面为完整报告。

## I6 — mock只检查进程环境标签，尚未封闭实际数据库的TEST隔离

**计划位置：** §0（21行）、§3.1（95、99行）、Task 3.1（176行）、Task 6.1/6.5（208、212行）。TEST DB拒绝规则目前只写在测试fixture；运行时写了`production+mock`拒绝，但没有约束mock实际连接的数据库。

**源码证据：**

- `katrain/web/core/config.py:123–146`在未显式提供DB URL时，会从`~/.katrain/config.json`或仓库配置读取database_url；新worktree不会天然隔离这个用户级配置。
- `core/db.py:26–31`直接用所选URL建engine。
- `models_db.py:82–84`的`User.credits`是一池余额；给order添加`provider_env`并不能把同一个用户的mock到账与正式余额隔离。

**影响：** 只设置`KATRAIN_DEPLOY_ENV=test`和`PAYMENTS_MODE=mock`即可通过计划中的运行时守卫，随后仍可能使用全局配置指向的数据库。测试管理员凭据也不能改变写入目标；因此现有描述不足以保证“模拟不改正式余额”。这不是对当前生产配置的推断，本轮没有访问生产或读取配置秘密。

**最小修改：** 为mock启动/创单规定显式、独立TEST数据库，禁止沿用用户级配置的隐式回落，并在实际数据库上核验预先设置的环境标记或等价的部署隔离约束；不允许服务自己把未知库标为test。测试角色只拥有TEST库权限即可，不需建立另一套账务表。将“test标签+非TEST/未知数据库仍拒绝写账”加入现有mock boundary测试，与production+mock拒绝一起覆盖。

## 已核对且不要求扩大范围的部分

- 双资源各自24h/自然周、两个窗口同时预留、Free周报告一次且无独立互动、统一24h锚点、wallet明确确认后另付费，这些规则已写清，无须重做商品研究。
- 单池credits、停售低价旧SKU但保留资产、报告wallet最低价和深度4倍、最多500手且不能截断，方向一致。正常250/300/500手会员报告应是一份，不能沿用250手折点导致Plus首盘不足。
- PostgreSQL真实并发验证、user起始固定锁序、无commit原语、退款回原桶、cron独立ORM与web终态结算、legacy free迁移防双赠，计划已有明确要求。
- P3身份/注册限流保持正式Free硬前置，商户能力和容量验证留在正式启用阶段；这些外部条件不应阻止隔离TEST阶段A的软件交付，也不应以模拟结果宣称正式收费完成。

修订上述边界后可进入用户允许的第2轮复核；本评审不要求追加第三轮，也不把未来代码评审、GPU容量验收或真实渠道验收算作本轮已经完成。
