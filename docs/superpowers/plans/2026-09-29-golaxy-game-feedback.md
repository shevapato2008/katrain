# Golaxy game feedback implementation plan

**Goal:** Complete the five approved fixes for recognition feedback, game controls, Golaxy coordinates, judge feedback, and unobstructed alerts, then update Git and deploy to RK3562.

**Architecture:** Keep `GamePage` and the shared vision worker as the source of game and camera state. Golaxy wire coordinates are converted only at the adapter boundary. The game page renders one right-rail recovery surface and passes point markers to `Board`; the physical-play orchestrator owns all attention LEDs. The judge endpoint remains authoritative for finishing and recording a game.

**Tech Stack:** FastAPI/Python, React/TypeScript, MUI, RK3562 LED and vision services.

**Approved artifact:** The revised `docs/previews/golaxy-game-feedback-design.html` at 1024×600 uses a compact highlighted card over a dimmed, visible, disabled right rail. The user approved this revision before frontend integration.

---

## Slice 1: Coordinate and judge contract

- [x] Add a failing golden test for core row 0 = bottom and Golaxy wire row 0 = top; fix `katrain/web/platforms/golaxy/coords.py` and adapter decode expectations.
- [x] Add failing endpoint tests for `judge` winner `U` and explicit `B/W/D`, including a position change during the request; return undecided coordinates and a terminal state only for a valid current-position verdict.
- [x] Reuse the existing game-result commit and platform-engine ledger path; avoid a frontend-only terminal flag.

## Slice 2: Shared recognition recovery

- [x] Reproduce repeated identical `illegal_change` events after dismissing the mismatch dialog.
- [x] Use the existing `visionDenyStone` path for a single extra false stone. Keep missing/colour errors truthful; suppress repeat prompts for the same unresolved event until the observed state changes.
- [x] Confirm RK3562 launches with `--vision-reference-check on` and that both local and platform games use the same worker.

## Slice 3: Visual feedback and hardware

- [x] Connect shared recovery state and Golaxy undecided points to `Board` circles and the approved right-rail panel.
- [x] Extend the physical-play orchestrator's existing blink path with violet attention points, one owner at a time, motion/timeout cleanup, and vision lamp masking. Drive it from server-owned mismatch and judge data.
- [x] Reuse the voice hook for one prompt per distinct issue; stop prompts on recovery or a new game.
- [x] Audit all Go game pages for the obsolete `重新识别` action; remove it where present. Keep `重新标定` and `重新分析`, which do different jobs.

## Slice 4: Verification and release

- [x] Run focused Python and frontend tests for all five points, then the relevant build and 1024×600 browser preview.
- [ ] Check the branch diff and perform the requested Git updates only after the five changes pass.
- [ ] Update `smartbox-software/vendor/katrain`, deploy to RK3562, and verify service/UI health without playing a game.
- [ ] Report items 1–5 individually with code, automated/device checks, commit IDs, and any limits before the user's board test.
