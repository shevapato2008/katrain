# Historical rank foundation independent review

Date: 2026-11-03. Scope: Task 1 only, base `0828f55a7`. Initial reviewed HEAD `7c73b3cb09e511c7feecd10c3d12c69dd8dc542c`; follow-up reviewed HEAD `b29a0c38f01b5fb0a613648df070f1d9b1cc77a5`.

**Current spec verdict: APPROVED. Current quality verdict: APPROVED for the Task 1 code.** Both initial integrity findings are fixed; no remaining code blocker was found in this focused follow-up. PostgreSQL execution is separately owned by the controller and is not claimed as independently run here. Missing native/API/repair integrations belong to later tasks and are not counted as omissions. This does not approve production changes or the unfinished integration/release.

## Follow-up verification

The spec pass preceded the quality pass: checked the unknown/no-grade invariant, the new allowlisted and hashed `incompatible_bare_ranks` material qualification, first-apply recomputation, compatible-grade/future stability, and the unchanged portable bindings/limits. Then inspected the implementation and new regression cases for unintended behavior or additional data-integrity gaps. No additional blocker was found.

Independently reran both original counterexamples through public APIs at the follow-up HEAD. The rehashed invented unknown `9p` now raises `unknown rank decision invalid` at all three boundaries: validator, initial verifier, and binder. Inserting the newer original CWI `7d` after freezing an `8p` historical-prior decision now produces unknown with `professional_grade_decrease`; applying the old frozen result raises `rank initial qualification/cohort changed`. The additional `9d` incompatibility, same-grade compatibility, and future-only contradiction cases are included in the focused suite.

Fresh planned verification: **72 passed, 1 skipped in 2.07s** using `PYTHONPATH=$PWD CI=true /Users/fan/Repositories/katrain-kiosk-debug/.venv/bin/python -m pytest -q tests/web_ui/test_kifu_historical_ranks.py tests/web_ui/test_kifu_source_rank_normalization.py`. The skipped case is the new opt-in PostgreSQL test; no DSN was read or printed by this reviewer. Its isolated-schema design and READ COMMITTED/timeout assertions were inspected, with execution left to the controller as assigned. Only this review document was changed by the reviewer.

The following initial findings and reproductions are retained as history; their acceptance observations refer to the initial HEAD.

Reviewed the approved plan and Astra R2 context, both new files, and the reused source/identity/journal contracts. Independently ran the planned focused suite: **66 passed in 1.81s** (`test_kifu_historical_ranks.py` and `test_kifu_source_rank_normalization.py`). Also ran the two isolated SQLite reproductions below through the public interfaces. No product code, configuration, production data, plan checkboxes, or deployment was changed. No filesystem access/listing/traversal under `data/kifu-album/` occurred. PostgreSQL isolation/lock/timeout execution remains for the controller's separate disposable-schema check; this review makes no PostgreSQL execution claim.

## Resolved P1 — Unknown snapshots can carry an invented canonical professional grade

Location: `katrain/web/kifu/historical_ranks.py:628–644`, `754–757`; first-apply path `805–809`.

The validator checks that a **null** rank has unknown origin, but does not enforce the reverse constraint. In the unknown-origin branch, it only requires that the raw source has no parseable grade. A valid unknown snapshot with an empty raw rank can therefore be changed to `rank_value=9`, `rank_system="professional_dan"`, `display_rank="9p"`, then rehashed. `validate_rank_decision`, `verify_initial_rank_decisions`, and `bind_rank_decision` all accept it, with an empty basis. The first-apply path intentionally does not resolve unknown decisions again, so it cannot catch this violation. This breaks the explicit requirement that unknown contains no invented numeric grade/system and makes the portable validation boundary accept unsupported canonical data.

Exact reproduction, using the existing test helpers and an in-memory database:

```python
entry = game(conn, 2, "1968-08-01", "", family="CWI")
decision = resolve(conn, entry)  # unknown / no_prior_original / no basis
decision.update(rank_value=9, rank_system="professional_dan", display_rank="9p")
decision["content_sha256"] = snapshot_digest(decision)
validate_rank_decision(decision)                    # accepted
verify_initial_rank_decisions(conn, [entry], [decision])  # accepted
bind_rank_decision(conn, entry, decision)           # accepted, basis=[]
```

Minimum fix: explicitly require unknown origin to have `rank_value is None`, `rank_system is None`, empty display, a nonempty refusal, and no basis. Add a regression that recomputes the valid content hash after inserting the unsupported grade and proves the public validator and first-apply boundary reject it. This is a semantic validation test, not merely a stale-hash test.

## Resolved P2 — A nearer incompatible bare original observation is invisible to qualification and fresh recheck

Location: `katrain/web/kifu/historical_ranks.py:350–380`, `467`, `815–817`.

`latest_day` is selected only from typed observations. A newer original bare dan record on a different day consequently contributes neither its known numeric grade nor a conflict/decrease guard to the frozen material qualification. For one exact owner, a 1960 `8p`, a 1967 CWI `7d` (source-aware unspecified seven dan), and an empty 1968 target produce a 1968 canonical `8p`. Yet resolving the 1967 record itself correctly refuses professional refinement with `professional_grade_decrease`. The known nearer numeric contradiction disappears solely because that record is an intermediate observation rather than the target.

This also bypasses first-apply freshness: freeze the 1968 result before inserting the 1967 original, insert that record, then verify the frozen decision. The fresh qualification is byte-for-byte unchanged and verification accepts it. The same issue applies when the conflicting record already exists only on the receiving database. The plan requires incompatible original observations and professional decreases to block inference and requires the material qualification to capture disqualifying changes.

Independently executed reproduction:

```python
game(conn, 1, "1960-01-01", "8p")
entry = game(conn, 2, "1968-08-01", "", family="CWI")
frozen = resolve(conn, entry)                       # historical_prior, 8p
nearer = game(conn, 3, "1967-01-01", "7d", family="CWI")
resolve(conn, nearer)["refusal_reason"]              # professional_grade_decrease
fresh = resolve(conn, entry)                       # still historical_prior, 8p
assert fresh["qualification"] == frozen["qualification"]
verify_initial_rank_decisions(conn, [entry], [frozen])  # accepted
```

Minimum fix: include relevant original bare numeric observations in qualification safety checks, especially observations newer than the selected typed basis. A nearer incompatible numeric observation must produce an explicit refusal rather than allow an older typed grade to bypass it. Preserve the raw numeric grade when the bare record itself is the target; do not turn inferred snapshots into evidence. Cover both prepare-time presence and prepare-to-apply insertion with a focused regression. Keep compatible same-grade p/bare observations accepted.

## Other contract observations

The implementation has strict portable field allowlists and hashes, exact root PB/PW/BR/WR/DT and source SHA validation, source-aware parsing, no current-profile/snapshot evidence lookup, complete scalar conflict checks before evidence-body loading, explicit scalar/body ceilings, and separate exact binding versus initial qualification APIs. The retained-basis helper validates applied batch/journal/binding afterimages and includes standalone artifacts. These are useful foundations, but the passing existing cases do not cover the two counterexamples above.

The nonblocking incoming-ID documentation observation is addressed: the follow-up docstring explicitly requires `album.id=None` and source-link `album_id=None` before insertion. Downstream adapters should preserve that representation. The resolver currently uses already-stored originals only, as its docstring states; same-incoming-batch evidence support must not be assumed by downstream callers.

The two fixes and focused counterexample regressions have been verified. Obtain the separately assigned PostgreSQL execution evidence before treating the foundation's database validation as complete. No additional full-suite or UI campaign is requested for this foundation.
