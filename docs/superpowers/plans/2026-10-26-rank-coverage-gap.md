# Rank coverage gap implementation plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development. Preserve production state until reviewed publication.

**Goal:** Correct verifiable missing ranks in the current bounded public page and make the existing producer's official identity consumer work beyond the initial six subjects.

**Architecture:** Keep the two existing tables, frozen per-game decision and native rank-only CAS. Replace person whitelists with exact official subject parsing of already approved, owner-bound captures; unsupported/ambiguous evidence stays unknown. Allow an explicit bounded correction scope with exact source IDs, raw SGF and original manifest hashes; never dynamic current overlays or automatic full-history revisits.

**Tech Stack:** Existing Python/SQLAlchemy/PostgreSQL native v2 publication. No UI/schema/LLM/new HTTP crawler.

## Chunk 1: Evidence and implementation

- [x] Read current RK public page without navigation: 20 rows, source91635363/PROD178745 (於之莹) and91634842/178744 (芮乃伟) blank and without snapshots.
- [x] Query exact owner FKs: unique qualified entities; latest explicit source grades eight (2026-10-03) and nine (10-15). Existing consumer rejects their official capture subjects; prod_synced members do not re-enter original three-ID correction.
- [ ] Inventory already approved exact official captures and current-page <=40 owners using bounded indexed lookup; record qualified/unknown/conflict per owner and missing snapshot per game. Do not enumerate SGF filesystem.
- [ ] `scripts/kifu_rank_correction.py` + focused tests: explicit immutable JSON scope <=20 IDs, exact original SGF/manifest hashes and publication key; same old default scope remains compatible. All build/freeze/reuse/apply validation uses the supplied scope; reject extras, duplicate IDs, invalid hashes, drift, over-limit. No native validation relaxation.
- [ ] `katrain/web/kifu/player_ranks.py` + focused tests: supported official URL schemas and exact subject/name/heading or roster membership, independent approved-owner binding retained. Remove six-person hardcodes, not exact matching. Prove wrong subject/key/duplicate/third-party evidence remains rejected; grade still comes from bound raw SGF.
- [ ] Fresh Astra Max code/data review of final changes before deployment, no full baseline retest or unrelated UI edits.

## Chunk 2: Publish and finite data journey

- [ ] Fetch/merge latest develop, focused checks, feature push→develop push→Smartbox gitlink/main. Preserve unrelated WTs.
- [ ] Minimal changed-runtime overlay to TEST/PROD compatible receiver and TEST producer; no migration/UI rebuild/RK restart unless actual dependency requires it. Preserve mounts, budgets, GPU/DB/MinIO and one writer. Use existing maintenance lock process with fresh baseline and exact original-control restore.
- [ ] Freeze explicit eligible current-page members from existing original native packages; known raw fields/hash/IDs/source/old receipt/state preimages protected. Unknown evidence remains listed, not guessed. Pin a bounded scope, no full-window backfill.
- [ ] Apply TEST→full five-language/public verification→same frozen manifest PROD→full verification→exact replay. Preserve raw SGF/ranks, old package/IDs/progress and counts; no translation/import of existing games.
- [ ] Read current RK fetch only; no navigation or restart. Independently audit actual corrected IDs/API/coverage and limitations using fresh Astra Max, not prior approval.
- [ ] Deliver exact bounded coverage list, verified ranks/as-of/provenance, remaining unknown reasons, commits, actual versions and receipts. Do not claim all historical records repaired.
