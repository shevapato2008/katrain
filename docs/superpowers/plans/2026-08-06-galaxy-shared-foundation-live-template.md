# Galaxy Shared Foundation and Live Template Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the minimal Galaxy-only visual foundation and migrate the real live-match detail page into the approved all-breakpoint board template without changing its backend contract or board artwork.

**Architecture:** Keep the work isolated under the lazily loaded Galaxy route: a locale-aware Galaxy theme and font bundle wrap `GalaxyApp`, `MainLayout` owns the responsive global chrome, and a slot-based `BoardPageShell` owns board/rail geometry without knowing live-match data. The existing `useLiveMatch`, board renderer, analysis panels, and playback controls remain the business authority; this slice changes only presentation, responsive state, branding, and accessibility.

**Tech Stack:** React 19, TypeScript 5.9, MUI 7, React Router 6, Vite 8, Vitest/Testing Library, Playwright, Python/fonttools/brotli, CSS `@font-face` unicode ranges.

**Approved spec:** `docs/superpowers/specs/2026-08-06-galaxy-board-template-ladder-design.md`

**Scope boundary:** This plan ends at visual approval of the real Galaxy live-match detail page. It does not implement the two future ladder settlement/eligibility contracts, migrate other board pages, or alter the 1024×600 kiosk layout.

---

## Chunk 1: Reproducible Galaxy Foundation and Responsive Chrome

### Task 1: Create an isolated execution worktree and capture the untouched baseline

**Files:**
- Create: `superpowers/tracks/galaxy-ui-redesign/capture_live_template.mjs`
- Create: `superpowers/tracks/galaxy-ui-redesign/visual/live-template/{1535x900,1536x900,1537x900,1440x900,1201x800,1200x800,1199x800,1024x768,901x700,900x700,899x700,430x880}/reference.png`
- Create: `superpowers/tracks/galaxy-ui-redesign/visual/live-template/geometry-reference.json`
- Create: `superpowers/tracks/galaxy-ui-redesign/visual/live-template/baseline.md`
- Create: `superpowers/tracks/galaxy-ui-redesign/visual/live-template/plan-base.txt`

- [x] **Step 1: Invoke the required worktree workflow**

Read and follow `@superpowers:using-git-worktrees`. This plan must already be committed in the original worktree. Verify that the exact base contains both approved documents, then create a fresh worktree from that immutable SHA—not from the dirty S0 experiment and not by moving or cleaning the user's current working tree:

```bash
git show HEAD:docs/superpowers/plans/2026-08-06-galaxy-shared-foundation-live-template.md >/dev/null
git show HEAD:docs/superpowers/specs/2026-08-06-galaxy-board-template-ladder-design.md >/dev/null
GALAXY_PLAN_BASE=$(git rev-parse HEAD)
git worktree add /Users/fan/Repositories/katrain-galaxy-live-template -b feature/galaxy-live-template "$GALAXY_PLAN_BASE"
```

Expected: both `git show` commands succeed; the new worktree is clean and starts at the printed `GALAXY_PLAN_BASE`; `/Users/fan/Repositories/katrain-galaxy-s0` remains untouched; the original worktree retains every uncommitted ladder/calibration change.

- [x] **Step 2: Record baseline build health before changing source**

Run from `katrain/web/ui` in the new worktree:

```bash
npm ci --offline
npm test -- --run src/galaxy/components/layout/GalaxySidebar.test.tsx
npm run build
npm run build:kiosk-2d
```

Expected: the existing sidebar test, full TypeScript/Vite build, and kiosk boundary verification pass. Write the exact `GALAXY_PLAN_BASE` plus newline to `visual/live-template/plan-base.txt`. Create `visual/live-template/baseline.md` in every case: record that SHA, commands, PASS results, and chosen match ID; if a pre-existing failure occurs, record its exact output there and do not broaden this slice to fix unrelated tests.

- [x] **Step 3: Write the capture script before modifying the UI**

The script must:

```js
const viewports = [
  [1535, 900], [1536, 900], [1537, 900], [1440, 900], [1201, 800], [1200, 800], [1199, 800],
  [1024, 768], [901, 700], [900, 700], [899, 700], [430, 880],
];
let matchId = 'yike_184016';
const livePath = () => `/galaxy/live/${matchId}`;
```

For each viewport it must navigate to the real server, wait for the live canvas, save a full-page screenshot, and write these measurements to `geometry.json`: viewport, canvas rectangle, sidebar rectangle if present, right-rail rectangle if present, horizontal document overflow, and visible text/buttons above the canvas. Use stable `data-testid` selectors where already available and a canvas/landmark fallback only for the untouched baseline.

- [x] **Step 4: Build and start the real application**

Run the frontend build, then start the backend from the repository root:

```bash
python katrain/web/server.py --host 127.0.0.1 --port 8901
```

Expected: `http://127.0.0.1:8901/galaxy/live/yike_184016` displays the real live match. If that recorded match has disappeared, query the real live list and replace the script's single `matchId` value with an existing match; record the chosen ID in `baseline.md`. Do not introduce a production fixture.

- [x] **Step 5: Capture and inspect all reference viewports**

Run from `katrain/web/ui`:

```bash
node ../../../superpowers/tracks/galaxy-ui-redesign/capture_live_template.mjs reference
```

Expected: twelve per-viewport `reference.png` files and valid `geometry-reference.json`; the current 1024/900/430 references visibly demonstrate the clipping or stacking problem this slice fixes. Stop the server afterward and restore `~/.katrain/config.json` only if starting the server changed it.

- [x] **Step 6: Commit only the baseline harness and selected evidence**

```bash
git add superpowers/tracks/galaxy-ui-redesign/capture_live_template.mjs superpowers/tracks/galaxy-ui-redesign/visual/live-template
git commit -m "记录 galaxy 直播页改版基线"
```

Expected: no generated app bundle, database, local config, or unrelated screenshot is staged.

### Task 2: Make the Chinese font subset reproducible and Galaxy-only

**Files:**
- Create: `tests/web_ui/test_build_galaxy_fonts.py`
- Create: `scripts/build_galaxy_fonts.py`
- Create: `katrain/web/ui/src/galaxy/assets/fonts/README.md`
- Create: `katrain/web/ui/src/galaxy/assets/fonts/OFL-1.1.txt`
- Create: `katrain/web/ui/src/galaxy/assets/fonts/sources.json`
- Create: `katrain/web/ui/src/galaxy/assets/fonts/galaxy-fonts.css`
- Create: `katrain/web/ui/src/galaxy/assets/fonts/longcang-brand.woff2`
- Create: `katrain/web/ui/src/galaxy/assets/fonts/wenkai-400-*.woff2`
- Create: `katrain/web/ui/src/galaxy/assets/fonts/wenkai-500-*.woff2`

- [x] **Step 1: Write failing unit tests for the codepoint policy**

Test the pure functions exported by `scripts/build_galaxy_fonts.py`:

```python
def test_chinese_subset_excludes_latin_digits_kana_and_hangul():
    assert is_chinese_ui_codepoint(ord("棋"))
    assert is_chinese_ui_codepoint(ord("，"))
    assert not is_chinese_ui_codepoint(ord("A"))
    assert not is_chinese_ui_codepoint(ord("8"))
    assert not is_chinese_ui_codepoint(ord("あ"))
    assert not is_chinese_ui_codepoint(ord("한"))

def test_only_cn_tw_catalogs_seed_priority_corpus(tmp_path):
    # Build tiny cn/tw/en catalogs; assert Chinese glyphs enter the priority set
    # and English letters never enter it.

def test_longcang_subset_is_exact_brand_text():
    assert BRAND_TEXT == "智星盒"

def test_manifest_is_deterministic_and_hashes_every_input():
    # Same inputs produce identical JSON and every source has sha256/version/license/url.
```

- [x] **Step 2: Run the font tests and verify failure**

```bash
uv run --with fonttools --with brotli pytest tests/web_ui/test_build_galaxy_fonts.py -q
```

Expected: FAIL because `scripts.build_galaxy_fonts` does not exist.

- [x] **Step 3: Implement the minimal generator**

Adapt the useful frequency-ordering and WOFF2 subset logic from the uncommitted S0 script, but enforce these exact policies:

```python
CHINESE_LOCALES = ("cn", "tw")
BRAND_TEXT = "智星盒"
ALLOWED_RANGES = (
    (0x3000, 0x303F),   # CJK punctuation
    (0x3400, 0x4DBF),   # Extension A
    (0x4E00, 0x9FFF),   # Unified ideographs
    (0xF900, 0xFAFF),   # Compatibility ideographs
    (0xFF01, 0xFF60),   # Full-width Chinese punctuation; filter letters/digits below
)
```

Additionally:

- explicitly exclude ASCII/full-width Latin letters and digits even if a catalog contains them;
- order cn/tw UI codepoints before remaining allowed CJK codepoints, then chunk deterministically;
- subset Long Cang to `BRAND_TEXT` only;
- emit Regular as weight `400` and Medium as `500 700` with `font-synthesis:none` supplied by Galaxy CSS;
- delete stale generated `wenkai-*`, `longcang-*`, and generated CSS before regeneration, but validate that the output directory is exactly `src/galaxy/assets/fonts` before deleting;
- emit `sources.json` with top-level `generator_command`, `generated_total_bytes`, `outputs`, and `inputs`; each `inputs[]` entry contains `name`, `url`, `version`, `filename`, `sha256`, and `license: "SIL OFL 1.1"`, while each output contains filename/SHA-256/bytes;
- do not generate or reference LXGW WenKai Mono.
- for the exact production output directory, delete only generated names (`wenkai-*.woff2`, `longcang-brand.woff2`, generated CSS/manifest) before regeneration; for any other output path, require that the directory is absent or empty and fail closed otherwise;
- serialize the manifest command with the canonical token `$OUT` rather than the caller's absolute output path, so identical source inputs generate byte-identical manifests in different fresh directories.

- [x] **Step 4: Run unit tests and a deterministic two-directory generation check**

Use these pinned official inputs and no moving `latest` URL:

| Source | Pinned release/commit | URL | SHA-256 |
|---|---|---|---|
| LXGW WenKai Regular | `v1.522` | `https://github.com/lxgw/LxgwWenKai/releases/download/v1.522/LXGWWenKai-Regular.ttf` | `39ad71264b588165b469e35e6afb162a378dacd1f95348160240ba9038ac3009` |
| LXGW WenKai Medium | `v1.522` | `https://github.com/lxgw/LxgwWenKai/releases/download/v1.522/LXGWWenKai-Medium.ttf` | `d4bdeb38a39151d74d084cba5090f8cb7d20bf83eedb78c35939ae70b9f4e3f6` |
| Long Cang Regular | Google Fonts commit `b7b1d76caa907473438546739b2ce3a92631adc3` | `https://raw.githubusercontent.com/google/fonts/b7b1d76caa907473438546739b2ce3a92631adc3/ofl/longcang/LongCang-Regular.ttf` | `e5bf2c3f24ef2327c6f136d8f73e2f9dfdf44896fdbeb35a9515f44777bb91bc` |

Populate the task-specific cache and verify it before running the generator:

```bash
mkdir -p /private/tmp/galaxy-font-sources
curl -fL https://github.com/lxgw/LxgwWenKai/releases/download/v1.522/LXGWWenKai-Regular.ttf -o /private/tmp/galaxy-font-sources/LXGWWenKai-Regular-v1.522.ttf
curl -fL https://github.com/lxgw/LxgwWenKai/releases/download/v1.522/LXGWWenKai-Medium.ttf -o /private/tmp/galaxy-font-sources/LXGWWenKai-Medium-v1.522.ttf
curl -fL https://raw.githubusercontent.com/google/fonts/b7b1d76caa907473438546739b2ce3a92631adc3/ofl/longcang/LongCang-Regular.ttf -o /private/tmp/galaxy-font-sources/LongCang-Regular-b7b1d76.ttf
printf '%s  %s\n' \
  39ad71264b588165b469e35e6afb162a378dacd1f95348160240ba9038ac3009 /private/tmp/galaxy-font-sources/LXGWWenKai-Regular-v1.522.ttf \
  d4bdeb38a39151d74d084cba5090f8cb7d20bf83eedb78c35939ae70b9f4e3f6 /private/tmp/galaxy-font-sources/LXGWWenKai-Medium-v1.522.ttf \
  e5bf2c3f24ef2327c6f136d8f73e2f9dfdf44896fdbeb35a9515f44777bb91bc /private/tmp/galaxy-font-sources/LongCang-Regular-b7b1d76.ttf | shasum -a 256 -c -
uv run --with fonttools --with brotli pytest tests/web_ui/test_build_galaxy_fonts.py -q
uv run --with fonttools --with brotli python scripts/build_galaxy_fonts.py --regular /private/tmp/galaxy-font-sources/LXGWWenKai-Regular-v1.522.ttf --medium /private/tmp/galaxy-font-sources/LXGWWenKai-Medium-v1.522.ttf --longcang /private/tmp/galaxy-font-sources/LongCang-Regular-b7b1d76.ttf --out /private/tmp/galaxy-fonts-a
uv run --with fonttools --with brotli python scripts/build_galaxy_fonts.py --regular /private/tmp/galaxy-font-sources/LXGWWenKai-Regular-v1.522.ttf --medium /private/tmp/galaxy-font-sources/LXGWWenKai-Medium-v1.522.ttf --longcang /private/tmp/galaxy-font-sources/LongCang-Regular-b7b1d76.ttf --out /private/tmp/galaxy-fonts-b
diff -rq /private/tmp/galaxy-fonts-a /private/tmp/galaxy-fonts-b
```

Expected: all three checksum lines report `OK`, tests pass, and `diff` prints nothing. Never commit upstream TTF files.

- [x] **Step 5: Generate the committed font assets and document licensing**

```bash
uv run --with fonttools --with brotli python scripts/build_galaxy_fonts.py --regular /private/tmp/galaxy-font-sources/LXGWWenKai-Regular-v1.522.ttf --medium /private/tmp/galaxy-font-sources/LXGWWenKai-Medium-v1.522.ttf --longcang /private/tmp/galaxy-font-sources/LongCang-Regular-b7b1d76.ttf --out katrain/web/ui/src/galaxy/assets/fonts
```

`README.md` must identify both upstream sources/releases, state that all three fonts are SIL OFL 1.1, reproduce the exact command and hashes from `sources.json`, and explain that only Galaxy imports this directory. Copy the unmodified OFL 1.1 license text; do not brand-rewrite it.

- [x] **Step 6: Verify the generated CSS has no prohibited glyphs or mono font**

```bash
rg -n "WenKai Mono|wenkai-mono" katrain/web/ui/src/galaxy/assets/fonts && exit 1 || true
uv run --with fonttools python -c "from fontTools.ttLib import TTFont; import glob; fs=glob.glob('katrain/web/ui/src/galaxy/assets/fonts/*.woff2'); assert fs; [(_ for _ in ()).throw(AssertionError(f)) for f in fs if any((48<=c<=57 or 65<=c<=90 or 97<=c<=122) for c in TTFont(f).getBestCmap())]"
uv run --with fonttools python -c "from fontTools.ttLib import TTFont; p='katrain/web/ui/src/galaxy/assets/fonts/longcang-brand.woff2'; assert set(TTFont(p).getBestCmap()) == set(map(ord, '智星盒'))"
```

Expected: no mono match and no Latin letters/digits in any generated subset. The Long Cang font's cmap is exactly the codepoints of `智星盒`.

- [x] **Step 7: Commit the generator, tests, fonts, and licensing together**

```bash
git add tests/web_ui/test_build_galaxy_fonts.py scripts/build_galaxy_fonts.py katrain/web/ui/src/galaxy/assets/fonts
git commit -m "添加 galaxy 中文字体资源"
```

### Task 3: Add a locale-scoped Galaxy theme without changing kiosk or other modes

**Files:**
- Create: `katrain/web/ui/src/galaxy/theme.ts`
- Create: `katrain/web/ui/src/galaxy/theme.test.tsx`
- Modify: `katrain/web/ui/src/GalaxyApp.tsx`

- [x] **Step 1: Write failing tests for locale and typography isolation**

Assert that:

```ts
expect(createGalaxyTheme('cn').typography.fontFamily).toContain('LXGW WenKai');
expect(createGalaxyTheme('tw').typography.fontFamily).toContain('LXGW WenKai');
for (const locale of ['en', 'jp', 'ko', 'de']) {
  expect(createGalaxyTheme(locale).typography.fontFamily).toBe(SYSTEM_UI_FONT);
}
expect(SYSTEM_UI_FONT).not.toContain('Manrope');
```

Render `GalaxyApp` with a mocked `useSettings()` and assert `.galaxy-root` exposes `data-language="cn"` and receives the nested `ThemeProvider`. The test must not change the top-level `zenTheme` because that would affect Zen and kiosk.

- [x] **Step 2: Run the tests and verify failure**

```bash
cd katrain/web/ui
npm test -- --run src/galaxy/theme.test.tsx
```

Expected: FAIL because `createGalaxyTheme` and the Galaxy root do not exist.

- [x] **Step 3: Implement the Galaxy-only theme and root**

Define:

```ts
export const SYSTEM_UI_FONT = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif";
export const CHINESE_UI_FONT = `'LXGW WenKai', ${SYSTEM_UI_FONT}`;
export const isChineseGalaxyLocale = (language: string) => language === 'cn' || language === 'tw';
export const createGalaxyTheme = (language: string) => createTheme(zenTheme, {
  typography: { fontFamily: isChineseGalaxyLocale(language) ? CHINESE_UI_FONT : SYSTEM_UI_FONT },
  // Repeat the selected family for headings/body/button so old Manrope variant overrides cannot leak through.
});
```

In `GalaxyApp`, import `./galaxy/assets/fonts/galaxy-fonts.css`, read `language` from `SettingsContext`, memoize the theme, wrap Galaxy routes in a nested `ThemeProvider`, and add:

```tsx
<Box className="galaxy-root" data-language={language} sx={{ width: '100vw', height: '100dvh', overflow: 'hidden', fontSynthesis: 'none' }}>
```

Do not import font CSS from `main.tsx`, shared `theme.ts`, global CSS, AppRouter, or any kiosk file.

- [x] **Step 4: Run tests and both production builds**

```bash
npm test -- --run src/galaxy/theme.test.tsx
npm run build
npm run build:kiosk-2d
```

Expected: tests/builds pass and the existing kiosk verifier still reports a clean boundary.

- [x] **Step 5: Prove the kiosk artifact does not contain Galaxy fonts**

```bash
find ../static-kiosk-2d -type f | rg 'wenkai|longcang|galaxy-fonts' && exit 1 || true
rg -n "LXGW WenKai|Long Cang" ../static-kiosk-2d && exit 1 || true
```

Expected: both checks produce no match. Record the full Galaxy font asset bytes and the network bytes loaded by the Chinese live page later in Chunk 3.

- [x] **Step 6: Commit the isolated theme**

```bash
git add katrain/web/ui/src/GalaxyApp.tsx katrain/web/ui/src/galaxy/theme.ts katrain/web/ui/src/galaxy/theme.test.tsx
git commit -m "隔离 galaxy 字体与主题"
```

### Task 4: Replace product branding while preserving legal-name boundaries

**Files:**
- Create: `katrain/web/ui/src/galaxy/components/layout/GalaxyTopBar.tsx`
- Create: `katrain/web/ui/src/galaxy/components/layout/GalaxyTopBar.test.tsx`
- Create: `tests/web_ui/test_stellabox_branding.py`
- Create: `superpowers/tracks/galaxy-ui-redesign/live-template/brand-boundary.md`
- Modify: `katrain/web/ui/src/legal/terms.ts`
- Modify: `katrain/web/ui/src/legal/privacy.ts`
- Modify: `katrain/web/ui/src/galaxy/pages/Dashboard.tsx`
- Modify: `katrain/web/ui/src/galaxy/components/auth/LoginModal.tsx`
- Modify: `katrain/web/ui/src/galaxy/components/layout/GalaxySidebar.tsx`
- Modify: `katrain/web/ui/src/galaxy/components/layout/GalaxySidebar.test.tsx`
- Modify: `katrain/i18n/locales/*/LC_MESSAGES/katrain.po` (brand-specific entries only)

- [x] **Step 1: Inventory every old product-name occurrence before replacing it**

```bash
rg -n --glob '!katrain/web/static/**' --glob '!katrain/web/static-kiosk-2d/**' --glob '!docs/**' --glob '!superpowers/**' '弈航|BoardNavi' katrain scripts > /tmp/galaxy-old-brand-before.txt
```

Classify each match as product-facing copy, stable internal identifier, legal entity/copyright holder, author attribution, or third-party license. Only the first category is authorized for automatic replacement. Always create `superpowers/tracks/galaxy-ui-redesign/live-template/brand-boundary.md`: list every intentionally retained match with its category/reason, or explicitly record “no retained old-brand matches” when none exist.

- [x] **Step 2: Write failing top-bar and brand-boundary tests**

Top-bar test assertions:

```ts
expect(screen.getByRole('img', { name: '智星盒 StellaBox' })).toHaveAttribute('src', '/assets/img/logo-white.png');
expect(screen.getByText('智星盒')).toHaveClass('galaxy-brand-cn');
expect(screen.getByText('StellaBox')).not.toHaveClass('galaxy-brand-cn');
expect(screen.getByRole('banner')).toHaveStyle({ height: '52px' });
expect(screen.getByRole('button', { name: /回到首页/ })).toBeInTheDocument();
```

Python boundary test assertions:

- `terms.ts` and `privacy.ts` contain no old product name;
- user-facing Galaxy defaults contain no `弈航`/`BoardNavi`;
- `OFL-1.1.txt`, copyright/author fields, database values, and API enums are outside the replacement scan;
- all non-Chinese brand translations use `StellaBox`, while cn/tw use `智星盒`.

- [x] **Step 3: Run the tests and verify failure**

```bash
cd katrain/web/ui && npm test -- --run src/galaxy/components/layout/GalaxyTopBar.test.tsx
cd ../../.. && pytest tests/web_ui/test_stellabox_branding.py -q
```

Expected: FAIL because the Galaxy top bar does not exist and legal copy still names the old product.

- [x] **Step 4: Implement the 52px brand top bar with real assets**

The left home button must render, in order:

```tsx
<img src="/assets/img/logo-white.png" alt="智星盒 StellaBox" />
<span className="galaxy-brand-cn">智星盒</span>
<span className="galaxy-brand-latin">StellaBox</span>
```

Use the generated Long Cang face only on `.galaxy-brand-cn`; explicitly use `SYSTEM_UI_FONT` on `.galaxy-brand-latin`. Size the existing logo and text inside the 52px bar; do not redraw the logo. The optional right slot is restricted to global status and language controls—no page title, back action, or board tool.

- [x] **Step 5: Replace only authorized product-facing copy**

Update product name, agreement/privacy titles, `智星盒账号`, and `智星盒团队` as approved. Change old English product name to `StellaBox`. Remove the old oversized brand block from `GalaxySidebar` now that the brand lives in `GalaxyTopBar`, and update its old-logo test in the same task. Update brand-specific PO entries without overwriting unrelated dirty translations when the feature branch is later integrated; do not run a bulk formatter over the PO files.

- [x] **Step 6: Run tests and a post-replacement audit**

```bash
cd katrain/web/ui && npm test -- --run src/galaxy/components/layout/GalaxyTopBar.test.tsx
cd ../../.. && pytest tests/web_ui/test_stellabox_branding.py -q
rg -n --glob '!katrain/web/static/**' --glob '!katrain/web/static-kiosk-2d/**' --glob '!docs/**' --glob '!superpowers/**' '弈航|BoardNavi' katrain scripts
```

Expected: tests pass. Any remaining `rg` hit is listed in `brand-boundary.md` with a non-product reason; there are no unexplained user-facing hits.

- [x] **Step 7: Commit branding and legal copy**

```bash
git add katrain/web/ui/src/galaxy/components/layout/GalaxyTopBar.tsx katrain/web/ui/src/galaxy/components/layout/GalaxyTopBar.test.tsx katrain/web/ui/src/galaxy/components/layout/GalaxySidebar.tsx katrain/web/ui/src/galaxy/components/layout/GalaxySidebar.test.tsx katrain/web/ui/src/legal/terms.ts katrain/web/ui/src/legal/privacy.ts katrain/web/ui/src/galaxy/pages/Dashboard.tsx katrain/web/ui/src/galaxy/components/auth/LoginModal.tsx katrain/i18n/locales tests/web_ui/test_stellabox_branding.py superpowers/tracks/galaxy-ui-redesign/live-template/brand-boundary.md
git commit -m "统一智星盒产品品牌"
```

### Task 5: Build the all-breakpoint global navigation state and chrome

**Files:**
- Create: `katrain/web/ui/src/galaxy/components/layout/galaxyNavigation.tsx`
- Create: `katrain/web/ui/src/galaxy/components/layout/useGalaxySidebar.ts`
- Create: `katrain/web/ui/src/galaxy/components/layout/useGalaxySidebar.test.tsx`
- Create: `katrain/web/ui/src/galaxy/components/layout/GalaxyBottomNav.tsx`
- Create: `katrain/web/ui/src/galaxy/components/layout/GalaxyBottomNav.test.tsx`
- Create: `katrain/web/ui/src/galaxy/components/layout/ModulePlate.tsx`
- Create: `katrain/web/ui/src/galaxy/components/layout/ModulePlate.test.tsx`
- Modify: `katrain/web/ui/src/galaxy/components/layout/GalaxySidebar.tsx`
- Modify: `katrain/web/ui/src/galaxy/components/layout/GalaxySidebar.test.tsx`
- Modify: `katrain/web/ui/src/galaxy/components/layout/MainLayout.tsx`

- [x] **Step 1: Write failing tests for the navigation state machine**

Cover these transitions with mocked media queries and localStorage:

```text
1536 first visit -> docked, 240px, expanded, persisted only after a user action
1200 first visit -> docked, 216px, expanded
docked user collapse -> completely hidden; storage false; 44px expand target remains
1199 first visit -> overlay closed; no storage write
1199 open -> temporary Drawer; Escape/scrim/route change closes and focus returns
1200 -> 1199 -> overlay starts closed regardless of docked state
1199 -> 1200 -> restore stored docked value
1199 open -> 899 -> overlay state cleared and Drawer unmounted
1200 -> 899 -> sidebar unmounted and overlay state cleared
899 -> fixed bottom nav; no sidebar toggle
```

Name the single storage key exactly `galaxy.sidebar.docked.expanded.v1`.

- [x] **Step 2: Write failing component tests for preserved navigation and accessibility**

Assert all existing entries plus explicit Home exist in the desktop navigation, retain their current MUI icon types, and call `requestNavigation`. Assert the collapsed control and overlay close control are native buttons with at least 44×44 geometry and translated `aria-label`s. Update the old logo-size test because branding moved from the sidebar to the top bar; do not replace the icons with text glyphs or custom SVG.

For `ModulePlate`, assert a 40×40 back button, title, subtitle, optional arbitrary status node, `backTo` navigation, and no rendered back control when `showBack={false}`.

For the mobile navigation, assert at most five direct destinations and a “More” action containing every remaining destination; changing route closes “More”.

- [x] **Step 3: Run the focused tests and verify failure**

```bash
cd katrain/web/ui
npm test -- --run \
  src/galaxy/components/layout/useGalaxySidebar.test.tsx \
  src/galaxy/components/layout/GalaxySidebar.test.tsx \
  src/galaxy/components/layout/GalaxyBottomNav.test.tsx \
  src/galaxy/components/layout/ModulePlate.test.tsx
```

Expected: FAIL because the hook, bottom nav, module plate, and new sidebar API do not exist.

- [x] **Step 4: Centralize the existing navigation model**

Export a function that accepts `t` and returns `{ key, label, path, icon }[]`. Include Home plus Play, Research, Tsumego, Review, Live, Kifu, and Tutorials. Reuse exactly the current MUI icons; Home may use MUI `HomeIcon`. Both sidebar and bottom nav consume this model so entries cannot silently diverge.

- [x] **Step 5: Implement the responsive state hook**

Expose a discriminated result such as:

```ts
type GalaxyNavMode = 'wide-docked' | 'standard-docked' | 'narrow-overlay' | 'mobile';
interface GalaxySidebarState {
  mode: GalaxyNavMode;
  dockedWidth: 240 | 216 | 0;
  dockedExpanded: boolean;
  overlayOpen: boolean;
  toggle(): void;
  closeOverlay(): void;
  toggleButtonRef: React.RefObject<HTMLButtonElement | null>;
}
```

Use MUI media queries at 1536/1200/900. Persist only user changes in docked mode. Close overlay on location pathname change and breakpoint exit. Return focus to the toggle after Escape, scrim, or explicit close.

- [x] **Step 6: Implement the desktop sidebar and narrow overlay**

Use MUI `Drawer` with `variant="temporary"` for 900–1199 so focus trapping, Escape handling, scroll lock, and scrim are real behavior rather than simulated CSS. In docked mode render width 240 or 216 only when expanded; when collapsed render no 64px icon rail. Keep navigation independently scrollable and settings/account pinned below it. The shared toggle is an absolutely positioned/overlayed 44×44 button anchored to the body row's top-left edge; when the docked drawer is closed it consumes zero grid/flex width, and its z-index keeps it operable without reducing the board column. Add a component assertion that the collapsed sidebar wrapper has width `0` and the main region begins at the body row's left edge.

- [x] **Step 7: Implement mobile bottom navigation and the reusable module plate**

Below 900px, unmount the left sidebar and its toggle. Fix the bottom navigation to the viewport, render no more than five direct entries, and put all remaining entries in an accessible MUI menu/drawer opened by “More”. Reserve its height in the main content scroll container.

Implement `ModulePlate` as a pure layout component with `title`, optional `subtitle`, `backTo`, `showBack`, and `status?: ReactNode`; it must not know live or ladder states.

- [x] **Step 8: Rebuild MainLayout around the 52px top bar**

Use this load-bearing hierarchy:

```text
.galaxy-root (100dvh, overflow hidden)
  GalaxyTopBar (52px, flex none)
  body row (flex 1, min-height 0)
    docked sidebar when expanded (zero-width when collapsed)
    main (flex 1, min-width 0, min-height 0)
    absolute shared sidebar trigger (zero layout width)
  mobile bottom nav (<900 only)
```

Mount `GalaxyTopBar` above both sidebar and main. Keep `GameNavigationProvider`. Do not give `main` a universal `overflow:auto`; board pages will define their own single scroll container in Chunk 2.

- [x] **Step 9: Run focused tests and builds**

```bash
npm test -- --run \
  src/galaxy/components/layout/useGalaxySidebar.test.tsx \
  src/galaxy/components/layout/GalaxySidebar.test.tsx \
  src/galaxy/components/layout/GalaxyBottomNav.test.tsx \
  src/galaxy/components/layout/GalaxyTopBar.test.tsx \
  src/galaxy/components/layout/ModulePlate.test.tsx
npm run build
npm run build:kiosk-2d
```

Expected: focused tests and both builds pass; kiosk verification finds neither `/galaxy/` nor Galaxy font residue.

- [x] **Step 10: Commit the responsive chrome**

```bash
git add katrain/web/ui/src/galaxy/components/layout
git commit -m "添加 galaxy 响应式导航框架"
```

## Chunk 2: Real Live-Match Board Template Vertical Slice

### Task 6: Implement the business-neutral board page shell

**Files:**
- Create: `katrain/web/ui/src/galaxy/components/board/BoardPageShell.tsx`
- Create: `katrain/web/ui/src/galaxy/components/board/BoardPageShell.test.tsx`

- [x] **Step 1: Write failing structural and responsive tests**

Render named sentinel nodes into `board`, `modulePlate`, `railBody`, `displayControls`, and `actions` slots. Assert the shell creates these stable test IDs and responsibilities:

```ts
expect(screen.getByTestId('board-page-shell')).toHaveStyle({ overflow: 'hidden' });
expect(screen.getByTestId('board-stage')).toHaveTextContent('BOARD');
expect(screen.getByTestId('board-stage')).not.toHaveTextContent('MODULE');
expect(screen.getByTestId('board-rail-module')).toHaveTextContent('MODULE');
expect(screen.getByTestId('board-rail-scroll')).toHaveTextContent('BODY');
expect(screen.getByTestId('board-rail-scroll')).toHaveTextContent('CONTROLS');
expect(screen.getByTestId('board-rail-actions')).toHaveTextContent('ACTIONS');
```

Mock MUI media queries and assert:

```text
1536 -> horizontal, rail 380px
1200 and 1440 -> horizontal, rail 340px
900 and 1199 -> horizontal, rail 320px
899 and 430 -> vertical, rail full width after board, actions in normal flow
```

Also assert the horizontal rail has exactly one scrolling middle region, while module/action regions are `flex:none`; the board stage is `min-width:0`, `min-height:0`, `display:grid`, `place-items:center`, and `padding:10px`.

- [x] **Step 2: Run the shell test and verify failure**

```bash
cd katrain/web/ui
npm test -- --run src/galaxy/components/board/BoardPageShell.test.tsx
```

Expected: FAIL because `BoardPageShell` does not exist.

- [x] **Step 3: Define the minimal slot contract**

Use a focused public interface:

```ts
export interface BoardPageShellProps {
  board: React.ReactNode;
  modulePlate: React.ReactNode;
  railBody: React.ReactNode;
  displayControls?: React.ReactNode;
  actions: React.ReactNode;
  onBoardSizeChange?: (edge: number) => void;
}
```

The shell must not import `MatchDetail`, `MoveAnalysis`, live hooks, ladder types, or route-specific copy.

- [x] **Step 4: Implement horizontal geometry**

For `min-width:900px`, render a two-column body: `minmax(0, 1fr)` plus the exact breakpoint rail width. The shell consumes 100% of `MainLayout`'s main width/height. Center the board in a 10px-padded grid and observe the board stage with `ResizeObserver`, calling `onBoardSizeChange(Math.floor(Math.min(contentWidth, contentHeight)))` only when the integer edge changes.

The right rail is `display:flex; flex-direction:column; min-height:0`. Module and actions are non-scrolling. Put `railBody` then `displayControls` inside one `overflow-y:auto; min-height:0` middle region so the rail never develops competing nested page scrollbars.

- [x] **Step 5: Implement the `<900px` vertical structure**

At 899px and below, the shell itself becomes the single vertical scroll container. Render the board first in a width-limited square stage, then a full-width rail section in this order: module plate, rail body, display controls, actions. All rail regions use natural height; actions are reachable by scrolling rather than fixed to the viewport. Add bottom padding equal to the mobile navigation height plus safe-area inset. Keep `.galaxy-root` and `MainLayout` non-scrolling.

- [x] **Step 6: Run the focused test and build**

```bash
npm test -- --run src/galaxy/components/board/BoardPageShell.test.tsx
npm run build
```

Expected: test and build pass. No board page has been migrated yet, so this commit is a reusable but dormant shell.

- [x] **Step 7: Commit the shell**

```bash
git add katrain/web/ui/src/galaxy/components/board/BoardPageShell.tsx katrain/web/ui/src/galaxy/components/board/BoardPageShell.test.tsx
git commit -m "添加 galaxy 棋盘页布局壳层"
```

### Task 7: Let the existing board fit small containers without altering its artwork

**Files:**
- Create: `katrain/web/ui/src/galaxy/components/board/useBoardCoordinates.ts`
- Create: `katrain/web/ui/src/galaxy/components/board/useBoardCoordinates.test.ts`
- Modify: `katrain/web/ui/src/components/live/LiveBoard.tsx`
- Modify: `katrain/web/ui/src/components/live/LiveBoard.test.tsx` (create if absent)

- [x] **Step 1: Write failing tests for canvas sizing and coordinate defaults**

For `LiveBoard`, mock a 380×380 `ResizeObserver` target and assert:

```text
default props -> existing 400px minimum remains (protects current callers)
minimumCanvasSize={0}, minContainerHeight={0} -> canvas becomes 372px, never 400px
both modes -> BOARD_ASSETS still request board.png, B_stone.png, W_stone.png
both modes -> showCoordinates still controls all four-side coordinate rendering
```

For `useBoardCoordinates(edge)`, assert:

```ts
expect(renderHook(() => useBoardCoordinates(499)).result.current.visible).toBe(false);
expect(renderHook(() => useBoardCoordinates(500)).result.current.visible).toBe(true);
```

After a user toggle, the explicit choice stays synchronized with the toggle and board while resizing across 500px. A new page/mount starts in automatic mode again; no global/localStorage preference is added in this slice.

- [x] **Step 2: Run focused tests and verify failure**

```bash
cd katrain/web/ui
npm test -- --run src/components/live/LiveBoard.test.tsx src/galaxy/components/board/useBoardCoordinates.test.ts
```

Expected: FAIL because `minimumCanvasSize` and `useBoardCoordinates` do not exist.

- [x] **Step 3: Add an opt-in minimum canvas size**

Extend the existing props without changing defaults:

```ts
minimumCanvasSize?: number; // default 400; responsive Galaxy page passes 0
```

Change only the sizing clamp:

```ts
const size = Math.floor(Math.min(width, height) - 8);
setCanvasSize(Math.max(minimumCanvasSize, Math.min(1200, size)));
```

Add `minimumCanvasSize` to the ResizeObserver effect dependencies. Do not change `BOARD_ASSETS`, board texture drawing, stone drawing, coordinates, stars, warm shadow, last-move marker, AI markers, or move parsing.

- [x] **Step 4: Implement the coordinate visibility hook**

Return `{ visible, userOverride, toggle, resetToAutomatic }`. Compute `visible` from `userOverride ?? edge >= 500`. The toggle must invert the currently rendered value, not a stale default, so its selected state always matches the canvas.

- [x] **Step 5: Run tests and the existing board wiring regressions**

```bash
npm test -- --run \
  src/components/live/LiveBoard.test.tsx \
  src/galaxy/components/board/useBoardCoordinates.test.ts \
  src/components/liveBoardWiring.test.ts \
  src/components/boardInteraction.test.ts
```

Expected: all pass; existing callers retain the 400px default.

- [x] **Step 6: Commit the opt-in board sizing behavior**

```bash
git add katrain/web/ui/src/components/live/LiveBoard.tsx katrain/web/ui/src/components/live/LiveBoard.test.tsx katrain/web/ui/src/galaxy/components/board/useBoardCoordinates.ts katrain/web/ui/src/galaxy/components/board/useBoardCoordinates.test.ts
git commit -m "支持 galaxy 棋盘完整缩放"
```

### Task 8: Extract accessible live display controls without changing their behavior

**Files:**
- Create: `katrain/web/ui/src/galaxy/pages/live/LiveMatchDisplayControls.tsx`
- Create: `katrain/web/ui/src/galaxy/pages/live/LiveMatchDisplayControls.test.tsx`

- [x] **Step 1: Write failing interaction tests**

Render the control component with controlled props and assert it preserves these controls and current MUI icon meanings:

```text
TouchApp -> try-move mode
Map -> territory; disabled when ownership is absent
FormatListNumbered -> move numbers
TipsAndUpdates -> AI recommendations
GridOn -> board coordinates
```

Each control must be a real `ToggleButton`, have a translated accessible name, reflect `selected`, and call only its matching callback. The disabled territory button must be wrapped in a non-disabled `<span>` inside its Tooltip so the explanation remains reachable. When try mode has moves, render the path and a 40px clear action; otherwise do not render the clear row.

- [x] **Step 2: Run the test and verify failure**

```bash
cd katrain/web/ui
npm test -- --run src/galaxy/pages/live/LiveMatchDisplayControls.test.tsx
```

Expected: FAIL because the extracted controls do not exist.

- [x] **Step 3: Implement the controlled presentation component**

Keep all business state in `LiveMatchPage`; accept booleans/callbacks plus `ownershipAvailable` and `tryMoves`. Use an equal-width responsive grid rather than allowing five labels to crush into a single 320px row: two rows are acceptable in the right rail, and every target is at least 40px high. Preserve the existing labels/translations and icons; add only the coordinate label/key needed for the fifth control.

- [x] **Step 4: Run the test and commit**

```bash
npm test -- --run src/galaxy/pages/live/LiveMatchDisplayControls.test.tsx
git add katrain/web/ui/src/galaxy/pages/live/LiveMatchDisplayControls.tsx katrain/web/ui/src/galaxy/pages/live/LiveMatchDisplayControls.test.tsx
git commit -m "整理直播棋盘显示开关"
```

Expected: all display-control interaction tests pass.

### Task 9: Migrate the real live-match detail page into the approved template

**Files:**
- Create: `katrain/web/ui/src/galaxy/pages/live/LiveMatchPage.test.tsx`
- Modify: `katrain/web/ui/src/galaxy/pages/live/LiveMatchPage.tsx`
- Modify: `katrain/web/ui/src/components/live/MatchInfo.tsx`
- Modify: `katrain/web/ui/src/components/live/MatchInfo.test.tsx` (create if absent)

- [x] **Step 1: Write failing page tests against the real component boundaries**

Mock only `useLiveMatch`, sound, and canvas-heavy child rendering. Supply a typed `MatchDetail` and analysis record, then assert:

```text
success -> BoardPageShell is present; board stage contains LiveBoard and no page header
success -> module plate contains translated black/white names, tournament/round, move count, and live/finished chip
success -> LiveBoard receives existing moves/currentMove/PV/AI/ownership/try-move props plus minimumCanvasSize=0, minContainerHeight=0, and the coordinate hook value
success -> rail body preserves MatchInfo, AiAnalysis, TrendChart
success -> display slot preserves all five controls
success -> action slot preserves PlaybackBar and its real callbacks
back -> requestNavigation/navigate returns to /galaxy/live
```

Test loading and error separately:

```text
loading -> same shell/rail geometry remains; skeleton/progress is visible; controls/actions disabled
error -> same shell remains; player-readable Alert and Retry button visible
retry -> awaits useLiveMatch.refresh; shows progress and disables Retry until it settles
retry -> old match data is not presented as refreshed data while the error branch is active
```

- [x] **Step 2: Write failing MatchInfo composition test**

Add `headingMode?: 'full' | 'metadata-only'` defaulting to `full`. Assert `metadata-only` hides only the duplicated live/finished chip and tournament/round title already represented by `ModulePlate`, while preserving the real date and source chip plus players, ranks, win-rate, score, rules, and komi. Existing callers without the prop must render unchanged.

- [x] **Step 3: Run focused tests and verify failure**

```bash
cd katrain/web/ui
npm test -- --run src/galaxy/pages/live/LiveMatchPage.test.tsx src/components/live/MatchInfo.test.tsx
```

Expected: FAIL because the page still uses the old header/500px sidebar and `MatchInfo` lacks `headingMode`.

- [x] **Step 4: Compose the module plate from real match data**

Use the existing translation helpers and fields—never hard-code sample players:

```text
title: translated black player vs translated white player
subtitle: translated tournament · round when present · currentMove / move_count moves
status: live error-colored chip or finished outlined chip
backTo: /galaxy/live
```

The module plate lives only in the right rail. Delete the old header above the board.

- [x] **Step 5: Compose the rail's single scroll region and fixed action**

Use `MatchInfo headingMode="metadata-only"`, the extracted display controls, `AiAnalysis`, and `TrendChart` in the shell's scrollable slots. The real date and source remain visible in `MatchInfo`; no existing match metadata is dropped. Put `PlaybackBar` alone in `actions` on horizontal viewports. Preserve PV hover, move clicking, live-follow, try-move clearing, territory availability, AI markers, move numbers, sound, and polling. Do not restore the deferred comment section.

- [x] **Step 6: Connect board-size reporting to coordinate visibility**

Store the integer edge reported by `BoardPageShell`, pass it to `useBoardCoordinates`, pass `visible` to `LiveBoard.showCoordinates`, and pass the same `visible`/`toggle` pair to the coordinate control. Pass `minimumCanvasSize={0}` and `minContainerHeight={0}` only from this responsive page; other board callers retain defaults.

- [x] **Step 7: Implement honest loading and error layouts**

For loading, render the same `BoardPageShell` structure with square board skeleton, module placeholder, rail skeletons, and disabled action placeholders so geometry does not jump. For error/no match, retain the shell, show a translated error in the rail and an enabled retry button wired through a local async `handleRetry`; the board area is an empty/skeleton state, not stale match content. `handleRetry` sets `retrying=true`, awaits `refresh()`, and clears it in `finally`; while true, the Retry button is disabled and contains a progress indicator without changing button geometry. Keep the back action available.

- [x] **Step 8: Run focused and live-hook regression tests**

```bash
npm test -- --run \
  src/galaxy/pages/live/LiveMatchPage.test.tsx \
  src/galaxy/pages/live/LiveMatchDisplayControls.test.tsx \
  src/components/live/MatchInfo.test.tsx \
  src/components/live/AiAnalysis.test.tsx \
  src/hooks/live/useLiveMatch.test.ts
```

Expected: all pass. No API request/response type or backend file changes in this task.

- [x] **Step 9: Run builds and inspect the source diff for asset preservation**

```bash
npm run build
npm run build:kiosk-2d
git diff --check
git diff -- katrain/web/ui/src/components/board/boardUtils.ts katrain/web/ui/public/assets/img/board.png katrain/web/ui/public/assets/img/B_stone.png katrain/web/ui/public/assets/img/W_stone.png
```

Expected: builds and diff check pass; the final asset-preservation diff is empty. If asset paths differ in this checkout, locate them with `rg --files` and verify the actual three existing files are unchanged.

- [x] **Step 10: Commit the real live template migration**

```bash
git add katrain/web/ui/src/galaxy/pages/live/LiveMatchPage.tsx katrain/web/ui/src/galaxy/pages/live/LiveMatchPage.test.tsx katrain/web/ui/src/components/live/MatchInfo.tsx katrain/web/ui/src/components/live/MatchInfo.test.tsx
git commit -m "迁移 galaxy 直播详情棋盘模板"
```

## Chunk 3: Browser Geometry, Same-Viewport Visual Gate, and Handoff

### Task 10: Automate breakpoint geometry and sidebar interaction acceptance

**Files:**
- Create: `katrain/web/ui/tests/galaxy-live-template.spec.ts`
- Modify: `superpowers/tracks/galaxy-ui-redesign/capture_live_template.mjs`

- [x] **Step 1: Write failing Playwright geometry tests**

Use the real application server supplied by the existing `playwright.config.ts`. Set one constant from `GALAXY_LIVE_MATCH_ID` with the baseline match ID as fallback. For each viewport, navigate to `/galaxy/live/${matchId}`, wait for the real canvas and `[data-testid="board-page-shell"]`, then assert:

```ts
const targets = [
  { width: 1535, height: 900, rail: 340, sidebar: 216, mode: 'horizontal' },
  { width: 1536, height: 900, rail: 380, sidebar: 240, mode: 'horizontal' },
  { width: 1537, height: 900, rail: 380, sidebar: 240, mode: 'horizontal' },
  { width: 1440, height: 900, rail: 340, sidebar: 216, mode: 'horizontal' },
  { width: 1201, height: 800, rail: 340, sidebar: 216, mode: 'horizontal' },
  { width: 1200, height: 800, rail: 340, sidebar: 216, mode: 'horizontal' },
  { width: 1199, height: 800, rail: 320, sidebar: 0, mode: 'horizontal' },
  { width: 1024, height: 768, rail: 320, sidebar: 0, mode: 'horizontal' },
  { width: 901, height: 700, rail: 320, sidebar: 0, mode: 'horizontal' },
  { width: 900, height: 700, rail: 320, sidebar: 0, mode: 'horizontal' },
  { width: 899, height: 700, rail: null, sidebar: 0, mode: 'vertical' },
  { width: 430, height: 880, rail: null, sidebar: 0, mode: 'vertical' },
];
```

Every case checks:

- top bar height is exactly 52px;
- `document.documentElement.scrollWidth <= innerWidth`;
- the canvas is square and wholly inside the board stage—no negative edge, overflow clip, or horizontal crop;
- no title/back/tool button is geometrically above the canvas inside the board column;
- the real logo resource is `/assets/img/logo-white.png`;
- horizontal rail width equals the target within 1px;
- horizontal module/actions intersect the viewport while only the middle rail is scrollable;
- vertical module/body/controls/actions follow the board and the action end is reachable by scrolling the shell;
- 1440×900 canvas is `828±2px`;
- 430×880 has fixed bottom navigation and its coordinate toggle starts unselected because the measured board edge is below 500px.

- [x] **Step 2: Write failing sidebar behavior tests**

Add explicit journeys:

```text
1536 docked collapse -> sidebar width becomes 0, rail remains 380, board canvas grows or stays height-limited, toggle remains >=44px
reload at 1200 -> stored collapsed state restored
1199 first enter -> overlay closed and localStorage untouched
1199 open -> canvas rectangle unchanged; background scroll locked; focus trapped
1199 Escape -> overlay closes and focus returns to trigger
1199 route click -> overlay closes
1200 -> 1199 -> overlay closed
1199 open -> 899 -> Drawer unmounted and bottom nav present
899 -> 1200 -> stored docked state restored
```

Use semantic labels/test IDs, never click by screen coordinate.

- [x] **Step 3: Run Playwright and verify the old/current implementation fails**

```bash
cd katrain/web/ui
npx playwright test tests/galaxy-live-template.spec.ts --project=chromium
```

Expected before the completed migration: FAIL on old 500px rail, missing responsive shell/sidebar behavior, or board clipping. If Chunk 2 was already applied before the test was authored, temporarily assert the old rail width of 500 to prove the test detects the contract, observe failure, then restore the approved assertion before proceeding.

- [x] **Step 4: Add stable selectors only at component boundaries**

If required by the tests, add `data-testid` only to `GalaxyTopBar`, sidebar/trigger, bottom nav, `BoardPageShell` regions, module plate, and live coordinate control. Do not annotate every visual child or expose business data solely for tests.

- [x] **Step 5: Make the capture script consume stable selectors and record font resources**

Update the script from Task 1 to write implementation measurements with the same schema as the reference. Add:

- computed `font-family` for `.galaxy-brand-cn`, `.galaxy-brand-latin`, a Chinese body label, an English label, and a numeric move counter;
- `performance.getEntriesByType('resource')` records for loaded `.woff2` URLs and transfer/encoded bytes;
- filesystem totals for generated source font assets and matching `wenkai-*`/`longcang-brand-*` files in the fresh Galaxy build, plus a matching-file count in the kiosk build;
- generator command/input hashes/license path copied from `sources.json` for one auditable budget record;
- rail/module/scroll/actions rectangles and `scrollHeight/clientHeight`;
- toggle/bottom-nav state and canvas visibility.

Write the resource data to `superpowers/tracks/galaxy-ui-redesign/visual/live-template/font-budget.json` and implementation geometry to `visual/live-template/geometry-implementation.json`.

- [x] **Step 6: Run Playwright until all geometry/interaction tests pass**

```bash
npx playwright test tests/galaxy-live-template.spec.ts --project=chromium
```

Expected: all target viewports and sidebar journeys pass. This proves geometry and behavior only; it does not satisfy visual approval.

- [x] **Step 7: Commit the browser acceptance test and capture updates**

```bash
git add katrain/web/ui/tests/galaxy-live-template.spec.ts superpowers/tracks/galaxy-ui-redesign/capture_live_template.mjs katrain/web/ui/src/galaxy
git commit -m "验证 galaxy 直播模板断点行为"
```

Expected: only selectors needed by the test are included with source changes.

### Task 11: Produce same-viewport visual evidence and stop for user approval

**Files:**
- Create: `tests/web_ui/test_compose_live_template_visuals.py`
- Create: `superpowers/tracks/galaxy-ui-redesign/compose_live_template_visuals.py`
- Create: `superpowers/tracks/galaxy-ui-redesign/visual/live-template/{1535x900,1536x900,1537x900,1440x900,1201x800,1200x800,1199x800,1024x768,901x700,900x700,899x700,430x880}/{implementation.png,side-by-side.png,overlay.png,diff.png,review.md}`
- Create: `superpowers/tracks/galaxy-ui-redesign/visual/live-template/geometry-implementation.json`
- Create: `superpowers/tracks/galaxy-ui-redesign/visual/live-template/font-budget.json`
- Create: `superpowers/tracks/galaxy-ui-redesign/visual/live-template/visual-review.md`
- Create after approval: `superpowers/tracks/galaxy-ui-redesign/visual/approved/live-template/{1535x900,1536x900,1537x900,1440x900,1201x800,1200x800,1199x800,1024x768,901x700,900x700,899x700,430x880}.png`

- [x] **Step 1: Write failing tests for evidence dimensions and composition**

Given a tiny temporary viewport directory containing `reference.png` and `implementation.png`, assert the script produces:

```text
side-by-side -> width = reference width + implementation width; same height
overlay -> same width/height as source; 50% alpha blend
diff -> same width/height as source; unchanged pixels black and changed pixels visible
mismatched input dimensions -> explicit nonzero failure naming the viewport
```

- [x] **Step 2: Run the composition test and verify failure**

```bash
uv run --with pillow pytest tests/web_ui/test_compose_live_template_visuals.py -q
```

Expected: FAIL because the composition script does not exist.

- [x] **Step 3: Implement the small deterministic Pillow composer**

Accept one `--visual-root`. Discover exact `<width>x<height>/` directories, require `reference.png` and `implementation.png` in each, and write `side-by-side.png`, `overlay.png`, and `diff.png` back into the same directory. Fail on missing/mismatched files. Use `Image.blend(reference, implementation, 0.5)` for overlay and `ImageChops.difference` for diff. Do not resize either source.

- [x] **Step 4: Capture implementation screenshots from the real backend**

Build the current branch, start the real backend on port 8901, verify readiness, capture, and always stop the process. Run from the implementation worktree root:

```bash
npm --prefix katrain/web/ui run build
python katrain/web/server.py --host 127.0.0.1 --port 8901 > /private/tmp/galaxy-live-template-server.log 2>&1 &
GALAXY_SERVER_PID=$!
for attempt in 1 2 3 4 5 6 7 8 9 10; do curl -fsS http://127.0.0.1:8901/health && break; sleep 1; done
curl -fsS http://127.0.0.1:8901/health
cd katrain/web/ui
node ../../../superpowers/tracks/galaxy-ui-redesign/capture_live_template.mjs implementation
cd ../../..
kill "$GALAXY_SERVER_PID"
wait "$GALAXY_SERVER_PID" || true
```

Expected: the capture script uses the fixed base `http://127.0.0.1:8901`; twelve viewport directories now contain `implementation.png`, and the slice root contains `geometry-implementation.json` plus `font-budget.json`. No fixture or mocked API is active. If capture fails, stop the recorded PID before retrying and inspect `/private/tmp/galaxy-live-template-server.log`.

- [x] **Step 5: Generate all comparison artifacts without resizing**

```bash
cd ../../..
uv run --with pillow python superpowers/tracks/galaxy-ui-redesign/compose_live_template_visuals.py \
  --visual-root superpowers/tracks/galaxy-ui-redesign/visual/live-template
```

Expected: `side-by-side.png`, `overlay.png`, and `diff.png` exist beside the two source files in every one of the twelve exact viewport directories; no source image was resized.

- [x] **Step 6: Audit the actual screenshots, not only metrics**

Fill each viewport's `review.md` and the slice-level `visual-review.md` summary with explicit observations for:

```text
composition and board priority
exact geometry/spacing and clipping
component hierarchy and scroll ownership
Chinese/Latin/numeric fonts
colors, borders, radii, and board material
real logo, current MUI icons, board/stone assets
copy, live/finished semantics, loading/error/disabled states
sidebar default/collapsed/overlay and mobile bottom navigation
899/430 shell scrolled to the action-region end with the fixed bottom navigation unobscured
```

Record the 1440 canvas target, rail widths, font-family samples, loaded font bytes, kiosk font absence, and every intentional deviation from the approved artifact. Each `review.md` records date, exact viewport, differences, user-approval state, and retained issues. Automated geometry PASS must not be written as visual PASS.

- [x] **Step 7: Present the complete visual set to the user and stop**

Show at minimum the 1440×900, 1024×768, 900×700, 899×700, and 430×880 implementation images plus their same-size side-by-side/overlay/diff artifacts. Include a scrolled mobile screenshot or the recorded scroll geometry proving actions are reachable above bottom navigation. Provide direct links to the remaining breakpoint evidence and summarize `visual-review.md`.

Expected: stop and wait for an explicit user visual confirmation. Do not begin Galaxy ladder contracts/backend, migrate other board pages, delete the reference set, or start kiosk design.

- [x] **Step 8: If the user rejects a visual detail, loop only within this slice**

Translate the feedback into a focused failing unit/Playwright assertion where practical, change the smallest relevant Galaxy component, rerun focused tests, recapture every affected viewport, regenerate comparisons, update `visual-review.md`, and request confirmation again. Preserve approved board/logo/icon assets throughout.

### Task 12: Run final verification and prepare the approved slice for integration

**Files:**
- Modify: `superpowers/tracks/galaxy-ui-redesign/visual/live-template/visual-review.md`
- Modify: `superpowers/tracks/galaxy-ui-redesign/visual/live-template/*/review.md`
- Create: `superpowers/tracks/galaxy-ui-redesign/visual/approved/live-template/*.png`
- Modify: `docs/superpowers/plans/2026-08-06-galaxy-shared-foundation-live-template.md` (checkboxes only during execution)

- [x] **Step 1: Record explicit user approval**

After confirmation, append the approval date, approved viewport evidence, and any accepted non-blocking differences to the slice summary and every viewport `review.md`. Copy each approved implementation byte-for-byte and verify it:

```bash
mkdir -p superpowers/tracks/galaxy-ui-redesign/visual/approved/live-template
for viewport_dir in superpowers/tracks/galaxy-ui-redesign/visual/live-template/*x*; do viewport=$(basename "$viewport_dir"); cp "$viewport_dir/implementation.png" "superpowers/tracks/galaxy-ui-redesign/visual/approved/live-template/$viewport.png"; cmp "$viewport_dir/implementation.png" "superpowers/tracks/galaxy-ui-redesign/visual/approved/live-template/$viewport.png"; done
```

Expected: all twelve `cmp` calls succeed. If approval is absent, this task must not run.

- [x] **Step 2: Invoke verification-before-completion and run the full relevant suite**

Read and follow `@superpowers:verification-before-completion`, then run from `katrain/web/ui`:

```bash
npm test
npx playwright test tests/galaxy-live-template.spec.ts --project=chromium
npm run build
npm run build:kiosk-2d
npm run lint
```

Run from repository root:

```bash
uv run --with fonttools --with brotli pytest tests/web_ui/test_build_galaxy_fonts.py tests/web_ui/test_stellabox_branding.py -q
uv run --with pillow pytest tests/web_ui/test_compose_live_template_visuals.py -q
git diff --check
git status --short
```

Expected: all new and existing frontend unit tests pass; the targeted Playwright suite passes; full and kiosk builds pass; kiosk boundary is clean; focused Python tests pass; diff check is clean. If repository-wide lint has pre-existing failures, record exact unchanged failures and prove every file changed by this branch passes an explicit `npx eslint <changed-ts/tsx-files>` run.

- [x] **Step 3: Recheck font and asset boundaries from fresh build output**

```bash
find katrain/web/static-kiosk-2d -type f | rg 'wenkai|longcang|galaxy-fonts' && exit 1 || true
rg -n "LXGW WenKai|Long Cang|/galaxy/" katrain/web/static-kiosk-2d && exit 1 || true
test -s katrain/web/ui/src/galaxy/assets/fonts/OFL-1.1.txt
test -s katrain/web/ui/src/galaxy/assets/fonts/sources.json
python -c "import json,pathlib; p=pathlib.Path('katrain/web/ui/src/galaxy/assets/fonts/sources.json'); d=json.loads(p.read_text()); assert d['generator_command']; assert all(s['sha256'] and s['version'] and s['license']=='SIL OFL 1.1' for s in d['inputs'])"
python -c "import json,pathlib; p=pathlib.Path('superpowers/tracks/galaxy-ui-redesign/visual/live-template/font-budget.json'); d=json.loads(p.read_text()); assert d['chinese_page']['request_count'] > 0; assert d['chinese_page']['encoded_bytes'] <= 511*1024; assert d['galaxy_build_font_bytes'] < 49*1024*1024; assert d['kiosk_build_font_matches'] == 0"
GALAXY_PLAN_BASE=$(tr -d '\n' < superpowers/tracks/galaxy-ui-redesign/visual/live-template/plan-base.txt)
git diff --exit-code "$GALAXY_PLAN_BASE" -- katrain/web/ui/src/components/board/boardUtils.ts katrain/img/board.png katrain/img/B_stone.png katrain/img/W_stone.png katrain/img/logo-white.png
```

Before these assertions, the capture/budget script must populate `font-budget.json` with: generated source asset total, Galaxy build font total, Chinese page request count/transfer/encoded bytes, kiosk match count, computed font samples, generator command, input SHA-256 values, and license path. Expected: the JSON assertions pass, no kiosk font/Galaxy route match exists, the license/source manifest is present, the Chinese page remains below the measured S0 upper bound, Galaxy total is below 49MB, and protected board/logo files plus drawing utilities are unchanged across the entire branch. The comparison uses the immutable plan-base SHA, never `HEAD~1`.

- [x] **Step 4: Invoke code review for the completed slice**

Read and follow `@superpowers:requesting-code-review`. Give the reviewer the approved spec, this plan, plan-base SHA, branch HEAD, test output, and `visual/live-template/visual-review.md`. Resolve blocking findings with focused tests; rerun the affected verification and update evidence if pixels changed.

- [x] **Step 5: Commit approved evidence and review fixes**

```bash
git add superpowers/tracks/galaxy-ui-redesign/visual tests/web_ui/test_compose_live_template_visuals.py superpowers/tracks/galaxy-ui-redesign/compose_live_template_visuals.py docs/superpowers/plans/2026-08-06-galaxy-shared-foundation-live-template.md
git commit -m "确认 galaxy 直播模板视觉验收"
```

Expected: the branch is clean after the commit. Generated `katrain/web/static*`, local databases/config, Playwright traces, source TTF files, and unrelated dirty-root work are not committed.

- [x] **Step 6: Prepare a non-destructive integration handoff**

Read and follow `@superpowers:finishing-a-development-branch`. Report commits, tests, visual evidence, font budget, and the fact that no ladder backend/kiosk work was started. Because the original worktree contains user-owned uncommitted ladder work and PO edits, do not merge/cherry-pick into it automatically; show the exact branch/commits and identify likely PO conflict files for the user to integrate safely.

Expected: this live-template slice is real, deployable, visually approved, and fixture-free on its feature branch. The next permitted plan is the separate Galaxy ladder journey; kiosk remains blocked on its own 1024×600 design approval.
