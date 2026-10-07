# ret76／ret77 混合五位棋手 KO 有限裁决

2026-10-08（Asia/Shanghai）。决策者 `/root/bulk_player_identity_decision_astra`；任务配置 **`gpt-6-astra` / `max`**，运行时未另暴露可独立核实的模型／推理强度标识。本次只核具体来源、读音和物理范围；无 SQL、FK／alias／merge、代码修改、候选签署或 TEST SSH。

## 当前五人：允许继续生成候选

沿用 [首轮日本姓名裁决](kifu-first-pass-japanese-name-decision-2026-10-07.md) 和已审 `nikl-ja-ko-personal-name-v1` 合同。以下**完整输入及输出内容 PASS**，可进入既有独立候选、批次审核；不是现有可变 JSON 自动获批。统一 `decision_kind=generated`、`source_basis=normative_ja_ko_v1`，明确为本人日文读音的规范韩文，不声称每项均已获韩语专业发表。

| PROD ↔ TEST | 姓名／实际完整假名 | 精确 KO 输出 | 规则与可用来源角色 | slots／库内状态 |
| --- | --- | --- | --- | --- |
| 6258 ↔ 12024 | 鈴木津奈／すずき つな；官方スズキ ツナ | **스즈키 쓰나** | す→스、ず→즈、词中き→키、つ→쓰；IgoRating `professional_go_rating_archive`，日本棋院本人页 `official_person_page`。 | 75；当前 owner 对应可用。 |
| 5621 ↔ 11394 | 白鳥澄子／しらとり すみこ；官方シラトリ スミコ | **시라토리 스미코** | し→시、词中と→토、词中こ→코；同上，官方来源为日本棋院 archive 本人页。 | 70；当前 owner 对应可用。 |
| 6666 ↔ 12435 | 平野正明／官方ヒラノ マサアキ | **히라노 마사아키** | ひ→히；本人的マサアキ保留「正／明」对应的连续元音，辅以 NIKL 同读名审定例，见下；`official_person_page`。 | 67；当前 owner 对应可用。 |
| 469 ↔ 470 | 岡田伸一郎／おかだ しんいちろう；官方オカダ シンイチロウ | **오카다 신이치로** | 词中か→카；しん＋い→신이；ろう长音省略→로；IgoRating 专业页＋日本棋院 archive 本人页。 | 66；既有五语名称是 `review`，不是已核正源。 |
| 5315 ↔ 11092 | 水野一郎／みずの いちろう；官方ミズノ イチロウ | **미즈노 이치로** | ず→즈、ち→치、ろう长音省略→로；IgoRating 专业页＋日本棋院 archive 本人页。 | 55；当前没有名称行。 |

合计 **333 个黑方／白方 player reference slots**，不是 333 盘棋。五人的 CN/TW/JP/EN 已有实际来源包，可由既有路径继续独立审核；本次新增签署／写库／已完成数为 **0**。提交时仍精确绑定实际原名、完整假名、姓／名边界、source role、正文定位／SHA、研究 hash、当前 owner 及名称 preimage。保留官方原文空白，不把整理后的展示名伪称为原始 HTML 连续字节。

## 实际核查范围

- ret76 输入 `/tmp/kifu-player-next5retired76-20261008/source-only-packet-v2.json`，SHA **`de8a2942549fae32098bd455ca4ac001c442c45ae243204f4c792438b07629bd`**；16 份不同来源正文 SHA 已核。ret77 输入 `/tmp/kifu-player-next5retired77-20261008/source-only-packet-v1.json`，SHA **`ed93fd0fd72d1230719c13db9a1611655740524ed54fe0722c2bdf0305e1f43c`**；仅审 469／5315，相关 9 份不同正文 SHA 已核。
- 实际读取 FH ret76 `binding-fh-v1/identity-bridge.json`，SHA **`7bf5c1ccbab34f2d5fabc6e9524e03602bb286ee9bf8cd36497f85f82fa54d94`**；ret77 `binding-fh-v1/identity-bridge-selected2.json`，SHA **`e8b07aa55d78505ac206983babe084f36e82d4396db9c396706741af4e72b513`**。各路径相对对应批次目录。本轮未重新查询数据库，采用这两份已捕获的有限物理范围，后续写入仍按既有 preimage 守卫。
- 日本棋院本人档案与 CWI 姓名／生日对应：6258 为 1921-04-16，5621 为 1919-01-06，6666 为 1945-07-17，469 为 1966-09-22，5315 为 1934-09-20。CWI 是独立历史棋谱资料；IgoRating JP/EN 是同一发行者，不能冒称日本棋院或两个独立来源。来源中旧名只辅助身份，不写跨 owner 别名。
- 5315 包里 `original_in_body=false` 是对不含空格字串的机械检查；实际官方正文明确有 `水野　一郎`、`ミズノ　イチロウ`、相符生日及 2005-12-26 逝世资料。不能把这个布尔值误读为页面没有本人姓名。

### 有限韩文冲突检查

ret76 原 Naver manifest SHA `74856c0d70c2198d1a7c7288b1aa567f8260c50fc1c88cf9256713c63d59c35c` 有 4 次成功；失败及一次重试仍失败的记录保留。改用实际可达韩维 API：`ko-wikipedia-query-manifest.json` SHA **`049a9823b4bdede67a590302a12641183559708414720c8e83732d26efcb2b97`**，重试 manifest SHA **`ae3261a9b9676e3ba0afd5aa5cc8a6b344f371521cd7ae08e3e4d5531caa1b24`**。当前三人都已取得原名＋围棋、完整 KO＋围棋两类 HTTP 200 查询；实际看过返回结果及 SHA，无相关相反用名。API 零结果只属于该次有限查询，不是全网无惯用名。

ret77 两人使用 `ko-two-candidate-query-manifest.json` SHA **`1c253277917ccc770083105821670ead21e887eb174f2f1e1a4879ea3945ebfc`** 及 exact 重试 manifest SHA **`01d608bad8a6e2f6609c45e7c149eac2adc610fa6bcaa7fee00382e2f01da961`**，成功正文 SHA 均核过。469 两类完整查询均成功。5315 未加引号的 `水野一郎 바둑` 实际 HTTP 200，返回分词产生的 25 条总命中，本次实际可见前 10 条均为异人／无关内容；其完整 KO 查询也实际 200。前者可以诚实记作一次**完成的有限原名查询**，不能充当同人证据、精确匹配结果或不存在证明。加引号的额外尝试网络失败不撤销已完成查询，也不要求追加负面闭环。

469 [韩经围棋报道](https://www.hankyung.com/article/2000011302491) 的搜索工具缓存确有 `오카다 신이치로`，与本次规则输出一致；直抓和 web.open 均 403，保持 discovery／缓存角色。不能伪造 conventional 的原站 200。缓存和官方页对应的配偶是 **岡田結美子／오카다 유미코**，producer 中途说“小林泉美”有误，已通知更正。相同拼法的正面缓存线索不构成冲突，不阻塞有独立原音、规则和真实查询的 generated。

### 6666 的连续元音

复用 NIKL [假名表](https://www.korean.go.kr/front/page/pageView.do?mn_id=97&page_id=P000108)、[日语细则](https://www.korean.go.kr/front/page/pageView.do?mn_id=97&page_id=P000129)、[日本人名规定](https://www.korean.go.kr/front/page/pageView.do?mn_id=97&page_id=P000146)。另直接 HTTP 200 捕获[第9次政府／媒体外来语审议记录](https://www.korean.go.kr/nkview/foreign/gpfor009.html)，实际有 **高木正明／다카기 마사아키**。该材料只作为相同已知读音名的表记参照，不证明棋手身份，也不证明平野的韩文全名曾发表。本人读音由日本棋院 `ヒラノ　マサアキ` 提供。本项采用 `마사아키`，不机械删成 `마사키`，也不建立“所有相邻元音一律保留”的通用规则。

新增捕获位于 ret76 `astra-decision-v1/nikl-masaaki-gpfor009.body`，UTF-8，SHA **`d0c44676896188b8f8412a30dab4fe9062abf923abdce36ea403b8c89eccd801`**；元数据同名 `.capture.json`，采时 `2026-10-07T16:54:32.930002+00:00`。可复用其真实规则证据，无需重新审计划或增设服务。

## 保留 ret76 两位内容成果，物理范围继续 HOLD

**544 田中佑樹：姓名内容 PASS，当前混批排除。**允许保存 conventional **`다나카 유키`** 的待后续来源研究：[Netmarble 第10届 Globis U-20 新闻](https://baduk.netmarble.net/News/News/BbsContentView.asp?seq=13300570)实际 HTTP 200、EUC-KR 正文在日本二段参赛者名单使用该名，并明确文字／照片由韩国棋院提供。IgoRating／日本棋院的本人读音、2005 年生日、2023 年二段身份与报道语境相符。来源是 Netmarble 专业新闻转载，不能冒称韩国棋院原站。原正文 `544-ko-netmarble.body` SHA **`47576da0fc3f63a458347f90ca168b99aaa4a8521250514c5ade2441b7427e9b`**，准确抓取 URL／时间在 `.capture.json`。Hangame 缓存保留 discovery，其当前 200 正文没有姓名，不能代用。

FH 显示 PROD 544 有 69 linked slots，但 TEST 对应 69 raw slots 全部 FK NULL，TEST 545／1045 为零槽旧 owner。**不把正确译名写给猜测的 TEST owner，不解开本次物理 HOLD**；留后续有限身份修复。

**3879 伊藤友惠：规则及外部字形桥内容 PASS，当前混批排除。**IgoRating 完整 `いとう ともえ` 支持 generated **`이토 도모에`**：とう长音省略，名首と→도。CWI 明列伊藤友恵／Ito Tomoe、生平及旧名；中文名册在淡路修三等人的师承栏发表“伊藤友惠”。本轮另直接 HTTP 200 捕获[日本棋院淡路修三本人页](https://www.nihonkiin.or.jp/player/htm/ki000043.htm)，明确 1955 年师从伊藤友恵，与中文名册相同学生的生日／入段年及导师对应。新增 `astra-decision-v1/3879-awaji-official-mentor.body` SHA **`72249bdad55f84a4926624e0708623df539a9b0e6e231f042a29cca001399c1d`**，采时 `2026-10-07T16:54:32.930478+00:00`。这是该人的具体关系桥，不是通用惠↔恵转换规则。

FH 同时发现惠字 owner PROD 3879／TEST 9676 各 63 slots，恵字另有 PROD 3878／TEST 9675 各 13 slots。**保持两组 owner、FK、alias 不动**；不因同人翻译内容成立就默认两库归并已完成。上述两项 HOLD 不阻塞表内五个 clean owners。
