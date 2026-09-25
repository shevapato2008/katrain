"""Local compose keeps the independent admin service off public interfaces."""

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


def test_admin_service_is_loopback_only_and_has_private_credentials():
    compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text())
    web = compose["services"]["katrain-web"]
    admin = compose["services"]["katrain-admin"]
    assert admin["profiles"] == ["admin"]
    assert admin["ports"] == ["127.0.0.1:${KATRAIN_ADMIN_HOST_PORT:-8010}:8010"]
    assert admin["image"] == web["image"]
    assert admin["command"] == ["python3", "-m", "katrain.web.admin"]
    admin_env = "\n".join(admin["environment"])
    web_env = "\n".join(web["environment"])
    for name in (
        "KATRAIN_ADMIN_USERNAME",
        "KATRAIN_ADMIN_PASSWORD_HASH",
        "KATRAIN_ADMIN_SESSION_SECRET",
        "KATRAIN_ADMIN_ENV",
    ):
        assert name in admin_env
        assert name not in web_env


def test_web_image_builds_the_separate_admin_ui():
    dockerfile = (ROOT / "Dockerfile.web").read_text()
    assert "npm run build:admin" in dockerfile
