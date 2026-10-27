# Galaxy 棋谱搜索 200ms：整体代码审核

日期：2026-10-27。独立审核基线 `e9b4d3ecce03b3269f12922a476fd6d6c6545547`，最终业务版本 `ca7393960`；web-only operator 随 `ad0c1c958` 纳入。对照[实施计划](../plans/2026-10-26-galaxy-kifu-search-200ms.md)和[计划审核](2026-10-27-kifu-search-plan-astra.md)，独立读取实际差异及相关既有 reader/proof 代码，并运行下述聚焦验证。未修改业务代码、操作远端服务或执行 DDL。

**结论：Approved。没有遗留 Critical / Important 必修项。** 最小实现及本次 web-only 发布 operator 可进入已经授权的第二阶段。此结论不表示完整搜索已达到 200ms，也不替代 TEST 实际规模的索引、结果等价性、并发和浏览器绘制验收。

本轮检查的关键边界：

- 四域精确候选通过同一 scalar `UNION ALL` 读取，只对唯一棋手候选做实际 proof；其它 owner/domain 的潜在碰撞均回原路径。`selected_raw.contains(q)` 在完成 proof 后保守探测，保留 selected 赛事搜索。非 strict 模式仍核对旧 alias 结果，未绕过 raw、同名或赛事兼容路径。
- 显式 `player_id` 要求存在当前合格的公开主语言姓名，排除 hidden/error/placeholder 与孤立姓名；无公开身份返回真实空页。HTTP 参数互斥/正数校验和 dispatcher → remote adapter 的透传成立。现有可见性、精确 total、日期/id 排序、分页、首条 SGF preview、批量 rank/report 路径保留。
- 批次 bindings 按实际 proof 族构建。请求内复用先刷新当前 batch/name/evidence 及相关 owner/source，再比较完整 artifact 快照；没有跨请求缓存。快照比较保留 JSON 类型及负零区别，first-pass 活候选继续使用 canonical digest 绑定。source、raw scope、撤销和当前内容验证仍在读取路径执行。
- 本地 Session 在同一 worker 内构造、查询、关闭，每请求独立；remote 分派保持 async。`Server-Timing` 明确区分 queue、worker、handler 和各读取阶段，未把 helper/handler 时间冒充包含响应序列化、发送和浏览器绘制的完整耗时。
- 三条搜索索引仅由显式脚本操作，核验表、键/表达式、btree/非 partial 定义及 valid/ready；逐条 AUTOCOMMIT `CREATE INDEX CONCURRENTLY`，设置本次语句/锁等待预算，异常不自动删除或重建索引。没有将这些大表索引接入 Web 启动。
- 前端新搜索/翻页一起接收列表、total 和首盘 preview，旧列表/详情有取消与迟到响应保护；首盘使用 list preview；空结果、失败、同词重试分开处理。语言变化和同页刷新保留仍在当前结果中的手动选择。

发现并闭环的唯一 Minor：新增 `kifu:preview_failed` 没有 locale 条目，会使非中文失败提示回退中文。`ca7393960` 已直接复用既有 `report:preview_failed`；不需要增加翻译体系或扩展审核。

本轮实际验证：

- `pytest`：`test_kifu_library_search.py`、`test_kifu_library_worker.py`、`test_kifu_search_indexes.py`、`test_kifu_identity_context.py`、`test_kifu_list.py`、`test_kifu_offline.py`，**67 passed, 1 skipped**。跳过项明确要求实际 PostgreSQL 的 sort-index 执行计划，未用 SQLite 伪造通过。
- `pytest tests/web_ui/test_kifu_name_orthographic.py -k 'refreshes or reader_rejects or request' -q`：**22 passed, 168 deselected**。
- `npm test -- src/api/kifuApi.test.ts src/galaxy/pages/KifuLibraryPage.test.tsx src/galaxy/pages/KifuLibraryPage.localization.test.tsx`：**29 passed**。随后复核上述单行文案修正；没有重新扩大 UI 状态测试。
- `git diff --check e9b4d3ecc..HEAD` 通过；operator AST 解析通过。此审核不将负责人其它测试报告或旧基线失败冒充本轮运行结果，也未扩修已确认存在于基线的无关失败。

web-only operator 补审仅覆盖本次新增发布边界，未重开已通过的业务审核。TEST 从 live labels 读取原十一层 Compose，核对 live hash/env、完整 effective config 与 CAS，只新增 web image/build-SHA override，并限定 `up --no-deps --no-build --pull never ... katrain-web`。PROD 使用新机 `117.50.177.254` 的 fresh inspect、明确旧 ID/image 和 CAS；仅正常停止/保留旧 web，再创建新 web。冻结迁移 manifest 仅作 SHA provenance；其它十六个服务的 ID/start/restart/state 前后必须相同。raw inspect/env/Compose 输出进入私有文件，失败保留证据与旧容器，由负责人依据 README 明确恢复，不盲目重试。

另外独立核对了 ops agent 保存的实际 PROD 私有 inspect，未输出 env：现有唯一 volume 的源在 HostConfig 中明确指定；两网络无静态 IPAM 或自定义 links，稳定 aliases 可从 inspect 重建；没有 AutoRemove/VolumesFrom，旧 web 使用 unless-stopped。未发现 clone 会改用匿名空卷或因旧静态 IP 无法重建的实际阻断。未运行 operator apply；最终候选镜像、实时 CAS、HTTP/页面健康仍须在第二阶段执行。

部署和性能尚待验收：正式版本的只读 [PROD HTTP 基线](evidence/2026-10-27-kifu-search/new-prod-http-before.jsonl)仍为 5 次姓名搜索 median **2137.7ms**、max **2203.5ms**，total=504；它不是本次代码加索引后的性能结果。先完成 feature 同步/验证/push → develop merge/push → 父 main submodule 指针 push，再 TEST 正式发布、受控 DDL、实际 EXPLAIN 与完整正确列表/棋盘的 1/4 客户端验收，最后新 PROD 小样本复验。TEST 唯一 collector 不重启、不终止 writer/DB session；旧 183 入口不恢复。若最小切片部署后仍未达预算，按计划的测量结果决定下一必要切片，不能据代码审核提前宣称任务的 200ms 目标完成。

## Task 2b 增量审核：完整内容 guard 与 first-pass 编译缓存

日期：2026-10-27。范围仅 `0f16fdd3c` 的三个 reader/cache 文件、修复 `fec348cae` 及相关测试，以及 TEST operator 将允许的 live Compose 链长度由 11 调整为 `{11, 12}` 的局部修改；不重审前端、索引或首轮业务。

**最终结论：Approved。初审发现的 1 项 Important 已由 `fec348cae` 修复，独立复验通过；没有遗留 Critical / Important。** 初审问题是 `compiled_first_pass.py` 的 header query 使用 `populate_existing()` 加 `defer(reviewed_artifact)`，但 SQLAlchemy 对已持有的 batch 不会因此清除已加载的旧 artifact。命中当前新内容的编译缓存后，`identity.py` 的 raw-player scope reader 再做普通 batch query 时仍会拿到旧 artifact，造成当前有效名字/棋谱被误拒。

最小复现使用已有 `bound_raw_player_bundle`，只操作临时 SQLite fixture：Session A 持有原 batch 并读到 1 条；另连接在 bundle 增加 metadata 字段并更新正确的 `bundle_sha256`；Session B 读当前有效内容、暖缓存得到 1 条；A 再次命中缓存只得 0 条。仅将 `read_compiled_first_pass` 桩为返回 None、恢复原 reader 且保持请求 context 后，A 得到 1 条。实际输出为 `initial=1, fresh_current=1, cache_hit_held=0, original_reader_held=1`。此问题不是缓存 hash 碰撞，而是 compiled 分支之外继续可见的旧 ORM attribute。

最小修复已落实：clean header 路径显式 `expire(batch, ["reviewed_artifact"])`，不执行 SQL，也不失效本语句 fresh 小字段；miss 仍由既有 undefer query 同时获取 artifact、新 guard 和标量。新增 held raw-player cache-hit 回归确认 A 现在仍返回 1 条、后续 scope 读取看到当前 artifact。独立运行 `pytest tests/web_ui/test_kifu_compiled_first_pass.py tests/web_ui/test_kifu_identity_context.py -q`，最终 **30 passed in 3.48s**；代码差异空白检查和 operator AST 解析通过。没有重复前端或全量回归。

其余 delta 边界已独立逐段核对：每次 guard 与小字段来自同一 SQL，miss 完整 artifact 与新 guard/scalars 也来自同一 SQL；cache key 包含当前状态、bundle/inventory/source 标量及完整 artifact 原文 SHA。缓存仅替代纯 first-pass membership/shared-displays 编译，活 candidate/research、name/evidence、owner/source、creation ledger 和 scope 仍验证；两个现有 ledger query 在 clean 路径增加 `populate_existing`，SQL 数量不变。混合证明族、dirty Session 及不支持的 guard 使用原路径。LRU 只保留内部生成的 marshal bytes，64MiB payload / 1024 项 / 单项 1MiB，读取私有 decode，编译/解码不在共享锁内；超限仅不入缓存，不改变当前完整校验结果。没有新增 MVCC 协议、预热 hook、schema 或数据库写入口。

operator 的 `{11, 12}` 调整只接纳首轮部署已经产生的第十二层 live Compose override，仍保留唯一绝对路径、live hash、完整 effective config、CAS 和非 web 保持检查，没有独立阻断项。

本增量审核未发布服务。首轮 TEST 已证明正确性但完整 paint 仍为 563–3804ms，200ms 未达；不能用一次 SQL SHA 时延或缓存命中推断最终目标。按最新收敛要求，审核后仍须重复 feature/develop/父 main 发布顺序，仅 TEST 先跑 quick 11 contracts 与最多 6 次真实 paint，区分 hit/miss/首次不同姓名；若明显未达，立即停止扩量并诚实报告，不自动追加大样本、4 客户端或网络组。PROD 保持原版本直到 TEST 门禁通过，唯一 collector 与其它非 web 服务继续保持。
