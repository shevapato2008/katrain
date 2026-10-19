# 大手合 ID 22 × ua：闭环复核状态

2026-10-02 复核；产品语码 `ua`、来源语言 `ja`。**不批准有限负面闭环、生成显示名或数据库写入。**现有 [16 项无 owner 范围模板](kifu-name-oteai-uk-manifest.json)仍为 `pending_review`；来源清单 [`.3`](kifu-name-source-registry-2026-10-02.3.json) 的 `ua.complete_for_negative_claims` 仍为 `false`。本次只审实际可读响应，不把索引、俄语正文或 HTTP 错误当作乌克兰语未命中。

## 本次实际检查

对现有模板的四个 UFGO 指定页、论坛主题 824 两页、九个乌克兰维基 API 查询、Wikidata Q4335071 `uk` 字段逐项请求；另补做此前未完成的九个 `https://ufgo.org/?s=...` 原生搜索。完整逐项 URL、UTC 抓取时间、HTTP 状态、响应和正文 SHA-256、正文摘录、API 命中数与续页字段保存在权限 `0600` 的 `/Users/fan/.local/share/kifu-name-audit/2026-10-02/oteai-uk-observations-2026-10-02.json`，文件 SHA-256 为 `580011a93d157c34a28a776a4b517462c9d8392cc29cbd31fc5a1cf99a669dd0`（此文件没有提交，且不是获批研究记录）。HTML `body_sha256` 是 BeautifulSoup 所取主要正文的 `get_text(' ', strip=True)` UTF-8 哈希；API 正文哈希是排序键、紧凑 JSON 的 UTF-8 哈希。原始响应字节另有 `response_sha256`。该提取方式与正式研究记录尚未独立核对。

| 检查 | 观察 | `response_sha256` | `body_sha256` |
|---|---|---|---|
| UFGO `pro-go-1` | 200；乌克兰语主文，未见对应赛事 | `2c2659cdde6e6439120210441baf1faaba86186aee4a8f7360170542948a6eb3` | `011e57324012f13f132f5bb928d5e54880b029044eaf4f715115774eb5608144` |
| UFGO `pro-go-2` / `pro-go-3` / `go-literature` | 200；前两篇俄语正文，书目以俄语为主，不能充当目标语正文 | `33af92b8d15f…` / `6fd62b29ccd6…` / `2ecf10d19941…` | `091c465dc3fb…` / `9ad6042aff8c…` / `5284aeb20070…` |
| 论坛 824 页 1 / 页 2 | 200；1 页有 `Отеаи`、`Отэаи`、`Oteai`，分别属于俄语论述/英语引文；2 页无相关乌克兰语用例，导航到此终止 | `f491a37c8104…` / `8d9382cd9806…` | `c85e1a286178…` / `48bdc41cd271…` |
| 乌克兰维基精确 1–6 | 六项各 200、`totalhits=0`、无续页；不能推出站外无惯用名 | 逐项见暂存观察 | 逐项见暂存观察 |
| 乌克兰维基描述 7 | 200、3 个无关结果、无续页 | `84778d28377d42a6bc66c778e576bca3c81d030fe5c9b08d900edc7e513176e1` | `2104960c2d27665969fb5a1acbd059d602e929ba45bd611cb18aa588cb3e9926` |
| 乌克兰维基描述 8 | 200、`totalhits=97`；只返回首 10 条及 `sroffset=10` 续页，**未完成** | `d707ea227a2caa44d9b768d02f3ee5b5886070050dd2acedd990a88455ac749b` | `386352101e4c0e792b5a0f88418dcb58369f08975c35a2485ac86187c79c5260` |
| 乌克兰维基描述 9 | HTTP 429，再试仍 429；**未完成** | 首次限流体 `159eeb1464ed…` | — |
| Wikidata Q4335071 | 首次单独请求 200，440 字节：`labels={}`、`aliases={}`、无 `ukwiki`；批量复抓 429、再试 403，须固定一次可复核响应 | 首次 `6af93ea4452f156e67316005eba51a92afd26ab679d21c21e11de899f1e49aa8` | — |

九个 UFGO 原生查询依模板所列顺序，均为 HTTP 200、`#primary` 明确显示“Нічого не знайдено”，无结果分页；每个页面的主要正文哈希相同：`9170f8f0ea56b7c95c0208ee2eefa67ec20595d221efccd9c307602fc9c1e6ab`。逐页原始响应哈希依次为 `34eeb9de7658…`、`13639f4d3b81…`、`b55634065745…`、`d091f8004e8a…`、`abdcfd6e679c…`、`35306ada212e…`、`9861d4915aab…`、`0da7e6f9ace2…`、`a49203cb3a72…`；完整值在暂存观察中。这只是 UFGO WordPress 搜索覆盖的内容，不证明论坛数据库或线下出版物已搜尽。论坛页的站点 UI 为乌克兰语，不改变命中帖文的俄语/英语实际语种。

## 必须修正的范围与词形问题

现有模板把乌克兰维基描述查询 8 固定为 `page_count=1`、`pagination_exhausted=true`；实际响应有续页，故该范围义务与事实冲突。须先修订模板并重新计算 `scope_template_sha256`，将全部续页作为检查义务；随后补查查询 9 和可复核的 Wikidata 字段，逐项保存完整目标语正文、哈希、语言依据、已知论坛线索的 `rejected_leads`，再由另一审核者签署 owner `{kind:"event",id:22}` 的 `scope_sha256`、`evidence_sha256` 和研究哈希。当前不能沿用原模板哈希 `489b5059…` 直接批准。

词形也需独立改判。[日本棋院](https://archive.nihonkiin.or.jp/juniorclub/history/history07.htm)给出 `大手合（おおてあい）`；[小学馆《数字大辞泉》](https://kotobank.jp/word/%E5%A4%A7%E6%89%8B%E5%90%88-39406)记 `おお‐てあい`，[《日本国語大辞典》“合い”](https://kotobank.jp/word/%E5%90%88%E3%81%84-1999898)明确 `あい` 是动词 `合う` 连用形名词化。[Дементьєва、Вознюк 2023，PDF 页 190–191](https://www.philol.vernadskyjournals.in.ua/journals/2023/5_2023/32.pdf)把词基内 `/ai/` 与动词、形容词、动名词词素交界的 `/a.i/` 分列，后者用 `аї`；这使[先前词形备忘](kifu-name-oteai-ua-wordform-research.md)仅据“同一词基”倾向 `-ай` 的推断不稳。不能仅由字形 `合い` 自动断定整名该按哪个转写类别；需日语构词与乌克兰语转写专家复核。[Дементьєва 2024，PDF](https://www.vestnik-philology.mgu.od.ua/archive/v66/12.pdf)又记录长音省写的常见实践与作者主张的双写路径；本轮取得该 PDF 字节并核读（SHA-256 `11233679bc9d9154c23aed3d7482bf9ac81620ae365139cb5b4b47a713884e7e`）。2023 PDF SHA-256 为 `2c264d8569a4db2378536e216b9f41b085b4fe8f44e7db671f92ffed0e3229d2`。两篇论文均未提供本赛事的乌克兰语用例，且是学术提案，不是已确立的赛事专名标准。暂不提出任何生成名。

结论只限于本次可读页面：未取得合格的乌克兰语赛事惯用名正文；负面闭环因续页、限流及独立审核未完成而保持待审。年份、春秋届次仍须按原始赛事值另审。
