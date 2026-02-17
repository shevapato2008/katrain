# RK3588 Kiosk UI Implementation Plan (Rev 2)

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a touch-optimized kiosk UI for 7-10 inch smart Go board terminals, frontend-first with mock data, parallel to Galaxy web UI.

**Architecture:** New `src/kiosk/` directory with its own theme, layout, and pages. Shares backend API and core types with Galaxy via `src/shared/` (extracted in Phase 3). Single Vite build serves both at different URL prefixes (`/galaxy/*`, `/kiosk/*`). KioskApp wraps itself with its own `ThemeProvider` (nested inside AppRouter's default zenTheme). "Ink Stone" dark theme, NavigationRail (left vertical, 72px) for landscape optimization, mock auth with route guard.

**Tech Stack:** React 19, TypeScript, MUI v7, React Router v6, Vite (rolldown-vite), Vitest, Testing Library, @fontsource (self-hosted fonts)

**Design doc:** `docs/plans/2026-02-17-rk3588-kiosk-ui-design.md`

**Review feedback:**
- `superpowers/tracks/rk3588-ui/review-feedback-codex.md`
- `superpowers/tracks/rk3588-ui/review-feedback-gemini.md`

---

## Changes from Rev 1

| # | Change | Rationale | Source |
|---|--------|-----------|--------|
| 1 | ThemeProvider nested inside KioskApp, not conditional at AppRouter | `window.location.pathname` runs once, not reactive to navigation | Codex P0-1, Gemini #1 |
| 2 | Local fonts via `@fontsource` npm packages, no CDN | Kiosk is offline/LAN; CDN = deployment failure | Codex P0-2 |
| 3 | Smoke tests for ALL page tasks (not just "visual verify") | Strict TDD requirement; regression protection for shared layer refactor | Codex P0-3 |
| 4 | Mock auth context + login page + route guard added | Requirement: "login required on each boot"; omission distorts flow evaluation | Codex P0-4 |
| 5 | Removed global `MuiButton.minHeight: 56` | Over-constrains compact contexts (game control panel 3x2 grid) | Codex P1-1 |
| 6 | Tab matching uses `matchPath` instead of `startsWith` | Prevents false positives (`/kiosk/livewatch` matching `/kiosk/live`) | Codex P1-2, Gemini #5 |
| 7 | BottomTabBar → NavigationRail (left vertical, 72px) | Landscape: saves 64px vertical for board; board area +13% on 1024x600 | Codex P1-3, Gemini #2 |
| 8 | 8 tabs → 6 items (merged AI+PvP into "对弈", 平台 moved to Settings) | Reduces cognitive load; follows Galaxy "Play" menu pattern | Codex P1-3, Gemini #2 |
| 9 | Mock data: fixed fixtures in `kiosk/data/mocks.ts`, no `Math.random()` | Reproducible visual verification and debugging | Codex P1-4, Gemini #4 |
| 10 | Secondary text color `#6b6560` → `#9a9590` | Original: 3.11:1 contrast (fails WCAG AA). New: ~4.7:1 (passes) | Codex review Q4 |
| 11 | Fonts reduced: Serif only for h1 (single weight 700) | Reduce first-screen load and memory on embedded device | Codex P1-6 |
| 12 | React.lazy for GalaxyApp/KioskApp code splitting | Prevent cross-app bundle bloat | Codex P2-3, Gemini #3 |

### Navigation layout comparison (1024x600 display)

| Layout | Chrome overhead | Board size | Panel size |
|--------|----------------|------------|------------|
| Bottom bar (Rev 1) | 40px top + 64px bottom = 104px vertical | 496×496 | 528×496 |
| **Left rail (Rev 2)** | **40px top + 72px left** | **560×560** | **392×560** |

Rail gives +13% board area — significant for a Go application where the board is the primary content.

### Navigation structure (Rev 2)

```
┌─────────────────────────────────────────────┐
│ StatusBar (40px)                            │
├──────┬──────────────────────────────────────┤
│ 对弈 │                                      │
│ 死活 │                                      │
│ 研究 │         Content (Outlet)             │
│ 棋谱 │                                      │
│ 直播 │                                      │
│      │                                      │
│ ──── │                                      │
│ 设置 │                                      │
├──────┴──────────────────────────────────────┤
  72px
```

**Existing code to know about:**
- Entry: `katrain/web/ui/src/main.tsx` → `AppRouter.tsx` → `GalaxyApp.tsx` / `ZenModeApp.tsx`
- Galaxy theme: `katrain/web/ui/src/theme.ts` (MUI dark, Manrope font, jade accents)
- Galaxy layout: `katrain/web/ui/src/galaxy/components/layout/MainLayout.tsx` (240px sidebar + Outlet)
- Shared components: `katrain/web/ui/src/components/Board.tsx`, `ScoreGraph.tsx`, `PlayerCard.tsx`
- Shared hooks: `katrain/web/ui/src/galaxy/hooks/useGameSession.ts` etc.
- Tests run with: `cd katrain/web/ui && npx vitest run <path>`
- Test setup: `src/test/setup.ts` imports `@testing-library/jest-dom`
- Vite config: `katrain/web/ui/vite.config.ts` (proxy `/api` → `:8001`, proxy `/ws` → ws)

---

## Phase 1: Foundation

### Task 1: Kiosk Theme + Local Fonts

**Files:**
- Create: `katrain/web/ui/src/kiosk/theme.ts`
- Create: `katrain/web/ui/src/kiosk/__tests__/theme.test.ts`

**Step 1: Install font packages**

Run: `cd katrain/web/ui && npm install @fontsource/noto-sans-sc @fontsource/noto-serif-sc @fontsource/jetbrains-mono`

**Step 2: Write the failing test**

Create `katrain/web/ui/src/kiosk/__tests__/theme.test.ts`:

```typescript
import { describe, it, expect } from 'vitest';
import { kioskTheme } from '../theme';

describe('kioskTheme', () => {
  it('is dark mode with ink-black background', () => {
    expect(kioskTheme.palette.mode).toBe('dark');
    expect(kioskTheme.palette.background.default).toBe('#1a1714');
  });

  it('uses Noto Sans SC as primary body font', () => {
    expect(kioskTheme.typography.fontFamily).toContain('Noto Sans SC');
  });

  it('uses Noto Serif SC only for h1', () => {
    expect((kioskTheme.typography.h1 as any).fontFamily).toContain('Noto Serif SC');
    // h3+ should use Sans, not Serif
    expect((kioskTheme.typography.h3 as any).fontFamily).toContain('Noto Sans SC');
  });

  it('has jade-glow #5cb57a as primary color', () => {
    expect(kioskTheme.palette.primary.main).toBe('#5cb57a');
  });

  it('has ember #c45d3e as error color', () => {
    expect(kioskTheme.palette.error.main).toBe('#c45d3e');
  });

  it('has secondary text with sufficient contrast (WCAG AA)', () => {
    // #9a9590 on #1a1714 gives ~4.7:1 ratio (AA requires 4.5:1)
    expect(kioskTheme.palette.text.secondary).toBe('#9a9590');
  });

  it('does NOT globally force button minHeight', () => {
    const overrides = kioskTheme.components?.MuiButton?.styleOverrides as any;
    expect(overrides.root.minHeight).toBeUndefined();
  });

  it('enforces 48px min icon button size for touch targets', () => {
    const overrides = kioskTheme.components?.MuiIconButton?.styleOverrides as any;
    expect(overrides.root.minWidth).toBe(48);
    expect(overrides.root.minHeight).toBe(48);
  });
});
```

**Step 3: Run test to verify it fails**

Run: `cd katrain/web/ui && npx vitest run src/kiosk/__tests__/theme.test.ts`
Expected: FAIL with "Cannot find module '../theme'"

**Step 4: Write minimal implementation**

Create `katrain/web/ui/src/kiosk/theme.ts`:

```typescript
import { createTheme } from '@mui/material';

// Self-hosted fonts via @fontsource — no CDN dependency
import '@fontsource/noto-sans-sc/400.css';
import '@fontsource/noto-sans-sc/600.css';
import '@fontsource/noto-sans-sc/700.css';
import '@fontsource/noto-serif-sc/700.css';
import '@fontsource/jetbrains-mono/400.css';
import '@fontsource/jetbrains-mono/500.css';

export const kioskTheme = createTheme({
  palette: {
    mode: 'dark',
    primary: {
      main: '#5cb57a',   // jade-glow
      light: '#7ec994',
      dark: '#2d5a3d',   // jade-deep
    },
    secondary: {
      main: '#8b7355',   // wood-amber
    },
    background: {
      default: '#1a1714', // ink-black
      paper: '#252019',
    },
    text: {
      primary: '#e8e4dc',  // stone-white (14:1 on ink-black)
      secondary: '#9a9590', // mist (~4.7:1 on ink-black, WCAG AA)
      disabled: '#3d3a36',
    },
    divider: 'rgba(232, 228, 220, 0.08)',
    success: { main: '#5cb57a' },
    warning: { main: '#c49a3c' },
    error: { main: '#c45d3e' },    // ember
    info: { main: '#5b9bd5' },
  },
  typography: {
    fontFamily: "'Noto Sans SC', 'Noto Sans', sans-serif",
    fontSize: 16,
    h1: { fontFamily: "'Noto Serif SC', 'Noto Serif', serif", fontWeight: 700 },
    h2: { fontFamily: "'Noto Sans SC', sans-serif", fontWeight: 700 },
    h3: { fontFamily: "'Noto Sans SC', sans-serif", fontWeight: 600 },
    h4: { fontFamily: "'Noto Sans SC', sans-serif", fontWeight: 600 },
    h5: { fontFamily: "'Noto Sans SC', sans-serif", fontWeight: 600 },
    h6: { fontFamily: "'Noto Sans SC', sans-serif", fontWeight: 600 },
    body1: { fontFamily: "'Noto Sans SC', sans-serif", fontSize: 16 },
    body2: { fontFamily: "'Noto Sans SC', sans-serif", fontSize: 14 },
    button: { fontFamily: "'Noto Sans SC', sans-serif", fontWeight: 600 },
    caption: { fontFamily: "'JetBrains Mono', monospace", fontSize: 12 },
  },
  shape: { borderRadius: 12 },
  components: {
    MuiButton: {
      styleOverrides: {
        root: {
          textTransform: 'none' as const,
          borderRadius: '12px',
          padding: '12px 24px',
          fontSize: '1rem',
          transition: 'transform 100ms ease-out, background-color 150ms',
          '&:active': { transform: 'scale(0.96)' },
        },
      },
    },
    MuiIconButton: {
      styleOverrides: {
        root: {
          minWidth: 48,
          minHeight: 48,
          '&:active': { transform: 'scale(0.96)' },
        },
      },
    },
    MuiPaper: {
      styleOverrides: {
        root: { backgroundImage: 'none' },
      },
    },
  },
});
```

**Step 5: Run test to verify it passes**

Run: `cd katrain/web/ui && npx vitest run src/kiosk/__tests__/theme.test.ts`
Expected: 8 tests PASS

**Step 6: Commit**

```bash
git add katrain/web/ui/src/kiosk/theme.ts katrain/web/ui/src/kiosk/__tests__/theme.test.ts katrain/web/ui/package.json katrain/web/ui/package-lock.json
git commit -m "feat(kiosk): add Ink Stone theme with local fonts and WCAG AA contrast"
```

---

### Task 2: Mock Auth Context + Login Page

**Files:**
- Create: `katrain/web/ui/src/kiosk/context/KioskAuthContext.tsx`
- Create: `katrain/web/ui/src/kiosk/components/guards/KioskAuthGuard.tsx`
- Create: `katrain/web/ui/src/kiosk/pages/LoginPage.tsx`
- Create: `katrain/web/ui/src/kiosk/__tests__/KioskAuth.test.tsx`

**Step 1: Write the failing test**

Create `katrain/web/ui/src/kiosk/__tests__/KioskAuth.test.tsx`:

```typescript
import { describe, it, expect } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { ThemeProvider } from '@mui/material';
import { kioskTheme } from '../theme';
import { KioskAuthProvider, useKioskAuth } from '../context/KioskAuthContext';
import KioskAuthGuard from '../components/guards/KioskAuthGuard';
import LoginPage from '../pages/LoginPage';

const renderWithProviders = (ui: React.ReactElement, route = '/kiosk/play') =>
  render(
    <ThemeProvider theme={kioskTheme}>
      <MemoryRouter initialEntries={[route]}>
        <KioskAuthProvider>{ui}</KioskAuthProvider>
      </MemoryRouter>
    </ThemeProvider>
  );

const AuthStatus = () => {
  const { isAuthenticated, user } = useKioskAuth();
  return <div data-testid="auth-status">{isAuthenticated ? user!.name : 'not-auth'}</div>;
};

describe('KioskAuth', () => {
  it('defaults to unauthenticated', () => {
    renderWithProviders(<AuthStatus />);
    expect(screen.getByTestId('auth-status')).toHaveTextContent('not-auth');
  });

  it('auth guard redirects to login when unauthenticated', () => {
    renderWithProviders(
      <Routes>
        <Route path="/kiosk/login" element={<div>LOGIN_PAGE</div>} />
        <Route element={<KioskAuthGuard />}>
          <Route path="/kiosk/play" element={<div>PLAY_PAGE</div>} />
        </Route>
      </Routes>
    );
    expect(screen.getByText('LOGIN_PAGE')).toBeInTheDocument();
    expect(screen.queryByText('PLAY_PAGE')).not.toBeInTheDocument();
  });

  it('login page renders username and PIN inputs', () => {
    renderWithProviders(
      <Routes>
        <Route path="/kiosk/play" element={<LoginPage />} />
      </Routes>,
      '/kiosk/play'
    );
    expect(screen.getByLabelText(/用户名/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/PIN/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /登录/i })).toBeInTheDocument();
  });
});
```

**Step 2: Run test to verify it fails**

Run: `cd katrain/web/ui && npx vitest run src/kiosk/__tests__/KioskAuth.test.tsx`
Expected: FAIL with "Cannot find module"

**Step 3: Create KioskAuthContext**

Create `katrain/web/ui/src/kiosk/context/KioskAuthContext.tsx`:

```typescript
import { createContext, useContext, useState, type ReactNode } from 'react';

interface KioskUser {
  name: string;
  rank: string;
}

interface KioskAuthState {
  isAuthenticated: boolean;
  user: KioskUser | null;
  login: (username: string, pin: string) => void;
  logout: () => void;
}

const KioskAuthContext = createContext<KioskAuthState | null>(null);

export const useKioskAuth = () => {
  const ctx = useContext(KioskAuthContext);
  if (!ctx) throw new Error('useKioskAuth must be used within KioskAuthProvider');
  return ctx;
};

export const KioskAuthProvider = ({ children }: { children: ReactNode }) => {
  const [user, setUser] = useState<KioskUser | null>(null);

  const login = (username: string, _pin: string) => {
    // Mock auth: always succeeds. Real auth integrated in Phase 4.
    setUser({ name: username || '棋手', rank: '1D' });
  };

  const logout = () => setUser(null);

  return (
    <KioskAuthContext.Provider value={{ isAuthenticated: !!user, user, login, logout }}>
      {children}
    </KioskAuthContext.Provider>
  );
};
```

**Step 4: Create KioskAuthGuard**

Create `katrain/web/ui/src/kiosk/components/guards/KioskAuthGuard.tsx`:

```typescript
import { Navigate, Outlet } from 'react-router-dom';
import { useKioskAuth } from '../../context/KioskAuthContext';

const KioskAuthGuard = () => {
  const { isAuthenticated } = useKioskAuth();
  if (!isAuthenticated) return <Navigate to="/kiosk/login" replace />;
  return <Outlet />;
};

export default KioskAuthGuard;
```

**Step 5: Create LoginPage**

Create `katrain/web/ui/src/kiosk/pages/LoginPage.tsx`:

```typescript
import { useState } from 'react';
import { Box, Typography, TextField, Button } from '@mui/material';
import { useNavigate } from 'react-router-dom';
import { useKioskAuth } from '../context/KioskAuthContext';

const LoginPage = () => {
  const [username, setUsername] = useState('');
  const [pin, setPin] = useState('');
  const { login } = useKioskAuth();
  const navigate = useNavigate();

  const handleLogin = () => {
    login(username, pin);
    navigate('/kiosk/play', { replace: true });
  };

  return (
    <Box
      sx={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        height: '100vh',
        bgcolor: 'background.default',
      }}
    >
      <Box sx={{ width: 360, display: 'flex', flexDirection: 'column', gap: 3 }}>
        <Typography variant="h4" sx={{ textAlign: 'center', color: 'primary.main', fontWeight: 700 }}>
          KaTrain
        </Typography>
        <TextField
          label="用户名"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          fullWidth
          autoFocus
        />
        <TextField
          label="PIN"
          type="password"
          value={pin}
          onChange={(e) => setPin(e.target.value)}
          fullWidth
        />
        <Button
          variant="contained"
          onClick={handleLogin}
          fullWidth
          sx={{ minHeight: 56, fontSize: '1.1rem' }}
        >
          登录
        </Button>
      </Box>
    </Box>
  );
};

export default LoginPage;
```

**Step 6: Run test to verify it passes**

Run: `cd katrain/web/ui && npx vitest run src/kiosk/__tests__/KioskAuth.test.tsx`
Expected: 3 tests PASS

**Step 7: Commit**

```bash
git add katrain/web/ui/src/kiosk/context/ katrain/web/ui/src/kiosk/components/guards/ katrain/web/ui/src/kiosk/pages/LoginPage.tsx katrain/web/ui/src/kiosk/__tests__/KioskAuth.test.tsx
git commit -m "feat(kiosk): add mock auth context, login page, and route guard"
```

---

## Phase 2: Layout Shell

### Task 3: StatusBar Component

**Files:**
- Create: `katrain/web/ui/src/kiosk/components/layout/StatusBar.tsx`
- Create: `katrain/web/ui/src/kiosk/__tests__/StatusBar.test.tsx`

**Step 1: Write the failing test**

Create `katrain/web/ui/src/kiosk/__tests__/StatusBar.test.tsx`:

```typescript
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ThemeProvider } from '@mui/material';
import { kioskTheme } from '../theme';
import StatusBar from '../components/layout/StatusBar';

const renderWithTheme = (ui: React.ReactElement) =>
  render(<ThemeProvider theme={kioskTheme}>{ui}</ThemeProvider>);

describe('StatusBar', () => {
  it('renders KaTrain branding', () => {
    renderWithTheme(<StatusBar username="张三" />);
    expect(screen.getByText('KaTrain')).toBeInTheDocument();
  });

  it('renders engine status indicator', () => {
    renderWithTheme(<StatusBar username="张三" />);
    expect(screen.getByTestId('engine-status')).toBeInTheDocument();
  });

  it('renders username', () => {
    renderWithTheme(<StatusBar username="张三" />);
    expect(screen.getByText('张三')).toBeInTheDocument();
  });

  it('renders current time', () => {
    renderWithTheme(<StatusBar username="张三" />);
    expect(screen.getByTestId('clock')).toBeInTheDocument();
  });
});
```

**Step 2: Run test to verify it fails**

Run: `cd katrain/web/ui && npx vitest run src/kiosk/__tests__/StatusBar.test.tsx`
Expected: FAIL with "Cannot find module"

**Step 3: Write minimal implementation**

Create `katrain/web/ui/src/kiosk/components/layout/StatusBar.tsx`:

```typescript
import { Box, Typography } from '@mui/material';

interface StatusBarProps {
  username?: string;
}

const StatusBar = ({ username }: StatusBarProps) => {
  return (
    <Box
      sx={{
        height: 40,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        px: 2,
        borderBottom: '1px solid',
        borderColor: 'divider',
        bgcolor: 'background.default',
        flexShrink: 0,
      }}
    >
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
        <Typography variant="body2" sx={{ fontWeight: 700, color: 'primary.main' }}>
          KaTrain
        </Typography>
        <Box
          data-testid="engine-status"
          sx={{ width: 6, height: 6, borderRadius: '50%', bgcolor: 'success.main' }}
        />
      </Box>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
        {username && (
          <Typography variant="body2" sx={{ color: 'text.secondary' }}>
            {username}
          </Typography>
        )}
        <Typography
          data-testid="clock"
          variant="caption"
          sx={{ color: 'text.secondary' }}
        >
          {new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
        </Typography>
      </Box>
    </Box>
  );
};

export default StatusBar;
```

**Step 4: Run test to verify it passes**

Run: `cd katrain/web/ui && npx vitest run src/kiosk/__tests__/StatusBar.test.tsx`
Expected: 4 tests PASS

**Step 5: Commit**

```bash
git add katrain/web/ui/src/kiosk/components/layout/StatusBar.tsx katrain/web/ui/src/kiosk/__tests__/StatusBar.test.tsx
git commit -m "feat(kiosk): add StatusBar with branding, engine status, user, clock"
```

---

### Task 4: NavigationRail Component

**Files:**
- Create: `katrain/web/ui/src/kiosk/components/layout/NavigationRail.tsx`
- Create: `katrain/web/ui/src/kiosk/__tests__/NavigationRail.test.tsx`

**Step 1: Write the failing test**

Create `katrain/web/ui/src/kiosk/__tests__/NavigationRail.test.tsx`:

```typescript
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { ThemeProvider } from '@mui/material';
import { kioskTheme } from '../theme';
import NavigationRail from '../components/layout/NavigationRail';

const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return { ...actual, useNavigate: () => mockNavigate };
});

const renderWithProviders = (ui: React.ReactElement, route = '/kiosk/play') =>
  render(
    <ThemeProvider theme={kioskTheme}>
      <MemoryRouter initialEntries={[route]}>{ui}</MemoryRouter>
    </ThemeProvider>
  );

describe('NavigationRail', () => {
  it('renders all 6 navigation labels', () => {
    renderWithProviders(<NavigationRail />);
    ['对弈', '死活', '研究', '棋谱', '直播', '设置'].forEach((label) => {
      expect(screen.getByText(label)).toBeInTheDocument();
    });
  });

  it('highlights active item based on current route using matchPath', () => {
    renderWithProviders(<NavigationRail />, '/kiosk/tsumego/problem/123');
    const tsumegoItem = screen.getByText('死活').closest('button');
    expect(tsumegoItem).toHaveAttribute('data-active', 'true');
  });

  it('does not false-match similar route prefixes', () => {
    renderWithProviders(<NavigationRail />, '/kiosk/live');
    const liveItem = screen.getByText('直播').closest('button');
    expect(liveItem).toHaveAttribute('data-active', 'true');
    const kifuItem = screen.getByText('棋谱').closest('button');
    expect(kifuItem).toHaveAttribute('data-active', 'false');
  });

  it('navigates on item click', () => {
    renderWithProviders(<NavigationRail />);
    fireEvent.click(screen.getByText('死活'));
    expect(mockNavigate).toHaveBeenCalledWith('/kiosk/tsumego');
  });

  it('settings item is visually separated at the bottom', () => {
    renderWithProviders(<NavigationRail />);
    const settingsItem = screen.getByText('设置').closest('button');
    expect(settingsItem).toHaveAttribute('data-section', 'footer');
  });
});
```

**Step 2: Run test to verify it fails**

Run: `cd katrain/web/ui && npx vitest run src/kiosk/__tests__/NavigationRail.test.tsx`
Expected: FAIL with "Cannot find module"

**Step 3: Write minimal implementation**

Create `katrain/web/ui/src/kiosk/components/layout/NavigationRail.tsx`:

```typescript
import { Box, ButtonBase, Typography } from '@mui/material';
import {
  SportsEsports as PlayIcon,
  Extension as TsumegoIcon,
  Science as ResearchIcon,
  MenuBook as KifuIcon,
  LiveTv as LiveIcon,
  Settings as SettingsIcon,
} from '@mui/icons-material';
import { useNavigate, useLocation, matchPath } from 'react-router-dom';

const primaryTabs = [
  { label: '对弈', icon: <PlayIcon />, path: '/kiosk/play', pattern: '/kiosk/play/*' },
  { label: '死活', icon: <TsumegoIcon />, path: '/kiosk/tsumego', pattern: '/kiosk/tsumego/*' },
  { label: '研究', icon: <ResearchIcon />, path: '/kiosk/research', pattern: '/kiosk/research' },
  { label: '棋谱', icon: <KifuIcon />, path: '/kiosk/kifu', pattern: '/kiosk/kifu/*' },
  { label: '直播', icon: <LiveIcon />, path: '/kiosk/live', pattern: '/kiosk/live/*' },
];

const settingsTab = { label: '设置', icon: <SettingsIcon />, path: '/kiosk/settings', pattern: '/kiosk/settings' };

const NavigationRail = () => {
  const navigate = useNavigate();
  const location = useLocation();

  const isActive = (pattern: string) => !!matchPath(pattern, location.pathname);

  const renderItem = (tab: typeof primaryTabs[0], section: 'main' | 'footer') => {
    const active = isActive(tab.pattern);
    return (
      <ButtonBase
        key={tab.path}
        onClick={() => navigate(tab.path)}
        data-active={active}
        data-section={section}
        sx={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          gap: 0.5,
          py: 1.5,
          width: '100%',
          borderRadius: 1,
          color: active ? 'primary.main' : 'text.secondary',
          bgcolor: active ? 'rgba(92, 181, 122, 0.08)' : 'transparent',
          transition: 'all 150ms ease-out',
          '&:active': { transform: 'scale(0.94)' },
        }}
      >
        <Box sx={{ fontSize: 22, display: 'flex' }}>{tab.icon}</Box>
        <Typography variant="caption" sx={{ fontSize: 11, lineHeight: 1, fontFamily: "'Noto Sans SC', sans-serif" }}>
          {tab.label}
        </Typography>
      </ButtonBase>
    );
  };

  return (
    <Box
      component="nav"
      sx={{
        width: 72,
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        py: 1,
        px: 0.5,
        gap: 0.5,
        borderRight: '1px solid',
        borderColor: 'divider',
        bgcolor: 'background.default',
        flexShrink: 0,
      }}
    >
      {primaryTabs.map((tab) => renderItem(tab, 'main'))}
      <Box sx={{ mt: 'auto' }} />
      <Box sx={{ width: '80%', height: '1px', bgcolor: 'divider', my: 0.5 }} />
      {renderItem(settingsTab, 'footer')}
    </Box>
  );
};

export default NavigationRail;
```

**Step 4: Run test to verify it passes**

Run: `cd katrain/web/ui && npx vitest run src/kiosk/__tests__/NavigationRail.test.tsx`
Expected: 5 tests PASS

**Step 5: Commit**

```bash
git add katrain/web/ui/src/kiosk/components/layout/NavigationRail.tsx katrain/web/ui/src/kiosk/__tests__/NavigationRail.test.tsx
git commit -m "feat(kiosk): add NavigationRail with matchPath routing and 6 items"
```

---

### Task 5: KioskLayout Shell

**Files:**
- Create: `katrain/web/ui/src/kiosk/components/layout/KioskLayout.tsx`
- Create: `katrain/web/ui/src/kiosk/__tests__/KioskLayout.test.tsx`

**Step 1: Write the failing test**

Create `katrain/web/ui/src/kiosk/__tests__/KioskLayout.test.tsx`:

```typescript
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { ThemeProvider } from '@mui/material';
import { kioskTheme } from '../theme';
import KioskLayout from '../components/layout/KioskLayout';

describe('KioskLayout', () => {
  it('renders status bar, navigation rail, and outlet content', () => {
    render(
      <ThemeProvider theme={kioskTheme}>
        <MemoryRouter initialEntries={['/kiosk/play']}>
          <Routes>
            <Route element={<KioskLayout username="张三" />}>
              <Route path="/kiosk/play" element={<div>PLAY_CONTENT</div>} />
            </Route>
          </Routes>
        </MemoryRouter>
      </ThemeProvider>
    );
    // StatusBar
    expect(screen.getByText('KaTrain')).toBeInTheDocument();
    // NavigationRail
    expect(screen.getByText('对弈')).toBeInTheDocument();
    expect(screen.getByText('设置')).toBeInTheDocument();
    // Outlet
    expect(screen.getByText('PLAY_CONTENT')).toBeInTheDocument();
  });
});
```

**Step 2: Run test to verify it fails**

Run: `cd katrain/web/ui && npx vitest run src/kiosk/__tests__/KioskLayout.test.tsx`
Expected: FAIL

**Step 3: Write minimal implementation**

Create `katrain/web/ui/src/kiosk/components/layout/KioskLayout.tsx`:

```typescript
import { Box } from '@mui/material';
import { Outlet } from 'react-router-dom';
import StatusBar from './StatusBar';
import NavigationRail from './NavigationRail';

interface KioskLayoutProps {
  username?: string;
}

const KioskLayout = ({ username }: KioskLayoutProps) => {
  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        height: '100vh',
        width: '100vw',
        overflow: 'hidden',
        bgcolor: 'background.default',
      }}
    >
      <StatusBar username={username} />
      <Box sx={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
        <NavigationRail />
        <Box
          component="main"
          sx={{ flex: 1, overflow: 'auto', display: 'flex', flexDirection: 'column' }}
        >
          <Outlet />
        </Box>
      </Box>
    </Box>
  );
};

export default KioskLayout;
```

**Step 4: Run test to verify it passes**

Run: `cd katrain/web/ui && npx vitest run src/kiosk/__tests__/KioskLayout.test.tsx`
Expected: 1 test PASS

**Step 5: Commit**

```bash
git add katrain/web/ui/src/kiosk/components/layout/KioskLayout.tsx katrain/web/ui/src/kiosk/__tests__/KioskLayout.test.tsx
git commit -m "feat(kiosk): add KioskLayout composing StatusBar + NavigationRail + Outlet"
```

---

### Task 6: KioskApp and Wire into AppRouter

**Files:**
- Create: `katrain/web/ui/src/kiosk/KioskApp.tsx`
- Create: `katrain/web/ui/src/kiosk/pages/PlaceholderPage.tsx`
- Modify: `katrain/web/ui/src/AppRouter.tsx`
- Create: `katrain/web/ui/src/kiosk/__tests__/KioskApp.test.tsx`

**Step 1: Write the failing test**

Create `katrain/web/ui/src/kiosk/__tests__/KioskApp.test.tsx`:

```typescript
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import KioskApp from '../KioskApp';

describe('KioskApp', () => {
  it('renders login page when not authenticated', () => {
    render(
      <MemoryRouter initialEntries={['/kiosk/play']}>
        <KioskApp />
      </MemoryRouter>
    );
    // Auth guard redirects to login
    expect(screen.getByRole('button', { name: /登录/i })).toBeInTheDocument();
  });

  it('renders nav rail on authenticated route', () => {
    render(
      <MemoryRouter initialEntries={['/kiosk/play']}>
        <KioskApp />
      </MemoryRouter>
    );
    // Login first
    const usernameInput = screen.getByLabelText(/用户名/i);
    const loginBtn = screen.getByRole('button', { name: /登录/i });
    const { fireEvent } = require('@testing-library/react');
    fireEvent.change(usernameInput, { target: { value: '张三' } });
    fireEvent.click(loginBtn);
    // After login, nav rail visible
    expect(screen.getByText('对弈')).toBeInTheDocument();
    expect(screen.getByText('KaTrain')).toBeInTheDocument();
  });

  it('redirects /kiosk to /kiosk/play', () => {
    render(
      <MemoryRouter initialEntries={['/kiosk']}>
        <KioskApp />
      </MemoryRouter>
    );
    // Should redirect to login (which then redirects to play after auth)
    expect(screen.getByRole('button', { name: /登录/i })).toBeInTheDocument();
  });
});
```

**Step 2: Run test to verify it fails**

Run: `cd katrain/web/ui && npx vitest run src/kiosk/__tests__/KioskApp.test.tsx`
Expected: FAIL

**Step 3: Create PlaceholderPage**

Create `katrain/web/ui/src/kiosk/pages/PlaceholderPage.tsx`:

```typescript
import { Box, Typography } from '@mui/material';
import { useLocation } from 'react-router-dom';

const PlaceholderPage = () => {
  const location = useLocation();
  const segment = location.pathname.split('/').filter(Boolean).pop() || 'home';

  return (
    <Box
      sx={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        height: '100%',
        flexDirection: 'column',
        gap: 2,
      }}
    >
      <Typography variant="h3" sx={{ color: 'text.secondary', opacity: 0.3 }}>
        {segment.toUpperCase()}
      </Typography>
      <Typography variant="body2" sx={{ color: 'text.secondary' }}>
        Coming soon
      </Typography>
    </Box>
  );
};

export default PlaceholderPage;
```

**Step 4: Create KioskApp**

Create `katrain/web/ui/src/kiosk/KioskApp.tsx`:

```typescript
import { Routes, Route, Navigate } from 'react-router-dom';
import { ThemeProvider, CssBaseline } from '@mui/material';
import { kioskTheme } from './theme';
import { KioskAuthProvider, useKioskAuth } from './context/KioskAuthContext';
import KioskAuthGuard from './components/guards/KioskAuthGuard';
import KioskLayout from './components/layout/KioskLayout';
import LoginPage from './pages/LoginPage';
import PlaceholderPage from './pages/PlaceholderPage';

const KioskRoutes = () => {
  const { user } = useKioskAuth();

  return (
    <Routes>
      {/* Public */}
      <Route path="login" element={<LoginPage />} />

      {/* Auth-protected */}
      <Route element={<KioskAuthGuard />}>
        {/* Fullscreen — no nav rail (added in Task 12) */}

        {/* Standard — with nav rail */}
        <Route element={<KioskLayout username={user?.name} />}>
          <Route index element={<Navigate to="play" replace />} />
          <Route path="play" element={<PlaceholderPage />} />
          <Route path="play/ai/setup/:mode" element={<PlaceholderPage />} />
          <Route path="play/pvp/setup" element={<PlaceholderPage />} />
          <Route path="tsumego" element={<PlaceholderPage />} />
          <Route path="tsumego/problem/:problemId" element={<PlaceholderPage />} />
          <Route path="research" element={<PlaceholderPage />} />
          <Route path="kifu" element={<PlaceholderPage />} />
          <Route path="live" element={<PlaceholderPage />} />
          <Route path="live/:matchId" element={<PlaceholderPage />} />
          <Route path="settings" element={<PlaceholderPage />} />
          <Route path="*" element={<Navigate to="play" replace />} />
        </Route>
      </Route>
    </Routes>
  );
};

const KioskApp = () => (
  <ThemeProvider theme={kioskTheme}>
    <CssBaseline />
    <KioskAuthProvider>
      <KioskRoutes />
    </KioskAuthProvider>
  </ThemeProvider>
);

export default KioskApp;
```

**Step 5: Modify AppRouter.tsx**

Replace `katrain/web/ui/src/AppRouter.tsx` with:

```typescript
import { lazy, Suspense } from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { ThemeProvider, CssBaseline } from '@mui/material';
import { zenTheme } from './theme';
import ZenModeApp from './ZenModeApp';

// Code-split: kiosk and galaxy bundles load independently
const GalaxyApp = lazy(() => import('./GalaxyApp'));
const KioskApp = lazy(() => import('./kiosk/KioskApp'));

const AppRouter = () => {
  return (
    <ThemeProvider theme={zenTheme}>
      <CssBaseline />
      <BrowserRouter>
        <Suspense fallback={null}>
          <Routes>
            <Route path="/kiosk/*" element={<KioskApp />} />
            <Route path="/galaxy/*" element={<GalaxyApp />} />
            <Route path="/*" element={<ZenModeApp />} />
          </Routes>
        </Suspense>
      </BrowserRouter>
    </ThemeProvider>
  );
};

export default AppRouter;
```

Note: AppRouter keeps a default `ThemeProvider` with `zenTheme` (for Galaxy and ZenMode). KioskApp nests its own `ThemeProvider` with `kioskTheme`, which overrides the parent. This is reactive — MUI's nested ThemeProvider applies whenever the KioskApp route is active.

**Step 6: Run test to verify it passes**

Run: `cd katrain/web/ui && npx vitest run src/kiosk/__tests__/KioskApp.test.tsx`
Expected: 3 tests PASS

**Step 7: Run ALL kiosk tests to make sure nothing broke**

Run: `cd katrain/web/ui && npx vitest run src/kiosk/`
Expected: All tests PASS (theme: 8, StatusBar: 4, NavigationRail: 5, KioskLayout: 1, Auth: 3, KioskApp: 3)

**Step 8: Verify visually in browser**

Run: `cd katrain/web/ui && npm run dev`
Visit: `http://localhost:5173/kiosk/`
Expected: Login page with ink-black background, KaTrain heading, username/PIN inputs, green login button. After login: NavigationRail on left (72px, 6 items), StatusBar at top, placeholder in center. Galaxy at `/galaxy/` still works unchanged.

**Step 9: Commit**

```bash
git add katrain/web/ui/src/kiosk/ katrain/web/ui/src/AppRouter.tsx
git commit -m "feat(kiosk): wire KioskApp into AppRouter with auth, nav rail, and code splitting"
```

---

## Phase 3: Reusable Components

### Task 7: ModeCard Component

**Files:**
- Create: `katrain/web/ui/src/kiosk/components/common/ModeCard.tsx`
- Create: `katrain/web/ui/src/kiosk/__tests__/ModeCard.test.tsx`

**Step 1: Write the failing test**

Create `katrain/web/ui/src/kiosk/__tests__/ModeCard.test.tsx`:

```typescript
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { ThemeProvider } from '@mui/material';
import { SportsEsports } from '@mui/icons-material';
import { kioskTheme } from '../theme';
import ModeCard from '../components/common/ModeCard';

const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return { ...actual, useNavigate: () => mockNavigate };
});

const renderCard = () =>
  render(
    <ThemeProvider theme={kioskTheme}>
      <MemoryRouter>
        <ModeCard
          title="自由对弈"
          subtitle="随意选择AI强度"
          icon={<SportsEsports />}
          to="/kiosk/play/ai/setup/free"
        />
      </MemoryRouter>
    </ThemeProvider>
  );

describe('ModeCard', () => {
  it('renders title and subtitle', () => {
    renderCard();
    expect(screen.getByText('自由对弈')).toBeInTheDocument();
    expect(screen.getByText('随意选择AI强度')).toBeInTheDocument();
  });

  it('navigates to target on click', () => {
    renderCard();
    fireEvent.click(screen.getByText('自由对弈'));
    expect(mockNavigate).toHaveBeenCalledWith('/kiosk/play/ai/setup/free');
  });
});
```

**Step 2: Run test to verify it fails**

Run: `cd katrain/web/ui && npx vitest run src/kiosk/__tests__/ModeCard.test.tsx`
Expected: FAIL

**Step 3: Write minimal implementation**

Create `katrain/web/ui/src/kiosk/components/common/ModeCard.tsx`:

```typescript
import { Box, Typography, ButtonBase } from '@mui/material';
import { useNavigate } from 'react-router-dom';

interface ModeCardProps {
  title: string;
  subtitle: string;
  icon: React.ReactNode;
  to: string;
}

const ModeCard = ({ title, subtitle, icon, to }: ModeCardProps) => {
  const navigate = useNavigate();

  return (
    <ButtonBase
      onClick={() => navigate(to)}
      sx={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 2,
        flex: 1,
        minHeight: 200,
        borderRadius: 3,
        bgcolor: 'background.paper',
        border: '1px solid',
        borderColor: 'divider',
        p: 3,
        transition: 'transform 100ms ease-out, border-color 200ms',
        '&:active': {
          transform: 'scale(0.96)',
          borderColor: 'primary.main',
        },
      }}
    >
      <Box sx={{ fontSize: 48, color: 'primary.main', display: 'flex' }}>{icon}</Box>
      <Typography variant="h4" sx={{ color: 'text.primary' }}>{title}</Typography>
      <Typography variant="body2" sx={{ color: 'text.secondary', textAlign: 'center' }}>
        {subtitle}
      </Typography>
    </ButtonBase>
  );
};

export default ModeCard;
```

**Step 4: Run test to verify it passes**

Run: `cd katrain/web/ui && npx vitest run src/kiosk/__tests__/ModeCard.test.tsx`
Expected: 2 tests PASS

**Step 5: Commit**

```bash
git add katrain/web/ui/src/kiosk/components/common/ModeCard.tsx katrain/web/ui/src/kiosk/__tests__/ModeCard.test.tsx
git commit -m "feat(kiosk): add ModeCard reusable touch-friendly card component"
```

---

### Task 8: OptionChips Component

**Files:**
- Create: `katrain/web/ui/src/kiosk/components/common/OptionChips.tsx`
- Create: `katrain/web/ui/src/kiosk/__tests__/OptionChips.test.tsx`

**Step 1: Write the failing test**

Create `katrain/web/ui/src/kiosk/__tests__/OptionChips.test.tsx`:

```typescript
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { ThemeProvider } from '@mui/material';
import { kioskTheme } from '../theme';
import OptionChips from '../components/common/OptionChips';

describe('OptionChips', () => {
  it('renders label and all options', () => {
    render(
      <ThemeProvider theme={kioskTheme}>
        <OptionChips
          label="棋盘"
          options={[
            { value: 9, label: '9路' },
            { value: 13, label: '13路' },
            { value: 19, label: '19路' },
          ]}
          value={19}
          onChange={() => {}}
        />
      </ThemeProvider>
    );
    expect(screen.getByText('棋盘')).toBeInTheDocument();
    expect(screen.getByText('9路')).toBeInTheDocument();
    expect(screen.getByText('13路')).toBeInTheDocument();
    expect(screen.getByText('19路')).toBeInTheDocument();
  });

  it('calls onChange when an option is clicked', () => {
    const onChange = vi.fn();
    render(
      <ThemeProvider theme={kioskTheme}>
        <OptionChips
          label="棋盘"
          options={[
            { value: 9, label: '9路' },
            { value: 19, label: '19路' },
          ]}
          value={19}
          onChange={onChange}
        />
      </ThemeProvider>
    );
    fireEvent.click(screen.getByText('9路'));
    expect(onChange).toHaveBeenCalledWith(9);
  });
});
```

**Step 2: Run test to verify it fails**

Run: `cd katrain/web/ui && npx vitest run src/kiosk/__tests__/OptionChips.test.tsx`
Expected: FAIL

**Step 3: Write minimal implementation**

Create `katrain/web/ui/src/kiosk/components/common/OptionChips.tsx`:

```typescript
import { Box, ButtonBase, Typography } from '@mui/material';

interface OptionChipsProps<T extends string | number> {
  label: string;
  options: { value: T; label: string }[];
  value: T;
  onChange: (value: T) => void;
}

function OptionChips<T extends string | number>({
  label,
  options,
  value,
  onChange,
}: OptionChipsProps<T>) {
  return (
    <Box sx={{ mb: 2.5 }}>
      <Typography variant="body2" sx={{ color: 'text.secondary', mb: 1 }}>
        {label}
      </Typography>
      <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
        {options.map((opt) => (
          <ButtonBase
            key={String(opt.value)}
            onClick={() => onChange(opt.value)}
            sx={{
              minWidth: 64,
              minHeight: 48,
              px: 2,
              borderRadius: 2,
              bgcolor: value === opt.value ? 'primary.dark' : 'background.paper',
              border: '1px solid',
              borderColor: value === opt.value ? 'primary.main' : 'divider',
              transition: 'all 100ms ease-out',
              '&:active': { transform: 'scale(0.96)' },
            }}
          >
            <Typography
              variant="body1"
              sx={{
                fontWeight: value === opt.value ? 600 : 400,
                color: value === opt.value ? 'primary.main' : 'text.primary',
              }}
            >
              {opt.label}
            </Typography>
          </ButtonBase>
        ))}
      </Box>
    </Box>
  );
}

export default OptionChips;
```

**Step 4: Run test to verify it passes**

Run: `cd katrain/web/ui && npx vitest run src/kiosk/__tests__/OptionChips.test.tsx`
Expected: 2 tests PASS

**Step 5: Commit**

```bash
git add katrain/web/ui/src/kiosk/components/common/OptionChips.tsx katrain/web/ui/src/kiosk/__tests__/OptionChips.test.tsx
git commit -m "feat(kiosk): add OptionChips touch-friendly selector component"
```

---

## Phase 4: Pages

### Task 9: Mock Data Fixtures + Play Selection Page

**Files:**
- Create: `katrain/web/ui/src/kiosk/data/mocks.ts`
- Create: `katrain/web/ui/src/kiosk/pages/PlayPage.tsx`
- Create: `katrain/web/ui/src/kiosk/__tests__/PlayPage.test.tsx`
- Modify: `katrain/web/ui/src/kiosk/KioskApp.tsx` (swap placeholder)

**Step 1: Create mock data fixtures**

Create `katrain/web/ui/src/kiosk/data/mocks.ts`:

```typescript
// Fixed mock data — deterministic, no Math.random(). Used across all kiosk pages.

export const mockGameState = {
  blackPlayer: '张三 (2D)',
  whitePlayer: 'KataGo 5D',
  blackCaptures: 3,
  whiteCaptures: 5,
  winRate: 56.3,
  bestMove: 'R16',
  bestMoveProb: 94.2,
  altMove: 'Q3',
  altMoveProb: 3.1,
  moveNumber: 42,
};

export const mockTsumegoProblems = [
  { id: 'beginner-1', label: '入门 1', level: '入门', solved: true },
  { id: 'beginner-2', label: '入门 2', level: '入门', solved: true },
  { id: 'beginner-3', label: '入门 3', level: '入门', solved: false },
  { id: 'beginner-4', label: '入门 4', level: '入门', solved: false },
  { id: 'elementary-1', label: '初级 1', level: '初级', solved: true },
  { id: 'elementary-2', label: '初级 2', level: '初级', solved: false },
  { id: 'elementary-3', label: '初级 3', level: '初级', solved: false },
  { id: 'elementary-4', label: '初级 4', level: '初级', solved: false },
  { id: 'intermediate-1', label: '中级 1', level: '中级', solved: false },
  { id: 'intermediate-2', label: '中级 2', level: '中级', solved: false },
  { id: 'advanced-1', label: '高级 1', level: '高级', solved: false },
  { id: 'advanced-2', label: '高级 2', level: '高级', solved: false },
];

export const mockKifuList = [
  { id: 'kifu-1', black: '柯洁 九段', white: '申真谞 九段', event: '2024 LG杯决赛', result: 'W+R' },
  { id: 'kifu-2', black: '李昌镐 九段', white: '曹薰铉 九段', event: '第18届三星杯', result: 'B+3.5' },
  { id: 'kifu-3', black: '张三 2D', white: 'KataGo 5D', event: '自由对弈', result: 'W+12.5' },
];

export const mockLiveMatches = [
  { id: 'live-1', black: '柯洁 九段', white: '朴廷桓 九段', event: '春兰杯半决赛', move: 127, status: 'live' as const },
  { id: 'live-2', black: '申真谞 九段', white: '芝野虎丸 九段', event: '应氏杯四分之一决赛', move: 89, status: 'live' as const },
  { id: 'live-3', black: '一力辽 九段', white: '卞相壹 九段', event: 'LG杯八强', move: 0, status: 'upcoming' as const },
];
```

**Step 2: Write the failing test for PlayPage**

Create `katrain/web/ui/src/kiosk/__tests__/PlayPage.test.tsx`:

```typescript
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { ThemeProvider } from '@mui/material';
import { kioskTheme } from '../theme';
import PlayPage from '../pages/PlayPage';

const renderPage = () =>
  render(
    <ThemeProvider theme={kioskTheme}>
      <MemoryRouter>
        <PlayPage />
      </MemoryRouter>
    </ThemeProvider>
  );

describe('PlayPage', () => {
  it('renders all 4 play mode cards', () => {
    renderPage();
    expect(screen.getByText('自由对弈')).toBeInTheDocument();
    expect(screen.getByText('升降级对弈')).toBeInTheDocument();
    expect(screen.getByText('本地对局')).toBeInTheDocument();
    expect(screen.getByText('在线大厅')).toBeInTheDocument();
  });

  it('separates AI and PvP sections with headers', () => {
    renderPage();
    expect(screen.getByText('人机对弈')).toBeInTheDocument();
    expect(screen.getByText('人人对弈')).toBeInTheDocument();
  });
});
```

**Step 3: Run test to verify it fails**

Run: `cd katrain/web/ui && npx vitest run src/kiosk/__tests__/PlayPage.test.tsx`
Expected: FAIL

**Step 4: Create PlayPage**

Create `katrain/web/ui/src/kiosk/pages/PlayPage.tsx`:

```typescript
import { Box, Typography } from '@mui/material';
import { SportsEsports, EmojiEvents, Handshake, Public } from '@mui/icons-material';
import ModeCard from '../components/common/ModeCard';

const PlayPage = () => {
  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3, p: 3, height: '100%', overflow: 'auto' }}>
      <Typography variant="h5" sx={{ color: 'text.secondary' }}>人机对弈</Typography>
      <Box sx={{ display: 'flex', gap: 3, flex: 1 }}>
        <ModeCard
          title="自由对弈"
          subtitle="随意选择AI强度和棋盘设置"
          icon={<SportsEsports fontSize="inherit" />}
          to="/kiosk/play/ai/setup/free"
        />
        <ModeCard
          title="升降级对弈"
          subtitle="根据实力自动匹配AI难度"
          icon={<EmojiEvents fontSize="inherit" />}
          to="/kiosk/play/ai/setup/ranked"
        />
      </Box>
      <Typography variant="h5" sx={{ color: 'text.secondary' }}>人人对弈</Typography>
      <Box sx={{ display: 'flex', gap: 3, flex: 1 }}>
        <ModeCard
          title="本地对局"
          subtitle="两人在智能棋盘上面对面对弈"
          icon={<Handshake fontSize="inherit" />}
          to="/kiosk/play/pvp/setup"
        />
        <ModeCard
          title="在线大厅"
          subtitle="匹配网络上的对手进行对弈"
          icon={<Public fontSize="inherit" />}
          to="/kiosk/play/pvp/lobby"
        />
      </Box>
    </Box>
  );
};

export default PlayPage;
```

**Step 5: Wire route in KioskApp.tsx**

In `katrain/web/ui/src/kiosk/KioskApp.tsx`, add import and replace route:

```typescript
import PlayPage from './pages/PlayPage';
// ...
<Route path="play" element={<PlayPage />} />
```

**Step 6: Run test to verify it passes**

Run: `cd katrain/web/ui && npx vitest run src/kiosk/__tests__/PlayPage.test.tsx`
Expected: 2 tests PASS

**Step 7: Commit**

```bash
git add katrain/web/ui/src/kiosk/data/mocks.ts katrain/web/ui/src/kiosk/pages/PlayPage.tsx katrain/web/ui/src/kiosk/__tests__/PlayPage.test.tsx katrain/web/ui/src/kiosk/KioskApp.tsx
git commit -m "feat(kiosk): add PlayPage with unified AI/PvP selection and mock data fixtures"
```

---

### Task 10: AI Game Setup Page

**Files:**
- Create: `katrain/web/ui/src/kiosk/pages/AiSetupPage.tsx`
- Create: `katrain/web/ui/src/kiosk/__tests__/AiSetupPage.test.tsx`
- Modify: `katrain/web/ui/src/kiosk/KioskApp.tsx`

**Step 1: Write the failing test**

Create `katrain/web/ui/src/kiosk/__tests__/AiSetupPage.test.tsx`:

```typescript
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { ThemeProvider } from '@mui/material';
import { kioskTheme } from '../theme';
import AiSetupPage from '../pages/AiSetupPage';

const renderPage = (mode = 'free') =>
  render(
    <ThemeProvider theme={kioskTheme}>
      <MemoryRouter initialEntries={[`/kiosk/play/ai/setup/${mode}`]}>
        <Routes>
          <Route path="/kiosk/play/ai/setup/:mode" element={<AiSetupPage />} />
        </Routes>
      </MemoryRouter>
    </ThemeProvider>
  );

describe('AiSetupPage', () => {
  it('renders board size options', () => {
    renderPage();
    expect(screen.getByText('棋盘')).toBeInTheDocument();
    expect(screen.getByText('9路')).toBeInTheDocument();
    expect(screen.getByText('19路')).toBeInTheDocument();
  });

  it('renders color selection', () => {
    renderPage();
    expect(screen.getByText(/黑/)).toBeInTheDocument();
    expect(screen.getByText(/白/)).toBeInTheDocument();
  });

  it('renders start button', () => {
    renderPage();
    expect(screen.getByRole('button', { name: /开始对弈/i })).toBeInTheDocument();
  });

  it('shows AI strength slider for free mode', () => {
    renderPage('free');
    expect(screen.getByText(/AI 强度/i)).toBeInTheDocument();
  });

  it('hides AI strength slider for ranked mode', () => {
    renderPage('ranked');
    expect(screen.queryByText(/AI 强度/i)).not.toBeInTheDocument();
  });
});
```

**Step 2: Run test to verify it fails**

Run: `cd katrain/web/ui && npx vitest run src/kiosk/__tests__/AiSetupPage.test.tsx`
Expected: FAIL

**Step 3: Create AiSetupPage**

Create `katrain/web/ui/src/kiosk/pages/AiSetupPage.tsx`:

```typescript
import { useState } from 'react';
import { Box, Typography, Button, Slider } from '@mui/material';
import { useParams, useNavigate } from 'react-router-dom';
import { PlayArrow, ArrowBack } from '@mui/icons-material';
import OptionChips from '../components/common/OptionChips';

const AiSetupPage = () => {
  const { mode } = useParams<{ mode: string }>();
  const navigate = useNavigate();
  const isRanked = mode === 'ranked';

  const [boardSize, setBoardSize] = useState(19);
  const [color, setColor] = useState<'black' | 'white'>('black');
  const [aiStrength, setAiStrength] = useState(5);
  const [handicap, setHandicap] = useState(0);
  const [timeLimit, setTimeLimit] = useState(0);

  const handleStart = () => {
    // TODO: POST /api/new-game → get sessionId → navigate to game
    navigate('/kiosk/play/ai/game/mock-session');
  };

  return (
    <Box sx={{ display: 'flex', height: '100%' }}>
      {/* Left: board preview placeholder */}
      <Box
        sx={{
          aspectRatio: '1',
          height: '100%',
          bgcolor: '#8b7355',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          flexShrink: 0,
        }}
      >
        <Typography sx={{ color: 'rgba(0,0,0,0.3)' }}>{boardSize}x{boardSize}</Typography>
      </Box>

      {/* Right: settings form */}
      <Box sx={{ flex: 1, p: 3, overflow: 'auto', display: 'flex', flexDirection: 'column' }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 3 }}>
          <Button
            onClick={() => navigate('/kiosk/play')}
            startIcon={<ArrowBack />}
            sx={{ minWidth: 40, p: 0.5 }}
          />
          <Typography variant="h5">{isRanked ? '升降级对弈' : '自由对弈'}</Typography>
        </Box>

        <OptionChips
          label="棋盘"
          options={[{ value: 9, label: '9路' }, { value: 13, label: '13路' }, { value: 19, label: '19路' }]}
          value={boardSize}
          onChange={setBoardSize}
        />

        <OptionChips
          label="我执"
          options={[{ value: 'black' as const, label: '● 黑' }, { value: 'white' as const, label: '○ 白' }]}
          value={color}
          onChange={setColor}
        />

        {!isRanked && (
          <Box sx={{ mb: 2.5 }}>
            <Typography variant="body2" sx={{ color: 'text.secondary', mb: 1 }}>
              AI 强度: ~{aiStrength}D
            </Typography>
            <Slider value={aiStrength} onChange={(_, v) => setAiStrength(v as number)} min={-20} max={9} step={1} />
          </Box>
        )}

        <OptionChips
          label="让子"
          options={[0, 2, 3, 4, 5, 6].map((n) => ({ value: n, label: n === 0 ? '无' : `${n}子` }))}
          value={handicap}
          onChange={setHandicap}
        />

        <OptionChips
          label="用时"
          options={[{ value: 0, label: '不限' }, { value: 10, label: '10分' }, { value: 20, label: '20分' }, { value: 30, label: '30分' }]}
          value={timeLimit}
          onChange={setTimeLimit}
        />

        <Box sx={{ mt: 'auto', pt: 2 }}>
          <Button variant="contained" fullWidth size="large" startIcon={<PlayArrow />} onClick={handleStart} sx={{ minHeight: 56, py: 2, fontSize: '1.1rem' }}>
            开始对弈
          </Button>
        </Box>
      </Box>
    </Box>
  );
};

export default AiSetupPage;
```

**Step 4: Wire route, run tests, commit**

Run: `cd katrain/web/ui && npx vitest run src/kiosk/__tests__/AiSetupPage.test.tsx`
Expected: 5 tests PASS

```bash
git add katrain/web/ui/src/kiosk/pages/AiSetupPage.tsx katrain/web/ui/src/kiosk/__tests__/AiSetupPage.test.tsx katrain/web/ui/src/kiosk/KioskApp.tsx
git commit -m "feat(kiosk): add AI game setup page with touch-friendly option chips"
```

---

### Task 11: Game Page with Mock Analysis (Fullscreen)

**Files:**
- Create: `katrain/web/ui/src/kiosk/components/game/MockBoard.tsx`
- Create: `katrain/web/ui/src/kiosk/components/game/GameControlPanel.tsx`
- Create: `katrain/web/ui/src/kiosk/pages/GamePage.tsx`
- Create: `katrain/web/ui/src/kiosk/__tests__/GamePage.test.tsx`
- Modify: `katrain/web/ui/src/kiosk/KioskApp.tsx` (add fullscreen game routes)

**Step 1: Write the failing test**

Create `katrain/web/ui/src/kiosk/__tests__/GamePage.test.tsx`:

```typescript
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { ThemeProvider } from '@mui/material';
import { kioskTheme } from '../theme';
import GamePage from '../pages/GamePage';

const renderPage = () =>
  render(
    <ThemeProvider theme={kioskTheme}>
      <MemoryRouter initialEntries={['/kiosk/play/ai/game/mock-session']}>
        <Routes>
          <Route path="/kiosk/play/ai/game/:sessionId" element={<GamePage />} />
        </Routes>
      </MemoryRouter>
    </ThemeProvider>
  );

describe('GamePage', () => {
  it('renders mock board with move number', () => {
    renderPage();
    expect(screen.getByText(/第42手/)).toBeInTheDocument();
  });

  it('renders player names', () => {
    renderPage();
    expect(screen.getByText(/张三/)).toBeInTheDocument();
    expect(screen.getByText(/KataGo/)).toBeInTheDocument();
  });

  it('renders win rate', () => {
    renderPage();
    expect(screen.getByText(/56.3%/)).toBeInTheDocument();
  });

  it('renders control buttons', () => {
    renderPage();
    expect(screen.getByText('悔棋')).toBeInTheDocument();
    expect(screen.getByText('认输')).toBeInTheDocument();
  });

  it('does NOT render navigation rail (fullscreen)', () => {
    renderPage();
    expect(screen.queryByText('对弈')).not.toBeInTheDocument();
    expect(screen.queryByText('设置')).not.toBeInTheDocument();
  });
});
```

**Step 2: Run test to verify it fails**

Run: `cd katrain/web/ui && npx vitest run src/kiosk/__tests__/GamePage.test.tsx`
Expected: FAIL

**Step 3: Create MockBoard**

Create `katrain/web/ui/src/kiosk/components/game/MockBoard.tsx`:

```typescript
import { Box, Typography } from '@mui/material';

const MockBoard = ({ moveNumber = 0 }: { moveNumber?: number }) => (
  <Box
    sx={{
      aspectRatio: '1',
      height: '100%',
      bgcolor: '#8b7355',
      borderRadius: 1,
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      position: 'relative',
      overflow: 'hidden',
      flexShrink: 0,
    }}
  >
    <Box
      sx={{
        position: 'absolute',
        inset: '8%',
        backgroundImage:
          'repeating-linear-gradient(0deg, transparent, transparent calc(100%/18 - 1px), rgba(0,0,0,0.3) calc(100%/18 - 1px), rgba(0,0,0,0.3) calc(100%/18)), repeating-linear-gradient(90deg, transparent, transparent calc(100%/18 - 1px), rgba(0,0,0,0.3) calc(100%/18 - 1px), rgba(0,0,0,0.3) calc(100%/18))',
      }}
    />
    <Typography variant="caption" sx={{ color: 'rgba(0,0,0,0.4)', zIndex: 1 }}>
      棋盘 · 第{moveNumber}手
    </Typography>
  </Box>
);

export default MockBoard;
```

**Step 4: Create GameControlPanel**

Create `katrain/web/ui/src/kiosk/components/game/GameControlPanel.tsx`:

```typescript
import { Box, Typography, Button, LinearProgress, Divider } from '@mui/material';
import { Undo, PanTool, Calculate, Flag, Settings, Close } from '@mui/icons-material';

interface Props {
  blackPlayer: string;
  whitePlayer: string;
  blackCaptures: number;
  whiteCaptures: number;
  winRate: number;
  bestMove: string;
  bestMoveProb: number;
  altMove: string;
  altMoveProb: number;
  moveNumber: number;
}

const GameControlPanel = (props: Props) => (
  <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%', p: 2, gap: 1.5 }}>
    {/* Players */}
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
        <Typography variant="body1" sx={{ fontWeight: 600 }}>● {props.blackPlayer}</Typography>
        <Typography variant="caption">○提: {props.blackCaptures}</Typography>
      </Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
        <Typography variant="body1" sx={{ fontWeight: 600 }}>○ {props.whitePlayer}</Typography>
        <Typography variant="caption">●提: {props.whiteCaptures}</Typography>
      </Box>
    </Box>

    <Divider />

    {/* Win rate */}
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
        <Typography variant="body2" sx={{ color: 'text.secondary' }}>胜率</Typography>
        <Typography variant="body1" sx={{ fontFamily: "'JetBrains Mono', monospace", fontWeight: 600 }}>
          {props.winRate.toFixed(1)}%
        </Typography>
      </Box>
      <LinearProgress
        variant="determinate"
        value={props.winRate}
        sx={{
          height: 8, borderRadius: 4, bgcolor: 'rgba(232,228,220,0.1)',
          '& .MuiLinearProgress-bar': { bgcolor: props.winRate > 50 ? 'success.main' : 'error.main', borderRadius: 4 },
        }}
      />
    </Box>

    {/* AI suggestion */}
    <Box>
      <Typography variant="body2" sx={{ color: 'text.secondary', mb: 0.5 }}>AI 推荐</Typography>
      <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
        <Typography sx={{ color: 'primary.main', fontWeight: 600 }}>{props.bestMove}</Typography>
        <Typography variant="caption" sx={{ fontFamily: "'JetBrains Mono', monospace" }}>{props.bestMoveProb.toFixed(1)}%</Typography>
      </Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
        <Typography variant="body2" sx={{ color: 'text.secondary' }}>{props.altMove}</Typography>
        <Typography variant="caption" sx={{ fontFamily: "'JetBrains Mono', monospace", color: 'text.secondary' }}>{props.altMoveProb.toFixed(1)}%</Typography>
      </Box>
    </Box>

    <Typography variant="caption" sx={{ color: 'text.secondary' }}>第 {props.moveNumber} 手</Typography>

    <Box sx={{ mt: 'auto' }} />

    {/* Controls — 3x2 grid */}
    <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 1 }}>
      <Button variant="outlined" startIcon={<Undo />} sx={{ minHeight: 48 }}>悔棋</Button>
      <Button variant="outlined" startIcon={<PanTool />} sx={{ minHeight: 48 }}>跳过</Button>
      <Button variant="outlined" startIcon={<Calculate />} sx={{ minHeight: 48 }}>计数</Button>
      <Button variant="outlined" color="error" startIcon={<Flag />} sx={{ minHeight: 48 }}>认输</Button>
      <Button variant="outlined" startIcon={<Settings />} sx={{ minHeight: 48 }}>设置</Button>
      <Button variant="outlined" startIcon={<Close />} sx={{ minHeight: 48 }}>退出</Button>
    </Box>
  </Box>
);

export default GameControlPanel;
```

**Step 5: Create GamePage**

Create `katrain/web/ui/src/kiosk/pages/GamePage.tsx`:

```typescript
import { Box } from '@mui/material';
import MockBoard from '../components/game/MockBoard';
import GameControlPanel from '../components/game/GameControlPanel';
import { mockGameState } from '../data/mocks';

const GamePage = () => {
  return (
    <Box sx={{ display: 'flex', height: '100vh', bgcolor: 'background.default' }}>
      <Box sx={{ height: '100%', aspectRatio: '1' }}>
        <MockBoard moveNumber={mockGameState.moveNumber} />
      </Box>
      <Box sx={{ flex: 1, overflow: 'auto' }}>
        <GameControlPanel {...mockGameState} />
      </Box>
    </Box>
  );
};

export default GamePage;
```

**Step 6: Add fullscreen game routes in KioskApp.tsx**

In the `KioskRoutes` component, add fullscreen routes inside the auth guard but outside KioskLayout:

```typescript
import GamePage from './pages/GamePage';
// ...
<Route element={<KioskAuthGuard />}>
  {/* Fullscreen — no nav rail */}
  <Route path="play/ai/game/:sessionId" element={<GamePage />} />
  <Route path="play/pvp/local/game/:sessionId" element={<GamePage />} />
  <Route path="play/pvp/room/:sessionId" element={<GamePage />} />

  {/* Standard — with nav rail */}
  <Route element={<KioskLayout username={user?.name} />}>
    {/* ... existing routes ... */}
  </Route>
</Route>
```

**Step 7: Run test to verify it passes**

Run: `cd katrain/web/ui && npx vitest run src/kiosk/__tests__/GamePage.test.tsx`
Expected: 5 tests PASS

**Step 8: Commit**

```bash
git add katrain/web/ui/src/kiosk/components/game/ katrain/web/ui/src/kiosk/pages/GamePage.tsx katrain/web/ui/src/kiosk/__tests__/GamePage.test.tsx katrain/web/ui/src/kiosk/KioskApp.tsx
git commit -m "feat(kiosk): add fullscreen GamePage with mock board and control panel"
```

---

### Task 12: Tsumego Selection Page

**Files:**
- Create: `katrain/web/ui/src/kiosk/pages/TsumegoPage.tsx`
- Create: `katrain/web/ui/src/kiosk/__tests__/TsumegoPage.test.tsx`
- Modify: `katrain/web/ui/src/kiosk/KioskApp.tsx`

**Step 1: Write the failing test**

Create `katrain/web/ui/src/kiosk/__tests__/TsumegoPage.test.tsx`:

```typescript
import { describe, it, expect } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { ThemeProvider } from '@mui/material';
import { kioskTheme } from '../theme';
import TsumegoPage from '../pages/TsumegoPage';

const renderPage = () =>
  render(
    <ThemeProvider theme={kioskTheme}>
      <MemoryRouter>
        <TsumegoPage />
      </MemoryRouter>
    </ThemeProvider>
  );

describe('TsumegoPage', () => {
  it('renders level filter chips', () => {
    renderPage();
    ['全部', '入门', '初级', '中级', '高级'].forEach((level) => {
      expect(screen.getByText(level)).toBeInTheDocument();
    });
  });

  it('renders problem buttons from fixed mock data', () => {
    renderPage();
    expect(screen.getByText('入门 1')).toBeInTheDocument();
    expect(screen.getByText('高级 2')).toBeInTheDocument();
  });

  it('filters problems when clicking a level chip', () => {
    renderPage();
    fireEvent.click(screen.getByText('入门'));
    expect(screen.getByText('入门 1')).toBeInTheDocument();
    expect(screen.queryByText('高级 1')).not.toBeInTheDocument();
  });
});
```

**Step 2: Run test to verify it fails**

Run: `cd katrain/web/ui && npx vitest run src/kiosk/__tests__/TsumegoPage.test.tsx`
Expected: FAIL

**Step 3: Create TsumegoPage**

Create `katrain/web/ui/src/kiosk/pages/TsumegoPage.tsx`:

```typescript
import { useState } from 'react';
import { Box, Typography, ButtonBase, Chip } from '@mui/material';
import { useNavigate } from 'react-router-dom';
import { mockTsumegoProblems } from '../data/mocks';

const levels = ['入门', '初级', '中级', '高级'];

const TsumegoPage = () => {
  const navigate = useNavigate();
  const [filter, setFilter] = useState('全部');
  const filtered = filter === '全部' ? mockTsumegoProblems : mockTsumegoProblems.filter((p) => p.level === filter);

  return (
    <Box sx={{ display: 'flex', height: '100%' }}>
      <Box sx={{ height: '100%', aspectRatio: '1', bgcolor: 'background.paper', display: 'flex', alignItems: 'center', justifyContent: 'center', borderRight: '1px solid', borderColor: 'divider', flexShrink: 0 }}>
        <Typography variant="body2" sx={{ color: 'text.secondary', opacity: 0.3 }}>题目预览</Typography>
      </Box>
      <Box sx={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        <Box sx={{ display: 'flex', gap: 1, p: 2, pb: 1, flexShrink: 0 }}>
          {['全部', ...levels].map((l) => (
            <Chip key={l} label={l} onClick={() => setFilter(l)} variant={filter === l ? 'filled' : 'outlined'} color={filter === l ? 'primary' : 'default'} sx={{ minHeight: 40, fontSize: '0.9rem' }} />
          ))}
        </Box>
        <Box sx={{ flex: 1, overflow: 'auto', display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(100px, 1fr))', gap: 1, p: 2, pt: 1, alignContent: 'start' }}>
          {filtered.map((p) => (
            <ButtonBase key={p.id} onClick={() => navigate(`/kiosk/tsumego/problem/${p.id}`)} sx={{ minHeight: 56, borderRadius: 2, bgcolor: p.solved ? 'primary.dark' : 'background.paper', border: '1px solid', borderColor: p.solved ? 'primary.main' : 'divider', '&:active': { transform: 'scale(0.96)' } }}>
              <Typography variant="body2" sx={{ fontWeight: 500 }}>{p.label}</Typography>
            </ButtonBase>
          ))}
        </Box>
      </Box>
    </Box>
  );
};

export default TsumegoPage;
```

**Step 4: Wire route, run tests, commit**

Run: `cd katrain/web/ui && npx vitest run src/kiosk/__tests__/TsumegoPage.test.tsx`
Expected: 3 tests PASS

```bash
git add katrain/web/ui/src/kiosk/pages/TsumegoPage.tsx katrain/web/ui/src/kiosk/__tests__/TsumegoPage.test.tsx katrain/web/ui/src/kiosk/KioskApp.tsx
git commit -m "feat(kiosk): add Tsumego selection page with filterable problem grid"
```

---

### Task 13: Remaining Tab Pages

Each page follows the left-board + right-panel pattern where appropriate. Create one at a time with a smoke test, wire route, commit.

**Files to create (each with a `__tests__` counterpart):**
- `katrain/web/ui/src/kiosk/pages/ResearchPage.tsx` — MockBoard left + analysis panel right
- `katrain/web/ui/src/kiosk/pages/KifuPage.tsx` — board preview left + scrollable game list right
- `katrain/web/ui/src/kiosk/pages/LivePage.tsx` — match list with mock live/upcoming
- `katrain/web/ui/src/kiosk/pages/SettingsPage.tsx` — language selector + external platforms section

**For each page, follow this TDD flow:**

**Step 1:** Write smoke test (renders key content, no runtime errors)

Example smoke test pattern:

```typescript
// __tests__/ResearchPage.test.tsx
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { ThemeProvider } from '@mui/material';
import { kioskTheme } from '../theme';
import ResearchPage from '../pages/ResearchPage';

describe('ResearchPage', () => {
  it('renders without crashing and shows key elements', () => {
    render(
      <ThemeProvider theme={kioskTheme}>
        <MemoryRouter>
          <ResearchPage />
        </MemoryRouter>
      </ThemeProvider>
    );
    expect(screen.getByText(/研究/i)).toBeInTheDocument();
  });
});
```

**Step 2:** Run test to verify it fails
**Step 3:** Create page component importing from `data/mocks.ts`
**Step 4:** Wire route in KioskApp.tsx
**Step 5:** Run test to verify it passes
**Step 6:** Commit individually

```bash
git commit -m "feat(kiosk): add ResearchPage with mock analysis panel"
git commit -m "feat(kiosk): add KifuPage with mock game list"
git commit -m "feat(kiosk): add LivePage with mock match list"
git commit -m "feat(kiosk): add SettingsPage with language selector and platform links"
```

**SettingsPage note:** This page includes an "外部平台" section with cards for 99围棋, 野狐围棋, 腾讯围棋, 新浪围棋. This replaces the separate "平台" tab from Rev 1, consolidating infrequently-accessed features.

---

## Phase 5: Verification

### Task 14: Navigation Integration Tests + SPA Fallback

**Files:**
- Create: `katrain/web/ui/src/kiosk/__tests__/navigation.integration.test.tsx`

**Step 1: Write integration tests**

Create `katrain/web/ui/src/kiosk/__tests__/navigation.integration.test.tsx`:

```typescript
import { describe, it, expect } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import KioskApp from '../KioskApp';

const renderApp = (route = '/kiosk') =>
  render(
    <MemoryRouter initialEntries={[route]}>
      <KioskApp />
    </MemoryRouter>
  );

const loginFirst = () => {
  const usernameInput = screen.getByLabelText(/用户名/i);
  fireEvent.change(usernameInput, { target: { value: '张三' } });
  fireEvent.click(screen.getByRole('button', { name: /登录/i }));
};

describe('Kiosk navigation integration', () => {
  it('unauthenticated user is redirected to login for any route', () => {
    renderApp('/kiosk/tsumego');
    expect(screen.getByRole('button', { name: /登录/i })).toBeInTheDocument();
  });

  it('login → redirects to play page with nav rail', () => {
    renderApp('/kiosk/play');
    loginFirst();
    expect(screen.getByText('对弈')).toBeInTheDocument();
    expect(screen.getByText('人机对弈')).toBeInTheDocument();
  });

  it('nav rail items navigate correctly', () => {
    renderApp('/kiosk/play');
    loginFirst();
    fireEvent.click(screen.getByText('死活'));
    expect(screen.getByText('入门 1')).toBeInTheDocument();
  });

  it('/kiosk redirects to /kiosk/play', () => {
    renderApp('/kiosk');
    loginFirst();
    expect(screen.getByText('人机对弈')).toBeInTheDocument();
  });

  it('unknown kiosk routes redirect to play', () => {
    renderApp('/kiosk/nonexistent');
    loginFirst();
    expect(screen.getByText('人机对弈')).toBeInTheDocument();
  });
});
```

**Step 2: Run tests**

Run: `cd katrain/web/ui && npx vitest run src/kiosk/__tests__/navigation.integration.test.tsx`
Expected: 5 tests PASS

**Step 3: Verify SPA fallback in dev server**

Run: `cd katrain/web/ui && npm run dev`
Test: Open `http://localhost:5173/kiosk/tsumego/problem/beginner-1` directly in browser.
Expected: App loads (not 404). Vite dev server handles SPA fallback automatically.

Note: For production deployment, FastAPI must be configured to serve `index.html` for `/kiosk/*` routes. This is handled in Phase 5 (kiosk infrastructure). Verify by checking `katrain/web/server.py` serves the SPA fallback.

**Step 4: Commit**

```bash
git add katrain/web/ui/src/kiosk/__tests__/navigation.integration.test.tsx
git commit -m "test(kiosk): add navigation integration tests and verify SPA fallback"
```

---

### Task 15: Full Test Suite + Visual Review

**Step 1: Run all kiosk tests**

Run: `cd katrain/web/ui && npx vitest run src/kiosk/`
Expected: All tests PASS

**Step 2: Run all tests to confirm no Galaxy regression**

Run: `cd katrain/web/ui && npx vitest run`
Expected: All existing tests still PASS

**Step 3: Visual walkthrough in browser**

Run: `cd katrain/web/ui && npm run dev`

Visit `http://localhost:5173/kiosk/` and verify each flow:
- [ ] Login page → enter username → 登录 → main interface
- [ ] 对弈 → 4 mode cards → 自由对弈 → setup → 开始对弈 → fullscreen game
- [ ] 对弈 → 升降级对弈 → setup (no AI slider) → start
- [ ] 死活 → problem grid → filter by level → click problem
- [ ] 研究 → board + analysis panel
- [ ] 棋谱 → game list
- [ ] 直播 → match list
- [ ] 设置 → language selector + platform links
- [ ] Nav rail highlights correct item on each page
- [ ] Fullscreen game pages have NO nav rail or status bar
- [ ] Back navigation from setup pages works

Visit `http://localhost:5173/galaxy/` and confirm unchanged.

**Step 4: Fix any visual issues**

```bash
git commit -m "fix(kiosk): address visual review feedback"
```

---

## Phase Gate: Entry Criteria for Phase 3+

Before proceeding to Phase 3 (Shared Layer Extraction), verify:

- [ ] All P0 items from reviews are closed
- [ ] All kiosk tests pass (`npx vitest run src/kiosk/`)
- [ ] No Galaxy test regressions
- [ ] No CDN dependencies (fonts loaded via @fontsource)
- [ ] Login → select mode → start game → exit flow works end-to-end
- [ ] Critical flow has automated test coverage (navigation integration test)
- [ ] SPA fallback works for deep links

## Future Phases (separate plans)

- **Phase 3: Shared Layer Extraction** — Move Board.tsx, hooks, API, types to `src/shared/`, update imports in both galaxy and kiosk. Rule: no copying galaxy hooks into kiosk; if you need a hook, extract to shared immediately.
- **Phase 4: Backend Integration** — Wire real game sessions, WebSocket, auth, tsumego API
- **Phase 5: Kiosk Infrastructure** — systemd services, Chromium kiosk mode, OS virtual keyboard setup (`onboard`), deployment script, SPA fallback in FastAPI
- **Phase 6: Hardware Integration** — Board sensor driver, WebSocket `board_input` protocol, input arbitration (physical board vs touch conflict rules)
- **Phase 7: Performance Baseline** — First-screen time, FPS, memory, WebSocket latency on target RK3588 device

## Infrastructure Notes (deferred to Phase 5)

**Virtual keyboard:** Kiosk text input (login, search) requires an OS-level virtual keyboard. On Ubuntu, use `onboard` configured for CJK input. React text inputs trigger it automatically. This is infrastructure setup, not frontend code.

**Screen burn-in prevention:** For OLED/IPS kiosk displays, implement a screensaver or dimming after idle timeout. This is a Phase 5 concern.
