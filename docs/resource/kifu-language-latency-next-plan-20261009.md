# 棋谱语言切换：下一步最小延迟修复

日期：2026-10-09。基线：`0d157e7f`。本文件只提出实施方案；未改业务代码、数据库或部署。

## 已确认的瓶颈

现有只读 TEST 路由诊断中，`q=加納一夫&lang=tw&page_size=20` 的进程内列表请求耗时 3.244 秒。`strict_matching_names()` 为搜索校验玩家名，随后 `strict_display_maps()` 为当前页展示再次校验；二者经 `identity._qualified_name_rows()` 各自读取并验证同一个已应用批次 588。批次含 63,934 行批准名称快照。两次 `name_orthographic.persisted_batch_bindings()` 分别耗时 0.785 和 0.897 秒，合计约占请求时间的 52%。现有 `30c668bd` 已消除**单次**验证内的重复快照扫描，但未消除**同一列表请求内**的第二次完整验证。CN/EN 已发布名称路径约 0.1–0.3 秒；本方案优先处理此处已量化的 TW/生成名称热点，不推断端到端可减少完整 1.68 秒。

## 实施建议

1. 在 `list_kifu_albums()` 创建一个仅在本次函数调用存活的空字典，传给 `strict_matching_names()` 与 `strict_display_maps()`。只沿玩家名称的 `_qualified_name_rows()` 调用传递，不扩大到全局、Session 生命周期或跨请求缓存。这个字典存成功验证的正交批次上下文，键为 batch id；现有 `contexts`/`orthographic_contexts` 局部结果继续为每次名称查询提供相同接口。没有缓存项时保持原调用 `name_orthographic.persisted_batch_bindings(batch)`。
2. `_qualified_name_rows()` 在参与复用的玩家名称路径读取批次前，先检查 Session 的 `new`、`dirty`、`deleted`；有待提交变化时走原查询及原验证，跳过强制刷新和缓存读写，避免覆盖未提交改动。无待提交变化时，首次读取、缓存未命中、命中比较和失效后重验都统一使用 `populate_existing()`（或等效的数据库新鲜行读取），不能只刷新命中项，避免同一 Session 的 identity map 在下一次空缓存请求中遮蔽撤销。仅当最新 `status == applied`、`bundle_sha256` 与 `reviewed_artifact` 均与创建缓存项时保存的值一致，才复用验证上下文；缓存项不得只保存会被刷新覆盖的 ORM 实例作为旧值。否则丢弃项并按原路径重新验证。不要缓存失败结果。只做此请求内部复用，不引入 TTL、进程状态或数据库结构。现有批次读取本来就会取完整 JSON；内容相等检查比再次计算完整快照证明便宜，具体收益用一次路由计时确认。
3. 保留每次名称查询、证据筛选及 `persisted_name_eligible()` 调用。特别是 `verified_source_live()` 必须对每个当前名称继续读取最新来源名称、证据、来源批次及 creation journal；不可把其结果放入上述字典。`name_orthographic.py` 当前含生产环境专用 legacy SQL 适配，实施时只改 `identity.py`/路由传参，不整体替换该模块。

### 失效边界

- 每个 HTTP 列表调用重新建字典；撤销、重审或新批次在下一请求立即经过当前数据库行及原资格门。测试复用同一个 `Session` 调两次列表时也不能共享字典。
- 同一请求两次校验之间，若批次 `status`、签名或批准 artifact 发生写入，最新行比较失败，旧上下文不得复用。若同一 Session 已有待提交写入，在批次刷新前直接跳过强制刷新及缓存读写；列表路由本身无写入。
- 对当前名称或来源证明的变更，不依靠批次字典判定；每次 `_qualified_name_rows()` 的名称/证据 SQL 与每次 `verified_source_live()` 的活体校验仍应拒绝撤销内容。新批准名称若引用新批次，因 id 未命中而完整验证。

## 聚焦验证

1. 用现有正交集成 fixture 对一次 TW 搜索列表计数：同一 batch 的 `persisted_batch_bindings()` 从两次降为一次；搜索结果、页展示和来源证明调用次数保持原样。
2. 在两次列表调用间通过独立写入事务撤销批次或修改批准状态，并用**同一个 Session** 再调用；保留旧批次 ORM 对象的强引用，断言空缓存请求也读取新鲜批次且旧名称不可搜索/展示。另对单次调用的搜索和展示之间模拟批次状态或 artifact 变化，断言缓存失效。来源名称或证据变化时仍由 `verified_source_live()` 拒绝。有待提交 Session 变化时确认原验证继续执行，且没有强制刷新覆盖这些变化。
3. 仅做一个代表性真实 TEST TW 搜索的只读计时，记录批次验证次数与路由耗时，并核对 CN/EN 简单查询无明显回退；不要扩张为全语言全状态回归或重复线上 profile。

现有测量依据：[`kifu-orthographic-read-latency-2026-10-09.md`](kifu-orthographic-read-latency-2026-10-09.md)。

独立审核已收敛为 PASS：[`kifu-language-latency-plan-review-20261009.md`](kifu-language-latency-plan-review-20261009.md)。实施步骤：[`2026-10-09-kifu-request-orthography-reuse.md`](../superpowers/plans/2026-10-09-kifu-request-orthography-reuse.md)。
