# Codex Review Feedback: Kiosk UI Alignment Plan — SBC v2

## Overall Assessment

**Verdict:** Reject with reasons.

The plan is directionally correct on the feature gaps, but it is not safe to execute as written.

- Task 2 correctly identifies the immediate 404 source.
- Task 1 does not prove its root cause from the current code and risks fixing the wrong layer.
- Task 3 proposes a `Board` integration that is not type-safe and is unlikely to compile without substantial extra work.
- Task 4 cannot reuse `HvHLobbyPage` directly without path and layout adaptation.
- The plan omits required test updates and a hardware-first verification step, which is important because the reported issues came from SBC device testing rather than desktop reproduction.

## Task 1: Stone Placement Offset

### Agreement / Disagreement

I do **not** agree that the root cause is already established.

- In [`katrain/web/ui/src/components/Board.tsx:580`](../../../katrain/web/ui/src/components/Board.tsx#L580), the canvas has `width` and `height` attributes, but there is no evidence in the current code that the flex container is stretching it visually.
- The more concrete risk in the current implementation is that `canvasSize` is artificially capped by `window.innerHeight - 100` in [`katrain/web/ui/src/components/Board.tsx:81`](../../../katrain/web/ui/src/components/Board.tsx#L81). On a 600px-tall kiosk screen, that can produce a drawing buffer smaller than the board slot.
- If you add `width: 100%` and `height: 100%` without also changing how `canvasSize` is computed, you may create a new CSS-to-buffer mismatch and get blur or scaling artifacts.
- There is another plausible kiosk-only factor: the whole app is wrapped in a rotated fixed-position container in [`katrain/web/ui/src/kiosk/components/layout/RotationWrapper.tsx:4`](../../../katrain/web/ui/src/kiosk/components/layout/RotationWrapper.tsx#L4). If the affected device uses rotation `90` or `270`, transformed geometry needs to be ruled out before blaming the canvas style.

### Concerns / Risks

- The plan only patches [`Board.tsx`](../../../katrain/web/ui/src/components/Board.tsx), but [`katrain/web/ui/src/components/tsumego/TsumegoBoard.tsx:346`](../../../katrain/web/ui/src/components/tsumego/TsumegoBoard.tsx#L346) uses the same sizing and click-conversion pattern. If the sizing diagnosis is correct, Task 2 will unblock a second broken board immediately after Task 1.
- The click path still uses `React.MouseEvent` only in [`katrain/web/ui/src/components/Board.tsx:498`](../../../katrain/web/ui/src/components/Board.tsx#L498) and [`katrain/web/ui/src/components/Board.tsx:530`](../../../katrain/web/ui/src/components/Board.tsx#L530). On a touchscreen kiosk, the plan should not assume synthesized click behavior is sufficient without device verification.
- The same coordinate math is duplicated instead of using the shared helpers in [`katrain/web/ui/src/components/board/boardUtils.ts:29`](../../../katrain/web/ui/src/components/board/boardUtils.ts#L29) and [`katrain/web/ui/src/components/board/boardUtils.ts:64`](../../../katrain/web/ui/src/components/board/boardUtils.ts#L64), which makes future divergence likely.

### Better Approach

- Add a short pre-fix diagnostic step on the actual SBC:
  - Log `canvas.width`, `canvas.height`, `rect.width`, `rect.height`, `window.devicePixelRatio`, `window.visualViewport?.scale`, and current kiosk rotation.
  - Confirm whether the problem reproduces at rotation `0` only, or also at `90`/`270`.
- If the issue is display-size mismatch, align the implementation with [`LiveBoard`](../../../katrain/web/ui/src/components/live/LiveBoard.tsx#L659), which already uses `maxWidth: '100%'` and `maxHeight: '100%'` instead of forcing `100%` fill.
- If you touch coordinate conversion, patch the shared behavior across `Board.tsx` and `TsumegoBoard.tsx`, or extract the logic to `boardUtils.ts` so kiosk play and kiosk tsumego do not diverge again.
- For kiosk touch reliability, consider migrating the interaction handlers to pointer events rather than mouse-only handlers.

### Missing Considerations

- No explicit on-device verification of touch input.
- No portrait/rotation verification despite the transform wrapper.
- No regression coverage for shared board components.
- No mention that Task 2 depends on the same board interaction path if tsumego becomes reachable again.

## Task 2: Tsumego 404

### Agreement / Disagreement

I **agree** with the diagnosis that the current endpoint is wrong.

- [`katrain/web/ui/src/kiosk/pages/TsumegoLevelPage.tsx:25`](../../../katrain/web/ui/src/kiosk/pages/TsumegoLevelPage.tsx#L25) calls `/api/v1/tsumego/levels/${levelId}?per_page=50`, and that route does not exist.
- The available backend routes are exactly the ones listed in [`katrain/web/api/v1/endpoints/tsumego.py:79`](../../../katrain/web/api/v1/endpoints/tsumego.py#L79), [`katrain/web/api/v1/endpoints/tsumego.py:108`](../../../katrain/web/api/v1/endpoints/tsumego.py#L108), [`katrain/web/api/v1/endpoints/tsumego.py:151`](../../../katrain/web/api/v1/endpoints/tsumego.py#L151), and [`katrain/web/api/v1/endpoints/tsumego.py:197`](../../../katrain/web/api/v1/endpoints/tsumego.py#L197).

### Concerns / Risks

- The proposed code fetches each category without a `limit` parameter. The backend default is `limit=20` in [`katrain/web/api/v1/endpoints/tsumego.py:156`](../../../katrain/web/api/v1/endpoints/tsumego.py#L156), so the page will silently truncate larger categories.
- The plan says “combine results and group by category”, but the proposed code only flattens into a single array. The current UI in [`TsumegoLevelPage.tsx`](../../../katrain/web/ui/src/kiosk/pages/TsumegoLevelPage.tsx#L56) also does not render grouped sections, so the task description and UI scope do not match.
- In board mode, offline tsumego returns empty data rather than 404. See [`katrain/web/core/repository.py:140`](../../../katrain/web/core/repository.py#L140). The kiosk page needs an explicit “offline / unavailable” state, not just an empty problem list.
- The plan does not mention test fallout. The existing frontend test in [`katrain/web/ui/src/kiosk/__tests__/TsumegoLevelPage.test.tsx:14`](../../../katrain/web/ui/src/kiosk/__tests__/TsumegoLevelPage.test.tsx#L14) mocks the old `{ problems: ... }` response shape and will need to be rewritten.

### Better Approach

- Fetch categories first, then fetch problems with an explicit high limit such as `?limit=1000`, or derive the limit from each category’s `count`.
- Preserve category ordering and either:
  - keep the current flat grid intentionally, or
  - actually render grouped sections if “group by category” is a real requirement.
- Handle three distinct states in kiosk:
  - loading,
  - API error,
  - board-mode offline / empty result.
- If you want to keep the kiosk’s simpler 2-step flow, the frontend-only aggregation is fine. There are only a few categories, so the N+1 cost is acceptable. I do not think a new backend endpoint is required yet.

### Missing Considerations

- No `AbortController` or stale-request handling if `levelId` changes quickly.
- No defined behavior for partial category failure.
- No test updates named in the plan.
- No acknowledgment that Task 1 may still block interaction on the now-reachable tsumego board.

## Task 3: AI Setup Board Preview

### Agreement / Disagreement

I agree with the diagnosis that the current board preview is just a placeholder.

- [`katrain/web/ui/src/kiosk/pages/AiSetupPage.tsx:68`](../../../katrain/web/ui/src/kiosk/pages/AiSetupPage.tsx#L68) is a hardcoded brown box with text.

I do **not** agree with the proposed implementation using a fake `GameState` for `Board`.

### Concerns / Risks

- `BoardProps` requires `onMove` in [`katrain/web/ui/src/components/Board.tsx:5`](../../../katrain/web/ui/src/components/Board.tsx#L5). The proposed `<Board gameState={...} analysisToggles={{ coords: true }} />` will not type-check as written.
- `GameState` has many required fields in [`katrain/web/ui/src/api.ts:10`](../../../katrain/web/ui/src/api.ts#L10) that the sample object does not provide, including `game_id`, `handicap`, `current_node_index`, `history`, `last_move`, `commentary`, `is_root`, `is_pass`, `end_result`, `children`, `note`, `ui_state`, and `language`.
- The sample object uses `move_number`, which is not a `GameState` field at all.
- The nested `players_info` sample is incomplete relative to `PlayerInfo` in [`katrain/web/ui/src/api.ts:1`](../../../katrain/web/ui/src/api.ts#L1).
- Reusing the gameplay `Board` for a static preview is the wrong abstraction. `Board` is stateful gameplay UI, not a cheap board-rendering primitive.

### Better Approach

- Reuse [`LiveBoard`](../../../katrain/web/ui/src/components/live/LiveBoard.tsx#L25) instead of `Board`.
- This is already how kiosk renders non-session board previews:
  - [`katrain/web/ui/src/kiosk/pages/ResearchPage.tsx:67`](../../../katrain/web/ui/src/kiosk/pages/ResearchPage.tsx#L67)
  - [`katrain/web/ui/src/kiosk/pages/KifuPage.tsx:245`](../../../katrain/web/ui/src/kiosk/pages/KifuPage.tsx#L245)
- A preview implementation like `moves={[]}`, `currentMove={0}`, `boardSize={boardSize}`, `showCoordinates={true}` gives the user the expected wood texture, grid, stars, and coordinates without inventing fake session state.
- If the setup page later needs handicap stones or richer preview behavior, create a dedicated `BoardPreview` component on top of `boardUtils.ts`, not on top of `GameState`.

### Missing Considerations

- No test update in [`katrain/web/ui/src/kiosk/__tests__/AiSetupPage.test.tsx`](../../../katrain/web/ui/src/kiosk/__tests__/AiSetupPage.test.tsx#L27) to verify that a real board preview renders.
- No discussion of whether the preview should respond to `boardSize` only, or also `handicap` and `color`.
- No guard against accidental clickability if a gameplay board component is reused.

## Task 4: Online Lobby Route

### Agreement / Disagreement

I **agree** with the route-gap diagnosis.

- [`katrain/web/ui/src/kiosk/pages/PlayPage.tsx:33`](../../../katrain/web/ui/src/kiosk/pages/PlayPage.tsx#L33) navigates to `/kiosk/play/pvp/lobby`.
- [`katrain/web/ui/src/kiosk/KioskApp.tsx:41`](../../../katrain/web/ui/src/kiosk/KioskApp.tsx#L41) does not define that route.
- The wildcard redirect at [`katrain/web/ui/src/kiosk/KioskApp.tsx:53`](../../../katrain/web/ui/src/kiosk/KioskApp.tsx#L53) explains why the user perceives “nothing happens”: the app likely navigates and immediately falls back to `/kiosk/play`.

I do **not** agree that `HvHLobbyPage` can be reused directly without a wrapper or extraction.

### Concerns / Risks

- [`katrain/web/ui/src/galaxy/pages/HvHLobbyPage.tsx:104`](../../../katrain/web/ui/src/galaxy/pages/HvHLobbyPage.tsx#L104) hardcodes navigation to `/galaxy/play/human/room/${data.session_id}`.
- [`katrain/web/ui/src/galaxy/pages/HvHLobbyPage.tsx:128`](../../../katrain/web/ui/src/galaxy/pages/HvHLobbyPage.tsx#L128) hardcodes a rated prerequisite redirect to `/galaxy/play/ai?mode=rated`.
- [`katrain/web/ui/src/galaxy/pages/HvHLobbyPage.tsx:275`](../../../katrain/web/ui/src/galaxy/pages/HvHLobbyPage.tsx#L275) hardcodes the watch button path to `/galaxy/play/human/room/${game.session_id}`.
- The page also pulls in `FriendsPanel` in [`katrain/web/ui/src/galaxy/pages/HvHLobbyPage.tsx:9`](../../../katrain/web/ui/src/galaxy/pages/HvHLobbyPage.tsx#L9), which is a desktop-oriented dependency and not obviously required on kiosk.
- “MUI is inherently responsive” is not an adequate plan for 800x480. The current lobby layout uses large desktop spacing and dual action buttons in a wide header.

### Better Approach

- Create a kiosk wrapper, or better, extract a shared multiplayer-lobby component that accepts route builders and feature flags.
- At minimum, parameterize:
  - match-found room path,
  - watch path,
  - rated-prerequisite redirect path,
  - optional sidebar panels such as friends.
- Then wire `/kiosk/play/pvp/lobby` to the kiosk-specific wrapper in [`KioskApp.tsx`](../../../katrain/web/ui/src/kiosk/KioskApp.tsx#L39).
- Add kiosk-specific layout decisions for 800x480 and 1024x600 instead of assuming the Galaxy composition will fit.

### Missing Considerations

- No route-level test added to [`katrain/web/ui/src/kiosk/__tests__/navigation.integration.test.tsx`](../../../katrain/web/ui/src/kiosk/__tests__/navigation.integration.test.tsx#L76).
- No mocked WebSocket test for kiosk route behavior.
- No explicit audit of all hardcoded `/galaxy/` paths before reusing the page.
- No mention of auth/token dependency even though lobby APIs are authenticated.

## Cross-Cutting Plan Gaps

### 1. Missing Test Plan

The plan should name the test files that must change. At minimum:

- [`katrain/web/ui/src/kiosk/__tests__/TsumegoLevelPage.test.tsx`](../../../katrain/web/ui/src/kiosk/__tests__/TsumegoLevelPage.test.tsx#L1)
- [`katrain/web/ui/src/kiosk/__tests__/AiSetupPage.test.tsx`](../../../katrain/web/ui/src/kiosk/__tests__/AiSetupPage.test.tsx#L1)
- [`katrain/web/ui/src/kiosk/__tests__/navigation.integration.test.tsx`](../../../katrain/web/ui/src/kiosk/__tests__/navigation.integration.test.tsx#L1)
- likely a new kiosk lobby test file

Backend coverage already exists for:

- tsumego APIs in [`tests/web_ui/test_tsumego_api.py`](../../../tests/web_ui/test_tsumego_api.py#L1)
- lobby online-user behavior in [`tests/web_ui/test_lobby_api.py`](../../../tests/web_ui/test_lobby_api.py#L1)

### 2. Missing Shared-Component Impact Analysis

The plan says the affected UI is kiosk plus shared `Board.tsx`, but the real shared blast radius is larger:

- [`katrain/web/ui/src/components/Board.tsx`](../../../katrain/web/ui/src/components/Board.tsx#L1)
- [`katrain/web/ui/src/components/tsumego/TsumegoBoard.tsx`](../../../katrain/web/ui/src/components/tsumego/TsumegoBoard.tsx#L1)
- [`katrain/web/ui/src/components/board/boardUtils.ts`](../../../katrain/web/ui/src/components/board/boardUtils.ts#L1)
- optionally [`katrain/web/ui/src/components/live/LiveBoard.tsx`](../../../katrain/web/ui/src/components/live/LiveBoard.tsx#L1) if you standardize sizing behavior

### 3. Missing Device-First Verification

Because the reported defects came from RK3562/RK3588 kiosk testing, the plan should include a short hardware verification checklist, not only desktop browser checks:

- landscape and rotated portrait,
- actual touch input,
- 800x480, 1024x600, 1280x800,
- board mode online and offline behavior,
- Chromium kiosk mode after a fresh load.

## Recommended Plan Changes

I would revise the plan in this order:

1. Add a preflight diagnostic step for Task 1 on the actual SBC to verify whether the bug is CSS scaling, transformed geometry, or touch event handling.
2. Rewrite Task 1 to cover shared board interaction paths, not only `Board.tsx`.
3. Rewrite Task 2 to include explicit `limit` handling, empty/offline states, and test updates.
4. Replace Task 3’s fake `GameState` approach with `LiveBoard` or a dedicated `BoardPreview`.
5. Rewrite Task 4 around a kiosk wrapper or extracted shared lobby component, not direct `HvHLobbyPage` reuse.
6. Add explicit frontend test file updates and a hardware verification section to the plan.

## Suggested Revised Execution Order

1. Diagnose and fix shared board interaction behavior on kiosk hardware.
2. Fix `TsumegoLevelPage` data flow and verify that `TsumegoProblemPage` is actually playable on-device.
3. Replace the AI setup placeholder using `LiveBoard` or `BoardPreview`.
4. Add the kiosk lobby wrapper/route and validate all route transitions away from `/galaxy/...`.

## Final Recommendation

Do not execute `plan.md` unchanged.

The highest-value corrections before implementation are:

- prove the stone-placement root cause on-device,
- stop using fake `GameState` for the setup preview,
- and avoid direct `HvHLobbyPage` reuse without route parameterization.

Once those are rewritten, the plan should be safe to downgrade from **Reject** to **Approve with changes**.
