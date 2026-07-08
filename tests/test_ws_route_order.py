"""Regression: websocket route registration order.

Starlette matches websocket routes in registration order. `/ws/{session_id}` is a
catch-all param route that matches ANY `/ws/<x>`, so a more specific route like
`/ws/vision` MUST be registered before it. If the param route wins, `/ws/vision`
connections are handled by the game-session endpoint, which looks up session
"vision", fails, and closes with 1008 "Session not found" — silently killing ALL
kiosk vision events (physical tsumego then hangs forever at "clear board").
"""

from starlette.routing import WebSocketRoute

from katrain.web.server import create_app


def test_ws_vision_registered_before_session_param_route():
    app = create_app(enable_engine=False)
    ws_paths = [r.path for r in app.routes if isinstance(r, WebSocketRoute)]

    assert "/ws/vision" in ws_paths, ws_paths
    assert "/ws/{session_id}" in ws_paths, ws_paths
    # Specific route must precede the catch-all param route.
    assert ws_paths.index("/ws/vision") < ws_paths.index("/ws/{session_id}"), ws_paths
