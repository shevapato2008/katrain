# Positive Japanese-to-Korean Name Generation Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** 用已核本人日文读音、NIKL 规则和实际冲突查询生成韩文显示名，诚实保存资料，减少历史棋手重复证明“没有译名”的工作。

**Architecture:** 只在现有 research/candidate 及同一读端重验路径添加 `normative_ja_ko_v1` 正面证据分支。限定已有 player ID、ja 输入、ko 输出、`nikl-ja-ko-personal-name-v1`，沿用逐名独立审核、研究哈希、前像、整批冲突、TEST→PROD、undo。CN/TW 原文显示不冒充已核译名，本次不新增其生成规则、数据库表或通用音译器。

**Tech Stack:** 现有 Python evidence/batch 模块、pytest、PostgreSQL、云端有限 importer/web overlay。

## Authorization and proportionality

用户授权 Astra/max 代决策、快速完成首轮和并行翻译。独立 `/root/bulk_player_identity_decision_astra` 已实际核 ret73 源及 NIKL 三页，裁决见 [政策备忘录](../../resource/kifu-first-pass-japanese-name-decision-2026-10-07.md)。替代方案包括继续三站负面闭环（重复且容易被网络失败阻塞）、把原文当译名（不采用）、限定正面规范生成（采用）。本方案不把 403 当作缺少通行用名，不放宽其他规则。

当前在已隔离的 `feature/kiosk-go-kifu` 工作目录执行；root sole signer/SQL writer。来源研究、只读绑定与实现可以分工；同一文件仅实现者修改。不得借此重写 reader/ORM、建立新服务或做全库回归。

## Chunk 1: One explicit evidence path

### Task 1: Validate positive original reading and exact generated review

**Files:**
- Modify `katrain/web/kifu/name_evidence.py`: 加入限定 scope 和正面证据验证，复用现有 capture/body/hash/时间验证。
- Modify `katrain/web/kifu/name_candidates.py`: generated 分支选择明确正面规则；旧负面、Hanja 和其他语言保持现有规则。
- Modify `katrain/web/kifu/name_batch.py`: 复用现有 evidence payload 与 batch ledger，为新正面分支保存完整的 applied batch 绑定，不新增表或第二套批准流程。
- Modify `katrain/web/kifu/identity.py`: 必做。展示、精确搜索及新增方法的覆盖资格共用同一 research/candidate/applied-proof 验证，不插入弱 alias。
- Test `tests/web_ui/test_kifu_name_evidence.py`, `tests/web_ui/test_kifu_name_candidates.py`; SQLite importer/reader 检查放在最接近的现有测试文件。

Exact contract:

```python
POSITIVE_SOURCE_BASIS = "normative_ja_ko_v1"
POSITIVE_SCOPE = "generated_from_original"
POSITIVE_RULE = "nikl-ja-ko-personal-name-v1"
# All three identifiers and player/ja/ko must match. Other generated rows
# continue to require not_found_in_scope and the unchanged closure checks.
```

- [x] 先写一个有效正面研究、pending candidate 与独立 approved candidate 的聚焦失败用例；运行对应测试证明旧代码拒绝新 contract。
- [x] 正面研究必须含 exact owner、原名、本人完整假名、姓/名边界、原名与读音来源 URL；保存实际正文、HTTP/capture 时间、SHA、定位及真实 source role。只能罗马字、猜音、姓名与读音不在来源中或身份尚 provisional 的数据拒绝。
- [x] 身份依据绑定当前 owner 和原名，可复用已核身份证据；不得仅以字形或罗马字近似建立人物对应，不改 FK。当前候选仍携带实际物理前像绑定。
- [x] 固定 NIKL 规则，保存人名规定、假名表、日语细则的实际捕获及引用位置。保留逐名完整输出解释，涵盖姓/名、词首词中、长音、促音等实际适用规则；不实现通用音译算法。
- [x] 实际冲突记录至少包括原名/已核罗马字＋围棋语境、候选韩文＋바둑 两类可用查询：URL、query、时间、正文/结果 SHA、检查到的相关结果和结论。全部入口失败、未解决相反用名或读音、已核其他人物的相同显示/alias 都拒绝；403/timeout 保持 unavailable，不制造 `not_found`。
- [x] 新分支不依赖 `negative_closure`，也不接受伪造 closure；`candidate_name` 精确等于输出，`decision_kind=generated`，source language 仍 ja。
- [x] 沿用 `generated_review` 逐项精确匹配 owner/lang/研究哈希/原名/读音/读音来源/规则/输出/reviewer/审核时间。新增正面依据中的捕获时间同样必须早于审核；producer 与 reviewer 不同，规则与全文输出分别审核。
- [x] 对新增 contract 字段做严格限定；不以 scope 不完整作为所有 generated 名字的通用放行条件。
- [x] `_candidate_evidence` 为此方法保存实际批次 bundle/冻结成员/研究的绑定。`_qualified_name_rows` 不得继续将此分支作为普通 generated 直接放行：核 ledger batch 已 applied，冻结成员及 candidate/research/evidence/name/owner/lang/revision 精确一致，proof/研究内容 hash 相符，并通过上述同一正面证据验证。展示、搜索复用资格集；覆盖统计只消费同一合格资格集，不因 verified/approved 标志单独计入新方法。没有 proof、未 applied 或 proof 被替换即拒绝。既有其他方法不随之放宽。
- [x] 负例只覆盖本次边界：非 player/非 ko/非 ja、错规则、来源或查询 hash/姓名/读音被换、只有失败查询、冲突未解决、审核早于新证据、研究哈希或精确输出不匹配；保留一个旧负面 generated 和旧 Hanja 路径的回归例。
- [x] 运行聚焦 evidence/candidate 测试及一个真实 SQLite importer→reader 用例：实际写入并读取新方法、拒绝伪造或未 applied 候选。只扩大测试以解决具体失败。
- [x] 独立 reviewer 审 spec 与代码的数据完整性边界；修复实际问题，达到最小充分验证后结束代码审查。

## Chunk 2: Five linked players, then more source work

### Task 2: ret73 controlled pilot and production reading

**Inputs:** `/tmp/kifu-player-next5retired73-20261007/source-packet-partial-v1`，manifest file SHA `64c0d6a599c5c4f99065ba95e70f3735fd03b499a76f4802f7ca3d23e7a9ac43`。五人是染谷一雄、日下包夫、泉谷実、浜島久義、出雲栄次；1,481 linked slots 不是预计新增完整棋局数。

- [ ] 独立 binder 捕获两库 owner 和已有名称前像，核 CWI/专业资料人物对应及同人/跨人物碰撞；不能把 provisional 包直接变成已核人物。只保存已闭合范围，疑点保持 raw/partial。
- [ ] 来源研究者实际取得五个本人假名、有限两类冲突检索及 NIKL 依据；逐名产生 KO 输出。可靠通行韩文用名优先；没有把握的单人交第二位 reviewer，不扩大所有人的检索。
- [ ] root 独立核五份完整输出及引用，签精确候选；JP/EN 正源可随既有 batch 同步保存。只写实际通过的名称和权威页面；CN/TW 仍使用原文/既有回退，不标记为五语严格齐全。
- [ ] 代码审通过后精确 commit/push；从实际 importer 和部署 reader 各自基线做有限 overlay，不直接替换旧 ORM 或整个服务配置。先 TEST dry-run→apply→verify，再 PROD；只 root 写库。
- [ ] 必要 web reader 已加载同一新分支；实际 HTTP 核一个 KO 名称及其查询、一个英语回退，不重拍 UI。对新方法进行真实 proof/读取阳性与一个未应用 proof 阴性检查。
- [ ] 将实际资料 URL/角色/语言/捕获/摘录/规则方法随 research 保存；`authoritative_pages` 复用其中本人/史料 URL，不把排名表冒充生平页。完整网页是否有保存如实记录。
- [ ] 同时报告五语严格齐全人数、规范生成数量、首轮原文显示人数与实际整局覆盖；未经处理的默认回退不算完成。每五人写库后报实际统计，保留两库收据并更新 HTML；继续下批，不等待人工重复确认。

## Review limit and handoff

root 写本计划；独立 gpt-6-astra/max 最多两轮审。实现按 subagent-driven-development 执行，独立代码审不由实现者签自己。若具体 schema 小项需调整，可在本限定 contract 内决定并留在实际 review，不重复启动设计流程。

第1轮审核发现一项实际边界：普通 generated 在既有 reader 中会直接放行，且 evidence 没有此方法的 applied proof。已将 name_batch/identity 改为必做，明确精确批次绑定与显示/搜索/统计共享资格，不新增 DDL；提交第2轮审核。

## Scope limits

不改原 SGF、段位、身份 ID、棋局链接、来源列表或隐藏状态；不增加 UI、人物主页、生平全文采集、任意语言生成、通用转换库、缓存服务或额外签核体系。赛事继续既有 literal 路径，当前已通过的数据批次继续入库。

## Implementation / independent review checkpoint

2026-10-07：独立Astra/max第2轮计划审PASS，无Essential。实现限定四个既有module与两个现有test，未新增DDL或通用转写器。实际TDD三次RED覆盖未知scope、缺persistedproof、同时移除所有mutablemethod标记后退到旧放行；四相关测试文件383passed，最后creationledger识别修正后聚焦20passed。独立FH（实际gpt-6-sol）按requesting-code-review实读6文件diff：spec/code均无Essential/Important。真实来源输出仍需逐人核验，ret73尚未签核、入库或上线；待完成有限旧PROD SQL reader适配和实际首批。

部署兼容修复与最终审核：实际旧PROD ORM基线不支持candidate→inventory传递依赖，已把本方法exactreview抽为name_evidence纯helper，candidate与persisted门复用；实际禁用candidate后的importer fixture读取通过。两savedreader有限overlay保持实际Compose/ORM基线。FH发现的唯一Important（畸形batch_id=[]触发TypeError）已在repo及两reader修复，非整数及bool均拒；两SQLite reader阳性、缺proof、pending、mutablemarkers全删、[]/True阴性通过，21聚焦通过。FH独立复核该guard后close review，无剩余Essential/Important。实际部署与真实候选仍待下段执行。
