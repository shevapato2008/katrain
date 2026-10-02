# Turkish and Ukrainian source check: Japanese Judan/十段戦

Research memo, 2026-10-02. This follows the [11-language memo](kifu-name-judan-11lang-source-memo-2026-10-02.md) and [Korean follow-up](kifu-name-judan-ko-source-memo-2026-10-02.md). The target is Japan's recurring Nihon Ki-in/Kansai Ki-in Go series, not Korea's separate 십단전, a shogi event, the holder's title, or a professional dan rank. This memo approves no product display name, alias, merge, or database change.

## Evidence

| Language | Inspected source and actual language | Exact witnessed form | What it establishes / limit |
|---|---|---|---|
| `ua` (`uk`) | [Ukrainian Wikipedia, “Ґо (гра),” “Організації та турніри”](https://uk.wikipedia.org/wiki/%D2%90%D0%BE_(%D0%B3%D1%80%D0%B0)), Ukrainian | `Дзюдан` | The passage introduces annually contested prestigious titles *in Japan* and lists `Дзюдан`. This identifies the Japanese Go title stem in Ukrainian context. It does not explicitly print a full name for the competition, describe its organizers, or distinguish the title holder from the series. Its `Дзюдан` link is a redlink, not a standalone article. This is one encyclopedia usage, not a federation naming rule. |
| `tr` | No inspectable Turkish Go source in the bounded searches below named this Japanese series. | — | No Turkish series form is attested by this pass. This is a search gap, not proof that Turkish usage does not exist. |

The [exact Wikidata competition item, Q2635247](https://www.wikidata.org/wiki/Q2635247), has the English label `Judan` and describes a Japanese Go competition; its displayed labels and sitelinks contain neither Turkish nor Ukrainian. Wikidata's page is English here and supplies no target-language spelling. A [Go shop on the Ukrainian federation domain](https://shop.ufgo.org/product_info.php?products_id=261) uses `Дзюдан` in a player-title list, but that product description is **Russian**, despite Ukrainian site navigation; it is not Ukrainian-language evidence. A Turkish-language [Japanese portrait search hit](https://www.jikad.org.tr/2012/index.php?id=486%3Ajapon-portreleri&option=com_content&view=article) uses `Judan` for **shogi**, so it cannot identify this Go series; the full page timed out on inspection.

## Source-based wording candidates, not attested series names

The [Nihon Ki-in's Japanese event page](https://www.nihonkiin.or.jp/match/jyudan/059.htm) gives the series core `十段戦`; its [official English archive](https://archive.nihonkiin.or.jp/match/jyudan/index-e.html) gives `Judan Title` as the tournament name and separates numbered terms. A [Japanese dictionary entry](https://kotobank.jp/word/%E5%8D%81%E6%AE%B5%E6%88%A6-77201) reads `十段戦` as `じゅうだんせん` (*jūdan-sen*) and defines it as one of Go's seven major title contests. These are identity and reading anchors, not Turkish or Ukrainian localization attestations.

| Language | Provisional construction | Explicit rule and uncertainty |
|---|---|---|
| `tr` | `Judan turnuvası` | Retain the Nihon Ki-in's official Latin stem `Judan` for `じゅうだん` and render the competition suffix `戦` descriptively as Turkish `turnuvası` (“tournament”). This is an editorial construction; neither its spelling, suffix choice, nor preference over `Jūdan` is evidenced by a Turkish Go source. |
| `ua` | `турнір «Дзюдан»` | Reuse the witnessed Ukrainian title spelling `Дзюдан` and add Ukrainian `турнір` to make the competition sense explicit for `戦`. The complete phrase is **not** witnessed on the Ukrainian page; the page attests only the title stem in a Japan-specific Go list. |

Edition numbers (`11th`–`15th` in the motivating batch) remain separate metadata. Sponsor prefixes are time dependent. Bare `Judan`/`Дзюдан` can mean a title rather than the recurring tournament unless the Go competition context is present.

## Bounded search and status

Searches used `Judan`, `Jūdan`, `十段戦`, Turkish `Japon`, `go`, `turnuva`, Ukrainian `Дзюдан`, `японський`, `го`/`ґо`, `турнір`, plus targeted searches of Turkish Go Association, Turkish Wikipedia, Merdiven Go, Ukrainian Go Federation, its forum/shop, Ukrainian Wikipedia, and Wikidata. The Turkish association [Go glossary](https://www.tgod.org.tr/go-sozlugu/) appeared in search results, but direct page inspection timed out, so it is not treated as a checked negative. No Turkish exact-entity passage or Ukrainian full competition-name passage was established in this pass. A later target-language specialist source could change either assessment.

Research agent configured as `gpt-6-sol`; no separate runtime model attestation was available. No code, database, or production changes, and no git staging or commit.
