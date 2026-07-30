# Game Board Navigation Guard Design

## Problem

The shared 2D and 3D boards treat a click on an occupied intersection as a request to navigate the session to the node where that stone was played. Galaxy game pages and the kiosk game page pass the live session navigation callback into those boards, so an accidental tap rewinds the authoritative game tree instead of being ignored.

Galaxy multiplayer has a second boundary defect: `/api/nav` mutates the shared session without checking whether the game is still active. During a live multiplayer game, either player or a spectator can therefore change the authoritative `current_node`.

## Chosen Behavior

### Board interaction

- In every live-play page, clicking an occupied intersection does nothing.
- Clicking an empty intersection continues to submit a move, subject to the existing turn and game-over checks.
- Research and review contexts may retain click-to-navigate by explicitly passing `onNavigate` to the board.
- The 2D and 3D boards must share the same occupied-point semantics: navigate only when an explicit navigation callback is present; otherwise do not fall through to `onMove`.
- Explicit history controls such as score graphs and review navigation remain separate from direct board taps.

### Multiplayer API boundary

- `/api/nav` rejects every request for an unfinished Galaxy multiplayer session, regardless of whether the caller is Black, White, or a spectator.
- Multiplayer undo remains a separate workflow and is not changed.
- After a multiplayer game has ended, `/api/nav` requires an authenticated user before allowing history navigation.
- Native Galaxy multiplayer means a session with multiplayer player IDs and no registered platform-gateway context. Golaxy and other platform-backed sessions are explicitly excluded from this new guard even though they use virtual multiplayer player IDs.
- Local play, AI play, research sessions, and existing Golaxy engine pending guards retain their current behavior.

The active-game rejection is a server-side invariant, not merely a UI restriction, so direct API calls cannot bypass it.

## Implementation Boundaries

Frontend live-play consumers stop passing `onNavigate` into the board surface:

- `katrain/web/ui/src/galaxy/pages/GamePage.tsx`
- `katrain/web/ui/src/galaxy/pages/GameRoomPage.tsx`
- `katrain/web/ui/src/kiosk/pages/GamePage.tsx`
- `katrain/web/ui/src/ZenModeApp.tsx`

The shared 2D board is hardened so an occupied point without `onNavigate` is ignored rather than submitted as an illegal move. The existing 3D implementation already ignores that case, but live Galaxy pages must also stop opting into its navigation behavior.

The `/api/nav` endpoint gains a focused multiplayer-state/authentication guard before mutating the session. Guard ordering is: resolve the session (`404` remains authoritative), apply the existing Golaxy engine-pending guard, exclude platform-backed sessions, then apply the native Galaxy multiplayer lifecycle/authentication checks.

`WebSession` gains a persistent `game_ended` lifecycle marker. State broadcasts latch it to `true` whenever an authoritative state contains `end_result`; direct count completion also latches it because that path sets the terminal node without a normal state callback. New-game/game-setup paths reset it to `false`. `/api/nav` also latches from the current state before its first post-game navigation, making the boundary robust when a terminal state was produced by an older path. Navigating to an earlier node never clears the marker, so multiple post-game navigation requests remain allowed.

Authenticated post-game navigation is wired end-to-end: `API.navigate` accepts an optional token, `useGameSession.onNavigate` supplies its session token, and the legacy Zen app supplies its token. Research/local callers may continue omitting a token because the new authentication rule applies only to finished native Galaxy multiplayer sessions.

## Error Semantics

- Active multiplayer game: HTTP `409 Conflict`, detail `navigation disabled during active multiplayer game`.
- Finished multiplayer game without authentication: HTTP `401 Unauthorized`, detail `Authentication required for multiplayer navigation`.
- Existing missing-session and engine-move-pending errors are unchanged.

## Test Strategy

Tests are written before production changes and must demonstrate the original failures:

1. Shared 2D board: an occupied-point click with no navigation callback calls neither `onNavigate` nor `onMove`; an empty-point click still calls `onMove`.
2. Shared 3D board: the same occupied-point cases retain the same semantics.
3. Live page wiring: Galaxy AI, Galaxy multiplayer, kiosk live play, and legacy Zen live play do not give their board surfaces `onNavigate`; review/research behavior is not removed.
4. API client wiring: authenticated game-session and Zen navigation include the token, while tokenless research navigation remains supported.
5. Server endpoint: unfinished native Galaxy multiplayer navigation is rejected for anonymous and authenticated callers; a finished session rejects anonymous callers, permits repeated authenticated navigation after moving off the terminal node, and resets its lifecycle marker for a new game; a non-multiplayer session remains unaffected.
6. Platform boundary: a non-pending Golaxy/platform session is excluded from the new native-multiplayer guard, while the existing engine-pending navigation guard and its error precedence remain green.

The local Node 26 runtime currently causes one pre-existing kiosk test file to fail during setup because `localStorage` is unavailable. This is an environment limitation, not part of this change; verification will use focused tests that run under the current environment plus backend coverage.

## Non-Goals

- Redesigning score-graph or toolbar history navigation.
- Adding private per-client review cursors for live multiplayer games.
- Changing undo, redo, branching, SGF loading, or Golaxy engine history synchronization.
- Repairing the unrelated Node 26 `localStorage` test-runtime incompatibility.
