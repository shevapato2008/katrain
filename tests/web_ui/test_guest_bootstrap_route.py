from katrain.web.core.config import settings
from katrain.web.server import create_app


def test_guest_box_sso_bootstrap_route_is_registered(monkeypatch):
    monkeypatch.setattr(settings, "KATRAIN_MODE", "server")
    app = create_app(enable_engine=False)

    paths = {route.path for route in app.routes}

    assert "/api/v1/auth/box-sso/guest-bootstrap" in paths
