# 高频退休棋手五语补齐决策

2026-10-06。用户授权的独立 Astra 决策；本次限时只读，只写本文，不批准任何具体姓名或数据库写入。

**决定：批准立即把一条资料工作线转向高频退休日本棋手，先闭环 3 人；采用“已有实际用名优先，缺名格走现有主五语 `generated`”路径。无需先改 `name_transliteration` 或建立通用转写服务。** 本决定没有把六次语言的宽松查证政策扩到主五语，也没有要求重新等待用户确认。

## 代码实际允许什么

- `name_transliteration.py` 的 `secondary-transliteration-v1` 明确限制 `SECONDARY_LANGUAGES`，其输出校验也不接受 Hangul。不能给规则换成 `ko`、扩语言集合或把日文读音套入中文拼音表来通关。
- `name_orthographic.py` 的 `primary-orthographic-v1` 只处理 `cn↔tw`；其 anchor 在 `name_evidence.py:1253` 起强制 `chinese_origin=True`、中文来源脚本、官方人物绑定和原名正文。日本姓名含汉字、中文 SGF/default name 都不能自动满足这些条件。不得伪填 Chinese origin。
- **主五语一般 `generated` 已经存在**：`name_candidates.py:617` 起接受真实 `not_found_in_scope` 研究、原语读音及 URL、明确生成规则版本和逐输出 `generated_review`。所以可以为本批命名 `primary-ja-to-ko-finite-20261006-v1` 的数据规则并人工逐名审核；不需要把 six-language `transliterated` 分支改为韩语。生成名称继续标 `generated`，不冒称韩文网页实际发表用名。
- 当前主五语负面闭环仍为既有 v1：在冻结 registry 指定来源内完成真实检索、分页和已知线索处置。核对的 `.8` registry 中 KO 必需项为韩国棋院、韩语 Wikipedia、Wikidata；`complete_for_negative_claims=False`，简单填三个 not_found 不能通过。v2 `secondary_reasonable_v1` 仅属六次语言。**五分钟是投入上限，不是“查无惯用名”的证明。** 完整的有限精确查询可以复用模板和已捕获结果；不要求无目的地穷尽整个网站。失败、404、页面空白、仅有 Latin 回退只能保留为未完成或对应的真实线索处置。

## 首个切片与实际证据

先由可用的 Sol 处理 3 人，root 保持实际入库；现有 Luna 正面来源批次继续。将已完成 owner ID 从工作队列剔除，避免重复搜索。

| PROD owner | 本地目录名 | 候选姓名槽位 | 已有可复用依据 |
|---:|---|---:|---|
| 3813 | 久井敬史 | 417 | 本人日本棋院资料明确 `ヒサイ ケイシ / HISAI, Keishi`，已有真实 GoRatings 英文名 |
| 4736 | 户泽昭宣 | 397 | 本人日本棋院锚点；已存 GoRatings 实际 `zh / ja / en` 名；KO H1 仍为 Latin |
| 5634 | 石井卫 | 345 | catalog 留有本人日本棋院 `ki000022.html` 锚点；需取回对应正文及原读音 |
| **合计** | **3 人** | **1,159** | 待补齐所有五语，不是已完成数 |

核对了 `/tmp/kifu-player-next5ai-20261005/sources/hisai-official.json`、`hisai-gr-en.json` 及 `/tmp/kifu-player-next5dc-20261006/sources/tozawa-gr-zh.json`、`tozawa-gr-ko.json`，四份存档原 body 均存在且 SHA256 与 metadata 一致。久井官方正文给出生日 1920-05-13、本人职业资料与读音；英文 GoRatings 1409 给出同一生日和 `Hisai Keishi`。户泽 GoRatings 921 的 zh H1 是 `户泽昭宣`，ko H1 是 `Tozawa Akinobu`，不能把后者当韩语实际用名。

`authoritative_pages` 是可复用索引，仍须取出指向的实际正文。例：中村勇太郎的 `ki000030` 是弟子黑泽忠尚的页面，中川新之的 `ki000036` 是高木祥一页面，影山利郎是官方出版物作者介绍；不能自动把这些 contextual mentions 升级成“本人官方假名与生日”。本地 `ishii-*` 文件也可能实际属于石井邦生，必须按 owner、完整原名和 URL 核对，不能按文件简称复用。

## 每人最多五分钟的生产办法

1. 先取已有本人锚点及真实各语言 Wiki／棋院／专业名录正文；找到身份一致的实际目标语名称即可采用，不为已找到的格补负面检索。原 source、locale、HTML/body hash、抓取时间、定位与 identity 依据保持原样。
2. JP 采用本人官方或日语条目真实汉字。EN 有可信英语名即采用；仅有日文页的罗马字字段时，把它真实标为已发表罗马化／读音依据，不把整张日文页改称英文网页或杜撰英语惯用名。必要的 EN 生成仍走主五既有流程。
3. KO 缺惯用名时先完成当前 registry 的有限 v1 检索；根据本人官方假名、姓／名分界与目标规范生成，逐名独立审核。Hepburn 拼法只作辅助，缺失音长、促音或边界时不猜。国立国语院的实际答复说明长元音与 `え＋い` 的处理有区别，足以说明不能逐英文字母机械替换；该答复不是整套转写表，真实批次需保存所用规则条文及相关定位。[国立国语院原文](https://www.korean.go.kr/front/onlineQna/onlineQnaView.do?mn_id=&pageIndex=1&qna_seq=313148)
4. CN/TW 优先采用实际中文来源。SGF PB/PW 或 default name 只可作原始写法和现有 owner 的线索，不能独自证明目标语惯用名、中文来源原名或新人物身份。若只能生成，保留日本官方原名／读音作为原语锚点，走既有完整主五负面闭环及逐人用字审核；不能借正字分支免检索。`筱/篠`、`励/勵/励`、`戸/戶/户`、`沢/澤/泽` 等必须按该人来源和目标地区审定，不运行一遍转换器就判完成。
5. 达五分钟仍缺原读音、目标语用例或 v1 闭环则记录精确缺口并切下一人；不要把限时届满填成 not_found，也不要以 GoRatings 404 为由放弃已存在的 Wiki、官方或历史专业资料。已满足的语言格可留存证据或按现有流程入库，但只有五格完整合格才更新该人完成状态。

## 最低交付 gate 与是否需要新代码

首批冻结 3 个 existing player owner 与对应五语输出／name preimage，来源 producer 与独立 reviewer 保持真实分离；同一官方锚点和规则可复用，各姓名的负面检索与完整输出仍分别签审。复用当前研究校验、碰撞、CAS、账本、撤销和 TEST→PROD 名称入库，验证已采纳名与 generated 都能实际显示、精确搜索，原 FK／identity／alias／rank／SGF 不变。没有新代码就不新增测试层或发布服务，只做现有 dry-run 与代表性真实读取。

**本轮不需要新的主五语通用代码规则。** 唯一先做的是有限日→韩生成规则记录和 3 人真实数据切片。若现有 importer 对这个合规包出现具体拒绝，先给出该拒绝及最小反例；只有确属证据表达缺口时，再做一个明确版本、固定 owner／原名／读音／输出的窄分支，配一组正例和来源／身份／碰撞／过期 preimage 拒绝测试、一次独立审查与 TEST→PROD。不得为绕过不完整检索而新增 primary reasonable-search 例外，或把 SGF/default 自动升格成正面姓名证据。已有 [2026-10-03 主五裁决](kifu-name-main-five-batch-policy-decision-2026-10-03.md) 中严谨来源原则继续有效；其中十一语范围以用户最新五语要求为准。

## 覆盖价值与计数

使用 `/tmp/kifu-player-next-ranked-live-20261006.json`，再排除 `/tmp/kifu-player-completed-prod-owner-ids-live.json` 的 615 个已完成 owner，当前文件剩 2,700 条。前十名为：筱原正美 469、林有太郎 459、曲励起 457、中村勇太郎 445、久井敬史 417、中川新之 397、户泽昭宣 397、影山利郎 393、榊原章二 380、染谷一雄 376，合计 **4,190 姓名槽位**；平均每人 419，约为每人 50–80 槽位现代棋手的 **5.2–8.4 倍**。完成 3 人试批后才按相同办法扩到这十人；复杂身份或无读音者跳过。

1,159 或 4,190 不能直接加到 both-players 或 full-five games：一局可能命中两名候选，且另一棋手／赛事尚未完成。root 提供的实时基准是 615/3,698 人、both players 92,694/173,025（53.57%）、full five 70,038（40.48%）；最终增量只取实际入库后报告。此次新增批准姓名数及新增完成数均为 **0**。
