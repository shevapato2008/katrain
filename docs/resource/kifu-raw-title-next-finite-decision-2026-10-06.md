# Next finite raw-title batches — Astra decision, 2026-10-06

**Proceed next with 阿含桐山杯本选 10 raw / 205 games, then two plain 招商银行杯 raws / 2 games.** These 12 / 207 fit the existing literal grammar and have exact cores in captured article text. No reader or schema extension is needed. This is a continuation decision, not approval of unsigned five-language candidates or a claim of current database state.

All files below are under `/tmp/kifu-event-next-high5-20261006/`. I read existing drafts and local captured HTML only. No source capture, database access, code change, or deployment was performed. The nine drafts contain 213 raw / 2,878 games, including first24 / 493; therefore 189 raw / 2,385 games remain outside that first batch.

## Immediate finite scopes

| Profile | Exact input / selector | Raw / games | Canonical SHA-256 of sorted raw strings |
|---|---|---:|---|
| agon10 | All records in `agon-preselection-translated-research-pending.json` | 10 / 205 | `2d3598c64fa103cfa1914e9942352151e81dabe76b865b546ba99341a2547a81` |
| cmb2 | `第9届招商银行杯第3轮`, `第9届招商银行杯第一轮` from `remaining-cmb-13-translated-research-pending.json` | 2 / 2 | `9e3ee2d49f318e2a7495ad4040e996d7dffee7a96d838642366d592a2864ee9d` |

The agon10 raws/counts are: `第11届阿含桐山杯本选第1轮` 49; `第11届阿含桐山杯本选第2轮` 24; `第11届阿含桐山杯本选第3轮` 14; `第11届阿含桐山杯本选第4轮` 7; `第11届阿含桐山杯本选第一轮` 5; `第12届阿含桐山杯本选第一轮` 60; `第12届阿含桐山杯本选第二轮` 25; `第16届阿含桐山杯本选第2轮` 1; `第16届阿含桐山杯本选第3轮` 1; `第十届阿含桐山杯本选第一轮` 19.

The agon11 captured HTML contains the exact core `阿含桐山杯本选` in its article heading; use that actual excerpt, not the draft excerpt whose longer wording interrupts the exact core. Keep each raw edition/round as its own lossless part; the article need not assert every edition. The existing `cmb_2006.html` article body contains `招商银行杯电视快棋赛`, which also supplies the exact `招商银行杯` core for cmb2.

Both environments' captured owners for these records are pending `unclassified_pending` with no existing names. Their captured member-ID digests agree between TEST and PROD. Digest format is canonical JSON of a list sorted by raw string, each member containing exactly `raw_value`, `raw_event_id`, and `album_ids`:

- agon10: `c42f126ebf6467d0bbeeb648737f15fa37dfd719d51bff9ab774dd410b926157`.
- cmb2: `024544d202a891cad76e994d5c598a12ad8f52729f8f49e0a080721cf21b545d`.

Canonical SHA-256 of the complete input research documents: agon file `0add9615e13d04e14d23b63fb87c7c807d421595ad92db18c49d8fd621852862`; remaining-CMB file `77ad84ebab7db737196c0d68177224ede6eaf9901a0347cc1381cf4557325bed`. Build actual per-profile manifests and bind their new hashes; the remaining-CMB document itself includes 11 records outside cmb2.

Two further grammar-compatible CMB records are `招商银行杯快棋赛第3轮` (1) and `第9届招商银行杯半决赛` (2). Their exact cores appear in related-story headings inside `cmb_2005_final.html`, rather than its main article text. Keep these 2 / 3 separate for a short evidence review; do not silently describe those headings as main article prose. If accepted, the four-record CMB scope is 4 / 5 with raw-set digest `26afd5c62c03618b4aea7102797f9956163fee856d161d14ec8651e42f62f557`.

## Minimum implementation follow-up

Keep the current owner tool and all existing locks/CAS/ledger/signature guards. Add two explicit finite profile constants for agon10 and cmb2, each pinning its exact raw-set hash, count and game total; retain first24 unchanged. Select only an allowlisted profile. Do not replace the hard pin with an arbitrary manifest-driven owner approver. Normalize these two existing draft shapes into the current `records` + per-environment `member_manifest` shape, without changing owner preimages or parser data. Re-read live complete preimages and exact public, nonduplicate, NULL-event/no-selection members before signing each environment's plan; then refresh catalog/inventory pins after owner approval and use ordinary format-2/inventory-4/no-link name bundles.

No grammar change is required for agon10 or cmb2. Five complete translations still need independent name review and actual source metadata/registry binding; these drafts are not ready-made importer research records. For Agon, review 本选 wording as a literal stage and avoid adding broader competition identity assertions to the translated title.

## Next bounded grammar work and source holds

| Existing draft | Scope | Decision |
|---|---:|---|
| `batch2-translated-raw-events-research-pending.json` | 35 / 200 | Parser parts are structurally accepted, but all 35 currently treat unsourced qualifiers/stages as part of their sourced core. Do not feed those whole cores to the current source check. First take the exact subset below. |
| `remaining-cmb-13-translated-research-pending.json` | 13 / 23 | cmb2 / 2 immediate; 2 / 3 heading-only evidence review; remaining 9 / 18 need literal component splits or core evidence. Keep the 3 Asian-TV titles / 6 games distinct from the domestic CMB family. |
| `generic-1145-translated-research-pending.json` | 89 / 1,145 | Grammar-compatible. Existing draft explicitly claims no external capture, so obtain/reuse positive core evidence before using this protocol. Five cores: 团体赛 1 / 294; 中国围棋段位赛 39 / 294; 全国围棋个人赛 46 / 186; 升段赛 2 / 126; `10-game match` 1 / 245. No all-library negative research is needed. |
| `2020-national-round-robin-translated-research-pending.json` | 13 / 213 | Grammar-compatible as currently split, but lacks captured source for exact core `2020中国国家队积分大循环`. A source for core without year would need the small bare-year split below. Correct visible draft slips such as TW `第10轮` and JP `第10回` during name review. |
| `agon-preselection-translated-research-pending.json` | 10 / 205 | Proceed as above. |

For the next code-sized increment, add only an explicit `stage` component accepting the six actually present suffixes `16强战`, `16强赛`, `八强战`, `八强赛`, `决赛`, `半决赛`. This unlocks **17 raw / 43 games** in batch2: select records containing exact `招商银行杯电视快棋赛` and containing neither `中国` nor `点金`; extract its final suffix as stage, keep one sourced core, and preserve exact concatenation. This subset's sorted raw-set digest is `2433f9b7ff8978bc3bd8f59de93952128b90e6b23420aeb8a585c50db4994b22`. `cmb_2006.html` supplies that exact core. A finite profile plus one lossless stage success/failure check is sufficient.

Defer broader grammar until its actual batch is ready. Concrete remaining examples are bare year `2004招商银行杯决赛` (allow exact `2004` year without inserting 年), embedded edition `招商银行杯第23届亚洲电视快棋赛决赛` (currently two core parts; do not relax to arbitrary multiple cores), and qualifiers `中国`, `点金中国`, `中国围棋` in batch2. Preserve those qualifiers literally; do not drop them to fit the source core. Tokyo's `10th Tokyo Shinbun Cup` and the All-Japan Women's titles need both actual English ordinal-with-space handling and captured core evidence; their local owner preimages alone do not meet the current source gate. Hold these rather than expanding the present implementation.

Priority: agon10 → cmb2 → stage-only CMB17; parallel source preparation for the five generic cores has the largest next payoff. Preserve the approved source/reviewer gates throughout.
