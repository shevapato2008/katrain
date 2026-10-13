# 棋谱列表请求内复用正交批次校验

日期：2026-10-09。状态：修正版计划独立审核 PASS，待实现。依据：[现有诊断](../../resource/kifu-orthographic-read-latency-2026-10-09.md)、[最小方案](../../resource/kifu-language-latency-next-plan-20261009.md)、[独立审核](../../resource/kifu-language-latency-plan-review-20261009.md)。性能任务不阻挡翻译入库。

## 目标与范围

消除同一次 `list_kifu_albums()` 搜索和展示中对同一未变化正交批次的第二次 `persisted_batch_bindings()` 完整验证。批次 588 的实际请求耗时 3.244 秒，其中两次验证分别为 0.785、0.897 秒；目标是去掉后一次验证，实际净收益须计时确认。

仅使用本次列表调用内的空字典，通过玩家名称路径传递。每次请求重新建立字典；所有名称资格筛选和逐名 `verified_source_live()` 保留。无跨请求缓存、TTL、Session 缓存或数据库结构变化。

## 最小文件

- `katrain/web/api/v1/endpoints/kifu.py`：列表函数创建并传递本次请求字典。
- `katrain/web/kifu/identity.py`：可选参数沿玩家名称查询传递，按新鲜批次值复用成功上下文。
- `tests/web_ui/test_kifu_name_orthographic.py`：在现有集成 fixture 中加入本次行为及失效边界用例；已有列表/API 测试可直接运行。

`name_orthographic.py` 保留现有算法和生产专用 legacy SQL 适配，实施不整体替换该模块。

## 3 个聚焦步骤

### 1. 用现有 fixture 固定复用和失效要求

对一个能在搜索及展示中命中同一正交批次的 TW 列表请求，计数 `persisted_batch_bindings()` 与来源活体验证：前者应从两次降为一次，结果、显示名称及来源验证次数保持原样。

覆盖同一 Session 的下一次请求及单次请求中间的批次状态/artifact 变化。跨请求用例保留旧批次 ORM 强引用并从独立事务写入撤销，使其能识别只刷新缓存命中的错误实现。保留来源变化拒绝验证，并检查待提交 Session 变化不会被强制刷新覆盖。使用现有测试设施，不新增测试框架。

### 2. 只接入本次列表的成功上下文复用

`list_kifu_albums()` 创建一个字典并传给 `strict_matching_names()` 和 `strict_display_maps()`；参数默认 `None`，现有其他调用者保持可用。沿玩家名称的 `_qualified_name_rows()` 路径传递，事件路径不扩展。

批次读取前先检查 Session 的 `new`、`dirty`、`deleted`。有待提交变化时走原查询及原验证，跳过强制刷新和缓存读写。其余情况下，该复用路径的所有批次读取统一 `populate_existing()` 或等效新鲜读取，覆盖首次、miss、命中比较和失效重验。

条目以 batch id 为键，仅存成功正交上下文及校验当时的 `status`、`bundle_sha256`、`reviewed_artifact` 值；不能以可刷新的 ORM 实例代替旧值。仅最新状态为 `applied` 且三项输入一致时复用；否则移除旧条目、按原路径验证，成功才重新存入。保留原有每次名称/证据查询、资格筛选和每个名称的 `persisted_name_eligible()` / `verified_source_live()`。

### 3. 聚焦验证并记录实际收益

运行新增用例、现有正交集成模块及直接涉及的列表/API 回归；如已有检查足以覆盖，不增加额外测试层。再做一次代表性真实 TEST TW 搜索的只读路由计时，记录批次验证次数、路由时间与返回结果，并核对 CN/EN 简单查询无明显回退。保留 JSON 读取、比较和来源验证成本的说明，不宣称省去两次验证总计 1.682 秒。

通过这些检查即完成该性能改动；不扩展全语言回归、重复 profile 或无关 UI 工作。实现和 TEST 验证完成后，按主任务已有发布授权推进；本计划本身不表示已实现或已上线。
