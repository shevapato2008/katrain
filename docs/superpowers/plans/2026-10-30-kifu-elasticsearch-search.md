# Kifu Elasticsearch Search Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 用 Elasticsearch 文档索引提供职业棋谱库搜索，保持现有列表、总数、分页、段位与首盘棋谱预览，并删除被替代的 PostgreSQL 预计算方案及其磁盘产物。

**Architecture:** PostgreSQL 保持业务主库，ES 每盘棋一个文档；同一物理索引另放有限词条分类/公开身份元数据及一个同步状态文档，不建立另一套关系表。名称、赛事显示内容在索引时整理，在线一次批量读取词条分类和状态，再执行相应检索及当前页必要的 PG 批量读取。复用小时导入的批次、幂等 receipt 和重试，不引入 Kafka、CDC 平台、新 outbox 表或通用依赖失效框架。ES 先在 TEST 验证，再发布到新的 PROD；旧方案停止扩充，切换验收后立即卸载。

**Tech Stack:** 现有 FastAPI / SQLAlchemy / PostgreSQL / httpx；固定版本和 digest 的 Elasticsearch Docker 镜像；pytest、现有固定到达率压测工具、现有 React 页面与浏览器测量。

---

## 0. 范围、真实现状与决策

- 本文件是待用户批准的实施计划。本次仅编写计划、最多两轮独立 Astra Max 对抗性评审及修改；不部署 ES、不下载镜像、不建立新索引。
- 数据是成熟职业棋谱库，以每小时新增为主。不建设假设中的改名、删除业务流程。若确有更名，只在查询前用小型显式映射将输入展开为多个精确词，一次 OR 查询。
- 全量建立一次 ES 索引，后续按已有发布批次中的 album IDs 增量更新；不每小时扫描全库。
- 基线代码为已发布 `origin/develop=07d1ddce9e8808fa6c7b840e1a0cd928048ac4bd`。当前对话工作区可能尚未合入它，执行前必须先同步，不可按旧工作区删除不存在的文件。
- PROD 是 `ucloud-v100` / `117.50.177.254`，不是旧 `117.50.183.169`；现有 8 逻辑 CPU、64GB RAM、约 100GB 根盘。不得重新做全站迁移或替换无关服务。
- 2026-10-30 实核：PROD 新 Web/image 已上，但 prepared 的 enabled/ready/coverage 均为 false，显示数据仅 117000 / 176949 盘，六表约 1,607,311,360B。TEST prepared 仍 enabled/ready/coverage=true，最新六表1,904,648,192B。两端位于不同主机，不能使用同一个“已停用”假设或合并磁盘回收额。
- 旧 +900 秒续跑授权已撤回；后续不修复、不重试旧准备工具。已提交的 prepare05 只到 Docker create HTTP400，没有创建/启动容器；保留真实失败账，不将其当作数据生成成功。
- 实测公网“王星昊”801ms、“吴清源”11581ms，后者约10923ms在旧显示核验。TEST 100QPS 的 HTTP max199.347ms 不代表正式环境已达标。
- 用户硬目标：实际 PROD 100QPS 的代表性姓名搜索，完整 HTTP 每请求≤200ms，错误及语义差异为0；1QPS 20ms只是诊断，不是硬门槛。公网及浏览器体验另外实测，不拿 ES `took` 替代完整请求。

### 现有步骤如何替换

| 步骤 | 当前工作 | ES 后的处理 |
|---|---|---|
| 参数校验 | q、player_id、lang、页码、page_size | 保留轻量校验与原422行为 |
| 名称处理 | 查审核历史、别名和名称资格 | 在线只做规范化和可选的显式词条展开；现有已确认名称在建索引时读取 |
| 搜索 | PG 多表匹配或 prepared members | ES keyword 精确匹配；赛事/日期/原有子串模式按冻结契约覆盖 |
| 排序、总数、分页 | PG COUNT/排序 | ES `track_total_hits=true`，固定排序和页码 |
| 显示名称 | 逐请求核验证据、整理五语名称 | 文档 `_source` 中读取已整理的名称 |
| 段位、报告 | 当前页查询 | 复用当前页批量 PG 查询，保留真实来源和报告判定 |
| 棋盘/资格 | 首盘预览；本页报告/段位依赖SGF绑定 | PG仍批读本页必要SGF，只将首条写入preview；ES不存SGF |
| 并发执行 | 4个独立 Python 读进程、IPC | Web 内异步 ES HTTP client；必要 PG 批读放有界线程，移除专用四进程 |
| 维护 | 六表、source triggers、dirty、policy hash、全量重建 | 一个索引、既有发布后幂等增量同步、一次性导入脚本 |

## Chunk 1: 契约、文档与索引（只建设当前搜索所需能力）

### Task 1: 冻结真实搜索与响应契约

**Files:**
- Read: `katrain/web/api/v1/endpoints/kifu.py`（`KifuAlbumSummary`、`KifuAlbumDetail`、`KifuAlbumListResponse`、`read_album_page_legacy`）。
- Read: `katrain/web/kifu/{identity,library,library_search,player_ranks,round_names}.py`。
- Read: `katrain/web/ui/src/{api/kifuApi.ts,types/kifu.ts,galaxy/pages/KifuLibraryPage.tsx}`。
- Create: `tests/web_ui/test_kifu_es_contract.py`。
- Create: `docs/operations/kifu-elasticsearch.md`（执行记录和资源清单，不保存业务全文）。

- [ ] **1.1** 建立实现 worktree，先 fetch/merge 最新 develop，保留当前未提交文件；不要为了写文档复制整套依赖。记录基线SHA与两端 backend 状态。
- [ ] **1.2** 冻结至少24个真实只读 case：王星昊、吴清源、其它不同棋手，q/player_id、历史中文到罗马字词条、无结果、空q、赛事、日期/子串、页2和深页。期望包括完整 items、total、顺序、rank/source、has_analysis、preview SGF SHA。私有全文0600，仅提交无敏感统计及 case 定义。
- [ ] **1.3** 显式保留：`GET /api/v1/kifu/albums?q=&player_id=&page=&page_size=&lang=`；q与player_id互斥；page≥1、page_size≤100；items/total/page/page_size/preview结构不变。第一页非空时 preview.id 必须等于 items[0].id。
- [ ] **1.4** 列表继续排除 `duplicate_of_id!=NULL` 或 `list_hidden_reason!=NULL`；详情可读取的记录范围不借迁移收窄。日期排序使用原 `date_sort DESC NULLS LAST, id DESC`。
- [ ] **1.5** 保留11个UI语言入参。五个名称语言为cn/tw/en/jp/ko，其余de/es/fr/ru/tr/ua按原规则显示英文名称，轮次仍按请求语言转换。不得默默改为只支持五语。
- [ ] **1.6** 写失败测试：伪ES命中同盘黑白两位姓名时只返回一盘；q不可偷换player_id来证明性能；非空列表缺preview或报告/段位字段时失败。Run: `pytest tests/web_ui/test_kifu_es_contract.py -q`，预期新ES入口未实现导致明确失败。冻结 oracle 后再写实现，不反向修改期望迁就快路径。
- [ ] **1.7** 提交：`test: freeze kifu elasticsearch response contract`。

### Task 2: 最小文档、名称投影与查询定义

**Files:**
- Create: `katrain/web/kifu/search_documents.py`（文档与批量投影）。
- Create: `katrain/web/kifu/search_terms.py`（查询词规范化与显式扩展）。
- Create: `katrain/web/kifu/search_projection.py`（复用资格结果的有限构建上下文与显示拼装，不引用prepared模块）。
- Create: `tests/web_ui/test_kifu_search_documents.py`。
- Modify: `katrain/web/kifu/library_search.py`（仅复用现有历史姓名映射，不复制一套）。

- [ ] **2.1** 每盘`_id="album:"+str(id)`、`doc_kind=album`，包含album_id、身份ID、可搜索词、date_sort、list_visible、原metadata一份和五语姓名/赛事小对象。其余文档仅为`term:<精确词编码>`、`public-player:<id>`和`sync-state`，不含棋谱副本/成员清单/证据链。所有列表、数量和遍历必加`doc_kind=album`，不能把词条文档计入棋谱总数。不放SGF全文、分析moves、审核证据全文。
- [ ] **2.2** 建立`build_projection_context(db, strict_mode)`及`project_album_batch(context, records)`两个明确入口。权威来源与复用边界见下表；首次在同一PG只读快照中按唯一owner/name/batch复用资格结果，每批只取实际slot/selection资料。不联网翻译、不重新跑名称研究；禁止每盘、每语再次调用完整证据链、legacy HTTP/detail reader或旧六表。需要的有限PG SGF可读取校验但不写入ES。记录1000盘样本的投影耗时、唯一owner/资格计算次数、RSS和索引字节，证明资格工作随唯一对象而非盘数×语言重复。

| 输出 | 明确权威来源及复用函数 |
|---|---|
| 原metadata、日期、可见性、身份绑定 | KifuAlbum原字段；duplicate/hidden规则不变 |
| canonical名称和公开身份资格 | 现有name/evidence表；复用`identity._approved_names`与`_qualified_name_rows`，不能只看status=verified |
| raw姓名及scope | `identity._approved_raw_player_names`的实际有限slots；不扩大到同原文所有谱 |
| raw赛事与selection | `_approved_raw_event_names`、`live_event_selections`；保留实际覆盖范围 |
| 五语名称、fallback、sources | `strict_display_maps`、`display_maps`、`resolve_strict_display`的现有规则及KifuAlbumSource→KifuSource；共享本次唯一资格上下文，不重新解释审核事实 |
| 查询分类 | 复用上述资格结果，保留canonical/raw/event/selection类型、授权owner集合和public player_id；不依赖可见棋谱数量 |

- [ ] **2.3** 如需复用endpoint内显示拼装，先把纯拼装/共同响应模型移到`search_projection.py`或既有`library.py`，让endpoint和投影共同调用，禁止catalog→endpoint循环import。未确认/候选值继续按现有规则显示，不能从“成熟库”推导所有verified候选都可公开。若具体资格函数无法批处理，报告其成本，不重建通用依赖图或重跑旧prepare。
- [ ] **2.4** 索引记录实际`KIFU_STRICT_NAMES`模式与schema版本，运行配置不匹配则not-ready。词条分类记录精确比较和原文lower子串所需键；Unicode规范化按原分支分别处理，不把NFKC/casefold扩大成所有SQL exact的等价规则。更名/历史词条只用现有显式映射，并保留旧`本因坊`前缀及仅在允许分支扩展的规则；不对所有exact q无条件套别名。

```python
def expand_legacy_terms(value: str, *, mode: str) -> list[str]:
    # mode comes from the qualified term metadata, not from search hit counts.
    if mode != "generic_with_historical_hints":
        return [value.lower()]
    aliases = HISTORICAL_PLAYER_ALIASES.get(value.removeprefix("本因坊"), ())
    return list(dict.fromkeys([value.lower(), *aliases]))
```

- [ ] **2.5** 请求先把sync-state和q的分类文档用一次`_mget`批读，之后一次album检索；不要每个词分别请求，也不在请求内读取PG名称审核史。`player_id`先查对应public-player资格；不存在或非公开就按原契约返回total=0。分类存在但无可见棋谱时仍返回0，不能改为generic。多身份仅使用已授权集合。例示的普通精确姓名过滤如下；raw/selection场景按下表生成有限bool，不走另一套审核引擎。

```json
{"track_total_hits":true,"from":0,"size":20,
 "query":{"bool":{"filter":[
   {"term":{"doc_kind":"album"}},
   {"term":{"list_visible":true}},
   {"terms":{"player_terms":["王星昊"]}}
 ]}},
 "sort":[{"date_sort":{"order":"desc","missing":"_last"}},
         {"album_id":"desc"}]}
```

- [ ] **2.6** 编写纯函数`compile_query(classification, q, player_id)`，在以下有限路由下对照原分支；不使用命中数推断名称类型，不用无差别全文查询代替原并集。

| 已确认分类 | 一次ES album检索的范围 |
|---|---|
| 空q | 全部list_visible，原日期/id排序 |
| public player_id / 单一exact player | 该身份的黑白任一位置；exact零盘仍是零盘 |
| 已授权同名 / exact player + finite raw | 授权owner IDs并集与明确raw slot键，保留scope |
| exact event / raw event / selected event | 对应event IDs、raw范围与真实selected覆盖，按原条件组合 |
| generic / 混合分支 | 原允许的名称/赛事/日期/原文集合和literal wildcard；只有此类使用对应历史提示 |

子串特殊字符按字面escape；玩家子串优先级用固定constant_score分组，随后原日期/id排序，不用BM25改变列表。term/public-player文档只存分类及owner/scope键，album文档存对应键；不复制逐词的album ID成员表。增量同步同时更新本次改变的这些有限分类文档。
- [ ] **2.7** mapping为`dynamic=strict,date_detection=false`；doc_kind/player_terms/event_terms为keyword、album_id/player_ids为long、list_visible为boolean；date_sort必须keyword，允许`1926-00-00`。显示payload、分类plan和同步诊断对象设`enabled:false`，仅存_source；子串字段单独声明wildcard。具体索引版本在一次请求的元数据和album读取间固定，不跨alias切换混读。
- [ ] **2.8** 测试Unicode、黑白、历史词条、五语、零月日及稳定排序，另加exact零盘不fallback、非公开player_id、授权/未授权同名、raw/selected scope、literal特殊字符和任意非空页preview。Run: `pytest tests/web_ui/test_kifu_search_documents.py tests/web_ui/test_kifu_es_contract.py -q`；先红后绿再提交。

### Task 3: 单实例ES与有界首次建索引

**Files:**
- Create: `deploy/elasticsearch/compose.yml`（仅ES，不能用它重建现有PROD Web/PG）。
- Create: `katrain/web/kifu/search_es.py`（mapping、httpx客户端、search/bulk/health）。
- Create: `scripts/kifu_search_index.py`（plan/build/check/refresh/sync-ids/activate）。
- Create: `tests/web_ui/test_kifu_search_es.py`。
- Modify: `docs/operations/kifu-elasticsearch.md`。

- [ ] **3.1** 以官方当前示例9.5.5作为待核定patch，实施时核官方registry支持/架构、固定实际tag+digest并记录`ES_IMAGE`；不支持则先修文档，禁止latest。复用httpx REST，不先增加SDK、Kibana、Kafka、集群管理平台。
- [ ] **3.2** TEST/PROD各自一个单节点、一个primary、replica=0。它是可从PG重建的搜索副本，单节点不宣称ES高可用。初始ES容器2GiB RAM、1GiB heap、2CPU、禁swap；Docker日志10MiB×3，另显式覆盖JVM默认GC日志为8MiB×4、ES应用日志最多100MiB，禁用自动heap dump。用该固定版本的jvm.options.d/log4j2配置验证轮转，不把Docker日志轮转误当GC日志限制。不提高现有Web4CPU/PG2CPU；共享8CPU不等于预留核。
- [ ] **3.3** 9200仅内部Docker网络或回环地址；关闭不需要的对外端口。使用ES鉴权及CA验证，Web只读凭据、导入/发布使用最小写权限凭据，凭据通过现有私有配置，不写代码、Git、kiosk包、公开日志。CLI建索引权限与在线读权限分离。
- [ ] **3.4** `plan`先输出schema/mapping版本、源count、索引名、预计批次、磁盘余量、原backend与暂停范围，不创建资源。Readiness不足时仍保持当前legacy服务可用。
- [ ] **3.5** 初次只建一个候选物理索引，流式500盘或≤2MiB NDJSON一批，不落全量JSONL/SGF副本。先1000盘及相应词条/公开身份文档样本，分别记录album和分类文档count/bytes、store/translog、RSS、资格计算耗时，再继续同一候选。全部词条文档独立计量，不能将其字节视为0或把它们计进棋谱total。
- [ ] **3.6** 全量导入遵循下文“首次上线顺序”；先准备并审好代码/配置，不先动运行服务，再暂停唯一ingest新一轮、等native自然结束，持原collector/stage及publication写锁后，按六步执行disable/部署bootstrap包/构建。PG同一只读快照覆盖名称、scope/selection及albums，不以MAX(id)充当快照；不暂停对局/报告、不kill发布。剩余窗口必须容纳实际部署和限时构建，构建前锁剩余不足30分钟就不开始，不无限续锁。
- [ ] **3.7** 候选refresh_interval=-1，Bulk逐项确认；期间不使用refresh=wait_for。结束显式refresh并恢复1s，核完整album ID集合/可见count/分类版本/24样本，sync-state置ready后才原子设置alias。全量成功不等于立刻放行collector：必须先确认两端实际写入包、索引目标/凭据及正常增量refresh已生效，按下文顺序恢复。
- [ ] **3.8** 首次全量限30分钟、整个索引（含分类文档）store2GiB观测停止阈值；任一超限停止推广，不自动扩大或无限重试。每台主机分别预留10GiB首次新增峰值和至少15GiB宿主剩余停止线；触线停止，不能提前扣除未回收旧表。镜像、translog、日志/临时merge另外计量。失败先恢复本次临时refresh/锁/原pause状态，保留小型统计，确认候选无alias/引用/活动任务后删该明确候选索引，避免无期限占盘；不删活跃索引/共享镜像。
- [ ] **3.9** 保留随机页码：初始max_result_window=200000覆盖当前约17.7万album（分类文档不计在结果过滤中）；核源count≤窗口。深页另验RSS/耗时，不能截成10000或改成cursor UI。若请求from+size超窗口，先同条件total-only：offset≥精确total时按原API返回空items/preview=null和真实total（page无上限），非空有效页超窗口则是部署容量校验失败，不能交付。每一个非空页都有首条preview。深页与常见姓名页1/2的100QPS单列。
- [ ] **3.10** 聚焦集成测试使用一个真实隔离ES索引：建/导入/重放同ID/失败项/精确total/稳定日期排序/第10001条以后分页/alias一次切换；结束删该测试索引。Run: `KIFU_ES_TEST_URL="$PRIVATE_ES_URL" pytest tests/web_ui/test_kifu_search_es.py -q`。完成提交后删除测试临时文档。

## Chunk 2: API与小时增量闭环

### Task 4: 接入API，保留完整列表与棋盘契约

**Files:**
- Modify: `katrain/web/api/v1/endpoints/kifu.py`。
- Modify: `katrain/web/server.py`（只改search client生命周期）。
- Modify: `katrain/web/core/config.py`。
- Modify: `katrain/web/kifu/library.py`（仅必要的当前页批量读取）。
- Test: `tests/web_ui/test_kifu_es_contract.py`。

- [ ] **4.1** 引入一个明确开关`KIFU_SEARCH_BACKEND=legacy|elasticsearch`，部署默认legacy；ES服务地址、alias与读凭据通过私有env。错误环境值启动时报错，不静默选一种backend。
- [ ] **4.2** ES分支一个共享AsyncClient，启动/关闭由既有Web lifespan管理；检索不占事件循环同步CPU，不增加整个Web多worker。PG当前页批读仍在自己的有限线程/Session内，Session不能跨线程。
- [ ] **4.3** ES取当前页ID、精确total（relation必须eq）和显示payload。PG按本页≤100个ID批取报告/真实段位、source_path及判定所需的本页SGF；canonical报告绑定可按现有函数再批取对应canonical记录。`report_availability`与`_rank_displays`确实要用当前SGF哈希/参数，不能声称只读首盘。只将首条SGF写入preview，ES始终不存SGF。非首条有报告/段位快照必须有case；成本计入完整HTTP。
- [ ] **4.4** `preview`使用第一条ID对应的原始完整SGF，哈希与PG相同。items不是ES原始_source直接透传，仍经原Pydantic契约；详情读取同样不能因删除prepared模块而失效。SQLite/本地模式保留普通PG/SQLite legacy读取，RK3562仍代理云端，不安装ES。
- [ ] **4.5** ES超时、连接失败、timed_out=true、_shards.failed>0或不完整total，一律真实503（search_unavailable），不返回空200、不悄悄回退。_mget也逐项检查error：读取失败不是found=false，不能把失败转成generic；只有成功读取下真实不存在的分类才按约定generic。正常空结果仍返回原空列表/preview=null。
- [ ] **4.6** 请求ES使用`allow_partial_search_results=false`、有限client timeout与连接池；搜索路径不自动重试放大负载。记录term expansion、ES请求、PG enrichment、序列化/完整HTTP分段，日志不包含SGF或秘密。
- [ ] **4.7** `/search-ready`报告backend、具体index/schema/strict模式和sync-state；保留现有ready消费字段。候选未完整构建、模式不符、状态missing/pending/failed或ES不可达均not-ready。API开始时同一次_mget取sync-state和分类，保存该具体索引的单调epoch；ES查询及PG补齐后再读同一具体索引的state，须仍ready且epoch相同才能组装200，否则503。每次writer置pending递增epoch，恢复ready不回退epoch，防止ready→pending→ready的ABA。包括空结果/越末页也走末尾校验；不因Web /health200或只有开头一次检查就报成功。记录两次状态读取成本，属于完整HTTP目标。
- [ ] **4.8** 对冻结24组完整JSON做对照，真实数据库与索引必须来自同一静止数据集。差异按字段定位，不放宽total/排序/预览或用ID搜索替代q。Run: `pytest tests/web_ui/test_kifu_es_contract.py tests/web_ui/test_kifu_search_es.py -q`。
- [ ] **4.9** 前端请求取消、过期响应保护、同词重试、首盘预览缓存和棋盘刷新修复保留，前端API不新增请求。Run: `cd katrain/web/ui && npm test -- src/api/kifuApi.test.ts src/galaxy/pages/KifuLibraryPage.test.tsx`。
- [ ] **4.10** 提交`feat: read kifu search pages from elasticsearch`。

### Task 5: 发布后按本批次同步，不增加全库小时扫描

**Files:**
- Modify: `katrain/kifu_ingest/catalog.py`（`publish_manifest`返回边界）。
- Modify: `katrain/web/kifu/name_batch.py`（原`_locked_write`真实commit及post-commit边界）、`event_selection.py`及实际导入入口。
- Modify narrowly: `katrain/kifu_ingest/{sync,orchestration,verification}.py`（仅接已有同manifest恢复路径及原错误返回，不扩消息协议）。
- Modify: `katrain/cron/jobs/kifu_ingest.py`的verify/resume接线；`scripts/kifu_incremental.py`如实际入口需要。
- Create: `tests/web_ui/test_kifu_search_publication.py`。
- Reuse: `tests/web_ui/test_kifu_incremental_postgres.py`。

- [ ] **5.1** 有限同步集合不是只有receipt.games：复用现有`undo_guard.affected_album_ids`、name/event journal的实际before/after、raw scope，取其与games的并集。若本次为既有owner补上公开名称，用现有黑白/赛事ID索引补齐该owner关联盘；不全库扫描，不建依赖图。分类/public-player文档同步对应的改变键。
- [ ] **5.2** 保持外层catalog的独立Connection及`_PUBLICATION_LOCK_KEY=0x4B49465550554231`原样，不在内层重取它。仅扩展`name_batch._locked_write`原Connection上的720220261002、720220261003两个内层key：同Connection先按原序session级取得，提交空锁事务后写ES pending，再进入原business xact/table锁与业务操作。business commit后原xact锁释放，session级两个key继续保护有限ES同步，finally解锁后才还池。不能另一个Connection持同key再进入旧锁自锁。只解本次实际取得的锁；释放未知则invalidate物理连接，不把可能持锁连接还池。业务/journal/receipt内容和签名不改，业务文档ES写不放进未提交PG事务。
- [ ] **5.3** gate仅一个ES sync-state，含单调epoch、status、类型及operation_ref：catalog为原manifest digest/publication key；新name/event apply为输入bundle digest（此时新batch ID可能尚不存在），undo为原batch ID；已有journal不另存业务副本。在原写锁下、PG变更前确认目标/模式，递增epoch置pending；失败不开始PG变更。business commit后按当前PG重投有限IDs/分类，refresh可见后ready，epoch不回退。pending期间API503；不能覆写未知旧pending，先按原receipt/journal修复或报告阻塞，不宣称分布式事务。
- [ ] **5.4** 将commit与post-commit结果分开捕获：已知PG回滚且ES内容未改变，可恢复原ready；PG commit结果未知则查原receipt/journal，未判明前保留pending。已知PG提交/ES失败则保留pending并报`search_index_pending`和可修复的batch/operation ID，绝不假称PG回滚、不自动undo业务、不把问题归类为来源7004。原幂等return同样经过同步，不能因return位于with内部就认为commit已提前完成。
- [ ] **5.5** Bulk检查每项；进程内只重试暂时失败项（有限次数），重启后从既有journal恢复本次有限affected IDs并重新读取当前PG，允许全批幂等重投。对PG存在但hidden的ID更新list_visible；对既有undo真正删除、PG已不存在的明确ID做幂等ES delete，对已无资格的分类键做相应删除。Web凭据没有delete权限。不是新增删除产品、CDC或outbox表。
- [ ] **5.6** `resume_batch`的names_ready、test_published、prod_published、test_verified均有索引修复点。TEST的publish重放/本地verify可按原PG receipt执行本地sync-batch；PROD verify不能新增任意远程sync命令，必须复用现有`send_verified_manifest`及原验证材料，对同一manifest经过原受限receiver幂等重放，让PROD本地publisher修索引，再核原receipt并推进原prod_verify状态。TEST不访问PROD9200/数据库，也不扩SSH forced command。不能只改publisher而漏掉直接verify重入；原签名receipt不变。
- [ ] **5.7** 接通下表所有实际writer及重入；暂时失败沿已有有限重试/预算隔离，下载/翻译可继续处理其他候选，但在ES pending未解决时不能把后续发布或搜索报为完全同步。操作员可显式切legacy恢复读服务，不悄悄丢掉未同步批次。不要为假设更名设计常驻传播服务。

| 实际入口 | 有限集合来源 | commit后的动作 |
|---|---|---|
| catalog.publish_manifest及幂等重放 | games+已有undo_guard/scope/owner关联盘 | 同步album/分类，refresh，解除本次pending |
| catalog.undo_publication及幂等重放 | 原guard和journal before/after（含被物理删除ID） | 按当前PG upsert/delete，保持原undo receipt |
| name_batch/event_selection apply/undo | 原journal touched owners/selection/album IDs | 同一边界投影相关盘和分类，不重验整库 |
| 现有import_kifu入口 | 本次已提交插入/更新ID | 同步明确IDs；一次性人工工具须输出可重试操作ID |
| resume_batch test/prod verify | 已有receipt batch_id→同一集合 | 先修复索引，再通过既有验证；不重复插谱 |
| 人工sync-ids/sync-batch | 明确ID或原batch journal | 在同一原锁下按当前PG修复，禁止旧快照覆盖新值 |

- [ ] **5.8** 真实隔离PG+ES测试：回滚不写业务搜索文档且gate可恢复；PG成功/ES失败后重放不重复业务；test_published本地恢复及prod_published经真实受限同manifest重放；扩展raw scope影响旧盘；实际undo物理删除；pending已写但journal未创建即退出的恢复；无receipt的import在PG写前已有可定位小记录、崩溃后不丢本批；旧pending不被覆写；请求两次检查间epoch变化（含ABA）不能混合200；部分Bulk及两端目标分离。只测这些真实边界，完成后提交。

pending崩溃恢复先拿原writer锁确认上次写已结束。按manifest/bundle digest查询原receipt/journal；只有确认原操作所有变更在该原子事务内、且按digest确无提交记录或有明确rollback时，才可认未提交并恢复ready（epoch保留）。已提交则用artifact/journal求affected集合重投；结果未知、operation_ref缺失或目标不符保持pending，不定时自动清空。无journal人工导入的小型0600记录必须在置pending之前原子落盘，operation_ref明确定位输入摘要及确定性source_path键，不含SGF/证据；恢复在原锁下按这些键投影当前PG存在的ID，对不存在的明确键处理对应旧ID，不假称原业务命令成功。该记录仅本次CLI使用，成功后留摘要并删除详细临时键，不建常驻队列/新PG表。

### 首次上线的固定顺序（TEST与PROD分别执行）

1. 所有包/配置/脚本先本地准备和审查完再取维护窗口，禁止持锁等待审核。确认本环境唯一writer；停新collector准入并等native自然完成。
2. TEST先用旧CLI disable；在原锁保护下部署已移除prepared依赖的新Web/cron/receiver，读保持legacy；写处于显式bootstrap模式，只有此静止窗口允许不向尚不存在的alias同步。
3. 同一有限静止窗口保持至构建结束；PG快照包括名称、资格、selection和albums。建候选、检查每批、恢复refresh、全量与样本核对；没有snapshot、原锁剩余或磁盘预算就不开始/不放行。
4. 成功时先使该索引sync-state=ready、原子alias指向候选，再启用实际publisher/receiver的正常增量目标/凭据，核验原入口已加载新hook，随后才能精确恢复本次collector控制并释放原锁。不得先恢复旧writer再补hook。
5. 少量真实增量和幂等恢复验证通过后，再切ES读并执行性能/页面验收。已知失败pending时ready=false，不以normal refresh窗口为借口返回已知缺批的结果。
6. 候选失败则保持legacy，显式恢复bootstrap/refresh及本次原控制像、释放自有锁；无active引用候选只保留小型统计后删除。部署新包不能使alias不存在时的正常collector永久进入pending：失败路径明确保持写同步disabled+legacy，报告尚未发布，下一次重建需新的明确执行决定。

## Chunk 3: 生产验收与旧方案完整退役

### Task 6: 聚焦审查与真实性能验收

**Files:**
- Reuse: `scripts/kifu_search_load.py`、`katrain/web/core/kifu_http_timing.py`。
- Modify narrowly: 以上工具若需要标记backend/index，不改计时分母/慢样本/固定到达率。
- Record: `docs/operations/kifu-elasticsearch.md`。

- [ ] **6.1** 独立Astra做实施代码及实际发布边界审查，修复Critical/Important后才部署；本计划的最多两轮评审不等于将来代码已获批准。
- [ ] **6.2** TEST先完成Task3–5：全量、24语义、本批发布与幂等重试、一次Web重启后ready。记录真实索引大小、镜像/RSS、CPU及PG当前页成本。
- [ ] **6.3** 低负载记录至少12位不同棋手首次/重复，含王星昊/吴清源，不预热后冒称冷态；1QPS诊断。性能样本在索引稳定ready、无本次pending写入的可读窗口运行：10/50QPS短ramp再100QPS30秒，3000请求、窗口发出/入口≥2970、最多32inflight、排空≤2秒。不能将这个零错误结果宣称覆盖写入窗口；发布期间的短时503及故障后恢复另做功能验收，不丢弃其失败样本混入性能报告。
- [ ] **6.4** 明确修复现有负载工具的最终verdict，而不只改报告文字：旧脚本overall仍按ASGI p95/低负载20ms，不能复用它宣布达标。新最终gate为3000个不同样本全部完整返回、HTTP max≤200ms、错误/超时/未发出/缺响应/语义差异均0、窗口实际发出和入口≥2970；ASGI p95和low20ms仅诊断。添加“p95<200但一个HTTP>200仍失败”和“low>20不拦截high”的聚焦测试。逐项报告完整HTTP p50/p95/p99/max、>200计数，不拿ES took或handler替代；TEST过后仍须实际8CPU PROD同口径通过，保留所有失败轮。
- [ ] **6.5** PROD实测前先核资源竞争：17个既有服务、Web/PG与新ES共享8CPU；观察100QPS下CPU、RSS、queue与错误，不自动扩大配额或买机器。深页/最大page_size另做低并发正确性及内存检查，单列延迟。
- [ ] **6.6** 从用户实际公网HTTPS入口逐个测试王星昊、吴清源：浏览器提交→完整列表可见→正确棋盘画完，分列API、网络与绘制时间。记录首轮与复查结果、响应体bytes/压缩。现公网5Mbps，若传输成为限制则给实测带宽账，不能把本机100QPS宣称公网100QPS。
- [ ] **6.7** 真实Galaxy及RK3562云端代理页面检查搜索、翻页、切语言、打开正确棋谱；没有合法登录/设备条件就标未验收，不伪造登录。UI无新布局，不额外做全屏视觉重构。

### Task 7: 清理旧预计算代码（是交付要求，不留两套长期运行）

**Files to remove after consumers migrate:**
- `katrain/web/kifu/{prepared_models,prepared_migration,prepared_read,prepare_search}.py`。
- `scripts/kifu_prepare_search.py`。
- `katrain/web/core/kifu_read_executor.py`。
- 对应仅验证旧六表/旧count分支/进程池的测试；保留并迁移可复用的契约、报告/段位及前端回归测试。

**Files to modify:**
- `katrain/web/api/v1/endpoints/kifu.py`：删除prepared import/分支，不动分析接口与业务资格规则。
- `katrain/web/server.py`：删除四进程pool启动/关闭，不动对局/engine/lobby单例；保留轻量通用HTTP计时。
- `katrain/cron/__main__.py`：移除旧policy signature启动import与日志，改为实际ES索引同步版本信息。
- `katrain/web/kifu/{name_batch,event_selection}.py`、`scripts/{import_kifu,kifu_name_batch,kifu_event_selection}.py`：移除纯prepared维护调用，保留原业务事务、审核、undo和锁。
- Create: `scripts/kifu_search_retire_prepared.py`（仅一次性显式plan/apply，不作为常驻任务）。

- [ ] **7.1** 用`rg -n 'prepared_read|prepared_models|prepare_search|kifu_read_executor' katrain scripts tests/web_ui`生成所有实际消费者清单，逐项判断后删除；不能用目录通配批删kifu模块。`prepared`普通变量与其它模块同名不算本方案。
- [ ] **7.2** 清理代码应在实现分支完成并测试，但数据库drop分开发动：先部署不依赖六表的新Web、真实TEST cron及PROD receiver，保证legacy回退也不依赖六表。不要先删表让仍运行的旧writer报错。
- [ ] **7.3** TEST在改动任何`web/kifu`包前先用旧CLI正常disable并确认状态；PROD本来disabled仍需fresh复核。不得因新文件改变旧policy hash而让仍enabled的TEST突然503。
- [ ] **7.4** 对清理后的包跑focused import/lifespan、真实PG发布重放、原报告/段位测试；静态搜索旧import为0。脚本和文档中明确的历史记录不计残留运行代码。
- [ ] **7.5** `git diff --stat`检查旧方案删除量与新代码量；不保留未使用的prepared feature flag、自动重建cron、四worker配置或“备用”后台准备器。移除只为旧四进程尾延迟诊断增加的GC callback和专用pool/policy日志，保留轻量完整HTTP计时及本次有效指标，不删除可复用的负载工具。
- [ ] **7.6** 提交`refactor: retire prepared postgres kifu search`；将清理后的同一包作为最终验收对象，不能只测未删除前版本。

### Task 8: 删除六张派生表、旧guard与无用磁盘产物

- [ ] **8.1** 先执行retire脚本`--plan`：打印明确schema/六表/trigger/function、当前读写包、prepared关闭状态、实际自有prepare进程0及数据库无旧维护事务；锁定单一目标库。需要的只有小型审计记录，不导出1.6GB派生表备份。
- [ ] **8.2** ES真实验收通过且清理后的Web/cron/receiver均已实际加载、legacy回退可用后，取短自然写入静止窗口；按原collector/stage锁保护，不kill在途工作、不重启无关服务。
- [ ] **8.3** 同一个PG事务，`lock_timeout=1s`、`statement_timeout=30s`，先删除属于旧方案的`kifu_prepared_<业务表>_{dml,truncate}`触发器，再删除`kifu_prepared_invalidate()`。目标业务表名单来自旧迁移的明确20表，不删任何其它trigger/function。
- [ ] **8.4** 按下面显式白名单执行schema-qualified DROP TABLE，使用RESTRICT、不用CASCADE：

```text
kifu_search_prepared_members
kifu_search_prepared_dependencies
kifu_search_prepared_displays
kifu_search_prepared_names
kifu_search_prepared_dirty
kifu_search_prepared_state
```

- [ ] **8.5** 检查无未知依赖后才commit，任何新依赖/锁超时均rollback并报告。COMMIT结果未知先查pg_catalog，不盲重发；之后复核六表与旧guard均不存在、一次真实新增及搜索仍成功。
- [ ] **8.6** 保留kifu_albums、玩家/赛事/名称主表、段位历史/快照、来源、分析数据、导入journal和receipt。已有3条搜索辅助索引及普通黑白ID/日期索引可能被admin/legacy使用，不能打包删除；只在确认无消费者后单独处理。
- [ ] **8.7** 两端分别记录清理前后`pg_total_relation_size`、PG volume和宿主`df`、WAL。DROP可释放派生关系文件，但不承诺df立即等额减少；不为追求数字跑全库VACUUM FULL、清PG WAL或删业务备份。
- [ ] **8.8** 远端旧prepare容器、旧临时helper、上传包、build context、无引用候选镜像只按本任务完整ID/路径白名单清理；先核无活动PID/挂载/其它服务引用。保留实际使用的Web/cron镜像和至多一份可用legacy回退镜像，完成清单后删除多余版本；禁止`docker system prune`或清全部tmp/worktree。
- [ ] **8.9** 本机只删除本任务可再生大包/重复build目录，保留小型评审、release证据与必要Git提交。不要将其它agent工作区、用户截图或其它任务产物当作“无用文件”。
- [ ] **8.10** 清理是最终发布的一部分，不能以“以后再清”报完成；若具体对象被实际进程引用，列出对象/大小/唯一阻塞，继续处理引用而不是无期限保留第二套方案。

### Task 9: 按既定四步集成和部署

- [ ] **9.1** 先把最新develop合入feature，解决冲突，focused checks通过，commit/push feature；保留无关改动。
- [ ] **9.2** 合入develop并push，记录实际远端SHA，不以本地merge或feature部署代替。
- [ ] **9.3** `smartbox-software/vendor/katrain`更新到已发布develop，parent main commit/push；只改必要指针/部署配置，不覆盖无关工作区。
- [ ] **9.4** TEST先部署：实际package/服务身份核验、临时关闭旧prepared、安全换唯一cron和Web、ES全量/增量/24语义/压测/页面、六表和磁盘清理后再验代表请求。
- [ ] **9.5** TEST过后PROD新117按相同步骤部署；实际PROD是raw Docker Engine迁移实例，不要拿通用compose重建Web/PG。仅新增ES独立service并显式接入原Docker网络/私有配置。受限receiver保持原root wrapper、数据库目标/用户和SSH host pin，fresh核新入口。
- [ ] **9.6** 任一ES性能/语义未达标停止切换；ES已切换后故障用显式backend=legacy回退，返回真实慢路径状态，不偷偷在单请求里fallback。清表后的回退使用本次已验证、不依赖prepared的legacy代码，而非恢复旧六表。业务PG与receipt从未迁走。
- [ ] **9.7** 最终报告feature/develop/Smartbox main SHA、两端实际Web/cron/receiver/ES版本、HTTP与浏览器结果、磁盘清理实际字节和剩余问题。云端搜索改动不要求安装ES到RK；如需要更新板端proxy包，按Smartbox发布流程另核实际版本与页面。

## 验收清单

- [ ] 完整API字段、所有现有语言、实际可见集合、精确total、稳定排序、首盘SGF和段位/报告契约通过。
- [ ] 两个用户指定姓名从正式网页验证，首次和重复分别报告；100QPS实际PROD完整HTTP每请求≤200ms，0错/0差异，真实到达率合格。
- [ ] 全量只建一次，小时更新只处理有限affected IDs；PG成功/ES失败可幂等恢复。pending期间阻止正式同步成功和ES读200，可继续下载/翻译其他候选；明确报告短时503和恢复，不承诺所有发布故障都不影响新谱可见性。
- [ ] ES无公开9200、凭据不入Git/kiosk；资源和导入峰值有实际测量，未擅自扩大配额。
- [ ] 两端旧prepared reader/writer/import依赖与4进程已移除；六表/旧guard已清理，自有大临时产物有删除清单。
- [ ] 业务表、原棋谱、来源、段位、分析、receipt、共用索引与无关服务保持。
- [ ] 发布提交与实际运行版本一致；清理后代表搜索和新增同步仍通过。

## 额外存储与停止生成旧数据的约束

下表是独立只读评估的工程预算，不是已建ES后的实际占用。每台主机分别计量；首次峰值不能预扣旧表回收。SGF和分析moves从不存入ES，metadata一份、五语只放小显示对象。

| 项目 | 预算或已知实测 |
|---|---|
| album文档primary store | 暂估0.3–1.5GiB；词条/公开身份分类文档另按实测数量和字节计入，不当作0 |
| 整个ES物理索引store | 含分类与状态文档，2GiB观测停止阈值；不是整个服务硬配额 |
| ES常态新增总磁盘 | 约3–7GiB预算，含实际镜像层、store、translog和受控日志；固定版本后复核 |
| 首次部署/导入额外峰值 | 预留8–10GiB，执行按10GiB安排，含解压与merge临时空间；宿主剩余低于15GiB停止 |
| PROD旧六表 | 1,607,311,360B≈1.497GiB，清理实际释放单列 |
| TEST旧六表 | 1,904,648,192B≈1.774GiB，不能抵扣PROD磁盘 |
| 其它明确可清理对象 | PROD本任务build包约126.64MB、Mac本任务build目录约574.71MB；删除前再次核引用 |

PROD现有在用2ded镜像名义3.02GB且共享层，不计成“可回收3GB”。不全量导出JSONL、不创建第二个样本/候选索引，不默认force-merge正在小时写入的索引。失败候选按Task3.8清理，旧方案不再运行prepare/增加派生数据。最终交付给出每端ES实际总量、PG关系文件回收量及宿主df变化，不只给估算。

## 评审记录（最多两轮）

| 轮次 | 独立评审 | 结论与修改 |
|---|---|---|
| 1 | 独立Astra Max，Needs revision，0 Critical/5 Important | 已逐项修订：资格/类型驱动路由和同索引有限分类元数据；具体批量投影权威来源；页内SGF绑定；真实affected IDs及既有undo删除；首次静止构建/真实commit/恢复点/pending边界。另修最终HTTP gate与完整磁盘预算。详见reviews/2026-10-30-kifu-elasticsearch-plan-r1.md |
| 2 | 同一独立Astra Max，Approved（计划层面），0 Critical/0 Important未解决 | 本轮修订并关闭epoch前后校验/ABA、PROD同manifest受限receiver恢复、PG写前可定位operation_ref及崩溃恢复、真实三把锁边界与上线顺序。未开第三轮；性能/容量尚待实测，稳定ready验收与发布短时503明确分列。详见reviews/2026-10-30-kifu-elasticsearch-plan-r2.md |

## 附件与依据

- 存储及建索引独立评估：`docs/superpowers/research/2026-10-30-kifu-elasticsearch-index-storage.md`（另一agent只读评估，已并入预算；未创建ES实例，估计不是实测store）。
- [Elastic 文档建模/避免搜索时join](https://www.elastic.co/docs/deploy-manage/production-guidance/optimize-performance/search-speed)
- [Terms精确词条OR](https://www.elastic.co/docs/reference/query-languages/query-dsl/query-dsl-terms-query)
- [Refresh与近实时可见性](https://www.elastic.co/docs/manage-data/data-store/near-real-time-search)
- [分页、10000默认窗口与深页资源代价](https://www.elastic.co/docs/reference/elasticsearch/rest-apis/paginate-search-results)
- [Search API完整结果/timeout选项](https://www.elastic.co/docs/api/doc/elasticsearch/operation/operation-search)
