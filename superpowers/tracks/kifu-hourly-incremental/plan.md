# 棋谱库小时增量与五语言发布 Implementation Plan

> **For agentic workers:** REQUIRED: Use `superpowers:subagent-driven-development` after the user approves this plan. Parallelize only tasks with disjoint files and stable contracts. Steps use checkbox (`- [ ]`) syntax. Root coordinates database writes, release and deployment.

**Goal:** 先对 MacBook 已抓取但尚未整理、翻译的 5,536 盘新谱（2026-01-31～2026-10-10）完成解析清洗、去重归并和五语缺口补齐，再回填测试库并验证同步正式；随后交付每小时持续抓取、处理和同步流程。

**Architecture:** 一个 `katrain-cron` 增量任务、一个库外暂存区、现有 catalog/证据/批次基础及受限正式接收入口。查询翻译在事务外完成，棋局、名称及受影响范围在目标环境短事务中一起发布；测试验证后转发同一不可变逻辑包。

**Tech Stack:** 现有 Python 3.11、HTTPX、SQLAlchemy、PostgreSQL、APScheduler、SGF parser、catalog 五语解析器、Docker；首选千问 API，提供方/模型待用户讨论确认。

**PRD:** [prd.md](./prd.md)
**日期/状态：** 2026-10-19，用户已授权开始实施；只读核对和隔离开发已启动，数据导入/部署尚未执行。新增谱未整理、未翻译的事实以本次用户更正为准。用户指定本目录覆盖 writing-plans 默认存放位置。

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

- [ ] **A1 · 整理：** 固定 5,536 盘来源清单与原始哈希；解析 SGF，拆分姓名/当时段位，处理 EV/GN 选择和格式异常；按无歧义证据关联/归并棋手、赛事类型和届次，轮次单独保存。输出解析成功、修正、重复、冲突和待处理数量。
- [ ] **A2 · 五语：** 对清洗后的独立棋手及赛事核心/原文标题建立缺口清单，先复用旧库合格 `cn/tw/jp/ko/en` 词典与已有模板；并行处理缺口，保存维基/棋院链接或如实标记直接翻译、转写方法。旧库翻译成果不能作为这 5,536 盘已翻译的凭证。
- [ ] **A3 · 审核与生成包：** 新名称一次独立审核并检查身份、五语完整性、数字/年份/轮次；按各棋局绑定名称和证据生成固定发布包。校验全部条目都有可解释状态；未完整条目不公开，不伪报整批完成。
- [ ] **A4 · 入库：** 完成上述步骤及必要代码审核后执行 Task 6；先测试库、验证后正式库，每批记录双口径覆盖率和剩余待办。原始清单不因回填进展而动态更换。

- [x] 用户已明确授权开始实施，并更正确认 5,536 盘未整理、未翻译。A 由当前会话先整理和补齐名称；B 的模型提供方、预算与自动同步策略单独确定，未经确认不擅自购买或切换付费服务。
- [x] 独立 GPT-6 Astra、`max` effort 已完成两轮 PRD/计划审核，修改后通过；结论见本文末尾。本次事实更正不追加第三轮计划审核。
- [x] 已按 `using-git-worktrees` 创建 `.worktrees/kifu-hourly-incremental`，保留原工作区分析任务相关未提交文件。根 agent 处理共享 Git；子 agent 不同时改同一文件。
- [ ] 用 `subagent-driven-development` 分派独立任务；先稳定共享契约和原子发布，再并行抓取、翻译、接收器三个边界。
- [ ] 完成后用 `requesting-code-review`，派独立 Astra max 审核生产写入、证据资格、重试及完整 diff；修复 must-fix 后复核至通过。普通文案和配置只做聚焦检查。
- [ ] 不停止或重选正在运行的 1,000 盘分析，不修改其 SGF/棋局 ID；正常 cron 分析继续固定 GPU1，增量任务不调用 KataGo。

## 1. 文件与责任边界

路径为拟实施清单，不表示已经创建。现有模块只提取必要入口，不做全库重构。

| 操作/路径 | 责任 |
| --- | --- |
| 新建 `katrain/kifu_ingest/__init__.py`、`contract.py` | 来源条目、五语候选及不可变发布包的数据契约、哈希 |
| 新建 `katrain/kifu_ingest/source_19x19.py` | 限速、列表/SGF 获取、有限重试，不导入旧爬虫全局日志与进度 |
| 新建 `katrain/kifu_ingest/staging.py` | 原始文件原子保存、manifest、发现/补偿游标、恢复 |
| 新建 `katrain/kifu_ingest/names.py` | 五语缺口计算、检索/翻译/审核适配；首次只实现选定提供方 |
| 新建 `katrain/kifu_ingest/catalog.py` | 目标库身份解析、现有解析/去重逻辑适配、原子发布及范围续签协调 |
| 新建 `katrain/kifu_ingest/sync.py`、`receiver.py` | 测试验证后的逻辑包传输、目标端幂等接收/回执 |
| 新建 `katrain/cron/jobs/kifu_ingest.py` | 阶段编排、预算、advisory lock、运行状态 |
| 新建 `scripts/kifu_incremental.py` | `inventory/prepare/run-once/receive/status` 运维入口 |
| 新建 `katrain/cron/migrations/003_kifu_incremental.sql` | 两张任务表及唯一约束；如编号冲突取当前下一个号 |
| 按需修改 `katrain/web/core/models_db.py`、`katrain/cron/models.py` | 同一任务表字段；不复制完整 catalog 规则到 cron |
| 修改 `scripts/import_kifu.py` | 提取可复用的单条解析/元信息入口，历史 CLI 行为保留 |
| 按需修改 `katrain/web/kifu/name_batch.py`、`name_first_pass.py`、`identity.py` | 增量自动化证据契约与当前事务接入；不绕过现有资格读取 |
| 修改 `katrain/cron/config.py`、`scheduler.py` | 默认关闭的新 job、参数与注册，现有任务不变 |
| 修改 `Dockerfile.cron`、`requirements-cron.txt`、现有 Compose 文件 | 共享包及必要 SGF/catalog 依赖、持久卷和受限凭据 |
| 新建 `tests/test_kifu_incremental.py`、`tests/cron/test_kifu_ingest.py`、`tests/web_ui/test_kifu_incremental_catalog.py` | 来源、恢复、发布及五语历史回归 |
| 更新本目录 `prd.md`、`plan.md` | 决策、进展、部署版本、计数及验收结果 |

**镜像边界：** 当前 cron 镜像仅复制 `katrain/cron`，不能假定其中存在 SGF parser 或 web catalog。先做最小导入验证，再显式复制本功能使用的共享包、`katrain/core/sgf_parser.py`、catalog 模块及所需 schema/config/数据资源；只补实际依赖。不启动 FastAPI/Kivy，也不通过 Docker socket 操纵其他服务。若现有 catalog 导入要求 web 启动配置，则提取最小共享基础，禁止用伪造配置绕过启动校验。

## Chunk 1：实况清单与共享发布基础

### Task 1：核对本地数据、两库和来源分页

**文件：** 运维入口的 `inventory` 模式、本目录现状记录；不写业务数据。

- [ ] 用只读事务提取两库 schema、公开/隐藏/重复数量、日期范围、来源路径与来源关联、现有名称资格、删除记录清单/回执。历史报告仅作参考。
- [ ] 在 Python 内扫描本地 `19x19/data/kifu`，输出总数、实际 SGF `DT` 范围、解析失败数、来源 ID 差集；避免输出完整文件列表。不得列举或读取受技能保护的 `data/kifu-album/` 目录。
- [ ] 确认这批新增谱尚未整理/翻译；从原始 SGF 与旧库合格词典建立“解析待办 / 名称可复用 / 五语实际缺口 / 区间外 / 日期待确认”清单，进入 A1～A3。仅复用可核对的既有名称，不重复等待不存在的新增谱译名文件。
- [ ] B 阶段再从来源第 0 页及若干间隔页取有限样本，保留 5–10 秒翻页间隔，比较排序字段、页间重叠和新增语义；不能把观察到的排序冒充服务保证，也不以这项试验阻塞 A。
- [ ] 将历史删除、隐藏、合并来源加入排除/匹配清单；将可确认的已删来源 ID 持久化为带历史决策依据的排除项，后续滚动扫描也须遵守，不能只在首次回填内排除。核对待导入不是“155,947 份全部重新入库”。
- [ ] 记录初始实际新增量、最新日期、五语缺口及两库身份映射差异，确定前部扫描与滚动对账预算。

**验收：** `inventory --read-only` 不执行 DDL/DML；输出 JSON 清单，可据其准确说明需补多少盘。若缺删除决策依据，相关 ID 保持隔离，不先恢复。

### Task 2：固定包契约和最小持久状态

**文件：** `contract.py`、任务表迁移/模型、`tests/test_kifu_incremental.py`。

- [ ] 先写重复来源 ID、重复批次、同 UUID 异哈希、非法阶段跳转的失败测试。
- [ ] 实现 `kifu_ingest_batches` 和 `kifu_ingest_items`；迁移只建本任务表/约束，不调用全库 `Base.metadata.create_all()`。
- [ ] 定义逻辑包：`format_version/batch_uuid/payload_sha256/source_items/albums/name_decisions/evidence`；成员用逻辑 ref，不跨库复制整数 ID。
- [ ] 区分来源键、原始字节哈希、规范 SGF 哈希、物理本地主键。数据包哈希覆盖全部业务与名称内容，传输凭据不入包。
- [ ] 定义逐项状态 `discovered → downloaded → parsed → names_ready → test_published → test_verified → prod_published → prod_synced`，以及带失败阶段的 `retry_wait/quarantined`。published 仅证明提交，verified/synced 才包括实际 API 验证；幂等重放和部分通过有明确回执。
- [ ] 把原始/规范文件引用、attempt、next_retry_at、错误码和两库回执持久化；分页发现检查点与条目成功状态分开。
- [ ] 跑聚焦测试并提交该独立基础。

**契约示意：**

```json
{
  "format_version": 1,
  "batch_uuid": "<UUID>",
  "payload_sha256": "<canonical-json-sha256>",
  "source_items": [{"ref": "s1", "source_key": "19x19", "external_id": "<source-id>"}],
  "albums": [{"ref": "g1", "source_refs": ["s1"], "sgf_sha256": "<sha256>"}],
  "name_decisions": [{"owner_ref": "p1", "names": {"cn": "…", "tw": "…", "jp": "…", "ko": "…", "en": "…"}}],
  "evidence": [{"owner_ref": "p1", "method": "generated_first_pass", "producer_request_id": "…", "reviewer_request_id": "…"}]
}
```

这只是字段关系示意；实现中的 schema 必须拒绝缺失棋局载荷、悬空 owner ref、无依据的身份关联及不完整五语，不能把示意包当可发布实例。

### Task 3：解析复用、身份匹配与原子范围续签

**文件：** `catalog.py`、`scripts/import_kifu.py`、必要的 `name_batch.py/name_first_pass.py/identity.py`、`tests/web_ui/test_kifu_incremental_catalog.py`。

- [ ] 先构造已合格 raw-event 的旧棋局，再加入同原文新棋局，证明当前完整 occurrence 校验会失配；另测“新局隐藏”仍不能避免失配。
- [ ] 提取现有 SGF 解析入口，支持明确来源路径与库外文件；验证编码、PB/PW 与 BR/WR、日期、EV/GN 及主线不被翻译改写。
- [ ] 保存 19x19 列表原始元信息与 SGF，明确派生字段优先级：有效 SGF 优先、缺项可用 `gamename/playTime/gameResult` 补充并留来源，冲突隔离；测试只有程序 GN、重复 GN、列表标题与 SGF EV 不同的情形。不得复刻旧 `enhance_sgf` 的字符串注入而不验证属性语义。
- [ ] 仅使用无歧义身份/别名关联；精确内容复用棋局加来源，主线匹配仅提示。已有来源 ID 内容变化隔离为修订。
- [ ] 定义新的自动化增量 evidence profile：文本候选和一次独立审核在库外完成；发布器在事务内确定目标 owner/棋局 ID、验证其上下文，并生成目标专属绑定。两种责任分开记录，不能把模型对文字的审核冒充对数据库绑定的审核。
- [ ] 在现有 native batch 事务基础上提供连接级发布入口：先检查前像和已有合格名称，再写入本批新增棋局/来源，绑定五语名称与研究证据，并续签受影响原文的完整范围，使用同一连接检查新旧卡片读取资格后一起提交。提交前任一步失败，事务全部回滚。
- [ ] 首次实现保留现有 native batch 的全库 inventory/catalog hash 与表锁保证，设置有限 lock_timeout/statement_timeout，竞争超时留待重试；发布前如有其他目录写入须重新绑定，不能沿用过期包或禁用快照检查。只把网络工作移出锁，不默认缩小锁范围；实测锁阻塞成为瓶颈时才另行讨论版本化局部前像契约，并以并发冲突测试证明不会漏掉关联变更。
- [ ] raw-event 续签须复用**同一原文同一译值**的已批准文本结论，验证旧成员字段未变，将新成员作为本次确定性绑定单独记录；生成新 revision 和批次，不修改旧证据。原文/译值/身份变化转入新翻译决策。保持现有历史 reader 条件，不改成“只要 raw 字符串相同就继承”。
- [ ] canonical、raw-player、raw-event、linked literal、selected GN 分别测试新成员与旧成员资格；不能用统一宽松补丁放行。
- [ ] 用两个数据库夹具制造相同人物不同整数 ID，证明目标端正确重绑；目标不明、名称碰撞、审核缺失、前像漂移则整批拒绝。
- [ ] 测试新 profile 的 producer/reviewer 独立性、请求 ID、可用来源或生成方法、精确 scope 与重放；运行现有 first-pass、raw-scope、provenance 相关测试，提交共享发布基础。

**关键验收：** 发布事务中不存在网络请求；提交前失败旧卡片不变；成功后受影响旧卡片五语资格零下降。提交后 API 验证失败适用 Task 4C/6 的待验证、重试与条件补偿规则，不声称数据库提交可撤回。该项未通过，后续只能库外暂存，不能回填线上目录。

## Chunk 2：稳定契约后并行实现

### Task 4A：来源抓取与恢复（Agent A）

**文件所有权：** `source_19x19.py`、`staging.py`、对应来源测试；不改共享表和目录发布器。

- [ ] 用模拟响应测试：第一条已存在但后面有新谱、跨页重复、列表错误/空页区别、SGF 失败后再次发现、已有来源内容变化。
- [ ] 实现固定来源地址、分页与 SGF 读取；HTTP 状态、业务 code、JSON、SGF 均校验；文件先临时写再原子改名。
- [ ] 每小时从 page 0 开始前部检查；失败条目独立重试；滚动对账有独立游标、重叠页和完成时间。原全量爬虫 `progress.json` 不读不写。
- [ ] 来源请求串行限速，按原配置保留 2–5 / 5–10 秒间隔。429 尊重 Retry-After；瞬态错误单请求最多三次，连续失败五次终止本轮，成功空列表才视为扫描结束。
- [ ] 本轮预算到达时保存 `partial/backlog`；不能记 source caught up。页检查成功后先持久化所有发现 ID，再推进检查点，下载失败不丢 ID。
- [ ] 聚焦测试通过后提交并交根 agent 集成。

### Task 4B：五语增量名称处理（Agent B）

**文件所有权：** `names.py`、对应名称服务测试；不修改旧直播翻译任务写入逻辑。

- [ ] 用已有合格五语、缺一语、目标维基标题、同名歧义、搜索不可达、直接赛事翻译、生成转写和审核拒绝样本写测试。
- [ ] 从 catalog 读取合格名称/别名；缓存键包含 owner/原文、目标语言、规则版本与资料版本，避免同批并发重复调用；原文相同但身份不同不能共用人物结果。
- [ ] 实现选定服务的一种 HTTP 适配，key 从受限 secret 配置读取；显式校验五语 JSON、非空、长度、数字/轮次、引用 URL 与审核结论。
- [ ] 优先目标语言维基页标题及棋院资料；按关联实体核对人物，不能仅因标题含姓名就认定同一人。
- [ ] 尚无可用目标用名时按授权直接翻译/转写，并保存 generated 方法。保留网页获取状态、链接、时间、摘要/哈希；不伪造来源。
- [ ] 新生成项只做一次独立审核调用；仅有明确可修复问题才重试，最多两次生成尝试，仍失败隔离。旧合格名不重复审核。
- [ ] 初始模型并发 3，与来源抓取限速独立；预算/令牌上限、401/402/429/超时可区分。没有 key 或额度不足时可发现/暂存，不公开半成品，不回退未授权的付费提供方。
- [ ] 用户批准付费提供方后跑约 20 个名称小样本，记录五语正确性、出处、延迟、token/搜索次数与实付估计，固定模型/提示词版本；提交。

### Task 4C：正式接收器与同步（Agent C）

**文件所有权：** `sync.py`、`receiver.py`、对应接收测试；调用共享 catalog 接口，不另写 SQL 导入规则。

- [ ] 测试同包重放、异哈希、跨环境主键不同、测试未验证、目标事务回滚、“正式已提交但回执丢失”和“正式已提交后 API 超时或进程退出；恢复后只继续验证”。
- [ ] 通过独立受限 SSH key 调固定接收命令，JSON 包走 stdin；目标 host key 固定校验，不执行来自包的 shell/SQL，不接受任意文件路径。
- [ ] 接收器只接收来源允许列表、受支持格式/大小和完整哈希的已验证包；使用必要表权限，读取自身正式 DSN，测试机不保存正式超级用户 DSN。
- [ ] 目标按当前库重建逻辑 ref → 本地主键，复核源 SGF/译名/证据后通过原子发布器落库；回执含本地主键映射、包哈希及实际新增/复用/冲突计数。
- [ ] 在正式发布事务中同时持久化目标批次 `prod_published` 回执；ACK 丢失时查询相同批次结果，不重复写入。提交后另做实际 API 验证，通过才记 `prod_synced`；超时只重试验证。若发现真实数据错误，以变更日志和后像条件补偿并记录独立回执，已有并发修改则拒绝强行撤销。
- [ ] 限定专用发布账号与 SSH 文件权限；不复制用户 MacBook 通用凭据，不引入公开未鉴权导入接口。聚焦测试后提交。

**并行说明：** A/B/C 都在 Task 2/3 契约稳定后启动；root 专有 `config.py/scheduler.py/Dockerfile/迁移与集成`。按会话实际可用并发槽派发，不宣称恒有十个 agent。

## Chunk 3：编排、回填及验收

### Task 5：接入 katrain-cron 与镜像

**文件：** `jobs/kifu_ingest.py`、`config.py`、`scheduler.py`、`Dockerfile.cron`、`requirements-cron.txt`、Compose、`tests/cron/test_kifu_ingest.py`。

- [ ] 新任务默认关闭；生产不启用发现/翻译，仅允许受限接收发布。测试首次部署先保持关闭，迁移/配置验证后才启用。
- [ ] 添加 `CRON_KIFU_INGEST_ENABLED`、`CRON_KIFU_INGEST_INTERVAL=3600`、staging 路径、来源页/时长预算、名称预算、提供方/模型和同步目标参数；secret 不写入提交或普通日志。
- [ ] 复用现有 RunRecorder 和暂停/立即执行；启动补查一次、max_instances=1，测试库 advisory lock 覆盖完整一轮编排但不以长数据库事务持锁；使用专用连接并在 finally 释放。
- [ ] 网络和模型工作使用异步 I/O；同步解析/DB 调用有限并发移出事件循环，保证其他 cron 任务可正常调度。
- [ ] 固定先发现/恢复、分阶段处理、测试发布验证、正式同步；成功、部分、阻塞、失败与无新增都有真实状态。任务整体异常须上抛，由现有运行日志记录失败。
- [ ] 明确初始 30 分钟是抓取预算，另设本轮总时间上限；到期持久化后退出，未完成发布包下一轮恢复，不与下一小时重入。
- [ ] 持久卷保留原始文件、逻辑包及回执；设置可讨论的留存天数和磁盘水位，仅清理已有双环境成功回执且超过留存期的任务文件，不删历史棋谱源文件。
- [ ] 镜像 import smoke 覆盖 parser/catalog/evidence/registry 资源，确认无 Kivy/FastAPI 服务启动依赖；数据库不可用、key 缺失均不拖死现有服务启动。

### Task 6：交付 A · 完成新谱整理和五语后回填测试库

**执行者：** root；仅在用户批准实施且代码审核通过后执行实际写入。

- [ ] `inventory` 保存两库最新前像与计数；`prepare` 接受明确本地来源目录/manifest，传输缺失文件及哈希，不全量覆盖服务器目录。
- [ ] 确认 A1～A3 已完成：本批由原始 SGF 产生清洗结果及五语绑定，复用名称与新生成名称都有依据。仅发布五语合格包；缺项另列补齐。不能把新谱当成已译现成包跳过处理，也不等待 B 的服务器翻译/小时调度全部开发完成。
- [ ] 先 `--dry-run`，禁止 DDL、业务 DML 或付费请求；付费名称试验单独使用明确 `--allow-paid`，不藏在 dry-run 内。
- [ ] 先选约 20 盘代表性新增棋做完整链路：已有棋手、新赛事、段位后缀、旧日期补录、精确重复；记录隔离原因。
- [ ] 处理/翻译在库外完成；测试库发布后按实际 API 五语读取并检查受影响旧名称资格；通过才同步该批正式库。
- [ ] 测试提交后 API 超时保留 `test_published`，恢复后只做验证；真实数据错误才进行条件补偿并阻止该批正式同步。补偿与重复恢复同样纳入聚焦验证。
- [ ] 按每批最多 100 盘执行余量，短事务并逐批保存两库回执；单个不合格条目隔离后重新冻结合格包，不修改已发布包内容。
- [ ] 全量重跑回填 manifest，期望新增 0、来源关联不重复、旧 SGF 哈希与分析绑定不变。
- [ ] 报告剩余隔离/失败/待同步数量；不以“可见卡片达标”掩盖未导入项。

### Task 7：聚焦验证与 Astra 代码审核

从新工作树运行，使用现有环境；不为本任务重新安装整个前端工具链。

```bash
<python> -m pytest tests/test_kifu_incremental.py tests/cron/test_kifu_ingest.py tests/web_ui/test_kifu_incremental_catalog.py -q
<python> -m pytest tests/web_ui/test_import_kifu_history.py tests/web_ui/test_kifu_provenance.py tests/web_ui/test_kifu_name_first_pass.py tests/web_ui/test_kifu_raw_player_scope.py -q
git diff --check
```

- [ ] 首次运行新测试确认 RED，再实现至 GREEN；不声明尚未执行的测试数量。
- [ ] 数据库高风险测试增加真实 PostgreSQL 的两个并发进程、断连重试、事务回滚用例，不用 SQLite 结果替代 advisory lock 验证。
- [ ] 真实样本验证 CN/TW/JP/KO/EN 及俄语→英语回退，中文/英文搜索集合一致；校验新旧卡片和段位。
- [ ] 在同条件比较部署前后代表 API 各 20 次耗时，记录中位数/P95，确认切语言无外部翻译请求。
- [ ] 独立 Astra max 审全部变更和生产边界；逐项修复 must-fix 并复核，通过后进入发布。没有新前端视觉设计则不增加全状态截图流程。

### Task 8：集成、发布与小时任务启用

- [ ] 按仓库发布流程：feature 追上 `develop`、解决冲突、验证、commit/push；合入并 push `develop`；更新 `smartbox-software/vendor/katrain` 指针并提交推送，保留无关修改。
- [ ] 先部署测试、验证迁移和服务健康；只重建本次变更涉及的服务。记录镜像 SHA、源码提交及实际启用配置，避免覆盖现有 GPU 路由与业务开关。
- [ ] 在正式机安装已审核接收入口及必要兼容代码，再回填同步；正式抓取/翻译开关保持关闭。整个过程不启动第二个增量抓取器。
- [ ] 实际打开 TEST/PROD Galaxy 棋谱列表、详情和 kiosk 代表页；测试盒端如在线，只验证同一 API 的数据展示，不无故重启当前棋局。
- [ ] 首次回填追平后启用测试小时任务，观察一次有新增或注入受控来源 fixture 的执行及下一次无新增执行；fixture 不进入生产包。
- [ ] 用服务器进程/容器管理保证断开 SSH 后继续运行；通过持久状态验证重启可续跑，不需要关闭用户 MacBook 做测试。
- [ ] 故障回滚先关闭新任务，再按批次前像及并发检查撤销本次数据/部署；保留测试成功但未同步的队列，不整库替换。

**拟提供的运维接口（实施后才存在）：**

```bash
<python> scripts/kifu_incremental.py inventory --source-dir <absolute-sgf-dir> --read-only --output <manifest.json>
<python> scripts/kifu_incremental.py prepare --manifest <manifest.json> --staging-dir <absolute-staging-dir>
<python> scripts/kifu_incremental.py run-once --manifest <manifest.json> --dry-run
<python> scripts/kifu_incremental.py run-once --manifest <manifest.json> --apply --allow-paid
<python> scripts/kifu_incremental.py status --json
```

`--apply` 不覆盖用户讨论中的正式自动同步选择；发布器仍要求测试验证回执。正式 receiver 的 DSN 和 SSH 密钥由受限运行配置提供，不在命令行传入。

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

## 4. 实施进展 · 2026-10-19

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
