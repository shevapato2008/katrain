# Baseline test failures (pre-existing, before sbc-tutorial-parity work)

> Captured 2026-06-28 on branch `feature/sbc-tutorial-parity`, after `npm install`, via `npx vitest run`.
> **These failures exist BEFORE any tutorial-module change.** They are unrelated to tutorial scope
> (orientation/jsdom, GamePage, AuthContext, TeachingSettings, ResearchPage, theme).
>
> **Adjusted verification gate for all phases:** a phase passes if it introduces **no NEW** failing
> test files/tests beyond this baseline, **and** any newly-added tutorial tests pass. "All green" is
> not achievable here and fixing these pre-existing failures is out of scope.

Summary: **7 test files failed · 19 tests failed · 377 passed (396 total)**. `npx vitest run` exit code = 1.

Pre-existing failing test files (do NOT attribute to tutorial work):
1. `src/components/TeachingSettingsDialog.test.tsx` — 3 tests
2. `src/context/AuthContext.test.tsx` — 1 test (login successfully)
3. `src/galaxy/pages/ResearchPage.test.tsx` — 2 tests
4. `src/kiosk/__tests__/GamePage.test.tsx` — 8 tests
5. `src/kiosk/__tests__/orientation.integration.test.tsx` — 3 tests
6. `src/kiosk/__tests__/OrientationContext.test.tsx` — 1 test
7. `src/kiosk/__tests__/theme.test.ts` — 1 test (Noto Serif SC only for h1)

Note: `orientation.integration` + `OrientationContext` + `theme` are pre-broken even though Phase 5
uses `useOrientation` and `kioskTheme`. The failures are environmental (localStorage/matchMedia in
jsdom), not logic the tutorial module depends on at runtime.
