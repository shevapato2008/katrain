# Tutorial manual review and numbering check implementation plan

> **For agentic workers:** Use superpowers:subagent-driven-development. Keep implementation and review proportional to this bounded correction.

**Goal:** Let an administrator explicitly approve the current diagram with one action, independently check printed numbers, and save calibration drafts reliably.

**Architecture:** Reuse the existing workbench and verify-board CAS/audit/history endpoint. Add a pure numbering check for the current static diagram; it never creates replay data or grants manual approval. Preserve strict diagram/replay contracts and fix the demonstrated invalid draft at its origin.

**Tech Stack:** Existing React/TypeScript workbench, FastAPI/Pydantic provider, isolated Vitest/pytest fixtures, existing TEST Docker services.

## Chunk 1: One bounded user journey

### Task 1: Diagnose and implement

**Owners/files:**
- Console: `admin-console/ui/src/admin/tutorials/workbench/TutorialWorkbench.tsx`, adjacent focused numbering helper/tests, `WorkbenchContainer.tsx` only if needed.
- Console: `admin-console/ui/src/admin/api/client.ts` and its tests for useful 422 validation details.
- Provider: `katrain/web/tutorials/manual_review.py`, `katrain/web/admin/routers/tutorial_workbench.py` only as necessary, existing focused review/workbench tests.

- [x] Read current save/review contracts; reproduce the 422 with an intercepted draft or isolated fixture. Never submit user diagram approval or discard current user data for testing.
- [x] Add focused failing tests for one enabled manual confirmation, save-then-approve with the returned version, save failure/409 retaining drafts and preventing approval, and approval invalidation on later diagram edits.
- [x] Implement one button: `人工审核通过`; dirty state: `保存并确认审核`. Source-region confirmation and replay completeness are not prerequisites. Saved/candidate handling must save the shown content before approving it. Keep unknown-point evidence visible and apply the agreed Astra decision without a hidden dead end.
- [x] Implement `校验编号`: check the current static diagram's numeric labels, unique consecutive values (arbitrary positive start), known B/W occupancy, alternating color, one number valid. No numeric labels succeeds. Ignore letters/shapes. Return specific missing/duplicate/same-color/empty/unknown points. Never mutate the diagram or set replay/review status.
- [x] Keep real replay editing separately available through existing editor. A passing numbering check does not imply capture legality or complete replay.
- [x] Fix 422 root cause; display API validation details rather than generic status. Do not relax strict contracts or fabricate data to make incomplete playback pass.
- [x] Run focused console tests and build; focused isolated provider tests. No broad full-suite or media regeneration.

### Task 2: Independent review and TEST delivery

- [x] Astra Max checks spec compliance first, then code quality/CAS/error paths; resolve blocking findings and recheck.
- [ ] Commit only owned changes in existing feature worktrees. No production release/merge or unrelated files.
- [ ] Deploy only `katrain-admin` and `smartbox-admin-admin-console-1` on home-ubuntu. Assert TEST environment and existing DB/media identity; preserve env/ports/networks/mounts and before/after content fingerprints for figures 1030–1033.
- [ ] Verify existing `127.0.0.1:18012` authenticated page: one enabled review control on 1032, numbering check success on 1–10, no actual review write on behalf of user. Capture one representative page.
- [ ] Report exact test link, behavior, verification, versions and any remaining limitations.

## Astra Max plan decisions

- PASS: retain existing static digest format so unchanged approved diagrams/media remain valid. In `_save_payload`, any complete diagram difference (including replay-only change) clears `board_review`; narration-only changes retain it.
- Unknown-color points and unconfirmed source range do not disable explicit human approval; retain their evidence and warnings. Numeric checks fail if a numbered point has unknown color.
- Read-only real-page reproduction: checking sequence-complete with `initial: null, moves: []` sends an invalid complete replay and causes Pydantic 422. Preserve incomplete content as `needs_calibration`; keep server strict validation.
