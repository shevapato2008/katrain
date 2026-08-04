# RK3562 AI Ladder Authority Proxy Design

## Problem and decision

In board mode, KaTrain correctly marks the local node as non-authoritative, but the AI ladder endpoints call only the local repository. An authenticated kiosk therefore receives HTTP 503 from `/api/v1/ai-ladder/status` even though `RemoteAPIClient` is authenticated against the configured Galaxy server.

The fix keeps the Galaxy server authoritative. The kiosk proxies status, start, game actions, state, and settlement observation to a server-owned ranked session. The RK3562 node never writes ladder profile or ledger rows and never submits a client-declared winner.

Rejected alternatives:

- Setting `ai_ladder_authoritative=True` in board mode would silently make the local SQLite database authoritative and break cross-device consistency.
- Uploading a result or SGF through a normal user bearer token would allow a user-controlled caller to manufacture a result; there is no provisioned device-attestation secret in the current architecture.
- Substituting a local rung when the remote server is unavailable would violate catalog certification and availability rules.

## Architecture

`RemoteAPIClient` gains typed methods for the authoritative ladder contract and a dedicated ranked-session state/action contract. A `RemoteRankedSessionGateway` stores only ephemeral routing state: immutable remote subject and SSO auth epoch, local owner id, remote session id, game id, user color, last authoritative state revision, and last state. It owns no rank or settlement data. Each session has one async lock shared by HTTP forwarding, state polling, and physical-move injection.

On a board node:

1. `catalog`, `status`, and `start` are forwarded with the remote bearer held by the backend.
2. `start` registers the returned remote session and returns a kiosk-safe local session id.
3. `/api/state`, move, resign, timeout, and count recognize that id and forward to dedicated server endpoints. Every mutation carries a deterministic `action_id` derived from `(remote subject, game_id, expected revision, action kind, canonical payload)` and the expected authoritative state revision. The server stores receipts scoped to `(remote subject, game_id, action_id)` for the ranked session lifetime, binds each receipt to the canonical request fingerprint, rejects reuse with another payload, serializes mutations, and rejects a stale expected revision without applying the action.
4. The existing local game WebSocket polls the authoritative remote state through the same per-session lock and emits the same `game_update` messages the React client already consumes. It publishes only a newer authoritative revision, so a slow poll cannot overwrite an action response. This avoids exposing the remote bearer to the browser.
5. Vision binding uses the same async gateway, not a synthetic synchronous `WebSession`. It validates the authoritative board size, human color, turn, SSO epoch, and expected revision before forwarding a physical move. A timeout leaves the action unresolved; the gateway polls/replays the same `action_id` before rearming detection. Expected-board and LED reconciliation consume only accepted monotonic remote state.
6. The existing settlement hook reads proxied `/ai-ladder/status`; settlement remains entirely inside the remote server's existing transaction and `game_id` idempotency boundary.

Deleting or leaving a local route never deletes an unsettled remote ranked session. Leaving an active game must use the authoritative resign/forfeit action. Local detach/unbind is allowed only after the authoritative state is terminal.

Galaxy/server mode continues through the current local authoritative code path unchanged.

## Contract and recovery

The public ladder payload remains the existing shared contract. Status additionally exposes an optional owner-only `active_game` projection so a kiosk browser or backend restart can rebuild its ephemeral route and continue a still-active server session. It includes remote session id, game id, immutable owner subject, user color, terminal flag, authoritative state revision, and the latest action receipt (id, request fingerprint, result revision, terminal flag). Recovery is locked and idempotent with one local route per remote game. The board proxy rewrites the remote session id in every response/event, not only in `active_game`; rung names, certification, availability, route, score, and recent results are forwarded unchanged.

Upstream HTTP status and detail are preserved for expected 4xx responses. Connection errors and timeouts become honest 503 responses. A failed read does not invent state. A timed-out mutation remains unresolved until polling observes a newer matching state or replay of the same `action_id` returns its stored response; no later mutation is accepted locally while one is unresolved. The WebSocket reports a retryable error and retries with a bounded interval. Authentication failure remains a login-required state.

Browser restart recovers from the board gateway mapping. Board-backend restart recovers from authoritative `active_game` plus its latest receipt before permitting a new mutation. Because IDs are deterministic from the prior revision and payload, replay after a lost response regenerates the same ID; if the authoritative revision already advanced, recovery adopts the receipt/state instead of creating a second action. Galaxy-server restart is fail-closed: until server sessions become durably reconstructable, losing the in-memory `WebSession` must retain the pending row and expose `server_session_lost`; it must never clear, settle, or replace the unfinished game. No local pending result or settlement is created.

## Security boundaries

- The browser receives only a local session id, never the remote access or refresh token.
- Gateway lookups require the current local shadow-user owner id, immutable remote subject, and SSO auth epoch.
- Box SSO generation replacement, login subject replacement, logout, or bridge clear atomically invalidates all mappings for the old epoch, stops pollers, unbinds remote-ranked vision, and closes registered game WebSockets.
- All result calculation, ranked game persistence, idempotent ledger insertion, placement, and promotion/demotion stay on the Galaxy server.
- Generic user-game upload remains forbidden for `game_type=ai_ladder_ranked`.
- Board mode remains `ai_ladder_authoritative=False` and never falls back to local ranked settlement.

## Test and acceptance strategy

Tests first cover remote-client request shapes, board status/start forwarding, upstream error mapping, owner/subject/epoch isolation, action deduplication and fingerprint mismatch, stale expected revisions, accepted-but-response-lost replay across a board-backend restart, monotonic state publication, WebSocket state projection, each restart case, logout during a binding, and physical move timeout reconciliation. Existing authoritative API and settlement tests remain unchanged and green.

After automated backend and frontend regression tests and a production build, deploy the KaTrain commit through the smartbox submodule to RK3562 without touching the existing `127.0.0.1:8000` KataGo service. Verify with account `fan`: ranked setup loads, start enters a game, state updates, physical/touch moves work, resignation settles once, status refreshes, and a new screenshot contains no authority-unavailable banner.
