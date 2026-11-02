# Integrated verification record

Frontend final focused integration selected28 related files:362passed,2failed,1known baseline skipped. The failures are confirmed pre-existing, unrelated to these changes:

- Galaxy library language retry request count is intermittent (3 expected vs4 observed); request effects/test unchanged. Initial independent baseline also reproduced sibling repeated-selected-card request-count failure, which this integrated selection explicitly skipped.
- Galaxy generic report library-import mock provides only raw event, while unchanged dialog already requires display_event. ReportsPage/component/test have zero change in this task. No generic report implementation was changed to mask that stale fixture.

Subsequent final Kiosk library-import-dialog source-safe rank regression:11/11passed. Both Kiosk/Galaxy report headers, shared utilities and final import dialog also independently passed51/51 under ASTRA review. All newly implemented feature cases pass. Full pre-existing i18n missing-key baseline is documented separately; all new history/physical keys were translated/compiled in11catalogs with no newly missing keys.

Two independent production builds (Kiosk2D and Galaxy) passed before the final narrow report/import display seams; final rebuilt outputs/check status will be recorded below. Representative actual runtime evidence is linked in `2026-11-03-baipu-physical-history-runtime.md` and `2026-11-03-kifu-standardization-runtime.md`.

No production DB changes, deployment, integration merge or SGF deletion are included in these verification actions.

Final builds: `npm run build:kiosk-2d` and `npm run build` both passed on the final frontend, including report/import rank consumers. Kiosk no-three/Galaxy/live-API boundary guard passed. TypeScript is included in both builds.

Backend final integrated selection:655passed,1skipped,1failed. The failure is the prepared-search peak-process-memory guard after vision/core and metadata tests ran in a single Python process. The unchanged guard was not relaxed. Running that exact cron test in a fresh process together with the final standardization module passed:41passed,1optionalPG-skip. Thus the isolated process/resource contract passes; the monolithic run is not reported as universally green. Dedicated history/rank PostgreSQL concurrency tests passed in the integrated selection, and independent reviewers separately ran metadata PostgreSQL tests.

Final read-only PROD/HOME manifests: root independently verified both canonical manifest hashes and all current preparation-module hashes against their evidence. Both scan176949albums; propose187duplicate pointers and5571rank overlays (5550unspecified,21historical-professional including target2), preserving184existing snapshots and259hidden rows. Live-writer compatibility is false in both environments; `production_applied:false`. Durable private manifests live under ignored `output/kifu-standardization/2026-11-03/`; their human summary is tracked separately.

Temporary browser sessions/services/SSH forwards were stopped; the actual RK page was restored. Disposable PostgreSQL cleanup is performed after final worker checks finish.

Final independent metadata/native/cron related run:227passed,1optionalPG-skipped in22.36s; standardization PostgreSQL apply/undo was enabled and passed. This clean related-process run includes the cron case that hit the monolithic vision+metadata process peak-RSS limit; no production resource budget was weakened. Both final metadata spec and ASTRA/MAX code quality reviews are APPROVED/SPEC COMPLIANT, including the strict referenced-name correction after the discarded broad195-group candidate.

Full private artifact output includes separate PROD/HOME preimages: nine ID pairs differ despite the same final187SGF pair set, so manifests must not be swapped between environments. Read-only/preparation evidence is also recorded in `evidence/2026-11-03-kifu-standardization-manifests.json`.

Cleanup complete: disposable PostgreSQL container `codex-baipu-history-pg-20261103` stopped after all worker checks. No production services were stopped or restarted.
