# 棋手目录简体化与去重：独立身份裁决

2026-10-04，独立 gpt-6-astra max。只读核对 TEST `katrain_db` 与 PROD `katrain_prod_20260725`，未改代码或数据库。本裁决批准身份及有限处理范围，执行应另冻结两库计划。

## 可执行拆批

| 批次 | TEST | PROD | 裁决 |
|---|---|---|---|
| A 简体 canonical | 542 趙善津→赵善津；348 工藤紀夫→工藤纪夫 | 541 趙善津→赵善津；347 工藤紀夫→工藤纪夫 | PASS，ID 保留，既有 66／366 槽位不迁移 |
| B 繁简重复目录 | 1028 周鶴洋并入1048 周鹤洋 | 无同等重复目录 | PASS 同人身份；源目录0棋局FK、0alias、0evidence、5条旧名称 |
| C 两盘错字 | 87152白方9988→1048；148135黑方9989→1048 | 4193 canonical改周鹤洋；87152白方保留4193；148135黑方4194→4193 | PASS，仅两个冻结槽位 |

A 可保留旧 canonical 为准确繁体 alias，但需单独列入计划并检查规范化别名碰撞。A 的全部旧五语名称保持 `review/legacy_unverified`。日本棋院的[赵善津资料](https://www.nihonkiin.or.jp/player/htm/ki000187.htm)和[工藤纪夫资料](https://www.nihonkiin.or.jp/player/htm/ki000026.htm)分别给出对应日文姓名、罗马字、生日及职业履历；432个既有FK关联SGF的原名及年代均与这两个既有身份一致。

B 的两套名称cn/en/tw逐字相同，jp/ko不同：1028为 `チョウ・カヨウ / 주학양`，1048为 `チョウ・ホーヤン / 저우 헤양`。安全合并方式为冻结并归档1028全部5条名称原像，保留1048的5条原行及审核状态，再删除源名称与重复目录；不把任一日、韩写法升级为核准名称。`周鶴洋`准确繁体别名可指向1048。中国围棋协会冻结官方响应 `CWA000014 / 周鹤洋 / 1976-06-18` 已重新读出并验证SHA；本次实时API重取超时，未将旧响应描述为本次实时结果。[海峰棋院倡棋杯历史](https://www.haifong.org/game/classes/889B583FD295AC653FB6B4B0AA0DA5CC)使用繁体周鶴洋；既有姓名来源复核也将该名称对应到同一协会棋手。

C 两盘身份由专业战报和对应对局记录交叉确认：

- 87152白方 `周鹤样`：2005-10-14、围甲14轮、对金承俊、白胜、150手。[搜狐当年战报](https://sports.sohu.com/20051015/n227203560.shtml)确认周鹤洋获胜并说明该场从15日提前至14日；[对局记录](https://www.goratings.org/zh/players/135.html)确认14日执白获胜。
- 148135黑方 `周鹤羊`：2006-06-15、围甲6轮、对赵守洵、黑胜、211手。[搜狐当年战报](https://sports.sohu.com/20060615/n243752547.shtml)记录赵守洵负周鹤洋；上述对局记录确认同日周鹤洋执黑获胜。

已检查两库完整原谱根属性和主线：各盘跨库SGF SHA相同，赛事／日期／对手／执色／胜负支持有限身份纠正。未声称与外部SGF逐手哈希一致。

## 数据完整性边界

现有入向FK只有 albums黑/白、player_names、player_aliases、name_research_evidence。另有不受FK约束的 `kifu_raw_player_values.review_metadata.player_id`：C中PROD raw10148需4194→4193；TEST raw10145需9988→1048，raw10148需9989→1048。须比较完整旧JSON后仅改指向，保留 `pending`、原kind、inventory SHA和parsed_data；本裁决未批准将这些raw全局转approved。PROD raw10145本已指向保留ID4193。

合并前锁定／CAS目录、名称、两个槽位及完整metadata原像；重查无新增引用和canonical/alias碰撞。删除重复ID之前须确认所有入向FK与活动metadata引用为零并保存可回滚原像。TEST9988/9989和PROD4194均无名称、alias、evidence，每个只关联对应一盘。TEST1028无raw metadata引用。不得按两库ID差值推导目标。

## HOLD

- 860个周鹤洋、679个赵善津、570个工藤纪夫未关联槽位及其他繁体／拼音／段位变体，另作精确棋谱审核，不随目录操作自动并入。
- 全部五语旧名称的审核升级及周鹤洋jp/ko争议；该问题不阻塞上述保留审核状态的目录合并。
- 全局错字alias `周鹤样／周鹤羊`；任何原始SGF、raw姓名、日期、赛事或对手身份改写。

## 留存

完整目录原像与435盘SGF解析摘要／环境各一份：`~/.local/share/kifu-name-audit/2026-10-04/player-canonical-dedup-independent-decision/`。DB目录读取时间为2026-10-04 05:57 UTC，SGF／metadata读取时间05:59 UTC；执行前需重冻结。目录、棋谱摘要、两份搜狐原文的SHA和精确操作清单见同名JSON。
