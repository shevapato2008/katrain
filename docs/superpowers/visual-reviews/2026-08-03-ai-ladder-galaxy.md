# Galaxy 升降级对局设置 Visual Review — 2026-08-03

## Scope and corrected information architecture

The user-supplied production screenshot establishes `/galaxy/play/ai?mode=rated` as the authoritative reference. 升降级对弈 is a child flow under 对局; its 41 server-defined AI levels replace the rated page's HumanSL (`拟人`) strategy and `20k…9d` rank slider. The earlier standalone Dashboard preview is superseded and removed.

The corrected visual slice keeps the existing board/rules, color, timer, cancel, and play layout. In the right-side 对手与时间 panel, a compact `41档升降级AI` summary now shows the server-decided placement/current opponent, placement progress, certification, route, pending settlement, unavailable, loading, and retry states. The full cumulative net-score/recent-five card remains the personal-profile presentation and is deliberately not duplicated in the setup form.

This remains a removable DEV fixture. The bottom 对局 action is disabled in preview so it cannot start the legacy HumanSL path. Real ranked start is deferred until the authoritative API slice after explicit visual confirmation.

## Reference and capture environment

- Worktree: `/private/tmp/katrain-ai-ladder-ranked-module`
- Reference source: user-provided 3456×2062 Retina browser screenshot of `https://go.sailorvoyage.top/galaxy/play/ai?mode=rated`
- Reference preparation: crop the 242 px browser chrome, then scale the 3456×1820 page content to its 1728×910 CSS-pixel viewport
- Implementation: frontend-only Vite on `http://127.0.0.1:5175`
- Final browser viewport: exactly 1728×910 CSS pixels
- Network isolation: exact-origin `/api/**` routes were intercepted. AI constants/catalog used isolated preview responses, auth returned anonymous 401, and Chinese labels used a minimal translation response. `/assets/**` used a transparent logo placeholder because the production bitmap is not in the Vite asset graph.
- Because that isolated translation response intentionally contains only the current slice's labels, existing sidebar entries such as `Research`, `Review`, `Live`, `Settings`, and `Sign In` fall back to English in the implementation captures while the production reference shows Chinese. This is a capture-fixture difference outside the opponent panel, not a proposed copy change or evidence of full-page copy parity.
- The initial discarded page load occurred before route interception and let Vite attempt its configured port 8001 proxy; every request was refused because no service was listening. Routes were then installed and the page reloaded before any retained screenshot. Port 8000 and the KataGo experiment were never contacted; no backend state, calibration output, or database was changed.
- Final console: the expected anonymous `/api/v1/auth/me` 401 plus the two existing React Router future warnings; no feature runtime exception.

The reference includes the user's green arrow annotation over the old HumanSL selector. That annotation remains in reference/overlay/difference evidence and is not part of the product UI.

## Evidence index

All 25 PNGs are local and intentionally uncommitted under `output/playwright/ai-ladder-rated-setup/`.

| State | Implementation | Side by side | 50% overlay | Pixel difference |
| --- | --- | --- | --- | --- |
| Production HumanSL reference | [`reference.png`](../../../output/playwright/ai-ladder-rated-setup/reference.png) | — | — | — |
| Placement | [`implementation-placement.png`](../../../output/playwright/ai-ladder-rated-setup/implementation-placement.png) | [`side-by-side-placement.png`](../../../output/playwright/ai-ladder-rated-setup/side-by-side-placement.png) | [`overlay-placement.png`](../../../output/playwright/ai-ladder-rated-setup/overlay-placement.png) | [`diff-placement.png`](../../../output/playwright/ai-ladder-rated-setup/diff-placement.png) |
| Placed | [`implementation-placed.png`](../../../output/playwright/ai-ladder-rated-setup/implementation-placed.png) | [`side-by-side-placed.png`](../../../output/playwright/ai-ladder-rated-setup/side-by-side-placed.png) | [`overlay-placed.png`](../../../output/playwright/ai-ladder-rated-setup/overlay-placed.png) | [`diff-placed.png`](../../../output/playwright/ai-ladder-rated-setup/diff-placed.png) |
| Pending settlement | [`implementation-pending.png`](../../../output/playwright/ai-ladder-rated-setup/implementation-pending.png) | [`side-by-side-pending.png`](../../../output/playwright/ai-ladder-rated-setup/side-by-side-pending.png) | [`overlay-pending.png`](../../../output/playwright/ai-ladder-rated-setup/overlay-pending.png) | [`diff-pending.png`](../../../output/playwright/ai-ladder-rated-setup/diff-pending.png) |
| Unavailable/provisional | [`implementation-unavailable.png`](../../../output/playwright/ai-ladder-rated-setup/implementation-unavailable.png) | [`side-by-side-unavailable.png`](../../../output/playwright/ai-ladder-rated-setup/side-by-side-unavailable.png) | [`overlay-unavailable.png`](../../../output/playwright/ai-ladder-rated-setup/overlay-unavailable.png) | [`diff-unavailable.png`](../../../output/playwright/ai-ladder-rated-setup/diff-unavailable.png) |
| Error/retry | [`implementation-error.png`](../../../output/playwright/ai-ladder-rated-setup/implementation-error.png) | [`side-by-side-error.png`](../../../output/playwright/ai-ladder-rated-setup/side-by-side-error.png) | [`overlay-error.png`](../../../output/playwright/ai-ladder-rated-setup/overlay-error.png) | [`diff-error.png`](../../../output/playwright/ai-ladder-rated-setup/diff-error.png) |
| Loading | [`implementation-loading.png`](../../../output/playwright/ai-ladder-rated-setup/implementation-loading.png) | [`side-by-side-loading.png`](../../../output/playwright/ai-ladder-rated-setup/side-by-side-loading.png) | [`overlay-loading.png`](../../../output/playwright/ai-ladder-rated-setup/overlay-loading.png) | [`diff-loading.png`](../../../output/playwright/ai-ladder-rated-setup/diff-loading.png) |

Reference, implementation, overlay, and difference images are 1728×910. Side-by-side images are 3456×910 from equal-size sources.

## Visual findings

### Composition and geometry

- Sidebar, page title, two-column grid, board/rules controls, timer controls, and bottom actions retain the reference geometry.
- The replacement occurs exactly in the reference arrow's target region: the old disabled `拟人` selector and `20k…9d` slider are absent only in the explicit preview.
- The compact summary preserves the right panel's overall height closely enough that 取消/对局 remain visible at 1728×910. The earlier full profile card pushed actions below the fold and was rejected during visual inspection.
- The left panel and all fixed rated-game rules remain unchanged. There is no horizontal overflow.

### Hierarchy, material, and semantics

- `41档升降级AI` identifies the new strength system without exposing rung numbers, model names, temperatures, visits, recipes, or 星阵 naming.
- Placement shows `定级对手：4级` and `定级进度 3/5`; placed shows `本局对手：5段`. These are server-decided summaries, not user-selectable strength controls.
- Certified/route state uses the existing jade/outlined-chip language. Pending and unavailable use amber plus icon and text; error uses an alert plus a 44 px retry action.
- The summary uses existing MUI typography, charcoal paper, rounded borders, shared icons, and theme tokens. ui-ux-pro-max guidance influenced the explicit progress indicator, visible labels, text-plus-color semantics, and disabled-state clarity; the repository's existing visual system takes precedence over generated style suggestions.

### Loading, retry, and fail-closed behavior

- Loading reserves the replacement region with a labelled skeleton.
- Error keeps timer controls visible and offers retry in the exact replaced region.
- A live Playwright click changed `ai-ladder-demo=error` to `ai-ladder-demo=placement` while preserving `mode=rated`, then rendered `定级对手：4级` and `定级进度 3/5`.
- Provisional/unavailable and pending settlement states keep the bottom 对局 action disabled. No adjacent or HumanSL fallback is presented.

## Fixture deletion and deferred integration

- Fixture: `src/features/aiLadder/__fixtures__/galaxyDemo.ts`; delete it when the authoritative status/start API replaces the visual preview.
- Preview gate: `DEV + mode=rated + ai-ladder-demo=<supported-state>`.
- Rated without an explicit preview query and all free-play flows remain unchanged in this visual slice.
- After visual approval, the real API must replace HumanSL for rated play, issue the immutable opponent/config snapshot, enable 对局 only when the selected rung is certified/available and settlement allows it, and remove all fixture paths.

## Confirmation gate

Proceed to authoritative database/API/AiSetup integration only after explicit confirmation of this corrected setup-page evidence. The full personal-profile status card will be integrated with the same contract in that later slice.
