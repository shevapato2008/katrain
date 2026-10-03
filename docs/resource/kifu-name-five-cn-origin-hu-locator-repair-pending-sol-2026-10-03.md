# 胡耀宇 CWA locator 修订：生产者待审包

2026-10-03；producer `/root/anchor_format4_impl_sol`，GPT-6 运行时身份（未独立认证子型号）。按[独立审核最小修复顺序](kifu-name-five-cn-origin-primary-five-independent-review-sol-2026-10-03.md)修订；没有新增审核签署、应用代码修改、DB 连接／写入、克隆操作或 Git 提交。

独占目录：`~/.local/share/kifu-name-audit/2026-10-03/china-professional-roster/five-cn-origin-hu-locator-repair-pending-sol/`。目录 0700，产物 0400；旧包完整复制到 `input-*` 留存，不覆盖原目录。版本 `hu-locator-repair-pending-v1`；真实生产时间及 producer 保存在新 pending approval 和 manifest。

原始 CWA JSON 字节 SHA `18ba2a04efdca69d47528cbe703d9c54e1005b7f986af782434cbc3f1dd316f9` 核对通过；`data.Z08[10]` 的 `playerNo=CWA000025`、`playerName=胡耀宇`、`playerBirthday=1982-01-18` 核对通过。胡锚 content **仅**将 `sources[0].record_locator` 从 `data.[Z09] roster row playerNo=CWA000025` 改为 `data.Z08[10] roster row playerNo=CWA000025`。来源字节／摘录／捕获时间、ID、生日、读音、有限 scope 等均未修改。

- 新胡锚 content canonical SHA：`77cbe2ba871f3f2e77a3389e92dc602d265f1507108879056f993494b7fbe117`。
- 新胡锚 **pending record** canonical SHA：`59d21ce7f1449566161a2ef79a95ed10353ff52e9f08900461ca01cba459e727`。它不是完整已签锚 hash。
- 其他四锚对象逐值一致，原审批保留。五份 scope／category 仍在未经修改的 owners 输入文件，六份 rule 在未经修改的原 bundle 输入文件。
- 六 batch 的胡成员改绑 pending 胡锚；各 batch 删除原 reviewer／批准结论，记录新 producer、时间与 pending status。30 candidate 全部改绑 pending batch hash，胡六行另改 anchor hash；删除旧 reviewer、审批结论和旧最终 preimage binding。30 个输出、owner、raw、scope、rule 均逐值一致。
- 主五 25 候选仅胡五行修 locator／锚依赖及对应待审状态；将旧 `identity_anchor_full_signed_record_sha256` 改为明确的 `identity_anchor_pending_record_sha256`。其余20行逐值不变；文件级 producer／时间和依赖集合路径/hash更新为新工件。

| 文件 | 字节 SHA-256 |
| --- | --- |
| `hu-anchor.pending.json` | `507d6a08b86e39bc222fb5143a2ff2a4f78257cfceb37a1baa422b0419aa4330` |
| `raw-anchors-v3.pending.json` | `e79c156519ac16ef1c49dc0ab8567b03905a8b23ee0e42cc9bc07249983f3d96` |
| `transliteration-batches.pending.json` | `619d4a13e86b671c4b9de20b64a0fc3525672991235dfdbb275bd6a69d7bbd57` |
| `six-language-candidates.pending.json` | `b3d4f43978ec1715b72a6f970875c7016f6bc05e0fd5b00565e178cc0d6c6d20` |
| `primary-five-candidates.pending.json` | `f7cdb2c5e58cfdb442c0515f244ffbcd929ca8b2a866fe65b27be720f40f5007` |
| `validation.json` | `c14dd1e32ef040a7ef3ba2ce3ad174e38dddeb47b7ccb4040ec870f7b547a520` |
| `manifest.json` | `475b744a37a77cb04bf8adfe8b1976545b82efa5fc777b133bb8ee8d743820a4` |

验证仅检查原文位置、内容最小差异、未变依赖与输出以及待审拒绝。现有 `validate_transliteration_anchor` 如预期拒绝新 pending 锚：`transliteration content lacks exact approval`。因此未生成冒称可执行／write-ready 的最终 bundle，也未运行数据库 rehearsal。

下一阶段必须先独立复核并签署胡锚；签署会改变完整 record hash，当前六 batch／candidate／主五依赖均需再绑定到该**已签** hash。随后六 batch 独立签署，再改绑30 candidate、重新完成真实目标前像和最终审批。当前 pending hashes 仅供审阅，不得视为 approved 依赖；历史 clone PASS 不移用到这些新工件。
