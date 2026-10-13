# Task 2 independent code review

Date: 2026-10-09. Reviewer: `/root/zh_ko_task2_review_astra`.

Reviewed the six Task 2 working-tree files over `d588f39c`, including the strict integer proof-ID correction made during this review. Task 1's accepted contract is the baseline. Scope: exact approval, applied proof, source integrity, importer and qualified readers. No production data, deployment, or Task 3 adapter approval is asserted here.

## Spec review — PASS after one correction

- Candidate routing uses the distinct Chinese basis/rule pair. The ordinary generated path retains its negative-search requirement. Chinese markers cannot be claimed by JA's broad legacy recognition; the existing JA positive regression still passes.
- Stored `normative_zh_ko` proof binds the batch, research and candidate hashes. The pure helper checks the applied batch, frozen bundle/member/research, exact owner/language/name/revision, and both name/evidence after-images. Creation-ledger recognition keeps removal of mutable markers from falling through as an ordinary name.
- The importer requires a null KO target preimage and rejects normalized different-owner KO collisions, both within a bundle and against existing verified names.
- CN/EN anchors bind the exact conventional source name/evidence, applied source batch, signed source bundle and creation journal. Both import and read recheck them. An anchored record fails closed when the pure helper has no live-source callback. English display validation does not establish Pinyin; the separate captured reading and independent exact review remain required.
- Display, exact-name matching and coverage use the same qualified gate. The SQLite tests cover pending/malformed proof, research/output changes, marker removal, and CN/EN source batch/name/evidence/journal drift. A separate bounded endpoint check also confirmed the actual search and RU-to-EN behavior described below.

### Corrected Important finding

`katrain/web/kifu/name_evidence.py:1885`: the initial pure helper compared proof IDs using Python equality without enforcing their type. On a real applied SQLite batch with ID `1`, changing only `evidence.research_payload.normative_zh_ko.batch_id` to `True` or `1.0` still returned `True`, even against the unchanged creation ledger. Python considers both values equal to integer `1`. The ORM wrapper already rejected them, but the pure helper is explicitly intended for independent SQL adapters.

The implementation now requires `type(proof["batch_id"]) is int` and `type(batch["id"]) is int`. The existing dependency-free helper test directly exercises `True` and `1.0` against untouched after-images. This finding is resolved; no Essential/Important finding remains.

## Quality review — PASS

The change stays within the existing candidate/importer/reader flow and adds no schema or general transliteration framework. SQL source checking remains outside the pure helper, with an explicit callback and a fail-closed default. Changes to shared JA and orthographic code are bounded and preserve their existing proof gates. The six-file diff and the focused integration checks provide sufficient evidence for this task; no full-suite or release review was performed.

## Independent verification

1. Before the strict-ID correction:

   `PYTHONPATH=. python -m pytest tests/web_ui/test_kifu_name_candidates.py tests/web_ui/test_kifu_name_batch.py -k 'positive_zh_ko or positive_ja_ko' -q`

   Result: **74 passed, 191 deselected**.

2. Independently reproduced the strict-ID issue with a fresh temporary SQLite database, then inspected the correction and reran the affected importer/reader tests:

   `PYTHONPATH=. python -m pytest tests/web_ui/test_kifu_name_batch.py -k 'positive_zh_ko or positive_ja_ko' -q`

   Result: **14 passed, 92 deselected**, including the direct pure-helper regression.

3. Fresh temporary SQLite import with both qualified CN and EN anchors, calling `strict_matching_names` and the existing `list_kifu_albums` endpoint function with `KIFU_STRICT_NAMES=1`:

   | Observation | Before source revocation | After CN batch changed to pending |
   |---|---|---|
   | Exact KO owner IDs | `{5498}` | `set()` |
   | Exact KO API album IDs | `[12]` | `[]` |
   | RU request for the English name | `[(12, "Wang Hongwei")]` | `[(12, "Wang Hongwei")]` |

   All assertions passed. This exercises the endpoint function directly, not a deployed HTTP server.

**Decision:** Task 2 is ready to proceed. Deployed legacy adapters and the actual first-batch execution remain Task 3 work.
