# OGS Kiosk Course Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the approved OGS course preview into a database-backed, usable Kiosk tutorial, preserving the source lesson order and each exercise's original answer mode.

**Architecture:** Reuse the imported `tutorial_ogs_courses` and `tutorial_ogs_steps` tables. Add a small public read-only course/step API by the known course slug, forward those reads through the board-mode proxy, and build the Kiosk course screens against that contract. Keep the existing book library reachable as a separate path. Board puzzles use the imported solution tree and Go move rules; choices appear only for source `choice` exercises, while pass, dead-stone removal, and finish get their own controls.

**Tech Stack:** FastAPI, SQLAlchemy, React 19, TypeScript, Vite, Vitest, pytest, Playwright. No new dependency and no bundled production content fixture.

**Approved visual reference:** `/Users/fan/Repositories/katrain-kiosk-ui-redesign/docs/design/kiosk-current-based-redesign-2026-10-14.html#courses`, with the chapter, board puzzle, and choice states in `docs/previews/ogs-course-design-2026-10-23/` at 1024×600. The preview JS contains simplified sample logic only; do not copy its sample data or one-move checker into production.

**Content boundary:** The imported OGS book currently exists in TEST. This plan implements runtime reads and interactions without publishing the content or exposing admin endpoints. Production import and license authorization are separate release decisions. Missing course/tables must yield an honest unavailable state, never fake lessons or claim progress.

**Acceptance criteria:**

- Kiosk course home, chapter/lesson list, and exercise screens match the approved design at 1024×600 and work with the existing database import.
- Every source exercise kind has the right interaction: `puzzle` and `remove` on board, `choice` on right, `pass` and `finish` as explicit actions. A wrong response allows retry; a correct response enables the next step. Multi-ply puzzles follow the source solution tree and show automatic opponent moves and captures.
- A lesson can be entered from its chapter, navigated step by step, and returned to the chapter. Loading, missing content, and network failure states are honest with retry where useful. Existing non-OGS tutorial book access remains available.
- The exercise page includes the shared `实体盘` action. For 19-line board puzzles it follows the existing tsumego hardware readiness, clear/setup, confirmed-move, response/capture and success path; for 9/13-line and non-board-answer steps it remains visibly unavailable with an on-screen reason. Screen interaction remains available.
- No OGS fixture data is shipped in production JS, and no admin session or write endpoint is required for public course reading.

## Chunk 1: Data contract and read-only delivery

### Task 1: Public OGS course API

**Files:**
- Modify: `katrain/web/tutorials/ogs_course.py`
- Modify: `katrain/web/api/v1/endpoints/tutorials.py`
- Test: `tests/web_ui/test_ogs_public_course.py` (new)

- [x] Write focused API tests using an in-memory imported sample: localized course index, localized step, correct lesson/page order, 404 on absent OGS course/page, 503 on missing OGS tables, no admin auth required, and no `raw_source` or entire translation map in the public response. Add a real app-startup check that OGS tables remain absent before and after `init_db()`, then public reads return 503.
- [x] Run `pytest -q tests/web_ui/test_ogs_public_course.py` and confirm the new tests fail for missing routes.
- [x] Add a read-only lookup by `SLUG` from `ogs_import.py`, reusing `course_index`/`step_output` where appropriate. Expose `GET /api/v1/tutorials/ogs-course?lang=zh-cn` and `GET /api/v1/tutorials/ogs-course/steps/{page}?lang=zh-cn`. Return only current-language chapter/lesson text plus counts/index metadata; step response includes the exercise tree, board state, viewport, annotations, current-language instruction, and source identity. Use a **separate public response projector** so the existing admin response retains `raw_source`. Import `ogs_course`/`ogs_models` only inside request handlers, after startup `init_db()`; verify no OGS table gets registered in time for startup `create_all()`. Guard unavailable tables as 503 without creating them. Validate the language against the imported catalog.
- [x] Run `pytest -q tests/web_ui/test_ogs_public_course.py tests/web_ui/test_admin_ogs_course.py tests/web_ui/test_tutorial_db_api.py` and confirm pass.
- [x] Commit only these task files with a short present-tense message.

### Task 2: Board proxy and TypeScript contract

**Files:**
- Modify: `katrain/web/core/remote_client.py`
- Modify: `katrain/web/api/v1/endpoints/board.py`
- Modify: `katrain/web/ui/src/api/tutorialApi.ts`
- Create: `katrain/web/ui/src/types/ogsCourse.ts`
- Test: `tests/web_ui/test_board_tutorial_proxy.py`
- Test: `katrain/web/ui/src/api/__tests__/tutorialReadonly.guard.test.ts`

- [x] Add focused tests for board proxy success and upstream 404/503/connection failure, plus read-only API export/URL selection on the frontend.
- [x] Run those tests and confirm the new assertions fail before implementation.
- [x] Forward the two public OGS GET routes through `RemoteAPIClient` and board proxy; keep all calls `auth=False`. Add typed `getOgsCourse` and `getOgsStep` to `TutorialReadAPI`. No OGS write route.
- [x] Run the focused tests, then commit only task files.

## Chunk 2: Source-faithful exercise interaction

### Task 3: Pure exercise state machine and board rules

**Files:**
- Create: `katrain/web/ui/src/kiosk/tutorial/ogsExercise.ts`
- Test: `katrain/web/ui/src/kiosk/tutorial/ogsExercise.test.ts`

- [x] Write representative tests using small imported payload fragments: all 5 kinds, multiple accepted first moves, wrong branch/retry, multi-ply automatic opponent continuation, capture/removal, occupied/out-of-bounds, suicide and immediate-ko rejection, and terminal correct handling. Invalid moves do not consume the turn or count as wrong. Test a correct terminal after an automatic opponent response using TEST `bl1-calculate-ladder:1` (fixture only in test), without bundling the export. For removal, selecting any stone toggles its whole connected group and succeeds only when the selected group points equal `remove_targets`; retry fully resets state.
- [x] Run `npm test -- --run src/kiosk/tutorial/ogsExercise.test.ts` and confirm failures.
- [x] Implement a pure state transition module: answer mode derives **only** from source `exercise.kind`; Go board updates use the source tree, alternating player and automatic opponent nodes, with captures, suicide/ko validation, and no occupied move. Inspect `correct`/`wrong` on both player and automatic response nodes; the root `wrong` flag does not fail the untouched puzzle. Do not decide answer correctness by arbitrary first points or offer answer choices for `puzzle`. A retry restores initial board, tree cursor and removal selection.
- [x] Run focused tests, then commit only task files.

## Chunk 3: Kiosk user journey

### Task 4: Course pages and visual system

**Files:**
- Create: `katrain/web/ui/src/kiosk/pages/OgsCourseHomePage.tsx`
- Create: `katrain/web/ui/src/kiosk/pages/OgsCourseChapterPage.tsx`
- Create: `katrain/web/ui/src/kiosk/pages/OgsCourseExercisePage.tsx`
- Create: `katrain/web/ui/src/kiosk/tutorial/OgsCourseBoard.tsx`
- Create: `katrain/web/ui/src/kiosk/tutorial/useOgsPhysicalBoard.ts`
- Create: `katrain/web/ui/src/kiosk/tutorial/ogs-course.css`
- Modify: `katrain/web/ui/src/kiosk/KioskApp.tsx`
- Modify: `katrain/web/ui/src/kiosk/components/layout/KioskLayout.tsx`
- Modify: `katrain/web/ui/src/kiosk/pages/TutorialCategoriesPage.tsx`
- Modify: `katrain/web/ui/src/kiosk/pages/TutorialBooksPage.tsx`
- Modify: `katrain/web/ui/src/kiosk/pages/TutorialSectionPage.tsx`
- Test: `katrain/web/ui/src/kiosk/pages/OgsCoursePages.test.tsx` (new)
- Test: `katrain/web/ui/src/kiosk/components/layout/KioskLayout.test.tsx`

- [x] Add page tests with API responses for home→chapter→lesson navigation, board answer, choice answer, pass/remove/finish, next/previous step, error/retry, and other-book link. Ensure a puzzle has no choice controls. Add one board display/click case from `bl4-opening-4:1`: white to play, partial-board viewport and A/B/C labels, with displayed crop mapped back to absolute board coordinates. Cover OGS home → legacy library → category → library → OGS home, including a back control visible during library loading/error/empty/populated states. Cover `实体盘` enabled on a 19-line puzzle with ready camera/geometry, disabled with a visible reason on 9/13-line and non-board-answer steps, and screen move/confirmed physical move sharing the same source judge.
- [x] Run focused Vitest and confirm new tests fail before pages are implemented.
- [x] Implement the approved 1024×600 layout using existing Kiosk shell, typography, tactile button tokens, and board drawing. Remove `/kiosk/tutorial` from `RAIL_ROUTES` and add it to `SELF_LAYOUT_ROUTES` so the approved full-width home fits while topbar/Dock remain. Route `/kiosk/tutorial` to OGS home, `/kiosk/tutorial/chapter/:chapterId` and `/kiosk/tutorial/lesson/:lessonId` to the new pages. Map legacy categories to `/kiosk/tutorial/library`, retain existing `/:category` and `/section/:sectionId` deep links. Add a persistent library back control to `/kiosk/tutorial` because `/library` is L2 and has no Dock/Home; change `TutorialBooksPage` and `TutorialSectionPage` back/fallback targets to `/library`. Derive counts/titles/pages from API data. Support `viewport`, letters, shapes and absolute click coordinates; crop only the display while applying moves and captures on the full board. Show no fabricated completion percentage. Put a tactile `实体盘` action alongside previous/next controls, using the shared `PhysicalBoardIcon`; adapt `usePhysicalTsumego` and `useVisionSync` through the small `useOgsPhysicalBoard` hook only for 19-line `puzzle` steps. Map source top-origin y to vision coordinates, use the pure judge for both touch and physical confirmed moves, keep existing setup/status guidance, and never claim hardware readiness when camera/geometry is unavailable. Reset physical setup on step change; turn-off stays available.
- [x] Run focused Vitest and `npm run build:kiosk-2d`; fix only issues caused by this work. Commit task files.

### Task 5: Integrated verification and cleanup

**Files:**
- Test: `katrain/web/ui/tests/tutorial-kiosk.spec.ts` (extend focused OGS journey)
- Create: `docs/previews/ogs-course-runtime-2026-10-23/` (one representative 1024×600 runtime preview and comparison)
- Modify: `docs/superpowers/plans/2026-10-23-ogs-kiosk-course.md` (mark actual task status)

- [x] Start an isolated local backend with the imported sample data and the real Vite/Kiosk runtime. Verify course→chapter→board puzzle→correct/next and choice lesson, plus one pass/remove/finish sequence and unavailable/error handling. Use source import, not design fixture. Verify a representative 19-line puzzle displays and gates `实体盘` coherently in a simulated ready/unready hardware state; real RK3562 hardware acceptance remains a deployment step. Keep the existing non-OGS tutorial journey reachable from `/library` and update its Playwright starting path.
- [x] Capture representative 1024×600 screenshots, compare against the approved reference at the same viewport (side-by-side and overlay/difference), fix material geometry/typography/state differences, and avoid broad screenshot churn.
- [x] Run focused backend and frontend tests and a Kiosk build. Confirm no production import of `ogs-course-fixture.js` or TEST export.
- [x] Request independent Astra Max adversarial code review of the full diff; fix findings and repeat until approved. Record any content publication/license blocker separately from code completion.

**Verification record (2026-10-23):** 44 focused backend tests and 44 focused frontend tests passed; `npm run build:kiosk-2d` passed. The real Kiosk/Vite page used 3,551 imported TEST steps from a temporary local SQLite database, and the first board exercise plus the `ending-the-game` pass/removal/finish sequence worked in a 1024×600 browser. The existing Playwright route spec now starts at `/kiosk/tutorial/library`; its runner could not start because the pinned Chromium headless binary was absent, so the corresponding navigation was checked in the interactive browser. The local course-only preview backend did not serve the branded image or KataGo health routes; the topbar image and AI banner in its screenshots do not represent the complete app. Independent Astra Max adversarial review passed after fixing terminal physical-board convergence, extra-stone coordinates/rendering, and `cross` annotations. RK3562 camera/LED acceptance and production content publication are release steps. The TEST export declares AGPL-3.0-or-later; confirm distribution authorization before a production import.

## Execution and review sequence

1. Independent Astra Max plan review. Revise and request at most one more plan review (two rounds total), then proceed with the best reviewed plan.
2. Apply @superpowers:subagent-driven-development. After the contract in Task 1 is stable, Task 2 and Task 3 may run in parallel because they edit disjoint files; Task 4 follows both. Keep implementation, spec review, and code quality review proportional to the actual risk. The final Astra Max review is mandatory.
3. Keep all changes on `feature/ogs-kiosk-course-20261023` until user asks for integration/release. Do not commit the original worktree's unrelated changes.
