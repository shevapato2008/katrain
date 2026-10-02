# 频次 21–40 五主语言姓名来源独立审核（Sol）

审核日期：2026-10-03（北京时间）。范围为 20 人 × `cn/tw/jp/ko/en` 的 100 个显示格。`cn` 按简中显示、`tw` 按台湾繁中职业来源、`jp` 按日文职业使用审核；包内键 `zh/zh-Hant/ja` 分别映射到这些显示格。PASS 仅表示此处明确列出的**显示姓名来源证据**成立，不批准人物主键、棋谱归属、外键、专辑或数据库写入。

**结论：按原 JSONL 的原样候选，91 PASS / 9 HOLD；采用本审核直接举证的两个日文新候选后，93 PASS / 7 HOLD。** 余下 7 个 HOLD 均为 `cn`：原候选是繁体或异体，不能因为 URL 为 `/zh/` 就批准为简中显示。本审核没有用自动简繁转换填这些格。原汇总的 95 PASS-CANDIDATE / 5 HOLD 不应当作为严格五主语言显示的验收数字。

## 输入与复核方式

读取了以下三个 memo；任务中所说 `last10` 实际文件名为 `second10`：

- [21–30 候选](kifu-name-five-primary-frequency-21-30-first10-candidates-luna-2026-10-03.md)。
- [31–40 候选](kifu-name-five-primary-frequency-31-40-second10-candidates-luna-2026-10-03.md)。
- [21–40 汇总](kifu-name-five-primary-frequency-21-40-summary-luna-2026-10-03.md)。

直接读取两个受控包的候选、索引、manifest 和原 HTML：

1. `~/.local/share/kifu-name-audit/2026-10-03/china-professional-roster/five-primary-21-30-top10-luna/`
2. `~/.local/share/kifu-name-audit/2026-10-03/china-professional-roster/five-primary-31-40-second10-luna/`

逐条以保存的响应体重新计算候选声明的 SHA-256，并核对 manifest 文件哈希；80 个 GoRatings H1 均与候选逐字一致；80 页真实正文中的生日均与各人的稳定生日一致；20 个繁中姓名均出现在保存的海峰正文、棋士页或赛事名单中，并复核对应职业语境。**未把索引字段代替网页原文。** 第一包 `goratings-index.json` 的申真谞 `ja` 项 `dob` 是空字符串，虽然候选写 `2000-03-17`；原 HTML 的 `生年月日 2000-03-17` 确实存在，因此这是索引缺项，不是生日冲突。前批 memo 的“四语生日相同”应限定为原 HTML 正文核对结论。

GoRatings 的 `zh/en/ja/ko` 是**同一个出版方**，同 ID 与生日只能证明该站各语言页面的内部一致性。海峰是第二个专业出版方，支持繁中真实用名和职业身份语境；新增日本棋院是第三个出版方。没有宣称四份 GoRatings 页面构成四个独立来源，也没有宣称海峰文章普遍提供独立生日。

来源登记基线仍为 `kifu-name-source-registry-2026-10-02.6.json`。两个原包、候选 JSONL、registry 均未修改。新网页通过直接 HTTP 响应解析确认，下面记录 URL、原文和响应 SHA-256；按任务“只写指定文档”的范围，没有另写响应快照或新候选 JSONL。

## 100 格逐人结果

表中 `P` 是 PASS，`H` 是 HOLD。`jp` 两个箭头表示**本报告提出的新候选**，不是把原包改写成新值。GoRatings 四语 URL 可由 `https://www.goratings.org/{zh,en,ja,ko}/players/{ID}.html` 精确定位；表内保留各网页 H1 实際字形。`tw` 直接来源逐人列在后表。

| 排名 | 输入名 | ID / 四语正文生日 | cn：原 H1 / 结论 | tw：直接用名 / 结论 | jp：原 H1 或新候选 / 结论 | ko：原 H1 / 结论 | en：原 H1 / 结论 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 21 | 姜东润 | 313 / 1989-01-23 | 姜東潤 H | 姜東潤 P | 姜東潤 P | 강동윤 P | Kang Dongyun P |
| 22 | 坂田荣男 | 592 / 1920-02-15 | 坂田荣男 P | 坂田榮男 P | 坂田栄男 P | 사카다 에이오 P | Sakata Eio P |
| 23 | 申真谞 | 1313 / 2000-03-17 | 申眞諝 H | 申真諝 P | 申眞諝 P | 신진서 P | Shin Jinseo P |
| 24 | 羽根直树 | 93 / 1976-08-14 | 羽根直樹 H | 羽根直樹 P | 羽根直樹 P | 하네 나오키 P | Hane Naoki P |
| 25 | 朴永训 | 125 / 1985-04-01 | 朴永訓 H | 朴永訓 P | パク・ヨンフン P | 박영훈 P | Park Yeonghun P |
| 26 | 结城聪 | 251 / 1972-02-11 | 结城聪 P | 結城聰 P | 結城聡 P | 유키 사토시 P | Yuki Satoshi P |
| 27 | 高尾绅路 | 175 / 1976-10-26 | 高尾紳路 H | 高尾紳路 P | 高尾紳路 P | 다카오 신지 P | Takao Shinji P |
| 28 | 陈耀烨 | 297 / 1989-12-16 | 陈耀烨 P | 陳耀燁 P | 陳耀ヨウ P | 천야오예 P | Chen Yaoye P |
| 29 | 时越 | 449 / 1991-01-11 | 时越 P | 時越 P | 时越 H → 時越 P | 스웨 P | Shi Yue P |
| 30 | 芮乃伟 | 115 / 1963-12-28 | 芮乃伟 P | 芮乃偉 P | ゼイ廼偉 P | 루이나이웨이 P | Rui Naiwei P |
| 31 | 金志锡 | 862 / 1989-06-13 | 金志錫 H | 金志錫 P | 金志錫 P | 김지석 P | Kim Jiseok P |
| 32 | 王铭琬 | 70 / 1961-11-22 | 王銘琬 H | 王銘琬 P | 王銘琬 P | 왕밍완 P | Wang Ming Wan P |
| 33 | 俞斌 | 92 / 1967-04-16 | 俞斌 P | 俞斌 P | 兪斌 P | 위빈 P | Yu Bin P |
| 34 | 柯洁 | 1195 / 1997-08-02 | 柯洁 P | 柯潔 P | 柯洁 H → 柯潔 P | 커제 P | Ke Jie P |
| 35 | 柁嘉熹 | 433 / 1991-01-15 | 柁嘉熹 P | 柁嘉熹 P | 柁嘉熹 P | 퉈자시 P | Tuo Jiaxi P |
| 36 | 王元均 | 1304 / 1996-03-14 | 王元均 P | 王元均 P | 王元均 P | 왕위안쥔 P | Wang Yuanjun P |
| 37 | 小林觉 | 51 / 1959-04-05 | 小林觉 P | 小林覺 P | 小林覚 P | 고바야시 사토루 P | Kobayashi Satoru P |
| 38 | 石田芳夫 | 222 / 1948-08-15 | 石田芳夫 P | 石田芳夫 P | 石田芳夫 P | 이시다 요시오 P | Ishida Yoshio P |
| 39 | 芈昱廷 | 1155 / 1996-01-08 | 芈昱廷 P | 羋昱廷 P | 芈昱廷 P | 미위팅 P | Mi Yuting P |
| 40 | 周睿羊 | 381 / 1991-03-08 | 周睿羊 P | 周睿羊 P | 周睿羊 P | 저우루이양 P | Zhou Ruiyang P |

原样计数：`cn` 13P/7H、`tw` 20P/0H、`jp` 18P/2H、`ko` 20P/0H、`en` 20P/0H，总计 91P/9H。采用两个新日文候选后 `jp` 为 20P/0H，总计 93P/7H。

`ko/en` 的 PASS 指 GoRatings 对应该语言页面的精确显示，另有独立专业资料支持所指职业棋手。它**不声称**这些拼写是韩国棋院、各国协会或所有出版方的统一首选拼写，也不消除 `Sakata Eio`、`Wang Ming Wan` 等转写风格差异。

## 繁中独立职业来源逐项核对

| 输入名 | 已直接核对的来源及页面字形 | 对人的职业语境 |
| --- | --- | --- |
| 姜东润 | [2018 国手山脉](https://haifong.org/news/content/712E678446CE7431D744ADA87E913665)：姜東潤 | 韩国九段名单；击败井山裕太、负廖元赫的赛果 |
| 坂田荣男 | [1965 名人战回顾](https://www.haifong.org/news/content/6CCDD265056ED6DAB83280A3C28582A5)：坂田榮男 | 日本名人；林海峰四比二夺冠，另述 1963 年年龄 43 岁 |
| 申真谞 | [2023 杭州亚运](https://www.haifong.org/news/content/9A383988CA0AD0BCDAF2E36445DD25BD)：申真諝 | 韩国世界第一、许皓鋐半决赛对手 |
| 羽根直树 | [2017 世界混双](https://www.haifong.org/news/content/D5F26F3BC6BA204CDEA10C75BCF48D26)：羽根直樹 | 日本组合藤泽里菜搭档；对台组合三四名赛 |
| 朴永训 | [2018 国手山脉](https://haifong.org/news/content/712E678446CE7431D744ADA87E913665)：朴永訓 | 韩国九段，王元均首轮对手 |
| 结城聪 | [2018 国手山脉](https://haifong.org/news/content/712E678446CE7431D744ADA87E913665)：結城聰 | 日本九段代表、申真諝对手 |
| 高尾绅路 | [2011 中日精英赛](https://www.haifong.org/news/content/BC8799108222DDE8326A191868156DBC)：高尾紳路 | 明列日方九段棋士、比赛树 |
| 陈耀烨 | [2021 春兰杯](https://www.haifong.org/news/content/A963F1FAC4B276D8490FD74048A8A548)：陳耀燁 | 中国历届冠军、许皓鋐十六强对手 |
| 时越 | [2025 北海新绎杯](https://www.haifong.org/news/content/1A1FC6784E61CEF19A50D168C92AB76B)：時越 | 中国九段、陈祈睿及周睿羊对手 |
| 芮乃伟 | [女子围棋史](https://www.haifong.org/news/content/4882B2D965117C4AF0369C0264FB9ED5)：芮乃偉 | 世界首位女子九段、2000 韩国国手战胜曹薰铉 |
| 金志锡 | [2018 国手山脉](https://haifong.org/news/content/712E678446CE7431D744ADA87E913665)：金志錫 | 韩国九段、胜林君谚和申真諝 |
| 王铭琬 | [2017 九段棋士专访](https://www.haifong.org/news/content/8A6B878FE3C30EAA8E4845A4D9FB099E)：王銘琬 | 九段职业棋士、围棋软件讨论；不是仅命中导航 |
| 俞斌 | [棋士页面](https://www.haifong.org/venue/692168FABACD02B8B959604A0DFEC581)：俞斌 | 正文独立姓名与九段；该页缺生日和详细履历，不能当成完整独立身份档案 |
| 柯洁 | [2021 春兰杯](https://www.haifong.org/news/content/A963F1FAC4B276D8490FD74048A8A548)：柯潔 | 中国九段、许皓鋐八强对手 |
| 柁嘉熹 | [2014 两岸棋王赛](https://haifong.org/news/content/4CB6B2B12736DA221BEABE4461DE6BAF)：柁嘉熹 | LG 杯冠军、白胜唐韦星 |
| 王元均 | [2014 两岸棋王赛](https://haifong.org/news/content/4CB6B2B12736DA221BEABE4461DE6BAF)：王元均 | 台湾棋王、负羋昱廷；文中同时比较王柁前日对局 |
| 小林觉 | [2025 围棋史专栏](https://www.haifong.org/news/content/CE1B374854762138825A17D8193F7CB7)：小林覺 | 明言日本棋士；另区分小林光一，未把两人合并 |
| 石田芳夫 | [1973 名人挑战赛回顾](https://www.haifong.org/news/content/B641DD5580F882FE80017DF335E2F5C3)：石田芳夫 | 人间电脑、林海峰七番胜负对手 |
| 芈昱廷 | [2014 两岸棋王赛](https://haifong.org/news/content/4CB6B2B12736DA221BEABE4461DE6BAF)：羋昱廷 | 梦百合杯冠军、黑胜王元均 |
| 周睿羊 | [2025 北海新绎杯](https://www.haifong.org/news/content/1A1FC6784E61CEF19A50D168C92AB76B)：周睿羊 | 中国九段、胜时越及大竹优 |

这些是显示来源的交叉核对，比赛日期、国家和对手语境并不构成本地棋谱或 FK 归属批准。俞斌棋士页和小林觉专栏的证据厚度比完整协会履历弱；这里仅用于来源显示的验证，没有把这一弱点隐藏为生日匹配。

## 五个日文 HOLD 的重新审核

### 陈耀烨：原候选 `陳耀ヨウ` 可作为有证据日文显示

日本棋院[2014 年 3 月第 3 周对局结果](https://archive.nihonkiin.or.jp/match/2014/03/33_17.html)正文，3 月 18 日百霊杯一回战列 `陳　耀ヨウ 九段`，对手 `金　眞輝 初段`，黑半目胜。候选 `陳耀ヨウ` 仅去掉姓名表格排版空格，字形与读音没有改动。包内 ID 297 英文原 HTML 同日记录 `Black Win Kim Jinhwi`，提供跨出版方同赛事同对手连接。

另有日本棋院[2010 电视亚洲杯报道](https://archive.nihonkiin.or.jp/publishing/2010/06/614.html)实际写 `陳耀燁九段`；[2015 梦百合杯报道](https://www.nihonkiin.or.jp/match_news/match_info/2_406.html)则写 `陳燿燁九段`。因此保留 `陳耀ヨウ / 陳耀燁 / 陳燿燁` 三个来源实际形式，不能声称其中一种排除了其余形式。原混写本身不再是 HOLD 理由；若后续要选统一产品首选全汉字显示，需明确选择规则。

### 时越：原 `时越` HOLD，新候选 `時越` PASS

同一份[2014 对局结果](https://archive.nihonkiin.or.jp/match/2014/03/33_17.html)正文写 `時　　越 九段`，白负 `王　堯 六段`；ID 449 同日记录 `White Loss Wang Yao`。日本棋院[2015 梦百合杯报道](https://www.nihonkiin.or.jp/match_news/match_info/2_406.html)本赛种子名单直接连续写 `時越九段`，因此新候选 `時越` 不需要自行做汉字转换。GoRatings 原 H1 `时越` 仍逐字保留为原源值，不能冒称该 H1 原本就是 `時越`。

### 芮乃伟：原候选 `ゼイ廼偉` 可作为有证据日文显示

日本棋院[2014 对局结果](https://archive.nihonkiin.or.jp/match/2014/03/33_17.html)正文直接写 `ゼイ廼偉 九段`，白胜 `於　之瑩 四段`；ID 115 同日记录 `White Win Yu Zhiying`。这是独立职业出版方的直接混写用例，原候选可 PASS。

日本棋院[2015 梦百合杯报道](https://www.nihonkiin.or.jp/match_news/match_info/2_406.html)同时存在全汉字 `芮乃偉九段（中国）`，对谢依旻的女流组赛事语境清楚。`ゼイ廼偉 / 芮乃偉` 并存，`廼` 不能静默改成 `乃` 后仍称原文。

### 柯洁：原 `柯洁` HOLD，新候选 `柯潔` PASS

日本棋院[2020 三星杯决赛结果](https://www.nihonkiin.or.jp/match_news/match_result/2020sansungfinal.html)可见文章 H1 为 `柯潔優勝【2020三星火災杯ワールド囲碁マスターズ決勝三番勝負】`，正文和成绩均直接写 `柯潔九段（中国）`。ID 1195 原包记录 2020-11-02 白胜及 11-03 黑胜 Shin Jinseo，与官方两局赛果一致。原 `柯洁` 留在 GoRatings 原值，新候选单独标为 `柯潔`。

### 芈昱廷：原候选 `芈昱廷` 可作为有证据日文显示，保留 `羋` 冲突

日本棋院[2016 新奥杯报道](https://www.nihonkiin.or.jp/match_news/match_result/21_16.html)正文中国参赛名单直接写 `芈昱廷九段`；[2015 梦百合杯报道](https://www.nihonkiin.or.jp/match_news/match_info/2_406.html)前期种子同样写 `芈昱廷九段（中国）`。因此不能只因这个字也用于简中，就认定日文职业来源未使用该字。

日本棋院[2020 农心杯报道](https://www.nihonkiin.or.jp/match_news/match_info/21noshin15_1.html)中国名单又写 `羋昱廷九段`。2014 官方对局表使用 `ビイク廷`，同日白胜黄云嵩的记录与 ID 1155 的 `White Win Huang Yunsong` 一致。保留 `芈昱廷 / 羋昱廷 / ビイク廷` 来源形式，不推导自动统一首选。这里的 PASS 证明原候选有直接日文职业用例，不证明它是唯一日文字形。

## 新增日文网页的直接响应核验

2026-10-03 直接 HTTP GET，原 HTML 经解析后核对姓名文字；SHA-256 是当次响应字节。旧 archive 页只有一个空的 logo H1，文章标题实际位于 H2，因此明确记录 H2，未把文章标题冒称为姓名 H1。现代页也包含一个空 logo H1，下表列的是非空文章 H1。

| 直接 URL | 实际文章标题及标题层级 | 响应 SHA-256 |
| --- | --- | --- |
| [2014 对局结果](https://archive.nihonkiin.or.jp/match/2014/03/33_17.html) | H2 `【3月第3週】主な対局結果`；H1 空 | `f4a7c29a68f42e653c2429eef2988744915f9e458ef3103f8a238b2b292035e2` |
| [2020 三星杯决赛](https://www.nihonkiin.or.jp/match_news/match_result/2020sansungfinal.html) | H1 `柯潔優勝【2020三星火災杯ワールド囲碁マスターズ決勝三番勝負】` | `64f143a7a31f0feb8da9e68cc0fc4b1d004668366a966fd47a0d13b55c33f98b` |
| [2016 新奥杯](https://www.nihonkiin.or.jp/match_news/match_result/21_16.html) | H1 `伊田16強戦へ。柯潔と対戦！【第1回新奥杯世界囲碁オープン戦】` | `09b93c26b220b90144c98a763c951b423e3237d2e8f9dbad964e059890eb464a` |
| [2020 农心杯](https://www.nihonkiin.or.jp/match_news/match_info/21noshin15_1.html) | H1 `中国優勝　柯潔半目残った！【第21回農心辛ラーメン杯世界囲碁最強戦】` | `5972959d7ae9a1a8db6799e44c6b5514a546147a41a6505be31d57fafee8dd42` |
| [2015 梦百合杯](https://www.nihonkiin.or.jp/match_news/match_info/2_406.html) | H1 `日本勢は決勝進出ならず【第2回夢百合杯世界囲碁オープン戦総合予選】` | `8a30341d1bca11ccafef8a00ad38477e20d79be77a9aa36fb4ca7285a1afb968` |
| [2010 电视亚洲杯](https://archive.nihonkiin.or.jp/publishing/2010/06/614.html) | H2 `週刊碁6月14日号（６月７日発売）特集内容`；H1 空 | `4814c96fe5d78455046d379929c072ffcd26fa189311d753cbca56ef40899d20` |

## 保留的 7 个 cn HOLD 与完成边界

`姜東潤、申眞諝、羽根直樹、朴永訓、高尾紳路、金志錫、王銘琬` 是本批 GoRatings `/zh/` 原 H1。对应输入名的简中字形可以作为下一轮查证目标，但本报告未将输入名或转换结果算成直接来源证据。这 7 格需补真实简中职业来源的逐字用名，再复核赛事/身份连接。

本报告只批准来源显示证据的结论与两个新的日文显示候选建议；未计算 raw-slot，未建立或修改本地人物实体、FK、专辑、SGF 归属。没有代码、数据库、registry 或原受控包写入，没有提交。
