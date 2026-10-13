# Provisional 20 exact approval plan and dry run

状态：**TEST 与 PROD dry run 均通过并已回滚；未实际写库。** 本步骤不含翻译。

## Pinned plans

- PROD: `kifu-player-provisional20-PROD-exact-plan-2026-10-04.json`, SHA-256 `9bdce156c3963b0d7b3f8be54f89b2b1fa8e58fdbb6eb5e21afc719e185331b0`
- TEST: `kifu-player-provisional20-TEST-exact-plan-2026-10-04.json`, SHA-256 `3586bf667d0f3a1d6c20d94b9a34a9f0fbd84241f07be8c0e567e402fc610b90`
- 独立审核正文 SHA-256：`8b3311c1e6f3641c749163c538c634459a6e43b3888bf3370c0e0459243cb736`

两份计划各含 20 个唯一 `raw_id` / `raw_value`，槽位求和均为 13,633。PROD inventory SHA 为 `51102a1992e24aec038cb0d04d7c65a2fd5ffb1083e0e528e931e53cefca1845`；TEST 为 `cc46067736fa3895c85963d88fdacd91aaf6dd1d2b5da3dc843d3df26a8d237c`。数字 `player_id` 按环境分别固定。

## Exact mutation

只更新 `kifu_raw_player_values` 的 20 行：

- `review_status`: `pending` → `approved`
- `review_metadata.kind`: `provisional_person_link` → `verified_person`
- 保留并前像校验环境专属 `player_id` 与 `inventory_sha256`
- 新 metadata 固定 `canonical_name`、逐 raw `source_url`、`reviewer=codex-independent-review`、具体 `identity_reason`、独立审核 `review_sha256`

`kifu_albums` FK 更新 0；canonical 新建 0；canonical 重命名 0；alias 更新 0；名称/翻译更新 0。

## Dry-run result

两库分别在 `SERIALIZABLE` 事务中锁定 raw staging 表，校验完整前像，执行 20 行精确 UPDATE，核验后像后 `ROLLBACK`：

| check | PROD | TEST |
|---|---:|---:|
| exact raw preimages | 20 | 20 |
| matching linked slots | 13,633 | 13,633 |
| wrong/null album FK slots | 0 | 0 |
| target canonical conflicts | 0 | 0 |
| simulated approved rows | 20 | 20 |
| simulated verified metadata rows | 20 | 20 |
| post-rollback pending/provisional rows | 20 / 20 | 20 / 20 |

`canonical_conflicts=0` 表示每个计划 target 的 `canonical_name` 在相应环境恰好一个目录行；李世石与李世石九段有意共享同一 canonical，不是冲突。应用仍须由 root 审核计划 SHA 后另行执行，并在锁内重复同一前像断言；本报告不授权 apply。
