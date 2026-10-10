# Literal Event Label Collision Implementation Plan

> **For agentic workers:** Use superpowers:subagent-driven-development. Keep this fix to the existing cross-bundle collision check and focused regression tests.

**Goal:** Allow an independently reviewed literal raw-event display label to share text with a formal event name without merging either identity.

**Architecture:** Existing raw-owner eligibility, signed research validation and applied-evidence qualification remain authoritative. Extend the existing raw-to-raw exception to the typed raw-event/formal-event pairing in both insertion orders; keep formal-to-formal and player collision checks.

**Tech Stack:** Existing Python name batch validators, SQLAlchemy and pytest. No schema or UI changes.

## Approved decision and reproduction

Independent Astra decision: `mixed-three-after617-prepared/reviewed-astra/raw-event-formal-label-collision-policy-decision.json`, SHA `13f1646669fd355dde025a5eb6a075172aebbf29a3429f910b197b121d48577e` in the current event preparation directory. Native TEST/PROD batch620 captures reproduce seven blocked labels across reviewed 新人王战、棋圣战、棋王赛; the source translations themselves passed independent review. Batch621 publishes only eight unblocked cells, retaining seven for this fix.

## Implementation and verification

Files: `katrain/web/kifu/name_batch.py` and the existing raw-event-title tests under `tests/web_ui/`.

- [ ] Add failing regression tests for a reviewed incoming literal raw label sharing a formal name, and a formal name sharing an already qualified literal raw label. Use existing real bundle/SQLite fixtures.
- [ ] In `_check_cross_bundle_collisions`, allow only an eligible approved literal raw-event owner against a formal event, or a formal event against an existing `eligible_literal_raw_name`. Reuse existing validated raw-to-raw semantics. An unreviewed/nonliteral raw name and player collisions remain blocked.
- [ ] Preserve `validate_bundle` and its raw-only format guard. The current seven cells only require cross-bundle insertion against existing formal names; allowing mixed raw/formal bundles would expand the accepted data format beyond this task.
- [ ] Run focused collision and raw-title tests, observe the new tests fail before implementation and pass afterward. Preserve negative controls; no full unrelated test suite.
- [ ] Request independent code review; fix material findings before commit/deploy.
- [ ] Build pinned native importer from the reviewed source diff. Native dry-run the remaining seven cells against current owner/name preimages, then root applies TEST and PROD with normal journal/physical checks.
- [ ] Deploy cloud readers only if the existing immutable qualified-read path requires the changed files. Verify real result names and report both coverage definitions; retain source evidence and original identities/SGFs.

No invented distinct-people tag, aliases, FK changes, renaming formal events, or new evidence framework is needed.

Scope refinement during implementation: the proposed mixed-bundle positive case required relaxing an additional format guard. Root excluded that optional mode under AGENTS.md proportionality; both insertion orders across existing bundles solve the observed failures with one production-file change.
