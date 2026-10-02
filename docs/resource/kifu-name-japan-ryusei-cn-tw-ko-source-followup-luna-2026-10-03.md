# Japan Ryūsei CN/TW/KO source follow-up — Luna — 2026-10-03

Status: additional source evidence only. Candidate forms below are documented usage, not approved translations, event identity decisions, or link authorization.

## Findings

### Mainland Chinese (zh-Hans)

The mainland Go media outlet FoxWQ (野狐围棋) explicitly distinguishes Japan's tournament as `日本龙星战` from China's own `中国龙星战`. Its report on the 2014 China-Japan champions match calls the former a traditional Japanese event, names the Japan Go and Shogi Channel as sponsor, gives the 24th edition, and contrasts the Chinese series started with the same model. This is strong contextual evidence for real professional-media usage; it is not a federation-issued canonical locale string. A 2025 report uses `日本第34届龙星战` in the same Japan-only context.

Sources: [FoxWQ 2014 champions match report](https://www.foxwq.com/news/8091.html) and [FoxWQ 2025 34th-edition report](https://www.foxwq.com/news/listid/id/16525.html). Captured response body hashes are in the packet manifest.

### Traditional Chinese (zh-Hant)

No Taiwanese Go federation/institution source found in this bounded pass that names the Japanese series. Haifong Go Institute's official catalog has its own Taiwan event named `龍星賽`; that is evidence of a potentially confusing local same-family name, not a translation of Japan's 竜星戦. A personal Taiwanese Go blog post (2013) titled `日本龍星戰新銳對決` explicitly says its content is translated from the 2013-11-11 issue of Weekly Go (`週刊碁`) and refers to the 23rd edition. This is useful evidence of Traditional Chinese editorial usage, but the blog is a secondary translator and was not upgraded to institutional authority. Treat `日本龍星戰` as an attested lead pending a Taiwan publisher or institution source.

Sources: [Haifong Go Institute tournament catalog](https://www.haifong.org/game/classes/F383ED878704891477874E7B7A07C4EC) and [Taiwanese Go blog's translated Weekly Go item](https://koubokukei.blogspot.com/2013/). The blog page is a large monthly archive; the packet retains the fetched body and the relevant entry can be found by its exact title.

### Korean (ko)

The Korean Baduk Federation's first-edition report documents a Korean tournament called `용성전` (1st edition in 2018), hosted by the Korean Baduk Federation with Baduk TV broadcast and Japanese Go/Shogi Channel sponsorship. A 2021 KBF article says the sponsor-backed tournament is held under the same name in Japan, China, and Korea. A 2019 KBF report describes a separate `한ㆍ중ㆍ일 용성전` (Korea-China-Japan Ryusei event), names the Japan, China, and Korea national champions as participants, and explains that the former China-Japan champions event ended when the tri-nation event was created. These are authoritative Korean-language sources for the Korean term, but they establish that the unqualified Korean string `용성전` is ambiguous across national series. This pass did not find a KBF source specifically naming the Japanese domestic series `일본 용성전`; retain it as unresolved rather than infer a canonical translation.

Sources: [KBF first Korean champion report](https://www.baduk.or.kr/news/report_view.asp?news_no=2720), [KBF 2021 series overview](https://m.baduk.or.kr/news/B01_view.asp?news_no=3707), and [KBF 2019 tri-nation event report](https://m.baduk.or.kr/news/B01_view.asp?news_no=2957).

## Captured evidence packet

Raw response bodies and a mode-0600 manifest are stored in `~/.local/share/kifu-name-audit/2026-10-03/japan-ryusei-cn-tw-ko-followup-luna/` (directory mode 0700). Manifest entries include exact URLs, language, source type, byte counts, and SHA-256.

| Capture | Source and language | SHA-256 |
|---|---|---|
| `foxwq_japan_china_match.body` | FoxWQ, zh-Hans | `e0befca60d3093b04c2d3f2c369c304851f4a51735bb5e7e44a3525e4bcf9f20` |
| `foxwq_japan_2025_edition.body` | FoxWQ, zh-Hans | `2db393a7f4f4c7410611db5680ba7eb9d84b0faadf7612786e145a0c69adcf53` |
| `kbf_korean_first_champion.body` | Korean Baduk Federation, ko | `a3468be1bd4ed203c2c6b29ddee1216a064b225282406168272ca54e13ea0919` |
| `kbf_korean_vs_other_countries.body` | Korean Baduk Federation, ko | `0add5bfb5402d7f9180e7f7f7687e7b078e391e5136bf6e043e25cfcf92ac013` |
| `kbf_korea_china_japan_series.body` | Korean Baduk Federation, ko | `546d818fef788b7efaec0b5bff53c2379e58c3ecae3ca4a214bd170784f35920` |
| `haifong_taiwan_own_ryusei.body` | Haifong Go Institute, zh-Hant | `a4c904c5f213ee12736311af347524bcffd0c34f0a6a2f0c73d3da1ac841ff55` |
| `taiwan_translation_lead.body` | Personal blog translating Weekly Go, zh-Hant | `abda9b1e3b59fbfaa567ea258a64bd1c3c1c968dedfc0cba6f0d6e48111a8043` |

This pass did not find a China Weiqi Association article specifically naming the Japanese domestic series, nor a Taiwan institutional article doing so, nor a Korean federation article using a uniquely Japan-scoped Korean series label. The mainland Go press and Korean federation evidence above materially clarify actual usage and ambiguity; gaps remain for institution-grade Traditional Chinese and unambiguous Korean localization.
