# 棋谱名称逐实体交付 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Scope update (2026-10-03):** 用户将本轮交付缩减为简体中文、繁体中文、日文、韩文、英文五种经核实名称。德、西、法、俄、土、乌界面中的棋谱棋手与赛事名称显示英文；以后再评估是否补齐六种译名。新入库棋手或赛事只需五种名称获批，旧的十一语已批准数据保留。下文提到的十一语目标和批次规模均由本段五语范围取代。

**入库节奏更新（2026-10-08）：** 按用户最新要求，从已在执行的第 587 批安全收尾后，改为累计 20 个不同棋手具有已核实、可写入的新增名称后集中更新 TEST 和 PROD。等待期间继续并行研究、绑定和审核，待审结果不计入数据库进度。一次集中更新只做一轮必要的前像/资格检查、来源页面同步、代表性实际 API 查询和最终覆盖率报告；复用现有导入事务，不为批量大小增加新的基础设施。保留每位棋手实际来源与审核记录；20 个已处理棋手不等于 20 个五语言齐全棋手，后者以数据库当前五种名称资格为准。赛事批次继续按原流程执行。已签未入库的 ret156 四位、ret165 一位先进入积累队列，不单独立即写入。

**赛事直译授权（2026-10-05）：** 用户允许赛事名称直接翻译。本次只给已有 `event` ID 的五种主要语言增加 `translated` 决策及 `translated_from_original` 研究状态；原文须有已登记官方、专业围棋或百科来源的真实 HTTP 200、正文 SHA-256、原文摘录、实际原语言和同赛事身份依据。来源检查的候选是 `original_name`，最终 `candidate_name` 则是译名，明确记录 `translation_method=literal_event_title` 和规则版本，由独立审核批准。沿用现有五语文字检查、前像、碰撞及事务导入；不要求证明当地没有惯用译名，不套用姓名读音或负面检索规则，不将直译标成 `conventional`。棋手、raw 对象和既有其他路径保持原门槛；本次无新表或新证据框架。

**Goal:** 棋手按上述 20 人节奏写入 TEST 和 PROD；赛事继续渐进写入。每次集中更新后公布实际数据库的实体和棋局覆盖进度。

**Architecture:** 继续使用现有来源、独立审核、不可变清单、前像绑定、事务导入和条件撤销机制。全局严格模式保持关闭；普通 API 对已批准对象使用与严格模式相同的证据/槽位解析，对其余对象维持既有显示。按上述五语和 20 人节奏提交已核实名称及必要的精确原文作用域；入库前确认当前前像和目录。独立实体与未归一的 raw-name 对象分别统计。

**Tech Stack:** Python、SQLAlchemy、PostgreSQL、FastAPI、pytest；TEST `home-ubuntu`，PROD `ucloud-v100`。

**Supersedes:** `2026-10-02-kifu-full-name-localization.md` Task 12 中全库 100% 才允许首个正式名称数据批次的门槛。全库 100% 仍是整个十一语言项目完成和启用全局严格模式的门槛。

---

## Chunk 1: 渐进可见与准确进度

### Task 1: 普通列表和搜索渐进使用已批准名称

**Files:** Modify `katrain/web/kifu/identity.py`, `katrain/web/api/v1/endpoints/kifu.py`; focused tests in `tests/web_ui/test_kifu_name_api.py`.

- [ ] **Step 1:** 写失败测试：严格模式关闭时，已批准 raw-player 的精确槽位在列表/详情显示目标语名，目标语搜索只返回该作用域；未批准的 raw 或错槽继续旧显示且搜索无扩展。已关联实体的新批准行优先于旧 legacy 行。
- [ ] **Step 2:** 运行 `pytest -q tests/web_ui/test_kifu_name_api.py -k incremental`，确认新断言先失败。
- [ ] **Step 3:** 复用 `strict_display_maps`、`strict_matching_names` 的合格名称与作用域校验，但仅对已批准项叠加到非严格回退；不得打开全局 `KIFU_STRICT_NAMES`，不得返回全库 unavailable 标签。
- [ ] **Step 4:** 重跑上述聚焦测试及既有列表/搜索相关测试。差异仅限已批准对象。

### Task 2: 每次入库后的实际进度报告

**Files:** Create `scripts/kifu_name_progress.py` and `tests/web_ui/test_kifu_name_progress.py`; reuse `katrain/web/kifu/name_coverage.py` and `identity.py`.

- [ ] **Step 1:** 写失败测试：只有当前数据库中 11 个语言全部经证据及版本校验合格的**独立实体 ID**才算完成；尚未关联身份的 raw-player/raw-event 完成数单列；候选、旧 verified、撤销批次、部分语言均不计入。
- [ ] **Step 2:** 运行聚焦测试见失败；实现只读一致快照，输出环境、时间、批次 ID、棋手实体与赛事实体的完成数/总数/百分比、raw 名称对象的单列数、双方棋手/赛事/三者同时完整覆盖的棋局数/可用棋局总数/百分比。棋局判断复用 `strict_slot_approvals` 对 11 语的同一精确 album 槽位，不以姓名行数代替。
- [ ] **Step 3:** 跑聚焦测试。每个数字保留分子和分母；TEST 与 PROD 独立运行、独立保存，后一次重新读取实时 DB，不能沿用上次报告或候选清单。

## Chunk 2: 首个对象与重复执行

### Task 3: 吴清源作为首个已关联棋手

**Files:** Existing approved controlled Wu artifacts referenced in `docs/resource/kifu-name-wu-11lang-completion-gap-2026-10-02.md`; new per-environment receipts under controlled audit storage; deployment record under `docs/resource/`.

- [ ] **Step 1:** 在 TEST 和 PROD 分别只读确认 `player:1` 的身份、现有棋局 FK、11 行完整前像、schema/代码版本及备份。若环境 ID 不同，以各环境实际 ID 重绑，绝不照搬 `player:1`。新清单或前像漂移时保留旧签包，制备新的待审产物并独立复核。
- [ ] **Step 2:** 复用现有获批 `9+2` 语言的来源，基于目标实际快照制备**只含吴清源一人**的新批次。两组来源登记版本分别为 `.2/.3`，沿用两个技术批次并在同一对象交付中顺序执行；每组当前库前像都重新独立签署，不移植旧签名。先在该环境的隔离副本按相同顺序 dry-run/apply/replay/undo；核对原 SGF/FK、所有 11 语显示和搜索。每笔数据库写入后都运行进度报告，第一笔仍未满 11 语时如实报告 0 个新增完成实体。
- [ ] **Step 3:** 先在 TEST 对该对象执行 `scripts/kifu_name_batch.py dry-run` 和 `apply`，再以真实 API 和进度脚本核验、公布 TEST 分子/分母/百分比。出现异常按当前批次条件撤销并报告实际状态。
- [ ] **Step 4:** 对 PROD 新鲜快照重走独立审核和隔离演练，执行 dry-run/apply；核验 API、SGF/FK 和进度，公布 PROD 分子/分母/百分比。不要把 TEST 批次 ID 或完成数算入 PROD。

### Task 4: 后续对象逐个重复

**Files:** Existing candidate/batch artifacts and runbook; each object gets a separate controlled approval and receipt.

- [ ] **Step 1:** 选下一位已完成 11 语且身份/范围明确的棋手或赛事。若仅 raw-name 已批准，先作为 raw 对象写入并单列名称对象进度，不能称为已归一人物/赛事；其真实棋局覆盖可按精确槽位增加。
- [ ] **Step 2:** 从上次写入后的实际 DB 重取 inventory、catalog、获批名称快照、名称行前像；每对象独立签包、隔离演练、TEST 更新与报告、PROD 更新与报告。每次更新只含一个棋手或一个赛事的十一语言决策及其受审作用域。
- [ ] **Step 3:** 按语言和高频未覆盖槽位继续研究，直到全库所有黑/白/赛事槽位十一语合格。最终再启用严格模式并执行原总计划中的全库验收；阶段数字不宣称全库完成。

## 安全边界

导入器现有哈希、独立审核、前像、类别、范围和碰撞闸门保持生效。生产数据批次不靠脚本现场自签，也不以离线校验替代目标 DB dry-run。SSH 或网络不可用时可以继续本地代码和审核准备，但不得把未执行的数据库更新报告为成果。

## Chunk 3: 棋手权威页面链接（2026-10-05）

**授权与决策：** 用户希望保存已经找到的棋手页面，供未来生平和著名棋局主页使用，并委托 `gpt-6-astra` 独立决定最小方案。本段完成 brainstorming 与 writing-plans，直接进入已授权实现；不再次等待设计确认。仅实现字段和同步工具，暂不生成生平、主页 API 或界面。

**方案比较：** 选择 `kifu_players.authoritative_pages` JSON 列，沿用现有 evidence、registry、metadata 的 SQLAlchemy `JSON` 惯例；此用途整份读取和少量追加，暂不需要 JSONB 索引或服务器端路径检索。JSONB 没有本轮收益；新建页面关系表则增加迁移和查询关系，留待确有独立页面编辑需求时考虑。

**数据约定：** 默认空数组，每项为 `url/source_id/language/role/evidence_ids`。URL 精确去重；同 URL 汇总证据 ID，已有手工条目的文字、分类及额外字段保留。`role` 如实记录来源登记的类别（官方、专业围棋资料、维基或其他百科、参考来源），不会把百科写成官方。页面语言取实际来源/页面语言，棋手原姓名使用中文不意味着韩国棋院页面是中文。

**来源边界：** 从当前 `verified` 棋手姓名行关联的独立 `approved` evidence 读取；owner、语言、revision、display name、decision、rule 均匹配，复用现有正式名称资格判断。核对持久化候选对研究内容的哈希绑定，只读取该研究中的正面来源、原名证据和独立身份佐证，以及明确同人的专业档案桥接；不递归抓取引文，不保存检索结果、负面/拒绝线索、发现用标签或其他棋手来源。没有可证明绑定的旧证据跳过，不猜测归属。

**并发与兼容：** apply 先取得普通 UPDATE 所需的 player 表写入锁，再在读取并合并页面前锁住对应 player 行，按 ID 顺序处理；该次序避免与姓名导入器既有表锁交叉等待，页面合并不会覆盖另一批同步或已经提交的手工更新。新增列不进入姓名行前像，也不进入 catalog 哈希。现有 catalog 哈希实际包含棋手 `id/canonical_name/created_at`，继续明确选择这三个历史字段以保持已签旧哈希逐字节兼容；现有 owner manifest 的 `id/canonical_name` 子集比较不变。身份、FK、译名和导入器事务/撤销流程不改。

### Task 5: 字段、证据采集和幂等同步

**Files:** Modify `katrain/web/core/models_db.py` and catalog 列选择处 `katrain/web/kifu/name_batch.py`; create `scripts/migrate_kifu_player_pages.sql`, `katrain/web/kifu/player_pages.py`, `scripts/kifu_player_pages.py`, `tests/web_ui/test_kifu_player_pages.py`.

- [x] **Step 1:** 用隔离 SQLite fixture 写聚焦失败测试：已批准当前姓名收集维基/官方页面；未审核、错 owner/语言/revision/姓名/rule、跨棋手 payload、检索和负面线索被排除；去重、手工值保留、幂等、dry-run 不写；旧 catalog 哈希及姓名前像不变。
- [x] **Step 2:** 增加 JSON 默认空数组字段，提供唯一显式迁移 `ALTER TABLE kifu_players ADD COLUMN IF NOT EXISTS authoritative_pages JSON NOT NULL DEFAULT '[]'`。部署前由主线程运行迁移，本任务不连接 TEST/PROD 写入，不自动启动迁移。
- [x] **Step 3:** 实现小型采集/合并模块与 CLI：`python scripts/kifu_player_pages.py dry-run --database-url ... [--player-id N ...]` 预览；独立审核后 `apply` 回填全体，后续每批姓名完成后对本批 player IDs 幂等同步一次。复用 evidence 内保存的 registry，不联网或读取待审核本地候选。
- [x] **Step 4:** 运行 `python -m pytest -q tests/web_ui/test_kifu_player_pages.py`，再选现有 name-batch 的 catalog/前像相关用例确认旧包兼容；`git diff --check`。只做本需求必要检查，不扩大全库回归或新增审计框架。
- [x] **Step 5:** 报告改动、实际测试结果与未执行迁移/回填的状态，交其他 agent 独立 code review，再由主线程安排显式迁移、预览与回填。

**实现验证（2026-10-05）：** 新增 21 个聚焦测试通过；现有 `test_kifu_name_batch.py` 中 `matching_existing_name_preimage_allows`、`v2_owner_preimage_accepts`、`v2_stale_catalog_rejects`、`v2_new_raw_owner_fixture` 四个用例通过。CLI `--help` 与本次文件 `git diff --check` 通过。只运行隔离 SQLite fixture，尚未执行 TEST/PROD 迁移、回填或 PostgreSQL 并发演练。当前采集器保守跳过无直接研究哈希绑定的 legacy payload、symbolic owner 及仅有生成 anchor 的姓名；同一棋手其他当前正面姓名证据仍会收集，报告 `eligible_names/names_with_pages` 体现差额。

**上线结果（2026-10-05）：** 独立 code review 通过，主线程在两环境显式迁移、dry-run、apply 并再次 dry-run。首次回填 TEST 76 位/465 URL、PROD 77 位/471 URL，重复同步均 0 变更。后续每5位姓名批次同步来源页面并保留真实回执。页面字段不会改变 catalog 哈希；既有待审名字包继续通过 stale 检查。完整回执在 `docs/resource/kifu-incremental-applied-2026-10-05/`，包含应用前后 JSON。
