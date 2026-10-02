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
Authorization: Basic {SERVER_HELD_CLIENT_CREDENTIALS}
```
The client ID is `golaxy_web`; credential values are deliberately omitted.

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
| `/channel/gamezone/game/invite/{usercode}` | Invitation destination declared by the official client; delivery unverified |
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
| Online user projection | Static game-zone JS + authenticated read-only capture | Successful rows contain `userCode`, `nickname`, `photo`/`photoFile`, `level`, `winNum`, `loseNum`, `inviteAble`, app/web user and connection status fields, and app/web status details. Client also references `followAlias`. | Wire rank/presence types and freshness remain unverified; the 2026-10-02 review below establishes selected static display meanings. |
| Quick match | Static app JS only | JSON `POST /api/social/gamezone/game/taste/match/{userCode}` passes caller options plus `userCode`, `gamename`, and defaults for `tasteBoardSize`, `tasteRule`, `tasteStone`, `tasteKomi`, `tasteHandicap`. Builder requires a successful `stompStatusCheck()`. Heartbeat and cancel use `POST /api/social/gamezone/game/taste/heartbeat/{userCode}` and `/api/social/gamezone/game/taste/cancel/{userCode}`, each with `{}` data. | No accepted request, match event, cancellation result, timeout or recovery capture. |
| Create room | Static app JS only | `POST /api/social/gameroom/reserve` data keys: `user_code`, `inviter_user_code`, `inviter_client_id`, `invitee_user_code`, `invitee_client_id`; optional invite fields default to empty strings. | Success/failure responses, permissions and room configuration handshake are unverified. |
| Join room | Static app JS only | `POST /api/social/gameroom/login/{gameroomId}` data: `user_role` and optional `password` (omitted when undefined). | Accepted role values, private-room behavior, spectator role and join events are unverified. |

No live human match, authenticated STOMP connection/event payload, spectator join, move submission, scoring, resign or reconnect sequence was captured by these files. Public room discovery does not prove spectator access to a room or live PvP readiness. Samples here retain field names and aggregate observations only; account identifiers, player names, phone numbers, tokens and raw responses are excluded.

### Read-only lobby implementation

`GET /api/v1/platforms/golaxy/rooms` and `/users` require the connected platform owner. They fetch page 0 from the authenticated Golaxy list endpoints above and return compatible kiosk projections. Rooms expose the observed room ID/code, handicap, player code/nickname, and `gameState.moveNum` as both the legacy hand-count `phase` and optional `move_number`. `room_type` now displays the verified `gameMetaDto.gameType` category (`80` → `自由战`, `82` → `升降战`), never a label inferred from `gameroomType`. `gameroomStateDto.onlineUserCount` projects to `room_user_count`, which includes all room users; `spectator_count` remains null. The lobby list still does not decode `gameState.situation` into a board; the separate room-detail snapshot endpoint below does.

The 2026-10-02 display mappings are integrated into the read-only adapter. Player and user ranks use only exact verified Elo entries `2500` → `7段` and `2600` → `准8段`, accepting integers or exact numeric strings; other values remain null. User rows expose code and display name (`followAlias` when present, otherwise `nickname`), nonnegative integer `wins`/`losses`, and a strictly boolean `invite_able`. The latter preserves the upstream preference and does not authorize or guarantee an invitation. Presence requires an explicit aggregate `connectionStatus` of `0`/`1` (integer or exact string): closed is `离线`; connected and explicitly false `inviteAble` is `拒绝`; otherwise the first nonempty connected web/app detail takes precedence when recognized, followed by recognized aggregate `userStatus`. Missing or unknown connection/status codes stay null rather than inheriting the official client's create-state fallback.

Avatar projection prefers `photoFile` over `photo` and accepts only absolute HTTPS URLs on the verified `assets.19x19.com` host, without URL credentials or a nonstandard port. Filename-only, external and malformed values remain null; the adapter does not guess an asset base from filenames. Optional numeric display fields reject booleans, negative values, fractional values and numeric strings rather than coercing them. A `/users?q=...` request still filters only that first page locally by case-insensitive display-name prefix. These projections do not add profile reads, invitation writes, or realtime presence.

The list envelope must have `code: "0"` and a `data` list. During normal room/user reads, an invalid token (`code: "6003"` or HTTP 401/403) returns local HTTP 401 to the UI without refreshing; other Golaxy failures, malformed responses, and timeouts return local HTTP 502, never a misleading empty list. Only connect/reconnect may refresh an expired stored token once, serially through the platform manager. Reconnect verifies a stored token against the authenticated user-list endpoint; the public live feed cannot verify it. A successful reconnect refresh emits `token_refreshed` for manager persistence.

### Read-only room snapshot — verified 2026-10-01

The first-party room controller reads authenticated `GET /api/social/gameroom/info/{room.id}` and polls it. A 31-second anonymized RK3562 trace of four ordinary rooms showed each later `situation` retaining the earlier sequence as a prefix while `moveNum` advanced (27→29, 37→39, 43→49, 43→44). The first-party JS treats `situation` as ordered moves from Black, with `-1` consuming a pass turn. This establishes a full read-only history source for the observed ordinary rooms; `/wsgame/game/meta|state/{id}` returned 404 for tested room and game IDs.

One observed in-progress room-detail response had `gameMetaDto.boardSize=19`, `handicap=0`, `startMoveNum=0`, `moveNum=9`, `gameType="82"`, `rule="chinese"`; nested `gameMetaDto.gameState` had `moveNum=9`, a nine-integer `situation`, and `gameStatus=10`. The enclosing `gameroomStatus` was 30. **`boardSize` and `startMoveNum` belong to `gameMetaDto`, not `gameState`.** Golaxy points are top-first row-major integers, decoded with `golaxy_to_katrain`; that decoder's row counts from the bottom, so GTP labels use column plus `row+1` (for example Q16 and Q4), without passing the row through the web `katrain_to_gtp` helper. The snapshot endpoint replays the sequence with `sgfmill.boards.Board` so captures affect the returned stones.

`GET /api/v1/platforms/golaxy/rooms/{room_id}/snapshot` is owner-only and accepts a numeric room ID. It returns a sanitized board projection only when the meta fields match the observed ordinary Chinese game: 19 lines, zero handicap, `startMoveNum=0`, `gameType="82"`, and `rule="chinese"`. Unsupported setups return 422; malformed or illegal histories and other upstream failures return 502; invalid credentials return 401. A room status of 30 is shown as in progress; first-party JS maps 40 to finished, but no terminal wire response has been captured, so `result` remains null. Real terminal, nonzero handicap, capture, and pass wire samples are still absent. Capture and pass replay are covered by local contract tests, not claimed as live observations. No spectator login, STOMP presence, or game write is issued for this snapshot.

## Social contract review — 2026-10-02

This review inspected `/private/tmp/golaxy-app-20260922.js`, `golaxy-gamezone.js`, `golaxy-rooms-response.json`, and `golaxy-users-response.json`, plus the adapter and its lobby/snapshot tests. **Captured** means a retained response was inspected; **static** means official request or rendering code was inspected; **prior observation** means the 2026-10-01 audit recorded it but its raw response is unavailable. Static requests establish a client contract, not successful server behavior. Tests use synthetic rows and do not establish additional wire types or outcomes. Only schemas, safe enum values and aggregate observations are recorded here.

### Lobby fields and display semantics

Room paths below are relative to a room row; user paths are relative to an online-user row.

| Meaning | Observed keys and types | Evidence and interpretation |
|---------|-------------------------|-----------------------------|
| Game category displayed in room list | `gameMetaDto.gameType: string`; both retained rooms have `"82"` | Captured + static `gameTypeStatus` and game-zone game-type renderer: `80` / `"80"` → `自由` (`自由战` in full mode), `82` / `"82"` → `升降` (`升降战`). The renderer separately overrides the name for official AI accounts; that account classifier is not a general game-type decoder. |
| Room source/type | `gameroomType: integer`; retained values `10`, `20` | Captured. Client declares `INVITE_GAMEROOM=10`, `TASTE_GAMEROOM=20`, but neither inspected bundle renders `gameroomType`. These enum names alone do not verify a user-facing room-source label. Keep unknown source types unknown; do not conflate this field with `gameMetaDto.gameType`. |
| Black and White ranks | `gameMetaDto.blackLevel`, `whiteLevel: integer`; retained values `2500`, `2600` | Captured + static: both room players render through `levelCom`. Its exact lookup is described below. |
| All users in room | `gameroomStateDto.onlineUserCount: integer` | Captured. This is the total of all room users, **never a spectator count**. A spectator count cannot be derived by subtracting two without a verified membership contract. |
| User identity and display name | `userCode`, `nickname`; optional `followAlias` | Prior observation confirms identity/name fields; raw types cannot be rechecked. Static user rendering prefers nonempty `followAlias`, then `nickname`. Identifiers must remain opaque. |
| User rank | `level` | Prior observation of successful rows; wire type unavailable. Static `levelCom` accepts numeric/string values and uses the same exact lookup as room ranks. Unknown numeric values have no rank meaning. |
| Wins and losses | `winNum`, `loseNum` | Prior observation; raw types unavailable. Static user-table headings are `胜` and `负`, and the profile uses the same fields. Numeric nonnegative counts are the intended projection; do not coerce malformed values into zero or infer missing counts. |
| Invitation eligibility | `inviteAble`, `inviterFollowRestrict`, `inviterLevelRestrict`, `followType` | `inviteAble` was previously observed; remaining keys are static consumer inputs, with wire types unverified. The first-party availability check combines connection/activity status with invite, mutual-follow and same-level restrictions. `inviteAble` alone does not prove the action can succeed. |
| Avatar | `photoFile`, `photo`; room metadata `blackPhotoFile`, `whitePhotoFile: string` | Room fields captured; user fields previously observed, with wire types unavailable. Static rendering prefers `photoFile || photo`; an existing HTTPS path is used directly, otherwise it prefixes the configured assets URL plus `/user_photo/`. This is a rendering clue, not authority to relay arbitrary URLs. |
| Presence | `appUserStatus`, `webUserStatus`, `appConnectionStatus`, `webConnectionStatus`, `appUserStatusDetail`, `webUserStatusDetail`; renderer also consumes aggregate `userStatus`, `connectionStatus` | App/web keys previously observed; aggregate keys are static inputs, raw types unavailable. Known labels and precedence below are supported by rendering code. Missing or unknown codes must not become `空闲` or `离线` by default. |

`levelCom.levelInfo` compares the input with the `eloScore` of `GLOBAL.getLevelListNew()`. That helper converts the official `computerLevel` entries to the human display list; `levelName` uses `extra.level_name || humanLevel`, where `humanLevel` is `saveName || label`. This is an **exact table**, not an arithmetic formula or a 1–29 rank index. The retained `2500` and `2600` render as `7段` and `准8段`. Test fixtures using `25`/`29` are synthetic and must not define a decoder. The inspected table supplies these labels:

| Captured Elo value | Display label |
|--------------------|---------------|
| `2500` | `7段` |
| `2600` | `准8段` |

For other values, consult the exact `computerLevel` entries through `getLevelListNew` and `levelCom`, rather than extrapolating. The zero entry has a blank label; `noneLevelShow` can render `无等级`, which does not establish a rank for every unknown value. Unknown values should stay null in the kiosk projection.

Presence rendering in `golaxy-gamezone.js` uses `statusDetail`, `statusCul`, and `statusData`: choose a nonempty detail from a connected web client first, then a connected app client; aggregate disconnected state selects `50`; connected state with false `inviteAble` selects the refusal label; otherwise a recognized detail overrides aggregate `userStatus`. The official client has its own fallback to the create state for unknowns, which does not verify their meaning. Its parameter table and enum values establish:

| Value / detail | Label |
|----------------|-------|
| `-1`, `0`, `10`, `20`, `30`, `40`, `50`, `90` | 拒绝, 创建, 登录, 空闲, 忙碌, 对弈, 离线, 退出 |
| `WSGAME_WATCH` | 观战 |
| `AI_LIFE_DEATH`, `AI_ANALYSIS`, `AI_GAME` | AI解题中, 研究中, 对弈 |

The client declares connection codes `0`/`1` as closed/open. No successful captured user response remains to verify whether those values arrive as numbers, strings, or another representation. First-party invitation availability rejects no connected device and any connected device whose status is busy/playing; it then applies the invite/follow/level policy. Official AI targets have a separate professional-account restriction in the user-row component. These checks describe first-party UI behavior, not server authorization.

### Profile request and invitation lifecycle

All paths here use the social base `/api/social`. In the profile dialog, `userInfoRequest({userCode: peer})` moves the selected row's code to `peer_user_code` and deletes `userCode` before calling `userInfoLoad`. Both `getUserInfor(peer)` and `userInfoLoad` therefore put the **authenticated caller** in `/follow/user/info/user_code/{caller}` and the **selected peer** in request data `{peer_user_code: peer}`; the latter defaults its path code to the stored caller. They do not substitute the peer into the path. The exact HTTP verb/query serialization for these profile calls has not been verified here. No successful profile response is preserved. The component consumes nickname, rank, avatar and wins/losses, but additional profile fields are unverified and must not be forwarded wholesale.

The invitation builders below explicitly use POST. Payloads are sanitized schemas; each user/client code is an opaque string, not a captured account value. `golaxy_web` is the official web client ID. The caller must be selected by the server's connected owner, never accepted as a browser-supplied principal.

| Action / first-party method | Path | Request schema and caller/peer placement | Outcome evidence |
|-----------------------------|------|------------------------------------------|------------------|
| Submit / `inviteUserForGame` | `/gamezone/game/invite` | `{inviter_user_code: caller, invitee_user_code: peer, inviter_client_id: "golaxy_web", invitee_client_id: string-or-empty}`. The builder forces the inviter client ID to the web ID, defaults the inviter code from the logged-in store, and first checks STOMP readiness and other-device busy state. | Static only. No accepted/rejected request or resulting invitation event captured. |
| Cancel / `inviteCancelToGame` | `/gamezone/game/invite/cancel` | Same four keys; preserves inviter/invitee roles from the invitation. Inviter client defaults to web ID; invitee client defaults empty. | Static only. No cancellation response, race, acknowledgement or peer event captured. |
| Accept / `acceptInvitation` | `/gamezone/game/invite/accept` | Same four keys; caller is the invitee. Invitee client defaults to web ID; inviter client defaults empty. | Static only. HTTP success does not establish a room/game handoff. |
| Reject / `refuseInvitation` | `/gamezone/game/invite/reject` | Same four keys plus `reject_duration: number` (client default `0`). Invitee client defaults to web ID; inviter client defaults empty. | Static only; duration unit and server behavior unverified. |
| Acknowledge / `ackInvitation` | `/gamezone/game/invite/ack` | Same four keys; inviter client defaults to web ID, invitee client empty. | Static only. The call site and lifecycle role are unverified; do not infer delivery acknowledgement semantics from its name. |

The builders read `gameroom_id` but do **not** include it in these invitation payloads. User-row and profile actions pass the selected peer into `inviteUsercode`; their inviter comes from the authenticated store. The profile supplies `ownUsercode`, while the builder reads `usercode` and consequently falls back to the stored caller. An object locally constructed after a user-list invite contains `code: 0` and `data.{inviteeUserCode,inviterUserCode,inviterUserInfo}`; this is client code, not a captured response schema.

`userStatusCheck` recognizes the string `MSG_GAMEZONE_GAME_INVITE_ACCEPT` and consumes `inviterUserInfo` / `inviteeUserInfo` app/web status and connection fields. It is a static helper input, not a verified STOMP envelope. The inspected files have no invitation timeout handler or captured invitation expiry, and quick-match `taste_max_wait=30` applies to another flow. **Invitation timeout, delivery, accept/reject/cancel terminal states, duplicate handling, and reconnect recovery are unverified.** A local wait deadline must be described as the kiosk stopping its wait, not proof that Golaxy cancelled the invitation.

Possible room/game handoff calls are separately declared: room reserve carries caller and inviter/invitee user/client fields; room login carries `user_role` and optional password; room config send/accept/reject use `/gameroom/game/config/{id}`, `/accept/{id}`, `/reject/{id}`; game start uses `/wsgame/start/{gameId}`. Config builders reference game type, board size, komi, both player codes/ranks, handicap, main/countdown time and count, stone, rule and `currentPlayer`. No captured response links an accepted invitation to a room, config or game ID. Do not navigate to a synthetic game or begin play based on POST success alone. No invitation or game write was issued during this review.

### Ordinary room detail and clock evidence

The prior 2026-10-01 room-detail observation and prefix trace still establish the narrow history contract documented above; their raw schemas are unavailable. The retained **room-list** response includes the clock fields below, but this does not prove those fields are present or authoritative in every `/gameroom/info/{id}` response. Use the following evidence boundaries when extending the detail contract:

| Area | Schema observed in retained room list | Detail status / limitation |
|------|----------------------------------------|----------------------------|
| Ordered history | `gameMetaDto.gameState.situation: string`, `moveNum: integer`; meta `boardSize`, `handicap`, `startMoveNum: integer` | **Verified by prior observation** for ordinary 19-line, no-handicap games: append-only history from Black. Only supported setups may be replayed; full lifecycle/recovery ordering is unverified. |
| Game ID | Row `wsGameId`, meta `wsGameId`, state `wsGameId: integer`; meta `gameroomId: integer` | **Captured in list**, not retained detail schema. In both rows the three game IDs agree, and the meta room ID matches the row ID. Keep room and game IDs distinct; positive nonzero ID/handoff semantics are not verified for every state. |
| Active side | State `currentPlayer: string`; meta/state `blackUserCode`, `whiteUserCode: string` | **Captured in list**: it equals the Black code in one row and White code in the other. This supports matching identity to side for those samples, not decoding a numeric side enum or assuming history parity remains authoritative during pauses. Detail availability is unverified. |
| Main clock | Meta/state `mainTime: integer`; state `blackRemainTime`, `whiteRemainTime: integer` | **Ambiguous** units/anchor. Values are compatible with milliseconds; static AI configs use `mainTime=2400000` and `countdownTime=30000`, but no ordinary-game clock renderer or elapsed-time trace was captured to verify conversion or subtraction rules. |
| Overtime | Meta/state `countdownTime`, `countdownNum: integer`; state `blackRemainCountdownTime`, `whiteRemainCountdownTime`, `blackRemainCountdownNum`, `whiteRemainCountdownNum`, `blackCountdownOverdueTime`, `whiteCountdownOverdueTime: integer` | **Captured fields, ambiguous semantics**. Samples have three periods and include a negative overdue value. Do not clamp or interpret negative overdue values, infer which period is running, or label a countdown without the missing timing contract. |
| Timing anchors | State `blackCountdownTimestamp`, `whiteCountdownTimestamp`, `blackConnectTimestamp`, `whiteConnectTimestamp`, `blackDisconnectTimestamp`, `whiteDisconnectTimestamp: integer` | **Ambiguous**. Magnitudes resemble epoch milliseconds, but countdown timestamps are identical for both sides in each retained row. No verified server-now, state observation timestamp, move timestamp, timezone or clock skew correction anchor was found. Connection timestamps cannot be assumed to anchor a game clock. |
| Running/paused state | Row `gameroomStatus: integer`; state `gameStatus: integer`, `gameActionType: integer`; state `blackConnectionStatus`, `whiteConnectionStatus: integer` | **Ambiguous** clock-running predicate. Room display evidence establishes `30` playing and `40` ended; the game enum declares `10` opening / `20` middle / `30` ending / `40` ended, without a verified clock predicate. These statuses do not establish whether a clock runs during pending actions, disconnects, scoring or pauses. No explicit running flag is present in the retained list. |
| Members and roles | Meta has both player codes/nicknames/photo filenames; row/room state has inviter/invitee codes; `gameroomStateDto` has `onlineUserCount: integer`, `currentInviters: string` | **Player identity captured; membership absent**. No retained member list or role field exists in the supplied list/detail evidence. Static `/gameroom/player/list/{gameroom_id}` and role renderer (`0` unknown, `10` player, `20` audience) are clues only; no successful list or spectator login observed. Inviter/invitee are not guaranteed Black/White roles. |

The official client also declares POST `/wsgame/state/sync/{wsGameId}` with a caller-provided JSON params object, but neither accepted payload nor clock-sync response was captured. It must not be used as a read-only clock source without verification. A snapshot may expose verified clock values after units are established; until a running predicate and timing anchor are established, display unknown or an explicitly static snapshot and do not decrement a fabricated live clock.

### STOMP handshake, subscriptions and relay boundary

The official client uses the SockJS **HTTPS base** `https://ws.19x19.com/api/social/channel/WS_STOMP_ENDPOINT_GOLAXY`, constructs SockJS with `withCredentials: true`, wraps it with STOMP, then calls `connect(headers, success, error)`. The base is not a captured raw WebSocket handshake URL; SockJS chooses its transport URLs. Static CONNECT headers are:

```text
Auth_token: {SERVER_HELD_ACCESS_TOKEN}
Channel: WS_STOMP_ENDPOINT_GOLAXY
Api_version: 2.0
Client_id: golaxy_web
```

Static subscriptions use `/channel/gamezone/{caller}`, `/channel/wsuser/{caller}`, the declared `/channel/gamezone/game/invite/{caller}`, `/channel/gameroom/{roomId}`, and `/channel/wsgame/{gameId}`. `subscribe` resolves the destination, replaces a prior subscription with the same logical key, and calls STOMP subscribe with `{id: destination}`. The callback receives the STOMP frame unchanged; no retained room/game frame establishes a JSON body envelope, event discriminator, sequence number, state payload or replay cursor. The earlier `/channel/wsgame/game/` string is also a declared URL prefix; it does not replace the actual `gameSub` template `/channel/wsgame/{gameId}`.

The client sends a game-zone heartbeat to `/channel/wsuser/heartbeat` every configured `15000` ms. Its static object contains `userCode`, `heartbeatInterval`, `deviceType` (`1` for web), `user_agent`, `Api_version`, `userStatus`, and `userStatusDetail`. No server heartbeat acknowledgement, STOMP negotiated heartbeat or room heartbeat wire schema was captured. `gamezoneLogin` / logout declare POST `/gamezone/login/{caller}` and `/gamezone/logout/{caller}`; their accepted responses and ordering relative to subscriptions are unverified.

Explicit disconnect clears client status, calls STOMP disconnect, stops the game-zone heartbeat and clears the client reference; the lower transport can also close SockJS. On unexpected close, the first-party client waits `5000` ms before reconnecting and reattaches remembered subscriptions; connection retries switch from `5000` to `15000` ms after the configured retry threshold of four. This is static client behavior. There is no captured reconnect, backfill, ordering or missed-event recovery guarantee, and resubscription alone does not prove continuity.

**Kiosk transport boundary:** the server owns Golaxy credentials, SockJS/STOMP connection, owner/room subscription lifecycle and any upstream heartbeat. The browser must never hold a Golaxy access/refresh token, CONNECT credential, or direct authenticated Golaxy subscription. It receives only owner-authorized, allowlisted and sanitized server events or snapshots. Disconnect/owner change must remove upstream subscriptions and invalidate browser delivery for the previous owner; raw frames and upstream errors must not relay credentials or personal fields.

Realtime room/board/clock/member claims require captured event schemas and verified snapshot reconciliation. Until then, **bounded polling while the relevant room is visible is a degraded fallback**: show freshness/reconnecting state honestly, stop on navigation, hidden page, disconnect or owner change, and cap/restrict retries. The existing room-history reads can support refreshed board snapshots; polling does not verify invitation completion, a running clock, member roles, or continuous realtime delivery. These evidence gaps keep human PvP unavailable.

## Key Risks

- **Phone-number auth** — non-`+86` login success remains unverified
- **No official API docs** — reverse-engineered from JS bundle
- **STOMP payload schemas unknown** — subscription channels known but message formats must be captured
- **Endpoints can change on any deploy** (latest inspected client bundle: 2026-09-22)
- **Legal gray area** — no public API terms
