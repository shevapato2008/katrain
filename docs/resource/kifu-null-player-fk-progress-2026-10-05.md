# 无棋手FK进度诊断（2026-10-05 12:28 UTC）

只读；复用post123格式4库存，并在两库实时读取catalog、别名及通过现有 `_approved_names` / `_qualified_name_rows` 的五语名称。实时公开局数、双方FK和NULL槽计数与各自库存完全一致。未改或解除任何HOLD。

- PROD：公开172766局，双方FK143984局（83.3405%），缺33595槽、涉及28782局；TEST：双方FK142503局（82.4832%），缺35200槽、涉及30263局。
- `Unknown`1198、`Black`1158、`White`1158合计3514槽是占位值，不能强建人物FK。
- 下表为PROD缺FK槽前20原文。只有韩升周能唯一匹配现有canonical，但其五语尚未获批；前20当前可唯一匹配五语已批准owner为0槽。

| 原文 | NULL槽 | exact/现有rankstrip结果 |
|---|---:|---|
| `Unknown` | 1198 | 占位值 |
| `Black` | 1158 | 占位值 |
| `White` | 1158 | 占位值 |
| `小松英树` | 444 | 无精确owner |
| `姜勋` | 433 | 无精确owner |
| `Iwamoto Kaoru` | 381 | 无精确owner |
| `林彦丞` | 366 | 无精确owner |
| `Maeda Nobuaki` | 366 | 无精确owner |
| `王尧` | 355 | 无精确owner |
| `Fujisawa Hosai` | 353 | 无精确owner |
| `蔡竞` | 350 | 无精确owner |
| `韩升周` | 317 | 唯一ID513，五语未齐 |
| `Yoshida Yoichi` | 311 | 无精确owner |
| `Ito Tomoe` | 300 | 无精确owner |
| `鹤山淳志` | 280 | 无精确owner |
| `杨一` | 272 | 无精确owner |
| `Okubo Ichigen` | 268 | 无精确owner |
| `尹灿熙` | 263 | 无精确owner |
| `Kano Yoshinori` | 256 | 无精确owner |
| `Iwata Tatsuaki` | 255 | 无精确owner |

TEST前20另包含杨鼎新864槽，替代PROD第20的Iwata Tatsuaki；杨鼎新、小松英树、鹤山淳志、韩升周在TEST可唯一匹配canonical，均未有完整已批准五语。未把汉字转简、姓/名换序、去空格或模糊相似作为新增规则。

## 已批准名字可提供的有限线索

按精确字串、现有 `normalize_alias`（NFKC/大小写/空白规范）及 `split_player_rank` 匹配，且所有canonical/别名/批准名合并后仍唯一、已有同raw FK无异主冲突：

- PROD有58种原文、1017槽指向当前五语已批准owner，其中858为原串规范匹配、159为已有段位后缀剥离；TEST有63种原文、1225槽（858+367）。这是候选线索计数，不是关联批准。
- 最大三组为 `Rin Kaiho`247→林海峰、`Takemiya Masaki`233→武宫正树、`Cho Chikun`220→赵治勋。**这700槽仍受10月4日既有HOLD约束**，旧因包括汉字变体目录/历史FK冲突；不能仅以新名字获批直接释放。来源为 `kifu-player-nonhan-ranks-41-60-review-2026-10-04.md` 与 `...61-80...`。
- 余下PROD317槽示例：睦镇硕九段45、梶原武雄33、桥本宇太郎八段25、桥本昌二15、林君諺14、杉内雅男14、周鹤洋12。未逐项解除旧HOLD或审核SGF归属，不能称可立即写入。
- TEST比PROD多208槽，主要为吴清源九段149、八段41、七段15等后缀；这些说明两库历史FK覆盖不同，不需重新研究其已批准姓名。

即使上述1017个机械线索全部经独立身份/旧HOLD复核后可关联，PROD仅可新增814个双方有FK棋局，上限83.8116%；按当前已完成五语owner，仅新增385个双方五语完整棋局。达到双方FK90%/95%尚分别缺11506/20144局，靠当前这批名字的字串匹配无法解决。应先按既有精确槽工具审有限身份范围，再推进高频缺失人物；无需改匹配规则或重新设计流程。

完整只读结果：`/tmp/kifu-null-player-diagnostic-20261005/{PROD,TEST}-analysis.json`。此诊断未修改1117包及任何生产数据。
