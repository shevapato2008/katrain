# Golaxy Lobby, Invitation, and Live Spectator Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver the approved 1024 × 600 Golaxy lobby, usable quick match/rooms/player invitation, account switching, and responsive spectator experience using verified Golaxy data and honest unavailable states.

**Architecture:** Keep Golaxy credentials and third-party calls in the owner-bound server adapter. Discover minimal contracts, build isolated frontend runtime states, obtain same-viewport user visual approval, then integrate backend journeys. A server-owned Golaxy room subscription relays sanitized events to the browser; the authoritative room snapshot recovers after reconnect, with bounded polling labelled as a degraded fallback. Keep invitation writes disabled in both API and UI until invite, cancel, outcome, game handoff, and actual PvP moves are verified end to end with two accounts.

**Tech Stack:** FastAPI/httpx, Python/pytest, React/TypeScript/Vite/Vitest, existing `GoBoardSvg` and `useSound`, Playwright at 1024 × 600.

**Approved design:** `docs/previews/golaxy-lobby-spectator-redesign-1024x600.html`. Its Fixture data must never enter production. The spectator board fills the left panel. Follow repository `AGENTS.md` vertical slices and proportionality. Official JS is a route/payload clue, not proof of a successful write or event; see `katrain/web/platforms/golaxy/PROTOCOL.md`.

**Worktree:** `/Users/fan/.config/superpowers/worktrees/katrain-kiosk-go-cross-platform/golaxy-social-live`. Python tests use `/Users/fan/Repositories/katrain-kiosk-go-cross-platform/.venv/bin/python` because global Python lacks `sgfmill`. UI commands run in `katrain/web/ui`.

**File map:** `adapter.py` validates Golaxy wire data; `platforms.py` enforces ownership and HTTP errors; `api.ts` contains typed client calls; `GolaxyHomePage.tsx`/CSS own lobby, profile and account states; `GolaxySpectatorPage.tsx`/CSS own spectator controls. Preview Fixture stays in `docs/previews` or tests, never imported into production. Existing Golaxy tests are the focused test homes.

## Chunk 1: Contracts and approved runtime

### Task 1: Bound the Golaxy contracts

**Files:** Modify `katrain/web/platforms/golaxy/PROTOCOL.md`; read `/private/tmp/golaxy-app-20260922.js`, `/private/tmp/golaxy-gamezone.js`, observed JSON in `/private/tmp`, and current adapter/tests.

- [ ] Record observed keys/types for room type, both ranks, room total, user rank, wins/losses, invitation eligibility, avatar, and presence. `onlineUserCount` means all room users, never spectators. Decode enums only with first-party rendering or captured response evidence.
- [ ] Inspect profile and invitation call sites: caller versus peer code, client ID, submit/cancel/accept/reject/timeout and game handoff. Record sanitized schemas only, not account identifiers or secrets. Mark unobserved outcomes unverified.
- [ ] Inspect ordinary room detail for ordered history, game ID, clock units, active side, timing anchor, overtime, running state, and member identities/roles. Mark each verified, absent, or ambiguous.
- [ ] Document Golaxy room/game STOMP handshake, subscription, event schema and disconnect behavior where observable. Browser-held Golaxy credentials are prohibited; the server owns the subscription and relays sanitized events. Document bounded visible-page polling only as a clearly labelled degraded fallback. Commit `document Golaxy social contracts`.

### Task 2: Isolated 1024 × 600 React preview and user visual gate

**Files:** Modify `katrain/web/ui/src/kiosk/pages/GolaxyHomePage.tsx`, `katrain/web/ui/src/kiosk/pages/GolaxySpectatorPage.tsx`, `katrain/web/ui/src/kiosk-shell/golaxy-home.css`, `katrain/web/ui/src/kiosk-shell/golaxy-spectator.css`; create preview-only Fixture under `docs/previews/` or frontend tests, never a production import.

- [ ] Render approved lobby cards, player rows/profile, account menu, invite pregame/pending/error, and spectator with full-width left board, clocks/latest move, members, 上一手, 回到最新 and sound toggle. Fixture values remain isolated and removable.
- [ ] Capture reference and actual React runtime at 1024 × 600, side-by-side and overlay/difference evidence for lobby/profile and spectator. Correct material geometry, typography, icons, copy and state-semantic differences.
- [ ] Run `npm run build`; expect pass. Present runtime preview and comparison links for explicit user confirmation. **Stop dependent backend integration until the user confirms the implemented runtime**; independent read-only contract work may continue.
- [ ] Commit the approved frontend layout and preview harness as `align Golaxy runtime layouts`; remove harness in final integration.

## Chunk 2: Lobby/account vertical slice

### Task 3: Project verified room and online-user fields

**Files:** Modify `katrain/web/platforms/golaxy/adapter.py`, `katrain/web/ui/src/api.ts`, `tests/web_ui/test_golaxy_lobby.py`, `katrain/web/platforms/golaxy/PROTOCOL.md`.

- [ ] Add failing adapter tests with sanitized observed shapes for room type, player ranks, `room_user_count`, user rank, wins/losses, avatar, presence, `invite_able`, and missing/malformed fields. Assert no invented spectator count or unverified label.
- [ ] Run `/Users/fan/Repositories/katrain-kiosk-go-cross-platform/.venv/bin/python -m pytest tests/web_ui/test_golaxy_lobby.py -q`; expect new assertions to fail.
- [ ] Extend `get_rooms`/`get_online_users` with strict optional projections and compatible existing keys. Update TypeScript types. Run same pytest; expect pass. Commit `show verified Golaxy lobby details`.

### Task 4: Integrate real lobby, profile read, and account switch

**Files:** Modify `katrain/web/platforms/golaxy/adapter.py`, `katrain/web/api/v1/endpoints/platforms.py`, `katrain/web/ui/src/api.ts`, `katrain/web/ui/src/kiosk/pages/GolaxyHomePage.tsx`, `katrain/web/ui/src/kiosk-shell/golaxy-home.css`, `tests/web_ui/test_golaxy_lobby.py`, `katrain/web/ui/src/kiosk/pages/GolaxyHomePage.test.tsx`.

- [ ] Add failing owner-only backend tests for profile lookup, target validation, expired auth, malformed response, and caller/peer isolation. If Task 1 cannot establish profile semantics, show only verified lobby fields and do not guess a new endpoint.
- [ ] Add failing UI tests for real room/user details, absent fields hidden, clicked-player identity stable across refresh, account logout/switch success and failure, and unavailable invite state. Logout waits for existing `API.platformLogout('golaxy', token)`; failure preserves account with retry.
- [ ] Run focused pytest and `npm test -- --run src/kiosk/pages/GolaxyHomePage.test.tsx`; expect failures. Implement verified owner-bound profile read if available, typed API call, and real-data wiring. Preserve quick-match, room, AI navigation, and existing stored-account privacy.
- [ ] Re-run focused pytest/UI test and `npm run build`; expect pass. Verify a 1024 × 600 real lobby/profile state, remove lobby Fixture, commit `connect Golaxy lobby and account flow`.

## Chunk 3: Invitation with external acceptance gate

### Task 5: Enable invitations only after the complete playable lifecycle

**Files:** Modify `katrain/web/platforms/golaxy/adapter.py`, `katrain/web/api/v1/endpoints/platforms.py`, `katrain/web/ui/src/api.ts`, `katrain/web/ui/src/kiosk/pages/GolaxyHomePage.tsx`, `katrain/web/ui/src/kiosk/pages/GolaxyHomePage.test.tsx`, `tests/web_ui/test_golaxy_lobby.py`, `katrain/web/platforms/golaxy/PROTOCOL.md`; inspect `katrain/web/platforms/manager.py` and Golaxy game gateway before handoff.

- [ ] With two user-controlled accounts capture submit → pending → accept → game-start and actual first move, plus reject/cancel/timeout and reconnect. Record sanitized response/event fields. Existing `PlatformManager._on_game_started()` handles OGS only and Golaxy move submission is unverified; accepted invite alone is insufficient.
- [ ] Add failing tests for owner-only submit/cancel/status, target, `inviteAble=false`, duplicates, upstream failure, timeout, stale account response, verified session handoff, and no upstream write on failed preconditions. Test UI screen/physical pregame, pending/cancel/error, and rejection without calling pending accepted.
- [ ] Run focused pytest and UI test; expect failures. Implement narrow server-owned submit/cancel/status and game handoff only from captured contract. Keep API (`409`/`501` explicit unavailable reason) and UI inactive until **all** invite, cancel, result, handoff, and move gates pass. Kifu/follow remain unavailable unless separately verified.
- [ ] Re-run tests and controlled two-account flow; expect accepted invite plus playable first move, and cancellation/rejection recovery. If accounts/protocol are unavailable, commit only verified read/profile and disabled state, mark this slice blocked, and report the exact gate. Commit enabled flow only after live acceptance.

### Task 5b: Complete quick match and room start flows

**Files:** Modify `katrain/web/platforms/golaxy/adapter.py`, `katrain/web/api/v1/endpoints/platforms.py`, `katrain/web/ui/src/api.ts`, `katrain/web/ui/src/kiosk/pages/GolaxyPregameSetupPage.tsx`, `katrain/web/ui/src/kiosk/pages/GolaxyPregameSetupPage.test.tsx`, `tests/web_ui/test_golaxy_lobby.py`, `katrain/web/platforms/golaxy/PROTOCOL.md`; reuse the verified PvP handoff from Task 5.

- [ ] With the two test accounts, capture one quick-match request, pending status, cancellation, match event and playable first move; capture create-room, room-code join, both-player config/start, leave, and playable first move. Verify official request fields, accepted responses and reconnect behavior. The official `tasteOptionAi` switch also triggers a separate timeout-to-AI fallback: keep that option unavailable until its playable fallback is verified. Never treat a room reservation, code lookup or join HTTP 200 as a started game; a code-only join may have audience role.
- [ ] Add failing focused tests for owner-only start/cancel/create/join, invalid room number, duplicate/stale requests, rejection and timeout, correct room/game identity, and session handoff. Test screen/physical preference reaches the started game, and failed actions leave the setup page retryable.
- [ ] Run focused backend and `GolaxyPregameSetupPage.test.tsx` tests; expect new assertions to fail. Implement only verified Golaxy wire actions and their typed API calls; enable each submit button only after its own full path through a real first move is verified. Keep the other path explicitly disabled if evidence is incomplete.
- [ ] Re-run focused tests and a controlled two-account quick-match and room game. Record which paths truly started a playable game. If any contract gate fails, leave that action disabled and report the unmet behavior instead of presenting a dead clickable flow. Commit `enable verified Golaxy quick match and rooms` only for verified paths.

## Chunk 4: Spectator vertical slice

### Task 6: Project verified history, clocks, members, and game identity

**Files:** Modify `katrain/web/platforms/golaxy/adapter.py`, `katrain/web/ui/src/api.ts`, `tests/web_ui/test_golaxy_spectator_contract.py`, `katrain/web/platforms/golaxy/PROTOCOL.md`.

- [ ] Add failing tests for ordered capture/pass replay, newest move, stable game ID that resets on room reuse, verified clocks and roster. Unknown clock units, no active-side anchor, malformed roster and missing fields yield `null`.
- [ ] Run `/Users/fan/Repositories/katrain-kiosk-go-cross-platform/.venv/bin/python -m pytest tests/web_ui/test_golaxy_spectator_contract.py -q`; expect failures.
- [ ] Extend the safe 19×19 snapshot with minimal position history or move list for 上一手/回到最新, last marker, game identity, and only verified clock/member fields. Derive positions from validated replay, never a client board. Document authority/units; rerun test, expect pass.
- [ ] If clocks or member identities remain unavailable, show honest unavailable state **and mark those requirements blocked**, not accepted. Commit `expose verified Golaxy spectator details`.

### Task 6b: Server-owned room event relay and recovery

**Files:** Modify `katrain/web/platforms/golaxy/adapter.py`, `katrain/web/api/v1/endpoints/platforms.py`, `tests/web_ui/test_golaxy_spectator_contract.py`; create one focused Golaxy subscription module only if adapter growth would obscure its current responsibilities.

- [ ] In a controlled authenticated room, capture the Golaxy STOMP handshake, room/game destination, sanitized move/state event bodies, heartbeat and disconnect behavior. Confirm which event identifies game/room and advances move number. Do not expose bearer tokens to browser code or logs.
- [ ] Add failing tests for owner-only browser event stream, validated event projection, duplicate/out-of-order suppression, lost connection, room/account change cleanup, and a snapshot recovery after reconnection. Test that another local user cannot subscribe to the connected account's room stream.
- [ ] Run focused spectator pytest; expect failures. Implement a server-owned authenticated subscription and local owner-bound SSE or WebSocket relay, emitting minimal room/game/move revision data rather than raw third-party payloads. Refresh the authoritative snapshot after reconnect; detach subscription when no owner clients remain. Avoid sharing a stale subscription across account switches.
- [ ] Re-run focused tests and verify a real newly played move produces a relay event and fresh snapshot. If handshake or event payload cannot be verified, leave relay unavailable and mark **real-time synchronization blocked**; do not describe faster polling as equivalent. Commit verified relay work only.

### Task 7: Integrate responsive spectator view and controls

**Files:** Modify `katrain/web/ui/src/kiosk/pages/GolaxySpectatorPage.tsx`, `katrain/web/ui/src/kiosk-shell/golaxy-spectator.css`, `katrain/web/ui/src/kiosk/pages/GolaxySpectatorPage.test.tsx`.

- [ ] Add failing UI tests for last marker, game change reset, earlier-position view, return to latest, incoming moves while viewing history, no replay/initial/duplicate sound, one `playSound('stone')` per new move, and local toggle respecting global preference. Test validated event-triggered snapshot reads, duplicate suppression, reconnect recovery, hidden/account/room teardown, and clock resync; test bounded visible-only polling only in degraded mode.
- [ ] Run `npm test -- --run src/kiosk/pages/GolaxySpectatorPage.test.tsx`; expect failures.
- [ ] Consume Task 6b's owner-bound browser relay and request an authoritative snapshot after a validated event or reconnect, without browser Golaxy credentials. Use bounded 1–2 second visible-page polling only when the relay is unavailable and label it “快照同步”, never “实时同步”. Use `GoBoardSvg.last` and `useSound`. Earlier-position view freezes displayed position while latest state advances; return restores it. Derive seconds only from verified clock anchor and clamp zero.
- [ ] Re-run UI test and `npm run build`; expect pass. Compare one 1024 × 600 actual runtime spectator capture with approved design, board including coordinates filling left panel. Check real newest move and sound, remove spectator Fixture, commit `improve Golaxy spectating`.

## Chunk 5: Integrated acceptance and code review

### Task 8: Focused regression and defect review

**Files:** Modify only files revealed by defects. Retain approved HTML, remove preview Fixture from production.

- [ ] Run `/Users/fan/Repositories/katrain-kiosk-go-cross-platform/.venv/bin/python -m pytest tests/web_ui/test_golaxy_lobby.py tests/web_ui/test_golaxy_spectator_contract.py -q`, targeted Golaxy frontend tests, and `npm run build`; expect pass.
- [ ] At 1024 × 600 verify account switch, real lobby/profile, invite state, latest spectator move, history controls, sound, clocks, roster and retry/error. Mark real-time synchronization blocked if Task 6b's event transport is unverified; polling alone does not satisfy it. Identify all external gates still blocked; passing local tests alone does not mark them complete.
- [ ] Request defect-first full review using `superpowers:requesting-code-review` and local review-agent rubric; fix all blocking correctness/security findings, rerun focused checks, repeat until no blocking findings. Commit final fixes.
- [ ] Report tests, runtime visual evidence, commits and incomplete gates accurately. Do not merge, push, update smartbox submodule or deploy unless subsequently requested.
