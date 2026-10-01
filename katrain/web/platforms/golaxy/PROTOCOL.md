# Golaxy / 星阵围棋 (19x19.com) Protocol Reference

> Researched from JS bundle analysis, sabaki-golaxy-live, and web traffic capture.

## Architecture

REST API + STOMP over SockJS for real-time events.

| Endpoint | Protocol | Notes |
|----------|----------|-------|
| `https://www.19x19.com/api/auth/*` | REST | User/auth service |
| `https://www.19x19.com/api/social/*` | REST | Social/game service |
| `https://www.19x19.com/api/engine/*` | REST | Engine/AI service |
| `wss://ws.19x19.com/api/social/channel/WS_STOMP_ENDPOINT_GOLAXY` | STOMP/SockJS | Real-time events |

## Authentication — VERIFIED 2026-04-08

**API Base:** `https://api.19x19.com` (NOT www.19x19.com!)

**Phone-number login** — the web login offers multiple country codes; the verified request format includes the selected dial code. A successful login with a non-`+86` number has not been verified here. No email login is implemented.

**OAuth2 token endpoint:** `POST https://api.19x19.com/api/auth/oauth/token`

**Client credentials:**
```
Authorization: Basic Z29sYXh5X3dlYjp4aW5nemhlbjA3MzA=
(golaxy_web:xingzhen0730)
```

**SMS code request:** `GET /api/auth/sms/code?username=PHONE&login=true&area=00{DIAL}`
- The selected calling code uses a `00` prefix (`+86` → `0086`, `+886` → `00886`).

**SMS login (verified body):**
```
username=00{DIAL}-{PHONE}&password=null&grant_type=sms_code&client_id=golaxy_web&sms_code={CODE}&scope=any
```
- Key differences: username includes the selected calling code, field is `sms_code` not `code`, includes `password=null`, `client_id`, `scope=any`

**Password login:**
```
username=00{DIAL}-{PHONE}&password={PWD}&grant_type=password&client_id=golaxy_web&scope=any
```

**Token refresh:**
```
grant_type=refresh_token&client_id=golaxy_web&refresh_token={TOKEN}
```

**Response:** `{access_token, refresh_token, token_type: "bearer", expires_in}`

**Authenticated requests use:** `authorization: bearer {access_token}` (lowercase "bearer")

**User identification:** `user_code` — used in social/game API paths

## REST API Services

### Game Service (`/api/social`)

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/gameroom/reserve` | Create game room |
| POST | `/gameroom/login/{id}` | Join room |
| POST | `/gameroom/logout/{id}` | Leave room |
| POST | `/gameroom/game/config/{id}` | Send/accept/reject game config |
| POST | `/wsgame/start/{gameId}` | Start game |
| POST | `/wsgame/genmove/{gameId}` | Place a move |
| POST | `/wsgame/backmove/{gameId}` | Request undo |
| POST | `/wsgame/action/accept/{id}` | Accept action |
| POST | `/wsgame/action/reject/{id}` | Reject action |
| POST | `/wsgame/game/end/{id}` | End game |
| POST | `/wsgame/judge/data/{id}` | Request scoring |
| GET | `/wsgame/game/meta/{id}` | Game metadata |
| GET | `/wsgame/game/state/{id}` | Game state |

### Live/Spectating (`/api/engine`) — No auth required

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/engine/golives/all` | All current live games |
| GET | `/engine/golives/history` | Historical games |
| GET | `/engine/golives/base/{liveId}?begin_move_num=0&end_move_num=N` | Live game moves |
| GET | `/engine/golives/{gameId}` | Game SGF |

## Real-Time: STOMP over SockJS

**WebSocket URL:** `wss://ws.19x19.com/api/social/channel/WS_STOMP_ENDPOINT_GOLAXY`

### Subscription channels

| Channel | Purpose |
|---------|---------|
| `/channel/gamezone/{usercode}` | Game zone events (invites, matches) |
| `/channel/wsuser/{usercode}` | User events (status, multi-device) |
| `/channel/wsgame/{gameId}` | Live game moves and state |
| `/channel/gameroom/{gameroomId}` | Room events (config, players) |
| `/channel/chatroom/{chatroomId}` | Chat messages |

### Send destinations

| Destination | Purpose |
|-------------|---------|
| `/channel/wsuser/heartbeat` | Keepalive |
| `/channel/chatroom/message/send/{id}` | Send chat |
| `/channel/chatroom/login/` | Join chat |
| `/channel/chatroom/logout/` | Leave chat |

## Implementation Strategy

1. **Start with live spectating** (no auth, proven by sabaki-golaxy-live)
2. **Add authenticated play** via REST + STOMP subscriptions
3. **Capture STOMP message payloads** from browser DevTools to document schemas

## PvP readiness — repository audit 2026-09-30

**NO-GO for box-side human games.** The REST paths and STOMP destinations above are transport clues, not a verified playable contract. This audit only inspected repository code and documentation; it did not capture a live PvP session.

| Behavior | Repository evidence | Missing evidence |
|----------|---------------------|------------------|
| Quick match and challenge | Adapter has no matching/challenge implementation | Requests, responses, cancellation, timeout, and game-zone events |
| Rooms | `get_rooms()` returns an empty list; HTTP room wrappers exist | Room listing, creation/join payloads, config handshake, and events |
| Moves | `submit_move()` labels its `{x, y}` payload as unverified | Accepted request shape, pass, turn and rejection events |
| End of game | HTTP end/state wrappers exist | Authoritative resign, scoring, timeout and final-result events |
| Realtime transport | STOMP destination names are documented | Authenticated connection, event bodies and replay/recovery rules |

The AI stateless `genmove` tunnel is a separate, working path and does not establish PvP readiness. The kiosk must keep its human-game entries disabled until authorized test-account captures provide anonymized samples for each required flow and those flows pass integration tests.

## First-party lobby evidence — reviewed 2026-10-01

Local evidence sources: `golaxy-app-20260922.js`, `golaxy-gamezone.js`, `golaxy-rooms-response.json`, and `golaxy-users-response.json` in `/private/tmp`. The JS files are official client assets; their request builders and rendering logic are **static clues**, not proof that a request succeeds. Saved responses establish only the observations listed below. This section supersedes the room-list evidence gap in the earlier audit; **PvP remains NO-GO**.

| Area | Evidence level / source | Confirmed observation | Remaining gap |
|------|-------------------------|-----------------------|---------------|
| Room listing | Captured response + app JS | `GET /api/social/gameroom/list?page=0&size=15`; envelope has `code: "0"` and a `data` list. JS defaults to page `0`, size `15`. | Pagination behavior, freshness and failure handling have not been exercised. |
| Room projection | Captured room response | Room fields include `id`, `gameroomCode`, `gameroomStatus`, `wsGameId`, `gameMetaDto` and `gameroomStateDto.onlineUserCount`. Metadata includes `gameType`, `handicap`, `komi`, `blackNickname`, `whiteNickname`, `blackLevel`, `whiteLevel` and `gameState.situation`, `moveNum`, `gameStatus`. | Status values and field authority across lifecycle transitions remain unverified. |
| Board snapshot | Captured room response, two snapshots | `situation` is a comma-separated sequence of integers; the two inspected sequences contain 76 and 25 entries respectively, equal to their `gameState.moveNum`. | This earlier snapshot alone did not establish a usable board decoder; see the later read-only room-detail evidence below. |
| Lobby refresh | Static app + game-zone JS | `gamezone_refresh_time` is `30`; the client refresh loop waits `1000 * gamezone_refresh_time` milliseconds between refreshes. | No measured server update cadence or realtime replacement contract. |
| Online user listing | Static app JS + failed saved response + authenticated read-only capture (2026-10-01) | Client uses `GET /api/social/gamezone/user/list` with defaults `page=0`, `size=15`, `level=-1`. Older saved response has `code: "6003"` (invalid token). A fresh authenticated request returned HTTP 200, `code: "0"`, and a `data` list of 16 rows. | The service returned 16 rows despite `size=15`; pagination behavior and freshness remain unverified. |
| Online user projection | Static game-zone JS + authenticated read-only capture | Successful rows contain `userCode`, `nickname`, `photo`/`photoFile`, `level`, `winNum`, `loseNum`, `inviteAble`, app/web user and connection status fields, and app/web status details. Client also references `followAlias`. | Numeric rank and presence codes have no verified display meaning; preserve unknowns rather than inventing labels. |
| Quick match | Static app JS only | JSON `POST /api/social/gamezone/game/taste/match/{userCode}` passes caller options plus `userCode`, `gamename`, and defaults for `tasteBoardSize`, `tasteRule`, `tasteStone`, `tasteKomi`, `tasteHandicap`. Builder requires a successful `stompStatusCheck()`. Heartbeat and cancel use `POST /api/social/gamezone/game/taste/heartbeat/{userCode}` and `/api/social/gamezone/game/taste/cancel/{userCode}`, each with `{}` data. | No accepted request, match event, cancellation result, timeout or recovery capture. |
| Create room | Static app JS only | `POST /api/social/gameroom/reserve` data keys: `user_code`, `inviter_user_code`, `inviter_client_id`, `invitee_user_code`, `invitee_client_id`; optional invite fields default to empty strings. | Success/failure responses, permissions and room configuration handshake are unverified. |
| Join room | Static app JS only | `POST /api/social/gameroom/login/{gameroomId}` data: `user_role` and optional `password` (omitted when undefined). | Accepted role values, private-room behavior, spectator role and join events are unverified. |

No live human match, authenticated STOMP connection/event payload, spectator join, move submission, scoring, resign or reconnect sequence was captured by these files. Public room discovery does not prove spectator access to a room or live PvP readiness. Samples here retain field names and aggregate observations only; account identifiers, player names, phone numbers, tokens and raw responses are excluded.

### Read-only lobby implementation

`GET /api/v1/platforms/golaxy/rooms` and `/users` require the connected platform owner. They fetch page 0 from the authenticated Golaxy list endpoints above and return the existing kiosk projections. Rooms expose the observed room ID/code, handicap, player code/nickname, and `gameState.moveNum` as a hand count. User rows expose code and display name: `followAlias` when present, otherwise `nickname`, matching the first-party game-zone client. A `/users?q=...` request filters that first page locally by case-insensitive display-name prefix; it does not search later pages. Rank, presence, room type, and game phase labels remain null until their numeric meanings are verified. `gameroomStateDto.onlineUserCount` includes all room users, so it is **not** reported as a spectator count. The lobby list still does not decode `gameState.situation` into a board; the separate room-detail snapshot endpoint below does.

The list envelope must have `code: "0"` and a `data` list. During normal room/user reads, an invalid token (`code: "6003"` or HTTP 401/403) returns local HTTP 401 to the UI without refreshing; other Golaxy failures, malformed responses, and timeouts return local HTTP 502, never a misleading empty list. Only connect/reconnect may refresh an expired stored token once, serially through the platform manager. Reconnect verifies a stored token against the authenticated user-list endpoint; the public live feed cannot verify it. A successful reconnect refresh emits `token_refreshed` for manager persistence.

### Read-only room snapshot — verified 2026-10-01

The first-party room controller reads authenticated `GET /api/social/gameroom/info/{room.id}` and polls it. A 31-second anonymized RK3562 trace of four ordinary rooms showed each later `situation` retaining the earlier sequence as a prefix while `moveNum` advanced (27→29, 37→39, 43→49, 43→44). The first-party JS treats `situation` as ordered moves from Black, with `-1` consuming a pass turn. This establishes a full read-only history source for the observed ordinary rooms; `/wsgame/game/meta|state/{id}` returned 404 for tested room and game IDs.

One observed in-progress room-detail response had `gameMetaDto.boardSize=19`, `handicap=0`, `startMoveNum=0`, `moveNum=9`, `gameType="82"`, `rule="chinese"`; nested `gameMetaDto.gameState` had `moveNum=9`, a nine-integer `situation`, and `gameStatus=10`. The enclosing `gameroomStatus` was 30. **`boardSize` and `startMoveNum` belong to `gameMetaDto`, not `gameState`.** Golaxy points are top-first row-major integers, decoded with `golaxy_to_katrain`; that decoder's row counts from the bottom, so GTP labels use column plus `row+1` (for example Q16 and Q4), without passing the row through the web `katrain_to_gtp` helper. The snapshot endpoint replays the sequence with `sgfmill.boards.Board` so captures affect the returned stones.

`GET /api/v1/platforms/golaxy/rooms/{room_id}/snapshot` is owner-only and accepts a numeric room ID. It returns a sanitized board projection only when the meta fields match the observed ordinary Chinese game: 19 lines, zero handicap, `startMoveNum=0`, `gameType="82"`, and `rule="chinese"`. Unsupported setups return 422; malformed or illegal histories and other upstream failures return 502; invalid credentials return 401. A room status of 30 is shown as in progress; first-party JS maps 40 to finished, but no terminal wire response has been captured, so `result` remains null. Real terminal, nonzero handicap, capture, and pass wire samples are still absent. Capture and pass replay are covered by local contract tests, not claimed as live observations. No spectator login, STOMP presence, or game write is issued for this snapshot.

## Key Risks

- **Phone-number auth** — non-`+86` login success remains unverified
- **No official API docs** — reverse-engineered from JS bundle
- **STOMP payload schemas unknown** — subscription channels known but message formats must be captured
- **Endpoints can change on any deploy** (latest JS bundle: 2026-04-03)
- **Legal gray area** — no public API terms
