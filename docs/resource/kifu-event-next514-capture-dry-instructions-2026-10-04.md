# Next514 exact event type batch

Astra's final decision approves exactly 474 albums and holds 40. The runner links 146 approved games to existing event ID 75 (`中日围棋对抗赛`) and creates only two exact event types if absent: `中国围棋霸王战` for 238 games and `中国新体育杯` for 90 games. It writes only approved `event_id` cells and the two new catalog rows. All 514 editions remain NULL, and every HOLD album remains unchanged.

The decision SHA is `d310278775a8a1b5e08062b271485effdce8e3e58ac5eb218639cdd66b60ce3e`. Capture pins both TEST and PROD post-next3 full read-only snapshots, their earlier snapshots, both next3 applied plans, and all independent decision inputs. It checks full album and SGF bytes, source links, global sources, event catalog, aliases, editions and the 213 selected existing player rows. New unrelated player identities do not expand the event batch.

With `KATRAIN_DATABASE_URL` set to the matching database inside each container:

```sh
python scripts/kifu_event_next514_exact.py capture --environment test --plan /tmp/kifu-event-next514-test-plan.json.gz
python scripts/kifu_event_next514_exact.py capture --environment prod --plan /tmp/kifu-event-next514-prod-plan.json.gz
```

Review both complete plans and separately approve each printed plan file SHA. The plans must show 474 approved, 40 HOLD, existing ID 75, and exactly two absent new canonical names. Then run a rollback dry run in each environment:

```sh
python scripts/kifu_event_next514_exact.py dry --environment test --plan /tmp/kifu-event-next514-test-plan.json.gz --plan-sha256 TEST_PLAN_SHA
python scripts/kifu_event_next514_exact.py dry --environment prod --plan /tmp/kifu-event-next514-prod-plan.json.gz --plan-sha256 PROD_PLAN_SHA
```

Apply only after separate plan SHA approval:

```sh
python scripts/kifu_event_next514_exact.py apply --environment test --plan /tmp/kifu-event-next514-test-plan.json.gz --plan-sha256 TEST_PLAN_SHA --approved-plan-sha256 TEST_PLAN_SHA
python scripts/kifu_event_next514_exact.py apply --environment prod --plan /tmp/kifu-event-next514-prod-plan.json.gz --plan-sha256 PROD_PLAN_SHA --approved-plan-sha256 PROD_PLAN_SHA
```

Dry and apply lock the relevant tables, recapture the entire plan, create only the two absent types, and update approved albums by NULL event/edition CAS. They verify all 514 album postimages and all ancillary rows. Dry rolls back and independently rereads the original state. Apply commits and independently rereads the final state, including the two complete catalog rows observed during the write transaction. A postcommit verification failure is reported as a committed write requiring investigation.
