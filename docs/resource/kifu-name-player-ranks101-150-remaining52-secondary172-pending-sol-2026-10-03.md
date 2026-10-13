# Ranks101–150：剩余 direct52 与 secondary172 有限候选组装

2026-10-03。Producer `/root/player30_remaining_translation_producer_sol`，GPT-6（运行时 subtype 未独立核实）。仅使用本地冻结材料；没有数据库连接、代码改动、commit/push 或自批。

受控包：`~/.local/share/kifu-name-audit/2026-10-03/player-ranks101-150-remaining52-secondary172-pending-sol-v1/`，目录0700、文件0400。manifest SHA `ea0899908b5e711908fb6b7918dd0bff646c06f66e0294c74aed4621862bda34`。所有输入包 manifest 内容逐文件核验，30条 anchor 实际通过现有签名/来源正文校验。完整已签 anchor/scope hash 逐格绑定。

| 有限成员 | 实际数量 / 状态 |
| --- | --- |
| 新获批10位锚点的 direct cells | **52 pending**：cn/jp/ko/en/tw各10、fr2 |
| 既有20位 direct cells | 103 保留原已审包，未重新生产或批准 |
| 六语 source-only proposals | **172**：50 rule members pending、122 HOLD |
| 兼容已签规则的 pending members | de13、es13、fr11、tr13；4个有限 batch content pending |
| 缺兼容 source-language/reading rule | 96：ja36、ko48、zh-Hant12 |
| 有 zh-Hans 规则但缺实际音节 token | 26：13位的 ru/ua 各1 |
| 新审批 / 名称字符串变更 / DB读写 | 0 / 0 / 0 |

52条 direct research 实际通过 `validate_research_record`；其 bundle 离线结果 `approved=0 / pending=52 / write_ready=false`，只有10个 owner 尚缺 independently approved display decision 的预期错误，无 write errors。保留原26 context exclusions；历史前像仍为2026-10-03 07:36:56 UTC capture，不能作为当前数据库新鲜检查。

50个 Latin member 输出逐字等于冻结源字符串，引用已有 source_lang=zh-Hans / pinyin-syllables-v1 已签 copy rule；没有将 ja、ko 或 zh-Hant 偷换为该范围。26个中文 Cyrillic成员在现存三组实际已签 ru/ua规则上均缺 token；没有加 token、回退或改写原字符串。122条 HOLD 保存原 proposal 与其 hash。pending batch 只提供精确 `content` 和 producer 状态；没有制作假 approval，不是 importer-ready signed batches，也没有将50个成员冒称已批准译名候选。

合并历史103、剩余52及secondary172，**owner/lang重复0、跨owner同语规范化姓名碰撞0**。这个有限集合检查不证明 canonical身份、历史legacy rows或当前线上碰撞已解决；沿用冻结空 approved-name snapshot，不签 `distinct_people_confirmed`、alias或person FK。

关键文件：`bundle.direct52.pending.json`、`research.direct52.pending.jsonl`、`candidates.direct52.frozen-preimage-bound.pending.jsonl`、`direct52.crosswalk.actual.json`、`secondary.rule-members.pending.jsonl`、`secondary.rule-members.HOLD.jsonl`、`transliteration-batches.content.pending.json`、`rules.available.signed-index.actual.json`、`rule-render-comparisons.actual.json`、`overlaps-collisions.actual.json`、`summary.actual.json`。`build.py`记录生产过程；固定v1输出目录使其不是可直接重复运行的覆盖脚本。

精确依赖包括 fresh-bulk155 `36de195a01a1d9863f13c14adff8ac2d4e6c7bd09917c62338edc8ee8351f894`、历史direct103审批 `bc9232609f962781137048b731df4f91dc1a58fe42f1f1cea45ba786810f0fe2`、最后dependent5审批 `e6a384f18391c97d8fe0c3aa158620d576a2d1e6c49bf0c503a15a6fb8895e9c`；其余完整依赖见包内 `dependencies.json`。规则索引保留每个实际签记录 canonical hash、来源绝对路径和来源文件字节hash。

下一步是独立审核52个 source candidate/research/历史前像绑定，以及50个有限rule members与4个batch content；122条继续HOLD，等待兼容规则或实际token表获批。后续真实目标库dry-run/apply及新鲜前像、verified碰撞和schema闸门未由本包授权。
