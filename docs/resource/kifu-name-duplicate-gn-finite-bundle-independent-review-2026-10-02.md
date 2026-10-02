# 重复 GN 有限选择：独立审核（2026-10-02）

**结论：批准精确的 1,160 个源属性选择，零排除、零待定。** 审核者 `/root/duplicate_gn_bundle_astra_review`，实际模型 `gpt-6-astra`；生产者是另一代理 `/root/duplicate_gn_finite_bundle`（`GPT-6 (Codex)`）。审核时间 `2026-10-02T06:34:56Z`，晚于生产时间 `06:25:38Z` 和范围冻结时间 `06:26:00Z`。本记录是完整工件哈希的独立外部依据，不能仅以工件内部自报的哈希替代。

## 固定工件

私有目录：`~/.local/share/kifu-name-audit/2026-10-02/duplicate-gn/`，模式 `0700`。

| 项目 | SHA-256 |
| --- | --- |
| 受控清单 `gnugo-second-gn-clone.jsonl` | `cc924c0ebf480bb80c04fcdfe1e93d4d9de28475aab52ff9ce8a0fc5fae55eb2` |
| 未修改的生产者草稿 `gnugo-second-gn-producer-draft.json` | `7b1d3eeeb637381d6ccc215fcfd3a0de75383b16825d0335cb5e94fca01c7527` |
| 精确成员集（canonical） | `4c931aa4217c7813df7a1343f5c170e7a411422cfa622fa60a7a81f392aad5b3` |
| **完整审核工件（canonical；apply 的可信 `--approved-bundle-sha256`）** | **`0ca95eb71a1a25005ec46be34f9c0f13eaaca862adeddc9192ef2bcdbc2e18bd`** |
| 审核文件 `gnugo-second-gn-reviewed.json` 的字节哈希 | `ee7e2540084de9086b1d5cd884ac49584d785df71d5c4dd176a23aa345cc97e0` |
| `review_signature`（审核对象的 canonical 哈希） | `a68d3d5f3ec763b39869b06af914352691cf65385d5102ed888f19b113327676` |

审核文件为独立新文件，536,056 字节、模式 `0600`；通过替换原草稿唯一的 `"review":null` 写入审核对象，并反向还原逐字节核对，证明其他生产者字节全部保留。原草稿及受控清单均未修改。canonical 使用 UTF-8 JSON，`sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False`，所以完整 canonical 哈希与带末尾换行的文件字节哈希不同。

## 独立核验

`06:33:05–06:33:13 UTC`，仅查询 `home-ubuntu` 的隔离备份库 `kifu_name_rehearsal_20261002`，连接默认只读，事务明确为 `REPEATABLE READ READ ONLY`，结束时回滚。库有 173,025 盘，全部 `event = GNUGo3.8` 的 1,160 个 ID 与草稿和受控清单完全相同，无遗漏、重复或误纳。独立核对该机备份文件 SHA-256 为 `ea8c1ae9e6ddb8038ac8b0ce91a012031c4b10bb3d39b6a4192316d2e0fbd990`，与[备份迁移记录](kifu-name-migration-record-2026-10-02.md)一致。

每盘先对完整 `sgf_content` 的 UTF-8 SHA-256 同时核对两份固定输入，通过后才解析。1,160 盘的旧 `event/event_id/source/source_path/date_played/round_name/board_size` 前像全部一致；旧事件均为 `GNUGo3.8`，关联均为 NULL。独立逐条件核验并与 `selected_second_gn` 交叉比较：`19x19` 路径、19×19 棋盘、唯一且精确的 `SO`、根节点无 `EV`、恰好两个有序 `GN`、首值精确为程序标记、次值非空且逐字等于固定选择值、次值非程序或 SGF 残片、唯一 `GC`。全部 1,160 个 `GC` 均以精确的 `GN[1] + " | "` 开头；没有依赖清单的布尔标记。

559 个不同次值全部仍为 `unclassified_pending` 描述；本次未批准赛事实体、译名或十一语言显示。核验时选择表和批次表均不存在，未迁移、应用、撤销或执行任何数据库写入。

私有复核脚本 `gnugo-second-gn-independent-audit.py` 的字节 SHA-256：`fcda56b9d58635e2d5213544ec3c1d7df8af3930fc7de493aacf72e15e096941`；私有结果 `gnugo-second-gn-independent-review-audit.json`：`f582ed5ab164e4256c7d33d3b4243779a49affb256ed5e95a843980861838fbc`。结果含实际只读事务状态、计数、解析依赖文件哈希和失败列表（空），不含 SGF 正文。复核时 HEAD 为 `d9c94dae2f8049a106703f10a33f32177066b0a9`，`event_selection.py` 字节 SHA-256 为 `b3aca1b9c699234797f04f0db21cd1c2af33cf776516e1203f1e75c9266a0806`。

`uv run python scripts/kifu_event_selection.py validate --bundle <私有审核文件>` 退出 0：`ready=true, member_count=1160`，返回上述完整工件和成员哈希。[Task 6](../superpowers/plans/2026-10-02-kifu-legacy-duplicate-gn-selection.md) 的隔离库迁移及 apply/undo 演练由后续记录负责；本批准不等于已应用或允许激活正式严格显示。
