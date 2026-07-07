"""回归：/ws/vision 必须注册在 /ws/{session_id} 之前——Starlette 按注册顺序匹配
websocket 路由，catch-all 会把 /ws/vision 当成 session_id="vision" 吞掉并以
1008 "Session not found" 关闭。这个遮蔽曾让所有视觉事件（疑似落子确认卡、
确认中提示、盘面异常对话框）从未到达过前端。"""

from starlette.routing import WebSocketRoute


def test_ws_vision_registered_before_session_catchall():
    from katrain.web.server import create_app

    app = create_app(enable_engine=False)
    ws_paths = [r.path for r in app.routes if isinstance(r, WebSocketRoute)]
    assert "/ws/vision" in ws_paths
    assert "/ws/{session_id}" in ws_paths
    assert ws_paths.index("/ws/vision") < ws_paths.index("/ws/{session_id}")
