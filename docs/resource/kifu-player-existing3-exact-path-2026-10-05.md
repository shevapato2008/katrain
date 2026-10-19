# Existing3 exact player-link path

This path covers only these confirmed existing identities: `中小野田智己` → PROD 352 / TEST 353 (210 NULL slots), `桥本雄二郎` → 486 / 487 (104), `高梨圣健` → 564 / 565 (93). No new player, alias, translated name, raw spelling, SGF, event, opponent or source association is written.

The two `kifu-player-existing3-{PROD,TEST}-draft-plan-2026-10-05.json.gz` files were captured directly from their respective live databases with `REPEATABLE READ READ ONLY`, then rolled back. Each contains 407 exact album IDs and full album preimages, existing target player rows, target aliases/names, the three raw staging rows and album/source associations. Their `.sha256` files pin compressed bytes. Current target catalog names are `中小野田智己`, `橋本雄二郎`, `高梨聖健` in both environments.

These are **drafts**, carrying the frozen candidate inventory SHA as provisional `review_sha256`. Apply explicitly rejects that provisional SHA. Add the independent identity decision artifact, including official source URLs and exact mappings, before preparing final plans. The capture remains useful review evidence; no live dry-run mutations or database apply were performed in this implementation task.

## Commands

Use the database URL configured for the chosen environment. PROD must report `katrain_prod_20260725`; TEST must report `katrain_db`. Each plan belongs to exactly one environment.

```sh
uv run python scripts/kifu_player_existing3_exact.py capture --environment test --plan /tmp/existing3-test-final.json.gz --review-sha256 REVIEW_SHA
uv run python scripts/kifu_player_existing3_exact.py dry --environment test --plan /tmp/existing3-test-final.json.gz --plan-sha256 PLAN_SHA --review-sha256 REVIEW_SHA --review /path/to/independent-review.json
uv run python scripts/kifu_player_existing3_exact.py apply --environment test --plan /tmp/existing3-test-final.json.gz --plan-sha256 PLAN_SHA --approved-plan-sha256 PLAN_SHA --review-sha256 REVIEW_SHA --review /path/to/independent-review.json
```

`capture` performs no DB writes. `dry` performs the complete planned updates in a transaction and rolls back. `apply` requires the independent review file bytes to match REVIEW_SHA and the separately approved compressed plan SHA to match PLAN_SHA. Final plan capture must be reviewed before apply. Substitute `prod` and a separate PROD plan for production. Do not pass TEST IDs to PROD.

The executor locks the affected tables, checks the live full scope against the pinned preimages, compares and swaps only NULL player FKs, and updates only each raw staging row's `review_status` and `review_metadata`. It checks the complete scope postimage before commit/rollback and independently checks it afterward. Existing metadata is retained with exact-link provenance added. Stale preimages, mismatched environment/target ID/membership, conflicting existing owners and unexpected postimages fail closed. A failed write rolls back all preceding writes.

Focused verification: `uv run pytest -q tests/web_ui/test_player_existing3_exact.py` (5 tests). Covers stale album/target preimages, tampered target ID, successful transactional dry rollback, approved apply with no new IDs, and a forced failure after the album updates with complete rollback. Production PostgreSQL locking has not been exercised by these SQLite tests.

## Completed application

After independent final-plan attestation and a supplemental review of direct SQL JSON binding (needed because the deployed PROD ORM lacked the staging model), both real dry-runs passed. The authorized application then committed TEST followed by PROD. Each environment linked exactly 407 NULL FKs (210 / 104 / 93), approved the three staging review rows, and created no player IDs. Complete in-transaction postimages and independent postcommit scope equality both passed. See `kifu-player-existing3-{TEST,PROD}-applied-receipt-2026-10-05.json` and matching checksum files. No deployment was performed.
