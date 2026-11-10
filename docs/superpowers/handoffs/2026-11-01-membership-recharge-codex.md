# Codex 开发入口：会员、实时额度与按次充值

> **2026-11-04 国际化已完成并发布：** 双端会员、用量、API 充值、订单及扣费提示 328 个键已补齐全部 11 种语言；独立 Astra Max 终审 Approved，190 UI / 14 Python / 7 浏览器覆盖通过。实际两端 Web 软件 `959800a4679447b871c7ad6ef89d062e93cd15bb` 已按四步流程先 TEST 后新 PROD 发布，11 个真实语言接口与实际登录页验证通过。Cron/引擎/数据库及 paused/disabled 边界未变，实体盒子未升级。当前事实以[本轮回执](../../operations/membership-i18n-release-2026-11-04.md)为准。

> **2026-11-02 最新 Max 修订：** Max 独立配置/运行时可售判定已按用户授权开放，双端 30 天总量与钱包最高扣费提示已随 Web 软件 `7f2ff0c65381250e41a9dc959d8cac9201c3a86b` 先 TEST 后新 PROD 发布，Cron 未改。此决定取代下方旧 Max停售状态；整体 paused/disabled 及正式商户阶段 B 未完成边界仍保持，不能声称现在可真实付款。以[本轮实际发布回执](../../operations/membership-max-release-2026-11-02.md)为当前权威；后续仅 docs 提交不改变镜像软件版本。

> **2026-11-02 发布完成：** 阶段 A 开发、隔离 TEST 与 TEST→新 PROD 软件发布已完成；实际部署软件 R 为 `7fb94dce9f3d4e36835843cc8b828eb59245f6f1`，feature/develop/父 main 四步集成已完成。两端主服务保持 paused/disabled，阶段 B 正式收款、可信 Free 身份/注册限流及 Max 容量前置仍未完成并保持关闭。以下“未开发/待确认/尚未发布”均为历史；以[实际发布回执](../../operations/membership-release-2026-11-02.md)为当前权威。后续仅文档的提交不改变此处镜像软件版本。

> **2026-11-02开发收尾：** `952580756fae2c64d2ce05695c98c3e3313c5ac8`已通过独立Astra Max全功能规格/代码/代表性视觉终审，0未解决Critical/Important。组合后端571通过/1历史跳过，修复后前端212与相关后端97通过，普通/严格Kiosk构建通过；真实完整API+JWT/HMAC/worker旅程4通过。当前进入已授权四步集成，尚未推送合并或部署。正式支付、Free可信身份和Max销售前置保持关闭；以operations后续发布回执为实际进度。

> **2026-11-02当前自主实施授权：** 用户已明确“设计完让Astra Max决策，然后直接进入开发”，不再等待人工逐页视觉确认。当前权威为[简单最终设计](../specs/2026-11-02-membership-simple-final-design.md)和[新实施计划](../plans/2026-11-02-membership-simple-implementation.md)。Astra首轮已裁定39/99/199元、30天普通报告参考30/90/240盘、每周最多约10/30/80盘（M=3W），Max仍不可售；不做24h/结转/释放。计划第二轮Approved（0未解决问题），已经进入并行SDD实施。产品代码正在开发；本地专用PG已准备，legacy聚焦基线38通过/1个未设置旧PG测试跳过。后续按SDD并行、独立Astra代码/视觉修复闭环及原四步发布推进，不能回到下面历史的“等用户视觉确认”暂停点。

> **2026-11-02最新用户反馈修订：** [当前权威增量](../specs/2026-11-02-membership-presentation-and-fallback-amendment.md)优先于下方历史商品/来源约定。用户要求隐藏标准单位、只显示本期/本周百分比；会员优先、不足时自动使用已有API积分（整次单来源，不自动人民币充值）；普通报告用日均1/4/13盘，不设每日上限。39/99/279元为本轮候选，优惠约57%/73%/76%，Max仍禁用。双端隔离Fixture、真实浏览器和一次[Astra Max增量视觉/代码复核](../reviews/2026-11-02-membership-percent-daily-fixture-astra.md)已通过；[预览](../../design/membership-recharge-2026-10-31/README.md)。尚待用户确认视觉/候选价格，后端自动回退未实施，不继续旧的“禁止自动使用钱包”约定。


> **2026-11-02视觉阶段完成：** 已按「API充值／会员」重做双端隔离Fixture，充值显示普通约0.01／高级约0.04积分每手，会员显示满额相对API约省68%／73%／75%及使用条件，移除24h与双资源。Kiosk仍在原合集，Galaxy含375px适配。真实浏览器预览、同尺寸对照及独立[Astra Max代码与视觉审核](../reviews/2026-11-02-membership-points-fixture-astra.md)已通过；[预览与验证](../../design/membership-recharge-2026-10-31/README.md)。待用户明确视觉确认，未进入后端、提交、集成或发布。阿里官方页截图价3817／旁列4579已单独[补入成本敏感性](../../operations/aliyun-gpu-cost-sensitivity-2026-11-02.md)，未将限1件优惠当作可复制扩容或续费价格。


> **最新状态：** 下述v3修订已经完成用户要求的两轮Astra Max审核，[最终Approved](../reviews/2026-11-01-membership-request-v3-astra-r2.md)，未解决问题0，两轮结束。用户成本质疑后补测305手完整306位置，用时397.484秒；按3500月租满载摊销，参考30盘纯租金15.84元。当前保留29/99/299候选，Pro/Max暂4/13倍，仍待商品与新视觉确认；不是已批准开售。多服务与云GPU价格两份独立调研在docs/operations，3500并非已获阿里/腾讯实际配置报价。旧v2商品后端继续暂停，不追加旧计划评审或重建工作区。

> **后续修订入口，优先于本文旧商品部分：** 用户在v2预览后改为积分充值／统一请求预算，取消24h和领地支招独立桶；最新澄清为300手、500visits/手，Plus周7盘及30天30盘，高级4倍。候选[新设计](../specs/2026-11-01-membership-points-and-request-budget-v3.md)已完成用户要求的两轮Astra Max审核并获Approved，价格与v3视觉尚待用户确认；暂停旧v2后端任务。已完成新PROD V100 75次有界实测及305手完整报告306位置实测，证据见新设计。原子账务、旁路防护、TEST隔离和发布顺序等不冲突边界仍有效。

## 当前工作区已准备

- 用户最新决定：由 Codex 继续本功能，不再交给 Gemini。旧资料中的 Gemini 执行者和“尚未创建 worktree”描述已被本记录取代；已审核的商品、权限和账务决策不变。
- 工作目录：`/Users/fan/Repositories/katrain-membership-recharge`，与原 `katrain-kiosk-debug` 平行。
- 分支：`feature/membership-recharge`。
- 创建基线：2026-11-01 实际 fetch 的 `origin/develop`，`f43b673d71ba9bc7a65344dd5c587ff9f4c1436b`。它完整包含原分支 `07d1ddce9e8808fa6c7b840e1a0cd928048ac4bd`，并多出 14 个提交，无需另外合并原分支。
- 已从原工作区逐字节复制并校验 SHA-256：主计划、两轮评审、旧设计讨论稿和两个 Fixture 文件。原工作区保持不变，没有复制依赖、虚拟环境、截图全集、环境变量或密钥。
- 最新 develop 已包含发布的 Elasticsearch 改动，正常继承即可；不要进入或修改另一个 `/Users/fan/Repositories/katrain-elasticsearch` 工作区，也不从其未发布分支抽取改动。
- 本准备步骤未实现会员功能、未部署、未启用真实收费。此分支尚未推送远端；发布时遵循下述四步。
- 准备验证：原工作区 HEAD 和已跟踪文件保持不变；本 worktree 产品代码与上述 `origin/develop` 一致，6 个源资料 SHA-256 一致，预览引用的本地字体存在。复用原工作区 Python 环境运行 `CI=true python -m pytest -p no:cacheprovider tests/web_ui/test_analysis_cost.py -q`，8 passed（0.03s）。这是现有计价纯函数的聚焦基线，不代表新会员功能已经实现或验收；未安装新依赖、未构建前端、未访问数据库/GPU/生产服务。

## 必读资料与计划状态

1. 本工作区 `AGENTS.md` 和适用于本任务的用户开发偏好。
2. `docs/superpowers/plans/2026-11-01-membership-usage-and-payments.md`：权威实施计划，4 个 Chunk、9 个 Task。Task 1.1 的 worktree 创建和资料复制已完成，仍须执行 Task 1.2 的现状核查；不要为重复创建目录覆盖现有工作。
3. `docs/superpowers/reviews/2026-11-01-membership-plan-astra-r1.md`、`2026-11-01-membership-plan-astra-r2.md`：两位独立 Astra Max 已完成最多两轮计划评审。第一轮 0 Critical / 6 Important 已逐项修订，第二轮 Approved，未解决 Critical / Important 均为 0；不重启第三轮计划评审。
4. `docs/superpowers/specs/2026-10-31-membership-recharge-design-draft.md`、`docs/design/membership-recharge-2026-10-31/`：历史背景和可运行的隔离 HTML Fixture。冲突处以新计划为准，旧页面不是本次实时额度设计已经获得视觉确认的证据。README 中旧截图属于原工作区的历史材料，没有整套复制。
5. `superpowers/tracks/galaxy-payment/requirements.md`：历史约束；过时事实须在新基线核实。源码比评审时更新了 14 个提交，核实相关账务路径即可，不重做无关搜索项目调查。

## 执行方式与验收顺序

- 使用 `superpowers:subagent-driven-development`，先稳定最小共享基础，再按用户旅程闭环。仅并行不冲突且契约已稳定的任务，不让多个 agent 同时改 schema、账务事务或同一 UI 文件。
- 使用 `ui-ux-pro-max` 读取现有设计系统，先更新 Galaxy 1440×900 / Kiosk 1024×600 的 Fixture 和可操作预览，核对字体字号、触控区、额度和倒计时。前端验证成本与实际风险相称，不做无关的全量视觉重拍。
- 用户流程要求：`Artifact/设计 → 临时 Fixture 前端 → 同尺寸视觉对比与用户确认 → 契约确认 → 后端实现 → 集成与验收 → 删除 Fixture`。新页面视觉尚未确认；展示参考、实现、并排和叠加/差异图并取得明确确认，再进入对应切片后端。不要把已确认计划或旧三张套餐卡当作新额度页面已确认。
- 不安装新平台或创建第二套钱包。保留现有单池 credits、报告队列和 PostgreSQL；复用必要的现有开发环境，避免复制 node_modules、.venv、模型和大批截图。测试仅覆盖本次行为和主要回归。
- 完成开发后，由独立 Astra Max 做代码审核及相关双端视觉审核，修复后复核至通过。计划已过审不等于代码已过审；不能调用指定审核者时如实说明，不能伪造审核通过。

## 已确认产品与价格口径

- Galaxy / Kiosk 同账号共用云端额度和余额；盒端本地 SQLite 不能授权发钱或消费。
- 两种独立资源计数：报告份数、领地/支招标准分析。各自显示 24 小时和本周的剩余量、比例和重置倒计时。24 小时首次使用起计，本周为北京时间周一零点；换设备和续费不重置。以服务器时间和权威状态为准，不每秒请求 API。
- Plus / Pro / Max：29 / 99 / 299 元每 30 天；标准报告每 24 小时 1 / 5 / 20 份、每周 7 / 35 / 140 份；标准互动每 24 小时 10 / 50 / 200 次、每周 70 / 350 / 1400 次。
- Free 每自然周 1 份普通报告，不单独赠送领地/支招，也不赠通用 credits。已拥有报告内的领地与推荐落点查看免费；会员不额外叠加一份 Free。
- 按次包：29 元发 1000 credits；单个标准互动局面 500 visits，扣 10 credits，即 0.29 元/次；2000 visits 为 4 标准单位。一次分析同时包含领地和支招，同 operation 的重试、切换显示和重复查看不重复收费。
- **整盘批量复盘与独立互动不是同一单价**：标准报告每手 500 visits，现有 `report_cost` 约 0.5 credit/手，v2 报告最低 10 credits；即 `0.029 × max(10, ceil(N / 2))` 元/盘。250 手示例扣 125 credits，即 3.625 元/盘、0.0145 元/手。不要误实现为每手 0.29 元。
- 用满 30 天报告权益且每盘 250 手时，Plus / Pro / Max 整笔会费分摊约为 0.00387 / 0.00264 / 0.00199 元/手；这是用满参考值，不是承诺或服务端固定按手费率，其他权益未分摊。
- 新订单停售旧低价 SKU，保护历史余额、账本和合法已付订单。固定商品版本、金额、profile 和扣费来源由服务端决定；会员不足不能默认自动扣钱包。
- 当前 API 次数包仅面向站内用户，不开放第三方 API Key 或公网原始 KataGo 代理。

## 重点边界与支付阶段

- 依计划覆盖旧 `/analyze`、`quick-analyze`、hint、state/WS 等入口和结果出口，防止免费 GPU 旁路；继续保留 ranked 禁辅助、直播和第三方服务原有权限。
- 报告需满足完整 0..N 位置、真实 requested visits 校验及完成结算后才交付结果；失败退款后不得继续读取中间前缀，retry 必须重新授权。保留删除、requeue、reaper 与旧任务的兼容边界。
- Kiosk 用有界完整 SGF 和不可变捕获的云端账号身份请求，不能把本地 session UUID 当云端 session，也不能切账号后用共享 token 把原请求算到另一个人。
- 用真实隔离 PostgreSQL 验证行锁、双窗口、预留/退还、幂等履约和并发；SQLite 不能证明这些边界。
- 阶段 A：真实业务后端、两端集成、TEST-only 模拟支付及必要验收。模拟环境必须显式指定且只读核验 TEST 数据库身份，禁止配置回落到正式库，production + mock 拒绝启动。
- 阶段 B：官方商户签约、资格、凭据以及真实支付/退款验收就绪后启用支付宝/微信。缺少外部前置不阻碍阶段 A，但不能宣称正式收款完成。Free 正式赠额同样核查计划中的真实身份/注册限流前置，不伪造验证事实。

## 发布与汇报

开发、独立审核和必要验收通过后，按用户授权流程：

1. fetch 最新 develop 并合入功能分支，解决冲突、验证、提交并推功能分支。
2. 合入并推送 develop。
3. 更新 `smartbox-software/vendor/katrain` 到已发布 develop 提交，保留父仓库无关改动，提交并推父仓库 main。
4. 先部署 TEST `home-ubuntu`，验证后部署新 PROD `ucloud-v100`（117.50.177.254）；核对实际版本、服务健康和代表性双端页面。不要访问已退役的旧 IP，不重建无关生产服务；RK3562 只按已授权范围验收。

阶段开始/完成及持续工作每 30 分钟，在新会话用文字汇报：当前步骤、已完成、阻塞、当前步骤预计剩余时间。汇报不暂停主线任务。最终给出代码和视觉审核结果、真实测试结果、已发布提交、实际部署版本，以及阶段 A / 阶段 B 分别的完成状态。

## 可复制的启动 prompt

请在当前 `katrain-membership-recharge` worktree 的 `feature/membership-recharge` 分支开始会员与充值模块开发。先读取 `AGENTS.md`、本交接文档以及本文链接的权威计划和两轮 Astra Max 评审。

工作区已从最新 develop 建好，计划已两轮过审；从 Task 1.2 核查实际基线开始，用 `superpowers:subagent-driven-development` 推进，不重建 worktree、不重复做计划评审。优先产出两端新的用量/购买 Fixture 和真实预览，遵守用户视觉确认后再进入对应后端的顺序。按本文落实额度、整盘复盘与独立互动的不同计价、TEST 模拟支付隔离、账务幂等和收费旁路保护。

开发后交独立 Astra Max 做代码和视觉审核，修改至通过；按原四步流程集成发布，先 TEST 后新 PROD。正式支付和 Free 上线前置未具备时准确报告阶段限制。每阶段和每 30 分钟汇报进度与当前步骤 ETA，持续推进，达到当前授权阶段的验收标准即交付。
