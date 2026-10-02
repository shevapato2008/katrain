# classification-v2 22 格修订包：独立最终签署与隔离演练 PASS

审核者 `/root/generic_v2_22_source_review_sol`，运行时标识 GPT-6，任务名不认证具体子型号。独立复核 [修订 pending 绑定包](kifu-name-generic-classification-v2-22-final-pending-v2-binder-sol-2026-10-03.md)，复算其全部 96 个冻结文件的字节 hash，核对原 producer、单独 binder、capture/source-candidate hash 和绑定时序。两个 create 现在仅含 `raw_value/category`；旧最终签名未移植，新候选签署时间为 `2026-10-02T23:18:09.392414+00:00`，晚于最新绑定。

**22/22 最终候选重新独立签署，validator 与隔离 clone dry-run/apply/replay/undo 全部 PASS。** 范围严格为段位赛901盘、个人赛638盘；原十一语精确文字、generic 分类、classification-v2 规则版及历史类别/模板签署均保留。原 importer create 字段阻塞已通过修改包解除，未扩张代码 allowlist；[旧 HOLD 记录](kifu-name-generic-classification-v2-22-final-review-importer-hold-sol-2026-10-03.md) 保留。

执行代码固定在 `.worktrees/generic-v2-22-binder-b0cdbdcf`，HEAD `b0cdbdcfacda23391cf39273c42e067f3fc11b79`，避免共享工作区并行 Hoensha 改动。仅连接 `127.0.0.1:55433/kifu_raw31_clone_20261003`；写入前以 `REPEATABLE READ READ ONLY` 再查 inventory/catalog 与两个精确 raw_event owner，确认 hash 与 binder 一致、两个 owner 仍不存在、全部22名称前像 NULL。

| 验收 | 实际结果 |
|---|---|
| validator / importer dry-run | ready / write_ready 均 true；dry-run 前后数据库状态一致 |
| apply | clone batch 2，46项审计变更；新增2个raw_event值、22个v2 generic名称及22份证据 |
| replay | already_applied，新增变更0，状态不变 |
| 十一语显示 | 1,539盘逐盘精确匹配批准字面值 |
| 十一语搜索 | 每个原文/语言的搜索结果ID集合精确等于901或638范围 |
| 批准覆盖 | 使用生产 strict_slot_approvals 核验全部16,929个事件语言槽，均为generic |
| undo | reverted46 / skipped0；业务catalog hash、目标SGF/event_id及相关表计数恢复 |
| 撤销后的显示审批与搜索 | 事件审批归零；批准译名搜索匹配归零 |
| 身份与原始棋谱 | event/alias计数不变，目标event_id仍NULL，SGF及原始event内容hash不变 |

批准覆盖验收调用真实 `strict_display_maps/resolve_strict_display`、`strict_matching_names/strict_raw_event_search_clause`、`strict_slot_approvals`，覆盖本批全部盘与十一语；没有以候选数乘冻结盘数冒充实际显示结果，也未宣称完整库覆盖。clone 业务状态已撤销恢复，保留本次 batch/change 审计历史，最后停止收据确认 `Running=false`。未进行 reapply，未修改应用代码、未提交，生产与现役测试数据库写入均0。

| 工件 | SHA-256 |
|---|---|
| 新 pending 包规范hash | `4fa682951e001cdc16e37024e04140df9dc21f1a29e0337801e275d3e038f98f` |
| 新签署包规范hash | `a2d215cb95c0b75b00ea3f8f18826bb534ce43f13b98a6493478260a317045a8` |
| 新签署包字节hash | `b69ae3533311693849c4c1b28d248fc61a1dddb31c310720f5651201fe55c212` |
| 演练manifest字节hash | `abba62a219c6eb354d22ea61e5b65f004438b59c804554d29802b49017557dfc` |

冻结目录：`~/.local/share/kifu-name-audit/2026-10-03/generic-classification-v2-22-final-v2-review-rehearsal-sol/`，0700/0400。manifest 固定19个工件，包括新签署包、签署结果、固定代码hash、独立前像核验、dry-run/apply/replay/undo、前后状态、全部十一语运行时结果和停止收据；冻结后全部hash复算通过。

此结论是 **已审候选与克隆演练 PASS**。线上新增覆盖仍为0，不能将撤销后的clone状态或旧生产dump视为正式入库。正式发布需实际目标fresh inventory/catalog及owner/name前像，并按既有导入门槛执行；Hoensha十一格尚属独立阶段二，本次不报告三组33格完成。
