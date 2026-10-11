# Ranks101–150：secondary122 有限规则扩展裁决

2026-10-03。独立决策者 `/root/secondary122_rule_decision_astra`。请求配置为 `gpt-6-astra / max`；本运行时可确认的身份为 GPT-6，未提供可独立核实的子型号证明。本备忘录只决定后续生产方法与范围，具体 rule、batch、candidate 新增审批均为 **0**；没有代码／数据库写入、commit 或 push。

**决定：先准备 85 格保持既有字符串的待审数据，37 格继续 HOLD。** 首批只需 16 个有明确源语范围的新规则记录和对应有限批次，可沿用现有两种渲染操作。日／韩俄乌转写另准备四个目标语言规则的证据；先处理下面列明的格式和音值问题，再决定其实际可渲染成员。不为保存未审字符串而扭曲 token 含义、修改已签读音或绕过渲染校验。主五语 `cn/tw/jp/ko/en` 的严格要求不变。

输入为[生产摘要](kifu-name-player-ranks101-150-remaining52-secondary172-pending-sol-2026-10-03.md)及受控包 `~/.local/share/kifu-name-audit/2026-10-03/player-ranks101-150-remaining52-secondary172-pending-sol-v1/`，manifest SHA `ea0899908b5e711908fb6b7918dd0bff646c06f66e0294c74aed4621862bda34`。已重算 manifest 与全部 70 个所列文件的字节／哈希。122 HOLD 实际涉及 30 个 owner：ja 7 人／36 格，ko 8 人／48 格，zh-Hant 2 人／12 格，zh-Hans 13 人／26 格。

**可复用的锚点边界。** 30 个现有完整已签 anchor 足以作为其原 owner、原 raw scope 内的已发表罗马字与已审分词输入；不用重新研究这 30 人身份。六个韩语特殊拼法还必须携带既有完整已签逐人 alias→Hangul 关系及 canonical hash；不能只解析 anchor 中提到旧 pending 记录的说明文字。`kim/young/myoung/hoon/hyun/sung/joon/nung/wuk` 不是由字符串可普遍反推的 RR。国立国语院允许既有专名拼法，并对个人姓名单独规定词序和分写；这支持保留实际发表的 Latin 拼法，不构成俄／乌转写表。[NIKL 原文](https://www.korean.go.kr/front_eng/roman/roman_01.do)

日本锚点可以支持本批已发表的 Hepburn 拼法；不能把无长音符号的别名声称为完整假名／音长记录。淡路修三已有官方 `アワジ シュウゾウ / AWAJI, Shuzo` 正文，目标规则必须明确如何处理长音。今村俊也与濑户大树现有主身份摘录是韩文资料，读音来自另签的日文／英文 GoRatings 对应；保留该真实来源链，不改写为已经检查了日本官方假名。若选择的目标规则需要别名未表达的区别，只补查受影响读音；不要求重查其余人。

**首批精确成员与规则。** 表中数字为 rank；完整 owner ref 为 `raw_ranks101_150_{rank}_20261003`。每行／每目标语独立记录，`entity_kind=player`，ja 使用 `hepburn-syllables-v1`，ko 使用 `rr-syllables-v1`，两种中文脚本使用 `pinyin-syllables-v1`。建议新版本前缀 `ranks101150-secondary122-finite-v1`，由源语、目标语与操作明确区分；不修改任何旧规则内容。

| source_lang → target | 操作／新规则数 | 精确 rank 集合 | 格数 |
| --- | --- | --- | ---: |
| ja → de | copy／1 | 102,115,128,134,136,139,144 | 7 |
| ja → es | copy／1 | 115,128,134,136,144 | 5 |
| ja → fr | copy／1 | 136,139,144 | 3 |
| ja → tr | copy／1 | 102,134,136,139,144 | 5 |
| ko → de/es/fr/tr | copy／4 | 各 118,127,132,133,135,137,149,150 | 32 |
| zh-Hant → de/es/fr/tr | copy／4 | 各 138,142 | 8 |
| zh-Hans → ru | syllable map／1 | 103,106,108,110,113,116,117,124,126,129,131,141 | 12 |
| zh-Hans → ua | syllable map／1 | 103,106,108,110,113,116,117,124,126,131,141 | 11 |
| zh-Hant → ru/ua | syllable map／2 | 各 142 | 2 |
| 合计 | **16** | 不含原包另外 50 个 pending members | **85** |

`copy` 指 `copy_roman_words_v1`，采用已发表罗马字显示的编辑规则，分类仍为 `transliterated`，不冒称四种目标语各有既定惯用名或发音完全相同。既有 Roman 姓名拼法保留原则可以复用；原规则的 source_lang／reading_system 及签名不能直接挪用，中文 LOC 拼音说明也不能成为日／韩音值依据。繁中两位采用已签普通话拼音，因此可新建明确 `zh-Hant` 范围的同类规则，无需把原锚点改成 `zh-Hans`。

中文俄／乌规则复用已留存的[俄语表](https://cidian.ru/palladius)与[2019 乌语学术表](https://chinese-studies.com.ua/pinyin_to_ukrainian_26.06.2019.pdf)，实际文件 SHA 分别为 `942c4f4b633939c1da9facfd29c00cfe4e04a549410bd3833f5681ed92a9b6ab`、`6ac441c5784986b9c127d8db94f83010e49807c0a8f177a6b2fa73391283c0ab`，本轮已重算一致。首批最小 token 集合：

- zh-Hans→ru，29 个：`cao chen cheng da ding er hao he jia ke li liao ling meng qing ran tai tao tong wang wei xie xin xing xu yang yu yuan zhao`。
- zh-Hans→ua，27 个：上述集合去掉 `ling tai`。`er/r — ер/р` 必须按正文拆取 `er→ер`，不能因自动提取漏项自行猜测。
- zh-Hant→ru/ua，各 3 个：`xuan yang zi`。

相对包内三组已签中文表的 token 并集，前两项分别新增 19／17 个实际 token；每个新规则仍须包含其全部 29／27 项，并审核对应正文。不能在渲染时隐式拼接多个旧规则、缺项回退，或给普通单音节附加只在某个邻接处才成立的符号。以上 85 格已用应用实际 `render_reading` 重算，输出逐字等于冻结 proposal；这只证明可表达性，不是规则或名称批准。

**七格明确例外，全部维持 HOLD。**

| rank / raw / target | 实测或正文发现 | 所需处置 |
| --- | --- | --- |
| 115 今村俊也 tr；128 伊田笃史 tr | copy 分别产生 `İmamura Toshiya`、`İda Atsushi`，原值为 ASCII `I` | 单独审定源拼法大小写保留方式及兼容操作，或取得目标语惯用名；不得把自动加点当作来源已支持。 |
| 129 孟泰龄 ua | 学术表 `ling→лін`，实际渲染 `Мен Тайлін`，原值 `Мен Тайлин` | 生产新的有来源候选及 before/after，再独立审；旧值不能保留为同表转写。 |
| 138 徐靖恩 ru | `jing+en` 普通拼接为 `Цзинэнь`，原值 `Цзинъэнь` | 审定音节边界规则；不得将普通 `jing` 永久改成带尾 `ъ` 的 token 来迁就一人。 |
| 138 徐靖恩 ua | 普通拼接虽等于原值 `Сюй Цзінень`，学术表另规定元音起始音节的边界分隔 | 单独审定 `jing/en` 分隔；渲染相等不构成语言正确证明。 |
| 145 邬光亚 ru/ua | 实际普通拼接分别为 `У Гуаня`、`У Ґуаня`；原值为 `У Гуанъя`、`У Гуан’я` | 分别审定边界处理；ua 还须解决表中 `guang→ґуан` 与原值 `Гуан` 的冲突。 |

**其余 30 格：目标转写规则的精确研究批次。**

| family | 精确 rank × target | 规则证据与当前问题 |
| --- | --- | --- |
| Japanese，14 格 | 102,115,128,134,136,139,144 × ru/ua | 本项目后续研究选 ru Polivanov、ua Fedorishyn 1994 两套分别有出处的体系；取完整表及长音、组合音节、词界说明，只提取本批实际 28 个 tokens。不能由俄文逐字替换生成乌文。现有 ua 的 `shi→сі` 与淡路的 `ji→джі` 至少需要统一体系核对。 |
| Korean，16 格 | 118,127,132,133,135,137,149,150 × ru/ua | 选 ru Kontsevich、ua Shchehel 2009 作为后续研究依据；沿用逐人 Hangul 对应，审核本批 20 个 alias tokens 的音值、姓／名词界、位置变化及连字符规则。Latin 别名自身不足以产生这两张表。 |

Japanese 实际 tokens：`a da ha hi i ji ka ki ko ma mi mo mu na ne o ra sa se shi shu su tai to tsu wa ya zo`。Korean 实际 tokens：`an chae hong hoon hye hyun ji jo joon kim min myoung na nung seo seong sung wuk yeong young`。二者均是本批有限输入，不批准通用罗马字逆转换。

日本 ua 的体系选择是本项目的编辑选择；[乌克兰科学院 2024 年研讨记录](https://www.oriental-studies.org.ua/uk/науковий-семінар-проблеми-академіч/)展示了不同方案及当时仍拟制定统一方案的事实，不能将该讨论冒称全国唯一强制标准，也不能用摘要代替尚待捕获的完整 Fedorishyn 表。[Shchehel 的原论文](https://movoznavstvo.org.ua/component/attachments/download/345.html)专门处理韩文姓名，规定给名音节间连字符，并说明从不统一的 Latin 拼法转成 Cyrillic 的困难。它是可用的完整研究依据，尚不是本批已签规则。

Korean 已有 10 个 proposal 存在当前渲染器的结构障碍：ru 的 133/135/137/149/150 在给名内部加空格；ua 的 133/137/150 加空格，118/135 加连字符。`syllable_map_v1` 禁止 token 输出包含这些分隔符，且 source anchor 的给名仍为一个 word。其余六格也需要音值证据。不要通过拆改已签 source words 或在 token 内夹带分隔符绕过校验。先冻结正确目标拼法及来源；仅对确定需要上下文／词内分隔的有限输入另提出最小操作扩展，或使用真正有来源的目标语惯用名路径。本轮不批准新操作，也不将未经核验的现有字符串视为必须保存的标准。

**生产、碰撞与签署顺序。** 先制作上述 16 个 unsigned rule contents 和 85 个精确 member intents；独立审批规则后，由 producer 绑定完整已签 rule／anchor／raw scope hashes、真实时间和实际 snapshot，重算并冻结 batch／candidate，再由独立审核者签署。已签规则内容改变必须换版本及完整 hash，不能回填签名或倒填时间。原 50 pending、52 direct、历史 103 direct 与 26 个 context exclusions 保持原边界。

本轮用实际 `normalize_alias` 对历史 103＋剩余 direct52＋secondary172 的 **327 格**重算：owner/lang 重复 0，跨 owner 同语规范化姓名碰撞 0。后续检查必须覆盖全部合并批次与真实已批准姓名 snapshot，保留现有 conventional 名优先及碰撞拒绝规则。任何同语同值跨 owner 冲突均保留整组待裁，不据此合并 alias／person；规则研究还须核对同一 alias token 在各 owner 是否对应不同 Hangul／假名或位置音值。当前冻结空 snapshot 不能证明线上无碰撞，真实库新鲜前像、schema、dry-run/apply 仍属后续原有闸门。

本轮交付的是 **85 格可优先生产、37 格有具体原因继续 HOLD** 的方法裁决。未批准任何译名、人物 ID、棋局 FK、生产导入或部署；未重复执行产品测试。
