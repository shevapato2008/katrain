# Kiosk Shared Layer Extraction + Backend Integration Design

**Date:** 2026-02-18
**Scope:** Phase 6 (Shared Layer Extraction) + Phase 7 (Backend Integration)
**Branch:** `feature/rk3588-ui`
**Prerequisite:** Phases 1-5 complete (82 tests passing, all kiosk pages with mock data)

---

## Goal

Replace all kiosk mock data with real backend API calls while extracting shared code from `galaxy/` to top-level `src/` directories. After this work, kiosk has a fully functional auth, game, tsumego, kifu, live, and research experience backed by real data.

## Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Auth strategy | Reuse Galaxy JWT auth | Same backend, same `/auth/login` API |
| Game modes | All (AI + local PvP + network rooms) | Full parity with Galaxy |
| Shared layer location | `src/` top-level (in-place) | Already has `src/components/`, `src/hooks/` — avoid creating a new `src/shared/` layer |
| Implementation approach | Interleaved per-domain | Extract shared code + wire kiosk for each domain sequentially |
| i18n | Integrate with Phase 7 | Replace hardcoded Chinese with `useTranslation` as each domain is wired |
| Domain priority | Auth → Game → Tsumego → Kifu → Live → Research+i18n | Auth is foundation; game is core product; tsumego has complete API |

---

## Architecture

### Directory Convention

```
src/
├── api/              # Shared API clients
├── components/       # Shared UI components
├── context/          # Shared context providers (Auth, Settings)
├── hooks/            # Shared hooks
├── types/            # Shared TypeScript types
├── utils/            # Shared utilities
├── galaxy/           # Galaxy-specific code (never imported by kiosk)
├── kiosk/            # Kiosk-specific code (never imported by galaxy)
└── AppRouter.tsx     # Top-level routing + shared providers
```

### Import Rules (enforced after completion)

- `src/kiosk/**` may import from `src/{api,components,context,hooks,types,utils}/**` only
- `src/galaxy/**` may import from `src/{api,components,context,hooks,types,utils}/**` only
- Neither may import from the other's directory

### Provider Hierarchy Change

```
Before:
  AppRouter → GalaxyApp → AuthProvider → SettingsProvider → pages
  AppRouter → KioskApp → KioskAuthProvider → pages

After:
  AppRouter → AuthProvider → SettingsProvider → {GalaxyApp | KioskApp} → pages
```

Both UIs share a single auth session and language setting. Login on one UI is visible to the other.

---

## Domain 1: Auth

### Extract
- `galaxy/context/AuthContext.tsx` → `src/context/AuthContext.tsx`
- Auth API logic → `src/api/auth.ts`

### Wire Kiosk
- Lift `AuthProvider` to `AppRouter.tsx`
- Rewrite kiosk `LoginPage` to call real `/auth/login` API via shared `useAuth()`
- Replace `KioskAuthGuard` with shared guard using `useAuth()`

### Delete
- `kiosk/context/KioskAuthContext.tsx`
- `kiosk/components/guards/KioskAuthGuard.tsx`

### Galaxy Impact
- Update 4-5 Galaxy files that import `AuthContext` (path change only)

---

## Domain 2: Game

### Extract
- `galaxy/hooks/useSessionBase.ts` → `src/hooks/useSessionBase.ts`
- `galaxy/hooks/useGameSession.ts` → `src/hooks/useGameSession.ts`
- `Board.tsx`, `ScoreGraph.tsx`, `PlayerCard.tsx`, `ControlBar.tsx` — already in `src/components/` (no move needed)

### Wire Kiosk
- `GamePage`: replace `MockBoard` with real `Board`, wire `useGameSession(sessionId)`
- `GameControlPanel`: wire real actions (pass, resign, undo, requestAnalysis)
- `AiSetupPage`: call real session creation API, navigate to real session ID
- PvP setup page: wire to matchmaking/room API

### Delete
- `kiosk/components/game/MockBoard.tsx`
- `kiosk/components/game/KioskPlayerCard.tsx` (replaced by shared `PlayerCard`)
- `kiosk/components/game/KioskScoreGraph.tsx` (replaced by shared `ScoreGraph`)
- `mockGameState` from `kiosk/data/mocks.ts`

### Kiosk-Specific (keep)
- `GameControlPanel.tsx` — unique compact vertical layout for touch kiosk
- `ItemToggle.tsx` — kiosk-specific toggle control
- `KioskResultBadge.tsx` — simplified result display

---

## Domain 3: Tsumego

### Extract
- `galaxy/components/tsumego/MiniBoard.tsx` → `src/components/MiniBoard.tsx`
- `galaxy/hooks/useTsumegoProblem.ts` → `src/hooks/useTsumegoProblem.ts`
- Tsumego API calls already at `/api/v1/tsumego/*`

### Wire Kiosk
- `TsumegoPage`: call `GET /tsumego/levels` for level list (replace `mockTsumegoLevels`)
- New `TsumegoLevelPage` (route `tsumego/:levelId`): call API for problem list within level
- New `TsumegoProblemPage`: use shared `Board.tsx` + `useTsumegoProblem` hook for interactive solving

### Delete
- `kiosk/components/game/KioskMiniBoard.tsx` (exact duplicate of Galaxy's MiniBoard)
- `mockTsumegoLevels`, `mockTsumegoProblems` from `kiosk/data/mocks.ts`

---

## Domain 4: Kifu

### Extract
- `galaxy/types/kifu.ts` → `src/types/kifu.ts`
- `galaxy/api/kifuApi.ts` → `src/api/kifuApi.ts`
- `galaxy/utils/resultTranslation.ts` → `src/utils/resultTranslation.ts`

### Wire Kiosk
- `KifuPage`: call `kifuApi.list()` instead of `mockKifuList`
- Board preview: load real SGF via API
- `KioskResultBadge`: use shared `resultTranslation` internally

### Delete
- `mockKifuList` from `kiosk/data/mocks.ts`

---

## Domain 5: Live

### Extract
- `galaxy/types/live.ts` → `src/types/live.ts`
- `galaxy/api/live.ts` → `src/api/live.ts`
- `galaxy/hooks/live/useLiveMatches.ts` → `src/hooks/live/useLiveMatches.ts`
- `galaxy/hooks/live/useLiveMatch.ts` → `src/hooks/live/useLiveMatch.ts`

### Wire Kiosk
- `LivePage`: use `useLiveMatches()` with real 30s polling
- Add match detail page using `useLiveMatch(id)`

### Delete
- `mockLiveMatches` from `kiosk/data/mocks.ts`

---

## Domain 6: Research + i18n

### Extract
- `galaxy/hooks/useResearchSession.ts` → `src/hooks/useResearchSession.ts`
- `galaxy/hooks/useResearchBoard.ts` → `src/hooks/useResearchBoard.ts`
- `galaxy/utils/rankUtils.ts` → `src/utils/rankUtils.ts`
- `galaxy/context/SettingsContext.tsx` → `src/context/SettingsContext.tsx`

### Wire Kiosk
- `ResearchPage`: use real research session via `useResearchSession`
- `AiSetupPage`: import `rankUtils` instead of inline `rankLabel`
- `SettingsPage`: use shared `SettingsContext` for language switching
- All pages: replace hardcoded Chinese strings with `t('key')` via `useTranslation`

### Delete
- `mockResearchState` from `kiosk/data/mocks.ts`
- Inline `rankLabel` function from `AiSetupPage.tsx`

---

## Testing Strategy

### Per-Domain Test Flow
1. Run `npx vitest run` before extraction (baseline)
2. After each file move: run Galaxy tests to catch broken imports
3. After kiosk wiring: update kiosk tests to mock API layer (`vi.mock`)
4. End of domain: full test suite must pass

### Kiosk Test Migration
- Replace mock data assertions with API mock assertions
- Use `vi.mock('../../../api/kifuApi')` pattern for unit tests
- Keep component-level rendering tests; change data expectations

### Phase Gate Criteria
- [ ] No kiosk file imports from `src/galaxy/`
- [ ] No Galaxy file imports from `src/kiosk/`
- [ ] All `mock*` exports deleted from `kiosk/data/mocks.ts`
- [ ] Kiosk auth uses real JWT (no stub)
- [ ] Kiosk game page connects to real WebSocket session
- [ ] All kiosk tests pass with mocked API
- [ ] All Galaxy tests pass (including fixing 3 pre-existing failures)
- [ ] All kiosk pages use `useTranslation` for strings

---

## Files to Move (Summary)

| From | To | Type |
|------|----|------|
| `galaxy/context/AuthContext.tsx` | `src/context/AuthContext.tsx` | Context |
| `galaxy/context/SettingsContext.tsx` | `src/context/SettingsContext.tsx` | Context |
| `galaxy/hooks/useSessionBase.ts` | `src/hooks/useSessionBase.ts` | Hook |
| `galaxy/hooks/useGameSession.ts` | `src/hooks/useGameSession.ts` | Hook |
| `galaxy/hooks/useResearchSession.ts` | `src/hooks/useResearchSession.ts` | Hook |
| `galaxy/hooks/useResearchBoard.ts` | `src/hooks/useResearchBoard.ts` | Hook |
| `galaxy/hooks/useTsumegoProblem.ts` | `src/hooks/useTsumegoProblem.ts` | Hook |
| `galaxy/hooks/live/useLiveMatches.ts` | `src/hooks/live/useLiveMatches.ts` | Hook |
| `galaxy/hooks/live/useLiveMatch.ts` | `src/hooks/live/useLiveMatch.ts` | Hook |
| `galaxy/api/live.ts` | `src/api/live.ts` | API |
| `galaxy/api/kifuApi.ts` | `src/api/kifuApi.ts` | API |
| `galaxy/types/live.ts` | `src/types/live.ts` | Type |
| `galaxy/types/kifu.ts` | `src/types/kifu.ts` | Type |
| `galaxy/utils/rankUtils.ts` | `src/utils/rankUtils.ts` | Util |
| `galaxy/utils/resultTranslation.ts` | `src/utils/resultTranslation.ts` | Util |
| `galaxy/components/tsumego/MiniBoard.tsx` | `src/components/MiniBoard.tsx` | Component |

## Kiosk Files to Delete

| File | Replaced By |
|------|-------------|
| `kiosk/context/KioskAuthContext.tsx` | `src/context/AuthContext.tsx` |
| `kiosk/components/guards/KioskAuthGuard.tsx` | Shared guard using `useAuth()` |
| `kiosk/components/game/MockBoard.tsx` | `src/components/Board.tsx` |
| `kiosk/components/game/KioskPlayerCard.tsx` | `src/components/PlayerCard.tsx` |
| `kiosk/components/game/KioskScoreGraph.tsx` | `src/components/ScoreGraph.tsx` |
| `kiosk/components/game/KioskMiniBoard.tsx` | `src/components/MiniBoard.tsx` |
| `kiosk/data/mocks.ts` (all mock exports) | Real API calls via shared hooks |

## Risk Mitigation

- **Galaxy regressions from import changes:** Run Galaxy tests after each file move, not just at domain end
- **WebSocket compatibility:** Kiosk's GamePage must handle the same WebSocket protocol as Galaxy — reusing `useSessionBase` guarantees this
- **Auth token sharing:** Both UIs in the same browser tab share localStorage — lifting AuthProvider ensures consistent state
- **i18n coverage:** Use `grep -r "'" src/kiosk/pages/` to find remaining hardcoded strings before marking i18n complete
