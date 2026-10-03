# 棋谱姓名与赛事名称审核手册

本手册用于十一语言全量核名。`en cn tw jp ko de es fr ru tr ua` 是产品语码；查资料时分别使用来源清单中的实际语言标签，尤其 `cn→zh-Hans`、`tw→zh-Hant`、`jp→ja`、`ua→uk`。全库完成的判据见实施计划 Task 10–12；某个有限批次通过校验不代表全库通过。

用户在 2026-10-02 明确：原有 `cn tw jp ko en` 五语优先严格核名；`de es fr ru tr ua` 六语有可靠当地围棋资料中的实际用名且身份明确时，可直接做 `conventional` 正面候选并独立复核，**不用为一个已经找到的名字继续穷尽该语种所有登记站点**。六语经合理、有记录的检索仍无当地用名时，可用已核实原名和读音做有规则的规范转写，再经独立复核。独立 `gpt-6-astra` max 已裁决采用下述 v2 有限合理范围；在相应校验器改动和测试通过前，现有严格闭环仍是实际写入闸门。十一语均须有合格显示决定，不能把六语设为机器回退或免审。

2026-10-03 用户进一步决定：某棋手若有对应目标语言的维基百科人物页面，在确认与已核实身份为同一人后，直接采用该页实际显示的姓名，不再逐站寻找更专业的同语种用名。唐韦星日语示例采用[日语页面](https://ja.wikipedia.org/wiki/%E5%94%90%E9%9F%8B%E6%98%9F)的「唐韋星」。保存页面修订版、实际语言/中文地区变体、姓名所在标题或正文、抓取记录与独立身份依据；带职业说明的消歧标题须由同页正文确认净名。资料在生日等细节上冲突时，记录冲突并定向审核同人关系；仅获批姓名，不借此批准冲突字段。页面不存在或身份不清时沿用其他来源与既定转写流程。

2026-10-02 代码总审在 `4de9e9f3` 通过：Critical/Important 均无遗留，四项重要缺陷（结构化赛事显示、SQLite 批次撤销外键、来源先于审批、跨身份同名搜索）已修复并复核；本地棋谱相关后端测试为 271 passed、1 skipped。此结论仅覆盖代码，不代表全库译名审批或上线完成。兼容迁移实测与备份见 [迁移记录](kifu-name-migration-record-2026-10-02.md)。

## 研究与命名顺序

1. 从只读 `inventory_format=2` 清单选择**互不重叠**的实体或原始值 ID × 语言。先核身份：人物生卒年代、对手、棋院资料、赛事年代和主办方。原始同形不等于同一人；年份、赛季、届次和轮次不是赛事专名。保留原始 SGF 字段。
2. 棋手优先查目标语言的维基百科人物页面；确认是同一人且页面直接显示姓名即可进入第 3 步。未命中或身份不明时，再查 `kifu-name-source-registry.json` 中的棋院、专业围棋资料及其他线索。赛事仍优先主办方和专业来源。记录 URL、实际正文语言、修订版、正文摘要和 SHA-256、访问时间、身份匹配依据。主页、目录、搜索摘要和 Wikidata 回退标签只能发现线索，不能单独证明最终名称。
3. 找到可采用的目标语用名时，候选类型为 `conventional`，名称须逐字出现在目标语言人物文章或专业来源的实际正文中。维基百科人物文章须保存版本、实际标题或直接显示净名的正文、哈希，并用独立的棋院、围棋资料或其他参考资料核对人物身份；同一人的身份依据可跨语言复用，无须再找该语种的专业姓名来源。Wikidata Q 标签仍只是文章定位线索。来源清单 `2026-10-02.2` 已将维基百科单列为 `wikipedia_article`，旧版研究哈希不会自动升级，须按新版重做证据。自动抓取只提供页面线索，文章版本和独立身份依据仍须核对并补齐。身份资料冲突时保留差异并定向复核，不自动否定或接受姓名。
   俄语 `rusgolib`（[世界棋手目录](https://rusgolib.gofederation.ru/KtoEst%27Kto/Mir.html)及各棋手个人页）属于已登记的目标语围棋资料：目录可定位候选和拉丁字母写法，个人页若有生日、棋院、经历等可加强身份核对。该站自述为协作维基，挂在联合会域名下并不意味着每条用名是联合会正式审定；有同名、转写分歧或目录待补/问号条目时再用独立棋院或其他资料消歧。目录没有某人也不构成负面检索闭环。
   吴清源样本的德/西/法语部分来源是 PDF。当前 `capture` 命令只解析 HTML，**不能**从 PDF 自动取得正文证据；可人工读取原 PDF 字节计算 `body_sha256`，逐字记录目标页正文、页码、实际语种 `observed_lang` 和 `language_basis: "reviewed_text"`，再由独立审核者对照 PDF。缺页、乱码或仅有搜索摘要时标 `incomplete`。
4. 旧 `generated` 路径仍需逐对象、逐语言的未命中闭环；原有 `cn tw jp ko en` 五语使用 v1，旧六语路径使用 v2。2026-10-03 起六语批量规范转写另走已实现的 `transliterated` 决策：绑定独立核实的原名、源语言与读音，按受审规则和有限成员生成，并复核碰撞与异常；它不声称各语惯用名不存在，也不沿用旧负面闭环。两条路径都须有可追溯的来源和独立审核。中日同形文字不证明读音相同，赛事翻译还需组成部分依据；网络限流或未命中不得伪称已穷尽。
5. 清晰的泛称如“段位赛”可提交 `generic`；明确空值和程序标签可提交空显示的 `hidden`；`Unknown/Black/White` 等占位棋手用本地化“未知棋手”提交 `placeholder`；损坏原文可提交本地化 `error` 或有专业来源对应的 `corrected`。不能用这些类型隐藏真实赛事、对局叙述或未完成核名的棋手。数据库 `NULL` 或空白 EV 槽位根本没有待翻译的来源值，API/覆盖率代码仅对该狭窄情形作明确空显示决策，无需伪造检索证据；非空真实赛事仍须获准证据。

`classification-v1` 在代码中给十一语言定义了这些类别的**待审核文案模板**。模板存在不等于译文获准上线；每种语言须由独立审核代理核对后，在候选中记录 `template_review`（版本、语言、模板 SHA-256、审核者实际 ID/模型/时间和结论），且候选本身也须有独立批准签名。校验器只接受与该版模板逐字相同的显示值；改文案须升级版本并重审，不能靠候选里任意写词来绕过来源查证。真实赛事绝不能改标泛称。

## 代理与审核

重复的资料查询优先派给用户指定的 `gpt-5.6-luna`；当前平台未提供该型号时，使用 `gpt-6-luna` 并记录**实际模型名**。查询代理仅产待审证据和候选。另一名独立 `gpt-6-luna` 审核代理核对来源正文、实际语言、身份、名字与段位/结果拆分后签署常规项。证据冲突、错认风险、资料缺失、历史改名或轻量代理无把握的事项升级 `gpt-6-sol`；若 Sol 创建新候选，再由另一独立 Sol 或 Astra 审核。两级仍无法判断时保持待审，交用户或受托专业审校人员。查询代理不得审核自己的候选。

每条候选记录 `producer_id`、`producer_model`、`produced_at`，以及独立的 `reviewer_id`、`reviewer_model`、`reviewed_at`、`review_conclusion`。审核者实际比对过的来源和语种应写在结论中。待审行没有审核签名，任何脚本不得自动改为 `approved`。检索记录与候选记录以规范 JSON SHA-256 绑定；候选中的 `research_sha256` 必须与对应原始检索记录完全一致。

同一检索记录里出现不同候选名时，每个被排除的名称须在 `excluded_candidates` 留下 `source_id`、`candidate_name`、`reason`。同语言同显示名落到不同身份 ID 时，批次校验报告碰撞；只有逐人核查后在每条候选写 `collision_decision: "distinct_people_confirmed"` 和具体 `collision_basis` 才能通过。这不合并两个身份。跨批次碰撞由数据库导入/覆盖率步骤继续检查。

## 逐对象有限未命中闭环

`negative_closure` 只批准**一个精确 `owner × lang × source_lang × scope`** 内未找到可采纳惯用名，不批准任何显示词。`ua.complete_for_negative_claims` 及其他全局标志仍为 `false`。大手合乌克兰语的已裁定范围见 [定向检索记录](kifu-name-oteai-uk-scope.md)和[独立裁决](kifu-name-oteai-uk-decision.md)；具体乌克兰语词形仍待读音/构词规则研究及独立候选审核。

v2 `negative_closure` 仅允许 `de es fr ru tr ua`，固定 `search_policy: "secondary_reasonable_v1"` 与唯一的 `bounded_scan_ids`。它沿用 v1 的对象、来源、身份、原名、独立审核、已知线索和哈希绑定；最低完成范围是一个适用的目标语 `official/language_go`，加一个目标语 `wikipedia_article/encyclopedia` 或 Wikidata 精确实体字段。`bounded_scan_ids` 所列扫描须从第 1 页连续到本次批准范围的 `page_count`，末页保留真实续页 URL、`pagination_exhausted=false`，并在 `pagination_basis` 和 `retained_limitations` 写明停止理由、剩余页面与未查渠道；未列的扫描仍须真正到终页。范围内所有页面均须实际读取，已知线索不得因限页而消失。v2 的策略、限页 ID 和未查来源 ID 进入模板/范围/证据哈希；v1 哈希和已归档工件保持不变。两版闭环都不自动批准具体转写词，后续仍需独立 `generated_review`、原名/读音及命名规则依据。

v2 另需 `unsearched_source_ids`：精确列出来源登记中未由目标语完整检查覆盖的来源 ID；每个 ID 也须写入 `retained_limitations`。限页末页的检查须附 `continuation_href` 和从该页原始正文摘出的 HTML 链接 `continuation_excerpt`，链接解析后须等于 `next_page_url`；限制说明同时写明扫描 ID 与该续页 URL。以 Wikidata 未命中作为第二来源时，目标语请求的正文摘录须为可解析 JSON，含所查 QID，且该目标语的 label、alias、sitelink 均不存在；再用 `entity_identity_evidence` 保存同一 QID 的源语 label 请求 URL、采集时间、HTTP 状态、响应 SHA-256、JSON 摘录和身份依据，源语 label 须等于研究记录的已核实原名。闭环审核时间必须晚于这份身份证据采集。格式校验只核对已提交证据的一致性，独立审核者仍须比对受控原始正文与身份、续页和停止理由。

在研究记录中写 `source_lang`（必须等于有来源证明的 `original_language`）和 `negative_closure`。闭环字段为 `version: 1`、精确 `owner`、产品语码 `lang`、`source_lang`、`scope_id`/`scope_version`、`registry_sha256`、`required_check_ids`、`required_checks`、`known_leads`、文字 `scope_boundary`、明确保留的 `retained_limitations` 列表、`scope_sha256`/`evidence_sha256`、独立审核者实际 `reviewer_id`/`reviewer_model`/`reviewed_at`、`conclusion: "approved_not_found_in_scope"` 及具体 `reason`。`scope_boundary` 应列清页面、检索词、分页和实体字段；未索引论坛、不可取得的出版物等写入限制，不得记为已查完。来源清单的该语种必查专业/百科/Wikidata 来源必须全部由闭环的检查覆盖。

`required_checks` 是由独立审核者先核定的**范围义务**，不能从实际检查倒推生成。每项固定 `check_id`、`source_id`、`method`、完整查询词、精确 URL（含参数）、`searched_forms`、`entity_field_scope`、`scan_id`、`page_index`/`page_count`、`next_page_url`、`pagination_exhausted` 和 `pagination_basis`。同一 `scan_id` 的页码必须从 1 连续到总页数；末页明确无续页，前页指向清单中的下一页。Wikidata 实体检查固定 QID、请求语言和 labels/aliases/sitelinks 字段。观察记录的对应字段须逐项等于义务，并另存 `fetched_at`、实际正文 `observed_lang` 与 `language_basis`、`response_sha256`、`body_sha256` 和正文摘录，标 `status: "not_found"`、`completeness: "complete"`、`scope_complete: true`、`search_scope`，以及 `negative_outcome: "no_target_string"` 或 `"rejected_leads"`。`partial/unavailable` 不能进入已批准闭环。

范围内的俄语页面可以作为额外的已查页面保留真实语种，但每个登记必查来源仍须至少有一次目标语种的完整检查。已知俄语论坛命中等在 `known_leads` 中固定检查 ID、原文拼写和 URL，且在对应检查的 `rejected_leads` 保存原名、原文链接/正文/哈希、实际语种、排除依据及独立 Sol 裁决。`no_target_string` 的正文摘录若出现已登记检索词、源语原名或已知线索原字串，将被拒绝；即使只是搜索框回显，也须明确审核排除，不得静默当作无命中。Wikidata `uk` 空标签仅是该实体该语言字段的未命中，不能代替 UFGO 与乌克兰维基检查。

用 `negative_closure_template_sha256(record)` 先为不含对象 ID 的范围义务、边界和限制计算可登记模板哈希；用 `negative_closure_scope_sha256(record)` 再把精确对象绑定到该模板；用 `negative_closure_evidence_sha256(record)` 绑定全部实际检查及源语原名/语言/读音依据。三个哈希都不覆盖闭环审核本身，避免自引用。同一 `scope_id`/版本只在模板哈希相同的前提下代表同一范围；缩短义务会改变哈希，须重新审核。候选仍通过完整 `research_sha256` 绑定研究记录。已批准的 `generated` 候选还须有 `generated_review.decision: "approve_generated"`，其中逐项固定 `owner`、`lang`、`display_name`、`generation_rule_version`、`research_sha256`、源语原名/读音/读音来源以及与候选相同的独立审核者 ID、实际模型和时间；候选顶层 `review_conclusion` 固定为 `approved_generated_display_and_rule`，理由放入 `generated_review.reason`。候选审核时间须晚于闭环审核。仅有闭环不能导入名称。

格式校验不能从短摘录证明整页没有其他名称、从来源站点推断未索引论坛内容，或认证审核者实际身份；范围完备性、正文语种和排除理由仍须由独立审核者依据完整来源逐项核对。大手合的具体范围义务应以[定向记录](kifu-name-oteai-uk-scope.md)和其独立范围清单为准；没有该清单及哈希的实际审批工件仍属待审。

若同一个对象和语言有多条相互矛盾的研究记录，应先合成一条保留全部命中、未命中与排除理由的记录；校验器会拒绝同键多记录。冲突候选的取舍必须记录 `gpt-6-sol` 的定向裁决、来源 URL 和独立高级模型审核，普通排除文案加轻量模型签名不足以批准。

## 有限批次产物和离线校验

已链接 ID 的候选 bundle 可用 `bundle_format: 1`；新增身份或棋局关联须用 `bundle_format: 2`。两版均含 `inventory_format: 2`、清单 SHA-256、来源清单版本及哈希、`rule_version`、有限 `members`、其规范 JSON 哈希 `member_set_sha256`，以及 `candidates`。每个 member 是精确的 `owner: {kind,id}`（第二版新增对象改用 `{kind,ref}`，绝不伪造数据库 ID）加 `lang`；`raw_player/raw_event` 还必须携带与清单完全相同的 `raw_value`。每个候选须与一个 member 一一对应。名称研究记录为 JSONL；`research_sha256` 引用其中某条记录。类别决策不伪造名称检索记录，其 `research_sha256` 留空，但仍要独立审核签名和规则版。

第二版另须包含 `catalog_sha256`（所有现有棋手、赛事、别名与原始值，包括尚未关联的行）、`owners`/`owner_set_sha256`、`album_links`/`link_set_sha256`。`owners` 对已存在 ID 固定至少原名/原始值的 `preimage`，新增对象声明有限 `create`；原始值声明全局出现棋局 ID 和哈希，并独立审定分类。每条 `album_link` 固定棋局 ID、黑/白/赛事槽位、清单内完整来源与上下文哈希、原文/日期/轮次/段位/旧关联 ID、该原文全局槽位的哈希，并附独立审核的身份匹配资料；赛事还要注明命名适用时期。全局槽位由固定清单一次计算；链接可选附完整槽位数组供人工复核，省略数组时仍须精确匹配其哈希，避免高频原名生成平方级工件。**新增棋手或赛事链接必须在同一个批次附齐十一语言已审核名称**。导入仅在单个事务内分配真实 ID 和关联棋局，并在批次收据保存符号引用到真实 ID 的映射；原始 SGF、PB/PW/EV 与其他棋局元数据不改。下一批关联需针对前一批之后的新清单重新取快照和审核。真实库上线前用**同一工件哈希**在隔离正式库副本 dry-run、应用和条件撤销演练。

此十一语要求同样适用于链接到**已有 ID** 的棋手或赛事，旧 `verified` 行不能代替本批的独立批准。每个链接的 `identity_review` 还须有 `scope_frozen_at` 和 `scope_sha256`：先固定目标声明、规则、清单及 catalog 哈希、精确原文所属的全部拟写槽位、完整棋局上下文及来源核对，再由独立审核者签署该范围哈希；审核时间必须晚于冻结时间。验证器按目标及精确原文分组重新计算哈希，要求组内共用同一审核决定。增删槽位、改目标、上下文或证据都会使旧批准失效，必须重新冻结和审核。哈希是受控审核产物的核对值，不是自动核实身份的证明；审核者仍须检查全部异常和适用范围。试点边界见[精确原名关联裁决](kifu-name-exact-link-policy-2026-10-02.md)。

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

可写候选另需 `preimage_binding`：`actor_id`/实际 `actor_model`、带时区的 `captured_at`/`bound_at`、与顶层完全一致的 `name_preimage_sha256`（允许显式 `null`）。来源候选的 `producer_id`/`produced_at` 和 `research_sha256` 保留原作者与原证据；后来绑定前像的人只写在 `preimage_binding`，不能冒充来源作者。不同人绑定时还需 `source_candidate_sha256` 指向归档来源候选的规范哈希；有受控前像文件时记录其原始字节 `capture_sha256`。两个哈希均须为小写 SHA-256，审核人还须对照归档文件实际核实，格式校验不能自行证明引用真实。写入闸要求来源候选先于绑定，前像采集不晚于绑定，绑定不晚于新审核，且审核人与来源作者、绑定人各不相同。旧来源审核可作为历史依据，但不能批准其后才采集的前像；要保留旧候选不变，复制成待审的生产绑定产物并重新独立审核。来源证据的 `ready` 校验不受该写入专用元数据影响。

本地第二版小样本可运行 `pytest -q tests/web_ui/test_kifu_name_batch.py -k 'v2'`：分别演示新增原始值符号引用、同一棋局两个槽位关联、新增棋手十一语言名称以及快照失效。测试里的名称和来源是虚构 fixture，绝不可作为线上译名。

`inventory_format=2` 包含原始 PB/PW/EV 文本及已链接的棋手/赛事 ID，但不含新增原始值表 ID。离线校验只证明原文出现在固定快照；Task 7 批次导入必须在写入事务里再次核对 `raw_player/raw_event` 的声明 ID **确实指向同一个精确原文**，并验证 album/身份链接及当前正式库快照。校验器从不写数据库，也不生成所谓自动翻译。

已审核第二个 GN 的选择进入 `inventory_format=3` 后，赛事分组清单按逐盘有效赛事原文计算，仍只输出待审核组。该格式的内部 `inventory_sha256` 不可单独用于离线证明选择补充未被改写；生成 v3 赛事分组时须从独立保存的完整清单取得**规范 JSON SHA-256**，传给 `scripts/kifu_name_groups.py --expected-inventory-artifact-sha256 ...`。生成器核对整个清单内容并把该外部摘要写入分组工件；旧 v2 分组命令保持兼容。审核人还须核对外部摘要来自冻结的原清单，不能从被审核者现场提交的改后文件重新计算当作独立批准。

## 发布和回滚

按清单 SHA、来源清单 SHA、规则版及有限成员集保存每个批准工件。入库前在隔离测试副本 dry-run、应用、核验原始 SGF/元数据未变，演练条件撤销。生产清单变化就重新生成批次和测试，不把旧工件扩展到新棋谱。最后报告每语种真实显示覆盖、原文回退、待审、身份冲突、赛事错分及跨语言搜索等价；缺口未清零只报告进度，不声称十一语言已完成。
