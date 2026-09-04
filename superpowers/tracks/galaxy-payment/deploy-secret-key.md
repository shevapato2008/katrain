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
