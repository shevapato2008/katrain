# 下一批 514 盘赛事独立决定（Astra，2026-10-04）

批准 **474 个精确 album ID 的赛事类型关联**，**40 个 HOLD**；既有 **4,225 个 HOLD ID** 与本包无交集，全部保留。本批不建立届次、别名，不改动原始赛事、日期、棋手、来源或 SGF；全部 514 行的 `event_edition_id` 保持 NULL。

| 规范中文名 | 批准 | HOLD | 类型动作 |
| --- | ---: | ---: | --- |
| 中日围棋对抗赛 | 146 | 23 | 两环境复核现有 ID 75 |
| 中国围棋霸王战 | 238 | 9 | 批准创建此精确类型；数字 ID 各环境现场分配 |
| 中国新体育杯 | 90 | 8 | 批准创建此精确类型；数字 ID 各环境现场分配 |

**最终 SHA-256：`d310278775a8a1b5e08062b271485effdce8e3e58ac5eb218639cdd66b60ce3e`**。逐盘批准／HOLD ID、完整根属性、SGF 哈希、环境各自完整行及来源关联前像哈希均在 [机器决定](kifu-event-next514-independent-decision-astra-2026-10-04.json)；[SHA 文件](kifu-event-next514-independent-decision-astra-2026-10-04.json.sha256)。本审查只有四个只读事务，没有数据库写入或生产代码修改。

## 赛事边界与来源

- **中日常规交流**：使用 [CWI 主年表（含 1976）](https://homepages.cwi.nl/~aeb/go/games/games/CJGoExchange/index.html)、[1987](https://homepages.cwi.nl/~aeb/go/games/games/CJGoExchange/1987/index.html)、[1989](https://homepages.cwi.nl/~aeb/go/games/games/CJGoExchange/1989/index.html)、[1990](https://homepages.cwi.nl/~aeb/go/games/games/CJGoExchange/1990/index.html)、[1991](https://homepages.cwi.nl/~aeb/go/games/games/CJGoExchange/1991/index.html) 的正式代表团与轮次记录。1989—1991 年正式年度代表团的年龄限制不改变其系列身份；[藤泽秀行青年访问团](https://homepages.cwi.nl/~aeb/go/games/games/CJShuko/index.html)属于另一系列。63706 的完整 SGF 明写“快棋表演赛”，125593 明写“藤泽秀行团中日青年围棋友谊赛”，143283 明写“特别对局”，三盘 HOLD。
- **中国围棋霸王战**：[1994-06-07 当时报纸报道的镜像](https://cn.govopendata.com/renminribao/1994/06/07/4/)及[野狐赛事史](https://foxwq.com/news/listid/id/16201.html)证明首届于 1994 年 7 月开赛；[1996-06-20 报道镜像](https://www.rmrb.zhouenlai.info/%E4%BA%BA%E6%B0%91%E6%97%A5%E6%8A%A5%EF%BC%881946-2003%EF%BC%89/1996/06/1996-06-20.htm)确认第三届分阶段预选。本赛、预选、胜败者组属于同一类型；不并入韩国霸王战。130503、134278、137048 的日期均为 1993-09-05，早于创办且未独立还原具体对局，HOLD。
- **中国新体育杯**：[国家体育总局／中国体育报](https://www.sport.gov.cn/n20001280/n20067662/n20067613/c22729544/content.html)确认这项历史赛事；[1990 年同期报道镜像](https://rmrb.zhouenlai.info/%E4%BA%BA%E6%B0%91%E6%97%A5%E6%8A%A5%EF%BC%881946-2003%EF%BC%89/1990/12/1990-12-12.htm)确认挑战赛机制，[1993 年末届决赛回顾](https://www.foxwq.com/news/listid/id/11568.html)支持末届决赛跨到 1993 年 3 月。规范名保留“新体育杯”并添加中国前缀；不合并大国手战、棋王赛。124065 的第二个 SGF GN/GC 却写“中国棋王赛”，HOLD。

## 数据质量 HOLD

完整解析及复盘 514 盘后，**31 盘在已占位置再次落子**；独立简化复盘和项目实际 `BaseGame._validate_move_and_update_chains` 在完全相同的 ID／手数报错，全部 HOLD。见 [复盘证据](kifu-event-next514-independent-replay-check-astra-2026-10-04.json)。未验证劫／超级劫或终局计分，未修复任何棋谱。

主线另比对本包及已关联 ID75 的 637 盘上下文：113607 经棋盘对称变换后，以已有 113606 的完整 176 手为前缀，且两者日期不一致，113607 HOLD；42422 与 47367 前 136 手完全相同，前 224 手仅第 137 手不同，却标注不同日期、双方及结果，两盘 HOLD（47367 同时为非法落子）。见 [主线重叠证据](kifu-event-next514-independent-duplicate-evidence-astra-2026-10-04.json)。本审查未做全库去重。

40 个精确 HOLD ID：

`36533, 36630, 36717, 41115, 42422, 47301, 47367, 52821, 58792, 59027, 59258, 60040, 60045, 60058, 63706, 80724, 82917, 106141, 111921, 112432, 113607, 116419, 119251, 119316, 120329, 124044, 124065, 125173, 125593, 127911, 128762, 130272, 130503, 134278, 137048, 137049, 137786, 139773, 143283, 145079`

批准的中日记录中，22 盘与 CWI 表的比分、执黑执白或记录长度有差异；两盘仅在轮次表中可查。日期／双方对阵和赛事标题足以确认类型，原始字段均保留；这不是对历史元数据正确性的认证。具体差异与 52830、130273 的颜色异文列于 [CWI 比对证据](kifu-event-next514-independent-sources-astra-2026-10-04/cwi-table-comparison.json)。霸王战、新体育杯的大部分对局未逐盘检索同期官方档案，类型关联同时依赖固定的 SGF／来源证据。

## 两环境前像与执行边界

| 环境 | next3 后只读捕获（UTC） | 类型目录 | 本批前赛事关联 | 仅本批后预期 |
| --- | --- | ---: | ---: | ---: |
| PROD | 09:59:51.856178 | 77 | 101,524 | 101,998 |
| TEST | 09:59:52.010427 | 77 | 101,042 | 101,516 |

next3 最终决定 SHA `87251ecea191f7cce337ee488e7daf82a71908dfda28455576197c9c499c872d` 及两环境 applied-plan 已固定。重新捕获确认只新增该批的类型 79／80／81，原目录、别名、届次、来源未发生其他变化；本包 514 行完整前像也未变化。比较旧工具时间戳时仅统一小数秒表示，执行哈希仍使用原始捕获 JSON。

PROD／TEST 的棋手数字 ID 不同，必须使用各自 [PROD 前像](kifu-event-next514-PROD-post-next3-independent-preimage-astra-2026-10-04.json.gz)／[TEST 前像](kifu-event-next514-TEST-post-next3-independent-preimage-astra-2026-10-04.json.gz)。候选 packet 的 `round_name` 空串是投影值，两个真实数据库均为 NULL；本决定将真实 NULL 固定为前像，不写轮次。

执行器应分别生成并固定 TEST／PROD 计划，验证完整前像及精确分区、回滚演练后按 TEST→PROD 执行。只允许 474 个 `event_id` 从 NULL 关联目标，以及创建上述两个精确类型；新数字 ID 不得预设。40 个新 HOLD 与全部旧 HOLD、来源、棋手、SGF 和原文不变。出现未解释的前像或目录变化时，须重新审查，不能自动放宽条件。来源正文、文本与 SHA 见 [来源清单](kifu-event-next514-independent-sources-astra-2026-10-04/manifest.json)。
