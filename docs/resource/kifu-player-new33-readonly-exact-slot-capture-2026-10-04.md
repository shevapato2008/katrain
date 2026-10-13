# new33 身份候选：TEST/PROD 只读精确逐槽前像捕获

提案：`kifu-player-new33-independent-identity-proposal-astra-2026-10-04.json`（本次按用户提供 SHA 前缀 `c1a04c` 绑定）。本文件只读，未执行任何 INSERT/UPDATE/DELETE，也不批准任何 FK。完整压缩 JSON：`kifu-player-new33-readonly-exact-slot-capture-2026-10-04.json.gz`。

## 捕获基线

- TEST：`katrain_db`，DB 时间 `2026-10-04 09:44:37.317049+00:00`，7373 slots / 7168 albums。
- PROD：`katrain_prod_20260725`，DB 时间 `2026-10-04 09:44:06.955775+00:00`，7373 slots / 7168 albums。
- 两环境 exact `(album_id, side, raw)` 集合一致；slot drift：PROD-only 0，TEST-only 0，共同 7373。
- 目录 FK 差异保留在每个 slot 的 `current_fk`、`opponent_fk` 及 catalog 快照中；不能据此直接归并。
- 捕获含每个完整 album 行、SGF 原文和 SHA-256、解析根属性/摘要、两侧 raw/rank/FK、event/event_id/edition、日期/result/duplicate、album_sources 与 source catalog、引用赛事/edition、全量 player/alias/name catalog，以及 33 个 raw staging 行。

## 提案成员

- approved capture scope：24 raws，4904 historical candidate slots（23 new + 杉内寿子 existing）。
- HOLD：9 raws、2469 slots，完整保留并单独列于 `hold_seed_membership`；不因本次捕获解除 HOLD。
- 当前 seed membership digest：all `e900cb56f769b4c9959418845a0f1884b44ac62c4d40bc2afcfc0e386c53cc4a`；candidate `598074b9bf2b7faca76234e1aa603bde12fc13ad44e645ef7147cdfd896ea5b3`；hold `b98a3ef147aa53b1634ec1d22824b55e2e55812efdf4d51de22404d824f1a4b1`。

## 差异与疑点

`semantic_album_differences`、`slot_drift` 和每个环境的 `sgf_parse_error` 是机器可读审查入口。事件 next3 后续可能改变约 2153 行；本文件是 `2026-10-04 09:44:37.317049+00:00` / `2026-10-04 09:44:06.955775+00:00` 的可重基线，任何后续执行前必须按完整前像 hash 重新 capture/rebase。

提案的 identity approval 不等于逐槽 approval；日期/段位/同局对手/SGF PB-PW-DT-SO/赛事上下文仍需下一轮独立 exact-slot decision。
