# Five-language fast first pass implementation plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development. Steps use checkbox syntax.

**Goal:** Store usable five-language player and event names with honest provenance, then correct generated titles whose untranslated content was replaced by pinyin; keep list/search available throughout.

**Architecture:** Add one opt-in `user_authorized_first_pass_v1` generated profile to the existing candidate, evidence, transaction and reader paths. Reuse existing identities, authoritative links, exact preimages, journals and rollback. Preserve approved names. Split frozen whole-catalog work into parallel translation shards and transactions of at most 200 owners; independently check each batch once.

**Tech Stack:** Existing Python/SQLAlchemy/PostgreSQL kifu pipeline; no schema or UI redesign.

**Decision:** `/tmp/kifu-fast-first-pass-decision-astra-20261011/decision.md` SHA-256 `407de435948e0c6329a91c2a82108b5b6045a3c13e8af3806d37602aa7efadfd`. Latest user explicitly permits direct translation when published names are unavailable, requires speed, and forbids excessive reviews.

## Chunk 1: Implement and verify the minimal profile

### Task 1: Generated profile, import and read qualification

Files: create `katrain/web/kifu/name_first_pass.py`; modify `name_evidence.py`, `name_candidates.py`, `name_batch.py`, `identity.py`; add a focused `tests/web_ui/test_kifu_name_first_pass.py`.

- [ ] Add failing examples for generated input without external search, preserving existing approved slots, source/target CAS, real persisted read qualification and exact raw-event scope.
- [ ] Run `PYTHONPATH=. /Users/fan/Repositories/katrain-kiosk-go-kifu/.venv/bin/python -m pytest tests/web_ui/test_kifu_name_first_pass.py -q`; confirm meaningful failures.
- [ ] Add the single explicit generated profile described in the decision; retain old paths and independent signature, collisions, transactions and journals. Mark `verification_level=generated_first_pass`; do not invent source URLs or published readings.
- [ ] Use precise `(album_id, raw, event_id)` scopes for raw titles and existing approved selections; never globally inherit a generated title across different event identities.
- [ ] Re-run the focused file plus the affected existing candidate/batch/identity tests. Record unrelated existing query-budget failures without expanding this task.
- [ ] Perform one independent focused code review, fix actual failures, and freeze exact changed files for root integration.

## Chunk 2: Parallel generation, actual database delivery

### Task 2: Fill the frozen missing pool

Files: `/tmp/kifu-full-firstpass-pool-sol-20261011/*`; per-agent generated JSON chunks; existing name-batch runner and progress documents.

- [ ] Capture TEST and PROD once in read-only snapshots after the actual batch644 receipt; reuse structure artifacts for names-only batches.
- [ ] Assign disjoint frequency-balanced player shards and event core/title shards to available Luna workers. Skip every existing `status=verified` row and every evidence-backed row; write only absent or evidence-free review slots. Supply missing five-language names and truthful method tags, write chunks every 20 entities. No repeated web search or negative-evidence gate.
- [ ] Bind actual TEST/PROD IDs and original rows, check all generated proposed names for obvious mistakes and owner collisions once, and sign exact batches once. Hold only genuinely conflicting identities or damaged data.
- [ ] Before the first new-profile write, root deploys the same approved reader/importer profile to TEST/PROD and RK3562; verify representative read qualification. Root then executes TEST dry/apply/readback and PROD for each at most 200-owner transaction. Preserve journals and prior source URLs; prepared files do not count as uploaded.
- [ ] Report actual completed entities and affected games after each commit; use bounded before/after deltas for fixed wide coverage and strict complete-card coverage. Reserve full-catalog coverage sweeps for the first representative validation and final report. Distinguish generated first pass from sourced names.
- [ ] Archive exact receipts/data, commit and push the authorized branch, and verify language switching/search with representative real API results.

### Completion criteria

All safe missing five-language slots are stored and usable by list/detail/search; report actual remaining identity collisions or damaged/hidden records separately. Other six UI languages fall back to English. Field completeness is not translation quality: pinyin or original-language fallback in a descriptive title does not count as completed semantic translation. Generated names must not be claimed as authoritative published translations.

## Chunk 3: Correct generated raw-event titles without replacing sourced names

### Task 3: A reusable, bounded generated-title correction gate

**Files:** modify `katrain/web/kifu/name_batch.py`; extend `tests/web_ui/test_kifu_name_first_pass.py`. Reuse `name_first_pass.py`, the existing signed bundle, source-scope checks, transaction, evidence and change journal. No schema changes, direct SQL update, new identity or album/SGF edit.

**Context and acceptance:** The actual English page contains `Game 2 Cheng Ming Zuo`, `Da Dan De Bu Ju`, and a book/collection caption rendered as pinyin. The current verified-name replacement exception supports only the reviewed batch712 player cells. Add a general raw-event correction branch; keep that player exception unchanged. A title can be corrected again later when another real mistake is found; do not restrict the new branch to four hardcoded owners or one batch number.

- [ ] Add a failing test for a valid `raw_event` generated-first-pass title correction, including reader qualification and complete before/after journal. Add focused rejection cases for an authoritative/evidence-backed non-first-pass row, changed name/evidence/revision or prior-batch hash, stale raw scope, and a candidate of another owner kind. Cover two consecutive corrections (generated v1 → corrected v2 → corrected v3): v3 qualifies through the newest update journal, while old v1/v2 CAS and markers are rejected. Keep an existing batch712 test as the regression for its separate authority-based player exception.
- [ ] Implement one marker version, `generated-raw-event-semantic-correction-v1`, on `first_pass_correction`. Bind the same owner/language/raw value, full name preimage SHA, prior name revision, prior candidate SHA, prior evidence SHA, prior applied batch ID and bundle SHA. The ordinary signed candidate binds the new research and scope. No invented external authority is required for user-authorized event translation.
- [ ] Require the live old name to be a qualified `user_authorized_first_pass_v1` generated name. Explicitly check the live name and evidence each have the required qualified status, `decision_kind=generated` and `generation_rule_version=user_authorized_first_pass_v1`; do not rely on the reader's existing chained inequality to establish those equalities. Verify existing persisted eligibility, exact evidence/candidate, applied signed batch membership and name/evidence journal after-images. A non-generated sourced name is never replaceable through this branch. Repeated corrections must validate the most recent generated revision and its actual journal, not assume the row was first created in that batch.
- [ ] Require the new research to use `raw_event_literal`, `generation.method=translation`, exact owner source image and complete live `raw_scope`. Preserve raw values, identity IDs, relationships, source URLs, original evidence and prior journal; new revision/evidence are written through the existing atomic candidate path.
- [ ] Run only the affected first-pass and correction tests. Perform one independent spec check and one focused code review covering overwrite protection, scope/CAS and reader proof. Fix material findings; no unrelated refactor or new audit infrastructure.

### Task 4: Parallel semantic translation and immediate database delivery

**Artifacts:** `/tmp/kifu-raw-event-semantic713-20261011/*`, per-worker title chunks, existing native bundle runner and actual database receipts; update the existing HTML progress report.

- [ ] Capture the four visible raw-event owners 98485, 73624, 73800 and 69402 read-only from each live environment with exact current names, evidence and finite scopes. For joined Latin text, read the complete original before translating; preserve unknown or truncated parts explicitly rather than inventing text.
- [ ] Assign independent Luna workers complete five-language title translations and reusable year/round/book-caption templates. Use Sol for ambiguous proper names. Existing sourced player names remain unchanged. Events and archive captions may be directly translated as authorized; no per-title web research or Astra review.
- [ ] Apply the pilot through native TEST dry/apply/readback, then independently bound PROD dry/apply/readback. Check one actual English result page and list/detail matching. A prepared bundle is not an uploaded result.
- [ ] Capture a bounded live inventory of generated titles still containing pinyin or unsegmented Latin text; rank by actual affected public game count. Candidate archive counts are only work estimates, never current PROD coverage statistics.
- [ ] Dispatch disjoint frequency-balanced title/template shards to available Luna workers. Trial 20 owners once, then reuse the tested transaction capacity of at most 200 owners. Root remains sole SQL/SSH/Git writer. Validate numbers, proper names and complete semantic content once per template plus exceptional titles, not repeated independent reviews per title.
- [ ] After each actual commit report player and event field completeness, fixed entity coverage and strict complete-card field coverage, plus this pass's actual corrected title/slot/game counts. Keep semantic translations, transliterations, retained original and pending text separate. Do not invent a global semantic quality percentage before its live denominator has been captured.
- [ ] Commit/push the feature and develop branches, update `smartbox-software/vendor/katrain`, deploy approved runtime changes to TEST and PROD, and deploy RK3562 when SSH connectivity returns. Report that device separately if it remains unreachable.

**Semantic completion criterion:** The actual targeted live title pool has complete translated descriptive content in cn/tw/jp/ko/en with numbers and known proper names preserved. Correct original text already in the target language and valid orthographic conversion may be retained and counted separately as no translation needed. Original/transliteration fallback and unresolved truncated titles are explicitly reported. Neither 97.02% field completeness nor a method tag alone proves translation completion.
