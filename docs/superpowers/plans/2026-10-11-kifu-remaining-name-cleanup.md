# Remaining Kifu Name Cleanup Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development for the independent research and cleanup tasks. Keep production SQL and release coordination in the root agent.

**Goal:** Delete games without actual player names; separate historical ranks and damaged SGF fragments from real names; complete the five display languages for remaining players and events; publish accurate post-cleanup statistics.

**Architecture:** Reuse the current entity IDs, name tables, source evidence, native batch application, and shared display resolution. Capture exact current rows before mutation. Preserve original SGF/source provenance for repaired games. Back up deleted albums and every dependent row, and account for translation scope proofs affected by deletion or relinking.

**Tech Stack:** Python, SQLAlchemy, PostgreSQL, existing five-language catalog and Galaxy/kiosk clients.

---

- [ ] Capture live TEST/PROD gaps, exact deletion candidates, SGF player properties, and foreign-key dependencies. Confirm missing names against original SGF, not only parsed catalog text.
- [ ] In parallel: verify Taiwanese historical rank syntax; clean every malformed player value and match an existing canonical identity; prepare all remaining five-language event names. Reuse already recorded authoritative translations and URLs. Direct translations are authorized for absent local names.
- [ ] Add only necessary parser/batch support and focused regression tests. An independent reviewer checks the bounded deletion and name mapping before database writes.
- [ ] Save compressed recoverable preimages. Dry-run and apply on TEST, verify, then apply on PROD. Preserve surviving identities, ranks, aliases, sources, and display qualification after scope changes.
- [ ] Measure both canonical-entity coverage and full five-language card coverage against the new game count, with the old 173,025 baseline and deleted count reported separately. Enumerate any remaining gap; do not count fallbacks as verified translations.
- [ ] Review code, merge latest develop into the feature branch, commit/push feature, merge/push develop, update/push smartbox-software submodule, and deploy the integrated release to both clouds (and shared device code if changed). Verify representative live Galaxy/kiosk responses.
- [ ] Deliver a concise report of deleted games, cleaned player values, rank retention, completed event languages, coverage, and published/deployed versions.
