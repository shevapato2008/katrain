# Independent review of pending ranks 101–150 primary-five packet

Reviewed 2026-10-03. This review is independent of the producer and is bounded to **external identity correspondence and exact language display evidence**. It does not approve a raw owner, category, album slot, person FK, name preimage, final candidate, or write.

## Bound inputs

- [Producer pending memo](kifu-name-player-ranks101-150-primary-five-producer-pending-codex-2026-10-03.md): SHA-256 `a1093b1791c20cecba25df1d727cda9dd2dd5f11043be48651dffdde029b324d`.
- Protected producer packet: `~/.local/share/kifu-name-audit/2026-10-03/player-ranks101-150-primary-five-pending-codex/`; `manifest.pending.json` SHA-256 `50faa85d0bcc3287ab22911600289c03d82dc2e3581eef95151ecf02e3fa74df`.
- `identity-proposals.pending.jsonl`: SHA-256 `8ab83fe21b52a332f4ae987c03eb3b6238011f4681bcd3ef9ef01a3bad5fcea1` (30 records).
- `primary-five-candidates.pending.jsonl`: SHA-256 `d7d4a58729d05da779bf58301738542791cdc2c4987baad88c0f111f05ab3623` (109 records).
- `all250-status.pending.jsonl`: SHA-256 `a6c62e53fb8e7ec4084d7a4ee03ad5d7074da1c763d94292f64efcdacb7ba037` (250 records).
- Upstream source cells: SHA-256 `02b05e101ab6c6b5da2afb7692609479694cfd2a0a14663b892da8d05831f48c`.

## Checks and verdict

I recalculated all producer file hashes and canonical source-record hashes. The 250 producer statuses match the upstream rank, raw string, language, occurrence count, decision, and source-cell hash row for row. Counts are **109 PASS source cells, 136 HOLD, five rank-147 牛雨田 exclusions**. The 109 candidate rank/language keys equal the 109 upstream PASS keys exactly. Per-language candidate counts are **cn 26, tw 2, jp 21, ko 30, en 30**; occurrence sums are **14,430 / 1,003 / 11,447 / 16,551 / 16,551**.

For all 30 identity proposals, the proposed GoRatings ID, DOB, official URL, official body file/hash, and source crosswalk record hash agree with the upstream crosswalk. Each GoRatings profile links to the stated official page. The captured official page hash matches, and its DOB appears in the body. The four Nihon Ki-in DOBs with an era in parentheses were checked in that form. No duplicate raw value or GoRatings ID occurs among the 30. The producer leaves every `person_fk` and `raw_slot_binding` null and every album-link list empty.

For all 109 display records, the source-cell hash, source-body hash, actual HTML language, raw string, rank, occurrence count, and exact player display were checked against retained bodies. All 107 GoRatings values equal the page `h1`. The two `tw` values are **徐靖恩** and **楊子萱** in Haifong `zh-tw` professional `h3` headings, with the site title prefix and rank removed. Every proposed name preimage and raw-slot binding is null, and every `production_write_ready` flag is false.

| Gate | PASS | HOLD | Meaning |
| --- | ---: | ---: | --- |
| Exact display source facts | **109** | 0 | The recorded strings are present in the retained target-language sources. |
| Identity proposal records as written | **26** | **4** | Four official-name fields contain a placeholder rather than the recorded name. |
| Combined identity-and-display candidate evidence | **94** | **15** | PASS only for the 26 identities with complete records; the 15 displays attached to the four held identities wait for record correction. |
| Final candidate approval / write readiness | **0** | **109** | Raw owner/category applicability, exact slots, FK, and preimage remain outside this review. |

The four held proposal records are below. Their source pages otherwise support the profile link and DOB; the HOLD concerns the packet's incorrect `official_identity_name_as_recorded` field. A corrected, rehashed producer record can be reviewed without new source research.

| Raw value | Rank | Attached display cells | Current field | Official Nihon Ki-in `h1` |
| --- | ---: | ---: | --- | --- |
| 伊田笃史 | 128 | 3 | `official player profile` | `伊田　篤史 （イダ　アツシ / IDA, Atsushi）` |
| Hane Yasumasa | 134 | 4 | `official player profile` | `羽根　泰正 （ハネ　ヤスマサ / HANE, Yasumasa）` |
| 淡路修三 | 139 | 4 | `official player profile` | `淡路　修三 （アワジ　シュウゾウ / AWAJI, Shuzo）` |
| 三村智保 | 144 | 4 | `official player profile` | `三村　智保 （ミムラ　トモヤス / MIMURA, Tomoyasu）` |

I also scanned accessible protected `*approved*.json` artifacts for exact matches to the 30 proposed `raw_value` strings and to the 109 `(language, display_name)` pairs. No exact match appeared. This is a bounded artifact scan, not a live database uniqueness or category/owner review. The earlier **牛雨田** approved match remains correctly excluded; no new category or owner is inferred for the other 49 raw strings.

The earlier independent source review's `cn 29` tally is superseded by its [dated correction](kifu-name-player-ranks101-150-independent-review-count-correction-sol-2026-10-03.md): `cn 26`. This changes no source cell status. No database or application code was changed, no final candidate was approved, and no commit was made for this review.
