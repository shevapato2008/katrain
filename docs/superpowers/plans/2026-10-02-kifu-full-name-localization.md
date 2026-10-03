# 棋谱棋手与赛事十一语言全量本地化 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让正式库每盘可见棋谱的黑白棋手及赛事，在 `en cn tw jp ko de es fr ru tr ua` 下都有经过来源查证的正确显示决策、可追溯译名和跨语言检索；全库十一语言覆盖率达到 100% 才交付。

**Architecture:** 保留 SGF 原文；把身份、原始写法、结构化赛事组成部分、译名、来源证据和批次日志分开。先完成只读清单与分类，再逐实体/原始写法核名和审核，最后以可撤销批次导入并让分页 API 直接读取已批准的该语言名称。5% 抽样仅用于发现规则及回归，所有生产数据批次必须以全库清单收口。

**Tech Stack:** Python、SQLAlchemy、PostgreSQL/SQLite、FastAPI、React/TypeScript、pytest、Vitest；线上测试 `home-ubuntu`，正式 `ucloud-v100`。

**Spec:** `docs/superpowers/specs/2026-10-02-kifu-full-name-localization-design.md`。执行代码切片时参考 `@superpowers:test-driven-development`，批次审查用 `@superpowers:requesting-code-review`，完工判定用 `@superpowers:verification-before-completion`。独立代理按文件所有权并行，任何两个代理不得同时改同一文件。

**模型分工与审批：** 用户指定由 `gpt-5.6-luna` 承担重复、资料量大的查询，结果没把握时交 `gpt-6-sol`。当前代理平台未提供 `gpt-5.6-luna`，实际执行用可用的轻量 `gpt-6-luna` 承担这一角色；若平台以后提供用户指定型号，切回指定型号。每个代理产物必须记录实际模型名，不能把替代型号冒称指定型号。查询代理只产待审候选，不得批准自己的产物。常规、来源明确的候选交**另一名独立 `gpt-6-luna` 审核代理**核对目标语言、身份、来源正文和规则后批准；不确定或审核分歧项交 `gpt-6-sol` 定向检索与裁决。若 `gpt-6-sol` 生成了新候选，再由另一名独立 `gpt-6-sol` 或 `gpt-6-astra` 复核，禁止自审。脚本先验证证据完整与语种，审核代理才可签署；审核日志存实际模型、代理/批次 ID、审核结论及时间。模型均无法确认时列给用户或受托专业审校人员裁决，并阻断该项上线和全量交付。

**2026-10-02 语言优先级补充：** 用户确认原有 `cn tw jp ko en` 五种语言优先严格核名；`de es fr ru tr ua` 六种仍须逐项交付，但有可靠的目标语言围棋资料实际用名、明确身份核对和独立复核时即可采用，不以把来源清单中其他站点全部检索一遍作为**正面惯用名**的前置条件。俄罗斯围棋联合会域名下的 Go 围棋图书馆是已登记的俄语围棋资料，个人条目可提供名称和身份线索；其自述为协作维基，不能仅凭目录同名、站点域名或名单缺项自动批准姓名。六种语言经合理且有记录的检索仍找不到当地用名时，用户允许依据已核实原名和读音规范转写，并记录依据、规则与独立复核。独立 `gpt-6-astra` max 裁决：仅六语采用有版本的有限合理检索闭环，至少一个目标语棋院/专业围棋来源加一个目标语百科或精确 Wikidata 字段，记录真实分页边界、未查渠道与已知线索；五语和既有严格闭环保持原样。校验器改动及聚焦测试通过前，不得把新许可当作绕过写入闸门。质量优先级不改变十一语言 100% 显示覆盖和零无依据回退的交付门槛。

**2026-10-03 维基百科优先用名（用户新决定）：** 对棋手，只要目标语言的维基百科页面明确对应已核实的同一人，直接采用该页实际显示的姓名，停止继续寻找该语言的棋院或其他用名来源。每人已核实的身份依据可跨语言复用；每个译名仍保存其目标语言文章 URL、修订版、实际页面语言、姓名原文与抓取记录，并由独立审核检查同人关系、消歧页、重定向及头衔混入。消歧括号不自动当作姓名，需由同页姓名正文支持最终显示值。`ua` 对应乌克兰语页面 `uk`；`cn/tw` 只采用实际核实过的简体/繁体页面变体，通用 `zh` 页面不得自行冒充两者。Wikidata 标签只用于定位文章，不能替代目标语言文章。页面不存在或身份冲突时继续原来源/规范转写路径；不得把检索未命中说成证实不存在。此规则适用于五种主要语言和六种次要语言，正面文章命中无需穷举其他来源；现有 `wikipedia_article` 证据校验与每人一次独立身份依据可直接承载，只有实际遇到阻塞契约时才做聚焦代码修改。

**2026-10-03 用户加速决定（覆盖上段六语自译前的逐名负面检索要求）：** `cn tw jp ko en` 仍按逐身份/赛事核名和严格来源审核。`de es fr ru tr ua` 优先直接采用容易取得的可靠目标语用名；没有现成用名时，允许从已经核实的实体原名、源语言和读音，按**源语言／已核读音体系 × 目标语 × 实体类别**的统一规则批量生成最终存储名；只见汉字不能推断它按中文还是日文发音。原名、身份及读音证据核实一次可供六语复用，新增逐名网络检索不是批量路径前置条件。六语不再要求对每个人或每个赛事分别完成“专业站＋百科”的无用名负面检索，也不得冒称已证明当地不存在惯用名。继续保存原名身份来源、规则版本、生产批次、独立规则审核和有限批次抽检记录；命中已知惯用名、身份冲突、碰撞或异常拼写时单独处理。十一语仍全部**预存到数据库**，切换语言只读批准行；实体身份、正式赛事归属和原 SGF 不因六语宽松而放松。此决定须先落实为受限校验器、导入器和运行时显示/搜索/覆盖路径的聚焦测试，不能把旧 `generated` 负面闭环静默跳过。

---

## 基线、范围及文件职责

正式库目前 173,025 盘、7,251 种原始棋手写法、50,222 种原始赛事实值；只有极少数实体译名已获核实。未经归并的原始值 × 11 共有 632,203 个名称项（棋手 79,761、赛事 552,442）；这不是最终审核工作量，必须先归并再测真实分母。`id % 20 = 0` 的只读 8,651 盘样本显示段位混名、损坏 SGF 字段、程序名、泛称及赛事/结果混写。全量清单需在执行时重新快照；新增棋谱进入增量队列，不能用此处固定数字作为最终分母。

5% 样本的当前关联基线：17,302 个棋手槽位中 17,137 个尚无实体 ID，涉及 2,718 种原始写法；8,514 个非空赛事槽位中 8,453 个尚无赛事 ID，涉及 6,236 种原始值。**这些是“尚未归一”，不是查证后“无法确定身份/赛事”的数量。**后者必须在 Task 4–6 完成来源查证和人工消歧后另行统计。正式库现有经审核的俄语棋手及赛事名称均为 0 条。

| 文件 | 单一职责 |
|---|---|
| `katrain/web/core/models_db.py`、`katrain/web/core/migrations.py`、`katrain/web/kifu/migrate_catalog.py`、`katrain/web/core/auth.py` | 证据、原始值、逐语言名称、审核/批次表及无损迁移、漂移保护 |
| `katrain/web/kifu/name_inventory.py`（新）、`scripts/kifu_name_inventory.py`（新） | 全库只读清单、类型/来源/年代统计、确定性快照哈希 |
| `katrain/web/kifu/name_parse.py`（新） | 姓名、段位、赛事组成部分的保守解析与坏数据识别 |
| `katrain/web/kifu/name_evidence.py`（新）、`scripts/kifu_name_research.py`（新） | 来源登记、同语言候选发现及逐目标语种证据；网络查询只产生待审候选 |
| `katrain/web/kifu/name_batch.py`（新）、`scripts/kifu_name_batch.py`（新） | 审核产物校验、dry-run、幂等导入、前后像与条件撤销 |
| `katrain/web/kifu/name_coverage.py`（新）、`scripts/kifu_name_coverage.py`（新） | 基于真实数据库关联计算全库 × 十一语言覆盖和缺口，不用种子候选充数 |
| `katrain/web/kifu/identity.py`、`katrain/web/api/v1/endpoints/kifu.py`、`scripts/import_kifu.py` | 当页批量读取获准译名、原始值类别与空值决策，跨语别名搜索；新谱导入复用解析分类 |
| `katrain/web/ui/src/galaxy/pages/KifuLibraryPage.tsx`、`katrain/web/ui/src/kiosk/pages/KifuPage.tsx`、`katrain/web/ui/src/kiosk/pages/KifuDetailPage.tsx` | 使用 API 显示值，语言变化重取并屏蔽过期响应 |
| `docs/resource/kifu-name-source-registry.json`（新） | 分语言、分机构的来源范围和检索规则版本；不存抓取正文 |
| `docs/resource/kifu-name-review-runbook.md`（新） | 核名、冲突、转写与审核操作及发布门槛 |
| `tests/web_ui/test_kifu_name_*.py`（新）和现有 kifu 测试、现有前端 localization 测试 | 聚焦解析、证据、批次、覆盖、API/页面回归 |

批准数据产物按输入清单版本分批保存于访问受控的独立存储并记录 SHA-256；仓库仅保存小型来源清单、规则和可复现脚本，不提交生产库导出或大量抓取内容。每批都要保留来源证据、审核人和数据库前后像。

资料索引从[中国围棋协会棋手名录](https://www.weiqi.org.cn/player/professional)、[日本棋院棋士资料](https://www.nihonkiin.or.jp/player/)、[韩国棋院棋手资料](https://www.baduk.or.kr/record/player.asp)、[海峰棋院职业棋士](https://www.haifong.org/profession)、[俄语围棋人物目录](https://rusgolib.gofederation.ru/KtoEst%27Kto/Mir.html)、[欧洲围棋联盟成员目录](https://www.eurogofed.org/members/)及各赛事主办方资料开始。目录页只能发现候选，实际采纳须核对人物或赛事详情与目标语言用法。中国名录和韩国目录曾在自动读取时出现空正文/“加载中”，这类响应必须记为检索未完成，不能记为无译名。

## Chunk 1：全库清单、解析及无损 schema

### Task 1：冻结全库输入与 5% 异常回归

**Files:** Create `katrain/web/kifu/name_inventory.py`, `scripts/kifu_name_inventory.py`, `tests/web_ui/test_kifu_name_inventory.py`; read `katrain/web/core/models_db.py` and the current list/detail SQL.

- [ ] 写测试：`id % 20 = 0` 的样本选择稳定；从 `kifu_albums` 的 PB/PW/EV/RO/BR/WR、身份 ID、来源中计数，输出不同原值、出现次数、受影响棋局数和清单哈希；分别报告全表与列表可见行（当前列表排除 `duplicate_of_id`），并把可用详情 ID 单列；来源统计同时读 `kifu_album_sources`，不把 SGF `source` 当数据集来源；不读取磁盘 SGF。
- [ ] 运行 `pytest tests/web_ui/test_kifu_name_inventory.py -q`，预期首次失败；在一个 PostgreSQL `REPEATABLE READ READ ONLY` 事务内按 ID 游标扫描，按固定列序、UTF-8/空值编码及 ID 升序序列化后计算 SHA-256；统计来源、年代、脚本类型，再运行预期通过。测试并发插入不会改变该次清单哈希。
- [ ] 对测试及正式库分别只读运行 `python scripts/kifu_name_inventory.py --database-url ... --output ...`；记录库标识、快照时间、总盘数、不同值与 SHA-256。正式基线需能重现当前约 173,025 / 7,251 / 50,222 量级；差异须解释，不能静默沿用旧数字。
- [ ] 用本地 `/tmp/kifu-5pct-20261002.csv` 的 8,651 盘分析异常；把每类的最小匿名化行和预期解析结果写入聚焦测试 fixture，使 CI 不依赖 `/tmp`。完整清单进入受控存储，CSV 不入 Git。提交清单工具与聚焦测试。

### Task 2：保守解析与最终显示类别

**Files:** Create `katrain/web/kifu/name_parse.py`, `tests/web_ui/test_kifu_name_parse.py`; modify `katrain/web/kifu/identity.py`, `katrain/web/api/v1/endpoints/kifu.py`, `tests/web_ui/test_kifu_localization.py`.

- [ ] 先写失败测试：`吴清源九段` 拆为姓名/段位；含 `]BR[` 的损坏值不得当正常后缀拆；`BR=白九目半胜` 不是段位，若姓名有合法末尾段位则改用该后缀，否则留空；合法 BR 与后缀冲突选 BR 并记冲突；`GNUGo3.8` 是程序标签；`JapanPromotionTournament,1934,Fall` 仅在有已审赛事 ID 时显示本地化大手合。
- [ ] 运行 `pytest tests/web_ui/test_kifu_name_parse.py tests/web_ui/test_kifu_localization.py -q`，预期新断言先失败；实现 `parse_player(raw, rank)` 和 `parse_event(raw, round_name)` 返回结构、可信度、异常代码，不写原始字段。
- [ ] 给所有原始值产生**暂定解析类别**（不持久化为已批准名称）：已识别身份、无身份但可读、占位、可证修正、损坏待审；赛事为正式赛事、通用赛事描述、对局说明、程序/来源标签、空、坏数据。只有规则明确且无冲突的解析结果可作为自动候选；正式分类与显示批准必须在 Task 3–6 的证据/审核之后，其他项进入审核队列。
- [ ] 更新 `display_event_name`，未关联或未获准的 CWI 模式不得冒充大手合；API 对无效段位给空字符串，使前端 `??` 不泄露原值；在 endpoint 测试中断言坏 `BR/WR` 均不显示。运行上列聚焦测试，提交。

### Task 3：证据与原始写法 schema

**Files:** Modify `katrain/web/core/models_db.py`, `katrain/web/core/migrations.py`, `katrain/web/kifu/migrate_catalog.py`, `katrain/web/core/auth.py`; create `tests/web_ui/test_kifu_name_schema.py`; extend `tests/web_ui/test_migrations.py`.

- [ ] 先写失败测试：空库建表、旧库无损迁移和二次迁移；原有 SGF 与 PB/PW/EV 等值完全不变；真实 FK/唯一约束生效；生产旧表不被重建。
- [ ] 新增原始棋手/赛事实值表（原值唯一、类别、解析版、审核状态），原始值对应的 `(raw_id, lang)` 译名表；现有 `kifu_player_names/kifu_event_names` 保留 `verified/review/missing` 生命周期，另加 `decision_kind`（来源采用、自译等）、证据引用及生成规则；只有已批准 `verified` 对外显示。旧 `verified` 行及 `reference_url` 原样保留为 legacy 数据，不能伪造检索证据；逐条核对后补证据和批准标志。新 API 的严格显示模式仅在全库已审数据准备好后切换，迁移与前端发布期间不得让未核实 legacy 名称冒充合格覆盖。译名行默认处于待审状态。
- [ ] 新增 `source_registry`、逐身份或原始值 × 语言的 `research_evidence`（检索词/原脚本/来源 URL/实际返回语言/时间/命中/未命中/候选排除理由/原名或读音依据/规则版本/审核人），以及批次和前后像变更表；名称的上线状态必须引用有效证据。SQL 类型容纳长尾描述，关联键和 `(owner, lang)` 有索引。
- [ ] 在 `migrations.PROTECTED_TABLES` 与现有精确集合测试中加入全部新增权威表，防止 SQLite 漂移重建；旧表新增列须显式 `ALTER TABLE`，不能依赖 `create_all`；旧表 FK/唯一/检查约束用独立 DDL 或先校验再建索引，PostgreSQL 大表索引使用并发创建/需扫描的约束单独验证。把新表加入 `katrain/web/kifu/migrate_catalog.py` 的 `CATALOG_TABLES`，由该脚本执行显式升级，`auth.py` 启动仅作存在性/漂移检查。运行 `python -m katrain.web.kifu.migrate_catalog --validate`（在隔离库，预期输出 `Kifu catalog schema ready; foreign keys validated`），再运行 `pytest tests/web_ui/test_kifu_name_schema.py tests/web_ui/test_migrations.py -q`，预期通过，提交。

## Chunk 2：身份归一、网络查证与十一语言产出

### Task 4：实体/原始写法映射及冲突审核

**Files:** Create `katrain/web/kifu/name_match.py`, `tests/web_ui/test_kifu_name_match.py`; modify `scripts/kifu_name_inventory.py`; do not call `catalog_backfill`'s combined dedup path.

- [ ] 写失败测试：吴清源不同脚本别名归一；相同汉字但人物不同保持两个 ID；无身份证据的原名保留原始写法显示层；年份、赛季、轮次从事件专名分离，赞助商变更及赛事更名须核对年代，不能仅去年份合并；损坏姓名只做有证据派生修正，否则显示本地化错误提示。
- [ ] 运行测试看失败；实现只读候选匹配和待审清单。官方人员/赛事目录、原始 SGF 对局日期、来源、对手只能作证据，不能按数据包路径推断国别或读音。每个自动连接标识规则版本和置信边界。
- [ ] 全量按来源与频次运行匹配，导出全部冲突、空白及未归一说明；按本计划的**独立审核代理→疑难 `gpt-6-sol`→必要时用户/专业审校**路由批准后，才形成带原始行/值作用域的批次。分别报告“尚未关联”“查证后确实无法确定身份”“原始资料损坏/占位”三类，按原始写法数和受影响槽位数双口径计数；统计“实际已连接的 album FK”，不用种子命中量代表连接率。运行聚焦测试并提交。

### Task 5：资料来源登记及逐目标语言检索

**Files:** Create `docs/resource/kifu-name-source-registry.json`, `katrain/web/kifu/name_evidence.py`, `scripts/kifu_name_research.py`, `tests/web_ui/test_kifu_name_evidence.py`.

- [ ] 写失败测试：产品语码 `ua/jp/cn/tw` 分别查 `uk/ja/zh-Hans/zh-Hant`，保存来源原始标签；Wikidata `mul` 或接口 fallback 不算目标语译名；同形异人不得共享检索结论；冲突候选不得自动转写。
- [ ] 实现来源清单版本、专业源优先级、受限速率/重试的批量候选发现和证据导入格式。每个实体或未归一可读原值 × 每个目标语言，记录原名/读音/所属语言依据、查询的别名和检索词、来源范围、日期、命中页及候选；优先查官方棋院/赛事主办方及目标语言围棋资料，维基百科同语言页需独立核对身份，Wikidata 标签只用于发现线索。**一旦取得可信正面用名证据即可进入独立审核，尤其六种新增语言无需继续做全来源的负面穷尽检索。**来源范围全部检查仅适用于宣称“范围内没有通行名”的生成候选。缓存请求与查询模板可以复用，但每个最终名字有自己的证据链接。
- [ ] 把重复检索按**不重叠的实体/原始值 ID × 语言**分批交给 `gpt-6-luna`（`gpt-5.6-luna` 可用时按用户指定替换）。先构建/缓存官方目录与同语言专业资料索引，再复用已查页面，避免每盘、每年或每个代理重新下载同一资料。代理仅输出结构化候选：对象 ID、目标语种、实际页面语言、查询词、URL/页面位置、命中/未命中/不可用、身份匹配依据、原名读音依据、候选名及不确定原因；校验器拒绝无 URL、无真实正文或语种不符的“已查”记录。
- [ ] 定义无通行名判据：规定来源范围已查、实际语言标记核对、候选逐项排除并记理由、审核人签字；只有此结论才能调用自行转写/翻译。若有可采纳通行名，直接采用并记来源；互相冲突时人工裁决。任何网络不可用、限流、反爬、空正文、分页未完成要标记 `unavailable/incomplete`，保持待审，不能自动推断为“没有”；只有确实完成检索才可标 `not_found_in_scope`。
- [ ] `gpt-6-luna` 对同名异人、证据冲突、来源语言回退、缺原名读音、历史更名/赞助商变化、坏 SGF、无法获取来源或自身低把握项，附已查证据与明确问题升级给 `gpt-6-sol`。后者补充定向检索并给出处可复核的判断或继续标待审；不得凭模型自信把未查完来源记作“无惯用名”。已充分解决的批量项不再重复交高成本模型。
- [ ] 运行 `pytest tests/web_ui/test_kifu_name_evidence.py -q`，预期通过；抽查吴清源的中/英/日/俄名称及大手合，核对真实专业来源与页面语言。提交代码、来源清单和测试。

### Task 6：十一语言候选、语种审核与批准产物

**Files:** Create `katrain/web/kifu/name_candidates.py`, `scripts/kifu_name_candidates.py`, `docs/resource/kifu-name-review-runbook.md`, `tests/web_ui/test_kifu_name_candidates.py`.

- [ ] 写失败测试：有通行名先采用；无可采纳通行名且来源语言/读音已确定才准生成候选；中文/日文同形不能无依据共用读音；赛事组成部分年份/赛季/届次/轮次各语模板化；程序标签/空值按类别隐藏；损坏值有证据修复或本地化错误决策。
- [ ] 构建逐条候选表：实体/原始值 ID、语种、显示值、采用或自译状态、来源证据 ID、转写/翻译规则版、查询代理与审核代理的独立 ID/实际模型/结论/时间。查询代理产物只标 `review`，由**不同代理**查对目标语言来源和身份后才能 `approved`；反查与相近名碰撞、错把段位/结果写进姓名、字符脚本、超长文本均列成审核错误。校验器拒绝查询与审核代理相同或缺签署的行。
- [ ] 按频次 × 错名风险给并行代理划分**不重叠的实体/语种批次**，对全库每一项执行查证与审核。常规项由独立 `gpt-6-luna` 语种审核代理批准；证据冲突、来源缺失、译名不确定由 `gpt-6-sol` 裁决；后者提出的新候选再交另一独立高级代理审核。两级代理仍无把握者交用户或受托专业审校人员，未获决定前保持待审并阻断全量发布。批次输出带清单版本和哈希；所有 11 种语言逐项清零。每次运行 `python scripts/kifu_name_candidates.py validate --bundle ...`，预期无 `missing_evidence/unreviewed/conflict` 才允许入库。记录实际剩余数和处理吞吐，追加批次直到为 0。
- [ ] 每批报告 `gpt-6-luna` 已查、升级 `gpt-6-sol`、仍待审、被规则校验驳回的数量及实际模型/令牌开销；按来源哈希去重缓存，不重复付费查询。抽查轻量模型判定“已有惯用名”和“未发现惯用名”的证据质量；抽查失败时扩大该规则批次的复核范围。独立语种审核仍是发布门槛。
- [ ] 完成小型高风险样本的人工对照，并运行 `pytest tests/web_ui/test_kifu_name_candidates.py -q`，预期通过，提交工具及 runbook；大规模批准数据作为独立受控产物保存。

### Task 6a：逐对象、逐语言的有限未命中审核（2026-10-02 补充）

**Files:** Modify `katrain/web/kifu/name_evidence.py`, `katrain/web/kifu/name_candidates.py`, `docs/resource/kifu-name-review-runbook.md`, `tests/web_ui/test_kifu_name_evidence.py`, `tests/web_ui/test_kifu_name_candidates.py`; keep `docs/resource/kifu-name-source-registry.json` as source registry, not a global absence assertion.

大手合乌克兰语调研显示：规定的专业和百科范围可以对**一个对象 × 一种语言**收口，而全局 `ua.complete_for_negative_claims` 仍须保持 `false`。独立 `gpt-6-astra` 已裁定这项有限范围足以进入自译候选研究，但**没有**批准具体乌克兰语显示词。`docs/resource/kifu-name-oteai-uk-scope.md` 是本例的范围记录，论坛俄语命中须作为被排除线索保存，不能写成无命中。

- [ ] 先写失败测试：同一审核闭环只能用于其精确 `owner/lang/source_lang/registry_sha256/scope_id`；证据检查集合或原文读音变更使签名失效；必查项 `partial/unavailable` 拒绝；已发现但被排除的线索需要正文、实际语种、排除理由和独立裁决；发现 Wikidata `uk` 空标签只证明该来源未命中；生成候选不能因为其他对象的未命中获准。
- [ ] 定义有限 `negative_closure`：版本、对象、产品/来源语码、范围 ID/版本、registry 哈希、必查 check ID 列表、证据哈希、范围边界、保留的不可用/未索引渠道、独立审核者真实 ID/模型/时间、`approved_not_found_in_scope` 结论和理由。证据哈希只覆盖闭环之外的对象/语码/来源检查及原名读音锚点，避免自引用；整个研究记录仍由候选 `research_sha256` 绑定。
- [ ] 每条必查检查记录来源 ID、方式、查询词、结果/正文 URL、访问时间、实际正文语种、响应/正文哈希、`complete|partial|unavailable`、`no_target_string|rejected_leads`；被排除线索带原名、来源正文哈希、实际语种、排除依据和独立裁决。校验器要求所有必查项完成且覆盖该对象范围内的登记专业/百科/Wikidata 来源；明确列出的非索引渠道可以保留为边界，不得被伪称已查完。
- [ ] 生成姓名或赛事名仍另需独立候选审核、源语原名和读音来源、命名规则版；闭环只批准“所列范围未发现惯用名”，不自动批准任何转写。运行 `pytest tests/web_ui/test_kifu_name_evidence.py tests/web_ui/test_kifu_name_candidates.py -q`，确认上述失败案例变绿，提交代码和手册。大手合 `おおてあい` 的读音需引用可靠日语辞典；具体乌克兰语写法须再由语言资料支持并独立审核。

### Task 6b：六种新增语言的合理检索转写闭环（用户补充，独立 Astra 裁决）

**Files:** Modify `katrain/web/kifu/name_evidence.py`, `tests/web_ui/test_kifu_name_evidence.py`, `tests/web_ui/test_kifu_name_candidates.py`, `docs/resource/kifu-name-review-runbook.md`; no database/schema/import changes.

- [ ] 为 `negative_closure` 新增 `version: 2`、`search_policy: "secondary_reasonable_v1"`、`bounded_scan_ids`，硬限制 `de es fr ru tr ua`。至少有一个适用于对象的目标语 `official/language_go` 完成检查，以及一个目标语 `wikipedia_article/encyclopedia` 或精确实体字段的 Wikidata 完成检查；所有已知线索须核实或独立排除。只能声称**所列范围内未找到可用名**，不能声称绝对没有译名。五种原有语言继续使用 v1 完整来源闭环。
- [ ] v2 可声明真实有限分页：扫描从第 1 页连续至本次范围页数；末页必须保留真实 `next_page_url`、`pagination_exhausted=false`，并在 `pagination_basis`、`retained_limitations` 写明为何停止及尚未遍历的余页。未声明限页者仍须真穷尽；网络失败、空正文、语言回退不可记为完成。研究哈希、闭环范围哈希须纳入 v2 的策略与限页 ID，v1 规范哈希及现有工件字节不变。
- [ ] 沿用原名/语种、独立读音来源、生成规则版、闭环先于候选审核、独立 `generated_review`、同名冲突和前像/导入闸门。先写聚焦失败测试：六语专业源加百科或 Wikidata 通过；五语 v2、单来源、错误语种、部分检查、未决线索、断页、伪终页、策略/范围/读音被改后旧哈希均拒绝；v1 严格工件仍通过。再实现并运行 evidence/candidates 聚焦测试，经独立规范和代码审核后提交。

### Task 6c：六语批量规范转写路径（2026-10-03 加速决定）

**Files:** Modify `katrain/web/kifu/name_evidence.py`, `katrain/web/kifu/name_candidates.py`, `katrain/web/kifu/name_batch.py`, `katrain/web/kifu/identity.py`, and only where needed `katrain/web/api/v1/endpoints/kifu.py`, `katrain/web/kifu/name_coverage.py`; focused tests in `tests/web_ui/test_kifu_name_evidence.py`, `test_kifu_name_candidates.py`, `test_kifu_name_batch.py`, `test_kifu_name_api.py`, `test_kifu_name_coverage.py`; controlled language-rule and candidate batches stay outside Git.

- [ ] 先写失败测试：新批量转写决策仅允许 `de es fr ru tr ua`；必须绑定经审核的实体原名、源语言、已核读音体系、准确的目标语规则版本与独立签名；不能写成 `conventional`，不能声称“检索证明无惯用名”；规则/原名/读音/成员/输出改变、跨批同语碰撞、异常拼写、错误读音体系、缺来源或自审一律拒绝。旧五语和旧 `generated` 负面闭环测试保持通过。
- [ ] 实现最小新决策分支，允许六语由受控规则在离线阶段生成、审核并存储 `display_name`，无需逐实体负面检索。优先从明确正面资料采用惯用名，批量路径不覆盖已审核的目标语惯用名；规则适用范围外的名称进入异常队列，不以原文无说明回退。导入器继承实际名称行前像、跨批碰撞检查、独立签署及条件撤销；API、搜索与覆盖率共用相同的已批准资格判定。
- [ ] 按源语言/读音体系、目标语和实体类别分有限批次；人工审核规则、代表样本和**全部异常**，并对批次每行机械复算。批准签署冻结的完整成员集合、每项输出、规则及原名/读音依赖哈希，任何增删或变更均使批准失效；无需逐名人工语言审核。报告已批准人数/赛事数、受益棋局数、碰撞与待审数。先在隔离副本 dry-run/apply/undo 和 11 语显示/搜索/覆盖一致性核对，再进入原 Task 7–12 的全库发布闸门。

### Task 6d：主五正面来源批量与中文姓名正字门禁（2026-10-03 补充）

**Decision:** 采纳独立 `gpt-6-astra/max` 的[裁决](../../resource/kifu-name-main-five-batch-policy-decision-2026-10-03.md)。逐人物官方身份/生日与 GoRatings 同 ID **实际目标语正文姓名**可作为 `cn tw jp ko en` 正面用名证据批量复用，不额外要求 Wikidata 四语标签完全一致；页面回退、身份冲突及不同 ID 仍 HOLD。另仅对已核实中文来源完整汉字人名新增 `primary-orthographic-v1`，允许审核过的无歧义 `cn↔tw` 字形生成为 `generated`；不得用于 `jp ko en`、赛事或六语，不得把旧 387 人检查自动视为获批。主五其余生成路径维持严格来源要求；十一语 100% 门槛不变。

**Files:** Modify `katrain/web/kifu/name_evidence.py`, `katrain/web/kifu/name_candidates.py`, `katrain/web/kifu/name_batch.py`, `katrain/web/kifu/identity.py`; use `katrain/web/kifu/name_coverage.py` only if it does not already share the identity resolver. Add focused cases in `tests/web_ui/test_kifu_name_evidence.py`, `test_kifu_name_candidates.py`, `test_kifu_name_batch.py`, `test_kifu_name_api.py`, `test_kifu_name_coverage.py`. Store reviewed rules, finite member bundles and source snapshots in the controlled audit directory.

- [ ] **Positive-source batch:** Reuse one approved official identity/DOB anchor and actual per-language GoRatings same-ID page body for each person; mechanically check person ID, DOB, text span, returned language, normalized display string and full-body hash on every row. On first parser template inspect `min(20,N)` whole bodies, thereafter `min(N,max(10,ceil(0.05N)))`, plus all exceptions; wrong extraction, missed fallback or identity mix-up pauses the affected template batch. Independent reviewer checks every complete output and all collisions; a true fallback or disputed person remains HOLD. Record conventional candidates through existing review and preimage flow.
- [ ] **Failing tests first:** Assert only `player/raw_player` with reviewed Chinese source identity and complete Han personal name can use `primary-orthographic-v1` for `cn/tw`; reject other languages, event owners, ambiguous surname/character mapping, `于/於` or `钟/鍾/鐘` without specific approval, existing conflicting conventional name, owner/raw-scope mismatch, self-review and stale rule/member/source/preimage hash. Assert persisted evidence tampering removes display, search and coverage eligibility. Run each new focused test before implementation and observe failure.
- [ ] **Minimal implementation:** Add a distinct `primary_orthographic` evidence kind/version with signed exact `source_char → target_char`, normative table version/location, regional/script direction, human-name applicability, approved exclusions including retained characters, and content hash; approve the reverse direction separately. Require official original-name/person binding, approved raw scope where relevant, finite `owner × original_name × lang × output` members and full-name independent review; record exact code-point substitutions and `decision_kind=generated`. Final reviewer must differ from source producer and name-preimage binder, and review after member freeze. Do not use negative-search or reading fields for this pure orthography path. Keep the existing five-language `generated` validator unchanged for other rules.
- [ ] **Import and runtime gate:** `name_candidates.py` validates the payload, independent reviewer and actual name preimage; `name_batch.py` rechecks source/rule/member hash, approved-name snapshot and catalog hash, collisions including aliases, known conventional names and row preimage under its existing transaction. `identity.py` verifies the persisted payload and exact name row for both display and search; coverage must use that same qualified resolver. A changed rule, member, original, name, approval or source body is ineligible even after import. No automatic player FK or alias expansion.
- [ ] **Verify and review:** Run `pytest -q tests/web_ui/test_kifu_name_evidence.py tests/web_ui/test_kifu_name_candidates.py tests/web_ui/test_kifu_name_batch.py tests/web_ui/test_kifu_name_api.py tests/web_ui/test_kifu_name_coverage.py`; on isolated PostgreSQL clone, dry-run/apply/replay/undo a small signed `cn/tw` batch and check SGF/FK unchanged plus display/search/coverage consistency. Independent spec and code review must pass before merging code; actual name batches require separate independent approval. Commit code and plan separately; do not touch live databases before Task 12.

## Chunk 3：安全写入、API/前端与真实覆盖率

### Task 7：独立批次导入、幂等及条件撤销

**Files:** Create `katrain/web/kifu/name_batch.py`, `scripts/kifu_name_batch.py`, `tests/web_ui/test_kifu_name_batch.py`.

- [ ] 先写失败测试：dry-run 零写入；同一 bundle 二次执行零新增；只写清单中原始值/album ID；FK 冲突中止；事务中每行记录前后像；撤销只在当前值仍等于本批后像时恢复，保留后续用户改动。
- [ ] 实现 `validate/dry-run/apply/undo/status` 子命令，入库前核对 source registry 版本、清单哈希、11 语言证据、批准人和数据约束。独立于现有会写来源/去重的 `backfill_catalog`。一个有唯一 bundle 哈希的子批次是原子写入单位：身份/译名/album FK/前后像在同一事务提交或全部回滚；失败只能从上一个已提交子批次续接；每次显示受影响对局和预计回滚范围。
- [ ] 覆盖已有译名行时，在审核工件中钉住该 `(owner,lang)` 的既有行前像或等价哈希；`apply` 在已持有写锁的事务内逐行比对，不允许研究后发生的人工改名被静默覆盖。新增姓名行须钉住“原先不存在”；缺少这个约束的旧 bundle 只允许验证，不得写入正式库。加入并发/陈旧前像拒绝测试。
- [ ] 在测试库对 5% 样本批次演练写入、重复写入、**子批次中途故障全回滚**、他人改动后条件撤销和再次应用；对比 SGF 及原始元数据哈希。运行 `pytest tests/web_ui/test_kifu_name_batch.py -q`，预期通过，提交。

### Task 8：API 显示与跨语言搜索

**Files:** Modify `katrain/web/kifu/identity.py`, `katrain/web/api/v1/endpoints/kifu.py`; create `tests/web_ui/test_kifu_name_api.py`; extend `tests/web_ui/test_kifu_localization.py`, `tests/web_ui/test_kifu_list.py`.

- [ ] 写失败测试：当页 20 盘 × 11 语言均取获准姓名、赛事或分类决策；5% fixture 的七来源与不同年代、CWI、大段位错误、`GNUGo`、泛称、EV/结果混写、空值/未知/未归一姓名均进入 API 断言；未关联但可读者取 raw-name 译名；坏数据按语言提示/隐藏；`吴清源/Go Seigen/Го Сэйгэн` 返回同一集合；歧义别名不把不同人合并；未获准名称绝不展示；已审核的无身份原始姓名译名可以按**该原始写法**检索，但不得把同名不同人合并；原始 SGF 字段不变。
- [ ] 实现分页后的批量名称/来源读取，响应现有 `display_*` 字段且不 N+1；为全部显示槽位返回权威非 null 值（应隐藏时返回空串，未知或损坏值返回本地化提示），不让前端用原始字段回退。跨语言别名匹配仅对已核实身份和无歧义别名扩展；无身份 raw-name 的各语译名仅映射回相同 raw 值或逐盘审核的范围，原始值仍可直接搜索。改动查询前后分别测 `EXPLAIN` 与 11 语种 P95，语言切换不重算与语言无关的昂贵结果。
- [ ] 运行 `pytest tests/web_ui/test_kifu_name_api.py tests/web_ui/test_kifu_localization.py tests/web_ui/test_kifu_list.py -q`，预期通过；核对 Galaxy 与 board 模式契约，提交。

### Task 9：页面显示与语言切换

**Files:** Modify `katrain/web/ui/src/galaxy/pages/KifuLibraryPage.tsx`, `katrain/web/ui/src/kiosk/pages/KifuPage.tsx`, `katrain/web/ui/src/kiosk/pages/KifuDetailPage.tsx`, both `katrain/web/ui/src/{galaxy,kiosk}/components/report/ReportLibraryImportDialog.tsx`, `katrain/web/ui/src/galaxy/components/research/CloudSGFPanel.tsx`, `katrain/web/ui/src/{galaxy,kiosk}/pages/ResearchPage.tsx`, `katrain/web/ui/src/types/kifu.ts`; extend relevant `*.localization.test.tsx`, import-dialog and research tests.

- [ ] 写聚焦测试：中文搜索后切俄语/乌克兰语，卡片人名、赛事、段位及本地化坏数据提示切换，查询词/页码保持；旧语言迟到响应不覆盖新语言；API 返回空字符串、null 或缺失显示字段时，前端按契约显示空/加载错误提示，**绝不**退回错误原文；详情标题、棋盘转入/研究标题也要核对。
- [ ] 盘点所有 `KifuAPI.getAlbums/getAlbum` 调用：棋谱页、详情页、Galaxy/Kiosk 报告导入弹窗、CloudSGFPanel、研究页可见标题均传 `lang` 并消费 `display_*`；SGF 原文导入字段保持原值。只修改必要显示位置和翻译词条，不改变卡片设计。运行对应 Vitest 与 `npm run build`（工作目录 `katrain/web/ui`），预期通过；以现有目标 viewport 做一次真实页面预览，提交。

### Task 10：真实全库覆盖率与差异补录循环

**Files:** Create `katrain/web/kifu/name_coverage.py`, `scripts/kifu_name_coverage.py`, `tests/web_ui/test_kifu_name_coverage.py`; extend `docs/resource/kifu-name-review-runbook.md`.

- [ ] 写失败测试：覆盖率以**列表可见及可用详情 ID 的并集 × 黑/白/赛事槽位 × 11**为分母，逐种语言区分官方/通行名、自译、通用值、合理隐藏、损坏提示、待审、原文回退；种子中有候选但 album 未连接计为未覆盖。程序标签隐藏不能掩盖真实赛事缺译；详情可访问的重复谱也必须有合格显示决策。
- [ ] 覆盖报告必须调用与 API 共用的显示决策解析器（或逐项重算并与 API 抽查比对），验证每盘每语种的**实际显示**、证据、类别及赛事年份/赛季/轮次与段位组合，不能只数已批准译名行。实现只读 SQL/批量覆盖报告、按源/年代/语种/类别分层，以及缺口清单和 SHA-256；5% fixture 的七来源与各异常类型须有覆盖断言。统计原始字段不变、无悬空 FK、无审批前显示、无错名碰撞；对导入后新增棋谱重跑增量清单与步骤 4–7。
- [ ] 每个批次在测试库重跑 `python scripts/kifu_name_coverage.py --database-url ... --output ...`，对未覆盖、冲突和新数据返回非零退出码；重新查证、审核、导入直到**每语种黑白姓名及赛事槽位的合格显示决策达到 100%，未经说明原文回退为 0**。运行聚焦测试并提交。

## Chunk 4：复核、上线与验收

### Task 11：系统集成与独立代码审核

**Files:** All changed code and tests; record summary in `docs/resource/kifu-name-review-runbook.md`.

- [ ] 在隔离测试库上运行完整十一语言批次、数据前后像核对、精确搜索等价、分页性能与回滚演练；原始 SGF 和元数据哈希不变。运行上述聚焦 pytest/Vitest 及 `npm run build`，按真实风险补测迁移/导入边界。
- [ ] 依 `@superpowers:requesting-code-review` 派独立代理审查 schema、证据门槛、身份误合并、批次可撤销、搜索和显示；Critical/Important 修复后重审至通过。按 `@superpowers:verification-before-completion` 记录运行命令、输出与未覆盖数，不以测试绿灯代替全库翻译完成。

### Task 12：测试及正式部署，十一语言全量交付

**Files:** Deployment record and approved data bundles; follow existing deployment runbook for web services.

- [ ] **前置兼容迁移（不激活功能）**：旧生产 `kifu_player_names/kifu_event_names` 尚无 `decision_kind/generation_rule_version/revision/evidence_id`，因此不能在旧表上臆造完整行的 `name_preimage_sha256`。固定代码 SHA，先对正式备份在隔离 PostgreSQL 副本恢复并运行显式 `migrate_catalog --validate`，核对旧姓名行、棋谱原文及行数不变、旧应用可读；再保留可恢复的正式备份，以有限锁等待运行同 SHA 的一次性迁移。保持现役 Web 和 `KIFU_STRICT_NAMES` 关闭。迁移后只读采集**实际正式库完整姓名行**的前像，将其加入有限候选，重新进行独立签署；候选缺失或前像改变即阻止导入。此前的来源审核仍有效，但不能替代新前像审核。此步骤经独立 `gpt-6-astra` max 决策，且不降低下述 100% 发布门槛。
- [ ] 查两环境当前 SHA、服务及数据库版本；各自做可验证备份与恢复演练。先部署测试代码/迁移，在生产等价的隔离测试副本上对**最终正式快照及每个增量 bundle**分别 dry-run、apply、100%/零缺口覆盖核对、条件撤销演练、页面 11 语种及跨语搜索验收；记录每批 bundle 哈希和 batch ID。
- [ ] 正式环境使用同一代码 SHA 和**在隔离测试副本通过的同哈希审核产物**分批 dry-run/apply；任何正式清单差异必须先生成新 bundle，回到隔离测试副本完成 dry-run、apply、覆盖率及撤销演练后才可进正式；若正式快照再次变化，重复这一关。每批前后检查行数、FK、原始 SGF/元数据哈希、覆盖率与 API 健康。新进棋谱持续进入增量查证队列，冻结验收时点后重新跑全库报告。
- [ ] **发布完成条件**：正式库当前全部可见棋谱在 11 语言的黑方、白方、赛事均有合格显示决策，待审/无证据自译/不明原文回退为 0；真实赛事有独立 ID，例外类别有审查原因；`吴清源/Go Seigen/Го Сэйгэн` 搜索一致，语言切换页面正确；代码审查通过并记录备份、批次与回滚点。任一条件未达，只报告阶段进度，不宣称全量完成。

## 并行与审查约束

Task 1 与 Task 3 的设计/测试、Task 4 的候选规则与 Task 5 的来源清单可由不同代理并行；共享 schema 与 API 契约冻结后，Task 5/6 的不重叠实体/语种批次可大量并行。Task 7 的真实写入、Task 8 的 API、Task 9 的页面须按依赖衔接；主代理负责合并、测试、覆盖率和发布。资料查证代理只产候选与证据，不得自行批准自己的机器候选；另一名独立审核代理负责常规项批准。重复检索固定由轻量 `gpt-6-luna` 承担（待指定的 `gpt-5.6-luna` 可用时替换）；只有明确证据冲突或低把握项升级 `gpt-6-sol`，并记录交接证据，避免同题重查。高风险身份冲突及赛事专名需要独立核对；普通 UI 调整只做聚焦验证。

大规模数据产出没有“固定几天可做完”的假设。Task 1–4 完成后先测出实际不同**身份/赛事/说明**数量与每语种审核吞吐，再据此分配并行批次；增派代理或审核人员不改变 100% 门槛。网络资料缺失、来源限流、身份无法判定时记录为明确缺口并继续其他批次，绝不把未检索视为“没有约定译名”。
