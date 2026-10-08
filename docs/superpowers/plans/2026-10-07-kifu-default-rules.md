# Professional Kifu Default Rules Implementation Plan

> **For agentic workers:** Use superpowers:subagent-driven-development. The user explicitly authorized a default rule when RU is absent and previously authorized deployment and home-ubuntu reruns.

**Goal:** Analyze games with missing RU using a transparent komi-based default, then restore their reports in both environments.

**Architecture:** Extend the existing resolver and immutable parameter snapshot. Explicit SGF and reviewed evidence keep precedence. Missing RU with explicit KM 6.5 defaults to Japanese; KM 7.5 defaults to Chinese. Other/missing komi stays unresolved. Default snapshots are usable but not verified assertions about tournament rules; no rewriting SGF, relabeling old results, new tables, or personal/live behavior changes.

**Tech Stack:** Existing Python resolver, FastAPI, PostgreSQL, React Galaxy/kiosk, isolated dual-GPU worker and strict batch transfer.

## Chunk 1: Policy and report contract

- [x] Add regression tests for default 6.5/7.5, precedence, unknown komi, immutable identities, API/list and worker/transfer acceptance.
- [x] In `katrain/cron/kifu_parameters.py`, add snapshot version 3 with `verified=false`, provenance `source=komi_default`, and versioned policy `komi-default-v1`. Validate by recomputing the exact snapshot; reject legacy snapshots and tampering.
- [x] In `katrain/web/api/v1/endpoints/kifu.py`, return `parameters_valid` independently of `parameters_verified`. Valid default reports expose their new rows; old unbound reports remain unavailable.
- [x] Update `types/kifu.ts`, `features/kifu/useKifuAnalysis.ts`, status/rule helpers, Galaxy metadata and kiosk metadata. Valid defaults render charts and show 日本规则（默认） / 中国规则（默认） and a source explanation in existing details. Preserve layout and verified event names.
- [x] Run focused Python/frontend regressions, typecheck, standard and kiosk2D build. Independent Astra max review.
- [x] Check one representative real default report preview per device class after result import.

## Chunk 2: Deployment and bounded rerun

- [x] Deploy only affected backend modules and built frontend to home-ubuntu/ucloud-v100, preserving concurrent changes and online engines.
- [x] Freeze previously excluded, supported games (24160, 24161, 24164–24169, 24171) after confirming their original SGF/komi/identities in both DBs. Keep KM 0 / missing KM unresolved.
- [x] Run on home-ubuntu using existing two-GPU isolated worker workflow, model s11003M-d5973M-7gres, 2000 visits. Preserve old reports until new complete results pass validation; back up before replacing jobs/moves.
- [x] Import new complete results into test and production, verify matching hashes, raw SGF unchanged, truthful default labels and working latest-report CTA. Record results and commit on the existing feature worktree.
