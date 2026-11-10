# 星阵 PROD 列表验证慢请求：只读定位

调查：2026-10-23 **21:39 起，北京时间**；原慢请求定位完成于 21:47 前，21:48–21:49 补做有时限的列表与官方前端核实（下文原始时间用 UTC）。仅只读 SSH、公开 GET、运行容器代码读取和独立进程的只读 DB 查询；未改线上文件、配置、数据、cron、服务，未调用模型、导入或发布。唯一本地写入为本报告，未提交。

## 结论与边界

**日期列表本身已有约 10–11 秒应用耗时，主要成本是显示名称的证据核验，其次是无匹配索引的数据库扫描。** 公网不是该样本的主要慢点。15 秒 read timeout 对这种基础耗时余量很小；单进程里同步 DB/JSON 工作占据异步路由执行时间，也提供了排队放大的明确机制。

本轮四个有限样本均成功，**没有重新复现超过 15 秒的请求，也没有当时请求的服务端 trace，故不能断言每次历史超时分别由何种瞬时负载触发**。但已定位可稳定复现的主要慢路径，不能仅靠增大 timeout 声称根因已修复。

## 运行版本与请求路径

- 13:39:48Z，ucloud Web 为 `katrain-lobby:0ac3190d8-backend-overlay`，区别于上一份调查的旧镜像；home cron 仍为 `katrain-cron:kifu-hourly-d6a930739`。
- 本轮相关五个运行文件与主仓库文件 SHA256 全部一致，故以下行号可复核。线上 `api/v1/endpoints/kifu.py` SHA256 为 `e4415009ee320dacd1f80446d24204282644d4dad4e7914e9508dfc9101a92f9`，`kifu/identity.py` 为 `54e4281bb247c102b47bba5068e87ea7ac6cef972856065390c3b22961c74d5e`。
- 调用链：`cron/jobs/kifu_ingest.py:506` → `kifu_ingest/sync.py:162,230`；`verify_album_api(timeout=15)` 完成每谱五语详情后，发 `GET /api/v1/kifu/albums?q=<date>&lang=cn&page=1&page_size=100`，核对公开列表卡片。
- 服务端 `web/api/v1/endpoints/kifu.py:256`：日期同样进入通用模糊搜索，先 `strict_matching_names`，再 count/list，再 `strict_display_maps`、可用性和响应组装；运行 `KIFU_STRICT_NAMES=False` **仍执行 strict 名称核验**。
- DB 为同机 Docker `postgres` / `172.19.0.2`；并非该路由跨 home 查询。`docker top` 仅显示一个 Web Python 进程。

## HTTP 与应用内实测

所有样本均为 `q=2026-01-29, lang=cn, page=1, page_size=100`，返回 total/items 都是 **30**，HTTP 响应 19,308 bytes。未做并发压测或遍历日期。

| UTC 时间 | 有限样本 | 结果 |
| --- | --- | --- |
| 13:41:08–13:41:19 | home **cron 容器网络**访问 `https://modelstella.com` | 200，**11.018s** |
| 13:41:31–13:41:41 | ucloud 新独立进程直接调用运行路由，传入只读 Session | **10.363s** |
| 13:43:15–13:43:26 | 同样直接调用，附 cProfile | **10.632s** |
| 13:43:58–13:44:08 | ucloud `http://127.0.0.1:8001` 同一公开路由 | 200，connect **0.000310s**，TTFB **10.206079s**，total **10.206357s** |

第一份应用内样本阶段计时（包含关系不能相加）：

| 阶段 | 秒 |
| --- | ---: |
| `strict_matching_names` | 0.428 |
| 主棋谱 count SQL / list SQL 的 cursor execute | 0.845 / 1.125 |
| `strict_display_maps` | **7.607** |
| 其中 raw player 审核 | 3.654 |
| 其中 raw event 审核 | 2.499 |
| `report_availability` | 0.018 |

共 56 条 SQL（含事务设置），cursor execute 合计 **4.639s**；该数字不包含结果反序列化和所有 Python 运算。第二份 cProfile 中，`strict_display_maps=7.679s`，9 次 `_qualified_name_rows` 累计 **6.647s**；`json.dumps` **17,408 次、累计 3.415s**。

代码解释了该成本：`identity.py:105` 在页面涉及的多类名称中反复加载创建记录与审核批次；约 `:214–250` 对批次 bundle 求 hash/建绑定，`:275` 附近为 first-pass 构建成员 hash。`_approved_raw_player_names():410` 在逐名称循环中还会重新 hash 所属完整 bundle；`name_transliteration.py:329`、`name_orthographic.py:483` 都先 hash bundle 再判断各自证明类型。现有正字法 request context 未覆盖全部重复工作。**没有绕过或改写任何资格判断来测量。**

## 数据库执行计划证据

对路由实际捕获的 SQL 做 **两个** `EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)`，在同一显式 `SET TRANSACTION READ ONLY` 事务内，预先 `SET LOCAL statement_timeout='18000ms'`，结束 rollback。仅调查这一页的现有查询，未做全库业务遍历、计数审计或重建索引。

1. 日期 count：

   ```sql
   SELECT count(id) FROM kifu_albums
   WHERE duplicate_of_id IS NULL AND list_hidden_reason IS NULL
     AND (search_text LIKE '%2026-01-29%'
       OR lower(player_black) LIKE '%2026-01-29%'
       OR lower(player_white) LIKE '%2026-01-29%');
   ```

   实际 **Seq Scan**，返回 30，过滤 176,802；执行 **885.519ms**；shared hit/read blocks = **1,505 / 123,906**。现有 `date_sort`、`date_sort DESC NULLS LAST,id DESC` 索引不支持这个 contains/OR 谓词。这说明日期仍按全文模糊条件走，不能说已有日期排序索引就足够。

2. 名称证据创建记录：实际 SQL 读取 `kifu_name_changes` 的完整 ORM 行，条件为 `target_table='kifu_name_research_evidence' AND target_row_id IN (<当前页58个证据ID>)`。

   **Gather → Parallel Seq Scan**，实际返回 58，执行 **565.968ms**；3 个 loop 每个平均过滤 207,119 行；shared hit/read blocks = **3,161 / 71,472**。现有该表索引仅 `id` 主键、`(batch_id,target_table,target_row_id)`、`(batch_id,sequence)`，缺少以 `(target_table,target_row_id)` 为前导的索引。第一份路由里该类查询还有 13 条、9 条、2 条结果的重复调用，cursor execute 分别约 0.565、0.521、0.091s。

这里的 read blocks 是 PostgreSQL shared-buffer miss，**不等于物理盘读取时间**。13:44:41Z 检查：`track_io_timing=off`、`log_min_duration_statement=-1`，未安装 `pg_stat_statements`、未配置 preload；无法用现有慢日志还原历史请求。该次 activity 快照没有 lock wait，但不能倒推 13:29/13:39 超时时也没有等待。

## 与失败现场的联系

home cron 13:29:53Z 的 `...31fe3d7bf66a3f1cb6f7c193`、13:39:23Z 的 `...2565d295b7498111a097ea40` 仍有 `prod_published → prod_verify → verify_album_api → httpx.ReadTimeout` 栈。13:33–13:39 连续日志还显示 `2026-01-27/28/29` 相同日期列表被多次重新请求；单次通过并没有免除同包后续棋谱的相同列表工作。

`verify_album_api` 的 `visible` 只记已经核对的 album ID，没有复用同一 query/page 的列表；包整体失败后又从头验。这是放大耗时的机制，不是允许跳过五语、SGF、名称或公开资格核验的理由。异步列表路由中使用同步 SQLAlchemy 和同步证据计算，且单个 Web 进程，使其他请求排队成为合理推断；本轮没有故意制造并发来验证。

## 最小修复建议（本轮均未实施）

1. **先在同一次安全验证内复用 `(query,lang,page,page_size)` 的成功列表响应**，保留每谱 ID、卡片、五语和 SGF 校验；瞬时 timeout 允许有限重试，并记录异常类型。优先恢复已有原生发布回执后的验证，不能因超时重做发布/翻译或直接标成功。不要把跨轮结果永久缓存当成当前公开资格。
2. DB 最小独立改动是给 `kifu_name_changes(target_table,target_row_id)` 配套索引；需另行按生产迁移流程执行，本轮没有建索引或验证实际收益。
3. 在**单个请求**中共享经内容 hash 验证的 batch bundle/绑定/成员集合，按 batch 与当前内容复用，保留 live 名称/证据/作用域校验；避免逐名称重复 hash 整个大 bundle。不能通过关掉严格证据审核提速。
4. 日期精确过滤是后续明确的 API 优化：可另加兼容的日期参数，利用 `date_sort` 并保留公开过滤；不要悄悄把现有任意 `q` 搜索语义改掉。是否需要该项，应在前几项后用同一页复测决定。提高 timeout 只能配合作为有限容错。

## 补充给小时范围设计的只读参数事实

运行 `jobs/kifu_ingest.py:584` 调用只传 `max_downloads=100` 与 deadline，未传分页预算，所以采用 `staging.py:261–262` 默认 **head 20 页、rolling 100 页**；`source_19x19.py:137` 每页 **20**。运行 `KIFU_INGEST_SOURCE_SECONDS=1800`，Source 构造未覆盖默认 **max_requests=500**。`scan_page()` 只按 ID 去重，没有按 `playTime` 限制日期。

13:42:42Z 首页只读两个元信息样本：`91571067` 的 `playTime=2026-10-23 09:34:00`、`createTime=16:09:56`；`91574352` 分别为 `09:01:00`、`17:02:10`。字段结构都是 `{date:{year,month,day},time:{hour,minute,second,nano}}`，没有 offset/zone；两样本 nano=0、playTime 秒=0。另有 `analyzeTime`，没有 `updated_at/updateTime`。**只证明字段形状，不证明源站时区、更新时间语义或可靠精度**；列表这两条也不按 createTime 倒序。以北京时间解释可配置比赛时间窗（最新方案推荐 7 天、硬上限 14 天）必须是明确产品假设，不能冒称源站时区声明。

## 有时限补核：前五页是否覆盖七天

13:48:37–13:49:07Z，对 page 0–4 各读一次（补读首页以取得完整统计）；每页 size=20，保留 Source 的 5–10 秒随机请求开始间隔，无重试、无 SGF 下载。以北京时间解释 `playTime`，七天截止为 `2026-10-16 21:48:37`。

| page（从0起） | 20条的比赛时间范围 | 七天窗内条数 |
| --- | --- | ---: |
| 0 | 10-23 09:34 → 10-20 07:39 | 20 |
| 1 | 10-20 00:00 → 10-19 09:04 | 20 |
| 2 | 10-19 09:03 → 10-18 00:00 | 20 |
| 3 | 10-18 00:00 → 10-16 00:00 | 9 |
| 4 | 10-16 00:00 → 10-15 00:00 | 0 |

总计 **100 条、100 个唯一 ID、69 条近七天**；按日数量 10-23/22/21/20/19/18/17/16/15 分别为 **2/6/5/11/30/10/5/17/14**。100 条相邻 `playTime` 上升对为 0。**当前样本五页已越过七天边界，有31条旧谱余量；不能据此保证高峰时仍够或14天窗口也够。** 达到页上限而末页仍在窗内时应报告截断，不能声称完整。默认排序契约未获确认，也不能据当前排序证明任意未来晚上传记录的位置。

在本次补核的90秒上限内，仅读取官方一个应用 JS：[当前官网](https://www.19x19.com/) 引用的 [app.5daf8ee8.js](https://assets.19x19.com/web-resource/golaxy/20261020_script/js/app.5daf8ee8.js)。其公开 game_type=2 方法实际构造 `GET /games/0086-golaxy_public`，参数仅 `{page:e,size:t,game_type:2,username:'0086-golaxy_public'}`；未传时间过滤或排序参数。同类普通 getSgfList 也是这四项。**未确认服务端支持时间过滤/排序，未以额外参数返回200冒充生效证据。** app 的 `gameInfo` 明确从 `playTime.date` 生成 `dt`，进一步支持它是比赛日期而非更新时间。未扩大到其它 chunk 或探测未知参数。
