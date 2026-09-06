# P3 手机登录 —— 写计划之前的实测发现

2026-09-07。全部是在 `feature/phone-login`（基于 develop `f2fc3c01`）上**跑出来的**，
不是读代码推的。写计划时直接引用，不要重推。

## F1 ✅ 需求文档那条 SQLite 断言仍然成立（复核过，没过期）

```
ALTER TABLE users ADD COLUMN phone VARCHAR UNIQUE
  -> OperationalError: Cannot add a UNIQUE column
ADD COLUMN(无约束) + CREATE UNIQUE INDEX  -> 成功
两行 phone=NULL 都能插入                  -> SQLite 唯一索引不管 NULL
```
⇒ 存量用户 `phone` 为空**不会**互相冲突，不需要为存量用户造占位号。

## F2 ✅ 现有迁移机制已经天然做对了这件拆分，不用手写 DDL

- `migrations.add_missing_columns()`（`migrations.py:324`）拼的 DDL 是
  `ALTER TABLE "users" ADD COLUMN "x" <type>` + 可选 DEFAULT —— **它不带 UNIQUE**，
  所以模型上就算写了 `unique=True` 也不会触发 F1 那个报错。
- `migrations.create_missing_indexes()`（`:374`）用的是 `index.create(bind=conn)`，
  **保留 `unique=True`**（注释里专门写了"不要按列名重建索引，那会静默变成全局唯一约束"）。

⇒ 做法：`User` 上加 `phone_e164 = Column(String(20), nullable=True)`（**列上不写 unique**，
避免歧义）+ `__table_args__ = (Index("ix_users_phone_e164", "phone_e164", unique=True),)`。
两个方言都自动迁移，零手写 DDL。`User` 现在**没有** `__table_args__`，是新增。

## F3 ⚠️ 无口令用户不能塞占位 hash —— `verify_password` 会**抛异常**，不是返回 False

实测（`katrain/web/core/auth.py`）：
```
verify_password("anything", "!")                  -> UnknownHashError
verify_password("anything", "")                   -> UnknownHashError
verify_password("anything", "not-a-bcrypt-hash")  -> UnknownHashError
verify_password("anything", "*")                  -> UnknownHashError
```
而 `hashed_password` 是 `nullable=False`（`models_db.py` User）。

后果如果照 Django 那套 `!` 约定写：纯手机注册的用户被人拿去打 `/auth/login`
⇒ **500 而不是 401**。两个问题一起来：
1. 崩溃路径；
2. **信息泄露** —— 500 与 401 可区分"这个用户名存在且是纯手机用户"与"查无此人"。

⇒ 计划里必须两条都做：
(a) 纯手机注册时生成**真的 bcrypt hash**（对一个随即丢弃的 32 字节随机串），
    这样 `verify_password` 干净地返回 False；
(b) `verify_password` 自己收口，遇到无法识别的 hash 返回 False 而不是抛
    —— 靠 (a) 一条是"约定"，靠 (b) 才是"结构"。存量数据里有脏 hash 时也不会 500。

## F4 ⚠️ JWT 的 `sub` 是 **username**，不是 user id ⇒ 纯手机用户必须有用户名

`create_access_token(data={"sub": user_dict["username"]})`（`auth.py` login/register 两处），
`get_user_from_token` 反查也是按 username。而 `users.username` 是 `unique, nullable=False`。

⇒ 手机注册要么让用户起名，要么服务端生成。**这是产品决策点，计划里必须写死**，
不能让实现者临场发挥。注意：**不要拿手机号当用户名** —— 它会进 JWT、进日志、
进 `/api/v1/social` 的公开资料。

## F5 全站唯一的限流是**进程内字典**，且它不是给 send-code 用的形状

`billing.py:58-76` 的 `_redeem_attempts: defaultdict(list)`。两个局限：
1. **进程重启即清零** —— 对"每 60 秒一条短信"这种要跨重启的冷却是漏的；
2. 多 worker 下各算各的 —— **这一半已核实：今天是单进程**。
   `server.py:3569` 是 `uvicorn.run(app, ...)`，传的是 **app 对象**且没有 `workers=`；
   uvicorn 的多 worker 必须传 import 字符串，所以这条路**不可能**起多进程。
   生产容器实测启动命令是 `python3 -m katrain --ui web --host 0.0.0.0 --port 8001`，走的正是这条。
   ⇒ 进程内字典**今天**是一致的。但它仍然扛不住重启，且这是个**会过期的前提**
   （哪天换成 gunicorn / `--workers` 就静默失效，而失效的表现是"限流变松"，没有任何报错）。

⇒ send-code 的冷却应当**从验证码表自己算**（该号最近一条未消费码的 `created_at`），
天然跨重启、天然跨 worker，不需要新存储。IP 维度那一半再用进程内字典兜。

## F6 盒子（board 模式）有一条完全独立的转发路径，新端点必须显式处理

`auth.py` 的 `login`/`register` 都有 `remote_client is not None` 分支：**盒子把注册登录
原样转发给云端**，然后在本地建影子用户（`_get_or_create_shadow_user`）。
且三个端点开头都有 `strict_box_sso_enabled()` → 403。

⇒ `send-code` / `login-by-phone` / `bind-phone` 三个新端点各自都要回答：
strict 盒子上是不是 403？board 模式是转发还是 503 `need_online`？
**漏掉任一个，盒子上的表现就是"在本地库里找不到人"这种查不出原因的失败。**

## F7 前端登录框现在是纯用户名口令一条路

`galaxy/components/auth/LoginModal.tsx`（133 行）：`isRegister` 一个布尔在登录/注册之间切，
`API.register` + `login(username, password)`。手机那条路要加的是**第三种模式**，
不是在这个布尔上再加一个分支。i18n 走 `i18n.t('auth:xxx', '默认英文')` —— 注意项目规矩是
**默认值要写中文**（见 `reference_kiosk_i18n_architecture`），这个文件现在写的是英文默认值。

## F8 🚨 加一个 Python 依赖 = 两份清单都要动，而生产那份**只活在 release 分支上**

| | develop 的 `Dockerfile.web` | release/ucloud-20260805 的 `Dockerfile.web` |
|---|---|---|
| 装什么 | `pip install -r requirements-web.txt -r requirements-desktop.txt` | `pip install --require-hashes -r requirements-web-runtime.txt` |
| 那份文件在 develop 上 | 在 | **不在**（release 独有） |

⇒ 只往 `requirements-web.txt` 加一行的后果：**测试环境正常，生产镜像构建也成功，
但包不在里面 —— 只在生产运行时 ImportError**。而且 `--require-hashes` 意味着不能只加名字，
要连 sha256 一起补。同族教训：[[reference_deploy_copies_a_subtree_only]]。

**⇒ 计划的硬约束：P3 不新增任何 Python 依赖。** 两处会想加，两处都不加：

1. **E.164 解析**：不引 `phonenumbers`（未安装，且是带数据块的大库）。
   手写一个"国家区号表 + 纯数字 + 长度区间"的归一化器，配单测。
   我们只需要"存成 E.164、判断是不是中国大陆号（决定走国内还是国际通道）"，
   不需要它的运营商/号段库。
2. **短信供应商 SDK**：不引 `aliyun-python-sdk-core` 之类。阿里云短信是 RPC 风格 +
   HMAC-SHA1 签名，用 `hmac`/`hashlib`/`urllib.parse`（标准库）+ 已有的 `httpx` 就能签。
   **而且这是更对的做法**：需求要求供应商调用必须 `async`（单进程下同步阻塞会拖垮整站），
   官方 SDK 是同步的。

若最终确实非加不可，计划里必须把"同时更新 release 分支的 hash-pinned 清单"写成一个显式任务，
不能靠实现者记得。

## F9 仓里已经有「这个账号没有本地口令」的先例 —— 而它是 F3 那颗雷的**已埋版本**

`auth.py:77`：
```python
SHADOW_USER_NO_LOCAL_AUTH = "SHADOW_USER_NO_LOCAL_AUTH"
```
`auth.py:187` 拿它当盒子影子用户的 `hashed_password`。**它是一个普通字符串，不是 bcrypt hash**
⇒ 按 F3 实测，`verify_password(任意, "SHADOW_USER_NO_LOCAL_AUTH")` 会抛 `UnknownHashError`。

**今天够不着**（读代码确认，不是"跑了没红"）：影子用户只在盒子本地库里产生 ——
`_get_or_create_shadow_user` 的两个调用点分别在 `box_sso_bootstrap`（被 `_require_bridge`
挡住，非 strict 一律 404）和 board 模式的 `login`（那条分支里 `/auth/login` 转发给云端，
根本走不到本地 `verify_password`）；strict 盒子上 `/auth/login` 直接 403。云端不产生影子用户。

⇒ 两条推论，都进计划：
1. **先例可以抄**：纯手机用户沿用"哨兵字符串"这个既有约定，不要另发明一套。
2. **但必须同时把 F3(b) 做掉**：`verify_password` 收口成"无法识别的 hash 返回 False"。
   否则这颗雷只是从"够不着"变成"够得着" —— 纯手机用户是**云端**账号，
   `/auth/login` 在云端走的正是本地 `verify_password` 那条路。
   现在修它顺带把影子用户那颗一起拆了。

## F10 🚨 生产上 `request.client.host` 对**所有用户都是同一个值** —— 按它做 IP 限流 = 全互联网一个桶

需求写着限流键必须是 `(phone, purpose)` + `client_ip` 两组同时生效。照直写
`request.client.host` 会造出一条**量错对象**的闸。三段实测：

**① uvicorn 会用 XFF 改写 client.host —— 但只在直连对端可信时。**
本机实跑（uvicorn 0.40.0，全默认，不显式传 `proxy_headers`）：
```
不带头             -> client_host = 127.0.0.1
X-Forwarded-For: 203.0.113.9              -> client_host = 203.0.113.9
X-Forwarded-For: 1.2.3.4, 203.0.113.9     -> client_host = 203.0.113.9   ← 取**最右**一跳
```
取最右是对的：nginx 用 `$proxy_add_x_forwarded_for`（**追加**自己看到的对端），
所以最右一跳恒等于 nginx 亲眼看到的客户端，客户端自己伪造的部分被挤到左边。
`Config.__init__` 默认：`proxy_headers=True`、`forwarded_allow_ips=None`（回落到 `127.0.0.1`）。

**② 生产 nginx 确实在传头**（`/etc/nginx/sites-enabled/modelstella.com`）：
`proxy_pass http://127.0.0.1:8001` + `X-Real-IP $remote_addr` + `X-Forwarded-For $proxy_add_x_forwarded_for`。

**③ 但 web 跑在容器里，对端不是 127.0.0.1 —— 所以那个头压根不被信任。**
```
容器 FORWARDED_ALLOW_IPS = (空) ⇒ uvicorn 回落到默认 127.0.0.1
NetworkMode = katrain-ucloud_app（bridge，不是 host）
容器默认网关 /proc/net/route = 010014AC = 172.20.0.1
```
nginx → 宿主 `127.0.0.1:8001` → Docker DNAT 进容器 ⇒ **容器看到的对端是 172.20.0.1**，
不在 `forwarded_allow_ips` 里 ⇒ **uvicorn 不改写** ⇒
**`request.client.host` 对每一个用户都是 `172.20.0.1`。**

⇒ 后果不是"限流失效"，是**反过来**：per-IP 限成 5 条/小时的话，全站第 6 个正常用户就被挡，
而表现是「限流生效了」，不是报错。**这是自己给自己造的故障。**

**三条路，计划里必须选一条并写死判据：**
- (a) 给容器配 `FORWARDED_ALLOW_IPS=172.20.0.1`。缺点：网段在 compose 重建网络时会变，
  变了之后**静默**退回全站一个桶。
- (b) **应用自己解析 XFF**，用"可信代理跳数"配置（取右起第 N 跳），显式且可单测。
- (c) `FORWARDED_ALLOW_IPS=*`。**不能用**：`8001` 除了 `127.0.0.1` 还发布在 `10.8.0.3`
  （WireGuard），存在不经过 nginx 的到达路径，那条路上 XFF 完全由攻击者控制。

无论选哪条，**必须配一条断言：两个不同客户端 IP 拿到的限流桶不是同一个**。
只断言"限流会拦"的用例对这个缺陷免疫——它在一个桶的世界里也是绿的。
同族：[[reference_gate_measures_wrong_operand]]。

## F11 ⚠️ 需求文档 §2.3 里 U1 的"为什么不能默认"**已经过期** —— 它描述的是没落地的第 1 稿

需求原文说每周免费走 `billing.grant`，`ref_id` 全局唯一 ⇒ `weekly:None:2026-W36`
会让第一个用户领到、其余 IntegrityError 静默不发。**实际落地的不是这样：**

```
grep -rn '"weekly\|weekly:' katrain/ --include=*.py | grep -v test   → 零命中
billing.grant 的非测试调用者 → config 注释 / 结算退款×2 / 注册赠额 / 管理员发放
                              （没有一个是每周免费）
```

真正落地的是**额度桶**：`reports.py:325-333` 调 `quota.try_consume(db, current_user.id,
"free_report:week", allowance=settings.FREE_WEEKLY_REPORTS)`；`quota._ensure_bucket` 按
`(user_id, kind, period_key)` 查行，**全模块不碰账本、没有 ref_id**。

⇒ U1 的实质问题因此变了（正确版本）：桶按 `user_id` 分 ⇒ 只要"一个账号 = 一个已验证手机号"
成立，桶就自动等价于按手机号分，**不需要改 `quota_buckets` 的键**。剩下要判的是：
存量 23 个无手机账号怎么算 / 新注册是否强制手机 / **换绑与注销后重注册**（同号解绑换新账号
= 新 user_id = 新桶，这才是真正剩下的刷号面）。

**这条本身也是教训**：需求文档里标着"已核实"的事实，在设计改稿之后**不会自己跟着改**。
把它当输入之前要先复核 —— 尤其是那些"为什么不能默认"的论证，它们最容易停在旧稿。
同族：[[reference_a_gate_can_expire]]、[[project_kiosk_go_design_27_screens]]（稿子里断言代码的句子要当过期候选）。
