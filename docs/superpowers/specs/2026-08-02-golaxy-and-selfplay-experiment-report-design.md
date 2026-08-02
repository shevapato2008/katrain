# 修复后星阵与内部对局实验报告设计

## 目标

在 `superpowers/tracks/golaxy-ai-ladder-parity/` 下生成一份可离线打开、便于审计和比较的单文件 HTML，系统整理修复 HumanSL 搜索与模型路由 bug 之后完成的全部星阵对局和内部自对弈。正文以去重后的有效实验为主，附录保留排除项、停机和续跑链的审计信息。

报告面向产品与研发决策：读者应能快速回答每个星阵等级测试过哪些模型、比分如何、哪些模型可作为候选对标；也能理解 HumanSL 原生采样、argmax、PIKL 搜索及 b18/b28 搜索深度之间的内部强度关系。

## 输出

- HTML：`superpowers/tracks/golaxy-ai-ladder-parity/reports/post-fix-experiment-report.html`
- 单文件、自包含 UTF-8 文档；CSS、结构化报告数据和少量原生 JavaScript 全部内嵌。
- 不依赖网络字体、CDN、构建工具或后端服务。
- 本次不修改应用运行时，也不把报告接入 Galaxy 或 kiosk 页面。

## 已确认决策

采用用户确认的**方案 A**：一份表格优先、可搜索筛选、可离线审计的自包含 HTML。正文只展示修复后、去重且身份可证明的有效证据；旧数据、重复表示、superseded、停机/续跑和语义探针统一进入审计附录。此次不采用多页面站点、只输出静态 Markdown，也不重新运行或补齐实验。

## 修复后证据边界

只有能证明包含以下修复基线的真实对局才进入正文统计：

- KaTrain：`e45531b3`，2026-07-22 13:45 +0800，合并 HumanSL 搜索路由修复。
- KataGo 实时服务：`e1b68dd0` 与 `d11d80ea`，分别加入模型路由身份认证和严格身份检查。
- 模型身份固定为：
  - b28：`798da8fe3e9819f09535240b1bc29cb3047a4fa981433c56c491e57007a3d3f0`
  - b18：`9d7a6afed8ff5b74894727e156f04f0cd36060a24824892008fbb6e0cba51f1d`
  - humanv0：`637746e44f0efe00ad1245a50aa9bbf0716efe364c43965ead97bd6835d84ab5`

生成器使用一份纳入版本控制的权威 source inventory，而不是按文件名或日期猜测。inventory 每项包含仓库相对路径、文件 SHA-256、schema、实验族、`included/excluded/superseded` disposition、理由、父源（若有）和预期身份。数据截止点固定为 inventory 中最后一个获准结果的时间。每个扫描到的候选证据必须恰好进入一个 disposition；未知文件不能被静默忽略。

正文源必须同时满足：inventory 标为 `included`；文件 SHA 匹配；账本 header/manifest 记录的 KaTrain 运行代码版本包含 `e45531b3` 或来自明确列入 inventory 的修复后 runner；所有实际参与落子/裁判的模型 SHA 与上述冻结值相符；使用显式 b18 搜索时，每次响应身份认证和 capability snapshot 证明服务具备 `e1b68dd0`、`d11d80ea` 引入的严格路由语义。缺失任一证明即标为 `excluded`，理由为 `unproven_post_fix_identity`。显式列入 inventory 的旧文件只校验存在性与 SHA，不按当前 schema 强制解析。

证据时间早于 KaTrain 基线、执行身份无法证明、仅为语义探针而非真实对局，或已被后续账本明确 supersede 的数据不进入正文比分。

修复后的停机或部分完成账本中，已经落盘的结果按所属 protocol 的 eligibility 规则统计，同时将实验标记为“未完整闭环”：Golaxy 的明确单盘结论计入；selfplay 只有完整颜色对中的明确结果计入。inconclusive 和因半对/未定对而被配对规则剔除的结果不计入胜负比分，但分别显示数量与原因。星阵 rank_1d..rank_6d `@1` 扩充目前为 59/60，必须显示最后一盘缺失状态。

## 数据单元与边界

实现分为三个逻辑单元，不要求拆成三个独立程序：

1. **数据提取器**：只读取 `calibration/results` 下获准的 JSONL、JSON、manifest 和 gzip 证据，验证格式与身份后输出规范化记录。它不负责视觉或结论措辞。
2. **证据归并器**：按原始账本 SHA、origin/result id、manifest raw SHA 和续跑父子关系去重，计算比分、有效盘、inconclusive、颜色配平、完成状态和证据等级。它输出一份确定性的报告数据对象。
3. **HTML 渲染器**：只消费规范化报告对象，生成最终单文件 HTML；不重新解释原始账本。

规范化报告对象包含 `experiments`、`audit_items`、`continuation_edges`、`source_inventory`、`known_empty_families`、`validation_summary` 和 `data_as_of`。渲染器据此同时生成正文与附录。

实现脚本放在 `superpowers/tracks/golaxy-ai-ladder-parity/calibration/`，便于以后重新生成报告，但脚本不是产品运行时依赖。

## 规范化实验记录

每条去重实验至少包含：

- `category`：Golaxy 或 selfplay。
- `experiment_family`：例如 HumanSL native sampling、argmax、PIKL boundary、b18 star calibration。
- `player_a`、`player_b`：完整模型/等级/访问数/选择语义。
- Golaxy 记录额外包含 `golaxy_level`、wire level 和产品等级别名（若适用）。
- `planned_games`、`raw_observed_games`、`eligible_games`、`missing_games`、`wins`、`losses`、`decision_games`、`inconclusive_games`、`pair_invalidated_games`。
- `player_a_black_games`、`player_a_white_games`、`complete_pairs`、`incomplete_pairs` 和按原因分组的未定盘。
- `inclusion_status`：included 或 excluded。
- `completion_status`：completed、partial 或 stopped。
- `evidence_class`：formal、descriptive 或 exploratory。
- `source_paths`、父子 SHA/原始 SHA、执行日期和身份摘要。
- `notes`：停止原因、协议限制、是否仅能支持描述性结论。

比分始终以前列玩家为视角。表头和方法说明必须明确这一规则。

### 统计层级与守恒

- **game/result** 是原始观测原子：一次已落盘 result 对应一盘，结论为 win、loss 或 inconclusive；reservation 不是 result。
- **pair** 是同 opening/slot、双方互换黑白的两盘。两盘都产生合格结论才是 `complete_pair`；缺盘或任一盘 inconclusive 时是 `incomplete/inconclusive_pair`。
- **segment/campaign** 是一段原始账本或续跑贡献；**experiment** 是同一汇总匹配键下所有 included segment 的累计。主表显示 experiment 累计，去重明细显示各 segment 的计划、观测、比分、缺失和停止点。
- Golaxy 协议按单盘计分：每个 conclusive result 都是 eligible，颜色配对完整性只作为质量提示。内部自对弈协议按完整颜色对计分：只要 pair 缺失一盘或任一盘 inconclusive，该 pair 中所有已落盘的 conclusive result 都不进入 eligible/胜负分母，并计入 `pair_invalidated_games`；runner 的 replacement pair 作为新 pair 参与目标数。
- 每层必须满足 `raw_observed_games = eligible_games + inconclusive_games + pair_invalidated_games`、`decision_games = wins + losses = eligible_games`。对按单盘计分的 Golaxy，`pair_invalidated_games=0`；对按 pair 计分的 selfplay，inconclusive pair 中原本 conclusive 的另一盘计入 `pair_invalidated_games`，真正 inconclusive 的盘计入 `inconclusive_games`。
- `planned_games` 描述目标合格样本，不包含 replacement 尝试；因此完成进度满足 `planned_games = eligible_games + missing_games`，而 raw observed 可因 inconclusive/replacement 超过 planned。这里的 `missing_games` 是距离目标 eligible 样本的缺口，不等同于物理上未产生 result 的盘数；物理缺失和未闭合 reservation 另在 segment 审计字段记录，均不计 raw observed。
- 黑白统计永远以 `player_a` 视角计算；inconclusive 仍计入 observed 和黑白盘数，但不计入胜负分母。
- `completion_status=completed` 要求 missing 为 0 且不存在未闭合 reservation；`partial` 表示仍可续跑或计划盘缺失；`stopped` 表示 runner 已明确停止但已有结果可计。是否进入正文只由 `inclusion_status=included` 决定，exploratory 仅限制结论强度。
- rank_1d..rank_6d 的扩充 segment 以 `planned_games=60, eligible_games=59, missing_games=1` 表达；与父 campaign 合并后的 experiment 累计以 `planned_games=100, eligible_games=99, missing_games=1` 表达。两层都保留，主表默认显示 99/100，segment 明细明确显示 59/60 和最后一个未闭合 reservation/停止原因。

## 去重与续跑规则

- canonical game id 使用统一 namespace，先解析引用、再选择身份，不能简单给原字段加不同前缀：
  1. 父账本行身份统一为 `source:<raw_sha256>:<result_line_number>`。父原件、`parent_raw_sha256 + parent_result_line` carry，以及值形如 `legacy:<sha>:<line>` 或 `source:<sha>:<line>` 的 `origin_id`/`origin_result_id` 全部规范为同一个 `source:<sha>:<line>`。
  2. 其他不可变 `origin_result_id` 与旧 schema `origin_id` 统一规范为 `origin:<value>`；两字段同时存在时必须解析到同一 canonical id。
  3. 没有 origin/父引用的原生 campaign result 使用 `campaign:<campaign_id>:<stage>:<slot/opening>:<attempt>:<player_a_color>`。
  4. 没有上述字段的受支持旧父原件使用自身 `source:<source_raw_sha256>:<result_line_number>`，因此未来 carry 可稳定引用它。
  键的作用域是整个报告，不是单个文件；未知引用格式、引用不存在的父行或同一 canonical id 内容不一致都必须失败。
- raw JSONL、gzip 归档、manifest 和 summary 指向相同 raw SHA 时，只计一份对局；manifest/summary 作为验证与元数据来源。相同 canonical id 的规范化内容必须完全一致，否则生成失败，不能择优覆盖。
- 星阵追加式 campaign 的 reservation/result 不跨账本复制；续跑链按父 SHA 排序后汇总已完成 result。
- carry evidence 若来自已冻结父账本，按 origin id 或父账本行号计一次。
- 同一 matchup 在不同协议、访问数、选择方式或执行阶段下保持为不同实验，不因双方名称相似而合并。
- 汇总匹配键固定包含 category、双方规范化模型身份、双方 rank/profile、访问数、选择语义、PIKL 配方指纹、棋盘/规则/贴目、开局集、裁判算法、Golaxy wire level 和协议版本。键完全相同的扩充实验可以在“汇总比分”中合并，同时在明细中保留各段账本贡献与停止点。
- selfplay 的不完整颜色对、inconclusive pair 和所有协议中未产生 result 的 reservation 不进入胜负分母；Golaxy 已产生的 conclusive 单盘不因另一颜色缺失而失效。
- continuation 必须形成无环 DAG；每个 child 的 parent path/SHA 必须匹配 inventory，孤儿、循环或多父冲突均失败。输出按汇总键、父子拓扑、canonical game id 确定性排序。

## 报告结构

### 1. 执行摘要

用表格列出纳入实验族、去重实验数、有效盘数、inconclusive 数和未闭环事项。提供不超过六条、且能由表格直接支持的关键观察，不给出超出样本量的统计断言。

### 2. 星阵对局总表

按星阵等级从低到高排列。每个等级一行或一组行，展示修复后测试过的全部 KataGo/HumanSL 配置、有效比分、完成状态、证据等级和候选对标备注。星阵原始等级名称保留；最高三级同时显示产品名称：

- 星阵1星（职业水平）
- 星阵2星（职业顶尖）
- 星阵3星（超越人类）

不得把产品名称替换回仅有“1星、2星、3星”的产品展示，但审计字段保留原始星阵名称。

### 3. 内部对局总表

按实验目的分成四张主表：

- 同等级 `@1` 加权采样 vs `@1s` argmax。
- 相邻等级 `rank_{n-1}d@1s` vs `rank_nd@1s`。
- 相邻等级 argmax vs 下一等级加权采样。
- PIKL/搜索访问数与 b18/b28 边界实验。

每表包含双方、有效比分、完整颜色对、inconclusive pair、证据等级和解释边界。

### 4. 关键关系表

以表格而非图表为主，整理：

- 同 rank 下 sampling 与 argmax 的强度差。
- 相邻 HumanSL rank 是否表现出单调方向。
- 搜索访问数从 1/2/5/10/20/40/80/160/320 变化时的观察。
- 星阵等级与当前候选模型之间已验证、过强、过弱和证据不足状态。

### 5. 去重实验明细

每条规范化记录一行，支持文本搜索和筛选。宽表列包括来源、模型身份、协议、有效盘、未定盘、颜色、日期、状态和备注。

### 6. 审计附录

分别列出：修复前排除、superseded、重复表示、停机/续跑链、身份无法证明和非对局语义探针。每项来自 `audit_items` 或 `continuation_edges`，给出路径、SHA 与排除理由，但不把原始大体积 JSON 嵌入 HTML。

### 7. 方法与术语

准确解释：

- `@1`：按 HumanSL policy 正权重进行抽样。
- `@1s`：HumanSL policy argmax。
- `@N`（N > 1）：b18 + humanv0 PIKL 引导搜索，选择搜索首选结果；不是 policy top-N。
- `b18@N` / `b28@N`：对应主模型的纯搜索访问数。
- PIKL 的效用调整语义和有效盘、完整颜色对、inconclusive 的计算规则。

## 交互与视觉

- 研究档案风格：暖白纸张背景、深墨文字、低饱和蓝绿主色、橙色警示。
- 基础字号不小于 16px，正文行高至少 1.5；状态不只依赖颜色，必须同时显示文字。
- 顶部提供目录、全局搜索、类别、证据等级和完成状态筛选；不实现复杂图表或动画。
- 表头粘滞；桌面宽表清晰，窄屏允许容器内横向滚动，不造成整页横向溢出。
- 打印样式隐藏筛选控件、展开全部内容、避免行被分页截断。
- 所有来源路径使用仓库相对路径文本；本地打开时不依赖不稳定的绝对链接协议。

## 异常与诚实状态

- 先用 inventory 分类来源；纳入源遇到未知 schema、重复 result id、父 SHA 不匹配或非法数值时必须失败，不生成“部分看似成功”的报告。
- 显式列为 excluded/superseded 的损坏或旧文件只验证存在性与 SHA，并记录排除原因，不进入严格业务 schema 解析。
- 报告顶部显示确定性的数据截止时间 `data_as_of`、修复基线和校验摘要。真实运行时钟不嵌入产物；若命令行需要显示本次生成时间，只输出到终端日志。
- 如果某个已知实验族没有任何合格记录，显示“无修复后有效证据”，而不是省略该实验族。
- 不推断未实测模型的星阵对标等级；候选对标备注必须能回指直接比分。

## 验证与验收

1. 单元测试覆盖修复边界、JSONL 解析、gzip/manifest 去重、续跑链合并、颜色配平、inconclusive 分母和比分视角。
2. 黄金数据测试固定下列关键结果和状态：
   - rank_1d@1 对星阵准1段、1段均 10–0；rank_2d@1 对准2段 9–1、对2段 10–0；rank_3d@1 对准3段、3段均 9–1；rank_4d@1 对准4段 9–1、对4段 8–2；rank_5d@1 对5段 8–2；rank_6d@1 对6段 6–3。扩充 segment 为 59/60、missing 1；与父 campaign 合并后的累计 experiment 为 99/100、partial、missing 1。
   - b18 对星阵3星的 @32 累计 7–7、eligible 14/20、missing 6、stopped；@64 累计 7–3、eligible 10/20、missing 10、stopped。来源是 `calibration/results/golaxy_b18_three_star_20game_20260801/` 的 parent/extension 链；`extension_v6` 新增 @32 的 6–4，`extension_v7` 因 Golaxy `7002 illegal query` 未新增有效盘。黄金测试必须断言这些人工冻结值，而非只用同一解析器重算。
   - 相邻 `@1s` 八组：1d–2d 7–13、2d–3d 7–13、3d–4d 4–16、4d–5d 9–11、5d–6d 6–14、6d–7d 9–11、7d–8d 6–14、8d–9d 7–13；每组 20 个 decision game 与 10 个完整颜色对。
3. source inventory 测试证明扫描到的每个候选源恰好属于 included、excluded 或 superseded；included 的每个 canonical game 只计一次，所有统计守恒，附录保留续跑边和停止原因。另用最小 fixture 证明父原件、`origin_id` carry、`origin_result_id` carry 和 `parent SHA + line` carry 归并为同一 canonical id；内容冲突时失败。
4. 生成器连续运行两次得到字节一致 HTML；产物只含固定 `data_as_of`，不含当前时钟。
5. HTML 结构校验：无外部资源、无缺失章节、所有主表行数与规范化数据一致；59/60 缺盘与 partial 状态可见。
6. 浏览器在桌面与移动 viewport 检查搜索、筛选、筛选后计数、表头、横向表格和打印样式；无控制台错误。
7. 最终报告展示修复后证据总数与独立重算一致，排除项不会进入正文有效盘总数，每个 source inventory 项都能在正文来源或附录中回查。

## 非目标

- 不自动重新运行实验或补齐当前缺失的星阵最后一盘。
- 不修改已有原始账本、manifest、summary 或模型配置。
- 不把探索性小样本包装成正式统计结论。
- 不建设通用 BI 平台、数据库或长期在线服务。
