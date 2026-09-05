# galaxy 支付与会员体系 —— 需求与既定裁决

分支 `feature/galaxy-payment`，worktree `/Users/fan/Repositories/katrain-galaxy-payment`。
写于 2026-09-05。上游 `develop` @ 30071a5d。

本文件是**输入**，不是计划。计划见同目录 `plan.md`。
凡本文件写"Fan 已裁定"的，实现时不得推翻；凡写"未定"的，需要决策而不是默认。

---

## 0. Fan 的裁决（按时间顺序，全部有效）

| # | 裁决 | 出处 |
|---|---|---|
| D1 | 收费模式是**会员制**，分等级，额度按**日/周/月**重置 | 2026-09-03 |
| D2 | **每周免费送一次复盘**的消耗量 | 2026-09-03 |
| D3 | 免费额度**送给所有注册用户**（含未付费），但**注册必须同时加手机绑定 + 限流** | 2026-09-04 |
| D4 | **直播分析不定价**——那是网站自发的分析，不向用户收费 | 2026-09-04 |
| D5 | **先修 `SECRET_KEY`**，再做手机绑定 | 2026-09-05 |
| D6 | **按计算量计费，不按盘数计费**。100 手认输的棋和 300 手的棋不能收一样的钱 | 2026-09-05 |
| D7 | **所有国家的手机号都要能绑**，区别只是国家区号前缀 | 2026-09-05 |
| D8 | 分析模型**不做 b28→b40**（3 倍算力换 390 Elo）。要升级则评估 transformer `tf3-b11c768`；上线前必须在生产 V100 上实测 `katago benchmark` | 2026-09-04 |

### 早前仍然有效的裁决（2026-06-07，`sbc-pure-play-remote-analysis/requirements.md` §7）
- **非目标**：双层「星币 + 道具次数」模型。用单池积分 + 单价替代。
  - 本 track 的做法：**额度桶是计数器，不是货币**。绝大多数消费不写 `credit_transactions`；账本仍是单池，只记真金白银。这样既保留"不要两种货币"的实质，又能表达"会过期的额度"——那是可变整数余额诚实表达不了的。

---

## 1. 已核实的仓库事实（实现时可直接依赖；发现不符请当场提出）

### 1.1 认证
- `katrain/web/core/config.py:38` `SECRET_KEY: str = "katrain-secret-key-change-this-in-production"`；`:115` 环境回退同一字面量。
- `KATRAIN_SECRET_KEY` **可以**覆盖，但 `docker-compose.yml` **没有传** ⇒ **生产跑的就是仓库里的字面量**。
- `katrain/config.json` 已提交进仓库，但它只影响 `DATABASE_URL`，不含 SECRET_KEY。
- 用它签发/校验 JWT 的四处：`core/auth.py:37,48`（encode）、`endpoints/auth.py:111,296`（decode）。
- token 载荷只有 `sub` / `exp` / `type`（+ 可选 `box_generation`），**没有 jti、没有版本位** ⇒ 换密钥 = 全站登出一次。
- access 7 天、refresh 90 天（`config.py:40-41`）。
- `endpoints/auth.py:321` `POST /auth/register` 收 `{username, password}`，无邮箱、无手机、无验证码、**无限流**。
- `UserRepository` 是 ABC，`create_user(self, username: str, hashed_password: str)`（`core/auth.py:58`，实现 :190）——加参数要同时改基类、实现和测试替身。
- `models_db.py:73-74` `username` 与 `hashed_password` 均 `nullable=False`。
- `core/auth.py:323` `_to_dict` 是**显式白名单**（id/uuid/username/hashed_password/rank/credits/is_admin/avatar_url/created_at）——新增列不会自动泄漏，但 `get_user_from_token` 只读这里，新列要用必须显式加。
- `endpoints/users.py:78` `/users/online` 与 `endpoints/games.py:28` `/games/active/multiplayer`（**至今未鉴权**）会把 `username` 明文吐给任意调用者。
- `strict_box_sso_enabled()` 为真时 `/register` 直接 403；登录走 `sb_token`（127.0.0.1 域 cookie）。
- Board 模式：`remote_client` 非空时 login/register **转发云端**；`remote_client.py:145 login` / `:157 register(username, password)` 是**逐方法**写的，不是通用代理。

### 1.2 计费
- `core/billing.py` 是服务端权威整数账本：`reserve` / `commit` / `refund` / `grant` / `spend` / `redeem` / `settle_order` / `reconcile_stale_reservations`。
- 原子性靠单条条件 UPDATE：`UPDATE users SET credits = credits - :amt WHERE id = :uid AND credits >= :amt`（SQLite + PG 双通）。
- `credit_transactions.ref_id` `String(160)` UNIQUE ⇒ 幂等键。
- **`reserve` / `spend` / `commit` / `refund` 的非测试调用者是 0 个**。`from ... import billing` 只有两处：`endpoints/billing.py:22` 与 `server.py:222`。**今天没有任何代码会花积分。**
- `config.py:53` `BILLING_PRICES = {"territory": 10, "hints": 10, "variations": 10}` —— 只被 `/billing/prices` 原样回显，**没有 `report` 这一项**。
- `config.py:59` `BILLING_FREE_GRANT: int = 10000` —— **全仓零引用，是死常量**。
- 新账号的赠额来自**两处列默认值**，都不走账本：
  - `models_db.py:78` `credits = Column(Integer, default=10000, nullable=False)`
  - `models.py:183` pydantic `User.credits: int = 10000` ← **容易漏改的第二处**
- ⚠️ `billing.py:168-203` `grant()` 的 `IntegrityError` 补偿分支**会多扣一次**：`db.rollback()` 已撤销那次 `+amt`，之后又执行了一次 `-amt`，净效果 `-amt`。顺序重放（`_existing_tx` 命中直接 return）那条路是对的。**上线前必须修**。

### 1.3 复盘
- `endpoints/reports.py:18` `REPORT_VISITS = {"normal": 500, "deep": 2000}`（每手的 visits）。
- `ReportTask` 行上已有 `total_moves` / `analyzed_moves` / `requested_visits` ⇒ **计算量计费的三个操作数都是现成的**。
- `reports.py:211` `if not task.force:` —— force 绕过去重。
- 盒子上复盘走 `_dispatch_remote_only`（云端），扣费落在云端，与账本权威一致。

### 1.4 基础设施
- **没有 Redis**。`docker-compose.yml` 只有 minio / minio-setup / katrain-web / katrain-cron；PG 是外部的。
- **没有 Alembic 迁移链**（`requirements-web.txt` 里**装着** `alembic>=1.13.0`，但仓里没有 alembic 目录/env.py——别去跑 `alembic revision`）。迁移走 `core/migrations.py` 手写、非破坏性 ADD COLUMN / CREATE INDEX，SQLite + PG 双兼容。
- `uvicorn.run(app, ...)` **无 workers 参数 ⇒ 单进程**。
- 开发跑 SQLite、生产跑 PG。
- `migrations.py:33` `PROTECTED_TABLES` 只含账本与升降级表，**`users` 不在其中**；`core/auth.py:155-162` 的漂移判据只比列名集合。
- **仓库里没有任何短信 SDK**（无 aliyun / tencentcloud / alibabacloud 依赖）。
- `Dockerfile.cron` 只 `COPY katrain/cron/` ⇒ 跨目录 import 与未列进 requirements 的第三方只在容器里炸。

### 1.5 前端
- 三个登录面**全是 MUI**：`components/LoginDialog.tsx`(88) 与 `RegisterDialog.tsx`(105)（共享领地）、`galaxy/components/auth/LoginModal.tsx`(133)、`kiosk/pages/LoginPage.tsx`(166)。
- `context/AuthContext.tsx:17` `login: (username, password) => Promise<void>`；`:92` strict-box 客户端拦截；`:103` 把错误折成 `Error('Login failed')`；`login` 是**裸 fetch**，不走 `API.login`。
- `LoginDialog.tsx:35` 不走 context，直接 `API.login`。
- `ZenModeApp.tsx:559/564` 在用 `LoginDialog`/`RegisterDialog`，而 `AppRouter.tsx:46` 把 `ZenModeApp` 挂在 `/*` 兜底 ⇒ **那是 modelstella.com 的大门，不是边角**。
- 已有可复用的手机验证码交互：`kiosk/pages/PlatformConnectPage.tsx`（`smsBusy`/`smsLeft`、60s 倒计时、倒计时禁点、没填号不发请求、"六位数字 · 60 秒内有效"）+ 配套测试。**但那是登录星阵的，短信由星阵发**；且它在 `src/kiosk/` 下，共享领地按契约不能反向 import。
- kiosk 登录页在 `KioskLayout` **外面**（`KioskApp.tsx:78`），`RotationWrapper` 是 `position:fixed; overflow:hidden` ⇒ `smartkeyboard.js` 的 `paddingBottom` + `scrollIntoView` 在这一页是**空操作**。软键盘上缘：英文 412、中文候选条 354。当前卡片底边 428 > 412，**已经被挡**。
- 构建隔离契约见仓库 CLAUDE.md：共享领地不得 import `src/kiosk/`、`src/galaxy/`、`src/pages/`；eslint 强制；改共享件 `npm run build` 与 `npm run build:kiosk-2d` 都要绿。
- `npx tsc --noEmit` 检查 **0 个文件**（根 tsconfig 是 `files: []` + references）；真正的是 `tsc -b`，且 `*.test.ts` 被 exclude。

---

## 2. 本 track 的范围

### 2.1 必须做（按依赖顺序）

**P0 — `SECRET_KEY`（D5，其余一切的前置）**
今天任何人都能拿仓库里的字面量自签一个 `{"sub": "<任意用户名>", "type": "access"}` 冒充任意用户（含 `admin`）。在这个前提下做手机绑定 = 给一扇没锁的门装门铃。
- 生产必须从环境注入；**拿不到就拒绝启动**（fail-fast，不许静默回退到字面量）。
- 换密钥 = 全站登出一次。需要发布顺序设计（见 plan）。
- 顺带评估 token 里加版本位 `tv`（缺失当 0，否则上线当天全站登出）；若加，`tv` 必须进 `_to_dict`，且 strict-box 的 `box_generation` 路径也要带。

**P1 — 按计算量计费（D6）**
计价单位是**实际算力**，不是"一局"。三个操作数已在 `ReportTask` 行上：
```
预估成本 = total_moves × requested_visits × model_cost_factor
实际成本 = analyzed_moves × requested_visits × model_cost_factor
```
- 用**现成的** `billing.reserve`（创建任务时按 `total_moves` 预扣）→ `billing.commit`（完成时按 `analyzed_moves` 结算）→ `billing.refund`（失败时退还）。这正是这三个零调用者函数的设计用途。
- 100 手认输的棋结算 ~1/3 于 300 手的棋 —— D6 由此成立。
- `BILLING_PRICES` 要加计价参数（单位价格 / 每 N visits 的价格），**不是** `report: N` 这种按盘定价。
- 用户看到的是"约 N 局标准复盘"这种可理解的量，但**必须诚实标注那是估算**；精确值同时可见。
- `ANALYSIS_MAX_VISITS` 与 `ANALYSIS_PREEMPT_THRESHOLD` **都是 500**，动一个必须同时看另一个。

**P2 — 额度桶（D1/D2）**
- 惰性周期键（`D:YYYY-MM-DD` / `W:YYYY-Www` / `P:<subscription_period_id>`，Asia/Shanghai），**不需要 cron 重置任务**。
- 原子扣减：`UPDATE quota_buckets SET used = used + :n WHERE ... AND used + :n <= allowance`。
- 限额快照存在桶行上（改套餐不影响已开桶）。
- 不滚存。用尽的行为：深度复盘硬拦，标准复盘降级到夜间低峰队列。

**P3 — 手机绑定与验证码登录（D3/D7）**
- `users` 加手机号列。⚠️ `ALTER TABLE users ADD COLUMN phone VARCHAR UNIQUE` 在 **SQLite 上直接报错**，必须拆成 ADD COLUMN（无约束）+ 独立 `CREATE UNIQUE INDEX`。
- 验证码存 PG/SQLite 表（无 Redis），只存 hash，一次性消费。
- **发新码时作废该号全部未消费的旧码**；校验只认最新一条。否则 60s 可重发 + 5min TTL ⇒ 同号可并存 5 条未消费码，`attempts` 挂在行上 = 防线漏。
- **`send-code` 不能鉴权**（注册时还没账号）⇒ 全站第一个"不鉴权还花钱"的端点。
- **verify 不收手机号**，收 `challenge_id`（不可猜串），失败计数挂在 challenge 上。否则任何人可以拿别人的号打满失败次数，**零成本远程锁死任意用户的登录，且受害者手机上一条短信都不会响**。
- 限流键必须是 `(phone, purpose)` + `client_ip` 两组同时生效。**前端 60 秒倒计时不是闸**，服务端必须自己算冷却。
- **全站日总量硬闸**（如 `SMS_DAILY_CAP`，env 常数，不要自适应式子——被打的那天会抬高均值形成棘轮）。pending 行要计入分母。
- 供应商调用必须 `async` + `httpx.AsyncClient(timeout≈3s)`。单进程下同步阻塞会拖垮整站。
- **国际号（D7）**：E.164 存储，前端国家区号选择器。国内通道不发国际号，国际短信是独立产品、单价差一个量级 ⇒ 国际号的限流与日额度要单独配。
- 测试环境不发真短信：`SMS_PROVIDER=console|<vendor>`，console 把码写日志；**生产未显式设置就 fail-fast**（否则生产静默跑 console，用户永远收不到码而接口一路返回成功 = 伪装成功）。

**P4 — 关掉刷号的旧路**

> ⚠️ **2026-09-05 终审补正（重要，别踩）**：本节下面写的两个选项成文于第 1 稿，
> 那时每周免费额度是**发积分**（进账本）。第 2 稿把它改成**不滚存的周额度桶**
> （计数器，不进账本）之后，**刷号那扇门就从账本挪到了计数器上**，而 P4 的措辞
> 停在账本时代。
>
> 具体后果：免费复盘桶的键是 `user_id`（`quota._ensure_bucket`），不是手机号；
> 而 `/auth/register` 至今无验证码、无限流。⇒ **注册 N 个用户名 = 每周 N 份免费复盘
> = N × 约 125 credits 的 GPU**。
>
> 所以选项 (b)「密码注册保留但 0 赠品」**只堵住了积分那一半**，堵不住免费复盘那一半。
> `BILLING_ENFORCED` 开闸的前置里那条「P3 手机绑定 + 注册限流」因此是**硬前置**，
> 不是"尽量"。开闸时若 P3 未落地，必须同时把 `FREE_WEEKLY_REPORTS` 配成 0。
只要 `/auth/register`（无验证码无限流）开着，"免费额度按手机号分桶"在事实上不成立：注册 100 个用户名 = 100 份列默认赠额，一条短信都不用发。二选一并写进计划：
- (a) 注册收敛成手机号一条路（`/register` 403/410，前端撤入口）；或
- (b) 密码注册保留但 **0 赠品**。
同时：`models_db.py:78` 与 `models.py:183` 两处 `10000` 都要改，赠额改由 `billing.grant` 发放。

**P5 — 合规页脚（收费前必须上线）**
- ICP 号是**法定义务**：292号令第十二条（主页显著位置，罚则第二十二条 5000–50000）+ 33号令第十三条（主页底部中央位置 + 链接备案系统，罚则第二十五条**责令限期改正、逾期不改正才罚** 5000–10000）。链接指向 `beian.miit.gov.cn`。
- 北京挂**网站备案号**带序号（`京ICP备xxxxxxxx号-N`）。（广东才是挂主体号不带序号，与我们无关。）
- 公安号挂标**查不到法条依据**（通读公安部33号令全25条无此要求），只是平台操作要求 ⇒ 挂，但文案不得写"根据《XX办法》第X条"。链接 `beian.mps.gov.cn/#/query/webSearch?code=<14位纯数字>`。
- 挂载点难题：`AppRouter.tsx:46` 把 `/` 渲染成全屏 `ZenModeApp`，`MainLayout` 是 `100dvh; overflow:hidden` ⇒ 直接加页脚会吃掉棋盘高度。做法：只在非棋盘页渲染 + 新增落地页。
- 号码本身待 Fan 提供（仓库里零记录）。实现用占位常量 + 单一真源，拿到号只改一处。

### 2.2 明确不做（本轮）

- 自动续费 / 连续包月。支付宝「商家扣款」要注册资本 ≥2000万 + ≥300 月付用户；微信阈值未核实。⇒ **定价必须按一次性购买 + 到期提醒 + 手动续费设计**，折扣挂在季/年而不是"连续包月 8 折"。
- 双层货币（见 §0 早前裁决）。
- `retired_phones` 表 + 90 天清理任务（注销时 `phone_e164` 置 NULL、`phone_hash` 留在 users 行上即可同时满足"明文删除"与"赠品不复发"）。
- 独立的 `PhoneBinding` 表（本轮唯一写入者是 bind，唯一读者没做；换绑历史已编码在 `credit_transactions.ref_id` 里）。
- 新增 `SMS_PEPPER` / `PHONE_BUCKET_PEPPER` 两个密钥（给一个连 `SECRET_KEY` 都还没覆盖的部署新增两个不可轮换的密钥是净负收益；要 HMAC 就复用 `SECRET_KEY`）。
- 虚商号段黑名单 / `phone_risk_tag`（保护的是每周几毛钱的赠品）。
- 图形验证码（天御 / 验证码2.0）——先上服务端闸，真被刷了再说。
- 短信状态回调端点（新的免鉴权攻击面；几百条/日用同步返回码 + 日志足够）。
- 备用短信服务商（签名 6 个月无发送记录会失效 ⇒ 备份签名按定义没流量 ⇒ 需要它那天它恰好是冷的）。
- 自适应熔断式子、`cost_fen` 逐条成本列、日志脱敏 CI 闸、`ctid`/`rowid` 双方言删除、`CheckConstraint("attempts >= 0")`、`PATCH /users/me` 改名。
- 直播分析的定价（D4）。其成本控制是运维旋钮，不属于本 track。
- 分析模型从 b28 换 b40（D8）。

### 2.3 未定 —— 需要决策，不得默认

| # | 问题 | 为什么不能默认 |
|---|---|---|
| U1 | 存量用户（无手机号）怎么办：强制补绑？宽限期？不绑就没有每周额度？ | `ref_id` 是**全局**唯一 ⇒ `weekly:None:2026-W36` 会让**第一个用户领到、其余全部 IntegrityError**，静默不发。这不是闸失效，是闸把所有人合并成同一个人。`grant` 调用点必须有 `if phone is None:` 显式分支。 |
| U2 | Box SSO（strict）用户身上没有手机号，"免费额度按手机分桶"在盒子上不成立 | 产品裁决点 |
| U3 | 国际号的短信通道选哪家、单价与日额度怎么配（D7 之后新增） | 成本量级不同 |
| U4 | 经营许可证：B25 还是 B21；"卖分析额度"是否构成经营性 | 无证经营的罚则是《互联网信息服务管理办法》**第十九条**：责令限期改正、没收违法所得、3–5 倍罚款；无违法所得或不足 5 万处 **10 万–100 万**；**情节严重责令关闭网站**。已另出 prompt 交由专门调研。 |
| U5 | 用手机号重置密码要不要本轮做 | 上线第一天客服就会被问 |

---

## 3. 硬性工程约束（违反即返工）

1. **状态诚实**：加载/错误/空态/重试不得伪装成成功。短信"已提交"≠"已送达"，文案不得写"已发送到您的手机"且必须有"收不到？"的出路。
2. **构建隔离**：共享领地不得 import `src/kiosk/`、`src/galaxy/`、`src/pages/`。改共享件 `npm run build` 与 `npm run build:kiosk-2d` 都要绿。
3. **迁移双兼容**：SQLite + PG。唯一约束走独立 CREATE UNIQUE INDEX，不走 ADD COLUMN UNIQUE。
4. **测试分层**：跑 SQLite 的单测证明不了 PG 的行锁/时区/跨 schema 外键——这类断言要 skip 并写明"只能在 PG 上证"，**不许改绿**。布局结论只认真浏览器，jsdom 无权作证。
5. **i18n**：后端只返回 `code`，文案全在前端 i18n 表；`t(key, '中文默认')`；11 种语言（cn≠zh）。
6. **部署顺序**：功能改动必须先部署 home-ubuntu（go.sailorvoyage.top，测试）再上 ucloud-v100（modelstella.com，生产）。
7. **生产代码不得残留模拟业务数据**；Fixture 必须隔离并在创建时写明删除条件。
8. **不要跑 `alembic revision`**（没有 env.py）；迁移只走 `core/migrations.py`。
9. **别用 `git stash`**：本仓 13 个 worktree 共用一条 stash 栈。
