"""Network-bound fake central authority for the physical-box smoke test."""

import asyncio

from fastapi import FastAPI, HTTPException, Request, WebSocket

app = FastAPI()
AUTH = "cloud-secret"


def state(stones=None, player="B"):
    stones = stones or []
    return {
        "game_type": "free",
        "board_size": [19, 19],
        "stones": stones,
        "current_node_index": len(stones),
        "player_to_move": player,
        "players_info": {"B": {"player_type": "human"}, "W": {"player_type": "human"}},
    }


app.state.game_state = state()
app.state.move_seen = asyncio.Event()


def require_cloud(request: Request):
    if request.headers.get("authorization") != f"Bearer {AUTH}":
        raise HTTPException(status_code=401)


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/api/v1/auth/me")
def me(request: Request):
    require_cloud(request)
    return {"id": 811, "username": "box-user"}


@app.get("/api/v1/users/online")
def online(request: Request):
    require_cloud(request)
    return [{"id": 811, "username": "box-user", "ladder_rung": 4, "rank_label": "1d", "presence": "playing"}]


@app.get("/api/v1/games/active/multiplayer")
def active(request: Request):
    require_cloud(request)
    return [
        {
            "session_id": "central-room",
            "player_b": "box-user",
            "player_w": "opponent",
            "player_b_id": 811,
            "player_w_id": 990,
            "spectator_count": 0,
            "move_count": 0,
        }
    ]


@app.get("/api/state")
def current_state(request: Request, session_id: str):
    require_cloud(request)
    if session_id != "central-room":
        raise HTTPException(status_code=404)
    return {"session_id": session_id, "state": app.state.game_state}


@app.post("/api/move")
async def move(request: Request):
    require_cloud(request)
    body = await request.json()
    if body.get("session_id") != "central-room" or body.get("coords") != [3, 3]:
        raise HTTPException(status_code=409, detail="unexpected move")
    app.state.game_state = state([["B", [3, 3], None, 1]], "W")
    app.state.move_seen.set()
    return {"session_id": "central-room", "state": app.state.game_state}


def require_ws(websocket: WebSocket):
    return websocket.cookies.get("sb_token") == AUTH and websocket.headers.get("origin") == (
        f"http://{websocket.url.netloc}"
    )


@app.websocket("/ws/lobby")
async def lobby(websocket: WebSocket):
    await websocket.accept()
    if not require_ws(websocket):
        await websocket.close(code=1008)
        return
    await websocket.send_json({"type": "lobby_update", "online_count": 2})
    while True:
        payload = await websocket.receive_json()
        if payload.get("type") == "start_matchmaking":
            await websocket.send_json(
                {"type": "match_found", "session_id": "central-room", "game_type": "free", "my_color": "B"}
            )


@app.websocket("/ws/central-room")
async def room(websocket: WebSocket):
    await websocket.accept()
    if not require_ws(websocket):
        await websocket.close(code=1008)
        return
    await websocket.send_json({"type": "game_update", "state": app.state.game_state})
    await app.state.move_seen.wait()
    await websocket.send_json({"type": "game_update", "state": app.state.game_state})
    app.state.game_state = state([["B", [3, 3], None, 1], ["W", [4, 4], None, 2]], "B")
    await websocket.send_json({"type": "game_update", "state": app.state.game_state})
    await websocket.receive_json()
