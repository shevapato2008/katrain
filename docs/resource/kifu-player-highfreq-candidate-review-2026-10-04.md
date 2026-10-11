# 高频中文三人：冻结候选，尚未完成实时预检

本轮候选来自已冻结 post7 inventory 和历史目录，仅作身份审查输入；不能执行到当前数据库。未写数据库。当前 SSH 路径连接超时，因此未捕获实时 FK、raw metadata、alias、译名及 evidence 前像，未进行事务 dry-run。

| 人物 | TEST 目标 | PROD 目标 | 冻结 NULL 候选槽 | 保护旧 FK | hold |
| --- | ---: | ---: | ---: | ---: | ---: |
| 小林光一 | 82 | 82 | 1,639 | 5 | 标题、连写、损坏等其他原值不纳入 |
| 井山裕太 | 56 | 56 | 1,279 | 0 | album 93943 黑白两个槽 |
| 萧正浩／蕭正浩 | 151 | 150 | 887 | 0 | 无 |

白名单仅 10 个 exact raw：小林光一、小林光一九段、小林光一八段、小林光一七段；井山裕太、井山裕太七段、井山裕太九段、井山裕太八段；萧正浩、蕭正浩。原值不改。候选清单每槽包含 album ID、side、exact raw、date、old FK，再附目标 FK。冻结旧 FK 五槽为 54327–54331，均已指向 82，只保护。

井山 self-game 为 album 93943，日期 2018-01-09，来源 `19x19`，路径 `data/kifu-album/19x19/41393565.sgf`，PB/PW 均为井山裕太。建议明确排除该 album 两槽，且不将 raw staging 的全量映射解释为该坏棋谱两槽已审核。其余 1,279 槽的对手原文无井山/Iyama 相同人物模式；其他两人候选对手亦无同人中文或常见罗马字模式。以上为冻结文件检查，实时 FK 对手仍需复查。

小林光一另有目录 ID 338「小林光一名誉」，本轮建议保留该 ID、全部引用与译名，仅把基本姓名及段位原值的 NULL 槽接向已有 82。官方[小林光一资料](https://archive.nihonkiin.or.jp/player/htm/ki000001.htm)及[日本棋院棋谱](https://u-gen.nihonkiin.or.jp/kifu_new/giboviewer/giboviewer.asp?gibo=4395%2F6mast_awaji_kouitik.sgf)显示名誉棋圣为人物称号；这不构成自动折叠旧目录权限。蕭正浩身份据[海峰棋院专访](https://www.haifong.org/news/content/89CC3622DAFF458D8A5403BF9546501F)，萧/蕭字形对应需独立身份确认。

文件 SHA-256：

- 冻结范围审查 JSON：`5aeacdfee3c655a50dbc6f8d720cd508ea8cae2b1ec651f0d4c746d836ac02f1`。
- TEST 候选 manifest：`38d30c6418bf400d2f0827971bc140939c0b032f2766b16e61b1d1077a20a77c`。
- PROD 候选 manifest：`1c6a08f40506eee4d68dc3bad489aa98d36e418b1eb3fcd65163cfe9a440d6be`。

后续必须独立审查身份与 album 93943 排除策略，分别实时捕获 TEST/PROD 五列前像及相关目录/staging 前像；现有 nonhan importer 要求所有槽 NULL 且禁止同名双方，不能原样套用此含五个保护槽及两个 hold 槽的整批。family importer 的八家族、两改名、504/20 计数为专批门禁，也不能冒用其格式。使用最小精确槽 importer，逐槽 compare-and-swap 并完整范围复核，生成真正冻结执行计划后才 dry-run；任何既有 FK 异人冲突均停止。写入等待协调。
