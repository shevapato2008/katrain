# Remaining Kifu Name Cleanup Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development for the independent research and cleanup tasks. Keep production SQL and release coordination in the root agent.

**Goal:** Delete games without actual player names; separate historical ranks and damaged SGF fragments from real names; complete the five display languages for remaining players and events; publish accurate post-cleanup statistics.

**Architecture:** Reuse the current entity IDs, name tables, source evidence, native batch application, and shared display resolution. Capture exact current rows before mutation. Preserve original SGF/source provenance for repaired games. Back up deleted albums and every dependent row, and account for translation scope proofs affected by deletion or relinking.

**Tech Stack:** Python, SQLAlchemy, PostgreSQL, existing five-language catalog and Galaxy/kiosk clients.

---

- [x] Capture live TEST/PROD gaps, exact deletion candidates, SGF player properties, and foreign-key dependencies. Confirm missing names against original SGF, not only parsed catalog text.
- [x] In parallel: verify Taiwanese historical rank syntax; clean every malformed player value and match an existing canonical identity; prepare all remaining five-language event names. Reuse already recorded authoritative translations and URLs. Direct translations are authorized for absent local names.
- [x] Add only necessary parser/batch support and focused regression tests. An independent reviewer checks the bounded deletion and name mapping before database writes.
- [x] Save compressed recoverable preimages. Dry-run and apply on TEST, verify, then apply on PROD. Preserve surviving identities, ranks, aliases, sources, and display qualification after scope changes.
- [x] Measure both canonical-entity coverage and full five-language card coverage against the new game count, with the old 173,025 baseline and deleted count reported separately. Enumerate any remaining gap; do not count fallbacks as verified translations.
- [x] Review code, merge latest develop into the feature branch, commit/push feature, merge/push develop, update/push smartbox-software submodule, and deploy the integrated release to both clouds (and shared device code if changed). Verify representative live Galaxy/kiosk responses.
- [x] Deliver a concise report of deleted games, cleaned player values, rank retention, completed event languages, coverage, and published/deployed versions.

## Actual execution status — 2026-10-12

- Both databases committed the removal of 1,753 games with no actual player name. Recoverable album/dependency preimages are retained locally and in private release directories. Retained population: 171,272; public list: 171,013; deliberately hidden: 250; duplicates: 9.
- Both databases repaired 343 unique games, including all 39 malformed SGF player fragments. Rank changes cover 80 games / 111 fields; historical 品 remains 品. Original SGF and surviving source provenance are preserved. Two additional Chang Hao slot repairs affect games already included in the unique total.
- Both databases verified the three v10 native name packets and the final v11 supplemental packet, ending at batch 724. Actual added name fields: TEST players 1,391 / events 4,467; PROD players 1,330 / events 4,467. The event fields belong to 954 exact original-title owners, not 954 independent tournament types.
- Focused source checks passed (109 regression tests and six NEC checks); the independent code/data review approved the bounded release. KaTrain feature and develop published `9a36555a9bc9cc6bdb16d77fe8fb71f6b177a1c8`; smartbox-software published `497a55a3c` with that submodule pointer. TEST and PROD serve the integrated application commit.
- Live detail APIs returned all five locales for representative cleaned names and event titles. Physical kiosk visual verification is not claimed: RK3562's application service was already stopped and was left stopped.
- Final full coverage snapshots completed in separate read-only containers after batch 724. TEST fixedwide is 154,985 / 171,272 (90.49%); PROD fixedwide is 155,499 / 171,272 (90.79%). Both strictcomplete values are 171,013 / 171,272 (99.85%); all 171,013 public cards have qualified five-language player/event displays, with zero public gaps. The 259 remaining whole-population gaps are the deliberately hidden/duplicate games.
- Generated first-pass names are accepted display values; their coverage is not a claim that every translation has an established conventional spelling or individual authoritative verification.
- Final search follow-up: the native canonical-plus-raw search and non-strict Chinese provisional fallback were corrected. Five focused regression cases passed; independent review approved the final diff. Both clouds serve `a53f20678d099ae7304e425a0b944802a7890186`; smartbox-software published `b7212f7530ca849da207541b6d19a170b4ac5f29` pointing to that release. Live CN/EN searches for either 吴清源 or Go Seigen each return 1,231 games, with matching first-page IDs in both environments.
- Actual result artifacts: [HTML report](../../resource/kifu-cleanup-report-2026-10-11.html), [Markdown report](../../resource/kifu-cleanup-report-2026-10-11.md), and [structured report](../../resource/kifu-cleanup-report-2026-10-11.json). Recoverable backups and native apply/verify receipts remain private local/release artifacts.
