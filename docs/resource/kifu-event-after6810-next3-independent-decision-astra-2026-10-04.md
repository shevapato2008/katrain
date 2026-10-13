# 三类赛事独立决定（Astra，2026-10-04）

批准 **2,153 个精确 album ID 的赛事类型关联**，共有 **268 个 HOLD**：原有 258 个全部保留，其中 19 个来自既有独立决定；另增加 10 个 KBS 简称记录。批准创建／解析以下三个规范类型；**本批所有 `event_edition_id` 必须保持 NULL**。

| 规范中文名 | 批准棋谱 | 该家族 HOLD |
| --- | ---: | ---: |
| 台湾友士杯十段赛 | 1,002 | 20 |
| 韩国KBS杯围棋王战 | 748 | 13 |
| 台湾联电杯职业围棋赛 | 403 | 0 |

另有 235 盘边界／其他赛事继续 HOLD。本次不解除任何旧 HOLD。

新增 HOLD 为 **29289、37535、37540、49258、50118、84628、91046、101391、101394、111481**。这些记录只重复 `5th/10th/19th/20th/21stKBSCup`，没有明确的 BadukWang／围棋王／棋王根标题，也未取得具体官方对局确认。本次按与原 HOLD 38770 一致的边界保留，不认定它们属于其他赛事。

**KBS 规范名修订为“韩国KBS杯围棋王战”**：[韩国棋院](https://www.baduk.or.kr/game/game_view.asp?cmpt_code=1106)使用 `KBS바둑왕전`，[中文维基百科](https://zh.wikipedia.org/wiki/KBS%E6%9D%AF)正文使用“KBS杯围棋王战”。本次只用维基百科辅助确定中文名称，不使用其年份表建立届次；官方记录存在跨年和同年两届情况。

赛事边界已核实：[友士杯官方历届表](https://www.haifong.org/news/content/5C0B8E819C04BC5F1D554375C86715E1)及[比赛办法](https://haifong.org/game/class_content/3854390B76776737CA4528BB9BD733B1)支持资格赛、初赛、本赛和挑战赛属于同一类型；友士队参加的团体赛、邀请／擂台／训练赛和两盘钰德冠名记录均不并入。[联电职业赛目录](https://haifong.org/game/classes/2E725C23C4DE1EEF626BA6D71BDEC4B2)与[UMC 快棋争霸报道](https://haifong.org/news/content/8BB86AE4EFB3EB5CA6C81764E83AEDF3)证明两者组织与赛制不同，122 盘快棋争霸记录全部保留 HOLD。KBS 文件名、特别对局及 MBC 冲突标题同样保留 HOLD。

已重新解析全部 **2,421 盘完整 SGF**，核对完整行／SGF／根属性／来源关联哈希、双方原名、结果、日期、19 路棋盘、主线手数与精确分区；候选全部通过。645、691 的来源原值“弈客围棋”和 SGF 双重 SO 标注有一致来源路径，并由[台湾棋院 2022 年 9 月对局表](https://taiwangorg.blogspot.com/2022/01/20229.html)确认第三届联电职业赛挑战赛前两局身份，批准类型关联且原样保留来源数据。[韩国棋院新闻](https://m.baduk.or.kr/news/B01_view.asp?news_no=4473)另确认 5846 的第 41 届 KBS 半决赛对局锚点。其余棋谱依赖已固定的本地 SGF／原文／来源证据；本审查未逐盘检索官方比赛档案。

existing17 棋手批次已报告提交并复核，决定固定了 [TEST](kifu-player-existing17-TEST-applied-plan-2026-10-04.json.gz) 与 [PROD](kifu-player-existing17-PROD-applied-plan-2026-10-04.json.gz) 实施计划及[实施记录](kifu-player-existing17-applied-2026-10-04.md)。两环境各 **27 个精确 FK 槽位**的目标 ID、目标目录行及只改变该槽位的完整 album 后像哈希均已列入机器决定；其中 62611 的棋手 FK 可为已批准后像，其赛事仍 HOLD。执行器必须重新读取并确认这些后像，仅允许该 27 个单元格的重基线。TEST 仍须独立捕获完整赛事范围；本审查未查询提交后的实时数据库。

机器决定（revision 2）：[JSON](kifu-event-after6810-next3-independent-decision-astra-2026-10-04.json)，[校验文件](kifu-event-after6810-next3-independent-decision-astra-2026-10-04.json.sha256)。SHA-256：`87251ecea191f7cce337ee488e7daf82a71908dfda28455576197c9c499c872d`。

初版 SHA `5e652e368a087520a3d89a6e0333f470a9f1f507b7535767dda34c113898ffd5` 已撤销，不得用于计划或写入；机器决定记录了替代关系，并保留初版压缩存档供追溯。

决定包含精确批准／HOLD ID、逐行前像哈希、全部既有 HOLD 交集、环境各自的棋手重基线、完整目录／别名／届次／来源哈希和[来源存档清单](kifu-event-after6810-next3-independent-sources-astra-2026-10-04/manifest.json)。类型数字 ID 必须分别在 TEST／PROD 实时解析或受控创建，不得预设或复用日本十段战、其他棋王赛 ID。后续类型创建和关联写入须使用另行固定的环境执行计划；不创建别名／届次，不改写原文、棋谱或来源。本审查没有数据库写入或生产代码编辑。
