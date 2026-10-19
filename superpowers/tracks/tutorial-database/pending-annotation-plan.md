# 带未决注记的静态棋图候选交付计划

> **For agentic workers:** Use superpowers:subagent-driven-development。仅在既有 APP 工作树修改导入路径，不改运行中的识别器或已审核的归属恢复代码。

**Goal:** 全书来源清点完成后，将《定式要领》第182页两张静态图连同未决墨迹说明交付到 TEST 校准入口，保留原始不完整状态和所有人工成果。

**Architecture:** 在现有整书 loader/CLI 加入显式、哈希绑定的 pending-annotation manifest；全部来源与 TEST 身份校验继续执行。仅匹配清单的两图 candidate-only，使用现有候选展示及 SGF 导出，不自动采用为当前棋图。

**已审核依据:** 独立 GPT-6-Astra/max 的本机 `joseki-p182-source-decision.md` 与 `joseki-p182-delivery-decision.md`。原页181–183已实看，不能可靠判定墨迹归属；静态44/49子结构均通过 Strict。该计划落实现有审核结论，无新增 UI、表或服务。

## 实施与验证

- [ ] 在现有 catalog importer 提取静态 payload 校验小函数；默认 normalize/loader 仍拒绝 incomplete。
- [ ] CLI 增加显式 manifest 参数。清单绑定 catalog/dataset、最终结果、index、logical ledger、来源清单和原页、两图完整记录/payload/疑点及原模型证据哈希；写库前逐项验证。
- [ ] 继续要求完整唯一1…290页、全部检测完成、每张独立图和引用映射完整、所有资产有效；除清单两图外任何失败或未决都拒绝。p54/v2必须先按已通过方案完整应用；本期不改它们。
- [ ] 清单两图原 `complete=false`、疑点及 `logical_coverage_closed=false` 不变；只保存 immutable candidate 和审计，跳过 current/history/adopted 写入。其他图沿用原路径及人工成果保护。
- [ ] dry-run/apply/rerun 明确输出 candidate_pending 与 applied=false；同数据集与识别ID不允许变内容。私有交付层分别记录来源清点、独立图映射、有效候选、未决注记数量，不把全图数写为机器全部完成。
- [ ] 复用现有测试夹具验证两独立候选、不写 current/history/review、原 raw 不变及复跑0新增；无清单、错哈希、第三未决图、payload问题、缺页/检测失败/漏引用仍拒绝。只运行相关导入与保护检查。
- [ ] 由独立 GPT-6-Astra/max 做规格与代码审查，真实阻塞修到通过。

## 应用门槛及交付

- 清单只在自然290页结束、书锁释放、已通过的两段归属修复发布核验后生成；现在不制作会随续跑失效的最终清单。
- root 串行核对 TEST 身份后 dry-run、apply、exact rerun。后台实看182页的两候选、原图、44/49子、原疑点、筛选与编辑取消，并核对两份独立 SGF/source index。
- 进度分别标记“全书候选可校准”与“注记归属未关闭”；不自动人工审核、不生成媒体、不写生产。
