# Oza preliminaries and Japanese NHK Cup source memo (2026-10-03)

Read-only source research for two high-coverage event cores. No event identity, translation, alias, candidate, database link, or production change is approved.

## Frozen production scope and component coverage

Input: `/Users/fan/.local/share/kifu-name-audit/2026-10-02/kifu-event-groups-prod-v4-20261002.json.gz`, file SHA-256 `ae483b833c73879cf9b5544060d3857f1898806fddb76c93c2e6e0bda6716d05`, inventory SHA-256 `2cad3eb47908cc585c1090cd79e9209e8815b7025fef9724b0cedf2ca8b0b8d9`.

| Core | Albums | Raw values | Component shape |
|---|---:|---:|---|
| `日本王座战预选` | **725** | **39** | 723 `explicit_components` + 2 `single_edition_fragment`; edition plus occasional round |
| `日本NHK杯快棋赛` | **648** | **116** | 647 `explicit_components` + 1 `single_edition_fragment`; edition plus optional round |

For Oza, editions are `2, 8–10, 13–15, 20–23, 28, 33, 38, 44, 46, 50, 52–73`, with one `届` spelling (`第62届`) among otherwise `期`; only three rows carry parsed rounds (`第2轮` once and `第3轮` twice), and two rows use the `日本第54/55期王座战预选` fragment form. For NHK, edition values span `3, 6–9, 11–30, 32, 33, 35–67` with both `期` and `届`; parsed rounds use `1/一轮`, `2/二轮`, and `3/三轮`, while three edition-only raw forms and one `日本第43期NHK杯快棋赛` fragment remain in the finite scope. The v4 artifact cannot establish whether missing editions represent absent source rows.

## Oza base-name evidence

Capture directory: `/Users/fan/.local/share/kifu-name-audit/2026-10-03/oza-nhk-five-captures/`, mode `0700`; bodies and manifest mode `0600`.

| Locale | Source and exact witnessed form | Pending interpretation | Body SHA-256 |
|---|---|---|---|
| `cn` | Chinese Wikipedia article identifies the Japanese series as `王座戰`/`王座战`, founded in 1953, with Japanese organizers and a preliminary stage. [Source](https://zh.wikipedia.org/wiki/%E7%8E%8B%E5%BA%A7%E6%88%B0_%28%E6%97%A5%E6%9C%AC%E5%9C%8D%E6%A3%8B%29) | `王座战` as a source-observed Chinese base; source is secondary and requires professional corroboration | `03413734b4f2d29231924c2d7baa7f8aeda986deefa9ce61f5fe640cf8121b4e` |
| `tw` | Haifong Go Institute's specialist archive has the event `日本王座戰在台北` and uses `王座戰` for the Japanese title series. [Source](https://www.haifong.org/game/030E25FFE6411C47169D382615F7466B) | `王座戰`; the Taipei exhibition/event page is not evidence that every production preliminary row is Taiwan-related | `47fa4a682148857ce610138f9a068fd755bd32bb80059c94f5682d9edc75db84` |
| `jp` | Nihon Ki-in official archive calls the series `王座戦`, lists organizers, 1952 founding, 16-player main tournament, and separate `予選B・C`. [Source](https://archive.nihonkiin.or.jp/match/oza/) | `王座戦`; the official page directly supports the base and the preliminary qualifier boundary | `e4f71b7c8a9054aca6151c9c8fec6bdf3decf51c9e9084ae29263cf42c9ecfd0` |
| `ko` | Korean professional Go archive Kifubara identifies `왕좌전(王座戰)` as a Japanese professional title and names the Nikkei sponsorship and 1953 origin. [Source](https://kifubara.app/ko/tournaments/32481df3-45e6-43b2-8e0a-c38e270ea1bb?edition=416efa86-b770-4e18-b052-794b8ea0433f) | `왕좌전`; specialist source, pending independent review for product wording | `0e11a999bb94daf50bc8581b5443acbbfaa80fe3ae6d69fc594ef0db04f8325d` |
| `en` | CWI professional archive uses `Oza title games` and `Oza (王座) title match`, with numbered games. [Source](https://homepages.cwi.nl/~aeb/go/games/games/Oza/) | `Oza`; archive does not itself define the preliminary-stage label | `0d55026da787f1b5f8e9434e1c29bab17da58f76270cdaf31ecc5a1abadf6544` |

Oza identity is well corroborated, but the selected core is specifically the Japanese preliminary stage. The Chinese raw qualifier `日本` and parser's two fragment forms must remain finite scope constraints. Do not translate or merge the core with the unrelated North American Oza or student World Student Oza.

## NHK base-name evidence

| Locale | Source and exact witnessed form | Pending interpretation | Body SHA-256 |
|---|---|---|---|
| `cn` | Chinese Wikipedia identifies `NHK杯电视围棋淘汰赛` as the Japanese NHK televised Go rapid tournament and describes its format. [Source](https://zh.wikipedia.org/wiki/NHK%E6%9D%AF%E7%94%B5%E8%A7%86%E5%9B%B4%E6%A3%8B%E6%B7%98%E6%B1%B0%E8%B5%9B) | `NHK杯电视围棋淘汰赛`; secondary source only, pending professional corroboration | `3c9fa49fecb16a9123465453e90688f360893c87db06a95d9e11dfca2e2bbe2f` |
| `tw` | The same article's Traditional variant is titled `NHK杯電視圍棋淘汰賽`. [Source](https://zh.wikipedia.org/wiki/NHK%E6%9D%AF%E7%94%B5%E8%A7%86%E5%9B%B4%E6%A3%8B%E6%B7%98%E6%B1%B0%E8%B5%9B?variant=zh-tw) | `NHK杯電視圍棋淘汰賽`; variant capture is editorially useful but not an independent Taiwan source | `6298453ceec55fc94cc74becda2150537a58bafa7665488887db747884dd7c53` |
| `jp` | Nihon Ki-in official archive calls it `NHK杯`, lists organizers NHK/Nihon Ki-in, a 50-player selection tournament, 1953 founding, and 30-second byo-yomi. [Source](https://archive.nihonkiin.or.jp/match/nhk/) | `NHK杯` or full `NHK杯テレビ囲碁トーナメント`; compact product form requires review | `7d6586e2d2fcc7cd3c31db1da949ccaf72f0b1af93b6d586e642fc89496d4ddd` |
| `ko` | Korean-language NHK Cup article uses `NHK배` and identifies the Japanese broadcast cup category, but is a community reference page rather than a federation archive. [Source](https://namu.moe/w/NHK%EB%B0%B0) | `NHK배`; HOLD pending a Korean professional/federation source | `793fb11066fb660d1d39d6296867f8fce47401abb05d02188c85c057db88ae3e` |
| `en` | CWI professional archive calls it `NHK Cup`, describes it as a radio/television blitz tournament, and lists editions and years. [Source](https://homepages.cwi.nl/~aeb/go/games/games/NHK/) | `NHK Cup`; archive form supports the base, not the Chinese “televised Go elimination” expansion | `b5292bc9d28e51daf1616a65b28d8035f802d58f9d00770dc24c699bdd376e4c` |

NHK has a genuine cross-language naming conflict between the official compact Japanese `NHK杯`, the full Japanese `NHK杯テレビ囲碁トーナメント`, and Chinese descriptive forms. The v4 core's `日本` qualifier is useful for disambiguation, but should not be silently translated into an event name. The round values are stage components and must stay separate from the base.

## Pending blockers and batch potential

- Oza: verify all 725 rows belong to the Japanese professional Oza preliminaries; distinguish preliminary groups from main tournament, title match, and unrelated Oza datasets. The 39 raw labels are a bounded 725-album review batch.
- NHK: verify the 648 rows against Japanese NHK Cup source provenance; resolve whether edition-only rows and the `日本第43期...` fragment belong to the same series. The 116 raw labels form a bounded 648-album batch.
- `cn`/`tw` NHK sources and `cn` Oza source are secondary references; `ko` NHK remains HOLD. Do not treat source coverage as translation approval.
- Historical component differences (`期`/`届`, Arabic/Han numerals, optional `日本`, and optional rounds) require an explicit finite renderer rule after independent review.
