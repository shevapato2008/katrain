# 剩余 120 名高频中国棋手的六语读音锚点候选

2026-10-03。此包是**待独立审核的来源/读音候选**；没有批准目标语显示名、数据库人物、棋谱归属、外键或线上写入。

从已冻结的 153 人四语专业资料候选中，扣除独立通过来源锚点的 33 人，得到 120 人、对应 10,793 个原始棋手槽位。逐人复用中国围棋协会职业棋手名册中唯一的精确姓名、编号及完整生日，以及同一 GoRatings ID 的中文人物页。英文人物页中 26 份复用前轮留存的原文及真实采集时间，另外 94 份新抓取并留存。120 份英文页的标题姓名和完整生日均与候选相符；英文页给出已发表的罗马字姓名。来源页面：[中国围棋协会职业棋手名录](https://www.weiqi.org.cn/player/professional)、[GoRatings 人物页](https://www.goratings.org/en/)。

用本地 `pypinyin 0.55.0` 仅提出音节切分，再要求分组后逐词无声调拼写与已发表的英文姓名精确相合；120 人均只有一种满足条件的切分。这种机械一致性不是读音审核，尤其复姓、异读、多音字和历史惯用拼法仍需独立复核。每条候选含三份来源的真实连续正文摘录、原始文件路径及 SHA-256、实际采集时间、姓名/生日/ID、完整 `reading_words` 和候选来源对应理由。待审内容已逐条通过双出版方 v2 锚点的结构校验，但没有伪造审核签名。

梁伟棠有额外的出生日期冲突：当前中文维基百科的六月字段与其直接引用的台湾棋院存档十月字段不符。候选明确引用[独立字段排除裁决](kifu-name-liang-weitang-dob-conflict-sol-2026-10-03.md)的受控工件 SHA `c33a2653b28154bd830d097b9c64194e3897f400140c3940f4d25b21b21586fb`，并保留复核要求；其十月日期不能仅凭本候选视为人物事实定论。

受控目录 `~/.local/share/kifu-name-audit/2026-10-03/china-professional-roster/secondary-six-remaining120-anchor-candidates-root/` 为 `0700`，文件为 `0600`。英文页捕获目录为同级的 `secondary-six-remaining120-en-capture-root/`。审核者应对所有 120 条原文、摘录、对应关系和音节决定逐项核查，异常项单独 HOLD。

| 工件 | SHA-256 |
| --- | --- |
| 上游 153 人候选 `candidates.pending.jsonl` | `7b6b592aeb59afa8a2243b542e93eb2e105e15b6beb9631d33c38d105c7518c0` |
| 英文页 `capture.pending.json` | `bb69278f3d6ca017c3f07bb13e1b2af68fb563d9b3051e721e2e4e41fc0a5861` |
| 本批 `candidates.pending.jsonl` | `426c03599195142a0f8a5ce04ebdc29f2d7ba5ac85e715ac7df6911fdcfdf514` |
| `manifest.pending.json` | `399cd47693c625362e04b9dfec823ae70fd896958ffb2ea16d1e7399d79be190` |

英文页索引新抓取成功率为 94/94，合并复用页后 120/120 的英文姓名与生日均字面匹配。这些计数仅衡量来源候选完备性，**不等于五语、六语或生产覆盖率**。
