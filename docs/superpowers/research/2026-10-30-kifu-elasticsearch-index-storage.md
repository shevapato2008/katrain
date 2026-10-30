# 职业棋谱 Elasticsearch 建索引与额外存储评估

日期：2026-10-30。范围：只读代码核对、现有 API 样本字节统计和 Elastic 官方资料；没有下载镜像、运行 ES、创建索引、运行旧 prepared、写业务数据库或删除数据。下列 HTTP 请求是实施说明，未执行。

## 结论

约 176,949 盘适合“一盘一文档，PostgreSQL 为主库，ES 为可重建搜索副本”。初始一个 primary、零 replica；原 metadata 只放一份，五语仅放姓名/赛事等小展示对象；SGF、分析 moves、段位来源证明不进 ES。现有首盘预览继续从 PG 读取，报告状态及段位资料按当前页批量查询。

**2GiB 可以作为单个索引 store 的初始停止阈值，不能称为 ES 总磁盘上限或预测占用。** 未建真实索引前，primary 暂按 **0.3–1.5GiB** 作工程估算；首次部署和导入给宿主机预留 **8–10GiB** 额外空间，包含镜像、日志、translog 和临时合并空间。这两个范围均非实测承诺。当前可用约 35.06GB（沿用主调查口径）没有显示明显的容量阻塞，但还需保留现有 PG、Docker 和系统增长余量。

容器 2GiB 内存、1GiB heap、2 CPU 可作为受限起点；这不能证明 8 logical CPU 共用宿主机上的 100QPS 性能。特别是精确 total 和随机深页，必须纳入后续真实验收。

主计划第一轮评审后采用同一物理索引内 `doc_kind=album/term/public-player/sync-state` 的紧凑分类/状态文档，0.3–1.5GiB 仍只是 album 文档的工程估算，不能视为已包含数量未知的分类文档；1,000盘初样本须同时包含相应分类文档，全量分类文档数量及字节另计，2GiB 总 store 停止阈值与8–10GiB峰值预算不自动上调。列表与count必须过滤doc_kind=album。

## 已核对的事实与样本

代码基线：`/Users/fan/.config/superpowers/worktrees/katrain-kiosk-debug/kifu-search-prepared-20261028`，`origin/develop` 基线 `07d1ddce`。

- `katrain/web/core/models_db.py:1054`：`KifuAlbum` 包括原始姓名、身份 ID、赛事、结果、日期、段位、规则、让子、贴目、手数等；SGF 独立为 `sgf_content`。
- `date_played` 是原文，可能为 `1926` 或 `1928-09-04,05`；`date_sort` 是 `String(10)`，可能为 `1926-00-00`。**不能直接映射为 ES date。** 保留 `keyword` 的词典序及 null-last，与当前 `date_sort DESC, id DESC` 一致。
- `katrain/web/api/v1/endpoints/kifu.py:128` 和 `:360`：列表契约仍是 `/api/v1/kifu/albums?q=...&lang=cn&page=1&page_size=20`，返回 `items/total/page/page_size/preview`；仅 `preview` 含首盘 SGF。`page_size` 上限 100。
- 当前 fallback 搜索仍使用 `search_text` / 原始姓名的任意子串 `contains`，完整姓名优先解析身份。仅用 keyword term 不能自动保留全部非完整输入语义；保留子串的具体查询必须写进实施计划。下面的容量范围不覆盖扩张式 ngram、向量、SGF 全文或全文分析 moves。

只读取本地两份已存在 API 响应，各 20 条，合计 40 个不同 ID；没有保存/输出业务正文或 SGF。按 `json.dumps(ensure_ascii=False, separators=(',', ':'))` 计算 UTF-8 字节：

| 样本口径 | 条数 | 均值 | p95 | 最大 |
|---|---:|---:|---:|---:|
| 完整列表 item | 40 | 730.40 B | 710 B | 2,253 B |
| 去掉 `*_rank_source`、`*_rank_origin`、`has_analysis` | 40 | 521.75 B | 571 B | 579 B |

样本均为中文列表，**不是**全库随机样本，也没有覆盖五语名字、额外检索词条或 Lucene 开销。两份首盘 SGF 为 1,164 B / 2,309 B，仅用于确认预览与列表分离，未纳入估算。以 521.75 B 机械乘 176,949 得约 **88MiB 单语 JSON**，只是 payload 尺度，**不是最终 ES 索引大小**。五语小对象和有限检索键后先按每盘约 1–2KiB 未压缩源文档作预算假设，即约 0.17–0.34GiB；实际须用最终导出器确认。

最终索引包含压缩 `_source`、倒排、doc values、内部 ID 和 segments。不能从 JSON 乘一个“标准 ES 放大率”得出可靠数字；0.3–1.5GiB 是为当前有限字段预留的宽范围。官方也指出动态字符串默认同时建 text/keyword 会浪费空间；应显式只建所需字段。[Elastic：磁盘优化](https://www.elastic.co/docs/deploy-manage/production-guidance/optimize-performance/disk-usage)

## 最小文档和 mapping 原则

| 字段组 | 初始类型 / 行为 | 用途 |
|---|---|---|
| `_id` | `album:<id>`，确定性 ID | 重试同一盘用 `index` 覆盖，避免重复；其它文档使用不同前缀 |
| `id` | `integer`，保留 doc values | 当前排序的稳定第二键；不直接按 `_id` 排序 |
| `black_player_id` / `white_player_id` | `integer`，可检索 | 身份精确过滤；不做无关聚合 |
| `event_id` / `event_edition_id` | `integer`，可检索 | 只在现有查询实际需要时保留 |
| `player_black` / `player_white` / `event` | 原文字段，一份 | 响应原 metadata；需要精确检索的字段用 keyword |
| `name_terms` / `event_terms` | 有限 `keyword` 数组，无 doc values | 已授权可搜索的姓名/赛事词条；入库和查询沿用同一规范化规则 |
| `date_sort` | `keyword`，doc values 开启 | 包含不完整日期；`missing: _last` |
| `date_played` | 原字符串 | 显示及日期查询；不让动态日期检测误判 |
| `display` | 五个固定语言的小对象 | `cn/tw/jp/ko/en` 下仅姓名、赛事及必要轮次展示名；不复制整份 metadata |
| `list_metadata` | `object, enabled:false` 或逐字段 `index:false` | 结果、原始段位、规则、贴目、让子、盘面尺寸、轮次、手数、来源等一份展示资料 |
| SGF、分析明细、段位证明、旧 prepared 证明对象 | 无字段 | 从 PG 原数据/当前页批量补齐 |

顶层采用 `dynamic: strict`、`date_detection: false`，保留普通 `_source` 以便返回列表及排查；未使用的精确字段关闭 doc values，不做默认 text+keyword 多字段。展示对象可 `enabled:false`，其用于搜索的有限授权词条独立放入 `name_terms/event_terms`；因此不需要给每个展示字符串额外建立全文索引。不要禁用 `_source` 以换小幅节省，或引入需额外订阅的 synthetic source。

精确姓名使用 keyword/身份 ID，不因“fuzzy”一词引入模糊姓名猜测。少量改名沿用用户约定：查询前小映射展开，形成一次 OR，不建设回写全库的改名工作流。原有任意子串需求如采用 wildcard 或专门 ngram 字段，应独立验证语义、响应时间和空间；不可把分词 match 当作任意子串等价物。

## 建立索引的具体顺序

1. **固定版本和边界，准备有限静止窗口。** 镜像固定 tag/digest；ES 只作为 API 内部依赖，数据目录独立 volume。先记录宿主机可用 bytes、Docker 占用、现有 PG 大小；同时限制应用/Docker/GC 日志和 heap dump，确认 8–10GiB 导入预算。只部署单 ES 节点，不需要 Kibana/Logstash。首次导入推荐与主计划一致：暂停唯一 ingest，等待在途任务自然结束，再建立同一业务库的只读一致快照；最终核验通过后恢复 ingest。
2. **创建一个未对用户启用的索引。** 例如 `kifu-albums-v1`，`number_of_shards:1`、`number_of_replicas:0`，使用上表完整显式 mapping。首次不创建第二个 ES 索引。`index.max_result_window` 方案见下文。若导入期间没有查询，可保留默认 refresh 的闲置优化；如显式关 refresh，则临时设 `refresh_interval:-1`。[Elastic：导入优化](https://www.elastic.co/docs/deploy-manage/production-guidance/optimize-performance/indexing-speed)
3. **PG 只读快照流式扫描，内存组 bulk。** 复用 `httpx` REST，无需新增 SDK。固定公开库的排除/重复/姓名授权规则；在步骤1建立的同库只读一致快照中按主键 keyset 分页（`id > cursor`），每批先取约 500 盘及所需姓名资料，生成 NDJSON 后立即发 `POST /kifu-albums-v1/_bulk`。先完成1,000盘受控阶段，记录store增长和失败后继续同一个候选索引；不创建第二份样本索引。不预导出全量 JSONL、不加载全库、不复制SGF进ES或落盘；既有资格校验确实需要SGF时只从PG按批读取。176,949 盘按 500 盘约 354 批；500 是起点而非最优值，再加请求字节上限，例如 2MiB，先单 worker。
4. **逐项确认并持久化小 checkpoint。** action 使用 `index` 和确定性 `_id`；NDJSON 每个 action 后跟一行 source，最后有换行，`Content-Type: application/x-ndjson`。HTTP 200 仍须检查 `errors` 和每项 status；仅对 429/暂时失败退避重试，mapping 错误停止并记录计数/ID。cursor 只在整批成功后推进。批次只是内存缓冲，不保存业务正文错误日志。[Elastic：Bulk API](https://www.elastic.co/docs/api/doc/elasticsearch/operation/operation-bulk)
5. **导入中检查预算。** 每批检查 `store.size_in_bytes`、translog、宿主机 free bytes 和导入进度。`store >=2GiB` 或触达预先约定的主机余量线就停止推进；监控阈值存在批次/合并时延，不是文件系统硬配额。没有实测前不自动调高。保留默认 translog `durability=request`，不为提速改成 async。
6. **完成静止窗口内的全量核验；非静止窗口仅作风险说明。** 推荐维持唯一 ingest 暂停、自然无在途的有限窗口，在同库只读快照中完成全量bulk并核对公开盘数/身份及抽样内容；步骤7、8最终核验通过后再恢复 ingest，不为首次导入建设并发新增追赶基础设施。只有未采用静止窗口时，才另有扫描期间新增及较小ID晚提交的风险；不能仅凭最大已分配ID断言全部已提交或导入完整。恢复后的小时新增沿用现有导入流程，ES失败保留可重试checkpoint，不能假报搜索已同步。
7. **恢复并验收。** 若步骤 2 显式关闭 refresh，则 `PUT /kifu-albums-v1/_settings {"index":{"refresh_interval":null}}` 恢复默认，随后执行一次 `POST /kifu-albums-v1/_refresh` 再做 count。不要在每个 bulk 使用 `refresh=true`；关闭 refresh 时也不要 `refresh=wait_for`，否则可能一直等待。零 replica 是这个单机方案的最终设置，不是假称稍后“恢复为1”；只有增加第二数据节点并接受双份空间时才考虑1。[Elastic：refresh 参数](https://www.elastic.co/docs/reference/elasticsearch/rest-apis/refresh-parameter)
8. **保持原 API 契约切换。** ES 返回当前页文档及精确 total，按 `date_sort DESC null-last, id DESC` 排序；API 批量从 PG 补齐当前页段位/报告状态及其绑定所需本页SGF，响应仅将第一条SGF写入 `preview`。先确认公开盘数、代表性姓名/五语显示、页1/2与深页、首盘预览及小时新增，再启用读路径；可使用只指向该一个索引的 alias。必须按主计划先核增量hook/目标生效再恢复collector，失败精确还原本次临时状态。旧 PG prepared 清理在确认无旧读写依赖后执行，本报告没有清理任何表。

正式执行后，用 `GET /kifu-albums-v1/_stats/store,translog,segments` 分别记录 primaries / total；用 `docker system df -v`、容器 size、数据/log volume 的 `du` 和宿主机 `df` 分开计量，避免把 volume 同时算进容器可写层。`_disk_usage?run_expensive_tasks=true` 可按需分析字段，但它较重，不作为每批检查。[Elastic：Index statistics](https://www.elastic.co/docs/api/doc/elasticsearch/operation/operation-indices-stats)、[字段磁盘分析](https://www.elastic.co/docs/reference/elasticsearch/rest-apis/index-disk-usage)

## total 与随机深页不能忽略

现有 `total:int` 是精确总量；ES 请求必须显式 `track_total_hits:true` 并确认 `hits.total.relation == eq`。默认只精确计数至 10,000，不能把 `gte` 的下界当作完整 total；精确计数也会付出执行成本。[Elastic：Search API](https://www.elastic.co/docs/api/doc/elasticsearch/operation/operation-search)

ES 默认 `from+size` 最大 10,000；20条/页时最多到第500页。现有 API 支持随机 `page`，此次不改成游标接口。主计划候选 **`max_result_window:200000`** 可容纳当前约17.7万盘的随机页，但堆内存和耗时随 `from+size` 增长；当前末页需收集约17.7万条排序候选，并非只处理返回的20条。高并发深页可能触发 1GiB heap 压力，2 CPU 限制也不保证200ms。100QPS验收针对常用完整姓名页1/2，另以低并发单独验证深页和无查询全库页。不得因容量足够就宣称深页吞吐成立。[Elastic：索引设置](https://www.elastic.co/docs/reference/elasticsearch/index-settings/index-modules)

`search_after + PIT` 是官方推荐的深分页方向，但需要顺序游标而非任意跳页；这里只记录它，不能无授权改变现有分页契约。20万窗口也不是永久全库上限：库量增长到附近时须复评。[Elastic：分页](https://www.elastic.co/docs/reference/elasticsearch/rest-apis/paginate-search-results)

## 存储：分项、峰值与清理后的净增减

下面 GiB 均按 `2^30` bytes；除已知样本/现有关系表字节外均为规划预算，不是实测。最终 `P` 代表全部 primary 的 Lucene store，`r` 为已实际分配的 replica 数。

| 类别 | 当前建议 / 预算 | 计量边界 |
|---|---|---|
| 最终 primary + replica | `P × (1+r)`；初始 P 暂估0.3–1.5GiB，2GiB停止；r=0 | 只指索引 store，不含 translog/日志/镜像；replica=1需第二数据节点才会正常分配 |
| 镜像层与拉取/解压阶段 | 首次合计先留约2–3GiB余量，最终以实际镜像层为准 | 官方9.5.5-amd64示例压缩大小921MB；**压缩下载量不等于宿主机解压镜像大小**，此处不强制选该版本 |
| translog / 节点状态 | 先额外留约0.5–1GiB | 不在 Lucene store 中；随导入/flush变化。当前官方文档阈值10GB，同时说明translog不超过磁盘1%，须按固定版本复核，不能把默认阈值理解为预分配10GB |
| 应用/GC/Docker日志、可写层、临时目录 | 在日志轮转受控前提下留约0.5–1GiB | 默认GC日志单独最多可达2GB，OOM heap dump可能再近1GiB；不收敛这些设置，预算需上调 |
| 首次普通 segment 合并余量 | 暂留约1–2GiB | 临时空间，不叠成永久最终索引；未实测，随merge变化 |
| 全量导出文件 | 0 | 流式PG→内存bulk→ES，不落全量JSONL |
| 旧ES索引保留 | 首次0 | 后续双索引重建需另加一个旧P及新索引导入余量；不得沿用首次单索引峰值 |

镜像数据来自[Elastic 官方镜像目录](https://www.docker.elastic.co/r/elasticsearch)。GC/heap dump边界来自[Elastic：重要设置](https://www.elastic.co/docs/deploy-manage/deploy/self-managed/important-settings-configuration)。translog的落盘、flush和大小边界见[Elastic：Translog](https://www.elastic.co/docs/reference/elasticsearch/index-settings/translog)。

**预算口径：**在上述受控日志和单索引条件下，先按 ES 常态总增量约 **3–7GiB**、首次部署/导入峰值约 **8–10GiB** 管理余量。这是风险预算，不能作为“17万盘实际用掉多少”的结果。不要在初次导入后默认 force merge；库仍按小时写入，官方建议只对不再写入的索引 force merge，且 `max_num_segments=1` 可能需要最多三倍 shard 大小的临时空间。[Elastic：Force merge API](https://www.elastic.co/docs/api/doc/elasticsearch/operation/operation-indices-forcemerge)

现有六张 PG 派生表（state / names / members / displays / dependencies / dirty）本次最新只读清单给出的 `pg_total_relation_size` 合计如下。PROD 与 TEST 位于不同宿主机，回收额必须分开计算。来源：`/Users/fan/.local/share/kifu-prepared-20261028/prod-investigation-20261030/safe-stop-and-cleanup-inventory.public.json`（`checked_at_utc: 2026-10-30T03:42:02Z`）。

| 清理对象 | 已知关系大小 | 换算 |
|---|---:|---:|
| PROD 六表，`ucloud-v100` | 1,607,311,360 B | 1.497GiB |
| TEST 六表，`home-ubuntu` | 1,904,648,192 B | 1.774GiB |

不能减掉 PG 原始 `kifu_albums` / SGF，因为 PG 仍为主库。TEST 的回收发生在 `home-ubuntu`，不能从 PROD 的 `ucloud-v100` 磁盘预算扣除。这里尚未现场验证文件系统实际回收，也没有额外把 PG WAL/备份计成即刻回收。

对每台主机分别令新增 ES 常态实际占用为 `E_host = P×(1+r) + 镜像实际层 + translog + 日志/可写层/状态`，该主机清理后净增为 **`E_host − 该主机实际释放的旧六表 bytes`**。若分别以每端3–7GiB工程范围推演：PROD `ucloud-v100` 约净增 **1.5–5.5GiB**；TEST `home-ubuntu` 约净增 **1.2–5.2GiB**。两端ES实际配置和数据量仍需分别计量，不能合并回收额或套用PROD剩余磁盘。这是情景算术，不保证会节省磁盘。若清理放在验收之后，首次峰值发生时旧表仍在，不能提前扣除回收额。

磁盘告警还应看宿主机总利用率：官方默认 low/high/flood 为85%/90%/95%，单数据节点同样适用，flood会对有关索引加只读块。因此2GiB索引阈值不能替代宿主机余量监控，也不应通过关闭水位保护迁就空间不足。[Elastic：磁盘水位](https://www.elastic.co/docs/reference/elasticsearch/configuration-reference/cluster-level-shard-allocation-routing-settings)

## 尚待实施时确认

最终版本/架构与解压镜像大小、最终字段及子串实现、全库五语实际payload分布、建索引后稳定store和导入峰值、GC/应用/Docker日志与dump配置、有限静止窗口的开始/恢复条件、恢复后的小时新增一致性、精确total与随机深页开销。首次实际导入先完成1,000盘受控阶段，记录store增长和失败，再继续同一候选索引；不为这个测量保留第二份试验索引。0 replica意味着搜索副本故障后需要停用或回退并从PG重建，不能宣称ES层高可用。
