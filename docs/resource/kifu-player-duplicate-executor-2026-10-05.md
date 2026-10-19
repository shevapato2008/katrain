# 有限重复棋手合并执行器

本工具只支持现有两对数据提案，不判断新身份、不生成译名：

| 对象 | PROD 保留 / 退役 | TEST 保留 / 退役 | 迁移 / 原槽保护 |
|---|---|---|---|
| 朴文垚 / 朴文尧 | 4885 / 4886 | 10670 / 10671 | 328 / 238 |
| 李喆 / 李哲 | 752 / 4982 | 753 / 10766 | 314 / 247 |

入口是 `scripts/kifu_player_duplicate.py`，消费原
`kifu-player-single-duplicate-proposal-v1` pending JSON 与 `current.json.gz`。
`--plan-sha256` 指原提案 **canonical JSON SHA**，不是文件字节 SHA。
前像同时检查 gzip 文件字节 SHA 和解压后的 canonical SHA。

执行命令：

```sh
python scripts/kifu_player_duplicate.py check --plan PLAN --preimage CURRENT --plan-sha256 SHA
python scripts/kifu_player_duplicate.py dry-run --plan PLAN --preimage CURRENT --plan-sha256 SHA
python scripts/kifu_player_duplicate.py apply --plan PLAN --preimage CURRENT --plan-sha256 SHA \
  --review REVIEW --review-file-sha256 REVIEW_BYTES_SHA --actor-id ACTUAL_ACTOR
python scripts/kifu_player_duplicate.py verify --batch-id ID
python scripts/kifu_player_duplicate.py undo --batch-id ID
```

数据库 URL 使用环境变量 `KATRAIN_DATABASE_URL` 或 `--database-url`。
PostgreSQL 环境名须匹配提案中的实际数据库名。

独立审查者应在实际审查原资料、精确计划和执行代码后产生以下 review JSON。
执行器不会生成批准；reviewer 必须不同于 proposal producer。执行者可以是独立审查者。

```json
{
  "format": "kifu-player-duplicate-review-v1",
  "status": "independent-approved",
  "plan_sha256": "EXACT_PLAN_CANONICAL_SHA",
  "full_preimage_canonical_sha256": "EXACT_PREIMAGE_CANONICAL_SHA",
  "identity_review_canonical_sha256": "EXACT_IDENTITY_REVIEW_CANONICAL_SHA",
  "producer_id": "ORIGINAL_PROPOSAL_PRODUCER",
  "reviewer_id": "ACTUAL_INDEPENDENT_REVIEWER",
  "reviewer_model": "ACTUAL_MODEL_OR_HUMAN",
  "reviewed_at": "ACTUAL_TIMESTAMP_WITH_TIMEZONE",
  "conclusion": "ACTUAL_REVIEW_CONCLUSION"
}
```

`check` 与 `verify` 仅 SELECT，PostgreSQL 使用 REPEATABLE READ read-only 事务。
`dry-run` 真实修改数据库，核对后像后整体 rollback，再读原范围证明恢复。
PostgreSQL 序列在 rollback 后可能留下空洞；输出 batch/alias ID 属于回滚事务，不是持久 receipt。
`apply` 和专用 `undo` 复用 name_batch 锁，并额外锁审计表。
每次仅按这对 owner FK、原名、raw metadata、来源关联、名字/证据和碰撞范围重读，
不刷新全库 inventory。五个 declared FK 及全部 player_id 相关列清单也须一致。
删除前要求旧 owner 无名字、别名、证据、权威页面、此前 owner 审计历史与剩余引用。

保留者整行、原有槽位、SGF、原名、raw 状态/其他 metadata/parsed_data、来源、名字和证据均受完整前像保护。
李喆的五条 `review / legacy_unverified / evidence_id=NULL` 名字保持原状态，不算多语完成。
审签 manifest、完整前像、生成 alias 整行及受保护后像 hash 保存在已有 `KifuNameBatch`，
实际业务变化完整前后像保存在已有 `KifuNameChange`；没有新增表。
审计使用固定 registry 记录，undo 后随批次留存。

重复 apply 只核对 manifest、完整 ledger 和全部后像，返回 `already_applied`，零数据写入。
专用 undo 先核对全部后像和保护范围，再恢复退役 owner，反向恢复 FK/metadata，最后只删除 receipt 的新 alias。
任一后续编辑、新引用、碰撞、schema 变化或部分审计损坏均拒绝整个 undo。
不要调用通用 `name_batch.undo_batch` 恢复本批次；其原有 allowlist 和删除恢复行为未扩展。
已 undone 的同一计划不允许再次 apply；再次执行需要真实独立审查的新版本。

本文描述实现边界，不声称真实 TEST/PROD 已执行；生产执行记录应另行保存真实 receipt。
