import argparse
import asyncio
import logging
import os
from pathlib import Path
from typing import Any, List, Optional, Union, Dict

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager

from katrain.web.api.v1.api import api_router
from katrain.web.core.config import settings
from katrain.web.session import SessionManager, LobbyManager
from katrain.web.models import *

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize User Persistence
    from katrain.web.core.auth import SQLAlchemyUserRepository, get_password_hash
    from katrain.web.core.game_repo import GameRepository
    from katrain.web.core.db import SessionLocal
    
    repo = SQLAlchemyUserRepository(SessionLocal)
    repo.init_db()
    
    game_repo = GameRepository(SessionLocal)

    # Create default admin user if no users exist
    # Create default admin user if no users exist
    if not repo.list_users():
        logging.getLogger("katrain_web").info("No users found. Creating default admin user (admin/admin)")
        try:
            repo.create_user("admin", get_password_hash("admin"))
        except ValueError:
            pass # Already exists race condition

    app.state.user_repo = repo
    app.state.game_repo = game_repo
    app.state.lobby_manager = LobbyManager()

    # Initialize Engine Clients and Router
    from katrain.web.core.engine_client import KataGoClient
    from katrain.web.core.router import RequestRouter
    
    local_client = KataGoClient(url=settings.LOCAL_KATAGO_URL)
    cloud_client = None
    if settings.CLOUD_KATAGO_URL:
        cloud_client = KataGoClient(url=settings.CLOUD_KATAGO_URL)
    
    app.state.router = RequestRouter(local_client=local_client, cloud_client=cloud_client)

    manager = app.state.session_manager
    try:
        from katrain.web.interface import WebKaTrain
        # Just init to trigger imports and config loading
        kt = WebKaTrain(force_package_config=False, enable_engine=False)
        
        # Sync configuration with Environment Settings
        engine_cfg = kt.config("engine")
        if settings.LOCAL_KATAGO_URL and engine_cfg.get("http_url") != settings.LOCAL_KATAGO_URL:
            if engine_cfg.get("backend") == "http":
                print(f"Syncing KataGo URL to {settings.LOCAL_KATAGO_URL} from environment")
                kt.update_config("engine/http_url", settings.LOCAL_KATAGO_URL)
                kt.save_config("engine")
                engine_cfg = kt.config("engine") # Reload local ref
        
        # Auto-test HTTP Engine
        engine_cfg = kt.config("engine")
        if engine_cfg.get("backend") == "http":
            import httpx
            logging.getLogger("httpx").setLevel(logging.WARNING)
            logging.getLogger("httpcore").setLevel(logging.WARNING)
            url = engine_cfg.get("http_url")
            health = engine_cfg.get("http_health_path", "/health")
            full_url = f"{url.rstrip('/')}/{health.lstrip('/')}"
            print(f"Testing KataGo Engine at {full_url}...")
            try:
                async with httpx.AsyncClient(trust_env=False) as client:
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
    
    yield
    
    task = getattr(app.state, "cleanup_task", None)
    if task:
        task.cancel()
    manager.cleanup_expired()

def create_app(enable_engine=True, session_timeout=None, max_sessions=None):
    if session_timeout is None:
        session_timeout = settings.SESSION_TIMEOUT
    if max_sessions is None:
        max_sessions = settings.MAX_SESSIONS
    # Set logging levels for our application
    logging.getLogger("katrain_web").setLevel(logging.INFO)
    
    app = FastAPI(lifespan=lifespan)
    app.include_router(api_router, prefix="/api/v1")
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

    @app.get("/health")
    async def health():
        from katrain.web.api.v1.endpoints.health import health as health_v1
        return await health_v1()

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
            if request.players:
                for bw, p in request.players.items():
                    session.katrain("update_player", bw=bw, player_type=p.player_type, player_subtype=p.player_subtype, name=p.name)
                    if p.name:
                        session.katrain.game.root.set_property("P" + bw, p.name)
            
            if request.clear_cache:
                session.katrain.engine.on_new_game()

            session.katrain("new_game", size=request.size, handicap=request.handicap, komi=request.komi, rules=request.rules)
            state = session.katrain.get_state()
            session.last_state = state
        return {"session_id": session.session_id, "state": state}

    @app.post("/api/game/setup")
    def game_setup(request: GameSettingsRequest):
        session = _get_session_or_404(manager, request.session_id)
        mode = request.mode
        settings = request.settings
        with session.lock:
            # Update players
            players = settings.get("players")
            if players:
                for bw, p in players.items():
                    session.katrain("update_player", bw=bw, player_type=p["player_type"], player_subtype=p["player_subtype"], name=p.get("name"))
                    if p.get("name"):
                        session.katrain.game.root.set_property("P" + bw, p["name"])

            if mode == "newgame" or mode == "setupposition":
                if settings.get("clear_cache"):
                    session.katrain.engine.on_new_game()
                session.katrain("new_game", size=settings.get("size"), handicap=settings.get("handicap"), komi=settings.get("komi"))
                if mode == "setupposition":
                    session.katrain("selfplay_setup", until_move=settings.get("setup_move"), target_b_advantage=settings.get("setup_advantage"))
            elif mode == "editgame":
                session.katrain("_do_edit_game", size=settings.get("size"), handicap=settings.get("handicap"), komi=settings.get("komi"), rules=settings.get("rules"))
            
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

    @app.get("/api/config")
    def get_config(session_id: str, setting: str):
        session = _get_session_or_404(manager, session_id)
        # config is thread-safe enough for read
        value = session.katrain.config(setting)
        return {"setting": setting, "value": value}

    @app.post("/api/config")
    def update_config(request: ConfigUpdateRequest):
        session = _get_session_or_404(manager, request.session_id)
        with session.lock:
            session.katrain.update_config(request.setting, request.value)
            state = session.katrain.get_state()
            session.last_state = state
        return {"session_id": session.session_id, "state": state}

    @app.post("/api/config/bulk")
    def update_config_bulk(request: ConfigBulkUpdateRequest):
        session = _get_session_or_404(manager, request.session_id)
        with session.lock:
            for setting, value in request.updates.items():
                session.katrain.update_config(setting, value)
            state = session.katrain.get_state()
            session.last_state = state
        return {"session_id": session.session_id, "state": state}

    @app.post("/api/player")
    def update_player(request: UpdatePlayerRequest):
        session = _get_session_or_404(manager, request.session_id)
        with session.lock:
            session.katrain("update_player", bw=request.bw, player_type=request.player_type, player_subtype=request.player_subtype, name=request.name)
            state = session.katrain.get_state()
            session.last_state = state
        return {"session_id": session.session_id, "state": state}

    @app.post("/api/player/swap")
    def swap_players(request: ToggleAnalysisRequest):
        session = _get_session_or_404(manager, request.session_id)
        with session.lock:
            session.katrain("swap_players")
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

    @app.post("/api/analysis/show-pv")
    def show_pv(request: PVRequest):
        session = _get_session_or_404(manager, request.session_id)
        with session.lock:
            session.katrain("_do_show_pv", request.pv)
            state = session.katrain.get_state()
            session.last_state = state
        return {"session_id": session.session_id, "state": state}

    @app.post("/api/analysis/clear-pv")
    def clear_pv(request: ToggleAnalysisRequest):
        session = _get_session_or_404(manager, request.session_id)
        with session.lock:
            session.katrain("_do_clear_pv")
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

    @app.get("/api/ai-constants")
    def get_ai_constants():
        from katrain.core.constants import (
            AI_STRATEGIES_RECOMMENDED_ORDER,
            AI_OPTION_VALUES,
            AI_KEY_PROPERTIES,
            AI_CONFIG_DEFAULT
        )
        # Convert range objects to lists for JSON serialization
        json_option_values = {}
        for k, v in AI_OPTION_VALUES.items():
            if isinstance(v, range):
                json_option_values[k] = list(v)
            elif isinstance(v, list):
                # Check for tuples inside list (value, label)
                new_list = []
                for item in v:
                    if isinstance(item, tuple):
                        new_list.append(list(item))
                    else:
                        new_list.append(item)
                json_option_values[k] = new_list
            else:
                json_option_values[k] = v

        # Default settings for each AI strategy
        strategy_defaults = {
            "ai:default": {},
            "ai:antimirror": {},
            "ai:handicap": {"automatic": True, "pda": 0},
            "ai:jigo": {"target_score": 0.5},
            "ai:scoreloss": {"strength": 0.2},
            "ai:policy": {"opening_moves": 24},
            "ai:simple": {
                "max_points_lost": 1.75,
                "settled_weight": 1.0,
                "opponent_fac": 0.5,
                "min_visits": 3,
                "attach_penalty": 1,
                "tenuki_penalty": 0.5
            },
            "ai:p:weighted": {"weaken_fac": 0.5, "pick_override": 1.0, "lower_bound": 0.001},
            "ai:p:pick": {"pick_override": 0.95, "pick_n": 5, "pick_frac": 0.35},
            "ai:p:local": {"pick_override": 0.95, "stddev": 1.5, "pick_n": 15, "pick_frac": 0.0, "endgame": 0.5},
            "ai:p:tenuki": {"pick_override": 0.85, "stddev": 7.5, "pick_n": 5, "pick_frac": 0.4, "endgame": 0.45},
            "ai:p:influence": {"pick_override": 0.95, "pick_n": 5, "pick_frac": 0.3, "threshold": 3.5, "line_weight": 10, "endgame": 0.4},
            "ai:p:territory": {"pick_override": 0.95, "pick_n": 5, "pick_frac": 0.3, "threshold": 3.5, "line_weight": 2, "endgame": 0.4},
            "ai:p:rank": {"kyu_rank": -2},
            "ai:human": {"human_kyu_rank": 0, "modern_style": True},
            "ai:pro": {"pro_year": 2010, "modern_style": True},
        }

        return {
            "strategies": AI_STRATEGIES_RECOMMENDED_ORDER,
            "options": json_option_values,
            "key_properties": list(AI_KEY_PROPERTIES),
            "default_strategy": AI_CONFIG_DEFAULT,
            "strategy_defaults": strategy_defaults
        }

    @app.post("/api/ai/estimate-rank")
    def estimate_rank(request: RankEstimationRequest):
        from katrain.core.ai import ai_rank_estimation
        from katrain.core.lang import rank_label
        try:
            rank = ai_rank_estimation(request.strategy, request.settings)
            return {"rank": rank_label(rank)}
        except Exception as e:
            logging.getLogger("katrain_web").error(f"Rank estimation failed: {e}")
            return {"rank": "??"}

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

    @app.websocket("/ws/lobby")
    async def lobby_websocket_endpoint(websocket: WebSocket):
        from katrain.web.api.v1.endpoints.auth import get_user_from_token
        token = websocket.query_params.get("token")
        if not token:
            await websocket.close(code=1008)
            return
        
        try:
            current_user = await get_user_from_token(token=token, repo=app.state.user_repo)
        except Exception:
            await websocket.close(code=1008)
            return

        await websocket.accept()
        lobby_manager = app.state.lobby_manager
        lobby_manager.add_user(current_user.id, websocket)
        try:
            # Broadcast update immediately
            await lobby_manager.broadcast({"type": "lobby_update", "online_count": len(lobby_manager.get_online_user_ids())})
            while True:
                message = await websocket.receive_json()
                if message.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})
        except WebSocketDisconnect:
            pass
        finally:
            lobby_manager.remove_user(current_user.id, websocket)
            await lobby_manager.broadcast({"type": "lobby_update", "online_count": len(lobby_manager.get_online_user_ids())})

    # SPA Routing for Galaxy UI
    @app.get("/galaxy", response_class=FileResponse)
    @app.get("/galaxy/{full_path:path}", response_class=FileResponse)
    async def serve_galaxy_app(full_path: str = None):
        return str(static_root / "index.html")

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


def build_frontend():
    ui_path = Path(__file__).resolve().parent / "ui"
    if not (ui_path / "package.json").exists():
        logging.getLogger("katrain_web").warning("Frontend source not found, skipping build.")
        return

    import shutil
    import subprocess
    import sys

    if not shutil.which("npm"):
        logging.getLogger("katrain_web").warning("npm not found, skipping frontend build. UI might be outdated.")
        return

    print("Building frontend...", flush=True)
    try:
        # Check dependencies
        if not (ui_path / "node_modules").exists():
            print("Installing frontend dependencies...", flush=True)
            subprocess.run(["npm", "install"], cwd=ui_path, check=True, capture_output=False)
        
        # Build
        subprocess.run(["npm", "run", "build"], cwd=ui_path, check=True, capture_output=False)
        print("Frontend build successful.", flush=True)
    except subprocess.CalledProcessError as e:
        print(f"Frontend build failed with exit code {e.returncode}.", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error during frontend build: {e}", file=sys.stderr)
        sys.exit(1)


def run_web():
    default_host = settings.KATRAIN_HOST
    default_port = settings.KATRAIN_PORT
    parser = argparse.ArgumentParser(description="Run KaTrain Web UI server")
    parser.add_argument(
        "--host",
        default=default_host,
        help="Host to bind the server to. Default: $KATRAIN_HOST or 0.0.0.0.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=default_port,
        help="Port to bind the server to. Default: $KATRAIN_PORT or 8001.",
    )
    parser.add_argument("--reload", action="store_true")
    parser.add_argument("--log-level", default="warning")
    parser.add_argument("--disable-engine", action="store_true")
    parser.add_argument("--ui", default=None, help="Interface mode to use. web (default) starts the FastAPI server, while desktop launches the Kivy GUI.")
    args, _unknown = parser.parse_known_args()

    # Build frontend if running in web mode and not explicitly disabled (could add flag later if needed)
    # We only build if we are actually starting the web server, or if --ui=web is explicit
    # However, create_app is used by uvicorn workers too, so we should be careful.
    # But run_web is the entry point.
    if not args.reload:  # Skip build in reload mode to avoid loops, or handle differently? 
        # Actually, user wants it on startup.
        build_frontend()

    import uvicorn

    host = args.host
    port = args.port
    
    # Configure uvicorn logging to reduce noise
    log_config = uvicorn.config.LOGGING_CONFIG
    log_config["formatters"]["default"]["fmt"] = "%(levelname)s:     %(message)s"
    log_config["formatters"]["access"]["fmt"] = "%(levelname)s:     %(message)s"

    print(f"\n" + "=" * 50, flush=True)
    print(f"Starting KaTrain Web UI", flush=True)
    if host == "0.0.0.0":
        print(f"Local access: http://127.0.0.1:{port}", flush=True)
        print(f"Network access: http://<your-ip-address>:{port}", flush=True)
    else:
        print(f"Access: http://{host}:{port}", flush=True)
    print("=" * 50 + "\n", flush=True)

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
