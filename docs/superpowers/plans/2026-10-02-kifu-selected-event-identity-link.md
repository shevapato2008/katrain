# 已审核第二 GN 的赛事身份关联 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 只在赛事身份和十一语名称均独立获批后，把已审核 SGF 第二个 `GN` 的有限棋局关联到真实赛事 ID；原棋谱和来源选择审核记录保持原样。

**Architecture:** 按[独立 Astra max 裁决](../../resource/kifu-name-selected-event-link-decision-2026-10-02.md)扩展现有名称批次，新增 `selected_event` 槽位，复用事务、来源证据、名字批准和前后像账本。新格式 4 明确区别于旧选择格式 3，读取端只接受原来源后像或经单一有效名称批次证明的 `NULL → event_id` 转移。显式只读导出 v4 清单时，尚未关联的选择也编码为 `event_id=null`，供首次审核和导入；同版本重算前像。首轮仅允许空 FK 到已核赛事 ID，批次撤销采用整批原子条件撤销。

**Tech Stack:** Python, SQLAlchemy, PostgreSQL/SQLite, FastAPI, pytest. 本计划不授权正式环境数据写入、严格模式切换或原始 SGF 修改。

**Spec:** `docs/resource/kifu-name-selected-event-link-decision-2026-10-02.md`；总计划 `docs/superpowers/plans/2026-10-02-kifu-full-name-localization.md`。按 `@superpowers:test-driven-development` 实现，完成后按 `@superpowers:requesting-code-review` 独立复核。

---

## 文件职责与约束

| 文件 | 此切片职责 |
| --- | --- |
| `katrain/web/kifu/event_selection.py` | 来源选择与后续关联的共同读取证明；来源批次先验与撤销顺序 |
| `katrain/web/kifu/name_inventory.py`、`scripts/kifu_name_inventory.py` | 显式只读 v4 导出及逐盘选择/关联证明摘要；旧 v2/v3 哈希不变 |
| `katrain/web/kifu/name_candidates.py` | 格式 4 有限 `selected_event` 成员、范围、独立签审和十一语验证 |
| `katrain/web/kifu/name_batch.py`、`scripts/kifu_name_batch.py` | 同事务导入、主键 `album_id` 的前后像记录、可信 bundle SHA 的 CLI 入口、全有或全无撤销 |
| `katrain/web/kifu/identity.py`、`katrain/web/kifu/name_coverage.py` | 共用经证明的选择及有效赛事 ID；无证据时保留缺口 |
| `katrain/web/kifu/name_match.py`、`katrain/web/kifu/name_structure.py` | v4 只读候选/分组兼容；不从同名自动判赛事身份 |
| `tests/web_ui/test_kifu_event_selection.py`、`test_kifu_name_inventory.py`、`test_kifu_name_candidates.py`、`test_kifu_name_batch.py`、`test_kifu_name_api.py`、`test_kifu_name_coverage.py` | 每一步的最小反例、正例和回滚 |

## Chunk 1：可验证的关联证据与清单

### Task 1：冻结精确成员契约

- [ ] 在 `tests/web_ui/test_kifu_name_candidates.py` 先写红灯：旧 `bundle_format=3` 不接受 `selected_event`；新格式 4 的成员必须带 `album_id`、原选择批次完整摘要、原选择后像及 SHA、SGF SHA、目标 `event` ID/ref、原 album/context SHA、全局原文作用域 SHA、独立 `identity_review`。v4 的 `identity_scope_sha256` 单独增加这些选择证明字段和成员类型，旧格式摘要逐字节不变；同一 `album_id` 替换来源批次、第二 GN 原文或来源后像，旧签审必须失效。从 v3 清单或其他 `GNUGo3.8` 盘挪用签名须失败。
- [ ] 运行 `uv run pytest -q tests/web_ui/test_kifu_name_candidates.py -k selected_event` 确认失败。随后在 `name_candidates.py` 增加格式 4 allowlist 与 `selected_event` 专属校验；重用已有 `identity_scope_sha256`、目标声明、来源检查和十一语门槛，不从同名、同届或 SGF 一致性推断身份。旧格式 1/2/3 的规范哈希和验证结果不变。
- [ ] 仅允许 `old_id is None`，目标是已有或同批新建 `event`；链接到已有 ID 也须在本批附齐该 ID 的十一语独立批准名称。v4 写入白名单只包含本次所需 `event`/`raw_event` 名称及 `selected_event`，拒绝夹带普通 album 黑/白/赛事关联、无关 owner、其他槽位或原始字段修改。缺语种、错时期、错地域或未签署范围返回有限错误。测试转绿并提交。

### Task 2：版本 4 清单和共同证明

- [ ] 在 `tests/web_ui/test_kifu_event_selection.py`、`test_kifu_name_inventory.py` 先写红灯：原选择后像有效时默认 v3 不变；`build_inventory(..., inventory_format=4)` / `scripts/kifu_name_inventory.py --inventory-format 4` 显式导出同一只读快照，未关联选择在 `selection_format=2` 中携带 `event_id=null` 与原来源后像 SHA，因此**零关联也能导出首个 v4 审核清单**；经有效名称批次链接时 v4 增加名称批次 ID/证明 SHA。导入器用同一格式 4 重算。伪造 FK、伪造/撤销关联批次、两份活跃证明、SGF 漂移或任何来源字段改变都须被拒并使覆盖失效。
- [ ] 在 `event_selection.py` 建一个批量共享读取函数，接受连接和逐盘选择行，按来源批次/名称批次缓存完整审核工件与变更账本。来源证明先走现有 `audited_selection_images`；若 FK 非空，仅接受唯一 `applied` 格式 4 关联批次，其 `KifuNameChange.before_image` 精确等于原来源后像、`after_image` 精确等于现行完整行，且审核工件规范 SHA、有限成员、独立签名、目标/ref 解析相符。保留 `selection_matches_audit` 对原后像的严格比较，不能通过忽略 `event_id` 绕过证明。
- [ ] `name_inventory.py` 在显式 v4 导出时对未关联选择输出原来源证明和 `event_id=null`，对已关联选择仅在关联证明有效时输出非空 FK；基本 album/source SHA 独立固定，选择补充增列证明字段。无有效证明的非空 FK 不可退化成旧 v3 合格行，必须形成可见漂移。旧 v2/v3 工件和哈希逐字节兼容。v4 的 `build_event_group_manifest` 仍须传入独立固定的完整 inventory artifact SHA，不可因扩大格式白名单绕过 v3 的外部钉住。运行聚焦测试并提交。

## Chunk 2：原子导入与条件撤销

### Task 3：名称批次写入选中赛事 FK

- [ ] 在 `tests/web_ui/test_kifu_name_batch.py` 写红灯：一条已审核选择 `NULL→现有事件 ID`，以及同批新建赛事 ref、十一语名称和关联；只变更 `kifu_album_event_selections.event_id`，原 album/SGF/来源选择批次不变。精确前像、目标目录、SGF、独立摘要任一变化时 dry-run/apply 都零写入。
- [ ] 给 `KifuNameChange` 对这张表显式使用 `album_id` 主键；`_UNDO_TABLES` 只增加这一明确表。`name_batch.py` 的锁先后统一为名称批次锁 `720220261002`、来源选择锁 `720220261003`，`event_selection.py` 来源写/撤销也依同序拿锁；在一个事务里重查格式 4 清单、全成员审核、目标名称前像和当前选择后像后更新 FK，记录完整 before/after。已有格式写路径不改语义。
- [ ] 格式 4 `apply` 必须接收**独立审核记录中的可信完整 bundle SHA**；`scripts/kifu_name_batch.py` 增加显式 `--expected-bundle-sha256`（格式 4 必填），透传到 `dry-run/apply` 并对规范 bundle 内容重算校验，不能从待导入包自身取所谓可信值。已应用同哈希重试需重查账本、目标与现行后像才返回 `already_applied`，已撤销哈希不重放。补 CLI 缺参/错哈希、并发/过时前像测试、运行 `uv run pytest -q tests/web_ui/test_kifu_name_batch.py`，提交。

### Task 4：整批撤销与来源选择先后

- [ ] 先写红灯：格式 4 正常撤销先复原选择 FK，再撤销名称/新事件；后来任何选择改动、名称改动、外部依赖或 SGF 漂移，使**整个批次**拒绝且零部分撤销。来源选择批次在有效 FK 存在时撤销失败；名称关联撤销后来源选择才可撤。
- [ ] 对格式 4 单独预检全体当前 after-image 和依赖，再在同一事务逆序撤销；任何失败整批 rollback，不返回旧版的 `partial_undo`。来源 `undo_batch` 在相同锁顺序下查活跃关联证明。原格式旧 `partial_undo` 保持。运行两模块聚焦测试并提交。

## Chunk 3：API、分组、覆盖和隔离演练

### Task 5：读写同一权威状态

- [ ] 在 API/覆盖测试先写红灯：有效格式 4 事件关联在列表、详情、跨语检索和 count 查询显示**完整原文或经过批准的赛事名称＋届次/轮次组成部分**；例如第二 GN `28th Honinbo Final` 只有 `Honinbo` 核心十一语名称时仍计缺口，直到完整赛事字段或该结构的组成部分显示获批。源 `event='GNUGo3.8'` 和 SGF 仍原样；未批准目标语言、证明撤销、SGF 漂移均输出待核缺口，不能把假 FK 当真。格式 4 的清单/覆盖 SHA 在 FK 变化时变化。
- [ ] `identity.py`、`name_coverage.py` 使用 Task 2 同一批量证明及现有严格组成部分规则，不各写放宽规则。`name_structure.py`、`name_match.py` 接受有效 v4 清单用于只读待审分组和匹配，不把程序标签归并成赛事；v4 分组继续核对外部完整清单 SHA。复用当前列表当页批量路径，避免逐盘审计查询；运行 `uv run pytest -q tests/web_ui/test_kifu_name_api.py tests/web_ui/test_kifu_name_coverage.py tests/web_ui/test_kifu_event_group_manifest.py tests/web_ui/test_kifu_name_match.py`，提交。

### Task 6：独立复审和受控备份库验收

- [ ] 对全改动执行聚焦 pytest、`git diff --check`；独立代理审核来源证明、身份范围、锁顺序、前后像、整批撤销及 API/覆盖一致性。修复 Critical/Important，并复审至通过。
- [ ] 只有真实来源与十一语名称均获独立批准的**有限子集**，才在 `home-ubuntu` 的隔离备份库使用同哈希工件 `validate → dry-run → apply → API/覆盖抽查 → undo`。逐次断言数据库名和原 SGF/album 字段摘要；若尚无合格子集，保留代码夹具验证并记录数据阻塞，不造假批准。
- [ ] 正式库仍维持 `KIFU_STRICT_NAMES` 关闭和无数据写入；最终全库十一语 100% 门槛按总计划验收后才按既定测试→正式发布流程执行。
