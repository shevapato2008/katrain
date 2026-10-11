# 中国阿含 793 之后的下一批赛事候选（只读）

在逻辑排除中国阿含桐山杯已批准的 793 盘后，当前 PROD 未关联赛事的预处理候选中，最高量且边界较清楚的两个 core 是 **韩国GS加德士杯 399 盘**与**韩国女子国手战 357 盘**。本包只冻结候选范围，没有作赛事身份决定，也没有写数据库。

|候选组|盘数|exact raw|日期范围|候选规范名|
|---|---:|---:|---|---|
|`kr_gs_caltex`|399|227|2005-09-08–2026-01-09|韩国GS加德士杯|
|`kr_womens_guksu`|357|144|1996-07-29–2025-12-18|韩国女子国手战|
|合计|756|371|1996-07-29–2026-01-09|待独立审核|

## 固定范围与保护

- TEST `katrain_db` 和 PROD `katrain_prod_20260725` 分别在 `REPEATABLE READ READ ONLY` 事务中冻结同一 756 个 exact ID；所有 `event_id`、`event_edition_id` 均为 NULL。
- 每个环境的完整 756 个 album 行、756 个来源关系、全部赛事／别名／届次／来源目录、引用棋手和 4,273 个既有 HOLD 槽位均在各自前像中冻结。4,273 个 HOLD 在两库都仍为 event/edition NULL，且与候选无交集。
- PROD 有 79 个赛事类型、96 个别名、1,535 个届次、2 个来源目录；TEST 有 79／95／1,535／2。按现有规范化键检查，两个候选名均未与赛事或别名碰撞。
- 日本阿含桐山杯及所有泛化阿含 raw 全部排除；现有 `日本阿含桐山杯` ID 39 不属于本范围。中国阿含已批准 793 个 ID 也只作逻辑排除，未假定其已落库。

## SGF 检查与待审核项

756 盘全部通过项目 `BaseGame` 回放（经 `build_steps_from_sgf`，忽略劫）；全部为 19 路，原始 event 逐字存在根 GN/EV。该检查不验证超级劫或终局计分。

范围内没有完全相同 SGF，但有 4 组相同主线候选，均在韩国女子国手战组：`3238/8426`、`3464/8430`、`13377/13398`、`20183/20274`。它们应在独立审核中 HOLD 或另行决定；本包没有选择保留记录。另有 6 盘 uploader/source 为 NULL（689、693、705、713、894、916），2 盘 result 为 NULL（103835、122369），原值均完整保留。

## 文件与 SHA-256

|文件|SHA-256|
|---|---|
|`kifu-event-next-after-china-ahan-candidate-request-2026-10-04.json`|`505d364ebba4e80ae4578212f9702bf07abf6c788c47ad4423475dabe501d74e`|
|`kifu-event-next-after-china-ahan-TEST-full-preimage-2026-10-04.json.gz`|`4639f68fa868c69e2be52f5b35b91cf6e23b3f44d7f171c6a0f9900f83c6aa13`|
|`kifu-event-next-after-china-ahan-PROD-full-preimage-2026-10-04.json.gz`|`5e919068df3f5cd773fbc13ae7ccf1eaf5aad7ee7a98268cb631d5c134a7b3ee`|
|`kifu-event-next-after-china-ahan-candidate-scope-2026-10-04.json.gz`|`fd0b4c21fb85d642e2a8286de3ec53e16e7d0617096206a98d0e5e62460b66cc`|
|`kifu-event-next-after-china-ahan-candidate-statistics-2026-10-04.json`|`61c5b3436cb5a6c23285520b1fa31b6d7a2f96edb02959f35061f6ae76a520e6`|

下一步只应由独立审核者确认两个赛事身份边界，并按 exact ID 把 756 盘拆成批准／HOLD。任何执行计划必须重新绑定这些环境独立前像，不得按 raw 文本模糊更新，也不得写届次、别名、原始字段、SGF、棋手或来源。
