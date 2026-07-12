# Kiosk 3D Board Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a real three.js 3D Go board to the kiosk 对弈 page — a 3D toggle button in the control panel (galaxy-style), plus touch-friendly camera controls: zoom +/−, an up/down pitch slider (both already built into the shared `Board3D`), and a NEW left/right (azimuth) slider. Default camera framed close to top-down so the whole 19×19 board is visible with no clipping, as large as fits.

**Architecture:** Reuse the existing galaxy `Board3D` component (`src/components/Board3D/`), which is import-clean (only shared `src/components/Board.tsx` + `src/api.ts`, zero galaxy deps). Extend it with **default-off** props for azimuth (yaw) control and a steeper initial camera so galaxy behavior is unchanged. Relax the kiosk-2d build boundary so the kiosk bundle may include three.js. Wire a `view3d` toggle into the kiosk `GamePage`/`GameControlPanel` using galaxy's dynamic-import + 2D/3D display-swap pattern.

**Tech Stack:** React 19 + TS + Vite + MUI. three.js `^0.183`, `@react-three/fiber ^9`, `@react-three/drei ^10` — already in `package.json` (no new deps). Vitest + Testing Library. Build gate `scripts/verify-kiosk.sh`.

## Global Constraints

- Device targets: RK3562 / RK3576 / RK3588, 7″ landscape **1024 × 600**. RK3562 is the weakest — 3D perf on it is unverified and is a gated milestone (Task 7).
- **Precedent:** smartbox-software 中国象棋/国际象棋 ship raw three.js on these boxes, tuned with `renderer.setPixelRatio(Math.min(devicePixelRatio, 1.5))` ("kiosk GPU 预算"), on-demand render (no persistent RAF), and a WebGL-unavailable → 2D fallback. Mirror that tuning.
- `Board3D` is **shared territory** (both the full web build and the kiosk build consume it after this plan). Every new prop MUST default to galaxy's current behavior. After changes, run BOTH `npm run build` and `npm run build:kiosk-2d`.
- Kiosk is Simplified-Chinese first: `t('English', '中文默认')` for all strings.
- The kiosk must still NOT import anything under `src/galaxy/**` or `src/pages/VideoRecorderPage*`. Only the `Board3D` restriction is relaxed.
- `verify-kiosk.sh` must keep its `/galaxy/` route check and non-board `/api/v1/live` check; only the three.js prohibition is removed.

---

### Task 1: Relax the kiosk-2d build boundary to allow three.js

Allow the kiosk-2d bundle to include three.js while keeping every other boundary guard intact. Four edit sites (mapped from the build-boundary audit).

**Files:**
- Modify: `katrain/web/ui/vite.config.ts:36-42` (drop `three`/@react-three from `rollupOptions.external` — they must be BUNDLED, not external, in kiosk mode)
- Modify: `katrain/web/ui/eslint.config.js:11-24` (remove the `components/Board3D/**` entry from `forbiddenFromKiosk`; keep galaxy + VideoRecorderPage bans)
- Modify: `katrain/web/ui/scripts/verify-kiosk.sh:18-30` (remove the `THREE.` + `'three'`/@react-three grep checks; keep the `/galaxy/` and live-API checks)
- No change to `AppRouter.tsx` — kiosk does not import galaxy; it will import `Board3D` directly (a shared component), which Rollup bundles into the kiosk chunk.

**Interfaces:**
- Produces: a kiosk-2d build that bundles three.js and passes `verify:kiosk-2d`.

- [ ] **Step 1: Edit `vite.config.ts` — stop externalizing three in kiosk mode**

Change the build block so kiosk mode no longer marks three as external (still keep the separate `outDir`):
```ts
    build: {
      outDir: kioskMode ? '../static-kiosk-2d' : '../static',
      emptyOutDir: true,
      // three.js is intentionally BUNDLED into the kiosk build now (3D Go board).
      // No rollupOptions.external — three/@react-three are packaged normally.
    },
```

- [ ] **Step 2: Edit `eslint.config.js` — allow Board3D import from kiosk**

Delete the `components/Board3D/**` object from the `forbiddenFromKiosk` array (lines ~16-19), leaving the `galaxy/**` and `VideoRecorderPage*` entries:
```js
const forbiddenFromKiosk = [
  {
    group: ['**/galaxy/**', '*/galaxy/*', '../galaxy/*', '../../galaxy/*', '../../../galaxy/*'],
    message: 'kiosk bundle must not import galaxy code — would drag in admin UI',
  },
  {
    group: ['**/pages/VideoRecorderPage*', '*/pages/VideoRecorderPage', '../pages/VideoRecorderPage'],
    message: 'kiosk bundle must not import VideoRecorderPage — recorder-only',
  },
]
```

- [ ] **Step 3: Edit `scripts/verify-kiosk.sh` — drop the three.js prohibition only**

Remove the two `grep` blocks (lines 18-30) that check for `THREE.` and `'three'`/`@react-three`. Keep the `/galaxy/` route-residue block and the non-board `/api/v1/live` block and the final `exit $fail`. Add a comment:
```bash
# NOTE: three.js is now intentionally bundled in the kiosk build (3D Go board).
# We no longer fail on THREE. / 'three' / @react-three. The galaxy-route and
# non-board live-API guards below still apply.
```

- [ ] **Step 4: Verify the boundary relax builds clean (no 3D yet)**

Run:
```bash
cd katrain/web/ui
npm run lint
npm run build:kiosk-2d
```
Expected: both exit 0. `verify-kiosk.sh` passes (no galaxy routes, no non-board live calls). Bundle-size step will later show a larger kiosk chunk once Board3D is imported (Task 4) — not yet.

- [ ] **Step 5: Commit**

```bash
git add katrain/web/ui/vite.config.ts katrain/web/ui/eslint.config.js katrain/web/ui/scripts/verify-kiosk.sh
git commit -m "build(kiosk): allow three.js in kiosk-2d bundle for 3D board (keep galaxy/live guards)"
```

---

### Task 2: Extend shared `Board3D` with azimuth (yaw) + steeper-camera props — default-off

Add opt-in props so the kiosk can (a) rotate left/right and (b) start closer to top-down, WITHOUT changing galaxy. Azimuth is currently hard-locked (`minAzimuthAngle=0, maxAzimuthAngle=0`); unlock it only when the new prop is set.

**Files:**
- Modify: `katrain/web/ui/src/components/Board3D/CameraController.tsx` (accept an azimuth range; keep locked by default)
- Modify: `katrain/web/ui/src/components/Board3D/index.tsx:46-56` (new props), `:58-60` (initial polar), `:117-124` (camera), `:132` (pass azimuth to controller)
- Test: `katrain/web/ui/src/components/Board3D/CameraController.test.tsx` (new)

**Interfaces:**
- Consumes: existing `Board3DProps`.
- Produces (added to `Board3DProps`):
  ```ts
  /** Allow left/right rotation. Default false → azimuth locked (galaxy behavior). */
  enableAzimuth?: boolean;
  /** Azimuth clamp in radians when enableAzimuth. Default [-Math.PI/3, Math.PI/3]. */
  azimuthRange?: [number, number];
  /** Initial tilt (polar) in radians. Default Math.PI * 0.2 (galaxy). Kiosk uses a
   *  smaller value for a more top-down first frame. */
  initialPolarAngle?: number;
  ```
  And on `CameraController`:
  ```ts
  minAzimuthAngle?: number;   // default 0 (locked)
  maxAzimuthAngle?: number;   // default 0 (locked)
  ```

- [ ] **Step 1: Write the failing test**

```tsx
// CameraController.test.tsx — assert azimuth props reach OrbitControls
import { render } from '@testing-library/react';
import { vi } from 'vitest';
const orbitProps: any = {};
vi.mock('@react-three/drei', () => ({
  OrbitControls: (p: any) => { Object.assign(orbitProps, p); return null; },
}));
vi.mock('three', () => ({ MOUSE: { ROTATE: 0, DOLLY: 1 } }));
import CameraController from './CameraController';

test('azimuth locked by default (0..0)', () => {
  render(<CameraController />);
  expect(orbitProps.minAzimuthAngle).toBe(0);
  expect(orbitProps.maxAzimuthAngle).toBe(0);
});

test('azimuth range passes through when provided', () => {
  render(<CameraController minAzimuthAngle={-1} maxAzimuthAngle={1} />);
  expect(orbitProps.minAzimuthAngle).toBe(-1);
  expect(orbitProps.maxAzimuthAngle).toBe(1);
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm run test -- CameraController`
Expected: FAIL — `minAzimuthAngle`/`maxAzimuthAngle` are hardcoded to 0 and not props.

- [ ] **Step 3: Implement — parametrize azimuth in CameraController**

In `CameraController.tsx`, add `minAzimuthAngle`/`maxAzimuthAngle` to the props interface (defaults 0) and pass them to `<OrbitControls>` instead of the literal `0`:
```tsx
interface CameraControllerProps {
  target?: [number, number, number];
  interactive?: boolean;
  fixedPolarAngle?: number;
  minAzimuthAngle?: number;
  maxAzimuthAngle?: number;
}
const CameraController = forwardRef<any, CameraControllerProps>(
  ({ target, interactive = true, fixedPolarAngle, minAzimuthAngle = 0, maxAzimuthAngle = 0 }, ref) => {
    // ... unchanged minPolar/maxPolar ...
    return (
      <OrbitControls
        /* ...unchanged... */
        minAzimuthAngle={minAzimuthAngle}
        maxAzimuthAngle={maxAzimuthAngle}
        enableRotate={interactive}
      />
    );
  });
```

- [ ] **Step 4: Wire the new Board3D props through**

In `index.tsx`: add `enableAzimuth`, `azimuthRange`, `initialPolarAngle` to `Board3DProps`; use `initialPolarAngle ?? Math.PI * 0.2` for the `useState`; compute azimuth bounds and pass to `<CameraController>`:
```tsx
const [polarAngle, setPolarAngle] = useState(initialPolarAngle ?? Math.PI * 0.2);
const [az0, az1] = enableAzimuth ? (azimuthRange ?? [-Math.PI / 3, Math.PI / 3]) : [0, 0];
// ...
<CameraController ref={orbitRef} target={cameraTarget} interactive={!disableControls}
  fixedPolarAngle={fixedPolarAngle} minAzimuthAngle={az0} maxAzimuthAngle={az1} />
```
Do not change the default camera position `[0, 22, 26]` here — the kiosk will pass its own `cameraPosition` (Task 6). Galaxy passes none → unchanged.

- [ ] **Step 5: Run tests + confirm galaxy unchanged**

Run: `npm run test -- CameraController` → PASS. Run full `npm run test` → existing Board3D/galaxy tests still green (defaults preserve behavior).

- [ ] **Step 6: Commit**

```bash
git add katrain/web/ui/src/components/Board3D/CameraController.tsx katrain/web/ui/src/components/Board3D/CameraController.test.tsx katrain/web/ui/src/components/Board3D/index.tsx
git commit -m "feat(board3d): opt-in azimuth + initial polar props (default-off, galaxy unchanged)"
```

---

### Task 3: Add the left/right (yaw) slider to the Board3D overlay

The overlay in `Board3D/index.tsx` (lines 162-229) already renders the zoom +/− buttons and the vertical pitch slider. Add a horizontal azimuth slider, rendered only when `enableAzimuth`. Also apply the smartbox pixel-ratio tuning to the Canvas.

**Files:**
- Modify: `katrain/web/ui/src/components/Board3D/index.tsx` (overlay + a `handleYaw` handler + Canvas `dpr`)

**Interfaces:**
- Consumes: `orbitRef` (OrbitControls), `enableAzimuth`, `az0/az1` from Task 2.
- Produces: a `handleYaw(angle)` that sets the controls' azimuth (`orbitRef.current.setAzimuthalAngle(angle)` then `.update()`), mirroring the existing `handleTiltChange`.

- [ ] **Step 1: Add the yaw handler + azimuth state**

```tsx
const [azimuth, setAzimuth] = useState(0);
const handleYaw = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
  const a = parseFloat(e.target.value);
  setAzimuth(a);
  const c = orbitRef.current;
  if (c?.setAzimuthalAngle) { c.setAzimuthalAngle(a); c.update(); invalidate(); }
}, []);
```
(Use the same `invalidate` already imported for `handleCreated`; if `frameloop='demand'` isn't set, `.update()` is enough.)

- [ ] **Step 2: Add the horizontal slider to the overlay**

Inside the `{!disableControls && (...)}` overlay block, add below the pitch slider (gated on `enableAzimuth`):
```tsx
{enableAzimuth && (
  <input type="range" aria-label="左右" min={az0} max={az1} step={0.01}
    value={azimuth} onChange={handleYaw}
    style={{ width: 180 /* horizontal; position bottom-center via wrapper */ }} />
)}
```
Position it bottom-center of the board area (a wrapping absolutely-positioned `div`), matching the confirmed mockup. Keep the existing zoom + pitch cluster bottom-right.

- [ ] **Step 3: Apply smartbox GPU tuning to the Canvas**

Add `dpr={[1, 1.5]}` to the `<Canvas>` props (caps pixel ratio at 1.5 — the smartbox "kiosk GPU 预算" value). This is safe for galaxy too (visually identical on desktop, cheaper on the kiosk).
```tsx
<Canvas
  shadows={{ type: PCFShadowMap }}
  dpr={[1, 1.5]}
  camera={{ position: cameraPosition || [0, 22, 26], fov: 40, near: 0.1, far: 100 }}
  /* ...unchanged... */
>
```

- [ ] **Step 4: Test + visual**

Run `npm run test` (no regressions). Visual verification of the slider deferred to Task 6.

- [ ] **Step 5: Commit**

```bash
git add katrain/web/ui/src/components/Board3D/index.tsx
git commit -m "feat(board3d): left/right yaw slider (opt-in) + cap dpr at 1.5 for kiosk GPU"
```

---

### Task 4: Mount `Board3D` in the kiosk `GamePage` with a 2D/3D swap

Port galaxy's dynamic-import + display-swap pattern into the kiosk `GamePage`. Load `Board3D` on first 3D activation, keep it mounted, hide the 2D `Board` with `display:none` while 3D is active. Persist the choice to `localStorage`.

**Files:**
- Modify: `katrain/web/ui/src/kiosk/pages/GamePage.tsx:510-521` (the board render region) + toggle state
- Reference: galaxy `src/galaxy/pages/GamePage.tsx:30-32,60-68,155-163,321-345`
- Test: `katrain/web/ui/src/kiosk/pages/GamePage.test.tsx` (extend)

**Interfaces:**
- Consumes: `analysisToggles` / `setAnalysisToggles` (already in kiosk GamePage), `Board3D` default export (dynamic import from `../../components/Board3D`). Board3D props = same `BoardProps` shape the kiosk already passes to `Board` + kiosk-only `enableAzimuth`, `initialPolarAngle`, `cameraPosition`.
- Produces: `analysisToggles.view3d: boolean`.

- [ ] **Step 1: Write the failing test**

```tsx
// GamePage.test.tsx addition — toggling 3D mounts Board3D lazily
// (mock ../../components/Board3D to a trivial component to avoid WebGL in jsdom)
vi.mock('../../components/Board3D', () => ({ default: () => <div data-testid="board3d" /> }));

test('activating 3D renders the 3D board container', async () => {
  // render GamePage with a running session (reuse existing test harness/mocks),
  // set analysisToggles.view3d via the 3D toggle, then:
  // await screen.findByTestId('board3d');
});
```
(Flesh out using the file's existing session mock. The key assertion: `findByTestId('board3d')` after toggling `view3d`.)

- [ ] **Step 2: Run test to verify it fails**

Run: `npm run test -- kiosk/pages/GamePage`
Expected: FAIL — no 3D board mounts today.

- [ ] **Step 3: Implement the dynamic import + swap**

Add near the top of the kiosk `GamePage` component:
```tsx
const [Board3D, setBoard3D] = useState<React.ComponentType<any> | null>(null);
const board3dLoadingRef = useRef(false);
const view3d = !!analysisToggles.view3d;
useEffect(() => {
  if (view3d && !Board3D && !board3dLoadingRef.current) {
    board3dLoadingRef.current = true;
    import('../../components/Board3D').then((m) => setBoard3D(() => m.default));
  }
}, [view3d, Board3D]);
```
Persist in the existing `onToggleAnalysis` path (GamePage already calls `setAnalysisToggles`): when key === `'view3d'`, also `localStorage.setItem('kiosk_view3d', String(next))`. Initialize `view3d` from `localStorage.getItem('kiosk_view3d') === 'true'` when building the initial `analysisToggles`.

Replace the board `<Box sx={{ height:'100%', aspectRatio:'1' }}>` region so both boards coexist:
```tsx
<Box sx={{ height: '100%', aspectRatio: '1', position: 'relative' }}>
  <Box sx={{ display: view3d && Board3D ? 'none' : 'block', height: '100%' }}>
    <Board gameState={gameState} onMove={handleBoardMove} onNavigate={session.onNavigate}
      analysisToggles={boardAnalysisToggles} playerColor={humanColor} engineOverlay={engineOverlay} />
  </Box>
  {view3d && Board3D && (
    <Board3D gameState={gameState} onMove={handleBoardMove} onNavigate={session.onNavigate}
      analysisToggles={boardAnalysisToggles} playerColor={humanColor}
      enableAzimuth initialPolarAngle={Math.PI * 0.14} cameraPosition={[0, 30, 20]} />
  )}
  {view3d && !Board3D && <CircularProgress sx={{ position: 'absolute', top: '50%', left: '50%' }} />}
</Box>
```
(`initialPolarAngle`/`cameraPosition` are first-pass values; Task 6 tunes them for full-board framing.)

- [ ] **Step 4: Run test to verify it passes**

Run: `npm run test -- kiosk/pages/GamePage`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add katrain/web/ui/src/kiosk/pages/GamePage.tsx katrain/web/ui/src/kiosk/pages/GamePage.test.tsx
git commit -m "feat(kiosk): mount Board3D in GamePage with lazy 2D/3D swap + persisted view3d"
```

---

### Task 5: 3D toggle button in the kiosk `GameControlPanel`

Add a `3D` `ItemToggle` to the kiosk control panel (galaxy uses `ViewInArIcon`), wired to `onToggleAnalysis('view3d')`. Place it next to 数子, matching the confirmed mockup + galaxy layout.

**Files:**
- Modify: `katrain/web/ui/src/kiosk/components/game/GameControlPanel.tsx:97-101` (add the toggle)
- Test: `katrain/web/ui/src/kiosk/components/game/GameControlPanel.test.tsx` (new or extend)

**Interfaces:**
- Consumes: existing `analysisToggles`, `onToggleAnalysis` props (already on `Props`).

- [ ] **Step 1: Write the failing test**

```tsx
// GameControlPanel.test.tsx
import { render, screen, fireEvent } from '@testing-library/react';
import { vi } from 'vitest';
import GameControlPanel from './GameControlPanel';

test('renders a 3D toggle wired to view3d', () => {
  const onToggle = vi.fn();
  render(<GameControlPanel gameState={{} as any} onAction={() => {}}
    analysisToggles={{}} onToggleAnalysis={onToggle} isGameOver={false} />);
  const btn = screen.getByText('3D');
  fireEvent.click(btn);
  expect(onToggle).toHaveBeenCalledWith('view3d');
});
```
(Provide the minimal required `Props` per the component's interface.)

- [ ] **Step 2: Run test to verify it fails**

Run: `npm run test -- GameControlPanel`
Expected: FAIL — no 3D button.

- [ ] **Step 3: Add the toggle**

Import the icon and add the toggle in the button grid (near the 数子/Undo cluster, ~line 101):
```tsx
import ViewInAr from '@mui/icons-material/ViewInAr';
// ...
<ItemToggle icon={<ViewInAr />} label={t('3D', '3D')}
  active={!!analysisToggles.view3d} onClick={() => onToggleAnalysis('view3d')} />
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm run test -- GameControlPanel`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add katrain/web/ui/src/kiosk/components/game/GameControlPanel.tsx katrain/web/ui/src/kiosk/components/game/GameControlPanel.test.tsx
git commit -m "feat(kiosk): 3D toggle button in GameControlPanel (view3d)"
```

---

### Task 6: Tune the initial camera for full-board, no-clip, as-large-as-fits framing

Dial in `cameraPosition` / `initialPolarAngle` / `fov` so a full 19×19 board is entirely visible at a near-top-down angle and fills the board area. This is empirical — verify visually.

**Files:**
- Modify: `katrain/web/ui/src/kiosk/pages/GamePage.tsx` (the `cameraPosition`/`initialPolarAngle` passed to `Board3D`)
- Possibly Modify: `katrain/web/ui/src/components/Board3D/index.tsx` (only if a kiosk-specific default is cleaner as a prop; otherwise pass from GamePage)

- [ ] **Step 1: Build the kiosk dev bundle and open the game page**

```bash
cd katrain/web/ui && npm run dev
```
Navigate to a 对弈 game (or use the gstack `/browse` skill to drive the running app), toggle 3D.

- [ ] **Step 2: Screenshot at 1024×600 and check framing**

Use `/browse`: `viewport 1024x600`, screenshot the board region. Verify: (a) all four board edges + coordinate labels visible, no clipping; (b) angle is clearly top-down-biased (far stones readable, not foreshortened into a thin band); (c) board fills most of the board area.

- [ ] **Step 3: Adjust and re-shoot**

Tune the trio until it matches the confirmed mockup (`kiosk-redesign.html` change 4):
- More top-down → smaller `initialPolarAngle` (e.g. `Math.PI * 0.12`–`0.16`) and higher camera Y.
- Fit the whole board → move camera back (larger distance) or widen `fov`; keep `maxDistance`/`minDistance` (10/50) in range.
- Record the final values in a code comment referencing this task.

- [ ] **Step 4: Commit**

```bash
git add katrain/web/ui/src/kiosk/pages/GamePage.tsx
git commit -m "feat(kiosk): tune 3D initial camera for full-board top-down framing"
```

---

### Task 7: RK3562 on-device performance gate + fallback decision

three.js 3D is validated on this hardware family (smartbox chess), but RK3562 specifically must be measured before shipping 3D on it. This is a manual device task; it decides whether RK3562 keeps fiber-based 3D or falls back.

- [ ] **Step 1: Deploy the kiosk-2d build to an RK3562 unit** (per the project's SBC deploy flow) and open a 对弈 game with 3D on.
- [ ] **Step 2: Measure** frame rate during play (stones dropping, camera slider drags) and idle, plus thermals over ~10 min. Target: interaction stays responsive (≳30 fps during slider drags; no runaway heat).
- [ ] **Step 3: Decide:**
  - **Pass** → ship 3D on RK3562. Done.
  - **Fail (fiber too heavy)** → fall back per the mockup's B2: either (a) gate the 3D toggle off on RK3562 (device-tier flag) and keep 2D, or (b) port the smartbox raw-three.js recipe as a lighter renderer. Capture the decision in a follow-up plan.
- [ ] **Step 4:** WebGL-unavailable safety: confirm that if `WebGLRenderingContext` is missing, the 3D toggle hides / falls back to 2D (mirror smartbox "板上 WebGL 不可用时回退 2D"). Add a `useState(() => !!window.WebGLRenderingContext)` guard around the 3D `ItemToggle` if not already covered.

---

### Verification (run after Tasks 1–6; Task 7 is device-gated)

- [ ] **Unit tests:** `cd katrain/web/ui && npm run test` — green (Board3D, CameraController, kiosk GamePage, GameControlPanel).
- [ ] **Lint:** `npm run lint` — green (kiosk may now import Board3D; still no galaxy/VideoRecorder imports).
- [ ] **Both builds:**
  ```bash
  npm run build            # full web → ../static
  npm run build:kiosk-2d   # kiosk → ../static-kiosk-2d ; verify-kiosk.sh now ALLOWS three.js
  ```
  Expected: both exit 0. Note the kiosk chunk grows (three + fiber + drei); the CI bundle-size step will report it.
- [ ] **Visual QA (1024×600, `/browse`):** 3D toggle in the panel turns green when on; zoom +/−, pitch (up/down), and yaw (left/right) sliders all present and functional; full board visible at a top-down angle, no clipping.

---

## Self-Review

**Spec coverage:**
- 3D toggle like galaxy (panel button, green when active): Task 5. ✓
- Zoom +/− and up/down pitch: already in Board3D overlay — reused via Task 4/3. ✓
- NEW left/right slider: Tasks 2 (azimuth unlock) + 3 (slider). ✓
- Initial angle top-down, full board no-clip, as large as fits: Tasks 4 (first pass) + 6 (tuning). ✓
- three.js feasible on kiosk hardware: Task 1 (boundary) + Task 7 (RK3562 gate + fallback). ✓

**Type consistency:** `enableAzimuth`/`azimuthRange`/`initialPolarAngle` added to `Board3DProps` in Task 2 and consumed in Task 4. `minAzimuthAngle`/`maxAzimuthAngle` added to `CameraControllerProps` in Task 2 and asserted in its test. `analysisToggles.view3d` written by Task 5's toggle, read by Task 4's swap.

**Placeholder scan:** No TBD. Task 6 is intentionally empirical (camera tuning) with concrete adjustment directions and a visual gate, not a placeholder. Task 7 is a manual device milestone with an explicit pass/fail branch.

**Shared-territory caution:** Every Board3D change (Tasks 2, 3) defaults to galaxy's existing behavior (azimuth locked, initial polar `0.2π`, `dpr [1,1.5]` visually identical on desktop). Galaxy build must be re-verified in the Verification step.

**Cross-plan dependency:** This plan is independent of `2026-07-12-kiosk-nav-and-page-redesign.md` and can land before or after it. The 3D board lives on the fullscreen game route (outside `KioskLayout`), so the Dock/SubPageBar changes don't interact with it.
