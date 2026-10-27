# Galaxy 棋手完整搜索 200ms Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在约定的实际用户网络与合理并发下，棋手姓名/ID搜索提交后约200ms内显示完整、正确的新分页结果和首盘棋盘，同时保持五语、审批撤销、raw scope和排名语义。

**Architecture:** 复用现有PostgreSQL，按小切片先消除物理全表扫描、赛事无关proof和重复计算，再核验预算；同步查询由独立线程拥有Session。只有最小改动仍不能达标时，才在现有数据库增加与发布/撤销同事务维护的紧凑有效展示投影；不把缓存命中、空结果或超时当达标。

**Tech Stack:** PostgreSQL15、SQLAlchemy同步Session/psycopg2、FastAPI、React19、现有pytest/Vitest/Playwright。HBase与Redis保持可选评估，不预装、不迁库。

---

状态：**2026-10-27 已授权实施与标准发布，承接既有调查；Astra Max整体计划审核最多两轮。** 隔离worktree为`kifu-search-200ms-20261027`，分支`perf/kifu-search-200ms-20261027`，最新`origin/develop=e9b4d3ecc`。先完成索引与proof去重最小切片，再依实测落实必要后续工作；不得因扩大审核或样本延误第一刀。

**用户明确的两阶段（2026-10-27）：** 实施阶段按 Writing Plans → Astra Max计划审核修订最多两轮 → SDD安全并行开发 → 独立Astra Max代码审核修到通过；只允许本地/隔离验证和环境只读探针，不提前变更TEST正式运行版本或执行DDL。部署阶段严格按feature同步最新develop/解冲突/验证/commit push → merge push develop → smartbox-software/vendor/katrain更新并commit push父main → 先home-ubuntu TEST部署、受控索引和正确性/性能验收 → 新PROD ucloud-v100=117.50.177.254小样本复验。禁止恢复旧183入口/writer，原17服务配置为权威。

**首轮Astra必要修订：** 唯一棋手候选还需保守探测`KifuAlbumEventSelection.selected_raw.contains(q)`；存在潜在匹配即回原兼容分支，防漏掉有效selected赛事结果。新增player_id在现有repository dispatcher及remote_kifu adapter透传，不能盒端静默丢弃过滤条件。

调查基准：[93f正式性能证据](../reviews/2026-10-26-galaxy-kifu-search-performance-investigation.md)。代码调查基线`e9b4d3ecce03b3269f12922a476fd6d6c6545547`；hourly维护可能继续前进，实施前只需同步最新develop并核对相关文件差异，不能用维护窗口时延替代稳定性能验收。

## Chunk 1：范围、契约与停止条件

### 文件职责与边界

| 文件 | 计划职责 |
|---|---|
| `katrain/web/api/v1/endpoints/kifu.py` | HTTP参数/远端dispatcher、本地worker调度、响应、单路由计时；保留detail/analysis契约 |
| 新建 `katrain/web/kifu/library_search.py` | 小字段精确候选分类、保守fast branch、黑白player_id查询predicate；不是通用搜索框架 |
| `katrain/web/kifu/identity.py` | 按证明族lazy构造、请求内快照复用、当前有效状态检查 |
| 新建 `katrain/web/kifu/library_read.py` | 现有本地list业务块移入同步函数；worker创建/关闭Session；保持20条preview与批量metadata |
| `katrain/web/core/migrations.py`、新建 `scripts/kifu_search_indexes.py` | 可核验的索引规格、只读检查、显式并发建索引；不在Web启动时给大表建索引 |
| `katrain/web/ui/src/api/kifuApi.ts` | AbortSignal传递、preview复用不被过期请求污染 |
| `katrain/web/ui/src/galaxy/pages/KifuLibraryPage.tsx` | 正确新selection、loading/error/retry；不做视觉重构 |
| 现有 `tests/web_ui/test_kifu_list.py` / `test_kifu_name_api.py` / `test_kifu_name_orthographic.py` / `test_migrations.py` | 扩展已有相关行为覆盖 |
| 新建 `tests/web_ui/test_kifu_library_worker.py` | 一条Session线程归属及一条非阻塞路由验证 |
| 新建 `katrain/web/ui/src/galaxy/pages/KifuLibraryPage.test.tsx` | 搜索替换、旧请求、重试；复用当前测试工具 |
| **条件性** `library_projection.py`、`models_db.py`及现有publish/apply/undo入口 | 仅在切片2复测未达标后，落实紧凑展示投影与失效，不提前创建 |

### 验收契约（不能悄悄减功能）

- [ ] 确认现有`q/page/page_size/lang`结果集、精确total、日期/id稳定排序、可见性和preview保持；page_size=20是主要验收尺寸，100另报预算，不以改小page_size达标。
- [ ] 新增可选`player_id: int >=1`表示**明确身份过滤**。`q`与`player_id`互斥，冲突422；未找到公开身份应返回真实0条，不是隐藏超时；错误与取消不能冒充0条成功。
- [ ] `q`默认保留跨语言/别名/同名/raw/赛事兼容语义。只在候选明确为唯一身份且无潜在其它domain/raw scope时fast branch；不猜用户输入就一定是棋手。
- [ ] 完整搜索成功包括新total、新20条列表、首条SGF可解析且正确棋盘真正绘制；列表新了而左棋盘仍旧不算成功。
- [ ] 冻结既有撤销/变更行为：批次status、artifact、evidence/name归属和revision、源依赖、raw/selected scope、SGF/隐藏/去重、rank-only变化不能被缓存漏掉。

### 分层预算（目标，尚无优化后实测）

正常已建立连接、用户到站点RTT≤40ms、无丢包/限速、返回≤32KiB、服务已就绪，TEST以1与4并发客户端分别测试；4客户端每人最高1次搜索/秒，约4QPS是本轮明确验收负载，不能称为系统最大容量。

| 指标 | p50目标 | p95目标 | p99目标 |
|---|---:|---:|---:|
| API server（含worker等待、DB、proof、序列化） | ≤60ms | ≤90ms | ≤110ms |
| 浏览器请求TTFB（含请求传输/网关/server） | ≤95ms | ≤135ms | ≤155ms |
| 提交→正确列表与棋盘绘制 | ≤120ms | ≤180ms | **≤200ms** |

预算提示：server110ms + 传输/网关45ms + 输入调度10ms + DOM/棋盘绘制35ms=200ms。**不能把各段p99相加当作端到端p99证明**；以同一请求真实端到端分布独立验收。worker等待目标≤10ms，超标先查阻塞/容量，不无限开线程或连接。

暖服务第一次查询一个未命中过的棋手也必须纳入，不只反复查询王星昊。新进程在ready前完成必要初始化；冷启动时长单列，不能一边对外healthy一边让首位用户承担全量编译。新网络连接在同一目标网络另测DNS/TCP/TLS和总时长；本轮公网已有建连>1s样本，这种连接无法保证总耗时200ms，不能用“换HBase10ms”抹掉。全球最坏网络不作承诺。

若用户要求赛事/短模糊词也同样200ms，必须作为独立场景报告并通过，不能混入热门棋手平均值藏掉慢请求。本计划首个闭环是用户明确提出的棋手姓名/ID搜索；其它模式的语义全程保持，现有模式不得因优化明显回退。

停止：任何阶段已在上述真实链路达到预算、正确性和相关回归要求，就不继续追加投影、Redis或HBase。未达标就记录剩余段成本并实施下一必要切片；不能提前声称“应该能到200ms”。

## Chunk 2：先消除扫描和不必要证明

### Task 1：索引与精确候选分支（一个可独立验收的后端切片）

**Files:** `migrations.py`、新`kifu_search_indexes.py`、新`library_search.py`、`kifu.py`；测试扩展`test_migrations.py`与`test_kifu_name_api.py`。

- [ ] 增加候选分类小测试：三语言同一player_id仍唯一；同display两个棋手/赛事/raw name时回到兼容分支；不合格审批不能成为已确认身份；旧name别名路径不被“提前return”截断。
- [ ] 用SQL事件捕获验证fast branch**不查询raw_event审核JSON、不调用selected_event search**；验证仍返回相同王星昊ID集合与total。先看到新增测试失败。
- [ ] 在`library_search.py`实现保守分类；仅小字段查询，不实例化完整evidence/batch大JSON。

```python
# 契约草图；各candidate SELECT沿用现有精确比较与必要标量审批条件。
def classify_exact(candidates):
    player_ids = {r.owner_id for r in candidates if r.kind == "player"}
    if len(player_ids) != 1:
        return None
    if any(r.kind != "player" for r in candidates):
        return None  # 潜在碰撞可保守fallback，不能反过来漏结果
    return next(iter(player_ids))

# 只有对actual player candidates完成现有proof校验后才构造：
predicate = or_(KifuAlbum.black_player_id == player_id,
                KifuAlbum.white_player_id == player_id)
```

- [ ] 所有姓名domain候选最好在一个UNION ALL SELECT/同一statement snapshot完成；先取owner/id/evidence_id与必要标量，命中唯一player再完成该player的`_qualified_name_rows`。无输入/ambiguous/selected/raw/composed依旧走原分支；显式player_id不经过名称domain猜测。
- [ ] 先验证production PG索引缺项，再候选建以下索引（本计划不执行）：

```sql
CREATE INDEX CONCURRENTLY ix_kifu_name_changes_target_row
  ON kifu_name_changes (target_table, target_row_id);
CREATE INDEX CONCURRENTLY ix_kifu_raw_event_names_display
  ON kifu_raw_event_names (display_name);
CREATE INDEX CONCURRENTLY ix_kifu_raw_event_names_lower_display
  ON kifu_raw_event_names (lower(display_name));
```

这里选择两个name索引保留当前`display=q OR lower(display)=q.lower()`语义，避免未经证明把Python/PG大小写和排序规则视为完全等价。若Astra确认单一lower谓词可保持五语语义，可收敛为一个表达式索引；不要全部四表先建八个索引。raw_player/player/event其它小表只有实测需要才增索引。

- [ ] 索引脚本`--check`仅检查定义、valid/ready与计划；`--apply`必须显式调用，用autocommit连接一次一个CONCURRENTLY。检查等价定义，不能仅凭同名`IF NOT EXISTS`认为正确；失败遗留invalid索引要报告并按正式变更流程清理。
- [ ] 在TEST允许的维护窗口执行；保留小时单写者，协调自然任务低负载时段，绝不kill旧事务/writer。CONCURRENTLY不能包在事务中，可能等待旧snapshot且增加I/O；设置运维总预算，超预算退出本次操作而不是自动终止他人session。成功后检查`pg_index.indisvalid/indisready`，必要时独立ANALYZE表达式统计。
- [ ] 验证实际EXPLAIN：历史表访问不再全扫，raw_event精确候选走索引/BitmapOr且不搬大JSON；棋谱仍黑白BitmapOr+小排序。验证新旧参数/结果和名单总数等价，再提交本切片。

Focused commands（实现后，按当前仓库环境执行）：

```text
pytest tests/web_ui/test_migrations.py -q
pytest tests/web_ui/test_kifu_name_api.py -k 'search or strict_cross_language' -q
pytest tests/web_ui/test_kifu_list.py -q
```

预计收益证据：消除本次三次历史查找与一项赛事零匹配扫描约1.4s量级；这是可消除的现有成本，**不是优化后的最终时延承诺**。风险主要是索引I/O及分类语义。索引+分类后复测同一API；若完整目标已过，跳过所有条件性新存储。

### Task 2：证明构建按需、请求内复用（保留活动撤销）

**Files:** `identity.py`、必要时`name_first_pass.py` / `name_orthographic.py` / `name_transliteration.py`；测试`test_kifu_name_orthographic.py`、`test_kifu_name_first_pass.py`、`test_kifu_name_api.py`。

- [ ] 先增加一个“first-pass-only批次不调用transliteration/orthographic bindings”的计数测试；一个同内容批次多次使用不重复算bundle/member hash的测试。不要写脆弱的固定总SQL数量镜像测试。
- [ ] 将`contexts={all batches...}`和orthographic全遍历改为实际proof族需要的集合；first-pass自己只构建所需membership。完整JSON只为实际需要的批次读取。
- [ ] 请求context记录`(batch_id, status, bundle_sha256, current_artifact_snapshot)`，只在现有刷新确认内容相同后复用已验证hash/集合；changed状态/内容马上丢弃。保持`populate_existing`语义，不能因ORM持有旧对象而失效。
- [ ] 复用同一请求相同证据creation rows、重复sources结果及bundle内容计算；对后续读取可能变化的mutable依赖先刷新，不把“请求内缓存”误当“请求期间不可能撤销”。禁止跨请求batch_id永久cache。
- [ ] 保留并运行现有`test_list_refreshes_orthographic_batch_within_and_between_requests`及source/artifact/scope变更测试；不为了性能删测试、关闭strict或返回未审核raw。全部通过再提交。

```text
pytest tests/web_ui/test_kifu_name_orthographic.py -k 'refreshes or reader_rejects or request' -q
pytest tests/web_ui/test_kifu_name_first_pass.py -q
pytest tests/web_ui/test_kifu_name_api.py -q
```

收益：profile显示eager两类bindings、重复hash与大JSON确有成本，但冷ORM239ms/hints168ms不能算持续收益。复测分开报告server暖态、未搜过棋手、ready前初始化。若仍>目标，必须进入Task5，不能把“只加索引应该够”作为完成。

## Chunk 3：并发、客户端完整可见与必要观测

### Task 3：同步分支的Session/线程边界与单路由计时

**Files:** 新`library_read.py`、`kifu.py`、`core/db.py`仅必要factory依赖；新`test_kifu_library_worker.py`，更新现有直接调用endpoint的unit helper以调用同步核心，HTTP契约测试仍走ASGI。

- [ ] 把当前local list块原样抽成`read_album_page(db, *, q, player_id, page, page_size, lang)`；保持单页SGF、report聚合和rank批量，没有预览串行新请求。
- [ ] worker创建与关闭Session，路由只await threadpool；异步remote dispatcher不改。worker factory依赖可注入测试engine，禁止导入production engine进行测试。

```python
def read_in_owned_session(session_factory, **params):
    with session_factory() as db:
        return read_album_page(db, **params)

async def list_kifu_albums(..., session_factory=Depends(get_kifu_session_factory)):
    if dispatcher is not None:
        return await existing_remote_branch(...)
    return await run_in_threadpool(read_in_owned_session, session_factory, **params)
```

- [ ] 验证Session构造、查询、close同一线程且每请求不同Session；一个可控阻塞local读时，另一无关轻请求仍能调度。用Event控制测试，不用随机sleep制造时序。
- [ ] 将q参数、worker排队、candidate/count/page/display/rank/report、总时长记录为小的单路由采样/Server-Timing。默认不记录原始q/SQL/身份资料；端点序列化及响应发送另计，不能仅把同步helper时间称为整个HTTP时间。
- [ ] 将worker并发限制与DB100连接、现有应用预算一起核算，先复用现有线程池/合理limit，不引入新的队列平台。结束事务及时close；取消fetch不能假设已停止DB执行。
- [ ] focused tests与TEST真实路由计时通过后提交；排队/事件循环推断由实际并发测量确认。

### Task 4：新列表与新棋盘同步；取消、失败与同词重试

**Files:** `kifuApi.ts`、`KifuLibraryPage.tsx`、新`KifuLibraryPage.test.tsx`。

- [ ] 新增一次代表性测试：无条件页选A，搜王星昊响应B，列表/total/左棋盘均B；无结果清空旧selection；同页仍有效selection可按当前产品约定保留。
- [ ] 为list与detail传`AbortSignal`；旧响应guard继续保留；过期getAlbums不能清空/替换当前preview Map。取消不显示错误，不当作0条成功。
- [ ] fetch成功一次性接受items/total/preview并确定selection。不要等待第二次detail fetch再画首盘；复用当前response.preview。错误显示可操作重试，同词Enter能触发真实retry token；loading不把旧total标成新搜索结果。
- [ ] 验证旧list/detail晚返回、搜索失败→重试、无结果；只做与本变更相关状态，不扩成全页面视觉重构。
- [ ] 按原1280×720正式场景做一次可操作真实预览：搜索前后list/标题/棋盘一致；记录request/response到最终paint。若交互文案或布局需要变更，按用户轻量视觉确认流程执行，不能以此阻塞后端非视觉切片。

```text
cd katrain/web/ui
npm test -- src/galaxy/pages/KifuLibraryPage.test.tsx
npm run build
```

## Chunk 4：条件性紧凑投影与最终验收

### Task 5：仅在Task1–4仍无法达标时，把完整证明移到写时

**前置结论：当前无可直接信任的全库display epoch。** 不接受`max(batch_id)`、最后manifest hash、name.revision、24h本地verification checkpoint作为整页完整新鲜度证明。rank-only不改变这些name信号；proof artifact/source可以改而revision不变。

**Files（只有必要时新建）:** `library_projection.py`、`models_db.py`、`migrations.py`；接入`name_batch.apply_bundle/undo_batch`、`catalog._publish_prepared/undo_publication`和实际去重/SGF/selected event修改入口；测试扩展现有publication/name/selection tests并新`test_kifu_library_projection.py`。

- [ ] Astra计划审核先确认最小投影粒度：优先**按name/证明批次存已编译小结果**；只有仍无法避免逐盘scope判断时才用album/lang卡片投影。不得两种都先实现。rank、report、SGF保持既有独立读，不把整个业务响应永久复制进去。
- [ ] 明确定义每个有效输出的依赖集合，来源沿用现有receipt/batch/evidence/selection和scope成员，不重新发明审批：输出值、policy版本、dependency keys、generation、ready状态。schema必须能回答“谁修改会使哪条失效”，不能只有`verified=true`。
- [ ] 给所有可变依赖建立**数据库维护的紧凑单调版本/失效guard**，至少包括name/evidence审批与内容、batch status/hash/artifact、实际源身份依赖、raw scope成员及selected SGF、album可见性/归属。history不可变日志可复用，不需重hash整表。不能让普通调用者任意更新版本后“自证”。
- [ ] 同事务做：完整现有proof校验 → 写输出与当前依赖版本 → published/ready。apply/undo/compensation/相关维护更改同事务更新或失效，不依赖另一个进程稍后发cache invalidation。
- [ ] DB guard必须覆盖绕过服务的变更；若做不到，不启用跨请求投影命中。读在同一SQL statement snapshot核对依赖版本/审批状态，发生变更不得复用旧证明；保留原“同请求后续读发现撤销”的测试（或用等效真实HTTP并发断言）。
- [ ] 发布前分批为历史数据生成与旧reader等价的投影，预算化处理、同现有writer锁协调；没有覆盖/验证不得切读。不为本轮研究启动全库backfill。
- [ ] 对未ready/失效结果明确策略：有效原reader仍可临时fallback，但该请求若>200ms必须计入未达标；不能fast-empty、漏卡片、旧数据或error算成功。只有覆盖充分且在并发写入/撤销下也通过预算后，才能开启。
- [ ] 验证撤销、artifact和source更改、scope新增/移除、隐藏/去重、SGF变化、rank-only（应独立看到新rank）、同名、多语；核对当前writer所有触点后提交。本切片若所需schema/写入口超过最低范围，回主session调整Astra计划，不能静默扩为新缓存平台。

这是额外写契约变更，风险显著高于索引；需要独立Astra审阅及TEST真实维护回放。没有该必要性证据时Task5整体跳过。

### Task 6：预算验收与发布

- [ ] 在TEST既有同等176k规模数据中，先验证正确性：王星昊504样本的ID/total/顺序、其它已批准棋手首次查询、五语/别名、重名/raw、无结果、翻页；赛事/模糊兼容路径单独报告，不用平均值掩盖。
- [ ] 用现有browser/API工具，正常1客户端与约定4客户端各收集约30–50次代表搜索，含未被缓存的不同棋手；带有限自然导入窗口。输出p50/p95/p99、错误/取消/漏结果、worker等待和分段耗时；小样本尾部分位仅供本次验收，不声称可外推全球SLA。生产只做小批功能/延迟确认，不生产压测。
- [ ] 同一请求测server、TTFB、列表和首盘实际paint；warm/cold连接、暖服务/新服务readiness分别列；完整链路满足Chunk1预算才过门。
- [ ] 运行相关pytest、前端focused tests和build；最终Astra审业务/一致性边界。若Task5未启用则不审其不存在的基础设施；预算已过即停止追加候选。
- [ ] 实施/发布已获授权，按仓库标准：合并最新develop到feature→验证/commit/push feature→merge/push develop→更新并发布smartbox-software submodule→TEST home-ubuntu / PROD ucloud-v100部署→服务健康及实际Galaxy页验证。索引先TEST验证再PROD显式窗口执行，不能把大表DDL暗藏在Web启动中。
- [ ] 与hourly维护agent确认writer/control/lock原状态及source SHA，守住单写者；不取消旧任务、不kill DB session、不重发翻译、不重启RK。回滚仅回代码/开关并保留兼容索引；新投影如已启用须有旧reader退路和写契约兼容。
- [ ] 报告实际发布commit、部署版本、索引valid状态、完整成功结果的延迟分布及任何未达项；未部署前不写“已优化上线”。

### Redis / HBase的决策门

现有PG核心双侧筛选已是几ms；剩余主要是应用读取/证明工作，换存储仍需解决。Redis若用于小热点缓存，只在统计命中率/热集合和多实例需要后采用；同样需要版本失效，miss与冷词必须过完整验收。HBase如需验证，可为`player_id + reverse_date + album_id`建立双侧索引读模型并单独比较，其10ms单次操作经验不能替代带姓名解析/审批/列表/预览/网络的200ms测试。

费用只按实际热数据RAM、持久副本、节点、备份、运维及一致性工作量比较；未知账单不报精确价格。不存在“本任务不许HBase”的用户硬约束；本计划先PG是证据驱动的最小验证顺序，若优化后或未来规模/吞吐要求证明不适合，保留重新评估HBase的选项。

## Chunk 5：TEST未过预算后的最小增量（Astra第2轮计划审核范围）

首轮已按授权顺序发布feature、develop `dc17489e2`、父main `f44676ae`，并仅部署TEST与3条并发索引。16项API检查及11项旧新契约等价通过，27次正确棋盘paint为563–3804ms，未达200ms；已停止扩量和PROD发布。[实际记录](../reviews/evidence/2026-10-27-kifu-search/test-after-summary.md)。

一次暖profile647ms中display586ms：11个first-pass批次snapshot深拷贝341ms，bundle/member编译120ms，SQL总82ms。11批次artifact约5.22MB，紧凑编译结果仅328132B（最大66014B/500候选）。完整artifact SQL SHA一次59.51ms只是定位样本，不证明最小SHA缓存路径不可能达到端到端目标。另两族在该profile几乎无编译成本，因此只优化first-pass，不进入Task5写投影/epoch、Redis或HBase。root已明确撤回复杂MVCC row-version方案：不实现xmin/ctid/filenode/XID64/postmaster协议。

### Task 2b：仅复用内容不变的first-pass纯编译结果

**Files:** 新`katrain/web/kifu/compiled_first_pass.py`、`identity.py`、`name_first_pass.py`；新`tests/web_ui/test_kifu_compiled_first_pass.py`。不提前加server启动预热hook；前端暂不追加优化，响应后paint成本单独保留。

- [ ] 先红测试已运行：两个独立Session/request仍重复bundle编译（1 failed / 3 passed）。保留跨请求artifact整数/浮点数、布尔值/整数、正负零变化拒绝；增加状态/hash/metadata变化、源/ledger/scope变化、dirty Session禁用、缓存可变别名隔离、预算淘汰与并发读取行为。
- [ ] `compile_first_pass(status,bundle_sha,artifact)`只产出已验证candidate/research哈希集合和`shared_displays`；成员canonical SHA和研究/owner/name/evidence/source/creation ledger/raw-scope校验照旧。`persisted_eligible(..., compiled=...)`仅省去已经验证且当前未变的完整bundle搬运及重编译；无compiled仍走原路径。
- [ ] 仅`first_pass_ids - (transliteration | orthographic | positive | legacy)`走该路径；混合批次、其它证明族及dirty Session保留旧reader，不做通用缓存框架。
- [ ] 进程内LRU仅存内部生成的marshal bytes，默认64MiB总payload、1024项、单项1MiB。每次命中私有解码，不共享可变dict/list/ORM；锁只保护namespace/LRU bytes取得和放入，编译与解码在锁外。超限/miss/不支持时原reader，仍计真实耗时，不得fast-empty。

**唯一PG guard：** 每次同一SQL statement snapshot返回fresh batch小字段和完整artifact原文SHA256：`encode(sha256(convert_to(CAST(reviewed_artifact AS text), 'UTF8')), 'hex')`。键含batch id/status/bundle SHA/完整artifact SHA与实际编译所需标量；不能仅用batch_id、stored bundle hash或旧ORM artifact。SQLite取原文并在Python算SHA，只用于可移植行为验证。不得用JSONB数字归一化或Python宽松相等代替完整内容绑定。

- [ ] 命中时query使用`populate_existing`并defer大artifact；proof使用同语句得到的fresh scalars和私有compiled。miss必须在**一个statement**同时读artifact、新SHA和scalars，用该statement的新key编译/入缓存；不得把旧header SHA配新artifact。guard不可用则原reader，不允许无guard缓存命中。
- [ ] 聚焦验证artifact只改内容/JSON类型、status/hash/metadata变化、旧ORM对象、同一请求后续撤销和dirty Session；PG实际查询与完整返回在TEST部署验收，禁止改正式业务行来造测试。

**首次查询/停止条件：** 本轮先不做预热，不再扫全artifact或重复引用集合发现，不按硬编码热门姓名伪造首次查询。最小SHA缓存实现审过后，以少量真实hit、miss、首次不同姓名及同一公开结果等价复测；各类实际耗时照实纳入。只有新的分层实测证明仍需下一刀时才提出必要增量，不能把缓存命中200ms暗示所有首次/miss均达标。

- [ ] 独立spec检查后Astra只审本次delta及必要operator适配；不重审已通过的前端/原索引范围。TEST现已12层Compose，第二次web发布仅允许同链增加下一层image/buildSHA override，保留collector与全部非web身份。
- [ ] 审核通过后再重复授权发布顺序；TEST先以少量首次不同姓名和公开结果等价复测，若仍明显未过200立即停止扩量并定位，达到后再做1/4客户端及明确网络条件。PROD仍待TEST门禁通过才发布；任何未达项如实报告。
