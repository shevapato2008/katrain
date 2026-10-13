# Top 8 unanchored player names — independent exact-slot decision

- Decision JSON SHA-256: `d10556cc0ec1d4b03297b376d0c2b3586e71ba0e379a5c184596b188df7d2508`
- Database writes: **0**. Two fresh `REPEATABLE READ READ ONLY` database transactions. This is a decision, not an apply receipt.
- TEST and PROD each: **2,920 slots / 2,898 games reviewed; 940 slots approved; 1,980 HOLD**. Every approved or held `(album_id, side)` is enumerated separately for each environment in the JSON.
- Approved changes: reuse two existing Chinese identities and create one Chinese identity for the exact approved NULL slots. No five-language text is invented or approved here.

| Exact raw | Chinese identity | TEST target | PROD target | Approve | HOLD | Decision |
|---|---|---:|---:|---:|---:|---|
| `姜勋` | 姜勳 — two people | — | — | 0 | 433 | HOLD_HOMONYM_PARTITION_REQUIRED |
| `Iwamoto Kaoru` | 岩本薰 | — | — | 0 | 384 | HOLD_COMPETING_CATALOG_VARIANTS |
| `Maeda Nobuaki` | 前田陈尔 | 9839 | 4043 | 297 | 70 | APPROVE_REUSE_EXISTING_FOR_EXACT_APPROVED_SLOTS |
| `林彦丞` | 林彦丞 | — | — | 344 | 22 | APPROVE_NEW_CANONICAL_FOR_EXACT_APPROVED_SLOTS |
| `王尧` | 王垚 | — | — | 0 | 355 | HOLD_COMPETING_CATALOG_VARIANTS |
| `Fujisawa Hosai` | 藤泽朋斋 | — | — | 0 | 354 | HOLD_COMPETING_CATALOG_VARIANTS |
| `蔡竞` | 蔡竞 | — | — | 0 | 350 | HOLD_NEAR_EXISTING_CATALOG_OWNER |
| `Yoshida Yoichi` | 吉田阳一 | 9914 | 4118 | 299 | 12 | APPROVE_REUSE_EXISTING_FOR_EXACT_APPROVED_SLOTS |

The original candidate `前田陸仁` is incorrect. Maeda Nobuaki is **前田陳爾**, rendered **前田陈尔** in the existing catalog. English/Japanese biographies and the publisher author page agree on the name and reading. The existing `前田陈二` alias points to that same owner. [English Wikipedia](https://en.wikipedia.org/wiki/Nobuaki_Maeda), [Japanese Wikipedia](https://ja.wikipedia.org/wiki/前田陳爾), [Tokyo Sogensha](https://www.tsogen.co.jp/np/author/794).

**Maeda: 297 approved, 70 HOLD.** The HOLD list has 53 partial dates and 17 missing dates. Approved games span 1927-05-11/12 through 1975-02-13. His promotion history is incomplete in the consulted biographies: rank checks use the documented bounds (four dan in 1927, six in the 1937 retirement-selection event, eight in 1956, nine in 1963), without inventing missing promotion dates. Wikipedia and the publisher describe his early admission differently; the earliest approved game occurs after either account.

**Lin: 344 approved, 22 HOLD.** Haifong confirms 林彥丞, birth 2001-09-18 and rank milestones; the Taiwan Ki-in report establishes admission by 2017-01-03. All catalog, name and alias rows in both fresh snapshots were scanned for listed simplified/traditional/Roman-name forms and have no owner. Thirteen slots lack a rank; nine conflict with the recorded career. [Haifong profile](https://www.haifong.org/profession/venue/AE4B5AB0DFEB900CDE0CBD2979FAFEA0), [Taiwan Ki-in admission report](https://taiwangorg.blogspot.com/2017/01/2017.html).

**Yoshida: 299 approved, 12 HOLD.** The official profile explicitly joins YOSHIDA, Yoichi to 吉田陽一 and supplies the promotion history. Ten games have incompatible low ranks, one is in the admission year without a known admission day, and one has only a year. Existing linked album 55630 also has suspicious 1973 `3p`/January-1 metadata; it is not used as proof and is outside this approval. [Nihon Ki-in profile](https://www.nihonkiin.or.jp/player/htm/ki000023.htm).

The other five groups retain all exact slots as HOLD:

- **姜勋, 433:** KBA has two different professionals with the same Hanja 姜勳, born 1957 and 1990. Partitioning by game needs a separate decision. [Senior](https://www.baduk.or.kr/record/player_view.asp?pkey=10000015), [Junior](https://www.baduk.or.kr/record/player_view.asp?pkey=10000590).
- **Iwamoto Kaoru, 384:** professional identity confirmed, but existing 岩本熏/岩本薫/岩本薰 catalog rows compete. [Nihon Ki-in profile](https://archive.nihonkiin.or.jp/player/htm/ki001002.htm).
- **王尧, 355:** CWA identifies 王垚; existing 王垚 and 王尭 each own games. This batch chooses neither a merge nor a spelling correction. [CWA000059](https://wqapi.cwql.org.cn/playerInfo/CWA000059).
- **Fujisawa Hosai, 354:** official material ties 藤沢朋斎 to former name 藤沢庫之助; four existing canonical spellings/name-era rows need explicit owner resolution. [Nihon Ki-in](https://www.nihonkiin.or.jp/event/area/online/post_1294.html), [Chinese Wikipedia](https://zh.wikipedia.org/wiki/藤泽朋斋).
- **蔡竞, 350:** CWA confirms the name, but existing 蔡竟 owns three games. Resolve that prior owner before creating another identity. [CWA000061](https://wqapi.cwql.org.cn/playerInfo/CWA000061).

Fresh catalog candidates (not merge approval):

| Identity | TEST IDs | PROD IDs |
|---|---|---|
| Iwamoto Kaoru | 10306 岩本熏, 10307 岩本薫, 10308 岩本薰 | 4515 岩本熏, 4516 岩本薫, 4517 岩本薰 |
| 王尧 | 394 王垚, 11273 王尭 | 393 王垚, 5499 王尭 |
| Fujisawa Hosai | 11619 藤沢库之助, 11622 藤泽库之助, 11623 藤泽朋斋, 11624 藤泽朋斎 | 5850 藤沢库之助, 5853 藤泽库之助, 5854 藤泽朋斋, 5855 藤泽朋斎 |
| 蔡竞 | 11605 蔡竟 | 5836 蔡竟 |

Both snapshots were captured at approximately **2026-10-04 12:29 UTC**. All 5,840 environment-specific album preimage and SGF checks passed; every original full album row exactly matched the fresh snapshot, and each side/name/date/rank matches parsed SGF root fields. Each decision slot carries its album-row, SGF and complete source-row hashes. The frozen captures include every current catalog/name/alias row and all games referencing candidate owners.

Apply only the enumerated approved slots with a fresh plan pinned to these hashes. Preserve all other album columns. An existing target must match its exact catalog preimage; creating 林彦丞 requires its continued absence across catalog, names and aliases. Any changed album/source/target state requires rebase review. No alias, translation, staging, rename, deletion or merge is approved.

Input hashes:

- original_exact_capture: `docs/resource/kifu-player-next-unanchored-30-readonly-2026-10-04.json` — `ad362d5b2c77ef048b77594ac43ee232dd1aea1e3799ecbe777d293ba35202ba`
- original_capture_markdown: `docs/resource/kifu-player-next-unanchored-30-readonly-2026-10-04.md` — `f8c572fac72ba8dc180dbd4a47504f2a821439995f33a9ea76b19a108bf3262f`
- source_manifest: `docs/resource/kifu-player-unanchored-top8-independent-sources-2026-10-04/manifest.json` — `dc33ba0a8a427c1afc8a043ea095cf8f473bf846556af3582bb0ed7ec40cba46`
- test_supplemental_capture: `docs/resource/kifu-player-unanchored-top8-supplemental-test-readonly-2026-10-04.json.gz` — `eac6e775d5b439c0bf3b823d3ead2a4521a817ec40902ca24d359e3c2223ef78`
- prod_supplemental_capture: `docs/resource/kifu-player-unanchored-top8-supplemental-prod-readonly-2026-10-04.json.gz` — `7d1ad857851afad42c9b720205e8a5b115646b24e9c26e0186ccd310f41ecbf1`

The source manifest records successful HTML/text captures, exact hashes and retrieval URLs. Direct downloads of Japanese Wikipedia and the bare Haifong host timed out; the Japanese page is preserved as an exact `web.run open` result, and the `www.haifong.org` profile was successfully captured. Source search URLs are not identity evidence.
