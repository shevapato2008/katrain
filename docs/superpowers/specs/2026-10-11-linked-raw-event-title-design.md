# 已关联赛事的有限 SGF 标题直译

## 决定与范围

**批准方案 A：新增明确的 linked SGF literal 路径。** 决策者为用户授权的独立 `/root/resume_catalog_cn_code_review_astra`，父代理配置为 `gpt-6-astra / max`。本文件批准设计；190 个名称仍须按实际前像绑定、独立审签后执行。本次只读本地代码和已留存材料，并写此设计文档。

目标是让已经关联正式赛事的原始标题获得五语显示名，同时保持其字面年份、届次和正式关联。当前有限集合为 38 个 raw owner、190 个候选名称、TEST/PROD 各 7,615 个不同的公开非重复棋局。品牌修订和在途棋手批次沿用原路径，不依赖本改动。

| 方案 | 判断 |
| --- | --- |
| A：独立 profile/basis，SGF 字面标题加既有核心来源，保存完整译文 | 采用。复用现有 owner 审核、名称证据、事务和共享 reader，只增加明确分支。 |
| B：每个系列新增专用 composed 模板和依赖对象 | 本轮不采用。需要逐系列扩展规则；当前只需有限、逐条审签的译文，已有 Honinbo composed 路径继续保留。 |

## 已核实的阻塞原因

- `scripts/kifu_raw_event_title_owners.py` 的 `_scope_rows` 要求全部 `event_id IS NULL`；`_english_event_refs` 另要求 `event_edition_id IS NULL`；prepare/inspect 还要求 owner 完全没有旧名称。
- `raw_event_translation.py` 的研究验证只接受旧 `sgf_literal_v1`，逐行要求 NULL event；英文 parts 只接受 core/edition。实际 `Oteai 1973` 的既有 parts 是 `core="Oteai"`、`year=" 1973"`，也会被拒绝。
- `name_evidence.py`、`name_candidates.py` 根据旧 basis 决定 SGF 来源豁免、capture 时间和 owner/scope 绑定。只修改 owner 脚本会在后续阶段失败。
- `name_batch.py:_check_raw_owner` 再次要求未关联棋局。`identity.py` 的 `_raw_event_map`、`strict_raw_event_search_clause` 同样只让 translated 名称作用于 NULL event；显示和 strict slot 还存在正式名称及 Oteai canonical 特判。
- 两库这 38 个 owner 均为 pending，且各有一行旧 CN `review/direct_translation` 名称，`evidence_id/revision` 均为空。应按精确前像升级，不能先删掉旧名来满足无名称条件。两库 Oteai 的正式 ID 不同：TEST=1、PROD=22，不能跨环境复用 ID。

## 最小数据与验证契约

### 1. 显式选择新路径

新增 `source_basis="linked_sgf_literal_v1"` 和 `owner_profile="sgf_english_linked_event"`。继续使用 `decision_kind="translated"`、`translation_method="literal_event_title"` 及现有 `raw-event-title-translation-v1` 证据/名称版本；新 basis/profile 必须在 owner marker、research、candidate 绑定中一致。未知、缺失或混用标记拒绝，旧 unlinked profiles 的条件原样保留。

新 profile 本轮仅接纳已有 parser 保存的三种形状：单独 core、正确英文序数的 core/edition、`oteai_year` 的 `Oteai` 加一个原样空格及四位年份。parts 必须逐字拼回 raw，并等于 owner 中现存的 parts；不得重解析、改写 parser 字段，或把未解析的年份/序数藏进 core。其他字面形状另行审核。

### 2. 冻结真实棋局范围和现有 FK

每个 raw 的 manifest 保存完整、排序、无重复的物理匹配 album IDs，以及每行 `event`、`event_id`、`event_edition_id`、可见/重复状态、`source_path`、原 SGF SHA-256 和已有 scope 字段。明确使用 `game_total`，不把关联数量写成 `current_null_games`。

本路径要求每个 raw 的全部物理匹配棋局都公开、非重复、无 event selection，且关联到 manifest 中同一个已审核系列的非空正式 event ID。现有 `event_edition_id` 可为 NULL 或合法现值，逐行冻结并保留；它不授权建立或修正任何届次关系。混合系列、额外/缺失棋局或 selection 冲突使该 raw 停止，不能通过过滤冲突行缩小范围。

保留每局原始 EV/GN 数组和 SGF 字节哈希；沿用已明确的 EV 优先、EV 缺失才取首 GN 的规则，选中的标题必须逐字等于 raw。SGF 内容、来源路径、身份 FK、届次 FK 均不写入。SGF 冲突的原文留待处理，不能为了通过改用另一标题。

现有 post643 的 15,045 行捕获只有 `id/event/event_id/duplicate_of_id/list_hidden_reason` 五字段，足以确认这 7,615 局的当前可见性和正式关联，**不足以充当 SGF/edition/source 的完整绑定**。准备阶段仅对选定 38 个 raw 补捕获一次上述必要字段，并分别冻结两库完整 owner、旧名称及有关 evidence 前像。

### 3. 来源事实与译文事实分开记录

原始完整标题由 SGF 见证；系列含义与五语核心用名复用已经审核的 Oteai、Honinbo、Old Meijin、Oza、Judan、Nihon Ki-in Championship 来源。新增一个有限 `reviewed_core_refs` 列表，记录既有审核材料的路径/内容 SHA、准确段落或条目、所支持的核心和语言，以及用途；准备时校验留存材料的真实字节。相关决定/摘录随 research 保存，由研究与候选哈希绑定；线上 reader 不依赖本机文件路径或重新访问网页。

已有 HTTP captures 继续记录真实 URL、正文 SHA、摘录和时间；既有审核文档引用放在 `reviewed_core_refs`，不伪造为 HTTP 200 capture。新 basis 要求非空且与当前核心相符的审核依据，可复用同一核心来源支持多个逐条列明的年份/届次。五语完整译文由独立 reviewer 审核，保存准确年份、数字、期/届单位和身份限定词，标记为直译，不宣称逐届完整标题已被外部出版。SGF 的英文字面来源也不表示日本赛事的历史原名是英语。

不新增通用模板引擎，不要求逐届重新取得全文 HTTP 见证，不改变来源 registry 的语言/身份边界。

### 4. 原事务与精确前像写入

owner 审批仍只更新 `review_status/review_metadata`。新 profile 可接纳 manifest 精确列出的旧 `review/direct_translation` 名称且无 evidence/revision；完整名称集合发生变化即拒绝。旧 profile 的无名称要求不变。

随后名称批次复用现有 `name_preimage_sha256`：原 CN 行保留 ID/created_at，按精确旧行更新；其余四语要求实际空前像。owner 审核和名称写入各自保留真实独立签名、可信外部 bundle hash、原锁、前/后像 journal、重放与撤销机制。名称 apply 在原事务锁内重新核对完整 scope，包括 SGF hash、全部现有 FK 和 selection 缺席；不能只信较早的 owner 审批。`album_links=[]`，不创建、合并或修改正式赛事、alias、album/SGF/source。

### 5. 同一资格用于展示、搜索和计数

`eligible_literal_raw_name` 校验新增 basis 的持久化 owner/候选/研究/独立审批后，reader 保留其有限 scope。资格必须落到具体 `(album_id, raw, event_id)`，并核对当前 edition FK、可见/重复/selection 状态、来源路径和 SGF hash；新增同 raw 棋局不自动继承，某局漂移只使该局的新名称失去资格。不得退化为 raw 字符串全局映射。

通过上述资格的完整 linked 标题作为该局的精确标题，优先于通用系列名称；仍遵守既有 obscured/selection 排除。它自身已有完整原文、系列身份和五语译文审批，不再依赖 canonical 必须写作 `Oteai` 或另一个可变的正式显示名。其他旧名称路径、碰撞及歧义策略不变。

展示、详情、翻译名搜索、`strict_slot_approvals` 使用同一资格判断。按当前页面或该次搜索的有限候选 IDs 批量读取必要字段/SGF hash，避免逐棋局触发 deferred SGF 查询，也不在请求中扫描全库。搜索 SQL 和 Python 展示判断必须给出同一有限成员结果。

## 需要修改的文件及部署

| 文件 | 本次职责 |
| --- | --- |
| `katrain/web/kifu/raw_event_translation.py` | 新 basis/profile、有限 year 形状、来源引用、scope/owner/持久化资格验证。 |
| `scripts/kifu_raw_event_title_owners.py` | 显式 profile CLI、完整 linked scope/SGF refs、旧待审名称集合 CAS、owner 元数据审批。 |
| `katrain/web/kifu/name_evidence.py` | 新 basis 对应的真实 SGF 原文来源分支，仍核来源与独立审签边界。 |
| `katrain/web/kifu/name_candidates.py` | 新 basis 的 capture 时间、parts/owner/scope/research 精确绑定。 |
| `katrain/web/kifu/name_batch.py` | 名称 apply 在锁内重新验证 linked 完整 scope；复用已有名称前像、journal、碰撞机制。 |
| `katrain/web/kifu/identity.py` | 有限 scope 映射、精确标题优先级、搜索和 strict slot 一致资格。 |

在现有 `test_kifu_raw_event_title_owners.py`、`test_kifu_raw_event_title_translation.py`、`test_kifu_name_api.py`、`test_kifu_name_coverage.py` 中补必要用例，复用已有 fixture，不另建审计框架。coverage 生产模块已经调用共享 reader，原则上不需要改算法；保持 API 返回数量/字段契约。

**零 DDL。** 元数据存现有 JSON、名称/evidence/journal 表。实际 R23 PROD 与 R21 importer 的旧 ORM 未映射 `event_edition_id`，实现应像既有 owner 脚本一样，批量读取现有物理列，不以换入整份 repo `models_db.py` 解决。无需新增模型、前端或 API endpoint 叶。

发布叶为上表六个文件：web reader 部署五个共享模块，importer/覆盖统计运行环境部署五个共享模块加 owner 脚本，使用同一审核版本。保留当前实际 image、Compose 链、env、static、R23 endpoint 和其他服务，只更新所需叶；实际 baseline 漂移即停止。先 TEST 的真实调用和名称批次通过，再 PROD；reader 与 importer 均升级后才写入新 basis。旧 reader 不支持新证据，因此失败时停止后续写入，按原 batch 撤销/发布回滚步骤处理，不能以健康检查替代读取资格核验。

## 验收（六项）

1. **正例贯通**：纯 `Oteai`、`Oteai 1973`、一个 Honinbo 届次和一个其他系列届次，五语候选通过 owner→research→candidate→apply→reader；TEST/PROD 各用自身 ID。旧 unlinked 样例继续通过，旧 profile 仍拒绝 linked。
2. **身份/来源拒绝**：错/缺 profile、错 parts、改年份/序数、缺核心审核引用、伪/缺审批、EV/GN 冲突、SGF/source/FK/edition 漂移、增减成员、隐藏/重复/selection 均有聚焦拒绝用例。有限成员外同 raw 棋局不得取得资格。
3. **写入完整性**：旧 CN 全行前像和四语空前像有效；任一漂移在事务写入前失败。owner/parser/原名保留边界和 journal 后像可核对；raw/SGF/source/FK 零变化；重放不新增记录，原撤销机制可还原旧 CN。
4. **读端一致**：代表性列表、详情及 exact 译名搜索给出同一成员和完整年份/届次；strict slot 与显示一致。撤销/证据损坏/现场 scope 漂移会失效，旧系列与旧 unlinked 行为不受影响；批量读取不产生每局 SGF 懒加载。
5. **实际兼容**：TEST、PROD 各用真实 image/mount/旧 ORM 验证完整导入及真实只读列表、搜索、详情请求，保留 R23 analysis handler；不是仅 import 或 `/health` 成功。无需重跑全库或全端测试。
6. **有限成果计数**：实际审签/入库后，仅对受影响的不同 album IDs 做 before/after wide、strict 五语计数；按单局资格差分，不把 7,615 直接记成新增覆盖、不按 190 名称累加。未受影响基线明确继承，P5 不因赛事名增长；实际 batch/verify 收据与所部署文件版本一起归档。

## 本次检查的固定输入

- `/tmp/kifu-next40-event-source-only-sol-20261011/next-event-38-plus-brand2-source-only-after643-v2.json`：`16d4bddd894d7cff17e41824e6a071cd5a2a666a6fd8dcd4e6c5260245ecfada`。
- 同目录 `native-route-feasibility-after643.json`：`d76ede40058b447901ae5a5b97623ca0311741ef474d27b95b3f504c67064f2b`。
- `/tmp/kifu-next-four-followup-sol-20261011/TEST-post643-union-r21.json.gz`：`c2fdf495d72b0d5a5dfc5f7161e4d2c7fd4ec64de0300124cbbca6d1e610e425`；PROD 同名文件：`c00f1aa3a23f7b1441761a9eb3470f0f72094eaf2de84e2d79b8411908b2012d`。两库均 pin batch 643；source-only 包中的十个既有来源材料 hash 已逐一核对一致。

下一步由 root 使用 writing-plans 制作小步实施计划，再按用户要求进行最多两轮独立审核；本支线不阻塞 R21 现有棋手名称批次。
