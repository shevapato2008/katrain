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
