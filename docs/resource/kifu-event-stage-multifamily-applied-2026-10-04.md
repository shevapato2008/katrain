# 五组赛事阶段原文关联执行记录

2026-10-04，独立身份裁决及执行脚本代码审核通过后，按 TEST → PROD 顺序将获批的 2,694 盘关联到既有赛事类型。没有写入赛事届次，没有创建赛事、别名或翻译。

| 赛事类型 | 每库新增关联 |
| --- | ---: |
| 日本本因坊战 | 365 |
| 台湾棋王赛 | 857 |
| 台湾天元赛 | 682 |
| 日本旧名人战 | 473 |
| 日本棋圣战 | 317 |

精确范围来自[独立裁决](kifu-event-stage-multifamily-independent-decision-2026-10-04.md)，`approved_albums` SHA-256 为 `6febe341f8648745603aad4b4d621d7a8d3a688548272a95b28ed92cf8d061f3`。59270 实际属于快棋名人战；118474 日期与身份不明；两盘均未改动。16999 只关联台湾天元赛事类型，其冲突的届次和日期未作推断。

执行器 [apply_kifu_event_stage_exact.py](../../scripts/apply_kifu_event_stage_exact.py) 将环境绑定实际数据库，事务中比对获批行的原文、日期、来源、重复标记及原有空关联，仅更新 `event_id`；回滚演练与提交后的独立只读核验均成功。审核时脚本 SHA-256 为 `768b48a04da0df7abf3aa0ca6b7b6417b9911ec40f2b65f678f3d1b8d10c4466`。

| 环境 | 冻结计划 SHA-256 | 本批新增 | 提交后赛事关联／173,025 | 待查两盘 |
| --- | --- | ---: | ---: | ---: |
| TEST | `0f0646b5cc99ea00eecb65ee31fd6d2e24e0b18870f4f71a00186261bd714bcb` | 2,694 | 87,169 | 2 未改 |
| PROD | `9754e1f134e8f596f0c93b1decc1cb33257420369cc3be8c175d9a837fd750fb` | 2,694 | 87,651 | 2 未改 |

计划、回滚演练、提交和提交后核验分别保存在同目录 `kifu-event-stage-multifamily-{TEST,PROD}-{plan,dry,apply,verify}-2026-10-04.json`。
