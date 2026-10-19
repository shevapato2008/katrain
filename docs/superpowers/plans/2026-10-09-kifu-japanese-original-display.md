# Japanese Original Display Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Reuse an already qualified Japanese Han name as an explicitly generated CN original-name display and, where supported by finite official glyph rules, a generated TW display, accelerating the user's first translation pass.

**Architecture:** Extend existing `primary-orthographic-v1` with `verified_japanese_display`. Bind the exact same-owner conventional JP name/evidence/applied batch/journal; preserve all JP codepoints for CN and convert directly from that same JP anchor for TW. Reuse existing importer, persistent read eligibility, and coverage; no schema or frontend change.

**Tech Stack:** Existing Python evidence validators, SQLAlchemy transaction/importer, pytest fixtures, PostgreSQL, minimal cloud backports.

## Design and delegated decision

User permits original names when no reliable Chinese name is found and delegates decisions to independent gpt-6-astra max. The session's accepted decision is recorded here: reuse only a same-owner qualified conventional JP name and exact applied-batch/creation-journal proof; CN preserves its original Han codepoints as generated display, TW uses finite official human-name glyph rules; only absent targets may be written, without aliases or identity merges. The former temporary decision file is unavailable and is not a review or implementation dependency. Alternatives: repeat per-person Chinese research (slower, does not improve the already checked cases); display raw runtime fallbacks (quick but cannot qualify stored five-language names). The selected branch stores honest generated display values with exact existing source proof.

Finish the current 20-player CN→TW database delivery before deploying or importing this branch. No new negative-closure research requirement. Prefer an already qualified Chinese name where one exists. No claimed Chinese publication, Chinese ethnicity, or Taiwan publication. Conventional CN increment remains zero.

## Chunk 1: source and generation semantics

### Task 1: Exact JP source binding

**Files:** Modify `katrain/web/kifu/name_evidence.py:1385`; test `tests/web_ui/test_kifu_name_orthographic.py`.

- [x] Extend the existing verified-source fixture to produce conventional JP evidence, avoiding a second fixture framework.
- [x] Add failing tests: same-owner JP is accepted; wrong language/owner, generated JP, candidate/research hash mismatch, revision mismatch, and unsupported characters are rejected.
- [x] Generalize only the existing verified-reference block with an explicit reference-to-source descriptor: CN uses `cn/zh-Hans/Hans`, JP uses `jp/ja/Kanji`. Keep the identical exact binding keys and qualified conventional evidence conditions. Do not relax old branches.
- [x] Accept only 2–16 CJK UNIFIED IDEOGRAPH codepoints; reject kana, Latin, rank text, punctuation, whitespace, `々`, compatibility ideographs and selectors before normalization. Identity HOLD owners remain outside approved data batches.
- [x] Run focused tests with `PYTHONPATH=. /opt/miniconda3/bin/python3.13 -m pytest tests/web_ui/test_kifu_name_orthographic.py -q`.

### Task 2: Two direct targets and persistent proof

**Files:** Modify `katrain/web/kifu/name_orthographic.py` and `katrain/web/kifu/identity.py`; modify `name_batch.py` only if a CN-specific error needs neutral wording; extend the same test module.

- [x] CN rule has exact keys `version,reference_kind,lang,source_lang,source_script,target_script,target_region,preservation` and exact values `primary-orthographic-v1,verified_japanese_display,cn,ja,Kanji,Kanji,CN,exact_codepoints`. Output is byte/codepoint-identical JP original, including Japanese glyphs; no simplification.
- [x] TW rule has the existing finite mapping/exclusion fields plus explicit `reference_kind=verified_japanese_display`, `source_lang=ja,source_script=Kanji,target_script=Hant,target_region=TW,lang=tw`. Every changed and unchanged input requires a reviewed single-valued human-name-applicable official entry. Unknown mappings are omitted from data; existing TW excluded names/characters remain rejected.
- [x] Require source anchor reference to match the rule/member; both targets source the qualified JP directly. Never use the generated CN result as a conventional source for the older CN→TW branch.
- [x] Require target name absent (`name_preimage_sha256=None`) in frozen and locked live state. Existing REVIEW/pending/generated/conventional rows are not overwritten. Reuse cross-owner names/aliases and same-batch target collision rejection.
- [x] Extend the current verified-source snapshot and live proof checks to JP: current name/evidence hashes must match, source batch applied and source candidate/research included, exact name journal after-image matches, unique evidence creation journal has NULL preimage and exact current after-image. Source drift fails import and persistent eligibility/coverage.
- [x] Extend the existing creation-ledger reference-kind check in `identity.py` to include `verified_japanese_display`, preserving the SQL scope. Parameterize the existing `masked_target` case for both CN and TW: removing mutable orthographic markers and disguising generated rows as conventional must not bypass persistent eligibility or increase conventional coverage.
- [x] Add a positive import→read→coverage CN/TW fixture, with generated counts and no conventional CN increment; prove canonical/FK/SGF/rank unchanged using existing scope assertions.
- [x] Add focused negative cases for target REVIEW, cross-owner name/alias collision, wrong rule target, unknown/excluded TW mappings, missing/mismatched batch or creation journal, import source drift and post-import source drift. Run existing orthographic module once after changes.

### Task 3: Review and commit

- [x] Independent code review of the actual diff against this plan's recorded decision; fix material findings, rerun only affected tests. Root alone commits explicit changed files; no unrelated refactor or full-site testing.
- [x] Record actual test results and review conclusion here. Never count prepared candidates as database progress.

## Chunk 2: cloud delivery and next grouped data batch

### Task 4: Minimal cloud delivery

**Files:** Create `docs/resource/kifu-japanese-original-display-deployed-2026-10-09.md` with actual receipts.

- [ ] Root inspect current TEST/PROD web and isolated importer versions. Reuse the previous CN-display minimal backport method; preserve existing identity/search SQL behavior. Review only the actual backport risk boundary; no schema migration.
- [ ] Build isolated importers with exact code hashes, verify imports; deploy web-only TEST then PROD with health checks. No GPU/DB/cron/RK restarts. If a cloud operation disconnects, read actual state before any retry.
- [ ] Independent source agent prepares high-frequency candidates from existing JP proof; binder captures current names/batches/journals and NULL targets. Root signs the exact final data after review. Keep user cadence: 20 distinct ready players per grouped delivery, combining already prepared conventional candidates where valid; partial owners do not count as full five-language owners.
- [ ] Root TEST baseline/dry-run/apply/readback and representative HTTP checks, then PROD. Confirm actual stored generated CN/TW values and English fallback for other locales with the same search collection; retain SGF/rank/IDs/source evidence.
- [ ] After grouped update, refresh actual player/event/game counts and percentages, HTML list, source links and ledger; distinguish generated fallback from local conventional names. Archive exact applied receipts and commit/push explicit files.

## Acceptance and stopping scope

This slice is complete when the JP branch passes focused tests and independent code review, cloud code is healthy, and its first actual data delivery has verified persistent and HTTP results. It does not claim all library translations or 90–95% coverage. Continue the existing player/event translation objective afterward; the 861 approved unlinked slots and queued C76 event names remain separate follow-up work after the current 20-player batch.

## Actual implementation verification

2026-10-09: Tasks 1–3 implemented; 148 focused orthographic tests passed (10.35 s), py_compile and git diff --check passed. Independent plan review (two rounds), spec review and code review all PASS. TEST four-file and PROD three-file minimal backports also passed focused independent review. Cloud deployment and first JP data delivery are pending; no database progress is claimed for this code change.
