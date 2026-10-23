# 星阵棋谱小时同步未更新：只读调查

调查时间：2026-10-23 19:34–19:43 北京时间（UTC+8）。下列服务器日志与数据库原始时间为 UTC；正文另有注明。仅调查，未修复、部署、重跑写入任务、调用模型或修改业务数据；本报告是唯一新增本地文件，未提交或推送。

## 结论

**已确认直接根因：历史失败下载队列阻断了最新列表扫描。** 小时调度正常运行，但每轮先下载历史待办；固定前五个 2021 年旧谱返回星阵业务错误 `7004 / can not find this game`，触发“连续五次失败立即返回”。代码尚未执行最新列表第 0 页就结束发现阶段。旧错误默认可重试且没有退避，故每小时重演，10 月 21–23 日新谱根本没有被发现，也没有进入翻译或入库阶段。

**另有独立故障：78 盘旧谱已在两库实际发布，但生产公开列表验证反复超时。** 三个包均有 TEST 完整验证和 PROD 原生发布回执，生产 78 行全部存在且公开；`prod_verify` 的列表请求抛 `httpx.ReadTimeout`，因此没有推进为 `prod_synced`。这加重每轮处理负担，但不是“新谱不存在”的原因。

两库与公开 API 均止于比赛日期 10 月 20 日，**不是前端缓存或界面筛选导致**。10 月 22 日确有旧谱补录，不能把最后插入时间等同最新比赛日期。

## 运行位置与现场状态

| 项目 | 只读证据 |
| --- | --- |
| 抓取、处理、双库发布的运行位置 | `home-ubuntu` 的 `katrain-cron`，APScheduler 进程内 interval job `kifu_ingest`；不是系统 crontab，fan 用户无 crontab |
| 调度配置 | `CRON_KIFU_INGEST_ENABLED=true`，间隔 3,600 秒，无 `cron_job_controls` 暂停记录 |
| 实际版本 | TEST cron、TEST/PROD Web 镜像均为 `d6a930739` 系列；环境 build SHA 为 `d6a93073930b24117c66e9b693617c2f9c84115d` |
| cron 持久挂载 | 主机 `/mnt/disk1/fan/kifu-hourly-incremental-20261019/ingest-stage` → 容器 `/app/data/kifu_ingest` |
| Compose 文件 | `/home/fan/Repositories/katrain/docker-compose.yml` + `/mnt/disk1/fan/kifu-hourly-incremental-20261019/cron-kifu.override.yml` |
| 发布目标 | TEST `http://host.docker.internal:8001`；PROD `https://modelstella.com`，受限 SSH receiver 发布 |
| 模型配置 | LLM 已启用，仅核对凭据存在、未输出值；100 盘/轮、20 新名称/轮、100,000 token/UTC 日 |
| 调度存活证据 | 19:35 北京时间心跳正常；run **70314** 于 **10-23 19:26:29** 启动，实际继续验证旧包 |
| 最新结束轮次（收尾复查） | run **70314**：10-23 **19:26:29–19:42:02**，`failed`；仍为 `5 source request(s), 3 package(s)`。前一 run70207 同样失败，耗时 911,099 ms |
| 历史统计 | 初次快照 `failed=78`、`errors=3`、`paused=5`、`running=1`；收尾时70314也失败，连续失败计数已 **82**，没有记录为 success 的轮次。失败轮次仍可能完成部分发布，不等于全部无进展 |

`ucloud-v100` 不重复抓取，符合既有设计；其老版本 cron 不是本功能调度器。其 Web 与 PostgreSQL 正常可访问。上述四个关键业务文件的本地 SHA256 与运行 TEST 容器逐一一致，以下代码行号可用于现场定位。

## 源站与两库核对

现场从 Mac 和 **TEST cron 容器网络** 请求同一星阵公开接口成功：

- [星阵公开列表第 0 页](https://api.19x19.com/api/engine/games/0086-golaxy_public?page=0&size=20&game_type=2&username=0086-golaxy_public)：HTTP 200，业务码 `0`。首页 20 条中有 **10-23 两条、10-22 六条、10-21 五条**；依据 `playTime`，不是猜测上传日期。这里只统计该页，未声称全站完整数量。
- 10-23 的 `91571067`（倡棋杯决赛）、`91574352`（王座战挑战赛）及 10-22/21 样本的只读 SGF 获取均成功。
- 13 个新 ID 均未进 staging；用实际 `known_source_ids()` 核对，既有主来源/来源关联与 1,752 条历史排除集合对这 13 个 ID 的交集均为空，排除错误去重/历史排除。两库按相应 `source_path` 查得 0 条。
- 运行容器用现有解析函数验证：`91574352` 正常派生 `date_played=2026-10-23`，可进入后续处理；`91571067` 的列表黑白姓名与下载 SGF 反向，触发 `source metadata conflicts with SGF player_black`。这是恢复抓取后需独立隔离核实的源数据问题，不能为追新放松身份校验，也不是当前未扫描的根因。

| 环境（10-23 19:35–19:40 只读快照） | 全部棋谱 | 公开棋谱 | 最新比赛日期 | 最近实际插入时间（北京时间） |
| --- | ---: | ---: | --- | --- |
| TEST / home-ubuntu PostgreSQL | 176,832 | 176,573 | 2026-10-20 | 2026-10-22 10:05:39 |
| PROD / ucloud-v100 PostgreSQL | 176,832 | 176,573 | 2026-10-20 | 2026-10-22 10:28:28 |

两库 10-20 均 5 盘，10-19 均 22 盘，没有 10-21 之后比赛日期。公开资格按 `duplicate_of_id IS NULL AND list_hidden_reason IS NULL` 计数。

实际请求 [TEST 公开列表](https://go.sailorvoyage.top/api/v1/kifu/albums?lang=cn&page=1&page_size=5) 和 [PROD 公开列表](https://modelstella.com/api/v1/kifu/albums?lang=cn&page=1&page_size=5) 均 HTTP 200，`total=176573`，首屏五盘均日期 10-20，与数据库一致。两库主键不同属正常，不能直接按 album ID 比较。

## 已确认根因的证据链

1. **10-21 08:51 北京时间**，滚动扫描在 page 1785 发现 2021-12-16 的七条老谱，任务表 `created_at=2026-10-21 00:51:10Z`。持久游标此后停在 `rolling_cursor=1786`；head 保留 `last_page=19`，不能把该字段当作近期成功扫描时间。
2. 七个 ID 为 `7923089, 7926016, 7928067, 7928304, 7929649, 7929673, 7929683`。前五个至调查时各 **59 次**尝试，后两个各 1 次；均 `source business error: 7004`。
3. 同一 TEST 容器直接请求 `games/shared/7923089`，HTTP 200、业务码 **7004**、消息 **can not find this game**；同容器请求最新列表和最新 SGF 业务码均 0，排除整个源站不可达、凭据过期或网络全面中断。
4. `source_19x19.py:123–126` 把所有非零业务码抛为默认 `retryable=True` 的 `SourceError`。`staging.py:245–252` 的 `fail()` 对这类错误将 `next_retry_at` 设为当时 wall clock，下一轮立即可重试。
5. `staging.py:313–352` 在扫描列表**之前**遍历历史待办；五次连续失败设置 partial 并返回整个 discovery。最新页扫描在 `:381` 之后，永远到不了。
6. 运行日志从 **10-21 09:00 北京时间至调查时**，最新列表 `GET .../games/0086-golaxy_public` 请求计数 **0**。近期每轮只见同五个旧谱 POST，然后 `downloaded=0`。
7. 用运行容器的原 `discover_and_download()` 和纯内存假 source/stage 做最小复现，不触网、不写文件：七个历史失败项，只请求 SGF `1..5`，`source_list_requests=[]`，结果 partial、errors=5。证明该控制流足以独立造成新谱长期不被发现。

脱敏实际日志（UTC）：

```text
2026-10-23 10:41:23 POST .../games/shared/7923089  HTTP/1.1 200
2026-10-23 10:41:27 POST .../games/shared/7926016  HTTP/1.1 200
2026-10-23 10:41:31 POST .../games/shared/7928067  HTTP/1.1 200
2026-10-23 10:41:34 POST .../games/shared/7928304  HTTP/1.1 200
2026-10-23 10:41:39 POST .../games/shared/7929649  HTTP/1.1 200
2026-10-23 10:41:40 kifu discovery partial: downloaded=0, pending=67, deferred_until=None
RuntimeError: kifu round failed: 5 source request(s), 3 package(s);
downloaded items were retained and processed
```

数据库中七个失败下载项仍为 `discovered`、无 error/attempts：`jobs/kifu_ingest.py:385–403` 只把成功下载推进状态，源下载失败细节保存在 staging。单查任务条目表会漏掉本次关键错误。

## 处理、翻译与 TEST → PROD 边界

TEST `kifu_ingest_items`：`prod_synced=206`、`prod_published=78`、`quarantined=317`、`discovered=7`。317 包含既有隔离，不是本次新谱失败数；PROD 不镜像 TEST 编排状态，不能将其空 `kifu_ingest_batches` 误判为没收到棋谱。

翻译并未因缺凭据阻断：最近有模型用量账本 10-20 **94,513**、10-21 **94,238**、10-22 **59,616 token**；没有 10-23 账本，符合当日未发现新谱、未触发新付费名称工作的现状。预算曾造成旧待办延期，但不能解释当前对最新列表的零请求。

三个未最终验证包：

| publication_key 后缀 | 盘数 | 两库实际状态 | 当前卡点 |
| --- | ---: | --- | --- |
| `bd5fdf7640ad9a37de370794` | 2 | TEST verified；PROD 发布回执及行存在 | PROD 列表验证 |
| `31fe3d7bf66a3f1cb6f7c193` | 32 | 同上 | 同上 |
| `2565d295b7498111a097ea40` | 44 | 同上 | 同上 |

在 PROD 按实际回执对应 ID 查询，**78 行均存在且公开**，比赛日期范围 2025-02-24～2026-10-09。TEST 同样查得全部 78 行。它们不是 10-21～23 的新谱；本次未对 78 盘重新进行全量五语/SGF 审计。

近期三个包的完整异常栈均指向：`jobs/kifu_ingest.py:464 → prod_verify(:506) → sync.py:230`，即 `GET /api/v1/kifu/albums?q=<date>&...` 的 **httpx.ReadTimeout**，默认单请求 read timeout 15 秒。运行容器抽样读取 PROD 一条详情耗时 8.398 秒，日期列表耗时 11.250 秒，均成功；这是单次样本，不能据此声称稳定性能或已定位下层慢因。

`verify_album_api()` 每次从包头顺序检查五语详情及列表，完成前不落部分验证进度，频繁超时会使同一批已过项反复重验。主任务 `jobs/kifu_ingest.py:558–589` 又优先恢复包，再进入发现，因此也可能挤占新谱时间。

另一个可见性问题：`process_package_queue():253` 对字符串为空的异常都写成 `package phase exceeded <remaining seconds>s`。本次 ReadTimeout 的字符串为空，数据库持久错误看似“整包 3299 秒超时”，实际日志是列表请求的 15 秒 ReadTimeout；不能只据数据库该文案判断整轮耗尽。

## 建议的最小修复与验证（均未执行）

1. **先解除发现阶段的队列阻塞。** 为明确的“找不到棋谱”业务码 7004 采用可审计的条目级终止/隔离处理，保留原元信息及错误，不无限重试；并保证历史坏项或历史下载预算不会跳过本轮最新页扫描。保留 429 的整源退避及现有速率/总预算，不能用绕过限流解决此问题。单纯删除游标或反复重启无效。
2. 对现有七条坏下载记录做显式、有限、可回滚的状态迁移；不要清空 stage、删除失败证据，或把未验证包手动标成成功。只在代码修复获准并部署后处理这些状态。
3. **分别处理 PROD 验证超时。** 先确认日期查询在应用/数据库层还是公网链路耗时，再调整到合理有限超时/重试，复用同轮相同列表查询或保留安全验证进度，减少全包从头重复。保持五语、SGF、名称、公开卡片验证；已有 PROD 原生回执应直接恢复验证，不重复入库或重做翻译。
4. 最低回归覆盖：七个 7004 历史待办存在时仍发现/下载一个新谱；7004 不每轮重试；429 仍遵循 Retry-After。另验证一次列表瞬时超时后能续验，且未通过仍不能标为 prod_synced。聚焦现有 source/staging/sync 测试，不需要全库重扫。
5. 恢复后观察一轮真实调度：日志确有 page 0 请求，`91574352` 或另一条无冲突最新谱进入暂存、必要翻译、TEST 发布与五语验证，再同包 PROD 发布/验证；两库及公开列表出现对应 10-23 日期，重放无新增。`91571067` 若仍冲突应诚实隔离，不能算成功。
6. 补足原监控中的“最近成功 head 扫描时间/最新源日期/最新入库比赛日期”及下载失败原因，让调度存活但无新谱的状态可见；先复用 cron 状态/日志，不另建监控系统。

尚未确认：PROD 列表偶发超过 15 秒的具体下层慢因；13 条最新谱除上述样本外的全部名称资格及源字段一致性。本调查没有调用付费翻译或进入有写入的真实准备/发布流程，不能保证全部 13 条修复后都可直接公开。

## 调查后用户补充的范围

用户明确要求：小时更新只覆盖当天新增附近的小范围，不应承担十几万盘棋的历史回扫。后续方案应采用有明确分页和处理数量上限的最新列表增量、棋谱 ID 去重及有限重叠回看；避免仅凭比赛日期过滤而漏掉跨天或延迟上传的棋谱。历史补录须独立调度，旧下载失败或旧包验证不得阻断小时新谱发现。

以上为待实施的方向记录，未改抓取逻辑、调度配置或数据库。本地对局与大厅功能的集成发布不包含棋谱同步修复。
