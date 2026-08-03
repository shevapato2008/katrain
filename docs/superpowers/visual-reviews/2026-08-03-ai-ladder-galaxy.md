# Galaxy AI升降级对弈 Visual Review — 2026-08-03

## Scope and verdict

This review covers the removable Galaxy dashboard fixture slice only. The final 1440×900 evidence shows the existing Dashboard unchanged without the demo query and the AI升降级对弈 card mounted between the welcome header and module grid for `placement`, `placed`, `pending`, `unavailable`, `error`, and `loading`.

No blocking card-level visual defect remains in the captured states. The final captures use the confirmed product wording `AI升降级对弈` / `开始升降级对弈`, and the placed/pending states expose the public rank name (`5段`) without the internal `第N档` field. This is ready for explicit visual confirmation; it is not approval to begin authoritative backend or AiSetup integration.

## Capture environment

- Worktree: `/private/tmp/katrain-ai-ladder-ranked-module`
- Frontend only: Vite on `http://127.0.0.1:5174`
- Browser viewport: exactly 1440×900 CSS pixels
- Browser state: anonymous, Chinese locale preference, empty translation payloads so checked-in fallback copy is visible
- Network isolation: final captures intercepted only exact-origin `http://127.0.0.1:5174/api/**` and `/assets/**` requests. Auth returned an anonymous 204 response; translation endpoints returned empty translation maps. No backend or KataGo service was started.
- Local logo limitation: `logo-white.png` is not in the Vite asset graph. The final capture session fulfilled `/assets/**` with a transparent 84×84 SVG, so the stable sidebar brand text remains but the bitmap logo is intentionally absent in both reference and implementation. This keeps comparisons honest and backend-free; it does not approve the production logo asset.
- Setup correction: an initial discarded interception used the broad pattern `**/api/**`, which also matched `/src/api/live.ts` and produced a blank page. Before the final `/assets/**` interception was added, discarded captures also exposed Vite's configured asset proxy and received 502 responses from port 8001. Port 8000 and KataGo were never contacted. Every evidence PNG listed below was recaptured after both interception rules were corrected; the final page loads reported 0 errors and only the two existing React Router future-flag warnings.

Commands used:

```bash
cd /private/tmp/katrain-ai-ladder-ranked-module/katrain/web/ui
npm run dev -- --host 127.0.0.1 --port 5174

cd /private/tmp/katrain-ai-ladder-ranked-module/output/playwright/ai-ladder-galaxy
/Users/fan/.codex/skills/playwright/scripts/playwright_cli.sh --session ai-ladder-galaxy open about:blank
/Users/fan/.codex/skills/playwright/scripts/playwright_cli.sh --session ai-ladder-galaxy resize 1440 900
# page.route intercepted the exact /api/** and /assets/** origin paths before navigation.
# Each URL below was opened, snapshotted, and captured with `screenshot --filename ...`.

for state_name in placement placed pending unavailable error loading; do
  ffmpeg -loglevel error -y -i reference.png -i "implementation-${state_name}.png" \
    -filter_complex "[0:v][1:v]hstack=inputs=2" "side-by-side-${state_name}.png"
  ffmpeg -loglevel error -y -i reference.png -i "implementation-${state_name}.png" \
    -filter_complex "[0:v][1:v]blend=all_expr='A*0.5+B*0.5'" "overlay-${state_name}.png"
  ffmpeg -loglevel error -y -i reference.png -i "implementation-${state_name}.png" \
    -filter_complex "[0:v][1:v]blend=all_mode=difference" "diff-${state_name}.png"
done
```

`sips -g pixelWidth -g pixelHeight` confirmed the reference and all six implementation/overlay/diff images are 1440×900; side-by-side images are two equal 1440×900 sources placed horizontally, so their result is 2880×900. `ffmpeg` completed all 18 state-comparison files without errors.

## Evidence index

All evidence is local and intentionally uncommitted under `output/playwright/ai-ladder-galaxy/`.

| State | Implementation | Side by side | 50% overlay | Pixel difference |
| --- | --- | --- | --- | --- |
| Existing Dashboard | [`reference.png`](../../../output/playwright/ai-ladder-galaxy/reference.png) | — | — | — |
| Placement | [`implementation-placement.png`](../../../output/playwright/ai-ladder-galaxy/implementation-placement.png) | [`side-by-side-placement.png`](../../../output/playwright/ai-ladder-galaxy/side-by-side-placement.png) | [`overlay-placement.png`](../../../output/playwright/ai-ladder-galaxy/overlay-placement.png) | [`diff-placement.png`](../../../output/playwright/ai-ladder-galaxy/diff-placement.png) |
| Placed | [`implementation-placed.png`](../../../output/playwright/ai-ladder-galaxy/implementation-placed.png) | [`side-by-side-placed.png`](../../../output/playwright/ai-ladder-galaxy/side-by-side-placed.png) | [`overlay-placed.png`](../../../output/playwright/ai-ladder-galaxy/overlay-placed.png) | [`diff-placed.png`](../../../output/playwright/ai-ladder-galaxy/diff-placed.png) |
| Pending settlement | [`implementation-pending.png`](../../../output/playwright/ai-ladder-galaxy/implementation-pending.png) | [`side-by-side-pending.png`](../../../output/playwright/ai-ladder-galaxy/side-by-side-pending.png) | [`overlay-pending.png`](../../../output/playwright/ai-ladder-galaxy/overlay-pending.png) | [`diff-pending.png`](../../../output/playwright/ai-ladder-galaxy/diff-pending.png) |
| Unavailable/provisional | [`implementation-unavailable.png`](../../../output/playwright/ai-ladder-galaxy/implementation-unavailable.png) | [`side-by-side-unavailable.png`](../../../output/playwright/ai-ladder-galaxy/side-by-side-unavailable.png) | [`overlay-unavailable.png`](../../../output/playwright/ai-ladder-galaxy/overlay-unavailable.png) | [`diff-unavailable.png`](../../../output/playwright/ai-ladder-galaxy/diff-unavailable.png) |
| Error | [`implementation-error.png`](../../../output/playwright/ai-ladder-galaxy/implementation-error.png) | [`side-by-side-error.png`](../../../output/playwright/ai-ladder-galaxy/side-by-side-error.png) | [`overlay-error.png`](../../../output/playwright/ai-ladder-galaxy/overlay-error.png) | [`diff-error.png`](../../../output/playwright/ai-ladder-galaxy/diff-error.png) |
| Loading | [`implementation-loading.png`](../../../output/playwright/ai-ladder-galaxy/implementation-loading.png) | [`side-by-side-loading.png`](../../../output/playwright/ai-ladder-galaxy/side-by-side-loading.png) | [`overlay-loading.png`](../../../output/playwright/ai-ladder-galaxy/overlay-loading.png) | [`diff-loading.png`](../../../output/playwright/ai-ladder-galaxy/diff-loading.png) |

## Visual findings

### Composition and geometry

- The reference preserves the existing 240 px fixed sidebar and the Dashboard's 1200 px maximum outer width. At 1440×900, main content begins at x=240 and uses 48 px page padding; the visible content aligns at x≈288 with an inner width of ≈1104 px.
- The welcome heading/tagline remain at the exact reference position. The card occupies the module grid's former top edge at y≈216 and spans the same ≈1104 px content width, so it reads as a dashboard status module rather than a separate page.
- The module cards retain their three-column geometry, 32 px gaps, icon blocks, and widths. The AI card pushes the grid downward without changing column sizing. A consistent ≈32 px gap separates card and grid.
- Approximate inspected card heights are 455 px placement, 449 px placed, 496 px pending, 503 px unavailable, 209 px error, and 235 px loading. The main pane scrolls; no content is clipped horizontally. At 900 px height, the first module row remains visible in every state, while lower rows naturally continue below the fold for taller states.
- The overlays and difference images localize all movement to the main content below the unchanged header: sidebar/header pixels remain aligned, and the module grid moves vertically as one unit. There is no lateral drift or viewport-size mismatch.

### Hierarchy, typography, color, and material

- `AI升降级对弈` is the card's strongest internal heading, followed by current placement/rank, chips, net-score meter, recent-five history, state message, and CTA. The order is consistent across ready states.
- Typography follows the existing MUI/Manrope theme: bold white headings, 16 px body copy, and secondary gray explanatory text. Numeric score and thresholds are readable and do not jump between states.
- Material is consistent with the Dashboard: deep charcoal `#0f0f0f` background, `#252525` paper, muted jade `#4a6b5c` primary action, subtle divider border, and rounded surfaces. The status card adds hierarchy without introducing a competing visual language.
- Semantic colors use the shared theme: green `#30a06e` for certified/win/promotion direction, amber `#e89639` for pending/provisional/unavailable, and coral `#e16b5c` for loss/demotion/error. Every color-coded meaning is accompanied by text and an icon or explicit label.

### Icons and assets

- Route, win/loss, pending, unavailable, and error semantics use the same MUI icon family as the existing sidebar/module cards. Outlined/filled differences correspond to role rather than appearing decorative.
- Win/loss pills are independently text-labelled (`胜`/`负`), so recent outcomes do not rely on green/red alone.
- The local bitmap-logo limitation is isolated to the capture environment as described above and affects reference/implementation equally. No AI-ladder-specific asset is missing.

### Copy and state semantics

- Placement shows `定级进度 3/5`, `当前对手：4级`, `已认证`, `服务器对弈`, score 0, three recent outcomes, and `继续定级`.
- Placed shows only the public rank `当前段位：5段`, score `+2`, five distinct recent outcomes, and `开始升降级对弈`. The internal rung number is absent.
- Pending keeps rank/history visible, adds the amber `本盘成绩结算中` status, and presents a clearly disabled `成绩结算中` button.
- Unavailable combines `暂定`, `该档位暂不可挑战`, and a disabled `暂不可挑战` button. This fails closed while still explaining why.
- The copy consistently distinguishes the cumulative score from the recent-five display: `最近5盘仅供展示，升降段只看累计净胜分`. No provider, recipe, model, temperature, visits, or 星阵 naming appears.

### Loading, error, and retry

- Loading reserves card space with two skeleton bars and the live status `正在加载升降级对弈状态…`; it exposes no misleading action.
- Error uses a full-width dark error alert with `升降级对弈状态加载失败` and a subordinate outlined `重试` control. It remains compact enough to keep the existing dashboard grid prominent.
- A live Playwright check clicked `重试`; the URL changed from `?ai-ladder-demo=error` to `?ai-ladder-demo=placement` and the placement content appeared immediately. No extra screenshot was needed because the resulting pixels are already captured as `implementation-placement.png`.

## Fixture deletion and deferred integration

- The fixture remains isolated in `src/features/aiLadder/__fixtures__/galaxyDemo.ts` and must be deleted when the authoritative status API replaces the visual fixture. Production behavior remains query-free because the mount is gated by `import.meta.env.DEV` and a supported `ai-ladder-demo` query.
- Real authenticated status loading, durable placement/rank, settlement refresh, and unavailable/error retry against the server are deferred until the authoritative API slice.
- The CTA currently demonstrates routing to `/galaxy/play/ai?mode=ai_ladder_ranked`. Real Galaxy `AiSetupPage` consumption and server-issued ranked game start are deliberately deferred; this visual review does not claim that integration is complete.

## Confirmation gate

Proceed to backend/API integration only after explicit user confirmation of the reference and the stable-state side-by-side/overlay/difference evidence. Until then, this remains a removable visual fixture slice.
