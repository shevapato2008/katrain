# 李昌镐 ID 143 五槽位：隔离库重检与停止记录

2026-10-02，在 `home-ubuntu` 的备份恢复隔离库 `kifu_name_rehearsal_20261002` **只读重检**[已签署工件](kifu-name-lee-143-five-link-v2-independent-review-2026-10-02.md)。本轮未执行 `apply`、`undo` 或迁移；正式库和现役测试库均未访问写入。此前同一库的完整导入、API 核对与撤销见[原演练记录](kifu-name-lee-143-v2-clone-rehearsal-2026-10-02.md)。

- 私有 `bundle-reviewed.json` 文件 SHA-256：`6d7b9f5fdbe16cea483f071cf58f61b4a53067cd1af548411f7cb0749e4de99a`；canonical bundle SHA-256：`cb0bb519a39583120b8872322ead962cd52faeed8975527c0d6a864ffb583c39`。固定 v2 inventory 内部 SHA-256：`66b8946d908468c5f9c8f0dc8ef4b4ceddb76d840ef42f5cff5122fc5744b3a3`。
- 执行 `python scripts/kifu_name_candidates.py validate --registry docs/resource/kifu-name-source-registry-2026-10-02.3.json --inventory <私有 inventory-prod-v2-20261002.json.gz> --bundle <私有 bundle-reviewed.json> --evidence <私有 research.jsonl>`：退出 0；`ready=true`、`write_ready=true`、11 approved、0 missing/pending/rejected、`errors=[]`、`write_errors=[]`。
- 经 SSH 隧道使用本仓库 `name_batch.dry_run_bundle`，仅在内存中将 inventory 的 `database_identifier` 改为本次克隆库连接，内部 snapshot SHA 不变。执行前断言 `current_database() = 'kifu_name_rehearsal_20261002'`，库有 173,025 盘。dry-run 重新核对全库快照、catalog、候选前像及五盘 SGF：`ready=true`、`write_ready=true`、11 candidates、`estimated_undo_rows=27`、`affected_albums=[40212,64489,83228,97368,98003]`，无错误。
- 只读核对当前五个目标槽位仍为原 `NULL`，其 SGF SHA-256 均匹配签署 link 前像；棋手 143 当前仅有原五语 `cn,en,jp,ko,tw`。事件选择表为 0 行。
- **停止原因：** 克隆库 `kifu_name_batches` 中同一 canonical bundle 哈希已有批次 **3**，状态 **`undone`**。`name_batch.apply_bundle` 明确拒绝重放已撤销的相同哈希。尽管 validate/dry-run 通过，本轮不能安全再次 apply；未尝试修改批次历史或强制绕过闸门。因本轮未应用，未重做 API/覆盖率抽查；原演练已记录此前应用时的验证与撤销。

临时连接文件已删除，SSH 隧道已关闭。此记录只证明当前克隆快照仍与该签署工件匹配，以及重放闸门正确阻止重复应用；不构成正式库写入或全库姓名覆盖批准。
