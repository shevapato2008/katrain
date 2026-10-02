# Honinbo v2 exact-link identity review (2026-10-02)

## Decision

**PASS for the finite link-identity mapping only:** all 1,617 `event` links in the 34 exact raw groups `1st Honinbo` through `34th Honinbo` may target the proposed symbolic professional series `event:@honinbo-series-2026-10-02`. I signed a new protected bundle copy as reviewer `/root/honinbo_name_preimage_binder_sol`, configured model `gpt-6-sol` / high as supplied by the parent (no independent runtime model attestation). The ordinal remains an edition and each `round_name` remains a separate stage. The other 234 Honinbo-like raw strings / 1,704 rows are excluded without an identity decision. This does not approve the eleven display-name candidates or authorize a production write.

## Producer provenance and chronology

The prior [HOLD](kifu-name-honinbo-link-identity-review-hold-sol-2026-10-02.md) was for missing producer identity and production time. I verified the byte SHA-256 `35072ea5407b6ac81d02b94601d8adf36efa4bc937f635b12ac48130fbd49257` of the new protected `honinbo-v2-evidence-producer-addendum.json`, its pinned source-evidence manifest, link-prep artifact, inventory, canonical 1,617-link set, 34 exact group counts, and capture-before-production chronology. It identifies the actual evidence producer `/root/honinbo_v2_bundle_prep_luna`, parent-configured `gpt-6-luna` / high, with `produced_at: 2026-10-02T15:07:47.700496Z`. Its attestation covers technical verification of captured bodies and all archive mappings; earlier source/path preparation and series adjudication remain separately pinned, not misattributed as the producer's independent findings.

The new scope freeze is `2026-10-02T15:10:24.414321+00:00`, after that production time and all source captures. My actual `reviewed_at` is `2026-10-02T15:10:24.458959+00:00`. Producer and reviewer IDs differ. Each of the 34 groups has one recomputed importer `identity_scope_sha256`, and every link in a group carries the identical signed review object. The protected manifest records all 34 hashes.

## Independent checks

I reran the protected verifier against the unchanged evidence-enriched pending bundle (byte SHA-256 `14926771f6fb4494702bf8e2a21597fa81fdfe02420a68778e8c921c707c8593`). It independently verified all six retained HTTPS body lengths, hashes, URLs and fetch times; the 102 edition-specific and seven series-level excerpts; 1,616 distinct CWI archive member hashes; and exact root `EV`/`RO` for all 1,617 link mappings. Each link's source path, archive hash, association context/hash, old null event ID, and raw group count matched the pinned inventory and link-prep file. The captured Nihon Ki-in and CWI tables align numbered editions 1–34 with title-match years 1941–1979, while CWI places tournament start in June 1939. Those title-match years were not imposed on preliminary or league game dates. Album 24560's known archive `DT`/production `DT` omission does not affect its matched EV/RO identity. No adjacent raw group was silently included.

## Protected output and validation

The new files are under `/Users/fan/.local/share/kifu-name-audit/2026-10-02/honinbo-link-identity-review-sol/` (directory mode `0700`, files `0600`). Existing HOLD, source, name-candidate, and bundle artifacts were not edited.

| Artifact | Byte SHA-256 |
|---|---|
| `honinbo-series-2026-10-02-v2-bundle.identity-reviewed.names-pending.json` | `c309a142cdd83548ce60a4e6f49b7ca355a684931d05fa68e1810905680cf452` |
| `signed-identity-review-manifest.json` | `d0cc55b949583af300fffd9ad25109ce31cacd4fb658901877d3d4dcb5630061` |

The signed bundle canonical JSON SHA-256 is `ea8e68ec6e8f14ab4596558ffe434a6c048313fdc5e5510cde6e9ea4039c221e`; its recomputed `link_set_sha256` is `6ecdc5d3c903f1d0225dd0cc82e154f510d9af29de8d034d6ed450a5a52cafbb`. Independent recomputation confirmed all 34 scope hashes and the link-set hash. Offline `validate_bundle` reports **zero link or member errors**, `write_errors: []`, and exactly one remaining general error: `linked identity lacks all eleven approved language names: event:@honinbo-series-2026-10-02`. It reports 11 pending candidates, `ready: false`, and `write_ready: false`.

The separate [final name-candidate HOLD](kifu-name-honinbo-bound-candidates-final-review-astra-2026-10-02.md) identifies seven research metadata rows needing correction or clarification before any final name signature. Those corrections need their own new evidence/candidate hashes and independent review; this link approval does not resolve them. A later import also needs its established fresh production-snapshot and isolated-copy gates. No production database or SGF write occurred.
