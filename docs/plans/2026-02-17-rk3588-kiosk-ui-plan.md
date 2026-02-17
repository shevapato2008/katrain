# RK3588 Kiosk UI Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a touch-optimized kiosk UI variant for 7-10 inch smart Go board terminals, frontend-first with mock data.

**Architecture:** New `src/kiosk/` directory parallel to `src/galaxy/`, sharing backend API and core types. Single Vite build serves both UIs at different URL prefixes (`/galaxy/*` and `/kiosk/*`). "Ink Stone" dark theme with Noto font family, all touch targets >= 48px.

**Tech Stack:** React 19, TypeScript, MUI v7, React Router v6, Vite (rolldown-vite), Vitest

**Design doc:** `docs/plans/2026-02-17-rk3588-kiosk-ui-design.md`

---

## Phase 1: Scaffold & Theme (Tasks 1-4)

### Task 1: Create Kiosk Theme

**Files:**
- Create: `katrain/web/ui/src/kiosk/theme.ts`
- Test: `katrain/web/ui/src/kiosk/__tests__/theme.test.ts`

**Step 1: Write the failing test**

```typescript
// kiosk/__tests__/theme.test.ts
import { describe, it, expect } from 'vitest';
import { kioskTheme } from '../theme';

describe('kioskTheme', () => {
  it('uses dark mode with ink-black background', () => {
    expect(kioskTheme.palette.mode).toBe('dark');
    expect(kioskTheme.palette.background.default).toBe('#1a1714');
  });

  it('uses Noto Sans SC as primary font', () => {
    expect(kioskTheme.typography.fontFamily).toContain('Noto Sans SC');
  });

  it('has touch-friendly button sizing', () => {
    const buttonOverrides = kioskTheme.components?.MuiButton?.styleOverrides as any;
    expect(buttonOverrides.root.minHeight).toBe(56);
  });

  it('has jade-glow as primary color', () => {
    expect(kioskTheme.palette.primary.main).toBe('#5cb57a');
  });
});
```

**Step 2: Run test to verify it fails**

Run: `cd katrain/web/ui && npx vitest run src/kiosk/__tests__/theme.test.ts`
Expected: FAIL — module not found

**Step 3: Write minimal implementation**

```typescript
// kiosk/theme.ts
import { createTheme } from '@mui/material';

export const kioskTheme = createTheme({
  palette: {
    mode: 'dark',
    primary: {
      main: '#5cb57a',  // jade-glow
      light: '#7ec994',
      dark: '#2d5a3d',  // jade-deep
    },
    secondary: {
      main: '#8b7355',  // wood-amber
    },
    background: {
      default: '#1a1714',  // ink-black
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
    error: { main: '#c45d3e' },   // ember
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
  shape: {
    borderRadius: 12,
  },
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
          '&:active': {
            transform: 'scale(0.96)',
          },
        },
      },
    },
    MuiIconButton: {
      styleOverrides: {
        root: {
          minWidth: 48,
          minHeight: 48,
          '&:active': {
            transform: 'scale(0.96)',
          },
        },
      },
    },
    MuiPaper: {
      styleOverrides: {
        root: {
          backgroundImage: 'none',
        },
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
          '&.Mui-selected': {
            color: '#5cb57a',
          },
        },
      },
    },
  },
});
```

**Step 4: Run test to verify it passes**

Run: `cd katrain/web/ui && npx vitest run src/kiosk/__tests__/theme.test.ts`
Expected: PASS

**Step 5: Commit**

```bash
git add katrain/web/ui/src/kiosk/
git commit -m "feat(kiosk): add Ink Stone theme with touch-friendly sizing"
```

---

### Task 2: Create KioskLayout Shell

**Files:**
- Create: `katrain/web/ui/src/kiosk/components/layout/KioskLayout.tsx`
- Create: `katrain/web/ui/src/kiosk/components/layout/StatusBar.tsx`
- Create: `katrain/web/ui/src/kiosk/components/layout/BottomTabBar.tsx`
- Test: `katrain/web/ui/src/kiosk/__tests__/KioskLayout.test.tsx`

**Step 1: Write the failing test**

```typescript
// kiosk/__tests__/KioskLayout.test.tsx
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { ThemeProvider } from '@mui/material';
import { kioskTheme } from '../theme';
import KioskLayout from '../components/layout/KioskLayout';

const renderWithProviders = (ui: React.ReactElement, { route = '/' } = {}) => {
  return render(
    <ThemeProvider theme={kioskTheme}>
      <MemoryRouter initialEntries={[route]}>
        {ui}
      </MemoryRouter>
    </ThemeProvider>
  );
};

describe('KioskLayout', () => {
  it('renders status bar with KaTrain branding', () => {
    renderWithProviders(<KioskLayout />);
    expect(screen.getByText('KaTrain')).toBeInTheDocument();
  });

  it('renders all 8 bottom tabs', () => {
    renderWithProviders(<KioskLayout />);
    expect(screen.getByText('人机')).toBeInTheDocument();
    expect(screen.getByText('人人')).toBeInTheDocument();
    expect(screen.getByText('死活')).toBeInTheDocument();
    expect(screen.getByText('研究')).toBeInTheDocument();
    expect(screen.getByText('棋谱')).toBeInTheDocument();
    expect(screen.getByText('直播')).toBeInTheDocument();
    expect(screen.getByText('平台')).toBeInTheDocument();
    expect(screen.getByText('设置')).toBeInTheDocument();
  });
});
```

**Step 2: Run test to verify it fails**

Run: `cd katrain/web/ui && npx vitest run src/kiosk/__tests__/KioskLayout.test.tsx`
Expected: FAIL — modules not found

**Step 3: Write StatusBar component**

```typescript
// kiosk/components/layout/StatusBar.tsx
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
        <Box sx={{ width: 6, height: 6, borderRadius: '50%', bgcolor: 'success.main' }} />
      </Box>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
        <Typography variant="caption" sx={{ color: 'text.secondary' }}>
          {new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
        </Typography>
      </Box>
    </Box>
  );
};

export default StatusBar;
```

**Step 4: Write BottomTabBar component**

```typescript
// kiosk/components/layout/BottomTabBar.tsx
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

  const currentTab = tabs.findIndex((tab) => location.pathname.startsWith(tab.path));

  return (
    <BottomNavigation
      value={currentTab === -1 ? 0 : currentTab}
      onChange={(_, newValue) => navigate(tabs[newValue].path)}
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

**Step 5: Write KioskLayout component**

```typescript
// kiosk/components/layout/KioskLayout.tsx
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

**Step 6: Run test to verify it passes**

Run: `cd katrain/web/ui && npx vitest run src/kiosk/__tests__/KioskLayout.test.tsx`
Expected: PASS

**Step 7: Commit**

```bash
git add katrain/web/ui/src/kiosk/
git commit -m "feat(kiosk): add KioskLayout with StatusBar and BottomTabBar"
```

---

### Task 3: Create KioskApp Entry and Wire Router

**Files:**
- Create: `katrain/web/ui/src/kiosk/KioskApp.tsx`
- Create: `katrain/web/ui/src/kiosk/pages/PlaceholderPage.tsx`
- Modify: `katrain/web/ui/src/AppRouter.tsx`

**Step 1: Create placeholder page for all tabs**

```typescript
// kiosk/pages/PlaceholderPage.tsx
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
      <Typography variant="h3" sx={{ color: 'text.secondary', opacity: 0.5 }}>
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

**Step 2: Create KioskApp with routes**

```typescript
// kiosk/KioskApp.tsx
import { Routes, Route, Navigate } from 'react-router-dom';
import KioskLayout from './components/layout/KioskLayout';
import PlaceholderPage from './pages/PlaceholderPage';

const KioskApp = () => {
  return (
    <Routes>
      <Route element={<KioskLayout />}>
        <Route index element={<Navigate to="/kiosk/ai" replace />} />
        <Route path="ai" element={<PlaceholderPage />} />
        <Route path="ai/setup/:mode" element={<PlaceholderPage />} />
        <Route path="ai/game/:sessionId" element={<PlaceholderPage />} />
        <Route path="pvp" element={<PlaceholderPage />} />
        <Route path="pvp/local/game/:sessionId" element={<PlaceholderPage />} />
        <Route path="pvp/lobby" element={<PlaceholderPage />} />
        <Route path="pvp/room/:sessionId" element={<PlaceholderPage />} />
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
    </Routes>
  );
};

export default KioskApp;
```

**Step 3: Add kiosk route to AppRouter.tsx**

Modify `katrain/web/ui/src/AppRouter.tsx`:

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

**Step 4: Verify in browser**

Run: `cd katrain/web/ui && npm run dev`
Visit: `http://localhost:5173/kiosk/`
Expected: See status bar, "AI" placeholder content, 8 bottom tabs. Clicking tabs switches placeholder text.

**Step 5: Commit**

```bash
git add katrain/web/ui/src/kiosk/ katrain/web/ui/src/AppRouter.tsx
git commit -m "feat(kiosk): wire KioskApp into AppRouter with all tab routes"
```

---

### Task 4: Add Noto + JetBrains Mono Font Assets

**Files:**
- Modify: `katrain/web/ui/index.html` (or create `katrain/web/ui/src/kiosk/styles/fonts.css`)

**Step 1: Add font imports for kiosk**

Create `katrain/web/ui/src/kiosk/styles/fonts.css`:

```css
/* Local-first font loading for embedded terminal (no network dependency) */
/* Fallback to Google Fonts CDN for dev environment */
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+SC:wght@400;500;600;700&family=Noto+Serif+SC:wght@600;700&family=JetBrains+Mono:wght@400;500&display=swap');
```

Note: For production RK3588 deployment, fonts will be bundled locally. CDN is dev-only fallback.

**Step 2: Import in KioskApp**

Add to top of `kiosk/KioskApp.tsx`:
```typescript
import './styles/fonts.css';
```

**Step 3: Verify in browser**

Visit `http://localhost:5173/kiosk/`, inspect font rendering in DevTools.
Expected: Noto Sans SC for body text, serif headings visible in placeholder.

**Step 4: Commit**

```bash
git add katrain/web/ui/src/kiosk/
git commit -m "feat(kiosk): add Noto and JetBrains Mono font loading"
```

---

## Phase 2: Core Pages with Mock Data (Tasks 5-12)

### Task 5: Human vs AI Selection Page

**Files:**
- Create: `katrain/web/ui/src/kiosk/pages/AiPlayPage.tsx`
- Create: `katrain/web/ui/src/kiosk/components/common/ModeCard.tsx`
- Modify: `katrain/web/ui/src/kiosk/KioskApp.tsx` (replace placeholder)

**Step 1: Create reusable ModeCard component**

```typescript
// kiosk/components/common/ModeCard.tsx
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

**Step 2: Create AiPlayPage**

```typescript
// kiosk/pages/AiPlayPage.tsx
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

**Step 3: Wire into KioskApp — replace placeholder for `ai` route**

In `kiosk/KioskApp.tsx`, import `AiPlayPage` and replace:
```typescript
<Route path="ai" element={<AiPlayPage />} />
```

**Step 4: Verify in browser**

Visit `http://localhost:5173/kiosk/ai`
Expected: Two large cards side by side — "自由对弈" and "升降级对弈"

**Step 5: Commit**

```bash
git add katrain/web/ui/src/kiosk/
git commit -m "feat(kiosk): add Human vs AI selection page with ModeCard"
```

---

### Task 6: AI Game Setup Page

**Files:**
- Create: `katrain/web/ui/src/kiosk/pages/AiSetupPage.tsx`
- Create: `katrain/web/ui/src/kiosk/components/common/OptionChips.tsx`

**Step 1: Create OptionChips reusable selector**

```typescript
// kiosk/components/common/OptionChips.tsx
import { Box, ButtonBase, Typography } from '@mui/material';

interface OptionChipsProps<T extends string | number> {
  label: string;
  options: { value: T; label: string }[];
  value: T;
  onChange: (value: T) => void;
}

function OptionChips<T extends string | number>({ label, options, value, onChange }: OptionChipsProps<T>) {
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

**Step 2: Create AiSetupPage with mock state**

```typescript
// kiosk/pages/AiSetupPage.tsx
import { useState } from 'react';
import { Box, Typography, Button, Slider } from '@mui/material';
import { useParams, useNavigate } from 'react-router-dom';
import { PlayArrow } from '@mui/icons-material';
import OptionChips from '../components/common/OptionChips';

const AiSetupPage = () => {
  const { mode } = useParams<{ mode: string }>();
  const navigate = useNavigate();
  const [boardSize, setBoardSize] = useState(19);
  const [color, setColor] = useState<'black' | 'white'>('black');
  const [aiStrength, setAiStrength] = useState(5);
  const [handicap, setHandicap] = useState(0);
  const [timeLimit, setTimeLimit] = useState(0);

  const isRanked = mode === 'ranked';

  const handleStart = () => {
    // TODO: call backend to create session, navigate to game page
    navigate('/kiosk/ai/game/mock-session-id');
  };

  return (
    <Box sx={{ display: 'flex', height: '100%' }}>
      {/* Left: board preview */}
      <Box
        sx={{
          aspectRatio: '1',
          height: '100%',
          bgcolor: 'background.paper',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          borderRight: '1px solid',
          borderColor: 'divider',
        }}
      >
        <Typography variant="h6" sx={{ color: 'text.secondary', opacity: 0.3 }}>
          {boardSize}x{boardSize} 棋盘预览
        </Typography>
      </Box>

      {/* Right: settings */}
      <Box sx={{ flex: 1, p: 3, overflow: 'auto', display: 'flex', flexDirection: 'column' }}>
        <Typography variant="h5" sx={{ mb: 3 }}>
          {isRanked ? '升降级对弈' : '自由对弈'}
        </Typography>

        <OptionChips
          label="棋盘"
          options={[
            { value: 9, label: '9路' },
            { value: 13, label: '13路' },
            { value: 19, label: '19路' },
          ]}
          value={boardSize}
          onChange={setBoardSize}
        />

        <OptionChips
          label="我执"
          options={[
            { value: 'black' as const, label: '● 黑' },
            { value: 'white' as const, label: '○ 白' },
          ]}
          value={color}
          onChange={setColor}
        />

        {!isRanked && (
          <Box sx={{ mb: 2.5 }}>
            <Typography variant="body2" sx={{ color: 'text.secondary', mb: 1 }}>
              AI 强度: ~{aiStrength}D
            </Typography>
            <Slider
              value={aiStrength}
              onChange={(_, v) => setAiStrength(v as number)}
              min={-20}
              max={9}
              step={1}
              sx={{ mx: 1 }}
            />
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
          options={[
            { value: 0, label: '不限' },
            { value: 10, label: '10分' },
            { value: 20, label: '20分' },
            { value: 30, label: '30分' },
          ]}
          value={timeLimit}
          onChange={setTimeLimit}
        />

        <Box sx={{ mt: 'auto', pt: 2 }}>
          <Button
            variant="contained"
            fullWidth
            size="large"
            startIcon={<PlayArrow />}
            onClick={handleStart}
            sx={{ py: 2, fontSize: '1.1rem' }}
          >
            开始对弈
          </Button>
        </Box>
      </Box>
    </Box>
  );
};

export default AiSetupPage;
```

**Step 3: Wire route in KioskApp**

```typescript
<Route path="ai/setup/:mode" element={<AiSetupPage />} />
```

**Step 4: Verify in browser**

Visit `http://localhost:5173/kiosk/ai`, click "自由对弈"
Expected: Left board preview + right panel with chip selectors, slider, start button

**Step 5: Commit**

```bash
git add katrain/web/ui/src/kiosk/
git commit -m "feat(kiosk): add AI game setup page with touch-friendly controls"
```

---

### Task 7: Game Page with Mock Analysis Data

**Files:**
- Create: `katrain/web/ui/src/kiosk/pages/GamePage.tsx`
- Create: `katrain/web/ui/src/kiosk/components/game/GameControlPanel.tsx`
- Create: `katrain/web/ui/src/kiosk/components/game/MockBoard.tsx`

This is the core page. Use a mock board placeholder initially (real Board component will be wired in shared layer extraction phase).

**Step 1: Create MockBoard placeholder**

```typescript
// kiosk/components/game/MockBoard.tsx
import { Box, Typography } from '@mui/material';

interface MockBoardProps {
  moveNumber?: number;
}

const MockBoard = ({ moveNumber = 0 }: MockBoardProps) => {
  return (
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
      {/* Grid lines placeholder */}
      <Box
        sx={{
          position: 'absolute',
          inset: '8%',
          backgroundImage:
            'repeating-linear-gradient(0deg, transparent, transparent calc(100%/18 - 1px), rgba(0,0,0,0.3) calc(100%/18 - 1px), rgba(0,0,0,0.3) calc(100%/18)), ' +
            'repeating-linear-gradient(90deg, transparent, transparent calc(100%/18 - 1px), rgba(0,0,0,0.3) calc(100%/18 - 1px), rgba(0,0,0,0.3) calc(100%/18))',
        }}
      />
      <Typography variant="caption" sx={{ color: 'rgba(0,0,0,0.4)', zIndex: 1 }}>
        棋盘 (手数: {moveNumber})
      </Typography>
    </Box>
  );
};

export default MockBoard;
```

**Step 2: Create GameControlPanel**

```typescript
// kiosk/components/game/GameControlPanel.tsx
import { Box, Typography, Button, LinearProgress, IconButton, Divider } from '@mui/material';
import {
  Undo as UndoIcon,
  PanTool as PassIcon,
  Calculate as CountIcon,
  Flag as ResignIcon,
  Settings as SettingsIcon,
  Close as ExitIcon,
} from '@mui/icons-material';

interface GameControlPanelProps {
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

const GameControlPanel = ({
  blackPlayer,
  whitePlayer,
  blackCaptures,
  whiteCaptures,
  winRate,
  bestMove,
  bestMoveProb,
  altMove,
  altMoveProb,
  moveNumber,
}: GameControlPanelProps) => {
  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        p: 2,
        gap: 1.5,
      }}
    >
      {/* Players */}
      <Box>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
          <Typography variant="body1" sx={{ fontWeight: 600 }}>
            ● {blackPlayer}
          </Typography>
          <Typography variant="caption">○ 提: {blackCaptures}</Typography>
        </Box>
        <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
          <Typography variant="body1" sx={{ fontWeight: 600 }}>
            ○ {whitePlayer}
          </Typography>
          <Typography variant="caption">● 提: {whiteCaptures}</Typography>
        </Box>
      </Box>

      <Divider />

      {/* Win rate */}
      <Box>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
          <Typography variant="body2" sx={{ color: 'text.secondary' }}>胜率</Typography>
          <Typography
            variant="body1"
            sx={{ fontFamily: "'JetBrains Mono', monospace", fontWeight: 600 }}
          >
            {winRate.toFixed(1)}%
          </Typography>
        </Box>
        <LinearProgress
          variant="determinate"
          value={winRate}
          sx={{
            height: 8,
            borderRadius: 4,
            bgcolor: 'rgba(232, 228, 220, 0.1)',
            '& .MuiLinearProgress-bar': {
              bgcolor: winRate > 50 ? 'success.main' : 'error.main',
              borderRadius: 4,
            },
          }}
        />
      </Box>

      {/* AI suggestions */}
      <Box>
        <Typography variant="body2" sx={{ color: 'text.secondary', mb: 0.5 }}>AI 推荐</Typography>
        <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
          <Typography variant="body1" sx={{ color: 'primary.main', fontWeight: 600 }}>
            {bestMove}
          </Typography>
          <Typography variant="caption" sx={{ fontFamily: "'JetBrains Mono', monospace" }}>
            {bestMoveProb.toFixed(1)}%
          </Typography>
        </Box>
        <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
          <Typography variant="body2" sx={{ color: 'text.secondary' }}>
            {altMove}
          </Typography>
          <Typography variant="caption" sx={{ fontFamily: "'JetBrains Mono', monospace", color: 'text.secondary' }}>
            {altMoveProb.toFixed(1)}%
          </Typography>
        </Box>
      </Box>

      <Typography variant="caption" sx={{ color: 'text.secondary' }}>
        第 {moveNumber} 手
      </Typography>

      <Box sx={{ mt: 'auto' }} />

      {/* Control buttons */}
      <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 1 }}>
        <Button variant="outlined" startIcon={<UndoIcon />} sx={{ minHeight: 48 }}>
          悔棋
        </Button>
        <Button variant="outlined" startIcon={<PassIcon />} sx={{ minHeight: 48 }}>
          跳过
        </Button>
        <Button variant="outlined" startIcon={<CountIcon />} sx={{ minHeight: 48 }}>
          计数
        </Button>
        <Button variant="outlined" color="error" startIcon={<ResignIcon />} sx={{ minHeight: 48 }}>
          认输
        </Button>
        <Button variant="outlined" startIcon={<SettingsIcon />} sx={{ minHeight: 48 }}>
          设置
        </Button>
        <Button variant="outlined" startIcon={<ExitIcon />} sx={{ minHeight: 48 }}>
          退出
        </Button>
      </Box>
    </Box>
  );
};

export default GameControlPanel;
```

**Step 3: Create GamePage**

```typescript
// kiosk/pages/GamePage.tsx
import { Box, Typography } from '@mui/material';
import { useParams } from 'react-router-dom';
import MockBoard from '../components/game/MockBoard';
import GameControlPanel from '../components/game/GameControlPanel';

const GamePage = () => {
  const { sessionId } = useParams();

  // Mock data — will be replaced by useGameSession hook
  const mockData = {
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

  return (
    <Box sx={{ display: 'flex', height: '100%' }}>
      {/* Status bar override for game */}
      <Box
        sx={{
          position: 'absolute',
          top: 0,
          left: 0,
          right: 0,
          height: 40,
          display: 'flex',
          alignItems: 'center',
          px: 2,
          bgcolor: 'background.default',
          borderBottom: '1px solid',
          borderColor: 'divider',
          zIndex: 10,
        }}
      >
        <Typography variant="body2" sx={{ fontWeight: 600 }}>
          ● {mockData.blackPlayer} vs ○ {mockData.whitePlayer}
        </Typography>
        <Typography variant="caption" sx={{ ml: 'auto', color: 'text.secondary' }}>
          {sessionId}
        </Typography>
      </Box>

      {/* Board area */}
      <Box sx={{ height: '100%', aspectRatio: '1', pt: '40px' }}>
        <MockBoard moveNumber={mockData.moveNumber} />
      </Box>

      {/* Control panel */}
      <Box sx={{ flex: 1, pt: '40px', overflow: 'auto' }}>
        <GameControlPanel {...mockData} />
      </Box>
    </Box>
  );
};

export default GamePage;
```

**Step 4: Wire route — GamePage hides tab bar**

In KioskApp.tsx, game routes render outside KioskLayout (no tab bar):

```typescript
<Routes>
  {/* Fullscreen pages (no tab bar) */}
  <Route path="ai/game/:sessionId" element={<GamePage />} />
  <Route path="pvp/local/game/:sessionId" element={<GamePage />} />
  <Route path="pvp/room/:sessionId" element={<GamePage />} />

  {/* Tab-bar pages */}
  <Route element={<KioskLayout />}>
    <Route index element={<Navigate to="/kiosk/ai" replace />} />
    <Route path="ai" element={<AiPlayPage />} />
    <Route path="ai/setup/:mode" element={<AiSetupPage />} />
    {/* ... rest of tab routes */}
  </Route>
</Routes>
```

**Step 5: Verify in browser**

Navigate: Kiosk → 人机 → 自由对弈 → 开始对弈
Expected: Fullscreen game page with mock board on left, control panel on right, no bottom tab bar

**Step 6: Commit**

```bash
git add katrain/web/ui/src/kiosk/
git commit -m "feat(kiosk): add GamePage with mock board and control panel"
```

---

### Task 8: Human vs Human Selection Page

**Files:**
- Create: `katrain/web/ui/src/kiosk/pages/PvpPlayPage.tsx`

**Step 1: Create PvpPlayPage** (reuses ModeCard from Task 5)

```typescript
// kiosk/pages/PvpPlayPage.tsx
import { Box } from '@mui/material';
import { Handshake, Public } from '@mui/icons-material';
import ModeCard from '../components/common/ModeCard';

const PvpPlayPage = () => {
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
        title="本地对局"
        subtitle="两人在智能棋盘上面对面对弈"
        icon={<Handshake fontSize="inherit" />}
        to="/kiosk/pvp/local/setup"
      />
      <ModeCard
        title="在线大厅"
        subtitle="匹配网络上的对手进行对弈"
        icon={<Public fontSize="inherit" />}
        to="/kiosk/pvp/lobby"
      />
    </Box>
  );
};

export default PvpPlayPage;
```

**Step 2: Wire route, verify, commit**

```bash
git commit -m "feat(kiosk): add Human vs Human selection page"
```

---

### Task 9: Tsumego Selection Page

**Files:**
- Create: `katrain/web/ui/src/kiosk/pages/TsumegoPage.tsx`

**Step 1: Create TsumegoPage with mock problem grid**

```typescript
// kiosk/pages/TsumegoPage.tsx
import { useState } from 'react';
import { Box, Typography, ButtonBase, Chip } from '@mui/material';
import { useNavigate } from 'react-router-dom';

const levels = ['入门', '初级', '中级', '高级'];

const mockProblems = levels.flatMap((level, li) =>
  Array.from({ length: 8 }, (_, i) => ({
    id: `${li}-${i}`,
    label: `${level} ${i + 1}`,
    level,
    solved: Math.random() > 0.5,
  }))
);

const TsumegoPage = () => {
  const navigate = useNavigate();
  const [filter, setFilter] = useState<string>('全部');

  const filtered = filter === '全部' ? mockProblems : mockProblems.filter((p) => p.level === filter);

  return (
    <Box sx={{ display: 'flex', height: '100%' }}>
      {/* Left: preview area */}
      <Box
        sx={{
          height: '100%',
          aspectRatio: '1',
          bgcolor: 'background.paper',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          borderRight: '1px solid',
          borderColor: 'divider',
        }}
      >
        <Typography variant="body2" sx={{ color: 'text.secondary', opacity: 0.3 }}>
          题目预览
        </Typography>
      </Box>

      {/* Right: problem grid */}
      <Box sx={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        {/* Filter bar */}
        <Box sx={{ display: 'flex', gap: 1, p: 2, pb: 1, flexShrink: 0 }}>
          {['全部', ...levels].map((l) => (
            <Chip
              key={l}
              label={l}
              onClick={() => setFilter(l)}
              variant={filter === l ? 'filled' : 'outlined'}
              color={filter === l ? 'primary' : 'default'}
              sx={{ minHeight: 40, fontSize: '0.9rem' }}
            />
          ))}
        </Box>

        {/* Problem grid */}
        <Box
          sx={{
            flex: 1,
            overflow: 'auto',
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(100px, 1fr))',
            gap: 1,
            p: 2,
            pt: 1,
            alignContent: 'start',
          }}
        >
          {filtered.map((p) => (
            <ButtonBase
              key={p.id}
              onClick={() => navigate(`/kiosk/tsumego/problem/${p.id}`)}
              sx={{
                minHeight: 56,
                borderRadius: 2,
                bgcolor: p.solved ? 'primary.dark' : 'background.paper',
                border: '1px solid',
                borderColor: p.solved ? 'primary.main' : 'divider',
                '&:active': { transform: 'scale(0.96)' },
              }}
            >
              <Typography variant="body2" sx={{ fontWeight: 500 }}>
                {p.label}
              </Typography>
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
git commit -m "feat(kiosk): add Tsumego selection page with problem grid"
```

---

### Task 10: Research Page

**Files:**
- Create: `katrain/web/ui/src/kiosk/pages/ResearchPage.tsx`

Similar layout to GamePage but with touch-to-place board and analysis panel. Uses MockBoard initially. Wire route, verify, commit.

```bash
git commit -m "feat(kiosk): add Research page shell with mock board"
```

---

### Task 11: Kifu Library Page

**Files:**
- Create: `katrain/web/ui/src/kiosk/pages/KifuPage.tsx`

Left: board preview. Right: scrollable game list with mock data (player names, date, result). Wire route, verify, commit.

```bash
git commit -m "feat(kiosk): add Kifu library page with mock game list"
```

---

### Task 12: Remaining Pages (Live, Platforms, Settings)

**Files:**
- Create: `katrain/web/ui/src/kiosk/pages/LivePage.tsx` — match list with mock data
- Create: `katrain/web/ui/src/kiosk/pages/PlatformsPage.tsx` — large card grid for external platforms
- Create: `katrain/web/ui/src/kiosk/pages/SettingsPage.tsx` — language selector only

Each follows the same pattern: create page component, wire route, verify in browser, commit individually.

```bash
git commit -m "feat(kiosk): add Live, Platforms, and Settings pages"
```

---

## Phase 3: Shared Layer Extraction (Tasks 13-16)

### Task 13: Extract Board.tsx to shared/

Move `katrain/web/ui/src/components/Board.tsx` → `katrain/web/ui/src/shared/components/Board.tsx`. Update galaxy imports. Add touch event handlers for kiosk. This is the largest refactor task.

### Task 14: Extract API and WebSocket Layer

Move `galaxy/hooks/useGameSession.ts`, `galaxy/api/`, types to `shared/`. Update galaxy imports.

### Task 15: Extract Auth and Settings Contexts

Move `galaxy/context/AuthContext.tsx` and `galaxy/context/SettingsContext.tsx` to `shared/context/`. Both UIs need auth and i18n.

### Task 16: Wire Kiosk Pages to Shared Components

Replace MockBoard with real Board component. Wire useGameSession, auth, and settings into kiosk pages.

---

## Phase 4: Backend Integration (Tasks 17-20)

### Task 17: Serve Kiosk at /kiosk/* Path

Configure Vite proxy and FastAPI static file serving to handle `/kiosk/*` routes.

### Task 18: Connect Game Sessions

Wire AiSetupPage to POST `/api/new-game`, GamePage to WebSocket, controls to REST endpoints.

### Task 19: Connect Tsumego, Research, Kifu

Wire each module to its corresponding backend API.

### Task 20: Connect Auth Flow

Wire login page to `/api/v1/auth/login`, integrate token storage, protect routes.

---

## Phase 5: Kiosk Infrastructure (Tasks 21-22)

### Task 21: Create systemd Service Files

Create `deploy/rk3588/katrain-server.service` and `deploy/rk3588/katrain-kiosk.service`.

### Task 22: Create Deployment Script

Create `deploy/rk3588/setup.sh` to install services, configure auto-login, set up Chromium kiosk.

---

## Phase 6: Hardware Integration (Tasks 23-24)

### Task 23: Board Input WebSocket Protocol

Add `board_input` and `board_sync` message types to backend WebSocket handler.

### Task 24: Hardware Driver Service

Create Python service that reads sensor data and forwards to KaTrain backend.
