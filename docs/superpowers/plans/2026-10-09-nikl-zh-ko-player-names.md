# Finite NIKL Chinese-to-Korean Player Names Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate reviewed Korean display names for a small batch of verified modern mainland Chinese players whose ordinary Mandarin names and complete Hanyu Pinyin readings are already sourced.

**Architecture:** Add the explicit `normative_zh_ko_v1` positive evidence profile to the existing research, candidate, batch and qualified reader path. A frozen, finite NIKL syllable table renders only reviewed readings; the same applied proof and live source checks govern display, exact search and coverage. Keep conventional Korean names authoritative and leave uncertain owners on hold.

**Tech Stack:** Python, existing SQLAlchemy name importer/readers, PostgreSQL, focused pytest, existing NIKL capture packet.

---

## Gate and files

Start implementation **after** the current 16-player conventional batch is closed. The approved scope and source facts are in [the decision](../../resource/kifu-next-source20-roster3-20261009/astra-native16-and-zh-ko-next-step.md) and [the NIKL capture packet](../../resource/kifu-nikl-cn-ko-research-20261009/rule-findings.md). The five original response hashes are indexed in `docs/resource/kifu-nikl-cn-ko-research-20261009/capture-index.json`; reuse them, without fetching the same rules again. The full rule response has SHA-256 `92977a7c4e2d255aa62d91011372bea1a198f5c3ee6f92db5b02fa6366fb9d9b`.

| File | Responsibility |
|---|---|
| `katrain/web/kifu/name_zh_ko.py` (new) | Fixed profile constants, only the actually needed reviewed Pinyin syllable→Hangul entries, source fingerprint/locators, deterministic full-name renderer. No general transliterator. |
| `katrain/web/kifu/name_evidence.py` | Validate the distinct ZH profile and exact independent review; provide a pure persisted eligibility helper shared with the deployed reader. Keep JA validation intact. |
| `katrain/web/kifu/name_candidates.py` | Route only the exact ZH basis/rule tuple through positive generation; other generated rows retain existing negative closure rules. |
| `katrain/web/kifu/name_batch.py` | Bind ZH research/candidate hashes and applied ledger in the existing batch artifact and evidence payload; check live source dependencies before write. |
| `katrain/web/kifu/identity.py` | Dispatch JA/ZH positive methods separately and gate ZH display/search/coverage on the same applied proof and live source status. |
| `tests/web_ui/test_kifu_name_candidates.py`, `tests/web_ui/test_kifu_name_batch.py` | Focused evidence, batch and reader tests, including one JA regression. Use an existing API fixture in `tests/web_ui/test_kifu_name_api.py` only if the importer→reader test does not cover the exact search IDs. |

No table, service, UI, generic language framework or full ORM replacement. Existing published KO names cannot be overwritten by a generated candidate, even for the same owner. A new name needs a null target preimage; batch collision checks must also reject equal normalized KO names assigned to different owners.

## Chunk 1: one finite positive method

### Task 1: Freeze the reading and rule contract

**Files:** Create `katrain/web/kifu/name_zh_ko.py`; modify `katrain/web/kifu/name_evidence.py`; test `tests/web_ui/test_kifu_name_candidates.py`.

- [ ] Add a failing positive fixture and exclusions. Exact tuple: `source_basis=normative_zh_ko_v1`, `scope_status=generated_from_original`, `generation_rule_version=nikl-zh-ko-personal-name-v1`, `decision_kind=generated`, owner `{kind: player, id: existing_id}`, target `ko`, original language `zh-Hans` or `zh-Hant`. A generic `positive_generation` field or scope marker alone never selects JA or ZH; any partial/mismatched marker fails closed.
- [ ] Require reviewed modern mainland/ordinary Mandarin scope and an exact same-person bridge to the existing owner and original Han name. Capture the real URL, role, locator, observed language, fetch time, excerpt/body and hash for each identity and reading source. A source may cover both Han name and complete published Pinyin if its actual row does so. Reuse qualified CN/EN source evidence when present, with its exact name/evidence/applied-batch binding; do not require CWA ID, birthday or the existing three-source `two_publisher` template. CN glyphs alone never prove Mandarin, and an EN column is a reading source only when its actual publication and independent review establish Hanyu Pinyin for this person.
- [ ] Store the published spelling, explicit surname/given split, and every syllable boundary as `reading_words`, for example `[["wang"], ["xi", "zhong"]]`; normalize only the declared `pinyin-syllables-v1` marks and separators using the existing normalizer. Require the normalized concatenation to match the published words and all syllables to exist in the frozen table. Preserve `ü` distinction. Reject unresolved `Chun/Chung`, Wade–Giles/Taiwan romanization, alias, ambiguous segmentation or conflicting published readings; never infer a reading from Han characters or a library. Exclude historical people, overseas names with non-Mandarin usage, Korean/Japanese Han names and foreign names translated into Chinese.
- [ ] Freeze only syllables used by the chosen real first batch. Each entry identifies the exact NIKL Chinese table/adjustment locator and whether the Hangul is an explicit table entry or a reviewed composition; pin the above original-body hash and official URL. Render each syllable deterministically, concatenate syllables within given name and surname+given into one Korean display string, and retain both boundaries in evidence. This is the project's Chinese-player format, not a claimed NIKL Chinese-name spacing mandate. Reject unknown syllables and unexplained whole-name outputs.
- [ ] Record the finite actual contrary-name checks: original Han name/verified Pinyin in Go context and proposed Korean name in Go context, with actual query, source/scope, response status/time/body hash/locator and relevant matches. 403/timeout is `unavailable`, never `not_found`; reliable published KO usage sends the owner to conventional review. Require explicit resolution of any conflicting name or owner. Do not demand global negative closure or a fixed three-site checklist.
- [ ] Run `PYTHONPATH=. python -m pytest tests/web_ui/test_kifu_name_candidates.py -k 'positive_zh_ko or positive_ja_ko' -q`. Expected: a valid pending research/candidate and independently approved exact output pass; wrong owner/language/reading/segmentation, unknown rule, tampered capture/hash, unresolved conflict and JA/ZH marker mixtures fail. No old generated path is weakened.

### Task 2: Exact approval, applied proof and read eligibility

**Files:** Modify `katrain/web/kifu/name_candidates.py`, `katrain/web/kifu/name_batch.py`, `katrain/web/kifu/identity.py`, and the pure ZH helper in `katrain/web/kifu/name_evidence.py`; test `tests/web_ui/test_kifu_name_batch.py`.

- [ ] First add a failing importer→reader fixture following `positive_ja_ko_bundle` in `test_kifu_name_batch.py`. Approved `generated_review` binds exact owner, `ko`, original name, published reading and boundary list, reading-source URL, ZH rule version, frozen used entries, full output, research hash, positive-content hash, reviewer ID/model/time and separate input/rule/output approvals. Reviewer differs from producer and signs after all captures. Pending records cannot be read.
- [ ] Extend existing batch evidence with a distinct `normative_zh_ko` proof `{batch_id, research_sha256, candidate_sha256}` and store the exact ZH research in the reviewed artifact. The pure helper checks applied status, signed bundle/member/research hashes, exact owner/lang/name/revision and name/evidence creation after-images. Keep it importable without `name_candidates` or full deployed ORM. `type(batch_id) is int` rejects bool and lists. A removed or renamed mutable marker must still be recognized from the immutable creation ledger and denied, never fall through as ordinary generated/conventional.
- [ ] Recheck a referenced, locally qualified CN/EN source's exact current name/evidence, source batch `applied` status and creation journal at import and read, reusing `name_orthographic.verified_source_live` where its anchor format fits. Revocation or drift removes generated KO from display, exact search and coverage together. External captures remain pinned to actual body hashes. Preserve the JA helper and explicitly dispatch by basis **and** rule; never let JA's broad `is_positive_ja_ko` interpretation of `positive_generation`/scope claim ZH records.
- [ ] Prove one real SQLite import→qualified display/exact search/coverage path and negatives for missing/wrong/changed proof, pending batch, tampered research or output, source revocation and different-owner KO collision. Add one existing JA positive regression and one RU/EN fallback check; compare exact returned owner IDs, not just rendered text. Run `PYTHONPATH=. python -m pytest tests/web_ui/test_kifu_name_candidates.py -k 'positive_zh_ko or positive_ja_ko' tests/web_ui/test_kifu_name_batch.py -k 'positive_zh_ko or positive_ja_ko' -q` (or run those two selectors as separate commands if pytest's combined `-k` obscures selection). Run the single touched API test only if needed to verify HTTP-level search IDs.

## Chunk 2: one sourced batch

### Task 3: Verify the deployed reader and deliver the first eligible owners

**Files:** Actual first-batch research/bundle/receipt under a new `docs/resource/kifu-zh-ko-firstbatch-20261009/` directory; only the minimal saved importer/web reader files required by their inspected TEST/PROD baselines. No planned schema file.

- [ ] After the 16 conventional names close, select a small set of existing modern mainland owners with a published same-person Han+unambiguous Hanyu Pinyin source and missing KO target. Resolve each owner's contrary-name checks and used rule entries; independently review/sign only eligible candidates. Holds stay out of the bundle. Verify current target preimages, cross-owner collisions and original source live bindings before signing.
- [ ] Inspect the actual TEST/PROD importer and web reader baselines. Backport only the ZH profile's pure validator, exact proof dispatch and qualified read gate into each legacy `Pweb`/SQL adapter; keep its older ORM and unrelated handlers. Run the focused import/read fixture against each adapter and confirm source-revocation denial before deployment. Do not copy the repository ORM wholesale.
- [ ] Use `scripts/kifu_name_batch.py` with the exact pinned bundle, registry, inventory, evidence and database URL: `validate`, then TEST `dry-run`→`apply`→`status`/readback, then PROD with fresh preimages and the same checks. Keep existing preimage/undo receipts. Verify one generated KO displayed and searched to the same owner IDs, one RU/EN fallback, source link and honest `generated` coverage in each environment. Save actual hashes, batch IDs and observed results. A source unavailable or unresolved owner simply remains on hold; do not fill a target to reach a quota.

## Completion

Done when the finite profile passes the focused tests, the first sourced batch is actually applied and read correctly in TEST and PROD, and the generated count reflects only qualified live names. The user has authorized this work; this document is preparation only and makes no claim that implementation, SQL or deployment has occurred.
