import argparse
import asyncio
import logging
import os
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any, List, Optional, Union, Dict

import numpy as np

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Depends
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager, contextmanager, nullcontext

from katrain.web.api.v1.api import api_router
from katrain.web.core.catalog_cache import add_catalog_cache_middleware
from katrain.web.core.config import settings
from katrain.web.core.ranked_session_guard import (
    guard_ai_ladder_ranked_owner,
    guard_ai_ladder_ranked_human_action,
    guard_ai_ladder_ranked_not_ended,
    guard_ai_ladder_ranked_session,
    guard_ai_ladder_ranked_ui_toggle,
    guard_ranked_vision_binding,
    guard_user_has_no_pending_ranked_game,
    is_ai_ladder_ranked_session,
    RankedAnalysisActivity,
    validate_ai_ladder_ranked_players,
)
from katrain.web.session import SessionManager, LobbyManager, Matchmaker
from katrain.web.models import *


def _json_safe(obj):
    """Recursively convert numpy scalars/arrays to native Python types.

    Vision events are built from numpy arrays (``np.where`` yields ``np.int64``
    coordinates). ``WebSocket.send_json`` uses the stdlib JSON encoder, which rejects
    numpy scalars — an unhandled encode error in the /ws/vision send loop silently
    kills the socket and freezes the kiosk. Sanitise every payload before sending so
    a numpy value in ANY event type can never take the socket down.
    """
    if isinstance(obj, dict):
        return {k: _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_json_safe(v) for v in obj]
    if isinstance(obj, np.generic):
        return obj.item()
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    return obj


@asynccontextmanager
async def lifespan(app: FastAPI):
    log = logging.getLogger("katrain_web")

    if settings.KATRAIN_MODE == "board":
        # ── Board mode startup (design.md Section 4.9) ──
        await _lifespan_board(app, log)
    else:
        # ── Server mode startup (existing logic, unchanged) ──
        await _lifespan_server(app, log)

    yield

    # ── Shutdown ──
    geometry_calibration = getattr(app.state, "geometry_calibration", None)
    if geometry_calibration:
        geometry_calibration.stop()

    # Vision service shutdown (board mode)
    vision = getattr(app.state, "vision", None)
    if vision:
        vision.stop()
    vision_poller = getattr(app.state, "vision_poller_task", None)
    if vision_poller:
        vision_poller.cancel()
    vision_pump = getattr(app.state, "vision_pump_task", None)
    if vision_pump:
        vision_pump.cancel()

    physical_play = getattr(app.state, "physical_play", None)
    if physical_play:
        await physical_play.shutdown()

    # LED service shutdown (board mode) — stop() does a final CLEAR! blackout.
    led_failsafe = getattr(app.state, "led_failsafe_task", None)
    if led_failsafe:
        led_failsafe.cancel()
    led = getattr(app.state, "led", None)
    if led:
        led.stop()

    # Capture service shutdown (board mode)
    capture = getattr(app.state, "capture", None)
    if capture:
        capture.stop()
    camera_hub = getattr(app.state, "camera_hub", None)
    if camera_hub:
        camera_hub.stop()

    if settings.KATRAIN_MODE == "board":
        connectivity = getattr(app.state, "connectivity_manager", None)
        if connectivity:
            await connectivity.stop()
        remote_client = getattr(app.state, "remote_client", None)
        if remote_client:
            await remote_client.close()
    else:
        live_service = getattr(app.state, "live_service", None)
        if live_service:
            await live_service.stop()
    task = getattr(app.state, "cleanup_task", None)
    if task:
        task.cancel()
    app.state.session_manager.cleanup_expired()


async def _lifespan_server(app: FastAPI, log):
    """Server mode initialization — existing logic, unchanged."""
    from katrain.web.core.auth import SQLAlchemyUserRepository, get_password_hash
    from katrain.web.core.game_repo import GameRepository
    from katrain.web.core.user_game_repo import UserGameRepository, UserGameAnalysisRepository
    from katrain.web.core.ai_ladder_ranked import AiLadderRankedRepository
    from katrain.web.core.db import SessionLocal

    repo = SQLAlchemyUserRepository(SessionLocal)
    repo.init_db()

    game_repo = GameRepository(SessionLocal)
    user_game_repo = UserGameRepository(SessionLocal)
    user_game_analysis_repo = UserGameAnalysisRepository(SessionLocal)
    ai_ladder_repo = AiLadderRankedRepository(SessionLocal)

    # Create default admin user if no users exist
    if not repo.list_users():
        log.info("No users found. Creating default admin user (admin/admin)")
        try:
            repo.create_user("admin", get_password_hash("admin"))
        except ValueError:
            pass  # Already exists race condition

    # Ensure the default 'admin' account carries the is_admin flag (billing admin).
    try:
        from katrain.web.core import models_db
        from katrain.web.core.db import SessionLocal as _SL

        _s = _SL()
        try:
            admin_row = _s.query(models_db.User).filter(models_db.User.username == "admin").one_or_none()
            if admin_row is not None and not admin_row.is_admin:
                admin_row.is_admin = True
                _s.commit()
                log.info("Marked default 'admin' account as is_admin=True")
        finally:
            _s.close()
    except Exception as e:  # pragma: no cover - defensive
        log.warning(f"Could not ensure admin flag: {e}")

    # Reconcile any credit reservations stuck after a previous crash.
    try:
        from katrain.web.core import billing
        from katrain.web.core.db import SessionLocal as _SL2

        _s2 = _SL2()
        try:
            billing.reconcile_stale_reservations(_s2, settings.BILLING_RESERVATION_TTL_SEC)
        finally:
            _s2.close()
    except Exception as e:  # pragma: no cover - defensive
        log.warning(f"Billing reconcile skipped: {e}")

    app.state.user_repo = repo
    app.state.game_repo = game_repo
    app.state.user_game_repo = user_game_repo
    app.state.user_game_analysis_repo = user_game_analysis_repo
    app.state.ai_ladder_repo = ai_ladder_repo
    app.state.ai_ladder_authoritative = True
    app.state.report_session_factory = SessionLocal
    app.state.lobby_manager = LobbyManager()
    app.state.matchmaker = Matchmaker()

    # Initialize Engine Clients and Router (cloud client attached iff CLOUD_KATAGO_URL set)
    from katrain.web.core.router import build_router

    app.state.router = build_router(settings.LOCAL_KATAGO_URL, settings.CLOUD_KATAGO_URL)

    manager = app.state.session_manager
    try:
        from katrain.web.interface import WebKaTrain

        kt = WebKaTrain(force_package_config=False, enable_engine=False)

        engine_cfg = kt.config("engine")
        if settings.LOCAL_KATAGO_URL and engine_cfg.get("http_url") != settings.LOCAL_KATAGO_URL:
            if engine_cfg.get("backend") == "http":
                print(f"Syncing KataGo URL to {settings.LOCAL_KATAGO_URL} from environment")
                kt.update_config("engine/http_url", settings.LOCAL_KATAGO_URL)
                kt.save_config("engine")
                engine_cfg = kt.config("engine")

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
        log.error(f"Initialization failed: {e}")

    manager.attach_loop(asyncio.get_running_loop())
    app.state.cleanup_task = asyncio.create_task(_cleanup_loop(manager))

    # Initialize Live Broadcasting Service
    from katrain.web.live import create_live_service

    live_service = create_live_service()
    app.state.live_service = live_service
    try:
        await live_service.start()
        log.info("Live broadcasting service started")
    except Exception as e:
        log.warning(f"Failed to start live service: {e}")

    # ── Tutorial Module (V2 — database-backed) ─────────────────────────────
    log.info("Tutorial V2: using database-backed tutorials")

    # ── Platform Manager (cross-platform online play) ─────────────────────
    _init_platform_manager(app, manager, log)


def _init_platform_manager(app, session_manager, log):
    """Initialize platform manager and adapters. Shared by both server and board modes."""
    from katrain.web.platforms.manager import PlatformManager
    from katrain.web.platforms.gateway import PlatformCommandGateway
    from katrain.web.platforms.credentials import PlatformCredentialStore

    platform_cred_store = PlatformCredentialStore()
    platform_manager = PlatformManager(session_manager, credential_store=platform_cred_store)
    app.state.platform_manager = platform_manager
    app.state.platform_gateway = PlatformCommandGateway(platform_manager, session_manager)

    # Engine-move failure recovery (Task 7, B5/M1/M4/m2): bounded retry + episode
    # tracking for the vision poller's platform/engine-play branch. Always wired up
    # (not gated on vision being enabled) so it's available uniformly wherever the
    # gateway is; the poller is the only consumer.
    from katrain.web.core.engine_recovery import EngineRecoveryConfig, EngineRecoveryTracker

    app.state.engine_recovery_config = EngineRecoveryConfig()
    app.state.engine_recovery = EngineRecoveryTracker(app.state.engine_recovery_config)

    for adapter_path, name in [
        ("katrain.web.platforms.ogs.adapter", "OGS"),
        ("katrain.web.platforms.fox.adapter", "Fox"),
        ("katrain.web.platforms.golaxy.adapter", "Golaxy"),
    ]:
        try:
            import importlib

            mod = importlib.import_module(adapter_path)
            adapter_cls = getattr(mod, f"{name}Adapter")
            platform_manager.register_adapter(adapter_cls())
            log.info(f"{name} platform adapter registered")
        except Exception as e:
            log.warning(f"Failed to register {name} adapter: {e}")


async def _lifespan_board(app: FastAPI, log):
    """Board mode initialization — design.md Section 4.9."""
    from functools import partial

    from katrain.web.core.auth import SQLAlchemyUserRepository
    from katrain.web.core.user_game_repo import UserGameRepository, UserGameAnalysisRepository
    from katrain.web.core.ai_ladder_ranked import AiLadderRankedRepository
    from katrain.web.core.tsumego_progress_repo import LocalTsumegoProgressRepository
    from katrain.web.core.db import SessionLocal
    from katrain.web.core.remote_client import RemoteAPIClient
    from katrain.web.core.sync_worker import SyncWorker
    from katrain.web.core.connectivity import ConnectivityManager
    from katrain.web.core.repository import (
        RepositoryDispatcher,
        RemoteTsumegoRepository,
        RemoteKifuRepository,
        RemoteUserGameRepository,
        enqueue_sync_item,
    )

    log.info(f"Starting in BOARD mode (device={settings.DEVICE_ID[:8]}..., remote={settings.REMOTE_API_URL})")

    # Local SQLite — create only the core tables needed for offline
    repo = SQLAlchemyUserRepository(SessionLocal)
    repo.init_db()
    app.state.user_repo = repo

    local_user_game_repo = UserGameRepository(SessionLocal)
    local_user_game_analysis_repo = UserGameAnalysisRepository(SessionLocal)
    local_tsumego_progress_repo = LocalTsumegoProgressRepository(SessionLocal)
    app.state.user_game_repo = local_user_game_repo
    app.state.user_game_analysis_repo = local_user_game_analysis_repo
    app.state.ai_ladder_repo = AiLadderRankedRepository(SessionLocal)
    # The board settles its own ranked games against its own SQLite. It has to: the game
    # is played by THIS box's KataGo, and /start creates the session on whichever node
    # serves it, so "authority elsewhere, engine here" is not a thing this design can
    # express. Cross-device rank still needs the settlement to reach the cloud — that is
    # the sync queue's job and is NOT wired yet, so a rank earned here is currently a
    # rank earned on this box.
    app.state.ai_ladder_authoritative = True
    app.state.tsumego_progress_repo = local_tsumego_progress_repo
    app.state.report_session_factory = SessionLocal

    # Remote API client
    remote_client = RemoteAPIClient(
        base_url=settings.REMOTE_API_URL,
        device_id=settings.DEVICE_ID,
        health_timeout=float(os.getenv("KATRAIN_HEALTH_CHECK_TIMEOUT", "10.0")),
    )
    app.state.remote_client = remote_client

    # Strict Box SSO receives remote tokens only through the authenticated
    # loopback bridge; it must never restore the retired device-wide credential.
    from katrain.web.core.box_sso import strict_box_sso_enabled

    if not strict_box_sso_enabled():
        try:
            from katrain.web.core.credentials import load_refresh_token

            saved_token = load_refresh_token(settings.DEVICE_ID)
            if saved_token:
                remote_client.set_refresh_token(saved_token)
                log.info("Restored refresh token from credentials store")
        except Exception as e:
            log.debug(f"No saved credentials: {e}")

    # Sync worker
    sync_worker = SyncWorker(SessionLocal, remote_client, ai_ladder_repo=app.state.ai_ladder_repo)
    sync_worker.recover_stale_leases()
    app.state.sync_worker = sync_worker

    # Connectivity manager
    connectivity = ConnectivityManager(remote_client, sync_worker)
    app.state.connectivity_manager = connectivity

    # Repository dispatcher
    sync_fn = partial(enqueue_sync_item, SessionLocal, device_id=settings.DEVICE_ID)
    # Also reachable outside the dispatcher: a ranked settlement is written by the
    # authoritative local path, not by the online/offline repository routing, but it
    # still has to reach the cloud through the same one queue.
    app.state.sync_enqueue_fn = sync_fn
    dispatcher = RepositoryDispatcher(
        connectivity_manager=connectivity,
        remote_tsumego=RemoteTsumegoRepository(remote_client),
        remote_kifu=RemoteKifuRepository(remote_client),
        remote_user_games=RemoteUserGameRepository(remote_client),
        local_user_game_repo=local_user_game_repo,
        sync_enqueue_fn=sync_fn,
        local_tsumego_progress_repo=local_tsumego_progress_repo,
        remote_client=remote_client,
    )
    app.state.repository_dispatcher = dispatcher

    # Engine: local KataGo for fast offline play; cloud attached iff CLOUD_KATAGO_URL is set
    # so AI 支招 (is_analysis) reaches the strong cloud GPU while play/领地/图表 stay local (Wave B #4).
    from katrain.web.core.router import build_router

    app.state.router = build_router(settings.LOCAL_KATAGO_URL, settings.CLOUD_KATAGO_URL)

    # Lobby/matchmaker placeholders (not used in board mode but needed by endpoints)
    app.state.lobby_manager = LobbyManager()
    app.state.matchmaker = Matchmaker()
    app.state.game_repo = None  # Multiplayer game_repo not used in board mode

    manager = app.state.session_manager
    try:
        from katrain.web.interface import WebKaTrain

        kt = WebKaTrain(force_package_config=False, enable_engine=False)
        engine_cfg = kt.config("engine")
        log.info(
            f"Board engine profile: max_visits={engine_cfg.get('max_visits')}, "
            f"fast_visits={engine_cfg.get('fast_visits')}, max_time={engine_cfg.get('max_time')}"
        )
    except Exception as e:
        log.error(f"Board mode initialization warning: {e}")

    manager.attach_loop(asyncio.get_running_loop())
    app.state.cleanup_task = asyncio.create_task(_cleanup_loop(manager))

    # Start connectivity monitoring (do NOT start live_service in board mode)
    connectivity.start()

    vision_config = getattr(settings, "_vision_config", None)
    capture_config = getattr(settings, "_capture_config", None)

    # Initialise every optional camera-dependent surface before attempting to
    # acquire the device. A missing UVC device must leave the regular board
    # (including LEDs and kiosk play) available rather than aborting lifespan.
    app.state.camera_hub = None
    app.state.vision = None
    app.state.vision_ws_clients = {}
    app.state.vision_move_queue = None
    app.state.vision_pump_task = None
    app.state.vision_poller_task = None
    app.state.capture = None
    app.state.geometry = None
    app.state.geometry_calibration = None
    app.state.physical_play = None
    app.state.physical_play_config = None

    # One physical camera owner shared by capture, calibration, and recognition.
    camera_hub = None
    if (vision_config and vision_config.enabled) or (capture_config and capture_config.enabled):
        from katrain.web.core.camera_hub import CameraHub, CameraHubConfig

        if vision_config and vision_config.enabled and capture_config and capture_config.enabled:
            vision_camera = (vision_config.camera_device, vision_config.camera_width, vision_config.camera_height)
            capture_camera = (capture_config.camera_device, capture_config.width, capture_config.height)
            if vision_camera != capture_camera:
                raise RuntimeError(
                    "Vision and capture must use the same camera device and resolution when sharing CameraHub: "
                    f"vision={vision_camera}, capture={capture_camera}"
                )
        if capture_config and capture_config.enabled:
            hub_config = CameraHubConfig(
                device_id=capture_config.camera_device,
                width=capture_config.width,
                height=capture_config.height,
                lock_exposure=capture_config.lock_exposure,
                exposure=capture_config.exposure,
                lock_awb=capture_config.lock_awb,
            )
        else:
            hub_config = CameraHubConfig(
                device_id=vision_config.camera_device,
                width=vision_config.camera_width,
                height=vision_config.camera_height,
                lock_exposure=False,
                lock_awb=False,
            )
        camera_hub = CameraHub(hub_config)
        try:
            camera_hub.start()
        except RuntimeError as exc:
            # CameraHub uses this error only when CameraManager cannot open the
            # configured device. Preserve every other RuntimeError as a startup
            # failure (including future non-device configuration defects).
            if not str(exc).startswith("Failed to open camera "):
                raise
            log.warning(
                "Camera unavailable; continuing without vision, capture, calibration, or physical play: %s", exc
            )
            camera_hub = None
    app.state.camera_hub = camera_hub

    # Vision service (optional — enabled when --vision-model is provided)
    if vision_config and vision_config.enabled and camera_hub is not None:
        from katrain.vision.service import VisionService

        vision = VisionService(vision_config, frame_source=camera_hub)
        vision.start()
        app.state.vision = vision
        app.state.vision_ws_clients = {}
        app.state.vision_move_queue = asyncio.Queue()
        app.state.vision_pump_task = asyncio.create_task(_vision_event_pump(app))
        app.state.vision_poller_task = asyncio.create_task(_vision_move_poller(app))
        log.info("Vision service started (backend=%s)", vision_config.backend)
    else:
        app.state.vision = None

    # LED service (optional — enabled when --led-serial-port is provided)
    led_config = getattr(settings, "_led_config", None)
    if led_config and led_config.enabled:
        from katrain.web.core.led_service import LedService

        led = LedService(led_config)
        led.start()
        app.state.led = led
        app.state.led_last_activity = time.monotonic()
        app.state.led_failsafe_task = asyncio.create_task(_led_failsafe_loop(app))
        log.info("LED service started (port=%s)", led_config.serial_port)
    else:
        app.state.led = None

    # Physical-play orchestrator: drives game LEDs from authoritative state
    # (track kiosk-physical-play; requires vision, LED optional/degraded-tolerant)
    if app.state.vision is not None:
        from katrain.web.core.physical_play import PhysicalPlayConfig
        from katrain.web.core.physical_play_orchestrator import PhysicalPlayOrchestrator

        pp_config = getattr(settings, "_physical_play_config", None) or PhysicalPlayConfig()
        app.state.physical_play_config = pp_config
        app.state.physical_play = PhysicalPlayOrchestrator(
            config=pp_config,
            led=app.state.led,
            vision=app.state.vision,
            session_manager=manager,
            touch_led_activity=lambda: setattr(app.state, "led_last_activity", time.monotonic()),
        )

        from katrain.web.core.hint_gate import DefaultHintGate

        app.state.hint_gate = DefaultHintGate(pp_config.hint_engine)
        log.info("Physical-play orchestrator ready (hint_engine=%s)", pp_config.hint_engine)
    else:
        app.state.physical_play = None
        app.state.physical_play_config = None

    # Capture service consumes the shared CameraHub and only owns file output.
    if capture_config and capture_config.enabled and camera_hub is not None:
        from katrain.web.core.capture_service import CaptureService

        capture = CaptureService(capture_config, hub=camera_hub)
        capture.start()
        app.state.capture = capture
        # P12: default "auto" = no-LED outer-corner per-move geometry (passive, zero LED for
        # geometry). "every-move" (LED fiducial, sub-pixel) is opt-in for high-quality TRAINING
        # capture; "off" disables. Select via --baipu-fiducial-mode or $KATRAIN_BAIPU_FIDUCIAL_MODE.
        # NOTE: real-hardware crowded-board accuracy of "auto" is gated by P12 Task 9 (待硬件).
        from katrain.web.core.baipu_capture import resolve_fiducial_mode

        app.state.baipu_fiducial_mode = resolve_fiducial_mode(
            getattr(settings, "_baipu_fiducial_mode", None), os.getenv("KATRAIN_BAIPU_FIDUCIAL_MODE")
        )
        app.state.baipu_drift_threshold_cells = getattr(settings, "baipu_drift_threshold_cells", 0.15)
        # Load an existing geometry lock if present (so capture/QA can run immediately).
        try:
            from katrain.vision.geometry_lock import load_geometry_lock

            geo_path = Path("~/.katrain/geometry_lock.npz").expanduser()
            app.state.geometry = load_geometry_lock(geo_path) if geo_path.exists() else None
        except Exception as e:
            log.warning("Failed to load geometry lock: %s", e)
            app.state.geometry = None
        log.info("Capture service started (camera=%s)", capture_config.camera_device)
    else:
        app.state.capture = None
        app.state.geometry = None

    # Calibration service needs only the camera: confirm-existing/promote and drift monitoring
    # run without an LED (no-LED geometry is a supported primary path). LED is required only for
    # a full LED-anchor RE-calibration (start() guards that).
    if app.state.capture is not None:
        from katrain.web.core.geometry_calibration_service import GeometryCalibrationService

        def promote_geometry(lock):
            app.state.geometry = lock
            vision_service = getattr(app.state, "vision", None)
            if vision_service is not None and hasattr(vision_service, "set_geometry"):
                vision_service.set_geometry(lock)

        def invalidate_geometry():
            # Drift mid-session (board/camera bumped): drop the stale warp so recognition_ready
            # falls and physical surfaces stop judging on a wrong grid until re-calibration.
            app.state.geometry = None
            vision_service = getattr(app.state, "vision", None)
            if vision_service is not None and hasattr(vision_service, "set_geometry"):
                vision_service.set_geometry(None)

        def suspend_vision():
            # For the duration of a calibration run, stop the RKNN worker's warp+CLAHE+detect
            # (~1 core) — it would otherwise recognise a board being re-locked, starving the
            # calibration compute + status poll + kiosk UI. Unlike invalidate_geometry this keeps
            # app.state.geometry as the fallback that resume_vision re-arms the worker with.
            vision_service = getattr(app.state, "vision", None)
            if vision_service is not None and hasattr(vision_service, "set_geometry"):
                vision_service.set_geometry(None)

        def resume_vision():
            vision_service = getattr(app.state, "vision", None)
            if vision_service is not None and hasattr(vision_service, "set_geometry"):
                vision_service.set_geometry(app.state.geometry)

        app.state.geometry_calibration = GeometryCalibrationService(
            led=app.state.led,
            capture=app.state.capture,
            save_path=Path("~/.katrain/geometry_lock.npz").expanduser(),
            initial_lock=app.state.geometry,
            on_success=promote_geometry,
            on_degraded=invalidate_geometry,
            on_suspend=suspend_vision,
            on_resume=resume_vision,
        )
    else:
        app.state.geometry_calibration = None

    # Push a persisted geometry lock into the vision worker at startup. Without this,
    # recognition silently lacks geometry after every server restart (the calibration
    # service already reports locked=true from the same file) until the user manually
    # recalibrates on the setup page.
    if app.state.geometry is not None and app.state.vision is not None:
        app.state.vision.set_geometry(app.state.geometry)

    # Platform manager for cross-platform online play (shared init)
    _init_platform_manager(app, manager, log)

    log.info("Board mode initialization complete")


def create_app(enable_engine=True, session_timeout=None, max_sessions=None):
    from katrain.web.api.v1.endpoints.auth import get_current_user, get_current_user_optional

    if session_timeout is None:
        session_timeout = settings.SESSION_TIMEOUT
    if max_sessions is None:
        max_sessions = settings.MAX_SESSIONS
    # Set logging levels for our application
    logging.getLogger("katrain_web").setLevel(logging.INFO)

    app = FastAPI(lifespan=lifespan)
    app.state.ranked_analysis_activity = RankedAnalysisActivity()

    @contextmanager
    def persistent_analysis_activity(current_user, session, kind: str, action: str):
        activity = app.state.ranked_analysis_activity
        with activity.lock:
            guard_user_has_no_pending_ranked_game(app, current_user, action)
            activity.begin_background(current_user.id, session.session_id, kind)
            try:
                yield
                guard_user_has_no_pending_ranked_game(app, current_user, action)
            except Exception:
                activity.end_background(current_user.id, session.session_id, kind)
                raise

    def register_persistent_analysis(current_user, session, kind: str, action: str) -> None:
        activity = app.state.ranked_analysis_activity
        with activity.lock:
            guard_user_has_no_pending_ranked_game(app, current_user, action)
            activity.begin_background(current_user.id, session.session_id, kind)
            guard_user_has_no_pending_ranked_game(app, current_user, action)

    def guard_session_reader(session, current_user, action: str) -> None:
        if current_user is None:
            raise HTTPException(status_code=401, detail=f"Authentication required for {action}")
        allowed_user_ids = {
            user_id for user_id in (session.user_id, session.player_b_id, session.player_w_id) if user_id is not None
        }
        if current_user.id not in allowed_user_ids:
            raise HTTPException(status_code=403, detail=f"{action} is restricted to a session participant")

    from katrain.web.core.box_sso import BoxSSOState

    app.state.box_sso = BoxSSOState(settings.KATRAIN_BOX_SSO_BRIDGE_KEY_PATH)
    app.include_router(api_router, prefix="/api/v1")
    add_catalog_cache_middleware(app)
    # Board mode serves the kiosk-2d bundle (board-proxy API base, no three.js);
    # the full server serves the complete build. Both emit index.html + /assets,
    # so we point the SPA routes + root mount at the matching directory.
    static_dirname = "static-kiosk-2d" if settings.KATRAIN_MODE == "board" else "static"
    static_root = Path(__file__).resolve().parent / static_dirname
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
    def create_session(current_user: User = Depends(get_current_user_optional), mode: str = "play"):
        try:
            katago_uuid = current_user.uuid if current_user else None
            if current_user is None:
                # Anonymous shells remain available for compatibility, but must not start
                # analysis that could later be harvested through an authenticated session.
                session = manager.create_session(skip_initial_analysis=True)
            else:
                with app.state.ranked_analysis_activity.lock:
                    guard_user_has_no_pending_ranked_game(app, current_user, "session analysis")
                    if mode == "research":
                        session = manager.create_research_session(user_id=current_user.id, katago_uuid=katago_uuid)
                    else:
                        session = manager.create_session(katago_uuid=katago_uuid, user_id=current_user.id)
                    app.state.ranked_analysis_activity.begin_background(current_user.id, session.session_id, "initial")
                    guard_user_has_no_pending_ranked_game(app, current_user, "session analysis")
        except HTTPException:
            raise
        except Exception as exc:
            logging.getLogger("katrain_web").error(f"API: create_session failed: {exc}")
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        return {"session_id": session.session_id, "state": session.last_state, "mode": session.mode}

    @app.delete("/api/session/{session_id}")
    def delete_session(session_id: str, current_user: User = Depends(get_current_user_optional)):
        try:
            session = manager.get_session(session_id)
            guard_ai_ladder_ranked_session(session, "delete-session")
            # Only allow owner to delete research sessions
            if session.mode == "research" and current_user and session.user_id != current_user.id:
                raise HTTPException(status_code=403, detail="Not authorized")
            app.state.ranked_analysis_activity.end_session(session.session_id)
            manager.remove_session(session_id)
        except KeyError:
            pass  # Already gone, that's fine
        return {"status": "deleted"}

    @app.get("/api/state")
    def get_state(session_id: str, current_user: User = Depends(get_current_user)):
        try:
            session = manager.get_session(session_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Session not found") from exc
        guard_session_reader(session, current_user, "session state")
        if not is_ai_ladder_ranked_session(session):
            guard_user_has_no_pending_ranked_game(app, current_user, "session state")
        state = session.last_state or session.katrain.get_state()
        if not is_ai_ladder_ranked_session(session):
            guard_user_has_no_pending_ranked_game(app, current_user, "session state")
        return {"session_id": session.session_id, "state": state}

    @app.post("/api/move")
    async def play_move(request: MoveRequest, current_user: User = Depends(get_current_user_optional)):
        session = _get_session_or_404(manager, request.session_id)
        guard_ai_ladder_ranked_human_action(session, current_user, "play-move")
        tracks_auto_analysis = not is_ai_ladder_ranked_session(session) and bool(
            getattr(session.katrain, "analysis_allowed", True)
        )
        if tracks_auto_analysis:
            if current_user is None:
                raise HTTPException(status_code=401, detail="Authentication required for analyzed games")
            guard_session_reader(session, current_user, "play move")

        # Skip turn validation for research sessions
        # Enforce Multiplayer Turns (only if this is a multiplayer session)
        if session.mode != "research" and (session.player_b_id is not None or session.player_w_id is not None):
            # This is a multiplayer game - require authentication and turn check
            if current_user is None:
                raise HTTPException(status_code=401, detail="Authentication required for multiplayer games")
            state = session.katrain.get_state()
            next_player = state["player_to_move"]
            allowed_user_id = session.player_b_id if next_player == "B" else session.player_w_id
            if current_user.id != allowed_user_id:
                raise HTTPException(status_code=403, detail="Not your turn")

        coords = None if request.pass_move else request.coords
        if coords is None and not request.pass_move:
            raise HTTPException(status_code=400, detail="coords required unless pass_move is true")

        # Route through platform gateway for cross-platform games
        gateway = getattr(app.state, "platform_gateway", None)
        if gateway and gateway.is_platform_game(request.session_id):
            from katrain.web.platforms.gateway import PlatformMoveRejectedError

            try:
                user_id = current_user.id if current_user else 0
                with persistent_analysis_activity(current_user, session, "move", "move analysis"):
                    if request.pass_move:
                        await gateway.pass_move(request.session_id, user_id)
                    else:
                        await gateway.play_move(request.session_id, coords[0], coords[1], user_id)
                    state = session.katrain.get_state()
                    session.last_state = state
                    return {"session_id": session.session_id, "state": state}
            except PlatformMoveRejectedError as e:
                raise HTTPException(status_code=409, detail=str(e))

        analysis_context = (
            persistent_analysis_activity(current_user, session, "move", "move analysis")
            if tracks_auto_analysis
            else nullcontext()
        )
        with analysis_context:
            with session.lock:
                guard_ai_ladder_ranked_human_action(session, current_user, "play-move")
                session.katrain("play", None if coords is None else tuple(coords))
                state = session.katrain.get_state()
                session.last_state = state
        # Natural (two-pass) game end never hits resign/count/timeout — record here so
        # local face-to-face games ending by both passing are still saved (end_result
        # auto-becomes truthy on two consecutive passes; requestCount then refuses).
        is_multiplayer = session.player_b_id is not None or session.player_w_id is not None
        if state.get("end_result") and not is_multiplayer and current_user and session.user_id:
            await _record_ai_game(session, app, current_user, state["end_result"])
        return {"session_id": session.session_id, "state": state}

    @app.post("/api/undo")
    def undo_move(request: UndoRedoRequest, current_user: User | None = Depends(get_current_user_optional)):
        session = _get_session_or_404(manager, request.session_id)
        guard_ai_ladder_ranked_session(session, "undo")
        if session.mode == "play" and getattr(session.katrain, "game_type", "free") in ("rated", "ranked"):
            raise HTTPException(status_code=403, detail="undo not allowed in ranked games")
        guard_session_reader(session, current_user, "undo")
        register_persistent_analysis(current_user, session, "undo", "undo analysis")
        _guard_engine_move_pending(app, request.session_id)
        with session.lock:
            session.katrain("undo", request.n_times)
            state = session.katrain.get_state()
            session.last_state = state
        return {"session_id": session.session_id, "state": state}

    @app.post("/api/redo")
    def redo_move(request: UndoRedoRequest, current_user: User | None = Depends(get_current_user_optional)):
        session = _get_session_or_404(manager, request.session_id)
        guard_ai_ladder_ranked_session(session, "redo")
        if session.mode == "play" and getattr(session.katrain, "game_type", "free") in ("rated", "ranked"):
            raise HTTPException(status_code=403, detail="redo not allowed in ranked games")
        guard_session_reader(session, current_user, "redo")
        register_persistent_analysis(current_user, session, "redo", "redo analysis")
        _guard_engine_move_pending(app, request.session_id)
        with session.lock:
            session.katrain("redo", request.n_times)
            state = session.katrain.get_state()
            session.last_state = state
        return {"session_id": session.session_id, "state": state}

    @app.get("/api/sgf/save")
    def save_sgf(session_id: str, current_user: User = Depends(get_current_user_optional)):
        session = _get_session_or_404(manager, session_id)
        if is_ai_ladder_ranked_session(session):
            guard_ai_ladder_ranked_owner(session, current_user, "save-sgf")
            if not getattr(session, "_recorded", False) or getattr(session, "ai_ladder_settlement_pending", False):
                raise HTTPException(status_code=403, detail="SGF is unavailable until ranked settlement completes")
        with session.lock:
            sgf = session.katrain.get_sgf()
        return {"sgf": sgf}

    @app.post("/api/sgf/load")
    def load_sgf(request: LoadSGFRequest, current_user: User | None = Depends(get_current_user_optional)):
        session = _get_session_or_404(manager, request.session_id)
        guard_ai_ladder_ranked_session(session, "load-sgf")
        guard_session_reader(session, current_user, "load SGF")
        guard_user_has_no_pending_ranked_game(app, current_user, "SGF analysis")
        if not request.skip_analysis:
            register_persistent_analysis(current_user, session, "load-sgf", "SGF analysis")
        with session.lock:
            session.katrain("load_sgf", request.sgf, skip_initial_analysis=request.skip_analysis)
            state = session.katrain.get_state()
            session.last_state = state
        return {"session_id": session.session_id, "state": state}

    @app.post("/api/new-game")
    def new_game(request: NewGameRequest, current_user: User = Depends(get_current_user)):
        session = _get_session_or_404(manager, request.session_id)
        guard_ai_ladder_ranked_session(session, "new-game")
        guard_session_reader(session, current_user, "new game")
        # Task 4: validate the rung BEFORE touching the session, so an out-of-range value
        # 422s cleanly instead of partially mutating game state.
        if request.ladder_rung is not None:
            from katrain.core.ladder import resolve_available_rung

            try:
                resolve_available_rung(request.ladder_rung)
            except (ValueError, TypeError):
                raise HTTPException(status_code=422, detail=f"invalid ladder_rung: {request.ladder_rung}")

        app.state.ranked_analysis_activity.end_session(session.session_id)
        with persistent_analysis_activity(current_user, session, "new-game", "new game analysis"):
            with session.lock:
                session.game_ended = False
                # A new game is starting: clear the "already recorded" guard from any
                # previous game on this (possibly reused) session so it becomes recordable again.
                session._recorded = False
                # This endpoint carries no game_type, so the game it starts is a free one.
                # Leaving the previous game's type on the session is how a casual game
                # played right after a 升降级对弈 game would keep forbidding analysis and
                # undo. `_do_new_game` resets its own copy the same way.
                session.game_type = "free"
                if request.players:
                    for bw, p in request.players.items():
                        session.katrain(
                            "update_player",
                            bw=bw,
                            player_type=p.player_type,
                            player_subtype=p.player_subtype,
                            name=p.name,
                        )
                        if p.name:
                            session.katrain.game.root.set_property("P" + bw, p.name)
                if request.clear_cache:
                    session.katrain.engine.on_new_game()

                session.katrain(
                    "new_game",
                    size=request.size,
                    handicap=request.handicap,
                    komi=request.komi,
                    rules=request.rules,
                    ladder_rung=request.ladder_rung,
                )
                state = session.katrain.get_state()
                session.last_state = state
        return {"session_id": session.session_id, "state": state}

    @app.post("/api/game/setup")
    def game_setup(request: GameSettingsRequest, current_user: User | None = Depends(get_current_user_optional)):
        session = _get_session_or_404(manager, request.session_id)
        guard_ai_ladder_ranked_session(session, "game-setup")
        guard_session_reader(session, current_user, "game setup")
        app.state.ranked_analysis_activity.end_session(session.session_id)
        register_persistent_analysis(current_user, session, "game-setup", "game setup analysis")
        mode = request.mode
        settings = request.settings
        with session.lock:
            session.game_ended = False
            # A (re)configured game is starting: clear the "already recorded" guard from
            # any previous game on this (possibly reused) session so it becomes recordable again.
            session._recorded = False
            # Update players
            players = settings.get("players")
            if players:
                for bw, p in players.items():
                    session.katrain(
                        "update_player",
                        bw=bw,
                        player_type=p["player_type"],
                        player_subtype=p["player_subtype"],
                        name=p.get("name"),
                    )
                    if p.get("name"):
                        session.katrain.game.root.set_property("P" + bw, p["name"])

            if mode == "newgame" or mode == "setupposition":
                if settings.get("clear_cache"):
                    session.katrain.engine.on_new_game()
                session.katrain(
                    "new_game", size=settings.get("size"), handicap=settings.get("handicap"), komi=settings.get("komi")
                )
                if mode == "setupposition":
                    session.katrain(
                        "selfplay_setup",
                        until_move=settings.get("setup_move"),
                        target_b_advantage=settings.get("setup_advantage"),
                    )
            elif mode == "editgame":
                session.katrain(
                    "_do_edit_game",
                    size=settings.get("size"),
                    handicap=settings.get("handicap"),
                    komi=settings.get("komi"),
                    rules=settings.get("rules"),
                )
            elif mode in ("free", "ranked"):
                # Kiosk human-vs-AI game setup
                color = settings.get("color", "black")
                human_bw = "B" if color == "black" else "W"
                ai_bw = "W" if color == "black" else "B"
                ai_strategy = settings.get("ai_strategy", "ai:default")
                rank_slider = int(settings.get("rank", 14))  # 0-28 slider value

                # Set human player name from logged-in user
                human_name = current_user.username if current_user else ""
                session.katrain(
                    "update_player",
                    bw=human_bw,
                    player_type="player:human",
                    player_subtype="player:human",
                    name=human_name,
                )
                session.katrain("update_player", bw=ai_bw, player_type="player:ai", player_subtype=ai_strategy)

                # Store game_type on session for auto-save at game end
                session.game_type = mode

                if ai_strategy == "ai:human":
                    session.katrain.update_config(f"ai/ai:human/human_kyu_rank", 20 - rank_slider)
                else:
                    session.katrain.update_config(f"ai/{ai_strategy}/kyu_rank", rank_slider - 19)

                time_enabled = settings.get("time_enabled", False)
                if time_enabled:
                    session.katrain.update_config("timer/main_time", settings.get("main_time", 0))
                    session.katrain.update_config("timer/byo_length", settings.get("byo_length", 30))
                    session.katrain.update_config("timer/byo_periods", settings.get("byo_periods", 3))
                    session.katrain.update_config("timer/paused", False)
                else:
                    session.katrain.update_config("timer/main_time", 0)
                    session.katrain.update_config("timer/byo_length", 0)
                    session.katrain.update_config("timer/paused", True)

                session.katrain(
                    "new_game",
                    size=settings.get("board_size", 19),
                    handicap=settings.get("handicap", 0),
                    komi=settings.get("komi", 6.5),
                    rules=settings.get("rules", "japanese"),
                    game_type=mode,  # R3/R5: rated/ranked games forbid analysis (anti-cheat)
                )

            elif mode == "pvp_local":
                # Two humans face-to-face on one kiosk. Explicitly force BOTH seats to
                # player:human — reset_players preserves prior player_type, so a session
                # recycled from a previous AI game could leave a stale player:ai seat that
                # would wrongly auto-trigger genmove after the first human (vision) move.
                black_name = settings.get("black_name") or ""
                white_name = settings.get("white_name") or ""
                session.katrain(
                    "update_player",
                    bw="B",
                    player_type="player:human",
                    player_subtype="player:human",
                    name=black_name,
                )
                session.katrain(
                    "update_player",
                    bw="W",
                    player_type="player:human",
                    player_subtype="player:human",
                    name=white_name,
                )
                session.game_type = "pvp_local"

                time_enabled = settings.get("time_enabled", False)
                if time_enabled:
                    session.katrain.update_config("timer/main_time", settings.get("main_time", 0))
                    session.katrain.update_config("timer/byo_length", settings.get("byo_length", 30))
                    session.katrain.update_config("timer/byo_periods", settings.get("byo_periods", 3))
                    session.katrain.update_config("timer/paused", False)
                else:
                    session.katrain.update_config("timer/main_time", 0)
                    session.katrain.update_config("timer/byo_length", 0)
                    session.katrain.update_config("timer/paused", True)

                session.katrain(
                    "new_game",
                    size=settings.get("board_size", 19),
                    handicap=settings.get("handicap", 0),
                    komi=settings.get("komi", 7.5),
                    rules=settings.get("rules", "chinese"),
                    game_type="pvp_local",
                )
                if black_name:
                    session.katrain.game.root.set_property("PB", black_name)
                if white_name:
                    session.katrain.game.root.set_property("PW", white_name)

            state = session.katrain.get_state()
            session.last_state = state
        return {"session_id": session.session_id, "state": state}

    @app.post("/api/edit-game")
    def edit_game(request: EditGameRequest, current_user: User | None = Depends(get_current_user_optional)):
        session = _get_session_or_404(manager, request.session_id)
        guard_ai_ladder_ranked_session(session, "edit-game")
        guard_session_reader(session, current_user, "edit game")
        register_persistent_analysis(current_user, session, "edit-game", "edit game analysis")
        with session.lock:
            session.katrain(
                "edit_game", size=request.size, handicap=request.handicap, komi=request.komi, rules=request.rules
            )
            state = session.katrain.get_state()
            session.last_state = state
        return {"session_id": session.session_id, "state": state}

    @app.post("/api/nav")
    def navigate(request: NavRequest, current_user: User = Depends(get_current_user_optional)):
        session = _get_session_or_404(manager, request.session_id)
        guard_ai_ladder_ranked_session(session, "navigate")
        _guard_engine_move_pending(app, request.session_id)
        gateway = getattr(app.state, "platform_gateway", None)
        is_platform_game = gateway and gateway.is_platform_game(request.session_id)
        is_native_multiplayer = not is_platform_game and (
            isinstance(session.player_b_id, int) or isinstance(session.player_w_id, int)
        )

        with session.lock:
            if is_native_multiplayer:
                if not session.game_ended:
                    current_state = session.katrain.get_state()
                    session.game_ended = bool(current_state.get("end_result"))
                if not session.game_ended:
                    raise HTTPException(status_code=409, detail="navigation disabled during active multiplayer game")
                if current_user is None:
                    raise HTTPException(status_code=401, detail="Authentication required for multiplayer navigation")

        # Anonymous sessions are created without initial analysis and remain usable for
        # legacy/plain navigation. Authenticated navigation retains the ranked-analysis
        # lease so an in-flight free-session analysis cannot race a ranked start.
        if current_user is None:
            with session.lock:
                session.katrain("nav", request.node_id)
                state = session.katrain.get_state()
                session.last_state = state
        else:
            allowed_user_ids = {
                user_id
                for user_id in (session.user_id, session.player_b_id, session.player_w_id)
                if isinstance(user_id, int) and user_id > 0
            }
            if allowed_user_ids and current_user.id not in allowed_user_ids:
                raise HTTPException(status_code=403, detail="navigation is restricted to a session participant")
            with persistent_analysis_activity(current_user, session, "nav", "navigation analysis"):
                with session.lock:
                    session.katrain("nav", request.node_id)
                    state = session.katrain.get_state()
                    session.last_state = state
        return {"session_id": session.session_id, "state": state}

    @app.post("/api/ai-move")
    def ai_move(request: UndoRedoRequest, current_user: User | None = Depends(get_current_user_optional)):
        session = _get_session_or_404(manager, request.session_id)
        guard_ai_ladder_ranked_session(session, "ai-move")
        guard_session_reader(session, current_user, "AI move")
        # Unconditional (not just while pending): this path bypasses the Golaxy
        # genmove tunnel entirely and triggers local KataGo directly, which is never
        # valid for an engine-play game (review D5/Task 0 inventory).
        gateway = getattr(app.state, "platform_gateway", None)
        if gateway and gateway.is_engine_game(request.session_id):
            raise HTTPException(status_code=403, detail="ai-move not allowed for engine-play sessions")
        register_persistent_analysis(current_user, session, "ai-move", "AI move analysis")
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
        guard_ai_ladder_ranked_session(session, "update-config")
        with session.lock:
            session.katrain.update_config(request.setting, request.value)
            state = session.katrain.get_state()
            session.last_state = state
        return {"session_id": session.session_id, "state": state}

    @app.post("/api/config/bulk")
    def update_config_bulk(request: ConfigBulkUpdateRequest):
        session = _get_session_or_404(manager, request.session_id)
        guard_ai_ladder_ranked_session(session, "update-config-bulk")
        with session.lock:
            for setting, value in request.updates.items():
                session.katrain.update_config(setting, value)
            state = session.katrain.get_state()
            session.last_state = state
        return {"session_id": session.session_id, "state": state}

    @app.post("/api/player")
    def update_player(request: UpdatePlayerRequest):
        session = _get_session_or_404(manager, request.session_id)
        guard_ai_ladder_ranked_session(session, "update-player")
        with session.lock:
            session.katrain(
                "update_player",
                bw=request.bw,
                player_type=request.player_type,
                player_subtype=request.player_subtype,
                name=request.name,
            )
            state = session.katrain.get_state()
            session.last_state = state
        return {"session_id": session.session_id, "state": state}

    @app.post("/api/player/swap")
    def swap_players(request: ToggleAnalysisRequest):
        session = _get_session_or_404(manager, request.session_id)
        guard_ai_ladder_ranked_session(session, "swap-players")
        with session.lock:
            session.katrain("swap_players")
            state = session.katrain.get_state()
            session.last_state = state
        return {"session_id": session.session_id, "state": state}

    @app.post("/api/analysis/continuous")
    def toggle_continuous_analysis(request: ToggleAnalysisRequest, current_user: User = Depends(get_current_user)):
        session = _get_session_or_404(manager, request.session_id)
        guard_ai_ladder_ranked_session(session, "continuous-analysis")
        activity = app.state.ranked_analysis_activity
        with activity.lock:
            guard_user_has_no_pending_ranked_game(app, current_user, "continuous analysis")
            with session.lock:
                session.katrain.pondering = not session.katrain.pondering
                session.katrain.update_state()
                state = session.katrain.get_state()
                session.last_state = state
            if session.katrain.pondering:
                activity.begin_background(current_user.id, session.session_id, "continuous")
            else:
                activity.end_background(current_user.id, session.session_id, "continuous")
            guard_user_has_no_pending_ranked_game(app, current_user, "continuous analysis")
        return {"session_id": session.session_id, "state": state, "pondering": session.katrain.pondering}

    @app.post("/api/analysis/current")
    def analyze_current(request: ToggleAnalysisRequest, current_user: User = Depends(get_current_user)):
        """On-demand analysis of the current position (kiosk 领地/图表). Free games only —
        the interface chokepoint (ANALYSIS_ACTIONS) makes this a no-op in rated/ranked. The
        analysis itself streams back asynchronously over the game WebSocket, so this returns
        the current (possibly not-yet-analyzed) state immediately."""
        session = _get_session_or_404(manager, request.session_id)
        guard_ai_ladder_ranked_session(session, "current-analysis")
        with persistent_analysis_activity(current_user, session, "current", "current analysis"):
            with session.lock:
                session.katrain("analyze_current")
                state = session.katrain.get_state()
                session.last_state = state
        return {"session_id": session.session_id, "state": state}

    @app.post("/api/analysis/extra")
    def analyze_extra(request: AnalyzeExtraRequest, current_user: User = Depends(get_current_user)):
        session = _get_session_or_404(manager, request.session_id)
        guard_ai_ladder_ranked_session(session, "extra-analysis")
        with persistent_analysis_activity(current_user, session, "extra", "extra analysis"):
            with session.lock:
                kwargs = request.kwargs or {}
                session.katrain("analyze_extra", mode=request.mode, **kwargs)
                state = session.katrain.get_state()
                session.last_state = state
        return {"session_id": session.session_id, "state": state}

    @app.post("/api/analysis/show-pv")
    def show_pv(request: PVRequest, current_user: User = Depends(get_current_user)):
        guard_user_has_no_pending_ranked_game(app, current_user, "analysis PV")
        session = _get_session_or_404(manager, request.session_id)
        guard_ai_ladder_ranked_session(session, "show-analysis-pv")
        with session.lock:
            session.katrain("_do_show_pv", request.pv)
            state = session.katrain.get_state()
            session.last_state = state
        guard_user_has_no_pending_ranked_game(app, current_user, "analysis PV")
        return {"session_id": session.session_id, "state": state}

    @app.post("/api/analysis/clear-pv")
    def clear_pv(request: ToggleAnalysisRequest, current_user: User = Depends(get_current_user)):
        guard_user_has_no_pending_ranked_game(app, current_user, "analysis PV")
        session = _get_session_or_404(manager, request.session_id)
        guard_ai_ladder_ranked_session(session, "clear-analysis-pv")
        with session.lock:
            session.katrain("_do_clear_pv")
            state = session.katrain.get_state()
            session.last_state = state
        guard_user_has_no_pending_ranked_game(app, current_user, "analysis PV")
        return {"session_id": session.session_id, "state": state}

    @app.post("/api/mode")
    def set_mode(request: ModeRequest, current_user: User | None = Depends(get_current_user_optional)):
        if request.mode != "play":
            if current_user is None:
                raise HTTPException(status_code=401, detail="Authentication required for analysis mode")
            guard_user_has_no_pending_ranked_game(app, current_user, "analysis mode")
        session = _get_session_or_404(manager, request.session_id)
        guard_ai_ladder_ranked_session(session, "set-mode")
        with session.lock:
            session.katrain.play_analyze_mode = request.mode
            session.katrain.update_state()
            state = session.katrain.get_state()
            session.last_state = state
        if request.mode != "play":
            guard_user_has_no_pending_ranked_game(app, current_user, "analysis mode")
        return {"session_id": session.session_id, "state": state, "mode": session.katrain.play_analyze_mode}

    @app.post("/api/nav/mistake")
    def find_mistake(request: FindMistakeRequest, current_user: User = Depends(get_current_user)):
        session = _get_session_or_404(manager, request.session_id)
        guard_ai_ladder_ranked_session(session, "find-mistake")
        _guard_engine_move_pending(app, request.session_id)
        with persistent_analysis_activity(current_user, session, "mistake", "mistake analysis"):
            with session.lock:
                session.katrain("find_mistake", fn=request.fn)
                state = session.katrain.get_state()
                session.last_state = state
        return {"session_id": session.session_id, "state": state}

    @app.post("/api/nav/branch")
    def switch_branch(request: SwitchBranchRequest, current_user: User = Depends(get_current_user)):
        session = _get_session_or_404(manager, request.session_id)
        guard_ai_ladder_ranked_session(session, "switch-branch")
        _guard_engine_move_pending(app, request.session_id)
        with persistent_analysis_activity(current_user, session, "nav", "navigation analysis"):
            with session.lock:
                session.katrain("switch_branch", direction=request.direction)
                state = session.katrain.get_state()
                session.last_state = state
        return {"session_id": session.session_id, "state": state}

    @app.post("/api/analysis/tsumego")
    def tsumego_frame(request: TsumegoRequest, current_user: User = Depends(get_current_user)):
        session = _get_session_or_404(manager, request.session_id)
        guard_ai_ladder_ranked_session(session, "tsumego-analysis")
        with persistent_analysis_activity(current_user, session, "tsumego", "tsumego analysis"):
            with session.lock:
                session.katrain("tsumego_frame", ko=request.ko, margin=request.margin)
                state = session.katrain.get_state()
                session.last_state = state
        return {"session_id": session.session_id, "state": state}

    @app.post("/api/analysis/selfplay")
    def selfplay(request: SelfPlayRequest, current_user: User = Depends(get_current_user)):
        session = _get_session_or_404(manager, request.session_id)
        guard_ai_ladder_ranked_session(session, "selfplay-analysis")
        with persistent_analysis_activity(current_user, session, "selfplay", "selfplay analysis"):
            with session.lock:
                session.katrain(
                    "selfplay_setup", until_move=request.until_move, target_b_advantage=request.target_b_advantage
                )
                state = session.katrain.get_state()
                session.last_state = state
        return {"session_id": session.session_id, "state": state}

    @app.post("/api/analysis/region")
    def set_region(request: SelectBoxRequest, current_user: User = Depends(get_current_user)):
        session = _get_session_or_404(manager, request.session_id)
        guard_ai_ladder_ranked_session(session, "region-analysis")
        with persistent_analysis_activity(current_user, session, "region", "region analysis"):
            with session.lock:
                session.katrain("select_box", coords=request.coords)
                state = session.katrain.get_state()
                session.last_state = state
        return {"session_id": session.session_id, "state": state}

    def _enqueue_ladder_settlement_sync(app, current_user, snapshot, raw_result, session):
        """Hand this board's settled ranked game to the sync queue for the cloud.

        Only on a node that HAS a queue (a board); a cloud server settles in place. The
        queue entry is keyed by game_id, so a retry — or a second settlement attempt
        after a crash — re-uses the same entry instead of submitting the game twice.
        Failure to enqueue must never undo a settlement that already happened locally:
        the rank moved, the ledger says so, and the worst case here is that the cloud
        learns about it later.
        """
        enqueue = getattr(app.state, "sync_enqueue_fn", None)
        if enqueue is None:
            return
        try:
            from katrain.web.core.ai_ladder_catalog import result_for_user

            enqueue(
                operation="settle_ai_ladder_ranked",
                endpoint="/api/v1/ai-ladder/settlements",
                method="POST",
                payload={
                    "game_id": snapshot.game_id,
                    "user_color": snapshot.user_color,
                    "result": result_for_user(raw_result, snapshot.user_color),
                    "game_type": snapshot.game_type,
                    "opponent": {
                        "rung": snapshot.opponent.rung,
                        "rank_name": snapshot.opponent.rank_name,
                        "config_snapshot": dict(snapshot.opponent.config_snapshot),
                        "certification_status": snapshot.opponent.certification_status,
                        "availability": snapshot.opponent.availability,
                        "route": snapshot.opponent.route,
                    },
                    "engine_stalled": bool(getattr(session.katrain, "last_ladder_error", False)),
                    "device_id": settings.DEVICE_ID,
                },
                user_id=str(current_user.id),
                idempotency_key=f"ladder-settlement:{snapshot.game_id}",
            )
        except Exception as exc:  # pragma: no cover - defensive
            logging.getLogger("katrain_web").error(f"Could not queue ranked settlement for sync: {exc}")

    async def _record_ai_game_locked(session, app, current_user, result):
        """Record a completed single-player/local game to user_games (remote-first via
        dispatcher, else local). source = play_local when both seats are human, else play_ai.

        Idempotent within a session: the natural (two-pass) game-end hook in `play_move`
        and the resign/count/timeout paths can all race to record the same finished game.
        Ranked AI games keep `_recorded` false until both the authoritative game row and
        ladder settlement succeed, so a transient settlement failure remains retryable."""
        if getattr(session, "_recorded", False) is True:
            return
        try:
            sgf_content = session.katrain.get_sgf()
            state = session.katrain.get_state()
            players_info = session.katrain.players_info

            # Determine player names
            player_black = players_info["B"].name or ""
            player_white = players_info["W"].name or ""
            # Fill in username for the human side if still empty
            if current_user:
                if players_info["B"].human and not player_black:
                    player_black = current_user.username
                if players_info["W"].human and not player_white:
                    player_white = current_user.username
            # Label AI side with calculated rank if name is still empty
            for bw, info in players_info.items():
                if info.ai:
                    name = info.name
                    if not name and info.calculated_rank:
                        name = f"AI ({info.calculated_rank})"
                    elif not name:
                        name = "AI"
                    if bw == "B":
                        player_black = player_black or name
                    else:
                        player_white = player_white or name

            # Extract only serializable rank labels. Some session adapters omit SGF
            # rank attributes entirely, and test doubles may synthesize attributes.
            def player_rank(info):
                for attribute in ("calculated_rank", "sgf_rank"):
                    value = getattr(info, attribute, None)
                    if isinstance(value, str) and value:
                        return value
                return ""

            black_rank = player_rank(players_info["B"])
            white_rank = player_rank(players_info["W"])

            board_size_val = state.get("board_size", [19, 19])
            board_size = board_size_val[0] if isinstance(board_size_val, (list, tuple)) else board_size_val
            move_count = len(state.get("history", []))
            komi = state.get("komi", 7.5)
            rules = state.get("ruleset", "chinese")
            game_type = getattr(session, "game_type", "free")

            from datetime import datetime

            game_date = datetime.now().strftime("%Y-%m-%d")

            source = "play_local" if (players_info["B"].human and players_info["W"].human) else "play_ai"

            data = {
                "sgf_content": sgf_content,
                "source": source,
                "player_black": player_black,
                "player_white": player_white,
                "black_rank": black_rank,
                "white_rank": white_rank,
                "result": result,
                "board_size": int(board_size),
                "rules": rules,
                "komi": komi,
                "move_count": move_count,
                "category": "game",
                "game_type": game_type,
                "game_date": game_date,
            }

            if game_type == "ai_ladder_ranked":
                from katrain.web.core.ai_ladder_catalog import (
                    AiLadderSessionSnapshot,
                    frozen_recipe_identity,
                    result_for_user,
                    session_snapshot_from_pending,
                )

                snapshot = getattr(session, "ai_ladder_snapshot", None)
                if not isinstance(snapshot, AiLadderSessionSnapshot):
                    raise ValueError("missing authoritative ranked AI snapshot")
                if current_user is None or current_user.id != session.user_id or current_user.id != snapshot.user_id:
                    raise ValueError("ranked AI session owner mismatch")
                if snapshot.session_id != session.session_id or snapshot.game_type != game_type:
                    raise ValueError("ranked AI session identity mismatch")
                if getattr(session.katrain, "game_type", None) != game_type:
                    raise ValueError("ranked AI runtime game type mismatch")
                if getattr(session.katrain, "ladder_rung", None) != {"rung": snapshot.opponent.rung}:
                    raise ValueError("ranked AI runtime rung mismatch")
                if getattr(session, "ai_ladder_ai_subtype", None) != snapshot.ai_subtype:
                    raise ValueError("ranked AI subtype mismatch")
                validate_ai_ladder_ranked_players(snapshot, players_info)
                if getattr(session, "ai_ladder_runtime_identity", None) != snapshot.execution_identity:
                    raise ValueError("ranked AI runtime configuration mismatch")
                if (
                    frozen_recipe_identity(getattr(session.katrain, "frozen_ladder_recipe", None))
                    != snapshot.execution_identity
                ):
                    raise ValueError("ranked AI frozen recipe mismatch")
                config_identity = snapshot.opponent.config_snapshot.get("recipe_identity")
                if config_identity != snapshot.execution_identity:
                    raise ValueError("ranked AI snapshot configuration mismatch")
                pending = app.state.ai_ladder_repo.get_pending_game(current_user.id)
                if pending is None or session_snapshot_from_pending(pending) != snapshot:
                    raise ValueError("ranked AI persistent snapshot mismatch")

                actual_result = state.get("end_result") or getattr(session.katrain.game, "end_result", None)
                if not isinstance(actual_result, str) or not actual_result.strip():
                    raise ValueError("ranked AI game has no authoritative end result")
                data["result"] = actual_result

                if not getattr(app.state, "ai_ladder_authoritative", False):
                    raise RuntimeError("ranked AI settlement is unavailable on this node")

                lifecycle = app.state.ai_ladder_repo.get_game_lifecycle(
                    user_id=current_user.id, game_id=snapshot.game_id
                )
                if getattr(lifecycle, "game_id", None) == snapshot.game_id and hasattr(
                    lifecycle, "origin_device_id"
                ):
                    data["origin_device_id"] = lifecycle.origin_device_id

                # Deliberately NOT the repository dispatcher, on any node. Settlement only
                # moves the rank after re-reading the row it just wrote, and the dispatcher
                # may have sent that row to the cloud (online) or queued it (offline) --
                # neither is readable here. The ranked row is written to this node's own
                # authoritative store; getting it to the cloud is the sync queue's job.
                saved = app.state.user_game_repo.create_ai_ladder_ranked(
                    user_id=current_user.id,
                    game_id=snapshot.game_id,
                    **data,
                )
                confirmed = app.state.user_game_repo.get_authoritative_ai_ladder_ranked(
                    snapshot.game_id, current_user.id
                )
                if (
                    saved.get("id") != snapshot.game_id
                    or confirmed is None
                    or confirmed.get("game_type") != "ai_ladder_ranked"
                ):
                    raise RuntimeError("authoritative ranked AI game row was not confirmed")
                app.state.ai_ladder_repo.mark_pending_game_saved(
                    user_id=current_user.id,
                    game_id=snapshot.game_id,
                    result=confirmed["result"],
                )

                terminal_result = result_for_user(confirmed["result"], snapshot.user_color)
                engine_stalled = bool(getattr(session.katrain, "last_ladder_error", False))
                if getattr(lifecycle, "game_id", None) == snapshot.game_id and hasattr(
                    lifecycle, "origin_device_id"
                ):
                    app.state.ai_ladder_repo.finalize_reserved_game(
                        user_id=current_user.id,
                        game_id=snapshot.game_id,
                        terminal_source="played_result",
                        result=terminal_result,
                        deciding_device_id=lifecycle.origin_device_id,
                        reservation_key=pending.get("reservation_key"),
                        game_record=data,
                        engine_stalled=engine_stalled,
                    )
                else:
                    app.state.ai_ladder_repo.settle_game(
                        user_id=current_user.id,
                        game_id=snapshot.game_id,
                        user_color=snapshot.user_color,
                        result=terminal_result,
                        game_type=game_type,
                        opponent=snapshot.opponent,
                        # The AI refused to move because the engine could not seat the rung
                        # at its calibrated strength. The ledger still gets a row -- it just
                        # says engine_unavailable instead of moving the rank. Cleared by the
                        # next successful AI move, so a game that stalled and recovered
                        # settles normally.
                        engine_stalled=engine_stalled,
                    )
                app.state.ai_ladder_repo.clear_pending_game(user_id=current_user.id, game_id=snapshot.game_id)
                _enqueue_ladder_settlement_sync(app, current_user, snapshot, confirmed["result"], session)
                session.ai_ladder_settlement_pending = False
                session._recorded = True
                return

            # Non-ranked games have nothing to settle: the ladder branch above records and
            # settles under one guard and returns, so reaching here means no rank moves.
            dispatcher = getattr(app.state, "repository_dispatcher", None)
            if dispatcher is not None:
                await dispatcher.user_games_create(user_id=current_user.id, data=data)
            else:
                app.state.user_game_repo.create(user_id=current_user.id, **data)
            session._recorded = True
        except Exception as e:
            if getattr(session, "game_type", None) == "ai_ladder_ranked":
                session.ai_ladder_settlement_pending = True
                try:
                    snapshot = getattr(session, "ai_ladder_snapshot", None)
                    pending = app.state.ai_ladder_repo.get_pending_game(session.user_id)
                    lifecycle = app.state.ai_ladder_repo.get_game_lifecycle(
                        user_id=session.user_id, game_id=snapshot.game_id
                    )
                    if (
                        pending is not None
                        and pending.get("game_saved")
                        and getattr(lifecycle, "state", None) == "active"
                    ):
                        app.state.ai_ladder_repo.mark_pending_settlement(
                            user_id=session.user_id,
                            game_id=snapshot.game_id,
                            reservation_key=pending.get("reservation_key"),
                            origin_device_id=lifecycle.origin_device_id,
                        )
                except Exception:
                    pass
            logging.getLogger("katrain_web").error(f"Failed to record game: {e}")

    async def _record_ai_game(session, app, current_user, result):
        record_lock = getattr(session, "record_game_lock", None)
        if not isinstance(record_lock, asyncio.Lock):
            record_lock = asyncio.Lock()
            session.record_game_lock = record_lock
        async with record_lock:
            await _record_ai_game_locked(session, app, current_user, result)

    globals()["_RECORD_FN"] = _record_ai_game

    @app.post("/api/resign")
    async def resign(request: ToggleAnalysisRequest, current_user: User = Depends(get_current_user_optional)):
        session = _get_session_or_404(manager, request.session_id)
        ranked_ai = is_ai_ladder_ranked_session(session)
        if ranked_ai:
            guard_ai_ladder_ranked_owner(session, current_user, "resign")

        # Route through platform gateway for cross-platform games
        gateway = getattr(app.state, "platform_gateway", None)
        platform_game = bool(not ranked_ai and gateway and gateway.is_platform_game(request.session_id))
        if platform_game:
            from katrain.web.platforms.gateway import PlatformMoveRejectedError

            try:
                user_id = current_user.id if current_user else 0
                await gateway.resign(request.session_id, user_id)
            except PlatformMoveRejectedError as e:
                raise HTTPException(status_code=409, detail=str(e))

        # For multiplayer games, record the result
        is_multiplayer = session.player_b_id is not None or session.player_w_id is not None

        if not platform_game:
            with session.lock:
                if ranked_ai:
                    snapshot = guard_ai_ladder_ranked_owner(session, current_user, "resign")
                    guard_ai_ladder_ranked_not_ended(session, "resign")
                    winner = "W" if snapshot.user_color == "B" else "B"
                    result = f"{winner}+R"
                    session.katrain.game.game_result = result
                    session.katrain.game.current_node.end_state = result
                    if hasattr(session.katrain, "_state"):
                        session.katrain._state["end_result"] = result
                else:
                    session.katrain("resign")
                state = session.katrain.get_state()
                session.last_state = state
        else:
            state = session.katrain.get_state()
            session.last_state = state

        # Record game result for multiplayer
        if is_multiplayer and current_user:
            try:
                winner_id = session.player_w_id if current_user.id == session.player_b_id else session.player_b_id
                result = f"{'W' if winner_id == session.player_w_id else 'B'}+R"

                app.state.game_repo.record_multiplayer_game(
                    sgf_content=session.katrain.get_sgf(),
                    result=result,
                    game_type=getattr(session, "game_type", "free"),
                    black_id=session.player_b_id,
                    white_id=session.player_w_id,
                )

                manager._schedule_broadcast(
                    session,
                    {"type": "game_end", "data": {"reason": "resign", "winner_id": winner_id, "result": result}},
                )
            except Exception as e:
                logging.getLogger("katrain_web").error(f"Failed to record game result: {e}")
        elif not is_multiplayer and current_user and session.user_id:
            result = state.get("end_result") or session.katrain.game.end_result
            if result:
                await _record_ai_game(session, app, current_user, result)

        return {"session_id": session.session_id, "state": state}

    def _complete_count(session, app, current_user):
        """Helper to complete counting and record result.

        Returns (result, needs_record). needs_record is True when the caller must
        await _record_ai_game(...) AFTER releasing session.lock (single-player/local
        games only — multiplayer games are recorded synchronously here instead).
        """
        # Get the score from current node's analysis
        current_node = session.katrain.game.current_node
        score = current_node.score

        if score is None:
            raise HTTPException(
                status_code=400, detail="Analysis not available yet. Please wait for KataGo analysis to complete."
            )

        # Format result: positive = Black leads, negative = White leads
        if score >= 0:
            result = f"B+{abs(score):.1f}"
            winner_color = "B"
        else:
            result = f"W+{abs(score):.1f}"
            winner_color = "W"

        # Set end state on the current node (game.end_result reads from current_node.end_state)
        session.katrain.game.game_result = result
        session.katrain.game.current_node.end_state = result
        session.game_ended = True

        # Record multiplayer game result
        is_multiplayer = session.player_b_id is not None or session.player_w_id is not None
        if is_multiplayer:
            winner_id = session.player_b_id if winner_color == "B" else session.player_w_id
            try:
                app.state.game_repo.record_multiplayer_game(
                    sgf_content=session.katrain.get_sgf(),
                    result=result,
                    game_type=getattr(session, "game_type", "free"),
                    black_id=session.player_b_id,
                    white_id=session.player_w_id,
                )
            except Exception as e:
                logging.getLogger("katrain_web").error(f"Failed to record count game result: {e}")

            manager._schedule_broadcast(
                session, {"type": "game_end", "data": {"reason": "count", "winner_id": winner_id, "result": result}}
            )
            return result, False

        needs_record = current_user is not None and session.user_id is not None
        return result, needs_record

    @app.post("/api/count/request")
    async def request_count(request: CountRequest, current_user: User = Depends(get_current_user_optional)):
        """Request to end game by counting. For HvAI, completes immediately. For HvH, sends request to opponent."""
        session = _get_session_or_404(manager, request.session_id)
        guard_ai_ladder_ranked_human_action(session, current_user, "request-count")

        # Verify move count >= configured minimum
        state = session.katrain.get_state()
        count_min_moves = session.katrain.config("game/count_min_moves", 100)
        if len(state.get("history", [])) < count_min_moves:
            raise HTTPException(status_code=400, detail=f"Cannot count before {count_min_moves} moves")

        # Check if game is already over
        if state.get("end_result"):
            raise HTTPException(status_code=400, detail="Game is already over")

        is_multiplayer = session.player_b_id is not None or session.player_w_id is not None

        if is_multiplayer:
            # HvH: Check if user is a player
            if not current_user:
                raise HTTPException(status_code=401, detail="Authentication required")

            is_player = current_user.id in (session.player_b_id, session.player_w_id)
            if not is_player:
                raise HTTPException(status_code=403, detail="Only players can request count")

            # Check if there's already a pending request
            if session.pending_count_request is not None:
                # If same user requests again, ignore
                if session.pending_count_request == current_user.id:
                    return {"session_id": session.session_id, "status": "pending"}

                # If other player requests, treat as accept
                with session.lock:
                    result, _ = _complete_count(session, app, current_user)
                    session.pending_count_request = None
                    session.pending_count_timestamp = None
                    state = session.katrain.get_state()
                    session.last_state = state
                return {"session_id": session.session_id, "state": state, "result": result}

            # Set pending request
            import time as time_module

            session.pending_count_request = current_user.id
            session.pending_count_timestamp = time_module.time()

            # Broadcast to opponent
            manager._schedule_broadcast(
                session,
                {
                    "type": "count_request",
                    "data": {"requester_id": current_user.id, "requester_name": current_user.username},
                },
            )

            return {"session_id": session.session_id, "status": "pending"}
        else:
            # HvAI / pvp_local: complete immediately
            with session.lock:
                guard_ai_ladder_ranked_human_action(session, current_user, "request-count")
                result, needs_record = _complete_count(session, app, current_user)
                state = session.katrain.get_state()
                session.last_state = state
            if needs_record:
                await _record_ai_game(session, app, current_user, result)
            return {"session_id": session.session_id, "state": state, "result": result}

    @app.post("/api/count/respond")
    def respond_count(request: CountResponse, current_user: User = Depends(get_current_user)):
        """Respond to a count request (HvH only). Accept or reject."""
        session = _get_session_or_404(manager, request.session_id)

        # Only for multiplayer games
        is_multiplayer = session.player_b_id is not None or session.player_w_id is not None
        if not is_multiplayer:
            raise HTTPException(status_code=400, detail="Not a multiplayer game")

        # Check if there's a pending request
        if session.pending_count_request is None:
            raise HTTPException(status_code=400, detail="No pending count request")

        # Verify user is the opponent (not the requester)
        if current_user.id == session.pending_count_request:
            raise HTTPException(status_code=400, detail="Cannot respond to your own request")

        # Verify user is a player
        is_player = current_user.id in (session.player_b_id, session.player_w_id)
        if not is_player:
            raise HTTPException(status_code=403, detail="Only players can respond to count")

        if request.accept:
            # Accept: complete the count
            with session.lock:
                result, _ = _complete_count(session, app, current_user)
                session.pending_count_request = None
                session.pending_count_timestamp = None
                state = session.katrain.get_state()
                session.last_state = state
            return {"session_id": session.session_id, "state": state, "result": result, "accepted": True}
        else:
            # Reject: clear request and notify
            session.pending_count_request = None
            session.pending_count_timestamp = None

            manager._schedule_broadcast(session, {"type": "count_rejected", "data": {"rejected_by": current_user.id}})

            return {"session_id": session.session_id, "accepted": False}

    @app.post("/api/timeout")
    async def timeout(request: ToggleAnalysisRequest, current_user: User = Depends(get_current_user_optional)):
        """End game due to timeout - current player loses on time"""
        session = _get_session_or_404(manager, request.session_id)
        guard_ai_ladder_ranked_human_action(session, current_user, "timeout")

        # For multiplayer games, record the result
        is_multiplayer = session.player_b_id is not None or session.player_w_id is not None

        with session.lock:
            guard_ai_ladder_ranked_human_action(session, current_user, "timeout")
            session.katrain("timeout")
            state = session.katrain.get_state()
            session.last_state = state

        # Record game result for multiplayer
        if is_multiplayer and current_user:
            try:
                winner_id = session.player_w_id if current_user.id == session.player_b_id else session.player_b_id
                result = f"{'W' if winner_id == session.player_w_id else 'B'}+T"

                app.state.game_repo.record_multiplayer_game(
                    sgf_content=session.katrain.get_sgf(),
                    result=result,
                    game_type=getattr(session, "game_type", "free"),
                    black_id=session.player_b_id,
                    white_id=session.player_w_id,
                )

                manager._schedule_broadcast(
                    session,
                    {"type": "game_end", "data": {"reason": "timeout", "winner_id": winner_id, "result": result}},
                )
            except Exception as e:
                logging.getLogger("katrain_web").error(f"Failed to record game result: {e}")
        elif not is_multiplayer and current_user and session.user_id:
            result = session.katrain.game.end_result
            if result:
                await _record_ai_game(session, app, current_user, result)

        return {"session_id": session.session_id, "state": state}

    @app.post("/api/multiplayer/leave")
    def leave_multiplayer_game(request: ToggleAnalysisRequest, current_user: User = Depends(get_current_user)):
        """Leave a multiplayer game (counts as forfeit)"""
        session = _get_session_or_404(manager, request.session_id)

        is_multiplayer = session.player_b_id is not None or session.player_w_id is not None
        if not is_multiplayer:
            raise HTTPException(status_code=400, detail="Not a multiplayer game")

        # Check if user is a player
        is_player = current_user.id in (session.player_b_id, session.player_w_id)
        if not is_player:
            # Spectator leaving - just return
            return {"status": "left", "redirect": "/galaxy/play/human"}

        # Player leaving = forfeit
        winner_id = session.player_w_id if current_user.id == session.player_b_id else session.player_b_id
        result = f"{'W' if winner_id == session.player_w_id else 'B'}+F"  # F for Forfeit

        try:
            app.state.game_repo.record_multiplayer_game(
                sgf_content=session.katrain.get_sgf(),
                result=result,
                game_type=getattr(session, "game_type", "free"),
                black_id=session.player_b_id,
                white_id=session.player_w_id,
            )
        except Exception as e:
            logging.getLogger("katrain_web").error(f"Failed to record game forfeit: {e}")

        # Broadcast game end to all connected sockets
        manager._schedule_broadcast(
            session,
            {
                "type": "game_end",
                "data": {"reason": "forfeit", "winner_id": winner_id, "result": result, "leaver_id": current_user.id},
            },
        )

        # Clean up the session
        manager.remove_session(request.session_id)

        return {"status": "forfeited", "redirect": "/galaxy/play/human"}

    @app.post("/api/timer/pause")
    def pause_timer(request: ToggleAnalysisRequest):
        session = _get_session_or_404(manager, request.session_id)
        guard_ai_ladder_ranked_session(session, "pause-timer")
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
        guard_ai_ladder_ranked_session(session, "delete-node")
        with session.lock:
            session.katrain("delete_node", node_id=request.node_id)
            state = session.katrain.get_state()
            session.last_state = state
        return {"session_id": session.session_id, "state": state}

    @app.post("/api/node/prune")
    def prune_branch(request: NavRequest):
        session = _get_session_or_404(manager, request.session_id)
        guard_ai_ladder_ranked_session(session, "prune-branch")
        with session.lock:
            session.katrain("prune_branch", node_id=request.node_id)
            state = session.katrain.get_state()
            session.last_state = state
        return {"session_id": session.session_id, "state": state}

    @app.post("/api/node/make-main")
    def make_main_branch(request: NavRequest):
        session = _get_session_or_404(manager, request.session_id)
        guard_ai_ladder_ranked_session(session, "make-main-branch")
        with session.lock:
            session.katrain("make_main_branch", node_id=request.node_id)
            state = session.katrain.get_state()
            session.last_state = state
        return {"session_id": session.session_id, "state": state}

    @app.post("/api/node/toggle-collapse")
    def toggle_collapse(request: NavRequest):
        session = _get_session_or_404(manager, request.session_id)
        guard_ai_ladder_ranked_session(session, "toggle-node-collapse")
        with session.lock:
            session.katrain("toggle_collapse", node_id=request.node_id)
            state = session.katrain.get_state()
            session.last_state = state
        return {"session_id": session.session_id, "state": state}

    @app.post("/api/ui/toggle")
    def toggle_ui(request: UIToggleRequest, current_user: User | None = Depends(get_current_user_optional)):
        session = _get_session_or_404(manager, request.session_id)
        analysis_toggles = getattr(
            session.katrain, "ANALYSIS_TOGGLES", frozenset({"eval", "hints", "ownership", "policy", "dots"})
        )
        if request.setting in analysis_toggles:
            if current_user is None:
                raise HTTPException(status_code=401, detail="Authentication required for analysis display")
            guard_user_has_no_pending_ranked_game(app, current_user, "analysis display")
        guard_ai_ladder_ranked_ui_toggle(session, request.setting)
        with session.lock:
            session.katrain("toggle_ui", setting=request.setting)
            state = session.katrain.get_state()
            session.last_state = state
        if request.setting in analysis_toggles:
            guard_user_has_no_pending_ranked_game(app, current_user, "analysis display")
        return {"session_id": session.session_id, "state": state}

    @app.post("/api/language")
    def switch_language(request: LanguageRequest):
        session = _get_session_or_404(manager, request.session_id)
        with session.lock:
            session.katrain("switch_lang", lang=request.lang)
            state = session.katrain.get_state()
            session.last_state = state
        return {
            "session_id": session.session_id,
            "state": state,
            "language": session.katrain.config("general/language"),
        }

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
            AI_CONFIG_DEFAULT,
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
                "tenuki_penalty": 0.5,
            },
            "ai:p:weighted": {"weaken_fac": 0.5, "pick_override": 1.0, "lower_bound": 0.001},
            "ai:p:pick": {"pick_override": 0.95, "pick_n": 5, "pick_frac": 0.35},
            "ai:p:local": {"pick_override": 0.95, "stddev": 1.5, "pick_n": 15, "pick_frac": 0.0, "endgame": 0.5},
            "ai:p:tenuki": {"pick_override": 0.85, "stddev": 7.5, "pick_n": 5, "pick_frac": 0.4, "endgame": 0.45},
            "ai:p:influence": {
                "pick_override": 0.95,
                "pick_n": 5,
                "pick_frac": 0.3,
                "threshold": 3.5,
                "line_weight": 10,
                "endgame": 0.4,
            },
            "ai:p:territory": {
                "pick_override": 0.95,
                "pick_n": 5,
                "pick_frac": 0.3,
                "threshold": 3.5,
                "line_weight": 2,
                "endgame": 0.4,
            },
            "ai:p:rank": {"kyu_rank": -2},
            "ai:human": {"human_kyu_rank": 0, "modern_style": True},
            "ai:pro": {"pro_year": 2010, "modern_style": True},
            "ai:ladder": {},
        }

        return {
            "strategies": AI_STRATEGIES_RECOMMENDED_ORDER,
            "options": json_option_values,
            "key_properties": list(AI_KEY_PROPERTIES),
            "default_strategy": AI_CONFIG_DEFAULT,
            "strategy_defaults": strategy_defaults,
        }

    @app.get("/api/ladder-rungs")
    def get_ladder_rungs():
        from katrain.web.core.ai_ladder_catalog import catalog_projection

        return catalog_projection()

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
    def analyze_game(request: GameAnalysisRequest, current_user: User = Depends(get_current_user)):
        session = _get_session_or_404(manager, request.session_id)
        guard_ai_ladder_ranked_session(session, "game-analysis")
        with persistent_analysis_activity(current_user, session, "game", "game analysis"):
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

    @app.post("/api/analysis/scan")
    def analysis_scan(request: AnalysisScanRequest, current_user: User = Depends(get_current_user)):
        session = _get_session_or_404(manager, request.session_id)
        guard_ai_ladder_ranked_session(session, "analysis-scan")
        with persistent_analysis_activity(current_user, session, "scan", "analysis scan"):
            with session.lock:
                session.katrain("analysis_scan", visits=request.visits or 500)
                state = session.katrain.get_state()
                session.last_state = state
        return {"session_id": session.session_id, "state": state}

    @app.get("/api/analysis/progress")
    def analysis_progress(session_id: str, current_user: User = Depends(get_current_user)):
        guard_user_has_no_pending_ranked_game(app, current_user, "analysis progress")
        session = _get_session_or_404(manager, session_id)
        guard_ai_ladder_ranked_session(session, "analysis-progress")
        with session.lock:
            progress = session.katrain._do_analysis_progress()
        guard_user_has_no_pending_ranked_game(app, current_user, "analysis progress")
        return {"session_id": session.session_id, **progress}

    @app.post("/api/analysis/report")
    def get_game_report(request: GameReportRequest, current_user: User = Depends(get_current_user)):
        guard_user_has_no_pending_ranked_game(app, current_user, "analysis report")
        session = _get_session_or_404(manager, request.session_id)
        guard_ai_ladder_ranked_session(session, "analysis-report")
        with session.lock:
            report = session.katrain._do_game_report(depth_filter=request.depth_filter)
        guard_user_has_no_pending_ranked_game(app, current_user, "analysis report")
        return {"session_id": session.session_id, "report": report}

    @app.post("/api/mode/insert")
    def set_insert_mode(request: InsertModeRequest):
        session = _get_session_or_404(manager, request.session_id)
        guard_ai_ladder_ranked_session(session, "insert-mode")
        with session.lock:
            session.katrain("insert_mode", mode=request.mode)
            state = session.katrain.get_state()
            session.last_state = state
        return {"session_id": session.session_id, "state": state}

    # NOTE: /ws/lobby MUST be defined BEFORE /ws/{session_id} to avoid routing conflicts
    @app.websocket("/ws/lobby")
    async def lobby_websocket_endpoint(websocket: WebSocket):
        from katrain.web.api.v1.endpoints.auth import get_user_from_token
        from katrain.web.core.box_sso import resolve_websocket_token, strict_box_sso_enabled

        logger = logging.getLogger("katrain_web")
        token = resolve_websocket_token(websocket)
        if not token:
            logger.warning("Lobby WebSocket: No token provided, closing connection")
            await websocket.accept()
            await websocket.close(code=1008, reason="No token provided")
            return

        try:
            current_user = await get_user_from_token(token=token, repo=app.state.user_repo, box_sso=app.state.box_sso)
        except Exception as e:
            logger.warning(f"Lobby WebSocket: Token validation failed: {e}")
            await websocket.accept()
            await websocket.close(code=1008, reason="Invalid token")
            return

        await websocket.accept()
        if strict_box_sso_enabled():
            app.state.box_sso.register_socket(websocket)
        lobby_manager = app.state.lobby_manager
        lobby_manager.add_user(current_user.id, websocket)
        logger.info(
            f"User {current_user.username} (ID: {current_user.id}) joined the lobby. Online users: {lobby_manager.get_online_user_ids()}"
        )
        try:
            # Broadcast update immediately
            await lobby_manager.broadcast(
                {"type": "lobby_update", "online_count": len(lobby_manager.get_online_user_ids())}
            )
            while True:
                message = await websocket.receive_json()
                msg_type = message.get("type")
                if msg_type == "ping":
                    await websocket.send_json({"type": "pong"})

                elif msg_type == "start_matchmaking":
                    game_type = message.get("game_type", "free")
                    logging.getLogger("katrain_web").info(
                        f"User {current_user.username} (ID: {current_user.id}) started matchmaking for {game_type}"
                    )

                    # Prerequisite for rated PvP: you must have a ladder rank, so the
                    # pairing has something to pair on. Formerly a count of finished
                    # `game_type == "rated"` games, which nothing ever wrote for an AI
                    # game -- the counter sat at 0 forever and the lobby sent players to
                    # a page that could not move it.
                    if game_type == "rated":
                        if not app.state.ai_ladder_repo.has_ladder_rank(current_user.id):
                            await websocket.send_json(
                                {
                                    "type": "error",
                                    "code": "PLACEMENT_REQUIRED",
                                    "message": "Finish your 5-game 定级赛 in 升降级对弈 before playing rated PvP.",
                                }
                            )
                            continue

                    match = app.state.matchmaker.add_to_queue(current_user.id, game_type, websocket)
                    if match:
                        logging.getLogger("katrain_web").info(f"Match found: {match.player1_id} vs {match.player2_id}")
                        # Fetch Usernames
                        user_repo = app.state.user_repo
                        u1 = user_repo.get_user_by_id(match.player1_id)
                        u2 = user_repo.get_user_by_id(match.player2_id)

                        # Create Multiplayer Session
                        # Randomly assign B/W
                        import random

                        if random.random() < 0.5:
                            pb, pw = match.player1_id, match.player2_id
                            pb_name, pw_name = u1.get("username") if u1 else "Black", (
                                u2.get("username") if u2 else "White"
                            )
                        else:
                            pb, pw = match.player2_id, match.player1_id
                            pb_name, pw_name = u2.get("username") if u2 else "Black", (
                                u1.get("username") if u1 else "White"
                            )

                        game_session = app.state.session_manager.create_multiplayer_session(
                            pb, pw, b_name=pb_name, w_name=pw_name
                        )

                        # Found a match!
                        match_payload = {
                            "type": "match_found",
                            "match_id": match.match_id,
                            "session_id": game_session.session_id,
                            "game_type": match.game_type,
                            "players": {
                                "player_b": pb,
                                "player_w": pw,
                                "player_b_name": pb_name,
                                "player_w_name": pw_name,
                            },
                        }

                        # Send reliably
                        try:
                            await match.player1_socket.send_json(match_payload)
                        except Exception as e:
                            logger.error(f"Failed to send match to Player 1: {e}")

                        try:
                            await match.player2_socket.send_json(match_payload)
                        except Exception as e:
                            logger.error(f"Failed to send match to Player 2: {e}")

                elif msg_type == "stop_matchmaking":
                    app.state.matchmaker.remove_from_queue(current_user.id)

                elif msg_type == "invite":
                    target_id = message.get("target_id")
                    if target_id and target_id != current_user.id:
                        # Find target sockets
                        # Note: accessing _online_users directly as get_online_user_ids only returns keys
                        # We need to expose sockets or lock properly. LobbyManager._online_users is internal but we are in the same module logic context mostly.
                        # Ideally LobbyManager should expose a method 'send_to_user'
                        with lobby_manager._lock:
                            target_sockets = list(lobby_manager._online_users.get(target_id, []))

                        if target_sockets:
                            invite_payload = {
                                "type": "invitation",
                                "from_id": current_user.id,
                                "from_name": current_user.username,
                                "mode": message.get("mode", "free"),
                            }
                            for ws in target_sockets:
                                try:
                                    await ws.send_json(invite_payload)
                                except:
                                    pass

                            # Confirm to sender
                            await websocket.send_json({"type": "info", "message": "Invitation sent."})
                        else:
                            await websocket.send_json({"type": "error", "message": "User is offline or not in lobby."})

                elif msg_type == "accept_invite":
                    target_id = message.get("target_id")  # The inviter
                    if target_id:
                        # Fetch Usernames
                        user_repo = app.state.user_repo
                        all_users = user_repo.list_users()
                        users_by_id = {u["id"]: u["username"] for u in all_users}

                        # Create Session (Inviter = Black, Acceptor = White by default, or random)
                        pb, pw = target_id, current_user.id

                        game_session = app.state.session_manager.create_multiplayer_session(
                            pb, pw, b_name=users_by_id.get(pb), w_name=users_by_id.get(pw)
                        )

                        match_payload = {
                            "type": "match_found",
                            "session_id": game_session.session_id,
                            "game_type": "free",  # Direct invites are free for now
                            "players": {"player_b": pb, "player_w": pw},
                        }

                        # Send to self (Acceptor)
                        await websocket.send_json(match_payload)

                        # Send to Inviter
                        with lobby_manager._lock:
                            target_sockets = list(lobby_manager._online_users.get(target_id, []))
                        for ws in target_sockets:
                            try:
                                await ws.send_json(match_payload)
                            except:
                                pass

        except WebSocketDisconnect:
            logging.getLogger("katrain_web").info(f"User {current_user.username} disconnected from lobby.")
            pass
        finally:
            app.state.box_sso.discard_socket(websocket)
            app.state.matchmaker.remove_from_queue(current_user.id)
            lobby_manager.remove_user(current_user.id, websocket)
            await lobby_manager.broadcast(
                {"type": "lobby_update", "online_count": len(lobby_manager.get_online_user_ids())}
            )

    # NOTE (ordering is load-bearing): /ws/vision MUST be registered BEFORE the
    # /ws/{session_id} param route. Starlette matches websocket routes in registration
    # order; if the param route comes first it captures /ws/vision as session_id="vision"
    # and closes it with 1008 "Session not found", silently killing ALL vision events to
    # the kiosk (physical tsumego then hangs forever at "clear board"). Do not reorder.
    @app.websocket("/ws/vision")
    async def vision_websocket(websocket: WebSocket):
        """Vision event WebSocket — events arrive via the pump's per-connection queue."""
        await websocket.accept()
        vision = getattr(app.state, "vision", None)
        if vision is None:
            await websocket.close(code=1008, reason="Vision service not enabled")
            return
        queue: asyncio.Queue = asyncio.Queue()
        app.state.vision_ws_clients[websocket] = queue
        logging.getLogger("katrain_web.vision").info(
            "[DIAG-WS] /ws/vision CONNECTED (clients now %d)", len(app.state.vision_ws_clients)
        )
        try:
            while True:
                while not queue.empty():
                    await websocket.send_json(_json_safe(queue.get_nowait()))

                vision.refresh_status()
                await websocket.send_json(
                    _json_safe(
                        {
                            "type": "vision_status",
                            "data": {
                                "camera_connected": vision.camera_status == "connected",
                                "pose_locked": vision.pose_lock_status == "locked",
                                "sync_state": vision.sync_state,
                            },
                        }
                    )
                )

                # Check for client messages (ping)
                try:
                    message = await asyncio.wait_for(websocket.receive_json(), timeout=0.5)
                    if message.get("type") == "ping":
                        await websocket.send_json({"type": "pong"})
                except asyncio.TimeoutError:
                    pass
        except WebSocketDisconnect:
            logging.getLogger("katrain_web.vision").info("[DIAG-WS] /ws/vision client WebSocketDisconnect")
        except Exception as exc:  # DIAG: surface any non-disconnect error that silently drops the socket
            logging.getLogger("katrain_web.vision").warning("[DIAG-WS] /ws/vision handler error: %r", exc)
        finally:
            app.state.vision_ws_clients.pop(websocket, None)
            logging.getLogger("katrain_web.vision").info(
                "[DIAG-WS] /ws/vision DISCONNECTED (clients now %d)", len(app.state.vision_ws_clients)
            )

    @app.websocket("/ws/{session_id}")
    async def websocket_endpoint(websocket: WebSocket, session_id: str):
        from katrain.web.api.v1.endpoints.auth import get_user_from_token
        from katrain.web.core.box_sso import resolve_websocket_token, strict_box_sso_enabled

        strict_box = strict_box_sso_enabled()
        token = resolve_websocket_token(websocket)
        try:
            if not token:
                raise ValueError("missing credential")
            current_user = await get_user_from_token(token=token, repo=app.state.user_repo, box_sso=app.state.box_sso)
        except Exception:
            await websocket.accept()
            await websocket.close(code=1008, reason="Invalid token")
            return
        try:
            session = manager.get_session(session_id)
        except KeyError:
            await websocket.accept()
            await websocket.close(code=1008, reason="Session not found")
            return
        try:
            guard_session_reader(session, current_user, "session websocket")
            if not is_ai_ladder_ranked_session(session):
                guard_user_has_no_pending_ranked_game(app, current_user, "session websocket")
        except HTTPException:
            await websocket.accept()
            await websocket.close(code=1008, reason="Session unavailable")
            return

        await websocket.accept()
        if strict_box:
            app.state.box_sso.register_socket(websocket)
        session.sockets.add(websocket)
        try:
            state = session.last_state or session.katrain.get_state()
            state["sockets_count"] = len(session.sockets)
            # Send initial state to this client
            await websocket.send_json({"type": "game_update", "state": state})
            # Broadcast updated spectator count to all other clients (lightweight update)
            manager.broadcast_to_session(session_id, {"type": "spectator_count", "count": len(session.sockets)})
            while True:
                message = await websocket.receive_json()
                if message.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})
                elif message.get("type") == "chat":
                    manager.broadcast_to_session(session_id, message)
        except WebSocketDisconnect:
            pass
        finally:
            if strict_box:
                app.state.box_sso.discard_socket(websocket)
            session.sockets.discard(websocket)
            # Broadcast updated spectator count when someone leaves
            if session.sockets:  # Only if there are still connected clients
                manager.broadcast_to_session(session_id, {"type": "spectator_count", "count": len(session.sockets)})

    # SPA Routing for Galaxy UI
    @app.get("/galaxy", response_class=FileResponse)
    @app.get("/galaxy/{full_path:path}", response_class=FileResponse)
    async def serve_galaxy_app(full_path: str = None):
        return str(static_root / "index.html")

    # SPA Routing for Kiosk UI
    @app.get("/kiosk", response_class=FileResponse)
    @app.get("/kiosk/{full_path:path}", response_class=FileResponse)
    async def serve_kiosk_app(full_path: str = None):
        return str(static_root / "index.html")

    # SPA Routing for Video Recorder
    @app.get("/record", response_class=FileResponse)
    async def serve_record_app():
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


def _guard_engine_move_pending(app: FastAPI, session_id: str) -> None:
    """409 while an engine-play (Golaxy 人机对弈 genmove tunnel) move is in flight.

    The tunnel can take up to ~180s; mutating the tree underneath it (undo/redo/
    nav to a different node) makes the eventual AI reply land on the wrong node
    once it returns (review B2). Task 4's gateway also re-checks a position token
    atomically before applying, so this 409 is belt-and-suspenders, not the only
    line of defense — but it's the one that gives the user an immediate, correct
    error instead of a move silently discarded ~3 minutes later.

    Scope (fable5 裁决 2026-07-11): only this fixed endpoint set is guarded this
    iteration — undo/redo/nav/nav-mistake/nav-branch (pending-gated, called from
    here) plus /api/ai-move (unconditional — see its own handler). The rest of the
    tree-mutation surface (sgf/load, new-game, edit-game, node/*, player/swap, ...)
    is intentionally NOT guarded — kiosk engine-mode UI doesn't expose those
    actions. Full endpoint inventory + rationale:
    superpowers/tracks/kiosk-golaxy-physical-play/plan.md (基线记录).
    """
    gateway = getattr(app.state, "platform_gateway", None)
    if gateway and gateway.is_engine_move_pending(session_id):
        raise HTTPException(status_code=409, detail="engine move pending")


async def _led_failsafe_loop(app: FastAPI, idle_timeout: float = 300.0):
    """Blackout the LED board after >5 min of inactivity (plan §2.1 Gemini 新#2).

    Prevents a Kiosk from leaving the LED lit all day if the operator walks off
    without exiting. Activity is stamped by the /led/* endpoints. (A WebSocket
    on-disconnect hook is a future refinement; the idle timer is the floor.)
    """
    log = logging.getLogger("katrain_web.led")
    cleared = False
    while True:
        try:
            await asyncio.sleep(30)
            led = getattr(app.state, "led", None)
            if not led:
                continue
            idle = time.monotonic() - getattr(app.state, "led_last_activity", time.monotonic())
            if idle > idle_timeout and not cleared:
                led.clear(strict=False)
                cleared = True
                log.info("LED idle >%.0fs — failsafe clear", idle_timeout)
            elif idle <= idle_timeout:
                cleared = False
        except asyncio.CancelledError:
            break
        except Exception as e:  # pragma: no cover - defensive
            log.debug("LED failsafe loop error: %s", e)


def _diag_log_vision_evt(log, evt: dict, n_clients: int) -> None:
    t = evt.get("type")
    data = evt.get("data", {})
    if t == "setup_progress":
        log.info(
            "[DIAG-VIS] setup_progress matched=%s/%s missing=%d extra=%d -> %d clients",
            data.get("matched"),
            data.get("total"),
            len(data.get("missing", [])),
            len(data.get("extra", [])),
            n_clients,
        )
    elif t == "vision_status":
        return  # too noisy; sent by the WS handler anyway
    else:
        log.info("[DIAG-VIS] %s data=%s -> %d clients", t, data, n_clients)


async def _vision_event_pump(app: FastAPI):
    """Sole consumer of the vision worker event queue — see vision_pump docstring."""
    from katrain.web.core.vision_pump import route_vision_event

    log = logging.getLogger("katrain_web.vision")
    while True:
        try:
            vision = getattr(app.state, "vision", None)
            if vision:
                for evt in vision.poll_events():
                    if isinstance(evt, dict):
                        _diag_log_vision_evt(log, evt, len(app.state.vision_ws_clients))
                    route_vision_event(
                        evt,
                        list(app.state.vision_ws_clients.values()),
                        app.state.vision_move_queue,
                        bound=bool(vision.bound_session_id),
                    )
            await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("vision event pump error")
            await asyncio.sleep(1.0)


def _apply_engine_recovery_outcome(
    app: FastAPI, manager, session_id: str, game_id: str, coords, reason: str, detail: str
) -> bool:
    """Task 7 (review B5/M1/M4/m2): run one gateway failure through
    app.state.engine_recovery's bounded-retry episode tracker; returns whether the
    caller should re-arm detection (push the expected board again so the stone
    retries). At the attempts threshold this additionally hands the physical-play
    orchestrator into its engine_error pause state and broadcasts
    physical_engine_error to the session — detection then stays paused server-side
    (the orchestrator pauses the vision worker), so the caller must NOT re-arm
    (closes gap G3: a stuck physical stone retrying the tunnel forever)."""
    tracker = getattr(app.state, "engine_recovery", None)
    if tracker is None:  # e.g. board mode / a test app that never wired one up
        return True
    outcome = tracker.on_failure(game_id=game_id, coords=coords, reason=reason, detail=detail)
    if outcome.enter_engine_error:
        episode = outcome.episode
        orchestrator = getattr(app.state, "physical_play", None)
        if orchestrator is not None:
            orchestrator.enter_engine_error(coords, episode.recovery_token)
        manager.broadcast_to_session(
            session_id,
            {
                "type": "physical_engine_error",
                "col": coords[0],
                "row": coords[1],
                "attempts": episode.count,
                "detail": episode.detail,
                "recovery_token": episode.recovery_token,
            },
        )
    return outcome.rearm


async def _handle_confirmed_move(app: FastAPI, vision, session_id: str, move_data, log) -> float:
    """Handle one vision ConfirmedMove for the bound session. Extracted from
    _vision_move_poller (which is otherwise a bare infinite loop) so tests can
    drive this per-move logic directly with a mocked gateway/vision, per Task 7's
    testability note.

    Returns the extra retry-throttle delay the poller should sleep before its next
    poll: 0.0 normally (the loop's own 0.1s tick is enough), 0.5 on an out-of-turn
    ignore or a re-armed gateway failure (unchanged pre-Task-7 throttle — a rejected
    move produces no game_update, so nothing else naturally slows the retry loop).
    """
    from katrain.vision.katrain_bridge import vision_move_to_katrain
    from katrain.web.platforms.gateway import PlatformMoveRejectedError

    manager = app.state.session_manager
    tracker = getattr(app.state, "engine_recovery", None)
    try:
        session = manager.get_session(session_id)
    except KeyError:
        session = None
    if not session:
        # Task 7 table: "session missing" clears the episode and continues — the
        # game this episode belonged to is gone, so there is nothing left to retry.
        if tracker is not None:
            tracker.clear()
        return 0.0

    def _rearm_detection() -> None:
        game_state = session.katrain.get_state()
        if game_state and "stones" in game_state:
            vision.set_expected_from_stones(game_state["stones"])

    if is_ai_ladder_ranked_session(session):
        move_player = "B" if move_data.color == 1 else "W"
        try:
            with session.lock:
                if getattr(vision, "bound_session_id", None) != session_id:
                    raise HTTPException(status_code=403, detail="vision is no longer bound to this session")
                binding = getattr(app.state, "ranked_vision_binding", None)
                snapshot = guard_ranked_vision_binding(session, binding, "physical-play")
                if move_player != snapshot.user_color:
                    raise HTTPException(status_code=403, detail="physical move color does not match the human seat")
                guard_ai_ladder_ranked_human_action(session, SimpleNamespace(id=binding.user_id), "physical-play")
                move = vision_move_to_katrain(move_data.col, move_data.row, move_data.color, board_size=19)
                session.katrain("play", move.coords)
        except (HTTPException, ValueError) as exc:
            log.info("Ranked vision move rejected for session %s: %s", session_id, exc)
            _rearm_detection()
            return 0.5

        log.info("Ranked vision move submitted: col=%d row=%d color=%d", move_data.col, move_data.row, move_data.color)
        orchestrator = getattr(app.state, "physical_play", None)
        if orchestrator is None:
            _rearm_detection()
        return 0.0

    # R1.3: only the side to move may inject (color check).
    expected_player = (session.last_state or {}).get("player_to_move")
    move_player = "B" if move_data.color == 1 else "W"
    if expected_player and move_player != expected_player:
        log.info("Vision move %s out of turn (expects %s) — ignored", move_player, expected_player)
        # Re-arm detection: the worker advanced its baseline when it emitted this
        # move; a rejection produces no game update, so nothing would ever
        # force_sync the baseline back and detection would stay silenced forever.
        # Re-pushing the (unchanged) expected board triggers the worker's
        # polluted-baseline re-sync, so the stone retries once the turn comes around.
        _rearm_detection()
        return 0.5

    move = vision_move_to_katrain(move_data.col, move_data.row, move_data.color, board_size=19)
    coords = (move.coords[0], move.coords[1])
    gateway = getattr(app.state, "platform_gateway", None)
    if gateway and gateway.is_platform_game(session_id):
        game_id = gateway.get_game_id(session_id) or ""
        try:
            await gateway.play_move(session_id, coords[0], coords[1], user_id=0)
        except PlatformMoveRejectedError as e:
            log.warning("Platform gateway rejected vision move: %s", e)
            rearm = _apply_engine_recovery_outcome(app, manager, session_id, game_id, coords, e.reason, str(e))
            if rearm:
                _rearm_detection()
                return 0.5
            return 0.0
        except Exception as gw_err:
            log.warning("Platform gateway rejected vision move: %s", gw_err)
            # Non-PlatformMoveRejectedError exceptions (httpx errors, unexpected
            # adapter bugs, ...) are tunnel/infra failures too — fold them into the
            # "engine_error" bucket so they count toward the same bounded-retry
            # episode instead of retrying forever (documented decision, Task 7).
            rearm = _apply_engine_recovery_outcome(
                app, manager, session_id, game_id, coords, "engine_error", str(gw_err)
            )
            if rearm:
                _rearm_detection()
                return 0.5
            return 0.0
        else:
            if tracker is not None:
                tracker.on_success()
    else:
        with session.lock:
            session.katrain("play", move.coords)

    log.info(
        "Vision move submitted: col=%d row=%d color=%d",
        move_data.col,
        move_data.row,
        move_data.color,
    )
    orchestrator = getattr(app.state, "physical_play", None)
    if orchestrator is None:
        _rearm_detection()
    return 0.0


async def _vision_move_poller(app: FastAPI):
    """Poll vision worker for confirmed moves and inject them into the bound session.

    Q4 blocking happens WORKER-SIDE: while the physical board owes a placement or
    removal, the orchestrator pauses move detection, so no ConfirmedMove is produced
    at all. Holding confirmed moves here was rejected — MoveDetector advances its
    baseline at confirm time, so held moves can go stale and corrupt the game.
    Expected-board pushes now happen in the orchestrator's update_state_callback
    wrapper (single authority); a fallback remains for vision-without-orchestrator.

    Per-move handling lives in _handle_confirmed_move (Task 7 extraction) — this
    loop is now just the poll/dispatch/throttle shell.
    """
    from katrain.vision.ipc import ConfirmedMove

    log = logging.getLogger("katrain_web.vision")
    while True:
        try:
            vision = getattr(app.state, "vision", None)
            if vision and vision.bound_session_id:
                move_data = vision.get_confirmed_move()
                if move_data and isinstance(move_data, ConfirmedMove):
                    retry_delay = await _handle_confirmed_move(app, vision, vision.bound_session_id, move_data, log)
                    if retry_delay:
                        await asyncio.sleep(retry_delay)
                        continue
        except asyncio.CancelledError:
            break
        except Exception as e:
            log.error("Vision move poller error: %s", e)
        await asyncio.sleep(0.1)


def build_frontend(force: bool = False):
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

    # Board/kiosk terminals serve the lean kiosk-2d bundle (no three.js, board-proxy
    # API base); the full server serves the complete build. Build/check the matching
    # output so board mode never falls back to the full bundle (which calls
    # /api/v1/live and 503s in board mode).
    is_board = settings.KATRAIN_MODE == "board"
    build_cmd = ["npm", "run", "build:kiosk-2d"] if is_board else ["npm", "run", "build"]
    out_dirname = "static-kiosk-2d" if is_board else "static"
    static_index = ui_path.parent / out_dirname / "index.html"
    if static_index.exists() and not force:
        logging.getLogger("katrain_web").info(
            "Frontend already built at %s, skipping (use --force-build to rebuild).",
            static_index.parent,
        )
        return

    print(f"Building frontend ({out_dirname})...", flush=True)
    try:
        # Check dependencies
        if not (ui_path / "node_modules").exists():
            print("Installing frontend dependencies...", flush=True)
            subprocess.run(["npm", "install"], cwd=ui_path, check=True, capture_output=False)

        # Build
        subprocess.run(build_cmd, cwd=ui_path, check=True, capture_output=False)
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
    parser.add_argument(
        "--force-build",
        action="store_true",
        help="Force a fresh `npm run build` even if katrain/web/static/index.html already exists.",
    )
    parser.add_argument("--log-level", default="warning")
    parser.add_argument("--disable-engine", action="store_true")
    parser.add_argument(
        "--ui",
        default=None,
        help="Interface mode to use. web (default) starts the FastAPI server, while desktop launches the Kivy GUI.",
    )
    parser.add_argument(
        "--vision-backend", default="onnx", choices=["onnx", "rknn", "ultralytics"], help="Vision inference backend"
    )
    parser.add_argument(
        "--vision-model", default=None, help="Path to vision model file. Providing this enables the vision service."
    )
    parser.add_argument("--vision-camera", default="0", help="Camera device ID (int) or path (e.g. /dev/video73)")
    parser.add_argument(
        "--vision-resolution", default="1280x720", help="Camera resolution WxH (e.g. 640x480, 1280x720, 2560x1440)"
    )
    parser.add_argument(
        "--vision-confidence",
        type=float,
        default=None,
        help="Detection confidence threshold (default: 0.5). Lower to catch weak real stones; "
        "raise to reject glare false positives.",
    )
    parser.add_argument(
        "--vision-confidence-keep",
        type=float,
        default=None,
        help="Hysteresis 'keep' threshold: a cell already holding a stone keeps it at this lower "
        "confidence (default: max(0.25, confidence - 0.15)). Fights weak-light flicker.",
    )
    parser.add_argument(
        "--vision-enhance",
        choices=["clahe", "off"],
        default=None,
        help="Pre-inference enhancement of the warped board image (default: clahe — "
        "measurably lifts weak-light stone confidence).",
    )
    parser.add_argument(
        "--vision-move-frames",
        type=int,
        default=None,
        help="Consecutive stable frames a single new stone must persist before it is accepted "
        "as a move (default: 5). Raise to reject transient false positives; lower for snappier "
        "move registration.",
    )
    parser.add_argument(
        "--vision-frame-average",
        type=int,
        default=None,
        help="Rolling average of the last N warped frames before inference (default: 8; 0/1 "
        "disables). Cuts weak-light sensor noise ~sqrt(N); auto-resets on motion.",
    )
    parser.add_argument(
        "--vision-ambiguous-confidence",
        type=float,
        default=None,
        help="Confirmed moves below this confidence go to the on-screen confirmation card "
        "instead of auto-playing (default: 0.55). Far-side stones meter ~0.36-0.45 on the "
        "Mac rig — lower this to auto-play them.",
    )
    parser.add_argument(
        "--vision-auto-exposure",
        choices=["software", "off"],
        default=None,
        help="Software AE: drive board-region median brightness into the target band by "
        "adjusting exposure at runtime (default: software; advisory-only on macOS).",
    )
    parser.add_argument(
        "--vision-ae-target",
        default=None,
        help="Software-AE target brightness as either a LO-HI gray-level band (e.g. 120-170) or a single "
        "midpoint value (e.g. 145) (default: 120-170).",
    )
    parser.add_argument(
        "--led-serial-port",
        default=None,
        help="Serial port of the ESP32-S3 LED board (e.g. /dev/cu.usbmodem2101). Providing this enables the LED service.",
    )
    parser.add_argument("--led-baud-rate", type=int, default=115200, help="LED serial baud rate. Default: 115200.")
    parser.add_argument(
        "--led-lut-path", default=None, help="Optional JSON (row,col)->index LUT; defaults to the built-in formula."
    )
    parser.add_argument(
        "--hint-engine",
        choices=["local", "cloud", "off"],
        default=None,
        help="AI hint engine routing for physical play (default: cloud, needs CLOUD_KATAGO_URL; falls back to local)",
    )
    parser.add_argument("--hint-top-n", type=int, default=None, help="AI hint top-N points (default: 3)")
    parser.add_argument(
        "--capture-camera",
        default=None,
        help="Camera device for physical-board capture/calibration (int or /dev/videoN). Shared with VisionService.",
    )
    parser.add_argument(
        "--capture-dir", default="~/.katrain/baipu_captures", help="Output dir for captured frames + manifests."
    )
    parser.add_argument("--capture-resolution", default="1280x720", help="Capture camera resolution WxH.")
    parser.add_argument(
        "--capture-exposure",
        type=float,
        default=None,
        help="Manual exposure value (camera-specific; tuned on the box).",
    )
    parser.add_argument(
        "--baipu-fiducial-mode",
        default=None,
        choices=["auto", "every-move", "off"],
        help="Geometry mode during baipu capture: auto (no-LED, default, live play) | "
        "every-move (LED fiducial, sub-pixel — use for TRAINING data capture) | off. "
        "Also settable via $KATRAIN_BAIPU_FIDUCIAL_MODE.",
    )
    args, _unknown = parser.parse_known_args()
    if args.baipu_fiducial_mode:
        settings._baipu_fiducial_mode = args.baipu_fiducial_mode

    # Configure vision service if model path provided
    if args.vision_model:
        from katrain.vision.config_service import VisionServiceConfig

        camera_dev = int(args.vision_camera) if args.vision_camera.isdigit() else args.vision_camera
        res_w, res_h = (int(x) for x in args.vision_resolution.split("x"))
        vision_kwargs = dict(
            enabled=True,
            backend=args.vision_backend,
            model_path=args.vision_model,
            camera_device=camera_dev,
            camera_width=res_w,
            camera_height=res_h,
            process_mode="worker" if settings.KATRAIN_MODE == "board" else "inprocess",
        )
        if args.vision_confidence is not None:
            vision_kwargs["confidence_threshold"] = args.vision_confidence
        if args.vision_confidence_keep is not None:
            vision_kwargs["confidence_keep"] = args.vision_confidence_keep
        if args.vision_enhance is not None:
            vision_kwargs["enhance"] = args.vision_enhance
        if args.vision_move_frames is not None:
            vision_kwargs["move_confirm_frames"] = args.vision_move_frames
        if args.vision_frame_average is not None:
            vision_kwargs["frame_average"] = args.vision_frame_average
        if args.vision_ambiguous_confidence is not None:
            vision_kwargs["ambiguous_confidence"] = args.vision_ambiguous_confidence
        if args.vision_auto_exposure is not None:
            vision_kwargs["auto_exposure"] = args.vision_auto_exposure
        if args.vision_ae_target is not None:
            vision_kwargs["ae_target"] = args.vision_ae_target
        settings._vision_config = VisionServiceConfig(**vision_kwargs)

    # Configure LED service if a serial port was provided
    if args.led_serial_port:
        from katrain.web.core.led_service import LedServiceConfig

        settings._led_config = LedServiceConfig(
            enabled=True,
            serial_port=args.led_serial_port,
            baud_rate=args.led_baud_rate,
            lut_path=args.led_lut_path,
        )

    # Configure physical-play orchestrator overrides if provided
    if args.hint_engine is not None or args.hint_top_n is not None:
        from katrain.web.core.physical_play import PhysicalPlayConfig

        settings._physical_play_config = PhysicalPlayConfig(
            hint_engine=args.hint_engine or PhysicalPlayConfig.hint_engine,
            hint_top_n=args.hint_top_n or 3,
        )

    # Configure capture service if a capture camera was provided
    if args.capture_camera is not None:
        from katrain.web.core.capture_service import CaptureServiceConfig

        cap_dev = int(args.capture_camera) if str(args.capture_camera).isdigit() else args.capture_camera
        cap_w, cap_h = (int(x) for x in args.capture_resolution.split("x"))
        settings._capture_config = CaptureServiceConfig(
            enabled=True,
            camera_device=cap_dev,
            width=cap_w,
            height=cap_h,
            out_dir=args.capture_dir,
            exposure=args.capture_exposure,
        )

    # Build frontend if running in web mode and not explicitly disabled (could add flag later if needed)
    # We only build if we are actually starting the web server, or if --ui=web is explicit
    # However, create_app is used by uvicorn workers too, so we should be careful.
    # But run_web is the entry point.
    if not args.reload:  # Skip build in reload mode to avoid loops
        build_frontend(force=args.force_build)

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
        access_log=False,  # Disable access logs to keep console clean for KataGo logs
    )


if __name__ == "__main__":
    run_web()
