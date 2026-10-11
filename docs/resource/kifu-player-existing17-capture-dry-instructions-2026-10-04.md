# Existing17 exact player FK batch

The pinned Astra decision approves exactly 3,576 NULL player FK slots and holds 807 slots across 17 exact raw names. This runner writes only the approved `black_player_id` or `white_player_id` cells. It makes no catalog, alias, name, raw staging, SGF, event, or edition changes.

Capture after the six-league batch has committed and been independently verified. The runner pins both frozen 4,383-slot snapshots and their full SGFs, the Astra decision SHA, and both applied six-league plans. It permits only the 137 enumerated `event_id` postimages in overlapping albums. It checks every other album field, source association, player catalog, alias, name, raw staging row, and reviewed event target catalog row against the frozen evidence. TEST and PROD target player IDs are resolved only from the exact decision.

With `KATRAIN_DATABASE_URL` set inside each database container:

```sh
python scripts/kifu_player_existing17.py capture --environment test --plan /tmp/kifu-existing17-test-plan.json.gz
python scripts/kifu_player_existing17.py capture --environment prod --plan /tmp/kifu-existing17-prod-plan.json.gz
```

Independently compare both captured plans and approve each printed plan file SHA. The plans must show 3,576 approved slots, 807 holds, 137 exact event rebases, and environment-specific target IDs from the decision. Then run a real rollback dry run in each environment:

```sh
python scripts/kifu_player_existing17.py dry --environment test --plan /tmp/kifu-existing17-test-plan.json.gz --plan-sha256 TEST_PLAN_SHA
python scripts/kifu_player_existing17.py dry --environment prod --plan /tmp/kifu-existing17-prod-plan.json.gz --plan-sha256 PROD_PLAN_SHA
```

Apply requires the separately approved plan byte SHA:

```sh
python scripts/kifu_player_existing17.py apply --environment test --plan /tmp/kifu-existing17-test-plan.json.gz --plan-sha256 TEST_PLAN_SHA --approved-plan-sha256 TEST_PLAN_SHA
python scripts/kifu_player_existing17.py apply --environment prod --plan /tmp/kifu-existing17-prod-plan.json.gz --plan-sha256 PROD_PLAN_SHA --approved-plan-sha256 PROD_PLAN_SHA
```

Dry and apply lock the relevant tables, recapture the complete preimage, use exact raw and NULL compare-and-set for every approved slot, and verify all approved and HOLD album postimages. Dry rolls back; apply commits. Both independently reread the full scope in a new transaction afterward. Any postcommit reread failure is reported explicitly as a committed write requiring investigation.
