# Ranks101–150：十条 HOLD 修正的独立审核

2026-10-03。Reviewer：`/root/hold10_independent_review_astra`。实际可确认模型身份为 `GPT-6`；请求配置为 `gpt-6-astra/max`，运行时未提供可独立核实的子型号证明。审核时间：`2026-10-03T09:16:30.762452+00:00`。

**结论：5 mapping PASS；6 有限韩文别名关系 PASS；5 修正 anchor PASS；另 5 dependent anchor HOLD。整体 import/write HOLD。** 本轮只对 producer 的既有精确 content 附加独立审批，未生成替代内容后自批。

| 审核对象 | 结论与精确范围 |
| --- | --- |
| 5 mapping | **PASS**：金明训、伊田笃史、罗玄、Hane Yasumasa、杨子萱。`research_record_sha256` 均等于上一轮完整已签 external-profile identity 记录的 canonical SHA；URL、有限 raw scope、原名、官方正文和完整生日一致。只批准这五条 raw→original 对应。 |
| 6 韩文关系 | **PASS**：金彩瑛、金明训、罗玄、安成浚、徐能旭、金惠敏。逐人 owner、有限 scope、已签身份、发表别名、Hangul 和逐音节关系一致。 |
| 5 修正 anchor | **PASS**：金彩瑛、安成浚、徐能旭、金惠敏、徐靖恩。前四条仅修改 `reading_normalization_basis`；徐靖恩仅修改 `source_lang` 和 `original_language_basis`。五条全部实际通过 `validate_transliteration_anchor`，未改变原发表读音。 |
| 5 dependent anchor | **HOLD**：金明训、伊田笃史、罗玄、Hane Yasumasa、杨子萱。新 anchor 尚未提供；旧 anchor 未获得审批。 |

六个有限关系如下；RR 列只解释韩文字母值，不替换已发表拼法，也不批准通用别名倒推规则或姓氏拼写标准。

| raw | 已发表 tokens | Hangul | RR 参考 |
| --- | --- | --- | --- |
| 金彩瑛 | kim / chae young | 김 / 채 영 | gim / chae yeong |
| 金明训 | kim / myoung hoon | 김 / 명 훈 | gim / myeong hun |
| 罗玄 | na / hyun | 나 / 현 | na / hyeon |
| 安成浚 | an / sung joon | 안 / 성 준 | an / seong jun |
| 徐能旭 | seo / nung wuk | 서 / 능 욱 | seo / neung uk |
| 金惠敏 | kim / hye min | 김 / 혜 민 | gim / hye min |

冻结的韩国国立国语院正文 SHA `d3921e37c9b96b913f15157552f7db5113769ccbea4f193a842f67527fa27540` 已重算；Section 2 与 3(4) 支持逐音节参考，3(7) 允许既有专名拼法。`김→kim` 只签这几个人实际发表的姓氏拼法；`gim` 不构成修改 Kim 的要求。四个已签 anchor 的 content 仍指向原 pending normalization 的精确 SHA；审核元数据同时绑定其独立已签 normalization 记录。

徐靖恩的海峰冻结正文 SHA `d227fc1aea622ac223fca9bf07235865f1009582815638d0648da7e6b022fd5f` 与 manifest 相符。实际正文含 `html lang="zh-tw"`、繁中叙述、本人姓名及 `2006年12月26日生`；同一 GoRatings 2077 档案链接该海峰页面。故 `zh-Hant` 描述有来源支持的原生脚本语境，未凭三字字形或网站国别推断。`Xu Jingen / xu jing en` 原样保留。

受控包：`~/.local/share/kifu-name-audit/2026-10-03/player-ranks101-150-hold10-independent-review-astra-v1/`，目录 `0700`、文件 `0400`。

- 本审核 manifest SHA：`3ae5a7e51342754ebf4d21ddd4c3f23fdc00ed2dacd4459b5297efddc3a50fd6`。
- 输入 producer manifest SHA：`370009820acb32f2a3b67b986f3c0173ad3dc05d2ba59cdd8ff42746afabafdd`。
- 上一轮 identity/reading 审核 manifest SHA：`dc034fd59cc13fea4d146854e114eab22e59e18574444c4fffba908a48f9670c`。
- 产物：`mappings5.approved.jsonl`、`korean-alias-normalizations6.approved.jsonl`、`reading-anchors5.approved.jsonl`、`reading-anchors5.HOLD.jsonl`；实际来源、SHA、span、scope 及 validator 结果在 `checks.actual.json`、`validator.actual.json`、`summary.actual.json` 与 `review.py`。

下一步由 producer 将完整已签 mapping 嵌入五条新 anchor，且每条 `anchor.produced_at >= mapping.reviewed_at`；本次最早时间为上述审核时间。金明训、罗玄还须携带本次已签的逐人 normalization。随后独立审核新 anchor，不可在旧记录倒填时间。

此前 20 PASS anchor 和 26 context exclusions 保持原状；本来源谱系现有 **25 PASS / 5 HOLD**。本轮没有批准译名候选、次六语规则、批次、通用 alias、person FK、导入或部署；未连接活动数据库、未改应用代码、未 commit/push。
