# Kifu Pagination Boundary Buttons Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Show first/last page icon buttons in the Galaxy game-record list, preserve Kiosk's existing buttons, and give both localized accessible names and hover hints.

**Architecture:** Enable Galaxy's existing `CompactPagination.showEdgeButtons` option. Reuse the shared SVG icons, `go`/`onPageChange`, exact API totals, disabled rules, and touch sizes; allow wrapping only within Galaxy's existing pagination container so the buttons fit its 320px rail. Add the two missing translation keys and shared `title` attributes. No new pagination abstraction, API request, backend work, or change to sorting, page size, authentication, loading/error behavior, or search persistence.

**Tech Stack:** Existing React/TypeScript UI, Vitest/Testing Library page tests, gettext PO catalogs, local Vite browser preview.

---

## Chunk 1: Existing pagination parity

### Findings and scope

- Base: local `develop` at `2c66860d5b4439cb0289a2944a9b07cfb213fc12`; that local ref was later verified not to contain `c507c7207e88a75182eeb0ef3770352f919a3a3a`. The release preserves that local work and cherry-picks this reviewed change onto fresh remote `develop`; see the release integration review.
- Worktree: `/Users/fan/.config/superpowers/worktrees/katrain-kiosk-debug/kifu-pagination-boundary-20261104`, branch `fix/kifu-pagination-boundary-20261104`. This global worktree is outside the repository. Its reused UI `node_modules` symlink is ignored by `katrain/web/ui/.gitignore`.
- `katrain/web/ui/src/kiosk/pages/KifuPage.tsx:352` already passes `showEdgeButtons`; no Kiosk product-code change is needed.
- `katrain/web/ui/src/galaxy/pages/KifuLibraryPage.tsx:594` omits the option, whose default is false.
- `katrain/web/ui/src/components/CompactPagination.tsx:44` and `:67` already implement first/last icons, boundary disabling, and existing navigation callbacks. The shared `disabled` flag remains authoritative.
- `katrain/web/ui/src/components/compactPagination.css` already defines 44px buttons, 8px gaps, disabled opacity, and focus indication. Reuse these values; do not alter unrelated styles.
- Galaxy's `BoardPageShell` supports a 320px rail and clips horizontal overflow. With boundary buttons enabled, the existing single-line form can exceed its available width. Permit the smallest Galaxy-only wrapping rule on its current pagination wrapper; preserve every 44px button and leave other consumers' layout unchanged.
- Both libraries use exact `total` from the existing list response and `Math.ceil(total / 20)`. Galaxy keeps its current rule of displaying the pager only for multiple pages. Kiosk keeps its current unavailable-total/error behavior.
- All 11 tracked locales lack `kifu:first_page` and `kifu:last_page`; the component currently falls back to Chinese.
- Baseline: the two existing page test files below pass, 34 tests total.

### Task 1: Focused page regression checks

**Files:**
- Modify: `katrain/web/ui/src/galaxy/pages/KifuLibraryPage.test.tsx`
- Modify: `katrain/web/ui/src/kiosk/pages/KifuPage.test.tsx`

- [x] Extend the existing page tests, using their existing API mocks and helpers. Do not create a separate test harness or a broad pagination suite.
- [x] Add one Galaxy test: return `total: 504`, search a nonempty query, and verify first is disabled on page 1 and last is enabled. Click last and assert exactly one additional `getAlbums` call with `{ q: <same query>, page: 26, page_size: 20, lang: 'cn' }`. Wait for accepted results, verify last is disabled, click first, and assert exactly one additional call with the same query and `page: 1`. Verify each boundary button's `title` matches its accessible name.
- [x] Extend Kiosk's existing `uses twenty-record server pagination and numeric page jump` test: on page 1, first is disabled and last is enabled; preserve its existing numeric jump to page 2; on page 2, last is disabled and first returns to page 1 through the existing API callback. Check the same two title/accessible-name pairs. No extra Kiosk product-code path is introduced.
- [x] Run the focused command and confirm the new checks fail because Galaxy's boundary buttons and shared titles are absent:

```bash
npm test --prefix katrain/web/ui -- src/galaxy/pages/KifuLibraryPage.test.tsx src/kiosk/pages/KifuPage.test.tsx
```

### Task 2: Enable existing buttons and labels

**Files:**
- Modify: `katrain/web/ui/src/galaxy/pages/KifuLibraryPage.tsx:594`
- Modify: `katrain/web/ui/src/components/CompactPagination.tsx:44`
- Modify: `katrain/i18n/locales/{cn,tw,en,jp,ko,de,es,fr,ru,tr,ua}/LC_MESSAGES/katrain.po`

- [x] Add `showEdgeButtons` to Galaxy's existing `<CompactPagination>` instance. Keep the default false and other consumers unchanged.
- [x] On Galaxy's existing pagination `<Box>`, scope a wrapping rule to its direct `.compact-pagination` child using the existing `sx` mechanism. This needs no new prop, class, or stylesheet. Preserve the wrapper's existing alignment/padding and all shared 44px button sizes and 8px gaps:

```tsx
sx={{
  display: 'flex', justifyContent: 'center', px: 1, pb: 2,
  '& > .compact-pagination': { flexWrap: 'wrap', minWidth: 0, maxWidth: '100%' },
}}
```

- [x] Add the following attributes to the existing boundary buttons, keeping their SVG, `disabled`, and click handlers intact:

```tsx
// First button
title={t('kifu:first_page', '第一页')}
// Last button
title={t('kifu:last_page', '最后一页')}
```

- [x] Add only these two nonempty, nonfuzzy PO entries in each tracked locale. The same keys supply both `aria-label` and `title`:

| Locale | `kifu:first_page` | `kifu:last_page` |
| --- | --- | --- |
| cn | 第一页 | 最后一页 |
| tw | 第一頁 | 最後一頁 |
| en | First page | Last page |
| jp | 最初のページ | 最後のページ |
| ko | 첫 페이지 | 마지막 페이지 |
| de | Erste Seite | Letzte Seite |
| es | Primera página | Última página |
| fr | Première page | Dernière page |
| ru | Первая страница | Последняя страница |
| tr | İlk sayfa | Son sayfa |
| ua | Перша сторінка | Остання сторінка |

- [x] Re-run the same focused command; expect all checks to pass. Check the two entries in every edited catalog for duplicates, empty/fuzzy values, and PO syntax using the existing PO parser or a one-time local check; do not add a persistent audit script or regenerate unrelated catalogs.

### Task 3: One representative real preview and delivery

**Files:** No permanent preview fixture or additional test suite required. Temporary local screenshots may live under `/tmp/kifu-pagination-boundary-20261104/`.

- [x] Start Vite from this worktree on a free, strict local port; verify the process's working directory. Use browser-level stubs for existing list/auth/translation endpoints as needed, with no production writes or permanent mock business data.
- [x] Inspect `/galaxy/kifu` at **1440×900**, using one multiple-page result (e.g. total 504), and capture one representative screenshot. Confirm the first/previous/page-input/jump/next/last order, existing icon style, readable total, 44px hit targets, and no clipped or overlapping footer controls. Exercise last→first in that same session and confirm one request per click. Use the actual English PO entries for an English label/title spot check if the browser stubs translations.
- [x] In the same browser session, perform one quick **320px Galaxy rail** overflow check (start with viewport **1024×900** and confirm the actual rail width is 320px). Check that every form control's bounding box stays within the available rail content bounds, the form's `scrollWidth <= clientWidth + 1`, and the five buttons retain at least 44×44px hit targets. Wrapping is allowed and must preserve DOM/keyboard order. This is a measurement-only check; no additional screenshot or viewport/state matrix is required.
- [x] Inspect `/kiosk/kifu` once at the existing target **1024×600**; confirm its existing boundary icons remain visible and the hints work. A second screenshot or full state recapture is unnecessary unless a visible defect appears. No new design artifact, four-up comparison, or layout redesign is needed for enabling this existing component option.
- [x] Run `git diff --check`; inspect that the final diff contains only the plan, the two UI components, the two focused test files, and the 22 PO entries. No full build or backend suite is required for this local change unless a concrete failure makes it necessary.
- [x] Send the final diff and focused test/browser results to ROOT for the requested independent Astra max code review. ROOT arranges at most two rounds of Astra max plan review before implementation and the final code-review gate; this plan author does not spawn reviewers.
- [x] Commit the scoped, reviewed change on this feature branch with the summary `show kifu first and last page buttons`, including this plan and both independent review records. Do not merge, push, deploy, touch servers/RK/PG/ES, resume cron, send external messages, or read/traverse `data/kifu-album/` as part of this task.

### Handoff status

Implementation and focused verification complete; the independent Astra max plan review (R2) and final code review are APPROVED. ROOT authorized the scoped commit including this plan and both review records. Existing unrelated worktrees and their untracked files remain untouched.

- Red: new Galaxy test failed because First page was absent; Kiosk extension failed because `title` was absent. Evidence: `/tmp/kifu-pagination-boundary-red.log`.
- Green: both existing page test files pass, **35/35**; Kiosk explicitly waits until page 2's first-page control is enabled before testing its last-page boundary and returning to page 1.
- All **22** new PO values are unique, nonempty, nonfuzzy, and valid quoted strings. `git diff --check` passes.
- One representative screenshot, visually inspected: `/tmp/kifu-pagination-boundary-20261104/galaxy-1440x900.png`. The existing form wraps when needed; no control is clipped.
- Galaxy browser last→first: list-call counts **3→4→5** (the initial three reflect preview setup reloads), pages **26→1**, unchanged `q=Shin` and `page_size=20`, and correct disabled boundaries. Actual English PO values supply both accessible names and titles.
- Narrow check at **1024×900**: outer rail **320px**, available content x=724–1004; form `clientWidth=scrollWidth=253`; all controls stay inside the bounds, every button is **44×44px**, and input is **56×44px**. No additional screenshot was taken.
- Kiosk at **1024×600**: existing first button bounds (665.55,460,44,44), last (964,460,44,44), both visible/in viewport; first disabled, last enabled, English titles correct.
- Temporary browser stubs existed only in `/tmp`; the setup script was removed and its browser session and dedicated Vite process were stopped. No product fixture or backend change was introduced. The screenshot and red-test log remain as review evidence.
