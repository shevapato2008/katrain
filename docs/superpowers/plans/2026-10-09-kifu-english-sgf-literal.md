# English-form SGF Literal Titles Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Admit the approved finite `sgf_english` raw-title profile through the existing owner and five-language name path.

**Architecture:** Validate lossless saved parser parts with a dedicated ASCII/English-ordinal grammar. Bind research language, parts hash, owner marker, frozen manifest, full scope and CAS using the existing pipeline. Do not alter parser, schema, identity, or UI.

**Tech Stack:** Python, SQLAlchemy, pytest.

---

**Files:** `katrain/web/kifu/raw_event_translation.py` (validator/research/owner match); `scripts/kifu_raw_event_title_owners.py` (profile/validator dispatch/CLI); `tests/web_ui/test_kifu_raw_event_title_translation.py` and `tests/web_ui/test_kifu_raw_event_title_owners.py` (focused behavior and regressions).

### Task 1: One bounded profile

- [x] **Step 1: Red.** Add tests for actual core-only, prefix spaced, prefix joined, and comma-suffix parts; five-language apply/strict reads; profile-language mismatch, invalid ordinals/characters, and parts/hash tampering. Run the two targeted files and confirm new tests fail for missing `sgf_english` support.
- [x] **Step 2: Green.** Add an explicit English validator and profile dispatch; require `original_language=en` for `sgf_english` and `zh-Hans` for both Chinese profiles; reuse current owner marker, frozen manifest, scope/CAS, and CLI. Keep original Chinese gates intact. Rerun targeted tests.
- [x] **Step 3: Verify.** Exercise scope/CAS drift and Chinese regression tests in the same two files; self-review the four-file diff and report results for a fresh independent review. Do not run real database/capture, deployment, or Git mutation.
