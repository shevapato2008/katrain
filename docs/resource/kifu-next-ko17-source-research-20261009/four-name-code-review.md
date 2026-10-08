# Four-name extension independent code review

Reviewer: `/root/zh_ko_native_adapter_review_astra`, `gpt-6-astra / max`, 2026-10-09.

**Spec: PASS. Quality: PASS. No Essential/Important finding remains.** Reviewed the final frozen changes in `name_zh_ko.py`, `name_evidence.py` and the two name candidate/batch test files against the approved four-name plan and the r7 source baseline.

- The six existing syllable entry source texts and all pinned rule constants are unchanged. The ten additions exactly match the independently reviewed mapping objects, including the NIKL `jia → 자` adjustment. Existing selected `used_entries` therefore retain their signed values.
- Legacy `modern_mainland` scope and single-page evidence still work. The distinct modern Mandarin shape requires the reviewed personal-name/ordinary-Mandarin flags, source basis and no unresolved variants; mixed or false scope shapes fail. No nationality or residence inference is introduced.
- The optional pair has only the four approved keys. It requires a strict positive integer profile ID, HTTPS GoRatings hosts, matching exact `/zh/players/<id>.html` and `/en/players/<id>.html` paths, no parameters/query/fragment, and the pinned common external authority URL in both independently hashed bodies. Exact Han and complete Latin forms remain required in their respective excerpts. Wrong ID/link, missing authority or published form, and changed body hashes are rejected.
- The modern shape preserves explicit script-language correspondence. The 6531 fixture retains `黃家胤`, the actual `zh-Hant` single-page bridge and its published hyphenated reading. A mislabeled simplified identity capture is rejected. No TW proof type or anchor/read allowlist is added.
- The existing exact candidate/research review hashes and applied journal gate cover the new shape. The paired SQLite importer→reader case resolves the expected owner, displays the generated name and counts it as generated; source revocation removes display, exact-name eligibility and coverage while the generated batch itself remains applied. Existing proof-tamper/source-revocation and JA regressions remain green.

The implementation stays within the existing finite validator and renderer. The focused fixtures are structural tests; they do not sign or approve the actual four database candidates.

## Independent verification on the final files

```text
PYTHONPATH=. /opt/miniconda3/bin/python3.13 -m pytest tests/web_ui/test_kifu_name_candidates.py -k 'positive_zh_ko or positive_ja_ko' -q
80 passed, 99 deselected

PYTHONPATH=. /opt/miniconda3/bin/python3.13 -m pytest tests/web_ui/test_kifu_name_batch.py -k 'positive_zh_ko or positive_ja_ko' -q
15 passed, 92 deselected
```

An independent source comparison also checked all six legacy entry texts and constants, then compared every new mapping to `source-and-rule-decision.json`.

| Reviewed file | SHA-256 |
|---|---|
| `katrain/web/kifu/name_zh_ko.py` | `b8631f4bc74d7982b90101c838591b02c77ed828c3b2b55e52483c17a5270c11` |
| `katrain/web/kifu/name_evidence.py` | `c1e5af429c999e0977911d929192f56af44079c8088f39b17e4d16995be4d98a` |
| `tests/web_ui/test_kifu_name_candidates.py` | `56ff71050a9a7cee27550118edaa359daf27077f0eedbe89860bd2fc5029596d` |
| `tests/web_ui/test_kifu_name_batch.py` | `2690ad1b36588cee67dcc5902302bcdfdf985b91ca001ef1d8ae105b4b4389cd` |

**Decision:** ready for the planned minimal native backport and exact bound-candidate review. This review used local files and disposable SQLite test fixtures only; no live database, SSH, Git mutation or deployment was performed.
