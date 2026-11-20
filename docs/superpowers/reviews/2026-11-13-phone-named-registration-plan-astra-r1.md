# Named phone registration — independent plan review R1

**结论：需修（1 项阻塞）。**

审核范围：2026-11-13 的设计与实施计划，对照 child `b342b48fc` 的 auth、phone_otp、models、migrations、remote_client，以及 parent `c877ea15` 的 launcher auth、identity、box_identity。仅做源码和方案审核；未实现产品、运行测试、连接设备或读取真实凭据。本报告是用户限定的最多两轮计划审核中的 R1。

## R1-1 · 阻塞：必须区分权威用户名唯一性和设备 shadow 缓存

设计第 26 行、计划 Task 1 第 29–32 行目前要求在共享 `User` 上增加 `public_username` 唯一索引，并把公开名同步到 board shadow，但没有区分两种库的角色。

现有代码不能自动处理这一冲突：

- `katrain/web/core/models_db.py:70` 的 `User` 同时用于云端账户和设备本地账户。
- `katrain/web/core/auth.py:118` 的 `init_db()` 运行共享 metadata 建表与迁移；`migrations.py:1367` 的通用索引创建会再次创建模型声明的索引。只在某一个迁移分支跳过 SQLite，不能抵消模型上无条件的 `unique=True`/`Index(unique=True)`。
- `katrain/web/api/v1/endpoints/auth.py:215` 的 `_get_or_create_shadow_user()` 按 canonical 名保留/创建影子行。`:498` 的安装路径明确保留原 shadow UUID 和个性化数据；没有同步云端账户删除或回收旧公开名缓存的机制。

具体故障：云账户 A 的公开名为 `棋友`，它登录过 RK，留下本地 shadow；A 在云端删除后，云账户 B 合法注册同一公开名。A、B 的 canonical 不同，但 RK 仍保留 A 的 shadow。若本地公开名全局唯一，B 的可信公开名同步就会违反约束，注册后的设备登录或 Go bootstrap 失败。为解决显示缓存冲突而删除 A 的本地历史、把 B 合并到 A 或改 canonical 都不符合本任务。

**最小修订：**

1. 共享模型仅声明 nullable 字段；由专用迁移按明确的运行角色建立和验证权威唯一索引，避免通用 `create_all/create_missing_indexes` 在 board 上补建它。权威 `server` 库强制唯一，包括用于服务端测试的 SQLite；`board` SQLite 只保存来自已验证 `/me`/受信任 bootstrap 的展示缓存，允许同名 shadow。不能用“PostgreSQL 等于 server、SQLite 等于 board”的方言判断代替角色。
2. 人类账户回填和 `get_user_by_login_name` 的命名空间规则只作用于权威身份库。board 不通过公开名查找或绑定身份，也不要因 shadow 没有本地 `PhoneIdentity` 就把历史 `u_…` 当成人类名称回填。可信缓存更新以 canonical 行和现有 generation/CAS 为边界；ID、UUID、JWT `sub`、ownership 不变。
3. 权威索引要验证真实形状：目标表与单列、唯一、有效/ready、无表达式、符合约定的 predicate/collation。最简单是普通完整唯一索引；不能只检查名字/列名，也不能接受覆盖部分用户的同名 partial 索引。现有 `verify_phone_auth_schema()` 的 PG catalog 校验可借鉴，不需要通用迁移框架。
4. 最少补三个聚焦证明：权威 PG 唯一性及重复迁移；server SQLite 也拒绝重复公开名；board 中两个 canonical shadow 可缓存同一公开名，第二个身份正常安装且两个旧 ID/UUID/历史保持。并覆盖已有 Task 1 的 malformed-index 拒绝测试。

这是数据权威边界修正，不需要别名表、墓碑平台或设备历史清理。

## 已核对，可保留的方案

- **身份与命名空间：** 单独的 password login-name lookup、歧义拒绝、canonical-only JWT/refresh/SSO lookup 是必要且足够的隔离。对旧人类账户原样回填、新人类 writer 占用同一公开名命名空间、保留新 `u_` 名称禁用规则，能避免两列查找产生静默身份选择。
- **历史生成账户：** 完整生成名模式 + PhoneIdentity + 非管理员，并排除同一用户的 `bound_existing` claim，符合现有 schema。`PhoneSignupClaim.user_id` 明确无 FK、仅作审计；删除后旧 claim 的存在仍阻止再次赠额，不能要求其 user_id 等于新用户才算已领取。现方案已写明这一点。
- **OTP 与一次赠额：** 保留 phone → challenge → user 锁顺序，最终创建/补全、claim、5000 adjustment 和消费同事务，现有每手机号状态锁可串行化同手机号操作。不同手机号争同一公开名交给权威唯一约束；只映射具体公开名冲突，不能沿用 `_create_user()` 对所有 `IntegrityError` 重试的宽泛处理。既有计划已覆盖必要并发和回滚测试。
- **密码及隐私：** 新设密码按 15 Unicode 字符、72 UTF-8 字节和 NUL 边界验证，旧密码验证不变；launcher JS 现有 ASCII 拦截确实需要删除。新的 register 必须沿用私有 phone route 的验证错误清洗与 no-store，并在两层明确允许新业务错误。实现时应先验证正确 OTP，再在锁外计算密码 hash，最后重新锁定并重验 TTL/flow/active challenge 后提交；无效 proof 不应触发昂贵 hash。这只是把计划现有“recheck”顺序具体化。
- **候选会话：** `RemoteClient._login_candidate()` 已在候选 token 上调用 canonical `/me` 并检查 generation；父 `_create_remote_session()` 经过 `/me` allowlist 后使用 `replace_active(expected_auth_attempt=...)`。注册复用这些路径即可，`profile_required` 在 candidate/session 创建前透传，不能退休旧会话。父 bootstrap 应只新增可选展示字段，保持原有 canonical 与锁事务。
- **兼容发布：** 新字段和 endpoint 是 additive；旧 `/me.username`、token shape、旧密码登录保持。上线新云端后旧前端可能把 `profile_required` 显示为泛化错误，因此应按既定同批 source/static 发布和 TEST → PROD → RK 顺序核对新 bundle。无需让旧客户端继续自动创建匿名账号来掩盖这段兼容窗口。
- **范围与验收：** 11/5 语言、Galaxy 当前页面弹窗且无 guest 按钮、Kiosk guest 保留、一次代表性同尺寸视觉比对足够。用户已授权直接开发部署，无须新增视觉确认。RK 的先读锁/进程/journal、忙则等待、独占 apply 锁且不终止别人部署，计划表述正确。

修订 R1-1 后可进入最后一轮聚焦计划确认；不要求增加其他设计流程、全量回归或与此身份边界无关的整改。
