# 日本六大棋战 exact 类型关联执行记录

2026-10-04。按 [独立赛事身份裁决](kifu-event-japanese-major-next-independent-decision-astra-2026-10-04.md)，TEST 与 PROD 各新增 **1,839 盘**赛事类型关联，复用日本碁圣、十段、棋圣、名人、王座、天元六个已有类型 ID；1,360 盘保留待查。只更新 `event_id`，未写届期 ID、棋手 ID、原始棋谱或赛事名称翻译。

在赛事裁决后提交的 mixed11 棋手批次改变了此范围内 89 盘的 90 个棋手 FK。第二次独立裁决确认这些均来自已审 mixed11 精确计划；执行器保持原赛事裁决 SHA 不变，并固定两库完整 3,199 行棋手 FK 的新 SHA。其他赛事、棋手原文、SGF、目录及 HOLD 前像均逐项检查。执行器在 [脚本](../../scripts/apply_kifu_japanese_major_exact.py)，独立代码审核 PASS；5 项聚焦测试通过。

| 环境 | 冻结计划 SHA-256 | 新增赛事关联 | 提交后赛事关联／173,025 | 完整关联棋局／173,025 |
| --- | --- | ---: | ---: | ---: |
| TEST | `fa154418e27a3cc70158ae226a7ecf4fdb1564ce3021271ae94f654d8da84d2a` | 1,839 | 91,336 | 66,616 |
| PROD | `8038151d0959cbd58691574071195b9664ced593879b0d8c2c34a3a78a609cea` | 1,839 | 91,818 | 67,630 |

顺序为两库只读 capture、真实事务 rollback dry-run、回滚后捕获文件逐字节相同、TEST 提交及只读全范围 verify、PROD 提交及只读全范围 verify。两库 verify 均返回 1,839 个批准关联和 1,360 个 HOLD 符合预期。捕获计划存于 `kifu-event-japanese-major-next-{TEST,PROD}-capture-2026-10-04.json`。
