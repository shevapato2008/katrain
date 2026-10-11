# Task 3 native adapter independent code review

Date: 2026-10-09. Reviewer: `/root/zh_ko_native_adapter_review_astra`.

Reviewed the actual TEST/PROD baseline files in `/tmp/kifu-zh-ko-native-baselines-root-20261009` against the four overlays in `/tmp/kifu-zh-ko-native-adapter-20261009`. Task 1/2 commit `536718120c3c8630ba56b4d2a656f120e93152af` is the approved source baseline. This review concerns the local native adapters only; it does not approve live candidates, SQL writes, builds, restarts or deployment.

## Spec review — PASS after one correction

The importer overlays are byte-identical to the approved canonical files. The TEST web reader adds explicit ZH dispatch and live source validation to its existing ORM gate. The PROD web reader retains its older SQL adapter and models. Both use the pure applied-proof helper, enforce integer proof IDs, separate JA/ZH qualification, and preserve the existing request context argument and exact-search flow.

CN/EN anchors are rechecked against the current name/evidence images, applied source batch, hashed source bundle and contained candidate/research, and creation after-images. Removing mutable payload/rule markers is recognized from the evidence creation ledger and denied. The corrected PROD adapter additionally recognizes the original ZH/JA method from a bounded lookup of the immutable name creation ledger, including when the current evidence link is removed or redirected. No source qualification is cached in the request context.

### Corrected Important finding: detached evidence bypassed the PROD display gate

Initial location: `PROD-web/katrain/web/kifu/identity.py:187–190` in the overlay before correction.

The initial `_normative_player_name_rows` returned every verified name as an ordinary row when its result set had no non-null `evidence_id`. This return happened before inspecting the name's ZH rule or its creation ledger. The later creation lookup also followed only the current evidence ID, so removal or repointing of that ID could disconnect recognition from the original name creation record.

Minimal real SQLite reproduction: import the existing synthetic ZH fixture with qualified CN and EN sources, then set only the generated KO row's `evidence_id` to `None`. The initial PROD reader returned:

```text
(display, exact_owner_ids, admitted_generated_rows)
('왕훙웨이', set(), 1)
```

Expected: `(None, set(), 0)`. The TEST reader correctly denied this case. The initial PROD display therefore exposed a name without its required applied proof and disagreed with exact search and qualified coverage.

The correction removes the early ordinary fallback and recognizes originally generated ZH/JA names from the bounded immutable **name** creation ledger as well as the current evidence markers. A missing or redirected evidence link now reaches the generated proof gate and fails closed. Ordinary legacy rows retain their existing fallback. Independent reruns pass for null and redirected links, each with retained and removed mutable markers, alongside the existing positive/source-revocation cases. This finding is resolved.

## Quality review — PASS

The saved patches stay within the approved native adaptation scope: no schema, full ORM replacement, unrelated handler change, or general transliterator. The four-file web overlays are appropriately small. The correction adds one ledger query bounded to the names already selected. No Essential/Important finding remains.

## Independent verification

- Recomputed all before/after/patch SHA-256 values in `manifest.json` against the actual baseline and overlay files; all match. All 20 modified Python files compile.
- Imported both native readers/helpers in fresh processes with their actual unchanged baseline `models_db.py`; both pass.
- Imported both copied pure evidence modules with `name_candidates` and `models_db` imports explicitly rejected; ZH dispatch and malformed-input denial pass.
- Ran `PYTHONPATH=. python /tmp/kifu_zh_ko_native_adapter_review_check.py`. Before adding the detached-evidence regression, both adapters passed exact owner IDs, generated display, CN and EN source-batch revocation with the same retained request context, strict proof IDs (`True`, `1.0`, `[]`), removed mutable payload/rule markers, JA positive qualification, and English preservation. TEST also verifies RU maps to EN. The untouched PROD endpoint performs the same RU-to-EN mapping.
- Before correction, the same script's detached-evidence regression passed on TEST and failed on PROD with the exact tuple above.
- After correction, reran the script and then extended only the reported regression to null/redirected evidence links × retained/removed mutable markers. **Both adapters pass all assertions**. It uses temporary SQLite data only. Two explicit dialect accommodations are limited to the existing PostgreSQL cast and equivalent timestamp serialization; qualification logic is not mocked.
- Recomputed the final manifest's baseline/overlay/patch hashes and recompiled all 20 modified files after the correction; all pass. Final PROD `identity.py` SHA-256: `52aff4159c156d34f17bddeb49feff53cf2082b4245b5a7713944a3cd10a615e`.

The 王宏伟 fixture is synthetic structural validation and is not first-batch eligibility evidence. No full suite or live environment operation was performed.

**Decision: PASS.** The native adapter code is ready for the planned build and environment verification. Actual first-batch eligibility, deployment and live readback remain separate Task 3 work.
