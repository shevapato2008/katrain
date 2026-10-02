# Japan Ryūsei source precheck — Luna — 2026-10-03

Status: bounded source evidence only. This note does not approve an event identity, any localized name, or database linking.

## Frozen scope and observed distribution

Input: `~/.local/share/kifu-name-audit/2026-10-03/japan-ryusei-scope-pending/scope.pending.json`. Its SHA-256 was recomputed as `52717f27e24dcaea3d8108794b6a426ca590064b310a09e1a6931aeb1c1a741e`, matching the supplied frozen SHA. It contains 1,249 album rows and 20 exact raw values; every row has `event_id=null`, `round_name=null`, a 19x19 source, and the dates span 1990-06-11 through 2013-03-04.

| Raw label | Albums | Recorded date span |
|---|---:|---|
| 日本第1期龙星战 | 99 | 1990-06-11–1991-08-18 |
| 日本第2期龙星战 | 99 | 1991-06-17–1992-08-16 |
| 日本第3期龙星战 | 97 | 1992-06-22–1993-08-09 |
| 日本第4期龙星战 | 99 | 1993-08-17–1994-09-04 |
| 日本第5期龙星战 | 50 | 1995-09-11–1996-09-01 |
| 日本第6期龙星战 | 51 | 1996-08-30–1997-08-31 |
| 日本第7期龙星战 | 99 | 1997-08-18–1998-09-06 |
| 日本第8期龙星战 | 97 | 1998-08-10–1999-09-04 |
| 日本第9期龙星战 | 99 | 1999-07-19–2000-08-07 |
| 日本第10期龙星战 | 97 | 2000-07-24–2001-08-13 |
| 日本第11期龙星战 | 103 | 2001-08-06–2002-09-16 |
| 日本第12期龙星战 | 101 | 2002-01-01–2003-08-05 |
| 日本第13期龙星战 | 102 | 2003-08-05–2004-09-06 |
| 第16届日本龙星战第二轮 | 2 | 2007-06-21 |
| 第17期日本龙星战第一轮 | 8 | 2008-08-08–2008-08-31 |
| 第17期日本龙星战第二轮 | 4 | 2008-09-05–2008-09-14 |
| 第21期日本龙星战 | 22 | 2011-08-04–2012-04-12 |
| 第21期日本龙星战第1轮 | 1 | 2012-05-31 |
| 第21期日本龙星战第2轮 | 1 | 2012-07-16 |
| 第22期日本龙星战 | 18 | 2012-08-23–2013-03-04 |

Notes for a later reviewer: the 1st–13th edition date bands are generally compatible with sequential editions, although the catalog date can precede or follow the edition's broadcast/competition year. The raw values skip editions 14–15 and 18–20; that is a scope-selection gap, not evidence those editions did not exist. One row dated 2002-01-01 occurs under the 12th-edition label and merits checking against its source SGF before making a year claim. The 16th edition label uses `届` while the others mainly use `期`; edition 17 explicitly encodes first/second round in 12 raw strings. Sixteen rows have a round encoded in raw text, but the structured `round_name` field is null for all 1,249. The 21st-edition round-qualified labels have dates 2012-05-31 and 2012-07-16, after the main label's recorded upper date 2012-04-12; check whether `date_played` is actual play date, broadcast date, or imported metadata before inferring a phase mismatch.

## Source evidence

Bodies were captured read-only into `~/.local/share/kifu-name-audit/2026-10-03/japan-ryusei-source-precheck-luna/`; see its mode-0600 `manifest.json` for byte lengths and hashes. The directory is mode 0700. The named files are raw response bodies, not curated quotations.

| Source, language | URL | Captured body SHA-256 | Evidence and limit |
|---|---|---|---|
| Nihon Ki-in, Japanese, 22nd edition | https://www.nihonkiin.or.jp/match/ryusei/022.html | `e45126c7bed095988affe4d56d1f8322b782bbd10480b2960da2252c71186538` | Page heading `第22期 竜星戦`; identifies the tournament as `竜星戦`, organizer as Igo & Shogi Channel and Nihon Ki-in, states establishment year 1990, and lists knockout stages. The page's current top-level season content is mixed with its archived 22nd-edition section; use the section heading, not current page header, as edition evidence. |
| Nihon Ki-in, Japanese, 9th edition | https://www.nihonkiin.or.jp/match/ryusei/009.htm | `e696143f7cef6939fa4fa87e67074205ced65a396293d25ee8b0b246fbfda3e4` | Page heading `第9期 竜星戦`; official event spelling; useful edition-specific cross-check. |
| Nihon Ki-in, Japanese, historical record | https://www.nihonkiin.or.jp/match/ryusei/archive.html | `463cecef6c6cf1bbb229d9d4ca607ce975c54b146820451b0d9274ded3da59e9` | Official past-edition index, including 22nd edition and season history. |
| Nihon Ki-in, English | https://www.nihonkiin.or.jp/english/topics/11/topics2011_10.htm | `7ca67b0c89ad29b85124deb667bc9cbf9a3eaadea8dff0c63ae322e0b1721149` | Official English article calls it “The 20th Ryusei Tournament” and documents 2011 context. Evidence for an English rendering in actual Nihon Ki-in English editorial, not proof it is a formal canonical English tournament title. |
| Igo & Shogi Channel, Japanese | https://www.igoshogi.net/igo/program.html | `600edf470975c47ba85959987af9a25f752e7fbb2f624e9fc7ec5e06603362d0` | Tournament-owner broadcaster describes 竜星戦 format: 96 players in eight blocks, selection of 16 for final tournament, one-game final; confirms this is the pro tournament/program series. Current format may not apply unchanged to historical editions. |
| Igo & Shogi Channel, Japanese, Korea-series distinction | https://www.igoshogi.net/igo/korea_ryusei/image/5tornament.pdf | `5488b7241d916962983a7e014fb8ac9f75cb9cf570d02d56b454665e42634c3a` | Organizer labels a separate event `第5期 韓国竜星戦`. This warns that the bare translated phrase “Korean Ryusei” can denote a different national series, not a translated Japan event. |

Primary-source findings establish Japanese `竜星戦` and an official Nihon Ki-in English usage `Ryusei Tournament`; romanization without macron is directly attested. “Ryūsei” is a scholarly-style romanization, not the spelling shown in the official English article. The organizer and Nihon Ki-in support creation year 1990 (the official English report shows the 20th edition in 2011; do not infer exact edition start/end dates from this alone). Edition 22 official results list the block/main phase and 16-player champion-deciding tournament; the broadcaster's current overview describes 96 players, eight blocks, 16 finalists, and a single-game final. Historical formats may have changed.

## Localization evidence boundary

This pass found primary evidence only for Japanese and an official English rendering. The source search did not establish publisher/organizer-grade canonical series names in Simplified Chinese, Traditional Chinese, Korean, or the remaining target languages. Search-indexed or community usages of `日本龙星战`, `日本龍星戰`, `일본 류세이전`/`용성전`, and “Ryusei” are leads only; they are not approved translations. In particular, the broadcaster's Korea-series page uses `韓国竜星戦`, so translating by generic kanji/hanja or substituting Korean's own series name would risk conflating events.

No assertion is made here about the full 11-language target list because that list is not present in this frozen scope file. Obtain authoritative locale-specific sources or record an explicit transliteration policy in the main review before proposing canonical values. This precheck deliberately leaves event identity, labels, and links pending.
