核心账务包独立审核，2026-11-02。

审核对象是 `feature/membership-recharge` 工作树中的 `core/{membership,billing_operations,billing_quotes}.py`、`core/billing.py` 改动及指定三组测试；基线 HEAD 为 `84433a82ed863b7d059e8b73ec6cc725b9a653d9`，本包实现尚未提交。catalog/schema/environment 基础包不重复审核。

最终结论：**Spec Approved → Quality Approved**。当前 0 个未解决 Critical、Important、Minor。以下保留首次审核及修复复核证据；本结论限于本包，不替代整功能的代码、视觉与部署验收。

首次审核发现的两项 Important 均已修复：

1. **Important：Free 权限失效被当成额度不足，自动扣钱包。** 位置：`katrain/web/core/billing_operations.py:64`、`:344`。`_source` 丢弃 `can_claim_free_report` 的拒绝原因；接受的报价是 `free_report` 时，授权阶段的可信核验由 True 变为 False，仍返回 wallet，只检查报价 cap 和余额后扣款。这违反“未知／权限失败不作钱包回退”，也让验证失败触发新的收费工作。

   真实 PG 复现：无会员、credits=10；先以 `trusted_free_eligible=True` 为普通 report、units=2 报价；另一事务对同 token 以 `trusted_free_eligible=False` 授权。实际结果为 `quoted_source=free_report, reserved_source=wallet, balance=8`。预期拒绝该 Free 授权，钱包及 operation 保持不变。应区分权限失效与可回退的资源不足；最初已明确报价为 wallet 的合法购买不应受 Free 前置影响。

2. **Important：锁住用户后未刷新 term/week ORM 缓存，会丢失另一事务的预留。** 位置：`katrain/web/core/membership.py:25`、`:37`，`katrain/web/core/billing_operations.py:54`、`:380`、`:386`。`_user` 使用 `populate_existing()`，但是随后额度读取及 `FOR UPDATE` 查询没有刷新 Session 已有对象。行锁串行化数据库访问，却没有刷新旧的 Python 字段；`reserved += units` 可以把已提交的新计数覆盖掉。`:420`、`:425` 的结算／退款计数使用相同读写方式，也需要一起检查。

   真实 PG 复现：会员 term 剩余10，已建立本周桶；Session A 读取并强引用 term 和 bucket，二者 reserved=0。Session B 正常授权 report 2并提交；Session A 再正常授权 position 1并提交。新 Session 读取结果：两条 reserved receipt 的 units 合计3，但 `term.reserved=1, week.reserved=1`。这破坏账务守恒，后续可能少计配额，或在结算较大 operation 时负数触发约束错误。应在 user 锁内以新鲜状态判定来源，并在锁住 term/week 后刷新权威计数再修改；补强引用双 Session 回归及相关结算／退款回归。

首次验证：指定隔离 PostgreSQL/period/quote 测试 **29 passed in 16.58s**（27 个 PG 用例）；另用相同安全 fixture 的独立随机 schema 运行以上两个确定性复现。原有测试通过不足以覆盖上述两个缺口。

修复复核：

- Free 报价签名绑定 `free_eligibility_policy=trusted_identity_v1`；新授权在可信状态为 False 或 None 时先返回 403，不创建 operation、不扣钱包。仍可信但周资格已经使用的情况可在原签名 cap 内回退钱包；初始 wallet 报价不受 Free 前置影响。
- 授权在用户锁内重新读取并锁住 term/week，相关 `populate_existing()` 刷新覆盖预留、结算、退款和旧 credit 状态；所有更新仍只 flush。新增强引用双 Session 回归覆盖计数守恒、来源重新判定、续期尾部和 owned receipt 刷新。
- 在复核中另发现实际 `SessionLocal(autoflush=False)` 下，回收的 `op.generation += 1` 被重入退款的刷新查询覆盖。独立 PG 曾复现退款正确但 generation 仍为0。实现已在重入前以 `db.flush([op])` 持久化当前事务内的 fence；整组 PG 测试改为与运行时一致的 `autoflush=False`，该回归及旧 generation 晚回回归通过。

最终独立验证：指定三组测试 **42 passed in 24.19s**，其中 **40 个真实 PostgreSQL 用例**。先确认以上规格缺口全部关闭后，再完成同包质量检查：固定入队锁与用户锁顺序、整笔来源/cap、刷新后的计数守恒、原来源幂等退款、崩溃 fencing、receipt 保留及服务只 flush 的边界均未发现剩余问题；修复没有引入额外 schema 或基础设施。

审核过程仅新增／更新本报告，没有修改产品代码，没有访问生产、默认应用数据库、GPU或秘密值。未进行 commit、push 或部署。
