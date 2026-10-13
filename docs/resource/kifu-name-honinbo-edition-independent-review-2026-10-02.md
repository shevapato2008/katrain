# Independent Honinbo edition identity review (2026-10-02)

## Decision for the frozen cohort

**Approve the series identity boundary for all 1,617 album associations in the exact `english_ordinal_edition` / `Honinbo` group.** The 34 raw values are `1st Honinbo` through `34th Honinbo`. Their common event identity is the professional **Honinbo title series**; the leading ordinal is the edition, and each existing `round_name` is a separate stage/round value. There are **no row-level identity HOLDs within this exact frozen cohort** on the evidence checked below. This is an identity-scope decision, not an approval of a particular event ID, 11-language display names, live production linkage, or uniqueness of game content.

The decision does **not** include the 234 other Honinbo-like raw values / 1,704 rows in the same inventory. Those include reversed or joined ordinals, qualifier and final labels, women's and amateur events, and historical or commemorative uses. Similar wording alone is insufficient to attach them to this event identity. Keep the two totals separate: **1,617 in scope; 1,704 adjacent and unresolved or excluded**.

## Independent checks

| Check | Result |
|---|---:|
| Exact group members / selected frozen production associations | 34 / 1,617 |
| Edition numbers represented | Every integer 1–34 |
| Distinct, non-null selected `round_name` values | 77; all 1,617 non-null |
| Selected source links | 1,617 CWI `source_path` links; 1,617 distinct inventory path strings |
| Mapped SGF files found in the local CWI archive | 1,617 associations, resolving to 1,616 physical archive paths |
| Archive SGF `EV` versus inventory `event` | 1,617 exact matches; 0 missing or mismatched |
| Archive SGF `RO` versus inventory `round_name` | 1,617 exact matches; 0 missing or mismatched |
| SGFs under `games/Honinbo/{edition}/` | 1,560; all directory numbers match the row edition; all 34 editions represented |
| SGFs under auxiliary archive paths | 57: `Cho_Chikun` 26, `Go_Seigen` 21, `people` 10; all have matching `EV` and `RO` |
| Distinct archive-byte SHA-256 values among selected associations | 1,616 |
| Other case-insensitive Honinbo-like inventory values / rows | 234 / 1,704, outside this group |

The one archive-path collision is album IDs **24560** and **152132**. Their distinct inventory source paths, `data/kifu-album/Go_Seigen/1941-01-01.sgf` and `data/kifu-album/CWI_History_Full/Go_Seigen/1941-01-01.sgf`, both map to `games/Go_Seigen/1941-01-01.sgf`. Thus the 1,617 figure counts album associations, not necessarily 1,617 different games. This collision does not change either row's series identity.

The official Nihon Ki-in [Honinbo Title archive](https://archive.nihonkiin.or.jp/match/honinbo/index-e.html) explicitly identifies the tournament, distinguishes the title match from the league, and lists editions 1–34 continuously. Its [Japanese historical record](https://www.nihonkiin.or.jp/match/honinbo/archive.html) presents 本因坊戦 as the series with numbered 期. CWI's [Honinbo title-games index](https://homepages.cwi.nl/~aeb/go/games/games/Honinbo/) lists those edition numbers and points to per-edition subpages for league results. CWI's [first-edition page](https://homepages.cwi.nl/~aeb/go/games/games/Honinbo/01/index.html) specifically says the tournament began in 1939 with preliminaries before the 1941 title match. These sources support retaining preliminary, league, and title-match games under the same series while preserving their stages. They also explain why game dates need not equal the listed title-match year. The CWI index separately lists honorary player titles and Honinbo names, so an ordinal plus `Honinbo` alone would not have sufficed without the SGF and archive-path checks.

## Pins, method, and limits

This review reads the frozen inventory timestamped `2026-10-01T18:11:45.460901Z` and its derived event group. It is not a fresh production query. The local artifacts and SHA-256 values are:

| Artifact | SHA-256 of file |
|---|---|
| `/Users/fan/.local/share/kifu-name-audit/2026-10-02/kifu-name-inventory-prod-v2-20261002.json.gz` | `518748084105398b4faeadc090d54f4a033b282a9402db20d2b0564fab465bd9` |
| `/Users/fan/.local/share/kifu-name-audit/2026-10-02/kifu-event-groups-prod-v4-20261002.json.gz` | `ae483b833c73879cf9b5544060d3857f1898806fddb76c93c2e6e0bda6716d05` |
| `/Users/fan/.local/share/kifu-name-audit/2026-10-02/park-junghwan-identity-work/cwi-full-archive/games.tgz` | `935522a59817c12b37227e843cd3b4bc8d7025e32e0e6fbc80b66d828dbbffcad` |

The inventory's internal canonical SHA-256 is `66b8946d908468c5f9c8f0dc8ef4b4ceddb76d840ef42f5cff5122fc5744b3a3`; the group's internal SHA-256 is `2cad3eb47908cc585c1090cd79e9209e8815b7025fef9724b0cedf2ca8b0b8d9`, and it declares the same inventory hash as input. The CWI archive was obtained from [`games.tgz`](https://homepages.cwi.nl/~aeb/go/games/games.tgz); its saved HTTP headers report `200 OK`, 46,246,395 bytes, `Last-Modified: Fri, 25 Sep 2026 20:32:55 GMT`, and `Date: Fri, 02 Oct 2026 11:01:37 GMT`.

I selected group members by exact `grammar` and `core`, then selected associations by exact raw `event` equality. For archive lookup I removed `data/kifu-album/`, then removed an optional `CWI_1950_1978/` or `CWI_History_Full/` prefix and prepended `games/`. I streamed the tarball once, extracted each selected member, and compared its SGF `EV` and `RO` values to the inventory row. The 1,560 numbered-directory cases also passed numeric edition comparison. Auxiliary paths were checked by SGF fields but do not have edition-number directory corroboration. No local imported SGF files or live database rows were compared byte for byte with the tarball, and no assertion of complete production display coverage follows.

The companion [scope note](kifu-name-honinbo-edition-scope-2026-10-02.md) records edition and adjacent-label counts. The [11-language source memo](kifu-name-honinbo-11lang-source-memo-2026-10-02.md) records candidate name forms. **Name-form selection remains pending**, including the Korean alternatives and lower-confidence Ukrainian evidence. A future event-ID assignment must still verify the selected canonical event record and attach only the 1,617 exact-cohort rows unless other raw families receive their own row-level evidence.
