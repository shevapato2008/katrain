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


## 2026-10-06 13:05 CST 来源补充决策：久井、户泽可走已发表名称采纳

**结论：前两人的 KO 已有足以准备既有 `source-adopted / conventional` 候选的正面来源，不再要求负面检索，不走 generated。** 此处批准来源适用性与准备路径，不签具体 candidate、不批准数据库写入。石井卫 KO 继续 HOLD；不能以规范生成的 `이시` 覆盖尚未解决的 Wikidata `이시이` 线索。

已读取 `/tmp/kifu-player-retired-pilot3-20261006/pilot-research.json`、source-index，实际解析 Namu、CiNii 及两位日本棋院本人资料 HTML，并核对这四份 HTML 的 SHA256 均与各自 metadata 一致。

### 已核对的正面正文和身份桥

- **久井敬史，3813：** Namu 镜像《제30회 혼인보전》实际韩语正文在“1975 年／最终预选／第 2 组”的参赛表中写有 `히사이 게이시`；不是搜索回显或页面导航。本人日本棋院 `ki001006.html` 实际给出 `久井　敬史`、`ヒサイ　ケイシ / HISAI, Keishi`、1920-05-13、职业经历及 1985 年退役。独立官方原名与完整读音、日本职业围棋及时代背景共同支持此处韩文指向该 owner。此同人判断是对两来源的交叉核对；不能写成 Namu 本身刊载了生日或日文汉字。对这条具体的已发表拼法，现有百科加独立官方身份佐证已经够用，无需再为同名格寻找另一个韩文来源。
- **户泽昭宣，4736：** 同一 Namu 韩语正文最终预选第 1 组写有 `도자와 아키노부`。CiNii `BA63657659` 同一书目实际列出韩文作者责任说明 `도자와 아키노부 지음`、日文作者 `戸沢, 昭宣 / トザワ, アキノブ`，以及 1991 年、首尔、韩国出版／正文语言代码 `kor`、原文语言 `jpn`、围棋死活题书与馆藏。本人日本棋院 `ki000027.html` 又给出 `戸沢　昭宣 / トザワ　アキノブ / TOZAWA, Akinobu` 和本人围棋著书背景。CiNii 这条已发表韩文作者署名及同页日文作者对应，是直接、具体的额外正面依据；无需增加“未找到惯用名”的检索。

### 诚实的 tier、role 和语种记录

1. Namu 来源登记为 **`tier=encyclopedia`**，role 明确是 **`community_encyclopedia_mirror / tournament_participant_mention`**，实际 host 为 `namu.moe`；不得称为 Wikipedia、官方棋院、专业围棋机构或已审核的本人传记。正文自己标注镜像并链接 Namu 编辑页。这里只批准这份捕获页面和这两个人名的有限用途，不给 Namu 全站名称自动背书。
2. Namu HTML 没有 `html lang` 属性，使用 **`observed_lang=ko, language_basis=reviewed_text`**；不要伪造 `html_lang`。`article_evidence` 保存真实标题、包含候选的完整表格片段及 passage SHA、抓取时间和 archive SHA。可把正文可见“最近修改时间 2026-08-03 00:11:51”及本次 2026-10-06 抓取快照写入 **edition**；没有取得真实 revision ID 就不填伪 ID。官方 `identity_corroboration` 使用两位各自日本棋院原正文和原始语言 `ja`，原名保留来源中的空格，再将展示空白整理与身份桥说明清楚。
3. CiNii 在现有枚举里保持 **`tier=reference`**，role 为 **`institutional_bibliographic_record / published_author_statement`**；它是机构书目证据，不为通过门禁改称百科或围棋机构。保留 **page/UI language=ja、field language=ko**、字段定位“書誌事項／著者責任表示”、书目 ID、出版年及原始 body hash。KO source check 的 `observed_lang=ko` 只指该实际检查的韩文作者字段，`language_basis=reviewed_text`，并显式附 `page_observed_lang=ja`、`evidence_scope=bibliographic_author_field` 等真实范围说明；绝不能把整页 html_lang 改成 ko。
4. **现有代码的实际限制：** `name_candidates.py` 不接受仅 reference tier 作为 conventional 的唯一正面来源。这不降低 CiNii 的证据价值，也无需为此改代码：本包已有 Namu 的合格 encyclopedia check，并各自带日本棋院独立身份佐证；CiNii 作为户泽的第二条 reference 正面 check／补充佐证即可。这样同时符合现有校验和真实来源角色。两人的 Wikidata 仅留 discovery 角色，不拿它代替已发表正文。

root 只需完成有限 registry 新来源登记、真实 article／identity 字段组装和候选常规独立签审，随后现有两库 dry-run→apply→verify；没有新增负面检索、新转写规则或代码扩展的必要。两人的其他 8 个语言格仍须按同批实际来源与当前 preimage 审核，不能用本段替代候选签名。此补充不阻塞正在执行的 C198 或其他已批准写入。
