# Six league event links: exact execution

This executor applies only the 6,810 album IDs approved by the independent decision at `kifu-event-after743-leagues-independent-decision-astra-2026-10-04.json`. All 1,784 held album IDs remain unchanged. It writes only `kifu_albums.event_id`; all editions remain NULL. It creates no catalog, aliases, or editions.

Run after the three-player FK batch is committed and independently verified. The capture checks the frozen PROD full album/SGF/source/catalog identity, including event catalog ID 75 already present in that snapshot. It checks 47 exact reviewed three-player FK postimages and one protected HOLD slot in the intersecting albums. Any other PROD FK/catalog or raw identity drift rejects capture. TEST player FK IDs and event target IDs are bound from its own database; its raw/SGF/source identity must still match the independent PROD evidence.

For each environment, with `KATRAIN_DATABASE_URL` pointing at its expected database (`katrain_db` for TEST, `katrain_prod_20260725` for PROD):

```sh
python scripts/kifu_event_leagues_exact.py capture --environment test --plan /tmp/kifu-event-leagues-test-plan.json.gz
python scripts/kifu_event_leagues_exact.py capture --environment prod --plan /tmp/kifu-event-leagues-prod-plan.json.gz
```

Review both captured plans together. Confirm the exact 6,810 approved and 1,784 HOLD IDs, the five target names and environment-specific catalog IDs, all frozen identities and three-player overlaps, and the plan file SHA values. Then use each file's printed SHA for the dry run:

```sh
python scripts/kifu_event_leagues_exact.py dry --environment test --plan /tmp/kifu-event-leagues-test-plan.json.gz --plan-sha256 TEST_PLAN_SHA
python scripts/kifu_event_leagues_exact.py dry --environment prod --plan /tmp/kifu-event-leagues-prod-plan.json.gz --plan-sha256 PROD_PLAN_SHA
```

The dry run performs the full CAS update, checks all 8,594 postimages, rolls back, and independently rereads the original scope. After the captured plan SHA has been separately approved, apply one environment at a time:

```sh
python scripts/kifu_event_leagues_exact.py apply --environment test --plan /tmp/kifu-event-leagues-test-plan.json.gz --plan-sha256 TEST_PLAN_SHA --approved-plan-sha256 TEST_PLAN_SHA
python scripts/kifu_event_leagues_exact.py apply --environment prod --plan /tmp/kifu-event-leagues-prod-plan.json.gz --plan-sha256 PROD_PLAN_SHA --approved-plan-sha256 PROD_PLAN_SHA
```

Apply checks the byte SHA, locks the relevant tables, recaptures the complete plan before any update, uses row-level NULL-to-target CAS, checks all in-transaction postimages, commits, then independently rereads all 8,594 album and ancillary rows. A postcommit verification failure is reported explicitly as a committed write requiring investigation.
