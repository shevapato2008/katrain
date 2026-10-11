# high5d：五赛事五语待审核（2026-10-05）

Producer `/root/event10_review_apply` / `gpt-6-astra` / max。9 格有当地直接用例；16 格明确按原文翻译。全部 pending；无 DB 写入。

| ID | 赛事 | 非重复可见棋局/环境 | cn | tw | jp | ko | en |
|---|---|---:|---|---|---|---|---|
| 75 | 中日围棋对抗赛 | 783 | [中日围棋对抗赛](https://www.olympic.cn/sports/other/2003/0918/24504.html) | [中日圍棋對抗賽](https://www.olympic.cn/sports/other/2003/0918/24504.html)（直译） | [日中囲碁対抗戦](https://www.olympic.cn/sports/other/2003/0918/24504.html)（直译） | [중일 바둑 대항전](https://www.olympic.cn/sports/other/2003/0918/24504.html)（直译） | [Japan-China Go Exchange](https://homepages.cwi.nl/~aeb/go/games/games/CJGoExchange/index.html) |
| 80 | 韩国KBS杯围棋王战 | 748 | [KBS围棋王战](https://www.baduk.or.kr/game/game_view.asp?cmpt_code=1106)（直译） | [KBS圍棋王戰](https://www.baduk.or.kr/game/game_view.asp?cmpt_code=1106)（直译） | [KBS囲碁王戦](https://www.baduk.or.kr/game/game_view.asp?cmpt_code=1106)（直译） | [KBS바둑왕전](https://www.baduk.or.kr/game/game_view.asp?cmpt_code=1106) | [KBS Cup](https://en.wikipedia.org/w/index.php?title=KBS_Cup&oldid=1262346303) |
| 34 | 日本女子名人战 | 705 | [日本女子名人战](https://www.nihonkiin.or.jp/match/fmeijin/archive.html)（直译） | [日本女子名人戰](https://www.nihonkiin.or.jp/match/fmeijin/archive.html)（直译） | [女流名人戦](https://www.nihonkiin.or.jp/match/fmeijin/archive.html) | [일본 여류명인전](https://www.nihonkiin.or.jp/match/fmeijin/archive.html)（直译） | [Women's Meijin](https://archive.nihonkiin.or.jp/match/fmeijin/index-e.html) |
| 48 | 韩国王位战 | 670 | [韩国王位战](https://archives.baduk.or.kr/archives/talk/view.asp?no=7)（直译） | [韓國王位戰](https://archives.baduk.or.kr/archives/talk/view.asp?no=7)（直译） | [韓国王位戦](https://archives.baduk.or.kr/archives/talk/view.asp?no=7)（直译） | [왕위전](https://archives.baduk.or.kr/archives/talk/view.asp?no=7) | [Wangwi](https://en.wikipedia.org/w/index.php?title=Wangwi&oldid=1333598247) |
| 72 | 中国全国围棋个人赛 | 670 | [全国围棋个人赛](https://www.sport.gov.cn/n322/n3407/n3413/c564649/content.html) | [中國全國圍棋個人賽](https://www.sport.gov.cn/n322/n3407/n3413/c564649/content.html)（直译） | [中国全国囲碁個人戦](https://www.sport.gov.cn/n322/n3407/n3413/c564649/content.html)（直译） | [중국 전국바둑개인전](https://www.sport.gov.cn/n322/n3407/n3413/c564649/content.html)（直译） | [Chinese National Individual Go Championship](https://www.sport.gov.cn/n322/n3407/n3413/c564649/content.html)（直译） |

TEST、PROD 均覆盖 3,576 盘。仅绑定现有 owner 和空 name 前像；保留既有棋局关联与 raw EV。

包目录：`/tmp/kifu-event-next-high5d-20261005`。两环境 `bundle.pending.json`、`target-preimages.json`、`validation.pending.json`；共享 `registry.json`、`research.pending.jsonl`、`sources/manifest.json`。

## 直译说明

- `75-tw`：Convert 中日围棋对抗赛 into Traditional Chinese 中日圍棋對抗賽, preserving the two-country regular representative exchange identity.
- `75-jp`：Render 围棋对抗赛 as 囲碁対抗戦, with 日中 naming Japan and China in Japanese order. This is regular bilateral representative exchange, not 日中スーパー囲碁.
- `75-ko`：Render 中日 as 중일, 围棋 as 바둑 and 对抗赛 as 대항전. Scope is the regular representative exchange series, not a later relay or youth event.
- `80-cn`：Preserve broadcaster KBS; translate 바둑왕전 directly as 围棋王战. No sponsor era, year or match round is added.
- `80-tw`：Preserve KBS and translate 바둑왕전 as 圍棋王戰 in Traditional Chinese.
- `80-jp`：Preserve KBS and translate 바둑왕전 as 囲碁王戦 in Japanese.
- `34-cn`：Render native 女流名人戦 as 女子名人战, adding 日本 to distinguish the Japanese title from Korean and Taiwanese events.
- `34-tw`：Render 女流名人戦 as 女子名人戰 in Traditional Chinese, with 日本 identity qualifier.
- `34-ko`：Render 女流名人戦 in Korean as 여류명인전 and add 일본 to distinguish the Japanese professional title from the Korean women’s Myeongin event.
- `48-cn`：Translate 왕위전 as 王位战, adding 韩国 to preserve its country-specific professional identity.
- `48-tw`：Translate 왕위전 as 王位戰 with 韓國 in Traditional Chinese.
- `48-jp`：Translate 왕위전 as 王位戦 with 韓国 in Japanese; this is the Korean Go title, not Japanese shogi Oi.
- `72-tw`：Convert 全国围棋个人赛 to Traditional Chinese 全國圍棋個人賽 and retain explicit 中國 country scope.
- `72-jp`：Render 全国围棋个人赛 as 全国囲碁個人戦 and add 中国, preserving individual competition rather than team or qualification events.
- `72-ko`：Render 中国全国围棋个人赛 as 중국 전국바둑개인전, preserving China/national/Go/individual scope and both men's and women's divisions.
- `72-en`：Render the official Chinese national individual Go competition as Chinese National Individual Go Championship. Preserve individual scope; do not narrow it to men or confuse it with qualification/dan events.

## 身份边界

- `75`：The already linked formal representative Japan–China regular Go exchange series of 1960s–1990s, covering the friendship and later competitive phases; the NEC Supergo relay, Fujisawa visits, youth and special matches remain separate. China Olympic native history and CWI distinguish these scopes.
- `80`：The Korean KBS televised Baduk Wang professional tournament, separate from the Korean Kiwang title, Japanese NHK Cup and Asian TV championship.
- `34`：The Japanese women’s Meijin professional Go title, separate from open Japanese Meijin, Korean women’s Myeongin and Japanese shogi women’s Meijin.
- `48`：The historical Korean Wangwi professional Go title, separate from Wangja, Paewang and Japanese shogi Oi.
- `72`：The Chinese national individual professional Go competition including male/female divisions, separate from national team, league, qualification and dan competitions. The batch reuses existing approved membership and adds no edition claims.
