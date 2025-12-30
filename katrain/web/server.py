import argparse
import asyncio
from pathlib import Path
from typing import Any, List, Optional, Union

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from katrain.web.session import SessionManager


class MoveRequest(BaseModel):
    session_id: str
    coords: Optional[List[int]] = Field(default=None, min_items=2, max_items=2)
    pass_move: bool = False


class UndoRedoRequest(BaseModel):
    session_id: str
    n_times: Union[int, str] = 1


class NavRequest(BaseModel):
    session_id: str
    node_id: int


class NewGameRequest(BaseModel):
    session_id: str
    size: Optional[int] = 19
    handicap: Optional[int] = 0
    komi: Optional[float] = 6.5


class LoadSGFRequest(BaseModel):
    session_id: str
    sgf: str


class ConfigUpdateRequest(BaseModel):
    session_id: str
    setting: str
    value: Any


class UpdatePlayerRequest(BaseModel):
    session_id: str
    bw: str
    player_type: Optional[str] = None
    player_subtype: Optional[str] = None


class ToggleAnalysisRequest(BaseModel):
    session_id: str


class ModeRequest(BaseModel):
    session_id: str
    mode: str


class AnalyzeExtraRequest(BaseModel):
    session_id: str
    mode: str
    kwargs: Optional[dict] = None


class FindMistakeRequest(BaseModel):
    session_id: str
    fn: str = "redo"


class SwitchBranchRequest(BaseModel):
    session_id: str
    direction: int


class TsumegoRequest(BaseModel):
    session_id: str
    ko: bool = False
    margin: Optional[int] = None


class SelfPlayRequest(BaseModel):
    session_id: str
    until_move: Any
    target_b_advantage: Optional[float] = None


class SelectBoxRequest(BaseModel):
    session_id: str
    coords: List[int]


def create_app(enable_engine=True, session_timeout=3600, max_sessions=100):
    print("DEBUG: create_app start")
    app = FastAPI()
    static_root = Path(__file__).resolve().parent / "static"
    assets_root = Path(__file__).resolve().parent.parent
    
    # Specific asset mounts first
    app.mount("/assets/img", StaticFiles(directory=assets_root / "img"), name="img")
    app.mount("/assets/fonts", StaticFiles(directory=assets_root / "fonts"), name="fonts")

    manager = SessionManager(
        session_timeout=session_timeout,
        max_sessions=max_sessions,
        enable_engine=enable_engine,
    )
    app.state.session_manager = manager

    @app.on_event("startup")
    async def _startup():
        print("DEBUG: Pre-initializing Kivy on main thread...")
        try:
            from katrain.web.interface import WebKaTrain
            # Just init to trigger imports and config loading
            WebKaTrain(force_package_config=True, enable_engine=False)
            print("DEBUG: Kivy pre-initialization complete.")
        except Exception as e:
            print(f"DEBUG: Kivy pre-initialization failed: {e}")

        manager.attach_loop(asyncio.get_running_loop())
        app.state.cleanup_task = asyncio.create_task(_cleanup_loop(manager))

    @app.on_event("shutdown")
    async def _shutdown():
        task = getattr(app.state, "cleanup_task", None)
        if task:
            task.cancel()
        manager.cleanup_expired()

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.post("/api/session")
    def create_session():
        print("API: create_session called")
        try:
            session = manager.create_session()
            print(f"API: create_session success, id={session.session_id}")
        except Exception as exc:
            print(f"API: create_session failed: {exc}")
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        return {"session_id": session.session_id, "state": session.last_state}

    @app.get("/api/state")
    def get_state(session_id: str):
        print(f"API: get_state called for {session_id}")
        try:
            session = manager.get_session(session_id)
        except KeyError as exc:
            print(f"API: session {session_id} not found")
            raise HTTPException(status_code=404, detail="Session not found") from exc
        return {"session_id": session.session_id, "state": session.last_state or session.katrain.get_state()}

    @app.post("/api/move")
    def play_move(request: MoveRequest):
        session = _get_session_or_404(manager, request.session_id)
        coords = None if request.pass_move else request.coords
        if coords is None and not request.pass_move:
            raise HTTPException(status_code=400, detail="coords required unless pass_move is true")
        with session.lock:
            session.katrain("play", None if coords is None else tuple(coords))
            state = session.katrain.get_state()
            session.last_state = state
        return {"session_id": session.session_id, "state": state}

    @app.post("/api/undo")
    def undo_move(request: UndoRedoRequest):
        session = _get_session_or_404(manager, request.session_id)
        with session.lock:
            session.katrain("undo", request.n_times)
            state = session.katrain.get_state()
            session.last_state = state
        return {"session_id": session.session_id, "state": state}

    @app.post("/api/redo")
    def redo_move(request: UndoRedoRequest):
        session = _get_session_or_404(manager, request.session_id)
        with session.lock:
            session.katrain("redo", request.n_times)
            state = session.katrain.get_state()
            session.last_state = state
        return {"session_id": session.session_id, "state": state}

    @app.get("/api/sgf/save")
    def save_sgf(session_id: str):
        session = _get_session_or_404(manager, session_id)
        with session.lock:
            sgf = session.katrain.get_sgf()
        return {"sgf": sgf}

    @app.post("/api/sgf/load")
    def load_sgf(request: LoadSGFRequest):
        session = _get_session_or_404(manager, request.session_id)
        with session.lock:
            session.katrain("load_sgf", request.sgf)
            state = session.katrain.get_state()
            session.last_state = state
        return {"session_id": session.session_id, "state": state}

    @app.post("/api/new-game")
    def new_game(request: NewGameRequest):
        session = _get_session_or_404(manager, request.session_id)
        with session.lock:
            session.katrain("new_game", size=request.size, handicap=request.handicap, komi=request.komi)
            state = session.katrain.get_state()
            session.last_state = state
        return {"session_id": session.session_id, "state": state}

    @app.post("/api/nav")
    def navigate(request: NavRequest):
        session = _get_session_or_404(manager, request.session_id)
        with session.lock:
            session.katrain("nav", request.node_id)
            state = session.katrain.get_state()
            session.last_state = state
        return {"session_id": session.session_id, "state": state}

    @app.post("/api/ai-move")
    def ai_move(request: UndoRedoRequest):
        session = _get_session_or_404(manager, request.session_id)
        with session.lock:
            session.katrain("ai-move")
            state = session.katrain.get_state()
            session.last_state = state
        return {"session_id": session.session_id, "state": state}

    @app.post("/api/config")
    def update_config(request: ConfigUpdateRequest):
        session = _get_session_or_404(manager, request.session_id)
        with session.lock:
            session.katrain.update_config(request.setting, request.value)
            state = session.katrain.get_state()
            session.last_state = state
        return {"session_id": session.session_id, "state": state}

    @app.post("/api/player")
    def update_player(request: UpdatePlayerRequest):
        session = _get_session_or_404(manager, request.session_id)
        with session.lock:
            session.katrain("update_player", bw=request.bw, player_type=request.player_type, player_subtype=request.player_subtype)
            state = session.katrain.get_state()
            session.last_state = state
        return {"session_id": session.session_id, "state": state}

    @app.post("/api/analysis/continuous")
    def toggle_continuous_analysis(request: ToggleAnalysisRequest):
        session = _get_session_or_404(manager, request.session_id)
        with session.lock:
            session.katrain.pondering = not session.katrain.pondering
            session.katrain.update_state()
            state = session.katrain.get_state()
            session.last_state = state
        return {"session_id": session.session_id, "state": state, "pondering": session.katrain.pondering}

    @app.post("/api/analysis/extra")
    def analyze_extra(request: AnalyzeExtraRequest):
        session = _get_session_or_404(manager, request.session_id)
        with session.lock:
            kwargs = request.kwargs or {}
            session.katrain("analyze_extra", mode=request.mode, **kwargs)
            state = session.katrain.get_state()
            session.last_state = state
        return {"session_id": session.session_id, "state": state}

    @app.post("/api/mode")
    def set_mode(request: ModeRequest):
        session = _get_session_or_404(manager, request.session_id)
        with session.lock:
            session.katrain.play_analyze_mode = request.mode
            session.katrain.update_state()
            state = session.katrain.get_state()
            session.last_state = state
        return {"session_id": session.session_id, "state": state, "mode": session.katrain.play_analyze_mode}

    @app.post("/api/nav/mistake")
    def find_mistake(request: FindMistakeRequest):
        session = _get_session_or_404(manager, request.session_id)
        with session.lock:
            session.katrain("find_mistake", fn=request.fn)
            state = session.katrain.get_state()
            session.last_state = state
        return {"session_id": session.session_id, "state": state}

    @app.post("/api/nav/branch")
    def switch_branch(request: SwitchBranchRequest):
        session = _get_session_or_404(manager, request.session_id)
        with session.lock:
            session.katrain("switch_branch", direction=request.direction)
            state = session.katrain.get_state()
            session.last_state = state
        return {"session_id": session.session_id, "state": state}

    @app.post("/api/analysis/tsumego")
    def tsumego_frame(request: TsumegoRequest):
        session = _get_session_or_404(manager, request.session_id)
        with session.lock:
            session.katrain("tsumego_frame", ko=request.ko, margin=request.margin)
            state = session.katrain.get_state()
            session.last_state = state
        return {"session_id": session.session_id, "state": state}

    @app.post("/api/analysis/selfplay")
    def selfplay(request: SelfPlayRequest):
        session = _get_session_or_404(manager, request.session_id)
        with session.lock:
            session.katrain("selfplay_setup", until_move=request.until_move, target_b_advantage=request.target_b_advantage)
            state = session.katrain.get_state()
            session.last_state = state
        return {"session_id": session.session_id, "state": state}

    @app.post("/api/analysis/region")
    def set_region(request: SelectBoxRequest):
        session = _get_session_or_404(manager, request.session_id)
        with session.lock:
            session.katrain("select_box", coords=request.coords)
            state = session.katrain.get_state()
            session.last_state = state
        return {"session_id": session.session_id, "state": state}

    @app.post("/api/resign")
    def resign(request: ToggleAnalysisRequest):
        session = _get_session_or_404(manager, request.session_id)
        with session.lock:
            session.katrain("resign")
            state = session.katrain.get_state()
            session.last_state = state
        return {"session_id": session.session_id, "state": state}

    @app.post("/api/rotate")
    def rotate(request: ToggleAnalysisRequest):
        session = _get_session_or_404(manager, request.session_id)
        with session.lock:
            session.katrain("rotate")
            state = session.katrain.get_state()
            session.last_state = state
        return {"session_id": session.session_id, "state": state}

    @app.websocket("/ws/{session_id}")
    async def websocket_endpoint(websocket: WebSocket, session_id: str):
        try:
            session = manager.get_session(session_id)
        except KeyError:
            await websocket.close(code=1008)
            return

        await websocket.accept()
        session.sockets.add(websocket)
        try:
            await websocket.send_json({"type": "game_update", "state": session.last_state or session.katrain.get_state()})
            while True:
                message = await websocket.receive_json()
                if message.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})
        except WebSocketDisconnect:
            pass
        finally:
            session.sockets.discard(websocket)

    @app.get("/")
    def index():
        return FileResponse(static_root / "index.html")

    # Catch-all for other static files (like vite.svg and JS/CSS in assets/)
    app.mount("/", StaticFiles(directory=static_root), name="root")

    return app


async def _cleanup_loop(manager: SessionManager):
    while True:
        await asyncio.sleep(30)
        manager.cleanup_expired()


def _get_session_or_404(manager: SessionManager, session_id: str):
    try:
        return manager.get_session(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Session not found") from exc


def run_web():
    parser = argparse.ArgumentParser(description="Run KaTrain Web UI server")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8001)
    parser.add_argument("--reload", action="store_true")
    parser.add_argument("--log-level", default="info")
    parser.add_argument("--disable-engine", action="store_true")
    parser.add_argument("--ui", default=None)
    args, _unknown = parser.parse_known_args()

    import uvicorn

    print(f"Starting KaTrain Web UI on http://{args.host}:{args.port}")
    app = create_app(enable_engine=not args.disable_engine)
    print("DEBUG: calling uvicorn.run")
    uvicorn.run(app, host=args.host, port=args.port, reload=args.reload, log_level=args.log_level)
