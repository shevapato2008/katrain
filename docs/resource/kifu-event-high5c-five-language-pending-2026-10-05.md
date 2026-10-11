# high5c：五赛事五语待审核（2026-10-05）

Producer `/root/event10_review_apply` / `gpt-6-astra` / max。17 格有当地直接用例；8 格明确按原文翻译。全部 pending；无 DB 写入。

| ID | 赛事 | 非重复可见棋局/环境 | cn | tw | jp | ko | en |
|---|---|---:|---|---|---|---|---|
| 35 | 日本女子本因坊战 | 900 | [日本女子本因坊战](https://www.nihonkiin.or.jp/match/fhoninbo/archive.html)（直译） | [日本女子本因坊戰](https://www.nihonkiin.or.jp/match/fhoninbo/archive.html)（直译） | [女流本因坊戦](https://www.nihonkiin.or.jp/match/fhoninbo/archive.html) | [일본 여류본인방전](https://www.cyberoro.com/news/N_news_view.oro?div_no=13&num=513148) | [Women's Honinbo](https://www.nihonkiin.or.jp/english/topics/11/topics2011_10.htm) |
| 54 | 台湾国手赛 | 842 | [台湾国手赛](https://haifong.org/game/classes/A822120A9D857AB7AC88180F76BF3529)（直译） | [國手賽](https://haifong.org/game/classes/A822120A9D857AB7AC88180F76BF3529) | [台湾国手戦](https://haifong.org/game/classes/A822120A9D857AB7AC88180F76BF3529)（直译） | [대만 국수전](https://www.baduk.or.kr/record/player_view.asp?pkey=20000150) | [Guoshou](https://gotoeveryone.k2ss.info/news/tw/go/12/) |
| 60 | 富士通杯世界围棋锦标赛 | 818 | [富士通杯世界围棋锦标赛](https://sports.sohu.com/fujitsucup23/) | [日本富士通盃](https://www.haifong.org/news/content/157A1D983409CB2FFAFF70140B175A51) | [世界囲碁選手権・富士通杯](https://archive.nihonkiin.or.jp/match/fujitsu/) | [후지쓰배 세계 바둑 선수권 대회](https://archives.baduk.or.kr/archives/talk/view.asp?no=7) | [Fujitsu Cup](https://archive.nihonkiin.or.jp/match/fujitsu/index-e.html) |
| 64 | 中国龙星战 | 806 | [中国龙星战](https://www.foxwq.com/news/5435.html) | [中國龍星戰](https://www.foxwq.com/news/5435.html)（直译） | [中国竜星戦](https://www.igoshogi.net/igo/china_ryusei/) | [중국 용성전](https://m.baduk.or.kr/news/B01_view.asp?news_no=3214) | [Longxing](https://en.wikipedia.org/w/index.php?title=Longxing_(competition)&oldid=1168652461) |
| 89 | 中国阿含桐山杯 | 793 | [阿含·桐山杯中国围棋快棋公开赛](https://www.sport.gov.cn/n20001280/n20067662/n20067613/c26786492/content.html) | [阿含·桐山盃中國圍棋快棋公開賽](https://www.sport.gov.cn/n20001280/n20067662/n20067613/c26786492/content.html)（直译） | [阿含・桐山杯中国囲碁早碁オープン戦](https://www.sport.gov.cn/n20001280/n20067662/n20067613/c26786492/content.html)（直译） | [아함·동산배 중국바둑속기오픈전](https://www.sport.gov.cn/n20001280/n20067662/n20067613/c26786492/content.html)（直译） | [Ahan Tongshan Cup](https://www.usgo.org/content.aspx?club_id=454497&item_id=109554&page_id=5) |

TEST、PROD 均覆盖 4,159 盘。仅绑定现有 owner 和空 name 前像；保留既有棋局关联与 raw EV。

包目录：`/tmp/kifu-event-next-high5c-20261005`。两环境 `bundle.pending.json`、`target-preimages.json`、`validation.pending.json`；共享 `registry.json`、`research.pending.jsonl`、`sources/manifest.json`。

## 直译说明

- `35-cn`：Translate native 女流 as 女子 and 戦 as 战, preserve 本因坊, and add 日本 identifying the Japanese professional series.
- `35-tw`：Translate native 女流 as 女子 and 戦 as 戰, preserve 本因坊, with 日本 identity qualifier.
- `54-cn`：Convert official 國手賽 to 国手赛 with 台湾 distinguishing the existing Taiwan professional title.
- `54-jp`：Preserve 国手 and render 賽 as 戦, with 台湾 identifying the existing 2005-onward title.
- `64-tw`：Convert 中国龙星战 to Traditional Chinese 中國龍星戰, preserving the China qualifier.
- `89-tw`：Convert the entire Chinese formal name to Traditional Chinese and Taiwan-style 盃, retaining China, fast-play and open-event scope.
- `89-jp`：Preserve 阿含・桐山杯 and render 中国围棋快棋公开赛 as 中国囲碁早碁オープン戦. This is the Chinese tournament, not the Japanese cup or bilateral champion match.
- `89-ko`：Render 阿含·桐山杯 as 아함·동산배 and 中国围棋快棋公开赛 as 중국바둑속기오픈전, preserving the China/open/fast-play scope.

## 身份边界

- `35`：The Japanese women’s Honinbo professional title; separate from the open Honinbo title.
- `54`：The Taiwan national-master professional title with numbered editions from 2005; historical predecessor and Korean Guksu competitions are not newly merged.
- `60`：The 1988–2011 international professional Fujitsu Cup, not unrelated amateur or student events sponsored by Fujitsu.
- `64`：The Chinese domestic Ryusei/Longxing television tournament; distinct from Japanese, Korean and bilateral champion events.
- `89`：The Chinese Ahan–Tongshan fast-play open cup. The Japanese Agon–Kiriyama title and China–Japan champion playoff are separate existing scopes.
