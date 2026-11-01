# Simple Membership, Usage and Recharge Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在Galaxy与Kiosk交付云端权威的会员、百分比用量、积分充值、自动来源选择和隔离TEST模拟收银，并按已授权流程集成发布，诚实区分软件完成与真实收款。

**Architecture:** 复用唯一整数credits钱包、PostgreSQL、QuotaBucket、ReportTask及现有cron。只增加必要的term与operation持久化；一次操作完整选会员或钱包，固定用户锁和单事务，后台计算不持数据库锁。共享API／hook稳定后两端独立布局可并行；不用Redis、新队列、另一钱包、额度结转或逐周释放机制。

**Tech Stack:** 现有FastAPI、SQLAlchemy/PostgreSQL、React19/MUI/Vite、httpx、KataGo、pytest/Vitest/Playwright；原手写迁移。

---

## 0. 权威、授权、实际基线

- 当前目录`/Users/fan/Repositories/katrain-membership-recharge`，分支`feature/membership-recharge`，实际HEAD `0d938a0b009f48b3a98803cd03446ce7f26375e8`。工作树中既有本任务设计／调研／交接修改必须保留；不新建worktree、不修改ES工作区。
- 业务以[简单设计](../specs/2026-11-02-membership-simple-final-design.md)为准。旧273行实施计划与原两轮评审保留高风险边界背景；本次为用户新要求的修订计划，独立Astra Max可决策本稿配额，**最多两轮计划审核**，不重启旧计划第三轮。代码审核另行迭代至通过。
- 用户明确授权Astra决策后直接开发，替代本次原人工视觉确认暂停点；仍做真实预览、同viewport对比和独立视觉审查。不得再用“等用户视觉确认”停住已授权主线。
- 当前没有MembershipTerm／BillingOperation、用户会员UI或支付客户端。现有钱包/额度helper多自行commit；paid与grant现为两个事务。报告/moves会返前缀，worker无generation，不能假设计划已经实现。
- 实际只读核对：`billing_proxy.py`和`web/report/analyzer.py`不存在，报告归cron。严格Kiosk的token=null可能是正常cookie认证；共享客户端必须用AuthContext.identityKey/status，不用!!token判断登录。
- 可复用Python：`../katrain-kiosk-debug/.venv/bin/python`；UI依赖复用相邻库已有node_modules，通过本工作树内symlink，不复制／重装依赖。测试进程显式设置临时`KATRAIN_DATABASE_URL`、测试SECRET_KEY，禁止隐式读用户配置指向数据库。
- 专用本地PG16测试容器已建立，127.0.0.1:55439，数据库`membership_validation_20261102`，凭据只在`/tmp/membership-validation-20261102-pg-21srdr53/test.env`（chmod600）。使用其TEST_DATABASE_URL，不把该文件、密码或真实env写Git／日志。所有破坏性fixture只允许loopback+此前缀+独立随机schema；不使用生产库测试。
- Context7已核对：[Session autobegin/commit](https://docs.sqlalchemy.org/en/20/orm/session_transaction.html)、[FOR UPDATE](https://docs.sqlalchemy.org/en/20/orm/queryguide/query.html)、[FastAPI测试覆盖依赖](https://fastapi.tiangolo.com/advanced/testing-dependencies/)、[React清理旧异步响应](https://react.dev/learn/synchronizing-with-effects)。服务原语flush-only，端点拥有一次commit，已有autobegin不嵌套begin。

## 1. 冻结契约（Astra可在两轮内裁定）

```python
CATALOG_VERSION = "membership_20261102_v1"
PLANS = {
    "plus": {"amount_fen": 3900, "term_units": 9030, "week_units": 3010},
    "pro":  {"amount_fen": 9900, "term_units": 27090, "week_units": 9030},
    "max":  {"amount_fen": 19900,"term_units": 72240, "week_units": 24080},
}
# 1 display point = 100 existing integer credits; 1 CNY grants 100 credits.
# normal report: N+1; advanced: 4*(N+1); position: 1/4.
# same canonical tf3 model for both depths, not arbitrary engine payloads.
```

- 固定tf3-b11c768模型SHA `93bdb63a3bfae4a70db0cb5265287495ecfc10b1ba1cc6814feeba1cdf055871`，普通500／高级2000visits；用实际模型响应严格验证，缺模型验证不能交付新收费结果。SGF≤256KiB、报告1..500有效主线手；短分析允许合法初始／摆子局面（0手），不套报告下限。棋盘≤19路、按实际合法面积校验ownership，19路才是361项；完整合法历史、setup/初始行棋方/rules/komi，不截断、不信客户端move_count。
- term独立30天、不重叠，续费／换档排在已有期限后，当前自然周使用历史保留。周北京时间周一00:00；UTC存储。`available=min(term.remaining,week.remaining)`，百分比各用各分母。GET不创建桶／赠额。
- Free仍为每自然周1份普通报告资格，非301个通用单位。付费期无额外Free；本周free_report/membership来源报告预留／运行／已完成占用Free资格；失败全退释放原授权周事实；删除保留receipt；仅短分析或wallet报告不占用Free。Free→会员带入新v3真实周请求量，新term从0开始。
- 历史Free迁移只导入能由真实task/SGF验证的单位和原资格事实，不按旧credits折算；若旧棋谱已删导致手数不可证，保留已用Free资格，不伪造单位或再赠Free。legacy在途未结算用户暂缓新授权至其完成，不让两个settler同管一笔钱。
- 钱包同一池User.credits，旧C只显示C/100积分，不改本金／赠额／账本。旧合法paid订单按旧快照履约，旧任务按旧价。停售旧p6/p30/p98仅针对新订单；旧未付单保留原快照有效性，不倒改已创建金额。
- 一次operation先查同用户合法已拥有结果，再作新授权；member足够完整预算时用member，否则整次wallet，不能混扣。接受的服务端quote须覆盖fallback积分上限；未知／离线／权限失败不作钱包回退，钱包不足402。不是自动人民币充值。
- 未付quote建议120秒，订单15分钟。quote用带域分隔的HMAC签名小payload（不是可当登录token的JWT），包含owner、环境、kind、fingerprint、profile、units、wallet_max_credits、catalog_version、expires_at、来源策略；执行重算绑定。不能只信客户端source/amount或把quote变成跨用户授权。
- 新报告、短分析、订单都保存独立幂等键：同user/kind/key只一次，同key不同fingerprint409。结果过期receipt仍在；同旧key不重跑，返回result_expired，明确新报价／新key才允许新分析。
- 单一`MEMBERSHIP_MODE=legacy|enabled|paused`，默认legacy，**替代原草稿的BILLING_MEMBERSHIP_ENABLED布尔值**。仅首次启用前legacy兼容旧行为；enabled/paused均要求BILLING_ENFORCED=true、schema/守卫就绪。首次启用后在既有SystemConfigDB记录`membership_activated_v1`，启动检查该标记或已有新版本账务事实时拒绝降回legacy。paused拒绝新创单、quote/消费/retry和旧GPU触发，继续读取／结算／退款／回收已有授权；不能暂停时免费走旧接口。所有已有新任务始终按持久化billing_version/operation走结果门和幂等，与当前模式无关。
- 云端`can_claim_free_report`可信判定必须参与实际授权及usage能力。当前无真实P3事实/注册限流保障时正式Free不合格，显示验证前置；登录成功/客户端phone_verified等布尔值均不是证明。隔离TEST应用可用受控依赖注入合格主体，但须已经通过实际TEST数据库守卫，生产没有测试身份入口。合法购买钱包不受Free前置影响。

### API与UI边界

- 扩展`/api/v1/billing`：`GET /catalog`、`GET /usage`、`POST /quotes`、`POST /orders`、`GET /orders`、`GET /orders/{id}`。旧balance/quota/prices兼容；新价使用同一目录，不能在UI硬编码权益。
- 新`POST /api/v1/analysis/positions`及`GET /positions/{operation_id}`，只接受固定profile／已签quote／完整SGF或拥有的游戏引用；返回授权operation和领地＋候选结果，不开放第三方API key/raw代理。
- 报告原创建／retry增加quote与idempotency字段；总闸开启缺quote则拒绝，不偷偷跑legacy免费路径。返回task+operation+权威来源／实际积分；结果只在完整成功并结算后提供。
- usage包括capabilities、catalog_version、server_now、revision、plan当前/下期、term/week各limit/used/reserved/remaining/percent/reset、wallet整数+显示积分、Free资格、payments_mode。内部整数可在API，产品任何页／弹窗不用“标准单位”。能力关闭/加载失败不返回假0。`Cache-Control:no-store`，账号+环境隔离，15秒可见同步＋操作后刷新，单调时钟本地倒计时。
- Kiosk普通local session不能云端直接加载。board先本地检查owner／ranked并导出有界完整SGF，云端重新合法性与中央ranked守卫；local session id只回显。新增请求捕获不可变user/token/generation，发送和refresh前检查绑定，不允许共享RemoteAPIClient换号误扣；云失败不落SQLite。
- 会员订单付款前显示“成功后生效／已有会员到期后顺延”，日期仅标“预计”。最终非重叠起止日期由user锁下履约计算并在已付回执显示；不为待付单预留排期或伪造并发下的确定日期。
- 官方支付未接通时disabled目录不可下单，TEST mock清楚标注且无真实支付码。Max默认不可售。客户端“已付款”／返回页不改变订单或钱包。

## Chunk 1：计划决策、基础与可见页面

### Task 1：独立决策／审核及工作检查点

**Files:** 本计划、简单设计、`docs/operations/membership-recharge.md`、已有docs设计与契约。

- [x] 1.1 交独立gpt-6-astra max、fresh context审核本计划并决策简单比例；明确仅两轮。本稿作者修改，再第二轮复核。未解决重要问题不得执行；若两轮仍不通过，按缺口收敛而非假通过／追加第三轮。
- [x] 1.2 记录最终目录／周上限、审核SHA／结论，更新交接和contracts，注明本次直接开发授权。以显式路径提交本任务既有设计／证据检查点，不`git add .`夹带其他任务。
- [x] 1.3 建当前UI node_modules symlink，复用Python；检查本地PG真实连接，只在专用库建立测试控制schema `billing_test_identity.environment` 与环境=TEST、database_name标记。它不在应用默认schema，避免将空应用库误判成旧库。普通应用不能创建／修改该标记。
- [x] 1.4 运行聚焦legacy基线（显式临时DB和测试密钥）：`tests/web_ui/test_analysis_cost.py tests/web_ui/test_billing.py tests/web_ui/test_quota.py`；只记录实际结果，不以SQLite证明锁。

### Task 2：纯目录／schema／运行时隔离（单一基础所有者）

**Files:** Create `katrain/web/core/billing_catalog.py`、`billing_environment.py`、`tests/web_ui/test_membership_catalog.py`、`test_membership_environment.py`、`membership_test_support.py`；Modify `core/{models_db,migrations,config,auth}.py`、`cron/models.py`、`tests/web_ui/test_migrations.py`。

- [x] 2.1 先写目录价格／单位／N+1／week=term/3及余额显示测试，运行应因缺模块失败；最小实现纯规则。
- [x] 2.2 在现有ORM新增`MembershipTerm`（user、plan、starts/ends、limit/used/reserved、order唯一、价版）、`BillingOperation`（user/kind/key唯一、fingerprint、来源、profile/SHA/units/wallet_ref、term_id/week_bucket_id、状态、generation/lease、task/游戏非cascade关联、有限result与expire）和必要user revision/migration标记。
- [x] 2.3 给QuotaBucket增加reserved、窗口起止与新kind，不改legacy快照语义；ReportTask增加nullablebilling_version/operation_id、generation、冻结模型SHA；RechargeOrder增加nullable价版/SKU快照/环境/provider_tx/expiry/fulfilled/refund事实。cron映射实际读写字段一致。新receipt不因删棋谱/任务cascade删除。
- [x] 2.4 手写迁移幂等补列、唯一索引／非负约束；users/report_tasks/新表及已有资产加入drift保护。旧钱包／ledger/order/task完整保留，不清库、不改ES迁移链。
- [x] 2.5 Settings加入显式部署环境production默认、PAYMENTS_MODE disabled默认及单一MEMBERSHIP_MODE三态；首次启用后复用SystemConfigDB持久标记、禁止legacy降级，不增加另一状态平台。mock要求显式KATRAIN_DATABASE_URL、禁止全局配置回落。`SQLAlchemyUserRepository.init_db` **任何DDL前**只读检查实际current_database和独立schema的TEST标记；production+mock／未知库／错库拒绝。单元测试断言DDL函数未被调用。
- [x] 2.6 用专用PG随机schema运行迁移两次、核对旧行及约束；SQLite只作纯规则／兼容。通过后提交`add membership catalog schema and test isolation`。给下游发布准确模块／函数／类型契约。

### Task 3：共享客户端契约与最终周展示（可与Task2独立部分并行）

**Files:** Create `ui/src/api/membershipApi.ts`、`ui/src/features/membership/{types.ts,presentation.ts,useMembership.ts}`及聚焦测试；Modify docs两端Fixture／contracts/README（仅最终每周显示和最终价）。

- [x] 3.1 先写纯展示测试：API积分两位、优惠56.8/63.5/72.5、每周10/30/80、各百分比、能力关闭/未知无假0；再写最小类型与API客户端。所有请求复用api.ts同源鉴权／cookie、ApiError，不凭!!token禁用正常严格盒端。
- [x] 3.2 hook按AuthContext.identityKey/status与环境清理旧快照、abort请求、忽略旧身份/旧revision；只在可见时15秒poll，消费/支付/回前台/跨零重取。用server_now+performance.now倒计时，归零只重取不发量。
- [x] 3.3 更新隔离设计到最终每周参考、最终价格，并真实查看1440×900／1024×600；按用户新授权交Astra最终复核，不再人为停等。设计数据仅docs／测试，无生产模拟导入。
- [x] 3.4 Run `npm test -- src/features/membership src/api/membershipApi.test.ts`，覆盖身份切换／严格cookie/null-token／poll清理／未知状态；低风险文字不另写一层审计脚本。提交共享契约检查点。

## Chunk 2：原子业务与会员购买旅程

### Task 4：term／周量／Free事实、quote及operation事务

**Files:** Create `core/membership.py`、`billing_operations.py`、`billing_quotes.py`；Modify `core/billing.py`；Create `tests/web_ui/test_membership_operations_pg.py`、`test_membership_periods.py`、`test_membership_quotes.py`。

- [x] 4.1 真实PG先写竞争最后单位／钱包的失败测试。新分析入队先取固定PG advisory transaction lock（统一双int键`19467,1102`），再按`user→order/operation→task→term/week bucket/credit`顺序；任何持user锁的路径不得反过来申请入队锁。结算/退款/支付只用user开头顺序，不需要入队锁。service仅flush，外层一次commit，GPU／provider HTTP在所有锁外。
- [x] 4.2 提供可复用明确API：`quote_operation(...)`、`reserve_operation_in_transaction(...)`、`commit_operation_in_transaction(...)`、`refund_operation_in_transaction(...)`、`usage_snapshot(...)`；kwargs显式user、now、fingerprint、profile、idempotency。保留legacy自commit函数，新增钱包无commit原语，不通过先peek再两个commit拼接。新增`reconcile_expired_positions(...)`：只读选候选，user→operation锁内复核kind/status/lease过期后递增generation、原来源恰好退款、释放名额；完成路径同锁互斥。报告不套短操作TTL，24h清result可复用该维护入口、receipt永存。
- [x] 4.3 实现term有效期、自然周、min实际剩余、来源自动选择与报价cap；账号并发每人1report+1position。全局入队锁覆盖跨用户检查与预留；报告计数包括相关新旧authorizing/pending/running任务，短分析计数包括reserved/running operation，各自取配置上限，使用同一个入队锁避免反向锁序。该限制是本服务入队保护，不冒称GPU独占。会员量只是一项请求预算，不创建第二钱包。
- [x] 4.4 quote HMAC域分隔，执行重新验证owner/env/profile/SGF/price/expiry，使用冻结fallback上限；并发不足原子改用钱包不超过已接受cap。无合法quote、401/403/503不能钱包兜底。
- [x] 4.5 在授权事务中调用云端`can_claim_free_report`，先验证可信P3事实再预留Free资格与周实际单位。缺失/未知P3或客户端自报核验均拒领且不触发GPU；TEST合格主体仅由已验证隔离app的受控依赖注入。usage返回free_eligible/不可领原因，不把不合格伪装为已用0。oldFree已用不再赠，旧任务待终态后启新路径；新Free→会员带周量、新termused0。退款回原term/原week/原wallet，不挪到新期。GET纯读，不调用会建桶commit的旧quota.peek。
- [x] 4.6 测试term/周任一不足不半扣、跨界退款、同key重放与不同指纹冲突、支付／退款／消费竞争、旧余额未缩放、到期不重复Free、升级不清周、月底跨5/6周不多发term。另加三个聚焦行为：不同账号争最后队列位恰好一笔预留且完结后可再入队；短预留提交后模拟进程消失，重建并reconcile只退一次、旧generation晚回拒绝；未核验/伪造核验拒Free，受控TEST主体可领取且生产无测试身份路由。
- [x] 4.7 在专用PG执行上述测试及legacybilling/settlement聚焦回归；核对实际持久状态，不用skip当通过。提交`reserve membership and wallet usage atomically`。

### Task 5：目录／usage／订单与TEST模拟履约

**Files:** Create `core/payments.py`、`payment_mock.py`、`api/v1/endpoints/payment_test.py`；Modify `api/v1/endpoints/billing.py`、`api/v1/api.py`、必要`server.py`注册；Create `test_membership_usage_api.py`、`test_membership_orders_pg.py`、`test_mock_payment_boundary.py`。

- [x] 5.1 用同一service实现catalog/usage/quote，字段和no-store按§1；reconcile如需写账先作明确事务再读一致快照。新UI不把legacyfree桶与新资格相加。把短操作幂等reconcile挂到现有server启动/维护循环，并在本人usage、operation状态查询和新授权前按需执行；新授权时先取全局入队锁再在user锁内回收本人过期操作，或先结束独立回收事务，不能持user锁再申请全局锁。不另建调度服务。usage能力从同一可信Free判定产生。
- [x] 5.2 新订单只传SKU/provider/key，金额、grant和权益快照服务端固定；同user key唯一、15分钟有效；GET仅本人，浏览器返回不履约。Max销售能力默认false，disabled支付返回不可购买。
- [x] 5.3 TEST路由仅显式test/development+mock注册且要求可信测试管理员与HMAC事件校验；不可匿名伪通知。startup/创单均调用已验证实际DB guard，未知库写前拒绝。测试bootstrap身份不注册为PROD后门。
- [x] 5.4 mock成功确认／查单恢复／重复通知同user→order锁，paid和credits或term同事务，一次履约；paid不被迟到failed降级。会员订单在履约时创建非重叠term，付款前只显示顺延规则／预计日期，最终起止在已付回执显示；测两端两个合法待付单依次成功，回执与实际区间一致且不重叠。
- [x] 5.5 仅全额退款：钱包当前available足够扣回grant；会员无used/reserved且无后续term依赖才作废term，否则需人工。退款ref唯一，paid/refund与资产同事务；不做部分退款／多批余额算法。
- [x] 5.6 旧settle_order不能把新快照订单当legacy两事务履约；对新版本明确拒绝或转新service。旧合法paid/未付按原快照兼容，停售仅新建旧SKU。
- [x] 5.7 PG验证通知重放／amount或环境篡改／越权／漏通知查单／付款退款消费竞争；production+mock和未知实际DB在DDL前拒绝。提交`add isolated membership checkout and usage API`。

### Task 6A／6B：Galaxy与Kiosk真实产品页面（共享契约稳定后并行）

**6A owns:** `ui/src/galaxy/pages/membership/*`、`GalaxyApp.tsx`、`galaxy/components/layout/{GalaxySidebar,GalaxyBottomNav,galaxyNavigation}.tsx`及对应测试。

**6B owns:** `ui/src/kiosk/pages/membership/*`及CSS、`kiosk/KioskApp.tsx`、`kiosk/components/settings/AccountSection.tsx`、必要KioskTopbar入口及测试。

- [x] 6.1 两端实现用量／API充值／会员，复用共享hook与真实catalog，不硬编码业务样例；百分比、周最多参考、满额条件、实际积分、Free资格、加载／离线／错误、待付款／失败／过期／已付均诚实。
- [x] 6.2 Checkout只轮询本人订单，支付变化后重取usage；mock无真实付款QR/品牌接通标记，生产无TEST操作按钮。支付不可用／Max不可售来自服务端能力，不靠CSS假禁用。
- [x] 6.3 Galaxy375／1440适配；Kiosk1024×600、18/22/28字号、44px触控、既有软键/全局字体。Kiosk弹层留在缩放画布内，不用默认MUI portal逃离tokens；不增加第八Dock项。
- [x] 6.4 新页面组件测试聚焦未知/耗尽/付费终态/strict-cookie认证；实际React Vite预览对齐确认Artifact，参考／实现／并排／叠加或diff保存。仅重拍受影响主视图，不全状态拍摄。
- [x] 6.5 两端所有者不得同时改共享hook／AuthContext／翻译全局文件；公共接线由共享所有者整合。独立规格检查后再质量检查，问题由各自实现者修复，提交各自页面。

## Chunk 3：报告与单局面完整收费旅程

### Task 7：报告授权／结果闸／完整深度及worker fencing

**Files:** Modify `api/v1/endpoints/{reports,user_games}.py`、`core/{report_settlement,report_reaper,user_game_repo}.py`、`cron/{models.py,jobs/report_analyze.py,clients/katago.py,jobs/requeue_reports.py}`；Create/extend `test_membership_reports.py`、`test_report_worker_fencing.py`、既有reports/client/reaper测试。

- [x] 7.1 先写v3报告创建与retry行为测试：serverSGF计算N+1/4倍，quote+operation+task一次commit；legacy版本留原价/grace语义。failed全退后retry必须新attempt完整重授权，同HTTP重放只一次。
- [x] 7.2 worker claim改原子row-lock/CAS并递增generation；stale/reset/retry改代并清lease。**每个位置写入与最终complete都比较task id+generation+operation绑定+running状态**，旧worker晚到无权覆盖新attempt或再标完成。不仅短任务做fencing。
- [x] 7.3 真实KataGoClient.analyze调用传严格requested_visits与冻结SHA，未配置验证不能跳过。验final/id/turn/按实际棋盘面积的有限ownership/candidates/modelSHA（19路为361），0..N完整且每位置深度达到才可complete；缺中间/初始/末位置均失败。test用mock HTTP穿过真实client，2000请求返回500拒绝。
- [x] 7.4 终态settle与operation单事务，completed但未结算可由GET按固定锁序reconcile；running/failed/refunded只提供进度，/moves和user_game分析旁路不返回前缀。只在committed后创建可读UserGameAnalysis。
- [x] 7.5 用户锁内拒绝活跃／未结算任务的棋谱删除；终态删除保留receipt不返已用量。旧reaper/通用120s退款排除membership版本reason/ref，旧requeue写前跳过新任务，不删已付结果复活免费GPU。
- [x] 7.6 测失败前缀→退款→不可读→retry重新授权成功→重复读取免费；并发旧worker晚回、stale reset、completed结算窗口、删除/requeue边界。运行既有report_charging/settlement/retry/cron contract聚焦回归。
- [x] 7.7 提交`authorize and fence complete paid reports`。报告任务不得import web账务模块，cron镜像边界保持；web负责新账务结算。

### Task 8：一次短分析、旧触发／结果出口与Kiosk身份桥

**Files:** Create `core/paid_analysis.py`、`api/v1/endpoints/paid_analysis.py`；Modify `endpoints/{analysis,hint,billing}.py`、`core/{hint_gate,pvp_territory,remote_client,repository}.py`、`server.py`、`interface.py`、必要session状态；Create `test_paid_analysis.py`、`test_paid_analysis_guards.py`、`test_membership_remote.py`。

- [x] 8.1 在改动前列实际路由/动作/输出矩阵：v1analysis/analyze、quick-analyze、hint、PVPterritory；legacy/api/analysis current/extra/continuous/game/scan/report、generic action、/api/state与WS。原认证/ranked/第三方/直播边界逐项保持。
- [x] 8.2 enabled时旧raw payload与任意visits入口拒绝或映射同一固定profileoperation；未接好不能免费直通。paused同样保留这些入口/结果保护，只拒绝新的GPU授权，已授权结果仍可读。仅首次启用前legacy兼容；已切换库不能降回旧免费行为。已授权同一结果领地+hint共用，重复查看不再请求GPU，不破坏原AI对弈/公共职业报告读取。
- [x] 8.3 单位置server合法历史构造fingerprint＋scope（合法初始／setup可0手），授权commit后锁外有限HTTP，严格验证后同generation单事务commit并交付；失败回原来源。每账号最多1短任务，有上限timeout／lease，崩溃由Task4.2/5.1的reconcile回收；迟到结果不得结算或读出。有限64KiB result，24h清payload而保留receipt；无无界搜索树缓存。
- [x] 8.4 Interface.get_state／last_state／广播只在对应用户、完整局面、profile、已committedoperation授权时输出私有analysis/PV/ownership/history评估/派生失分，不拿AI对弈内部分析或未授权缓存免费发给用户；保留棋子/时钟/真实手顺等必要对局信息。退款前缀不得通过保存session分析绕过。
- [x] 8.5 board本地owner/ranked校验后导出完整SGF快照，不把local session当云端对象；中央guard阻止pending ranked账号辅助。新增远端方法在发送及token refresh前核对捕获user/token/generation，换人旧请求拒绝、结果丢弃；云4xx原样、断网503，绝不落本地SQLite扣费。
- [x] 8.6 测真实挂载三路旧API无权益→拒绝且engine0调用、state/WS无泄露、一次操作两显示只扣/算1、错误/超时/late generation拒交付、同key异指纹、云端没有local session仍可合法快照授权、共享盒切账号零错扣。
- [x] 8.7 提交`meter private analysis and close legacy bypasses`。不得扩大成对外API key或多进程KataGo改造。

### Task 9：报告／研究交互接线与真实双端验收

**Files:** Modify `ui/src/features/report/useReportTasks.ts`、`src/api/reportApi.ts`、两端ReportsPage、`src/hooks/useResearchSession.ts`、`src/api.ts`及必要两端ResearchPage；Create `ui/tests/membership-recharge.spec.ts`、聚焦quote/hook测试。

- [x] 9.1 一位整合者拥有共享消费入口，报告创建/重试先取服务端quote，在已有开始确认显示会员优先及最大API积分回退价格；确认后带quote/key执行，拒绝时重取，不把旧报价金额从客户端写入账本。
- [x] 9.2 研究领地/支招通过一次meteredoperation结果，而不是两个按钮各算一次；切换和重新查看不扣，profile变更须新quote。旧continuous/raw不可用时给诚实状态，不后台偷偷免费算。
- [x] 9.3 身份生命周期用identityKey/status，严格Kiosk cookie/null-token可用；切账号旧请求和result丢弃。余额/会员信息从消费响应或usage重取，不在前端乐观加钱/发额度。
- [x] 9.4 TEST专用PG+可控mock engine跑真实业务API：买Pro→两端同账号相同usage→一次普通分析显示领地/hint只扣1→报告N+1完整交付→失败原来源退→会员不足钱包全额兜底→Free资格不双领。支付是TEST mock，不用生产余额/GPU压测。
- [x] 9.5 保留测试route mocks在测试文件；生产无mock余额/fixture/控制按钮。`npm run build`和`npm run build:smartbox-kiosk-2d`各一次；`playwright.visual.config.ts`独立5189端口启动当前Vite，代表性双端真实页面+375检查。新失败或变更才重复必要检查。
- [x] 9.6 同viewport查看Artifact/产品截图/并排/叠加或diff，记录构图/间距/字体材质/图标/状态差异，修至Astra审核通过；不以DOM布局测试代替目视。

## Chunk 4：独立终审、集成与阶段发布

### Task 10：独立Astra代码／视觉审查与修改闭环

**Files:** Review整个功能diff、相关tests及实际图；Create `docs/superpowers/reviews/2026-11-02-membership-simple-code-astra-*.md`；Updateoperations/plan状态。

- [x] 10.1 每个实现包按SDD先独立规格检查，再质量检查；相称检查可合并到同一独立审核者顺序完成，不为小样式增加两套测试平台。实现者自审不能代替独立审。
- [x] 10.2 fresh独立gpt-6-astra max全面代码与代表性视觉审查，重点事务、Free、quote自动回退边界、workerfencing、入口/出口旁路、云身份、TEST实际DB与旧资产。没有代码SHA/真实测试证据不能宣称已通过。
- [x] 10.3 将反馈交回对应实现者按SDD修复并运行受影响检查，同审核者复核至无未解决Critical/Important；代码审核不受“两轮计划上限”限制，但不为低风险细节反复全量回归。

### Task 11：前置核实、四步集成发布与诚实收尾

**Files:** `docs/operations/membership-recharge.md`、`core/health_report.py`、必要部署配置；父仓库submodulepointer。

- [ ] 11.1 读取server-deploy技能，核实真实P3身份/注册限流与官方支付能力，仅输出布尔摘要、不泄露env/密钥。缺官方商户/验签/查单/小额支付退款时支付保持disabled，PROD不注册mock；缺P3不开放正式Free领取。TEST用受控测试依赖，非生产后门。
- [ ] 11.2 多棋局真实端到端容量未验证前Max仍不可售；既有306位置预热引擎样本不当作生产SLA。可先完成软件TEST，不新增生产负载实验去装作容量通过。
- [ ] 11.3 fetch最新develop→合并入功能分支→解决冲突并核验组合→显式提交push功能分支。再合并推develop，记录SHA；不把仅部署feature视作已集成。
- [ ] 11.4 更新`smartbox-software/vendor/katrain`到公开developSHA，保留父仓库无关改动，提交并推main；不进入ES worktree。
- [ ] 11.5 先部署TEST home-ubuntu，验证版本/健康、真实账务＋隔离mock与代表性两端页面，再部署新PROD ucloud-v100 117.50.177.254。发布仅重建本次所需服务，不触旧IP/无关MinIO等。PROD缺收费前置时部署软件但禁销售/新授权，显示实际不可用状态，不导入TEST数据或凭据。
- [ ] 11.6 上线后安全暂停只能用MEMBERSHIP_MODE=paused，不用legacy关计费恢复免费。保留账本、已预留任务结算/退款、结果门和兼容读；不清资产、不回滚到会免费复活新任务的旧worker。测新任务在途→paused旧API不能新增GPU、原任务只结一次、refunded仍不可读且retry拒新授权；首次启用前legacy只作必要兼容验证。
- [ ] 11.7 报告阶段A软件/TEST、阶段B真实支付分别状态、已发布commit/实际部署版本、测试和审核结果、必要前置未完成项。阶段开始/完成及每30分钟报告进展/阻塞/当前步骤ETA，汇报不暂停工作。测试结束停止本任务临时PG容器，保留现有服务。

## 并行与依赖（不能跳过稳定基础）

1. 当前只读审计与本地专用PG准备可并行；不提前写产品代码越过计划审核。
2. 审核后Task2基础单一所有者；Task3共享客户端/docs可独立并行，双方不改同一文件。
3. Task4依赖Task2稳定；Task5依赖Task4，6A/6B可在Task3契约稳定后并行布局，先使用测试拦截而非生产fixture，随Task5接真实会员购买旅程。
4. Task7与Task8在Task4稳定后可按不同文件包并行；共同需要api.py/server.py/repository.py时由单一整合者串行合入，不让agent互相覆盖。
5. Task9只在购买/用量切片已真实闭环后整合消费入口；Task10审核后再Task11发布。任何无法满足的外部前置如实隔离，不能以“用户已睡觉”放宽资金/生产边界。

**审核记录：** [第1轮](../reviews/2026-11-02-membership-simple-plan-astra-r1.md)已裁定产品采用M=3W与39/99/199，实施计划0Critical/4Important/2Minor。本文已补I1三态及禁止降级、I2短操作回收执行者、I3可信Free授权、I4全局入队锁，并修实际棋盘面积/初始局面和预计生效日期。下一次为第2轮最终复核，不追加第三轮；尚未实现产品代码。

**第2轮最终结果（2026-11-02）：** [Astra Max R2](../reviews/2026-11-02-membership-simple-plan-astra-r2.md) Approved，0 Critical / 0 Important / 0 Minor。审核计划SHA256 `1c01181b761cc6ccbd963a372dc9f46c340adabe677419cad42a220a20d6a5ae`、设计SHA256 `d41b5e0a5cfba93a01af5bd869094ffe48e9657437702d8db903db9e34db4b69`。直接进入SDD，计划审核结束；代码/真实PG/视觉/发布另行验收。

**实施进度（2026-11-02 02:35）：** 基础、共享客户端、原子账务及Task5/8已独立规格→质量通过；真实双端会员页面预览通过。实际发现的Free权限回退/ORM缓存/autoflush、冻结权益、SGF分析出口已修复并复核。报告Task7最后ownedretry与ranked出口修复30PG绿，待Astra复核；Task9消费接线与真实组合API旅程收尾。所有提交仍在功能分支，尚未push/merge/deploy。

**最终开发审查（2026-11-02）：** 独立Astra Max对`952580756fae2c64d2ce05695c98c3e3313c5ac8`给出Task9 Spec → Integrated Quality Approved，0未解决Critical/Important，见[终审](../reviews/2026-11-02-membership-final-astra-r1.md)。额外摆子提示图单次fixture定位超时未取得，已记录非阻塞限制；代表性双端/375及quote视觉均通过。进入四步集成发布，发布尚未完成。
