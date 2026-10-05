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

- [ ] 增加聚焦失败用例：已存在且原文范围明确的 raw owner，五主语言完整标题走 `translated_from_original`；玩家不能借此直译，原 entity event 流程不变。
- [ ] 扩展研究与候选验证，沿用 `literal_event_title`，raw 规则为 `raw-event-title-translation-v1`。精确绑定 `owner.id`、`candidate.raw_value`、库存原值、原始语言来源、真实正文 hash 和 source capture 时间。直译不声明为目标语言通行专名。
- [ ] 如果复用核心来源，保存源中实际出现的 core 与完整 raw 的无损 parts；不得把网页中的核心伪称为完整轮次标题。完整 display 绑定被审核的核心和明确 components；缺失或含糊部分保留原文，不猜测。只补本批实际遇到的汉字/全角序号。
- [ ] 为首批 24 个已有且无名称的 raw owner 单独生成有限分类审核单，复用 raw2134 的独立签名、完整前镜像 CAS、写锁、变更账本及撤销机制。只认定“原文可读、可按字面及明确届次/轮次翻译”，不认定赛事身份；保留 category=`unclassified_pending`、parser_version、parsed_data、原值及 FK，只将 review_status 从 pending 改为 approved 并存真实 producer/reviewer 的 review_metadata。每库绑定完整前镜像、catalog hash、精确原文及当前公开、非重复、NULL event_id、无 selected_event 的成员，先 TEST dry-run/apply/verify 再 PROD。分类批准不算翻译完成。
- [ ] 用 `bundle_format=2`、`inventory_format=4`、`album_links=[]` 复用名称写入和撤销，分类完成后重新绑定实际新 catalog 与 owner 前镜像。只允许真实已有 raw ID 和已批准 owner；本次不扩大 raw owner 创建接口、不绕过 pending 门禁。
- [ ] 同一完整译名仅对两端均已审核的 translated raw descriptions 放行，批内与跨批一致；不伪签不同人物，不放宽人物或赛事身份碰撞。只写名称、证据、账本，不改 alias、赛事/棋手 FK、原 EV/SGF、段位。

### Task 2: 显示与精确搜索

**Files:**
- Modify: `katrain/web/kifu/identity.py`
- Modify: `katrain/web/kifu/legacy_raw_events.py`
- Modify only if needed: `katrain/web/api/v1/endpoints/kifu.py`
- Add only if needed: `katrain/web/kifu/raw_event_translation.py`（strict 与旧 SQL reader 共用的纯资格检查）
- Modify: 原始赛事兼容规则打包器（先定位现有生成器，不手改生成结果）
- Test: `tests/web_ui/test_kifu_raw_event_title_translation.py`、现有 legacy raw reader 聚焦用例

- [ ] 增加显示和搜索失败用例：五语言直译、六语言英语回退、同名译文对应多个精确 raw、selected_event/已有 event_id 排除。
- [ ] 两种 reader 使用相同的窄资格检查：批准状态、实际不同 producer/reviewer、candidate/research hash、owner、raw、locale、display、revision 和规则一致。已有 generic/archive 的签名与范围检查保持有效。
- [ ] 页面只查当前页的精确 raw 集合；搜索合并全部已批准的精确成员，保持 ordinary fuzzy 查询行为。不能用子串将韩国围甲误关联到中国围甲。
- [ ] 主语言缺译仍算缺口；次语言只使用已批准英语名称，不再现场翻译。

### Task 3: 聚焦验证、独立审核与发布一批

**Files:**
- Modify: 此计划勾选状态及现有进度报告/实际入库收据

- [ ] 运行：`.venv/bin/python -m pytest tests/web_ui/test_kifu_raw_event_title_translation.py -q`，预期通过。另运行被修改现有 reader/翻译门禁的相关测试，不做无关全量回归。
- [ ] 检查错误 raw/hash/签名、撤销后不显示、同名多成员搜索，以及新译文没有改 alias/FK/SGF。root 做需求核对，独立 agent 做代码审查；仅修实际阻塞，直到通过。
- [ ] 将审核通过的代码提交，先以真实已有 raw owner 的小批次 TEST dry-run/apply/verify，再 PROD。研究 agent 准备友情杯/招商银行杯完整标题的候选；中国围甲和韩国围乙的已核实体匹配单独统计，不混入直译范围。
- [ ] 以当前云端镜像为基础准备最小覆盖，保留已有报告缓存、完整 Compose 层和环境文件路径。发布 TEST 后核对真实列表/搜索，再发布 PROD；失败恢复此前镜像。普通棋手五人批次在研究与开发期间继续推进。
- [ ] 每次实际 DB 更新刷新棋手、赛事、覆盖棋局统计及 HTML，pending 和仅核心译名不计完成。只有五语言完整标题已写入且真实 reader 可读取的原文棋局计入新增覆盖。
