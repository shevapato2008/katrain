# Independent review: raw-player ranks 101–150 source candidates

Date: 2026-10-03. This is a source-only review of the unsigned Luna packet. It does not approve candidate names, identity bindings, database changes, album slots, or production writes.

## Reviewed inputs and exact hashes

- Source memo `kifu-name-player-ranks101-150-source-candidates-luna-2026-10-03.md`: SHA-256 `3c2c1f3e9baf3c2527cef8d20600f2229ddbc92f161c86bba1babf1987df9f42`.
- Protected packet: `~/.local/share/kifu-name-audit/2026-10-03/player-ranks101-150-source-luna/`.
- `manifest.pending.json`: SHA-256 `14d7563c8d128b056bf78c1f713e19f33c5cdf3c01db7ce0239f99beedda4121`.
- `primary-language-cells-all250.pending.jsonl`: SHA-256 `02b05e101ab6c6b5da2afb7692609479694cfd2a0a14663b892da8d05831f48c`.
- `frozen-frequency-ranks101-150.json`: SHA-256 `1eede4c20078f5ea1f7764a7691cafd7880affec66243ad3074bd27d81cbc954`.
- Frozen historical clone compressed file: SHA-256 `e320eaf300bbbeffa4fdb1fca006b2d516ccb041653c58e192cd1a483490597e`; embedded inventory SHA-256 `f4907ffbe70d62b4b77f6d3bf5ba7ed789f2685f46eff7ffdfe080f2abc4bab1`.

## Independent checks

I decompressed the frozen clone and independently counted nonempty raw strings at `album_associations` indexes 2 and 3 across 173,025 rows, sorted by descending count then Unicode raw string, and assigned one-based ranks. The computed ranks 101–150 exactly equal the packet's 50 rows; ranks 89–100 reproduce the retained prior twelve pairs. The canonical compact JSON SHA-256 for ranks 101–150 is `62bfce2161da22917d96c927988d4653a514b5c8b521eb45b400e523c300044d`. Rank 150 is 金惠敏 (476) and rank 151 is 白洪淅 (475). This verifies derivation from the identified clone, not from an independently supplied rank-101–150 source.

All eleven manifest-listed artifact hashes match their files, and the combined 250-cell file equals the concatenation of the two 125-cell files. I independently recalculated **109 PASS / 136 HOLD / 5 EXCLUDED_APPROVED**. Per language (`cn / tw / jp / ko / en`), PASS counts are **29 / 2 / 21 / 30 / 30**, HOLD counts are **23 / 47 / 28 / 19 / 19**, and each language has one excluded cell. PASS occurrence sums reproduce **14,430 / 1,003 / 11,447 / 16,551 / 16,551**. These are per-language raw-string opportunities, not distinct games.

I checked **all 109 PASS cells** against the retained page bytes: their file SHA-256 values and HTML language tags agree with the cell records. For the 107 GoRatings PASS cells, the page's literal `h1` equals the recorded displayed name. Each cell's profile ID and DOB agree with its identity crosswalk; the profile body contains the linked official profile URL. For all 30 PASS identities, the saved official page hash matches its crosswalk and its full DOB is visible in the official page text. This includes Nihon Ki-in dates written with an era in parentheses. All 30 Korean PASS strings also appear exactly as the person heading in a captured KBA profile; Hikosaka's KBA profile omits the DOB, so his DOB comes from Nihon Ki-in. For the two Taiwan cells, the saved Haifong pages have `html lang="zh-tw"`, the correct person in their professional-name `h3`, and the stated DOB; their GoRatings profiles also link directly to the same Haifong URL. This is a byte-level review of the retained captures, not a fresh assessment of the live websites or of independent preferred transliterations.

The HOLD distribution is consistent with the stated conservative policy: 19 rows lack a defensible same-ID official crosswalk (14 in the first half, five in the second), nine Japanese cells have source-script or formatting concerns, four Chinese cells have script/form concerns, and Taiwan remains HOLD absent a Taiwan-specific source. 黄云嵩 has a localized profile but no official DOB link and correctly remains all HOLD. I found no basis in the retained packet to promote any HOLD. The five excluded cells all belong to rank 147 牛雨田; an exact `raw_value` match exists in a protected approved JSON artifact, including `raw-player-next7-phase4-final-independent-review-sol/final-bundle-review.approved.json` (SHA-256 `3323028db6ac38a8a7e3ec772eada6c6d22c36c9d4b39b0eeee42e72b8a7455c`).

## Corrections and disposition

1. **No PASS/HOLD/EXCLUDED status changes** are supported by this review. All 109 positive cells remain unsigned source candidates; all 136 HOLD cells stay HOLD; all five 牛雨田 cells stay excluded.
2. The source memo's first-half sentence saying “Eleven additional same-ID profile pages were captured for 黄云嵩” should say **four locale pages** (`zh`, `ja`, `ko`, `en`). The first-half GoRatings capture file has 48 records total: four each for twelve names, including 黄云嵩.
3. The `observed_name` field in the two TW PASS cell records contains a **browser title**, `海峰棋院-徐靖恩` or `海峰棋院-楊子萱`, rather than the exact player display. The saved page's professional heading is `徐靖恩 七段` or `楊子萱 六段`; the candidate player strings are **徐靖恩** and **楊子萱**. Any downstream candidate extraction must use the person heading without the site prefix or rank suffix. The two TW PASS evidence decisions remain supported.

No database write, candidate approval, or git commit was performed.
