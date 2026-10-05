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
- [ ] 独立研究 producer 交付实际官方网页字节、五语言完整标题、两库精确前镜像和成员 ID。root 核对来源及集合，按 TEST→PROD 完成 owner 审核；随后重新绑定实际 catalog，再写入 100 个名称单元。
- [ ] 核对完整 scope 不变、实际显示／精确搜索与英语回退，更新实际覆盖与 HTML；不重复构建或重启未变的网页服务。棋手五人批次持续并行。
