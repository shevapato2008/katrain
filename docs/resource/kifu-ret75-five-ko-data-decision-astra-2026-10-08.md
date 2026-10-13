# ret75 五位棋手姓名有限裁决

2026-10-08（Asia/Shanghai）。决策者 `/root/bulk_player_identity_decision_astra`；本任务配置 **`gpt-6-astra` / `max`**，运行时未另提供可独立核实的模型或推理强度标识。状态：**`conditional_current_owner_binding`**。本文件审核具体来源和输出；不是研究记录签批、owner 绑定、SQL 或发布批准。

## 结论

沿用 [首轮日本姓名裁决](kifu-first-pass-japanese-name-decision-2026-10-07.md) 和已审实现。**三个 KO 输出可继续制成待审候选；6633、6634 的读音／发表姓名内容有依据，但各自未满足当前入库合同，分别 HOLD。**五位现有 JP/EN 正源可继续使用，仍须 FH 对当前 owner 的有限同人、旧名及碰撞核对；不自动链接或合并人物。

| Owner / 原名 | JP / EN 可用来源值 | 本轮 KO | 决定 |
| --- | --- | --- | --- |
| 6599 小松伸昭 | 小松伸昭 / Komatsu Nobuaki | **고마쓰 노부아키** | `generated`：IgoRating 本人 `こまつ のぶあき`；CWI 同行姓名、旧名及生平辅助对应。 |
| 6633 大澤銀次郎 | 大沢銀次郎 / Osawa Ginjiro | **오사와 긴지로** | 规则输出内容可保存；**KO 入库 HOLD**：NDL 作者典拠角色及同页原名／假名不满足现有正面规范合同，见下。 |
| 6634 窪内秀知 | 窪内秀知 / Kubouchi Shuchi | **구보우치 슈치** | 真实专业发表内容 **PASS**；本轮仅 source-only，**KO 入库 HOLD**，见下。 |
| 6686 九世安井算知 | 九世安井算知 / Yasui Sanchi IX | **제9세 야스이 산치** | `conventional`：Cyberoro 正文逐字含世次和姓名，取代 v5 旧 KO HOLD。 |
| 6259 鈴木越雄 | 鈴木越雄 / Suzuki Etsuo | **스즈키 에쓰오** | `generated`：IgoRating 本人 `すずき えつお`；CWI 同行姓名、旧名及生平辅助对应。 |

原包机会范围 524 个已链接 player slots；上述三个可继续 KO 为 344 slots，6633／6634 合计 180 slots。它们不是本轮新增完成量：**本裁决写库、签署和新增完成数均为 0**。CN/TW 没有新正源，继续用户已授权的原文/default 首轮显示，不能计作严格核实的 CN/TW 译名或五语全完成。

## 核过的有限证据

- 以 producer `/root/player_ei_sources_sol` 的 `source-only-packet-v7.json` 为冻结输入，位于 `/tmp/kifu-player-next5retired75-20261007/`；SHA-256 **`846fd9057af3ca9049a5dbb72af800c9d04d32a7b5cd3dad893e13251c8488e2`**。15 个不同原始正文文件均独立重算 SHA 相符。v5 SHA `09993ada7ea3d65e1a578c9756d7598043fc8778c53475810d20f0647ce322ba` 保留为前版，不把新发现倒写成它原来已有的证据。
- 原 KO 查询 manifest `e16c7c0c1fe613410e2bea9cf8a7cf52c35df1e87bbac8653eb06839ffb4039e` 有 6 次 HTTP 200、4 次真实失败；一次有限重试 manifest **`437051aaedec96001a6831aabed6ac935364f11058847a3500c1714d63ed6269`** 补齐 4 次 200。十份成功正文 SHA 均核过；每人实际完成原名＋围棋、候选 Hangul＋围棋两类查询。失败记录保留，不称“网络不存在韩文”。
- 6599 搜索可见其他小松及其他 Nobuaki，未支持当前完整姓名的相反拼法；6633 可见无关结果；6259 Namu 棋赛表出现同样 `스즈키 에쓰오`，是相关正面发现，不能因直页未取得就反过来阻塞规范输出，也不把搜索摘要升级为专业发表正文。童书作者同音结果不充当围棋身份。

### 规范输出内容与实际可提交范围

6599／6259 使用既有 `nikl-ja-ko-personal-name-v1`、`source_basis=normative_ja_ko_v1`，记录 `decision_kind=generated`，不能称已发表韩语职业惯用名。复用已捕获的 NIKL [假名表](https://www.korean.go.kr/front/page/pageView.do?mn_id=97&page_id=P000108)、[日语细则](https://www.korean.go.kr/front/page/pageView.do?mn_id=97&page_id=P000129)、[日本人名规定](https://www.korean.go.kr/front/page/pageView.do?mn_id=97&page_id=P000146)。三个拟用输出的读音和姓/名边界逐个核过；6633 仅保存分析，不能据此越过其来源合同 HOLD：

- `こまつ｜のぶあき` → `고마쓰｜노부아키`：姓首 こ→고，つ→쓰；名内 き→키。无促音或长音处理。
- `オオサワ｜ギンジロウ` → `오사와｜긴지로`：明确的开头 オオ、末尾 ロウ 长音按细则省略；ギン→긴、ジ→지。不是从汉字猜读音。
- `すずき｜えつお` → `스즈키｜에쓰오`：ず→즈、名中完整 つ→쓰；保留后接 お→오，无促音。不会生成 `에츠오`。

IgoRating 是实际专业数据页，不冒称日本棋院；其 JP/EN 是同一发行者。CWI 是历史棋谱资料，不把它提供的生平冒写为 IgoRating 页面本身提供。独立候选签核仍须绑定准确 owner、输入正文、规则、研究 hash 和输出；本备忘录不代签后续可变 JSON。

### 6633：可接受的外部身份桥，仍须当前 owner 对应

[NDL authority 00500273](https://id.ndl.go.jp/auth/ndlna/00500273) 提供完整汉字、假名，来源为《囲棋独習案内》。本轮另实际打开并直接 HTTP 200 归档其[书目 000000493843](https://ndlsearch.ndl.go.jp/books/R100000002-I000000493843)：明确连接同一 authority、围棋书作者及 1895 年出版信息。CWI 方圆社棋谱使用 Osawa Ginjiro；已捕获棋史在 1874 年、1881 年及 1891 年围棋语境出现大沢／大澤银次郎。

据此，**同一稀见全名、同一围棋领域、相容年代，加上真实新旧字形，可作为本次有限 JP/EN 姓名采用的综合身份依据**，不因缺 DOB 机械 HOLD。此为多源综合判断；NDL 没有明言“这个作者就是 owner 6633”，棋史也不是官方 person key。FH 如发现当前 owner 年代、原文、旧名或同名者实质冲突，只停该人；不批准全库澤→沢替换或 owner 合并。

**KO 另有明确合同缺口：**正面规范分支要求同一合格 JA capture 含其原名和完整假名，且来源角色须在既定名单中。NDL 作者典拠实际标目为 `大沢, 銀次郎`、`オオサワ, ギンジロウ`；棋史有 `大澤銀次郎` 而没有本人假名。新增书目强化同人判断，并未把作者典拠变成传记辞典或职业棋手资料页。本轮不伪造其 source_role、不改原始摘录、不为此修改校验；因此 6633 KO 留 source-only／HOLD。它不阻塞该人其他已有正源语言，也不阻塞其余三人的 KO。

新增原始书目捕获：`astra-decision-v1/6633-ndl-book.body`，SHA **`5acbac52fe9d979f262e67aeda9ec3439ffd2ed3626bfaabd0fe82836a8d41da`**；元数据 `6633-ndl-book.capture.json`，采时 `2026-10-07T16:09:37.594429+00:00`。上述路径相对本批 `/tmp/kifu-player-next5retired75-20261007/`。

### 6634：专业发表可确认，抓取状态必须真实

已独立通过 web.open 复现 [Badukworld 第23届 NHK 杯完整专业对局表](https://www.badukworld.co.kr/servlets/GameGiboJs?flag=1&index=0&key=23rd+Japanese+NHK+Cup)，三个 1975–1976 年对局行均出现 `구보우치 슈치`。官方[关西棋院本人页](https://kansaikiin.jp/kisi_prof/kubouchisyuchi.html)提供窪内秀知、完整假名和 1920-01-25 生日，CWI 支持旧名窪内敏明；Naver 另有同 Hangul、汉字及生日的棋赛表线索，但角色仍是 discovery。

独立工具摘录已保存 `astra-decision-v1/badukworld.web-tool-extracted.txt`，SHA **`d0ead9dd56eb945866c60bde842c3184c2ab626a032d9a2cb5247c0c9eaaac92`**。这是**工具提取文字的 SHA**，不是原站 HTML hash；原站响应状态未知，直接请求 403/超时保留。工具显示旧抓取缓存，不声称本轮直接访问成功。

现有 `found source_check` 需要真实 HTTP 200；因此**本轮不把该摘录送成可采纳 conventional research**，不把 Naver 的 200 冒写为 Badukworld 的 200，也不为此修改门禁。只留正源材料及准确拟用值；以后取得可归档的合格正文再提交此项。其他已满足门限的项目可继续。

撤回本轮中途消息里“`くぼうち` 必须机械生成为 `구보치`”的表述：假名相邻 `お` 行＋`う` 不自动证明跨词素处是应删除的长音。本轮既不批准该替代拼法，也不另以未经确认的音节分析把发表值包装成 generated。

### 6686：采用明确九世的专业正文

[Cyberoro 专栏 973](https://www.cyberoro.com/column/column_view.oro?column_no=973) 原站实际 HTTP 200；独立解码 EUC-KR 后确认正文在 1845 年与秀和对局语境连续写有 **`제9세 야스이 산치 安井算知`**。原文件 `6686-ko-cyberoro-column.body`，SHA **`e0a8911d820a3b2f2d30582ed61873643c60bf0eac7c377ad22b92b4ac77442b`**，采时 `2026-10-07T16:01:45.197283Z`。

结合日本棋院明确九世／天保四杰的两篇正文及 CWI `Yasui Sanchi IX`，允许逐字采用 **`제9세 야스이 산치`** 为 conventional。保留世次即可直接消歧，无须为本项再生成韩文或补全姓氏假名。Naver 的第二世资料保留为“不同世次”；不能代证九世，也不能仅因同名就把真实九世正源判为冲突。此结论不批准第二世与九世共享 owner、alias 或检索归并。

## 可立即继续的范围

EI 可按表准备五位 JP/EN、两个规范 KO、一个九世 conventional KO 的 pending 记录；附新增 NDL 书目和 v7 的真实 Cyberoro 正源。FH 完成当前两库 owner/旧名/碰撞对应后，由独立 reviewer 按现有路径签准确候选和批次。6633／6634 KO 分别留待后续；原有 5853/5854、5662/616 等旧名关系仍 HOLD，不借本批合并。保持首轮显示、严格核实、原文保留三个统计口径；不追加全库检索、三站负面闭环、DDL 或音译服务。
