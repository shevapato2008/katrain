# 五位中国棋手十一语：最新 TEST v2 克隆迁移与 pending 重绑

2026-10-03。Producer：`/root/five_player_test_stage_preflight_sol`。本记录仅证明最新 TEST 快照的隔离恢复、真实 schema 迁移及 pending 重绑核对，**不构成独立名称审批或 active TEST 写入批准**。

## 最新快照与真实迁移

`07:42:37–07:45:51 UTC`，从 `home-ubuntu` 的 `katrain-postgres/katrain_db` 只读导出 19 张棋谱业务／审计表，包含 `kifu_albums`，不含账号、教程、分析表。使用 `pg_dump --serializable-deferrable`，并设置 `PGOPTIONS=-c default_transaction_read_only=on`。源 Web 仍为 `2e4fcef5`、`KIFU_STRICT_NAMES=0`。首次未包含 albums 的 catalog-only 导出仅保留历史记录，未用于恢复；权威快照为下表的 `latest-test-kifu-catalog.dump`，不能用于覆盖整库。

恢复至新独占本地 container／volume `kifu-five-test-rebind-sol-v2-20261003`，实际端点 `postgresql+psycopg2://postgres@127.0.0.1:55445/katrain_db`。`07:48:44 UTC` 实际执行受目标断言和数据写语句拦截保护的 `migrate_catalog --validate`：只新增 `kifu_album_event_selections`、`kifu_event_selection_batches`，无删表，外键校验通过，迁移中的 `INSERT/UPDATE/DELETE/TRUNCATE` 语句为 0。现存表字段与所需名称索引此前已齐全。

源 TEST 只读核对、恢复克隆、迁移后克隆的 **19 表完整行哈希全部一致**。全部 **173,025 albums** 的 SGF/FK 哈希一致。五个精确 occurrence ID 集和 **4,358 完整黑白槽位 context／4,238 albums** 均与已审来源包一致；五 raw owner 和全部 55 名字前像为空。克隆已停止，`Running=false`。

## 原始哈希与受控产物

受控目录：`/Users/fan/.local/share/kifu-name-audit/2026-10-03/china-professional-roster/five-cn-origin-main11-test-rebind-pending-sol-v2/`。目录 `0700`，35 个 manifest 所列文件及 manifest 冻结为 `0400`；完整命令、时间、表哈希、DDL、代码绑定和停止回执见包内记录。

| 对象 | SHA-256 |
| --- | --- |
| `manifest.pending.json` 文件字节 | `bc0e99c9bc31df9efaac195efe82a40c01648544b012ceb365554cc22cfa9fa6` |
| `latest-test-kifu-catalog.dump` 文件字节，79,264,657 bytes | `c6391f0995ed83cb63db990da7860d85271288a8fb226b03850c0e6eef605350` |
| 全部 173,025 albums 的 SGF/FK | `e6a3e7e4f9988fcf87805d33d81c748aa2d8104d984f2ebb4a99f3f9066f8bbf` |
| 新 format-4 inventory | `d5f376a980d12ec82ca18940b199295d6ce0f14b052261e9ce95afe58eb8af54` |
| base album/source snapshot | `c765d95689b98c6944cdab88b5a37cfd9a6fb2c2419807a7d10c64f8f455a87b` |
| catalog snapshot | `3d4625b37b57c49f8fbf594a15f2bdb51525067df1cf2e7a5612dc5622f8fa79` |
| `preimage-capture.target.readonly.json` 文件字节 | `e9b1b80386e9ecaf06f3e9ee228911a09e6a4be412cf0a2860383e8946563fb4` |
| pending bundle canonical | `f7947f6635960598e35422400153aacb82b5d2fbf981d9ce5d6bb1c0143c3cce` |
| 复用来源的独立审批 manifest 文件字节 | `819682d6faa96c67176960dfb68a9ea11786dc49122a208db83e5f33f8a66940` |

## 重绑结果与独立审批待办

已生成实际 clone URL 的新 inventory、只读前像 capture、55 个真实时间 preimage binding，以及五 scope、五 anchor、六 batch、55 candidate 的 **pending** proposals。55 显示值、25 条来源 `source_checks`、五精确槽位数组、六已审 language rule、五 category 决策和 registry 保留；所有更改依赖对象的旧 reviewer 字段移除，未把旧 clone 签名当作新目标批准。真实 `validate_bundle` 和 readonly `dry_run_bundle` 已调用并拒绝 pending scope／anchor／batch／candidate 闸门；重绑阶段只有 389 SELECT、3 SHOW，SQL writes 0，未调用 apply。

后续必须按真实依赖顺序闭环：独立审新 scope → producer 重绑完整 signed scope hash 并重新生产 anchor → 独立审 anchor → producer 重绑 research、batch、candidate；六 batch 生产时间晚于新 anchor review，55 前像真实重新捕获／绑定 → 独立审主五候选和六完整 batch → 机械绑定 30 次六候选 → 最终 validate/dry-run。只有该实际目标的最终签包 PASS 后才能进行 clone apply/replay/conditional undo；本轮未完成这些写入演练。

包内 `README.md`、`fingerprint.py`、`migrate-clone.py`、`prepare-rebind.py` 提供复现及后续只读 capture 入口。将来若 root 决定 active TEST 迁移与写入，必须使用其**实际 URL**、新 capture 和新的独立审批链；不能直接改 inventory URL，不能复用本次 clone endpoint 的签名。

**本轮没有 active TEST／PROD 数据库写入、迁移、服务重启或名称 apply；应用代码未修改。**
