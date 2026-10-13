# 七个 raw-player：最终签署包隔离 clone 演练 PASS

**PASS：77条最终候选的真实 dry-run、apply、重放、十一语有限范围展示/搜索/覆盖及undo恢复全部通过。** 使用[最终独立签署包](kifu-name-raw-player-next7-phase4-final-independent-review-sol-2026-10-03.md)的原始不可变内容；执行者 `/root/hoensha_path_encoding_code_review_sol`，演练时间 `2026-10-03T00:46:53.100605+00:00` 至 `2026-10-03T00:47:52.449727+00:00`。

唯一数据库目标为 `127.0.0.1:55433/kifu_raw31_clone_20261003`，容器 `kifu-raw31-clone-20261003`。未连接生产或活动测试数据库。代码固定干净 committed worktree `.worktrees/raw7-phase3-bc259148` / `bc2591482acb47ba06aee8c7131ad1ef489a594e`；9个相关模块文件字节hash逐项冻结，没有使用共享未提交改动、修改应用代码或执行schema迁移。

在 dry-run/apply之前分别进行新鲜 `REPEATABLE READ READ ONLY` 捕获，时间为 `2026-10-03T00:46:59.436520+00:00` 和 `2026-10-03T00:47:06.959762+00:00`。完整inventory hash `f4907ffbe70d62b4b77f6d3bf5ba7ed789f2685f46eff7ffdfe080f2abc4bab1`、catalog hash `37ab4773652e10e38cdcc49a6fc13e3f72ec734aeb30be548d2597c0660f7f09`、七个精确raw owner及77条姓名的NULL前像、空approved-name snapshot均匹配签署包。所需clone schema已由真实SELECT和完整导入/撤销路径验证；历史clone的兼容性表不认证当前生产schema。没有改写原候选生产时间或历史preimage_binding。

| 检查 | 实际结果 |
| --- | --- |
| dry-run | ready/write_ready=true；预计161条undo记录；0写入 |
| apply | batch3；7个raw owner、77个name、77个evidence，共161条change |
| 十一语严格展示及覆盖 | 1568 PASS槽×11语 = 17248个批准显示单元；7 HOLD槽×11语 = 77个单元继续缺失 |
| 十一语姓名搜索 | 七人×十一语的77次搜索扩展全部精确等于各自有限PASS album集合，HOLD不泄漏 |
| 精确重放 | already_applied；change_count=0；0写入；完整姓名及审计行hash不变 |
| undo | reverted=161；skipped=0；already_reverted=0；batch状态undone |
| 恢复 | 77条姓名与77条evidence、7个owner全部撤销；展示/搜索回到基线；inventory/catalog/snapshot及全库173025条SGF/FK hash恢复或保持一致 |

有限范围有1575个全局槽、1568 PASS和7 HOLD，对应1553个不同album。导入器`affected_albums`报告完整raw出现范围，包含HOLD所在album；真正的姓名展示和搜索批准受有限slot scope限制。展示使用正式 `strict_display_maps` / `resolve_strict_display`，搜索使用 `strict_matching_names` / `strict_raw_player_search_clause`，覆盖使用正式 `strict_slot_approvals`（与`coverage_report`共用）；每个目标slot和十一语均逐项验证。没有运行全catalog coverage报告，也不声称全catalog已完成。

撤销后业务状态恢复，保留正常审计历史：batch由2增至3、change由69增至230，新增batch3为undone；source registry仍为2条。数据库写语句仅出现在apply和undo阶段，且仅涉及raw姓名与审核表；没有写album、人物实体或FK。容器已停止，stop exit0，Running=false。

受控证据：`~/.local/share/kifu-name-audit/2026-10-03/raw-player-next7-final-clone-rehearsal-sol/`（目录0700、文件0400），含四次只读前像、真实dry-run/apply/replay/undo结果、三阶段逐slot展示和搜索/覆盖结果、前后行hash、SQL写入记录、停止回执和代码hash。

| 固定对象 | SHA-256 |
| --- | --- |
| 最终不可变bundle canonical | `6b6b3c1a071acfca3a9107cf8c9709a86c464776166dd17d8cbd6e3250567b31` |
| 最终bundle文件字节 | `c743be8ebfca429cea15ded04acbfb6140b2c6dad2e0ee5c0d05e69c733741e9` |
| 最终签署packet manifest文件字节 | `1ce62240ed8c1a1fd117cada7e92f55385d272f4b56674ca8ab6deafaba19377` |
| 演练packet manifest文件字节 | `95486d843bf95bb72ad25bf6aa47da1363475c8980ae8e5481a7a730ba8951b5` |

该结果证明已授权隔离clone上的真实协议及有限范围行为。Clone仍源自旧production-origin dump；当前生产时效stale/unknown，实际生产fresh前像与schema核实及正式写入批准尚未完成。本轮生产写入、活动测试库写入、人物归属/FK增量、应用代码修改和Git提交均0。
