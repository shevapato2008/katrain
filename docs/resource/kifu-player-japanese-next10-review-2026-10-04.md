# 日本棋士下一批10人精确候选（只读）

基于 post7 两库173,025盘冻结槽，并在2026-10-04读取两库实时目录及目标姓名全部对局前像。每库 **3,035个 NULL 棋手槽候选，20个 hold，现有FK保护0槽**。没有数据库写入；独立身份/范围审核、live capture、dry-run仍待执行。

|exact raw|TEST ID|PROD ID|每库候选槽|日期范围|官方来源|
|---|---:|---:|---:|---|---|
|佐田笃史|253|252|390|2012-07-09～2026-01-14|[棋院](https://kansaikiin.jp/kisi_prof/sadaatsushi.html)|
|铃木步|407|406|389|2001-04-01～2025-12-22|[棋院](https://archive.nihonkiin.or.jp/player/htm/ki000380.htm)|
|林汉杰|244|243|317|2001-08-20～2025-11-03|[棋院](https://archive.nihonkiin.or.jp/player/htm/ki000373.htm)|
|杉内雅男|12350|6586|352|1937-05-26～2017-11-02|[棋院](https://www.nihonkiin.or.jp/player_news/passed_away/post_261.html)|
|高木祥一|12352|6588|279|1964-10-15～2019-03-28|[棋院](https://archive.nihonkiin.or.jp/player/htm/ki000036.htm)|
|铃木伸二|807|806|305|2008-10-02～2025-12-28|[棋院](https://archive.nihonkiin.or.jp/player/htm/ki000419.htm)|
|加藤充志|315|314|259|1990-08-01～2025-08-25|[棋院](https://www.nihonkiin.or.jp/player/htm/ki000299.html)|
|上野梨纱|9|9|249|2019-03-30～2026-01-22|[棋院](https://www.nihonkiin.or.jp/player/htm/ki000489.htm)|
|张豊猷|781|780|248|2000-02-23～2025-12-18|[棋院](https://www.nihonkiin.or.jp/player/htm/ki000352.html)|
|安达利昌|325|324|247|2009-11-12～2026-01-08|[棋院](https://archive.nihonkiin.or.jp/profile/saiyou/2009/)|

仅按exact简体原文与冻结 album ID/side 关联唯一同字canonical，繁体、职衔、混合姓名、英文与其他变体不在本批。Unknown/Black/White不选；周鹤洋、赵善津、工藤纪夫及已冻结上野爱咲美/志田达哉/黄翊祖避开。小松英树、沟上知亲仍需目录决策。

七人存在简繁双目录：佐田、铃木步、林汉杰、铃木伸二、上野梨纱、张豊猷、安达。文件记录并保护传统ID，不合并/改名/重指已有FK；精确简体canonical在各库仅一条，精确简繁原文无player alias。杉内雅男、高木祥一、加藤充志仅一条同字目录。本批身份成立与目录去重是不同事项，仍须独立审核确认该保护边界。

逐盘对手检查：同原文自弈0盘，对手已有FK等于目标ID0盘。候选全部晚于或同于官方职业入段年份；杉内雅男全部不晚于2017-11-02，官方记录最后一局就是当天、2017-11-21逝世。19槽1900占位日期hold（杉内13、高木5、加藤1），另杉内1934-08-04 album 124951黑方hold，早于官方1937入段；不把时代异常自动归档。

两库文件分别保留post7 inventory SHA、目标目录/传统目录前像、3,012盘实时原文/日期/双方FK/赛事/来源/duplicate前像，以及候选六列槽、hold槽及原因。NULL槽总数3,055，扣除20后为3,035；相同album双侧可能均属于本批，所以盘数不等于槽数。

|库|候选review JSON|SHA-256|
|---|---|---|
|TEST|[kifu-player-japanese-next10-frozen-review-test-2026-10-04.json](./kifu-player-japanese-next10-frozen-review-test-2026-10-04.json)|`446e816da75b5a31c074fab8627c03e8f1bf70adfda105197d5e991596570d99`|
|PROD|[kifu-player-japanese-next10-frozen-review-prod-2026-10-04.json](./kifu-player-japanese-next10-frozen-review-prod-2026-10-04.json)|`7d1ca12e136a23125a8cb425575970d6113184013f55286589e231f45534b3f5`|

已核验：槽唯一、所有候选FK空、原文及日期与post7对应槽一致、各类总和正确、候选hold无交集。资料只支持当前exact身份关联候选，不等于已经批准执行。
