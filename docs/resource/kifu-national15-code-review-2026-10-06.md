# National15 独立代码审查

- 日期：2026-10-06；审查者：GPT-6 Astra。
- 结论：**APPROVE**。未发现阻塞项。
- 对象：主工作树相对 `d5db21de72b3c40ed53b517d37cd3a09f83a258e` 的四个实现文件及两个聚焦测试文件；按已批准的固定 SGF 字面翻译策略审查，不重审既有全套功能。

## 核对结果

1. **范围封闭。** `sgf_literal_v1` 仅允许固定 15 个中文 raw、现有 raw_event ID、`reviewed_sgf_gn` 与五主语言。exact core/round 顺序、lossless 拼接、唯一 core 保留；年份仍在真实 core 中。`name_evidence` 在进入该分支前拒绝 player、raw_player、entity event 及其他 scope status；旧未带 marker 的外部来源规则继续要求真实 exact-core 来源。
2. **来源绑定到批准范围。** pure 校验重算完整 `scope_rows` hash，要求唯一排序 IDs、exact raw、NULL event、source_path/SGF hash，逐一绑定完整 `original_sgf_refs`。candidate 将这个 hash 与现有 owner declaration 的批准 metadata、全部 occurrence IDs 对齐；writer 继续核对实际 owner preimage 和库存。持久化 reader 再次比较实际 raw owner 的批准 scope hash，并沿用 candidate/research hash、raw/lang/display/revision/version、独立签名检查，不能仅凭格式正确的 SHA 放行。
3. **真实 GN 被保留。** 本地读取两库 `fresh-live-scope.json`：各 15 raw / 486 唯一盘，全部 scope hash、逐项成员、SGF 引用与 raw-set SHA `a1c386f0d6b606f2ed588d8b98bfd39398cec584bba683ab07e0dc7f9dede77d` 一致；全部 EV 为空，首个 GN 精确等于 raw。album **92131** 的后续 GN 为 `2020中国国家队积分大循环第5轮（白超时黑胜）`，**60639** 为 `2020中国国家队积分大循环第8轮（黑超时白胜）`，两库一致；实现允许保留这些原值，没有改写 SGF 或将注释冒充标题。
4. **辅助网页不是身份来源。** `translation_support` 校验 HTTPS URL、非空来源/实际片段/用途/归档引用、HTTP 200、SHA、具体语种及带时区时间；candidate 与持久化 reader 均拒绝晚于独立审核的原始或辅助捕获。三份已保存网页原始字节的 SHA 与 `source_research.json` 一致。来源字段作为有 hash 绑定、经人工阅读的研究保存，不要求辅助网页包含完整带年份 raw，也不将文章/博客冒充官方命名或赛事身份。
5. **有限 profile 与事务。** `national15` 固定 raw 集合及数量 15，fresh 总盘数从 manifest 写入已签 plan；prepare/inspect 都核对完整成员总量与真实全 occurrence 范围，不裁剪到历史数量。真实本批总数为 486。完整 before/CAS、catalog/inventory pins、双层锁、独立 plan/manifest SHA、重放与 undo 路径未修改；旧 profiles 的既定数量与默认 first24 保留。
6. **旧 reader 兼容。** 查询、身份碰撞、public/NULL/nonduplicate/no-selection 过滤未改；两种 reader 仍复用无 ORM 依赖的 pure 模块。已保存旧标准研究包均未使用新 `source_basis` marker，不受新分支影响。部署时只需把审核后的共享 pure 模块同步到实际运行时，再进行真实展示/搜索验收；本报告不表示已部署或写入。

## 验证依据与边界

- 实施者报告两个聚焦模块合计 **86 passed（6.92s）**、`git diff --check` clean；已阅读新增测试，覆盖三种标题形态、范围/owner 类型、GN 与 hash 篡改、owner scope、捕获时间、旧来源分支及双 reader 的持久化拒绝路径。本次未重复该套测试。
- 独立执行的本地数据核对仅覆盖真实 15/486 捕获、GN/SGF 引用、scope hash 及三份网页文件 SHA；未访问数据库或网络。
- 已将吞吐决策文档中的 EV 假设改为本批实际 GN 事实。除审查/决策文档外，没有修改实现、签署、提交、SSH、写库或部署。
