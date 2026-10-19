# 棋谱库小时增量与五语言发布 Implementation Plan

> **For agentic workers:** REQUIRED: Use `superpowers:subagent-driven-development` after the user approves this plan. Parallelize only tasks with disjoint files and stable contracts. Steps use checkbox (`- [ ]`) syntax. Root coordinates database writes, release and deployment.

**Goal:** 先对 MacBook 已抓取但尚未整理、翻译的 5,536 盘新谱（2026-01-31～2026-10-10）完成解析清洗、去重归并和五语缺口补齐，再回填测试库并验证同步正式；随后交付每小时持续抓取、处理和同步流程。

**Architecture:** 一个 `katrain-cron` 增量任务、一个库外持久暂存区、现有 catalog/证据/批次基础及受限正式接收入口。查询翻译在事务外完成，棋局、名称及受影响范围在目标环境同一原子事务中发布；保留 native 全库快照和锁，事务耗时按实际回执记录。测试验证后转发同一不可变逻辑包。

**Tech Stack:** 现有 Python 3.11、HTTPX、SQLAlchemy、PostgreSQL、APScheduler、SGF parser、catalog 五语解析器、Docker；使用已获用户授权的 Qwen Plus API，专用持久账本每日最多 100,000 token。

**PRD:** [prd.md](./prd.md)
**日期/状态：** 2026-10-20 文档整理快照。核心开发、独立代码审核、两库迁移及 B 单盘真实闭环/重启恢复已完成；A 回填、最终 Web 更新与持续 hourly 启用尚未完成。下方带时间的执行记录保留为历史，不能作为最新总数。用户指定本目录覆盖 writing-plans 默认存放位置。

### 当前状态快照

以下数量来自 root 本次交接时已验证回执；下一 A 包正在执行，未把在途写入计作验证完成。

| 项目 | 已确认状态 | 尚未完成 |
| --- | --- | --- |
| A first pass | 原始 5,536 盘中 5,279 盘形成审核绑定就绪包，257 盘隔离 | 就绪数不是入库数；隔离盘不公开 |
| A TEST | 2026-10-20 05:08 已验证4,578条来源：4,575新增、3精确复用；038c已通过原生/实际API核对 | 046c/047c方法修正已独立签署，v2队列继续 |
| A PROD | 同时点已验证3,378条来源：3,375新增、3精确复用 | 只接收TEST已验证的同一不可变包 |
| B 真实小样 | A 以外另 1 盘，两端 `prod_synced`；TEST173066 / PROD173046；五语、列表、幂等重放及 cron 重启恢复通过，专用账本 6,324 token | 4 条旧 prompt-only 隔离恢复脚本已准备、未执行 |
| 代码与部署 | 已发布完整整合代码128697a32；TEST cron当前e694、两端Web当前b894；128三份候选镜像已完成源码/静态哈希和导入检查；本轮新方法检查也已独立审核通过 | 最终候选需包含本轮已提交方法检查，A两库完成后再部署 |
| 持续调度 | 已批准 Qwen Plus 每 UTC 日 100,000 token、3,600 秒、每轮最多100盘/20新名称；持久 Compose 路径已核对 | B 仍 disabled / LLM disabled / cap0，全部 A 完成后协调恢复与启用，并观察真实下一轮 |

临时 A ops 两路只读校验试验已收敛，不宣称加速。后续 A 采用已独立审核的全量原生事务检查、全量提交后 DB 对账和代表 HTTP 样本，实际口径见文末；B 产品代码保持逐盘 HTTP 验证。最终 Web 替换前保存最新 `/tmp/kifu-backfill` 与四份实际 ops/helper，不把临时工具烘入产品镜像。

当前快照不表示已做完 20 次前后性能基准、全量 manifest 重放或浏览器视觉验收；相关未执行项继续保留在下方。

---

## 0. 执行边界与审查方式

### 两项交付的执行顺序

| 交付 | 执行路径 | 不应等待的事项 |
| --- | --- | --- |
| A：5,536 盘整理、五语处理、测试回填与正式同步 | Task 1 固定原始清单 → 下方 A1 清洗归并 → A2 复用词典并补齐五语 → Task 2/3 必要发布适配 → Task 7 相应检查 → Task 6 回填；需要发布代码时执行 Task 8 相应步骤 | 不等待 B 的小时抓取、服务器模型选型和调度全部完成；但不能跳过本批整理与翻译 |
| B：持续小时增量 | 共用已稳定基础，再实施 Task 4A/4B/4C、Task 5，最后完成 Task 7/8 的剩余验收与小时启用 | A 已验证的成果不重新抓取或重译 |

A 如有新增代码或正式同步需求，仍须完成相应审核与安全发布。已有导入能力和旧库名称词典优先复用；A 的首次名称工作可由当前 Codex 会话的独立 agent 并行完成，不为等待 B 的服务器 API 自动化而推迟。两项分别报告状态与数量；任务章节编号不是要求所有开发结束后才允许执行 Task 6。

### 任务 A 新增前置步骤：先整理、翻译，再回填

**本次更正：** 5,536 盘只是已抓取的原始棋谱，不是已整理、已翻译的数据包。实施顺序固定为：`原始 SGF → 解析清洗与去重 → 复用旧库译名、补齐五语 → 独立审核 → 测试库回填与验证 → 正式库同步`。每一步分别统计进度；解析成功或生成翻译候选，都不能计作已完成翻译或已入库。

- [x] **A1 · 整理：** 固定 5,536 盘来源清单与原始哈希；解析 SGF，拆分姓名/当时段位，处理 EV/GN 选择和格式异常；按无歧义证据关联/归并棋手、赛事类型和届次，轮次单独保存。输出解析成功、修正、重复、冲突和待处理数量。
- [x] **A2 · 五语：** 对清洗后的独立棋手及赛事核心/原文标题建立缺口清单，先复用旧库合格 `cn/tw/jp/ko/en` 词典与已有模板；并行处理缺口，保存维基/棋院链接或如实标记直接翻译、转写方法。已完成合格 5,279 盘的五语绑定，另 257 盘明确隔离，未将其冒充已译完成。
- [x] **A3 · 审核与生成包：** 新名称一次独立审核并检查身份、五语完整性、数字/年份/轮次；按各棋局绑定名称和证据生成固定发布包。校验全部条目都有可解释状态；未完整条目不公开，不伪报整批完成。
- [ ] **A4 · 入库：** 完成上述步骤及必要代码审核后执行 Task 6；先测试库、验证后正式库，每批记录双口径覆盖率和剩余待办。原始清单不因回填进展而动态更换。

- [x] 用户已明确授权开始实施，并更正确认 5,536 盘未整理、未翻译。A 由当前会话先整理和补齐名称；B 的模型提供方、预算与自动同步策略单独确定，未经确认不擅自购买或切换付费服务。
- [x] 独立 GPT-6 Astra、`max` effort 已完成两轮 PRD/计划审核，修改后通过；结论见本文末尾。本次事实更正不追加第三轮计划审核。
- [x] 已按 `using-git-worktrees` 创建 `.worktrees/kifu-hourly-incremental`，保留原工作区分析任务相关未提交文件。根 agent 处理共享 Git；子 agent 不同时改同一文件。
- [x] 用 `subagent-driven-development` 分派独立任务；先稳定共享契约和原子发布，再并行抓取、翻译、接收器三个边界。
- [x] 完成后用 `requesting-code-review`，派独立 Astra max 审核生产写入、证据资格、重试及完整 diff；修复 must-fix 后复核至通过。普通文案和配置只做聚焦检查。
- [x] 本任务未停止或重选正在运行的 1,000 盘分析，未修改其 SGF/棋局 ID；正常 cron 分析继续固定 GPU1，增量任务不调用 KataGo。后续发布继续遵守此边界。

## 1. 文件与责任边界

以下为已实现文件与实际责任边界；没有新建 `contract.py` 或 `receiver.py`。

| 操作/路径 | 实际责任 |
| --- | --- |
| `katrain/kifu_ingest/inventory.py`、`exclusions.py`、`data/historical-exclusions-20261011.json` | 本地清单、来源差集和带依据的历史排除 |
| `katrain/kifu_ingest/state.py` | 两张任务表、阶段 CAS、稳定 UUID、包哈希和回执 |
| `katrain/kifu_ingest/preparation.py` | 复用现有 SGF parser、姓名解析和 GN 选择，纯派生元信息；未修改历史 `scripts/import_kifu.py` CLI |
| `katrain/kifu_ingest/source_19x19.py`、`staging.py` | 限速来源读取、原始 SGF/元信息、发现与滚动游标、原子文件保存 |
| `katrain/kifu_ingest/names.py`、`name_reuse.py` | Qwen producer/reviewer、资料候选及有限名称/模板复用 |
| `katrain/kifu_ingest/catalog.py` | 不可变包/名称契约、目标身份解析、native 原子发布、范围续签与条件补偿 |
| `katrain/kifu_ingest/sync.py` | 固定受限 SSH、测试回执检查及实际五语详情/公开列表验证 |
| `katrain/kifu_ingest/orchestration.py`、`scripts/kifu_incremental.py` | `inventory/prepare/run-once/receive/status` CLI 与库外准备入口；receiver 子命令在此实现 |
| `katrain/cron/jobs/kifu_ingest.py` | 冻结包优先恢复、阶段编排、持久 UTC 日预算、session advisory lock |
| `katrain/cron/migrations/003_kifu_incremental.sql` | 仅本任务两张表及约束；两库已显式执行 |
| `katrain/cron/config.py`、`scheduler.py` | 默认关闭的新 job、参数及现有 RunRecorder 注册 |
| `Dockerfile.cron`、`requirements-cron.txt`、`docker-compose.kifu-ingest.yml` | 共享代码/资源依赖、SSH 客户端及 opt-in 持久挂载配置 |
| `tests/test_kifu_incremental_*.py`、`tests/cron/test_kifu_ingest.py` | 清单、来源、准备、名称、状态、CLI 与恢复检查 |
| `tests/web_ui/test_kifu_incremental_catalog.py`、`test_kifu_incremental_postgres.py` | 目录资格回归和独立本地 PostgreSQL 并发/发布/补偿验证 |
| 本目录 `prd.md`、`plan.md` | 决策、版本、数量口径和历史执行记录 |

**镜像边界：** 已在 cron 镜像显式复制本功能共享包、SGF parser、catalog/schema/config/数据资源并补足实际依赖，离线 import smoke 已通过。导入不启动 FastAPI/Kivy，也不通过 Docker socket 操纵其他服务。Web e694 候选镜像只覆盖 b894 后实际变化的 job/sync 两文件，其余源码和三套前端文件树保持原镜像内容。

## Chunk 1：实况清单与共享发布基础

### Task 1：核对本地数据、两库和来源分页

**文件：** 运维入口的 `inventory` 模式、本目录现状记录；不写业务数据。

- [x] 已读取两库 schema、公开/隐藏/重复基线、来源及身份差异，保存历史排除依据；历史报告不代替现场查询。最终 fresh 全库资格指标仍按 Task 6 留待汇总。
- [x] 在 Python 内扫描本地 `19x19/data/kifu`，输出总数、实际 SGF `DT` 范围、解析失败数、来源 ID 差集；避免输出完整文件列表。不得列举或读取受技能保护的 `data/kifu-album/` 目录。
- [x] 确认这批新增谱尚未整理/翻译；从原始 SGF 与旧库合格词典建立“解析待办 / 名称可复用 / 五语实际缺口 / 区间外 / 日期待确认”清单，进入 A1～A3。仅复用可核对的既有名称，不重复等待不存在的新增谱译名文件。
- [x] B 已真实读取来源并下载小样；实现从第0页及独立滚动游标发现、分页限速与跨页去重，不以第一条旧谱或较小ID停止。
- [ ] 来源排序保证仍未建立；如需补充间隔页抽样结论，单列有限只读检查，不把当前观察冒充来源上传顺序保证，也不阻塞 A。
- [x] 将历史删除、隐藏、合并来源加入排除/匹配清单；将可确认的已删来源 ID 持久化为带历史决策依据的排除项，后续滚动扫描也须遵守，不能只在首次回填内排除。核对待导入不是“155,947 份全部重新入库”。
- [x] 记录初始实际新增量、最新日期、五语缺口及两库身份映射差异，确定前部扫描与滚动对账预算。

**验收：** `inventory` 本身只读，不带额外只读 flag，不执行 DDL/DML；输出逐条 entry 和末尾 summary 的 JSONL。若缺删除决策依据，相关 ID 保持隔离，不先恢复。

### Task 2：固定包契约和最小持久状态

**文件：** `state.py`、`catalog.py`、`orchestration.py`、`003_kifu_incremental.sql`、实际 `tests/test_kifu_incremental_*.py`。

- [x] 先写重复来源ID、重复批次、同publication_key异哈希/稳定UUID及非法阶段跳转的失败测试。
- [x] 实现 `kifu_ingest_batches` 和 `kifu_ingest_items`；迁移只建本任务表/约束，不调用全库 `Base.metadata.create_all()`。
- [x] 定义实际逻辑包 `format/publication_key/games/decisions`；包哈希单独计算，`batch_uuid` 由任务 journal 生成；身份用可移植 canonical 名称，目标库重绑 ID。
- [x] 区分来源键、原始字节哈希、规范 SGF 哈希、物理本地主键。数据包哈希覆盖全部业务与名称内容，传输凭据不入包。
- [x] 定义逐项状态 `discovered → downloaded → parsed → names_ready → test_published → test_verified → prod_published → prod_synced`，以及带失败阶段的 `retry_wait/quarantined`。published 仅证明提交，verified/synced 才包括实际 API 验证；幂等重放和部分通过有明确回执。
- [x] 持久化原始文件引用、raw/sgf哈希、attempts、next_retry_at、错误和两库回执；发现/滚动游标在 Stage manifest，条目/批次阶段与回执在 StateStore。
- [x] 跑聚焦测试并提交该独立基础。

**实际字段结构示意（占位哈希与文本，不能直接发布）：**

```json
{
  "format": "kifu-incremental-manifest-v1",
  "publication_key": "<stable-logical-key>",
  "games": [{
    "source_key": "19x19",
    "source_item_id": "<numeric-id>",
    "origin_path": "data/kifu-album/19x19/<numeric-id>.sgf",
    "raw_sha256": "<raw-file-sha256>",
    "sgf_sha256": "<complete-canonical-sgf-sha256>",
    "sgf_content": "<complete-SGF>",
    "metadata": {"player_black": "…", "player_white": "…", "event": "…", "date_played": "2026-02-01"}
  }],
  "decisions": []
}
```

`decisions=[]` 只适用于目标库已有合格名称可复用的包。新增名称决策实际包含 `kind/key/displays/methods/original_language/sources/source_items/producer/review`；`displays` 和 `methods` 都是 `cn/tw/jp/ko/en` 对象，有限成员为 `source_key/source_item_id/slot/sgf_sha256`。审核绑定完整文字、证据及成员哈希；不能仅填写一个 approved 标志。可选 `identities` 使用 canonical_name，不传跨库整数ID。传输 envelope 为 `manifest/manifest_sha256/test_verification`，不是 manifest 内的 UUID/payload 字段。

### Task 3：解析复用、身份匹配与原子范围续签

**文件：** `preparation.py`、`catalog.py`，复用已有 parser/name_parse/event_selection/name_batch/name_first_pass/identity；catalog 与真实 PostgreSQL 聚焦测试。

- [x] 先构造已合格 raw-event 的旧棋局，再加入同原文新棋局，证明当前完整 occurrence 校验会失配；另测“新局隐藏”仍不能避免失配。
- [x] 复用现有 SGF parser 与姓名/GN规则，由 preparation 派生元信息；支持库外来源文件并验证原 SGF、姓名/段位、日期、赛事及主线不被翻译改写，历史 importer CLI 未改动。
- [x] 保存 19x19 列表原始元信息与 SGF，明确派生字段优先级：有效 SGF 优先、缺项可用 `gamename/playTime/gameResult` 补充并留来源，冲突隔离；测试只有程序 GN、重复 GN、列表标题与 SGF EV 不同的情形。不得复刻旧 `enhance_sgf` 的字符串注入而不验证属性语义。
- [x] 仅使用无歧义身份/别名关联；精确内容复用棋局加来源，仅主线相同不足以自动合并；再次提供同来源ID异内容会拒绝覆盖并留待修订。
- [x] 定义新的自动化增量 evidence profile：文本候选和一次独立审核在库外完成；发布器在事务内确定目标 owner/棋局 ID、验证其上下文，并生成目标专属绑定。两种责任分开记录，不能把模型对文字的审核冒充对数据库绑定的审核。
- [x] 在现有native事务机制内使用同一连接完成发布：先检查前像和已有合格名称，再写入本批新增棋局/来源，绑定五语名称与研究证据，并续签受影响原文的完整范围，使用同一连接检查新旧卡片读取资格后一起提交。提交前任一步失败，事务全部回滚。
- [x] 首次实现保留现有 native batch 的全库 inventory/catalog hash 与表锁保证，显式设置有限lock_timeout，结合任务/传输预算处理竞争重试；发布前如有其他目录写入须重新绑定，不能沿用过期包或禁用快照检查。网络工作移出锁，不缩小锁范围；未声称已做局部锁重构。
- [x] 发布入口在原事务内设置 PostgreSQL `statement_timeout=15min`，是每条 SQL 的有限时限，不是整个任务时限；提交/回滚后恢复连接原设置。真实 PG 写后超时测试完成 RED→GREEN，直接相关 catalog + PG 两文件 54 项通过，独立 Astra max 对两文件审核 APPROVE。提交 `6e5021a65`；当前正在 A 回填的旧进程不热替换此代码，最终部署再采用。
- [x] raw-event 续签须复用**同一原文同一译值**的已批准文本结论，验证旧成员字段未变，将新成员作为本次确定性绑定单独记录；生成新 revision 和批次，不修改旧证据。原文/译值/身份变化转入新翻译决策。保持现有历史 reader 条件，不改成“只要 raw 字符串相同就继承”。
- [x] canonical、raw-player、raw-event、linked literal、selected GN 分别测试新成员与旧成员资格；不能用统一宽松补丁放行。
- [x] 用两个数据库夹具制造相同人物不同整数 ID，证明目标端正确重绑；目标不明、名称碰撞、审核缺失、前像漂移则整批拒绝。
- [x] 测试新 profile 的 producer/reviewer 独立性、请求 ID、可用来源或生成方法、精确 scope 与重放；运行现有 first-pass、raw-scope、provenance 相关测试，提交共享发布基础。

**关键验收：** 发布事务中不存在网络请求；提交前失败旧卡片不变；成功后受影响旧卡片五语资格零下降。提交后 API 验证失败适用 Task 4C/6 的待验证、重试与条件补偿规则，不声称数据库提交可撤回。该项未通过，后续只能库外暂存，不能回填线上目录。

## Chunk 2：稳定契约后并行实现

### Task 4A：来源抓取与恢复（Agent A）

**文件所有权：** `source_19x19.py`、`staging.py`、对应来源测试；不改共享表和目录发布器。

- [x] 用模拟响应测试：第一条已存在但后面有新谱、跨页重复、列表错误/空页区别、SGF 失败后再次发现、已有来源内容变化。
- [x] 实现固定来源地址、分页与 SGF 读取；HTTP 状态、业务 code、JSON、SGF 均校验；文件先临时写再原子改名。
- [x] 每小时从 page 0 开始前部检查；失败条目独立重试；滚动对账有独立游标、重叠页和完成时间。原全量爬虫 `progress.json` 不读不写。
- [x] 来源请求串行限速，按原配置保留 2–5 / 5–10 秒间隔。429 尊重 Retry-After；瞬态错误单请求最多三次，连续失败五次终止本轮，成功空列表才视为扫描结束。
- [x] 本轮预算到达时保存 `partial/backlog`；不能记 source caught up。页检查成功后先持久化所有发现 ID，再推进检查点，下载失败不丢 ID。
- [x] 聚焦测试通过后提交并交根 agent 集成。

### Task 4B：五语增量名称处理（Agent B）

**文件所有权：** `names.py`、对应名称服务测试；不修改旧直播翻译任务写入逻辑。

- [x] 用已有合格五语、缺一语、目标维基标题、同名歧义、搜索不可达、直接赛事翻译、生成转写和审核拒绝样本写测试。
- [x] 从 catalog 读取合格名称/别名与可续签模板；同一有限批次按 kind/key 归组并合并明确 source_items，避免逐盘重复生成。未实现额外的跨批模型结果缓存，不混用不同身份。
- [x] 实现选定服务的一种 HTTP 适配，key 从受限 secret 配置读取；显式校验五语 JSON、非空、长度、数字/轮次、引用 URL 与审核结论。
- [x] 真实读取有限维基搜索与 langlinks 作为候选证据，交独立审核核对人物和用名；搜索命中不直接证明身份。现有合格 canonical/alias 优先复用，未另外建设通用棋院爬虫。
- [x] 尚无可用目标用名时按授权直接翻译/转写，并保存 generated 方法。保留网页获取状态、链接、时间、摘要/哈希；不伪造来源。
- [x] 新生成项只做一次独立审核调用；仅有明确可修复问题才重试，最多两次生成尝试，仍失败隔离。旧合格名不重复审核。
- [x] 模型适配器并发上限3，实际编排按有限名称组处理；与串行抓源限速分开。持久UTC日预算及401/402/429/超时可区分；无key/额度时留待办，不公开半成品，不换未授权提供方。
- [x] 用户批准 Qwen Plus 后完成真实新名称单盘 TEST→PROD 小样，修正并审核五语对象提示，日账本累计6,324 token；4条早期提示失败保留隔离，未当成功样本。
- [ ] 原计划约20个名称的提供方小样未完整执行，是否补充待定；不能把当前少量调用写成20名质量/性能对照，不自动增加付费试验。

### Task 4C：正式接收器与同步（Agent C）

**实际文件：** `sync.py`、`orchestration.py` 的 receive 子命令与对应测试；调用共享 catalog，不另写 SQL 导入规则。

- [x] 测试同包重放、异哈希、跨环境主键不同、测试未验证、目标事务回滚、“正式已提交但回执丢失”和“正式已提交后 API 超时或进程退出；恢复后只继续验证”。
- [x] 通过独立受限 SSH key 调固定接收命令，JSON 包走 stdin；目标 host key 固定校验，不执行来自包的 shell/SQL，不接受任意文件路径。
- [x] 接收器只接收来源允许列表、受支持格式/大小和完整哈希的已验证包；通过固定 wrapper 复用正式Web现有DSN，测试机不保存该DSN。专用SSH账号只获固定命令权限，未新建仅按表授权的数据库角色。
- [x] 目标按来源ID/完整SGF及canonical_name指令解析本地主键，复核SGF/译名/证据后原子落库；回执含目标album_id、manifest哈希和逐项inserted/reused action，冲突直接拒绝。
- [x] 在正式 native 发布事务中持久化 applied 回执；TEST编排收到后记 `prod_published`。ACK丢失时安全重放返回原native回执，不重复写入；实际API验证后才记 `prod_synced`，API超时仅续读。若发现真实数据错误，以变更日志和后像条件补偿并记录独立回执，已有并发修改则拒绝强行撤销。
- [x] 限定专用发布账号与 SSH 文件权限；不复制用户 MacBook 通用凭据，不引入公开未鉴权导入接口。聚焦测试后提交。

**并行说明：** A/B/C 都在 Task 2/3 契约稳定后启动；root 专有 `config.py/scheduler.py/Dockerfile/迁移与集成`。按会话实际可用并发槽派发，不宣称恒有十个 agent。

## Chunk 3：编排、回填及验收

### Task 5：接入 katrain-cron 与镜像

**文件：** `jobs/kifu_ingest.py`、`config.py`、`scheduler.py`、`Dockerfile.cron`、`requirements-cron.txt`、Compose、`tests/cron/test_kifu_ingest.py`。

- [x] 新任务默认关闭；生产不启用发现/翻译，仅允许受限接收发布。测试首次部署先保持关闭，迁移/配置验证后才启用。
- [x] 添加默认关闭/LLM/UTC日token上限、3600秒间隔、staging路径、来源1800秒/总3300秒、最多100盘/20新名称和同步目标参数；页数上限为发现器默认20/100，Qwen Plus为当前实现默认模型，不虚构额外模型切换CLI。secret不入提交/普通日志。
- [x] 复用现有 RunRecorder 和暂停/立即执行；启动补查一次、max_instances=1，测试库 advisory lock 覆盖完整一轮编排但不以长数据库事务持锁；使用专用连接并在 finally 释放。
- [x] 网络和模型工作使用异步 I/O；同步解析/DB 调用有限并发移出事件循环，保证其他 cron 任务可正常调度。
- [x] 固定先恢复冻结包，再发现下载、分阶段处理、测试发布验证、正式同步；成功、部分、阻塞、失败与无新增都有真实状态。任务整体异常须上抛，由现有运行日志记录失败。
- [x] 明确初始 30 分钟是抓取预算，另设本轮总时间上限；到期持久化后退出，未完成发布包下一轮恢复，不与下一小时重入。
- [x] 持久挂载保留原始SGF、元信息、冻结包和UTC日账本；任务表保留双环境回执，实测重建cron仍在。
- [ ] 留存天数/磁盘水位清理策略待定，当前未实现自动清理，也未删除任务原始文件或历史棋谱。
- [x] 镜像离线import smoke覆盖parser/catalog/evidence/registry资源，无Kivy/FastAPI服务启动依赖；无key不发模型请求并留持久待办已有聚焦检查。未声称做过线上DB停机实验。

### Task 6：交付 A · 完成新谱整理和五语后回填测试库

**执行者：** root；仅在用户批准实施且代码审核通过后执行实际写入。

- [x] 已固定本地来源清单、两库基线与目标差异；发布事务使用native前像。`inventory`读取本地source-dir，`prepare`接收已准备games/独立审核decisions JSON生成包；传输固定包及必要文件，不全量覆盖服务器目录。
- [x] 确认 A1～A3 已完成：本批由原始 SGF 产生清洗结果及五语绑定，复用名称与新生成名称都有依据。仅发布五语合格包；缺项另列补齐。不能把新谱当成已译现成包跳过处理，也不等待 B 的服务器翻译/小时调度全部开发完成。
- [x] `run-once --manifest … --dry-run` 的无DB/无付费校验已实现并测试；包发布前校验schema/哈希。付费仅由已批准cron开关和持久预算控制，不存在额外付费CLI flag。
- [x] 首20盘canonical复用包已完成双环境发布与五语API验证；B新增名称单盘亦完成真实闭环，后续A批次出现2盘精确复用。其它边界由聚焦夹具覆盖，不声称首20盘覆盖所有场景。
- [x] 处理/翻译在库外完成；测试库发布后按实际 API 五语读取并检查受影响旧名称资格；通过才同步该批正式库。
- [x] 提交后API超时保留native applied/ops回执，A续跑只做读取验证；B编排用test_published/prod_published表达待验证。真实数据错误才条件补偿并阻止继续同步，补偿与恢复已有聚焦验证。
- [ ] 按每批最多100盘执行余量，逐批原子发布并保存两库回执；单个不合格条目隔离后重新冻结合格包，不修改已发布包内容。
- [ ] 原计划全量重放manifest尚未执行，是否追加待定。已有真实B同包重放零新增/来源不重复、原SGF核对及本地PG幂等/补偿检查可作为最低充分证据；不得写成已做全量重放。
- [ ] 报告剩余隔离/失败/待同步数量；不以“可见卡片达标”掩盖未导入项。

### Task 7：聚焦验证与 Astra 代码审核

从新工作树运行，使用现有环境；不为本任务重新安装整个前端工具链。

```bash
<python> -m pytest tests/test_kifu_incremental_*.py tests/cron/test_kifu_ingest.py tests/web_ui/test_kifu_incremental_catalog.py -q
<python> -m pytest tests/web_ui/test_import_kifu_history.py tests/web_ui/test_kifu_provenance.py tests/web_ui/test_kifu_name_first_pass.py tests/web_ui/test_kifu_raw_player_scope.py -q
git diff --check
```

- [x] 首次运行新测试确认 RED，再实现至 GREEN；不声明尚未执行的测试数量。
- [x] 数据库高风险测试增加真实 PostgreSQL 的两个并发进程、断连重试、事务回滚用例，不用 SQLite 结果替代 advisory lock 验证。
- [x] 实际双环境CN/TW/JP/KO/EN详情、元信息/段位、原SGF、来源及公开卡片通过；“吴清源”/“Go Seigen”实际搜索总数与首页ID序列一致。
- [ ] 俄语→英语回退的最终真实代表页检查尚未单独留验收记录；现有resolver规则不等于该项现场已验收。
- [ ] 原计划前后各20次性能对照尚未执行，中位数/P95不得伪报。是否追加该对照待定；建议先复用已记录的真实API读路径、单次耗时、批次验证及无现场翻译边界作最低充分核对，不新建性能平台。
- [x] 独立 Astra max 审全部变更和生产边界；逐项修复 must-fix 并复核，通过后进入发布。没有新前端视觉设计则不增加全状态截图流程。

### Task 8：集成、发布与小时任务启用

- [x] 代码已按流程合入并推送feature/develop至e694，父仓库子模块指针已更新推送；后续仅文档整理尚未提交，未覆盖无关工作区修改。
- [x] 两库003显式迁移、b894 Web兼容部署及健康/API基础验证完成；TEST cron已部署e694，GPU1路由与原任务保持，镜像/配置/重启回执已保存。
- [ ] 最终两机Web更新至已准备e694镜像尚未执行；A完成后先导出runtime cache/检查点与三类ops helper，再分别只替换Web并验证真实代表页。
- [x] 在正式机安装已审核接收入口及必要兼容代码，再回填同步；正式抓取/翻译开关保持关闭。整个过程不启动第二个增量抓取器。
- [x] 已完成两机健康、Galaxy/kiosk入口HTTP与真实棋谱API检查，未改前端布局。
- [ ] 浏览器真实视觉/在线测试盒代表页验收尚未完成，入口HTTP200不能代替视觉验收，不无故重启当前棋局。
- [ ] 首次回填追平后启用测试小时任务，观察一次有新增或注入受控来源 fixture 的执行及下一次无新增执行；fixture 不进入生产包。
- [x] 服务器cron `unless-stopped`、Docker开机启动、持久挂载与重建恢复已验证；后续使用持久标准Compose base及显式ingest override，既有运行不依赖Mac。完整hourly执行与下一次调度仍待上项启用后观察。
- [x] 暂停、持久待同步、native条件补偿与并发拒绝策略已实现并经聚焦/本地PG验证；真实暂停及恢复已执行。没有因HTTP超时撤销有效生产数据，未声称执行过生产整批补偿。

**已实现的运维接口：** `run-once` 校验或发布已经审核冻结的包，不抓取、不调用付费模型；自动发现和付费补译由 cron 的已批准开关与持久预算控制。

```bash
<python> scripts/kifu_incremental.py inventory --source-dir <absolute-sgf-dir> --after 2026-01-30 > inventory.jsonl
<python> scripts/kifu_incremental.py prepare --games <games.json> --decisions <reviewed-decisions.json> --publication-key <unique-key> --output <manifest.json>
<python> scripts/kifu_incremental.py run-once --manifest <manifest.json> --dry-run
<python> scripts/kifu_incremental.py run-once --manifest <manifest.json> --apply
<python> scripts/kifu_incremental.py status
```

`run-once --apply` 对显式配置的目标调用原子发布器，本身不自动抓取/同步，也不检查TEST回执。自动受限SSH的 `receive` 才强制校验TEST实际五语回执；A人工受控同步由root先确认同包TEST verified。receiver读取正式Web现有DSN，专用私钥只在TEST受限挂载，均不在命令行传入。

## 2. 每批汇报格式

```text
批次 UUID / 包哈希 / 时间 / 源最新日期 / 已检查页与滚动对账位置
发现 / 下载 / 解析 / 复用 / 新增 / 排除 / 隔离 / 失败 / 待翻译 / 待同步
TEST：总棋局、公开棋局、fixedwide 数/分母/%、strictcomplete 数/分母/%、公开完整卡片率
PROD：同上；本批新增/复用及两库差异
棋手 P5 数/分母/%；赛事 E5 数/分母/%；新增权威/生成名称分别计数
本批覆盖棋局/新增待处理总数；累计进度；费用/用量；最老待办年龄
```

沿用现有 `fixedwide`、`strictcomplete` 定义，不用另一套简化 SQL 另算同名指标。棋手/赛事名称数量与棋局完整卡片比例分别报告，不混用分母，不把原文标题 owner 数当赛事类型数。

## 3. 方案审核记录

1. **第一轮：ISSUES_FOUND。** 独立 GPT-6 Astra max 提出一项 must-fix：提交后的实际 API 验证失败不能称为原事务回滚，正式需保留已提交待验证状态。已补充同事务资格校验/提交回执、`prod_published`、提交后读取重试与条件补偿，以及退出恢复用例。另采纳非阻塞建议：首次实现保留 native 全库快照和表锁，设置有限超时，不先重构局部锁。
2. **第二轮：APPROVE。** 同一独立 GPT-6 Astra max 复核通过，无剩余 must-fix；确认提交前/后验证边界、正式回执原子性、恢复/条件补偿及 native 锁策略。审核当时尚未开始实施，之后用户已授权开工。

审核只针对本两份文档，不代替后续代码和数据发布审核；当前开工授权来自用户随后明确的实施指令。

**用户讨论更正（两轮审核后，2026-10-19）：** 用户已授权实施，并明确 5,536 盘新谱尚未整理、尚未翻译。此前“已整理/翻译成果回填”的前提作废；新增 A1～A4，先清洗归并、复用词典/补齐五语、审核生成包，再测试回填和正式同步。当前已有子 agent 在隔离工作树实现清单与安全发布基础；尚未向实际数据库导入或部署。本更正不启动第三轮计划审核，后续代码仍按既定流程独立审核至通过。

## 4. 历史实施记录

以下保留各时点原始进展；其中“当前”“尚未”等词仅指相应历史时点，最新口径以上方状态表为准。

### 实施进展 · 2026-10-19

- 实际固定清单为 5,536 盘，`DT` 范围 2026-01-31～2026-10-10；原始文件来自本地 `19x19/data/kifu`，没有扫描受保护的 `data/kifu-album/` 目录。另 105 份区间外新文件不混入本次数量。
- 第一遍派生元信息通过 5,526 盘；10 盘多 GN 标题互异，保留原始 SGF 并单列待处理。姓名原文保留，段位独立派生，不因清洗改变原文资格范围键。
- 历史删除的 1,752 个 19x19 来源 ID 已保存为带清理决策引用和备份哈希的版本化排除集；发现、准备、发布和接收必须遵守，不重新恢复旧问题棋局。
- 两库存在不同整数 ID 及少量目录差异。发布包使用逻辑 canonical 名称，目标端重新解析 ID，不复制测试库整数 ID。
- 新增姓名、赛事候选五语已并行生成；独立语义检查发现部分赛事通用词被拼音化，正在应用修正。候选文件数、语言字段齐全不计作已审核、已入库或完整卡片覆盖。
- 独立 Astra 首轮代码审核提出 9 项 must-fix；发布基础已修复隐藏/重复复用、身份冲突、元字段派生和条件补偿。44 项 catalog 检查及 197 项原有名称回归通过；本地隔离 PostgreSQL 的发布、重放、回滚、独立进程锁、迁移和条件补偿共 5 项检查通过。
- 独立 Astra 已给首个 20 盘包 **A_APPROVE，仅限 TEST 试发布**：包哈希 `9d6d90ce083c313ee89ab6c43fc9cec17fe45a0d1cf0aa259174deff3b14387f`，无新名称决策，均复用两库已有合格 canonical 五语。TEST 五语详情、公开列表和代表页验证通过后才同步该包至 PROD。此批准不代表 A 全量或 B 完成。
- B 的调度、接收、恢复和预算修复继续并行；小时任务和付费模型调用保持关闭。首次回填不等待 B 全部完成。当前尚无本需求的实际数据库写入或云端部署。

### 本轮代码与名称审核结果 · 2026-10-19

- B 全量代码已由独立 GPT-6 Astra max 复核通过（B_APPROVE）；已修复持久重试回执、跨日 token 账本、历史排除、单条异常隔离、SSH 镜像依赖及公开列表验证。主窗口重跑新增 B 聚焦用例 106 项全部通过。
- 名称数据独立审核通过 1,922/1,923 个赛事字段、113/121 个棋手候选及全部 21 条字形身份映射；按实际棋谱成员组包后核对有限绑定，不能把此计为已入库。
- A 发布基础已推送 feature/develop：`fccdeaf70c17455bf11434979057da3ba90c1034`；smartbox-software main 子模块指针提交 `0d26a33f`。两机兼容镜像构建中，尚未重启应用或写入新增棋谱。
- 用户已确认小时任务使用现有 Qwen Plus，每日最多 100,000 token，达到上限持久暂存并次日恢复。启用前仍执行小样及真实 TEST→PROD 验证。

### 用户要求安全暂停 · 2026-10-19

- 已关闭 TEST 新增抓取和付费翻译：持久 override `/mnt/disk1/fan/kifu-hourly-incremental-20261019/cron-kifu.override.yml` 中 ENABLED=false、LLM_ENABLED=false、MAX_TOKENS=0。正常 Analyze/ReportAnalyzer 与 GPU1 :8002、独立 1000 盘 GPU 任务保持运行。
- 两机 Web 已部署 `0cf3d8b4be6913da0e30d555193100dc2b565156`，健康、棋谱列表、Galaxy/kiosk 页面入口 HTTP200；TEST cron 当前已提交镜像 `748dc3e5109f742cd654615316e3ab901df29ca4`。功能分支已推送748；develop/父仓库指针仍为0cf（父提交e4c95771），748 develop push曾网络超时，恢复后先核对。
- 5536 原始盘中5279盘（95.36%）审核并绑定就绪（53签署包5201盘+不可变78盘），257盘隔离；不是已入库率。实际首20盘因既有两个赛事raw共用JP显示名的原子续签检查顺序问题整体回滚；新谱实际发布0盘。两库003迁移已完成。
- 付费4个样本均被隔离，发布批次0；最终专用账本4698 token。已定位并保存未提交提示示例修复：displays/methods必须是五语对象而非数组；22项名称测试通过，但尚未独立复核该最后修复并部署。
- 未提交 A 修复位于 catalog.py 和对应catalog测试：把同一个native cross-bundle检查移至完整child后像写齐、commit之前。最小复现已RED；修后47项通过，新增测试夹具错误已保存修正但尚未重跑。恢复后先重跑48项并独立Astra审查，不能直接部署未审代码。
- 两机SGF去重缓存已完成（TEST777秒、PROD992秒）并备份到各自主机任务目录 `sgf-cache.json`；重建Web后恢复至 `/tmp/kifu-backfill/sgf-cache.json`（注意运行用户写权限），避免重跑首次全库解析。TEST真实指标快照已完成：171272总盘，171013公开；fixedwide154985，strictcomplete171013，P5 3838/3865，E5 84/85。PROD指标只读任务暂停时终止，尚无新完整结果。
- 运维、签署包、完整排除表、重试脚本和补丁保存在 `/tmp/kifu-hourly-incremental-20261019`；安全暂停快照 `safe-pause-uncommitted.patch`。恢复后继续先TEST验证再PROD发布；小时任务保持关闭，直到明确恢复后样本全链路成功。

### 恢复实施 · 2026-10-19 22:16 CST

- 用户已明确继续。A共享译名续签检查顺序与B五语对象示例两处最小修复均获独立Astra APPROVE；主窗口合并重跑70项聚焦测试全部通过。
- 新小时任务仍保持关闭，待部署已审代码并通过真实单盘TEST→PROD后启用；每日10万token授权仍有效。
- TEST/PROD SSH可用、两机SGF缓存备份仍在。PROD健康端点可读但棋谱列表出现10–15秒超时，正在一次聚焦只读核对，未新增写入。

### 本次继续后的实际状态（进行中）

- 已完成原始 5,536 盘的第一遍整理和状态对账；5,279 盘（95.36%）形成独立审核签署的固定发布包，257 盘隔离。53 个名称发布包覆盖 5,201 盘，另外两个复用旧合格名称的包覆盖 20 + 58 盘。就绪数不是入库数。
- 已发布到 feature/develop 的最新代码为 `7b781fd709aebccf30b9ca44640abdac2ca3b51d`，父仓库 main `42eda710` 更新子模块至该提交。A 续签检查顺序、B 五语对象提示修复在 `b894c9d3`；7b 修复正式接收超时使用本轮剩余时间，不再错误限于 180 秒。独立 Astra 均已 APPROVE；主窗口相应聚焦检查分别为 70 项和 26 项通过。
- TEST/PROD Web 当前部署 b894，保持已运行的 1,000 盘分析、GPU 引擎和 Postgres 不变。后续 cron-only 7b 部署不重启 Web。
- A 首 20 盘 TEST 已提交（批次 726）并通过 100 个五语详情检查及公开列表核对；PROD 已提交（批次 725），首次提交后接口验证超时，当前仅恢复读取验证，不重做数据库发布。TEST 下一批 58 盘已提交（批次 730），接口验证进行中。
- B 真实千问样本来源 `91346707` 的五语已生成并通过独立模型审核，TEST album 173066 的实际五语详情及公开列表通过；专用 token 账本累计 6,324，已验证 cron 重建后仍保留。正式接收及完整 `prod_synced` 尚待验证。四个旧提示失败样本保留原始 SGF，不将其视作坏谱删除。
- 回填按环境各一个 writer 交错执行，同一个包必须 TEST verified 后才发往 PROD；SHA 与提交回执固定。断连或读取超时不自动重发未知写入，先对账恢复；所有检查仍使用原有五语资格及来源/SGF 校验。
- 双口径：TEST 全量基线为 171,272 总盘、171,013 公开，fixedwide 154,985、strictcomplete 171,013，P5 3,838/3,865，E5 84/85。首 20 盘通过后按该基线加本批原子资格检查计算为 fixedwide 155,005/171,292（90.49%）、strictcomplete 171,033/171,292（99.85%）；此处是基线加批次的推算，不冒充新全库扫描。PROD 新全量指标尚待完成。
- 实际 API 及 Galaxy/kiosk 入口 HTTP 检查已经执行；当前浏览器工具没有可用浏览器，因此没有声称完成真实视觉截图验收。新功能没有修改前端布局。

### 继续执行记录 · 2026-10-19 23:30 CST

- 测试库累计 478 盘回填通过逐盘五语详情、完整 SGF 哈希、来源和公开列表卡片核对，另有 1 盘小时任务样本。该时点总盘 171,751、公开 171,492；按全量基线加原子资格通过批次计算，strictcomplete 171,492/171,751（99.85%），fixedwide 155,464/171,751（90.52%）。后续进度由实际批次回执持续更新，不把此快照当最终总数。
- 正式首 20 盘已提交且完成同样 API 验证。B 样本正式 native 批次 727 已 applied，album 173046，外部五语 API 和列表均通过；但长时间空闲的 SSH 连接丢失回执，TEST 仍处于 test_verified/retry_wait，不冒报 prod_synced。
- 已观察到旧 SSH TCP 连接有未确认字节和重传，正式接收子进程已退出；仅终止该专用滞留客户端，保留数据库回执和冻结包。最小修复增加 ServerAliveInterval=30 / ServerAliveCountMax=6，经独立 Astra APPROVE、26 项聚焦测试通过，提交 `e694c36fb` 已推送 feature/develop，父仓库 main `7e1da45c` 更新子模块。
- TEST cron 已只重建为 e694 的已提交代码，状态、冻结包和 6,324 token 账本保留，当前只重试原包，无新抓取或模型调用；正常分析仍指向 GPU1 :8002。正式回填派发暂时等待这一包的持久回执恢复，避免两个 writer 争锁。
- 临时运维进程采用单次只读资格检查内的有界原生哈希缓存；正常和异常退出均恢复原函数。首次完整 native 校验、来源、SGF、ledger 和 collision 检查不变。另在单包提交后的 API 验证窗口复用相同列表 GET 响应，逐盘五语详情和卡片比对仍执行。这两项经独立 Astra 审查，缓存跨窗口失效/异常恢复及原有 scope/collision 共 8 项聚焦检查通过；不修改 Web 服务进程。
- 全库统计读取在 Web 内碰到实际 4 GiB 内存上限，已停止仅该只读统计进程。改为同一个 REPEATABLE READ/READ ONLY 快照内每 1,000 盘分块，原生逐槽小样结果与分块合并逐项相同；独立 Astra 审查通过。统计运行在独立 8 GiB/1 CPU/只读容器，不占用 Web 的 4 GiB 限额。正式 P5 已核实 3,663/3,689、E5 84/85，完整卡片总数尚在统计，未复用旧审计结果。
- 两库实测“吴清源”与“Go Seigen”的搜索总数均为 1,231，首页 ID 序列一致；本次回填负载下单请求耗时 TEST 7.98–11.55 秒、PROD 12.32–19.17 秒，此为单次观测，不冒称已完成原计划 20 次前后性能基准。原有合格五语实体命中时不会调用模型。
- 全量回填与正式回执恢复完成前，持续小时抓取保持关闭，避免与固定回填包抢先处理同一来源或改变受保护译值。最终启用配置已预备：24/7 每 3,600 秒、最多 100 盘/20 个新名称、Qwen Plus 每 UTC 日 100,000 token；启用后由服务器独立运行。

### 持久恢复验收 · 2026-10-19 23:40 CST

- 小时任务样本 `91346707` 已由真实编排完成 TEST→PROD；批次和条目均持久化为 `prod_synced`。TEST album 173066、PROD album 173046；两端逐语言详情、原 SGF、元信息、译名、来源和公开列表均通过共享验证器。
- 安全重放返回原正式回执，两库各有且仅有一条该来源关联，没有新增重复。随后仅重建 TEST cron，状态、同一冻结包和 6,324 token 专用账本保持。重放未调用付费模型，没有手工推进成功状态。
- TEST cron 当前为 e694 已提交镜像，容器 c728241737d0；正常 Analyze/ReportAnalyzer 继续，GPU1 :8002 不变。持续抓取仍关闭，等待历史回填完成；24/7 每小时的批准配置已在服务器保存，不依赖 Mac 启动。
- A 回填在该时点 TEST 已完成 578 盘，PROD 已完成 20 盘，正在交错执行下一包。两库写入分别只有一个调度中的 writer；PROD 样本完成后已解除历史回填等待。

### 批量执行记录 · 2026-10-20 00:20 CST

- TEST 已验证 978 盘来源记录：实际新增 976 盘、精确复用旧棋局 2 盘；总盘 172,249、公开 171,990。全量基线加本批原子资格检查得到 strictcomplete 171,990/172,249（99.85%）、fixedwide 155,962/172,249（90.54%）。复用计入来源处理数，不重复计作物理新增。
- PROD 已验证 278 盘来源记录，均为新增；另有已验收小时样本 1 盘。总盘 171,551、公开 171,292；strictcomplete 按基线加已验证批次为 171,292/171,551（99.85%），fresh fixedwide 全库统计仍进行中。后续批次继续交错执行。
- 实测提交后 HTTP 核对占用较多时间：TEST 两个 100 盘包分别为 199.40/188.35 秒；PROD 58 盘包 348.68 秒、首个 100 盘包 306.54 秒。因此仅对本次临时运维验证进程增加最多两路只读请求，仍逐盘执行原生五语详情、SGF、来源、元信息和公开卡片全部检查，异常取消并等待其他任务后原样抛出。每环境仍只有一个数据库 writer，原子发布与资格条件不变。
- 独立 Astra 实读辅助代码后 APPROVE；并发上限、保序、保留全部决策、错误取消及原生接口校验共 6 项聚焦检查通过。正式在当前包结束的空档验证原有 20 盘，100 项五语详情及相应列表检查全部通过，166.55 秒，整个 Web 容器观察内存峰值 477,343,744 字节，低于 3 GiB 边界。没有据此声明未测得的提速比例。
- 后续临时 ops 脚本 SHA `c8aa78d0ddf84a3d86cf3c48a28dce0d6009a1081a09bc08ca50d0c086dbb37b`；辅助 `ops_api_verify_pool.py` SHA `235c6c12b0086e926ca8f2f62c9bb4f30882fb6555a5c5ca12485d779f441c2c`。已装载的串行进程自然完成，仅后续新进程使用两路核对。缓存仍为原先 32 项、同一只读窗口内有效；没有扩大缓存。该运维调整不冒称已修改小时任务产品代码。
- 已核实 TEST cron `unless-stopped`、Docker 开机启动、新增状态和 SSH 挂载均持久。后续启用或 recreate 使用持久标准 Compose base `/home/fan/Repositories/katrain/docker-compose.yml` 与显式 ingest override，避免依赖 `/tmp` 的旧部署输入；具体命令保存在服务器交接记录中。

### 收敛临时并发试验 · 2026-10-20 00:36 CST

- 一次代表检查证明两路校验结果和内存边界正确，但没有建立加速证据。实际本地云端路径 `list_kifu_albums/get_kifu_album` 是 async 路由中直接同步查库和计算资格，单 Web worker 下该工作没有因客户端增加请求而并行；共享列表缓存还可能在同查询首次并发 miss 时额外发一次请求。
- 已将两机未来临时 ops 进程恢复至原已审核脚本 SHA `8cfbc8cef8d50eb2325f37118cce1529b443d3a3a1b8e5902d6f351416c8ea70`。已装载的两路进程自然完成，结果仍须全部校验；原生资格、数据库单 writer、只读窗口内 LRU32 和重试规则不变。本轮不扩展生产 API 性能重构，不宣称已提速。
- 该时点 TEST 验证 1,178 盘来源记录（1,176 新增、2 复用），PROD 验证 378 盘（全部新增），继续原有流水线。PROD 总盘 171,651、公开 171,392；基线加批次的 strictcomplete 为 171,392/171,651（99.85%），fresh fixedwide 统计仍在运行。

### develop 合并及 SQL 时限 · 2026-10-20 01:20 CST

- 已拉取并合并 develop `e36c9f7e1` 的92个后续提交，合并提交 `5ae9fa24a`；这些提交主要为教程/admin工作，没有改动本功能的 ingest、cron或kifu资格代码，合并无冲突。最终镜像需要从整合后的源码构建，不能仅覆盖旧镜像的三个文件就标成新整合版本。
- 发布事务的每条SQL增加15分钟有限时限，提交 `6e5021a65`，独立Astra max审核APPROVE；真实PG用例证明写入后超时整批回滚，连接原5秒设置恢复。合并后主窗口实际运行 catalog、真实PG、cron三文件，共 **80 passed in 23.54s**，没有跳过PG。
- 同时点A回填已核对 TEST1,578条来源（1,576新增、2复用）、PROD678条来源（均新增）。两端仍各一个writer，下一批在运行；没有把合并或新镜像构建应用到这些在途进程。

### A 后续验收收敛 · 2026-10-20

- 已发布整合提交 `841b87622` 到当前分支和develop；父仓库main `a8708837`更新子模块。两端完整整合镜像构建中，尚不重建正在回填的Web。
- 累计实际逐盘五语HTTP核对已覆盖TEST1,678、PROD778条来源。独立Astra max根据这些实测及用户比例原则批准后续A批次改为“全量原生事务检查＋提交后全量只读DB对账＋代表HTTP样本”；持续B产品代码仍逐盘完整HTTP验证，不受此临时运维调整影响。
- 每个后续包在同一REPEATABLE READ/READ ONLY快照核对完整manifest SHA、applied原回执、全部来源成员/原始及规范SGF哈希/链接、原PB/PW/EV、公开状态和全部五语原生资格。HTTP样本固定首/中/末，并按实际DB绑定补齐insert/reuse、canonical/raw player及canonical/raw event类型，沿用完整decisions、同一原回执及原验证器。
- 实际ops SHA `43d378f60c35c44c7cc8a764510061fb915ab4cb614f08e6bfbae534a6a3b13f`、新helper `ops_batch_verification.py` SHA `2a1a247315472c3d0091de23aeaad590464fbc42212456e3ca2c56a464abc116`；独立Astra实读后APPROVE。两项新聚焦测试加原生verifier三项共5项通过（0.48s），覆盖抽样类型补齐、原回执/原始字段损坏拒绝。
- 仅未来进程原子换脚本，现役进程自然完成；PROD首个新规则包为batch008，TEST从替换后的下一包开始。任一全量对账或样本失败都不发verified，队列停止。结果记录`database`全量数量、`api_scope=sampled`、实际`api.games/checks`、规则及样本source/album ID；顶层games是整体通过的包成员数，不等于HTTP样本数。最终汇总从保存的详细verification读取，不能伪称每盘HTTP全通过。
- 全部A结束后，两库各对首/中/末批次各两条并补齐缺少绑定类型，再做一次五语HTTP核对。未抽中条目的个别HTTP显示/搜索差异是这一比例方案接受的剩余风险；不据此宣称性能提升百分比。
- 最终Web替换前除原cache/receipt及coverage helper外，还需导出新的`ops_batch_verification.py`；任何临时helper均不烘入产品镜像。

### 冻结原文隔离修复与运维工具审核 · 2026-10-20

- catalog 的 `no_native_generated_scope_refresh` 表示旧证据不能自动扩展到新棋局。此前 prepare 未消费这一状态，会浪费模型请求并让整包在发布时失败。现只针对这一状态，在付费请求前隔离相关棋局，并从所有 pending 名称成员中移除它们。新名称缺五语及原文语言不一致仍按原流程处理，不复制旧签名到新范围。
- 独立 GPT-6 Astra max 实读生产 diff 和新增测试后 **APPROVE**；主窗口实际复跑 preparation/CLI/cron 聚焦检查 **55 passed in 0.67s**。尚未部署该修复。
- A 的257盘隔离报告见 [清单说明](reports/first-pass-isolations-20261020.md) 和 [完整JSON](reports/first-pass-isolations-20261020.json)。JSON SHA256 `42f335c6a65b1ca8e87defe359a8a32927b3358033158eb3a39e127273e4bc88`；保留逐项理由、原始哈希和5,536=5,279+257对账。
- [隔离登记工具](operations/record_a_isolations.py) 只通过 StateStore 登记已发现/已隔离状态，绝不添加 Stage 或下载/发布成功字段。独立 Astra 对实际代码 **APPROVE**；真实 StateStore/Stage 两项检查 **2 passed in 0.68s**，包含零下载跳过、中断恢复及冲突前置拒绝。须待 A 两库完成、B关闭且cap0，持有既有session lock后执行。目前仅准备，未执行。
- [四条提示失败恢复工具](operations/recover_prompt_quarantines.py) 仅把有效原始SGF恢复为 downloaded，留待正常任务重做名称审核，不手动推进发布成功；与257盘集合不相交。同样须在 B 启用前执行，目前未执行。

### A 第38包有限数据修正 · 2026-10-20

- 第38签署包在 TEST 的提交前原生冲突检查失败；两云只读核对均无该manifest回执，目标原文也无既有译名，原事务整体回滚。其他已验证批次保留，原队列中的正式第26包自然完成后才恢复派发。
- 原文“第31届韩国GS加德士杯胜者组4强战”的日/韩/英译文使用了“半决赛”词义，其中韩/英与另一原文译名重合且缺少数字4，触发原生 literal shared-display 数字保留要求。只把三处改为 `第31回 韓国GSカルテックス杯勝者組 4強戦`、`제31회 한국 GS칼텍스배 승자조 4강전`、`31st Korean GS Caltex Cup Winners’ Bracket Round of 4`，不放宽原生规则。
- 独立 Astra 对实际修正包重新审核并签署，见 [有限审核记录](reports/batch038c-correction-review-20261020.json)。100盘、原始SGF/哈希、其他59项决策和目标source_items保持不变。新包 `batch038c.json` 的canonical SHA为 `1efdcc0be252ca8f1dc3bd8344d6f16330ff71fc7393ea04bc577c3c4456900e`；原038包、原索引、原审批和257盘隔离报告保持历史原件，实际执行使用另存的修正索引。
- 离线使用实际原生碰撞谓词扫描55包、5279盘、2207项决策和11035个语言项，没有发现其他同类包内或跨包数字丢失碰撞。这不冒充全库语义重审或云端发布验证。
- 恢复前 TEST 已验证3778盘，PROD已验证2678盘。原失败状态归档后仅标记为rolled_back并指向新包，没有伪造verified或手动推进业务成功阶段。TEST修正包通过后，正式库才接收同一新SHA。

### A 第46/47包生成方式修正 · 2026-10-20

- 第46包在 TEST 的提交前校验失败：原文“菲特拉·R·S”的日文显示“フィトラ・R・S”标记为 retain_original，与实际音译不符；两云只读核对无该包回执及既有目标译名。剩余包的纯数据检查还定位第47包“菲特拉”→“フィトラ”的同类标记错误，第47原包没有尝试发布。
- 只把两条日文方法改为 transliteration，全部显示文字、身份、200盘SGF及其余68项决策不变。实际独立 Astra 重新签署 [审核记录](reports/batch046047-method-review-20261020.json)，两包原生 manifest 校验通过。新 canonical SHA：046c `c8d73169f2f89966035f0d6630d0118bb103103dc6a0c79a751711b9d6a4b4b8`，047c `39700b99c3d59d2c8c5f4772a050fd62d038a7c114e41f2c0d273977915fa10a`。
- 对55原包和038c的2267项决策、11335个方法项使用实际 validate_research 做离线方法检查，只发现这两项；修正后通过。检查中的其他结构字段使用占位前提，故此结论仅限生成方法，不冒充完整数据库资格或语义重审。
- 原冻结文件、v1修正索引及257盘隔离报告不改写；另存v2索引，只将046/047换成新审核包并保留038c。固定5279来源及原raw/SGF哈希全集不变。最终HTTP抽样额外包含三条修正来源作为回归样本。

### 自动补译入口的生成方式检查 · 2026-10-20

- 只对没有合格复用模板的新 raw_player 增加最小前置检查：标为 retain_original 的显示必须与原生 parse_player(key, None).name一致。发现错误时不调用付费reviewer，进入既有一次producer修复；仍失败则隔离，不冻结无效包。
- 已有合格原文模板保留其既有 original_name/generation依据，不由此检查覆盖；canonical player处理不变，原生发布校验仍是最终权威，预算和账本逻辑不变。
- 独立 GPT-6 Astra max 实读代码 **APPROVE**。主窗口实际运行名称、CLI、preparation和cron四文件 **82 passed in 0.77s**；新增场景覆盖两条Fitra样例、重复失败零reviewer、附带九段的合法保留及旧模板兼容。无真实模型付费请求。
