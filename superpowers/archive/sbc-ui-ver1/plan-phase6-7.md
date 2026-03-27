# Kiosk Shared Layer + Backend Integration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Extract shared code from `galaxy/` to top-level `src/`, then wire all kiosk pages to real backend APIs, replacing mock data.

**Architecture:** Interleaved per-domain approach — for each feature domain (auth, game, tsumego, kifu, live, research), first extract shared code, then wire kiosk. 6 domains executed sequentially: auth → game → tsumego → kifu → live → research+i18n.

**Tech Stack:** React 19, TypeScript, MUI v7, React Router v6, Vitest, vi.mock for API mocking in tests

**Design doc:** `docs/plans/2026-02-18-kiosk-shared-layer-backend-integration-design.md`

**Branch:** `feature/rk3588-ui`

**Existing code to know about:**
- Entry: `katrain/web/ui/src/AppRouter.tsx` → lazy-loads `GalaxyApp` and `kiosk/KioskApp`
- `GalaxyApp.tsx` lives at `src/GalaxyApp.tsx` (NOT `src/galaxy/GalaxyApp.tsx`)
- Galaxy providers: `AuthProvider` + `SettingsProvider` currently inside `GalaxyApp.tsx`
- Kiosk stub auth: `kiosk/context/KioskAuthContext.tsx` (mock, no backend)
- Tests run with: `cd katrain/web/ui && npx vitest run <path>`
- All paths below are relative to `katrain/web/ui/src/` unless stated otherwise

**Import rule (enforced after completion):**
- `kiosk/` may import from top-level `src/` only (never from `galaxy/`)
- `galaxy/` may import from top-level `src/` only (never from `kiosk/`)

---

## Domain 1: Auth

### Task 1: Extract AuthContext to shared location

**Files:**
- Move: `galaxy/context/AuthContext.tsx` → `context/AuthContext.tsx`
- Modify: `GalaxyApp.tsx` (update import path)
- Modify: `galaxy/components/layout/GalaxySidebar.tsx` (update import path)
- Modify: `galaxy/components/guards/AuthGuard.tsx` (update import path)
- Modify: `galaxy/pages/ResearchPage.tsx` (update import path)
- Modify: `galaxy/pages/HvHLobbyPage.tsx` (update import path)
- Modify: `galaxy/components/auth/LoginModal.tsx` (update import path)

**Step 1: Move the file**

```bash
cd katrain/web/ui
mkdir -p src/context
git mv src/galaxy/context/AuthContext.tsx src/context/AuthContext.tsx
```

**Step 2: Update all Galaxy imports**

Find and replace in all files that import from `galaxy/context/AuthContext`:
- `GalaxyApp.tsx`: change `'./galaxy/context/AuthContext'` → `'./context/AuthContext'`
- `galaxy/components/layout/GalaxySidebar.tsx`: change `'../../context/AuthContext'` → `'../../../context/AuthContext'`
- `galaxy/components/guards/AuthGuard.tsx`: change `'../../context/AuthContext'` → `'../../../context/AuthContext'`
- `galaxy/pages/ResearchPage.tsx`: change `'../context/AuthContext'` → `'../../context/AuthContext'`
- `galaxy/pages/HvHLobbyPage.tsx`: change `'../context/AuthContext'` → `'../../context/AuthContext'`
- `galaxy/components/auth/LoginModal.tsx`: change `'../../context/AuthContext'` → `'../../../context/AuthContext'`

**Step 3: Run Galaxy tests to verify no broken imports**

Run: `cd katrain/web/ui && npx vitest run src/galaxy/ src/components/`
Expected: Same pass/fail as before (3 pre-existing failures in GalaxySidebar/ResearchPage are expected)

**Step 4: Commit**

```bash
git add -A
git commit -m "refactor: move AuthContext from galaxy/ to shared src/context/"
```

---

### Task 2: Extract SettingsContext to shared location

**Files:**
- Move: `galaxy/context/SettingsContext.tsx` → `context/SettingsContext.tsx`
- Modify: `GalaxyApp.tsx` (update import path)
- Modify: All Galaxy files importing SettingsContext

**Step 1: Move the file**

```bash
git mv src/galaxy/context/SettingsContext.tsx src/context/SettingsContext.tsx
```

**Step 2: Update Galaxy imports**

Find all imports of `SettingsContext` in Galaxy files and update paths:
- `GalaxyApp.tsx`: `'./galaxy/context/SettingsContext'` → `'./context/SettingsContext'`
- Any Galaxy component importing from `'../context/SettingsContext'` or `'../../context/SettingsContext'`: adjust path to go through `../../../context/SettingsContext` etc.

Run: `cd katrain/web/ui && grep -r "SettingsContext" src/galaxy/ src/GalaxyApp.tsx --include="*.tsx" --include="*.ts" -l`
to find all files that need updating.

**Step 3: Run Galaxy tests**

Run: `cd katrain/web/ui && npx vitest run`
Expected: Same baseline as before

**Step 4: Commit**

```bash
git add -A
git commit -m "refactor: move SettingsContext from galaxy/ to shared src/context/"
```

---

### Task 3: Lift AuthProvider + SettingsProvider to AppRouter

**Files:**
- Modify: `AppRouter.tsx` (add providers)
- Modify: `GalaxyApp.tsx` (remove providers, keep only Routes)

**Step 1: Update AppRouter.tsx**

Add `AuthProvider` and `SettingsProvider` wrapping the `<Routes>`:

```tsx
// AppRouter.tsx
import { lazy, Suspense } from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { ThemeProvider, CssBaseline } from '@mui/material';
import { zenTheme } from './theme';
import { AuthProvider } from './context/AuthContext';
import { SettingsProvider } from './context/SettingsContext';
import ZenModeApp from './ZenModeApp';

const GalaxyApp = lazy(() => import('./GalaxyApp'));
const KioskApp = lazy(() => import('./kiosk/KioskApp'));

const AppRouter = () => (
  <BrowserRouter>
    <ThemeProvider theme={zenTheme}>
      <CssBaseline />
      <AuthProvider>
        <SettingsProvider>
          <Suspense fallback={null}>
            <Routes>
              <Route path="/kiosk/*" element={<KioskApp />} />
              <Route path="/galaxy/*" element={<GalaxyApp />} />
              <Route path="/*" element={<ZenModeApp />} />
            </Routes>
          </Suspense>
        </SettingsProvider>
      </AuthProvider>
    </ThemeProvider>
  </BrowserRouter>
);

export default AppRouter;
```

**Step 2: Remove providers from GalaxyApp.tsx**

Remove `AuthProvider` and `SettingsProvider` wrapping from `GalaxyApp.tsx`. Keep only the `<Routes>` with Galaxy-specific routes. Remove the imports for `AuthProvider` and `SettingsProvider`.

```tsx
// GalaxyApp.tsx — simplified
import { Routes, Route, Navigate } from 'react-router-dom';
import MainLayout from './galaxy/components/layout/MainLayout';
// ... page imports unchanged ...

const GalaxyApp = () => (
  <Routes>
    <Route element={<MainLayout />}>
      {/* ... all Galaxy routes unchanged ... */}
    </Route>
    <Route path="*" element={<Navigate to="/galaxy" replace />} />
  </Routes>
);

export default GalaxyApp;
```

**Step 3: Run all tests**

Run: `cd katrain/web/ui && npx vitest run`
Expected: All existing tests pass (Galaxy tests that use AuthContext should still work because AuthProvider is now at a higher level — but unit tests may need the provider wrapped. Check if Galaxy tests render with their own providers or rely on the app-level one.)

Note: If Galaxy page tests fail because they don't wrap with AuthProvider in their test setup, you may need to update those test files to add `<AuthProvider>` to their render wrappers. However, most Galaxy page tests likely already include their own mock providers.

**Step 4: Commit**

```bash
git add -A
git commit -m "refactor: lift AuthProvider and SettingsProvider to AppRouter level"
```

---

### Task 4: Wire kiosk LoginPage to real auth API

**Files:**
- Modify: `kiosk/pages/LoginPage.tsx` (use shared `useAuth`)
- Modify: `kiosk/__tests__/KioskAuth.test.tsx` (update to use shared auth)

**Step 1: Update LoginPage to use shared auth**

Replace `useKioskAuth` with `useAuth` from shared context:

```tsx
// kiosk/pages/LoginPage.tsx
import { useState } from 'react';
import { Box, TextField, Button, Typography, Alert } from '@mui/material';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';

const LoginPage = () => {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleLogin = async () => {
    setError('');
    setLoading(true);
    try {
      await login(username, password);
      navigate('/kiosk/play', { replace: true });
    } catch (e: any) {
      setError(e.message || '登录失败');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100vh', p: 3 }}>
      <Typography variant="h4" sx={{ mb: 3 }}>KaTrain</Typography>
      {error && <Alert severity="error" sx={{ mb: 2, width: '100%', maxWidth: 360 }}>{error}</Alert>}
      <TextField
        label="用户名"
        value={username}
        onChange={(e) => setUsername(e.target.value)}
        sx={{ mb: 2, width: '100%', maxWidth: 360 }}
      />
      <TextField
        label="密码"
        type="password"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        sx={{ mb: 2, width: '100%', maxWidth: 360 }}
      />
      <Button
        variant="contained"
        onClick={handleLogin}
        disabled={loading || !username}
        sx={{ width: '100%', maxWidth: 360, minHeight: 48 }}
      >
        {loading ? '登录中...' : '登录'}
      </Button>
    </Box>
  );
};

export default LoginPage;
```

**Step 2: Update kiosk auth test**

Update `kiosk/__tests__/KioskAuth.test.tsx` to mock the shared auth context instead of the kiosk stub. Tests should mock `useAuth` to return controllable auth state.

**Step 3: Run kiosk tests**

Run: `cd katrain/web/ui && npx vitest run src/kiosk/`
Expected: All pass (some tests may need updating if they reference `useKioskAuth`)

**Step 4: Commit**

```bash
git add -A
git commit -m "feat(kiosk): wire LoginPage to real auth API via shared AuthContext"
```

---

### Task 5: Replace KioskAuthGuard + delete stubs

**Files:**
- Modify: `kiosk/KioskApp.tsx` (use shared auth, remove KioskAuthProvider)
- Modify: `kiosk/components/guards/KioskAuthGuard.tsx` (use shared useAuth)
- Delete: `kiosk/context/KioskAuthContext.tsx`
- Modify: `kiosk/components/layout/KioskLayout.tsx` (get username from shared auth)
- Modify: All kiosk test files referencing KioskAuthContext

**Step 1: Update KioskAuthGuard**

```tsx
// kiosk/components/guards/KioskAuthGuard.tsx
import { Navigate, Outlet } from 'react-router-dom';
import { useAuth } from '../../../context/AuthContext';

const KioskAuthGuard = () => {
  const { isAuthenticated } = useAuth();
  return isAuthenticated ? <Outlet /> : <Navigate to="/kiosk/login" replace />;
};

export default KioskAuthGuard;
```

**Step 2: Update KioskApp.tsx**

Remove `KioskAuthProvider` and `useKioskAuth` imports. Remove `KioskAuthProvider` wrapper. Get `user` from `useAuth` instead:

```tsx
// Key changes in KioskApp.tsx:
import { useAuth } from '../context/AuthContext';
// Remove: import { KioskAuthProvider, useKioskAuth } from './context/KioskAuthContext';

const KioskRoutes = () => {
  const { user } = useAuth();
  // ...
  <KioskLayout username={user?.username} />
  // ...
};

const KioskApp = () => (
  <ThemeProvider theme={kioskTheme}>
    <CssBaseline />
    <KioskRoutes />
  </ThemeProvider>
);
```

Note: Galaxy's `User` type has `username` (not `name`). Update `KioskLayout` to accept this.

**Step 3: Delete KioskAuthContext**

```bash
git rm src/kiosk/context/KioskAuthContext.tsx
```

**Step 4: Update all kiosk tests**

Find all test files importing `KioskAuthContext` or `KioskAuthProvider`:
```bash
grep -r "KioskAuth" src/kiosk/__tests__/ -l
```

Replace with shared auth mock:
```tsx
// Common test pattern:
vi.mock('../../context/AuthContext', () => ({
  useAuth: () => ({
    isAuthenticated: true,
    user: { id: 1, username: '张三', rank: '2D', credits: 0 },
    login: vi.fn(),
    logout: vi.fn(),
    token: 'mock-token',
  }),
}));
```

**Step 5: Run all tests**

Run: `cd katrain/web/ui && npx vitest run`
Expected: All kiosk + Galaxy tests pass

**Step 6: Commit**

```bash
git add -A
git commit -m "refactor(kiosk): replace stub auth with shared AuthContext, delete KioskAuthContext"
```

---

## Domain 2: Game

### Task 6: Extract game session hooks to shared location

**Files:**
- Move: `galaxy/hooks/useSessionBase.ts` → `hooks/useSessionBase.ts`
- Move: `galaxy/hooks/useGameSession.ts` → `hooks/useGameSession.ts`
- Modify: All Galaxy files importing these hooks

**Step 1: Move files**

```bash
git mv src/galaxy/hooks/useSessionBase.ts src/hooks/useSessionBase.ts
git mv src/galaxy/hooks/useGameSession.ts src/hooks/useGameSession.ts
```

**Step 2: Update Galaxy imports**

Find and update all Galaxy files importing these hooks:
```bash
grep -r "useSessionBase\|useGameSession" src/galaxy/ --include="*.ts" --include="*.tsx" -l
```

Files likely needing update:
- `galaxy/hooks/useResearchSession.ts`: `'./useSessionBase'` → `'../../hooks/useSessionBase'`
- `galaxy/pages/GamePage.tsx`: `'../hooks/useGameSession'` → `'../../hooks/useGameSession'`
- `galaxy/pages/GameRoomPage.tsx`: same pattern
- Any other Galaxy page using game sessions

**Step 3: Run tests**

Run: `cd katrain/web/ui && npx vitest run`
Expected: Same baseline

**Step 4: Commit**

```bash
git add -A
git commit -m "refactor: move useSessionBase and useGameSession to shared src/hooks/"
```

---

### Task 7: Wire kiosk GamePage to real Board and session

**Files:**
- Modify: `kiosk/pages/GamePage.tsx` (replace MockBoard with real Board, wire useGameSession)
- Modify: `kiosk/components/game/GameControlPanel.tsx` (wire real actions)
- Delete: `kiosk/components/game/MockBoard.tsx`
- Delete: `kiosk/components/game/KioskPlayerCard.tsx` (use shared PlayerCard)
- Delete: `kiosk/components/game/KioskScoreGraph.tsx` (use shared ScoreGraph)
- Modify: `kiosk/__tests__/GamePage.test.tsx` (mock useGameSession)

**Step 1: Rewrite GamePage to use real session**

Replace mock imports with real hooks and shared components:

```tsx
// kiosk/pages/GamePage.tsx — key structure
import { useParams } from 'react-router-dom';
import { useGameSession } from '../../hooks/useGameSession';
import { useAuth } from '../../context/AuthContext';
import Board from '../../components/Board';
import GameControlPanel from '../components/game/GameControlPanel';

const GamePage = () => {
  const { sessionId } = useParams<{ sessionId: string }>();
  const { token } = useAuth();
  const session = useGameSession({ token });

  useEffect(() => {
    if (sessionId) session.setSessionId(sessionId);
  }, [sessionId]);

  if (!session.gameState) return <LoadingSkeleton />;

  return (
    <Box sx={{ display: 'flex', height: '100vh' }}>
      <Box sx={{ flex: 1 }}>
        <Board gameState={session.gameState} onMove={session.onMove} />
      </Box>
      <GameControlPanel
        gameState={session.gameState}
        onAction={session.handleAction}
        onNavigate={session.onNavigate}
      />
    </Box>
  );
};
```

**Step 2: Rewrite GameControlPanel to accept real props**

Change `GameControlPanel` to accept `gameState`, `onAction`, `onNavigate` props instead of using mock data internally. Keep the compact kiosk-specific layout but wire actions to real callbacks.

**Step 3: Delete replaced components**

```bash
git rm src/kiosk/components/game/MockBoard.tsx
git rm src/kiosk/components/game/KioskPlayerCard.tsx
git rm src/kiosk/components/game/KioskScoreGraph.tsx
```

**Step 4: Update GamePage tests**

Mock `useGameSession` to return controlled state:

```tsx
vi.mock('../../hooks/useGameSession', () => ({
  useGameSession: () => ({
    sessionId: 'test-session',
    setSessionId: vi.fn(),
    gameState: { /* mock GameState matching src/api.ts shape */ },
    onMove: vi.fn(),
    handleAction: vi.fn(),
    onNavigate: vi.fn(),
    error: null,
  }),
}));
```

**Step 5: Remove mockGameState from mocks.ts**

Delete `mockGameState` and related types (`KioskTimerState`, `KioskAnalysisPoint`) from `kiosk/data/mocks.ts`.

**Step 6: Run tests**

Run: `cd katrain/web/ui && npx vitest run src/kiosk/`
Expected: All pass

**Step 7: Commit**

```bash
git add -A
git commit -m "feat(kiosk): wire GamePage to real Board and useGameSession, delete mock components"
```

---

### Task 8: Wire kiosk AiSetupPage to real session creation

**Files:**
- Modify: `kiosk/pages/AiSetupPage.tsx` (call real API to create session)
- Modify: `kiosk/__tests__/AiSetupPage.test.tsx` (mock API calls)

**Step 1: Update AiSetupPage handleStart**

Replace the mock navigation with real session creation:

```tsx
import { API } from '../../api';
import { useAuth } from '../../context/AuthContext';
import { internalToRank, sliderToInternal } from '../../utils/rankUtils';

// In handleStart:
const handleStart = async () => {
  try {
    const response = await API.createSession({
      mode: mode === 'ranked' ? 'ranked' : 'free',
      boardSize,
      rules,
      // ... other settings
    });
    navigate(`/kiosk/play/ai/game/${response.session_id}`);
  } catch (e) {
    // Show error
  }
};
```

Also replace inline `rankLabel` function with import from shared `rankUtils.ts` (moved in Domain 6, but can import now if already moved, or keep inline for now).

**Step 2: Update tests to mock API**

```tsx
vi.mock('../../api', () => ({
  API: {
    createSession: vi.fn().mockResolvedValue({ session_id: 'new-session-123' }),
  },
}));
```

**Step 3: Run tests**

Run: `cd katrain/web/ui && npx vitest run src/kiosk/__tests__/AiSetupPage.test.tsx`
Expected: All pass

**Step 4: Commit**

```bash
git add -A
git commit -m "feat(kiosk): wire AiSetupPage to real session creation API"
```

---

## Domain 3: Tsumego

### Task 9: Extract MiniBoard + useTsumegoProblem to shared location

**Files:**
- Move: `galaxy/components/tsumego/MiniBoard.tsx` → `components/MiniBoard.tsx`
- Move: `galaxy/hooks/useTsumegoProblem.ts` → `hooks/useTsumegoProblem.ts`
- Delete: `kiosk/components/game/KioskMiniBoard.tsx` (exact duplicate)
- Modify: Galaxy files importing MiniBoard and useTsumegoProblem

**Step 1: Move MiniBoard**

```bash
git mv src/galaxy/components/tsumego/MiniBoard.tsx src/components/MiniBoard.tsx
```

**Step 2: Delete kiosk duplicate**

```bash
git rm src/kiosk/components/game/KioskMiniBoard.tsx
```

**Step 3: Update all imports**

Galaxy files importing MiniBoard:
```bash
grep -r "MiniBoard" src/galaxy/ --include="*.tsx" -l
```
Update paths from `'../tsumego/MiniBoard'` or `'../../components/tsumego/MiniBoard'` to `'../../components/MiniBoard'` (adjust depth).

Kiosk files that imported `KioskMiniBoard`:
```bash
grep -r "KioskMiniBoard" src/kiosk/ --include="*.tsx" -l
```
Replace with `import MiniBoard from '../../components/MiniBoard'` (adjust path).

**Step 4: Move useTsumegoProblem**

```bash
git mv src/galaxy/hooks/useTsumegoProblem.ts src/hooks/useTsumegoProblem.ts
```

Update Galaxy imports (tsumego pages):
```bash
grep -r "useTsumegoProblem" src/galaxy/ --include="*.tsx" -l
```

**Step 5: Run tests**

Run: `cd katrain/web/ui && npx vitest run`
Expected: All pass

**Step 6: Commit**

```bash
git add -A
git commit -m "refactor: move MiniBoard and useTsumegoProblem to shared location, delete KioskMiniBoard"
```

---

### Task 10: Wire TsumegoPage to real API + implement detail pages

**Files:**
- Modify: `kiosk/pages/TsumegoPage.tsx` (call real API)
- Create: `kiosk/pages/TsumegoLevelPage.tsx` (problem list for a level)
- Create: `kiosk/pages/TsumegoProblemPage.tsx` (interactive problem solving)
- Modify: `kiosk/KioskApp.tsx` (update routes)
- Modify: `kiosk/__tests__/TsumegoPage.test.tsx` (mock API)
- Create: `kiosk/__tests__/TsumegoLevelPage.test.tsx`
- Create: `kiosk/__tests__/TsumegoProblemPage.test.tsx`

**Step 1: Write TsumegoPage test with API mock**

```tsx
// kiosk/__tests__/TsumegoPage.test.tsx
vi.mock('../../api', () => ({
  API: {
    getTsumegoLevels: vi.fn().mockResolvedValue({
      levels: [
        { id: '15k', rank: '15K', totalProblems: 1000, categories: [...] },
        // ...
      ]
    }),
  },
}));
```

**Step 2: Update TsumegoPage to fetch from API**

Replace `mockTsumegoLevels` import with `useEffect` + `useState` + API call to `GET /api/v1/tsumego/levels`. Show loading state while fetching.

**Step 3: Implement TsumegoLevelPage**

New page at route `tsumego/:levelId` that:
- Fetches problem list for the level from API
- Shows filterable problem grid with MiniBoard thumbnails
- Click navigates to `tsumego/problem/:problemId`

**Step 4: Implement TsumegoProblemPage**

New page that:
- Uses shared `useTsumegoProblem(problemId)` hook
- Renders shared `Board.tsx` for interactive stone placement
- Shows problem status (solved/failed), hint toggle, reset, undo buttons
- Kiosk-specific compact layout

**Step 5: Update kiosk routes**

```tsx
// In KioskApp.tsx, replace PlaceholderPage for tsumego routes:
<Route path="tsumego" element={<TsumegoPage />} />
<Route path="tsumego/:levelId" element={<TsumegoLevelPage />} />
<Route path="tsumego/problem/:problemId" element={<TsumegoProblemPage />} />
```

**Step 6: Delete mock data**

Remove `mockTsumegoLevels` and `mockTsumegoProblems` from `kiosk/data/mocks.ts`.

**Step 7: Run tests**

Run: `cd katrain/web/ui && npx vitest run src/kiosk/`
Expected: All pass

**Step 8: Commit**

```bash
git add -A
git commit -m "feat(kiosk): wire TsumegoPage to real API, add TsumegoLevelPage and TsumegoProblemPage"
```

---

## Domain 4: Kifu

### Task 11: Extract kifu types, API, and resultTranslation to shared location

**Files:**
- Move: `galaxy/types/kifu.ts` → `types/kifu.ts`
- Move: `galaxy/api/kifuApi.ts` → `api/kifuApi.ts`
- Move: `galaxy/utils/resultTranslation.ts` → `utils/resultTranslation.ts`
- Modify: Galaxy files importing these

**Step 1: Move files**

```bash
mkdir -p src/types src/api src/utils
git mv src/galaxy/types/kifu.ts src/types/kifu.ts
git mv src/galaxy/api/kifuApi.ts src/api/kifuApi.ts
git mv src/galaxy/utils/resultTranslation.ts src/utils/resultTranslation.ts
```

**Step 2: Update Galaxy imports**

```bash
grep -r "types/kifu\|api/kifuApi\|utils/resultTranslation" src/galaxy/ --include="*.ts" --include="*.tsx" -l
```

Update each found file's import path.

**Step 3: Update internal imports in moved files**

`kifuApi.ts` imports from `'../types/kifu'` — update to `'../types/kifu'` (may still work if both are at same level, but verify).

**Step 4: Run tests**

Run: `cd katrain/web/ui && npx vitest run`
Expected: All pass

**Step 5: Commit**

```bash
git add -A
git commit -m "refactor: move kifu types, API, and resultTranslation to shared location"
```

---

### Task 12: Wire KifuPage to real API

**Files:**
- Modify: `kiosk/pages/KifuPage.tsx` (use real API)
- Modify: `kiosk/__tests__/KifuPage.test.tsx` (mock API)
- Modify: `kiosk/components/game/KioskResultBadge.tsx` (use shared resultTranslation)

**Step 1: Update KifuPage to fetch from API**

Replace `mockKifuList` with `KifuAPI.getAlbums()`. Use `useState`/`useEffect` for data fetching. Update field names to match `KifuAlbumSummary` type (e.g., `player_black` instead of `playerBlack`).

**Step 2: Update KioskResultBadge**

Import and use `translateResult` from shared `utils/resultTranslation.ts` instead of inline result formatting.

**Step 3: Delete mockKifuList from mocks.ts**

**Step 4: Update tests**

```tsx
vi.mock('../../api/kifuApi', () => ({
  KifuAPI: {
    getAlbums: vi.fn().mockResolvedValue({
      items: [{ id: 1, player_black: '柯洁', /* ... */ }],
      total: 1, page: 1, page_size: 20,
    }),
  },
}));
```

**Step 5: Run tests**

Run: `cd katrain/web/ui && npx vitest run src/kiosk/`
Expected: All pass

**Step 6: Commit**

```bash
git add -A
git commit -m "feat(kiosk): wire KifuPage to real kifu API, use shared resultTranslation"
```

---

## Domain 5: Live

### Task 13: Extract live types, API, and hooks to shared location

**Files:**
- Move: `galaxy/types/live.ts` → `types/live.ts`
- Move: `galaxy/api/live.ts` → `api/live.ts`
- Move: `galaxy/hooks/live/useLiveMatches.ts` → `hooks/live/useLiveMatches.ts`
- Move: `galaxy/hooks/live/useLiveMatch.ts` → `hooks/live/useLiveMatch.ts`
- Modify: Galaxy files importing these

**Step 1: Move files**

```bash
mkdir -p src/hooks/live
git mv src/galaxy/types/live.ts src/types/live.ts
git mv src/galaxy/api/live.ts src/api/live.ts
git mv src/galaxy/hooks/live/useLiveMatches.ts src/hooks/live/useLiveMatches.ts
git mv src/galaxy/hooks/live/useLiveMatch.ts src/hooks/live/useLiveMatch.ts
```

**Step 2: Update all imports in moved files**

- `api/live.ts` imports from `'../types/live'` — update to `'../types/live'` (same relative path if both at top level)
- `hooks/live/useLiveMatches.ts` imports from `'../../api/live'` and `'../../types/live'` and `'../../../hooks/useTranslation'` — update to `'../../api/live'`, `'../../types/live'`, `'../useTranslation'`
- `hooks/live/useLiveMatch.ts` — similar updates

**Step 3: Update Galaxy imports**

```bash
grep -r "types/live\|api/live\|hooks/live/useLiveMatch" src/galaxy/ --include="*.ts" --include="*.tsx" -l
```

**Step 4: Run tests**

Run: `cd katrain/web/ui && npx vitest run`
Expected: All pass

**Step 5: Commit**

```bash
git add -A
git commit -m "refactor: move live types, API, and hooks to shared location"
```

---

### Task 14: Wire LivePage to real API + implement match detail

**Files:**
- Modify: `kiosk/pages/LivePage.tsx` (use useLiveMatches hook)
- Create: `kiosk/pages/LiveMatchPage.tsx` (match detail with board)
- Modify: `kiosk/KioskApp.tsx` (update route)
- Modify: `kiosk/__tests__/LivePage.test.tsx` (mock hook)
- Create: `kiosk/__tests__/LiveMatchPage.test.tsx`

**Step 1: Update LivePage to use useLiveMatches**

Replace `mockLiveMatches` with `useLiveMatches()` hook. Update field names to match `MatchSummary` type. Add loading/error states.

**Step 2: Implement LiveMatchPage**

New page at route `live/:matchId` that:
- Uses `useLiveMatch(matchId)` for real-time match data
- Renders shared `Board.tsx` with match position
- Shows player info, analysis, and playback controls

**Step 3: Update routes**

```tsx
<Route path="live/:matchId" element={<LiveMatchPage />} />
```

**Step 4: Delete mockLiveMatches from mocks.ts**

**Step 5: Run tests**

Run: `cd katrain/web/ui && npx vitest run src/kiosk/`
Expected: All pass

**Step 6: Commit**

```bash
git add -A
git commit -m "feat(kiosk): wire LivePage to real API, add LiveMatchPage with real-time updates"
```

---

## Domain 6: Research + i18n + Utils

### Task 15: Extract research hooks and rankUtils to shared location

**Files:**
- Move: `galaxy/hooks/useResearchSession.ts` → `hooks/useResearchSession.ts`
- Move: `galaxy/hooks/useResearchBoard.ts` → `hooks/useResearchBoard.ts`
- Move: `galaxy/utils/rankUtils.ts` → `utils/rankUtils.ts`
- Modify: Galaxy files importing these

**Step 1: Move files**

```bash
git mv src/galaxy/hooks/useResearchSession.ts src/hooks/useResearchSession.ts
git mv src/galaxy/hooks/useResearchBoard.ts src/hooks/useResearchBoard.ts
git mv src/galaxy/utils/rankUtils.ts src/utils/rankUtils.ts
```

**Step 2: Update imports in moved files**

- `useResearchSession.ts` imports from `'./useSessionBase'` — update to `'./useSessionBase'` (same dir now)
- `useResearchBoard.ts` imports from `'../utils/sgfSerializer'` and `'../components/research/ResearchToolbar'` — update paths. Note: `sgfSerializer` stays in `galaxy/utils/` for now (or move it too if kiosk needs it). `ResearchToolbar` types may need to be extracted or the type import adjusted.

**Step 3: Update Galaxy imports**

```bash
grep -r "useResearchSession\|useResearchBoard\|rankUtils" src/galaxy/ --include="*.ts" --include="*.tsx" -l
```

**Step 4: Run tests**

Run: `cd katrain/web/ui && npx vitest run`
Expected: All pass

**Step 5: Commit**

```bash
git add -A
git commit -m "refactor: move research hooks and rankUtils to shared location"
```

---

### Task 16: Wire kiosk ResearchPage + AiSetupPage to shared code

**Files:**
- Modify: `kiosk/pages/ResearchPage.tsx` (use real research session)
- Modify: `kiosk/pages/AiSetupPage.tsx` (use shared rankUtils)
- Modify: `kiosk/__tests__/ResearchPage.test.tsx` (mock hooks)

**Step 1: Update ResearchPage**

Replace mock data with `useResearchSession()` and `useResearchBoard()`. Replace `MockBoard` with real `Board.tsx`. Keep kiosk-specific two-panel layout.

**Step 2: Update AiSetupPage**

Replace inline `rankLabel` function with import from `utils/rankUtils.ts`:
```tsx
import { internalToRank, sliderToInternal } from '../../utils/rankUtils';
```

**Step 3: Delete mockResearchState from mocks.ts**

**Step 4: Update tests**

```tsx
vi.mock('../../hooks/useResearchSession', () => ({
  useResearchSession: () => ({
    sessionId: 'research-1',
    gameState: { /* mock */ },
    createSession: vi.fn(),
    onMove: vi.fn(),
    // ...
  }),
}));
```

**Step 5: Run tests**

Run: `cd katrain/web/ui && npx vitest run src/kiosk/`
Expected: All pass

**Step 6: Commit**

```bash
git add -A
git commit -m "feat(kiosk): wire ResearchPage to real session, use shared rankUtils in AiSetupPage"
```

---

### Task 17: i18n integration across all kiosk pages

**Files:**
- Modify: All kiosk page files (replace hardcoded Chinese strings with `t()` calls)
- Modify: `kiosk/pages/SettingsPage.tsx` (use shared SettingsContext for language)

**Step 1: Update SettingsPage to use shared SettingsContext**

```tsx
import { useSettings } from '../../context/SettingsContext';

const SettingsPage = () => {
  const { language, setLanguage, languages } = useSettings();
  // Use languages array for selector, setLanguage for onChange
};
```

**Step 2: Add useTranslation to all kiosk pages**

For each kiosk page, add:
```tsx
import { useTranslation } from '../../hooks/useTranslation';

const Page = () => {
  const { t } = useTranslation();
  // Replace hardcoded strings: '对弈' → t('nav:play', '对弈')
  // ...
};
```

Pages to update:
- `PlayPage.tsx` — mode card titles/subtitles
- `AiSetupPage.tsx` — section labels, button text
- `GamePage.tsx` — control panel labels
- `TsumegoPage.tsx` — title, subtitle
- `ResearchPage.tsx` — labels
- `KifuPage.tsx` — title, column headers
- `LivePage.tsx` — title, status labels
- `SettingsPage.tsx` — section headers
- `LoginPage.tsx` — labels, button text
- `GameControlPanel.tsx` — button labels
- `NavigationRail.tsx` — tab labels
- `StatusBar.tsx` — labels

**Step 3: Run tests**

Run: `cd katrain/web/ui && npx vitest run src/kiosk/`

Note: Tests using `screen.getByText('死活题')` may need updating to use regex or the translated key, depending on how the test mocks the i18n. If `useTranslation` returns the fallback in test environment (which it likely does since no translations are loaded), the existing Chinese fallback strings should still work.

**Step 4: Commit**

```bash
git add -A
git commit -m "feat(kiosk): integrate i18n across all kiosk pages via shared useTranslation"
```

---

## Domain 7: Cleanup

### Task 18: Delete mocks.ts and verify clean state

**Files:**
- Delete or clean: `kiosk/data/mocks.ts` (remove all mock exports, or delete file if empty)
- Verify: No kiosk file imports from `galaxy/`
- Verify: No Galaxy file imports from `kiosk/`

**Step 1: Check remaining mock usage**

```bash
grep -r "from.*data/mocks\|from.*mocks" src/kiosk/ --include="*.ts" --include="*.tsx" -l
```

If any files still import from mocks, update them. If `mocks.ts` is now empty, delete it.

**Step 2: Verify import rules**

```bash
# No kiosk → galaxy imports
grep -r "from.*galaxy/" src/kiosk/ --include="*.ts" --include="*.tsx"
# Should return nothing

# No galaxy → kiosk imports
grep -r "from.*kiosk/" src/galaxy/ --include="*.ts" --include="*.tsx"
# Should return nothing
```

**Step 3: Run full test suite**

Run: `cd katrain/web/ui && npx vitest run`
Expected: All tests pass

**Step 4: Commit**

```bash
git add -A
git commit -m "chore(kiosk): delete mock data, verify clean shared layer boundaries"
```

---

## Phase Gate: Entry Criteria for Phase 8+

Before proceeding to Phase 8 (Kiosk Infrastructure), verify:

- [ ] No kiosk file imports from `src/galaxy/`
- [ ] No Galaxy file imports from `src/kiosk/`
- [ ] All `mock*` exports deleted from `kiosk/data/mocks.ts` (or file removed)
- [ ] Kiosk auth uses real JWT (no stub)
- [ ] Kiosk game page connects to real WebSocket session
- [ ] All kiosk tests pass with mocked API
- [ ] All Galaxy tests pass
- [ ] All kiosk pages use `useTranslation` for i18n strings

```bash
cd katrain/web/ui && npx vitest run   # Full regression
```

---

## Files Moved Summary

| From | To |
|------|----|
| `galaxy/context/AuthContext.tsx` | `context/AuthContext.tsx` |
| `galaxy/context/SettingsContext.tsx` | `context/SettingsContext.tsx` |
| `galaxy/hooks/useSessionBase.ts` | `hooks/useSessionBase.ts` |
| `galaxy/hooks/useGameSession.ts` | `hooks/useGameSession.ts` |
| `galaxy/hooks/useResearchSession.ts` | `hooks/useResearchSession.ts` |
| `galaxy/hooks/useResearchBoard.ts` | `hooks/useResearchBoard.ts` |
| `galaxy/hooks/useTsumegoProblem.ts` | `hooks/useTsumegoProblem.ts` |
| `galaxy/hooks/live/useLiveMatches.ts` | `hooks/live/useLiveMatches.ts` |
| `galaxy/hooks/live/useLiveMatch.ts` | `hooks/live/useLiveMatch.ts` |
| `galaxy/api/live.ts` | `api/live.ts` |
| `galaxy/api/kifuApi.ts` | `api/kifuApi.ts` |
| `galaxy/types/live.ts` | `types/live.ts` |
| `galaxy/types/kifu.ts` | `types/kifu.ts` |
| `galaxy/utils/rankUtils.ts` | `utils/rankUtils.ts` |
| `galaxy/utils/resultTranslation.ts` | `utils/resultTranslation.ts` |
| `galaxy/components/tsumego/MiniBoard.tsx` | `components/MiniBoard.tsx` |

## Kiosk Files Deleted Summary

| File | Replaced By |
|------|-------------|
| `kiosk/context/KioskAuthContext.tsx` | `context/AuthContext.tsx` |
| `kiosk/components/guards/KioskAuthGuard.tsx` | Rewritten to use shared `useAuth()` |
| `kiosk/components/game/MockBoard.tsx` | `components/Board.tsx` |
| `kiosk/components/game/KioskPlayerCard.tsx` | `components/PlayerCard.tsx` |
| `kiosk/components/game/KioskScoreGraph.tsx` | `components/ScoreGraph.tsx` |
| `kiosk/components/game/KioskMiniBoard.tsx` | `components/MiniBoard.tsx` |
| `kiosk/data/mocks.ts` | Real API calls via shared hooks |
