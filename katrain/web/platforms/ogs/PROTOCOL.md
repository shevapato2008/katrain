# OGS Protocol Reference

> Verified from goban library source, gtp2ogs source, and live research (2025-2026).
> OGS has completed migration from socket.io to native WebSocket.

## Authentication

**For human-user clients (OAuth2 PKCE):**
1. Register app at `https://online-go.com/oauth2/applications/`
2. Authorization: `https://online-go.com/oauth2/authorize/` (PKCE flow)
3. Token exchange: `https://online-go.com/oauth2/token/`
4. Access tokens last 30 days, refresh tokens 30 days
5. Use access token to call `GET /api/v1/ui/config` -> returns `user_jwt`
6. Send JWT in WebSocket `authenticate` message

**Alternative — session login (simpler for board devices):**
1. `POST /api/v0/login` with `{"username": "...", "password": "..."}`
2. `GET /api/v1/ui/config` -> returns `user_jwt`

**For bots:**
- Send `bot_username` + `bot_apikey` with `jwt: ""` in `authenticate`

## Real-time Transport

**Protocol:** Native WebSocket (socket.io is gone)

**URL:** `wss://online-go.com`
- Alternative for Apple/UK: `wss://wsp.online-go.com`
- Alternative public: `wss://wss.online-go.com`

**Wire format (JSON arrays):**
- Client → Server: `[command, data?, request_id?]`
- Server → Client: `[event_name, data]` (event) or `[request_id, data?, error?]` (response)

## Authentication Message

```json
["authenticate", {
  "jwt": "...",
  "client": "KaTrain-SmartBoard",
  "client_version": "0.1"
}, 1]
```
Response: `[1, {"id": 12345, "username": "..."}]`

Note: Old fields `player_id`, `chat_auth`, `notification_auth` are deprecated.
The `authenticate` message implicitly subscribes to notifications/chat.

## Game Lifecycle

### Connect to game
```
-> ["game/connect", {"game_id": 12345, "chat": false}]
<- ["game/12345/gamedata", {...full GobanEngineConfig...}]
<- ["game/12345/clock", {...clock state...}]
```

### Submit move
```
-> ["game/move", {"game_id": 12345, "move": "dp"}]
```
**Coordinate encoding:** `num2char(x) + num2char(y)` where `a=0, b=1, ..., z=25`.
Does NOT skip 'i' (same as SGF). Pass = `".."` (x=-1, y=-1).
No explicit ACK — invalid moves trigger error events.

### Receive opponent move
```
<- ["game/12345/move", {"game_id": 12345, "move_number": 42, "move": [3, 3, 5000]}]
```
`move` is `AdHocPackedMove`: `[x, y, timedelta?, color?]`. 0-indexed from top-left.
Pass = `[-1, -1]`.

### Snapshot decoding audit (2026-09-30)

The official [Goban protocol types](https://docs.online-go.com/goban/modules/protocol.html), [GobanEngine config](https://github.com/online-go/goban/blob/main/src/engine/GobanEngine.ts), [AdHoc move format](https://github.com/online-go/goban/blob/main/src/engine/formats/AdHocFormat.ts), and [OGSConnectivity move handler](https://github.com/online-go/goban/blob/main/src/Goban/OGSConnectivity.ts) establish the following source-derived shape. **This is not a captured game from the box's account**; authenticated live sequence and final-result timing still need an integration check.

- `gamedata.initial_state.black` and `.white` are coordinate strings. Decode their two-character coordinates and place these stones before replaying moves.
- `gamedata.moves` is an array of packed move arrays such as `[[x, y, delta], ...]` (or JGOF move objects), never a flat `x,y,delta,x,y,delta` list.
- A `game/{id}/move` event includes `game_id`, `move_number`, and one packed move. The official client's continuity check compares its current count with `move_number - 1`, so the event number is the new move's one-based number. Check the game ID and sequence; on a gap, fetch an authoritative snapshot before applying more moves.
- The `game/{id}/phase = "finished"` event alone gives no result. `gamedata` can contain `winner`, `outcome`, `score`, and `end_time`; scoring acceptance may also carry these. Do not save a winner until an authoritative result is available.

An anonymous read of three public completed games via `GET /api/v1/games/{id}/` confirmed the **REST nesting**: outer `width`, `height`, `players`, `outcome`, `black_lost`, `white_lost`, `ended` accompany an inner `gamedata` object containing `game_id`, board settings, `players`, `phase`, `initial_state`, nested packed `moves`, `winner` (a player id), `outcome`, `score`, and `end_time`. Outer `winner`, `phase`, and `moves` were absent. One anonymized 13-road scored result had `phase="finished"`, 124 packed moves ending in two `[-1,-1,time_delta]` passes, `outcome="59.5 points"`, and `score.black.total=25`, `score.white.total=84.5`; the winning id matched inner `players.white.id`. Other public results showed `outcome="Timeout"` and `"Resignation"` with a winning id, without score totals. This verifies actual REST shapes, not this box's authenticated game event timing.

### Clock update
```
<- ["game/12345/clock", {
  "game_id": 12345,
  "current_player": 12345,
  "black_player_id": 12345,
  "white_player_id": 67890,
  "expiration": 1712345678000,
  "last_move": 1712345600000,
  "black_time": {"thinking_time": 300, "periods": 5, "period_time": 30},
  "white_time": {"thinking_time": 600, "periods": 5, "period_time": 30},
  "pause": {"paused": false, "pause_control": {}}
}]
```

**ClockTime varies by system:**
- **Byo-yomi:** `{thinking_time, periods, period_time, period_time_left?}`
- **Fischer:** `{thinking_time, skip_bonus}`
- **Canadian:** `{thinking_time, moves_left, block_time}`
- **Simple:** just a `number` (seconds)
- **Absolute:** `{thinking_time}`

Note: `current_player` is a player_id (not "B"/"W") — compare with `black_player_id`/`white_player_id`.

### Phase change
```
<- ["game/12345/phase", "stone removal"]
<- ["game/12345/phase", "finished"]
```
Phases: `"play"` → `"stone removal"` → `"finished"`

### Stone removal (scoring)
```
-> ["game/removed_stones/set", {"game_id": 12345, "removed": true, "stones": "aabbcc"}]
-> ["game/removed_stones/accept", {"game_id": 12345, "stones": "aabbcc", "strict_seki_mode": false}]
-> ["game/removed_stones/reject", {"game_id": 12345}]
```

### Resign
```
-> ["game/resign", {"game_id": 12345}]
```

### Game end
Signaled by `game/{id}/phase` = `"finished"` and/or updated `game/{id}/gamedata` with
`phase: "finished"`, `winner: player_id`, `outcome: "Resignation"/"Timeout"/"X.5 points"/etc.`

## Lobby / Seek Graph

```
-> ["seek_graph/connect", {"channel": "global"}]
<- ["seekgraph/global", [{challenge_id, user_id, username, rank, ranked, ...}, ...]]
```

### Public challenge contract checked 2026-09-30

The anonymous public WebSocket returned an initial `seekgraph/global` array of 49 entries. Two had `time_control_parameters.speed = "live"`; 47 were `"correspondence"`. The live entries had top-level `width`, `height`, `rengo`, `invite_only`, `private`, `user_id`, `username`, and numeric `rank` (not `ranking`). OGS's [Goban seek message interface](https://docs.online-go.com/goban/interfaces/protocol.SeekgraphChallengeMessage.html) confirms the main seek fields; the observed `rank` and `private` names come from the actual wire frame. The example below replaces player identifiers and omits unrelated fields:

```json
{
  "challenge_id": 123,
  "user_id": 456,
  "username": "anonymous",
  "rank": 26.25,
  "width": 19,
  "height": 19,
  "rengo": false,
  "invite_only": false,
  "private": false,
  "time_control": "byoyomi",
  "time_control_parameters": {
    "system": "byoyomi", "time_control": "byoyomi", "speed": "live",
    "main_time": 900, "period_time": 30, "periods": 5
  },
  "rules": "japanese", "ranked": true, "handicap": 0, "komi": null
}
```

The adapter offers only square 9/13/19 games with an explicit non-rengo, public seek and a recognized real-time speed (`live`, `rapid`, `blitz`; these values are in the [official Speed type](https://docs.online-go.com/goban/types/protocol.Speed.html)). Missing or unknown fields are excluded. An empty initial WebSocket snapshot is a real empty list. Before a snapshot arrives, or after the connection drops, listing fails and the box API returns 502; it must not present a false empty list.

The REST `GET /api/v1/challenges/?page_size=3` request returned HTTP 401 without an authenticated OGS session. Its response shape, including `game.width/height/rengo/time_control_parameters.speed`, was **not verified** on 2026-09-30. REST fallback is therefore disabled. Do not enable it from assumed paths without an authenticated, redacted response sample.

## Automatch
```
-> ["automatch/find_match", {
  "uuid": "...",
  "size_speed_options": [{"size": "19x19", "speed": "live"}],
  "lower_rank_diff": 3,
  "upper_rank_diff": 3,
  "rules": {"condition": "no-preference", "value": "chinese"},
  "handicap": {"condition": "no-preference", "value": "enabled"}
}]
<- ["automatch/start", {"uuid": "...", "game_id": 12345}]
-> ["automatch/cancel", {"uuid": "..."}]
```

## Challenge Flow
Current [OGS web client public-seek accept handler](https://github.com/online-go/online-go.com/blob/main/src/components/GameAcceptModal/GameAcceptModal.tsx) calls `POST /api/v1/challenges/{challenge_id}/accept` with `{}`. It ignores the POST response and navigates with the seek entry's `game_id`. Its [request helper](https://github.com/online-go/online-go.com/blob/main/src/lib/requests.ts) prefixes `/api/v1/` and sends `X-CSRFToken` from the login session cookie. This differs from the `me/challenges/{id}/accept` path used for direct invitations. A public seek without a verified `game_id` must not be accepted because the POST response is not a reliable source for it. Source reviewed 2026-09-30; an authenticated accept/result frame from this box remains unverified.

For a direct live invitation, the [current OGS ChallengeModal](https://github.com/online-go/online-go.com/blob/main/src/components/ChallengeModal/ChallengeModal.tsx#L3009-L3388) sends a `game.time_control` string, a `game.time_control_parameters` object containing both `system` and the legacy `time_control` key, and `challenger_color`. Its response carries `challenge` and `game` (number or object with `id`). While waiting, the client subscribes to `game/{game_id}/gamedata` and sends `challenge/keepalive` with `{challenge_id, game_id}` each second. It stops on gamedata, rejection, or cancellation; cancellation calls `DELETE /api/v1/me/challenges/{challenge_id}`. The box follows those wire shapes. A two-account OGS match has not yet verified this flow on the device.

Challenges arrive as notifications:
```
<- ["notification", {
  "type": "challenge",
  "challenge": {
    "id": 123,
    "challenger": {"id": 456, "username": "...", "ranking": 25.5},
    "width": 19, "height": 19,
    "rules": "chinese", "ranked": true
  }
}]
```
Accept via REST: `POST /api/v1/me/challenges/{id}/accept`
Decline via REST: `DELETE /api/v1/me/challenges/{id}`

## Ping / Clock Sync (10s interval)
```
-> ["net/ping", {"client": 1712345678000, "drift": 0, "latency": 50}]
<- ["net/pong", {"client": 1712345678000, "server": 1712345678050}]
```

## Key REST Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| POST | /api/v0/login | Session login |
| GET | /api/v1/ui/config | JWT + user config |
| GET | /api/v1/me/ | Current user profile |
| GET | /api/v1/players/ | Player search |
| POST | /api/v1/players/{id}/challenge/ | Send challenge |
| POST | /api/v1/me/challenges/{id}/accept | Accept challenge |
| DELETE | /api/v1/me/challenges/{id}/ | Decline challenge |
| GET | /api/v1/games/{id}/ | Game details |
| GET | /api/v1/games/{id}/sgf | Game SGF |
| GET | /api/v1/ui/overview | Active games |

## Important Notes

- Socket.io is **gone**. Native WebSocket only.
- All emits are fire-and-forget (no ack callbacks) unless you include a request_id.
- Pings are essential — 10s interval for keep-alive and clock sync.
- `active_game` events arrive after authentication for all your ongoing games.
- Strip `clock.now` from clock events — use local time for countdown.
- The goban library `GobanSocket` is the authoritative reference for wire format.
