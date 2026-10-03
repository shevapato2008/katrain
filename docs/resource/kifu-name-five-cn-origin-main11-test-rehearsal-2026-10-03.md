# 五位棋手十一语言：测试库隔离副本演练

日期：2026-10-03。此记录只覆盖从当日运行中的 TEST 数据库只读备份恢复出的**隔离副本**；运行中的 TEST 和正式库没有迁移、导入、重启或写入。

从 TEST 备份恢复 173,025 盘棋后，仅在隔离副本新增两张缺失的赛事选择表。重新采集的清单与目录分别绑定该副本，4,358 个黑白棋手原始槽位、4,238 盘关联棋局及 55 个显示值与此前审核范围逐项一致。五个原始范围、五个身份锚、25 个主语言候选、六个次语言完整批次、30 个次语言候选按依赖顺序独立审核并重新签署。最终 TEST 副本专用 bundle canonical SHA-256 为 `6aeff0caef8bd2c23f2edaebf12210d7f0cee2d5d9a316b8600630e4e78e4cfe`；55 条候选的 `ready/write_ready` 均为 true。

实际隔离演练：dry-run 预计 115 条变更；apply 提交 115 条（5 个 raw owner、55 个译名、55 个证据）；47,938 个逐语显示位置核对通过；重复导入为 0 写入；conditional undo 撤销全部 115 条，skipped 0。173,025 盘棋的 SGF、外键和业务表恢复到演练前校验值 `e6a3e7e4f9988fcf87805d33d81c748aa2d8104d984f2ebb4a99f3f9066f8bbf`。批次、变更和来源登记的正常审计记录仍保留；隔离容器已停止。

第一次入口预检因演练脚本的事务状态问题在写入前停止；随后隔离容器 2 GB 人为内存上限触发 OOM，发生在首次 apply **已提交后**的读回阶段。保留失败回执，将该容器上限调整为 8 GB 后，从已提交批次继续核对，没有第二次 apply，最终完成重放和撤销。完整受控回执在 `~/.local/share/kifu-name-audit/2026-10-03/china-professional-roster/five-cn-origin-main11-test-final-mechanical-rehearsal-producer/`；handoff manifest SHA-256 `b1c64dfa8471e394a9238e00d2096665cc65a5acbef4604c52718384d9ddd16f`，rehearsal result SHA-256 `8b168262d2aa6674186f54e50548139367454be7eebdec1bcb16d1aeefc8fa74`。

该 bundle 的目标数据库标识为隔离副本。若以后导入运行中的 TEST，必须先按其真实数据库标识和最新只读快照重新绑定前像、在新绑定后独立签署完整批次，再做目标库 dry-run；不能把本次副本的 bundle 直接用于运行中的 TEST。
