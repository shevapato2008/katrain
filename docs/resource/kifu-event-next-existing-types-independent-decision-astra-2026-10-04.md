# 既有赛事类型2,331盘：独立裁决

2026-10-04，独立 gpt-6-astra max。**PASS修订后的2,328盘／451个精确原文，新增HOLD 3盘。** 未写数据库或代码。原候选gzip SHA `dec60fc706bb8b64d55f59168744ff44992752f9b3be8e10455f225cc92d764a` 保持不变；精确清单见同名JSON，assignments SHA `86cdd9dad37bbc7647184aba64f8f3082f0bfec9a39b8767239ce037dcb21f86`。

|目标ID|类型|批准盘数|精确原文数|
|---:|---|---:|---:|
|24|日本本因坊战|665|204|
|37|日本新人王战|158|7|
|58|中国围棋天元战|799|149|
|59|中国倡棋杯|638|85|
|65|中国围棋名人战|68|6|

## 必须从原候选剔除

- **172253**：`2nd Shinjin-O`，1977-08-08，小林光一对大竹英雄。原谱明确 `RO[Memorial game]`、`BR[Shinjin-O]`、`WR[Meijin]`，为新人王对名人的纪念对局。[日本棋院历届记录](https://www.nihonkiin.or.jp/match/shinjin/archive.html)给出的第二期正式决赛对手是赵治勋；[小林光一回忆的专业译文](https://sports.sina.cn/others/qipai/2020-07-07/detail-iircuyvk2419514.d.html)也把对大竹的纪念棋另列。同raw其余40盘不因此排除。
- **31868**：`第69届日本本因坊战最终预选`，2013-08-08，256手。PB/PW/RE均缺，库中双方Unknown，暂无独立具体对局锚点，HOLD精确此盘。
- **41146**：`第10届中国名人赛第一轮`，1997-07-05，56手，同样缺PB/PW/RE且双方Unknown，HOLD精确此盘。

后二项属于证据不足，未判定为错误赛事；不从文字相近性补造棋手身份。原包1,742盘HOLD全部保持，合计HOLD **1,745盘**；未扩大到台湾倡棋选拔、韩国一二级联赛、Nihon Ki-in #1、异值标题或其他待研究原文。

## 独立核验与身份边界

两库分别以REPEATABLE READ READ ONLY读取候选及原HOLD全部4,073行，冻结event/date/players/source/path、两个赛事FK及SGF SHA **零差异**。TEST快照`4105688:4105688:`时间06:17:31 UTC；PROD快照`1715765:1715765:`时间06:19:32 UTC。两库五个目标ID的canonical均相同。全2,331份候选SGF重新解析：所有EV/GN选择与raw一致，无跨属性异值标题；同时检查RO/GC等根属性，从中识别上述纪念棋。候选无空/1900日期，年代及显式系列未见其他身份越界；1975等跨年预赛与1976等年度决赛不混作届期写入。

[本因坊第79期官方页](https://www.nihonkiin.or.jp/match/honinbo/079.html)说明最终预选、本战和五番挑战赛均属同一类型；结构变化不另建赛事。[国家体育总局](https://www.sport.gov.cn/n20001280/n20745751/n20767274/c22033486/content.html)确认同里冠名与中国天元系列；[新浪当年网选报道](https://sports.sina.com.cn/go/2016-12-31/doc-ifxzczff3487740.shtml?from=wap)确认2016年底网选进入2017年第31届本选和本赛，因此跨年网选属于同赛类型。

[第19届倡棋官方报道](https://www.sport.gov.cn/n20001280/n20067662/n20067613/c28644067/content.html)支持复赛及本赛归属；[2004年专业报道](https://sports.sina.com.cn/o/2004-07-05/1132979470.shtml)明确首届网选及7月5日聂卫平对柁嘉熹（候选119479），[专业回顾](https://www.foxwq.com/news/listid/id/8844.html)说明网络和后续选拔汇入正赛。倡棋第17至19届有停届间隔，不按逐年公式建届期。

[人民网赛事历史](https://qipai.people.com.cn/n1/2017/1031/c415041-29618168.html)及[第14届决赛当年报道](https://2012.sohu.com/25/88/sports_news163768825.shtml)支持中国名人身份和候选终局日期；中国名人保持与日本新旧名人、韩国名人、厦门邀请赛分离。

## 应用限制

只更新精确名单的 `event_id`，`event_edition_id`保持null。执行须绑定两库各自catalog原像和完整逐盘原像，不能按raw批量UPDATE；`2nd Shinjin-O`同时包含正式比赛和本次剔除的纪念棋，尤其不能按该raw整体关联。原始SGF、赛事文字、日期、棋手、来源及全部HOLD保持原像。

只读证据文件在 `~/.local/share/kifu-name-audit/2026-10-04/event-next-existing-independent/`，两库完整hash和快照写入JSON。身份裁决及精确子集通过不等于已经写库；执行后才报告新增关联量。

## 执行前像补充

新增 `approved_albums` 为2,328行十列数组：`id,event,date_played,event_id,event_edition_id,source,source_path,duplicate_of_id,target_event_id,target_event_edition_id`。前八列已分别从两库只读读取，完全相同且duplicate_of_id全为null；两库正式catalog完整行和目标map在 `environment_catalogs`。SGF SHA及选中属性仍由 `assignments` 逐ID提供，候选原SGF正文由已绑定候选包引用。`held_rows`为新增三盘八字段，`original_held_rows`为原1,742盘八字段。

- 十列应用清单SHA：`0d5241b0d24c878dd0f809a5df49ef4c0468ac948ca863221b4da3b026258413`。
- 内嵌决策SHA（排除本字段）：`bc7e98d904f6a13f5cbf6c73df045deef44b34bcc2b0433f1b040621d09363d7`。
- 最终JSON文件SHA：`0aa02a5d539c6a0f805e4ad040c156150608b622b9e5eb784ad4927ba04dab3b`。
