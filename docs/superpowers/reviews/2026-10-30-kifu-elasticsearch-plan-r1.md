# Kifu Elasticsearch 计划独立评审，第 1 轮

日期：2026-10-30。评审者：独立 Astra Max。结论：**Needs revision**。Critical：0；Important：5。下面五项需要在第二轮前写清，另有两处确定的小修正。没有要求第三轮或额外平台。

评审对象是 `docs/superpowers/plans/2026-10-30-kifu-elasticsearch-search.md` 的首稿，不是已完成的实现。只读核对了 `kifu-search-prepared-20261028` 中的真实业务、查询、发布和退役代码；所引用文件相对 `origin/develop=07d1ddce9e8808fa6c7b840e1a0cd928048ac4bd` 无差异。也读了独立存储报告。本轮未启动服务、建立 ES 索引、运行旧 prepared 或操作业务数据库；唯一写入是本评审文件。

总体方向可行：PG 主库、每盘一个 ES 文档、无 SGF/analysis moves 副本、既有发布批次增量、显式 legacy 回退、清掉六表和四读进程，均比继续修旧方案合适。问题主要是计划若按当前文字直接实现，会在查询分类、权威显示、页内补齐和真实写入边界上改变行为。

## I1 — 查询路由必须由名称资格和类型决定，不能由可见命中数决定

位置：Task 1.2–1.6、2.4–2.6、3.9。

基线 `katrain/web/api/v1/endpoints/kifu.py:559–688` 先判断合格名称的身份、原始名称范围、赛事选择和冲突类型，之后才查询棋谱。Task 2.6 的“精确集合 total 为 0 才进入兼容查询”不等价：一个已确认身份若暂无可见棋谱，应返回 0，不能因此改成赛事/原文子串搜索；反过来，有棋手命中也不能自动省略当前规则允许的 selected-event/raw 范围。Task 2.5 的“同词多身份取并集”也必须是现有授权并集，`identity.strict_matching_names():987–1073` 对未获授权的同名碰撞不会无条件扩张。

`player_id` 还有独立公开资格边界：`library_search.public_player_id():92` 检查存在的身份及合格的主要语言名称。不能将所有 album 的 black/white IDs 原样放进 `player_ids` 后直接匹配，否则当前返回 0 的非公开身份会被搜出来。规范化也应区分原先的 exact 名称比较、normalized alias 和原文 lower 子串；不能把所有 NFKC/casefold 处理都视为与原 SQL 自动等价。

**最小改法：**投影时批量完成既有名称资格判断，产生一个紧凑、有限的 query 分类结果：精确身份、授权同名/原文范围、精确赛事、generic，以及可公开的 player IDs。可以放在当前索引版本的小型词典/词条分类元数据中；不需要逐谱 members 表、依赖表或运行时证据核验。常见 exact q 直接走一次 ES 精确查询；只有分类确为 generic 才走 literal wildcard。原有混合分支按其确定条件组合，不按结果页或 total 猜测。固定实际 `KIFU_STRICT_NAMES` 模式；索引与模式不匹配时不能静默继续。历史词条展开须保留原来适用的分支和 `本因坊` 前缀行为，而不是对所有 exact q 无条件扩张。

先在计划里写一张小路由表，再让现有测试/24 个真实 case 覆盖这些类别；不用扩大成全历史名称治理测试。至少保留“合格 exact 但可见盘数 0”“不公开 player_id”“允许与不允许的同名集合”“原文/selected event”“literal 特殊字符”几个反例。

同一契约中还需补一个小边界：API 没有 page 上限，原先越过末页返回空 items 和精确 total。`max_result_window=200000` 只能覆盖当前有效页，不能使 `page=100000` 自动合法。超过窗口时可走一次同过滤条件的 total-only 查询；确实越过 total 则按原契约返回空页，不把 ES 窗口错误变成 503 或新增 422。每个非空页都应有对应首条 preview，不只第 1 页。ES 的窗口限制及深页成本见[官方分页文档](https://www.elastic.co/docs/reference/elasticsearch/rest-apis/paginate-search-results)。

## I2 — “已发布/确认值”尚不是可实施的投影来源契约

位置：Task 2.1–2.3、3.5。

删除六表后，业务库没有一列可直接替代全部已确认显示。`identity._approved_names():71` 的 verified/approved SQL 条件只是第一层；`_qualified_name_rows():156` 还处理现有持久化资格。原始姓名有 finite slot scope，赛事有实际 selection、原始赛事范围及 fallback。只取 status=verified 会改变公开输出；简单把现有 `strict_display_maps` 对每批五语重跑，也可能把旧逐谱核验成本搬到一次性脚本中。

**最小改法：**在 Task 2 增加如下来源约定，并指定一个批量投影入口，不再只写“读取确认值”：

| 输出 | 权威来源及处理 |
|---|---|
| 原 metadata、日期、可见性、身份绑定 | `KifuAlbum` 原字段，保留 duplicate/hidden 条件 |
| canonical 姓名/赛事显示与 exact 分类 | 现有 name/evidence 表，复用 `_approved_names` 和 `_qualified_name_rows` 的资格结果；不是只看 status |
| raw 姓名/赛事、选择覆盖 | `_approved_raw_player_names` 的有限 slots、`_approved_raw_event_names`、`live_event_selections` 的真实资格及作用范围 |
| 非 strict fallback、五语显示及 sources | 原 `resolve_strict_display` / legacy fallback 规则与 `KifuAlbumSource → KifuSource`；其余 UI 语言仍按现有规则映射 |

在一次静止构建中按唯一 owner/name/batch 复用资格结果，再把结果套到分批 album 上；有限 scope/selection 只读取其实际相关资料。明确禁止每盘、每语重新跑完整证据链和 legacy reader，禁止依赖待删六表。确有必要的有限 SGF 验证可以读取 PG，但不能复制进 ES。增量使用同一投影入口，仅处理本次有限受影响集合。

这不要求重写名称治理，也不要求新“已确认名称”数据库。需要的是一个可直接实现的复用边界，以及在同一候选索引样本阶段记录一次投影耗时/输入规模。30 分钟是否足够是后续实测条件，不应先承诺成功；若现有资格函数不能满足批处理边界，应明确报告具体函数和成本，而非重新运行旧 prepare。

## I3 — 只读首盘 SGF 与保留当前报告/段位判定互相矛盾

位置：步骤替换表、Task 4.3–4.4。

`katrain/web/kifu/library.py:11–88` 的 `report_availability` 对当前页记录计算 SGF 哈希，并在有报告时用 SGF 验证参数。`endpoints/kifu.py:958–981` 的 `_rank_displays` 也以当前 SGF 哈希、source_path、slot 和 raw rank 绑定快照。现有 prepared reader 在 `kifu.py:505` 已明确说明为什么整页需要 SGF。

**最小改法：**允许 PG 对当前页最多 100 条批读上述判定所需的 SGF/来源信息；响应仍只把首条 SGF 放入 preview，ES 始终不存 SGF。沿用当前判定，不为此次迁移另造一套报告摘要/哈希权威表。实际页内补齐成本纳入完整 HTTP 验收即可。这样是有限读取，也避免误把未核验的报告或 rank 标为有效。

只需复用已有报告/段位测试并加一个非首条有报告/快照的页面 case；无需全站回归。

## I4 — 真实受影响集合不止 receipt.games，既有 undo 还会物理删谱

位置：Task 5.1、5.6–5.7，Task 7 的 writer 清单。

这是基线已存在的行为，不是提出未来改名/删除需求：

- `catalog.py:1899–1908` 已计算本批 games 之外的 event/raw scope 受影响盘，`_publication_undo_guard` 保存 `affected_album_ids`。`_apply_decisions():829` 也允许为既有 owner 补上尚未确认的名称；只重投 receipt.games 无法保证该 owner 既有文档和分类结果更新。
- `catalog.undo_publication():1240–1352` 会在 journal 的 before_image 为 None 时真正删除新建 album；不是只设置 list_visible。Task 5.6 所述“undo/隐藏同步 list_visible”无法覆盖 PG 中已不存在的 ID，会留下 ES 幽灵条目和不存在的 preview。
- 已有 name_batch/event_selection 的 apply/undo 是实际 writer；清掉 prepared 的调用后，不能默认为它们对 ES 没有影响。

**最小改法：**把“批次 IDs”写成明确的有限 affected IDs：receipt.games 加已有 guard/journal 给出的相关 IDs；若本次确实新增了既有 owner 的公开名称，仅通过已有黑白/赛事 ID 索引取该 owner 的关联盘，不建全局依赖图，也不每小时扫库。所有重试均从当前 PG 状态重新投影。`sync-ids` 对存在但 hidden 的盘更新可见性，对 PG 已不存在的明确 ID 做幂等 ES delete。删除权限只给同步 writer，不给 Web。

为现有真实入口列出 apply/undo → affected IDs → post-commit 同步的短表即可。未实际使用的管理工具可以列为需人工 `sync-ids` 的维护入口，但不能保留一个会改当前搜索输出、又没有同步约定的已部署 writer。签名 receipt 保持原样，有限诊断/同步集合可以复用已有 journal 或独立的小型诊断，不新增 outbox/CDC。

验证只需覆盖一批扩展既有 raw scope/名称的旧盘和一次实际 undo 删除；不新增删除产品或通用更名传播系统。

## I5 — 将初次构建、发布提交和失败恢复接成一个明确顺序

位置：Task 3.6–3.8、4.7、5.1–5.5、9.4–9.6。

当前文字分别描述了静止快照、alias 和 post-commit upsert，但没有明确静止窗口何时结束，以及新 hook/目标 alias 在恢复 collector 前是否已经可用。若全量成功后恢复旧发布路径，再晚些部署同步代码，中间新增会漏掉。反过来，先启用必需同步的 publisher 而 alias 尚不存在，会把正常发布留在待同步状态。失败候选还需明确恢复 refresh/锁/collector，不能无限保留暂停状态。

另外，真实提交在 `name_batch._locked_write():220–227` 的退出阶段；`catalog.py:1884/2089` 的 return 仍位于该上下文内。同步必须在调用者取得已提交结果后执行，并覆盖幂等返回。现有 `resume_batch():457–491` 在 test_published/prod_published 阶段直接做验证，未必再次调用 publisher；必须说明 pending 的 ES 修复在哪一层执行，而不是只保证最早返回分支有 hook。

**最小改法：**给两端各一份相同的短顺序：

1. 先停新一轮 collector 准入并等待已有 receiver 自然完成；TEST 用旧包 disable prepared，再部署已删除旧依赖的新包，保持 legacy 服务。
2. 在同一个有限静止窗口内构建/核对候选；明确 PG 快照覆盖名称和 album，不只记录一个最大 ID。
3. 成功后恢复 refresh、设置 alias、确认本机 publisher/receiver 的增量目标和配置已经生效，再恢复 collector；后续切 ES 读路径。失败保持 legacy，退出自己持有的锁/暂停状态，保留小型结果记录并明确处置未启用候选。
4. PG commit 后，利用现有 publication 串行锁完成有限 ES 尝试；人工 repair 同样不得与旧投影乱序覆盖。进程中仅重试失败项，重启后可对有限 affected IDs 全部幂等重放，不需要持久化每个 Bulk item 状态。
5. 用现有批次恢复点/receipt 明确 PG 已提交但 ES 未完成的状态及重试入口，包含 test_published/prod_published 的恢复；仅 refresh 可见后才推进验证成功。写清 pending 时搜索 readiness 和 API 允许的可见窗口，不能一面报完全同步、一面正常返回一个已知漏批次的成功结果。也不能因 ES 失败自动撤销已提交 PG 或解除原 TEST→PROD receiver 边界。

无需实现跨 PG/ES 分布式事务。这里需要把已有锁、receipt 和恢复阶段接对，而不是增加平台。关闭 refresh 的候选构建期间不能使用 `refresh=wait_for` 等待自动刷新；该等待会一直持续到显式 refresh，见[Elastic refresh 文档](https://www.elastic.co/docs/reference/elasticsearch/rest-apis/refresh-parameter)。

## 两处确定的小修正

1. **性能工具的最终 verdict。** Task 6 已正确要求每个完整 HTTP ≤200ms，但复用脚本 `scripts/kifu_search_load.py:299–319` 的 `overall` 当前由 `asgi_p95` 判定，low profile 也仍把 20ms 当门槛。计划应明确修改/另行定义本次最终 gate 为完整 HTTP max≤200ms、超时/错误/语义差异 0、全部 3000 样本及真实到达率合格；现有 ASGI p95 保留为诊断。不要接受旧脚本 overall=pass 作为新目标通过。公网/浏览器与同机完整 HTTP 分开记录的现有写法正确。
2. **磁盘预算与失败候选清理。** 将已完成研究报告的估算并入 Task 3：primary 0.3–1.5GiB 仅估算，store 2GiB 停；常态 ES 总增量预算 3–7GiB，首次额外峰值 8–10GiB，预先给出宿主 free bytes 停止线与原业务增长余量。除了 Docker 日志还需有限 GC 日志和 heap dump 策略。TEST/PROD 不同主机，各算各的；PROD 约 1.497GiB 旧六表回收不能提前抵扣首次峰值，也不能扣 TEST 回收。阈值失败只保留小型统计和明确诊断所需对象，不无限保留未启用候选索引或重复镜像。以上都不是实测达标声明。

## 已满足的关键边界，不要求扩大评审范围

- date_sort 用 keyword 保留零月日，单 primary/零 replica 如实承认非高可用；精确 total、失败 shard/timeout 不冒充空成功的约定合理。
- TEST 先旧 CLI disable，实际 Web/cron/receiver 无旧依赖后才 drop；40 个白名单 guard 在六表之前移除，同事务、短锁超时、RESTRICT、未知结果查 catalog，顺序正确。
- 四读进程退役、SQLite/legacy 回退、报告和段位继续使用 PG 的方向正确；需按 I3 修正读取量。
- 受限 native receiver、安全目标/凭据边界、同 manifest 幂等、无公开 9200、PROD raw Docker 不重建既有 Web/PG 均已覆盖。
- 旧 prepare 不再重试，按完整对象 ID/路径清理，保留业务表、实际运行/shared image 和必要回退，禁止全局 prune，符合“不浪费磁盘”要求。prepare05 的 create 400 不是活动写入或生成成功。
- 不增加 CDC、outbox、通用依赖图，不以假设改名需求扩张一期范围，也不要求新 UI 设计。

## 计划缺口与执行前验证的区别

上面的 I1–I5 是首稿中的逻辑/来源/步骤缺口，需要修改计划；小修正则可直接落入既定任务。ES 固定版本与 digest、实际 store/峰值、1GiB heap 能否承受深页、共享 8CPU 上完整 HTTP 100QPS、页面和 RK 实际体验，均是**实施时必须测量的结果**，本次没有 ES 环境不能提前判通过，也不因此要求现在部署或多做一轮研究。

第二轮只复查上述修订及其内部一致性。若仍有未决行为，明确标出，不以未来测试替代方案；不追加第三轮。
