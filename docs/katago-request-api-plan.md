# KataGo Request API Integration Plan for KaTrain

## Goal
Use KataGo's HTTP/WebSocket request API endpoints (not GTP) to fetch structured analysis responses and render them on the KaTrain game board.

## Scope and Assumptions
- Endpoints follow `KataGo/docs/RealTimeIntegrationPlan.md`: `POST /analyze`, `WS /stream_analysis`, `GET /health`.
- Requests/Responses use the analysis JSON format (`moves`, `initialStones`, `rules`, `komi`, `moveInfos`, `rootInfo`).
- This is a planning document only; no code changes are made here.

## Dual Deployment Evaluation (Local + Cloud)
- Local KataGo (subprocess) is fast for interactive play, works offline, and keeps data on-device.
- Cloud KataGo (HTTP) enables heavy analysis and long-running review on GPUs.
- Two transports add complexity but keep existing workflows intact and enable selective use of cloud power.
- Recommendation: keep the current local KataGoEngine path, add an HTTP engine backend, and normalize responses into KaTrain's analysis structures.

## Plan
1. Engine profiles and routing
   - Define engine profiles: Local subprocess (existing) and Remote-HTTP (new).
   - Add a routing policy: manual selection, or automatic (local for live play, cloud for deep review/teacher mode).
   - Configure per-profile limits: max visits, timeouts, concurrency.
   - Use `GET /health` to detect remote availability and expose status.

2. Build request payloads from KaTrain game state (HTTP path)
   - Serialize the current node into KataGo analysis JSON:
     - `moves`: sequence from root to current node.
     - `initialStones`: handicap/setup stones from the root.
     - `rules`, `komi`, `boardSize` from KaTrain settings.
   - Generate a unique `id` per analysis request.
   - For streaming, configure the gateway to send periodic updates (aligned with KataGo's `reportDuringSearchEvery`).

3. Request flows
   - One-shot analysis: `POST /analyze` when analysis is triggered (manual analyze, background review, or teacher mode).
   - Live analysis: open `WS /stream_analysis` while analysis mode is active; push new requests on each move or navigation event.
   - For game-playing: use the top `moveInfos` entry as the candidate move and commit it to the game tree, tagging the source engine.
   - If multiple requests overlap, keep the newest `id` active and ignore older responses.

4. Response mapping into KaTrain analysis structures
   - Parse JSON response:
     - `moveInfos[]` mapped to KaTrain move recommendation entries (move, visits, winrate, scoreLead, PV).
     - `rootInfo` mapped to the overall evaluation for the current node.
   - Convert KataGo coordinates to KaTrain's internal point representation and handle pass/resign.
   - Map local subprocess results into the same structure to keep UI logic unified.

5. Board and UI integration
   - Display top-N suggestions as overlays/heatmap on the board.
   - Render PV lines in the analysis panel and optionally on the board.
   - Keep the analysis cache keyed by node so revisiting a node restores its last analysis instantly.
   - Optionally render local quick results immediately, then replace with cloud results when available.

6. Reliability, fallback, and privacy
   - Debounce rapid navigation and coalesce repeated requests for the same position.
   - Apply timeouts and show user-friendly errors when the API is unreachable or busy.
   - If remote fails, fall back to local; if local is unavailable, allow remote-only mode.
   - Require explicit opt-in for remote analysis and support TLS/auth if needed.

7. Validation checklist
   - Verify board coordinate mapping against a known position from `RealTimeAPI_TestGuide.md`.
   - Confirm switching between Local and Remote preserves analysis UI and node association.
   - Ensure stale responses do not update the UI after quick navigation and fallbacks behave as expected.

## To-Do Questions
- What concrete routing policy should pick Local vs Cloud (e.g., visits thresholds, analysis modes)?
- How should the UI indicate Local vs Cloud (badge, status line, tooltip)?
