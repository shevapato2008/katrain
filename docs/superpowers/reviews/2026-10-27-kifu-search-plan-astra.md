# Galaxy 棋谱搜索 200ms：整体计划审核

日期：2026-10-27。审核基线：`e9b4d3ecce03b3269f12922a476fd6d6c6545547`。范围：[实施计划](../plans/2026-10-26-galaxy-kifu-search-200ms.md)、[性能调查](2026-10-26-galaxy-kifu-search-performance-investigation.md)，并核对实际搜索、proof、dispatcher 和前端状态代码。

**结论：Approved。首轮发现的两项必要修订已由实施负责人接受，随计划和实现直接落实；不需要第二轮文案审核或用户再次确认。** 此结论批准最小实现路线，不代表代码已通过审核或 200ms 已实测达标。

## 先审规格：两项必须落实的修订

1. **唯一棋手 fast branch 仍需探测 selected raw 的子串碰撞。** 四类名称的精确候选不覆盖所有既有搜索入口。`identity.py:970–1001` 的 `strict_selected_event_search_ids` 会以 `KifuAlbumEventSelection.selected_raw.contains(q, autoescape=True)` 找到已选择赛事；即使该赛事的批准展示名并不精确等于 q，其有效棋谱仍可能加入结果。只检查四张名称表就提前返回棋手 ID 会漏结果。最小修订：用相同匹配语义的标量 `EXISTS`/有限候选探测；任何潜在 selected raw 命中均回原兼容分支。零命中时可跳过完整 selected-event proof，仍满足不读取无关审核 JSON 的目标。增加一个“唯一棋手名同时出现在另一已批准 selected raw 中”的等价性用例即可。无需新增搜索索引体系。

2. **新增 `player_id` 必须透传现有远端链路。** `kifu.py:275–279` → `core/repository.py:247–250` → `RemoteKifuRepository.list_albums` 目前只传 q/page/page_size/lang。按计划字面保持参数不变，会让盒端接受 `player_id` 后返回未过滤全库。最小修订：沿这条现有链路传递可选 `player_id`，在分派前统一校验与 q 互斥；保留 async、离线/故障返回语义。补一个参数透传断言即可，不需要改 dispatcher 架构。

上述两项之外，规格覆盖充分：保留五语与别名、同名及 raw scope、当前审批和内容、可见性、精确 total、稳定排序分页、rank/report 和首盘 SGF；错误、取消、空结果与有效成功均有清晰边界。非 strict 模式的旧 alias 路径仍须按计划保留，不能因已发现一个批准棋手而提前绕过它。

## 再审最小落地与可维护性

- 三条索引对应已观测到的访问形态；保留原 `display=q OR lower(display)=q.lower()`，本轮不再缩成单 lower 谓词。显式、逐条 `CONCURRENTLY`，核验实际定义及 valid/ready，不放进 Web 启动，范围适当。
- proof 按实际证明族 lazy 构造与请求内复用可直接削减已知重复成本。复用的只是对相同当前内容算出的 digest/membership；后续使用仍刷新 mutable batch/source/name/evidence，保留 `populate_existing` 和现有同请求撤销测试，不以持有 ORM 对象或相同 batch ID 作为新鲜度依据。
- 本地同步读取整体进入拥有 Session 的 worker 是合理边界；返回已完成的响应数据，Session 在同线程关闭。复用受控线程池，按实际并发与当前 DB 配置核算，不额外建设队列或连接平台。
- 前端一次接受当前 list/total/preview，修正 selection，配合 AbortSignal、旧响应 guard 和同词重试，覆盖已复现的问题。聚焦状态测试与一次 1280×720 真实可操作预览足够，不需要视觉重构或全状态截图。
- Task 5 投影、Redis、HBase 均不提前实现。只有上述最小改动实测仍未过预算且剩余成本支持该选择，才收敛下一必要步骤；不得默默把本次实施扩为写契约/缓存平台。

## 执行和交付边界

按最新任务授权采用两阶段：实施阶段只改代码、做本地验证和只读环境探针，**不提前改变 TEST 部署版本、不执行 TEST/PROD DDL**。完整代码独立审核通过后，才按仓库顺序同步并发布 feature、合并并发布 develop、更新父仓库 main 的 submodule，再先完成 TEST 正式版本部署、显式索引变更与实测，最后发布新 PROD。

PROD 目标以 `ubuntu@117.50.177.254` 的实际运行容器/配置为权威；旧机已退役，不根据历史调查表或旧别名向旧机发布。TEST 唯一小时 writer 不停、不 kill，不终止其 DB session。DDL 在已授权的自然低负载窗口按预算执行，报告 invalid 遗留而非盲目重试。

验收按计划的 1 与 4 客户端各约 30–50 次聚焦样本，包含不同棋手首次查询、精确结果/total/顺序核对以及有限自然导入窗口；同请求观测 server、TTFB 和正确列表/棋盘实际绘制。已建立连接与新连接分开报告，样本尾部分位不外推为总体 SLA。200ms 只有完整正确结果达标才成立；达到目标即停止追加工作。

本轮为计划与源码审阅，未运行产品测试、未操作服务或数据库。没有其它阻断实施的问题；后续独立代码审核聚焦上述两项修订和已有审批/当前内容边界，无需重新开启设计讨论。

## 第 2 轮：Task 2b 最小 SHA 编译缓存增量

日期：2026-10-27。仅审核当前 Chunk 5、[TEST 结果](evidence/2026-10-27-kifu-search/test-after-summary.md)、[display profile](evidence/2026-10-27-kifu-search/test-display-profile.txt)及 first-pass reader 接口；不重审首轮已批准代码。首轮已发布至 develop `dc17489e2`、父 main `f44676ae`，TEST 正确性通过但 200ms 未达，PROD 尚未发布。

**结论：Approved。当前收敛后的完整 artifact 原文 SHA 方案没有阻断实施的问题；计划审核到此结束，不需要第 3 轮文案审核。** MVCC row-version 协议已撤回，不在本轮批准范围，也不得作为实现中的替代捷径；server 预热 hook、全 artifact 扫描及投影/epoch 均不在本轮范围。

实测已把主要成本定位到 first-pass 的快照 deepcopy 与 bundle/member 编译。只缓存经过校验的 candidate/research 哈希集合及 shared-displays，能直接移除这部分重复计算，并保留当前源数据及审批的读取边界。约 59.5ms 的单次 SQL SHA 样本不能单独证明完整链路能否达标；先实现、再少量真实复测的顺序合理。

实现和独立代码审核须守住以下已约定边界：

- **内容与状态必须来自同一读取。** hit 的 key 和 proof 输入使用该 SQL 返回的 fresh scalars、完整 artifact 原文 SHA；miss 在另一个单独 statement 同时取得 artifact、新 SHA 和 scalars，并完全使用这组新值。禁止把旧 header key、旧 ORM artifact 或只存储的 bundle SHA 与新内容拼接。每次后续 proof 读取都重新取当前状态，保留同请求撤销测试。
- **缓存只替代纯编译。** canonical bundle 校验仍在 miss 完整执行；每次请求仍校验当前 candidate/research、owner/name/evidence、source、creation ledger 和 raw scope，rank/report 保持原路径。编译结果不能携带可复用的最终 eligible/批准结论。dirty Session、混合证明族、缺少有效 guard 均走原 reader。
- **命中不得隐式再读或误用旧 artifact。** `populate_existing` 与 defer 配合时，调用点不能继续通过通用 `image(batch)` 或访问 `batch.reviewed_artifact` 触发大 JSON 加载；first-pass 的 compiled 分支应显式使用同语句的小字段。原 reader 分支继续保留完整输入。此项同时防止快路径失效和不同读取时刻的数据混用，不需要引入新的 ORM 抽象。
- **共享的是内部 bytes。** 64MiB payload / 1024 项 / 单项 1MiB 边界、每次私有解码和短锁范围足够；淘汰或并发 miss 只影响速度，不能使旧 key 的编译结果冒充新 key。无须增建缓存服务、后台刷新或 single-flight 平台。

最低充分验证沿用计划中的聚焦用例：跨请求复用；artifact 类型/符号零及内容变化；状态/hash 与 held-ORM 刷新；同请求撤销、live source/scope 与 dirty Session；私有解码和容量边界。补足一次 header→miss 之间内容改变时的新 key 绑定断言，并在现有 TEST 的只读真实查询中核对 PG SHA 返回与完整结果即可；无需再做已撤回 MVCC 的物理 tuple/rewrite/XID 测试。guard/编译失败不得变成成功空结果。

本轮先不预热。hit、miss、首次不同姓名的真实完整 paint 分开保留，未达标即停止扩样并报告剩余分段成本；不得用热命中代替首次搜索目标。后续按既有独立代码审核与标准发布顺序推进，TEST 门禁通过前保持 PROD 不变，继续保护唯一小时 writer 和当前 Compose 非 web 配置。本轮未改业务代码、未运行数据库写操作。
