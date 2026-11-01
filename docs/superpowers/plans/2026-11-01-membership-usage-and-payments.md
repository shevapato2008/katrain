# Membership, Live Usage and Prepaid Analysis Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在Galaxy和Kiosk实现共用云端账务的Free/Plus/Pro/Max、24小时/当周实时额度和倒计时、领地/支招次数包，以及审批前可验收的隔离模拟支付。

**Architecture:** 复用PostgreSQL、现有整数credits账本、额度桶和报告任务。会员额度是计数器，充值仍只有一池credits；一次标准局面分析返回领地和候选着法，使用同一份授权结果。前端先以隔离Fixture确认新设计，再逐条接云端事务；真实支付适配器留待官方签约和凭据具备后验收，不以模拟到账冒充正式收款。

**Tech Stack:** 现有FastAPI/SQLAlchemy/PostgreSQL、React/MUI/Vite、httpx、KataGo、pytest/Vitest/Playwright；不增加Redis、Kafka、另一套钱包或支付中台。

---

## 0. 权威范围、输入与交接状态

- 用户2026-11-01要求：实时显示24小时和当周剩余量及各自重置时间；增加100次领地/支招等按次充值并显示单次价格，明显贵于会员；Free每周1次复盘，不单送独立领地/支招；用writing-plans出计划，经独立Astra Max最多两轮评审和逐轮修改，再交Gemini执行。本轮**仅计划/评审/交接，不开发或部署产品代码**。
- 本计划取代`docs/superpowers/specs/2026-10-31-membership-recharge-design-draft.md`中一次性试用、旧充值包、周开通锚点等冲突内容。旧`docs/design/membership-recharge-2026-10-31/index.html`是已存在的内存Fixture，尚不包含本轮额度栏和Free/次数包，不能标成新设计已获确认。
- 2026-11-01代码基线所在工作区：`/Users/fan/Repositories/katrain-kiosk-debug`，`fix/kiosk-ui-debug`，已同步的远端develop基线`07d1ddce9`。执行前重新fetch，不把记录当成永远最新。
- Elasticsearch另由Gemini在`/Users/fan/Repositories/katrain-elasticsearch`、`feature/kifu-elasticsearch-gemini-20261031`处理。本功能不得进入或修改该worktree，也不要合入其未完成搜索功能。
- 本期把“API次数包”解释为站内Galaxy/Kiosk调用自有云端分析的付费权益；**不默认开放第三方API Key、公共KataGo代理或开发者计费平台**。若用户明确选择对外API，应在执行前单列增量范围，不能默默开放公网原始`/analyze`。
- 旧`superpowers/tracks/galaxy-payment/{requirements,plan}.md`是重要历史输入，但“仓库字面SECRET_KEY”“无报告计费”等2026-09事实已经过时，必须以当前代码核实。仍保留的边界：单池credits、云端权威、直播自身分析不收费、正式Free赠额前需要原P3身份核验/注册限流前置。不为本计划另建短信/认证平台。
- **阶段A交付**：更新设计预览、真实业务后端+TEST-only模拟支付、双端云端接线及必要验证。**阶段B交付**：具备商户签约/资质/凭据和Free反滥用前置后真实渠道联调与正式启用；缺失时报告明确待办，不宣布正式收费完成。
- 冻结功能闸`BILLING_V2_ENABLED=False`默认值；为true时要求原`BILLING_ENFORCED=True`且本期schema/运行时guard已就绪，否则启动拒绝。v2开关统一控制新报告授权、旧互动入口适配、usage和新UI能力，不能一边显示额度一边免费直通旧引擎。为false时legacy行为保持，新catalog能力显示不可购买/不渲染新用量，不伪造受限状态。付款模式另由PAYMENTS_MODE控制，不据“有前端入口”自动打开收费。

## 1. 商品和消费规则（本期执行决策）

### 1.1 商品目录v2

| 档位 | 30天建议价 | 报告份数：24h / 当周 | 标准互动分析：24h / 当周 | 说明 |
| --- | --- | --- | --- | --- |
| Free | 0 | 1 / 1 | 0 / 0 | 24h上限不是每天赠送，仍只可每自然周成功生成1份普通报告 |
| Plus | 29元 | 1 / 7 | 10 / 70 | 每日1份普通报告；深度须另付费 |
| Pro | 99元 | 5 / 35 | 50 / 350 | 可选1份深度+1份普通；互动额度另计 |
| Max | 299元 | 20 / 140 | 200 / 1400 | 可选5份深度；实际容量校准后才能正式开放销售 |
| analysis_100_v1 | 29元/包 | 不发报告份额 | 购买100次标准互动分析的等值credits | 无会员也能购买，不增加会员窗口上限 |

互动额度是为使“按次比会员贵”有同商品基准而新增的建议权益。展示“满额使用参考”：Plus/Pro/Max的30天300/1500/6000次对应约0.0967/0.066/0.0498元/次（即使把整笔会费都分摊给互动调用）；次卡0.29元/标准次，约为其3/4.4/5.8倍，报告权益尚未计入。**这不是未用满时的实际单次成本，也不是利润率**；偶尔使用者选次卡可能总支出更低，不隐藏这一事实。

- 初步复用`BILLING_PRICES`既有标准动作10credits：29元包发1000credits，标准分析10credits/次，2000visits增强档40credits/次。不要把增强档也宣传成“100次”，必须说明其消耗4次标准额度、约1.16元/次。
- credits仍是唯一可购买余额；“还可约100次”按`floor(available_credits/10)`动态估算，不新增另一种可转让次数币。该余额也能支付明确报价的其他服务，不能再承诺始终只能兑换100次互动。
- 冻结价格版本`membership_v2`、`interactive_500_v1`、`analysis_100_v1`与金额（分）。服务端决定价格、grant、模型/visit上限，客户端只传SKU/选择的扣费来源。
- 停售旧讨论稿“10元1250点”和当前旧`p6/p30/p98`产品供新订单选择，避免便宜充值SKU套利。**不删除或贬值历史余额/账本/已付订单**；旧未付订单按原快照与有效期查单/关单，合法已付按快照履约。价格比较只针对v2新购权益，不能拿存量余额宣称统一新单价。

### 1.2 一次是什么，Free不赠什么

- 标准互动：固定受控模型profile，单个≤19×19合法局面、500visits，返回`rootInfo`、候选着法/PV和ownership。禁止客户端任意模型、visits、多个`analyzeTurns`或无限ponder。增强2000visits暂按4个标准单位；不得由公用raw `/analyze`绕开。
- 同局面“领地/支招”只是同一授权结果的两种展示，不按按钮双扣。同一用户的同一已成功operation重试、重复打开和显示切换不再扣；不是按每次HTTP请求收费。
- 缓存键至少含用户授权scope、完整合法局面/轮到谁/劫历史、rules、komi、board size、模型SHA、profile版本和实际分析深度。不能只按手数或棋盘照片相同复用；不同用户不能获得私有报告。
- Free的1份普通报告包含其已生成位置的领地/候选着法，报告内部查看免费；**不**把报告份数换成独立互动credits，不注册赠通用credits，不用公共/原始引擎缓存给Free开放独立支招。独立互动入口先检查会员或已购余额授权，再考虑缓存复用。
- 普通报告为500visits/手、合法主线最多500手的一份完整报告；深度2000档扣4份。超限在分析前报价/拒绝，不截断。主线为空/无法忠实还原的SGF不给有效报告。分析的初始局面和手数口径需由服务端统一，不信客户端手数。
- 充值支付报告保留按手数变化的计价，但v2最低收费不得低于相同深度的一次独立互动：`max(10, report_cost(moves,500))` / `max(40, report_cost(moves,2000))`。这防止用一个局面伪装报告获得更便宜独立分析；长棋批量报告较低的每位置价格是明确的低优先级批处理商品，不接受多条无关局面/分支作为一份报告。旧任务使用旧计价，不追溯加价。
- 网站自动直播分析、已有职业棋谱报告读取和AI对弈本身原有权限不因充值改价。第三方星阵/OGS/野狐服务不纳入自有V100包，不替第三方扣费。升降级/认证对局禁用辅助的原守卫不能因付费而绕过。

### 1.3 周期、续费和扣费来源

- **24h**：同账号、所有资源共享首笔有效预留的起止锚点。没有消费时`not_started`，显示“首次使用后起计”；过期但尚未新消费时显示可用新窗口，不在GET中重新开桶。每次有效新窗口为`[start,start+24h)`，不是自然日或滑动日志。换设备/续费不重置。
- **当周**：为匹配“当周”及现有Free规则，统一Asia/Shanghai周一00:00到下周一00:00；不再用旧稿的付费日起7天锚点。UTC存储/传输带时区，前端明确写北京时间。会员到期实时按Free规则处理，无未付费的延长权益。
- 同一资源的24h和周上限同时生效，周额度不是额外赠送。Free成功报告只记一份周额度；已订阅者的套餐份数包含基础体验，不再额外叠加Free1份。
- 同档续费延长30天；跨档购买先做“当前期限到期后切换”，付款前写清生效日，不做复杂即时按天退款/升级。用户锁下串行生成不重叠subscription terms，避免双通知/两订单把同一天叠加权益。现有使用量不因换档清零。
- 有会员额度先报价为`membership`/`free_report`；不足时前端可选择`wallet`并确认准确点数，默认不能自动透支钱包。wallet不受会员赠送窗口约束，但共享单账号与全局并发/队列限制。
- 会员/Free报告以完整交付结算，失败且没有完整可访问报告时全额归还原预留。v2的retry先重新授权，不能把已退款task直接复活成免费GPU工作。legacy任务保持原结算语义。
- v2报告只有`task.completed`、0..N共N+1个位置完整且实际深度/模型校验通过、关联operation已committed时才可交付结果。`/reports/{id}/moves`等读取口对running/failed/refunded只提供状态/进度或409 `report_not_ready`，不返回ownership/top_moves或可还原分析的前缀；不把已退款前缀拷入可读取的UserGameAnalysis。legacy保持既有读语义。completed但尚未结算时，结果GET可先按固定锁序结算，再决定交付。

## 2. 实时额度契约与诚实状态

增加`GET /api/v1/billing/usage`，保留旧`balance/quota/prices`兼容字段；新UI只读v2结构，不把旧free_weekly和新桶各赠一次。

```json
{
  "server_now":"2026-11-01T04:00:00Z", "revision":18,
  "plan":{"code":"pro","ends_at":"2026-12-01T04:00:00Z"},
  "resources":{
    "reports":{
      "h24":{"state":"active","limit":5,"used":1,"reserved":1,"remaining":3,"remaining_percent":60,"starts_at":"2026-11-01T02:00:00Z","resets_at":"2026-11-02T02:00:00Z"},
      "week":{"state":"active","limit":35,"used":8,"reserved":1,"remaining":26,"remaining_percent":74.2857,"resets_at":"2026-11-01T16:00:00Z"}
    },
    "interactive":{
      "h24":{"state":"active","limit":50,"used":2,"reserved":0,"remaining":48,"remaining_percent":96,"resets_at":"2026-11-02T02:00:00Z"},
      "week":{"state":"active","limit":350,"used":12,"reserved":0,"remaining":338,"remaining_percent":96.5714,"resets_at":"2026-11-01T16:00:00Z"}
    }
  },
  "wallet":{"available_credits":1000,"standard_analysis_estimate":100},
  "payment_mode":"mock", "observed_at":"2026-11-01T04:00:00Z"
}
```

- `remaining=max(0,limit-used-reserved)`，有效套餐决定limit；不能复用旧helper“桶创建时永久冻结allowance”的行为使换档后限额错误。used/reserved历史保留，允许到期降级后used>limit，不能给负余额。0限额的百分比为null，不除零。
- Free报告显示24h最多1、当周最多1；互动显示“未包含，可购买次数包”，`state=not_included`、limit=0、reset=null，不显示“明天送领地”。
- 展示两组资源（报告/领地与支招），每组24h/周两行：剩余数/总数、剩余百分比进度条、各自倒计时和绝对重置时间。不能用一条“剩余80%”混合不同单位。
- 客户端以`server_now + performance.now()增量`倒计时，不依赖设备日期；每秒本地刷新文字，页面可见时15秒同步一次，付款/消费/退款/跨窗口、回前台和网络恢复立即重取。无必要新增WebSocket/SSE平台。
- 到边界倒计时归零只触发重取，不能本地发额度。网络断开显示上次同步时间和“数据待刷新”，不把缓存叫实时余额。未开始窗口明确说明而不伪造24小时倒计时。
- API `Cache-Control:no-store`；按账号+环境隔离缓存、logout清除、abort旧请求、忽略旧账号/旧revision响应。跨端更新15秒内可见，当前端操作完成立即刷新；不能称强实时推送。

## 3. 最小持久化、事务和付费分析边界

### 3.1 表与职责

- 复用`User.credits`和`CreditTransaction`，金额用分、余额用整数，不重建钱包。`User`增加当前24h锚点及`billing_revision`；仅有效预留/履约/结算修改revision，普通GET不写账。
- 复用`QuotaBucket`，新增nullable起止时间、`reserved`和v2类别/价格版本；不同资源/周期键有唯一约束。v2使用service的无commit原语；legacy helper保持旧调用可用。
- 增加`MembershipTerm`：user、plan、starts/ends、order唯一；当前及未来不重叠，renewal使用user行锁。
- 增加`BillingOperation`：user、kind、服务端fingerprint、客户端幂等键（user/kind/key唯一）、frozen profile/price、source、units、24h/周bucket IDs或credit ref、task/position scope、status、lease/generation、错误及有限result。状态`reserved→running→committed|refunded`，失败终态不自行重启。
- 复用`RechargeOrder`，加SKU/price/entitlement快照、provider_env、渠道transaction_id、有效期、fulfillment标记；旧订单nullable兼容。支付确认一次事务同时置paid和发放权益。退款记原渠道结果及余额/权益冲正，不能仅改一个paid标志。
- `ReportTask`加nullable `billing_version`/`billing_operation_id`；`katrain/cron/models.py`对应其实际读取字段。v2不能同时填legacy charge_ref/free_grant_period让两个settler各结一次。BillingOperation的任务/棋谱关联不得以cascade删除账务receipt；终态内容删除后仍保留owner、fingerprint、金额/源bucket、履约事实和审计id。
- 所有新增资产/额度表和`users/report_tasks`加入现有drift保护名单。只增列/索引/表，不drop重建既有资产；用项目手写迁移体系，不新建Alembic迁移链。

### 3.2 原子服务边界

```python
# endpoint owns this SQLAlchemy session transaction (autobegin is allowed).
# The services below flush only. Do not call old helpers that commit internally.
user = db.execute(select(User).where(User.id == user_id).with_for_update()).scalar_one()
existing = find_operation(db, user_id, kind, idempotency_key)
if existing:
    return require_same_fingerprint(existing, fingerprint)
quote = validate_server_quote_and_scope(db, user, request, now)
operation = reserve_source_and_create_job(db, user, quote, now)
db.commit()  # the job is not runnable before its source and linkage are durable
# GPU/payment HTTP is outside all database row locks.
```

- 所有消费者/订单履约/退款/settler按`user→order/operation→task→bucket/credit`固定锁序；先只读查候选ID，再逐个锁，不反向持task锁等user。重复operation相同fingerprint返回同结果；同key不同局面/profile返回409，不再扣。
- 并发/队列上限也在同一授权事务确认：每账号最多1个报告+1个短互动；共用既有后台报告队列，不新增另一套分布式任务平台。GPU实际全局容量取运行配置，排满在预扣前429。
- 错误/DB回滚不能保留半笔额度。结算将reserved转used或退回原bucket/ref，跨周/24h不能退入新桶。不是`peek`后调用两次各自commit的`try_consume`。
- v2报告任务仅在授权事务完成后进入pending。cron镜像只复制`katrain/cron`，不能让cron直接import web billing；保留web的终态reconcile，v2与legacy分支明确分离。v2返回/usage前可结算该账号，但使用同锁序且不重开窗口；后台周期仅兜底。
- v2失败退款后重试：在user/task锁下确认原operation已结束，以新attempt操作重新报价/预留并原子绑定，不能直接把refunded任务设pending。SGF/模型仍要匹配；同一次重试HTTP幂等。可复用合法未交付前缀，但成功报告只结一份完整权益。
- 短互动使用有上界的engine请求和lease/generation fencing；旧worker在退款后返回不能再次commit/交付。不能用通用120秒TTL回收仍在跑的长报告。超过保留期的结果可清掉payload，账务幂等receipt保留；同旧key不重跑，返回明确result_expired并重新报价。
- 删除个人棋谱/任务前，在同一user锁事务检查关联v2 operation：reserved/running或未完成终态结算时返回409 `analysis_in_progress`，不级联删走任务。终态删除不返还已消费权益，保留receipt；原旧reaper只管理legacy资金ref，v2使用`report_v2`/`interactive_v2`等明确reason/ref并从旧reaper/通用TTL排除，由operation服务统一回收。
- `katrain/cron/jobs/requeue_reports.py`一期对v2任务明确跳过/拒绝且不删任何结果，不让它用legacy exempt标记复活committed任务。保留原legacy工具功能；v2普通失败走本计划重新授权retry，不为一期另建运维重排平台。
- v2报告profile用实际client调用链验证：N为服务端SGF主线有效手数（1..500），完整位置集合为0..N，按N手报价而不能漏初始/末局面。传`min_visits=requested_visits`或等价严格参数到`katrain/cron/clients/katago.py:analyze`的真正validate_result调用，验证final、id/turn、模型SHA验证事实、实际root visits和ownership；2000请求返回500不能落有效行/completed/结算。不能只测试静态helper而实际调用仍默认min_visits=1。legacy可用显式默认兼容，但v2 worker必须传严格profile。

### 3.3 新接口及绕过审查

- `POST /api/v1/billing/quotes`：服务端校验资源、profile、拥有的游戏/局面，给准确份数或credits、source、expires_at和规范化fingerprint。执行时重新校验；过期/报价变化409，不让客户端任意指定user/model/visits/金额。
- `POST/GET /api/v1/billing/orders`及`GET /orders/{id}`：仅自己订单；新建传SKU+provider+idempotency key，未付15分钟到期。客户端“已付款”不是履约证据。
- `POST /api/v1/analysis/positions`、`GET /api/v1/analysis/positions/{operation_id}`：自有云端的固定profile单局面分析，用户可查询同一个operation；结果包含已授权的领地/候选着法，旧按钮适配到此结果，不各打一次GPU。
- 普通Kiosk局面选定**有界完整SGF快照**路线，不先同步另一个用户棋谱平台：盒端本地先校验session归属和原ranked/free场景守卫，再导出当前主线前缀（含初始摆子、完整劫历史、初始行棋方、rules、komi）。云端接受这是已认证用户提交的分析输入，按≤256KiB、≤500手、≤19×19、完整合法性/可忠实还原的setup校验后生成自己的fingerprint；不信payload的用户、费用、ranked=false或raw引擎参数。使用中央`guard_user_has_no_pending_ranked_game`，保留本地certified/ranked守卫。local session_id仅回显关联，不要求云端manager加载；PVP既有room专用桥单独保留。自有云端已有user_game引用仍必须查owner和版本。
- `server.py`现有`/api/analysis/current,extra,continuous,game,scan,region`、generic action及`/api/pvp/territory`，以及`endpoints/analysis.py`的`/api/v1/analysis/analyze`、`quick-analyze`和`endpoints/hint.py`的`/api/v1/hint`/`core/hint_gate.py`，均进入必做触发/返回矩阵。v2启用后旧raw payload明确拒绝或映射固定profileoperation，不能成为不计量旁路。无限continuous/任意extra先拒绝（显示有限分析方式），不为一期设计无限流计费。
- 复核`interface.py:get_state`、WebSocket、user_game analysis和报告结果读取：Free不能不经过互动授权就从自动分析字段读到任意私有支招。优先在现有**针对当前接收账号**的状态输出边界过滤辅助字段，不修改引擎node.analysis或共享session.last_state影响对手/旁观者；保留AI对手实际落子、必要比赛状态和原rated/ranked守卫。直播/职业报告公开读维持原语义。
- 盒端在`RemoteAPIClient`和`RepositoryDispatcher`增加billing/analysis方法，先核对已有`cloud_session_is(current_user.id)`绑定；_remote_only本身不证明身份。请求捕获不可变云端token/账号及generation，实际发出HTTP/refresh时仍须是这份绑定，不能await后从共享单例取另一账号token；绑定变化拒绝发请求/丢弃响应并重新认证。仅“响应回来后丢弃”不能补救已错扣。换账号测试暂停在发送前，保证绝不发乙token替甲扣钱。不信本地user_id，不用SQLite结算、不硬编码IP、不把secret放进客户端。离线503含need_online，不回空余额或假成功。
- HTTP约定：402需要付费/余额不足，429额度或并发上限（带各窗口remaining/reset及可选充值），409幂等/报价冲突，503云端不可达；错误不能触发钱包自动兜底。

## Chunk 1: 共享基础与已确认设计

### Task 1: 建立本功能执行分支、现状清单与契约

**Files:** Read `AGENTS.md`、上述旧payment track、`config.py`、`billing.py`、`quota.py`、`reports.py`、`report_settlement.py`、`repository.py`、`remote_client.py`、`migrations.py`；Create `docs/operations/membership-recharge.md`、`tests/web_ui/test_membership_catalog.py`。

- [ ] 1.1 fetch实际origin/develop；在与当前目录并列的新`/Users/fan/Repositories/katrain-membership-recharge` worktree开`feature/membership-recharge`，保留根工作区和ES工作区。只复制本计划、评审、交接、会员设计/Fixture文件，不`git add .`夹带别的任务。不复制node_modules/.venv或截图全集；复用已有环境。
- [ ] 1.2 记录实际基线、billing开关、报告/余额旧行为及P3是否已完成。仅记录布尔状态和摘要，不打印env/密钥/手机号。不要把旧track过时事实当现在的安全事故。
- [ ] 1.3 冻结四档目录、100次包29元/1000credits、固定profile与有效时间语义；写下面的失败测试，再最小实现`billing_catalog.py`的纯规则。

```python
def test_free_has_report_trial_but_no_standalone_analysis():
    free = catalog()['free']
    assert free.reports_week == 1
    assert free.interactive_h24 == free.interactive_week == 0

def test_pack_and_membership_comparison_uses_same_standard_unit():
    pack = products()['analysis_100_v1']
    assert (pack.amount_fen, pack.credits) == (2900, 1000)
    assert pack.credits // INTERACTIVE_STANDARD_CREDITS == 100
    assert INTERACTIVE_STANDARD_CREDITS == 10
```

- [ ] 1.4 Run `pytest tests/web_ui/test_membership_catalog.py -q`：先因新接口缺失失败，后覆盖价格整数/4倍深度、停售旧SKU但履约旧订单、不同类型资源不混加。通过后commit `define membership catalog and analysis units`。

### Task 2: 两端实时额度和购买预览（后端之前）

**Files:** Modify `docs/design/membership-recharge-2026-10-31/index.html`；Create/Modify `docs/design/membership-recharge-2026-10-31/README.md`、`docs/design/membership-recharge-2026-10-31/contracts.json`。

- [ ] 2.1 用`ui-ux-pro-max`读取现有Galaxy/kiosk主题、全局字体字号与1024×600约束；以用户Codex截图为额度信息层级参考，不复制品牌/小字号。交互区放“复盘/领地与支招”资源选择，每个资源显示24h与当周两条剩余进度、数量/百分比和重置倒计时。
- [ ] 2.1a Kiosk以“用量／订阅／按次充值”分屏/页签组织，不在1024×600塞四档卡片和四条进度再缩小字号；Free放当前权益/体验入口，付费升级仍为三张卡。Galaxy可复用同契约采用较宽布局。
- [ ] 2.2 在隔离Fixture实现Free、会员、已耗尽、未开始24h、未包含互动、正在预留、倒计时跨零/重取、离线旧数据、100次包单价和模拟支付。没有余额/权益的生产模拟数据；模拟按钮留在预览工具区。
- [ ] 2.3 固定同一UTC clock为测试基准，前端每秒递减而非每秒发请求。展示“本周0/1，X天后恢复”时不能让24h重置误导为可领取Free新报告。0额度显示“未包含”，无NaN。
- [ ] 2.4 在Galaxy1440×900和Kiosk1024×600做一次代表性的真实预览；同时保存Artifact、实现截图、并排与差异/叠加图，记录间距/层级/字体/图标/语义，尤其检查大字号时数量和倒计时不截断。仅重拍受影响状态，不做全状态摄影。
- [ ] 2.5 给用户看可操作预览并记录确认。**用户未明确确认前，不进入当前会员购买/用量切片后端实现**（本会话AGENTS要求）。预先固定§2契约、Fixture删除条件；不把确认旧三卡页面当确认本轮新进度栏。commit `preview membership usage and prepaid checkout`。

## Chunk 2: 用量与账务（视觉确认后）

### Task 3: 非破坏性schema与有效套餐/周期服务

**Files:** Modify `katrain/web/core/{models_db,migrations,config}.py`；Create `katrain/web/core/{billing_catalog,membership,billing_usage}.py`；Create `tests/web_ui/{test_membership_periods,test_membership_usage_pg}.py`。

- [ ] 3.1 编写有真实PostgreSQL连接的迁移/并发fixture，沿现有测试风格用显式TEST DB URL，非隔离库拒绝破坏性fixture。SQLite只用于纯规则，不拿它证明行锁正确。
- [ ] 3.2 实现§3.1最小表/列/索引和保护名单，重复迁移幂等，已有credits/账本/order/task不丢失。模型和现有手写迁移同时更新，不依赖create_all加旧表列。
- [ ] 3.3 有效套餐按服务端now选择已付term，到期取Free；无term按Free。24h锚点仅在首次有效消费写入，周一边界正确处理UTC/ISO周跨年。纯函数返回时间边界，GET不新建额度或自动赠点。
- [ ] 3.4 测试自然周周日23:59:59→周一00:00、24h精确边界、设备改时钟、会员到期/续费不重置、Free没有日赠互动、未开始/limit0、reserved降低可用量。
- [ ] 3.5 Run `pytest tests/web_ui/test_membership_periods.py tests/web_ui/test_membership_usage_pg.py -q`，预期边界与PG测试全部通过；没有PG时明确未验证，不以skip作为可发布。commit `add durable membership and quota windows`。

### Task 4: 原子预留/结算、幂等与legacy并存

**Files:** Modify `katrain/web/core/{billing,quota,report_settlement,report_reaper,user_game_repo}.py`、`katrain/web/api/v1/endpoints/{reports,user_games}.py`、`katrain/cron/{models.py,jobs/report_analyze.py,clients/katago.py,jobs/requeue_reports.py}`；Create `tests/web_ui/{test_membership_operations_pg,test_membership_report_settlement}.py`；Extend `tests/web_ui/{test_report_reaper,test_cron_katago_contract,test_report_analyzer}.py`及既有requeue测试。

- [ ] 4.1 把现有资金/桶操作抽出明确`*_in_transaction`无commit原语，legacy入口仍保留事务所有权。新的endpoint只commit一次；从auth开始已有autobegin时不再嵌套`db.begin()`制造异常。
- [ ] 4.2 实现user锁、固定锁序、fingerprint与user/kind/idempotency unique；预留两桶或钱包、创建operation并关联task在同一事务。报价/队列不满足时所有计数不变。异步GPU在commit之后、行锁之外运行。
- [ ] 4.3 report端点按billing_version分流；v2正常/深度/Free份数、新wallet最低价、内部重试、完整失败退款和新attempt重授权见§1/3。旧任务不改价，`settle_finished_reports`和通用TTL不重复处理v2。
- [ ] 4.3a 真实`KatagoClient.analyze()`链路按v2 requested_visits验证每个final响应、模型、ownership和0..N覆盖；返回不足深度绝不能completed。进度GET只报计数，`/reports/{id}/moves`及同内容读出口在complete+operation committed之前不交付前缀；结果GET可先结算以免完成窗口假报错。
- [ ] 4.3b 在用户锁下保护活跃/未结算v2报告的棋谱删除；终态删除保留BillingOperation及账务事实、不退款。旧reaper/TTL不处理v2 reason/ref；旧requeue在写前拒绝v2，绝不删除已付v2结果。允许legacy回归按原规则继续。
- [ ] 4.4 切换前对账旧free_report桶/在途legacy报告。已有当周免费使用量必须带入v2共享report周计数；按用户锁作一次性带标记迁移，不新发第二次Free。旧free预留尚未终态就不对其用户启用v2，待既有结算结束；余额不清零/重置。
- [ ] 4.5 PG测试两终端争最后1份、同请求并发/不同fingerprint、两桶一满不半扣、付款/退款同时消费、跨周期退款回原桶、已退款retry重新授权、旧当前周已用不多送、新旧settler不双结。异常注入在flush/commit前后，核对持久状态而非只看HTTP。
- [ ] 4.5a 增加源码缺口的最小回归：有内部前缀→failed全退→结果读不返回分析→retry重新授权完整成功→重复读免费；活跃删除409、终态删除receipt还在、旧requeue不改v2；mock HTTP走真实client“请求2000返回500”不能完成/结算，以及缺第0/最后位置不能完整交付。不用GPU、不造全新审计平台。
- [ ] 4.6 Run `pytest tests/web_ui/test_membership_operations_pg.py tests/web_ui/test_membership_report_settlement.py tests/web_ui/test_billing_race.py tests/web_ui/test_report_settlement.py -q`。commit `reserve and settle membership usage atomically`。

### Task 5: 实时usage接口与盒端权威转发

**Files:** Modify `katrain/web/api/v1/endpoints/billing.py`、`katrain/web/core/{remote_client,repository}.py`；Create `tests/web_ui/test_membership_usage_api.py`，Extend既有remote/repository测试。

- [ ] 5.1 实现§2响应、revision、no-store、账号归属；有效额度纯查询，不调用会create/commit的旧`quota.peek`来实现新GET。若需先处理终态结算，作为明确的先行事务，随后同一一致快照构造响应。
- [ ] 5.2 旧API字段保持兼容但标明effective backend/version，新UI不能把两个来源重复加总。老balance可继续显示legacycredits，标准次数估算不混成报告份数。
- [ ] 5.3 为RemoteAPIClient和RepositoryDispatcher增加billing/有界快照分析方法，落实§3.3不可变cloud_session绑定，保留云端4xx、断网503。测试云端没有本地session也能分析一次合法快照、同账号两端读取同一变化，以及共享盒切账号时不读取/扣前后另一人的账。云端不接受任意user_id归属。
- [ ] 5.4 Run `pytest tests/web_ui/test_membership_usage_api.py tests/web_ui/test_billing_api.py -q`；验证匿名401、别人的订单/余额不可读、数据库出错不回0、GET不会刷新grant。commit `expose authoritative membership usage to both clients`。

## Chunk 3: 模拟购买与单局面付费旅程

### Task 6: 商品订单、TEST-only模拟渠道和一次履约

**Files:** Create `katrain/web/core/{payments,payment_mock}.py`、`katrain/web/api/v1/endpoints/payment_test.py`；Modify `billing.py`端点、`api.py`、`config.py`、`server.py`；Create `tests/web_ui/{test_membership_orders_pg,test_mock_payment_boundary}.py`。

- [ ] 6.1 显式环境`KATRAIN_DEPLOY_ENV=development|test|production`（默认production）和`PAYMENTS_MODE=disabled|mock|live`（默认disabled）。server/board不是TEST/PROD区分，不能据server就允许mock。production+mock启动拒绝；mock操作路由只在显式test/development注册，并受测试管理员凭据保护，无secret的匿名“模拟成功”接口不存在。
- [ ] 6.1b 实现§0的BILLING_V2_ENABLED统一功能闸和BILLING_ENFORCED不一致时拒启；TEST通过显式配置启用v2和mock，旧模式测试维持默认关闭。测旧API不存在v2“UI有限额、后端仍免费直通”的混合组合。
- [ ] 6.1a **mock实际数据库也必须隔离**：强制显式`KATRAIN_DATABASE_URL`，在Settings解析中禁止mock沿`~/.katrain/config.json`或仓库配置隐式回落；数据库初始化/schema写入前只读校验预先建立的TEST环境标记及预期库身份（或等价已验证部署约束），未知/production标记/目标不符即拒绝启动和写账。服务不能自动把未知库标test。测试角色只具备TEST库权限，复用同一schema，不增加第二套钱包。空白临时测试库的标记由测试bootstrap显式建立，不由正常应用初始化写入。
- [ ] 6.2 接订单创建/查询/自己列表，冻结SKU/价格/权益/环境和15分钟有效期。渠道调用不持user锁；结果通过同一user→order锁序幂等履约，支付状态和credits或term发放同一次commit。重复通知/查单/浏览器刷新只发一次。
- [ ] 6.3 mock provider输出清楚标注的非真实付款信息，允许模拟成功/失败/过期/通知重复/回调漏到后查单。模拟通知按固定测试密钥校验，持久化通知/处理事实后才确认接收，不能200后只留内存任务等重启丢款。
- [ ] 6.4 paid不能被旧失败通知降级；过期前端不是渠道已关单的证明。已付未履约用同一order恢复；两个会员订单在user锁下顺延term；换档按到期后生效，UI/订单均记录生效日。
- [ ] 6.5 mock退款通过原order+唯一refund_ref作同一冲正；余额不足退款不造负余额，显示需人工处置；mock不允许真实钱或凭据混入。原始支付私钥/手机号不进日志/Git。
- [ ] 6.5a 一期自动流程仅做全额退款：钱包须扣回该订单全部grant且当前available足够；会员须无已用/预留权益且无后续term排期依赖，再原子作废term并记退款。条件不满足转人工审核，不在本期发明部分退款/多批点数算法，也不能退了钱还保留会员。该自动化边界不是对法定退款权的否认，后续真实渠道按协议处理。
- [ ] 6.6 Run `pytest tests/web_ui/test_membership_orders_pg.py tests/web_ui/test_mock_payment_boundary.py tests/web_ui/test_billing.py -q`。必须测production拒mock、test标签+缺显式URL/未知或非TEST实际库仍拒绝（schema写入前）、匿名伪通知/金额篡改/他人订单/重放/付款与退款争余额。commit `add isolated mock checkout and idempotent fulfillment`。

### Task 7: 一次标准分析、两种显示、无付费旁路

**Files:** Create `katrain/web/core/paid_analysis.py`、`katrain/web/api/v1/endpoints/paid_analysis.py`；Modify `api.py`、`endpoints/{analysis,hint}.py`、`core/{hint_gate,pvp_territory,remote_client,repository}.py`、`server.py`、`interface.py`及相关状态输出；Create `tests/web_ui/{test_paid_analysis,test_paid_analysis_guards}.py`。

- [ ] 7.1 先记录§3.3所有实际触发/泄露分析入口的矩阵：路由/动作、session归属、ranked守卫、有限profile或明确拒绝、返回结果出口。用相同service接入，不能只收费新增按钮而旧current/extra仍免费计算同一服务。
- [ ] 7.2 落实§3.3的完整SGF快照契约/已有云端对象owner校验和ranked守卫，不尝试云端加载普通Kiosk local session；profile服务端固定，预留前复用同用户既有有效授权operation，其他先授权。单次GPU同时includeOwnership+候选着法，500/2000visit上限固定。validate root visits、ownership长度/数值和返回指纹，错误body不能当成功。
- [ ] 7.3 审核旧异步current返回“正在分析”的语义；不能在返回初始state时就结算。只有完整可访问结果才commit；重放返回同operation结果，开关领地/PV只读。模型/规则/位置变化必须新报价，不能静默复用旧结果。
- [ ] 7.4 短任务的超时/崩溃recovery带generation fencing，退款后迟到结果不再收费或交付；报告长任务不由120秒通用TTL回收。result payload上限64KiB、过期24h后有界清payload，保留最小账务receipt，不保留搜索树或无界内存缓存。
- [ ] 7.5 测试Free不能通过新/旧路由、generic action、state/WS或engine原始公网路径拿未授权私有支招；已拥有Free报告内部读取仍可行；旧ranked禁止辅助与第三方分析规则不变。真实GPU端口仅云端内网可访问，发布时核实而非假设。
- [ ] 7.5a 对真实已挂载`/api/v1/analysis/analyze`、`quick-analyze`和`/api/v1/hint`分别断言Free无权益请求被拒且engine调用数为0；一次已授权标准结果分别展示领地/hint后GPU调用和扣量仍为1。保留当前用户原`DefaultHintGate`场景限制，不能因会员允许rated作弊。
- [ ] 7.6 Run `pytest tests/web_ui/test_paid_analysis.py tests/web_ui/test_paid_analysis_guards.py -q`，与既有lobby territory/ranked守卫相关测试一起聚焦运行，不跑无关全库。commit `meter one position result across territory and hints`。

## Chunk 4: 双端真实集成与交付

### Task 8: 共享React用量/倒计时与产品页面

**Files:** Create `katrain/web/ui/src/{api/billingApi.ts,types/billing.ts,hooks/useBillingUsage.ts,components/billing/UsageLimits.tsx}`及对应测试；Create `galaxy/pages/MembershipPage.tsx`、`kiosk/pages/MembershipPage.tsx`；Modify `GalaxyApp.tsx`、`galaxy/components/layout/{MainLayout,GalaxySidebar}.tsx`、`kiosk/KioskApp.tsx`、`kiosk/components/settings/AccountSection.tsx`、原领地/支招/报告入口。

- [ ] 8.1 共享组件不反向importGalaxy/Kiosk；两端仅各自布局、同一billing API契约和账号缓存。加载、Free0、预留、耗尽、reset边界、离线、购买失败/待确认都有诚实文案；不写死余额/倒计时/成功结果。
- [ ] 8.2 在`useBillingUsage`实现server-clock偏移+monotonic计时、每秒本地文字、可见15秒poll和操作后重取；fake timers测设备改时钟、窗口跨零、回前台重取、旧revision/旧账号响应丢弃、组件卸载不泄漏timer。页面不需要长期后台轮询。
- [ ] 8.3 新SKU同时显示29元/100标准次、0.29元/次、增强档4次、会员满额参考的相同单位对比，不写“会员总是更省”。价格和可购买能力来自catalog；Free展示每周1次报告，不出现独立互动赠送或“注册赠10000积分”。
- [ ] 8.4 支付完成只根据服务端order状态更新；前端跳回/点击已付款不会加钱。复盘引用operation，扣费前展示准确来源/成本；没有自动钱包回退。Kiosk字号/字体跟全局设置，关键按钮≥44px。
- [ ] 8.5 Run `cd katrain/web/ui && npm test -- src/hooks/useBillingUsage.test.ts src/components/billing/UsageLimits.test.tsx src/galaxy/pages/MembershipPage.test.tsx src/kiosk/pages/MembershipPage.test.tsx`。再按共享件影响运行`npm run build`与`npm run build:kiosk-2d`各一次；新变化/失败才重复。
- [ ] 8.6 代表性真实浏览器跨端同账号：mock买Pro→两端额度一致→执行一个mock-engine标准互动→领地/支招切换只扣1→模拟终态失败归还→24h/周跨界与离线恢复→Free周报告后独立互动仍需付费。使用TEST DB/可控engine，不在生产试扣余额。
- [ ] 8.7 按确认Artifact在相同viewport作最终代表性视觉对比；删除生产导入路径的Fixture和调试按钮；保留独立docs预览标记。commit `integrate membership usage and checkout in Galaxy and kiosk`。

### Task 9: 生产前置、评审与分阶段发布

**Files:** Update `docs/operations/membership-recharge.md`、`core/health_report.py`、必要原auth限流/身份接口测试；真实渠道后续适配器独立文件，不改本期模拟边界。

- [ ] 9.1 核实原P3手机绑定/验证身份与注册限流是否已有可用实现。**本计划不以“总闸打开+Free1”直接绕过旧硬前置**；TEST用明确mock身份，PROD缺前置时不开放免费领取，UI说明“完成验证后领取”，记录依赖，而不是静默改为Free0却说免费已上线。注册赠通用credits保持0；不清除历史合法credits。更新health规则仅在真实前置可验证时允许Free1。
- [ ] 9.1a 抽出可信的Free领取资格检查，只由云端已有P3事实/受信身份信息决定；不能接受客户端`phone_verified`布尔值。阶段A在隔离TEST数据库/测试app依赖中注入明确的已核验测试主体以验Free旅程，不发真实短信、不把测试身份断言注册为生产HTTP后门。
- [ ] 9.2 对当前正式模型/V100作有界容量核对，优先历史记录；覆盖接近500手报告、500/2000visit和互动混合使用。价格/10/50/200调用权益属于本期初始配置，不声称500元优惠成本永久有效；若Max不安全先禁售并如实显示，而非静默削配后仍卖20盘。
- [ ] 9.3 使用独立代码review者检查账务原子性、Free范围/旁路、profile、UI真实状态与mock生产隔离，修复重要问题再发布。**本次两轮Astra评的是计划，不是未来代码已通过。**
- [ ] 9.4 阶段A完成可在TEST验证真实账务+mock支付。真实微信/支付宝只在官方产品签约/资质/密钥具备后配置；申请流程和时间参考见旧讨论稿对应节，不能把模拟当渠道验签实测。至少完成真实通知验签/金额商户校验、漏通知查单、小额支付退款，才能启用正式收款。
- [ ] 9.5 用户授权正式集成时按项目四步：最新develop合入功能分支并验证/push→合入develop并push→更新smartbox-software/vendor/katrain并提交push main→先home-ubuntu、后新ucloud-v100（117.50.177.254）及授权的RK界面验收。不在ES worktree发布，不使用旧117.50.183.169，不照搬过时Compose重建原生Docker无关服务。
- [ ] 9.6 正式切换先处理legacy在途授权和旧当周Free使用量；确认同一数据库/账号、prod禁mock、所有计量路径同版。回退只关闭新销售/新授权或切回兼容读，不清账本/桶、不退回会免费复活已扣任务的旧worker；必要时只暂停新增付费任务并保留读取/结算。
- [ ] 9.7 最终给用户：已发布SHA/真实运行版本、两端截图、TEST/mock实际通过项、未具备的商户/身份/容量前置，以及真实支付是否验过。更新所有状态诚实区分“设计完成／软件TEST完成／正式收费完成”。

## 4. 并行边界、验收清单与交接

- 只有已确认UI契约之后可并行：共享无业务依赖的用量组件实现与已冻结schema下的支付mock适配器。`models_db.py/migrations.py/billing_usage.py`由单一集成者持有；报告/互动接线依赖其稳定后再分工。不把多个未闭环旅程一起铺开。
- 验收核心：两种资源各有24h/周数量和正确倒计时；Free周报告1次且无独立互动赠送；29元包标准100次且不被旧低价SKU绕过；一次领地/支招只扣一次；同账号跨端额度15秒内更新；并发不超扣/双发，失败退款回原周期，legacy资产不丢，PROD无模拟入口/凭据。
- 计划评审上限为独立Astra Max **最多两轮**，每轮写文件并按反馈修订。本计划不自动追加第三轮、重做产品研究或为模拟支付发起实际扣款。
- 第1轮结果：`../reviews/2026-11-01-membership-plan-astra-r1.md`，Needs revision，0 Critical/6 Important。本稿已按I1–I6补齐直接分析入口、v2结果交付门、删除/旧requeue/回收边界、盒端SGF与不可变云端身份、报告真实深度/0..N完整性、mock实际数据库隔离；交第2轮复核，不冒称代码已修复。
- **最终计划状态（2026-11-01）：第2轮独立Astra Max已Approved，未解决Critical 0 / Important 0，见`../reviews/2026-11-01-membership-plan-astra-r2.md`。本次共两轮，到此结束；第2轮后仅追加本结果记录，未改业务决策或执行正文。可交Gemini实施，代码/TEST/正式支付验收仍按计划另行完成。**
- Gemini接手先读本计划、两轮评审和新交接文档，输出实际现状与剩余步骤，再从Task1执行；缺官方能力时完成阶段A而如实留下阶段B，不绕过前置。每个阶段及至少30分钟汇报进度和当前步骤ETA，汇报不暂停开发。
