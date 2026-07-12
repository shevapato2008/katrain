# Kiosk Nav & Page Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix three kiosk UI problems — (1) show the bottom Dock only on first-level pages and give every deeper page a back affordance, (2) promote 跨平台对弈 to a sibling section on the 对弈 hub that lists platforms directly, (3) make the 对弈 setup pages compact enough that 开始对弈 is visible without scrolling.

**Architecture:** All changes are inside `katrain/web/ui/src/kiosk/` plus one shared file (`Board.tsx` is NOT touched here). Add one shared `SubPageBar` component; make `KioskLayout` route-aware so the Dock renders only on the 8 L1 tab roots; restructure `PlayPage` into three sibling sections; rebuild `AiSetupPage` as a 2-column dropdown form. No build-boundary changes — this plan keeps the kiosk-2d bundle exactly as-is (no three.js).

**Tech Stack:** React 19 + TypeScript + Vite + MUI (`@mui/material`), Vitest + Testing Library. Kiosk theme tokens in `src/kiosk/theme.ts`. Test runner: `npm run test` (`vitest run`) from `katrain/web/ui/`.

## Global Constraints

- Device target: 7″ landscape, **1024 × 600**. Everything must fit without vertical scroll on the 对弈 hub and the setup pages.
- Kiosk is Simplified-Chinese first. Every user-facing string uses `t('English key', '中文默认')` (see `src/kiosk/hooks/useTranslation`). Never hardcode a bare Chinese or English string.
- Reuse existing kiosk theme tokens only (jade `#58b57a`, slate `#0f1416`, raise `#18211f`, `--raise2 #1d2725`, hair `#2b3a35`, ice `#eef3f1`, sub `#93a49d`). No new palette.
- **Do not import anything under `src/galaxy/**`, `src/components/Board3D/**`, or `src/pages/VideoRecorderPage*` from `src/kiosk/**`** — the eslint `no-restricted-imports` guard and `verify:kiosk-2d` will fail. This plan needs none of them.
- Shared-territory rule: this plan touches only `src/kiosk/**`. After it lands, run BOTH `npm run build` and `npm run build:kiosk-2d` — both must be green.
- Format check before every commit: `npm run lint` (eslint) must pass.

---

### Task 1: Shared `SubPageBar` back-bar component

A reusable top bar for every non-L1 page: a large touch back button + a page title (+ optional right slot). Replaces the ~13 inconsistent inline back buttons across deeper pages and gives the 4 pages that currently have none a back affordance (required once the Dock is hidden on deeper pages in Task 2).

**Files:**
- Create: `katrain/web/ui/src/kiosk/components/layout/SubPageBar.tsx`
- Test: `katrain/web/ui/src/kiosk/components/layout/SubPageBar.test.tsx`

**Interfaces:**
- Consumes: `useNavigate` (react-router-dom), `useTranslation` from `../../hooks/useTranslation`.
- Produces:
  ```ts
  interface SubPageBarProps {
    title: string;                 // already-translated page title
    onBack?: () => void;           // custom handler (stateful targets); wins over `to`
    to?: string;                   // static back route, e.g. '/kiosk/play'
    right?: React.ReactNode;       // optional right-aligned slot (status chips, actions)
  }
  export default function SubPageBar(props: SubPageBarProps): JSX.Element
  ```
  Back behavior: if `onBack` given, call it; else if `to` given, `navigate(to)`; else `navigate(-1)`.

- [ ] **Step 1: Write the failing test**

```tsx
// SubPageBar.test.tsx
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { vi } from 'vitest';
import SubPageBar from './SubPageBar';

const navigate = vi.fn();
vi.mock('react-router-dom', async (orig) => ({
  ...(await orig<typeof import('react-router-dom')>()),
  useNavigate: () => navigate,
}));

beforeEach(() => navigate.mockClear());

test('renders title and a back button', () => {
  render(<MemoryRouter><SubPageBar title="自由对弈" to="/kiosk/play" /></MemoryRouter>);
  expect(screen.getByText('自由对弈')).toBeInTheDocument();
  expect(screen.getByRole('button', { name: /返回|back/i })).toBeInTheDocument();
});

test('navigates to `to` when back pressed', () => {
  render(<MemoryRouter><SubPageBar title="x" to="/kiosk/play" /></MemoryRouter>);
  fireEvent.click(screen.getByRole('button', { name: /返回|back/i }));
  expect(navigate).toHaveBeenCalledWith('/kiosk/play');
});

test('prefers onBack over to', () => {
  const onBack = vi.fn();
  render(<MemoryRouter><SubPageBar title="x" to="/kiosk/play" onBack={onBack} /></MemoryRouter>);
  fireEvent.click(screen.getByRole('button', { name: /返回|back/i }));
  expect(onBack).toHaveBeenCalled();
  expect(navigate).not.toHaveBeenCalled();
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm run test -- SubPageBar` (from `katrain/web/ui/`)
Expected: FAIL — `Cannot find module './SubPageBar'`.

- [ ] **Step 3: Write minimal implementation**

```tsx
// SubPageBar.tsx
import { Box, Typography, Button } from '@mui/material';
import { ArrowBack } from '@mui/icons-material';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from '../../hooks/useTranslation';

interface SubPageBarProps {
  title: string;
  onBack?: () => void;
  to?: string;
  right?: React.ReactNode;
}

// Standard back bar for all non-L1 kiosk pages. The Dock is hidden on these
// routes (KioskLayout, Task 2), so this is the only way back up the stack.
const SubPageBar = ({ title, onBack, to, right }: SubPageBarProps) => {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const handleBack = () => {
    if (onBack) onBack();
    else if (to) navigate(to);
    else navigate(-1);
  };
  return (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, px: 2.5, py: 1.25,
      borderBottom: '1px solid', borderColor: 'divider', flexShrink: 0, minHeight: 52 }}>
      <Button onClick={handleBack} startIcon={<ArrowBack />} aria-label={t('Back', '返回')}
        sx={{ minHeight: 40, px: 1.75, color: 'text.primary', bgcolor: 'var(--raise2)',
          border: '1px solid', borderColor: 'divider' }}>
        {t('Back', '返回')}
      </Button>
      <Typography sx={{ fontSize: 17, fontWeight: 600, color: 'text.primary',
        overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{title}</Typography>
      {right && <Box sx={{ ml: 'auto', display: 'flex', alignItems: 'center', gap: 1 }}>{right}</Box>}
    </Box>
  );
};

export default SubPageBar;
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm run test -- SubPageBar`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add katrain/web/ui/src/kiosk/components/layout/SubPageBar.tsx katrain/web/ui/src/kiosk/components/layout/SubPageBar.test.tsx
git commit -m "feat(kiosk): shared SubPageBar back bar for non-L1 pages"
```

---

### Task 2: Route-aware Dock — show only on the 8 L1 roots

Make `KioskLayout` render the `Dock` only when the current path is one of the 8 first-level tab roots. On every deeper page the Dock is hidden (the page supplies its own `SubPageBar`). This is the core of requirement (1).

**Files:**
- Modify: `katrain/web/ui/src/kiosk/components/layout/navTabs.tsx` (export the L1 path set)
- Modify: `katrain/web/ui/src/kiosk/components/layout/KioskLayout.tsx:8-24`
- Test: `katrain/web/ui/src/kiosk/components/layout/KioskLayout.test.tsx`

**Interfaces:**
- Consumes: `primaryTabs`, `settingsTab` from `./navTabs` (existing, `path` field).
- Produces: `export const L1_PATHS: string[]` in `navTabs.tsx` — the exact pathnames where the Dock shows.

- [ ] **Step 1: Add the L1 path set to navTabs.tsx**

Append to `katrain/web/ui/src/kiosk/components/layout/navTabs.tsx` (after `settingsTab`):

```ts
// The 8 first-level routes where the bottom Dock is shown. Every other kiosk
// route is a deeper page: Dock hidden, SubPageBar (back) shown instead.
export const L1_PATHS: string[] = [...primaryTabs, settingsTab].map((t) => t.path);
```

- [ ] **Step 2: Write the failing test**

```tsx
// KioskLayout.test.tsx
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import KioskLayout from './KioskLayout';

// Dock renders the 对弈 label; assert its presence/absence by route.
function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route element={<KioskLayout username="友" />}>
          <Route path="/kiosk/play" element={<div>hub</div>} />
          <Route path="/kiosk/play/ai/setup/:mode" element={<div>setup</div>} />
        </Route>
      </Routes>
    </MemoryRouter>,
  );
}

test('Dock shows on L1 play', () => {
  renderAt('/kiosk/play');
  expect(screen.getByText('对弈')).toBeInTheDocument();
});

test('Dock hidden on deeper setup page', () => {
  renderAt('/kiosk/play/ai/setup/free');
  expect(screen.queryByText('对弈')).not.toBeInTheDocument();
});
```

- [ ] **Step 3: Run test to verify it fails**

Run: `npm run test -- KioskLayout`
Expected: FAIL — second test finds 对弈 (Dock renders on all routes today).

- [ ] **Step 4: Implement — gate the Dock in KioskLayout**

Edit `KioskLayout.tsx`. Add the import and an `isL1` check; gate `<Dock />` on it:

```tsx
import { L1_PATHS } from './navTabs';
// ...
const KioskShell = ({ username }: KioskLayoutProps) => {
  const { immersive } = useImmersive();
  const location = useLocation();
  const isL1 = L1_PATHS.includes(location.pathname);
  const showConsole = !immersive && CONSOLE_ROUTES.includes(location.pathname);
  const showDock = !immersive && isL1;   // Dock only on first-level pages
  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%', width: '100%', overflow: 'hidden', bgcolor: 'background.default' }}>
      {!immersive && <Header username={username} />}
      <Box sx={{ display: 'flex', flex: 1, minHeight: 0, overflow: 'hidden' }}>
        {showConsole && <SmartBoardConsole />}
        <Box component="main" sx={{ flex: 1, minWidth: 0, overflow: 'auto', display: 'flex', flexDirection: 'column' }}>
          <Outlet />
        </Box>
      </Box>
      {showDock && <Dock />}
    </Box>
  );
};
```

- [ ] **Step 5: Run test to verify it passes**

Run: `npm run test -- KioskLayout`
Expected: PASS (2 tests).

- [ ] **Step 6: Commit**

```bash
git add katrain/web/ui/src/kiosk/components/layout/navTabs.tsx katrain/web/ui/src/kiosk/components/layout/KioskLayout.tsx katrain/web/ui/src/kiosk/components/layout/KioskLayout.test.tsx
git commit -m "feat(kiosk): show Dock only on L1 pages; deeper pages get back bar"
```

---

### Task 3: Add back bars to the pages that lack one; migrate the rest to SubPageBar

Once the Dock is hidden on deeper pages, any page without a back affordance is a dead-end. Three components lack one and MUST get a `SubPageBar`: `PlaceholderPage` (used by `play/pvp/setup` and `kifu/:kifuId`), `PlatformConnectPage` (`play/cross-platform`), `PlatformLobbyPage` (`play/cross-platform/lobby`). Then migrate the pages that already have ad-hoc back buttons to the shared bar for consistency (stateful targets preserved via `onBack`).

**Files:**
- Modify: `katrain/web/ui/src/kiosk/pages/PlaceholderPage.tsx` — add SubPageBar (target `navigate(-1)` — it serves two different parents).
- Modify: `katrain/web/ui/src/kiosk/pages/PlatformConnectPage.tsx:131-138` — replace the plain `Typography` header with `SubPageBar title="跨平台对弈" to="/kiosk/play"`.
- Modify: `katrain/web/ui/src/kiosk/pages/PlatformLobbyPage.tsx` — add `SubPageBar title=<platform> to="/kiosk/play/cross-platform"`.
- Modify (migrate, one per file): `AiSetupPage.tsx` (Task 5 rebuilds it — skip here), `LobbyPage.tsx:176`, `PlatformEngineSetupPage.tsx:202-209`, `TsumegoCategoriesPage.tsx`, `TsumegoLevelPage.tsx`, `TsumegoUnitsPage.tsx`, `TsumegoUnitListPage.tsx`, `TsumegoProblemPage.tsx` (stateful — use `onBack={goToUnits}`), `BaipuSessionPage.tsx`, `LiveMatchPage.tsx`, `TutorialBooksPage.tsx`, `TutorialBookDetailPage.tsx` (stateful `onBack`), `TutorialSectionPage.tsx` (stateful `onBack`).
- Test: `katrain/web/ui/src/kiosk/pages/PlatformConnectPage.test.tsx` (new — assert back bar present).

**Interfaces:**
- Consumes: `SubPageBar` (Task 1). Import as `import SubPageBar from '../components/layout/SubPageBar';`.

- [ ] **Step 1: Write the failing test (the required additions — dead-end pages)**

```tsx
// PlatformConnectPage.test.tsx  (mock API.platformStatus to resolve [])
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { vi } from 'vitest';
vi.mock('../../api', () => ({ API: { platformStatus: vi.fn().mockResolvedValue({ platforms: [] }) } }));
vi.mock('../../context/AuthContext', () => ({ useAuth: () => ({ token: 't' }) }));
import PlatformConnectPage from './PlatformConnectPage';

test('cross-platform page has a back bar (not a dead-end without the Dock)', async () => {
  render(<MemoryRouter><PlatformConnectPage /></MemoryRouter>);
  await waitFor(() =>
    expect(screen.getByRole('button', { name: /返回|back/i })).toBeInTheDocument());
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm run test -- PlatformConnectPage`
Expected: FAIL — no back button in current PlatformConnectPage.

- [ ] **Step 3: Add SubPageBar to the three dead-end pages**

`PlatformConnectPage.tsx` — replace the outer heading block (lines 131-138) so the page is `SubPageBar` + the existing card grid. Wrap the return in a column `Box` that starts with:
```tsx
import SubPageBar from '../components/layout/SubPageBar';
// ...
return (
  <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
    <SubPageBar title={t('Cross-Platform Play', '跨平台对弈')} to="/kiosk/play" />
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, p: 3, flex: 1, minHeight: 0, overflow: 'auto' }}>
      {/* existing subtitle + platforms grid + login dialog unchanged */}
    </Box>
  </Box>
);
```
`PlaceholderPage.tsx` — wrap the centered label with a column and add `<SubPageBar title={t('Coming soon','敬请期待')} />` (defaults to `navigate(-1)`).
`PlatformLobbyPage.tsx` — add `<SubPageBar title={platformLabel} to="/kiosk/play/cross-platform" />` at the top of its render.

- [ ] **Step 4: Migrate the already-have-back-button pages (one commit per page or grouped)**

For each page in the migrate list, delete the inline `<Button ... startIcon={<ArrowBack/>}>` (and its `<ArrowBack>`/`<ArrowBackIcon>` import if now unused) and render `<SubPageBar title={<pageTitle>} to={<staticTarget>} />` — or `onBack={<existingHandler>}` where the target is stateful:
- `TsumegoProblemPage.tsx`: `onBack={goToUnits}` (keeps the flushProgress + level/category logic).
- `TutorialBookDetailPage.tsx`: `onBack={() => book ? navigate('/kiosk/tutorial/' + book.category) : navigate(-1)}`.
- `TutorialSectionPage.tsx`: `onBack={onBack}` (existing nav-state handler).
- All tsumego list pages, `LobbyPage`, `PlatformEngineSetupPage`, `BaipuSessionPage`, `LiveMatchPage`, `TutorialBooksPage`: use the static `to` targets documented in the page inventory.

Preserve each page's existing content layout below the bar; only the header/back region changes.

- [ ] **Step 5: Run tests + lint**

Run: `npm run test` then `npm run lint`
Expected: PASS. No `ArrowBack is defined but never used` lint errors (remove now-dead imports).

- [ ] **Step 6: Commit**

```bash
git add katrain/web/ui/src/kiosk/pages/
git commit -m "feat(kiosk): every deeper page uses SubPageBar; fix cross-platform/placeholder dead-ends"
```

---

### Task 4: 对弈 hub — 跨平台对弈 as a sibling section listing platforms

Rebuild `PlayPage` into three sibling sections: 人机对弈 (自由/升降级), 人人对弈 (本地/在线大厅), 跨平台对弈 (platform cards fetched from `API.platformStatus`). Remove the duplicated 跨平台 card that previously sat under both 人机 and 人人. This is requirement (2).

**Files:**
- Modify: `katrain/web/ui/src/kiosk/pages/PlayPage.tsx` (full rewrite of the sections)
- Modify: `katrain/web/ui/src/kiosk/pages/PlayPage.test.tsx`
- Reference (platform meta + fetch pattern): `PlatformConnectPage.tsx:18-32,47-59` (`PLATFORM_META`, `API.platformStatus`).

**Interfaces:**
- Consumes: `API.platformStatus(token)` → `{ platforms: PlatformInfo[] }` (from `src/api.ts`), `PlatformInfo` fields `platform, connected, saved_username, supports_engine_play`. `useAuth().token`.
- Produces: no new exports.

- [ ] **Step 1: Write the failing test**

```tsx
// PlayPage.test.tsx additions
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { vi } from 'vitest';
vi.mock('../../api', () => ({ API: { platformStatus: vi.fn().mockResolvedValue({
  platforms: [{ platform: 'golaxy', connected: true, saved_username: '13800000000', supports_engine_play: true }],
}) } }));
vi.mock('../../context/AuthContext', () => ({ useAuth: () => ({ user: { username: '友' }, token: 't' }) }));
import PlayPage from './PlayPage';

test('renders three sibling sections including 跨平台对弈', async () => {
  render(<MemoryRouter><PlayPage /></MemoryRouter>);
  expect(screen.getByText('人机对弈')).toBeInTheDocument();
  expect(screen.getByText('人人对弈')).toBeInTheDocument();
  expect(screen.getByText('跨平台对弈')).toBeInTheDocument();
  await waitFor(() => expect(screen.getByText('星阵围棋')).toBeInTheDocument());
});

test('does not render a duplicate 跨平台 mode card under 人机/人人', () => {
  render(<MemoryRouter><PlayPage /></MemoryRouter>);
  // The old duplicate ModeCard title. Platform cards use platform names, not this.
  expect(screen.queryByText('连接 OGS、野狐等平台')).not.toBeInTheDocument();
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm run test -- PlayPage`
Expected: FAIL — 跨平台对弈 label absent as a section; duplicate subtitle still present.

- [ ] **Step 3: Rewrite PlayPage sections**

Replace the two `ModeCard` grids (lines 79-124) with three sections. Keep greeting + resume bar. 人机 = 自由对弈 (primary) + 升降级对弈 only. 人人 = 本地对局 + 在线大厅 only. New 跨平台 section maps `platforms` to compact platform cards:

```tsx
// add state + fetch (mirror PlatformConnectPage)
const { user, token } = useAuth();
const [platforms, setPlatforms] = useState<PlatformInfo[]>([]);
useEffect(() => {
  if (!token) return;
  API.platformStatus(token).then((d) => setPlatforms(d.platforms)).catch(() => {});
}, [token]);

// ... after 人人对弈 grid:
<Typography sx={sectionLabelSx}>{t('Cross-Platform', '跨平台对弈')}</Typography>
<Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 1.5 }}>
  {platforms.map((p) => {
    const meta = PLATFORM_META[p.platform] ?? { label: p.platform, labelCn: p.platform, color: '#888' };
    const target = p.connected
      ? (p.supports_engine_play
          ? `/kiosk/play/cross-platform/engine/${p.platform}`
          : `/kiosk/play/cross-platform/lobby?platform=${p.platform}`)
      : '/kiosk/play/cross-platform';   // not connected → go to login page
    return (
      <ButtonBase key={p.platform} onClick={() => navigate(target)}
        sx={{ display:'flex', flexDirection:'column', alignItems:'flex-start', gap:0.75, p:'11px 13px',
          borderRadius:'15px', border:'1px solid', borderColor: p.connected ? 'primary.dark' : 'divider',
          bgcolor:'background.paper' }}>
        <Box sx={{ display:'flex', alignItems:'center', gap:1, width:'100%' }}>
          <Box sx={{ width:8, height:8, borderRadius:'50%', bgcolor: p.connected ? 'success.main' : 'text.disabled' }} />
          <Typography sx={{ fontSize:14, fontWeight:600 }}>{t(meta.label, meta.labelCn)}</Typography>
        </Box>
        <Typography sx={{ fontSize:11, color:'text.secondary' }}>
          {p.connected ? t('Connected','已连接') : t('Tap to connect','点击登录连接')}
        </Typography>
      </ButtonBase>
    );
  })}
</Box>
```
Copy `PLATFORM_META` into PlayPage (or lift it to a shared `src/kiosk/constants/platforms.ts` and import from both PlayPage and PlatformConnectPage — preferred, DRY). Import `PlatformInfo` type from `../../api`.

- [ ] **Step 4: Run test to verify it passes**

Run: `npm run test -- PlayPage`
Expected: PASS.

- [ ] **Step 5: Verify the hub still fits 1024×600 without scroll**

Run the visual check (see Verification task). The 3-section layout budget: greeting ~46 + 人机 (label+row) ~78 + 人人 ~78 + 跨平台 ~74 + gaps ≈ 316px, well within the ~466px content area. Confirm no vertical scrollbar appears.

- [ ] **Step 6: Commit**

```bash
git add katrain/web/ui/src/kiosk/pages/PlayPage.tsx katrain/web/ui/src/kiosk/pages/PlayPage.test.tsx katrain/web/ui/src/kiosk/constants/platforms.ts
git commit -m "feat(kiosk): 对弈 hub — 跨平台对弈 sibling section lists platforms, drop duplicate card"
```

---

### Task 5: Compact `AiSetupPage` — 2-column dropdown form, no scroll

Rebuild the 自由/升降级 setup form so every control fits without scrolling and 开始对弈 is always visible. Left board preview stays; right side becomes a 2-column grid of compact controls (dropdowns for rules/strategy/rank/handicap/komi/time, segmented for board/color). Uses `SubPageBar` (Task 1). This is requirement (3).

**Files:**
- Modify: `katrain/web/ui/src/kiosk/pages/AiSetupPage.tsx` (rebuild the right column; keep all `handleStart` logic + state unchanged)
- Test: `katrain/web/ui/src/kiosk/pages/AiSetupPage.test.tsx` (extend existing)
- Reference: existing `Menu`/`MenuItem` dropdown pattern in `PlatformEngineSetupPage.tsx:253-367`.

**Interfaces:**
- Consumes: existing state vars (`boardSize, rules, color, aiStrategy, rank, handicap, komi, timeEnabled...`) and `handleStart` — unchanged. `SubPageBar`.
- Produces: no new exports. All existing `API.gameSetup` payload fields stay identical (do not change the submitted values).

- [ ] **Step 1: Write the failing test**

```tsx
// AiSetupPage.test.tsx — the no-scroll contract + start button always mounted
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import AiSetupPage from './AiSetupPage';
// (reuse existing mocks in the file for API/useAuth/LiveBoard)

test('Start button is present without scrolling (rendered, not gated behind overflow)', () => {
  render(<MemoryRouter initialEntries={['/kiosk/play/ai/setup/free']}>
    <Routes><Route path="/kiosk/play/ai/setup/:mode" element={<AiSetupPage />} /></Routes>
  </MemoryRouter>);
  expect(screen.getByRole('button', { name: /开始对弈|start game/i })).toBeInTheDocument();
  expect(screen.getByRole('button', { name: /返回|back/i })).toBeInTheDocument();
});

test('rules render as a dropdown trigger, not 4 separate chips', () => {
  render(<MemoryRouter initialEntries={['/kiosk/play/ai/setup/free']}>
    <Routes><Route path="/kiosk/play/ai/setup/:mode" element={<AiSetupPage />} /></Routes>
  </MemoryRouter>);
  // Compact form shows the current rule value as one control; the Japanese/Korean/AGA
  // options are behind the dropdown (not all visible at once).
  expect(screen.queryByText('AGA')).not.toBeInTheDocument();
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm run test -- AiSetupPage`
Expected: FAIL — current page renders all rule chips (AGA visible) and the right column is `overflow:auto` (start button can be off-screen but is in DOM; the AGA assertion fails).

- [ ] **Step 3: Rebuild the right column**

Replace the right `<Box sx={{ flex:1, p:3, overflow:'auto' ...}}>` block. New structure: `SubPageBar` at top (remove the inline back button), then a `display:grid; gridTemplateColumns:'1fr 1fr'; gap` form, then a pinned full-width `开始对弈` button with `mt:auto`. Convert sliders to compact dropdowns using MUI `Select` (or the existing Menu pattern):
- 棋盘: keep `OptionChips` segmented (9/13/19).
- 我执: keep `OptionChips` segmented (黑/白).
- 规则: `Select` (中国/日本/韩国/AGA).
- AI 策略 (free only): `Select` (拟人/KataGo/实地/厚势/策略).
- AI 棋力 (when shown): compact — a `Select` of common ranks OR keep the slider but in a single grid cell with the value chip inline (do not let it span full width).
- 让子: `Select` 0–9.
- 贴目 (free, handicap 0): `Select` 0.5–7.5 step 0.5.
- 用时: `Select` (不限时/5分/10分/…) that maps to the existing `timeEnabled`+`mainTime`+`byoyomi` state (keep the same submitted values; a preset dropdown is fine — e.g. "不限时" → timeEnabled=false; "10分3×30秒" → the current byoyomi defaults).

Keep the left board preview `Box` (width 322, `LiveBoard`) exactly as-is. Do NOT change `handleStart` or the `API.gameSetup` payload.

Layout container: outer `Box display:flex flexDirection:column height:100%`; then `Box display:flex flex:1` for preview + form; form column uses `overflow:hidden` (NOT auto) so the no-scroll contract is structural.

- [ ] **Step 4: Run test to verify it passes**

Run: `npm run test -- AiSetupPage`
Expected: PASS. Also run the existing `AiSetupPage.test.tsx` cases — the `API.gameSetup` payload assertions must still pass (values unchanged).

- [ ] **Step 5: Visual check at 1024×600**

Confirm (via the Verification task) that for both `free` and `ranked` modes, with time control ON, everything fits and 开始对弈 needs no scroll.

- [ ] **Step 6: Commit**

```bash
git add katrain/web/ui/src/kiosk/pages/AiSetupPage.tsx katrain/web/ui/src/kiosk/pages/AiSetupPage.test.tsx
git commit -m "feat(kiosk): compact 2-column AiSetupPage — 开始对弈 visible without scroll"
```

---

### Task 6: Apply the compact pattern to `PlatformEngineSetupPage` (secondary)

`PlatformEngineSetupPage` (跨平台人机设置) has the same `overflowY:auto` scroll problem. Apply the same compact 2-column + `SubPageBar` treatment for consistency. Lower priority; can ship after Task 5.

**Files:**
- Modify: `katrain/web/ui/src/kiosk/pages/PlatformEngineSetupPage.tsx:197` (remove `overflowY:auto`, adopt 2-col grid + pinned start button + SubPageBar)
- Test: extend `katrain/web/ui/src/kiosk/pages/AiSetupPage.test.tsx` pattern into a new `PlatformEngineSetupPage` no-scroll test.

- [ ] **Step 1:** Mirror Task 5's structure. Its handicap/level dropdowns already exist (lines 253-367) — keep them, arrange in a 2-col grid, pin 开始对弈.
- [ ] **Step 2:** Run `npm run test` + visual check.
- [ ] **Step 3: Commit**

```bash
git add katrain/web/ui/src/kiosk/pages/PlatformEngineSetupPage.tsx
git commit -m "feat(kiosk): compact PlatformEngineSetupPage to match AiSetupPage"
```

---

### Verification (run after all tasks)

- [ ] **Unit tests:** `cd katrain/web/ui && npm run test` — all green.
- [ ] **Lint:** `npm run lint` — no errors (especially no unused `ArrowBack` imports, no `src/kiosk` → galaxy/Board3D imports).
- [ ] **Both builds green (shared-territory rule):**
  ```bash
  cd katrain/web/ui
  npm run build            # full web build → ../static
  npm run build:kiosk-2d   # kiosk build + verify:kiosk-2d (must still find NO three.js)
  ```
  Expected: both exit 0. `verify:kiosk-2d` still passes because this plan added no three.js.
- [ ] **Visual QA at 1024×600** (via the gstack `/browse` skill, screenshotting the running dev server or built dist):
  - 对弈 hub: three sibling sections, platform cards visible, Dock present, no vertical scroll.
  - 自由对弈 setup: SubPageBar (no Dock), 2-col form, 开始对弈 visible without scroll.
  - A deep tsumego page: Dock gone, back bar present, back returns to parent.

---

## Self-Review

**Spec coverage:**
- Req 1 (Dock on L1 only + back everywhere): Task 2 (gate Dock) + Task 1 (SubPageBar) + Task 3 (fill the 3 gaps, migrate the rest). ✓
- Req 2 (跨平台 sibling section listing platforms): Task 4. ✓
- Req 3 (compact setup, no scroll to 开始对弈): Task 5 (AiSetupPage) + Task 6 (PlatformEngineSetupPage). ✓
- Req 4 (3D): out of scope — see the separate `2026-07-12-kiosk-3d-board.md` plan.

**Type consistency:** `SubPageBarProps` (`title/onBack/to/right`) used identically in Tasks 1, 3, 5. `L1_PATHS: string[]` defined in navTabs (Task 2 step 1), consumed in KioskLayout (Task 2 step 4). `PlatformInfo` imported from `../../api` in Task 4 matches PlatformConnectPage's usage.

**Placeholder scan:** No TBD/TODO. Migration list in Task 3 names every file + its exact back target from the inventory. Task 5 enumerates each control's replacement.

**Known simplification:** Task 3 migration of the ~10 already-working pages is consistency polish; if time-boxed, the required subset for req 1 is only the 3 dead-end pages (PlaceholderPage, PlatformConnectPage, PlatformLobbyPage) + Task 2. The tsumego/tutorial pages already have working back buttons, so they are safe even before migration.
