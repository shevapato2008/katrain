# NULL event_id 覆盖分析与下一批（2026-10-05）

本轮仅分析既有冻结资料及 PROD 的五条 raw owner 定向只读查询；没有数据库写入、全库重抓或代码修改。

## 结论与口径

`/tmp/kifu-five-language-progress-prod-20261005.json` 的 **64 个五语齐全赛事覆盖全部 104,737 个非空 event_id 棋局**，并不表示覆盖全部棋局。剩余 21 个实体没有 FK 棋局，本轮无需继续翻译它们。

冻结 inventory 为 `/tmp/kifu-event-next5-20261005/PROD/inventory.json.gz`，捕获时间 `2026-10-05T09:52:55.080602Z`；按当前隐藏清单过滤：

| 范围 | 局数 |
| --- | ---: |
| 全库 | 173,025 |
| event_id 非空 | 104,737 |
| event_id NULL | 68,288 |
| NULL 中已隐藏 / 重复 | 250 / 7 |
| 公开列表中 NULL | **68,031** |
| 公开列表中已有赛事关联 | 104,735 |

这里是两个不同的交付进度：此前精确归一批次只给获批棋局写赛事 FK；中文首遍则对其余原文另做显示转换。因此已完成赛事的五语名称不会自动覆盖其余裸日期、文件名、泛称或尚未归一的带届次原文。赛事实体数量也不是未关联原文数量：公开 NULL 仍有 **25,397 种原文**。

## 公开 NULL 的类别与高频原文

类别沿用 [既有 PROD 原文捕获](kifu-event-display-weighted-prod-capture-2026-10-04.json)，仅和冻结 album 清单、250 隐藏 ID 做本地连接。

| 原类别 | 局数 | 含义 |
| --- | ---: | --- |
| unclassified_pending | 62,418 | 包括真实赛事变体、历史/训练对局、文件名及仍待归类原文 |
| empty | 2,811 | 事件原文空；保持空显示，无需虚构赛事 |
| generic_event_description | 1,539 | 段位赛 901、个人赛 638 |
| program_source_label | 1,160 | GNUGo3.8；软件标签不能当赛事身份 |
| game_description | 101 | 对局描述，不自动生成赛事实体 |
| corrupt_data | 2 | 沿用已有损坏数据处理 |

除上述空值/GNUGo/泛称外，高频完整原文为：Hoensha game **595**、Castle Game **539**、KB国民银行杯2012韩国围乙联赛 **339**、团体赛 **324**、10-game match **245**、友情杯 **176**、2013职业棋手精英赛 **137**、2014日本国家队新浪网络训练赛 **136**、升段赛 **125**、2013职业精英网络赛 **125**、全运会 **103**。

中文首遍资产对公开 NULL 有 **54,919** 局 exact-raw 显示提示及 **6,339** 局 album+SGF 显示提示；另有 2,811 空值、3,962 无资产提示。它们说明已有大量中文展示成果，不能计为审核通过的五语身份覆盖。中文提示恰等于已完成实体名的 1,243 局也只能作定位候选，不能据此批量写 FK。

## 第一批可执行：复用已批准的 123 局

[既有赛事类型独立决定](kifu-event-type-only-independent-policy-astra-2026-10-04.md) 及其 [逐局 JSON](kifu-event-type-only-independent-policy-astra-2026-10-04.json) 已批准 327 局类型语义；本地连接确认 327 局在当前冻结 inventory 均仍为 NULL。

| 现有目标 | TEST / PROD ID | 已批准局数 |
| --- | ---: | ---: |
| 韩国围棋联赛 | 50 | 50 |
| 中日围棋对抗赛 | 75 | 43 |
| 中国全国围棋团体赛 | 73 | 30 |
| **可复用现有五语实体合计** | | **123** |

最小实施：从旧决定精确抽取这 123 个 album ID，复用现有 exact-link 事务执行方式，定向刷新两环境的完整 album/SGF/source 前像及三个目标的已批准五语证据，生成两份待独立审核的执行包。只写 event_id；保留 edition、轮次、结果、原文和 SGF。不能把其内裸日期/文件名登记为全局别名，也不能把 30 局全国团体赛扩大为全部 324 局“团体赛”。

另外 204 局分别是韩国棋圣战 152、中国全国围棋段位赛 52，需要新赛事类型及名称，排在本次既有 ID 批次之后。旧决定里“五语翻译暂停”的流程描述已被本轮用户授权取代；逐局身份范围和保留原字段的约束仍适用。

## 已有 raw 多语方案：2,134 局，暂存后续

- **段位赛/个人赛 1,539 局**：[classification-v2 的 22 格最终修订包](kifu-name-generic-classification-v2-22-final-v2-review-clone-rehearsal-sol-2026-10-03.md) 已审核并完成隔离 clone 显示、搜索、重放及撤销演练。
- **Hoensha 595 局**：[archive-description-v1 十一语包](kifu-name-hoensha-archive-v1-final-review-clone-rehearsal-sol-2026-10-03.md) 已同样通过；它表示方圆社史料来源，不冒充一个正式赛事。

这些既有包覆盖五主语言，可复用固定词句与来源；无需重做翻译研究。但目前尚不能直接换 owner ID 后导入：

1. PROD 定向只读确认“段位赛” raw74834、“个人赛” raw71508、“Hoensha game” raw69522 均已存在、review_status=pending、无名称。旧 clone 包则创建新 raw owner。当前 `name_batch._apply_owners` 对已有 ID 直接跳过，不会应用已审类别；读取器要求 raw owner 已批准。Hoensha 还需把旧 unclassified_pending 改成已审 archive 类别。
2. 当前 PROD legacy overlay 只读 entity names 与 CN 首遍提示，没有 reviewed raw_event_names 的显示/搜索路径；只入库不会在该运行时兑现这 2,134 局的五语显示。

后续最小补齐应沿用既有 preimage/change/undo 机制做有限 raw 类别批准，并把既有审核读取规则接入 legacy；无需新表或新证明框架。本轮先交付 123 局，不为这两个兼容点扩大实现范围。

## 再下一批的优先级与风险

在公开 NULL 原文中，按已登记赛事 canonical/alias 做唯一目标的子串定位，得到日本龙星 ID40 **424**、台湾棋王 ID53 **328**、日本女子名人 ID34 **254**、韩国名人 ID49 **159**，合计 **1,165** 个候选，且均不在既有 4,768 局 HOLD 并集中。可将它们作为下一组精确范围包，复用已批准赛事身份来源；这些数字是待复核候选量，不是已批准写入量。无需为只关联类型而默认核验全部届次/赛果。

韩国围乙的显式原文候选虽达 **1,211**，却已有 [一级/二级身份边界 HOLD](kifu-event-after743-leagues-independent-decision-astra-2026-10-04.md)；其中唯一现有别名定位的 1,025 局全部在旧 HOLD 集内。不能因数量大或中文首遍已有标签就直接解锁。Castle Game 539 及其他历史、训练、泛称原文也不能硬塞进相近现有实体。

**建议顺序：123 局已审精确关联 → 1,165 局现有实体候选的有限类型复核 → 2,134 局已审 raw 显示包的两个兼容点。** 不处理零 FK obsolete 实体，不触碰已隐藏 250 局，不把中文资产命中或名称相似当作新的身份批准。

本地统计摘要：`/tmp/kifu-null-event-summary-20261005.json`；分类来源为既有捕获、中文资产和冻结 inventory，没有新建审计体系。
