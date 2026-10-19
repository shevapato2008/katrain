# high5f：五赛事五语待审核（2026-10-05）

Producer `/root/event10_review_apply` / `gpt-6-astra` / max。12 格有当地直接用例；13 格明确按原文翻译。全部 pending；无 DB 写入。

| ID | 赛事 | 非重复可见棋局/环境 | cn | tw | jp | ko | en |
|---|---|---:|---|---|---|---|---|
| 46 | 全日本第一位战 | 480 | [全日本第一位决定战](https://www.nihonkiin.or.jp/player/htm/ki000008.html)（直译） | [全日本第一位決定戰](https://www.nihonkiin.or.jp/player/htm/ki000008.html)（直译） | [全日本第一位決定戦](https://www.nihonkiin.or.jp/player/htm/ki000008.html) | [전일본 제1위 결정전](https://www.nihonkiin.or.jp/player/htm/ki000008.html)（直译） | [All Japan 1st Place Tournament](https://homepages.cwi.nl/~aeb/go/games/games/AJ1st/) |
| 69 | 梦百合杯世界围棋公开赛 | 468 | [梦百合杯世界围棋公开赛](https://www.sport.gov.cn/n20001280/n20067662/n20067613/c22864378/content.html) | [夢百合杯世界圍棋公開賽](https://www.haifong.org/game/classes/1270DFFAAF3269D7793FF55248A9DDDE) | [夢百合杯世界囲碁オープン戦](https://www.nihonkiin.or.jp/match_news/match_result/363.html) | [몽백합배 세계바둑오픈전](https://www.sport.gov.cn/n20001280/n20067662/n20067613/c22864378/content.html)（直译） | [Mlily Cup](https://homepages.cwi.nl/~aeb/go/games/games/Mlily/) |
| 61 | 应氏杯世界职业围棋锦标赛 | 428 | [应氏杯世界职业围棋锦标赛](https://www.sport.gov.cn/n20001280/n20067662/n20067613/c27069198/content.html) | [應氏杯世界職業圍棋錦標賽](https://www.haifong.org/game/classes/8AD0F09CC001B8A2EEBBC376AEEAB539) | [応氏杯世界選手権](https://www.nihonkiin.or.jp/match/ohshihai/007.html) | [응씨배 세계프로바둑선수권대회](https://www.sport.gov.cn/n20001280/n20067662/n20067613/c27069198/content.html)（直译） | [Ing Cup](https://homepages.cwi.nl/~aeb/go/games/games/Ing/) |
| 73 | 中国全国围棋团体赛 | 419 | [全国围棋团体赛](https://www.sport.gov.cn/n322/n3407/n3413/c564649/content.html) | [中國全國圍棋團體賽](https://www.sport.gov.cn/n322/n3407/n3413/c564649/content.html)（直译） | [中国全国囲碁団体戦](https://www.sport.gov.cn/n322/n3407/n3413/c564649/content.html)（直译） | [중국 전국바둑단체전](https://www.sport.gov.cn/n322/n3407/n3413/c564649/content.html)（直译） | [Chinese National Team Go Championship](https://www.sport.gov.cn/n322/n3407/n3413/c564649/content.html)（直译） |
| 81 | 台湾联电杯职业围棋赛 | 403 | [台湾联电杯职业围棋赛](https://www.haifong.org/game/classes/2E725C23C4DE1EEF626BA6D71BDEC4B2)（直译） | [聯電盃職業圍棋賽](https://www.haifong.org/game/classes/2E725C23C4DE1EEF626BA6D71BDEC4B2)（直译） | [台湾聯電杯プロ囲碁戦](https://www.haifong.org/game/classes/2E725C23C4DE1EEF626BA6D71BDEC4B2)（直译） | [대만 UMC배 프로바둑대회](https://www.haifong.org/game/classes/2E725C23C4DE1EEF626BA6D71BDEC4B2)（直译） | [UMC Cup Professional Go Tournament](https://www.cmcnet.com.tw/files/20240710115110847.pdf) |

TEST、PROD 均覆盖 2,198 盘。仅绑定现有 owner 和空 name 前像；保留既有棋局关联与 raw EV。

包目录：`/tmp/kifu-event-next-high5f-20261005`。两环境 `bundle.pending.json`、`target-preimages.json`、`validation.pending.json`；共享 `registry.json`、`research.pending.jsonl`、`sources/manifest.json`。

## 直译说明

- `46-cn`：Render 全日本第一位決定戦 in Simplified Chinese as 全日本第一位决定战, preserving All-Japan first-place identity.
- `46-tw`：Render the Japanese 第一位決定戦 as 第一位決定戰 in Traditional Chinese, preserving 全日本.
- `46-ko`：Translate 全日本第一位決定戦 as 전일본 제1위 결정전. This retains the national scope and first-place decision competition, distinct from Kansai Ki-in and the earlier Nihon Ki-in title.
- `69-ko`：Render 梦百合杯世界围棋公开赛 as 몽백합배 세계바둑오픈전, preserving sponsor, world, Go and open tournament scope.
- `61-ko`：Render 应氏杯世界职业围棋锦标赛 as 응씨배 세계프로바둑선수권대회, preserving Ing sponsor identity and the world professional Go championship.
- `73-tw`：Convert 全国围棋团体赛 into Traditional Chinese 全國圍棋團體賽 with explicit 中國 country scope.
- `73-jp`：Render 全国围棋团体赛 as 全国囲碁団体戦 with 中国 country scope; preserve the domestic team competition rather than individual or international play.
- `73-ko`：Render 中国全国围棋团体赛 as 중국 전국바둑단체전, preserving national domestic team competition scope.
- `73-en`：Translate the Chinese national team Go competition as Chinese National Team Go Championship. Team describes the domestic competition format, not matches of China's national representative team.
- `81-cn`：Convert 『聯電盃』職業圍棋賽 into Simplified Chinese 联电杯职业围棋赛, omit the sponsor's typographic quotation brackets, and add 台湾 to preserve this domestic competition identity.
- `81-tw`：Normalize the officially captured 『聯電盃』職業圍棋賽 to the display title 聯電盃職業圍棋賽 by removing only typographic quotation brackets. This is a declared title rendering, without a claim that the unquoted target was found verbatim in the captured body.
- `81-jp`：Render the Taiwanese 『聯電盃』職業圍棋賽 as 台湾聯電杯プロ囲碁戦, retaining the sponsor and professional Go competition scope.
- `81-ko`：Render the Taiwanese professional Go tournament as 대만 UMC배 프로바둑대회. UMC is explicitly identified in the same native Haifong source as the sponsoring 聯華電子 company.

## 身份边界

- `46`：The All Japan first-place title 全日本第一位決定戦 held in 1970–1975, identified by Nihon Ki-in's Otake biography and CWI's dedicated title section. CWI separately describes the 1949 All Japan Hayago event and earlier Nihon-Kiin first-place predecessor; no membership of those distinct scopes is added here.
- `69`：The Mlily-sponsored world Go open tournament beginning in 2013, open to professionals and qualified amateurs. This is the recurring open championship, not the separately sponsored Gu Li–Lee Sedol ten-game match.
- `61`：The Ing-sponsored world professional individual Go championship, founded in 1988 and held on a four-year cycle; this is distinct from the Changqi Cup and amateur Ing events.
- `73`：The Chinese national domestic team Go competition, explicitly listed separately from national individual and league competitions in the Chinese sports authority's description. Existing approved linked games and editions are unchanged.
- `81`：The Taiwan Chi Yuan professional UMC Cup begun in 2020 and held for four editions through 2023. It is distinct from the UMC Millennium Cup in 2000 and from the separate UMC-sponsored rapid Go competition. Haifong identifies the native title and UMC sponsor, while CMC's official English annual report names the UMC Cup Professional Go Tournament among Taiwan Chi Yuan's four professional competitions.
