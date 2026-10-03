# 棋谱名称逐实体交付 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 每完成一个棋手或赛事的十一语言译名，即分别写入 TEST 和 PROD，并在每次写入后公布实际数据库的实体和棋局覆盖进度。

**Architecture:** 继续使用现有来源、独立审核、不可变清单、前像绑定、事务导入和条件撤销机制。全局严格模式保持关闭；普通 API 对已批准对象使用与严格模式相同的证据/槽位解析，对其余对象维持既有显示。每次只提交一个对象的完整十一语及必要的精确原文作用域；下一对象根据上一次写入后的新快照重绑。独立实体与未归一的 raw-name 对象分别统计。

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
