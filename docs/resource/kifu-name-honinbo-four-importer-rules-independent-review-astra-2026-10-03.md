# Honinbo four corrected importer rules: independent approval

**PASS — exact corrected `en cn jp de` rule records for editions 1–34.** The capture-provenance and German-revision blockers in the [partial review](kifu-name-honinbo-composition-partial-independent-review-astra-2026-10-03.md) are resolved. I signed four new rule copies. This does **not** approve the old 374 candidates, database preimages, an import bundle or database writes.

Reviewer: `/root/oza_ua_display_decision_astra`, parent-configured `gpt-6-astra` / max, without runtime attestation. Actual review time: **2026-10-02T18:08:12.461696Z**. Independent producer `/root/honinbo_final_candidates` and its `inherited/unverified` model label are preserved. Input: [corrected producer memo](kifu-name-honinbo-four-importer-rules-corrected-pending-2026-10-03.md).

## Verification

- Recomputed the corrected packet, enclosing manifest, both capture manifests and all seven source-body hashes/lengths. Each source URL, body hash and capture time matches its exact receipt. Two sources reuse authentic earlier receipts: CWI edition 1 at `2026-10-02T14:39:46.990141+00:00` and the Japanese official archive at `2026-10-02T14:39:38.553547+00:00`.
- The other five sources have separate recorded request-start and response-read completion times, HTTP 200, matching requested/final HTTPS URLs, and retained bytes identical to their earlier reviewed bodies. Completion times span `2026-10-02T18:00:32.615739Z` to `2026-10-02T18:00:33.536517Z`, before packet production at `2026-10-02T18:02:05.135540Z` and this review. HTTP cache/server dates were not substituted for local capture times.
- The German retained/recaptured HTML contains `wgRevisionId: 227470618`, matching `content.sources[0].revision`. The seven excerpts still occur in the actual HTML text. Comparing restored content objects confirms that **only seven capture times and this revision field changed**; source bodies, bases, series owner, renderer and styles are unchanged.
- Independently checked all **34 × 4 = 136** displays, including every English ordinal suffix branch, against the previous outputs and importer renderer. All match byte for byte. The four-language display-map canonical SHA-256 is `d3c0cbc4673f3569c806a836ad3d544fbae3d45a76d0ad086677f8cf9b94ae80`; the full eleven-language map remains `ba6fbbe44090ba2ef0c9ea537aceb2c94d29c201ce59ce2f0317c334ed1da793`.
- All four signed copies pass `_source_captures` and `_reviewed_record`, including independent identities, exact immutable content hashes and source/production/review chronology. The earlier seven signed rules, 34 category approvals and scope are unchanged.

## Signed records

| Locale | Approved immutable content SHA-256 |
| --- | --- |
| `en` | `bea590bfee950338f754dc9133c4fe591f456dfb3ea04621a7a7546e5646291f` |
| `cn` | `d1e39bc8999663eb75245275eac0e5ff3cad6e5a4f43f24bcbd24dd9866be9ac` |
| `jp` | `5f30fd40682f1c0ef2fac9f2fb46de2805ffe174f4b6b12f06e396494fd74a9d` |
| `de` | `a0bbdf972f8e40c9d08f62283058cb056c6a2ef8da7c70f92814d9d539f77d30` |

New protected artifact: `/Users/fan/.local/share/kifu-name-audit/2026-10-03/honinbo-four-rule-review-astra/honinbo-four-importer-rules-v2.approved.json` (directory `0700`, file `0600`). It contains the four exact signed records, their complete approved-record hashes, all receipt bindings and input pins.

- Artifact byte SHA-256: **`a2b37a41665471e4f939d2081756960b7db45ece7b87bd7a0b190edd0271af66`**.
- Artifact canonical SHA-256: `68deae7df4b9e30b6a2dfd3edb953e009353abb1b392cd230e764e188b938424`.
- Original corrected pending packet byte SHA-256: `42731d807d38162886690073f5f2e7595120c2c0b6565db8622977e0cb9cb7e3`.
- Producer manifest byte SHA-256: `03ee8225ded11eda7e49cdd762c8eb93943c6f69f10dc306c5990decdb0ad95b`.
- Recapture manifest byte SHA-256: `f90467d374c24dacfc169200925d1855aba96a7b12a46194ed154614b135efec`.

Together with the previous partial artifact, all eleven importer rules now have independent signatures. **Next:** produce fresh candidate records after these approvals, binding complete approved rule-record hashes and the actual new production time; then obtain independent current database preimage binding and final candidate/bundle review. The old 374 rows remain pending and cannot inherit these approvals. Full display/coverage and both player-slot gates remain. No existing artifact, code or database was changed.
