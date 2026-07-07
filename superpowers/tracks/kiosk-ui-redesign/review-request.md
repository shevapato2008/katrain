# Review Request — 智星盒 StellaBox Kiosk UI 重开发 Implementation Plan

**You are reviewing an implementation plan, not code that has been written yet.** The plan is `superpowers/tracks/kiosk-ui-redesign/plan.md` (≈2000 lines, 51 tasks, Phases A→D). Nothing in it has been executed. Your job is to find everything that will go wrong when a competent-but-context-free engineer executes it task-by-task, and to challenge the decisions that shaped it.

Please be adversarial and specific. Vague praise is useless; a concrete "Task B1.3 assumes `player_to_move` is populated during AI turns but the WS sends it only after the move resolves, so state A will flicker" is gold.

---

## 1. What this is

KaTrain is a Go/Baduk app with a **Kivy desktop UI** and a **web UI** (FastAPI + React/TS/Vite). The web UI ships **two builds from one codebase**: a full `web/static/` and a stripped **kiosk** `web/static-kiosk-2d/` for 7″ SBC touch terminals (no three.js / no galaxy 3D).

This plan **rebuilds the kiosk web UI** from its current web-derived shell into a locked-in visual design called **"direction ③ Board Console"**: a **landscape-only 1024×600** shell = top **Header** + bottom **Dock** + a left **SmartBoardConsole** (only on the `/kiosk/play` hub). It reskins all 8 kiosk modules to a cold "slate" design system, **down-ports** galaxy's Research analysis experience into kiosk territory, and leaves **stubs** for an LED/camera physical-play track that lives in a separate repo.

The **visual design is already locked and approved** (see `design.md`) — do **not** re-litigate the aesthetics, the direction choice, landscape-only, or the module IA. Review the **implementation plan** that turns that design into code.

## 2. How the plan was produced (so you know where to distrust it)

The plan was authored by AI agents that **read the real repo** (exact files, props, line numbers, `data-testid`s, hooks, APIs), cross-checked by adversarial critic agents, then drafted in a strict "writing-plans" task format against a fixed set of shared-interface contracts. Consequences for your review:

- **Line numbers may have drifted** or be slightly off — treat cited line ranges as strong hints, not gospel. Flag any that look wrong, but the real risk is logic, not ±3 lines.
- **Cross-file assumptions are the main hallucination risk** — a task claiming "galaxy `ResearchAnalysisPanel` is self-contained (only imports `ResearchToolbar` + `useTranslation`)" should be verified against the actual file.
- The plan is deliberately **grounded, not creative** — if it invents an API, prop, or file that doesn't exist, that's a defect worth flagging loudly.

## 3. Read these first, in order

| # | File | What it is |
|---|---|---|
| 1 | `superpowers/tracks/kiosk-ui-redesign/plan.md` | **The plan under review.** |
| 2 | `superpowers/tracks/kiosk-ui-redesign/design.md` | The locked visual spec (§4 system, §5 per-module). The plan cites its §-numbers. |
| 3 | `CLAUDE.md` → section "SBC 构建边界契约" | The **dual-build boundary contract** the plan must never violate. |
| 4 | `katrain/web/ui/src/kiosk/KioskApp.tsx` | The kiosk route tree + provider order — sanity-check the plan's routing claims. |
| 5 | `katrain/web/ui/eslint.config.js`, `vite.config.ts`, `scripts/verify-kiosk.sh` | The enforced build/boundary gates the plan's verification steps rely on. |
| 6 | `superpowers/tracks/kiosk-ui-redesign/HANDOFF.md` | Artifact→code mapping (context, not required). |
| 7 | `superpowers/tracks/kiosk-ui-redesign/artifacts/*.html` | Self-contained visual mockups each reskin task must match. |

The former design-phase activity log is preserved at `plan-design-phase.md` (historical, not needed for review).

## 4. Hard constraints the plan MUST satisfy (verify it does)

1. **SBC dual-build.** Two outputs: `npm run build` (full) and `npm run build:kiosk-2d` (kiosk, chains `verify:kiosk-2d` which greps the kiosk dist for `three`/`@react-three`/`/galaxy/`/non-board `/api/v1/live` and fails on any hit). `src/kiosk/**` may **not** import `src/galaxy/**`, `components/Board3D/**`, or `pages/VideoRecorderPage*` (eslint `no-restricted-imports`).
2. **Shared territory is consume-only.** Shared = `components/` (except `Board3D/`), `hooks/`, `context/`, `api.ts` + `api/`, `utils/`, `types/`, `src/theme.ts`, `i18n.ts`. The plan claims the **only** shared-territory *edit* in the entire track is `katrain/web/ui/package.json` (Task A1, adding two fonts). **Verify this claim** — any other shared edit forces the full galaxy build + risks galaxy regressions, and the plan must have flagged it as "Gate S". `src/kiosk/theme.ts` is kiosk-only (not the shared `src/theme.ts`).
3. **No emoji anywhere in kiosk.** SBC ships no emoji font → 🎉/⚔️ render as tofu. Everything must be `@mui/icons-material` SVG. Two live tofu bugs are fixed in Task B2.1.
4. **Landscape only** (1024×600); portrait is deleted (Task A3).
5. **Down-ported galaxy code must not import galaxy** — Phase C re-implements galaxy research components under `kiosk/`; verify no task leaves a `galaxy/**` import (eslint would fail, but catching it in review is cheaper).

## 5. Shared interface contracts (fixed names — check tasks use them consistently)

- **Theme** (`src/kiosk/theme.ts`, A2): slate palette; `warning.main = #e0a24a` is **the single amber token** — modules must consume `theme.warning.main`, never re-hardcode amber.
- **ImmersiveContext** (`src/kiosk/context/ImmersiveContext.tsx`, A6): `useImmersive(): { immersive; setImmersive(v) }` + `<ImmersiveProvider>` mounted in `KioskLayout`. This is the mechanism that hides Dock/console for the tsumego solve page (A11) and Research L2 (C1.6) — an in-component state transition a route-allowlist can't do. **Scrutinize whether this actually works** given the provider is mounted inside `KioskLayout` and the immersive pages render as its `<Outlet/>` children.
- **LED colors** (`src/kiosk/constants/ledColors.ts`, A4): `LedIntent` / `LED_HEX` / `LED_LABEL` — 黑`#ff3b30`/白`#34c759`/提子`#2f6fff`/提示`#ffffff`. Consumed by 摆谱 (B7) + physical stub (D1).
- **Active-session store** (`src/kiosk/utils/activeSession.ts`, A5): `readActiveSession/writeActiveSession/clearActiveSession` — consumed by 对弈「继续上一局」(B1) + 死活「继续练习」(B2).
- **Physical-tsumego** (D1): indirection `usePhysicalTsumego.ts` re-exports a stub; interface `PhysicalTsumegoPhase` / `UsePhysicalTsumego`.
- **Settings language**: 中→`'cn'`, 英→`'en'` via `useSettings().setLanguage` (SettingsContext already wires i18n).

## 6. Phase & dependency structure

```
Phase A (foundation, land A1→A13):
  A1 fonts(package.json,Gate S) · A2 theme+amber+hex-sweep(single owner) · A3 isPortrait removal(ATOMIC: 9 pages+14 test mocks)
  A4 ledColors · A5 activeSession · A6 ImmersiveContext · A7 Header · A8 Dock · A9 SmartBoardConsole
  A10 KioskLayout rewrite + navTabs icons + delete StatusBar/NavigationRail/TopTabBar · A11 immersive wiring · A12 LoginPage+logout · A13 geometry reskin
Phase B (independent module reskins): B1 对弈 · B2 死活(+toggle seam) · B3 棋谱 · B4 直播 · B5 教程 · B6 设置 · B7 摆谱
Phase C (research down-port, new-build): C1.1–C1.8 (+ post-C kifu retarget)
Phase D (死活 physical 5-state stub): D1.1–D1.3
```

## 7. Decisions I made — please challenge these

These were judgment calls (some from an internal adversarial critique). Push back if any is wrong:

1. **`isPortrait` removal is ONE atomic task (A3)** spanning 9 pages + 14 test mocks, rather than each module dropping its own branch. Rationale: removing the field from `OrientationContext` reddens the TS build until every consumer is fixed. **Is atomic-A3 right, or does it make A3 an un-reviewable mega-commit?**
2. **`ImmersiveContext` flag** to hide Dock/console for in-component immersive states (tsumego solve, Research L2), instead of moving those routes to fullscreen (outside `KioskLayout`) like the game pages. **Is the flag cleaner, or would fullscreen routes be more robust?**
3. **SmartBoardConsole ships with a static/empty 19×19 preview** — there is no "current recognized board" data feed yet. **Acceptable stub, or should the console be deferred until a feed exists?**
4. **Header carries a compact global hardware-status cluster** (engine/camera/calibration dots) so browse pages don't lose all hardware visibility after `StatusBar` deletion. **Right call, or clutter?**
5. **摆谱 (Baipu) is a Phase-B reskin, not a Phase-D physical stub** — it's already fully built with hardware fall-throughs. **Agree?**
6. **棋谱「在研究中打开」keeps its existing `GamePage` target in Phase B**; retargeting to the new Research report is an isolated **post-Phase-C** task (C1.8). **Correct sequencing, or should 棋谱 wait for C?**
7. **`kiosk/theme.ts` and `navTabs.tsx` each have a single owner task** (A2, A10) to avoid divergent concurrent edits. **Over-cautious?**
8. **Physical-tsumego stub behind an indirection file** so the external physical track swaps one re-export line. Note: the plan (D1.1) discovered the sibling worktree `../katrain-kiosk-physical-tsumego` is **already fully built but its hook shape ≠ the stub contract**, so the swap is NOT drop-in — D1.1 records this as a sign-off dependency. **Is stub-first still the right move, or should Phase D adopt the real hook's actual signature now?**

## 8. Known risks / places to dig hardest

- **`ImmersiveContext` provider scope** (see §5) — does `setImmersive(true)` from an `<Outlet/>` child actually reach the `KioskLayout`-mounted provider and hide the Dock, or is there a provider-boundary bug?
- **Research down-port fidelity (Phase C, heaviest).** Verify against the real galaxy files: is `ResearchAnalysisPanel` really self-contained? Are `useResearchSession`/`Board.tsx`/`LiveBoard` truly reusable **as-is** with no prop additions (any prop add = shared edit = galaxy risk)? Does re-calling `analysisScan` actually *resume* incrementally (the failure/retry state D depends on it) or restart from 0?
- **State A (AI思考中) in 对弈 (B1)** is *derived* (`player_to_move===AI && !end_result`) because there's no backend "thinking" signal, and it overlaps `PhysicalPlayStatusChip`'s `确认中` (move_pending). Is the arbitration the plan specifies actually unambiguous, or will both fire?
- **`PhysicalBoardGuard requireRecognition` pass-through.** 棋谱-open, 死活-solve, and research-session routes are guarded by `requireRecognition`. On a camera kiosk without recognition, do these land on the guard instead of the content? The plan adds a `phase==='disabled'` pass-through test (B2.5) — is that sufficient, and does it match the guard's real logic?
- **i18n coverage (B6).** Wiring 英→`'en'` may expose that many kiosk strings are hardcoded 中文 (esp. `GeometryCalibrationWorkspace`). The plan scopes B6 to the SettingsPage wiring only and flags broader i18n-wrapping as follow-up. Is that honest, or does "language 中/英 actually works" require more?
- **Panel width refits (Phase C).** Down-ported galaxy panels were 500px rails with a hardcoded 420×140 trend SVG; kiosk rails are 340/298/404px. The plan gives specific refit values — sanity-check they fit 1024×600 without overflow.
- **Test-mock sweep (A3).** 14 test files mock `{ isPortrait: false }`. If the plan's file list is incomplete, the build stays red. Cross-check by grepping `isPortrait` across `src/kiosk`.
- **Board-loss surface consolidation (B1.4).** GamePage has 3 overlapping desync surfaces (PoseLostBanner/RecalibrationModal, VisionSyncOverlay board-lost dialog, PhysicalSyncEscalationDialog). Does the plan actually consolidate them to one-visible-at-a-time, or just say so?

## 9. Explicitly OUT of scope (don't flag these as gaps)

- **Code-level brand rename** 弈航/BoardNavi → 智星盒/StellaBox (galaxy + shared + i18n + tests + logo image + legal ToS) — a separate track; the plan only puts "智星盒 StellaBox" text in the Header beside the old logo image.
- **Geometry `no-LED-outer-frame-PRIMARY` rework** (`project_geometry_recalib_arch`) — A13 only adds advisory copy + honors the existing never-auto-LED rule.
- **Physical-play *backend* orchestration** (LED/camera/phase-machine wiring) — lives in the `katrain-kiosk-physical-tsumego` repo; this plan ships visual stubs only.
- **Portrait**, **9×9/13×13 boards**, **personal cloud SGF save** (`UserGamesAPI`) — all deliberately dropped.
- Aesthetics / direction ③ / module IA — locked in `design.md`.

## 10. What I want back

Please produce, ranked most-severe first:

1. **Correctness defects** — a task that will produce a wrong result, a broken build, or a runtime failure. Give the task ID, the specific wrong assumption, and the concrete failure scenario (inputs → wrong output).
2. **Sequencing/dependency errors** — a task that depends on something built later, an intermediate red-build window, or a shared-territory edit not flagged as Gate S.
3. **Coverage gaps** — any `design.md §5` state/screen (loading/empty/error/physical) or `KioskApp.tsx` route with no owning task.
4. **Boundary violations** — any task that would import galaxy from kiosk, edit shared territory unannounced, introduce three.js into the kiosk bundle, or break `verify-kiosk.sh`.
5. **Over/under-specification** — placeholder steps, fabricated APIs/props/files, or tasks too coarse to review independently.
6. **Verdicts on the §7 decisions** and the §8 risks — agree/disagree with reasoning.

A short overall verdict (ship / ship-with-fixes / needs-rework) at the top would help. Where you assert a defect, cite the exact `plan.md` task ID and, where possible, the real repo file that contradicts it.
