# 下一批高频中文姓名：11 人，8,255 个冻结候选槽

只读准备；不含目录新建、改名或合并。冻结数据来自 TEST/PROD post7 inventory，当前前批 3,805 槽执行未影响本批姓名。本文不是实时执行计划；必须等待前批提交后重新捕获目录、staging、完整 exact raw 范围及对手 FK，并事务 dry-run。

| exact raw（唯一纳入原值） | NULL 槽 | PROD ID | TEST ID | 官方身份来源 |
|---|---:|---:|---:|---|
| 柳时熏 |875|164|165|[日本棋院 柳時熏](https://www.nihonkiin.or.jp/player/htm/ki000277.htm)|
| 山田规三生 |870|74|74|[日本棋院 山田規三生 / Yamada Kimio](https://archive.nihonkiin.or.jp/player/htm/ki000292.htm)|
| 陈祈睿 |851|44|44|[海峰棋院职业比赛：陳祈睿](https://www.haifong.org/news/content/0208FC010DA1063A1A897681EB06A230)|
| 林君谚 |833|100|101|[海峰棋院名人赛：林君諺](https://haifong.org/news/content/E846D83A08EA989828B0C6578BF88EC2)|
| 许皓鋐 |800|93|93|[海峰棋院许皓鋐海峰盃二连霸](https://www.haifong.org/news/content/0208FC010DA1063A1A897681EB06A230)|
| 赖均辅 |725|68|68|[海峰棋院賴均輔首夺海峰盃](https://haifong.org/news/content/6171780B5FAFE37808CFD6CB1520CE56)|
| 林书阳 |691|53|53|[海峰棋院职业比赛：林書陽](https://haifong.org/news/content/6171780B5FAFE37808CFD6CB1520CE56)|
| 谢依旻 |632|155|156|[日本棋院 謝依旻](https://www.nihonkiin.or.jp/player/htm/ki000398_3.html)|
| 许家元 |624|32|32|[日本棋院 許家元 / HSU, Chia Yuan](https://www.nihonkiin.or.jp/player/htm/ki000451_8.html)|
| 刘星 |679|644|645|[国家体育总局：阿含桐山杯第八、九届冠军刘星](https://www.sport.gov.cn/qpzx/n5387/c875721/content.html)|
| 睦镇硕 |675|22|22|[韩国棋院：목진석（睦鎭碩）九段](https://www.baduk.or.kr/record/player_view.asp?pkey=10000093)|

官方来源姓名与既有简体中文 canonical 的对应是本轮身份判断；不将标题、多人连写或混合 roman 字符串自动归并。冻结两环境均 8,255 候选、0 保护旧 FK、0 纳入范围 hold，exact 同名对手为 0。实时对手 FK、别名及 staging 仍需捕获校验。

## 原值变体与段位（明确不纳入本批）

纯段位原值共 59 槽：柳时熏九段3；山田规三生八段1；谢依旻三段3、四段1；刘星七段5；睦镇硕九段45、全角空格九段1。留给后续小批，防止在本批加入未检查的独立目录/alias 冲突。

其他原值：柳时熏RyuShikun2；许皓鋐黑嘉嘉1；本木克弥谢依旻1、谢依旻CGI1、谢依旻、一力辽1、高尾绅路谢依旻1；向井千瑛、许家元3；浙江刘星1；MOKJINSEOK睦镇硕1、睦镇硕MOKJINSEOK1；含睦镇硕多人原值合计5槽。上述不是候选。

## 目录冲突扫描与 hold

`kifu-player-highfreq-next11-catalog-scan-2026-10-04.json` 记录两环境既有目录逐目标的 exact canonical 及 normalized exact raw alias 扫描。每个 canonical 唯一且 ID 与环境正确对应；22 个姓名/环境组合均无异人 alias 冲突。这是本地已有快照扫描，不代替实时预检。

其他高频姓名暂缓：周鹤洋860（PROD无正确 canonical、周鹤样4193及周鹤羊4194不能仅凭形近字修正；TEST已有1048，应分别处理）；赵善津679（PROD趙善津541、TEST542，需单独有前像的简体 canonical 改名计划）；林士勋655（[海峰棋院](https://haifong.org/profession/venue/39DB6A531FEBD95C2829A32DA88CCCE0)为林士勛，目录新建/异体映射待核）；桥本宇太郎805（协调方提供PROD6577，但旧冻结目录未收录，先核实两环境最新目录和 alias）。不纠正旧错误目录或迁移其现有引用。

## 下一步

前批提交后使用现有 `scripts/kifu_player_exact_slots.py capture`，分别为 TEST/PROD 生成新的完整冻结执行计划；capture 的完整范围、目录目标唯一性、alias 冲突、staging metadata、同人对手检查全部通过后，分别 `run` 事务 dry-run。仅在协调批准后按 TEST→PROD 顺序 apply；当前未写数据库。

冻结 review SHA-256：PROD `c195ac1ed387ffd0f5ecd628bfed1e30e89f82b81805b7dd1b156b2c8a8c48ca`；TEST `86d6533f662d1881d4e9df9af6bdc35fc97e9b2a1f4a81206d652a3fa784239a`。

## 实时预检与事务回滚已完成

前批 3,805 槽提交后，已分别使用最新 repo exact/family/second helpers 和 models 捕获 TEST/PROD 全前像。两环境各 8,255 NULL 候选、11 exact raw、0 保护槽、0 hold；目标 canonical、exact raw alias、raw staging metadata 已冻结，对手 FK 在事务执行时实时复查。实际 SQL dry-run 更新检查成功并回滚；回滚后再次 capture，全部前像与冻结计划完全一致。未 apply。

- TEST 执行计划 SHA-256：`f3cb0247c989df6489be3f29ce0bc1ba70772da5387cc5853bf30801cd2933c7`。
- PROD 执行计划 SHA-256：`31181898f7b15e40c140f329eaf18dc5f6b4516a6ae65af2641155a92d05c5e4`。

等待协调批准以上两个 SHA 后才可 TEST→PROD apply。

## 已批准 apply 完成

独立 Astra max 审查通过后，协调批准上述固定 SHA，按 TEST→PROD 提交并验证。两环境均新增 8,255 FK 槽，11 staging 原值 approved。目标目录及相关 alias/name/evidence 前像未变；完整 selected raw/source/date 槽范围和目标 FK 均正确；全库 173,025 个 PB/PW 原始字符串未变；21 个排除 raw 的 FK/source/date 范围及 staging 前像完全未变（含 59 段位槽）。

| 环境 | 玩家 FK 槽前→后 | 目录 IDs | black | white | 双方玩家 | event | 三项齐全 |
|---|---:|---:|---:|---:|---:|---:|---:|
| TEST | 273695→281950 | 3848 | 140701 | 141249 | 117623 | 81926 | 54967 |
| PROD | 275300→283555 | 3670 | 141438 | 142117 | 118969 | 82408 | 55754 |
