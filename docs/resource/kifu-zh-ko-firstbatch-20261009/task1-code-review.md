# Task1 code review

Final review: 2026-10-09, against HEAD `6b24071d` and the uncommitted Task1 changes in `katrain/web/kifu/name_zh_ko.py`, `katrain/web/kifu/name_evidence.py`, and `tests/web_ui/test_kifu_name_candidates.py`.

Scope: Task1 of `docs/superpowers/plans/2026-10-09-nikl-zh-ko-player-names.md`, using the independently approved `source-and-rule-decision.json` / `.md` in this directory. The review followed the requested order: Spec first, then Quality, with bounded rechecks of the reported fixes.

## Spec

**PASS. No remaining Essential or Important Task1 blockers.**

- JA and ZH use separate positive markers and exact basis/rule tuples. Partial or mixed markers fail; the existing JA validation is not weakened.
- The finite renderer freezes exactly the six approved syllables, pins the official NIKL URL/body hash and source locators, and deterministically reproduces `왕훙웨이` and `웡쯔위`. Fixed rule metadata is appropriate; each record need not embed the full NIKL response.
- Evidence retains reviewed modern-mainland/ordinary-Mandarin scope, exact owner/original-name identity, the complete published Pinyin, surname/given and syllable boundaries, and captured identity/reading bodies with recomputed hashes. It does not infer a reading from Han characters.
- Contrary checks preserve actual Pinyin or Han queries and literal Hangul roster scans, with separate finite Go `search_scope`. The U-Go URL query is bound to the recorded query. Real HTTP captures and saved tool responses retain distinct contracts; unavailable results cannot claim absence. Matching community use remains positive reference evidence.
- The pure ZH candidate validator binds the exact research and positive-content hashes, owner, rule entries, boundaries, full output, independent reviewer and capture/review times. Pending research and approved exact candidates have separate states.

Task2 routing, EN anchor support, live source rechecks, persisted applied proof, importer and reader integration, exact search, coverage and collision checks remain explicitly deferred. This PASS does not approve a real candidate bundle, database write or deployed reader.

## Quality

**PASS. All reported Important findings are closed; no Essential findings.**

1. **Actual query preservation — closed.** The original requirement for synthetic Han/Pinyin/Go tokens was replaced with actual-query plus finite-source-scope validation. Both selected owners' real query forms pass, while wrong or missing scope and changed URL/query bindings reject.
2. **Reliable official Korean usage — closed.** The guard covers `official_go_roster`, `official_roster`, `professional_go_roster` and `professional_go_profile`. Same-person Han+KO detection now uses the already hash-validated captured `body_excerpt`, independent of how `relevant_matches` is grouped. Combined, split and omitted match-list representations cannot conceal the same official row. The captured different-person case remains resolvable.
3. **Single original-form match reported absent — closed.** The absence guard uses Han OR complete verified Pinyin. A captured exact match to either form cannot be labelled `not_found`; unavailable remains a separate outcome.

The implementation stays within the existing pure evidence path and a dependency-free finite renderer. It introduces no service, schema or general transliteration framework. The 64-character registry-version guard addresses the reported production column boundary and has a focused regression check.

Verification:

- Latest independent run: `PYTHONPATH=. python -m pytest tests/web_ui/test_kifu_name_candidates.py -k 'positive_zh_ko or positive_ja_ko or registry_version' -q` — **61 passed, 98 deselected**.
- Earlier independent full candidate-file run during this review — **152 passed**. Subsequent rechecks were limited to the two repaired guards and their focused cases; the final full-file count reported by the implementer was not independently rerun.
- Recomputed all **13** body hashes in the approved source decision against the saved files: all matched. Verified the code's pinned official rule URL/body hash and recomputed both approved full Korean outputs.
- Independently reproduced the original failures before their repairs; inspected the final guard changes and verified the corresponding regression cases after repair.

No production code, candidate signatures, SQL, cloud state, Git history or deployment was changed by this review.
