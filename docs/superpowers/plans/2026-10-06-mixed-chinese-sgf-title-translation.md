# 有限中文混合赛事标题 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** 复用既有可追溯入库流程，安全支持含ASCII品牌字母和期／无第届次的中文赛事原文，扩大五語真实覆盖。

**Architecture:** 新增显式 `sgf_chinese_mixed` profile，旧profile保持原限制；所有原parsed parts、完整scope、manifest、owner marker及事务边界复用。每个有限批独立翻译与签审，实际TEST→PROD写入后才统计；不重新解析或建立赛事身份。

**Tech Stack:** 现有Python纯验证器、SQLAlchemy/PostgreSQL、有限CLI与Docker运行镜像；无新依赖或schema。

**Design:** [已提出设计](../specs/2026-10-06-mixed-chinese-sgf-title-design.md)。独立[决策](../../resource/kifu-next-high-coverage-decision-2026-10-06.md)。用户已授权Astra代理决策；设计／计划独立审查最多2轮。

---

## Chunk 1: 有限profile接线

### Task 1: 聚焦RED检查

**Files:**
- Modify: `tests/web_ui/test_kifu_raw_event_title_translation.py`
- Modify: `tests/web_ui/test_kifu_raw_event_title_owners.py`

- [x] 用现有fixture添加明确新profile的真实标题形态：`KB国民银行杯2012韩国围乙联赛`、`第2期日本幽玄杯精锐循环赛`、`3届韩国最强棋手战循环圈`。parts采用捕获原文的现存形态，而不是为测试重写业务解析。
- [x] 证明新profile尚不能通过，记录一次RED命令／结果。
- [x] 小组拒绝用例覆盖旧profile仍拒绝新形态、纯Latin、未知或跨profile marker、重复kind／多core、非lossless／改变parts hash。复用已有缺成员、已有名／链接／选择及重放检查，不增加新的审计框架。

Run: `PYTHONPATH=. .venv/bin/python -m pytest tests/web_ui/test_kifu_raw_event_title_translation.py tests/web_ui/test_kifu_raw_event_title_owners.py -q`。

### Task 2: 最小实现

**Files:**
- Modify: `katrain/web/kifu/raw_event_translation.py`
- Modify: `scripts/kifu_raw_event_title_owners.py`

- [x] 添加 `SGF_CHINESE_MIXED_PROFILE = "sgf_chinese_mixed"` 与独立窄校验器；保留现有中文字符集合并增加 `[A-Za-z]`，必须含汉字。仅edition增加原有 `第?N(?:届|屆|期)`；round仍使用旧规则。一个core、唯一kind、原parts完全拼回raw。
- [x] 纯research validator的共同ordinal检查在已明确的SGF新profile内选择对应规则；其余旧入口保持旧语法。新profile research绑定真实完整scope/source/first-GN及原parts hash。
- [x] `sgf_literal_owner_matches` 要求research.profile与批准owner marker.profile准确一致，并校验原parts；未知profile、缺marker及旧／新互换必须拒绝。
- [x] Owner脚本扩展显式profile选项，复用原最多150条、唯一raw/set hash、完整未命名公共NULL scope、preimage/hash、审批身份、dry/apply/verify和重放规则；marker记录实际选择的profile。没有fresh manifest不能执行。
- [x] 运行上述两个测试文件至GREEN。只处理本次行为及最可能回归，原profile与national15兼容也由这组既有用例证明。
- [x] 独立代码review（实施者之外），修正实际问题至通过。无需无关全库测试或新基础设施。
- [x] root按准确改动路径commit，记录测试／review；不把其他未跟踪文件混入提交。

## Chunk 2: 真实来源、部署与入库

### Task 3: 有限来源包

**Files:**
- Create data packet: `/tmp/kifu-event-title-mixed150a-20261006/`（确切条数由实际候选决定）
- Update progress: `docs/resource/kifu-name-incremental-resume-2026-10-05.md`
- Update report: `docs/resource/kifu-five-language-progress-2026-10-05.html`
- Archive actual evidence/receipts: `docs/resource/kifu-incremental-applied-2026-10-05/`

- [ ] 独立producer从全库grouped frequency高→低选≤150候选，仅实际public NULL／nonhidden／nonduplicate／unselected／unnamed；跳过疑似损坏原文与实体碰撞，不修改译词绕过。
- [ ] 读取两环境当前owner、原parts、全部SGF first GN／EV／source／SHA及完整scope，冻结raw set／matrix／research／registry。一个core仅翻译一次并复用年份轮次；采用来源URL／摘录／时间／body SHA随evidence入库，literal SGF不声明外部权威核实。
- [ ] root读core与实际scope／来源，批准准确有限owner计划。来源producer与root reviewer保持分离；root唯一数据库writer。

### Task 4: 必要部署与真实验收

- [x] 对现有TEST镜像保留endpoint、identity、缓存及配置，仅更新必要纯验证器／importer代码；核对运行文件SHA与健康。读取并遵循现有server-deploy流程，不无故重建无关服务。
- [ ] TEST准确owner dry-run→apply→verify；由实际独立producer捕获批准afterimage，绑定pending五語names；root签审后names dry-run→apply→verify。
- [ ] 确认两种reader对整个实际scope一致、原SGF／段位／FK／identity零改动；代表性的品牌字母、期／届两种分段实际五語显示／精确搜索及英语回退。一次旧profile代表性真实查询证明旧数据仍可读取；无需全状态重拍。
- [ ] TEST通过后发布相同审核代码到PROD，走同样精确owner／names流程与实际验收；不只凭测试成功宣布上线。
- [ ] 读取真实PROD覆盖率、更新HTML／完成名单／每批报告；保存冻结source、审批、afterimages、两库真实receipts并git commit/push。2,979候选上限或重复scope不得当作新增完成。
- [ ] 如需要放宽到多core、纯Latin或通用parser，删除对应候选并继续本有限范围；不扩大本切片。

## 工作分配与持续推进

两名Luna继续棋手资料批次，Sol实施这一小补丁及后续来源包，root负责审核和串行实际数据库写入。独立Astra按用户授权确认设计／计划（至多2轮），再审查代码边界。g／DK／DL在途包先完成，不因新profile设计停下。翻译主语言仅五种；保持来源角色与实际完成统计诚实。

## 实际实现与审核记录

2026-10-06：Sol实际RED 10 failed / 113 passed；GREEN 127 passed in 10.22s。独立Astra第1轮代码审核APPROVE，无must-fix，并独立运行127 passed in 10.31s。审核记录见[独立代码审核](../../resource/kifu-mixed-title-code-review-2026-10-06.md)。root核对四文件diff SHA与审核记录一致；当前提交仅完成Chunk1，新profile尚未部署、候选未计为完成。

2026-10-06实际部署准备：两库importer已构建并检查显式profile导入；TEST→PROD web仅COPY共享pure一文件，运行SHA `616796e1b51b9f5afed877a3365d24e5c53d1a48abcc4100254cd41f2dafd70d`，保留实际15/16层Compose与原env路径。两端健康且既有g profile各16 HTTP通过。PROD使用原有sudo -n读取受保护env路径，未打印/改动env。新profile尚无新数据获批或激活，因此不计五语覆盖；混合来源、TEST→PROD owner/name及新数据HTTP仍待后续。报表两reader的内嵌pure同步到相同已审且已部署字节，避免新profile未来漏计。
