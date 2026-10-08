# 棋谱语言切换最小延迟修复：独立计划审核

日期：2026-10-09。审核对象：[修正版方案](kifu-language-latency-next-plan-20261009.md)及[三步实施计划](../superpowers/plans/2026-10-09-kifu-request-orthography-reuse.md)。只读核对代码与已有计时，并按授权修订计划文档；未改业务代码、数据库或运行时，未执行 Git 操作。

**最终结论：PASS。唯一必须修正已在同一次审核中补入计划，可按最小范围实施。性能工作不阻挡翻译入库。**

## 已修正：空缓存也要读取新鲜批次

原计划第 2 点只明确对“候选缓存命中”使用 `populate_existing()`，不足以兑现“同一个 Session 再次调用列表也能立即识别撤销”的约束。新请求的字典虽然为空，但 Session 中若仍持有原 `KifuNameBatch` 对象，普通 ORM 查询仍可能返回其旧属性；缓存未命中并重新运行验证也会校验旧批次。当前 [`identity.py`](../../katrain/web/kifu/identity.py:171) 的批次查询没有刷新已有对象。

已补入的最小修正：对参与本次请求复用的批次读取，首次读取、未命中、命中比较和失效后重验都读取数据库当前值；可以在现有批次查询上统一使用 `populate_existing()`。先检查 Session 的 `new`、`dirty`、`deleted`；存在待提交变化时，走原查询及原验证路径，跳过缓存读写和强制刷新，避免刷新覆盖未提交改动。当前 [`SessionLocal`](../../katrain/web/core/db.py:53) 配置为 `autoflush=False`，不能依赖查询自动 flush 这些变化。

已有“同 Session 两次列表”用例只需保留一个对原批次 ORM 对象的强引用，再通过独立写入事务撤销该批次，验证第二次请求；这可避免对象被回收后测试偶然通过。无需增加新的测试框架。

## 其余判断

- **确实能避免重复。** [`strict_matching_names()`](../../katrain/web/kifu/identity.py:561) 和 [`strict_display_maps()`](../../katrain/web/kifu/identity.py:727) 都进入 `_qualified_name_rows()`。列表路由把同一个本地字典传入两个玩家名称分支，即可使未变化的批次 588 从两次完整正交验证降为一次。不得在两个下游函数中分别新建字典。
- **复用依赖完整。** [`persisted_batch_bindings()`](../../katrain/web/kifu/name_orthographic.py:456) 的持久化输入只有批次 `status`、`bundle_sha256` 和 `reviewed_artifact`。比较这三个创建缓存时的值与新鲜数据库值足以约束该上下文；缓存条目应保存这些值及成功上下文，不能把会被刷新覆盖的 ORM 实例本身当作旧值。失败不缓存、失配走原验证即可。
- **来源撤销门继续有效。** 保留每个名称的 `persisted_name_eligible()` 与 [`verified_source_live()`](../../katrain/web/kifu/name_orthographic.py:487)，后者通过当前连接读取来源名称、证据、来源批次及 creation journal，不受上述上下文复用影响。名称/证据查询与筛选保持执行；本改动不承诺跨整个请求的原子快照。
- **收益口径合理。** 已有实际路由计时为 3.244 秒，两次验证合计 1.682 秒。预期消掉的是第二次约 0.897 秒验证，并仍支付 JSON 读取及内容比较成本；不能承诺减少完整 1.682 秒。保留计划中的一次代表性 TEST 路由计数与计时即可。

无需扩展到跨请求缓存、TTL、Session 缓存、数据库结构或其他语言路径。上述一处已补明，按计划的聚焦验证完成即可；本次审核未执行性能实验或应用测试，也不构成上线验证。
