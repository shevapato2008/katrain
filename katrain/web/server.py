import argparse
import asyncio
import logging
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
    node_id: Optional[int] = None


class NewGameRequest(BaseModel):
    session_id: str
    size: Optional[int] = 19
    handicap: Optional[int] = 0
    komi: Optional[float] = 6.5


class EditGameRequest(BaseModel):
    session_id: str
    size: Optional[int] = None
    handicap: Optional[int] = None
    komi: Optional[float] = None
    rules: Optional[str] = None


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


class InsertModeRequest(BaseModel):
    session_id: str
    mode: str = "toggle"


class UIToggleRequest(BaseModel):
    session_id: str
    setting: str


class LanguageRequest(BaseModel):
    session_id: str
    lang: str


class ThemeRequest(BaseModel):
    session_id: str
    theme: str


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


class GameAnalysisRequest(BaseModel):
    session_id: str
    visits: Optional[int] = None
    mistakes_only: bool = False
    move_range: Optional[List[int]] = None


class GameReportRequest(BaseModel):
    session_id: str
    depth_filter: Optional[List[float]] = None


def create_app(enable_engine=True, session_timeout=3600, max_sessions=100):
    # Set logging levels for our application
    logging.getLogger("katrain_web").setLevel(logging.INFO)
    
    app = FastAPI()
    static_root = Path(__file__).resolve().parent / "static"
    assets_root = Path(__file__).resolve().parent.parent
    
    # Specific asset mounts first
    app.mount("/assets/img", StaticFiles(directory=assets_root / "img"), name="img")
    app.mount("/assets/fonts", StaticFiles(directory=assets_root / "fonts"), name="fonts")
    app.mount("/assets/sounds", StaticFiles(directory=assets_root / "sounds"), name="sounds")

    manager = SessionManager(
        session_timeout=session_timeout,
        max_sessions=max_sessions,
        enable_engine=enable_engine,
    )
    app.state.session_manager = manager

    @app.on_event("startup")
    async def _startup():
        try:
            from katrain.web.interface import WebKaTrain
            # Just init to trigger imports and config loading
            kt = WebKaTrain(force_package_config=False, enable_engine=False)
            
            # Auto-test HTTP Engine
            engine_cfg = kt.config("engine")
            if engine_cfg.get("backend") == "http":
                import httpx
                url = engine_cfg.get("http_url")
                health = engine_cfg.get("http_health_path", "/health")
                full_url = f"{url.rstrip('/')}/{health.lstrip('/')}"
                print(f"Testing KataGo Engine at {full_url}...")
                try:
                    async with httpx.AsyncClient() as client:
                        resp = await client.get(full_url, timeout=5.0)
                        if resp.status_code == 200:
                            print(f"KataGo Engine is reachable: {resp.json()}")
                        else:
                            print(f"WARNING: KataGo Engine returned status {resp.status_code}")
                except Exception as e:
                    print(f"WARNING: Failed to connect to KataGo Engine: {e}")

        except Exception as e:
            logging.getLogger("katrain_web").error(f"Initialization failed: {e}")

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
        try:
            session = manager.create_session()
        except Exception as exc:
            logging.getLogger("katrain_web").error(f"API: create_session failed: {exc}")
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        return {"session_id": session.session_id, "state": session.last_state}

    @app.get("/api/state")
    def get_state(session_id: str):
        try:
            session = manager.get_session(session_id)
        except KeyError as exc:
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

    @app.post("/api/edit-game")
    def edit_game(request: EditGameRequest):
        session = _get_session_or_404(manager, request.session_id)
        with session.lock:
            session.katrain("edit_game", size=request.size, handicap=request.handicap, komi=request.komi, rules=request.rules)
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

    @app.post("/api/timer/pause")
    def pause_timer(request: ToggleAnalysisRequest):
        session = _get_session_or_404(manager, request.session_id)
        with session.lock:
            session.katrain.timer_paused = not session.katrain.timer_paused
            state = session.katrain.get_state()
            session.last_state = state
        return {"session_id": session.session_id, "state": state, "paused": session.katrain.timer_paused}

    @app.post("/api/rotate")
    def rotate(request: ToggleAnalysisRequest):
        session = _get_session_or_404(manager, request.session_id)
        with session.lock:
            session.katrain("rotate")
            state = session.katrain.get_state()
            session.last_state = state
        return {"session_id": session.session_id, "state": state}

    @app.post("/api/node/delete")
    def delete_node(request: NavRequest):
        session = _get_session_or_404(manager, request.session_id)
        with session.lock:
            session.katrain("delete_node", node_id=request.node_id)
            state = session.katrain.get_state()
            session.last_state = state
        return {"session_id": session.session_id, "state": state}

    @app.post("/api/node/prune")
    def prune_branch(request: NavRequest):
        session = _get_session_or_404(manager, request.session_id)
        with session.lock:
            session.katrain("prune_branch", node_id=request.node_id)
            state = session.katrain.get_state()
            session.last_state = state
        return {"session_id": session.session_id, "state": state}

    @app.post("/api/node/make-main")
    def make_main_branch(request: NavRequest):
        session = _get_session_or_404(manager, request.session_id)
        with session.lock:
            session.katrain("make_main_branch", node_id=request.node_id)
            state = session.katrain.get_state()
            session.last_state = state
        return {"session_id": session.session_id, "state": state}

    @app.post("/api/node/toggle-collapse")
    def toggle_collapse(request: NavRequest):
        session = _get_session_or_404(manager, request.session_id)
        with session.lock:
            session.katrain("toggle_collapse", node_id=request.node_id)
            state = session.katrain.get_state()
            session.last_state = state
        return {"session_id": session.session_id, "state": state}

    @app.post("/api/ui/toggle")
    def toggle_ui(request: UIToggleRequest):
        session = _get_session_or_404(manager, request.session_id)
        with session.lock:
            session.katrain("toggle_ui", setting=request.setting)
            state = session.katrain.get_state()
            session.last_state = state
        return {"session_id": session.session_id, "state": state}

    @app.post("/api/language")
    def switch_language(request: LanguageRequest):
        session = _get_session_or_404(manager, request.session_id)
        with session.lock:
            session.katrain("switch_lang", lang=request.lang)
            state = session.katrain.get_state()
            session.last_state = state
        return {"session_id": session.session_id, "state": state, "language": session.katrain.config("general/language")}

    @app.get("/api/translations")
    def get_translations(lang: str):
        from katrain.core.lang import i18n
        # Switch language temporarily to get the catalog if needed, 
        # but i18n.switch_lang is global.
        # However, the frontend will call this when it wants to refresh its labels.
        i18n.switch_lang(lang)
        catalog = getattr(i18n.ugettext.__self__, "_catalog", {})
        return {"lang": lang, "translations": catalog}

    @app.post("/api/theme")
    def switch_theme(request: ThemeRequest):
        session = _get_session_or_404(manager, request.session_id)
        with session.lock:
            session.katrain("switch_theme", theme=request.theme)
            state = session.katrain.get_state()
            session.last_state = state
        return {"session_id": session.session_id, "state": state, "theme": session.katrain.config("trainer/theme")}

    @app.post("/api/analysis/game")
    def analyze_game(request: GameAnalysisRequest):
        session = _get_session_or_404(manager, request.session_id)
        with session.lock:
            kwargs = {
                "visits": request.visits,
                "mistakes_only": request.mistakes_only,
                "move_range": request.move_range,
            }
            # remove None values
            kwargs = {k: v for k, v in kwargs.items() if v is not None}
            session.katrain("game_analysis", **kwargs)
            state = session.katrain.get_state()
            session.last_state = state
        return {"session_id": session.session_id, "state": state}

    @app.post("/api/analysis/report")
    def get_game_report(request: GameReportRequest):
        session = _get_session_or_404(manager, request.session_id)
        with session.lock:
            report = session.katrain._do_game_report(depth_filter=request.depth_filter)
        return {"session_id": session.session_id, "report": report}

    @app.post("/api/mode/insert")
    def set_insert_mode(request: InsertModeRequest):
        session = _get_session_or_404(manager, request.session_id)
        with session.lock:
            session.katrain("insert_mode", mode=request.mode)
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

    # Catch-all for other static files (like vite.svg and JS/CSS in assets/)
    app.mount("/", StaticFiles(directory=static_root, html=True), name="root")

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
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind the server to. Use 127.0.0.1 if using a reverse proxy like Nginx.")
    parser.add_argument("--port", type=int, default=8001)
    parser.add_argument("--reload", action="store_true")
    parser.add_argument("--log-level", default="warning")
    parser.add_argument("--disable-engine", action="store_true")
    parser.add_argument("--ui", default=None, help="Interface mode to use. 'web' (default) starts the FastAPI server, while 'desktop' launches the Kivy GUI.")
    args, _unknown = parser.parse_known_args()

    import uvicorn

    host = args.host
    port = args.port
    
    # Configure uvicorn logging to reduce noise
    log_config = uvicorn.config.LOGGING_CONFIG
    log_config["formatters"]["default"]["fmt"] = "%(levelname)s:     %(message)s"
    log_config["formatters"]["access"]["fmt"] = "%(levelname)s:     %(message)s"

    print(f"\n" + "=" * 50)
    print(f"Starting KaTrain Web UI")
    if host == "0.0.0.0":
        print(f"Local access: http://127.0.0.1:{port}")
        print(f"Network access: http://<your-ip-address>:{port}")
    else:
        print(f"Access: http://{host}:{port}")
    print("=" * 50 + "\n")

    app = create_app(enable_engine=not args.disable_engine)
    uvicorn.run(
        app, 
        host=host, 
        port=port, 
        reload=args.reload, 
        log_level=args.log_level,
        access_log=False # Disable access logs to keep console clean for KataGo logs
    )


if __name__ == "__main__":
    run_web()