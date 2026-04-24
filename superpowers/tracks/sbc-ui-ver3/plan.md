# Katrain SBC Kiosk 2D-only Build Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce a Katrain kiosk build that ships **no `three` / `@react-three` code** and measures the bundle-size + first-paint savings versus the full build. Back-fill numbers into `smartbox-software/docs/dev-plan-2026-04-24.md` §"实测数字".

**Architecture:** Source-level compile-time flag `__KIOSK_2D_ONLY__` drives three layers of defense against leaking three.js into the kiosk bundle: (1) AppRouter gates out `/galaxy/*` and `/record` so their chunks are never referenced; (2) Vite `rollupOptions.external` fails the build loudly if any surviving path still reaches `three` / `@react-three/*`; (3) a standalone grep-based verify script blocks commits if the dist still contains `THREE.` symbols. Measurements are captured by a headless-Chromium Node script that boots a tiny static server against each dist and reports FCP / LCP / bundle size to markdown.

**Tech Stack:** Vite 7, React 19, TypeScript, Playwright's `chromium` browser API (standalone, not the test runner), Node's built-in `http` module (for a ~20-line SPA-fallback static server).

**Scope:** Afternoon 14:30-18:00 (3.5h). Out of scope: evening Mode switching design, late-night W1 doc wrap-up, SBC real-device verification (already covered — RK3562/RK3576 kiosk boot previously tested), any changes to Board.tsx (2D capabilities confirmed present at 598 lines).

**Branch:** `feat/kiosk-2d-build-2026-04-24`, branched from `feature/rk3588-ui` (the current HEAD which already has develop merged in).

---

## File Structure

| Action | Path | Responsibility |
|---|---|---|
| **Create** | `katrain/web/ui/src/vite-env.d.ts` | TypeScript ambient declaration for the `__KIOSK_2D_ONLY__` global (Vite's default `vite-env.d.ts` does not exist in this repo) |
| **Modify** | `katrain/web/ui/vite.config.ts` | Read `VITE_KIOSK_2D_ONLY` env, `define` `__KIOSK_2D_ONLY__`, swap `outDir` to `../static-kiosk-2d`, attach `rollupOptions.external` for three in kiosk mode |
| **Modify** | `katrain/web/ui/src/AppRouter.tsx` | Conditional `lazy()` imports + conditional `<Route>` renders so `/galaxy/*` and `/record` do not exist when `__KIOSK_2D_ONLY__` is true |
| **Modify** | `katrain/web/ui/src/pages/VideoRecorderPage.tsx` | Top-of-module `throw` when `__KIOSK_2D_ONLY__` — second line of defense if the module is ever bundled |
| **Modify** | `katrain/web/ui/package.json` | `build:kiosk-2d` script + `verify:kiosk-2d` grep script |
| **Create** | `katrain/web/ui/scripts/measure-kiosk.mjs` | Headless-Chromium Playwright script: boot static servers for both dists, capture FCP / LCP / bundle bytes, write markdown table to stdout and JSON to disk |
| **Create** | `scripts/launch-kiosk.sh` | Minimal Chromium kiosk launcher for local dogfooding during tonight's Mode switching design (not acceptance-gated; SBC real hardware already verified) |
| **Modify** | `superpowers/tracks/sbc-ui-ver3/plan.md` | This file — replaces the earlier ver3 draft |

**New files:** 4 · **Modified files:** 5 · **New npm deps:** 0 (uses already-installed `@playwright/test`, Node built-ins)

---

## Task 0: Branch + baseline full-build numbers

**Files:**
- Create branch: `feat/kiosk-2d-build-2026-04-24`

**Why first:** We need the **full build's** `../static/` dist as a baseline for later comparison. Once we change vite.config, even `npm run build` (no flag) may behave differently, so baseline must come from untouched code. The target `../static/` directory does not exist yet — nothing to back up from a previous run.

- [ ] **Step 1: Confirm clean starting state**

Run:
```bash
cd /Users/fan/Repositories/katrain-rk3588-ui
git status
git branch --show-current
```
Expected: `feature/rk3588-ui`, clean tree (merge already committed in prior session).

- [ ] **Step 2: Create + checkout new branch**

Run:
```bash
git checkout -b feat/kiosk-2d-build-2026-04-24
```

- [ ] **Step 3: Run baseline full build**

Run:
```bash
cd katrain/web/ui
time npm run build 2>&1 | tee /tmp/full-build.log
```
Expected: exits 0. Record real time from `time` output (target buckets: <30s / <60s / >60s).

- [ ] **Step 4: Capture baseline bundle stats**

Run (still in `katrain/web/ui`):
```bash
du -sh ../static
du -sh ../static/assets/*.js 2>/dev/null | sort -h | tail -5
grep -l "THREE\." ../static/assets/*.js 2>/dev/null | head -5
grep -l "@react-three\|react-three" ../static/assets/*.js 2>/dev/null | head -5
```
Expected:
- `../static` total visible (probably 5-15 MB)
- Largest chunks listed — three should appear in at least one
- At least one chunk file matched by `THREE\.`

Save this terminal output to `/tmp/baseline-stats.txt` by copy-paste — we fill it into Task 8's commit message.

- [ ] **Step 5: Move baseline dist out of the way**

Run:
```bash
mv ../static ../static-full-baseline
ls ../static-full-baseline/index.html
```
Expected: `index.html` listed.

This frees up `../static` so the next `npm run build` (no flag) will land fresh there if we ever need it, and keeps the full-build reference stable for Task 7's Playwright script.

No commit yet — source is unchanged.

---

## Task 1: Ambient type declaration for `__KIOSK_2D_ONLY__`

**Files:**
- Create: `katrain/web/ui/src/vite-env.d.ts`

TypeScript needs to know `__KIOSK_2D_ONLY__` is a boolean global before we reference it. Without this, Task 2's `vite.config.ts` `define` will emit the constant into the bundle but `tsc -b` (run by `npm run build`) will fail with "Cannot find name `__KIOSK_2D_ONLY__`".

- [ ] **Step 1: Write the failing check (tsc baseline)**

Run:
```bash
cd /Users/fan/Repositories/katrain-rk3588-ui/katrain/web/ui
npx tsc -b 2>&1 | tail -10
```
Expected: exits 0, no errors (baseline is clean).

Note: Red/green for this task is **introduce the symbol later (Task 2 AppRouter uses it), confirm tsc errors, then this declaration makes it pass**. We write the declaration first so the chain is already primed.

- [ ] **Step 2: Create `vite-env.d.ts`**

Create file `katrain/web/ui/src/vite-env.d.ts`:

```ts
/// <reference types="vite/client" />

/**
 * Compile-time constant wired by vite.config.ts `define`.
 * true in kiosk-2d builds, false in the regular full build.
 * Source-level guards reading this value are tree-shaken by Rollup.
 */
declare const __KIOSK_2D_ONLY__: boolean;
```

- [ ] **Step 3: Verify TS still compiles**

Run:
```bash
npx tsc -b 2>&1 | tail -10
```
Expected: exits 0.

- [ ] **Step 4: Commit**

Run:
```bash
cd /Users/fan/Repositories/katrain-rk3588-ui
git add katrain/web/ui/src/vite-env.d.ts
git commit -m "feat(kiosk-build): declare __KIOSK_2D_ONLY__ ambient global"
```

---

## Task 2: Vite config — env flag, conditional outDir, rollup external

**Files:**
- Modify: `katrain/web/ui/vite.config.ts`

Current file (33 lines) reads no env vars and always writes to `../static`. We add `loadEnv`, a `define` for the compile-time constant, and kiosk-mode-only overrides for `outDir` and `rollupOptions.external`.

The `external` list contains three and both `@react-three/*` packages. In kiosk mode, if any surviving import path still references these, Rollup will fail with `"three" is not externalizable` or emit a warning — either way, the next task's `verify:kiosk-2d` grep closes the loop.

- [ ] **Step 1: Replace `vite.config.ts`**

Overwrite `katrain/web/ui/vite.config.ts` with:

```ts
/// <reference types="vitest" />
import { defineConfig, loadEnv } from 'vitest/config'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const kioskMode = env.VITE_KIOSK_2D_ONLY === 'true'

  return {
    plugins: [react()],
    define: {
      __KIOSK_2D_ONLY__: JSON.stringify(kioskMode),
    },
    server: {
      proxy: {
        '/api': { target: 'http://127.0.0.1:8001', changeOrigin: true },
        '/ws':  { target: 'ws://127.0.0.1:8001', ws: true },
        '/assets': { target: 'http://127.0.0.1:8001', changeOrigin: true },
      }
    },
    build: {
      outDir: kioskMode ? '../static-kiosk-2d' : '../static',
      emptyOutDir: true,
      rollupOptions: kioskMode ? {
        external: ['three', '@react-three/fiber', '@react-three/drei'],
      } : undefined,
    },
    test: {
      globals: true,
      environment: 'jsdom',
      setupFiles: './src/test/setup.ts',
      exclude: ['tests/**', 'node_modules/**'],
    },
  }
})
```

- [ ] **Step 2: Verify the non-kiosk build still works**

Run (from `katrain/web/ui`):
```bash
cd /Users/fan/Repositories/katrain-rk3588-ui/katrain/web/ui
npm run build 2>&1 | tail -15
```
Expected: exits 0, output in `../static/`. `du -sh ../static` comparable to baseline (within a few KB — we only changed config, not source).

- [ ] **Step 3: Try kiosk mode without AppRouter guards (expected to fail loud)**

Run:
```bash
VITE_KIOSK_2D_ONLY=true npm run build 2>&1 | tail -20
```
Expected: **build fails or emits warnings** because `VideoRecorderPage.tsx` statically imports `three` and Galaxy pages dynamically import `Board3D`. This failure is the "Layer 2" trap proving external is wired. Screenshot/note the error — we confirm it flips to success after Task 3-4.

If build somehow succeeds, proceed anyway (tree-shaking may already have removed the deps) — Task 5's verify grep is the final gate.

- [ ] **Step 4: Clean up any partial kiosk dist**

```bash
rm -rf ../static-kiosk-2d
```

- [ ] **Step 5: Commit**

Run:
```bash
cd /Users/fan/Repositories/katrain-rk3588-ui
git add katrain/web/ui/vite.config.ts
git commit -m "feat(kiosk-build): add VITE_KIOSK_2D_ONLY flag + rollup external for three"
```

---

## Task 3: AppRouter — gate out `/galaxy/*` and `/record` in kiosk builds

**Files:**
- Modify: `katrain/web/ui/src/AppRouter.tsx`

Current AppRouter (36 lines) lazily imports `GalaxyApp` and `VideoRecorderPage` **unconditionally**. Galaxy's `pages/GamePage.tsx` and `pages/GameRoomPage.tsx` dynamically import `Board3D` — so the Galaxy chunk graph reaches three. VideoRecorderPage statically imports three. Both must be source-level severed in kiosk mode so Rollup DCE never queues those chunks.

Key pattern: `const X = __KIOSK_2D_ONLY__ ? null : lazy(() => import('./X'))`. Vite's `define` replaces `__KIOSK_2D_ONLY__` with the literal `true` / `false` **before** Rollup sees the module, so the `true ? null : ...` branch is dead code and Rollup drops the `import()` — which means the chunk itself is never emitted.

- [ ] **Step 1: Replace `AppRouter.tsx`**

Overwrite `katrain/web/ui/src/AppRouter.tsx` with:

```tsx
import { lazy, Suspense } from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { ThemeProvider, CssBaseline } from '@mui/material';
import { zenTheme } from './theme';
import { AuthProvider } from './context/AuthContext';
import { SettingsProvider } from './context/SettingsContext';
import ZenModeApp from './ZenModeApp';

// Code-split: kiosk and galaxy bundles load independently.
// Galaxy + VideoRecorder reach three.js (via Board3D / direct import),
// so they are excluded from the kiosk-2d build at the source level —
// the ternary collapses to `null` at compile time and Rollup drops
// the dynamic `import()` and its transitive chunk.
const KioskApp = lazy(() => import('./kiosk/KioskApp'));
const GalaxyApp = __KIOSK_2D_ONLY__
  ? null
  : lazy(() => import('./GalaxyApp'));
const VideoRecorderPage = __KIOSK_2D_ONLY__
  ? null
  : lazy(() => import('./pages/VideoRecorderPage'));

const AppRouter = () => {
  return (
    <ThemeProvider theme={zenTheme}>
      <CssBaseline />
      <BrowserRouter>
        <AuthProvider>
          <SettingsProvider>
            <Suspense fallback={null}>
              <Routes>
                <Route path="/kiosk/*" element={<KioskApp />} />
                {!__KIOSK_2D_ONLY__ && GalaxyApp && (
                  <Route path="/galaxy/*" element={<GalaxyApp />} />
                )}
                {!__KIOSK_2D_ONLY__ && VideoRecorderPage && (
                  <Route path="/record" element={<VideoRecorderPage />} />
                )}
                <Route path="/*" element={<ZenModeApp />} />
              </Routes>
            </Suspense>
          </SettingsProvider>
        </AuthProvider>
      </BrowserRouter>
    </ThemeProvider>
  );
};

export default AppRouter;
```

- [ ] **Step 2: Verify full build still succeeds**

Run:
```bash
cd /Users/fan/Repositories/katrain-rk3588-ui/katrain/web/ui
npm run build 2>&1 | tail -10
```
Expected: exits 0.

- [ ] **Step 3: Sanity-check `/` and `/galaxy/*` still present in full build output**

Run:
```bash
grep -l "GalaxyApp\|/galaxy" ../static/assets/*.js 2>/dev/null | head -3
```
Expected: at least one chunk matches (GalaxyApp still bundled in the full build).

- [ ] **Step 4: Commit**

Run:
```bash
cd /Users/fan/Repositories/katrain-rk3588-ui
git add katrain/web/ui/src/AppRouter.tsx
git commit -m "feat(kiosk-build): gate /galaxy and /record routes on __KIOSK_2D_ONLY__"
```

---

## Task 4: VideoRecorderPage defensive throw

**Files:**
- Modify: `katrain/web/ui/src/pages/VideoRecorderPage.tsx`

Belt-and-suspenders: if Task 3's DCE ever regresses (e.g., someone adds a non-lazy `import VideoRecorderPage` elsewhere), the module load itself should fail loudly instead of silently pulling three.js back in. The `if (__KIOSK_2D_ONLY__) throw ...` at file top is compile-time-folded to either unconditional throw (dead module) or dead code, depending on the flag.

- [ ] **Step 1: Read first 20 lines of current file to find insertion point**

Run:
```bash
cd /Users/fan/Repositories/katrain-rk3588-ui
sed -n '1,20p' katrain/web/ui/src/pages/VideoRecorderPage.tsx
```
Expected: comment block / first `import` statements visible.

- [ ] **Step 2: Add throw guard at top of file**

Edit `katrain/web/ui/src/pages/VideoRecorderPage.tsx` — insert this block **before** all existing imports (line 1, above the first `import` or comment):

```tsx
if (__KIOSK_2D_ONLY__) {
  throw new Error(
    'VideoRecorderPage must not be imported in kiosk-2d builds. ' +
    'If this fires, AppRouter gating regressed.'
  );
}
```

Use the Edit tool to insert at the very top of the file.

- [ ] **Step 3: Verify full build still succeeds**

Run:
```bash
cd /Users/fan/Repositories/katrain-rk3588-ui/katrain/web/ui
npm run build 2>&1 | tail -10
```
Expected: exits 0. The `if (false) throw ...` branch is dead code in the full build.

- [ ] **Step 4: Commit**

Run:
```bash
cd /Users/fan/Repositories/katrain-rk3588-ui
git add katrain/web/ui/src/pages/VideoRecorderPage.tsx
git commit -m "feat(kiosk-build): defensive throw in VideoRecorderPage on kiosk flag"
```

---

## Task 5: package.json scripts — `build:kiosk-2d` + `verify:kiosk-2d`

**Files:**
- Modify: `katrain/web/ui/package.json`

Two scripts:
- `build:kiosk-2d` — sets env, runs `tsc -b && vite build` (preserving the existing TS gate)
- `verify:kiosk-2d` — greps the emitted bundle for `THREE.` and any `three`/`@react-three` import strings. Exits 0 on clean, non-zero on any match.

- [ ] **Step 1: Read current scripts block**

Run:
```bash
cd /Users/fan/Repositories/katrain-rk3588-ui
grep -A 8 '"scripts"' katrain/web/ui/package.json
```
Expected: current scripts block visible.

- [ ] **Step 2: Add the two scripts**

Edit `katrain/web/ui/package.json` — modify the `"scripts"` object so it reads:

```json
"scripts": {
  "dev": "vite",
  "build": "tsc -b && vite build",
  "build:kiosk-2d": "tsc -b && VITE_KIOSK_2D_ONLY=true vite build",
  "verify:kiosk-2d": "scripts/verify-kiosk.sh",
  "lint": "eslint .",
  "test": "vitest run",
  "test:watch": "vitest",
  "preview": "vite preview"
}
```

- [ ] **Step 3: Create the verify shell script**

Create `katrain/web/ui/scripts/verify-kiosk.sh`:

```bash
#!/usr/bin/env bash
# Verify the kiosk-2d dist contains no three.js / @react-three code.
# Exits 0 on clean, 1 on any match.
set -euo pipefail

DIST="${DIST:-../static-kiosk-2d}"

if [[ ! -d "$DIST" ]]; then
  echo "❌ $DIST not found. Run 'npm run build:kiosk-2d' first." >&2
  exit 1
fi

fail=0

# Minified three.js uses the `THREE.` namespace prefix.
if matches=$(grep -l "THREE\." "$DIST"/assets/*.js 2>/dev/null); then
  echo "❌ Found THREE. in:" >&2
  echo "$matches" >&2
  fail=1
fi

# Source-string residue check — dynamic import paths that survived minification.
if matches=$(grep -El '["'\'']three["'\'']|@react-three' "$DIST"/assets/*.js 2>/dev/null); then
  echo "❌ Found three / @react-three import string in:" >&2
  echo "$matches" >&2
  fail=1
fi

if [[ $fail -eq 0 ]]; then
  size=$(du -sh "$DIST" | cut -f1)
  echo "✅ no three.js in $DIST ($size total)"
fi

exit $fail
```

Then mark executable:
```bash
chmod +x katrain/web/ui/scripts/verify-kiosk.sh
```

- [ ] **Step 4: Commit**

Run:
```bash
cd /Users/fan/Repositories/katrain-rk3588-ui
git add katrain/web/ui/package.json katrain/web/ui/scripts/verify-kiosk.sh
git commit -m "feat(kiosk-build): add build:kiosk-2d + verify:kiosk-2d scripts"
```

---

## Task 6: Run kiosk build and prove bundle has no three.js (Red → Green)

**Files:** none modified (just running commands and recording numbers)

- [ ] **Step 1: Red — confirm the baseline dist DOES contain three**

Run:
```bash
cd /Users/fan/Repositories/katrain-rk3588-ui/katrain/web/ui
DIST=../static-full-baseline ./scripts/verify-kiosk.sh
```
Expected: exits **1** with messages listing full-baseline chunks that contain `THREE.`. This confirms the script actually works.

- [ ] **Step 2: Green — run the kiosk build**

Run:
```bash
time npm run build:kiosk-2d 2>&1 | tee /tmp/kiosk-build.log | tail -20
```
Expected: exits 0. Note the build time.

Troubleshooting: if Rollup complains about `three` being marked external but not installed as peer / "not externalizable" warnings, the build should still produce output. Proceed to step 3 — the true gate is grep.

- [ ] **Step 3: Green — verify no three in kiosk dist**

Run:
```bash
npm run verify:kiosk-2d
```
Expected: exits 0, prints `✅ no three.js in ../static-kiosk-2d (<size>)`.

If it fails: check Galaxy/Record were actually gated (`grep -l "GalaxyApp\|VideoRecorder" ../static-kiosk-2d/assets/*.js` should be empty). If still failing, one of: (a) AppRouter guard misspelled, (b) `define` typo for `__KIOSK_2D_ONLY__`. Re-read Tasks 2-3.

- [ ] **Step 4: Record kiosk bundle stats**

Run:
```bash
du -sh ../static-kiosk-2d
du -sh ../static-kiosk-2d/assets/*.js 2>/dev/null | sort -h | tail -5
ls ../static-kiosk-2d/assets/*.js 2>/dev/null | wc -l
echo "--- baseline ---"
du -sh ../static-full-baseline
du -sh ../static-full-baseline/assets/*.js 2>/dev/null | sort -h | tail -5
ls ../static-full-baseline/assets/*.js 2>/dev/null | wc -l
```
Save output to `/tmp/kiosk-stats.txt` for Task 9's commit message. Expected savings: **~30-45 MB** removed from kiosk dist.

- [ ] **Step 5: Acceptance checkpoint**

Eyeball three requirements before proceeding:
- [ ] `npm run verify:kiosk-2d` passed
- [ ] `du -sh ../static-kiosk-2d` is at least 10 MB smaller than `../static-full-baseline`
- [ ] kiosk dist JS chunk count is fewer than full baseline (because Galaxy+Record chunks are gone)

No commit — we only ran commands.

---

## Task 7: Playwright metrics script — FCP / LCP / bundle size for both builds

**Files:**
- Create: `katrain/web/ui/scripts/measure-kiosk.mjs`

Standalone Node ESM script using `@playwright/test`'s `chromium` browser API (not the test runner — avoids the `webServer` config in `playwright.config.ts` which boots the Python backend). Boots a 20-line inline SPA-fallback HTTP server against each dist, navigates to `/kiosk/login` (un-auth-gated kiosk-bundle entry point), captures metrics.

Measurement semantics:
- **FCP**: `performance.getEntriesByName('first-contentful-paint')[0].startTime`
- **LCP**: via `PerformanceObserver({type:'largest-contentful-paint', buffered:true})` — init-script injected before navigation, largest value wins
- **TTI proxy**: wall-clock between `page.goto` and `networkidle`
- **Bundle size**: recursive `stat` over the dist, summed
- **DOM complete / load event**: from `performance.getEntriesByType('navigation')[0]`

Output: markdown table to stdout (copy-pasteable into the smartbox-software doc) + `kiosk-metrics.json` with raw numbers.

- [ ] **Step 1: Write the script**

Create `katrain/web/ui/scripts/measure-kiosk.mjs`:

```js
#!/usr/bin/env node
/**
 * measure-kiosk.mjs — compare first-paint + bundle size for full vs kiosk-2d builds.
 *
 * Usage:  node scripts/measure-kiosk.mjs
 * Output: markdown table to stdout, raw JSON to ./kiosk-metrics.json
 *
 * Requires ../static-full-baseline and ../static-kiosk-2d to exist.
 */
import { chromium } from '@playwright/test';
import http from 'node:http';
import { readFile, readdir, stat, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const UI_DIR = path.resolve(__dirname, '..');

const MIME = {
  '.html': 'text/html', '.js': 'application/javascript', '.mjs': 'application/javascript',
  '.css': 'text/css', '.json': 'application/json', '.svg': 'image/svg+xml',
  '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.woff': 'font/woff',
  '.woff2': 'font/woff2', '.ttf': 'font/ttf', '.ico': 'image/x-icon',
};

async function dirSize(dir) {
  let total = 0;
  for (const name of await readdir(dir, { withFileTypes: true })) {
    const p = path.join(dir, name.name);
    total += name.isDirectory() ? await dirSize(p) : (await stat(p)).size;
  }
  return total;
}

function makeSpaServer(root) {
  return http.createServer(async (req, res) => {
    const urlPath = decodeURIComponent((req.url || '/').split('?')[0]);
    let filePath = path.join(root, urlPath);
    let exists = false;
    try { exists = (await stat(filePath)).isFile(); } catch { /* not a file */ }
    if (!exists) filePath = path.join(root, 'index.html');
    try {
      const data = await readFile(filePath);
      const ct = MIME[path.extname(filePath)] || 'application/octet-stream';
      res.writeHead(200, { 'Content-Type': ct, 'Cache-Control': 'no-store' });
      res.end(data);
    } catch {
      res.writeHead(404).end('not found');
    }
  });
}

async function listen(server, port) {
  return new Promise((resolve, reject) => {
    server.once('error', reject);
    server.listen(port, '127.0.0.1', () => resolve());
  });
}

async function close(server) {
  return new Promise((resolve) => server.close(() => resolve()));
}

async function measure(label, staticDir, port, route = '/kiosk/login') {
  const absDir = path.resolve(UI_DIR, staticDir);
  const bytes = await dirSize(absDir);
  const server = makeSpaServer(absDir);
  await listen(server, port);
  const browser = await chromium.launch();
  try {
    const context = await browser.newContext({ viewport: { width: 1280, height: 800 } });
    const page = await context.newPage();
    await page.addInitScript(() => {
      // @ts-ignore
      window.__lcp__ = 0;
      new PerformanceObserver((list) => {
        for (const e of list.getEntries()) {
          // @ts-ignore
          if (e.startTime > window.__lcp__) window.__lcp__ = e.startTime;
        }
      }).observe({ type: 'largest-contentful-paint', buffered: true });
    });
    const url = `http://127.0.0.1:${port}${route}`;
    const t0 = Date.now();
    await page.goto(url, { waitUntil: 'networkidle', timeout: 30000 });
    const tti = Date.now() - t0;
    // Give LCP one more rAF tick.
    await page.waitForTimeout(300);
    const metrics = await page.evaluate(() => {
      const fcpEntry = performance.getEntriesByName('first-contentful-paint')[0];
      const nav = performance.getEntriesByType('navigation')[0];
      return {
        fcp: Math.round(fcpEntry ? fcpEntry.startTime : 0),
        // @ts-ignore
        lcp: Math.round(window.__lcp__ || 0),
        domComplete: Math.round(nav ? nav.domComplete : 0),
        loadEvent: Math.round(nav ? nav.loadEventEnd : 0),
      };
    });
    return { label, bytes, ...metrics, tti };
  } finally {
    await browser.close();
    await close(server);
  }
}

const pct = (kiosk, full) => full === 0 ? '—' : `${Math.round((1 - kiosk / full) * 100)}%`;
const mb = (b) => (b / 1024 / 1024).toFixed(2);

console.error('→ measuring full baseline…');
const full = await measure('full', '../static-full-baseline', 9190);
console.error('→ measuring kiosk-2d…');
const kiosk = await measure('kiosk-2d', '../static-kiosk-2d', 9191);

const rows = [
  ['dist/ 总大小', `${mb(full.bytes)} MB`, `${mb(kiosk.bytes)} MB`, pct(kiosk.bytes, full.bytes)],
  ['FCP',          `${full.fcp} ms`,       `${kiosk.fcp} ms`,       pct(kiosk.fcp, full.fcp)],
  ['LCP',          `${full.lcp} ms`,       `${kiosk.lcp} ms`,       pct(kiosk.lcp, full.lcp)],
  ['domComplete',  `${full.domComplete} ms`, `${kiosk.domComplete} ms`, pct(kiosk.domComplete, full.domComplete)],
  ['load event',   `${full.loadEvent} ms`, `${kiosk.loadEvent} ms`, pct(kiosk.loadEvent, full.loadEvent)],
  ['TTI (networkidle proxy)', `${full.tti} ms`, `${kiosk.tti} ms`, pct(kiosk.tti, full.tti)],
];

console.log('| 指标 | 完整版 (with three) | 2D-only (kiosk) | 降幅 |');
console.log('|---|---|---|---|');
for (const [k, a, b, d] of rows) {
  console.log(`| ${k} | ${a} | ${b} | ${d} |`);
}

await writeFile(path.join(UI_DIR, 'kiosk-metrics.json'),
  JSON.stringify({ full, kiosk, generatedAt: new Date().toISOString() }, null, 2));

console.error('→ wrote kiosk-metrics.json');
```

- [ ] **Step 2: Make the script executable + chosen route sanity-check**

Run:
```bash
cd /Users/fan/Repositories/katrain-rk3588-ui
chmod +x katrain/web/ui/scripts/measure-kiosk.mjs
grep -n "login" katrain/web/ui/src/kiosk/KioskApp.tsx
```
Expected: login is mounted outside KioskAuthGuard (line ~37 per prior explore) — `/kiosk/login` will render without backend auth.

- [ ] **Step 3: Run the metrics script**

Run (from `katrain/web/ui`):
```bash
cd katrain/web/ui
node scripts/measure-kiosk.mjs 2>&1 | tee /tmp/metrics.log
```
Expected:
- Two `→ measuring…` progress lines on stderr
- Markdown table on stdout
- `kiosk-metrics.json` written to `katrain/web/ui/kiosk-metrics.json`

Troubleshooting:
- **Chromium missing**: `npx playwright install chromium` (first-run only).
- **Port 9190/9191 in use**: tweak the ports in the script (bottom `await measure(...)` calls).
- **`/kiosk/login` errors in console** but page renders — OK, we're measuring shell bundle, not backend wiring.

- [ ] **Step 4: Sanity-check the numbers**

Expected magnitudes (ballpark — actual will vary):
- Bundle size: **2D-only ~35-45 MB smaller** than full
- FCP: **2D-only ≤ full** (smaller bundle → less parse time)
- LCP: **2D-only ≤ full**

If kiosk FCP > full by a large margin, something is off (probably still loading Galaxy chunks). Re-run Task 6 verify.

- [ ] **Step 5: Commit the measurement script + results**

Run:
```bash
cd /Users/fan/Repositories/katrain-rk3588-ui
git add katrain/web/ui/scripts/measure-kiosk.mjs katrain/web/ui/kiosk-metrics.json
git commit -m "feat(kiosk-build): add measure-kiosk.mjs with FCP/LCP/size comparison"
```

Note: `kiosk-metrics.json` is committed so the numbers are reproducible + versioned. It is regenerated on every measurement run.

---

## Task 8: `launch-kiosk.sh` — local Chromium dogfooding launcher

**Files:**
- Create: `scripts/launch-kiosk.sh`

Explicitly de-scoped from acceptance per user feedback ("RK3562/RK3576 kiosk boot previously tested"). Still useful tonight for the Mode switching design session when we need to eyeball the 2D build in kiosk chrome locally. Minimal, no auto-test.

- [ ] **Step 1: Write the launch script**

Create `scripts/launch-kiosk.sh`:

```bash
#!/usr/bin/env bash
# launch-kiosk.sh — Boot a local Chromium in kiosk mode against the 2D-only build.
#
# Usage:
#   bash scripts/launch-kiosk.sh
#   PORT=9191 RES=1920x1080 bash scripts/launch-kiosk.sh
#
# Prereq: katrain/web/ui/npm run build:kiosk-2d
# Backend note: the SPA calls /api/* — if you want working data, run KataGo server at :8000
#   and the FastAPI backend at :8001 alongside (outside this script's scope).

set -euo pipefail

PORT="${PORT:-9190}"
RES="${RES:-1280x800}"
STATIC_DIR="${STATIC_DIR:-katrain/web/static-kiosk-2d}"
ROUTE="${ROUTE:-/kiosk/login}"

if [[ ! -d "$STATIC_DIR" ]]; then
  echo "❌ $STATIC_DIR not found. Run: cd katrain/web/ui && npm run build:kiosk-2d" >&2
  exit 1
fi

# Find chromium / chrome.
CHROME=""
for candidate in chromium chromium-browser google-chrome chrome \
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  "/Applications/Chromium.app/Contents/MacOS/Chromium"; do
  if command -v "$candidate" >/dev/null 2>&1 || [[ -x "$candidate" ]]; then
    CHROME="$candidate"
    break
  fi
done

if [[ -z "$CHROME" ]]; then
  echo "❌ No chromium / chrome binary found on PATH." >&2
  exit 1
fi

# Boot static server (background).
npx --yes http-server "$STATIC_DIR" -p "$PORT" --silent -c-1 &
SERVER_PID=$!
trap "kill $SERVER_PID 2>/dev/null || true" EXIT
sleep 1

URL="http://localhost:${PORT}${ROUTE}"
echo "→ Launching kiosk: $URL (res=$RES, chrome=$CHROME)"

"$CHROME" \
  --kiosk \
  --app="$URL" \
  --window-size="${RES/x/,}" \
  --window-position=0,0 \
  --disable-pinch \
  --overscroll-history-navigation=0 \
  --no-first-run \
  --no-default-browser-check \
  --user-data-dir=/tmp/smartbox-kiosk-profile
```

- [ ] **Step 2: Make executable + smoke-test**

Run:
```bash
cd /Users/fan/Repositories/katrain-rk3588-ui
chmod +x scripts/launch-kiosk.sh
# Optional smoke — human driven, not gated.
# bash scripts/launch-kiosk.sh   # opens Chromium full-screen, Cmd+Q to quit
```

Smoke is human-in-the-loop; not required for this task's completion. Skip if time-constrained.

- [ ] **Step 3: Commit**

Run:
```bash
git add scripts/launch-kiosk.sh
git commit -m "feat(kiosk-build): add launch-kiosk.sh for local Chromium dogfooding"
```

---

## Task 9: Push branch + produce hand-off summary

**Files:** none modified (push + summary).

- [ ] **Step 1: Confirm branch state**

Run:
```bash
cd /Users/fan/Repositories/katrain-rk3588-ui
git log --oneline feature/rk3588-ui..HEAD
```
Expected: 7 commits (Task 1, 2, 3, 4, 5, 7, 8).

- [ ] **Step 2: Push branch**

Run:
```bash
git push -u origin feat/kiosk-2d-build-2026-04-24
```
Expected: new remote tracking branch created.

- [ ] **Step 3: Extract the markdown table for the cross-repo doc**

Run:
```bash
cd katrain/web/ui
node scripts/measure-kiosk.mjs 2>/dev/null | tee /tmp/kiosk-metrics-table.md
```
This re-runs measurement and gives you a copy-pasteable markdown table in `/tmp/kiosk-metrics-table.md`.

- [ ] **Step 4: Hand-off — fill numbers into smartbox-software**

This step operates on a **different repo** (`smartbox-software`). Do not automate — manual copy is fine and matches the intent of "master plan numbers回填":

1. Open `/Users/fan/Repositories/smartbox-software/docs/dev-plan-2026-04-24.md` in an editor.
2. Navigate to §"实测数字".
3. Replace the `__` placeholders in the "Katrain 2D-only build vs 完整版" table with the markdown from `/tmp/kiosk-metrics-table.md`.
4. Under "2D Canvas 三功能完成度" tick all three as ✅ with note: "既有能力 (Board.tsx 598 行) — 无需新开发".
5. Commit in that repo:
   ```bash
   cd /Users/fan/Repositories/smartbox-software
   git add docs/dev-plan-2026-04-24.md
   git commit -m "docs(dev-plan 4/24): fill Katrain 2D-only build measured numbers"
   git push
   ```

- [ ] **Step 5: Acceptance checklist**

Confirm each:
- [ ] `feat/kiosk-2d-build-2026-04-24` pushed to origin
- [ ] `npm run verify:kiosk-2d` exits 0 on a fresh `npm run build:kiosk-2d`
- [ ] `kiosk-metrics.json` committed and has non-zero FCP/LCP for both builds
- [ ] kiosk bundle ≥ 10 MB smaller than full
- [ ] `smartbox-software/docs/dev-plan-2026-04-24.md` §"实测数字" table is filled, committed, pushed
- [ ] `ROADMAP.md` W1 4/24 row can be marked ✅ (do this in the late-night W1 wrap-up session per master plan, not here)

---

## Risk & fallbacks

**1. Rollup's DCE misses the `__KIOSK_2D_ONLY__ ? null : lazy(...)` pattern.**
Vite replaces `__KIOSK_2D_ONLY__` before Rollup runs; Rollup sees `true ? null : lazy(...)` and drops the `lazy()` branch. If for some reason this doesn't work (older Rollup + inlined-constant edge case), the kiosk build will contain `GalaxyApp.chunk.js` and Task 6 verify will fail. Fallback: switch to an `if (!__KIOSK_2D_ONLY__) { ... }` top-level registration block — even more explicit to the minifier.

**2. `rollupOptions.external` breaks full-baseline comparison.**
External is only set when `kioskMode === true`. Full build (no env var) keeps `rollupOptions: undefined`. Nothing changes in full behavior. We verified this by running `npm run build` after Task 2.

**3. `/kiosk/login` doesn't render without backend.**
The login page makes network calls that will fail against our bare static server — but the page **shell** renders (LCP fires on text/background). If this isn't the case, swap route to `/` (ZenModeApp) which is backend-free. Both builds load the same `/` so FCP delta reflects purely the extra bundle weight of Galaxy in the full build.

**4. Chromium not installed for Playwright.**
`npx playwright install chromium` — one-time. If offline / firewalled, Task 7 is blocked; capture numbers manually in Chrome DevTools as a fallback.

**5. Time slips past 18:00.**
Strict cut-line priorities to preserve:
1. Tasks 1-6 (the actual build + verify) — cannot slip; these are the deliverable.
2. Task 7 (metrics) — numbers can land tomorrow morning if needed.
3. Task 8 (launch-kiosk.sh) — genuinely optional; user confirmed real-device testing already covers it.
4. Task 9 step 4 (cross-repo doc fill) — reschedule to late-night W1 wrap-up slot if 18:00 hits.

---

## Self-review notes (executed on this plan before hand-off)

**Spec coverage:**
- ✅ 2D-only build flag → Task 2
- ✅ Board.tsx 2D capabilities preserved → not modified, verified still bundled (Task 3 step 3 implicit — ZenModeApp + KioskApp still import Board)
- ✅ kiosk build script → Task 5
- ✅ no three.js in bundle → Task 5 verify + Task 6 gate
- ✅ launch-kiosk.sh → Task 8
- ✅ bundle size comparison → Task 6 step 4
- ✅ FCP/LCP/TTI/bundle size comparison → Task 7 (Playwright automated per user Q6a)
- ✅ KataGo server at :8000 noted → irrelevant to measurement (we use bare static serve) but documented in launch-kiosk.sh header
- ✅ Cross-repo number fill → Task 9 step 4
- ✅ Galaxy and /record both gated → Task 3 (answers user Q2=c)
- ✅ New branch `feat/kiosk-2d-build-2026-04-24` → Task 0 step 2
- ✅ Full baseline captured before modifications → Task 0 step 5

**Placeholder scan:** none found. Each step has concrete commands or code.

**Type consistency:** `__KIOSK_2D_ONLY__` (double underscore, all caps) used identically in `vite-env.d.ts`, `vite.config.ts` define, `AppRouter.tsx` guards, `VideoRecorderPage.tsx` throw, `measure-kiosk.mjs` (not referenced — good, measurement is build-agnostic).

**Out-of-scope sections that were previously in sbc-ui-ver3/plan.md and are NOT here:**
- 2D Canvas drawing functions (落子/标记/高亮 functions) — already present in Board.tsx; no new code needed
- SBC real-device verification — user confirmed previously tested
- Evening Mode switching design + late-night W1 docs — user Q1 answered "只覆盖 下午"; those live in smartbox-software repo and are out of scope for this plan
