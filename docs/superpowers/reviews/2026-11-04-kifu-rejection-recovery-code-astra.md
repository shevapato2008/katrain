# Kifu rejection and cron recovery — independent code review

Review scope: the 13 implementation/test files on `fix/kifu-rejection-resilience-20261104`, against base `4f7d17b738` and the approved `2026-11-04-kifu-rejection-audit-and-cron-recovery` plan. Review order: specification compliance, then code quality. No product files, services, model calls, production databases, or restricted business-data paths were changed or accessed by this reviewer.

## Final verdict — APPROVED

Specification compliance and code quality pass. No unresolved substantive findings remain. The only R1 finding was corrected and independently rechecked:

- **Resolved P2 — a decoded non-finite number bypassed rejection persistence.** In `katrain/kifu_ingest/names.py`, `_call` rejected literal `NaN`/`Infinity` with `parse_constant`, but JSON such as `{"unexpected":1e999}` decoded to an infinite float. Candidate validation then raised `NameRejected`; `_record_rejection` attempted strict serialization of that candidate and raised a bare `ValueError` before invoking the diagnostic writer. Consequently neither the rejection evidence nor its normal isolation path was retained. A single local `httpx.MockTransport` reproduction returned one paid audit event, one fake request, zero rejection records, and `ValueError: Out of range float values are not JSON compliant: inf`.
  - Implemented correction: one strict JSON/UTF-8 serialization check inside `_call`'s existing parsing `try`. The existing `ValueError` handler now classifies this response as `provider_output_malformed`, preserves the final response content/hash, and records the rejection before repair. One focused regression also verifies a later budget stop does not erase the first diagnostic or duplicate the paid-call event. The reviewer independently ran that new test: **1 passed in 0.19s**. The scoped `git diff --check` also passed.

The remaining specification checks pass by source inspection:

- Ordinary initial and narrowed rejections are recorded before repair/rethrow; an earlier rejection survives later approval. Distinct semantic, candidate, review-protocol, and provider-output reasons are preserved.
- Paid calls settle and emit the existing call event before rejection handling. Diagnostic-write failure propagates as `NameDiagnosticStorageError`, stops repair, and cannot enter the ordinary `NameRejected` isolation-and-continue branch.
- Diagnostic files use the existing atomic writer plus directory fsync, bounded payloads, unique IDs, and a reference placed before the journal's 512-character truncation. Records contain final-content evidence and hashes rather than credentials, headers, SGF bodies, or reasoning fields.
- Portable approved decisions, review hashes, checkpoints, quarantine policy, source/package isolation, and publication receipt contracts are unchanged.
- Startup does not start interval jobs before the first readable controls snapshot. The existing poll cadence and last-known snapshot behavior are retained; shutdown interrupts the polling delay. Unreadable admin controls return 503.
- Health checks preserve offline/disabled/paused/running/stuck precedence. Never-run jobs use process start; resume advances the overdue anchor; stale failed/errors results no longer hide missed scheduling, while their original fields remain available.

Code quality is otherwise appropriate for the scope: one optional diagnostic callback, no schema migration, watchdog, automatic resume/release, or additional paid-call layer. Existing tests cover the operational paths proportionately.

Validation evidence: ROOT independently reported the combined focused suite before the one-line correction at **241 passed in 3.00s**, with four existing `cleanup` UTC deprecation warnings. After the correction, the author reported the complete names test file at **84 passed in 0.37s**. The reviewer did not repeat either suite; independent execution was limited to the original fake-response reproduction and the corrected regression above. This approval covers the implementation only; deployment, manual-pause changes, and quarantined-item release remain outside scope.
