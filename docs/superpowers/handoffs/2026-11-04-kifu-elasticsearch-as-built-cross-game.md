# 围棋 Elasticsearch 实现与跨棋种交接（2026-11-04）

本文对照已发布代码 **R=`fb916f12516dd510080fb736a48a825dc206bc37`**，供国际象棋、中国象棋 agent 复用实现经验。它是现状说明和适配清单，不授权重建、改数据、部署或接入其它棋种。本轮只读代码及已有本地证据，没有查询线上服务、执行导入/重建或重新压测。

历史入口：[10-30 主计划](../plans/2026-10-30-kifu-elasticsearch-search.md)、[10-31 WIP 交接](2026-10-31-kifu-elasticsearch-gemini.md)、[11-02 拼音计划](../plans/2026-11-02-kifu-elasticsearch-pinyin.md)、[操作要求](../../operations/kifu-elasticsearch.md)。旧分支、未勾选清单、固定棋手盘数和旧快照不表示当前状态；下面以 R 的函数和字段为准。

## 1. 真实边界与代码入口

**PostgreSQL 是业务权威；ES 是可从 PG 重建的搜索投影。** ES 决定候选记录、准确总数和顺序，保存已整理的五语显示名称。PG 提供当前页真实业务数据、段位快照、报告可用性及首盘完整 SGF。ES 不是棋谱、名称审核或段位的第二业务主库。

| 入口 | R 中的职责 |
|---|---|
| [search_documents.py](../../../katrain/web/kifu/search_documents.py) | `SCHEMA_VERSION="kifu-search-v1"`、确定性文档 ID、五个名称语言 |
| [search_projection.py](../../../katrain/web/kifu/search_projection.py) | `build_projection_context` 一次资格整理；`project_album_batch` 有限记录投影；`classification_actions` 更新/撤销分类 |
| [search_terms.py](../../../katrain/web/kifu/search_terms.py) | `classify_qualified_names`、`merge_classifications`、`compile_query`；身份 scope 与查询语义 |
| [search_es.py](../../../katrain/web/kifu/search_es.py) | 精确 mapping/analysis、REST 边界、bulk、alias、角色和响应完整性检查 |
| [kifu.py](../../../katrain/web/api/v1/endpoints/kifu.py) | `read_album_page_elasticsearch`、`_enrich_elasticsearch_page`、`_summary`、`/search-ready` |
| [search_sync.py](../../../katrain/web/kifu/search_sync.py) / [name_batch.py](../../../katrain/web/kifu/name_batch.py) | `begin_sync/finish_sync/recover_pending` 和 `_locked_write` 的真实 commit 边界 |
| [catalog.py](../../../katrain/kifu_ingest/catalog.py) / [cron job](../../../katrain/cron/jobs/kifu_ingest.py) | `publish_manifest`、undo、`resume_batch`，原 receipt/manifest 与重入 |
| [kifu_search_index.py](../../../scripts/kifu_search_index.py) | `plan/build/check/activate`、明确 ID/batch 修复，不管理调度器 |

### 存什么，不存什么

同一个物理索引包含 `album:<int id>`、`term:e:<lower 原词的 base64url>`、非 strict 模式的 `term:a:<normalize_alias 后编码>`、`public-player:<id>`、唯一 `sync-state`。长词条 ID 使用同原始字节的 SHA-256，避免 512-byte ID 限制。classification 存有限 owner/name/scope 键，**没有逐词 album ID 成员表**。

实际 mapping 是 `dynamic:strict`、`date_detection:false`：

| 字段族 | 类型和用途 |
|---|---|
| `id, album_id, black_player_id, white_player_id, event_id` | `long`；`id` 是排序兜底，`album_id` 用于 PG 取详情 |
| `raw_player_name_ids, raw_event_name_ids, selected_event_name_ids, selected_event_id` | `long`；只保存实际通过原资格/覆盖规则的关联 |
| `doc_kind, date_sort, player_aliases, event_aliases` 及 provisional 名称 | `keyword`；`date_sort` 可保留 `1926-00-00`，不能照搬成 ES date |
| `list_visible, public, strict_mode` | `boolean`；列表始终过滤 `doc_kind=album`、`list_visible=true` |
| `search_text, player_black_lower, player_white_lower, selected_event_raw_lower` | `wildcard`；`* ? \\` 在查询中按字面 escape |
| `display.<cn\|tw\|en\|jp\|ko>` | 显式子对象；姓名主字段 keyword 不索引，赛事 keyword + `.words`；cn/tw 姓名、赛事另有 `.pinyin` |
| `search_text_pinyin` | text；内容来自同一 `album.search_text`，有拼音分析路径 |
| `metadata, classification, diagnostics, operation_ref` | `enabled:false`；保存必要 payload，不自动分析它们的子字段 |

`metadata` 是 KifuAlbum 标量字段加排序后的 `sources`，排除 `sgf_content/search_text/source_path/created_at`。五语显示在 `display`。SGF、analysis moves、完整审核证据留在 PG。`search_text` 使用已存的 lower 拼接文本，含姓名、原段位、赛事、结果、日期、地点、轮次和来源；它不是全文 SGF，也不是 source_path 搜索。`KifuAlbum.source_path` 是 PG 唯一导入键；`KifuAlbumSource.origin_path` 保留来源关联。source path 不是跨环境稳定 album ID，TEST/PROD 的本地整数 ID 也可能不同。手工导入恢复可用 source key 找回当前 PG ID，绝不能通过读取棋谱文件推断 ES 状态。模型见 [models_db.py](../../../katrain/web/core/models_db.py)，导入见 [import_kifu.py](../../../scripts/import_kifu.py)。

## 2. 查询、语言与前端契约

`GET /api/v1/kifu/albums?q=&player_id=&page=&page_size=&lang=`：q trim 后最长 200；q 与正整数 player_id 互斥；page≥1，**默认 page_size=20、允许 1–100**。11 个 UI 语言仍接受；名称存储 cn/tw/en/jp/ko，其余按既有 `name_display_language` 使用英文，轮次按请求语言本地化。查询语言不由 UI lang 限制。

1. 一次 `_mget` 读 sync-state 和 q 的分类（或 public-player）。带空格拼音再探测去空白的确定性分类；非 strict 才取 alias 命名空间。逐项错误不能当成“分类不存在”。
2. `compile_query` 保留 exact player、授权 shared players、player+raw、exact event/raw event、generic 分支。公开 player_id 必须有资格；没有则零结果。exact 零盘不会改走 generic。raw/selected 覆盖不是“同原文全库可用”。
3. 在同一具体索引执行一次 album search。`track_total_hits=true` 且响应 `relation=eq`；禁 partial，拒绝 timeout/shard failure。通常按 `date_sort desc/nulls last, id desc`；generic 的玩家子串/拼音命中有一级 constant_score 优先，组内仍按日期/id，**不是自由 BM25 排名**。
4. PG 按本页 IDs 一次取记录，校验存在和 visibility，再批量取 rank snapshots、`report_availability`。结果顺序依 ES；items 使用现有响应模型。每个非空页的 `preview` 都是首条完整 SGF，`preview.id==items[0].id`；空页 preview=null。
5. 补齐后再次读同一具体索引的 sync-state，须仍 ready 且 epoch 未变。空结果、越末页同样检查。故障统一 503 `search_unavailable`，不以空 200 掩盖，不自动改用 legacy 全表搜索。

`max_result_window=200000` 保留现有随机页码。超过窗口时先 total-only：offset 已越过准确 total 可回正常空页；仍是有效页则 503 容量失败，不静默截断。全量 build 拒绝源 album count>200000；后续增长仍需监控，当前增量协议不是自动扩容器。深页消耗应独立测量，不能复制 200000 为所有棋种的默认。Elastic 官方说明 `from+size` 成本随深度增加：[分页与窗口](https://www.elastic.co/docs/reference/elasticsearch/rest-apis/paginate-search-results)、[max_result_window](https://www.elastic.co/docs/reference/elasticsearch/index-settings/index-modules)。

段位原值、显示值、origin/source、result、rules、round、sources、has_analysis 都保留。段位/结果不是 ES 重新推断；`_summary` 及原 rank/report 绑定规则负责显示。当前页可能为验证绑定读取多条 SGF，只有首条进入 preview；不能声称“PG 只读一盘”。

前端 [KifuLibraryPage.tsx](../../../katrain/web/ui/src/galaxy/pages/KifuLibraryPage.tsx) 固定 `PAGE_SIZE=20`，消费准确 total、首盘预览和 rank/report；[kifuApi.ts](../../../katrain/web/ui/src/api/kifuApi.ts) 缓存首盘详情 10 秒。迁移不得丢失取消/过期响应保护、同词重试及棋盘与当前选择的绑定。

### CJK、Latin、别名与拼音的真实配置

| 路径 | R 配置/边界 |
|---|---|
| cn/tw 赛事 `.words` | IK `ik_max_word` 索引 / `ik_smart` 查询；不承诺简繁自动互转 |
| jp 赛事 `.words` | Kuromoji；词典和实际 token 需小语料验证 |
| ko 赛事 `.words` | 自定义 Nori tokenizer，索引 mixed / 查询 discard，含有限静态词典规则 |
| en 赛事 `.words` | standard tokenizer + cjk_width/lowercase，无 stemming/stop filter |
| 姓名与精确分类 | 原 lower exact namespace，不全局 NFKC/casefold；alias 单独 normalize，非 strict 使用；同名合并受资格约束 |
| 中文拼音 | pypinyin 为合格 cn/tw canonical 姓名/赛事生成全拼、首字母分类，保留碰撞检查；Go 姓氏多音表另属领域规则。ES pinyin filter 提供姓名/赛事/通用文本补充路径 |

generic 赛事 words 是**同一语言字段内 AND，五语字段 OR**，并非跨字段拼接词项。存在 exact player 资格时不加入赛事 words；Latin 查询仅在对应分支启用拼音补充，不把任意罗马字串当公开身份。历史吴清源/本因坊等显式提示仅用于原允许的非 strict generic 分支。`search_terms.compile_query` 才是完整真值，旧计划的 `player_terms/event_terms` JSON 示例不可直接运行。

## 3. 全量与增量发布协议

### 全量不是在线双写重建

`kifu_search_index.py` 的实际子命令为 `plan, build, check, refresh, sync-ids, sync-batch, activate`。build/check/activate 需要 legacy reads、`KIFU_SEARCH_SYNC_MODE=bootstrap`、显式 `KIFU_SEARCH_BOOTSTRAP_QUIESCENT=1` 和 deadline；build 使用 PG 原 writer 锁加只读 REPEATABLE READ 快照。建一个 `<alias>-<UTC timestamp>-<random>` 候选，先语言探针、分类、首 1000 盘计量，再流式导入和核对 mapping、全体 ID、visible count、分类和样本。

`build/activate --replace` 支持已有 alias 的替换，但仍要求明确维护窗口。候选 refresh 后写 ready state，activate 校验候选再单次 `_aliases` remove/add，并复查 alias。代码使用 `must_exist:true` 且检查 acknowledged/errors，语义参考 [Elastic alias API](https://www.elastic.co/guide/en/elasticsearch/reference/8.19/indices-aliases.html)。这是 **ES alias 操作的原子性**，不是 PG/ES 分布式事务，也不保证整次重建零停机。当前没有不停写的 catch-up/双写重建流程。

### 正常 mutation 的最小顺序

```
原业务 session 锁 → 解析前次 pending → 写 ES pending(epoch+1) 并 refresh
→ PG 业务事务 + 原 journal/receipt → PG COMMIT
→ 从当前 PG 计算有限作用域 → bulk index/delete → refresh → ES ready
→ 释放原 session 锁
```

`name_batch._locked_write` 在原连接持有 session advisory keys `720220261002/720220261003`，跨真实 PG commit 持续保护投影；catalog 另有独立外层 publication guard，不能重复取同 key 自锁。同步启用时缺少 operation_ref 的普通写入被拒绝。直接 SQL 绕开这些入口不在一致性承诺内。

operation_ref 复用 manifest digest+publication key、bundle digest 或原 batch ID。`ChangeScope/_batch_scope/_expand_scope` 合并原 games、journal before/after、undo guard、raw scope；发生公开名称变化时，按黑白 player/event FK 索引扩展关联的既有盘及 selected event，**不只新增 N 盘，也不做每小时全库重建**。scope 可以很大，有限不代表廉价。

存在但隐藏/重复的 PG 记录更新 `list_visible=false`；原 undo 已物理删除的明确 ID 发幂等 ES delete；失效 term 等分类键删除，public-player 按当前资格写 `public=false` 或删除。不是新增删除业务。bulk 每批≤500 actions、≤2MiB，逐项检查；暂时错误仅最多 3 次有界重试，delete 404 视为幂等成功。搜索热路径不自动重试。

| 故障点 | 真实处理 |
|---|---|
| PG 尚未变更，ES gate 建立失败 | 拒绝进入业务 mutation |
| 已知 PG rollback、未发 album bulk | `cancel_sync` 可恢复 ready，epoch 不回退 |
| PG COMMIT 回应丢失 | 保持 pending，凭原 durable receipt/journal 判明；不能因异常就说 rollback |
| PG 已提交、投影/bulk/refresh/ready 失败 | `SearchIndexPending/search_index_pending`；保留业务提交，禁止假 rollback/自动 undo |
| 旧 pending 无法判明、ref/目标/资格变动 | 阻止新操作覆盖；取得原锁后修复或报告，不定时清 gate |
| crash/reentry | `recover_pending` / 原同 manifest 重放读取当前 PG 幂等修复，不重放旧 ES 快照 |

这里的“commit_pending”是跨系统尚未完成的概念：**R 的 ES 状态字面值为 `pending/ready`，没有 `commit_pending/READY` 枚举**。协议有 outbox-like 的待完成职责，但没有新建事务 outbox 表、CDC 或 Kafka；可靠恢复依赖原 journal/receipt 和 writer locks。不要宣称强 ACID 或所有直接写入自动被捕获。

手工 [import_kifu.py](../../../scripts/import_kifu.py) 每个实际 chunk 先落 `0600`、≤256KiB、≤500 source keys 的原子恢复记录，再进入 pending。`repair_manual_import` 通过 source_path/origin_path 找当前 IDs 和旧 IDs，成功后保留摘要，返回 `original_import_status=unknown`；不能把搜索修复成功当原导入完整成功。本轮没有运行该导入器或访问棋谱文件目录。

### Receiver 与恢复入口

TEST 本地修复使用原 batch；PROD 修复复用 `send_verified_manifest`、原 TEST verification 与 SSH `kifu-incremental-receive` forced command，让 PROD 本地 publisher 重入。没有开放任意远端 sync-ID/rebuild 命令，TEST 不直连 PROD PG/9200。[sync.py](../../../katrain/kifu_ingest/sync.py) 验 manifest、receipt、专用 known_hosts，receiver 退出码 3 仅接受匹配原 manifest/publication_key 的 `search_index_pending`；[orchestration.py](../../../katrain/kifu_ingest/orchestration.py) 是 receiver 边界。

`resume_batch` 在 names_ready/test_published/test_verified/prod_published 的相应阶段修搜索后再验证、推进。不要新造 publication key 或跳到 prod_synced。修复使用 `sync-ids` 的明确 IDs、`sync-batch --batch-id ... --batch-type name|event` 的原 batch，或原正常重放；**CLI 没有 `recover-pending` 子命令**，该能力是 `search_sync.recover_pending(engine)`，应经现有受控 operator 调用。不要复制任意内联数据库修复命令。

## 4. 配置、安全、监控和成本

`KIFU_SEARCH_BACKEND=legacy|elasticsearch`（默认 legacy）；同步为 `disabled|bootstrap|enabled`。运行契约要求 ES reads 配套 enabled sync，`sync_mode()` 在 writer/cron 调用时拒绝不兼容配置；Web reader 自身只核 ES state，不证明其它进程 writer 已正确配置。bootstrap 的普通写入 bypass 要求 quiescent 且没有 active alias。显式切 legacy 是操作员回退选择，不能代替修复 pending。R 的运行时 readiness 只核 `kifu-search-v1`、strict、目标和 epoch，并非每次比较代码/完整 mapping hash；新分析链变更必须经过候选 mapping 检查和实际重建，不能只复用同名 schema 字符串就宣称旧索引兼容。

`SearchSettings` 从 `KIFU_ES_URL/INDEX_ALIAS/CA_CERT` 和角色专属 `KIFU_ES_<READ|WRITER|ADMIN>_API_KEY` 或 username/password 读取。远程要求 HTTPS、验证 CA，HTTP 仅 loopback；URL 不含凭据/query，关闭 redirects 和环境代理。默认 timeout=3s、连接数=32（上限128）。Web 共享 async read client；writer 同步；admin 才能建/删索引、切 alias。

[roles.json](../../../deploy/elasticsearch/roles.json) 限 `kifu-search`/`kifu-search-*`：read=`read,view_index_metadata`；writer 加 `index,delete,maintenance`；admin 为该索引族 all+cluster monitor。真正权限靠 ES RBAC，Python role 检查不是服务端授权替代。配置新棋种时需独立 alias/prefix/角色，避免给予跨棋种写权限。

[cron overlay](../../../docker-compose.kifu-ingest.yml) 只为 TEST cron 加 writer key、只读 CA mount、专用 SSH key/known_hosts mounts 和私网；[ES compose](../../../deploy/elasticsearch/compose.yml) 仅启动 ES：loopback9200、私网、TLS、bootstrap password file、证书只读挂载。PROD receiver 也必须加载本机 writer 凭据和 CA；本轮没有 inspect 其私有 wrapper/mount，不能把 compose 示例当现网验证。不要输出 env 全文或把 key/SGF/审核全文提交 Git。

**仓库示例的已知缺口：** R 的 `deploy/elasticsearch/README.md` 尚漏列 pinyin；单 role API 的例子却传整份 roles.json，且使用 `curl -k`，不可照抄作为权限/TLS 验收。compose 引用了仓库未提供的 `./log4j2.properties`，基础 `docker-compose.yml` 也未接全 Web ES 配置。新部署需先准备对应每个 role 的 body、可信 CA 和实际挂载，并检查实际启动配置；这不是“现网一定缺失”的结论。本轮只标明缺口，未更改部署文件。

镜像/插件锁见 [versions.lock.json](../../../deploy/elasticsearch/versions.lock.json)：R 固定 ES9.5.5 amd64/base digest、IK/Kuromoji/Nori/pinyin 包及 SHA-512，复用 [prepare_plugins.py](../../../deploy/elasticsearch/prepare_plugins.py) 的 descriptor/版本检查。本文 API 资料由 Context7 查询官方 Elastic 文档；锁定版本事实来自仓库，不把外部8.19文档称为9.5.5已实测。

资源是**配置/停止阈值，不是实际常驻占用**：1 primary/0 replica、container2CPU/2GiB、heap1GiB、无额外 swap。bulk 与投影运行在 publisher 进程，不全算 ES 容器 CPU。单节点可重建，不是 HA。build 默认1800s（可显式 `--max-seconds`）、index store≤2GiB、起始 free≥25GiB、运行 stop<15GiB；索引 store/translog、镜像、PG WAL、日志须分账。Docker 日志10MiB×3；[jvm.options](../../../deploy/elasticsearch/jvm.options) GC8MiB×4且禁 heap dump；应用日志上限要核实际 log4j2 文件，不能凭缺失示例保证。

监控最低项：`/api/v1/kifu/search-ready` 的具体 index/schema/strict/status/epoch、pending 持续时长、原批次进度及明确错误、`kifu_search_sync_stage` 的 projection/bulk/refresh_ready、HTTP错误/耗时、store/translog/free disk/RSS/CPU。`/health=200` 不代表搜索 ready。state 的 `album_count/visible_count` 不是每次增量持续维护的业务统计 API，total 以实际 album query 为准。没有独立自动告警系统可在此声称已接好。

### 已有测量，避免错误外推

| 证据范围 | 已观察结果 | 不能推导的结论 |
|---|---|---|
| 旧同作用域纯 projection，14056 records / 16602 actions | 45.27min → 213.516s；优化以 raw-event literal 的批内索引替代重复候选扫描 | 不是一整个 fresh hourly job，也不是每新增一盘的成本 |
| R 的 Run100690，2026-11-04 | 正常轮次21m1.393s，发布6盘，包含多个 scope 的既有盘 fanout；5 metadata页+97 SGF=102次源请求；还有模型和 native/API verification | 不能按6盘线性外推或把全轮时长全归 ES |
| 同轮 HOME/TEST ES operation A | 7774 actions：projection148968.379ms + bulk5113.736ms + refresh_ready59.286ms = **154141.401ms** | 不是7774盘全新棋谱，也不是PROD计时 |
| 同轮 HOME/TEST ES operation B | 1003 actions：19613.825 +157.973 +81.600 = **19853.398ms** | actions 包含 album/分类/delete，不等于新增盘数 |
| 同轮 PROD | 两端搜索 ready、列表200及6盘五语各30 checks验证有记录；没有可用 ES 分阶段计时 | 不编造 PROD ES 总时长、CPU/RAM或 fresh rebuild 时长 |

原投影优化范围可追溯至 [projection review](../reviews/2026-11-03-kifu-projection-loop-recovery-final-astra.md)。本轮运行证据为发布 controller 的本地 artifact：`/tmp/kifu-release-integration-20261104/output/recent-backfill-20261104/final-summary.json`，不是长期仓库文件；上表保留必要无秘密统计。Run 的 status=errors/error_count=1 是源 SGF 黑白与 metadata 冲突隔离，**不代表 ES 失败**。旧“17盘 TEST ES184.567s / 双端恢复14m14s”是冻结包恢复，不能改写为 fresh hourly 总开销。

旧计划实际 PROD100QPS×30s、每完整HTTP≤200ms、零错/零差异是验收目标；本轮没有该口径证据，不能用已有 ready、单次列表200、TEST计时或ES took宣布达标。CPU/RAM的实际峰值和完整新建索引耗时也未在本轮复测。

## 5. 给 Chess / Xiangqi agent 的最小适配

### 先承认两个产品的现有边界

以下仅接口定位，读取父仓库已发布 `1879b45797c576e43a93f1448c5e8233a375b7cd` 的 Git 内容；没有修改或宣称它们已接 ES。

| 棋种 | 现有实现 | 迁移前必须冻结 |
|---|---|---|
| Chess | `chess/api/chess_api/kifu_proxy.py` 只读代理云端；`kifu-platform/api/kifu_api/{routes,search,models_db,search_catalog}.py` 的 PG/SQLite查询、source许可、generation/finalized/readiness及缓存边界。`/api/v1/kifu/search?q=&limit=&offset=`，默认limit5、上限50，返回 `{total,games}`；game_id为32位hex | generation可见性、source public_enabled/署名许可、别名及中文展示、year/date/id排序、Elo/result/ECO/opening、PGN/复盘详情；保留proxy错误与参数白名单 |
| Xiangqi | `xiangqi/api/xiangqi_api/kifu_db.py` 只读静态SQLite schema2，`kifu-content`构建；`main.py` 的 `/api/kifu/games`，page_size仅3/5，越末页422，返回games/page/page_count/total；`kifu_view.py` 负责显示 | red/black原名及romanized、event/year、year空值/id排序、moves与fingerprint、缺库/坏库503和正常零结果的区别、整包替换身份、review queue绑定 |

**可复用的 shared protocol：** 业务/内容 authority 单一、稳定业务ID与确定性 projection、显式索引版本/alias、有限幂等 upsert/delete、真实 writer/发布锁、持久 operation_ref+待完成恢复、ready前后版本校验、读写管理权限分离、候选验证/受控切换、故障不伪装零结果、完整响应和完整HTTP验收。

**围棋专属不可照搬：** KifuAlbum模型、SGF PB/PW/BR/WR/DT/RE、Go段位推导、komi/handicap/board replay、五语 name evidence/raw scope/selected GN、同名资格、吴清源/本因坊别名、Go多音姓氏表、Go去重/报告绑定，以及100QPS目标和200000窗口。不要为复用搜索在其它棋种先复制这套名称审核或段位系统。

静态 Xiangqi 若仍以不可变内容包为权威，可让“包 fingerprint/schema → 同代候选索引 → 整体切换”承担一致性，不必凭空加每盘 pending/cron。Chess 则应把 ES projection 纳入现有 generation/finalized 发布顺序，不另造与它竞争的全局业务代际。是否采用 ES 先由实际容量/延迟与部署资源判断；本文不决定替换已足够快的本地查询。

### 每个棋种交回这一张字段表即可开工

| 契约项 | Go R 已有值 | Chess / Xiangqi agent 要填写的最小内容 |
|---|---|---|
| 权威与稳定 ID | PG KifuAlbum.id / album:<id> | 当前model/package ID、source/content去重键；不要按显示名或导入顺序重造ID |
| 可见性/版本 | duplicate/hidden + schema/strict/epoch | Chess generation+source权限 / Xiangqi package schema+fingerprint；count与rows同谓词 |
| 身份/名字 | black/white FK、qualified exact/raw/alias | white/black 或 red/black、可信alias来源、原文/展示/phonetic区分、碰撞规则 |
| 赛事/日期 | event IDs、五语display、date_sort keyword | 当前event/opening/ECO/year/date字段、缺失值、稳定全序；用真样本决定分析链 |
| 搜索文档 | 有限元数据、显示、分类，无SGF | 只索引当前搜索需要的字段；不复制PGN/moves/analysis/audit全文 |
| 返回与补齐 | items/total/page/page_size/preview、PG ranks/report | 保留各自 response model、page/offset语义、Elo/result/许可/详情及复盘绑定 |
| mutation/recovery | 原locks/receipt、pending→commit→bulk→ready | 列出实际导入/更名/撤销/包替换入口、operation ref、已提交判据、有限fanout及删除 |
| 资源与验收 | 单节点预算、完整HTTP/原oracle | 实测语料count/bytes、UI页大小、目标设备/网络/QPS、构建窗口及回退方式 |

### 最小迁移与验收顺序

1. 冻结当前接口与小型真实 oracle：空查询、原文/CJK/Latin/alias、同名碰撞、无结果、页2/末页/越界、来源不可见、详情与棋盘。比较完整响应字段及排序，先写明各棋种与 Go 的差异。
2. 实现当前领域的纯投影/查询，先小语料检查 token、AND/OR、literal特殊字符、大小写/宽度、拼音碰撞；只安装实际需要的固定插件。没有需求不加五语/拼音。
3. 接现有真实发布入口与恢复 authority；让 candidate/新generation在校验前不可见。证明 PG/内容包已成功、ES失败和 commit结果未知各自怎样恢复，撤销/删除怎样同步；直接绕开入口的写法禁止作为正常导入路径。
4. 同一稳定快照/内容包建一个候选，分开量 projection、bulk、refresh、store/translog/RSS/CPU；校验全体ID/visibility、准确total、代表完整响应。切换读路径与writer/receiver配置时检查实际凭据和mount，不能用源码示例代替运行配置。
5. 故障验收只覆盖关键边界：部分bulk、断连、目标/版本不符、pending期间读、ready→pending→ready、已提交重放不重复、撤销删除不残留、前端过期响应；静态包用对应包切换/指纹漂移场景。再测代表真实HTTP和页面，达到当前目标后停止，不扩成全新测试平台。
6. 保留明确回退版本和未完成投影记录。按实际项目流程发布，核 published SHA、内容/index代际和服务健康；验收后才退役旧派生索引/缓存，不能删除业务权威或审计记录。

Go 现有可参考用例是 [contract](../../../tests/web_ui/test_kifu_es_contract.py)、[projection](../../../tests/web_ui/test_kifu_search_documents.py)、[transport/index](../../../tests/web_ui/test_kifu_search_es.py)、[publication recovery](../../../tests/web_ui/test_kifu_search_publication.py)、[raw-event index equivalence](../../../tests/web_ui/test_kifu_projection_raw_event_index.py)。它们证明各自边界的预期；本文没有重跑测试，也不要求其它棋种逐字复制。

## 6. 本次文档核对范围

已对照 R 的 mapping/query/projection/API/models/UI、原writer与receiver、全量CLI、角色与Compose配置、聚焦测试名称及上述固定运行artifact。仅做文档链接、引用路径、diff与秘密检查，不修改产品、数据库、ES、cron或服务。没有新建通用搜索框架，没有实施Chess/Xiangqi迁移，没有把新的小时段位策略或尚未实现的优化写成已上线。

未补造的证据：当前完整PROD100QPS验收、两端实际私有secret mounts/RBAC deny probe、真实CPU/RAM峰值、fresh full rebuild耗时、所有历史prepared表/磁盘清理。未来接手人需要对应任务时再取得这些证据，不能从本文推断它们已通过。
