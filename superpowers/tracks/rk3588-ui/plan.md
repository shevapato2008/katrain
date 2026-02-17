# RK3588 Kiosk UI Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a touch-optimized kiosk UI for 7-10 inch smart Go board terminals, frontend-first with mock data, parallel to the existing Galaxy web UI.

**Architecture:** New `src/kiosk/` directory with its own theme, layout, and pages. Shares backend API layer and core types with Galaxy via `src/shared/`. Single Vite build serves both at different URL prefixes (`/galaxy/*`, `/kiosk/*`). "Ink Stone" dark theme, MUI v7 components restyled for 48px+ touch targets.

**Tech Stack:** React 19, TypeScript, MUI v7, React Router v6, Vite (rolldown-vite), Vitest, Testing Library

**Design doc:** `docs/plans/2026-02-17-rk3588-kiosk-ui-design.md`

**Existing code to know about:**
- Entry: `katrain/web/ui/src/main.tsx` → `AppRouter.tsx` → `GalaxyApp.tsx` / `ZenModeApp.tsx`
- Galaxy theme: `katrain/web/ui/src/theme.ts` (MUI dark, Manrope font, jade accents)
- Galaxy layout: `katrain/web/ui/src/galaxy/components/layout/MainLayout.tsx` (240px sidebar + Outlet)
- Shared components already at: `katrain/web/ui/src/components/Board.tsx`, `ScoreGraph.tsx`, `PlayerCard.tsx`
- Shared hooks already at: `katrain/web/ui/src/galaxy/hooks/useGameSession.ts` etc.
- Tests run with: `cd katrain/web/ui && npx vitest run <path>`
- Test setup: `src/test/setup.ts` imports `@testing-library/jest-dom`
- Vite config: `katrain/web/ui/vite.config.ts` (proxy `/api` → `:8001`, proxy `/ws` → ws)

---

## Task 1: Create Kiosk Theme

**Files:**
- Create: `katrain/web/ui/src/kiosk/theme.ts`
- Create: `katrain/web/ui/src/kiosk/__tests__/theme.test.ts`

**Step 1: Write the failing test**

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

  it('uses Noto Serif SC for headings', () => {
    expect((kioskTheme.typography.h1 as any).fontFamily).toContain('Noto Serif SC');
  });

  it('has jade-glow #5cb57a as primary color', () => {
    expect(kioskTheme.palette.primary.main).toBe('#5cb57a');
  });

  it('has ember #c45d3e as error color', () => {
    expect(kioskTheme.palette.error.main).toBe('#c45d3e');
  });

  it('enforces 56px min button height for touch targets', () => {
    const overrides = kioskTheme.components?.MuiButton?.styleOverrides as any;
    expect(overrides.root.minHeight).toBe(56);
  });

  it('enforces 48px min icon button size for touch targets', () => {
    const overrides = kioskTheme.components?.MuiIconButton?.styleOverrides as any;
    expect(overrides.root.minWidth).toBe(48);
    expect(overrides.root.minHeight).toBe(48);
  });

  it('sets bottom nav bar height to 64px', () => {
    const overrides = kioskTheme.components?.MuiBottomNavigation?.styleOverrides as any;
    expect(overrides.root.height).toBe(64);
  });
});
```

**Step 2: Run test to verify it fails**

Run: `cd katrain/web/ui && npx vitest run src/kiosk/__tests__/theme.test.ts`
Expected: FAIL with "Cannot find module '../theme'"

**Step 3: Write minimal implementation**

Create `katrain/web/ui/src/kiosk/theme.ts`:

```typescript
import { createTheme } from '@mui/material';

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
      primary: '#e8e4dc',  // stone-white
      secondary: '#6b6560', // mist
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
    h2: { fontFamily: "'Noto Serif SC', 'Noto Serif', serif", fontWeight: 700 },
    h3: { fontFamily: "'Noto Serif SC', 'Noto Serif', serif", fontWeight: 600 },
    h4: { fontFamily: "'Noto Serif SC', 'Noto Serif', serif", fontWeight: 600 },
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
          minHeight: 56,
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
    MuiBottomNavigation: {
      styleOverrides: {
        root: {
          height: 64,
          backgroundColor: '#1a1714',
          borderTop: '1px solid rgba(232, 228, 220, 0.08)',
        },
      },
    },
    MuiBottomNavigationAction: {
      styleOverrides: {
        root: {
          minWidth: 'auto',
          padding: '6px 0',
          color: '#6b6560',
          '&.Mui-selected': { color: '#5cb57a' },
        },
      },
    },
  },
});
```

**Step 4: Run test to verify it passes**

Run: `cd katrain/web/ui && npx vitest run src/kiosk/__tests__/theme.test.ts`
Expected: 8 tests PASS

**Step 5: Commit**

```bash
git add katrain/web/ui/src/kiosk/theme.ts katrain/web/ui/src/kiosk/__tests__/theme.test.ts
git commit -m "feat(kiosk): add Ink Stone theme with touch-friendly component overrides"
```

---

## Task 2: Create StatusBar Component

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
    renderWithTheme(<StatusBar />);
    expect(screen.getByText('KaTrain')).toBeInTheDocument();
  });

  it('renders engine status indicator', () => {
    renderWithTheme(<StatusBar />);
    expect(screen.getByTestId('engine-status')).toBeInTheDocument();
  });

  it('renders current time', () => {
    renderWithTheme(<StatusBar />);
    // Time text exists (format varies)
    expect(screen.getByTestId('clock')).toBeInTheDocument();
  });
});
```

**Step 2: Run test to verify it fails**

Run: `cd katrain/web/ui && npx vitest run src/kiosk/__tests__/StatusBar.test.tsx`
Expected: FAIL with "Cannot find module '../components/layout/StatusBar'"

**Step 3: Write minimal implementation**

Create `katrain/web/ui/src/kiosk/components/layout/StatusBar.tsx`:

```typescript
import { Box, Typography } from '@mui/material';

const StatusBar = () => {
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
Expected: 3 tests PASS

**Step 5: Commit**

```bash
git add katrain/web/ui/src/kiosk/components/layout/StatusBar.tsx katrain/web/ui/src/kiosk/__tests__/StatusBar.test.tsx
git commit -m "feat(kiosk): add StatusBar with branding, engine status, clock"
```

---

## Task 3: Create BottomTabBar Component

**Files:**
- Create: `katrain/web/ui/src/kiosk/components/layout/BottomTabBar.tsx`
- Create: `katrain/web/ui/src/kiosk/__tests__/BottomTabBar.test.tsx`

**Step 1: Write the failing test**

Create `katrain/web/ui/src/kiosk/__tests__/BottomTabBar.test.tsx`:

```typescript
import { describe, it, expect } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { ThemeProvider } from '@mui/material';
import { kioskTheme } from '../theme';
import BottomTabBar from '../components/layout/BottomTabBar';

const renderWithProviders = (ui: React.ReactElement, route = '/kiosk/ai') =>
  render(
    <ThemeProvider theme={kioskTheme}>
      <MemoryRouter initialEntries={[route]}>{ui}</MemoryRouter>
    </ThemeProvider>
  );

describe('BottomTabBar', () => {
  it('renders all 8 tab labels', () => {
    renderWithProviders(<BottomTabBar />);
    const labels = ['人机', '人人', '死活', '研究', '棋谱', '直播', '平台', '设置'];
    labels.forEach((label) => {
      expect(screen.getByText(label)).toBeInTheDocument();
    });
  });

  it('highlights the active tab based on current route', () => {
    renderWithProviders(<BottomTabBar />, '/kiosk/tsumego');
    const tsumegoTab = screen.getByText('死活').closest('button');
    expect(tsumegoTab).toHaveClass('Mui-selected');
  });
});
```

**Step 2: Run test to verify it fails**

Run: `cd katrain/web/ui && npx vitest run src/kiosk/__tests__/BottomTabBar.test.tsx`
Expected: FAIL with "Cannot find module '../components/layout/BottomTabBar'"

**Step 3: Write minimal implementation**

Create `katrain/web/ui/src/kiosk/components/layout/BottomTabBar.tsx`:

```typescript
import { BottomNavigation, BottomNavigationAction } from '@mui/material';
import {
  SportsEsports as AiIcon,
  Groups as PvpIcon,
  Extension as TsumegoIcon,
  Science as ResearchIcon,
  MenuBook as KifuIcon,
  LiveTv as LiveIcon,
  Language as PlatformIcon,
  Settings as SettingsIcon,
} from '@mui/icons-material';
import { useNavigate, useLocation } from 'react-router-dom';

const tabs = [
  { label: '人机', icon: <AiIcon />, path: '/kiosk/ai' },
  { label: '人人', icon: <PvpIcon />, path: '/kiosk/pvp' },
  { label: '死活', icon: <TsumegoIcon />, path: '/kiosk/tsumego' },
  { label: '研究', icon: <ResearchIcon />, path: '/kiosk/research' },
  { label: '棋谱', icon: <KifuIcon />, path: '/kiosk/kifu' },
  { label: '直播', icon: <LiveIcon />, path: '/kiosk/live' },
  { label: '平台', icon: <PlatformIcon />, path: '/kiosk/platforms' },
  { label: '设置', icon: <SettingsIcon />, path: '/kiosk/settings' },
];

const BottomTabBar = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const currentTab = tabs.findIndex((t) => location.pathname.startsWith(t.path));

  return (
    <BottomNavigation
      value={currentTab === -1 ? 0 : currentTab}
      onChange={(_, idx) => navigate(tabs[idx].path)}
      showLabels
      sx={{ flexShrink: 0 }}
    >
      {tabs.map((tab) => (
        <BottomNavigationAction
          key={tab.path}
          label={tab.label}
          icon={tab.icon}
          sx={{ minWidth: 0, px: 0.5 }}
        />
      ))}
    </BottomNavigation>
  );
};

export default BottomTabBar;
```

**Step 4: Run test to verify it passes**

Run: `cd katrain/web/ui && npx vitest run src/kiosk/__tests__/BottomTabBar.test.tsx`
Expected: 2 tests PASS

**Step 5: Commit**

```bash
git add katrain/web/ui/src/kiosk/components/layout/BottomTabBar.tsx katrain/web/ui/src/kiosk/__tests__/BottomTabBar.test.tsx
git commit -m "feat(kiosk): add BottomTabBar with 8 tabs and active route highlighting"
```

---

## Task 4: Create KioskLayout Shell

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
  it('renders status bar, outlet content, and tab bar together', () => {
    render(
      <ThemeProvider theme={kioskTheme}>
        <MemoryRouter initialEntries={['/kiosk/ai']}>
          <Routes>
            <Route element={<KioskLayout />}>
              <Route path="/kiosk/ai" element={<div>AI_PAGE_CONTENT</div>} />
            </Route>
          </Routes>
        </MemoryRouter>
      </ThemeProvider>
    );
    // StatusBar present
    expect(screen.getByText('KaTrain')).toBeInTheDocument();
    // Outlet renders child
    expect(screen.getByText('AI_PAGE_CONTENT')).toBeInTheDocument();
    // TabBar present
    expect(screen.getByText('人机')).toBeInTheDocument();
  });
});
```

**Step 2: Run test to verify it fails**

Run: `cd katrain/web/ui && npx vitest run src/kiosk/__tests__/KioskLayout.test.tsx`
Expected: FAIL with "Cannot find module '../components/layout/KioskLayout'"

**Step 3: Write minimal implementation**

Create `katrain/web/ui/src/kiosk/components/layout/KioskLayout.tsx`:

```typescript
import { Box } from '@mui/material';
import { Outlet } from 'react-router-dom';
import StatusBar from './StatusBar';
import BottomTabBar from './BottomTabBar';

const KioskLayout = () => {
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
      <StatusBar />
      <Box
        component="main"
        sx={{ flexGrow: 1, overflow: 'auto', display: 'flex', flexDirection: 'column' }}
      >
        <Outlet />
      </Box>
      <BottomTabBar />
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
git commit -m "feat(kiosk): add KioskLayout composing StatusBar + Outlet + BottomTabBar"
```

---

## Task 5: Create KioskApp and Wire into AppRouter

**Files:**
- Create: `katrain/web/ui/src/kiosk/KioskApp.tsx`
- Create: `katrain/web/ui/src/kiosk/pages/PlaceholderPage.tsx`
- Create: `katrain/web/ui/src/kiosk/styles/fonts.css`
- Modify: `katrain/web/ui/src/AppRouter.tsx`
- Test: `katrain/web/ui/src/kiosk/__tests__/KioskApp.test.tsx`

**Step 1: Write the failing test**

Create `katrain/web/ui/src/kiosk/__tests__/KioskApp.test.tsx`:

```typescript
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { ThemeProvider } from '@mui/material';
import { kioskTheme } from '../theme';
import KioskApp from '../KioskApp';

const renderApp = (route: string) =>
  render(
    <ThemeProvider theme={kioskTheme}>
      <MemoryRouter initialEntries={[route]}>
        <KioskApp />
      </MemoryRouter>
    </ThemeProvider>
  );

describe('KioskApp', () => {
  it('renders tab bar on /kiosk/ai', () => {
    renderApp('/kiosk/ai');
    expect(screen.getByText('人机')).toBeInTheDocument();
    expect(screen.getByText('KaTrain')).toBeInTheDocument();
  });

  it('shows placeholder content for unimplemented pages', () => {
    renderApp('/kiosk/research');
    expect(screen.getByText(/RESEARCH/i)).toBeInTheDocument();
  });

  it('redirects /kiosk to /kiosk/ai', () => {
    renderApp('/kiosk');
    // After redirect, AI tab should be active
    expect(screen.getByText('AI')).toBeInTheDocument();
  });
});
```

**Step 2: Run test to verify it fails**

Run: `cd katrain/web/ui && npx vitest run src/kiosk/__tests__/KioskApp.test.tsx`
Expected: FAIL with "Cannot find module '../KioskApp'"

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

**Step 4: Create fonts.css**

Create `katrain/web/ui/src/kiosk/styles/fonts.css`:

```css
/* Dev: load from Google Fonts CDN. Production RK3588: bundle locally. */
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+SC:wght@400;500;600;700&family=Noto+Serif+SC:wght@600;700&family=JetBrains+Mono:wght@400;500&display=swap');
```

**Step 5: Create KioskApp**

Create `katrain/web/ui/src/kiosk/KioskApp.tsx`:

```typescript
import { Routes, Route, Navigate } from 'react-router-dom';
import './styles/fonts.css';
import KioskLayout from './components/layout/KioskLayout';
import PlaceholderPage from './pages/PlaceholderPage';

const KioskApp = () => {
  return (
    <Routes>
      <Route element={<KioskLayout />}>
        <Route index element={<Navigate to="/kiosk/ai" replace />} />
        <Route path="ai" element={<PlaceholderPage />} />
        <Route path="ai/setup/:mode" element={<PlaceholderPage />} />
        <Route path="pvp" element={<PlaceholderPage />} />
        <Route path="pvp/lobby" element={<PlaceholderPage />} />
        <Route path="tsumego" element={<PlaceholderPage />} />
        <Route path="tsumego/problem/:problemId" element={<PlaceholderPage />} />
        <Route path="research" element={<PlaceholderPage />} />
        <Route path="kifu" element={<PlaceholderPage />} />
        <Route path="live" element={<PlaceholderPage />} />
        <Route path="live/:matchId" element={<PlaceholderPage />} />
        <Route path="platforms" element={<PlaceholderPage />} />
        <Route path="settings" element={<PlaceholderPage />} />
        <Route path="*" element={<Navigate to="/kiosk/ai" replace />} />
      </Route>
      {/* Fullscreen game pages (no tab bar) — added in later tasks */}
    </Routes>
  );
};

export default KioskApp;
```

**Step 6: Modify AppRouter.tsx to add kiosk route**

File: `katrain/web/ui/src/AppRouter.tsx` — replace entire contents:

```typescript
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { ThemeProvider, CssBaseline } from '@mui/material';
import { zenTheme } from './theme';
import { kioskTheme } from './kiosk/theme';
import ZenModeApp from './ZenModeApp';
import GalaxyApp from './GalaxyApp';
import KioskApp from './kiosk/KioskApp';

const AppRouter = () => {
  const isKiosk = window.location.pathname.startsWith('/kiosk');

  return (
    <ThemeProvider theme={isKiosk ? kioskTheme : zenTheme}>
      <CssBaseline />
      <BrowserRouter>
        <Routes>
          <Route path="/kiosk/*" element={<KioskApp />} />
          <Route path="/galaxy/*" element={<GalaxyApp />} />
          <Route path="/*" element={<ZenModeApp />} />
        </Routes>
      </BrowserRouter>
    </ThemeProvider>
  );
};

export default AppRouter;
```

**Step 7: Run test to verify it passes**

Run: `cd katrain/web/ui && npx vitest run src/kiosk/__tests__/KioskApp.test.tsx`
Expected: 3 tests PASS

**Step 8: Run ALL kiosk tests to make sure nothing broke**

Run: `cd katrain/web/ui && npx vitest run src/kiosk/`
Expected: All tests PASS (theme: 8, StatusBar: 3, BottomTabBar: 2, KioskLayout: 1, KioskApp: 3)

**Step 9: Verify visually in browser**

Run: `cd katrain/web/ui && npm run dev`
Visit: `http://localhost:5173/kiosk/`
Expected: Dark ink-black background, green "KaTrain" in status bar, "AI" placeholder in center, 8 tab icons at bottom. Clicking tabs changes placeholder text. Galaxy at `/galaxy/` still works unchanged.

**Step 10: Commit**

```bash
git add katrain/web/ui/src/kiosk/ katrain/web/ui/src/AppRouter.tsx
git commit -m "feat(kiosk): wire KioskApp into AppRouter with all routes and font loading"
```

---

## Task 6: Create ModeCard Reusable Component

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
          to="/kiosk/ai/setup/free"
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
    expect(mockNavigate).toHaveBeenCalledWith('/kiosk/ai/setup/free');
  });
});
```

**Step 2: Run test to verify it fails**

Run: `cd katrain/web/ui && npx vitest run src/kiosk/__tests__/ModeCard.test.tsx`
Expected: FAIL with "Cannot find module '../components/common/ModeCard'"

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

## Task 7: Create OptionChips Reusable Component

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

## Task 8: Human vs AI Selection Page

**Files:**
- Create: `katrain/web/ui/src/kiosk/pages/AiPlayPage.tsx`
- Modify: `katrain/web/ui/src/kiosk/KioskApp.tsx` (swap placeholder for real page)

**Step 1: Create AiPlayPage**

Create `katrain/web/ui/src/kiosk/pages/AiPlayPage.tsx`:

```typescript
import { Box } from '@mui/material';
import { SportsEsports, EmojiEvents } from '@mui/icons-material';
import ModeCard from '../components/common/ModeCard';

const AiPlayPage = () => {
  return (
    <Box
      sx={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        height: '100%',
        gap: 3,
        p: 3,
      }}
    >
      <ModeCard
        title="自由对弈"
        subtitle="随意选择AI强度和棋盘设置"
        icon={<SportsEsports fontSize="inherit" />}
        to="/kiosk/ai/setup/free"
      />
      <ModeCard
        title="升降级对弈"
        subtitle="根据实力自动匹配AI难度"
        icon={<EmojiEvents fontSize="inherit" />}
        to="/kiosk/ai/setup/ranked"
      />
    </Box>
  );
};

export default AiPlayPage;
```

**Step 2: Wire into KioskApp.tsx**

In `katrain/web/ui/src/kiosk/KioskApp.tsx`, add import and replace route:

```typescript
import AiPlayPage from './pages/AiPlayPage';
// ...
<Route path="ai" element={<AiPlayPage />} />
```

**Step 3: Verify in browser**

Visit: `http://localhost:5173/kiosk/ai`
Expected: Two large cards — "自由对弈" and "升降级对弈" — centered, with icons, touch-active styling.

**Step 4: Commit**

```bash
git add katrain/web/ui/src/kiosk/pages/AiPlayPage.tsx katrain/web/ui/src/kiosk/KioskApp.tsx
git commit -m "feat(kiosk): add Human vs AI selection page"
```

---

## Task 9: AI Game Setup Page

**Files:**
- Create: `katrain/web/ui/src/kiosk/pages/AiSetupPage.tsx`
- Modify: `katrain/web/ui/src/kiosk/KioskApp.tsx`

**Step 1: Create AiSetupPage**

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
    // TODO: POST /api/new-game → get sessionId → navigate
    navigate('/kiosk/ai/game/mock-session');
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
        }}
      >
        <Typography sx={{ color: 'rgba(0,0,0,0.3)' }}>{boardSize}x{boardSize}</Typography>
      </Box>

      {/* Right: settings form */}
      <Box sx={{ flex: 1, p: 3, overflow: 'auto', display: 'flex', flexDirection: 'column' }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 3 }}>
          <Button
            onClick={() => navigate('/kiosk/ai')}
            startIcon={<ArrowBack />}
            sx={{ minHeight: 40, minWidth: 40, p: 0.5 }}
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
          <Button variant="contained" fullWidth size="large" startIcon={<PlayArrow />} onClick={handleStart} sx={{ py: 2, fontSize: '1.1rem' }}>
            开始对弈
          </Button>
        </Box>
      </Box>
    </Box>
  );
};

export default AiSetupPage;
```

**Step 2: Wire route, verify at `/kiosk/ai/setup/free`, commit**

```bash
git add katrain/web/ui/src/kiosk/pages/AiSetupPage.tsx katrain/web/ui/src/kiosk/KioskApp.tsx
git commit -m "feat(kiosk): add AI game setup page with touch-friendly option chips"
```

---

## Task 10: Game Page with Mock Analysis

**Files:**
- Create: `katrain/web/ui/src/kiosk/components/game/MockBoard.tsx`
- Create: `katrain/web/ui/src/kiosk/components/game/GameControlPanel.tsx`
- Create: `katrain/web/ui/src/kiosk/pages/GamePage.tsx`
- Modify: `katrain/web/ui/src/kiosk/KioskApp.tsx` (add fullscreen game routes outside KioskLayout)

**Step 1: Create MockBoard**

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

**Step 2: Create GameControlPanel**

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

    {/* Controls — 3x2 grid of buttons */}
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

**Step 3: Create GamePage**

Create `katrain/web/ui/src/kiosk/pages/GamePage.tsx`:

```typescript
import { Box } from '@mui/material';
import MockBoard from '../components/game/MockBoard';
import GameControlPanel from '../components/game/GameControlPanel';

const GamePage = () => {
  const mock = {
    blackPlayer: '张三 (2D)', whitePlayer: 'KataGo 5D',
    blackCaptures: 3, whiteCaptures: 5, winRate: 56.3,
    bestMove: 'R16', bestMoveProb: 94.2, altMove: 'Q3', altMoveProb: 3.1, moveNumber: 42,
  };

  return (
    <Box sx={{ display: 'flex', height: '100vh', bgcolor: 'background.default' }}>
      <Box sx={{ height: '100%', aspectRatio: '1' }}>
        <MockBoard moveNumber={mock.moveNumber} />
      </Box>
      <Box sx={{ flex: 1, overflow: 'auto' }}>
        <GameControlPanel {...mock} />
      </Box>
    </Box>
  );
};

export default GamePage;
```

**Step 4: Wire fullscreen game routes in KioskApp.tsx**

Restructure KioskApp routes so game pages render WITHOUT KioskLayout (no tab bar):

```typescript
import GamePage from './pages/GamePage';
// ...
const KioskApp = () => (
  <Routes>
    {/* Fullscreen — no tab bar */}
    <Route path="ai/game/:sessionId" element={<GamePage />} />
    <Route path="pvp/local/game/:sessionId" element={<GamePage />} />
    <Route path="pvp/room/:sessionId" element={<GamePage />} />

    {/* Standard — with tab bar */}
    <Route element={<KioskLayout />}>
      {/* ... all tab routes ... */}
    </Route>
  </Routes>
);
```

**Step 5: Verify in browser**

Navigate: `/kiosk/ai` → 自由对弈 → 开始对弈
Expected: Fullscreen game with wood-colored mock board left, control panel right, NO tab bar.

**Step 6: Commit**

```bash
git add katrain/web/ui/src/kiosk/
git commit -m "feat(kiosk): add fullscreen GamePage with mock board and control panel"
```

---

## Task 11: Human vs Human Selection Page

**Files:**
- Create: `katrain/web/ui/src/kiosk/pages/PvpPlayPage.tsx`
- Modify: `katrain/web/ui/src/kiosk/KioskApp.tsx`

**Step 1: Create PvpPlayPage** (reuses ModeCard)

```typescript
// katrain/web/ui/src/kiosk/pages/PvpPlayPage.tsx
import { Box } from '@mui/material';
import { Handshake, Public } from '@mui/icons-material';
import ModeCard from '../components/common/ModeCard';

const PvpPlayPage = () => (
  <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', gap: 3, p: 3 }}>
    <ModeCard title="本地对局" subtitle="两人在智能棋盘上面对面对弈" icon={<Handshake fontSize="inherit" />} to="/kiosk/pvp/local/setup" />
    <ModeCard title="在线大厅" subtitle="匹配网络上的对手进行对弈" icon={<Public fontSize="inherit" />} to="/kiosk/pvp/lobby" />
  </Box>
);

export default PvpPlayPage;
```

**Step 2: Wire `<Route path="pvp" element={<PvpPlayPage />} />`, verify, commit**

```bash
git add katrain/web/ui/src/kiosk/pages/PvpPlayPage.tsx katrain/web/ui/src/kiosk/KioskApp.tsx
git commit -m "feat(kiosk): add Human vs Human selection page"
```

---

## Task 12: Tsumego Selection Page

**Files:**
- Create: `katrain/web/ui/src/kiosk/pages/TsumegoPage.tsx`
- Modify: `katrain/web/ui/src/kiosk/KioskApp.tsx`

**Step 1: Create TsumegoPage with mock problem grid**

```typescript
// katrain/web/ui/src/kiosk/pages/TsumegoPage.tsx
import { useState } from 'react';
import { Box, Typography, ButtonBase, Chip } from '@mui/material';
import { useNavigate } from 'react-router-dom';

const levels = ['入门', '初级', '中级', '高级'];
const mockProblems = levels.flatMap((level, li) =>
  Array.from({ length: 8 }, (_, i) => ({ id: `${li}-${i}`, label: `${level} ${i + 1}`, level, solved: Math.random() > 0.5 }))
);

const TsumegoPage = () => {
  const navigate = useNavigate();
  const [filter, setFilter] = useState('全部');
  const filtered = filter === '全部' ? mockProblems : mockProblems.filter((p) => p.level === filter);

  return (
    <Box sx={{ display: 'flex', height: '100%' }}>
      <Box sx={{ height: '100%', aspectRatio: '1', bgcolor: 'background.paper', display: 'flex', alignItems: 'center', justifyContent: 'center', borderRight: '1px solid', borderColor: 'divider' }}>
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

**Step 2: Wire route, verify, commit**

```bash
git add katrain/web/ui/src/kiosk/pages/TsumegoPage.tsx katrain/web/ui/src/kiosk/KioskApp.tsx
git commit -m "feat(kiosk): add Tsumego selection page with filterable problem grid"
```

---

## Task 13: Remaining Tab Pages (Research, Kifu, Live, Platforms, Settings)

Each follows the same left-board + right-panel pattern. Create one at a time, wire route, verify, commit.

**Files to create:**
- `katrain/web/ui/src/kiosk/pages/ResearchPage.tsx` — MockBoard left + analysis panel right with mock data
- `katrain/web/ui/src/kiosk/pages/KifuPage.tsx` — board preview left + scrollable game list right with mock data
- `katrain/web/ui/src/kiosk/pages/LivePage.tsx` — match list with mock upcoming/live matches
- `katrain/web/ui/src/kiosk/pages/PlatformsPage.tsx` — 2x2 card grid: 99围棋, 野狐围棋, 腾讯围棋, 新浪围棋
- `katrain/web/ui/src/kiosk/pages/SettingsPage.tsx` — language selector only

**For each page:**

**Step 1:** Create the page component with mock data
**Step 2:** Wire route in KioskApp.tsx (replace PlaceholderPage import)
**Step 3:** Verify in browser at `/kiosk/<tab-name>`
**Step 4:** Commit individually

```bash
git commit -m "feat(kiosk): add ResearchPage with mock analysis panel"
git commit -m "feat(kiosk): add KifuPage with mock game list"
git commit -m "feat(kiosk): add LivePage with mock match list"
git commit -m "feat(kiosk): add PlatformsPage with external platform cards"
git commit -m "feat(kiosk): add SettingsPage with language selector"
```

---

## Task 14: Run Full Test Suite and Visual Review

**Step 1: Run all kiosk tests**

Run: `cd katrain/web/ui && npx vitest run src/kiosk/`
Expected: All tests PASS

**Step 2: Run galaxy tests to confirm no regression**

Run: `cd katrain/web/ui && npx vitest run`
Expected: All existing tests still PASS

**Step 3: Visual walkthrough in browser**

Visit `http://localhost:5173/kiosk/` and tap through every tab:
- [ ] ⚔️ 人机 → two cards → setup → start → fullscreen game
- [ ] 👥 人人 → two cards
- [ ] 📖 死活 → problem grid → (problem page placeholder)
- [ ] 🔬 研究 → board + analysis
- [ ] 📋 棋谱 → game list
- [ ] 📡 直播 → match list
- [ ] 🌐 平台 → 4 platform cards
- [ ] ⚙️ 设置 → language selector

Visit `http://localhost:5173/galaxy/` and confirm unchanged.

**Step 4: Commit any fixes**

```bash
git commit -m "fix(kiosk): address visual review feedback"
```

---

## Future Phases (separate plans)

These phases will be planned in separate documents once Phase 1-2 (frontend mock) is validated:

- **Phase 3: Shared Layer Extraction** — Move Board.tsx, hooks, API, types to `src/shared/`, update imports in both galaxy and kiosk
- **Phase 4: Backend Integration** — Wire real game sessions, WebSocket, auth, tsumego API
- **Phase 5: Kiosk Infrastructure** — systemd services, Chromium kiosk, deployment script
- **Phase 6: Hardware Integration** — Board sensor driver, WebSocket `board_input` protocol
