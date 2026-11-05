# Territory view preview — 2026-11-05

Frontend tasks 1–3 are implemented. **ROOT relayed the user’s explicit visual approval on 2026-11-06: “按当前布局继续”. The visual gate is cleared.** ROOT assigned Task 4 backend endpoint/tests to a separate implementer; this frontend handoff adds only the optional `score_lead` TypeScript field and its dialog input. ROOT coordinates independent code review. No merge, push, deployment, real game, paid analysis or hardware command belongs to this preview.

## Composition and existing design

Read `ui-ux-pro-max` and the existing kiosk theme, `go-tokens.css`, `go-screens.css` side-dialog rules and `dialog-typography.css`. Reuse the existing jade/slate palette, SmartBox CJK/font stacks, purple outlined 380px side dialog and kiosk 18/22/28px portal hierarchy. A single large close action keeps the board visible. Buttons, backdrop and Escape use the same local hide action. Loading/error use the same shell and remain dismissible.

The static reference is an independently authored HTML result panel over the existing runtime game shell/Canvas. It does not represent an external approved artifact. Both reference and implementation use 1024×600. One representative result per source is captured; loading/error/boundary behavior is checked in focused unit tests, without a screenshot matrix.

Evidence directory: `/tmp/territory-view-dismissal-20261105/`.

| Source | Reference | Implementation | Comparison |
| --- | --- | --- | --- |
| Ranked | `ranked-reference.png` + `.html` | `ranked-implementation.png` | `ranked-side-by-side.png`, `ranked-overlay.png` |
| Star | `star-reference.png` + `.html` | `star-implementation.png` | `star-side-by-side.png`, `star-overlay.png` |

Actual geometry for both: dialog `(588,122.25) 380×355.5`; close target `(606,399.25) 344×62.5`; board `(16,70) 516×516`, right edge 532; rail overflow 0, document 1024×600. The reference uses the same width/right inset and a slightly taller composition (about 8px), with somewhat heavier type than the actual shared MUI portal rules. Those type/linebox differences are visible in the overlay; implementation follows the existing runtime kiosk typography. The board, component order, surface colors, actions and semantic copy agree. There is no new icon or artwork; the existing map icon remains on the territory action. Star quota wraps to two lines at the larger actual kiosk body size; the close target stays in view. No source claims exact black/white scores.

The user's later right-edge refinement keeps this same placement. The representative browser checks explicitly require `board.right <= dialog.left`, a fully transparent fullscreen backdrop, and the right-rail scrim starting at or beyond `board.right`. Actual values are `532 <= 588`, backdrop `rgba(0, 0, 0, 0)`, and scrim left 540px. The left board and its ownership shading remain clear; no additional or global dialog style change was needed.

## Source-specific contract and view lifecycle

- Ranked: preserve the server's per-game three-success ledger and existing request-ID retry. A cached successful answer is checked before zero-quota/new-request guards. The button has `aria-pressed`; closing removes the Canvas overlay but retains the answer. Same-scope pending work never adds another POST. Pending dismissal wins over a late answer while server `remaining` still updates. Position/enable generations reject old answers; session/account/game changes cannot overwrite the new scope's quota/error.
- Ranked ownership counts are labelled “黑/白方较确定区域 N 点”, never exact score totals or a derived lead. Current backend responses do not include `score_lead`, so this frontend preview honestly says “暂未取得领先判断”. The presentation accepts an optional finite black-perspective `lead`; its positive/negative/zero/missing behavior has direct tests. After ROOT relayed visual confirmation, the frontend type and dialog were connected to optional nullable `score_lead`; missing fields on old receipts retain the same honest missing-lead presentation and reuse ownership. The separate backend Task 4 supplies that field from the same analysis. There is no second analysis request.
- Star: keep one current-position `area` answer independently of the active overlay kind. Open→close→reopen and area→options→area reuse it without a new `area` call or quota refresh. Actual calls, including failures/stale positions, refresh account item counts. The platform insufficient dialog remains available; closing an in-flight area suppresses later unsolicited dialogs. No automatic retry/refund or claim that network failure means no charge.
- Both: scope includes account/auth identity, session, game, node, complete move/pass history through the current cursor, board/rules/komi/handicap and terminal state. Move, pass, end, account/session change and unmount invalidate current view. Only the mounted current page is cached. Closing hides the view, and the loading note explains that a new query after leaving the page may use quota.
- Both area paths remain Canvas-only. No global LED clear was added. Existing options→nonoptions `hintDismiss` and other engine overlay handling stay in place. Lobby territory behavior is unchanged.

## Fixture isolation and verification

`katrain/web/ui/tests/kiosk-territory-dialog.spec.ts` is a permanent test fixture. It intercepts all `/api/` and `/ws/` requests, supplies the two territory responses locally, reads only six named image Git blobs and blocks other backend media. Source-module URLs containing `/api/` or `/assets/` are explicitly allowed through to Vite. No production fake result or fixture route/entry point exists, so none needs deletion. If a temporary production entry is introduced later, remove it before integration; retain only test-local fixtures.

Run only the independent visual config (the default Playwright config starts a backend and is excluded):

```sh
KATRAIN_PW_VISUAL_PORT=5197 npm run test:e2e -- --config=playwright.visual.config.ts tests/kiosk-territory-dialog.spec.ts --project=chromium --workers=1
```

Port 5187 was already occupied; 5197 is exclusive to this worktree run. The mock runtime verifies visible dialog/close target, no rail/page overflow, actual Canvas pixel changes on open, Canvas restoration on close, zero-quota ranked reopen, and no second area call when switching Star tools. Result: **2/2 passed**.

TDD evidence: the new ranked/Star lifecycle assertions first failed against the original implementation (15 failures, 20 existing passes in the selected run); a later pending-insufficient assertion also failed before its small fix. Final related Vitest run: **132/132 passed across 4 files**. `npx tsc -b`: **passed**. A final enable-cycle single-flight test also failed first (two POSTs instead of one) and passed after keeping its quota scope independent of view enable generation; logs are `/tmp/territory-red-20261105.log`, `/tmp/territory-insufficient-red-20261105.log`, `/tmp/territory-enable-red-20261105.log`, `/tmp/territory-frontend-green-20261105.log`, `/tmp/territory-tsc-20261105.log` and `/tmp/territory-visual-20261105.log`. The existing count mock expectation in the engine suite was updated to include the already-existing auth-token argument; no count product behavior changed.

Sparse-worktree note: TypeScript requires the existing named `katrain/assets/board-equipment/go/stones/clamshell-slate/v1/source/recipe.json`; it was materialized unchanged from its Git blob for module resolution. Node modules are symlinked to the existing UI install. Excluded tracked entries remain `skip-worktree`. No filesystem access or status traversal of the prohibited album directory was used.

Runtime localization was checked separately: `katrain/core/lang.py` loads gettext `.mo` catalogs, and the existing root `i18n.py` compiles with `polib.pofile(...).save_as_mofile(...)`. Only the cn/en catalogs were compiled with that same method using the existing project virtualenv. The two explicitly requested `.mo` products are committed despite the general ignore rule; no other locale or PO normalization was run. A pure `gettext.GNUTranslations` check loaded each compiled file and verified all 20 new keys against its PO entry, including cn `领地判断` and en `Territory estimate`. It did not import/start the app or access runtime data.

## Remaining gates

1. Visual approval: complete, explicitly relayed by ROOT on 2026-11-06.
2. Separate Task 4 backend endpoint/tests implementation: ROOT has authorized another implementer; not part of this frontend commit.
3. ROOT’s independent spec/Astra code review and eventual integration/release workflow remain separate. No backend completion claim, merge or deployment is made by this frontend handoff.
