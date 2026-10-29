# Galaxy 棋谱搜索 Prepared Read Path Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将完整名称及来源证明移到导入、审核与发布准备阶段，使云端搜索只读取已确认映射和展示数据，同时保留实时失效、完整结果、精确 total、排序分页和正确首盘 preview。

**Architecture:** 保留 PostgreSQL 和现有公共 JSON 契约。增加仅服务棋谱搜索的持久准备结果；业务写事务通过数据库失效触发器和受控准备函数同步维护它们。在线事务检查准备状态、读取映射与页面展示，继续使用现有黑白 ID 索引、可见性过滤及有界报告/段位查询，不再执行名称/来源 proof 或首次编译。

**Tech Stack:** PostgreSQL 15、SQLAlchemy、FastAPI/ASGI、React/Vite；SQLite 保留本地兼容路径。无 Redis、HBase、消息平台或 MVCC 行版本推断。

**授权与版本说明：** 原计划于 2026-10-27 完成两轮独立 Astra Max 审核；用户于 2026-10-28 明确授权实施与发布。2026-10-29 用户进一步明确：1 QPS 的 20ms 仅作诊断，硬目标为实际线上 8 核机器在 100 QPS 下每个请求完整响应不超过 200ms。下述对应实现和验收段按这项最新指令更新，不重开整份计划审核。旧基线、失败样本和资源窗口调整继续保留，实际执行证据见运行手册。

| 十步简述 | 现在具体做什么 | 后续怎么优化 |
|---|---|---|
| 1. 接收请求与参数检查 | 校验语言、页码、page_size、q/player_id；进入有界 worker，创建同线程 Session | 保留；补完整 ASGI/入口计时，包含排队及序列化 |
| 2. 判断搜索意图 | `unique_exact_player_id()` 对四种名称域探测，再做 proof 与碰撞检查 | 明确 player_id 直接走棋手路径；自由 q 查询准备好的统一词条，无需重新证明或加载四域 artifact |
| 3. 姓名、别名映射到 ID | `strict_matching_names()`、`matching_entity_ids()` 等动态解析已审核名称、legacy 别名及同名关系 | 写入阶段生成可查映射；在线保留一次有索引查找和同名集合，不丢别名或未归并棋谱 |
| 4. raw scope 与赛事选择 | 动态核验 raw 玩家/赛事范围、selected GN、来源成员和选用审批 | 准备精确的允许成员关系；在线读取既有范围，不做来源追溯；明确棋手路径跳过无关赛事探测 |
| 5. 筛选可见棋谱 | 按黑/白棋手 ID、raw 范围、日期/赛事/模糊条件筛选，排除隐藏与重复 | 保留正确谓词和现有索引；通用 q 的含义与排序不变 |
| 6. 精确 total 与分页 | 独立 COUNT，按日期降序/nulls last、ID 降序取当前页 | 保留；同一读事务取得一致的 count/page，不用估算或截断结果 |
| 7. 证明名称、来源并生成展示 | `_qualified_name_rows()`、first-pass、orthographic、composition、event selection 等反复验证、加载/哈希 artifact | 完整证明移到导入/审核/发布准备；在线只查 ready、有效标记和版本，再读已确认展示字段 |
| 8. 段位和报告可用性 | 当前页批量查询 rank snapshots、report availability，保持内容绑定和完整性 | 先保留已测约 4ms 的有界检查；不在本次扩建报告/段位写模型；仅实测仍阻塞目标时再单独决策 |
| 9. JSON 与首盘 preview | 组装 20 条摘要及第一页首盘完整 SGF，FastAPI 校验/序列化并发送 | 保留完整字段；仅首盘需要完整 SGF，计入序列化与最后 body 发送时间 |
| 10. 浏览器展示 | Abort/响应代次防串线；解析 preview；loading 卸载棋盘；卡片逐项 Fade | 保留正确 selection/retry；去不必要渐入，复用棋盘实例，分别报告真实可见列表/棋盘时间 |

## Chunk 1: 目标、数据契约与安全边界

### 1. 规划时基线与当前验收合同

- 下列基线保留 2026-10-27 规划时事实；当前实际发布以运行手册为准。当时 fresh `origin/develop=06d8e732f2c9cb956c76d9c9806f3f3584adcd43`，TEST 为该版本、三条搜索索引及纯 first-pass 编译缓存；新 PROD `117.50.177.254` 为 `e9b4d3ecce03b3269f12922a476fd6d6c6545547`。
- 真实规模约 176,884 albums；现有 11 组契约结果已等价。TEST 王星昊暖 API 曾为 166–249ms，重复样本 237.8ms；该样本 candidate 79.530、display 134.255、count 2.370、page 4.063、report 3.159、rank 0.935ms。各数来自特定样本，不能混加不同请求的最小值。
- 一力辽首次样本 display 3.06s；已有页面涉及 18 个 first-pass raw 赛事名与一个 orthographic 棋手名，未记录各缓存 hit/miss，不能把这段全部归为纯编译。
- 11 批次完整 artifact SHA 单次只读探针约 59.5ms。只持久化 SHA 不能移除其它 proof、来源验证或冷编译，因而不是本方案的完成条件。
- 原浏览器指标与新 API 指标分开：当前暖 response→首次 clearRect 69–85ms；之后两帧确认/校验 28–48ms。已有 349ms 样本未验卡片最终 opacity，不称作“全部列表完全显示”。
- 证据沿用 `release/kifu-search-test-evidence-20261027@3ce0c1dd0a1ddeb0e38f394e406730cbe7d2f187` 中的 `docs/superpowers/reviews/2026-10-27-kifu-search-validation.md` 和对应 evidence；实施前不为计划重跑 profile/扫描 artifact。

**当前验收合同（2026-10-29 用户明确更新）：**

| 项目 | 建议执行口径 | 通过条件 |
|---|---|---|
| 棋手搜索：低负载诊断 | 已 ready、已建连接，1 QPS；player_id、棋手姓名及合法别名，包含该 q 的完整同名/raw/碰撞语义；server ingress 收到请求至完整 JSON 最后 body 交付 | 20ms 为参考，不再拦截高负载或发布；p50/p95/p99/max、样本数实报，错误率 0、语义差异 0 |
| 棋手搜索：负载主门禁 | 实际线上 8 核机器，或经主会话明确认可的等效配置；100 QPS 固定到达率，包含服务端排队；使用同一棋手查询域 | 本轮所有请求完整响应均 ≤200ms；实报 p50/p95/p99/max、>200ms 数、超时及其它错误；错误率 0、语义差异 0，30 秒入口与实际发出均 ≥2970；不能仅以 p95 达标放行 |
| 主门禁精确清单 | 24 个冻结的棋手查询、至少 12 个不同棋手，覆盖 cn/tw/jp/ko/en、页2、合法别名、同名与 raw 未归并；固定 50% 唯一姓名、25% player_id、15% 别名/同名、10% 含 raw 结果的棋手姓名 | 按现有契约和代表数据，在同一快照核对 legacy/prepared 完整 JSON 后保存期望；已授权口径不重复确认。每个首次不同棋手均入样，不能用 ID 替代姓名 q、减少字段/结果或靠混合分位隐藏慢族 |
| 通用兼容域 | 赛事、日期、任意模糊、无条件页及真实无结果查询，五语/翻页单独核对 | 保留原结果/排序/分页语义，性能与样本单列，不自动扩展为同一个 20ms/200ms 门禁，也不放入主负载比例稀释结果 |
| 首次访问 | 重启后 ready，不预先请求目标棋手；准备结果已持久化 | 新棋手首查不触发 proof、纯编译、补数据或慢 fallback；不把冷 TLS 纳入 API 指标 |
| 浏览器 | 固定 viewport，真实 20 条列表、当前首盘、正确标题/棋子；另测公网条件 | 单列请求、响应→实际可见列表、正确棋盘绘制；原完整 200ms 愿望单列实测，不由 API 20ms 推导 |
| 未准备/失效 | 明确的 503 与错误码 | 从成功延迟统计外列出，但计入可用性/错误率，不能用它们或空结果“达标” |

200ms 指完整请求，不能仅报 PostgreSQL 毫秒或现有 `kifu_handler`。ASGI 入口至最后 `http.response.body(more_body=False)` 计时包含执行器排队、IPC、DB、Python、Pydantic、JSON 和 send；完整 HTTP 请求补充 ASGI 之前的接收/代理排队。分别实报生成器排队、HTTP−ASGI 和 ASGI 内的逐请求差值，不混加不同请求的分位。公网 RTT、TLS 首连、5Mbps 带宽及客户端 parse/paint 分列。若入口不能观测接受队列，则报告覆盖缺口，不宣称包含它。TEST 当前 192 逻辑核且无 CPU 配额，不能直接代表线上 8 核；最新授权允许在 TEST 通过后，对新 177 做经聚焦 OPS 审核的短时受控 100 QPS 验证。

### 2. 旧→新请求流与明确移出的调用

```text
旧：请求 → worker → 四域候选/proof → 精确 COUNT/分页
    → selected-event/proof → strict/fallback display/proof
    → 报告/段位 → summary/首盘 SGF → 序列化/发送

新：请求 → worker-owned readonly transaction → prepared state/策略版本
    → prepared lookup / 现有 player_id → 同一可见性/范围谓词
    → 精确 COUNT/分页 → 当前页 prepared display + 当前 album 字段
    → 有界报告/段位检查 → summary/首盘 SGF → 序列化/发送

写：业务变更 → DB 原子标脏/失效 → 完整 proof 与依赖闭包准备
    → 写入准备结果/覆盖信息 → 同事务提交业务与 ready 结果
```

从 prepared 在线分支移除以下调用；它们保留为准备器的唯一语义权威及 legacy 回滚路径，不删除校验代码：

- `library_search.unique_exact_player_id()`、`public_player_id()` 内的 `_qualified_name_rows()`。
- `identity.strict_matching_names()`、`matching_entity_ids()` 内动态审批/proof 分支；用准备词条表达相同匹配优先级、legacy/historical 提示及碰撞。
- `identity.live_event_selections()` / `strict_selected_event_search_ids()` 对 `event_selection.verified_selection_rows()`、来源/ledger/history 的动态验证。
- `strict_display_maps()`、`display_maps()`、`_approved_raw_player_names()`、`_approved_raw_event_names()`、`_linked_live_members()`、`_raw_event_map()` 的动态证明与 scope 重建。
- `_qualified_name_rows()` 整个入口，包括 first-pass `persisted_eligible()`、orthographic `persisted_name_eligible()` / `verified_source_live()`、transliteration、normative ja/zh、legacy-negative、composition 依赖核验、artifact SHA/编译查询全部离开在线请求；同样移出 `first_pass_cn.valid_override_search_ids()` 的动态 proof。
- `_obscured_program_event_ids_loaded()` 的 SGF/GN 判定、`resolve_strict_display()` 的安全回退选择移到 album display 准备。展示中的“未审核/不可用”标签仍可作为完整证明后的合法输出；缺准备数据不是该标签的理由。

`_summary()` 拆出“已有准备 display + 当前 album 标量 + 当前 rank”组装入口；在线不再次调用名称 proof 或自行回退到 raw 字符串。单盘 `/albums/{id}` 使用同一准备展示来源，避免列表与详情不一致。准备覆盖域为**所有现有详情可读 album**，包括 hidden 和 duplicate；列表仍使用原来的隐藏/重复过滤，不能借改造将详情改成 404。`/analysis` 的完整分析读取与安全逻辑不属于本次重构。

### 3. 最小持久数据结构

新表不进入原审批包、inventory、canonical before/after images、undo journals、native publication receipts 的业务哈希。它们可从业务数据重建；不得给旧业务表添加会改变通用 `_image()` 字段集的缓存列。使用独立 SQLAlchemy Core MetaData，不注册进已有 `Base.metadata`，避免已有 `create_all()` 入口自动创建生产准备表。表名和列职责在 Task 1 固定，不扩成通用缓存框架。

| 表 | 最小字段 / 索引 | 职责 |
|---|---|---|
| `kifu_search_prepared_state` | singleton PK、`policy_version`、`enabled`、`ready`、`initial_coverage_complete`、`prepared_at`、准备 `phase/cursor` | 全库姓名映射覆盖/策略门闩及与批提交原子更新的 checkpoint；ready 不是进程健康的同义词 |
| `kifu_search_prepared_names` | PK、`name_kind`、`source_name_id`/legacy key、`lang`、`display_name`、`normalized_term`、`match_class`、`owner_id`、`eligible`、`exact_group_authorized_ids`（有限集合，默认空）、`valid`、`policy_version`；原 display/SQL lower、token/kind/owner 索引、源 key 唯一约束 | 单行公开资格与 exact/shared 同名集合授权分别存储；`valid=true,eligible=false` 明确记录已检查但不可公开，不可因单行合格就扩张同名集合 |
| `kifu_search_prepared_members` | `prepared_name_id`、`album_id`、`slot`（black/white/event）、必要的 event/selection 约束；复合唯一、album 反查索引 | 只存必须有限限定的 raw/selected scope，不把 raw 名称无条件扩展到全库 |
| `kifu_search_prepared_displays` | `(album_id,name_lang)` PK、`valid`、`policy_version`、display 黑白/赛事、sources、obscured/selection 结果、严格模式输出 | 所有详情可读 album 的五种名称语言最终展示；不复制 SGF、整 artifact 或分析 moves；轮次按请求语言在线轻量格式化 |
| `kifu_search_prepared_dependencies` | `target_kind`/target key、`input_kind`/input key；正/反向复合索引 | 名称/展示的实际依赖及范围 watch key，供**写时**定位失效闭包，在线不遍历证明图 |
| `kifu_search_prepared_dirty` | `(input_kind,input_key)` PK、原因/首个时间；有限去重集合 | DB 强制记录变更，包括新插入、无现有名称行的 owner 和 scope 成员；不会因“查不到旧 prepared 行”漏失效 |

这些是一个棋谱读契约的覆盖、映射、有限范围、展示和失效记录，不增加跨业务队列、工作流引擎或多级缓存。`prepared_at` 只供诊断，不是有效性证明。先不增加持久 artifact SHA：完整 proof 已移到准备阶段，只有准备器实测存在重复哈希瓶颈才提出局部派生摘要；它不得重新成为逐请求门槛。

依赖包括真实读取的 batch、change、evidence、source registry、owner/name、source associations、event selection，以及**集合变化** watch key（raw 字面值、棋手/赛事 owner、album/source scope）。另必须登记 `(名称域,lang,normalize_alias(display))` 的正/否定 token 组 watch，观察该组全部 relevant verified 行及其状态，包括不通过单行 proof 的行。新 INSERT、改名、状态变更、撤销、删除均记录 old/new token；准备闭包重新计算整组的 `_finite_shared_player_ids()` 授权及依赖，不能只准备新 owner C 后清脏。无需增加新表，使用 names 中的有限集合字段及现有 dependencies/dirty key。仅记录现有行 ID 不足以捕获新 INSERT；缺失/否定查询同样登记 watch key。无法精确定位的已知证明输入变更使全局 ready=false，须显式修复；不猜测其无影响。

触发器从实际 OLD/NEW 捕获名称域、语言、原始 display 到 dirty key/载荷，准备器用原 Python `normalize_alias()` 生成 old/new 组闭包；不假设 PG15 的 lower 等于 Python NFKC/casefold，也不信任写调用者提供的 normalized key。若输入无法精确归组，保守标记对应域待重建，未完成不得 ready。在线只在**实际 SQL 命中的合资格 owner 集合**与已准备授权集合相等、且原跨域条件成立时使用 shared 扩张；不能仅因 normalized token 相等就并入整组 IDs。

`match_class` 至少区分 approved exact、legacy exact/alias、historical/provisional generic；保留当前“先 exact 再 generic”和同名语义，不把所有词条简单 OR 造成结果扩张。exact 候选仍执行原各域 SQL 规则，例如 `display_name = q OR lower(display_name) = q.lower()`；`normalize_alias()` 的 NFKC/casefold/空白归一仅用于原本使用它的后筛及集合授权，不能用 `normalized_term == normalize(q)` 替代 SQL exact 而扩张命中。

名称输出只准备 `name_display_language()` 所映射的 cn/tw/jp/ko/en；de/es/fr/ru/tr/ua 继续读取英文姓名。轮次仍在线执行轻量 `display_round_name(record.round_name, requested_lang)`，保留俄语等原契约，不额外物化六种名称语言。`policy_version` 的实际比较值须绑定代码规则版本、严格模式、语言映射及所用静态提示资产版本；切换严格模式或影响展示/搜索的规则必须重新准备，不能只比较手填的 generation 数字。

### 4. 写入、撤销、来源变更与事务

| 触点 | 当前代码位置 | 必须完成的契约 |
|---|---|---|
| 名称 apply/undo、artifact/status/journal | `katrain/web/kifu/name_batch.py`: `apply_bundle()`、`undo_batch()`、`_locked_write()` | 在最终状态和 journal 写完后、commit 前 prepare 受影响 owner/范围/album；失败回滚全部 |
| 小时导入、TEST→PROD receiver、rank correction/undo | `katrain/kifu_ingest/catalog.py`: `_publish_prepared()`、`_publish_rank_correction()`、`undo_publication()` | 复用既有锁/接收审批，纳入所有新增及历史 scope 受影响 albums；receipt 成功前完成准备；重放亦校验 ready |
| 赛事 GN 选用与撤销 | `katrain/web/kifu/event_selection.py`: `apply_bundle()`、`undo_batch()` | 新/旧 selected_raw、event、album、来源范围全部进入闭包；不能保留撤销前显示 |
| 棋手去重/合并、alias、归属重连 | `katrain/web/kifu/player_duplicate.py`: `run()`、`undo()`；`kifu_ingest/catalog.py` identity/owner 更新 | survivor、retired、raw 与受影响黑白 slots 同步准备；同名多个有效 ID 仍完整返回 |
| 原始 SGF/元数据/隐藏/重复/来源关联 | `scripts/import_kifu.py`、`katrain/web/kifu/provenance.py:ensure_album_source()`、`catalog.py` | DB 先标脏；受控导入在原事务 flush 后准备，禁止提交新 album 后靠搜索补齐 |
| 旧 repair/catalog 脚本及直接 SQL | `katrain/web/kifu/catalog_*.py`、`player_*.py`、`event_*.py` 等现有写入口 | 不逐一无关重写；数据库触发器兜底失效。未适配工具明确报告需 prepare；启用前列明仍在使用的入口，不得影响现行唯一 collector |
| source registry、evidence、ledger 变更/删除 | 对应 `models_db.py` 表及上述受控写入口 | 即使名称本身没变，也失效依赖结果；反查 batch/change/evidence/source 和集合 watch key |
| rank/report 更新 | `player_ranks.py`、`kifu_ingest/catalog.py`、`cron/jobs/kifu_analyze.py`、`cron/analysis_repo.py` | 本轮不复制其资格状态，继续在线批量查当前数据；不得因准备 display 固定 has_analysis 或 rank |

**真实 writer 版本切换表（enable 的前置条件）：**

| 执行入口 | 既有 engine / 代码加载方式 | 提交前 hook 与换版要求 |
|---|---|---|
| TEST 唯一小时 collector | `katrain/cron/jobs/kifu_ingest.py` 常驻进程启动时 import `catalog.publish_manifest`；传 `katrain.cron.db.engine`，来自 `cron.config.DATABASE_URL` / `KATRAIN_DATABASE_URL` | 新 `catalog._publish_prepared()` 在原 Connection commit 前准备；必须发布新 cron image 并在无在途 job/发布的自然安全点受控替换唯一进程，只换 Web 不生效 |
| PROD 固定 receiver | 受限 SSH `kifu-incremental-receive` → root-owned wrapper `/usr/local/sbin/kifu-incremental-receive-root` → `docker exec` 运行 `/app/scripts/kifu_incremental.py receive` → `orchestration._engine()` 的 `KIFU_INGEST_DATABASE_URL`；既有 wrapper 从容器 `KATRAIN_DATABASE_URL` 提供值 | 新进程必须加载已发布包的 `catalog.publish_manifest()` 及 commit 前准备 hook；按 fresh wrapper/容器 inspect 核对实际代码 pin。若 wrapper 指当前 Web 容器，Web 切换后新 exec 已载新包，无需另造 receiver 服务；不得仍 exec 保留的旧容器 |
| 人工名称 apply/undo | `scripts/kifu_name_batch.py` → `name_batch.apply_bundle()/undo_batch()`；`create_engine(args.database_url)` | 运行已发布 checkout/image，库内 commit 前准备；不靠 shell 在命令结束后另补数据 |
| 人工赛事选择 apply/undo | `scripts/kifu_event_selection.py` → `event_selection.apply_bundle()/undo_batch()`；`create_engine(args.database_url)` | 同上；含 old/new selected scope |
| 人工棋手合并/撤销 | `scripts/kifu_player_duplicate.py` → `player_duplicate.run()/undo()`；显式 URL 或原 `KATRAIN_DATABASE_URL` | 同上；survivor/retired/token 组/历史 slots 都准备 |
| 人工 SGF import 与显式修复 | `scripts/import_kifu.py` 使用 `web.core.db.engine`；准备 CLI 使用同一显式目标库/既有身份；其它仍在用脚本逐项登记 | 原 Session flush 后在其 Connection 调 prepare，再 commit；未适配入口只能失效并报告需修复，不允许伪装 ready |

receiver 的实际路径/镜像/目标 DB 以新 177 主机部署核对为准，不能从旧 183 文档推导新地址。现有 `web-only.py` 只执行 Web 阶段，其“全部非 Web ID/镜像不变”保证不能套用到必要的 TEST cron 换版。新 cron 必须保留 stage、key、budget、host pin、session advisory lock 和 `staging_writer_lock`；无在途安全点与原锁共同防止探针后又启动 job 的竞态，不 kill 活动任务、不起第二 collector。若无法取得安全边界或旧 writer 绝对不能换版，则本方案暂不能 enable，先向主会话报告。

数据库迁移安装覆盖相关业务输入的 INSERT/UPDATE/DELETE 触发器与 TRUNCATE 失效守卫；不只监听 `UPDATE OF status`。相关表：players/events、其 aliases/names、raw values/names、name batch/change/evidence/source registry、albums/album_sources/sources、album_event_selections/event_selection_batches；dedup 操作的实际 album/alias 变化亦被覆盖。排除纯分析 moves 高频写表，不增加每步分析的全局锁。

触发器只写 dirty keys、标记对应准备行 invalid、设置 ready=false，不在 PostgreSQL 中重写完整 Python proof。不 hash 全 artifact、不调用模型、不做网络访问。现有迁移方式支持时启用 ALWAYS。**本需求默认保留既有受信 DB owner/运维身份和原业务 engine，不新增必需凭证，不做全站角色切换。** 完整准备器是唯一正常代码写入派生结果及置 ready 的入口；HTTP caller 没有写 ready/valid、提交任意准备值或以 caller-set GUC 自证的接口。普通业务源表 DML 必经触发器失效，只有完整准备器消费全部 dirty、核验覆盖并生成结果后才能置 ready。

这项保证不抵御持有 DBowner/superuser 的可信运维恶意伪造派生表、关闭触发器或任意 DDL。部署时只读核对当前角色属性/权限并记录事实，不能声称另建 prepared owner 就能约束仍持 superuser 的 Web。若发现某在用调用者不应被信任，拒绝 enable 并上报实际权限范围，由主会话另作取舍；不能静默扩成全站身份改造。全部正常 apply/import/prepare 使用原调用者传入的一条业务 Connection/事务，不引入必需的 `KIFU_PREPARE_DATABASE_URL`。凭证不进仓库、日志或接口。

受控准备函数 `prepare_changed(conn, dirty_keys, *, policy_version, budget)` 在**同一 Connection 和事务**内：

```python
dirty = read_dirty_keys(conn)                 # 包括触发器记录的新旧 key
targets = expand_existing_semantic_scope(conn, dirty)  # old/new + reverse deps + watch keys
names, members, dependencies = prove_names(conn, targets)  # 调用原完整 proof
displays = prepare_album_displays(conn, targets, names)
replace_prepared_targets(conn, names, members, displays, dependencies)
clear_only_fully_prepared_dirty_keys(conn, dirty)
assert_no_unresolved_inputs_for_enable(conn)
mark_ready_if_initial_coverage_complete(conn)
```

- 同事务 pending 写入必须由完整准备器读取本连接的最新行；不能用另一 Session 或上次请求缓存证明未提交数据。原 proof 中依赖 ORM 刷新的部分要由 Connection-bound Session/显式 flush 覆盖测试，绝不共享在线 Session。
- 业务写锁沿用现有顺序；再以固定顺序锁 prepared state/targets，所有准备写统一顺序。禁止两个 Session 嵌套争同一 advisory lock。写超预算/证明失败：常规 apply/import 整体 rollback，不能发布半个版本。
- 紧急撤销/来源失效允许原子提交“业务撤销 + invalid/ready=false”，优先收回旧数据；准备失败不能阻止撤销。这条路径明确返回需修复状态，在线 503，禁止仍展示旧审批结果。
- 未适配直接 SQL 同样导致 invalid/ready=false，不能悄悄保留旧映射或通过搜索慢 fallback；离线 repair 工具消费 dirty keys 进行有界修复。DDL/superuser 人工破坏属于运维权限边界，需要发布核对，不能用应用守卫承诺抵御 DB 管理员。
- 在线使用一个只读、一致快照事务（PostgreSQL REPEATABLE READ），依次读 state、映射、COUNT/page、展示及当前元数据。搜索的线性化点是读快照：撤销提交之后建立快照的新请求必见失效；已取得旧快照的在途请求可完成旧快照，不把跨请求旧缓存混入新结果。
- `enabled=true` 时任何覆盖/策略缺失、dirty、invalid、语言缺行：返回 503 `kifu_search_not_ready`，附可重试状态；不返回 200 空列表、少结果、旧名或 legacy 慢路径。一般 health 保持进程含义，另暴露 `kifu_search_ready`；不能把未 ready 实例纳入搜索成功率。

## Chunk 2: 可执行任务、准备与发布

### Task 1: 固定契约与最小 schema/失效守卫

**Files:**
- Create: `katrain/web/kifu/prepared_read.py`（行/协议、readiness、lookup，不放完整 proof）
- Create: `katrain/web/kifu/prepared_models.py`（上述六表的独立 Core MetaData，不进入旧 Base）
- Create: `katrain/web/kifu/prepared_migration.py`（显式建表/触发器、检查定义、权限前置条件）
- Create: `scripts/kifu_prepare_search.py`（唯一显式 migrate/plan/prepare/verify/enable/disable 入口）
- Create: `tests/web_ui/test_kifu_prepared_schema.py`
- Create: `tests/web_ui/test_kifu_prepared_invalidation_pg.py`

- [ ] 写红测试：新增 raw owner/alias、artifact-only 更新、batch undo、source/evidence/change 修改与删除、source association 成员新增、TRUNCATE 均产生 dirty；事务 rollback 不残留 dirty。HTTP caller/函数输入中的 ready/verified/GUC 不能绕过完整准备器；不对可信 DBowner 直接改表虚构权限拒绝测试。
- [ ] 运行 `python -m pytest tests/web_ui/test_kifu_prepared_schema.py -q`，应因 schema/协议尚不存在而失败。
- [ ] 实现上述最小表与有界 key 触发器。默认 disabled，显式迁移才安装生产触发器；Web startup 不执行 DDL。提供 `migrate --dry-run` 和独立 `verify-schema` 检查实际定义/启用状态/权限，不只验证表存在。测试旧 `Base.metadata.create_all()` 不包含新表、旧业务表字段集及 canonical images 不变。
- [ ] SQLite 使用等价的本地表/触发器或明确 legacy-disabled 路径；PG 专属功能不在 SQLite 上伪造通过。PG 集成测试只接受显式隔离库 `KIFU_TEST_POSTGRES_URL`，拒绝 TEST/PROD 业务库。
- [ ] `python -m pytest tests/web_ui/test_kifu_prepared_schema.py tests/web_ui/test_kifu_prepared_invalidation_pg.py -q`；PG job 无 URL 时明确 skip，不能据此宣称验证了生产触发器。
- [ ] Commit: `add prepared kifu search schema and invalidation guards`。

### Task 2: 原 proof 准备器、范围闭包与增量维护

**Files:**
- Create: `katrain/web/kifu/prepare_search.py`（完整 proof、依赖/watch 收集、changed target 准备）
- Modify: `katrain/web/kifu/identity.py`（只加准备调用所需明确依赖输出，不删原 proof）
- Modify: `katrain/web/kifu/name_first_pass.py`、`name_orthographic.py`、`name_composition.py`、`event_selection.py`（准备依赖与范围输出）
- Modify: `katrain/web/kifu/name_batch.py`、`player_duplicate.py`、`provenance.py`
- Modify: `katrain/kifu_ingest/catalog.py`、`scripts/import_kifu.py`
- Verify/adapt only if needed: `katrain/cron/jobs/kifu_ingest.py`、`katrain/kifu_ingest/orchestration.py`、`scripts/kifu_name_batch.py`、`scripts/kifu_event_selection.py`、`scripts/kifu_player_duplicate.py`（保留上述 engine，核对真实包加载及库内 hook）
- Create: `tests/web_ui/test_kifu_prepare_search.py`
- Extend: `tests/web_ui/test_kifu_name_batch.py`、`test_kifu_name_composition.py`、`test_kifu_rank_publication.py`
- Extend: `tests/cron/test_kifu_ingest.py`、`tests/test_kifu_incremental_cli.py`、`tests/web_ui/test_kifu_incremental_catalog.py`（仅发布/replay/undo 的 hook 与 dirty/ready 断言）

- [ ] 写红测试：五语 final display、未审核真实回退、orthographic/source drift、first-pass 内容/ledger/成员变化、composition base 撤销、selected GN apply/undo、raw player rank-only 与有限 slots、同名/alias、未归并结果；准备输出与旧 reader 相同。
- [ ] 加一个“否定依赖”回归：初始无 raw/alias/selection，之后 INSERT 新成员；旧准备数据必须失效并纳入新闭包。只测试现有依赖行变更不足以通过。
- [ ] 最小同名 A/B/C 回归：A/B 已审核 shared_display 并已准备；插入同语言、同 normalize_alias token 的 verified C，C 单行 proof 不合格。必须失效并重新准备整个 token 组，清脏后 A/B 的 exact/shared 授权与旧 reader 一致；删除/撤销 C 后合法集合按旧语义恢复。另测改名 old/new token 和 SQL exact/lower 与 NFKC/casefold 不同的例子，比较完整 ID/total/分支语义，不只 eligible 行数。
- [ ] `python -m pytest tests/web_ui/test_kifu_prepare_search.py -q`，预期失败在缺少准备函数。
- [ ] 实现纯准备函数，复用原 proof 和展示选择代码；依赖只用于写时 invalidation，在线不加载 proof。用 owner/raw scope 去重证明，同一个一致事务内复用不可变编译内容；不以 caller 提供“verified=true”替代 proof。
- [ ] 将 prepare 放到实际业务最终写入后、commit 前；增量范围优先复用 `name_batch._affected_albums()`、catalog publication affected set 和 event_selection 既有范围，补全 token 组的所有 relevant verified 行及依赖。正常入口读 dirty 队列并核对全部已消费，不能只 prepare 新导入盘/owner 而漏历史 raw scope 或 A/B 集合授权。
- [ ] 写两连接并发测试：发布失败 rollback；撤销 commit 后新搜索不能读旧结果；并发插入 scope 成员不能使未覆盖结果 ready；重放不改变业务 receipt/canonical SHA，且检查准备资格。
- [ ] 运行 `python -m pytest tests/web_ui/test_kifu_prepare_search.py tests/web_ui/test_kifu_name_batch.py tests/web_ui/test_kifu_name_composition.py tests/web_ui/test_kifu_rank_publication.py -q`。已知原有失败单列，不通过扩大 scope 顺手修复无关问题。
- [ ] `python -m pytest tests/cron/test_kifu_ingest.py tests/test_kifu_incremental_cli.py tests/web_ui/test_kifu_incremental_catalog.py -q`，只新增本契约所需回归：真实 cron publish 和 CLI receive/publish/replay/undo 走新包后，receipt/hash 不变、触发的 dirty 被同事务消费、ready 保持；未调用 prepare 的旧 writer 必须留下明确 not-ready，而非假通过。
- [ ] Commit: `prepare search names and displays with business writes`。

**并行边界：** Task 1/2 的共享协议必须先稳定；`identity.py`、`name_batch.py`、`catalog.py` 不允许多个 worker 抢改。Task 4 UI 与 Task 2 后端可在协议固定后并行。每个实施任务 fresh worker，spec 后 quality 审核合并为本切片的必要检查；最终独立 Astra Max 审实际数据/并发/失效改动，不重复全量审旧代码。

### Task 3: prepared 在线列表/详情与完整计时

**Files:**
- Modify: `katrain/web/kifu/prepared_read.py`、`library_search.py`
- Modify: `katrain/web/api/v1/endpoints/kifu.py`（`read_album_page()`、`get_kifu_album()`、summary）
- Modify: `katrain/web/core/repository.py`、`config.py`（仅开关/转发需要的变化）
- Create: `katrain/web/core/kifu_http_timing.py`
- Create: `katrain/web/core/kifu_read_executor.py`（仅 Kifu 只读执行，2026-10-29 并发定位后的局部调整）
- Modify: `katrain/web/server.py`（装入仅匹配 kifu 路由的 ASGI 计时/ready 状态）
- Create: `tests/web_ui/test_kifu_prepared_read.py`
- Extend: `tests/web_ui/test_kifu_library_search.py`、`test_kifu_library_worker.py`、`test_kifu_request_identity.py`

- [ ] 写红测试：ready 读成功；不 ready/dirty/policy mismatch/五语缺行均 503；正确无结果仍 200 total=0。把所有在线 proof/编译入口 monkeypatch 为 `raise AssertionError("online proof")`，prepared 列表及详情仍必须通过。
- [ ] 测新旧结果相等：total、完整分页 ID/顺序、display 五语、sources、raw scope、同名/alias、隐藏/重复、report/rank、preview SHA。用现有 fixture 扩展，不建第二套产品 fixture 平台。
- [ ] 加一条 hidden、一条 duplicate 的详情回归：ready 后 `/albums/{id}` 维持原 display/SGF/report 结果，列表仍不返回它们；删除后的 ID 仍 404。详情先确认原 record 存在，再校验准备展示，不能以缺 prepared 行代替原存在性语义。保留 `test_kifu_name_api.py` 的俄语轮次回归，在线轻量 formatter 不参与名称 proof。
- [ ] `python -m pytest tests/web_ui/test_kifu_prepared_read.py -q`，应失败于尚未实现 prepared 分支。
- [ ] 实现同快照读取。player_id 直接查准备好的公共棋手资格；自由 q 先按原 SQL exact/lower 规则查准备词条，再应用原 normalization 后筛、token 组授权及 exact/generic 优先级。保留日期/模糊行为，不把 normalize 相等当 SQL exact，也不把自动识别的一位棋手当作理由跳过仍存在的 raw/同名/赛事结果。
- [ ] 默认不增加搜索控件或新产品模式。已明确的棋手入口传已有 `player_id`；普通搜索框维持 q 的通用含义。若未来新增 `search_kind=player`，必须单独声明语义并测试转发，本任务不以它缩小既有 q 结果。
- [ ] 相同谓词构造 COUNT/page；读取 page 的 20 行准备展示，校验每个 `(album_id,lang)` 完整且有效。批量保留当前 `report_availability()`/`lookup_album_rank_snapshots()` 与原内容绑定；不要把不完整分析或过期段位快照改为可用。
- [ ] 原表只取 page 必需标量；仅第一行读取 SGF 供 preview。若现有 rank/report 检查需要其它行 SGF，则先保留正确行为并记录该成本，不以删检查完成“只首行 SGF”。
- [ ] ASGI wrapper 在收到 scope 起计，最后 body 发送后记总耗时/状态/bytes/request ID；原 handler Server-Timing 保留分段名。最后发送时间不伪装成提前写入的响应头。日志不含查询姓名、SGF、密钥或完整结果。
- [ ] 仅默认 server-mode/PostgreSQL 的 Kifu 列表使用固定 4 个 spawn 读进程；每进程自行创建同角色 Engine/Session，继续原只读 RR、完整查询/报告/段位/SGF 校验，返回完整 JSON bytes。全 Web 仍为单进程，对局、lobby、matchmaker、engine 单例不跨进程。启动时在 ready 边界核对进程/mapper/policy，不预热目标棋手；关闭自然等待只读任务并释放自己的连接。
- [ ] 总 admission 最多 32；取消/超时后，额度须等底层真实任务完成或确实取消才归还，不能因父请求取消而让队列无界。worker 故障明确失败，不隐式慢 fallback；记录实际 worker pool 边界，不能拿父 Engine 的空 pool 代表读进程。SQLite、board/remote dispatcher、注入 factory 保持原行为。通过真实隔离 PG 验证进程连接所有权、完整 JSON/503、取消持额及关闭。
- [ ] `python -m pytest tests/web_ui/test_kifu_prepared_read.py tests/web_ui/test_kifu_library_search.py tests/web_ui/test_kifu_library_worker.py tests/web_ui/test_kifu_request_identity.py -q`；计时测试必须含排队和人为序列化延迟，并验证 event loop 仍可响应。
- [ ] Commit: `read prepared kifu results without request proof`。

### Task 4: 浏览器真实显示、重试与稳定棋盘

**Files:**
- Modify: `katrain/web/ui/src/galaxy/pages/KifuLibraryPage.tsx`
- Extend: `katrain/web/ui/src/galaxy/pages/KifuLibraryPage.test.tsx`
- Modify only if needed: `katrain/web/ui/src/api/kifuApi.ts`、`katrain/web/ui/src/api/kifuApi.test.ts`
- Reuse: `katrain/web/ui/src/galaxy/components/live/LiveBoard.tsx`（先不改全站棋盘绘制器）

- [ ] 红测试：loading 不能显示旧棋谱为当前结果；新列表与第一盘 preview 原子切换；同词 Enter 重试、Abort、快速切换、语言保留手选均保持。
- [ ] 去掉搜索结果逐项 `Fade timeout={200+index*25}`。页面内保留同一 LiveBoard 实例，loading 用遮罩并将当前内容标为不可用，不卸载/重建，也不露出旧标题/棋盘为新搜索结果；新 preview 到达一次性更新 props。无结果/错误仍清楚显示且可重试。
- [ ] 本页不加第二次 SGF parse，不预加载一套假棋盘，不靠隐藏真实 canvas 缩短指标。只有真实绘制阻塞仍存在才改 LiveBoard 内部。
- [ ] 在 `katrain/web/ui` 执行 `npm test -- src/galaxy/pages/KifuLibraryPage.test.tsx src/api/kifuApi.test.ts` 与 `npm run build`，预期相关测试/build 通过；使用 package.json 的现有测试脚本，不安装新工具链。
- [ ] 一次代表性真实 viewport 验证：新词、翻页、无结果及重试；确认正确第一盘/标题/selected ID/棋子，列表 opacity=1。只保留必要截图，不进行新视觉设计或全站重拍。
- [ ] Commit: `keep kifu preview stable during search updates`。

### Task 5: 现存数据的有界准备、切换与回滚工具

**Files:**
- Complete: `scripts/kifu_prepare_search.py`、`prepare_search.py`、`prepared_migration.py`
- Create: `tests/web_ui/test_kifu_prepare_search_command.py`
- Create: `docs/operations/releases/2026-10-27-kifu-prepared-search.md`

- [ ] 红测试 CLI：默认 dry-run，显式 migrate/apply/enable；cursor 可恢复、budget 超出退出非零且不 enable；重复 prepare 幂等；dirty 未清零/coverage 不完整时 enable 拒绝；disable 不改业务数据。
- [ ] 明确命令接口：

```bash
python scripts/kifu_prepare_search.py plan --max-seconds 30 --sample-albums 1000
python scripts/kifu_prepare_search.py migrate --dry-run
python scripts/kifu_prepare_search.py migrate --apply
python scripts/kifu_prepare_search.py prepare --batch-size 500 --max-seconds 1800 --max-memory-mib 512 --resume
python scripts/kifu_prepare_search.py verify --all-coverage --compare-sample 24
python scripts/kifu_prepare_search.py enable --expected-policy-version 1
python scripts/kifu_prepare_search.py disable
```

- [ ] `plan` 首先用小字段分别统计列表可见 albums 与**所有现有详情可读 albums**、不同 owner/raw/name/语言与预计成员上界；仅限 1000 albums/有限相关名称估算实际准备成本，不重新读全 artifact 汇总。展示成本和覆盖预算按后者计算，不能漏 hidden/duplicate。输出预计行数、空间/内存、总时间；若估计超过 30 分钟、2GiB 新关系或 512MiB 进程内存，先报告主会话收敛，不自动放宽预算。
- [ ] 新写数据走 Task 2 原子准备；现存约 176k 数据走显式一次性准备：名称按 owner/raw/token 组 key、所有详情可读展示按 album ID 游标，每批 ≤500 albums。将 `phase/cursor` checkpoint 放在现有 prepared state 行内，与该批准备行/dirty 消费在同事务提交；中断从最后提交批恢复，不新增进度表。不维持跨全库长快照、不重新导入 SGF、不运行 LLM/翻译、不修改业务审批事实。
- [ ] 启用前不向用户暴露半准备数据。准备期间当前线上 legacy 版本继续提供原行为；新包预装处于 disabled 模式，禁止把 legacy 慢路径计入新目标通过。最终在既有 writer 锁下处理剩余 dirty、验证完整覆盖/策略和触发器，再原子 enable。
- [ ] 与唯一小时 collector 共存：每批短事务、有限 statement/lock timeout，遇 writer 活动/锁超时就退出或让出并记录 cursor；不得 kill 活动事务、任意暂停小时任务或无限自动重试。自然空闲点的必要单实例换版按 writer 表执行；新 writer 确实加载 commit 前准备 hook 后才 enable。
- [ ] 全覆盖检查比较 `(所有现有详情可读 album ×五种名称语言)` 所需行与有效准备行、映射、token 组及 raw/selected scope 覆盖、未解析 dirty；列表 visible 谓词保持不变。隐藏/重复谱仍属于详情准备与失效闭包，不只抽样对照 total。无资格名称记录“已检查且不公开”，不能把没处理与不公开混为一谈。
- [ ] 24 组对照覆盖真实王/柯/张涛/一力辽、别名、同名、未归并 raw、赛事/日期/模糊/无结果、页2及五语。迁移过程中变化的行以最终受控重放结果为准，不拼接不同时刻旧/new JSON。
- [ ] `python -m pytest tests/web_ui/test_kifu_prepare_search_command.py -q`；isolated PG 测跨批次更新/INSERT/undo、进程中断恢复、最终 enable CAS/锁语义，预期无缺行/重复/假 ready。
- [ ] 回滚先 disable，使旧 reader 重新执行完整原 proof，保持语义安全并明确恢复慢延迟；然后在相同自然空闲边界回退 writer/receiver 的代码 pin 与 Web 镜像。绝不能先退旧 writer、留下 enabled 的 prepared 读路径。保留新表/守卫及准备证据，不急删数据或卸触发器，不假称旧包仍使用新性能路径。
- [ ] Commit: `add bounded search preparation and cutover tools`。

### Task 6: 聚焦验证、独立代码审核与负载验收

**Files:**
- Create: `scripts/kifu_search_load.py`（仅本 API、固定到达率/有限总数、无通用压测平台）
- Create: `tests/web_ui/test_kifu_search_load.py`（只测计时/分位/错误计数不假报）
- Update: `docs/operations/releases/2026-10-27-kifu-prepared-search.md`

- [ ] 实施结束前独立 Astra Max 审整体实际 diff，重点 prepared 权威写入、DB 失效、原子性、scope、旧镜像兼容；修到通过。计划本轮最多两次审核不自动授权额外计划循环。
- [ ] 一次聚焦后端套件覆盖本计划新测试与直接修改的现有测试；前端相关测试/build 一次。已知旧失败给出 baseline，不重复全库回归或重构无关模块。
- [ ] 负载脚本输出完整响应接收校验、状态/错误、精确 total/首盘 hash/ID 序列、offered/achieved QPS、排队和 server total 的 p50/p95/p99/max、连接数、实际 in-flight、样本与 elapsed；不能只对 HTTP200 快请求算成功率。100 QPS 是到达率，不是开 100 个并发循环。负载发生器限定最多 32 个 in-flight，超出仍计排队/失败，不丢弃慢样本；发生超预算/语义差异应标失败。
- [ ] 冻结 §1 已获授权的主门禁棋手清单/分布：50% 唯一姓名、25% player_id、15% 别名/同名、10% 含 raw 结果的棋手姓名；五语与页2在适用查询内轮换。低负载先完成至少 12 个不同棋手的首次查询，再重复，不将首次新棋手排除。每个姓名 q 保留完整同名/raw/碰撞结果，不能仅保留“明确ID快分支”；逐类实报。
- [ ] 通用赛事/日期/模糊/无条件页/无结果用单独兼容清单核对结果和性能，不进入主负载百分位或比例；本次不为它们扩建全文搜索索引/平台。
- [ ] TEST ready 后重启一次 web，记录 ready 时间，无请求预热目标棋手。低负载 120 请求、1 QPS、24 查询/首次不同棋手/五语/翻页作为诊断，20ms 不再是放行门槛；保留已经取得的样本，不为新合同重复低负载或以热身隐藏冷读取。
- [ ] 正确性成立后，有限 ramp 10/50 QPS 各 5 秒，再 100 QPS 30 秒；按类报告样本数/延迟。每次必要代码修复后才进行新的有界验收，不无限扩样寻找好数字。错误/排队急升、writer 健康异常即止测并保存证据。
- [ ] 100 QPS 稳态窗口固定 30 秒、计划到达 3000 次；必须实际发出并被入口接收至少 2970 次（≥99 QPS，允许 1% 边界误差），否则本轮负载无效/未通过，不能声称承受 100 QPS。任意未发出、超时、失败、缺响应仍入总数及错误统计，错误率须为 0；排空可最多 2 秒但不计入 30 秒内 achieved QPS。分别记录调度→发出及入口→last-body，发生器排队不能代替服务端负载。
- [ ] 新硬门槛按每个请求核对完整 ASGI/HTTP 响应，实报 p95/p99/max、>200ms 数、超时/错误和全部慢样本。TEST 未限额的 192 逻辑核数据仅用于定位；最终须在实际新 177 的 8 核机器或明确等效配置上受控验证。先核 Web/PG 实际 quota、内存和其它服务共享资源，不静默调整配额；若确需资源 delta，先交同一 OPS 审核明确范围。
- [ ] 服务端入口/ASGI 指标与本机持久连接 HTTP 收全 JSON 的 wall time 关联；公网与浏览器另列。不以 handler 时间替代最后 body，不把本机结果称全球网络体验。
- [ ] 同时记录当次 CPU/RSS、DB pool 上限与占用/等待、DB 连接数、磁盘/网络吞吐、响应 bytes 和压缩设置；不额外建设监控平台。带宽以实际 bytes×achieved QPS 计算并标明 TLS/压缩边界，资源规格/worker 数也必须列出，不能用“100QPS”省略硬件前提。
- [ ] 如果移出 proof 后仍未达目标，按当前分段定位，只报告剩余成本及下一必要决策；不自动引入全卡片投影、Redis、额外写协议或提高资源掩盖。首个新棋手仍触发 proof 即实现未完成。

### Task 7: 实施完成后的发布顺序（已获实施授权，逐项以真实门禁放行）

- [ ] Feature fetch/merge 最新 develop，解冲突、聚焦验证，commit/push feature；确认包含所有最新教程/图标/排名改动。
- [ ] merge/push develop；记录发布 SHA。不得以仅部署 feature 代替集成。
- [ ] 更新 `smartbox-software/vendor/katrain` 到已发布 develop；仅 commit/push 父 main 指针，保留用户无关改动。
- [ ] 先 home-ubuntu TEST：保留现有三索引，显式 migrate；旧 web-only CAS 只用于新 Web disabled 换版阶段；随后取得 cron 无在途 job/发布的自然安全边界及既有 writer 锁，受控将唯一 cron 换为含新 catalog hook 的已发布 image。记录旧/新 ID、image、代码 SHA 及保持不变的配置，不能沿用“所有非Web镜像/ID绝不变”的旧发布承诺。
- [ ] TEST 完成旧数据有界准备；经真实新 cron/CLI 入口做一组已批准、有限的正常发布、replay、undo/恢复验证（不新增模型请求、不全库导入），确认业务 receipt/hash 等价，dirty 同事务消费、ready 能保持。使用隔离测试数据或明确获准的小范围 TEST 包；不得为验证撤销无关现有数据。确认下一次唯一 writer 仍用新包，再 enable 并做正确性/负载/真实棋盘验收。任一失败则不推广 PROD。
- [ ] 新 PROD **ubuntu@117.50.177.254**：按实际 Engine inspect/operator 的 web-only 发布方式更新 Web，保持 prepared disabled；保留冻结迁移 manifest、原网络/媒体/SSO/host pin/单 V100 两 engines。迁移/新索引显式执行并检查定义/valid/ready；必要索引 CONCURRENTLY 使用 autocommit，不在 Web startup 建。
- [ ] PROD receiver 在无在途 receive/事务的安全边界核对 wrapper、实际 `docker exec` 目标、包 SHA 和 `KIFU_INGEST_DATABASE_URL` 目标库；若执行当前 Web，新 Web 生效即提供新 receiver 包，验证后保持受限 SSH/sudoers 不变。若另有固定旧包/镜像 pin，只受控更新该 pin，不重启无关 cron，也不能继续运行旧 hook。TEST producer 仍是唯一一个，原 host pin 指向新 177。
- [ ] PROD 受控准备后，使用合法已有包的幂等 replay 核对真实 receiver 新 hook；正常新发布/undo 的实际 writer 路径已由 TEST 同包验证，生产不为验收随意撤销数据。观察自然合法发布后的 dirty/ready；无法验证新 writer 则拒绝 enable。全覆盖/策略/守卫/dirty 通过后原子 enable，先做少量正确性/读延迟/页面复验；再按最新用户目标与聚焦 OPS 审核的短时方案，在实际 8 核主机受控验证 100 QPS，不盲直接压测，不加购资源或静默改 quota。
- [ ] 不操作旧 183 入口、不复活退役 producer。TEST 允许必要的**唯一** collector 安全换版，stage/key/budgets/pin/锁/单实例保持；不 kill 活动任务、不启动第二 collector。PROD 其它无关 cron、PG/GPU/MinIO 不动；不重启 RK、不改设备模式。预算或安全边界不合适则停在 disabled 可回滚状态。
- [ ] 记录 feature/develop/父 main SHA、Web/collector/receiver 的 actual 代码 SHA/image/container（含必要变化）、schema/ready/policy/coverage、writer 单实例与配置保持证据、角色事实、真实 API 分位/网络条件、浏览器正确棋盘结果和回滚开关。目标未过必须明确报告，不能称已完成性能目标。

### 执行停止条件

- 原“仅计划/docs 分支”限制已由 2026-10-28 明确实施授权解除；当前按上述发布顺序与真实门禁执行，不重复请求该授权。
- 实施后若准备结构/范围/权限显著超过本计划（例如要改全站角色或全库业务 images），先回主会话说明具体差异；不借本计划引入平台工程。
- 若真实结果/来源语义不等价、readiness 无法诚实判定、唯一 writer 受阻，停止启用/推广并保留证据；继续正确旧 reader 仅作为显式回滚，性能目标记未过。
