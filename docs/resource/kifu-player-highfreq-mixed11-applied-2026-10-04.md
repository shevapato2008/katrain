# 高频棋手 11 人 exact 关联执行记录

2026-10-04。独立身份审核后，TEST 与 PROD 各关联 **2,922 个精确姓名 NULL 槽**：吴依铭 325、鲁佳 317、伊凌涛 312、孙喆 307、卢钰桦 298、蒋其润 293、福冈航太朗 232、大竹优 225、酒井佑规 208、寺山怜 203、刘宇航 202。保留 30 个待查槽（包括 5 个定段前业余对局），不创建或合并目录 ID，不改原始 SGF、段位或五语名称。

冻结 review 见 `kifu-player-highfreq-mixed11-revised-review-{test,prod}-2026-10-04.json`；[独立审核说明](kifu-player-highfreq-mixed11-independent-review-2026-10-04.md)。旧的 2,927 槽计划已作废。

| 环境 | 修订 review SHA-256 | 冻结计划 SHA-256 | 提交后棋手关联槽／346,050 | 完整关联棋局／173,025 |
| --- | --- | --- | ---: | ---: |
| TEST | `eb1f30ac7ec46a1e7c36bea7436f7b60da31d02d0a65c54b68f52b2a7977d678` | `1ab5318de70a4d1f0cffa0f2beb98fb5912c95efe60d4c10a7d596d5513d5321` | 293,002 | 65,131 |
| PROD | `9b54573cd315746875d8ea9e577e440b63a12f630fbe9ef3a1f8b1547a2c7bd3` | `e49f76c817a8990978faeb5aa2e9bf4c05f35e9fb95da7001e860b1d8df284a1` | 294,607 | 66,119 |

两库分别重新 capture → 真实事务 rollback dry-run → 检查 rollback 后完整范围不变 → TEST apply/完整 exact scope 复核 → PROD apply/完整 exact scope 复核。提交后从两库只读查得表中实时计数；event_id 总数保持 TEST 89,497、PROD 89,979。
