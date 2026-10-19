# Next 15 exact player names: capture and dry-run

This producer follows the independent identity decision. It covers 13 approved exact raw names, retains the two whole-raw holds (`小松英树`, `林彦丞`), and retains all 31 listed slot holds. Extra SGF, date, or same-person conflicts become held slots. It creates six Chinese canonical identities only when the live canonical, alias, and display-name collision checks remain clear. The four existing wrong-spelling IDs and three already-correct IDs are reused. Existing player canonicals, aliases, five-language name rows, source data, raw values, dates, and SGF text are preserved. Raw staging status and metadata remain unchanged because partial holds prevent blanket approval.

**Code and frozen plans require independent review before any database execution.** Capture is read-only; dry-run rolls back all changes. Apply is available only after a separate review of the environment-specific plan hash.

Set `KATRAIN_DATABASE_URL` to the intended environment. The CLI checks `current_database()` against the reviewed TEST or PROD name and pins both the independent decision file and each frozen inventory by SHA-256.

```sh
python scripts/kifu_player_next15.py capture --environment test \
  --inventory /tmp/kifu-five-test-inventory-post7.json.gz \
  --plan docs/resource/kifu-player-next15-TEST-plan-2026-10-04.json.gz

python scripts/kifu_player_next15.py capture --environment prod \
  --inventory /tmp/kifu-five-prod-inventory-post7.json.gz \
  --plan docs/resource/kifu-player-next15-PROD-plan-2026-10-04.json.gz
```

Review each plan's `candidate_slots`, `held_slots`, `protected_slots`, `whole_raw_held_slots`, `catalog`, and `sgf` preimages. The SHA printed by capture is the exact compressed plan file hash. The expected ceiling is 5,423 candidate slots; additional holds can lower it. Each candidate must have a NULL FK, and the plan does not repoint existing FKs.

```sh
python scripts/kifu_player_next15.py dry --environment test \
  --inventory /tmp/kifu-five-test-inventory-post7.json.gz \
  --plan docs/resource/kifu-player-next15-TEST-plan-2026-10-04.json.gz \
  --plan-sha256 REVIEWED_TEST_PLAN_SHA
```

Repeat for PROD with its own inventory, plan, and SHA. Do not reuse a TEST plan in PROD. The dry run locks and rechecks the complete exact-raw scope, SGF hashes, source links, catalog collision rows, existing names and aliases before rolling back table changes. PostgreSQL sequences may advance when it simulates six new IDs. After independent approval, `apply` requires the same `--plan-sha256` and a matching `--approved-plan-sha256` supplied separately.
