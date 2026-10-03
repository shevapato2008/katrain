# 日本王座战预选：有限来源核查（待审）

日期：2026-10-03（北京时间）。**PENDING / source-only / no approval.** 本备忘只核查冻结组的范围、赛事身份、阶段语义及来源支持的译名研究；不批准赛事合并、候选名、别名、规则或棋局关联，也未写入数据库／代码。

## 冻结范围与解析

输入为 protected `~/.local/share/kifu-name-audit/2026-10-03/oza-series-preliminary-scope/scope.pending.json`，SHA-256 `8a94c6104227324bfb21bc781b4b5ba85c4247f4648a1465204862936acd0413`。该 artifact 的全量范围含 Oza 2,061 局和预选 725 局；本 memo 只处理后者：**39 个精确原文、725 局**，全为 19x19 source、当前 event_id 均为空。精确原文是下列有限集合，不以子串扩展：

- 37 个 `explicit_components`：34 个 edition-only、3 个 edition+round；
- 2 个 `single_edition_fragment`：`日本第54期王座战预选`、`日本第55期王座战预选`；
- edition unit includes `期` and one `届` (`第62届…`); round forms are 14期/15期第3轮 and 20期第2轮.
- parsed editions: 2, 8–10, 13–15, 20–21, 23, 28, 33, 38, 44, 46, 50, 52–55, 58–73. Parsed edition/round proves the string grammar only, not edition-to-year or each SGF's identity.

Current grouping reports `日本王座战预选` as a component-backed core (725/725), while the older 2026-10-02 audit scope had 723 games/37 members and must not be reused as occurrence scope. See [event-core v4](kifu-name-event-core-priority-v4-2026-10-03.md) and [current Oza bounded scope](kifu-name-oza-series-preliminary-scope-2026-10-03.md).

## 身份与阶段来源核查

**身份：高置信度指向日本职业围棋王座战系列，但不能据系列名来源批准这 725 局。** 日本棋院沿革记载第1回王座战于1953年开始；日本棋院赛事日程及第54期档案将赛事名写作「王座戦」，并区分「予選C／B／A／最終予選」「本戦」「挑戦手合」。关西棋院第74期预选 A/B 组合表同时列出赛事主办方日本经济新闻社、日本棋院、关西棋院。这些日本棋院／关西棋院一手来源足以验证现代赛事身份和阶段词，不能证明所有历史年份使用同一分组制度，也不能逐局绑定当前 scope。[日本棋院沿革](https://archive.nihonkiin.or.jp/profile/enkaku/index.html) · [日本棋院赛程](https://www.nihonkiin.or.jp/match/schedule.html) · [第54期页面](https://www.nihonkiin.or.jp/match/oza/054.html) · [关西棋院第74期预选表 PDF](https://kansaikiin.jp/wp/wp-content/uploads/2026/01/%E3%80%8C%E7%AC%AC74%E6%9C%9F%E7%8E%8B%E5%BA%A7%E6%88%A6%E3%80%8D%E4%BA%88%E9%81%B8A%E3%83%BBB-%E7%B5%84%E3%81%BF%E5%90%88%E3%82%8F%E3%81%9B%E8%A1%A8%EF%BC%882026-1-28%E6%9B%B4%E6%96%B0%EF%BC%89.pdf)

**阶段：预选可作为独立于赛事 core 的阶段概念；不得将泛称预选改细为预选 A/B/C 或最终预选。** 当前 39 个原文未带 A/B/C，只有三条原文带第几轮；“第2/3轮”是轮次，不是阶段层级。现代结构不能回填旧期。`日本王座战预选` 是含有明确 stage 词的中文原始描述，本次不建议把整个字符串作为赛事 core 与 `Oza` 合并。

**与已审 Oza core 的边界：**此前 `Oza` 2,061/103 家族及五语核心名另有独立待审／复核记录。本组是单独的明确中文预选 cohort；系列基础名来源可复用为出处线索，但 Oza core 的身份、译名审查不能自动授权本组 owner 或原文行。保留两个范围，不合并、不交叉继承 occurrence。

## 五个主要语言的来源观察（仅来源层）

| 语言 | 来源实际用名 | 来源观察与限制 |
|---|---|---|
| `jp` | `王座戦`; 阶段 `予選` | 日本棋院官方名称及官方阶段。精确子类包括 `予選C/B/A/最終予選`，本组只支持泛称预选。 |
| `en` | `Ōza` / `Oza`; `preliminary tournament` | 英文 Go 条目把它识别为日本职业围棋七大头衔之一，并说明 preliminary tournament；American Go Association 使用 “Oza title”。Macron 用法不一。不能把 preliminary 自动解释成某一固定轮次。 |
| `cn` | `日本王座战`; `预选` | GoChess.cn 围棋 SGF 条目直接列“74期日本王座战预选a组”；日本棋院一手材料支持其所指赛事身份。该网帖是标签实际用名证据，不是主办方来源。 |
| `tw` | `王座戰` / `王座戰 (日本圍棋)`; `預選` | 繁中 Kifubara 日本围棋赛事页使用 `王座戰` 且标示日本职业赛及主办方；繁中维基标题用括注消歧，正文区分预选、本战、挑战手合。尚无发现更优的台湾职业棋院直接叫法。 |
| `ko` | `일본 왕좌전` / `왕좌전`; `예선` | 韩国棋院历史报道实际使用 `제18기 일본 왕좌전 1차예선`。既有韩语来源审查还记录韩棋院球员履历和韩文对局目录的用法。阶段词可观察，但具体 `1차` 不应移植到本组泛称。 |

直接来源：[GoChess.cn 第74期原始标签](https://www.gochess.cn/forum.php?extra=&mobile=no&mod=viewthread&tid=132142) · [Kifubara 繁中日本 Oza 档案](https://kifubara.app/zh_Hant/tournaments/32481df3-45e6-43b2-8e0a-c38e270ea1bb?edition=416efa86-b770-4e18-b052-794b8ea0433f) · [韩国棋院第18期报道](https://m.baduk.or.kr/news/B01_view.asp?news_no=1376) · [既有11语来源研究（引用线索，旧scope）](kifu-name-oza-qualifier-11lang-research.md)。这些形式是来源实际观察，**仍非候选审批**。

## 六个次要语言：仅可组合的工作构形

在本次有限检索中，次要语言没有找到足以同时证明该日本围棋赛事和该语言完整赛事名的可靠本地来源。如下仅是**待来源查证的拼接工作构形**：赛事 base 采用相应语言来源中观察到的 `Oza`/`Ōza`/`Одза`，stage 由一般“预选/qualifying”词义组合；不得登记为“来源实际用名”、不得据此提交候选。除俄语系列身份有俄语条目外，其余 base 的 target-language conventional status 均不足。

| 语言 | 可研究的组合（未证实惯用名） | 证据状态 |
|---|---|---|
| `de` | `Oza-Vorrunde` | 未找到日围棋德语来源确认 base 或完整组合；不建议作为候选。 |
| `es` | `torneo preliminar del Ōza` | 西语围棋资料可见 Ōza 日本赛事名，但当前没找到赛事页面直接用完整阶段名；组合为编辑构形。 |
| `fr` | `tournoi préliminaire de l’Ōza` | 本地法语 Go 页面用过 `Oza` 但检索命中多为欧洲资格赛/其他赛事；日本赛事身份和组合未证。 |
| `ru` | `предварительный турнир Одза` | 俄语条目直接把 `Одза` 指为日本围棋头衔并叙述淘汰赛；未见它将赛段命名为此短语，组合仍属编辑构形。 |
| `tr` | `Oza ön elemesi` | 未找到土耳其语日本围棋赛事命名来源；组合未证。 |
| `ua` | `попередній турнір Одза` | 未找到乌克兰语日本围棋赛事命名来源；组合未证。 |

俄语/意大利语/西语材料供身份及 stage 交叉参考：[俄语「Одза」](https://ru.wikipedia.org/wiki/%D0%9E%D0%B4%D0%B7%D0%B0)（secondary; 明示日本围棋及挑战者淘汰赛） · [意大利语第74届 Oza](https://it.wikipedia.org/wiki/%C5%8Cza_2026)（有意语 `tornei preliminari`，仅作组合措辞参考） · [西语 Ōza 条目](https://es.wikipedia.org/wiki/%C5%8Cza_%28go%29)。本次未用同名将棋王座战作证；[日本将棋联盟王座战页](https://www.shogi.or.jp/match/ouza/) 是不同赛事，必须排除。

## 待审决定

建议仅把该组视作 **Oza（王座戦）系列下的预选阶段 cohort** 进入下一轮逐局身份检查。**不能以当前证据批准 event_id 与 `Oza` core 绑定**：语义层面关系明确，仍需比对 725 局对应的源 SGF/原始标记及异常年份边界；尤其保护 edition、round 原值，不推导历史阶段细目。若要建立五语候选，可复核上述 `en/cn/tw/jp/ko` 的来源实际形式；六个次要语言需本地源证据或维持 unresolved。没有批准任何名称、别名、身份链接、candidate row、导入或 strict display。
