# Named phone registration — independent plan review R2

**结论：Approved，可进入实施。**

这是最多两轮计划审核的最终一轮。仅复核更新后的设计、实施计划是否解决 R1-1 及由修订引入的相关风险；未扩展设计范围，未实现产品、运行测试、连接设备或读取真实凭据。

R1-1 已在计划层面闭环：

- **权威范围明确。** 专用迁移按 server/board 角色处理；权威 PostgreSQL 和 server SQLite 均强制公开名唯一，board SQLite 仅缓存可信展示名。没有以数据库方言代替身份权威的判断。
- **共享 metadata 隐患已封住。** 明确禁止在共享 ORM 列、约束、索引上声明该唯一性，也禁止迁移运行时创建会污染 shared metadata 的 Index；通用建表和缺失索引补建不会将 server 约束带入后续 board 引擎。
- **迁移目标明确。** server 建立并验证普通完整、单列、无 predicate/表达式的实际唯一索引；保留幂等及 malformed-index 拒绝要求。board 不执行权威账户回填，不因缺少本地 PhoneIdentity 错认历史 `u_…` shadow。
- **缓存不改变身份。** 公开名只从已验证云端 `/me` 或受信任 bootstrap 同步，可信 null 清理旧推导值。缓存允许重名但不参与本地密码认证；canonical 查找、JWT `sub`、generation/CAS、ID、UUID 和历史归属保持不变。
- **验证与故障相称。** 计划已有权威 PG/server SQLite 唯一性、同进程 server 迁移不污染后续 board metadata，以及云 A 删除后 B 复用公开名、同 RK 两条 shadow 共存且身份历史不变的聚焦证明。无需增加新表、清理历史账户或建立别名平台。

对关联历史兼容规则的复核未发现新阻塞：生成账户分类仍排除同一用户的 `bound_existing` claim；删除后保留的 claim.user_id 只作审计，永久 claim 继续阻止重复赠额；分类和迁移不自动修改密码或身份。

本次批准针对方案可实施性，实际迁移、唯一索引有效性、并发赠额及身份切换仍由计划中已有的聚焦实现测试和最终代码审核验证，不代表测试已经执行。用户已授权的视觉修正与 TEST → PROD → RK 忙则等待的发布约束维持原定范围。无需第三轮计划审核或再次视觉确认。
