# 棋谱姓名与赛事名称审核手册

本手册用于十一语言全量核名。`en cn tw jp ko de es fr ru tr ua` 是产品语码；查资料时分别使用来源清单中的实际语言标签，尤其 `cn→zh-Hans`、`tw→zh-Hant`、`jp→ja`、`ua→uk`。全库完成的判据见实施计划 Task 10–12；某个有限批次通过校验不代表全库通过。

## 研究与命名顺序

1. 从只读 `inventory_format=2` 清单选择**互不重叠**的实体或原始值 ID × 语言。先核身份：人物生卒年代、对手、棋院资料、赛事年代和主办方。原始同形不等于同一人；年份、赛季、届次和轮次不是赛事专名。保留原始 SGF 字段。
2. 按 `kifu-name-source-registry.json` 检索目标语言的棋院/主办方及专业围棋资料，再查维基百科对应语言页和 Wikidata 精确语言标签。记录每次查询词、URL、实际正文语言、页面正文摘要和 SHA-256、访问时间、身份匹配依据。主页、目录、搜索摘要和 Wikidata 回退标签只能发现线索，不能单独证明最终名称。
3. 找到可采用的惯用名时，候选类型为 `conventional`，名称必须逐字出现在有实际目标语言正文的专业来源中。各来源互相冲突时，保留冲突和排除理由，转交疑难审核，不自动挑一个。
4. 只有目标语言范围内**所有规定来源**均完成搜索、逐项记录未命中且来源清单明确允许负面结论，才可以生成 `generated` 候选。棋手必须有可信原名、所属语言和**独立来源的读音**；中日同形文字不证明读音相同。赛事翻译要有原语言来源及组成部分依据。网络不可用、限流、反爬、空正文、语言回退或未遍历分页一律标 `incomplete`，不能视作“无通行名”。当前来源清单各语种负面范围均未完成，因此此时不会有合格的自译批准产物。
5. 清晰的泛称如“段位赛”可提交 `generic`；明确空值和程序标签可提交空显示的 `hidden`；`Unknown/Black/White` 等占位棋手用本地化“未知棋手”提交 `placeholder`；损坏原文可提交本地化 `error` 或有专业来源对应的 `corrected`。不能用这些类型隐藏真实赛事、对局叙述或未完成核名的棋手。缺失的数据库 `NULL` 赛事槽位不对应原始值表 ID，由 API/覆盖率模块用明确的空值决策处理。

## 代理与审核

重复的资料查询优先派给用户指定的 `gpt-5.6-luna`；当前平台未提供该型号时，使用 `gpt-6-luna` 并记录**实际模型名**。查询代理仅产待审证据和候选。另一名独立 `gpt-6-luna` 审核代理核对来源正文、实际语言、身份、名字与段位/结果拆分后签署常规项。证据冲突、错认风险、资料缺失、历史改名或轻量代理无把握的事项升级 `gpt-6-sol`；若 Sol 创建新候选，再由另一独立 Sol 或 Astra 审核。两级仍无法判断时保持待审，交用户或受托专业审校人员。查询代理不得审核自己的候选。

每条候选记录 `producer_id`、`producer_model`、`produced_at`，以及独立的 `reviewer_id`、`reviewer_model`、`reviewed_at`、`review_conclusion`。审核者实际比对过的来源和语种应写在结论中。待审行没有审核签名，任何脚本不得自动改为 `approved`。检索记录与候选记录以规范 JSON SHA-256 绑定；候选中的 `research_sha256` 必须与对应原始检索记录完全一致。

同一检索记录里出现不同候选名时，每个被排除的名称须在 `excluded_candidates` 留下 `source_id`、`candidate_name`、`reason`。同语言同显示名落到不同身份 ID 时，批次校验报告碰撞；只有逐人核查后在每条候选写 `collision_decision: "distinct_people_confirmed"` 和具体 `collision_basis` 才能通过。这不合并两个身份。跨批次碰撞由数据库导入/覆盖率步骤继续检查。

## 有限批次产物和离线校验

候选 bundle 为 JSON，包含 `bundle_format: 1`、`inventory_format: 2`、清单 SHA-256、来源清单版本及哈希、`rule_version`、有限 `members`、其规范 JSON 哈希 `member_set_sha256`，以及 `candidates`。每个 member 是精确的 `owner: {kind,id}` 加 `lang`；`raw_player/raw_event` 还必须携带与清单完全相同的 `raw_value`。每个候选须与一个 member 一一对应。名称研究记录为 JSONL；`research_sha256` 引用其中某条记录。类别决策不伪造名称检索记录，其 `research_sha256` 留空，但仍要独立审核签名和规则版。

```sh
python scripts/kifu_name_candidates.py validate \
  --registry docs/resource/kifu-name-source-registry.json \
  --inventory /secure/kifu-name-inventory.json.gz \
  --evidence /secure/kifu-name-research.jsonl \
  --bundle /secure/kifu-name-candidates.json
```

校验器只读文件并在标准输出报告 `approved`、`pending`、`rejected`、`missing`、重复候选、越界成员、同语同名碰撞及证据错误。只有所声明有限成员全部合法且获准时退出码为 0。**这不是全库覆盖报告**：实施计划 Task 10 必须另以真实数据库黑白棋手及赛事槽位 × 十一语言核算，并要求 100%、未审和无依据原文回退均为 0。

`inventory_format=2` 包含原始 PB/PW/EV 文本及已链接的棋手/赛事 ID，但不含新增原始值表 ID。离线校验只证明原文出现在固定快照；Task 7 批次导入必须在写入事务里再次核对 `raw_player/raw_event` 的声明 ID **确实指向同一个精确原文**，并验证 album/身份链接及当前正式库快照。校验器从不写数据库，也不生成所谓自动翻译。

## 发布和回滚

按清单 SHA、来源清单 SHA、规则版及有限成员集保存每个批准工件。入库前在隔离测试副本 dry-run、应用、核验原始 SGF/元数据未变，演练条件撤销。生产清单变化就重新生成批次和测试，不把旧工件扩展到新棋谱。最后报告每语种真实显示覆盖、原文回退、待审、身份冲突、赛事错分及跨语言搜索等价；缺口未清零只报告进度，不声称十一语言已完成。
