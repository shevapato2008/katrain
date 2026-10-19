# Ranks101–150：最后五条 dependent anchor 独立复审

2026-10-03。Reviewer：`/root/hold10_independent_review_astra`。模型记录：`GPT-6; requested gpt-6-astra/max; runtime subtype unverified`。审核时间：`2026-10-03T09:23:50.405697+00:00`。

**本次 5 PASS / 0 HOLD。** 只对 producer 已生成的精确 anchor content 附加审批；未修改内容或生成替代 anchor 后自批。

| raw | 原名 / source_lang | 原发表读音与分词 | 结论 |
| --- | --- | --- | --- |
| 金明训 | 김명훈 / ko | Kim Myounghoon：kim / myoung hoon | PASS |
| 伊田笃史 | 伊田篤史 / ja | Ida Atsushi：i da / a tsu shi | PASS |
| 罗玄 | 나 현 / ko | Na Hyun：na / hyun | PASS |
| Hane Yasumasa | 羽根泰正 / ja | Hane Yasumasa：ha ne / ya su ma sa | PASS |
| 杨子萱 | 楊子萱 / zh-Hant | Yang Zixuan：yang / zi xuan | PASS |

五条都嵌入上一轮完整已签 mapping，canonical SHA 与实际审批文件、producer bindings 逐条一致。金明训、罗玄还分别绑定已签有限韩文 normalization SHA `c45c2828e6d3158095389ff325f141183c9f6ebf4c2cec3d3277f6462976da3a`、`2c193b00c8ed04bacba2e4927bbd1272c9d4a46ed8040847202a411bb60cff51`；其 owner、scope、原名、发表读音和来源数组完全一致。

mapping/normalization 审核时间均为 `2026-10-03T09:16:30.762452+00:00`，五条新 anchor 生成于 `2026-10-03T09:19:37.439286+00:00`，时间顺序真实有效。相比旧 HOLD 内容，三条只替换 mapping；金明训、罗玄另改 normalization basis。重新核验 10 份来源正文 SHA、原文片段、姓名/生日定位、profile ID 和官方链接；五条实际通过 `validate_transliteration_anchor`。

受控包：`~/.local/share/kifu-name-audit/2026-10-03/player-ranks101-150-dependent-anchor5-independent-review-astra-v1/`，目录 `0700`、文件 `0400`。

- 本审核 manifest SHA：`e6a384f18391c97d8fe0c3aa158620d576a2d1e6c49bf0c503a15a6fb8895e9c`。
- 输入 producer manifest SHA：`24c4625607bd47fc396d62006ea76b7d012c19f65855a00f62f53d36540250d5`。
- 上一轮 mapping 审核 manifest SHA：`3ae5a7e51342754ebf4d21ddd4c3f23fdc00ed2dacd4459b5297efddc3a50fd6`。
- 审批文件：`reading-anchors5.approved.jsonl`。五个完整 mapping SHA、新旧 anchor SHA、两条 normalization SHA、时间及来源实测结果位于 `checks5.actual.json`；另有 `validator.actual.json`、`summary.actual.json`、`review.py`。

既有 25 个 PASS anchor 未变，因此该有限来源谱系现在为 **30 PASS / 0 HOLD**。历史 HOLD 文件保持原样；只有本次新 anchor 获批。本审核不批准译名候选、通用规则、批次、alias 表、person FK、导入或部署，整体 import/write 仍未由本审核放行。未连接数据库、未改应用代码、未 commit/push。
