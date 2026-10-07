# Official Hanja Retention Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在身份已闭合的韩国棋手姓名中，将官方完整汉字原样用于繁中显示，避免为相同字形重复检索繁中网页，同时诚实保存证据性质。

**Architecture:** 在现有 orthographic evidence、候选和批次验证中增加一个明确的 `official_hanja_preserved` 分支。只支持 `player` 的 `ko` 官方姓名到 `tw` 的逐码点保留；沿用独立签核、数据库前像、catalog、已核名及别名冲突检查，不改数据库结构、身份、棋局、段位或前端。

**Tech Stack:** Python、现有 kifu evidence/batch CLI、pytest、PostgreSQL。

## Design decision and authorization

用户已授权 Astra max 代做必要决策，并要求快速完成第一遍、保留权威页面、并行翻译和按五位入库。2026-10-07 独立 `/root/tw_hanja_scope_decision_astra` 实际读完 ret66 五份 KBA 正文及 hash 后，批准下列有限方案。Brainstorming 比较了继续逐人查独立 TW 网页（重复成本高）、伪装现有中文来源（不允许）、明确官方 Hanja 保留分支（采用）。该授权代替再次等待用户确认。

- 仅韩国棋院本人页明确同列完整韩文名、完整汉字名、稳定 person ID，且此 person ID 已与当前棋手身份范围闭合时使用。
- 保存真实 `ko` 来源语言、原 URL、完整捕获内容或现有可验证正文、时间、SHA、摘录、person ID 和定位；不将网页伪标为 `zh-Hant`。
- TW 显示逐码点等于原官方汉字，不使用 OpenCC、NFKC、字体异体替换或推断缺失汉字。允许记录实际兼容汉字，不对显示值做规范化改写。
- 只计入“TW 显示完成”，不得声称“台湾习称核实”或“未找到习称所以不存在”。可信既有 TW conventional 名称优先，禁止覆盖已有已核实 TW 名称。
- 崔原進已有海峰棋院繁中赛果，继续 conventional；郭圓根、任昌植、金裕撰、吳承玟可作为该分支的首批候选，仍须真绑定、冲突及独立审核。

## Chunk 1: Minimal gate and integration

### Task 1: Implement exact retention with existing controls

**Files:**
- Modify: `katrain/web/kifu/name_evidence.py` — 明确分支的官方原名 anchor，保留原中文 anchor 的严格条件。
- Modify: `katrain/web/kifu/name_orthographic.py` — 逐码点输出分支，复用成员绑定、签核时序、冲突和 catalog 检查。
- Modify only if necessary: `katrain/web/kifu/name_candidates.py`, `katrain/web/kifu/name_batch.py` 或既有 authority 同步入口，确保既有 CLI 可携带并重验此证据，不增加另一套写库流程。
- Test: `tests/web_ui/test_kifu_name_orthographic.py`，必要时现有 `test_kifu_name_evidence.py`。

- [ ] 写聚焦失败用例：官方韩文页完整 Hanja 及 person ID 可支持 TW 原样输出；source language 仍 ko。
- [ ] 写最可能的错误用例：原字被替换、缺失/不完整姓名、同人 ID 不匹配、已核 TW 名或同名别名冲突、冒充中文来源、沿用旧中文转换分支无变化。
- [ ] `.venv/bin/pytest tests/web_ui/test_kifu_name_orthographic.py tests/web_ui/test_kifu_name_evidence.py -q`，确认新用例在实现前失败。
- [ ] 最小实现：显式 retention evidence/rule 标识；旧中文规则保持原限制；姓名显示必须 exact equality；不新增逐字转换表或身份归并工具。
- [ ] 同命令通过，并仅运行与候选/批次重验相关的已有测试以确认入口集成；不扩张到全库或 UI 回归。
- [ ] 独立审查先确认设计符合，再检查代码质量及生产数据完整性边界；修复实际问题，最多两次计划审核，不做重复数据审查。

## Chunk 2: First real batch and receipts

### Task 2: Real ret66 pilot, no invented sources

**Inputs:** `/tmp/kifu-player-next5retired66-20261007/lead-summary.json` 与实际归档 `sources/*-kba.{body,json}`、两库 current.json。

- [ ] 根窗口独立读本批 source/identity binding；实施者不签核、不执行 SQL。
- [ ] 首批只用明确官方汉字四人，崔原進继续 TW conventional；完成各自另四语言正源后组合 25 个候选。
- [ ] 为首批写清 `official_hanja_preserved`、真实 ko 来源、无台湾习称/不存在习称断言；保留 URL、时间、SHA、摘录、person ID；核对 authority 同步可复用该链接。
- [ ] 对审核通过代码构建有限 importer 或必要的数据 CLI，分别在 TEST dry-run→apply→verify、PROD 同流程。根窗口 sole signer/writer，捕获前像后不并发 SQL 写入。
- [ ] 真实查询验证名称、研究依据及来源链接均保存；五位完成后统计棋手数、赛事数、完整展示棋局数和百分比。官方保留与 conventional 的方法分别列出，不把前者算成台湾习称已核实。
- [ ] 确认实际 web 名称读端已加载支持新分支的代码，并以真实名称读取验证；旧 `identity.py` 会重验 orthographic 证据，不能只更新 importer。读端未更新时沿用现有云端发布路径完成必要更新，仅更新相关 web 服务；根据 RK3562 是否在本地重验名称决定其必要更新。分别记录“数据库入库”与“线上显示”结果。
- [ ] 保存两库收据、增量 ledger 和 HTML；精确 stage 后 commit/push。

## Scope limits

不做全库转换、不改原 SGF、比赛来源列表、段位字段、玩家/赛事 ID、FK、别名或隐藏标签；不增加网页全文/生平后台、翻译服务、缓存设施或前端页面。本轮只解决现有可靠证据的重复检索瓶颈。

## Implementation checkpoint

2026-10-07：3文件最小实现；orthographic/evidence实际172项、candidate/batch实际190项通过，包含SQLite importer与identity保持兼容字码点的真实读取测试。独立FH reviewer按spec符合性→代码质量/数据完整性顺序实读方案、diff及三份KBA真实desktop页，两阶段PASS，无Critical/Important；未重复全套测试。严格本人页格式变化会拒绝处理，属于预期边界。真实ret66及webreader/importer发布尚未执行，不计本批入库完成。
