from types import SimpleNamespace
import httpx
import pytest
from katrain.web.core.config import settings
from katrain.web.api.v1.endpoints.auth import get_current_user, get_current_user_optional


@pytest.fixture
def real_runtime(monkeypatch):
    import importlib.util
    from pathlib import Path
    import katrain.web.session as session_module

    spec = importlib.util.spec_from_file_location(
        "_membership_real_interface", Path(session_module.__file__).with_name("interface.py")
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(session_module, "WebKaTrain", module.WebKaTrain)
    return module


def test_state_position_key_uses_current_full_path_in_board_snapshot(monkeypatch, real_runtime):
    from katrain.core.game_node import GameNode
    from katrain.core.sgf_parser import Move
    from katrain.web.core.billing_input import canonical_analysis_input
    from katrain.web.core.paid_analysis import session_position_sgf
    from katrain.web.session import SessionManager

    runtime_session = SessionManager(enable_engine=False).create_session(user_id=10, skip_initial_analysis=True)
    runtime = runtime_session.katrain
    root = runtime.game.root
    root.set_property("AB", ["aa", "ba"])
    root.set_property("AW", ["bb"])
    root.set_property("PL", "W")
    cursor = GameNode(parent=root, move=Move.from_gtp("D4", player="W"))
    GameNode(parent=cursor, move=Move.from_gtp("Q16", player="B"))
    runtime.game.set_current_node(cursor)
    original_update_timer = runtime.update_timer

    def update_timer_inside_snapshot():
        assert runtime.ai_ladder_commit_lock._is_owned(), "state must hold the real AI commit lock"
        original_update_timer()

    monkeypatch.setattr(runtime, "update_timer", update_timer_inside_snapshot)
    state = runtime.get_state()
    sgf = session_position_sgf(runtime_session, SimpleNamespace(id=10))
    assert state["expected_position_key"] == canonical_analysis_input(sgf, "position", "normal")["fingerprint"]
    assert state["current_node_id"] == id(cursor) and state["current_node_index"] == 1
    assert canonical_analysis_input(sgf, "position", "normal")["moves"] == [["W", "D4"]]


@pytest.mark.parametrize("unsupported", ["midgame_setup", "overlong"])
def test_unsupported_position_keeps_state_with_no_position_key(real_runtime, unsupported):
    from katrain.core.game_node import GameNode
    from katrain.core.sgf_parser import Move
    from katrain.web.session import SessionManager

    runtime = SessionManager(enable_engine=False).create_session(user_id=10, skip_initial_analysis=True).katrain
    cursor = runtime.game.play(Move.from_gtp("D4", player="B"), analyze=False)
    if unsupported == "midgame_setup":
        cursor.set_property("AB", "aa")
    else:
        for index in range(500):
            cursor = GameNode(parent=cursor, move=Move(None, "W" if index % 2 == 0 else "B"))
        runtime.game.set_current_node(cursor)
    state = runtime.get_state()
    assert state["current_node_id"] == id(cursor)
    assert state["expected_position_key"] is None


@pytest.fixture
def paid_play_api(monkeypatch, real_runtime):
    from fastapi import FastAPI
    from katrain.web.api.v1.endpoints import billing, paid_analysis
    from katrain.web.api.v1.endpoints.auth import require_writable_user
    from katrain.web.core.db import get_db
    from katrain.web.session import SessionManager

    monkeypatch.setattr(settings, "MEMBERSHIP_MODE", "enabled")
    monkeypatch.setattr(settings, "KATRAIN_MODE", "server")
    app = FastAPI()
    app.include_router(billing.router, prefix="/api/v1/billing")
    app.include_router(paid_analysis.router, prefix="/api/v1/analysis")
    app.state.session_manager = SessionManager(enable_engine=False)
    owner = SimpleNamespace(id=10, username="owner")
    session = app.state.session_manager.create_session(user_id=10, skip_initial_analysis=True)
    app.dependency_overrides[require_writable_user] = lambda: owner

    class NoDatabaseWork:
        def __getattr__(self, name):
            pytest.fail("Rejected play request reached database: " + name)

    app.dependency_overrides[get_db] = lambda: NoDatabaseWork()
    calls = []

    def no_billing(*args, **kwargs):
        calls.append("billing")
        pytest.fail("Rejected play request reached billing")

    async def no_engine(**kwargs):
        calls.append("engine")
        pytest.fail("Rejected play request reached engine")

    monkeypatch.setattr(billing.operations, "quote_operation", no_billing)
    monkeypatch.setattr(paid_analysis.ops, "reserve_operation_in_transaction", no_billing)
    app.state.paid_analysis_client = SimpleNamespace(analyze=no_engine)
    return app, session, owner, calls


@pytest.mark.asyncio
@pytest.mark.parametrize("route", ["quote", "execute"])
@pytest.mark.parametrize("failure", ["advanced", "missing_key", "stale_key", "unsupported_position"])
async def test_play_quote_and_execute_reject_before_billing(paid_play_api, route, failure):
    from katrain.core.sgf_parser import Move

    app, session, _, calls = paid_play_api
    key = session.katrain.get_state().get("expected_position_key", "old-contract")
    body = {"session_id": session.session_id, "profile": "normal", "expected_position_key": key}
    if failure == "advanced":
        body["profile"] = "advanced"
    elif failure == "missing_key":
        body.pop("expected_position_key")
    else:
        # Browser still shows the last WS frame after the server has committed a move.
        session.katrain.game.play(Move.from_gtp("D4", player="B"), analyze=False)
        if failure == "unsupported_position":
            session.katrain.game.current_node.set_property("AB", "aa")
    if route == "quote":
        body["kind"] = "position"
        path = "/api/v1/billing/quotes"
    else:
        body.update(quote_token="not-used", idempotency_key="not-reserved")
        path = "/api/v1/analysis/positions"
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(path, json=body)
    assert response.status_code == (403 if failure == "advanced" else 409), response.text
    assert response.json()["detail"]["code"] == (
        "position_profile_unavailable" if failure == "advanced" else "position_changed"
    )
    assert calls == []


def test_play_capture_and_research_advanced_preserve_session_guards(paid_play_api, monkeypatch):
    from fastapi import HTTPException
    from katrain.web.api.v1.endpoints.billing import BillingQuoteRequest
    from katrain.web.api.v1.endpoints.paid_analysis import _position_input
    from katrain.web.core.billing_input import canonical_analysis_input
    from katrain.web.core import paid_analysis

    app, session, owner, _ = paid_play_api
    request = SimpleNamespace(app=app)
    key = session.katrain.get_state().get("expected_position_key", "old-contract")
    body = BillingQuoteRequest(kind="position", profile="normal", session_id=session.session_id)
    body = body.model_copy(update={"expected_position_key": key})
    serialize = paid_analysis.current_position_sgf

    def serialize_inside_snapshot(runtime):
        assert session.lock.locked() and runtime.ai_ladder_commit_lock._is_owned()
        return serialize(runtime)

    monkeypatch.setattr(paid_analysis, "current_position_sgf", serialize_inside_snapshot)
    capture = _position_input(request, body, owner)
    assert capture.session_id is None
    assert canonical_analysis_input(capture.sgf, "position", "normal")["fingerprint"] == key
    session.mode = "research"
    research = _position_input(
        request, body.model_copy(update={"profile": "advanced", "expected_position_key": None}), owner
    )
    assert research.profile == "advanced" and research.sgf == capture.sgf
    for attr, value in [("bot_game", True), ("user_id", 99)]:
        setattr(session, attr, value)
        with pytest.raises(HTTPException) as blocked:
            _position_input(request, body, owner)
        assert blocked.value.status_code == 403
        setattr(session, attr, False if attr == "bot_game" else 10)
    for attr, value in [("game_type", "ranked"), ("pvp_bot_session", True)]:
        previous = getattr(session.katrain, attr, None)
        setattr(session.katrain, attr, value)
        with pytest.raises(HTTPException) as blocked:
            _position_input(request, body, owner)
        assert blocked.value.status_code == 403
        setattr(session.katrain, attr, previous)


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["enabled", "paused"])
async def test_real_mounted_legacy_apis_cannot_trigger_engine(monkeypatch, mode, real_runtime):
    from katrain.web.server import create_app

    monkeypatch.setattr(settings, "MEMBERSHIP_MODE", mode)
    app = create_app(enable_engine=False)
    owner = SimpleNamespace(id=10, uuid="account", username="owner")
    app.dependency_overrides[get_current_user] = lambda: owner
    app.dependency_overrides[get_current_user_optional] = lambda: owner
    session = app.state.session_manager.create_session(user_id=10, skip_initial_analysis=True)

    class Engine:
        calls = 0

        async def route(self, payload):
            self.calls += 1
            return {"ownership": [0] * 361}

    engine = Engine()
    app.state.router = engine
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
        for path, data in [
            ("/api/v1/analysis/quick-analyze", {"moves": []}),
            ("/api/v1/analysis/analyze", {"session_id": session.session_id, "payload": {"maxVisits": 100}}),
            ("/api/v1/hint", {"session_id": session.session_id}),
            ("/api/analysis/current", {"session_id": session.session_id}),
            ("/api/analysis/game", {"session_id": session.session_id}),
        ]:
            response = await c.post(path, json=data)
            assert response.status_code in (409, 503), (path, response.text)
    assert engine.calls == 0


def test_private_state_removes_all_derived_analysis(monkeypatch):
    from katrain.web.core.paid_analysis import strip_private_analysis

    state = {
        "analysis": {"moves": [{"move": "C3"}]},
        "commentary": "Winrate 99%",
        "history": [{"score": 5, "winrate": 0.99, "move": "C3"}],
        "stones": [["B", [2, 2], 4, 1]],
        "ghost_stones": [["B", [1, 1]]],
        "note": "analysis note",
        "board_size": [9, 9],
        "timer": {"paused": False},
        "end_result": "B+3.0?",
    }
    clean = strip_private_analysis(state)
    assert clean["analysis"] is None and clean["commentary"] == "" and clean["note"] == ""
    assert clean["history"][0]["score"] is None and clean["stones"][0][2] is None
    assert clean["ghost_stones"] == [] and clean["end_result"] is None
    assert clean["board_size"] == [9, 9] and clean["timer"] == {"paused": False}


def test_navigation_does_not_start_free_analysis_in_enabled_mode(monkeypatch, real_runtime):
    from katrain.web.session import SessionManager

    monkeypatch.setattr(settings, "MEMBERSHIP_MODE", "enabled")
    runtime = SessionManager(enable_engine=False).create_session(user_id=1, skip_initial_analysis=True).katrain
    node = runtime.game.current_node
    calls = []
    monkeypatch.setattr(node, "analyze", lambda *a, **kw: calls.append(kw))
    runtime("nav", id(node))
    assert calls == []


def test_real_state_and_callback_remove_internal_ai_analysis(monkeypatch, real_runtime):
    from katrain.web.session import SessionManager

    monkeypatch.setattr(settings, "MEMBERSHIP_MODE", "enabled")
    manager = SessionManager(enable_engine=False)
    session = manager.create_session(user_id=1, skip_initial_analysis=True)
    runtime = session.katrain
    runtime.game.current_node.analysis = {
        "root": {"visits": 500, "scoreLead": 3.0, "winrate": 0.9},
        "moves": {},
        "ownership": [0.0] * 361,
    }
    runtime.preview_pv = [["B", [2, 2]]]
    state = runtime.get_state()
    manager._on_state(session.session_id, state)
    assert state["analysis"] is None and state["ghost_stones"] == []
    assert session.last_state["analysis"] is None
    assert runtime.should_suppress_auto_eval()
    monkeypatch.setattr(settings, "MEMBERSHIP_MODE", "legacy")
    assert runtime.get_state()["analysis"] is None  # a hot rollback cannot reopen the cache


def test_ai_selection_still_receives_internal_analysis(monkeypatch, real_runtime):
    from katrain.web.session import SessionManager
    import katrain.core.ai as ai

    monkeypatch.setattr(settings, "MEMBERSHIP_MODE", "enabled")
    runtime = SessionManager(enable_engine=False).create_session(user_id=1, skip_initial_analysis=True).katrain
    runtime.players_info["B"] = SimpleNamespace(ai=True, strategy="ai:default", player="B")
    node = runtime.game.current_node
    calls = []
    monkeypatch.setattr(node, "analyze", lambda *a, **kw: calls.append(kw))

    def generate(game, mode, options):
        assert calls, "AI policy selection must receive the regular analysis it waits for"
        return None

    monkeypatch.setattr(ai, "generate_ai_move", generate)
    runtime._do_ai_move(node)


def test_websocket_initial_cached_state_does_not_leak(monkeypatch, real_runtime):
    from contextlib import asynccontextmanager
    from fastapi.testclient import TestClient
    from katrain.web.server import create_app
    from katrain.web.core.auth import create_access_token

    monkeypatch.setattr(settings, "MEMBERSHIP_MODE", "enabled")
    monkeypatch.setattr(settings, "KATRAIN_BOX_SSO", False)
    app = create_app(enable_engine=False)

    @asynccontextmanager
    async def no_lifespan(app):
        yield

    app.router.lifespan_context = no_lifespan
    owner = SimpleNamespace(id=10, uuid="owner", username="owner")
    app.state.user_repo = SimpleNamespace(get_user_by_username=lambda username: vars(owner))
    session = app.state.session_manager.create_session(user_id=10, skip_initial_analysis=True)
    session.last_state = {
        **session.last_state,
        "analysis": {"winrate": 0.9},
        "commentary": "private",
        "ghost_stones": [["B", [2, 2]]],
    }
    token = create_access_token(data={"sub": "owner"})
    with TestClient(app) as c:
        with c.websocket_connect("/ws/" + session.session_id + "?token=" + token) as ws:
            state = ws.receive_json()["state"]
            assert state["analysis"] is None and state["commentary"] == "" and state["ghost_stones"] == []


def test_internal_ai_logs_and_automatic_game_report_are_private(monkeypatch, real_runtime):
    from katrain.web.session import SessionManager
    from katrain.core.constants import OUTPUT_DEBUG

    monkeypatch.setattr(settings, "MEMBERSHIP_MODE", "enabled")
    runtime = SessionManager(enable_engine=False).create_session(user_id=1, skip_initial_analysis=True).katrain
    delivered = []
    runtime.message_callback = lambda kind, data: delivered.append((kind, data))
    runtime.log("Top policy move C3 winrate 0.9", OUTPUT_DEBUG)
    runtime.game.current_node.end_state = "B+R"
    runtime._do_update_state()
    assert not any(kind in ("log", "game_report") for kind, _ in delivered)


def test_generic_hyphenated_analysis_action_is_guarded(monkeypatch, real_runtime):
    from fastapi import HTTPException
    from katrain.web.session import SessionManager

    monkeypatch.setattr(settings, "MEMBERSHIP_MODE", "enabled")
    runtime = SessionManager(enable_engine=False).create_session(user_id=1, skip_initial_analysis=True).katrain
    with pytest.raises(HTTPException) as blocked:
        runtime("analyze-extra", "ponder")
    assert blocked.value.status_code == 409


@pytest.mark.asyncio
async def test_active_app_cannot_hot_rollback_sessionless_raw_proxy(monkeypatch, real_runtime):
    from katrain.web.server import create_app

    monkeypatch.setattr(settings, "MEMBERSHIP_MODE", "enabled")
    app = create_app(enable_engine=False)
    owner = SimpleNamespace(id=10, username="owner")
    app.dependency_overrides[get_current_user] = lambda: owner
    calls = []

    async def route(payload):
        calls.append(payload)
        return {"ownership": [0] * 361}

    app.state.router = SimpleNamespace(route=route)
    monkeypatch.setattr(settings, "MEMBERSHIP_MODE", "legacy")
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
        response = await c.post("/api/v1/analysis/quick-analyze", json={"moves": []})
        assert response.status_code == 409
    assert calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["enabled", "paused", "hot_legacy"])
async def test_sgf_export_keeps_manual_game_without_internal_analysis(monkeypatch, real_runtime, mode):
    from katrain.core.game_node import GameNode
    from katrain.core.sgf_parser import SGF, Move
    from katrain.web.server import create_app

    class GameParser(SGF):
        _NODE_CLASS = GameNode

    monkeypatch.setattr(settings, "MEMBERSHIP_MODE", "enabled" if mode == "hot_legacy" else mode)
    app = create_app(enable_engine=False)
    owner = SimpleNamespace(id=10, username="owner", uuid="owner")
    app.dependency_overrides[get_current_user_optional] = lambda: owner
    session = app.state.session_manager.create_session(user_id=10, skip_initial_analysis=True)
    runtime = session.katrain
    root = runtime.game.root
    runtime._config["trainer"].update(save_analysis=True, save_feedback=[True] * 6, save_marks=True)
    root.set_property("PB", "Black player")
    root.set_property("RE", "B+R")
    root.note = "Human root note"
    child = GameNode(parent=root, move=Move.from_gtp("D4", player="B"))
    child.note = "Human move comment"
    variation = GameNode(parent=root, move=Move.from_gtp("Q16", player="B"))
    variation.note = "Human variation"
    root.analysis = {
        "root": {"visits": 500, "scoreLead": 3.0, "winrate": 0.9},
        "moves": {
            "C3": {
                "move": "C3",
                "visits": 500,
                "scoreLead": 3.0,
                "winrate": 0.9,
                "prior": 0.2,
                "order": 0,
                "pv": ["C3", "Q16"],
            }
        },
        "ownership": [0.1] * 361,
        "policy": None,
        "completed": True,
    }
    child.analysis = {
        "root": {"visits": 500, "scoreLead": -1.0, "winrate": 0.4},
        "moves": {},
        "ownership": [0.1] * 361,
        "policy": None,
        "completed": True,
    }
    assert runtime.get_state()["analysis"] is None
    if mode == "hot_legacy":
        monkeypatch.setattr(settings, "MEMBERSHIP_MODE", "legacy")
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/sgf/save", params={"session_id": session.session_id})
    assert response.status_code == 200, response.text
    sgf = response.json()["sgf"]
    parsed = GameParser.parse_sgf(sgf)
    assert not parsed.load_analysis(), "SGF export must not recover private KT engine data"
    assert "KT[" not in sgf and "MA[" not in sgf and "SQ[" not in sgf
    assert parsed.get_property("PB") == "Black player" and parsed.get_property("RE") == "B+R"
    assert parsed.note == "Human root note"
    assert parsed.children[0].move.gtp() == "D4"
    assert parsed.children[0].note == "Human move comment"
    assert parsed.children[1].move.gtp() == "Q16" and parsed.children[1].note == "Human variation"
    # Serialization must not consume or mutate the engine data used by internal play.
    assert root.analysis["root"]["visits"] == 500 and child.analysis_complete
    assert runtime.get_sgf() == sgf  # automatic persistence uses this same safe boundary


def test_legacy_sgf_retains_analysis_save_opt_in(monkeypatch, real_runtime):
    from katrain.core.game_node import GameNode
    from katrain.core.sgf_parser import SGF
    from katrain.web.session import SessionManager

    class GameParser(SGF):
        _NODE_CLASS = GameNode

    monkeypatch.setattr(settings, "MEMBERSHIP_MODE", "legacy")
    runtime = SessionManager(enable_engine=False).create_session(user_id=10, skip_initial_analysis=True).katrain
    runtime._config["trainer"]["save_analysis"] = True
    runtime.game.root.analysis = {
        "root": {"visits": 500, "scoreLead": 3.0, "winrate": 0.9},
        "moves": {},
        "ownership": [0.1] * 361,
        "policy": None,
        "completed": True,
    }
    parsed = GameParser.parse_sgf(runtime.get_sgf())
    assert parsed.load_analysis() and parsed.analysis["root"]["visits"] == 500
