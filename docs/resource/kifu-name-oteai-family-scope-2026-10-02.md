# Oteai 120 原文家族范围与例外盘点（2026-10-02）

本次由 `gpt-6-luna` 完成（用户请求的 `gpt-5.6-luna` 当前不可用）。这是一份原始值分流和来源范围研究，不是名称批准、候选签署、事件合并决定或十一语言完成声明；没有写生产数据库。

## 计数与可复现材料

在 `ucloud-v100 / katrain-ucloud-postgres-1 / katrain_prod_20260725` 以 `katrain_user` 只读查询 `kifu_albums.event ILIKE '%oteai%'`，命中 120 个原文、6,466 盘。SQL、逐原文上下文与来源路径样本、模式分流 TSV、网页原始响应体和 SHA-256 manifest 均在仓库外受控目录 `/Users/fan/.local/share/kifu-event-inventory/2026-10-02/oteai-family-scope/`；目录权限 `0700`、文件权限 `0600`。具体散列和文件字节数见该目录 `manifest.json`。

| 按原文格式分流 | 原文数 | 棋谱数 | 范围说明 |
|---|---:|---:|---|
| 精确 `Oteai` | 1 | 575 | 已关联现有生产事件 ID 22；分布在四个来源组（`19x19`、`CWI_1950_1978`、`CWI_History_Full`、`Go_Seigen`）。该关联是现状记录，不是本次重新批准。 |
| `Oteai YYYY`（严格四位年份） | 48 | 5,584 | 年值覆盖 1927–1978（有缺年）；27 个原文来自 `CWI_1950_1978`，21 个来自 `CWI_History_Full`。多盘实际日期字符串跨出标签年份，故年份先作为原标签结构字段审核，不以比赛日期重算。 |
| `Oteai YYYY, Spring/Fall` | 13 | 48 | 全部来自 `CWI_History_Full`；可将年份和季节作为分开的结构字段核验。 |
| `YYYY Oteai` | 4 | 6 | 反向年式，全部来自历史资料组；如 `1940 Oteai` 的棋谱日期实际落在 1941，须先核源条目。 |
| 无年份季节/场次标签 | 13 | 146 | 包含 Spring/Autumn/First/Second/Late Session，部分中文件路径来源不是年度 Oteai 目录；不能仅凭季节字样填补年份。 |
| 关西机构或支部标签 | 9 | 52 | 其中 2 个明写 `Kansai Ki-in`（33 盘），7 个写 `Kansai Branch/Betsuin`（19 盘）；须区分 1950 年后独立的关西棋院与更早的地区支部标签。 |
| 特别赛、加赛或编者描述 | 23 | 43 | 例：`Oteai winners' playoff series`、`…sponsored by Asahi Shinbun`、`Game to mark Takagawa's promotion…`、`Probably Oteai`。不得当作普通大手合年度标签。 |
| 其他标点或非标准值 | 9 | 12 | 例：`Oteai 1974?`、`Oteai{carriedoverfrom1942}`、`Oteai,7and8-danrankingtournament`；保留原值并逐项回查。 |
| **总计** | **120** | **6,466** | |

因此建议分三个队列：

- **可进入独立身份/结构审核：62 个值、6,207 盘**（精确 `Oteai`、48 个严格年式和 13 个带明确季节的年式）。审核仍需逐一确认来源机构/比赛年；不得据字符串自动写 alias 或把年季格式批准为显示名。
- **单独的关西机构身份审核：9 个值、52 盘。** 日本棋院大手合、关西棋院大手合和历史上的关西支部记录应分别解释；在审核决定父子、并行实体或别名关系前不互相挂接。
- **暂缓入赛事身份合并：49 个值、207 盘。** 包括无年份 session、特殊赛事/加赛描述、反向年式和其他异常值；先判断它们描述的是一项手合、某一届/季、加赛、旁支比赛还是具体对局注释。

## 赛事身份与机构边界

日本棋院官方沿革的日文时间线原文记载：1927 年“日本棋院大手合・東西対抗第一回開始”；1929 年“大手合東西制を廃止（春秋の定期手合開始）”；2003 年“大手合廃止、新昇段制度制定”。本次抓取原始页面 [日本棋院沿革（archive）](https://archive.nihonkiin.or.jp/profile/enkaku/index.html)，正文响应 SHA-256 `5cee9347cb336317bdc6cc52c198e6194f9521d38fd8dbacee32c19262804f82`，26,035 字节，见受控目录 `nihonkiin-enkaku-archive.html`。

作为历史边界补充，Kotobank 显示的《Britannica 国际大百科事典 小项目事典》“大手合”词条把大手合定义为日本棋院与关西棋院用于审查升段的对局制度，并写明关西棋院于 1950 年独立时仿照日本棋院引入、2003 年日本棋院废止、2004 年关西棋院废止。该页面是辞典转载，不是主办机构原始档案；本次只用它识别需要分开的机构与终止年份，不据此批准目录实体关系。抓取的 [Kotobank 大手合词条](https://kotobank.jp/word/%E5%A4%A7%E6%89%8B%E5%90%88-39406)原始响应 SHA-256 `0ee5e7e71798c99a3753ffe7d3b5581424457cf86605cf28571307e05e70024a`，209,903 字节，见受控目录 `kotobank-oteai.html`。小学馆《数字大辞泉》同页对词头给出读音 `おお‐てあい` 和释义“围棋中决定专业棋手升段的对局”。

这支持把**大手合作为升段对局制度/赛事身份术语**来研究；其普通年份、1929 后春秋场、组别和轮次首先是届次或对局组成信息，而不是看到一条就创建独立事件。但“日本棋院大手合”与“关西棋院大手合”跨越 1950 年后的机构所有权不同；制度同名不等于组织、赛季、目录实体天然相同。源数据还含 1927–1949 年“关西支部”表述，不能倒套到 1950 年独立后的关西棋院。核心正式用语有证据，具体原始值的身份链接仍需逐来源复核。

## 主要例外与来源/时期限制

- **赛季不带年份：** `Oteai,AutumnSession`（45 盘）、`Oteai,SpringSession`（42 盘）来自 `19x19`，两者各含若干 `1900-01-01` 占位日期；`Oteai Spring Session`（14 盘）含一个无日期值。CWI 历史资料另有 `Oteai Autumn Session`、`Oteai First/Second Session`、拼接写法及跨期 `heldover` 标记。这些原文可能指向多个年代，暂不能组成一个确定赛季。
- **关西支部及关西棋院不能混成一组：** `Kansai Ki-in Oteai` 26 盘来自 `CWI_1950_1978/KK/KKOteai/...`，而无空格的 `KansaiKi-inOteai` 7 盘来自 `19x19`，不能借用前者的目录证明。较早带空格的 `Kansai Branch Oteai`、`Kansai Branch Summer/Winter/Spring Oteai` 等来自 `CWI_History_Full` 的棋士个人目录；压缩写法 `KansaiBranchOteai` 3 盘、`KansaiBranchWinterOteai` 2 盘、`KansaiBetsuinOteai` 1 盘则来自 `19x19`。这些标签的具体机构隶属/赛制边界需要历史赛程或棋院史料核验，不能只因英文标签含 Kansai 就指向独立后的关西棋院。
- **赞助/纪念/资格赛描述：** `1936AutumnOteaiWinners'PlayoffSeriessponsoredbyAsahiShinbun`、`AsahiShinbuntournamentfor1935AutumnOteaiwinners`、`Kansai Branch Oteai Select Tournament sponsored by Sunday Mainichi`、`Great relay game to commemorate 15 years of the Oteai`、`Special tournament to select participants in Oteai` 均可能是伴随赛、晋级/获奖者加赛或纪念对局，不能等同于常规大手合本体。几个 `playoff series` 值没有 `date_played`；另有 `1936Autumn...` 记录日期 `1900-01-01`。
- **特殊/不确定批注：** `Oteai,7and8-danrankingtournament`、`Oteai 1949 Special`、`Oteai 1939, Later`、`Oteai{carriedoverfrom1942}`、`Oteai 1974?`、`Probably Oteai` 需保留问号、跨年、组别或来源不确定标记。日期字段中共有 34 盘为空、33 盘为 `1900-01-01` 占位、3 盘含问号；日期文本格式混合，不能据其计算制度年份边界。

## 后续独立审核问题

1. 62 个核心候选值逐条对照 CWI 原始目录及对应棋院历史：它们属于日本棋院的“日本棋院大手合”、关西棋院体系，还是只是在数据来源中泛写 Oteai？年份是竞赛届年、开赛年还是源档案年份？
2. 对 `Oteai YYYY, Spring/Fall` 和无年份 session 值，分别核实季节是否常规赛季、因战争/改制/延期出现的特殊场次，保留 held-over 与日历日期错位。
3. 对关西标签，分别确认独立前“关西支部”的组织含义、1950 年后的 Kansai Ki-in 专属大手合和两棋院交流赛；只有明确制度/组织关系后，才讨论是否挂到同一上位赛事概念。
4. 把所有 playoff、sponsored、select、commemorative 和 probable 值与逐盘来源正文/SGF 事件注释核对，决定应归作副赛事、特定对局说明，还是低可信来源标签。
5. 对 `1900-01-01`、无日期和问号日期先确认来源导入约定；不把占位日期解释成赛事举行于 1900 年。

以上结果足以把精确和年/季值交给独立身份审核，并把机构及描述型边界清楚留待判断；不支持批量归并 120 个原文，也不证明十一语言覆盖完成。
