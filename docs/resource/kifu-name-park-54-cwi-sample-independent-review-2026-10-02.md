# 朴廷桓 ID 54：CWI 20 行样本独立身份复核

2026-10-02；审核代理 `/root/park_sample_independent_sol`；父代理确认分配模型 **`gpt-6-sol`、`reasoning_effort=high`**，本子代理运行时没有可独立读取的底层模型标识。这是**逐行人物身份裁决**，不是 231 行 CWI 同色候选、210 行机械保守子集或全部 1,526 行的整层批准；未连接或写入数据库，未改程序、已有文档或十一语名称载荷。

## 裁决

对预先列在[来源分诊](kifu-name-park-54-cwi-230-source-triage-2026-10-02.md)中的 20 行（19 行机械 clean，加排除项 `28450`），本轮裁决 **11 PASS、9 HOLD**。11 PASS 中 `56656`、`120680`、`122631`、`122632` 已由[先前四行独立复核](kifu-name-park-54-identity-independent-review-2026-10-02.md)批准，**不得重复计作新增**；本轮新增身份 PASS **7 行**：`122395/black`、`69017/black`、`46008/black`、`82717/black`、`122524/black`、`122574/black`、`794/white`。PASS 只覆盖所列冻结 `album_id/side`、本次来源 SGF 哈希及人物 54 的关联判断，不能直接转成生产写入；真实 NULL FK、目标/catalog 同时点前像、范围哈希和十一语名称审核仍须另行绑定。

我从受控来源文件和 CWI `games.tgz` 原始成员字节重新计算 20 对 SHA-256，用仓库 SGF parser 重读根属性、棋盘缺省、根摆子及首变完整落子序列，未仅接受生产者的匹配标签。20 对来源和 CWI 哈希全部等于分诊记录；20/20 的棋盘大小、摆子、完整有色落子序列及日期相等，目标人物在同一黑白方；13 个已抓取韩国棋院 HTML 的原始响应哈希也全部相符。逐行全部哈希、SGF 双方、日期、结果、手数、KBA URL 和裁决理由见受控 `recomputed-20-rows.jsonl` 与 `row-decisions.jsonl`。它们仍不能证明 CWI 与 `19x19` 的上游棋谱采集链相互独立。人物源语锚点沿用先前复核中的[韩国棋院棋士页](https://www.baduk.or.kr/record/player_view.asp?pkey=10000457)，本轮没有对其他同名人物或整库目录重新签署。

| Album/方 | KBA 正文核查 | 身份裁决 |
| --- | --- | --- |
| `30489/black` | 本次有限搜索无逐盘官方记载；双方 SGF 282 手同谱。 | **HOLD**：仅有可能共享上游的双档案。 |
| `45576/white` | 无逐盘官方记载；253 手同谱。 | **HOLD**。 |
| `28450/black` | 无逐盘官方记载；159 手同谱；GoRatings 无唯一同日同色对手匹配，原分诊已排除。 | **HOLD**：不能作为 clean 候选。 |
| `60230/black` | 无逐盘官方记载；180 手同谱。 | **HOLD**。 |
| `122395/black` | [KBA 517](https://m.baduk.or.kr/news/B01_view.asp?news_no=517)正文给出 2012-06-18 LG 32 强、朴执黑 153 手中盘胜吴光亚。 | **PASS（新增）**。 |
| `69017/black` | [KBA 624](https://m.baduk.or.kr/news/B01_view.asp?news_no=624)正文明确 2012-11-14 三星杯半决赛第 2 局，朴执黑 236 手中盘负古力。 | **PASS（新增）**；原分诊表将其写为“弱赛事背景”过于保守，实际正文具有逐盘信息。 |
| `60281/black` | 无逐盘官方记载；178 手同谱。 | **HOLD**。 |
| `45947/black` | [KBA 1036](https://m.baduk.or.kr/news/B01_view.asp?news_no=1036)给出朴执黑胜陈耀烨 5.5 目，却记 **278 手**；来源/CWI 的同一完整主线均为 **283 手**。 | **HOLD**：手数冲突未解，沿用先前四行审阅的保守门槛。 |
| `46008/black` | [KBA 1134](https://m.baduk.or.kr/news/B01_view.asp?news_no=1134)给出 2014-11-17 LG 8 强，朴执黑 219 手中盘胜陈耀烨。 | **PASS（新增）**。 |
| `82717/black` | [KBA 1783](https://m.baduk.or.kr/news/B01_view.asp?news_no=1783)列 2016-05-30 LG 32 强朴对“장웨이제”；[KBA 1784](https://m.baduk.or.kr/news/B01_view.asp?news_no=1784)记朴该轮晋级；[KBA 1790](https://m.baduk.or.kr/news/B01_view.asp?news_no=1790)明确朴在同一轮中盘胜该对手。[KBA 690](https://m.baduk.or.kr/news/B01_view.asp?news_no=690)另将其韩文名标为 `江維杰`，对应源谱对手。 | **PASS（新增）**：日期、赛事/轮次、人物、对手、胜负形成逐局交叉；KBA 未独立给出执黑及 201 手，该两项只由一致 SGF 提供。 |
| `122524/black` | [KBA 1886](https://m.baduk.or.kr/news/B01_view.asp?news_no=1886)给出 2016-08-12 应氏杯决赛第 2 局，朴执黑 282 手负唐韦星；其 3 点与韩式 2.5 目的说明和 SGF 白胜 3 点一致。 | **PASS（新增）**；勿将文章提及的第 1 局混入。 |
| `60900/white` | 无逐盘官方记载；287 手同谱；GoRatings 同日同色还有多行语境。 | **HOLD**。 |
| `46338/black` | 无逐盘官方记载；158 手同谱。 | **HOLD**。 |
| `122574/black` | [KBA 2614](https://m.baduk.or.kr/news/B01_view.asp?news_no=2614)实际正文明确 2018-05-30 LG 16 强，朴执黑 173 手中盘胜芝野虎丸。 | **PASS（新增）**；原分诊表称缺对手及手数，仅因其摘录未覆盖该正文段落。 |
| `56656/white` | [KBA 3028](https://m.baduk.or.kr/news/B01_view.asp?news_no=3028)给出朴执白 184 手中盘胜党毅飞。 | **PASS（先前已批）**。 |
| `120680/white` | [KBA 3226](https://m.baduk.or.kr/news/B01_view.asp?news_no=3226)给出朴执白 152 手中盘胜彭立尧；对手段位记录差异不作为另一身份。 | **PASS（先前已批）**。 |
| `122631/black` | [KBA 3354](https://m.baduk.or.kr/news/B01_view.asp?news_no=3354)给出申真谞执白 236 手中盘胜朴。 | **PASS（先前已批）**。 |
| `122632/white` | [KBA 3356](https://m.baduk.or.kr/news/B01_view.asp?news_no=3356)给出申真谞执黑 161 手中盘胜朴。 | **PASS（先前已批）**。 |
| `794/white` | [KBA 4359](https://m.baduk.or.kr/news/B01_view.asp?news_no=4359)给出 2022-10-28 三星杯 32 强，朴执白 168 手中盘胜柯洁。 | **PASS（新增）**。 |
| `19401/black` | [KBA 5376](https://m.baduk.or.kr/news/B01_view.asp?news_no=5376)对应 2025-06-22 春兰杯决赛第 2 局，朴执黑对杨楷文、285 手取胜；但 KBA 为 **2.5 目**，CWI 为 **3.5 目**，来源 `RE` 则记中盘胜。 | **HOLD**：得分幅度和终局方式未核清，暂不以人物/手数吻合覆盖结果记录冲突。 |

无官方页面的七行是“本次限定查找未取得逐盘正文”，不是该棋局不存在；其 CWI 与来源同谱仍只是候选。`45947` 的 5 手差及 `19401` 的结果差是具体已知矛盾，不能把它们改称“格式不同”。`82717` 由补取的官方抽签、赛果与韩中姓名对应资料加强，然而 KBA 本身无完整落子记录；其 PASS 是精确同色全谱绑定加独立赛事记载的**该行**身份判断，不提升其他同谱行。两档案共享上游的可能性对全部 20 行均保留。

## 受控证据与范围

受控目录为 `/Users/fan/.local/share/kifu-name-audit/2026-10-02/park-junghwan-identity-work/independent-sample-review/`；目录 `0700`，文件 `0600`。其中新抓取的 KBA 690、1783、1784 HTML 均 HTTP 200，URL、最终地址、字节数和各自 SHA-256 写在 `supplementary-kba-pages.json`；独立复算覆盖分诊原有 13 个 HTML。关键文件的 SHA-256：

| 文件 | SHA-256 |
| --- | --- |
| `recomputed-20-rows.jsonl` | `0d842fcff06d9a6990017129954d89c3ea8716a751eeaebfb7eb95e19688381d` |
| `row-decisions.jsonl` | `d55a59f79f95cc8ac22ab7c70172ed77730d61c78362e126c35871e3b316dfc3` |
| `supplementary-kba-pages.json` | `11058d09afbb7e4e8dcf39b949830231ea74b75e3af089389de4a8b51633d25e` |
| `verify_sample.py` | `4775b69993f61eaf8c10a1395e156880b46e29c6c23d9e28bc5122e3ad87991c` |
| `write_decisions.py` | `962525ac842113dba2c889bf1993da54fee197dde8d7c3d601fc555850cc9cb2` |

输入冻结文件校验：`park-54-kba-20-row-review.jsonl` 为 `1667d8cc8714bf648e1d7611f85a19dadd8a950dbd1d8de2b834bcaef7536a63`；`kba-page-evidence.jsonl` 为 `11ecc763788de4828f6a0412ed7f84e62e96896bb205e638e51f502e0b3b03fa`；`park-54-cwi-same-side-row-evidence.jsonl` 为 `20e3508dee417e2db1b208d8a272e586ee01fe7cdc0b9ec59da21bd4f81189b7`。CWI 原始 `games.tgz` 为 `935522a59817c12b37227e843cd3b4bc8d702e32e0e6fbc80b66d828dbbffcad`；全部 20 行各自来源/CWI 文件哈希和官方正文 URL/哈希在 `row-decisions.jsonl`。阅读时三份前置备忘录 SHA-256 依次为：[完整匹配生产者](kifu-name-park-54-cwi-fullmatch-producer-2026-10-02.md) `3486d1da283c860b86cd684a9b59397f7071d7b34d057d9d33e9cddb17ed5f5a`、[来源分诊](kifu-name-park-54-cwi-230-source-triage-2026-10-02.md) `19682c09d4727f1091a03fd7ae5db06492d2a337c7e80eb525ab20192630fd73`、[先前四行复核](kifu-name-park-54-identity-independent-review-2026-10-02.md) `bff0f92b633ecd18b788072e4594da02f046e4a66245e1b721ec032be97c6fb0`。

这 20 行是生产者固定的跨年代/赛事样本，而非可代表 210 行机械子集的概率抽样；不能用 11/20 估计总体正确率，也不能根据本次零新身份冲突批准其余 210 行或 1,526 行。未运行应用测试或生产写入。
