# 高频棋手繁简碰撞前 20 组：身份审查

2026-10-04。只读审查，输入为 `docs/resource/kifu-player-auto-batch-prod-2026-10-04.json`（SHA-256 `b633eaa698f12590a9ad513c1f7231d7c4d3cd9e5c4e49b0cc91d89753ba1a39`）。从 `holds` 中筛出 `han_variant_collision` 或 `homonym_qualifier`，按槽位数取前 20 个主组；同一 `canonical_name` 下另列繁简组。**结论只针对表中的纯姓名异体与其段位后缀**，不批准这 26,015 个槽位的棋局 FK 关联。

| 排名 | 简中默认名与同人异体 | 主组＋异体槽位 | 现有目录 ID | 审查决定与证据 |
| ---: | --- | ---: | --- | --- |
| 1 | 李昌镐／李昌鎬 | 2,199＋9 | 143 | **同人**。韩棋院列 이창호／李昌鎬，中文维基同页使用两形。[韩棋院](https://www.baduk.or.kr/record/player_view.asp?pkey=10000001) · [维基百科](https://zh.wikipedia.org/wiki/李昌鎬) |
| 2 | 赵治勋／趙治勳 | 2,065＋1 | 608 | **同人**。韩棋院列 조치훈／趙治勳，日本棋士生涯相符。[韩棋院](https://www.baduk.or.kr/record/player_view.asp?pkey=20000020) · [维基百科](https://zh.wikipedia.org/wiki/趙治勳) |
| 3 | 曹薰铉／曹薰鉉 | 1,970＋1 | 46 | **同人**。韩棋院正式汉字为曺薰鉉；中文维基同时使用曹薰铉、曹薰鉉。不能把“曹／曺”设为全库通用替换规则。[韩棋院](https://www.baduk.or.kr/record/player_view.asp?pkey=10000002) · [维基百科](https://zh.wikipedia.org/wiki/曹薰铉) |
| 4 | 林海峰／林海峯 | 1,690＋6 | 298（带头衔） | **同人**。日本棋院用林海峯，中文维基用林海峰；目录 298 的 canonical 为“林海峯名誉”，须先去掉头衔再作为纯姓名锚点。[日本棋院](https://www.nihonkiin.or.jp/player/htm/ki000009.htm) · [维基百科](https://zh.wikipedia.org/wiki/林海峰_(围棋)) |
| 5 | 依田纪基／依田紀基 | 1,396＋14 | 57、488 | **同人，合并目录重复 ID 候选**；简中显示用依田纪基，保留纪／紀原文。[日本棋院](https://www.nihonkiin.or.jp/player/htm/ki000101.htm) · [维基百科](https://zh.wikipedia.org/wiki/依田纪基) |
| 6 | 刘昌赫／劉昌赫 | 1,320＋2 | 69 | **同人**。韩棋院列 유창혁／劉昌赫，中文维基给简中名。[韩棋院](https://www.baduk.or.kr/record/player_view.asp?pkey=10000003) · [维基百科](https://zh.wikipedia.org/wiki/刘昌赫) |
| 7 | 武宫正树／武宮正樹／武宮正树 | 1,294＋16 | 490（繁体） | **同人**。后一个是混合字形；日本棋院正式名武宮正樹。[日本棋院](https://www.nihonkiin.or.jp/player/htm/ki000003.htm) · [维基百科](https://zh.wikipedia.org/wiki/武宮正樹) |
| 8 | 张栩／張栩 | 1,272＋5 | 80、313 | **同人，合并目录重复 ID 候选**；简中显示张栩。[日本棋院](https://www.nihonkiin.or.jp/player/htm/ki000331_4.html) · [维基百科](https://zh.wikipedia.org/wiki/張栩) |
| 9 | 王立诚／王立誠 | 1,246＋7 | 17、353 | **同人，合并目录重复 ID 候选**；简中显示王立诚。[日本棋院](https://www.nihonkiin.or.jp/player/htm/ki000065.htm) · [维基百科](https://zh.wikipedia.org/wiki/王立诚) |
| 10 | 朴永训／朴永訓 | 1,148＋1 | 66 | **同人**。韩棋院列 박영훈／朴永訓。[韩棋院](https://www.baduk.or.kr/record/player_view.asp?pkey=10000256) · [维基百科](https://zh.wikipedia.org/wiki/朴永训) |
| 11 | 羽根直树／羽根直樹 | 1,106＋4 | 323、612 | **同人，合并目录重复 ID 候选**。[日本棋院](https://www.nihonkiin.or.jp/player/htm/ki000307.html) · [维基百科](https://zh.wikipedia.org/wiki/羽根直树) |
| 12 | 申真谞／申真諝 | 1,105＋1 | 70 | **同人**。韩棋院正式汉字申眞諝，中文维基提供申真谞／申真諝；“真／眞”只作为此人的已证别形。[韩棋院](https://www.baduk.or.kr/record/player_view.asp?pkey=10000735) · [维基百科](https://zh.wikipedia.org/wiki/申真谞) |
| 13 | 金志锡／金志錫 | 1,099＋3 | 105 | **同人**。韩棋院列 김지석／金志錫，并曾在对外名单直接并列金志锡。[韩棋院](https://www.baduk.or.kr/record/player_view.asp?pkey=10000408) · [维基百科](https://zh.wikipedia.org/wiki/金志錫) |
| 14 | 高尾绅路／高尾紳路 | 1,094＋7 | 440、584 | **同人，合并目录重复 ID 候选**；简中显示高尾绅路（ID 584），正式日文原文保留。[日本棋院](https://www.nihonkiin.or.jp/player/htm/ki000305_7.html) · [维基百科](https://zh.wikipedia.org/wiki/高尾绅路) |
| 15 | 王铭琬／王銘琬 | 1,048＋13 | 无纯中文 ID | **同人**。日本棋院正式名王銘琬；目录另有“王銘エン”ID 420，不能仅据混写自动并入，须单独核 ID。[日本棋院](https://www.nihonkiin.or.jp/player/htm/ki000066.html) · [维基百科](https://zh.wikipedia.org/wiki/王銘琬) |
| 16 | 芈昱廷／羋昱廷 | 1,006＋1 | 396 | **同人**。中国围棋协会名册用芈昱廷，中文维基信息框列羋昱廷。[中国围棋协会](https://www.weiqi.org.cn/player/professional) · [维基百科](https://zh.wikipedia.org/wiki/芈昱廷) |
| 17 | 一力辽／一力遼 | 997＋1 | 42、539 | **同人，合并目录重复 ID 候选**。[日本棋院](https://archive.nihonkiin.or.jp/player/htm/ki000435.htm) · [维基百科](https://zh.wikipedia.org/wiki/一力辽) |
| 18 | 河野临／河野臨 | 984＋8 | 58、565 | **同人，合并目录重复 ID 候选**。[日本棋院](https://www.nihonkiin.or.jp/player/htm/ki000345.htm) · [维基百科](https://zh.wikipedia.org/wiki/河野臨) |
| 19 | 陈诗渊／陳詩淵 | 955＋4 | 无纯中文 ID | **同人**。海峰棋院职业棋士资料用陳詩淵，中文维基同一人页面；需建立纯中文姓名 ID。[海峰棋院](https://www.haifong.org/venue/248B7B2EE622C94D9B841530AE46D9FF) · [维基百科](https://zh.wikipedia.org/wiki/陳詩淵) |
| 20 | 范廷钰／范廷鈺 | 916＋1 | 206 | **同人**。中国围棋协会名册用范廷钰，中文维基信息框用范廷鈺。[中国围棋协会](https://www.weiqi.org.cn/player/professional) · [维基百科](https://zh.wikipedia.org/wiki/范廷钰) |

20 个主组 25,910 槽，旁系繁简原文 105 槽，合计 **26,015 槽**；本表确认的是 20 组各自的**同人字形关系**，并没有把不同人归在一起。七对目录重复 ID（依田纪基、张栩、王立诚、羽根直树、高尾绅路、一力辽、河野临）可以据此进入目录去重方案；实际主键保留、别名迁移、外键迁移仍须查看库中引用和约束。

带“挑战者”“棋圣”“名誉”的称号原文、人物连写及同名区分符应与纯姓名**分离处理**，不从表中推导自动别名。例如“曹薰铉赵惠连”是两人连写；“赵治勋棋圣”含头衔。棋局年代、来源和对手还需要逐盘或按来源范围确认，不能用本次名字证据直接把 26,015 槽回填到棋手 ID。
