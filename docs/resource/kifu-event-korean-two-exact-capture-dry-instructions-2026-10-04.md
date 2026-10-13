# Korean GS Caltex and Women's Guksu exact executor

Implementation only; this handoff has performed no TEST or PROD database access or writes.

Pinned independent decision: `749e066920dcdc0fc181074f15c10128e7f277ba87d98d699e87bc5638595d80`.
Pinned post-Ahan exact rebase: `f7bf5374be594ca994bbadf6a26ae6af6e2cc6d9864bc2be181b18776548bd3f`.

The executor creates exactly 韩国GS加德士杯 and 韩国女子国手战 and updates only the 737 approved `event_id` cells. It compares all 756 candidate album rows, their full source associations, all source/event/alias/edition rows, all 180 referenced player rows, the 4,273 prior HOLD event/edition slots, and global album/event-link/edition-link counts. Both new target identities must be absent, including normalized alias collisions. Every candidate edition slot, all 19 new HOLD rows, and the prior HOLD event/edition slots remain protected. The two environment preimages are validated on every command, together with all decision input file hashes and the exact prior Ahan catalog/statistics rebase.

Safe6 approved player slots overlap none of the 756 candidate albums. They overlap 11 prior HOLD albums (42187, 67636, 67677, 78355, 87143, 101128, 111874, 116256, 125780, 146606, 147875); the independently reviewed prior HOLD preimage contains only `id`, `event_id`, `event_edition_id`, which safe6 does not alter. The referenced player catalog guard intentionally contains the frozen 180 referenced rows, rather than unrelated newly created player rows. No safe6 exception or automatic rebase was added.

Files and SHA256:

| File | SHA256 |
| --- | --- |
| `katrain/web/kifu/event_korean_two_exact.py` | `f354c6a22645f199d5b90d74e6b047660cc954d21510c149479bbd2bffe06e2f` |
| `scripts/kifu_event_korean_two_exact.py` | `6b30f60b519ca57ed65bca15f53a6e53d06bf0e37d558674229ed1b44246be02` |
| `tests/web_ui/test_kifu_event_korean_two_exact.py` | `43e33fbd13bf43136d4c24c6f64686675e7d168dc5056ea9b30190aee67afa8c` |

Stage the module and CLI under the same repository tree as the existing `event_next3_exact.py` helper and database models. Include the independent decision, every file under its `inputs`, both environment-specific `FROZEN` files, the post-Ahan rebase, and each environment's `original_preimage`, `ahan_applied_plan`, and `ahan_committed_event_postimage` referenced by that rebase. Exact relative paths must be preserved; the executor refuses missing or changed pinned evidence.

Run each environment separately with its credential-provided `KATRAIN_DATABASE_URL`. Substitute an explicit output path for `PLAN`, and the SHA returned by capture for `CAPTURE_SHA`:

```sh
python scripts/kifu_event_korean_two_exact.py capture --environment test --plan PLAN
python scripts/kifu_event_korean_two_exact.py dry --environment test --plan PLAN --plan-sha256 CAPTURE_SHA
```

Repeat with `--environment prod`, its own database URL, plan and SHA. Capture uses a PostgreSQL repeatable read, read-only transaction. Dry rehearses the actual inserts and exact updates under table locks, verifies the full expected postimage, rolls back, and verifies the independently reread preimage. As in the proven predecessor, sequence allocation during PostgreSQL rehearsal may advance sequence values; actual target IDs are resolved independently during apply.

Submit both captured plan SHAs and rollback results for independent review before apply. The apply command requires identical `--plan-sha256` and separately authorized `--approved-plan-sha256`; it recaptures the full protected scope under locks, performs exact per-album compare-and-set, verifies before commit, and verifies the committed postimage through a separate read-only session.

Validation: `pytest -q tests/web_ui/test_kifu_event_korean_two_exact.py tests/web_ui/test_kifu_event_china_ahan_exact.py tests/web_ui/test_kifu_event_next514_exact.py` passed 13 tests. The focused five cases cover both pinned TEST/PROD evidence chains and protected capture drift, rollback/apply/CAS/independent verification, exact Ahan rebase drift, and target alias collision. CLI `--help` succeeded.
