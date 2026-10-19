# ret80 金島忠：单项韩文姓名决定

日期：2026-10-08（Asia/Shanghai）。审阅者：`/root/ret77_ko_astra_decision`；既有子任务配置 `gpt-6-astra`，reasoning effort `max`。范围仅限 ret80 的 PROD 6673 金島忠这一项 KO，其他四项不在本次复审范围。

本决定锚定 `/tmp/kifu-player-next5retired80-20261008/source-producer-frozen25-final-v3/source-matrix25.json`，SHA-256 `549893e3c9d75649618b364787817bce042192d3070db064f10ae81dc4dd674d`；对应 manifest SHA-256 `a8c835e22c92f482db2a352aed7d36aefcfc16c604e4ff638716108b14e9f479`，两份散列均已实际重算核对。本项在已审阅的 source-v2 中为 `김도충`／`published_name`／`found`，RISS 主证据摘录与原始正文连续匹配；来源生产者确认 final-v3 保留相同候选、方法及正文，仅迁移路径并整理状态说明。本次未重新审阅其余四项。

**决定：CORRECT → `김도충`，按 `published_name`／已找到正文接受。** 此人无需因本项韩文姓名问题 HOLD 或替换。采用的是 RISS 书目中实际刊载的作者名；不宣称它是唯一通行译名，也不以此推断人物国籍、族属或原生语言。

## 实际采用的证据

已直接读取 [RISS《棋經衆妙》书目](https://www.riss.kr/search/detail/DetailView.do?p_mat_type=d7345961987b50bf&control_no=31cd2a28b94a9b13) 的 UTF-8 原始正文。作者字段明确列出 `김도충 (金島忠)`，与同条书名、原字作者及围棋丛书语境相连：

- 作者包括林元美、赵治勋、**김도충（金島忠）**、赵祥衍；书名为《棋經衆妙》。
- 责任说明列林元美原著，赵治勋、金島忠、赵祥衍解说；丛书为 `아진바둑 고전시리즈`。
- 书目记录出版项为首尔、아진、1993，正文提供 RISS 记录号 `M7273403`。

这足以按本轮已授权的有限来源标准，将准确原字 `金島忠` 与围棋专业语境中的韩文刊载名 `김도충` 对应；没有依据搜索标题自行生成这个名字。此次读取的是机构书目记录，没有读取纸书或书籍扫描原件，因此不声称已核对原书封面／版权页，也没有把该书目误称为棋院官方人物资料。

原始正文：`/tmp/kifu-player-next5retired80-20261008/6673-ko-riss-lead.body`；捕获记录为同目录 `6673-ko-riss-lead.capture.json`。记录 HTTP 200，最终 URL 与请求一致，抓取时间 `2026-10-07T19:25:18.127909+00:00`，正文 203,430 bytes。独立重算 SHA-256 为 `e988ac82d4eb2aceb30e0ee79027e6b79425ab64d265e4b265e16aefbd075b7c`，与记录匹配。

## 官方读音与另两种韩文形式

[日本棋院 ki000060](https://archive.nihonkiin.or.jp/player/htm/ki000060.htm) 的同一人物表实际给出 `金島　忠`、`Kanashima Tadashi`、`カナシマ　タダシ`、1945/1/7。原始文件 `6673-official-retry.body` 的 SHA-256 为 `814c98dee26b81141e093ee5ab1977f7e3563bf32d9ad4c5033cd372d44396d1`，捕获记录为 HTTP 200；IgoRating 的 `6673-ja.body` 也实际写出 `金島忠（かなしま ただし）`，SHA-256 为 `97d68afd776629d3df8bd8eedb893b17200800562f86e563222c652ac70370af`。

据此前已实际核实的 [NIKL 日语假名表](https://www.korean.go.kr/front/page/pageView.do?mn_id=97&page_id=P000108)，カ・ナ・シ・マ按姓名单位写为가・나・시・마；独立给定名的首字タ写다，后接ダ→다、シ→시。因此 **`가나시마 다다시` 是官方完整假名的正确规范推导**。规则正文 SHA-256 为 `94edbf8feed1569ed74c4700b4188511a7cccb226d879dd5d7fd1a49f3deb220`。

保存的 Naver 候选查询中，Namu 第39届王座战及第41届本因坊战片段出现 **`가나시마 타다시`**。这与 NIKL 给定名词首タ→다的形式有差异，构成实际发现的另一写法线索；不能描述为“未发现不同写法”。但第41届本因坊战的原站请求实际为 HTTP 403，保存正文是 Cloudflare 拦截页，未读取棋战原文，故不能据此认证为已核实的原站刊载姓名。

此次采用 RISS 已读取的 `김도충`；另外两种形式及其证据层级保留在说明中。`김도충` 不由 `カナシマ タダシ` 的 NIKL 转写产生，因此方法必须是 `published_name`，不能标成 `normative_ja_to_ko`。官方日文读音及对应英文名保持原来源语义；不据韩文书目作者栏擅自改变原始语言分类或断言人物的出生语言。

## 有限查询与失败记录

资料均位于 `/tmp/kifu-player-next5retired80-20261008/`，没有为本决定追加广泛检索。

| 捕获 | 实际结果 | 原始正文 SHA-256 |
| --- | --- | --- |
| `ko-finite-v1/6673-candidate_go.body`：`가나시마 다다시 바둑` | HTTP 200，标题符合查询，正文结果区含 Namu 的 `가나시마 타다시` 片段。 | `7cdb6fbd5671d65c5a80ce3503029c6df6525c3773de0753db6b176eaa58ac1a` |
| 初次 `6673-original_go` | `NameResolutionError`，未取得正文；不是已完成的空结果查询。 | 无正文 |
| `ko-finite-v1/6673-original_go-retry.body`：`金島忠 바둑` | 一次有限重试取得 HTTP 200，标题符合查询，结果区发现 RISS 的围棋书目链接。 | `c251b10ea754dd89a166e48596d718aa31cb0cb1e7c5f65e7587285f42816d88` |
| `6673-ko-namu-lead.body` | HTTP 403，实际为 Cloudflare 拦截正文；不证明人物、译名或页面不存在。 | `938b56e42f9b676c0bfb7044789772ee26071b645d2b15fd8643e24c300df989` |
| `6673-ko-riss-lead.body` | 一次有限直访取得 HTTP 200，实际作者栏明确对应 `김도충 (金島忠)`；为最终姓名证据。 | `e988ac82d4eb2aceb30e0ee79027e6b79425ab64d265e4b265e16aefbd075b7c` |

执行方提供的 PROD 6673 → TEST 12442、54 slots 是任务绑定信息，本审阅未独立查询数据库。此决定只接受来源人物的韩文刊载名，不授权自动合并、别名写入或棋谱重新链接；未执行 SQL、签名或 Git 操作。已将最终值 `김도충` 和证据限制回传来源生产者。
