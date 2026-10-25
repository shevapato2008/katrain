# 棋手等级历史与小时回退：Astra 计划评审 Round 1

**Verdict: Needs fixes**

评审基线：`2e7640d892e311f3fc8ed70d4dc5a32e470d2ddf`。完整阅读目标计划、`AGENTS.md`、库内调查报告；抽核六人摘要、六个准确 SGF 头记录及本轮补充的 `official-rank-capture-inventory.json`，并只读检查 prepare/stage、catalog、原生 journal/undo、receive/verification、API 和现有表结构。未访问业务写接口、外部人物网站，未修改业务代码、运行采集或发布。以下是实施前需要补齐的三个接点，不要求增加表、爬虫、队列或全库审核。

1. **R1 — 明确源 rank 的观察必须进入同包发布，不能只处理缺 rank 的席位。**

   计划 Task 2 第 59/63–64 行承诺 current 缓存与后续明确新谱更新；Task 3 第 81/103 行却只描述缺 rank 席位的冻结及“source rank 真的缺”的写入校验。照后者实现，人物已有 current 后不会再查最近原始等级，显式 8p 新谱也没有固定观察的传递路径，后来的缺 rank 谱可能一直使用旧 7p。等级更新、同等级更新日期及冲突后的可用性需要成为一个明确的原生事务契约。

   最小调整：v2 为所有可靠已绑定人物的明确原始 rank 携带固定 `rank_observations`（或等价的 source 类型事实），另保存每盘 `source / library_current / unknown` 决策；“原 rank 必须缺失”只约束 fallback 不得覆盖原值。prepare 只固定文件，history/current 在相应棋谱原生提交时原子写入，双库从同一观察内容处理，不在 PROD 重新找当前资料。按既有 player 行加锁，覆盖尚无 current 行的情况。同来源/内容重试去重；不同日期/不同准确原谱给出相同 7p 可以追加**观察**并推进 current 的 `source_as_of`，不称升段，也不改旧观察。较旧事实不回退 current；同日等级冲突或职业降段待复核时，后续 fallback 必须明确返回 conflict/unknown，不能只读仍带 qualified 的旧 current 后继续补值。

   聚焦验收：7p current → 明确 8p 新谱发布 → 下一盘缺 rank 得 8p；原 7p 包重放仍 7p；较新同值观察推进依据日期；同日冲突留空但合法谱继续。无需单独刷新任务。

2. **R2 — v2 的 rank-aware 完整验证必须落实到 PROD 接收门禁，不只是 checkpoint。**

   计划 Task 4 第 119–120 行要求新检查点不能借旧验证冒充通过，但当前 `sync.py:69 validate_test_verification` 只检查 manifest SHA、五语 album/lang 数量；`orchestration.py:421` 的 receive 正是调用这个函数。`verify_album_api` 最终还把详细检查压缩成 album/lang。只更换本地 checkpoint 算法或增加 GET 比较，仍可能让带正确 v2 manifest SHA、但从未检查 rank 的旧式报告通过 receiver。

   最小调整：为 v2 返回并严格校验固定 rank-aware 算法版本及有限检查摘要，绑定 manifest、准确 source key/ID、slot、SGF SHA、冻结 snapshot SHA/origin、预期 raw/display rank，以及五语详情和公开卡片检查；不能只给每条加一个恒真标志。`send_verified_manifest` 和 receive 使用同一版本分支验证，v1 保持原行为。rank fact 的规范化内容及 SHA 计算也须明确，使 receiver 可以校验包内固定事实，而不是只接受一个不可核算的 `rank_fact_sha256` 字符串。事实应保留等级来源与职业身份来源各自的准确定位/最小证据/hash，不能借当前 profile 重算。

   聚焦验收：把仅含旧 album/lang checks 的报告绑定到正确 v2 SHA，receiver 仍拒绝；删一侧、换 source/SGF/snapshot 或遗漏任一五语/公开卡片 rank 检查均拒绝；旧 v1 报告仍走原兼容路径。

3. **R3 — rank 原生撤销需要检查后来引用，完整前后像本身不够。**

   计划 Task 3 第 104 行和 Task 5 第 136 行承诺沿 native journal/undo；现有 `catalog.py:1157 _check_retained_publication_receipts` 仅保护后来 receipt 使用的 album/source link，新增 snapshot JSON 对 history fact 的引用没有 FK 或对应依赖检查。例：A 插入事实 H，B 复用 H 发布另一盘且不改 H；撤销 A 的 after-image 仍可能完全匹配，删除 H 后 B 的固定事实依赖及人物历史被破坏。不能依赖偶然更新 `last_checked_at` 来挡住它。

   最小调整：在现有 native undo 中增加有限 rank 依赖检查，或为本地 snapshot → history 加引用约束并保护仍被保留 receipt 使用的事实。发现后来引用或 current 已更新则整笔拒绝撤销，不级联删除、不自动改 B；仍只用两张表。区别 replay 与 undo：旧包在人物升段后重放应核验其不可变事实/每盘快照并返回原 receipt，不能因 `is_current` 或 `last_checked_at` 的正常变化而失败，更不能回退 current。原包已被显式 correction 修改 overlay 时可以 fail closed，但不得覆盖后来的 overlay。所有 source receipt/依赖查询同时识别 v1/v2，避免改 `FORMAT` 常量后漏掉旧依赖。

   聚焦验收：A 建 H、B 不改 H 但引用 H，撤销 A 被拒绝且零修改；人物升级后重放旧包仍保持新 current 和旧 snapshot；v1 已发布谱经 v2 correction 后，v1 receipt/SGF/album/source/prod_synced 不变。

可直接保留的设计：两张增量表、按 canonical 唯一解析当地 ID、原 metadata/SGF 不变、早于名称服务固定 unknown、三 ID 独立 correction 生命周期、批量 API 读取、receiver 先部署、现有来源/模型/3300 秒协作预算。纠正入口只操作已准确解析的既有 album，最好在共享 publisher 内使用 rank-only 分支，复用 guard/journal/receipt 而跳过全库 SGF 暖缓存及姓名续审；这比另建完整发布平台更小，也符合计划“不插新谱、不动 source link”的边界。

实施注意事项，不另加审核轮次：

- 六个准确 SGF 头支持 7/4/5/5/5/7 的原始数值。新补充的捕获 inventory 已定位王爽 `pkey=20000627` 页的 `기사정보 상세 / 王爽 / 5단`、周泓余 `pkey=20001261` 的同实体 7단，以及其他四人的官方准确字段，支持无需新外部请求即可形成六人的职业身份事实。实施仍须从这些准确绑定的已有捕获抽取、校验相应 hash，不能把 inventory 摘录或 `identity_basis` 评语当原网页。日本人物的父亲/老师文字、中国棋协邻人行、高星错人 wiki 都应由同一小组真实片段用例拒绝，不需扩为全库审核；本切片不必顺便从这些页面回填全部升段日期。
- 新表使用 DATE，而 `name_batch._image`/`_values_for_table` 当前只转换 datetime/DateTime；扩 rank journal 时补 DATE 的 ISO 往返即可，保持已有行序列化字节语义。
- 调查报告 §4 仍保留外部 profile TTL/20 HTTP 的早期建议；实施以本计划“零外部 profile 请求”为准，并删除/注明这段已被取代，避免授权范围回流。

以上三项可集中补入计划后进行唯一剩余的 Round 2。此轮不要求更换架构，也不要求对尚未实现的功能做线上试写。
