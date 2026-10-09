# Four Sourced Mandarin Names Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver the missing Korean names for Huang Jia-Yin, Yang Yilun, Ke Peichen and Wang Zihan using their actual published readings, including Taiwanese sources, without weakening the existing applied name proof.

**Architecture:** Extend the existing finite NIKL profile with ten reviewed syllables and one explicit modern Mandarin scope shape. Preserve legacy scope and single-page evidence; support an exact paired GoRatings profile where Han and Latin appear in separate locale pages. Reuse existing candidate review, native importer, journal and qualified display/search; no schema or UI changes.

**Tech Stack:** Python, existing name evidence/importer, PostgreSQL, focused pytest, pinned NIKL and profile captures.

---

## Scope and source decision

The independent Astra decision is [source-and-rule-decision.md](../../resource/kifu-next-ko17-source-research-20261009/source-and-rule-decision.md), with detailed JSON and original captures alongside it. Approved exact inputs:

| PROD player ID | Original | Reading words | Korean |
|---|---|---|---|
| 6531 | 黃家胤 | `[[huang], [jia, yin]]` | 황자인 |
| 5115 | 杨以伦 | `[[yang], [yi, lun]]` | 양이룬 |
| 5214 | 柯沛辰 | `[[ke], [pei, chen]]` | 커페이천 |
| 5543 | 王紫涵 | `[[wang], [zi, han]]` | 왕쯔한 |

5806/Wesley Hsiao and Wang Hongwei remain on hold. This is not a generic transliterator or a rule for all English name fields. Weng delivery uses the unchanged r7 code and closes before this cohort's SQL writes. Root alone deploys and writes data.

## Chunk 1: bounded contract extension

### Task 1: Finite rules and honest evidence shape

**Files:**
- Modify: `katrain/web/kifu/name_zh_ko.py` (ten syllables with exact NIKL locators).
- Modify: `katrain/web/kifu/name_evidence.py` (`_validate_positive_zh_ko` only, helpers if needed).
- Modify: `tests/web_ui/test_kifu_name_candidates.py` (four inputs and contract rejection checks).

- [ ] Add failing tests for all four exact outputs, unknown syllables, invalid scope, wrong paired player ID, changed source body/hash and missing published form.
- [ ] Add only `huang 황, jia 자, yin 인, yang 양, yi 이, lun 룬, ke 커, pei 페이, chen 천, han 한`; preserve old entries byte-for-byte. `jia` cites Chinese section item 2 (`쟈 → 자`), not a guessed composition. Keep the same pinned NIKL rule body and version; the signed `used_entries` binds the exact selected entries.
- [ ] Preserve existing scope shape (`modern_mainland=True`, ordinary Mandarin/personal name/basis/no variants). Add a distinct accepted shape `{modern_standard_mandarin: True, ordinary_mandarin: True, personal_name: True, basis: <per-person source decision>, unresolved_reading_variants: []}`. Mixed shapes or false flags fail. Nationality/residence alone never satisfies scope. Do not claim Taiwanese players are mainland players.
- [ ] Preserve single-page reading proof. For paired GoRatings pages add optional `reading.profile_pair` with exact `{provider: "goratings", player_id: <positive integer>, original_url: <identity capture URL>}`. Both real captures are independently hashed; URLs must be HTTPS on `goratings.org` or `www.goratings.org`, exact `/zh/players/<same id>.html` and `/en/players/<same id>.html`, without query/fragment. Original capture must contain the exact Han original; reading capture the complete published Latin. Both must contain the same third-party authority profile link (an exact `authority_url` in the pair). Use the actual common authority URL for this cohort; the pair has no alternate birthday branch. No concatenated or synthetic HTTP response, and no fallback to arbitrary same-name pages. Pair shape includes `authority_url`, so its accepted keys are provider/player_id/original_url/authority_url.
- [ ] For 6531 keep original `黃家胤`, `zh-Hant` and the actual Traditional Chinese page language. Use the real bilingual official page as the captured exact owner bridge and a qualified EN anchor; omit the mismatched simplified CN anchor. The existing TW name may corroborate the owner but is not a live source anchor: the current reader does not support that anchor type. Preserve existing CN/EN anchor validation and do not add a TW proof path or manufacture a conversion proof.
- [ ] Run `PYTHONPATH=. /opt/miniconda3/bin/python3.13 -m pytest tests/web_ui/test_kifu_name_candidates.py -k 'positive_zh_ko or positive_ja_ko' -q`; all selected tests pass. No whole-suite expansion.

### Task 2: Persisted reader compatibility and independent review

**Files:**
- Modify: `tests/web_ui/test_kifu_name_batch.py` (one new paired-scope importer→reader case).
- Create: bounded review note in `docs/resource/kifu-next-ko17-source-research-20261009/`.

- [ ] Add one importer→reader test for the new Mandarin/paired shape: approved KO displays/searches same owner, missing or altered proof and revoked source fail display/search eligibility; existing Weng/JA paths still pass. Reuse current fixture and journal checks.
- [ ] Run focused candidate and batch selectors separately. Request independent code review of touched files and fix concrete issues. No second proof framework.
- [ ] Root commits only these code/tests/plan/review files and pins resulting hashes for minimal native importer/reader backport. Existing deployed ORM, environment/config, mount policy and unrelated handlers remain intact.

## Chunk 2: actual four-name delivery

### Task 3: Prepare and write names, preserve pages and report

**Files:** Actual research, candidate approvals, native receipts and bounded archive under `docs/resource/kifu-next-ko17-source-research-20261009/`; reuse the current native delivery helper with only cohort membership/output parameters where needed.

- [ ] Prepare actual per-person source records using the stored original bodies/times; pair Chinese and English pages without rewriting either. 5543 has a same-ID community Korean hit consistent with the rule; record it as a reference match, not absence or an official conventional name.
- [ ] Root captures fresh TEST/PROD actual IDs, targets, source ledgers, catalog, collision and selected physical albums; do not infer TEST IDs from PROD. Independent Astra reviews exact bound candidates. No pending names counted as completed.
- [ ] Root uses pinned native code: read-only dry-run, TEST apply/readback, then PROD apply/readback. Recheck physical owner/catalog/SGF/FK/source/target under the existing write lock; preserve hidden250, ranks, album IDs and SGFs. Archive actual receipts, not full inventories.
- [ ] Verify actual cn/ko/en/ru HTTP results preserve same game IDs and English fallback. Add professional/Wikipedia URLs using existing authority-page synchronization without replacing unrelated page metadata. Update bounded actual player/card counts and percentages after the write. Commit/push scoped closure files.

## Acceptance

Done when the four sourced names are actually qualified and searchable in both cloud environments, with authority URLs stored and honest statistics. Holds remain explicit; no RK restart. Existing five-language names and immutable applied proofs remain valid. User authorization covers execution; no additional approval question is required.

## Discovered regression: preserve the reviewed legacy negative method

The real r7 catalog comparison found four batch-332 Korean names using the same rule-version string as the new positive profile. Their immutable creation images contain approved negative-closure research rather than `normative_zh_ko`; the new reader therefore rejected valid existing names. Actual read-only capture: `/tmp/kifu-zh-ko-weng-closure-root-20261009/598-old332-four-capture-actual.json.gz`; 730 unique albums / 731 target slots. An independent Astra review confirmed the exact research/closure/review hashes and current creation images.

**Files:** Minimal pure compatibility helper in `name_evidence.py`, qualified reader branch in `identity.py`, focused existing batch test, and the inspected native SQL reader adaptation. No database write or migration.

- [ ] Add one legacy-negative reader regression and one stripped-positive/altered-legacy rejection check before implementing the fix.
- [ ] Accept the existing legacy method only when the complete live evidence equals its unique `before_image=null` creation after-image in an actually applied batch, with exact approved candidate/research/negative-closure/generated-review bindings. Do not remove rule-only recognition or let arbitrary missing positive proof fall through. New positive creation remains governed by its immutable positive proof even after mutable markers are removed.
- [ ] Keep new import restrictions unchanged; this is read compatibility for already applied research, not permission to republish or overwrite a name using an old method.
- [ ] Independently review the focused code and native backport; verify the actual four old owners regain qualification and Weng remains qualified before updating the 598 coverage totals. Reuse the eight-game Weng delta once the original catalog set is restored; no full 173k strict rescan.

## Finite next-five rule extension (2026-10-09)

Independent source/rule review at `/tmp/kifu-mandarin-next5-nikl-extension-luna-20261009/norm-extension-review-astra.md` approved twelve further syllables for five sourced readings: `qing/hai/xiao/rui/shan/ye/hui/dong/tian/xu/jian/ying`. Preserve the original eighteen entries, the v1 rule version, and legacy `korean.go.kr`/`92977…` proofs. New entries require the exact captured `www.korean.go.kr`/`fba750…` pair; crossed URL/hash pairs and new syllables on the old capture fail. `xu` cites the Ministry of Education spelling explanation at raw line 206, and `jian` is identified as a rule composition rather than a quoted example. This changes only the finite rule and its evidence check; owner-bound candidates, native deployment and database writes remain separate reviewed steps.
