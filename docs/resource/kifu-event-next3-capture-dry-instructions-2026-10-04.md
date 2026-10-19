# Next-three exact event type batch

The independent decision enumerates 2,153 approved albums and 268 HOLD albums. The runner creates only these three canonical types, if still absent: `台湾友士杯十段赛`, `韩国KBS杯围棋王战`, and `台湾联电杯职业围棋赛`. It writes only approved `kifu_albums.event_id` cells. All editions remain NULL; aliases, names, source records, SGFs, and player FKs remain unchanged.

Capture separately in TEST and PROD with `KATRAIN_DATABASE_URL` set to the expected database. Capture checks the pinned decision, frozen PROD full albums/SGFs/source/catalog, exact 27 applied existing17 player FK postimages, TEST source identity, and absence of a colliding catalog or alias owner.

```sh
python scripts/kifu_event_next3_exact.py capture --environment test --plan /tmp/kifu-event-next3-test-plan.json.gz
python scripts/kifu_event_next3_exact.py capture --environment prod --plan /tmp/kifu-event-next3-prod-plan.json.gz
```

Review the two complete captured plans and separately approve each plan file SHA. Each must show 2,153 approved, 268 HOLD, and 27 reviewed player FK postimages. Then run a real rollback dry run in both environments:

```sh
python scripts/kifu_event_next3_exact.py dry --environment test --plan /tmp/kifu-event-next3-test-plan.json.gz --plan-sha256 TEST_PLAN_SHA
python scripts/kifu_event_next3_exact.py dry --environment prod --plan /tmp/kifu-event-next3-prod-plan.json.gz --plan-sha256 PROD_PLAN_SHA
```

Apply only after the plan SHA is separately approved:

```sh
python scripts/kifu_event_next3_exact.py apply --environment test --plan /tmp/kifu-event-next3-test-plan.json.gz --plan-sha256 TEST_PLAN_SHA --approved-plan-sha256 TEST_PLAN_SHA
python scripts/kifu_event_next3_exact.py apply --environment prod --plan /tmp/kifu-event-next3-prod-plan.json.gz --plan-sha256 PROD_PLAN_SHA --approved-plan-sha256 PROD_PLAN_SHA
```

Dry and apply lock the relevant tables, recapture the full preimage, create the three exact target rows, update approved albums by NULL event/edition CAS, and verify all 2,421 album postimages plus source/catalog/alias/edition data. Dry rolls back and independently rereads the original state. Apply commits and independently rereads the final state in a new transaction. A postcommit reread failure is reported as a committed write requiring investigation.
