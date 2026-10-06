# EG 五位棋手的 Wikidata 韩文标签处理决定

2026-10-06；`/root/historical_ko_policy_astra`，`gpt-6-astra`。补充[历史日本棋手韩文名政策](kifu-historical-japanese-korean-name-policy-2026-10-06.md)。本次只读证据与代码并记录决定，没有代码/数据库修改，也没有签署具体姓名候选。

**决定：允许已有 `generated` + v1 有限闭环路径继续。五个真实韩文标签必须作为正面发现线索保留，可由独立审核者明确认定“单独的 Wikidata 标签不足以证明可采纳惯用名”，以既有 `rejected_leads` 表达。此后按本人日文读音与国立国语院规则独立审核生成值；无需把取得额外韩文发表页设为必经步骤。**

本次逐一读取 `/tmp/kifu-player-next5eg-20261006/sources/` 内五份 `*-wikidata-Q*.jsonbody`，重算 SHA-256 均与对应 `.json` 抓取记录一致，记录的 HTTP 状态均为200。实际内容如下，五项均无 `ko` aliases 和 `kowiki` sitelink：

| PROD ID | 原名 | Wikidata | 实见 `labels.ko.value` | JSON SHA-256 |
| --- | --- | --- | --- | --- |
| 6270 | 長谷川章 | [Q11653942](https://www.wikidata.org/wiki/Special:EntityData/Q11653942.json) | 하세가와 아키라 | `cff6d3e06ca2b7a02d08c6c8a2972c093ad9268e63517dbddeb0e105029e26c1` |
| 5244 | 橋本誼 | [Q15197135](https://www.wikidata.org/wiki/Special:EntityData/Q15197135.json) | 하시모토 요시미 | `7ecebc88c869f531670c694c73cab779496a7a63e219224455265c07617fe4b4` |
| 6260 | 鍋島一郎 | [Q107570281](https://www.wikidata.org/wiki/Special:EntityData/Q107570281.json) | 나베시마 이치로 | `b21482f4c97991ab242e87a527f683ec2bf57cbbb0f15f1e61a6134376f668de` |
| 6252 | 鈴木五良 | [Q107657878](https://www.wikidata.org/wiki/Special:EntityData/Q107657878.json) | 스즈키 고로 | `327e57a0a76de448453a8b7ce1e08255786461920911de040d088f3d3164db7b` |
| 6581 | 星野紀 | [Q29410853](https://www.wikidata.org/wiki/Special:EntityData/Q29410853.json) | 호시노 도시 | `136d69e2b8b4db0bc849f368de608c97493f0303e69235d0faa1e384f6ca3f42` |

也已读取现有日文读音正文：長谷川章来自 Kotobank 收录的人名辞典，橋本誼来自日本棋院本人档案，其余三位来自 igorating 的具名棋手页。它们的来源角色应分别保留，不能统称“官方假名”。这些读音与上表输出之间的国立国语院转写关系可供候选审核使用；上表记录实见标签，不代表姓名行已批准。

**闭环的准确命题是“在已完整检查的有限范围，未取得足以批准 `conventional` 的惯用名证据”。** 现有 `negative_outcome=rejected_leads` 正是保留发现文本及其不被采纳理由的分支；`no_target_string` 不适用于这五条。Wikidata 的 `tier=discovery` 保持不变，韩文实际语言仍记录为 `ko`。机器枚举 `decision=rejected_for_target_language` 的理由必须写清：拒绝的是作为韩文惯用名的独立证据资格；标签确实存在、确实是韩文，也未被认定为错误。不能写成“无韩文名”“标签缺失”或“非韩文”。

最小剩余操作：

1. 保留原 EntityData 抓取不动，补取或复用真实 `/w/api.php?action=wbgetentities` 响应；逐个精确 Q 项查询 `props=labels|aliases|sitelinks`、`languages=ko`、关闭语言回退，可加 `sitefilter=kowiki` 收窄所请求站点。v1 验证器要求该 API 形状，不能把现有 EntityData 的 URL 改写成未请求过的 API。
2. 每条源检查保留标签的真实 JSON/哈希，在 `known_leads` 与 `rejected_leads` 列出该标签、同人 Q、原名、实际 `ko` 和证据资格判断。检查层的 `status=not_found` 只表示没有通过惯用名准入的结果，必须同时有 `negative_outcome=rejected_leads` 和上述精确范围说明。保留独立 `gpt-6-sol` 审核者真实身份、模型、理由及时间；本政策文档不能代替那份签署。
3. 继续完成当前 registry 的韩国棋院和韩语维基有限查询及全部已知线索处置。本目录目前未见韩国棋院抓取；若其他目录已有完整记录，直接复用。真实访问失败、无正文或未完成分页不能记成完成。韩语维基有真实同人文章时，按用户既有授权采用其用名。
4. 完成 v1 闭环后，独立审核具体 `generated_review`，绑定本人读音、确切输出、`nikl-ja-ko-personal-name-v1`、规范来源及研究哈希，再沿原25项 TEST→PROD 流程。输出与 Wikidata 相同不改变 `generated` 性质；依据仍为有来源读音和规则。

代码依据：`name_candidates.py` 的 `generated` 分支及 conventional 来源层级检查；`name_evidence.py` 的 `_validate_negative_outcome`、`_validate_negative_closure`。v1 支持被独立排除的已发现线索；只有 v2 的 Wikidata 分支调用 `_validate_entity_identity` 强制目标字段完全不存在。此决定沿 v1 原有语义执行，不利用 v2、不升级来源层级、不删除或隐瞒正面标签，也不省去其他必需来源。遇到真实可靠惯用名或未解决冲突时重新按具体证据处理，不以本决定自动排除它。
