# Ranks 101–150: fresh raw30 / direct155 pending bulk packet

2026-10-03. Produced by `/root/players_101_150_candidates_sol` (GPT-6 runtime; exact model suffix not independently exposed). **30 exact raw owners, 155 direct-source importer-format proposals frozen pending independent review. Zero approved candidates, person FK links, aliases, or live database writes.** The independently reviewed source-positive set is 147 primary cells plus 180 secondary source-name proposals; it is not 327 importer-approved names.

Protected v2 packet: `/Users/fan/.local/share/kifu-name-audit/2026-10-03/player-ranks101-150-fresh-bulk-pending-sol-v2/`, directory `0700`, all files `0400`. Manifest SHA-256 `36de195a01a1d9863f13c14adff8ac2d4e6c7bd09917c62338edc8ee8351f894`. This v2 uses exactly the allowed `raw_value/category` create fields and adds explicit source-capture metadata dependencies. The preliminary v1 packet is preserved; use v2 for review.

## Exact finite counts

| Scope | Count |
| --- | ---: |
| Raw owners | 30 |
| All exact black/white slots | 16,551 |
| Proposed finite display slots | 16,525 |
| Context exceptions retained HOLD | 26 |
| All distinct occurrence albums | 15,880 |
| Proposed display distinct albums | 15,856 |
| Primary direct-source proposals | 147 |
| Secondary actual target-article proposals | 8 |
| Total direct-source pending candidates | **155** |
| Secondary Latin reuse / Cyrillic rule HOLD | **112 / 60** |
| Direct155 proposed language-slots | **85,703** |

Direct155 language cells: `cn30 / tw27 / jp30 / ko30 / en30 / es2 / fr6`. Proposed language-slots: `cn16525 / tw14938 / jp16525 / ko16525 / en16525 / es1178 / fr3487`. The complete reviewed source-name proposal set would represent 180,188 language-slots if all its independent rule and applicability gates later passed; that number is a conditional upper bound, not approved coverage. `summary.actual.json` records every owner's counts, languages and full occurrence/scope hashes.

Three primary `tw` cells on these 30 owners remain HOLD: 今村俊也、濑户大树、三村智保. Across the full primary ranks101–150 matrix, the reviewed status remains 147 source-positive / 98 HOLD / 5 excluded. The 26 context exceptions retain six unknown-date sentinels, sixteen invalid rank fields and four duplicate-marked slots. No scope exception was silently included.

## Fresh production capture

One successful `REPEATABLE READ READ ONLY` transaction read all 173,025 album hash vectors, 173,034 source links, six catalog tables, four name tables and research evidence. Target: `ucloud-v100 / katrain-ucloud-postgres-1 / katrain_prod_20260725`. Start/end `2026-10-03T07:36:56.499701+00:00` / `07:38:29.824952+00:00`; same snapshot `1647002:1647002:`. It ended with `ROLLBACK`. Gzip capture SHA-256 `457959f10c94a38e87c1a90b19ffb8fbcbe9de9f507bfcba9f7fe229e9ab0bed`.

Full actual format2 inventory SHA-256 is `66b8946d908468c5f9c8f0dc8ef4b4ceddb76d840ef42f5cff5122fc5744b3a3`; catalog SHA-256 is `37ab4773652e10e38cdcc49a6fc13e3f72ec734aeb30be548d2597c0660f7f09`. All album association/context/source-link projections exactly equal the historical clone. The clone's differing `f4907ffb…` full hash includes an empty format4 event-selection supplement; actual production does not have `kifu_album_event_selections`, so the new inventory omits that supplement and uses format2. An initial failed READ ONLY capture is retained in v1; one corrected capture was run, with no migration or extra full scan.

Both entire raw-player value/name tables are empty. Every new exact raw ref's name preimage is therefore explicit null. Current research-evidence table is empty and all 4,485 identity-name rows have null evidence IDs, so the qualified importer approved-name snapshot is exactly `[]`. These facts establish this captured raw-name preimage only; they establish no person identity/FK or later production freshness.

## Independent replay and remaining gates

A separate read of the frozen v2 packet verified all 176 manifest files, 15 external dependencies and four validator module hashes. Existing `validate_research_record` passed for all 155 records. Every proposed display slot's full context, exact spelling and null player FK was checked against the fresh inventory. Existing `validate_bundle` reproduced `validator.actual.pending.json` exactly: **ready=false, write_ready=false, approved=0**, with 30 unsigned-owner errors and their 155 member / 155 candidate consequences. Its `pending=0` means the candidate checks fail before their approval-status accounting; it does not mean this producer signed anything.

The raw30 categories and display scopes need independent signatures first. Signing a scope changes its canonical hash, so later copies must bind the real signed scope hash before independent final candidate/preimage approval. The 172 secondary source-name proposals remain in `secondary172.source-only.HOLD.jsonl`: 112 source-backed Latin reuse and 60 Cyrillic proposals need actual compatible original/reading anchors, rules and finite signed batches. They were not relabeled as conventional names or as complete negative-source searches.

The packet embeds the direct-source research bodies and freezes their original bytes. The two Haifong proposals' missing candidate timestamps were recovered from archived official capture metadata with matching body hashes; no timestamp was invented. Wikipedia's stored product variant `jp` is normalized to target language `ja`, preserving the original field. 童夢成's previously adjudicated birthday discrepancy remains in the archived source record and its retained body, without deciding any birthday field here.

The frozen importer replay command is:

```sh
.venv/bin/python scripts/kifu_name_candidates.py validate \
  --registry /Users/fan/.local/share/kifu-name-audit/2026-10-03/player-ranks101-150-fresh-bulk-pending-sol-v2/registry.existing-approved.frozen.json \
  --inventory /Users/fan/.local/share/kifu-name-audit/2026-10-03/player-ranks101-150-fresh-bulk-pending-sol-v2/inventory.fresh-production.json.gz \
  --bundle /Users/fan/.local/share/kifu-name-audit/2026-10-03/player-ranks101-150-fresh-bulk-pending-sol-v2/bundle.direct155.preimage-bound.pending.json \
  --evidence /Users/fan/.local/share/kifu-name-audit/2026-10-03/player-ranks101-150-fresh-bulk-pending-sol-v2/research.direct155.pending.jsonl
```

Expected exit is 1 at the pending signature gate. No isolated-clone importer rehearsal, production import, deployment, application-code edit or commit was performed.
