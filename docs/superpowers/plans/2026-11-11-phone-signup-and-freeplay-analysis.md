# 手机号注册赠额与自由对弈付费分析 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development. Steps use checkbox syntax for tracking. 计划由独立 Astra Max 最多两轮审核；按独立切片实施及规格、质量核验，最终独立 Astra Max 代码和代表性真实页面审核。只部署 TEST、PROD；本次不连接、升级或重启 RK3562，保留明日设备交接。

**Goal:** 新手机号验证注册只赠 50 显示积分；恢复自由对弈中有额度用户的普通 500 visits 分析，正确计费且不开放旧免费旁路。

**Architecture:** 复用现有账本、会员优先与钱包回退、报价、幂等 position operation 及 `usePaidPosition`。自由对弈结果只投影到当前账号/局面的私有 React 状态。注册将手机号验证消费、建号、唯一赠额和账本改为同一事务；短信服务商与已批准模板尚待用户提供，未就绪不得以固定码、假发送或只填手机号冒充验证。

**Tech Stack:** 现有 FastAPI、SQLAlchemy、PostgreSQL、React、Vitest、Playwright、11 语 gettext；复用服务器配置保留型发布工具，不引入新的支付/钱包、Redis 或新部署平台。

## 权威输入、范围及前置

- 用户 2026-11-11 明确授权开发及两云发布；RK3562 明天再部署，本次严格不触设备。
- 独立工作树沿用 `/Users/fan/Repositories/katrain-membership-recharge` / `feature/membership-recharge`，已从旧 `7d1b52d06` 快进至发布 develop `c6a48d2d7da4d350f4bc0bd82c2f695e58266ce2`。保留其他人的棋盘、USB、字体等改动。
- 显示 1 积分等于内部 100 credits；新 50 积分必须为 **5000**，不是 50。当前注册源码默认 0，历史账号/SQL 默认有 10000；需部署前只读核实实际版本和赠额设置，不依据已有 100 积分推断当前注册行为。
- 不改既有用户、充值、订单、会员期或余额，不追扣旧赠额，不为旧用户补发新赠额。
- 默认延续旧账号用户名/密码登录。新手机号是私有认证身份，不用完整手机号作为公开昵称/用户名，不加入在线用户和棋谱等公开 DTO。
- 已向用户询问本站短信提供商、批准签名/模板及安全配置位置；这是注册切片的外部依赖，不阻塞分析切片。提供商确定后补齐精确配置/适配任务再实施相应网络路径，真实短信验收需要用户提供测试号码。绝不把星阵登录验证码用于本站身份核验。
- 业务设计沿用 39/99/199、会员本期与本周都足够则整次会员，否则整次现有钱包；不新增每日上限/拆分收费/自动充值。保留 enabled/live、8 个微信字段及只读秘密挂载、Free0、Max 可售和全部运行资源。

## 已确认根因

1. 会员模式为防止未付费读取，将共享 WS/state 的 `analysis_delivered` 设为 false。Galaxy/Kiosk 将该字段误作“未登录”，因此全部置灰；自由对弈页面没有接上付费 position 操作。
2. Kiosk 支招还依赖 `physicalPlay`，普通浏览器会被误禁。旧 `API.hint` 与 `API.analyzeCurrent` 被后端 guard 拒绝是正确的，不重新开放。
3. Kiosk 默认开启 score，节点变化 effect 会调用旧自动分析。付费接入必须停止此 effect，不得把它机械替换成自动报价或自动扣费。
4. 正常原生自由 AI 不带 `bot_game`；大厅机器人有该标记，应继续拒绝。ranked、在线公平限制、非参与者和未结算 ranked 等既有规则保持。

## Chunk 1：自由对弈 500 visits 分析闭环

### Task A1：固定最小契约与有额度页面行为

**Files:** `katrain/web/ui/src/features/analysis/usePaidPosition.ts`、`hooks/useResearchSession.ts`（参照，不为本任务重构）、`galaxy/pages/GamePage.tsx`、`kiosk/pages/GamePage.tsx`、`galaxy/components/game/RightSidebarPanel.tsx`、`kiosk/components/game/GameControlPanel.tsx`。

- [x] 分开真实登录/参与者资格与“共享结果不交付”。已登录、原生 free、`analysis_allowed` 可通过新付费入口；无主/他人会话仍由服务端拒绝，按钮不可直接用 `analysisRequiresLogin=false` 一刀切放行。
- [x] 复用当前页面按钮、研究页已发布的报价确认框和视觉，不新增页面设计或自动订阅。对用户主动的支招、领地、当前评估请求使用 `input:{session_id, expected_position_key}`、`profile:'normal'`。
- [x] 支招、领地和当前评估共用一个结果；同一局面切换视图不重复创建 operation、扣费或开 GPU。未分析历史点留空，不自动补买整局图表。
- [x] 实现前用隔离前端数据展示一个真实尺寸 Galaxy 与 Kiosk 交互预览，核对既有按钮、报价来源/上限、失败/余额不足和结果，不做无关布局设计或截图矩阵。仅用本机 Fixture，不写生产业务数据；由独立 Astra 对照审核现有视觉，Fixture 不进入产品发布。

### Task A2：服务端锁定对局普通强度（可与 A3 在契约稳定后并行）

**Files:** `katrain/web/api/v1/endpoints/paid_analysis.py:_position_input`、`api/v1/endpoints/billing.py:BillingQuoteRequest`、`core/paid_analysis.py:session_position_sgf`、`interface.py:get_state`、`web/models.py`、前端 GameState/quote/position DTO；测试扩展 `tests/web_ui/test_paid_analysis_guards.py` 和现有 membership position/quote API 测试。

- [x] 先写隔离失败用例：play session 的 quote 和 execute 都拒绝 advanced；normal 允许且真实 client 调用参数固定 `max_visits=500`，响应须满足现有最低 visits/模型/局面校验。
- [x] 选定窄的 `expected_position_key` 契约：完整当前路径 SGF 经现有 `canonical_analysis_input(sgf,"position","normal")["fingerprint"]` 得出 opaque key；在发送盘面字段的同一快照中带给客户端。不能从 GameState stones/history 反推 SGF，它们缺失已被提掉的摆子和各节点 AB/AW/AE/PL。仅 play 付费边界要求此 key，研究会话兼容原契约。
- [x] 状态帧的盘面、当前节点和 key 必须在实际落子/导航使用的 `runtime.ai_ladder_commit_lock`（RLock）下共同生成；请求在同一实际变更锁内校验 key/play/normal 并捕获不可变 SGF，沿用既有锁顺序。不能只锁没有覆盖 AI 写入的 `session.lock`，也不持锁跨 DB/await。缺失/变更 key 在预扣/引擎前返回明确 `position_changed`；不支持的超长局面 key 为空、分析不可用，不令整个状态接口失败。不新增通用会话版本基础设施。
- [x] 在 quote/execute 共用 `_position_input` 会话接缝检查 `session.mode`：play 只允许 normal；research 会话和研究 SGF 的已有 advanced 能力保持。不能只隐藏前端选项，也不降低报告高级强度。
- [x] 加两例：服务端已走下一手而客户端 WS 仍旧时 quote 拒绝；报价后换手再确认 execute 拒绝。均断言零 reservation、零扣费、零 GPU。校验/捕获后再换手可按既有授权结算，UI 丢弃旧投影，不新造退款规则。
- [x] 保留 session participant、完整 SGF/规则/贴目/摆子绑定、500 手上限、ranked/大厅 bot/反作弊 lease。拒绝请求不得预扣、调用引擎或写结果。
- [x] 复用现有 operation 并发、幂等、缓存、退款；不另造收费接口或重写账务。用已有隔离 PostgreSQL 测试补足本次会员优先、钱包不足、重试扣一次及失败退原来源的接缝。

### Task A3：前端接上付费请求与私有结果

**Files:** 两个 `GamePage.tsx`、必要的共享私有投影 helper/测试；现有 `usePaidPosition.test.tsx`、Galaxy GamePage tests、Kiosk GamePage tests。

- [x] 先写页面失败用例：authenticated free + `analysis_delivered=false` 仍能主动请求；未登录/不允许分析保持限制。Kiosk 浏览器不因无实体盘而禁用普通支招。
- [x] 复用 `usePaidPosition` 的 scope、幂等与旧响应丢弃；snapshot 包含会话、服务端发来的 expected_position_key、节点、完整路径、盘面、规则/贴目；quote 和 execute 都发送同一 key，报价返回 fingerprint 必须匹配。换手、分支、账号、会话或卸载即丢弃旧投影，不自动报价/扣费。
- [x] 对 `position_changed` 明确清掉原报价/开关并等待下一次主动点击，不沿用 hook 对所有409自动重新quote的通用分支去悄悄换局面。仅报价过期等仍可按原幂等规则提示重试。
- [x] receipt 的 ownership/moves/rootInfo 只投影为本组件所需盘面标记和评估；不写回 `setGameState`、共享 WS、服务端节点缓存或广播给对手。投影可小范围复用研究页实现，不重构整套会话架构。
- [x] 首次点击获取报价，用户确认后执行；已拥有同局面结果切视图即时复用。双击一次、取消不消费、超时/失败展示真实回执，余额不足可引导会员/充值但不自动下单。
- [x] 移除对局节点变化的旧自动 analyze effect，保留正常 AI 对手落子。图表只展示已实际获得的评估，不把开关默认 true 当作购买授权。
- [x] 保留已有 Kiosk 支招面板/合法显示语义。实体灯反馈的动态效果留明日真实设备验收，不能将云浏览器结果写成实机灯已通过。
- [x] 新用户文案使用 `.agents/skills/katrain-i18n-expert` 补齐全部 11 语；不硬编码中文，不重新翻译无关目录。

### Task A4：切片验收

- [x] 执行相关 hook/页面测试及后端 session/quote/operation 聚焦用例，明确隔离 `KATRAIN_DATABASE_URL`，不得回落本机真实 DB；PG用例另需真实设置 `TEST_DATABASE_URL`，沿用 `membership_test_support.py` 的 loopback `membership_validation*` 数据库与独立TEST marker，不把只设前者称为PG已执行。无 GPU 用已有模拟引擎传输验证，不生成真实付费操作。
- [x] 构建普通和 strict Kiosk，实际浏览器验证新点击→报价→确认→500结果→切视图复用，以及换手不自动消费。金额来自实际测试账本，不用伪造生产余额。
- [x] 独立规格/质量及最终 Astra 代码/代表预览审核，修至通过。只重跑实际改动与最可能回归点，沿用已通过的账务隔离测试，不建立新的全量审计体系。

## Chunk 2：手机号验证注册 + 一次 50 积分（外部依赖待确认）

### Task B1：确定短信服务契约及 UI 最小扩展

**Files:** `core/config.py`、新独立 `core/phone_signup.py`（或同等聚焦服务）、`api/v1/endpoints/auth.py`、`web/models.py`；Galaxy `components/auth/LoginModal.tsx`、旧 `components/RegisterDialog.tsx`、`web/ui/src/api.ts`。

- [ ] 用户确认提供商/支持号码地区、批准签名及验证码模板后，在本计划补齐确切参数与官方文档；秘密只用服务器私有文件配置，不进入前端/聊天/日志/Git。没有真实提供商配置则发送返回明确 unavailable，不产生账户/赠额。
- [ ] 新注册必须有规范化手机号及已验证一次性验证码；保留公开用户名/昵称与密码，旧账号继续可登录。新登录允许私有手机号查找，返回的公开用户仍不含完整手机号。支持地区按提供商确认，不自行宣称全球可发短信。
- [ ] 复用登录窗，新增手机号、验证码及获取按钮；展示成功注册赠50积分，倒计时/发送失败/验证码错误/重复注册明确。先隔离预览一个代表 viewport，再做后端接入；翻译全部11语。

### Task B2：验证与赠额单事务

**Files:** `core/models_db.py`、`core/migrations.py`、`core/auth.py`、`core/phone_signup.py`、`core/config.py`、`auth.py`；现有 signup/auth/billing 测试。

- [ ] 仅增加私有手机号身份/验证时间、有限期验证码挑战和持久一次赠额记录；按最终最小数据模型补加法迁移及唯一索引，相关身份/账本表加入 PROTECTED_TABLES，严禁 drift 重建。
- [ ] 手机验证消费、创建账户、手机号唯一占用、5000 credits 赠额与账本 ref 同一 DB 事务。复用 flush-only 账务原语；不调用现有自行 commit 的 `create_user` + `billing.grant` 两阶段组合。
- [ ] 同手机号最多获赠一次，幂等/并发/网络重试不多发；账号删除不能清掉可重复领赠额的事实。既有用户/余额不更改，不加“全员重置50”迁移。
- [ ] 服务商确定后冻结号码规范化、验证码格式/有效期/错误次数、手机号/IP发送冷却和日预算、可信客户端IP来源，不能留实施者随意决定。验证码错误次数/发送计数需独立持久并发安全，不能因账户事务回滚而归零；发送网络调用不持有用户/账务锁。
- [ ] 验证码只保存带盐/密钥摘要、短有效期、单次消费、错误次数上限；发送按手机号和可信客户端 IP 限频/日预算，注册错误同样限次。优先复用现有 DB，不为此添加 Redis 或通用风控系统。
- [ ] 金额配置明确以内部 credits 装配并验证，默认新规则5000且只在验证注册成功后生效；修掉环境变量不读取问题。不得令通用用户构造、shadow/SSO刷新或导入账号自动获赠。
- [ ] 聚焦测试覆盖未验证/假号、失效/重放、发送失败、限流、同号并发、事务回滚重试、显示50与账本5000、旧余额不变和敏感数据不出公开DTO。

### Task B3：父仓及设备协议兼容

**Files:** `katrain/web/core/remote_client.py`、板端注册代理、父仓 `setup-wizard/app/routers/auth.py`、`app/services/identity.py`、`app/static/js/launcher.js` 及 auth tests。

- [ ] 同步手机号/验证码挑战字段与错误码；父代理不得丢字段，也不得把任意验证码400/409视为“重复账号”再自动login。仅准确 duplicate-account 情况允许既有合法登录行为，认证错误原样返回。
- [ ] 私有手机号登录保留但只作认证别名：云端解析到唯一 canonical public username/UUID 后，JWT subject、板端 shadow、remote client 与 Box bootstrap 只用已验证云 `/me` 的正式身份。不能用 `login_data.username` 原始手机号建 shadow 或公开展示。若旧数字用户名与手机号别名冲突，明确区分登录输入类型并拒绝不确定映射，绝不猜账号。增加两种登录归一到同一账号/shadow、DTO/JWT不含手机号、未知/冲突不误登录的聚焦测试。
- [ ] 真实用户、guest、shadow、刷新 token、Box SSO边界保持。源代码可本机验证和提交，今天不部署 RK，也不要求用户远程登录设备。
- [ ] 配置未准备时不得发布“手机号注册和50赠额已可正式验收”；可以先发布独立分析切片，并列出注册前置缺口。未完成B的默认赠额/环境读取变更不能单独带入原有无验证注册路径；不以展示50宣称账本已到账。未验证号码路径不能替代为手机号格式校验后直接赠额。

## Chunk 3：传统集成及两云发布

- [ ] 独立 Astra Max 计划最多两轮；A 的契约冻结后可先执行，B 的短信/号码范围未确认前只做不依赖该决定的工作。实现各切片规格→质量审核，最终独立 Astra Max 审核至通过。
- [ ] 发布前读取 `.agents/skills/server-deploy`，只读核实两云实际运行 SHA、完整 Config/HostConfig/Env、微信8字段/只读挂载、商业模式及注册赠额；不输出秘密或手机号。
- [ ] 同步最新 develop 到功能分支、解决冲突、聚焦验证、commit/push；合入并推 develop；更新父仓 vendor/katrain，保留其他工作区修改并推 main。
- [ ] 用已审 code-only 机制从实际配置克隆，仅替换完整已发布软件/static/11语；注册若需新配置/显式迁移，展示精确增量并记录只加不删。保留真实收款、预算、账务数据、资源/网络，不重启无关 DB/GPU/Cron。
- [ ] TEST先行，普通浏览器 Galaxy和云Kiosk代表旅程通过后 PROD。使用隔离本机/测试专用账号验证消费；不擅自用真实个人余额跑分析，不代用户微信付款，不用模拟订单冒充正式收款。
- [ ] 最终回执报告测试、准确发布commit/镜像/实际商业设置、短信未具备项与RK次日验收清单；不为纯文档尾提交反复构建。

## 明日 RK3562 交接

记录今日服务器/父仓精确软件、注册协议/模板配置、源代码已准备而设备未更新的事实。明日重新获设备窗口并 fresh capture；保留 enabled/billing=true/Free0、16z会员drop-in、activation marker、原数据库和支付密钥不上盒边界。核对本人登录、注册代理、云赠额、自由对弈500visits/退款、支招/领地及灯反馈；今天不声称这些实机检查通过。
