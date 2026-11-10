# Lobby Game Spec Compliance Review — 2026-10-23

**Status: Approved**

Independently reviewed the actual implementation diff against base `5016186ed`, the approved fullstack plan, and the accepted 06a lobby reference. Reviewed backend commit `0e223cb454458e549874e98ce3159a3c4283a652` and final frontend commit `351b28dc4947d80b656ad8bea493daf1180a0c94`. No material missing, extra, or misinterpreted requirements found.

- `katrain/web/core/pvp_territory.py` and the narrow server route require authenticated ordinary human lobby participation, snapshot the authoritative tree under the session lock, reuse the existing bounded engine client and temporary analysis lease, return only validated ownership and position identity, and recheck authority/position after awaiting. Mirror forwarding rechecks box generation, mapped room, session and current position without applying or broadcasting private analysis. General analysis guards remain unchanged.
- `useLobbyTerritory.ts` is click-only, prevents duplicate requests, validates response identity/data, converts top-origin ownership to the board overlay, and suppresses cached or late answers across position, game, session and availability changes. Engine failure leaves a retryable control and does not alter play or formal count state.
- `GamePage.tsx` routes only `pvp_lobby` to the new paired panel, while retaining actual count/respond, degraded-count retry, official-result, resign/leave, physical synchronization, session-gone and central reconnect flows. Count identity failure only disables count; legitimate pass/resign remain available. Territory does not replace urgent count or hardware feedback.
- Inspected the actual same-size reference/runtime side-by-side and overlay images under `output/playwright/lobby-game-unified/`. Board and rail composition, paired trapezoids, 18/22/28 typography, four ordered horizontal actions, matching toggle sizes, tactile treatment and map-trifold icon match the approved slice. The existing shared topbar, actual touch/physical guidance and no-handicap wording remain; the footer gives an honest reference-only explanation. Central disconnection retains the truthful full-page reconnect state.

Read the focused backend, hook/component, GamePage and browser test cases covering the new contract and preserved journeys. The controller is independently rerunning the integrated checks and build; this spec review does not claim live GPU/production verification. KataGo responses and browser transports are mocked in the focused evidence. The known unrelated baseline local-confirmation mock failures are outside this slice.

No product files changed during review. Proceed to the separately required independent final code-quality review.
