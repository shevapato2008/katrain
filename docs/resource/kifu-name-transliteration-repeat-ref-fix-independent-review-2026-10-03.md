# Transliteration symbolic-owner repeat fix: independent review

Reviewed commit: `c8fd79ebd943cab46064e956284cc06a527bfb9e` (`resolve transliteration owner refs on repeat`). Reviewer: `/root/transliteration_repeat_fix_review`. Date: 2026-10-03.

**PASS. No P0/P1/P2 findings.** The confirmed Task 6c P2 self-collision is resolved for v2/v3 symbolic raw owner references. This conclusion covers the importer change, not production data readiness or deployment.

The review inspected the commit diff, first-apply and repeat paths, persisted transliteration eligibility, and conditional undo. At review completion, `git diff c8fd79eb -- katrain/web/kifu/name_batch.py tests/web_ui/test_kifu_name_transliteration_integration.py` was empty, despite unrelated commits advancing HEAD.

- `katrain/web/kifu/name_batch.py:478`: the repeat check resolves the symbolic owner through the saved artifact; missing, non-integer, and non-positive resolutions fail. It never rewrites the signed candidate.
- `katrain/web/kifu/name_batch.py:483`: exemption still requires both owner kind and resolved numeric ID. Other owners with the same normalized spelling remain collisions, including equal IDs in different owner tables.
- `katrain/web/kifu/name_batch.py:795`: repeat validation retains signed-artifact, evidence-hash, and after-image checks before the collision scan at line 822. First apply still calls the scan without persisted resolutions at line 514.
- `tests/web_ui/test_kifu_name_transliteration_integration.py:146`: the added v2 raw-player regression checks the persisted mapping, exact `already_applied` result, unchanged signed bundle/evidence/artifact, and one surviving name row.

Fresh focused tests, using Python 3.13.11:

```sh
KATRAIN_DATABASE_URL=sqlite:///:memory: .venv/bin/python -m pytest -q tests/web_ui/test_kifu_name_transliteration_integration.py
# 23 passed in 1.34s

KATRAIN_DATABASE_URL=sqlite:///:memory: .venv/bin/python -m pytest -q tests/web_ui/test_kifu_name_batch.py -k 'v2 or selected_only_raw_event or conventional_name_evidence_matches_verified_row_and_collision_is_blocked or apply_is_atomic_audited_idempotent_and_preserves_sgf or undo_uses_after_image_compare_and_swap'
# 23 passed, 62 deselected in 2.41s
```

Independent Python stdin probes used the existing `catalog`, `_v2_wrap`, `refresh_bindings`, `_evidence`, and `apply_reviewed_selection` helpers with new `sqlite:///:memory:` engines. The v3 fixtures included a real reviewed duplicate-GN selection, yielding inventory format 3.

| Probe | Cases | Result |
| --- | ---: | --- |
| v2/v3 × raw_player/raw_event × foreign owner of the same kind or different kind with identical numeric ID | 8 | All passed |
| Saved reference absent, `0`, `True`, string `"1"`, or wrong positive ID `2` | 5 | All rejected without SQL writes |

Each of the eight matrix cases checked dry-run, apply, JSON-reloaded exact repeat, collision rejection, undo, and rejection of retry after undo. Exact repeat returned `already_applied`, the original batch ID, and `change_count=0`; a SQL listener observed no INSERT/UPDATE/DELETE or DDL. Complete relevant table images, signed candidates, source anchors, persisted evidence, and reviewed artifacts were unchanged by repeat. A subsequently inserted verified conventional name with uppercase-equivalent spelling triggered `cross-bundle normalized name collision`; that rejection also issued zero writes. Undo reverted exactly the three batch changes (owner, evidence, name), preserved the foreign owner/name/evidence and source album/selection images, and reported no skipped rows.

The invalid-reference probes verified persisted JSON types before retry. The boolean case initially needed an explicit table UPDATE because ORM dictionary equality treats `True` and `1` as equal and suppressed the intended fixture mutation. After correcting that probe setup, all five cases failed closed with zero writes and unchanged signed input.

No application code was edited by this review. Database writes were confined to disposable test fixtures; no real database, network service, or deployment was modified. No PostgreSQL execution was performed for this small, dialect-independent comparison change. The memo is left uncommitted for the coordinating agent.
