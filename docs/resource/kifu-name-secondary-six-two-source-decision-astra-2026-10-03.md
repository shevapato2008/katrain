# 六种次要语言：双来源读音锚点裁决

2026-10-03；独立决策者 `/root/secondary_six_anchor_decision`。父任务指定 `gpt-6-astra / max`；运行时仅可见 GPT-6 标识，未独立认证底层型号。本文批准方法和待审工件准备，不签署具体译名、数据库人物、棋局归属或 FK，不授权生产写入。

**决定：有条件批准显式 v2 锚点。** 中文官方原名与专业英文罗马字姓名可以来自不同出版方；必须用被独立审核、与锚点内容一起签署的来源人物对应链连接。无需继续为每人寻找同时包含汉字和罗马字的中文页面。`cn/tw/jp/ko/en` 的既有用名要求不变；该路径仅服务 `de/es/fr/ru/tr/ua` 的 `transliterated` 决策。

已阅读 `name_evidence.py`、`name_transliteration.py`、候选与持久化入口、现有音译单元/集成测试，以及[五语名称复核](kifu-name-five-primary-chinese-professional-review-2026-10-03.md)和[人物关联政策](kifu-name-bulk-player-identity-policy-decision-2026-10-02.md)。当前校验要求所有锚点来源匹配原名语言，且一个摘录同时含原名和读音；这比证明读音属于该人物所需的条件更窄。

本次只读复核了官方响应的 1,062 条记录，以及候选包的 40 条精确名册对应、80 份中英 GoRatings 原始人物页：记录唯一性、留存字节哈希、姓名/完整生日字面和人物页 ID 检查均通过。它证明现有来源链可以整理，尚未审核逐人的音节切分和六语结果。

| 已核对的受控输入 | SHA-256 |
| --- | --- |
| `five-primary-40-pending/candidates.pending.jsonl` | `60fcccf509cd961da72b6e3a30d97cf384e1b151ebdf02683044306848e29d4a` |
| `five-primary-40-review-astra/reviewed-40.jsonl` | `6763f04bb05b0293c6ce10b739689e3ba425e582aaad0c6cbb780d979f14d907` |
| 官方 `professional-list.body` | `18ba2a04efdca69d47528cbe703d9c54e1005b7f986af782434cbc3f1dd316f9` |
| `roman-reading-source-discovery/coverage-exceptions.pending.json` | `a810e395e16a86b48915f34e6a0ca22ab00e9a24f14b189703a1111d26a36bff` |

路径根为 `~/.local/share/kifu-name-audit/2026-10-03/china-professional-roster/`。严格同正文发现仅有 9/40 人，其中一人生日冲突；31 人在该有限检索中未覆盖。这不是六语惯用名不存在的证明。

## 最小 v2 契约

保留现有 `evidence_kind: transliteration_anchor`、原名/读音/owner 字段、来源捕获字段和独立签署格式。只增加锚点分支，不扩大规则或数据库模式。

| 字段 | 必须检查的内容 |
| --- | --- |
| `content.anchor_format` | 严格整数 `2`。首版仅接受 `entity_kind: player`、`owner.kind: player`（现有 ID 或符号 ref）、`source_lang: zh-Hans` 和 `reading_system: pinyin-syllables-v1`；赛事、原始值聚合和其他源语沿用旧路径。 |
| `content.source_reading_kind` | `published_roman_name`。它记录专业英文页实际采用的姓名，不宣称来源字段本身标注了“拼音”。 |
| `content.sources` | 本次实现恰好三条，`role` 分别为 `original`、`identity_bridge`、`reading`，每种一次。原有 HTTPS URL、HTTP 200、捕获时间、原始字节哈希、真实摘录、`observed_lang`、`language_basis`、`identity_basis` 全部保留。 |
| 每条来源的结构化事实 | 增加 `publisher_id`、`person_id_namespace`、`person_id`、`exact_name`、`birthdate`、`record_locator`。ID 必须是该出版方真实的人物键；日期为真实、日精度的 `YYYY-MM-DD`；姓名和生日均须出现在该人物的真实来源记录/摘录中。定位字段说明 API 的具体对象或人物页字段，不能用整页别人的生日。 |
| `content.source_link` | 固定 `method: official_name_dob_to_localized_profile_id_v1`；`official_match_count: 1`；`official_scope_sha256` 等于完整名册响应哈希；`unresolved_conflicts: []`；非空 `review_basis`，说明精确姓名、完整生日、站内 ID、专业人物语境和已知异常的逐项核对。唯一性限于固定名册，不能声称全网唯一。 |
| 独立批准 | 沿用 `approved_original_name_and_reading`；在 v2 中其范围明确包含整条 `source_link`、真实语种、全部结构化事实、音节及词界。原 producer/reviewer 分离、时间顺序及精确 `content_sha256` 检查不变；不再增加一层签名体系。 |

`publisher_id` 和 URL/键命名空间必须相符，不能靠自填 `official` 获得可信度。当前只准已核实的中国围棋协会名单接口与 GoRatings 人物页路径：协会 API 与官方前端的关系已有[名册捕获证据](kifu-name-china-professional-roster-batch-2026-10-03.md)；GoRatings 是专业资料出版方，不标成棋院官方机构。新增站点另审，不在这次实现中建设通用身份图谱。

原始名册使用 `publisher_id: china_go_association`、`person_id_namespace: cwa_player_no`；两个 GoRatings 页面使用 `publisher_id: goratings`、`person_id_namespace: goratings_player_id`。GoRatings 的两种语言页面是同一个出版方。这里的“双来源”是两个出版方；**现有材料需要三份页面/响应记录**。英文页没有汉字或协会编号时，中文 GoRatings 页就是不可省略的桥梁。

## 不可放宽的对应关系

机器逐项验证，独立审核者从完整留存正文复核：

1. `original.exact_name == identity_bridge.exact_name == original_name`，不做简繁、异体、空白或模糊名字归并。官方完整名单内该精确姓名必须只有一个记录；即使生日相同，有两个协会编号仍 HOLD。
2. 三条记录的日精度生日严格相同；`identity_bridge.person_id == reading.person_id`，且二者均属于 GoRatings 命名空间、对应 URL 和同一人物语言切换路径。`CWA000274` 与 GoRatings `729` 是两个命名空间，不能当作相同 ID。
3. `reading.exact_name == source_reading`，出自该英文人物页的真实姓名字段；原名、生日和罗马字不能从不同人物行拼成摘录。原始字节哈希必须由制包者计算、审核者复核，不能把发现包的拼接摘要冒充原文。
4. `source_lang` 表示原名语言；英文 `reading.observed_lang` 如实为 `en`。GoRatings 中文页实际标记 `zh` 时保留 `zh`，另用已审核正文说明简体字形；API 没有 HTML 语种时用 `reviewed_text`，不伪造 `html_lang`。按角色检查语言；不得把所有来源改填 `zh-Hans`，也不得削弱音译规则来源的目标语检查。
5. 现有 `pinyin-source-v1` 规范化相等检查继续强制执行。审核者须判断该已发布罗马字与普通话拼音体系相容，明确 `reading_words` 的音节和姓名词界；英文用名审核不会自动批准音节切分。不得从汉字猜读音、改字母、重排姓/名，或把方言、历史罗马字直接当作汉语拼音。疑义项单独 HOLD。

`pypinyin` 等工具只能检查一致性，不能提供本人的读音证据。父代理报告的本批异常是曾志豪：来源为 `Zeng Zhihao`，工具默认可能给出 `ceng zhi hao`；须按已捕获 `Zeng Zhihao` 独立审核 `[["zeng"], ["zhi", "hao"]]` 并说明多音姓例外，不能用工具结果替换来源字母。其余机械一致项仍需要同样的明确切分批准。

例如丁波的来源链为：协会 `CWA000274 / 丁波 / 1971-01-24` → GoRatings 中文 `729 / 丁波 / 1971-01-24` → 英文 `729 / Ding Bo / 1971-01-24`。这是来源记录对应；将锚点绑定到数据库 ID、创建人物或判断某盘 PB/PW 指向该人，仍需各自的独立审批。Wikidata 标签/QID 可以保留为交叉线索，不替代这条链，也不自动批准 QID 绑定。

## HOLD 与本批推进范围

缺完整生日、不同 ID、名字变体、同名多记录、来源人物语境不足、已知未解决的身份/读音冲突、非拼音罗马字、无法确定的切分、缺原始捕获或独立签署，均 HOLD；不能用已有五语 PASS 或多数来源一致覆盖它们。

**梁伟棠必须从新 v2 批次排除。** 官方/GoRatings/原候选是 `1963-10-02`，新留存中文维基正文是 `1963-06-02`。本文不裁定哪个生日正确；先另行核实并保留冲突处置，之后再签新锚点。旧五语名称审核是历史事实，不构成新来源对应链的豁免。汪美成的 Wikidata 性别冲突已有五语审核明确排除该字段作为对应依据；须保留该限制，不把它改写成没有发现过异常。

**可以立即准备待审有限批次。** 40 人中最多 39 人可制备 v2 来源对应候选；此前 35 人五语完整通过的集合再去掉梁伟棠，首个完整十一语包上限为 **34 人、204 个次要语言显示值**。另外五人的 `jp/tw` 原有 HOLD 保留；其已通过的 `cn/en` 来源可以继续整理六语锚点，但不能据此宣称十一语完成。以上数字均为准备上限，本次具体锚点/六语显示/人物/FK 新增批准数都是 0。

要成为可导入包，仍需逐人独立批准新 v2 锚点、已批准的有限语言规则、机械重算的六语结果及完整批次签署；继续执行同语碰撞、既有惯用名优先、前像/快照和十一语关联闸。四种拉丁字母语言可复用已审的罗马字复制规则；俄/乌必须分别使用已审音节映射。五语原证据须按现有导入契约整理，来源登记问题仍须解决。无需为这条 `transliterated` 路径补做六语“未找到惯用名”的负面检索。

## 兼容与最低充分验证

缺省 `anchor_format` 的旧记录按 v1 原规则验证；显式 `1` 同义。未知版本、布尔版本和 v2 字段配合旧版本均拒绝。旧签署内容与哈希不变，不重签、不迁移历史记录。旧 pending 来源若转成 v2，复制成新工件、保留原件并重新独立签署；旧名称证据批准不能沿用为新哈希的批准。

只在 `validate_transliteration_anchor` 增加严格分支/小型辅助函数。`secondary-transliteration-v1` 的渲染、规则、批次协议和数据库结构无需改版。沿用外层批准结论可兼容 `persisted_name_eligible` 当前的校验；若实现另改结论文案，必须同步持久化资格入口，不能只修离线导入。不得全局取消 `validate_transliteration_sources` 的语言限制。

实现后在现有音译测试中覆盖以下风险，不新增通用审计框架：

| 聚焦用例 | 预期 |
| --- | --- |
| 原有同正文 v1；合法三记录 v2，英文 `observed_lang=en` | 两者通过；v2 能进入现有六语批次。 |
| 无桥梁的两页，即使生日相同；同名但生日不符；桥梁与英文页 ID 不同；编号命名空间错配；官方同名双编号 | 全部拒绝；重新计算外层签名也不能绕过。 |
| 英文页谎填 `zh-Hans`；摘录没有对应姓名/生日；读音规范化或词界变更未重审；未知版本/缺角色/重复角色 | 拒绝；词界必须由内容哈希和独立批准绑定。 |
| 来源/对应链内容被改而使用旧批准；未解决生日冲突；自我审核；批准早于捕获 | 全部拒绝。 |
| 五种主语言借用此音译路径；惯用名覆盖；同语碰撞 | 继续由现有闸拒绝，复用现有测试。 |
| 一个 v2 锚点贯穿导入、持久化显示/搜索资格及完全相同的重复应用；保存后的来源链被改 | 正常链可用且重复无新增；漂移后资格失效。复用现有 SQLite 集成 fixture。 |

本次仅写决策备忘录，没有改产品代码、提交 commit、连接生产数据库或运行产品测试；以上测试是后续实现的验收条件。已完成的验证是本地来源文件、记录对应和哈希的只读核对。
