# Kifu release integration — independent ASTRA/MAX review

**Decision: APPROVED. No outstanding material merge or regression finding.**

Reviewed the settled staged integration of `8d9edb3a04027f44e57b923ec37cee04edd78cfe` (`develop`) into `40b8cab73b5b46c74b50eb8d2f944d64d84944ac` (approved feature), against both parents. The prior approved physical/history and source-standardization reviews remain the full feature reviews. This pass covers the five conflict resolutions, all eleven paths changed on both sides, the research replay adapter, and the additional catalog repair/search coordinator correction.

The final staged and working-tree M3 blobs match: `scripts/standardize_kifu_catalog.py` is `ff1a67c35e6a4981fc59da329d085ad23c64e976`; its test module is `953e6fc58823529d4b7a9255dc27bb614419c613`.

## Integration assessment

- Album detail uses the current original-record reader and retains exact-bound source ranks and verified display-duplicate proof. The Elasticsearch list path loads the player IDs needed by rank validation. Removed prepared-search modules have no remaining Python references in `katrain/` or `scripts/`.
- Protected migrations retain `users`, `report_tasks`, and `baipu_history`. The history router, model, server initialization, and existing sync-worker lock remain integrated with the latest startup and queue behavior.
- History transport uses the latest `_identity_generation` for pre-request, post-response, and refresh checks. The stricter token/binding setters and existing identity-bound paid requests remain present. No second generation counter survives the merge.
- LiveBoard and research display replay share the reviewed FF4 helper. Research setup extraction and next-player helpers retain their editing and metadata contracts.
- The legacy importer retains current manual-import Elasticsearch coordination and validates semantic duplicate provenance before retaining the original exact-byte owner. Native publication and HTTP verification preserve original source receipts while exposing the verified canonical display card.
- Catalog CLI apply/undo now use the existing `name_batch._locked_write` coordinator with the finite union of changed rank albums and dedup members. Its session locks cover pending, the real SQL commit, projection, refresh, and ready. A known rollback restores the gate; a post-commit projection failure leaves a recoverable finite-ID pending operation. Connection-level helpers preserve caller-owned transactions and explicitly return `caller_managed` search status. Manifest preparation and frozen evidence logic are unchanged by this integration correction.

## Verification

Independently ran on the settled staged code:

```text
KATRAIN_DATABASE_URL=sqlite:////tmp/kifu-release-integration-review.db CI=true .venv/bin/python -m pytest -q tests/web_ui/test_kifu_catalog_standardization.py -k 'catalog_repair_es or catalog_repair_preimage or production_cli_uses_es'
4 passed, 41 deselected in 1.34s
```

These cases cover pending before SQL, projection after an externally visible commit, exact affected IDs, failure/retry recovery and stale-read refusal, preimage rollback, and actual CLI apply/retry/undo dispatch. Both `git diff --check` and `git diff --cached --check` passed; no unresolved merge paths remain.

The integration owner also supplied settled focused results: 128 passed with one optional PostgreSQL skip for catalog/search/incremental publication, 92 identity/history tests, 106 frontend replay/research tests plus TypeScript, and 156 metadata tests with an optional PostgreSQL skip. These are owner-reported evidence; the independent run above was deliberately confined to the new coordination seam. PostgreSQL was not restarted for this narrow pass; existing approved lock/audit coverage and the unchanged coordinator were inspected.

Only this review document was written by the reviewer. Tests used isolated SQLite fixtures. No production/developer database, device, deployment, or `data/kifu-album/` filesystem access occurred. Published commits, deployed runtime compatibility, and production data-application results remain release-execution evidence to be recorded by the integration owner.
