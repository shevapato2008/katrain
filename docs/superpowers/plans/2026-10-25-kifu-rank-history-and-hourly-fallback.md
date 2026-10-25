# 棋手等级历史与小时回退 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** TEST对原谱缺等级的合法近期新谱，按可靠已存在人物身份冻结库内最新已知等级；保留人物升段历史，并将同一已验证快照原生发布PROD。

**Architecture:** 沿用kifu_players和现有身份/名称/TEST→PROD发布管道，仅增加人物rank history/current投影、每盘rank snapshot及确定性适配。原SGF、原rank、旧包/回执不动；新包固定rank/provenance，不在重试或PROD重新选择当前资料。只用本轮有界候选人物，不新增全库扫描或队列平台。

**Tech Stack:** 现有Python、SQLAlchemy/PostgreSQL、httpx、pytest、JSON canonical SHA、既有stage原子文件及原生发布日志。

---

状态：**用户已授权实施和真实发布；先fresh Astra Max最多两轮计划审核，Approved后实施，完成后独立代码/实际效果复审。** 基线实际fetch的develop2e7640d892e311f3fc8ed70d4dc5a32e470d2ddf；隔离分支feature/kifu-rank-fallback-20261025。保持其他UI分支与未跟踪报告。首切片仅库内已绑定身份、最近明确原始等级及现存可靠官方证据；不引入任何外部人物定时爬虫或新增LLM。

代码阶段已完成：`727fecb97` 已获 fresh Astra Max Approved，整体规范审也已通过。审核发现的同日矛盾到达顺序、同内容事实的不同观察时刻合包、v2 省略原等级断言三项均已最小修复并复核。真实 PostgreSQL 迁移、三 ID TEST→同包 PROD 纠正/重放、线上 API 和同源 RK 验收继续按发布门执行；此状态不表示已经上线。

## Chunk 1: 最小数据基础与有界来源

实施进度：foundation 已在 `32f1273812e` 完成，规范审与质量审均 Approved；聚焦 113 项通过。审核补齐了启动 DDL 排除、迟到冲突、损坏 SGF 单人隔离及 typed/unknown 到达顺序。临时 PostgreSQL 演练尚未取得环境，不将 SQLite 结果称作 PostgreSQL 并发证据；发布前显式迁移及约束核对仍须执行。其余 chunk 继续实施，尚未部署。

### Task 1: 两张增量表与纯等级解析

**Files:**
- Modify: katrain/web/core/models_db.py（新增class，不改已有KifuPlayer/KifuAlbum字段）
- Create: katrain/cron/migrations/004_kifu_player_ranks.sql（当前最大版本003，实施时复核）
- Create: katrain/web/kifu/player_ranks.py
- Create: tests/test_kifu_player_ranks.py

- [ ] 写失败测试：9p/6d/6k明确区分；“七段”没有身份不能默认d/p；人物证据可补职业身份而不改变原谱明确等级；3002不是rank；同名多实体拒绝自动命中。
- [ ] 隔离DB测试先验证失败，再实现最小解析/表。候选核心列如下（非可直接上线DDL，约束须同步models/迁移）：

```text
kifu_player_rank_history
  id PK; player_id FK kifu_players
  rank_value positive int; rank_system professional_dan/amateur_dan/kyu/dan_unspecified
  source_as_of DATE NULL; valid_from DATE NULL
  observed_at TIMESTAMPTZ NOT NULL; last_checked_at TIMESTAMPTZ NULL
  source_kind; source_ref JSON; evidence JSON; content_sha256
  status qualified/conflict; is_current bool
  UNIQUE(player_id,content_sha256)
  UNIQUE(player_id) WHERE is_current
  INDEX(player_id,source_as_of)

kifu_album_rank_snapshots
  id PK; album_id FK kifu_albums; side black/white
  rank_fact_id FK rank_history ON DELETE RESTRICT NULL; snapshot JSON; snapshot_sha256; publication_key; native_batch_id
  INDEX(rank_fact_id)
  UNIQUE(album_id,side)
```

- [ ] current就是同一history表的active行。变更时先锁定有界人物/当前行、再插新历史/切active，事务原子；不得只取MAX(rank)。相同来源/内容事实重试去重；不同依据日期/不同准确原谱的同值等级可追加观察并推进source_as_of，不称升段事件。rank/首观察/原始证据不可静默改写。content SHA不含本地ID、active标志或重试时刻。
- [ ] source_as_of是资料对等级的依据日期，valid_from只在来源确认准确升段日期时填；未知保留null及原日期精度文字。明确区分observed_at与snapshot.matched_at。
- [ ] 约束测试：两个current并发不能都成功、历史7p→8p保留、无升段日期不自动填now、晚上传旧比赛不降级当前投影。已有rating_history/users不复用。
- [ ] `pytest -q tests/test_kifu_player_ranks.py`应通过；迁移只对临时PG演练。提交此最小基础。

### Task 2: 按已绑定人物批量得到最新已知rank

**Files:**
- Modify: katrain/web/kifu/player_ranks.py
- Create: katrain/kifu_ingest/ranks.py
- Create: tests/test_kifu_rank_sources.py
- Evidence fixtures: 从本调查字段表抽取六人最小公开片段，禁止整份全库inventory进fixture。

- [ ] 先写测试：按人物稳定本地ID批量查current；无cache时只查询这些ID关联的非空原始rank；同日候选冲突不按id任挑；来源SGF日期旧但created_at新不能胜过近期资料；绝不把新fallback快照当原始rank再次传播。
- [ ] 复用catalog.lookup_qualified_identities的id/canonical/status。i18n不是身份索引；canonical/alias归一化命中0或多个就不补，维持原有身份隔离。不要按姓氏/模糊名/当前账号rank匹配。
- [ ] 实现一组最多200名唯一人物的current批量读；必要最近原始rank使用现有black/white_player_id索引的UNION查询，SQL statement_timeout建议5秒。不得扫描SGF正文或整个库，不为本需求增加全库索引工程。返回相同最高依据日期的冲突统计，不能LIMIT1吞冲突。
- [ ] 初始化先限本调查六人；rank grade候选是7/4/5/5/5/7，职业类型须绑定相同人物的官方证据。日本棋院只解析目标人物“棋士段位”标签；中国棋协只取精确playerNo及playerName那一条，不能取邻人；不能用正文第一处“段”（可能是父亲/老师）。名称approved不是任意rank正文approved，保留确切来源/path/hash和解析版本供复核。
- [ ] 首切片只读库内当前事实、已绑定人物关联的最近原始rank及已有可靠官方捕获；不发外部profile请求。来源不够/同名歧义/职业类型不能核实时留空并继续。外部profile TTL刷新仅非阻塞后续项，禁止实现新爬虫、rank LLM、逐卡HTTP、PROD刷新器或collect-history。人物更新先来自后续已处理明确rank的新谱或显式审定的有限资料维护。
- [ ] 优先级：本盘明确源rank → 同一人物已核定当前/最新已知rank；库内新谱明确rank和官方人物资料都可更新人物投影，按依据日期/来源质量选，不按观察时间或段位数字最大值选。职业段位下降、跨职业/业余系统冲突不自动切current，须复核；不能仅因资料刚抓到就覆盖可信较新等级。冲突/未核身份不补、记录原因；过时依据仍可作为“库内最新已知”但标其日期与刷新延期，不伪称当日已确认。
- [ ] 输出rank_from_library/unknown_identity/unknown_system/conflict/profile_refresh_deferred与依据年龄的聚合日志；单人不明不挡合法新谱。
- [ ] `pytest -q tests/test_kifu_player_ranks.py tests/test_kifu_rank_sources.py`通过后提交。

## Chunk 2: 冻结、原生发布与API完整验证

### Task 3: 冻结一次的rank快照与可重放新包

**Files:**
- Modify: katrain/kifu_ingest/orchestration.py:159-211/325-340
- Modify: katrain/kifu_ingest/staging.py（新增独立rank快照存取）
- Modify: katrain/kifu_ingest/catalog.py:255-296/1342-1605
- Modify: katrain/cron/jobs/kifu_ingest.py:790-836
- Modify: katrain/web/kifu/name_batch.py（只扩rank新增表的undo/journal支持，保留旧proof/inventory语义）
- Test: tests/test_kifu_incremental_preparation.py、tests/test_kifu_incremental_decision_resume.py、tests/web_ui/test_kifu_incremental_catalog.py

- [ ] 先写失败测试：源BR9p+人物8p仍为9p；源空+人物7p冻结7p；人物升8p后同一prepared/已冻结包重试仍7p；TEST/PROD人物id不同但相同逻辑身份成功；歧义、错黑白、错SGF SHA、来源hash错误均拒绝。
- [ ] 在prepare已有可靠resolved/portable身份检查后、外部名称调用前，批量解析需要回退的slot；把结果先原子持久到stage/rank-snapshots。v2同时冻结所有可靠已绑定人物的明确source rank_observations，source/library_current/unknown决策分开；原rank缺失断言仅约束fallback不得覆盖源，不能阻断source observations更新current。键绑定sourceID+原SGF SHA+两侧canonical+policy，已有文件不得覆盖。原source_metadata、source fingerprint和raw SGF不变；无rank也冻结显式unknown，避免同包重试漂移。
- [ ] 新包使用显式新格式（建议kifu-incremental-manifest-v2），旧v1包及原receipt恢复仍支持。v2每game增加rank_snapshots，其内容被manifest SHA完整覆盖；不把profile rank塞进原metadata再绕过derive校验。旧receiver须因不认识v2拒绝，不能忽略新字段后假发布成功。
- [ ] 建议冻结slot契约：

```json
{
  "version":"kifu-rank-snapshot-v1",
  "origin":"library_current",
  "rank_value":7,
  "rank_system":"professional_dan",
  "player_ref":{"canonical_name":"已唯一绑定的人物规范名"},
  "rank_fact_sha256":"固定资料内容SHA",
  "source_ref":{"kind":"explicit_album_rank","source_key":"19x19","source_item_id":"准确ID","sgf_sha256":"原依据谱SHA","slot":"white"},
  "source_as_of":"2026-10-19",
  "valid_from":null,
  "observed_at":"资料被系统观察的UTC时间",
  "matched_at":"本次首次准备时的UTC时间",
  "identity_evidence":{"source_url":"官方人物来源","body_sha256":"固定证据SHA","subject_key":"已绑定官方人物ID"},
  "policy_version":"library-rank-fallback-v1"
}
```

- [ ] TEST原生发布在既有publication guard/事务内对fallback验证source rank真的缺，对source observation验证准确原SGF/metadata字段，二者都验证canonical identity精确且未换人、规范化rank事实及每盘绑定一致。rank fact自身必须携完整可核算内容，grade来源及职业身份来源各自有准确subject/字段/最小证据/hash；不能只传不可核算的rank_fact_sha256。然后同一事务落本地history/current和album snapshot；锁既有player行覆盖尚无current的并发。PROD只验证/接收同一已验证快照，按当地canonical解析ID，不读取最新人物资料重算这盘等级、不抓源、不翻译。旧包重放不把PROD更新的current8p降回7p，但这盘旧snapshot仍7p。
- [ ] 原生receipt/artifact含rank内容hash和新增行日志。新增表不加入旧名称proof的全库hash输入；rank有自己有限范围的前后像/hash，沿既有native journal/undo检查完整前像。已有KifuPlayer/KifuAlbum列形状、原SGF字段、原包checksum均不改变。
- [ ] 保留sourcePG+Stage writer+native publication guard边界；不引入新写线程或在旧线程未结束时重启写者。来源600秒/后段300秒边界、3300秒协作预算和既有模型限额不放宽；rank有界HTTP计入全轮余量。当前首次publish暖缓存慢路径依旧存在，不宣称顺便修好。
- [ ] 聚焦上述三组测试与现有state/source预算回归通过后提交。

### Task 4: API按批次读取、源值优先、五语验证rank

**Files:**
- Modify: katrain/web/api/v1/endpoints/kifu.py:98-118/480-543（summary/detail/list统一）
- Modify: katrain/kifu_ingest/sync.py:171-224
- Modify: katrain/kifu_ingest/verification.py:85-101
- Create: tests/web_ui/test_kifu_rank_snapshots_api.py
- Extend: tests/test_kifu_api_verification.py

- [ ] 写API测试：明确源9p/6d/6k及源中文等级优先，人物当前更高也不覆盖原等级；仅原rank缺失读取该盘snapshot；仍未知display null/空。职业身份不明不能自动当业余，补充身份也不得把原明确9d翻成9p。
- [ ] 本页album IDs一次批量读snapshot，不在每张卡查询人物或HTTP。新增来源信息可放detail/审计字段；列表只返回已经决策的display rank，前端不承担归一化/人物查找。原black_rank/white_rank仍是原数据。
- [ ] v2验证除原五语姓名/赛事/SGF/来源/公开卡片外，增加raw ranks、display ranks、snapshot SHA与origin一致性；任一未过不得prod_synced。TEST和PROD列表/详情采用同一快照，不因当前资料不同漂移。
- [ ] v2的verify_album_api最终保留rank-aware有限报告，send_verified_manifest与PROD receive共同严格校验算法版本、manifest SHA及准确sourceKey/ID/slot/SGF SHA/snapshot SHA/origin/raw和display ranks与五语详情+公开卡片检查的有限摘要，不只计数album/lang；旧式报告即使换成正确v2 SHA仍拒绝，缺一侧或一语/公开检查拒绝。新rank-aware checkpoint算法/manifest绑定只适用于v2；旧v1原检查点/receipt验证保持兼容。新rank结果不能靠旧名字检查点冒充通过。
- [ ] 集成baipu现成UI commit1704114fa4f7dc4f693402f57a99c02cccc8088d（fix/kiosk-hide-missing-ranks-20261025），不重复写UI。空rank不渲染节点、职业/业余/级明确格式保留。最终对同版本1024×600实际页面复核。
- [ ] `pytest -q tests/test_kifu_player_ranks.py tests/test_kifu_rank_sources.py tests/test_kifu_incremental_preparation.py tests/test_kifu_incremental_decision_resume.py tests/web_ui/test_kifu_incremental_catalog.py tests/web_ui/test_kifu_rank_snapshots_api.py`应通过。另运行tests/test_kifu_api_verification.py和tests/cron/test_kifu_hourly_orchestration.py；无需无关全UI/全GPU回归。提交。

## Chunk 3: 既有近期谱的有限纠正与发布验收准备

### Task 5: 独立原生纠正入口，不重置小时状态

**Files:**
- Extend: katrain/kifu_ingest/ranks.py（构建/验证有限correction manifest）
- Create: scripts/kifu_rank_correction.py（默认dry-run，显式ID白名单）
- Create: tests/web_ui/test_kifu_rank_correction.py
- Create: docs/operations/kifu-rank-fallback.md（在实施分支内）

- [ ] 测试：初批三ID，绑定sourceKey/ID+原SGF SHA+原rank+人物FK/逻辑身份+原snapshot完整前像；原rank已有值、名字变了、SGF变了或overlay已被后来更新则拒绝。
- [ ] 新logical correction key由有限成员+固定rank事实+policy hash决定；复用v2原生发布中“same exact SGF→reused album”路径，仅追加/明确纠正rank overlay与其行日志。不能insert新谱、重新翻译、改raw ranks/SGF/source link，不能原地改旧包或receipt。
- [ ] correction作为独立native batch/receipt生命周期，先TEST公开API完整验证，再同一包PROD；不回退或改绑原StateStore已prod_synced的item/publication进度。重放already_applied/零新增；撤销也按当前前像检查，保留历史证据。
- [ ] 初次dry-run固定91694911、91638738、91637528；本次用户已授权按准确原SGF hash、原rank空及身份CAS有限真实纠正，先dry-run与审核再执行同包TEST→PROD。若未来扩展仅明确近期窗口+限100的另一批，不自动扫描全库，不追2021旧源。
- [ ] 临时SQLite/PG完成新谱发布一次、同包重放、人物升段后旧包重放、旧谱correction一次/重放/拒绝冲突的聚焦测试，保存预期before/after。不得用模拟测试称线上已完成。
- [ ] 本独立负责人按已获授权安排fresh Astra审计划与最终代码/数据完整性/实际效果；按项目fetch/feature→develop→Smartbox parent规范集成/push。先安全加TEST/PROD两新表、部署兼容receiver/API，再启用TEST producer；PROD不采集。保留队列/stage/预算/锁/GPU/DB/MinIO。与主session协调RK非并发窗口，部署包含1704114fa的同源build，不能以旧RK“未记录”界面验收。
- [ ] 真实验收至少一盘源rank空的新谱：唯一身份→库内rank事实→固定snapshot→完整TEST→同包PROD→两库/API等级与origin一致；再重跑证明不重译/重导且旧包未漂移。另验证一盘原rank明确与人物当前不同，原值仍优先；失败/未知完全隐藏不挡合法谱。

实施前需Astra重点审：现有rank原始证据的职业身份提取；source_as_of与valid_from区别；无全局人物UUID时沿现有逻辑身份的便携绑定；v1兼容且v2 fail-closed；native有限日志/undo不破坏原名称proof；预算/单写者/幂等；旧prod_synced进度保持；API source-first。

## 交付门槛

计划最多两轮Astra Max；独立审核必须使用gpt-6-astra/max/fork none。实施按SDD拆为数据基础、冻结/发布/API垂直切片和真实发布纠正；规范审与代码质量审清零再推进。最终报告需明确每个已发布commit、运行镜像/模块hash、source空rank真实样本→匹配→snapshot→双库/列表/UI、三ID纠正及重放、无额外翻译/重复入库、人物升段不漂移旧包、未知隐藏、RK实际版本。所有当前等级均“库内最新已知”，valid_from未知不得用采集日伪造。

## Astra Round1集中修正（Round2审核依据）

- **R1观察路径**：v2对所有可靠已绑定人物都固定明确source观察，另固定每盘source/library_current/unknown选择。prepare不写history；native同事务提交。来源/内容相同重试去重，不同依据日的同值7p是新观察，不是新升段。较旧依据不回退；同日不同等级、职业降段/系统冲突使该人物唯一current进入conflict，后续fallback返回unknown而不是继续使用旧qualified值；本盘明确raw rank及合法谱仍继续。current部分唯一索引覆盖所有status的is_current行。验证7p→明确8p新谱→下一空rank谱得8p，旧7p包重放不变。
- **R2接收资格**：v2报告用新的固定rank-aware algorithm和有限完整检查内容，绑定manifest、source/slot/SGF/snapshot/origin/raw/display及五语详情/公开卡片，producer send与receive共用校验。缺少rank验证的v1式count-only报告拒绝；事实SHA可从包内规范化不可变内容重算，等级证据与职业身份证据分别校验精确来源，不依赖receiver查今天profile。v1原行为/hash保留。
- **R3引用/撤销与重放**：每盘snapshot落当地rank_fact_id外键(RESTRICT)+索引，rank native undo在任何写前检查后来仍保留的snapshot/receipt引用和current前后像变化，存在依赖或后来current改变则整笔拒绝，不级联/不改后来包。旧包正常重放只核不可变fact内容/每盘快照并返回原receipt，忽略is_current/last_checked_at正常变化且不回退current；若该盘overlay已被显式纠正可以fail closed，不能覆盖新overlay。聚焦测试A建H、B不改H但引用H，undo A零修改且拒绝；7→8后旧包replay仍旧快照/新current。
- **v1/v2识别**：catalog.py的known publication来源、native receipt authority、applied replay、source/undo依赖与artifact生成六处都识别两版，不能只改FORMAT常量。迁移不改变旧名称proof/inventory的字节语义；rank journal额外支持DATE ISO往返。
- **rank-only纠正**：共享native publisher的显式rank-only分支只取3个准确source路径/SGF/身份/完整前像，复用publication guard/journal/receipt，跳过全库SGF暖缓存、全库去重和姓名续审。它不insert album、不改源link、不重译，不建立新发布平台。原StateStore已prod_synced记录完全保持，纠正有独立key/receipt及TEST→PROD验证。
