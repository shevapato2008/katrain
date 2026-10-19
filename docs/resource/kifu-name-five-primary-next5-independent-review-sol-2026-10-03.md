# 下一批 5 名中国职业棋手五语名称证据独立复核

2026-10-03。**5 人的 25 个精确显示值 PASS，HOLD 0。** 原候选文件仍为 pending。本结论只签署名称证据；2,202 个原始 SGF 槽位均无归属、人物/FK、QID、正式导入或数据库写入批准。审核者 `/root/five_primary_next5_review_sol` 与候选生产分离；运行时标示 GPT-6，具体型号和配置未独立认证。

## 审核依据

输入为[固定候选说明](kifu-name-five-primary-next5-candidates-2026-10-03.md)及受控 JSONL，字节 SHA-256 `a21c93acf1a9811c436f1ed1a175b25c1f98d56853c4eae1a914b54f34f7494f`。逐人重新读取[中国围棋协会职业名册](https://www.weiqi.org.cn/player/professional)原始 API 响应：编号、简体全名、完整生日和段位均与候选相符；五个姓名在该 1,062 人名册中各出现一次。逐人核对留存的 GoRatings 四语榜单原始 HTML 同一站内 ID 的**完整链接文字**、中文人物页完整生日，并另抓取、保存、读回英／日／韩人物页 15 份，全部 HTTP 200，标题与完整生日相符。[GoRatings 榜单入口](https://www.goratings.org/en/)

Wikidata 留存实体 JSON 的 `en/ja/ko` 明确标签、日精度 `P569` 和对应 GoRatings ID 的 `P2805` 逐项相合。GoRatings 的多语页面仍属同一出版方，Wikidata 是结构化交叉线索，不视作四个独立来源。**杨士海例外**：`Q9081023` 的 `zh` 标签实际为 `楊士海`，没有在本次实体 JSON 中发现简体中文 alias；先前四语预检关于有简体 alias 的笼统描述不作为本次依据。`cn: 杨士海` 由协会原始名册与 GoRatings 中文榜单、人物页正文直接支持；同一实体的完整生日、`P2805=86` 以及英／日／韩标签相合。该例外没有被改写成“严格四语预检通过”。

繁中均核对实际正文及相邻上下文，未用 URL 或孤立 substring 批准。香港资料采用 CP950 解码；香港政府 PDF 的一页表格同时经文字提取及页面渲染核对。无一繁中出处列出完整 DOB 或协会编号，故此处只批准该围棋人物语境中的准确显示写法。

|名册姓名／编号／DOB|CN|TW|JP|KO|EN|繁中人物语境|
|---|---|---|---|---|---|---|
|马晓春 / CWA000006 / 1964-08-26|`马晓春` PASS|`馬曉春` PASS|`馬暁春` PASS|`마샤오춘` PASS|`Ma Xiaochun` PASS|[海峰 2021 三星杯历史表](https://haifong.org/news/content/0F98EC180E9B0946A4088FD4B3A89136)完整写作 `[中]馬曉春九段`，列 1998 亚军；[2018 世界业余赛回顾](https://haifong.org/news/content/3AC44A3742B0C361511AB616B32D59B2)另列 1983 中国代表。前者是主要职业语境，后者只作补充历史线索。|
|王檄 / CWA000026 / 1984-01-09|`王檄` PASS|`王檄` PASS|`王檄` PASS|`왕시` PASS|`Wang Xi` PASS|同一[三星杯历史表](https://haifong.org/news/content/0F98EC180E9B0946A4088FD4B3A89136)列 2004 亚军 `[中]王檄五段`；历史五段与当前协会九段相容。|
|杨士海 / CWA000098 / 1971-01-14|`杨士海` PASS（标签例外）|`楊士海` PASS|`楊士海` PASS|`양스하이` PASS|`Yang Shihai` PASS|[香港妙手圍棋院人物页](https://hk2.com/personages.htm)写其 1986 年成为中国职业棋手、1997 年升八段及中国／香港赛事经历；[香港政府 2025 围棋运动员名单](https://www.lcsd.gov.hk/en/ngames/2025/common/doc/athlete_list/mass/go.pdf)在男子个人公开组列 `楊士海`。|
|王汝南 / CWA000003 / 1946-09-02|`王汝南` PASS|`王汝南` PASS|`王汝南` PASS|`왕루난` PASS|`Wang Runan` PASS|[海峰 2008 TOTO 杯报道](https://www.haifong.org/news/content/314C8924C474BA855D729498B9EA3716)的图说写 `中國代表王汝南八段`，与协会八段相合。|
|徐莹 / CWA000173 / 1972-12-31|`徐莹` PASS|`徐瑩` PASS|`徐瑩` PASS|`쉬잉` PASS|`Xu Ying` PASS|[海峰 2017 AlphaGo／柯洁报道](https://www.haifong.org/news/content/155298F458578BCA9084923F9D251788)正文称 `職業女子棋手和評論員徐瑩`；协会记录为女棋手五段。|

日文三个变体 `馬暁春`、`楊士海`、`徐瑩` 都是 GoRatings 日语榜单及人物页的实际标题／链接文字，并与 Wikidata 的明确日文标签一致；不是由繁中字符串自动转换。`王檄`、`王汝南` 的日文写法虽与中文同字，也从日文原文逐字核对。英文与韩文亦只通过表中精确值，不批准其他拼写、读音或转写规则。

## 碰撞及范围

按 `NFKC → casefold → 合并空白` 查本批同语候选、六期 GoRatings 留存索引及冻结目录：本批同语碰撞 **0**；四语候选在榜单索引均只指向各自站内 ID；冻结目录 canonical name、alias、同语 display name 碰撞 **0**。目录是 2026-10-02 的只读快照，SHA-256 `420ed4a10445a8d50c49d1132cd47ee8eee893b871dce2a968e8593775fa6105`，含 876 人、22 个显示名、23 个别名；没有重查当前生产数据库。零碰撞不证明棋谱归属，也不能排除全网同名。

保护审核包：`~/.local/share/kifu-name-audit/2026-10-03/china-professional-roster/five-primary-next5-review-sol/`（目录 `0700`，文件 `0600`）。逐行包固定候选行 SHA、名册记录、Wikidata 标签／生日／站内 ID、每语原始来源 URL 和正文 SHA、精确值与结论。签署 JSON 是审核者声明及 SHA 绑定，**不是**模型身份的密码学认证。

|产物|SHA-256|
|---|---|
|`reviewed-5.jsonl`|`d3f5204c3b2035e9751b6aab4ad5a210d17ce40cc8d544bedb68da3b555dd211`|
|`name-evidence-pass-25.scope.json`|`aa6837831788b104c2c94b314e6a1601220f91950a51f4f082e3c8fa75c4aa3a`|
|`complete-five-pass-5.scope.json`|`4d359ceab5afaaf33e36234302c200b826478f59a195af46610bd56e396c2786`|
|`name-evidence-hold-0.scope.json`|`7fa9b208c9ea4aa58b037fa4fcef019c904a56b1394971f2b25e01294bb2a787`|
|`profile-captures.json`|`de6812377901253af251f2c434ec25badf5fe77add27bbc1e442cf2c7b2c135f`|
|`review-manifest.json`|`d3b7c454f47bf42b43b200539db17169be395f8a6916ec258fc78f545f1ef118`|
|`review-signature.json`|`430774a591cd8b973042c4bdfe1b93e7e33f6a230999a2f21ca732125c2bbc15`|

本轮未修改代码、正式来源登记、数据库或部署，也未提交 Git。后续导入仍需独立人物／SGF 绑定、前像及正式导入审查。
