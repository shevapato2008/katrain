# 部署前置检查：Release 0（admin 默认凭据 + SECRET_KEY）

## admin/admin 存量账号（Task 0）

代码改动（`katrain/web/server.py` 的空库首启逻辑、`katrain/web/core/config.py` 的
`ADMIN_BOOTSTRAP_PASSWORD`）挡的是**以后不再产生** `admin/admin` 这样的账号，挡不住
**已经产生的那个**。

**上线前必须检查两台机器（home-ubuntu、ucloud-v100）上是否存在用户名为 `admin` 且口令
仍是 `admin` 的账号**：

- 有，且该账号确实是当年空库首启自动创建的 —— 当场改掉密码或禁用该账号。
- 部署本次改动之前，这两台机器的数据库都不是空库（不会再触发首启创建逻辑），所以
  代码改动本身不会自动清理存量账号，必须人工核实。

## SECRET_KEY 发布顺序（Task 2）

代码改动后，`_lifespan_server` 在服务端模式下会在启动的第一步校验 `settings.SECRET_KEY`：
拿不到显式注入、或注入的值为空/空白/短于 32 字符、或等于仓库里的内置默认字面量
（`config.INSECURE_DEFAULT_SECRET_KEY`），进程**直接拒绝启动**（`RuntimeError`）。
`docker-compose.yml` 的 `katrain-web` 与 `katrain-cron` 两个服务的 `environment` 都加了
`KATRAIN_SECRET_KEY=${KATRAIN_SECRET_KEY:?...}`——`.env` 里没有这个变量，`docker compose up`
会在建容器之前就失败（`:?` 是 compose 自己的语法，不依赖代码里的这道闸）。

**换密钥 = 全站登出一次。** access token 有效期 7 天、refresh token 90 天
（`Settings.ACCESS_TOKEN_EXPIRE_MINUTES` / `REFRESH_TOKEN_EXPIRE_DAYS`），旧密钥签发的
token 一律用 HS256 校验签名，换了密钥就全部验签失败——所有在线用户会被强制退出，
需要重新登录。这是预期行为，不是 bug。**不要**为了避免这一次性的登出体验去保留旧密钥
做双验证（同时接受新旧两把密钥验签）——那等于在换锁之后继续给旧钥匙开门，
洞还开着，SECRET_KEY 泄露的风险没有被真正堵上。

**发布顺序：**

1. 生成一把新密钥：`python -c "import secrets;print(secrets.token_urlsafe(48))"`。
2. 先在 **home-ubuntu**（测试环境）的 `.env` 里设置 `KATRAIN_SECRET_KEY`，重启
   `katrain-web` 与 `katrain-cron`，确认两个服务都正常拉起（能起来就说明闸本身没挡住
   合法值），再走一遍登录 + 一次需要鉴权的请求，确认 token 签发/校验链路正常。
3. 验证通过后再上 **ucloud-v100**（生产）：设置 `.env`、重启两个服务。
4. 生产这一步会让当时在线的所有用户话一次登出——建议选低峰时段操作，或提前公告。
5. **回滚代码时必须保留这把新密钥，绝不能回退到已经公开过的旧值**（本仓字面量默认值
   本身就是已公开的旧值之一）：代码回滚只影响这道启动闸存不存在，不影响哪把密钥在
   签发/校验 token；如果回滚后 `.env` 里的 `KATRAIN_SECRET_KEY` 被误改回旧值或删除，
   旧密钥重新生效，等于把这次修复撤销。


## 发布顺序：web 必须先于 cron 起（终审补）

数据库迁移只在 web 侧跑（`katrain/web/core/auth.py` 的 `add_missing_columns` /
`create_missing_indexes`，由 `_lifespan_server` 触发）。而 `docker-compose.yml` 里
`katrain-cron` **没有** `depends_on: katrain-web`。

若 cron 先起，`report_analyze.py` 查 `report_tasks.sgf_hash` 会打在一个还缺列的库上
直接炸。同时发布时风险低（web 通常先就绪），但**发布单里要写死这一句**：

```
docker compose up -d katrain-web        # 等它起来、迁移跑完
docker compose up -d katrain-cron
```

或者给 compose 加 `depends_on`——本轮没改，因为改编排属于部署侧变更，
应该和这次发布分开评估。

## 部署当天就生效、不受 BILLING_ENFORCED 控制的三件事（终审补）

「开闸前行为不变」这句只覆盖 `POST /api/v1/reports/` 这一个端点。下面三条
**部署即生效**，别让那句话替它们背书：

1. **没有 `KATRAIN_SECRET_KEY` 会拒绝启动**，且换密钥 = 全站登出一次（这是 D5 的本意）
2. **新注册账号的 credits 从 10000 变成 0**（`BILLING_SIGNUP_GRANT` 默认 0）。
   存量用户不受影响（开账迁移是 grandfather，只补账不改余额）
3. **每次启动跑一遍开账回填**，给所有余额与账本对不上的存量用户各写一条
   `opening_balance` 账本行。第一次跑完之后后续启动是空转
