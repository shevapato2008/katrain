# Japanese Oza: five primary-language source candidates

The frozen v4 event inventory groups **2,061 albums and 103 raw event labels** under `Oza`: 2,058 albums / 102 labels have an edition component, while one unparsed `Oza` label covers three albums. This is a source and display-name research batch, **not** approval that all labels belong to the Japanese professional series. The 102 component-bearing labels still need finite row/date/source checks before an event ID or localized album display is signed.

| Language | Proposed series core | Source and derivation |
| --- | --- | --- |
| Chinese | `日本王座战` | [FoxWQ professional report](https://www.foxwq.com/news/listid/id/7453.html) uses the exact phrase for the Japanese 60th title match between 張栩 and 井山裕太. |
| Traditional Chinese | `日本圍棋王座戰` | [Haifong's first-game report](https://www.haifong.org/news/content/8A4A649B26B5007EC2A65A26D77B05D4) says `日本第60期圍棋王座戰`; the proposed core removes only the edition. |
| Japanese | `王座戦` | [Nihon Ki-in's series archive](https://archive.nihonkiin.or.jp/match/oza/index.html) uses this exact name. |
| Korean | `일본왕좌전` | [Korea Baduk Association's 張栩 career record](https://www.baduk.or.kr/record/player_view.asp?pkey=20000106) calls the 59th/60th Japanese series `일본왕좌전`, matching the Chinese/Traditional 2012 context. |
| English | `Oza` | [Nihon Ki-in's English page](https://archive.nihonkiin.or.jp/match/oza/061-e.html) calls it `Oza Title`; the short proper name `Oza` also occurs in the frozen raw labels. The page's `Oza Title Match` means a final and must not label preliminaries. |

All five retained HTTP bodies returned 200; the pending packet records each body SHA-256, rendered phrase and context. The freeze is `~/.local/share/kifu-name-audit/2026-10-02/kifu-event-groups-prod-v4-20261002.json.gz`, SHA-256 `ae483b833c73879cf9b5544060d3857f1898806fddb76c93c2e6e0bda6716d05`. Pending packet: `~/.local/share/kifu-name-audit/2026-10-03/oza-five-source-pending-root/`; `candidates.pending.json` SHA-256 `6360b33052ab04015441bd392428dc5640c9558928a21d9746a1037f31a7760c`; capture manifest SHA-256 `d3a5e709e4d8f0be4b895e4a827500f505af0c4da5628c0e6d68f2fa7e4441fb`.

Next review must compare the 102 finite raw labels and underlying album dates/source paths to the Nihon Ki-in historical editions, exclude Korean or other Oza homonyms, and keep the three unparsed albums on HOLD. The Chinese FoxWQ publisher also needs a fixed source-registry entry before importer use. No database or application code was changed.
