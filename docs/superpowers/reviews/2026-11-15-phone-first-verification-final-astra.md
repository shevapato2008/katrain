# First phone verification and four-game public names: final review

Implementation status: **Approved**, no remaining Important/Critical findings.

Reviewed code snapshots:

- Child: `6d52d497204d86a4d0e8005a45b51a8ff2a1ecd1`.
- Parent: `3548e0894a3b2bb0e9453a820059316bbd254ed6`.
- Latest report guidance/charging work from child `b6ccc9bcc01850bc9c58d49a6959b8626c710c38` and parent `e75bf185` is retained.

## Independent specification review

Overall Approved. Identified and closed:

- I1: Gomoku room pending/failed profile synthesized a raw internal-name viewer. Removed that fallback; safe presentation remains.
- I2: Go personal research-game picker and provenance heading bypassed public display projections. Both now consume the trusted projection and preserve imported names.
- I3: Gomoku lobby archives store ownership in the lobby side table. Cursor/numbered/detail reads now use that explicit owner fact, with foreign access excluded.
- Two server-owned native Go seat columns are excluded from generic repository updates as well as public create/update inputs.

Specification reviewer independently checked critical gift/history/expiry/concurrency cases, Go runtime/repository projection, setup refresh/hint guards, all three parent history/card deltas, and PostgreSQL/SQLite additive migration. No production account or real SMS was used.

## Independent Astra Max code-quality review

Overall Approved after these focused corrections:

- Q1: Native Go archives retained only the row owner's seat. Two nullable server-owned integer seat IDs now retain both known account associations. Native writer accepts strict positive integers; generic input/update paths cannot forge them. Both users' list/detail views resolve both public names while preserving source player names and SGF bytes. Unknown legacy rows are not backfilled or paired by SGF hash.
- Q2: Go display filters did not recognize `0086` or formatted full phone numbers. Python/TypeScript predicates now align with launcher formatting checks and preserve ordinary legacy names such as `2024`.

Astra independently reviewed financial idempotence/rollback/expiry, shared profile TTL/coalescing/CAS/offline fallback, all four identity/display paths, trusted history ownership and external-name preservation. Final focused quality rerun: 9 passed; no new Important/Critical findings. Parent code-quality review did not repeat already sufficient specification suites.

## Focused verification

- Phone PG/API/remote affected suites: 197 passed; final generated-account/completion matrix: 13 passed. Counts overlap and are not summed.
- Go runtime/repository/native-seat checks, UI player/lobby/report/research checks, and post-upstream-merge report suites passed. Both PostgreSQL and SQLite additive migration/idempotence tests passed in the dedicated test harness (2 tests); no migration backfill or schema defaults.
- Setup auth/profile/phone/hint suites and async account-switch guards passed; three changed child keys compile and match PO values in all 11 languages, five launcher locales retained.
- Chess, Xiangqi and Gomoku affected identity/history/lobby/card tests and all three TypeScript builds passed. Matched/foreign owner, PGN ordering, lobby ownership, unknown/anonymous/external records and archive byte immutability were checked.
- Representative local previews cover Galaxy and 1024×600 Kiosk; all three other games show the public name. The compact binding hint and disabled pre-input confirmation button fit the 1024×600 viewport.

Known unchanged baselines: two Chess local-player default-label assertions expect `棋手1/棋手2` while the existing controller uses `白方/黑方`; global `i18n.py` has unrelated preexisting catalog inconsistencies. Scoped changes/compiled translations pass. No unrelated default-label/catalog rewrite was included.

Deployment acceptance is separate: all 11 compiled catalogs must be staged explicitly (only cn/en MO files are tracked). Website lobby static publication requires its own narrow deployment adaptation review; the old helper's unconditional platform-container recreation must not be used for a static-only release. RK deployment remains subject to connectivity, deployment occupancy and active-game checks. Real SMS/gift/paid-analysis acceptance remains manual.
