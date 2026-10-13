# 重复 GN 有限选择：隔离库导入与撤销演练

2026-10-02 06:38–06:48 UTC，在 `home-ubuntu` 的**备份恢复隔离库** `kifu_name_rehearsal_20261002` 演练。连接经本机 SSH 隧道转发到该机 PostgreSQL 15；每一步都在执行前断言 `current_database() = 'kifu_name_rehearsal_20261002'`。现役测试库和正式库均未写入。核心导入代码 `event_selection.py` 字节 SHA-256 为 `b3aca1b9c699234797f04f0db21cd1c2af33cf776516e1203f1e75c9266a0806`；演练结束时 HEAD 为 `d5194becc3d307e32cf0d0f9e16e2c8587fbcc6e`。其他任务的未提交改动不纳入本记录。

## 固定输入与前像

- 独立[审核备忘录](kifu-name-duplicate-gn-finite-bundle-independent-review-2026-10-02.md)已提交为 `5f15dbd8`。私有审核文件 `gnugo-second-gn-reviewed.json` 的字节 SHA-256 为 `ee7e2540084de9086b1d5cd884ac49584d785df71d5c4dd176a23aa345cc97e0`，canonical 完整工件 SHA-256 为 **`0ca95eb71a1a25005ec46be34f9c0f13eaaca862adeddc9192ef2bcdbc2e18bd`**，成员集 SHA-256 为 `4c931aa4217c7813df7a1343f5c170e7a411422cfa622fa60a7a81f392aad5b3`。
- 隔离库起始 `kifu_albums = 173,025`，其中 `event = 'GNUGo3.8'` 精确 1,160 盘；两张选择表尚不存在。
- 将 1,160 个目标 album 的 `id/event/event_id/sgf_content/source/source_path/date_played/round_name/board_size` 按 ID 顺序写成规范 JSON 行并计算 SHA-256：`fa98c5391daa53a90e98bcce297eedc2b023ca1a3aa89ebae7fdeee88fefded8`。私有连接文件和摘要文件位于 `~/.local/share/kifu-name-audit/2026-10-02/duplicate-gn/rehearsal/`，目录 `0700`、连接文件 `0600`；未提交凭据或 SGF 正文。

## 执行与结果

本机 Python 通过 `sqlalchemy.create_engine` 读取私有克隆库 URL，使用当前仓库的 `katrain.web` 代码。实际调用顺序如下；`<bundle>` 代表上述私有 JSON，`<engine>` 仅指断言过库名的隔离库连接。连接 URL 未进入 Git 或命令行参数。

1. `Base.metadata.create_all(<engine>, tables=[KifuEventSelectionBatch.__table__, KifuAlbumEventSelection.__table__])`，随后 `verify_kifu_event_selection_schema(<engine>)` 通过；两表行数均为 0。
2. `validate_bundle(<bundle>)` 返回 `ready=true, member_count=1160`；`dry_run_bundle(<engine>, <bundle>)` 返回 `status=ready, ready=true`，完整工件及成员哈希均匹配上方固定值。
3. `apply_bundle(<engine>, <bundle>, expected_bundle_sha256='0ca95eb71a1a25005ec46be34f9c0f13eaaca862adeddc9192ef2bcdbc2e18bd')` 返回 `status=applied, batch_id=1, change_count=1160`。只读复核选择表精确 1,160 行，ID 集与固定成员集完全相同；每行 `selected_raw/sgf_sha256` 与对应成员相同，并通过 `audited_selection_images` 与 `selection_matches_audit`。原 album 前像摘要保持 `fa98c539…fefded8`。
4. 在 `KIFU_STRICT_NAMES=1` 的同一代码下抽查棋局 `5542`：`live_event_selections` 选中 `第5届韩国最强棋士战预选`；详情的原 `event` 仍为 `GNUGo3.8`，`sgf_content` 未变。该描述尚无中文已批准名称，因此 `display_event=赛事名称待核实`，`strict_slot_approvals(...)[5542][2] is None`。未执行耗时的 173,025 盘全量覆盖率报告；此处只验证单盘 API/覆盖槽位一致性。
5. `undo_batch(<engine>, 1)` 返回 `status=undone, reverted=1160`。最终只读复核：选择表 0 行；批次 1 状态 `undone`；album 总数 173,025、旧标记 1,160；全部目标 album 前像摘要仍为 `fa98c5391daa53a90e98bcce297eedc2b023ca1a3aa89ebae7fdeee88fefded8`。

本演练证明该精确工件可在备份副本中原子应用、核对并条件撤销；不批准把选择写入正式库，也不代表 559 个描述的赛事实体或十一语显示已获批准。隔离库保留新表和状态为 `undone` 的审计批次，**无活动选择行**。
