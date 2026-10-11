# 下一批 15 个高频中文棋手身份审查（2026-10-04）

本轮只审查“一个 exact 中文 raw 是否唯一指向一个职业棋手”，不批准数据库写入，也不把同名段位变体自动并入。槽数来自 173,025 盘生产冻结 inventory；正式执行前仍须对 TEST/PROD 实时 capture，并把日期异常、同人对局、来源冲突逐槽置为 HOLD。

| exact raw | 冻结 exact 槽 | 规范身份 | PROD / TEST 目录决定 | 身份来源 | 结论 |
|---|---:|---|---|---|---|
| 林士勋 | 655 | 林士勋（官方：林士勛） | 新建 / 新建 | [海峰棋院棋士页](https://haifong.org/profession/venue/39DB6A531FEBD95C2829A32DA88CCCE0) | 候选 |
| 周俊勋 | 567 | 周俊勋（官方：周俊勛） | 新建 / 新建 | [海峰棋院棋士页](https://haifong.org/profession/venue/524D63AB167F4AC82887FD1660977B3E) | 候选 |
| 李志贤 | 486 | 李志賢（男，이지현，1992） | 151 / 152 | [韩国棋院棋手档案](https://www.baduk.or.kr/record/player_view.asp?pkey=10000570)；[韩国棋院中韩文排名表](https://www.baduk.or.kr/news/report_view.asp?news_no=1878) | 候选；官方档案明确标注男棋手，消除同音姓名疑义 |
| 小松英树 | 445 | 小松英樹 | 535 / **HOLD** | [日本棋院棋手档案](https://archive.nihonkiin.or.jp/player/htm/ki000148.htm) | TEST 同时有 536=`小松英樹`、1017=`小松英树`，先合并/裁决重复 ID |
| 沟上知亲 | 442 | 溝上知親 | 275 / 276 | [日本棋院官方升段表](https://www.nihonkiin.or.jp/news/docs/h26_godohyosyo.pdf) | 候选，exact 简体 raw 指向既有日文 canonical |
| 蔡丞韦 | 423 | 蔡丞韦（官方：蔡丞韋） | 新建 / 新建 | [海峰棋院职业棋士名录](https://www.haifong.org/profession)；[海峰棋院棋王赛报道](https://www.haifong.org/news/content/FE15E9D30449AED92A9B4DD1AC75FAD2) | 候选 |
| 偰玹准 | 399 | 偰玹准（官方：偰玹準；설현준，1999） | 新建 / 新建 | [韩国棋院棋手档案](https://www.baduk.or.kr/record/player_view.asp?pkey=10000767) | 候选 |
| 黄世元 | 380 | 黄世元（官方：黃世元） | 新建 / 新建 | [海峰棋院棋士页](https://www.haifong.org/profession/venue/4CE8E505BBEEC3B5C043C1C50291CDD9) | 候选 |
| 林彦丞 | 366 | 林彦丞（官方：林彥丞） | 新建 / 新建 | [海峰棋院职业棋士名录](https://www.haifong.org/profession)；[海峰棋院精锐队名录](https://www.haifong.org/elite/40466E1FFD8AD5CA6538D6FDD8497320) | 候选 |
| 张凯馨 | 364 | 张凯馨（官方：張凱馨） | 新建 / 新建 | [海峰棋院棋士页](https://haifong.org/profession/venue/C69D6010E6103B10BE46C2050F1B73ED) | 候选 |
| 岛村俊广 | 362 | 岛村俊广（官方：島村俊廣） | 新建 / 新建 | [日本棋院表彰名录](https://www.nihonkiin.or.jp/profile/enkaku/jyokun.html)；[日本棋院百周年棋谱页](https://www.nihonkiin.or.jp/special/100anniversary/kishi_select/44.html) | 候选 |
| 崔明勋 | 351 | 崔明勳（최명훈，1975） | 188 / 189 | [韩国棋院棋手档案](https://www.baduk.or.kr/record/player_view.asp?pkey=10000065) | 候选 |
| 韩尚勋 | 351 | 韩尚勋（官方：韓尙勳；한상훈，1988） | 新建 / 新建 | [韩国棋院棋手档案](https://www.baduk.or.kr/record/player_view.asp?pkey=10000467)；[韩国棋院中韩文排名表](https://m.baduk.or.kr/news/B01_view.asp?news_no=768) | 候选 |
| 安国铉 | 337 | 安国铉（官方：安國鉉；안국현，1992） | 新建 / 新建 | [韩国棋院棋手档案](https://www.baduk.or.kr/record/player_view.asp?pkey=10000548)；[韩国棋院中韩文排名表](https://www.baduk.or.kr/news/report_view.asp?news_no=1878) | 候选 |
| 张哲豪 | 337 | 张哲豪（官方：張哲豪） | 新建 / 新建 | [海峰棋院棋士页](https://www.haifong.org/profession/venue/A171DFC04906431680FC73EB858CC94A) | 候选 |

## 目录检查

冻结目录中只有 `李志贤`（PROD 151 / TEST 152）与 `崔明勋`（188 / 189）为同字既有 canonical；`沟上知亲` 可复用 `溝上知親`（275 / 276）。PROD 的 `小松英樹` 为 535；TEST 的 536 与简体重复 ID 1017 构成执行冲突，因此整项暂缓。其余 11 人没有精确简体或对应繁体 canonical/alias；建议依现有中文目录惯例以 exact 简体 raw 新建 canonical，把来源中的繁体/日韩汉字保留为官方姓名证据。

段位变体不在本范围：`周俊勋九段` 2、`小松英树七段` 2、`小松英树九段` 1、`小松英树八段` 1、`沟上知亲八段` 1、`岛村俊广九段` 5、`崔明勋九段` 7、`崔明勋　九段` 2、`崔明勋七段` 1、`韩尚勋三段` 6、`韩尚勋二段` 4、`安国铉二段` 1，全部继续 HOLD。

候选 exact 槽合计 6,265；其中 5,820 槽身份层面可进入下一步实时槽审查，`小松英树` 445 槽因 TEST 重复目录 HOLD。这里的“候选”不覆盖日期占位、自我对局、对手或来源冲突；这些必须由后续 frozen review 显式分流。
