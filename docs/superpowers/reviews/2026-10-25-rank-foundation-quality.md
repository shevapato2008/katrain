# 棋手等级 foundation：独立代码质量审核

**Final Verdict: Approved — 32f1273812e5f96f0704a59c987e1fde53f9c40d**

四项历史 must-fix 已定向验证关闭，当前 foundation 范围无剩余 must-fix。下文保留最初发现和中间复审，最终证据见文末。

**初审 Verdict: Needs fixes**

审核对象：`2680a3617..946c67a895962f87c2d59ab4eb4dc2f078ac0ca8`，计划 Task 1/2 的 7 个文件。已阅读 `AGENTS.md`、实施计划和独立规范审报告，并直接检查新模块、ORM、004、startup 和测试。未修改业务代码、访问远程数据或服务、抓取新来源，也未把后续 producer/API/publisher/journal/undo 未接入列为本单元问题。

## Must-fix

### 1. P2 — 新表仍进入 startup 通用自动迁移路径

位置：`katrain/web/core/auth.py:129-144`（本次新增的排除仅限 `create_all`）；同一函数的 `:177`、`:180` 继续调用通用迁移器。`katrain/web/core/migrations.py:1109-1111` 和 `:1163-1164` 的排除集合没有两张 rank 表；`:62` 的 `PROTECTED_TABLES` 也没有它们。

现有 rank 表缺字段或索引时，启动仍会自动修改权威历史/snapshot schema，绕过 004 的 CHECK、FK、唯一约束和显式迁移边界。已在临时内存 SQLite 实际复现：先正常 bootstrap，再创建仅含 `(id, player_id)` 的 `kifu_player_rank_history` 并插入一行，第二次 `init_db()` 成功后自动添加其余全部字段和两个索引，保留的行变成 `rank_value=0, rank_system='', status='', content_sha256=''`。这不是规范审已经覆盖的“表不存在时不创建”场景。两个通用迁移器也会在 PostgreSQL 调用，不能只排除 fresh/常规 `create_all`。

最小修正：把两表集中定义为显式迁移拥有的 rank 表集合，供 startup `create_all`、`add_missing_columns`、`create_missing_indexes` 排除，并加入权威表 drift 保护。已有 rank schema 不满足时保留原数据，交由显式迁移处理；不要用默认值补历史。增加一个已有不完整 rank 表启动后零 DDL/零数据变化（或在任何变更前明确拒绝）的聚焦回归。

### 2. P2 — 迟到的旧资料会绕过职业降段冲突判断

位置：`katrain/web/kifu/player_ranks.py:645-660`，冲突判断被 `if active` 包住。

相同的两条明确职业等级事实会随到达顺序产生不同资格：

```text
8p / 2026-10-01 → 7p / 2026-10-03:
  current = 7p / 2026-10-03 / conflict，lookup 返回 conflict
7p / 2026-10-03 → 迟到的 8p / 2026-10-01:
  current = 7p / 2026-10-03 / qualified，lookup 返回 qualified
```

上述两序列均已在独立临时 SQLite 用实际 `build_source_rank_fact` / `apply_rank_fact` / `lookup_library_rank_facts` 复现。第二种顺序中，旧 8p 揭示相同的职业降段矛盾，却因 `active=False` 被保存为非 current qualified 行后忽略，之后仍给空 rank 的新谱补 7p。现有“较新 8p 后上传旧 7p 不回退”测试不能覆盖反向等级矛盾。

最小修正：将“是否推进依据日/选择 current 事实”和“新证据是否使投影冲突”分开。迟到旧资料保持较新 current 的依据日和等级，不回退；但若与较新职业事实构成降段（或跨系统冲突），同样使唯一 current 进入 conflict，保留不可变事实内容和 SHA。为两种到达顺序增加同结果的聚焦回归，并保留正常旧低段不回退测试。

### 3. P2 — 单个损坏的候选 SGF 会中断整个有界查询批次

位置：`katrain/web/kifu/player_ranks.py:825-847`；实际异常从 `:150` 的 `SGF.parse_sgf()` 抛出。

候选解析只捕获 `ValueError` / `TypeError`，而仓库解析器的 `katrain.core.sgf_parser.ParseError` 直接继承 `Exception`。临时库中给人物甲放一份有非空 raw rank 的损坏 SGF、给人物乙放一份正常 8p SGF，一次查询两个已绑定 ID 时，函数直接抛出 `ParseError: Expected '(' at start`，乙也没有结果。已有库的单份不可验证源不应中断其他人物及合法新谱的处理。

最小修正：在逐候选容错边界明确捕获解析器的 `ParseError`，跳过该候选；仍允许后续有效候选/其他人物继续。不要扩大成吞掉数据库或程序错误的广泛 `Exception`。增加一个损坏候选与另一个有效人物同批时分别 unknown/qualified 的回归。

### 4. P2 — 尚未确定的职业/业余系统会永久污染后来明确的段位

位置：`katrain/web/kifu/player_ranks.py:655-658`，`rank_system !=` 一律进入 sticky conflict，未区分 `dan_unspecified` 与明确系统之间的信息补全。

按父任务补充的同一边界独立确认：先记录 `七段 / 2026-10-01`（无职业 proof，系统 `dan_unspecified`），再记录明确 `8p / 2026-10-03`，current 实际为 `(8, professional_dan, conflict)`。反向先明确 `8p / 2026-10-01`，再记录 `七段 / 2026-10-03`，current 被换成 `(7, dan_unspecified, conflict)`。这些均由临时 SQLite 中的真实 builder/apply 调用复现。尚未确定职业/业余的“段”不能本身成为职业与业余相矛盾的证据；当前 sticky 策略使后来的明确资料仍不可用于 fallback。

最小修正：区分信息未全与确实冲突。允许较新明确的职业/业余段位取代 `dan_unspecified`；未知系统观察不得反盖已有明确段位，亦不得仅因系统未知把明确 current 变成 conflict。保留未知观察的不可变历史、已明确职业/业余/级之间的真实矛盾和明确职业降段门禁。`dan_unspecified` 仍明确是“段”，不必把它当成可无条件兼容“级”的完全未知类型。增加 unknown→明确及明确→unknown 的两个聚焦回归。

## 已核对的质量边界

- grade 与职业身份分别可核算，固定 fact 不含当地 ID，内容哈希不随 retry/current 变化；原 capture 与当地 approved owner 会再核对。官方字段解析限当前有限对象，不发 HTTP/LLM。
- discovery 使用既有 player FK 的 UNION，有最高日冲突聚合、每人三候选、单份/总 SGF 字节预算；没有逐人查询循环。snapshot helper 为单次有界查询。
- apply 锁既有 player 行覆盖首次 current，事务由 caller 拥有；部分唯一索引覆盖 conflict，snapshot 对 fact 为 RESTRICT。首 observed_at 和明确源等级不被静默改写。
- 004 与 ORM 的当前字段、约束和索引对应；本次不改变旧 player/album 列形状。

## 实际验证及限度

本轮独立运行 8 项现有聚焦测试（dedup/首观察时间、正常旧资料不回退、三种冲突、已有/空库 startup 不建 rank 表、批量固定查询数），全部通过；另外执行上述四类最小反例，均重现当前缺陷。第四项由父任务提出，本审独立验证两个方向后纳入判断。未重复规范审的 94 项测试，也未重新抓取六人来源。

本轮没有运行 PostgreSQL DDL 或双连接 current 并发实验；沿用已说明的环境限制，不以 SQLite 验证替代 PG 迁移/锁证据。后续完整 publisher/API/undo、临时 PG 演练和真实 TEST→PROD 验收仍按计划执行。本报告仅评当前 foundation 代码质量，修复四项后可做定向复审。

## 定向复审：7192e813efe19a74c4dcdcc28e3f6d10d32c1135

**Verdict: Needs fixes — 原第 4 项尚有一个对称的到达顺序缺口。**

只检查 `946c67a89..7192e813e` 的 5 个文件及原四项边界，未扩展全库/发布器范围。独立执行新增回归和原有正常旧资料/三种冲突回归，共 **19 passed**。

- 第 1 项关闭：`KIFU_RANK_TABLES` 集中用于 auth 排除、通用补列/索引排除和 `PROTECTED_TABLES`；两张已有不完整表的测试证明字段、索引和行均保留原状。
- 第 2 项关闭：迟到旧高职业段/跨明确系统事实使较新 current 标记 conflict，未回退其等级、依据日或不可变 fact SHA；双到达顺序均覆盖。
- 第 3 项关闭：仅在逐候选边界增加准确 `ParseError` 捕获；损坏候选不会影响同人的其他有效候选或其他人物。
- 第 4 项已修复 unknown 较旧、typed 较新的序列，以及 typed 先到后收到较新 unknown 的序列；仍遗漏较新 unknown 先到、较旧 typed 后到的对称情况。

剩余位置：`katrain/web/kifu/player_ranks.py:645-656`。日期先决定 `active`；代码仅有 typed current 不被 unknown 反盖的规则，没有 unknown current 被较旧 typed 精化的对称规则。独立临时 SQLite 运行真实 builder/apply/lookup，使用相同的 8 段数字以排除等级差异：

```text
8p / 2026-10-01 → 八段(无 proof) / 2026-10-03:
  current = 8 / professional_dan / 2026-10-01 / qualified
  lookup = qualified
八段(无 proof) / 2026-10-03 → 迟到 8p / 2026-10-01:
  current = 8 / dan_unspecified / 2026-10-03 / qualified
  lookup = unknown_system
```

这是原第 4 项的信息精化/未知不覆盖已知边界，并非新增审查范围；相同事实集合仍随到达顺序改变能否 fallback。最小补齐：当 current 仅为 `dan_unspecified`、incoming 为明确 `professional_dan`/`amateur_dan` 时优先明确事实，允许保留该明确事实自身的较旧依据日，不重写 fact 或伪造日期。保留 dan↔kyu 与已明确系统冲突规则。增加上述同值两顺序的参数回归即可，无需重复整套数据审。

## 最终定向复审：32f1273812e5f96f0704a59c987e1fde53f9c40d

**Verdict: Approved — 当前 foundation 无剩余 must-fix。**

直接核对 `7192e813e..32f1273812e`，仅涉及 `player_ranks.py` 和对应测试。新增优先规则严格限定为 current 是 `dan_unspecified`、incoming 是明确职业/业余段：允许明确事实接任，保留其真实 source_as_of、grade、证据和 SHA；未知观察仍留在 history，不会反盖已知 typed current。没有放宽已有 typed 与 typed、dan 与 kyu 的系统冲突，也没有放宽明确职业降段规则。

独立运行覆盖本四项及必要既有边界的 **27 项定向测试，27 passed / 1.01s**：新增 8 组 `8p/8d × 八段/九段 × 两到达顺序` 全通过；两种顺序均选同一明确 fact，保留明确事实 2026-10-01 的真实依据日及 unknown 观察 2026-10-03 的原内容。其余覆盖 partial rank startup 零修改、迟到高职业段/跨系统两顺序冲突、正常旧低段不回退、unknown 不反盖 typed、dan↔kyu 冲突和损坏候选隔离，全部通过。

复核确认前三项修复仍在：集中 `KIFU_RANK_TABLES` 覆盖 auth 与通用迁移/保护集合；迟到矛盾仅更新当前投影 status，不改较新事实内容；`ParseError` 仅在逐候选容错边界捕获。本轮只写本报告，未改业务代码、访问生产或增加全库/外部来源审查。

批准仅覆盖当前 foundation。PostgreSQL 迁移/并发实测、后续 native publisher 的完整前后像 journal/undo、API 与真实 TEST→PROD 验收仍按已审计划执行，不将尚未接入的后续单元当成本 foundation 缺项。
