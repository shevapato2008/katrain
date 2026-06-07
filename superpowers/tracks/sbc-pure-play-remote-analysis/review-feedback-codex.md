# Codex 评审反馈：对弈付费分析 + 积分充值

> 审核范围：`requirements.md`、`plan.md`，并抽查了当前仓库中的 `katrain/web/interface.py`、`katrain/core/game.py`、`katrain/core/engine.py`、`katrain/web/core/{models_db.py,auth.py,config.py,db.py}`、`katrain/web/server.py`、`katrain/web/session.py`、前端 `katrain/web/ui/src/{kiosk,galaxy,components,hooks,context}`。
>
> 总体取向：这份计划的分阶段思路是对的，但在“云端权威扣费”“排位反作弊”“扣费幂等/退款一致性”“真实源码入口”上还不够硬，直接照着做会留下资产和作弊漏洞。

## 发现清单

### [严重度: Blocker] kiosk 侧积分没有明确走云端权威，可能落成“本地 SQLite 扣费”

位置: `requirements.md §3.3`、`requirements.md §4 R2/R3`；`plan.md 阶段 2`；代码 `katrain/web/core/config.py:94`、`katrain/web/api/v1/endpoints/auth.py:84-132`

问题: 需求明确说积分余额/扣减以云端服务器为准，kiosk 离线时禁用付费分析。但计划阶段 2 只写了在 FastAPI 本地新增 `billing.py` 和 `/billing/*` API，未说明 board 模式下这些 API 必须代理到 `REMOTE_API_URL`。当前 board 模式会强制使用本地 SQLite，登录也是本地 shadow-user token。如果实现时前端调用板端本地 `/api/v1/billing/*`，用户重置/篡改本地 SQLite 就能恢复 `User.credits`，服务端权威失效。

建议: 阶段 2 必须拆出 server/board 两条路径：server 模式直接读写云端 DB；board 模式的 `balance/spend/redeem/recharge/orders` 全部通过 remote client 转发云端，离线直接返回 `need_online`，本地只允许短期只读缓存且不得参与扣减。补测试：board 模式下修改本地 `users.credits` 不影响余额；断开 `REMOTE_API_URL` 后付费分析按钮禁用且 `spend` 不落本地账。

### [严重度: Blocker] 排位禁分析的服务端门控仍不完整，现有绕过入口很多

位置: `requirements.md §3.5`、`requirements.md §6.4`；`plan.md 阶段 4 rated 流水线`；代码 `katrain/web/server.py:334-346`、`katrain/web/server.py:464-520`、`katrain/web/server.py:598-645`、`katrain/web/session.py:14-22`

问题: 计划只说 `_do_new_game` 增加 `rated` 并在 `_do_toggle_ui` / 付费分析拒绝，但当前 rated 来源分散：galaxy 只是 URL `mode=rated`，仍调用 `API.newGame`；kiosk 用 `/api/game/setup` 的 `mode='ranked'`；多人排位在 matchmaker 里是 `game_type='rated'`。`WebSession` 也没有持久的 `rated/game_type` 字段。即使付费分析接口拒绝，现有 `/api/analysis/extra`、`/api/analysis/continuous`、`/api/ui/toggle`、`/api/analysis/show-pv` 等旧接口仍可能被直接请求绕过前端置灰。

建议: 在 `WebSession` 增加统一字段 `game_type: free|ranked|rated|research` 或 `analysis_allowed: bool`，由 `create_session`、`new-game`、`game/setup`、matchmaker 创建会话时写入，并同步到 `WebKaTrain.get_state()`。新增 `assert_analysis_allowed(session)`，统一保护 `/api/ui/toggle` 中的 `show_hints/show_ownership/show_policy/show_dots`、`/api/analysis/extra`、`/api/analysis/continuous`、`/api/analysis/show-pv`、新的付费分析接口。补 API 级测试：排位会话直接 POST 这些旧接口均 403 且不触发引擎/扣费。

### [严重度: Blocker] `ref_id` 带前端 nonce 会让“幂等”失去防连点意义

位置: `plan.md:135`；`requirements.md §6.3`

问题: 计划让前端生成 `f"{session}:{node_id}:{kind}:{nonce}"`。这只能防同一次 HTTP 重试，防不了用户在同一节点连续点击，因为每次点击都能换 nonce，后端会认为是不同付费动作并多次扣费。对“领地/支招/变化图按节点跑一次”的 UX 来说，这是明显的重复扣分风险；如果产品真的允许同一节点同一道具反复付费，也必须在文案和结果刷新策略里明确。

建议: 默认改成服务端派生幂等键：`analysis:{session_id}:{node_id}:{kind}`，同一会话同一节点同一 kind 成功后再次请求直接返回既有 entitlement/result 或 409 “already_purchased”，不再扣分。若需要“强制重算”，新增显式 `force_recompute=true`，由服务端生成 attempt id 并在 UI 二次确认。测试覆盖双击、重试、刷新页面后再次点击。

### [严重度: Blocker] “先扣分、再远程分析、失败退款”没有持久 pending 状态，进程崩溃会吞积分

位置: `plan.md:132-138`；`requirements.md §6.3`

问题: 阶段 4 的流程是 `spend -> 调引擎 -> 回调成功/失败 -> 失败 grant 退款`。分析请求可能耗时数秒，且远程引擎、网络、进程都可能在扣费后崩溃。当前计划没有 `pending/committed/refunded` 状态、没有后台 reconcile、没有管理员修复入口；如果进程在扣费后、退款前退出，用户余额会永久少。

建议: 不要把资产状态只放在内存回调里。新增 `PaidAnalysisRequest` 或扩展 `CreditTransaction.status`：`reserved -> committed/refunded/expired`。扣费时先创建 pending/reserved 记录并减少可用余额；分析成功 commit，失败/超时 refund；启动时扫描超时 pending 自动退款或标记人工处理。最小版本也要有 `try/finally + timeout + pending reconcile`。补测试：扣费后模拟引擎异常、超时、进程重启后的 pending 清理。

### [严重度: High] R1 抑制自动 eval 的计划定位不准，容易漏掉真正的初始分析入口

位置: `plan.md:36-40`；代码 `katrain/core/game.py:463-465`、`katrain/core/game.py:553-560`、`katrain/web/interface.py:382-465`、`katrain/web/interface.py:1027-1030`

问题: 计划说 `_do_new_game(interface.py:382)` “不调用 analyze_all_nodes(line 465)”，但当前 `_do_new_game` 并没有直接调用它；初始分析来自 `Game.__init__` 里 `skip_initial_analysis=False` 时启动的后台线程。`interface.py:465` 实际在 `_do_edit_game`。另外配置变更重启引擎后也会 `analyze_all_nodes`。如果只照计划改，很可能仍有初始/编辑/配置路径发 eval。

建议: 阶段 1 改为建立统一 helper，例如 `auto_eval_enabled()` 或 `should_suppress_auto_eval()`，在创建 `WebGame` 前传入 `skip_initial_analysis=skip_initial_analysis or suppress_auto_eval`；`WebGame.play` 调用 `super().play(..., analyze=analyze and auto_eval_enabled)`；`_do_update_state` 跳过 ponder；`_do_edit_game`、配置重启后的 `analyze_all_nodes`、`load_sgf` 默认分析也要按 play/research 模式区分。补测试覆盖新局、走子、编辑局、加载 SGF、配置重启，而不只是走一步。

### [严重度: High] 阶段 3 先把 `analyze_extra/game_analysis` 路由到远程，会在付费门控前打开免费远程分析入口

位置: `plan.md:102-108`、`plan.md:123-138`；代码 `katrain/web/server.py:598-616`、`katrain/web/interface.py:907-916`

问题: 阶段 3 是“不计费”远程引擎编排，计划要求复盘、`analyze_extra`、`game_analysis` 都改用 `analysis_engine()`。但阶段 4 才做付费分析和 rated 门控。这样阶段 3 独立上线时，play 模式下旧的 `/api/analysis/extra` 仍可免费请求远程强引擎；即使阶段 4 后，如果旧接口不封，也能绕过新付费接口。

建议: 阶段 3 只接复盘报告/研究模式，或者同时加服务端 `analysis_allowed` 守卫。play 模式的实时分析必须只走阶段 4 的 `paid_analysis`。计划里明确旧 `/api/analysis/extra` 在 `MODE_PLAY` 下对 `territory/hints/variations/ponder` 返回 403 或迁移到 paid handler，research/report 模式保留免费/不计费行为。

### [严重度: High] 管理员权限模型不存在，`校验 admin` 现在没有落点

位置: `plan.md:85`、`plan.md:200-207`；代码 `katrain/web/core/models_db.py:29-43`、`katrain/web/models.py:142-150`、`katrain/web/server.py:71-75`

问题: 当前 `User` 只有 `username/rank/credits` 等字段，没有 `role/is_admin`。服务端启动时创建 `admin/admin` 只是普通用户。计划多处要求管理员加分、生成兑换码、确认 ManualConfirm 订单，但没有数据模型、JWT claims、依赖函数或默认管理员迁移策略。实现时很容易退化成 `username == "admin"`，这对真实充值后台不够安全。

建议: 阶段 2 加入 `User.is_admin = Column(Boolean, default=False, nullable=False)`，Pydantic `User` 和 repository 同步返回；新增 `get_current_admin_user` 依赖，所有 `/billing/admin/*` 使用它。首次初始化可把首个默认 admin 标记为 admin，但必须支持改密码/禁用默认弱口令。board 模式 shadow-user 不应获得本地 admin 权限。补非 admin 403、shadow user 403、admin 成功测试。

### [严重度: High] 用 `Float` 表示积分和人民币金额不适合资产账本

位置: `requirements.md §5`、`plan.md:63-66`、`plan.md:193-201`；代码 `katrain/web/core/models_db.py:39`

问题: 现有 `User.credits` 是 `Float` stub，但计划继续让 `CreditTransaction.delta`、`RechargeOrder.credits`、`price_cny` 使用 Float。资产账本用浮点数会带来舍入误差、比较误差、审计困难，`credits >= amount` 在不同 DB/驱动下也容易出现边界问题。充值金额还涉及人民币，不能用二进制浮点。

建议: 本期就迁到整数。若积分没有小数，使用 `credits_balance INTEGER` / `delta INTEGER`；人民币用 `price_fen INTEGER`。如果必须保留兼容字段，服务层统一把旧 `User.credits` 当显示值，新增账本使用整数并做一次性迁移/回填。配置里的单价也用整数。测试覆盖 0、刚好够、连续扣减后的余额精确性。

### [严重度: High] 无 Alembic 下直接上账本，需要显式迁移/索引策略

位置: `requirements.md §5`、`plan.md:63-66`；代码 `katrain/web/core/auth.py:87-130`

问题: 需求说没有 Alembic，`create_all` 自动建新表。新表可以创建，但新增 `User.is_admin`、调整 `credits` 类型、增加唯一索引/约束、为兑换码和订单加索引，都不能只靠 `create_all`。当前 `init_db` 对 SQLite schema drift 会 drop all，本地缓存还行；但 billing 上线后账本数据不能被 drop。Postgres 的补列逻辑也不会处理类型变更、唯一索引和约束补建。

建议: 阶段 2 增加“轻量迁移”任务：在 `init_db` 或独立脚本中用 SQLAlchemy inspector 显式创建缺失索引/约束/列，只做可审计的 ALTER，不对包含 billing 表的 DB 执行 drop all。若调整 `User.credits` 类型，则提供回填脚本和回滚说明。补测试在已有旧 schema 的 SQLite/Postgres fixture 上启动后列、索引、默认值都正确。

### [严重度: High] 兑换码的并发与爆破防护不足，`行锁` 在 SQLite 下也不可靠

位置: `plan.md:73`、`plan.md:80-90`

问题: 计划写 `redeem` “行锁取未用 code”，但 SQLite 没有等价的 `SELECT ... FOR UPDATE` 行锁语义。并发兑换同一 code 时，如果实现为先查再改，可能双发；同时没有限制错误尝试次数，短码会被脚本爆破。

建议: 兑换码使用高熵随机值，至少 128 bit，不使用可枚举短码。兑换必须是单条条件更新：`UPDATE redeem_codes SET used_by=:uid, used_at=now WHERE code=:code AND used_by IS NULL AND (expires_at IS NULL OR expires_at>now)`，检查 rowcount 后再 `grant(ref_id='redeem:{code}')`，并保证同一事务。增加按用户/IP 的失败频控，错误响应不要区分“无效/已用/过期”。并发测试必须用两个独立 DB session。

### [严重度: Medium] 付费分析结果的“一次性展示字段”没有定义清楚，会和现有 `cn.analysis` 缓存冲突

位置: `requirements.md §4 R3`、`plan.md:136-172`；代码 `katrain/web/interface.py:270-314`、`katrain/web/ui/src/components/Board.tsx:187-304`

问题: 当前 `get_state().analysis` 直接来自当前节点的 `cn.analysis`，棋盘根据 `analysisToggles.ownership/hints/policy` 渲染。如果付费分析结果写入普通 `cn.analysis`，用户之后只要切开关就能重复看，且 SGF/复盘缓存语义不清；如果不写入 `cn.analysis`，现有 `Board` 又不知道从哪里取“付费一次性结果”。计划只写“塞进 state 的一次性展示字段”，没有字段名、生命周期、节点导航/刷新后的行为。

建议: 明确状态模型，例如 `paid_analysis: {node_id, territory?, hints?, variations?, entitlements}`，按 `session_id + node_id + kind` 存内存/DB entitlement。已购买节点再次打开可免费查看已有结果，不自动重算；离开节点是否隐藏但保留 entitlement 要写清楚。`Board` 只渲染 `paid_analysis` 或在 `analysisToggles` 中区分 `paid_hints_visible`。补测试：购买后刷新页面/导航回来/同节点再次点击/新节点点击的行为。

### [严重度: Medium] API 路径和认证边界不一致，前端计划容易接错端点

位置: `plan.md:80-85`、`plan.md:138`、`plan.md:157-158`；代码 `katrain/web/api/v1/api.py:5-18`、`katrain/web/ui/src/api.ts:135-155`

问题: 后端计划写 `GET /billing/balance` 挂进 v1 endpoint，但前端计划写拉 `/billing/balance`，付费分析又写 `POST /api/analysis/paid` 而不是 `/api/v1/analysis/paid`。当前项目同时有 `/api/*` 会话接口和 `/api/v1/*` 资源接口，若不统一，board 代理、鉴权、Playwright mock 都容易分叉。

建议: 明确最终路径：billing 全部 `/api/v1/billing/*`，paid analysis 若需要访问 session manager 可放 `/api/analysis/paid`，但也要在 `api.ts` 里封装并说明它用 session token。更推荐 `/api/v1/billing/analysis/paid` 调 billing，再通过 app.state session manager 执行分析，避免支付和会话 API 分裂。文档中把前端请求路径改为精确 URL。

### [严重度: Medium] 远程引擎配置入口不够具体，`engine/remote_url` 不是当前 `Settings` 会自动读取的配置

位置: `requirements.md §4 R6`、`plan.md:102-106`；代码 `katrain/web/core/config.py:1-100`、`katrain/web/interface.py:157-170`、`katrain/core/engine.py:795-819`

问题: 计划说新增 `engine/remote_url`，但后端 `Settings` 只读取部分 env 和 `server.database_url`；KaTrain 的 `self.config("engine")` 是另一个配置体系。若不明确来源，可能出现前端/服务器以为配置了 remote_url，实际 `WebKaTrain` 初始化时没读到。`create_engine` 现在也只认识 `http_url/api_url`，不是 `remote_url`。

建议: 明确配置落点和映射：例如 `~/.katrain/config.json` 的 `engine.remote_url` 由 `WebKaTrain.config("engine/remote_url")` 读取，构造 `remote_cfg = {**engine_cfg, "backend": "http", "http_url": remote_url, ...}`；或新增 env `KATRAIN_ANALYSIS_KATAGO_URL` 到 `Settings`。健康检查失败时不要悄悄 fallback 到本地付费分析，除非 UI 明确提示“远程不可用，是否本地慢速分析”。补启动配置测试。

### [严重度: Medium] ManualConfirm 订单缺少所有权、审计和包价约束

位置: `plan.md:188-211`

问题: 计划有订单、凭证、管理员确认，但没有规定：订单套餐必须来自服务端配置而不是前端传任意 credits/price；上传凭证大小/类型/存储位置；用户只能给自己的订单提交 proof；管理员确认要记录谁确认、确认备注、实际到账金额；重复 proof/order 的处理；取消/过期订单是否还能确认。这些都是人工收款模式最容易出纠纷的地方。

建议: `RechargeOrder` 增加 `package_id, amount_fen, credits, proof_url/proof_text, proof_hash, confirmed_by, confirmed_at, confirm_note, provider_payload`。`create_order` 只接受服务端套餐 id，`proof` 接口校验 order.user_id，管理员确认只允许 pending/proof_submitted 状态，重复确认幂等返回已入账。测试覆盖用户越权提交别人的订单、前端篡改金额、重复确认、取消后确认。

### [严重度: Medium] 真支付空壳的接口形状仍需预留 raw body、验签、防重放

位置: `plan.md:193-202`

问题: 计划说 WeChatPay/Alipay Provider 空壳、webhook 现在 501。但若现在把 route 设计成普通 JSON Pydantic body，未来接微信/支付宝时要重构，因为验签通常需要原始 request body、headers、timestamp/nonce 和 event id 防重放。

建议: 即使返回 501，也把 provider base interface 定成 `verify_callback(raw_body: bytes, headers: Mapping[str, str]) -> PaymentEvent`。新增 `PaymentWebhookEvent(provider, event_id, received_at, processed_at, raw_hash)` 唯一防重表的占位模型或至少在计划写明。这样真网关接入时只填 provider，不改业务层。

### [严重度: Medium] kiosk 离线判断不能只看 `analysis_engine.available`

位置: `requirements.md §3.3`、`requirements.md §4 R3`；`plan.md:134`、`plan.md:157-158`

问题: 计划的离线守卫写的是 board 且 `analysis_engine` 不可用就返回 `need_online`，但 kiosk 付费分析依赖两条远程链路：云端 billing 和远程强引擎。可能出现远程引擎可达但云端 billing/token 失效，或者 billing 可达但 b28 不可用。只看引擎会让按钮可点后扣费失败/卡住。

建议: 前端 `CreditContext` 应暴露 `billingOnline/balanceStatus`，board 模式下余额刷新失败即禁用付费按钮并提示登录/联网；后端 paid handler 先检查当前用户、远程 billing spend，再检查 analysis engine。错误码区分 `need_login`、`need_online_billing`、`analysis_engine_unavailable`、`insufficient`。补网络断开、token 过期、remote engine down 三类测试。

### [严重度: Low] 阶段 6 的 WeChat/Alipay 空壳和管理员页面可以后移，避免拖慢核心闭环

位置: `plan.md:188-213`

问题: 本期真实支付明确是 non-goal，核心是 ManualConfirm + 兑换码。现在计划同时要求 provider 包、两个空壳 provider、webhook 空壳、充值页、管理员订单核对页，阶段 6 可能变成 UI/支付大爆炸，拖慢前面付费分析上线。

建议: 本期保留 `PaymentProvider` base 和 `ManualConfirmProvider`，WeChat/Alipay 只在接口文档或空目录 README 标注，不必实现类和路由。管理员页面可先做极简 API + 后台脚本/CLI，前台管理页作为 Phase 6b。这样不影响订单/流水/settle 生命周期，也降低集成风险。

## Top 3 必改

1. **board 模式 billing 必须云端权威**：阶段 2 先定义并测试 board 代理/离线禁用，不允许本地 SQLite 余额参与扣减。
2. **排位反作弊必须服务端统一封口**：给 `WebSession` 增加统一 game_type/rated 状态，并保护所有旧分析接口，不只保护新付费接口和前端按钮。
3. **付费扣分必须有稳定幂等键和 pending/reconcile**：去掉前端随机 nonce；扣费到分析完成之间要有持久状态，避免双扣和崩溃吞积分。

## 可砍 / 过度设计

- WeChatPay/Alipay 具体 provider 类和 webhook 路由可以只留接口契约，不必本期实现空壳。
- 管理员订单核对页面可以先降级为受保护 API 或运维脚本，先把 ManualConfirm 的订单/流水/settle 后端闭环做稳。
- `RechargeOrder.expired` 若没有定时任务和明确业务规则，本期可先不做自动过期，只保留 `pending/cancelled/paid`。

## 一句话总体判断

计划不能直接照着干；它的阶段划分合理，但最大的单点风险是 **kiosk 付费链路如果落成本地扣费 + 前端 nonce 幂等，会同时破坏服务端权威和资产一致性**。先补云端 billing、服务端 rated 门控、扣费幂等/退款持久化，再进入 UI 和充值模块会更稳。
