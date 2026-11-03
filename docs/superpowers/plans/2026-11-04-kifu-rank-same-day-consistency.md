# Align historical rank preparation with strict original-observation checks

> **For agentic workers:** Use superpowers:subagent-driven-development. Independent Astra max plan review (at most two rounds), then focused implementation and independent final code review. Do not weaken the existing first-write guard.

**Goal:** Refuse an inferred professional category when the same player's original ranks conflict on the target day, consistently during preparation and first publication.

**Evidence:** HOME original part 150 stopped before commit: album 15771 black is bare 7段 on 2024-11-03; 15776 white freezes historical_type 9p on the same day using a 2000 typed basis/professional maximum 6. Fresh read-only preparation exactly equals the frozen decision. Album/source/snapshot/basis beforeimages all match. `_qualification` permits the intermediate bare grade, while `_verify_incoming_rank_observations` correctly requires equality on the target day. HOME parts 1–149 committed 16,667 slots; PROD has no historical-repair writes. Both collectors remain in the recorded single-job maintenance pause.

## Minimal implementation

- Modify only `katrain/web/kifu/historical_ranks.py` and focused rank/native tests. Keep schema, snapshot version, source/provenance and frozen legacy receipt dispatch unchanged. This enforces the existing policy; no policy or signature shortcut for old manifests.
- In `_qualification`, treat a same-target-day original bare numeric mismatch as incompatible, even when it lies between the earlier professional maximum and the target source grade. Retain compatible earlier bare progression, same-day equal grades, future exclusion, and typed amateur boundaries.
- Ensure original observations in the supplied incoming targets, which may not exist in PG yet, receive the same disqualifying checks during preparation as during first write. Reuse one pure compatibility decision if that avoids divergent predicates. Incoming originals can disqualify but cannot become new positive historical evidence; inferred snapshots cannot propagate. A conflict preserves the explicit source grade/system (or unknown), records an existing honest refusal where possible, and does not drop the game.
- RED→GREEN cases: the exact older 6p / target-day bare 7 / target-day bare 9 shape for stored and new incoming records; reverse input order; compatible earlier 7 then later 9; same-day equal grades; missing rank with conflicting original; future-only contradiction. Verify prepare results successfully pass the unchanged strict first-write check when persisted, with no forged proof.
- Run focused historical rank, repair, freeze/native publication tests. Independent Astra final review must approve before deploying this change.

## Data and release

- The resolver bytes change, so old code-bound manifests must not be edited or relabelled. After immutable deployment, create fresh RR read-only audit manifests for both actual DBs with the same original matched-at timestamp. Ordinary repair deliberately skips existing v3; do not claim its census revalidates them or relax `_replaceable`.
- Separately enumerate exactly the committed HOME slots from the 149 original receipts/journals, verify their current exact afterimages, and read-only recompute each decision from original sources/cohorts using the new resolver and original timestamp. Record semantic/refusal differences and exact slots. If none differ, preserve the accepted rows. If any differ, stop further data writes and first propose/review a finite correction bound to those exact historical-repair journals, beforeimages and new decisions; do not add a generic v3 replacement mechanism pre-emptively or undo unrelated accepted work. This conditional correction remains required work if actual differences exist.
- Review the fresh aggregate decisions and changed same-day cases independently. Use existing finite apply/receipt/CAS operator, with the new code/database/index pins and fresh backup. No automatic offsets, skipped failed parts, gate clearing, SGF deletion or source rewriting.
- Publish feature→develop→parent gitlink; preserve concurrent UI work, full TEST role configuration and PROD 8 GiB/12 GiB limits. Reuse verified static bytes only if UI inputs are identical to the corresponding exact export. Complete server/RK deployment and real API/hourly acceptance; record RK connectivity honestly.
