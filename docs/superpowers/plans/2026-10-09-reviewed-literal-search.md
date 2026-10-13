# Minimal literal-title search repair — 2026-10-09

## Confirmed failure

Read-only PROD HTTP and source probes: `第1届中国城市甲级联赛` returns 0, while raw `ChinaCityLeagueA,1st` returns 65 with that Chinese display. Existing reviewed raw-name helper resolves the Chinese name to exactly those 65 albums (ID-set SHA `46e4cd4a5d33fd3ed15d2ced22c60a1726e9449797e3fa04c063c0eecc5c8a4d`). Actual old endpoint never calls it; the 570-line identity reader has no native strict raw-name matching function. This is a missing query connection.

## Minimal change

1. In shared `legacy_raw_events.py`, add only a literal exact-title search helper. Reuse existing live name/evidence/raw-owner approval, signature, exact research, language and collision checks. Read existing evidence creation ledger and applied batch in one bounded SQL query. Require unchanged created payload, source registry, canonical bundle SHA, unique exact candidate, retained research SHA and signed owner occurrence IDs.
2. Return only the reviewed occurrence IDs with unchanged raw event, null event link, public, nonduplicate and no selected-event slot. No translation runs and no ORM models, table, front-end or importer changes are added.
3. Patch each actual old endpoint by the same five-line helper call immediately before its existing query/count filters. OR the helper scope into the existing needle; all alias, rank, partial search, sorting, visibility, counts, display, dispatcher and response logic remains byte-for-byte unchanged outside the insertion.
4. TEST and PROD endpoint baseline imports differ: TEST uses existing `identity_display_compat`, which its proposal preserves. Keep separate environment-bound endpoint artifacts. Shared helper requires only the already installed pure legacy rule module import adaptation.

## Validation

- One targeted red regression failed because the new literal helper was absent.
- 27 focused literal tests passed: five languages, multiple exact raw owners, ambiguous other-name owners, changed approval/source/signature, batch status/hash/candidate/research/creation-ledger rejection, outside reviewed occurrence IDs, changed raw, public/unlinked/nonduplicate/unselected restrictions and the actual old album ORM shape. No full regression run.
- Exact PROD preview executes both proposed modules only in a separate Python process and a READ ONLY database transaction. Chinese and Traditional Chinese exact titles: 0→65; original raw query: 65→65; partial Chinese and irrelevant text: 0→0. Repaired scope SHA exactly matches the original helper. All deployed source bytes remain unchanged before and after; no deploy or database write.
- Both endpoint proposals compile. Removing the exact five-line insertion reproduces each captured old endpoint byte-for-byte. Current workspace native endpoint is untouched.

## Delivery boundary

Independent review applies to the frozen shared helper, both actual-endpoint deltas, manifests and this evidence. Root owns the guarded R16 two-file mounts and TEST-first runtime verification. This task creates no new deployment framework and performs no Git, runtime restart/apply or remote database mutation.

See `PROD-source-capture-manifest-actual.json`, `TEST-source-sha-actual.json`, `proposal-manifest.json`, `TEST-proposal-manifest.json`, `PROD-current-runtime-hypothesis.json`, `PROD-live-preview-readonly.json`, `focused-tests.txt` and the two endpoint diffs for exact bytes and receipts.
