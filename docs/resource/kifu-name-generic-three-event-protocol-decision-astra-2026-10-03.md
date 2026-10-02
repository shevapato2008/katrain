# 三个原始赛事标签：最小协议决策（2026-10-03）

决策任务：`/root/generic_event_protocol_decision_astra`。运行时标识为 GPT-6，任务名中的 astra 不作为具体模型子型号认证。本次只阅读资料与代码、编写此决策；未改应用代码、连接数据库、批准候选包或提交。

**采用两阶段实现：先增加冻结的 `classification-v2`，交付个人赛与段位赛的 22 格；再增加独立的 `archive-description-v1`，交付 Hoensha 的 11 格。** 两阶段均须完整保存十一语，经实际前像绑定和独立签署后进入既有导入器。阶段一完成只可报告两组进展；用户的三组 33 格目标须到阶段二完成才算完成。阶段二不应因六次语种不存在官方赛事名称而再开名称检索闭环。

## 决策依据与当前状态

依据 [33 格独立语言审核](kifu-name-generic-three-event-11lang-independent-review-sol-2026-10-03.md)、[v2 草案阻塞记录](kifu-name-generic-three-event-v2-bundle-producer-2026-10-03.md)、[冻结标签分流](kifu-name-high-volume-event-triage-2026-10-02.md) 及以下实现：

- `name_candidates.py`：分类模板固定为 `classification-v1`；校验精确文本、语言模板 hash 和独立签署；新 raw owner 必须与当前 parser 分类一致。
- `name_evidence.py`：现有研究记录服务于找到惯用名、负面检索和读音等主张；无法把档案说明翻译诚实包装为其中一种名称研究。
- `name_batch.py`：既有 raw owner/name、JSON 证据、前像绑定、事务和 undo 已能承载说明文字；无需新表或新 owner 类型。
- `identity.py`：通用 raw 名默认按精确原文全局显示；仅 composed 等已有专用范围路径。新的档案说明需要在相同显示、搜索、覆盖率入口遵守自己的有限范围。
- `name_coverage.py`：以实际严格显示审批为准，并按 `decision_kind` 计数。待核实 fallback 不算已覆盖。

原稿结论仍是 **30 PASS / 3 HOLD**。采用审核给出的三条替代可生产修订候选，不能倒改原稿结果，也不能把语言审核当作原文范围、实际包或数据库审批。901 + 638 + 595 = 2,134 是旧冻结盘数；其十一语事件槽理论上限为 23,474，不是当前新增覆盖或全库完成率。

## 阶段一：冻结旧版本，新增通用说明模板

`段位赛`、`个人赛` 继续使用 `owner.kind=raw_event`、`category=generic_event_description`、`decision_kind=generic`。不补全国、年份、届次、升段制度或唯一赛事身份。`album_links=[]`，不写 event owner、赛事 alias 或任何棋局 `event_id`。

保留旧 `classification-v1` 的全部模板内容、hash 算法和验证含义。新增独立、不可原地改写的 `classification-v2` 表；其内容等于旧表加下列精确替换，其余 placeholder/error/generic 文本不变：

| 原文 | 语言 | v2 精确文本 |
|---|---|---|
| 个人赛 | en | Individual tournament |
| 个人赛 | ru | Индивидуальный турнир |
| 个人赛 | ua | Індивідуальний турнір |
| 段位赛 | ko | 단위(段位) 관련 대회 |
| 段位赛 | en | Dan-rank tournament |
| 段位赛 | de | Dan-Grad-Turnier |
| 段位赛 | es | Torneo de grados dan |
| 段位赛 | fr | Tournoi de grades dan |
| 段位赛 | ru | Турнир по данам |
| 段位赛 | tr | Dan derecesi turnuvası |
| 段位赛 | ua | Турнір за данами |

实现边界如下：

1. 校验按候选的 `generation_rule_version` 选择模板，再核对 `template_review.version/lang/sha256`；未知版本拒绝。不能简单把全局常量改成 v2，也不能把 v1 的旧字符串覆盖为新字符串。
2. `classification_template_sha256(lang, version=...)` 可增加显式版本参数；为现有调用保留默认 v1。原 `_CLASSIFICATION_TEMPLATES` 若继续被 `strict_fallback` 导入，应保持其旧含义，或明确迁移该调用；fallback 本轮无需改变。
3. v1 hash 继续使用原 `{version, lang, templates}` 内容。v2 即便某语言文本与 v1 相同，因版本不同也需要新模板签署。不得复制旧 `template_review` 后改版本或 hash。
4. 本轮按两个原文各 11 格重制和签署完整候选，不只交付发生变化的 3/8 格。五主语 cn/tw/jp/ko/en 按独立审核的语义与术语尺度核对；次六语 de/es/fr/ru/tr/ua 按可靠含义与组合规则审核。它们均明确为通用说明；编辑翻译不需要伪装为当地官方赛事名。
5. 对采用本次新通用规则的 raw owner，在包校验中要求精确十一语 member/candidate 集合且全部 approved。现有代码只对新身份 owner 强制十一语；不能假定 raw owner 已有同样门槛。此要求限定于新规则，不追溯改变旧 v1 包的合法性。
6. 复用 `bundle_format=2 / inventory_format=4`。两个原文可同包，也可分别导入；每个原文的十一语必须一起通过。阶段一冻结规模为 1,539 盘、22 个候选、16,929 个事件语言槽上限。

v1 与 v2 的模板选择只是离线候选协议。数据库保存批准的字面值和规则版本，运行时不按最新模板重译旧行；旧包、旧 evidence 和旧名字 revision 均不被后台升级。

## 阶段二：明确的 Hoensha 档案说明

采用以下有限协议，不扩展为任意描述生成框架：

| 字段 | 决策 |
|---|---|
| owner | `raw_event`，精确原文 `Hoensha game` |
| 新 category | `archive_source_description` |
| 新 decision_kind | `archive_description` |
| 规则版本 | `archive-description-v1` |
| 文本规则 | 以下十一语固定完整字符串，按版本和语言绑定 hash |
| 身份关联 | 零 event owner、零 event alias、`album_links=[]`，目标 `event_id` 保持 NULL |
| 范围 | 本轮实际库存中经核对的 Hoensha 来源行；旧冻结 595 盘仅作比较基准 |

| 语言 | 精确文本 |
|---|---|
| cn | 方圆社史料棋局 |
| tw | 方圓社史料棋局 |
| jp | 方円社の棋譜（史料） |
| ko | 호엔샤(方円社) 관련 옛 기보 |
| en | Hoensha archive game |
| de | Historische Partie aus dem Hoensha-Archiv |
| es | Partida histórica del archivo de Hoensha |
| fr | Partie historique des archives de la Hoensha |
| ru | Историческая партия из архива Хоэнся |
| tr | Hoensha arşivinden tarihî go partisi |
| ua | Історична партія з архіву Хоенся |

这里的 archive 指已核对的 CWI 历史棋谱来源语境；不声称存在一个经认证、由方円社现今管理的档案机构。不得据组织月会历史推导每盘的具体月会、届次或赛事 ID。英语是编辑扩写，其他翻译及俄乌转写不作为官方当地名称证明。

### 分类版本与证据

保留 `parse_event` 的默认保守结果，避免一次全局分类改变使旧包的 `unclassified_pending` 前提失效。在候选协议增加一个**仅在 `archive-description-v1` 下生效的精确规则**：原文必须严格等于 `Hoensha game`，owner 必须是 raw_event，声明类别必须为 archive_source_description，所有该 owner 的候选只能使用 archive_description。新 owner 的既有 `parser_version` 字段可记录该规则版本；候选与 owner 声明必须一致。此规则是受版本限制的分类，不是让任意 `category_review` 文本覆盖 parser 的通用出口。

旧类别/版本继续走原校验分支。`Hoensha Game`、带额外空格的变体、别的组织或其他 `unclassified_pending` 不能靠同一规则通过。若真实库已存在该原文的旧 raw owner，先核对其前像与类别；不得借本次新增模板悄悄改类或新建重复 raw owner。现有 importer 没有一般 raw owner 重分类流程，遇到这种实际状态应单独做最小迁移决定。

档案说明仍令 `research_sha256` 为空，不提交假的 `scope_status=found` 或十一份“未找到名称”记录。利用既有 `category_review`/JSON evidence 增加一个有限档案依据对象即可；不增加通用 research 类型、不修改惯用名/负面检索门槛。该对象必须绑定：精确 raw、类别与规则版本、inventory hash、完整出现行及其 hash、已核对的来源上下文、来源 URL/抓取时间/正文 SHA-256、独立分类审核者和时间。候选绑定其 hash，模板审核另外绑定该语言的精确文字与版本。

可直接使用已经保留并复算通过的 CWI Hoensha 与日本棋院历史正文作为主要分类依据，并准确注明旧抓取时间。它们已有 registry `.7` 记录；NDL、Kotobank 可保留为附加材料，本次不必为四份正文全部登记而扩张 registry 工作。若纳入机器校验的正式 source ID，必须实际存在于所固定的 registry。来源页证明历史组织/史料语境，不证明十一种翻译是来源页中的惯用名称。

### 持久化和实际显示

既有 raw 表、name 表和 evidence JSON 足够；不需数据库 schema migration。`name_batch.py` 只需把已经验证、由候选 hash 绑定的档案依据/范围存入现有 evidence payload，保留完整批准字面值、规则版本与 reviewer。继续复用前像检查、锁、事务、变化记录和 undo。

**档案说明不得无条件复用当前 `result[raw]` 的全局映射。** 本次 archive 用语依据的是有限 CWI 史料范围，批准不能顺带扩张到尚未核对的同文新行。最低充分处理是复用现有 `(album_id, raw, event_id)` 映射方式：只有签署范围内、当前仍为精确原文、无 event_id、未改用另一个 selected event 的行可显示/计数；其他行保持待核实。无需新建一般原文范围框架。

现有 owner 的 `occurrence_album_ids` 已提供有限成员，不要再造第二套不同成员清单。将其连同来源依据作为同一签署范围保存；运行时只做已有资料的资格检查，不发网络请求、不再翻译。来源上下文在实际库存/导入核对中确认；库存漂移由现有 audit 门槛拒绝。此最小实现不宣称实时重新认证远端网页。

`_approved_raw_event_names`、`_raw_event_map`、`strict_raw_event_search_clause` 必须遵守同一档案范围；`strict_slot_approvals` 的无 event_id 分支目前直接 `raw_events.get(raw)`，需改用现有支持复合 key 的读取函数，才能与 `resolve_strict_display` 一致。新 decision 只能加入 raw_event 的允许集合，不能放进对 player/event 全局有效的 `_DECISIONS`。撤销或损坏的档案依据不能继续计为批准。

覆盖率仍走 `name_coverage.py` 的真实解析结果，`by_decision` 单列 `archive_description`；已审档案说明可以满足事件展示槽的覆盖要求，但不得计作已确认的赛事身份。`generic` 同理。完整十一语入库和十一语严格显示覆盖需分别核对；不得以一格模板存在乘以 595 冒充实际结果。

## 代码与测试边界

| 阶段 | 允许的最小代码范围 | 最低充分验证 |
|---|---|---|
| 一 | `name_candidates.py` 的双版本模板、显式 hash 选择、仅新规则的十一语完整门槛；调用方显式选择 v2。`identity.py` 仅在必要时保持旧 fallback 引用语义。 | 固定旧十一语 v1 hash/文本；旧已审样本仍过；新 22 格精确通过；新文本配旧版本/旧 hash、未知版本、缺语或 pending 均拒绝；一次代表性 raw 包导入及 undo，确认无 event/alias/album link 变化。 |
| 二 | 同文件内有限 archive 分类/模板/依据校验；`name_batch.py` 持久化依据；`identity.py` 的 raw_event 资格、范围显示与搜索；需要时只加直接辅助函数。`name_evidence.py` 的一般研究规则保持原义。 | 11 格通过；错误 owner/raw/version/category、无来源依据、改正文hash、非独立审批、缺语/pending 拒绝；导入/undo证据保留；一组内外范围行验证显示、搜索、coverage一致；无 event_id/alias 生成。 |

扩展已有 `test_kifu_name_candidates.py`、`test_kifu_name_batch.py`、`test_kifu_identity.py`、`test_kifu_name_coverage.py` 的聚焦用例即可。正文 hash 被篡改的校验要比对签署内容与保留文件，不要求运行时联网抓网页。旧 v1 兼容性测试是本次必要回归点；不建立全新审核基础设施、不跑无关棋力/GPU/前端全状态测试。

两个阶段的实际候选包都须重新取得目标库 inventory/catalog 与 raw owner/name 前像、由真实 binder 绑定、由独立 reviewer 签最终内容，再通过已有 dry-run/apply 门槛。丁波的 raw_player 前像与旧 Honinbo receipt 均不能用作本批 raw_event 的当前前像。无需因本决定重复征求已经存在的执行授权；本文件本身不冒充数据库写入授权。

## 批准与禁止

批准作为实现方向：上述两套相互独立的冻结规则、三组完整十一语、现有 raw 数据模型与批次机制、对说明性质诚实的覆盖计数。阶段一先完成，不等待 Hoensha 协议；随后继续阶段二，不能以阶段一代替三组完成。

禁止：覆盖 v1 表或旧 hash；把新签署回填成原稿旧审批；把说明译文标为 conventional/generated/composed/transliterated 来绕闸；把 Hoensha 设为杯赛或正式赛事实体；为段位赛/个人赛推定全国身份；放开任意 unclassified 原文的自由译文入口；只存五主语或只存发生变化的格；把未审范围、fallback、旧冻结盘数或候选格数报告成实际数据库全量覆盖。

此决策的交付状态：协议方向已明确；代码、候选包最终签署、实际导入与最终十一语全量覆盖均仍由后续执行与证据确认。
