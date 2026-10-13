# Hoensha：十一语最终候选独立审核与隔离 clone 演练 PASS

**PASS：595条archive来源范围、11个最终候选及隔离clone的真实导入/重放/十一语显示搜索覆盖/撤销恢复全部通过。** 审核者 `/root/hoensha_path_encoding_code_review_sol`，运行时标识GPT-6，具体子型号未独立暴露，与[候选生产者](kifu-name-hoensha-archive-v1-bound-pending-luna-2026-10-03.md)不同。真实最终签署 `2026-10-03T01:05:34.436492+00:00`，晚于分类、模板、clone捕获及前像绑定；原生产时间和preimage_binding保留。

重算生产者保护索引的32个文件hash，核对root分类及模板原件。完整595行与固定inventory精确相同：578条直接Hoensha路径与17条已独立核对的Honinbo_Shuho完整路径，均为CWI来源、原始`EV[Hoensha game]`、NULL event ID，无album links。两份留存正文、原签路径及副本字节相同：CWI SHA-256 `abeb516b8b69c606d1bf246191416aa6ef4a1db14b5b171aac505cafd22c417e`；日本棋院 `813b6092377b2808f5dc91574fee2ea2c38673f84351ca72dd3c83fd9b74289f`，按严格Shift_JIS解码后摘录精确存在。

校验器要求每个候选与其template_review使用同一审核者；本次按root明确授权，对[既有语言审核](kifu-name-generic-three-event-11lang-independent-review-sol-2026-10-03.md)及固定`archive-description-v1`十一字符串/hash独立复核，在新包中以本人真实身份和时间重新签署模板和候选。root原审批工件完整保留作为前置来源，没有移植其签名。capture内容hash、11个NULL前像及逐条source-candidate hash全部重算；category/owner/member/scope不变。正式validator实际 **ready=true、write_ready=true、approved=11、pending/rejected/missing=0、errors/write_errors=[]**。

演练仅使用 `127.0.0.1:55433/kifu_raw31_clone_20261003`，固定干净committed代码 `bc2591482acb47ba06aee8c7131ad1ef489a594e`及7个模块文件hash。Dry-run和apply前分别于 `2026-10-03T01:09:24.807567+00:00`、`2026-10-03T01:09:32.704229+00:00` 重新进行REPEATABLE READ READ ONLY捕获；inventory/catalog、精确owner/name前像及approved-name snapshot均匹配签署包，所需clone schema经真实读写路径验证。未使用生产或活动测试库。

| 演练步骤 | 实际结果 |
| --- | --- |
| dry-run | ready/write_ready=true；精确595个事件；23条预计undo记录；0写入 |
| apply | batch4；1个raw_event owner、11个name、11个evidence，共23条change |
| 十一语展示、搜索、覆盖 | 595×11 = 6545个批准显示单元；十一语搜索扩展各自精确等于595事件范围 |
| 精确重放 | already_applied；change_count=0；0写入；姓名及审计行hash一致 |
| undo/恢复 | reverted=23；skipped=0；业务、展示、搜索、inventory/catalog/snapshot恢复；173025条SGF及人物/event FK hash保持一致 |

上述展示和搜索使用正式strict display/search函数；覆盖逐槽使用与`coverage_report`共用的`strict_slot_approvals`。这是595条有限范围验收，没有运行或声称全catalog coverage完成。撤销后raw owner/name/evidence均回到0；正常审计历史保留，batch从3增至4、change从230增至253，batch4为undone，source registry仍2条。写语句只涉及raw姓名及审核表，没有写事件/人物实体、album或FK。clone已停止，Running=false。

受控最终审核包：`~/.local/share/kifu-name-audit/2026-10-03/hoensha-archive-description-v1-final-independent-review-sol/`；演练包：`~/.local/share/kifu-name-audit/2026-10-03/hoensha-archive-description-v1-final-clone-rehearsal-sol/`。目录0700、文件0400；包含真实候选/模板签署、原root审批、逐条前后hash、只读前像、正式validator和导入结果、三阶段逐槽显示/搜索/覆盖、行hash、SQL写记录及停止回执。

| 固定对象 | SHA-256 |
| --- | --- |
| 原审批绑定pending bundle文件字节 | `3287d0182eaa8e45613d08c466dc6188d75c8c5050a6152306f556f1f090dfea` |
| 不变595条scope canonical | `d10c54be5c4e0bfe13f1f6fa9480549c0f29c2fa55ed36e222f45b114d820b44` |
| 最终批准bundle canonical | `8e15b9b3921cd7042457854fa30c36fce5af1811be958c809446c5ad08c1b73b` |
| 最终bundle文件字节 | `407b478a31ece768b5ac8cf3db680448886366efa5bf60e3795d1d515d76dd44` |
| 最终审核manifest文件字节 | `e1b491f58306798025230dc1195de48d8afe4fbd480e20577b4eb3492c519364` |
| 演练manifest文件字节 | `f3f8c88c825b177df89c388225431cc6779f391999e51f84fb7fa043f501ef80` |

该PASS限定历史来源说明和已授权隔离clone；没有正式赛事身份、人物归属/FK或当前生产时效批准。Clone源自旧production-origin dump；正式目标fresh前像与schema核实及生产写入批准仍待完成。本轮生产/活动测试库访问与写入、应用代码修改、生产者工件修改及Git提交均0。
