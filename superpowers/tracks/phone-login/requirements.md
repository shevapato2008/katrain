# P3 · 手机绑定与验证码登录 —— 需求

分支 `feature/phone-login`，基于 develop `f2fc3c01`（galaxy 计费第一切片已上线两台机器）。
2026-09-07 开工。上一轮的 P3 条款在 `superpowers/tracks/galaxy-payment/requirements.md` §2.1，
**那份仍然有效，但 U1 那段论证已过期**（见本目录 `preflight-findings.md` F11）。

## 0. 为什么做这一轮

三条理由，任意一条单独成立：

1. **法定义务。** 现行《网络安全法》第二十六条（修正前第二十四条）：为用户提供
   **信息发布、即时通讯**等服务时应当要求用户提供真实身份信息。本站有对局聊天与直播评论。
   ⇒ 手机实名不是"为了计费额外加的"，是补一个已经欠着的合规项。
2. **`BILLING_ENFORCED` 开闸的硬前置。** 每周免费复盘的额度桶按 `user_id` 分
   （`quota.try_consume(db, current_user.id, "free_report:week", …)`），而 `/auth/register`
   至今无验证码无限流 ⇒ 注册 N 个用户名 = 每周 N 份免费复盘 ≈ N×125 credits 的 GPU。
   开闸时若本轮未落地，必须同时把 `FREE_WEEKLY_REPORTS` 配成 0。
3. **产品**：Fan 定的"所有国家的手机号都要支持"。

## 1. 本轮范围

### 1.1 必须做
- `users` 加手机号列（E.164）+ 独立唯一索引。
- 验证码表：只存 hash，一次性消费，发新码作废该号全部未消费旧码。
- 三个端点：发码 / 手机号登录（含首次即注册）/ 已登录用户绑定手机。
- 两组限流同时生效：`(phone, purpose)` 与 `client_ip`；**冷却从库里算**，不靠进程内存。
- 全站日总量硬闸 `SMS_DAILY_CAP`（env 常数，pending 行计入分母），国内与国际**分开配**。
- 供应商抽象：`SMS_PROVIDER=console|aliyun`；**生产未显式配置就 fail-fast**。
- 前端：登录框加"手机号 + 验证码"第三种模式 + 国家区号选择器；隐私政策与独立同意项。

### 1.2 明确不做（沿用上一轮 §2.2，并新增两条）
沿用：`retired_phones` 表 + 90 天清理任务、独立 `PhoneBinding` 表、新增 `SMS_PEPPER` /
`PHONE_BUCKET_PEPPER`（要 HMAC 就复用 `SECRET_KEY`）、虚商号段黑名单、图形验证码、
短信状态回调端点、备用短信服务商、自适应熔断式子。

**本轮新增的两条"不做"：**
- **不新增任何 Python 依赖**（依据见 F8：生产的依赖清单是 release 分支独有的
  hash-pinned `requirements-web-runtime.txt`，只往 `requirements-web.txt` 加包
  ⇒ 测试正常、生产镜像也建得出来、**只在生产运行时 ImportError**）。
  ⇒ E.164 手写归一化器（我们只需要"存成 E.164"+"是不是中国大陆号"，不需要号段库）；
  阿里云用 `hmac`/`hashlib`/`urllib.parse`（标准库）+ 已有的 `httpx` 自签
  —— 这同时也是更对的做法，因为官方 SDK 是同步的而需求要求 async。
- **不开真短信通道**：签名实名制报备在运营商侧要 5–10 个工作日且不承诺时效。
  本轮把通道抽象与 `console` 提供方做完并测透，`aliyun` 提供方按文档实现但
  **不作为本轮验收项**（拿不到凭据就验不了，验不了就不许声称它能用）。

## 2. 硬性约束（违反即返工）

1. **状态必须诚实。** `console` 提供方在生产环境下**不许静默生效** —— 生产未显式设置
   供应商就 fail-fast 拒绝启动/拒绝该端点，绝不能"接口一路返回成功而用户永远收不到码"。
2. **`verify` 不收手机号，收 `challenge_id`**（不可猜串），失败计数挂在 challenge 上。
   否则任何人可以拿别人的号打满失败次数，**零成本远程锁死任意用户的登录，
   且受害者手机上一条短信都不会响**。
3. **`send-code` 不鉴权**（注册时还没账号）⇒ 这是全站第一个"不鉴权还花钱"的端点。
   它的每一条防线都要有对应的红用例。
4. **per-IP 限流不得用 `request.client.host`**（F10：生产上它对所有用户恒为 `172.20.0.1`）。
   用应用自解析 XFF 取右起第 N 跳，`TRUSTED_PROXY_HOPS` 默认 1。
   **必须有一条断言：两个不同客户端 IP 拿到的桶不是同一个** —— 只断言"限流会拦"
   的用例对这个缺陷免疫（它在一个桶的世界里也是绿的）。
5. **`verify_password` 必须收口**：遇到无法识别的 hash 返回 False 而不是抛
   `UnknownHashError`（F3/F9）。否则纯手机用户被打 `/auth/login` 会 500 而不是 401，
   而 500 与 401 可区分"此人存在且是纯手机用户"。这条顺带拆掉影子用户那颗已埋的雷。
6. **三个新端点每一个都要显式回答盒子问题**（F6）：strict 盒子上是不是 403？
   board 模式是转发给云端还是 503 `need_online`？漏掉任一个，盒子上的表现是
   "在本地库里找不到人"这种查不出原因的失败。
7. **迁移走既有机制**：模型上声明列（列上**不写** `unique=True`）+ `__table_args__` 里
   声明 `Index(..., unique=True)`。`add_missing_columns` 拼的 DDL 不带 UNIQUE、
   `create_missing_indexes` 用 `index.create()` 保留 unique ⇒ 两个方言都自动迁移，
   零手写 DDL（F1/F2）。
8. **i18n 默认值写中文**，不写英文（现有 `LoginModal.tsx` 写的是英文默认值，是反例）。
9. 供应商调用 `async` + `httpx.AsyncClient(timeout≈3s)`。单进程下同步阻塞会拖垮整站。
10. 阿里云侧的已知事实（已查证，实现时按这个来）：签名可用【万智星】（企业全称子集），
    **不能**用【智星盒】；国际/港澳台短信不需要资质、不需要签名和模板；
    官方流控上限 同一签名对同号 1条/分钟、5条/小时、10条/天，全平台同号 40条/天
    —— **我们自己的限流必须比这更严**，否则用户先撞的是运营商的墙、
    拿到的是一个我们无法解释的失败。

## 3. 裁决（两个独立 opus agent 各自裁完，本节是交叉核对后的**最终裁定**）

两份裁决书在 U1 机制与"注册是否强制手机"两条上**判反**。以下每条都注明采信谁、为什么，
凡涉及代码事实的都由本 session 亲自读过源码核实（行号见括注）。

### D-U1 存量账号：不强制补绑、不设宽限期

**没绑手机 = 没有每周免费复盘；绑定成功当场生效，包括当周。** 存量账号（生产 9 + 测试 14）
`phone_e164` 留 NULL，不造占位号（F1：SQLite 唯一索引不管 NULL），不做数据迁移。

**零用户可见回归**（核实 `reports.py:276-289`）：`BILLING_ENFORCED` 默认 False 时整段早退去建
pending 任务，**根本不碰 quota** ⇒ 今天没有任何人拥有这个福利，拿走它不回归任何人。

**分桶键永远是 `user_id`，永不改成手机号。** 反刷号性质由两条合成：`phone_e164` 唯一索引保证
「一号一账号」+ 桶键 `user_id` 保证「一账号一份额度」。把手机号塞进桶键是同一件事的第二种表达，
只多引入 NULL 这个第三状态。

### D-U1-M 机制：**在触碰 quota 之前短路**（采信 p3-decider，不采信 p3-decider-2）

亲自核实 `quota.py:47-77`：`_ensure_bucket` **只在行不存在时**写 `allowance`，行存在就原样返回；
`peek` 的 docstring 明写「限额取桶上的快照」；`try_consume` 的 UPDATE 拿行上的 `allowance` 比。

⇒ 拿 `allowance=0` 去 peek 一个未绑手机的用户，**当周就开出一个 allowance=0 的桶，
该用户当周绑了手机也永远拿不到额度**——"绑定当场生效"当场作废。

两家都看见了这个陷阱（这是交叉核对最有价值的一次命中），但解法不同：

| | 落法 | 代价 |
|---|---|---|
| p3-decider | 未绑手机**不调** `quota.peek` / `try_consume`，桶行不建 | 无 |
| p3-decider-2 | `allowance=(N if phone else 0)`，再加一条绑号后的 `UPDATE quota_buckets SET allowance` | 多一条写进 quota_buckets 的路径 + 并发推理；**且它的重裁稿里把这条 UPDATE 丢了**，只剩表达式 ⇒ 缺陷原样留在里面 |

**采信短路。** 两个调用点都要在触碰 quota **之前**返回：
- `billing.py:106-108` `GET /quota`：不调 `peek`，直接返
  `"free_weekly": {"used":0, "allowance":0, "blocked_reason":"phone_required"}`
- `reports.py:325` 的免费额度分支条件加一项 `and current_user.phone_e164`

**状态要诚实**（§3.1）：`blocked_reason` 是必需的——没有它，前端分不出 `allowance:0`（没绑手机）
与 `used:1, allowance:1`（本周已用完）。`reports.py` 的 402 detail 同样加一格
`"free_weekly_blocked": "phone_unbound"`，否则我们在把「你还没绑手机」伪装成「你没钱」。

### D-U2 注册**不强制**手机（采信 p3-decider-2，**推翻** p3-decider 的 F4 主裁）

**手机号是「拿免费额度 + 发言」的门票，不是「有账号」的门票。** 未绑手机仍可注册、登录、
下棋、自费复盘、买积分；不能拿每周免费额度，不能发言。

四条依据，前两条是风险，后两条是本 session 核实的事实：

1. **经济闸已经由 D-U1 结构性关严**：注册 N 个用户名 = N × 0 份免费复盘。关掉密码注册不再增加
   任何防刷收益，只增加风险。
2. **强制手机 = 把短信做成全部增长的单点**。签名报备 5–10 工作日且不承诺时效、6 个月无发送记录
   会失效、国际通道有日额度。任何一条命中的那天，新用户注册通道归零。
3. **实名义务约束的是「提供信息发布 / 即时通讯服务」，不是「有账号」**（《网络安全法》二十六条）
   ⇒ 正确落点是**未绑手机不得发言**，两处，均已核实：
   - 对局聊天 `server.py:2820-2825`：已有 `if current_user is None: → chat_requires_identity`
     的正确形状（注释写着「说一句而不是静默丢弃:静默丢弃时发言的人看不出自己没发出去」），
     紧跟一个 `elif not current_user.phone_e164: → chat_requires_phone` 即可。
   - 直播评论 `live.py:587-591 create_comment`：`Depends(get_current_user)`，加 403
     `comment_requires_phone`。
4. **这条裁决同时消掉了 F13 的破坏性改动**：注册契约不变 ⇒ `api.ts` 的 `register` 不动 ⇒
   共享领土的 `components/RegisterDialog.tsx`（`ZenModeApp` 用，非 strict 盒子包里带着它）
   不会坏，`auth.py:329-345` 的 board 注册转发也不用改 410。**少动三处共享文件。**

保留 p3-decider F4 的**子裁定**（与本条不冲突）：**用户名由用户自己起，密码必填，不做无密码账号。**
依据已核实：盒子登录只有用户名口令一条路（kiosk `LoginPage.tsx` 无注册入口）；且全仓
`hashed_password` 唯一写入点是 `core/auth.py:194 create_user`，**没有任何改密码路径**。

**顺带补一处已知缺口**（p3-decider-2 提出，已核实 `auth.py:322-326`）：`/auth/register` **至今零限流**。
P3 要为 `send-code` 建 per-IP 限流器，**同一个限流器一行 Depends 挂到 `/auth/register` 上**——
不要出现"建了限流器却没给那个已知无限流的端点用"。

**本轮注册表单不加手机字段。** 绑定只有一个入口：`POST /auth/bind-phone`（鉴权），
UI 落在设置页 + 撞到免费额度闸时的那一处提示（用户在那里才有绑定的动机）。

### D-U3 盒子：什么都不改（两家一致）

三个新端点：strict 盒子 403（与 `auth.py:234/291` 同形）、board 非 strict 503 `need_online_phone`
**且不转发**、server 正常。三个都要写，一个都不能漏——漏掉的那个在盒子上表现为「本地库里查无此人」，
一种查不出原因的失败（F6）。

前提核实：strict 盒子的身份**就是云端账号**（launcher 已在云端登录后把 token 交给
`box_sso_bootstrap`，`auth.py:200-217`），复盘走 `_dispatch_remote_only` 打云端 ⇒
quota 消费的永远是**云端** user id，盒子上那行影子用户不是任何计费决策的操作数。

盒子用户看到「需要绑定手机号」时**文案要写「请在 modelstella.com 登录后绑定」**，
不能只写「需要绑定手机号」——盒子上没有入口。

### D-U4 短信通道：阿里云一家两条 API（两家一致）

|  | 国内（+86 且 14 位） | 国际/港澳台 |
|---|---|---|
| Action | `SendSms` | `SendMessageToGlobe` |
| Endpoint | `dysmsapi.aliyuncs.com` | `dysmsapi.ap-southeast-1.aliyuncs.com` |
| 报备 | 签名【万智星】+ 模板，5–10 工作日 | **不需要签名与模板** |
| 日额度 | `SMS_DAILY_CAP_CN = 300` | `SMS_DAILY_CAP_INTL = 50` |

两个额度**独立计数器，互不借用**。国际那条不被报备阻塞 ⇒ **端到端可以先用国际通道跑通**，
不必等国内签名下来。零新增 Python 依赖（标准库 `hmac`/`hashlib` + 已有 `httpx` 手签，F8）。

⚠️ **分母是「已提交条数」不是「已送达条数」**：阿里云国际短信按提交计费，运营商回执失败照收
⇒ 供应商超时/报错的也要计入日额度（我们不知道阿里收没收，保守计），但**不计入该号 60s 冷却**
（一次抖动不该锁用户 60 秒）。这正是两个计数器必须分开记的理由。

✅ **已定 `SMS_DAILY_CAP_INTL = 50`**（两家给的数不一致，取低的那个）。理由：国际号是**最贵的
攻击面**，封顶要比国内低**一个量级**而不是低三成；按最坏单价 ~$0.15/条算，50 条封顶约 $7.5/日。

一张表 `sms_challenges`（不是两张）：日额度、同号冷却、per-IP 计数**全部从这张表数 SQL**，
不用进程内字典（F5：`billing.py:58` 那个 defaultdict 进程重启即清零）。
verify **只收 `challenge_id` 不收手机号**；发新码时先把该号该用途的未消费码全部作废。

### D-U5 重置密码：做，但只做鉴权那一半（只有 p3-decider 裁了，采信）

- **不做** 免鉴权的 `POST /auth/reset-password`。
- **做** `POST /auth/set-password`（**鉴权** + `challenge_id` + `code` + `new_password`）。
- 登录框的「忘记密码？」**不跳独立流程**，切到「验证码登录」tab。

决定性事实（已核实）：全仓 `hashed_password` 唯一写入点是 `core/auth.py:194`，
没有任何改密码/重置/管理员改他人密码的端点，也没有邮箱列 ⇒ **今天一个用户忘了密码，
这个系统里没有任何人能帮他。**

必须有的一步：**校验 `challenge.phone_e164 == current_user.phone_e164`**，
否则一个人可以拿自己号上的码去改别人的密码。

**已知限制，要写进计划**：手机丢了 = 账号丢了（没有邮箱、密保、人工申诉）。且 JWT 没有版本位
⇒ **改密码不会踢掉已签发的旧 token，最长 7 天**，与用户直觉相反，UI 上要说出来。

### D-U6 用户名来源：**问题消失**

D-U2 定了注册仍是用户名+密码 ⇒ 不存在"纯手机注册的用户没有用户名"这种账号，
JWT 的 `sub` 取 username（F4）继续成立，不需要生成器，也不需要 `PATCH /users/me` 改名。

### D-F10 客户端 IP：应用自解析 XFF（已定，依据见 F10）

`TRUSTED_PROXY_HOPS` 默认 1，取右起第 N 跳。**不写死 `FORWARDED_ALLOW_IPS`**——
生产网关 172.20.0.1 / 测试 172.19.0.1 本来就不是一个值，且 Docker 重建网络后会变，
变了是**静默**退回"全站一个桶"。

### 顺带纠正需求文档 §1.2 的三条过期断言（本 session 逐条核实）

| 文档说 | 实际 |
|---|---|
| `BILLING_FREE_GRANT: int = 10000`，全仓零引用，是死常量 | 已改名 `BILLING_SIGNUP_GRANT: int = 0`（`config.py:97`），**有真调用者** `auth.py:359-365` |
| `models_db.py:78` 与 `models.py:183` 两处 10000 都要改 | **都已是 0**，仓里已 grep 不到这两个 10000 |
| `billing.grant()` 的 IntegrityError 补偿分支会多扣一次，上线前必须修 | **已修**，`billing.py:190-196` 只 rollback + 读回 winner，注释写明 "Do NOT debit again here" |

另：`billing.py:5-10` 的模块头注释说反话——它写 "Read-only balance falls through to a remote fetch
if available"，而 `get_balance`（`:83-85`）在 board 模式直接 `_need_online()` 抛 503，**没有任何
fallthrough**。照这条注释理解盒子行为会得出错误结论。（非本轮修，已记。）

## 4. 验收

- 全量 pytest 与本分支基线**按失败名字集合**比对，新增为空。
- 每条安全断言都要有变异验证：把防线拆掉，对应用例当场变红。
- 前端 `npm run build` 与 `npm run build:kiosk-2d` 都绿（登录框是共享领土，两个产物都吃）。
- 真浏览器验收登录流程（jsdom 对布局与真实交互无权作证）。
