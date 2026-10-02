# Gosei 核心：624 盘有限范围与五语用名线索（HOLD）

2026-10-03，只读候选备忘录。这里的 `Gosei` 是冻结赛事拆解结果的**待审核心字符串**，不是已批准的赛事实体、译名或棋谱链接。没有写数据库、改代码或应用候选。

## 选择理由与有限原文

输入为受控 `kifu-event-groups-prod-v4-20261002.json.gz`（文件 SHA-256 `ae483b833c73879cf9b5544060d3857f1898806fddb76c93c2e6e0bda6716d05`，内容 SHA-256 `2cad3eb47908cc585c1090cd79e9209e8815b7025fef9724b0cedf2ca8b0b8d9`），对应生产 inventory SHA-256 `66b8946d908468c5f9c8f0dc8ef4b4ceddb76d840ef42f5cff5122fc5744b3a3`。按相同核心汇总，剔除已研究的 Oteai、富士通杯、Oza，以及已有单独材料的 Old Meijin、Pro Best Ten、日本棋院选手权、Tengen、NHK 杯、日本龙星战等，未闭环高频项包括 Meijin（927 盘/45 种）、Kisei（899/52）、Gosei（**624/44**）、日本碁圣战预选（593/36）、日本 SGW 杯中庸战预选（545/18）。前两者有更广泛的同名系列边界；本次选 Gosei 的有限 44 种英文原文和 624 盘，便于一次拆开核心、届期和来源语境。这个排序只是研究优先级，不断言其他组已经完成翻译。

| 原文字形 | 棋谱 | 变体 | 例子 |
| --- | ---: | ---: | --- |
| 届期紧连核心 | 353 | 24 | `10thGosei`、`24thGosei` |
| 核心后逗号届期 | 175 | 16 | `Gosei,11th`、`Gosei,1st` |
| 届期空格核心 | 96 | 4 | `1st Gosei`、`4th Gosei` |

44 种原文分别标有第 1–19、21–28 届；第 20 届没有该核心原文，不应补造。完整 44 行和逐盘语境留在仓库外受控文件。每个原文都要保留原样：`Gosei` 作为候选系列核心，`1st` 等作为待审**届期组成部分**；日期是棋谱语境，不能由它生成或更改届期。另一组 `日本碁圣战预选` 涉及预选阶段，不能仅凭同一赛事词干并入这 44 种写法或套用相同槽位范围。

## 棋谱和来源边界

冻结 inventory 中精确命中 624 个不同 album，`event_id` 和 `duplicate_of_id` 均为空。来源分布：19x19 为 528 盘；CWI 为 96 盘，其中 91 盘在 `CWI_1950_1978/Gosei/<届期>/` 且目录届期与原文相等，另外 5 盘在 `CWI_1950_1978/Cho_Chikun/`，ID 为 157743、157748、157750、157769、157770，需逐盘核来源。CWI 行的 `round_name` 含 `Preliminary` 89、`0` 3、`League` 2、`League Play-off` 1、`1` 1；19x19 的 528 行无 round。即便是直系目录，路径相符只证明导入来源形式相符，尚须校验 SGF 原文和实际赛事阶段。

日本棋院记载碁聖战创设于 1975 年；[CWI 专业棋谱目录](https://homepages.cwi.nl/~aeb/go/games/games/Gosei/)按第 1 届对应 1976 年列出对局。以 `1975 + 届期` 作**筛查参照**，275 盘日期在对应年、348 盘在前一年（预选可能提前，但逐盘归属尚未核实）。余下 **1 盘 HOLD**：album 64235，原文 `24thGosei`，日期 `1900-01-01`，19x19 来源 `41349078.sgf`；这是明显哨兵/冲突日期，不能据此推断真实比赛年。其余 623 盘仅通过粗粒度年差检查，并未因此取得事件身份 PASS。冻结清单日期为 1975–2003（另有上述 1900 哨兵）；新导入、原文字段变化或来源更换必须重新圈定范围。

## 五语直接用名线索

以下页面及辅助消歧页面的 HTTP 200 原文已存入受控目录，哈希见 `source-manifest.pending.json`。它们支持**核心名称候选**，不是 624 盘的逐盘身份证明，也不决定阶段或届期呈现。

| 语种 | 直接来源与见证用语 | 待审核心候选与边界 |
| --- | --- | --- |
| 简中 | [野狐围棋原站日本第 46 期赛事报道](https://www.foxwq.com/news/listid/id/11892.html)：`第46期日本碁圣战挑战赛第2局`；另存[新浪体育转载](https://sports.sina.cn/others/qipai/2021-08-30/detail-iktzscyx1222387.d.html?wm=3049_0015)。 | `日本碁圣战` / `碁圣战` 待定；中文产品是否保留地域限定需审核。 |
| 繁中 | [中央社日本第 43 屆报道](https://www.cna.com.tw/news/firstnews/201808030322.aspx)：`日本圍棋第43屆碁聖戰` | `日本碁聖戰` / `碁聖戰` 待定。台湾另有本地[中環碁聖賽](https://www.haifong.org/game/classes/480E360835EAB350F93094AAECD2A797)，不能靠 `碁聖` 一词跨系列映射。 |
| 日文 | [日本棋院赛事页](https://www.nihonkiin.or.jp/match/gosei/026.html)：棋戦名称 `碁聖戦`，列出主办方和预选/本战结构 | `碁聖戦`；第几期和预选等是独立组成部分。 |
| 韩文 | [韩国棋院日本第 38 期预选报道](https://m.baduk.or.kr/news/B01_view.asp?news_no=586)：`제38기 기성(碁聖)전 예선A조`；[Tygem 专业围棋报道](https://tygem.game.naver.com/news/news/view.asp?find=&findword=&gubun=&pagec=21&seq=616)明确与 `기성(棋聖_기세이)전` 区分。 | `기성(碁聖)전` 或其它清晰限定形式待独立审核；不能把这两项同音赛事共用裸 `기성전`。 |
| 英文 | [CWI 专业棋谱目录](https://homepages.cwi.nl/~aeb/go/games/games/Gosei/)：`Gosei title games`、`Gosei (碁聖) title match` | `Gosei`；目录的 title-match 表述不能覆盖库存中的预选行。 |

## 继续审核所需

1. 将 44 种原文的来源 SGF 根字段、目录和棋谱上下文逐项核对，尤其是 528 盘 19x19、5 盘异目录 CWI，以及 1900 年日期。只在核实过的有限 album 集合内签链接；保留预选/联盟/挑战手合等阶段差异。
2. 独立审查五语候选的赛事实体指向与显示形式，特别是繁中台湾同名赛事、韩文 `碁聖`/`棋聖` 消歧。随后再考虑其余六语和组成部分模板。
3. 制包时使用当时的 inventory 和事务内前像；本备忘录的频次、日期与来源仅来自冻结只读快照，没有复查今天的生产差异，也没有批准任何链接。

受控目录：`/Users/fan/.local/share/kifu-name-audit/2026-10-03/gosei-core-pending/`（目录 `0700`，文件 `0600`）。`slot-context.pending.jsonl` SHA-256 `41b9c3f7029e5361bb043d87fb9878c886962b6282be7a5bc7e33e64e02a137f`；`scope-summary.pending.json` SHA-256 `759423b53cf9c029c59565d3ce33707ac6440dd9478510ad9db0aa6c02684fcd`；五语与消歧响应体的时间、URL、哈希固定在 `source-manifest.pending.json`（SHA-256 `91fac3bdc1376a3cefa549992412e306d5cd4bc566fdeb6076590eac78fb514f`）。文件均为 HOLD；没有 Git 提交。
