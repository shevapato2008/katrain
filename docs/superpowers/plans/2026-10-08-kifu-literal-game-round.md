# 赛事字面翻译 game / round 补充 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** 让既有 SGF mixed 字面翻译路径接受 parser 已保存的第N局/N局/N轮，推进五语数据交付。

**Architecture:** 仅补共享 `validate_chinese_mixed_literal_parts` 部件校验与 `validate_raw_title_research` 的 mixed 专属前置kind检查；producer、owner 与严格读端复用同一规则。保留原始 SGF/raw/parts、单 core、kind 唯一、拼接相等、150 raw 上限、完整 scope 与 CAS；不新增 profile 或正式赛事身份。

**Tech Stack:** 既有 Python、pytest、PostgreSQL 名称批次及云端 Docker 发布工具。

---

## Chunk 1: 有限规则及验收

依据独立 Astra max 决定 [资源文档](../../resource/kifu-event-literal-game-round-addendum-astra-2026-10-08.md)。同一 RO 快照新增结构候选4329 raw/5475 games，不等于已翻译或新增整卡覆盖。

**Files:**
- Modify: `katrain/web/kifu/raw_event_translation.py`
- Test: `tests/web_ui/test_kifu_raw_event_title_translation.py`
- Test: `tests/web_ui/test_kifu_raw_event_title_owners.py`

- [x] 添加真实三类回归：2016惠山古镇杯中国围乙1轮、18届韩国GG拍卖杯绅士淑女擂台赛2局、第N局实际原文；使用现有parser生成parts，不补写原文。贯通 owner prepare/dry-run、名称资格、入库与严格显示读取。
- [x] 运行新增用例确认当前因部件规则而失败，记录具体失败，不把fixture失败误作产品回归。
- [x] 最小修改：mixed路径的round允许可选第，增加game的第N局/N局；采用“旧 `_ORDINAL` 分支或新增分支”。正整数限制仅针对新增 N轮/第N局/N局，逐字锚定；旧第N轮（含原规则已接受的零值）及纯 `sgf_chinese`、其他profile不收紧。同步research的mixed专属kind入口，不能让它先拒绝game。不得用改kind来替代保留语义。
- [x] 拒绝错配kind（局标成round）、非正整数、改写parts/hash、跨profile或新增未知kind；补旧第0轮兼容与新增0轮/0局拒绝断言。复用已有scope/CAS/replay测试，不创建新审计框架。
- [x] 运行两份相关测试：`.venv/bin/python -m pytest tests/web_ui/test_kifu_raw_event_title_translation.py tests/web_ui/test_kifu_raw_event_title_owners.py -q`。预期全通过。
- [x] 独立Astra审代码及规则边界，最多两轮；修复实际阻塞问题，测试达到充分验证后停止扩张。

## Chunk 2: 发布及继续数据

- [ ] 提交并push具体代码、测试及计划，不纳入其他未跟踪文件。
- [x] 读取TEST/PROD实际运行镜像和文件SHA，保留其他会话最新发布的配置、env、挂载与静态前端；为TEST/PROD读端分别创建含新模块SHA的不可变镜像并按实际Compose服务持久发布，保留旧标签回退；只发布共享校验模块的必要差异，不整体覆盖项目或重启GPU/RK服务。
- [x] 创建新独立importer标签及build receipt，保留旧标签/历史receipt。核对TEST/PROD读端与新importer使用相同规则，健康及文件SHA通过。
- [x] 首包fresh capture BC8+GG候选145raw/211games，实际记录若变化重新冻结。source actor、真实UTC、逐盘GN/EV/SGF哈希、真实source/binder及root独立审核、显示名和来源均保存；无FK/SGF/段位/展示标签变更。
- [x] TEST dry-run→apply→verify，然后PROD同序；网络不明先查journal，不重复SQL。每批完成后报实际棋手/赛事实体/棋局覆盖率，刷新HTML阶段成果。
- [x] 原150raw/156games包与棋手五人流水线继续。此补充不暂停清晰数据交付；完成后继续高频到低频翻译。

### 独立计划审查记录

- 第1轮 Astra max指出旧数字兼容、research前置kind、读端不可变持久发布三项补充；本版均已明确。第2轮Astra max PASS，审读SHA `cccaaf9851d9edca9dd3cac9b382823f3281a7fc02605f1843576d31a2b345ce`。这仅为计划审批；代码与发布仍待实际验收。

### Chunk 1 实际验收

- 初版9项规则回归真实RED；Astra第1轮要求收窄新增数字后，4项非法数字真实RED。第2版主窗口两份suite实际 `152 passed in 9.62s`，`git diff --check` PASS；独立Astra第2轮15个纯函数边界PASS，无阻塞。模块SHA `e9122f7fe70260a97e813cb8be9529fe2759750a71311c437ae61474dcf19fc4`。两轮审核见 `docs/resource/kifu-literal-game-round-code-review-astra-2026-10-08.md`；发布和真实新grammar数据仍待Chunk2。

- Chunk2 reader/importer已按实际收据发布，记录见 `docs/resource/kifu-literal-game-round-deployed-2026-10-08.md`。GitHub两种传输均超时，commit已完成但push待重试；新grammar数据首包仍未写入，不计完成。

- Chunk2首包BC8＋GG owner493/name494两库实际应用，725严格译名与211不变SGF/FK核验，各10真实HTTP通过。进度读脚本旧616796模块漏计已更新为已发布e912，只读重算新增178盘整卡，未重跑SQL；棋手ret85／495也已两库入库，各6真实HTTP通过。最新正式库1500/3698棋手、64/85赛事实体、112603/173025整卡。后续翻译继续，不计作全库完成。
