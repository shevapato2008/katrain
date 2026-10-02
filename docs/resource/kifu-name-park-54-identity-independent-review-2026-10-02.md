# 朴廷桓 ID 54：有限棋谱身份独立复核

2026-10-02；审核代理 `/root/park_54_identity_review_sol`，父代理明确分配模型 **`gpt-6-sol`、`reasoning_effort=high`**；运行时没有独立可读取的底层服务标识。只读核查受控文件及公开资料；没有连接或写入数据库、修改程序或批准十一语名称载荷。

## 决定与范围

按[有限批量身份政策](kifu-name-bulk-player-identity-policy-decision-2026-10-02.md)，**身份范围 PASS 4 个冻结槽位，HOLD 1,522 个**。PASS 仅为本文件列明的四个 `album_id/side`、本次冻结 SGF 哈希和人物 54 的身份判断；不是把来源 `19x19` 或同名 `朴廷桓` 整层批准，也不是可直接执行的生产写入载荷。生产写入仍须同时点完整目标/catalog 前像、真实 NULL FK、精确集合及最终关联哈希另行绑定审核。

复算[生产者清单](kifu-name-park-54-identity-scope-producer-2026-10-02.md)的现时文档 SHA-256 为 `67b989617c6b9052e55ba50aa92c3bb97a2a58c504be8c64beef8a81edae6847`。受控 `park-54-full-row-evidence.jsonl` 的 SHA-256 为 `602c6ccc9dc2746e47ffc055b110a6854882d75fa5d5f08447a5385d11fa6960`，确有 **1,526** 行。独立重算其分类为 1,385 个唯一日期/执色/结果相符候选、89 个无同日同色索引、42 个同日同色不唯一、7 个结果缺失、3 个结果冲突，合计 1,526。1,385 是筛查候选，不是已核实的完整棋谱身份。

[韩国棋院官方棋士页](https://www.baduk.or.kr/record/player_view.asp?pkey=10000457)直接将 `박정환` 与 `朴廷桓` 配对，列出韩国所属、1993-01-11 出生和 2006-05-13 入段。2007–2026 的候选日期没有先于该入段日，但活动期合理本身不能证明任何一盘的身份。

## 有界的完整棋谱核验

我选定[CWI 的第 24 届 LG 杯赛事页](https://homepages.cwi.nl/~aeb/go/games/games/LG/24/index.html)作为**预先定义的有限赛事组**，取其中标为 Park Junghwan 的六个公开 SGF，不按匹配结果挑盘。CWI 将其放在[职业棋谱档案](https://homepages.cwi.nl/~aeb/go/games/games/)的 LG 杯赛事目录；它是另一出版页面，但未声明每盘 SGF 的原始采集链，不能证明与 `19x19` 完全独立。六个 CWI 文件的完整落子顺序均与受控 SGF 完全一致，各自在全部 1,526 行中只命中一条；日期、黑白双方、结果、6.5 目贴目也吻合。受控源文件字节 SHA-256 与行中 `sgf_sha256` 六条全相等，均为 19 路、无摆子，单一主线；CWI 文件无摆子属性，也没有与 19 路默认棋盘冲突的设置。2026-10-02 10:48 UTC 前将六份 CWI SGF 与六份韩国棋院报道 HTML 保存在受控目录 `.../park-junghwan-identity-work/independent-review-captures/`；12 文件 `sha256.manifest` 的 SHA-256 为 `1f22b808ac93534e68582de9d5f8c85c78398ce81e1355d0b43605b32dbeed80`。

| 冻结槽位 | CWI 原始 SGF（完整步数） | 独立的韩国棋院赛事记载 | 身份裁决 |
| --- | --- | --- | --- |
| `122609/black`，2019-05-27，对童梦成 | [10.sgf](https://homepages.cwi.nl/~aeb/go/games/games/LG/24/10.sgf)，231 | [32 强报道](https://m.baduk.or.kr/news/B01_view.asp?news_no=3025)同人、同色、同结果，却写 **213 手**。 | **HOLD：手数冲突** |
| `56656/white`，2019-05-29，对党毅飞 | [17.sgf](https://homepages.cwi.nl/~aeb/go/games/games/LG/24/17.sgf)，184 | [16 强报道](https://m.baduk.or.kr/news/B01_view.asp?news_no=3028)明确朴执白，184 手中盘胜党。 | **PASS** |
| `120680/white`，2019-10-28，对彭立尧 | [25.sgf](https://homepages.cwi.nl/~aeb/go/games/games/LG/24/25.sgf)，152 | [8 强报道](https://m.baduk.or.kr/news/B01_view.asp?news_no=3226)明确朴执白，152 手中盘胜彭。 | **PASS** |
| `122627/black`，2019-10-30，对陶欣然 | [30.sgf](https://homepages.cwi.nl/~aeb/go/games/games/LG/24/30.sgf)，383 | [4 强报道](https://m.baduk.or.kr/news/B01_view.asp?news_no=3229)同人、同结果，却写 **375 手**。 | **HOLD：手数冲突** |
| `122631/black`，2020-02-10，对申真谞 | [F1.sgf](https://homepages.cwi.nl/~aeb/go/games/games/LG/24/F1.sgf)，236 | [决赛首局报道](https://m.baduk.or.kr/news/B01_view.asp?news_no=3354)明确申执白 236 手中盘胜朴。 | **PASS** |
| `122632/white`，2020-02-12，对申真谞 | [F2.sgf](https://homepages.cwi.nl/~aeb/go/games/games/LG/24/F2.sgf)，161 | [决赛次局报道](https://m.baduk.or.kr/news/B01_view.asp?news_no=3356)明确申执黑 161 手中盘胜朴；[赛事历届成绩](https://www.baduk.or.kr/game/game_view.asp?cmpt_code=2103&etcKey=2)列申以 2–0 胜朴。 | **PASS** |

两项冲突是官方报道手数与两个内容相同的棋谱档案之间的差异；可能是文字误记或棋谱尾段问题，现有证据没有证明哪一方有误，不将其并入 PASS。CWI 文件和 `19x19` 有可能共享上游，因此四条 PASS 依靠**完整主线同色唯一匹配，加上韩国棋院逐局日期/对手/执色/结果/手数的独立记载**，不是依靠「两个网站」这一事实。

## 未扩展到其他候选

为检验 1,385 个筛查候选而不是事后挑易查的棋谱，先固定种子 `park-54-identity-independent-review-2026-10-02:/root/park_54_identity_review_sol`（UTF-8 SHA-256 `cf30bf018cb5338c30859cb96a47d89d4fcb3053d877ba21ad9fb3f53c44bf1c`），以该哈希的十六进制整数初始化 Python `random.Random`，从按 `album_id` 升序的 1,385 行无放回抽 12 行。抽中顺序为 `101071, 89630, 15558, 122005, 122643, 122480, 83817, 105197, 15443, 86966, 61185, 4825`；上述 ID 数组的紧凑 JSON SHA-256 为 `b8a56dfb16b49ebca375e4b20a1727227cff6285a3e49244db0b15a170e54fb0`。这些行的日期、对手译名、执色、结果与[GoRatings 棋手对局索引](https://www.goratings.org/en/players/1090.html)可逐一对应，但本轮没有取得其完整外部棋谱或独立的逐局原始记录；**12/12 仍为 unresolved，不能计为随机审核通过**。这项小样本也远未达到政策的误差上界要求。

八组相同完整主线的 16 个槽位是 `37/10381`、`4173/5563`、`16770/16822`、`18264/18265`、`18880/19002`、`25564/84460`、`26296/84469`、`31477/150538`；逐组检查日期、执色、结果与对手，全部属于 1,385 筛查候选，但都不在四个 PASS 内。它们是八盘游戏的重复上下文，而非 16 个独立证人。尤其 `37/white` 的对手写 `王硕00`、`10381/white` 写 `王硕`；`25564/black` 与 `84460/black` 的赛事文字还分别出现不同赛季表述。全部 16 槽位继续 HOLD，不能用重复频次增加对整层的信心。其余无完整同色匹配及全量来源归属证明的 1,381 个筛查候选，连同生产者原有 141 个异常，也保持 HOLD；其中前述两项赛事手数冲突在这 1,381 内。汇总 **4 PASS + 1,381 筛查候选 HOLD + 141 初始异常 HOLD = 1,526**。

本结论不更改原始 PB/PW、日期、段位或棋谱；若后续解释两处手数冲突或取得其他完整棋谱，需重新冻结具体成员并独立审核，不由本四槽决定自动外推。
