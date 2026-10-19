# Five-player TEST v2 approved isolated clone rehearsal

Status: **PASS_EXACT_SIGNED_BUNDLE_CLONE_REHEARSAL** (2026-10-03). The rehearsal used only the original local isolated stopped clone. Exact container ID, image, sole volume, local Docker endpoint and localhost port binding were guarded; the clone was stopped after restoration.

Approved input and protected evidence hashes:

- Final independent review manifest: `944e528423d9cf544d94b40aa2e7c7d2c0df7298316c8e0dccaa5e8629bf7a53`.
- Exact bundle canonical SHA: `ad890a5b111d39751652ee9ec8b7da207e5ab70d8f06bbca5d24d1fc031cb710`.
- Rehearsal evidence manifest: `62a957692b41cff4f876f8141400101e8cd694453b35278b7dc58d4b4ad31086`.

Fresh read-only inventory/catalog, empty approved-name snapshot, 55 absent name preimages and 4,358 exact signed slot contexts matched the approved inputs. Producer files and signed code hashes were verified.

Validation and dry-run passed with 55 candidates and 115 planned changes. Apply created 5 raw owners, 55 names and 55 research evidence rows. Production strict display and slot approval helpers verified **47,938 scoped language cells (4,358 × 11)**: 26,148 secondary-language cells and 21,790 main-language cells. Deduplicated exact translated searches returned each signed album scope precisely. Coverage is restricted to those signed slots through the shared production `strict_slot_approvals` helper; this is not a full-catalog coverage result.

Replay produced **zero changes and zero write statements**. Conditional undo reverted **all 115 changes, with zero skipped rows**. Complete business-table hashes, target album-row hash and all **173,025 album SGF/FK rows** matched baseline after undo. SGF/FK SHA: `e6a3e7e4f9988fcf87805d33d81c748aa2d8104d984f2ebb4a99f3f9066f8bbf`.

Business rows were restored. The expected rehearsal audit trail remains: batch 1, 115 undo ledger entries and one source-registry record. Protected evidence includes the fresh inventory, preflights, validation/dry-run/apply/replay/undo receipts, scoped runtime results, before/after hashes and final stopped-clone receipt.

No active TEST or PROD database connection/write occurred. The rehearsal made no repository code changes, commit or push. This result does not authorize an active TEST or PROD apply.
