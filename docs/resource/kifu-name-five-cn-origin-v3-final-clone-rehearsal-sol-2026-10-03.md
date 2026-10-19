# 五名中文原名 v3：最终六语包隔离克隆演练 PASS

2026-10-03，独立演练 `/root/hoensha_path_encoding_code_review_sol`。使用[最终已签包](kifu-name-five-cn-origin-v3-final-batches-approved-sol-2026-10-03.md)，canonical SHA-256 `6a13b7e5ff51872d1cbb0310d0847c37b46c5f5f2c4b1f866c97563d88fa9ac0`；未修改候选、生产时间或前像绑定。

唯一数据库为 `127.0.0.1:55433/kifu_raw31_clone_20261003`，容器 `kifu-raw31-clone-20261003`，独占从停止态启动，结束后 `Running=false`。运行时固定干净提交 `7da9f719d5ebfbe3d05b10fa1e62cb02a6b6d688`，worktree `.worktrees/five-cn-origin-rehearsal-7da9f719`；相关模块哈希在演练前后相符，28 个转写集成／范围聚焦测试通过。

## 实际验证

Dry-run／apply 前分别于 `2026-10-03T02:08:24.314023+00:00`、`2026-10-03T02:08:31.556764+00:00` 进行新鲜 `REPEATABLE READ READ ONLY` 捕获。完整 inventory `f4907ffbe70d62b4b77f6d3bf5ba7ed789f2685f46eff7ffdfe080f2abc4bab1`、catalog `37ab4773652e10e38cdcc49a6fc13e3f72ec734aeb30be548d2597c0660f7f09`、空 approved-name snapshot、五个缺失 raw owner 及所有姓名前像均匹配。全部 **4,358** 原名／色方／完整上下文／NULL FK 与已签范围一致：唐韦星858、杨鼎新864、檀啸911、胡耀宇868、连笑857，共4,238棋谱。

| 检查 | 实际结果 |
| --- | --- |
| 正式 validator／dry-run | ready、write_ready 均 true；30 approved，errors／write_errors 空，missing0；dry-run零写入 |
| apply | batch5，65变更：5 raw owner、30六语姓名、30证据；album links0 |
| 六语显示／严格覆盖 | de/es/fr/ru/tr/ua，4,358×6＝**26,148** 精确单元全部通过 |
| 严格译名搜索 | 每个名称恰好返回该 raw 的已签棋谱集合；相同 Latin 输出复用同一精确查询结果，未扩大到来源人物身份 |
| 主五语 | **21,790** 个有限槽位显示／资格与基线相同，新增主五语姓名0 |
| 完全相同包重放 | already_applied，change_count0，SQL写入0，全部名称／审计行哈希不变 |
| 条件撤销 | undone，reverted65、skipped0；全部业务表及完整目标棋谱行哈希恢复 |

显示、搜索和覆盖使用正式 `strict_display_maps`／`resolve_strict_display`、`strict_matching_names`／`strict_raw_player_search_clause`、与 `coverage_report` 共用的 `strict_slot_approvals`。本次覆盖是有限黑／白槽位，不是全库覆盖。旧克隆没有这五名的已导入主五语姓名；此前来源／候选批准未因此变成数据库显示批准。

全部 **173,025** 棋谱的 SGF／人物与赛事 FK 哈希在演练前后相同：`18d4ff1a39aaeaa60280ace733c643c665fa2c3772d08c012195f35c8643817a`。SQL写入只涉及 raw 姓名与审计表，没有写棋谱、人物、赛事、alias或FK。撤销后 raw owner/name/evidence 均回到0；正常审计保留，batch4→5、change253→318，batch5为undone；保留关联审计的 registry2→3。

## 冻结证据与边界

受控目录 `~/.local/share/kifu-name-audit/2026-10-03/five-cn-origin-v3-final-clone-rehearsal-sol/`，目录0700、文件0400，包含输入／代码哈希、新鲜库存及四次前像、正式验证与导入结果、三阶段逐槽显示／搜索／覆盖、全库SGF/FK哈希、重放行哈希、SQL写记录及停止回执。manifest SHA-256 **`bc7f9227ccf5a619f8dc80973c353dcc164769cddec7ea2942375b87e652d0cc`**。

此 PASS 仅证明该最终包在已授权隔离克隆中的行为。克隆来源仍为旧 production-origin dump，当前生产时效未核实。生产／活动测试库连接和写入、人物归属／FK批准、应用代码修改及Git提交均0；本包不完成全库十一语发布门槛。
