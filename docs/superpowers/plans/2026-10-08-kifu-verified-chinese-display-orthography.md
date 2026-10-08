# 已核中文姓名的繁体显示 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** 为已有合格 CN 显示名的外国棋手提供有依据、诚实标记为 generated 的 TW 字形显示，减少逐人重复检索。

**Architecture:** 在现有 primary-orthographic-v1 中加入明确的 verified_chinese_display 锚点；保持旧中文原名和官方 KBA Hanja 分支原有门槛。复用有限规则、完整姓名审定、源与目标前像、批次证明及读端校验；不建新表或转换服务。仅先处理四个干净姓名，5410 已有真实 TW 来源走原有 conventional 入库队列。

**Tech Stack:** Python、现有 SQLAlchemy 导入器、PostgreSQL、pytest。

---

## Chunk 1: 最小证据分支及实际入库

授权说明：`/tmp/kifu-han-script-firstpass-astra-decision-20261008.md`（独立 Astra/max）；本计划不能替代具体候选审批。

首批拟定 P6752 塙保时→塙保時、P6765 加纳一夫→加納一夫、P6768 金井新一→金井新一、P5365 泉谷实→泉谷實。实际 TEST ID 单独匹配。只允许 player、CN→TW、源 CN 已合格且目标 TW 缺失。姓名原语言不变，不冒称台湾刊载。中文 canonical、verified 状态标签或 SGF 汉字外观不能独自作为证据。升／昇不得自动处理；保持当前异常字过滤与已知冲突检查。

### Task 1: 扩展现有 orthographic 锚点

**Files:**
- Modify: `katrain/web/kifu/name_evidence.py` (`validate_primary_orthographic_anchor`)
- Modify: `katrain/web/kifu/name_orthographic.py`（有限规则验证与持久化证明）
- Modify as necessary: `katrain/web/kifu/name_candidates.py`（源 CN 前像/合格证明绑定）
- Test: `tests/web_ui/test_kifu_name_orthographic.py`

- [x] 先用现有 fixture 添加一个日本棋手、已合格 CN 显示名、缺失 TW 的最小候选。新锚点 `reference_kind=verified_chinese_display` 精确绑定同 owner 的源 CN 完整行及 evidence/batch 证明，不设置 chinese_origin=True、不伪造 official_person。
- [x] 运行新测试确认旧门拒绝新输入：`.venv/bin/python -m pytest tests/web_ui/test_kifu_name_orthographic.py -k verified_chinese_display -q`。
- [x] 实现最小分支：源语言固定 zh-Hans/Hans，目标固定 tw/Hant；输入 original_name 必须等于被绑定 CN display_name，校验源 CN 为当前真实合格显示名。复用原实际来源及证明，不要求新 TW 来源，不新增 reading/negative_search。
- [x] 来源行证据完整性：不能仅检查源状态；沿现有合格 reader/gate 验证完整 name/evidence/必要 batch。源本分支强制仅接受同 owner 当前已合格 conventional CN（源 name/evidence 的 decision、revision、display 与现有资格证据一致），拒绝生成、转写、正字法等递归输入，不开放证明链。来源角色、原页面语言保留实际值。
- [x] 使用已有逐字方向规则和完整输出审定，规则涵盖姓名全部字符（包括原样保留字符），保留异常字与碰撞拒绝。字形不变也记录 generated。未知 reference_kind 必须拒绝；旧分支不得因新分支放宽。

### Task 2: 导入 CAS 与读取证明

**Files:**
- Modify: `katrain/web/kifu/name_batch.py`（仅若既有逻辑未覆盖源 CN 前像重查）
- Modify: `katrain/web/kifu/identity.py`（复用创建日志识别，重验原始方法与证明，不新造回退）
- Test: `tests/web_ui/test_kifu_name_orthographic.py`

- [x] 在真实导入事务内重查源 CN 完整前像与合格证明，以及目标 TW NULL/absence CAS。源改动、源证据失效或 TW 后填均拒绝，不写 CN/JP/KO/EN、ID、FK、别名、段位、SGF。
- [x] 将精确源证据和批次绑定随现有 journal 保存，读端重验不可被去掉 subtype、改 owner/源值/证明后冒充普通名字；复用创建日志识别此分支，测试 name/evidence/candidate 的生成标记及 primary_orthographic payload 被协同移除后仍拒绝降级。限定同 owner，CN→TW。
- [x] 测试一个完整的候选验证→dry-run→apply→qualified readback；测试 review/fallback 输入、异主源、源前像漂移、目标已有值、改持久化证明、方向错和升／昇歧义的拒绝。复用现有 fixture/测试层，避免新审计框架。
- [x] 运行聚焦文件及仅相关现有用例：`.venv/bin/python -m pytest tests/web_ui/test_kifu_name_orthographic.py -q`；必要时添加 name_candidates/name_batch/identity 中实际受影响的特定用例。无需全量 UI/GPU 回归。
- [x] 交独立 code-review agent 审查所有产品改动；修复实际问题后通过。最多两轮独立 Astra 计划审核；不扩张无关功能。

### Task 3: 发布并推进已有翻译队列

- [ ] Root 显式提交计划及通过审查的产品文件，记录聚焦测试实际结果。
- [ ] 仅部署 importer 和实际云端读取需要的代码到 TEST，做四姓名中的一个真实候选导入及接口读取；通过后部署 PROD。数据按各环境真实前像独立签审，不混用 ID。
- [ ] 四个完整姓名按固定规则一次审定，保留 generated 方法和真实来源，不计为台湾刊载习称；实际两库应用与 reader 合格才更新覆盖率。
- [ ] 每批数据库写入后立即更新真实统计与 HTML 清单。继续已审 148/149/151 及 B/C 赛事标题队列；该代码分支不得阻塞已有可入库内容。

验收：已有合格 CN conventional 来源可生成明确审定的 TW 显示，旧分支行为保持；证据/前像不合格不能写入或计数；两库和实际接口证明后诚实报告覆盖率。

计划审核：独立 Astra/max 第 1 轮提出两项必要修订，已强制 conventional 源并明确创建日志防协同降级；第 2 轮 PASS；实现已通过 86 项聚焦测试、独立 spec 与 code review，部署验收待执行。
