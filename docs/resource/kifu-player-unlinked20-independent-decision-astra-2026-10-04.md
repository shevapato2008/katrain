# 未关联棋手 20 raw 独立决策（2026-10-04）

独立审查：gpt-6-astra。只读查询 TEST/PROD；本轮数据库写入 0，翻译写入 0。**五语言翻译继续暂停。**

## 决定

**部分 GO：PROD 11 raw / 1,587 个 NULL 槽，TEST 9 raw / 862 个 NULL 槽。** 两边均包括尹灿熙 263 槽的目录更名前置条件，以及本因坊算砂 1 槽的新建中文规范名。其余 PROD 9 raw / 1,358 槽、TEST 11 raw / 2,083 槽 HOLD。

若先不更正尹灿熙目录，可独立推进 **PROD 10 raw / 1,324 槽、TEST 8 raw / 599 槽**。这两个数字仍包含本因坊算砂的新建操作；纯复用子集分别 9 raw / 1,323 槽、7 raw / 598 槽。

本决定核准人物身份与精确 FK 关联，不认证棋谱全部元数据正确；不是已经入库完成的数量。

| exact raw | 每库槽数 | PROD | TEST |
|---|---:|---|---|
| 小松英树 | 445 | GO → 535 小松英樹 | HOLD 536,1017 |
| 韩升周 | 317 | GO → 513 韩升周 | GO → 514 韩升周 |
| Ito Tomoe | 301 | HOLD 3878,3879 | HOLD 9675,9676 |
| 鹤山淳志 | 280 | GO → 536 鶴山淳志 | HOLD 537,1008 |
| 杨一 | 272 | HOLD | HOLD |
| Okubo Ichigen | 268 | HOLD 4257,4260 | HOLD 10052,10055 |
| 尹灿熙 | 263 | GO 更名后 → 4455 尹灿熙 | GO 更名后 → 10246 尹灿熙 |
| Kano Yoshinori | 256 | HOLD 4048,4049 | HOLD 9844,9845 |
| Iwata Tatsuaki | 255 | GO → 4519 岩田达明 | GO → 10310 岩田达明 |
| Sumino Tsunehiro | 252 | HOLD 5435,5436,5437 | HOLD 11210,11211,11212 |
| Aoyagi Hideo | 14 | GO → 6400 青柳英雄 | GO → 12165 青柳英雄 |
| 王祥云初段 | 8 | GO → 559 王祥云 | GO → 560 王祥云 |
| Hayashi Tennyu | 6 | HOLD | HOLD |
| OnoYutaka | 2 | GO → 4440 小野丰 | GO → 10231 小野丰 |
| Koga Yoshio | 1 | HOLD | HOLD |
| Nikkai, 1st Honinbo Sansa | 1 | GO 新建 本因坊算砂 | GO 新建 本因坊算砂 |
| OkumuraNoboru | 1 | GO → 4274 奥村登 | GO → 10069 奥村登 |
| YamaguchiShigeharu | 1 | HOLD | HOLD |
| 久島国夫 | 1 | GO → 6669 久岛国夫 | GO → 12438 久岛国夫 |
| 小山滿鶴 | 1 | HOLD 4406,4409 | HOLD 10197,10200 |

## 尹灿熙：纠错并复用，禁止新建

- PROD 4455、TEST 10246 的 canonical 均为 **尹惨熙**；各自 alias 0，完整已关联集合只有 **album49563 / black** 一槽：2015-09-30、四段、对崔明勋、第2届韩国 LetsRunPark 杯64强，路径 `data/kifu-album/19x19/41331439.sgf`。
- [韩国棋院尹燦熙档案](https://www.baduk.or.kr/record/player_view.asp?pkey=10000465)明确姓名 `윤찬희(尹燦熙)`；2006入段、2014晋四段、2015年底晋五段。 [TYGEM 同日棋谱目录](https://tygem.game.naver.com/live/gibo/list.asp?find=&findword=&gubun=&pagec=926)精确载同赛事、日期、黑方 윤찬희 四段、白方 최명훈 九段。由这一对局配对推定既有“惨”为“灿”的错字，人物一致，不是另一个实体。
- **GO：将此唯一 ID canonical 从尹惨熙改为尹灿熙，再复用该 ID 关联本批 raw10680 的263槽。** 重查完整已关联槽仍只有上述一槽、alias仍空、无新竞争 owner；变动即停止重审。可在同一精确事务里重命名和赋 FK。
- 原始 SGF 和 raw“尹惨熙”保留；raw10667 的 review_status 本清单不改。其既有1槽不是新增关联数量。其它尹燦熙、带段位原名及组合队名均不在本批内。

## 本因坊算砂：可新建，历史叙事另保留不确定性

[日本棋院历史页](https://www.nihonkiin.or.jp/teach/history/history02.html)与[围棋殿堂](https://www.nihonkiin.or.jp/profile/sisetsu/dendou/list01.html)明确日海/Nikkai、初代本因坊算砂、幼名加納與三郎的身份关系。双库再次扫描本因坊、日海、算砂/算沙、罗马字及幼名，未找到同一人物；仅“加纳”短名空目录不能据此占用本因坊算砂身份。

**GO：各库创建1个中文 canonical“本因坊算砂”，仅绑定 raw8509 `Nikkai, 1st Honinbo Sansa` 的 album154458 / white。** 日本棋院同时说明1582三劫故事的史实性有争议，因此仅确认该署名指向的人物；不得把1582-06-20棋谱的真实性、日期、对手或结果标为已证实。写入前须再次排除新出现的同人物目录，分库记录真实生成 ID。

## 补查与 HOLD 原因

- **OnoYutaka → 小野丰**（PROD4440 / TEST10231，2槽）：[CWI 棋手晋段资料](https://homepages.cwi.nl/~aeb/go/misc/progression.html)明确小野豊/Ono Yutaka，1968年9月二段、1971年6月四段，吻合本批两槽；[专门棋手页](https://igorating.com/players/yutaka-ono)交叉确认汉字与读音。目录既有12槽1970–1993一致。大野伸行对应 Nobuyuki，应排除。此项依据专业整理资料，不声称找到日本棋院本人档案。
- **OkumuraNoboru → 奥村登**（PROD4274 / TEST10069，1槽）：[日本棋院本人档案](https://www.nihonkiin.or.jp/player/htm/ki000193.html)明确罗马字、1971四段，支持1977四段槽；现有1978/1980两槽同为四段。
- **久島国夫 → 久岛国夫**（PROD6669 / TEST12438，1槽）：[日本棋院本人档案](https://www.nihonkiin.or.jp/player/htm/ki000056.htm)确认1991九段。既有65个 Hisajima Kunio 槽中的1959/1960两局对木谷实，无职业段位/赛事；官方明确1957拜木谷实，因此这些早年记录未构成身份混入证据，不能仅以1965入段年排除本人。
- **Okubo Ichigen**：已由[日本棋院档案](https://archive.nihonkiin.or.jp/player/htm/ki000017.htm)确认大窪一玄，但补查发现大漥一玄/大窐一玄两个竞争目录（PROD4257/4260、TEST10052/10055）。HOLD，不再沿用“没有汉字锚点”的旧理由，也不新建第三个 ID。
- **Sumino Tsunehiro**：[CWI](https://homepages.cwi.nl/~aeb/go/misc/progression.html)给出炭野恒広/炭野武司及罗马字关系，[日本棋院档案](https://archive.nihonkiin.or.jp/player/htm/junkishi.html)也记载炭野恒広。目录已有恒广/恒広/武司三 owner（PROD5435/5436/5437、TEST11210/11211/11212），HOLD 待归属决策，不新建。
- **TEST 小松英树、鹤山淳志**各有简繁重复 owner，均为空；PROD各只有本次对应目标，故两库不能机械复用同一决策或数字 ID。
- **Ito Tomoe、Kano Yoshinori、小山滿鶴**涉及多个既有 owner；本批不批准合并、删除或任选其一。**杨一**有同名身份混合风险，不按年份/段位粗分。Hayashi Tennyu、Koga Yoshio、YamaguchiShigeharu 尚缺本轮足够的具体身份链，继续 HOLD。
- 其余 GO 的官方/专业来源、逐项理由与全部精确槽见 JSON。小松英树的1900占位日期、鹤山淳志的2008九段异常、韩升周的“六的”及 Iwata 的 Chubu 1st 标签均不因本次身份关联被改写或认定为正确元数据。

## 应用边界与证据

双库只读快照分别核对20 raw全部 **2,945 NULL槽**，与输入JSON的 `(album_id, side, date_played, rank, opponent_raw, event, round, source_path)` **逐字段完全相等**；原 raw 行均 pending、metadata null。全范围以 JSON 的 `exact_slots` 为准，按 `raw_value + album_id + side + expected NULL FK` 写入，禁止扩大到同名全库、其它原名或 alias 自动回填。

根代理应将本决定与新鲜完整 preimage 绑定到分环境计划，dry-run 后仅执行批准子集。HOLD保持；尹灿熙目录修正须单列前置操作；规范名新建/更名之外只允许精确 FK 与本批获批 raw 的审核元数据。原始SGF、事件/轮次/结果/日期/段位及五语言翻译均不在批准写范围内。

- 输入 JSON：`docs/resource/kifu-player-unlinked-timed-pilot-review-2026-10-04.json`，SHA256 `de1955a64d4dde46f05f1b1081f2944dcf59aa4da703131a2771b680343b058a`。
- 决策 JSON（全部20项、各环境ID、全部精确槽与前置条件）：`docs/resource/kifu-player-unlinked20-independent-decision-astra-2026-10-04.json`，SHA256 `21823dad57eb648ff1b23dcc6b10bb3926bd217bb456cf367a6d7e409e831238`。
- 只读证据快照：`docs/resource/kifu-player-unlinked20-independent-readonly-evidence-astra-2026-10-04.json.gz`，SHA256 `407a9f163b971a1f9e0e89eb91c7be48276372ad0e4b191e00b8bd3e2003ea1c`。
