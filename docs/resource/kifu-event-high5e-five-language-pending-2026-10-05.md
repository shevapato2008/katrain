# high5e：五赛事五语待审核（2026-10-05）

Producer `/root/event10_review_apply` / `gpt-6-astra` / max。11 格有当地直接用例；14 格明确按原文翻译。全部 pending；无 DB 写入。

| ID | 赛事 | 非重复可见棋局/环境 | cn | tw | jp | ko | en |
|---|---|---:|---|---|---|---|---|
| 47 | 韩国国手战 | 665 | [韩国国手战](https://www.baduk.or.kr/game/game_view.asp?cmpt_code=1101)（直译） | [韓國國手戰](https://www.baduk.or.kr/game/game_view.asp?cmpt_code=1101)（直译） | [韓国国手戦](https://www.baduk.or.kr/game/game_view.asp?cmpt_code=1101)（直译） | [국수전](https://www.baduk.or.kr/game/game_view.asp?cmpt_code=1101) | [Guksu](https://en.wikipedia.org/w/index.php?title=Guksu&oldid=1288865481) |
| 63 | 日本关西棋院第一位决定战 | 619 | [日本关西棋院第一位决定战](https://kansaikiin.jp/wp/2026/07/24/sanyo-hai/)（直译） | [日本關西棋院第一位決定戰](https://kansaikiin.jp/wp/2026/07/24/sanyo-hai/)（直译） | [関西棋院第一位決定戦](https://kansaikiin.jp/wp/2026/07/24/sanyo-hai/) | [간사이기원 제1위 결정전](https://kansaikiin.jp/wp/2026/07/24/sanyo-hai/)（直译） | [Kansai Ki-in First Place Tournament](https://kansaikiin.jp/wp/2026/07/24/sanyo-hai/)（直译） |
| 67 | 春兰杯世界职业围棋锦标赛 | 587 | [春兰杯世界职业围棋锦标赛](https://www.sport.gov.cn/n20001280/n20067662/n20067613/c27069198/content.html) | [春蘭杯世界職業圍棋錦標賽](https://www.haifong.org/game/classes/0D13ACB8AFE22F9BDE07FDAABECD53AA) | [春蘭杯世界囲碁選手権](https://www.nihonkiin.or.jp/match/shunran/013.html) | [춘란배 세계프로바둑선수권대회](https://www.sport.gov.cn/n20001280/n20067662/n20067613/c27069198/content.html)（直译） | [Chunlan Cup](https://homepages.cwi.nl/~aeb/go/games/games/Chunlan/) |
| 56 | 台湾中环碁圣赛 | 578 | [中环碁圣赛](https://www.haifong.org/game/classes/480E360835EAB350F93094AAECD2A797)（直译） | [中環碁聖賽](https://www.haifong.org/game/classes/480E360835EAB350F93094AAECD2A797) | [台湾中環碁聖戦](https://www.haifong.org/game/classes/480E360835EAB350F93094AAECD2A797)（直译） | [중환기성전](https://tygem.game.naver.com/news/news/view.asp?seq=38953) | [CMC Gosei Championship](https://www.cmcnet.com.tw/files/20240710115110847.pdf) |
| 97 | 衢州烂柯杯中国围棋冠军赛 | 561 | [衢州烂柯杯中国围棋冠军赛](https://www.sport.gov.cn/n20001280/n20067662/n20067613/c22643886/content.html) | [衢州爛柯盃中國圍棋冠軍賽](https://www.sport.gov.cn/n20001280/n20067662/n20067613/c22643886/content.html)（直译） | [衢州爛柯杯中国囲碁チャンピオン戦](https://www.sport.gov.cn/n20001280/n20067662/n20067613/c22643886/content.html)（直译） | [취저우 란커배 중국바둑선수권대회](https://www.sport.gov.cn/n20001280/n20067662/n20067613/c22643886/content.html)（直译） | [Quzhou Lanke Cup Chinese Go Championship](https://www.sport.gov.cn/n20001280/n20067662/n20067613/c22643886/content.html)（直译） |

TEST、PROD 均覆盖 3,010 盘。仅绑定现有 owner 和空 name 前像；保留既有棋局关联与 raw EV。

包目录：`/tmp/kifu-event-next-high5e-20261005`。两环境 `bundle.pending.json`、`target-preimages.json`、`validation.pending.json`；共享 `registry.json`、`research.pending.jsonl`、`sources/manifest.json`。

## 直译说明

- `47-cn`：Render 국수전 (國手戰) as 国手战, adding 韩国 to distinguish this historical Korean title from the Taiwanese Guoshou and other national events.
- `47-tw`：Render 국수전 as 國手戰 in Traditional Chinese, preserving explicit 韓國 country scope.
- `47-jp`：Render 국수전 as 国手戦 in Japanese and add 韓国 to distinguish the Korean competition.
- `63-cn`：Render 関西棋院第一位決定戦 in Simplified Chinese as 关西棋院第一位决定战 and add 日本 country context; preserve first-place decision tournament scope.
- `63-tw`：Render 関西棋院第一位決定戦 as 關西棋院第一位決定戰 in Traditional Chinese, adding 日本 country context.
- `63-ko`：Render 関西棋院 as 간사이기원 and 第一位決定戦 as 제1위 결정전. Preserve the Kansai Ki-in competition rather than the Nihon Ki-in or All-Japan first-place events.
- `63-en`：Retain the institution's name Kansai Ki-in and translate 第一位決定戦 as First Place Tournament. This explicit translation does not claim published use or the broader Kansai Ki-in Championship identity.
- `67-ko`：Render 春兰杯世界职业围棋锦标赛 as 춘란배 세계프로바둑선수권대회, preserving sponsor, world, professional, Go and championship scope.
- `56-cn`：Convert 中環碁聖賽 into Simplified Chinese 中环碁圣赛; retain 碁 as part of this proper title. This is the newly numbered event from 2013.
- `56-jp`：Render 中環碁聖賽 as 中環碁聖戦 in Japanese, adding 台湾 to distinguish it from Japanese Gosei and from the former international CMC Cup.
- `97-tw`：Render the official domestic 衢州烂柯杯中国围棋冠军赛 in Traditional Chinese as 衢州爛柯盃中國圍棋冠軍賽; keep 中國 and 冠軍賽 to distinguish the later world Lanke event.
- `97-jp`：Render the domestic Chinese championship as 衢州爛柯杯中国囲碁チャンピオン戦. Preserve the title's Chinese championship scope without introducing a world championship claim.
- `97-ko`：Render the domestic championship as 취저우 란커배 중국바둑선수권대회, retaining Quzhou/Lanke and Chinese Go championship scope; this is not the world Lanke Cup.
- `97-en`：Render 衢州烂柯杯中国围棋冠军赛 as Quzhou Lanke Cup Chinese Go Championship. Chinese Go Championship explicitly distinguishes this domestic event from the World Go Open launched in 2023.

## 身份边界

- `47`：The historical South Korean Guksu professional Go title organized by Dong-A Ilbo, distinct from Taiwanese Guoshou, Korean Kuksu Mountains international matches and women's Guksu.
- `63`：The already linked Kansai Ki-in first-place decision tournament. Its institution and 第一位決定戦 identity are retained; no Nihon Ki-in first-place event, All-Japan first-place event, or broader Kansai Ki-in Championship alias is merged.
- `67`：The Chunlan-sponsored world professional individual Go championship, with established international participants; existing event ownership is reused without modifying editions or links.
- `56`：The Taiwanese 中環碁聖賽 newly numbered from 2013. Native Haifong history explicitly distinguishes it from the previous 中環盃 and pre-2013 碁聖戰. CMC's own English annual report identifies CMC Gosei Championship among Taiwan's four professional competitions.
- `97`：The domestic 衢州烂柯杯中国围棋冠军赛, as identified by the Chinese sports authority's account of its eighth edition in 2021. This is separate from the international 衢州烂柯杯世界围棋公开赛 launched in 2023. Existing membership is preserved.
