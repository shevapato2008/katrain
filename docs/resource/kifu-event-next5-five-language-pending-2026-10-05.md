# 日本五棋战：五语名称待审包

2026-10-05。数据包：`/tmp/kifu-event-next5-20261005`。25 个名称均有对应语言正文支持，按现有导入器的 `conventional` 类型准备，状态全部为 `pending`；未写数据库。

| ID | 当前 canonical_name | cn | tw | jp | ko | en |
|---|---|---|---|---|---|---|
| 23 | 日本碁圣战 | 碁圣战 | 碁聖戰 | 碁聖戦 | 작은기성전 | Gosei |
| 26 | 日本棋圣战 | 棋圣战 | 棋聖戰 | 棋聖戦 | 기성전 | Kisei |
| 27 | 日本名人战 | 名人战 | 名人戰 | 名人戦 | 명인전 | Meijin |
| 28 | 日本王座战 | 王座战 | 王座戰 | 王座戦 | 왕좌전 | Oza |
| 29 | 日本天元战 | 天元战 | 天元戰 | 天元戦 | 천원전 | Tengen |

显示名称取赛事本名，与此前本因坊、十段包一致；catalog canonical_name 和赛事关联保持原值。名称不含届次、年份或阶段。名人战中文证据采用列表中 1976 年新名人战的条目，并与日本棋院当前名人战档案对应。

日文采用日本棋院各赛事历史页：[碁聖戦](https://www.nihonkiin.or.jp/match/gosei/archive.html)、[棋聖戦](https://www.nihonkiin.or.jp/match/kisei/archive.html)、[名人戦](https://www.nihonkiin.or.jp/match/meijin/archive.html)、[王座戦](https://www.nihonkiin.or.jp/match/oza/archive.html)、[天元戦](https://www.nihonkiin.or.jp/match/tengen/archive.html)。英文采用[日本棋院英文报道](https://www.nihonkiin.or.jp/english/topics/12/topics2012_11.htm)的常用名；其中 Oza 遵循官方无长音符号拼写。

中文来自维基同一日本头衔列表的[简体](https://zh.wikipedia.org/zh-cn/日本圍棋頭銜戰得主列表)和[繁体](https://zh.wikipedia.org/zh-tw/日本圍棋頭銜戰得主列表)正文，捕获修订号 93983385。四项韩文名见[韩国棋院井山裕太履历](https://www.baduk.or.kr/record/player_view.asp?pkey=10000324)；碁圣采用[韩文维基 작은기성전](https://ko.wikipedia.org/wiki/작은기성전)，修订号 40894600，避免与棋圣战的 기성전 混淆。维基记录附日本棋院同赛事身份佐证。

PROD、TEST 分别于 09:53:16、09:53:14 UTC 做只读捕获，按 canonical_name 找到并核实上述 ID。两环境五赛事名称表均为空，覆盖 16,455 局。环境各自的 `current.json`、`inventory.json.gz`、`bundle.pending.json` 和 `validation.pending.json` 均在包内；来源捕获在 `sources/`，共享研究在 `research.pending.jsonl`。Registry 沿用原版本 `2026-10-02.5`。

两环境 `validate_bundle` 结果均为：25 candidates、25 pending、0 missing、0 errors、0 write_errors。`ready/write_ready=false` 来自尚待独立签署；本包未进行数据库干跑或 apply。后续仍由现有导入器校验实时 catalog/inventory 和名称前值。
