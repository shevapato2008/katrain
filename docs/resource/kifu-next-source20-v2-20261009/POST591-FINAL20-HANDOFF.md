# Post-591 next 20: unsigned review handoff

The final source set is `source20-post591-final-pending.json`: 20 distinct players, 614 linked game slots per environment. It replaces held 339/340 with 696/697. Nothing here is signed, approved in the database, applied, or deployed.

## Current global read-only context

`PROD-post591-global-readonly.json.gz` and `TEST-post591-global-readonly.json.gz` now retain one current batch-591 global inventory, catalog hash, strictly qualified approved-name snapshot, aliases, latest source registry and exact final-20 qualification summary per environment. `post591-global-readonly-manifest.json` records capture times, actual importer image IDs and file hashes. Both snapshots assert batch 591 applied and exactly four qualified primary names for each of the final 20 owners, with the proposed target language still absent. Each inventory is format 2 with 173,025 album associations and the same inventory/catalog hash as its post-590 predecessor; the name snapshots are freshly read at batch 591. PROD used pinned r4 image `sha256:02e58b41bac1ca2bdb4cd0aa1d15a319c63781e098b0cb1523dbbc318f2bc7bc`; TEST used pinned r4 image `sha256:b606992b2f6c6ce6a7c00bd6c49f1a9fcc7330fc5ee44dd426bd6ecf30267e48` after its r5 web container was confirmed stable. All database access was read-only; no owner rows were written.

## Why 339 was held

The Japanese Go federation's actual individual profile (`339-nihonkiin-profile.body`, SHA-256 `1b2b090921d51d3f606b4b3654d0aee7dbe305f59f8421a42206c89a601b85d3`) prints `陳柏劭（チン ハクショウ）`. Current NIKL JA-to-KO transcription would produce `친 하쿠쇼`, while the real Korean Jstart article prints `진 하쿠쇼`. Jstart is a general Japan-study publication, retained as a Korean `reference` source, not elevated to the product's conventional source tier. This case must be separately reviewed later; the old `천백소` REVIEW row is untouched.

## Replacement 696/697

Both read-only current-591 captures show canonical `高若环`, qualified CN/EN/JP/TW, and the unqualified KO REVIEW `고 약환` with its complete 13-field preimage. The 25 game slots per environment include SGF SHA-256, player FKs, ranks and event/game scope. Real Korean sources retained as HTTP 200 GET bodies:

- Korea Baduk Association opponent row: `696-kba-opponent.body`, source URL in `696-actual-korean-sources.json`.
- Cyberoro specialist Go article: `696-cyberoro-news.body`; it identifies a Chinese women Go first-dan player and publishes `가오뤄환`.

An independently captured Chinese women's league article `696-chinese-women-league.body` publishes `高若环初段` in the Fujian team. Its capture descriptor is `696-chinese-identity-corroboration.json`; it is an identity bridge, not target-language Korean evidence. The older Baduk TV profile's final bracket Hanzi differs and is deliberately not used as the original-name anchor.

## Native pending records and exact state

For each environment, `*-post591-final20-pending-conventional18.json.gz` holds 18 pending conventional research records; `*-post591-final20-pending-positive-ko2.json.gz` holds 6635 and 4568 positive Japanese-kana/NIKL records with two actual 200 Korean Wikipedia API conflict queries per owner. All 20 records pass `validate_research_record` against the proposed registry. `*-post591-final20-native-pending-unsigned-draft.json.gz` holds 20 source-bound pending candidates, exact target-name CAS, owner preimages and research; all pass native pending candidate validation using the frozen post-590 inventory solely as a provisional owner-presence check. Its final format-2 write gate has not been claimed.

`source-registry-proposed-pending.json` leaves every existing source and language scope unchanged and adds Namu as a community encyclopedia, PairGo as the organizer of its own event, and Jstart as a reference. Jstart is unused by the final 20; root may omit it from a final registry, but then the registry hash in the pending research must be regenerated before approval.

The original `source20-v2.json` and exact-20 read-only captures remain immutable together by source-packet SHA. `source20-v2-corrections.md` corrects the Traditional Chinese Wikipedia 迪納 variant count to two event rows, while the selected 迪那 spelling occurs in three full-name rows. 5094's Korean Wikipedia disambiguation line is real; its individual person link is red and is not represented as an existing biography. Baduk TV personal details were actually retrieved by POST with retained `prpl_code` and body SHA. The Cyberoro same-code GET uses the same underlying data, not independent corroboration.

## Root assembly boundary

`assemble-final20-after-root-review.py` is the offline final bridge. It requires a root-supplied fresh current-591 global inventory, approved name snapshot, catalog hash, page synchronization status, exact source registry, reviewed 20 candidate signatures and owner preimages. It rejects changes to the pending source/research/CAS and invokes native `validate_bundle` before writing an **unsigned** format-2 bundle and evidence. It does not approve, sign, import, or connect to SQL. Run after review with:

```bash
PYTHONPATH=. python docs/resource/kifu-next-source20-v2-20261009/assemble-final20-after-root-review.py --env PROD --root-approved-fresh-input /path/to/PROD-root-approved-fresh.json.gz
PYTHONPATH=. python docs/resource/kifu-next-source20-v2-20261009/assemble-final20-after-root-review.py --env TEST --root-approved-fresh-input /path/to/TEST-root-approved-fresh.json.gz
```

Manifest files in this directory record SHA-256 for the two environment drafts and research files. Source-level decisions are conditional until root reviews exact identities, source registration, generated input/rule/output and fresh whole-database context.
