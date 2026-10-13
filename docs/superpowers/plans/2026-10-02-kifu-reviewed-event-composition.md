# 棋谱赛事届次审核组合 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把已核实的赛事基础名与经独立审核的逐语言届次规则组合为完整、已存储的原始赛事显示名；先让本因坊 `1st Honinbo` 至 `34th Honinbo` 的 374 个名称安全通过现有审核、导入与覆盖闸门。

**Architecture:** 保留现有 `event` 身份、`raw_event` 原文、来源证据及严格显示表。新增范围受限的 `composed` 名称决策和版本化纯数据规则；离线校验器验证基础名、届次、范围、来源和独立签署并逐字节复算，导入器存储 374 条完整译名。API 与覆盖率只读取满足依赖条件的已批准名称，不在请求时翻译或拼接。

**Tech Stack:** Python、SQLAlchemy、PostgreSQL、FastAPI、pytest；正式库快照与隔离测试副本。

**Spec:** [独立决策](../../resource/kifu-name-honinbo-reviewed-composition-decision-astra-2026-10-02.md)，[全量方案](../specs/2026-10-02-kifu-full-name-localization-design.md)，[全量计划](2026-10-02-kifu-full-name-localization.md)。本计划只增加本因坊届次切片，不降低全库 11 语言、黑白棋手及赛事三槽位 100% 发布门槛。首次代码实现遵循 `@superpowers:test-driven-development`，完成后遵循 `@superpowers:requesting-code-review` 和 `@superpowers:verification-before-completion`。

**并行边界：** 逐语言资料研究可与代码实现并行；相同规则的生产者和审核者须是不同代理；代码文件同一时刻只由一个实现者修改。正式库只读，直到全库发布闸门满足。

## Chunk 1：受限组合契约与语法来源

### Task 1：冻结有限范围和十一条逐语言规则

**Files:** Read `docs/resource/kifu-name-honinbo-ordinal-source-research-2026-10-02.md`, `docs/resource/kifu-name-honinbo-raw-event-display-preview-2026-10-02.md`, protected inventory/group/base evidence; create protected rule and source records under `~/.local/share/kifu-name-audit/2026-10-02/`; summarize in `docs/resource/kifu-name-honinbo-composition-rule-review-2026-10-02.md`.

- [ ] 固定 34 个完整原文、各自唯一届次 1–34、1,617 个赛事槽位、34 个全局 occurrence/scope 哈希；记录当前 inventory、catalog、已签 11 基础名工件哈希。为 34 个原文各声明一个 `raw_event` owner，保留解析类别 `unclassified_pending`，逐 owner 列出完整 occurrence IDs/hash 和独立 `category_review`；另一代理逐条核对“精确原文 → 届次 → 本因坊系列”及全部出现范围。只允许精确原文成员，拒绝未列出的近似拼写。
- [ ] Luna 分语言补齐 `tw ko es fr ru ua tr` 的正文或权威语法依据；保存实际 URL、正文语种、采集时刻、正文 SHA-256、确切摘录和应用理由。`en cn jp de` 也形成显式规则记录；不得从另一种语言的网页推定本语言语法。
- [ ] 为每语种规则记录基础名候选哈希、系列身份、数字单位/词序/空格/大小写、渲染器版本、来源哈希、生产者和时间。单独计算规则正文哈希，审核签署不进入正文哈希；候选再绑定整个获批规则哈希。
- [ ] 不同代理独立审核 11 条规则，特别复核 1/17/34、英语 2/3/11/12/13/21/22/23/31/32/33、法语第一届及实际变格。缺来源或分歧的规则保持 pending，不生成批准候选。

### Task 2：最小渲染器与组合候选校验

**Files:** Create `katrain/web/kifu/name_composition.py`, `tests/web_ui/test_kifu_name_composition.py`; modify `katrain/web/kifu/name_candidates.py`, `tests/web_ui/test_kifu_name_candidates.py`.

- [ ] 先写失败测试：仅已冻结 `Honinbo` 34 个精确原文、11 个语言和获批基础名/规则可组合；无效或错配序数、遗漏/额外 occurrence、额外 raw、错误系列、错误语种、改变基础名/规则/范围哈希、缺独立审核、旧签名、重复或碰撞均拒绝。`parse_event` 的 `unclassified_pending` 保持不变，不能进入 Oteai 特例。
- [ ] 运行 `pytest -q tests/web_ui/test_kifu_name_composition.py tests/web_ui/test_kifu_name_candidates.py`，确认新断言先失败。
- [ ] 实现纯数据、白名单操作的逐语言届次渲染；不执行任意模板表达式。候选使用 `decision_kind=composed`、空 `research_sha256`、精确 raw owner/value/lang/display、基础候选哈希、批准规则哈希、整数届次和 raw 范围哈希。校验器逐字节复算 374 项且强制 34×11 完整集合；`conventional` 和 `generated` 原有条件不变。
- [ ] 重跑聚焦测试，加入一个改动已批准基础名或规则后校验失败的回归用例；运行原有 generated/conventional 检查并提交本任务代码。

## Chunk 2：导入证据与运行时一致性

### Task 3：现有表内保存依赖与条件撤销

**Files:** Modify `katrain/web/kifu/name_batch.py`, `katrain/web/kifu/name_evidence.py` (仅确需处), `tests/web_ui/test_kifu_name_batch.py`; no schema migration.

- [ ] 先写失败测试：导入已批准基础名和 374 条组合名后，证据 JSON 保留规则及依赖哈希、解析后的系列 ID/基础 evidence ID/版本；签署候选对象不被导入器重写。缺语言、缺前像字段、与实库不符的旧前像及跨 bundle 同语碰撞拒绝；真实采集证明名称行不存在时必须允许显式 `null` 前像。分别覆盖合法 null、缺字段和采集后新增行；事务失败全回滚。
- [ ] 运行 `pytest -q tests/web_ui/test_kifu_name_batch.py tests/web_ui/test_kifu_name_composition.py`，确认失败；实现仅对 `raw_event` 的 `composed` 分支，基础名先于组合名写入，复用现有日志和锁内前像比较。
- [ ] 验证重复应用零新增；条件撤销只回滚本批触及的行/链接，后续人工修改列冲突，其他批次的基础名和关联仍在。重跑测试并提交。

### Task 4：同一严格资格判定用于 API、搜索和覆盖率

**Files:** Modify `katrain/web/kifu/identity.py`, `katrain/web/kifu/name_coverage.py`, `katrain/web/api/v1/endpoints/kifu.py` (仅现有查询无法传递资格时), `tests/web_ui/test_kifu_name_api.py`, `tests/web_ui/test_kifu_name_coverage.py`.

- [ ] 先写失败测试：已批 `composed` 名称只有在 raw owner、该语名行/证据版本、已批基础名及棋局赛事链接全部匹配时显示与搜索；pending、缺语种、断开/改变基础依赖、错误系列均为覆盖缺口，不能退回基础名或原文。检查结果与 API 显示同口径。
- [ ] 运行 `pytest -q tests/web_ui/test_kifu_name_api.py tests/web_ui/test_kifu_name_coverage.py` 确认失败；在当页批量查询中加入所需依赖字段和共同资格判定。请求期不运行渲染器、网络调用或逐棋局证据查询。
- [ ] 聚焦测查询次数、搜索和覆盖率一致性；重跑两套测试并提交。

## Chunk 3：有限数据包、审查与隔离验收

### Task 5：签署 374 条名称并进行隔离库演练

**Files:** Protected candidate/bundle JSON under `~/.local/share/kifu-name-audit/2026-10-02/`; summary `docs/resource/kifu-name-honinbo-composition-import-rehearsal-2026-10-02.md`.

- [ ] 在规则独立审核全部 PASS 后，Luna 用冻结 34 原文和规则机械生成 374 候选；独立审核者复算所有值、语法样本、来源与跨名碰撞，并签署完整集合。另一个绑定者从当前库只读捕获每条 raw owner/名称行的完整前像；新行显式钉住不存在。独立最终审核者检查时间顺序和前像后再签最终候选。最终同批工件包含 1 个赛事 owner、34 个 raw owner、11 条基础名、374 条组合名以及 1,617 条已审关联；不改已有身份审核载荷。
- [ ] 将基础名、链接与 374 条组合名合成**一个**最终工件并冻结哈希；使用精确 registry、inventory、catalog 和研究/规则输入执行 `scripts/kifu_name_candidates.py validate`，要求整个工件 `approved=385`（其中组合名 374）、`pending=0`、`errors=[]`、`write_errors=[]`、`ready=true`、`write_ready=true`。记录文件和规范哈希，隔离演练必须使用这个同一哈希；不把只校验 374 条名称视为可写批准。
- [ ] 先在隔离库运行 validate/dry-run/apply、重复 apply 和条件 undo；核对 1,617×11=17,787 个赛事显示槽位、原 SGF/原文/日期/轮次完全不变。播放器两侧仍单独计入全库缺口；隔离通过不授权正式库写入。
- [ ] 对最终代码运行 `pytest -q tests/web_ui/test_kifu_name_composition.py tests/web_ui/test_kifu_name_candidates.py tests/web_ui/test_kifu_name_batch.py tests/web_ui/test_kifu_name_api.py tests/web_ui/test_kifu_name_coverage.py`。派独立代理先做需求符合性审核再做代码质量审核；修复后复核直到通过，记录确切测试与剩余缺口，提交并推送功能分支。

**发布边界：** 全库 11 语种三槽位实际合格覆盖未达 100% 前，不合并到 `develop`、不开正式 strict 模式、不写正式名称数据或部署这一切片。
