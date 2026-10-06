# 原始赛事标题五语言直译 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development. Steps use checkbox syntax for tracking.

**Goal:** 将原文赛事标题的中文、繁中、日文、韩文、英文完整译名存入现有数据库，并在两种云端阅读器中显示和精确搜索。

**Architecture:** 扩展现有 `translated` 研究、候选、入库与读取路径到已有 `raw_event` ID；DB 存完整标题，核心翻译及年份、届次、轮次在离线生成时复用。复用事务、审核、撤销、SQL 兼容模块，其他六语言读取英语；不建立新的翻译服务或身份归并流程。

**Tech Stack:** Python、SQLAlchemy、PostgreSQL、现有 pytest 与 Docker 有限覆盖发布。

**Authority:** 用户已批准赛事直接翻译及五主语言范围；其授权的独立 GPT-6 Astra 决定见 `docs/resource/kifu-raw-event-translation-decision-2026-10-06.md`。首批只处理已捕获的 24 raw / 493 局（友情杯 7 / 271，招商杯 17 / 222），其他原文另批处理；apply 前分别核对两库当前精确成员，不把完整 family 总数混入本批。

## Chunk 1: 一个原文标题的完整用户旅程

### Task 1: 候选与现有入库协议

**Files:**
- Modify: `katrain/web/kifu/name_evidence.py`
- Modify: `katrain/web/kifu/name_candidates.py`
- Modify only if needed: `katrain/web/kifu/name_batch.py`
- Adapt bounded tool: `/tmp/kifu-raw2134-20261005/kifu_raw2134_categories.py`（只保留本批 24 个 owner 的有限 review_status/review_metadata 审核单，不推广 owner 创建）
- Test: `tests/web_ui/test_kifu_raw_event_title_translation.py`

- [x] 增加聚焦失败用例：已存在且原文范围明确的 raw owner，五主语言完整标题走 `translated_from_original`；玩家不能借此直译，原 entity event 流程不变。
- [x] 扩展研究与候选验证，沿用 `literal_event_title`，raw 规则为 `raw-event-title-translation-v1`。精确绑定 `owner.id`、`candidate.raw_value`、库存原值、原始语言来源、真实正文 hash 和 source capture 时间。直译不声明为目标语言通行专名。
- [x] 如果复用核心来源，保存源中实际出现的 core 与完整 raw 的无损 parts；不得把网页中的核心伪称为完整轮次标题。完整 display 绑定被审核的核心和明确 components；缺失或含糊部分保留原文，不猜测。只补本批实际遇到的汉字/全角序号。
- [x] 为首批 24 个已有且无名称的 raw owner 单独生成有限分类审核单，复用 raw2134 的独立签名、完整前镜像 CAS、写锁、变更账本及撤销机制。只认定“原文可读、可按字面及明确届次/轮次翻译”，不认定赛事身份；保留 category=`unclassified_pending`、parser_version、parsed_data、原值及 FK，只将 review_status 从 pending 改为 approved 并存真实 producer/reviewer 的 review_metadata。每库绑定完整前镜像、catalog hash、精确原文及当前公开、非重复、NULL event_id、无 selected_event 的成员，先 TEST dry-run/apply/verify 再 PROD。分类批准不算翻译完成。
- [x] 用 `bundle_format=2`、`inventory_format=4`、`album_links=[]` 复用名称写入和撤销，分类完成后重新绑定实际新 catalog 与 owner 前镜像。只允许真实已有 raw ID 和已批准 owner；本次不扩大 raw owner 创建接口、不绕过 pending 门禁。
- [x] 同一完整译名仅对两端均已审核的 translated raw descriptions 放行，批内与跨批一致；不伪签不同人物，不放宽人物或赛事身份碰撞。只写名称、证据、账本，不改 alias、赛事/棋手 FK、原 EV/SGF、段位。

### Task 2: 显示与精确搜索

**Files:**
- Modify: `katrain/web/kifu/identity.py`
- Modify: `katrain/web/kifu/legacy_raw_events.py`
- Modify only if needed: `katrain/web/api/v1/endpoints/kifu.py`
- Add only if needed: `katrain/web/kifu/raw_event_translation.py`（strict 与旧 SQL reader 共用的纯资格检查）
- Modify: 原始赛事兼容规则打包器（先定位现有生成器，不手改生成结果）
- Test: `tests/web_ui/test_kifu_raw_event_title_translation.py`、现有 legacy raw reader 聚焦用例

- [x] 增加显示和搜索失败用例：五语言直译、六语言英语回退、同名译文对应多个精确 raw、selected_event/已有 event_id 排除。
- [x] 两种 reader 使用相同的窄资格检查：批准状态、实际不同 producer/reviewer、candidate/research hash、owner、raw、locale、display、revision 和规则一致。已有 generic/archive 的签名与范围检查保持有效。
- [x] 页面只查当前页的精确 raw 集合；搜索合并全部已批准的精确成员，保持 ordinary fuzzy 查询行为。不能用子串将韩国围甲误关联到中国围甲。
- [x] 主语言缺译仍算缺口；次语言只使用已批准英语名称，不再现场翻译。

### Task 3: 聚焦验证、独立审核与发布一批

**Files:**
- Modify: 此计划勾选状态及现有进度报告/实际入库收据

- [x] 运行：`.venv/bin/python -m pytest tests/web_ui/test_kifu_raw_event_title_translation.py -q`，预期通过。另运行被修改现有 reader/翻译门禁的相关测试，不做无关全量回归。
- [x] 检查错误 raw/hash/签名、撤销后不显示、同名多成员搜索，以及新译文没有改 alias/FK/SGF。root 做需求核对，独立 agent 做代码审查；仅修实际阻塞，直到通过。
- [x] 将审核通过的代码提交，先以真实已有 raw owner 的小批次 TEST dry-run/apply/verify，再 PROD。研究 agent 准备友情杯/招商银行杯完整标题的候选；中国围甲和韩国围乙的已核实体匹配单独统计，不混入直译范围。
- [x] 以当前云端镜像为基础准备最小覆盖，保留已有报告缓存、完整 Compose 层和环境文件路径。发布 TEST 后核对真实列表/搜索，再发布 PROD；失败恢复此前镜像。普通棋手五人批次在研究与开发期间继续推进。
- [x] 每次实际 DB 更新刷新棋手、赛事、覆盖棋局统计及 HTML，pending 和仅核心译名不计完成。只有五语言完整标题已写入且真实 reader 可读取的原文棋局计入新增覆盖。

## Continuation: 有限追加批次（2026-10-06）

独立 GPT-6 Astra max 已检查九份研究包，建议先处理阿含桐山杯本选 10 原文／205 局及招商银行杯 2 原文／2 局；详情归档于 `docs/resource/kifu-raw-title-next-finite-decision-2026-10-06.md`。沿用已有字面语法和审核协议，不新增身份或 FK。

- [x] 在现有 owner 工具追加显式 `agon10`、`cmb2` profile；分别固定原文集合 SHA、数量和成员总数，首批 first24 校验不变。新增 profile 均固定范围，默认仍为 first24。
- [x] 聚焦验证 profile 选择、错误原文／数量／范围拒绝；保留完整前镜像 CAS、现有锁、签名和账本。独立代码审核通过后提交。
- [x] 研究 agent 将既有草稿规范成现有 manifest；阿含核心采用已捕获正文标题的真实连续片段，招商核心采用已捕获 2006 年正文。届次／轮次来自原 EV，不宣称来源核实了每个届次。
- [x] root 分别核对两库 live 精确前镜像及范围，TEST→PROD 批准 owner，再由独立 producer 绑定新 catalog／前镜像，审核并写入五语言名称。刷新实际统计及 HTML。
- [x] 并行获取团体赛、十番棋、中国围棋段位赛、全国围棋个人赛、升段赛的核心正向来源；源和候选完整后另批交付。不扩张当前 profile 到任意 manifest。

后续 CMB17／43 的六种阶段后缀待该批来源及候选齐备时单独实施；本轮不引入该语法。

## Continuation 2: 通用说明与明确地理限定语

两项独立 Astra 决定见 `docs/resource/kifu-generic-core-and-agon-decision-2026-10-06.md` 和 `docs/resource/kifu-generic-team-mixed-scope-decision-2026-10-06.md`。

- [x] 先审核纯 unlinked 的 `generic49`：49 原文／557 盘，原文集合 SHA `17b041004df08a99aa9845060e0d6009f103e612110673e48a6260e2bd1395ab`。仅追加有限 owner profile 与聚焦成功／错误 scope 检查，不改变原 reader 或任何旧 profile。
- [x] 独立 producer 从已核实 generic50 资料派生这 49 项，绑定真实 HTTPS 体育总局与 World Go 字节，保留届次、年份、轮次。两库真实 owner 审核、名称写入、查询和报告继续采用同一协议；原始字段 72432 的五格与既有核实赛事实体 72 碰撞，独立审核后将其 10 盘保留待审，实际交付其余 48 项／547 盘。
- [x] 随后为固定 `geographic39`：39 原文／294 盘，集合 SHA `996b55aae2bacf4b5b1273d14fb75e5f4c95d1d5bc0451f3759606a1fd4da315`，只允许一次 `geographic_qualifier:中国` 紧邻 `core:围棋段位赛`。限定语来自原 EV，核心由真实 HTTPS 2016 体育总局正文支持；研究 parts 无损，不修改 DB parser 或原 EV。测试一次成功及越界原文／错误限定语／位置拒绝；独立代码审核后才写入并发布纯检查模块。
- [x] 团体赛另批处理：现 324 个 raw occurrences 中 294 盘 unlinked，30 盘有 event_id。先只读冻结全部 324 个 ID／字段及 30 个完整 linked 镜像，有限 signed owner metadata 明确 eligible／excluded。仅在固定 owner 73686 的小范围例外中允许既有 linked 记录；保留原 FK，excluded event_id 即使换成另一个非 NULL 也须 CAS 拒绝。format2 owner occurrence 必须为全部 324，members 仅五语言名称单元；展示／搜索及新增覆盖只计 294。不改变 `_v2_scope` 或两 reader；旧纯 unlinked 路径不变。未有完整捕获前不批准该批，独立审核所有涉及生产数据边界的代码。

各小批独立提交，已可交付部分不等待团体赛特例；棋手来源与五人入库继续并行。

### 已完成代码及当前数据状态（2026-10-06 05:13 CST）

- `generic49` 代码经独立 Astra 审查 APPROVE，实际源码只新增固定 profile；研究及两库 owner 110 已实际写入核验。依独立碰撞决定，两库名称 119 实际写入核验 48 项／547 盘、240 格；其余五格原始字段 72432／10 盘待审。两端各 16 项真实 HTTP 通过，未增加身份碰撞例外。
- `geographic39` 代码提交 `af4bc201`（独立实现 `13c288bc`）经独立 Astra APPROVE；44 项聚焦测试通过。39／294 的研究资料和全部 parts 已验证，运行时纯模块已发布两环境，健康、实际文件 hash 及各四项 HTTP 回归通过；owner 111／名称 115 已在两库实际写入核验 195 格，各 16 项实际显示／搜索／英语回退 HTTP 通过。
- Agon owner 103／name 106、CMB owner 104／name 107，已在两库实际写入并核对；HTTP 分别每环境 16／11 项通过。实际统计及归档完成。
- 团体赛 TEST／PROD 全 324 行已只读完整捕获，294 unlinked＋30 event_id=73；完整 IDs 与 inventory4 一致。固定特例代码 493fe0d1（独立实现 443403b9）经 Astra APPROVE，45 项聚焦测试通过；owner 112／名称 118 两库实际写入核验五格，原 324 行及 FK 不变，新增展示只计 294 盘。每端 18 项真实 HTTP 通过，包含 30 盘既有赛事译名与段位展示保持不变。
- 棋手来源研究与实际五人入库一直并行；已到 CB／数据库批次 122，PROD 415／3,698 位完整棋手，完整五语言展示 49,879／173,025 盘。继续推进下一批，不把资料草稿计入完成。

## Continuation 3: 2004 年围棋甲级联赛轮次标题

下一批 `league20` 固定为已捕获的 20 原文／214 盘，原文集合 SHA `a56431132255fce798e22d0b8a0869f677f9ec8784fad6bba0a72babe615de9a`。全部使用既有 year＋core＋round 语法；官方正文连续出现「围棋甲级联赛」作为字面核心依据，不从该依据推导赛事身份或新增「全国」限定语。

- [x] 在既有 owner 工具添加一个固定 profile，并复用现有参数化成功／错误 raw／数量／scope 检查；不改变 reader、语法或 FK。RED unknown profile → GREEN 11 项通过，独立 Astra APPROVE；报告 `docs/resource/kifu-league20-code-review-2026-10-06.md`。
- [x] 独立研究 producer 交付实际官方网页字节、五语言完整标题、两库精确前镜像和成员 ID。root 核对来源及集合；两库 owner 125／名称 126 已实际写入核验 100 格，214 盘原始字段及 FK 不变。名称阶段使用独立完整 registry，保留已应用 owner registry；首次 registry 格式拒绝发生在零名称写入前，修正后真实 CLI dry-run 通过。
- [x] 两端各 11 项实际显示／精确搜索／英语回退 HTTP 通过，完整两阶段 receipts 已归档。CE 棋手批次 127 后实际统计为 430／3,698 位棋手、64／85 赛事、完整五语言展示 50,933／173,025 盘；原文标题五语言覆盖 4,183 盘。未重启未变的网页服务。

## Continuation 4: Castle Game 历史对局标题

仅为原文字面翻译：固定 raw 69273／539 盘，raw-set SHA `85b73b82847777deefd627ce637ee3870725385cdfd76916202b4c23574f5f7c`。BGA Journal 134 实际 PDF 的 printed p.8／PDF p.9 支持历史围棋 Castle Game 用语，日本棋院历史页支持日文御城碁。不推导具体届次、比赛身份或 FK。

- [x] 最小新增 `castle1` 固定 profile（1 原文／539 盘），复用已有参数化 exact raw／数量／scope 检查；RED unknown profile → GREEN 12 passed；独立 Astra APPROVE，报告 `docs/resource/kifu-castle1-code-review-2026-10-06.md`。TYGEM 韩文实文另证 `오시로고(御城棋)`；译名不是五语官方专名声明。
- [x] root 核对原始 PDF、日本棋院及新增 TYGEM 实际字节正文、五语译法和完整 CLI registry。CE／CF 完成后，两库 owner 129／名称 130 实际写入核验 5 格／539 盘；owner manifest 不变，名称阶段独立 registry/research 保存新增韩文来源。
- [x] 两端各 6 项 HTTP 通过，539 盘原始字段和 FK 不变，两种 reader 一致。实际统计、HTML 和 receipts 已更新；原始标题五语覆盖 4,722 盘，完整展示仍 51,186 盘（双方棋手尚未同时齐全）。未重启网页服务。

## Continuation 5: 东京新闻杯届次标题

最新两库真实捕获为 11 原文／175 盘（旧摘要 167 已废弃），raw-set SHA `c5303d78e042bbb83c3e6c666abfd74e0d14127e32dbd52b38b4b9fc02685a1d`。CWI 实际原文写 Tokyo Shinbun Cup (東京新聞盃)，并列 1–11 届；Kifudepot 日文棋谱标题佐证。只翻译 exact title/edition，不改变身份、parser 或 FK；Final 等其他四 raw 留下一批。

- [x] 固定 profile 复用现有参数化 fixture；同时纯 validator 只放行 exact 1st–11th Tokyo Shinbun Cup 的两段无损 edition＋core，不泛化其他英文比赛或 Final。原 Chinese ordinal gate 保留。RED 11 fail／5 pass → GREEN 两文件 64 passed；独立 Astra 审查后提交，并把同一纯文件在当前线上镜像上最小覆盖发布。当前云端基底已是 kifu-library-fast，保留其 endpoint／identity／性能和前端文件。
- [x] producer 交付标准 CLI-valid 55 条 unsigned 研究与实际 owner scope；root 核对来源、数字和五语译文，按 TEST→PROD owner→name 入库。
- [x] 线上显示／搜索／英语回退与原始数据不变核验；报告真实覆盖、HTML、归档。棋手批次并行，确认同人重复不计新棋手，不绕过碰撞。

实际交付：代码 9b3d8532 经独立 Astra APPROVE，source packet 55 条通过全部纯校验，owner 133／name 134 两库实际写入核验 11／175／55。两端仅共享纯 validator 新镜像发布；健康、hash、旧 4 项及新 11 项 HTTP 均通过。CWI 主要来源已存 evidence research_payload，Kifudepot 补充核查页保存在 immutable manifest/归档，未宣称所有补充页面都已进 DB。实际原文标题覆盖 4,897、完整展示 51,675；两类来源存储位置如实区分。


## Continuation 6 — national15 literal SGF titles

Independent Astra decision: [scope and source policy](../../resource/kifu-next-event-throughput-decision-2026-10-06.md). User permits literal event translations; no external exact-title requirement or event identity assertion.

- [x] Actual read-only TEST/PROD capture: 15 raw / 486 whole-scope albums, raw-set SHA `a1c386f0d6b606f2ed588d8b98bfd39398cec584bba683ab07e0dc7f9dede77d`. All original SGFs have empty EV and their first GN equals the raw title; two second GN values retain time-loss annotations. Preserve this actual provenance.
- [x] Minimal fixed-scope `sgf_literal_v1` branch with original GN/source/SGF hashes and approved-owner scope binding in candidate and reader; retain strict previous sources and identity rules.
- [x] Independent pending producer: 75 names; TW 輪 / JP ラウンド; actual supplementary source links and honest limitations inside signed research.
- [x] Focused code review APPROVE: [independent review](../../resource/kifu-national15-code-review-2026-10-06.md). Red checks fail before implementation; final relevant modules 86 passed in 6.92 s.
- [x] TEST owner/names dry-run/apply/verify and PROD, actual reader deployment/HTTP checks, counts and archives.

Actual national15 completion: owner 139/name 140 on both databases; 486 unchanged albums/75 names, no FK change. Runtime TEST/PROD health and file hashes, four old HTTP cases and sixteen new language/search/fallback cases passed. Source GN and all applied/runtime receipts archived. After CM141, actual PROD five-language players470/3,698; events64/85; complete display53,570/173,025.

## Continuation 7 — manifest-bound Chinese SGF bulk

Independent Astra [bulk decision](../../resource/kifu-next-literal-event-bulk-decision-2026-10-06.md) freezes a research candidate batch150 raw/4,104 albums/750 names. Implement one bounded manifest-driven Chinese SGF profile and approved parser-parts hash in existing owner metadata, preserving national15 compatibility and all identity/CAS/collision gates. Literal event translation uses original GN; future same-shape batches require reviewed data, not per-title runtime changes.

- [x] Minimal implementation and focused checks, then independent code review. New manifest-driven Chinese SGF branch: 108 focused cases pass; independent Astra review identified one manifest replay binding gap, fixed with RED2 failures → GREEN2 cases. Final review APPROVE; no broad repeat tests.
- [x] Independent source producer, actual complete TEST/PROD scope and five-language collision checks; re-freeze any held entries before approval. Seven raw titles (159 albums/35 names) collide with previously verified event entity names and remain held. New frozen actual scope143 raw/3,945 albums/715 names, raw-set SHA `4ce2f12e3ef56e7fddd1f16ea3038a993891d1e5ac3d47b8842a6f89914dbe4f`; both reduced-set collision reads have zero matches. Original150 packet never approved/applied. Owner manifest canonical SHA `d034a03f7b0d8bbfedf1e2eb0ee9d20bcab08ad95ef853d2aadb595967792a6d`.
- [x] Actual TEST→PROD owner/name writes, one needed runtime update, representative real HTTP, honest counts and archives. Both environments owner146/name147 verified143/3,945/715, unchanged SGF/rank/FKs; strict and previous readers agree. Current-image pure-module deployment health/file hashes, old4 and national16 cases, new16 representative HTTP cases passed per environment. Raw five-language display covers9,328 albums; complete display56,850/173,025 (32.8565%). Actual source, actor mapping, holds and runtime receipts archived.


## Continuation 8 — next148 data-only literal batch

Reuse the reviewed and deployed `sgf_chinese` profile; no code, schema or runtime change is needed. Independently captured148 raw/2,063 games/740 names; raw-set SHA `81b2f40a5ad7694cc1ea7a4b785f29169428064c829a24bbd6188b074f080354`, frozen source manifest `9c7e2b3909259b813daa5ea51aa64c35b4ef596559d82989fb8c6f3e2cbe00d1`. Actual producer `/root/national15_sources_sol`. Hold placeholder省略 and verified-entity collision中国围棋霸王赛,14 albums each; do not hide or infer an identity. Root reviewed120 reusable core translations and corrected three stage/sponsor phrases before freezing. Post147 actual740-key collision checks are zero in both databases.

- [x] Actual source, whole scope, existing owner preimages and five-language matrix review; two unsigned owner plans prepared and independently approved.
- [x] TEST→PROD owner152/name153 actual apply/verify; bind740 names to actual afterimages, root review and sequential writes. Frozen player CT/CU finish before owner capture to avoid unnecessary rebinding.
- [x] Representative16 actual HTTP cases per environment, including the natural fourth-edition Lebaishi title union and English fallback; actual stats/HTML/receipts. Raw display11,391; complete display58,747/173,025 (33.9529%). No broad retests or service restart.


## Continuation 9 — next149 data-only literal batch

Reuse the reviewed deployed profile without product code or schema changes. Actual unsigned source packet149 raw/1,465 games/745 names, raw-set SHA `5228f491778baf03dc21269b394198e3cba166d544cb37b06a50416dd4735ab7`; manifest `0d70b8488342ea72c528811f0fe2c6afc6a45c8e6b3c6f0cdc8bbd9f3247f618`. Root read106 core translations, corrected second-stage wording and unified Guksu Cup spelling. After bulk148 actual names, both environments745-key collision checks returned zero. Contradictory 女男子组 remains held; no hide/identity inference.

- [x] Actual whole-scope source capture and frozen unsigned five-language evidence, pending owner plans.
- [x] Root exact owner review; TEST→PROD owner156/name157 actual writes; bind745 names to verified afterimages, root review, sequential name writes.
- [x] Sixteen representative actual HTTP cases per environment; actual stats/HTML and exact source/receipts archived. Raw display12,856, complete display60,058 (34.7106%).


## Continuation 10 — next150b data-only literal batch

Reuse the same reviewed/deployed `sgf_chinese` profile. Actual post149 scope150 raw/1,201 games/750 names; raw-set SHA `39e7bcf9c9619e1334f21f82b0fd561ad31bf85b0549b871de1ae7e6e42ddf91`, frozen source manifest `6831eaacd736b6ef4e99c4c39def0d91023dba944a6b012e539f0799bde7549a`. Root read115 core translations; preserve all years/sponsors/rounds and former Taiwan Rookie King qualifier distinction. Post157 dual-environment collision check has zero blocked/entity-alias matches; the one natural Korean raw-name union is legal literal display. Existing owner61551 (40 albums) + new owner61564 (8) must produce48-member HTTP union; both actual scopes captured, disjoint, and hashed. No event identity/alias/FK inference.

- [x] Independent actual full-scope source/collision capture, root literal matrix review and unsigned frozen research750.
- [x] Exact owner review and TEST→PROD owner161 writes after CX/CY/CZ completed; bind750 names to actual verified afterimages, root exact review and name162 writes.
- [x] Each environment16 actual HTTP checks including48-member Korean literal union; two readers agree,1,201 original albums/ranks/SGFs/FKs unchanged. Raw display14,057 and complete display61,427 (35.5018%). Actual receipts and source/hash provenance archived. No runtime change or broad retests.
