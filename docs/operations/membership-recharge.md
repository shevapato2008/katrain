# 会员、实时额度与按次充值：实施记录

> **2026-11-09 微信 Native 发布：** 用户已授权继续集成部署，最新精确版本、两云及实体状态见[发布回执](wechat-native-release-2026-11-09.md)。会员/充值扫码、验签解密、查单及原子到账已实现，保留11语；真实收款仍关闭，资料尚未准备，见[安全准备指引](wechat-native-credentials.md)。下方旧“候选/未发布”段落仅为历史。

> **2026-11-04 国际化已发布：** 会员、用量与充值已补齐 11 种语言，独立 Astra Max 代码/翻译/视觉审核 Approved。两端实际 Web 软件为 `959800a4679447b871c7ad6ef89d062e93cd15bb`，先 TEST 后新 PROD 验证通过；仅 Web/static/语言包更新，其他服务与支付边界保持。当前版本、验收入口和设备边界见[国际化发布回执](membership-i18n-release-2026-11-04.md)。

> **2026-11-02 Max 与提示修订已发布：** 用户授权开放 Max，双端增加 30 天总量与钱包最高扣费确认；实际新 Web 软件为 `7f2ff0c65381250e41a9dc959d8cac9201c3a86b`。Max 独立开关及运行时可售判定已为 true，价格/预算不变，优先于下方旧停售记录；主服务仍 paused/disabled，真实商户收款仍属未完成的阶段 B。清理最终状态与实际版本以[本轮发布回执](membership-max-release-2026-11-02.md)为准，后续 docs 提交不冒称镜像版本变化。

> **2026-11-02 软件实施与验证：** 最新代码检查点 `952580756fae2c64d2ce05695c98c3e3313c5ac8`。分包已独立规格→质量闭环；[全功能Astra终审](../superpowers/reviews/2026-11-02-membership-final-astra-r1.md)已批准，0未解决Critical/Important，研究setup/PL与报告改谱/同步冲突均闭环。组合后端571通过／1个历史PG变量未设跳过（新PG均实际执行），修复后前端212通过、相关后端97通过；普通与严格Kiosk构建均通过。真实完整API/JWT/HMAC/mock引擎HTTP＋worker旅程4通过。尚未push／合并／部署；下方v2/v3与早期未开发记录为历史。

> **当前简单方案与自主执行：** [2026-11-02新计划](../superpowers/plans/2026-11-02-membership-simple-implementation.md)及[最终设计](../superpowers/specs/2026-11-02-membership-simple-final-design.md)优先于下方历史。用户授权Astra决策后直接开发；39/99/199、本期30/90/240、周最多约10/30/80已由Astra首轮裁定，计划第二轮最终审核已通过（0未解决问题），已进入SDD开发。不再等待人工视觉确认，仍做真实预览及独立代码/视觉审核。软件、真实收款与Max实际可售分别验收，不混称完成。

> **最新v3.1：** 用户反馈后的[展示/自动回退修订](../superpowers/specs/2026-11-02-membership-presentation-and-fallback-amendment.md)优先。UI隐藏标准单位、独立百分比、日均普通报告1/4/13盘，候选39/99/279；会员优先、不足时自动使用已有API积分，完整operation单来源。双端Fixture与Astra增量复核通过，待用户视觉确认；真实后端未实现。下文29/99/299及不自动回退等为历史记录。


> 最新用户方向（2026-11-01后续）：暂停按旧v2商品实施。改为积分充值＋统一请求预算、取消24h和报告/互动双资源；Plus参考每盘300手，周7盘／30天30盘，高级按4倍。见[候选v3修订](../superpowers/specs/2026-11-01-membership-points-and-request-budget-v3.md)。已有V100测量与价格情景，候选价格和新视觉均未获用户确认；下方v2完成记录只作历史，不能据此继续原后端或发布。

v3设计已完成两轮Astra Max审核：[最终Approved报告](../superpowers/reviews/2026-11-01-membership-request-v3-astra-r2.md)，未解决问题0。公开305手／306位置500visits完整串行实测397.484秒，按300手归一和3500元月租满载摊销，30盘纯租金约15.84元；先前39.45～68.50元是含κ50%及20%预留的经营情景，不是实测成本下限。保留29/99/299价格候选，Pro/Max暂4/13倍，但未获用户批准、Max仍不可售。v3隔离UI已完成并经独立Astra Max代码与视觉审核通过，待用户视觉确认；后端未实施。

另有独立[单引擎与多服务调研](katago-single-vs-multi-service-2026-11-01.md)和[阿里／腾讯GPU价格核查](cloud-gpu-pricing-2026-11-01.md)。同卡多进程未做公平A/B，不能假定提速。腾讯V100官方公开价格索引包月5190/5750元、盘网另计，三年预付均摊2595/2875元但不是月付；用户已补充阿里官方页截图：V100限1件3817元/月起、旁列官网折扣价4579元；A10限1件3203.99元，续费、盘网及重复扩容未核实。主稿3500元仍是用户指定假设，迁移须按真实配置单重算，不能预支降租或开售。按同速及满载假设，阿里3817/4579情景下Plus纯租金为17.27/20.72元，见[补算](aliyun-gpu-cost-sensitivity-2026-11-02.md)。

## 当前阶段

2026-11-02 01:55：新简单计划两轮Astra Max已批准（0未解决问题），开发按SDD进行。设计证据检查点55cbbccb8；严格引擎请求合同cc4e132c1已经独立规格→质量审核通过，复验49项通过（实现者相关回归60项通过），尚非整功能终审。专用本地PG及独立TEST身份标记已就绪；基础schema/模式隔离、原子账务、不可变云身份、共享UI及Galaxy页面正在并行实施。无推送、合并或部署，正式支付/Free可信身份/Max容量仍待实际前置核查。

### 历史阶段记录

2026-11-01，Task 1.2 现状核查完成。权威实施依据为[已通过两轮评审的计划](../superpowers/plans/2026-11-01-membership-usage-and-payments.md)及[Codex 交接](../superpowers/handoffs/2026-11-01-membership-recharge-codex.md)。本记录是源码基线核查，不是业务实现、代码审核通过、TEST 验收或正式收费完成的证明。

- 工作区：`/Users/fan/Repositories/katrain-membership-recharge`。
- 分支：`feature/membership-recharge`。
- 实际核查 HEAD：`0d938a0b009f48b3a98803cd03446ce7f26375e8`，开始核查时工作区干净。
- 该提交为 `prepare membership plan and Codex development handoff`，直接父提交为交接所述 `f43b673d71ba9bc7a65344dd5c587ff9f4c1436b`；两者差异只有七个设计、计划、评审和交接文件，产品代码一致。没有重建 worktree 或另行抽取 Elasticsearch 分支。
- 本次没有读取部署环境或密钥文件，没有访问数据库、GPU、生产服务或支付渠道。下表记录代码默认值和实现能力，不推断服务器的实际配置。

## 代码默认值与资产基础

| 项目 | 核查事实 | 源码证据 |
| --- | --- | --- |
| 旧收费总闸 | `BILLING_ENFORCED=False`；关闭时报告不扣余额、不消费免费桶 | `katrain/web/core/config.py:99`；`katrain/web/api/v1/endpoints/reports.py:277` |
| 新功能/支付模式 | 尚无 `BILLING_V2_ENABLED`、`KATRAIN_DEPLOY_ENV`、`PAYMENTS_MODE` 配置或相应启动组合校验 | `katrain/web/core/config.py:40` 至文件末尾 |
| 新用户余额 | ORM 与响应模型均默认 0；注册赠额默认 0，显式启用后才走账本 `grant` | `katrain/web/core/models_db.py:82`；`katrain/web/models.py:212`；`katrain/web/core/config.py:95`；`katrain/web/api/v1/endpoints/auth.py:552` |
| 旧商品/动作价 | 仍公布 `p6/p30/p98` 与 territory/hints/variations 各 10 credits；未有 v2 catalog | `katrain/web/core/config.py:88`；`katrain/web/api/v1/endpoints/billing.py:110` |
| 余额账本 | 已有整数 `User.credits`、唯一 `ref_id` 交易账本及 reserve/commit/refund/grant；旧 reserve/grant 并发冲突后的重复补偿错误已修复，不能继续照搬旧 track 的事故描述 | `katrain/web/core/billing.py:69`、`:105`、`:164`、`:176`；`katrain/web/core/models_db.py:1600` |
| 事务所有权 | 旧 reserve/commit/refund/grant、quota helper 会自行 commit；已有 `apply_adjustment` 为 flush-only 原语，但新双窗口授权不能直接组合旧 helper | `katrain/web/core/billing.py:186`；`katrain/web/core/quota.py:46`、`:81`、`:95` |
| 额度桶 | 仅自然 day/week/month 周期，周键按北京时间 ISO 周；桶上冻结 allowance；无 reserved、24h 共享锚点或会员 term | `katrain/web/core/quota.py:22`、`:25`、`:75`；`katrain/web/core/models_db.py:1663` |
| 旧免费额 | `FREE_WEEKLY_REPORTS=1`，作为普通报告的周桶上限；不是独立互动赠送 | `katrain/web/core/config.py:109`；`katrain/web/api/v1/endpoints/reports.py:324` |
| 迁移 | 手写非破坏性迁移；账本/订单/额度桶已保护，`users`、`report_tasks` 尚未加入 drift 保护名单 | `katrain/web/core/migrations.py:1`、`:19`、`:35`、`:65` |

`Settings` 是 `BaseModel`，自行装配若干环境变量；现有构造函数未装配上述旧 billing 旋钮的环境变量。发布时必须核实并实现实际配置入口，不能以 shell 中存在同名变量推断收费已开。

## 旧报告与读接口

- 云端检查个人棋谱 owner，并在非 force 情况去重 authorizing/pending/running/completed 报告。旧收费路径先落 authorizing 和授权意图，再用免费周桶或自动回退钱包，最后设 pending；这是 legacy 多次 commit 流程，不是新计划要求的单次授权事务。见 `katrain/web/api/v1/endpoints/reports.py:247`、`:258`、`:298`、`:314`、`:336`。
- 旧批量报告按 `ceil(N × visits / 1000)` 计算（有效模型默认 b28），非零最低 1 credit；250 手、500 visits 为 125 credits。v2 的报告最低 10/40 credits 尚未实现。不能把独立标准互动 10 credits 乘到报告每一手。见 `katrain/web/core/analysis_cost.py:13`、`:34`。
- 旧结算按 completed 或 failed 超过重试宽限期处理，按累计成本之差结算，部分分析可收费并退估算差额；运维豁免可全退。旧 retry 宽限期内复用原授权，之后为剩余量重新预扣。v2 完整交付才结算、失败全退和新 attempt 授权需要明确分流，不能改变旧任务价格。见 `katrain/web/core/report_settlement.py:20`、`:26`、`:50`；`katrain/web/api/v1/endpoints/reports.py:429`。
- `/billing/quota` 先做用户终态结算，再调用会开桶/commit 的 `quota.peek`；返回旧 free_weekly 和按 250 手估算。新 usage GET 必须用独立纯读取契约，不能重用该写入路径。盒端现有 `/billing/balance`、`/quota`、`/redeem` 均返回 503 `need_online_billing`，尚未接云端 proxy。见 `katrain/web/api/v1/endpoints/billing.py:70`、`:78`、`:94`、`:120`。
- `/reports/{id}/moves` 当前只检查 owner，随后直接返回逐手分析；没有 completed + operation committed 交付门。worker 逐行保存后才置 completed。见 `katrain/web/api/v1/endpoints/reports.py:511`；`katrain/cron/jobs/report_analyze.py:230`、`:279`。
- 真实 `KatagoClient.analyze()` 已有模型 SHA/final/turn/ownership 等校验入口，但调用未传 requested min_visits，helper 默认仅 1；v2 必须穿过真实 client 严格校验，并核对 0..N 的 N+1 位置。见 `katrain/cron/clients/katago.py:98`、`:105`。
- 普通个人棋谱删除没有活跃 v2 账务守卫，关系可级联删报告；旧 requeue 会删逐手结果、重设 pending 并设豁免。旧通用 TTL 排除 `reason=report`，report reaper 另行管理旧引用。v2 必须保留 receipt、拒绝活跃删除/旧 requeue，并与旧回收器隔离。见 `katrain/web/core/user_game_repo.py:377`；`katrain/web/core/models_db.py:1460`；`katrain/cron/jobs/requeue_reports.py:110`；`katrain/web/core/billing.py:292`；`katrain/web/core/report_reaper.py:17`。

## 身份、盒端权威与付费入口

| 边界 | 实际能力与缺口 |
| --- | --- |
| P0 启动密钥 | 已有 server 启动前空值、过短和默认值拒绝，不能声称仍以仓库默认密钥正常启动。未读取实际密钥。证据：`katrain/web/core/config.py:14`；`katrain/web/server.py:273`。 |
| P3 手机绑定/注册限流 | 核查用户 schema、auth/core 与 API 源码，未发现本站手机号绑定/验证码 challenge 或注册限流实现。`/auth/register` 接受用户名/密码；strict Box SSO 会拒绝直接注册，普通 server 注册仍无该 P3 守卫。证据：`katrain/web/core/models_db.py:70`；`katrain/web/api/v1/endpoints/auth.py:518`。 |
| 第三方短信 | `platforms.py:414` 是已登录用户向第三方星阵申请验证码，不构成本站 Free 领取的可信身份事实。 |
| Free 正式前置 | 现有 health 规则在收费开启且免费额大于 0 时报告错误，说明 P3 尚未上线；此核查未验证任何外部身份系统已满足前置。TEST 以后应以隔离测试主体验旅程，PROD 缺前置显示“完成验证后领取”，不能宣布 Free 正式领取已完成。证据：`katrain/web/core/health_report.py:47`。 |
| 盒端绑定 | 已有 `cloud_session_is(user_id)`，明确 `RemoteAPIClient` 为共享进程单例；`_remote_only` 仅处理连通性/HTTP 错误，不做用户绑定。证据：`katrain/web/core/repository.py:369`、`:422`。 |
| 远端请求 | 已在 401 refresh 前后核对 refresh token + bound user，且 logout 清绑定；尚无付费方法的不可变请求身份/generation 契约，不能把已有 refresh 防护等同于完整发送前防错扣。证据：`katrain/web/core/remote_client.py:73`、`:97`、`:122`。 |
| 普通 Kiosk 局面 | 尚无计划中的有界完整 SGF paid-analysis 方法；已有 reports remote-only 与 PVP 专用 room bridge 不能证明云端可加载普通 local session。新请求需捕获云端身份，在发送/刷新时校验绑定，不允许本机 SQLite 授权资金。 |

需要封闭的实际分析入口仍与已审计划一致：

- `/api/v1/analysis/analyze` 直接转发 payload；`quick-analyze` 接受客户端 visits 并返回 ownership/候选着法；均已有 ranked 守卫，尚无会员 operation 授权。见 `katrain/web/api/v1/endpoints/analysis.py:15`、`:48`，挂载 `katrain/web/api/v1/api.py:31`。
- `/api/v1/hint` 已有场景/anti-cheat 守卫，但 `DefaultHintGate` 是配置 gate，settle 为空；不能因接入会员删掉原 ranked 限制。见 `katrain/web/api/v1/endpoints/hint.py:51`；`katrain/web/core/hint_gate.py:31`，挂载 `katrain/web/api/v1/api.py:48`。
- legacy current/extra/continuous/game/scan/region、generic action 与 PVP territory 仍需在 Task 7 逐项登记触发/结果矩阵；真实路径见 `katrain/web/server.py:1227`、`:1973`、`:1994`、`:2011`、`:2128`、`:3541`、`:3561`。
- 当前 state 将 node 的 moves/ownership/policy 等组合为 analysis；HTTP state 和 WS 共用 session 快照。v2 必须按接收账号过滤，不能改共享引擎节点或对手/观众共用快照来隐藏字段。见 `katrain/web/interface.py:676`；`katrain/web/server.py:1119`、`:1300`。本次仅核查边界，没有声称已逐条完成绕过验证。

## 支付与后续切片闸门

现有 `RechargeOrder` 有服务端金额/credits 快照和人工确认字段，但未有 v2 SKU/环境/有效期/履约标记；`settle_order` 先 commit paid，再调用 grant，不能承担新订单原子履约。当前 billing 路由仅 balance/quota/prices/redeem，未有真实微信/支付宝或 TEST mock 适配器。见 `katrain/web/core/models_db.py:1637`；`katrain/web/core/billing.py:273`；`katrain/web/api/v1/endpoints/billing.py:67`。

数据库配置缺显式 URL 时会读取用户级或仓库配置；新 worktree 不能证明 TEST 隔离。当前没有计划中的只读 TEST 身份标记核验。mock 必须在任何 schema 写入前拒绝未知/生产目标，应用不能自行标 test。见 `katrain/web/core/config.py:125`；`katrain/web/core/db.py:26`。本次没有导入 Settings 或连接库探测配置。

1. 当前先完成双端新 Fixture 和目标尺寸可操作预览。视觉未明确确认前，不进入对应 schema/事务/API 后端切片。
2. 确认后按已审计划实施单池 credits、双资源/双窗口、完整报告交付、一次互动两种展示；用真实隔离 PostgreSQL 验证行锁、回滚与幂等，SQLite 不作并发正确性证明。
3. 阶段 A 尚未完成：业务后端、隔离 TEST 模拟支付与双端真实接线均待实施；不能以 Fixture 成功动画代替真实事务验收。
4. 阶段 B 未验证：未核验商户签约、资质、凭据、真实支付通知/查单/退款、P3 外部前置或当前 GPU 容量。模拟支付不代表正式收款；Max 容量未通过时不得默认为可售。
5. 独立代码与视觉审核、TEST 验收通过后才执行既定四步发布；先 TEST `home-ubuntu`，后新 PROD `ucloud-v100`。本次未提交、推送或部署。

核查方法：读取源码、`git log`/`git diff` 与聚焦 `rg` 检索。未运行产品测试；未修改产品代码。后续实现和实际测试结果在完成时另行追加，不能由本基线核查推定通过。

## 本轮设计切片进度

用户后续明确要求先用 `claude-design` 设计、`ui-ux-pro-max` 优化，并把 Kiosk 模块加入现有围棋设计合集。本轮因此先完成 Task 2 设计 Fixture；Task 1.3 的服务端纯目录规则及后续后端尚未开始，不把设计目录快照算作已实现服务端 catalog。

- Kiosk 入口：[合集 · 会员用量](../design/kiosk-current-based-redesign-2026-10-14.html#membership-usage)，同组包含订阅、按次充值、TEST 收银台；新增文件隔离在 `docs/design/kiosk-unified/membership.{js,css}`。
- Galaxy 入口：[网页 Fixture](../design/membership-recharge-2026-10-31/index.html)，旧 Kiosk 链接转至合集。字段、固定示意时钟、价格和退出条件见[设计说明](../design/membership-recharge-2026-10-31/README.md)与[契约快照](../design/membership-recharge-2026-10-31/contracts.json)。
- 双端真实浏览器代表预览、截图与旧稿同尺寸并排／叠加／差异已经保存；聚焦交互和语法检查见设计说明。此处没有接真实业务服务或模拟支付服务，不是阶段 A 完成。
- 独立 Fixture 规格复核通过；[Astra Max 设计代码与视觉审核](../superpowers/reviews/2026-11-01-membership-fixture-astra.md)已 Approved，无未解决问题。用户视觉确认待取得；不等同于后续完整业务代码审核已通过。
- 当前不推送、不部署，不进入会员购买／用量后端切片。确认后从 Task 1.3 的目录规则及 Task 3 持久化继续，后续完整代码审核、真实 PostgreSQL、TEST 和发布要求仍须执行。

## 管理端与发布边界

前台1显示积分＝100原整数credits。既有admin/users余额、调账与兑换码工具历史“积分”文案仍指整数credits；运营输入和流水必须按credits处理，不能把前台显示积分原数直接调账，也不能缩放已存本金或账本。本期不扩大为重建独立admin服务。

主TEST现有katrain_db为superuser连接且没有独立TEST标记，不直接启用mock。受控模拟收银使用专用数据库、非superuser业务角色、独立owner的只读control标记，必要时临时独立app端口；主TEST和PROD软件以paused/disabled发布，不改既有TEST数据、ES、媒体、SSO或数据库服务。正式商户adapter、真实验签查单/试付退款、Free可信身份/注册限流与Max容量仍未完成。

首次财务发布不得自动启动旧f43 Web/Cron回退镜像。失败停止本次candidate、保留原stopped backup和私有manifest、向前修复；不得清activation或切legacy恢复免费私有分析。实际发布版本和服务回执待后续记录。
