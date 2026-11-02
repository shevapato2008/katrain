# 棋谱库五语名称与赛事分词器调研

日期：2026-10-30。范围：只读官方文档、上游仓库与发行目录；本文件是方案依据，未运行 Elasticsearch、未下载镜像或插件 ZIP、未建索引、未调用本地或远端 `_analyze`、未改业务库。原实施继续暂停。原主计划的两轮 Astra Approved 不覆盖本次新增的分词器和检索语义选择。

## 结论

当前 ES 计划**没有使用 IK，也没有配置语言分词器**。Task 2.6–2.7 使用 `keyword` 精确词、独立 `wildcard` 字面子串字段和固定日期排序。这适合保留已有的完整姓名精确优先、部分姓名/赛事字面匹配，但还不是赛事多关键词搜索设计。

不能仅凭“五语”就安装五套分词器，也不能把通用中文分词器称为围棋人名的最佳选择。应先区分四类目标；精确身份仍靠 `keyword`/ID，分词只为明确需要的赛事多词检索增加。若用户只要原有精确与子串能力，当前无插件路线足够，增加 IK 没有已证明的收益。若用户需要“赛事名称中多个关键词可以不连续、顺序可变”，建议在原字段旁增加赛事 `text` 检索字段，再用真实语料选择分析器。

候选建议是：中文简繁共同比较 **IK 与 ICU**（内置 CJK 为无需插件的对照，SmartCN 作为简体专用候选）；日文比较 **Kuromoji 与 ICU/CJK**；韩文比较 **Nori 与 ICU/CJK**；英文优先 **standard**，不默认词干化。这里的“优先比较”是工程建议，不是已经测出的胜负。ICU 只有一个插件，cn/tw 可共用一个分析链；不是五套独立平台。

## 1. 四类目标不能混在同一种分词里

| 检索目标 | 例子 | 合适的主机制 | 分词器边界 |
|---|---|---|---|
| 完整姓名精确、定位同一棋手 | `王星昊`、`Wang Xinghao`、`신진서` | 已整理五语名称 → 有资格的身份/词条 → `keyword`/ID；保留原精确优先和零盘行为 | 不能改成人名词元 OR/BM25，否则同姓、相同音节或部分英文名会扩大集合 |
| 部分姓名、前缀或任意子串 | `星昊`、`Xing`、`진서` | 维持原 literal 子串规则；若将来单独明确前缀语义才选 prefix | 词语分词不保证任意字符子串；前缀与子串也不是同一功能。不要为了部分姓名把全字段改成 ngram |
| 完整赛事名、已批准等价称呼 | 某届赛事完整名称 | 保留 `event_terms` 的 `keyword`/赛事身份及已授权范围；子串分支照旧 | 分词不能取代赛事身份或名称资格，也不应使已确定的 exact event 自动扩成所有含某个通用词的比赛 |
| 赛事多关键词/自然语句 | `三星 世界 大师`、`Changqi Final`；更进一步的“找申真谞参加的世界赛决赛” | 多关键词可用新增赛事 `text` 字段；需定义 AND/OR、短语、字段范围和与旧分支关系 | 分词解决词元边界；完整自然语句中的棋手/赛事/阶段/日期意图并非仅安装分析器即可解决 |

Elastic 的 `term` 是精确词查询；`match` 会分析输入，默认词元 OR，可显式 AND。因此“换上 IK”本身没有回答组合词语义。[term](https://www.elastic.co/docs/reference/query-languages/query-dsl/query-dsl-term-query)、[match](https://www.elastic.co/docs/reference/query-languages/query-dsl/query-dsl-match-query)。

## 2. 五语候选与建议

下表只讨论**需要分词的赛事 text 字段**；所有语言的人名精确字段都继续使用 keyword/身份键。

| 名称语言 | 第一轮候选 | 官方能力与主要局限 | 当前建议 |
|---|---|---|---|
| cn 简体中文 | IK、ICU；CJK 对照，SmartCN 补充 | IK 有自定义词典和粗/细切分；ICU 提供 Unicode 归一与中文词边界；CJK 是字 bigram；SmartCN 明确面向简体中文/中英混合 | 若要赛事多词，IK 与 ICU 用同样真实赛事比较；不预先宣布 IK 胜出 |
| tw 繁体中文 | ICU、IK；CJK 对照 | 简繁是中文的字形差异；SmartCN 文档只保证简体目标。IK README 不承诺自动简繁互通，不能据此猜繁体效果 | 可与 cn 共用分析链，但必须测试繁体语料；已有 cn/tw 等价名先提供召回，不默认再建简繁转换副本 |
| jp 日语 | Kuromoji；ICU/CJK 对照 | Kuromoji 有日语形态词典、用户词典、复合切分；默认 analyzer 还带基本形、词性/停用词和词干处理，可能影响专名 | 多词赛事优先评估 Kuromoji；若 ICU 已足够则不为语言数增加插件 |
| ko 韩语 | Nori；ICU/CJK 对照 | Nori 明确使用韩语形态词典，支持自定义名词及复合词分解；ICU 的一般词边界不等于 Nori 的形态分析 | 多词赛事优先评估 Nori；姓名整词由 exact 保护，赛事复合词测试 `none` 与 `mixed` 的收益/多余词元 |
| en 英语 | standard；english 仅对照 | standard 默认保留停用词且不做词干化；english 增加停用词与词干处理，可能改变专名和赛事短标题 | 先 standard；除非样本证明词形召回有必要，不引入 english |

这些候选是依据官方功能而做的选择，未测量各自的召回率、误召回率、速度或磁盘；“最适合当前数据”必须由下文的小样本验证决定。

### 2.1 中文候选细看

| 机制 | 能提供什么 | 不能直接提供什么 | 额外维护 |
|---|---|---|---|
| keyword | 整串保存为精确词，适合人名/赛事词条和已知等价名 | 自然语言词边界、词序无关组合；任意子串另走已有字段 | 无语言插件；保持原比较规则，不能擅自把 NFKC/casefold 扩大到所有 exact |
| 内置 CJK | 对中日韩字符形成相邻 bigram；不依赖围棋词典 | 真正的词语/实体识别；简繁等价和翻译；不能把它误称为完全相同的原 literal 子串 | 无额外插件；默认链含英文 stopwords，混合赛事名仍须测试 |
| ICU | 跨文字 Unicode 处理、中文/日文词典词边界；适合统一对照 | 围棋领域名称词典、身份等价；默认 ICU 归一不应被当作简繁翻译 | 一个官方插件；按需配置 transform 才能显式转换简繁，不能与默认 normalization 混为一谈 |
| SmartCN | 官方描述为对简体中文或中英混合文本做概率切分 | 文档未承诺繁体中文或围棋专名最佳表现 | 一个官方插件；不以它代表整个 cn/tw 双字形需求 |
| IK | `ik_smart` 与 `ik_max_word`；自定义主词/停用词典，可补围棋词 | 不保证未登录人名整词，不保证繁体归一/跨语言翻译，不保证粗切分是细切分的子集 | 第三方插件，锁定 ES 对应包；先用静态小词典，不新增远程热更新服务 |

CJK 的核心是 bigram，官方也建议用自己的文本/查询比较 ICU，未给出通用胜者。[CJK bigram](https://www.elastic.co/docs/reference/text-analysis/analysis-cjk-bigram-tokenfilter)、[CJK analyzer](https://www.elastic.co/docs/reference/text-analysis/analysis-lang-analyzer#cjk-analyzer)。SmartCN 的明确目标是简体中文。[SmartCN](https://www.elastic.co/docs/reference/elasticsearch/plugins/analysis-smartcn)。

IK README 展示 `ik_max_word` 产生更多重叠组合、`ik_smart` 较粗，并明确两者不是包含关系。是否采用常见的“索引 max_word、查询 smart”需要样本证明，不能只抄示例。词典是领域补充，不是把每个棋手名复制进分词词典的理由；已有 exact 字段已解决整名身份。[IK 官方维护仓库](https://github.com/infinilabs/analysis-ik)。

### 2.2 ICU 的三个不同功能

1. `icu_tokenizer` 是词边界处理；`icu_analyzer` 默认组合 normalizer、tokenizer、folding。Unicode normalization/case folding 与中文简繁转换不是同一个承诺。[ICU tokenizer](https://www.elastic.co/docs/reference/elasticsearch/plugins/analysis-icu-tokenizer)、[ICU analyzer](https://www.elastic.co/docs/reference/elasticsearch/plugins/analysis-icu-analyzer)。
2. `icu_transform` 可显式选 Unicode transform；ICU 上游列有 Simplified/Traditional 转换。这是可选字符转换，不是王星昊 → Wang Xinghao 的已批准英文姓名翻译，也不能替代现有五语称呼表。[Elastic transform](https://www.elastic.co/docs/reference/elasticsearch/plugins/analysis-icu-transform)、[ICU transforms](https://unicode-org.github.io/icu/userguide/transforms/general/)。
3. Elastic tokenizer 文档概括称支持中日韩等语言词典；但 ICU 自己的词典边界清单列出中文、日文等，未列韩语；Lucene 当前源码把 Han/Hiragana/Katakana 合并的路径交给 CJK dictionary break iterator，Hangul 走默认规则。不能因此承诺 ICU 与 Nori 的韩语形态/复合分解能力相同；具体选定 ES/Lucene 版本仍要 `_analyze` 确认。[ICU boundary analysis](https://unicode-org.github.io/icu/userguide/boundaryanalysis/)、[Lucene 当前源码](https://github.com/apache/lucene/blob/main/lucene/analysis/icu/src/java/org/apache/lucene/analysis/icu/segmentation/DefaultICUTokenizerConfig.java)。这里对源码行为的解释是推断，不是 9.5.5 token 实测。

### 2.3 日文、韩文与英文不能只换名字

Kuromoji tokenizer 默认使用 MeCab-IPADIC，可追加用户词典；其默认 analyzer 还会移除部分词性和停用词、做基本形及词干转换。因此应把 `棋聖戦`、`本因坊戦`、数字届数、选手名与全半角混排放在样本中，不能假设安装后专名自然保真。[Kuromoji tokenizer](https://www.elastic.co/docs/reference/elasticsearch/plugins/analysis-kuromoji-tokenizer)、[Kuromoji analyzer](https://www.elastic.co/docs/reference/elasticsearch/plugins/analysis-kuromoji-analyzer)。

Nori 使用 mecab-ko-dic；`discard` 默认拆复合词并丢原形，`mixed` 同时保留，`none` 不拆；可追加自定义名词。`mixed` 只是候选，可能增加词元和误召回，不能直接当最佳配置。[Nori tokenizer](https://www.elastic.co/docs/reference/elasticsearch/plugins/analysis-nori-tokenizer)、[Nori analyzer](https://www.elastic.co/docs/reference/elasticsearch/plugins/analysis-nori-analyzer)。

standard 默认 stopwords=`_none_`，保留不同词形；english 带英语 stopwords 和 stemming。对于 `Go Seigen`、`Samsung Cup`、`Best-of-3` 一类姓名/赛事短词，保留原词更容易解释，词干和删词应有样本收益才启用。[standard](https://www.elastic.co/docs/reference/text-analysis/analysis-standard-analyzer)、[english](https://www.elastic.co/docs/reference/text-analysis/analysis-lang-analyzer#english-analyzer)。

## 3. 简繁、翻译和 UI 语言

cn/tw 是当前产品的两个名称显示字段，底层同属中文而字形/习惯称呼不同；不是因为有两个字段就必须两种 tokenizer。现有 PG 已整理原名和五语姓名、赛事名，可将合资格的等价称呼放进相应搜索投影，保留 source 和身份范围。分析器本身不会知道 `王星昊` 与 `Wang Xinghao` 属于同一棋手；拉丁转写也不能当作权威别名。

`lang=en` 表示显示语言，不能把搜索限制为英文：英文 UI 输入 `王星昊`、韩语 UI 输入日文赛事名，都应进入跨语言原词/等价名匹配。若增加赛事 text，应对明确的候选语言字段查询，各字段用自己的 search analyzer，再合并满足条件的 album；不要把 UI 语言当成唯一 analyzer。混合输入如 `삼성 Cup` 是否允许词项跨语言字段拼接，是另一个需定义的语义，不能靠“multi_match 默认设置”暗中决定。

## 4. ES 9.5.5 与插件版本证据

候选 ES patch 仍以主计划待核定的 9.5.5 为准。以下是**发行/文档证据**，均不等于已在目标镜像安装或启动成功。

| 组件 | 9.5.5 对应证据（2026-10-30） | 当前验证层级 |
|---|---|---|
| keyword / standard / CJK | ES 内置组件，无单独语言插件包 | 官方功能已核；未运行 ES |
| analysis-icu | 官方插件页直接列出 `analysis-icu-9.5.5.zip`；对包 URL 做 HEAD 得 200、application/zip、13,755,403B | 包端点/版本存在；未下载和安装 |
| analysis-smartcn | 官方插件页直接列出 `analysis-smartcn-9.5.5.zip` | 官方对应发行链接存在；HEAD 本轮超时，未安装，超时不能记为不支持 |
| analysis-kuromoji | 官方插件页直接列出 `analysis-kuromoji-9.5.5.zip` | 同上 |
| analysis-nori | 官方插件页直接列出 `analysis-nori-9.5.5.zip` | 同上 |
| 第三方 IK | 维护者 stable HTML 目录明确列出 `elasticsearch-analysis-ik-9.5.5.zip` 和 `.zip.sha512`；README 所给安装入口换为 `/9.5.5` 后 HEAD 为 200、application/zip、4,619,688B | **对应发行包存在**；未下载、核 descriptor/哈希、安装或实测分词。不能说只到 README 示例 9.1.4，也不能说已经验证可部署 |

对应发布来源：[ICU](https://www.elastic.co/docs/reference/elasticsearch/plugins/analysis-icu)、[SmartCN](https://www.elastic.co/docs/reference/elasticsearch/plugins/analysis-smartcn)、[Kuromoji](https://www.elastic.co/docs/reference/elasticsearch/plugins/analysis-kuromoji)、[Nori](https://www.elastic.co/docs/reference/elasticsearch/plugins/analysis-nori)、[IK stable 发行目录](https://release.infinilabs.com/analysis-ik/stable/)、[IK 9.5.5 安装入口](https://get.infini.cloud/elasticsearch/analysis-ik/9.5.5)。本轮只读取小型目录 HTML、文档及 HTTP HEAD 元数据；后一次目录探测超时不抹去此前成功读取的明确条目。

Elastic 说明多数插件需匹配包括 patch 的运行版本；使用 stable plugin API 的文本分析插件有同 major 兼容例外。这里采用官方对应 build 及 IK 自身“版本匹配”要求，不假设任意 9.x ZIP 通用。日后升级同时核所选插件包、校验和、安装/启动；不能把 main 分支文档当作任一 patch 的运行证明。[插件版本检查](https://www.elastic.co/docs/reference/elasticsearch/command-line-tools/elasticsearch-plugin)。

## 5. 当前主计划已经满足和仍欠缺的内容

| 项目 | 当前计划结论 | 本次是否应改 |
|---|---|---|
| 完整人名精确优先、ID、同名授权和 raw scope | Task 2.4–2.6 已设计 | 保留，禁止用 text/BM25 替换 |
| 赛事精确分类/选择范围、原 literal 子串 | 已覆盖，仍需冻结 oracle 实证 | 保留，不因分词器扩集合 |
| 五语已整理名称与其余 UI 语言英文 fallback | Task 1.5、2.1–2.4 已列 | 应补显式用例证明“搜索语言不受显示语言限制” |
| 多个不连续/乱序赛事关键词 | 未定义，keyword/wildcard 不自动实现 | 仅在用户确认需要后增加独立 text 字段和明确组合规则 |
| 任意完整自然语句理解 | 不在当前方案 | 不把它暗中等同于“多词分词”；不追加 NLP 平台 |
| 分词器/词典版本、真实 token、兼容测试和分词额外磁盘 | 原计划没有，因为原路线无插件 | 若选语言 text，则补本次所需的小样本和发布核验，不新增全面评审平台 |
| `date_sort`、排序、总数、分页与 preview | 原契约明确，包括 `1926-00-00` | 保持 keyword 日期、原顺序及精确总数；不让 relevance 改列表排序 |

## 6. 最小字段建议：保留 exact，按需增加赛事 words

这是条件方案，未执行 mapping 修改。

| 字段用途 | 建议形态 |
|---|---|
| 当前人名/赛事资格与精确过滤 | 保留既有 `player_terms` / `event_terms` keyword、身份键与范围键 |
| 原有任意字面子串 | 保留原独立 literal/wildcard 字段和 escape 规则；不改变字符比较分支 |
| 需要多词赛事时的扩展 | 优先复用五语原赛事值，例如 `display.<lang>.event`，用keyword主字段附`.words` text multi-field，不在_source再复制一份event_search正文；按补充计划将该显示层改为显式可解析mapping，未参与检索的姓名/来源仍不额外索引 |
| analyzer 数量 | cn/tw 可以共享同一实际链；jp/ko 仅在语言插件相对基线有收益时专用；en standard；试验候选不全部留进生产 |
| 非检索显示 payload | 仍只保留一份 `_source` 的已整理显示对象。原 `enabled:false` 对象内的字段不会索引；新检索字段必须位于独立启用的明确路径 |

multi-field 可以让同一个字符串同时有 exact 与 text 版本，且不增加第二份 `_source` 字符串；它仍然有额外倒排占用。索引已存在时追加字段不会自动填充旧文档，所以应在首次建索引前定下最小方案；若之后才新增，须计量一次有界重建/更新成本。[multi-fields](https://www.elastic.co/docs/reference/elasticsearch/mapping-reference/multi-fields)。

若用户选择多词，建议先定义为“同一条已整理赛事名称中全部查询词匹配，各语言字段 OR”，保留已有 exact 分类优先，词项 AND，仍固定日期/id 排序；`match` 不使用默认 OR 的宽泛召回。这个定义只是待确认的最小选项，尚未获用户确认。混合字段 AND、棋手+赛事组合与完整自然句不顺带加入。不同 analyzer 的 `multi_match` 不能想当然视为跨语言统一词袋，官方明确区分 field-centric 与 cross-fields 行为。[multi-match](https://www.elastic.co/docs/reference/query-languages/query-dsl/query-dsl-multi-match-query)。

不新增全文 SGF、不给所有人名/metadata 做 ngram、不同时保存 IK/ICU/CJK/SmartCN 的所有生产倒排、不引入新字典平台或假设中的改名删除流程。少量更名继续查询前显式映射成有限精确 OR。

## 7. 恢复实施后才执行的小样本验证

本轮没有 token 或性能实测结果。现有真实 frozen-main-24 公开响应已由 Root 只读抽取以下短语；不复制私有 oracle、SGF、secret 或正文。

| 语言 | 真实公开名称样本 | 真实公开赛事样本 |
|---|---|---|
| cn | 申真谞、王星昊 | 第12届国手山脉杯世界赛半决赛 |
| tw | 柯潔、黨毅飛 | 第6屆嵊州杯中國王中王爭霸賽總決賽 |
| jp | 井山裕太、一力遼 | 52期日本天元戦挑戦手合5番勝負第2局1-0 |
| ko | 신진서、리웨이칭 | 제12회 국수산맥배 세계전 결승 신진서 VS 리웨이칭 |
| en | Dang Yifei、Gu Zihao | 20th Changqi Cup China Professional Go Championship Final Best-of-3 Game 2: 0–1 |

另补以下**人工测试短语**，用于边界测试而非宣称数据库已收录或自动归为同人：`吴清源`、`吳清源`、`王星昊`、`Wang Xinghao`、`Go Seigen`、`三星杯世界围棋大师赛`、`棋聖戦`、`本因坊戦`、`삼성화재배`、`Samsung Cup`。加入全半角、空白、连字符、英文大小写，以及少量围棋术语如 `本因坊`、`挑戦手合`、`국수산맥배`、`Best-of-3`。

在用户恢复授权后，只在既有计划的一个隔离候选中做有界检查：

1. 固定 ES patch、每个候选插件发行版/校验和、词典内容和分析链；先安装/启动核验，再对同样样本 `_analyze`，记录 token、position、offset。现在不执行。
2. 人名 exact 必须完整保真：五语整名、已授权等价名、同姓或部分英文名的负例；部分姓名与特殊字符子串对照原契约，不能拿 text 的偶然命中证明子串兼容。
3. 赛事多词在确认语义下对照“必须命中/必须不命中”样本；至少覆盖不连续词、词序变换、一个通用词导致的误召回、简繁、日/韩复合词、全半角和数字轮次。只比较 tokens 好不好看不足以证明检索质量。
4. 同一已确认棋手/赛事精确输入用五种 UI 语言显示，应命中相同身份与记录；英文 UI 输入中文也应如此。原generic/raw若有明确语言条件的fallback，单列当前集合与预期，不为统一ID而偷偷改其资格范围。混合输入如 `삼성 Cup` 记录为待定语义，不偷偷扩行为。
5. 同样 1000 盘样本分别记录仅 exact/literal 与所选赛事 text 增量的 store、terms/词元数量、导入 CPU/耗时/RSS，以及代表查询完整 HTTP 延迟；沿用主计划磁盘停止线。不得在未测量前声称某分析器更快、更省或100QPS已达标。

保留有明显质量收益的最少分析链；如果赛事 text 没有新增已确认需求或不能证明收益，则继续现有 keyword/wildcard 方案。原日期/分页/total/preview、资格范围与生产100QPS验收不因分析器研究改变。

## 8. 需要用户明确的检索语义

当前唯一会改变实施范围的选择是：**继续完整姓名/赛事精确优先和原字面子串，还是额外支持赛事名称的多个不连续关键词组合？** 后者还应确认组合默认全部词命中还是任一词命中；建议全部词命中且同一赛事名内组合，减少通用词误召回。可使用 `三星 世界 大师` / `Changqi Final` 这类短例确认，不要求用户选择具体插件品牌。

在答案明确前，两条路线都保留在研究中，不默认启用 text，也不默认“无 IK 就不符合要求”。此文完成的是资料核对与候选筛选；新语言方案尚未经过原两轮 Astra 审批，也尚未完成目标运行时验证。
