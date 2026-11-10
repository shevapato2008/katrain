# Real release follow-up: receiver lifetime and replay

Base: `ef96a50a7e69e93e57e890cca837c9298f45f329`. Independent reviewer: new `gpt-6-astra`, reasoning `max`, no inherited conversation, task `astra_receiver_boundary_review`.

Real run 70886 completed one 10-game package through TEST and PROD (50 API checks each). A second package entered PROD publication with 494 seconds remaining. Its SSH transport timed out at the 3300-second cooperative round allowance while the remote Docker receiver continued working. Future scheduling was paused without killing that writer. This exposed a remote lifetime boundary absent from the original local simulations.

The follow-up keeps publication SSH awaited without a subprocess wall timeout. Read-only identity checks retain their finite deadline. A PostgreSQL session advisory guard covers both SGF warm-up and the existing locked publication transaction; a disconnected receiver retains its guard until it finishes, and another receiver fails closed before warm-up. Acquisition or release errors invalidate the connection rather than returning uncertain session locks to the pool. Native receipt replays skip full-catalog SGF warm-up but retain all locked source, complete SGF, identity, public-card and five-language qualification checks.

The reviewer found one acquisition-error lock-pool gap, corrected before approval. New regression tests reproduced the old transport timeout, unnecessary replay warm-up, missing whole-publication guard, and acquisition-reply uncertainty. The reviewer independently ran the three changed test files: **127 passed**, plus `git diff --check`.

Final verdict: **Approved; no remaining must-fix in the six Python files**. No real PostgreSQL test DSN was available to the reviewer. No production action or model call was performed by the reviewer. This code review does not replace the separately requested post-deployment independent flow audit.

The full targeted suite after the corrections contains 301 tests. The existing first-publication full-catalog SGF normalization/snapshot cost remains; no candidate-query/index redesign is included. The 3300 seconds remains a cooperative admission budget, not a hard cancellation deadline. SSH keepalives detect transport loss; a responsive remote process can still outlive the allowance, so its original writer must be allowed to finish.
