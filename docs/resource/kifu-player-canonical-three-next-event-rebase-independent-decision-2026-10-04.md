# 三棋手计划接纳九条已提交赛事变更：独立决定

**通过，限定为九个精确 `event_id: NULL → 75` 后像。** TEST 与 PROD 的原始棋手批准仍各为 **1,529 槽**，HOLD 仍各为 **580 槽**。本次仅离线核对本地证据；没有数据库读写或代码修改，也没有新增写入授权。

[机器决定](kifu-player-canonical-three-next-event-rebase-independent-decision-2026-10-04.json)文件 SHA-256：`aa2e104ca58ee2f884a1566fe38b664d74298960ed3616af1d51c6b3625d78b9`。

| Album ID | 三棋手槽 | 原棋手决定 | 接纳的赛事变化 |
| ---: | --- | --- | --- |
| 36687 | 工藤纪夫／黑 | HOLD，FK 保持 NULL | NULL → 75 |
| 36688 | 工藤纪夫／白 | HOLD，FK 保持 NULL | NULL → 75 |
| 36755 | 工藤纪夫／白 | HOLD，FK 保持 NULL | NULL → 75 |
| 65378 | 工藤纪夫／白 | HOLD，FK 保持 NULL | NULL → 75 |
| 65387 | 工藤纪夫／黑 | HOLD，FK 保持 NULL | NULL → 75 |
| 66039 | 工藤纪夫／白 | HOLD，FK 保持 NULL | NULL → 75 |
| 66058 | 工藤纪夫／白 | HOLD，FK 保持 NULL | NULL → 75 |
| 66326 | 工藤纪夫／黑 | 已批准；TEST 348／PROD 347 | NULL → 75 |
| 103013 | 赵善津／白 | 已批准；TEST 542／PROD 541 | NULL → 75 |

九条均属于已批准的「中日围棋对抗赛」。与日本职业十杰战批准项、next-event 的 453 个 HOLD、此前 47 条日本大赛变化、8 条 mixed11 对手 FK 变化的交集均为空。两个环境中，这九条 next-event 执行前像的全部共有字段均与各自冻结棋手审核一致，包括棋手 FK、日期、赛事原文、来源和 SGF SHA-256。

七个棋手 HOLD 原因均为 `EV_GN_missing_or_different_titles`，保留原审核结果。独立的赛事类型批准不能据此解除棋手 HOLD。

执行器应固定以下证据，保留现有 mixed11、日本大赛以及棋手审核 SHA：

- [next-event 决定](kifu-event-next-scope-independent-decision-astra-2026-10-04.json)文件 SHA：`84eace6d50f3029fc4dcd353b1b3e31dece649376c6fccae2d595263c32d5088`。
- [比较计划](kifu-event-next-scope-compared-plan-2026-10-04.json)文件 SHA：`b2336ca4c02f6a26bfb3144ad5cef4c604f7776900b9b0554bd42dc78567698e`；内部计划 SHA：`7e54d349be3e252ddc27894af82b40221567f494f05d932459ca80ffa6fd6262`。
- [已应用记录](kifu-event-next-scope-applied-2026-10-04.md)固定两个环境的实际目标 ID 为 75，十杰战为 44。原比较计划在插入前捕获，新赛事 ID 仍是 NULL；实际 ID 不可由该 NULL 或 sequence 推断。机器决定记录了各环境捕获 SHA 与应用记录 SHA。

最小实现是在 `approved_intervening_deltas` 中添加上述精确九 ID 集合，校验决定、比较计划、环境及原像后，仅增加 `(album_id, event_id): (None, 75)`。要求计算所得交集完全一致，拒绝已有 delta key 冲突，并核对总计 **64 个变化字段：56 个赛事 FK、8 个对手 FK，涉及 62 盘**。此前日本大赛与 mixed11 在 134184、134220 两盘有不同字段的重叠，本次九盘没有这些重叠。

在捕获与事务后独立验证中核对 `kifu_events` 的 `(75, 中日围棋对抗赛)`，并把该表加入现有 dry/apply 锁定边界。九盘当前赛事 FK 必须严格为 75；NULL、44、dry 消耗的 sequence ID 或其他值均应失败。其他字段继续按完整冻结行及既有批准变化逐项核对。将新证据 pin 写入重新捕获的三棋手计划。

聚焦检查只需扩展现有测试：两个环境的精确 64 字段集合、错误／过期赛事后像、ID 75 目录身份错误、七个 HOLD 中代表性棋手 FK 变动。复用已有 SGF 漂移、CAS、回滚及事务后验证。分别重新捕获 TEST／PROD，按现有 dry 和计划审核流程继续；旧计划不能复用。

主要风险是把赛事批准误当作七个棋手 HOLD 的解除，或放宽到任意赛事 ID、任意原始赛事文本。上述精确成员、SHA、前后像及目录约束将接纳范围限定为已提交的九条背景变化。
