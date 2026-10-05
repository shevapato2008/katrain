2026-10-05，`/root/event10_review_apply` 使用父任务确认的 `gpt-6-astra` / `max` 配置，独立批准现有赛事 24、25 的 10 项名称。逐项重新打开网页，并核对保留原文的 SHA-256。

| 赛事 ID | 简中 | 繁中 | 日文 | 韩文 | 英文 |
|---:|---|---|---|---|---|
| 24 | 本因坊战 | 本因坊戰 | 本因坊戦 | 본인방전 | Honinbo |
| 25 | 十段战 | 十段戰 | 十段戦 | 일본십단전 | Judan |

英语名称由 [CWI 本因坊赛事档案](https://homepages.cwi.nl/~aeb/go/games/games/Honinbo/) 和 [CWI 日本职业赛事目录](https://homepages.cwi.nl/~aeb/go/games/games/index.html) 直接支持。目录把 Honinbo、Judan 列为赛事，足以确认其在本任务中的赛事含义。

中文简繁体分别核对固定版本的目标语言正文：[本因坊战简中](https://zh.wikipedia.org/w/index.php?title=%E6%9C%AC%E5%9B%A0%E5%9D%8A%E6%88%98&oldid=93277475&variant=zh-cn)、[本因坊戰繁中](https://zh.wikipedia.org/w/index.php?title=%E6%9C%AC%E5%9B%A0%E5%9D%8A%E6%88%98&oldid=93277475&variant=zh-tw)、[十段战简中](https://zh.wikipedia.org/w/index.php?title=%E5%8D%81%E6%AE%B5%E6%88%98&oldid=92446810&variant=zh-cn)、[十段戰繁中](https://zh.wikipedia.org/w/index.php?title=%E5%8D%81%E6%AE%B5%E6%88%98&oldid=92446810&variant=zh-tw)。这些正文均明确指向日本赛事；包内保留日本棋院独立赛事身份佐证。

日本棋院的 [本因坊戦](https://www.nihonkiin.or.jp/match/honinbo/070.html) 与 [十段戦](https://www.nihonkiin.or.jp/match/jyudan/064.html) 页面直接支持日文名称。十段战页面同时使用带当期赞助商的名称和简洁赛事标题；跨届赛事实体采用页面已经使用的「十段戦」。

韩国棋院的 [张栩履历](https://www.baduk.or.kr/record/player_view.asp?pkey=20000106) 使用「본인방전」，[井山裕太履历](https://www.baduk.or.kr/record/player_view.asp?pkey=10000324) 使用「일본십단전」。届次、年份和对手与日本赛事一致，十段战韩文保留来源中的日本限定。

TEST 与 PROD 的新只读快照分别采于 09:37:44、09:37:48 UTC。两赛事的所有者前像与原包一致，10 个名称前像仍为空。仅刷新包级 inventory/catalog 哈希；原始独立绑定人与空名称前像保持原样，并经本次新快照复核。两个批准包均通过现有验证器，10 项 approved，0 项 pending/rejected，0 项结构或写入错误。

逐项来源、原文哈希、审核签名和环境哈希见 [独立审核 JSON](kifu-event24-25-five-language-independent-review-2026-10-05.json)。批准包为 [TEST](kifu-event24-25-TEST-approved-names-2026-10-05.json.gz)、[PROD](kifu-event24-25-PROD-approved-names-2026-10-05.json.gz)，原始研究记录见 [research JSONL](kifu-event24-25-five-language-research-2026-10-05.jsonl.gz)。运行数据包保留于两台服务器及本机的 `/tmp/kifu-event24-25-reviewed-20261005/`。
