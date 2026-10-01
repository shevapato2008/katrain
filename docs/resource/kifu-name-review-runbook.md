# 棋谱姓名与赛事名称审核手册

本手册用于十一语言全量核名。`en cn tw jp ko de es fr ru tr ua` 是产品语码；查资料时分别使用来源清单中的实际语言标签，尤其 `cn→zh-Hans`、`tw→zh-Hant`、`jp→ja`、`ua→uk`。全库完成的判据见实施计划 Task 10–12；某个有限批次通过校验不代表全库通过。

## 研究与命名顺序

1. 从只读 `inventory_format=2` 清单选择**互不重叠**的实体或原始值 ID × 语言。先核身份：人物生卒年代、对手、棋院资料、赛事年代和主办方。原始同形不等于同一人；年份、赛季、届次和轮次不是赛事专名。保留原始 SGF 字段。
2. 按 `kifu-name-source-registry.json` 检索目标语言的棋院/主办方及专业围棋资料，再查维基百科对应语言页和 Wikidata 精确语言标签。记录每次查询词、URL、实际正文语言、页面正文摘要和 SHA-256、访问时间、身份匹配依据。主页、目录、搜索摘要和 Wikidata 回退标签只能发现线索，不能单独证明最终名称。
3. 找到可采用的惯用名时，候选类型为 `conventional`，名称必须逐字出现在有实际目标语言正文的专业来源中。目标语言维基百科文章或独立百科可作为名称用法证据，须另记文章版本、标题、逐字正文及其哈希，并用**另一出版方**的棋院、围棋资料或参考资料核对原名和身份；Wikidata Q 标签仍只是线索。来源清单 `2026-10-02.2` 已将维基百科单列为 `wikipedia_article`，旧版研究哈希不会自动升级，须按新版重做证据。自动抓取只提供页面线索，文章版本和独立身份依据仍须人工核对并补齐。各来源互相冲突时，保留冲突和排除理由，转交疑难审核，不自动挑一个。
   吴清源样本的德/西/法语部分来源是 PDF。当前 `capture` 命令只解析 HTML，**不能**从 PDF 自动取得正文证据；可人工读取原 PDF 字节计算 `body_sha256`，逐字记录目标页正文、页码、实际语种 `observed_lang` 和 `language_basis: "reviewed_text"`，再由独立审核者对照 PDF。缺页、乱码或仅有搜索摘要时标 `incomplete`。
4. 只有目标语言范围内**所有规定来源**均完成搜索、逐项记录未命中，并取得下述逐对象有限负面闭环（或来源清单明确允许全语种负面结论），才可以提出 `generated` 候选。每项未命中须明确记为 `no_target_string` 或 `rejected_leads`；后者逐条保存原名/候选、网页正文及哈希、实际正文语言、拒绝依据和独立 Sol 审核，不得把发现过的名字写成“完全没找到”。棋手与赛事均须有可信源语原名、所属语言和**独立来源的读音**；中日同形文字不证明读音相同。赛事翻译还需组成部分依据。网络不可用、限流、反爬、空正文、语言回退或未遍历分页一律标 `incomplete`，不能视作“无通行名”。
5. 清晰的泛称如“段位赛”可提交 `generic`；明确空值和程序标签可提交空显示的 `hidden`；`Unknown/Black/White` 等占位棋手用本地化“未知棋手”提交 `placeholder`；损坏原文可提交本地化 `error` 或有专业来源对应的 `corrected`。不能用这些类型隐藏真实赛事、对局叙述或未完成核名的棋手。数据库 `NULL` 或空白 EV 槽位根本没有待翻译的来源值，API/覆盖率代码仅对该狭窄情形作明确空显示决策，无需伪造检索证据；非空真实赛事仍须获准证据。

`classification-v1` 在代码中给十一语言定义了这些类别的**待审核文案模板**。模板存在不等于译文获准上线；每种语言须由独立审核代理核对后，在候选中记录 `template_review`（版本、语言、模板 SHA-256、审核者实际 ID/模型/时间和结论），且候选本身也须有独立批准签名。校验器只接受与该版模板逐字相同的显示值；改文案须升级版本并重审，不能靠候选里任意写词来绕过来源查证。真实赛事绝不能改标泛称。

## 代理与审核

重复的资料查询优先派给用户指定的 `gpt-5.6-luna`；当前平台未提供该型号时，使用 `gpt-6-luna` 并记录**实际模型名**。查询代理仅产待审证据和候选。另一名独立 `gpt-6-luna` 审核代理核对来源正文、实际语言、身份、名字与段位/结果拆分后签署常规项。证据冲突、错认风险、资料缺失、历史改名或轻量代理无把握的事项升级 `gpt-6-sol`；若 Sol 创建新候选，再由另一独立 Sol 或 Astra 审核。两级仍无法判断时保持待审，交用户或受托专业审校人员。查询代理不得审核自己的候选。

每条候选记录 `producer_id`、`producer_model`、`produced_at`，以及独立的 `reviewer_id`、`reviewer_model`、`reviewed_at`、`review_conclusion`。审核者实际比对过的来源和语种应写在结论中。待审行没有审核签名，任何脚本不得自动改为 `approved`。检索记录与候选记录以规范 JSON SHA-256 绑定；候选中的 `research_sha256` 必须与对应原始检索记录完全一致。

同一检索记录里出现不同候选名时，每个被排除的名称须在 `excluded_candidates` 留下 `source_id`、`candidate_name`、`reason`。同语言同显示名落到不同身份 ID 时，批次校验报告碰撞；只有逐人核查后在每条候选写 `collision_decision: "distinct_people_confirmed"` 和具体 `collision_basis` 才能通过。这不合并两个身份。跨批次碰撞由数据库导入/覆盖率步骤继续检查。

## 逐对象有限未命中闭环

`negative_closure` 只批准**一个精确 `owner × lang × source_lang × scope`** 内未找到可采纳惯用名，不批准任何显示词。`ua.complete_for_negative_claims` 及其他全局标志仍为 `false`。大手合乌克兰语的已裁定范围见 [定向检索记录](kifu-name-oteai-uk-scope.md)和[独立裁决](kifu-name-oteai-uk-decision.md)；具体乌克兰语词形仍待读音/构词规则研究及独立候选审核。

在研究记录中写 `source_lang`（必须等于有来源证明的 `original_language`）和 `negative_closure`。闭环字段为 `version: 1`、精确 `owner`、产品语码 `lang`、`source_lang`、`scope_id`/`scope_version`、`registry_sha256`、`required_check_ids`、`required_checks`、`known_leads`、文字 `scope_boundary`、明确保留的 `retained_limitations` 列表、`scope_sha256`/`evidence_sha256`、独立审核者实际 `reviewer_id`/`reviewer_model`/`reviewed_at`、`conclusion: "approved_not_found_in_scope"` 及具体 `reason`。`scope_boundary` 应列清页面、检索词、分页和实体字段；未索引论坛、不可取得的出版物等写入限制，不得记为已查完。来源清单的该语种必查专业/百科/Wikidata 来源必须全部由闭环的检查覆盖。

`required_checks` 是由独立审核者先核定的**范围义务**，不能从实际检查倒推生成。每项固定 `check_id`、`source_id`、`method`、完整查询词、精确 URL（含参数）、`searched_forms`、`entity_field_scope`、`scan_id`、`page_index`/`page_count`、`next_page_url`、`pagination_exhausted` 和 `pagination_basis`。同一 `scan_id` 的页码必须从 1 连续到总页数；末页明确无续页，前页指向清单中的下一页。Wikidata 实体检查固定 QID、请求语言和 labels/aliases/sitelinks 字段。观察记录的对应字段须逐项等于义务，并另存 `fetched_at`、实际正文 `observed_lang` 与 `language_basis`、`response_sha256`、`body_sha256` 和正文摘录，标 `status: "not_found"`、`completeness: "complete"`、`scope_complete: true`、`search_scope`，以及 `negative_outcome: "no_target_string"` 或 `"rejected_leads"`。`partial/unavailable` 不能进入已批准闭环。

范围内的俄语页面可以作为额外的已查页面保留真实语种，但每个登记必查来源仍须至少有一次目标语种的完整检查。已知俄语论坛命中等在 `known_leads` 中固定检查 ID、原文拼写和 URL，且在对应检查的 `rejected_leads` 保存原名、原文链接/正文/哈希、实际语种、排除依据及独立 Sol 裁决。`no_target_string` 的正文摘录若出现已登记检索词、源语原名或已知线索原字串，将被拒绝；即使只是搜索框回显，也须明确审核排除，不得静默当作无命中。Wikidata `uk` 空标签仅是该实体该语言字段的未命中，不能代替 UFGO 与乌克兰维基检查。

用 `negative_closure_template_sha256(record)` 先为不含对象 ID 的范围义务、边界和限制计算可登记模板哈希；用 `negative_closure_scope_sha256(record)` 再把精确对象绑定到该模板；用 `negative_closure_evidence_sha256(record)` 绑定全部实际检查及源语原名/语言/读音依据。三个哈希都不覆盖闭环审核本身，避免自引用。同一 `scope_id`/版本只在模板哈希相同的前提下代表同一范围；缩短义务会改变哈希，须重新审核。候选仍通过完整 `research_sha256` 绑定研究记录。已批准的 `generated` 候选还须有 `generated_review.decision: "approve_generated"`，其中逐项固定 `owner`、`lang`、`display_name`、`generation_rule_version`、`research_sha256`、源语原名/读音/读音来源以及与候选相同的独立审核者 ID、实际模型和时间；候选顶层 `review_conclusion` 固定为 `approved_generated_display_and_rule`，理由放入 `generated_review.reason`。候选审核时间须晚于闭环审核。仅有闭环不能导入名称。

格式校验不能从短摘录证明整页没有其他名称、从来源站点推断未索引论坛内容，或认证审核者实际身份；范围完备性、正文语种和排除理由仍须由独立审核者依据完整来源逐项核对。大手合的具体范围义务应以[定向记录](kifu-name-oteai-uk-scope.md)和其独立范围清单为准；没有该清单及哈希的实际审批工件仍属待审。

若同一个对象和语言有多条相互矛盾的研究记录，应先合成一条保留全部命中、未命中与排除理由的记录；校验器会拒绝同键多记录。冲突候选的取舍必须记录 `gpt-6-sol` 的定向裁决、来源 URL 和独立高级模型审核，普通排除文案加轻量模型签名不足以批准。

## 有限批次产物和离线校验

已链接 ID 的候选 bundle 可用 `bundle_format: 1`；新增身份或棋局关联须用 `bundle_format: 2`。两版均含 `inventory_format: 2`、清单 SHA-256、来源清单版本及哈希、`rule_version`、有限 `members`、其规范 JSON 哈希 `member_set_sha256`，以及 `candidates`。每个 member 是精确的 `owner: {kind,id}`（第二版新增对象改用 `{kind,ref}`，绝不伪造数据库 ID）加 `lang`；`raw_player/raw_event` 还必须携带与清单完全相同的 `raw_value`。每个候选须与一个 member 一一对应。名称研究记录为 JSONL；`research_sha256` 引用其中某条记录。类别决策不伪造名称检索记录，其 `research_sha256` 留空，但仍要独立审核签名和规则版。

第二版另须包含 `catalog_sha256`（所有现有棋手、赛事、别名与原始值，包括尚未关联的行）、`owners`/`owner_set_sha256`、`album_links`/`link_set_sha256`。`owners` 对已存在 ID 固定至少原名/原始值的 `preimage`，新增对象声明有限 `create`；原始值声明全局出现棋局 ID 和哈希，并独立审定分类。每条 `album_link` 固定棋局 ID、黑/白/赛事槽位、清单内完整来源与上下文哈希、原文/日期/轮次/段位/旧关联 ID、该原文全局槽位的哈希，并附独立审核的身份匹配资料；赛事还要注明命名适用时期。全局槽位由固定清单一次计算；链接可选附完整槽位数组供人工复核，省略数组时仍须精确匹配其哈希，避免高频原名生成平方级工件。**新增棋手或赛事链接必须在同一个批次附齐十一语言已审核名称**。导入仅在单个事务内分配真实 ID 和关联棋局，并在批次收据保存符号引用到真实 ID 的映射；原始 SGF、PB/PW/EV 与其他棋局元数据不改。下一批关联需针对前一批之后的新清单重新取快照和审核。真实库上线前用**同一工件哈希**在隔离正式库副本 dry-run、应用和条件撤销演练。

第二版新增原始值的 `create.category` 必须与保守解析器对该精确原文给出的类别一致，且该符号引用至少有一条与类别相容、已独立审核的显示决策（例如程序标签只能 `hidden`，占位棋手只能 `placeholder`）。类别审核签名本身不能把 `GNUGo4.0` 改称正式赛事。解析器确实误判时，先保留待审；需要另写有来源的例外规则并经独立审查后升级批次规则，不得在工件中任意覆盖类别。

```sh
python scripts/kifu_name_candidates.py validate \
  --registry docs/resource/kifu-name-source-registry.json \
  --inventory /secure/kifu-name-inventory.json.gz \
  --evidence /secure/kifu-name-research.jsonl \
  --bundle /secure/kifu-name-candidates.json
```

校验器只读文件并在标准输出报告 `approved`、`pending`、`rejected`、`missing`、重复候选、越界成员、同语同名碰撞及证据错误。只有所声明有限成员全部合法且获准时退出码为 0。**这不是全库覆盖报告**：实施计划 Task 10 必须另以真实数据库黑白棋手及赛事槽位 × 十一语言核算，并要求 100%、未审和无依据原文回退均为 0。

每条待写候选还要在独立审核前固定 `name_preimage_sha256`：该对象及语言尚无名称行时写显式 `null`，已有行则使用当前完整数据库行的规范 JSON SHA-256（包含行 ID、译名、状态、引用和时间等字段）。可用 `name_preimage_sha256(engine, owner, lang)` 只读取得；新增符号对象必须为 `null`。审核者需核对这份前像。离线报告的 `ready` 只表示名称证据合格；`write_ready` 才表示包含可写入的前像约束。`scripts/kifu_name_batch.py validate` 对 `write_ready=false` 返回非零退出码，数据库 `dry-run/apply` 还会重新读取并比较当前行。审核后发生的人工编辑或插入会使批次失败，须重取前像并重新审核，不可由导入脚本现场补上。

本地第二版小样本可运行 `pytest -q tests/web_ui/test_kifu_name_batch.py -k 'v2'`：分别演示新增原始值符号引用、同一棋局两个槽位关联、新增棋手十一语言名称以及快照失效。测试里的名称和来源是虚构 fixture，绝不可作为线上译名。

`inventory_format=2` 包含原始 PB/PW/EV 文本及已链接的棋手/赛事 ID，但不含新增原始值表 ID。离线校验只证明原文出现在固定快照；Task 7 批次导入必须在写入事务里再次核对 `raw_player/raw_event` 的声明 ID **确实指向同一个精确原文**，并验证 album/身份链接及当前正式库快照。校验器从不写数据库，也不生成所谓自动翻译。

## 发布和回滚

按清单 SHA、来源清单 SHA、规则版及有限成员集保存每个批准工件。入库前在隔离测试副本 dry-run、应用、核验原始 SGF/元数据未变，演练条件撤销。生产清单变化就重新生成批次和测试，不把旧工件扩展到新棋谱。最后报告每语种真实显示覆盖、原文回退、待审、身份冲突、赛事错分及跨语言搜索等价；缺口未清零只报告进度，不声称十一语言已完成。
