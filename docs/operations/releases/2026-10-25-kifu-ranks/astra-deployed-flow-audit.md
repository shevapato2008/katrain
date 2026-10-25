# 棋手等级：独立部署后真实流程审核

**结论：Approved，限定于已授权的三 ID 等级纠正、同包 TEST→PROD 发布、RK 展示和新 producer 的实际有界轮询。当前没有未关闭的产品 must-fix。** 不能据此宣称已实证“全新空 rank 棋谱首次插入”，也不能宣称完整覆盖七天来源或 3300 秒硬截止。

这是 fresh、独立的 Astra Max 部署后审核，不重复部署前代码终审。审核于北京时间 2026-10-26 凌晨完成；独立在线抽查主要发生于 UTC 2026-10-25 17:23–17:32。读取了两处 AGENTS、`kifu-album-sync`、`server-deploy`、批准计划、代码终审和本目录部署证据；随后实际 SSH 只读核查两云数据库、API、运行镜像/文件、调度记录/有限日志及 RK 精确文件。数据库连接显式设置 `READ ONLY` 和 8 秒语句超时。未执行采集、翻译、模型调用、发布、重放、迁移、服务/锁/队列变更，也未运行会保存产品报告的 verify 脚本。仅写本审核报告；未读取私有棋局或 Chat，未枚举、glob 或读取 filesystem `data/kifu-album/`，未输出凭据。

**发布版本与实际运行一致。** 独立 `git ls-remote` 核实 feature 与 `origin/develop` 均为 `93f2038a0020d43b3090b1a71c8877980580f740`；Smartbox `origin/main` 为 `51825c0e00a7f58544193ea6d584489252c6887e`，该提交的 `vendor/katrain` gitlink 指向上述 source。实际三个容器的 image、`KATRAIN_BUILD_SHA`、39 个发布清单内运行文件摘要均与部署回执一致；包括环境、挂载和运行配置的整体摘要也一致，未打印其中原值。

| 运行对象 | 独立核实的 image |
| --- | --- |
| TEST Web | `sha256:e5b77e0a6165617132900d22104bc7fbfe91b760b81ade7822f63fb345a2281f` |
| TEST cron | `sha256:d67fcb72cbb31470b8cbbc24745ff0826fc7111e8594b64dbfecfaa98a46dc44` |
| PROD Web | `sha256:dd83ae55fdb2549844be8d4d8f518b24f671990471a4b7d3f2b876555863ce2e` |

双端健康 API 均返回 200/ok。PROD 原分析 cron 仍是 `katrain-cron:board-consistency-56f53fa4`，启动时间为 10-10，其旧配置无 ingest 启用项；没有成为第二采集/翻译端。两云的 COPY overlay、其他服务保留和部署顺序由 [TEST Web](test/web-deployed.filtered.json)、[TEST cron](test/cron-retry-deployed.filtered.json)、[PROD Web](prod/web-deployed.filtered.json) 记录支持。首轮 cron 的 `runtime_settings_changed` 拒绝及自动回滚也保留在 [原回执](test/cron-deployed.filtered.json)，最终成功没有掩盖这次失败。

**同一冻结包的权威、身份映射和数据完整性已在线核实。** 精确读取持久 stage 的 `rank-corrections/three-games-v1.json`，重新计算 canonical SHA 为 `1db149a53968f4a4b6c524624034ce876afc9d351434ef32e2e4114cd61675f2`，文件 bytes SHA 为 `d69ce9788ca34009af508e05b87b35e92cefee62cd7a0dbdda6c3f64891bb283`；两种摘要不同是 JSON 编码与 canonical 表示的区别。纯只读 rank/报告验证函数均接受该 v2 rank-only 包、六个事实，以及双端各 15 项五语详情和 3 个公开卡片证据；报告 receipt SHA 均匹配保存的原生 receipt。

独立查询真实 native batch `927` / `920` 的 artifact，二者都保存该 manifest SHA、同一 publication key、`rank_only` 模式及六个 rank bindings，各自 receipt 与 [TEST](cloud/test-apply.json)、[PROD](cloud/prod-receipt.json) 完全一致。publication key 为 `rank-only-19x19-91637528-91638738-91694911-v1`。实际重放由 [replay-result.json](cloud/replay-result.json) 证明双端回执相同；本审核没有再次执行重放。

| source ID | TEST album | PROD album | 冻结黑 / 白 | 原 rank |
| --- | --- | --- | --- | --- |
| 91694911 | 179093 | 178757 | 7p / 4p | 两侧均 null |
| 91638738 | 179085 | 178749 | 5p / 5p | 两侧均 null |
| 91637528 | 179084 | 178748 | 5p / 7p | 两侧均 null |

两个库中三盘的完整 album 行（SGF 以摘要比较）、source links、原 native batches/原 artifact 摘要，均与部署后的精确证据相等。另独立比较保存的部署前后像，原字段/原链接/原批次/棋谱数确实不变。TEST 三个原 StateStore 行仍是原 `prod_synced`、原 publication key，整行摘要不变。棋谱总数两端均为 `176876`，history 和 snapshot 均为 `6/6`；没有新增重复谱。实际 snapshot 六个内容摘要在两库相同；唐奕等人物的当地 ID 存在差异（例如 TEST 483、PROD 482），对应同一逻辑人物和事实，未把裸本地 ID 跨库沿用。

六个 current 均为 qualified/professional_dan，依据日期从 2026-09-05 至 10-19，`valid_from` 全为 null；观察/匹配时间另存为 10-25。这里证明的是“库内最新已知资料”，并非比赛当时或今天重新确认的等级。真实 PostgreSQL 当前 unique-current 索引覆盖所有 `is_current` 行，snapshot 每盘每侧唯一，fact FK 为 RESTRICT；两端实际关键约束已抽查。精确 004 SQL 的临时表演练和零 public 假业务行由 [TEST schema](test/schema.filtered.json)、[PROD schema](prod/schema.filtered.json) 支持，本审核未重新做写入或并发破坏实验。

**用户看到的等级与冻结包一致。** UTC 17:27–17:28 独立直接 GET 两端全部三盘 × 五语详情，共 30 项，均 HTTP 200；逐项比较原黑白/赛事、显示姓名/赛事、规范化 SGF SHA、source、两侧 raw/display/origin 和完整 provenance，全部与冻结验证证据一致。再 GET 两端公开第一页，前三张分别为 7p/4p、5p/5p、5p/7p，完整来源字段相同；第 4–6 张 display 为空、origin=unknown。没有把未知强行补成等级。

另直接 GET TEST `178908`：原白方“三段”，API 仍显示“三段”、origin=source，SGF SHA 为 `e666a1653dfc74ef5340f2bb104d13b7ee0ee43e6485be3bbaafb608b9d055e1`；同一上野梨纱在六个 current 中为 4p。该真实样本证实原谱优先。`3002` 不被当成段位、严格黑白/SGF/人物绑定、旧包在 current 推进后不漂移等边界沿用已批准代码；部署运行文件与该代码一致。本轮没有为演示晋段而修改真实 current。

RK 的远端 release manifest 与本地保存件字节相同，记录 1191 文件；独立抽查六个 rank/API 核心文件、strict index 和入口 JS，八个 hash 均匹配。入口 `index-BL-M4qBg.js` SHA 为 `19e60d9e3d65f3b5167785f7562a9b3fd479abaaa3cc1af9baaf0f78d2dd4719`。已目视 [1024×600 实屏](rk/page1-after.png)：首两张可见卡片的职业等级、姓名和结果关系正确；其余卡片/未知节点以 [实际 DOM/API 记录](rk/page1-browser-verification.json) 核实，不把屏幕外节点称作截图中全部可见。记录的字号为 18px，结果中心差 0。实际运行 PID、相机/模型/本地引擎健康及 462 个保护项不变由 [运行验收记录](rk/runtime-verification.json) 支持。

本审核时 RK 已按 [恢复回执](rk/entry-restored.filtered.json) 回到原 Chat 上下文，独立 `systemctl show` 为 inactive/MainPID=0，未启动或导航设备。当前文件核验与先前真实运行验收相衔接，不声称本次重新观察了运行中的相机或页面。Smartbox parent SHA 是发布 gitlink 上下文；此次设备复制范围只有 vendor/KaTrain，未把它扩大为整个 parent 已部署。

**小时同步在部署后确实运行，边界也真实保留。** 独立查询 TEST 当前调度：enabled=true、interval=3600、control=[]、consecutive_failures=0。手工有界轮 UTC 16:43:12→16:47:01 成功，228256 ms；之后自然小时轮 17:13:19→17:16:59 成功，220011 ms、error_count=0。后者证明正常调度已恢复，不只是手工脚本结束。

独立读取该自然轮的有限 docker 日志和 stage head：窗口为北京时间 `2026-10-19T01:13:23+08:00` 至 `2026-10-26T01:13:23+08:00`，5 页/100 ID、60 HTTP/55 SGF、39 超窗、19 本轮终止条目。日志明确 `actionable_window_pending=0`、`needs_credentials=0`、`legacy_pending=0`，同时输出 limited source coverage；`head_page_cap=true`、`boundary_in_window=false`，不能把 completed 或 pending=0 解读成七天全量无遗漏。全 stage 日志的 terminal=72 与本轮 coverage 的 19 是不同统计范围。

七个固定 2021 坏项的 attempts 仍为 64、64、64、64、64、1、1，rolling cursor 仍 `1786`；`91571067` 仍 failed/terminal，没有解除冲突隔离。实际配置为 window7（代码硬上限14）、head5（硬10）、HTTP160（硬240）、SGF100、recheck20、source600秒、recovery300秒、total3300秒、token100000；名称 LLM 的既有启用状态保留，未为本功能增加额度或调用途径。429/Retry-After 整源退避及7004/逐条隔离由已审核且摘要相同的部署代码维持，本次成功轮未制造429以重试该分支。

实际 `.writer.lock` 仍是 inode203039078、uid/gid0、0600；control 恢复原“无行”，审核时无 ingest advisory lock。维护过程、旧 writer 等待、第一 holder TTL 后继续暂停及第二 holder 验证后恢复的记录与最终自然轮状态相符，见 [phase 2](test/maintenance-phase2-ready.filtered.json)、[phase 1 控制恢复](test/phase1-control-restored.filtered.json)、[旧 holder 退役](test/phase1-lock-retired.filtered.json)。本审核未重新获取/释放锁。中断恢复及幂等的所有异常分支不能由一轮 success 证明；实际精确重放和恢复后的自然轮提供部署证据，其余沿用代码终审的聚焦验证。

**一处证据缺陷已明确纠正，不能继续引用原结论。** 实施方在审核期间主动指出，`run_bounded_source.py` 和 `three_snapshot.py` 用 YYYY-MM-DD 拼接账本名，真实 DailyTokenBudget 使用 YYYYMMDD。独立检查确认，所以 [source-round-result](cloud/source-round-result.json) 的两个 `ledger_sha256:null` / `token_ledger_unchanged:true`，以及 before/after 中那个不存在的 ledger 项，均不构成实际账本前后不变的证据。产品预算实现没有这个文件名错误，错误限于证据采集脚本。

独立读取正确的 `qwen-usage-20261025.json`：SHA `2f2b2b17ac6c56121e55f8c2ff0f1f17f00633e5c8695df2b1dc3187a1325b90`，25 条账本记录、9 条 call；最后 call 为 UTC 08:59:56.244425，mtime 为 08:59:56.245057，发布窗口15:00之后 call=0。结合原生 rank-only 路径和完整性结果，支持此次纠正及两轮 producer 未新增该调用通道的模型调用记录；**仍没有补出发布前真实账本 SHA 前像，也不把这一抽查称作全系统计费审计**。[补充证据](test/final-schedule-ledger.filtered.json) 与 README 已清楚纠正原主张，无需为补前像重跑付费任务或阻塞三盘产品交付。

**保留的证据与能力边界如下，均非此次已授权切片的未关闭 must-fix。**

- 两个实际有界轮没有合法、尚未入库的新来源，故新空 rank 棋谱从首次准备、必要名称翻译、全新 insert 到同包 PROD 的整条线上路径尚未实证。三盘已有谱的 correction、既有测试和当前轮询成功不能替代它；应等自然合法样本，不制造数据或解开隔离。
- current 以后晋段、冲突及断线后旧包不漂移，已有部署前独立代码/合成回归证据；本轮真实 history 只有六条初始事实，没有发生实际晋段。当前等级不承诺自动追踪每位棋手的真实升段，未新增人物爬虫。
- 来源无可靠 updated_at/upload-time 过滤；有限 head 与内容指纹不是“最近一小时全部更新”的保证。历史深页、旧78盘此前恢复后的完整状态不在本次重做范围，也没有重发旧回执来凑成功数量。
- 3300 秒是协作准入预算，不是正在运行的同步数据库/原生 receiver 线程的硬截止。普通新谱首次发布仍存在全 SGF 缓存冷路径；“此前约20分钟”是历史运行限制，不是本轮复测值。rank-only 的早分支避免了它，本次没有承诺新入库稳定在数分钟内。保留单 writer 到实际结束比超时后另开写者更符合当前数据完整性边界，因此这个已披露限制可接受，但后续不得把小时调度频率当作每轮硬完成 SLA。

已逐项核对本目录 README 的上述发布、三盘结果、运行证据和限制主张，与实际抽查一致。审核未重跑392项基础测试，未扩张到全库、其他UI或旧小时引擎审计。当前交付可以完成；后续自然新谱的首次插入证据仍应如实单独记录。
