# 重复 GN 有限选择：生产者证据（2026-10-02）

2026-10-02 06:25–06:26 UTC，生产者 `/root/duplicate_gn_finite_bundle`（GPT-6 / Codex）按[实施计划](../superpowers/plans/2026-10-02-kifu-legacy-duplicate-gn-selection.md)的 Task 6，在代码提交 `1cfac74b917d26262461b7361acbcb6ea13779b2` 下生成待独立复核草稿。数据源是 `home-ubuntu` 上从正式备份恢复的隔离 PostgreSQL 库 `kifu_name_rehearsal_20261002`，库中有 173,025 盘；其备份来源见[迁移记录](kifu-name-migration-record-2026-10-02.md)。本次没有访问或写入现役测试库、正式库，也没有向隔离库写入。

## 固定输入与复现方法

- 受控清单：`~/.local/share/kifu-name-audit/2026-10-02/duplicate-gn/gnugo-second-gn-clone.jsonl`；404,657 字节，SHA-256 `cc924c0ebf480bb80c04fcdfe1e93d4d9de28475aab52ff9ce8a0fc5fae55eb2`，含 1,160 个互异 `id`。
- 以清单 ID 为唯一范围，在 `REPEATABLE READ READ ONLY` 事务中按 `id` 读取隔离库 `kifu_albums` 的 `event, event_id, source, source_path, date_played, round_name, board_size, sgf_content`，然后回滚只读事务。共取得 1,160 行。先用 UTF-8 字节计算每行 `sgf_content` 的 SHA-256，与清单逐一比对；**哈希通过后**才调用 `SGF.parse_sgf`。
- 对解析后的根节点运行共享的 `selected_second_gn(root, classify_source_path(source_path))`，并逐字比对受控清单的两个 `GN` 值和选择出的 `GN[1]`。该共享规则核对缺失 `EV`、精确 `SO`、两个有序 `GN`、第二值非程序/残片以及唯一 `GC` 与第二值的一致关系。随后核对清单中的旧 `event/event_id`、路径、日期、轮次，以及库中的 `source` 和 `board_size`。
- 将合格成员按 `album_id` 升序序列化；成员哈希使用 `canonical_sha256(members)`，即 UTF-8 JSON 的 `sort_keys=True, separators=(",", ":"), ensure_ascii=False` 后取 SHA-256。生产者草稿的 `review` 为 `null`，未构造审核者身份、结论或签名。

## 产物与结果

| 项目 | 结果 |
| --- | --- |
| 隔离库取得 / 合格 / 排除 | 1,160 / 1,160 / 0 |
| 不同的 `GN[1]` 原文 | 559；是待分类描述，不代表 559 个赛事实体 |
| 成员 SHA-256 | `4c931aa4217c7813df7a1343f5c170e7a411422cfa622fa60a7a81f392aad5b3` |
| 待审草稿 | `~/.local/share/kifu-name-audit/2026-10-02/duplicate-gn/gnugo-second-gn-producer-draft.json`，533,755 字节，文件模式 `0600` |
| 草稿文件 SHA-256 | `7b1d3eeeb637381d6ccc215fcfd3a0de75383b16825d0335cb5e94fca01c7527` |
| 生产 / 冻结时间 | `2026-10-02T06:25:38Z` / `2026-10-02T06:26:00Z` |

每个成员固定 `album_id`、旧 `event/event_id/source/source_path/date_played/round_name/board_size`、完整 SGF SHA-256、属性名 `GN`、索引 `1`、原样选择值和规则版本 `19x19-gnugo-second-gn-v1`。草稿不含 SGF 正文，目录为 `0700`。所有 1,160 个旧事件仍为 `GNUGo3.8`，旧 `event_id` 均为 `NULL`，本次没有覆盖这些字段。

**审核状态：待审。** 独立审核者需复核上述精确成员哈希、证据范围与结论，在冻结时间之后填入 `review`，才会形成可供 CLI `validate` / `dry-run` 的完整工件及其批次哈希。此次查询时隔离库尚无 `kifu_album_event_selections` 和 `kifu_event_selection_batches` 表；未运行 `apply` 或 `undo`。后续迁移及同代码版本的隔离库演练由 Task 6 的下一阶段记录，不能把本草稿视为已批准写入。
