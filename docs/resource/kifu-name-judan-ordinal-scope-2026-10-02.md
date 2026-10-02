# Judan ordinal series: bounded event identity scope (2026-10-02)

This is a read-only producer audit for the 1,384 frozen albums whose exact raw event is `1st Judan` through `18th Judan`. It proposes a finite event-identity review cohort, not an approved event ID, translation, album link, or production write.

## Series anchor and cohort boundary

The [Nihon Ki-in's official Judan archive](https://archive.nihonkiin.or.jp/match/jyudan/index-e.html) identifies `Judan Title` as a tournament, gives 1961 as the founding year, and lists the numbered first through eighteenth terms separately from the title holders. The [eleven-language source memo](kifu-name-judan-11lang-source-memo-2026-10-02.md) records pending local-language name evidence. The ordinal should remain edition metadata; the stable event identity is the Japanese professional 十段戦, distinct from Korea's Siptan event and from a player's dan rank. The official page's winner year is not assumed to be every qualifier game's calendar year.

The frozen production inventory (`inventory_format=2`, canonical SHA-256 `66b8946d908468c5f9c8f0dc8ef4b4ceddb76d840ef42f5cff5122fc5744b3a3`) has **1,384** exact-ordinal rows in 18 raw values. All have `event_id=null` and a `CWI` source link. Of these, **1,345** have a unique source path in `CWI_1950_1978/Judan/<edition>/...` whose directory number equals the raw-event ordinal. The other **39** come from Go Seigen, Cho Chikun, or unusual-game directories; keep them outside the direct-path proposal pending row-level source review. Three of the 39 are under `unusual/illegal_ko_*`.

| Edition | Direct-path rows | Edition | Direct-path rows | Edition | Direct-path rows |
|---:|---:|---:|---:|---:|---:|
| 1 | 69 | 7 | 78 | 13 | 103 |
| 2 | 69 | 8 | 85 | 14 | 108 |
| 3 | 74 | 9 | 87 | 15 | 95 |
| 4 | 71 | 10 | 83 | 16 | 31 |
| 5 | 74 | 11 | 100 | 17 | 35 |
| 6 | 76 | 12 | 101 | 18 | 6 |

The 1,345 direct-path rows span source dates `1961-07-19` to `1978-12-21`; none has a missing date or player name. These dates are source-record dates, not independently verified event schedules. Edition directories and metadata are evidence from the same CWI publication chain, so their agreement alone is not independent confirmation of every game.

## Public archive body cross-check

The existing local copy of CWI's public `games.tgz` (46,246,395 bytes, SHA-256 `935522a59817c12b37227e843cd3b4bc8d702e32e0e6fbc80b66d828dbbffcad`) contains the **exact relative member path for all 1,345** direct-path rows. I parsed each archive member with the application's SGF parser and compared its root `EV` or `GN`, `DT`, `PB`, and `PW` to the frozen inventory row. All four fields match for **1,345/1,345**; the controlled artifact records each member's byte SHA-256 and observed root fields. This verifies archive-to-inventory root agreement, but does not yet compare every live production SGF byte or mainline, nor independently verify each game's event assignment.

Controlled artifacts under `/Users/fan/.local/share/kifu-name-audit/2026-10-02/judan-ordinal-scope/` have directory permission `0700` and file permission `0600`:

| Artifact | Rows | SHA-256 |
|---|---:|---|
| `direct-path-rows.jsonl` | 1,345 | `3a417a0768146db7a57f060616c0a7fc5d4966dc865672273b30a789f1904014` |
| `hold-other-path-rows.jsonl` | 39 | `f88762f9ccc249516e017e24c3d1e2af68b4352a92f03ae7ee60d01274da668a` |
| `direct-path-archive-root-evidence.jsonl` | 1,345 | `368aff854d0d119a26f2e34c5ebb19959426f268ae35c904659f5760d639742d` |

The artifact row key is album ID; it retains exact raw event, edition, source path/link ID, existing event FK, source date and both names. The archive-root artifact adds the exact archive member path, member-byte hash, observed root fields and four comparison booleans. The proposed review scope is only the 1,345 direct-path rows. The 39 holds and other `Judan`-like raw values must not be swept into it.

Next gate: an independent reviewer should compare the bounded cohort and archive evidence with official series/edition records, spot-check full game contents and anomalies, and sign only a defensible finite subset. These rows have ordinary raw `EV` event values; they need a reviewed `event`-slot name/link batch, not the separate second-`GN` selection mechanism. Before such a batch, recapture current production inventory/catalog/SGF preimages and bind exact album IDs, edition/round preservation, source checks, eleven reviewed names, and undo proof. No such batch or approval exists yet.
