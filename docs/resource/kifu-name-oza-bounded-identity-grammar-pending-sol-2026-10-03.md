# Oza 系列／预选：有限身份与语法候选范围（待独立核查）

日期：2026-10-03。状态：**PENDING，`write_ready=false`**。本记录只提出研究顺序和有限候选范围；没有批准名称、规则、身份链接或写入。未改代码，未写生产／测试／克隆数据库，未部署或改 strict flag。

## 身份与阶段边界

目标系列是日本职业围棋「王座戦」。官方资料列出日本经济新闻社、日本棋院、关西棋院及创设年 1952；须排除将棋、学生赛和其他地区同名赛事。[日本棋院历史资料](https://archive.nihonkiin.or.jp/match/oza/)

系列身份与阶段展示分别核查：`Oza` 的拼写／期号本身不证明「本赛」。冻结 CWI 的 1,356 局中，RO 明示 preliminary 的有 **1,313 局**，其余 **43 局**为数字、Round 或 semifinal 等尚不能确定阶段的值。保留 RO 原文；不得把整批渲染为本赛或挑战手合。官方现代「予選 B・C／本戦／挑戦手合」结构也不能直接回填历史记录。[日本棋院王座戦](https://www.nihonkiin.or.jp/match/oza/)

既有 [Oza 十一语来源复核](kifu-name-oza-oldmeijin-11lang-independent-review-2026-10-02.md) 可复用系列基础名的来源：十语为来源层 PASS，乌克兰语当地惯用名仍 HOLD；[乌语 editorial decision](kifu-name-oza-ua-editorial-decision-2026-10-02.md) 另有生成拼写研究。这些均不等于候选批准。本切片不补造十一语名称，也不把系列名来源批准转用于阶段词。

[预选来源 memo](kifu-name-oza-nhk-five-source-memo-2026-10-03.md) 的 inventory SHA 与当前冻结库存不同：只复用其网页证据，不转移旧 occurrence 集合。当前唯一范围输入是下述 `8a94…0413` 文件。

## 优先级与可核查覆盖

总范围：**142 个精确原文、2,786 局**；全部当前 `event_id=null`。所有 occurrence、来源路径、原日期、RO 和原文分组均保留在 protected scope 中。

|顺序|有限范围|原文组|局数|后续核查重点|
|---|---|---:|---:|---|
|A|CWI 空格 ordinal，排除 `20th Oza`、`28th Oza`|22|1,234|首批：留存原始 SGF 全成员已精确匹配；独立判定系列身份|
|B1|普通 `第n期日本王座战预选`|33|716|第二批：查 19x19 原始 SGF；仅声明不细分的预选阶段|
|C|19x19 joined ordinal／suffix ordinal，排除 `45thOza`|77|697|来源身份优先；日期一致不单独构成身份凭证|
|B2|预选片段、`届`、附加轮次|6|9|逐例判定，保留单位与轮次差异|
|H|来源／期号／身份存在待决异常|4|130|HOLD，暂不进入首批链接候选|

A 占全部范围 **44.3%**；A+B1 为 **55 原文／1,950 局（70.0%）**，适合作为前两次有限复核。A 的最大组依次为 `22nd Oza` 111、`23rd Oza` 109、`21st Oza` 102、`17th Oza` 93、`18th Oza` 92、`19th Oza` 92。完整 22 原文及每组精确 album ID 已冻结，禁止按 substring 扩大。

## 已发现的决定性异常

- **`28th Oza`，17 局（album 170812–170828）全部 HOLD。** 留存路径为 `games/Oza/26/P01.sgf` 至 `P17.sgf`，EV 为 `28th Oza`，日期为 1977／1978。CWI 索引标第 26 期为 1978、第 28 期为 1980；第 26 期页面也标 1978。目录／EV／日期发生冲突，不自动改为第 26 期。该页面未列出 P 文件，不把页面赛果当作这 17 局的逐局证明。[CWI 总索引](https://homepages.cwi.nl/~aeb/go/games/games/Oza/)、[第 26 期索引](https://homepages.cwi.nl/~aeb/go/games/games/Oza/26/index.html)
- **`20th Oza`，105 局整组暂缓。** 其中 album **25025** 的冻结来源 `data/kifu-album/Go_Seigen/1972-09-11.sgf` 在留存 archive 中不存在；日期为空，RO=`Round 2`。存在其他日期文件不允许替代此路径。其余 104 局有精确 archive 匹配，可在后续重新冻结更小 occurrence 子集；当前优先完整原文组。
- **`45thOza`，5 局暂缓。** album **54534** 日期 `1998-02-06` 晚于 CWI 第 45 期结果年 1997；其余为 1996／1997。可能是延迟日期／源期号解释，未证明错误；须取原始 SGF 判定。[CWI 总索引](https://homepages.cwi.nl/~aeb/go/games/games/Oza/)
- **裸 `Oza`，3 局暂缓。** album **121167**（1985-04-04）、**130235**（1971-11-17）、**131924**（1985-01-10）缺期号／阶段上下文；字符串相同不足以确认日本该系列。
- 4 条缺日期、15 条粗粒度／多日期保留原值。以 `1952+期号` 与宽松年份窗口做的日期筛查只是异常提示，**不是身份规则**，不得生成不存在的精确日期。

留存 CWI archive 共精确匹配 **1,355／1,356** 个来源路径。匹配局的 EV、RO、DT 与冻结记录一致；PB／PW 与冻结全量库存也全部一致，无 mismatch。它是留存 archive 的证明，尚未逐局读取当前生产对象存储 SGF；独立复核及写入前仍需真实来源／preimage gate。

## 有限语法候选交接

1. A 仅解析精确 ordinal 原文的期号和系列核心。暂不从 EV 增加阶段；RO 逐局保留，不能压成同一个「本赛」标签。
2. B1 明示「预选」，候选阶段只到 `preliminary_unspecified`，不得自动细化为一次／二次或现代 B／C。
3. B2 的 `第62届`、`日本第54/55期` 片段及 `第14/15期…第3轮`、`第20期…第2轮`分别待审。「第 n 轮」不等同 preliminary tier。
4. 后续应建立 **Oza 专属且独立签署**的规则、有限输出及依赖；Honinbo 的已审规则不能直接授权本范围。系列十一语基础名、阶段词／数字语法、精确 owner/scope 均须各有已审锚点；冲突检查、真实数据库快照及克隆演练仍属后续门槛。

## Protected 产物与复核入口

根目录：`~/.local/share/kifu-name-audit/2026-10-03/oza-bounded-identity-grammar-pending-sol/`（目录 0700，文件 0600）。SHA 均为文件 bytes，只有首批 subset 一项是规范 JSON 哈希。

|产物|SHA-256|
|---|---|
|原输入 `oza-series-preliminary-scope/scope.pending.json`|`8a94c6104227324bfb21bc781b4b5ba85c4247f4648a1465204862936acd0413`|
|`identity-grammar-scope.pending.json`|`031f708e0118863960588e7aaab8c42fcaab3d841fb6f5b9f5b34b74039056bb`|
|A 首批完整分组规范哈希|`e4e1639ccbdcb14e094761d650bf5b18cc1594a4d476b60a82be170413484fd4`|
|`cwi-root-checks.pending.json`|`a202130a5ed2b4a4e77d2e10004ed4f39fa71ef1aaf90c0cfef6016b3806b20d`|
|`cwi-root-context-checks.pending.json`|`37de252584bc0a54ee785e69d9b859cdda807febfca7520c6f6c71b94538f733`|
|`cwi-oza-26-index.body`|`4bcb34e1abf96778ce656c1f23821b0725c6f4c3ca6a807e1757ce1832bdbdaa`|
|`manifest.pending.json`|`bb38708c659aebce141c4ded6c6b9faf6847095d7dfde1e2977c9e0f17b59466`|

库存规范哈希：`66b8946d908468c5f9c8f0dc8ef4b4ceddb76d840ef42f5cff5122fc5744b3a3`。留存 `games.tgz` 在 `2026-10-02/park-junghwan-identity-work/cwi-full-archive/`，bytes SHA `935522a59817c12b37227e843cd3b4bc8d702e32e0e6fbc80b66d828dbbffcad`。

复核者可先重算 manifest 文件哈希、142／2,786 分区及 A 的规范哈希，再独立查看 A 全成员 source root 与原始库存上下文。所有层级仍为 pending；本文不授权链接、候选导入或发布。
