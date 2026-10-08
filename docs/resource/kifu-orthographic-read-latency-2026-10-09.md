# TEST batch 588 orthographic read latency profile

Measured on 2026-10-09 against TEST batch 588 using the pinned `katrain-kifu-importer:jp-original-display-test-20261009-r1` image. The database connection came from the existing TEST web container environment without printing its URL. Every query ran after `SET TRANSACTION READ ONLY`; this investigation made no database, deployment, or product-code changes.

The applied batch contains 20 candidates, 20 orthographic members, 20 anchors, one rule, and **63,934 approved-name snapshot rows**. Batch retrieval and binding validation were timed separately with `time.perf_counter()`:

| Run | ORM `KifuNameBatch(588)` retrieval | `persisted_batch_bindings` | Result |
| --- | ---: | ---: | --- |
| 1 | 0.593 s | 1.277 s | valid |
| 2 | 0.419 s | 1.257 s | valid |
| 3 | 0.421 s | 1.245 s | valid |

`cProfile` gave 2.206 s for `validate_orthographic` and 2.164 s for the wrapper. Profiling overhead makes those times unsuitable as endpoint latency estimates, but call counts identify the work: 4.88 million calls per validation, including 2.62 million `_require` calls and 255,940 `_normalize` calls. The member loop in [`name_orthographic.py`](../../katrain/web/kifu/name_orthographic.py) scans the entire approved-name snapshot once for each member to check target replacement and cross-owner collisions (lines 340–356). At 20 × 63,934, that is about 1.28 million snapshot-row visits, with two assertions per visit. The verified source lookup (lines 292–303) adds another repeated snapshot scan. Batch JSON retrieval has material cost but is smaller than validation in these measurements.

The reported TEST TW list searches took 5.5–5.7 s while CN/en/ru took 170–244 ms. This profile confirms an expensive orthographic read path; it did not trace a complete HTTP request, so it does not apportion the entire 5.5–5.7 s to individual calls. The list path can qualify names during search and again for display, which may repeat batch validation within one request.

## Smallest fix to review

Keep full snapshot validation and all batch, anchor, source, journal, target-preimage, and collision gates. During each `validate_orthographic` invocation, build local indexes from the already validated snapshot: owner/language target presence, language/normalized-name cross-owner claims, and exact qualified conventional-source rows with their name/evidence hashes. Query those indexes in the member loop instead of rescanning 63,934 rows per member. Normalize each snapshot name once. Keep the indexes local to that invocation so every read continues to revalidate the current applied artifact; no process cache or new schema is needed.

## Local patched invocation (no deployment)

The per-invocation indexes were implemented in `name_orthographic.py` after the full snapshot validation. The existing orthographic test module, including a scale check and two added adversarial snapshot cases, passed **150 tests**. The scale check failed against the old implementation with 10,100 normalizations for 100 members × 100 snapshot rows; with the index it stays within a linear bound. The adversarial checks reject a late foreign name collision and two duplicate source rows that split the correct name from the correct evidence hash.

For an actual-data comparison, the patched module (SHA-256 `63c5e10ec8880d98f8cf767428603c6887923d2d6b27b2d42669594c42c27f49`) was mounted read-only over the same pinned TEST importer image. The container filesystem and SQL transaction were read-only. No image was changed or deployed.

| Run | Patched ORM batch retrieval | Patched `persisted_batch_bindings` | Result |
| --- | ---: | ---: | --- |
| 1 | 0.596 s | 0.875 s | valid |
| 2 | 0.466 s | 0.899 s | valid |
| 3 | 0.349 s | 0.878 s | valid |

Unprofiled binding validation fell from 1.25–1.28 s to 0.88–0.90 s, about **30% faster** for this batch. `cProfile` now shows 1.49 million calls rather than 4.88 million, with `_normalize` down from 255,940 to 64,534 calls. The remaining work includes exact JSON hashing and validating every snapshot row; those gates remain intact. This is a component comparison, not a post-deployment HTTP latency claim.

## TEST r2 list route, read-only diagnosis

After TEST deployed r2, an isolated `katrain-kifu-importer:jp-original-display-test-20261009-r2` container invoked the actual `list_kifu_albums` route once for `q=加納一夫`, `lang=tw`, page size 20. It used the TEST database in a read-only SQL transaction and a read-only container filesystem; no code was injected into the running web service. The in-process route took **3.244 s**, returning 22 total matches and 20 page items. This is not the browser-to-server HTTP timing (reported separately at 4.2–4.7 s).

| Component during that one route call | Calls | Total time |
| --- | ---: | ---: |
| Player-name qualification for search | 1 (2 rows) | 1.482 s |
| Player-name qualification for page display | 1 (13 rows) | 1.551 s |
| Batch 588 `persisted_batch_bindings` inside those calls | 2 | 0.785 + 0.897 = 1.682 s |
| Live source proof | 3 | 0.111 s |
| SQL statements referencing name batches | 5 | 0.361 s |
| SQL statements referencing name changes | 9 | 0.083 s |

The route qualifies player names once to resolve the search and again to display the selected page. Each qualification validates the same applied batch 588 context. The two context validations account for about 52% of measured in-process route time; both player-name qualification calls together account for about 94%. This explains the remaining TW cost more directly than the initial component profile. A possible next focused change is explicit reuse of one validated batch context within this single list request, while retaining per-name live source checks. That requires a separate review of freshness semantics before implementation. No new runtime cache or code change was made in this diagnostic step.
